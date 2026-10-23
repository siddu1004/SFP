"""Synthetic HTTP error injection for VCR cassette playback (test-only).

When ``NOTEBOOKLM_VCR_RECORD_ERRORS`` is set to ``429`` / ``5xx`` /
``expired_csrf`` AND
:class:`notebooklm._web.transport.middleware.error_injection.ErrorInjectionMiddleware`
has been constructed with an injected ``builder`` callable (canonical:
``tests/cassette_patterns.py:build_synthetic_error_response``), the
middleware short-circuits each chain invocation with the synthetic
response so the client's exception-mapping branches (429 →
``RateLimitError``, 5xx → ``ServerError``, 400-CSRF → ``AuthError``) fire
end-to-end.

**The env var is a no-op without an injected builder.** Production code
(``MiddlewareChainBuilder`` in ``_web/transport/middleware/chain.py``) instantiates
``ErrorInjectionMiddleware()`` with no builder argument, so a leaked
``NOTEBOOKLM_VCR_RECORD_ERRORS`` env var on a user install cannot trigger
any synthetic substitution — the middleware passes through. Tests that
exercise the substitution path construct the middleware directly with an
explicit ``builder=`` argument (issue #1005).

**Production behavior is also unchanged when the env var is unset.** The
middleware delegates straight to ``next_call``; the ``Kernel.post`` chain
terminal runs exactly as it would without the middleware in the chain.

``ErrorInjectionMiddleware`` substitutes responses at the chain level
(ABOVE VCR), so recording synthetic errors into cassettes is not supported
— replay-only is the documented contract: the synthetic-error cassettes in
``tests/cassettes/`` are hand-written from the canonical shapes in
``tests/cassette_patterns.py``.

Public surface kept:

- :func:`_get_error_injection_mode` — env-var → mode normalization.
- :func:`_refuse_synthetic_error_outside_test_context` — client
  construction (``NotebookLMClient.__init__``) calls this so a leaked
  deploy env raises ``RuntimeError`` instead of silently activating the
  chain middleware. The guard fires only when ``PYTEST_CURRENT_TEST`` is
  unset (pytest sets it for every test).
- :data:`ERROR_INJECT_ENV_VAR` — env-var name (canonical string).
"""

from __future__ import annotations

__all__ = [
    "ERROR_INJECT_ENV_VAR",
    "_get_error_injection_mode",
    "_refuse_synthetic_error_outside_test_context",
]

from ..._runtime.error_injection import (
    ERROR_INJECT_ENV_VAR,
    _get_error_injection_mode,
    _refuse_synthetic_error_outside_test_context,
)
