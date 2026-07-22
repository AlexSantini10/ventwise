# Home Assistant Integration

## Final Goal

The project should become a Home Assistant custom integration distributed
through HACS.

## User Configuration

The UI should allow the user to:

- add, edit, and remove rooms
- choose the supported forecast source
- set the ideal comfort temperature
- optionally choose a notification target during the initial setup
- select temperature and humidity sensors per room
- define notification targets and the devices that should receive them
- configure all entity references used by the integration
- set notification cooldown
- define quiet hours and do-not-disturb windows
- temporarily disable notifications without disabling the whole integration
- enable or disable the whole integration
- keep runtime state after a restart
- fall back to the standard weather forecast when optional outdoor sensors or numeric helpers are not configured
- create rooms during the initial setup flow, or skip them and add them later

Supported forecast sources are limited to the standard Home Assistant `weather` entities VentWise can read today. If a different forecast source should be supported, it should be requested as a GitHub issue.

## Implementation Pattern

### Config Flow

Use `config flow` for first-time setup.

### Options Flow

Use `options flow` for later edits.

### Validation

Validate entity domains, numeric ranges, and room definitions before storing
changes in the config entry.

### Device and Entities

Expose one logical device that groups runtime state and controls:

- recommendation state
- score
- reason
- master enable control
- quiet-hour or notification state
- notification target or delivery state
- detailed debug attributes for the recommendation sensors

Use the config flow and options flow for all user-editable inputs such as room
sensors, comfort temperature, and notification target entities.

## Storage

Store configuration in the integration config entry.

Store runtime markers in the same entry so cooldown and last-action state
survive restarts.

Do not require the user to edit YAML for normal operation.

## Core vs Integration Boundary

- Core engine: scoring and recommendation decisions.
- Integration layer: Home Assistant entities, storage, UI, and scheduling.
