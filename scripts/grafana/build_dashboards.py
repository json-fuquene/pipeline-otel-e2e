#!/usr/bin/env python3
"""Genera los dashboards Grafana del laboratorio observable (ID-003).

Los JSON resultantes se versionan en docker/grafana/dashboards-observable/ y se aprovisionan al
construir la imagen Grafana. Ejecutar de nuevo tras cambiar nombres, SLOs o consultas:

    python3 scripts/grafana/build_dashboards.py
"""
from __future__ import annotations

import json
from pathlib import Path

LAB = "pipeline-otel-obs"
REGION = "us-east-1"
OTEL_LOGS = f"/pipeline-otel/{LAB}"
FLOW_LOGS = f"/vpc/{LAB}/flow-logs"
FINDINGS_LOGS = f"/aws/events/{LAB}/security-findings"
ALERT_LOGS = f"/aws/lambda/{LAB}-alert-enricher"
VPC_CIDR = "10.63.0.0/16"
SERVICES = ["catalog", "orders", "data-service"]
SLO_MS = {"catalog": 150, "orders": 400, "data-service": 300}

PROM = {"type": "prometheus", "uid": "prometheus"}
CW = {"type": "cloudwatch", "uid": "cloudwatch"}
OUT = Path(__file__).resolve().parents[2] / "docker" / "grafana" / "dashboards-observable"
FLOW_PARSE = (
    'parse @message "* * * * * * * * * * * * * * * * *" as version, account, eni, srcaddr, dstaddr, '
    "srcport, dstport, protocol, packets, bytes, start, end, action, status, pkt_src, pkt_dst, direction"
)


class Layout:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.row_h = 0
        self.next_id = 1

    def place(self, w: int, h: int) -> dict:
        if self.x + w > 24:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        pos = {"x": self.x, "y": self.y, "w": w, "h": h}
        self.x += w
        self.row_h = max(self.row_h, h)
        return pos

    def id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


def prom(expr: str, legend: str, ref: str = "A") -> dict:
    return {"datasource": PROM, "expr": expr, "legendFormat": legend, "refId": ref}


def cw_metric(ref: str, namespace: str, metric: str, dims: dict, stat: str, *, label: str = "",
              hide: bool = False, period: str = "60", query_id: str = "", match_exact: bool = True) -> dict:
    return {
        "datasource": CW, "refId": ref, "id": query_id, "region": REGION, "queryMode": "Metrics",
        "metricQueryType": 0, "metricEditorMode": 0, "namespace": namespace, "metricName": metric,
        "dimensions": dims, "matchExact": match_exact, "statistic": stat, "period": period,
        "expression": "", "sqlExpression": "", "label": label, "logGroups": [], "hide": hide,
    }


def cw_expression(ref: str, expression: str, *, label: str = "", query_id: str = "") -> dict:
    return {
        "datasource": CW, "refId": ref, "id": query_id, "region": REGION, "queryMode": "Metrics",
        "metricQueryType": 0, "metricEditorMode": 1, "expression": expression, "namespace": "",
        "metricName": "", "dimensions": {}, "matchExact": True, "statistic": "Average", "period": "60",
        "sqlExpression": "", "label": label, "logGroups": [], "hide": False,
    }


def cw_logs(ref: str, groups: list[str], query: str) -> dict:
    return {
        "datasource": CW, "refId": ref, "id": "", "region": REGION, "queryMode": "Logs",
        "logsMode": "Logs", "queryLanguage": "CWLI", "queryType": "range",
        "logGroupNames": groups, "expression": query,
    }


def panel(layout: Layout, title: str, targets: list[dict], *, kind: str = "timeseries", w: int = 12,
          h: int = 8, unit: str | None = None, datasource: dict = PROM, description: str = "",
          thresholds: list[tuple[str, float | None]] | None = None, options: dict | None = None,
          transformations: list[dict] | None = None) -> dict:
    defaults: dict = {}
    if unit:
        defaults["unit"] = unit
    if thresholds:
        defaults["thresholds"] = {
            "mode": "absolute",
            "steps": [{"color": color, "value": value} for color, value in thresholds],
        }
        if kind == "timeseries":
            defaults["custom"] = {"thresholdsStyle": {"mode": "line+area"}}
    body = {
        "id": layout.id(), "type": kind, "title": title, "description": description,
        "datasource": datasource, "gridPos": layout.place(w, h), "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []}, "options": options or {},
    }
    if transformations:
        body["transformations"] = transformations
    return body


def dashboard(uid: str, title: str, panels: list[dict], tags: list[str], refresh: str = "30s") -> dict:
    return {
        "uid": uid, "title": title, "tags": ["ID-003", *tags], "timezone": "browser",
        "schemaVersion": 41, "version": 1, "editable": False, "refresh": refresh,
        "time": {"from": "now-1h", "to": "now"}, "panels": panels,
        "templating": {"list": []}, "annotations": {"list": []},
    }


def services_dashboard() -> dict:
    lay = Layout()
    req = 'pipeline_http_server_request_duration_seconds_count{http_route!~"/health/.*"}'
    err = 'pipeline_http_server_request_duration_seconds_count{http_route!~"/health/.*",http_response_status_code=~"5.."}'
    panels = [
        panel(lay, "Solicitudes por segundo", [prom("sli:requests:rate1m", "{{exported_job}}")], w=8, unit="reqps"),
        panel(lay, "Tasa de error 5xx (%)", [prom("100 * sli:error_ratio:rate1m", "{{exported_job}}")], w=8,
              unit="percent", thresholds=[("green", None), ("red", 1)]),
        panel(lay, "Latencia p99 (ms) — SLO catálogo 150 / pedidos 400 / data 300",
              [prom("1000 * sli:latency_p99_seconds:1m", "{{exported_job}}")], w=8, unit="ms",
              thresholds=[("green", None), ("orange", 150), ("red", 300)]),
        panel(lay, "Error budget restante en el rango (SLO 99 %)", [prom(
            f"clamp_min(100 * (1 - (sum by (exported_job) (increase({err}[$__range])) / "
            f"clamp_min(sum by (exported_job) (increase({req}[$__range])), 1)) / 0.01), -100)",
            "{{exported_job}}")], kind="bargauge", w=8, unit="percent",
            thresholds=[("red", None), ("orange", 25), ("green", 50)],
            options={"orientation": "horizontal", "displayMode": "gradient", "reduceOptions": {"calcs": ["lastNotNull"]}},
            description="100 % = presupuesto intacto; 0 % = presupuesto consumido en la ventana del dashboard."),
        panel(lay, "Burn rate (5 m) frente a SLO 99 %", [prom("slo:burn_rate:5m", "{{exported_job}}")], w=8,
              thresholds=[("green", None), ("orange", 6), ("red", 14.4)],
              description="1 = consumo exacto del presupuesto; 14.4 = alerta de quema rápida (Google SRE)."),
        panel(lay, "Spans DB — p95 de db.client.operation.duration (data-service)", [prom(
            "1000 * histogram_quantile(0.95, sum by (le, db_operation_name, db_collection_name) "
            "(rate(pipeline_db_client_operation_duration_seconds_bucket[5m])))",
            "{{db_operation_name}} {{db_collection_name}}")], w=8, unit="ms"),
        panel(lay, "Grafo de servicios (servicegraph): solicitudes/s por arista", [prom(
            "sum by (client, server) (rate(pipeline_traces_service_graph_request_total[5m]))",
            "{{client}} → {{server}}")], kind="bargauge", w=12,
            options={"orientation": "horizontal", "displayMode": "basic", "reduceOptions": {"calcs": ["lastNotNull"]}}),
        panel(lay, "Registros fallidos pedidos → data-service", [prom(
            "sum by (reason) (rate(pipeline_orders_data_record_failures_total[5m]))", "{{reason}}")], w=12,
            unit="ops"),
        panel(lay, "Logs 5xx con trace_id (pivotar a Jaeger)", [cw_logs("A", [OTEL_LOGS],
            "fields @timestamp, service, route, status_code, duration_ms, trace_id, request_id"
            " | filter status_code >= 500 | sort @timestamp desc | limit 50")],
            kind="table", w=24, h=9, datasource=CW),
    ]
    return dashboard("id003-services", "ID-003 · Servicios y SLO (3 pilares)", panels, ["slo", "otel"])


def aiops_dashboard() -> dict:
    lay = Layout()
    ns = "PipelineOtel/Services"
    panels = []
    for service in ["data-service", "catalog"]:
        dims = {"service": service}
        panels.append(panel(lay, f"{service}: tasa de error vs banda esperada (2σ)", [
            cw_metric("A", ns, "RequestCount", dims, "Sum", hide=True, query_id="req"),
            cw_metric("B", ns, "ServerErrorCount", dims, "Sum", hide=True, query_id="err"),
            cw_expression("C", "100 * FILL(err, 0) / req", label="error rate %", query_id="rate"),
            cw_expression("D", "ANOMALY_DETECTION_BAND(rate, 2)", label="banda 2σ", query_id="band"),
        ], w=12, unit="percent", datasource=CW))
        panels.append(panel(lay, f"{service}: latencia p99 vs SLO {SLO_MS[service]} ms y banda 2σ", [
            cw_metric("A", ns, "RequestLatency", dims, "p99", label="p99", query_id="p99"),
            cw_expression("B", "ANOMALY_DETECTION_BAND(p99, 2)", label="banda 2σ", query_id="band"),
        ], w=12, unit="ms", datasource=CW, thresholds=[("green", None), ("red", SLO_MS[service])]))
    panels.append(panel(lay, "Alertas enriquecidas emitidas (por tipo)", [
        cw_metric(chr(65 + i), "PipelineOtel/AIOps", "EnrichedAlerts", {"kind": kind, "service": "*"}, "Sum",
                  label=kind, match_exact=False)
        for i, kind in enumerate(["correlated", "latency", "network", "security"])
    ], kind="barchart", w=8, datasource=CW, options={"xTickLabelRotation": -45}))
    panels.append(panel(lay, "Alertas enriquecidas (trace_id, estado y accionabilidad)", [cw_logs("A", [ALERT_LOGS],
        'fields @timestamp, alarm, state, service, kind, primary_trace_id, actionable, enrichment_seconds'
        ' | filter type = "enriched_alert" | sort @timestamp desc | limit 50')],
        kind="table", w=16, datasource=CW))
    panels.append(panel(lay, "Cambios de configuración de caos (inicio/fin de experimentos)", [cw_logs("A", [OTEL_LOGS],
        'fields @timestamp, service, event, current.latency_ms, current.error_rate, current.error_delay_ms,'
        ' current.experiment | filter event = "chaos_config_changed" | sort @timestamp desc | limit 20')],
        kind="table", w=24, datasource=CW))
    return dashboard("id003-aiops", "ID-003 · AIOps: anomalías, correlación y alertas", panels, ["aiops"], "1m")


def network_dashboard() -> dict:
    lay = Layout()
    sc = "AWS/ECS"
    panels = [
        panel(lay, "Service Connect: solicitudes por destino (L7 este-oeste)", [
            cw_metric(chr(65 + i), sc, "RequestCount", {"DiscoveryName": name}, "Sum", label=name)
            for i, name in enumerate(["catalog", "data-service", "otel-collector"])
        ], w=12, datasource=CW),
        panel(lay, "Service Connect: respuestas 5xx del destino", [
            cw_metric(chr(65 + i), sc, "HTTPCode_Target_5XX_Count", {"TargetDiscoveryName": name}, "Sum", label=name)
            for i, name in enumerate(["catalog", "data-service"])
        ], w=12, datasource=CW),
        panel(lay, "Service Connect: TargetResponseTime (promedio / máximo)", [
            cw_metric("A", sc, "TargetResponseTime", {"TargetDiscoveryName": "catalog"}, "Average", label="catalog avg"),
            cw_metric("B", sc, "TargetResponseTime", {"TargetDiscoveryName": "catalog"}, "Maximum", label="catalog max"),
            cw_metric("C", sc, "TargetResponseTime", {"TargetDiscoveryName": "data-service"}, "Average", label="data avg"),
            cw_metric("D", sc, "TargetResponseTime", {"TargetDiscoveryName": "data-service"}, "Maximum", label="data max"),
        ], w=12, unit="ms", datasource=CW),
        panel(lay, "Service Connect: conexiones activas", [
            cw_metric(chr(65 + i), sc, "ActiveConnectionCount", {"DiscoveryName": name}, "Average", label=name)
            for i, name in enumerate(["catalog", "data-service", "orders"])
        ], w=12, datasource=CW),
        panel(lay, "VPC Flow Logs: bytes norte-sur vs este-oeste", [
            cw_metric("A", "PipelineOtel/Network", "AcceptedBytes", {}, "Sum", hide=True, query_id="total"),
            cw_metric("B", "PipelineOtel/Network", "EastWestBytes", {}, "Sum", label="este-oeste", query_id="ew"),
            cw_expression("C", "total - ew", label="norte-sur", query_id="ns"),
            cw_expression("D", "ANOMALY_DETECTION_BAND(ew, 2)", label="banda E-W 2σ", query_id="band"),
        ], w=12, unit="bytes", datasource=CW),
        panel(lay, "VPC Flow Logs: flujos rechazados", [
            cw_metric("A", "PipelineOtel/Network", "RejectedFlows", {}, "Sum", label="REJECT")
        ], w=12, datasource=CW, thresholds=[("green", None), ("red", 50)]),
        panel(lay, "Top pares este-oeste (bytes)", [cw_logs("A", [FLOW_LOGS],
            f'{FLOW_PARSE} | filter action = "ACCEPT" and isIpv4InSubnet(srcaddr, "{VPC_CIDR}")'
            f' and isIpv4InSubnet(dstaddr, "{VPC_CIDR}")'
            " | stats sum(bytes) as total_bytes, count(*) as flows by srcaddr, dstaddr, dstport"
            " | sort total_bytes desc | limit 15")], kind="table", w=24, h=9, datasource=CW),
    ]
    return dashboard("id003-network", "ID-003 · Red L7 (Service Connect) y VPC Flow Logs", panels, ["network"], "1m")


def security_dashboard() -> dict:
    lay = Layout()
    sec = "PipelineOtel/Security"
    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    stat_opts = {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "graphMode": "none"}
    panels = [
        panel(lay, "Intentos de autenticación fallidos (Grafana, 5 min)", [
            cw_metric("A", sec, "FailedAuthAttempts", {}, "Sum", period="300", label="fallidos")
        ], kind="stat", w=6, datasource=CW, thresholds=[("green", None), ("orange", 1), ("red", 5)], options=stat_opts),
        panel(lay, "CVEs activos por severidad (Inspector → Security Hub)", [
            cw_metric(chr(65 + i), sec, "ActiveCVEs", {"severity": s}, "Maximum", period="900", label=s)
            for i, s in enumerate(severities)
        ], kind="stat", w=12, datasource=CW, thresholds=[("green", None), ("red", 1)], options=stat_opts),
        panel(lay, "Flujos rechazados (5 min)", [
            cw_metric("A", "PipelineOtel/Network", "RejectedFlows", {}, "Sum", period="300", label="REJECT")
        ], kind="stat", w=6, datasource=CW, thresholds=[("green", None), ("orange", 10), ("red", 50)], options=stat_opts),
        panel(lay, "Tráfico norte-sur vs este-oeste", [
            cw_metric("A", "PipelineOtel/Network", "AcceptedBytes", {}, "Sum", hide=True, query_id="total"),
            cw_metric("B", "PipelineOtel/Network", "EastWestBytes", {}, "Sum", label="E-W", query_id="ew"),
            cw_expression("C", "total - ew", label="N-S", query_id="ns"),
        ], w=12, unit="bytes", datasource=CW),
        panel(lay, "Intentos de autenticación fallidos en el tiempo", [
            cw_metric("A", sec, "FailedAuthAttempts", {}, "Sum", label="fallidos")
        ], w=12, datasource=CW),
        panel(lay, "Hallazgos activos por severidad (todos los productos)", [
            cw_metric(chr(65 + i), sec, "ActiveFindings", {"severity": s}, "Maximum", period="900", label=s)
            for i, s in enumerate(severities)
        ], kind="barchart", w=12, datasource=CW),
        panel(lay, "Top orígenes rechazados", [cw_logs("A", [FLOW_LOGS],
            f'{FLOW_PARSE} | filter action = "REJECT"'
            " | stats count(*) as flows by srcaddr, dstport | sort flows desc | limit 15")],
            kind="table", w=12, datasource=CW),
        panel(lay, "Últimos hallazgos HIGH/CRITICAL/MEDIUM de Security Hub", [cw_logs("A", [FINDINGS_LOGS],
            "fields @timestamp, detail.findings.0.Severity.Label as severity, detail.findings.0.Title as title,"
            " detail.findings.0.ProductName as product, detail.findings.0.Resources.0.Id as resource"
            " | sort @timestamp desc | limit 30")], kind="table", w=24, h=9, datasource=CW),
    ]
    return dashboard("id003-security", "ID-003 · Golden Signals de Seguridad", panels, ["security"], "1m")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, board in {
        "services.json": services_dashboard(),
        "aiops.json": aiops_dashboard(),
        "network.json": network_dashboard(),
        "security.json": security_dashboard(),
    }.items():
        (OUT / name).write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{name}: {len(board['panels'])} paneles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
