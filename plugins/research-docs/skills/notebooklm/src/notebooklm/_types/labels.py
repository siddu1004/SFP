"""Pure-value type for a NotebookLM source label.

Re-exported from ``notebooklm.types``. A source ``Label`` describes source
membership only — **no ``kind``, no ``artifact_ids``** (a future artifact-label
surface is a separate type).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .._deprecation import warn_registered_deprecation


@dataclass
class Label:
    """A NotebookLM source label (a topic grouping of sources).

    Notebook-scoped. Membership is many-to-many: a source may belong to multiple
    labels, and a label owns a list of source IDs (the source carries no
    back-reference).
    """

    id: str
    name: str
    notebook_id: str | None = None
    emoji: str | None = None
    # Source UUIDs in this label. Empty for a freshly-created (still empty) label.
    source_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_api_response(
        cls,
        data: list[Any],
        *,
        notebook_id: str | None = None,
        method_id: str | None = None,
    ) -> Label:
        """Parse one label 4-tuple ``[name, sources, label_id, emoji]``.

        .. deprecated:: 0.9.0
           Use ``client.labels`` typed APIs. Raw Web row decoding has no
           supported public replacement.
        """
        warn_registered_deprecation("label_from_api_response")
        from .._web.rows.labels import decode_label

        return decode_label(
            cls,
            data,
            notebook_id=notebook_id,
            method_id=method_id,
        )
