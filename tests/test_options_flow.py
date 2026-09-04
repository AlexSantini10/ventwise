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
    CONF_OUTDOOR_HUMIDITY_OVERRIDE,
    CONF_OUTDOOR_TEMPERATURE_OVERRIDE,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_ROOM_KIND,
    CONF_ROOM_NAME,
    CONF_ROOM_SELECTION,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOMS,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
    CONF_WIND_SPEED_OVERRIDE,
)
from custom_components.ventwise.options_flow import VentWiseOptionsFlowHandler


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


def test_settings_screen_saves_everyday_and_comfort_values_together() -> None:
    """Users do not need to navigate between technical settings sections."""

    flow = _make_flow()

    saved = asyncio.run(
        flow.async_step_settings(
            {
                CONF_OUTDOOR_WEATHER_ENTITY_ID: "weather.home",
                CONF_TARGET_TEMPERATURE_C: 22.0,
                CONF_AUTO_COMFORT_TEMPERATURE: True,
                CONF_TARGET_HUMIDITY_PERCENT: 50.0,
                CONF_STABILITY_MINUTES: 10,
                CONF_NOTIFICATION_DEVICE_ID: [],
                CONF_SOFT_OUTDOOR_THRESHOLD_C: 23.0,
                CONF_COOLDOWN_MINUTES: 45,
                CONF_OUTDOOR_TEMPERATURE_OVERRIDE: False,
                CONF_OUTDOOR_HUMIDITY_OVERRIDE: False,
                CONF_WIND_SPEED_OVERRIDE: False,
            }
        )
    )

    assert saved["type"] == "create_entry"
    assert saved["data"][CONF_AUTO_COMFORT_TEMPERATURE] is True
    assert saved["data"][CONF_COOLDOWN_MINUTES] == 45


def test_options_menu_has_one_settings_screen_and_rooms() -> None:
    """The top level does not fragment everyday settings into submenus."""

    flow = _make_flow()

    overview = asyncio.run(flow.async_step_init())

    assert overview["type"] == "menu"
    assert overview["step_id"] == "init"
    assert overview["menu_options"] == ["settings", "rooms"]


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
        flow.async_step_edit_room_details(
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
