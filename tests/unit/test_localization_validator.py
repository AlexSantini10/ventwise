"""Tests for the machine-readable localization quality gate."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.check_localization as localization
from scripts.check_localization import validate


def _write_catalog(directory: Path, locale: str, values: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
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

    assert ("missing_ui_key", "config.description") in found
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


def test_validator_reports_notification_catalog_placeholder_errors(tmp_path, monkeypatch) -> None:
    for locale in ("en", "it", "es", "fr", "de", "ru", "zh-Hans"):
        _write_catalog(tmp_path / "translations", locale, {"label": locale})

    runtime_catalog = tmp_path / "notifications"
    runtime_catalog.mkdir()
    (runtime_catalog / "en.json").write_text(
        json.dumps({"message": "Open {count}", "extra": "Extra"}, ensure_ascii=False), encoding="utf-8"
    )
    (runtime_catalog / "it.json").write_text(
        json.dumps({"message": "Apri {number}"}, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(localization, "NOTIFICATION_CATALOG", runtime_catalog)
    monkeypatch.setattr(localization, "SOURCE_CATALOG", tmp_path / "missing-strings.json")

    issues = validate(tmp_path / "translations")

    assert any(issue.category == "missing_ui_key" for issue in issues)
    assert any(issue.category == "placeholder_mismatch" for issue in issues)
    assert any(issue.category == "missing_locale" and issue.locale == "es" for issue in issues)


def test_inline_ui_scanner_allows_translation_keys_and_flags_literal_labels(tmp_path: Path) -> None:
    flow = tmp_path / "flow.py"
    flow.write_text(
        "return self.async_show_form(step_id='user', title='Inline label')\n",
        encoding="utf-8",
    )

    issues = localization.scan_inline_ui_text((flow,))

    assert any(issue.category == "inline_ui_text" for issue in issues)
