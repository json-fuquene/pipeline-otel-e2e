from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import threading
import time

try:
    from .common import ROOT, Docker, SafetyError, append_json, http_request, utc, validate_id, write_json
    from .load import Load, require_baseline
except ImportError:
    from common import ROOT, Docker, SafetyError, append_json, http_request, utc, validate_id, write_json
    from load import Load, require_baseline

SERVICES = ("catalog", "orders", "chaos-net", "postgres", "otel-collector", "catalog-migrate", "orders-migrate")


class Run:
    def __init__(self, run_id, root=ROOT, docker=None):
        self.run_id = validate_id(run_id)
        self.project = "chaos-" + run_id
        self.root = Path(root)
        self.private = self.root / ".chaos" / run_id
        self.output = self.root / "artifacts" / "chaos" / run_id
        self.docker = docker
        self.metadata = None

    def connect(self):
        self.docker = self.docker or Docker()
        if self.metadata and self.metadata["docker_endpoint"] != self.docker.endpoint:
            raise SafetyError("Docker endpoint differs from the prepared run.")

    def event(self, name, **fields):
        append_json(self.output / "events.jsonl", {"event": name, "utc": utc(), "monotonic": time.monotonic(), **fields})

    def save(self, state):
        self.metadata["state"] = state
        write_json(self.output / "metadata.json", self.metadata)
        self.event("state", state=state)

    def read(self):
        for path in (self.root / ".chaos", self.private, self.output, self.output / "metadata.json", self.private / "env"):
            if path.is_symlink():
                raise SafetyError("Symlinked run paths are not allowed.")
        self.metadata = json.loads((self.output / "metadata.json").read_text())
        if self.metadata.get("run_id") != self.run_id or self.metadata.get("project") != self.project:
            raise SafetyError("Run metadata identity mismatch.")
        if (self.private / "env").stat().st_mode & 0o077:
            raise SafetyError("Private environment file permissions must be 0600.")
        self.connect()

    def compose(self, *args, timeout=30):
        environment = {k: v for k, v in self.docker.env.items() if k not in {
            "CHAOS_RUN_ID", "POSTGRES_PASSWORD", "CATALOG_DB_PASSWORD", "ORDERS_DB_PASSWORD",
            "COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_ENV_FILES", "COMPOSE_PROFILES",
        }}
        return self.docker.call([
            "compose", "--env-file", str(self.private / "env"),
            "-f", str(self.root / "compose.chaos.yaml"), "-p", self.project, *args,
        ], timeout=timeout, env=environment)

    def identities(self, required=SERVICES):
        return self.docker.verify(self.project, self.run_id, required)

    def auxiliary(self, action, target=None):
        self.identities()
        command = ["exec", "-T", "chaos-net", "python", "/opt/chaos/supervisor.py", action]
        if target:
            command += ["--target", target]
        before = time.monotonic()
        value = json.loads(self.compose(*command, timeout=20))
        after = time.monotonic()
        if not value.get("ok"):
            raise SafetyError("Supervisor rejected operation; inspect status and verify cleanup.")
        self.event("supervisor_" + action, data=value["data"], host_before=before, host_after=after)
        value["data"]["host_confirmation_monotonic"] = after
        return value["data"]

    def new_paths(self):
        for path in (self.root / ".chaos", self.root / "artifacts", self.root / "artifacts" / "chaos"):
            if path.is_symlink():
                raise SafetyError("Symlinked run roots are not allowed.")
        self.private.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.private.parent, 0o700)
        self.private.mkdir(mode=0o700)
        self.output.mkdir(parents=True)
        for name in ("logs", "metrics"):
            (self.output / name).mkdir()
        for name in ("events.jsonl", "requests.jsonl"):
            (self.output / name).touch()
        values = {name: secrets.token_hex(32) for name in (
            "POSTGRES_PASSWORD", "CATALOG_DB_PASSWORD", "ORDERS_DB_PASSWORD",
        )}
        values["CHAOS_RUN_ID"] = self.run_id
        fd = os.open(self.private / "env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write("".join(f"{key}={value}\n" for key, value in values.items()))

    @contextmanager
    def lock(self):
        with (self.private / "lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise SafetyError("Another command is already preparing or running this run.") from error
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def prepare(self):
        if self.private.exists() or self.output.exists():
            raise SafetyError("Run ID already exists; use a new identifier.")
        self.connect()
        if self.docker.verify(self.project, self.run_id):
            raise SafetyError("Docker project already exists; refusing reuse.")
        for kind in ("volume", "network"):
            if self.docker.call([kind, "ls", "-q", "--filter", f"label=com.docker.compose.project={self.project}"]).strip():
                raise SafetyError("Docker project resources already exist; refusing reuse.")
        self.new_paths()
        self.metadata = {
            "format_version": 1, "run_id": self.run_id, "project": self.project,
            "docker_endpoint": self.docker.endpoint, "created_at": utc(),
            "experiment": "E1", "delay_ms": 6000, "ttl_seconds": 60, "lease_seconds": 10,
            "windows_seconds": {"baseline": 60, "fault": 60, "drain": 15, "recovery": 60},
            "rate_per_operation": 1, "max_business_in_flight": 10, "request_timeout_seconds": 8,
            "clock_domains": {"requests": "host", "supervisor": "container", "mapping": "IPC host_before/host_after bounds"},
            "versions": {"python": sys.version.split()[0], "docker": self.docker.call(["--version"]).strip(),
                         "compose": self.docker.call(["compose", "version", "--short"]).strip()},
        }
        self.save("preparing")
        with self.lock():
            try:
                print("Preparing local images and services; first build may take several minutes.", flush=True)
                self.compose("build", timeout=1200)
                self.compose("up", "-d", "--wait", "--wait-timeout", "180", timeout=240)
                self.identities()
                urls = {}
                metric_urls = {}
                images = {}
                for service in ("catalog", "orders"):
                    identifier = self.compose("ps", "-q", service).strip()
                    urls[service] = self.docker.port(identifier, 8000)
                    metric_urls[service] = self.docker.port(identifier, 9464)
                for service in SERVICES:
                    identifier = self.compose("ps", "-aq", service).strip()
                    images[service] = self.docker.call(["inspect", "--format", "{{.Image}}", identifier]).strip()
                self.metadata.update(urls=urls, metric_urls=metric_urls, images=images)
                self.metadata["target"] = self.auxiliary("preflight")["target"]
                status, product, _ = http_request(urls["catalog"] + "/products", {"name": "Chaos control", "price": "1.00"})
                if status != 201:
                    raise SafetyError("Product seeding failed.")
                from uuid import UUID
                self.metadata["product_id"] = str(UUID(product["id"]))
                status, order, _ = http_request(urls["orders"] + "/orders", {"product_id": self.metadata["product_id"], "quantity": 1})
                if status != 201:
                    raise SafetyError("Order seeding failed.")
                self.metadata["order_id"] = str(UUID(order["id"]))
                self.save("prepared")
            except BaseException:
                self.save("prepare_failed")
                raise

    def orders(self):
        identifiers = []
        offset = 0
        while True:
            status, page, _ = http_request(self.metadata["urls"]["orders"] + f"/orders?limit=100&offset={offset}")
            if status != 200 or not isinstance(page.get("items"), list):
                raise SafetyError("Cannot verify order persistence.")
            identifiers.extend(row["id"] for row in page["items"])
            if len(page["items"]) < 100:
                return identifiers
            offset += 100
            if offset > 10000:
                raise SafetyError("Unexpected order population; exclusive laboratory required.")

    def capture(self, services=None):
        existing = self.identities(required=None if services is not None else SERVICES)
        private_values = [line.split("=", 1)[1] for line in (self.private / "env").read_text().splitlines() if "PASSWORD=" in line]
        for service in ("catalog", "orders", "chaos-net", "otel-collector"):
            if service not in existing:
                continue
            logs = self.compose("logs", "--no-color", "--no-log-prefix", service)
            for value in private_values:
                logs = logs.replace(value, "[REDACTED]")
            (self.output / "logs" / f"{service}.log").write_text(logs)

    def run(self):
        self.read()
        with self.lock():
            if self.metadata["state"] != "prepared":
                raise SafetyError("Only a prepared, unused run may execute.")
            self.identities()
            preflight = self.auxiliary("preflight")
            if preflight["target"] != self.metadata["target"]:
                raise SafetyError("Catalog target changed since preparation.")
            load = Load(self.metadata, self.output)
            stop = threading.Event()
            heartbeat = None
            self.save("running")
            old_handlers = {}

            def interrupt(signum, frame):
                load.fail("interrupted")
                raise KeyboardInterrupt

            def renew():
                while not stop.wait(1):
                    try:
                        if load.abort.is_set():
                            self.auxiliary("rollback")
                            return
                        state = self.auxiliary("status")
                        if state["state"] == "clean" and state["reason"] == "ttl_expired":
                            return
                        if state["state"] != "active":
                            raise SafetyError("Watchdog is not active.")
                        self.auxiliary("renew")
                    except Exception:
                        load.fail("watchdog_unavailable")
                        try:
                            self.auxiliary("rollback")
                        except Exception:
                            pass
                        return

            for sig in (signal.SIGINT, signal.SIGTERM):
                old_handlers[sig] = signal.signal(sig, interrupt)
            complete = False
            try:
                before = self.orders()
                if before != [self.metadata["order_id"]]:
                    raise SafetyError("Only seeded control order may exist before the run.")
                write_json(self.output / "orders-before.json", before)
                print("Measuring baseline, fault, drain and recovery; allow about four minutes.", flush=True)
                require_baseline(load.phase("baseline", 60))
                state = self.auxiliary("arm", self.metadata["target"])
                self.metadata["activation"] = state
                write_json(self.output / "metadata.json", self.metadata)
                heartbeat = threading.Thread(target=renew, name="watchdog-renewal", daemon=True)
                heartbeat.start()
                load.phase("fault", 60)
                stop.set()
                heartbeat.join(timeout=25)
                if heartbeat.is_alive():
                    raise SafetyError("Watchdog renewal did not stop.")
                self.auxiliary("rollback")
                load.phase("drain", 15, create=False)
                load.phase("recovery", 60)
                after = self.orders()
                write_json(self.output / "orders-after.json", after)
                created = [row["resource_id"] for row in load.rows if row["operation"] == "create" and row.get("resource_id")]
                if set(after) != set(before) | set(created) or len(after) != len(before) + len(created):
                    raise SafetyError("Order persistence mismatch.")
                complete = True
            except BaseException:
                self.event("aborted", reason=load.reason or "operation_interrupted_or_failed")
                raise
            finally:
                stop.set()
                try:
                    state = self.auxiliary("rollback")
                    if state["state"] == "idle":
                        self.auxiliary("preflight")
                    if state["state"] not in {"clean", "idle"}:
                        raise SafetyError("Cleanup could not be verified.")
                    if heartbeat:
                        heartbeat.join(timeout=25)
                        if heartbeat.is_alive():
                            raise SafetyError("Renewal worker did not stop; cleanup status needs inspection.")
                    self.capture()
                    self.save("executed" if complete else "aborted")
                except Exception:
                    self.save("cleanup_unverified")
                    raise
                finally:
                    for sig, handler in old_handlers.items():
                        signal.signal(sig, handler)

    def control(self, action):
        self.read()
        services = self.identities(required=None)
        if not services:
            if action == "down" and self.metadata["state"] in {"stopped", "prepare_failed", "preparing"}:
                self.compose("down", timeout=90)
                self.save("stopped")
                return {"state": "stopped", "volume": "preserved"}
            raise SafetyError("Laboratory is not running; namespace cleanup cannot be verified.")
        if action == "status" and self.metadata["state"] in {"prepare_failed", "preparing"}:
            return {"state": self.metadata["state"], "services": sorted(services), "injection": "never_started"}
        if action == "down" and self.metadata["state"] in {"prepare_failed", "preparing"}:
            with self.lock():
                self.capture(services)
                self.compose("down", timeout=90)
                self.save("stopped")
            return {"state": "stopped", "volume": "preserved", "injection": "never_started"}
        if action == "status":
            state = self.auxiliary("status")
            if state["state"] == "idle":
                self.auxiliary("preflight")
            return state
        state = self.auxiliary("rollback")
        if state["state"] == "idle":
            self.auxiliary("preflight")
        if state["state"] not in {"idle", "clean"}:
            raise SafetyError("Cleanup must be verified before stopping the laboratory.")
        if action == "down":
            with self.lock():
                self.capture()
                self.compose("down", timeout=90)
                self.save("stopped")
        return state


def main():
    parser = argparse.ArgumentParser(description="Isolated local latency Game Day; no remote Docker endpoints")
    parser.add_argument("action", choices=("prepare", "run", "rollback", "status", "down"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        run = Run(args.run_id)
        if args.action == "prepare":
            run.prepare()
        elif args.action == "run":
            run.run()
        else:
            print(json.dumps(run.control(args.action), indent=2))
        return 0
    except KeyboardInterrupt:
        print("Interrupted; inspect rollback/status before reusing the laboratory.", file=sys.stderr)
        return 130
    except (SafetyError, OSError, ValueError, KeyError, TypeError):
        print("Operation failed; use status/rollback to verify cleanup. No credentials were printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
