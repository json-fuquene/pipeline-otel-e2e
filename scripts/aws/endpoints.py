#!/usr/bin/env python3
"""Resuelve las IP públicas de las tareas ECS del laboratorio observable y escribe endpoints.json.

Uso:
    terraform -chdir=infra/aws-observable output -json lab_config > artifacts/aws/lab_config.json
    python3 scripts/aws/endpoints.py artifacts/aws/lab_config.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.aws.awscli import aws, load_lab_config  # noqa: E402

PORTS = {
    "catalog": {"catalog": 8001},
    "orders": {"orders": 8002},
    "observability": {"grafana": 3000, "jaeger": 16686, "prometheus": 9090},
}


def public_ip(cluster: str, service: str, region: str) -> str | None:
    tasks = aws("ecs", "list-tasks", "--cluster", cluster, "--service-name", service,
                "--desired-status", "RUNNING", region=region)["taskArns"]
    if not tasks:
        return None
    described = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", tasks[0], region=region)
    details = described["tasks"][0]["attachments"][0]["details"]
    eni = next(item["value"] for item in details if item["name"] == "networkInterfaceId")
    interfaces = aws("ec2", "describe-network-interfaces", "--network-interface-ids", eni, region=region)
    return interfaces["NetworkInterfaces"][0].get("Association", {}).get("PublicIp")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    config = load_lab_config(sys.argv[1])
    endpoints: dict[str, str] = {}
    for key, ports in PORTS.items():
        ip = public_ip(config["cluster"], config["services"][key], config["region"])
        for name, port in ports.items():
            endpoints[name] = f"http://{ip}:{port}" if ip else "sin tarea en ejecución"
    target = Path(sys.argv[1]).with_name("endpoints.json")
    target.write_text(json.dumps(endpoints, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(endpoints, indent=2))
    print(f"Guardado en {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
