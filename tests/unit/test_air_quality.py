"""Contract tests for the optional Open-Meteo/CAMS adapter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from custom_components.ventwise.application import air_quality


class _Response:
    def __init__(self, payload: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.error = error

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    async def json(self) -> dict[str, object]:
        return self.payload


class _Session:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object], int]] = []

    def get(self, url: str, *, params: dict[str, object], timeout: int):
        self.calls.append((url, params, timeout))
        return self.response


def test_open_meteo_adapter_parses_current_values_and_metadata(monkeypatch) -> None:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    session = _Session(_Response({
        "current": {"time": "2026-11-09T11:00", "pm2_5": 12.5, "grass_pollen": 3},
        "current_units": {"pm2_5": "µg/m³", "grass_pollen": "grains/m³"},
    }))
    monkeypatch.setattr(air_quality, "async_get_clientsession", lambda _hass: session)
    hass = SimpleNamespace(config=SimpleNamespace(latitude=45.46, longitude=9.19))

    readings = asyncio.run(air_quality.async_fetch_open_meteo_exposure(hass, now))

    assert readings["pm2_5"].observation.value == 12.5
    assert readings["pm2_5"].observation.unit == "µg/m³"
    assert readings["pm2_5"].observation.source_id == "open_meteo_cams"
    assert readings["grass_pollen"].attribution == "Open-Meteo / CAMS"
    assert session.calls[0][1]["latitude"] == 45.46
    assert "pm2_5" in session.calls[0][1]["current"]


def test_open_meteo_adapter_fails_closed_on_http_error(monkeypatch) -> None:
    session = _Session(_Response(error=TimeoutError("timeout")))
    monkeypatch.setattr(air_quality, "async_get_clientsession", lambda _hass: session)
    hass = SimpleNamespace(config=SimpleNamespace(latitude=45.46, longitude=9.19))

    with pytest.raises(air_quality.ProviderUnavailableError):
        asyncio.run(air_quality.async_fetch_open_meteo_exposure(hass, datetime.now(timezone.utc)))


def test_open_meteo_adapter_does_not_request_without_home_assistant_location(monkeypatch) -> None:
    called = False

    def session(_hass):
        nonlocal called
        called = True
        return _Session(_Response())

    monkeypatch.setattr(air_quality, "async_get_clientsession", session)
    hass = SimpleNamespace(config=SimpleNamespace(latitude=None, longitude=None))

    assert asyncio.run(air_quality.async_fetch_open_meteo_exposure(hass, datetime.now(timezone.utc))) == {}
    assert called is False
