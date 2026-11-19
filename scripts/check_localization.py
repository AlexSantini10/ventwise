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

    for locale, catalog in sorted(catalogs.items()):
        if locale == "en":
            continue
        for key in sorted(set(english) - set(catalog)):
            issues.append(Issue(locale, "missing", key, "missing from locale"))
        for key in sorted(set(catalog) - set(english)):
            issues.append(Issue(locale, "extra", key, "not present in English catalog"))
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
        lines.append(f"- {location} [{issue.category}] {issue.detail}")
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
    return 1 if issues and (args.strict or not args.report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
