"""Envoltorio mínimo sobre AWS CLI v2 (evita exigir boto3 en el equipo local)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AwsCliError(RuntimeError):
    pass


def aws(*args: str, region: str | None = None, parse: bool = True) -> Any:
    command = ["aws", *args, "--output", "json"]
    if region:
        command += ["--region", region]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise AwsCliError(f"{' '.join(command[:4])}…: {result.stderr.strip()}")
    if not parse or not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def load_lab_config(path: str | Path) -> dict[str, Any]:
    """Lee `terraform output -json lab_config` (acepta el objeto directo o con clave value)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("value", data) if isinstance(data, dict) else data


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_aws_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
