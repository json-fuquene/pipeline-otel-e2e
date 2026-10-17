#!/usr/bin/env python3
"""Genera señales de seguridad controladas contra el sandbox propio (ID-003, Módulo C).

* ``--failed-logins N``: N intentos de login con contraseña inválida en Grafana → métrica
  FailedAuthAttempts y alarma de autenticación (umbral 5 en 5 min).
* ``--probe-ports``: conexiones TCP a puertos no publicados de la tarea (22, 5432, 8003, 9464…) →
  flujos REJECT en VPC Flow Logs y panel «Top orígenes rechazados».

Usar solo contra el laboratorio desplegado por esta cuenta.

  python3 scripts/security/generate_security_signals.py --grafana http://IP:3000 --failed-logins 8
  python3 scripts/security/generate_security_signals.py --host IP --probe-ports
"""
from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.request

PROBE_PORTS = (22, 23, 80, 443, 3306, 5432, 6379, 8003, 9464, 9465, 9466, 13133)


def failed_logins(base_url: str, attempts: int) -> list[int]:
    statuses = []
    for attempt in range(attempts):
        body = json.dumps({"user": "admin", "password": f"invalid-{attempt}-{time.time_ns()}"}).encode()
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/login", data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                statuses.append(response.status)
        except urllib.error.HTTPError as error:
            statuses.append(error.code)
        time.sleep(1)
    return statuses


def probe_ports(host: str, rounds: int) -> dict[int, str]:
    results: dict[int, str] = {}
    for _ in range(rounds):
        for port in PROBE_PORTS:
            try:
                with socket.create_connection((host, port), timeout=2):
                    results[port] = "abierto"
            except OSError:
                results[port] = "bloqueado"
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--grafana", help="URL de Grafana, p. ej. http://IP:3000")
    parser.add_argument("--failed-logins", type=int, default=0)
    parser.add_argument("--host", help="IP pública de una tarea del laboratorio")
    parser.add_argument("--probe-ports", action="store_true")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if args.failed_logins and args.grafana:
        print("Respuestas de login inválido:", failed_logins(args.grafana, args.failed_logins))
    if args.probe_ports and args.host:
        print("Resultado de sondeo:", probe_ports(args.host, args.rounds))
    if not ((args.failed_logins and args.grafana) or (args.probe_ports and args.host)):
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
