from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "compose.yaml"
K6_SCRIPT = ROOT / "scripts/benchmark/overhead.js"
SERVICES = ("catalog", "orders")
VARIANTS = ("otel", "baseline")


def command(args: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


def docker_compose(project: str, *args: str, env: dict[str, str]) -> str:
    return command(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", project, *args],
        env=env,
    )


def host_memory_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def parse_bytes(value: str) -> int:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)?\s*", value)
    if match is None:
        raise ValueError(f"Formato de memoria de Docker no reconocido: {value}")
    amount = float(match.group(1))
    unit = (match.group(2) or "B").lower()
    scale = {
        "b": 1,
        "kb": 1000,
        "kib": 1024,
        "mb": 1000**2,
        "mib": 1024**2,
        "gb": 1000**3,
        "gib": 1024**3,
        "tb": 1000**4,
        "tib": 1024**4,
    }.get(unit)
    if scale is None:
        raise ValueError(f"Unidad de memoria de Docker no reconocida: {unit}")
    return int(amount * scale)


def request_json(url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status not in {200, 201}:
                raise RuntimeError(f"HTTP {response.status} en {url}")
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code} en {url}") from error


def wait_ready(base_urls: dict[str, str], timeout_seconds: int = 180) -> None:
    deadline = time.monotonic() + timeout_seconds
    pending = set(SERVICES)
    while pending and time.monotonic() < deadline:
        for service in tuple(pending):
            try:
                request_json(f"{base_urls[service]}/health/ready")
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
                continue
            pending.remove(service)
        if pending:
            time.sleep(2)
    if pending:
        raise RuntimeError(f"Servicios sin readiness: {', '.join(sorted(pending))}")


def docker_stats(container: str) -> tuple[float, int, int]:
    output = command(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", container]
    )
    record = json.loads(output.splitlines()[0])
    cpu = float(record["CPUPerc"].rstrip("%"))
    memory_used, memory_limit = record["MemUsage"].split("/", 1)
    return cpu, parse_bytes(memory_used), parse_bytes(memory_limit)


def api_seed(base_urls: dict[str, str], run_id: str) -> tuple[str, str]:
    product = request_json(
        f"{base_urls['catalog']}/products",
        {"name": f"overhead-{run_id}", "price": "1.00"},
    )
    order = request_json(
        f"{base_urls['orders']}/orders",
        {"product_id": product["id"], "quantity": 1},
    )
    request_json(f"{base_urls['catalog']}/products/{product['id']}")
    request_json(f"{base_urls['orders']}/orders/{order['id']}")
    return product["id"], order["id"]


def summary_metric(summary: dict[str, Any], name: str, field: str) -> float | int | None:
    metric = summary.get("metrics", {}).get(name, {})
    values = metric.get("values", metric)
    return values.get(field)


def check_totals(summary: dict[str, Any]) -> tuple[int, int]:
    passes = 0
    fails = 0

    def collect(group: dict[str, Any]) -> None:
        nonlocal passes, fails
        for check in group.get("checks", {}).values():
            passes += check.get("passes", 0)
            fails += check.get("fails", 0)
        for child in group.get("groups", {}).values():
            collect(child)

    collect(summary.get("root_group", {}))
    return passes, fails


def inspect_limits(project: str, env: dict[str, str]) -> dict[str, dict[str, int]]:
    limits = {}
    for service in SERVICES:
        container_id = docker_compose(project, "ps", "-q", service, env=env)
        if not container_id:
            raise RuntimeError(f"No hay contenedor activo para {service}")
        raw = command(
            [
                "docker",
                "inspect",
                "--format",
                "{{.HostConfig.NanoCpus}}|{{.HostConfig.Memory}}",
                container_id,
            ]
        )
        nano_cpus, memory = raw.split("|", 1)
        limits[service] = {
            "nano_cpus": int(nano_cpus),
            "memory_bytes": int(memory),
        }
    return limits


def capture_round(
    *,
    project: str,
    variant: str,
    round_number: int,
    env: dict[str, str],
    args: argparse.Namespace,
    output_dir: Path,
    base_urls: dict[str, str],
    run_id: str,
) -> dict[str, Any]:
    variant_dir = output_dir / f"{variant}-r{round_number}"
    variant_dir.mkdir(parents=True, exist_ok=True)
    variant_env = {**env, "OTEL_ENABLED": "true" if variant == "otel" else "false"}
    wait_ready(base_urls)
    product_id, order_id = api_seed(base_urls, f"{run_id}-{variant}-{round_number}")
    (variant_dir / "seed.json").write_text(
        json.dumps({"product_id": product_id, "order_id": order_id}, indent=2) + "\n"
    )
    container_ids = {
        service: docker_compose(project, "ps", "-q", service, env=variant_env)
        for service in SERVICES
    }
    if any(not container_ids[service] for service in SERVICES):
        raise RuntimeError("No se encontraron los dos contenedores de APIs")

    stats_path = variant_dir / "docker-stats.csv"
    with stats_path.open("w", newline="") as stats_file:
        writer = csv.writer(stats_file)
        writer.writerow(
            [
                "timestamp_utc",
                "phase",
                "variant",
                "round",
                "service",
                "cpu_percent",
                "memory_used_bytes",
                "memory_limit_bytes",
            ]
        )
        k6_summary = variant_dir / "k6-summary.json"
        k6_log = variant_dir / "k6.log"
        command_args = [
            "k6",
            "run",
            "--summary-export",
            str(k6_summary),
            "-e",
            f"BASE_URL_CATALOG={base_urls['catalog']}",
            "-e",
            f"BASE_URL_ORDERS={base_urls['orders']}",
            "-e",
            f"PRODUCT_ID={product_id}",
            "-e",
            f"ORDER_ID={order_id}",
            "-e",
            f"RATE={args.rate}",
            "-e",
            f"WARMUP_SECONDS={args.warmup_seconds}",
            "-e",
            f"DURATION_SECONDS={args.duration_seconds}",
            str(K6_SCRIPT),
        ]
        with k6_log.open("w") as k6_output:
            process = subprocess.Popen(
                command_args,
                cwd=ROOT,
                env=variant_env,
                stdout=k6_output,
                stderr=subprocess.STDOUT,
                text=True,
            )
            measure_start = time.monotonic() + args.warmup_seconds
            next_sample = time.monotonic()
            try:
                while process.poll() is None:
                    now = time.monotonic()
                    if now >= next_sample:
                        timestamp = datetime.now(timezone.utc).isoformat()
                        phase = "measure" if now >= measure_start else "warmup"
                        for service, container_id in container_ids.items():
                            cpu, memory_used, memory_limit = docker_stats(container_id)
                            writer.writerow(
                                [
                                    timestamp,
                                    phase,
                                    variant,
                                    round_number,
                                    service,
                                    cpu,
                                    memory_used,
                                    memory_limit,
                                ]
                            )
                        stats_file.flush()
                        next_sample = now + 1
                    time.sleep(0.1)
                k6_exit_code = process.wait()
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise

    summary = json.loads(k6_summary.read_text())
    check_passes, check_failures = check_totals(summary)
    dropped = summary_metric(summary, "dropped_iterations", "count") or 0
    failed_rate = summary_metric(summary, "http_req_failed", "value")
    failed_rate = failed_rate if failed_rate is not None else 1
    catalog_p99 = summary_metric(summary, "catalog_duration", "p(99)")
    orders_p99 = summary_metric(summary, "orders_duration", "p(99)")
    http_requests = summary_metric(summary, "http_reqs", "count") or 0
    rounds = {
        "variant": variant,
        "round": round_number,
        "k6_exit_code": k6_exit_code,
        "catalog_p99_ms": catalog_p99,
        "orders_p99_ms": orders_p99,
        "catalog_cpu_avg_percent": None,
        "orders_cpu_avg_percent": None,
        "catalog_memory_avg_bytes": None,
        "orders_memory_avg_bytes": None,
        "dropped_iterations": dropped,
        "http_req_failed_rate": failed_rate,
        "check_passes": check_passes,
        "check_failures": check_failures,
        "http_requests": http_requests,
    }
    measured_rows: dict[str, list[dict[str, str]]] = {service: [] for service in SERVICES}
    with stats_path.open(newline="") as stats_file:
        for row in csv.DictReader(stats_file):
            if row["phase"] == "measure":
                measured_rows[row["service"]].append(row)
    for service in SERVICES:
        samples = measured_rows[service]
        if not samples:
            raise RuntimeError(f"No hubo muestras de recursos para {service}")
        rounds[f"{service}_cpu_avg_percent"] = statistics.mean(
            float(row["cpu_percent"]) for row in samples
        )
        rounds[f"{service}_memory_avg_bytes"] = statistics.mean(
            int(row["memory_used_bytes"]) for row in samples
        )
    rounds["valid"] = bool(
        k6_exit_code == 0
        and catalog_p99 is not None
        and orders_p99 is not None
        and http_requests > 0
        and check_passes > 0
        and dropped == 0
        and failed_rate == 0
        and check_failures == 0
    )
    rounds["invalid_reason"] = "" if rounds["valid"] else "Faltan métricas/respuestas o hubo checks fallidos, errores HTTP, dropped iterations o error de k6."
    return rounds


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def relative_delta(base: float | None, measured: float | None) -> float | None:
    if base is None or measured is None or base == 0:
        return None
    return (measured - base) * 100 / base


def format_value(value: float | None, suffix: str = "") -> str:
    return "N/D" if value is None else f"{value:.3f}{suffix}"


def write_reports(
    output_dir: Path,
    rounds: list[dict[str, Any]],
    environment: dict[str, Any],
) -> None:
    (output_dir / "00-entorno.json").write_text(
        json.dumps(environment, indent=2, ensure_ascii=False) + "\n"
    )
    fields = [
        "variant",
        "round",
        "catalog_p99_ms",
        "orders_p99_ms",
        "catalog_cpu_avg_percent",
        "orders_cpu_avg_percent",
        "catalog_memory_avg_bytes",
        "orders_memory_avg_bytes",
        "http_requests",
        "http_req_failed_rate",
        "check_passes",
        "check_failures",
        "dropped_iterations",
        "valid",
        "invalid_reason",
    ]
    with (output_dir / "01-rondas.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rounds)

    lines = [
        "# Comparación de overhead OpenTelemetry",
        "",
        "Las cifras se calculan como la mediana entre rondas válidas. CPU/memoria son promedios de muestras `docker stats` durante la medición; memoria se refiere al uso reportado por Docker CLI en este host.",
        "",
        "| API | Métrica | Base | OTel | Diferencia | Diferencia relativa |",
        "|---|---|---:|---:|---:|---:|",
    ]
    valid = [row for row in rounds if row.get("valid")]
    for service in SERVICES:
        for metric, suffix in (("p99_ms", " ms"), ("cpu_avg_percent", " p.p."), ("memory_avg_bytes", " MiB")):
            key = f"{service}_{metric}"
            base_values = [float(row[key]) for row in valid if row["variant"] == "baseline" and row.get(key) is not None]
            otel_values = [float(row[key]) for row in valid if row["variant"] == "otel" and row.get(key) is not None]
            base = median(base_values)
            otel = median(otel_values)
            if metric == "memory_avg_bytes":
                base = base / (1024**2) if base is not None else None
                otel = otel / (1024**2) if otel is not None else None
            difference = otel - base if base is not None and otel is not None else None
            percent = relative_delta(base, otel)
            label = {
                "p99_ms": "HTTP p99",
                "cpu_avg_percent": "CPU promedio",
                "memory_avg_bytes": "Memoria promedio",
            }[metric]
            lines.append(
                f"| {service} | {label} | {format_value(base, ' ms' if metric == 'p99_ms' else ('%' if metric == 'cpu_avg_percent' else ' MiB'))} | {format_value(otel, ' ms' if metric == 'p99_ms' else ('%' if metric == 'cpu_avg_percent' else ' MiB'))} | {format_value(difference, suffix)} | {format_value(percent, '%')} |"
            )
    lines.extend(
        [
            "",
            f"Rondas válidas: {len(valid)} de {len(rounds)}. Los resultados `N/D` significan que no hubo suficientes rondas válidas o que el denominador fue cero.",
            "",
        ]
    )
    (output_dir / "02-comparacion.md").write_text("\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compara p99, CPU y memoria con y sin OpenTelemetry.")
    parser.add_argument("--rounds", type=int, default=1, help="Rondas por variante (predeterminado: 1, modo indicativo).")
    parser.add_argument("--rate", type=int, default=2, help="Iteraciones por segundo del escenario k6.")
    parser.add_argument("--warmup-seconds", type=int, default=3)
    parser.add_argument("--duration-seconds", type=int, default=15)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.rounds < 1 or args.rate < 1 or args.warmup_seconds < 1 or args.duration_seconds < 1:
        parser.error("Usa al menos 1 ronda y valores positivos para tasa, calentamiento y duración.")
    return args


def main() -> int:
    args = parse_args()
    for executable in ("docker", "k6"):
        if shutil.which(executable) is None:
            raise RuntimeError(f"No se encontró el ejecutable requerido: {executable}")
    if not Path(ROOT / ".env").is_file():
        raise RuntimeError("Falta .env; inicializa las credenciales locales con scripts/init-local-env.py.")
    for port in (8001, 8002):
        with socket.socket() as listener:
            if listener.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"El puerto local {port} ya está ocupado; libera el Compose actual antes del benchmark.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = uuid.uuid4().hex[:8]
    revision = command(["git", "rev-parse", "--short", "HEAD"])
    output_dir = args.output_dir or ROOT / "artifacts/overhead" / f"{timestamp}-{revision}-{run_id}"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "k6-version.txt").write_text(command(["k6", "version"]) + "\n")
    (output_dir / "docker-compose-version.txt").write_text(
        command(["docker", "compose", "version"]) + "\n"
    )

    base_urls = {"catalog": "http://127.0.0.1:8001", "orders": "http://127.0.0.1:8002"}
    environment = {
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": revision,
        "git_worktree_dirty": bool(command(["git", "status", "--short"])),
        "host_platform": platform.platform(),
        "host_cpu_count": os.cpu_count(),
        "host_memory_bytes": host_memory_bytes(),
        "python_version": sys.version,
        "docker_compose_version": command(["docker", "compose", "version"]),
        "docker_daemon_platform": command(["docker", "info", "--format", "{{.OSType}}/{{.Architecture}}"]),
        "k6_version": command(["k6", "version"]),
        "load": {
            "rate_iterations_per_second": args.rate,
            "preallocated_vus": max(args.rate, 10),
            "max_vus": max(args.rate * 4, 40),
            "warmup_seconds": args.warmup_seconds,
            "duration_seconds": args.duration_seconds,
            "rounds_per_variant": args.rounds,
        },
        "measured_containers": list(SERVICES),
        "resource_note": "CPU y memoria corresponden a cada contenedor API y a la semántica reportada por docker stats en esta plataforma.",
    }
    rounds: list[dict[str, Any]] = []
    variants = [
        variant
        for round_index in range(args.rounds)
        for variant in (VARIANTS if round_index % 2 == 0 else tuple(reversed(VARIANTS)))
    ]
    variant_round_numbers = {variant: 0 for variant in VARIANTS}
    project = f"otelbench-{run_id}"
    try:
        build_env = {**os.environ, "OTEL_ENABLED": "true"}
        (output_dir / "docker-build.log").write_text(
            command(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", project, "build", "catalog", "orders"],
                env=build_env,
            )
            + "\n"
        )
        for index, variant in enumerate(variants, start=1):
            variant_round_numbers[variant] += 1
            round_number = variant_round_numbers[variant]
            env = {**os.environ, "OTEL_ENABLED": "true" if variant == "otel" else "false"}
            (output_dir / f"{variant}-r{round_number}").mkdir(parents=True)
            compose_args = (
                ("up", "--detach")
                if index == 1
                else ("up", "--detach", "--force-recreate", "--no-deps", "catalog", "orders")
            )
            (output_dir / f"{variant}-r{round_number}" / "compose-up.log").write_text(
                docker_compose(project, *compose_args, env=env) + "\n"
            )
            limits = inspect_limits(project, env)
            environment.setdefault("container_limits", {})[
                f"{variant}-r{round_number}"
            ] = limits
            row = capture_round(
                project=project,
                variant=variant,
                round_number=round_number,
                env=env,
                args=args,
                output_dir=output_dir,
                base_urls=base_urls,
                run_id=run_id,
            )
            rounds.append(row)
            print(f"Ronda {index}/{len(variants)}: {variant} r{round_number} — {row['valid']}")
    finally:
        try:
            docker_compose(
                project,
                "down",
                "--volumes",
                "--remove-orphans",
                env={**os.environ, "OTEL_ENABLED": "true"},
            )
        finally:
            write_reports(output_dir, rounds, environment)
    print(f"Evidencias: {output_dir}")
    return 0 if len([row for row in rounds if row.get("valid")]) == len(variants) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
