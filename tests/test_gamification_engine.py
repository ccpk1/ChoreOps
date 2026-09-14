"""Unit tests for GamificationEngine - pure Python logic tests.

These tests verify the stateless gamification evaluation without any Home Assistant
mocking. The GamificationEngine is a pure Python module with no HA dependencies.

Test Categories:
- Points criterion evaluation (_evaluate_points)
- Chore count criterion evaluation (_evaluate_chore_count)
- Daily completion criterion evaluation (_evaluate_daily_completion)
- Streak criterion evaluation (_evaluate_streak)
- Badge evaluation full flow (evaluate_badge)
- Achievement evaluation (evaluate_achievement)
- Challenge evaluation (evaluate_challenge)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.gamification_engine import GamificationEngine

if TYPE_CHECKING:
    from custom_components.choreops.type_defs import EvaluationContext

# =============================================================================
# TEST FIXTURES - Minimal context builders
# =============================================================================


def make_context(
    *,
    assignee_id: str = "test-assignee-123",
    current_points: float = 0.0,
    total_points_earned: float = 0.0,
    points_cycle_count: int = 0,
    chores_cycle_count: int = 0,
    days_cycle_count: int = 0,
    today_points: float = 0.0,
    today_approved: int = 0,
    approved_count: int = 0,
    total_count: int = 0,
    due_count: int | None = None,
    approved_due_today: int | None = None,
    missed_since_advance: bool = False,
    has_overdue: bool = False,
    cycle_failed: bool = False,
    approved_all_time: int = 0,
    last_update_day: str | None = None,
    today_iso: str | None = None,
    cumulative_baseline: float = 0.0,
    cumulative_cycle_points: float = 0.0,
) -> EvaluationContext:
    """Build a minimal EvaluationContext for testing.

    This creates the context structure that GamificationEngine expects.

    `due_count` / `approved_due_today` default to the all-tracked counts, so a
    context describes a day where every tracked chore is owed unless a test says
    otherwise.
    """
    effective_due_count = total_count if due_count is None else due_count
    effective_approved_due = (
        approved_count if approved_due_today is None else approved_due_today
    )
    return cast(
        "EvaluationContext",
        {
            "assignee_id": assignee_id,
            "current_points": current_points,
            "total_points_earned": total_points_earned,
            "current_badge_progress": {
                const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT: points_cycle_count,
                const.DATA_USER_BADGE_PROGRESS_CHORES_CYCLE_COUNT: chores_cycle_count,
                const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT: days_cycle_count,
                const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY: last_update_day,
            },
            "today_stats": {
                "today_points": today_points,
                "today_approved": today_approved,
                "total_earned": total_points_earned,
            },
            "today_completion": {
                "approved_count": approved_count,
                "total_count": total_count,
                "due_count": effective_due_count,
                "approved_due_today": effective_approved_due,
                "missed_since_advance": missed_since_advance,
                "has_overdue": has_overdue,
                "cycle_failed": cycle_failed,
            },
            "today_completion_due": {
                "approved_count": approved_count,
                "total_count": total_count,
                "due_count": effective_due_count,
                "approved_due_today": effective_approved_due,
                "missed_since_advance": missed_since_advance,
                "has_overdue": has_overdue,
                "cycle_failed": cycle_failed,
            },
            # v43+: chore_stats deleted, use chore_periods_all_time
            "chore_periods_all_time": {
                const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: approved_all_time,
            },
            "achievement_progress": {},
            "today_iso": today_iso or datetime.now(UTC).date().isoformat(),
            # Required fields for EvaluationContext TypedDict
            "badge_progress": {},
            "cumulative_badge_progress": {
                "baseline_points": cumulative_baseline,
                "cycle_points": cumulative_cycle_points,
            },
            "badges_earned": {},
        },
    )


def make_badge_target(
    *,
    target_type: str = const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
    threshold: int = 100,
    maintenance_rules: int | None = None,
) -> dict[str, Any]:
    """Build a minimal badge target dict."""
    target = {
        const.DATA_BADGE_TARGET_TYPE: target_type,
        const.DATA_BADGE_TARGET_THRESHOLD_VALUE: threshold,
    }
    if maintenance_rules is not None:
        target[const.DATA_BADGE_MAINTENANCE_RULES] = maintenance_rules
    return target


def make_badge(
    *,
    badge_id: str = "badge-123",
    name: str = "Test Badge",
    target_type: str = const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
    threshold: int = 100,
    badge_type: str = const.BADGE_TYPE_CUMULATIVE,
    maintenance_rules: int | None = None,
) -> dict[str, Any]:
    """Build a minimal badge definition."""
    return {
        const.DATA_BADGE_ID: badge_id,
        const.DATA_BADGE_NAME: name,
        const.DATA_BADGE_TYPE: badge_type,
        const.DATA_BADGE_TARGET: make_badge_target(
            target_type=target_type,
            threshold=threshold,
            maintenance_rules=maintenance_rules,
        ),
    }


def make_achievement(
    *,
    achievement_id: str = "achieve-123",
    name: str = "Test Achievement",
    target_type: str = const.ACHIEVEMENT_TYPE_TOTAL,
    target_value: int = 10,
    source_badge_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal achievement definition."""
    achievement = {
        const.DATA_ACHIEVEMENT_ID: achievement_id,
        const.DATA_ACHIEVEMENT_NAME: name,
        const.DATA_ACHIEVEMENT_TYPE: target_type,
        const.DATA_ACHIEVEMENT_TARGET_VALUE: target_value,
    }
    if source_badge_id:
        achievement[const.DATA_ACHIEVEMENT_SOURCE_BADGE_ID] = source_badge_id
    return achievement


def make_challenge(
    *,
    challenge_id: str = "challenge-123",
    name: str = "Test Challenge",
    challenge_type: str = "",
    target_value: int = 5,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Build a minimal challenge definition."""
    today = datetime.now(UTC).date().isoformat()
    return {
        const.DATA_CHALLENGE_ID: challenge_id,
        const.DATA_CHALLENGE_NAME: name,
        const.DATA_CHALLENGE_TYPE: challenge_type
        or const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW,
        const.DATA_CHALLENGE_TARGET_VALUE: target_value,
        const.DATA_CHALLENGE_START_DATE: start_date or today,
        const.DATA_CHALLENGE_END_DATE: end_date or today,
    }


# =============================================================================
# TEST: _evaluate_points
# =============================================================================


class TestEvaluatePoints:
    """Tests for points criterion evaluation."""

    def test_below_threshold_returns_not_met(self) -> None:
        """Points below threshold returns met=False."""
        context = make_context(today_points=50)  # Periodic badge uses today_points
        badge_data = make_badge(threshold=100)
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_points(context, target)

        assert result["met"] is False
        assert result["current_value"] == 50
        assert result["threshold"] == 100
        assert result["progress"] == 0.5

    def test_at_threshold_returns_met(self) -> None:
        """Points at threshold returns met=True."""
        context = make_context(today_points=100)
        badge_data = make_badge(threshold=100)
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_points(context, target)

        assert result["met"] is True
        assert result["current_value"] == 100
        assert result["progress"] == 1.0

    def test_above_threshold_returns_met(self) -> None:
        """Points above threshold returns met=True."""
        context = make_context(today_points=150)
        badge_data = make_badge(threshold=100)
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_points(context, target)

        assert result["met"] is True
        assert result["current_value"] == 150
        assert result["progress"] == 1.0  # Capped at 1.0

    def test_zero_threshold_returns_met(self) -> None:
        """Zero threshold always returns met=True (any value >= 0)."""
        context = make_context(total_points_earned=50)
        badge_data = make_badge(threshold=0)
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_points(context, target)

        # When threshold=0, current >= 0 is always True
        assert result["met"] is True
        # Progress is 0.0 to avoid division by zero
        assert result["progress"] == 0.0

    def test_progress_calculation(self) -> None:
        """Progress percentage calculated correctly."""
        context = make_context(today_points=25)  # Periodic badge uses today_points
        badge_data = make_badge(threshold=100)
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_points(context, target)

        assert result["progress"] == 0.25
        assert result["current_value"] == 25

    def test_window_points_prevents_same_day_double_count(self) -> None:
        """Canonical window points take precedence over additive cycle math."""
        context = make_context(points_cycle_count=5, today_points=5)
        context["today_stats"]["window_points"] = 5.0
        badge_data = make_badge(threshold=50)
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_points(context, target)

        assert result["met"] is False
        assert result["current_value"] == 5.0
        assert result["progress"] == 0.1


# =============================================================================
# TEST: _evaluate_chore_count
# =============================================================================


class TestEvaluateChoreCount:
    """Tests for chore count criterion evaluation."""

    def test_below_threshold_returns_not_met(self) -> None:
        """Chore count below threshold returns met=False."""
        # Engine calculates: chores_cycle_count + today_approved
        context = make_context(chores_cycle_count=5, today_approved=3)
        badge_data = make_badge(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
            threshold=10,
        )
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_chore_count(context, target)

        assert result["met"] is False
        assert result["current_value"] == 8  # cycle_count(5) + today(3)
        assert result["threshold"] == 10

    def test_at_threshold_returns_met(self) -> None:
        """Chore count at threshold returns met=True."""
        # Engine calculates: chores_cycle_count + today_approved
        context = make_context(chores_cycle_count=5, today_approved=5)
        badge_data = make_badge(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
            threshold=10,
        )
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_chore_count(context, target)

        assert result["met"] is True
        assert result["current_value"] == 10  # cycle_count(5) + today(5)

    def test_zero_chores_returns_not_met(self) -> None:
        """Zero chores completed returns not met."""
        context = make_context(chores_cycle_count=0, today_approved=0)
        badge_data = make_badge(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
            threshold=10,
        )
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_chore_count(context, target)

        assert result["met"] is False
        assert result["current_value"] == 0
        assert result["progress"] == 0.0

    def test_window_approved_prevents_same_day_double_count(self) -> None:
        """Canonical window approvals take precedence over additive cycle math."""
        context = make_context(chores_cycle_count=1, today_approved=1)
        context["today_stats"]["window_approved"] = 1
        badge_data = make_badge(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
            threshold=3,
        )
        target = badge_data[const.DATA_BADGE_TARGET]

        result = GamificationEngine._evaluate_chore_count(context, target)

        assert result["met"] is False
        assert result["current_value"] == 1
        assert result["progress"] == pytest.approx(1 / 3)


# =============================================================================
# TEST: _evaluate_daily_completion
# =============================================================================


class TestEvaluateDailyCompletion:
    """Tests for daily completion criterion evaluation."""

    def test_100_percent_required_all_complete(self) -> None:
        """100% completion required, all chores complete → met."""
        context = make_context(
            days_cycle_count=5,
            approved_count=10,
            total_count=10,
            has_overdue=False,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=7,
        )

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False  # 5 + 1 = 6 < 7
        assert result["current_value"] == 6  # 5 + 1 for today meeting criteria

    def test_100_percent_required_partial_complete(self) -> None:
        """100% completion required, partial complete → not met."""
        context = make_context(
            days_cycle_count=5,
            approved_count=8,
            total_count=10,
            has_overdue=False,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=False
        )

        # Today doesn't meet 100%, so progress doesn't increment
        assert result["met"] is False

    def test_80_percent_required(self) -> None:
        """80% completion required, 80% complete → met."""
        context = make_context(
            days_cycle_count=6,
            approved_count=8,
            total_count=10,  # 80%
            has_overdue=False,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=0.8, only_due_today=False
        )

        assert result["met"] is True  # 6 + 1 = 7 >= threshold

    def test_no_overdue_constraint_fails_with_overdue(self) -> None:
        """No overdue constraint fails when overdue chores exist."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            has_overdue=True,  # Has overdue
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
            require_no_overdue=True,
        )

        # Even though 100% complete, overdue constraint fails
        assert result["met"] is False

    def test_zero_chores_returns_not_met(self) -> None:
        """Zero chores to complete returns not met."""
        context = make_context(
            days_cycle_count=0,
            approved_count=0,
            total_count=0,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False

    def test_same_day_re_evaluation_is_idempotent(self) -> None:
        """Same-day re-evaluation does not increment daily cycle twice."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            today_iso="2026-02-13",
            last_update_day="2026-02-13",
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
        )

        assert result["current_value"] == 6
        assert result["met"] is False

    def test_due_only_path_uses_due_snapshot(self) -> None:
        """Due-only evaluation reads today_completion_due values."""
        context = make_context(
            days_cycle_count=1,
            approved_count=0,
            total_count=0,
        )
        context["today_completion_due"] = {
            "approved_count": 2,
            "total_count": 2,
            "has_overdue": False,
        }
        target = make_badge_target(threshold=2)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=True,
        )

        assert result["current_value"] == 2
        assert result["met"] is True

    def test_no_overdue_variant_passes_when_none_overdue(self) -> None:
        """No-overdue variant can pass when completion is met and overdue is false."""
        context = make_context(
            days_cycle_count=4,
            approved_count=5,
            total_count=5,
            has_overdue=False,
        )
        target = make_badge_target(threshold=5)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
            require_no_overdue=True,
        )

        assert result["current_value"] == 5
        assert result["met"] is True

    def test_no_overdue_variant_fails_on_resolved_cycle_overdue(self) -> None:
        """Cycle failure fails the badge even when nothing is overdue right now.

        Mirrors the issue #293 report: a chore that went overdue earlier in the
        cycle and was since resolved must still block a no-overdue badge.
        """
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            has_overdue=False,
            cycle_failed=True,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
            require_no_overdue=True,
        )

        assert result["met"] is False
        assert result["current_value"] == 0

    def test_no_overdue_cycle_failure_clears_accumulated_progress(self) -> None:
        """Strict mode is a survival check: in-cycle lateness zeroes progress."""
        context = make_context(
            days_cycle_count=9,
            approved_count=10,
            total_count=10,
            cycle_failed=True,
        )
        target = make_badge_target(threshold=10)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
            require_no_overdue=True,
        )

        assert result["current_value"] == 0
        assert result["progress"] == 0.0

    def test_cycle_failure_is_ignored_without_no_overdue_requirement(self) -> None:
        """Cycle failure must not affect variants that do not require punctuality."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            cycle_failed=True,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
        )

        assert result["current_value"] == 7
        assert result["met"] is True


# =============================================================================
# TEST: _evaluate_streak
# =============================================================================


class TestEvaluateStreak:
    """Tests for streak criterion evaluation."""

    def test_streak_continues_when_today_meets_criteria(self) -> None:
        """The streak advances when today is satisfied and nothing was missed."""
        context = make_context(
            days_cycle_count=5,
            approved_count=10,
            total_count=10,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
            threshold=7,
        )

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False  # 5 + 1 = 6 < 7
        assert result["current_value"] == 6

    def test_streak_starts_at_one_when_no_credit_exists(self) -> None:
        """A satisfied day with no prior credit starts the streak at 1.

        Continuity is no longer inferred from calendar adjacency, so the only way
        to be starting fresh is to have no credited days at all.
        """
        context = make_context(
            days_cycle_count=0,
            approved_count=10,
            total_count=10,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False
        assert result["current_value"] == 1

    def test_streak_holds_while_today_is_still_in_progress(self) -> None:
        """An unmet day that is still in progress does not break the streak.

        Regression guard for issue #294: the nightly rollover evaluates a
        brand-new day with nothing approved yet, which used to zero the streak
        before any chore could be completed.
        """
        context = make_context(
            days_cycle_count=5,
            approved_count=5,
            total_count=10,  # Only 50%, but the day is not over
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False
        assert result["current_value"] == 5  # Streak held

    def test_streak_breaks_when_an_occurrence_was_missed(self) -> None:
        """The streak resets to 0 once a scheduled occurrence went unmet.

        The break signal is `missed_since_advance`, not calendar staleness: an
        unmet day that is still in progress holds (see the test above), while an
        occurrence that has actually passed unmet breaks.
        """
        context = make_context(
            days_cycle_count=5,
            approved_count=0,
            total_count=10,
            missed_since_advance=True,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False
        assert result["current_value"] == 0  # Streak broken

    def test_streak_breaks_on_a_miss_even_when_today_is_satisfied(self) -> None:
        """Today being satisfied does not rescue a streak with a missed occurrence.

        Precedence matters: the miss check runs before the advance branch, so a
        missed occurrence is not silently forgiven by a strong day.
        """
        context = make_context(
            days_cycle_count=5,
            approved_count=10,
            total_count=10,
            missed_since_advance=True,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 0

    def test_neutral_day_holds_the_streak(self) -> None:
        """A day with nothing owed neither advances nor breaks the streak."""
        context = make_context(
            days_cycle_count=5,
            approved_count=0,
            total_count=3,
            due_count=0,
            approved_due_today=0,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 5
        assert "nothing owed today" in result["reason"]

    def test_neutral_day_still_breaks_on_a_miss(self) -> None:
        """A missed occurrence breaks the streak even if today has nothing owed.

        Without this ordering a streak could survive indefinitely: an occurrence
        is missed, and every following day is neutral so nothing else reports it.
        """
        context = make_context(
            days_cycle_count=5,
            total_count=3,
            due_count=0,
            approved_due_today=0,
            missed_since_advance=True,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 0

    def test_non_due_chores_do_not_count_against_the_day(self) -> None:
        """A chore that is not owed today cannot make the day unsatisfiable.

        This is the defect the initiative exists to fix: scoring 4/5 because a
        weekly chore was not due made the day impossible and broke streaks.
        """
        context = make_context(
            days_cycle_count=5,
            approved_count=4,
            total_count=5,
            due_count=4,
            approved_due_today=4,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 6

    def test_streak_meets_threshold(self) -> None:
        """Streak meets threshold returns met=True."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is True
        assert result["current_value"] == 7

    def test_streak_same_day_re_evaluation_is_idempotent(self) -> None:
        """Same-day streak re-evaluation does not double increment."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            today_iso="2026-02-13",
            last_update_day="2026-02-13",
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
            threshold=7,
        )

        result = GamificationEngine._evaluate_streak(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
        )

        assert result["current_value"] == 6
        assert result["met"] is False

    def test_streak_due_only_path_uses_due_snapshot(self) -> None:
        """Due-only streak evaluation reads today_completion_due values."""
        context = make_context(
            days_cycle_count=4,
            approved_count=0,
            total_count=0,
        )
        context["today_completion_due"] = {
            "approved_count": 3,
            "total_count": 3,
            "due_count": 3,
            "approved_due_today": 3,
            "missed_since_advance": False,
            "has_overdue": False,
        }
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES,
            threshold=5,
        )

        result = GamificationEngine._evaluate_streak(
            context,
            target,
            percent_required=1.0,
            only_due_today=True,
        )

        assert result["current_value"] == 5
        assert result["met"] is True

    def test_streak_no_overdue_variant_fails_when_overdue(self) -> None:
        """No-overdue streak variant fails when overdue chores exist."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            has_overdue=True,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE,
            threshold=7,
        )

        result = GamificationEngine._evaluate_streak(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
            require_no_overdue=True,
        )

        assert result["current_value"] == 0
        assert result["met"] is False

    def test_streak_no_overdue_variant_fails_on_resolved_cycle_overdue(self) -> None:
        """No-overdue streak fails on in-cycle lateness that was since resolved."""
        context = make_context(
            days_cycle_count=6,
            approved_count=10,
            total_count=10,
            has_overdue=False,
            cycle_failed=True,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE,
            threshold=7,
        )

        result = GamificationEngine._evaluate_streak(
            context,
            target,
            percent_required=1.0,
            only_due_today=False,
            require_no_overdue=True,
        )

        assert result["current_value"] == 0
        assert result["met"] is False


# =============================================================================
# TEST: evaluate_badge (full flow)
# =============================================================================


class TestEvaluateBadge:
    """Tests for full badge evaluation."""

    def test_badge_meets_criteria(self) -> None:
        """Badge criteria met returns criteria_met=True."""
        context = make_context(today_points=100)
        badge = make_badge(threshold=50, badge_type=const.BADGE_TYPE_PERIODIC)

        result = GamificationEngine.evaluate_badge(context, badge)

        assert result["criteria_met"] is True
        assert result["overall_progress"] == 1.0
        assert result["entity_type"] == "badge"

    def test_badge_not_met_below_threshold(self) -> None:
        """Badge not met when below threshold."""
        context = make_context(today_points=25)
        badge = make_badge(threshold=100, badge_type=const.BADGE_TYPE_PERIODIC)

        result = GamificationEngine.evaluate_badge(context, badge)

        assert result["criteria_met"] is False
        assert result["overall_progress"] == 0.25

    def test_badge_with_no_target_returns_not_met(self) -> None:
        """Badge with no target returns criteria_met=False."""
        context = make_context(points_cycle_count=100)
        badge = {
            const.DATA_BADGE_ID: "badge-no-target",
            const.DATA_BADGE_NAME: "No Target Badge",
            const.DATA_BADGE_TARGET: {},  # Empty target
        }

        result = GamificationEngine.evaluate_badge(context, badge)

        assert result["criteria_met"] is False
        assert "No target" in result["reason"]


# =============================================================================
# TEST: evaluate_achievement
# =============================================================================


class TestEvaluateAchievement:
    """Tests for achievement evaluation."""

    def test_chore_total_achievement_met(self) -> None:
        """CHORE_TOTAL achievement criteria met when count reached."""
        context = make_context(approved_all_time=15)
        achievement = make_achievement(
            target_type=const.ACHIEVEMENT_TYPE_TOTAL,
            target_value=10,
        )

        result = GamificationEngine.evaluate_achievement(context, achievement)

        assert result["criteria_met"] is True
        assert result["entity_type"] == "achievement"

    def test_chore_total_achievement_not_met(self) -> None:
        """CHORE_TOTAL achievement not met when below count."""
        context = make_context(approved_all_time=5)
        achievement = make_achievement(
            target_type=const.ACHIEVEMENT_TYPE_TOTAL,
            target_value=10,
        )

        result = GamificationEngine.evaluate_achievement(context, achievement)

        assert result["criteria_met"] is False

    def test_streak_achievement(self) -> None:
        """STREAK achievement uses the freshly tracked streak, not a stored peak.

        The streak comes from ``tracked_current_streak`` (derived fresh from chore
        data each evaluation). A stale persisted high-water-mark must NOT satisfy
        the achievement on its own -- that was the monotonic-streak bug.
        """
        # A fresh tracked streak that meets the threshold -> achievement met.
        context = make_context()
        context["tracked_current_streak"] = 5
        achievement = make_achievement(
            target_type=const.ACHIEVEMENT_TYPE_STREAK,
            target_value=5,
        )

        result = GamificationEngine.evaluate_achievement(context, achievement)

        assert result["criteria_met"] is True

        # A high stored peak with no live tracked streak must NOT satisfy it.
        stale_context = make_context()
        stale_context["tracked_current_streak"] = 0
        stale_context["achievement_progress"] = {
            "achieve-123": {
                stale_context["assignee_id"]: {
                    const.DATA_USER_CURRENT_STREAK: 5,
                }
            }
        }

        stale_result = GamificationEngine.evaluate_achievement(
            stale_context, achievement
        )

        assert stale_result["criteria_met"] is False

    def test_total_achievement_badge_award_count_extension(self) -> None:
        """TOTAL achievement can map to badge award_count source when configured."""
        context = make_context()
        context["badges_earned"] = {
            "badge-hero": {
                const.DATA_USER_BADGES_EARNED_AWARD_COUNT: 3,
            }
        }
        achievement = make_achievement(
            target_type=const.ACHIEVEMENT_TYPE_TOTAL,
            target_value=3,
            source_badge_id="badge-hero",
        )

        result = GamificationEngine.evaluate_achievement(context, achievement)

        assert result["criteria_met"] is True
        criterion = result["criterion_results"][0]
        assert (
            criterion["criterion_type"] == const.CANONICAL_TARGET_TYPE_BADGE_AWARD_COUNT
        )


# =============================================================================
# TEST: evaluate_challenge
# =============================================================================


class TestEvaluateChallenge:
    """Tests for challenge evaluation."""

    def test_challenge_within_date_window_met(self) -> None:
        """Challenge criteria met when within date window and count reached."""
        today = datetime.now(UTC).date().isoformat()
        context = make_context(assignee_id="test-assignee-123", today_iso=today)
        challenge = make_challenge(
            challenge_id="challenge-123",
            target_value=5,
            start_date=today,
            end_date=today,
        )
        # Challenge progress is nested: {challenge_id: {assignee_id: tracking}}
        context["challenge_progress"] = {
            "challenge-123": {
                "test-assignee-123": {const.DATA_CHALLENGE_COUNT: 5},
            },
        }

        result = GamificationEngine.evaluate_challenge(context, challenge)

        assert result["criteria_met"] is True
        assert result["entity_type"] == "challenge"

    def test_challenge_outside_date_window(self) -> None:
        """Challenge not met when outside date window."""
        today = datetime.now(UTC).date().isoformat()
        context = make_context(today_iso=today)
        challenge = make_challenge(
            target_value=5,
            start_date="2020-01-01",
            end_date="2020-01-02",
        )

        result = GamificationEngine.evaluate_challenge(context, challenge)

        # Should not be met (outside window)
        assert result["criteria_met"] is False

    def test_challenge_progress_calculation(self) -> None:
        """Challenge progress calculated correctly."""
        today = datetime.now(UTC).date().isoformat()
        context = make_context(assignee_id="test-assignee-123", today_iso=today)
        challenge = make_challenge(
            challenge_id="challenge-123",
            target_value=10,
            start_date=today,
            end_date=today,
        )
        # Challenge progress is nested: {challenge_id: {assignee_id: tracking}}
        context["challenge_progress"] = {
            "challenge-123": {
                "test-assignee-123": {const.DATA_CHALLENGE_COUNT: 3},
            },
        }

        result = GamificationEngine.evaluate_challenge(context, challenge)

        assert result["criteria_met"] is False
        assert result["overall_progress"] == 0.3

    def test_challenge_below_target(self) -> None:
        """Challenge not met when below target value."""
        today = datetime.now(UTC).date().isoformat()
        context = make_context(assignee_id="test-assignee-123", today_iso=today)
        challenge = make_challenge(
            challenge_id="challenge-123",
            target_value=5,
            start_date=today,
            end_date=today,
        )
        # Challenge progress is nested: {challenge_id: {assignee_id: tracking}}
        context["challenge_progress"] = {
            "challenge-123": {
                "test-assignee-123": {const.DATA_CHALLENGE_COUNT: 2},
            },
        }

        result = GamificationEngine.evaluate_challenge(context, challenge)

        assert result["criteria_met"] is False
        assert result["overall_progress"] == 0.4


# =============================================================================
# TEST: Handler Registry
# =============================================================================


class TestHandlerRegistry:
    """Tests for criterion handler registry."""

    def test_all_target_types_have_handlers(self) -> None:
        """All declared target types have registered handlers."""
        # Ensure handlers are registered
        GamificationEngine._register_handlers()

        expected_types = [
            const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
            const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES,
            const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
            const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
        ]

        for target_type in expected_types:
            assert target_type in GamificationEngine._CRITERION_HANDLERS, (
                f"Missing handler for {target_type}"
            )

    def test_handler_returns_criterion_result(self) -> None:
        """Handler returns properly structured CriterionResult."""
        GamificationEngine._register_handlers()

        context = make_context(points_cycle_count=50)
        badge_data = make_badge(threshold=100, badge_type=const.BADGE_TYPE_PERIODIC)
        target = badge_data[const.DATA_BADGE_TARGET]

        handler = GamificationEngine._CRITERION_HANDLERS.get(
            const.BADGE_TARGET_THRESHOLD_TYPE_POINTS
        )
        assert handler is not None

        result = handler(context, target)

        # Verify CriterionResult structure
        assert "met" in result
        assert "current_value" in result
        assert "threshold" in result
        assert "progress" in result
        assert "criterion_type" in result


# =============================================================================
# TEST: eligible scope for the daily-completion (Days) family
# =============================================================================


class TestDailyCompletionEligibleScope:
    """The Days family scores against the chores actually owed today."""

    def test_percentage_uses_only_owed_chores(self) -> None:
        """A chore that is not owed today cannot make the day unsatisfiable.

        Scoring 3/10 because seven chores were not due made the day impossible;
        the day is judged on the chores that were actually available.
        """
        context = make_context(
            days_cycle_count=0,
            approved_count=3,
            total_count=10,
            due_count=3,
            approved_due_today=3,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=5,
        )

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 1

    def test_partial_completion_of_owed_chores_does_not_advance(self) -> None:
        """Only some of the owed chores done leaves the day unsatisfied."""
        context = make_context(
            days_cycle_count=0,
            approved_count=2,
            total_count=10,
            due_count=3,
            approved_due_today=2,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=5,
        )

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 0

    def test_neutral_day_holds_the_counter(self) -> None:
        """A day with nothing owed neither advances nor empties the counter."""
        context = make_context(
            days_cycle_count=3,
            approved_count=0,
            total_count=4,
            due_count=0,
            approved_due_today=0,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=5,
        )

        result = GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["current_value"] == 3
        assert "nothing owed today" in result["reason"]

    def test_min_count_keeps_the_all_selected_scope(self) -> None:
        """An absolute count must stay satisfiable when fewer chores are owed.

        Decision 10: applying the eligible scope here would make the target
        unreachable whenever fewer chores are due than the required count, so the
        badge could never advance again.
        """
        context = make_context(
            days_cycle_count=0,
            approved_count=5,
            total_count=5,
            due_count=3,
            approved_due_today=3,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES,
            threshold=5,
        )

        result = GamificationEngine._evaluate_daily_completion(
            context, target, count_required=5
        )

        assert result["current_value"] == 1
        assert "5+" in result["reason"]

    def test_min_count_counts_completions_of_not_owed_chores(self) -> None:
        """A non-due chore is extra credit for an absolute count, not an obstacle.

        The deliberate asymmetry with the percentage variants: an unavailable
        chore makes a ratio impossible but can still be counted as extra effort.
        """
        context = make_context(
            days_cycle_count=0,
            approved_count=5,
            total_count=5,
            due_count=2,
            approved_due_today=2,
        )
        target = make_badge_target(
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES,
            threshold=5,
        )

        result = GamificationEngine._evaluate_daily_completion(
            context, target, count_required=5
        )

        assert result["current_value"] == 1
