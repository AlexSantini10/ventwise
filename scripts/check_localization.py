"""Validate VentWise user-facing translation catalogs.

The English catalog is the schema source of truth.  Other locales may rely on
Home Assistant's runtime English fallback, but that fallback is reported here
and fails strict validation so missing work cannot reach a release unnoticed.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS_DIR = ROOT / "custom_components" / "ventwise" / "translations"
SOURCE_CATALOG = ROOT / "custom_components" / "ventwise" / "strings.json"
NOTIFICATION_CATALOG = ROOT / "custom_components" / "ventwise" / "translations" / "notifications"
NOTIFICATION_SOURCE = ROOT / "custom_components" / "ventwise" / "application" / "notification.py"
REQUIRED_LOCALES = ("en", "it", "es", "fr", "de", "ru", "zh-Hans")
RUNTIME_LOCALE_KEYS = {locale.lower() for locale in REQUIRED_LOCALES}
DEFAULT_ALLOWLIST = {"title"}
MOJIBAKE_MARKERS = ("Ã", "Â", "Ð", "Ñ", "â€", "�")
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")


@dataclass(frozen=True)
class Issue:
    locale: str
    category: str
    key: str
    detail: str
    warning: bool = False


def _load(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    result: dict[str, Any] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        result.update(_flatten(child, path))
    return result


def _placeholders(value: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(value))


def _validate_catalog_shape(
    source: dict[str, Any], english: dict[str, Any], issues: list[Issue]
) -> None:
    """Ensure the Home Assistant source catalog declares the English UI shape."""

    source_flat = _flatten(source)
    english_flat = _flatten(english)
    source_flat.pop("title", None)
    english_flat.pop("title", None)
    for key in sorted(set(english_flat) - set(source_flat)):
        issues.append(Issue("en", "missing_ui_key", key, "missing from strings.json"))
    for key in sorted(set(source_flat) - set(english_flat)):
        issues.append(Issue("source", "obsolete_catalog_key", key, "not present in translations/en.json", True))
    source_options = {
        key.removeprefix("selector.")
        for key in source_flat
        if key.startswith("selector.") and ".options." in key
    }
    english_options = {
        key.removeprefix("selector.")
        for key in english_flat
        if key.startswith("selector.") and ".options." in key
    }
    for key in sorted(english_options - source_options):
        issues.append(Issue("en", "missing_selector_option", f"selector.{key}", "selector option is not declared in strings.json"))


def _validate_notification_catalog(issues: list[Issue]) -> None:
    """Validate the standalone runtime notification catalog."""

    paths = sorted(NOTIFICATION_CATALOG.glob("*.json")) if NOTIFICATION_CATALOG.is_dir() else []
    if not paths:
        issues.append(Issue("runtime", "missing_catalog", "translations/notifications", "catalog directory is missing or empty"))
        return
    catalog: dict[str, dict[str, Any]] = {}
    for path in paths:
        try:
            catalog[path.stem.lower()] = _load(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
            issues.append(Issue(path.stem, "invalid_catalog", str(path), str(error)))
    expected = {locale.lower(): locale for locale in REQUIRED_LOCALES}
    found = {locale.lower() for locale in catalog}
    for locale in sorted(set(expected) - found):
        issues.append(Issue(expected[locale], "missing_locale", "notifications", "runtime locale is missing"))
    english = catalog.get("en")
    if not isinstance(english, dict):
        issues.append(Issue("runtime", "invalid_catalog", "notifications.en", "English runtime catalog is missing"))
        return
    english_flat = _flatten(english)
    for locale, values in catalog.items():
        if locale.lower() == "en":
            continue
        if not isinstance(values, dict):
            issues.append(Issue(locale, "invalid_catalog", "notifications", "locale must be an object"))
            continue
        localized = _flatten(values)
        for key in sorted(set(english_flat) - set(localized)):
            issues.append(Issue(locale, "missing_ui_key", f"notifications.{key}", "missing from runtime locale"))
        for key in sorted(set(localized) - set(english_flat)):
            issues.append(Issue(locale, "obsolete_catalog_key", f"notifications.{key}", "not present in English runtime catalog", True))
        for key in sorted(set(english_flat) & set(localized)):
            source_value = english_flat[key]
            localized_value = localized[key]
            if isinstance(source_value, str) and isinstance(localized_value, str):
                if _placeholders(source_value) != _placeholders(localized_value):
                    issues.append(Issue(locale, "placeholder_mismatch", f"notifications.{key}", "runtime placeholders differ"))
                if len(localized_value.strip()) > 1 and localized_value == source_value:
                    issues.append(Issue(locale, "copied_from_english", f"notifications.{key}", localized_value))
                if any(marker in localized_value for marker in MOJIBAKE_MARKERS):
                    issues.append(Issue(locale, "invalid_encoding", f"notifications.{key}", "contains mojibake"))


def scan_inline_ui_text(paths: tuple[Path, ...]) -> list[Issue]:
    """Find likely user-facing literals in the integration flow modules."""

    issues: list[Issue] = []
    allowed = {"", "en", "room", "macro_room", "add_room", "edit_room", "remove_room", "finish"}
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as error:
            issues.append(Issue("source", "inline_ui_text", str(path), str(error)))
            continue
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            function_name = getattr(call.func, "attr", "")
            if function_name not in {"async_show_form", "async_show_menu"}:
                continue
            for keyword in call.keywords:
                if keyword.arg not in {"title", "description", "menu_options"}:
                    continue
                values = list(ast.walk(keyword.value))
                for value_node in values:
                    if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
                        continue
                    value = value_node.value.strip()
                    if len(value) < 3 or value in allowed or value.startswith("notify."):
                        continue
                    if any(char in value for char in " .!?…") and not value.startswith("http"):
                        issues.append(Issue("source", "inline_ui_text", f"{path.name}:{value_node.lineno}", value))
    return issues


def validate(
    translations_dir: Path = TRANSLATIONS_DIR,
    *,
    allowlist: set[str] | None = None,
) -> list[Issue]:
    allowlist = DEFAULT_ALLOWLIST if allowlist is None else allowlist
    paths = sorted(translations_dir.glob("*.json"))
    issues: list[Issue] = []
    if not paths:
        return [Issue("en", "catalog", "", "no translation files found")]

    catalogs: dict[str, dict[str, Any]] = {}
    found_locales = {path.stem for path in paths}
    for locale in REQUIRED_LOCALES:
        if locale not in found_locales:
            issues.append(Issue(locale, "missing_locale", "", "translation file is missing"))
    for path in paths:
        locale = path.stem
        try:
            catalogs[locale] = _flatten(_load(path))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
            issues.append(Issue(locale, "invalid_catalog", "", str(error)))

    english = catalogs.get("en")
    if english is None:
        issues.append(Issue("en", "catalog", "", "missing English source catalog"))
        return issues

    try:
        source_catalog = _load(SOURCE_CATALOG)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        issues.append(Issue("source", "invalid_catalog", "strings.json", str(error)))
    else:
        _validate_catalog_shape(source_catalog, catalogs["en"], issues)

    for locale, catalog in sorted(catalogs.items()):
        if locale == "en":
            continue
        for key in sorted(set(english) - set(catalog)):
            issues.append(Issue(locale, "missing_ui_key", key, "missing from locale"))
        for key in sorted(set(catalog) - set(english)):
            issues.append(Issue(locale, "obsolete_catalog_key", key, "not present in English catalog", True))
        for key in sorted(set(english) & set(catalog)):
            source = english[key]
            localized = catalog[key]
            if not isinstance(source, str) or not isinstance(localized, str):
                continue
            if key not in allowlist and len(localized.strip()) > 1 and localized == source:
                issues.append(Issue(locale, "copied_from_english", key, localized))
            if _placeholders(source) != _placeholders(localized):
                issues.append(
                    Issue(
                        locale,
                        "placeholder_mismatch",
                        key,
                        f"expected {sorted(_placeholders(source))}, got {sorted(_placeholders(localized))}",
                    )
                )
            for marker in MOJIBAKE_MARKERS:
                if marker in localized:
                    issues.append(Issue(locale, "invalid_encoding", key, f"contains {marker!r}"))
                    break

    _validate_notification_catalog(issues)
    issues.extend(
        scan_inline_ui_text(
            (
                ROOT / "custom_components" / "ventwise" / "config_flow.py",
                ROOT / "custom_components" / "ventwise" / "configuration" / "flow.py",
                ROOT / "custom_components" / "ventwise" / "configuration" / "options_flow.py",
            )
        )
    )

    if NOTIFICATION_SOURCE.exists():
        try:
            tree = ast.parse(NOTIFICATION_SOURCE.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as error:
            issues.append(Issue("runtime", "invalid_catalog", "notification.py", str(error)))
        else:
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for marker in MOJIBAKE_MARKERS:
                        if marker in node.value:
                            issues.append(
                                Issue(
                                    "runtime",
                                    "invalid_encoding",
                                    f"notification.py:{node.lineno}",
                                    f"contains {marker!r}",
                                )
                            )
                            break
                if not isinstance(node, ast.Dict):
                    continue
                keys = {
                    key.value.lower()
                    for key in node.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
                if "en" not in keys or len(keys & RUNTIME_LOCALE_KEYS) < 2:
                    continue
                for locale in REQUIRED_LOCALES:
                    if locale.lower() not in keys:
                        issues.append(
                            Issue(
                                locale,
                                "runtime_missing_locale",
                                f"notification.py:{node.lineno}",
                                "runtime localization map is incomplete",
                            )
                        )

    return issues


def _report(issues: list[Issue]) -> str:
    if not issues:
        return "Localization check passed: all locale catalogs are aligned."
    lines = ["Localization issues found:"]
    for issue in issues:
        location = f"{issue.locale}:{issue.key}" if issue.key else issue.locale
        suffix = " warning" if issue.warning else ""
        lines.append(f"- {location} [{issue.category}{suffix}] {issue.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="print a human-readable report")
    parser.add_argument("--strict", action="store_true", help="return non-zero when issues exist")
    parser.add_argument("--json", action="store_true", dest="as_json", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    issues = validate()
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], ensure_ascii=False, indent=2))
    else:
        print(_report(issues))
    blocking = [issue for issue in issues if not issue.warning]
    return 1 if blocking and (args.strict or not args.report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
