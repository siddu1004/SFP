"""Stdlib-source oracle for the #2485 selector-transport write bug.

Shared by ``tests/unit/test_windows_asyncio.py`` and
``tests/unit/test_windows_compatibility.py``; it lives outside both so neither
test module imports the other (``test_no_cross_test_imports``).
"""

from __future__ import annotations

import inspect
import re
from asyncio import selector_events

import pytest


def stdlib_has_write_send_bug() -> bool:
    """Read the stdlib source to tell whether ``_write_send`` has the bug.

    This is an oracle independent of the bytecode gate: the fixed method puts
    the whole chunk back (``appendleft(buffer)``); the buggy one only puts back
    a partial remainder. Version numbers are not enough (3.15 alphas before a8
    still have the bug).
    """
    try:
        source = inspect.getsource(selector_events)
    except (OSError, TypeError):
        pytest.skip("asyncio source is not available")
    match = re.search(r"\n    def _write_send\(self\):\n(.*?)\n    def ", source, re.DOTALL)
    if match is None:
        return False  # 3.10/3.11: no _write_send
    return "self._buffer.appendleft(buffer)\n" not in match.group(1)
