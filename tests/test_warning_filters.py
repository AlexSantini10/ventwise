"""Regression tests for intentional third-party warning filters."""

from __future__ import annotations

import warnings


def test_known_aiohttp_deprecation_warning_is_ignored() -> None:
    """Keep the Home Assistant import warning scoped to its upstream source."""
    warnings.warn_explicit(
        "Inheritance class HomeAssistantApplication from web.Application is discouraged",
        DeprecationWarning,
        filename="aiohttp/web_app.py",
        lineno=169,
        module="aiohttp.web_app",
    )
