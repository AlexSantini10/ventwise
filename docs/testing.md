# Testing

## What Must Be Verified

### Functional behavior

- open recommendation when outside is clearly more comfortable
- close recommendation when inside is already better
- no recommendation when the advantage is marginal

### Seasonal behavior

- summer scenario with outside cooler
- summer scenario with outside warm but still better perceived
- winter scenario with outside warmer and more comfortable
- winter scenario with no real benefit

### Noise control

- notifications do not repeat too often
- cooldown works
- quiet hours block notifications correctly
- short-lived spikes do not trigger alerts

## Test Types

- pure Python unit tests for scoring
- integration tests for configuration handling
- Home Assistant behavior tests for entity updates, if needed later

## Recommended Test Matrix

- inside hotter, outside cooler
- inside cooler, outside hotter
- inside more humid, outside drier
- windy cold outside with warm inside
- neutral conditions near the target

