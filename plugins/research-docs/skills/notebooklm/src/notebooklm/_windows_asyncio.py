"""Backport of CPython's selector-transport write fix for the Windows CLI (#2485).

On CPython 3.12-3.14, ``asyncio.selector_events._SelectorSocketTransport._write_send``
pops a chunk off the write buffer before calling ``send()``. If ``send()`` then
raises ``BlockingIOError``, the chunk is discarded. The writer callback stays
registered, so once the buffer is empty every loop tick fails with
``AssertionError: Data should not be empty`` while the peer waits for bytes that
never arrive. Windows always takes this path (it has no ``socket.sendmsg``), and
Winsock can report ``WSAEWOULDBLOCK`` after ``select()`` reported the socket as
writable. A Windows CLI run with ``NOTEBOOKLM_WINDOWS_EVENT_LOOP=selector``
(the opt-in for sandboxes where the Proactor loop hangs, #79) uses this
transport, so multi-megabyte uploads lose data.

CPython fixed this on main (3.15) in gh-146507 without a backport. This module
installs that fix on interpreters that still carry the bug. The replacement is
the 3.14-branch method with the one-line fix from main. A bytecode check
identifies the buggy method, so the patch does nothing on 3.10/3.11 (older
write path), on 3.15+ (already fixed), or on any build that changes the method.

Only the CLI's root command group installs this, and only when
``NOTEBOOKLM_WINDOWS_EVENT_LOOP=selector`` selects the selector loop. The
default Proactor loop does not use this transport, and the library itself never
patches asyncio. Shell completion does not run that callback, so its notebook
lookups stay unpatched; they are small requests that never fill a send buffer.

Remove this module once the CLI drops the selector opt-in, or once the minimum
supported Python ships the fix.
"""

from __future__ import annotations

import dis
import logging
import socket
from asyncio import selector_events
from typing import Any

logger = logging.getLogger(__name__)

_MARKER = "_notebooklm_backport_2485"


def _write_send(self: Any) -> None:
    """CPython 3.14-branch ``_write_send`` plus the gh-146507 BlockingIOError fix."""
    assert self._buffer, "Data should not be empty"
    if self._conn_lost:
        return
    try:
        buffer = self._buffer.popleft()
        n = self._sock.send(buffer)
        if n != len(buffer):
            # Not all data was written
            self._buffer.appendleft(buffer[n:])
    except (BlockingIOError, InterruptedError):
        # The fix: put the chunk back instead of dropping it.
        self._buffer.appendleft(buffer)
        return
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException as exc:
        self._loop._remove_writer(self._sock_fd)
        self._buffer.clear()
        self._fatal_error(exc, "Fatal write error on socket transport")
        if self._empty_waiter is not None:
            self._empty_waiter.set_exception(exc)
    else:
        self._maybe_resume_protocol()  # May append to buffer.
        if not self._buffer:
            self._loop._remove_writer(self._sock_fd)
            if self._empty_waiter is not None:
                self._empty_waiter.set_result(None)
            # gh-156512: don't let _call_connection_lost be called twice
            if self._closing and not self._conn_lost:
                self._conn_lost += 1
                self._call_connection_lost(None)
            elif self._eof:
                self._sock.shutdown(socket.SHUT_WR)


setattr(_write_send, _MARKER, True)


def _is_buggy_write_send(fn: Any) -> bool:
    """Return True only for the unfixed CPython 3.12-3.14 ``_write_send``.

    The buggy method calls ``appendleft`` once (partial send); the fixed one
    calls it twice. The replacement must also reference every name the original
    does, so a build that changed the method in other ways is left alone.
    """
    code = getattr(fn, "__code__", None)
    if code is None:
        return False
    appendleft_calls = sum(
        1 for instruction in dis.get_instructions(code) if instruction.argval == "appendleft"
    )
    if appendleft_calls != 1:
        return False
    return set(code.co_names) <= set(_write_send.__code__.co_names)


def install_selector_write_fix() -> bool:
    """Patch the selector transport if this interpreter has the #2485 bug.

    Returns True when the fix is in place (installed now or earlier) and False
    when the interpreter does not need it or the check could not run.
    """
    transport_cls = getattr(selector_events, "_SelectorSocketTransport", None)
    current = getattr(transport_cls, "_write_send", None)
    if transport_cls is None or current is None:
        return False
    if getattr(current, _MARKER, False):
        return True
    try:
        buggy = _is_buggy_write_send(current)
    except Exception:  # noqa: BLE001 - a failed check must never break CLI startup
        logger.debug("Could not inspect asyncio _write_send; leaving it unpatched", exc_info=True)
        return False
    if not buggy:
        logger.debug("asyncio _write_send does not match the #2485 bug; leaving it unpatched")
        return False
    transport_cls._write_send = _write_send
    logger.debug("Installed the #2485 fix for asyncio's selector transport")
    return True
