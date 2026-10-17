"""Enriquecedor de alertas, métricas de seguridad y reproducción de ruido (ID-003, Módulos B y C)."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enricher = load("alert_enricher", "infra/lambda/alert_enricher/handler.py")
security = load("security_metrics", "infra/lambda/security_metrics/handler.py")

ENV = {
    "OTEL_LOG_GROUP": "/pipeline-otel/lab",
    "FLOW_LOG_GROUP": "/vpc/lab/flow-logs",
    "FINDINGS_LOG_GROUP": "/aws/events/lab/security-findings",
    "ECS_LOG_GROUP": "/ecs/lab",
    "LAB_NAME": "lab",
    "VPC_CIDR": "10.63.0.0/16",
}


def alarm(kind: str, service: str, state: str = "ALARM") -> dict:
    return {
        "AlarmName": f"lab-{service}-correlated-errors",
        "AlarmDescription": json.dumps({"service": service, "kind": kind, "group": "aiops",
                                        "rule": "error_rate > baseline + 2σ AND latency_p99 > SLO"}),
        "NewStateValue": state,
        "OldStateValue": "OK",
        "NewStateReason": "composite",
        "StateChangeTime": "2026-10-20T15:04:05.123+0000",
    }


def test_correlated_alert_carries_trace_id_and_runbook():
    calls = []

    def query(group, text, start, end):
        calls.append((group, text, end - start))
        return [{"@timestamp": "2026-10-20 15:03:59", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                 "status_code": "503", "route": "/records"}]

    alert = enricher.enrich(alarm("correlated", "data-service"), query, ENV,
                            now=datetime(2026, 10, 20, 15, 4, 20, tzinfo=timezone.utc))
    assert alert["primary_trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert alert["actionable"] is True
    assert alert["links"]["jaeger_path"] == "/trace/4bf92f3577b34da6a3ce929d0e0e4736"
    assert alert["runbook"]
    group, text, window = calls[0]
    assert group == "/pipeline-otel/lab"
    assert 'service = "data-service"' in text and "status_code >= 500" in text
    assert window >= 600
    subject, message = enricher.render_message(alert)
    assert subject.startswith("[ALARM] data-service")
    assert "trace_id primario" in message


def test_latency_alert_sorts_by_duration():
    texts = []
    enricher.enrich(alarm("latency", "catalog"), lambda g, t, s, e: texts.append(t) or [], ENV)
    assert "sort duration_ms desc" in texts[0]


def test_ok_state_skips_queries():
    alert = enricher.enrich(alarm("correlated", "data-service", state="OK"),
                            lambda *a: (_ for _ in ()).throw(AssertionError("no query")), ENV)
    assert alert["state"] == "OK" and alert["evidence"] == []


def test_network_and_security_queries_target_their_groups():
    assert enricher.build_query("network", "vpc", "10.63.0.0/16")[0] == "FLOW_LOG_GROUP"
    assert enricher.build_query("security", "grafana", "10.63.0.0/16")[0] == "ECS_LOG_GROUP"
    assert enricher.build_query("security", "account", "10.63.0.0/16")[0] == "FINDINGS_LOG_GROUP"


def test_query_failure_still_publishes_alert():
    def boom(*args):
        raise TimeoutError

    alert = enricher.enrich(alarm("correlated", "data-service"), boom, ENV)
    assert alert["evidence_error"] == "TimeoutError" and alert["actionable"] is False


def test_security_metrics_counts_cves_by_severity():
    findings = [
        {"Severity": {"Label": "HIGH"}, "Types": ["Software and Configuration Checks/Vulnerabilities/CVE"]},
        {"Severity": {"Label": "HIGH"}, "Types": ["Software and Configuration Checks/AWS Security Best Practices"]},
        {"Severity": {"Label": "CRITICAL"}, "Types": ["Software and Configuration Checks/Vulnerabilities/CVE"]},
    ]
    all_findings, cves = security.count_by_severity(findings)
    assert all_findings["HIGH"] == 2 and cves["HIGH"] == 1 and cves["CRITICAL"] == 1
    data = security.metric_data(all_findings, cves)
    assert len(data) == 10
    assert {"MetricName": "ActiveCVEs", "Dimensions": [{"Name": "severity", "Value": "LOW"}],
            "Value": 0, "Unit": "Count"} in data


def test_noise_replay_static_vs_correlated():
    from scripts.aiops.noise_report import episodes, replay

    assert episodes([False, True, True, False, True]) == 2
    # 60 minutos estables con ruido leve, picos aislados de latencia (ruido para la regla estática)
    # y un incidente real de 5 minutos con errores y latencia a la vez.
    rate = [0.2 if i % 7 else 0.6 for i in range(60)] + [8, 9, 10, 9, 8] + [0.2] * 10
    p99 = [120 if i % 15 else 320 for i in range(60)] + [600] * 5 + [120] * 10
    result = replay({"error_rate": rate, "p99": p99}, slo_ms=300, static_pct=1.0)
    assert result["aiops_notifications"] == 1
    assert result["static_notifications"] > result["aiops_notifications"]
