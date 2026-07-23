"""Tests for notification delivery helpers."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.notification import (
    async_send_notification,
    build_notification_payload,
    notification_entity_ids_for_device_ids,
)


class _FakeEntry:
    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id


class _FakeServices:
    def __init__(self, *, failing_target: str | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, object], dict[str, object] | None]] = []
        self._failing_target = failing_target

    async def async_call(self, domain, service, service_data, *, target=None, blocking=False):
        self.calls.append((domain, service, service_data, target))
        if (
            domain == "notify"
            and target is not None
            and target.get("entity_id") == self._failing_target
        ):
            raise RuntimeError("delivery failed")


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


def test_build_notification_payload_uses_requested_language() -> None:
    summary = type(
        "Summary",
        (),
        {
            "best_room": "Salotto",
            "action": type("Action", (), {"value": "open"})(),
        },
    )()

    title, message = build_notification_payload(summary, language="it-IT")

    assert title == "VentWise"
    assert message == "Salotto: apri le finestre."


def test_async_send_notification_updates_home_assistant_persistent_notification() -> None:
    hass = type("Hass", (), {"services": _FakeServices(), "config": type("Config", (), {"language": "it"})()})()

    result = asyncio.run(
        async_send_notification(
            hass,
            ["notify.mobile_app_alice"],
            title="VentWise",
            message="Camera: open windows.",
            device_ids=["device-1"],
        )
    )

    assert result is True
    assert hass.services.calls[0][:2] == ("notify", "send_message")
    assert hass.services.calls[1][:2] == ("persistent_notification", "create")
    assert hass.services.calls[1][2]["notification_id"] == "ventwise_last_notification_delivery"
    assert hass.services.calls[1][2]["title"] == "Notifica VentWise consegnata"


def test_async_send_notification_reports_failure_to_home_assistant(caplog: pytest.LogCaptureFixture) -> None:
    hass = type("Hass", (), {"services": _FakeServices(failing_target="notify.mobile_app_alice"), "config": type("Config", (), {"language": "it"})()})()

    with caplog.at_level("ERROR"):
        result = asyncio.run(
            async_send_notification(
                hass,
                ["notify.mobile_app_alice"],
                title="VentWise",
                message="Camera: open windows.",
                device_ids=["device-1"],
            )
        )

    assert result is False
    assert hass.services.calls[-1][:2] == ("persistent_notification", "create")
    assert hass.services.calls[-1][2]["title"] == "Consegna notifica VentWise fallita"
    assert any(record.exc_info for record in caplog.records)


def test_async_send_notification_reports_missing_targets(caplog: pytest.LogCaptureFixture) -> None:
    hass = type("Hass", (), {"services": _FakeServices(), "config": type("Config", (), {"language": "it"})()})()

    with caplog.at_level("ERROR"):
        result = asyncio.run(
            async_send_notification(
                hass,
                [],
                title="VentWise",
                message="Camera: open windows.",
                device_ids=["device-1"],
            )
        )

    assert result is False
    assert hass.services.calls[-1][:2] == ("persistent_notification", "create")
    assert hass.services.calls[-1][2]["title"] == "Consegna notifica VentWise fallita"
    assert any(record.exc_info for record in caplog.records)
