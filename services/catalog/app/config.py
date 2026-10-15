from __future__ import annotations

import os

from sqlalchemy import URL


class ConfigurationError(RuntimeError):
    """La configuración requerida está incompleta o no es válida."""


def database_url() -> str:
    values = {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_NAME", "pipeline"),
        "username": os.getenv("DB_USER", "catalog_app"),
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
        query={"application_name": "catalog"},
    ).render_as_string(hide_password=False)
