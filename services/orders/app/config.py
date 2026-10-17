from __future__ import annotations

import os
from urllib.parse import urlsplit

from sqlalchemy import URL


class ConfigurationError(RuntimeError):
    """La configuración requerida está incompleta o no es válida."""


SSL_MODES = frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"})


def connection_query(application_name: str) -> dict[str, str]:
    """Parámetros de conexión; DB_SSLMODE permite exigir TLS contra Amazon RDS."""
    query = {"application_name": application_name}
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    if sslmode:
        if sslmode not in SSL_MODES:
            raise ConfigurationError("La configuración sslmode no es válida.")
        query["sslmode"] = sslmode
    return query


def database_url() -> str:
    values = {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "pipeline"),
        "username": os.getenv("DB_USER", "orders_app"),
        "password": os.getenv("DB_PASSWORD"),
    }
    for key, value in values.items():
        if value is None or not value.strip():
            raise ConfigurationError(f"La configuración {key} es obligatoria.")
    try:
        port = int(values["port"])
    except (TypeError, ValueError) as error:
        raise ConfigurationError("La configuración port no es válida.") from error
    if not 1 <= port <= 65535:
        raise ConfigurationError("La configuración port no es válida.")

    return URL.create(
        "postgresql+psycopg",
        username=values["username"],
        password=values["password"],
        host=values["host"],
        port=port,
        database=values["database"],
        query=connection_query("orders"),
    ).render_as_string(hide_password=False)


def catalog_base_url() -> str:
    value = os.getenv("CATALOG_BASE_URL", "http://catalog:8000").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ConfigurationError("CATALOG_BASE_URL no es válida.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ConfigurationError("CATALOG_BASE_URL no es válida.")
    return value


def data_service_base_url() -> str | None:
    """URL del data-service. Vacía deshabilita el registro de pedidos y el resumen."""
    value = os.getenv("DATA_SERVICE_BASE_URL", "").strip().rstrip("/")
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ConfigurationError("DATA_SERVICE_BASE_URL no es válida.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ConfigurationError("DATA_SERVICE_BASE_URL no es válida.")
    return value
