"""Bootstrap and validate the dedicated authenticated Chrome profile for the Docker Lab."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_URL = "http://localhost:8123"
PROFILE_NAME = "VentWise-HA-Headless-Chrome"


def chrome_executable() -> str:
    candidates = (
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    )
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Google Chrome was not found")


def profile_directory() -> Path:
    configured = os.environ.get("VENTWISE_HEADLESS_PROFILE")
    if configured:
        return Path(configured).expanduser()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / PROFILE_NAME
    return Path.home() / ".ventwise" / PROFILE_NAME


def chrome_args(*, url: str, profile: Path, headless: bool) -> list[str]:
    args = [
        chrome_executable(),
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        url,
    ]
    if headless:
        args[1:1] = ["--headless=new", "--disable-gpu", "--dump-dom"]
    return args


def is_authenticated_dom(dom: str) -> bool:
    """Return true only when the HA authorization component is absent."""

    authorization_markers = ("<ha-authorize", "/frontend_latest/authorize.", "/auth/authorize")
    return (
        "<home-assistant" in dom
        and not any(marker in dom for marker in authorization_markers)
    )


def bootstrap(url: str, profile: Path) -> int:
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(chrome_args(url=url, profile=profile, headless=False))
    print(f"Chrome opened with the dedicated Lab profile: {profile}")
    print("Complete the Home Assistant login manually, then close that Chrome window.")
    print("Run this command afterwards to verify the authenticated headless session:")
    print("  python scripts/ha-headless-browser.py check")
    return 0


def check(url: str, profile: Path) -> int:
    if not profile.exists():
        print(
            f"Headless Chrome profile does not exist: {profile}. Run bootstrap first.",
            file=sys.stderr,
        )
        return 2
    result = subprocess.run(
        chrome_args(url=url, profile=profile, headless=True),
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if result.returncode != 0:
        print("Chrome headless failed to load the Docker Lab.", file=sys.stderr)
        return result.returncode or 1
    if not is_authenticated_dom(result.stdout):
        print(
            "Docker Lab is not authenticated in the dedicated headless profile. "
            "Run bootstrap and log in manually.",
            file=sys.stderr,
        )
        return 3
    print(f"Authenticated headless Chrome session verified: {url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bootstrap", "check"), default="check", nargs="?")
    parser.add_argument("--url", default=os.environ.get("VENTWISE_TEST_LAB_URL", DEFAULT_URL))
    parser.add_argument("--profile", type=Path, default=profile_directory())
    args = parser.parse_args()
    if args.action == "bootstrap":
        return bootstrap(args.url, args.profile)
    return check(args.url, args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
