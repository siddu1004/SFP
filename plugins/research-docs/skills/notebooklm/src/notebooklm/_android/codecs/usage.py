"""Presence-preserving Android usage-meter projection."""

from __future__ import annotations

from datetime import timezone
from typing import TYPE_CHECKING, Any

from ...exceptions import DecodingError

if TYPE_CHECKING:
    from ..._usage import RawUsageAction, RawUsageSummary, RawUsageWindow, UsageAccount


def _usage_types() -> Any:
    # Kept lazy so importing the optional Android backend does not widen the
    # public type module's import-time protobuf closure.
    from ... import _usage

    return _usage


def decode_usage_account(response: Any) -> UsageAccount:
    """Read the server-owned meter bit; every absent envelope branch is false."""

    enabled = False
    if response.HasField("account"):
        account = response.account
        if account.HasField("premium_user_info"):
            premium = account.premium_user_info
            if premium.HasField("compute_metering_enabled"):
                enabled = premium.compute_metering_enabled
    return _usage_types().UsageAccount(compute_metering_enabled=enabled)


def _decode_reset_timestamp(message: Any, *, method_id: str) -> Any:
    if not message.HasField("next_refresh_time"):
        return None
    try:
        return message.next_refresh_time.ToDatetime(tzinfo=timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise DecodingError(
            "Android ListQuotaSummary response has an invalid reset timestamp",
            method_id=method_id,
        ) from exc


def decode_quota_summary(response: Any, *, method_id: str) -> RawUsageSummary:
    """Project the wire overlay without collapsing absent proto3 scalars."""

    usage = _usage_types()
    windows: list[RawUsageWindow] = []
    for row in response.summaries:
        windows.append(
            usage.RawUsageWindow(
                window_code=row.window if row.HasField("window") else None,
                resets_at=_decode_reset_timestamp(row, method_id=method_id),
                used_percent=(
                    row.used_micros_percent if row.HasField("used_micros_percent") else None
                ),
                remaining_percent=(
                    row.remaining_micros_percent
                    if row.HasField("remaining_micros_percent")
                    else None
                ),
            )
        )

    actions: list[RawUsageAction] = []
    for row in response.action_quota_summaries:
        actions.append(
            usage.RawUsageAction(
                action_code=row.action if row.HasField("action") else None,
                has_sufficient_quota=(
                    row.has_sufficient_quota if row.HasField("has_sufficient_quota") else None
                ),
                cost_tier_code=row.cost_tier if row.HasField("cost_tier") else None,
                remaining_deferred_artifact_generations=(
                    row.remaining_deferred_artifact_generations
                    if row.HasField("remaining_deferred_artifact_generations")
                    else None
                ),
                estimated_cost_percent=(
                    row.estimated_cost_pct_of_budget
                    if row.HasField("estimated_cost_pct_of_budget")
                    else None
                ),
            )
        )

    return usage.RawUsageSummary(
        status_code=response.status if response.HasField("status") else None,
        windows=tuple(windows),
        actions=tuple(actions),
        method_id=method_id,
    )


__all__ = ["decode_quota_summary", "decode_usage_account"]
