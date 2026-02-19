"""Gamification Engine - Pure logic for badge, achievement, and challenge evaluation.

This engine provides stateless, pure Python functions for:
- Badge criterion evaluation (points, chore count, daily completion, streaks)
- Achievement progress checking (STREAK, TOTAL, DAILY_MIN types)
- Challenge completion detection (date-windowed goals)
- Acquisition vs retention logic separation

ARCHITECTURE: This is a pure logic engine with NO Home Assistant dependencies.
All functions are static methods that operate on passed-in data.

PURITY REQUIREMENT: This engine receives ALL data via context parameter.
It NEVER imports from helpers or calls external functions.
The GamificationManager is responsible for building context with pre-computed data.

Badge Target Types (17+ variants):
- points, points_chores: Point-based thresholds
- chore_count: Simple chore completion count
- days_*: Daily completion variants (all, 80%, no_overdue, due_only)
- streak_*: Consecutive day variants (all, 80%, no_overdue, due_only)

See docs/ARCHITECTURE.md for the Engine vs Manager distinction.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from .. import const

if TYPE_CHECKING:
    from ..type_defs import (
        CanonicalTargetDefinition,
        CriterionResult,
        EvaluationContext,
        EvaluationResult,
    )


# =============================================================================
# INTERNAL DATE HELPERS (avoid circular import with helpers)
# =============================================================================


def _today_iso() -> str:
    """Return today's date as ISO string (YYYY-MM-DD) in UTC."""
    return datetime.now(UTC).date().isoformat()


# =============================================================================
# TYPE ALIASES
# =============================================================================

# Handler function signature: (context, target_data) -> CriterionResult
CriterionHandler = Callable[["EvaluationContext", dict[str, Any]], "CriterionResult"]


# =============================================================================
# GAMIFICATION ENGINE
# =============================================================================


class GamificationEngine:
    """Pure logic engine for gamification evaluation.

    All methods are static - no instance state. This enables easy unit testing
    without any Home Assistant mocking.

    PURITY CONTRACT:
    - All data comes via `context` parameter
    - No external imports from helpers (circular import risk)
    - No side effects, no database access, no state mutation
    - Context is built by Manager with pre-computed values

    Context Requirements:
    - today_stats: Pre-computed daily stats (points, chores, streaks)
    - assignee_info: Full assignee data (for badge_progress lookups)
    - all_chores: Chore definitions (for due date checking)
    - today_iso: Current date as ISO string

    Evaluation Flow:
        1. Context is prepared by Manager with all needed assignee/chore data
        2. Engine evaluates criteria using pure functions
        3. Engine returns results (criteria_met, progress, reasons)
        4. Manager handles side effects (awarding, notifications, storage)

    Badge Evaluation Modes:
        CUMULATIVE BADGES (never lost, only demoted):
        - evaluate_badge(): First-time award based on total lifetime points
        - check_cumulative_maintenance(): ACTIVE vs DEMOTED based on cycle points

        PERIODIC BADGES (never lost, re-awarded when criteria met again):
        - evaluate_badge(): First-time award based on current period stats
        - Re-awards use same evaluate_badge() logic (criteria unchanged)
    """

    # =========================================================================
    # CRITERION HANDLER REGISTRY
    # =========================================================================

    # Maps badge target_type to handler function
    # Handlers are registered as static methods below
    _CRITERION_HANDLERS: dict[str, CriterionHandler] = {}
    _PERIODIC_TARGET_METADATA: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_periodic_target_metadata(
        cls,
        target_type: str,
    ) -> dict[str, Any] | None:
        """Return canonical periodic target metadata for a raw target type."""
        cls._register_handlers()
        return cls._PERIODIC_TARGET_METADATA.get(target_type)

    @classmethod
    def _register_handlers(cls) -> None:
        """Register all criterion handlers.

        Called once at module load to populate _CRITERION_HANDLERS.
        Uses a registry pattern for clean separation and easy extension.
        """
        if cls._CRITERION_HANDLERS:
            return  # Already registered

        target_specs: list[tuple[str, CriterionHandler, dict[str, Any]]] = [
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                cls._evaluate_points,
                {
                    "canonical_type": "points",
                    "persist_bucket": "points_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES,
                cls._evaluate_points_from_chores,
                {
                    "canonical_type": "points_chores",
                    "persist_bucket": "points_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
                cls._evaluate_chore_count,
                {
                    "canonical_type": "chore_count",
                    "persist_bucket": "chores_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
                cls._evaluate_daily_completion_all,
                {
                    "canonical_type": "daily_completion",
                    "percent_required": 1.0,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES,
                cls._evaluate_daily_completion_80pct,
                {
                    "canonical_type": "daily_completion",
                    "percent_required": 0.8,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES_NO_OVERDUE,
                cls._evaluate_daily_completion_no_overdue,
                {
                    "canonical_type": "daily_completion_no_overdue",
                    "percent_required": 1.0,
                    "require_no_overdue": True,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES,
                cls._evaluate_daily_due_all,
                {
                    "canonical_type": "daily_completion_due",
                    "percent_required": 1.0,
                    "use_due_only_scope": True,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_DUE_CHORES,
                cls._evaluate_daily_due_80pct,
                {
                    "canonical_type": "daily_completion_due",
                    "percent_required": 0.8,
                    "use_due_only_scope": True,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES_NO_OVERDUE,
                cls._evaluate_daily_due_no_overdue,
                {
                    "canonical_type": "daily_completion_due_no_overdue",
                    "percent_required": 1.0,
                    "use_due_only_scope": True,
                    "require_no_overdue": True,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES,
                cls._evaluate_daily_min_3,
                {
                    "canonical_type": "daily_minimum",
                    "min_count_required": 3,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES,
                cls._evaluate_daily_min_5,
                {
                    "canonical_type": "daily_minimum",
                    "min_count_required": 5,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_7_CHORES,
                cls._evaluate_daily_min_7,
                {
                    "canonical_type": "daily_minimum",
                    "min_count_required": 7,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
                cls._evaluate_streak_all,
                {
                    "canonical_type": "completion_streak",
                    "percent_required": 1.0,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_CHORES,
                cls._evaluate_streak_80pct,
                {
                    "canonical_type": "completion_streak",
                    "percent_required": 0.8,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE,
                cls._evaluate_streak_no_overdue,
                {
                    "canonical_type": "completion_streak_no_overdue",
                    "percent_required": 1.0,
                    "require_no_overdue": True,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES,
                cls._evaluate_streak_due_80pct,
                {
                    "canonical_type": "completion_streak_due",
                    "percent_required": 0.8,
                    "use_due_only_scope": True,
                    "persist_bucket": "days_cycle",
                },
            ),
            (
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_DUE_CHORES_NO_OVERDUE,
                cls._evaluate_streak_due_no_overdue,
                {
                    "canonical_type": "completion_streak_due_no_overdue",
                    "percent_required": 1.0,
                    "use_due_only_scope": True,
                    "require_no_overdue": True,
                    "persist_bucket": "days_cycle",
                },
            ),
        ]

        cls._CRITERION_HANDLERS = {
            target_type: handler for target_type, handler, _meta in target_specs
        }
        cls._PERIODIC_TARGET_METADATA = {
            target_type: dict(meta) for target_type, _handler, meta in target_specs
        }

    # =========================================================================
    # MAIN EVALUATION METHODS
    # =========================================================================

    @classmethod
    def evaluate_badge(
        cls,
        context: EvaluationContext,
        badge_data: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate if assignee meets badge criteria.

        Pure function - no side effects, no database access.

        Args:
            context: EvaluationContext with assignee data, chore data, timestamps
            badge_data: Badge definition from storage

        Returns:
            EvaluationResult with criteria_met, overall_progress, criterion_results
        """
        cls._register_handlers()

        badge_id = badge_data.get(const.DATA_BADGE_ID, "unknown")
        badge_name = badge_data.get(const.DATA_BADGE_NAME, "Unknown Badge")

        # Get target from badge (single target dict, not list)
        target = badge_data.get(const.DATA_BADGE_TARGET, {})
        if not target:
            return cls._make_result(
                entity_id=badge_id,
                entity_name=badge_name,
                entity_type="badge",
                criteria_met=False,
                overall_progress=0.0,
                criterion_results=[],
                reason="No target defined for badge",
            )

        # Wrap single target in list for consistent processing
        targets = [target]

        # Evaluate each target
        criterion_results: list[CriterionResult] = []
        all_met = True
        total_progress = 0.0

        for target in targets:
            target_type = target.get(const.DATA_BADGE_TARGET_TYPE)

            # Route cumulative badges with all-time points target to specialized handler
            badge_type = badge_data.get(const.DATA_BADGE_TYPE)
            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                result = cls._evaluate_cumulative_points(context, target)
                criterion_results.append(result)
                if not result["met"]:
                    all_met = False
                total_progress += result["progress"]
                continue

            handler = cls._CRITERION_HANDLERS.get(target_type)

            if handler is None:
                # Unknown target type - log and skip
                const.LOGGER.warning(
                    "Unknown badge target type: %s for badge %s",
                    target_type,
                    badge_id,
                )
                criterion_results.append(
                    cls._make_criterion_result(
                        criterion_type=target_type or "unknown",
                        met=False,
                        progress=0.0,
                        threshold=0,
                        current_value=0,
                        reason=f"Unknown target type: {target_type}",
                    )
                )
                all_met = False
                continue

            # Call handler
            result = handler(context, target)
            criterion_results.append(result)

            if not result["met"]:
                all_met = False

            total_progress += result["progress"]

        # Calculate average progress
        avg_progress = total_progress / len(targets) if targets else 0.0

        return cls._make_result(
            entity_id=badge_id,
            entity_name=badge_name,
            entity_type="badge",
            criteria_met=all_met,
            overall_progress=avg_progress,
            criterion_results=criterion_results,
        )

    @classmethod
    def evaluate_achievement(
        cls,
        context: EvaluationContext,
        achievement_data: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate if assignee has completed an achievement.

        Achievement types:
        - STREAK: Consecutive days of specific action
        - TOTAL: Cumulative count (chores, points, rewards)
        - DAILY_MIN: Minimum daily activity

        Args:
            context: EvaluationContext with assignee data
            achievement_data: Achievement definition

        Returns:
            EvaluationResult with completion status
        """
        achievement_id = achievement_data.get(const.DATA_ACHIEVEMENT_ID, "unknown")
        achievement_name = achievement_data.get(
            const.DATA_ACHIEVEMENT_NAME, "Unknown Achievement"
        )
        achievement_type = str(achievement_data.get(const.DATA_ACHIEVEMENT_TYPE, ""))
        threshold = float(
            achievement_data.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 0.0)
        )

        # Get assignee achievement tracking data from context
        # This is per-assignee progress keyed by assignee_id within achievement_progress
        assignee_id: str = context.get("assignee_id") or ""
        achievement_progress: dict[str, Any] = context.get("achievement_progress") or {}
        tracking_raw = achievement_progress.get(achievement_id, {})
        if isinstance(tracking_raw, dict) and assignee_id in tracking_raw:
            nested_tracking = tracking_raw.get(assignee_id)
            if isinstance(nested_tracking, dict):
                tracking = nested_tracking
            else:
                tracking = {}
        elif isinstance(tracking_raw, dict):
            tracking = tracking_raw
        else:
            tracking = {}

        source_badge_id = str(
            achievement_data.get(const.DATA_ACHIEVEMENT_SOURCE_BADGE_ID, "")
        )

        canonical_type = const.ACHIEVEMENT_TO_CANONICAL_TARGET_MAP.get(
            achievement_type,
            "unknown_target",
        )
        if (
            achievement_type == const.ACHIEVEMENT_TYPE_TOTAL
            and source_badge_id
            and source_badge_id in (context.get("badges_earned") or {})
        ):
            canonical_type = const.CANONICAL_TARGET_TYPE_BADGE_AWARD_COUNT

        runtime_context = cast("EvaluationContext", dict(context))
        runtime_context["current_achievement_progress"] = cast("Any", tracking)

        canonical_target: CanonicalTargetDefinition = {
            "target_type": cast("Any", canonical_type),
            "threshold_value": threshold,
            "source_entity_type": "achievement",
            "source_item_id": achievement_id,
            "source_raw_type": achievement_type,
            "baseline_value": float(tracking.get(const.DATA_ACHIEVEMENT_BASELINE, 0)),
        }
        if source_badge_id:
            canonical_target["source_badge_id"] = source_badge_id

        return cls.evaluate_canonical_target(
            runtime_context,
            entity_id=achievement_id,
            entity_name=achievement_name,
            entity_type="achievement",
            canonical_target=canonical_target,
        )

    @classmethod
    def evaluate_challenge(
        cls,
        context: EvaluationContext,
        challenge_data: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate if assignee has completed a challenge.

        Challenges are time-bound goals with start/end dates.

        Challenge types:
        - TOTAL_WITHIN_WINDOW: Cumulative count within date range
        - DAILY_MIN: Minimum daily activity within date range

        Args:
            context: EvaluationContext with assignee data
            challenge_data: Challenge definition

        Returns:
            EvaluationResult with completion status
        """
        challenge_id = challenge_data.get(const.DATA_CHALLENGE_ID, "unknown")
        challenge_name = challenge_data.get(
            const.DATA_CHALLENGE_NAME, "Unknown Challenge"
        )
        challenge_type = str(challenge_data.get(const.DATA_CHALLENGE_TYPE, ""))
        threshold = float(challenge_data.get(const.DATA_CHALLENGE_TARGET_VALUE, 0.0))

        # Check date window
        start_date = challenge_data.get(const.DATA_CHALLENGE_START_DATE)
        end_date = challenge_data.get(const.DATA_CHALLENGE_END_DATE)
        today_iso = context.get("today_iso") or _today_iso()

        # Check if challenge is active
        if start_date and today_iso < start_date[:10]:
            return cls._make_result(
                entity_id=challenge_id,
                entity_name=challenge_name,
                entity_type="challenge",
                criteria_met=False,
                overall_progress=0.0,
                criterion_results=[],
                reason="Challenge has not started yet",
            )

        if end_date and today_iso > end_date[:10]:
            return cls._make_result(
                entity_id=challenge_id,
                entity_name=challenge_name,
                entity_type="challenge",
                criteria_met=False,
                overall_progress=0.0,
                criterion_results=[],
                reason="Challenge has ended",
            )

        # Get assignee challenge tracking data from context
        # challenge_progress in context contains per-challenge, per-assignee progress
        assignee_id: str = context.get("assignee_id") or ""
        challenge_progress: dict[str, Any] = context.get("challenge_progress") or {}
        tracking_raw = challenge_progress.get(challenge_id, {})
        if isinstance(tracking_raw, dict) and assignee_id in tracking_raw:
            nested_tracking = tracking_raw.get(assignee_id)
            if isinstance(nested_tracking, dict):
                tracking = nested_tracking
            else:
                tracking = {}
        elif isinstance(tracking_raw, dict):
            tracking = tracking_raw
        else:
            tracking = {}

        canonical_type = const.CHALLENGE_TO_CANONICAL_TARGET_MAP.get(
            challenge_type,
            "unknown_target",
        )

        runtime_context = cast("EvaluationContext", dict(context))
        runtime_context["current_challenge_progress"] = cast("Any", tracking)

        canonical_target: CanonicalTargetDefinition = {
            "target_type": cast("Any", canonical_type),
            "threshold_value": threshold,
            "source_entity_type": "challenge",
            "source_item_id": challenge_id,
            "source_raw_type": challenge_type,
        }

        return cls.evaluate_canonical_target(
            runtime_context,
            entity_id=challenge_id,
            entity_name=challenge_name,
            entity_type="challenge",
            canonical_target=canonical_target,
        )

    @classmethod
    def evaluate_canonical_target(
        cls,
        context: EvaluationContext,
        *,
        entity_id: str,
        entity_name: str,
        entity_type: str,
        canonical_target: CanonicalTargetDefinition,
    ) -> EvaluationResult:
        """Evaluate a canonical target definition for any gamification source."""
        criterion_result = cls._evaluate_canonical_target_criterion(
            context,
            canonical_target,
        )

        return cls._make_result(
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            criteria_met=criterion_result["met"],
            overall_progress=criterion_result["progress"],
            criterion_results=[criterion_result],
            reason=criterion_result["reason"],
        )

    @staticmethod
    def _evaluate_canonical_target_criterion(
        context: EvaluationContext,
        canonical_target: CanonicalTargetDefinition,
    ) -> CriterionResult:
        """Evaluate one canonical target and return normalized criterion result."""
        target_type = str(canonical_target.get("target_type", "unknown_target"))
        threshold = float(canonical_target.get("threshold_value", 0.0))

        current_value = 0.0
        reason = ""

        if target_type == const.CANONICAL_TARGET_TYPE_DAILY_MINIMUM:
            today_stats = context.get("today_stats") or {}
            current_value = float(today_stats.get("today_approved", 0))
            reason = f"Today: {current_value}/{threshold}"

        elif target_type == const.CANONICAL_TARGET_TYPE_COMPLETION_STREAK:
            achievement_progress = context.get("current_achievement_progress") or {}
            current_value = float(
                cast("dict[str, Any]", achievement_progress).get(
                    const.DATA_USER_CURRENT_STREAK,
                    0,
                )
            )
            reason = f"Streak: {current_value}/{threshold}"

        elif target_type == const.CANONICAL_TARGET_TYPE_TOTAL_WITH_BASELINE:
            chore_periods_all_time = context.get("chore_periods_all_time") or {}
            baseline = float(canonical_target.get("baseline_value", 0.0))
            total_approved = float(
                chore_periods_all_time.get(
                    const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                )
            )
            current_value = max(total_approved - baseline, 0.0)
            reason = f"Total: {current_value}/{threshold}"

        elif target_type == const.CANONICAL_TARGET_TYPE_TOTAL_WITHIN_WINDOW:
            challenge_progress = context.get("current_challenge_progress") or {}
            current_value = float(
                cast("dict[str, Any]", challenge_progress).get(
                    const.DATA_CHALLENGE_COUNT,
                    0,
                )
            )
            reason = f"Total: {current_value}/{threshold}"

        elif target_type == const.CANONICAL_TARGET_TYPE_BADGE_AWARD_COUNT:
            badges_earned = context.get("badges_earned") or {}
            source_badge_id = str(canonical_target.get("source_badge_id", ""))
            badge_entry = badges_earned.get(source_badge_id, {})
            current_value = float(
                cast("dict[str, Any]", badge_entry).get(
                    const.DATA_USER_BADGES_EARNED_AWARD_COUNT,
                    0,
                )
            )
            reason = f"Badge awards: {current_value}/{threshold}"

        else:
            reason = f"Unknown canonical target type: {target_type}"

        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold if threshold > 0 else False

        return GamificationEngine._make_criterion_result(
            criterion_type=target_type,
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=reason,
        )

    # =========================================================================
    # POINTS-BASED HANDLERS
    # =========================================================================

    @staticmethod
    def _evaluate_points(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Evaluate points-based criterion for PERIODIC badges.

        Uses per-badge cycle count (resets on badge cycle) plus today's points.
        NOT for cumulative badges - see _evaluate_cumulative_points instead.

        Args:
            context: EvaluationContext with point tracking data
            target: Badge target with threshold_value

        Returns:
            CriterionResult with met status and progress
        """
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)

        # Use per-badge cycle count
        badge_progress = context.get("current_badge_progress") or {}
        cycle_count = badge_progress.get(
            const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0
        )

        # Get today's point progress from pre-computed stats in context
        today_stats = context.get("today_stats") or {}
        today_points = today_stats.get("today_points", 0)

        # Total is cycle_count (previously accumulated) + today's points
        current_value = cycle_count + today_points

        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold

        return GamificationEngine._make_criterion_result(
            criterion_type=const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=f"Points: {current_value}/{threshold}",
        )

    @staticmethod
    def _evaluate_cumulative_points(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Evaluate points-based criterion for CUMULATIVE badges.

        Uses all-time total points earned (never resets).
        This is for badge tier progression based on lifetime achievement.

        Args:
            context: EvaluationContext with total_points_earned
            target: Badge target with threshold_value

        Returns:
            CriterionResult with met status and progress
        """
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)

        # Use all-time total points for cumulative badge tier determination
        current_value = context.get("total_points_earned", 0.0)

        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold

        return GamificationEngine._make_criterion_result(
            criterion_type="cumulative_points",
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=f"Cumulative points: {current_value}/{threshold}",
        )

    @staticmethod
    def _evaluate_points_from_chores(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Evaluate points-from-chores badge criterion (PERIODIC BADGES ONLY).

        Checks if assignee has earned enough points specifically from chores
        (excludes bonuses, penalties, manual adjustments, etc.).

        Args:
            context: EvaluationContext with point tracking data
            target: Badge target with threshold_value

        Returns:
            CriterionResult with met status and progress
        """
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)

        # PERIODIC BADGES ONLY: Use per-badge cycle count
        badge_progress = context.get("current_badge_progress") or {}
        cycle_count = badge_progress.get(
            const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0
        )

        # Get chore-specific points from pre-computed stats
        today_stats = context.get("today_stats") or {}
        total_earned = today_stats.get("total_earned", 0)

        # For chore-specific points, calculate delta from cycle_count
        today_chore_points = (
            total_earned - cycle_count if total_earned > cycle_count else 0
        )
        current_value = cycle_count + today_chore_points

        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold

        return GamificationEngine._make_criterion_result(
            criterion_type=const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES,
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=f"Chore points: {current_value}/{threshold}",
        )

    # =========================================================================
    # CHORE COUNT HANDLER
    # =========================================================================

    @staticmethod
    def _evaluate_chore_count(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Evaluate chore count badge criterion.

        Checks if assignee has completed enough total chores.

        Args:
            context: EvaluationContext with current_badge_progress
            target: Badge target with threshold_value

        Returns:
            CriterionResult with met status and progress
        """
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)

        # Get cycle count from badge progress
        badge_progress = context.get("current_badge_progress") or {}
        cycle_count = badge_progress.get(
            const.DATA_USER_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0
        )

        # Get today's chore completion count from pre-computed stats
        today_stats = context.get("today_stats") or {}
        today_approved = today_stats.get("today_approved", 0)

        current_value = cycle_count + today_approved
        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold

        return GamificationEngine._make_criterion_result(
            criterion_type=const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=f"Chores: {current_value}/{threshold}",
        )

    # =========================================================================
    # DAILY COMPLETION HANDLERS
    # =========================================================================

    @staticmethod
    def _evaluate_daily_completion(
        context: EvaluationContext,
        target: dict[str, Any],
        *,
        percent_required: float = 1.0,
        only_due_today: bool = False,
        require_no_overdue: bool = False,
        count_required: int | None = None,
    ) -> CriterionResult:
        """Core daily completion evaluation logic.

        Parameterized handler for all daily completion variants.

        Context Requirements:
        - today_completion: Pre-computed completion stats with keys:
            - approved_count: Number of approved chores
            - total_count: Total tracked chores
            - has_overdue: Whether any overdue chores exist

        Args:
            context: EvaluationContext with current_badge_progress, today_completion
            target: Badge target with threshold_value (days needed)
            percent_required: Minimum completion percentage (0.0-1.0)
            only_due_today: Only count chores due today (affects context prep)
            require_no_overdue: Fail if any overdue chores exist
            count_required: Minimum chore count (overrides percent_required)

        Returns:
            CriterionResult with met status and progress
        """
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)

        daily_status = GamificationEngine._resolve_daily_status(
            context,
            only_due_today=only_due_today,
        )
        cycle_count = int(daily_status.get("cycle_count", 0))
        approved_count = int(daily_status.get("approved_count", 0))
        total_count = int(daily_status.get("total_count", 0))
        has_overdue = bool(daily_status.get("has_overdue", False))
        already_counted_today = bool(daily_status.get("already_counted_today", False))

        # Determine if today meets criteria
        today_met = False
        if total_count > 0:
            if count_required is not None:
                today_met = approved_count >= count_required
            else:
                percent_complete = approved_count / total_count
                today_met = percent_complete >= percent_required

            # Check overdue constraint
            if today_met and require_no_overdue and has_overdue:
                today_met = False

        # If today meets criteria, increment cycle (conceptually)
        # Actual cycle update happens in Manager
        if today_met:
            current_value = cycle_count if already_counted_today else cycle_count + 1
        else:
            current_value = cycle_count

        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold

        # Build descriptive reason
        pct_str = (
            f"{int(percent_required * 100)}%"
            if count_required is None
            else f"{count_required}+"
        )
        due_str = " (due)" if only_due_today else ""
        overdue_str = ", no overdue" if require_no_overdue else ""
        reason_detail = (
            f"{current_value}/{threshold} (today: {approved_count}/{total_count})"
        )

        return GamificationEngine._make_criterion_result(
            criterion_type=target.get(const.DATA_BADGE_TARGET_TYPE, "daily"),
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=f"Days {pct_str}{due_str}{overdue_str}: {reason_detail}",
        )

    # Daily completion variant handlers (parameterized wrappers)

    @staticmethod
    def _evaluate_daily_completion_all(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% of tracked chores completed each day."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0
        )

    @staticmethod
    def _evaluate_daily_completion_80pct(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """80% of tracked chores completed each day."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=0.8
        )

    @staticmethod
    def _evaluate_daily_completion_no_overdue(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% completion with no overdue chores."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, require_no_overdue=True
        )

    @staticmethod
    def _evaluate_daily_due_all(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% of chores DUE TODAY completed."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=1.0, only_due_today=True
        )

    @staticmethod
    def _evaluate_daily_due_80pct(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """80% of chores DUE TODAY completed."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, percent_required=0.8, only_due_today=True
        )

    @staticmethod
    def _evaluate_daily_due_no_overdue(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% of chores DUE TODAY completed with no overdue."""
        return GamificationEngine._evaluate_daily_completion(
            context,
            target,
            percent_required=1.0,
            only_due_today=True,
            require_no_overdue=True,
        )

    @staticmethod
    def _evaluate_daily_min_3(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Minimum 3 chores completed each day."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, count_required=3
        )

    @staticmethod
    def _evaluate_daily_min_5(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Minimum 5 chores completed each day."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, count_required=5
        )

    @staticmethod
    def _evaluate_daily_min_7(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """Minimum 7 chores completed each day."""
        return GamificationEngine._evaluate_daily_completion(
            context, target, count_required=7
        )

    # =========================================================================
    # STREAK HANDLERS
    # =========================================================================

    @staticmethod
    def _evaluate_streak(
        context: EvaluationContext,
        target: dict[str, Any],
        *,
        percent_required: float = 1.0,
        only_due_today: bool = False,
        require_no_overdue: bool = False,
    ) -> CriterionResult:
        """Core streak evaluation logic.

        Streaks require CONSECUTIVE days meeting criteria.
        Missing a day resets progress to 0.

        Context Requirements:
        - today_stats.streak_yesterday: Whether yesterday maintained streak
        - today_completion: Pre-computed completion stats
        - current_badge_progress.days_cycle_count: Current streak count

        Args:
            context: EvaluationContext with streak and completion stats
            target: Badge target with threshold_value (consecutive days needed)
            percent_required: Minimum completion percentage (0.0-1.0)
            only_due_today: Only count chores due today
            require_no_overdue: Fail if any overdue chores exist

        Returns:
            CriterionResult with met status and progress
        """
        threshold = target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)

        daily_status = GamificationEngine._resolve_daily_status(
            context,
            only_due_today=only_due_today,
        )
        cycle_count = int(daily_status.get("cycle_count", 0))
        approved_count = int(daily_status.get("approved_count", 0))
        total_count = int(daily_status.get("total_count", 0))
        has_overdue = bool(daily_status.get("has_overdue", False))
        streak_yesterday = bool(daily_status.get("streak_yesterday", False))
        already_counted_today = bool(daily_status.get("already_counted_today", False))

        # Determine if today meets criteria
        today_met = False
        if total_count > 0:
            percent_complete = approved_count / total_count
            today_met = percent_complete >= percent_required

            # Check overdue constraint
            if today_met and require_no_overdue and has_overdue:
                today_met = False

        # Streak logic:
        # - If yesterday had streak AND today meets criteria: continue streak
        # - If today meets criteria but no yesterday streak: start new streak (1)
        # - If today doesn't meet criteria: streak breaks (0)
        if today_met:
            if already_counted_today:
                current_value = cycle_count
            elif streak_yesterday:
                current_value = cycle_count + 1
            else:
                # Starting fresh streak today
                current_value = 1
        else:
            # Streak broken
            current_value = 0

        progress = min(1.0, current_value / threshold) if threshold > 0 else 0.0
        criteria_met = current_value >= threshold

        pct_str = f"{int(percent_required * 100)}%"
        due_str = " (due)" if only_due_today else ""
        overdue_str = ", no overdue" if require_no_overdue else ""
        reason = (
            f"Streak {pct_str}{due_str}{overdue_str}: "
            f"{current_value}/{threshold} consecutive days"
        )

        return GamificationEngine._make_criterion_result(
            criterion_type=target.get(const.DATA_BADGE_TARGET_TYPE, "streak"),
            met=criteria_met,
            progress=progress,
            threshold=threshold,
            current_value=current_value,
            reason=reason,
        )

    # Streak variant handlers (parameterized wrappers)

    @staticmethod
    def _evaluate_streak_all(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% of tracked chores for consecutive days."""
        return GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0
        )

    @staticmethod
    def _evaluate_streak_80pct(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """80% of tracked chores for consecutive days."""
        return GamificationEngine._evaluate_streak(
            context, target, percent_required=0.8
        )

    @staticmethod
    def _evaluate_streak_no_overdue(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% completion with no overdue for consecutive days."""
        return GamificationEngine._evaluate_streak(
            context, target, percent_required=1.0, require_no_overdue=True
        )

    @staticmethod
    def _evaluate_streak_due_80pct(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """80% of chores DUE TODAY for consecutive days."""
        return GamificationEngine._evaluate_streak(
            context, target, percent_required=0.8, only_due_today=True
        )

    @staticmethod
    def _evaluate_streak_due_no_overdue(
        context: EvaluationContext,
        target: dict[str, Any],
    ) -> CriterionResult:
        """100% of chores DUE TODAY with no overdue for consecutive days."""
        return GamificationEngine._evaluate_streak(
            context,
            target,
            percent_required=1.0,
            only_due_today=True,
            require_no_overdue=True,
        )

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    @staticmethod
    def _make_result(
        entity_id: str,
        entity_name: str,
        entity_type: str,
        criteria_met: bool,
        overall_progress: float,
        criterion_results: list[CriterionResult],
        reason: str = "",
    ) -> EvaluationResult:
        """Create a standardized EvaluationResult.

        Args:
            entity_id: Badge/achievement/challenge ID
            entity_name: Display name
            entity_type: "badge", "achievement", or "challenge"
            criteria_met: Whether all criteria are satisfied
            overall_progress: Average progress across all criteria (0.0-1.0)
            criterion_results: List of individual criterion results
            reason: Optional explanation (used for edge cases)

        Returns:
            EvaluationResult TypedDict
        """
        return {
            "entity_id": entity_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "criteria_met": criteria_met,
            "overall_progress": overall_progress,
            "criterion_results": criterion_results,
            "reason": reason,
            "evaluated_at": _today_iso(),
        }

    @staticmethod
    def _resolve_daily_status(
        context: EvaluationContext,
        *,
        only_due_today: bool,
    ) -> dict[str, Any]:
        """Resolve normalized daily state for day-count and streak evaluators."""
        badge_progress: Any = context.get("current_badge_progress") or {}
        cycle_count = int(
            badge_progress.get(const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0)
        )
        last_update_day = str(
            badge_progress.get(const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY, "")
        )
        today_iso = str(context.get("today_iso") or _today_iso())
        already_counted_today = last_update_day == today_iso

        completion_key = (
            "today_completion_due" if only_due_today else "today_completion"
        )
        today_completion: Any = context.get(completion_key) or {}
        approved_count = int(today_completion.get("approved_count", 0))
        total_count = int(today_completion.get("total_count", 0))
        has_overdue = bool(today_completion.get("has_overdue", False))

        today_stats: Any = context.get("today_stats") or {}
        streak_yesterday = bool(today_stats.get("streak_yesterday", False))

        return {
            "cycle_count": cycle_count,
            "last_update_day": last_update_day,
            "today_iso": today_iso,
            "already_counted_today": already_counted_today,
            "approved_count": approved_count,
            "total_count": total_count,
            "has_overdue": has_overdue,
            "streak_yesterday": streak_yesterday,
        }

    @staticmethod
    def _make_criterion_result(
        criterion_type: str,
        met: bool,
        progress: float,
        threshold: float,
        current_value: float,
        reason: str = "",
    ) -> CriterionResult:
        """Create a standardized CriterionResult.

        Args:
            criterion_type: Type of criterion (e.g., "points", "streak_all_chores")
            met: Whether this criterion is satisfied
            progress: Progress toward threshold (0.0-1.0)
            threshold: Target value to reach
            current_value: Current achieved value
            reason: Human-readable explanation

        Returns:
            CriterionResult TypedDict
        """
        return {
            "criterion_type": criterion_type,
            "met": met,
            "progress": progress,
            "threshold": threshold,
            "current_value": current_value,
            "reason": reason,
        }

    @staticmethod
    def _get_achievement_total(
        context: EvaluationContext,
        achievement_data: dict[str, Any],
    ) -> int:
        """Get total count for achievement progress.

        Reads from chore_periods_all_time in context based on achievement type.

        Args:
            context: EvaluationContext with chore_periods_all_time
            achievement_data: Achievement definition with type

        Returns:
            Current total count
        """
        # v43+: chore_stats deleted, use chore_periods_all_time bucket
        chore_periods_all_time = context.get("chore_periods_all_time") or {}
        achievement_type = achievement_data.get(const.DATA_ACHIEVEMENT_TYPE)

        # For total chore achievements, use approved from chore_periods.all_time
        if achievement_type == const.ACHIEVEMENT_TYPE_TOTAL:
            return chore_periods_all_time.get(
                const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
            )

        # For point achievements, use total_points_earned from context
        # (the context is built with this from point_stats)
        return int(context.get("total_points_earned", 0))

    @staticmethod
    def _get_challenge_total(
        context: EvaluationContext,
        challenge_data: dict[str, Any],
    ) -> int:
        """Get total count for challenge progress.

        Similar to achievement total but may have different sources.

        Args:
            context: EvaluationContext with chore_periods_all_time
            challenge_data: Challenge definition with target_type

        Returns:
            Current total count
        """
        # Reuse achievement logic for now
        return GamificationEngine._get_achievement_total(context, challenge_data)
