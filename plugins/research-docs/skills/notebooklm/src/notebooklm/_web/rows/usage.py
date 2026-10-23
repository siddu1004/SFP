"""Typed positional views for the live usage-meter Web responses.

The batchexecute transport represents protobuf messages as elision-aware
arrays.  This module is the single owner of the recovered field positions so
the feature adapter can validate named values without indexing raw payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


def _at(value: Any, position: int) -> Any:
    """Return an array slot while treating an elided field as absent."""

    return value[position] if isinstance(value, list) and position < len(value) else None


@dataclass(frozen=True)
class UsageTimestampRow:
    """View of a JSPB ``Timestamp`` pair: ``[seconds, nanos]``."""

    _raw: Any = field(repr=False)

    _SECONDS_POS: ClassVar[int] = 0
    _NANOS_POS: ClassVar[int] = 1

    @property
    def is_well_formed_container(self) -> bool:
        return isinstance(self._raw, list) and bool(self._raw)

    @property
    def seconds(self) -> Any:
        return _at(self._raw, self._SECONDS_POS)

    @property
    def nanos(self) -> Any:
        return _at(self._raw, self._NANOS_POS)


@dataclass(frozen=True)
class UsageAccountEnvelopeRow:
    """View of the direct or one/two-envelope ``GetAccount`` response."""

    _raw: Any = field(repr=False)

    _ENVELOPE_POS: ClassVar[int] = 0
    _PREMIUM_USER_INFO_POS: ClassVar[int] = 4
    _COMPUTE_METERING_ENABLED_POS: ClassVar[int] = 6

    @property
    def compute_metering_enabled(self) -> bool:
        first_envelope = _at(self._raw, self._ENVELOPE_POS)
        candidates = (
            self._raw,
            first_envelope,
            _at(first_envelope, self._ENVELOPE_POS),
        )
        for account in candidates:
            premium = _at(account, self._PREMIUM_USER_INFO_POS)
            enabled = _at(premium, self._COMPUTE_METERING_ENABLED_POS)
            if isinstance(enabled, bool):
                return enabled
        return False


@dataclass(frozen=True)
class UsageWindowRow:
    """View of one quota-window summary row."""

    _raw: Any = field(repr=False)

    _WINDOW_POS: ClassVar[int] = 4
    _RESET_POS: ClassVar[int] = 5
    _USED_PERCENT_POS: ClassVar[int] = 6
    _REMAINING_PERCENT_POS: ClassVar[int] = 7

    @property
    def is_array(self) -> bool:
        return isinstance(self._raw, list)

    @property
    def window_code(self) -> Any:
        return _at(self._raw, self._WINDOW_POS)

    @property
    def reset_timestamp(self) -> Any:
        return _at(self._raw, self._RESET_POS)

    @property
    def used_percent(self) -> Any:
        return _at(self._raw, self._USED_PERCENT_POS)

    @property
    def remaining_percent(self) -> Any:
        return _at(self._raw, self._REMAINING_PERCENT_POS)


@dataclass(frozen=True)
class UsageActionRow:
    """View of one per-action quota summary row."""

    _raw: Any = field(repr=False)

    _ACTION_POS: ClassVar[int] = 0
    _HAS_QUOTA_POS: ClassVar[int] = 1
    _DEFERRED_GENERATIONS_POS: ClassVar[int] = 2
    _COST_TIER_POS: ClassVar[int] = 3
    _ESTIMATED_COST_POS: ClassVar[int] = 5

    @property
    def is_array(self) -> bool:
        return isinstance(self._raw, list)

    @property
    def action_code(self) -> Any:
        return _at(self._raw, self._ACTION_POS)

    @property
    def has_sufficient_quota(self) -> Any:
        return _at(self._raw, self._HAS_QUOTA_POS)

    @property
    def remaining_deferred_artifact_generations(self) -> Any:
        return _at(self._raw, self._DEFERRED_GENERATIONS_POS)

    @property
    def cost_tier_code(self) -> Any:
        return _at(self._raw, self._COST_TIER_POS)

    @property
    def estimated_cost_percent(self) -> Any:
        return _at(self._raw, self._ESTIMATED_COST_POS)


@dataclass(frozen=True)
class UsageSummaryRow:
    """View of the top-level ``ListQuotaSummary`` response."""

    _raw: Any = field(repr=False)

    _STATUS_POS: ClassVar[int] = 0
    _WINDOWS_POS: ClassVar[int] = 1
    _ACTIONS_POS: ClassVar[int] = 3

    @property
    def is_array(self) -> bool:
        return isinstance(self._raw, list)

    @property
    def status_code(self) -> Any:
        return _at(self._raw, self._STATUS_POS)

    @property
    def windows(self) -> Any:
        return _at(self._raw, self._WINDOWS_POS)

    @property
    def actions(self) -> Any:
        return _at(self._raw, self._ACTIONS_POS)


__all__ = [
    "UsageAccountEnvelopeRow",
    "UsageActionRow",
    "UsageSummaryRow",
    "UsageTimestampRow",
    "UsageWindowRow",
]
