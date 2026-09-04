# Scoring Model

## Goal

The score should represent how much opening or closing windows improves
comfort.

The model must prefer:

- meaningful recommendations
- low spam
- behavior that works in both hot and cold seasons

## Evaluation Strategy

For each room:

1. Read indoor temperature and humidity.
2. Read outdoor temperature and humidity.
3. Optionally read wind speed.
4. Compute perceived comfort for inside and outside.
5. Compare both with the comfort target.
6. Decide whether opening or closing creates a larger benefit.

## Climate-Adaptive Comfort Target

The configured comfort temperature is the resident's baseline preference. When
the climate-adaptive target is enabled, VentWise derives an effective target
from the current perceived outdoor temperature:

- 20 C perceived outdoors leaves the baseline unchanged.
- Each degree above or below that reference adjusts the target by 0.25 C.
- The adaptation is capped at plus or minus 2 C and always remains in the
  18–26 C indoor safety range.
- Indoor sensor readings do not alter the target. They describe the room
  condition that the recommendation should improve, avoiding a feedback loop
  where a hot or cold room shifts its own goal.

The target is used only for VentWise scoring and recommendations. It never
changes a thermostat or HVAC setpoint.

## Early Rules

- If the outside condition is closer to the comfort target than the inside
  condition, opening should be favored.
- If the inside condition is already better, closing should be favored.
- If the difference is small, return `none`.

## Soft Threshold

- A soft outside threshold of `22 C` is used to suppress pointless alerts.
- This threshold is not absolute.
- Winter situations are still valid when outside is more comfortable.

## Anti-Spam Rules

- Require a minimum score before sending a notification.
- Require the recommendation to be stable for a short time.
- Apply cooldown after a notification.
- Block notifications temporarily during quiet hours.

## Suggested Initial Shape

The first version can be simple:

- comfort delta from target temperature
- humidity penalty
- wind modifier
- final score from the combined comfort signals

The exact tuning can be adjusted after real-world testing.
