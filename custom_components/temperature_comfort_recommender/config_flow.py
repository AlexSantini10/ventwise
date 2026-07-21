"""Config flow for VentWise."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_ROOMS, DOMAIN, NAME
from .const import CONF_ROOM_COUNT
from .flow import (
    build_global_schema,
    build_room_schema,
    normalize_global_config,
    normalize_room_config,
)


class TemperatureComfortRecommenderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._global_data: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []
        self._room_count = 0
        self._room_index = 0

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Collect global settings and the desired room count."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._global_data = normalize_global_config(user_input)
                self._room_count = int(self._global_data.pop(CONF_ROOM_COUNT))
                self._rooms = []
                self._room_index = 0
                return await self.async_step_room()
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="user",
            data_schema=build_global_schema(self._global_data),
            errors=errors,
        )

    async def async_step_room(self, user_input: dict[str, Any] | None = None):
        """Collect one room at a time."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._rooms.append(normalize_room_config(user_input))
                self._room_index += 1
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
            else:
                if self._room_index < self._room_count:
                    return await self.async_step_room()
                data = {**self._global_data, CONF_ROOMS: self._rooms}
                return self.async_create_entry(title=NAME, data=data)

        default_room: dict[str, Any] = {}
        return self.async_show_form(
            step_id="room",
            data_schema=build_room_schema(default_room, self._room_index),
            errors=errors,
            description_placeholders={
                "current_room": str(self._room_index + 1),
                "room_count": str(self._room_count),
            },
        )


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""

        from .options_flow import TemperatureComfortRecommenderOptionsFlowHandler

        return TemperatureComfortRecommenderOptionsFlowHandler(config_entry)
