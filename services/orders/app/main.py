from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from services.orders.app.config import catalog_base_url
from services.orders.app.database import create_database
from services.orders.app.errors import (
    ApiError,
    ErrorEnvelope,
    api_error_handler,
    database_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from services.orders.app.models import Order
from services.orders.app.observability import configure_logging, request_logging_middleware
from services.orders.app.telemetry import (
    configure_telemetry,
    get_tracer,
    instrument_httpx,
    sanitize_server_span,
    start_metrics_server,
    stop_telemetry,
)
from services.orders.app.schemas import (
    CatalogProduct,
    OrderCreate,
    OrderOut,
    OrderPage,
    OrdersReadiness,
)

logger = configure_logging()
configure_telemetry("orders")
instrument_httpx()
tracer = get_tracer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory, engine = create_database()
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.state.catalog_base_url = catalog_base_url()
    app.state.catalog_client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0),
        follow_redirects=False,
    )
    try:
        start_metrics_server()
        yield
    finally:
        await app.state.catalog_client.aclose()
        await engine.dispose()
        stop_telemetry()


app = FastAPI(title="Pedidos", version="1.0.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="health/live,health/ready",
    server_request_hook=sanitize_server_span,
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    return await request_logging_middleware(
        request, call_next, logger, json_paths=frozenset({"/orders"})
    )


app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)


async def get_session(request: Request):
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


async def get_catalog_product(request: Request, product_id: UUID) -> CatalogProduct:
    client: httpx.AsyncClient = request.app.state.catalog_client
    url = f"{request.app.state.catalog_base_url}/products/{product_id}"
    request_headers = {"X-Request-ID": request.state.request_id}
    try:
        async with asyncio.timeout(5.0):
            response = await client.get(url, headers=request_headers)
            if response.status_code == 404:
                raise ApiError(404, "product_not_found", "Producto no encontrado.")
            if response.status_code >= 500:
                raise ApiError(503, "catalog_unavailable", "El catálogo no está disponible.")
            if response.status_code != 200:
                raise ApiError(502, "catalog_invalid_response", "El catálogo devolvió una respuesta inválida.")
            product = CatalogProduct.model_validate_json(response.content, strict=True)
            if product.id != product_id:
                raise ApiError(502, "catalog_invalid_response", "El catálogo devolvió una respuesta inválida.")
            return product
    except ApiError:
        raise
    except (httpx.TimeoutException, TimeoutError) as error:
        raise ApiError(504, "catalog_timeout", "El catálogo tardó demasiado en responder.") from error
    except (httpx.HTTPError, ValueError, TypeError) as error:
        raise ApiError(502 if isinstance(error, ValueError) else 503,
                       "catalog_invalid_response" if isinstance(error, ValueError) else "catalog_unavailable",
                       "El catálogo devolvió una respuesta inválida." if isinstance(error, ValueError)
                       else "El catálogo no está disponible.") from error


@app.post(
    "/orders",
    response_model=OrderOut,
    status_code=201,
    responses={404: {"model": ErrorEnvelope}, 415: {"model": ErrorEnvelope},
               422: {"model": ErrorEnvelope}, 502: {"model": ErrorEnvelope},
               503: {"model": ErrorEnvelope}, 504: {"model": ErrorEnvelope},
               500: {"model": ErrorEnvelope}},
)
async def create_order(
    payload: OrderCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    with tracer.start_as_current_span("orders.order.create"):
        product = await get_catalog_product(request, payload.product_id)
        unit_price = Decimal(product.price)
        order = Order(
            id=uuid4(),
            product_id=product.id,
            product_name=product.name,
            unit_price=unit_price,
            quantity=payload.quantity,
            total=unit_price * payload.quantity,
            created_at=datetime.now(UTC),
        )
        try:
            async with session.begin():
                session.add(order)
                await session.flush()
        except SQLAlchemyError as error:
            await session.rollback()
            raise ApiError(
                503, "database_unavailable", "La base de datos no está disponible."
            ) from error
        return OrderOut.model_validate(order)


@app.get(
    "/orders", response_model=OrderPage,
    responses={422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope},
               500: {"model": ErrorEnvelope}},
)
async def list_orders(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(
        select(Order).order_by(Order.created_at.asc(), Order.id.asc()).limit(limit).offset(offset)
    )
    return OrderPage(
        items=[OrderOut.model_validate(order) for order in rows], limit=limit, offset=offset
    )


@app.get(
    "/orders/{order_id}", response_model=OrderOut,
    responses={404: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope},
               503: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
)
async def get_order(order_id: UUID, session: AsyncSession = Depends(get_session)):
    order = await session.get(Order, order_id)
    if order is None:
        raise ApiError(404, "order_not_found", "Pedido no encontrado.")
    return OrderOut.model_validate(order)


@app.get("/health/live")
async def live():
    return {"status": "ok", "service": "orders"}


@app.get(
    "/health/ready", response_model=OrdersReadiness,
    responses={503: {"model": OrdersReadiness}},
)
async def ready(request: Request):
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    checks = {"database": "up", "catalog": "up"}
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        checks["database"] = "down"

    try:
        client: httpx.AsyncClient = request.app.state.catalog_client
        async with asyncio.timeout(2.0):
            response = await client.get(
                f"{request.app.state.catalog_base_url}/health/ready",
                headers={"X-Request-ID": request.state.request_id},
                timeout=httpx.Timeout(2.0),
            )
        if response.status_code != 200:
            checks["catalog"] = "down"
    except (httpx.HTTPError, TimeoutError):
        checks["catalog"] = "down"

    is_ready = all(status == "up" for status in checks.values())
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "service": "orders",
            "checks": checks,
        },
    )
