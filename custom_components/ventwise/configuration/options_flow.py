"""Options flow for VentWise."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from ..const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_COOLDOWN_MINUTES,
    CONF_SOFT_OUTDOOR_THRESHOLD_C,
    DEFAULT_AUTO_COMFORT_TEMPERATURE,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_SOFT_OUTDOOR_THRESHOLD_C,
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
    build_daily_options_schema,
    build_recommendation_options_schema,
    build_manual_sources_schema,
    build_air_quality_options_schema,
    build_air_quality_source_selection_schema,
    build_air_quality_source_schema,
    build_diagnostics_options_schema,
    build_unit_schema,
    _localized_room_kind_label,
    normalize_settings_config,
    normalize_basic_config,
    normalize_advanced_config,
    normalize_outdoor_source_config,
    normalize_outdoor_override_config,
    normalize_unit_config,
    normalize_room_config,
    split_config_data,
    validate_room_automation_confirmation,
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
        self._selected_air_quality_source: str | None = None

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
            menu_options=["daily", "rooms", "advanced", "units"],
            description_placeholders={
                "room_count": str(len(current_rooms)),
            },
        )

    async def async_step_units(self, user_input: dict[str, Any] | None = None):
        """Change display units without reinterpreting saved values."""

        if user_input is not None:
            self._current_config = {
                **self._current_config,
                **normalize_unit_config(user_input),
            }
            return self.async_create_entry(title=NAME, data=self._result_data())
        return self.async_show_form(
            step_id="units",
            data_schema=build_unit_schema(self._current_config),
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        """Edit everyday, outdoor, and comfort settings on one screen."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                candidate_config = {
                    **self._current_config,
                    **normalize_settings_config(user_input, self._current_config),
                }
                validate_room_automation_confirmation(
                    self._rooms, candidate_config, self.hass
                )
                self._current_config = candidate_config
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="settings",
            data_schema=build_settings_schema(self._current_config, self.hass),
            errors=errors,
        )

    async def async_step_daily(self, user_input: dict[str, Any] | None = None):
        """Edit settings used in ordinary day-to-day use."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config = normalize_basic_config({**self._current_config, **user_input})
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(step_id="daily", data_schema=build_daily_options_schema(self._current_config, self.hass), errors=errors)

    async def async_step_advanced(self, user_input: dict[str, Any] | None = None):
        """Show technical settings."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")
        return self.async_show_menu(step_id="advanced", menu_options=["recommendations", "manual_sources", "air_quality", "diagnostics"])

    async def async_step_recommendations(self, user_input: dict[str, Any] | None = None):
        return await self._save_advanced_form("recommendations", build_recommendation_options_schema, user_input, validate_co2=True)

    async def async_step_manual_sources(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = normalize_outdoor_source_config({**self._current_config, **user_input})
                self._current_config = normalize_outdoor_override_config(data, data)
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(step_id="manual_sources", data_schema=build_manual_sources_schema(self._current_config), errors=errors)

    async def async_step_air_quality(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_abort(reason="invalid_step")
        return self.async_show_menu(step_id="air_quality", menu_options=["air_quality_global", "air_quality_source_select"])

    async def async_step_air_quality_global(self, user_input: dict[str, Any] | None = None):
        return await self._save_advanced_form("air_quality_global", build_air_quality_options_schema, user_input)

    async def async_step_air_quality_source_select(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            from ..const import AIR_QUALITY_VARIABLES
            source = user_input.get("air_quality_source")
            if source in AIR_QUALITY_VARIABLES:
                self._selected_air_quality_source = str(source)
                return await self.async_step_air_quality_source()
            errors["air_quality_source"] = "invalid_input"
        return self.async_show_form(step_id="air_quality_source_select", data_schema=build_air_quality_source_selection_schema(), errors=errors)

    async def async_step_air_quality_source(self, user_input: dict[str, Any] | None = None):
        if self._selected_air_quality_source is None:
            return self.async_abort(reason="invalid_step")
        return await self._save_advanced_form("air_quality_source", lambda defaults: build_air_quality_source_schema(defaults, self._selected_air_quality_source), user_input)

    async def async_step_diagnostics(self, user_input: dict[str, Any] | None = None):
        return await self._save_advanced_form("diagnostics", build_diagnostics_options_schema, user_input)

    async def _save_advanced_form(self, step_id: str, schema_builder, user_input, *, validate_co2: bool = False):
        """Save one advanced group, retaining all values not displayed by it."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = dict(self._current_config)
                data.setdefault(CONF_AUTO_COMFORT_TEMPERATURE, DEFAULT_AUTO_COMFORT_TEMPERATURE)
                data.setdefault(CONF_SOFT_OUTDOOR_THRESHOLD_C, DEFAULT_SOFT_OUTDOOR_THRESHOLD_C)
                data.setdefault(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES)
                sources = data.get("air_quality_entity_ids", {})
                policies = data.get("exposure_policies", {})
                from ..const import AIR_QUALITY_VARIABLES
                for kind in AIR_QUALITY_VARIABLES:
                    if isinstance(sources, dict) and kind in sources:
                        data[f"air_quality_{kind}_entity_id"] = sources[kind]
                    if isinstance(policies, dict) and isinstance(policies.get(kind), dict):
                        policy = policies[kind]
                        data.update({f"air_quality_{kind}_policy": policy.get("mode", "ignore"), f"air_quality_{kind}_threshold": policy.get("threshold"), f"air_quality_{kind}_unit": policy.get("unit", ""), f"air_quality_{kind}_averaging_period": policy.get("averaging_period", "instant")})
                data.update(user_input)
                candidate = normalize_advanced_config(data)
                if validate_co2 and candidate.get("co2_enabled") and not candidate.get("co2_entity_id") and not any(room.get("co2_entity_id") for room in self._rooms):
                    raise ConfigValidationError("co2_entity_id")
                validate_room_automation_confirmation(self._rooms, candidate, self.hass)
                self._current_config = candidate
                self._selected_air_quality_source = None
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(step_id=step_id, data_schema=schema_builder(self._current_config), errors=errors)

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
        """Choose Base or Advanced settings for the selected room."""

        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")

        if user_input is not None:
            return self.async_abort(reason="invalid_step")
        return self.async_show_menu(
            step_id="edit_room_details",
            menu_options=["edit_room_base", "edit_room_advanced"],
        )

    async def async_step_edit_room_base(self, user_input: dict[str, Any] | None = None):
        """Edit the base fields of a selected room."""

        return await self._handle_selected_room_section(user_input, "base")

    async def async_step_edit_room_advanced(self, user_input: dict[str, Any] | None = None):
        """Edit the advanced fields of a selected room."""

        return await self._handle_selected_room_section(user_input, "advanced")

    async def _handle_selected_room_section(self, user_input: dict[str, Any] | None, section: str):
        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")
        selected_room = self._rooms[self._selected_room_index]
        return await self._handle_room_step(
            str(selected_room.get(CONF_ROOM_KIND, "room")),
            user_input,
            room_index=self._selected_room_index,
            default_room=selected_room,
            step_id=f"edit_room_{section}",
            section=section,
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
        section: str | None = "base",
    ):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                room_input = {**(default_room or {}), **user_input}
                room = normalize_room_config(room_input, room_kind)
                candidate_rooms = list(self._rooms)
                if room_index is None:
                    candidate_rooms.append(room)
                else:
                    candidate_rooms[room_index] = room
                validate_room_automation_confirmation(
                    candidate_rooms, self._current_config, self.hass
                )
                self._rooms = candidate_rooms
                self._current_config[CONF_ROOMS] = deepcopy(candidate_rooms)
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
                section,
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
