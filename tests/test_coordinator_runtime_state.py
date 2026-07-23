"""Tests for coordinator runtime state persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_ENABLED,
    CONF_NOTIFICATION_ENABLED,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_HUMIDITY_SOURCE,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_SOURCE,
    CONF_RUNTIME_STATE,
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
    CONF_WIND_SPEED_ENTITY_ID,
    CONF_WIND_SPEED_SOURCE,
    CONF_ROOMS,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_TARGET_TEMPERATURE_C,
    CONF_STABILITY_MINUTES,
    OUTDOOR_SOURCE_OVERRIDE,
)
from custom_components.ventwise.coordinator import VentWiseCoordinator


class _FakeConfigEntries:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []
        self.reloaded: list[str] = []

    def async_update_entry(self, entry, options):
        self.updated.append(options)
        entry.options = options

    async def async_reload(self, entry_id: str) -> None:
        self.reloaded.append(entry_id)


class _FakeConfigEntry:
    def __init__(
        self,
        *,
        entry_id: str,
        data: dict[str, object],
        options: dict[str, object],
    ) -> None:
        self.entry_id = entry_id
        self.data = data
        self.options = options
        self.domain = "ventwise"
        self.title = "VentWise"
        self._unload_callbacks: list[object] = []

    def async_on_unload(self, callback) -> None:
        self._unload_callbacks.append(callback)


def _make_coordinator(options: dict[str, object] | None = None):
    hass = SimpleNamespace(
        config_entries=_FakeConfigEntries(),
        states=SimpleNamespace(get=lambda *_: None),
    )
    entry = _FakeConfigEntry(
        entry_id="abc123",
        data={},
        options=options or {},
    )
    coordinator = VentWiseCoordinator(hass, entry, {**entry.data, **entry.options})
    return coordinator, hass, entry


def test_coordinator_loads_persisted_runtime_state() -> None:
    started_at = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)
    notification_at = datetime(2026, 7, 21, 13, 5, tzinfo=timezone.utc)
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_RUNTIME_STATE: {
                CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Camera"],
                CONF_RUNTIME_LAST_ACTION_STARTED_AT: started_at.isoformat(),
                CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE: ["open", "Camera"],
                CONF_RUNTIME_LAST_NOTIFICATION_AT: notification_at.isoformat(),
            },
        }
    )

    assert coordinator._last_action_signature == ("open", "Camera")
    assert coordinator._last_action_started_at == started_at
    assert coordinator._last_notification_signature == ("open", "Camera")
    assert coordinator._last_notification_at == notification_at


def test_coordinator_persists_runtime_state_without_dropping_options() -> None:
    coordinator, hass, entry = _make_coordinator(
        {
            CONF_ENABLED: True,
            "custom_setting": "keep-me",
        }
    )
    timestamp = datetime(2026, 7, 21, 13, 15, tzinfo=timezone.utc)
    coordinator._last_action_signature = ("open", "Camera")
    coordinator._last_action_started_at = timestamp
    coordinator._last_notification_signature = ("open", "Camera")
    coordinator._last_notification_at = timestamp

    coordinator._persist_runtime_state()

    assert hass.config_entries.updated
    persisted = hass.config_entries.updated[-1]
    assert persisted[CONF_ENABLED] is True
    assert persisted["custom_setting"] == "keep-me"
    assert persisted[CONF_RUNTIME_STATE][CONF_RUNTIME_LAST_ACTION_SIGNATURE] == [
        "open",
        "Camera",
    ]
    assert persisted[CONF_RUNTIME_STATE][CONF_RUNTIME_LAST_ACTION_STARTED_AT] == timestamp.isoformat()
    assert entry.options == persisted


def test_coordinator_ignores_corrupted_runtime_state_payload() -> None:
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_RUNTIME_STATE: {
                CONF_RUNTIME_LAST_ACTION_SIGNATURE: "invalid",
                CONF_RUNTIME_LAST_ACTION_STARTED_AT: "not-a-timestamp",
                CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE: ["open", "Camera"],
                CONF_RUNTIME_LAST_NOTIFICATION_AT: "also-invalid",
            },
        }
    )

    assert coordinator._last_action_signature is None
    assert coordinator._last_action_started_at is not None
    assert coordinator._last_notification_signature == ("open", "Camera")
    assert coordinator._last_notification_at is not None


def test_coordinator_tracks_source_entities_for_event_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_track_state_change_event(hass, entity_ids, callback):
        captured["entity_ids"] = list(entity_ids)
        captured["callback"] = callback
        return lambda: captured.setdefault("state_unsubscribed", True)

    from custom_components.ventwise import coordinator as coordinator_module

    monkeypatch.setattr(
        coordinator_module,
        "async_track_state_change_event",
        _fake_track_state_change_event,
    )

    coordinator, _, _ = _make_coordinator(
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_OUTDOOR_TEMPERATURE_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_OUTDOOR_TEMPERATURE_ENTITY_ID: "sensor.outdoor_temp",
            CONF_OUTDOOR_HUMIDITY_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_OUTDOOR_HUMIDITY_ENTITY_ID: "sensor.outdoor_humidity",
            CONF_WIND_SPEED_SOURCE: OUTDOOR_SOURCE_OVERRIDE,
            CONF_WIND_SPEED_ENTITY_ID: "sensor.wind_speed",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                }
            ],
        }
    )

    coordinator._refresh_state_listeners()

    assert captured["entity_ids"] == [
        "sensor.outdoor_humidity",
        "sensor.outdoor_temp",
        "sensor.room_humidity",
        "sensor.room_temp",
        "sensor.wind_speed",
        "weather.home",
    ]


def test_coordinator_schedules_next_time_refresh_after_stability_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_track_point_in_time(hass, callback, point_in_time):
        captured["point_in_time"] = point_in_time
        captured["callback"] = callback
        return lambda: captured.setdefault("time_unsubscribed", True)

    from custom_components.ventwise import coordinator as coordinator_module

    monkeypatch.setattr(
        coordinator_module,
        "async_track_point_in_time",
        _fake_track_point_in_time,
    )

    coordinator, _, _ = _make_coordinator(
        {
            CONF_STABILITY_MINUTES: 10,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                }
            ],
        }
    )
    coordinator._listeners_initialized = True
    fixed_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    coordinator._last_action_started_at = fixed_now
    snapshot = SimpleNamespace(stable_for_seconds=0, cooldown_active=False)

    coordinator._refresh_time_listener(fixed_now, snapshot)

    assert captured["point_in_time"] == fixed_now + timedelta(minutes=10)


@pytest.mark.asyncio
async def test_coordinator_keeps_recommendation_active_during_notification_cooldown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    from custom_components.ventwise import coordinator as coordinator_module

    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: fixed_now)
    monkeypatch.setattr(coordinator_module.dt_util, "now", lambda: fixed_now)

    fake_states = {
        "weather.home": SimpleNamespace(
            state="sunny",
            attributes={"temperature": 20.0, "humidity": 50.0, "wind_speed": 1.0},
        ),
        "sensor.room_temp": SimpleNamespace(state="28.0"),
        "sensor.room_humidity": SimpleNamespace(state="55.0"),
    }
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_STABILITY_MINUTES: 10,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_humidity",
                }
            ],
        }
    )
    coordinator.hass.states = SimpleNamespace(get=fake_states.get)
    coordinator._last_action_signature = ("open", "Camera")
    coordinator._last_action_started_at = fixed_now - timedelta(minutes=15)
    coordinator._last_notification_signature = ("open", "Camera")
    coordinator._last_notification_at = fixed_now - timedelta(minutes=1)

    snapshot = await coordinator._async_update_data()

    assert snapshot.summary.action.value == "open"
    assert snapshot.notification_allowed is False
    assert snapshot.cooldown_active is True
    assert snapshot.weather_condition == "sunny"
