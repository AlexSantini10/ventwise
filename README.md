# Temperature Comfort Recommender

**A Home Assistant comfort assistant for windows, built for HACS.**

Temperature Comfort Recommender helps you decide when opening or closing
windows is likely to improve indoor comfort. It evaluates temperature,
humidity, wind, and your comfort target, then exposes a clear recommendation
back to Home Assistant.

This project is a native Home Assistant custom integration, not an AppDaemon
app.

## Why this project exists

- Reduce guesswork around when to open or close windows.
- Work across multiple rooms, not just a single sensor pair.
- Keep recommendations useful, quiet, and configurable from the Home Assistant
  UI.
- Provide a clean path to a Home Assistant custom integration distributed via
  HACS.

## Key features

- Comfort-based recommendation engine
- Multi-room support
- Summer and winter behavior
- Quiet hours and cooldowns
- UI-first configuration in Home Assistant
- HACS-ready distribution model

## Planned experience

From Home Assistant, you should be able to:

- define rooms
- choose the sensors for each room
- set your ideal comfort temperature
- configure notification cooldowns
- add quiet hours or temporary notification blocks
- enable or disable the recommender quickly

## Project structure

- `docs/`: development and design documentation
- `src/`: reusable Python comfort engine
- `custom_components/temperature_comfort_recommender/`: Home Assistant
  custom integration
- `tests/`: scoring and behavior tests
- `examples/`: sample configurations and scenarios

## Documentation

- [Project overview](docs/overview.md)
- [Domain model](docs/domain-model.md)
- [Scoring model](docs/scoring-model.md)
- [Home Assistant integration](docs/home-assistant-integration.md)
- [Testing](docs/testing.md)
- [HACS packaging](docs/hacs-packaging.md)
- [License and disclaimer](docs/NOTICE.md)

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](docs/NOTICE.md).
