"""Tests for the VentWise options flow room management."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_ROOM_KIND,
    CONF_ROOM_NAME,
    CONF_ROOM_SELECTION,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOMS,
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
