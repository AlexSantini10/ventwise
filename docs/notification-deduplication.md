# Notification Deduplication

VentWise keeps one notification marker for each room. A marker records the
last delivered action, its stable reason category, severity band, and delivery
time.

Two recommendations are equivalent only when all of the following match for
the same room:

- action (`open` or `close`);
- recommendation reason category (`comfort`, `wind`, or the current weather
  condition);
- severity band: `normal` below 0.55, `elevated` from 0.55 to below 0.75, or
  `urgent` at 0.75 and above.

During a room's configured cooldown, VentWise suppresses only an equivalent
recommendation. A different action, reason, or severity band bypasses that
cooldown and is delivered immediately once the normal stability, quiet-hours,
channel, and minimum-score gates pass.

After the cooldown expires, VentWise may deliver the same recommendation
again. This makes persistent room conditions visible without permanently
silencing them.

Suppressed equivalent recommendations and cooldown bypasses are logged at
debug level with the room, action, reason, severity, and suppression decision.
Markers are persisted across Home Assistant restarts. Markers written by older
VentWise versions do not contain reason or severity, so the first new
recommendation is intentionally treated as changed and can be delivered.
