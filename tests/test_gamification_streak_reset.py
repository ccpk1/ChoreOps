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

    Only ``coordinator.assignees_data`` and ``coordinator.chores_data`` are
    exercised by the helpers under test; no async_setup is run, so no listeners or
    startup hooks are registered.
    """
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.assignees_data = {}
    coordinator.chores_data = {}
    return GamificationManager(hass, coordinator)


DAILY_CHORE: dict[str, Any] = {
    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
    const.DATA_CHORE_APPLICABLE_DAYS: [],
}

WEEKLY_CHORE_TEMPLATE: dict[str, Any] = {
    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
    const.DATA_CHORE_APPLICABLE_DAYS: [],
}
"""Weekly chore whose applicable day is filled in per test, see below."""


def _weekly_chore_due_today() -> dict[str, Any]:
    """A weekly chore recurrring on today's weekday only.

    Its occurrences are therefore exactly seven days apart, so a window shorter
    than a week cannot contain one. That makes the assertions below independent of
    which weekday the suite happens to run on - unlike a hardcoded "mon", which
    would pass or fail depending on the calendar.
    """
    return {
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
        const.DATA_CHORE_APPLICABLE_DAYS: [dt_today_local().strftime("%a").lower()],
    }


def _set_chore_definitions(
    manager: GamificationManager,
    definitions: dict[str, dict[str, Any]],
) -> None:
    """Install chore definitions on the mock coordinator."""
    manager.coordinator.chores_data.update(definitions)


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
    ("value", "case"),
    [
        pytest.param(None, "missing", id="missing"),
        pytest.param("", "empty", id="empty"),
        pytest.param("not-a-date", "unparseable", id="unparseable"),
    ],
)
def test_streak_alive_breaks_on_unreadable_data(
    manager: GamificationManager, value: Any, case: str
) -> None:
    """Unreadable data breaks the streak rather than preserving it (decision 19).

    A positive streak implies a completion timestamp exists, so its absence is a
    defect. Silently continuing would mask it, so the streak breaks and the user
    can report the bug.
    """
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})

    assert manager._streak_alive("chore-a", value) is False, case


def test_streak_alive_breaks_when_chore_is_unknown(
    manager: GamificationManager,
) -> None:
    """An unknown chore cannot be evaluated, so it breaks for the same reason."""
    assert manager._streak_alive("missing-chore", _date_str(0)) is False


@pytest.mark.parametrize(
    ("days_ago", "expected", "case"),
    [
        pytest.param(0, True, "today", id="today"),
        pytest.param(1, True, "yesterday", id="yesterday"),
        pytest.param(2, False, "two-days-ago", id="two-days-ago"),
    ],
)
def test_streak_alive_daily_chore_window(
    manager: GamificationManager, days_ago: int, expected: bool, case: str
) -> None:
    """A daily chore keeps its streak while no day passed unmet.

    Mirrors the previous today-or-yesterday rule for daily chores, now derived
    from the schedule instead of the calendar.
    """
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})

    assert manager._streak_alive("chore-a", _date_str(days_ago)) is expected, case


def test_streak_alive_weekly_chore_survives_its_off_days(
    manager: GamificationManager,
) -> None:
    """A weekly chore's streak survives the days it is not owed.

    This is conflict C2, the defect this tranche exists to fix: the old calendar
    gate zeroed a valid weekly streak as soon as the last completion was more than
    a day old. Three days is still more than a day, so the old rule would call this
    dead.
    """
    _set_chore_definitions(manager, {"chore-a": _weekly_chore_due_today()})

    assert manager._streak_alive("chore-a", _date_str(3)) is True


def test_streak_alive_weekly_chore_breaks_after_a_skipped_occurrence(
    manager: GamificationManager,
) -> None:
    """The weekly exemption must not make a streak immortal.

    A gap longer than the recurrence interval contains an occurrence, so the
    streak breaks. Without this, the fix for C2 would trade a false break for a
    false hold.
    """
    _set_chore_definitions(manager, {"chore-a": _weekly_chore_due_today()})

    assert manager._streak_alive("chore-a", _date_str(8)) is False


@pytest.mark.parametrize(
    ("days_ago", "expected", "case"),
    [
        pytest.param(0, True, "today", id="today"),
        pytest.param(1, True, "yesterday", id="yesterday"),
        pytest.param(2, False, "two-days-ago", id="two-days-ago"),
    ],
)
def test_streak_alive_handles_datetime_strings(
    manager: GamificationManager, days_ago: int, expected: bool, case: str
) -> None:
    """ISO datetime strings (with ``T`` and tz) are parsed and localized correctly."""
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})

    assert manager._streak_alive("chore-a", _datetime_str(days_ago)) is expected, case


def test_streak_alive_todays_pending_occurrence_does_not_break(
    manager: GamificationManager,
) -> None:
    """A chore completed yesterday stays alive while today is still in progress.

    The window ends at the **start of today**, not "now", so today's not-yet-done
    occurrence is not read as missed. Ending it at "now" would break a valid streak
    mid-day, which is the #294 symptom in the achievement path.
    """
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})

    assert manager._streak_alive("chore-a", _date_str(1)) is True


@pytest.mark.parametrize(
    ("days_ago", "expected", "case"),
    [
        pytest.param(1, True, "consecutive-day-continues", id="consecutive-day"),
        pytest.param(2, False, "skipped-day-breaks", id="skipped-day"),
    ],
)
def test_streak_alive_unscheduled_chore_follows_daily_rules(
    manager: GamificationManager, days_ago: int, expected: bool, case: str
) -> None:
    """A chore with no schedule is inferred as daily (decision 18).

    Previously such a chore could never report a miss, so an achievement streak
    over it froze at whatever value it reached. It now behaves as a daily streak:
    consecutive days build it, a skipped day breaks it.
    """
    _set_chore_definitions(
        manager,
        {
            "chore-a": {
                const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_NONE,
                const.DATA_CHORE_APPLICABLE_DAYS: [],
            }
        },
    )

    assert manager._streak_alive("chore-a", _date_str(days_ago)) is expected, case


# =============================================================================
# B2. Manager -- _get_tracked_current_streak only counts alive streaks
# =============================================================================


def test_tracked_streak_fresh_chore_counts(manager: GamificationManager) -> None:
    """A chore completed today contributes its full streak."""
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})
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
    """A high streak with a missed occurrence behind it counts as 0."""
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})
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
    _set_chore_definitions(
        manager,
        {"stale-high": DAILY_CHORE, "fresh-low": DAILY_CHORE},
    )
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
    _set_chore_definitions(
        manager,
        {"stale-high": DAILY_CHORE, "fresh-low": DAILY_CHORE},
    )
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


def test_tracked_streak_missing_timestamp_breaks_the_streak(
    manager: GamificationManager,
) -> None:
    """A positive streak with no last_completed is a data defect, so it breaks.

    Decision 19: an unreadable value must surface the problem rather than
    continuing the streak and masking it. Should be unreachable in practice
    (completions always write both fields), hence asserted explicitly.
    """
    _set_chore_definitions(manager, {"chore-a": DAILY_CHORE})
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
    assert manager._get_tracked_current_streak("kid", ["chore-a"]) == 0
