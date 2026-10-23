"""Narrow collaborator protocols used by the Android artifact adapter."""

from __future__ import annotations

import builtins
from typing import Protocol

from ..types import Artifact, MindMap


class NoteBackedMindMapLister(Protocol):
    async def list_mind_map_artifacts_with_content(
        self, notebook_id: str
    ) -> tuple[builtins.list[Artifact], builtins.list[MindMap]]: ...

    async def list_mind_map_artifacts(self, notebook_id: str) -> builtins.list[Artifact]: ...

    async def list_note_backed_mind_maps(self, notebook_id: str) -> builtins.list[MindMap]: ...


__all__ = ["NoteBackedMindMapLister"]
