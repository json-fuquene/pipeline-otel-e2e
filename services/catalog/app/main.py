from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from services.catalog.app.database import create_database
from services.catalog.app.errors import (
    ApiError,
    ErrorEnvelope,
    api_error_handler,
    database_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from services.catalog.app.models import Product
from services.catalog.app.observability import configure_logging, request_logging_middleware
from services.catalog.app.telemetry import (
    configure_telemetry,
    get_tracer,
    sanitize_server_span,
    start_metrics_server,
    stop_telemetry,
)
from services.catalog.app.schemas import CatalogReadiness, ProductCreate, ProductOut, ProductPage

logger = configure_logging()
configure_telemetry("catalog")
tracer = get_tracer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory, engine = create_database()
    app.state.session_factory = session_factory
    app.state.engine = engine
    try:
        start_metrics_server()
        yield
    finally:
        await engine.dispose()
        stop_telemetry()


app = FastAPI(title="Catálogo", version="1.0.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="health/live,health/ready",
    server_request_hook=sanitize_server_span,
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    return await request_logging_middleware(
        request, call_next, logger, json_paths=frozenset({"/products"})
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


@app.post(
    "/products",
    response_model=ProductOut,
    status_code=201,
    responses={415: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope},
               503: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
)
async def create_product(payload: ProductCreate, session: AsyncSession = Depends(get_session)):
    with tracer.start_as_current_span("catalog.product.create"):
        product = Product(
            id=uuid4(),
            name=payload.name,
            price=Decimal(payload.price),
            created_at=datetime.now(UTC),
        )
        try:
            async with session.begin():
                session.add(product)
                await session.flush()
        except SQLAlchemyError as error:
            await session.rollback()
            raise ApiError(
                503, "database_unavailable", "La base de datos no está disponible."
            ) from error
        return ProductOut.model_validate(product)


@app.get(
    "/products", response_model=ProductPage,
    responses={422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope},
               500: {"model": ErrorEnvelope}},
)
async def list_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.scalars(
        select(Product)
        .order_by(Product.created_at.asc(), Product.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return ProductPage(
        items=[ProductOut.model_validate(product) for product in rows],
        limit=limit,
        offset=offset,
    )


@app.get(
    "/products/{product_id}", response_model=ProductOut,
    responses={404: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope},
               503: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
)
async def get_product(product_id: UUID, session: AsyncSession = Depends(get_session)):
    product = await session.get(Product, product_id)
    if product is None:
        raise ApiError(404, "product_not_found", "Producto no encontrado.")
    return ProductOut.model_validate(product)


@app.get("/health/live")
async def live():
    return {"status": "ok", "service": "catalog"}


@app.get(
    "/health/ready", response_model=CatalogReadiness,
    responses={503: {"model": CatalogReadiness}},
)
async def ready(request: Request):
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "catalog",
                "checks": {"database": "down"},
            },
        )
    return {"status": "ready", "service": "catalog", "checks": {"database": "up"}}
