from __future__ import annotations

import os

from sqlalchemy import URL

SCHEMA = "data"
SSL_MODES = frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"})


class ConfigurationError(RuntimeError):
    """La configuración requerida está incompleta o no es válida."""


def database_settings() -> dict[str, str | int]:
    values = {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "pipeline"),
        "username": os.getenv("DB_USER", "data_app"),
        "password": os.getenv("DB_PASSWORD"),
    }
    for key, value in values.items():
        if value is None or not value.strip():
            raise ConfigurationError(f"La configuración {key} es obligatoria.")
    try:
        port = int(values["port"])  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ConfigurationError("La configuración port no es válida.") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("La configuración port no es válida.")
    return {**values, "port": port}  # type: ignore[dict-item]


def database_url() -> str:
    values = database_settings()
    query = {"application_name": "data-service"}
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    if sslmode:
        if sslmode not in SSL_MODES:
            raise ConfigurationError("La configuración sslmode no es válida.")
        query["sslmode"] = sslmode
    return URL.create(
        "postgresql+psycopg",
        username=str(values["username"]),
        password=str(values["password"]),
        host=str(values["host"]),
        port=int(values["port"]),
        database=str(values["database"]),
        query=query,
    ).render_as_string(hide_password=False)


def cloud_provider() -> str:
    """Proveedor donde reside la base: ``aws`` (RDS), ``gcp`` (Cloud SQL) o ``local``."""
    value = os.getenv("DB_CLOUD_PROVIDER", "local").strip().lower()
    if value not in {"aws", "gcp", "local"}:
        raise ConfigurationError("DB_CLOUD_PROVIDER debe ser aws, gcp o local.")
    return value
