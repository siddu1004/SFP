"""Deprecation runway for the nine public Web-row decoder shims."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

import pytest

from notebooklm._web.rows.artifacts import decode_artifact, decode_mind_map_artifact
from notebooklm._web.rows.collections import decode_collection
from notebooklm._web.rows.labels import decode_label
from notebooklm._web.rows.notebooks import decode_notebook
from notebooklm._web.rows.sharing import decode_share_status, decode_shared_user
from notebooklm._web.rows.source_models import decode_source, source_from_row
from notebooklm._web.rows.sources import SourceRow
from notebooklm.types import Artifact, Collection, Label, Notebook, SharedUser, ShareStatus, Source

_SOURCE_ROW = SourceRow.from_unknown_shape(["src-1", "Source title"])

_CASES: tuple[tuple[str, Callable[[], Any], Callable[[], Any]], ...] = (
    (
        "Artifact.from_api_response",
        lambda: Artifact.from_api_response(["art-1", "Artifact", 1, None, 3]),
        lambda: decode_artifact(Artifact, ["art-1", "Artifact", 1, None, 3]),
    ),
    (
        "Artifact.from_mind_map",
        lambda: Artifact.from_mind_map(["map-1", None, 2]),
        lambda: decode_mind_map_artifact(Artifact, ["map-1", None, 2]),
    ),
    (
        "Collection.from_api_response",
        lambda: Collection.from_api_response(["Collection", None, "collection-1", ""]),
        lambda: decode_collection(Collection, ["Collection", None, "collection-1", ""]),
    ),
    (
        "Label.from_api_response",
        lambda: Label.from_api_response(["Label", None, "label-1", ""]),
        lambda: decode_label(Label, ["Label", None, "label-1", ""]),
    ),
    (
        "Notebook.from_api_response",
        lambda: Notebook.from_api_response(["Notebook", [], "notebook-1", "📓"]),
        lambda: decode_notebook(Notebook, ["Notebook", [], "notebook-1", "📓"]),
    ),
    (
        "ShareStatus.from_api_response",
        lambda: ShareStatus.from_api_response([[], None], "notebook-1"),
        lambda: decode_share_status(ShareStatus, [[], None], "notebook-1"),
    ),
    (
        "SharedUser.from_api_response",
        lambda: SharedUser.from_api_response(["user@example.com", 1]),
        lambda: decode_shared_user(SharedUser, ["user@example.com", 1]),
    ),
    (
        "Source.from_api_response",
        lambda: Source.from_api_response(["src-1", "Source title"]),
        lambda: decode_source(Source, ["src-1", "Source title"]),
    ),
    (
        "Source.from_row",
        lambda: Source.from_row(_SOURCE_ROW),
        lambda: source_from_row(Source, _SOURCE_ROW),
    ),
)


@pytest.mark.parametrize(("surface", "public_call", "web_call"), _CASES)
def test_public_decoder_warns_at_caller_and_matches_web_constructor(
    surface: str,
    public_call: Callable[[], Any],
    web_call: Callable[[], Any],
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = public_call()

    assert result == web_call()
    assert len(caught) == 1
    assert str(caught[0].message).startswith(f"{surface}(...) is deprecated")
    assert caught[0].filename == __file__
    assert caught[0].lineno == public_call.__code__.co_firstlineno


@pytest.mark.parametrize(("_surface", "_public_call", "web_call"), _CASES)
def test_web_owned_constructors_do_not_warn(
    _surface: str,
    _public_call: Callable[[], Any],
    web_call: Callable[[], Any],
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        web_call()


def test_source_api_decoder_preserves_subclass_from_row_override() -> None:
    """The deprecated facade retains its historical subclass extension point."""
    seen: list[SourceRow] = []

    class CustomSource(Source):
        @classmethod
        def from_row(cls, row: SourceRow) -> Source:
            seen.append(row)
            return cls(id=row.id, title=f"custom:{row.title}")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = CustomSource.from_api_response(["src-custom", "Source title"])

    assert result == CustomSource(id="src-custom", title="custom:Source title")
    assert seen == [SourceRow.from_unknown_shape(["src-custom", "Source title"])]
    assert len(caught) == 1
    assert caught[0].filename == __file__


def test_source_api_decoder_super_from_row_override_warns_once() -> None:
    """Delegating subclass overrides do not repeat the public warning."""

    class DelegatingSource(Source):
        @classmethod
        def from_row(cls, row: SourceRow) -> Source:
            return super().from_row(row)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = DelegatingSource.from_api_response(["src-delegating", "Source title"])

    assert isinstance(result, DelegatingSource)
    assert (result.id, result.title) == ("src-delegating", "Source title")
    assert len(caught) == 1
    assert str(caught[0].message).startswith("Source.from_api_response(...) is deprecated")

    with warnings.catch_warnings(record=True) as direct_caught:
        warnings.simplefilter("always")
        direct_result = DelegatingSource.from_row(_SOURCE_ROW)

    assert isinstance(direct_result, DelegatingSource)
    assert (direct_result.id, direct_result.title) == ("src-1", "Source title")
    assert len(direct_caught) == 1
    assert str(direct_caught[0].message).startswith("Source.from_row(...) is deprecated")
