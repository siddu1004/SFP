"""Supervised per-occurrence source deletion with bounded cleanup pacing."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace

from .._idempotency import attach_operation_metadata
from ..exceptions import ValidationError
from ..outcomes import (
    _MAX_BATCH_OUTCOME_ITEMS,
    BatchItemOutcome,
    BatchOutcome,
    CommitState,
    OperationMetadata,
    ReconciliationReport,
    RecoveryAction,
)
from ..types import SourceDeleteOutcome
from .polling import SpawnSourceChild


def _attach_settlement(error: BaseException, results: list[SourceDeleteOutcome]) -> None:
    """Keep complete local results and an explicitly bounded adapter receipt."""
    previous = (
        getattr(error, "operation_metadata", None)
        or getattr(error, "_operation_metadata", None)
        or OperationMetadata()
    )
    items = tuple(item.outcome for item in results)
    states = {CommitState.NOT_SENT, previous.commit_state, *(item.commit_state for item in items)}
    state = next(
        candidate
        for candidate in (
            CommitState.UNKNOWN,
            CommitState.CONFIRMED,
            CommitState.REJECTED,
            CommitState.NOT_SENT,
        )
        if candidate in states
    )
    attach_operation_metadata(
        error,
        replace(
            previous,
            batch_outcome=(BatchOutcome(items) if len(items) <= _MAX_BATCH_OUTCOME_ITEMS else None),
            source_delete_outcomes=items,
            commit_state=state,
            recovery_action=(
                RecoveryAction.INSPECT_AND_RECONCILE
                if state is CommitState.UNKNOWN
                else previous.recovery_action
            ),
        ),
    )


def _failed(member: int, source_id: str, error: BaseException) -> SourceDeleteOutcome:
    metadata = getattr(error, "operation_metadata", None) or getattr(
        error, "_operation_metadata", None
    )
    state = (
        metadata.commit_state
        if metadata is not None and metadata.commit_state is not None
        else CommitState.UNKNOWN
    )
    return SourceDeleteOutcome(
        source_id,
        BatchItemOutcome(
            member=member,
            input=source_id,
            commit_state=state,
            resource_id=(
                source_id
                if state is CommitState.CONFIRMED
                else (metadata.source_id or next(iter(metadata.known_resource_ids), None))
                if state is CommitState.UNKNOWN and metadata is not None
                else None
            ),
            error=None if state is CommitState.CONFIRMED else error,
            reconciliation=(
                (metadata.reconciliation if metadata is not None else None)
                or ReconciliationReport(
                    unresolved_inputs=(source_id,), reason="source deletion was not confirmed"
                )
            )
            if state is CommitState.UNKNOWN
            else None,
        ),
        error=error,
    )


async def delete_sources_with_outcomes(
    notebook_id: str,
    source_ids: tuple[str, ...],
    *,
    delete: Callable[[str, str], Awaitable[None]],
    spawn_child: SpawnSourceChild,
) -> list[SourceDeleteOutcome]:
    """Keep cleanup's ten-wide, 0.5-second pacing and settle before escape."""
    if any(not isinstance(sid, str) or not sid for sid in source_ids):
        raise ValidationError("source_ids must contain non-empty source IDs")
    results = [
        SourceDeleteOutcome(sid, BatchItemOutcome(i, sid, CommitState.NOT_SENT))
        for i, sid in enumerate(source_ids)
    ]
    tasks: list[asyncio.Task[None]] = []

    def factory(index: int) -> Callable[[], Awaitable[None]]:
        async def run() -> None:
            sid = source_ids[index]
            try:
                await delete(notebook_id, sid)
            except BaseException as error:
                results[index] = _failed(index, sid, error)
                if not isinstance(error, Exception):
                    raise
            else:
                results[index] = SourceDeleteOutcome(
                    sid, BatchItemOutcome(index, sid, CommitState.CONFIRMED, resource_id=sid)
                )

        return run

    try:
        for start in range(0, len(source_ids), 10):
            tasks = []
            for index in range(start, min(start + 10, len(source_ids))):
                tasks.append(await spawn_child("sources.delete_many.member", factory(index)))
            await asyncio.gather(*tasks)
            if start + 10 < len(source_ids):
                await asyncio.sleep(0.5)
    except BaseException as error:
        for task in tasks:
            if not task.done():
                task.cancel()
        settlement = asyncio.gather(*tasks, return_exceptions=True)
        while not settlement.done():
            try:
                await asyncio.shield(settlement)
            except asyncio.CancelledError:
                # Repeated caller cancellation cannot abandon owned writers/children.
                continue
        settlement.result()
        _attach_settlement(error, results)
        raise
    return results
