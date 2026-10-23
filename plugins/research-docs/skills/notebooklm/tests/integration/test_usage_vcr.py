"""Read-only Web usage-meter VCR coverage.

Recording instructions (run each process separately, never switch identity in
one process)::

    NOTEBOOKLM_PROFILE=YOUR_STANDARD_PROFILE NOTEBOOKLM_VCR_RECORD=1 \
      uv run pytest tests/integration/test_usage_vcr.py::TestUsageVCR::test_standard_usage -v
    NOTEBOOKLM_PROFILE=YOUR_PRO_PROFILE NOTEBOOKLM_VCR_RECORD=1 \
      uv run pytest tests/integration/test_usage_vcr.py::TestUsageVCR::test_pro_usage -v

Both tests are read-only and issue ``GetAccount`` followed by
``ListQuotaSummary`` when the account's compute-meter bit is enabled.  The
committed cassettes must remain separate because account-tier values and reset
timestamps are profile-specific.  Numeric percentages are intentionally only
checked for finite values: VCR sanitization may rewrite their exact values.
"""

from __future__ import annotations

import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from notebooklm import NotebookLMClient
from notebooklm.rpc import RPCMethod
from tests.integration.conftest import get_vcr_auth
from tests.vcr_config import notebooklm_vcr

try:
    from notebooklm.types import UsageActionKind, UsageSummaryStatus, UsageWindowKind
except ImportError:  # Public usage models land in the sibling integration branch.
    pytest.skip("Usage public models are not available yet", allow_module_level=True)


pytestmark = pytest.mark.vcr
_CASSETTES = Path(__file__).parents[1] / "cassettes" / "web"
_RECORDING = os.environ.get("NOTEBOOKLM_VCR_RECORD", "").casefold() in {"1", "true", "yes"}


@asynccontextmanager
async def _vcr_client():
    auth = await get_vcr_auth()
    async with NotebookLMClient(auth) as client:
        yield client


def _skip_until_recorded(name: str) -> None:
    if not _RECORDING and not (_CASSETTES / name).is_file():
        pytest.skip(f"{name} is not recorded yet; set NOTEBOOKLM_VCR_RECORD=1 to record")


def _assert_cassette_covers_usage_reads(name: str) -> None:
    """Pin that each committed recording contains both usage RPC requests."""

    path = _CASSETTES / name
    if not path.is_file():
        return  # VCR writes the cassette after the recording test returns.
    body = path.read_text(encoding="utf-8")
    for method in (RPCMethod.GET_ACCOUNT, RPCMethod.LIST_QUOTA_SUMMARY):
        assert method.value in body, f"{name} does not record {method.name} ({method.value})"


def _assert_usage_summary(summary) -> None:
    assert summary.status is UsageSummaryStatus.READY
    assert {window.kind for window in summary.windows} == {
        UsageWindowKind.FIVE_HOUR,
        UsageWindowKind.WEEKLY,
    }
    assert len(summary.windows) == 2
    for window in summary.windows:
        assert math.isfinite(window.used_percent)
        assert math.isfinite(window.remaining_percent)
        assert window.resets_at.tzinfo is not None

    # These action rows are stable in both recorded tiers and pin the
    # transport's action-code translation without pinning sanitized prices.
    assert summary.action(UsageActionKind.FLASHCARDS) is not None
    assert summary.action(UsageActionKind.QUIZ) is not None
    assert summary.action(UsageActionKind.DEEP_RESEARCH) is not None
    assert all(action.code > 0 for action in summary.actions)


class TestUsageVCR:
    @pytest.mark.asyncio
    @notebooklm_vcr.use_cassette("usage_standard.yaml")
    async def test_standard_usage(self) -> None:
        """Replay the Standard/free read-only usage snapshot."""

        _skip_until_recorded("usage_standard.yaml")
        async with _vcr_client() as client:
            summary = await client.settings.get_usage()
        _assert_usage_summary(summary)
        _assert_cassette_covers_usage_reads("usage_standard.yaml")

    @pytest.mark.asyncio
    @notebooklm_vcr.use_cassette("usage_pro.yaml")
    async def test_pro_usage(self) -> None:
        """Replay the Pro read-only usage snapshot."""

        _skip_until_recorded("usage_pro.yaml")
        async with _vcr_client() as client:
            summary = await client.settings.get_usage()
        _assert_usage_summary(summary)
        _assert_cassette_covers_usage_reads("usage_pro.yaml")
