"""Cleanup keeps arbitrary candidate counts under real supervised admission."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from notebooklm import NotebookLMClient, OperationTimeoutError, RPCError
from notebooklm._app.source_clean import SourceCleanPreview, execute_source_clean
from notebooklm._client_metrics import ClientMetrics
from notebooklm._idempotency import (
    OperationJournal,
    attach_operation_journal,
    attach_operation_metadata,
)
from notebooklm._runtime.call_supervisor import CallSupervisor
from notebooklm._runtime.operation_context import adopt_operation_journal_entry
from notebooklm._source.delete_batch import _attach_settlement
from notebooklm._sources import SourcesAPI
from notebooklm.outcomes import (
    BatchItemOutcome,
    BatchOutcome,
    CommitState,
    OperationMetadata,
    ReconciliationReport,
    RecoveryAction,
    operation_metadata_payload,
)
from notebooklm.types import SourceDeleteOutcome

pytestmark = pytest.mark.asyncio


def _cleanup(delete, count, *, timeout=None):
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
    preview = SourceCleanPreview(
        "nb", False, tuple((str(i), "", "error", "error_status") for i in range(count))
    )
    return client, supervisor, preview


@pytest.mark.parametrize("count", [21, 45])
async def test_large_cleanup_preserves_results_concurrency_and_pacing(monkeypatch, count):
    active = peak = 0
    calls = []
    pauses = []
    original_sleep = asyncio.sleep

    async def delete(notebook_id, source_id):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        calls.append((notebook_id, source_id))
        await original_sleep(0)
        active -= 1
        if source_id == "20":
            raise RPCError("deletion was not confirmed")

    async def sleep(delay):
        pauses.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    client, supervisor, preview = _cleanup(delete, count)
    result = await execute_source_clean(preview, client=client)
    assert calls == [("nb", str(i)) for i in range(count)]
    assert len(result.outcomes) == count
    assert [item.outcome.member for item in result.outcomes] == list(range(count))
    assert result.deleted_count == count - 1
    assert result.failure_count == 1
    assert result.outcomes[20].outcome.commit_state is CommitState.UNKNOWN
    assert all(
        item.outcome.commit_state is CommitState.CONFIRMED
        for item in result.outcomes
        if item.source_id != "20"
    )
    assert peak <= 10
    assert pauses == [0.5] * ((count - 1) // 10)
    await supervisor.wait_for_idle(1, 0)


async def test_large_cleanup_cancellation_keeps_full_tail_and_bounded_projection(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()
    cleanup_started = asyncio.Event()
    settled = []
    captured = []
    original_sleep = asyncio.sleep

    async def delete(notebook_id, source_id):
        if int(source_id) < 20:
            return
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            cleanup_started.set()
            await release.wait()
            settled.append(source_id)

    async def sleep(delay):
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    client, supervisor, preview = _cleanup(delete, 45)

    async def action():
        try:
            await execute_source_clean(preview, client=client)
        except asyncio.CancelledError as error:
            # Observe the original carrier before Python 3.10 Task delivery
            # wraps it in a fresh cancellation with this error as __context__.
            captured.append(error)
            raise

    task = asyncio.create_task(action())
    await entered.wait()
    task.cancel()
    await cleanup_started.wait()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    metadata = captured[0]._operation_metadata
    items = metadata.source_delete_outcomes
    assert len(items) == 45
    assert [item.member for item in items] == list(range(45))
    assert all(item.commit_state is CommitState.CONFIRMED for item in items[:20])
    assert items[20].commit_state is CommitState.UNKNOWN
    assert items[-1].commit_state is CommitState.NOT_SENT
    assert metadata.commit_state is CommitState.UNKNOWN
    assert metadata.recovery_action is RecoveryAction.INSPECT_AND_RECONCILE
    assert settled
    payload = operation_metadata_payload(captured[0])
    assert payload["batch_outcome"]["total_items"] == 45
    assert payload["batch_outcome"]["omitted_items"] == 25
    assert len(payload["batch_outcome"]["items"]) == 20
    await supervisor.wait_for_idle(1, 0)


@pytest.mark.parametrize("last_state", [CommitState.UNKNOWN, CommitState.REJECTED])
async def test_full_settlement_accounts_for_failure_after_projection_prefix(last_state):
    items = [
        SourceDeleteOutcome(str(i), BatchItemOutcome(i, str(i), CommitState.NOT_SENT))
        for i in range(20)
    ]
    items.append(
        SourceDeleteOutcome(
            "last",
            BatchItemOutcome(
                20,
                "last",
                last_state,
                reconciliation=ReconciliationReport(unresolved_inputs=("last",))
                if last_state is CommitState.UNKNOWN
                else None,
            ),
        )
    )
    journal = OperationJournal("cleanup")
    entry = journal.new_entry(method="DeleteSources")
    entry.batch_outcome = BatchOutcome((items[0].outcome,))
    error = RPCError("cleanup interrupted")
    attach_operation_metadata(error, journal.snapshot(primary=entry))
    _attach_settlement(error, items)
    attach_operation_journal(error, journal)
    assert error.operation_metadata.commit_state is last_state
    assert error.operation_metadata.source_delete_outcomes[-1].commit_state is last_state
    assert error.operation_metadata.batch_outcome is None
    payload = operation_metadata_payload(error)
    assert len(payload["batch_outcome"]["items"]) == 20
    assert payload["batch_outcome"]["total_items"] == 21
    assert payload["batch_outcome"]["omitted_items"] == 1
    # An absence of confirmed/unknown members is not an owner replay grant.
    assert payload["batch_outcome"]["whole_request_retriable"] is False


async def test_confirmed_cleanup_cannot_erase_earlier_unknown_evidence():
    error = RPCError("earlier mutation was not confirmed")
    attach_operation_metadata(error, OperationMetadata(commit_state=CommitState.UNKNOWN))
    results = [
        SourceDeleteOutcome(
            str(i), BatchItemOutcome(i, str(i), CommitState.CONFIRMED, resource_id=str(i))
        )
        for i in range(25)
    ]
    _attach_settlement(error, results)
    assert error.operation_metadata.commit_state is CommitState.UNKNOWN
    assert error.operation_metadata.recovery_action is RecoveryAction.INSPECT_AND_RECONCILE
    assert len(error.operation_metadata.source_delete_outcomes) == 25


async def test_large_cleanup_does_not_widen_canonical_batch_outcome():
    with pytest.raises(ValueError, match="capped at 20"):
        BatchOutcome(tuple(BatchItemOutcome(i, str(i), CommitState.NOT_SENT) for i in range(21)))


async def test_large_cleanup_deadline_preserves_complete_journal_bearing_settlement(monkeypatch):
    original_sleep = asyncio.sleep
    loop = asyncio.get_running_loop()
    now = loop.time()
    monkeypatch.setattr(loop, "time", lambda: now)

    async def sleep(delay):
        await original_sleep(0)

    async def delete(notebook_id, source_id):
        nonlocal now
        entry = adopt_operation_journal_entry(
            supervisor, method="DeleteSources", operation="sources.delete"
        )
        assert entry is not None
        entry.mark_dispatched()
        if int(source_id) < 20:
            entry.record(CommitState.CONFIRMED, "server accepted deletion")
            return
        # Expire the real operation timer only after evidence reaches beyond
        # the diagnostic prefix, independent of worker scheduling latency.
        now += 2
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "sleep", sleep)
    client, supervisor, preview = _cleanup(delete, 45, timeout=1)
    with pytest.raises(OperationTimeoutError) as caught:
        await execute_source_clean(preview, client=client)
    metadata = caught.value.operation_metadata
    assert len(metadata.source_delete_outcomes) == 45
    assert len(metadata.entries) >= 21
    assert all(
        item.commit_state is CommitState.CONFIRMED for item in metadata.source_delete_outcomes[:20]
    )
    assert metadata.source_delete_outcomes[20].commit_state is CommitState.UNKNOWN
    assert metadata.source_delete_outcomes[-1].commit_state is CommitState.NOT_SENT
    assert metadata.commit_state is CommitState.UNKNOWN
    assert metadata.recovery_action is RecoveryAction.INSPECT_AND_RECONCILE
    assert operation_metadata_payload(caught.value)["batch_outcome"]["total_items"] == 45
    await supervisor.wait_for_idle(1, 0)
