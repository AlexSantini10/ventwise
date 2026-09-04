"""End-to-end user journey tests from setup data to user-facing advice."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_OUTDOOR_HUMIDITY_OVERRIDE,
    CONF_OUTDOOR_TEMPERATURE_OVERRIDE,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_ROOM_ENABLED,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOMS,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
    CONF_WIND_SPEED_OVERRIDE,
    DOMAIN,
)
from custom_components.ventwise.config_flow import VentWiseConfigFlow
from custom_components.ventwise.flow import (
    normalize_basic_config,
    normalize_outdoor_source_config,
    normalize_room_config,
)
from custom_components.ventwise.notification import build_recommendation_explanation
from custom_components.ventwise.runtime import (
    build_integration_config,
    build_room_profiles,
    build_scoring_config,
)
from custom_components.ventwise.ventwise_core import ComfortRecommender, RecommendationAction


class _StandaloneVentWiseConfigFlow(VentWiseConfigFlow):
    """Config flow harness without Home Assistant's flow manager."""

    async def async_set_unique_id(self, unique_id: str | None = None) -> None:
        self._test_unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        return None

    def _async_current_entries(self):
        return ()


class _ExistingEntryVentWiseConfigFlow(_StandaloneVentWiseConfigFlow):
    """Config flow harness that simulates a previously configured instance."""

    def _async_current_entries(self):
        return (object(),)


def _setup_options() -> dict[str, object]:
    """Build the data submitted by the initial setup and room forms."""

    basic = normalize_basic_config(
        {
            CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.ventwise_test_weather",
            CONF_TARGET_TEMPERATURE_C: 22.0,
            CONF_AUTO_COMFORT_TEMPERATURE: False,
            CONF_TARGET_HUMIDITY_PERCENT: 50.0,
            CONF_STABILITY_MINUTES: 0,
            CONF_NOTIFICATION_DEVICE_ID: [],
        }
    )
    outdoor = normalize_outdoor_source_config(
        {
            CONF_OUTDOOR_TEMPERATURE_OVERRIDE: False,
            CONF_OUTDOOR_HUMIDITY_OVERRIDE: False,
            CONF_WIND_SPEED_OVERRIDE: False,
        }
    )
    room = normalize_room_config(
        {
            CONF_ROOM_ENABLED: True,
            CONF_ROOM_NAME: "Camera test",
            CONF_ROOM_TEMPERATURE_ENTITY_ID: "input_number.ventwise_test_bedroom_temperature",
            CONF_ROOM_HUMIDITY_ENTITY_ID: "input_number.ventwise_test_bedroom_humidity",
            CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED: False,
            CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C: None,
            CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED: False,
            CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE: None,
        },
        "room",
    )
    return {**basic, **outdoor, CONF_ROOMS: [room]}


def _evaluate(options: dict[str, object], states: dict[str, object]):
    """Evaluate the same data path used after the user saves setup."""

    config = build_integration_config(options)
    rooms, outdoor = build_room_profiles(config, states.get)
    assert outdoor is not None
    summary = ComfortRecommender(build_scoring_config(config)).evaluate(rooms, outdoor)
    assert summary.room_recommendations
    return summary, summary.room_recommendations[0]


def test_config_flow_creates_a_room_from_the_user_journey() -> None:
    """Exercise the actual setup wizard through its saved room data."""

    basic_input = {
        CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.ventwise_test_weather",
        CONF_TARGET_TEMPERATURE_C: 22.0,
        CONF_AUTO_COMFORT_TEMPERATURE: False,
        CONF_TARGET_HUMIDITY_PERCENT: 50.0,
        CONF_STABILITY_MINUTES: 0,
        CONF_NOTIFICATION_DEVICE_ID: [],
    }
    outdoor_input = {
        CONF_OUTDOOR_TEMPERATURE_OVERRIDE: False,
        CONF_OUTDOOR_HUMIDITY_OVERRIDE: False,
        CONF_WIND_SPEED_OVERRIDE: False,
    }
    room_input = {
        CONF_ROOM_ENABLED: True,
        CONF_ROOM_NAME: "Camera test",
        CONF_ROOM_TEMPERATURE_ENTITY_ID: "input_number.ventwise_test_bedroom_temperature",
        CONF_ROOM_HUMIDITY_ENTITY_ID: "input_number.ventwise_test_bedroom_humidity",
        CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED: False,
        CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C: None,
        CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED: False,
        CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE: None,
    }

    async def run_flow() -> tuple[dict[str, object], dict[str, object], str | None]:
        flow = _StandaloneVentWiseConfigFlow()
        outdoor_result = await flow.async_step_user(basic_input)
        assert outdoor_result["step_id"] == "outdoor"
        rooms_result = await flow.async_step_outdoor(outdoor_input)
        assert rooms_result["step_id"] == "rooms"
        updated_rooms_result = await flow.async_step_add_room(room_input)
        assert updated_rooms_result["step_id"] == "rooms"
        result = await flow.async_step_finish()
        repeated_result = await flow.async_step_finish()
        return result, repeated_result, flow._test_unique_id

    result, repeated_result, unique_id = asyncio.run(run_flow())

    assert result["type"] == "create_entry"
    assert result["options"][CONF_ROOMS][0][CONF_ROOM_NAME] == "Camera test"
    assert unique_id == DOMAIN
    assert repeated_result["type"] == "abort"
    assert repeated_result["reason"] == "single_instance_allowed"


def test_config_flow_prevents_a_second_ventwise_entry() -> None:
    """A second setup attempt must not create a duplicate integration entry."""

    result = asyncio.run(
        _ExistingEntryVentWiseConfigFlow().async_step_user(
            {
                CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.ventwise_test_weather",
                CONF_TARGET_TEMPERATURE_C: 22.0,
                CONF_NOTIFICATION_DEVICE_ID: [],
            }
        )
    )

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


def test_setup_to_user_facing_open_and_close_recommendations() -> None:
    """Cover setup, sensor input, scoring, and the user-visible explanation."""

    options = _setup_options()
    states = {
        "weather.ventwise_test_weather": SimpleNamespace(
            state="sunny",
            attributes={"temperature": 23.0, "humidity": 45.0, "wind_speed": 2.0},
        ),
        "input_number.ventwise_test_bedroom_temperature": SimpleNamespace(state="26"),
        "input_number.ventwise_test_bedroom_humidity": SimpleNamespace(state="50"),
    }

    open_summary, open_room = _evaluate(options, states)

    assert open_summary.action is RecommendationAction.OPEN
    assert build_recommendation_explanation(open_room, language="it") == (
        "apri le finestre. Fuori è più confortevole adesso: 3.2°C più vicino al comfort."
    )

    states["weather.ventwise_test_weather"] = SimpleNamespace(
        state="sunny",
        attributes={"temperature": 28.0, "humidity": 45.0, "wind_speed": 2.0},
    )
    states["input_number.ventwise_test_bedroom_temperature"] = SimpleNamespace(state="19")

    close_summary, close_room = _evaluate(options, states)

    assert close_summary.action is RecommendationAction.CLOSE
    assert build_recommendation_explanation(close_room, language="it") == (
        "chiudi le finestre. Dentro è più confortevole adesso: 2.8°C più vicino al comfort."
    )
