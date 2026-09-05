"""Tests for persisted VentWise configuration migrations."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise import async_migrate_entry
from custom_components.ventwise.const import (
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
    CONF_RUNTIME_STATE,
)


class _FakeConfigEntries:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def async_update_entry(self, entry, **kwargs) -> None:
        self.updates.append(kwargs)
        for key, value in kwargs.items():
            setattr(entry, key, value)


def _entry(*, version: int, data: dict[str, object], options: dict[str, object]):
    return SimpleNamespace(
        entry_id="migration-test",
        version=version,
        data=data,
        options=options,
    )


def test_migration_preserves_settings_and_nests_legacy_runtime_state() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=1,
        data={
            "target_temperature_c": 21.0,
            CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Bedroom"],
        },
        options={
            "target_temperature_c": 22.0,
            CONF_RUNTIME_LAST_NOTIFICATION_AT: "2026-09-05T10:15:00+00:00",
        },
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert entry.version == 2
    assert entry.data == {}
    assert entry.options["target_temperature_c"] == 22.0
    assert entry.options[CONF_RUNTIME_STATE] == {
        CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Bedroom"],
        CONF_RUNTIME_LAST_NOTIFICATION_AT: "2026-09-05T10:15:00+00:00",
    }


def test_migration_rejects_a_future_entry_version(caplog: pytest.LogCaptureFixture) -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(version=3, data={}, options={})

    assert asyncio.run(async_migrate_entry(hass, entry)) is False
    assert hass.config_entries.updates == []
    assert "unsupported future version" in caplog.text
