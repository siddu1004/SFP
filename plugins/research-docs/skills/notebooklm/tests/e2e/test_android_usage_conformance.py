"""Opt-in, read-only Web/Android usage-meter parity qualification.

Run each tier in a separate process so ``NOTEBOOKLM_PROFILE`` never changes
inside a test process::

    NOTEBOOKLM_PROFILE=YOUR_STANDARD_PROFILE NOTEBOOKLM_ANDROID_USAGE_CONFORMANCE=1 \
      uv run pytest tests/e2e/test_android_usage_conformance.py -v
    NOTEBOOKLM_PROFILE=YOUR_PRO_PROFILE NOTEBOOKLM_ANDROID_USAGE_CONFORMANCE=1 \
      uv run pytest tests/e2e/test_android_usage_conformance.py -v

The test performs account/quota reads only and never generates an artifact.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

from notebooklm import NotebookLMClient

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.readonly,
    pytest.mark.skipif(
        os.environ.get("NOTEBOOKLM_ANDROID_USAGE_CONFORMANCE") != "1",
        reason="set NOTEBOOKLM_ANDROID_USAGE_CONFORMANCE=1 for the live Android gate",
    ),
]


async def test_android_usage_matches_web_for_one_explicit_profile() -> None:
    assert os.environ.get("NOTEBOOKLM_PROFILE"), "use an explicit isolated profile"

    async with NotebookLMClient.from_storage(backend="android") as android:
        assert android.backends["settings"] == "android"
        native = await android.settings.get_usage()

    async with NotebookLMClient.from_storage(backend="web") as web:
        browser = await web.settings.get_usage()

    assert native.status == browser.status
    assert native.actions == browser.actions
    assert len(native.windows) == len(browser.windows)
    for native_window, browser_window in zip(native.windows, browser.windows, strict=True):
        assert native_window.kind == browser_window.kind
        assert native_window.used_percent == browser_window.used_percent
        assert native_window.remaining_percent == browser_window.remaining_percent
        # Unused windows slide with wall clock, while charged windows are
        # anchored. Bound only the sequential-read timing delta.
        assert abs(native_window.resets_at - browser_window.resets_at) < timedelta(seconds=30)
