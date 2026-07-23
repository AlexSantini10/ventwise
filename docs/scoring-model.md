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
