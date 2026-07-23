"""Switch platform for VentWise."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity, VentWiseRoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up switch entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    entities: list[SwitchEntity] = [
        MasterEnableSwitch(coordinator),
        AutomaticComfortTemperatureSwitch(coordinator),
        QuietHoursEnableSwitch(coordinator),
        NotificationEnableSwitch(coordinator),
    ]
    for room in coordinator.config.rooms:
        entities.extend(
            [
                RoomEnableSwitch(coordinator, room),
                RoomTargetTemperatureOverrideEnableSwitch(coordinator, room),
                RoomTargetHumidityOverrideEnableSwitch(coordinator, room),
            ]
        )
    async_add_entities(entities)


class MasterEnableSwitch(VentWiseEntity, SwitchEntity):
    """Master enable switch for the integration."""

    _attr_icon = "mdi:toggle-switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "master_enable", "Integration enabled")

    @property
    def is_on(self) -> bool:
        return self.coordinator.config.enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_enabled(False)


class NotificationEnableSwitch(VentWiseEntity, SwitchEntity):
    """Enable or disable notifications only."""

    _attr_icon = "mdi:bell-switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "notification_enable", "Notifications enabled")

    @property
    def is_on(self) -> bool:
        return self.coordinator.config.notification_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_notification_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_notification_enabled(False)


class AutomaticComfortTemperatureSwitch(VentWiseEntity, SwitchEntity):
    """Enable or disable automatic comfort temperature."""

    _attr_icon = "mdi:thermostat-auto"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "auto_comfort_temperature", "Adaptive comfort temperature")

    @property
    def is_on(self) -> bool:
        return self.coordinator.config.auto_comfort_temperature_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_auto_comfort_temperature_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_auto_comfort_temperature_enabled(False)


class QuietHoursEnableSwitch(VentWiseEntity, SwitchEntity):
    """Enable or disable quiet hours globally."""

    _attr_icon = "mdi:bell-sleep"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "quiet_hours_enable", "Quiet hours enabled")

    @property
    def is_on(self) -> bool:
        return self.coordinator.config.quiet_hours_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_quiet_hours_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_quiet_hours_enabled(False)


class RoomEnableSwitch(VentWiseRoomEntity, SwitchEntity):
    """Enable or disable a single room."""

    _attr_icon = "mdi:home-switch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(coordinator, room, "enabled", f"Enable {room.name}")

    @property
    def is_on(self) -> bool:
        return self.room.enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_room_enabled(self.room.room_id or self.room.name, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_room_enabled(self.room.room_id or self.room.name, False)


class RoomTargetTemperatureOverrideEnableSwitch(VentWiseRoomEntity, SwitchEntity):
    """Enable or disable the room comfort temperature override."""

    _attr_icon = "mdi:thermostat-box"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(
            coordinator,
            room,
            "target_temperature_override_enabled",
            f"{room.name} temperature override enabled",
        )

    @property
    def is_on(self) -> bool:
        return self.room.target_temperature_c_override_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_room_target_temperature_override_enabled(
            self.room.room_id or self.room.name,
            True,
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_room_target_temperature_override_enabled(
            self.room.room_id or self.room.name,
            False,
        )


class RoomTargetHumidityOverrideEnableSwitch(VentWiseRoomEntity, SwitchEntity):
    """Enable or disable the room comfort humidity override."""

    _attr_icon = "mdi:water-percent"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(
            coordinator,
            room,
            "target_humidity_override_enabled",
            f"{room.name} humidity override enabled",
        )

    @property
    def is_on(self) -> bool:
        return self.room.target_humidity_percent_override_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_room_target_humidity_override_enabled(
            self.room.room_id or self.room.name,
            True,
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_room_target_humidity_override_enabled(
            self.room.room_id or self.room.name,
            False,
        )
