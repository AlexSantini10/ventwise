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
- choose VentWise temperature (`°C` or `°F`) and wind-speed (`m/s`, `km/h`,
  `mph`, or `kn`) units
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

- aggregate recommendation, score, and localized reason
- current weather, forecast temperature, outdoor pressure, wind speed, and wind gust
- measured and calculated outdoor moisture sensors, including absolute humidity,
  humidity ratio, vapor pressure, and indoor/outdoor moisture difference
- master enable control
- quiet-hour or notification state
- notification target or delivery state
- detailed debug attributes for the recommendation sensors
- one room-level window-state sensor that reports `open`, `closed`,
  `unavailable`, or `not_configured`

The optional global CO₂ sensor is used as the fallback for rooms without a
room-specific CO₂ sensor. A room-specific sensor always takes precedence.
Decision diagnostics remain available as structured attributes on aggregate
and room recommendation entities, including normalized inputs, quality,
traces, candidate scores, core results, and delivery projections.

Measured and calculated sensors are regular Home Assistant sensors. The same
outdoor measurements and calculated values are mirrored on every room device,
so a room such as `Sala visione` can show the shared outdoor context alongside
its indoor values. Diagnostic entity categories are reserved for core and
debug-only values.

VentWise provides native Home Assistant translations for all supported
platforms, including sensors, controls, diagnostics, time entities, states,
and weather conditions. Entity names are resolved using the Home Assistant
server language when the entity is first registered; changing that language
later requires reloading or recreating the integration entities to replace
names already stored in the entity registry.

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
