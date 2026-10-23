"""Deterministic coverage for failure-safe live collection provisioning."""

from __future__ import annotations

import asyncio

import pytest

from notebooklm import Collection, CollectionError
from notebooklm.outcomes import (
    CommitState,
    OperationMetadata,
    ReconciliationCandidate,
    ReconciliationReport,
    RecoveryAction,
)
from tests.e2e._collection_candidate import created_collection_candidate

_NAME = "nbpy-e2e Case fixed-token"


class _Collections:
    def __init__(
        self,
        *initial: Collection,
        create_mode: str = "error",
        metadata_mode: str = "candidate",
        create_exception: BaseException | None = None,
        add_unrelated: bool = False,
        list_failures: set[int] | None = None,
        delete_failures: int = 0,
        commit_create: bool = True,
        created_visible_on_list_call: int | None = None,
    ) -> None:
        self.items = {item.id: item for item in initial}
        self.create_mode = create_mode
        self.metadata_mode = metadata_mode
        self.create_exception = create_exception
        self.add_unrelated = add_unrelated
        self.list_failures = list_failures or set()
        self.delete_failures = delete_failures
        self.commit_create = commit_create
        self.created_visible_on_list_call = created_visible_on_list_call
        self.list_calls = 0
        self.delete_attempts: list[str] = []

    async def list(self) -> list[Collection]:
        self.list_calls += 1
        if self.list_calls in self.list_failures:
            raise RuntimeError("transient list failure")
        return [
            item
            for item in self.items.values()
            if not (
                item.id == "created-id"
                and self.created_visible_on_list_call is not None
                and self.list_calls < self.created_visible_on_list_call
            )
        ]

    async def create(self, name: str) -> Collection:
        created = Collection(id="created-id", name=name)
        if self.commit_create:
            self.items[created.id] = created
        if self.add_unrelated:
            self.items["unrelated-id"] = Collection(id="unrelated-id", name="someone else's row")
        if self.create_exception is not None:
            raise self.create_exception
        if self.create_mode == "return":
            return created

        error = CollectionError("inspect")
        if self.metadata_mode != "missing":
            candidate_ids = (
                ()
                if self.metadata_mode == "empty"
                else ("created-id", "unrelated-id", "preexisting-id")
            )
            error._operation_metadata = OperationMetadata(  # type: ignore[attr-defined]
                commit_state=CommitState.CONFIRMED,
                recovery_action=RecoveryAction.INSPECT_AND_RECONCILE,
                reconciliation=ReconciliationReport(
                    candidates=tuple(ReconciliationCandidate(id=item) for item in candidate_ids)
                ),
            )
        raise error

    async def delete(self, collection_id: str) -> None:
        self.delete_attempts.append(collection_id)
        if len(self.delete_attempts) <= self.delete_failures:
            raise RuntimeError("transient delete failure")
        self.items.pop(collection_id, None)


class _Client:
    def __init__(self, collections: _Collections) -> None:
        self.collections = collections


def _context(client: _Client):
    return created_collection_candidate(
        client,  # type: ignore[arg-type]
        "Case",
        token="fixed-token",
        retry_delay=0,
    )


async def test_body_assertion_still_cleans_only_exact_post_baseline_row() -> None:
    preexisting = Collection(id="preexisting-id", name=_NAME)
    collections = _Collections(preexisting, add_unrelated=True)
    client = _Client(collections)

    with pytest.raises(AssertionError, match="body failed"):
        async with _context(client) as collection:
            assert collection.id == "created-id"
            raise AssertionError("body failed")

    assert set(collections.items) == {"preexisting-id", "unrelated-id"}
    assert collections.delete_attempts == ["created-id"]


async def test_unexpected_create_return_is_cleaned_before_contract_failure_escapes() -> None:
    collections = _Collections(create_mode="return")

    with pytest.raises(AssertionError, match="unexpectedly returned"):
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert collections.items == {}
    assert collections.delete_attempts == ["created-id"]


@pytest.mark.parametrize("metadata_mode", ["missing", "empty"])
async def test_missing_create_evidence_still_cleans_exact_unique_name(
    metadata_mode: str,
) -> None:
    collections = _Collections(metadata_mode=metadata_mode)

    with pytest.raises(AssertionError):
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert collections.items == {}
    assert collections.delete_attempts == ["created-id"]


@pytest.mark.parametrize(
    "create_exception", [RuntimeError("write failed"), asyncio.CancelledError()]
)
async def test_post_commit_error_or_cancellation_is_preserved_after_cleanup(
    create_exception: BaseException,
) -> None:
    collections = _Collections(create_exception=create_exception)

    with pytest.raises(type(create_exception)) as raised:
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert raised.value is create_exception
    assert collections.items == {}
    assert collections.delete_attempts == ["created-id"]


async def test_transient_discovery_and_cleanup_lists_are_retried() -> None:
    # 1=baseline; 2=first discovery; 3=successful discovery;
    # 4=first cleanup; 5=cleanup/delete; 6-7=bounded absence confirmation.
    collections = _Collections(list_failures={2, 4})

    async with _context(_Client(collections)) as collection:
        assert collection.id == "created-id"

    assert collections.items == {}
    assert collections.list_calls == 7
    assert collections.delete_attempts == ["created-id"]


async def test_cleanup_deletes_candidate_that_appears_after_initial_absence() -> None:
    # 1=baseline; 2-4=discovery misses; 5=initial cleanup absence;
    # 6=the committed row becomes visible; 7-8=bounded absence confirmation.
    collections = _Collections(created_visible_on_list_call=6)

    with pytest.raises(
        AssertionError,
        match="did not report one exact-name reconciliation candidate",
    ):
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert collections.items == {}
    assert collections.list_calls == 8
    assert collections.delete_attempts == ["created-id"]


async def test_cleanup_confirms_stable_absence_for_the_bounded_window() -> None:
    # No row committed: discovery and every cleanup observation stay empty.
    collections = _Collections(commit_create=False)

    with pytest.raises(
        AssertionError,
        match="did not report one exact-name reconciliation candidate",
    ):
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert collections.items == {}
    assert collections.list_calls == 8
    assert collections.delete_attempts == []


async def test_transient_delete_is_retried_and_verified() -> None:
    collections = _Collections(delete_failures=1)

    async with _context(_Client(collections)):
        pass

    assert collections.items == {}
    assert collections.delete_attempts == ["created-id", "created-id"]


async def test_persistent_delete_failure_reports_exact_leak() -> None:
    collections = _Collections(delete_failures=99)

    with pytest.raises(AssertionError, match=r"exact intended rows: \['created-id'\]"):
        async with _context(_Client(collections)):
            pass

    assert set(collections.items) == {"created-id"}
    assert collections.delete_attempts == ["created-id"] * 4


async def test_body_error_remains_primary_when_cleanup_also_fails() -> None:
    collections = _Collections(delete_failures=99)
    primary = RuntimeError("body failed")

    with pytest.raises(RuntimeError) as raised:
        async with _context(_Client(collections)):
            raise primary

    assert raised.value is primary
    assert isinstance(raised.value.__cause__, AssertionError)
    assert "collection cleanup left exact intended rows" in str(raised.value.__cause__)


async def test_create_error_remains_primary_when_cleanup_also_fails() -> None:
    primary = RuntimeError("post-commit write failure")
    collections = _Collections(create_exception=primary, delete_failures=99)

    with pytest.raises(RuntimeError) as raised:
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert raised.value is primary
    assert isinstance(raised.value.__cause__, AssertionError)
    assert "collection cleanup left exact intended rows" in str(raised.value.__cause__)


async def test_cancellation_remains_primary_when_cleanup_also_fails() -> None:
    primary = asyncio.CancelledError()
    collections = _Collections(create_exception=primary, delete_failures=99)

    with pytest.raises(asyncio.CancelledError) as raised:
        async with _context(_Client(collections)):
            raise AssertionError("unreachable")

    assert raised.value is primary
    assert isinstance(raised.value.__cause__, AssertionError)
    assert "collection cleanup left exact intended rows" in str(raised.value.__cause__)
