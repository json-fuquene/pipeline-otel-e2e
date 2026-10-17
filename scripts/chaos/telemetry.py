from __future__ import annotations

import hashlib
import re
import threading
import time
import urllib.request

try:
    from .common import SafetyError, append_json, utc
except ImportError:
    from common import SafetyError, append_json, utc

NUMERIC = r"(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?Inf|NaN)"
METRIC_SAMPLE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?:[^"{}]|"(?:\\.|[^"\\])*")*\})?'
                           + r"[ \t]+" + NUMERIC + r"(?:[ \t]+" + NUMERIC + r")?(?:[ \t]+#.*)?[ \t]*$")


def metric_names(text):
    names = set()
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        sample = METRIC_SAMPLE.fullmatch(line)
        if not sample:
            return []
        names.add(sample[1])
    return sorted(names)


def read_metrics(url):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+/metrics", url):
        raise SafetyError("Only loopback metrics URLs are allowed.")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(url, timeout=2) as response:
        body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024 or response.status != 200:
            raise SafetyError("Metrics response is too large or unsuccessful.")
        return body.decode("utf-8")


class Telemetry:
    def __init__(self, metadata, output, phase, fail, sanitize=lambda value: value,
                 request=read_metrics, clock=time.monotonic):
        self.metadata = metadata
        self.output = output
        self.phase = phase
        self.fail = fail
        self.sanitize = sanitize
        self.request = request
        self.clock = clock
        self.stop_event = threading.Event()
        self.threads = []
        self.lock = threading.Lock()
        self.names = {"catalog": set(), "orders": set()}

    def sample(self, service, sequence):
        row = {"service": service, "sequence": sequence, "phase": self.phase(),
               "utc": utc(), "monotonic": self.clock(), "status_code": None, "error": None}
        try:
            text = self.sanitize(self.request(self.metadata["metric_urls"][service] + "/metrics"))
            names = metric_names(text)
            if not names:
                raise SafetyError("Metrics payload contains no discoverable sample names.")
            relative = f"metrics/{service}-{sequence:05d}.prom"
            (self.output / relative).write_text(text, encoding="utf-8")
            row.update(file=relative, status_code=200, sha256=hashlib.sha256(text.encode()).hexdigest())
            with self.lock:
                self.names[service].update(names)
        except (OSError, ValueError, SafetyError):
            row["error"] = "metrics_capture_failed"
            self.fail("metrics_capture_failed")
        row["end_monotonic"] = self.clock()
        try:
            with self.lock:
                append_json(self.output / "metrics/index.jsonl", row)
        except OSError:
            self.fail("metrics_index_failed")
            raise
        return row

    def worker(self, service):
        sequence = 0
        deadline = self.clock()
        while not self.stop_event.is_set():
            try:
                self.sample(service, sequence)
            except Exception:
                self.fail("metrics_capture_failed")
                return
            sequence += 1
            deadline += 5
            if self.clock() > deadline:
                self.fail("metrics_schedule_omitted")
                return
            self.stop_event.wait(max(0, deadline - self.clock()))

    def start(self):
        for service in ("catalog", "orders"):
            thread = threading.Thread(target=self.worker, args=(service,), name="metrics-" + service, daemon=True)
            self.threads.append(thread)
            thread.start()

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)
            if thread.is_alive():
                self.fail("metrics_worker_did_not_stop")
                raise SafetyError("Metrics worker did not stop.")
        return {service: sorted(names) for service, names in self.names.items()}
