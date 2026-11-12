"""Shared error classification and safe diagnostic metadata."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCategory(StrEnum):
    """Categories used by both configuration and runtime diagnostics."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DELIVERY = "delivery"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True, slots=True)
class ErrorDiagnostic:
    """Safe, user-facing error metadata; never contains exception text."""

    category: ErrorCategory
    message: str
    operation: str
    reference: str


def error_reference(operation: str, exception: BaseException | None = None) -> str:
    """Return a stable short reference without exposing sensitive values."""

    value = f"{operation}:{type(exception).__name__ if exception else 'error'}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def log_unexpected(
    logger: logging.Logger,
    exception: BaseException,
    *,
    operation: str,
    context: str,
) -> str:
    """Log an unexpected error with traceback and return its safe reference."""

    reference = error_reference(operation, exception)
    logger.exception(
        "VentWise unexpected error reference=%s domain=ventwise operation=%s context=%s",
        reference,
        operation,
        context,
    )
    return reference


def handled_error(category: ErrorCategory, message: str, operation: str) -> ErrorDiagnostic:
    """Build a diagnostic for an expected, non-exceptional condition."""

    return ErrorDiagnostic(category, message, operation, error_reference(operation))


def error_context(**values: Any) -> str:
    """Return only stable identifiers for log context."""

    return ",".join(f"{key}={str(value)[:80]}" for key, value in values.items())
