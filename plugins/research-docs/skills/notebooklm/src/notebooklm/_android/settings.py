"""Android implementation of the public account-settings contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from .._runtime.call_supervisor import OperationLease
from .._settings import SettingsAPI
from .._usage import RawUsageSummary, UsageAccount
from ..exceptions import DecodingError
from ..types import AccountLimits, UserSettings
from .epoch import bind_workflow_epoch, reset_workflow_epoch
from .session import AndroidSession

_SERVICE = "google.internal.labs.tailwind.orchestration.v1.LabsTailwindOrchestrationService"
GET_OR_CREATE_ACCOUNT_METHOD = f"/{_SERVICE}/GetOrCreateAccount"
GET_ACCOUNT_METHOD = f"/{_SERVICE}/GetAccount"
LIST_QUOTA_SUMMARY_METHOD = f"/{_SERVICE}/ListQuotaSummary"
MUTATE_ACCOUNT_METHOD = f"/{_SERVICE}/MutateAccount"


def _proto() -> Any:
    from .proto.google.internal.labs.tailwind.orchestration.v1 import account_pb2

    return cast(Any, account_pb2)


def _quota_proto() -> tuple[Any, Any]:
    from .proto.google.internal.labs.tailwind.api.v1 import quota_pb2
    from .proto.notebooklm.internal.android.wire.v1 import usage_pb2

    return cast(Any, quota_pb2), cast(Any, usage_pb2)


def _empty_request() -> Any:
    from google.protobuf.empty_pb2 import Empty

    return Empty()


def _request_context() -> Any:
    from .upload import android_request_context

    return android_request_context()


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _non_negative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _decode_account(account: Any) -> UserSettings:
    language = None
    if account.HasField("user_info") and account.user_info.HasField("output_language"):
        language = account.user_info.output_language.language_code or None

    limits = AccountLimits()
    if account.HasField("tier_limits"):
        wire = account.tier_limits
        field_names = (
            "account_type",
            "max_projects",
            "max_sources_per_project",
            "max_words_per_source",
            "subscription_tier",
        )
        values = [getattr(wire, name) if wire.HasField(name) else None for name in field_names]
        while values:
            trailing = values.pop()
            if trailing is not None:
                values.append(trailing)
                break
        limits = AccountLimits(
            notebook_limit=(
                _non_negative_int(wire.max_projects) if wire.HasField("max_projects") else None
            ),
            source_limit=(
                _non_negative_int(wire.max_sources_per_project)
                if wire.HasField("max_sources_per_project")
                else None
            ),
            raw_limits=tuple(values),
            tier=(
                _positive_int(wire.subscription_tier)
                if wire.HasField("subscription_tier")
                else None
            ),
        )
    return UserSettings(limits=limits, output_language=language)


class AndroidSettingsAPI(SettingsAPI):
    """Native output-language and quota settings over the account RPCs."""

    @asynccontextmanager
    async def _operation_scope(self, label: str) -> AsyncIterator[OperationLease]:
        async with self._transport.operation_scope(label) as lease:
            token = bind_workflow_epoch(self._transport, lease.epoch)
            try:
                yield lease
            finally:
                reset_workflow_epoch(token)

    def __init__(self, session: AndroidSession) -> None:
        self._transport = session

    async def _get_usage_account(self, *, lease: OperationLease | None) -> UsageAccount:
        """Fetch meter eligibility through the path-only GetAccount contract."""

        from .codecs.usage import decode_usage_account

        proto = _proto()
        response = await self._transport.unary(
            GET_ACCOUNT_METHOD,
            _empty_request(),
            replay_safe=True,
            response_type=proto.GetOrCreateAccountResponse,
            expected_epoch=None if lease is None else lease.epoch,
        )
        return decode_usage_account(response)

    async def _list_quota_summary(self, *, lease: OperationLease | None) -> RawUsageSummary:
        """Fetch one uncached usage snapshot through the inferred native alias."""

        from .codecs.usage import decode_quota_summary

        quota_proto, wire_proto = _quota_proto()
        response = await self._transport.unary(
            LIST_QUOTA_SUMMARY_METHOD,
            quota_proto.ListQuotaSummaryRequest(request_context=_request_context()),
            replay_safe=True,
            response_type=wire_proto.WireListQuotaSummaryResponse,
            expected_epoch=None if lease is None else lease.epoch,
        )
        return decode_quota_summary(response, method_id=LIST_QUOTA_SUMMARY_METHOD)

    async def _get_user_settings(self, *, expected_epoch: int) -> UserSettings:
        proto = _proto()
        response = await self._transport.unary(
            GET_OR_CREATE_ACCOUNT_METHOD,
            proto.GetOrCreateAccountRequest(request_context=_request_context()),
            replay_safe=False,
            response_type=proto.GetOrCreateAccountResponse,
            expected_epoch=expected_epoch,
        )
        if not response.HasField("account"):
            raise DecodingError(
                "Android GetOrCreateAccount response omitted account",
                method_id=GET_OR_CREATE_ACCOUNT_METHOD,
            )
        return _decode_account(response.account)

    async def set_output_language(self, language: str) -> str | None:
        if not language:
            return None
        proto = _proto()
        request = proto.MutateAccountRequest(
            mutations=[
                proto.AccountMutation(
                    change_property=proto.AccountMutation_ChangePropertyMutation(
                        new_user_info=proto.UserInfo(
                            output_language=proto.OutputLanguage(language_code=language)
                        )
                    )
                )
            ],
            request_context=_request_context(),
        )
        async with self._transport.operation_scope("settings.set_output_language") as lease:
            account = await self._transport.unary(
                MUTATE_ACCOUNT_METHOD,
                request,
                replay_safe=False,
                response_type=proto.Account,
                expected_epoch=lease.epoch,
            )
            return _decode_account(account).output_language

    async def get_user_settings(self) -> UserSettings:
        async with self._transport.operation_scope("settings.get_user_settings") as lease:
            return await self._get_user_settings(expected_epoch=lease.epoch)

    async def get_output_language(self) -> str | None:
        async with self._transport.operation_scope("settings.get_output_language") as lease:
            return (await self._get_user_settings(expected_epoch=lease.epoch)).output_language

    async def get_account_limits(self) -> AccountLimits:
        async with self._transport.operation_scope("settings.get_account_limits") as lease:
            return (await self._get_user_settings(expected_epoch=lease.epoch)).limits


__all__ = [
    "AndroidSettingsAPI",
    "GET_ACCOUNT_METHOD",
    "GET_OR_CREATE_ACCOUNT_METHOD",
    "LIST_QUOTA_SUMMARY_METHOD",
    "MUTATE_ACCOUNT_METHOD",
]
