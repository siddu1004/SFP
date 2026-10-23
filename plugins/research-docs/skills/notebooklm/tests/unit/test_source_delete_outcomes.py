"""Real namespace cleanup with supervised children and fake mutation terminals."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from notebooklm import NotebookLMClient, OperationTimeoutError, RPCError
from notebooklm._app.source_clean import SourceCleanPreview, execute_source_clean
from notebooklm._client_metrics import ClientMetrics
from notebooklm._idempotency import attach_operation_metadata
from notebooklm._runtime.call_supervisor import CallSupervisor
from notebooklm._runtime.operation_context import (
    adopt_operation_journal_entry,
    current_operation_context,
)
from notebooklm._sources import SourcesAPI
from notebooklm.outcomes import CommitState, OperationMetadata, ReconciliationReport

pytestmark = pytest.mark.asyncio


def _client(delete, timeout=None):
    supervisor = CallSupervisor(
        metrics=ClientMetrics(), max_concurrent_rpcs=16, operation_timeout=timeout
    )
    supervisor.prepare_generation(1)
    supervisor.start_accepting(1)
    owner = SimpleNamespace(
        _operation_scope=supervisor.operation_scope,
        _spawn_child=supervisor.spawn_child,
        delete=delete,
    )

    async def bulk(notebook_id, ids):
        return await SourcesAPI.delete_many_with_outcomes(owner, notebook_id, ids)

    client = object.__new__(NotebookLMClient)
    client._collaborators = SimpleNamespace(call_supervisor=supervisor)
    client.sources = SimpleNamespace(delete_many_with_outcomes=bulk)
    return client, supervisor


def _preview(count):
    return SourceCleanPreview(
        "nb", False, tuple((str(i), "", "error", "error_status") for i in range(count))
    )


async def test_cleanup_children_share_journal_and_preserve_occurrence_order():
    contexts = []

    async def delete(nb, sid):
        contexts.append(current_operation_context(supervisor))

    client, supervisor = _client(delete)
    async with client.operation():
        parent = current_operation_context(supervisor)
        results = await client.sources.delete_many_with_outcomes("nb", ["a", "a", "b"])
    assert [item.source_id for item in results] == ["a", "a", "b"]
    assert [item.outcome.member for item in results] == [0, 1, 2]
    assert all(item.outcome.commit_state is CommitState.CONFIRMED for item in results)
    assert all(context.journal is parent.journal for context in contexts)
    assert all(context.owner_task is not parent.owner_task for context in contexts)
    await supervisor.wait_for_idle(1, 0)


async def test_cleanup_preserves_confirmed_unknown_and_rejected_evidence():
    async def delete(nb, sid):
        if sid == "0":
            return
        state = CommitState.UNKNOWN if sid == "1" else CommitState.REJECTED
        error = RPCError("safe failure")
        attach_operation_metadata(
            error,
            OperationMetadata(
                commit_state=state,
                reconciliation=ReconciliationReport(unresolved_inputs=(sid,), reason="uncertain")
                if state is CommitState.UNKNOWN
                else None,
            ),
        )
        raise error

    client, supervisor = _client(delete)
    result = await execute_source_clean(_preview(3), client=client)
    assert result.deleted_count == 1
    assert [item.outcome.commit_state for item in result.outcomes] == [
        CommitState.CONFIRMED,
        CommitState.UNKNOWN,
        CommitState.REJECTED,
    ]
    assert result.outcomes[1].outcome.reconciliation.unresolved_inputs == ("1",)
    await supervisor.wait_for_idle(1, 0)


async def test_cleanup_pacing_and_concurrency_remain_bounded():
    active = peak = 0
    release = asyncio.Event()
    started = asyncio.Event()

    async def delete(nb, sid):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 10:
            started.set()
        await release.wait()
        active -= 1

    client, supervisor = _client(delete)
    # Patch only the between-batch delay; no terminal or admission policy is mocked.
    sleep = AsyncMock()
    with patch.object(asyncio, "sleep", sleep):
        action = asyncio.create_task(execute_source_clean(_preview(12), client=client))
        await started.wait()
        assert peak == 10
        release.set()
        result = await action
    assert result.deleted_count == 12
    sleep.assert_awaited_once_with(0.5)
    await supervisor.wait_for_idle(1, 0)


async def test_cancel_settles_children_and_keeps_unattempted_tail():
    first_done = asyncio.Event()
    paused = asyncio.Event()
    settled = []

    async def delete(nb, sid):
        if sid == "0":
            first_done.set()
            return
        try:
            paused.set()
            await asyncio.Event().wait()
        finally:
            settled.append(sid)

    client, supervisor = _client(delete)
    escaped = []

    async def run_cleanup():
        try:
            await execute_source_clean(_preview(12), client=client)
        except asyncio.CancelledError as error:
            # Python 3.10 Task await wraps cancellation and keeps the original
            # exception in __context__. Capture the API's own escaping carrier.
            escaped.append(error)
            raise

    action = asyncio.create_task(run_cleanup())
    await first_done.wait()
    await paused.wait()
    # Admission can be cancelled while the batch owner is still scheduling children.
    action.cancel()
    with pytest.raises(asyncio.CancelledError) as caught:
        await action
    assert escaped
    assert caught.value is escaped[0] or caught.value.__context__ is escaped[0]
    metadata = escaped[0]._operation_metadata
    items = metadata.batch_outcome.items
    assert len(items) == 12
    assert items[0].commit_state is CommitState.CONFIRMED
    assert items[-1].commit_state is CommitState.NOT_SENT
    assert any(item.commit_state is CommitState.UNKNOWN for item in items)
    assert settled
    await supervisor.wait_for_idle(1, 0)


@pytest.mark.parametrize("with_journal", [False, True])
async def test_cleanup_timeout_keeps_confirmed_sibling_evidence(with_journal, monkeypatch):
    loop = asyncio.get_running_loop()
    now = loop.time()
    expiry = now + 0.02
    monkeypatch.setattr(loop, "time", lambda: now)
    first_done = asyncio.Event()

    async def delete(nb, sid):
        nonlocal now
        entry = (
            adopt_operation_journal_entry(
                supervisor, method="DeleteSources", operation="sources.delete"
            )
            if with_journal
            else None
        )
        if entry is not None:
            entry.mark_dispatched()
        if sid == "0":
            if entry is not None:
                entry.record(CommitState.CONFIRMED, "server accepted deletion")
            first_done.set()
            return
        await first_done.wait()
        # Expire only after a sibling has confirmed, so the test always reaches
        # the evidence-preservation path even under Windows scheduling jitter.
        now = expiry
        await asyncio.Event().wait()

    client, supervisor = _client(delete, timeout=0.01)
    with pytest.raises(OperationTimeoutError) as caught:
        await execute_source_clean(_preview(12), client=client)
    assert (
        caught.value.operation_metadata.batch_outcome.items[0].commit_state is CommitState.CONFIRMED
    )
    assert (
        caught.value.operation_metadata.batch_outcome.items[-1].commit_state is CommitState.NOT_SENT
    )
    await supervisor.wait_for_idle(1, 0)
