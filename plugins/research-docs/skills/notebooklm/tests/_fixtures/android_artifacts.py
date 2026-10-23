"""Shared injected Android artifact terminals and graph builders."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

from google.protobuf import empty_pb2

from notebooklm._android.artifacts import (
    DELETE_ARTIFACT_METHOD,
    DERIVE_ARTIFACT_METHOD,
    EXPORT_TO_DRIVE_METHOD,
    GENERATE_ARTIFACT_METHOD,
    GENERATE_REPORT_SUGGESTIONS_METHOD,
    GET_ARTIFACT_METHOD,
    LIST_ARTIFACTS_METHOD,
    AndroidArtifactsAPI,
)
from notebooklm._android.assets import AndroidAssetDownloadService
from notebooklm._android.proto.google.internal.labs.tailwind.orchestration.v1 import artifacts_pb2
from notebooklm._android.session import AndroidSession
from notebooklm._client_metrics import ClientMetrics
from notebooklm._idempotency import bound_operation_journal_entries
from notebooklm._notebook_metadata import NotebookSourceIdProvider
from notebooklm._runtime.call_supervisor import CallSupervisor
from notebooklm._types.enums import ArtifactTypeCode
from notebooklm.types import Artifact, MindMap

_PROTO = artifacts_pb2


@dataclass(frozen=True)
class _Lease:
    epoch: int = 7


class FakeSession:
    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []
        self.errors: dict[str, BaseException] = {}
        self.scopes: list[str] = []

    @asynccontextmanager
    async def operation_scope(self, label: str, **kwargs: Any) -> AsyncIterator[_Lease]:
        assert not kwargs
        self.scopes.append(label)
        yield _Lease()

    async def unary(self, method: str, request: Any, **kwargs: Any) -> Any:
        for entry in bound_operation_journal_entries():
            entry.mark_dispatched()
        self.calls.append((method, request, kwargs))
        error = self.errors.get(method)
        if error is not None:
            raise error
        response = self.responses[method]
        if isinstance(response, list):
            return response.pop(0)
        return response


class FakeNotebooks:
    def __init__(self, source_ids: list[str] | None = None) -> None:
        self.source_ids = source_ids or ["source-1", "source-2"]
        self.calls: list[str] = []

    async def get_source_ids(self, notebook_id: str) -> list[str]:
        self.calls.append(notebook_id)
        return list(self.source_ids)


class FakeMindMaps:
    def __init__(self, artifacts: list[Artifact] | None = None) -> None:
        self.artifacts = artifacts or []
        self.mind_maps: list[MindMap] = []
        self.calls: list[str] = []
        self.error: BaseException | None = None

    async def list_mind_map_artifacts(self, notebook_id: str) -> list[Artifact]:
        self.calls.append(notebook_id)
        if self.error is not None:
            raise self.error
        return list(self.artifacts)

    async def list_mind_map_artifacts_with_content(
        self, notebook_id: str
    ) -> tuple[list[Artifact], list[MindMap]]:
        self.calls.append(notebook_id)
        if self.error is not None:
            raise self.error
        artifacts = list(self.artifacts) or [
            Artifact(
                id=mind_map.id,
                title=mind_map.title,
                _artifact_type=ArtifactTypeCode.MIND_MAP.value,
                status=3,
                created_at=mind_map.created_at,
            )
            for mind_map in self.mind_maps
        ]
        return artifacts, list(self.mind_maps)

    async def list_note_backed_mind_maps(self, notebook_id: str) -> list[MindMap]:
        self.calls.append(notebook_id)
        if self.error is not None:
            raise self.error
        return list(self.mind_maps)


class FakeAssets:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.representation_calls: list[tuple[str, str, str]] = []
        self.error: BaseException | None = None

    async def download_url(self, url: str, output_path: str) -> str:
        self.calls.append((url, output_path))
        if self.error is not None:
            raise self.error
        return output_path

    async def download_urls_batch(self, urls_and_paths: list[tuple[str, str]]) -> Any:
        raise AssertionError(f"batch transfer not expected: {urls_and_paths!r}")

    async def download_representation(
        self,
        url: str,
        output_path: str,
        *,
        representation: str,
    ) -> str:
        self.representation_calls.append((url, output_path, representation))
        if self.error is not None:
            raise self.error
        return output_path


def _supervisor() -> CallSupervisor:
    return CallSupervisor(
        metrics=ClientMetrics(),
        max_concurrent_rpcs=2,
    )


def _artifact(
    artifact_id: str,
    *,
    title: str = "Artifact",
    type_code: int = _PROTO.ARTIFACT_TYPE_INFOGRAPHIC,
    status: int = _PROTO.ARTIFACT_STATUS_READY,
    variant: int = 0,
    etag: str = "etag-1",
    url: str | None = None,
    source_ids: list[str] | None = None,
) -> Any:
    message = _PROTO.Artifact(
        artifact_id=artifact_id,
        title=title,
        type=type_code,
        status=status,
        etag=etag,
    )
    if type_code == _PROTO.ARTIFACT_TYPE_APP:
        message.app.generation_options.app_type = variant
    if type_code == _PROTO.ARTIFACT_TYPE_INFOGRAPHIC and url is not None:
        message.infographic.infographics.add(title=title).image.url = url
    for source_id in source_ids or []:
        message.sources.add().source_id.id = source_id
    return message


def _graph(
    studio: list[Any] | None = None,
) -> tuple[FakeSession, FakeNotebooks, FakeMindMaps, FakeAssets, AndroidArtifactsAPI]:
    studio_rows = studio or []
    get_response = _PROTO.GetArtifactResponse()
    if studio_rows:
        get_response.artifact.CopyFrom(studio_rows[-1])
    session = FakeSession(
        {
            LIST_ARTIFACTS_METHOD: _PROTO.ListArtifactsResponse(artifacts=studio_rows),
            GET_ARTIFACT_METHOD: get_response,
            DELETE_ARTIFACT_METHOD: empty_pb2.Empty(),
            DERIVE_ARTIFACT_METHOD: _PROTO.DeriveArtifactResponse(),
            GENERATE_ARTIFACT_METHOD: _PROTO.GenerateArtifactResponse(),
            EXPORT_TO_DRIVE_METHOD: _PROTO.ExportToDriveResponse(),
            GENERATE_REPORT_SUGGESTIONS_METHOD: _PROTO.GenerateReportSuggestionsResponse(),
        }
    )
    notebooks = FakeNotebooks()
    mind_maps = FakeMindMaps()
    assets = FakeAssets()

    api = AndroidArtifactsAPI(
        session=cast(AndroidSession, session),
        supervisor=_supervisor(),
        notebooks=cast(NotebookSourceIdProvider, notebooks),
        mind_maps=mind_maps,
        asset_downloads=cast(AndroidAssetDownloadService, assets),
    )
    return session, notebooks, mind_maps, assets, api
