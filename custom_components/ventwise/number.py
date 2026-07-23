"""Number platform for VentWise."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_STABILITY_MINUTES, CONF_TARGET_HUMIDITY_PERCENT, CONF_TARGET_TEMPERATURE_C
from .coordinator import VentWiseCoordinator
from .entity import VentWiseEntity, VentWiseRoomEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up number entities from a config entry."""

    coordinator = hass.data[entry.domain][entry.entry_id].coordinator
    entities: list[NumberEntity] = [
        ComfortTemperatureNumber(coordinator),
        ComfortHumidityNumber(coordinator),
        StabilityMinutesNumber(coordinator),
    ]
    for room in coordinator.config.rooms:
        entities.extend(
            [
                RoomTargetTemperatureOverrideNumber(coordinator, room),
                RoomTargetHumidityOverrideNumber(coordinator, room),
            ]
        )
    async_add_entities(entities)


class ComfortTemperatureNumber(VentWiseEntity, NumberEntity):
    """Global indoor comfort temperature."""

    _attr_icon = "mdi:thermometer"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 10.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "comfort_temperature", "Indoor comfort temperature")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.config.target_temperature_c)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_target_temperature(float(value))


class ComfortHumidityNumber(VentWiseEntity, NumberEntity):
    """Global indoor comfort humidity."""

    _attr_icon = "mdi:water-percent"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 20.0
    _attr_native_max_value = 80.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "comfort_humidity", "Indoor comfort humidity")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.config.target_humidity_percent)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_target_humidity(float(value))


class StabilityMinutesNumber(VentWiseEntity, NumberEntity):
    """Global minimum stability requirement in minutes."""

    _attr_icon = "mdi:timer-sand"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 24 * 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "stability_minutes", "Stability window")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.config.stability_minutes)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_stability_minutes(int(value))


class RoomTargetTemperatureOverrideNumber(VentWiseRoomEntity, NumberEntity):
    """Room-specific comfort temperature override."""

    _attr_icon = "mdi:thermometer"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 10.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "°C"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(
            coordinator,
            room,
            "target_temperature_override",
            f"{room.name} comfort temperature override",
        )

    @property
    def native_value(self) -> float | None:
        return self.room.target_temperature_c_override

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_target_temperature_override(
            self.room.room_id or self.room.name,
            float(value),
        )


class RoomTargetHumidityOverrideNumber(VentWiseRoomEntity, NumberEntity):
    """Room-specific comfort humidity override."""

    _attr_icon = "mdi:water-percent"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 20.0
    _attr_native_max_value = 80.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(
            coordinator,
            room,
            "target_humidity_override",
            f"{room.name} comfort humidity override",
        )

    @property
    def native_value(self) -> float | None:
        return self.room.target_humidity_percent_override

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_target_humidity_override(
            self.room.room_id or self.room.name,
            float(value),
        )
