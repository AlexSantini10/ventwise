"""A real Home Assistant journey from onboarding through a restart."""

from __future__ import annotations

import os

import pytest

if os.name == "nt":
    pytest.skip("Home Assistant's pytest framework requires a Unix runner", allow_module_level=True)

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from custom_components.ventwise.const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_ROOM_ENABLED,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
    DOMAIN,
)
from custom_components.ventwise.ventwise_core import RecommendationAction


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _seed_states(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "weather.ventwise_test_weather",
        "sunny",
        {"temperature": 20.0, "humidity": 45.0, "wind_speed": 1.0},
    )
    hass.states.async_set("sensor.ventwise_test_temperature", "27")
    hass.states.async_set("sensor.ventwise_test_humidity", "50")


@pytest.mark.asyncio
async def test_onboarding_sensor_update_and_reload_journey(hass: HomeAssistant) -> None:
    """Exercise the user flow, real entry setup, decision entity and reload."""

    _seed_states(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.ventwise_test_weather",
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_AUTO_COMFORT_TEMPERATURE: False,
            CONF_TARGET_HUMIDITY_PERCENT: 50.0,
            CONF_STABILITY_MINUTES: 0,
        },
    )
    assert result["type"] == "menu"
    assert result["step_id"] == "rooms"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_room"}
    )
    assert result["step_id"] == "add_room"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ROOM_ENABLED: True,
            CONF_ROOM_NAME: "Camera test",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.ventwise_test_temperature",
            CONF_ROOM_HUMIDITY_ENTITY_ID: "sensor.ventwise_test_humidity",
            CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED: False,
            CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C: None,
            CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED: False,
            CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE: None,
        },
    )
    assert result["type"] == "menu"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "menu"
    assert result["step_id"] == "optional_setup"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "create_entry"
    entry = result["result"]
    await hass.async_block_till_done()

    recommendation = hass.states.get("sensor.camera_test_recommendation")
    assert recommendation is not None
    assert recommendation.state == RecommendationAction.OPEN.value
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.camera_test_recommendation") is not None
