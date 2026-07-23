"""Notification delivery helpers for VentWise."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

from homeassistant.helpers import entity_registry as er

from .ventwise_core import RecommendationSummary

_LOGGER = logging.getLogger(__name__)
_PERSISTENT_NOTIFICATION_ID = "ventwise_last_notification_delivery"


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


def build_notification_payload(summary: RecommendationSummary) -> tuple[str, str]:
    """Build a readable notification title and body."""

    room_name = summary.best_room or "VentWise"
    action = summary.action.value
    title = "VentWise"
    if action == "open":
        body = f"{room_name}: open windows."
    elif action == "close":
        body = f"{room_name}: close windows."
    else:
        body = f"{room_name}: no action needed."
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
                title="VentWise notification delivery failed",
                message=(
                    f"{title}: {message}\n\n"
                    f"Failed targets: {', '.join(failed_targets)}"
                ),
            )
            return False

        await _async_create_persistent_notification(
            hass,
            title="VentWise notification delivered",
            message=(
                f"{title}: {message}\n\n"
                f"Delivered to: {', '.join(delivered_targets)}"
            ),
        )
        return True
    except Exception:
        _LOGGER.exception("VentWise notification delivery failed")
        await _async_create_persistent_notification(
            hass,
            title="VentWise notification delivery failed",
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
