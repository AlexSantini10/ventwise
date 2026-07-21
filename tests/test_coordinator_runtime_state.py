"""Tests for coordinator runtime state persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import (
    CONF_ENABLED,
    CONF_RUNTIME_STATE,
    CONF_RUNTIME_LAST_ACTION_SIGNATURE,
    CONF_RUNTIME_LAST_ACTION_STARTED_AT,
    CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE,
    CONF_RUNTIME_LAST_NOTIFICATION_AT,
)
from custom_components.ventwise.coordinator import VentWiseCoordinator


class _FakeConfigEntries:
    def __init__(self) -> None:
        self.updated: list[dict[str, object]] = []
        self.reloaded: list[str] = []

    def async_update_entry(self, entry, options):
        self.updated.append(options)
        entry.options = options

    async def async_reload(self, entry_id: str) -> None:
        self.reloaded.append(entry_id)


def _make_coordinator(options: dict[str, object] | None = None):
    hass = SimpleNamespace(
        config_entries=_FakeConfigEntries(),
        states=SimpleNamespace(get=lambda *_: None),
    )
    entry = SimpleNamespace(
        entry_id="abc123",
        data={},
        options=options or {},
        domain="ventwise",
        title="VentWise",
    )
    coordinator = VentWiseCoordinator(hass, entry, {**entry.data, **entry.options})
    return coordinator, hass, entry


def test_coordinator_loads_persisted_runtime_state() -> None:
    started_at = datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc)
    notification_at = datetime(2026, 7, 21, 13, 5, tzinfo=timezone.utc)
    coordinator, _, _ = _make_coordinator(
        {
            CONF_ENABLED: True,
            CONF_RUNTIME_STATE: {
                CONF_RUNTIME_LAST_ACTION_SIGNATURE: ["open", "Camera"],
                CONF_RUNTIME_LAST_ACTION_STARTED_AT: started_at.isoformat(),
                CONF_RUNTIME_LAST_NOTIFICATION_SIGNATURE: ["open", "Camera"],
                CONF_RUNTIME_LAST_NOTIFICATION_AT: notification_at.isoformat(),
            },
        }
    )

    assert coordinator._last_action_signature == ("open", "Camera")
    assert coordinator._last_action_started_at == started_at
    assert coordinator._last_notification_signature == ("open", "Camera")
    assert coordinator._last_notification_at == notification_at


def test_coordinator_persists_runtime_state_without_dropping_options() -> None:
    coordinator, hass, entry = _make_coordinator(
        {
            CONF_ENABLED: True,
            "custom_setting": "keep-me",
        }
    )
    timestamp = datetime(2026, 7, 21, 13, 15, tzinfo=timezone.utc)
    coordinator._last_action_signature = ("open", "Camera")
    coordinator._last_action_started_at = timestamp
    coordinator._last_notification_signature = ("open", "Camera")
    coordinator._last_notification_at = timestamp

    coordinator._persist_runtime_state()

    assert hass.config_entries.updated
    persisted = hass.config_entries.updated[-1]
    assert persisted[CONF_ENABLED] is True
    assert persisted["custom_setting"] == "keep-me"
    assert persisted[CONF_RUNTIME_STATE][CONF_RUNTIME_LAST_ACTION_SIGNATURE] == [
        "open",
        "Camera",
    ]
    assert persisted[CONF_RUNTIME_STATE][CONF_RUNTIME_LAST_ACTION_STARTED_AT] == timestamp.isoformat()
    assert entry.options == persisted
