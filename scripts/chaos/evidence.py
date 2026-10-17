from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from uuid import UUID

try:
    from .common import SafetyError, p95, validate_id
    from .telemetry import metric_names
except ImportError:
    from common import SafetyError, p95, validate_id
    from telemetry import metric_names

PHASES = {"baseline": 60, "fault": 60, "drain": 15, "recovery": 60}
OPERATIONS = {"create", "control_catalog", "control_orders", "ready_catalog", "ready_orders", "live_catalog", "live_orders"}
SECRET = re.compile(r'''(?i)(?:password|passwd|secret|token)["']?\s*[:=]\s*["']?([^\s,}"']+)''')
METADATA_FIELDS = {
    "format_version", "evidence_kind", "run_id", "project", "docker_endpoint", "created_at", "experiment",
    "delay_ms", "ttl_seconds", "lease_seconds", "windows_seconds", "rate_per_operation", "max_business_in_flight",
    "request_timeout_seconds", "clock_domains", "versions", "state", "urls", "metric_urls", "images", "target",
    "product_id", "order_id", "activation", "capture_start_utc", "metric_names", "metrics_interval_seconds",
    "capture_end_utc", "cleanup_verified",
}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def identifier(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def timestamp(value):
    try:
        return isinstance(value, str) and datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is not None
    except ValueError:
        return False


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def require(condition):
    if not condition:
        raise ValueError("Evidence validation failed.")


def parse_debug_spans(text):
    spans = []
    for block in re.split(r"(?m)^\s*Span #\d+\s*$", text)[1:]:
        trace = re.search(r"(?m)^\s*Trace ID\s*:\s*([0-9a-fA-F]{32})\s*$", block)
        name = re.search(r"(?m)^\s*Name\s*:\s*(.+)$", block)
        kind = re.search(r"(?m)^\s*Kind\s*:\s*(\w+)", block)
        status = re.search(r"(?m)^\s*Status code\s*:\s*(\w+)", block)
        span_id = re.search(r"(?m)^\s*(?:Span ID|ID)\s*:\s*([0-9a-fA-F]{16})\s*$", block)
        parent = re.search(r"(?m)^\s*Parent ID\s*:\s*([0-9a-fA-F]{16})\s*$", block)
        if trace and name and kind and span_id:
            spans.append({"trace_id": trace[1].lower(), "name": name[1].strip(), "kind": kind[1].lower(),
                          "span_id": span_id[1].lower(), "parent_id": parent[1].lower() if parent else None,
                          "http_catalog": bool(re.search(r"(?:url\.full|http\.url): Str\(http://catalog:8000/products/", block)),
                          "status": status[1].lower() if status else None})
    return spans


class Evidence:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.errors = []
        self.warnings = []

    def issue(self, code):
        if code not in self.errors:
            self.errors.append(code)

    def text(self, relative, required=True):
        path = self.directory / relative
        try:
            if self.directory.is_symlink() or any(part.is_symlink() for part in (path, *path.parents) if part != self.directory.parent):
                raise ValueError("symlink")
            if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
                raise ValueError("file")
            text = path.read_bytes().decode("utf-8")
            if any(match[1] != "[REDACTED]" for match in SECRET.finditer(text)):
                self.issue("sensitive_content_detected")
                return ""
            return text
        except (OSError, ValueError):
            if required:
                self.issue("unreadable_" + relative.replace("/", "_"))
            return ""

    def json(self, relative, fallback):
        text = self.text(relative)
        try:
            return json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except ValueError:
            self.issue("invalid_json_" + relative.replace("/", "_"))
            return fallback

    def lines(self, relative):
        result = []
        for line in self.text(relative).splitlines():
            try:
                row = json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                if not isinstance(row, dict):
                    raise ValueError()
                result.append(row)
            except ValueError:
                self.issue("invalid_jsonl_" + relative.replace("/", "_"))
        return result

    def metadata(self):
        value = self.json("metadata.json", {})
        if not isinstance(value, dict):
            self.issue("metadata_schema")
            return {}
        try:
            require(set(value).issubset(METADATA_FIELDS))
            validate_id(value.get("run_id", ""))
            require(value["project"] == "chaos-" + value["run_id"])
            require(value["format_version"] == 2 and value["experiment"] == "E1")
            require(value["evidence_kind"] in {"measured", "synthetic"})
            require(identifier(value["product_id"]) and identifier(value["order_id"]))
            require(value["windows_seconds"] == PHASES)
            require(value["delay_ms"] == 6000 and value["ttl_seconds"] == 60)
            require(value["state"] in {"executed", "stopped"})
            require(value.get("cleanup_verified") is True)
            require(timestamp(value["capture_start_utc"]) and timestamp(value["capture_end_utc"]))
            require(value["clock_domains"]["requests"] == "host" and value["clock_domains"]["supervisor"] == "container")
            require(value.get("rate_per_operation", 1) == 1 and value.get("request_timeout_seconds", 8) == 8)
        except (AssertionError, KeyError, TypeError, ValueError, SafetyError):
            self.issue("metadata_schema_or_incomplete_run")
        return value

    def requests(self):
        rows = self.lines("requests.jsonl")
        valid = []
        seen = set()
        for row in rows:
            try:
                require(identifier(row["request_id"]) and row["request_id"] not in seen)
                seen.add(row["request_id"])
                require(row["phase"] in PHASES and row["operation"] in OPERATIONS)
                require(all(number(row[key]) for key in ("start_monotonic", "end_monotonic", "duration_seconds")))
                require(timestamp(row["start_utc"]) and timestamp(row["end_utc"]))
                require(row["end_monotonic"] >= row["start_monotonic"])
                require(abs(row["duration_seconds"] - row["end_monotonic"] + row["start_monotonic"]) < 0.001)
                status = row.get("status_code")
                require(status is None or isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599)
                require(row.get("transport_error") in {None, "request_failed"})
                if row.get("transport_error") is None:
                    require(row.get("response_request_id") == row["request_id"] and status is not None)
                if row["operation"] == "create" and status == 201 and row.get("transport_error") is None:
                    require(identifier(row.get("resource_id")))
                if row.get("resource_id") is not None:
                    require(row["operation"] == "create" and status == 201 and row.get("transport_error") is None)
                valid.append(row)
            except (AssertionError, KeyError, TypeError, ValueError):
                self.issue("requests_schema_or_duplicates")
        if not rows:
            self.issue("requests_empty")
        return valid

    def windows(self, events):
        windows = {}
        for name, duration in PHASES.items():
            starts = [row.get("monotonic") for row in events if row.get("event") == "phase_start" and row.get("phase") == name]
            ends = [row.get("monotonic") for row in events if row.get("event") == "phase_end" and row.get("phase") == name]
            if len(starts) != 1 or len(ends) != 1 or not all(number(v) for v in starts + ends):
                self.issue("phase_windows_incomplete")
                continue
            if not duration - 0.5 <= ends[0] - starts[0] <= duration + 5:
                self.issue("phase_duration_invalid")
            windows[name] = [starts[0], ends[0]]
        previous = None
        for window in windows.values():
            if previous is not None and window[0] < previous:
                self.issue("phase_windows_overlap")
            previous = window[1]
        if any(row.get("event") == "aborted" for row in events):
            self.issue("run_aborted")
        return windows

    def fault_bounds(self, events):
        arms = [row for row in events if row.get("event") == "supervisor_arm"]
        clean = [row for row in events if row.get("event", "").startswith("supervisor_") and isinstance(row.get("data"), dict)
                 and row["data"].get("state") == "clean"]
        if len(arms) != 1 or not clean:
            self.issue("activation_or_cleanup_missing")
            return None
        offsets = []
        for row in events:
            data = row.get("data", {})
            if not isinstance(data, dict) or not row.get("event", "").startswith("supervisor_"):
                continue
            values = [row.get("host_before"), row.get("host_after"), data.get("monotonic")]
            if all(number(v) for v in values) and values[0] <= values[1]:
                offsets.append((values[0] - values[2], values[1] - values[2]))
        try:
            lower, upper = max(v[0] for v in offsets), min(v[1] for v in offsets)
            require(lower <= upper)
            removed = [row["data"]["removed_monotonic"] for row in clean]
            require(removed and all(number(value) for value in removed) and max(removed) - min(removed) < 0.001)
            arm = arms[0]
            require(number(arm["host_after"]) and arm["data"]["state"] == "active")
            require(all(row["data"].get("reason") in {"manual", "ttl_expired"} for row in clean))
            require(all(not any(q.get("handle") in {"7a10:", "7a20:"} for q in row["data"]["snapshot"]["qdisc"]) for row in clean))
            removal = [removed[0] + lower, removed[0] + upper]
            require(removal[0] > arm["host_after"] + 10)
            require(number(arm["data"]["deadline"]) and 0 <= removed[0] - arm["data"]["deadline"] <= 5)
            return {"stable_start": arm["host_after"] + 10, "removal": removal,
                    "clock_offset": [lower, upper], "uncertainty_seconds": upper - lower}
        except (AssertionError, KeyError, TypeError, ValueError):
            self.issue("clock_mapping_or_cleanup_invalid")
            return None

    def metrics(self, windows, metadata):
        entries = self.lines("metrics/index.jsonl")
        coverage = {service: {name: [] for name in PHASES} for service in ("catalog", "orders")}
        discovered = {service: set() for service in coverage}
        seen = set()
        sequences = {service: [] for service in coverage}
        for entry in entries:
            try:
                service = entry["service"]
                require(service in coverage and number(entry["monotonic"]))
                require(entry["phase"] in {"preflight", *PHASES})
                require(isinstance(entry["sequence"], int) and not isinstance(entry["sequence"], bool) and entry["sequence"] >= 0)
                require(number(entry["end_monotonic"]) and entry["end_monotonic"] >= entry["monotonic"])
                require(timestamp(entry["utc"]) and entry["status_code"] == 200 and entry["error"] is None)
                require(re.fullmatch(r"metrics/" + service + r"-\d{5}\.prom", entry["file"]))
                require(entry["file"] not in seen)
                seen.add(entry["file"])
                text = self.text(entry["file"])
                require(hashlib.sha256(text.encode()).hexdigest() == entry["sha256"])
                names = metric_names(text)
                require(names)
                discovered[service].update(names)
                sequences[service].append(entry["sequence"])
                for phase, (start, end) in windows.items():
                    if start <= entry["monotonic"] < end:
                        coverage[service][phase].append(entry["monotonic"])
            except (AssertionError, KeyError, TypeError, ValueError):
                self.issue("metrics_capture_invalid")
        for service, phases in coverage.items():
            if sequences[service] != list(range(len(sequences[service]))):
                self.issue("metrics_sequence_incomplete")
            for phase, times in phases.items():
                if phase not in windows:
                    continue
                start, end = windows[phase]
                times = sorted(times)
                boundaries = [start, *times, end]
                if len(times) < max(1, math.ceil(PHASES[phase] / 5) - 2) or any(b - a > 10 for a, b in zip(boundaries, boundaries[1:])):
                    self.issue("metrics_coverage_incomplete")
            if sorted(discovered[service]) != metadata.get("metric_names", {}).get(service):
                self.issue("metric_names_mismatch")
        return {service: {phase: len(times) for phase, times in phases.items()} for service, phases in coverage.items()}

    def correlation(self, rows):
        api_logs = {}
        for service in ("catalog", "orders"):
            records = []
            for line in self.text(f"logs/{service}.log").splitlines():
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and identifier(row.get("request_id")):
                        records.append(row)
                except ValueError:
                    pass
            api_logs[service] = records
            if not records:
                self.issue("api_logs_missing")
        spans = parse_debug_spans(self.text("logs/otel-collector.log"))
        if not spans:
            self.issue("debug_trace_format_unrecognized_or_empty")
        self.text("logs/chaos-net.log")
        correlated = []
        timeout_correlated = 0
        for request in rows:
            if request["operation"] != "create" or request["phase"] != "fault" or request.get("status_code") is None:
                continue
            matches = [row for row in api_logs["orders"] if row.get("request_id") == request["request_id"] and row.get("status_code") == request["status_code"]]
            for log in matches:
                trace_id = log.get("trace_id")
                if not isinstance(trace_id, str) or not re.fullmatch(r"[0-9a-f]{32}", trace_id) or int(trace_id, 16) == 0:
                    continue
                related = [span for span in spans if span["trace_id"] == trace_id]
                business_ids = {span["span_id"] for span in related if span["name"] == "orders.order.create"}
                timed_out = request["status_code"] == 504 and request.get("error_code") == "catalog_timeout"
                if any(span["kind"] == "client" and span["http_catalog"] and span["parent_id"] in business_ids
                       and (not timed_out or span["status"] == "error") for span in related):
                    correlated.append({"request_id": request["request_id"], "trace_id": trace_id})
                    timeout_correlated += timed_out
                    break
        if not correlated:
            self.issue("fault_trace_correlation_missing")
        return {"fault_requests_correlated": len(correlated), "timeout_requests_correlated": timeout_correlated, "examples": correlated[:3],
                "recognized_spans": len(spans), "server_catalog_span_required": False}

    def persistence(self, rows, metadata):
        before = self.json("orders-before.json", [])
        after = self.json("orders-after.json", [])
        if not all(isinstance(values, list) and all(identifier(value) for value in values) and len(values) == len(set(values)) for values in (before, after)):
            self.issue("persistence_schema_invalid")
            return None
        if before != [metadata.get("order_id")]:
            self.issue("initial_orders_not_exclusive")
        created = [row["resource_id"] for row in rows if row["operation"] == "create" and row.get("resource_id") and row.get("transport_error") is None]
        matches = len(created) == len(set(created)) and set(after) == set(before) | set(created) and len(after) == len(before) + len(created)
        return {"before": len(before), "after": len(after), "created_201": len(created),
                "unexplained_delta": len(after) - len(before) - len(created), "identifiers_match": matches}

    def analyze(self):
        metadata = self.metadata()
        rows = self.requests()
        events = self.lines("events.jsonl")
        windows = self.windows(events)
        bounds = self.fault_bounds(events)
        phases = {}
        transitions = []
        for phase, window in windows.items():
            phases[phase] = {}
            for operation in sorted(OPERATIONS):
                selected = [row for row in rows if row["phase"] == phase and row["operation"] == operation]
                if any(not window[0] <= row["start_monotonic"] < window[1] for row in selected):
                    self.issue("request_start_outside_phase")
                transitions.extend(row["request_id"] for row in selected if row["end_monotonic"] >= window[1])
                expected = 201 if operation == "create" else 200
                success = sum(row["status_code"] == expected and row.get("transport_error") is None for row in selected)
                phases[phase][operation] = {
                    "attempts": len(selected), "successes": success, "success_rate": ratio(success, len(selected)),
                    "p95_seconds": p95([row["duration_seconds"] for row in selected]) if selected else None,
                    "transport_errors": sum(row.get("transport_error") is not None for row in selected),
                    "status_codes": {str(status): sum(row["status_code"] == status for row in selected)
                                     for status in sorted({row["status_code"] for row in selected}, key=str)},
                }
        eligible = [row for row in rows if bounds and row["phase"] == "fault" and row["operation"] == "create"
                    and bounds["stable_start"] <= row["start_monotonic"] < bounds["removal"][0]
                    and row["end_monotonic"] < bounds["removal"][0]]
        timeouts = [row for row in eligible if row["status_code"] == 504 and row.get("error_code") == "catalog_timeout" and row.get("transport_error") is None]
        timed = sum(4.5 <= row["duration_seconds"] <= 6.5 for row in timeouts)
        if len(eligible) < 30:
            self.issue("stable_fault_samples_insufficient")
        for phase in PHASES:
            for operation in ("create", "control_catalog", "control_orders"):
                expected = 0 if phase == "drain" and operation == "create" else PHASES[phase]
                if phases.get(phase, {}).get(operation, {}).get("attempts") != expected:
                    self.issue("scheduled_business_load_incomplete")
            for operation in ("live_catalog", "live_orders", "ready_catalog", "ready_orders"):
                if phases.get(phase, {}).get(operation, {}).get("attempts") != PHASES[phase] // 5:
                    self.issue("scheduled_health_load_incomplete")
        netem_seen = any(q.get("handle") == "7a20:" and q.get("kind") == "netem" and number(q.get("packets")) and q["packets"] > 0
                         for event in events if isinstance(event.get("data"), dict)
                         for q in event["data"].get("snapshot", {}).get("qdisc", []))
        if not netem_seen:
            self.issue("netem_effect_not_evidenced")
        metrics = self.metrics(windows, metadata)
        correlation = self.correlation(rows)
        persistence = self.persistence(rows, metadata)
        readiness = [row for row in rows if bounds and row["operation"] == "ready_orders" and row["start_monotonic"] >= bounds["removal"][1]
                     and row["status_code"] == 200 and row.get("transport_error") is None]
        readiness.sort(key=lambda row: row["end_monotonic"])
        recovery = [max(0, readiness[0]["end_monotonic"] - bound) for bound in reversed(bounds["removal"])] if readiness else None
        if not readiness:
            self.issue("recovery_readiness_missing")
        criteria = {"timeout_rate": (ratio(len(timeouts), len(eligible)) or 0) >= 0.95,
                    "timeout_duration": (ratio(timed, len(timeouts)) or 0) >= 0.95,
                    "persistence": bool(persistence and persistence["identifiers_match"]),
                    "readiness_within_60s": bool(recovery and recovery[1] <= 60)}
        for phase in ("baseline", "recovery"):
            criteria[phase] = all(
                phases.get(phase, {}).get(operation, {}).get("success_rate") == 1
                and (phases[phase][operation]["p95_seconds"] or 0) < 1
                for operation in ("create", "control_catalog", "control_orders"))
        criteria["controls"] = all(phases.get(phase, {}).get(operation, {}).get("success_rate") == 1
                                   and (phases[phase][operation]["p95_seconds"] or 0) < 1
                                   for phase in PHASES for operation in ("control_catalog", "control_orders"))
        criteria["liveness"] = all(phases.get(phase, {}).get(operation, {}).get("success_rate") == 1
                                   for phase in PHASES for operation in ("live_catalog", "live_orders"))
        if recovery and recovery[0] <= 60 < recovery[1]:
            self.issue("recovery_clock_uncertainty")
        calculated = "inconclusa" if self.errors else "aceptada" if all(criteria.values()) else "refutada"
        synthetic = metadata.get("evidence_kind") != "measured"
        if synthetic:
            self.warnings.append("synthetic_evidence_is_not_an_operational_result")
        try:
            safe_run_id = validate_id(metadata.get("run_id", ""))
        except (SafetyError, TypeError):
            safe_run_id = None
        evidence_kind = metadata.get("evidence_kind") if metadata.get("evidence_kind") in {"measured", "synthetic"} else None
        return {"format_version": 2, "run_id": safe_run_id, "evidence_kind": evidence_kind,
                "integrity": {"complete": not self.errors, "errors": sorted(self.errors), "warnings": self.warnings},
                "hypothesis": "inconclusa" if synthetic else calculated, "calculated_hypothesis": calculated,
                "requires_manual_confirmation": True, "criteria": criteria, "windows": windows, "fault_bounds": bounds,
                "phases": phases, "transitions": sorted(set(transitions)), "total_attempts": len(rows),
                "fault": {"eligible_attempts": len(eligible), "catalog_timeouts": len(timeouts), "timeouts_in_duration": timed,
                          "timeout_rate": ratio(len(timeouts), len(eligible)), "duration_rate": ratio(timed, len(timeouts))},
                "persistence": persistence, "readiness_recovery_seconds": recovery,
                "metrics_coverage": metrics, "correlation": correlation}


def analyze_directory(directory):
    evidence = Evidence(directory)
    try:
        return evidence.analyze()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, SafetyError):
        evidence.issue("evidence_schema_inconsistent")
        return {"format_version": 2, "integrity": {"complete": False, "errors": sorted(evidence.errors)},
                "hypothesis": "inconclusa", "calculated_hypothesis": "inconclusa", "requires_manual_confirmation": True}
