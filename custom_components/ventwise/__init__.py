"""VentWise integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_STATE,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)
_CONFIG_ENTRY_VERSION = 2
_LEGACY_RUNTIME_KEYS = (
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import VentWiseCoordinator
    VentWiseCoordinator = Any  # type: ignore[assignment]
else:
    ConfigEntry = Any  # type: ignore[assignment]
    HomeAssistant = Any  # type: ignore[assignment]
    VentWiseCoordinator = Any  # type: ignore[assignment]


@dataclass(slots=True)
class IntegrationRuntimeData:
    """Runtime storage for the integration."""

    coordinator: VentWiseCoordinator


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate persisted VentWise configuration without losing user settings."""

    if entry.version > _CONFIG_ENTRY_VERSION:
        _LOGGER.error(
            "VentWise config entry %s uses unsupported future version %s (supported: %s)",
            entry.entry_id,
            entry.version,
            _CONFIG_ENTRY_VERSION,
        )
        return False
    if entry.version == _CONFIG_ENTRY_VERSION:
        return True

    merged_options = {**entry.data, **entry.options}
    runtime_state = merged_options.get(CONF_RUNTIME_STATE)
    if not isinstance(runtime_state, Mapping):
        legacy_runtime_state = {
            key: merged_options.pop(key)
            for key in _LEGACY_RUNTIME_KEYS
            if key in merged_options
        }
        if legacy_runtime_state:
            merged_options[CONF_RUNTIME_STATE] = legacy_runtime_state

    _LOGGER.info(
        "Migrating VentWise config entry %s from version %s to %s",
        entry.entry_id,
        entry.version,
        _CONFIG_ENTRY_VERSION,
    )
    _LOGGER.debug(
        "VentWise config entry %s migration preserves %d option keys",
        entry.entry_id,
        len(merged_options),
    )
    hass.config_entries.async_update_entry(
        entry,
        data={},
        options=merged_options,
        version=_CONFIG_ENTRY_VERSION,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    from homeassistant.const import Platform

    from .coordinator import VentWiseCoordinator

    coordinator = VentWiseCoordinator(
        hass,
        entry,
        {**entry.data, **entry.options},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = IntegrationRuntimeData(
        coordinator=coordinator
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(
        entry,
        [
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.SWITCH,
            Platform.TIME,
        ],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    from homeassistant.const import Platform

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.SWITCH,
            Platform.TIME,
        ],
    )
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
    return unload_ok
