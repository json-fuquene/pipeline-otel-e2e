"""Enriquecedor de alertas (ID-003, Módulo B).

Recibe por SNS los cambios de estado de las alarmas compuestas (regla de correlación AIOps), de red y
de seguridad. Para cada ALARM consulta CloudWatch Logs Insights y adjunta evidencia accionable:

* errores/correlación → los ``trace_id`` de las solicitudes 5xx del servicio en la ventana;
* latencia → los ``trace_id`` de las solicitudes más lentas;
* red → los pares origen/destino/puerto con más flujos rechazados o mayor volumen este-oeste;
* seguridad → los últimos hallazgos de Security Hub o intentos de autenticación fallidos.

El resultado se publica en el tópico enriquecido, se escribe como JSON en el log de la función
(consultable desde Grafana) y se cuenta en ``PipelineOtel/AIOps``. Solo usa la biblioteca estándar
y boto3 incluido en el runtime de Lambda.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

QueryFn = Callable[[str, str, int, int], list[dict[str, str]]]

FLOW_PARSE = (
    'parse @message "* * * * * * * * * * * * * * * * *" as version, account, eni, srcaddr, dstaddr, '
    "srcport, dstport, protocol, packets, bytes, start, end, action, status, pkt_src, pkt_dst, direction"
)

RUNBOOKS = {
    "correlated": [
        "Abrir la traza primaria en Jaeger/Grafana Explore y ubicar el span con status ERROR.",
        "Revisar spans DB (db.query.summary, db.response.status_code) para descartar falla de RDS.",
        "Consultar el parámetro de caos del servicio y los despliegues recientes de ECS.",
        "Si el error budget cae por debajo del 50 %, congelar cambios y escalar al responsable del servicio.",
    ],
    "error": [
        "Abrir la traza primaria y localizar el span que devolvió 5xx.",
        "Comparar con la tasa de error de los servicios dependientes en el dashboard AIOps y SLO.",
    ],
    "latency": [
        "Abrir la traza más lenta y comparar la duración de los spans HTTP, DB y de negocio.",
        "Revisar TargetResponseTime de Service Connect para separar latencia de red y de aplicación.",
        "Verificar CPU/memoria del servicio en ECS y la latencia de RDS.",
    ],
    "network": [
        "Validar si los pares origen/destino corresponden a servicios del laboratorio o a orígenes externos.",
        "Confirmar las reglas del security group y que ningún puerto nuevo quedó expuesto.",
    ],
    "security": [
        "Revisar el hallazgo en Security Hub y su recurso afectado.",
        "Para intentos de autenticación fallidos, confirmar el origen en VPC Flow Logs y rotar la credencial si aplica.",
    ],
}


def parse_description(description: str | None) -> dict[str, Any]:
    if not description:
        return {}
    try:
        value = json.loads(description)
    except (TypeError, ValueError):
        return {"rule": description}
    return value if isinstance(value, dict) else {}


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    if len(normalized) >= 5 and normalized[-5] in "+-" and normalized[-3] != ":":
        normalized = normalized[:-2] + ":" + normalized[-2:]
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def build_query(kind: str, service: str | None, vpc_cidr: str) -> tuple[str, str] | None:
    """Devuelve (variable de entorno del grupo de logs, consulta Logs Insights)."""
    if kind in {"correlated", "error"} and service:
        return "OTEL_LOG_GROUP", (
            "fields @timestamp, trace_id, span_id, request_id, route, status_code, duration_ms"
            f' | filter service = "{service}" and status_code >= 500 and ispresent(trace_id)'
            " | sort @timestamp desc | limit 5"
        )
    if kind == "latency" and service:
        return "OTEL_LOG_GROUP", (
            "fields @timestamp, trace_id, span_id, request_id, route, status_code, duration_ms"
            f' | filter service = "{service}" and ispresent(trace_id) and route not like /health/'
            " | sort duration_ms desc | limit 5"
        )
    if kind == "network":
        return "FLOW_LOG_GROUP", (
            f"{FLOW_PARSE}"
            f' | filter action = "REJECT" or (isIpv4InSubnet(srcaddr, "{vpc_cidr}")'
            f' and isIpv4InSubnet(dstaddr, "{vpc_cidr}"))'
            " | stats count(*) as flows, sum(bytes) as total_bytes by srcaddr, dstaddr, dstport, action"
            " | sort flows desc | limit 5"
        )
    if kind == "security" and service == "grafana":
        return "ECS_LOG_GROUP", (
            "fields @timestamp, @logStream, @message"
            " | filter @logStream like /grafana/ and @message like /(?i)invalid username or password|password-auth.failed/"
            " | sort @timestamp desc | limit 5"
        )
    if kind == "security":
        return "FINDINGS_LOG_GROUP", (
            "fields @timestamp, detail.findings.0.Title as title, detail.findings.0.Severity.Label as severity,"
            " detail.findings.0.Resources.0.Id as resource"
            " | sort @timestamp desc | limit 5"
        )
    return None


def enrich(
    alarm: dict[str, Any],
    query: QueryFn,
    env: dict[str, str],
    now: datetime | None = None,
) -> dict[str, Any]:
    meta = parse_description(alarm.get("AlarmDescription"))
    state = alarm.get("NewStateValue", "UNKNOWN")
    kind = meta.get("kind", "error")
    service = meta.get("service")
    changed_at = parse_time(alarm.get("StateChangeTime"))
    now = now or datetime.now(timezone.utc)

    alert: dict[str, Any] = {
        "type": "enriched_alert",
        "lab": env.get("LAB_NAME"),
        "alarm": alarm.get("AlarmName"),
        "state": state,
        "previous_state": alarm.get("OldStateValue"),
        "service": service,
        "kind": kind,
        "rule": meta.get("rule"),
        "group": meta.get("group"),
        "reason": alarm.get("NewStateReason"),
        "state_changed_at": changed_at.isoformat(),
        "enriched_at": now.isoformat(),
        "enrichment_seconds": None,
        "evidence": [],
        "primary_trace_id": None,
        "runbook": RUNBOOKS.get(kind, []),
        "actionable": False,
    }
    if state != "ALARM":
        return alert

    target = build_query(kind, service, env.get("VPC_CIDR", "10.63.0.0/16"))
    if target is None:
        return alert
    group_env, query_text = target
    log_group = env.get(group_env)
    if not log_group:
        alert["evidence_error"] = f"{group_env} no está configurado"
        return alert

    start = int((changed_at - timedelta(minutes=10)).timestamp())
    end = int((max(now, changed_at) + timedelta(minutes=1)).timestamp())
    started = time.monotonic()
    try:
        rows = query(log_group, query_text, start, end)
    except Exception as error:  # noqa: BLE001 - la alerta se publica aunque falle la evidencia
        alert["evidence_error"] = type(error).__name__
        rows = []
    alert["enrichment_seconds"] = round(time.monotonic() - started, 2)
    alert["evidence"] = rows
    trace_ids = [row["trace_id"] for row in rows if row.get("trace_id")]
    if trace_ids:
        alert["primary_trace_id"] = trace_ids[0]
        alert["trace_ids"] = trace_ids
        alert["links"] = {
            "jaeger_path": f"/trace/{trace_ids[0]}",
            "grafana_hint": env.get("GRAFANA_HINT", ""),
        }
    alert["actionable"] = bool(trace_ids) or (kind in {"network", "security"} and bool(rows))
    return alert


def render_message(alert: dict[str, Any]) -> tuple[str, str]:
    subject = f"[{alert['state']}] {alert.get('service') or 'lab'} — {alert.get('kind')} — {alert.get('alarm')}"
    lines = [
        f"Alarma: {alert.get('alarm')}",
        f"Estado: {alert.get('previous_state')} → {alert.get('state')} ({alert.get('state_changed_at')})",
        f"Regla: {alert.get('rule')}",
        f"Servicio: {alert.get('service')}",
    ]
    if alert.get("primary_trace_id"):
        lines.append(f"trace_id primario: {alert['primary_trace_id']}  (Jaeger {alert['links']['jaeger_path']})")
    if alert.get("evidence"):
        lines.append("Evidencia:")
        lines.extend(f"  - {json.dumps(row, ensure_ascii=False)}" for row in alert["evidence"])
    if alert.get("runbook") and alert.get("state") == "ALARM":
        lines.append("Runbook:")
        lines.extend(f"  {index}. {step}" for index, step in enumerate(alert["runbook"], start=1))
    lines.append("")
    lines.append(json.dumps(alert, ensure_ascii=False, default=str))
    return subject[:99], "\n".join(lines)


def _logs_query(client) -> QueryFn:
    def run(log_group: str, query_text: str, start: int, end: int) -> list[dict[str, str]]:
        query_id = client.start_query(
            logGroupName=log_group, startTime=start, endTime=end, queryString=query_text, limit=5
        )["queryId"]
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            response = client.get_query_results(queryId=query_id)
            if response["status"] in {"Complete", "Failed", "Cancelled", "Timeout"}:
                return [
                    {field["field"]: field["value"] for field in row if not field["field"].startswith("@ptr")}
                    for row in response.get("results", [])
                ]
            time.sleep(1)
        client.stop_query(queryId=query_id)
        return []

    return run


def handler(event, context):  # pragma: no cover - integración con AWS
    import boto3

    env = dict(os.environ)
    logs = boto3.client("logs")
    sns = boto3.client("sns")
    cloudwatch = boto3.client("cloudwatch")
    query = _logs_query(logs)
    results = []
    for record in event.get("Records", []):
        alarm = json.loads(record["Sns"]["Message"])
        alert = enrich(alarm, query, env)
        print(json.dumps(alert, ensure_ascii=False, default=str))
        subject, message = render_message(alert)
        sns.publish(TopicArn=env["ENRICHED_TOPIC_ARN"], Subject=subject, Message=message)
        if alert["state"] == "ALARM":
            cloudwatch.put_metric_data(
                Namespace="PipelineOtel/AIOps",
                MetricData=[
                    {
                        "MetricName": "EnrichedAlerts",
                        "Dimensions": [
                            {"Name": "kind", "Value": str(alert.get("kind"))},
                            {"Name": "service", "Value": str(alert.get("service") or "lab")},
                        ],
                        "Value": 1,
                        "Unit": "Count",
                    },
                    {
                        "MetricName": "ActionableAlerts",
                        "Dimensions": [{"Name": "kind", "Value": str(alert.get("kind"))}],
                        "Value": 1 if alert["actionable"] else 0,
                        "Unit": "Count",
                    },
                ],
            )
        results.append({"alarm": alert["alarm"], "state": alert["state"], "actionable": alert["actionable"]})
    return {"processed": results}
