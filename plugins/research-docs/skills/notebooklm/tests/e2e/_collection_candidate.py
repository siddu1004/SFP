"""Failure-safe provisioning for live collection lifecycle tests."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from typing import Protocol

from notebooklm import Collection, CollectionError
from notebooklm.outcomes import CommitState, RecoveryAction

_DISCOVERY_ATTEMPTS = 3
_CLEANUP_ATTEMPTS = 4
_RETRY_DELAY = 0.5


class _CollectionsNamespace(Protocol):
    async def list(self) -> list[Collection]: ...

    async def create(self, name: str) -> Collection: ...

    async def delete(self, collection_id: str) -> None: ...


class _CollectionClient(Protocol):
    collections: _CollectionsNamespace


def _reconciliation_candidate_ids(error: BaseException) -> set[str]:
    metadata = getattr(error, "operation_metadata", None)
    report = None if metadata is None else metadata.reconciliation
    return set() if report is None else {candidate.id for candidate in report.candidates}


async def _discover_candidate(
    client: _CollectionClient,
    *,
    name: str,
    baseline_ids: frozenset[str],
    candidate_ids: set[str],
    attempts: int,
    retry_delay: float,
) -> Collection:
    """Find exactly one named candidate without treating its row as product evidence."""

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            rows = await client.collections.list()
        except Exception as error:
            last_error = error
        else:
            matches = [
                row
                for row in rows
                if row.id not in baseline_ids and row.id in candidate_ids and row.name == name
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise AssertionError(
                    f"collection create reported multiple exact-name candidates: "
                    f"{[row.id for row in matches]!r}"
                )
        if attempt + 1 < attempts:
            await asyncio.sleep(retry_delay)

    if last_error is not None:
        raise AssertionError(
            f"collection candidate could not be inspected after {attempts} attempts: "
            f"{type(last_error).__name__}"
        ) from last_error
    raise AssertionError("collection create did not report one exact-name reconciliation candidate")


async def _cleanup_created_collection(
    client: _CollectionClient,
    *,
    name: str,
    baseline_ids: frozenset[str],
    candidate_ids: set[str],
    verified_ids: set[str],
    attempts: int,
    retry_delay: float,
) -> None:
    """Delete and verify only this run's exact-name, post-baseline rows.

    Candidate IDs alone are not ownership evidence. An ID becomes eligible only
    after a list shows that it was absent from the pre-create baseline and has
    this test's full UUID name. Once verified, the ID remains eligible if the
    lifecycle test renamed the collection before cleanup.
    """

    safe_ids = {
        collection_id for collection_id in verified_ids if collection_id not in baseline_ids
    }
    last_observation_clean = False
    for attempt in range(attempts):
        try:
            rows = await client.collections.list()
        except Exception:
            last_observation_clean = False
        else:
            exact_name_ids = {
                row.id for row in rows if row.id not in baseline_ids and row.name == name
            }
            # The exact full name is the test-harness ownership boundary. The
            # intersection corroborates candidate IDs before the union adds
            # exact-name rows seen after missing metadata or an unexpected return.
            corroborated_candidate_ids = candidate_ids & exact_name_ids
            safe_ids.update(corroborated_candidate_ids | exact_name_ids)
            remaining_ids = {
                row.id
                for row in rows
                if row.id not in baseline_ids and (row.id in safe_ids or row.name == name)
            }
            last_observation_clean = not remaining_ids
            for collection_id in sorted(remaining_ids):
                try:
                    await client.collections.delete(collection_id)
                except Exception:
                    # A later list determines whether the idempotent delete
                    # committed despite the error and retries only if it remains.
                    pass
        if attempt + 1 < attempts:
            await asyncio.sleep(retry_delay)

    # An early empty list is not conclusive after a create: the committed row
    # may become visible later. Consume the complete observation window above,
    # returning only when its final sample is clean. If the final sample failed
    # or still contained a row we attempted to delete, take one last list as
    # the bounded verification step used by the existing cleanup-error contract.
    if last_observation_clean:
        return

    try:
        rows = await client.collections.list()
    except Exception as error:
        raise AssertionError(
            f"collection cleanup could not be verified after {attempts} attempts: "
            f"{type(error).__name__}"
        ) from error

    leaked_ids = sorted(
        row.id
        for row in rows
        if row.id not in baseline_ids and (row.id in safe_ids or row.name == name)
    )
    if leaked_ids:
        raise AssertionError(f"collection cleanup left exact intended rows: {leaked_ids!r}")


@contextlib.asynccontextmanager
async def created_collection_candidate(
    client: _CollectionClient,
    label: str,
    *,
    token: str | None = None,
    discovery_attempts: int = _DISCOVERY_ATTEMPTS,
    cleanup_attempts: int = _CLEANUP_ATTEMPTS,
    retry_delay: float = _RETRY_DELAY,
) -> AsyncIterator[Collection]:
    """Create a UUID-named candidate and clean it on every exit path.

    The helper never changes the product contract: a decoded collection create
    must still raise with reconciliation evidence. The test harness uses the
    pre-create baseline plus an exact unique name only to provision disposable
    state for subsequent live lifecycle checks.
    """

    name = f"nbpy-e2e {label} {token or uuid.uuid4().hex}"
    baseline_ids = frozenset(row.id for row in await client.collections.list())
    candidate_ids: set[str] = set()
    verified_ids: set[str] = set()
    primary_error: BaseException | None = None
    primary_traceback = None
    try:
        try:
            try:
                returned = await client.collections.create(name)
            except BaseException as error:
                candidate_ids.update(_reconciliation_candidate_ids(error))
                if not isinstance(error, CollectionError):
                    raise
                create_error = error
            else:
                if isinstance(returned, Collection):
                    candidate_ids.add(returned.id)
                raise AssertionError("collection create unexpectedly returned a resource")

            metadata = create_error.operation_metadata
            assert metadata is not None
            assert metadata.commit_state is CommitState.CONFIRMED
            assert metadata.recovery_action is RecoveryAction.INSPECT_AND_RECONCILE
            assert metadata.known_resource_ids == ()
            assert metadata.reconciliation is not None

            collection = await _discover_candidate(
                client,
                name=name,
                baseline_ids=baseline_ids,
                candidate_ids=candidate_ids,
                attempts=discovery_attempts,
                retry_delay=retry_delay,
            )
            verified_ids.add(collection.id)
            yield collection
        except BaseException as error:
            primary_error = error
            primary_traceback = error.__traceback__

        try:
            await _cleanup_created_collection(
                client,
                name=name,
                baseline_ids=baseline_ids,
                candidate_ids=candidate_ids,
                verified_ids=verified_ids,
                attempts=cleanup_attempts,
                retry_delay=retry_delay,
            )
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            add_note = getattr(primary_error, "add_note", None)
            if add_note is not None:
                add_note(
                    "Secondary collection cleanup failure: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
            raise primary_error.with_traceback(primary_traceback) from cleanup_error
        if primary_error is not None:
            raise primary_error.with_traceback(primary_traceback)
    finally:
        # Break traceback/exception reference cycles retained across the
        # asynchronous cleanup awaits above.
        primary_error = None
        primary_traceback = None


__all__ = ["created_collection_candidate"]
