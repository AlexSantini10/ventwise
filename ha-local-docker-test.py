#!/usr/bin/env python3
"""Run a local Home Assistant Docker sandbox for VentWise."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_IMAGE = "ghcr.io/home-assistant/home-assistant:stable"
DEFAULT_CONTAINER_NAME = "ventwise-ha-test"
DEFAULT_PORT = 8123
TEST_FIXTURES_MARKER = "# VentWise test fixtures"
TEST_HELPERS_FILE = "ventwise_test_helpers.yaml"
TEST_WEATHER_CONDITION_FILE = "ventwise_test_weather_condition.yaml"
TEST_WEATHER_FILE = "ventwise_test_weather.yaml"

TEST_HELPERS_YAML = """ventwise_test_bedroom_temperature:
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

TEST_WEATHER_YAML = """- weather:
    - name: VentWise Test Weather
      unique_id: ventwise_test_weather
      condition: "{{ states('input_select.ventwise_test_weather_condition') }}"
      temperature: "{{ states('input_number.ventwise_test_outdoor_temperature') | float(23) }}"
      temperature_unit: "°C"
      humidity: "{{ states('input_number.ventwise_test_outdoor_humidity') | float(45) }}"
      wind_speed: "{{ states('input_number.ventwise_test_wind_speed') | float(2) }}"
      wind_speed_unit: "m/s"
"""

TEST_WEATHER_CONDITION_YAML = """ventwise_test_weather_condition:
  name: VentWise Test Weather Condition
  options:
    - sunny
    - rainy
    - thunderstorm
  initial: sunny
  icon: mdi:weather-partly-cloudy
"""


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def default_config_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "VentWise-HA-Test"
    return Path.home() / ".ventwise-ha-test"


def ensure_docker() -> None:
    if shutil.which("docker") is None:
        raise SystemExit("Docker is not installed or not available on PATH.")


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def docker_output(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def ensure_config(config_root: Path) -> Path:
    config_dir = config_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "configuration.yaml"
    if not config_file.exists():
        config_file.write_text(
            "default_config:\n\nhomeassistant:\n  name: VentWise Test\n",
            encoding="utf-8",
        )

    ensure_test_fixtures(config_dir, config_file)

    return config_dir


def ensure_test_fixtures(config_dir: Path, config_file: Path) -> None:
    """Provision repeatable test helpers and a local weather entity."""

    config_text = config_file.read_text(encoding="utf-8")
    fixture_lines = (
        f"input_number: !include {TEST_HELPERS_FILE}",
        f"input_select: !include {TEST_WEATHER_CONDITION_FILE}",
        f"template: !include {TEST_WEATHER_FILE}",
    )
    missing_lines = [line for line in fixture_lines if line not in config_text]
    if missing_lines:
        marker = f"{TEST_FIXTURES_MARKER}\n" if TEST_FIXTURES_MARKER not in config_text else ""
        config_file.write_text(
            f"{config_text.rstrip()}\n\n{marker}{'\n'.join(missing_lines)}\n",
            encoding="utf-8",
        )
    (config_dir / TEST_HELPERS_FILE).write_text(TEST_HELPERS_YAML, encoding="utf-8")
    (config_dir / TEST_WEATHER_CONDITION_FILE).write_text(
        TEST_WEATHER_CONDITION_YAML,
        encoding="utf-8",
    )
    (config_dir / TEST_WEATHER_FILE).write_text(TEST_WEATHER_YAML, encoding="utf-8")


def integration_source() -> Path:
    source = repo_root() / "custom_components" / "ventwise"
    if not source.exists():
        raise SystemExit(f"Integration folder not found: {source}")
    return source


def container_exists(name: str) -> bool:
    output = docker_output(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^/{name}$",
            "--format",
            "{{.Names}}",
        ]
    )
    return bool(output)


def stop_container(name: str) -> None:
    if container_exists(name):
        run(["docker", "rm", "-f", name])


def start_container(
    *,
    name: str,
    image: str,
    config_dir: Path,
    integration_dir: Path,
    port: int,
    timezone: str,
) -> None:
    stop_container(name)

    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--restart",
            "unless-stopped",
            "-p",
            f"{port}:8123",
            "-e",
            f"TZ={timezone}",
            "-v",
            f"{str(config_dir)}:/config",
            "-v",
            f"{str(integration_dir)}:/config/custom_components/ventwise:ro",
            image,
        ]
    )

    print(f"Home Assistant is starting at http://localhost:{port}")
    print(f"Runtime config: {config_dir}")
    print(f"Local integration: {integration_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ha-local-docker-test.py",
        description="Run a local Home Assistant Docker sandbox for VentWise.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("up", "down", "logs", "restart"),
        default="up",
        help="Container action to run.",
    )
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="Home Assistant image.")
    parser.add_argument(
        "--container-name",
        default=DEFAULT_CONTAINER_NAME,
        help="Docker container name.",
    )
    parser.add_argument(
        "--config-root",
        type=Path,
        default=default_config_root(),
        help="External runtime directory for Home Assistant.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Host port.")
    parser.add_argument("--timezone", default="Europe/Rome", help="Container timezone.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_docker()

    config_dir = ensure_config(args.config_root)
    integration_dir = integration_source()

    if args.action in {"up", "restart"}:
        start_container(
            name=args.container_name,
            image=args.image,
            config_dir=config_dir,
            integration_dir=integration_dir,
            port=args.port,
            timezone=args.timezone,
        )
        return 0

    if args.action == "down":
        stop_container(args.container_name)
        return 0

    if args.action == "logs":
        run(["docker", "logs", "-f", args.container_name])
        return 0

    raise SystemExit(f"Unsupported action: {args.action}")


if __name__ == "__main__":
    raise SystemExit(main())
