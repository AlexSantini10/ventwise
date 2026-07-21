"""Options flow for VentWise."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant import config_entries

from .const import CONF_ROOMS, DOMAIN, NAME
from .flow import (
    build_advanced_options_schema,
    build_basic_options_schema,
    build_room_schema,
    normalize_advanced_config,
    normalize_basic_config,
    normalize_room_config,
    split_config_data,
)


class VentWiseOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._current_config = {**config_entry.data, **config_entry.options}
        _, current_rooms = split_config_data(self._current_config)
        self._rooms = current_rooms
        self._room_index = len(current_rooms)

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show the options menu."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        _, current_rooms = split_config_data(self._current_config)
        self._rooms = current_rooms
        self._room_index = len(current_rooms)
        return self.async_show_menu(
            step_id="init",
            menu_options=["basic", "advanced", "rooms"],
            description_placeholders={
                "room_count": str(len(current_rooms)),
            },
        )

    async def async_step_basic(self, user_input: dict[str, Any] | None = None):
        """Edit the user-facing basic settings."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(normalize_basic_config(user_input))
                return self.async_create_entry(title=NAME, data=self._result_data())
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="basic",
            data_schema=build_basic_options_schema(self._current_config),
            errors=errors,
        )

    async def async_step_advanced(self, user_input: dict[str, Any] | None = None):
        """Edit the advanced settings."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(normalize_advanced_config(user_input))
                return self.async_create_entry(title=NAME, data=self._result_data())
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="advanced",
            data_schema=build_advanced_options_schema(self._current_config),
            errors=errors,
        )

    async def async_step_rooms(self, user_input: dict[str, Any] | None = None):
        """Show room management actions."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        _, current_rooms = split_config_data(self._current_config)
        self._rooms = current_rooms
        return self.async_show_menu(
            step_id="rooms",
            menu_options=["add_room", "add_macro_room", "finish"],
            description_placeholders={
                "room_count": str(len(self._rooms)),
            },
        )

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None):
        """Add a normal room."""

        return await self._handle_room_step("room", user_input)

    async def async_step_add_macro_room(self, user_input: dict[str, Any] | None = None):
        """Add a macro-room."""

        return await self._handle_room_step("macro_room", user_input)

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Finish room management."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        self._current_config[CONF_ROOMS] = deepcopy(self._rooms)
        return self.async_create_entry(title=NAME, data=self._result_data())

    async def _handle_room_step(
        self,
        room_kind: str,
        user_input: dict[str, Any] | None = None,
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                room = normalize_room_config(user_input, room_kind)
                self._rooms.append(room)
                self._current_config[CONF_ROOMS] = deepcopy(self._rooms)
                return await self.async_step_rooms()
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        default_room: dict[str, Any] = {}
        self._room_index = len(self._rooms)
        return self.async_show_form(
            step_id="add_room" if room_kind == "room" else "add_macro_room",
            data_schema=build_room_schema(default_room, self._room_index, room_kind),
            errors=errors,
            description_placeholders={
                "current_room": str(self._room_index + 1),
            },
        )

    def _result_data(self) -> dict[str, Any]:
        data = dict(self._current_config)
        data[CONF_ROOMS] = deepcopy(self._rooms)
        return data
