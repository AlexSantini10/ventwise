"""Derive the VentWise Home Assistant UI contract from real flow schemas."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UIContract:
    """The identifiers that a flow may expose to Home Assistant."""

    steps: frozenset[str]
    fields: frozenset[str]
    selector_options: frozenset[str]
    menu_options: frozenset[str]
    placeholders: frozenset[str]


def schema_field_ids(schema: Any) -> frozenset[str]:
    """Return field IDs from a voluptuous schema without depending on HA internals."""

    return frozenset(
        str(getattr(key, "schema", key))
        for key in getattr(schema, "schema", {})
    )


def selector_option_ids(schema: Any, field_id: str | None = None) -> frozenset[str]:
    """Return static selector option IDs exposed by a schema."""

    options: set[str] = set()
    for key, value in getattr(schema, "schema", {}).items():
        if field_id is not None and str(getattr(key, "schema", key)) != field_id:
            continue
        config = getattr(value, "config", None)
        if isinstance(config, Mapping):
            for option in config.get("options", ()):
                if isinstance(option, str):
                    options.add(option)
                elif isinstance(option, Mapping) and isinstance(option.get("value"), str):
                    options.add(option["value"])
    return frozenset(options)


def build_contract(
    schemas: Mapping[str, Any],
    menus: Mapping[str, Iterable[str]],
    placeholders: Iterable[str] = (),
) -> UIContract:
    """Build a stable contract from representative flow scenarios."""

    fields = {field for schema in schemas.values() for field in schema_field_ids(schema)}
    options = {option for schema in schemas.values() for option in selector_option_ids(schema)}
    return UIContract(
        steps=frozenset(schemas),
        fields=frozenset(fields),
        selector_options=frozenset(options),
        menu_options=frozenset(option for values in menus.values() for option in values),
        placeholders=frozenset(placeholders),
    )
