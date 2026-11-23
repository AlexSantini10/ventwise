#!/usr/bin/env python3
"""Build and run an isolated, persistent Home Assistant test lab for VentWise."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

DEFAULT_IMAGE = "ghcr.io/home-assistant/home-assistant:stable"
DEFAULT_CONTAINER_NAME = "ventwise-ha-test"
DEFAULT_PORT = 8123
PACKAGE_NAME = "ventwise-lab.zip"
PACKAGE_ROOT_FILES = frozenset({"README.md", "LICENSE", "NOTICE", "hacs.json"})
FIXTURES_MARKER = "# VentWise test lab fixtures"

HELPERS_YAML = """ventwise_test_bedroom_temperature:
  name: VentWise Test Bedroom Temperature
  min: 10
  max: 35
  step: 0.1
  initial: 26
  mode: box
  unit_of_measurement: "°C"
ventwise_test_bedroom_humidity:
  name: VentWise Test Bedroom Humidity
  min: 20
  max: 90
  step: 1
  initial: 50
  mode: box
  unit_of_measurement: "%"
ventwise_test_bedroom_co2:
  name: VentWise Test Bedroom CO2
  min: 400
  max: 3000
  step: 10
  initial: 700
  mode: box
  unit_of_measurement: "ppm"
ventwise_test_living_room_temperature:
  name: VentWise Test Living Room Temperature
  min: 10
  max: 35
  step: 0.1
  initial: 19
  mode: box
  unit_of_measurement: "°C"
ventwise_test_living_room_humidity:
  name: VentWise Test Living Room Humidity
  min: 20
  max: 90
  step: 1
  initial: 65
  mode: box
  unit_of_measurement: "%"
ventwise_test_living_room_co2:
  name: VentWise Test Living Room CO2
  min: 400
  max: 3000
  step: 10
  initial: 700
  mode: box
  unit_of_measurement: "ppm"
ventwise_test_outdoor_temperature:
  name: VentWise Test Outdoor Temperature
  min: -20
  max: 45
  step: 0.1
  initial: 23
  mode: box
  unit_of_measurement: "°C"
ventwise_test_outdoor_humidity:
  name: VentWise Test Outdoor Humidity
  min: 0
  max: 100
  step: 1
  initial: 45
  mode: box
  unit_of_measurement: "%"
ventwise_test_wind_speed:
  name: VentWise Test Wind Speed
  min: 0
  max: 30
  step: 0.1
  initial: 2
  mode: box
  unit_of_measurement: "m/s"
ventwise_test_wind_gust:
  name: VentWise Test Wind Gust
  min: 0
  max: 30
  step: 0.1
  initial: 2
  mode: box
  unit_of_measurement: "m/s"
ventwise_test_units_room_temperature:
  name: VentWise Units Lab Room Temperature
  min: 250
  max: 320
  step: 0.01
  initial: 295.15
  mode: box
  unit_of_measurement: "K"
ventwise_test_units_room_humidity:
  name: VentWise Units Lab Room Humidity (ratio 0–1)
  min: 0
  max: 1
  step: 0.01
  initial: 0.5
  mode: box
  unit_of_measurement: "ratio"
ventwise_test_units_room_co2:
  name: VentWise Units Lab Room CO₂
  min: 400
  max: 5000
  step: 10
  initial: 700
  mode: box
  unit_of_measurement: "ppm"
ventwise_test_units_outdoor_temperature:
  name: VentWise Units Lab Outdoor Temperature
  min: 250
  max: 320
  step: 0.01
  initial: 296.15
  mode: box
  unit_of_measurement: "K"
ventwise_test_units_outdoor_humidity:
  name: VentWise Units Lab Outdoor Humidity (ratio 0–1)
  min: 0
  max: 1
  step: 0.01
  initial: 0.45
  mode: box
  unit_of_measurement: "ratio"
ventwise_test_units_wind_speed:
  name: VentWise Units Lab Wind Speed
  min: 0
  max: 100
  step: 0.1
  initial: 14.4
  mode: box
  unit_of_measurement: "km/h"
ventwise_test_units_wind_gust:
  name: VentWise Units Lab Wind Gust
  min: 0
  max: 100
  step: 0.1
  initial: 21.6
  mode: box
  unit_of_measurement: "km/h"
"""

BOOLEANS_YAML = """ventwise_test_bedroom_window_left:
  name: VentWise Test Bedroom Window Left
ventwise_test_bedroom_window_right:
  name: VentWise Test Bedroom Window Right
ventwise_test_living_room_window:
  name: VentWise Test Living Room Window
ventwise_test_bedroom_start:
  name: VentWise Test Bedroom Start Action
ventwise_test_bedroom_stop:
  name: VentWise Test Bedroom Stop Action
ventwise_test_living_room_start:
  name: VentWise Test Living Room Start Action
ventwise_test_living_room_stop:
  name: VentWise Test Living Room Stop Action
"""

CONDITION_YAML = """ventwise_test_weather_condition:
  name: VentWise Test Weather Condition
  options: [sunny, rainy, lightning-rainy]
  initial: sunny
"""

SCRIPTS_YAML = """ventwise_test_reset:
  alias: VentWise Lab - Reset neutral
  mode: restart
  sequence:
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 22}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_humidity
      data: {value: 50}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_co2
      data: {value: 700}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_living_room_temperature
      data: {value: 22}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_living_room_humidity
      data: {value: 50}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_living_room_co2
      data: {value: 700}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 22}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_humidity
      data: {value: 50}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 2}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_gust
      data: {value: 2}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: sunny}
    - service: input_boolean.turn_off
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right
          - input_boolean.ventwise_test_living_room_window

ventwise_test_open_recommendation:
  alias: VentWise Lab - Open recommendation
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 28}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_humidity
      data: {value: 55}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 18}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_humidity
      data: {value: 45}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 2}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: sunny}
    - service: input_boolean.turn_off
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right

ventwise_test_humidity_exchange:
  alias: VentWise Lab - Humidity exchange
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 24}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_humidity
      data: {value: 75}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 20}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_humidity
      data: {value: 35}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 2}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: sunny}
    - service: input_boolean.turn_off
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right
          - input_boolean.ventwise_test_living_room_window

ventwise_test_co2:
  alias: VentWise Lab - CO2 influence
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 23}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_humidity
      data: {value: 50}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_co2
      data: {value: 1800}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 22}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_humidity
      data: {value: 45}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 2}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: sunny}

ventwise_test_weather_block:
  alias: VentWise Lab - Severe weather block
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 28}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 18}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 2}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: lightning-rainy}
    - service: input_boolean.turn_off
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right

ventwise_test_wind_block:
  alias: VentWise Lab - Wind block
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 28}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 18}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 15}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: sunny}
    - service: input_boolean.turn_off
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right

ventwise_test_urgent_close:
  alias: VentWise Lab - Urgent close
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 23}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 5}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 15}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: lightning-rainy}
    - service: input_boolean.turn_on
      target:
        entity_id: input_boolean.ventwise_test_bedroom_window_left

ventwise_test_gust_block:
  alias: VentWise Lab - Gust block
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_bedroom_temperature}
      data: {value: 28}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_outdoor_temperature}
      data: {value: 18}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_wind_speed}
      data: {value: 2}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_wind_gust}
      data: {value: 15}
    - service: input_select.select_option
      target: {entity_id: input_select.ventwise_test_weather_condition}
      data: {option: sunny}

ventwise_test_multi_room:
  alias: VentWise Lab - Multi-room split
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_bedroom_temperature
      data: {value: 28}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_living_room_temperature
      data: {value: 18}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_outdoor_temperature
      data: {value: 22}
    - service: input_number.set_value
      target:
        entity_id:
          - input_number.ventwise_test_bedroom_humidity
          - input_number.ventwise_test_living_room_humidity
      data: {value: 50}
    - service: input_number.set_value
      target:
        entity_id: input_number.ventwise_test_wind_speed
      data: {value: 2}
    - service: input_select.select_option
      target:
        entity_id: input_select.ventwise_test_weather_condition
      data: {option: sunny}
    - service: input_boolean.turn_off
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right
          - input_boolean.ventwise_test_living_room_window

ventwise_test_close_recommendation:
  alias: VentWise Lab - Close recommendation
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_bedroom_temperature}
      data: {value: 20}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_outdoor_temperature}
      data: {value: 30}
    - service: input_boolean.turn_on
      target:
        entity_id: input_boolean.ventwise_test_bedroom_window_left

ventwise_test_ventilate:
  alias: VentWise Lab - Ventilate recommendation
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_bedroom_temperature}
      data: {value: 25}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_outdoor_temperature}
      data: {value: 18}

ventwise_test_winter_symmetry:
  alias: VentWise Lab - Winter symmetry
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_bedroom_temperature}
      data: {value: 16}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_outdoor_temperature}
      data: {value: 22}

ventwise_test_marginal_benefit:
  alias: VentWise Lab - Marginal benefit
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_bedroom_temperature}
      data: {value: 22.3}
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_outdoor_temperature}
      data: {value: 22}

ventwise_test_co2_threshold:
  alias: VentWise Lab - CO2 threshold
  mode: restart
  sequence:
    - service: script.ventwise_test_reset
    - service: input_number.set_value
      target: {entity_id: input_number.ventwise_test_bedroom_co2}
      data: {value: 1000}

ventwise_test_window_already_open:
  alias: VentWise Lab - Window already open
  mode: restart
  sequence:
    - service: script.ventwise_test_open_recommendation
    - service: input_boolean.turn_on
      target:
        entity_id: input_boolean.ventwise_test_bedroom_window_left

ventwise_test_multiple_windows:
  alias: VentWise Lab - Multiple window contacts
  mode: restart
  sequence:
    - service: script.ventwise_test_open_recommendation
    - service: input_boolean.turn_on
      target:
        entity_id:
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right
"""

TEMPLATE_YAML = """- binary_sensor:
    - name: VentWise Test Bedroom Window Left
      unique_id: ventwise_test_bedroom_window_left
      device_class: window
      state: "{{ is_state('input_boolean.ventwise_test_bedroom_window_left', 'on') }}"
    - name: VentWise Test Bedroom Window Right
      unique_id: ventwise_test_bedroom_window_right
      device_class: window
      state: "{{ is_state('input_boolean.ventwise_test_bedroom_window_right', 'on') }}"
    - name: VentWise Test Living Room Window
      unique_id: ventwise_test_living_room_window
      device_class: window
      state: "{{ is_state('input_boolean.ventwise_test_living_room_window', 'on') }}"
- weather:
    - name: VentWise Test Weather
      unique_id: ventwise_test_weather
      condition_template: "{{ states('input_select.ventwise_test_weather_condition') }}"
      temperature_template: "{{ states('input_number.ventwise_test_outdoor_temperature') | float(23) }}"
      temperature_unit: "°C"
      humidity_template: "{{ states('input_number.ventwise_test_outdoor_humidity') | float(45) }}"
      wind_speed_template: "{{ states('input_number.ventwise_test_wind_speed') | float(2) }}"
      wind_speed_unit: "m/s"
      wind_gust_speed_template: "{{ states('input_number.ventwise_test_wind_gust') | float(2) }}"
"""

DASHBOARD_CONFIG_YAML = """dashboards:
  ventwise-test-lab:
    mode: yaml
    title: VentWise Test Lab
    icon: mdi:test-tube
    show_in_sidebar: true
    filename: ventwise_test_dashboard.yaml
  ventwise-core-lab:
    mode: yaml
    title: VentWise Core Lab
    icon: mdi:cpu-64-bit
    show_in_sidebar: true
    filename: ventwise_core_dashboard.yaml
  ventwise-units-lab:
    mode: yaml
    title: VentWise Units Lab
    icon: mdi:scale-balance
    show_in_sidebar: true
    filename: ventwise_units_dashboard.yaml
"""

UNITS_DASHBOARD_YAML = """title: VentWise Units Lab
views:
  - title: Unità non standard
    path: ventwise-units-lab
    icon: mdi:scale-balance
    cards:
      - type: markdown
        content: |
          # VentWise Units Lab

          Questi helper dichiarano unità diverse da quelle canoniche di
          VentWise: Kelvin, frazioni di umidità (ratio, 0–1) e km/h. Modifica
          i valori e osserva che VentWise converte 0,5 ratio in 50% e continua
          a calcolare usando °C, %, e m/s.
      - type: entities
        title: Sorgenti non standard
        entities:
          - input_number.ventwise_test_units_room_temperature
          - input_number.ventwise_test_units_room_humidity
          - input_number.ventwise_test_units_room_co2
          - input_number.ventwise_test_units_outdoor_temperature
          - input_number.ventwise_test_units_outdoor_humidity
          - input_number.ventwise_test_units_wind_speed
          - input_number.ventwise_test_units_wind_gust
      - type: entities
        title: Risultato VentWise
        entities:
          - sensor.units_lab_room_indoor_temperature
          - sensor.units_lab_room_indoor_humidity
          - sensor.units_lab_room_recommendation
          - sensor.units_lab_room_reason
          - sensor.units_lab_room_wind_speed
"""

CORE_DASHBOARD_YAML = """title: VentWise Core Lab
views:
  - title: Motore deterministico
    path: ventwise-core-lab
    icon: mdi:cpu-64-bit
    cards:
      - type: markdown
        content: |
          # VentWise Core Lab

          Questa pagina usa una seconda istanza VentWise con una sola stanza,
          nessun contatto finestra e nessuna delivery notification. L'unico
          risultato mostrato è quello prodotto dal motore deterministico.

          Premi un preset, poi **Ricevi consiglio core**.
      - type: grid
        columns: 2
        square: false
        cards:
          - type: button
            name: Reset neutral
            icon: mdi:restore
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_reset}
          - type: button
            name: Open
            icon: mdi:window-open
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_open_recommendation}
          - type: button
            name: Close
            icon: mdi:window-closed
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_close_recommendation}
          - type: button
            name: Ventilate
            icon: mdi:air-filter
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_ventilate}
          - type: button
            name: Humidity exchange
            icon: mdi:water-percent
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_humidity_exchange}
          - type: button
            name: CO2 influence
            icon: mdi:molecule-co2
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_co2}
          - type: button
            name: Weather block
            icon: mdi:weather-lightning-rainy
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_weather_block}
          - type: button
            name: Wind block
            icon: mdi:weather-windy
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_wind_block}
          - type: button
            name: Gust block
            icon: mdi:weather-windy-variant
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_gust_block}
          - type: button
            name: Winter symmetry
            icon: mdi:snowflake-thermometer
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_winter_symmetry}
          - type: button
            name: Marginal benefit
            icon: mdi:scale-balance
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_marginal_benefit}
          - type: button
            name: CO2 threshold
            icon: mdi:molecule-co2
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target: {entity_id: script.ventwise_test_co2_threshold}
      - type: entities
        title: Core inputs
        entities:
          - input_number.ventwise_test_outdoor_temperature
          - input_number.ventwise_test_outdoor_humidity
          - input_number.ventwise_test_wind_speed
          - input_number.ventwise_test_wind_gust
          - input_select.ventwise_test_weather_condition
          - input_number.ventwise_test_bedroom_temperature
          - input_number.ventwise_test_bedroom_humidity
          - input_number.ventwise_test_bedroom_co2
      - type: button
        entity: button.ventwise_core_lab_request_recommendation
        name: Ricevi consiglio core
        icon: mdi:cpu-64-bit
        tap_action:
          action: perform-action
          perform_action: button.press
          target: {entity_id: button.ventwise_core_lab_request_recommendation}
      - type: entities
        title: Core deterministic output
        entities:
          - sensor.core_engine_room_recommendation
          - sensor.core_engine_room_score
          - sensor.core_engine_room_reason
          - binary_sensor.core_engine_room_active
      - type: markdown
        content: |
          ```json
          {{ state_attr('sensor.core_engine_room_recommendation', 'core_result') | tojson }}
          ```
"""

DASHBOARD_YAML = """title: VentWise Test Lab
views:
  - title: Prova VentWise
    path: ventwise-test-lab
    icon: mdi:test-tube
    cards:
      - type: markdown
        content: |
          # VentWise Test Lab

          Modifica un dato di prova, poi premi **Ricevi consiglio ora**. I
          risultati e le motivazioni vengono aggiornati qui sotto: non serve
          alcun dispositivo fisico.

          **Scenari rapidi:** con finestre chiuse, imposta una stanza più calda
          e l'esterno più fresco per ottenere un consiglio di apertura. Apri
          poi uno dei contatti della camera: VentWise non deve suggerire di
          riaprire una finestra già aperta. La camera ha due contatti: ne basta
          uno aperto perché lo stato aggregato sia `open`.
      - type: horizontal-stack
        cards:
          - type: button
            entity: input_boolean.ventwise_test_bedroom_window_left
            name: Apri/chiudi finestra camera
            icon: mdi:window-open-variant
            tap_action:
              action: toggle
          - type: button
            entity: input_boolean.ventwise_test_living_room_window
            name: Apri/chiudi finestra soggiorno
            icon: mdi:window-open-variant
            tap_action:
              action: toggle
      - type: markdown
        content: |
          ## Preset v0.18

          Each button sets the complete scenario. Press **Receive recommendation
          now** after selecting a preset. **Reset neutral** restores the baseline.
      - type: grid
        columns: 2
        square: false
        cards:
          - type: button
            name: Reset neutral
            icon: mdi:restore
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_reset
          - type: button
            name: Open recommendation
            icon: mdi:window-open
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_open_recommendation
          - type: button
            name: Humidity exchange
            icon: mdi:water-percent
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_humidity_exchange
          - type: button
            name: CO2 influence
            icon: mdi:molecule-co2
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_co2
          - type: button
            name: Weather block
            icon: mdi:weather-lightning-rainy
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_weather_block
          - type: button
            name: Wind block
            icon: mdi:weather-windy
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_wind_block
          - type: button
            name: Gust block
            icon: mdi:weather-windy-variant
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_gust_block
          - type: button
            name: Urgent close
            icon: mdi:window-shutter-alert
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_urgent_close
          - type: button
            name: Multi-room split
            icon: mdi:home-split
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_multi_room
          - type: button
            name: Close recommendation
            icon: mdi:window-closed
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_close_recommendation
          - type: button
            name: Ventilate recommendation
            icon: mdi:air-filter
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_ventilate
          - type: button
            name: Winter symmetry
            icon: mdi:snowflake-thermometer
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_winter_symmetry
          - type: button
            name: Marginal benefit
            icon: mdi:scale-balance
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_marginal_benefit
          - type: button
            name: CO2 threshold
            icon: mdi:molecule-co2
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_co2_threshold
          - type: button
            name: Window already open
            icon: mdi:window-open-variant
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_window_already_open
          - type: button
            name: Multiple contacts
            icon: mdi:window-open
            tap_action:
              action: perform-action
              perform_action: script.turn_on
              target:
                entity_id: script.ventwise_test_multiple_windows
      - type: entities
        title: Dati esterni simulati
        entities:
          - input_number.ventwise_test_outdoor_temperature
          - input_number.ventwise_test_outdoor_humidity
          - input_number.ventwise_test_wind_speed
          - input_number.ventwise_test_wind_gust
          - input_select.ventwise_test_weather_condition
          - weather.ventwise_test_weather
      - type: entities
        title: Dati simulati — Camera
        entities:
          - input_number.ventwise_test_bedroom_temperature
          - input_number.ventwise_test_bedroom_humidity
          - input_number.ventwise_test_bedroom_co2
          - input_boolean.ventwise_test_bedroom_window_left
          - input_boolean.ventwise_test_bedroom_window_right
          - binary_sensor.ventwise_test_bedroom_window_left
          - binary_sensor.ventwise_test_bedroom_window_right
      - type: entities
        title: Dati simulati — Soggiorno
        entities:
          - input_number.ventwise_test_living_room_temperature
          - input_number.ventwise_test_living_room_humidity
          - input_number.ventwise_test_living_room_co2
          - input_boolean.ventwise_test_living_room_window
          - binary_sensor.ventwise_test_living_room_window
      - type: button
        entity: button.ventwise_test_lab_request_recommendation
        name: Ricevi consiglio ora
        icon: mdi:message-text-fast-outline
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.ventwise_test_lab_request_recommendation
      - type: entities
        title: Controlli VentWise
        entities:
          - switch.ventwise_test_lab_master_enable
          - switch.ventwise_test_lab_notification_enable
          - switch.ventwise_test_lab_auto_comfort_temperature
          - switch.ventwise_test_lab_quiet_hours_enable
          - time.ventwise_test_lab_quiet_hours_start
          - time.ventwise_test_lab_quiet_hours_end
      - type: entities
        title: Risultati VentWise — Camera
        entities:
          - sensor.camera_test_recommendation
          - sensor.camera_test_score
          - sensor.camera_test_reason
          - sensor.camera_test_window_state
          - binary_sensor.camera_test_active
      - type: entities
        title: Risultati VentWise — Soggiorno
        entities:
          - sensor.living_room_recommendation
          - sensor.living_room_score
          - sensor.living_room_reason
          - sensor.living_room_window_state
          - binary_sensor.living_room_active
      - type: markdown
        content: |
          ## Raw engine output

          The cards below expose structured, non-localized diagnostics. `core_action`
          is the pure engine result; `delivered_action` includes HA delivery filters.

          **Camera** — core: `{{ state_attr('sensor.camera_test_recommendation', 'core_action') }}`; delivered: `{{ state_attr('sensor.camera_test_recommendation', 'delivered_action') }}`

          ```json
          {{ state_attr('sensor.camera_test_recommendation', 'core_result') | tojson }}
          ```

          **Living room** — core: `{{ state_attr('sensor.living_room_recommendation', 'core_action') }}`; delivered: `{{ state_attr('sensor.living_room_recommendation', 'delivered_action') }}`

          ```json
          {{ state_attr('sensor.living_room_recommendation', 'core_result') | tojson }}
          ```

      - type: markdown
        content: |
          ## Delivery filter checks

          The core result must remain unchanged while delivery is filtered.
          Enable quiet hours and set its active interval around the current
          time to verify `quiet_hours`. Set a non-zero stability interval and
          press **Receive recommendation now** before it expires to verify
          `stability`. Repeat the same recommendation after a successful
          notification to verify `duplicate`/`cooldown`. Disable the
          notification channel to verify `notification_channel`.
"""

BOOTSTRAP_MANIFEST = '{"domain":"ventwise_lab_bootstrap","name":"VentWise Test Lab Bootstrap","version":"1.0.0","integration_type":"helper","config_flow":true,"requirements":[],"codeowners":[]}'
BOOTSTRAP_INIT = '''"""Provision the repeatable VentWise Lab config entries."""
from homeassistant.config_entries import ConfigEntry

DOMAIN = "ventwise_lab_bootstrap"
FULL_DATA = {
    "outdoor_weather_entity_id": "weather.ventwise_test_weather",
    "target_temperature_c": 22.0, "target_humidity_percent": 50.0,
    "co2_enabled": True, "co2_threshold_ppm": 1000.0,
    "stability_minutes": 0, "co2_enabled": True, "co2_threshold_ppm": 1000.0,
    "home_assistant_notification_enabled": True,
    "rooms": [
        {"kind": "room", "room_id": "camera_test", "name": "Camera test", "enabled": True,
         "temperature_entity_id": "input_number.ventwise_test_bedroom_temperature",
         "humidity_entity_id": "input_number.ventwise_test_bedroom_humidity",
         "co2_entity_id": "input_number.ventwise_test_bedroom_co2",
         "window_sensor_entity_ids": ["binary_sensor.ventwise_test_bedroom_window_left", "binary_sensor.ventwise_test_bedroom_window_right"],
         "start_entity_id": "input_boolean.ventwise_test_bedroom_start", "stop_entity_id": "input_boolean.ventwise_test_bedroom_stop"},
        {"kind": "room", "room_id": "living_room", "name": "Living room", "enabled": True,
         "temperature_entity_id": "input_number.ventwise_test_living_room_temperature",
         "humidity_entity_id": "input_number.ventwise_test_living_room_humidity",
         "co2_entity_id": "input_number.ventwise_test_living_room_co2",
         "window_sensor_entity_ids": ["binary_sensor.ventwise_test_living_room_window"],
         "start_entity_id": "input_boolean.ventwise_test_living_room_start", "stop_entity_id": "input_boolean.ventwise_test_living_room_stop"},
    ],
}

CORE_DATA = {
    "outdoor_weather_entity_id": "weather.ventwise_test_weather",
    "target_temperature_c": 22.0, "target_humidity_percent": 50.0,
    "co2_enabled": True, "co2_threshold_ppm": 1000.0,
    "stability_minutes": 0, "cooldown_minutes": 0,
    "quiet_hours_enabled": False, "notification_enabled": False,
    "home_assistant_notification_enabled": False,
    "rooms": [
        {"kind": "room", "room_id": "core_engine_room", "name": "Core engine room", "enabled": True,
         "temperature_entity_id": "input_number.ventwise_test_bedroom_temperature",
         "humidity_entity_id": "input_number.ventwise_test_bedroom_humidity",
         "co2_entity_id": "input_number.ventwise_test_bedroom_co2"},
    ],
}

UNITS_DATA = {
    "outdoor_temperature_entity_id": "input_number.ventwise_test_units_outdoor_temperature",
    "outdoor_humidity_entity_id": "input_number.ventwise_test_units_outdoor_humidity",
    "wind_speed_entity_id": "input_number.ventwise_test_units_wind_speed",
    "target_temperature_c": 22.0, "target_humidity_percent": 50.0,
    "co2_enabled": True, "co2_threshold_ppm": 1000.0,
    "stability_minutes": 0, "cooldown_minutes": 0,
    "quiet_hours_enabled": False, "notification_enabled": False,
    "rooms": [
        {"kind": "room", "room_id": "units_lab_room", "name": "Units lab room", "enabled": True,
         "temperature_entity_id": "input_number.ventwise_test_units_room_temperature",
         "humidity_entity_id": "input_number.ventwise_test_units_room_humidity",
         "co2_entity_id": "input_number.ventwise_test_units_room_co2",
         "co2_enabled": True},
    ],
}

ENTRIES = (
    ("ventwise_test_full_lab", "VentWise Test Lab", FULL_DATA),
    ("ventwise_test_core_lab", "VentWise Core Lab", CORE_DATA),
    ("ventwise_test_units_lab", "VentWise Units Lab", UNITS_DATA),
)

async def async_setup(hass, config):
    hass.data["ventwise_lab_bootstrap"] = True
    existing = {
        entry.unique_id
        for entry in hass.config_entries.async_entries("ventwise")
    }
    for unique_id, title, data in ENTRIES:
        if unique_id in existing:
            continue
        entry = ConfigEntry(
            domain="ventwise", title=title, data=data, options={}, source="user",
            version=4, minor_version=1, unique_id=unique_id,
            discovery_keys={}, subentries_data=None,
        )
        await hass.config_entries.async_add(entry)
    bootstrap_entries = hass.config_entries.async_entries(DOMAIN)
    if not any(entry.unique_id == "ventwise_lab_bootstrap" for entry in bootstrap_entries):
        async def add_helper_entry() -> None:
            await hass.config_entries.async_add(
                ConfigEntry(
                    domain=DOMAIN,
                    title="VentWise Lab Helpers",
                    data={},
                    options={},
                    source="import",
                    version=1,
                    minor_version=0,
                    unique_id="ventwise_lab_bootstrap",
                    discovery_keys={},
                    subentries_data=None,
                )
            )
        hass.async_create_task(add_helper_entry())
    return True


async def async_setup_entry(hass, entry):
    """Set up the Lab notification helper."""
    await hass.config_entries.async_forward_entry_setups(entry, ["notify"])
    return True
'''

BOOTSTRAP_NOTIFY = '''"""Provide an isolated notification device for the VentWise Lab."""

from homeassistant.components.notify import NotifyEntity
from homeassistant.helpers.entity import DeviceInfo


class VentWiseLabNotifyEntity(NotifyEntity):
    """A local notification sink used only by the Docker Lab."""

    _attr_name = "VentWise Lab notifications"
    _attr_unique_id = "ventwise_lab_notifications"
    _attr_device_info = DeviceInfo(
        identifiers={("ventwise_lab_bootstrap", "notification_device")},
        name="VentWise Lab notification device",
        manufacturer="VentWise",
    )

    async def async_send_message(self, message: str, title: str | None = None, **kwargs) -> None:
        """Accept the message without sending it outside the isolated Lab."""
        self._async_record_notification()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Lab notification entity."""
    async_add_entities([VentWiseLabNotifyEntity()])
'''

BOOTSTRAP_CONFIG_FLOW = '''"""Keep the internal VentWise Lab helper config entry non-interactive."""

from homeassistant import config_entries

DOMAIN = "ventwise_lab_bootstrap"


class VentWiseLabBootstrapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Do not expose the Lab helper as a user-configurable integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Abort any accidental manual setup attempt."""
        return self.async_abort(reason="single_instance_allowed")
'''


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_config_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    return (Path(local_app_data) / "VentWise-HA-Test") if local_app_data else Path.home() / ".ventwise-ha-test"


def run(command: list[str]) -> None:
    if subprocess.run(command, check=False).returncode:
        raise SystemExit(1)


def docker_output(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()


def integration_version(integration_dir: Path) -> str:
    try:
        version = json.loads((integration_dir / "manifest.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError) as error:
        raise SystemExit(f"Could not read VentWise manifest: {error}") from error
    if not isinstance(version, str) or not version.strip():
        raise SystemExit(f"VentWise manifest has no usable version: {integration_dir / 'manifest.json'}")
    return version.strip()


def build_package(config_root: Path) -> Path:
    package = config_root / "artifacts" / PACKAGE_NAME
    package.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(repo_root() / "scripts" / "build_release_package.py"), "--source-path", str(repo_root()), "--output-path", str(package)])
    return package


def install_package(package: Path, config_dir: Path) -> Path:
    """Install only package files into the Lab, never from a source bind mount."""
    target = config_dir / "custom_components" / "ventwise"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    with ZipFile(package) as archive:
        if "manifest.json" not in archive.namelist():
            raise SystemExit(f"Invalid VentWise package without manifest: {package}")
        for name in archive.namelist():
            if name in PACKAGE_ROOT_FILES or name.endswith("/"):
                continue
            destination = (target / name).resolve()
            if target.resolve() not in destination.parents:
                raise SystemExit(f"Unsafe path in VentWise package: {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    return target


def ensure_config(config_root: Path) -> Path:
    config_dir = config_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    configuration = config_dir / "configuration.yaml"
    if not configuration.exists():
        configuration.write_text(
            "default_config:\n\nhomeassistant:\n  name: VentWise Test Lab\n  language: it\n",
            encoding="utf-8",
        )
    lines = (
        "input_number: !include ventwise_test_helpers.yaml", "input_boolean: !include ventwise_test_booleans.yaml",
        "input_select: !include ventwise_test_weather_condition.yaml", "template: !include ventwise_test_template.yaml",
        "script: !include ventwise_test_scripts.yaml",
        "lovelace: !include ventwise_test_dashboards.yaml", "ventwise_lab_bootstrap:",
    )
    text = configuration.read_text(encoding="utf-8")
    if "  language: it" not in text and "homeassistant:" in text:
        text = text.replace(
            "homeassistant:\n  name: VentWise Test Lab",
            "homeassistant:\n  name: VentWise Test Lab\n  language: it",
        )
        configuration.write_text(text, encoding="utf-8")
    missing = [line for line in lines if line not in text]
    if missing:
        marker = f"{FIXTURES_MARKER}\n" if FIXTURES_MARKER not in text else ""
        configuration.write_text(f"{text.rstrip()}\n\n{marker}{'\n'.join(missing)}\n", encoding="utf-8")
    for name, content in {
        "ventwise_test_helpers.yaml": HELPERS_YAML, "ventwise_test_booleans.yaml": BOOLEANS_YAML,
        "ventwise_test_weather_condition.yaml": CONDITION_YAML, "ventwise_test_template.yaml": TEMPLATE_YAML,
        "ventwise_test_scripts.yaml": SCRIPTS_YAML,
        "ventwise_test_dashboards.yaml": DASHBOARD_CONFIG_YAML, "ventwise_test_dashboard.yaml": DASHBOARD_YAML,
        "ventwise_core_dashboard.yaml": CORE_DASHBOARD_YAML,
        "ventwise_units_dashboard.yaml": UNITS_DASHBOARD_YAML,
    }.items():
        (config_dir / name).write_text(content, encoding="utf-8")
    bootstrap = config_dir / "custom_components" / "ventwise_lab_bootstrap"
    bootstrap.mkdir(parents=True, exist_ok=True)
    (bootstrap / "manifest.json").write_text(BOOTSTRAP_MANIFEST, encoding="utf-8")
    (bootstrap / "__init__.py").write_text(BOOTSTRAP_INIT, encoding="utf-8")
    (bootstrap / "notify.py").write_text(BOOTSTRAP_NOTIFY, encoding="utf-8")
    (bootstrap / "config_flow.py").write_text(BOOTSTRAP_CONFIG_FLOW, encoding="utf-8")
    return config_dir


def container_exists(name: str) -> bool:
    return bool(docker_output(["docker", "ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"]))


def stop_container(name: str) -> None:
    if container_exists(name):
        run(["docker", "rm", "-f", name])


def mounted_integration_version(name: str) -> str:
    return docker_output(["docker", "exec", name, "python", "-c", "import json; from pathlib import Path; print(json.loads(Path('/config/custom_components/ventwise/manifest.json').read_text(encoding='utf-8'))['version'])"])


def verify_mounted_integration_version(name: str, expected: str) -> None:
    actual = mounted_integration_version(name)
    if actual != expected:
        raise SystemExit(f"VentWise package version mismatch: expected {expected}, container sees {actual}.")


def start_container(name: str, image: str, config_dir: Path, port: int, timezone: str) -> None:
    stop_container(name)
    run(["docker", "run", "-d", "--name", name, "-p", f"{port}:8123", "-e", f"TZ={timezone}", "-v", f"{config_dir}:/config", image])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("up", "down", "logs", "restart", "reset"), default="up")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--container-name", default=DEFAULT_CONTAINER_NAME)
    parser.add_argument("--config-root", type=Path, default=default_config_root())
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timezone", default="Europe/Rome")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if shutil.which("docker") is None:
        raise SystemExit("Docker is not installed or not available on PATH.")
    if args.action == "reset":
        stop_container(args.container_name)
        if args.config_root.exists():
            shutil.rmtree(args.config_root)
        print(f"VentWise Test Lab reset: {args.config_root}")
        return 0
    if args.action == "down":
        stop_container(args.container_name)
        return 0
    if args.action == "logs":
        run(["docker", "logs", "-f", args.container_name])
        return 0
    config_dir = ensure_config(args.config_root)
    package = build_package(args.config_root)
    version = integration_version(install_package(package, config_dir))
    start_container(args.container_name, args.image, config_dir, args.port, args.timezone)
    verify_mounted_integration_version(args.container_name, version)
    print(f"VentWise Test Lab is starting at http://localhost:{args.port}")
    print(f"Runtime profile: {config_dir}\nInstalled package: {package}\nVentWise version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
