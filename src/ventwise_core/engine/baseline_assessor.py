"""Default baseline assessment."""

from ..domain.baseline import BaselineAssessment, BaselineState
from ..domain.decision_contracts import DecisionRoom, TraceEntry


class DefaultBaselineAssessor:
    """Use known window state as the explicit reference state."""

    def assess(self, room: DecisionRoom) -> BaselineAssessment:
        observation = room.window_open
        if observation is not None and observation.value is True:
            return BaselineAssessment(
                BaselineState.KEEP_OPEN,
                True,
                "window_known_open",
                (TraceEntry("baseline.window_state", "open"),),
            )
        if observation is not None and observation.value is False:
            return BaselineAssessment(
                BaselineState.KEEP_CLOSED,
                True,
                "window_known_closed",
                (TraceEntry("baseline.window_state", "closed"),),
            )
        return BaselineAssessment(
            BaselineState.UNKNOWN if room.window_contact_configured else BaselineState.KEEP_CLOSED,
            False,
            "window_state_unknown" if room.window_contact_configured else "window_state_not_configured",
        )
