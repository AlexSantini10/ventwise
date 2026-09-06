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

VentWise always suppresses equivalent recommendations, including after a room's
configured cooldown expires. During the cooldown, it also suppresses
non-urgent updates to a recommendation's reason category or severity. This
prevents short sensor fluctuations from becoming a stream of alerts.

Only these changes bypass the cooldown:

- a different action (`open` or `close`), after the normal stability window;
- an escalation to `urgent` severity, which is delivered immediately.

After the cooldown expires, VentWise can deliver a recommendation only when
its reason category or severity has changed. Small changes to sensor values or
the human-readable explanation do not create a new notification.

Suppressed equivalent recommendations and cooldown bypasses are logged at
debug level with the room, action, reason, severity, and suppression decision.
Markers are persisted across Home Assistant restarts. Markers written by older
VentWise versions do not contain reason or severity, so the first new
recommendation is intentionally treated as changed and can be delivered.
