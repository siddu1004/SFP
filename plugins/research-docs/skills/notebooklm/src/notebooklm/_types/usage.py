"""Public transport-neutral models for the live compute usage meter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UsageSummaryStatus(str, Enum):
    """Availability state returned by the live compute meter."""

    DISABLED = "disabled"
    READY = "ready"
    SKIPPED = "skipped"


class UsageWindowKind(int, Enum):
    """Server-defined compute-meter reset windows."""

    FIVE_HOUR = 1
    WEEKLY = 2


class UsageActionKind(int, Enum):
    """Server-defined actions charged by the unified compute meter."""

    AUDIO_OVERVIEW = 1
    VIDEO_OVERVIEW = 2
    BREAKDOWNS_VIDEO = 3
    SHORTS_VIDEO = 4
    INFOGRAPHIC = 5
    SLIDES = 6
    REPORTS = 7
    TABLES = 8
    FLASHCARDS = 9
    QUIZ = 10
    MINDMAP = 11
    CANVAS = 12
    SLIDES_EDITING = 13
    FLASHCARD_EDITING = 14
    DEEP_RESEARCH = 15
    NOS = 16
    FAST_RESEARCH = 17
    QNA = 18
    NOS_IMAGE_GENERATION = 19
    GUIDED_VIEW = 20
    DOCUMENT_GUIDE = 21
    SUGGESTION_CHIPS = 22


class UsageActionCostTier(int, Enum):
    """Relative cost tier advertised for a metered action."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


@dataclass(frozen=True)
class UsageWindow:
    """One authoritative usage percentage and reset time."""

    kind: UsageWindowKind
    used_percent: float
    remaining_percent: float
    resets_at: datetime


@dataclass(frozen=True)
class UsageAction:
    """Current availability and advertised cost for one server action code."""

    code: int
    kind: UsageActionKind | None
    has_sufficient_quota: bool
    cost_tier: UsageActionCostTier | None
    remaining_deferred_artifact_generations: int | None
    estimated_cost_percent: float | None


@dataclass(frozen=True)
class UsageSummary:
    """A live compute-meter snapshot for the current account."""

    status: UsageSummaryStatus
    windows: tuple[UsageWindow, ...] = ()
    actions: tuple[UsageAction, ...] = ()

    @property
    def enabled(self) -> bool:
        """Whether the account is eligible for server-side compute metering."""
        return self.status is not UsageSummaryStatus.DISABLED

    @property
    def available(self) -> bool:
        """Whether a live meter snapshot is currently available."""
        return self.status is UsageSummaryStatus.READY

    def window(self, kind: UsageWindowKind) -> UsageWindow | None:
        """Return the row for ``kind``, if the server supplied it."""
        return next((window for window in self.windows if window.kind is kind), None)

    def action(self, code: int | UsageActionKind) -> UsageAction | None:
        """Return the action row for a numeric or known action code."""
        return next((action for action in self.actions if action.code == code), None)

    @property
    def active_window(self) -> UsageWindow | None:
        """Return the UI-compatible active window from a ready snapshot."""
        if self.status is not UsageSummaryStatus.READY:
            return None
        weekly = self.window(UsageWindowKind.WEEKLY)
        if weekly is not None and weekly.used_percent >= 100.0:
            return weekly
        return self.window(UsageWindowKind.FIVE_HOUR)

    @property
    def is_exhausted(self) -> bool | None:
        """Whether the active meter window is exhausted, when available."""
        if self.status is not UsageSummaryStatus.READY:
            return None
        active = self.active_window
        return active.used_percent >= 100.0 if active is not None else False


__all__ = [
    "UsageAction",
    "UsageActionCostTier",
    "UsageActionKind",
    "UsageSummary",
    "UsageSummaryStatus",
    "UsageWindow",
    "UsageWindowKind",
]
