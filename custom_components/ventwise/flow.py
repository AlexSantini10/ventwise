"""Shared config flow helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    DeviceSelector,
    EntitySelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_COOLDOWN_MINUTES,
    CONF_MINIMUM_SCORE,
    CONF_MASTER_CONTROL_ENTITY_ID,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_ROOM_COUNT,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_WEIGHT,
    CONF_ROOMS,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_TEMPERATURE_C,
    CONF_WIND_SPEED_ENTITY_ID,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_ROOM_COUNT,
    DEFAULT_ROOM_WEIGHT,
    DEFAULT_SOFT_OUTDOOR_THRESHOLD_C,
    DEFAULT_STABILITY_MINUTES,
    DEFAULT_TARGET_TEMPERATURE_C,
    MAX_ROOM_COUNT,
    MAX_ROOM_WEIGHT,
    MIN_ROOM_WEIGHT,
)


def build_global_schema(defaults: Mapping[str, object]) -> vol.Schema:
    """Create the shared schema for global settings."""

    return vol.Schema(
        {
            vol.Required(
                CONF_TARGET_TEMPERATURE_C,
                default=defaults.get(CONF_TARGET_TEMPERATURE_C, DEFAULT_TARGET_TEMPERATURE_C),
            ): vol.All(vol.Coerce(float), vol.Range(min=10.0, max=30.0)),
            vol.Required(
                CONF_SOFT_OUTDOOR_THRESHOLD_C,
                default=defaults.get(
                    CONF_SOFT_OUTDOOR_THRESHOLD_C, DEFAULT_SOFT_OUTDOOR_THRESHOLD_C
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=-10.0, max=40.0)),
            vol.Required(
                CONF_MINIMUM_SCORE,
                default=defaults.get(CONF_MINIMUM_SCORE, DEFAULT_MINIMUM_SCORE),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Required(
                CONF_COOLDOWN_MINUTES,
                default=defaults.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=24 * 60)),
            vol.Required(
                CONF_STABILITY_MINUTES,
                default=defaults.get(CONF_STABILITY_MINUTES, DEFAULT_STABILITY_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=24 * 60)),
            vol.Required(
                CONF_QUIET_HOURS_ENABLED,
                default=defaults.get(CONF_QUIET_HOURS_ENABLED, True),
            ): cv.boolean,
            vol.Required(
                CONF_QUIET_HOURS_START,
                default=defaults.get(CONF_QUIET_HOURS_START, DEFAULT_QUIET_HOURS_START),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_QUIET_HOURS_END,
                default=defaults.get(CONF_QUIET_HOURS_END, DEFAULT_QUIET_HOURS_END),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID),
            ): EntitySelector(),
            vol.Required(
                CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID),
            ): EntitySelector(),
            vol.Optional(
                CONF_WIND_SPEED_ENTITY_ID,
                default=defaults.get(CONF_WIND_SPEED_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_MASTER_CONTROL_ENTITY_ID,
                default=defaults.get(CONF_MASTER_CONTROL_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_NOTIFICATION_DEVICE_ID,
                default=defaults.get(CONF_NOTIFICATION_DEVICE_ID) or None,
            ): DeviceSelector(),
            vol.Required(
                CONF_ROOM_COUNT,
                default=defaults.get(CONF_ROOM_COUNT, DEFAULT_ROOM_COUNT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_ROOM_COUNT)),
        }
    )


def build_room_schema(defaults: Mapping[str, object], room_number: int) -> vol.Schema:
    """Create the shared schema for a room definition."""

    return vol.Schema(
        {
            vol.Required(CONF_ROOM_NAME, default=defaults.get(CONF_ROOM_NAME, f"Room {room_number + 1}")): cv.string,
            vol.Required(
                CONF_ROOM_TEMPERATURE_ENTITY_ID,
                default=defaults.get(CONF_ROOM_TEMPERATURE_ENTITY_ID),
            ): EntitySelector(),
            vol.Required(
                CONF_ROOM_HUMIDITY_ENTITY_ID,
                default=defaults.get(CONF_ROOM_HUMIDITY_ENTITY_ID),
            ): EntitySelector(),
            vol.Required(
                CONF_ROOM_WEIGHT,
                default=defaults.get(CONF_ROOM_WEIGHT, DEFAULT_ROOM_WEIGHT),
            ): vol.All(vol.Coerce(float), vol.Range(min=MIN_ROOM_WEIGHT, max=MAX_ROOM_WEIGHT)),
        }
    )


def normalize_global_config(user_input: Mapping[str, object]) -> dict[str, object]:
    """Normalize global flow data for storage."""

    data = dict(user_input)
    data[CONF_QUIET_HOURS_START] = _normalize_time_string(data[CONF_QUIET_HOURS_START])
    data[CONF_QUIET_HOURS_END] = _normalize_time_string(data[CONF_QUIET_HOURS_END])
    for key in (
        CONF_WIND_SPEED_ENTITY_ID,
        CONF_MASTER_CONTROL_ENTITY_ID,
        CONF_NOTIFICATION_DEVICE_ID,
    ):
        value = data.get(key)
        data[key] = value or None
    return data


def normalize_room_config(user_input: Mapping[str, object]) -> dict[str, object]:
    """Normalize room flow data for storage."""

    data = dict(user_input)
    data[CONF_ROOM_NAME] = str(data[CONF_ROOM_NAME]).strip()
    return data


def split_config_data(data: Mapping[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Split a saved config entry into global settings and rooms."""

    global_data = {
        key: value
        for key, value in data.items()
        if key != CONF_ROOMS
    }
    rooms = [dict(room) for room in data.get(CONF_ROOMS, [])]
    return global_data, rooms


def _normalize_time_string(value: object) -> str:
    text = str(value).strip()
    if len(text.split(":")) == 2:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M:%S")
    return datetime.strptime(text, "%H:%M:%S").strftime("%H:%M:%S")
