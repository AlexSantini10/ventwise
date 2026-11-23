"""Notification delivery helpers for VentWise."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

try:
    from ...ventwise_core import RecommendationSummary
    from ...ventwise_core.domain.decision_contracts import RoomRecommendation
except ImportError:  # Local source-tree development uses the standalone package.
    from ventwise_core import RecommendationSummary
    from ventwise_core.domain.decision_contracts import RoomRecommendation
from ...const import LAB_NOTIFICATION_ENTITY_ID

_LOGGER = logging.getLogger(__name__)
_PERSISTENT_RECOMMENDATION_ID = "ventwise_recommendation"
_PERSISTENT_ON_DEMAND_RECOMMENDATION_ID = "ventwise_on_demand_recommendation"
_PERSISTENT_DELIVERY_FAILURE_ID = "ventwise_notification_delivery_failure"
_PERSISTENT_DIAGNOSTIC_ID = "ventwise_diagnostic"
_LANGUAGE_PREFIXES: tuple[str, ...] = ("en", "it", "es", "fr", "de", "ru", "zh-hans")
_NOTIFICATION_CATALOG_DIR = Path(__file__).parents[2] / "translations" / "notifications"
_NOTIFICATION_CATALOG: dict[str, dict[str, str]] = {
    path.stem.lower(): json.loads(path.read_text(encoding="utf-8"))
    for path in _NOTIFICATION_CATALOG_DIR.glob("*.json")
}


def notification_entity_ids_for_device_ids(
    hass,
    device_ids: Sequence[str],
) -> tuple[str, ...]:
    """Resolve configured device IDs to notify entity IDs."""

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entity_ids: list[str] = []
    seen: set[str] = set()

    mobile_app_unique_ids: set[str] = set()
    for device_id in device_ids:
        # New configurations persist the notify entity ID itself.  Unlike a
        # device-registry ID, this does not change when the Companion App
        # recreates its device entry.
        if device_id.startswith("notify."):
            if device_id == LAB_NOTIFICATION_ENTITY_ID:
                if device_id not in seen:
                    seen.add(device_id)
                    entity_ids.append(device_id)
                continue
            entry = entity_registry.async_get(device_id)
            if entry is not None and entry.entity_id not in seen:
                seen.add(entry.entity_id)
                entity_ids.append(entry.entity_id)
            continue
        device = device_registry.async_get(device_id)
        if device is None:
            continue
        mobile_app_unique_ids.update(
            str(identifier)
            for domain, identifier in device.identifiers
            if domain == "mobile_app"
        )

    for device_id in device_ids:
        for entry in er.async_entries_for_device(entity_registry, device_id):
            entity_id = entry.entity_id
            if not entity_id or not entity_id.startswith("notify."):
                continue
            if entity_id in seen:
                continue
            seen.add(entity_id)
            entity_ids.append(entity_id)

    # Home Assistant can split or recreate device-registry entries while the
    # Companion App notify entity keeps its stable mobile_app identifier. Match
    # that identifier too, so both previously saved and current device IDs stay
    # valid across such migrations.
    if mobile_app_unique_ids:
        for entry in entity_registry.entities.values():
            entity_id = entry.entity_id
            if (
                not entity_id
                or not entity_id.startswith("notify.")
                or entry.platform != "mobile_app"
                or str(entry.unique_id) not in mobile_app_unique_ids
                or entity_id in seen
            ):
                continue
            seen.add(entity_id)
            entity_ids.append(entity_id)

    if not entity_ids:
        _LOGGER.warning(
            "No notification entities were resolved for %d configured device(s)",
            len(device_ids),
        )
    return tuple(entity_ids)


def build_notification_payload(
    summary: RecommendationSummary,
    *,
    language: str | None = None,
) -> tuple[str, str]:
    """Build a readable notification title and body."""

    recommendation = _best_room_recommendation(summary)
    if recommendation is not None:
        return build_room_notification_payload(recommendation, language=language)
    else:
        room_name = summary.best_room or "VentWise"
        title = _notification_action_title(summary.action.value, language)
        body = f"VentWise · {room_name}"
    return title, body


def build_on_demand_notification_payload(
    summary: RecommendationSummary,
    *,
    language: str | None = None,
) -> tuple[str, str]:
    """Build a clearly informational recommendation requested by a user."""

    title = _notification_texts(language)["on_demand_title"]
    if summary.action.value == "none":
        return title, build_recommendation_status(
            blocked_by=getattr(summary, "blocked_by", None),
            language=language,
        )
    _, message = build_notification_payload(summary, language=language)
    return title, message


def build_room_notification_payload(
    recommendation: RoomRecommendation,
    *,
    language: str | None = None,
) -> tuple[str, str]:
    """Build a notification payload for one specific room."""

    return (
        _notification_action_title(recommendation.action.value, language),
        build_recommendation_explanation(
            recommendation,
            language=language,
            include_room_name=True,
        ),
    )


def home_assistant_notification_id_for_room(
    recommendation: RoomRecommendation,
) -> str:
    """Return a stable persistent-notification ID for one room."""

    identifier = recommendation.room_id or recommendation.room_name
    return f"{_PERSISTENT_RECOMMENDATION_ID}_{_safe_identifier(identifier, 'room')}"


def home_assistant_on_demand_notification_id() -> str:
    """Return the stable ID for the latest on-demand recommendation."""

    return _PERSISTENT_ON_DEMAND_RECOMMENDATION_ID


def home_assistant_delivery_failure_id_for_target(target: str | None) -> str:
    """Return the persistent-notification ID for a delivery failure target."""

    if target is None:
        return f"{_PERSISTENT_DELIVERY_FAILURE_ID}_general"
    return f"{_PERSISTENT_DELIVERY_FAILURE_ID}_{_safe_identifier(target, 'target')}"


def home_assistant_diagnostic_notification_id(issue: str) -> str:
    """Return the stable persistent-notification ID for a diagnostic issue."""

    return f"{_PERSISTENT_DIAGNOSTIC_ID}_{_safe_identifier(issue, 'issue')}"


def build_diagnostic_notification_payload(
    issue: str,
    *,
    language: str | None = None,
) -> tuple[str, str]:
    """Build localised persistent-notification content for a diagnostic issue."""

    texts = _notification_texts(language)
    key = issue if issue in {"unavailable_data", "no_enabled_rooms"} else "unavailable_data"
    return texts[f"diagnostic_{key}_title"], texts[f"diagnostic_{key}_message"]

    diagnostics = {
        "unavailable_data": {
            "en": ("VentWise data unavailable", "Required weather or room sensor data is unavailable."),
            "fr": ("Données VentWise indisponibles", "Les données météo ou des capteurs de la pièce sont indisponibles."),
            "de": ("VentWise-Daten nicht verfügbar", "Erforderliche Wetter- oder Raumsensordaten sind nicht verfügbar."),
            "it": ("Dati VentWise non disponibili", "I dati meteo o dei sensori della stanza richiesti non sono disponibili."),
            "es": ("Datos de VentWise no disponibles", "Los datos meteorol\u00f3gicos o de sensores de habitaci\u00f3n necesarios no est\u00e1n disponibles."),
            "ru": ("\u0414\u0430\u043d\u043d\u044b\u0435 VentWise \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b", "\u041d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b \u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u043f\u043e\u0433\u043e\u0434\u044b \u0438\u043b\u0438 \u0434\u0430\u0442\u0447\u0438\u043a\u043e\u0432 \u043a\u043e\u043c\u043d\u0430\u0442\u044b."),
            "zh-hans": ("VentWise \u6570\u636e\u4e0d\u53ef\u7528", "\u65e0\u6cd5\u83b7\u53d6\u5fc5\u9700\u7684\u5929\u6c14\u6216\u623f\u95f4\u4f20\u611f\u5668\u6570\u636e\u3002"),
        },
        "no_enabled_rooms": {
            "en": ("VentWise needs an enabled room", "No enabled rooms are configured."),
            "fr": ("VentWise nécessite une pièce activée", "Aucune pièce activée n'est configurée."),
            "de": ("VentWise benötigt einen aktivierten Raum", "Es sind keine aktivierten Räume konfiguriert."),
            "it": ("VentWise richiede una stanza attiva", "Non sono configurate stanze attive."),
            "es": ("VentWise necesita una habitaci\u00f3n activa", "No hay habitaciones activas configuradas."),
            "ru": ("VentWise \u043d\u0443\u0436\u043d\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0430\u044f \u043a\u043e\u043c\u043d\u0430\u0442\u0430", "\u041d\u0435\u0442 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d\u043d\u044b\u0445 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u043a\u043e\u043c\u043d\u0430\u0442."),
            "zh-hans": ("VentWise \u9700\u8981\u542f\u7528\u7684\u623f\u95f4", "\u672a\u914d\u7f6e\u542f\u7528\u7684\u623f\u95f4\u3002"),
        },
    }
    return diagnostics.get(issue, diagnostics["unavailable_data"]).get(
        _normalize_language_key(language), diagnostics["unavailable_data"]["en"]
    )


def build_recommendation_explanation(
    recommendation: RoomRecommendation,
    *,
    language: str | None = None,
    include_room_name: bool = False,
) -> str:
    """Build a concise user-facing explanation for one room recommendation."""

    texts = _notification_texts(language)
    action = recommendation.action.value
    prefix = f"VentWise · {recommendation.room_name}: " if include_room_name else ""
    if action == "ventilate":
        minutes = getattr(recommendation, "ventilation_duration_minutes", None) or 10
        return f"{prefix}{_ventilation_reason(language, minutes)}"
    if action == "open":
        if getattr(recommendation, "reason_code", None) == "forecast":
            return f"{prefix}{texts['forecast_reason']}"
        reason = _localized_temperature_reason(recommendation, texts, use_outside=True)
        return f"{prefix}{reason}" if reason else f"{prefix}{texts['none']}"
    if action == "close":
        if getattr(recommendation, "reason_code", None) == "forecast":
            return f"{prefix}{texts['forecast_reason']}"
        reason = _localized_temperature_reason(recommendation, texts, use_outside=False)
        return f"{prefix}{reason}" if reason else f"{prefix}{texts['none']}"
    return f"{prefix}{texts['none']}"


def build_recommendation_status(
    *,
    blocked_by: str | None,
    language: str | None = None,
) -> str:
    """Explain why no actionable recommendation is currently available."""

    texts = _notification_texts(language)
    if blocked_by in {"quiet_hours", "cooldown", "stability", "unavailable", "disabled"}:
        return texts[f"status_{blocked_by}"]
    return texts["none"]

    status_texts = {
        "quiet_hours": {
            "en": "Recommendations are paused during quiet hours.",
            "fr": "Les recommandations sont suspendues pendant les heures calmes.",
            "de": "Empfehlungen sind während der Ruhezeiten pausiert.",
            "it": "Le raccomandazioni sono sospese durante la fascia silenziosa.",
            "es": "Las recomendaciones están pausadas durante las horas de silencio.",
            "ru": "Рекомендации приостановлены в режиме тишины.",
            "zh-hans": "建议会在静默时段暂停。",
        },
        "cooldown": {
            "en": "The same recommendation was sent recently.",
            "fr": "La même recommandation a été envoyée récemment.",
            "de": "Dieselbe Empfehlung wurde kürzlich gesendet.",
            "it": "La stessa raccomandazione è stata inviata di recente.",
            "es": "La misma recomendación se envió recientemente.",
            "ru": "Та же рекомендация была отправлена недавно.",
            "zh-hans": "相同的建议最近已发送。",
        },
        "stability": {
            "en": "Waiting for the recommendation to remain stable.",
            "fr": "La recommandation doit encore rester stable.",
            "de": "Die Empfehlung muss noch stabil bleiben.",
            "it": "In attesa che la raccomandazione resti stabile.",
            "es": "Esperando a que la recomendación se mantenga estable.",
            "ru": "Ожидание стабилизации рекомендации.",
            "zh-hans": "正在等待建议保持稳定。",
        },
        "unavailable": {
            "en": "Waiting for the required sensor data.",
            "fr": "En attente des données nécessaires des capteurs.",
            "de": "Warten auf die erforderlichen Sensordaten.",
            "it": "In attesa dei dati richiesti dai sensori.",
            "es": "Esperando los datos necesarios de los sensores.",
            "ru": "Ожидание необходимых данных датчиков.",
            "zh-hans": "正在等待所需的传感器数据。",
        },
        "disabled": {
            "en": "VentWise is disabled.",
            "fr": "VentWise est désactivé.",
            "de": "VentWise ist deaktiviert.",
            "it": "VentWise è disabilitato.",
            "es": "VentWise está deshabilitado.",
            "ru": "VentWise отключён.",
            "zh-hans": "VentWise 已禁用。",
        },
    }
    language_key = _normalize_language_key(language)
    if blocked_by in status_texts:
        return status_texts[blocked_by].get(language_key, status_texts[blocked_by]["en"])
    return texts["none"]


async def async_send_notification(
    hass,
    entity_ids: Iterable[str],
    *,
    title: str,
    message: str,
    device_ids: Sequence[str] | None = None,
    send_to_home_assistant: bool = False,
    home_assistant_notification_id: str = _PERSISTENT_RECOMMENDATION_ID,
) -> bool:
    """Deliver a recommendation to selected devices and/or Home Assistant."""

    targets = list(dict.fromkeys(entity_ids))
    texts = _notification_texts(getattr(getattr(hass, "config", None), "language", None))
    try:
        if not targets and not send_to_home_assistant:
            raise RuntimeError("No notification entities resolved for configured devices")

        delivered_targets: list[str] = []
        failed_targets: list[str] = []
        for entity_id in targets:
            try:
                if entity_id == LAB_NOTIFICATION_ENTITY_ID:
                    await _async_create_persistent_notification(
                        hass,
                        title=title,
                        message=message,
                        notification_id=home_assistant_notification_id,
                    )
                    delivered_targets.append(entity_id)
                    continue
                service_data: dict[str, object] = {"title": title, "message": message}
                await hass.services.async_call(
                    "notify",
                    "send_message",
                    service_data,
                    target={"entity_id": entity_id},
                    blocking=True,
                )
                delivered_targets.append(entity_id)
            except Exception:
                failed_targets.append(entity_id)
                _LOGGER.exception("Failed to deliver a VentWise notification")

        home_assistant_delivered = False
        if send_to_home_assistant:
            home_assistant_delivered = await _async_create_persistent_notification(
                hass,
                title=title,
                message=message,
                notification_id=home_assistant_notification_id,
            )

        if failed_targets:
            for failed_target in failed_targets:
                await _async_create_persistent_notification(
                    hass,
                    title=texts["failed_title"],
                    message=(
                        f"{title}: {message}\n\n"
                        f"{texts['failed_targets']}: {failed_target}"
                    ),
                    notification_id=home_assistant_delivery_failure_id_for_target(
                        failed_target
                    ),
                )
        return bool(delivered_targets) or home_assistant_delivered
    except Exception:
        _LOGGER.exception("VentWise notification delivery failed")
        await _async_create_persistent_notification(
            hass,
            title=texts["failed_title"],
            message=f"{title}: {message}",
            notification_id=home_assistant_delivery_failure_id_for_target(None),
        )
        return False


async def _async_create_persistent_notification(
    hass,
    *,
    title: str,
    message: str,
    notification_id: str,
) -> bool:
    """Create or update the latest VentWise persistent notification."""

    try:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": notification_id,
            },
            blocking=True,
        )
        return True
    except Exception:
        _LOGGER.exception("Failed to create VentWise persistent notification")
        return False


async def async_create_persistent_notification(
    hass,
    *,
    title: str,
    message: str,
    notification_id: str,
) -> bool:
    """Create or update a persistent notification without propagating service failures."""

    return await _async_create_persistent_notification(
        hass,
        title=title,
        message=message,
        notification_id=notification_id,
    )


async def async_dismiss_persistent_notification(hass, notification_id: str) -> bool:
    """Dismiss a persistent notification, returning whether Home Assistant accepted it."""

    try:
        await hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": notification_id},
            blocking=True,
        )
        return True
    except Exception:
        _LOGGER.exception("Failed to dismiss VentWise persistent notification")
        return False


def _notification_texts(language: str | None) -> dict[str, str]:
    """Return localized notification text snippets."""

    language_key = _normalize_language_key(language)
    return _NOTIFICATION_CATALOG.get(language_key, _NOTIFICATION_CATALOG["en"])


def _notification_action_title(action: str, language: str | None) -> str:
    """Return the action text formatted as a notification title."""

    if action == "ventilate":
        return _notification_texts(language)["action_ventilate"]
        return {
            "en": "Ventilate briefly",
            "it": "Arieggia brevemente",
            "es": "Ventila brevemente",
            "fr": "Aérer brièvement",
            "de": "Kurz lüften",
            "ru": "Кратко проветрите",
            "zh-hans": "短时通风",
        }.get(_normalize_language_key(language), "Ventilate briefly")
    texts = _notification_texts(language)
    return texts.get(action, texts["none"]).rstrip(".。 ").capitalize()


def _normalize_language_key(language: str | None) -> str:
    """Normalize a Home Assistant language code to a supported prefix."""

    normalized = (language or "en").strip().lower().replace("_", "-")
    for prefix in _LANGUAGE_PREFIXES:
        if normalized.startswith(prefix):
            return prefix
    return "en"


def _safe_identifier(value: str, fallback: str) -> str:
    """Convert a user or entity identifier into a stable notification suffix."""

    return re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_") or fallback


def _ventilation_reason(language: str | None, minutes: int) -> str:
    """Return the localized bounded-duration ventilation guidance."""

    return _notification_texts(language)["ventilation_reason"].format(minutes=minutes)


def _localized_temperature_reason(
    recommendation: RoomRecommendation,
    texts: dict[str, str],
    *,
    use_outside: bool,
) -> str | None:
    """Return a brief localized explanation based on the best room metrics."""

    indoor_delta = abs(recommendation.indoor_perceived_c - recommendation.target_perceived_c)
    outdoor_delta = abs(recommendation.outdoor_perceived_c - recommendation.target_perceived_c)
    if abs(indoor_delta - outdoor_delta) < 0.05:
        return None

    if use_outside and outdoor_delta < indoor_delta:
        return texts["open_reason"].format(delta=indoor_delta - outdoor_delta)
    if not use_outside and indoor_delta < outdoor_delta:
        return texts["close_reason"].format(delta=outdoor_delta - indoor_delta)
    return None


def _best_room_recommendation(summary: RecommendationSummary):
    """Return the recommendation matching the summary's best room, if any."""

    if not summary.best_room:
        return None

    for recommendation in summary.room_recommendations:
        if recommendation.room_name == summary.best_room:
            return recommendation
    return summary.room_recommendations[0] if summary.room_recommendations else None
