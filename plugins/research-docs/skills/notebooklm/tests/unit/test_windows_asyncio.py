"""Tests for the selector-transport write fix the Windows CLI installs (#2485).

CPython 3.12-3.14 drop a chunk when ``send()`` raises ``BlockingIOError`` inside
``_SelectorSocketTransport._write_send``. Windows always uses that method; the
transport tests below force it on every OS and inject the error with a socket
proxy, so the bug and the fix reproduce without a Windows machine.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import types
from asyncio import selector_events
from typing import Any

import pytest

from notebooklm import _windows_asyncio
from tests._helpers.windows_asyncio import stdlib_has_write_send_bug

CHUNK = 64 * 1024
N_CHUNKS = 32
TOTAL = CHUNK * N_CHUNKS

# The method's body differs before 3.12 (bytearray buffer) and from 3.15 on
# (byte accounting), so transport tests only run where the bug exists.
transport_versions = pytest.mark.skipif(
    not ((3, 12) <= sys.version_info[:2] < (3, 15)),
    reason="exercises the deque-based _write_send of CPython 3.12-3.14",
)


# Verbatim CPython 3.12-3.14 ``_write_send``, kept as the bug's control. It is
# compiled from text because pytest's assertion rewriting would otherwise change
# its bytecode, which the gate inspects.
_BUGGY_WRITE_SEND_SOURCE = """
def _write_send(self):
    assert self._buffer, 'Data should not be empty'
    if self._conn_lost:
        return
    try:
        buffer = self._buffer.popleft()
        n = self._sock.send(buffer)
        if n != len(buffer):
            # Not all data was written
            self._buffer.appendleft(buffer[n:])
    except (BlockingIOError, InterruptedError):
        pass
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException as exc:
        self._loop._remove_writer(self._sock_fd)
        self._buffer.clear()
        self._fatal_error(exc, 'Fatal write error on socket transport')
        if self._empty_waiter is not None:
            self._empty_waiter.set_exception(exc)
    else:
        self._maybe_resume_protocol()  # May append to buffer.
        if not self._buffer:
            self._loop._remove_writer(self._sock_fd)
            if self._empty_waiter is not None:
                self._empty_waiter.set_result(None)
            if self._closing:
                self._call_connection_lost(None)
            elif self._eof:
                self._sock.shutdown(socket.SHUT_WR)
"""
_namespace: dict[str, Any] = {"socket": socket}
exec(compile(_BUGGY_WRITE_SEND_SOURCE, "<cpython-3.14 _write_send>", "exec"), _namespace)
_buggy_write_send = _namespace["_write_send"]


class _FlakySocket:
    """Socket proxy whose every Nth ``send()`` raises ``BlockingIOError``.

    It also caps each send at 16 KiB, so every 64 KiB write leaves data in the
    transport buffer and the writer callback (``_write_send``) has to run.
    """

    def __init__(self, sock: socket.socket, every: int = 7) -> None:
        self._sock = sock
        self._every = every
        self.calls = 0

    def send(self, data: Any) -> int:
        self.calls += 1
        if self._every and self.calls % self._every == 0:
            raise BlockingIOError
        return self._sock.send(data[:16384])

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sock, name)


def _run_transfer(
    write_send: Any,
    *,
    use_writelines: bool = False,
    flaky: bool = True,
    timeout: float = 5.0,
) -> tuple[int, int]:
    """Send TOTAL bytes over loopback with ``write_send`` as the writer callback.

    Returns ``(bytes received, "Data should not be empty" errors)``.
    """
    loop = asyncio.SelectorEventLoop()
    assertion_errors = 0

    def handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        nonlocal assertion_errors
        if isinstance(context.get("exception"), AssertionError):
            assertion_errors += 1
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handler)

    async def main() -> int:
        received = 0
        done = asyncio.Event()

        async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            nonlocal received
            while data := await reader.read(1 << 20):
                received += len(data)
            done.set()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        _, writer = await asyncio.open_connection("127.0.0.1", port)
        transport: Any = writer.transport
        transport._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8192)
        transport._write_ready = types.MethodType(write_send, transport)
        if flaky:
            transport._sock = _FlakySocket(transport._sock)

        async def send_all() -> None:
            if use_writelines:
                writer.writelines([b"x" * CHUNK for _ in range(N_CHUNKS)])
                await writer.drain()
            else:
                for _ in range(N_CHUNKS):
                    writer.write(b"x" * CHUNK)
                    await writer.drain()
            writer.close()
            await done.wait()
            await writer.wait_closed()

        try:
            await asyncio.wait_for(send_all(), timeout)
        except asyncio.TimeoutError:
            # The buggy method can stall drain() (a dropped chunk empties the
            # buffer while the protocol is paused) or never finish the close.
            # It also leaves its writer registered on an empty buffer, which
            # abort() does not unregister; Windows select() then fails on the
            # closed socket, so unregister it first.
            asyncio.get_running_loop()._remove_writer(transport._sock_fd)  # type: ignore[attr-defined]
            transport.abort()
        # With the buggy method the server handler never sees EOF; cancel it.
        pending = asyncio.all_tasks() - {asyncio.current_task()}
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        server.close()
        await server.wait_closed()
        return received

    try:
        received = loop.run_until_complete(main())
    finally:
        loop.close()
    return received, assertion_errors


class TestBugDetection:
    def test_gate_matches_running_interpreter(self) -> None:
        current = selector_events._SelectorSocketTransport.__dict__.get("_write_send")
        expected = stdlib_has_write_send_bug()
        if getattr(current, _windows_asyncio._MARKER, False):
            # Already installed in this process (a selector-loop CLI run on Windows).
            assert expected
        else:
            assert _windows_asyncio._is_buggy_write_send(current) is expected

    def test_gate_accepts_the_buggy_method(self) -> None:
        assert _windows_asyncio._is_buggy_write_send(_buggy_write_send) is True

    def test_gate_rejects_the_fixed_method(self) -> None:
        assert _windows_asyncio._is_buggy_write_send(_windows_asyncio._write_send) is False

    def test_gate_rejects_missing_or_non_function(self) -> None:
        assert _windows_asyncio._is_buggy_write_send(None) is False
        assert _windows_asyncio._is_buggy_write_send(object()) is False

    def test_gate_rejects_method_touching_unknown_names(self) -> None:
        def changed(self: Any) -> None:
            buffer = self._buffer.popleft()
            self._buffer.appendleft(buffer)
            self._new_bookkeeping = 0

        assert _windows_asyncio._is_buggy_write_send(changed) is False


class TestInstall:
    @pytest.fixture
    def transport_cls(self, monkeypatch: pytest.MonkeyPatch) -> type:
        cls = type("FakeTransport", (), {"_write_send": _buggy_write_send})
        monkeypatch.setattr(selector_events, "_SelectorSocketTransport", cls)
        return cls

    def test_installs_on_buggy_method(self, transport_cls: type) -> None:
        assert _windows_asyncio.install_selector_write_fix() is True
        assert transport_cls.__dict__["_write_send"] is _windows_asyncio._write_send

    def test_install_is_idempotent(self, transport_cls: type) -> None:
        assert _windows_asyncio.install_selector_write_fix() is True
        assert _windows_asyncio.install_selector_write_fix() is True
        assert transport_cls.__dict__["_write_send"] is _windows_asyncio._write_send

    def test_leaves_unrecognized_method_alone(self, transport_cls: type) -> None:
        def other(self: Any) -> None:
            pass

        transport_cls._write_send = other  # type: ignore[attr-defined]
        assert _windows_asyncio.install_selector_write_fix() is False
        assert transport_cls.__dict__["_write_send"] is other

    def test_failed_inspection_leaves_method_alone(
        self, transport_cls: type, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(fn: Any) -> bool:
            raise RuntimeError("bytecode changed")

        monkeypatch.setattr(_windows_asyncio, "_is_buggy_write_send", boom)
        assert _windows_asyncio.install_selector_write_fix() is False
        assert transport_cls.__dict__["_write_send"] is _buggy_write_send

    def test_missing_transport_class(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delattr(selector_events, "_SelectorSocketTransport")
        assert _windows_asyncio.install_selector_write_fix() is False


@transport_versions
@pytest.mark.timeout(30)
class TestTransport:
    def test_buggy_method_loses_data(self) -> None:
        """Control: the injected BlockingIOError reproduces the #2485 data loss."""
        received, assertion_errors = _run_transfer(_buggy_write_send, timeout=1.0)
        assert received < TOTAL
        assert assertion_errors > 0

    @pytest.mark.parametrize("use_writelines", [False, True], ids=["write", "writelines"])
    def test_fixed_method_delivers_every_byte(self, use_writelines: bool) -> None:
        received, assertion_errors = _run_transfer(
            _windows_asyncio._write_send, use_writelines=use_writelines
        )
        assert received == TOTAL
        assert assertion_errors == 0

    def test_close_while_writing_reports_connection_lost_once(self) -> None:
        loop = asyncio.SelectorEventLoop()

        class Client(asyncio.Protocol):
            def __init__(self) -> None:
                self.lost = 0
                self.closed = loop.create_future()

            def connection_lost(self, exc: BaseException | None) -> None:
                self.lost += 1
                if not self.closed.done():
                    self.closed.set_result(None)

        async def main() -> tuple[int, int]:
            received = 0
            done = asyncio.Event()

            async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                nonlocal received
                while data := await reader.read(1 << 20):
                    received += len(data)
                done.set()
                writer.close()

            server = await asyncio.start_server(handle, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            transport: Any
            transport, protocol = await loop.create_connection(Client, "127.0.0.1", port)
            transport._write_ready = types.MethodType(_windows_asyncio._write_send, transport)
            transport._sock = _FlakySocket(transport._sock)
            transport.write(b"x" * TOTAL)
            transport.close()  # buffer still holds data: the writer must flush, then close
            await asyncio.wait_for(protocol.closed, 10)
            # gh-156512 guard: the flush-then-close path marks the connection
            # lost, so a later abort() is a no-op. Without the guard it reaches
            # _force_close() and raises AttributeError on the cleared _loop.
            transport.abort()
            await asyncio.wait_for(done.wait(), 10)
            await asyncio.sleep(0)
            server.close()
            await server.wait_closed()
            return protocol.lost, received

        try:
            lost, received = loop.run_until_complete(main())
        finally:
            loop.close()
        assert lost == 1
        assert received == TOTAL


@transport_versions
@pytest.mark.skipif(sys.platform != "win32", reason="real Winsock send path")
@pytest.mark.timeout(60)
def test_fixed_method_on_real_winsock() -> None:
    """Large transfer through the selector loop on Windows, with no injected errors."""
    received, assertion_errors = _run_transfer(_windows_asyncio._write_send, flaky=False)
    assert received == TOTAL
    assert assertion_errors == 0
