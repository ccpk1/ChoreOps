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

from custom_components.choreops import const
from custom_components.choreops.engines.gamification_engine import GamificationEngine

if TYPE_CHECKING:
    from custom_components.choreops.type_defs import EvaluationContext

# =============================================================================
# TEST FIXTURES - Minimal context builders
# =============================================================================


def make_context(
    *,
    kid_id: str = "test-kid-123",
    current_points: float = 0.0,
    total_points_earned: float = 0.0,
    points_cycle_count: int = 0,
    chores_cycle_count: int = 0,
    days_cycle_count: int = 0,
    today_points: float = 0.0,
    today_approved: int = 0,
    approved_count: int = 0,
    total_count: int = 0,
    has_overdue: bool = False,
    approved_all_time: int = 0,
    streak_yesterday: bool = False,
    last_update_day: str | None = None,
    today_iso: str | None = None,
    cumulative_baseline: float = 0.0,
    cumulative_cycle_points: float = 0.0,
) -> EvaluationContext:
    """Build a minimal EvaluationContext for testing.

    This creates the context structure that GamificationEngine expects.
    """
    return cast(
        "EvaluationContext",
        {
            "kid_id": kid_id,
            "current_points": current_points,
            "total_points_earned": total_points_earned,
            "current_badge_progress": {
                const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT: points_cycle_count,
                const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT: chores_cycle_count,
                const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT: days_cycle_count,
                const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY: last_update_day,
            },
            "today_stats": {
                "today_points": today_points,
                "today_approved": today_approved,
                "total_earned": total_points_earned,
                "streak_yesterday": streak_yesterday,
            },
            "today_completion": {
                "approved_count": approved_count,
                "total_count": total_count,
                "has_overdue": has_overdue,
            },
            "today_completion_due": {
                "approved_count": approved_count,
                "total_count": total_count,
                "has_overdue": has_overdue,
            },
            # v43+: chore_stats deleted, use chore_periods_all_time
            "chore_periods_all_time": {
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: approved_all_time,
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


# =============================================================================
# TEST: _evaluate_streak
# =============================================================================


class TestEvaluateStreak:
    """Tests for streak criterion evaluation."""

    def test_streak_continues_when_yesterday_had_streak(self) -> None:
        """Streak increments when yesterday had streak and today meets criteria."""
        context = make_context(
            days_cycle_count=5,  # Yesterday's streak
            approved_count=10,
            total_count=10,
            streak_yesterday=True,
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

    def test_streak_starts_fresh_without_yesterday(self) -> None:
        """Streak starts at 1 when no yesterday streak but today meets criteria."""
        context = make_context(
            days_cycle_count=5,
            approved_count=10,
            total_count=10,
            streak_yesterday=False,  # No streak yesterday
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False
        assert result["current_value"] == 1  # Fresh start

    def test_streak_breaks_when_today_fails(self) -> None:
        """Streak resets to 0 when today doesn't meet criteria."""
        context = make_context(
            days_cycle_count=5,
            approved_count=5,
            total_count=10,  # Only 50%
            streak_yesterday=True,
        )
        target = make_badge_target(threshold=7)

        result = GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, only_due_today=False
        )

        assert result["met"] is False
        assert result["current_value"] == 0  # Streak broken

    def test_streak_meets_threshold(self) -> None:
        """Streak meets threshold returns met=True."""
        context = make_context(
            days_cycle_count=6,  # Yesterday's streak
            approved_count=10,
            total_count=10,
            streak_yesterday=True,
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
            streak_yesterday=True,
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
            streak_yesterday=True,
        )
        context["today_completion_due"] = {
            "approved_count": 3,
            "total_count": 3,
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
            streak_yesterday=True,
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
        """STREAK achievement evaluation uses current_streak from tracking."""
        context = make_context()
        # Add achievement progress with streak tracking
        context["achievement_progress"] = {
            "achieve-123": {
                context["kid_id"]: {
                    const.DATA_KID_CURRENT_STREAK: 5,
                }
            }
        }
        achievement = make_achievement(
            target_type=const.ACHIEVEMENT_TYPE_STREAK,
            target_value=5,
        )

        result = GamificationEngine.evaluate_achievement(context, achievement)

        assert result["criteria_met"] is True

    def test_total_achievement_badge_award_count_extension(self) -> None:
        """TOTAL achievement can map to badge award_count source when configured."""
        context = make_context()
        context["badges_earned"] = {
            "badge-hero": {
                const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 3,
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
        context = make_context(kid_id="test-kid-123", today_iso=today)
        challenge = make_challenge(
            challenge_id="challenge-123",
            target_value=5,
            start_date=today,
            end_date=today,
        )
        # Challenge progress is nested: {challenge_id: {kid_id: tracking}}
        context["challenge_progress"] = {
            "challenge-123": {
                "test-kid-123": {const.DATA_CHALLENGE_COUNT: 5},
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
        context = make_context(kid_id="test-kid-123", today_iso=today)
        challenge = make_challenge(
            challenge_id="challenge-123",
            target_value=10,
            start_date=today,
            end_date=today,
        )
        # Challenge progress is nested: {challenge_id: {kid_id: tracking}}
        context["challenge_progress"] = {
            "challenge-123": {
                "test-kid-123": {const.DATA_CHALLENGE_COUNT: 3},
            },
        }

        result = GamificationEngine.evaluate_challenge(context, challenge)

        assert result["criteria_met"] is False
        assert result["overall_progress"] == 0.3

    def test_challenge_below_target(self) -> None:
        """Challenge not met when below target value."""
        today = datetime.now(UTC).date().isoformat()
        context = make_context(kid_id="test-kid-123", today_iso=today)
        challenge = make_challenge(
            challenge_id="challenge-123",
            target_value=5,
            start_date=today,
            end_date=today,
        )
        # Challenge progress is nested: {challenge_id: {kid_id: tracking}}
        context["challenge_progress"] = {
            "challenge-123": {
                "test-kid-123": {const.DATA_CHALLENGE_COUNT: 2},
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
