"""Prepared identities cannot transfer authority between owners or generations."""

from __future__ import annotations

import gc
import weakref
from dataclasses import FrozenInstanceError, replace

import pytest

from notebooklm._artifact.download_selection import PreparedDownloadCache
from notebooklm.downloads import resolve_download_format
from notebooklm.exceptions import ValidationError
from notebooklm.types import Artifact, ArtifactDownloadRequest, ArtifactType


def _audio(*, status: int = 3) -> Artifact:
    return Artifact(
        id="artifact-1",
        title="Audio",
        _artifact_type=1,
        status=status,
        url="https://signed.invalid/private?token=secret",
    )


def test_prepared_selection_keeps_only_public_metadata_and_rejects_other_owner() -> None:
    owner: PreparedDownloadCache[object] = PreparedDownloadCache()
    other: PreparedDownloadCache[object] = PreparedDownloadCache()
    snapshot = object()
    prepared = owner.prepare(
        ArtifactDownloadRequest("nb-1", ArtifactType.AUDIO), _audio(), snapshot, epoch=1
    )
    assert owner.require(prepared, epoch=1) is snapshot
    assert (prepared.artifact_id, prepared.extension, prepared.mime_type) == (
        "artifact-1",
        ".m4a",
        "audio/mp4",
    )
    assert "secret" not in repr(prepared)
    assert "signed.invalid" not in repr(prepared)
    with pytest.raises(ValidationError):
        other.require(prepared, epoch=1)


@pytest.mark.parametrize(
    "changes", [{}, {"notebook_id": "nb-2"}, {"artifact_id": "other"}, {"representation": "mp3"}]
)
def test_reconstructed_or_modified_selection_does_not_authorize_download(
    changes: dict[str, str],
) -> None:
    owner: PreparedDownloadCache[object] = PreparedDownloadCache()
    prepared = owner.prepare(
        ArtifactDownloadRequest("nb-1", ArtifactType.AUDIO), _audio(), object(), epoch=1
    )
    with pytest.raises(ValidationError):
        owner.require(replace(prepared, **changes), epoch=1)
    with pytest.raises(FrozenInstanceError):
        prepared.notebook_id = "nb-2"  # type: ignore[misc]
    # Even bypassing dataclass freezing cannot repurpose the backend snapshot.
    object.__setattr__(prepared, "notebook_id", "nb-2")
    with pytest.raises(ValidationError):
        owner.require(prepared, epoch=1)


def test_reopened_generation_rejects_old_selection_and_accepts_new_one() -> None:
    owner: PreparedDownloadCache[object] = PreparedDownloadCache()
    request = ArtifactDownloadRequest("nb-1", ArtifactType.AUDIO)
    old = owner.prepare(request, _audio(), object(), epoch=1)
    snapshot = object()
    new = owner.prepare(request, _audio(), snapshot, epoch=2)
    with pytest.raises(ValidationError):
        owner.require(old, epoch=2)
    assert owner.require(new, epoch=2) is snapshot


def test_releasing_selection_releases_private_snapshot() -> None:
    class Snapshot:
        pass

    owner: PreparedDownloadCache[Snapshot] = PreparedDownloadCache()
    snapshot = Snapshot()
    reference = weakref.ref(snapshot)
    prepared = owner.prepare(
        ArtifactDownloadRequest("nb-1", ArtifactType.AUDIO), _audio(), snapshot, epoch=1
    )
    del snapshot
    gc.collect()
    assert reference() is not None
    del prepared
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("status", [1, 2, 4, 5])
def test_incomplete_artifacts_cannot_be_prepared(status: int) -> None:
    owner: PreparedDownloadCache[object] = PreparedDownloadCache()
    with pytest.raises(ValidationError):
        owner.prepare(
            ArtifactDownloadRequest("nb-1", ArtifactType.AUDIO),
            _audio(status=status),
            object(),
            epoch=1,
        )


@pytest.mark.parametrize(
    "kind,representation,extension,mime",
    [
        (ArtifactType.AUDIO, None, ".m4a", "audio/mp4"),
        (
            ArtifactType.SLIDE_DECK,
            "pptx",
            ".pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        (ArtifactType.QUIZ, "markdown", ".md", "text/markdown"),
        (ArtifactType.FLASHCARDS, "html", ".html", "text/html"),
    ],
)
def test_representation_resolves_actual_extension_and_mime(
    kind: ArtifactType, representation: str | None, extension: str, mime: str
) -> None:
    _, resolved = resolve_download_format(kind, representation)
    assert (resolved.extension, resolved.mime_type) == (extension, mime)


@pytest.mark.parametrize(
    "kind,representation",
    [(ArtifactType.AUDIO, "mp3"), (ArtifactType.QUIZ, "pdf"), (ArtifactType.UNKNOWN, None)],
)
def test_unsupported_representations_fail_before_preparation(
    kind: ArtifactType, representation: str | None
) -> None:
    with pytest.raises(ValidationError):
        resolve_download_format(kind, representation)
