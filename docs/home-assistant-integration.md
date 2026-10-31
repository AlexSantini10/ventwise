# Home Assistant Integration

## What VentWise Does

VentWise is a Home Assistant custom integration that recommends whether opening
or closing a window is likely to improve comfort. It is an advisory tool: it
does not directly open windows, control shutters, or change a thermostat/HVAC
setpoint.

For installation, first setup, updates, and removal, use the
[user guide](user-guide.md).

## User Configuration

The UI should allow the user to:

- add, edit, and remove rooms
- choose the supported forecast source
- set the ideal comfort temperature
- choose one or more notification targets during the initial setup
- choose forecast or override independently for outdoor temperature, humidity,
  and wind speed
- select temperature and humidity sensors per room
- optionally select one or more binary window contacts per room
- define notification targets and the devices that should receive them
- configure all entity references used by the integration
- set notification cooldown
- define quiet hours and do-not-disturb windows
- temporarily disable notifications without disabling the whole integration
- enable or disable the whole integration
- keep runtime state after a restart
- fall back to the standard weather forecast whenever an outdoor metric stays on forecast
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
- one room-level window-state sensor that reports `open`, `closed`,
  `unavailable`, or `not_configured`

Use the config flow and options flow for all user-editable inputs such as room
sensors, comfort temperature, notification target entities, quiet hours, and
outdoor-data overrides.

When window contacts are configured, VentWise aggregates them per room: the
room is open when any contact is open and closed only when every contact is
closed. It suppresses an open or brief-ventilation recommendation for an
already open room and a close recommendation for an already closed room.
Unavailable contacts do not change the advice; the room window-state entity
shows `unavailable` so the user can assess the data quality.

## Storage

Store configuration in the integration config entry.

Store runtime markers in the same entry so cooldown and last-action state
survive restarts.

Do not require the user to edit YAML for normal operation.

## Core vs Integration Boundary

- Core engine: scoring and recommendation decisions.
- Integration layer: Home Assistant entities, storage, UI, and scheduling.
