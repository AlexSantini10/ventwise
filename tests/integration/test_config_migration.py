"""Tests for persisted VentWise configuration migrations."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.ventwise import async_migrate_entry
from custom_components.ventwise.config_flow import VentWiseConfigFlow
from custom_components.ventwise.const import (
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
    CONF_RUNTIME_STATE,
    DEFAULT_TEMPERATURE_UNIT,
    DEFAULT_WIND_SPEED_UNIT,
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


def test_config_flow_version_matches_migration_target() -> None:
    assert VentWiseConfigFlow.VERSION == 6


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
    assert entry.version == 6
    assert entry.data == {
        "target_temperature_c": 21.0,
        CONF_NOTIFICATION_DEVICE_ID: ["device-alice", "device-bob"],
    }
    assert entry.options["target_temperature_c"] == 22.0
    assert entry.options[CONF_RUNTIME_STATE] == {
        CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Bedroom"],
        CONF_RUNTIME_LAST_NOTIFICATION_AT: "2026-09-05T10:15:00+00:00",
    }


def test_migration_removes_retired_smoke_setting_and_preserves_other_data() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=3,
        data={"smoke_alert_entity_id": "binary_sensor.fire", "unknown_data": "kept"},
        options={"smoke_alert_entity_id": "binary_sensor.smoke", "unknown_option": True},
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert entry.version == 6
    assert entry.data == {"unknown_data": "kept"}
    assert entry.options == {
        "unknown_option": True,
        "temperature_unit": DEFAULT_TEMPERATURE_UNIT,
        "wind_speed_unit": DEFAULT_WIND_SPEED_UNIT,
        "urgent_close_during_quiet_hours": False,
    }


def test_migration_is_idempotent_for_current_entry() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(version=6, data={"kept": True}, options={"also_kept": True})

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert hass.config_entries.updates == []


def test_migration_rejects_a_future_entry_version(caplog: pytest.LogCaptureFixture) -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(version=7, data={}, options={})

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
    assert entry.version == 6
    assert entry.data == {"legacy_data": "kept"}
    assert entry.options[CONF_RUNTIME_STATE] == {"future_marker": "kept"}
    assert entry.options["future_option"] is True


def test_migration_removes_retired_room_inputs_from_data_and_options() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=4,
        data={"rooms": [{"name": "Study", "hvac_entity_id": "climate.study", "kept": True}]},
        options={"rooms": [{"name": "Bedroom", "radiation_entity_id": "sensor.sun", "unknown": "kept"}]},
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    assert entry.version == 6
    assert entry.data["rooms"] == [{"name": "Study", "kept": True}]
    assert entry.options["rooms"] == [{"name": "Bedroom", "unknown": "kept"}]


def test_migration_converts_legacy_window_contacts_without_inversion() -> None:
    hass = SimpleNamespace(config_entries=_FakeConfigEntries())
    entry = _entry(
        version=5,
        data={
            "rooms": [{
                "name": "Study",
                "window_sensor_entity_ids": [
                    "binary_sensor.left",
                    "binary_sensor.right",
                ],
                "temperature_entity_id": "sensor.study",
            }]
        },
        options={},
    )

    assert asyncio.run(async_migrate_entry(hass, entry)) is True
    room = entry.data["rooms"][0]
    assert room["window_contacts"] == [
        {"entity_id": "binary_sensor.left", "invert": False},
        {"entity_id": "binary_sensor.right", "invert": False},
    ]
    assert "window_sensor_entity_ids" not in room
    assert room["temperature_entity_id"] == "sensor.study"
