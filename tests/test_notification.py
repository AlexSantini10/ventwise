"""Tests for notification delivery helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.notification import (
    async_send_notification,
    build_notification_payload,
    home_assistant_notification_id_for_room,
    build_recommendation_explanation,
    build_recommendation_status,
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
    summary = SimpleNamespace(
        best_room="Salotto",
        action=SimpleNamespace(value="open"),
        room_recommendations=(
                SimpleNamespace(
                    room_name="Salotto",
                    action=SimpleNamespace(value="open"),
                    indoor_perceived_c=27.2,
                target_perceived_c=22.0,
                outdoor_perceived_c=23.8,
            ),
        ),
    )

    title, message = build_notification_payload(summary, language="it-IT")

    assert title == "VentWise · Salotto"
    assert message == "apri le finestre. Fuori è più confortevole adesso: 3.4°C più vicino al comfort."


def test_recommendation_explanation_is_concise_and_localized() -> None:
    recommendation = SimpleNamespace(
        room_name="Camera",
        action=SimpleNamespace(value="close"),
        indoor_perceived_c=21.0,
        outdoor_perceived_c=25.0,
        target_perceived_c=22.0,
    )

    explanation = build_recommendation_explanation(recommendation, language="it-IT")

    assert explanation == "chiudi le finestre. Dentro è più confortevole adesso: 2.0°C più vicino al comfort."


def test_home_assistant_notification_id_is_distinct_per_delivery_and_room() -> None:
    camera = SimpleNamespace(room_name="Camera", room_id="camera-1")
    living_room = SimpleNamespace(room_name="Salotto", room_id="living-1")
    first_delivery = datetime(2026, 9, 4, 10, 15, 30, tzinfo=timezone.utc)
    second_delivery = datetime(2026, 9, 4, 11, 15, 30, tzinfo=timezone.utc)

    assert home_assistant_notification_id_for_room(
        camera, first_delivery
    ) == "ventwise_recommendation_camera-1_20260904t101530000000"
    assert home_assistant_notification_id_for_room(
        living_room, first_delivery
    ) == "ventwise_recommendation_living-1_20260904t101530000000"
    assert home_assistant_notification_id_for_room(
        camera, second_delivery
    ) == "ventwise_recommendation_camera-1_20260904t111530000000"


def test_recommendation_status_is_localized() -> None:
    assert build_recommendation_status(blocked_by="stability", language="it") == (
        "In attesa che la raccomandazione resti stabile."
    )


def test_async_send_notification_does_not_create_delivery_debug_on_success() -> None:
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
    assert hass.services.calls[0][2]["message"] == "Camera: open windows."
    assert len(hass.services.calls) == 1


def test_async_send_notification_delivers_to_home_assistant_when_selected() -> None:
    hass = type("Hass", (), {"services": _FakeServices(), "config": type("Config", (), {"language": "it"})()})()

    result = asyncio.run(
        async_send_notification(
            hass,
            [],
            title="VentWise",
            message="Camera: open windows.",
            send_to_home_assistant=True,
        )
    )

    assert result is True
    assert hass.services.calls == [
        (
            "persistent_notification",
            "create",
            {
                "title": "VentWise",
                "message": "Camera: open windows.",
                "notification_id": "ventwise_recommendation",
            },
            None,
        )
    ]


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
    assert hass.services.calls[-1][2]["notification_id"] == "ventwise_notification_delivery_failure"
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
