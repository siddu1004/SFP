"""Studio batches share deadlines and preserve earlier mutation evidence."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from notebooklm import NotebookLMClient, OperationTimeoutError, RPCError
from notebooklm._client_metrics import ClientMetrics
from notebooklm._runtime.call_supervisor import CallSupervisor
from notebooklm._runtime.operation_context import adopt_operation_journal_entry
from notebooklm.outcomes import CommitState
from notebooklm.types import ArtifactListing, ArtifactType

pytest.importorskip("fastmcp")

from notebooklm.mcp.tools._studio_delete import delete_studio_items  # noqa: E402

NOTE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ART = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _client(timeout: float | None = None):
    """Bind minimal Studio namespaces to the real operation supervisor."""
    supervisor = CallSupervisor(
        metrics=ClientMetrics(), max_concurrent_rpcs=1, operation_timeout=timeout
    )
    supervisor.prepare_generation(1)
    supervisor.start_accepting(1)
    client = object.__new__(NotebookLMClient)
    client._collaborators = SimpleNamespace(call_supervisor=supervisor)

    async def notes_list(_):
        """Expose the text note selected for the first write."""
        return [SimpleNamespace(id=NOTE, title="note", content="body")]

    async def artifacts_list_with_status(_):
        """Expose an authoritative artifact snapshot for mixed-batch resolution."""
        return ArtifactListing(
            items=(SimpleNamespace(id=ART, title="report", kind=ArtifactType.REPORT),),
            is_complete=True,
        )

    async def maps_list(_):
        """Keep the report on the artifact deletion path."""
        return []

    client.notes = SimpleNamespace(list=notes_list)
    client.artifacts = SimpleNamespace(list_with_status=artifacts_list_with_status)
    client.mind_maps = SimpleNamespace(list_note_backed=maps_list)
    return client, supervisor


@pytest.mark.asyncio
async def test_batch_studio_delete_shares_one_configured_budget(monkeypatch):
    """The second write cannot restart the budget consumed by the first write."""
    # Advance virtual time in seconds, comfortably above Windows' clock resolution.
    # asyncio may dispatch timers one clock-resolution early while inventory reads
    # yield, so a millisecond-scale budget can expire before the first write.
    client, supervisor = _client(15.0)
    loop = asyncio.get_running_loop()
    now = loop.time()
    monkeypatch.setattr(loop, "time", lambda: now)
    dispatched = []

    async def notes_delete(*_):
        """Consume part of the budget after the first write is admitted."""
        nonlocal now
        async with supervisor.operation_scope("notes.delete"):
            dispatched.append("notes")
            now += 10.0

    async def artifacts_delete(*_):
        """Cross the aggregate deadline before dispatching the second write."""
        nonlocal now
        async with supervisor.operation_scope("artifacts.delete"):
            now += 10.0
            async with supervisor.call_scope("artifact.dispatch", None, None):
                dispatched.append("artifact")

    client.notes.delete = notes_delete
    client.artifacts.delete = artifacts_delete
    with pytest.raises(OperationTimeoutError):
        await delete_studio_items(client, "nb", [NOTE, ART], confirm=True)
    assert dispatched == ["notes"]
    await supervisor.wait_for_idle(1, 0)


@pytest.mark.asyncio
async def test_batch_studio_delete_preserves_nested_mutation_evidence():
    """When nested writes supply journal entries, a later failure preserves that evidence."""
    # These doubles isolate aggregation; real Web note deletes can have no journal
    # entries or per-note evidence (covered by the NotesAPI integration tests).
    client, supervisor = _client()

    async def notes_delete(*_):
        """Record a successful note mutation in the enclosing operation journal."""
        async with supervisor.operation_scope("notes.delete"):
            entry = adopt_operation_journal_entry(
                supervisor, method="DELETE_NOTE", operation="notes.delete"
            )
            assert entry is not None
            entry.mark_dispatched()
            entry.record(CommitState.CONFIRMED, "note delete accepted", known_resource_ids=(NOTE,))

    async def artifacts_delete(*_):
        """Record a rejected artifact mutation and propagate its failure."""
        async with supervisor.operation_scope("artifacts.delete"):
            entry = adopt_operation_journal_entry(
                supervisor, method="DELETE_ARTIFACT", operation="artifacts.delete"
            )
            assert entry is not None
            entry.mark_dispatched()
            entry.record(CommitState.REJECTED, "artifact denied")
            raise RPCError("artifact denied")

    client.notes.delete = notes_delete
    client.artifacts.delete = artifacts_delete
    with pytest.raises(RPCError, match="artifact denied") as caught:
        await delete_studio_items(client, "nb", [NOTE, ART], confirm=True)
    metadata = caught.value.operation_metadata
    assert metadata is not None
    assert metadata.commit_state is CommitState.CONFIRMED
    assert metadata.known_resource_ids == (NOTE,)
    assert [(entry.operation, entry.commit_state) for entry in metadata.entries] == [
        ("notes.delete", CommitState.CONFIRMED),
        ("artifacts.delete", CommitState.REJECTED),
    ]
    await supervisor.wait_for_idle(1, 0)
