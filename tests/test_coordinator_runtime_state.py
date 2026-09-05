"""Tests for coordinator runtime state persistence."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_COOLDOWN_MINUTES,
    CONF_ENABLED,
    CONF_NOTIFICATION_ENABLED,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED,
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
    CONF_RUNTIME_NOTIFICATION_MARKERS,
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
from custom_components.ventwise.coordinator import VentWiseCoordinator, _first_forecast_temperature
from custom_components.ventwise.runtime import NotificationMarker, RoomActionGuard, RoomConfig
from custom_components.ventwise.ventwise_core import RecommendationAction
from custom_components.ventwise.ventwise_core.models import RoomRecommendation


class _FakeConfigEntries:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []
        self.reloaded: list[str] = []

    def async_update_entry(self, entry, options):
        self.updated.append(options)
        entry.options = options

    async def async_reload(self, entry_id: str) -> None:
        self.reloaded.append(entry_id)


class _FakeServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object], dict[str, object] | None]] = []

    async def async_call(self, domain, service, service_data, *, target=None, blocking=False):
        self.calls.append((domain, service, service_data, target))


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
        services=_FakeServices(),
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
    assert coordinator._notification_markers == {
        "Camera": NotificationMarker(("open", "Camera"), notification_at)
    }


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
    coordinator._notification_markers = {
        "Camera": NotificationMarker(("open", "Camera"), timestamp)
    }

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
    assert persisted[CONF_RUNTIME_STATE][CONF_RUNTIME_NOTIFICATION_MARKERS] == {
        "Camera": {
            "signature": ["open", "Camera"],
            "notified_at": timestamp.isoformat(),
        }
    }
    assert entry.options == persisted


def test_coordinator_persists_notification_reason_and_severity() -> None:
    coordinator, hass, _ = _make_coordinator({CONF_ENABLED: True})
    timestamp = datetime(2026, 7, 21, 13, 15, tzinfo=timezone.utc)
    coordinator._notification_markers = {
        "Camera": NotificationMarker(
            ("open", "Camera"),
            timestamp,
            "Outside is more comfortable.",
            "urgent",
        )
    }

    coordinator._persist_runtime_state()

    marker = hass.config_entries.updated[-1][CONF_RUNTIME_STATE][
        CONF_RUNTIME_NOTIFICATION_MARKERS
    ]["Camera"]
    assert marker["reason"] == "Outside is more comfortable."
    assert marker["severity"] == "urgent"


def test_room_action_guard_holds_reversals_and_survives_restart() -> None:
    """A room cannot flip from open to close until its own guards permit it."""

    coordinator, hass, entry = _make_coordinator({CONF_ENABLED: True})
    room = RoomConfig(
        room_id="bedroom-1",
        name="Bedroom",
        temperature_entity_id="sensor.bedroom_temperature",
        action_change_hold_minutes=5,
        action_lockout_minutes=30,
    )
    started_at = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)
    open_recommendation = RoomRecommendation(
        "Bedroom", RecommendationAction.OPEN, 0.5, "Fresh air helps.", 22.0, 25.0, 20.0, 22.0,
        room_id="bedroom-1",
    )
    close_recommendation = RoomRecommendation(
        "Bedroom", RecommendationAction.CLOSE, 0.5, "Keep the room closed.", 22.0, 25.0, 30.0, 22.0,
        room_id="bedroom-1",
    )

    assert coordinator._guard_room_recommendation(open_recommendation, room, started_at).action == RecommendationAction.OPEN
    assert coordinator._guard_room_recommendation(
        close_recommendation, room, started_at + timedelta(minutes=1)
    ).action == RecommendationAction.NONE
    assert coordinator._guard_room_recommendation(
        close_recommendation, room, started_at + timedelta(minutes=31)
    ).action == RecommendationAction.NONE
    assert coordinator._guard_room_recommendation(
        close_recommendation, room, started_at + timedelta(minutes=36)
    ).action == RecommendationAction.CLOSE

    coordinator._persist_runtime_state()
    restored = _FakeConfigEntry(entry_id="abc123", data={}, options=hass.config_entries.updated[-1])
    restarted = VentWiseCoordinator(
        SimpleNamespace(config_entries=_FakeConfigEntries(), states=SimpleNamespace(get=lambda *_: None)),
        restored,
        restored.options,
    )
    assert restarted._room_action_guards["bedroom-1"].accepted_action == "close"


def test_urgent_close_bypasses_room_action_guard() -> None:
    coordinator, _, _ = _make_coordinator({CONF_ENABLED: True})
    room = RoomConfig(None, "Bedroom", "sensor.bedroom_temperature")
    now = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)
    coordinator._room_action_guards["Bedroom"] = RoomActionGuard(
        "open", lockout_until=now + timedelta(minutes=30)
    )
    urgent_close = RoomRecommendation(
        "Bedroom", RecommendationAction.CLOSE, 0.8, "Storm incoming.", 22.0, 25.0, 20.0, 22.0
    )

    assert coordinator._guard_room_recommendation(urgent_close, room, now).action == RecommendationAction.CLOSE


def test_short_term_forecast_uses_the_nearest_upcoming_temperature() -> None:
    now = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)

    temperature = _first_forecast_temperature(
        [
            {"datetime": "2026-07-21T12:00:00+00:00", "temperature": 19.0},
            {"datetime": "2026-07-21T15:00:00+00:00", "temperature": 28.0},
            {"datetime": "2026-07-21T14:00:00+00:00", "temperature": 26.0},
        ],
        now,
    )

    assert temperature == 26.0


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
    assert coordinator._notification_markers == {}


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


def test_coordinator_keeps_recommendation_active_during_notification_cooldown(
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
    initial_snapshot = asyncio.run(coordinator._async_update_data())
    recommendation = initial_snapshot.summary.room_recommendations[0]
    coordinator._notification_markers = {
        "Camera": NotificationMarker(
            coordinator._notification_identity(recommendation),
            fixed_now - timedelta(minutes=1),
            recommendation.reason_code,
            coordinator._notification_severity(recommendation.score),
        )
    }

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.summary.action.value == "open"
    assert snapshot.notification_allowed is False
    assert snapshot.cooldown_active is True
    assert snapshot.weather_condition == "sunny"


def test_coordinator_applies_cooldown_independently_per_room(
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
        "sensor.camera_temp": SimpleNamespace(state="28.0"),
        "sensor.living_temp": SimpleNamespace(state="28.0"),
    }
    coordinator, hass, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
            CONF_COOLDOWN_MINUTES: 60,
            CONF_STABILITY_MINUTES: 0,
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.camera_temp",
                },
                {
                    CONF_ROOM_NAME: "Salotto",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                },
            ],
        }
    )
    coordinator.hass.states = SimpleNamespace(get=fake_states.get)
    initial_snapshot = asyncio.run(coordinator._async_update_data())
    camera_recommendation = next(
        recommendation
        for recommendation in initial_snapshot.summary.room_recommendations
        if recommendation.room_name == "Camera"
    )
    coordinator._notification_markers = {
        "Camera": NotificationMarker(
            coordinator._notification_identity(camera_recommendation),
            fixed_now - timedelta(minutes=1),
            camera_recommendation.reason_code,
            coordinator._notification_severity(camera_recommendation.score),
        )
    }
    hass.services.calls.clear()

    living_snapshot = asyncio.run(coordinator._async_update_data())

    assert living_snapshot.summary.best_room == "Camera"
    assert living_snapshot.notification_allowed is True
    assert len(hass.services.calls) == 1
    assert hass.services.calls[0][2]["notification_id"] == "ventwise_recommendation_salotto_20260723t120000000000"

    camera_snapshot = asyncio.run(coordinator._async_update_data())

    assert camera_snapshot.summary.best_room == "Camera"
    assert camera_snapshot.cooldown_active is True
    assert camera_snapshot.notification_allowed is False
    assert len(hass.services.calls) == 1


def test_coordinator_repeats_equivalent_notification_after_cooldown_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_now = [datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)]
    from custom_components.ventwise import coordinator as coordinator_module

    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: current_now[0])
    monkeypatch.setattr(coordinator_module.dt_util, "now", lambda: current_now[0])
    fake_states = {
        "weather.home": SimpleNamespace(
            state="sunny",
            attributes={"temperature": 20.0, "humidity": 50.0, "wind_speed": 1.0},
        ),
        "sensor.room_temp": SimpleNamespace(state="28.0"),
    }
    coordinator, hass, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
            CONF_COOLDOWN_MINUTES: 60,
            CONF_STABILITY_MINUTES: 0,
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_temp",
                }
            ],
        }
    )
    coordinator.hass.states = SimpleNamespace(get=fake_states.get)

    first_snapshot = asyncio.run(coordinator._async_update_data())
    first_marker = coordinator._notification_markers["Camera"]
    coordinator._notification_markers["Camera"] = NotificationMarker(
        first_marker.signature,
        first_marker.notified_at,
        "wind",
        first_marker.severity,
    )
    suppressed_snapshot = asyncio.run(coordinator._async_update_data())
    current_now[0] += timedelta(minutes=61)
    second_snapshot = asyncio.run(coordinator._async_update_data())

    assert first_snapshot.notification_allowed is True
    assert suppressed_snapshot.notification_allowed is False
    assert suppressed_snapshot.cooldown_active is True
    assert second_snapshot.notification_allowed is True
    assert len(hass.services.calls) == 2
    assert hass.services.calls[0][2]["notification_id"] != hass.services.calls[1][2]["notification_id"]


def test_notification_marker_detects_action_reason_and_severity_changes() -> None:
    marker = NotificationMarker(
        ("open", "Camera"),
        datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        "comfort",
        "normal",
    )
    equivalent = RoomRecommendation(
        room_name="Camera",
        action=RecommendationAction.OPEN,
        score=0.5,
        reason="Outside is more comfortable.",
        target_perceived_c=22.0,
        indoor_perceived_c=26.0,
        outdoor_perceived_c=20.0,
        suggested_comfort_temperature_c=22.0,
    )

    assert VentWiseCoordinator._matches_notification_marker(
        SimpleNamespace(
            _notification_identity=VentWiseCoordinator._notification_identity,
            _notification_severity=VentWiseCoordinator._notification_severity,
        ),
        marker,
        equivalent,
    )
    assert VentWiseCoordinator._matches_notification_marker(
        SimpleNamespace(
            _notification_identity=VentWiseCoordinator._notification_identity,
            _notification_severity=VentWiseCoordinator._notification_severity,
        ),
        marker,
        RoomRecommendation(
            room_name="Camera",
            action=RecommendationAction.OPEN,
            score=0.5,
            reason="Outside is 2.1°C closer to comfort.",
            target_perceived_c=22.0,
            indoor_perceived_c=26.0,
            outdoor_perceived_c=20.0,
            suggested_comfort_temperature_c=22.0,
        ),
    )

    assert not VentWiseCoordinator._matches_notification_marker(
        SimpleNamespace(
            _notification_identity=VentWiseCoordinator._notification_identity,
            _notification_severity=VentWiseCoordinator._notification_severity,
        ),
        marker,
        RoomRecommendation(
            room_name="Camera",
            action=RecommendationAction.CLOSE,
            score=0.5,
            reason="Outside is more comfortable.",
            target_perceived_c=22.0,
            indoor_perceived_c=26.0,
            outdoor_perceived_c=20.0,
            suggested_comfort_temperature_c=22.0,
        ),
    )


def test_notification_cooldown_bypass_is_limited_to_actions_and_urgency() -> None:
    coordinator = SimpleNamespace(
        _notification_identity=VentWiseCoordinator._notification_identity,
        _notification_severity=VentWiseCoordinator._notification_severity,
    )
    marker = NotificationMarker(
        ("open", "Camera"),
        datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc),
        "comfort",
        "normal",
    )

    def recommendation(
        *,
        action: RecommendationAction = RecommendationAction.OPEN,
        score: float = 0.5,
        reason_code: str = "comfort",
    ) -> RoomRecommendation:
        return RoomRecommendation(
            room_name="Camera",
            action=action,
            score=score,
            reason="Human-readable explanation.",
            target_perceived_c=22.0,
            indoor_perceived_c=26.0,
            outdoor_perceived_c=20.0,
            suggested_comfort_temperature_c=22.0,
            reason_code=reason_code,
        )

    assert not VentWiseCoordinator._should_bypass_notification_cooldown(
        coordinator,
        marker,
        recommendation(),
    )
    assert not VentWiseCoordinator._should_bypass_notification_cooldown(
        coordinator,
        marker,
        recommendation(reason_code="wind"),
    )
    assert VentWiseCoordinator._should_bypass_notification_cooldown(
        coordinator,
        marker,
        recommendation(action=RecommendationAction.CLOSE),
    )
    assert VentWiseCoordinator._should_bypass_notification_cooldown(
        coordinator,
        marker,
        recommendation(score=0.8),
    )
    assert not VentWiseCoordinator._matches_notification_marker(
        SimpleNamespace(
            _notification_identity=VentWiseCoordinator._notification_identity,
            _notification_severity=VentWiseCoordinator._notification_severity,
        ),
        marker,
        RoomRecommendation(
            room_name="Camera",
            action=RecommendationAction.OPEN,
            score=0.5,
            reason="Indoor humidity is too high.",
            target_perceived_c=22.0,
            indoor_perceived_c=26.0,
            outdoor_perceived_c=20.0,
            suggested_comfort_temperature_c=22.0,
            reason_code="humidity",
        ),
    )
    assert not VentWiseCoordinator._matches_notification_marker(
        SimpleNamespace(
            _notification_identity=VentWiseCoordinator._notification_identity,
            _notification_severity=VentWiseCoordinator._notification_severity,
        ),
        marker,
        RoomRecommendation(
            room_name="Camera",
            action=RecommendationAction.OPEN,
            score=0.8,
            reason="Outside is more comfortable.",
            target_perceived_c=22.0,
            indoor_perceived_c=26.0,
            outdoor_perceived_c=20.0,
            suggested_comfort_temperature_c=22.0,
        ),
    )


def test_coordinator_notifies_each_eligible_room(
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
        "sensor.camera_temp": SimpleNamespace(state="28.0"),
        "sensor.living_temp": SimpleNamespace(state="28.0"),
    }
    coordinator, hass, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
            CONF_STABILITY_MINUTES: 0,
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.camera_temp",
                },
                {
                    CONF_ROOM_NAME: "Salotto",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                },
            ],
        }
    )
    coordinator.hass.states = SimpleNamespace(get=fake_states.get)

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.notification_allowed is True
    assert len(hass.services.calls) == 2
    assert {call[2]["notification_id"] for call in hass.services.calls} == {
        "ventwise_recommendation_camera_20260723t120000000000",
        "ventwise_recommendation_salotto_20260723t120000000000",
    }
    assert {call[2]["title"] for call in hass.services.calls} == {
        "VentWise · Camera",
        "VentWise · Salotto",
    }


def test_coordinator_sends_notification_to_selected_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    from custom_components.ventwise import coordinator as coordinator_module

    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: fixed_now)
    monkeypatch.setattr(coordinator_module.dt_util, "now", lambda: fixed_now)
    monkeypatch.setattr(
        coordinator_module,
        "notification_entity_ids_for_device_ids",
        lambda _hass, _device_ids: ("notify.mobile_app_alice", "notify.mobile_app_bob"),
    )

    fake_states = {
        "weather.home": SimpleNamespace(
            state="sunny",
            attributes={"temperature": 20.0, "humidity": 50.0, "wind_speed": 1.0},
        ),
        "sensor.room_temp": SimpleNamespace(state="28.0"),
        "sensor.room_humidity": SimpleNamespace(state="55.0"),
    }
    coordinator, hass, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_NOTIFICATION_DEVICE_ID: ["device-1"],
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
    coordinator._notification_markers = {}

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.notification_allowed is True
    assert len(hass.services.calls) == 2
    assert hass.services.calls[0][0] == "notify"
    assert hass.services.calls[0][1] == "send_message"
    assert hass.services.calls[0][2]["title"] == "VentWise · Camera"
    assert hass.services.calls[0][2]["message"].startswith("open windows.")
    assert "Outside is more comfortable" in hass.services.calls[0][2]["message"] or "Fuori è più confortevole" in hass.services.calls[0][2]["message"]
    assert hass.services.calls[0][3] == {"entity_id": "notify.mobile_app_alice"}
    assert hass.services.calls[1][3] == {"entity_id": "notify.mobile_app_bob"}


def test_coordinator_sends_notification_to_home_assistant_when_selected(
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
    coordinator, hass, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
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
    coordinator._notification_markers = {}

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.notification_allowed is True
    assert len(hass.services.calls) == 1
    assert hass.services.calls[0][0:2] == ("persistent_notification", "create")
    assert hass.services.calls[0][2]["notification_id"] == "ventwise_recommendation_camera_20260723t120000000000"


def test_coordinator_uses_automatic_comfort_temperature_when_enabled(
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
        "sensor.room_humidity": SimpleNamespace(state="50.0"),
    }
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_AUTO_COMFORT_TEMPERATURE: True,
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

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.target_perceived_c == pytest.approx(22.0)
    assert snapshot.suggested_comfort_temperature_c == pytest.approx(22.0)
    assert snapshot.summary.action.value == "open"


def test_coordinator_keeps_global_outdoor_values_without_rooms(
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
    }
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
        }
    )
    coordinator.hass.states = SimpleNamespace(get=fake_states.get)

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.summary.reason == "No enabled rooms configured."
    assert snapshot.outdoor_temperature_c == 20.0
    assert snapshot.outdoor_humidity_percent == 50.0
    assert snapshot.wind_speed_m_s == 1.0


def test_coordinator_logs_unavailable_required_data_once_and_recovery(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    from custom_components.ventwise import coordinator as coordinator_module

    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: fixed_now)
    monkeypatch.setattr(coordinator_module.dt_util, "now", lambda: fixed_now)
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Bedroom",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.bedroom_temperature",
                }
            ],
        }
    )
    states: dict[str, object] = {}
    coordinator.hass.states = SimpleNamespace(get=states.get)

    with caplog.at_level("INFO"):
        asyncio.run(coordinator._async_update_data())
        asyncio.run(coordinator._async_update_data())
        states.update(
            {
                "weather.home": SimpleNamespace(
                    state="sunny",
                    attributes={"temperature": 20.0, "humidity": 50.0, "wind_speed": 1.0},
                ),
                "sensor.bedroom_temperature": SimpleNamespace(state="24.0"),
            }
        )
        asyncio.run(coordinator._async_update_data())

    assert caplog.text.count("required weather or room sensor data is unavailable") == 1
    assert "VentWise has the required data again and resumed recommendations." in caplog.text
    assert "weather.home" not in caplog.text
    assert "sensor.bedroom_temperature" not in caplog.text


def test_coordinator_averages_global_perceived_indoor_across_rooms(
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
        "sensor.room_1_temp": SimpleNamespace(state="24.0"),
        "sensor.room_1_humidity": SimpleNamespace(state="50.0"),
        "sensor.room_2_temp": SimpleNamespace(state="28.0"),
        "sensor.room_2_humidity": SimpleNamespace(state="50.0"),
    }
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Camera 1",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_1_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_1_humidity",
                },
                {
                    CONF_ROOM_NAME: "Camera 2",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.room_2_temp",
                    CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.room_2_humidity",
                },
            ],
        }
    )
    coordinator.hass.states = SimpleNamespace(get=fake_states.get)

    snapshot = asyncio.run(coordinator._async_update_data())

    assert snapshot.active_indoor_perceived_c == pytest.approx(26.0)
