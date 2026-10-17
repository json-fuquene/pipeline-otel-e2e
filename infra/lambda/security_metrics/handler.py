"""Publica conteos de hallazgos activos de Security Hub como métricas (ID-003, Módulo C).

Se ejecuta por EventBridge Scheduler. Las métricas ``PipelineOtel/Security`` alimentan el panel
«CVEs activos» del dashboard de Golden Signals de Seguridad:

* ``ActiveCVEs{severity}``: hallazgos de vulnerabilidades (Amazon Inspector sobre imágenes ECR).
* ``ActiveFindings{severity}``: todos los hallazgos activos (controles FSBP, Inspector, GuardDuty).
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL")
CVE_TYPE_PREFIX = "Software and Configuration Checks/Vulnerabilities/CVE"

ACTIVE_FILTERS = {
    "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
    "WorkflowStatus": [
        {"Value": "NEW", "Comparison": "EQUALS"},
        {"Value": "NOTIFIED", "Comparison": "EQUALS"},
    ],
}


def count_by_severity(findings: Iterable[dict]) -> tuple[Counter, Counter]:
    all_findings: Counter = Counter()
    cves: Counter = Counter()
    for finding in findings:
        severity = (finding.get("Severity") or {}).get("Label", "INFORMATIONAL")
        all_findings[severity] += 1
        if any(item.startswith(CVE_TYPE_PREFIX) for item in finding.get("Types", [])):
            cves[severity] += 1
    return all_findings, cves


def metric_data(all_findings: Counter, cves: Counter) -> list[dict]:
    data = []
    for severity in SEVERITIES:
        for name, counter in (("ActiveFindings", all_findings), ("ActiveCVEs", cves)):
            data.append(
                {
                    "MetricName": name,
                    "Dimensions": [{"Name": "severity", "Value": severity}],
                    "Value": counter.get(severity, 0),
                    "Unit": "Count",
                }
            )
    return data


def handler(event, context):  # pragma: no cover - integración con AWS
    import boto3

    securityhub = boto3.client("securityhub")
    cloudwatch = boto3.client("cloudwatch")
    paginator = securityhub.get_paginator("get_findings")
    findings = (
        finding
        for page in paginator.paginate(Filters=ACTIVE_FILTERS, PaginationConfig={"PageSize": 100})
        for finding in page["Findings"]
    )
    all_findings, cves = count_by_severity(findings)
    data = metric_data(all_findings, cves)
    for start in range(0, len(data), 20):
        cloudwatch.put_metric_data(Namespace="PipelineOtel/Security", MetricData=data[start:start + 20])
    return {"active_findings": dict(all_findings), "active_cves": dict(cves)}
