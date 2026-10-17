#!/usr/bin/env python3
"""Compara el ruido de alertas: umbrales estáticos vs. regla AIOps correlacionada (ID-003, Módulo B).

Dos evidencias cuantitativas sobre la misma ventana:

1. Historial real de CloudWatch: transiciones a ALARM de las alarmas estáticas
   (error_rate > 1 %, p99 > SLO) frente a las compuestas AIOps (correlated-errors, latency-degradation).
2. Reproducción offline sobre las métricas por minuto (GetMetricData): cuenta episodios de alerta
   de la regla estática y de la regla correlacionada con baseline móvil (media + 2σ, 60 min).

Uso:
  python3 scripts/aiops/noise_report.py --config artifacts/aws/lab_config.json --hours 6
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.aws.awscli import aws, load_lab_config, utcnow  # noqa: E402

NAMESPACE = "PipelineOtel/Services"
STATIC_GROUPS = ("static_error_rate", "latency_slo")
AIOPS_GROUPS = ("correlated_errors", "latency_degradation")


def alarm_transitions(name: str, start, end, region: str) -> int:
    count, token = 0, None
    while True:
        args = ["cloudwatch", "describe-alarm-history", "--alarm-name", name, "--history-item-type",
                "StateUpdate", "--start-date", start.isoformat(), "--end-date", end.isoformat()]
        if token:
            args += ["--next-token", token]
        page = aws(*args, region=region)
        for item in page.get("AlarmHistoryItems", []):
            data = json.loads(item.get("HistoryData", "{}"))
            if data.get("newState", {}).get("stateValue") == "ALARM":
                count += 1
        token = page.get("NextToken")
        if not token:
            return count


def metric_series(service: str, start, end, region: str) -> dict[str, list[float | None]]:
    queries = [
        {"Id": "req", "MetricStat": {"Metric": {"Namespace": NAMESPACE, "MetricName": "RequestCount",
         "Dimensions": [{"Name": "service", "Value": service}]}, "Period": 60, "Stat": "Sum"}, "ReturnData": True},
        {"Id": "err", "MetricStat": {"Metric": {"Namespace": NAMESPACE, "MetricName": "ServerErrorCount",
         "Dimensions": [{"Name": "service", "Value": service}]}, "Period": 60, "Stat": "Sum"}, "ReturnData": True},
        {"Id": "p99", "MetricStat": {"Metric": {"Namespace": NAMESPACE, "MetricName": "RequestLatency",
         "Dimensions": [{"Name": "service", "Value": service}]}, "Period": 60, "Stat": "p99"}, "ReturnData": True},
    ]
    result = aws("cloudwatch", "get-metric-data", "--metric-data-queries", json.dumps(queries),
                 "--start-time", start.isoformat(), "--end-time", end.isoformat(),
                 "--scan-by", "TimestampAscending", region=region)
    by_id = {item["Id"]: dict(zip(item["Timestamps"], item["Values"])) for item in result["MetricDataResults"]}
    stamps = sorted(set(by_id.get("req", {})) | set(by_id.get("p99", {})))
    req = [by_id.get("req", {}).get(ts) for ts in stamps]
    err = [by_id.get("err", {}).get(ts, 0.0) for ts in stamps]
    p99 = [by_id.get("p99", {}).get(ts) for ts in stamps]
    rate = [100 * e / r if r else None for e, r in zip(err, req)]
    return {"timestamps": stamps, "error_rate": rate, "p99": p99}


def episodes(flags: list[bool]) -> int:
    """Cuenta episodios (rachas de minutos en alerta); cada episodio equivale a una notificación."""
    count, previous = 0, False
    for flag in flags:
        if flag and not previous:
            count += 1
        previous = flag
    return count


def replay(series: dict, slo_ms: float, static_pct: float, window: int = 60, sigma: float = 2.0) -> dict:
    rate, p99 = series["error_rate"], series["p99"]
    static_flags, aiops_flags = [], []
    for index, (value, latency) in enumerate(zip(rate, p99)):
        history = [x for x in rate[max(0, index - window):index] if x is not None]
        baseline = statistics.fmean(history) if len(history) >= 10 else None
        spread = statistics.pstdev(history) if len(history) >= 10 else None
        latency_breach = latency is not None and latency > slo_ms
        static_flags.append((value is not None and value > static_pct) or latency_breach)
        anomalous = value is not None and baseline is not None and value > baseline + sigma * spread
        aiops_flags.append(bool(anomalous and latency_breach))
    return {
        "minutes": len(rate),
        "static_alert_minutes": sum(static_flags),
        "static_notifications": episodes(static_flags),
        "aiops_alert_minutes": sum(aiops_flags),
        "aiops_notifications": episodes(aiops_flags),
    }


def reduction(static: int, aiops: int) -> str:
    return "—" if static == 0 else f"{100 * (static - aiops) / static:.0f} %"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--hours", type=float, default=6)
    parser.add_argument("--out", default="artifacts/aiops")
    args = parser.parse_args()

    config = load_lab_config(args.config)
    region = config["region"]
    end = utcnow()
    start = end - timedelta(hours=args.hours)
    static_pct = 1.0

    rows, replay_rows = [], []
    for service, slo_ms in config["latency_slo_ms"].items():
        static = sum(alarm_transitions(config["alarms"][g][service], start, end, region) for g in STATIC_GROUPS)
        aiops = sum(alarm_transitions(config["alarms"][g][service], start, end, region) for g in AIOPS_GROUPS)
        rows.append({"service": service, "static_notifications": static, "aiops_notifications": aiops,
                     "reduction": reduction(static, aiops)})
        simulated = replay(metric_series(service, start, end, region), float(slo_ms), static_pct)
        simulated.update({"service": service, "reduction": reduction(simulated["static_notifications"],
                                                                     simulated["aiops_notifications"])})
        replay_rows.append(simulated)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = f"{end:%Y%m%dT%H%M%SZ}"
    report = {"start": start.isoformat(), "end": end.isoformat(), "cloudwatch_history": rows, "replay": replay_rows}
    (out / f"noise-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        f"# Ruido de alertas: estático vs. AIOps ({start:%Y-%m-%d %H:%M} – {end:%H:%M} UTC)",
        "",
        "## Historial real de CloudWatch (transiciones a ALARM)",
        "",
        "| Servicio | Estáticas (error > 1 %, p99 > SLO) | AIOps (correlacionadas) | Reducción |",
        "|---|---|---|---|",
        *[f"| {r['service']} | {r['static_notifications']} | {r['aiops_notifications']} | {r['reduction']} |" for r in rows],
        "",
        "## Reproducción offline sobre las mismas métricas (episodios por minuto)",
        "",
        "| Servicio | Minutos | Minutos en alerta (estática) | Notificaciones estáticas | Minutos en alerta (AIOps) | Notificaciones AIOps | Reducción |",
        "|---|---|---|---|---|---|---|",
        *[f"| {r['service']} | {r['minutes']} | {r['static_alert_minutes']} | {r['static_notifications']} | "
          f"{r['aiops_alert_minutes']} | {r['aiops_notifications']} | {r['reduction']} |" for r in replay_rows],
        "",
    ]
    markdown = "\n".join(lines)
    (out / f"noise-{stamp}.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
