#!/usr/bin/env python3
"""Ejecuta un experimento de caos controlado y mide MTTD, SLO y error budget (ID-003, Módulo D).

Experimentos:
  exp1-latency-catalog  latencia +200 ms en catalog (service-b del flujo pedidos → catálogo)
  exp2-errors-data      10 % de errores en data-service (503 tras 500 ms, simula timeout de BD)

Precondiciones: laboratorio desplegado, carga constante en curso (scripts/load/steady.js) y al menos
la línea base recomendada para el modelo de anomalías. Solo usar en el sandbox propio.

Uso:
  python3 scripts/chaos/run_experiment.py exp2-errors-data \
      --config artifacts/aws/lab_config.json --prometheus http://IP:9090 --duration 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.aws.awscli import aws, load_lab_config, parse_aws_time, utcnow  # noqa: E402

MTTD_TARGET_SECONDS = 120
AVAILABILITY_SLO = 0.99


@dataclass(frozen=True)
class Experiment:
    key: str
    service: str
    chaos: dict
    primary_alarm: tuple[str, str]
    detection_alarms: tuple[tuple[str, str], ...]
    hypothesis: str


EXPERIMENTS = {
    "exp1-latency-catalog": Experiment(
        key="exp1-latency-catalog",
        service="catalog",
        chaos={"latency_ms": 200, "experiment": "exp1-latency-catalog"},
        primary_alarm=("latency_degradation", "catalog"),
        detection_alarms=(("latency_slo", "catalog"), ("latency_anomaly", "catalog"), ("latency_slo", "orders")),
        hypothesis="Con +200 ms en catalog, la regla de degradación de latencia alerta en ≤ 2 min; "
                   "el SLO p99 de catalog (150 ms) se viola y el de orders (400 ms) se mantiene.",
    ),
    "exp2-errors-data": Experiment(
        key="exp2-errors-data",
        service="data-service",
        chaos={"error_rate": 0.10, "error_delay_ms": 500, "experiment": "exp2-errors-data"},
        primary_alarm=("correlated_errors", "data-service"),
        detection_alarms=(("error_anomaly", "data-service"), ("latency_slo", "data-service"),
                          ("static_error_rate", "data-service")),
        hypothesis="Con 10 % de errores (503 tras 500 ms), la regla correlacionada error_rate > baseline+2σ "
                   "Y p99 > SLO alerta en ≤ 2 min con un trace_id de una solicitud fallida.",
    ),
}


def prom_query(base: str, query: str, at: float | None = None) -> list[dict]:
    params = {"query": query}
    if at is not None:
        params["time"] = f"{at:.3f}"
    url = f"{base.rstrip('/')}/api/v1/query?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as response:
        payload = json.load(response)
    return payload.get("data", {}).get("result", [])


def prom_value(base: str | None, query: str, at: float | None = None) -> float | None:
    if not base:
        return None
    try:
        result = prom_query(base, query, at)
    except OSError:
        return None
    return float(result[0]["value"][1]) if result else None


def slo_window(base: str | None, job: str, start: float, end: float, latency_slo_ms: float) -> dict:
    seconds = max(60, int(end - start))
    selector = f'exported_job="{job}",http_route!~"/health/.*"'
    total = prom_value(base, f"sum(increase(pipeline_http_server_request_duration_seconds_count{{{selector}}}[{seconds}s]))", end)
    errors = prom_value(
        base,
        f'sum(increase(pipeline_http_server_request_duration_seconds_count{{{selector},http_response_status_code=~"5.."}}[{seconds}s]))',
        end,
    ) or 0.0
    p99 = prom_value(
        base,
        f"histogram_quantile(0.99, sum by (le) (rate(pipeline_http_server_request_duration_seconds_bucket{{{selector}}}[{seconds}s])))",
        end,
    )
    window: dict = {"window_seconds": seconds, "requests": total, "errors": errors,
                    "latency_p99_ms": round(p99 * 1000, 1) if p99 is not None else None,
                    "latency_slo_ms": latency_slo_ms}
    if total:
        error_ratio = errors / total
        budget = (1 - AVAILABILITY_SLO) * total
        window.update({
            "availability": round(1 - error_ratio, 5),
            "availability_slo": AVAILABILITY_SLO,
            "availability_slo_met": error_ratio <= (1 - AVAILABILITY_SLO),
            "window_budget_consumed_pct": round(100 * errors / budget, 1) if budget else None,
            # Presupuesto mensual: 1 % de las solicitudes de 30 días al ritmo observado.
            "monthly_budget_consumed_pct": round(100 * errors / ((1 - AVAILABILITY_SLO) * total / seconds * 30 * 86400), 3),
        })
    if p99 is not None:
        window["latency_slo_met"] = p99 * 1000 <= latency_slo_ms
    return window


def alarm_states(names: list[str], region: str) -> dict[str, dict]:
    result = aws("cloudwatch", "describe-alarms", "--alarm-names", *names,
                 "--alarm-types", "CompositeAlarm", "MetricAlarm", region=region)
    states = {}
    for alarm in result.get("MetricAlarms", []) + result.get("CompositeAlarms", []):
        states[alarm["AlarmName"]] = {"state": alarm["StateValue"], "updated": alarm["StateUpdatedTimestamp"]}
    return states


def first_alarm_transition(name: str, region: str, since) -> str | None:
    history = aws("cloudwatch", "describe-alarm-history", "--alarm-name", name,
                  "--history-item-type", "StateUpdate", "--start-date", since.isoformat(),
                  "--scan-by", "TimestampAscending", region=region)
    for item in history.get("AlarmHistoryItems", []):
        data = json.loads(item.get("HistoryData", "{}"))
        if data.get("newState", {}).get("stateValue") == "ALARM":
            return item["Timestamp"]
    return None


def enriched_alert(config: dict, alarm_name: str, since, region: str) -> dict | None:
    query = (
        "fields @timestamp, alarm, state, primary_trace_id, actionable, enrichment_seconds, evidence"
        f' | filter type = "enriched_alert" and alarm = "{alarm_name}" and state = "ALARM"'
        " | sort @timestamp asc | limit 1"
    )
    started = aws("logs", "start-query", "--log-group-name", config["alerts_log_group"],
                  "--start-time", str(int(since.timestamp())), "--end-time", str(int(time.time()) + 60),
                  "--query-string", query, region=region)
    for _ in range(30):
        response = aws("logs", "get-query-results", "--query-id", started["queryId"], region=region)
        if response["status"] in {"Complete", "Failed", "Cancelled", "Timeout"}:
            rows = response.get("results", [])
            return {f["field"]: f["value"] for f in rows[0] if not f["field"].startswith("@ptr")} if rows else None
        time.sleep(2)
    return None


def put_chaos(parameter: str, value: dict, region: str) -> None:
    aws("ssm", "put-parameter", "--name", parameter, "--type", "String", "--overwrite",
        "--value", json.dumps(value), region=region, parse=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", choices=sorted(EXPERIMENTS))
    parser.add_argument("--config", required=True, help="terraform output -json lab_config")
    parser.add_argument("--prometheus", help="URL de Prometheus (http://IP:9090) para SLO/error budget")
    parser.add_argument("--duration", type=int, default=300, help="segundos con la falla activa")
    parser.add_argument("--recovery-timeout", type=int, default=600)
    parser.add_argument("--out", default="artifacts/chaos")
    args = parser.parse_args()

    config = load_lab_config(args.config)
    region = config["region"]
    exp = EXPERIMENTS[args.experiment]
    alarms = config["alarms"]
    primary = alarms[exp.primary_alarm[0]][exp.primary_alarm[1]]
    detection = [alarms[group][service] for group, service in exp.detection_alarms]
    watched = [primary, *detection]
    parameter = config["chaos_parameters"][exp.service]
    slo_ms = float(config["latency_slo_ms"][exp.service])

    started_at = utcnow()
    run_dir = Path(args.out) / f"{started_at:%Y%m%dT%H%M%SZ}-{exp.key}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{exp.key}] hipótesis: {exp.hypothesis}")

    before = alarm_states(watched, region)
    if any(state["state"] == "ALARM" for state in before.values()):
        print("Advertencia: hay alarmas en ALARM antes de inyectar; el MTTD puede no ser válido.")
    steady = slo_window(args.prometheus, exp.service, time.time() - 600, time.time(), slo_ms)

    injected_at = utcnow()
    put_chaos(parameter, exp.chaos, region)
    print(f"Falla inyectada {injected_at.isoformat()} en {parameter}: {exp.chaos}")

    detections: dict[str, str] = {}
    deadline = time.monotonic() + args.duration
    try:
        while time.monotonic() < deadline:
            states = alarm_states(watched, region)
            for name, state in states.items():
                if state["state"] == "ALARM" and name not in detections:
                    detections[name] = state["updated"]
                    delta = (parse_aws_time(state["updated"]) - injected_at).total_seconds()
                    print(f"  ALARM {name} (+{delta:.0f} s)")
            time.sleep(10)
    finally:
        reverted_at = utcnow()
        put_chaos(parameter, {"enabled": False}, region)
        print(f"Falla revertida {reverted_at.isoformat()}")

    impact = slo_window(args.prometheus, exp.service, injected_at.timestamp(), reverted_at.timestamp(), slo_ms)
    impact_orders = None
    if exp.service != "orders":
        impact_orders = slo_window(args.prometheus, "orders", injected_at.timestamp(), reverted_at.timestamp(),
                                   float(config["latency_slo_ms"]["orders"]))

    recovered_at = None
    recovery_deadline = time.monotonic() + args.recovery_timeout
    while time.monotonic() < recovery_deadline:
        if alarm_states([primary], region).get(primary, {}).get("state") != "ALARM":
            recovered_at = utcnow()
            break
        time.sleep(15)

    since = injected_at - timedelta(seconds=5)
    first = {name: first_alarm_transition(name, region, since) for name in watched}
    mttd = {
        name: round((parse_aws_time(ts) - injected_at).total_seconds(), 1) if ts else None
        for name, ts in first.items()
    }
    alert = enriched_alert(config, primary, since, region)

    report = {
        "experiment": exp.key,
        "service": exp.service,
        "hypothesis": exp.hypothesis,
        "chaos": exp.chaos,
        "injected_at": injected_at.isoformat(),
        "reverted_at": reverted_at.isoformat(),
        "recovered_at": recovered_at.isoformat() if recovered_at else None,
        "alarm_states_before": before,
        "mttd_seconds": mttd,
        "primary_alarm": primary,
        "primary_mttd_seconds": mttd.get(primary),
        "mttd_target_seconds": MTTD_TARGET_SECONDS,
        "mttd_met": mttd.get(primary) is not None and mttd[primary] <= MTTD_TARGET_SECONDS,
        "steady_state": steady,
        "impact": impact,
        "impact_orders": impact_orders,
        "enriched_alert": alert,
        "alert_actionable": bool(alert and alert.get("primary_trace_id")),
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"Evidencia en {run_dir}")
    return 0


def fmt(value, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def render_markdown(report: dict) -> str:
    impact = report["impact"] or {}
    lines = [
        f"# Experimento {report['experiment']}",
        "",
        f"- Servicio: `{report['service']}` · Falla: `{json.dumps(report['chaos'])}`",
        f"- Inyección: {report['injected_at']} · Reversión: {report['reverted_at']} · Recuperación: {fmt(report['recovered_at'])}",
        f"- Hipótesis: {report['hypothesis']}",
        "",
        "## Detección (MTTD)",
        "",
        "| Alarma | MTTD (s) |",
        "|---|---|",
    ]
    lines += [f"| `{name}` | {fmt(value)} |" for name, value in report["mttd_seconds"].items()]
    lines += [
        "",
        f"MTTD de la alarma primaria `{report['primary_alarm']}`: **{fmt(report['primary_mttd_seconds'], ' s')}** "
        f"(objetivo ≤ {report['mttd_target_seconds']} s → {'cumple' if report['mttd_met'] else 'no cumple'}).",
        "",
        "## SLO y error budget durante la falla",
        "",
        "| Indicador | Línea base (10 min) | Durante la falla |",
        "|---|---|---|",
        f"| Solicitudes | {fmt(report['steady_state'].get('requests'))} | {fmt(impact.get('requests'))} |",
        f"| Disponibilidad (SLO 99 %) | {fmt(report['steady_state'].get('availability'))} | {fmt(impact.get('availability'))} |",
        f"| Latencia p99 ms (SLO {fmt(impact.get('latency_slo_ms'))}) | {fmt(report['steady_state'].get('latency_p99_ms'))} | {fmt(impact.get('latency_p99_ms'))} |",
        f"| Presupuesto de la ventana consumido | — | {fmt(impact.get('window_budget_consumed_pct'), ' %')} |",
        f"| Presupuesto mensual consumido | — | {fmt(impact.get('monthly_budget_consumed_pct'), ' %')} |",
        "",
        f"- ¿Se degradó el SLO de disponibilidad? {'No' if impact.get('availability_slo_met', True) else 'Sí'}",
        f"- ¿Se degradó el SLO de latencia? {'No' if impact.get('latency_slo_met', True) else 'Sí'}",
    ]
    if report.get("impact_orders"):
        orders = report["impact_orders"]
        lines.append(
            f"- Impacto aguas arriba (orders): disponibilidad {fmt(orders.get('availability'))}, "
            f"p99 {fmt(orders.get('latency_p99_ms'))} ms (SLO {fmt(orders.get('latency_slo_ms'))} ms)."
        )
    alert = report.get("enriched_alert") or {}
    lines += [
        "",
        "## Accionabilidad de la alerta",
        "",
        f"- trace_id primario: `{fmt(alert.get('primary_trace_id'))}`",
        f"- Tiempo de enriquecimiento: {fmt(alert.get('enrichment_seconds'), ' s')}",
        f"- ¿Accionable? {'Sí: la alerta incluye trace_id, evidencia y runbook' if report['alert_actionable'] else 'No / pendiente de revisar'}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
