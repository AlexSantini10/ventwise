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
or safety-related close advice is not delayed. The accepted action, lockout,
and pending reversal are stored in the configuration entry and therefore
survive a Home Assistant restart.
