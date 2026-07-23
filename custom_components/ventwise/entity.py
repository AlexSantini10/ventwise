"""Base entity helpers for the integration."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import VentWiseCoordinator
from .runtime import RoomConfig


ENTITY_NAME_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "weather_condition": "Weather condition",
        "average_perceived_indoor_temperature": "Average perceived indoor temperature",
        "perceived_outdoor_temperature": "Perceived outdoor temperature",
        "effective_comfort_temperature": "Effective comfort temperature",
        "suggested_comfort_temperature": "Suggested comfort temperature",
        "outdoor_temperature": "Outdoor temperature",
        "outdoor_humidity": "Outdoor humidity",
        "wind_speed": "Outdoor wind speed",
        "recommendation": "Recommendation",
        "recommendation_score": "Recommendation score",
        "recommendation_reason": "Recommendation reason",
        "perceived_indoor_temperature": "Perceived indoor temperature",
        "temperature": "Indoor temperature",
        "indoor_humidity": "Indoor humidity",
        "integration_enabled": "Integration enabled",
        "notifications_enabled": "Notifications enabled",
        "automatic_comfort_temperature": "Automatic comfort temperature",
        "quiet_hours_enabled": "Quiet hours enabled",
        "notifications_currently_allowed": "Notifications currently allowed",
        "notification_cooldown_active": "Notification cooldown active",
        "recommendation_active": "Recommendation active",
        "comfort_temperature": "Comfort temperature",
        "comfort_humidity": "Comfort humidity",
        "recommendation_stability_window": "Recommendation stability window",
        "enabled": "Enabled",
        "temperature_override_enabled": "Temperature override enabled",
        "humidity_override_enabled": "Humidity override enabled",
        "temperature_override": "Temperature override",
        "humidity_override": "Humidity override",
    },
    "it": {
        "weather_condition": "Condizione meteo",
        "average_perceived_indoor_temperature": "Temperatura interna percepita media",
        "perceived_outdoor_temperature": "Temperatura esterna percepita",
        "effective_comfort_temperature": "Temperatura di comfort effettiva",
        "suggested_comfort_temperature": "Temperatura di comfort suggerita",
        "outdoor_temperature": "Temperatura esterna",
        "outdoor_humidity": "Umidità esterna",
        "wind_speed": "Velocità vento esterna",
        "recommendation": "Raccomandazione",
        "recommendation_score": "Punteggio raccomandazione",
        "recommendation_reason": "Motivo raccomandazione",
        "perceived_indoor_temperature": "Temperatura interna percepita",
        "temperature": "Temperatura interna",
        "indoor_humidity": "Umidità interna",
        "integration_enabled": "Integrazione abilitata",
        "notifications_enabled": "Notifiche abilitate",
        "automatic_comfort_temperature": "Temperatura di comfort automatica",
        "quiet_hours_enabled": "Fascia silenziosa abilitata",
        "notifications_currently_allowed": "Notifiche attualmente consentite",
        "notification_cooldown_active": "Pausa notifiche attiva",
        "recommendation_active": "Raccomandazione attiva",
        "comfort_temperature": "Temperatura di comfort",
        "comfort_humidity": "Umidità di comfort",
        "recommendation_stability_window": "Finestra di stabilità della raccomandazione",
        "enabled": "Abilitato",
        "temperature_override_enabled": "Override temperatura abilitato",
        "humidity_override_enabled": "Override umidità abilitato",
        "temperature_override": "Override temperatura",
        "humidity_override": "Override umidità",
    },
    "es": {
        "weather_condition": "Condición meteorológica",
        "average_perceived_indoor_temperature": "Temperatura interior percibida media",
        "perceived_outdoor_temperature": "Temperatura exterior percibida",
        "effective_comfort_temperature": "Temperatura de confort efectiva",
        "suggested_comfort_temperature": "Temperatura de confort sugerida",
        "outdoor_temperature": "Temperatura exterior",
        "outdoor_humidity": "Humedad exterior",
        "wind_speed": "Velocidad del viento exterior",
        "recommendation": "Recomendación",
        "recommendation_score": "Puntuación de recomendación",
        "recommendation_reason": "Motivo de la recomendación",
        "perceived_indoor_temperature": "Temperatura interior percibida",
        "temperature": "Temperatura interior",
        "indoor_humidity": "Humedad interior",
        "integration_enabled": "Integración habilitada",
        "notifications_enabled": "Notificaciones habilitadas",
        "automatic_comfort_temperature": "Temperatura de confort automática",
        "quiet_hours_enabled": "Horas de silencio habilitadas",
        "notifications_currently_allowed": "Notificaciones permitidas ahora",
        "notification_cooldown_active": "Enfriamiento de notificaciones activo",
        "recommendation_active": "Recomendación activa",
        "comfort_temperature": "Temperatura de confort",
        "comfort_humidity": "Humedad de confort",
        "recommendation_stability_window": "Ventana de estabilidad de la recomendación",
        "enabled": "Habilitado",
        "temperature_override_enabled": "Override de temperatura habilitado",
        "humidity_override_enabled": "Override de humedad habilitado",
        "temperature_override": "Override de temperatura",
        "humidity_override": "Override de humedad",
    },
    "ru": {
        "weather_condition": "Погодные условия",
        "average_perceived_indoor_temperature": "Средняя воспринимаемая внутренняя температура",
        "perceived_outdoor_temperature": "Воспринимаемая наружная температура",
        "effective_comfort_temperature": "Фактическая комфортная температура",
        "suggested_comfort_temperature": "Предлагаемая комфортная температура",
        "outdoor_temperature": "Наружная температура",
        "outdoor_humidity": "Наружная влажность",
        "wind_speed": "Скорость ветра снаружи",
        "recommendation": "Рекомендация",
        "recommendation_score": "Оценка рекомендации",
        "recommendation_reason": "Причина рекомендации",
        "perceived_indoor_temperature": "Воспринимаемая внутренняя температура",
        "temperature": "Внутренняя температура",
        "indoor_humidity": "Внутренняя влажность",
        "integration_enabled": "Интеграция включена",
        "notifications_enabled": "Уведомления включены",
        "automatic_comfort_temperature": "Автоматическая комфортная температура",
        "quiet_hours_enabled": "Режим тишины включён",
        "notifications_currently_allowed": "Уведомления сейчас разрешены",
        "notification_cooldown_active": "Активна пауза уведомлений",
        "recommendation_active": "Рекомендация активна",
        "comfort_temperature": "Комфортная температура",
        "comfort_humidity": "Комфортная влажность",
        "recommendation_stability_window": "Окно стабильности рекомендации",
        "enabled": "Включено",
        "temperature_override_enabled": "Override температуры включён",
        "humidity_override_enabled": "Override влажности включён",
        "temperature_override": "Override температуры",
        "humidity_override": "Override влажности",
    },
    "zh-hans": {
        "weather_condition": "天气状况",
        "average_perceived_indoor_temperature": "平均感知室内温度",
        "perceived_outdoor_temperature": "感知室外温度",
        "effective_comfort_temperature": "实际舒适温度",
        "suggested_comfort_temperature": "建议舒适温度",
        "outdoor_temperature": "室外温度",
        "outdoor_humidity": "室外湿度",
        "wind_speed": "室外风速",
        "recommendation": "建议",
        "recommendation_score": "建议分数",
        "recommendation_reason": "建议原因",
        "perceived_indoor_temperature": "感知室内温度",
        "temperature": "室内温度",
        "indoor_humidity": "室内湿度",
        "integration_enabled": "集成已启用",
        "notifications_enabled": "通知已启用",
        "automatic_comfort_temperature": "自动舒适温度",
        "quiet_hours_enabled": "静默时段已启用",
        "notifications_currently_allowed": "当前允许通知",
        "notification_cooldown_active": "通知冷却已启用",
        "recommendation_active": "建议已启用",
        "comfort_temperature": "舒适温度",
        "comfort_humidity": "舒适湿度",
        "recommendation_stability_window": "建议稳定窗口",
        "enabled": "已启用",
        "temperature_override_enabled": "温度覆盖已启用",
        "humidity_override_enabled": "湿度覆盖已启用",
        "temperature_override": "温度覆盖",
        "humidity_override": "湿度覆盖",
    },
}


class VentWiseEntity(CoordinatorEntity[VentWiseCoordinator]):
    """Base entity for VentWise."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
        entity_suffix: str,
        name_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_suffix}"
        self._attr_name = _localized_name(name_key, coordinator.hass.config.language)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.config_entry.title or NAME,
        )


class VentWiseRoomEntity(VentWiseEntity):
    """Base entity attached to a specific room device."""

    def __init__(
        self,
        coordinator: VentWiseCoordinator,
        room: RoomConfig,
        entity_suffix: str,
        name_key: str,
    ) -> None:
        room_key = room.room_id or room.name
        super().__init__(
            coordinator,
            f"{room_key}_{entity_suffix}",
            name_key,
        )
        self._room = room
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id, room_key)},
            manufacturer=MANUFACTURER,
            name=room.name,
        )

    @property
    def room(self) -> RoomConfig:
        """Return the associated room config."""

        return self._room


def _localized_name(name_key: str, language: str | None) -> str:
    """Return a translated entity label for the current backend language."""

    normalized_language = (language or "en").replace("_", "-").lower()
    base_language = normalized_language.split("-", 1)[0]
    labels = ENTITY_NAME_LABELS.get(normalized_language) or ENTITY_NAME_LABELS.get(
        base_language,
        ENTITY_NAME_LABELS["en"],
    )
    return labels.get(name_key, name_key.replace("_", " ").title())
