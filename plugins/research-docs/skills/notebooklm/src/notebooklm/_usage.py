"""Transport-neutral orchestration and decoded bridge for live usage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, NoReturn

from .exceptions import DecodingError, ServerError
from .types import (
    UsageAction,
    UsageActionCostTier,
    UsageActionKind,
    UsageSummary,
    UsageSummaryStatus,
    UsageWindow,
    UsageWindowKind,
)

DEFAULT_USAGE_METHOD = "ListQuotaSummary"


@dataclass(frozen=True)
class UsageAccount:
    """Decoded account eligibility bit supplied by a transport adapter."""

    compute_metering_enabled: bool = False


@dataclass(frozen=True)
class RawUsageWindow:
    """Presence-aware decoded quota-window fields supplied by an adapter."""

    window_code: int | None
    resets_at: datetime | None
    used_percent: float | None
    remaining_percent: float | None


@dataclass(frozen=True)
class RawUsageAction:
    """Presence-aware decoded quota-action fields supplied by an adapter."""

    action_code: int | None
    has_sufficient_quota: bool | None
    cost_tier_code: int | None
    remaining_deferred_artifact_generations: int | None
    estimated_cost_percent: float | None


@dataclass(frozen=True)
class RawUsageSummary:
    """Decoded transport response before neutral validation and projection."""

    status_code: int | None
    windows: tuple[RawUsageWindow, ...] = ()
    actions: tuple[RawUsageAction, ...] = ()
    method_id: str = DEFAULT_USAGE_METHOD


def decode_usage_summary(raw: RawUsageSummary) -> UsageSummary:
    """Validate a decoded quota response and project it to public models."""
    method_id = raw.method_id or DEFAULT_USAGE_METHOD
    status = _integer(raw.status_code)
    if status == 2:
        return UsageSummary(status=UsageSummaryStatus.SKIPPED)
    if status == 3:
        raise ServerError("ListQuotaSummary failed", method_id=method_id)
    if status != 1:
        _drift("ListQuotaSummary returned a missing or unknown status", method_id)

    windows = tuple(
        sorted((_decode_window(row, method_id) for row in raw.windows), key=lambda row: row.kind)
    )
    expected_kinds = {UsageWindowKind.FIVE_HOUR, UsageWindowKind.WEEKLY}
    actual_kinds = {window.kind for window in windows}
    if len(windows) != len(expected_kinds) or actual_kinds != expected_kinds:
        _drift(
            "ListQuotaSummary must contain exactly one five-hour and one weekly window", method_id
        )

    actions = tuple(
        sorted(
            (_decode_action(row, method_id) for row in raw.actions), key=lambda action: action.code
        )
    )
    return UsageSummary(status=UsageSummaryStatus.READY, windows=windows, actions=actions)


def _decode_window(row: RawUsageWindow, method_id: str) -> UsageWindow:
    code = _integer(row.window_code)
    try:
        kind = UsageWindowKind(code) if code is not None else None
    except ValueError:
        kind = None
    if kind is None:
        _drift("ListQuotaSummary returned an unknown or missing window code", method_id)

    resets_at = row.resets_at
    if not isinstance(resets_at, datetime) or resets_at.tzinfo is None:
        _drift("ListQuotaSummary window omitted a valid reset timestamp", method_id)
    try:
        if resets_at.utcoffset() is None:
            _drift("ListQuotaSummary window omitted a valid reset timestamp", method_id)
        resets_at = resets_at.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        _drift("ListQuotaSummary window contained an invalid reset timestamp", method_id)

    used = _finite_float(row.used_percent, method_id, "used percentage")
    remaining = _finite_float(row.remaining_percent, method_id, "remaining percentage")
    if used is None and remaining is None:
        _drift("ListQuotaSummary window omitted both percentages", method_id)
    if used is None:
        assert remaining is not None
        used = 100.0 - remaining
    if remaining is None:
        remaining = 100.0 - used
    return UsageWindow(
        kind=kind, used_percent=used, remaining_percent=remaining, resets_at=resets_at
    )


def _decode_action(row: RawUsageAction, method_id: str) -> UsageAction:
    code = _integer(row.action_code)
    if code is None or code <= 0:
        _drift("ListQuotaSummary action omitted a valid action code", method_id)
    try:
        kind = UsageActionKind(code)
    except ValueError:
        kind = None

    available = row.has_sufficient_quota
    if available is not None and not isinstance(available, bool):
        _drift("ListQuotaSummary action contained an invalid quota availability", method_id)

    tier_code = _integer(row.cost_tier_code)
    try:
        tier = UsageActionCostTier(tier_code) if tier_code is not None else None
    except ValueError:
        tier = None

    deferred = row.remaining_deferred_artifact_generations
    if deferred is not None and (_integer(deferred) is None or deferred < 0):
        _drift("ListQuotaSummary action contained a negative deferred-generation count", method_id)

    cost = _finite_float(row.estimated_cost_percent, method_id, "estimated cost percentage")
    return UsageAction(
        code=code,
        kind=kind,
        has_sufficient_quota=available is True,
        cost_tier=tier,
        remaining_deferred_artifact_generations=deferred,
        estimated_cost_percent=cost,
    )


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _finite_float(value: Any, method_id: str, label: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _drift(f"ListQuotaSummary contained an invalid {label}", method_id)
    try:
        result = float(value)
    except OverflowError as exc:
        raise DecodingError(
            f"ListQuotaSummary contained an out-of-range {label}", method_id=method_id
        ) from exc
    if not math.isfinite(result):
        _drift(f"ListQuotaSummary contained a non-finite {label}", method_id)
    return result


def _drift(message: str, method_id: str) -> NoReturn:
    raise DecodingError(message, method_id=method_id)


__all__ = [
    "DEFAULT_USAGE_METHOD",
    "RawUsageAction",
    "RawUsageSummary",
    "RawUsageWindow",
    "UsageAccount",
    "decode_usage_summary",
]
