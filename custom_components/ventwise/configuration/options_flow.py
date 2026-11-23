"""Options flow for VentWise."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    import probatio as vol
except ModuleNotFoundError:  # Home Assistant versions before the probatio migration
    import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from ..const import (
    CONF_ROOM_CO2_ENTITY_ID,
    CONF_ROOM_CO2_UNIT,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_HUMIDITY_UNIT,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMPERATURE_ENTITY_ID,
    CONF_ROOM_HUMIDITY_ENTITY_ID,
    CONF_ROOM_REMOVE_CONFIRMATION,
    CONF_ROOM_SELECTION,
    CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS,
    CONF_ROOMS,
    CONF_TEMPERATURE_UNIT,
    CONF_WIND_SPEED_UNIT,
    DEFAULT_TEMPERATURE_UNIT,
    DEFAULT_WIND_SPEED_UNIT,
    NAME,
)
from .configuration_helpers import (
    ConfigValidationError,
    build_room_schema,
    build_room_unit_schema,
    build_comfort_schema,
    build_notification_schema,
    build_override_schema,
    build_unit_schema,
    _localized_room_kind_label,
    normalize_room_config,
    normalize_comfort_config,
    normalize_notification_config,
    normalize_override_config,
    normalize_unit_config,
    outdoor_source_unit_summary,
    source_unit_summary,
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
        self._pending_room_input: dict[str, Any] | None = None
        self._pending_room_kind: str | None = None
        self._pending_room_index: int | None = None

    def _language(self) -> str | None:
        hass = getattr(self, "hass", None)
        return getattr(getattr(hass, "config", None), "language", None)

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_abort(reason="invalid_step")
        return self.async_show_menu(
            step_id="init",
            menu_options=["units", "comfort", "notifications", "overrides", "rooms"],
            description_placeholders={"room_count": str(len(self._rooms))},
        )

    async def async_step_units(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._current_config.update(normalize_unit_config(user_input))
            return self.async_create_entry(title=NAME, data=self._result_data())
        return self.async_show_form(
            step_id="units", data_schema=build_unit_schema(self._current_config)
        )

    async def async_step_comfort(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(
                    normalize_comfort_config(user_input, self._current_config)
                )
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="comfort",
            data_schema=build_comfort_schema(self._current_config, self.hass),
            errors=errors,
            description_placeholders={
                "temperature_unit": self._current_config.get(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT),
                "wind_speed_unit": self._current_config.get(CONF_WIND_SPEED_UNIT, DEFAULT_WIND_SPEED_UNIT),
            },
        )

    async def async_step_notifications(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(
                    normalize_notification_config(user_input, self._current_config)
                )
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="notifications",
            data_schema=build_notification_schema(self._current_config, self.hass),
            errors=errors,
        )

    async def async_step_overrides(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._current_config.update(
                    normalize_override_config(user_input, self._current_config)
                )
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="overrides",
            data_schema=build_override_schema(self._current_config, self.hass),
            errors=errors,
            description_placeholders={
                "sensor_units_summary": outdoor_source_unit_summary(self._current_config, self.hass),
            },
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        """Compatibility alias for older flow links."""

        return await self.async_step_comfort(user_input)

    async def async_step_rooms(self, user_input: dict[str, Any] | None = None):
        """Select an existing room or the final add-room option."""

        _, self._rooms = split_config_data(self._current_config)
        if user_input is not None:
            selection = user_input.get(CONF_ROOM_SELECTION)
            if selection == self._add_room_label():
                return await self.async_step_add_room()
            try:
                self._selected_room_index = self._room_selection_index(selection)
            except (TypeError, ValueError):
                return self.async_show_form(
                    step_id="edit_room_select",
                    data_schema=self._room_selection_schema(),
                    errors={"base": "invalid_input"},
                )
            return await self.async_step_room_actions()
        return self.async_show_form(
            step_id="edit_room_select",
            data_schema=self._room_selection_schema(),
            description_placeholders={"room_count": str(len(self._rooms))},
        )

    async def async_step_edit_room_select(self, user_input: dict[str, Any] | None = None):
        """Handle the translated room selector step."""

        return await self.async_step_rooms(user_input)

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None):
        return await self._handle_room_step("room", user_input)

    async def async_step_room_actions(self, user_input: dict[str, Any] | None = None):
        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return await self.async_step_rooms()
        if user_input is not None:
            return self.async_abort(reason="invalid_step")
        return self.async_show_menu(
            step_id="rooms",
            menu_options=["edit_room", "remove_room"],
            description_placeholders={
                "room_name": str(self._rooms[self._selected_room_index].get(CONF_ROOM_NAME, ""))
            },
        )

    async def async_step_edit_room(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_edit_room_details(user_input)

    async def async_step_edit_room_details(self, user_input: dict[str, Any] | None = None):
        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return self.async_abort(reason="invalid_step")
        selected_room = self._rooms[self._selected_room_index]
        return await self._handle_room_step(
            "room",
            user_input,
            room_index=self._selected_room_index,
            default_room=selected_room,
            step_id="edit_room_form",
        )

    async def async_step_edit_room_form(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_edit_room_details(user_input)

    async def async_step_remove_room(self, user_input: dict[str, Any] | None = None):
        """Show explicit confirmation before deleting the selected room."""

        if user_input is not None:
            try:
                self._selected_room_index = self._room_selection_index(
                    user_input[CONF_ROOM_SELECTION]
                )
            except (KeyError, TypeError, ValueError):
                return await self.async_step_room_actions()
        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return await self.async_step_rooms()
        return self.async_show_form(
            step_id="remove_room_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_ROOM_REMOVE_CONFIRMATION, default=False): cv.boolean}
            ),
            description_placeholders={
                "room_name": str(self._rooms[self._selected_room_index].get(CONF_ROOM_NAME, ""))
            },
        )

    async def async_step_confirm_remove_room(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            return await self.async_step_remove_room()
        if not user_input.get(CONF_ROOM_REMOVE_CONFIRMATION, False):
            return await self.async_step_room_actions()
        if self._selected_room_index is None or self._selected_room_index >= len(self._rooms):
            return await self.async_step_rooms()
        self._rooms.pop(self._selected_room_index)
        self._selected_room_index = None
        self._persist_rooms()
        return self.async_create_entry(title=NAME, data=self._result_data())

    async def async_step_remove_room_select(self, user_input: dict[str, Any] | None = None):
        """Handle the translated removal confirmation step."""

        return await self.async_step_confirm_remove_room(user_input)

    async def async_step_finish(self, user_input: dict[str, Any] | None = None):
        """Close the room screen without applying additional changes."""

        if user_input is not None:
            return self.async_abort(reason="invalid_step")
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
                if room_index is not None:
                    for field, empty_value in (
                        (CONF_ROOM_HUMIDITY_ENTITY_ID, None),
                        (CONF_ROOM_HUMIDITY_UNIT, None),
                        (CONF_ROOM_CO2_ENTITY_ID, None),
                        (CONF_ROOM_CO2_UNIT, None),
                        (CONF_ROOM_WINDOW_SENSOR_ENTITY_IDS, []),
                    ):
                        if field not in user_input:
                            room_input[field] = empty_value
                room = normalize_room_config(room_input, room_kind)
                pending_index = room_index if room_index is not None else len(self._rooms)
                if pending_index == len(self._rooms):
                    self._rooms.append(room)
                else:
                    self._rooms[pending_index] = room
                self._persist_rooms()
                self._pending_room_input = room
                self._pending_room_kind = room_kind
                self._pending_room_index = pending_index
                return await self.async_step_room_units()
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        default_room = default_room or {}
        self._room_index = room_index if room_index is not None else len(self._rooms)
        return self.async_show_form(
            step_id=step_id or "add_room",
            data_schema=build_room_schema(
                default_room, self._room_index, "room", self._language()
            ),
            errors=errors,
            description_placeholders={
                "current_room": str(self._room_index + 1),
                "temperature_unit": self._current_config.get(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT),
            },
        )

    async def async_step_room_units(self, user_input: dict[str, Any] | None = None):
        """Confirm the units used by the selected room sources."""
        errors: dict[str, str] = {}
        if self._pending_room_input is None or self._pending_room_kind is None:
            return await self.async_step_rooms()
        if user_input is not None:
            try:
                room_input = {**self._pending_room_input, **user_input}
                room = normalize_room_config(room_input, self._pending_room_kind)
                candidate_rooms = list(self._rooms)
                if self._pending_room_index is None:
                    candidate_rooms.append(room)
                else:
                    candidate_rooms[self._pending_room_index] = room
                self._rooms = candidate_rooms
                self._selected_room_index = None
                self._persist_rooms()
                self._pending_room_input = None
                self._pending_room_kind = None
                self._pending_room_index = None
                return self.async_create_entry(title=NAME, data=self._result_data())
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="room_units",
            data_schema=build_room_unit_schema(self._pending_room_input, self.hass),
            errors=errors,
            description_placeholders={
                "sensor_units_summary": source_unit_summary(
                    tuple(
                        (label, self._pending_room_input.get(entity_field), measurement)
                        for label, entity_field, measurement in (
                            ("temperature", CONF_ROOM_TEMPERATURE_ENTITY_ID, "temperature"),
                            ("humidity", CONF_ROOM_HUMIDITY_ENTITY_ID, "humidity"),
                            ("CO₂", CONF_ROOM_CO2_ENTITY_ID, "co2"),
                        )
                    ),
                    self.hass,
                )
            },
        )

    def _persist_rooms(self) -> None:
        """Keep room edits in the flow until the final save."""

        self._current_config[CONF_ROOMS] = deepcopy(self._rooms)

    def _room_selection_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_ROOM_SELECTION): SelectSelector(
                    SelectSelectorConfig(options=self._room_selection_options())
                )
            }
        )

    def _room_selection_options(self) -> list[str]:
        options = [
            self._room_selection_label(room, index, self._language())
            for index, room in enumerate(self._rooms)
        ]
        options.append(self._add_room_label())
        return options

    def _add_room_label(self) -> str:
        labels = {
            "it": "Aggiungi stanza",
            "es": "Añadir habitación",
            "fr": "Ajouter une pièce",
            "de": "Raum hinzufügen",
            "ru": "Добавить комнату",
            "zh-hans": "添加房间",
        }
        language = (self._language() or "en").replace("_", "-").lower()
        return labels.get(language, labels.get(language.split("-", 1)[0], "Add room"))

    def _room_selection_index(self, room_label: str) -> int:
        if room_label == self._add_room_label():
            raise ValueError("add-room selection is not an existing room")
        return self._room_selection_options().index(room_label)

    @staticmethod
    def _room_selection_label(
        room: dict[str, Any], index: int, language: str | None = None
    ) -> str:
        name = str(room.get(CONF_ROOM_NAME, f"Room {index + 1}")).strip()
        return f"{index + 1}. {name} ({_localized_room_kind_label('room', language)})"

    def _result_data(self) -> dict[str, Any]:
        data = dict(self._current_config)
        data[CONF_ROOMS] = deepcopy(self._rooms)
        return data
