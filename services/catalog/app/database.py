from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from services.catalog.app.config import database_url
from services.catalog.app.telemetry import instrument_database


def create_database() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(
        database_url(),
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
        pool_pre_ping=True,
        pool_timeout=2,
    )
    instrument_database(engine)
    return async_sessionmaker(engine, expire_on_commit=False), engine
