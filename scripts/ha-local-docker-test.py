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
  options: [sunny, rainy, thunderstorm]
  initial: sunny
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
      condition: "{{ states('input_select.ventwise_test_weather_condition') }}"
      temperature: "{{ states('input_number.ventwise_test_outdoor_temperature') | float(23) }}"
      temperature_unit: "°C"
      humidity: "{{ states('input_number.ventwise_test_outdoor_humidity') | float(45) }}"
      wind_speed: "{{ states('input_number.ventwise_test_wind_speed') | float(2) }}"
      wind_speed_unit: "m/s"
"""

DASHBOARD_CONFIG_YAML = """dashboards:
  ventwise-test-lab:
    mode: yaml
    title: VentWise Test Lab
    icon: mdi:test-tube
    show_in_sidebar: true
    filename: ventwise_test_dashboard.yaml
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
      - type: entities
        title: Dati esterni simulati
        entities:
          - input_number.ventwise_test_outdoor_temperature
          - input_number.ventwise_test_outdoor_humidity
          - input_number.ventwise_test_wind_speed
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
"""

BOOTSTRAP_MANIFEST = '{"domain":"ventwise_lab_bootstrap","name":"VentWise Test Lab Bootstrap","version":"1.0.0","integration_type":"helper","requirements":[],"codeowners":[]}'
BOOTSTRAP_INIT = '''"""Provision the repeatable VentWise Lab config entry."""
from homeassistant.config_entries import ConfigEntry

DOMAIN = "ventwise_lab_bootstrap"
DATA = {
    "outdoor_weather_entity_id": "weather.ventwise_test_weather",
    "target_temperature_c": 22.0, "target_humidity_percent": 50.0,
    "stability_minutes": 0, "co2_enabled": True, "co2_threshold_ppm": 1000.0,
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

async def async_setup(hass, config):
    if any(entry.unique_id == "ventwise_test_lab" for entry in hass.config_entries.async_entries("ventwise")):
        return True
    entry = ConfigEntry(domain="ventwise", title="VentWise Test Lab", data=DATA, options={}, source="user", version=2, minor_version=1, unique_id="ventwise_test_lab", discovery_keys={}, subentries_data=None)
    await hass.config_entries.async_add(entry)
    return True
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
        configuration.write_text("default_config:\n\nhomeassistant:\n  name: VentWise Test Lab\n", encoding="utf-8")
    lines = (
        "input_number: !include ventwise_test_helpers.yaml", "input_boolean: !include ventwise_test_booleans.yaml",
        "input_select: !include ventwise_test_weather_condition.yaml", "template: !include ventwise_test_template.yaml",
        "lovelace: !include ventwise_test_dashboards.yaml", "ventwise_lab_bootstrap:",
    )
    text = configuration.read_text(encoding="utf-8")
    missing = [line for line in lines if line not in text]
    if missing:
        marker = f"{FIXTURES_MARKER}\n" if FIXTURES_MARKER not in text else ""
        configuration.write_text(f"{text.rstrip()}\n\n{marker}{'\n'.join(missing)}\n", encoding="utf-8")
    for name, content in {
        "ventwise_test_helpers.yaml": HELPERS_YAML, "ventwise_test_booleans.yaml": BOOLEANS_YAML,
        "ventwise_test_weather_condition.yaml": CONDITION_YAML, "ventwise_test_template.yaml": TEMPLATE_YAML,
        "ventwise_test_dashboards.yaml": DASHBOARD_CONFIG_YAML, "ventwise_test_dashboard.yaml": DASHBOARD_YAML,
    }.items():
        (config_dir / name).write_text(content, encoding="utf-8")
    bootstrap = config_dir / "custom_components" / "ventwise_lab_bootstrap"
    bootstrap.mkdir(parents=True, exist_ok=True)
    (bootstrap / "manifest.json").write_text(BOOTSTRAP_MANIFEST, encoding="utf-8")
    (bootstrap / "__init__.py").write_text(BOOTSTRAP_INIT, encoding="utf-8")
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
