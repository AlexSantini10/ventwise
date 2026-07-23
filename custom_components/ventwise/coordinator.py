"""Data update coordinator for the integration runtime."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    state_to_bool,
)
from .const import (
    CONF_ROOM_ENABLED,
    CONF_ROOM_ID,
    CONF_ROOMS,
    CONF_STABILITY_MINUTES,
    CONF_TARGET_HUMIDITY_PERCENT,
    CONF_TARGET_TEMPERATURE_C,
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
        super().__init__(
            hass,
            config_entry=config_entry,
            logger=_LOGGER,
            name="VentWise",
            update_interval=timedelta(minutes=1),
        )

    @property
    def config(self) -> IntegrationConfig:
        """Return the normalized integration config."""

        return self._config

    async def _async_update_data(self) -> RuntimeSnapshot:
        """Refresh recommendation state from Home Assistant entity states."""

        self._config = build_integration_config(
            {**self._config_entry.data, **self._config_entry.options}
        )
        self._recommender = ComfortRecommender(build_scoring_config(self._config))

        if not self._config.enabled:
            return RuntimeSnapshot(
                summary=RecommendationSummary(
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="The integration is disabled.",
                    blocked_by="disabled",
                ),
                weather_condition=None,
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

        rooms, outdoor = build_room_profiles(self._config, self.hass.states.get)
        if outdoor is None or not rooms:
            return RuntimeSnapshot(
                summary=RecommendationSummary(
                    action=RecommendationAction.NONE,
                    score=0.0,
                    reason="Outdoor or room sensor data is not available yet.",
                    blocked_by="unavailable",
                ),
                weather_condition=_weather_condition(
                    self._config.outdoor_weather_entity_id,
                    self.hass.states.get,
                ),
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
        if self._config.quiet_hours_pause_entity_id:
            quiet_hours_active = quiet_hours_active or (
                state_to_bool(self.hass.states.get(self._config.quiet_hours_pause_entity_id))
                is True
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

        self._persist_runtime_state()

        return RuntimeSnapshot(
            summary=summary,
            weather_condition=_weather_condition(
                self._config.outdoor_weather_entity_id,
                self.hass.states.get,
            ),
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

        options = dict(self._config_entry.options)
        rooms = [dict(room) for room in options.get(CONF_ROOMS, [])]
        for room in rooms:
            if self._room_matches(room, room_key):
                room[CONF_ROOM_ENABLED] = enabled
                break
        self._update_entry_options({CONF_ROOMS: rooms})
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)

    def _signature(self, summary: RecommendationSummary) -> tuple[str, str]:
        return (summary.action.value, summary.best_room or "")

    def _load_runtime_state(self) -> RuntimeState:
        return load_runtime_state({**self._config_entry.data, **self._config_entry.options})

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

    @staticmethod
    def _room_matches(room: dict[str, Any], room_key: str) -> bool:
        room_id = room.get(CONF_ROOM_ID)
        if room_id is not None and str(room_id) == room_key:
            return True
        return str(room.get("name", "")).strip() == room_key
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
