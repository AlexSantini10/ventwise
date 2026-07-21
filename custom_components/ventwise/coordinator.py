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

from ventwise_core import (
    RecommendationAction,
    RecommendationContext,
    RecommendationSummary,
)
from ventwise_core import ComfortRecommender

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
                notification_allowed=False,
                quiet_hours_active=False,
                cooldown_active=False,
                enabled=True,
                stable_for_seconds=0,
                last_updated=dt_util.utcnow(),
            )

        now = dt_util.now()
        raw_summary = self._recommender.evaluate(
            rooms=rooms,
            outdoor=outdoor,
            context=RecommendationContext(
                quiet_hours_active=False,
                cooldown_active=False,
                stable_for_seconds=10**6,
            ),
        )
        signature = self._signature(raw_summary)
        if signature != self._last_action_signature:
            self._last_action_signature = signature
            self._last_action_started_at = now

        stable_for_seconds = int((now - self._last_action_started_at).total_seconds())
        quiet_hours_start = self._config.quiet_hours_start
        quiet_hours_end = self._config.quiet_hours_end
        if self._config.quiet_hours_start_entity_id:
            quiet_hours_start = _state_to_time_string(
                self.hass.states.get(self._config.quiet_hours_start_entity_id),
                quiet_hours_start,
            )
        if self._config.quiet_hours_end_entity_id:
            quiet_hours_end = _state_to_time_string(
                self.hass.states.get(self._config.quiet_hours_end_entity_id),
                quiet_hours_end,
            )
        quiet_hours_active = self._config.quiet_hours_enabled and is_quiet_hours_active(
            now,
            quiet_hours_start,
            quiet_hours_end,
        )
        if self._config.quiet_hours_pause_entity_id:
            quiet_hours_active = quiet_hours_active or (
                state_to_bool(self.hass.states.get(self._config.quiet_hours_pause_entity_id))
                is True
            )
        cooldown_active = self._last_notification_signature == signature and (
            now - self._last_notification_at
        ) < timedelta(minutes=self._config.cooldown_minutes)

        summary = self._recommender.evaluate(
            rooms=rooms,
            outdoor=outdoor,
            context=RecommendationContext(
                quiet_hours_active=quiet_hours_active,
                cooldown_active=cooldown_active,
                stable_for_seconds=stable_for_seconds,
            ),
        )

        notification_allowed = (
            summary.action != RecommendationAction.NONE
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
            notification_allowed=notification_allowed,
            quiet_hours_active=quiet_hours_active,
            cooldown_active=cooldown_active,
            enabled=True,
            stable_for_seconds=stable_for_seconds,
            last_updated=now,
        )

    async def async_set_enabled(self, enabled: bool) -> None:
        """Persist the master enable flag in config entry options."""

        self.hass.config_entries.async_update_entry(
            self._config_entry,
            options={**self._config_entry.options, "enabled": enabled},
        )
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


def _state_to_time_string(state: Any | None, fallback: str) -> str:
    """Read a time-like entity state and normalize it for quiet hours."""

    raw_state = getattr(state, "state", None)
    if raw_state is None:
        return fallback
    text = str(raw_state).strip()
    if not text:
        return fallback
    if " " in text:
        text = text.split(" ", maxsplit=1)[-1]
    if len(text.split(":")) == 2:
        return f"{text}:00"
    return text
