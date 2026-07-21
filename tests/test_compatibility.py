"""Compatibility coverage for supported Home Assistant versions."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.ventwise.const import CONF_WIND_SPEED_ENTITY_ID
from custom_components.ventwise.flow import build_advanced_options_schema


def _selector_domains(selector) -> set[str]:
    """Normalize selector domains across Home Assistant versions."""

    domain = selector.config["domain"]
    if isinstance(domain, str):
        return {domain}
    return {str(item) for item in domain}


def test_advanced_options_schema_keeps_sensor_only_selectors_version_compatible() -> None:
    """The Home Assistant selector shape should stay compatible across releases."""

    schema = build_advanced_options_schema({})
    selector = schema.schema[CONF_WIND_SPEED_ENTITY_ID]

    assert _selector_domains(selector) == {"sensor"}
