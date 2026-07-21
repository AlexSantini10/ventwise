"""Config flow for VentWise."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, NAME
from .flow import ConfigValidationError, build_config_schema, normalize_basic_config


class VentWiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._setup_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Collect the minimal setup required to start."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._setup_data = normalize_basic_config(user_input)
                return self.async_create_entry(title=NAME, data={}, options=self._setup_data)
            except ConfigValidationError as err:
                errors[err.field] = err.message
            except (ValueError, TypeError, KeyError):
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="user",
            data_schema=build_config_schema(self._setup_data),
            errors=errors,
        )


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""

        from .options_flow import VentWiseOptionsFlowHandler

        return VentWiseOptionsFlowHandler(config_entry)
