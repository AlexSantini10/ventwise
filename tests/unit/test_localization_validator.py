"""Tests for the machine-readable localization quality gate."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.check_localization as localization
from scripts.check_localization import validate


def _write_catalog(directory: Path, locale: str, values: dict[str, object]) -> None:
    (directory / f"{locale}.json").write_text(
        json.dumps(values, ensure_ascii=False), encoding="utf-8"
    )


def test_validator_reports_missing_copied_and_placeholder_errors(tmp_path: Path) -> None:
    _write_catalog(
        tmp_path,
        "en",
        {
            "title": "VentWise",
            "config": {
                "message": "Open {count} windows",
                "description": "Choose a room",
            },
        },
    )
    _write_catalog(
        tmp_path,
        "it",
        {"title": "VentWise", "config": {"message": "Open windows"}},
    )

    issues = validate(tmp_path)
    found = {(issue.category, issue.key) for issue in issues}

    assert ("missing", "config.description") in found
    assert ("placeholder_mismatch", "config.message") in found
    assert ("copied_from_english", "config.message") not in found
    assert ("missing", "title") not in found


def test_validator_reports_values_copied_from_english(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "en", {"title": "VentWise", "label": "Open windows"})
    _write_catalog(tmp_path, "de", {"title": "VentWise", "label": "Open windows"})

    issues = validate(tmp_path)

    assert any(
        issue.locale == "de"
        and issue.category == "copied_from_english"
        and issue.key == "label"
        for issue in issues
    )


def test_validator_reports_invalid_encoding_markers(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "en", {"label": "Perceived temperature"})
    _write_catalog(tmp_path, "fr", {"label": "Température Ã l'extérieur"})

    issues = validate(tmp_path)

    assert any(issue.category == "invalid_encoding" for issue in issues)


def test_validator_reports_missing_required_locale_file(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "en", {"label": "Label"})

    issues = validate(tmp_path)

    assert any(
        issue.locale == "it" and issue.category == "missing_locale"
        for issue in issues
    )


def test_validator_reports_incomplete_runtime_locale_map(
    tmp_path: Path, monkeypatch
) -> None:
    for locale in ("en", "it", "es", "fr", "de", "ru", "zh-Hans"):
        _write_catalog(tmp_path, locale, {"label": locale})
    source = tmp_path / "notification.py"
    source.write_text(
        "TEXTS = {'en': 'English', 'it': 'Italian'}\n", encoding="utf-8"
    )
    monkeypatch.setattr(localization, "NOTIFICATION_SOURCE", source)

    issues = validate(tmp_path)

    assert any(issue.category == "runtime_missing_locale" for issue in issues)
