"""Bound recovery execution under the existing profile-wide cross-process lock."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from pathlib import Path


async def run_bound_refresh(
    storage_path: Path,
    profile: str | None,
    *,
    runner: Callable[[Path, str | None], Awaitable[None]],
    lock_path: Path | None,
    flock: Callable[[Path], AbstractContextManager[bool]],
    wait_for_holder: Callable[[Path], Awaitable[bool]],
) -> None:
    """Wait for incompatible writers, then execute this policy's own command.

    A different policy's successful subprocess cannot stand in for this policy.
    The physical lock remains per profile, so differing policies still serialize
    their storage writes. Contention is bounded by the existing holder wait.
    """
    if lock_path is None:
        await runner(storage_path, profile)
        return
    for _ in range(3):
        with flock(lock_path) as acquired:
            if acquired:
                await runner(storage_path, profile)
                return
        await wait_for_holder(lock_path)
    raise RuntimeError("Authentication recovery profile remained busy")
