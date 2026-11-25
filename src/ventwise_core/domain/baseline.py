"""Baseline state and assessment contracts."""

from dataclasses import dataclass
from enum import Enum

from .decision_contracts import TraceEntry


class BaselineState(str, Enum):
    """State maintained when no new action is selected."""

    KEEP_OPEN = "keep_open"
    KEEP_CLOSED = "keep_closed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BaselineAssessment:
    """Explicit reference state used to compare every candidate."""

    state: BaselineState
    window_state_known: bool
    reason_code: str
    evidence: tuple[TraceEntry, ...] = ()
