"""Integration tests using Home Assistant's custom-component pytest framework."""

from __future__ import annotations

import os

import pytest

if os.name == "nt":
    pytest.skip("Home Assistant's pytest framework requires a Unix runner", allow_module_level=True)

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ventwise.const import (
    CONF_CO2_ENABLED,
    CONF_CO2_THRESHOLD_PPM,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_ROOMS,
    CONF_ROOM_CO2_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS,
    CONF_STABILITY_MINUTES,
    DOMAIN,
)
from custom_components.ventwise.coordinator import VentWiseCoordinator


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_contact_and_co2_state_changes_refresh_a_real_ha_coordinator(
    hass: HomeAssistant,
) -> None:
    """No physical sensor is needed to exercise HA event delivery and refresh."""

    hass.states.async_set(
        "weather.test_lab",
        "sunny",
        {"temperature": 20.0, "humidity": 45.0, "wind_speed": 1.0},
    )
    hass.states.async_set("sensor.test_temperature", "27")
    hass.states.async_set("sensor.test_co2", "700")
    hass.states.async_set("binary_sensor.test_window_left", "off")
    hass.states.async_set("binary_sensor.test_window_right", "off")

    options = {
        CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.test_lab",
        CONF_STABILITY_MINUTES: 0,
        CONF_CO2_ENABLED: True,
        CONF_CO2_THRESHOLD_PPM: 1000.0,
        CONF_ROOMS: [
            {
                CONF_ROOM_NAME: "Test room",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.test_temperature",
                CONF_ROOM_CO2_ENTITY_ID: "sensor.test_co2",
                CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS: [
                    "binary_sensor.test_window_left",
                    "binary_sensor.test_window_right",
                ],
            }
        ],
    }
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options)
    entry.add_to_hass(hass)
    coordinator = VentWiseCoordinator(hass, entry, options)

    await coordinator.async_config_entry_first_refresh()
    assert coordinator.data.window_states["Test room"] == "closed"

    hass.states.async_set("binary_sensor.test_window_left", "on")
    await hass.async_block_till_done()
    assert coordinator.data.window_states["Test room"] == "open"

    hass.states.async_set("sensor.test_co2", "1400")
    await hass.async_block_till_done()
    recommendation = coordinator.data.summary.room_recommendations[0]
    assert recommendation.co2_influence is not None
