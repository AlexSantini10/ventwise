"""Options flow for VentWise."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from .const import CONF_ROOMS, DOMAIN, NAME
from .flow import (
    build_global_schema,
    build_room_schema,
    normalize_global_config,
    normalize_room_config,
    split_config_data,
)


class VentWiseOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._current_config = {**config_entry.data, **config_entry.options}
        self._global_data: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []
        self._room_count = 0
        self._room_index = 0

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Collect global settings and room count."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._global_data = normalize_global_config(user_input)
                self._room_count = int(self._global_data.pop("room_count"))
                _, current_rooms = split_config_data(self._current_config)
                self._rooms = current_rooms[: self._room_count]
                self._room_index = 0
                return await self.async_step_room()
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        current_global = dict(self._current_config)
        current_global["room_count"] = len(self._current_config.get(CONF_ROOMS, []))
        return self.async_show_form(
            step_id="init",
            data_schema=build_global_schema(current_global),
            errors=errors,
        )

    async def async_step_room(self, user_input: dict[str, Any] | None = None):
        """Collect one room at a time."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                room = normalize_room_config(user_input)
                if self._room_index < len(self._rooms):
                    self._rooms[self._room_index] = room
                else:
                    self._rooms.append(room)
                self._room_index += 1
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
            else:
                if self._room_index < self._room_count:
                    return await self.async_step_room()
                updated = {**self._current_config, **self._global_data, CONF_ROOMS: self._rooms}
                return self.async_create_entry(title=NAME, data=updated)

        default_room = self._rooms[self._room_index] if self._room_index < len(self._rooms) else {}
        return self.async_show_form(
            step_id="room",
            data_schema=build_room_schema(default_room, self._room_index),
            errors=errors,
            description_placeholders={
                "current_room": str(self._room_index + 1),
                "room_count": str(self._room_count),
            },
        )
