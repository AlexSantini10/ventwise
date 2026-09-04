"""Options flow for VentWise."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    CONF_ROOM_KIND,
    CONF_ROOM_NAME,
    CONF_ROOM_SELECTION,
    CONF_ROOMS,
    NAME,
)
from .flow import (
    ConfigValidationError,
    build_room_schema,
    build_settings_schema,
    _localized_room_kind_label,
    normalize_settings_config,
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
        self._selected_room_index: int | None = None

    def _language(self) -> str | None:
        """Return the active HA language when available."""

        hass = getattr(self, "hass", None)
        config = getattr(hass, "config", None)
        return getattr(config, "language", None)

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show the small top-level navigation menu."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        _, current_rooms = split_config_data(self._current_config)
        self._rooms = current_rooms
        self._room_index = len(current_rooms)
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "rooms"],
            description_placeholders={
                "room_count": str(len(current_rooms)),
            },
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        """Edit everyday, outdoor, and comfort settings on one screen."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(
                    normalize_settings_config(user_input, self._current_config)
                )
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="settings",
            data_schema=build_settings_schema(self._current_config),
            errors=errors,
        )

    async def async_step_rooms(self, user_input: dict[str, Any] | None = None):
        """Show room management actions."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        _, current_rooms = split_config_data(self._current_config)
        self._rooms = current_rooms
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
        """Add a normal room."""

        return await self._handle_room_step("room", user_input)

    async def async_step_add_macro_room(self, user_input: dict[str, Any] | None = None):
        """Add a macro-room."""

        return await self._handle_room_step("macro_room", user_input)

    async def async_step_edit_room(self, user_input: dict[str, Any] | None = None):
        """Pick a room to edit."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._selected_room_index = self._room_selection_index(user_input[CONF_ROOM_SELECTION])
            except (KeyError, ValueError):
                errors["base"] = "invalid_input"
            else:
                return await self.async_step_edit_room_details()

        return self.async_show_form(
            step_id="edit_room",
            data_schema=self._room_selection_schema(),
            errors=errors,
            description_placeholders={
                "room_count": str(len(self._rooms)),
            },
        )

    async def async_step_edit_room_details(self, user_input: dict[str, Any] | None = None):
        """Edit the selected room."""

        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")

        selected_room = self._rooms[self._selected_room_index]
        room_kind = str(selected_room.get(CONF_ROOM_KIND, "room"))
        return await self._handle_room_step(
            room_kind,
            user_input,
            room_index=self._selected_room_index,
            default_room=selected_room,
            step_id="edit_room_form" if room_kind == "room" else "edit_macro_room_form",
        )

    async def async_step_edit_room_form(self, user_input: dict[str, Any] | None = None):
        """Submit edits for a standard room."""

        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")
        selected_room = self._rooms[self._selected_room_index]
        return await self._handle_room_step(
            str(selected_room.get(CONF_ROOM_KIND, "room")),
            user_input,
            room_index=self._selected_room_index,
            default_room=selected_room,
            step_id="edit_room_form",
        )

    async def async_step_edit_macro_room_form(self, user_input: dict[str, Any] | None = None):
        """Submit edits for a macro-room."""

        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")
        selected_room = self._rooms[self._selected_room_index]
        return await self._handle_room_step(
            str(selected_room.get(CONF_ROOM_KIND, "macro_room")),
            user_input,
            room_index=self._selected_room_index,
            default_room=selected_room,
            step_id="edit_macro_room_form",
        )

    async def async_step_remove_room(self, user_input: dict[str, Any] | None = None):
        """Pick a room to remove."""

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
            step_id="remove_room",
            data_schema=self._room_selection_schema(),
            errors=errors,
            description_placeholders={
                "room_count": str(len(self._rooms)),
            },
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Save all staged settings and close the options flow."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")

        self._current_config[CONF_ROOMS] = deepcopy(self._rooms)
        return self.async_create_entry(title=NAME, data=self._result_data())

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
                room_input = {**(default_room or {}), **user_input}
                room = normalize_room_config(room_input, room_kind)
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
            data_schema=build_room_schema(
                default_room,
                self._room_index,
                room_kind,
                self._language(),
            ),
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

        return [
            self._room_selection_label(room, index, self._language())
            for index, room in enumerate(self._rooms)
        ]

    def _room_selection_index(self, room_label: str) -> int:
        """Resolve a selected room label back to its index."""

        options = self._room_selection_options()
        return options.index(room_label)

    @staticmethod
    def _room_selection_label(room: dict[str, Any], index: int, language: str | None = None) -> str:
        """Build a stable room label for dropdowns."""

        kind_value = str(room.get(CONF_ROOM_KIND, "room"))
        name = str(room.get(CONF_ROOM_NAME, f"{_localized_room_kind_label(kind_value, language)} {index + 1}")).strip()
        kind = _localized_room_kind_label(kind_value, language)
        return f"{index + 1}. {name} ({kind})"

    def _result_data(self) -> dict[str, Any]:
        data = dict(self._current_config)
        data[CONF_ROOMS] = deepcopy(self._rooms)
        return data
