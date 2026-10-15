from __future__ import annotations

import json
import logging
import os
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from opentelemetry.trace import get_current_span


def configure_logging() -> logging.Logger:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise RuntimeError("LOG_LEVEL no es válido.")
    logging.basicConfig(level=level, format="%(message)s", force=True)
    return logging.getLogger("service")


def request_id_from_header(value: str | None) -> str:
    if value:
        try:
            parsed = uuid.UUID(value)
            if str(parsed) == value:
                return value
        except (ValueError, AttributeError):
            pass
    return str(uuid.uuid4())


async def request_logging_middleware(
    request: Request,
    call_next,
    logger: logging.Logger,
    *,
    json_paths: frozenset[str] = frozenset(),
):
    request_id = request_id_from_header(request.headers.get("x-request-id"))
    request.state.request_id = request_id
    started = time.perf_counter()
    status_code = 500
    try:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if request.method == "POST" and request.url.path in json_paths and content_type != "application/json":
            response = JSONResponse(
                status_code=415,
                content={
                    "error": {
                        "code": "unsupported_media_type",
                        "message": "Se requiere application/json.",
                    },
                    "request_id": request_id,
                },
            )
        else:
            response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        span_context = get_current_span().get_span_context()
        trace_id = f"{span_context.trace_id:032x}" if span_context.is_valid else None
        span_id = f"{span_context.span_id:016x}" if span_context.is_valid else None
        logger.info(
            json.dumps(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "level": "INFO",
                    "service": "orders",
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "method": request.method,
                    "route": route_path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
                separators=(",", ":"),
            )
        )
