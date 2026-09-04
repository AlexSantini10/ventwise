"""Data update coordinator for the integration runtime."""

from __future__ import annotations

import logging
from math import fsum
from dataclasses import replace
from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time, async_track_state_change_event
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .ventwise_core import (
    ComfortRecommender,
    RecommendationAction,
    RecommendationContext,
    RecommendationSummary,
    suggested_comfort_temperature,
)

from .runtime import (
    IntegrationConfig,
    NotificationMarker,
    RoomActionGuard,
    RuntimeSnapshot,
    RuntimeState,
    build_integration_config,
    build_room_profiles,
    build_scoring_config,
    dump_runtime_state,
    load_runtime_state,
    is_quiet_hours_active,
)
from .notification import (
    async_send_notification,
    build_room_notification_payload,
    home_assistant_notification_id_for_room,
    notification_entity_ids_for_device_ids,
)
from .const import (
    CONF_AUTO_COMFORT_TEMPERATURE,
    CONF_ROOM_ENABLED,
    CONF_ROOM_ID,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED,
    CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C,
    CONF_ROOMS,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_HOURS_END,
    CONF_QUIET_HOURS_START,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
    OUTDOOR_SOURCE_OVERRIDE,
)
from .const import CONF_NOTIFICATION_ENABLED

_LOGGER = logging.getLogger(__name__)

_NOTIFICATION_SEVERITY_ELEVATED_SCORE = 0.55
_NOTIFICATION_SEVERITY_URGENT_SCORE = 0.75


class VentWiseCoordinator(DataUpdateCoordinator[RuntimeSnapshot]):
    """Coordinate state across all VentWise entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        config_entry_data: dict[str, Any],
    ) -> None:
        self._config_entry = config_entry
        self._config = build_integration_config(config_entry_data)
        self._recommender = ComfortRecommender(build_scoring_config(self._config))
        self._runtime_state = self._load_runtime_state()
        self._last_action_signature = self._runtime_state.last_action_signature
        self._last_action_started_at = self._runtime_state.last_action_started_at or dt_util.utcnow()
        self._notification_markers = dict(self._runtime_state.notification_markers)
        self._room_action_guards = dict(self._runtime_state.room_action_guards)
        self._state_listener_unsubs: list[Callable[[], None]] = []
        self._time_listener_unsubs: list[Callable[[], None]] = []
        self._listeners_initialized = False
        config_entry.async_on_unload(self._async_remove_listeners)
        super().__init__(
            hass,
            config_entry=config_entry,
            logger=_LOGGER,
            name="VentWise",
            update_interval=None,
        )

    @property
    def config(self) -> IntegrationConfig:
        """Return the normalized integration config."""

        return self._config

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh initial data and start event listeners."""

        await super().async_config_entry_first_refresh()
        self._refresh_state_listeners()
        self._listeners_initialized = True
        self._refresh_time_listener(self.data.last_updated, self.data)

    async def _async_update_data(self) -> RuntimeSnapshot:
        """Refresh recommendation state from Home Assistant entity states."""

        self._config = build_integration_config(
            {**self._config_entry.data, **self._config_entry.options}
        )
        self._recommender = ComfortRecommender(build_scoring_config(self._config))

        if not self._config.enabled:
            snapshot = RuntimeSnapshot(
                summary=RecommendationSummary(
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="The integration is disabled.",
                    suggested_comfort_temperature_c=None,
                    blocked_by="disabled",
                ),
                weather_condition=None,
                target_perceived_c=None,
                suggested_comfort_temperature_c=None,
                outdoor_perceived_c=None,
                active_indoor_perceived_c=None,
                outdoor_temperature_c=None,
                outdoor_humidity_percent=None,
                wind_speed_m_s=None,
                wind_gust_m_s=None,
                notification_allowed=False,
                quiet_hours_active=False,
                cooldown_active=False,
                enabled=False,
                stable_for_seconds=0,
                last_updated=dt_util.utcnow(),
            )
            self._refresh_time_listener(snapshot.last_updated, snapshot)
            return snapshot

        rooms, outdoor = build_room_profiles(self._config, self.hass.states.get)
        notification_entity_ids = (
            notification_entity_ids_for_device_ids(
                self.hass,
                self._config.notification_device_ids,
            )
            if self._config.notification_device_ids
            else ()
        )
        if outdoor is None:
            snapshot = RuntimeSnapshot(
                summary=RecommendationSummary(
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="Outdoor or room sensor data is not available yet.",
                    suggested_comfort_temperature_c=None,
                    blocked_by="unavailable",
                ),
                weather_condition=_weather_condition(
                    self._config.outdoor_weather_entity_id,
                    self.hass.states.get,
                ),
                target_perceived_c=None,
                suggested_comfort_temperature_c=None,
                outdoor_perceived_c=None,
                active_indoor_perceived_c=None,
                outdoor_temperature_c=None,
                outdoor_humidity_percent=None,
                wind_speed_m_s=None,
                wind_gust_m_s=None,
                notification_allowed=False,
                quiet_hours_active=False,
                cooldown_active=False,
                enabled=True,
                stable_for_seconds=0,
                last_updated=dt_util.utcnow(),
            )
            self._refresh_time_listener(snapshot.last_updated, snapshot)
            return snapshot

        if not rooms:
            snapshot = RuntimeSnapshot(
                summary=RecommendationSummary(
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="No enabled rooms configured.",
                ),
                weather_condition=_weather_condition(
                    self._config.outdoor_weather_entity_id,
                    self.hass.states.get,
                ),
                target_perceived_c=self._config.target_temperature_c,
                suggested_comfort_temperature_c=None,
                outdoor_perceived_c=outdoor.temperature_c
                + (
                    (outdoor.humidity_percent - self._config.target_humidity_percent)
                    * self._recommender.config.humidity_weight
                ),
                active_indoor_perceived_c=None,
                outdoor_temperature_c=outdoor.temperature_c,
                outdoor_humidity_percent=outdoor.humidity_percent,
                wind_speed_m_s=outdoor.wind_speed_m_s,
                wind_gust_m_s=outdoor.wind_gust_m_s,
                notification_allowed=False,
                quiet_hours_active=False,
                cooldown_active=False,
                enabled=True,
                stable_for_seconds=0,
                last_updated=dt_util.utcnow(),
            )
            self._refresh_time_listener(snapshot.last_updated, snapshot)
            return snapshot

        now = dt_util.now()
        outdoor_perceived_c = outdoor.temperature_c + (
            (outdoor.humidity_percent - self._config.target_humidity_percent)
            * self._recommender.config.humidity_weight
        )
        suggested_target = suggested_comfort_temperature(
            self._config.target_temperature_c,
            outdoor_perceived_c,
        )
        effective_target_temperature_c = (
            suggested_target
            if self._config.auto_comfort_temperature_enabled
            else self._config.target_temperature_c
        )
        scoring_config = build_scoring_config(
            replace(
                self._config,
                target_temperature_c=effective_target_temperature_c,
            )
        )
        summary = ComfortRecommender(scoring_config).evaluate(
            rooms=rooms,
            outdoor=outdoor,
            context=RecommendationContext(
                quiet_hours_active=False,
                cooldown_active=False,
                stable_for_seconds=10**6,
            ),
        )
        summary = _with_suggested_comfort_temperature(summary, suggested_target)
        summary = self._apply_room_action_guardrails(summary, now)
        signature = self._signature(summary)
        if signature != self._last_action_signature:
            self._last_action_signature = signature
            self._last_action_started_at = now

        stable_for_seconds = int((now - self._last_action_started_at).total_seconds())
        quiet_hours_active = self._config.quiet_hours_enabled and is_quiet_hours_active(
            now,
            self._config.quiet_hours_start,
            self._config.quiet_hours_end,
        )
        best_recommendation = next(
            (
                recommendation
                for recommendation in summary.room_recommendations
                if recommendation.room_name == summary.best_room
            ),
            None,
        )
        notification_marker = self._notification_markers.get(summary.best_room or "")
        cooldown_active = (
            notification_marker is not None
            and best_recommendation is not None
            and (now - notification_marker.notified_at)
            < timedelta(minutes=self._config.cooldown_minutes)
            and not self._should_bypass_notification_cooldown(
                notification_marker,
                best_recommendation,
            )
        )

        notification_channel_available = (
            self._config.notification_enabled
            and (
                bool(notification_entity_ids)
                or self._config.home_assistant_notification_enabled
            )
            and not quiet_hours_active
            and stable_for_seconds >= self._config.stability_minutes * 60
        )
        notification_allowed = False
        for recommendation in summary.room_recommendations:
            room_signature = self._notification_identity(recommendation)
            room_marker = self._notification_markers.get(recommendation.room_name)
            matches_marker = room_marker is not None and self._matches_notification_marker(
                room_marker,
                recommendation,
            )
            bypasses_cooldown = room_marker is not None and self._should_bypass_notification_cooldown(
                room_marker,
                recommendation,
            )
            room_cooldown_active = (
                room_marker is not None
                and (now - room_marker.notified_at)
                < timedelta(minutes=self._config.cooldown_minutes)
                and not bypasses_cooldown
            )
            room_notification_allowed = (
                notification_channel_available
                and recommendation.action != RecommendationAction.NONE
                and recommendation.score >= self._config.minimum_score
                and not room_cooldown_active
            )
            if not room_notification_allowed:
                if room_cooldown_active:
                    _LOGGER.debug(
                        "VentWise notification suppressed: %s for room=%s "
                        "action=%s reason_code=%s severity=%s cooldown_remaining_seconds=%d",
                        "equivalent recommendation" if matches_marker else "non-urgent update",
                        recommendation.room_name,
                        recommendation.action.value,
                        recommendation.reason_code,
                        self._notification_severity(recommendation.score),
                        int(
                            (
                                timedelta(minutes=self._config.cooldown_minutes)
                                - (now - room_marker.notified_at)
                            ).total_seconds()
                        ),
                    )
                continue

            if room_marker is not None and bypasses_cooldown:
                bypass_reason = (
                    "action changed"
                    if room_marker.signature != room_signature
                    else "urgent escalation"
                )
                _LOGGER.debug(
                    "VentWise notification cooldown bypassed: %s for room=%s "
                    "previous_action=%s previous_reason_code=%s previous_severity=%s "
                    "action=%s reason_code=%s severity=%s",
                    bypass_reason,
                    recommendation.room_name,
                    room_marker.signature[0],
                    room_marker.reason,
                    room_marker.severity,
                    recommendation.action.value,
                    recommendation.reason_code,
                    self._notification_severity(recommendation.score),
                )

            title, message = build_room_notification_payload(
                recommendation,
                language=getattr(getattr(self.hass, "config", None), "language", None),
            )
            delivered = await async_send_notification(
                self.hass,
                notification_entity_ids,
                title=title,
                message=message,
                device_ids=self._config.notification_device_ids,
                send_to_home_assistant=self._config.home_assistant_notification_enabled,
                home_assistant_notification_id=home_assistant_notification_id_for_room(
                    recommendation,
                    now,
                ),
            )
            if delivered:
                self._notification_markers[recommendation.room_name] = NotificationMarker(
                    room_signature,
                    now,
                    recommendation.reason_code,
                    self._notification_severity(recommendation.score),
                )
                notification_allowed = True

        target_perceived_c = effective_target_temperature_c
        active_indoor_perceived_c = _average_room_indoor_perceived_temperature(summary)

        snapshot = RuntimeSnapshot(
            summary=summary,
            weather_condition=_weather_condition(
                self._config.outdoor_weather_entity_id,
                self.hass.states.get,
            ),
            target_perceived_c=target_perceived_c,
            suggested_comfort_temperature_c=suggested_target,
            outdoor_perceived_c=outdoor_perceived_c,
            active_indoor_perceived_c=active_indoor_perceived_c,
            outdoor_temperature_c=outdoor.temperature_c,
            outdoor_humidity_percent=outdoor.humidity_percent,
            wind_speed_m_s=outdoor.wind_speed_m_s,
            wind_gust_m_s=outdoor.wind_gust_m_s,
            notification_allowed=notification_allowed,
            quiet_hours_active=quiet_hours_active,
            cooldown_active=cooldown_active,
            enabled=True,
            stable_for_seconds=stable_for_seconds,
            last_updated=now,
        )
        self._persist_runtime_state()
        self._refresh_time_listener(now, snapshot)
        return snapshot

    async def async_set_enabled(self, enabled: bool) -> None:
        """Persist the master enable flag in config entry options."""

        self._update_entry_options({"enabled": enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_notification_enabled(self, enabled: bool) -> None:
        """Persist the notification enable flag in config entry options."""

        self._update_entry_options({CONF_NOTIFICATION_ENABLED: enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_quiet_hours_enabled(self, enabled: bool) -> None:
        """Persist the quiet-hours enable flag in config entry options."""

        self._update_entry_options({CONF_QUIET_HOURS_ENABLED: enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_stability_minutes(self, minutes: int) -> None:
        """Persist the global stability window in config entry options."""

        self._update_entry_options({CONF_STABILITY_MINUTES: minutes})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_target_temperature(self, temperature_c: float) -> None:
        """Persist the global comfort temperature in config entry options."""

        self._update_entry_options({CONF_TARGET_TEMPERATURE_C: temperature_c})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_auto_comfort_temperature_enabled(self, enabled: bool) -> None:
        """Persist the automatic comfort temperature flag in config entry options."""

        self._update_entry_options({CONF_AUTO_COMFORT_TEMPERATURE: enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_target_humidity(self, humidity_percent: float) -> None:
        """Persist the global comfort humidity in config entry options."""

        self._update_entry_options({CONF_TARGET_HUMIDITY_PERCENT: humidity_percent})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_quiet_hours_start(self, value: str) -> None:
        """Persist the global quiet-hours start time in config entry options."""

        self._update_entry_options({CONF_QUIET_HOURS_START: value})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_quiet_hours_end(self, value: str) -> None:
        """Persist the global quiet-hours end time in config entry options."""

        self._update_entry_options({CONF_QUIET_HOURS_END: value})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_room_enabled(self, room_key: str, enabled: bool) -> None:
        """Persist the enabled flag for one room."""

        self._update_room(room_key, {CONF_ROOM_ENABLED: enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_room_target_temperature_override_enabled(
        self,
        room_key: str,
        enabled: bool,
    ) -> None:
        """Persist the temperature override enable flag for one room."""

        self._update_room(room_key, {CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_ENABLED: enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_room_target_temperature_override(
        self,
        room_key: str,
        temperature_c: float,
    ) -> None:
        """Persist the room comfort temperature override."""

        self._update_room(room_key, {CONF_ROOM_TARGET_TEMPERATURE_OVERRIDE_C: temperature_c})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_room_target_humidity_override_enabled(
        self,
        room_key: str,
        enabled: bool,
    ) -> None:
        """Persist the humidity override enable flag for one room."""

        self._update_room(room_key, {CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE_ENABLED: enabled})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    async def async_set_room_target_humidity_override(
        self,
        room_key: str,
        humidity_percent: float,
    ) -> None:
        """Persist the room comfort humidity override."""

        self._update_room(room_key, {CONF_ROOM_TARGET_HUMIDITY_PERCENT_OVERRIDE: humidity_percent})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    def _signature(self, summary: RecommendationSummary) -> tuple[str, str]:
        return (summary.action.value, summary.best_room or "")

    @staticmethod
    def _notification_identity(recommendation) -> tuple[str, str]:
        """Return the stable action identity stored for one room."""

        return recommendation.action.value, recommendation.room_name

    @staticmethod
    def _notification_severity(score: float) -> str:
        """Bucket a score so material urgency changes bypass the cooldown."""

        if score >= _NOTIFICATION_SEVERITY_URGENT_SCORE:
            return "urgent"
        if score >= _NOTIFICATION_SEVERITY_ELEVATED_SCORE:
            return "elevated"
        return "normal"

    def _matches_notification_marker(self, marker: NotificationMarker, recommendation) -> bool:
        """Return whether a marker represents the same semantic recommendation."""

        return (
            marker.signature == self._notification_identity(recommendation)
            and marker.reason == recommendation.reason_code
            and marker.severity == self._notification_severity(recommendation.score)
        )

    def _should_bypass_notification_cooldown(
        self,
        marker: NotificationMarker,
        recommendation,
    ) -> bool:
        """Allow only stable action changes and urgent escalations through a cooldown."""

        if (
            marker.signature != self._notification_identity(recommendation)
            or marker.reason is None
            or marker.severity is None
        ):
            return True
        return (
            self._notification_severity(recommendation.score) == "urgent"
            and marker.severity != "urgent"
        )

    def _apply_room_action_guardrails(
        self,
        summary: RecommendationSummary,
        now: datetime,
    ) -> RecommendationSummary:
        """Hold per-room reversals so sensor noise cannot flip advice rapidly."""

        room_config_by_key = {
            (room.room_id or room.name): room for room in self._config.rooms
        }
        guarded_recommendations = []
        for recommendation in summary.room_recommendations:
            room_key = recommendation.room_id or recommendation.room_name
            room = room_config_by_key.get(room_key)
            if room is None:
                guarded_recommendations.append(recommendation)
                continue
            guarded_recommendations.append(
                self._guard_room_recommendation(recommendation, room, now)
            )

        actionable = [
            recommendation
            for recommendation in guarded_recommendations
            if recommendation.action != RecommendationAction.NONE
        ]
        if not actionable:
            return replace(
                summary,
                action=RecommendationAction.NONE,
                score=0.0,
                reason="No room currently has a stable action recommendation.",
                best_room=None,
                room_recommendations=tuple(guarded_recommendations),
            )
        best = max(actionable, key=lambda recommendation: recommendation.score)
        return replace(
            summary,
            action=best.action,
            score=best.score,
            reason=best.reason,
            best_room=best.room_name,
            room_recommendations=tuple(guarded_recommendations),
        )

    def _guard_room_recommendation(self, recommendation, room, now: datetime):
        """Apply one room's reversal hold and action lockout."""

        if recommendation.action == RecommendationAction.NONE:
            return recommendation

        room_key = recommendation.room_id or recommendation.room_name
        guard = self._room_action_guards.get(room_key)
        action = recommendation.action.value
        if guard is None:
            self._accept_room_action(room_key, action, room.action_lockout_minutes, now)
            return recommendation
        if action == guard.accepted_action:
            if guard.pending_action is not None:
                self._room_action_guards[room_key] = replace(
                    guard, pending_action=None, pending_since=None
                )
            return recommendation

        # A close recommendation with an urgent score is safety-critical and is
        # never delayed by a previous open suggestion.
        if (
            recommendation.action == RecommendationAction.CLOSE
            and self._notification_severity(recommendation.score) == "urgent"
        ):
            self._accept_room_action(room_key, action, room.action_lockout_minutes, now)
            return recommendation

        if guard.lockout_until is not None and now < guard.lockout_until:
            return self._guarded_recommendation(
                recommendation,
                "VentWise is keeping the previous room advice until its safety lock expires.",
            )

        if guard.pending_action != action or guard.pending_since is None:
            self._room_action_guards[room_key] = replace(
                guard, pending_action=action, pending_since=now
            )
            return self._guarded_recommendation(
                recommendation,
                "VentWise is waiting for this room's changed advice to settle.",
            )

        if (now - guard.pending_since) < timedelta(minutes=room.action_change_hold_minutes):
            return self._guarded_recommendation(
                recommendation,
                "VentWise is waiting for this room's changed advice to settle.",
            )

        self._accept_room_action(room_key, action, room.action_lockout_minutes, now)
        return recommendation

    def _accept_room_action(
        self,
        room_key: str,
        action: str,
        lockout_minutes: int,
        now: datetime,
    ) -> None:
        self._room_action_guards[room_key] = RoomActionGuard(
            accepted_action=action,
            lockout_until=now + timedelta(minutes=lockout_minutes)
            if lockout_minutes
            else None,
        )

    @staticmethod
    def _guarded_recommendation(recommendation, reason: str):
        """Hide an unstable reversal until the room-specific guard permits it."""

        return replace(
            recommendation,
            action=RecommendationAction.NONE,
            score=0.0,
            reason=reason,
            reason_code="guarded",
        )

    def _load_runtime_state(self) -> RuntimeState:
        return load_runtime_state({**self._config_entry.data, **self._config_entry.options})

    def _refresh_state_listeners(self) -> None:
        for unsub in self._state_listener_unsubs:
            unsub()
        self._state_listener_unsubs = []
        entity_ids = self._watched_entity_ids()
        if not entity_ids:
            return
        self._state_listener_unsubs.append(
            async_track_state_change_event(
                self.hass,
                entity_ids,
                self._async_source_state_changed,
            )
        )

    def _refresh_time_listener(self, now: datetime, snapshot: RuntimeSnapshot) -> None:
        for unsub in self._time_listener_unsubs:
            unsub()
        self._time_listener_unsubs = []

        if not self._listeners_initialized:
            return

        next_refresh = self._next_time_refresh(now, snapshot)
        if next_refresh is None:
            return

        self._time_listener_unsubs.append(
            async_track_point_in_time(
                self.hass,
                self._async_time_refresh,
                next_refresh,
            )
        )

    def _next_time_refresh(self, now: datetime, snapshot: RuntimeSnapshot) -> datetime | None:
        candidates: list[datetime] = []
        stability_seconds = self._config.stability_minutes * 60
        if snapshot.stable_for_seconds < stability_seconds:
            target = self._last_action_started_at + timedelta(seconds=stability_seconds)
            if target > now:
                candidates.append(target)
        if snapshot.cooldown_active:
            marker = self._notification_markers.get(snapshot.summary.best_room or "")
            if marker is not None:
                target = marker.notified_at + timedelta(minutes=self._config.cooldown_minutes)
                if target > now:
                    candidates.append(target)
        room_config_by_key = {
            configured_room.room_id or configured_room.name: configured_room
            for configured_room in self._config.rooms
        }
        for room_key, guard in self._room_action_guards.items():
            if guard.pending_since is not None:
                room = room_config_by_key.get(room_key)
                if room is not None:
                    target = guard.pending_since + timedelta(
                        minutes=room.action_change_hold_minutes
                    )
                    if target > now:
                        candidates.append(target)
            if guard.lockout_until is not None and guard.lockout_until > now:
                candidates.append(guard.lockout_until)
        if self._config.quiet_hours_enabled:
            quiet_hours_target = _next_quiet_hours_transition(
                now,
                self._config.quiet_hours_start,
                self._config.quiet_hours_end,
            )
            if quiet_hours_target is not None:
                candidates.append(quiet_hours_target)
        if not candidates:
            return None
        return min(candidates)

    @callback
    def _async_source_state_changed(self, event: Any) -> None:
        """Refresh when one of the watched source entities changes."""

        self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _async_time_refresh(self, now: datetime) -> None:
        """Refresh when a time-based gate may have changed."""

        self.hass.async_create_task(self.async_request_refresh())

    def _watched_entity_ids(self) -> list[str]:
        entity_ids: set[str] = set()
        if self._config.outdoor_weather_entity_id:
            entity_ids.add(self._config.outdoor_weather_entity_id)
        if (
            self._config.outdoor_temperature_source == OUTDOOR_SOURCE_OVERRIDE
            and self._config.outdoor_temperature_entity_id
        ):
            entity_ids.add(self._config.outdoor_temperature_entity_id)
        if (
            self._config.outdoor_humidity_source == OUTDOOR_SOURCE_OVERRIDE
            and self._config.outdoor_humidity_entity_id
        ):
            entity_ids.add(self._config.outdoor_humidity_entity_id)
        if (
            self._config.wind_speed_source == OUTDOOR_SOURCE_OVERRIDE
            and self._config.wind_speed_entity_id
        ):
            entity_ids.add(self._config.wind_speed_entity_id)
        for room in self._config.rooms:
            entity_ids.add(room.temperature_entity_id)
            if room.humidity_entity_id:
                entity_ids.add(room.humidity_entity_id)
        return sorted(entity_ids)

    def _async_remove_listeners(self) -> None:
        """Remove all event listeners registered by the coordinator."""

        for unsub in self._state_listener_unsubs:
            unsub()
        self._state_listener_unsubs = []
        for unsub in self._time_listener_unsubs:
            unsub()
        self._time_listener_unsubs = []

    def _persist_runtime_state(self) -> None:
        runtime_state = RuntimeState(
            last_action_signature=self._last_action_signature,
            last_action_started_at=self._last_action_started_at,
            notification_markers=dict(self._notification_markers),
            room_action_guards=dict(self._room_action_guards),
        )
        if runtime_state == self._runtime_state:
            return
        self._runtime_state = runtime_state
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            options={
                **self._config_entry.options,
                **dump_runtime_state(runtime_state),
            },
        )

    def _update_entry_options(self, updates: dict[str, Any]) -> None:
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            options={**self._config_entry.options, **updates},
        )

    def _update_room(self, room_key: str, updates: dict[str, Any]) -> None:
        options = dict(self._config_entry.options)
        rooms = [dict(room) for room in options.get(CONF_ROOMS, [])]
        for room in rooms:
            if self._room_matches(room, room_key):
                room.update(updates)
                break
        self._update_entry_options({CONF_ROOMS: rooms})

    @staticmethod
    def _room_matches(room: dict[str, Any], room_key: str) -> bool:
        room_id = room.get(CONF_ROOM_ID)
        if room_id is not None and str(room_id) == room_key:
            return True
        return str(room.get("name", "")).strip() == room_key


def _next_quiet_hours_transition(
    now: datetime,
    start_value: str,
    end_value: str,
) -> datetime | None:
    start_time = _parse_time(start_value)
    end_time = _parse_time(end_value)
    today = now.date()
    start_today = datetime.combine(today, start_time, tzinfo=now.tzinfo)
    end_today = datetime.combine(today, end_time, tzinfo=now.tzinfo)
    if is_quiet_hours_active(now, start_value, end_value):
        if start_time <= end_time:
            return end_today if end_today > now else end_today + timedelta(days=1)
        if now.time() < end_time:
            return end_today
        return end_today + timedelta(days=1)
    if start_time <= end_time:
        return start_today if start_today > now else start_today + timedelta(days=1)
    return start_today if start_today > now else start_today + timedelta(days=1)


def _parse_time(value: str) -> time:
    parts = str(value).strip().split(":")
    if len(parts) == 2:
        parts.append("00")
    return datetime.strptime(":".join(parts), "%H:%M:%S").time()


def _weather_condition(
    weather_entity_id: str | None,
    state_getter: Any,
) -> str | None:
    if not weather_entity_id:
        return None
    state = state_getter(weather_entity_id)
    if state is None:
        return None
    raw_state = getattr(state, "state", None)
    if raw_state is None:
        return None
    text = str(raw_state).strip()
    return text or None


def _with_suggested_comfort_temperature(
    summary: RecommendationSummary,
    suggested_temperature_c: float,
) -> RecommendationSummary:
    """Keep the exposed adaptive target consistent across summary and rooms."""

    room_recommendations = tuple(
        replace(
            recommendation,
            suggested_comfort_temperature_c=suggested_temperature_c,
        )
        for recommendation in summary.room_recommendations
    )
    return replace(
        summary,
        suggested_comfort_temperature_c=suggested_temperature_c,
        room_recommendations=room_recommendations,
    )


def _average_room_indoor_perceived_temperature(
    summary: RecommendationSummary,
) -> float | None:
    """Return the mean perceived indoor temperature across available rooms."""

    values = [recommendation.indoor_perceived_c for recommendation in summary.room_recommendations]
    if not values:
        return None
    return fsum(values) / len(values)
