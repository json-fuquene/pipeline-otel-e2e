#!/usr/bin/env python3
"""Create local database credentials without printing or overwriting them."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def add_missing_keys(target: Path, values: dict[str, str]) -> int:
    """Agrega solo las claves ausentes (p. ej. DATA_DB_PASSWORD de ID-003) sin tocar las existentes."""
    current = target.read_text(encoding="utf-8")
    present = {line.split("=", 1)[0] for line in current.splitlines() if "=" in line}
    missing = {key: value for key, value in values.items() if key not in present}
    if not missing:
        print(".env ya existe y está completo; no se modificó.", file=sys.stderr)
        return 1
    with target.open("a", encoding="utf-8") as output:
        if not current.endswith("\n"):
            output.write("\n")
        output.write("".join(f"{key}={value}\n" for key, value in missing.items()))
    print(f".env actualizado con {', '.join(sorted(missing))}. Las credenciales no se muestran.")
    return 0


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "CATALOG_DB_PASSWORD": secrets.token_hex(32),
        "ORDERS_DB_PASSWORD": secrets.token_hex(32),
        "DATA_DB_PASSWORD": secrets.token_hex(32),
    }
    if len(set(values.values())) != len(values):
        raise RuntimeError("No fue posible generar credenciales distintas.")

    content = "# Archivo local generado; no compartir ni versionar.\n"
    content += "".join(f"{key}={value}\n" for key, value in values.items())
    descriptor: int | None = None
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            descriptor = None
            output.write(content)
    except FileExistsError:
        return add_missing_keys(target, values)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        target.unlink(missing_ok=True)
        raise

    print(".env creado con permisos privados. Las credenciales no se muestran.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
