"""Gamification Manager - Debounced badge/achievement/challenge evaluation.

This manager handles gamification evaluation with debouncing:
- Pending tracking: Which kids need re-evaluation (persisted to storage)
- Debounced evaluation: Batch evaluations to avoid redundant processing
- Event listening: Responds to points_changed, chore_approved, etc.
- Result application: Awards/revokes badges, achievements, challenges

ARCHITECTURE (v0.5.0+):
- GamificationManager = "The Judge" (STATEFUL orchestration)
- GamificationEngine = Pure evaluation logic (STATELESS)
- Coordinator provides context data and receives result notifications

RELIABILITY (Phase 7.4):
- Pending evaluations are persisted to storage meta
- On restart, pending evaluations are recovered and processed
- Kid deletion removes kid from pending queue
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError

from .. import const, data_builders as db
from ..engines.gamification_engine import GamificationEngine
from ..helpers import entity_helpers as eh
from ..helpers.entity_helpers import get_item_id_by_name, remove_entities_by_item_id
from ..utils.dt_utils import dt_add_interval, dt_next_schedule, dt_now_iso, dt_today_iso
from .base_manager import BaseManager

if TYPE_CHECKING:
    import asyncio

    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import (
        AchievementData,
        AchievementProgress,
        BadgeData,
        CanonicalTargetDefinition,
        ChallengeData,
        ChallengeProgress,
        EvaluationContext,
        EvaluationResult,
        KidBadgeProgress,
        KidData,
    )


# Default debounce timing (seconds)
_DEBOUNCE_SECONDS: float = 2.0


class GamificationManager(BaseManager):
    """Manager for gamification evaluation with debouncing.

    Responsibilities:
    - Track which kids need gamification re-evaluation (dirty tracking)
    - Debounce evaluation to batch rapid changes
    - Build evaluation context from coordinator data
    - Apply evaluation results (badge awards, achievements, challenges)
    - Emit gamification events (badge_earned, achievement_earned, etc.)

    NOT responsible for:
    - Point calculations (handled by EconomyManager)
    - Notifications (handled by NotificationManager via Coordinator)
    - Storage persistence (handled by Coordinator)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize the GamificationManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
        """
        super().__init__(hass, coordinator)

        # Pending evaluations - kids needing re-evaluation (persisted to storage)
        self._pending_evaluations: set[str] = set()

        # Debounce timer handle
        self._eval_timer: asyncio.TimerHandle | None = None

        # Debounce configuration
        self._debounce_seconds = _DEBOUNCE_SECONDS

    async def async_setup(self) -> None:
        """Set up the GamificationManager.

        Subscribe to:
        - STATS_READY: Startup cascade - initialize badge refs → emit GAMIFICATION_READY
        - Domain events that can trigger gamification checks
        - Lifecycle events for reactive cleanup

        Recover any pending evaluations from storage (restart resilience).
        """
        # Startup cascade - wait for stats to be ready before initializing badges
        self.listen(const.SIGNAL_SUFFIX_STATS_READY, self._on_stats_ready)

        # Point changes affect point-based badges
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)

        # Chore events affect chore count, daily completion, streaks
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DISAPPROVED, self._on_chore_disapproved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_STATUS_RESET, self._on_chore_status_reset)
        self.listen(const.SIGNAL_SUFFIX_CHORE_OVERDUE, self._on_chore_overdue)

        # Reward events can affect specific badges
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_approved)

        # Bonus/penalty events affect points
        self.listen(const.SIGNAL_SUFFIX_BONUS_APPLIED, self._on_bonus_applied)
        self.listen(const.SIGNAL_SUFFIX_PENALTY_APPLIED, self._on_penalty_applied)

        # Daily maintenance - cumulative badge cycle evaluation
        self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)

        # Lifecycle events - reactive cleanup (Platinum Architecture)
        self.listen(const.SIGNAL_SUFFIX_KID_DELETED, self._on_kid_deleted)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DELETED, self._on_chore_deleted)
        self.listen(const.SIGNAL_SUFFIX_CHORE_UPDATED, self._on_chore_updated)

        # Recover pending evaluations from storage (restart resilience)
        pending = self.coordinator._data.get(const.DATA_META, {}).get(
            const.DATA_META_PENDING_EVALUATIONS, []
        )
        if pending:
            const.LOGGER.info(
                "GamificationManager: Recovering %d pending evaluations from storage",
                len(pending),
            )
            self._pending_evaluations.update(pending)
            self._schedule_evaluation()

        normalized_count = self._normalize_all_scope_tracked_chores_storage()
        if normalized_count > 0:
            const.LOGGER.info(
                "GamificationManager: Normalized %d legacy all-scope tracked_chores entries",
                normalized_count,
            )
            self.coordinator._persist_and_update()

        const.LOGGER.debug(
            "GamificationManager initialized with %s second debounce",
            self._debounce_seconds,
        )

    def _normalize_all_scope_tracked_chores_storage(self) -> int:
        """Normalize legacy all-scope tracked_chores storage to empty selection lists.

        For tracked-chores badge types, an empty selected_chores configuration
        means "all chores". Older data may have materialized all chore UUIDs into
        kid badge progress, which becomes stale as chores are added/removed.

        Returns:
            Number of kid badge_progress records normalized.
        """
        normalized = 0

        for kid_info in self.coordinator.kids_data.values():
            badge_progress = kid_info.get(const.DATA_KID_BADGE_PROGRESS)
            if not isinstance(badge_progress, dict):
                continue

            for badge_id, progress in badge_progress.items():
                if not isinstance(progress, dict):
                    continue

                badge_info = self.coordinator.badges_data.get(badge_id)
                if not badge_info:
                    continue

                badge_type = badge_info.get(const.DATA_BADGE_TYPE)
                if badge_type not in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES:
                    continue
                if badge_type in const.INCLUDE_SPECIAL_OCCASION_BADGE_TYPES:
                    continue

                tracked_chores_cfg = badge_info.get(const.DATA_BADGE_TRACKED_CHORES, {})
                selected_chores = tracked_chores_cfg.get(
                    const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
                )
                tracked_chores = progress.get(
                    const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES
                )

                if (
                    isinstance(selected_chores, list)
                    and len(selected_chores) == 0
                    and isinstance(tracked_chores, list)
                    and len(tracked_chores) > 0
                ):
                    progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = []
                    normalized += 1

        return normalized

    def _on_stats_ready(self, payload: dict[str, Any]) -> None:
        """Handle startup cascade - initialize badge references after stats ready.

        Cascade Position: STATS_READY → GamificationManager → GAMIFICATION_READY

        Updates chore badge references for all kids, then signals completion
        of the startup cascade. UIManager can listen for dashboard finalization.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.debug(
            "GamificationManager: Processing STATS_READY - signaling ready"
        )

        # Signal cascade complete
        self.emit(const.SIGNAL_SUFFIX_GAMIFICATION_READY)
        const.LOGGER.info("KidsChores initialization cascade complete")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_points_changed(self, payload: dict[str, Any]) -> None:
        """Handle points_changed event.

        Skip re-evaluation for points from gamification awards to prevent
        infinite loops (badge awards points → triggers gamification check
        → awards badge → awards points → ...).

        Args:
            payload: Event data with kid_id, delta, source, etc.
        """
        kid_id = payload.get("kid_id")
        source = payload.get("source", "")

        # Skip gamification-originated point changes to prevent loops
        gamification_sources = {
            const.POINTS_SOURCE_BADGES,
            const.POINTS_SOURCE_ACHIEVEMENTS,
            const.POINTS_SOURCE_CHALLENGES,
        }
        if source in gamification_sources:
            const.LOGGER.debug(
                "GamificationManager: Skipping points_changed from source %s "
                "(gamification-originated)",
                source,
            )
            return

        # Update cumulative badge progress (for positive deltas only)
        delta = payload.get("delta", 0.0)
        if delta > 0 and kid_id:
            kid_info = self.coordinator.kids_data.get(kid_id)
            if kid_info:
                progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
                cycle_points = progress.get(
                    const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0.0
                )
                cycle_points += delta
                progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = round(
                    cycle_points, const.DATA_FLOAT_PRECISION
                )

        if kid_id:
            self._mark_pending(kid_id)

    def _on_chore_updated(self, payload: dict[str, Any]) -> None:
        """Handle chore_updated event (Platinum Architecture: event-driven).

        When a chore is updated (assignments changed, config modified), we need
        to recalculate badges for all kids since badge criteria may reference
        any chore and assignment changes affect which kids can earn badges.

        Args:
            payload: Event data with chore_id, chore_name, etc.
        """
        const.LOGGER.debug(
            "GamificationManager: Chore updated, recalculating all badges"
        )
        self.recalculate_all_badges()

    def _on_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle chore_approved event.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    def _on_chore_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle chore_disapproved event.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    def _on_chore_status_reset(self, payload: dict[str, Any]) -> None:
        """Handle chore_status_reset event.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    def _on_chore_overdue(self, payload: dict[str, Any]) -> None:
        """Handle chore_overdue event.

        Overdue events can affect "perfect week" or streak-based badges.

        Args:
            payload: Event data with kid_id, chore_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    def _on_reward_approved(self, payload: dict[str, Any]) -> None:
        """Handle reward_approved event.

        Args:
            payload: Event data with kid_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    def _on_bonus_applied(self, payload: dict[str, Any]) -> None:
        """Handle bonus_applied event.

        Args:
            payload: Event data with kid_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    def _on_penalty_applied(self, payload: dict[str, Any]) -> None:
        """Handle penalty_applied event.

        Args:
            payload: Event data with kid_id, etc.
        """
        kid_id = payload.get("kid_id")
        if kid_id:
            self._mark_pending(kid_id)

    async def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
        """Handle midnight rollover event.

        Triggers re-evaluation of all kids' gamification criteria.
        Cumulative badge maintenance is evaluated via the unified
        date-aware state machine in _evaluate_cumulative_badge.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.debug(
            "GamificationManager: Processing midnight rollover - "
            "recalculating all badges"
        )
        self.recalculate_all_badges()

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def recalculate_all_badges(self) -> None:
        """Global re-check of all badges for all kids.

        Marks all kids as dirty for re-evaluation. The debounced evaluation
        logic will handle persistence when changes are actually made.
        """
        const.LOGGER.info("Recalculate All Badges - Starting recalculation")
        for kid_id in self.coordinator.kids_data:
            self._mark_pending(kid_id)
        const.LOGGER.info("Recalculate All Badges - All kids marked for evaluation")

    async def award_achievement(self, kid_id: str, achievement_id: str) -> None:
        """Award the achievement to the kid.

        Update the achievement progress to indicate it is earned,
        and send notifications to both the kid and their parents.

        Args:
            kid_id: The internal UUID of the kid
            achievement_id: The internal UUID of the achievement
        """
        achievement_info = self.coordinator.achievements_data.get(achievement_id)
        if not achievement_info:
            const.LOGGER.error(
                "ERROR: Achievement Award - Achievement ID '%s' not found.",
                achievement_id,
            )
            return

        # Get or create the existing progress dictionary for this kid
        progress_for_kid = achievement_info.setdefault(
            const.DATA_ACHIEVEMENT_PROGRESS, {}
        ).get(kid_id)
        if progress_for_kid is None:
            # If it doesn't exist, initialize it with baseline from the kid's current total.
            kid_info: KidData | dict[str, Any] = self.coordinator.kids_data.get(
                kid_id, {}
            )
            # Read approved_all_time from chore_periods.all_time bucket (v43+)
            # Cast to dict[str, Any] since chore_periods is a runtime-added bucket
            chore_periods: dict[str, Any] = cast(
                "dict[str, Any]", kid_info.get(const.DATA_KID_CHORE_PERIODS, {})
            )
            all_time_container: dict[str, Any] = cast(
                "dict[str, Any]",
                chore_periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}),
            )
            # All-time uses nested structure: periods["all_time"]["all_time"] = {data}
            all_time_data: dict[str, Any] = cast(
                "dict[str, Any]", all_time_container.get(const.PERIOD_ALL_TIME, {})
            )
            progress_dict = {
                const.DATA_ACHIEVEMENT_BASELINE: all_time_data.get(
                    const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, const.DEFAULT_ZERO
                ),
                const.DATA_ACHIEVEMENT_CURRENT_VALUE: const.DEFAULT_ZERO,
                const.DATA_ACHIEVEMENT_AWARDED: False,
            }
            achievement_info[const.DATA_ACHIEVEMENT_PROGRESS][kid_id] = cast(
                "AchievementProgress", progress_dict
            )
            progress_for_kid = cast("AchievementProgress", progress_dict)

        # Type narrow: progress_for_kid is now guaranteed to be AchievementProgress
        progress_for_kid_checked: AchievementProgress = progress_for_kid

        # Mark achievement as earned for the kid
        progress_for_kid_checked[const.DATA_ACHIEVEMENT_AWARDED] = True
        progress_for_kid_checked[const.DATA_ACHIEVEMENT_CURRENT_VALUE] = (  # type: ignore[typeddict-unknown-key]
            achievement_info.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 1)
        )

        # Award the extra reward points defined in the achievement
        extra_points = achievement_info.get(
            const.DATA_ACHIEVEMENT_REWARD_POINTS, const.DEFAULT_ZERO
        )

        const.LOGGER.debug(
            "DEBUG: Achievement Award - Achievement ID '%s' to Kid ID '%s'",
            achievement_info.get(const.DATA_ACHIEVEMENT_NAME),
            kid_id,
        )

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit event for NotificationManager to send notifications
        # EconomyManager listens to this and handles point deposit
        self.emit(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_EARNED,
            kid_id=kid_id,
            achievement_id=achievement_id,
            kid_name=eh.get_kid_name_by_id(self.coordinator, kid_id) or "",
            achievement_name=achievement_info.get(const.DATA_ACHIEVEMENT_NAME, ""),
            achievement_points=extra_points,
        )

    async def award_challenge(self, kid_id: str, challenge_id: str) -> None:
        """Award the challenge to the kid.

        Update progress and notify kid/parents.

        Args:
            kid_id: The internal UUID of the kid
            challenge_id: The internal UUID of the challenge
        """
        challenge_info = self.coordinator.challenges_data.get(challenge_id)
        if not challenge_info:
            const.LOGGER.error(
                "ERROR: Challenge Award - Challenge ID '%s' not found", challenge_id
            )
            return

        # Get or create the existing progress dictionary for this kid
        progress_for_kid = challenge_info.setdefault(
            const.DATA_CHALLENGE_PROGRESS, {}
        ).setdefault(
            kid_id,
            {
                const.DATA_CHALLENGE_COUNT: const.DEFAULT_ZERO,
                const.DATA_CHALLENGE_AWARDED: False,
            },
        )

        # Mark challenge as earned for the kid by storing progress
        progress_for_kid[const.DATA_CHALLENGE_AWARDED] = True
        progress_for_kid[const.DATA_CHALLENGE_COUNT] = challenge_info.get(
            const.DATA_CHALLENGE_TARGET_VALUE, 1
        )

        # Get extra reward points from the challenge
        extra_points = challenge_info.get(
            const.DATA_CHALLENGE_REWARD_POINTS, const.DEFAULT_ZERO
        )

        const.LOGGER.debug(
            "DEBUG: Challenge Award - Challenge ID '%s' to Kid ID '%s'",
            challenge_info.get(const.DATA_CHALLENGE_NAME),
            kid_id,
        )

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit event for NotificationManager to send notifications
        # EconomyManager listens to this and handles point deposit
        self.emit(
            const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED,
            kid_id=kid_id,
            challenge_id=challenge_id,
            kid_name=eh.get_kid_name_by_id(self.coordinator, kid_id) or "",
            challenge_name=challenge_info.get(const.DATA_CHALLENGE_NAME, ""),
            challenge_points=extra_points,
        )

    def update_streak_progress(
        self, progress: AchievementProgress, today: date
    ) -> None:
        """Update a streak progress dict.

        If the last approved date was yesterday, increment the streak.
        Otherwise, reset to 1.

        Args:
            progress: Achievement progress dictionary to update
            today: Current date for streak calculation
        """
        last_date = None
        last_date_str = progress.get(const.DATA_KID_LAST_STREAK_DATE)
        if last_date_str:
            try:
                last_date = date.fromisoformat(last_date_str)
            except (ValueError, TypeError, KeyError):
                last_date = None

        # If already updated today, do nothing
        if last_date == today:
            return

        # If yesterday was the last update, increment the streak
        if last_date == today - timedelta(days=1):
            current_streak = progress.get(const.DATA_KID_CURRENT_STREAK, 0)
            progress[const.DATA_KID_CURRENT_STREAK] = current_streak + 1

        # Reset to 1 if not done yesterday
        else:
            progress[const.DATA_KID_CURRENT_STREAK] = 1

        progress[const.DATA_KID_LAST_STREAK_DATE] = today.isoformat()

    # =========================================================================
    # PENDING TRACKING AND DEBOUNCE (Phase 7.4: Persisted Queue)
    # =========================================================================

    def _persist_pending(self) -> None:
        """Persist pending evaluation queue to storage meta.

        This ensures restart resilience - if HA restarts during debounce window,
        pending evaluations will be recovered on next startup.

        Uses call_soon_threadsafe since this may be called from dispatcher
        (SyncWorker thread) via signal handlers.
        """
        self.hass.loop.call_soon_threadsafe(self._persist_pending_impl)

    def _persist_pending_impl(self) -> None:
        """Internal implementation that runs on the event loop thread."""
        meta = self.coordinator._data.setdefault(const.DATA_META, {})
        meta[const.DATA_META_PENDING_EVALUATIONS] = list(self._pending_evaluations)
        self.coordinator._persist()

    def _mark_pending(self, kid_id: str) -> None:
        """Mark a kid as needing re-evaluation (persisted).

        Args:
            kid_id: The internal UUID of the kid
        """
        was_already_pending = kid_id in self._pending_evaluations
        self._pending_evaluations.add(kid_id)

        # Only persist if this is a NEW addition (optimization for burst events)
        if not was_already_pending:
            self._persist_pending()

        self._schedule_evaluation()
        const.LOGGER.debug(
            "Kid %s marked pending for gamification evaluation, %d total pending",
            kid_id,
            len(self._pending_evaluations),
        )

    def _on_kid_deleted(self, payload: dict[str, Any]) -> None:
        """Remove deleted kid from pending evaluations and gamification data.

        Follows Platinum Architecture (Choreography): GamificationManager reacts
        to KID_DELETED signal and cleans its own domain data.

        Handles cleanup of:
        - Pending evaluation queue
        - Achievement progress/assignments
        - Challenge progress/assignments

        Args:
            payload: Event data containing kid_id
        """
        kid_id = payload.get("kid_id", "")
        if not kid_id:
            return

        # 1. Clean up pending evaluation queue
        if kid_id in self._pending_evaluations:
            self._pending_evaluations.discard(kid_id)
            self._persist_pending()
            const.LOGGER.debug(
                "GamificationManager: Removed deleted kid %s from pending queue",
                kid_id,
            )

        # 2. Clean up achievement/challenge progress and assignments (inline)
        cleaned = False
        for entities_data, section_name in [
            (self.coordinator._data.get(const.DATA_ACHIEVEMENTS, {}), "achievements"),
            (self.coordinator._data.get(const.DATA_CHALLENGES, {}), "challenges"),
        ]:
            for entity in entities_data.values():
                # Remove kid from progress dict
                progress = entity.get(const.DATA_PROGRESS, {})
                if kid_id in progress:
                    del progress[kid_id]
                    const.LOGGER.debug(
                        "Removed progress for deleted kid '%s' in %s",
                        kid_id,
                        section_name,
                    )
                    cleaned = True

                # Remove kid from assigned_kids list
                if const.DATA_ASSIGNED_KIDS in entity:
                    original_assigned = entity[const.DATA_ASSIGNED_KIDS]
                    if kid_id in original_assigned:
                        entity[const.DATA_ASSIGNED_KIDS] = [
                            k for k in original_assigned if k != kid_id
                        ]
                        const.LOGGER.debug(
                            "Removed deleted kid from %s '%s' assigned_kids",
                            section_name,
                            entity.get(const.DATA_NAME),
                        )
                        cleaned = True

        if cleaned:
            self.coordinator._persist()

        const.LOGGER.debug(
            "GamificationManager: Cleaned gamification refs for deleted kid %s",
            kid_id,
        )

    def _on_chore_deleted(self, payload: dict[str, Any]) -> None:
        """Clear selected_chore_id in achievements/challenges if deleted chore was selected.

        Follows Platinum Architecture (Choreography): GamificationManager reacts
        to CHORE_DELETED signal and cleans its own domain data.

        Args:
            payload: Event data containing chore_id, chore_name
        """
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "")
        if not chore_id:
            return

        valid_chore_ids = set(self.coordinator.chores_data.keys())
        cleaned = False

        # Clean achievements: clear selected_chore_id if chore no longer exists
        for achievement_info in self.coordinator._data.get(
            const.DATA_ACHIEVEMENTS, {}
        ).values():
            selected = achievement_info.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
            if selected and selected not in valid_chore_ids:
                achievement_info[const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID] = ""
                const.LOGGER.debug(
                    "Cleared selected chore in achievement '%s'",
                    achievement_info.get(const.DATA_NAME),
                )
                cleaned = True

        # Clean challenges: clear selected_chore_id if chore no longer exists
        for challenge_info in self.coordinator._data.get(
            const.DATA_CHALLENGES, {}
        ).values():
            selected = challenge_info.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID)
            if selected and selected not in valid_chore_ids:
                challenge_info[const.DATA_CHALLENGE_SELECTED_CHORE_ID] = (
                    const.SENTINEL_EMPTY
                )
                const.LOGGER.debug(
                    "Cleared selected chore in challenge '%s'",
                    challenge_info.get(const.DATA_NAME),
                )
                cleaned = True

        if cleaned:
            self.coordinator._persist()
            const.LOGGER.debug(
                "GamificationManager: Cleaned gamification refs for deleted chore '%s'",
                chore_name,
            )

    def _schedule_evaluation(self) -> None:
        """Schedule debounced evaluation.

        Cancels any existing timer and schedules a new one.
        This batches rapid changes into a single evaluation pass.

        Uses call_soon_threadsafe to safely interact with event loop
        since this method may be called from dispatcher (SyncWorker thread).
        """
        self.hass.loop.call_soon_threadsafe(self._schedule_evaluation_impl)

    def _schedule_evaluation_impl(self) -> None:
        """Internal implementation that runs on the event loop thread.

        This method must only be called from the event loop thread
        (via call_soon_threadsafe from _schedule_evaluation).
        """
        if self._eval_timer:
            self._eval_timer.cancel()

        self._eval_timer = self.hass.loop.call_later(
            self._debounce_seconds,
            lambda: self.hass.add_job(self._evaluate_pending_kids()),
        )

    async def _evaluate_pending_kids(self) -> None:
        """Evaluate all pending kids in batch.

        This is the main evaluation loop that runs after debounce timer fires.
        Clears the persistent queue after successful evaluation.
        """
        # Clear timer reference
        self._eval_timer = None

        # Capture and clear pending set atomically
        kids_to_evaluate = self._pending_evaluations.copy()
        self._pending_evaluations.clear()
        self._persist_pending()  # Clear from storage

        if not kids_to_evaluate:
            return

        const.LOGGER.debug(
            "Starting gamification evaluation for %d kids: %s",
            len(kids_to_evaluate),
            list(kids_to_evaluate),
        )

        for kid_id in kids_to_evaluate:
            try:
                await self._evaluate_kid(kid_id)
            except Exception:
                const.LOGGER.exception(
                    "Error evaluating gamification for kid %s",
                    kid_id,
                )

    async def _evaluate_kid(self, kid_id: str) -> None:
        """Evaluate all gamification criteria for a single kid.

        Args:
            kid_id: The internal UUID of the kid
        """
        # Build evaluation context
        context = self._build_evaluation_context(kid_id)
        if not context:
            const.LOGGER.warning(
                "Could not build evaluation context for kid %s",
                kid_id,
            )
            return

        # Get badge data from coordinator
        badges_data = self.coordinator.badges_data

        # Evaluate each badge
        for badge_id, badge_data in badges_data.items():
            await self._evaluate_badge_for_kid(context, badge_id, badge_data)

        # Get achievement data from coordinator
        achievements_data = self.coordinator.achievements_data

        # Evaluate each achievement
        for achievement_id, achievement_data in achievements_data.items():
            await self._evaluate_achievement_for_kid(
                context, achievement_id, achievement_data
            )

        # Get challenge data from coordinator
        challenges_data = self.coordinator.challenges_data

        # Evaluate each challenge
        for challenge_id, challenge_data in challenges_data.items():
            await self._evaluate_challenge_for_kid(
                context, challenge_id, challenge_data
            )

    # =========================================================================
    # BADGE EVALUATION (Split by badge type for clarity)
    # =========================================================================
    # CRITICAL PRINCIPLE: Badges are NEVER removed/lost.
    # - Cumulative: Can be DEMOTED (lower multiplier) but never removed
    # - Periodic: Can be re-awarded (increment award_count) but never removed

    async def _evaluate_badge_for_kid(
        self,
        context: EvaluationContext,
        badge_id: str,
        badge_data: BadgeData,
    ) -> None:
        """Route badge evaluation to type-specific handler.

        Args:
            context: The evaluation context for the kid
            badge_id: Badge internal ID
            badge_data: Badge definition
        """
        kid_id = context["kid_id"]

        # Skip badges not assigned to this kid (empty list = assigned to all)
        assigned_to = badge_data.get(const.DATA_BADGE_ASSIGNED_TO, [])
        if assigned_to and kid_id not in assigned_to:
            return

        badge_type = badge_data.get(const.DATA_BADGE_TYPE)

        # Route to type-specific evaluation (complete separation)
        if badge_type == const.BADGE_TYPE_CUMULATIVE:
            await self._evaluate_cumulative_badge(kid_id, badge_id, badge_data, context)
        else:
            # Periodic, special occasion, and any future badge types
            await self._evaluate_periodic_badge(kid_id, badge_id, badge_data, context)

    async def _evaluate_cumulative_badge(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        context: EvaluationContext,
    ) -> None:
        """Evaluate cumulative badge — unified state machine.

        Handles ALL state transitions for cumulative badges:
        - NOT earned → acquisition check (total_points vs threshold)
        - EARNED → date-aware maintenance state machine:
          - No maintenance enabled → always ACTIVE, skip
          - No dates yet → initialize maintenance dates
          - Period still open (today < end_date) → skip (accumulate points)
          - Period ended + maintenance met → confirm ACTIVE, reset cycle, advance dates
          - Period ended + not met + grace available → enter GRACE
          - Period ended + not met + no grace (or grace expired) → DEMOTED
          - In GRACE + met → re-promote to ACTIVE
          - In GRACE + expired → DEMOTED

        CRITICAL: Maintenance ONLY evaluated for the highest-earned cumulative badge.
        Lower-tier earned badges are always ACTIVE — their maintenance is never checked.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            context: Evaluation context
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        badges_earned = kid_data.get(const.DATA_KID_BADGES_EARNED, {})
        already_earned = badge_id in badges_earned

        if not already_earned:
            # First-time acquisition: check lifetime points via engine
            badge_dict = cast("dict[str, Any]", badge_data)
            result = GamificationEngine.evaluate_badge(context, badge_dict)
            if result.get("criteria_met", False):
                await self._apply_cumulative_first_award(
                    kid_id, badge_id, badge_data, result
                )
            return

        # ── ALREADY EARNED: maintenance state machine ──

        # Guard: only evaluate maintenance for the highest-earned cumulative badge
        highest_earned, _, _, _, _ = self.get_cumulative_badge_levels(kid_id)
        highest_badge_id = (
            highest_earned.get(const.DATA_BADGE_INTERNAL_ID) if highest_earned else None
        )
        if badge_id != highest_badge_id:
            return  # Lower-tier badge — always ACTIVE, skip maintenance

        # Guard: maintenance must be enabled (has frequency + threshold)
        if not self._badge_maintenance_enabled(badge_data):
            return  # No maintenance = always ACTIVE

        # Read maintenance state from cumulative_badge_progress
        progress = kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        progress_dict = cast("dict[str, Any]", progress)
        status = progress_dict.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        end_date_str: str | None = progress_dict.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
        )
        grace_end_str: str | None = progress_dict.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        )
        cycle_points = float(
            progress_dict.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0.0
            )
        )

        # Get maintenance threshold from badge target
        target = badge_data.get(const.DATA_BADGE_TARGET, {})
        maintenance_threshold = float(target.get(const.DATA_BADGE_MAINTENANCE_RULES, 0))

        today_iso = dt_today_iso()

        # 1. First-time dates (badge earned but no maintenance dates yet)
        if not end_date_str:
            self._apply_cumulative_init_maintenance_dates(
                kid_id, badge_id, badge_data, progress_dict
            )
            return

        met = cycle_points >= maintenance_threshold

        # 2. DEMOTED + maintenance met -> immediate re-promotion to ACTIVE
        # Do not wait for period boundary once threshold is met in demoted state.
        if status == const.CUMULATIVE_BADGE_STATE_DEMOTED and met:
            await self._apply_cumulative_maintenance_met(kid_id, badge_id, badge_data)
            return

        # 3. Maintenance period still open — just accumulate points, no action
        if today_iso < end_date_str:
            return

        # 4. Period ended (today >= end_date) — evaluate

        if met:
            # Maintenance met: confirm ACTIVE, reset cycle, advance dates, emit rewards
            await self._apply_cumulative_maintenance_met(kid_id, badge_id, badge_data)
            return

        # 5. Not met — check current state for grace/demotion
        if status == const.CUMULATIVE_BADGE_STATE_GRACE:
            # In grace period — check if grace expired
            if grace_end_str and today_iso >= grace_end_str:
                self._apply_cumulative_demotion(
                    kid_id,
                    badge_id,
                    badge_data,
                    progress_dict,
                    cycle_points,
                    maintenance_threshold,
                )
            # else: still within grace window, do nothing
            return

        # 6. Not in grace — enter grace or demote immediately
        reset_schedule = badge_data.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        grace_days = int(
            reset_schedule.get(const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS, 0)
        )

        if grace_days > 0:
            self._apply_cumulative_enter_grace(
                kid_id,
                badge_id,
                badge_data,
                progress_dict,
                end_date_str,
                grace_days,
            )
        else:
            self._apply_cumulative_demotion(
                kid_id,
                badge_id,
                badge_data,
                progress_dict,
                cycle_points,
                maintenance_threshold,
            )

    async def _evaluate_periodic_badge(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        context: EvaluationContext,
    ) -> None:
        """Evaluate periodic badge (period-based, never removed).

        Flow:
        1. NOT earned → Check acquisition (period stats vs threshold)
        2. Earned → Check acquisition again (same criteria for re-award)
           - Criteria met → Re-award badge (increment award_count, update periods)
           - Criteria not met → Do nothing (badge stays earned)

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            context: Evaluation context
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        canonical_target = self._map_badge_to_canonical_target(
            kid_id,
            badge_id,
            badge_data,
        )
        target_metadata = GamificationEngine.get_periodic_target_metadata(
            str(canonical_target.get("source_raw_type", ""))
        )
        if target_metadata is None:
            const.LOGGER.warning(
                "Skipping periodic badge evaluation for badge %s due to unknown target type",
                badge_id,
            )
            return

        # Ensure periodic badge progress structure exists before evaluation.
        self._ensure_kid_periodic_badge_structures(kid_id, badge_id, badge_data)

        schedule_changed = self._advance_non_cumulative_badge_cycle_if_needed(
            kid_id,
            badge_id,
            badge_data,
            today_iso=context["today_iso"],
        )
        if schedule_changed:
            self.coordinator._persist_and_update()

        badges_earned = kid_data.get(const.DATA_KID_BADGES_EARNED, {})
        already_earned = badge_id in badges_earned

        # Cast TypedDict to dict for engine
        badge_dict = cast("dict[str, Any]", badge_data)

        runtime_context = self._build_target_runtime_context(
            context,
            badge_id,
            badge_data,
            canonical_target=canonical_target,
        )

        # Periodic badges use same criteria for first award and re-awards
        result = GamificationEngine.evaluate_badge(runtime_context, badge_dict)

        if self._persist_target_progress_state(
            kid_id,
            source_item_id=badge_id,
            source_item_data=badge_data,
            result=result,
            already_earned=already_earned,
            today_iso=context["today_iso"],
            canonical_target=canonical_target,
        ):
            self.coordinator._persist_and_update()

        if result.get("criteria_met", False):
            await self._apply_target_award_effects(
                kid_id,
                badge_id,
                badge_data,
                result,
                already_earned=already_earned,
                canonical_target=canonical_target,
            )
        # If criteria not met: do nothing (badge stays earned, no re-award)

    def _map_badge_to_canonical_target(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
    ) -> CanonicalTargetDefinition:
        """Map a Badge Item to canonical target definition for shared processing."""
        target = cast("dict[str, Any]", badge_data.get(const.DATA_BADGE_TARGET, {}))
        target_type = str(target.get(const.DATA_BADGE_TARGET_TYPE, ""))

        target_metadata = GamificationEngine.get_periodic_target_metadata(target_type)
        canonical_type = (
            str(target_metadata.get("canonical_type"))
            if target_metadata is not None
            else "unknown_target"
        )

        if target_metadata is None:
            const.LOGGER.warning(
                "Unknown periodic badge target type '%s' for badge %s",
                target_type,
                badge_id,
            )

        mapped_target: CanonicalTargetDefinition = {
            "target_type": cast("Any", canonical_type),
            "threshold_value": float(
                target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0.0)
            ),
            "source_entity_type": "badge",
            "source_item_id": badge_id,
            "source_raw_type": target_type,
            "tracked_chore_ids": self.get_badge_in_scope_chores_list(
                badge_data, kid_id
            ),
        }

        if target_metadata is None:
            return mapped_target

        if target_metadata.get("use_due_only_scope"):
            mapped_target["use_due_only_scope"] = True
        if target_metadata.get("require_no_overdue"):
            mapped_target["require_no_overdue"] = True
        min_count_required = target_metadata.get("min_count_required")
        if min_count_required is not None:
            mapped_target["min_count_required"] = int(min_count_required)
        percent_required = target_metadata.get("percent_required")
        if percent_required is not None:
            mapped_target["percent_required"] = float(percent_required)

        return mapped_target

    def _resolve_target_status_transition(
        self,
        *,
        criteria_met: bool,
        already_earned: bool,
    ) -> str:
        """Resolve deterministic non-cumulative badge status transitions."""
        if criteria_met:
            return const.BADGE_STATE_EARNED
        if already_earned:
            return const.BADGE_STATE_ACTIVE_CYCLE
        return const.BADGE_STATE_IN_PROGRESS

    async def _apply_target_award_effects(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        result: EvaluationResult,
        *,
        already_earned: bool,
        canonical_target: CanonicalTargetDefinition,
    ) -> None:
        """Apply non-cumulative badge award effects through a shared adapter."""
        const.LOGGER.debug(
            "Applying target award effects for kid %s source %s canonical_type %s",
            kid_id,
            canonical_target.get("source_item_id", badge_id),
            canonical_target.get("target_type", "unknown"),
        )

        if not already_earned:
            await self._apply_periodic_first_award(kid_id, badge_id, badge_data, result)
            return

        if self._is_periodic_award_recorded_for_current_cycle(kid_id, badge_id):
            const.LOGGER.debug(
                "Skipping periodic re-award for kid %s badge %s "
                "(already awarded in current cycle)",
                kid_id,
                badge_id,
            )
            return

        await self._apply_periodic_reaward(kid_id, badge_id, badge_data)

    def _is_periodic_award_recorded_for_current_cycle(
        self,
        kid_id: str,
        badge_id: str,
    ) -> bool:
        """Return True if periodic badge already has an award recorded this cycle."""
        kid_data: KidData | dict[str, Any] = self.coordinator.kids_data.get(kid_id, {})

        badges_earned = cast(
            "dict[str, Any]", kid_data.get(const.DATA_KID_BADGES_EARNED, {})
        )
        badge_entry = cast("dict[str, Any]", badges_earned.get(badge_id, {}))
        last_awarded_raw = badge_entry.get(
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED, ""
        )
        last_awarded_day = str(last_awarded_raw)[:10]
        if not last_awarded_day:
            return False

        badge_progress_all = cast(
            "dict[str, Any]", kid_data.get(const.DATA_KID_BADGE_PROGRESS, {})
        )
        progress = cast("dict[str, Any]", badge_progress_all.get(badge_id, {}))
        start_date = str(progress.get(const.DATA_KID_BADGE_PROGRESS_START_DATE, ""))
        end_date = str(progress.get(const.DATA_KID_BADGE_PROGRESS_END_DATE, ""))

        if start_date and end_date:
            return start_date <= last_awarded_day <= end_date

        return last_awarded_day == dt_today_iso()

    def _build_target_runtime_context(
        self,
        base_context: EvaluationContext,
        badge_id: str,
        badge_data: BadgeData,
        *,
        canonical_target: CanonicalTargetDefinition,
    ) -> EvaluationContext:
        """Build shared target runtime context using stats-owned period reads.

        Args:
            base_context: Base evaluation context for the kid.
            badge_id: Badge internal ID.
            badge_data: Badge definition.
            canonical_target: Canonical target mapping for source item.

        Returns:
            EvaluationContext augmented with runtime keys consumed
            by GamificationEngine.
        """
        kid_id = base_context["kid_id"]
        today_iso = base_context["today_iso"]

        kid_data: KidData | dict[str, Any] = self.coordinator.kids_data.get(kid_id, {})
        badge_progress = cast(
            "dict[str, Any]",
            kid_data.get(const.DATA_KID_BADGE_PROGRESS, {}),
        )
        current_badge_progress = cast(
            "dict[str, Any]", badge_progress.get(badge_id, {})
        )

        tracked_chores = canonical_target.get(
            "tracked_chore_ids"
        ) or self.get_badge_in_scope_chores_list(badge_data, kid_id)

        today_stats = self.coordinator.statistics_manager.get_badge_scoped_today_stats(
            kid_id,
            tracked_chores,
            today_iso=today_iso,
            current_badge_progress=current_badge_progress,
        )
        today_completion = (
            self.coordinator.statistics_manager.get_badge_scoped_today_completion(
                kid_id,
                tracked_chores,
                today_iso=today_iso,
                only_due_today=False,
            )
        )
        today_completion_due = (
            self.coordinator.statistics_manager.get_badge_scoped_today_completion(
                kid_id,
                tracked_chores,
                today_iso=today_iso,
                only_due_today=True,
            )
        )

        runtime_context = cast("EvaluationContext", dict(base_context))
        runtime_context["current_badge_progress"] = cast(
            "KidBadgeProgress", current_badge_progress
        )
        runtime_context["today_stats"] = today_stats
        runtime_context["today_completion"] = today_completion
        runtime_context["today_completion_due"] = today_completion_due
        return runtime_context

    def _ensure_kid_periodic_badge_structures(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
    ) -> None:
        """Ensure non-cumulative badge progress structure exists for evaluation.

        Mirrors landlord ensure patterns used by chore/reward/badge tracking by
        creating missing containers before tenant/stat/evaluation logic reads them.

        Args:
            kid_id: Kid internal ID.
            badge_id: Badge internal ID.
            badge_data: Badge definition.
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        if const.DATA_KID_BADGE_PROGRESS not in kid_info:
            kid_info[const.DATA_KID_BADGE_PROGRESS] = {}

        badge_progress = cast(
            "dict[str, Any]", kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
        )
        entry = cast("dict[str, Any]", badge_progress.setdefault(badge_id, {}))

        badge_type = badge_data.get(const.DATA_BADGE_TYPE)
        target = cast("dict[str, Any]", badge_data.get(const.DATA_BADGE_TARGET, {}))

        entry.setdefault(
            const.DATA_KID_BADGE_PROGRESS_NAME,
            badge_data.get(const.DATA_BADGE_NAME),
        )
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_TYPE, badge_type)
        entry.setdefault(
            const.DATA_KID_BADGE_PROGRESS_STATUS,
            const.BADGE_STATE_IN_PROGRESS,
        )
        entry.setdefault(
            const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE,
            target.get(const.DATA_BADGE_TARGET_TYPE),
        )
        entry.setdefault(
            const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE,
            float(target.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0.0)),
        )

        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0.0)
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0)
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0)
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED, {})
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {})
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS, 0.0)
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET, False)
        entry.setdefault(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY, "")

    def _advance_non_cumulative_badge_cycle_if_needed(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        *,
        today_iso: str,
    ) -> bool:
        """Advance expired daily/periodic cycle windows and reset cycle counters.

        Args:
            kid_id: Kid internal ID.
            badge_id: Badge internal ID.
            badge_data: Badge definition.
            today_iso: Local date key for current evaluation cycle.

        Returns:
            True if schedule/progress fields were updated.
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return False

        badge_progress = cast(
            "dict[str, Any]", kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
        )
        progress = cast("dict[str, Any]", badge_progress.get(badge_id, {}))
        if not progress:
            return False

        recurring_frequency = str(
            progress.get(
                const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY,
                const.FREQUENCY_NONE,
            )
        )
        if recurring_frequency == const.FREQUENCY_NONE:
            return False

        end_date_iso = str(progress.get(const.DATA_KID_BADGE_PROGRESS_END_DATE, ""))
        if not end_date_iso:
            return False

        if end_date_iso >= today_iso:
            return False

        rolled_cycles = 0
        current_end = end_date_iso
        previous_end = end_date_iso
        while current_end < today_iso:
            next_end = self._get_next_non_cumulative_cycle_end(
                badge_data,
                current_end,
            )
            if not next_end or next_end <= current_end:
                break
            previous_end = current_end
            current_end = next_end
            rolled_cycles += 1

        if rolled_cycles == 0:
            return False

        progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = current_end
        progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = previous_end
        progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
            int(progress.get(const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT, 0))
            + rolled_cycles
        )
        progress[const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED] = False

        progress[const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT] = 0.0
        progress[const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT] = 0
        progress[const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT] = 0
        progress[const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED] = {}
        progress[const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED] = {}
        progress[const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS] = 0.0
        progress[const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET] = False
        progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = ""

        return True

    def _get_next_non_cumulative_cycle_end(
        self,
        badge_data: BadgeData,
        current_end_iso: str,
    ) -> str | None:
        """Get the next cycle end date for a non-cumulative badge."""
        reset_schedule = badge_data.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        recurring_frequency = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
            const.FREQUENCY_NONE,
        )

        if recurring_frequency == const.FREQUENCY_CUSTOM:
            custom_interval = reset_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
            )
            custom_interval_unit = reset_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
            )
            if custom_interval and custom_interval_unit:
                custom_result = dt_add_interval(
                    current_end_iso,
                    interval_unit=custom_interval_unit,
                    delta=int(custom_interval),
                    require_future=False,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                return str(custom_result) if custom_result else None
            return None

        next_result = dt_next_schedule(
            current_end_iso,
            interval_type=recurring_frequency,
            require_future=False,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )
        return str(next_result) if next_result else None

    def _persist_target_progress_state(
        self,
        kid_id: str,
        *,
        source_item_id: str,
        source_item_data: BadgeData,
        result: EvaluationResult,
        already_earned: bool,
        today_iso: str,
        canonical_target: CanonicalTargetDefinition,
    ) -> bool:
        """Persist shared non-cumulative target progress state.

        This shared mutator is currently badge-backed and is intentionally
        source-shaped for future achievement/challenge wrapper reuse.

        Args:
            kid_id: Kid internal ID.
            source_item_id: Source item UUID (badge for now).
            source_item_data: Source item data (badge for now).
            result: Evaluation result from engine.
            already_earned: Whether source has already been earned/completed.
            today_iso: Current local day ISO key.
            canonical_target: Canonical target mapping for this source.

        Returns:
            True when any persisted field changed.
        """
        return self._persist_periodic_badge_progress(
            kid_id,
            source_item_id,
            source_item_data,
            result,
            already_earned=already_earned,
            today_iso=today_iso,
            canonical_target=canonical_target,
        )

    def _persist_periodic_badge_progress(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        result: EvaluationResult,
        *,
        already_earned: bool,
        today_iso: str,
        canonical_target: CanonicalTargetDefinition | None = None,
    ) -> bool:
        """Persist runtime periodic evaluation fields into kid badge progress.

        Args:
            kid_id: Kid internal ID.
            badge_id: Badge internal ID.
            badge_data: Badge definition.
            result: Evaluation result from engine.
            already_earned: Whether kid already has this badge in badges_earned.
            today_iso: Current local day ISO key.
            canonical_target: Canonical target mapping for this source.
                Optional for backward-compatible direct calls.

        Returns:
            True when any persisted field changed.
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return False

        badge_progress_all = cast(
            "dict[str, Any]", kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
        )
        progress = cast("dict[str, Any]", badge_progress_all.get(badge_id, {}))
        if not progress:
            return False

        changed = False

        overall_progress = round(
            float(result.get("overall_progress", 0.0)),
            const.DATA_FLOAT_PRECISION,
        )
        criteria_met = bool(result.get("criteria_met", False))
        if (
            progress.get(const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS)
            != overall_progress
        ):
            progress[const.DATA_KID_BADGE_PROGRESS_OVERALL_PROGRESS] = overall_progress
            changed = True
        if progress.get(const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET) != criteria_met:
            progress[const.DATA_KID_BADGE_PROGRESS_CRITERIA_MET] = criteria_met
            changed = True

        expected_status = self._resolve_target_status_transition(
            criteria_met=criteria_met,
            already_earned=already_earned,
        )
        if progress.get(const.DATA_KID_BADGE_PROGRESS_STATUS) != expected_status:
            progress[const.DATA_KID_BADGE_PROGRESS_STATUS] = expected_status
            changed = True

        if canonical_target is not None:
            target_type = canonical_target.get("source_raw_type")
        else:
            target = cast("dict[str, Any]", badge_data.get(const.DATA_BADGE_TARGET, {}))
            target_type = target.get(const.DATA_BADGE_TARGET_TYPE)

        target_metadata = GamificationEngine.get_periodic_target_metadata(
            str(target_type)
        )
        persist_bucket = (
            str(target_metadata.get("persist_bucket"))
            if target_metadata is not None
            else "unknown"
        )

        criterion_results = result.get("criterion_results", [])
        criterion_current_value = 0.0
        if criterion_results:
            criterion_current_value = float(
                criterion_results[0].get("current_value", 0.0)
            )

        if persist_bucket == "points_cycle":
            if (
                float(
                    progress.get(const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0.0)
                )
                != criterion_current_value
            ):
                progress[const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT] = (
                    criterion_current_value
                )
                changed = True
                if (
                    progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY)
                    != today_iso
                ):
                    progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_iso
                    changed = True

        elif persist_bucket == "chores_cycle":
            chores_count = int(criterion_current_value)
            if (
                int(progress.get(const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0))
                != chores_count
            ):
                progress[const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT] = (
                    chores_count
                )
                changed = True
                if (
                    progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY)
                    != today_iso
                ):
                    progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_iso
                    changed = True

        elif persist_bucket == "days_cycle":
            previous_days = int(
                progress.get(const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0)
            )
            days_count = int(criterion_current_value)
            if previous_days != days_count:
                progress[const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT] = days_count
                changed = True

            previous_update_day = str(
                progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY, "")
            )
            if days_count > 0 and (
                days_count != previous_days or previous_update_day == today_iso
            ):
                if previous_update_day != today_iso:
                    progress[const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY] = today_iso
                    changed = True

        elif persist_bucket == "unknown":
            const.LOGGER.warning(
                "Skipping periodic badge progress persistence for unknown target type '%s'",
                target_type,
            )

        return changed

    # =========================================================================
    # CUMULATIVE BADGE OPERATIONS
    # =========================================================================

    async def _apply_cumulative_first_award(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        result: EvaluationResult,
    ) -> None:
        """Award cumulative badge for the first time.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            result: Evaluation result (unused but kept for signature consistency)
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        const.LOGGER.info("Kid %s earned cumulative badge %s", kid_id, badge_id)

        # Initialize cumulative badge progress
        progress = kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        progress_dict = cast("dict[str, Any]", progress)
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0.0
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
            const.CUMULATIVE_BADGE_STATE_ACTIVE
        )

        # Set maintenance dates if enabled
        maintenance_enabled = self._badge_maintenance_enabled(badge_data)
        if maintenance_enabled:
            end_date, grace_end = self._calculate_maintenance_dates(badge_data)
            progress_dict[
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
            ] = end_date
            progress_dict[
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
            ] = grace_end

        # Update badge tracking (calls _persist_and_update)
        await self._record_badge_earned(kid_id, badge_id, badge_data)

        # Build and emit Award Manifest
        manifest = self._build_badge_award_manifest(badge_data)
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            kid_id=kid_id,
            badge_id=badge_id,
            kid_name=eh.get_kid_name_by_id(self.coordinator, kid_id) or "",
            badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
            **manifest,
        )

    def _apply_cumulative_init_maintenance_dates(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        progress_dict: dict[str, Any],
    ) -> None:
        """Initialize maintenance dates for a newly earned cumulative badge.

        Called when a badge is earned but has no maintenance_end_date yet.
        Sets the first maintenance window dates and persists.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            progress_dict: Mutable reference to cumulative_badge_progress
        """
        end_date, grace_end = self._calculate_maintenance_dates(badge_data)
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
            end_date
        )
        progress_dict[
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        ] = grace_end
        self.coordinator._persist_and_update()

        kid_name = eh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
        const.LOGGER.debug(
            "Initialized maintenance dates for kid '%s' badge '%s': "
            "end=%s, grace_end=%s",
            kid_name,
            badge_data.get(const.DATA_BADGE_NAME) or badge_id,
            end_date,
            grace_end,
        )

    def _apply_cumulative_enter_grace(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        progress_dict: dict[str, Any],
        end_date_str: str,
        grace_days: int,
    ) -> None:
        """Enter grace period for cumulative badge maintenance.

        Transitions status to GRACE and calculates grace_end date from
        the maintenance end_date + grace_days.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            progress_dict: Mutable reference to cumulative_badge_progress
            end_date_str: The maintenance end date (ISO string) grace starts from
            grace_days: Number of grace days
        """
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
            const.CUMULATIVE_BADGE_STATE_GRACE
        )
        grace_end = dt_add_interval(
            end_date_str,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=grace_days,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )
        progress_dict[
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        ] = str(grace_end) if grace_end else None
        self.coordinator._persist_and_update()

        kid_name = eh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
        const.LOGGER.info(
            "Kid '%s' entered grace period for badge '%s' (grace ends: %s)",
            kid_name,
            badge_data.get(const.DATA_BADGE_NAME) or badge_id,
            grace_end,
        )

    def _apply_cumulative_demotion(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        progress_dict: dict[str, Any],
        cycle_points: float,
        maintenance_threshold: float,
    ) -> None:
        """Demote cumulative badge — maintenance not met.

        Sets status to DEMOTED, resets cycle_points, advances maintenance dates
        for next evaluation cycle, recalculates point multiplier, and emits
        BADGE_UPDATED signal.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            progress_dict: Mutable reference to cumulative_badge_progress
            cycle_points: Points earned this cycle (for logging)
            maintenance_threshold: Required threshold (for logging)
        """
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
            const.CUMULATIVE_BADGE_STATE_DEMOTED
        )
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0.0

        # Advance dates for next cycle (so demotion evaluation starts fresh)
        end_date, grace_end = self._calculate_maintenance_dates(badge_data)
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
            end_date
        )
        progress_dict[
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        ] = grace_end

        # Recalculate multiplier (uses next-lower badge)
        self.update_point_multiplier_for_kid(kid_id)

        self.coordinator._persist_and_update()

        kid_name = eh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
        const.LOGGER.info(
            "Kid '%s' demoted from badge '%s' — "
            "maintenance not met (cycle_points=%.1f, required=%.1f)",
            kid_name,
            badge_data.get(const.DATA_BADGE_NAME) or badge_id,
            cycle_points,
            maintenance_threshold,
        )

        self.emit(
            const.SIGNAL_SUFFIX_BADGE_UPDATED,
            kid_id=kid_id,
            badge_id=badge_id,
            status="demoted",
            badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
        )

    async def _apply_cumulative_maintenance_met(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
    ) -> None:
        """Handle cumulative badge maintenance met — confirm ACTIVE, reset cycle.

        Called when maintenance threshold is met.
        Applies regardless of current status (ACTIVE, GRACE, or DEMOTED).

        Actions:
        1. Set status = ACTIVE
        2. Reset cycle_points = 0
        3. Advance maintenance dates for next cycle
        4. Recalculate point multiplier (restores full if was DEMOTED)
        5. If current status is ACTIVE/GRACE: update badges_earned + emit manifest
        6. If current status is DEMOTED: do not emit award manifest

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        progress = kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        progress_dict = cast("dict[str, Any]", progress)
        current_status = progress_dict.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        was_demoted = current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED

        # Data corruption repair: DEMOTED when maintenance disabled
        maintenance_enabled = self._badge_maintenance_enabled(badge_data)
        if (
            not maintenance_enabled
            and current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED
        ):
            progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
                const.CUMULATIVE_BADGE_STATE_ACTIVE
            )
            self.coordinator._persist_and_update()
            const.LOGGER.info(
                "Repaired invalid DEMOTED status for kid %s badge %s "
                "(maintenance not enabled)",
                kid_id,
                badge_id,
            )
            return

        # Set ACTIVE, reset cycle
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
            const.CUMULATIVE_BADGE_STATE_ACTIVE
        )
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0.0

        # Advance maintenance dates for next cycle
        end_date, grace_end = self._calculate_maintenance_dates(badge_data)
        progress_dict[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
            end_date
        )
        progress_dict[
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        ] = grace_end

        # Update badge tracking (period stats) only for non-demoted maintenance cycles.
        # For DEMOTED -> ACTIVE reactivation we restore status/multiplier only.
        if not was_demoted:
            self.update_badges_earned_for_kid(kid_id, badge_id)

        # Recalculate multiplier (restore full strength if was DEMOTED)
        self.update_point_multiplier_for_kid(kid_id)

        # Persist changes
        self.coordinator._persist_and_update()

        kid_name = eh.get_kid_name_by_id(self.coordinator, kid_id) or kid_id
        const.LOGGER.info(
            "Kid '%s' maintained badge '%s' — cycle reset, next maintenance: %s",
            kid_name,
            badge_data.get(const.DATA_BADGE_NAME, badge_id),
            end_date,
        )

        if was_demoted:
            self.emit(
                const.SIGNAL_SUFFIX_BADGE_UPDATED,
                kid_id=kid_id,
                badge_id=badge_id,
                status=const.CUMULATIVE_BADGE_STATE_ACTIVE,
                badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
            )
            return

        # Build and emit Award Manifest
        manifest = self._build_badge_award_manifest(badge_data)
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            kid_id=kid_id,
            badge_id=badge_id,
            kid_name=kid_name,
            badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
            **manifest,
        )

    def _badge_maintenance_enabled(self, badge_data: BadgeData) -> bool:
        """Check if cumulative badge has maintenance enabled.

        Maintenance requires BOTH a reset schedule AND a maintenance threshold.

        Args:
            badge_data: Badge definition

        Returns:
            True if maintenance is enabled
        """
        target = badge_data.get(const.DATA_BADGE_TARGET, {})
        maintenance_threshold = float(target.get(const.DATA_BADGE_MAINTENANCE_RULES, 0))
        reset_schedule = badge_data.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        recurring_frequency = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
            const.FREQUENCY_NONE,
        )
        return recurring_frequency != const.FREQUENCY_NONE and maintenance_threshold > 0

    # =========================================================================
    # PERIODIC BADGE OPERATIONS
    # =========================================================================

    async def _apply_periodic_first_award(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
        result: EvaluationResult,
    ) -> None:
        """Award periodic badge for the first time.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
            result: Evaluation result (unused but kept for signature consistency)
        """
        const.LOGGER.info("Kid %s earned periodic badge %s", kid_id, badge_id)

        # Update badge tracking (calls _persist_and_update)
        await self._record_badge_earned(kid_id, badge_id, badge_data)

        # Build and emit Award Manifest
        manifest = self._build_badge_award_manifest(badge_data)
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            kid_id=kid_id,
            badge_id=badge_id,
            kid_name=eh.get_kid_name_by_id(self.coordinator, kid_id) or "",
            badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
            **manifest,
        )

    async def _apply_periodic_reaward(
        self,
        kid_id: str,
        badge_id: str,
        badge_data: BadgeData,
    ) -> None:
        """Re-award periodic badge (increment award_count).

        Badges are never removed. Re-earning means incrementing award_count
        and updating period statistics.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID
            badge_data: Badge definition
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return

        badges_earned = kid_data.get(const.DATA_KID_BADGES_EARNED, {})
        badge_entry = badges_earned.get(badge_id)
        if not badge_entry:
            return

        const.LOGGER.info(
            "Kid %s re-earned periodic badge %s (incrementing award_count)",
            kid_id,
            badge_id,
        )

        # Increment award_count (badge re-award)
        badge_entry_dict = cast("dict[str, Any]", badge_entry)
        current_count = badge_entry_dict.get(
            const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 1
        )
        badge_entry_dict[const.DATA_KID_BADGES_EARNED_AWARD_COUNT] = current_count + 1

        # Update last award date
        badge_entry_dict[const.DATA_KID_BADGES_EARNED_LAST_AWARDED] = dt_now_iso()

        # Persist changes
        self.coordinator._persist_and_update()

        # Build and emit Award Manifest (kid gets all badge rewards again)
        manifest = self._build_badge_award_manifest(badge_data)
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            kid_id=kid_id,
            badge_id=badge_id,
            kid_name=eh.get_kid_name_by_id(self.coordinator, kid_id) or "",
            badge_name=badge_data.get(const.DATA_BADGE_NAME, "Unknown"),
            **manifest,
        )

    # =========================================================================
    # ACHIEVEMENT EVALUATION
    # =========================================================================

    async def _evaluate_achievement_for_kid(
        self,
        context: EvaluationContext,
        achievement_id: str,
        achievement_data: AchievementData,
    ) -> None:
        """Evaluate a single achievement for a kid.

        Args:
            context: The evaluation context for the kid
            achievement_id: Achievement internal ID
            achievement_data: Achievement definition
        """
        kid_id = context["kid_id"]

        # Check if kid already has this achievement (awarded flag in progress)
        achievement_progress = achievement_data.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
        kid_progress = achievement_progress.get(kid_id, {})
        already_awarded = kid_progress.get(const.DATA_ACHIEVEMENT_AWARDED, False)

        if already_awarded:
            # Achievements are permanent - no re-evaluation needed
            return

        canonical_target = self._map_achievement_to_canonical_target(
            kid_id,
            achievement_id,
            achievement_data,
            kid_progress,
        )
        runtime_context = self._build_source_runtime_context(
            context,
            kid_id=kid_id,
            canonical_target=canonical_target,
            current_achievement_progress=kid_progress,
        )
        result = GamificationEngine.evaluate_canonical_target(
            runtime_context,
            entity_id=achievement_id,
            entity_name=str(
                achievement_data.get(const.DATA_ACHIEVEMENT_NAME, "Unknown Achievement")
            ),
            entity_type="achievement",
            canonical_target=canonical_target,
        )

        # Apply result
        await self._apply_achievement_result(
            kid_id, achievement_id, achievement_data, result
        )

    async def _apply_achievement_result(
        self,
        kid_id: str,
        achievement_id: str,
        achievement_data: AchievementData,
        result: EvaluationResult,
    ) -> None:
        """Apply achievement evaluation result.

        Args:
            kid_id: Kid's internal ID
            achievement_id: Achievement internal ID
            achievement_data: Achievement definition
            result: Evaluation result from engine
        """
        criteria_met = result.get("criteria_met", False)

        if criteria_met:
            const.LOGGER.info(
                "Kid %s unlocked achievement %s",
                kid_id,
                achievement_id,
            )
            # Persist achievement award (handles data update + notifications)
            await self.award_achievement(kid_id, achievement_id)

            # Emit event for any additional listeners
            self.emit(
                const.SIGNAL_SUFFIX_ACHIEVEMENT_EARNED,
                kid_id=kid_id,
                achievement_id=achievement_id,
                achievement_name=achievement_data.get(
                    const.DATA_ACHIEVEMENT_NAME, "Unknown"
                ),
                result=result,
            )

    # =========================================================================
    # CHALLENGE EVALUATION
    # =========================================================================

    async def _evaluate_challenge_for_kid(
        self,
        context: EvaluationContext,
        challenge_id: str,
        challenge_data: ChallengeData,
    ) -> None:
        """Evaluate a single challenge for a kid.

        Args:
            context: The evaluation context for the kid
            challenge_id: Challenge internal ID
            challenge_data: Challenge definition
        """
        kid_id = context["kid_id"]

        # Check if kid already completed this challenge (awarded flag in progress)
        challenge_progress = challenge_data.get(const.DATA_CHALLENGE_PROGRESS, {})
        kid_progress = challenge_progress.get(kid_id, {})
        already_awarded = kid_progress.get(const.DATA_CHALLENGE_AWARDED, False)

        if already_awarded:
            # Challenges can only be completed once
            return

        today_iso = str(context.get("today_iso", dt_today_iso()))
        start_date = str(challenge_data.get(const.DATA_CHALLENGE_START_DATE, ""))
        end_date = str(challenge_data.get(const.DATA_CHALLENGE_END_DATE, ""))

        # Lifecycle wrapper ownership stays in manager: only active-window
        # challenges are evaluated.
        if start_date and today_iso < start_date[:10]:
            return
        if end_date and today_iso > end_date[:10]:
            return

        canonical_target = self._map_challenge_to_canonical_target(
            kid_id,
            challenge_id,
            challenge_data,
        )
        runtime_context = self._build_source_runtime_context(
            context,
            kid_id=kid_id,
            canonical_target=canonical_target,
            current_challenge_progress=kid_progress,
        )
        result = GamificationEngine.evaluate_canonical_target(
            runtime_context,
            entity_id=challenge_id,
            entity_name=str(
                challenge_data.get(const.DATA_CHALLENGE_NAME, "Unknown Challenge")
            ),
            entity_type="challenge",
            canonical_target=canonical_target,
        )

        # Apply result
        await self._apply_challenge_result(kid_id, challenge_id, challenge_data, result)

    def _map_achievement_to_canonical_target(
        self,
        kid_id: str,
        achievement_id: str,
        achievement_data: AchievementData,
        kid_progress: AchievementProgress | dict[str, Any],
    ) -> CanonicalTargetDefinition:
        """Map Achievement Item definitions to canonical target definitions."""
        raw_type = str(achievement_data.get(const.DATA_ACHIEVEMENT_TYPE, ""))
        canonical_type = str(
            const.ACHIEVEMENT_TO_CANONICAL_TARGET_MAP.get(raw_type, "unknown_target")
        )
        source_badge_id = str(
            achievement_data.get(const.DATA_ACHIEVEMENT_SOURCE_BADGE_ID, "")
        )
        kid_data = self.coordinator.kids_data.get(kid_id)
        kid_badges_earned = (
            kid_data.get(const.DATA_KID_BADGES_EARNED, {}) if kid_data else {}
        )

        if (
            raw_type == const.ACHIEVEMENT_TYPE_TOTAL
            and source_badge_id
            and source_badge_id in kid_badges_earned
        ):
            canonical_type = const.CANONICAL_TARGET_TYPE_BADGE_AWARD_COUNT

        mapped: CanonicalTargetDefinition = {
            "target_type": cast("Any", canonical_type),
            "threshold_value": float(
                achievement_data.get(const.DATA_ACHIEVEMENT_TARGET_VALUE, 0.0)
            ),
            "source_entity_type": "achievement",
            "source_item_id": achievement_id,
            "source_raw_type": raw_type,
            "baseline_value": float(
                cast("Any", kid_progress).get(const.DATA_ACHIEVEMENT_BASELINE, 0)
            ),
        }
        selected_chore_id = str(
            achievement_data.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, "")
        )
        if selected_chore_id:
            kid_assigned_chores = self._get_kid_assigned_chores(kid_id)
            mapped["tracked_chore_ids"] = (
                [selected_chore_id] if selected_chore_id in kid_assigned_chores else []
            )
        if source_badge_id:
            mapped["source_badge_id"] = source_badge_id
        return mapped

    def _map_challenge_to_canonical_target(
        self,
        kid_id: str,
        challenge_id: str,
        challenge_data: ChallengeData,
    ) -> CanonicalTargetDefinition:
        """Map Challenge Item definitions to canonical target definitions."""
        raw_type = str(challenge_data.get(const.DATA_CHALLENGE_TYPE, ""))
        canonical_type = str(
            const.CHALLENGE_TO_CANONICAL_TARGET_MAP.get(raw_type, "unknown_target")
        )

        mapped: CanonicalTargetDefinition = {
            "target_type": cast("Any", canonical_type),
            "threshold_value": float(
                challenge_data.get(const.DATA_CHALLENGE_TARGET_VALUE, 0.0)
            ),
            "source_entity_type": "challenge",
            "source_item_id": challenge_id,
            "source_raw_type": raw_type,
        }
        selected_chore_id = str(
            challenge_data.get(const.DATA_CHALLENGE_SELECTED_CHORE_ID, "")
        )
        if selected_chore_id:
            kid_assigned_chores = self._get_kid_assigned_chores(kid_id)
            mapped["tracked_chore_ids"] = (
                [selected_chore_id] if selected_chore_id in kid_assigned_chores else []
            )
        return mapped

    def _build_source_runtime_context(
        self,
        base_context: EvaluationContext,
        *,
        kid_id: str,
        canonical_target: CanonicalTargetDefinition,
        current_achievement_progress: AchievementProgress
        | dict[str, Any]
        | None = None,
        current_challenge_progress: ChallengeProgress | dict[str, Any] | None = None,
    ) -> EvaluationContext:
        """Build runtime context for canonical source target evaluation."""
        runtime_context = cast("EvaluationContext", dict(base_context))
        today_iso = str(base_context.get("today_iso", dt_today_iso()))
        tracked_chores_from_target = canonical_target.get("tracked_chore_ids")
        if isinstance(tracked_chores_from_target, list):
            tracked_chores = tracked_chores_from_target
        else:
            tracked_chores = self._get_kid_assigned_chores(kid_id)

        runtime_context["today_stats"] = (
            self.coordinator.statistics_manager.get_badge_scoped_today_stats(
                kid_id,
                tracked_chores,
                today_iso=today_iso,
                current_badge_progress=None,
            )
        )
        runtime_context["today_completion"] = (
            self.coordinator.statistics_manager.get_badge_scoped_today_completion(
                kid_id,
                tracked_chores,
                today_iso=today_iso,
                only_due_today=False,
            )
        )
        runtime_context["today_completion_due"] = (
            self.coordinator.statistics_manager.get_badge_scoped_today_completion(
                kid_id,
                tracked_chores,
                today_iso=today_iso,
                only_due_today=True,
            )
        )

        if current_achievement_progress is not None:
            runtime_context["current_achievement_progress"] = cast(
                "Any", current_achievement_progress
            )
        if current_challenge_progress is not None:
            runtime_context["current_challenge_progress"] = cast(
                "Any", current_challenge_progress
            )

        return runtime_context

    async def _apply_challenge_result(
        self,
        kid_id: str,
        challenge_id: str,
        challenge_data: ChallengeData,
        result: EvaluationResult,
    ) -> None:
        """Apply challenge evaluation result.

        Args:
            kid_id: Kid's internal ID
            challenge_id: Challenge internal ID
            challenge_data: Challenge definition
            result: Evaluation result from engine
        """
        criteria_met = result.get("criteria_met", False)

        if criteria_met:
            const.LOGGER.info(
                "Kid %s completed challenge %s",
                kid_id,
                challenge_id,
            )
            # Persist challenge completion (handles data update + notifications)
            await self.award_challenge(kid_id, challenge_id)

            # Emit event for any additional listeners
            self.emit(
                const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED,
                kid_id=kid_id,
                challenge_id=challenge_id,
                challenge_name=challenge_data.get(const.DATA_CHALLENGE_NAME, "Unknown"),
                result=result,
            )

    # =========================================================================
    # CONTEXT BUILDING
    # =========================================================================

    def _build_evaluation_context(self, kid_id: str) -> EvaluationContext | None:
        """Build evaluation context from coordinator data.

        This extracts minimal data needed for gamification evaluation.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            EvaluationContext dict or None if kid not found
        """
        kid_data = self.coordinator.kids_data.get(kid_id)
        if not kid_data:
            return None

        # Get today's ISO date using helper
        today_iso = dt_today_iso()

        # Get total earned from all_time period bucket using stats engine
        point_periods = kid_data.get(const.DATA_KID_POINT_PERIODS, {})
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_KID_POINT_PERIODS_ALL_TIME
        }
        total_earned = float(
            self.coordinator.stats.get_period_total(
                point_periods,
                const.PERIOD_ALL_TIME,
                const.DATA_KID_POINT_PERIOD_POINTS_EARNED,
                period_key_mapping=period_key_mapping,
            )
        )

        # Get badge progress from kid data
        badge_progress = kid_data.get(const.DATA_KID_BADGE_PROGRESS, {})

        # Build achievement progress from achievements_data
        # (progress is stored in each achievement, keyed by kid_id)
        achievement_progress: dict[str, Any] = {}
        for ach_id, ach_data in self.coordinator.achievements_data.items():
            ach_progress = ach_data.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
            if kid_id in ach_progress:
                achievement_progress[ach_id] = ach_progress[kid_id]

        # Build challenge progress from challenges_data
        # (progress is stored in each challenge, keyed by kid_id)
        challenge_progress: dict[str, Any] = {}
        for chal_id, chal_data in self.coordinator.challenges_data.items():
            chal_progress = chal_data.get(const.DATA_CHALLENGE_PROGRESS, {})
            if kid_id in chal_progress:
                challenge_progress[chal_id] = chal_progress[kid_id]

        # Build context (using cast pattern for TypedDict compatibility)
        context: EvaluationContext = {
            "kid_id": kid_id,
            "kid_name": kid_data.get(const.DATA_KID_NAME, "Unknown"),
            "current_points": float(kid_data.get(const.DATA_KID_POINTS, 0.0)),
            "total_points_earned": total_earned,
            "badge_progress": badge_progress,
            "cumulative_badge_progress": kid_data.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
            ),
            "badges_earned": kid_data.get(const.DATA_KID_BADGES_EARNED, {}),
            # v43+: chore_stats deleted, use chore_periods.all_time for totals
            # Cast to dict[str, Any] since chore_periods is a runtime-added bucket
            # All-time uses nested structure: periods["all_time"]["all_time"] = {data}
            "chore_periods_all_time": cast(
                "dict[str, Any]",
                cast("dict[str, Any]", kid_data.get(const.DATA_KID_CHORE_PERIODS, {}))
                .get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
                .get(const.PERIOD_ALL_TIME, {}),
            ),
            "achievement_progress": achievement_progress,
            "challenge_progress": challenge_progress,
            "today_iso": today_iso,
        }

        return context

    # =========================================================================
    # DRY RUN (SHADOW MODE)
    # =========================================================================

    def dry_run_badge(
        self,
        kid_id: str,
        badge_id: str,
    ) -> EvaluationResult | None:
        """Evaluate badge without applying results (for comparison/debugging).

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge internal ID

        Returns:
            EvaluationResult or None if context/badge not found
        """
        context = self._build_evaluation_context(kid_id)
        if not context:
            return None

        badge_data = self.coordinator.badges_data.get(badge_id)
        if not badge_data:
            return None

        # Cast TypedDict to dict for engine
        badge_dict = cast("dict[str, Any]", badge_data)
        return GamificationEngine.evaluate_badge(context, badge_dict)

    def dry_run_achievement(
        self,
        kid_id: str,
        achievement_id: str,
    ) -> EvaluationResult | None:
        """Evaluate achievement without applying results.

        Args:
            kid_id: Kid's internal ID
            achievement_id: Achievement internal ID

        Returns:
            EvaluationResult or None if context/achievement not found
        """
        context = self._build_evaluation_context(kid_id)
        if not context:
            return None

        achievement_data = self.coordinator.achievements_data.get(achievement_id)
        if not achievement_data:
            return None

        # Cast TypedDict to dict for engine
        achievement_dict = cast("dict[str, Any]", achievement_data)
        return GamificationEngine.evaluate_achievement(context, achievement_dict)

    def dry_run_challenge(
        self,
        kid_id: str,
        challenge_id: str,
    ) -> EvaluationResult | None:
        """Evaluate challenge without applying results.

        Args:
            kid_id: Kid's internal ID
            challenge_id: Challenge internal ID

        Returns:
            EvaluationResult or None if context/challenge not found
        """
        context = self._build_evaluation_context(kid_id)
        if not context:
            return None

        challenge_data = self.coordinator.challenges_data.get(challenge_id)
        if not challenge_data:
            return None

        # Cast TypedDict to dict for engine
        challenge_dict = cast("dict[str, Any]", challenge_data)
        return GamificationEngine.evaluate_challenge(context, challenge_dict)

    # =========================================================================
    # BADGE UTILITIES (Pure Helpers - No Side Effects)
    # =========================================================================
    # These methods perform calculations/lookups without modifying state.
    # Migrated from coordinator.py as Tier 1 (no internal dependencies).

    def process_award_items(
        self,
        award_items: list[str],
        rewards_dict: dict[str, Any],
        bonuses_dict: dict[str, Any],
        penalties_dict: dict[str, Any],
    ) -> tuple[dict[str, list[str]], list[str]]:
        """Process award_items and return dicts of items to award or penalize.

        Args:
            award_items: List of award item strings (e.g., "reward:uuid", "bonus:uuid")
            rewards_dict: Dictionary of reward data keyed by reward_id
            bonuses_dict: Dictionary of bonus data keyed by bonus_id
            penalties_dict: Dictionary of penalty data keyed by penalty_id

        Returns:
            Tuple of (to_award dict, to_penalize list)
        """
        to_award: dict[str, list[str]] = {
            const.AWARD_ITEMS_KEY_REWARDS: [],
            const.AWARD_ITEMS_KEY_BONUSES: [],
        }
        to_penalize: list[str] = []
        for item in award_items:
            if item.startswith(const.AWARD_ITEMS_PREFIX_REWARD):
                reward_id = item.split(":", 1)[1]
                if reward_id in rewards_dict:
                    to_award[const.AWARD_ITEMS_KEY_REWARDS].append(reward_id)
            elif item.startswith(const.AWARD_ITEMS_PREFIX_BONUS):
                bonus_id = item.split(":", 1)[1]
                if bonus_id in bonuses_dict:
                    to_award[const.AWARD_ITEMS_KEY_BONUSES].append(bonus_id)
            elif item.startswith(const.AWARD_ITEMS_PREFIX_PENALTY):
                penalty_id = item.split(":", 1)[1]
                if penalty_id in penalties_dict:
                    to_penalize.append(penalty_id)
        return to_award, to_penalize

    def _build_badge_award_manifest(self, badge_data: BadgeData) -> dict[str, Any]:
        """Build Award Manifest from badge data.

        Extracts and processes award items from badge definition into
        a manifest dict ready for SIGNAL_SUFFIX_BADGE_EARNED emission.

        Args:
            badge_data: Badge definition containing awards

        Returns:
            Manifest dict with keys: points, multiplier, reward_ids,
            bonus_ids, penalty_ids
        """
        award_data = badge_data.get(const.DATA_BADGE_AWARDS, {})
        # Extract award items - stored as list of "type:uuid" strings
        award_items = award_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
        to_award, to_penalize = self.process_award_items(
            award_items,
            self.coordinator.rewards_data,
            self.coordinator.bonuses_data,
            self.coordinator.penalties_data,
        )

        return {
            "points": award_data.get(
                const.DATA_BADGE_AWARDS_AWARD_POINTS, const.DEFAULT_ZERO
            ),
            "multiplier": award_data.get(const.DATA_BADGE_AWARDS_POINT_MULTIPLIER),
            "reward_ids": to_award.get(const.AWARD_ITEMS_KEY_REWARDS, []),
            "bonus_ids": to_award.get(const.AWARD_ITEMS_KEY_BONUSES, []),
            "penalty_ids": to_penalize,
        }

    def get_badge_in_scope_chores_list(
        self,
        badge_info: BadgeData,
        kid_id: str,
        kid_assigned_chores: list[str] | None = None,
    ) -> list[str]:
        """Get the list of chore IDs that are in-scope for this badge evaluation.

        For badges with tracked chores:
        - Returns only those specific chore IDs that are also assigned to the kid
        For badges without tracked chores:
        - Returns all chore IDs assigned to the kid

        Args:
            badge_info: Badge configuration dictionary
            kid_id: Kid's internal ID
            kid_assigned_chores: Optional pre-computed list of chores assigned to kid
                                (optimization to avoid re-iterating all chores)

        Returns:
            List of chore IDs in scope for this badge/kid combination
        """
        badge_type = badge_info.get(const.DATA_BADGE_TYPE, const.BADGE_TYPE_PERIODIC)
        include_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES

        # OPTIMIZATION: Use pre-computed list if provided, otherwise compute
        if kid_assigned_chores is None:
            kid_assigned_chores = self._get_kid_assigned_chores(kid_id)

        # If badge does not include tracked chores, return empty list
        if include_tracked_chores:
            tracked_chores = badge_info.get(const.DATA_BADGE_TRACKED_CHORES, {})
            tracked_chore_ids = tracked_chores.get(
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
            )

            if tracked_chore_ids:
                # Badge has specific tracked chores, return only those assigned to the kid
                return [
                    chore_id
                    for chore_id in tracked_chore_ids
                    if chore_id in kid_assigned_chores
                ]
            # Badge considers all chores, return all chores assigned to the kid
            return kid_assigned_chores
        # Badge does not include tracked chores component, return empty list
        return []

    def _get_kid_assigned_chores(self, kid_id: str) -> list[str]:
        """Return all chore IDs currently assigned to the kid."""
        kid_assigned_chores: list[str] = []
        for chore_id, chore_info in self.coordinator.chores_data.items():
            chore_assigned_to = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not chore_assigned_to or kid_id in chore_assigned_to:
                kid_assigned_chores.append(chore_id)
        return kid_assigned_chores

    def get_cumulative_badge_levels(
        self, kid_id: str
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
        float,
        float,
    ]:
        """Determine the highest earned cumulative badge and adjacent tier badges.

        Args:
            kid_id: Kid's internal ID

        Returns:
            Tuple of:
            - highest_earned_badge_info (dict or None)
            - next_higher_badge_info (dict or None)
            - next_lower_badge_info (dict or None)
            - baseline (float) - DEPRECATED, returns 0.0
            - cycle_points (float)
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return None, None, None, 0.0, 0.0

        # Get total earned from point_periods using stats engine
        point_periods = kid_info.get(const.DATA_KID_POINT_PERIODS, {})
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_KID_POINT_PERIODS_ALL_TIME
        }
        total_points_earned = float(
            self.coordinator.stats.get_period_total(
                point_periods,
                const.PERIOD_ALL_TIME,
                const.DATA_KID_POINT_PERIOD_POINTS_EARNED,
                period_key_mapping=period_key_mapping,
            )
        )

        # Get cycle_points for maintenance tracking
        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        cycle_points = round(
            float(
                progress.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS, 0)
            ),
            const.DATA_FLOAT_PRECISION,
        )

        # Get badges this kid has earned (from badges_earned dict)
        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})

        # Get sorted list of cumulative badges (lowest to highest threshold)
        cumulative_badges = sorted(
            (
                (badge_id, badge_info)
                for badge_id, badge_info in self.coordinator.badges_data.items()
                if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE
            ),
            key=lambda item: float(
                item[1]
                .get(const.DATA_BADGE_TARGET, {})
                .get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)
            ),
        )

        if not cumulative_badges:
            # No cumulative badges exist
            return None, None, None, 0.0, cycle_points

        highest_earned: dict[str, Any] | None = None
        next_higher: dict[str, Any] | None = None
        next_lower: dict[str, Any] | None = None
        previous_badge_info: dict[str, Any] | None = None

        for badge_id, badge_info in cumulative_badges:
            threshold = float(
                badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                )
            )

            # Check if badge is assigned to this kid (empty list = assigned to all)
            is_assigned_to = not badge_info.get(
                const.DATA_BADGE_ASSIGNED_TO, []
            ) or kid_id in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])

            if not is_assigned_to:
                continue

            # Badge is earned if it's in badges_earned dict OR total_points >= threshold
            is_earned = badge_id in badges_earned or total_points_earned >= threshold

            if is_earned:
                highest_earned = cast("dict[str, Any]", badge_info)
                next_lower = previous_badge_info
            else:
                # First unearned badge is next_higher
                next_higher = cast("dict[str, Any]", badge_info)
                break

            previous_badge_info = cast("dict[str, Any]", badge_info)

        return (
            highest_earned,
            next_higher,
            next_lower,
            0.0,  # baseline deprecated, return 0
            cycle_points,
        )

    def update_point_multiplier_for_kid(self, kid_id: str) -> None:
        """Update the kid's points multiplier based on current cumulative badge.

        Phase 3A: Use get_cumulative_badge_progress to compute current badge
        (demotion-aware, no storage reads).

        Phase 3B Landlord/Tenant: GamificationManager calculates the multiplier
        but emits a signal for EconomyManager (the Landlord) to perform the write.

        Args:
            kid_id: Kid's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        old_multiplier = float(
            kid_info.get(
                const.DATA_KID_POINTS_MULTIPLIER,
                const.DEFAULT_KID_POINTS_MULTIPLIER,
            )
        )

        # Phase 3A: Get current badge via computed progress (demotion-aware)
        cumulative_badge_progress = self.get_cumulative_badge_progress(kid_id)
        current_badge_id = cumulative_badge_progress.get(
            const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID
        )

        multiplier: float = const.DEFAULT_KID_POINTS_MULTIPLIER

        if current_badge_id:
            badge_data = self.coordinator.badges_data.get(current_badge_id)
            if badge_data:
                badge_awards = badge_data.get(const.DATA_BADGE_AWARDS, {})
                raw_multiplier = badge_awards.get(
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                    const.DEFAULT_KID_POINTS_MULTIPLIER,
                )
                if isinstance(raw_multiplier, (int, float)):
                    multiplier = float(raw_multiplier)

        # Phase 3B: Emit signal for EconomyManager (Landlord) to write
        self.emit(
            const.SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED,
            kid_id=kid_id,
            multiplier=multiplier,
            old_multiplier=old_multiplier,
            new_multiplier=multiplier,
            reference_id=current_badge_id,
        )

    # =========================================================================
    # BADGE CORE OPERATIONS (State-Modifying Methods)
    # =========================================================================
    # These methods award/demote/remove badges and modify kid/badge state.
    # Migrated from coordinator.py as Tier 2/3 (depend on utilities above).

    def update_badges_earned_for_kid(self, kid_id: str, badge_id: str) -> None:
        """Update the kid's badges-earned tracking for the given badge.

        Updates period stats (daily, weekly, etc.) for badge award tracking.

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error(
                "ERROR: Update Kid Badges Earned - Kid ID '%s' not found", kid_id
            )
            return

        badge_info = self.coordinator.badges_data.get(badge_id)
        if not badge_info:
            const.LOGGER.error(
                "ERROR: Update Kid Badges Earned - Badge ID '%s' not found", badge_id
            )
            return

        today_local_iso = dt_today_iso()

        badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})

        # Phase 4: GamificationManager (Landlord) creates/updates structure only
        # StatisticsManager (Tenant) handles period updates via _on_badge_earned listener

        if badge_id not in badges_earned:
            # Create new badge tracking entry with empty periods (Landlord creates structure only)
            # StatisticsEngine creates daily/weekly/monthly/yearly keys on-demand
            # Top-level award_count is manager-owned for periodic re-awards.
            # Tenant-owned period aggregates remain in periods buckets.
            badges_earned[badge_id] = {  # pyright: ignore[reportArgumentType]
                const.DATA_KID_BADGES_EARNED_NAME: badge_info.get(
                    const.DATA_BADGE_NAME, ""
                ),
                const.DATA_KID_BADGES_EARNED_LAST_AWARDED: today_local_iso,
                const.DATA_KID_BADGES_EARNED_PERIODS: {},  # Tenant populates sub-keys
            }
            const.LOGGER.info(
                "Update Kid Badges Earned - Created new tracking for badge '%s' for kid '%s'",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )
        else:
            # Update existing badge tracking (Landlord updates metadata fields only)
            # award_count increment for periodic re-award is manager-owned.
            # Tenant-owned period aggregates are still handled in periods buckets.
            tracking_entry = badges_earned[badge_id]
            tracking_entry[const.DATA_KID_BADGES_EARNED_NAME] = badge_info.get(
                const.DATA_BADGE_NAME, ""
            )
            tracking_entry[const.DATA_KID_BADGES_EARNED_LAST_AWARDED] = today_local_iso

            # Ensure periods structure exists (Landlord ensures container)
            # StatisticsEngine creates daily/weekly/monthly/yearly keys on-demand
            tracking_entry.setdefault(
                const.DATA_KID_BADGES_EARNED_PERIODS,
                {},  # type: ignore[typeddict-item]  # Tenant populates sub-keys
            )

            const.LOGGER.info(
                "Update Kid Badges Earned - Updated tracking for badge '%s' for kid '%s'",
                badge_info.get(const.DATA_BADGE_NAME, badge_id),
                kid_info.get(const.DATA_KID_NAME, kid_id),
            )

        # Phase 4: Periods updated by StatisticsManager._on_badge_earned listener
        # No direct StatisticsEngine calls - clean Landlord/Tenant separation

    def _ensure_kid_badge_structures(self, kid_id: str, badge_id: str) -> None:
        """Ensure badge periods structure exists (Landlord responsibility).

        Creates ONLY the empty periods dict. StatisticsManager (Tenant) populates
        everything inside via StatisticsEngine.record_transaction which creates
        period type keys (daily/weekly/etc.) on-demand.

        Follows the Landlord-Tenant pattern used by ChoreManager and RewardManager:
        - Landlord (GamificationManager): Creates empty periods: {} container
        - Tenant (StatisticsManager): Populates ALL sub-keys via record_transaction

        This prevents the race condition where:
        1. Badge entry created with periods: {}
        2. BADGE_EARNED signal emitted
        3. StatisticsManager._on_badge_earned finds periods structure ready

        Pattern matches:
        - ChoreManager._ensure_kid_structures() - creates empty periods: {}
        - RewardManager._ensure_kid_structures() - creates empty periods: {}

        Args:
            kid_id: Kid's internal ID
            badge_id: Badge's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
        badge_entry = badges_earned.get(badge_id)
        if not badge_entry:
            const.LOGGER.warning(
                "_ensure_kid_badge_structures: Badge entry not found for kid=%s, badge=%s",
                kid_id,
                badge_id,
            )
            return

        # Cast to mutable dict for dynamic period structure creation
        badge_entry_dict = cast("dict[str, Any]", badge_entry)

        # Landlord creates ONLY empty periods container
        # Tenant (StatisticsEngine.record_transaction) creates ALL sub-keys on-demand
        if const.DATA_KID_BADGES_EARNED_PERIODS not in badge_entry_dict:
            badge_entry_dict[const.DATA_KID_BADGES_EARNED_PERIODS] = {}

        const.LOGGER.debug(
            "_ensure_kid_badge_structures: Ensured periods container for kid=%s, badge=%s",
            kid_id,
            badge_id,
        )

        self.coordinator._persist_and_update()

    def update_chore_badge_references_for_kid(
        self, include_cumulative_badges: bool = False
    ) -> None:
        """Update badge reference lists in kid chore data.

        Legacy helper retained for diagnostics and migration parity.

        Runtime badge evaluation resolves scope dynamically from badge definitions,
        so startup no longer materializes `badge_refs` snapshots.

        Args:
            include_cumulative_badges: Include cumulative badges in references.
                Default False since cumulative badges are points-only.
        """
        # Clear existing badge references
        for _kid_id, kid_info in self.coordinator.kids_data.items():
            if const.DATA_KID_CHORE_DATA not in kid_info:
                continue

            for chore_data in kid_info[const.DATA_KID_CHORE_DATA].values():
                chore_data[const.DATA_KID_CHORE_DATA_BADGE_REFS] = []

        # Add badge references to relevant chores
        for badge_id, badge_info in self.coordinator.badges_data.items():
            # Skip cumulative badges if not explicitly included
            if (
                not include_cumulative_badges
                and badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE
            ):
                continue

            # For each kid this badge is assigned to
            assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            for kid_id in (
                assigned_to or self.coordinator.kids_data.keys()
            ):  # If empty, apply to all kids
                kid_info_loop = self.coordinator.kids_data.get(kid_id)
                if not kid_info_loop or const.DATA_KID_CHORE_DATA not in kid_info_loop:
                    continue

                # Use the helper function to get the correct in-scope chores
                in_scope_chores_list = self.get_badge_in_scope_chores_list(
                    badge_info, kid_id
                )

                # Add badge reference to each tracked chore
                for chore_id in in_scope_chores_list:
                    if chore_id in kid_info_loop[const.DATA_KID_CHORE_DATA]:
                        chore_entry = kid_info_loop[const.DATA_KID_CHORE_DATA][chore_id]
                        badge_refs: list[str] = chore_entry.get(
                            const.DATA_KID_CHORE_DATA_BADGE_REFS, []
                        )
                        if badge_id not in badge_refs:
                            badge_refs.append(badge_id)
                            chore_entry[const.DATA_KID_CHORE_DATA_BADGE_REFS] = (
                                badge_refs
                            )

    def get_cumulative_badge_progress(self, kid_id: str) -> dict[str, Any]:
        """Build and return the full cumulative badge progress block for a kid.

        Phase 3A: Returns dict with CUMULATIVE_BADGE_PROGRESS_* constant keys.
        All derived fields computed on-read, only state fields read from storage.

        Uses badge level logic, progress tracking, and next-tier metadata.
        Does not mutate state.

        Args:
            kid_id: Kid's internal ID

        Returns:
            Dictionary with cumulative badge progress data (state + computed fields)
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return {}

        # Get stored state fields (only 4 fields remain in storage)
        stored_progress = kid_info.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        ).copy()

        # Compute values from badge level logic
        (highest_earned, next_higher, next_lower, _, cycle_points) = (
            self.get_cumulative_badge_levels(kid_id)
        )

        # Get kid's total points from point_periods using stats engine
        point_periods = kid_info.get(const.DATA_KID_POINT_PERIODS, {})
        period_key_mapping = {
            const.PERIOD_ALL_TIME: const.DATA_KID_POINT_PERIODS_ALL_TIME
        }
        total_points = float(
            self.coordinator.stats.get_period_total(
                point_periods,
                const.PERIOD_ALL_TIME,
                const.DATA_KID_POINT_PERIOD_POINTS_EARNED,
                period_key_mapping=period_key_mapping,
            )
        )

        # Check if highest earned badge has a reset schedule (maintenance cycle)
        # If no reset schedule → no maintenance, no demotion, cycle_points = 0
        has_reset_schedule = False
        if highest_earned:
            reset_schedule = highest_earned.get(const.DATA_BADGE_RESET_SCHEDULE, {})
            recurring_frequency = reset_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                const.FREQUENCY_NONE,
            )
            has_reset_schedule = recurring_frequency != const.FREQUENCY_NONE

        # Determine status and current badge based on reset schedule
        if not has_reset_schedule:
            # No reset schedule → no maintenance cycle
            # Status is always active, cycle_points is 0, current badge = highest earned
            current_status = const.CUMULATIVE_BADGE_STATE_ACTIVE
            cycle_points = 0.0
            current_badge_info = highest_earned
        else:
            # Has reset schedule → use stored status and cycle_points
            current_status = stored_progress.get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
                const.CUMULATIVE_BADGE_STATE_ACTIVE,
            )
            if current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED:
                current_badge_info = next_lower
            else:
                current_badge_info = highest_earned

        # Phase 3A: Use CUMULATIVE_BADGE_PROGRESS_* constants for dict keys
        computed_progress = {
            # State fields (corrected based on reset schedule check)
            const.CUMULATIVE_BADGE_PROGRESS_STATUS: current_status,
            const.CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: cycle_points,
            # Derived fields (computed only, not stored)
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                highest_earned.get(const.DATA_BADGE_INTERNAL_ID)
                if highest_earned
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME: (
                highest_earned.get(const.DATA_BADGE_NAME) if highest_earned else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD: (
                float(
                    highest_earned.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if highest_earned
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: (
                current_badge_info.get(const.DATA_BADGE_INTERNAL_ID)
                if current_badge_info
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: (
                current_badge_info.get(const.DATA_BADGE_NAME)
                if current_badge_info
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD: (
                float(
                    current_badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if current_badge_info
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID: (
                next_higher.get(const.DATA_BADGE_INTERNAL_ID) if next_higher else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME: (
                next_higher.get(const.DATA_BADGE_NAME) if next_higher else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_THRESHOLD: (
                float(
                    next_higher.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )
                )
                if next_higher
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED: (
                max(
                    0.0,
                    float(
                        next_higher.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                    - total_points,
                )
                if next_higher
                else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID: (
                next_lower.get(const.DATA_BADGE_INTERNAL_ID) if next_lower else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME: (
                next_lower.get(const.DATA_BADGE_NAME) if next_lower else None
            ),
            const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_THRESHOLD: (
                float(next_lower.get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0))
                if next_lower
                else None
            ),
        }

        # Merge computed values over stored progress
        stored_progress.update(computed_progress)  # type: ignore[typeddict-item]

        return cast("dict[str, Any]", stored_progress)

    def demote_cumulative_badge(self, kid_id: str) -> None:
        """Update cumulative badge status to DEMOTED when maintenance fails.

        Called when a cumulative badge's maintenance requirements are no longer met.
        The badge is not removed, but the kid's status is set to DEMOTED which
        affects their multiplier.

        Args:
            kid_id: Kid's internal ID
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error(
                "Demote Cumulative Badge - Kid ID '%s' not found", kid_id
            )
            return

        progress = kid_info.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS)
        if not progress:
            const.LOGGER.debug(
                "Demote Cumulative Badge - No cumulative badge progress for kid '%s'",
                kid_id,
            )
            return

        # Only update if not already demoted
        current_status = progress.get(
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
            const.CUMULATIVE_BADGE_STATE_ACTIVE,
        )
        if current_status != const.CUMULATIVE_BADGE_STATE_DEMOTED:
            progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
                const.CUMULATIVE_BADGE_STATE_DEMOTED
            )

            # Recalculate multiplier immediately so the penalty takes effect
            self.update_point_multiplier_for_kid(kid_id)

            self.coordinator._persist_and_update()

            kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)
            const.LOGGER.info(
                "Demoted cumulative badge status for kid '%s' (%s)",
                kid_name,
                kid_id,
            )

    def _calculate_maintenance_dates(
        self, badge_data: BadgeData
    ) -> tuple[str | None, str | None]:
        """Calculate next maintenance end date and grace end date for a badge.

        Uses the badge's reset_schedule to compute the next maintenance window
        from today. Called at award time (first-time, re-promotion, maintenance
        renewal) so dates are set in real-time, not deferred to midnight.

        Args:
            badge_data: Badge configuration dict with reset_schedule.

        Returns:
            Tuple of (maintenance_end_date, maintenance_grace_end_date) as
            ISO date strings, or (None, None) if schedule is not configured.
        """
        reset_schedule = badge_data.get(const.DATA_BADGE_RESET_SCHEDULE, {})
        recurring_frequency = reset_schedule.get(
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
            const.FREQUENCY_NONE,
        )

        if recurring_frequency == const.FREQUENCY_NONE:
            return (None, None)

        today_iso = dt_today_iso()
        next_end_date: str | None = None

        if recurring_frequency == const.FREQUENCY_CUSTOM:
            custom_interval = reset_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
            )
            custom_unit = reset_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
            )
            if custom_interval and custom_unit:
                result = dt_add_interval(
                    today_iso,
                    interval_unit=custom_unit,
                    delta=int(custom_interval),
                    require_future=True,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                next_end_date = str(result) if result else None
        else:
            result = dt_next_schedule(
                today_iso,
                interval_type=recurring_frequency,
                require_future=True,
                return_type=const.HELPER_RETURN_ISO_DATE,
            )
            next_end_date = str(result) if result else None

        # Calculate grace end date from the maintenance end date.
        # When grace_days == 0, grace_end == end_date (no grace window).
        next_grace_end_date: str | None = None
        grace_days = int(
            reset_schedule.get(const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS, 0)
        )
        if next_end_date:
            if grace_days > 0:
                grace_result = dt_add_interval(
                    next_end_date,
                    interval_unit=const.TIME_UNIT_DAYS,
                    delta=grace_days,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                next_grace_end_date = (
                    str(grace_result) if grace_result else next_end_date
                )
            else:
                # No grace period — grace end matches maintenance end
                next_grace_end_date = next_end_date

        return (next_end_date, next_grace_end_date)

    def remove_awarded_badges(
        self, kid_name: str | None = None, badge_name: str | None = None
    ) -> None:
        """Remove awarded badges based on provided kid_name and badge_name.

        This is the public API that accepts names and converts to IDs.

        Args:
            kid_name: Kid's display name (optional)
            badge_name: Badge's display name (optional)
        """
        # Convert kid_name to kid_id if provided
        kid_id: str | None = None
        if kid_name:
            kid_id = get_item_id_by_name(
                self.coordinator, const.ENTITY_TYPE_KID, kid_name
            )
            if kid_id is None:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid name '%s' not found", kid_name
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_name,
                    },
                )

        # If badge_name is provided, try to find its corresponding badge_id
        badge_id: str | None = None
        if badge_name:
            badge_id = get_item_id_by_name(
                self.coordinator, const.ENTITY_TYPE_BADGE, badge_name
            )
            if not badge_id:
                # Badge isn't found, may have been deleted - clean up kid data only
                const.LOGGER.warning(
                    "Remove Awarded Badges - Badge name '%s' not found in badges_data. "
                    "Removing from kid data only",
                    badge_name,
                )
                # Remove badge name from specific kid or all kids
                if kid_id:
                    kid_info = self.coordinator.kids_data.get(kid_id)
                    if kid_info:
                        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
                        to_remove = [
                            bid
                            for bid, entry in badges_earned.items()
                            if entry.get(const.DATA_KID_BADGES_EARNED_NAME)
                            == badge_name
                        ]
                        for bid in to_remove:
                            del badges_earned[bid]
                else:
                    for kid_info in self.coordinator.kids_data.values():
                        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
                        to_remove = [
                            bid
                            for bid, entry in badges_earned.items()
                            if entry.get(const.DATA_KID_BADGES_EARNED_NAME)
                            == badge_name
                        ]
                        for bid in to_remove:
                            del badges_earned[bid]

                self.coordinator._persist_and_update()
                return

        self.remove_awarded_badges_by_id(kid_id, badge_id)

    def remove_awarded_badges_by_id(
        self, kid_id: str | None = None, badge_id: str | None = None
    ) -> None:
        """Remove awarded badges based on provided kid_id and badge_id.

        This is the internal method that operates on IDs directly.

        Args:
            kid_id: Kid's internal ID (optional)
            badge_id: Badge's internal ID (optional)
        """
        const.LOGGER.info("Remove Awarded Badges - Starting removal process")
        found = False

        if badge_id and kid_id:
            # Reset a specific badge for a specific kid
            kid_info = self.coordinator.kids_data.get(kid_id)
            badge_info = self.coordinator.badges_data.get(badge_id)
            if not kid_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            if not badge_info:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Badge ID '%s' not found", badge_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_BADGE,
                        "name": badge_id,
                    },
                )
            badge_name = badge_info.get(const.DATA_BADGE_NAME, badge_id)
            kid_name_str = kid_info.get(const.DATA_KID_NAME, kid_id)
            badge_type = badge_info.get(const.DATA_BADGE_TYPE)

            # Remove the badge from the kid's badges_earned
            badges_earned = kid_info.setdefault(const.DATA_KID_BADGES_EARNED, {})
            if badge_id in badges_earned:
                found = True
                const.LOGGER.warning(
                    "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                    badge_name,
                    kid_name_str,
                )
                del badges_earned[badge_id]

            # Remove the kid from the badge earned_by list
            earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
            if kid_id in earned_by_list:
                earned_by_list.remove(kid_id)

            # Update multiplier if cumulative badge was removed
            if found and badge_type == const.BADGE_TYPE_CUMULATIVE:
                self.update_point_multiplier_for_kid(kid_id)

            if not found:
                const.LOGGER.warning(
                    "Remove Awarded Badges - Badge '%s' ('%s') not found in kid '%s' ('%s') data",
                    badge_id,
                    badge_name,
                    kid_id,
                    kid_name_str,
                )

        elif badge_id:
            # Remove a specific awarded badge for all kids
            badge_info_elif = self.coordinator.badges_data.get(badge_id)
            if not badge_info_elif:
                const.LOGGER.warning(
                    "Remove Awarded Badges - Badge ID '%s' not found in badges data",
                    badge_id,
                )
            else:
                badge_name = badge_info_elif.get(const.DATA_BADGE_NAME, badge_id)
                badge_type = badge_info_elif.get(const.DATA_BADGE_TYPE)
                kids_affected: list[str] = []
                for loop_kid_id, kid_info in self.coordinator.kids_data.items():
                    kid_name_str = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
                    badges_earned = kid_info.setdefault(
                        const.DATA_KID_BADGES_EARNED, {}
                    )
                    if badge_id in badges_earned:
                        found = True
                        kids_affected.append(loop_kid_id)
                        const.LOGGER.warning(
                            "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                            badge_name,
                            kid_name_str,
                        )
                        del badges_earned[badge_id]

                    # Remove the kid from the badge earned_by list
                    earned_by_list = badge_info_elif.get(const.DATA_BADGE_EARNED_BY, [])
                    if loop_kid_id in earned_by_list:
                        earned_by_list.remove(loop_kid_id)

                # Update multiplier for all affected kids if cumulative badge
                if badge_type == const.BADGE_TYPE_CUMULATIVE:
                    for affected_kid_id in kids_affected:
                        self.update_point_multiplier_for_kid(affected_kid_id)

                # Clear orphan earned_by references
                if const.DATA_BADGE_EARNED_BY in badge_info_elif:
                    badge_info_elif[const.DATA_BADGE_EARNED_BY].clear()

                if not found:
                    const.LOGGER.warning(
                        "Remove Awarded Badges - Badge '%s' ('%s') not found in any kid's data",
                        badge_id,
                        badge_name,
                    )

        elif kid_id:
            # Remove all awarded badges for a specific kid
            kid_info_elif = self.coordinator.kids_data.get(kid_id)
            if not kid_info_elif:
                const.LOGGER.error(
                    "ERROR: Remove Awarded Badges - Kid ID '%s' not found", kid_id
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                    translation_placeholders={
                        "entity_type": const.LABEL_KID,
                        "name": kid_id,
                    },
                )
            kid_name_str = kid_info_elif.get(const.DATA_KID_NAME, "Unknown Kid")
            had_cumulative = False
            for loop_badge_id, badge_info in self.coordinator.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME, "")
                badge_type = badge_info.get(const.DATA_BADGE_TYPE)
                earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                badges_earned = kid_info_elif.setdefault(
                    const.DATA_KID_BADGES_EARNED, {}
                )
                if kid_id in earned_by_list:
                    found = True
                    if badge_type == const.BADGE_TYPE_CUMULATIVE:
                        had_cumulative = True
                    earned_by_list.remove(kid_id)
                    if loop_badge_id in badges_earned:
                        const.LOGGER.warning(
                            "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                            badge_name,
                            kid_name_str,
                        )
                        del badges_earned[loop_badge_id]

            # Clear orphan badges_earned
            if const.DATA_KID_BADGES_EARNED in kid_info_elif:
                kid_info_elif[const.DATA_KID_BADGES_EARNED].clear()

            # Update multiplier if any cumulative badges were removed
            if had_cumulative:
                self.update_point_multiplier_for_kid(kid_id)

            if not found:
                const.LOGGER.warning(
                    "Remove Awarded Badges - No badge found for kid '%s'",
                    kid_info_elif.get(const.DATA_KID_NAME, kid_id),
                )

        else:
            # Remove all awarded badges for all kids
            const.LOGGER.info(
                "Remove Awarded Badges - Removing all awarded badges for all kids"
            )
            kids_with_cumulative: set[str] = set()
            for loop_badge_id, badge_info in self.coordinator.badges_data.items():
                badge_name = badge_info.get(const.DATA_BADGE_NAME, "")
                badge_type = badge_info.get(const.DATA_BADGE_TYPE)
                for loop_kid_id, kid_info in self.coordinator.kids_data.items():
                    kid_name_str = kid_info.get(const.DATA_KID_NAME, "Unknown Kid")
                    badges_earned = kid_info.setdefault(
                        const.DATA_KID_BADGES_EARNED, {}
                    )
                    if loop_badge_id in badges_earned:
                        found = True
                        if badge_type == const.BADGE_TYPE_CUMULATIVE:
                            kids_with_cumulative.add(loop_kid_id)
                        const.LOGGER.warning(
                            "Remove Awarded Badges - Removing badge '%s' from kid '%s'",
                            badge_name,
                            kid_name_str,
                        )
                        del badges_earned[loop_badge_id]

                    # Remove the kid from the badge earned_by list
                    earned_by_list = badge_info.get(const.DATA_BADGE_EARNED_BY, [])
                    if loop_kid_id in earned_by_list:
                        earned_by_list.remove(loop_kid_id)

                    # Clear orphan badges_earned
                    if const.DATA_KID_BADGES_EARNED in kid_info:
                        kid_info[const.DATA_KID_BADGES_EARNED].clear()

                # Clear orphan earned_by references
                if const.DATA_BADGE_EARNED_BY in badge_info:
                    badge_info[const.DATA_BADGE_EARNED_BY].clear()

            # Update multiplier for all kids who had cumulative badges removed
            for affected_kid_id in kids_with_cumulative:
                self.update_point_multiplier_for_kid(affected_kid_id)

            if not found:
                const.LOGGER.warning(
                    "Remove Awarded Badges - No awarded badges found in any kid's data"
                )

        const.LOGGER.info("Remove Awarded Badges - Badge removal process completed")
        self.coordinator._persist_and_update()

    # =========================================================================
    # BADGE AWARDING AND PROGRESS SYNC (State-Modifying Methods)
    # =========================================================================

    async def _record_badge_earned(
        self, kid_id: str, badge_id: str, badge_data: BadgeData
    ) -> None:
        """Record that a kid earned a badge (GamificationManager's domain only).

        Phase 7 Signal-First Logic: This method ONLY updates badge tracking data.
        All award processing (points, multiplier, rewards, bonuses, penalties)
        is handled by domain experts via BADGE_EARNED signal:
        - EconomyManager: points, multiplier, bonuses, penalties
        - RewardManager: reward grants

        Args:
            kid_id: The kid's internal UUID
            badge_id: The badge's internal UUID
            badge_data: Badge definition
        """
        kid_info = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error("_record_badge_earned: Kid ID '%s' not found", kid_id)
            return

        badge_name = badge_data.get(const.DATA_BADGE_NAME, badge_id)
        kid_name = kid_info.get(const.DATA_KID_NAME, kid_id)

        # Update badge's earned_by list
        earned_by_list = badge_data.setdefault(const.DATA_BADGE_EARNED_BY, [])
        if kid_id not in earned_by_list:
            earned_by_list.append(kid_id)

        # Update kid's badges_earned dict (Landlord creates structure)
        self.update_badges_earned_for_kid(kid_id, badge_id)

        # Phase 4: Ensure badge periods structure exists before emitting signal
        # This ensures StatisticsManager (Tenant) has structure ready when signal fires
        self._ensure_kid_badge_structures(kid_id, badge_id)

        const.LOGGER.info(
            "Badge recorded: '%s' earned by kid '%s'",
            badge_name,
            kid_name,
        )

        # Persist badge tracking data
        self.coordinator._persist_and_update()

    async def award_badge(self, kid_id: str, badge_id: str) -> None:
        """Award a badge to a kid (public API, emits full manifest).

        This is the public method for manually awarding badges (e.g., special occasion).
        It delegates to _record_badge_earned for tracking and emits the Award Manifest
        so domain experts handle their items:
        - EconomyManager: points, multiplier, bonuses, penalties
        - RewardManager: reward grants (free)

        For automatic badge evaluation, use _evaluate_badge_for_kid instead.

        Args:
            kid_id: The kid's internal UUID
            badge_id: The badge's internal UUID
        """
        badge_info: BadgeData | None = self.coordinator.badges_data.get(badge_id)
        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.error("award_badge: Kid ID '%s' not found", kid_id)
            return
        if not badge_info:
            const.LOGGER.error(
                "award_badge: Badge ID '%s' not found",
                badge_id,
            )
            return

        # Record badge in GamificationManager's domain
        await self._record_badge_earned(kid_id, badge_id, badge_info)

        # Build and emit Award Manifest for domain experts
        award_data = badge_info.get(const.DATA_BADGE_AWARDS, {})
        award_items = award_data.get(const.DATA_BADGE_AWARDS_AWARD_ITEMS, [])
        to_award, to_penalize = self.process_award_items(
            award_items,
            self.coordinator.rewards_data,
            self.coordinator.bonuses_data,
            self.coordinator.penalties_data,
        )

        # Emit the Award Manifest
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_EARNED,
            kid_id=kid_id,
            badge_id=badge_id,
            badge_name=badge_info.get(const.DATA_BADGE_NAME, "Unknown"),
            points=award_data.get(
                const.DATA_BADGE_AWARDS_AWARD_POINTS, const.DEFAULT_ZERO
            ),
            multiplier=award_data.get(const.DATA_BADGE_AWARDS_POINT_MULTIPLIER),
            reward_ids=to_award.get(const.AWARD_ITEMS_KEY_REWARDS, []),
            bonus_ids=to_award.get(const.AWARD_ITEMS_KEY_BONUSES, []),
            penalty_ids=to_penalize,
        )

    def sync_badge_progress_for_kid(self, kid_id: str) -> None:
        """Sync badge progress for a specific kid.

        Initializes badge progress for new badges and updates existing progress
        for configuration changes. Handles all non-cumulative badge types.

        This method does NOT persist - caller is responsible for persistence.

        Args:
            kid_id: The kid's internal UUID
        """
        kid_info: KidData | None = self.coordinator.kids_data.get(kid_id)
        if not kid_info:
            return

        # Phase 4: Clean up badge_progress for badges no longer assigned to this kid
        if const.DATA_KID_BADGE_PROGRESS in kid_info:
            badges_to_remove = []
            for progress_badge_id in kid_info[const.DATA_KID_BADGE_PROGRESS]:
                badge_info: BadgeData | None = self.coordinator.badges_data.get(
                    progress_badge_id
                )
                # Remove if badge deleted OR kid not in assigned_to list
                if not badge_info or kid_id not in badge_info.get(
                    const.DATA_BADGE_ASSIGNED_TO, []
                ):
                    badges_to_remove.append(progress_badge_id)

            for badge_id in badges_to_remove:
                del kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id]
                const.LOGGER.debug(
                    "DEBUG: Removed badge_progress for badge '%s' from kid '%s' "
                    "(unassigned or deleted)",
                    badge_id,
                    kid_info.get(const.DATA_KID_NAME, kid_id),
                )

        for badge_id, badge_info in self.coordinator.badges_data.items():
            # Feature Change v4.2: Badges now require explicit assignment.
            # Empty assigned_to means badge is not assigned to any kid.
            assigned_to_list = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
            is_assigned_to = kid_id in assigned_to_list
            if not is_assigned_to:
                continue

            # Skip cumulative badges (handled separately)
            if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE:
                continue

            # Initialize progress structure if it doesn't exist
            if const.DATA_KID_BADGE_PROGRESS not in kid_info:
                kid_info[const.DATA_KID_BADGE_PROGRESS] = {}

            badge_type = badge_info.get(const.DATA_BADGE_TYPE)

            # --- Set flags based on badge type ---
            has_target = badge_type in const.INCLUDE_TARGET_BADGE_TYPES
            has_special_occasion = (
                badge_type in const.INCLUDE_SPECIAL_OCCASION_BADGE_TYPES
            )
            has_achievement_linked = (
                badge_type in const.INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES
            )
            has_challenge_linked = (
                badge_type in const.INCLUDE_CHALLENGE_LINKED_BADGE_TYPES
            )
            has_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES
            has_assigned_to = badge_type in const.INCLUDE_ASSIGNED_TO_BADGE_TYPES
            has_reset_schedule = badge_type in const.INCLUDE_RESET_SCHEDULE_BADGE_TYPES

            # ===============================================================
            # SECTION 1: NEW BADGE SETUP - Create initial progress structure
            # ===============================================================
            badge_progress_dict = kid_info.get(const.DATA_KID_BADGE_PROGRESS, {})
            if badge_id not in badge_progress_dict:
                # --- Common fields ---
                progress: dict[str, Any] = {
                    const.DATA_KID_BADGE_PROGRESS_NAME: badge_info.get(
                        const.DATA_BADGE_NAME
                    ),
                    const.DATA_KID_BADGE_PROGRESS_TYPE: badge_type,
                    const.DATA_KID_BADGE_PROGRESS_STATUS: const.BADGE_STATE_IN_PROGRESS,
                }

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE
                    )
                    threshold_value = float(
                        badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = target_type
                    progress[const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE] = (
                        threshold_value
                    )

                    # Initialize all possible progress fields to their defaults
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_POINTS_CYCLE_COUNT, 0.0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_CHORES_CYCLE_COUNT, 0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_CHORES_COMPLETED, {}
                    )
                    progress.setdefault(
                        const.DATA_KID_BADGE_PROGRESS_DAYS_COMPLETED, {}
                    )

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = challenge_id

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    tracked_chores_cfg = badge_info.get(
                        const.DATA_BADGE_TRACKED_CHORES, {}
                    )
                    selected_chores = tracked_chores_cfg.get(
                        const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = list(
                        selected_chores
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress[const.DATA_BADGE_ASSIGNED_TO] = assigned_to

                # --- Reset Schedule fields ---
                if has_reset_schedule:
                    reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
                    recurring_frequency = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        const.FREQUENCY_NONE,
                    )
                    start_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_START_DATE
                    )
                    end_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                    )
                    progress[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )

                    # Set initial schedule if there is a frequency and no end date
                    if recurring_frequency != const.FREQUENCY_NONE:
                        if end_date_iso:
                            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                                start_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                                end_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                                const.DEFAULT_ZERO
                            )
                        else:
                            # Calculate initial end date from today
                            today_local_iso = dt_today_iso()
                            is_daily = recurring_frequency == const.FREQUENCY_DAILY
                            is_custom_1_day = (
                                recurring_frequency == const.FREQUENCY_CUSTOM
                                and reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                                )
                                == 1
                                and reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                                )
                                == const.TIME_UNIT_DAYS
                            )

                            if is_daily or is_custom_1_day:
                                # Special case: daily badge uses today as end date
                                new_end_date_iso: str | date | None = today_local_iso
                            elif recurring_frequency == const.FREQUENCY_CUSTOM:
                                # Handle other custom frequencies
                                custom_interval = reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                                )
                                custom_interval_unit = reset_schedule.get(
                                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                                )
                                if custom_interval and custom_interval_unit:
                                    new_end_date_iso = dt_add_interval(
                                        today_local_iso,
                                        interval_unit=custom_interval_unit,
                                        delta=custom_interval,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                                else:
                                    # Default fallback to weekly
                                    new_end_date_iso = dt_add_interval(
                                        today_local_iso,
                                        interval_unit=const.TIME_UNIT_WEEKS,
                                        delta=1,
                                        require_future=True,
                                        return_type=const.HELPER_RETURN_ISO_DATE,
                                    )
                            else:
                                # Use standard frequency helper
                                new_end_date_iso = dt_next_schedule(
                                    today_local_iso,
                                    interval_type=recurring_frequency,
                                    require_future=True,
                                    return_type=const.HELPER_RETURN_ISO_DATE,
                                )

                            progress[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                                start_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                                new_end_date_iso
                            )
                            progress[const.DATA_KID_BADGE_PROGRESS_CYCLE_COUNT] = (
                                const.DEFAULT_ZERO
                            )

                            # Set penalty applied to False
                            progress[const.DATA_KID_BADGE_PROGRESS_PENALTY_APPLIED] = (
                                False
                            )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # Store the progress data
                kid_info[const.DATA_KID_BADGE_PROGRESS][badge_id] = cast(  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    "KidBadgeProgress", progress
                )

            # ===============================================================
            # SECTION 2: BADGE SYNC - Update existing badge progress data
            # ===============================================================
            else:
                # Remove badge progress if badge no longer available or not assigned
                if badge_id not in self.coordinator.badges_data or (
                    badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    and kid_id not in badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                ):
                    if badge_id in badge_progress_dict:
                        del badge_progress_dict[badge_id]
                        const.LOGGER.info(
                            "INFO: Badge Maintenance - Removed badge progress for "
                            "badge '%s' from kid '%s' (badge deleted or unassigned).",
                            badge_id,
                            kid_info.get(const.DATA_KID_NAME, kid_id),
                        )
                    continue

                # The badge already exists in progress data - sync configuration fields
                progress_sync: dict[str, Any] = cast(
                    "dict[str, Any]", badge_progress_dict[badge_id]
                )

                # --- Common fields ---
                progress_sync[const.DATA_KID_BADGE_PROGRESS_NAME] = badge_info.get(
                    const.DATA_BADGE_NAME, "Unknown Badge"
                )
                progress_sync[const.DATA_KID_BADGE_PROGRESS_TYPE] = badge_type

                # --- Target fields ---
                if has_target:
                    target_type = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_TYPE,
                        const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                    )
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_TARGET_TYPE] = (
                        target_type
                    )

                    progress_sync[
                        const.DATA_KID_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE
                    ] = badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                    )

                # --- Special Occasion fields ---
                if has_special_occasion:
                    occasion_type = badge_info.get(const.DATA_BADGE_OCCASION_TYPE)
                    if occasion_type:
                        progress_sync[const.DATA_BADGE_OCCASION_TYPE] = occasion_type

                # --- Achievement Linked fields ---
                if has_achievement_linked:
                    achievement_id = badge_info.get(
                        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                    )
                    if achievement_id:
                        progress_sync[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = (
                            achievement_id
                        )

                # --- Challenge Linked fields ---
                if has_challenge_linked:
                    challenge_id = badge_info.get(const.DATA_BADGE_ASSOCIATED_CHALLENGE)
                    if challenge_id:
                        progress_sync[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = (
                            challenge_id
                        )

                # --- Tracked Chores fields ---
                if has_tracked_chores and not has_special_occasion:
                    tracked_chores_cfg = badge_info.get(
                        const.DATA_BADGE_TRACKED_CHORES, {}
                    )
                    selected_chores = tracked_chores_cfg.get(
                        const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
                    )
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_TRACKED_CHORES] = list(
                        selected_chores
                    )

                # --- Assigned To fields ---
                if has_assigned_to:
                    assigned_to = badge_info.get(const.DATA_BADGE_ASSIGNED_TO, [])
                    progress_sync[const.DATA_BADGE_ASSIGNED_TO] = assigned_to

                # --- Reset Schedule fields ---
                if has_reset_schedule:
                    reset_schedule = badge_info.get(const.DATA_BADGE_RESET_SCHEDULE, {})
                    recurring_frequency = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        const.FREQUENCY_NONE,
                    )
                    start_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_START_DATE
                    )
                    end_date_iso = reset_schedule.get(
                        const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                    )
                    progress_sync[const.DATA_KID_BADGE_PROGRESS_RECURRING_FREQUENCY] = (
                        recurring_frequency
                    )
                    # Only update start and end dates if they have values
                    if start_date_iso:
                        progress_sync[const.DATA_KID_BADGE_PROGRESS_START_DATE] = (
                            start_date_iso
                        )
                    if end_date_iso:
                        progress_sync[const.DATA_KID_BADGE_PROGRESS_END_DATE] = (
                            end_date_iso
                        )

    # =========================================================================
    # CRUD METHODS (Manager-owned create/update/delete)
    # =========================================================================
    # These methods own the write operations for badge entities.
    # Called by options_flow.py and services.py - they must NOT write directly.

    def create_badge(
        self,
        user_input: dict[str, Any],
        internal_id: str | None = None,
        badge_type: str | None = None,
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Create a new badge in storage.

        Args:
            user_input: Badge data with DATA_* keys.
            internal_id: Optional pre-generated UUID (for form resubmissions).
            badge_type: Optional badge type override.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Complete BadgeData dict ready for use.

        Emits:
            SIGNAL_SUFFIX_BADGE_CREATED with badge_id and badge_name.
        """
        # Build complete badge data structure
        if badge_type:
            badge_data = dict(db.build_badge(user_input, badge_type=badge_type))
        else:
            badge_data = dict(db.build_badge(user_input))

        # Override internal_id if provided (for form resubmission consistency)
        if internal_id:
            badge_data[const.DATA_BADGE_INTERNAL_ID] = internal_id

        final_id = str(badge_data[const.DATA_BADGE_INTERNAL_ID])
        badge_name = str(badge_data.get(const.DATA_BADGE_NAME, ""))

        # Store in coordinator data
        self.coordinator._data[const.DATA_BADGES][final_id] = badge_data

        # Sync badge progress for all kids (creates progress sensors)
        for kid_id in self.coordinator.kids_data:
            self.sync_badge_progress_for_kid(kid_id)
        # Recalculate badges to trigger initial evaluation
        self.recalculate_all_badges()

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_CREATED,
            badge_id=final_id,
            badge_name=badge_name,
        )

        const.LOGGER.info(
            "Created badge '%s' (ID: %s)",
            badge_name,
            final_id,
        )

        return badge_data

    def update_badge(
        self,
        badge_id: str,
        updates: dict[str, Any],
        badge_type: str | None = None,
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Update an existing badge in storage.

        Args:
            badge_id: Internal UUID of the badge to update.
            updates: Partial badge data with DATA_* keys to merge.
            badge_type: Optional badge type override.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated BadgeData dict.

        Raises:
            HomeAssistantError: If badge not found.

        Emits:
            SIGNAL_SUFFIX_BADGE_UPDATED with badge_id and badge_name.
        """
        badges_data = self.coordinator._data.get(const.DATA_BADGES, {})
        if badge_id not in badges_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BADGE,
                    "name": badge_id,
                },
            )

        existing = badges_data[badge_id]
        # Build updated badge (merge existing with updates)
        if badge_type:
            updated_badge = dict(
                db.build_badge(updates, existing=existing, badge_type=badge_type)
            )
        else:
            updated_badge = dict(db.build_badge(updates, existing=existing))

        # Store updated badge
        self.coordinator._data[const.DATA_BADGES][badge_id] = updated_badge

        # Sync badge progress for all kids after badge update
        for kid_id in self.coordinator.kids_data:
            self.sync_badge_progress_for_kid(kid_id)
        self.recalculate_all_badges()

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        badge_name = str(updated_badge.get(const.DATA_BADGE_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_UPDATED,
            badge_id=badge_id,
            badge_name=badge_name,
        )

        const.LOGGER.debug(
            "Updated badge '%s' (ID: %s)",
            badge_name,
            badge_id,
        )

        return updated_badge

    def delete_badge(self, badge_id: str, *, immediate_persist: bool = False) -> None:
        """Delete a badge from storage and cleanup references.

        Args:
            badge_id: Internal UUID of the badge to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If badge not found.

        Emits:
            SIGNAL_SUFFIX_BADGE_DELETED with badge_id and badge_name.
        """
        badges_data = self.coordinator._data.get(const.DATA_BADGES, {})
        if badge_id not in badges_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_BADGE,
                    "name": badge_id,
                },
            )

        badge_name = badges_data[badge_id].get(const.DATA_BADGE_NAME, badge_id)

        # Delete from storage
        del self.coordinator._data[const.DATA_BADGES][badge_id]

        # Remove awarded badges from kids (this manager has the method)
        self.remove_awarded_badges_by_id(badge_id=badge_id)

        # Sync badge progress for all kids after badge deletion
        # Phase 3A: cumulative progress computed on-read (no storage write needed)
        for kid_id in self.coordinator.kids_data:
            self.sync_badge_progress_for_kid(kid_id)

        # Remove badge-related entities from Home Assistant registry
        remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            badge_id,
        )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_DELETED,
            badge_id=badge_id,
            badge_name=badge_name,
        )

        const.LOGGER.info(
            "Deleted badge '%s' (ID: %s)",
            badge_name,
            badge_id,
        )

    # =========================================================================
    # ACHIEVEMENT CRUD
    # =========================================================================

    def create_achievement(
        self,
        user_input: dict[str, Any],
        internal_id: str | None = None,
        *,
        immediate_persist: bool = False,
    ) -> str:
        """Create a new achievement in storage.

        Args:
            user_input: Achievement data with DATA_* keys.
            internal_id: Optional pre-generated UUID.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            The internal_id of the created achievement.

        Emits:
            SIGNAL_SUFFIX_ACHIEVEMENT_CREATED with achievement_id and achievement_name.
        """
        # Build complete achievement data structure
        achievement_data = dict(db.build_achievement(user_input))

        # Override internal_id if provided
        if internal_id:
            achievement_data[const.DATA_ACHIEVEMENT_INTERNAL_ID] = internal_id

        final_id = str(achievement_data[const.DATA_ACHIEVEMENT_INTERNAL_ID])
        achievement_name = str(achievement_data.get(const.DATA_ACHIEVEMENT_NAME, ""))

        # Store in coordinator data
        self.coordinator._data.setdefault(const.DATA_ACHIEVEMENTS, {})[final_id] = (
            achievement_data
        )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_CREATED,
            achievement_id=final_id,
            achievement_name=achievement_name,
        )

        const.LOGGER.info(
            "Created achievement '%s' (ID: %s)",
            achievement_name,
            final_id,
        )

        return final_id

    def update_achievement(
        self,
        achievement_id: str,
        updates: dict[str, Any],
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Update an existing achievement in storage.

        Args:
            achievement_id: Internal UUID of the achievement to update.
            updates: Partial achievement data with DATA_* keys to merge.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated AchievementData dict.

        Raises:
            HomeAssistantError: If achievement not found.

        Emits:
            SIGNAL_SUFFIX_ACHIEVEMENT_UPDATED with achievement_id and achievement_name.
        """
        achievements_data = self.coordinator._data.get(const.DATA_ACHIEVEMENTS, {})
        if achievement_id not in achievements_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ACHIEVEMENT,
                    "name": achievement_id,
                },
            )

        existing = achievements_data[achievement_id]
        # Build updated achievement (merge existing with updates)
        updated_achievement = dict(db.build_achievement(updates, existing=existing))
        # Preserve internal_id
        updated_achievement[const.DATA_ACHIEVEMENT_INTERNAL_ID] = achievement_id

        # Store updated achievement
        self.coordinator._data[const.DATA_ACHIEVEMENTS][achievement_id] = (
            updated_achievement
        )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        achievement_name = str(updated_achievement.get(const.DATA_ACHIEVEMENT_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_UPDATED,
            achievement_id=achievement_id,
            achievement_name=achievement_name,
        )

        const.LOGGER.debug(
            "Updated achievement '%s' (ID: %s)",
            achievement_name,
            achievement_id,
        )

        return updated_achievement

    def delete_achievement(
        self, achievement_id: str, *, immediate_persist: bool = False
    ) -> None:
        """Delete an achievement from storage and cleanup references.

        Args:
            achievement_id: Internal UUID of the achievement to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If achievement not found.

        Emits:
            SIGNAL_SUFFIX_ACHIEVEMENT_DELETED with achievement_id and achievement_name.
        """
        achievements_data = self.coordinator._data.get(const.DATA_ACHIEVEMENTS, {})
        if achievement_id not in achievements_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ACHIEVEMENT,
                    "name": achievement_id,
                },
            )

        achievement_name = achievements_data[achievement_id].get(
            const.DATA_ACHIEVEMENT_NAME, achievement_id
        )

        # Delete from storage
        del self.coordinator._data[const.DATA_ACHIEVEMENTS][achievement_id]

        # Remove achievement-related entities from Home Assistant registry
        remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            achievement_id,
        )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_DELETED,
            achievement_id=achievement_id,
            achievement_name=achievement_name,
        )

        const.LOGGER.info(
            "Deleted achievement '%s' (ID: %s)",
            achievement_name,
            achievement_id,
        )

    # =========================================================================
    # CHALLENGE CRUD
    # =========================================================================

    def create_challenge(
        self,
        user_input: dict[str, Any],
        internal_id: str | None = None,
        *,
        immediate_persist: bool = False,
    ) -> str:
        """Create a new challenge in storage.

        Args:
            user_input: Challenge data with DATA_* keys.
            internal_id: Optional pre-generated UUID.
            immediate_persist: If True, persist immediately (use for config flow operations).
            internal_id: Optional pre-generated UUID.

        Returns:
            The internal_id of the created challenge.

        Emits:
            SIGNAL_SUFFIX_CHALLENGE_CREATED with challenge_id and challenge_name.
        """
        # Build complete challenge data structure
        challenge_data = dict(db.build_challenge(user_input))

        # Override internal_id if provided
        if internal_id:
            challenge_data[const.DATA_CHALLENGE_INTERNAL_ID] = internal_id

        final_id = str(challenge_data[const.DATA_CHALLENGE_INTERNAL_ID])
        challenge_name = str(challenge_data.get(const.DATA_CHALLENGE_NAME, ""))

        # Store in coordinator data
        self.coordinator._data.setdefault(const.DATA_CHALLENGES, {})[final_id] = (
            challenge_data
        )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_CHALLENGE_CREATED,
            challenge_id=final_id,
            challenge_name=challenge_name,
        )

        const.LOGGER.info(
            "Created challenge '%s' (ID: %s)",
            challenge_name,
            final_id,
        )

        return final_id

    def update_challenge(
        self,
        challenge_id: str,
        updates: dict[str, Any],
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Update an existing challenge in storage.

        Args:
            challenge_id: Internal UUID of the challenge to update.
            updates: Partial challenge data with DATA_* keys to merge.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated ChallengeData dict.

        Raises:
            HomeAssistantError: If challenge not found.

        Emits:
            SIGNAL_SUFFIX_CHALLENGE_UPDATED with challenge_id and challenge_name.
        """
        challenges_data = self.coordinator._data.get(const.DATA_CHALLENGES, {})
        if challenge_id not in challenges_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHALLENGE,
                    "name": challenge_id,
                },
            )

        existing = challenges_data[challenge_id]
        # Build updated challenge (merge existing with updates)
        updated_challenge = dict(db.build_challenge(updates, existing=existing))
        # Preserve internal_id
        updated_challenge[const.DATA_CHALLENGE_INTERNAL_ID] = challenge_id

        # Store updated challenge
        self.coordinator._data[const.DATA_CHALLENGES][challenge_id] = updated_challenge

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        challenge_name = str(updated_challenge.get(const.DATA_CHALLENGE_NAME, ""))

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_CHALLENGE_UPDATED,
            challenge_id=challenge_id,
            challenge_name=challenge_name,
        )

        const.LOGGER.debug(
            "Updated challenge '%s' (ID: %s)",
            challenge_name,
            challenge_id,
        )

        return updated_challenge

    def delete_challenge(
        self, challenge_id: str, *, immediate_persist: bool = False
    ) -> None:
        """Delete a challenge from storage and cleanup references.

        Args:
            challenge_id: Internal UUID of the challenge to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If challenge not found.

        Emits:
            SIGNAL_SUFFIX_CHALLENGE_DELETED with challenge_id and challenge_name.
        """
        challenges_data = self.coordinator._data.get(const.DATA_CHALLENGES, {})
        if challenge_id not in challenges_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHALLENGE,
                    "name": challenge_id,
                },
            )

        challenge_name = challenges_data[challenge_id].get(
            const.DATA_CHALLENGE_NAME, challenge_id
        )

        # Delete from storage
        del self.coordinator._data[const.DATA_CHALLENGES][challenge_id]

        # Remove challenge-related entities from Home Assistant registry
        remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            challenge_id,
        )

        self.coordinator._persist(immediate=immediate_persist)
        self.coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_CHALLENGE_DELETED,
            challenge_id=challenge_id,
            challenge_name=challenge_name,
        )

        const.LOGGER.info(
            "Deleted challenge '%s' (ID: %s)",
            challenge_name,
            challenge_id,
        )

    # =========================================================================
    # DATA RESET - Transactional Data Reset for Gamification Domain
    # =========================================================================

    async def data_reset_badges(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for badges domain.

        Clears per-kid badge state including badge_data tracking and
        badge-related lists while preserving badge definitions.

        Args:
            scope: Reset scope (global, kid, item_type, item)
            kid_id: Target kid ID for kid scope (optional)
            item_id: Target badge ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: badges domain - scope=%s, kid_id=%s, item_id=%s",
            scope,
            kid_id,
            item_id,
        )

        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})

        # Determine which kids to process
        if kid_id:
            kid_ids = [kid_id] if kid_id in kids_data else []
        else:
            kid_ids = list(kids_data.keys())

        for loop_kid_id in kid_ids:
            kid_info = kids_data.get(loop_kid_id)
            if not kid_info:
                continue

            # Reset badge-related fields from _BADGE_KID_RUNTIME_FIELDS
            for field in db._BADGE_KID_RUNTIME_FIELDS:
                if field not in kid_info:
                    continue
                field_data = kid_info[field]
                if item_id and isinstance(field_data, dict):
                    # Item scope - only clear specific badge
                    field_data.pop(item_id, None)
                elif isinstance(field_data, (dict, list)):
                    field_data.clear()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Recalculate multiplier for affected kids after clearing badge data
        # With cumulative badge progress cleared, this will emit signal with 1.0
        # (same pattern as demote_cumulative_badge)
        for loop_kid_id in kid_ids:
            self.update_point_multiplier_for_kid(loop_kid_id)

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: badges domain complete - %d kids affected",
            len(kid_ids),
        )

    async def data_reset_achievements(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for achievements domain.

        Clears per-kid achievement progress stored in the achievement's
        progress dict while preserving achievement definitions.

        Args:
            scope: Reset scope (global, kid, item_type, item)
            kid_id: Target kid ID for kid scope (optional)
            item_id: Target achievement ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: achievements domain - scope=%s, kid_id=%s, item_id=%s",
            scope,
            kid_id,
            item_id,
        )

        achievements_data = self.coordinator._data.get(const.DATA_ACHIEVEMENTS, {})
        kids_data = self.coordinator._data.get(const.DATA_KIDS, {})

        # Determine which achievements to process
        if item_id:
            achievement_ids = [item_id] if item_id in achievements_data else []
        else:
            achievement_ids = list(achievements_data.keys())

        # Validate kid_id if provided
        if kid_id and kid_id not in kids_data:
            const.LOGGER.warning(
                "Data reset: achievements - kid_id '%s' not found",
                kid_id,
            )
            return

        affected_count = 0
        for achievement_id in achievement_ids:
            achievement_info = achievements_data.get(achievement_id)
            if not achievement_info:
                continue

            progress = achievement_info.get(const.DATA_ACHIEVEMENT_PROGRESS, {})
            if kid_id:
                # Kid scope - only clear this kid's progress
                if kid_id in progress:
                    del progress[kid_id]
                    affected_count += 1
            else:
                # Global/item_type/item scope - clear all progress
                affected_count += len(progress)
                progress.clear()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: achievements domain complete - %d progress entries cleared",
            affected_count,
        )

    async def data_reset_challenges(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for challenges domain.

        Clears challenge progress while preserving challenge definitions.
        Progress is stored in challenge[progress][kid_id].

        Args:
            scope: Reset scope (global, kid, item_type, item)
            kid_id: Target kid ID for kid scope (optional)
            item_id: Target challenge ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: challenges domain - scope=%s, kid_id=%s, item_id=%s",
            scope,
            kid_id,
            item_id,
        )

        challenges_data = self.coordinator._data.get(const.DATA_CHALLENGES, {})

        # Determine which challenges to process
        if item_id:
            challenge_ids = [item_id] if item_id in challenges_data else []
        else:
            challenge_ids = list(challenges_data.keys())

        affected_count = 0
        # Reset challenge progress
        for challenge_id in challenge_ids:
            challenge_info = challenges_data.get(challenge_id)
            if not challenge_info:
                continue

            progress = challenge_info.get(const.DATA_CHALLENGE_PROGRESS, {})
            if kid_id:
                # Kid scope - only clear this kid's progress
                if kid_id in progress:
                    del progress[kid_id]
                    affected_count += 1
            else:
                # Global/item_type/item scope - reset all progress
                affected_count += len(progress)
                progress.clear()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self.coordinator._persist_and_update()

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: challenges domain complete - %d progress entries cleared",
            affected_count,
        )
