"""Ordered evidence for supervised source cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..outcomes import BatchItemOutcome


@dataclass(frozen=True)
class SourceDeleteOutcome:
    """One requested deletion, including its canonical commit and recovery evidence."""

    source_id: str
    outcome: BatchItemOutcome
    error: BaseException | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Canonical evidence owns the bounded, redacted public spelling.
        object.__setattr__(self, "source_id", self.outcome.input)
