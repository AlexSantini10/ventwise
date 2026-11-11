"""Translation lookup for runtime messages and entity labels."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_DIR = Path(__file__).parent / "translations" / "runtime"
_LANGUAGES = ("en", "it", "es", "fr", "de", "ru", "zh-hans")


@lru_cache(maxsize=len(_LANGUAGES))
def _load_catalog(language: str) -> dict[str, Any]:
    return json.loads((_CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))


def runtime_catalog(language: str | None) -> dict[str, Any]:
    """Return the catalog for a supported locale, falling back to English."""

    normalized = (language or "en").strip().lower().replace("_", "-")
    key = next(
        (item for item in _LANGUAGES if normalized == item or normalized.startswith(item + "-")),
        "en",
    )
    return _load_catalog(key)


def translate(language: str | None, *keys: str) -> str:
    """Return one runtime string from the selected catalog."""

    value = runtime_catalog(language)
    for key in keys:
        value = value[key]
    if not isinstance(value, str):
        raise TypeError(f"Translation path does not identify a string: {keys!r}")
    return value
