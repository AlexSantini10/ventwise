"""Version helper for VentWise."""

from __future__ import annotations

import json
from pathlib import Path


def _read_manifest_version() -> str:
    manifest_path = Path(__file__).resolve().parents[2] / "custom_components" / "ventwise" / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))["version"]


VERSION = _read_manifest_version()
