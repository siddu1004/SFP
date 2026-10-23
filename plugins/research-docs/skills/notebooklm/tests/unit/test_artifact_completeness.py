"""Authoritative aggregate artifact-read contracts for the Web backend."""

from __future__ import annotations

import asyncio
import warnings
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from notebooklm._client_metrics import ClientMetrics
from notebooklm._runtime.call_supervisor import AdmissionState, CallSupervisor
from notebooklm._runtime.lifecycle import ClientLifecycle
from notebooklm._web.artifacts import WebArtifactsAPI
from notebooklm._web.mind_maps import NoteBackedMindMapService
from notebooklm._web.notes import NoteService
from notebooklm.exceptions import ArtifactNotFoundError, DecodingError, RPCError
from notebooklm.types import (
    ArtifactListingComponent,
    ArtifactLookupStatus,
    ArtifactType,
)
from tests._fixtures.fake_core import make_fake_core


def _studio_row(artifact_id: str = "studio") -> list[object]:
    return [artifact_id, "Studio result", 2, None, 3]


def _web_api(
    studio_rows: list[object],
    *,
    note_result: list[object] | BaseException,
) -> WebArtifactsAPI:
    core = make_fake_core(rpc_call=AsyncMock(return_value=studio_rows))
    mind_maps = MagicMock(spec=NoteBackedMindMapService)
    if isinstance(note_result, BaseException):
        mind_maps.list_mind_maps = AsyncMock(side_effect=note_result)
    else:
        mind_maps.list_mind_maps = AsyncMock(return_value=note_result)
    notebooks = MagicMock()
    notebooks.get_source_ids = AsyncMock(return_value=[])
    return WebArtifactsAPI(
        rpc=core,
        supervisor=core,
        notebooks=notebooks,
        mind_maps=mind_maps,
        note_service=MagicMock(spec=NoteService),
    )


@pytest.mark.asyncio
async def test_complete_empty_is_authoritative_missing() -> None:
    api = _web_api([], note_result=[])

    listing = await api.list_with_status("nb")
    lookup = await api.lookup("nb", "absent")

    assert listing.items == ()
    assert listing.is_complete
    assert listing.failures == ()
    assert lookup.status is ArtifactLookupStatus.MISSING
    assert lookup.artifact is None


@pytest.mark.asyncio
async def test_non_mind_map_filter_skips_irrelevant_secondary_read() -> None:
    api = _web_api([_studio_row()], note_result=AssertionError("must not run"))

    listing = await api.list_with_status("nb", ArtifactType.REPORT)

    assert [item.id for item in listing.items] == ["studio"]
    assert listing.is_complete
    api._mind_maps.list_mind_maps.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(RPCError("secret cookie: SID=do-not-retain"), id="rpc"),
        pytest.param(httpx.ConnectError("signed=https://secret.invalid/token"), id="http"),
    ],
)
async def test_studio_hit_plus_secondary_outage_is_found_with_bounded_evidence(
    error: BaseException,
) -> None:
    api = _web_api([_studio_row()], note_result=error)

    listing = await api.list_with_status("nb")
    lookup = await api.lookup("nb", "studio")

    assert [item.id for item in listing.items] == ["studio"]
    assert not listing.is_complete
    assert len(listing.failures) == 1
    failure = listing.failures[0]
    assert failure.component is ArtifactListingComponent.NOTE_BACKED_MIND_MAPS
    assert failure.error_type == type(error).__name__
    assert "secret" not in failure.message.lower()
    assert lookup.status is ArtifactLookupStatus.FOUND
    assert lookup.artifact is not None and lookup.artifact.id == "studio"
    assert lookup.failures[0].component is ArtifactListingComponent.NOTE_BACKED_MIND_MAPS


@pytest.mark.asyncio
async def test_no_hit_plus_secondary_outage_is_unknown() -> None:
    api = _web_api([], note_result=RPCError("temporary"))

    lookup = await api.lookup("nb", "absent")

    assert lookup.status is ArtifactLookupStatus.UNKNOWN
    assert lookup.artifact is None
    assert [failure.component for failure in lookup.failures] == [
        ArtifactListingComponent.NOTE_BACKED_MIND_MAPS
    ]


@pytest.mark.asyncio
async def test_web_listing_holds_one_admission_across_graceful_close() -> None:
    """A close between the two backing reads cannot split their generation."""
    supervisor = CallSupervisor(metrics=ClientMetrics(), max_concurrent_rpcs=None)
    lifecycle = ClientLifecycle(
        supervisor=supervisor,
        transports=(),
        loop_participants=(supervisor,),
    )
    await lifecycle.open()

    studio_started = asyncio.Event()
    release_studio = asyncio.Event()
    observed_epochs: list[int] = []

    async def list_studio(_notebook_id: str) -> list[object]:
        async with supervisor.call_scope("test.studio", "studio", None) as lease:
            observed_epochs.append(lease.epoch)
            studio_started.set()
            await release_studio.wait()
            return [_studio_row()]

    async def list_notes(_notebook_id: str) -> list[object]:
        async with supervisor.call_scope("test.notes", "notes", None) as lease:
            observed_epochs.append(lease.epoch)
            return []

    api = _web_api([], note_result=[])
    api._supervisor = supervisor
    api._list_raw = list_studio  # type: ignore[method-assign]
    api._mind_maps.list_mind_maps = list_notes

    workflow = asyncio.create_task(api.list_with_status("nb"))
    await studio_started.wait()
    closing = asyncio.create_task(lifecycle.close(drain=True))
    for _ in range(100):
        generation = supervisor._current
        if generation is not None and generation.state is AdmissionState.DRAINING:
            break
        await asyncio.sleep(0)
    else:
        raise AssertionError("graceful close did not begin draining")

    release_studio.set()
    listing, _ = await asyncio.gather(workflow, closing)

    assert [item.id for item in listing.items] == ["studio"]
    assert listing.is_complete
    assert observed_epochs == [1, 1]


@pytest.mark.asyncio
async def test_primary_failure_and_secondary_decoding_error_raise_by_identity() -> None:
    primary = RPCError("primary unavailable")
    api = _web_api([], note_result=[])
    api._list_raw = AsyncMock(side_effect=primary)  # type: ignore[method-assign]
    with pytest.raises(RPCError) as primary_raised:
        await api.list_with_status("nb")
    assert primary_raised.value is primary

    drift = DecodingError("note schema drift")
    api = _web_api([], note_result=drift)
    with pytest.raises(DecodingError) as drift_raised:
        await api.list_with_status("nb")
    assert drift_raised.value is drift


@pytest.mark.asyncio
async def test_legacy_warning_is_targeted_to_ambiguous_absence() -> None:
    found_api = _web_api([_studio_row()], note_result=RPCError("temporary"))
    with warnings.catch_warnings(record=True) as found_warnings:
        warnings.simplefilter("always")
        assert (await found_api.get_or_none("nb", "studio")) is not None
    assert not [item for item in found_warnings if item.category is DeprecationWarning]

    missing_api = _web_api([], note_result=[])
    with warnings.catch_warnings(record=True) as missing_warnings:
        warnings.simplefilter("always")
        assert await missing_api.get_or_none("nb", "absent") is None
    assert not [item for item in missing_warnings if item.category is DeprecationWarning]

    unknown_api = _web_api([], note_result=RPCError("temporary"))
    with pytest.warns(DeprecationWarning, match="artifacts.lookup"):
        assert await unknown_api.get_or_none("nb", "absent") is None
    with (
        pytest.warns(DeprecationWarning, match="artifacts.lookup"),
        pytest.raises(ArtifactNotFoundError),
    ):
        await unknown_api.get("nb", "absent")


@pytest.mark.asyncio
async def test_web_strict_prompt_keeps_direct_path_without_lookup_preflight() -> None:
    api = _web_api([_studio_row()], note_result=[])
    api.lookup = AsyncMock(side_effect=AssertionError("redundant aggregate lookup"))  # type: ignore[method-assign]

    assert await api.get_prompt("nb", "studio", require_complete=True) is None

    api.lookup.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("require_complete", [False, True])
async def test_web_prompt_propagates_secondary_outage_directly(
    require_complete: bool,
) -> None:
    error = RPCError("note read unavailable")
    api = _web_api([], note_result=error)

    with pytest.raises(RPCError) as raised:
        await api.get_prompt("nb", "absent", require_complete=require_complete)

    assert raised.value is error
