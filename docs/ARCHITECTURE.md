# VentWise Architecture

## Purpose

This project will become a Home Assistant custom integration distributed through
HACS. The goal is to help users decide when opening or closing windows improves
comfort, while keeping the configuration simple from the Home Assistant UI.

## Final Delivery Model

- Reusable comfort-scoring core in Python.
- Home Assistant custom integration on top of the core.
- HACS as the distribution channel.
- UI-first configuration with no manual YAML required for normal use.
- No AppDaemon layer.

## High-Level Layers

### 1. Core Engine

- Pure Python logic.
- Independent from Home Assistant APIs.
- Handles:
  - comfort scoring
  - indoor vs outdoor comparison
  - humidity and wind modifiers
  - anti-spam and cooldown decisions

### 2. Home Assistant Integration

- Exposes a `config flow` to create the integration.
- Exposes an `options flow` to edit the configuration later.
- Creates a single visible device for the recommender.
- Creates entities for:
  - current recommendation
  - score
  - reason
  - master enable/disable
  - quiet hours / do-not-disturb controls
  - notification target or delivery state
- Stores room configuration and thresholds in the integration config entry.
- Keeps all user-editable entity references and comfort settings in the
  config entry, surfaced through the UI.

### 3. HACS Packaging

- The repository is meant to be published as a HACS custom repository.
- HACS installs the integration into Home Assistant.
- The user updates it from HACS like any other custom integration.

## User Experience in Home Assistant

The user should be able to:

- define rooms from the UI
- choose the sensors for each room
- choose notification targets and devices
- set the ideal comfort temperature
- configure all entity selectors used by the integration
- configure notification frequency
- configure quiet hours and do-not-disturb windows, such as night silence
- temporarily block notifications without disabling the whole integration

## Recommended Entity Model

- `sensor.*` for score and explanation
- `binary_sensor.*` for action state or active recommendation
- `switch.*` or `input_boolean.*` for master enable
- `device` to group all recommender entities neatly in the UI

## Reusability Rules

- Do not hardcode entity IDs in the core engine.
- Keep room definitions in configuration data.
- Support multiple rooms from the start.
- Make the configuration understandable to non-developers.

## Current Repo Mapping

- `src/`: core engine experiments and reusable logic.
- `custom_components/temperature_comfort_recommender/`: future Home Assistant integration code.
- `tests/`: scoring and behavior tests.
- `examples/`: sample configurations and scenarios.
- `docs/`: design and usage notes.

## Future Direction

Once the architecture is stable, the project can be moved into a new standalone
repository and packaged for HACS publication.
