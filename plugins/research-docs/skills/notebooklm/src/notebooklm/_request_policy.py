"""Private, redacted construction policy and explicit Web owner bindings."""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import wraps
from secrets import token_bytes
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeVar, cast

from ._request_context import request_policy_scope

if TYPE_CHECKING:
    from .options import WebRequestOptions

_RECOVERY_ENV = (
    "NOTEBOOKLM_REFRESH_CMD",
    "NOTEBOOKLM_REFRESH_CMD_USE_SHELL",
    "NOTEBOOKLM_REFRESH_CMD_MIDSESSION",
    "NOTEBOOKLM_HEADLESS_REAUTH",
    "NOTEBOOKLM_HEADLESS_REAUTH_CDP_URL",
)
_IDENTITY_SALT = token_bytes(32)
_F = TypeVar("_F", bound=Callable[..., Any])


@dataclass(frozen=True)
class ResolvedWebPolicy:
    """Bound policy excludes credentials; execution details never enter repr."""

    base_url: str
    language: str
    build_label: str
    transport: str
    impersonate: str
    environment: Mapping[str, str | None] = field(repr=False)
    identity: str = field(repr=False)


def resolve_web_policy(options: WebRequestOptions | None) -> ResolvedWebPolicy | None:
    if options is None:
        return None
    from ._curl_cffi_transport import DEFAULT_IMPERSONATE
    from ._env import get_base_url, get_default_bl, get_default_language, validate_base_url

    # Ignore a surrounding caller's policy: each direct construction captures its
    # own options/environment, including clients constructed inside another action.
    with request_policy_scope(None):
        base = (
            validate_base_url(options.base_url) if options.base_url is not None else get_base_url()
        )
        language = options.language if options.language is not None else get_default_language()
        label = options.build_label if options.build_label is not None else get_default_bl()
    transport = options.transport or os.environ.get("NOTEBOOKLM_TRANSPORT", "").strip() or "httpx"
    if transport not in {"httpx", "curl_cffi"}:
        raise ValueError("Web request transport must be 'httpx' or 'curl_cffi'")
    impersonate = (
        options.impersonate or os.environ.get("NOTEBOOKLM_IMPERSONATE") or DEFAULT_IMPERSONATE
    )
    environment = {name: os.environ.get(name) for name in _RECOVERY_ENV}
    environment.update(
        {
            "NOTEBOOKLM_BACKEND": "web",
            "NOTEBOOKLM_BASE_URL": base,
            "NOTEBOOKLM_HL": language,
            "NOTEBOOKLM_BL": label,
            "NOTEBOOKLM_TRANSPORT": transport,
            "NOTEBOOKLM_IMPERSONATE": impersonate,
        }
    )
    identity = hmac.new(
        _IDENTITY_SALT, json.dumps(environment, sort_keys=True).encode(), hashlib.sha256
    ).hexdigest()
    return ResolvedWebPolicy(
        base, language, label, transport, impersonate, MappingProxyType(environment), identity
    )


def scoped_call(policy: ResolvedWebPolicy | None, function: _F) -> _F:
    """Bind an existing callable without changing its signature or live auth inputs."""
    if inspect.iscoroutinefunction(function):

        @wraps(function)
        async def asynchronous(*args: Any, **kwargs: Any) -> Any:
            with request_policy_scope(policy):
                return await function(*args, **kwargs)

        return cast(_F, asynchronous)

    @wraps(function)
    def synchronous(*args: Any, **kwargs: Any) -> Any:
        with request_policy_scope(policy):
            return function(*args, **kwargs)

    return cast(_F, synchronous)


class RequestPolicyOwner:
    """Branch-local owners receive this value before the frozen graph is installed."""

    request_policy: ResolvedWebPolicy | None = None

    def scoped(self, function: _F) -> _F:
        return scoped_call(self.request_policy, function)


def request_scoped(function: _F) -> _F:
    """Apply the concrete owner's policy, including explicit legacy dynamic mode."""
    if inspect.iscoroutinefunction(function):

        @wraps(function)
        async def asynchronous(self: RequestPolicyOwner, *args: Any, **kwargs: Any) -> Any:
            with request_policy_scope(self.request_policy):
                return await function(self, *args, **kwargs)

        return cast(_F, asynchronous)

    @wraps(function)
    def synchronous(self: RequestPolicyOwner, *args: Any, **kwargs: Any) -> Any:
        with request_policy_scope(self.request_policy):
            return function(self, *args, **kwargs)

    return cast(_F, synchronous)
