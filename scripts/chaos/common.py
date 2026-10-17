from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?\Z")


class SafetyError(RuntimeError):
    pass


def validate_id(value):
    if not RUN_ID.fullmatch(value):
        raise SafetyError("Run ID must contain 1–32 lowercase letters, digits or internal hyphens.")
    return value


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def append_json(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value) + "\n")


def p95(values):
    if not values:
        raise SafetyError("No latency samples available.")
    return sorted(values)[math.ceil(len(values) * 0.95) - 1]


def http_request(url, body=None, request_id=None):
    if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+/[^\s]*", url):
        raise SafetyError("Only loopback HTTP endpoints are allowed.")
    data = json.dumps(body).encode() if body is not None else None
    headers = {"X-Request-ID": request_id or str(uuid4())}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            return response.status, json.loads(response.read()), response.headers.get("X-Request-ID")
    except urllib.error.HTTPError as response:
        try:
            value = json.loads(response.read())
        except (ValueError, OSError):
            value = {}
        return response.code, value, response.headers.get("X-Request-ID")


class Docker:
    def __init__(self, env=None, command=subprocess.run):
        self.env = dict(os.environ if env is None else env)
        self.command = command
        endpoint = self.env.get("DOCKER_HOST")
        context = self.env.get("DOCKER_CONTEXT")
        if context or not endpoint:
            context = context or self.call_local(["docker", "context", "show"]).strip()
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", context):
                raise SafetyError("Invalid local Docker context name.")
            endpoint = self.call_local([
                "docker", "context", "inspect", context, "--format", "{{.Endpoints.docker.Host}}",
            ]).strip()
        if not (re.fullmatch(r"unix:///[^\s]+", endpoint or "") or re.fullmatch(r"npipe:////\./pipe/[a-zA-Z0-9_.-]+", endpoint or "")):
            raise SafetyError("A local Docker unix socket or named pipe is required; remote endpoints refused.")
        self.endpoint = endpoint
        for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            self.env.pop(key, None)

    def call_local(self, args, timeout=30, env=None):
        try:
            result = self.command(
                args, cwd=ROOT, env=self.env if env is None else env,
                capture_output=True, text=True, check=True, timeout=timeout,
            )
            return result.stdout
        except (OSError, subprocess.SubprocessError) as error:
            raise SafetyError("Docker operation failed; command output withheld to protect credentials.") from error

    def call(self, args, timeout=30, env=None):
        return self.call_local(["docker", "--host", self.endpoint, *args], timeout, env)

    def verify(self, project, run_id, required=None):
        identifiers = self.call([
            "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}",
        ]).split()
        services = set()
        for identifier in identifiers:
            raw = self.call(["inspect", "--format", "{{json .Config.Labels}}", identifier])
            labels = json.loads(raw)
            if labels.get("io.pipeline.chaos.run") != run_id or labels.get("com.docker.compose.project") != project:
                raise SafetyError("Container identity mismatch; no operation performed.")
            services.add(labels.get("com.docker.compose.service"))
        if required and not set(required).issubset(services):
            raise SafetyError("Required laboratory services are missing.")
        for kind in ("volume", "network"):
            names = self.call([kind, "ls", "-q", "--filter", f"label=com.docker.compose.project={project}"]).split()
            for name in names:
                labels = json.loads(self.call([kind, "inspect", "--format", "{{json .Labels}}", name]))
                if labels.get("io.pipeline.chaos.run") != run_id or labels.get("com.docker.compose.project") != project:
                    raise SafetyError("Network or volume identity mismatch; no operation performed.")
        return services

    def port(self, container, internal):
        bindings = json.loads(self.call([
            "inspect", "--format", "{{json .NetworkSettings.Ports}}", container,
        ]))
        rows = bindings.get(f"{internal}/tcp") or []
        if len(rows) != 1 or rows[0].get("HostIp") != "127.0.0.1":
            raise SafetyError("Expected exactly one loopback binding.")
        port = int(rows[0]["HostPort"])
        if not 1 <= port <= 65535:
            raise SafetyError("Invalid laboratory port.")
        return f"http://127.0.0.1:{port}"
