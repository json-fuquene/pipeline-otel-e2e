"""Enriquecimiento de spans de base de datos según OTel DB Semantic Conventions (estables).

``SQLAlchemyInstrumentor`` crea un span CLIENT por sentencia y, con
``OTEL_SEMCONV_STABILITY_OPT_IN=database``, ya emite ``db.system.name``, ``db.namespace``,
``db.query.text`` y ``db.operation.name``. Este módulo completa los atributos que la
instrumentación automática no calcula para PostgreSQL:

* ``db.namespace`` con el patrón ``{database}|{schema}`` exigido para PostgreSQL;
* ``db.collection.name`` y ``db.query.summary`` (``"SELECT data.order_records"``), que también
  pasa a ser el nombre del span;
* ``server.port``, ``db.response.status_code`` (SQLSTATE) y ``error.type`` cuando la sentencia falla;
* el histograma estable ``db.client.operation.duration`` en segundos.

Las sentencias son parametrizadas, por lo que ``db.query.text`` no contiene valores literales.
"""
from __future__ import annotations

import re
import time
from typing import Any

from opentelemetry import metrics
from sqlalchemy import event
from sqlalchemy.engine import Engine

_TABLE = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+((?:\"?[A-Za-z_][\w$]*\"?\.)?\"?[A-Za-z_][\w$]*\"?)",
    re.IGNORECASE,
)
_OPERATION = re.compile(r"^\s*(?:/\*.*?\*/\s*)?([A-Za-z]+)", re.DOTALL)
_DURATION_BUCKETS = (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10)


def operation_name(statement: str) -> str | None:
    match = _OPERATION.match(statement or "")
    return match.group(1).upper() if match else None


def collection_name(statement: str, default_schema: str) -> str | None:
    match = _TABLE.search(statement or "")
    if not match:
        return None
    name = match.group(1).replace('"', "")
    return name if "." in name else f"{default_schema}.{name}"


def query_summary(statement: str, default_schema: str) -> str | None:
    operation = operation_name(statement)
    if operation is None:
        return None
    if operation in {"BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE"}:
        return operation
    collection = collection_name(statement, default_schema)
    return f"{operation} {collection}" if collection else operation


def semconv_attributes(statement: str, *, database: str, schema: str, port: int) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "db.system.name": "postgresql",
        "db.namespace": f"{database}|{schema}",
        "server.port": port,
    }
    operation = operation_name(statement)
    if operation:
        attributes["db.operation.name"] = operation
    collection = collection_name(statement, schema)
    if collection:
        attributes["db.collection.name"] = collection
    summary = query_summary(statement, schema)
    if summary:
        attributes["db.query.summary"] = summary
    return attributes


class DbSemconvEnricher:
    def __init__(self, *, database: str, schema: str, server_address: str, port: int) -> None:
        self.database = database
        self.schema = schema
        self.server_address = server_address
        self.port = port
        self._duration = metrics.get_meter("services.data.db").create_histogram(
            "db.client.operation.duration",
            unit="s",
            description="Duración de operaciones de cliente de base de datos.",
            explicit_bucket_boundaries_advisory=_DURATION_BUCKETS,
        )

    def _metric_attributes(self, statement: str, error_type: str | None = None) -> dict[str, Any]:
        attributes = semconv_attributes(
            statement, database=self.database, schema=self.schema, port=self.port
        )
        attributes.pop("db.query.summary", None)
        attributes["server.address"] = self.server_address
        if error_type:
            attributes["error.type"] = error_type
        return attributes

    def before_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        context._semconv_started = time.perf_counter()
        span = getattr(context, "_otel_span", None)
        if span is None or not span.is_recording():
            return
        attributes = semconv_attributes(
            statement, database=self.database, schema=self.schema, port=self.port
        )
        span.set_attributes(attributes)
        if "db.query.summary" in attributes:
            span.update_name(attributes["db.query.summary"])

    def after_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        started = getattr(context, "_semconv_started", None)
        if started is not None:
            self._duration.record(time.perf_counter() - started, self._metric_attributes(statement))

    def handle_error(self, exception_context) -> None:
        error = exception_context.original_exception
        error_type = type(error).__name__
        sqlstate = getattr(error, "sqlstate", None) or getattr(
            getattr(error, "diag", None), "sqlstate", None
        )
        execution_context = exception_context.execution_context
        statement = exception_context.statement or ""
        span = getattr(execution_context, "_otel_span", None) if execution_context else None
        if span is not None and span.is_recording():
            span.set_attribute("error.type", sqlstate or error_type)
            if sqlstate:
                span.set_attribute("db.response.status_code", sqlstate)
        started = getattr(execution_context, "_semconv_started", None) if execution_context else None
        if started is not None:
            self._duration.record(
                time.perf_counter() - started,
                self._metric_attributes(statement, sqlstate or error_type),
            )


def register_error_listener(engine: Engine, enricher: DbSemconvEnricher) -> None:
    """Debe ejecutarse antes de instrumentar: el instrumentor cierra el span en ``handle_error``."""
    event.listen(engine, "handle_error", enricher.handle_error)


def register_span_listeners(engine: Engine, enricher: DbSemconvEnricher) -> None:
    """Debe ejecutarse después de instrumentar para encontrar el span ya creado."""
    event.listen(engine, "before_cursor_execute", enricher.before_cursor_execute)
    event.listen(engine, "after_cursor_execute", enricher.after_cursor_execute)
