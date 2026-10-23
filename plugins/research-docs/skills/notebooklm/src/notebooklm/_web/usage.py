"""Web positional codecs for the live compute-meter usage RPCs.

The public usage models deliberately live outside the Web backend.  This
module only translates the batchexecute arrays into the neutral bridge records
owned by :mod:`notebooklm._usage`; keeping that boundary here makes the same
semantic validation usable by the Web and Android adapters.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from ..exceptions import DecodingError
from ..rpc import RPCMethod
from .rows.usage import (
    UsageAccountEnvelopeRow,
    UsageActionRow,
    UsageSummaryRow,
    UsageTimestampRow,
    UsageWindowRow,
)

if TYPE_CHECKING:
    from .._runtime.call_supervisor import OperationLease
    from .._usage import RawUsageAction, RawUsageSummary, RawUsageWindow, UsageAccount
    from .contracts import RpcCaller

_ACCOUNT_METHOD_ID = RPCMethod.GET_ACCOUNT.value
_QUOTA_METHOD_ID = RPCMethod.LIST_QUOTA_SUMMARY.value
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _bridge_types() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    """Load neutral bridge records only when a usage call is made.

    The public branch supplies ``_usage`` alongside this adapter.  Lazy import
    avoids making unrelated legacy Web settings imports depend on that branch
    while the transport changes are developed independently.
    """

    from .._usage import (  # noqa: PLC0415
        RawUsageAction,
        RawUsageSummary,
        RawUsageWindow,
        UsageAccount,
    )

    return UsageAccount, RawUsageSummary, RawUsageWindow, RawUsageAction, datetime


def build_get_account_params() -> list[Any]:
    """Build the empty Web request for ``GetAccount``."""

    return []


def build_list_quota_summary_params() -> list[Any]:
    """Build ``ListQuotaSummary([RequestContext])`` for batchexecute.

    Web's request-context slot is represented by the usual ``null`` value;
    unlike the Android transport, there is no local protobuf object to build.
    """

    return [None]


def _error(message: str, *, method_id: str) -> DecodingError:
    return DecodingError(message, method_id=method_id)


def _optional_number(value: Any, *, method_id: str, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{label} is not numeric", method_id=method_id)
    try:
        number = float(value)
    except OverflowError as exc:
        raise _error(f"{label} is out of range", method_id=method_id) from exc
    if not math.isfinite(number):
        raise _error(f"{label} is non-finite", method_id=method_id)
    return number


def _optional_int(value: Any, *, method_id: str, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(f"{label} is not integral", method_id=method_id)
    return value


def _timestamp(value: Any, *, method_id: str) -> datetime | None:
    """Decode a JSPB Timestamp represented as ``[seconds, nanos]``.

    The Web array codec uses the protobuf pair representation.  Reject
    malformed present values so drift is not mistaken for a missing reset
    time; in particular, protobuf ``int64`` seconds and ``int32`` nanos must
    not be accepted as fractional JSON numbers.
    """

    if value is None:
        return None
    row = UsageTimestampRow(value)
    if not row.is_well_formed_container:
        raise _error("invalid quota reset timestamp", method_id=method_id)
    seconds = row.seconds
    nanos = row.nanos if row.nanos is not None else 0
    if isinstance(seconds, bool) or not isinstance(seconds, int):
        raise _error("quota reset timestamp seconds is not integral", method_id=method_id)
    if isinstance(nanos, bool) or not isinstance(nanos, int):
        raise _error("quota reset timestamp nanos is not integral", method_id=method_id)
    if not 0 <= nanos < 1_000_000_000:
        raise _error("quota reset timestamp nanos is invalid", method_id=method_id)
    try:
        return _UNIX_EPOCH + timedelta(
            seconds=seconds,
            microseconds=nanos // 1_000,
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise _error("quota reset timestamp is out of range", method_id=method_id) from exc


def decode_account(data: Any) -> UsageAccount:
    """Extract ``PremiumUserInfo.computeMeteringEnabled`` from GetAccount.

    ``GetAccount`` is an account envelope (field 1 in the native equivalent),
    while the Web response has appeared both as ``[account]`` and as a direct
    account array.  The field path inside the account is stable: account f5,
    premium-user-info f7.  Absent account/field and an explicit false all map
    to the neutral account's false default, as required by ADR-0037.
    """

    UsageAccount, _, _, _, _ = _bridge_types()
    row = UsageAccountEnvelopeRow(data)
    return UsageAccount(compute_metering_enabled=row.compute_metering_enabled)


def _decode_window(row: Any) -> RawUsageWindow:
    _, _, RawUsageWindow, _, _ = _bridge_types()
    view = UsageWindowRow(row)
    if not view.is_array:
        raise _error("quota window row is not an array", method_id=_QUOTA_METHOD_ID)
    return RawUsageWindow(
        window_code=_optional_int(
            view.window_code, method_id=_QUOTA_METHOD_ID, label="quota window code"
        ),
        resets_at=_timestamp(view.reset_timestamp, method_id=_QUOTA_METHOD_ID),
        used_percent=_optional_number(
            view.used_percent, method_id=_QUOTA_METHOD_ID, label="quota used percentage"
        ),
        remaining_percent=_optional_number(
            view.remaining_percent,
            method_id=_QUOTA_METHOD_ID,
            label="quota remaining percentage",
        ),
    )


def _decode_action(row: Any) -> RawUsageAction:
    _, _, _, RawUsageAction, _ = _bridge_types()
    view = UsageActionRow(row)
    if not view.is_array:
        raise _error("quota action row is not an array", method_id=_QUOTA_METHOD_ID)
    action_code = _optional_int(
        view.action_code, method_id=_QUOTA_METHOD_ID, label="quota action code"
    )
    has_quota = view.has_sufficient_quota
    if has_quota is not None and not isinstance(has_quota, bool):
        raise _error("quota availability is not boolean", method_id=_QUOTA_METHOD_ID)
    deferred = view.remaining_deferred_artifact_generations
    if deferred is not None and (
        isinstance(deferred, bool) or not isinstance(deferred, int) or deferred < 0
    ):
        raise _error("remaining deferred generations is invalid", method_id=_QUOTA_METHOD_ID)
    cost_tier = view.cost_tier_code
    if cost_tier is not None and (isinstance(cost_tier, bool) or not isinstance(cost_tier, int)):
        raise _error("quota cost tier is not integral", method_id=_QUOTA_METHOD_ID)
    return RawUsageAction(
        action_code=action_code,
        has_sufficient_quota=has_quota,
        cost_tier_code=cost_tier,
        remaining_deferred_artifact_generations=deferred,
        estimated_cost_percent=_optional_number(
            view.estimated_cost_percent,
            method_id=_QUOTA_METHOD_ID,
            label="estimated quota cost",
        ),
    )


def decode_quota_summary(data: Any) -> RawUsageSummary:
    """Decode ``ListQuotaSummary`` response fields f1, f2, and f4."""

    _, RawUsageSummary, _, _, _ = _bridge_types()
    view = UsageSummaryRow(data)
    if not view.is_array:
        raise _error("quota summary response is not an array", method_id=_QUOTA_METHOD_ID)
    windows_data = view.windows
    actions_data = view.actions
    if windows_data is None:
        windows: tuple[Any, ...] = ()
    elif isinstance(windows_data, list):
        windows = tuple(_decode_window(row) for row in windows_data)
    else:
        raise _error("quota windows field is not an array", method_id=_QUOTA_METHOD_ID)
    if actions_data is None:
        actions: tuple[Any, ...] = ()
    elif isinstance(actions_data, list):
        actions = tuple(_decode_action(row) for row in actions_data)
    else:
        raise _error("quota actions field is not an array", method_id=_QUOTA_METHOD_ID)
    status = _optional_int(view.status_code, method_id=_QUOTA_METHOD_ID, label="quota status")
    return RawUsageSummary(
        status_code=status,
        windows=windows,
        actions=actions,
        method_id=_QUOTA_METHOD_ID,
    )


async def get_usage_account(rpc: RpcCaller, *, lease: OperationLease | None = None) -> UsageAccount:
    """Issue an uncached live GetAccount read and decode its account bit."""

    del lease  # Web RPC caller has no epoch argument; retained for backend parity.
    return decode_account(
        await rpc.rpc_call(RPCMethod.GET_ACCOUNT, build_get_account_params(), source_path="/")
    )


async def list_quota_summary(
    rpc: RpcCaller, *, lease: OperationLease | None = None
) -> RawUsageSummary:
    """Issue an uncached live ListQuotaSummary read and decode its payload."""

    del lease
    return decode_quota_summary(
        await rpc.rpc_call(
            RPCMethod.LIST_QUOTA_SUMMARY,
            build_list_quota_summary_params(),
            source_path="/",
        )
    )


__all__ = [
    "build_get_account_params",
    "build_list_quota_summary_params",
    "decode_account",
    "decode_quota_summary",
    "get_usage_account",
    "list_quota_summary",
]
