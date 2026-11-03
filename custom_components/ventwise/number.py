"""Number platform for VentWise."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
)
from .application.coordinator import VentWiseCoordinator
from .entities.base import VentWiseEntity, VentWiseRoomEntity
from .units import temperature_from_celsius, temperature_to_celsius
from .const import DEFAULT_TEMPERATURE_UNIT, UNIT_CELSIUS


class TemperatureNumberMixin:
    @property
    def native_unit_of_measurement(self):
        return getattr(self.coordinator.config, "temperature_unit", DEFAULT_TEMPERATURE_UNIT)

    @property
    def native_min_value(self):
        return temperature_from_celsius(10.0, self.native_unit_of_measurement)

    @property
    def native_max_value(self):
        return temperature_from_celsius(30.0, self.native_unit_of_measurement)

    @property
    def native_step(self):
        return 0.5 if self.native_unit_of_measurement == UNIT_CELSIUS else 1.0

    def _to_celsius(self, value: float) -> float:
        return temperature_to_celsius(value, self.native_unit_of_measurement)

    def _temperature(self, value: float | None) -> float | None:
        return temperature_from_celsius(value, self.native_unit_of_measurement)


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


class ComfortTemperatureNumber(TemperatureNumberMixin, VentWiseEntity, NumberEntity):
    """Global indoor comfort temperature."""

    _attr_icon = "mdi:thermometer"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: VentWiseCoordinator) -> None:
        super().__init__(coordinator, "comfort_temperature", "comfort_temperature")

    @property
    def native_value(self) -> float:
        return self._temperature(self.coordinator.config.target_temperature_c)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_target_temperature(self._to_celsius(float(value)))


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
        super().__init__(coordinator, "comfort_humidity", "comfort_humidity")

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
        super().__init__(coordinator, "stability_minutes", "recommendation_stability_window")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.config.stability_minutes)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_stability_minutes(int(value))


class RoomTargetTemperatureOverrideNumber(TemperatureNumberMixin, VentWiseRoomEntity, NumberEntity):
    """Room-specific comfort temperature override."""

    _attr_icon = "mdi:thermometer"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: VentWiseCoordinator, room) -> None:
        super().__init__(
            coordinator,
            room,
            "target_temperature_override",
            "temperature_override",
        )

    @property
    def native_value(self) -> float | None:
        return self._temperature(self.room.target_temperature_c_override)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_target_temperature_override(
            self.room.room_id or self.room.name,
            self._to_celsius(float(value)),
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
            "humidity_override",
        )

    @property
    def native_value(self) -> float | None:
        return self.room.target_humidity_percent_override

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_target_humidity_override(
            self.room.room_id or self.room.name,
            float(value),
        )
