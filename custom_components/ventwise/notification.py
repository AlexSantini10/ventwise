"""Notification delivery helpers for VentWise."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence
from datetime import datetime

from homeassistant.helpers import entity_registry as er

from .ventwise_core import RecommendationSummary
from .ventwise_core.models import RoomRecommendation

_LOGGER = logging.getLogger(__name__)
_PERSISTENT_RECOMMENDATION_ID = "ventwise_recommendation"
_PERSISTENT_DELIVERY_FAILURE_ID = "ventwise_notification_delivery_failure"
_LANGUAGE_PREFIXES: tuple[str, ...] = ("en", "it", "es", "ru", "zh-hans")
_NOTIFICATION_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "open": "open windows.",
        "close": "close windows.",
        "none": "no action needed.",
        "open_reason": "Outside is more comfortable right now: {delta:.1f}°C closer to comfort.",
        "close_reason": "Inside is more comfortable right now: {delta:.1f}°C closer to comfort.",
        "forecast_reason": "Short-term forecast: outside conditions are expected to become less comfortable soon.",
        "failed_title": "VentWise notification delivery failed",
        "failed_targets": "Failed targets",
    },
    "it": {
        "open": "apri le finestre.",
        "close": "chiudi le finestre.",
        "none": "nessuna azione necessaria.",
        "open_reason": "Fuori è più confortevole adesso: {delta:.1f}°C più vicino al comfort.",
        "close_reason": "Dentro è più confortevole adesso: {delta:.1f}°C più vicino al comfort.",
        "forecast_reason": "Previsione a breve termine: fuori sarà presto meno confortevole.",
        "failed_title": "Consegna notifica VentWise fallita",
        "failed_targets": "Target falliti",
    },
    "es": {
        "open": "abre las ventanas.",
        "close": "cierra las ventanas.",
        "none": "no se necesita ninguna accion.",
        "open_reason": "Afuera es más confortable ahora: {delta:.1f}°C más cerca del confort.",
        "close_reason": "Adentro es más confortable ahora: {delta:.1f}°C más cerca del confort.",
        "delivered_title": "Notificacion de VentWise entregada",
        "failed_title": "Fallo la entrega de la notificacion de VentWise",
        "delivered_to": "Entregada a",
        "failed_targets": "Destinos fallidos",
    },
    "ru": {
        "open": "откройте окна.",
        "close": "закройте окна.",
        "none": "действие не требуется.",
        "open_reason": "Снаружи сейчас комфортнее: на {delta:.1f}°C ближе к комфорту.",
        "close_reason": "Внутри сейчас комфортнее: на {delta:.1f}°C ближе к комфорту.",
        "delivered_title": "Уведомление VentWise доставлено",
        "failed_title": "Сбой доставки уведомления VentWise",
        "delivered_to": "Доставлено на",
        "failed_targets": "Не удалось доставить",
    },
    "zh-hans": {
        "open": "打开窗户。",
        "close": "关闭窗户。",
        "none": "无需操作。",
        "open_reason": "现在室外更舒适：更接近舒适温度 {delta:.1f}°C。",
        "close_reason": "现在室内更舒适：更接近舒适温度 {delta:.1f}°C。",
        "delivered_title": "VentWise 通知已送达",
        "failed_title": "VentWise 通知发送失败",
        "delivered_to": "已发送到",
        "failed_targets": "失败目标",
    },
}


def notification_entity_ids_for_device_ids(
    hass,
    device_ids: Sequence[str],
) -> tuple[str, ...]:
    """Resolve configured device IDs to notify entity IDs."""

    entity_registry = er.async_get(hass)
    entity_ids: list[str] = []
    seen: set[str] = set()

    for device_id in device_ids:
        for entry in er.async_entries_for_device(entity_registry, device_id):
            entity_id = entry.entity_id
            if not entity_id or not entity_id.startswith("notify."):
                continue
            if entity_id in seen:
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
        title = "VentWise" if room_name == "VentWise" else f"VentWise · {room_name}"
        body = f"{room_name}: {_notification_texts(language).get(summary.action.value, _notification_texts(language)['none'])}"
    return title, body


def build_room_notification_payload(
    recommendation: RoomRecommendation,
    *,
    language: str | None = None,
) -> tuple[str, str]:
    """Build a notification payload for one specific room."""

    return (
        f"VentWise · {recommendation.room_name}",
        build_recommendation_explanation(
            recommendation,
            language=language,
            include_room_name=False,
        ),
    )


def home_assistant_notification_id_for_room(
    recommendation: RoomRecommendation,
    delivered_at: datetime,
) -> str:
    """Return a distinct persistent-notification ID for one delivery."""

    identifier = recommendation.room_id or recommendation.room_name
    safe_identifier = re.sub(r"[^a-z0-9_-]+", "_", identifier.lower()).strip("_")
    delivered_stamp = delivered_at.strftime("%Y%m%dT%H%M%S%f").lower()
    return f"{_PERSISTENT_RECOMMENDATION_ID}_{safe_identifier or 'room'}_{delivered_stamp}"


def build_recommendation_explanation(
    recommendation: RoomRecommendation,
    *,
    language: str | None = None,
    include_room_name: bool = False,
) -> str:
    """Build a concise user-facing explanation for one room recommendation."""

    texts = _notification_texts(language)
    action = recommendation.action.value
    prefix = f"{recommendation.room_name}: " if include_room_name else ""
    if action == "open":
        if getattr(recommendation, "reason_code", None) == "forecast":
            return f"{prefix}{texts['open']} {texts.get('forecast_reason', _NOTIFICATION_TEXTS['en']['forecast_reason'])}"
        reason = _localized_temperature_reason(recommendation, texts, use_outside=True)
        return f"{prefix}{texts['open']} {reason}" if reason else f"{prefix}{texts['open']}"
    if action == "close":
        if getattr(recommendation, "reason_code", None) == "forecast":
            return f"{prefix}{texts['close']} {texts.get('forecast_reason', _NOTIFICATION_TEXTS['en']['forecast_reason'])}"
        reason = _localized_temperature_reason(recommendation, texts, use_outside=False)
        return f"{prefix}{texts['close']} {reason}" if reason else f"{prefix}{texts['close']}"
    return f"{prefix}{texts['none']}"


def build_recommendation_status(
    *,
    blocked_by: str | None,
    language: str | None = None,
) -> str:
    """Explain why no actionable recommendation is currently available."""

    texts = _notification_texts(language)
    status_texts = {
        "quiet_hours": {
            "en": "Recommendations are paused during quiet hours.",
            "it": "Le raccomandazioni sono sospese durante la fascia silenziosa.",
        },
        "cooldown": {
            "en": "The same recommendation was sent recently.",
            "it": "La stessa raccomandazione è stata inviata di recente.",
        },
        "stability": {
            "en": "Waiting for the recommendation to remain stable.",
            "it": "In attesa che la raccomandazione resti stabile.",
        },
        "unavailable": {
            "en": "Waiting for the required sensor data.",
            "it": "In attesa dei dati richiesti dai sensori.",
        },
        "disabled": {
            "en": "VentWise is disabled.",
            "it": "VentWise è disabilitato.",
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
            raise RuntimeError(f"No notify entities resolved for device IDs: {list(device_ids or [])}")

        delivered_targets: list[str] = []
        failed_targets: list[str] = []
        for entity_id in targets:
            try:
                await hass.services.async_call(
                    "notify",
                    "send_message",
                    {"title": title, "message": message},
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
            await _async_create_persistent_notification(
                hass,
                title=texts["failed_title"],
                message=(
                    f"{title}: {message}\n\n"
                    f"{texts['failed_targets']}: {', '.join(failed_targets)}"
                ),
                notification_id=_PERSISTENT_DELIVERY_FAILURE_ID,
            )
        return bool(delivered_targets) or home_assistant_delivered
    except Exception:
        _LOGGER.exception("VentWise notification delivery failed")
        await _async_create_persistent_notification(
            hass,
            title=texts["failed_title"],
            message=f"{title}: {message}",
            notification_id=_PERSISTENT_DELIVERY_FAILURE_ID,
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


def _notification_texts(language: str | None) -> dict[str, str]:
    """Return localized notification text snippets."""

    language_key = _normalize_language_key(language)
    return _NOTIFICATION_TEXTS.get(language_key, _NOTIFICATION_TEXTS["en"])


def _normalize_language_key(language: str | None) -> str:
    """Normalize a Home Assistant language code to a supported prefix."""

    normalized = (language or "en").strip().lower().replace("_", "-")
    for prefix in _LANGUAGE_PREFIXES:
        if normalized.startswith(prefix):
            return prefix
    return "en"


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
