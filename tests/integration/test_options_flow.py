"""Tests for the VentWise options flow room management."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_COOLDOWN_MINUTES,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_ROOM_KIND,
    CONF_ROOM_NAME,
    CONF_ROOM_SELECTION,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOMS,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
)
from custom_components.ventwise.configuration.options_flow import VentWiseOptionsFlowHandler


def _make_flow(options: dict[str, object] | None = None) -> VentWiseOptionsFlowHandler:
    entry = SimpleNamespace(
        data={},
        options=options or {},
    )
    return VentWiseOptionsFlowHandler(entry)


def test_room_selection_helpers_expose_stable_labels() -> None:
    flow = _make_flow(
        {
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Living room",
                    CONF_ROOM_KIND: "room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                },
                {
                    CONF_ROOM_NAME: "Upstairs",
                    CONF_ROOM_KIND: "macro_room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.upstairs_temp",
                },
            ]
        }
    )

    assert flow._room_selection_options() == [
        "1. Living room (Room)",
        "2. Upstairs (Macro Room)",
    ]
    assert flow._room_selection_index("2. Upstairs (Macro Room)") == 1


def test_remove_room_updates_the_saved_list() -> None:
    flow = _make_flow(
        {
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Living room",
                    CONF_ROOM_KIND: "room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                },
                {
                    CONF_ROOM_NAME: "Upstairs",
                    CONF_ROOM_KIND: "macro_room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.upstairs_temp",
                },
            ]
        }
    )

    asyncio.run(flow.async_step_remove_room({CONF_ROOM_SELECTION: "1. Living room (Room)"}))

    assert len(flow._rooms) == 1
    assert flow._rooms[0][CONF_ROOM_NAME] == "Upstairs"
    assert flow._current_config[CONF_ROOMS][0][CONF_ROOM_NAME] == "Upstairs"


def test_daily_screen_preserves_advanced_values() -> None:
    """Everyday changes do not overwrite values hidden in Advanced."""

    flow = _make_flow({CONF_COOLDOWN_MINUTES: 45})

    saved = asyncio.run(
        flow.async_step_daily(
            {
                CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
                CONF_TARGET_TEMPERATURE_C: 22.0,
                CONF_AUTO_COMFORT_TEMPERATURE: True,
                CONF_TARGET_HUMIDITY_PERCENT: 50.0,
                CONF_STABILITY_MINUTES: 10,
                CONF_NOTIFICATION_DEVICE_ID: [],
                "home_assistant_notification_enabled": False,
            }
        )
    )

    assert saved["type"] == "create_entry"
    assert saved["data"][CONF_AUTO_COMFORT_TEMPERATURE] is True
    assert saved["data"][CONF_COOLDOWN_MINUTES] == 45


def test_options_menu_has_purpose_based_sections() -> None:
    """The top level makes settings discoverable by user goal."""

    flow = _make_flow()

    overview = asyncio.run(flow.async_step_init())

    assert overview["type"] == "menu"
    assert overview["step_id"] == "init"
    assert overview["menu_options"] == [
        "comfort", "co2", "outdoor_air", "windows", "rooms", "notifications", "other"
    ]
    other = asyncio.run(flow.async_step_other())
    assert other["type"] == "form"
    assert set(other["data_schema"].schema) >= {"temperature_unit", "wind_speed_unit", "debug_mode_enabled"}


def test_room_edit_menu_exposes_four_purpose_based_sections() -> None:
    flow = _make_flow({CONF_ROOMS: [{CONF_ROOM_NAME: "Living room", CONF_ROOM_KIND: "room"}]})

    asyncio.run(flow.async_step_edit_room({CONF_ROOM_SELECTION: "1. Living room (Room)"}))
    details = asyncio.run(flow.async_step_edit_room_details())

    assert details["menu_options"] == [
        "edit_room_basics",
        "edit_room_comfort",
        "edit_room_co2_windows",
        "edit_room_advanced",
    ]


def test_air_quality_source_updates_only_the_selected_source() -> None:
    flow = _make_flow({"air_quality_entity_ids": {"pm10": "sensor.pm10"}})

    asyncio.run(flow.async_step_air_quality_source_select({"air_quality_source": "pm2_5"}))
    saved = asyncio.run(
        flow.async_step_air_quality_source(
            {
                "air_quality_pm2_5_entity_id": "sensor.pm25",
                "air_quality_pm2_5_policy": "avoid",
                "air_quality_pm2_5_threshold": 25,
                "air_quality_pm2_5_unit": "µg/m³",
                "air_quality_pm2_5_averaging_period": "24h",
            }
        )
    )

    assert saved["data"]["air_quality_entity_ids"] == {"pm10": "sensor.pm10", "pm2_5": "sensor.pm25"}
    assert saved["data"]["exposure_policies"]["pm2_5"]["threshold"] == 25.0


def test_edit_room_replaces_the_selected_room() -> None:
    flow = _make_flow(
        {
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Living room",
                    CONF_ROOM_KIND: "room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                },
                {
                    CONF_ROOM_NAME: "Upstairs",
                    CONF_ROOM_KIND: "macro_room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.upstairs_temp",
                },
            ]
        }
    )

    asyncio.run(flow.async_step_edit_room({CONF_ROOM_SELECTION: "1. Living room (Room)"}))
    asyncio.run(
        flow.async_step_edit_room_base(
            {
                CONF_ROOM_NAME: "Studio",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.studio_temp",
                "humidity_entity_id": None,
                "weight": 1.5,
                "start_entity_id": None,
                "stop_entity_id": None,
            }
        )
    )

    assert flow._rooms[0][CONF_ROOM_NAME] == "Studio"
    assert flow._rooms[0][CONF_ROOM_TEMPERATURE_ENTITY_ID] == "sensor.studio_temp"
    assert flow._rooms[0][CONF_ROOM_KIND] == "room"
    assert flow._current_config[CONF_ROOMS][0][CONF_ROOM_NAME] == "Studio"


def test_options_flow_supports_units_macro_rooms_and_staged_room_changes() -> None:
    """Cover each options navigation branch without relying on a live HA profile."""

    flow = _make_flow(
        {
            CONF_ROOMS: [
                {
                    CONF_ROOM_NAME: "Living room",
                    CONF_ROOM_KIND: "room",
                    CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.living_temp",
                }
            ]
        }
    )

    assert asyncio.run(flow.async_step_units()) ["type"] == "form"
    assert asyncio.run(flow.async_step_units({"temperature_unit": "C", "wind_speed_unit": "km/h"}))["type"] == "create_entry"

    rooms = asyncio.run(flow.async_step_rooms())
    assert rooms["menu_options"] == ["add_room", "add_macro_room", "edit_room", "remove_room", "finish"]
    assert asyncio.run(flow.async_step_add_macro_room())["step_id"] == "add_macro_room"
    assert asyncio.run(
        flow.async_step_add_macro_room(
            {
                CONF_ROOM_NAME: "Upstairs",
                CONF_ROOM_TEMPERATURE_ENTITY_ID: "sensor.upstairs_temp",
            }
        )
    )["type"] == "menu"

    selection = flow._room_selection_options()[0]
    assert asyncio.run(flow.async_step_edit_room({CONF_ROOM_SELECTION: selection}))["step_id"] == "edit_room_details"
    assert asyncio.run(flow.async_step_edit_room_base())["step_id"] == "edit_room_base"
    assert asyncio.run(flow.async_step_remove_room({CONF_ROOM_SELECTION: selection}))["type"] == "menu"
    saved = asyncio.run(flow.async_step_finish())
    assert saved["type"] == "create_entry"
    assert saved["data"][CONF_ROOMS][0][CONF_ROOM_NAME] == "Upstairs"
