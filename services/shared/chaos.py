"""Inyección controlada de latencia y errores para experimentos de caos (ID-003, fase 4).

La configuración se lee de una de dos fuentes, nunca de ambas:

* Variables de entorno ``CHAOS_LATENCY_MS``, ``CHAOS_ERROR_RATE`` y ``CHAOS_ERROR_DELAY_MS``
  (uso local con Compose; el valor se fija al arrancar).
* Un parámetro JSON de AWS SSM Parameter Store indicado en ``CHAOS_SSM_PARAMETER``; se consulta
  cada ``CHAOS_POLL_SECONDS`` segundos, de modo que un experimento empieza y termina sin redesplegar.

Sin fuente configurada el controlador queda inactivo y el middleware delega la solicitud sin
costo adicional. Las rutas de salud y métricas nunca reciben fallas.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from opentelemetry.trace import get_current_span

MAX_DELAY_MS = 10_000
EXCLUDED_PREFIXES = ("/health/", "/metrics", "/docs", "/openapi.json")


class ChaosConfigError(ValueError):
    """La configuración de caos no es válida."""


@dataclass(frozen=True)
class ChaosConfig:
    latency_ms: int = 0
    error_rate: float = 0.0
    error_delay_ms: int = 0
    experiment: str | None = None

    @property
    def active(self) -> bool:
        return self.latency_ms > 0 or self.error_rate > 0


INACTIVE = ChaosConfig()


def _as_int(value: object, name: str) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        raise ChaosConfigError(f"{name} no es válido.")
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ChaosConfigError(f"{name} no es válido.") from error
    if not 0 <= number <= MAX_DELAY_MS:
        raise ChaosConfigError(f"{name} debe estar entre 0 y {MAX_DELAY_MS}.")
    return number


def _as_rate(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        raise ChaosConfigError("error_rate no es válido.")
    try:
        rate = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ChaosConfigError("error_rate no es válido.") from error
    if not 0.0 <= rate <= 1.0:
        raise ChaosConfigError("error_rate debe estar entre 0 y 1.")
    return rate


def parse_config(raw: Mapping[str, object]) -> ChaosConfig:
    """Valida un diccionario con las claves ``latency_ms``, ``error_rate`` y ``error_delay_ms``."""
    experiment = raw.get("experiment")
    if experiment is not None and (not isinstance(experiment, str) or len(experiment) > 64):
        raise ChaosConfigError("experiment no es válido.")
    if raw.get("enabled") is False:
        return ChaosConfig(experiment=experiment or None)
    return ChaosConfig(
        latency_ms=_as_int(raw.get("latency_ms"), "latency_ms"),
        error_rate=_as_rate(raw.get("error_rate")),
        error_delay_ms=_as_int(raw.get("error_delay_ms"), "error_delay_ms"),
        experiment=experiment or None,
    )


def config_from_env(env: Mapping[str, str]) -> ChaosConfig:
    return parse_config(
        {
            "latency_ms": env.get("CHAOS_LATENCY_MS"),
            "error_rate": env.get("CHAOS_ERROR_RATE"),
            "error_delay_ms": env.get("CHAOS_ERROR_DELAY_MS"),
            "experiment": env.get("CHAOS_EXPERIMENT") or None,
        }
    )


class ChaosController:
    """Mantiene la configuración vigente y aplica las fallas en el middleware HTTP."""

    def __init__(
        self,
        service: str,
        logger: logging.Logger,
        *,
        env: Mapping[str, str] | None = None,
        ssm_reader: Callable[[str], str] | None = None,
        rng: Callable[[], float] = random.random,
        sleep: Callable[[float], object] = asyncio.sleep,
    ) -> None:
        env = os.environ if env is None else env
        self.service = service
        self.logger = logger
        self.parameter = (env.get("CHAOS_SSM_PARAMETER") or "").strip() or None
        self.poll_seconds = max(2.0, float(env.get("CHAOS_POLL_SECONDS", "5")))
        self._ssm_reader = ssm_reader
        self._rng = rng
        self._sleep = sleep
        self._task: asyncio.Task | None = None
        self._last_read_error: str | None = None
        self.config = INACTIVE if self.parameter else config_from_env(env)
        if self.config.active:
            self._log_change(INACTIVE, self.config, source="env")

    @property
    def source(self) -> str:
        return "ssm" if self.parameter else "env"

    async def start(self) -> None:
        if self.parameter and self._task is None:
            await self.refresh()
            self._task = asyncio.create_task(self._poll(), name=f"chaos-poll-{self.service}")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def refresh(self) -> None:
        if not self.parameter:
            return
        try:
            raw = await asyncio.to_thread(self._read_parameter, self.parameter)
            new_config = parse_config(json.loads(raw))
        except Exception as error:  # noqa: BLE001 - la falla de lectura no debe tumbar la API
            message = type(error).__name__
            if message != self._last_read_error:
                self._last_read_error = message
                self._emit("chaos_config_unavailable", error_type=message)
            return
        self._last_read_error = None
        if new_config != self.config:
            previous, self.config = self.config, new_config
            self._log_change(previous, new_config, source="ssm")

    async def _poll(self) -> None:
        while True:
            await asyncio.sleep(self.poll_seconds)
            await self.refresh()

    def _read_parameter(self, name: str) -> str:
        if self._ssm_reader is not None:
            return self._ssm_reader(name)
        import boto3  # importación diferida: solo se requiere con SSM

        client = boto3.client("ssm")
        return client.get_parameter(Name=name)["Parameter"]["Value"]

    def _emit(self, event: str, **fields: object) -> None:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": "WARNING",
            "service": self.service,
            "event": event,
            **fields,
        }
        self.logger.warning(json.dumps(payload, separators=(",", ":")))

    def _log_change(self, previous: ChaosConfig, current: ChaosConfig, *, source: str) -> None:
        self._emit(
            "chaos_config_changed",
            source=source,
            active=current.active,
            previous=asdict(previous),
            current=asdict(current),
        )

    async def middleware(self, request: Request, call_next):
        config = self.config
        path = request.url.path
        if not config.active or path.startswith(EXCLUDED_PREFIXES):
            return await call_next(request)

        span = get_current_span()
        if config.experiment and span.is_recording():
            span.set_attribute("chaos.experiment", config.experiment)
        if config.latency_ms:
            await self._sleep(config.latency_ms / 1000)
            if span.is_recording():
                span.add_event("chaos.latency_injected", {"chaos.latency_ms": config.latency_ms})

        if config.error_rate and self._rng() < config.error_rate:
            if config.error_delay_ms:
                await self._sleep(config.error_delay_ms / 1000)
            if span.is_recording():
                span.set_attribute("chaos.injected", True)
                span.add_event(
                    "chaos.error_injected",
                    {"chaos.error_rate": config.error_rate, "chaos.error_delay_ms": config.error_delay_ms},
                )
            request_id = getattr(request.state, "request_id", "")
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "chaos_injected",
                        "message": "Falla inyectada por un experimento de caos controlado.",
                    },
                    "request_id": request_id,
                },
            )
        return await call_next(request)
