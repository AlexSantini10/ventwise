# Domain Model

## Core Concepts

### Room

A room represents a comfort evaluation scope.

Each room has:

- name
- indoor temperature sensor
- indoor humidity sensor
- optional local notes or label

### External Context

Global values used by all rooms:

- outdoor temperature
- outdoor humidity
- wind speed
- optional quiet-hour schedule

### Comfort Target

The comfort target is the temperature the user considers most pleasant.

It must be configurable from the Home Assistant UI.

### Recommendation

The engine should output one of:

- `open`
- `close`
- `none`

It should also provide:

- score
- reason
- confidence or strength indicator

## First Target Sensors

- Camera:
  - `sensor.termometro_camera_temperatura`
  - `sensor.termometro_camera_umidita`
- Zona giorno:
  - `sensor.termometro_salotto_temperatura`
  - `sensor.termometro_salotto_umidita`

## Configuration Objects

The integration should keep a per-room structure with:

- room name
- temperature sensor entity
- humidity sensor entity
- room-specific weights or overrides, if needed later

