from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str


class ValidationDetail(BaseModel):
    loc: list[str]
    type: str


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[ValidationDetail] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorInfo
    request_id: str


def error_response(request: Request, status: int, code: str, message: str, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    response = JSONResponse(
        status_code=status,
        content={
            "error": error,
            "request_id": getattr(request.state, "request_id", ""),
        },
    )
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


async def api_error_handler(request: Request, error: ApiError):
    return error_response(request, error.status_code, error.code, error.message)


async def validation_error_handler(request: Request, error: RequestValidationError):
    details = [
        {"loc": [str(part) for part in item.get("loc", ())], "type": item.get("type", "invalid")}
        for item in error.errors()
    ]
    return error_response(request, 422, "validation_error", "La solicitud no es válida.", details)


async def http_error_handler(request: Request, error: StarletteHTTPException):
    codes = {
        404: ("not_found", "El recurso solicitado no existe."),
        405: ("method_not_allowed", "El método no está permitido."),
        415: ("unsupported_media_type", "Se requiere application/json."),
    }
    code, message = codes.get(error.status_code, ("http_error", "La solicitud no se pudo completar."))
    return error_response(request, error.status_code, code, message)


async def database_error_handler(request: Request, error: SQLAlchemyError):
    return error_response(
        request, 503, "database_unavailable", "La base de datos no está disponible."
    )


async def unexpected_error_handler(request: Request, error: Exception):
    return error_response(request, 500, "internal_error", "Ocurrió un error interno.")
