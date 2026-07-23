"""Notification delivery helpers for VentWise."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

from homeassistant.helpers import entity_registry as er

from .ventwise_core import RecommendationSummary

_LOGGER = logging.getLogger(__name__)
_PERSISTENT_NOTIFICATION_ID = "ventwise_last_notification_delivery"
_LANGUAGE_PREFIXES: tuple[str, ...] = ("en", "it", "es", "ru", "zh-hans")
_NOTIFICATION_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "open": "open windows.",
        "close": "close windows.",
        "none": "no action needed.",
        "too_warm": "It is too warm inside: {delta:.1f}°C above comfort.",
        "too_cold": "It is too cold inside: {delta:.1f}°C below comfort.",
        "delivered_title": "VentWise notification delivered",
        "failed_title": "VentWise notification delivery failed",
        "delivered_to": "Delivered to",
        "failed_targets": "Failed targets",
    },
    "it": {
        "open": "apri le finestre.",
        "close": "chiudi le finestre.",
        "none": "nessuna azione necessaria.",
        "too_warm": "Dentro fa troppo caldo: {delta:.1f}°C sopra il comfort.",
        "too_cold": "Dentro fa troppo freddo: {delta:.1f}°C sotto il comfort.",
        "delivered_title": "Notifica VentWise consegnata",
        "failed_title": "Consegna notifica VentWise fallita",
        "delivered_to": "Consegnata a",
        "failed_targets": "Target falliti",
    },
    "es": {
        "open": "abre las ventanas.",
        "close": "cierra las ventanas.",
        "none": "no se necesita ninguna accion.",
        "too_warm": "Dentro hace demasiado calor: {delta:.1f}°C por encima del confort.",
        "too_cold": "Dentro hace demasiado frio: {delta:.1f}°C por debajo del confort.",
        "delivered_title": "Notificacion de VentWise entregada",
        "failed_title": "Fallo la entrega de la notificacion de VentWise",
        "delivered_to": "Entregada a",
        "failed_targets": "Destinos fallidos",
    },
    "ru": {
        "open": "откройте окна.",
        "close": "закройте окна.",
        "none": "действие не требуется.",
        "too_warm": "Внутри слишком жарко: на {delta:.1f}°C выше комфорта.",
        "too_cold": "Внутри слишком холодно: на {delta:.1f}°C ниже комфорта.",
        "delivered_title": "Уведомление VentWise доставлено",
        "failed_title": "Сбой доставки уведомления VentWise",
        "delivered_to": "Доставлено на",
        "failed_targets": "Не удалось доставить",
    },
    "zh-hans": {
        "open": "打开窗户。",
        "close": "关闭窗户。",
        "none": "无需操作。",
        "too_warm": "室内太热: 比舒适温度高 {delta:.1f}°C。",
        "too_cold": "室内太冷: 比舒适温度低 {delta:.1f}°C。",
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
        _LOGGER.debug("No notify entities resolved for device IDs: %s", list(device_ids))
    return tuple(entity_ids)


def build_notification_payload(
    summary: RecommendationSummary,
    *,
    language: str | None = None,
) -> tuple[str, str]:
    """Build a readable notification title and body."""

    room_name = summary.best_room or "VentWise"
    action = summary.action.value
    title = "VentWise"
    texts = _notification_texts(language)
    body = _build_notification_body(room_name, action, summary, texts)
    return title, body


async def async_send_notification(
    hass,
    entity_ids: Iterable[str],
    *,
    title: str,
    message: str,
    device_ids: Sequence[str] | None = None,
) -> bool:
    """Send a notification message to the selected notify entities."""

    targets = list(dict.fromkeys(entity_ids))
    texts = _notification_texts(getattr(getattr(hass, "config", None), "language", None))
    try:
        if not targets:
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
                _LOGGER.exception("Failed to deliver VentWise notification to %s", entity_id)

        if failed_targets:
            await _async_create_persistent_notification(
                hass,
                title=texts["failed_title"],
                message=(
                    f"{title}: {message}\n\n"
                    f"{texts['failed_targets']}: {', '.join(failed_targets)}"
                ),
            )
            return False

        await _async_create_persistent_notification(
            hass,
            title=texts["delivered_title"],
            message=(
                f"{title}: {message}\n\n"
                f"{texts['delivered_to']}: {', '.join(delivered_targets)}"
            ),
        )
        return True
    except Exception:
        _LOGGER.exception("VentWise notification delivery failed")
        await _async_create_persistent_notification(
            hass,
            title=texts["failed_title"],
            message=f"{title}: {message}",
        )
        return False


async def _async_create_persistent_notification(
    hass,
    *,
    title: str,
    message: str,
) -> None:
    """Create or update the latest VentWise persistent notification."""

    try:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": _PERSISTENT_NOTIFICATION_ID,
            },
            blocking=True,
        )
    except Exception:
        _LOGGER.exception("Failed to create VentWise persistent notification")


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


def _build_notification_body(
    room_name: str,
    action: str,
    summary: RecommendationSummary,
    texts: dict[str, str],
) -> str:
    """Build a localized, human-readable notification body."""

    if action == "open":
        reason = _localized_temperature_reason(summary, texts, warmer=True)
        if reason is not None:
            return f"{room_name}: {texts['open']} {reason}"
    elif action == "close":
        reason = _localized_temperature_reason(summary, texts, warmer=False)
        if reason is not None:
            return f"{room_name}: {texts['close']} {reason}"
    return f"{room_name}: {texts.get(action, texts['none'])}"


def _localized_temperature_reason(
    summary: RecommendationSummary,
    texts: dict[str, str],
    *,
    warmer: bool,
) -> str | None:
    """Return a brief localized explanation based on the best room metrics."""

    recommendation = _best_room_recommendation(summary)
    if recommendation is None:
        return None

    delta = recommendation.indoor_perceived_c - recommendation.target_perceived_c
    if abs(delta) < 0.05:
        return None

    if warmer and delta > 0:
        return texts["too_warm"].format(delta=delta)
    if not warmer and delta < 0:
        return texts["too_cold"].format(delta=abs(delta))
    return None


def _best_room_recommendation(summary: RecommendationSummary):
    """Return the recommendation matching the summary's best room, if any."""

    if not summary.best_room:
        return None

    for recommendation in summary.room_recommendations:
        if recommendation.room_name == summary.best_room:
            return recommendation
    return summary.room_recommendations[0] if summary.room_recommendations else None
