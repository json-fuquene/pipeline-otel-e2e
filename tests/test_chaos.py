"""Pruebas unitarias del controlador de caos (ID-003, RF-311–RF-313)."""
from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services.shared.chaos import ChaosConfig, ChaosConfigError, ChaosController, parse_config


def build_app(controller: ChaosController) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def chaos_middleware(request: Request, call_next):
        return await controller.middleware(request, call_next)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = "req-1"
        return await call_next(request)

    @app.get("/items")
    async def items():
        return {"ok": True}

    @app.get("/health/ready")
    async def ready():
        return {"status": "ready"}

    return app


def controller(env: dict[str, str], *, rng=lambda: 0.0, sleeps: list[float] | None = None):
    recorded = [] if sleeps is None else sleeps

    async def fake_sleep(seconds: float):
        recorded.append(seconds)

    return ChaosController("test", logging.getLogger("chaos-test"), env=env, rng=rng, sleep=fake_sleep)


def test_parse_config_validates_ranges():
    assert parse_config({"latency_ms": "200"}).latency_ms == 200
    assert parse_config({"error_rate": 0.1}).error_rate == pytest.approx(0.1)
    assert not parse_config({"enabled": False, "latency_ms": 200}).active
    for bad in ({"latency_ms": -1}, {"error_rate": 1.5}, {"error_rate": True}, {"latency_ms": "x"}):
        with pytest.raises(ChaosConfigError):
            parse_config(bad)


def test_inactive_without_source_passes_through():
    ctl = controller({})
    assert not ctl.config.active
    response = TestClient(build_app(ctl)).get("/items")
    assert response.status_code == 200


def test_latency_injection_from_env():
    sleeps: list[float] = []
    ctl = controller({"CHAOS_LATENCY_MS": "200"}, sleeps=sleeps)
    response = TestClient(build_app(ctl)).get("/items")
    assert response.status_code == 200
    assert sleeps == [0.2]


def test_error_injection_returns_503_with_code():
    ctl = controller({"CHAOS_ERROR_RATE": "0.1", "CHAOS_ERROR_DELAY_MS": "500"}, rng=lambda: 0.05)
    response = TestClient(build_app(ctl)).get("/items")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "chaos_injected",
            "message": "Falla inyectada por un experimento de caos controlado.",
        },
        "request_id": "req-1",
    }


def test_error_not_injected_above_rate():
    ctl = controller({"CHAOS_ERROR_RATE": "0.1"}, rng=lambda: 0.5)
    assert TestClient(build_app(ctl)).get("/items").status_code == 200


def test_health_routes_never_fail():
    ctl = controller({"CHAOS_ERROR_RATE": "1"}, rng=lambda: 0.0)
    assert TestClient(build_app(ctl)).get("/health/ready").status_code == 200


def test_ssm_refresh_changes_config_and_logs(caplog):
    values = iter(
        [
            json.dumps({"latency_ms": 0, "error_rate": 0}),
            json.dumps({"error_rate": 0.1, "error_delay_ms": 500, "experiment": "exp-2"}),
            "not-json",
        ]
    )
    ctl = ChaosController(
        "data-service",
        logging.getLogger("chaos-ssm"),
        env={"CHAOS_SSM_PARAMETER": "/lab/chaos/data-service"},
        ssm_reader=lambda name: next(values),
    )
    assert ctl.source == "ssm"
    with caplog.at_level(logging.WARNING, logger="chaos-ssm"):
        asyncio.run(ctl.refresh())
        assert not ctl.config.active
        asyncio.run(ctl.refresh())
        assert ctl.config == ChaosConfig(error_rate=0.1, error_delay_ms=500, experiment="exp-2")
        asyncio.run(ctl.refresh())  # lectura inválida: conserva la última configuración
        assert ctl.config.error_rate == pytest.approx(0.1)
    events = [json.loads(record.message)["event"] for record in caplog.records]
    assert events == ["chaos_config_changed", "chaos_config_unavailable"]
