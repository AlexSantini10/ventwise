"""Config flow for VentWise."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_ROOM_KIND, CONF_ROOM_NAME, CONF_ROOM_SELECTION, CONF_ROOMS, DOMAIN, NAME
from .flow import (
    ConfigValidationError,
    build_config_schema,
    build_room_schema,
    build_setup_overrides_schema,
    normalize_basic_config,
    normalize_room_config,
    normalize_setup_overrides_config,
    split_config_data,
)


class VentWiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._setup_data: dict[str, Any] = {}
        self._current_config: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []
        self._room_index = 0
        self._selected_room_index: int | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Collect the minimal setup required to start."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._setup_data = normalize_basic_config(user_input)
                self._current_config = dict(self._setup_data)
                self._rooms = []
                self._room_index = 0
                self._selected_room_index = None
                return await self.async_step_outdoor()
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="user",
            data_schema=build_config_schema(self._setup_data),
            errors=errors,
        )

    async def async_step_outdoor(self, user_input: dict[str, Any] | None = None):
        """Collect optional outdoor overrides."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(normalize_setup_overrides_config(user_input))
                return await self.async_step_rooms()
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="outdoor",
            data_schema=build_setup_overrides_schema(self._current_config),
            errors=errors,
            description_placeholders={
                "weather_source": str(self._current_config.get("outdoor_weather_entity_id", "")),
            },
        )

    async def async_step_rooms(self, user_input: dict[str, Any] | None = None):
        """Show room management actions during setup."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        _, current_rooms = split_config_data(self._current_config)
        self._rooms = current_rooms
        self._room_index = len(current_rooms)
        menu_options = ["add_room", "add_macro_room"]
        if self._rooms:
            menu_options.extend(["edit_room", "remove_room"])
        menu_options.append("finish")
        return self.async_show_menu(
            step_id="rooms",
            menu_options=menu_options,
            description_placeholders={
                "room_count": str(len(self._rooms)),
            },
        )

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None):
        """Add a normal room during initial setup."""

        return await self._handle_room_step("room", user_input)

    async def async_step_add_macro_room(self, user_input: dict[str, Any] | None = None):
        """Add a macro-room during initial setup."""

        return await self._handle_room_step("macro_room", user_input)

    async def async_step_edit_room(self, user_input: dict[str, Any] | None = None):
        """Pick a room to edit during setup."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._selected_room_index = self._room_selection_index(user_input[CONF_ROOM_SELECTION])
            except (KeyError, ValueError):
                errors["base"] = "invalid_input"
            else:
                return await self.async_step_edit_room_details()

        return self.async_show_form(
            step_id="edit_room_select",
            data_schema=self._room_selection_schema(),
            errors=errors,
            description_placeholders={
                "room_count": str(len(self._rooms)),
            },
        )

    async def async_step_edit_room_details(self, user_input: dict[str, Any] | None = None):
        """Edit the selected room during setup."""

        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")

        selected_room = self._rooms[self._selected_room_index]
        room_kind = str(selected_room.get(CONF_ROOM_KIND, "room"))
        step_id = "edit_room_form" if room_kind == "room" else "edit_macro_room_form"
        return await self._handle_room_step(
            room_kind,
            user_input,
            room_index=self._selected_room_index,
            default_room=selected_room,
            step_id=step_id,
        )

    async def async_step_remove_room(self, user_input: dict[str, Any] | None = None):
        """Pick a room to remove during setup."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                room_index = self._room_selection_index(user_input[CONF_ROOM_SELECTION])
            except (KeyError, ValueError):
                errors["base"] = "invalid_input"
            else:
                self._rooms.pop(room_index)
                self._current_config[CONF_ROOMS] = deepcopy(self._rooms)
                self._selected_room_index = None
                return await self.async_step_rooms()

        return self.async_show_form(
            step_id="remove_room_select",
            data_schema=self._room_selection_schema(),
            errors=errors,
            description_placeholders={
                "room_count": str(len(self._rooms)),
            },
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Finish the initial setup."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        self._current_config[CONF_ROOMS] = deepcopy(self._rooms)
        return self.async_create_entry(title=NAME, data={}, options=self._result_data())

    async def _handle_room_step(
        self,
        room_kind: str,
        user_input: dict[str, Any] | None = None,
        *,
        room_index: int | None = None,
        default_room: dict[str, Any] | None = None,
        step_id: str | None = None,
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                room = normalize_room_config(user_input, room_kind)
                if room_index is None:
                    self._rooms.append(room)
                else:
                    self._rooms[room_index] = room
                self._current_config[CONF_ROOMS] = deepcopy(self._rooms)
                self._selected_room_index = None
                return await self.async_step_rooms()
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        default_room = default_room or {}
        self._room_index = room_index if room_index is not None else len(self._rooms)
        return self.async_show_form(
            step_id=step_id or ("add_room" if room_kind == "room" else "add_macro_room"),
            data_schema=build_room_schema(default_room, self._room_index, room_kind),
            errors=errors,
            description_placeholders={
                "current_room": str(self._room_index + 1),
            },
        )

    def _room_selection_schema(self) -> vol.Schema:
        """Create the room selector schema used by edit/remove actions."""

        return vol.Schema(
            {
                vol.Required(CONF_ROOM_SELECTION): SelectSelector(
                    SelectSelectorConfig(options=self._room_selection_options())
                )
            }
        )

    def _room_selection_options(self) -> list[str]:
        """Return readable room labels for selection forms."""

        return [self._room_selection_label(room, index) for index, room in enumerate(self._rooms)]

    def _room_selection_index(self, room_label: str) -> int:
        """Resolve a selected room label back to its index."""

        options = self._room_selection_options()
        return options.index(room_label)

    @staticmethod
    def _room_selection_label(room: dict[str, Any], index: int) -> str:
        """Build a stable room label for dropdowns."""

        name = str(room.get(CONF_ROOM_NAME, f"Room {index + 1}")).strip()
        kind = str(room.get(CONF_ROOM_KIND, "room")).replace("_", " ")
        return f"{index + 1}. {name} ({kind})"

    def _result_data(self) -> dict[str, Any]:
        data = dict(self._current_config)
        data[CONF_ROOMS] = deepcopy(self._rooms)
        return data


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""

        from .options_flow import VentWiseOptionsFlowHandler

        return VentWiseOptionsFlowHandler(config_entry)
