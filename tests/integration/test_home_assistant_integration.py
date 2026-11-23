"""Integration tests using Home Assistant's custom-component pytest framework."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

if os.name == "nt":
    pytest.skip("Home Assistant's pytest framework requires a Unix runner", allow_module_level=True)

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import SOURCE_USER
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ventwise.const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_CO2_ENABLED,
    CONF_CO2_ENTITY_ID,
    CONF_CO2_THRESHOLD_PPM,
    CONF_COOLDOWN_MINUTES,
    CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED,
    CONF_NOTIFICATION_ENABLED,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOMS,
    CONF_ROOM_CO2_ENTITY_ID,
    CONF_ROOM_CO2_ENABLED,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_SELECTION,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_TEMPERATURE_UNIT,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
    CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS,
    CONF_STABILITY_MINUTES,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_TARGET_TEMPERATURE_C,
    CONF_TARGET_HUMIDITY_PERCENT,
    DOMAIN,
)
from custom_components.ventwise.application.coordinator import VentWiseCoordinator
from custom_components.ventwise.application.notification import async_send_notification
from custom_components.ventwise.application import coordinator as coordinator_module
from custom_components.ventwise import IntegrationRuntimeData
from ventwise_core import RecommendationAction


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _options(**overrides: object) -> dict[str, object]:
    """Return one complete state-driven room configuration."""

    options: dict[str, object] = {
        CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.test_lab",
        CONF_TARGET_TEMPERATURE_C: 22.0,
        CONF_STABILITY_MINUTES: 0,
        CONF_CO2_ENABLED: True,
        CONF_CO2_THRESHOLD_PPM: 1000.0,
        CONF_ROOMS: [
            {
                CONF_ROOM_NAME: "Test room",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.test_temperature",
                CONF_ROOM_CO2_ENTITY_ID: "sensor.test_co2",
                CONF_ROOM_CO2_ENABLED: True,
                CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS: [
                    "binary_sensor.test_window_left",
                    "binary_sensor.test_window_right",
                ],
            }
        ],
    }
    options.update(overrides)
    return options


def _seed_states(hass: HomeAssistant) -> None:
    """Publish complete fake sensor data through the real HA state machine."""

    hass.states.async_set(
        "weather.test_lab",
        "sunny",
        {"temperature": 20.0, "humidity": 45.0, "wind_speed": 1.0},
    )
    hass.states.async_set("sensor.test_temperature", "27")
    hass.states.async_set("sensor.test_co2", "700")
    hass.states.async_set("binary_sensor.test_window_left", "off")
    hass.states.async_set("binary_sensor.test_window_right", "off")


async def _setup_coordinator(
    hass: HomeAssistant,
    options: dict[str, object],
) -> VentWiseCoordinator:
    """Set up VentWise through HA's config-entry lifecycle."""

    entry = MockConfigEntry(domain=DOMAIN, version=2, data={}, options=options)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    runtime = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(runtime, IntegrationRuntimeData)
    return runtime.coordinator


@pytest.mark.asyncio
async def test_contact_and_co2_state_changes_refresh_a_real_ha_coordinator(
    hass: HomeAssistant,
) -> None:
    """No physical sensor is needed to exercise HA event delivery and refresh."""

    _seed_states(hass)
    options = _options()
    coordinator = await _setup_coordinator(hass, options)

    assert coordinator.data.window_states["Test room"] == "closed"

    hass.states.async_set("binary_sensor.test_window_left", "on")
    await hass.async_block_till_done()
    assert coordinator.data.window_states["Test room"] == "open"

    hass.states.async_set("sensor.test_co2", "1400")
    await hass.async_block_till_done()
    recommendation = coordinator.data.summary.room_recommendations[0]
    assert recommendation.co2_influence is not None


@pytest.mark.asyncio
async def test_real_config_entry_setup_creates_entities_and_unloads_cleanly(
    hass: HomeAssistant,
) -> None:
    """Exercise platform forwarding through Home Assistant's config-entry manager."""

    _seed_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={}, options=_options())
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    runtime = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(runtime, IntegrationRuntimeData)
    assert hass.states.get("sensor.test_room_recommendation") is not None
    assert hass.states.get("sensor.test_room_co2").state == "700"
    assert hass.states.get("sensor.test_room_window_state").state == "closed"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_options_save_waits_for_updated_runtime_and_entities(
    hass: HomeAssistant,
) -> None:
    """An options save must finish only after the new runtime is visible."""

    _seed_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={}, options=_options())
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "comfort"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TARGET_TEMPERATURE_C: 24.0,
            CONF_AUTO_COMFORT_TEMPERATURE: False,
            CONF_TARGET_HUMIDITY_PERCENT: 55.0,
            CONF_STABILITY_MINUTES: 0,
            CONF_SOFT_OUTDOOR_THRESHOLD_C: 22.0,
            CONF_CO2_ENABLED: False,
            CONF_CO2_ENTITY_ID: None,
            CONF_CO2_THRESHOLD_PPM: 1000.0,
        },
    )

    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    runtime = hass.data[DOMAIN][entry.entry_id]
    assert runtime.coordinator.config.target_temperature_c == 24.0
    assert entry.options[CONF_TARGET_TEMPERATURE_C] == 24.0
    assert hass.states.get("sensor.test_room_co2").state == "700"


@pytest.mark.asyncio
async def test_room_options_save_removes_co2_from_the_saved_entry(
    hass: HomeAssistant,
) -> None:
    """Removing a room CO₂ source through the real flow must be persisted."""

    _seed_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={}, options=_options())
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "rooms"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ROOM_SELECTION: "1. Test room (Room)"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "edit_room"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ROOM_NAME: "Test room",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.test_temperature",
            CONF_ROOM_CO2_ENTITY_ID: None,
            CONF_ROOM_CO2_ENABLED: False,
            CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED: False,
            CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C: None,
            CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED: False,
            CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE: None,
        },
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ROOM_TEMPERATURE_UNIT: "°C"}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    room = entry.options[CONF_ROOMS][0]
    assert room[CONF_ROOM_CO2_ENTITY_ID] is None
    assert room[CONF_ROOM_CO2_ENABLED] is False
    assert hass.states.get("sensor.test_room_co2").state in {
        "not_configured",
        "unavailable",
    }


@pytest.mark.asyncio
async def test_clearing_optional_bindings_keeps_ventwise_entities_available(
    hass: HomeAssistant,
) -> None:
    """Removing source bindings keeps derived entities with clear states."""

    _seed_states(hass)
    options = _options()
    options[CONF_ROOMS][0][CONF_ROOM_HUMIDITY_ENTITY_ID] = "sensor.test_humidity"
    hass.states.async_set("sensor.test_humidity", "50")
    entry = MockConfigEntry(domain=DOMAIN, version=6, data={}, options=options)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    updated_options = dict(options)
    updated_options[CONF_ROOMS] = [
        {
            CONF_ROOM_NAME: "Test room",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.test_temperature",
            CONF_ROOM_CO2_ENABLED: False,
            CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS: [],
        }
    ]
    hass.config_entries.async_update_entry(entry, options=updated_options)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_room_co2") is not None
    assert hass.states.get("sensor.test_room_co2").state == "disabled"
    assert hass.states.get("sensor.test_room_indoor_humidity") is not None
    assert hass.states.get("sensor.test_room_indoor_humidity").state in {"unknown", "unavailable"}
    assert hass.states.get("sensor.test_room_window_state") is not None
    assert hass.states.get("sensor.test_room_window_state").state == "not_configured"


@pytest.mark.asyncio
async def test_entity_ids_stay_english_when_home_assistant_uses_italian(
    hass: HomeAssistant,
) -> None:
    """Entity IDs are an automation contract, not a translated presentation label."""

    hass.config.language = "it"
    _seed_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={}, options=_options())
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_room_recommendation") is not None
    assert hass.states.get("sensor.test_room_raccomandazione") is None

    recommendation = hass.states.get("sensor.test_room_recommendation")
    score = hass.states.get("sensor.test_room_score")
    reason = hass.states.get("sensor.test_room_reason")
    assert recommendation is not None
    assert score is not None
    assert reason is not None
    assert "Raccomandazione" in recommendation.attributes["friendly_name"]
    assert "Punteggio" in score.attributes["friendly_name"]
    assert "Recommendation" not in recommendation.attributes["friendly_name"]
    assert "Score" not in score.attributes["friendly_name"]
    assert "Outside" not in reason.state


@pytest.mark.asyncio
async def test_real_flow_manager_starts_the_ventwise_config_flow(
    hass: HomeAssistant,
) -> None:
    """Ensure the config-flow entry point is discoverable by HA itself."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.test_lab",
            CONF_TARGET_TEMPERATURE_C: 22.0,
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "outdoor"


@pytest.mark.asyncio
async def test_real_window_events_suppress_satisfied_advice_and_notifications(
    hass: HomeAssistant,
) -> None:
    """An open contact must prevent both repeated advice and another delivery."""

    _seed_states(hass)
    deliveries: list[ServiceCall] = []

    async def _capture_delivery(call: ServiceCall) -> None:
        deliveries.append(call)

    hass.services.async_register("persistent_notification", "create", _capture_delivery)
    options = _options(
        **{
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_QUIET_HOURS_ENABLED: False,
        }
    )
    coordinator = await _setup_coordinator(hass, options)

    assert coordinator.data.summary.action is RecommendationAction.OPEN
    assert len(deliveries) == 1
    assert deliveries[0].data["notification_id"] == "ventwise_recommendation_test_room"

    hass.states.async_set("binary_sensor.test_window_left", "on")
    await hass.async_block_till_done()
    assert coordinator.data.summary.action is RecommendationAction.NONE
    assert coordinator.data.summary.blocked_by == "window_state"
    assert len(deliveries) == 1


@pytest.mark.asyncio
async def test_real_state_events_do_not_redeliver_an_unchanged_recommendation(
    hass: HomeAssistant,
) -> None:
    """The coordinator's delivery marker suppresses deterministic duplicates."""

    _seed_states(hass)
    deliveries: list[ServiceCall] = []

    async def _capture_delivery(call: ServiceCall) -> None:
        deliveries.append(call)

    hass.services.async_register("persistent_notification", "create", _capture_delivery)
    options = _options(
        **{
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_COOLDOWN_MINUTES: 60,
            CONF_QUIET_HOURS_ENABLED: False,
        }
    )
    coordinator = await _setup_coordinator(hass, options)

    assert coordinator.data.summary.action is RecommendationAction.OPEN
    assert len(deliveries) == 1
    assert deliveries[0].data["notification_id"] == "ventwise_recommendation_test_room"

    hass.states.async_set("sensor.test_temperature", "27.1")
    await hass.async_block_till_done()
    assert coordinator.data.summary.action is RecommendationAction.OPEN
    assert coordinator.data.cooldown_active is True
    assert len(deliveries) == 1

    hass.states.async_set("sensor.test_temperature", "27.2")
    await hass.async_block_till_done()
    assert coordinator.data.summary.action is RecommendationAction.OPEN
    assert coordinator.data.cooldown_active is True
    assert len(deliveries) == 1


@pytest.mark.asyncio
async def test_quiet_hours_block_automatic_delivery_in_a_real_ha_runtime(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quiet-hours constraints apply before the coordinator calls notification delivery."""

    _seed_states(hass)
    deliveries: list[dict[str, object]] = []

    async def _capture_delivery(_hass, _entity_ids, **kwargs: object) -> bool:
        deliveries.append(kwargs)
        return True

    monkeypatch.setattr(coordinator_module, "async_send_notification", _capture_delivery)
    fixed_now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(coordinator_module.dt_util, "now", lambda: fixed_now)
    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: fixed_now)
    options = _options(
        **{
            CONF_HOME_ASSISTANT_NOTIFICATION_ENABLED: True,
            CONF_NOTIFICATION_ENABLED: True,
            CONF_QUIET_HOURS_ENABLED: True,
            CONF_QUIET_HOURS_START: "00:00:00",
            CONF_QUIET_HOURS_END: "23:59:59",
        }
    )
    coordinator = await _setup_coordinator(hass, options)

    assert coordinator.data.summary.action is RecommendationAction.OPEN
    assert coordinator.data.quiet_hours_active is True
    assert deliveries == []


@pytest.mark.asyncio
async def test_notification_delivery_uses_the_real_ha_service_registry(
    hass: HomeAssistant,
) -> None:
    """Verify a selected notify target receives the expected HA service call."""

    received: list[ServiceCall] = []

    async def _capture(call: ServiceCall) -> None:
        received.append(call)

    hass.services.async_register("notify", "send_message", _capture)

    delivered = await async_send_notification(
        hass,
        ("notify.test_phone",),
        title="VentWise test",
        message="Open the window",
    )

    assert delivered is True
    assert len(received) == 1
    assert received[0].data == {
        "title": "VentWise test",
        "message": "Open the window",
        "entity_id": "notify.test_phone",
    }
