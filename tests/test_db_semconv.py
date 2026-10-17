"""Atributos OTel DB Semantic Conventions del data-service (ID-003, RF-302)."""
from __future__ import annotations

import os

import pytest

from services.data.app.db_semconv import collection_name, operation_name, query_summary, semconv_attributes


def test_operation_and_collection_extraction():
    statement = "INSERT INTO data.order_records (id, order_id) VALUES (%(id)s, %(order_id)s)"
    assert operation_name(statement) == "INSERT"
    assert collection_name(statement, "data") == "data.order_records"
    assert query_summary(statement, "data") == "INSERT data.order_records"


def test_unqualified_table_uses_default_schema():
    assert collection_name("SELECT count(*) FROM order_records", "data") == "data.order_records"
    assert query_summary("SELECT 1", "data") == "SELECT"
    assert query_summary("COMMIT", "data") == "COMMIT"


def test_semconv_attributes_for_postgresql():
    attributes = semconv_attributes(
        'SELECT data.order_records.id FROM data.order_records WHERE data.order_records.order_id = %(p)s',
        database="pipeline",
        schema="data",
        port=5432,
    )
    assert attributes == {
        "db.system.name": "postgresql",
        "db.namespace": "pipeline|data",
        "server.port": 5432,
        "db.operation.name": "SELECT",
        "db.collection.name": "data.order_records",
        "db.query.summary": "SELECT data.order_records",
    }


@pytest.mark.skipif(not os.getenv("TEST_DATA_DB_PASSWORD"), reason="Requiere PostgreSQL con el esquema data")
def test_data_service_spans_against_postgres(monkeypatch):
    """Integración: crea un registro y verifica spans CLIENT con convenciones estables."""
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", "http,database")
    monkeypatch.setenv("DB_USER", "data_app")
    monkeypatch.setenv("DB_PASSWORD", os.environ["TEST_DATA_DB_PASSWORD"])
    monkeypatch.setenv("DB_HOST", os.getenv("TEST_DB_HOST", "127.0.0.1"))
    monkeypatch.setenv("OTEL_METRICS_PORT", "19466")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:1")
    from services.data.app import main, telemetry

    exporter = InMemorySpanExporter()
    telemetry._tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    import uuid

    with TestClient(main.app) as client:
        response = client.post(
            "/records",
            json={"order_id": str(uuid.uuid4()), "product_id": str(uuid.uuid4()), "quantity": 1, "total": "9.90"},
        )
        assert response.status_code == 201
        assert client.get("/reports/summary").status_code == 200

    db_spans = [span for span in exporter.get_finished_spans() if span.attributes.get("db.system.name")]
    insert = next(span for span in db_spans if span.name == "INSERT data.order_records")
    assert insert.attributes["db.namespace"] == "pipeline|data"
    assert insert.attributes["db.collection.name"] == "data.order_records"
    assert insert.attributes["db.operation.name"] == "INSERT"
    assert "db.query.text" in insert.attributes
    assert insert.attributes["server.port"] == 5432
    business = {span.name for span in exporter.get_finished_spans()}
    assert {"data.record.create", "data.report.summary"} <= business
