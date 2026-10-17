from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

from scripts.chaos import analyze, check_evidence
from scripts.chaos.common import p95
from scripts.chaos.evidence import analyze_directory, parse_debug_spans
from scripts.chaos.telemetry import Telemetry, metric_names, read_metrics


def stamp(seconds):
    return (datetime(2026, 10, 16, tzinfo=timezone.utc) + timedelta(seconds=seconds)).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def save_lines(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def fixture(directory):
    root = Path(directory)
    (root / "metrics").mkdir()
    (root / "logs").mkdir()
    product, seed = str(uuid4()), str(uuid4())
    metadata = {
        "format_version": 2, "evidence_kind": "synthetic", "run_id": "fixture", "project": "chaos-fixture",
        "state": "executed", "experiment": "E1", "product_id": product, "order_id": seed,
        "windows_seconds": {"baseline": 60, "fault": 60, "drain": 15, "recovery": 60},
        "delay_ms": 6000, "ttl_seconds": 60, "metric_names": {"catalog": ["demo_metric"], "orders": ["demo_metric"]},
        "clock_domains": {"requests": "host", "supervisor": "container"},
        "capture_start_utc": stamp(0), "capture_end_utc": stamp(214),
        "cleanup_verified": True,
    }
    rows, events, metrics, created = [], [], [], []
    sequence = 0
    for phase, start, seconds in (("baseline", 0, 60), ("fault", 61, 60), ("drain", 126, 15), ("recovery", 141, 60)):
        events.extend([{"event": "phase_start", "phase": phase, "monotonic": start, "utc": stamp(start)},
                       {"event": "phase_end", "phase": phase, "monotonic": start + seconds, "utc": stamp(start + seconds)}])
        for second in range(seconds):
            operations = ["control_catalog", "control_orders"] + ([] if phase == "drain" else ["create"])
            if second % 5 == 0:
                operations += ["ready_catalog", "ready_orders", "live_catalog", "live_orders"]
            for operation in operations:
                request_id = str(uuid4())
                status = 201 if operation == "create" else 200
                duration = 0.1
                error = None
                if phase == "fault" and operation == "create":
                    status, duration, error = 504, 5.0, "catalog_timeout"
                if phase == "fault" and operation == "ready_orders":
                    status = 503
                row = {"request_id": request_id, "response_request_id": request_id, "operation": operation,
                       "phase": phase, "start_monotonic": start + second, "end_monotonic": start + second + duration,
                       "duration_seconds": duration, "start_utc": stamp(start + second), "end_utc": stamp(start + second + duration),
                       "status_code": status, "error_code": error, "transport_error": None}
                if operation == "create" and status == 201:
                    row["resource_id"] = str(uuid4())
                    created.append(row["resource_id"])
                rows.append(row)
            if second % 5 == 0:
                for service in ("catalog", "orders"):
                    text = f'demo_metric{{service="{service}"}} 1\n'
                    filename = f"metrics/{service}-{sequence:05d}.prom"
                    (root / filename).write_text(text)
                    metrics.append({"service": service, "sequence": sequence, "phase": phase,
                                    "utc": stamp(start + second + 0.5), "monotonic": start + second + 0.5,
                                    "end_monotonic": start + second + 0.6,
                                    "status_code": 200, "error": None, "file": filename,
                                    "sha256": hashlib.sha256(text.encode()).hexdigest()})
                sequence += 1
    events += [
        {"event": "supervisor_arm", "host_before": 60, "host_after": 60.2, "data": {
            "state": "active", "monotonic": 1000.1, "deadline": 1060,
            "snapshot": {"qdisc": [{"kind": "netem", "handle": "7a20:", "packets": 0}]}}},
        {"event": "supervisor_status", "host_before": 80, "host_after": 80.2, "data": {
            "state": "active", "monotonic": 1020.1,
            "snapshot": {"qdisc": [{"kind": "netem", "handle": "7a20:", "packets": 12}]}}},
        {"event": "supervisor_rollback", "host_before": 120.1, "host_after": 120.3, "data": {
            "state": "clean", "reason": "ttl_expired", "monotonic": 1060.2,
            "removed_monotonic": 1060.1, "snapshot": {"qdisc": [], "filters": []}}},
    ]
    save(root / "metadata.json", metadata)
    save_lines(root / "requests.jsonl", rows)
    save_lines(root / "events.jsonl", events)
    save_lines(root / "metrics/index.jsonl", metrics)
    save(root / "orders-before.json", [seed])
    save(root / "orders-after.json", [seed, *created])
    fault = next(row for row in rows if row["phase"] == "fault" and row["operation"] == "create")
    trace = "a" * 32
    save_lines(root / "logs/orders.log", [{"request_id": fault["request_id"], "status_code": 504, "trace_id": trace}])
    save_lines(root / "logs/catalog.log", [{"request_id": str(uuid4()), "status_code": 200}])
    (root / "logs/chaos-net.log").write_text('{"event":"removed"}\n')
    (root / "logs/otel-collector.log").write_text(
        f"Span #0\n    Trace ID : {trace}\n    ID : {'1' * 16}\n    Name : orders.order.create\n    Kind : Internal\n    Status code : Error\n"
        f"Span #1\n    Trace ID : {trace}\n    ID : {'2' * 16}\n    Parent ID : {'1' * 16}\n    Name : GET\n    Kind : Client\n    Status code : Error\n"
        f"    -> url.full: Str(http://catalog:8000/products/{product})\n")
    return metadata, rows, events, metrics


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.metadata, self.rows, self.events, self.metrics = fixture(self.root)

    def analyze(self):
        return analyze_directory(self.root)

    def test_complete_fixture_computes_acceptance_but_never_validates_real_run(self):
        result = self.analyze()
        self.assertEqual(result["integrity"]["errors"], [])
        self.assertEqual(result["calculated_hypothesis"], "aceptada")
        self.assertEqual(result["hypothesis"], "inconclusa")
        self.assertEqual(result["fault"]["eligible_attempts"], 44)
        self.assertEqual(result["persistence"]["unexplained_delta"], 0)
        self.assertTrue(result["requires_manual_confirmation"])

    def test_repeated_analysis_is_deterministic(self):
        self.assertEqual(json.dumps(self.analyze()), json.dumps(self.analyze()))

    def test_incorrect_timeout_duration_refutes_complete_evidence(self):
        for row in self.rows:
            if row["operation"] == "create" and row["phase"] == "fault":
                row.update(duration_seconds=7, end_monotonic=row["start_monotonic"] + 7, end_utc=stamp(row["start_monotonic"] + 7))
        save_lines(self.root / "requests.jsonl", self.rows)
        result = self.analyze()
        self.assertTrue(result["integrity"]["complete"], result["integrity"])
        self.assertEqual(result["calculated_hypothesis"], "refutada")

    def test_transition_requests_remain_in_global_count(self):
        result = self.analyze()
        self.assertTrue(result["transitions"])
        self.assertEqual(result["total_attempts"], len(self.rows))
        self.assertEqual(result["phases"]["fault"]["create"]["attempts"], 60)

    def test_transport_failures_remain_in_denominator(self):
        eligible = next(row for row in self.rows if row["phase"] == "fault" and row["operation"] == "create" and row["start_monotonic"] == 90)
        eligible.update(status_code=None, error_code=None, transport_error="request_failed", response_request_id=None)
        save_lines(self.root / "requests.jsonl", self.rows)
        result = self.analyze()
        self.assertEqual(result["fault"]["eligible_attempts"], 44)
        self.assertEqual(result["fault"]["catalog_timeouts"], 43)

    def test_missing_metrics_file_is_incomplete(self):
        (self.root / self.metrics[0]["file"]).unlink()
        self.assertFalse(self.analyze()["integrity"]["complete"])

    def test_metric_tampering_is_detected(self):
        (self.root / self.metrics[0]["file"]).write_text("demo_metric 999\n")
        self.assertIn("metrics_capture_invalid", self.analyze()["integrity"]["errors"])

    def test_missed_sampling_intervals_are_detected(self):
        save_lines(self.root / "metrics/index.jsonl", self.metrics[20:])
        self.assertIn("metrics_coverage_incomplete", self.analyze()["integrity"]["errors"])

    def test_unknown_trace_format_is_incomplete(self):
        (self.root / "logs/otel-collector.log").write_text("new unknown format\n")
        self.assertIn("debug_trace_format_unrecognized_or_empty", self.analyze()["integrity"]["errors"])

    def test_client_span_must_belong_to_business_span(self):
        path = self.root / "logs/otel-collector.log"
        path.write_text(path.read_text().replace("Parent ID : " + "1" * 16, "Parent ID : " + "3" * 16))
        self.assertIn("fault_trace_correlation_missing", self.analyze()["integrity"]["errors"])

    def test_database_client_error_cannot_substitute_for_http_client(self):
        path = self.root / "logs/otel-collector.log"
        path.write_text(path.read_text().replace("url.full", "db.statement"))
        self.assertIn("fault_trace_correlation_missing", self.analyze()["integrity"]["errors"])

    def test_catalog_server_span_not_required(self):
        result = self.analyze()
        self.assertTrue(result["integrity"]["complete"])
        self.assertEqual(result["correlation"]["timeout_requests_correlated"], 1)
        self.assertFalse(result["correlation"]["server_catalog_span_required"])

    def test_missing_trace_context_cannot_confirm_hypothesis(self):
        path = self.root / "logs/orders.log"
        path.write_text(path.read_text().replace('"' + "a" * 32 + '"', "null"))
        self.assertFalse(self.analyze()["integrity"]["complete"])

    def test_duplicate_requests_are_rejected(self):
        save_lines(self.root / "requests.jsonl", [*self.rows, self.rows[0]])
        self.assertIn("requests_schema_or_duplicates", self.analyze()["integrity"]["errors"])

    def test_nonfinite_duration_is_rejected(self):
        self.rows[0]["duration_seconds"] = float("nan")
        save_lines(self.root / "requests.jsonl", self.rows)
        self.assertFalse(self.analyze()["integrity"]["complete"])

    def test_bad_clock_domains_are_not_compared_directly(self):
        self.events[-1]["host_before"] = 200
        self.events[-1]["host_after"] = 201
        save_lines(self.root / "events.jsonl", self.events)
        self.assertIn("clock_mapping_or_cleanup_invalid", self.analyze()["integrity"]["errors"])

    def test_packet_counters_required_to_demonstrate_injection(self):
        self.events[-2]["data"]["snapshot"]["qdisc"][0]["packets"] = 0
        save_lines(self.root / "events.jsonl", self.events)
        self.assertIn("netem_effect_not_evidenced", self.analyze()["integrity"]["errors"])

    def test_residual_rules_prevent_cleanup_confirmation(self):
        self.events[-1]["data"]["snapshot"]["qdisc"] = [{"handle": "7a10:"}]
        save_lines(self.root / "events.jsonl", self.events)
        self.assertFalse(self.analyze()["integrity"]["complete"])

    def test_persistence_discrepancy_refutes_hypothesis(self):
        values = json.loads((self.root / "orders-after.json").read_text())
        save(self.root / "orders-after.json", [*values, str(uuid4())])
        result = self.analyze()
        self.assertTrue(result["integrity"]["complete"])
        self.assertEqual(result["calculated_hypothesis"], "refutada")
        self.assertEqual(result["persistence"]["unexplained_delta"], 1)

    def test_sensitive_content_is_never_echoed(self):
        path = self.root / "logs/orders.log"
        path.write_text(path.read_text() + '\n{"password":"do-not-print-this"}\n')
        result = self.analyze()
        self.assertIn("sensitive_content_detected", result["integrity"]["errors"])
        self.assertNotIn("do-not-print-this", json.dumps(result))

    def test_symlink_to_secret_is_not_read(self):
        path = self.root / "logs/orders.log"
        path.unlink()
        path.symlink_to(self.root / "metadata.json")
        self.assertIn("unreadable_logs_orders.log", self.analyze()["integrity"]["errors"])

    def test_legacy_format_requires_new_run(self):
        self.metadata["format_version"] = 1
        save(self.root / "metadata.json", self.metadata)
        self.assertFalse(self.analyze()["integrity"]["complete"])

    def test_cli_is_read_only_and_never_accesses_network(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("socket.socket", side_effect=AssertionError("No network")), redirect_stdout(io.StringIO()):
            self.assertEqual(check_evidence.main([str(self.root)]), 0)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_analyzer_writes_only_summary(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with redirect_stdout(io.StringIO()):
            self.assertEqual(analyze.main([str(self.root)]), 0)
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertTrue((self.root / "summary.json").is_file())

    def test_corrupt_stored_summary_is_rejected_by_read_only_verifier(self):
        save(self.root / "summary.json", {"hypothesis": "aceptada"})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(check_evidence.main([str(self.root)]), 1)
        self.assertIn("stored_summary_mismatch", json.loads(output.getvalue())["integrity"]["errors"])

    def test_generated_summary_is_consistent_with_verifier(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(analyze.main([str(self.root)]), 0)
            self.assertEqual(check_evidence.main([str(self.root)]), 0)

    def test_unknown_metadata_fields_fail_closed(self):
        self.metadata["unexpected_configuration"] = "not-public"
        save(self.root / "metadata.json", self.metadata)
        result = self.analyze()
        self.assertFalse(result["integrity"]["complete"])
        self.assertNotIn("not-public", json.dumps(result))

    def test_partial_metadata_is_a_report_not_an_exception(self):
        save(self.root / "metadata.json", {})
        self.assertFalse(self.analyze()["integrity"]["complete"])

    def test_invalid_metadata_identifiers_are_not_echoed(self):
        self.metadata["run_id"] = "private-value!"
        save(self.root / "metadata.json", self.metadata)
        self.assertNotIn("private-value!", json.dumps(self.analyze()))

    def test_resource_id_cannot_hide_failed_order_persistence(self):
        row = next(row for row in self.rows if row["status_code"] == 504)
        row["resource_id"] = str(uuid4())
        save_lines(self.root / "requests.jsonl", self.rows)
        self.assertIn("requests_schema_or_duplicates", self.analyze()["integrity"]["errors"])

    def test_redacted_field_is_not_reported_as_raw_secret(self):
        path = self.root / "logs/chaos-net.log"
        path.write_text('password=[REDACTED]\n{"event":"removed"}\n')
        self.assertTrue(self.analyze()["integrity"]["complete"])

    def test_zero_timeouts_can_refute_with_correlated_success_trace(self):
        created = []
        for row in self.rows:
            if row["operation"] == "create" and row["phase"] == "fault":
                row.update(status_code=201, error_code=None, resource_id=str(uuid4()))
                created.append(row["resource_id"])
        save_lines(self.root / "requests.jsonl", self.rows)
        path = self.root / "orders-after.json"
        save(path, json.loads(path.read_text()) + created)
        path = self.root / "logs/orders.log"
        path.write_text(path.read_text().replace('"status_code": 504', '"status_code": 201'))
        path = self.root / "logs/otel-collector.log"
        path.write_text(path.read_text().replace("Status code : Error", "Status code : Unset"))
        result = self.analyze()
        self.assertTrue(result["integrity"]["complete"], result["integrity"])
        self.assertEqual(result["calculated_hypothesis"], "refutada")

    def test_refuted_evidence_still_exits_zero(self):
        path = self.root / "orders-after.json"
        save(path, json.loads(path.read_text()) + [str(uuid4())])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(check_evidence.main([str(self.root)]), 0)


class TelemetryTests(unittest.TestCase):
    def test_metric_names_are_discovered_without_assuming_instrumentation_names(self):
        text = '# HELP custom_count counter\ncustom_count{label="value"} 2\ncustom_seconds_bucket{le="1"} 4\n'
        self.assertEqual(metric_names(text), ["custom_count", "custom_seconds_bucket"])

    def test_plain_text_error_is_not_accepted_as_metrics(self):
        self.assertEqual(metric_names("upstream unavailable\n"), [])
        self.assertEqual(metric_names("valid_sample 1\ninvalid_sample broken\n"), [])

    def test_remote_metric_url_is_rejected_without_request(self):
        with self.assertRaises(Exception), patch("socket.socket", side_effect=AssertionError("No network")):
            read_metrics("https://example.com/metrics")

    def test_sampling_saves_raw_data_hash_and_sanitizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "metrics").mkdir()
            failures = []
            telemetry = Telemetry({"metric_urls": {"catalog": "http://127.0.0.1:1"}}, root, lambda: "baseline", failures.append,
                                  sanitize=lambda value: value.replace("fake-private", "[REDACTED]"),
                                  request=lambda url: 'test_metric{label="fake-private"} 2\n')
            row = telemetry.sample("catalog", 0)
            self.assertEqual(failures, [])
            self.assertNotIn("fake-private", (root / row["file"]).read_text())
            self.assertEqual(telemetry.stop()["catalog"], ["test_metric"])

    def test_sampling_failure_is_recorded_and_aborts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "metrics").mkdir()
            failures = []

            def failed(url):
                raise OSError("fake-secret-transport-details")

            telemetry = Telemetry({"metric_urls": {"orders": "http://127.0.0.1:1"}}, root, lambda: "fault", failures.append, request=failed)
            row = telemetry.sample("orders", 0)
            self.assertEqual(row["error"], "metrics_capture_failed")
            self.assertEqual(failures, ["metrics_capture_failed"])
            self.assertNotIn("fake-secret", (root / "metrics/index.jsonl").read_text())

    def test_p95_uses_nearest_rank(self):
        self.assertEqual(p95(list(range(1, 21))), 19)


if __name__ == "__main__":
    unittest.main()
