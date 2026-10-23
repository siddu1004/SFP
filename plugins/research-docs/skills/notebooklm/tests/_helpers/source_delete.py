"""Exercise the production batch-delete owner with fake terminal deletes."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from types import SimpleNamespace

from notebooklm._client_metrics import ClientMetrics
from notebooklm._runtime.call_supervisor import CallSupervisor
from notebooklm._sources import SourcesAPI
from notebooklm.types import SourceDeleteOutcome


async def delete_with_outcomes(
    notebook_id: str,
    source_ids: Sequence[str],
    *,
    delete: Callable[[str, str], Awaitable[None]],
) -> list[SourceDeleteOutcome]:
    supervisor = CallSupervisor(metrics=ClientMetrics(), max_concurrent_rpcs=16)
    supervisor.prepare_generation(1)
    supervisor.start_accepting(1)
    owner = SimpleNamespace(
        _operation_scope=supervisor.operation_scope,
        _spawn_child=supervisor.spawn_child,
        delete=delete,
    )
    return await SourcesAPI.delete_many_with_outcomes(owner, notebook_id, source_ids)
