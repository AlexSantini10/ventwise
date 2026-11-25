"""Run authenticated Chrome headless smoke checks against the Docker Lab dashboard."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import websocket


DEFAULT_URL = os.environ.get("VENTWISE_TEST_LAB_URL", "http://localhost:8123")
DEFAULT_PROFILE = Path(
    os.environ.get(
        "VENTWISE_HEADLESS_PROFILE",
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        / "VentWise-HA-Headless-Chrome",
    )
)
CHROME_PATHS = (
    shutil.which("chrome"),
    shutil.which("chrome.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)
PRESETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "open": ("script.ventwise_test_open_recommendation", ("open", "ventilate")),
    "ventilate": ("script.ventwise_test_ventilate", ("ventilate",)),
    "close": ("script.ventwise_test_close_recommendation", ("close",)),
    "none": ("script.ventwise_test_marginal_benefit", ("none",)),
    "humidity": ("script.ventwise_test_humidity_exchange", ("open", "ventilate")),
    "co2": ("script.ventwise_test_co2", ("ventilate",)),
    "weather": ("script.ventwise_test_weather_block", ("none",)),
    "wind": ("script.ventwise_test_wind_block", ("none",)),
    "gust": ("script.ventwise_test_gust_block", ("none",)),
    "urgent-close": ("script.ventwise_test_urgent_close", ("close",)),
    "multi-room": ("script.ventwise_test_multi_room", ("open",)),
    "winter": ("script.ventwise_test_winter_symmetry", ("open",)),
    "co2-threshold": ("script.ventwise_test_co2_threshold", ("ventilate",)),
    "window-open": ("script.ventwise_test_window_already_open", ("none",)),
    "multiple-contacts": ("script.ventwise_test_multiple_windows", ("none",)),
}


def chrome_path() -> str:
    for candidate in CHROME_PATHS:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Google Chrome was not found")


class DevTools:
    def __init__(self, websocket_url: str) -> None:
        self.socket = websocket.create_connection(
            websocket_url,
            timeout=15,
            http_proxy_host=None,
            http_proxy_port=None,
        )
        self.message_id = 0

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.message_id += 1
        message_id = self.message_id
        self.socket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"CDP {method} failed: {message['error']}")
                return message

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        if "exceptionDetails" in result.get("result", {}):
            raise RuntimeError(f"Browser evaluation failed: {result['result']['exceptionDetails']}")
        return result.get("result", {}).get("result", {}).get("value")


def wait_for_target(port: int) -> dict[str, Any]:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as response:
                targets = json.load(response)
            pages = [target for target in targets if target.get("type") == "page"]
            if pages and pages[0].get("webSocketDebuggerUrl"):
                return pages[0]
        except (OSError, ValueError):
            time.sleep(0.25)
    raise TimeoutError("Chrome DevTools target did not become available")


def read_states(devtools: DevTools) -> dict[str, Any]:
    expression = """
    (() => {
      const homeAssistant = document.querySelector('home-assistant');
      const states = homeAssistant?.hass?.states
        ? Object.values(homeAssistant.hass.states)
        : [];
      if (!states.length) return {
        ok:false,
        status:'hass-state-cache-unavailable',
        has_home_assistant:!!homeAssistant,
        has_hass:!!homeAssistant?.hass,
        hass_keys:homeAssistant?.hass ? Object.keys(homeAssistant.hass).slice(0,20) : []
      };
      const wanted = new Set([
        'sensor.camera_test_recommendation',
        'sensor.living_room_recommendation',
        'sensor.core_engine_room_recommendation',
        'sensor.camera_test_reason',
        'sensor.living_room_reason',
        'input_number.ventwise_test_bedroom_temperature',
        'input_number.ventwise_test_outdoor_temperature',
        'input_boolean.ventwise_test_bedroom_window_left'
      ]);
      return {ok:true, states: states.filter((item) => wanted.has(item.entity_id) || item.entity_id.startsWith('sensor.camera_test_')).map((item) => ({
          entity_id:item.entity_id, state:item.state,
          attributes:{
            core_action:item.attributes.core_action,
            delivered_action:item.attributes.delivered_action,
            reason_code:item.attributes.reason_code,
            core_result:item.attributes.core_result,
            recommendation:item.attributes.recommendation
          }
        }))
      };
    })()
    """
    result = devtools.evaluate(expression)
    if not result or not result.get("ok"):
        raise RuntimeError(f"Authenticated Home Assistant state API unavailable: {result}")
    return {item["entity_id"]: item for item in result["states"]}


def call_service(devtools: DevTools, domain: str, service: str, data: dict[str, str]) -> None:
    expression = f"""
    (async () => {{
      const homeAssistant = document.querySelector('home-assistant');
      if (!homeAssistant?.hass) return {{ok:false, reason:'hass-unavailable'}};
      await homeAssistant.hass.callService(
        {json.dumps(domain)}, {json.dumps(service)}, {json.dumps(data)}
      );
      return {{ok:true}};
    }})()
    """
    result = devtools.evaluate(expression)
    if not result or not result.get("ok"):
        raise RuntimeError(f"Authenticated Home Assistant service call failed: {result}")


def run(url: str, profile: Path, selected: list[str]) -> int:
    if not profile.exists():
        raise RuntimeError("Run ha-headless-browser.py bootstrap first")
    port = 9223
    process = subprocess.Popen(
        [
            chrome_path(),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-mode",
            "--disable-crash-reporter",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={profile}",
            f"--remote-debugging-port={port}",
            f"{url}/ventwise-test-lab/0",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        target = wait_for_target(port)
        devtools = DevTools(target["webSocketDebuggerUrl"])
        devtools.call("Page.enable")
        devtools.call("Runtime.enable")
        time.sleep(5)
        auth_state = devtools.evaluate("({url:location.href, authorization:!!document.querySelector('ha-authorize')})")
        if auth_state.get("authorization") or "/auth/" in auth_state.get("url", ""):
            raise RuntimeError("Headless Chrome is not authenticated; run the profile bootstrap")
        devtools.evaluate("location.href = '/ventwise-test-lab/0'")
        time.sleep(5)
        results = []
        for key in selected:
            script_entity, expected_actions = PRESETS[key]
            call_service(devtools, "script", "turn_on", {"entity_id": script_entity})
            time.sleep(5)
            call_service(
                devtools,
                "button",
                "press",
                {"entity_id": "button.ventwise_test_lab_request_recommendation"},
            )
            time.sleep(8)
            states = read_states(devtools)
            bedroom = states.get("sensor.camera_test_core_recommendation", {})
            actual = bedroom.get("state")
            passed = actual in expected_actions
            results.append({
                "preset": key,
                "expected": "|".join(expected_actions),
                "actual": actual,
                "passed": passed,
                "delivery": states.get("sensor.camera_test_recommendation", {}).get("state"),
                "window_state": states.get("sensor.camera_test_window_state", {}).get("state"),
            })
            print(json.dumps(results[-1], ensure_ascii=False))
        return 0 if all(result["passed"] for result in results) else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--preset", action="append", choices=sorted(PRESETS))
    args = parser.parse_args()
    selected = args.preset or list(PRESETS)
    return run(args.url, args.profile, selected)


if __name__ == "__main__":
    raise SystemExit(main())
