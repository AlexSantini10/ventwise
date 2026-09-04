"""Regression tests for intentional third-party warning filters."""

from __future__ import annotations

import warnings


def test_known_home_assistant_deprecation_warning_is_ignored() -> None:
    """Keep the known Home Assistant import warning scoped to its message."""
    warnings.warn_explicit(
        "Inheritance class HomeAssistantApplication from web.Application is discouraged",
        DeprecationWarning,
        filename="aiohttp/web_app.py",
        lineno=169,
        module="abc",
    )
