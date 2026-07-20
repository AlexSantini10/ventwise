"""Temperature Comfort Recommender integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME

PLATFORMS: list[str] = []


@dataclass(slots=True)
class IntegrationRuntimeData:
    """Runtime storage for the integration."""

    config: dict[str, Any]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration from YAML, if present."""

    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = IntegrationRuntimeData(
        config={**entry.data, **entry.options}
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)
    return True

