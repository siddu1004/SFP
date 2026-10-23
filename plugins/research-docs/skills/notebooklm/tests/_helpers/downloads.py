"""Typed download client doubles shared by adapter contract tests."""

from unittest.mock import AsyncMock, MagicMock

from notebooklm.downloads import DOWNLOAD_REGISTRY, resolve_download_format
from notebooklm.types import (
    Artifact,
    ArtifactDownloadListing,
    ArtifactDownloadRequest,
    ArtifactDownloadSelection,
    ArtifactListing,
)


def configure_complete_artifact_listing(mock_client: MagicMock) -> None:
    """Project ``artifacts.list`` as a complete ``list_with_status`` inventory.

    Fuzzy resolvers require completeness evidence. Tests that override ``list``
    keep working because this wrapper reads the current list mock at call time.
    """

    async def list_with_status(notebook_id, artifact_type=None):
        del artifact_type
        items = await mock_client.artifacts.list(notebook_id)
        return ArtifactListing(items=tuple(items), is_complete=True)

    mock_client.artifacts.list_with_status = AsyncMock(side_effect=list_with_status)


def configure_prepared_artifact_downloads(mock_client: MagicMock) -> None:
    """Install the typed download contract on a client double's artifacts namespace."""

    async def prepare_downloads(request: ArtifactDownloadRequest) -> ArtifactDownloadListing:
        """Project the overridden typed list into public prepared identities."""
        representation, output = resolve_download_format(request.kind, request.output_format)
        artifacts = await mock_client.artifacts.list(request.notebook_id)
        selections = tuple(
            ArtifactDownloadSelection(
                notebook_id=request.notebook_id,
                artifact_id=artifact.id,
                kind=artifact.kind,
                title=artifact.title,
                created_at=artifact.created_at,
                last_modified_at=artifact.last_modified_at,
                representation=representation,
                extension=output.extension,
                mime_type=output.mime_type,
            )
            for artifact in artifacts
            if isinstance(artifact, Artifact)
            and artifact.kind is request.kind
            and artifact.is_completed
        )
        return ArtifactDownloadListing(selections, is_complete=True)

    async def download(selection: ArtifactDownloadSelection, output_path: str) -> str:
        """Bridge typed execution to a test's established per-kind callback."""
        entry = next(item for item in DOWNLOAD_REGISTRY if item.kind is selection.kind)
        legacy = getattr(mock_client.artifacts, entry.download_attr)
        kwargs: dict[str, str] = {"artifact_id": selection.artifact_id}
        if entry.format_kwarg:
            kwargs[entry.format_kwarg] = selection.representation
        return await legacy(selection.notebook_id, output_path, **kwargs)

    mock_client.artifacts.prepare_downloads = AsyncMock(side_effect=prepare_downloads)
    mock_client.artifacts.download = AsyncMock(side_effect=download)
