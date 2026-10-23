"""Per-backend weak ownership of prepared download state.

A caller retains only an immutable public identity. Backend-specific snapshots
stay local to the backend instance and expire when that identity is released.
Generation changes invalidate all retained snapshots before another use.
"""

from __future__ import annotations

from dataclasses import astuple, dataclass
from typing import Generic, TypeVar
from weakref import WeakKeyDictionary

from .._types.artifact_download import ArtifactDownloadRequest, ArtifactDownloadSelection
from .._types.artifacts import Artifact
from ..downloads import resolve_download_format
from ..exceptions import ValidationError

_Snapshot = TypeVar("_Snapshot")


@dataclass(frozen=True)
class _PreparedState(Generic[_Snapshot]):
    fields: tuple[object, ...]
    snapshot: _Snapshot


class PreparedDownloadCache(Generic[_Snapshot]):
    """Opaque ownership checks independent of Web/Android snapshot shapes."""

    def __init__(self) -> None:
        self._epoch: int | None = None
        self._entries: WeakKeyDictionary[ArtifactDownloadSelection, _PreparedState[_Snapshot]] = (
            WeakKeyDictionary()
        )

    def _bind_epoch(self, epoch: int) -> None:
        if self._epoch != epoch:
            self._entries.clear()
            self._epoch = epoch

    @staticmethod
    def validate_request(request: ArtifactDownloadRequest) -> None:
        """Reject invalid inputs before fetching even an empty candidate list."""
        if not request.notebook_id or not request.notebook_id.strip():
            raise ValidationError("Notebook ID cannot be empty")
        resolve_download_format(request.kind, request.output_format)

    def prepare(
        self,
        request: ArtifactDownloadRequest,
        artifact: Artifact,
        snapshot: _Snapshot,
        *,
        epoch: int,
    ) -> ArtifactDownloadSelection:
        self._bind_epoch(epoch)
        if not request.notebook_id or not request.notebook_id.strip():
            raise ValidationError("Notebook ID cannot be empty")
        if artifact.kind != request.kind or not artifact.is_completed:
            raise ValidationError(
                "Only completed artifacts matching the requested kind can be prepared"
            )
        representation, output = resolve_download_format(request.kind, request.output_format)
        selection = ArtifactDownloadSelection(
            notebook_id=request.notebook_id,
            artifact_id=artifact.id,
            kind=artifact.kind,
            title=artifact.title,
            created_at=artifact.created_at,
            representation=representation,
            extension=output.extension,
            mime_type=output.mime_type,
            last_modified_at=artifact.last_modified_at,
        )
        self._entries[selection] = _PreparedState(fields=astuple(selection), snapshot=snapshot)
        return selection

    def require(self, selection: ArtifactDownloadSelection, *, epoch: int) -> _Snapshot:
        self._bind_epoch(epoch)
        if not isinstance(selection, ArtifactDownloadSelection):
            raise ValidationError("Expected a prepared artifact download selection")
        state = self._entries.get(selection)
        if state is None or astuple(selection) != state.fields:
            raise ValidationError(
                "Download selection does not belong to this client and generation"
            )
        return state.snapshot
