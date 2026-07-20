# Home Assistant Integration

## Final Goal

The project should become a Home Assistant custom integration distributed
through HACS.

## User Configuration

The UI should allow the user to:

- add and remove rooms
- select temperature and humidity sensors per room
- define the ideal comfort temperature
- set notification cooldown
- define quiet hours
- temporarily disable notifications
- enable or disable the whole integration

## Implementation Pattern

### Config Flow

Use `config flow` for first-time setup.

### Options Flow

Use `options flow` for later edits.

### Device and Entities

Expose one logical device that groups:

- recommendation state
- score
- reason
- master enable control
- quiet-hour or notification state

## Storage

Store configuration in the integration config entry.

Do not require the user to edit YAML for normal operation.

## Core vs Integration Boundary

- Core engine: scoring and recommendation decisions.
- Integration layer: Home Assistant entities, storage, UI, and scheduling.

