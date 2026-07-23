"""Tests for notification delivery helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.notification import notification_entity_ids_for_device_ids


class _FakeEntry:
    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id


def test_notification_entity_resolution_filters_to_notify_entities(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRegistry:
        pass

    def _fake_async_get(_hass):
        return _FakeRegistry()

    def _fake_entries_for_device(_registry, device_id):
        if device_id == "device-1":
            return [
                _FakeEntry("notify.mobile_app_alice"),
                _FakeEntry("sensor.alice_battery"),
                _FakeEntry("notify.mobile_app_alice"),
            ]
        if device_id == "device-2":
            return [
                _FakeEntry("switch.kitchen"),
                _FakeEntry("notify.mobile_app_bob"),
            ]
        return []

    from custom_components.ventwise import notification as notification_module

    monkeypatch.setattr(notification_module.er, "async_get", _fake_async_get)
    monkeypatch.setattr(notification_module.er, "async_entries_for_device", _fake_entries_for_device)

    result = notification_entity_ids_for_device_ids(object(), ["device-1", "device-2"])

    assert result == ("notify.mobile_app_alice", "notify.mobile_app_bob")
