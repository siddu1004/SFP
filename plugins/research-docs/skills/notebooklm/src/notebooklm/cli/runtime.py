"""CLI runtime primitives.

Windows event loop (#75, #79, #2485): CLI commands run on asyncio's default
event loop, which on Windows is ``ProactorEventLoop``, the same loop
``notebooklm-mcp``, ``notebooklm-server`` and the Python API use.
``NOTEBOOKLM_WINDOWS_EVENT_LOOP=selector`` opts a Windows CLI process into
``SelectorEventLoop`` instead, for environments where the Proactor loop hangs
(the one report so far came from a Sandboxie-Plus box, #75).
``NOTEBOOKLM_WINDOWS_EVENT_LOOP=proactor`` forces the Proactor loop even if
something in the process installed a different event-loop policy.

On Python 3.11+ the choice is passed to ``asyncio.Runner`` as a loop factory
and the global event-loop policy is never touched, so Playwright's sync API,
which builds its own loop from that policy, keeps the Proactor loop it needs to
start the browser driver (#89). Python 3.10 has no loop factory, so there the
opt-in sets the policy (which 3.10 does not deprecate) for the duration of each
run and then restores it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..exceptions import ConfigurationError

if TYPE_CHECKING:
    import click

logger = logging.getLogger(__name__)

WINDOWS_EVENT_LOOP_ENV = "NOTEBOOKLM_WINDOWS_EVENT_LOOP"
WINDOWS_EVENT_LOOP_CHOICES = ("proactor", "selector")

_NESTED_LOOP_MESSAGE = (
    "Cannot run sync CLI command from within an existing event loop. "
    "Use the async API (``async with NotebookLMClient(...)``) directly "
    "instead of invoking the sync CLI helper from async code."
)


def is_quiet(ctx: click.Context | None = None) -> bool:
    """Return True iff the active CLI invocation was started with ``--quiet``.

    The root group declared in ``notebooklm_cli.py`` owns the canonical
    ``--quiet`` flag. Every subcommand context that descends from it sees
    the flag on ``ctx.find_root().params["quiet"]``, which is what this
    helper reads.

    Resolution rules:

    * If ``ctx`` is provided, walk to its root and read ``params["quiet"]``.
    * If ``ctx`` is ``None``, fall back to ``click.get_current_context(
      silent=True)`` so call sites that don't already carry a context
      reference still inherit the root flag.
    * If there is no active Click context at all (e.g., a library import
      path or a standalone unit test), return False. Library importers
      must never see surprise output suppression.

    The helper is intentionally defensive: a malformed ``params`` mapping,
    a missing key, or a non-bool value all degrade to ``False`` rather than
    raising. CLI-side suppression is a quality-of-life knob; an exception
    here would convert a misconfiguration into a hard failure of every
    command, which would be far worse than printing one extra status line.
    """
    if ctx is None:
        import click

        ctx = click.get_current_context(silent=True)
        if ctx is None:
            return False
    try:
        root_params = ctx.find_root().params
    except (AttributeError, RuntimeError):
        return False
    value = root_params.get("quiet", False)
    return value if isinstance(value, bool) else False


def windows_event_loop_choice() -> str | None:
    """Return the event loop requested for Windows, or None for asyncio's default.

    Always None off Windows, where the variable has no effect. An unrecognised
    value raises ``ConfigurationError`` so a typo fails loudly instead of
    silently running on the default loop.
    """
    if sys.platform != "win32":
        return None
    value = os.environ.get(WINDOWS_EVENT_LOOP_ENV, "").strip().lower()
    if not value:
        return None
    if value not in WINDOWS_EVENT_LOOP_CHOICES:
        raise ConfigurationError(
            f"Unknown {WINDOWS_EVENT_LOOP_ENV}={value!r}; "
            f"expected one of {list(WINDOWS_EVENT_LOOP_CHOICES)} or unset."
        )
    return value


def _windows_loop_factory(choice: str) -> Callable[[], asyncio.AbstractEventLoop]:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop if choice == "proactor" else asyncio.SelectorEventLoop
    raise RuntimeError("Windows event loops are only available on Windows")


def _windows_loop_policy(choice: str) -> asyncio.AbstractEventLoopPolicy:
    if sys.platform == "win32":
        if choice == "proactor":
            return asyncio.WindowsProactorEventLoopPolicy()
        return asyncio.WindowsSelectorEventLoopPolicy()
    raise RuntimeError("Windows event loop policies are only available on Windows")


def _run_with_windows_loop(coro, choice: str):
    logger.debug("Running CLI command on the %s event loop (%s)", choice, WINDOWS_EVENT_LOOP_ENV)
    runner_cls = getattr(asyncio, "Runner", None)
    try:
        if runner_cls is not None:
            with runner_cls(loop_factory=_windows_loop_factory(choice)) as runner:
                return runner.run(coro)
        # Python 3.10: set the policy for this run only, so code that runs
        # afterwards (e.g. Playwright's own loop) gets the default again.
        original_policy = asyncio.get_event_loop_policy()
        asyncio.set_event_loop_policy(_windows_loop_policy(choice))
        try:
            return asyncio.run(coro)
        finally:
            asyncio.set_event_loop_policy(original_policy)
    except BaseException:
        # If the loop itself could not be created, the coroutine never started;
        # close it so the real error is not followed by "never awaited". This
        # is a no-op for a coroutine that ran.
        close = getattr(coro, "close", None)
        if close is not None:
            close()
        raise


def run_async(coro):
    """Run async coroutine in sync context.

    Guards against being called from inside an already-running event loop.
    ``asyncio.run`` raises ``RuntimeError`` in that case ("asyncio.run() cannot
    be called from a running event loop"); we re-raise with a CLI-shaped
    message and explicitly close the coroutine first so the caller does not
    see a ``RuntimeWarning: coroutine '...' was never awaited``.

    Nested event loops are intentionally not supported (no ``nest_asyncio``,
    no ``loop.run_until_complete`` fallback): the CLI assumes a single
    top-level ``asyncio.run`` invariant.

    On Windows, ``NOTEBOOKLM_WINDOWS_EVENT_LOOP`` can pick the event loop (see
    the module docstring); otherwise asyncio's default is used.
    """
    try:
        choice = windows_event_loop_choice()
    except ConfigurationError:
        coro.close()
        raise
    if choice is not None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _run_with_windows_loop(coro, choice)
        # Check before creating the loop: a Runner entered inside a running
        # loop fails again while shutting down and hides the original error.
        coro.close()
        raise RuntimeError(_NESTED_LOOP_MESSAGE)
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        # Distinguish "loop already running" from other RuntimeErrors (e.g.,
        # programmer errors inside the coroutine that surface as RuntimeError).
        # Only the running-loop case requires us to close the coroutine -- in
        # every other case ``asyncio.run`` has already driven it to completion
        # or cancellation, and calling ``close()`` would be a no-op at best
        # (and could mask a still-pending state at worst).
        if "running event loop" not in str(exc):
            raise
        coro.close()
        raise RuntimeError(_NESTED_LOOP_MESSAGE) from exc
