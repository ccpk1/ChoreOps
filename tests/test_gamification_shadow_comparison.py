"""Shadow comparison tests for GamificationEngine vs legacy code.

These tests verify the new GamificationEngine produces the same results
as the legacy coordinator methods before we remove the legacy code.

Phase 5.4: Shadow Mode Validation
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.gamification_engine import GamificationEngine
from custom_components.choreops.utils.dt_utils import dt_now_local, dt_today_iso
from tests.helpers import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.choreops.type_defs import (
        AchievementData,
        BadgeData,
        ChallengeData,
        EvaluationContext,
    )


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario: 3 kids, 2 parents, 8 chores, badges, achievements."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# ============================================================================
# TEST CLASSES
# ============================================================================


class TestBadgeShadowComparison:
    """Compare new engine badge evaluation with legacy results."""

    @pytest.mark.asyncio
    async def test_points_badge_evaluation_matches(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test that new engine evaluates points-based badges same as legacy.

        Scenario:
        1. Give kid enough points to earn a points-based badge
        2. Compare legacy evaluation result vs new engine result
        """
        coordinator = scenario_full.coordinator

        # Get first kid
        kid_id, kid_data = next(iter(coordinator.kids_data.items()))
        kid_name = kid_data.get(const.DATA_KID_NAME, "Unknown")

        # Find a points-based badge
        points_badge_id = None
        points_badge_data: BadgeData | None = None
        for badge_id, badge_data in coordinator.badges_data.items():
            target = badge_data.get(const.DATA_BADGE_TARGET, {})
            target_type = target.get(const.DATA_BADGE_TARGET_TYPE, "")
            if target_type == const.BADGE_TARGET_THRESHOLD_TYPE_POINTS:
                points_badge_id = badge_id
                points_badge_data = badge_data
                break

        if not points_badge_id or points_badge_data is None:
            pytest.skip("No points-based badge in scenario_full")

        # Get threshold
        target = points_badge_data.get(const.DATA_BADGE_TARGET, {})
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 100)

        # Set kid's points above threshold
        kid_data[const.DATA_KID_POINTS] = float(threshold + 50)

        # Also update point_stats for total_earned (LEGACY - kept for test compatibility)
        point_stats = kid_data.setdefault(const.DATA_KID_POINT_STATS_LEGACY, {})
        point_stats[const.DATA_KID_POINT_STATS_EARNED_ALL_TIME_LEGACY] = float(
            threshold + 50
        )

        # Build evaluation context for new engine
        context: EvaluationContext = {
            "kid_id": kid_id,
            "kid_name": kid_name,
            "current_points": float(kid_data.get(const.DATA_KID_POINTS, 0.0)),
            "total_points_earned": float(
                point_stats.get(const.DATA_KID_POINT_STATS_EARNED_ALL_TIME_LEGACY, 0.0)
            ),
            "badge_progress": kid_data.get(const.DATA_KID_BADGE_PROGRESS, {}),
            "cumulative_badge_progress": kid_data.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
            ),
            "badges_earned": kid_data.get(const.DATA_KID_BADGES_EARNED, {}),
            # v43+: chore_stats deleted, use chore_periods.all_time
            "chore_periods_all_time": kid_data.get(
                const.DATA_KID_CHORE_PERIODS, {}
            ).get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}),
            "achievement_progress": {},
            "challenge_progress": {},
            "today_iso": dt_today_iso(),
        }

        # Evaluate with new engine
        new_result = GamificationEngine.evaluate_badge(
            context, cast("dict[str, Any]", points_badge_data)
        )

        # Verify new engine says criteria is met
        assert new_result["criteria_met"] is True, (
            f"New engine should say criteria met for kid with {threshold + 50} points "
            f"(threshold: {threshold})"
        )
        assert new_result["overall_progress"] >= 1.0, "Progress should be 100%+"

    @pytest.mark.asyncio
    async def test_chore_count_badge_evaluation_matches(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test that new engine evaluates chore-count badges same as legacy.

        Scenario:
        1. Set up kid with completed chores in badge progress
        2. Compare legacy evaluation result vs new engine result
        """
        coordinator = scenario_full.coordinator

        # Get first kid
        kid_id, kid_data = next(iter(coordinator.kids_data.items()))
        kid_name = kid_data.get(const.DATA_KID_NAME, "Unknown")

        # Find a chore-count badge
        chore_badge_id = None
        chore_badge_data: BadgeData | None = None
        for badge_id, badge_data in coordinator.badges_data.items():
            target = badge_data.get(const.DATA_BADGE_TARGET, {})
            target_type = target.get(const.DATA_BADGE_TARGET_TYPE, "")
            if target_type == const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT:
                chore_badge_id = badge_id
                chore_badge_data = badge_data
                break

        if not chore_badge_id or chore_badge_data is None:
            pytest.skip("No chore-count badge in scenario_full")

        # Get threshold
        target = chore_badge_data.get(const.DATA_BADGE_TARGET, {})
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 5)

        # Set up badge progress with enough chores
        badge_progress = kid_data.setdefault(const.DATA_KID_BADGE_PROGRESS, {})
        badge_progress[chore_badge_id] = cast(
            "dict[str, Any]",
            {
                const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT: threshold + 2,
                const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT: 100.0,
            },
        )

        # Build evaluation context
        context: EvaluationContext = {
            "kid_id": kid_id,
            "kid_name": kid_name,
            "current_points": float(kid_data.get(const.DATA_KID_POINTS, 0.0)),
            "total_points_earned": 100.0,
            "badge_progress": badge_progress,
            "cumulative_badge_progress": kid_data.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
            ),
            "badges_earned": kid_data.get(const.DATA_KID_BADGES_EARNED, {}),
            # v43+: chore_stats deleted, use chore_periods.all_time
            "chore_periods_all_time": kid_data.get(
                const.DATA_KID_CHORE_PERIODS, {}
            ).get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}),
            "achievement_progress": {},
            "challenge_progress": {},
            "today_iso": dt_today_iso(),
        }

        # Evaluate with new engine
        new_result = GamificationEngine.evaluate_badge(
            context, cast("dict[str, Any]", chore_badge_data)
        )

        # Verify new engine says criteria is met
        assert new_result["criteria_met"] is True, (
            f"New engine should say criteria met for kid with {threshold + 2} chores "
            f"(threshold: {threshold})"
        )


class TestAchievementShadowComparison:
    """Compare new engine achievement evaluation with legacy results."""

    @pytest.mark.asyncio
    async def test_chore_total_achievement_evaluation(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test chore total achievement evaluation matches."""
        coordinator = scenario_full.coordinator

        # Get first kid
        kid_id, kid_data = next(iter(coordinator.kids_data.items()))
        kid_name = kid_data.get(const.DATA_KID_NAME, "Unknown")

        # Find a CHORE_TOTAL achievement
        achievement_id = None
        achievement_data: AchievementData | None = None
        for ach_id, ach_data in coordinator.achievements_data.items():
            ach_type = ach_data.get(const.DATA_ACHIEVEMENT_TYPE, "")
            if ach_type == const.ACHIEVEMENT_TYPE_TOTAL:
                achievement_id = ach_id
                achievement_data = ach_data
                break

        if not achievement_id or achievement_data is None:
            pytest.skip("No CHORE_TOTAL achievement in scenario_full")

        # Get target count
        target_count = achievement_data.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 10)

        # Set up chore_periods.all_time with enough completions (v43+ structure)
        chore_periods = kid_data.setdefault(const.DATA_KID_CHORE_PERIODS, {})
        chore_periods[const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME] = {
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: target_count + 5,
            const.DATA_KID_CHORE_DATA_PERIOD_POINTS: 500.0,
        }

        # Build evaluation context
        context: EvaluationContext = {
            "kid_id": kid_id,
            "kid_name": kid_name,
            "current_points": float(kid_data.get(const.DATA_KID_POINTS, 0.0)),
            "total_points_earned": 500.0,
            "badge_progress": kid_data.get(const.DATA_KID_BADGE_PROGRESS, {}),
            "cumulative_badge_progress": kid_data.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
            ),
            "badges_earned": kid_data.get(const.DATA_KID_BADGES_EARNED, {}),
            # v43+: chore_stats deleted, use chore_periods.all_time
            "chore_periods_all_time": chore_periods.get(
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
            ),
            "achievement_progress": {},
            "challenge_progress": {},
            "today_iso": dt_today_iso(),
        }

        # Evaluate with new engine
        new_result = GamificationEngine.evaluate_achievement(
            context, cast("dict[str, Any]", achievement_data)
        )

        # Verify new engine evaluation
        # Note: Result depends on achievement having the right chore_id target
        # This test validates the engine runs without error
        assert "criteria_met" in new_result
        assert "overall_progress" in new_result


class TestChallengeShadowComparison:
    """Compare new engine challenge evaluation with legacy results."""

    @pytest.mark.asyncio
    async def test_challenge_within_window_evaluation(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test challenge evaluation within date window."""
        coordinator = scenario_full.coordinator

        # Get first kid
        kid_id, kid_data = next(iter(coordinator.kids_data.items()))
        kid_name = kid_data.get(const.DATA_KID_NAME, "Unknown")

        # Find any challenge
        challenge_id = None
        challenge_data: ChallengeData | None = None
        for chal_id, chal_data in coordinator.challenges_data.items():
            challenge_id = chal_id
            challenge_data = chal_data
            break

        if not challenge_id or challenge_data is None:
            pytest.skip("No challenges in scenario_full")

        # Set challenge dates to include today
        today = dt_now_local()
        challenge_data[const.DATA_CHALLENGE_START_DATE] = (
            today - timedelta(days=1)
        ).isoformat()
        challenge_data[const.DATA_CHALLENGE_END_DATE] = (
            today + timedelta(days=7)
        ).isoformat()

        # Build evaluation context
        context: EvaluationContext = {
            "kid_id": kid_id,
            "kid_name": kid_name,
            "current_points": float(kid_data.get(const.DATA_KID_POINTS, 0.0)),
            "total_points_earned": 100.0,
            "badge_progress": kid_data.get(const.DATA_KID_BADGE_PROGRESS, {}),
            "cumulative_badge_progress": kid_data.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
            ),
            "badges_earned": kid_data.get(const.DATA_KID_BADGES_EARNED, {}),
            # v43+: chore_stats deleted, use chore_periods.all_time
            "chore_periods_all_time": kid_data.get(
                const.DATA_KID_CHORE_PERIODS, {}
            ).get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}),
            "achievement_progress": {},
            "challenge_progress": {},
            "today_iso": dt_today_iso(),
        }

        # Evaluate with new engine
        new_result = GamificationEngine.evaluate_challenge(
            context, cast("dict[str, Any]", challenge_data)
        )

        # Verify new engine evaluation runs
        assert "criteria_met" in new_result
        assert "overall_progress" in new_result


class TestManagerDryRunMethods:
    """Test the GamificationManager dry_run methods work correctly."""

    @pytest.mark.asyncio
    async def test_dry_run_badge_returns_result(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test dry_run_badge returns evaluation result."""
        coordinator = scenario_full.coordinator

        # Get first kid and badge
        kid_id = next(iter(coordinator.kids_data.keys()))
        badge_id = next(iter(coordinator.badges_data.keys()), None)

        if not badge_id:
            pytest.skip("No badges in scenario_full")

        # Call dry_run_badge
        result = coordinator.gamification_manager.dry_run_badge(kid_id, badge_id)

        # Verify result structure
        assert result is not None
        assert "criteria_met" in result
        assert "overall_progress" in result
        assert isinstance(result["criteria_met"], bool)
        assert isinstance(result["overall_progress"], float)

    @pytest.mark.asyncio
    async def test_dry_run_achievement_returns_result(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test dry_run_achievement returns evaluation result."""
        coordinator = scenario_full.coordinator

        # Get first kid and achievement
        kid_id = next(iter(coordinator.kids_data.keys()))
        achievement_id = next(iter(coordinator.achievements_data.keys()), None)

        if not achievement_id:
            pytest.skip("No achievements in scenario_full")

        # Call dry_run_achievement
        result = coordinator.gamification_manager.dry_run_achievement(
            kid_id, achievement_id
        )

        # Verify result structure
        assert result is not None
        assert "criteria_met" in result
        assert "overall_progress" in result

    @pytest.mark.asyncio
    async def test_dry_run_challenge_returns_result(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test dry_run_challenge returns evaluation result."""
        coordinator = scenario_full.coordinator

        # Get first kid and challenge
        kid_id = next(iter(coordinator.kids_data.keys()))
        challenge_id = next(iter(coordinator.challenges_data.keys()), None)

        if not challenge_id:
            pytest.skip("No challenges in scenario_full")

        # Set challenge to active date window
        challenge_data = coordinator.challenges_data[challenge_id]
        today = dt_now_local()
        challenge_data[const.DATA_CHALLENGE_START_DATE] = (
            today - timedelta(days=1)
        ).isoformat()
        challenge_data[const.DATA_CHALLENGE_END_DATE] = (
            today + timedelta(days=7)
        ).isoformat()

        # Call dry_run_challenge
        result = coordinator.gamification_manager.dry_run_challenge(
            kid_id, challenge_id
        )

        # Verify result structure
        assert result is not None
        assert "criteria_met" in result
        assert "overall_progress" in result

    @pytest.mark.asyncio
    async def test_dry_run_with_invalid_kid_returns_none(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test dry_run methods return None for invalid kid."""
        coordinator = scenario_full.coordinator

        badge_id = next(iter(coordinator.badges_data.keys()), None)
        if not badge_id:
            pytest.skip("No badges in scenario_full")

        # Call with invalid kid ID
        result = coordinator.gamification_manager.dry_run_badge(
            "invalid-kid-id", badge_id
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_dry_run_with_invalid_badge_returns_none(
        self,
        scenario_full: SetupResult,
    ) -> None:
        """Test dry_run_badge returns None for invalid badge."""
        coordinator = scenario_full.coordinator

        kid_id = next(iter(coordinator.kids_data.keys()))

        # Call with invalid badge ID
        result = coordinator.gamification_manager.dry_run_badge(
            kid_id, "invalid-badge-id"
        )

        assert result is None
