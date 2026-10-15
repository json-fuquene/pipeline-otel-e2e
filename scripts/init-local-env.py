#!/usr/bin/env python3
"""Create local database credentials without printing or overwriting them."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "CATALOG_DB_PASSWORD": secrets.token_hex(32),
        "ORDERS_DB_PASSWORD": secrets.token_hex(32),
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
        print(".env ya existe; no se modificó.", file=sys.stderr)
        return 1
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        target.unlink(missing_ok=True)
        raise

    print(".env creado con permisos privados. Las credenciales no se muestran.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
