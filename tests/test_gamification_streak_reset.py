"""Regression tests: completion-streak achievements must reset after a missed day.

Background (bug fixed alongside these tests): the COMPLETION_STREAK achievement
progress was computed as ``max(stored_streak, tracked_streak)``. The stored value
was only ever written from that same ``max()``, so it behaved as a monotonic
high-water-mark that could never decrease -- a kid's streak would stay at its peak
forever, even after fully missing one or more days.

The fix has two required parts:

A. Engine (``GamificationEngine._evaluate_canonical_target_criterion``): the
   COMPLETION_STREAK branch now uses the freshly tracked streak alone, never the
   stored high-water-mark.

B. Manager (``GamificationManager._get_tracked_current_streak`` /
   ``_streak_alive``): a chore's stored streak only counts if it was last
   completed today or yesterday, so a fully missed day resets it.

These are pure-logic tests -- no Home Assistant runtime is started. The engine
criterion is a staticmethod; the manager helpers only touch
``coordinator.assignees_data``, so a MagicMock coordinator is sufficient.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.gamification_engine import GamificationEngine
from custom_components.choreops.managers.gamification_manager import GamificationManager
from custom_components.choreops.utils.dt_utils import dt_today_local

# =============================================================================
# Helpers
# =============================================================================


def _eval_streak(
    *,
    tracked: float,
    stored: float | None = None,
    threshold: float = 14.0,
) -> dict[str, Any]:
    """Evaluate the COMPLETION_STREAK criterion and return the criterion result.

    ``tracked`` is the freshly derived streak (``tracked_current_streak``);
    ``stored`` is the persisted high-water-mark, supplied only when a test wants
    to prove it is ignored.
    """
    context: dict[str, Any] = {"tracked_current_streak": tracked}
    if stored is not None:
        context["current_achievement_progress"] = {
            const.DATA_USER_CURRENT_STREAK: stored
        }
    target: dict[str, Any] = {
        "target_type": const.CANONICAL_TARGET_TYPE_COMPLETION_STREAK,
        "threshold_value": threshold,
    }
    return cast(
        "dict[str, Any]",
        GamificationEngine._evaluate_canonical_target_criterion(
            cast("Any", context),
            cast("Any", target),
        ),
    )


def _date_str(days_ago: int) -> str:
    """Date-only string (``YYYY-MM-DD``) ``days_ago`` days before local today."""
    return (dt_today_local() - timedelta(days=days_ago)).isoformat()


def _datetime_str(days_ago: int) -> str:
    """ISO datetime string (with ``T`` and tz) ``days_ago`` days before today."""
    day = dt_today_local() - timedelta(days=days_ago)
    return datetime.combine(day, time(12, 0), tzinfo=UTC).isoformat()


@pytest.fixture
def manager() -> GamificationManager:
    """A GamificationManager with mock hass/coordinator and empty chore data.

    Only ``coordinator.assignees_data`` is exercised by the helpers under test;
    no async_setup is run, so no listeners or startup hooks are registered.
    """
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.assignees_data = {}
    return GamificationManager(hass, coordinator)


def _set_chores(
    manager: GamificationManager,
    assignee_id: str,
    chores: dict[str, dict[str, Any]],
) -> None:
    """Install ``chores`` as the assignee's per-chore data on the mock coordinator."""
    manager.coordinator.assignees_data[assignee_id] = {
        const.DATA_USER_CHORE_DATA: chores
    }


# =============================================================================
# A. Engine -- COMPLETION_STREAK uses tracked value, not max(stored, tracked)
# =============================================================================


def test_engine_streak_ignores_stale_stored_high_water_mark() -> None:
    """Regression guard: a high stored streak must not pin the value above tracked.

    This is the exact bug: stored=7 (peak), tracked=4 (current). Result must be 4.
    """
    result = _eval_streak(tracked=4, stored=7, threshold=14.0)
    assert result["current_value"] == 4.0
    assert "4.0/14.0" in result["reason"]


def test_engine_streak_zero_when_tracked_zero_despite_high_stored() -> None:
    """A fully reset streak (tracked=0) reports 0 even with a large stored peak."""
    result = _eval_streak(tracked=0, stored=30, threshold=14.0)
    assert result["current_value"] == 0.0
    assert result["progress"] == 0.0
    assert result["met"] is False


def test_engine_streak_progress_and_met() -> None:
    """Progress is tracked/threshold; met flips once the threshold is reached."""
    partial = _eval_streak(tracked=4, threshold=14.0)
    assert partial["current_value"] == 4.0
    assert partial["progress"] == pytest.approx(4.0 / 14.0)
    assert partial["met"] is False

    reached = _eval_streak(tracked=14, threshold=14.0)
    assert reached["current_value"] == 14.0
    assert reached["progress"] == 1.0
    assert reached["met"] is True


# =============================================================================
# B1. Manager -- _streak_alive staleness window
# =============================================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),  # missing -> fail open
        ("", True),  # empty -> fail open
        ("not-a-date", True),  # unparseable -> fail open
    ],
)
def test_streak_alive_fails_open(
    manager: GamificationManager, value: Any, expected: bool
) -> None:
    """Missing or unparseable values fail open so a valid streak is never zeroed."""
    assert manager._streak_alive(value) is expected


def test_streak_alive_today_and_yesterday(manager: GamificationManager) -> None:
    """Today and yesterday are both inside the inclusive window (alive)."""
    assert manager._streak_alive(_date_str(0)) is True
    assert manager._streak_alive(_date_str(1)) is True


def test_streak_alive_two_days_ago_is_dead(manager: GamificationManager) -> None:
    """A gap of a full missed day (last completion 2 days ago) breaks the streak."""
    assert manager._streak_alive(_date_str(2)) is False


def test_streak_alive_handles_datetime_strings(
    manager: GamificationManager,
) -> None:
    """ISO datetime strings (with ``T`` and tz) are parsed and localized correctly."""
    assert manager._streak_alive(_datetime_str(0)) is True
    assert manager._streak_alive(_datetime_str(1)) is True
    assert manager._streak_alive(_datetime_str(2)) is False


# =============================================================================
# B2. Manager -- _get_tracked_current_streak only counts alive streaks
# =============================================================================


def test_tracked_streak_fresh_chore_counts(manager: GamificationManager) -> None:
    """A chore completed today contributes its full streak."""
    _set_chores(
        manager,
        "kid",
        {
            "chore-a": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 4,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(0),
            }
        },
    )
    assert manager._get_tracked_current_streak("kid", ["chore-a"]) == 4


def test_tracked_streak_stale_chore_resets_to_zero(
    manager: GamificationManager,
) -> None:
    """A high streak with a last completion older than yesterday counts as 0."""
    _set_chores(
        manager,
        "kid",
        {
            "chore-a": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 9,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(3),
            }
        },
    )
    assert manager._get_tracked_current_streak("kid", ["chore-a"]) == 0


def test_tracked_streak_fresh_beats_stale_high(
    manager: GamificationManager,
) -> None:
    """max() returns the best *alive* streak; a stale high streak does not win."""
    _set_chores(
        manager,
        "kid",
        {
            "stale-high": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 9,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(3),
            },
            "fresh-low": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 4,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(0),
            },
        },
    )
    assert manager._get_tracked_current_streak("kid", ["stale-high", "fresh-low"]) == 4


def test_tracked_streak_zero_streak_short_circuits(
    manager: GamificationManager,
) -> None:
    """A non-positive streak contributes 0 regardless of last-completed."""
    _set_chores(
        manager,
        "kid",
        {
            "chore-a": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 0,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(0),
            }
        },
    )
    assert manager._get_tracked_current_streak("kid", ["chore-a"]) == 0


def test_tracked_streak_fallback_branch_scans_all_chores(
    manager: GamificationManager,
) -> None:
    """With no tracked_chores list, all chores are scanned (alive ones only)."""
    _set_chores(
        manager,
        "kid",
        {
            "stale-high": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 9,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(3),
            },
            "fresh-low": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 4,
                const.DATA_USER_CHORE_DATA_LAST_COMPLETED: _date_str(0),
            },
        },
    )
    assert manager._get_tracked_current_streak("kid", []) == 4


def test_tracked_streak_missing_timestamp_fails_open(
    manager: GamificationManager,
) -> None:
    """Documents the accepted caveat: a positive streak with no last_completed.

    _streak_alive fails open on missing data, so such a chore keeps its streak.
    This should be unreachable in practice (completions always write both fields)
    but is asserted here so the trade-off is a deliberate, visible decision.
    """
    _set_chores(
        manager,
        "kid",
        {
            "chore-a": {
                const.DATA_USER_CHORE_DATA_CURRENT_STREAK: 5,
                # no DATA_USER_CHORE_DATA_LAST_COMPLETED
            }
        },
    )
    assert manager._get_tracked_current_streak("kid", ["chore-a"]) == 5
