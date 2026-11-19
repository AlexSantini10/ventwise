"""Tests for persisted VentWise configuration migrations."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.ventwise import async_migrate_entry
from custom_components.ventwise.const import (
    CONF_CO2_ENABLED,
    CONF_CO2_ENTITY_ID,
    CONF_ROOM_CO2_ENABLED,
    CONF_ROOM_CO2_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOMS,
    CONF_SAFETY_BYPASS_QUIET_HOURS,
    CONF_NOTIFICATION_DEVICE_ID,
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


def test_migration_preserves_settings_and_notification_devices() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=1,
        data={
            "target_temperature_c": 21.0,
            CONF_NOTIFICATION_DEVICE_ID: ["device-alice", "device-bob"],
            CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Bedroom"],
        },
        options={
            "target_temperature_c": 22.0,
            CONF_RUNTIME_LAST_NOTIFICATION_AT: "2026-09-05T10:15:00+00:00",
        },
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert entry.version == 5
    assert entry.data == {
        "target_temperature_c": 21.0,
        CONF_NOTIFICATION_DEVICE_ID: ["device-alice", "device-bob"],
    }
    assert entry.options["target_temperature_c"] == 22.0
    assert entry.options[CONF_RUNTIME_STATE] == {
        CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Bedroom"],
        CONF_RUNTIME_LAST_NOTIFICATION_AT: "2026-09-05T10:15:00+00:00",
    }
    assert entry.options[CONF_SAFETY_BYPASS_QUIET_HOURS] is False


def test_migration_rejects_a_future_entry_version(caplog: pytest.LogCaptureFixture) -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(version=6, data={}, options={})

    assert asyncio.run(async_migrate_entry(hass, entry)) is False
    assert hass.config_entries.updates == []
    assert "unsupported future version" in caplog.text


def test_migration_keeps_current_runtime_state_and_unknown_option_data() -> None:
    """Version-two entries remain usable even when optional legacy data is sparse."""

    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=2,
        data={"legacy_data": "kept"},
        options={CONF_RUNTIME_STATE: {"future_marker": "kept"}, "future_option": True},
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert entry.version == 5
    assert entry.data == {"legacy_data": "kept"}
    assert entry.options[CONF_RUNTIME_STATE] == {"future_marker": "kept"}
    assert entry.options["future_option"] is True
    assert entry.options[CONF_SAFETY_BYPASS_QUIET_HOURS] is False


def test_migration_moves_legacy_global_co2_to_each_room() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=4,
        data={},
        options={
            CONF_CO2_ENABLED: True,
            CONF_CO2_ENTITY_ID: "sensor.home_co2",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Bedroom",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.bedroom_temperature",
                },
                {
                    CONF_ROOM_NAME: "Study",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.study_temperature",
                    CONF_ROOM_CO2_ENTITY_ID: "sensor.study_co2",
                },
            ],
        },
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    rooms = entry.options[CONF_ROOMS]
    assert rooms[0][CONF_ROOM_CO2_ENTITY_ID] == "sensor.home_co2"
    assert rooms[0][CONF_ROOM_CO2_ENABLED] is True
    assert rooms[1][CONF_ROOM_CO2_ENTITY_ID] == "sensor.study_co2"
    assert rooms[1][CONF_ROOM_CO2_ENABLED] is True
    assert CONF_CO2_ENABLED not in entry.options
    assert CONF_CO2_ENTITY_ID not in entry.options
