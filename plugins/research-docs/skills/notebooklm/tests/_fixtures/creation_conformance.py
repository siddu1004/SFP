"""Injected protocol terminals for the shared creation contract matrix."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from notebooklm._android.artifact_creation import CREATE_ARTIFACT_METHOD as CREATE_ARTIFACT_METHOD
from notebooklm._android.artifact_proto import ARTIFACTS_PROTO as PROTO
from notebooklm._android.artifacts import AndroidArtifactsAPI
from notebooklm._android.mind_maps import AndroidMindMapsAPI
from notebooklm._idempotency import bound_operation_journal_entries
from notebooklm._notes import NotesAPI
from notebooklm._web.mind_maps import WebMindMapsAPI
from notebooklm.types import Artifact, GenerationStatus, MindMapResult
from tests._fixtures.fake_core import declared_noop_operation_scope, make_fake_core


class AndroidTerminal:
    operation_scope = staticmethod(declared_noop_operation_scope)

    def __init__(self):
        self.responses = {}
        self.calls = []

    async def unary(self, method, request, **kwargs):
        for entry in bound_operation_journal_entries():
            entry.mark_dispatched()
        self.calls.append((method, request, kwargs))
        return self.responses[method]


class Notebooks:
    def __init__(self):
        self.source_ids = ["resolved"]
        self.calls = []

    async def get_source_ids(self, notebook_id):
        self.calls.append(notebook_id)
        return list(self.source_ids)


def android_artifacts_graph():
    terminal = AndroidTerminal()
    notebooks = Notebooks()
    mind_maps, assets = MagicMock(), MagicMock()
    api = AndroidArtifactsAPI(
        session=terminal,
        supervisor=make_fake_core(),
        notebooks=notebooks,
        mind_maps=mind_maps,
        asset_downloads=assets,
    )
    return terminal, notebooks, mind_maps, assets, api


def artifact_proto(artifact_id, *, type_code, variant=None, status):
    artifact = PROTO.Artifact(artifact_id=artifact_id, type=type_code, status=status)
    if type_code == PROTO.ARTIFACT_TYPE_APP:
        artifact.app.generation_options.app_type = variant
    return artifact


def interactive_artifact(artifact_id):
    return Artifact(id=artifact_id, title="Interactive", _artifact_type=4, status=3, _variant=4)


def android_mind_maps_graph(*, artifacts):
    notes = MagicMock(spec=NotesAPI)
    notes.configure_mock(_list_note_backed_mind_maps=AsyncMock(return_value=[]))
    artifact_api = MagicMock(spec=AndroidArtifactsAPI)
    artifact_api.configure_mock(
        list=AsyncMock(return_value=artifacts),
        _list_all_studio=AsyncMock(return_value=artifacts),
        wait_for_completion=AsyncMock(
            return_value=GenerationStatus(task_id="created", status="completed")
        ),
        generate_mind_map=AsyncMock(
            return_value=MindMapResult(mind_map={"name": "Root"}, note_id="note")
        ),
        _generate_interactive_mind_map=AsyncMock(
            return_value=GenerationStatus(task_id="created", status="pending")
        ),
        _get_interactive_mind_map_tree=AsyncMock(return_value={"name": "Interactive"}),
    )
    return (
        AndroidMindMapsAPI(session=AndroidTerminal(), artifacts=artifact_api, notes=notes),
        artifact_api,
        notes,
    )


def web_mind_maps_graph(*, interactive):
    rpc = MagicMock(rpc_call=AsyncMock(return_value=None))
    mind_maps = MagicMock(list_mind_maps=AsyncMock(return_value=[]))
    artifacts = MagicMock(
        list=AsyncMock(return_value=interactive),
        wait_for_completion=AsyncMock(
            return_value=GenerationStatus(task_id="created", status="completed")
        ),
        generate_mind_map=AsyncMock(),
    )
    notebooks = MagicMock(get_source_ids=AsyncMock(return_value=["s"]))
    api = WebMindMapsAPI(
        rpc=rpc,
        supervisor=make_fake_core(),
        mind_maps=mind_maps,
        artifacts=artifacts,
        notebooks=notebooks,
        notes=MagicMock(),
    )
    return api, rpc, mind_maps, artifacts, notebooks
