from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time
from uuid import uuid4

try:
    from .common import SafetyError, append_json, http_request, p95, utc
except ImportError:
    from common import SafetyError, append_json, http_request, p95, utc


class Load:
    def __init__(self, metadata, output, request=http_request, clock=time.monotonic, sleep=time.sleep):
        self.metadata = metadata
        self.output = output
        self.request = request
        self.clock = clock
        self.sleep = sleep
        self.rows = []
        self.abort = threading.Event()
        self.lock = threading.Lock()
        self.reason = None
        self.current_phase = "preflight"

    def fail(self, reason):
        with self.lock:
            self.reason = self.reason or reason
            self.abort.set()

    def attempt(self, phase, operation, url, body=None):
        request_id = str(uuid4())
        started = self.clock()
        row = {
            "request_id": request_id, "operation": operation, "phase": phase,
            "start_utc": utc(), "start_monotonic": started,
            "status_code": None, "error_code": None, "transport_error": None,
        }
        try:
            status, response, returned_id = self.request(url, body, request_id)
            row.update(status_code=status, response_request_id=returned_id)
            if isinstance(response, dict):
                error = response.get("error")
                if isinstance(error, dict) and isinstance(error.get("code"), str):
                    row["error_code"] = error["code"][:100]
                if operation == "create" and status == 201:
                    from uuid import UUID
                    row["resource_id"] = str(UUID(response["id"]))
        except (OSError, ValueError, KeyError, TypeError):
            row["transport_error"] = "request_failed"
        finished = self.clock()
        row.update(end_utc=utc(), end_monotonic=finished, duration_seconds=finished - started)
        try:
            with self.lock:
                append_json(self.output / "requests.jsonl", row)
                self.rows.append(row)
        except OSError:
            self.fail("capture_failed")
            raise
        if operation.startswith("control_") or operation.startswith("live_"):
            if row["status_code"] != 200 or row["transport_error"]:
                self.fail(f"{operation}_failed")
            if operation.startswith("control_"):
                samples = [r["duration_seconds"] for r in self.rows if r["phase"] == phase and r["operation"] == operation]
                if len(samples) >= 20 and p95(samples) >= 1:
                    self.fail(f"{operation}_latency")
        return row

    def phase(self, name, seconds, tick=lambda: None, create=True):
        self.current_phase = name
        urls = self.metadata["urls"]
        operations = [
            ("control_catalog", urls["catalog"] + "/products/" + self.metadata["product_id"], None),
            ("control_orders", urls["orders"] + "/orders/" + self.metadata["order_id"], None),
        ]
        if create:
            operations.insert(0, ("create", urls["orders"] + "/orders", {"product_id": self.metadata["product_id"], "quantity": 1}))
        business = ThreadPoolExecutor(max_workers=10, thread_name_prefix="business")
        probes = ThreadPoolExecutor(max_workers=8, thread_name_prefix="probes")
        pending = set()
        probe_pending = set()
        started = self.clock()
        append_json(self.output / "events.jsonl", {"event": "phase_start", "phase": name, "utc": utc(), "monotonic": started})
        try:
            for second in range(seconds):
                target = started + second
                while self.clock() < target and not self.abort.is_set():
                    self.sleep(min(0.1, target - self.clock()))
                if self.abort.is_set():
                    raise SafetyError(self.reason or "Load aborted.")
                if self.clock() - target >= 1:
                    self.fail("scheduled_load_omitted")
                    raise SafetyError(self.reason)
                tick()
                finished = {task for task in pending if task.done()}
                for task in finished:
                    task.result()
                pending -= finished
                if len(pending) + len(operations) > 10:
                    self.fail("scheduled_load_omitted")
                    raise SafetyError(self.reason)
                for operation, url, body in operations:
                    pending.add(business.submit(self.attempt, name, operation, url, body))
                if second % 5 == 0:
                    finished_probes = {task for task in probe_pending if task.done()}
                    for task in finished_probes:
                        task.result()
                    probe_pending -= finished_probes
                    if len(probe_pending) + 4 > 8:
                        self.fail("health_probe_omitted")
                        raise SafetyError(self.reason)
                    for service in ("catalog", "orders"):
                        for kind in ("ready", "live"):
                            operation = kind + "_" + service
                            probe_pending.add(probes.submit(self.attempt, name, operation, urls[service] + "/health/" + kind))
            deadline = started + seconds
            while self.clock() < deadline and not self.abort.is_set():
                self.sleep(min(0.1, deadline - self.clock()))
        finally:
            append_json(self.output / "events.jsonl", {"event": "phase_end", "phase": name, "utc": utc(), "monotonic": self.clock()})
            business.shutdown(wait=True, cancel_futures=False)
            probes.shutdown(wait=True, cancel_futures=False)
        for task in pending | probe_pending:
            task.result()
        if self.abort.is_set():
            raise SafetyError(self.reason or "Load aborted.")
        return [r for r in self.rows if r["phase"] == name]


def require_baseline(rows):
    for operation, status in (("create", 201), ("control_catalog", 200), ("control_orders", 200)):
        samples = [row for row in rows if row["operation"] == operation]
        if len(samples) != 60 or any(row["status_code"] != status or row["transport_error"] for row in samples):
            raise SafetyError("Baseline failed; no injection permitted.")
        if p95([row["duration_seconds"] for row in samples]) >= 1:
            raise SafetyError("Baseline latency is outside the experimental limit.")
