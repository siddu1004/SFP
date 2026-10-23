"""Transport-neutral ``source clean`` business logic.

This is the Click-free core behind ``source clean`` (imported directly by the
``cli/source_cmd.py`` / ``cli/_source_render.py`` command layer): it owns the
pure orchestration of source cleanup (classifying junk sources, batched
deletion, returning a typed :class:`SourceCleanResult`). Presentation (Rich
text vs. JSON envelope), confirmation prompting, and exit-code policy live in
the Click command layer (:mod:`notebooklm.cli.source_cmd`).

This module is transport-neutral — no ``click`` / ``rich`` / ``cli`` /
``fastmcp`` imports (enforced by ``tests/_guardrails/test_app_boundary.py``).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import urlparse, urlunparse

from ..options import USE_DEFAULT, UseDefault
from ..outcomes import CommitState, redact_operation_text
from ..types import Source, SourceDeleteOutcome, source_status_to_str


class _CleanupSources(Protocol):
    async def delete_many_with_outcomes(
        self, notebook_id: str, source_ids: Sequence[str]
    ) -> list[SourceDeleteOutcome]: ...


class _CleanupClient(Protocol):
    @property
    def sources(self) -> _CleanupSources: ...

    def operation(
        self, timeout: float | None | UseDefault = None
    ) -> AbstractAsyncContextManager[object]: ...


CleanCandidate = tuple[str, str, str, str]
CleanFailure = tuple[str, str]
CleanStatus = Literal["already_clean", "dry_run", "cancelled", "completed"]


@dataclass(frozen=True)
class SourceCleanResult:
    """Result of source-clean orchestration."""

    notebook_id: str
    status: CleanStatus
    candidates: tuple[CleanCandidate, ...]
    deleted_count: int = 0
    failures: tuple[CleanFailure, ...] = ()
    outcomes: tuple[SourceDeleteOutcome, ...] = ()

    @property
    def failure_count(self) -> int:
        return len(self.failures)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


@dataclass(frozen=True)
class SourceCleanPreview:
    """Immutable cleanup target set prepared before adapter authorization."""

    notebook_id: str
    dry_run: bool
    candidates: tuple[CleanCandidate, ...]


_GATEWAY_TITLE_PATTERN = re.compile(
    r"^\s*(access denied|403|404|forbidden|not found|502"
    r"|just a moment|attention required|security check|captcha)",
    re.IGNORECASE,
)
_JUNK_STATUSES = frozenset({"error"})
_UNDATED_SORT_KEY = float("inf")


def normalize_url_for_dedup(url: str) -> str:
    """Return a URL with only the fragment stripped, for dedup comparison."""
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def classify_junk_sources(sources: list[Source]) -> list[CleanCandidate]:
    """Identify duplicate, error, and access-blocked sources for cleanup."""
    sorted_sources = sorted(
        sources,
        key=lambda s: s.created_at.timestamp() if s.created_at else _UNDATED_SORT_KEY,
    )

    candidates: list[CleanCandidate] = []
    seen_urls: dict[str, str] = {}

    for source in sorted_sources:
        title = (source.title or "").strip()
        status = source_status_to_str(source.status) if source.status else "unknown"

        if status in _JUNK_STATUSES:
            candidates.append((source.id, title, status, "error_status"))
            continue

        if _GATEWAY_TITLE_PATTERN.match(title):
            candidates.append((source.id, title, status, "gateway_title"))
            continue

        url = source.url or ""
        if url:
            normalized = normalize_url_for_dedup(url)
            kept = seen_urls.get(normalized)
            if kept is not None:
                candidates.append((source.id, title, status, f"duplicate_of:{kept[:8]}"))
                continue
            seen_urls[normalized] = source.id

    return candidates


def candidates_payload(candidates: Sequence[CleanCandidate]) -> list[dict[str, str]]:
    """Convert clean candidates to the JSON payload shape."""
    return [
        {"id": sid, "title": title, "status": status, "reason": reason}
        for sid, title, status, reason in candidates
    ]


async def prepare_source_clean(
    *,
    notebook_id: str,
    dry_run: bool,
    list_sources: Callable[[str], Awaitable[list[Source]]],
    classify_sources: Callable[[list[Source]], list[CleanCandidate]] = classify_junk_sources,
) -> SourceCleanPreview:
    """Classify junk sources without deleting or consulting presentation policy."""
    sources = await list_sources(notebook_id)
    candidates = classify_sources(sources)
    return SourceCleanPreview(notebook_id, dry_run, tuple(candidates))


def skip_source_clean(preview: SourceCleanPreview, *, cancelled: bool = False) -> SourceCleanResult:
    """Project a prepared no-op, dry run, or adapter-declined cleanup."""
    if not preview.candidates:
        return SourceCleanResult(
            notebook_id=preview.notebook_id,
            status="already_clean",
            candidates=(),
        )
    if preview.dry_run:
        return SourceCleanResult(
            notebook_id=preview.notebook_id,
            status="dry_run",
            candidates=preview.candidates,
        )
    if cancelled:
        return SourceCleanResult(
            notebook_id=preview.notebook_id,
            status="cancelled",
            candidates=preview.candidates,
        )
    raise ValueError("non-empty cleanup preview requires execution or cancellation")


async def execute_source_clean(
    preview: SourceCleanPreview,
    *,
    client: _CleanupClient,
) -> SourceCleanResult:
    """Delete the exact immutable target set an adapter already authorized."""
    if preview.dry_run or not preview.candidates:
        return skip_source_clean(preview)

    async with client.operation(timeout=USE_DEFAULT):
        outcomes = await client.sources.delete_many_with_outcomes(
            preview.notebook_id, tuple(candidate[0] for candidate in preview.candidates)
        )
        return SourceCleanResult(
            notebook_id=preview.notebook_id,
            status="completed",
            candidates=preview.candidates,
            deleted_count=sum(
                item.outcome.commit_state is CommitState.CONFIRMED for item in outcomes
            ),
            failures=tuple(
                (
                    item.source_id,
                    redact_operation_text(item.error)
                    if item.error
                    else "deletion was not confirmed",
                )
                for item in outcomes
                if item.error is not None or item.outcome.commit_state is not CommitState.CONFIRMED
            ),
            outcomes=tuple(outcomes),
        )


__all__ = [
    "CleanCandidate",
    "CleanFailure",
    "CleanStatus",
    "SourceCleanResult",
    "SourceCleanPreview",
    "candidates_payload",
    "classify_junk_sources",
    "normalize_url_for_dedup",
    "execute_source_clean",
    "prepare_source_clean",
    "skip_source_clean",
]
