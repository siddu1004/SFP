"""Small import leaf for infrastructure shared by the MCP and REST adapters.

This module is intentionally outside :mod:`notebooklm._app`: the exported
values support transport hosting rather than transport-neutral business logic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from ._loop_bound import LoopBoundPrimitive
from ._redact import redact
from ._runtime.config import DEFAULT_SERVER_KEEPALIVE_INTERVAL
from ._runtime.operation_context import detached_operation_context
from ._serving import (
    LOOPBACK_HOSTNAMES,
    addr_is_loopback,
    check_bind_allowed,
    host_header_is_loopback,
    is_loopback,
)


class _CallSupervisor(Protocol):
    """The minimal runtime capability detached adapter work needs."""

    def active_epoch(self) -> int | None: ...

    def operation_scope(
        self,
        label: str,
        *,
        timeout: float | None,
        expected_epoch: int,
        _absolute_deadline: float | None,
    ) -> AbstractAsyncContextManager[object]: ...


class _ClientRuntime(Protocol):
    @property
    def call_supervisor(self) -> _CallSupervisor: ...


class AdapterRuntimeClient(Protocol):
    """Narrow adapter crossing for epoch-qualified detached client work."""

    @property
    def _collaborators(self) -> _ClientRuntime: ...

    def operation(self, timeout: float | None = None) -> AbstractAsyncContextManager[object]: ...


def client_generation_epoch(client: AdapterRuntimeClient) -> int:
    """Read the active client epoch through the adapter-support boundary."""

    epoch = client._collaborators.call_supervisor.active_epoch()
    if epoch is None:
        raise RuntimeError("Client not initialized. Use 'async with' context.")
    return epoch


@asynccontextmanager
async def _client_operation(
    client: AdapterRuntimeClient,
    timeout: float | None,
    *,
    expected_epoch: int,
    absolute_deadline: float | None = None,
) -> AsyncIterator[object]:
    """Create a fresh server-owned client operation for detached adapter work."""

    async with client._collaborators.call_supervisor.operation_scope(
        "detached adapter operation",
        timeout=timeout,
        expected_epoch=expected_epoch,
        _absolute_deadline=absolute_deadline,
    ) as lease:
        yield lease


def _detached_adapter_context():
    """Clear request-owned operation/replay state in a detached adapter task."""

    return detached_operation_context()


__all__ = [
    "DEFAULT_SERVER_KEEPALIVE_INTERVAL",
    "AdapterRuntimeClient",
    "LOOPBACK_HOSTNAMES",
    "LoopBoundPrimitive",
    "addr_is_loopback",
    "check_bind_allowed",
    "client_generation_epoch",
    "host_header_is_loopback",
    "is_loopback",
    "redact",
]
