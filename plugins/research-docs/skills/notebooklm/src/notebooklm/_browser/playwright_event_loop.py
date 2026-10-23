"""Keep Playwright off a caller's selector event-loop policy on Windows (#89).

Playwright's sync API builds its loop from the global event-loop policy and
needs ``ProactorEventLoop`` on Windows to start its driver subprocess. The CLI
no longer installs a policy (it passes a loop factory to ``asyncio.Runner``),
so the guard here only acts when something else did: a Python API caller that
set ``WindowsSelectorEventLoopPolicy``, or the CLI's selector opt-in on Python
3.10 (no loop factory), which holds that policy while a command runs, e.g.
during headless re-auth in a worker thread. ``browser_capture`` re-exports it.
"""

from __future__ import annotations

import asyncio
import sys
import warnings
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def windows_playwright_event_loop() -> Iterator[None]:
    """Swap out a selector event-loop policy on Windows while Playwright runs.

    Restores that policy on exit. Does nothing when another policy is in use,
    off Windows, and on Pythons without the policy API (3.16+).
    """
    if sys.platform != "win32":
        yield
        return

    original_policy = None
    swap = False
    # The policy API is deprecated from Python 3.14 and removed in 3.16.
    # ``catch_warnings`` swaps the process-wide filter list, so a thread warning
    # at the same instant could briefly see this "ignore"; that only hides a
    # DeprecationWarning, and only around these few calls.
    #
    # The swap and restore are process-wide too. With the CLI's 3.10 selector
    # opt-in, headless re-auth runs this in a worker thread while the command's
    # loop is live. That worker finishes before ``asyncio.run`` returns (it
    # waits for the default executor), so this restore always precedes the
    # CLI's own restore of the caller's policy.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        get_policy = getattr(asyncio, "get_event_loop_policy", None)
        selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if get_policy is not None and selector_policy is not None:
            original_policy = get_policy()
            swap = isinstance(original_policy, selector_policy)
        if swap:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    try:
        yield
    finally:
        if swap:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(original_policy)
