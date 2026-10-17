from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from services.data.app.config import cloud_provider
from services.data.app.database import create_database
from services.data.app.errors import (
    ApiError,
    ErrorEnvelope,
    api_error_handler,
    database_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from services.data.app.models import OrderRecord
from services.data.app.observability import configure_logging, request_logging_middleware
from services.data.app.schemas import DataReadiness, RecordCreate, RecordOut, Summary, TopProduct
from services.data.app.telemetry import (
    attach_otel_logging,
    configure_telemetry,
    get_tracer,
    sanitize_server_span,
    start_metrics_server,
    stop_telemetry,
)
from services.shared.chaos import ChaosController

SERVICE_NAME = "data-service"

logger = configure_logging()
otel_enabled = configure_telemetry(SERVICE_NAME)
attach_otel_logging(logger)
tracer = get_tracer()
chaos = ChaosController(SERVICE_NAME, logger)
provider = cloud_provider()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_factory, engine = create_database()
    app.state.session_factory = session_factory
    app.state.engine = engine
    try:
        if otel_enabled:
            start_metrics_server()
        await chaos.start()
        yield
    finally:
        await chaos.stop()
        await engine.dispose()
        stop_telemetry()


app = FastAPI(title="Datos", version="1.0.0", lifespan=lifespan)
if otel_enabled:
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health/live,health/ready",
        server_request_hook=sanitize_server_span,
    )


# Orden de middlewares: el último registrado es el más externo. El caos queda dentro del
# middleware de logging para que la latencia y los 503 inyectados aparezcan en duration_ms.
@app.middleware("http")
async def chaos_middleware(request: Request, call_next):
    return await chaos.middleware(request, call_next)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    return await request_logging_middleware(
        request, call_next, logger, json_paths=frozenset({"/records"})
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
    "/records",
    response_model=RecordOut,
    status_code=201,
    responses={200: {"model": RecordOut}, 415: {"model": ErrorEnvelope},
               422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope},
               500: {"model": ErrorEnvelope}},
)
async def create_record(
    payload: RecordCreate,
    session: AsyncSession = Depends(get_session),
):
    """Registra el evento de un pedido. Repetir el mismo ``order_id`` devuelve el registro existente."""
    with tracer.start_as_current_span("data.record.create") as span:
        span.set_attribute("app.order.id", str(payload.order_id))
        statement = (
            insert(OrderRecord)
            .values(
                id=uuid4(),
                order_id=payload.order_id,
                product_id=payload.product_id,
                quantity=payload.quantity,
                total=Decimal(payload.total),
                recorded_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=[OrderRecord.order_id])
            .returning(OrderRecord.id)
        )
        try:
            async with session.begin():
                created_id = (await session.execute(statement)).scalar_one_or_none()
                record = await session.scalar(
                    select(OrderRecord).where(OrderRecord.order_id == payload.order_id)
                )
        except SQLAlchemyError as error:
            raise ApiError(
                503, "database_unavailable", "La base de datos no está disponible."
            ) from error
        if record is None:
            raise ApiError(503, "database_unavailable", "La base de datos no está disponible.")
        span.set_attribute("app.record.created", created_id is not None)
        body = RecordOut.model_validate(record).model_dump(mode="json")
        return JSONResponse(status_code=201 if created_id is not None else 200, content=body)


@app.get(
    "/records/{record_id}", response_model=RecordOut,
    responses={404: {"model": ErrorEnvelope}, 422: {"model": ErrorEnvelope},
               503: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}},
)
async def get_record(record_id: UUID, session: AsyncSession = Depends(get_session)):
    record = await session.get(OrderRecord, record_id)
    if record is None:
        raise ApiError(404, "record_not_found", "Registro no encontrado.")
    return RecordOut.model_validate(record)


@app.get(
    "/reports/summary", response_model=Summary,
    responses={422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope},
               500: {"model": ErrorEnvelope}},
)
async def summary(
    window_minutes: int = Query(default=60, ge=1, le=10_080),
    limit: int = Query(default=5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Agrega pedidos registrados en la ventana indicada (consulta analítica sobre RDS/Cloud SQL)."""
    with tracer.start_as_current_span("data.report.summary") as span:
        since = datetime.now(UTC) - timedelta(minutes=window_minutes)
        span.set_attribute("app.report.window_minutes", window_minutes)
        totals = (
            await session.execute(
                select(
                    func.count(OrderRecord.id),
                    func.coalesce(func.sum(OrderRecord.quantity), 0),
                    func.coalesce(func.sum(OrderRecord.total), 0),
                ).where(OrderRecord.recorded_at >= since)
            )
        ).one()
        top_rows = (
            await session.execute(
                select(
                    OrderRecord.product_id,
                    func.count(OrderRecord.id).label("orders"),
                    func.sum(OrderRecord.quantity).label("units"),
                    func.sum(OrderRecord.total).label("revenue"),
                )
                .where(OrderRecord.recorded_at >= since)
                .group_by(OrderRecord.product_id)
                .order_by(func.sum(OrderRecord.total).desc(), OrderRecord.product_id)
                .limit(limit)
            )
        ).all()
        return Summary(
            window_minutes=window_minutes,
            orders=int(totals[0]),
            units=int(totals[1]),
            revenue=format(Decimal(str(totals[2])), ".2f"),
            top_products=[
                TopProduct(
                    product_id=row.product_id,
                    orders=int(row.orders),
                    units=int(row.units),
                    revenue=format(Decimal(str(row.revenue)), ".2f"),
                )
                for row in top_rows
            ],
            database=provider,
        )


@app.get("/health/live")
async def live():
    return {"status": "ok", "service": SERVICE_NAME}


@app.get(
    "/health/ready", response_model=DataReadiness,
    responses={503: {"model": DataReadiness}},
)
async def ready(request: Request):
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    checks = {"database": "up"}
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        checks["database"] = "down"
    is_ready = checks["database"] == "up"
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "service": SERVICE_NAME,
            "checks": checks,
        },
    )
