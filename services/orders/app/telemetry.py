from __future__ import annotations

import os
from collections.abc import Sequence
from http.server import HTTPServer
from threading import Thread
from typing import Any

os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import start_http_server
from sqlalchemy.ext.asyncio import AsyncEngine

_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_metrics_server: tuple[HTTPServer, Thread] | None = None
_httpx_instrumented = False


def configure_telemetry(service_name: str) -> None:
    global _tracer_provider, _meter_provider
    if _tracer_provider is not None:
        return

    resource = Resource.create(
        {SERVICE_NAME: service_name, "deployment.environment.name": "local"}
    )
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    _tracer_provider = TracerProvider(resource=resource)
    _tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(_tracer_provider)
    set_global_textmap(TraceContextTextMapPropagator())

    _meter_provider = MeterProvider(
        resource=resource, metric_readers=[PrometheusMetricReader()]
    )
    metrics.set_meter_provider(_meter_provider)


def instrument_httpx() -> None:
    global _httpx_instrumented
    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument(async_request_hook=sanitize_httpx_span)
        _httpx_instrumented = True


def instrument_database(engine: AsyncEngine) -> None:
    if _tracer_provider is None or _meter_provider is None:
        raise RuntimeError(
            "La telemetría debe configurarse antes de instrumentar PostgreSQL."
        )
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=_tracer_provider,
        meter_provider=_meter_provider,
    )


def sanitize_server_span(span: Span | None, scope: dict[str, Any]) -> None:
    if span is None or not span.is_recording():
        return
    path = scope.get("path", "/")
    scheme = scope.get("scheme", "http")
    headers = dict(scope.get("headers", []))
    host = headers.get(b"host", b"").decode("latin1")
    safe_url = f"{scheme}://{host}{path}" if host else path
    span.set_attribute("http.target", path)
    span.set_attribute("http.url", safe_url)
    span.set_attribute("url.path", path)
    span.set_attribute("url.query", "")
    span.set_attribute("url.full", safe_url)


async def sanitize_httpx_span(span: Span | None, request: Sequence[Any]) -> None:
    if span is None or not span.is_recording():
        return
    url = request[1]
    safe_url = str(url.copy_with(query=None))
    span.set_attribute("http.url", safe_url)
    span.set_attribute("url.query", "")
    span.set_attribute("url.full", safe_url)


def start_metrics_server() -> tuple[HTTPServer, Thread]:
    global _metrics_server
    if _metrics_server is None:
        port = int(os.getenv("OTEL_METRICS_PORT", "9464"))
        if not 1 <= port <= 65535:
            raise RuntimeError("OTEL_METRICS_PORT debe estar entre 1 y 65535.")
        _metrics_server = start_http_server(port=port, addr="0.0.0.0")
    return _metrics_server


def stop_telemetry() -> None:
    global _metrics_server
    if _metrics_server is not None:
        server, thread = _metrics_server
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        _metrics_server = None
    if _meter_provider is not None:
        _meter_provider.shutdown()
    if _tracer_provider is not None:
        _tracer_provider.shutdown()


def get_tracer():
    return trace.get_tracer("services.orders")
