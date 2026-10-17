from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time

SOCKET = "/run/chaos/control.sock"
ROOT_HANDLE = "7a10:"
DELAY_HANDLE = "7a20:"


class SafetyError(RuntimeError):
    pass


def execute(args):
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=0.5)
        return result.stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise SafetyError("Local network command failed; inspect cleanup status.") from error


def target_address():
    addresses = socket.getaddrinfo("catalog", 8000, type=socket.SOCK_STREAM)
    if any(entry[0] != socket.AF_INET for entry in addresses):
        raise SafetyError("Only an unambiguous IPv4 catalog target is supported.")
    values = {entry[4][0] for entry in addresses}
    if len(values) != 1:
        raise SafetyError("Catalog target is ambiguous.")
    return str(ipaddress.IPv4Address(values.pop()))


class TargetMonitor:
    def __init__(self):
        self.value = None
        self.updated = 0
        self.lock = threading.Lock()

    def refresh(self):
        while True:
            try:
                value = target_address()
            except (SafetyError, OSError):
                value = None
            with self.lock:
                self.value = value
                self.updated = time.monotonic()
            time.sleep(1)

    def resolve(self):
        with self.lock:
            if self.value is None or time.monotonic() - self.updated > 5:
                raise SafetyError("Catalog DNS is unavailable or stale.")
            return self.value


class Kernel:
    def __init__(self, command=execute):
        self.command = command

    def route(self, address):
        routes = json.loads(self.command(["ip", "-j", "-4", "route", "get", address]))
        if len(routes) != 1 or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,15}", routes[0].get("dev", "")):
            raise SafetyError("Cannot determine a unique network interface.")
        device = routes[0]["dev"]
        if device == "lo":
            raise SafetyError("Loopback cannot be an injection target.")
        return device

    def snapshot(self, device):
        return {
            "qdisc": json.loads(self.command(["tc", "-j", "-s", "qdisc", "show", "dev", device])),
            "filters": json.loads(self.command(["tc", "-j", "-s", "filter", "show", "dev", device])),
        }

    def preflight(self, address):
        device = self.route(address)
        snapshot = self.snapshot(device)
        if snapshot["filters"] or any(
            row.get("kind") != "noqueue" or row.get("handle") != "0:"
            for row in snapshot["qdisc"]
        ):
            raise SafetyError("Foreign traffic-control rules found; injection refused.")
        return device, snapshot

    def root(self, device):
        self.command([
            "tc", "qdisc", "add", "dev", device, "root", "handle", ROOT_HANDLE,
            "prio", "bands", "3", "priomap", *(["0"] * 16),
        ])

    def delay(self, device, address):
        self.command([
            "tc", "qdisc", "add", "dev", device, "parent", "7a10:3", "handle", DELAY_HANDLE,
            "netem", "delay", "6000ms",
        ])
        self.command([
            "tc", "filter", "add", "dev", device, "parent", ROOT_HANDLE, "protocol", "ip",
            "prio", "1", "u32", "match", "ip", "protocol", "6", "0xff",
            "match", "ip", "ihl", "5", "0xf", "match", "ip", "nofrag",
            "match", "ip", "dst", address + "/32",
            "match", "ip", "dport", "8000", "0xffff", "flowid", "7a10:3",
        ])

    def remove(self, device):
        snapshot = self.snapshot(device)
        roots = [row for row in snapshot["qdisc"] if row.get("root")]
        if any(row.get("handle") == ROOT_HANDLE and row.get("kind") == "prio" for row in roots):
            self.command(["tc", "qdisc", "del", "dev", device, "root", "handle", ROOT_HANDLE])
        final = self.snapshot(device)
        if any(row.get("handle") in {ROOT_HANDLE, DELAY_HANDLE} for row in final["qdisc"]):
            raise SafetyError("Owned rules remain after cleanup.")
        return final


class Supervisor:
    def __init__(self, kernel=None, clock=time.monotonic, resolve=target_address, emit=None):
        self.kernel = kernel or Kernel()
        self.clock = clock
        self.resolve = resolve
        self.emit = emit or (lambda event: print(json.dumps(event), flush=True))
        self.state = "idle"
        self.device = None
        self.address = None
        self.deadline = None
        self.lease = None
        self.reason = None
        self.removed_at = None
        self.last_snapshot = None
        self.used = False

    def event(self, name, **fields):
        self.emit({"event": name, "monotonic": self.clock(), "utc": time.time(), **fields})

    def check(self):
        if self.state != "active":
            return
        if self.clock() >= self.deadline:
            self.rollback("ttl_expired")
        elif self.clock() >= self.lease:
            self.rollback("lease_expired")
        else:
            try:
                if self.resolve() != self.address or self.kernel.route(self.address) != self.device:
                    self.rollback("target_changed")
            except (SafetyError, OSError):
                self.rollback("target_unavailable")

    def arm(self, address):
        if self.used or self.state != "idle":
            raise SafetyError("Only one injection is permitted per prepared run.")
        if str(ipaddress.IPv4Address(address)) != self.resolve():
            raise SafetyError("Catalog destination changed before injection.")
        self.device, self.last_snapshot = self.kernel.preflight(address)
        self.address = address
        self.deadline = self.clock() + 60
        self.lease = self.clock() + 10
        self.state = "installing"
        self.used = True
        self.event("watchdog_armed", deadline=self.deadline, target=address, before=self.last_snapshot)
        try:
            self.kernel.root(self.device)
            self.kernel.delay(self.device, address)
            self.last_snapshot = self.kernel.snapshot(self.device)
            self.state = "active"
            self.check()
            if self.state != "active":
                raise SafetyError("Injection expired before activation.")
            self.event("activated", target=address, snapshot=self.last_snapshot)
        except Exception:
            self.rollback("installation_failed")
            raise
        return self.status()

    def renew(self):
        self.check()
        if self.state != "active":
            raise SafetyError("Injection is not active; lease cannot be renewed.")
        self.lease = self.clock() + 10
        return self.status()

    def rollback(self, reason="manual"):
        if self.state == "idle":
            return self.status()
        if self.state == "clean":
            return self.status()
        self.reason = reason
        self.state = "cleaning"
        try:
            self.last_snapshot = self.kernel.remove(self.device)
        except Exception:
            self.state = "cleanup_failed"
            self.event("cleanup_failed", reason=reason)
            raise
        self.state = "clean"
        self.removed_at = self.clock()
        self.event("removed", reason=reason, snapshot=self.last_snapshot)
        return self.status()

    def status(self):
        snapshot = self.kernel.snapshot(self.device) if self.device else None
        if snapshot and self.state == "active":
            handles = {row.get("handle") for row in snapshot["qdisc"]}
            if not {ROOT_HANDLE, DELAY_HANDLE}.issubset(handles) or not snapshot["filters"]:
                self.rollback("rules_missing")
                raise SafetyError("Active injection rules are missing.")
        if snapshot and self.state == "clean" and any(
            row.get("handle") in {ROOT_HANDLE, DELAY_HANDLE} for row in snapshot["qdisc"]
        ):
            raise SafetyError("Cleanup status disagrees with kernel rules.")
        return {
            "state": self.state, "target": self.address, "device": self.device,
            "deadline": self.deadline, "lease": self.lease, "reason": self.reason,
            "removed_monotonic": self.removed_at,
            "monotonic": self.clock(), "snapshot": snapshot,
        }

    def dispatch(self, request):
        self.check()
        action = request.get("action")
        if action == "arm":
            return self.arm(request.get("target"))
        if action == "renew":
            return self.renew()
        if action == "rollback":
            return self.rollback()
        if action == "preflight":
            address = self.resolve()
            device, snapshot = self.kernel.preflight(address)
            return {"target": address, "device": device, "snapshot": snapshot}
        if action == "status":
            return self.status()
        raise SafetyError("Unknown supervisor action.")


def serve():
    Path(SOCKET).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    monitor = TargetMonitor()
    threading.Thread(target=monitor.refresh, daemon=True, name="catalog-dns").start()
    supervisor = Supervisor(resolve=monitor.resolve)
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET)
        os.chmod(SOCKET, 0o600)
        server.listen(4)
        server.settimeout(0.2)
        try:
            while not stopping:
                try:
                    supervisor.check()
                    connection, _ = server.accept()
                except socket.timeout:
                    continue
                except (SafetyError, OSError):
                    time.sleep(0.2)
                    continue
                with connection:
                    connection.settimeout(1)
                    try:
                        request = json.loads(connection.makefile("rb").readline(4096))
                        result = {"ok": True, "data": supervisor.dispatch(request)}
                    except Exception:
                        result = {"ok": False, "error": "Supervisor rejected command; inspect safe status/logs."}
                    try:
                        connection.sendall(json.dumps(result).encode() + b"\n")
                    except OSError:
                        pass
        finally:
            try:
                supervisor.rollback("shutdown")
            finally:
                Path(SOCKET).unlink(missing_ok=True)


def client(action, target=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(15)
        connection.connect(SOCKET)
        connection.sendall(json.dumps({"action": action, "target": target}).encode() + b"\n")
        result = json.loads(connection.makefile("rb").readline(262144))
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


def main():
    parser = argparse.ArgumentParser(description="Local namespace netem watchdog")
    parser.add_argument("action", choices=("serve", "preflight", "arm", "renew", "rollback", "status"))
    parser.add_argument("--target")
    args = parser.parse_args()
    try:
        if args.action == "serve":
            serve()
            return 0
        return client(args.action, args.target)
    except (OSError, ValueError, SafetyError):
        print("Supervisor operation failed; cleanup must be verified.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
