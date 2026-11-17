# VentWise v0.18.0

## Deterministic Decision Pipeline

This release completes the first usable DDP path. Home Assistant observations
are normalized once into immutable snapshots, evaluated by one deterministic
engine, and rendered through the existing recommendation-only entities.

Implemented behavior includes:

- canonical units, source timestamps, provenance, deterministic room ordering,
  and explicit data quality states;
- RH-based comfort scoring plus humidity-ratio moisture exchange and optional
  bounded CO2 influence in the same objective;
- fail-closed handling for configured safety evidence, severe weather, wind and
  gust blocks, and unknown window contacts;
- urgent close recommendations for known-open windows that bypass ordinary
  delivery suppression;
- immutable aggregate results with evaluation timestamps and sanitized
  component traces.

Forecast trajectories, particulate and pollen policies, adaptive duration,
advanced hysteresis, and calibrated room-impact models remain future work.
