"""Task-local injection of resolved Web policy into shared auth helpers.

This context carries immutable policy only, never live cookies or account routing.
Owners establish it explicitly; standalone calls retain dynamic environment resolution.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol


class BoundRequestPolicy(Protocol):
    @property
    def environment(self) -> Mapping[str, str | None]: ...

    @property
    def identity(self) -> str: ...


_CURRENT: ContextVar[BoundRequestPolicy | None] = ContextVar("notebooklm_web_policy", default=None)


@contextmanager
def request_policy_scope(policy: BoundRequestPolicy | None) -> Iterator[None]:
    token = _CURRENT.set(policy)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def policy_env(name: str, default: str | None = None) -> str | None:
    policy = _CURRENT.get()
    if policy is not None and name in policy.environment:
        value = policy.environment[name]
        return default if value is None else value
    return os.environ.get(name, default)


def policy_child_environment() -> dict[str, str]:
    """Overlay only selected policy keys onto the environment at spawn time."""
    result = os.environ.copy()
    policy = _CURRENT.get()
    if policy is not None:
        for name, value in policy.environment.items():
            if value is None:
                result.pop(name, None)
            else:
                result[name] = value
    return result


def policy_key(key: str) -> str:
    """Opaque policy-qualified flight/epoch identity, never an execution command."""
    policy = _CURRENT.get()
    return key if policy is None else f"{key}\0{policy.identity}"


def has_bound_policy() -> bool:
    return _CURRENT.get() is not None
