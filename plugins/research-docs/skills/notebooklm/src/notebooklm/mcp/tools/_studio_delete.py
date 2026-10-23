"""Explicit-subset Studio deletion with a single write for text notes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..._app import artifacts as artifact_core
from ..._app.resolve import FULL_ID_PATTERN, validate_id
from ...exceptions import ValidationError
from ...options import USE_DEFAULT
from .._coerce import coerce_list
from .._confirm import needs_confirmation
from .._resolve import reject_non_canonical_id
from ._studio_items import partition_studio_refs, studio_items

if TYPE_CHECKING:
    from ...client import NotebookLMClient

MAX_DELETE_STUDIO_ITEMS = 100


def validate_delete_refs(
    item: str | None, items: list[str] | str | None, *, confirm: bool
) -> list[str] | None:
    """Reject malformed batches before opening the client or resolving names."""
    refs = coerce_list(items)
    if (item is None) == (refs is None):
        raise ValidationError("Provide either 'item' (one) or 'items' (a subset), not both")
    if refs is None:
        return None
    if not refs or len(refs) > MAX_DELETE_STUDIO_ITEMS:
        raise ValidationError(f"'items' must contain 1 to {MAX_DELETE_STUDIO_ITEMS} refs")
    refs = [validate_id(ref, "item") for ref in refs]
    for ref in refs:
        if confirm and not FULL_ID_PATTERN.fullmatch(ref):
            raise ValidationError(
                "confirm=True requires canonical item ids returned by the preview; "
                "names and prefixes can resolve to different items"
            )
        reject_non_canonical_id(ref, "studio item")
    return refs


async def delete_studio_items(
    client: NotebookLMClient, notebook_id: str, refs: list[str], *, confirm: bool
) -> dict[str, Any]:
    """Partition one snapshot, batch text notes, and route each artifact by kind."""
    async with client.operation(timeout=USE_DEFAULT):
        resolved, not_found = partition_studio_refs(
            refs, await studio_items(client, notebook_id, require_complete=True)
        )
        if not confirm:
            return needs_confirmation(
                {
                    "action": "delete_studio_items",
                    "notebook_id": notebook_id,
                    "count": len(resolved),
                    "items": [
                        {"item_id": item.item_id, "type": item.type, "title": item.title}
                        for item in resolved
                    ],
                    "not_found": not_found,
                }
            )

        # Only text notes enter the bulk note request. In particular, interactive
        # mind maps stay on DELETE_ARTIFACT; note-backed maps use the existing
        # kind-aware artifact core and are cleared only when explicitly selected.
        note_ids = [item.item_id for item in resolved if item.type == "note"]
        if note_ids:
            await client.notes.delete(notebook_id, note_ids)
        deleted: list[dict[str, Any]] = []
        for item in resolved:
            was_note_backed = False
            if item.type != "note":
                was_note_backed = await artifact_core.delete_artifact(
                    client, notebook_id, item.item_id
                )
            deleted.append(
                {"item_id": item.item_id, "type": item.type, "was_note_backed": was_note_backed}
            )
        return {
            "status": "deleted",
            "notebook_id": notebook_id,
            "deleted": deleted,
            "deleted_count": len(deleted),
            "not_found": not_found,
            "not_found_count": len(not_found),
            "total_count": len(deleted) + len(not_found),
        }
