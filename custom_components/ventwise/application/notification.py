"""Notification delivery helpers for VentWise."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Sequence

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..translation import runtime_catalog, translate
from ..ventwise_core import RecommendationSummary
from ..ventwise_core.models import RoomRecommendation

_LOGGER = logging.getLogger(__name__)
_PERSISTENT_RECOMMENDATION_ID = "ventwise_recommendation"
_PERSISTENT_ON_DEMAND_RECOMMENDATION_ID = "ventwise_on_demand_recommendation"
_PERSISTENT_DELIVERY_FAILURE_ID = "ventwise_notification_delivery_failure"
_PERSISTENT_DIAGNOSTIC_ID = "ventwise_diagnostic"
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


def is_companion_app_notification_entity(hass, entity_id: str) -> bool:
    """Return whether a notify entity is provided by the Companion App.

    Older Companion App entities commonly used the ``notify.mobile_app_*``
    prefix. Newer Home Assistant installations can expose the same service as
    ``notify.<device_name>``, so the entity-registry platform is authoritative.
    """

    if entity_id.startswith("notify.mobile_app_"):
        return True

    entry = er.async_get(hass).async_get(entity_id)
    return entry is not None and entry.platform == "mobile_app"


def mobile_app_notification_service(entity_id: str) -> str:
    """Return the Companion App notify service for an entity-registry target."""

    object_id = entity_id.removeprefix("notify.")
    if object_id.startswith("mobile_app_"):
        return object_id
    return f"mobile_app_{object_id}"


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

    title = translate(language, "on_demand_title")
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

    issue = issue if issue in {
        "unavailable_data",
        "no_enabled_rooms",
        "provider_unavailable",
        "unexpected_error",
    } else "unavailable_data"
    return (
        translate(language, "diagnostic", issue, "title"),
        translate(language, "diagnostic", issue, "message"),
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
        reason_code = getattr(recommendation, "reason_code", None)
        if reason_code in {"co2_high", "humidity_high"}:
            return f"{prefix}{texts[reason_code].format(**_reason_values(recommendation))}"
        return f"{prefix}{_ventilation_reason(language, minutes)}"
    if action == "open":
        if getattr(recommendation, "reason_code", None) == "forecast":
            return f"{prefix}{texts['forecast_reason']}"
        reason = _localized_temperature_reason(recommendation, texts, use_outside=True)
        return f"{prefix}{reason}" if reason else f"{prefix}{texts['none']}"
    if action == "close":
        urgent_reason = _urgent_close_reason(recommendation, texts)
        if urgent_reason is not None:
            return f"{prefix}{urgent_reason}"
        if getattr(recommendation, "reason_code", None) == "forecast":
            return f"{prefix}{texts['forecast_reason']}"
        reason = _localized_temperature_reason(recommendation, texts, use_outside=False)
        return f"{prefix}{reason}" if reason else f"{prefix}{texts['none']}"
    return f"{prefix}{texts['none']}"


def _urgent_close_reason(recommendation: RoomRecommendation, texts: dict[str, str]) -> str | None:
    """Return the concrete non-thermal reason for a safety close."""

    return {
        "current_precipitation": texts["close_current_precipitation"],
        "severe_weather": texts["close_severe_weather"],
        "unsafe_wind": texts["close_unsafe_wind"],
        "outdoor_exposure_avoid": texts["close_outdoor_exposure"],
    }.get(getattr(recommendation, "reason_code", None))


def build_recommendation_status(
    *,
    blocked_by: str | None,
    language: str | None = None,
) -> str:
    """Explain why no actionable recommendation is currently available."""

    if blocked_by in {"quiet_hours", "cooldown", "stability", "unavailable", "disabled"}:
        return translate(language, "status", blocked_by)
    return translate(language, "notification", "none")


async def async_send_notification(
    hass,
    entity_ids: Iterable[str],
    *,
    title: str,
    message: str,
    device_ids: Sequence[str] | None = None,
    send_to_home_assistant: bool = False,
    home_assistant_notification_id: str = _PERSISTENT_RECOMMENDATION_ID,
    mobile_action: dict[str, str] | None = None,
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
                service_data: dict[str, object] = {"title": title, "message": message}
                companion_target = is_companion_app_notification_entity(hass, entity_id)
                if mobile_action is not None and companion_target:
                    service_data["data"] = {"actions": [mobile_action]}
                service = (
                    mobile_app_notification_service(entity_id)
                    if mobile_action is not None and companion_target
                    else "send_message"
                )
                target = None if service != "send_message" else {"entity_id": entity_id}
                await hass.services.async_call(
                    "notify",
                    service,
                    service_data,
                    target=target,
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

    return runtime_catalog(language)["notification"]


def _notification_action_title(action: str, language: str | None) -> str:
    """Return the action text formatted as a notification title."""

    if action == "ventilate":
        return translate(language, "ventilate_title")
    texts = _notification_texts(language)
    text = texts.get(action, texts["none"]).rstrip(".。 ")
    return text[:1].upper() + text[1:]


def confirmation_action_title(action: str, language: str | None) -> str:
    """Return the localized label for a Companion App confirmation button."""

    return translate(language, "confirmation", "open" if action == "open" else "close")


def _safe_identifier(value: str, fallback: str) -> str:
    """Convert a user or entity identifier into a stable notification suffix."""

    return re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_") or fallback


def _ventilation_reason(language: str | None, minutes: int) -> str:
    """Return the localized bounded-duration ventilation guidance."""

    return translate(language, "ventilation_reason").format(minutes=minutes)


def _reason_values(recommendation: RoomRecommendation) -> dict[str, float]:
    """Return measured and configured advisory values for localized reasons."""

    return {
        "value": float(getattr(recommendation, "co2_ppm", None) or getattr(recommendation, "humidity_percent", 0.0)),
        "threshold": float(
            getattr(recommendation, "co2_threshold_ppm", None)
            if getattr(recommendation, "reason_code", None) == "co2_high"
            else getattr(recommendation, "humidity_threshold_percent", 100.0)
        ),
        "target": float(getattr(recommendation, "humidity_target_percent", 50.0) or 50.0),
    }


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
