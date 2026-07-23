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
    RecommendationAction,
    RecommendationContext,
    RecommendationSummary,
)
from .ventwise_core import ComfortRecommender

from .runtime import (
    IntegrationConfig,
    RuntimeSnapshot,
    RuntimeState,
    build_integration_config,
    build_room_profiles,
    build_scoring_config,
    dump_runtime_state,
    load_runtime_state,
    is_quiet_hours_active,
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
        self._last_notification_at = self._runtime_state.last_notification_at or (
            dt_util.utcnow() - timedelta(days=1)
        )
        self._last_notification_signature = self._runtime_state.last_notification_signature
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
                outdoor_perceived_c=outdoor.temperature_c
                + (
                    (outdoor.humidity_percent - self._config.target_humidity_percent)
                    * self._recommender.config.humidity_weight
                ),
                active_indoor_perceived_c=None,
                outdoor_temperature_c=outdoor.temperature_c,
                outdoor_humidity_percent=outdoor.humidity_percent,
                wind_speed_m_s=outdoor.wind_speed_m_s,
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
        summary = self._recommender.evaluate(
            rooms=rooms,
            outdoor=outdoor,
            context=RecommendationContext(
                quiet_hours_active=False,
                cooldown_active=False,
                stable_for_seconds=10**6,
            ),
        )
        effective_target_temperature_c = self._config.target_temperature_c
        if self._config.auto_comfort_temperature_enabled:
            suggested_target = _suggested_comfort_temperature(
                self._config.target_temperature_c,
                summary,
            )
            if suggested_target is not None:
                effective_target_temperature_c = suggested_target
                auto_config = replace(
                    self._config,
                    target_temperature_c=effective_target_temperature_c,
                )
                summary = ComfortRecommender(build_scoring_config(auto_config)).evaluate(
                    rooms=rooms,
                    outdoor=outdoor,
                    context=RecommendationContext(
                        quiet_hours_active=False,
                        cooldown_active=False,
                        stable_for_seconds=10**6,
                    ),
                )
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
        cooldown_active = self._last_notification_signature == signature and (
            now - self._last_notification_at
        ) < timedelta(minutes=self._config.cooldown_minutes)

        notification_allowed = (
            self._config.notification_enabled
            and summary.action != RecommendationAction.NONE
            and summary.score >= self._config.minimum_score
            and not quiet_hours_active
            and not cooldown_active
            and stable_for_seconds >= self._config.stability_minutes * 60
        )

        if notification_allowed and self._last_notification_signature != signature:
            self._last_notification_signature = signature
            self._last_notification_at = now

        target_perceived_c = effective_target_temperature_c
        outdoor_perceived_c = outdoor.temperature_c + (
            (outdoor.humidity_percent - self._config.target_humidity_percent)
            * self._recommender.config.humidity_weight
        )
        active_indoor_perceived_c = _average_room_indoor_perceived_temperature(summary)

        snapshot = RuntimeSnapshot(
            summary=summary,
            weather_condition=_weather_condition(
                self._config.outdoor_weather_entity_id,
                self.hass.states.get,
            ),
            target_perceived_c=target_perceived_c,
            suggested_comfort_temperature_c=summary.suggested_comfort_temperature_c,
            outdoor_perceived_c=outdoor_perceived_c,
            active_indoor_perceived_c=active_indoor_perceived_c,
            outdoor_temperature_c=outdoor.temperature_c,
            outdoor_humidity_percent=outdoor.humidity_percent,
            wind_speed_m_s=outdoor.wind_speed_m_s,
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
            target = self._last_notification_at + timedelta(minutes=self._config.cooldown_minutes)
            if target > now:
                candidates.append(target)
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
            last_notification_signature=self._last_notification_signature,
            last_notification_at=self._last_notification_at,
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


def _suggested_comfort_temperature(
    target_temperature_c: float,
    summary: RecommendationSummary,
) -> float | None:
    if not summary.best_room:
        return None
    best_room = next(
        (recommendation for recommendation in summary.room_recommendations if recommendation.room_name == summary.best_room),
        None,
    )
    if best_room is None:
        return None
    balance_point = (best_room.indoor_perceived_c + best_room.outdoor_perceived_c) / 2.0
    suggestion = target_temperature_c + ((balance_point - target_temperature_c) * 0.25)
    return round(max(10.0, min(30.0, suggestion)), 1)


def _average_room_indoor_perceived_temperature(
    summary: RecommendationSummary,
) -> float | None:
    """Return the mean perceived indoor temperature across available rooms."""

    values = [recommendation.indoor_perceived_c for recommendation in summary.room_recommendations]
    if not values:
        return None
    return fsum(values) / len(values)
