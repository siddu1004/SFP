from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest

from notebooklm import Artifact, UnknownTypeWarning
from notebooklm._types.artifacts import _warned_artifact_types
from tests.e2e import conftest as e2e
from tests.e2e._artifact_helpers import (
    completed_download_candidates,
    completed_interactive_mind_maps,
    studio_item_may_have_download_payload,
)
from tests.e2e._mcp_live_helpers import (
    is_android_inventory_only_slide_failure,
    pick_downloadable_artifact,
    structured_failure_detail,
)

MANAGED = {
    "NOTEBOOKLM_E2E_MANAGED_COPIES": "1",
    "NOTEBOOKLM_E2E_MANAGED_MODE": "full",
    "NOTEBOOKLM_E2E_REFERENCE_PREPARED": "1",
    "NOTEBOOKLM_READ_ONLY_NOTEBOOK_ID": "reference-role",
    "NOTEBOOKLM_GENERATION_NOTEBOOK_ID": "generation-role",
    "NOTEBOOKLM_MULTI_SOURCE_NOTEBOOK_ID": "generation-role",
}


def install(monkeypatch, **overrides: str | None) -> None:
    for name, value in {**MANAGED, **overrides}.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def test_managed_full_requires_reference_and_shared_mutable_workspace(monkeypatch) -> None:
    install(monkeypatch)
    assert e2e._managed_bindings() == {
        "NOTEBOOKLM_READ_ONLY_NOTEBOOK_ID": "reference-role",
        "NOTEBOOKLM_GENERATION_NOTEBOOK_ID": "generation-role",
        "NOTEBOOKLM_MULTI_SOURCE_NOTEBOOK_ID": "generation-role",
    }
    for overrides in (
        {"NOTEBOOKLM_E2E_MANAGED_COPIES": "true"},
        {"NOTEBOOKLM_E2E_MANAGED_MODE": "rpc"},
        {"NOTEBOOKLM_E2E_REFERENCE_PREPARED": None},
        {"NOTEBOOKLM_GENERATION_NOTEBOOK_ID": None},
        {"NOTEBOOKLM_MULTI_SOURCE_NOTEBOOK_ID": "multi-source-role"},
        {"NOTEBOOKLM_READ_ONLY_NOTEBOOK_ID": "generation-role"},
    ):
        install(monkeypatch, **overrides)
        with pytest.raises(ValueError):
            e2e._managed_bindings()


@pytest.mark.asyncio
async def test_managed_role_fixtures_do_not_touch_cache_create_cleanup_or_client(
    monkeypatch,
) -> None:
    install(monkeypatch)

    class ExplodingClient:
        def __getattr__(self, name):
            raise AssertionError(f"managed fixture touched client.{name}")

    generation = e2e.generation_notebook_id.__wrapped__(ExplodingClient())
    assert await anext(generation) == "generation-role"
    with pytest.raises(StopAsyncIteration):
        await anext(generation)

    multi_source = e2e.multi_source_notebook_id.__wrapped__(ExplodingClient())
    assert await anext(multi_source) == "generation-role"
    with pytest.raises(StopAsyncIteration):
        await anext(multi_source)


def test_read_only_fixture_uses_managed_reference(monkeypatch) -> None:
    install(monkeypatch)
    assert e2e.read_only_notebook_id.__wrapped__() == "reference-role"


def test_managed_readonly_mode_requires_only_the_prepared_reference(monkeypatch) -> None:
    install(
        monkeypatch,
        NOTEBOOKLM_E2E_MANAGED_MODE="readonly",
        NOTEBOOKLM_GENERATION_NOTEBOOK_ID=None,
        NOTEBOOKLM_MULTI_SOURCE_NOTEBOOK_ID=None,
    )
    assert e2e._managed_bindings() == {"NOTEBOOKLM_READ_ONLY_NOTEBOOK_ID": "reference-role"}
    assert e2e.read_only_notebook_id.__wrapped__() == "reference-role"


def test_managed_mind_map_download_selects_only_completed_interactive_artifacts() -> None:
    processing = SimpleNamespace(is_interactive_mind_map=True, is_completed=False)
    completed = SimpleNamespace(is_interactive_mind_map=True, is_completed=True)
    completed_other_kind = SimpleNamespace(is_interactive_mind_map=False, is_completed=True)

    assert completed_interactive_mind_maps([processing, completed, completed_other_kind]) == [
        completed
    ]


def test_url_backed_download_selectors_reject_inventory_only_artifacts() -> None:
    inventory_only = SimpleNamespace(kind="audio", is_completed=True, url=None, id="inventory-only")
    processing = SimpleNamespace(kind="audio", is_completed=False, url="https://asset.test")
    downloadable = SimpleNamespace(
        kind="audio", is_completed=True, url="https://asset.test", id="downloadable"
    )

    assert completed_download_candidates(
        [inventory_only, processing, downloadable], "audio", backend="web"
    ) == [downloadable]
    assert completed_download_candidates(
        [inventory_only, processing, downloadable], "audio", backend="android"
    ) == [downloadable]
    assert (
        studio_item_may_have_download_payload(
            {"type": "audio", "status_label": "completed", "url": None}, backend="web"
        )
        is False
    )
    assert (
        studio_item_may_have_download_payload(
            {"type": "audio", "status_label": "completed", "url": "https://asset.test"},
            backend="android",
        )
        is True
    )
    assert (
        studio_item_may_have_download_payload(
            {"type": "report", "status_label": "completed", "url": None}, backend="web"
        )
        is True
    )


def test_download_selector_skips_unclassified_type4_before_kind() -> None:
    legacy = Artifact(id="legacy-type4", title="Legacy", _artifact_type=4, status=3)
    downloadable = SimpleNamespace(
        kind="audio", is_completed=True, url="https://asset.test", id="downloadable"
    )
    _warned_artifact_types.discard((4, None))

    with warnings.catch_warnings():
        warnings.simplefilter("error", UnknownTypeWarning)
        candidates = completed_download_candidates([legacy, downloadable], "audio", backend="web")

    assert candidates == [downloadable]


def test_android_slide_deck_download_selectors_allow_backend_hydration() -> None:
    inventory_only = SimpleNamespace(
        kind="slide_deck", is_completed=True, url=None, id="inventory-only"
    )
    downloadable = SimpleNamespace(
        kind="slide_deck", is_completed=True, url="https://asset.test", id="downloadable"
    )

    assert completed_download_candidates([inventory_only], "slide_deck", backend="web") == []
    assert completed_download_candidates(
        [inventory_only, downloadable], "slide_deck", backend="android"
    ) == [
        downloadable,
        inventory_only,
    ]
    item = {"type": "slide-deck", "status_label": "completed", "url": None}
    assert studio_item_may_have_download_payload(item, backend="web") is False
    assert studio_item_may_have_download_payload(item, backend="android") is True


def test_android_mcp_selector_prefers_confirmed_payload_before_slide_hydration() -> None:
    fallback = {"id": "fallback", "type": "slide-deck", "status_label": "completed"}
    confirmed = {
        "id": "confirmed",
        "type": "audio",
        "status_label": "completed",
        "url": "https://asset.test",
    }

    assert pick_downloadable_artifact([fallback, confirmed], backend="android") is confirmed
    assert pick_downloadable_artifact([fallback], backend="android") is fallback


def test_android_inventory_only_slide_recognizes_typed_mcp_failure() -> None:
    result = {
        "outcome": "error",
        "failure": {
            "reason": "download_failed",
            "detail": "Failed to download slide_deck: PDF URL not available in artifact data",
        },
        "error": "obsolete flat field must not be consulted",
    }

    assert structured_failure_detail(result) == result["failure"]["detail"]
    assert is_android_inventory_only_slide_failure(
        result,
        backend="android",
        artifact_type="slide-deck",
    )


@pytest.mark.parametrize(
    ("result", "backend", "artifact_type"),
    [
        (
            {
                "outcome": "error",
                "failure": {"detail": "PDF URL not available in artifact data"},
            },
            "web",
            "slide-deck",
        ),
        (
            {
                "outcome": "error",
                "failure": {"detail": "PDF URL not available in artifact data"},
            },
            "android",
            "audio",
        ),
        (
            {
                "outcome": "success",
                "failure": {"detail": "PDF URL not available in artifact data"},
            },
            "android",
            "slide-deck",
        ),
        (
            {"outcome": "error", "error": "PDF URL not available in artifact data"},
            "android",
            "slide-deck",
        ),
        (
            {"outcome": "error", "failure": {"detail": "some other failure"}},
            "android",
            "slide-deck",
        ),
        (
            {
                "outcome": "error",
                "failure": {"detail": "PDF URL not available in artifact data"},
            },
            "android",
            "slide-deck",
        ),
        (
            {
                "outcome": "error",
                "failure": {
                    "reason": "authentication",
                    "detail": "PDF URL not available in artifact data",
                },
            },
            "android",
            "slide-deck",
        ),
    ],
    ids=(
        "web-backend",
        "non-slide-artifact",
        "success-outcome",
        "legacy-flat-error",
        "different-detail",
        "missing-failure-reason",
        "wrong-failure-reason",
    ),
)
def test_android_inventory_only_slide_preserves_nonmatching_failures(
    result: dict[str, object],
    backend: str,
    artifact_type: str,
) -> None:
    assert not is_android_inventory_only_slide_failure(
        result,
        backend=backend,
        artifact_type=artifact_type,
    )


def test_unmanaged_configuration_preserves_legacy_path(monkeypatch) -> None:
    for name in MANAGED:
        monkeypatch.delenv(name, raising=False)
    assert e2e._managed_bindings() is None


def test_managed_controls_without_activation_fail_closed(monkeypatch) -> None:
    for name in MANAGED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NOTEBOOKLM_E2E_MANAGED_MODE", "full")
    with pytest.raises(ValueError, match="without the activation"):
        e2e._managed_bindings()

    monkeypatch.delenv("NOTEBOOKLM_E2E_MANAGED_MODE")
    monkeypatch.setenv("NOTEBOOKLM_E2E_REFERENCE_PREPARED", "1")
    with pytest.raises(ValueError, match="without the activation"):
        e2e._managed_bindings()


def test_unconfigure_resets_first_use_cleanup_state() -> None:
    e2e._generation_cleanup_done = True
    e2e._multi_source_cleanup_done = True
    e2e.pytest_unconfigure(None)
    assert e2e._generation_cleanup_done is False
    assert e2e._multi_source_cleanup_done is False
