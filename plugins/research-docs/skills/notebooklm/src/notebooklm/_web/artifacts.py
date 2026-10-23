"""Artifacts API for NotebookLM studio content.

Provides operations for generating, listing, downloading, and managing
AI-generated artifacts including Audio Overviews, Video Overviews, Reports,
Quizzes, Flashcards, Infographics, Slide Decks, Data Tables, and Mind Maps.
"""

import builtins
import contextlib
import logging
import reprlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._artifact import polling as _artifact_polling
from .._artifact.creation_normalized import NormalizedArtifactCreationRequest
from .._artifact.download_selection import PreparedDownloadCache
from .._artifact.downloads import AssetDownloadService
from .._artifacts import ArtifactsAPI, _ArtifactCopyResult
from .._idempotency import call_unconfirmed_on_transport_loss, unresolved_commit_error
from .._notebook_metadata import NotebookSourceIdProvider
from .._request_policy import RequestPolicyOwner, request_scoped
from .._types.artifact_download import (
    ArtifactDownloadListing,
    ArtifactDownloadRequest,
    ArtifactDownloadSelection,
)
from .._types.enums import (
    ArtifactTypeCode,
    ExportType,
)
from .._types.research import MindMapResult
from ..exceptions import (
    ArtifactNotFoundError,
    NetworkError,
    RateLimitError,
    RPCError,
    ServerError,
)
from ..rpc import RPCMethod
from ..types import (
    Artifact,
    ArtifactCreationCapability,
    ArtifactCustomizationChoices,
    ArtifactListing,
    ArtifactType,
    CopiedArtifact,
    CustomizationChoice,
    GenerationStatus,
    ReportPreset,
    ReportSuggestion,
)
from .artifact.downloads import ArtifactDownloadService
from .artifact.generation import ArtifactGenerationService
from .artifact.listing import ArtifactListingService
from .contracts import RpcCaller
from .mind_maps import NoteBackedMindMapService
from .notes import NoteService
from .params.artifacts import (
    build_copy_artifacts_params,
    build_customization_choices_params,
    build_suggest_reports_params,
)
from .params.creation import encode_creation
from .rows import artifacts as _artifact_rows
from .rows.customization import unwrap_customization_choices
from .rows.transfers import CopiedArtifactRow, unwrap_mapping_rows

if TYPE_CHECKING:
    from .._runtime.call_supervisor import CallSupervisor, OperationLease

logger = logging.getLogger("notebooklm._artifacts")


@dataclass(frozen=True)
class _PreparedWebDownload:
    """Private rows retained for one opaque prepared selection."""

    artifacts_data: builtins.list[Any]
    mind_maps: builtins.list[Any] | None
    artifacts: builtins.list[Artifact]
    is_note_backed_mind_map: bool


class WebArtifactsAPI(RequestPolicyOwner, ArtifactsAPI):
    """Operations on NotebookLM artifacts (studio content).

    Artifacts are AI-generated content: Audio/Video Overviews, Reports,
    Quizzes, Flashcards, Infographics, Slide Decks, Data Tables, and Mind Maps.

    Usage::

        async with NotebookLMClient.from_storage() as client:
            status = await client.artifacts.generate_audio(notebook_id)
            await client.artifacts.wait_for_completion(notebook_id, status.task_id)
            await client.artifacts.download_audio(notebook_id, "output.mp4")
            artifacts = await client.artifacts.list(notebook_id)
            await client.artifacts.rename(notebook_id, artifact_id, "New Title")
    """

    def _operation_scope(
        self, label: str
    ) -> contextlib.AbstractAsyncContextManager["OperationLease"]:
        """Return the backend's scope for one multi-call workflow."""
        return self._supervisor.operation_scope(label)

    def __init__(
        self,
        *,
        rpc: RpcCaller,
        supervisor: "CallSupervisor",
        notebooks: NotebookSourceIdProvider,
        mind_maps: NoteBackedMindMapService,
        note_service: NoteService,
        storage_path: Path | None = None,
        asset_downloads: AssetDownloadService | None = None,
    ) -> None:
        """Initialize the artifacts API.

        Args:
            rpc: RPC dispatch surface (:class:`RpcCaller`) — used for direct
                artifact RPCs (delete, rename, export, list_raw) and threaded
                into the generation and download services.
            supervisor: The single logical-call admission authority used for
                polling scopes, child leaders, loop-affinity checks, and drain
                hook registration.
            notebooks: Source-id resolver. Required — wire from
                ``NotebookLMClient`` (no implicit fallback). Threaded into the
                generation service.
            mind_maps: Note-backed mind-map facade (:class:`NoteBackedMindMapService`)
                — owns the ``list_mind_maps`` / ``extract_content`` paths
                consumed by ``_web.artifact.downloads.download_mind_map``.
            note_service: Backend note-row primitives — owns the ``create_note``
                call site that the generation service's ``generate_mind_map``
                uses to persist generated mind maps.
            storage_path: Standalone helper compatibility cookie source.
            asset_downloads: Selected Web asset lifecycle and live-cookie owner.
        """
        super().__init__(
            supervisor=supervisor,
            notebooks=notebooks,
            asset_downloads=asset_downloads or AssetDownloadService(storage_path=storage_path),
        )
        self._rpc = rpc
        self._mind_maps = mind_maps
        self._note_service = note_service
        self._listing = ArtifactListingService()
        self._downloads = ArtifactDownloadService(
            rpc=self._rpc,
            listing=self._listing,
            mind_maps=self._mind_maps,
            asset_downloads=self._asset_downloads,
            download_to_path=self._download_to_path,
            download_urls_batch=self._download_urls_batch,
            format_interactive_content=self._format_interactive_content,
        )
        self._generation = ArtifactGenerationService(
            rpc=self._rpc,
            notebooks=self._notebooks,
            note_service=self._note_service,
        )
        self._prepared_downloads: PreparedDownloadCache[_PreparedWebDownload] = (
            PreparedDownloadCache()
        )

    @request_scoped
    def _resolve_language(self, language: str | None) -> str:
        return super()._resolve_language(language)

    async def _send_create_artifact(
        self,
        request: NormalizedArtifactCreationRequest,
    ) -> GenerationStatus:
        params, label = encode_creation(request)
        return await self._generation._call_generate(
            request.notebook_id,
            params,
            null_result_artifact_type=label,
        )

    # =========================================================================
    # List/Get Operations
    # =========================================================================

    async def list(
        self, notebook_id: str, artifact_type: ArtifactType | None = None
    ) -> builtins.list[Artifact]:
        """List all artifacts in a notebook, including mind maps.

        Returns all AI-generated content. Note-backed mind maps live in the
        notes collection while interactive mind maps are studio artifacts
        (type 4 / variant 4); this listing merges both backings under
        ``ArtifactType.MIND_MAP``. Pass ``artifact_type`` to filter (e.g.
        ``ArtifactType.MIND_MAP`` for mind maps only).
        """
        listing = await self.list_with_status(notebook_id, artifact_type)
        return list(listing.items)

    async def list_with_status(
        self, notebook_id: str, artifact_type: ArtifactType | None = None
    ) -> ArtifactListing:
        """List artifacts together with aggregate-read completeness evidence.

        Primary Studio failures and all decoding failures raise directly.
        A transient secondary backing failure returns the successfully decoded
        items with ``is_complete=False`` and a bounded component diagnostic.
        """
        logger.debug("Listing artifacts in notebook %s", notebook_id)
        async with self._operation_scope("artifacts.list"):
            (
                listing,
                _raw_studio_rows,
                _mind_map_rows,
            ) = await self._listing.list_artifacts_with_status_and_raw(
                notebook_id,
                artifact_type,
                list_raw=self._list_raw,
                list_mind_maps=self._list_mind_maps,
            )
        return listing

    async def _list_for_download(
        self, notebook_id: str, artifact_type: ArtifactType | None = None
    ) -> tuple[builtins.list[Artifact], builtins.list[Any], builtins.list[Any] | None]:
        """List artifacts + raw rows for the legacy download-prefetch seam."""
        return await self._listing.list_artifacts_with_raw(
            notebook_id,
            artifact_type,
            list_raw=self._list_raw,
            list_mind_maps=self._list_mind_maps,
        )

    async def get_prompt(
        self,
        notebook_id: str,
        artifact_id: str,
        *,
        require_complete: bool = False,
    ) -> str | None:
        """Get the free-text prompt an artifact was generated from (any studio type).

        Returns ``None`` when the artifact stores no prompt (e.g. a note-backed
        mind map); raises :class:`ArtifactNotFoundError` for an unknown id.
        ``require_complete=True`` prevents a failed aggregate backing from
        being projected as absence. Web's direct prompt read is already strict;
        Android uses :meth:`lookup` for this explicit path.

        .. versionadded:: 0.8.0
        """
        # This decoder already reads Studio directly and propagates the exact
        # note-backed lookup failure on a Studio miss. ``require_complete`` is
        # therefore an additive cross-backend spelling, not a Web preflight.
        return await self._listing.get_prompt(notebook_id, artifact_id, list_raw=self._list_raw, list_mind_maps=self._list_mind_maps)  # fmt: skip

    # =========================================================================
    # Generate Operations
    # =========================================================================

    async def revise_slide(
        self,
        notebook_id: str,
        artifact_id: str,
        slide_index: int,
        prompt: str,
    ) -> GenerationStatus:
        """Revise an individual slide in a completed slide deck using a prompt."""
        return await self._generation.revise_slide(notebook_id, artifact_id, slide_index, prompt)

    async def retry_failed(self, notebook_id: str, artifact_id: str) -> GenerationStatus:
        """Retry a failed Studio artifact in place (the UI "Retry" action).

        Re-runs generation for an already-failed artifact without deleting it
        first; the same ``artifact_id`` is preserved as the task id, so existing
        :meth:`poll_status` / :meth:`wait_for_completion` flows keep working. An
        accepted retry returns ``GenerationStatus(status="pending")`` (#2127).

        Follows the ADR-0019 "async kickoff" contract: a synchronous
        ``USER_DISPLAYABLE_ERROR`` refusal (rate limit, quota, non-retryable
        artifact) **raises** ``RateLimitError`` / ``RPCError`` rather than
        returning ``status="failed"``, matching the sibling ``generate_*`` /
        :meth:`revise_slide` methods after v0.8.0 (#1342). A null / missing-id
        result raises :class:`ArtifactFeatureUnavailableError`. ``notebook_id``
        is routing-only (sets the ``source_path`` header); the artifact is
        identified solely by ``artifact_id``.
        """
        return await self._generation.retry_failed(notebook_id, artifact_id)

    async def generate_mind_map(
        self,
        notebook_id: str,
        source_ids: builtins.list[str] | None = None,
        language: str | None = "en",
        instructions: str | None = None,
    ) -> MindMapResult:
        """Generate a note-backed mind map and persist it as a note.

        Returns a :class:`~notebooklm._types.research.MindMapResult` with
        ``mind_map`` (parsed structure, or ``None`` on an empty response) and
        ``note_id`` (the persisted note id, or ``None``).
        """
        async with self._operation_scope("artifacts.generate_mind_map"):
            return await self._generation.generate_mind_map(
                notebook_id,
                source_ids=source_ids,
                language=language,
                instructions=instructions,
            )

    # =========================================================================
    # Download Operations
    # =========================================================================

    async def prepare_downloads(self, request: ArtifactDownloadRequest) -> ArtifactDownloadListing:
        """Prepare completed candidates without exposing backend caches.

        Validate the representation before I/O. Every returned selection is
        bound to this backend instance, notebook, and current client generation.
        Partial results retain typed failure evidence; they do not prove absence.
        """
        # Validate before reading either aggregate backing, including the empty
        # listing case where ``PreparedDownloadCache.prepare`` would not run.
        self._prepared_downloads.validate_request(request)
        async with self._operation_scope("artifacts.prepare_downloads") as lease:
            (
                listing,
                artifacts_data,
                mind_maps,
            ) = await self._listing.list_artifacts_with_status_and_raw(
                request.notebook_id,
                request.kind,
                list_raw=self._list_raw,
                list_mind_maps=self._list_mind_maps,
            )
            selections: list[ArtifactDownloadSelection] = []
            for artifact in listing.items:
                if artifact.kind is not request.kind or not artifact.is_completed:
                    continue
                selections.append(
                    self._prepared_downloads.prepare(
                        request,
                        artifact,
                        _PreparedWebDownload(
                            artifacts_data=artifacts_data,
                            mind_maps=mind_maps,
                            artifacts=list(listing.items),
                            is_note_backed_mind_map=(
                                artifact.kind is ArtifactType.MIND_MAP
                                and artifact._artifact_type == ArtifactTypeCode.MIND_MAP.value
                            ),
                        ),
                        epoch=lease.epoch,
                    )
                )
            return ArtifactDownloadListing(
                selections=tuple(selections),
                is_complete=listing.is_complete,
                failures=listing.failures,
            )

    async def download(self, selection: ArtifactDownloadSelection, output_path: str) -> str:
        """Download an owned prepared identity within its admitted generation."""
        snapshot: _PreparedWebDownload | None = None
        request: ArtifactDownloadRequest | None = None
        mind_maps: builtins.list[Any] | None = None
        try:
            async with self._operation_scope("artifacts.download") as lease:
                snapshot = self._prepared_downloads.require(selection, epoch=lease.epoch)
                request = ArtifactDownloadRequest(
                    selection.notebook_id,
                    selection.kind,
                    selection.representation,
                )
                # An interactive Studio mind map remains usable when its optional
                # notes aggregate failed. ``[]`` means this prepared selection has
                # no note-backed match and deliberately avoids retrying that RPC.
                mind_maps = snapshot.mind_maps if snapshot.mind_maps is not None else []
                return await self._download_with_legacy_prefetch(
                    request,
                    output_path,
                    selection.artifact_id,
                    artifacts_data=snapshot.artifacts_data,
                    mind_maps=mind_maps,
                    artifacts=snapshot.artifacts,
                )
        finally:
            del self, snapshot, request, mind_maps

    async def _download_with_legacy_prefetch(
        self,
        request: ArtifactDownloadRequest,
        output_path: str,
        artifact_id: str | None,
        *,
        artifacts_data: builtins.list[Any] | None = None,
        mind_maps: builtins.list[Any] | None = None,
        artifacts: builtins.list[Artifact] | None = None,
    ) -> str:
        """Dispatch compatibility rows through the existing typed backend methods."""
        try:
            if request.kind is ArtifactType.AUDIO:
                return await self._download_audio_legacy(
                    request.notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
                )
            if request.kind is ArtifactType.VIDEO:
                return await self._download_video_legacy(
                    request.notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
                )
            if request.kind is ArtifactType.INFOGRAPHIC:
                return await self._download_infographic_legacy(
                    request.notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
                )
            if request.kind is ArtifactType.SLIDE_DECK:
                return await self._download_slide_deck_legacy(
                    request.notebook_id,
                    output_path,
                    artifact_id,
                    "pdf" if request.output_format is None else request.output_format,
                    artifacts_data=artifacts_data,
                )
            if request.kind is ArtifactType.REPORT:
                return await self._download_report_legacy(
                    request.notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
                )
            if request.kind is ArtifactType.MIND_MAP:
                return await self._download_mind_map_legacy(
                    request.notebook_id,
                    output_path,
                    artifact_id,
                    mind_maps=mind_maps,
                    artifacts_data=artifacts_data,
                )
            if request.kind is ArtifactType.DATA_TABLE:
                return await self._download_data_table_legacy(
                    request.notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
                )
            if request.kind is ArtifactType.QUIZ:
                return await self._download_quiz_legacy(
                    request.notebook_id,
                    output_path,
                    artifact_id,
                    "json" if request.output_format is None else request.output_format,
                    artifacts=artifacts,
                )
            if request.kind is ArtifactType.FLASHCARDS:
                return await self._download_flashcards_legacy(
                    request.notebook_id,
                    output_path,
                    artifact_id,
                    "json" if request.output_format is None else request.output_format,
                    artifacts=artifacts,
                )
            raise AssertionError(f"unsupported prepared artifact kind: {request.kind!r}")
        finally:
            del self, request, artifacts_data, mind_maps, artifacts

    async def _download_audio_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        *,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download an Audio Overview to a file."""
        async with self._operation_scope("artifacts.download_audio"):
            return await self._downloads.download_audio(
                notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
            )

    async def _download_video_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        *,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download a Video Overview to a file."""
        async with self._operation_scope("artifacts.download_video"):
            return await self._downloads.download_video(
                notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
            )

    async def _download_infographic_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        *,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download an Infographic to a file."""
        async with self._operation_scope("artifacts.download_infographic"):
            return await self._downloads.download_infographic(
                notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
            )

    async def _download_slide_deck_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        output_format: str = "pdf",
        *,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download a slide deck as PDF or PPTX."""
        async with self._operation_scope("artifacts.download_slide_deck"):
            return await self._downloads.download_slide_deck(
                notebook_id, output_path, artifact_id, output_format, artifacts_data=artifacts_data
            )

    async def _download_interactive_artifact(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None,
        output_format: str,
        artifact_type: str,
        *,
        artifacts: builtins.list[Artifact] | None = None,
    ) -> str:
        """Download quiz or flashcard artifact."""
        return await self._downloads.download_interactive_artifact(
            notebook_id, output_path, artifact_id, output_format, artifact_type, artifacts=artifacts
        )

    async def _download_report_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        *,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download a report artifact as markdown."""
        async with self._operation_scope("artifacts.download_report"):
            return await self._downloads.download_report(
                notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
            )

    async def _download_mind_map_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        *,
        mind_maps: builtins.list[Any] | None = None,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download a mind map as JSON."""
        async with self._operation_scope("artifacts.download_mind_map"):
            return await self._downloads.download_mind_map(
                notebook_id,
                output_path,
                artifact_id,
                mind_maps=mind_maps,
                artifacts_data=artifacts_data,
            )

    async def _download_data_table_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        *,
        artifacts_data: builtins.list[Any] | None = None,
    ) -> str:
        """Download a data table as CSV."""
        async with self._operation_scope("artifacts.download_data_table"):
            return await self._downloads.download_data_table(
                notebook_id, output_path, artifact_id, artifacts_data=artifacts_data
            )

    async def _download_quiz_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        output_format: str = "json",
        *,
        artifacts: builtins.list[Artifact] | None = None,
    ) -> str:
        """Download quiz questions."""
        async with self._operation_scope("artifacts.download_quiz"):
            return await self._download_interactive_artifact(
                notebook_id, output_path, artifact_id, output_format, "quiz", artifacts=artifacts
            )

    async def _download_flashcards_legacy(
        self,
        notebook_id: str,
        output_path: str,
        artifact_id: str | None = None,
        output_format: str = "json",
        *,
        artifacts: builtins.list[Artifact] | None = None,
    ) -> str:
        """Download flashcard deck."""
        async with self._operation_scope("artifacts.download_flashcards"):
            return await self._download_interactive_artifact(
                notebook_id,
                output_path,
                artifact_id,
                output_format,
                "flashcards",
                artifacts=artifacts,
            )

    # =========================================================================
    # Management Operations
    # =========================================================================

    async def delete(self, notebook_id: str, artifact_id: str) -> None:
        """Delete an artifact.

        Idempotent: deleting an already-absent artifact succeeds (returns
        ``None``) and never raises ``ArtifactNotFoundError``. Real failures
        (``403``/``5xx``/auth/transport) still propagate.

        .. versionchanged:: 0.7.0
            **Breaking change:** previously returned a hardcoded ``True``;
            now returns ``None`` (issue #1211). ``if await artifacts.delete(...):``
            no longer enters its block.
        """
        logger.debug("Deleting artifact %s from notebook %s", artifact_id, notebook_id)
        params = [[2], artifact_id]  # Single-id only; live batch-shape probes failed.
        await self._rpc.rpc_call(
            RPCMethod.DELETE_ARTIFACT,
            params,
            source_path=f"/notebook/{notebook_id}",
            allow_null=True,
        )

    async def rename(
        self,
        notebook_id: str,
        artifact_id: str,
        new_title: str,
        *,
        return_object: bool = True,
    ) -> Artifact | None:
        """Rename an artifact.

        ``return_object=True`` (default) re-fetches (a full ``LIST_ARTIFACTS``
        call) and returns the renamed :class:`~notebooklm.types.Artifact`;
        ``False`` returns ``None`` on success. Miss-detection runs in both
        modes.

        Raises:
            ArtifactNotFoundError: if the artifact does not exist (detected via
                a list fetch, not a 404), in both ``return_object`` modes.
                Note-backed mind-map ids are *not* renameable here — use
                ``mind_maps.rename``.

        .. versionchanged:: 0.7.0
            **Breaking change:** no longer returns ``None`` on success; it
            re-fetches and raises :class:`ArtifactNotFoundError` for a missing
            target (#1255), plus the ``return_object`` opt-out.

        .. versionchanged:: 0.8.0
            **Breaking change:** ``return_object=False`` now runs the existence
            preflight too, so a missing target raises
            :class:`ArtifactNotFoundError` instead of silently returning
            ``None`` (#1362).
        """
        async with self._operation_scope("artifacts.rename"):
            params = [[artifact_id, new_title], [["title"]]]
            await self._rpc.rpc_call(
                RPCMethod.RENAME_ARTIFACT,
                params,
                source_path=f"/notebook/{notebook_id}",
                allow_null=True,
                # #2290: a status-tagged null is a server rejection, not an empty success.
                raise_on_null_status=True,
            )
            # Resolve via studio artifacts only — never public ``get()`` (#1247) nor
            # the merged listing (a note-backed mind-map id no-ops on RENAME_ARTIFACT
            # — use ``mind_maps.rename``). v0.8.0 (#1362): the lookup runs on
            # ``False`` too so a missing target is detected, but ``False`` still
            # returns ``None`` on success.
            artifact = await self._listing.get_studio_only(
                notebook_id, artifact_id, list_raw=self._list_raw
            )
            if artifact is None:
                raise ArtifactNotFoundError(artifact_id, method_id=RPCMethod.RENAME_ARTIFACT.value)
            return None if not return_object else artifact

    # =========================================================================
    # Export Operations
    # =========================================================================

    async def _send_export(
        self,
        notebook_id: str,
        artifact_id: str | None,
        title: str,
        export_type: ExportType,
        *,
        content: str | None,
    ) -> Any:
        """Send one ``EXPORT_ARTIFACT`` request through the Web frontend."""
        params = [None, artifact_id, content, title, int(export_type)]
        return await call_unconfirmed_on_transport_loss(
            lambda: self._rpc.rpc_call(
                RPCMethod.EXPORT_ARTIFACT,
                params,
                source_path=f"/notebook/{notebook_id}",
                allow_null=True,
                # #2290: a status-tagged null is a server rejection, not an empty success.
                raise_on_null_status=True,
            ),
            method=RPCMethod.EXPORT_ARTIFACT,
            what="the artifact or content export",
        )

    # =========================================================================
    # Suggestions
    # =========================================================================

    async def suggest_reports(
        self,
        notebook_id: str,
    ) -> builtins.list[ReportSuggestion]:
        """Get AI-suggested report formats for a notebook."""
        params = build_suggest_reports_params(notebook_id)

        result = await self._rpc.rpc_call(
            RPCMethod.GET_SUGGESTED_REPORTS,
            params,
            source_path=f"/notebook/{notebook_id}",
            allow_null=True,
        )

        if not (result and isinstance(result, list)):
            return []

        # GET_SUGGESTED_REPORTS returns a wrapped ``[[row1, ...]]`` envelope or a
        # flat list; the wrap probe + per-row decode are centralised behind
        # ``unwrap_artifact_rows`` / ``ReportSuggestionRow`` (#1491).
        items = _artifact_rows.unwrap_artifact_rows(
            result, method_id=RPCMethod.GET_SUGGESTED_REPORTS.value, source="suggest_reports"
        )
        return [
            ReportSuggestion(
                title=row.title,
                description=row.description,
                prompt=row.prompt,
                audience_level=row.audience_level,
            )
            for row in map(_artifact_rows.ReportSuggestionRow, items)
            if row.is_well_formed
        ]

    async def _send_copy(
        self,
        notebook_id: str,
        artifact_ids: builtins.list[str],
        target_notebook_id: str,
    ) -> _ArtifactCopyResult:
        """Send ``CopyArtifactsAsync`` and decode its committed mappings."""
        try:
            result = await self._rpc.rpc_call(
                RPCMethod.COPY_ARTIFACTS,
                build_copy_artifacts_params(list(artifact_ids), target_notebook_id),
                source_path=f"/notebook/{notebook_id}",
                allow_null=True,
                raise_on_null_status=True,
                disable_internal_retries=True,
            )
        except (NetworkError, RateLimitError, ServerError) as exc:
            rpc_code = exc.rpc_code if isinstance(exc, RPCError) else None
            raise unresolved_commit_error(
                RPCMethod.COPY_ARTIFACTS,
                "CopyArtifactsAsync",
                RPCError(
                    "UNRESOLVED — CopyArtifactsAsync may have committed before its "
                    "response was lost. Do not blindly retry; list the target notebook's "
                    "artifacts and reconcile first.",
                    method_id=RPCMethod.COPY_ARTIFACTS.value,
                    rpc_code=rpc_code,
                ),
                preserve_exception=True,
            ) from exc

        rows = unwrap_mapping_rows(
            result, method_id=RPCMethod.COPY_ARTIFACTS.value, source="CopyArtifactsAsync"
        )
        # A malformed entry is logged and skipped rather than aborting the
        # decode: the well-formed entries are the only proof of copies that have
        # already committed, and dropping them would hide committed writes.
        copied: builtins.list[CopiedArtifact] = []
        malformed = 0
        for raw in rows:
            row = CopiedArtifactRow(raw)
            artifact = (
                _artifact_rows.decode_artifact(Artifact, row.artifact_row)
                if row.is_well_formed and row.artifact_row is not None
                else None
            )
            if row.original_id is None or artifact is None or not artifact.id:
                malformed += 1
                logger.warning(
                    "CopyArtifactsAsync returned a malformed mapping entry: %s",
                    reprlib.repr(raw),
                )
                continue
            copied.append(CopiedArtifact(original_id=row.original_id, artifact=artifact))

        return _ArtifactCopyResult(
            copied,
            RPCMethod.COPY_ARTIFACTS.value,
            malformed_count=malformed,
            raw_response=reprlib.repr(rows) if malformed else None,
        )

    async def _read_customization_choices(
        self, notebook_id: str | None = None
    ) -> ArtifactCustomizationChoices:
        """Read and decode the Web customization table."""
        # ``allow_null=False``: the server always serves the table, so a null
        # (status-bearing or not) is drift / rejection, never "no choices".
        result = await self._rpc.rpc_call(
            RPCMethod.GET_CUSTOMIZATION_CHOICES,
            build_customization_choices_params(notebook_id),
            source_path=f"/notebook/{notebook_id}" if notebook_id else "/",
            allow_null=False,
        )
        view = unwrap_customization_choices(
            result,
            method_id=RPCMethod.GET_CUSTOMIZATION_CHOICES.value,
            source="get_customization_choices",
        )

        def _choices(rows: Any) -> tuple[CustomizationChoice, ...]:
            return tuple(
                CustomizationChoice(code=row.code, title=row.title, description=row.description)
                for row in rows
                if row.is_well_formed and row.code is not None
            )

        return ArtifactCustomizationChoices(
            audio=_choices(view.audio_rows),
            video=_choices(view.video_rows),
            slide_deck=_choices(view.slide_deck_rows),
            reports=tuple(
                ReportPreset(
                    report_type=row.report_type,
                    description=row.description,
                    directive=row.directive,
                )
                for row in view.report_rows
                if row.is_well_formed
            ),
        )

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _call_generate(
        self,
        notebook_id: str,
        params: builtins.list[Any],
        *,
        null_result_artifact_type: str | None = None,
    ) -> GenerationStatus:
        """Make a generation RPC call with error handling.

        Facade hop: tests call ``api._call_generate(...)`` directly; the
        implementation lives on :class:`ArtifactGenerationService`.
        """
        return await self._generation._call_generate(
            notebook_id,
            params,
            null_result_artifact_type=null_result_artifact_type,
        )

    async def _list_mind_maps(self, notebook_id: str) -> builtins.list[Any]:
        """Get raw mind-map rows via the injected mind-map facade."""
        return await self._mind_maps.list_mind_maps(notebook_id)

    async def _list_raw(self, notebook_id: str) -> builtins.list[Any]:
        """Get raw artifact list data."""
        # Keep this facade hop so callers/tests that patch ``api._list_raw``
        # still affect public listing paths that delegate into the service.
        return await self._listing.list_raw(notebook_id, rpc=self._rpc)

    async def _list_studio(
        self,
        notebook_id: str,
        task_id: str,
    ) -> builtins.list[Artifact]:
        """Return the target poll projection without querying note-backed rows."""
        return await self._listing.list_studio(
            notebook_id,
            task_id,
            list_raw=self._list_raw,
        )

    def _select_artifact(
        self,
        candidates: builtins.list[Any],
        artifact_id: str | None,
        type_name: str,
        no_result_error_key: str,
        *,
        type_code: ArtifactTypeCode,
    ) -> Any:
        """Select an artifact from candidates by ID, or return latest completed.

        Single point of completed-artifact selection: filters the raw
        ``_list_raw`` list to entries matching ``type_code`` with status
        ``COMPLETED``, then applies the explicit-ID or latest-timestamp rule.

        The length guard requires only ``len(a) > 4`` — the minimum to read
        ``a[2]`` (type) and ``a[4]`` (status). A completed-but-too-short
        artifact passes here and surfaces as ``ArtifactParseError`` from the
        downstream extractor rather than ``ArtifactNotReadyError`` from this
        filter (downstream wraps ``IndexError``/``TypeError`` into
        ``ArtifactParseError``). ``no_result_error_key`` is *not* in general
        ``type_name.lower()`` — ``download_video`` passes ``"video_overview"``
        to preserve historical exception keys.

        Raises:
            ArtifactNotReadyError: If no candidate is found after filtering.
        """
        return self._listing.select_artifact(
            candidates,
            artifact_id,
            type_name,
            no_result_error_key,
            type_code=type_code,
        )

    def _parse_generation_result(
        self,
        result: Any,
        *,
        method_id: str,
        source: str = "_parse_generation_result",
    ) -> GenerationStatus:
        """Parse a generation result into GenerationStatus.

        Facade hop: tests call ``api._parse_generation_result(...)`` directly;
        the implementation lives on :class:`ArtifactGenerationService`.
        """
        return self._generation._parse_generation_result(result, method_id=method_id, source=source)

    def _get_artifact_type_name(self, artifact_type: int) -> str:
        """Human-readable name for an ``ArtifactTypeCode``, else the raw int as str."""
        return _artifact_polling._get_artifact_type_name(artifact_type)

    def _is_media_ready(self, art: builtins.list[Any], artifact_type: int) -> bool:
        """Check if a media artifact's download URLs are populated.

        For media artifacts (audio, video, infographic, slide deck) the API may
        set status=COMPLETED before the URLs are populated; this verifies they
        are available. Returns ``True`` for non-media types and (defensively)
        on unexpected structure.

        Positional URL locations (BATCHEXECUTE rows): ``art[6][5]`` audio URL
        list, ``art[8][i][0][0]`` video URL string (nested variants/entries),
        ``art[16][3]`` slide-deck PDF URL.
        """
        try:
            if not isinstance(art, list):
                return artifact_type not in _artifact_rows.ArtifactRow._MEDIA_ARTIFACT_TYPES
            return _artifact_rows.ArtifactRow(art).is_media_ready(artifact_type)
        except (IndexError, TypeError):
            return artifact_type not in _artifact_rows.ArtifactRow._MEDIA_ARTIFACT_TYPES

    @property
    def creation_capabilities(self) -> tuple[ArtifactCreationCapability, ...]:
        capabilities = tuple(
            ArtifactCreationCapability(
                cap.family,
                cap.supported_options,
                ("concept_explanation report format is not supported by Web",),
            )
            if cap.family == "report"
            else cap
            for cap in super().creation_capabilities
        )
        return capabilities + (
            ArtifactCreationCapability(
                "interactive_mind_map",
                ("instructions",),
                ("language is not encoded by the Web interactive mind-map protocol",),
            ),
        )
