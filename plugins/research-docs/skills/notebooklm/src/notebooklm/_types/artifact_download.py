"""Public immutable inputs and identities for prepared artifact downloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .artifacts import ArtifactListingFailure, ArtifactType


@dataclass(frozen=True)
class ArtifactDownloadRequest:
    """Select completed artifacts of one kind in a notebook.

    ``output_format=None`` selects the documented per-kind default. Backend
    preparation validates format support before fetching artifacts.
    """

    notebook_id: str
    kind: ArtifactType
    output_format: str | None = None


@dataclass(frozen=True, eq=False)
class ArtifactDownloadSelection:
    """An opaque prepared identity plus metadata for naming and presentation.

    Only the backend that prepared this exact object can consume it, within the
    same client generation. Reconstructing or copying its fields does not create
    an authorized selection. No cookies, URLs, raw rows, or protobufs are exposed.
    """

    notebook_id: str
    artifact_id: str
    kind: ArtifactType
    title: str
    created_at: datetime | None
    representation: str
    extension: str
    mime_type: str
    last_modified_at: datetime | None = None


@dataclass(frozen=True)
class ArtifactDownloadListing:
    """Prepared completed candidates with the aggregate read's completeness.

    An exact positive identity can remain usable when another backing failed.
    Absence, partial identifiers, names, or selection across the whole listing
    require completeness. The application owns naming and destination policy.
    """

    selections: tuple[ArtifactDownloadSelection, ...]
    is_complete: bool
    failures: tuple[ArtifactListingFailure, ...] = ()
