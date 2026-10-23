"""Global safety gate for the test-only synthetic-error environment."""

from __future__ import annotations

import logging
import os

from .config import CORE_LOGGER_NAME

logger = logging.getLogger(CORE_LOGGER_NAME)

ERROR_INJECT_ENV_VAR = "NOTEBOOKLM_VCR_RECORD_ERRORS"


def _get_error_injection_mode() -> str | None:
    """Return a normalized supported synthetic-error mode, if configured."""

    raw = os.environ.get(ERROR_INJECT_ENV_VAR, "").strip()
    if not raw:
        return None
    normalized = raw.casefold()
    return normalized if normalized in {"429", "5xx", "expired_csrf"} else None


def _refuse_synthetic_error_outside_test_context() -> None:
    """Reject leaked test-only configuration outside a pytest context."""

    mode = _get_error_injection_mode()
    if mode is None or os.environ.get("PYTEST_CURRENT_TEST"):
        return
    message = (
        f"{ERROR_INJECT_ENV_VAR}={mode!r} is set but no pytest context was "
        f"detected (PYTEST_CURRENT_TEST unset). This env var is test-only — "
        f"it substitutes synthetic error responses for every batchexecute "
        f"RPC and must not be set in production. Unset {ERROR_INJECT_ENV_VAR} "
        f"to restore normal behavior, or run under pytest if synthetic-error "
        f"recording is intended."
    )
    logger.warning(message)
    raise RuntimeError(message)


__all__ = [
    "ERROR_INJECT_ENV_VAR",
    "_get_error_injection_mode",
    "_refuse_synthetic_error_outside_test_context",
]
