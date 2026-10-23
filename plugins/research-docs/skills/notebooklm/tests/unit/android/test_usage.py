"""Exact Android usage-meter protobuf, codec, and adapter contracts."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.empty_pb2 import Empty
from google.protobuf.timestamp_pb2 import Timestamp

from notebooklm._android.codecs import usage as usage_codec
from notebooklm._android.proto.google.internal.labs.tailwind.api.v1 import quota_pb2
from notebooklm._android.proto.google.internal.labs.tailwind.metering.v1 import metering_pb2
from notebooklm._android.proto.google.internal.labs.tailwind.orchestration.v1 import account_pb2
from notebooklm._android.proto.notebooklm.internal.android.wire.v1 import usage_pb2
from notebooklm._android.session import AndroidSession
from notebooklm._android.settings import (
    GET_ACCOUNT_METHOD,
    LIST_QUOTA_SUMMARY_METHOD,
    AndroidSettingsAPI,
)
from notebooklm._android.upload import android_request_context
from notebooklm.exceptions import DecodingError

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "android" / "usage_wire.json"


@dataclass(frozen=True)
class _UsageAccount:
    compute_metering_enabled: bool = False


@dataclass(frozen=True)
class _RawUsageWindow:
    window_code: int | None
    resets_at: datetime | None
    used_percent: float | None
    remaining_percent: float | None


@dataclass(frozen=True)
class _RawUsageAction:
    action_code: int | None
    has_sufficient_quota: bool | None
    cost_tier_code: int | None
    remaining_deferred_artifact_generations: int | None
    estimated_cost_percent: float | None


@dataclass(frozen=True)
class _RawUsageSummary:
    status_code: int | None
    windows: tuple[_RawUsageWindow, ...] = ()
    actions: tuple[_RawUsageAction, ...] = ()
    method_id: str = "EylDcb"


_BRIDGE = SimpleNamespace(
    UsageAccount=_UsageAccount,
    RawUsageWindow=_RawUsageWindow,
    RawUsageAction=_RawUsageAction,
    RawUsageSummary=_RawUsageSummary,
)


def _fixture_hex(fixture: dict[str, Any], key: str) -> str:
    """Join short, secret-scanner-safe chunks into one exact wire hex string."""

    value = fixture[key]
    return "".join(value) if isinstance(value, list) else value


@pytest.fixture(autouse=True)
def _install_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(usage_codec, "_usage_types", lambda: _BRIDGE)


def _fields(message_type: type[Any]) -> dict[str, tuple[int, int, str | None, bool]]:
    return {
        field.name: (
            field.number,
            field.type,
            None if field.message_type is None else field.message_type.full_name,
            field.has_presence,
        )
        for field in message_type.DESCRIPTOR.fields
    }


def test_exact_quota_proto_packages_fields_enums_and_service_boundary() -> None:
    message = FieldDescriptor.TYPE_MESSAGE
    int32 = FieldDescriptor.TYPE_INT32
    boolean = FieldDescriptor.TYPE_BOOL
    double = FieldDescriptor.TYPE_DOUBLE
    enum = FieldDescriptor.TYPE_ENUM

    assert quota_pb2.DESCRIPTOR.package == "google.internal.labs.tailwind.api.v1"
    assert quota_pb2.DESCRIPTOR.services_by_name == {}
    assert _fields(quota_pb2.ListQuotaSummaryRequest) == {
        "request_context": (
            1,
            message,
            "labs.language.tailwind.common.protos.RequestContext",
            True,
        )
    }

    package = "google.internal.labs.tailwind.metering.v1"
    assert metering_pb2.DESCRIPTOR.package == package
    assert metering_pb2.DESCRIPTOR.services_by_name == {}
    assert _fields(metering_pb2.ListQuotaSummaryResponse) == {
        "status": (1, enum, None, False),
        "summaries": (2, message, f"{package}.QuotaSummaryEntry", False),
        "out_of_quota_actions": (3, enum, None, False),
        "action_quota_summaries": (4, message, f"{package}.UserActionQuotaSummary", False),
    }
    assert _fields(metering_pb2.QuotaSummaryEntry) == {
        "window": (5, enum, None, False),
        "next_refresh_time": (6, message, "google.protobuf.Timestamp", True),
        "used_micros_percent": (7, double, None, False),
    }
    assert _fields(metering_pb2.UserActionQuotaSummary) == {
        "action": (1, enum, None, False),
        "has_sufficient_quota": (2, boolean, None, False),
        "cost_tier": (4, enum, None, False),
        "estimated_cost_pct_of_budget": (6, double, None, False),
    }
    assert metering_pb2.UserAction.Name(22) == "SUGGESTION_CHIPS"
    assert metering_pb2.ActionCostTier.keys() == [
        "ACTION_COST_TIER_UNSPECIFIED",
        "LOW",
        "MEDIUM",
        "HIGH",
        "VERY_HIGH",
    ]
    assert metering_pb2.ListQuotaSummaryResponse.Status.keys() == [
        "STATUS_UNSPECIFIED",
        "SUCCESS",
        "SKIPPED",
        "FAILED",
    ]

    assert usage_pb2.DESCRIPTOR.package == "notebooklm.internal.android.wire.v1"
    assert _fields(usage_pb2.WireQuotaSummaryEntry) == {
        "window": (5, enum, None, True),
        "next_refresh_time": (6, message, "google.protobuf.Timestamp", True),
        "used_micros_percent": (7, double, None, True),
        "remaining_micros_percent": (8, double, None, True),
    }
    assert _fields(usage_pb2.WireUserActionQuotaSummary) == {
        "action": (1, enum, None, True),
        "has_sufficient_quota": (2, boolean, None, True),
        "remaining_deferred_artifact_generations": (3, int32, None, True),
        "cost_tier": (4, enum, None, True),
        "action_priority": (5, int32, None, True),
        "estimated_cost_pct_of_budget": (6, double, None, True),
    }
    assert _fields(usage_pb2.WireListQuotaSummaryResponse) == {
        "status": (1, enum, None, True),
        "summaries": (
            2,
            message,
            "notebooklm.internal.android.wire.v1.WireQuotaSummaryEntry",
            False,
        ),
        "out_of_quota_actions": (3, enum, None, False),
        "action_quota_summaries": (
            4,
            message,
            "notebooklm.internal.android.wire.v1.WireUserActionQuotaSummary",
            False,
        ),
    }


def test_synthetic_fixture_pins_empty_get_account_envelope_and_context_bytes() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert Empty().SerializeToString().hex() == fixture["get_account_request_hex"] == ""

    account = account_pb2.GetOrCreateAccountResponse.FromString(
        bytes.fromhex(fixture["get_account_response_hex"])
    )
    assert account.SerializeToString().hex() == fixture["get_account_response_hex"]
    assert account.account.premium_user_info.HasField("compute_metering_enabled")
    assert account.account.premium_user_info.compute_metering_enabled is True
    assert usage_codec.decode_usage_account(account) == _UsageAccount(True)

    request = quota_pb2.ListQuotaSummaryRequest(request_context=android_request_context())
    assert len(request.SerializeToString()) == 52
    assert request.SerializeToString().hex() == _fixture_hex(fixture, "list_quota_request_hex")


def test_synthetic_quota_fixture_preserves_elision_future_codes_and_exact_floats() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    wire = bytes.fromhex(_fixture_hex(fixture, "list_quota_response_hex"))
    response = usage_pb2.WireListQuotaSummaryResponse.FromString(wire)
    assert response.SerializeToString() == wire

    decoded = usage_codec.decode_quota_summary(response, method_id=LIST_QUOTA_SUMMARY_METHOD)
    assert decoded.status_code == 1
    assert decoded.windows == (
        _RawUsageWindow(
            window_code=1,
            resets_at=datetime(2026, 9, 5, 7, 37, 21, 548366, tzinfo=timezone.utc),
            used_percent=None,
            remaining_percent=100.0,
        ),
        _RawUsageWindow(
            window_code=2,
            resets_at=datetime(2026, 9, 12, 2, 37, 21, 548437, tzinfo=timezone.utc),
            used_percent=1.7261085,
            remaining_percent=98.2738914,
        ),
    )
    assert decoded.actions == (
        _RawUsageAction(23, False, 99, None, None),
        _RawUsageAction(9, None, None, 0, 1.8666666666666667),
    )

    # The exact APK subset retains live-only fields as unknowns and can pass
    # them through. Parsing through it does lose explicit-false presence,
    # demonstrating why runtime must select the overlay directly.
    exact = metering_pb2.ListQuotaSummaryResponse.FromString(wire)
    reparsed = usage_pb2.WireListQuotaSummaryResponse.FromString(exact.SerializeToString())
    assert reparsed.summaries == response.summaries
    assert reparsed.action_quota_summaries[1] == response.action_quota_summaries[1]
    assert reparsed.action_quota_summaries[0].action == 23
    assert reparsed.action_quota_summaries[0].cost_tier == 99
    assert response.action_quota_summaries[0].HasField("has_sufficient_quota")
    assert not reparsed.action_quota_summaries[0].HasField("has_sufficient_quota")
    assert not hasattr(exact.summaries[0], "remaining_micros_percent")


@pytest.mark.parametrize("status", [None, 0, 1, 2, 3, 99])
def test_status_presence_and_unknown_values_are_not_normalized(status: int | None) -> None:
    response = usage_pb2.WireListQuotaSummaryResponse()
    if status is not None:
        response.status = status
    decoded = usage_codec.decode_quota_summary(response, method_id=LIST_QUOTA_SUMMARY_METHOD)
    assert decoded.status_code == status


def test_all_scalar_presence_cases_and_nonfinite_values_reach_neutral_decoder() -> None:
    response = usage_pb2.WireListQuotaSummaryResponse(status=1)
    response.summaries.add(window=1)
    response.summaries.add(
        window=2,
        used_micros_percent=float("nan"),
        remaining_micros_percent=float("inf"),
    )
    response.action_quota_summaries.add(
        action=10,
        has_sufficient_quota=False,
        remaining_deferred_artifact_generations=-1,
        cost_tier=0,
        estimated_cost_pct_of_budget=float("-inf"),
    )

    decoded = usage_codec.decode_quota_summary(response, method_id=LIST_QUOTA_SUMMARY_METHOD)
    assert decoded.windows[0].used_percent is None
    assert decoded.windows[0].remaining_percent is None
    assert math.isnan(cast(float, decoded.windows[1].used_percent))
    assert decoded.windows[1].remaining_percent == float("inf")
    assert decoded.actions[0] == _RawUsageAction(10, False, 0, -1, float("-inf"))


def test_invalid_present_timestamp_is_bounded_decoding_error() -> None:
    response = usage_pb2.WireListQuotaSummaryResponse(status=1)
    row = response.summaries.add(window=1)
    row.next_refresh_time.CopyFrom(Timestamp(seconds=253_402_300_800))
    with pytest.raises(DecodingError) as raised:
        usage_codec.decode_quota_summary(response, method_id=LIST_QUOTA_SUMMARY_METHOD)
    assert raised.value.method_id == LIST_QUOTA_SUMMARY_METHOD


@dataclass(frozen=True)
class _Lease:
    epoch: int


class _FakeSession:
    def __init__(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.account = account_pb2.GetOrCreateAccountResponse.FromString(
            bytes.fromhex(fixture["get_account_response_hex"])
        )
        self.quota = usage_pb2.WireListQuotaSummaryResponse.FromString(
            bytes.fromhex(_fixture_hex(fixture, "list_quota_response_hex"))
        )
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def unary(self, method: str, request: Any, **kwargs: Any) -> Any:
        self.calls.append((method, request, kwargs))
        return self.account if method == GET_ACCOUNT_METHOD else self.quota


async def test_adapter_hooks_use_native_read_paths_codecs_and_one_shared_epoch() -> None:
    session = _FakeSession()
    api = AndroidSettingsAPI(cast(AndroidSession, session))
    lease = _Lease(71)

    assert await api._get_usage_account(lease=cast(Any, lease)) == _UsageAccount(True)
    summary = await api._list_quota_summary(lease=cast(Any, lease))
    assert summary.status_code == 1
    assert [call[0] for call in session.calls] == [GET_ACCOUNT_METHOD, LIST_QUOTA_SUMMARY_METHOD]

    account_call, quota_call = session.calls
    assert isinstance(account_call[1], Empty)
    assert account_call[1].SerializeToString() == b""
    assert account_call[2] == {
        "replay_safe": True,
        "response_type": account_pb2.GetOrCreateAccountResponse,
        "expected_epoch": 71,
    }
    assert isinstance(quota_call[1], quota_pb2.ListQuotaSummaryRequest)
    assert quota_call[1].HasField("request_context")
    assert quota_call[2] == {
        "replay_safe": True,
        "response_type": usage_pb2.WireListQuotaSummaryResponse,
        "expected_epoch": 71,
    }


@pytest.mark.parametrize(
    "response",
    [
        account_pb2.GetOrCreateAccountResponse(),
        account_pb2.GetOrCreateAccountResponse(account=account_pb2.Account()),
        account_pb2.GetOrCreateAccountResponse(
            account=account_pb2.Account(premium_user_info=account_pb2.PremiumUserInfo())
        ),
        account_pb2.GetOrCreateAccountResponse(
            account=account_pb2.Account(
                premium_user_info=account_pb2.PremiumUserInfo(compute_metering_enabled=False)
            )
        ),
    ],
)
def test_absent_or_explicit_false_meter_bit_normalizes_to_disabled(response: Any) -> None:
    assert usage_codec.decode_usage_account(response) == _UsageAccount(False)
