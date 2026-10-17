from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from services.data.app.config import SCHEMA, database_settings, database_url
from services.data.app.db_semconv import (
    DbSemconvEnricher,
    register_error_listener,
    register_span_listeners,
)
from services.data.app.telemetry import instrument_database


def create_database() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    settings = database_settings()
    engine = create_async_engine(
        database_url(),
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
        pool_pre_ping=True,
        pool_timeout=2,
    )
    enricher = DbSemconvEnricher(
        database=str(settings["database"]),
        schema=SCHEMA,
        server_address=str(settings["host"]),
        port=int(settings["port"]),
    )
    register_error_listener(engine.sync_engine, enricher)
    instrument_database(engine)
    register_span_listeners(engine.sync_engine, enricher)
    return async_sessionmaker(engine, expire_on_commit=False), engine
