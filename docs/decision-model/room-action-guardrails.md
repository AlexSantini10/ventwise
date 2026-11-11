# Per-room action guardrails

VentWise evaluates every room independently. To avoid noisy sensors making a
room alternate rapidly between **open** and **close**, each room has two simple
settings in its room form:

- **Wait before reversing advice** (default: 5 minutes): a new opposite action
  must remain present for this long before VentWise shows it.
- **Keep room advice for** (default: 30 minutes): after VentWise accepts an
  open or close action, it suppresses the opposite action for this long.

While a reversal is being held, VentWise exposes no action for that room and
explains that the changed advice is settling. This avoids presenting a stale,
potentially incorrect instruction.

An urgent **close** recommendation always bypasses both guardrails, so weather
or safety-related close advice is not delayed. An active observed safety block
always selects close before indoor temperature or contact delivery checks. The
close is delivered when the window is open, its state is unknown, or no window
contact is configured; only a contact already reporting closed suppresses the
duplicate delivery as `window_already_closed`. Missing or stale critical
weather remains fail-closed and does not itself imply that a window is open or
that a hazard was observed. The accepted action, lockout, and pending reversal
are stored in the configuration entry and therefore survive a Home Assistant
restart.
