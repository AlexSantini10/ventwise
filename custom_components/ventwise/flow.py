"""Shared config flow helpers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    DeviceSelector,
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_COOLDOWN_MINUTES,
    CONF_MASTER_CONTROL_ENTITY_ID,
    CONF_NOTIFICATION_DEVICE_ID,
    CONF_OUTDOOR_WEATHER_ENTITY_ID,
    CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
    CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_END_ENTITY_ID,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_PAUSE_ENTITY_ID,
    CONF_QUIET_HOURS_START,
    CONF_QUIET_HOURS_START_ENTITY_ID,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_KIND,
    CONF_ROOM_NAME,
    CONF_ROOM_PAUSE_ENTITY_ID,
    CONF_ROOM_START_ENTITY_ID,
    CONF_ROOM_STOP_ENTITY_ID,
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
    DEFAULT_ROOM_WEIGHT,
    DEFAULT_SOFT_OUTDOOR_THRESHOLD_C,
    DEFAULT_STABILITY_MINUTES,
    DEFAULT_TARGET_TEMPERATURE_C,
    MAX_ROOM_WEIGHT,
    MIN_ROOM_WEIGHT,
)


@dataclass(slots=True)
class ConfigValidationError(ValueError):
    """Validation error tied to a specific config field."""

    field: str
    message: str = "invalid_input"


def build_config_schema(defaults: Mapping[str, object]) -> vol.Schema:
    """Create the minimal setup schema."""

    return vol.Schema(
        {
            vol.Required(
                CONF_OUTDOOR_WEATHER_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_WEATHER_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="weather")),
            vol.Required(
                CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_WIND_SPEED_ENTITY_ID,
                default=defaults.get(CONF_WIND_SPEED_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_TARGET_TEMPERATURE_C,
                default=defaults.get(CONF_TARGET_TEMPERATURE_C, DEFAULT_TARGET_TEMPERATURE_C),
            ): vol.All(vol.Coerce(float), vol.Range(min=10.0, max=30.0)),
        }
    )


def build_basic_options_schema(defaults: Mapping[str, object]) -> vol.Schema:
    """Create the user-facing basic options schema."""

    return vol.Schema(
        {
            vol.Required(
                CONF_OUTDOOR_WEATHER_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_WEATHER_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="weather")),
            vol.Required(
                CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_WIND_SPEED_ENTITY_ID,
                default=defaults.get(CONF_WIND_SPEED_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_TARGET_TEMPERATURE_C,
                default=defaults.get(CONF_TARGET_TEMPERATURE_C, DEFAULT_TARGET_TEMPERATURE_C),
            ): vol.All(vol.Coerce(float), vol.Range(min=10.0, max=30.0)),
            vol.Required(
                CONF_QUIET_HOURS_ENABLED,
                default=defaults.get(CONF_QUIET_HOURS_ENABLED, True),
            ): cv.boolean,
            vol.Optional(
                CONF_QUIET_HOURS_PAUSE_ENTITY_ID,
                default=defaults.get(CONF_QUIET_HOURS_PAUSE_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_NOTIFICATION_DEVICE_ID,
                default=defaults.get(CONF_NOTIFICATION_DEVICE_ID) or None,
            ): DeviceSelector(),
        }
    )


def build_advanced_options_schema(defaults: Mapping[str, object]) -> vol.Schema:
    """Create the advanced settings schema."""

    return vol.Schema(
        {
            vol.Required(
                CONF_SOFT_OUTDOOR_THRESHOLD_C,
                default=defaults.get(
                    CONF_SOFT_OUTDOOR_THRESHOLD_C, DEFAULT_SOFT_OUTDOOR_THRESHOLD_C
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=-10.0, max=40.0)),
            vol.Required(
                CONF_COOLDOWN_MINUTES,
                default=defaults.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=24 * 60)),
            vol.Required(
                CONF_STABILITY_MINUTES,
                default=defaults.get(CONF_STABILITY_MINUTES, DEFAULT_STABILITY_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=24 * 60)),
            vol.Required(
                CONF_QUIET_HOURS_START,
                default=defaults.get(CONF_QUIET_HOURS_START, DEFAULT_QUIET_HOURS_START),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_QUIET_HOURS_END,
                default=defaults.get(CONF_QUIET_HOURS_END, DEFAULT_QUIET_HOURS_END),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_QUIET_HOURS_START_ENTITY_ID,
                default=defaults.get(CONF_QUIET_HOURS_START_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_QUIET_HOURS_END_ENTITY_ID,
                default=defaults.get(CONF_QUIET_HOURS_END_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_OUTDOOR_TEMPERATURE_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID) or None,
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_OUTDOOR_HUMIDITY_ENTITY_ID,
                default=defaults.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID) or None,
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_WIND_SPEED_ENTITY_ID,
                default=defaults.get(CONF_WIND_SPEED_ENTITY_ID) or None,
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_MASTER_CONTROL_ENTITY_ID,
                default=defaults.get(CONF_MASTER_CONTROL_ENTITY_ID) or None,
            ): EntitySelector(),
        }
    )


def build_room_schema(defaults: Mapping[str, object], room_number: int, room_kind: str) -> vol.Schema:
    """Create the schema for a room or macro-room definition."""

    friendly_default = f"{room_kind.replace('_', ' ').title()} {room_number + 1}"
    return vol.Schema(
        {
            vol.Required(
                CONF_ROOM_NAME,
                default=defaults.get(CONF_ROOM_NAME, friendly_default),
            ): cv.string,
            vol.Required(
                CONF_ROOM_TEMPERATURE_ENTITY_ID,
                default=defaults.get(CONF_ROOM_TEMPERATURE_ENTITY_ID),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_ROOM_HUMIDITY_ENTITY_ID,
                default=defaults.get(CONF_ROOM_HUMIDITY_ENTITY_ID) or None,
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_ROOM_WEIGHT,
                default=defaults.get(CONF_ROOM_WEIGHT, DEFAULT_ROOM_WEIGHT),
            ): vol.All(vol.Coerce(float), vol.Range(min=MIN_ROOM_WEIGHT, max=MAX_ROOM_WEIGHT)),
            vol.Optional(
                CONF_ROOM_START_ENTITY_ID,
                default=defaults.get(CONF_ROOM_START_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_ROOM_STOP_ENTITY_ID,
                default=defaults.get(CONF_ROOM_STOP_ENTITY_ID) or None,
            ): EntitySelector(),
            vol.Optional(
                CONF_ROOM_PAUSE_ENTITY_ID,
                default=defaults.get(CONF_ROOM_PAUSE_ENTITY_ID) or None,
            ): EntitySelector(),
        }
    )


def normalize_basic_config(user_input: Mapping[str, object]) -> dict[str, object]:
    """Normalize minimal setup data."""

    data = dict(user_input)
    data[CONF_OUTDOOR_WEATHER_ENTITY_ID] = _normalize_required_entity_id(
        data.get(CONF_OUTDOOR_WEATHER_ENTITY_ID), CONF_OUTDOOR_WEATHER_ENTITY_ID, "weather"
    )
    data[CONF_OUTDOOR_TEMPERATURE_ENTITY_ID] = _normalize_required_entity_id(
        data.get(CONF_OUTDOOR_TEMPERATURE_ENTITY_ID), CONF_OUTDOOR_TEMPERATURE_ENTITY_ID, "sensor"
    )
    data[CONF_OUTDOOR_HUMIDITY_ENTITY_ID] = _normalize_required_entity_id(
        data.get(CONF_OUTDOOR_HUMIDITY_ENTITY_ID), CONF_OUTDOOR_HUMIDITY_ENTITY_ID, "sensor"
    )
    data[CONF_WIND_SPEED_ENTITY_ID] = _normalize_required_entity_id(
        data.get(CONF_WIND_SPEED_ENTITY_ID), CONF_WIND_SPEED_ENTITY_ID, "sensor"
    )
    data[CONF_TARGET_TEMPERATURE_C] = _normalize_float(
        data.get(CONF_TARGET_TEMPERATURE_C),
        CONF_TARGET_TEMPERATURE_C,
        10.0,
        30.0,
    )
    _normalize_optional_entities(
        data,
        CONF_QUIET_HOURS_PAUSE_ENTITY_ID,
        CONF_NOTIFICATION_DEVICE_ID,
    )
    return data


def normalize_advanced_config(user_input: Mapping[str, object]) -> dict[str, object]:
    """Normalize advanced flow data for storage."""

    data = dict(user_input)
    data[CONF_SOFT_OUTDOOR_THRESHOLD_C] = _normalize_float(
        data.get(CONF_SOFT_OUTDOOR_THRESHOLD_C),
        CONF_SOFT_OUTDOOR_THRESHOLD_C,
        -10.0,
        40.0,
    )
    data[CONF_COOLDOWN_MINUTES] = _normalize_int(
        data.get(CONF_COOLDOWN_MINUTES),
        CONF_COOLDOWN_MINUTES,
        0,
        24 * 60,
    )
    data[CONF_STABILITY_MINUTES] = _normalize_int(
        data.get(CONF_STABILITY_MINUTES),
        CONF_STABILITY_MINUTES,
        0,
        24 * 60,
    )
    data[CONF_QUIET_HOURS_START] = _normalize_time_string(data[CONF_QUIET_HOURS_START], CONF_QUIET_HOURS_START)
    data[CONF_QUIET_HOURS_END] = _normalize_time_string(data[CONF_QUIET_HOURS_END], CONF_QUIET_HOURS_END)
    _normalize_optional_entities(
        data,
        CONF_QUIET_HOURS_START_ENTITY_ID,
        CONF_QUIET_HOURS_END_ENTITY_ID,
        CONF_MASTER_CONTROL_ENTITY_ID,
    )
    _normalize_optional_entity_ids(
        data,
        CONF_QUIET_HOURS_START_ENTITY_ID,
        CONF_QUIET_HOURS_END_ENTITY_ID,
        CONF_MASTER_CONTROL_ENTITY_ID,
    )
    return data


def normalize_room_config(user_input: Mapping[str, object], room_kind: str) -> dict[str, object]:
    """Normalize room flow data for storage."""

    data = dict(user_input)
    data[CONF_ROOM_KIND] = _normalize_room_kind(room_kind)
    data[CONF_ROOM_NAME] = str(data[CONF_ROOM_NAME]).strip()
    if not data[CONF_ROOM_NAME]:
        raise ConfigValidationError(CONF_ROOM_NAME)
    data[CONF_ROOM_WEIGHT] = _normalize_float(
        data.get(CONF_ROOM_WEIGHT),
        CONF_ROOM_WEIGHT,
        MIN_ROOM_WEIGHT,
        MAX_ROOM_WEIGHT,
    )
    _normalize_optional_entities(
        data,
        CONF_ROOM_HUMIDITY_ENTITY_ID,
        CONF_ROOM_START_ENTITY_ID,
        CONF_ROOM_STOP_ENTITY_ID,
        CONF_ROOM_PAUSE_ENTITY_ID,
    )
    data[CONF_ROOM_TEMPERATURE_ENTITY_ID] = _normalize_required_entity_id(
        data.get(CONF_ROOM_TEMPERATURE_ENTITY_ID),
        CONF_ROOM_TEMPERATURE_ENTITY_ID,
        "sensor",
    )
    _normalize_optional_entity_ids(
        data,
        CONF_ROOM_HUMIDITY_ENTITY_ID,
        domain="sensor",
    )
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


def _normalize_optional_entities(data: dict[str, object], *keys: str) -> None:
    for key in keys:
        value = data.get(key)
        if value is None:
            data[key] = None
            continue
        text = str(value).strip()
        data[key] = text or None


def _normalize_optional_entity_ids(
    data: dict[str, object],
    *keys: str,
    domain: str | None = None,
) -> None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            data[key] = None
            continue
        data[key] = _normalize_required_entity_id(text, key, domain)


def _normalize_int(value: object, field: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(field) from exc
    if number < minimum or number > maximum:
        raise ConfigValidationError(field)
    return number


def _normalize_float(value: object, field: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(field) from exc
    if number < minimum or number > maximum:
        raise ConfigValidationError(field)
    return number


def _normalize_required_entity_id(value: object, field: str, domain: str | None = None) -> str:
    if value is None:
        raise ConfigValidationError(field)
    text = str(value).strip()
    if not text:
        raise ConfigValidationError(field)
    if "." not in text or text.startswith(".") or text.endswith("."):
        raise ConfigValidationError(field)
    entity_domain = text.split(".", 1)[0]
    if domain is not None and entity_domain != domain:
        raise ConfigValidationError(field)
    return text


def _normalize_room_kind(value: object) -> str:
    text = str(value).strip()
    if text not in {"room", "macro_room"}:
        raise ConfigValidationError(CONF_ROOM_KIND)
    return text


def _normalize_time_string(value: object, field: str) -> str:
    text = str(value).strip()
    if len(text.split(":")) == 2:
        try:
            return datetime.strptime(text, "%H:%M").strftime("%H:%M:%S")
        except ValueError as exc:
            raise ConfigValidationError(field) from exc
    try:
        return datetime.strptime(text, "%H:%M:%S").strftime("%H:%M:%S")
    except ValueError as exc:
        raise ConfigValidationError(field) from exc
