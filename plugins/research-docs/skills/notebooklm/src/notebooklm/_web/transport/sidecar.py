"""Lazy compatibility export for the root-owned deprecated Web sidecar."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..._client_compat import LazyWebSidecar


def __getattr__(name: str) -> object:
    if name != "LazyWebSidecar":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from ..._client_compat import LazyWebSidecar

    return LazyWebSidecar


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})


__all__ = ["LazyWebSidecar"]
