from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from services.data.app.config import database_url
from services.data.app.models import Base

config = context.config

url = database_url().replace("%", "%%")
config.set_main_option("sqlalchemy.url", url)
target_metadata = Base.metadata
schema = "data"


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == schema
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema=schema,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema=schema,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
