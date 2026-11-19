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
    CONF_CO2_ENABLED,
    CONF_CO2_ENTITY_ID,
    CONF_ROOM_CO2_ENABLED,
    CONF_ROOM_CO2_ENTITY_ID,
    CONF_ROOMS,
    CONF_SAFETY_BYPASS_QUIET_HOURS,
    CONF_TEMPERATURE_UNIT,
    CONF_WIND_SPEED_UNIT,
    DEFAULT_TEMPERATURE_UNIT,
    DEFAULT_WIND_SPEED_UNIT,
    DEFAULT_SAFETY_BYPASS_QUIET_HOURS,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)
_CONFIG_ENTRY_VERSION = 5
_LEGACY_RUNTIME_KEYS = (
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .application.coordinator import VentWiseCoordinator
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

    migrated_data = dict(entry.data)
    migrated_options = dict(entry.options)
    migrated_options.setdefault(CONF_TEMPERATURE_UNIT, DEFAULT_TEMPERATURE_UNIT)
    migrated_options.setdefault(CONF_WIND_SPEED_UNIT, DEFAULT_WIND_SPEED_UNIT)
    migrated_options.setdefault(
        CONF_SAFETY_BYPASS_QUIET_HOURS,
        DEFAULT_SAFETY_BYPASS_QUIET_HOURS,
    )
    if entry.version < 5:
        legacy_enabled = bool(
            migrated_options.get(CONF_CO2_ENABLED, migrated_data.get(CONF_CO2_ENABLED, False))
        )
        legacy_entity = migrated_options.get(
            CONF_CO2_ENTITY_ID, migrated_data.get(CONF_CO2_ENTITY_ID)
        )
        rooms = migrated_options.get(CONF_ROOMS, migrated_data.get(CONF_ROOMS, []))
        if isinstance(rooms, list) and (rooms or legacy_entity or legacy_enabled):
            migrated_rooms = []
            for raw_room in rooms:
                room = dict(raw_room) if isinstance(raw_room, Mapping) else {}
                room_entity = room.get(CONF_ROOM_CO2_ENTITY_ID) or legacy_entity
                room.setdefault(CONF_ROOM_CO2_ENTITY_ID, room_entity)
                room.setdefault(CONF_ROOM_CO2_ENABLED, bool(legacy_enabled and room_entity))
                migrated_rooms.append(room)
            target = migrated_options if CONF_ROOMS in migrated_options else migrated_data
            target[CONF_ROOMS] = migrated_rooms
        migrated_data.pop(CONF_CO2_ENABLED, None)
        migrated_data.pop(CONF_CO2_ENTITY_ID, None)
        migrated_options.pop(CONF_CO2_ENABLED, None)
        migrated_options.pop(CONF_CO2_ENTITY_ID, None)
    runtime_state = migrated_options.get(
        CONF_RUNTIME_STATE, migrated_data.get(CONF_RUNTIME_STATE)
    )
    if not isinstance(runtime_state, Mapping):
        legacy_runtime_state: dict[str, Any] = {}
        for key in _LEGACY_RUNTIME_KEYS:
            if key in migrated_data:
                legacy_runtime_state[key] = migrated_data.pop(key)
            elif key in migrated_options:
                legacy_runtime_state[key] = migrated_options.pop(key)
        if legacy_runtime_state:
            migrated_options[CONF_RUNTIME_STATE] = legacy_runtime_state

    _LOGGER.info(
        "Migrating VentWise config entry %s from version %s to %s",
        entry.entry_id,
        entry.version,
        _CONFIG_ENTRY_VERSION,
    )
    _LOGGER.debug(
        "VentWise config entry %s migration preserves %d option keys",
        entry.entry_id,
        len(migrated_data) + len(migrated_options),
    )
    hass.config_entries.async_update_entry(
        entry,
        data=migrated_data,
        options=migrated_options,
        version=_CONFIG_ENTRY_VERSION,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    from homeassistant.const import Platform

    from .application.coordinator import VentWiseCoordinator

    try:
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
                Platform.BUTTON,
                Platform.SENSOR,
                Platform.NUMBER,
                Platform.SWITCH,
                Platform.TIME,
            ],
        )
    except Exception:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        _LOGGER.exception("Unable to set up VentWise")
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    from homeassistant.const import Platform

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        [
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.SWITCH,
            Platform.TIME,
        ],
    )
    if unload_ok:
        domain_data = hass.data.get(DOMAIN, {})
        domain_data.pop(entry.entry_id, None)
    else:
        _LOGGER.error("VentWise could not unload all platforms")
    return unload_ok
