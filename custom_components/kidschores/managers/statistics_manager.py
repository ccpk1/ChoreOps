"""Statistics Manager - Event-driven statistics aggregation.

This manager handles all period-based and all-time statistics:
- Point stats (earned/spent by period and source)
- Chore stats (completions by period)
- Reward stats (claims/approvals by period)

ARCHITECTURE (v0.5.0+ "Clean Break"):
- StatisticsManager LISTENS to domain events (POINTS_CHANGED, CHORE_APPROVED, etc.)
- Domain managers (EconomyManager, ChoreManager, RewardManager) emit events ONLY
- This decouples business logic from historical reporting

Event subscriptions:
- SIGNAL_SUFFIX_POINTS_CHANGED → _on_points_changed()
- SIGNAL_SUFFIX_CHORE_APPROVED → _on_chore_approved()
- SIGNAL_SUFFIX_CHORE_COMPLETED → _on_chore_completed()
- SIGNAL_SUFFIX_CHORE_CLAIMED → _on_chore_claimed()
- SIGNAL_SUFFIX_CHORE_DISAPPROVED → _on_chore_disapproved()
- SIGNAL_SUFFIX_CHORE_OVERDUE → _on_chore_overdue()
- SIGNAL_SUFFIX_REWARD_APPROVED → _on_reward_approved()

PHASE 7.5 ARCHITECTURE (Statistics Presenter & Data Sanitization):
- Directive 1: Derivative Data is Ephemeral - temporal stats MUST NOT be persisted
- Directive 2: Manager-Controlled Time - StatisticsManager owns the "Financial Calendar"
- Directive 3: Cache is Presentation, not Database - must be recreatable from buckets

Cache Architecture:
- _stats_cache[kid_id] contains PRES_* keys for presentation (memory-only)
- Persistent data lives in point_data.periods (buckets) and high-water marks
- Cache is rebuilt from buckets on startup and on-demand (get_stats API)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.core import callback

from .. import const
from ..utils.dt_utils import dt_add_interval, dt_now_local, dt_parse
from .base_manager import BaseManager

if TYPE_CHECKING:
    from asyncio import TimerHandle

    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator
    from ..engines.statistics_engine import StatisticsEngine
    from ..type_defs import ChoreData


__all__ = ["StatisticsManager"]

# Phase 7.5: Cache refresh debounce delay (500ms)
# Prevents thundering herd on rapid events (e.g., bulk approvals)
CACHE_REFRESH_DEBOUNCE_SECONDS = 0.5


class StatisticsManager(BaseManager):
    """Manager for event-driven statistics aggregation.

    Responsibilities:
    - Listen to domain events (POINTS_CHANGED, CHORE_APPROVED, REWARD_APPROVED)
    - Update period-based statistics (daily/weekly/monthly/yearly/all_time)
    - Maintain all-time aggregates
    - Prune old history data

    NOT responsible for:
    - Computing point balances (EconomyManager)
    - Business logic (domain managers)
    - Gamification triggers (GamificationManager)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize the StatisticsManager.

        Args:
            hass: Home Assistant instance
            coordinator: The main KidsChores coordinator
        """
        super().__init__(hass, coordinator)
        self._coordinator = coordinator

        # Phase 7.5: Presentation cache (memory-only, PRES_* keys)
        # Cache structure: {kid_id: {PRES_KID_POINTS_EARNED_TODAY: ..., ...}}
        # This cache holds derived/temporal values that are NOT persisted to storage.
        # All values can be regenerated from period buckets (point_data.periods).
        self._stats_cache: dict[str, dict[str, Any]] = {}

        # Phase 7.5: Debounce timers for cache refreshes (500ms per-kid)
        # Prevents thundering herd on rapid events (e.g., bulk approvals)
        self._cache_timers: dict[str, TimerHandle] = {}

    @property
    def _stats_engine(self) -> StatisticsEngine:
        """Get the StatisticsEngine from coordinator."""
        return self._coordinator.stats

    async def async_setup(self) -> None:
        """Set up event subscriptions for statistics tracking.

        Subscribe to:
        - CHORES_READY: Startup cascade - hydrate stats → emit STATS_READY
        - POINTS_CHANGED: Track point transactions
        - CHORE_APPROVED: Track chore completions
        - REWARD_APPROVED: Track reward redemptions

        Phase 7.5:
        - Midnight Rollover: Clear 'today' cache keys at midnight
        - Startup Hydration: Now triggered by CHORES_READY signal (cascade)
        """
        # Startup cascade - wait for chores to be ready before hydrating stats
        self.listen(const.SIGNAL_SUFFIX_CHORES_READY, self._on_chores_ready)

        # Subscribe to point change events
        self.listen(const.SIGNAL_SUFFIX_POINTS_CHANGED, self._on_points_changed)

        # Subscribe to chore events
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_COMPLETED, self._on_chore_completed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_CLAIMED, self._on_chore_claimed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DISAPPROVED, self._on_chore_disapproved)
        self.listen(const.SIGNAL_SUFFIX_CHORE_OVERDUE, self._on_chore_overdue)
        self.listen(const.SIGNAL_SUFFIX_CHORE_MISSED, self._on_chore_missed)

        # Quiet transitions - state changes without bucket writes (snapshot only)
        self.listen(const.SIGNAL_SUFFIX_CHORE_STATUS_RESET, self._on_chore_status_reset)
        self.listen(const.SIGNAL_SUFFIX_CHORE_UNDONE, self._on_chore_undone)

        # Subscribe to reward approval events
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_approved)
        self.listen(const.SIGNAL_SUFFIX_REWARD_CLAIMED, self._on_reward_claimed)
        self.listen(const.SIGNAL_SUFFIX_REWARD_DISAPPROVED, self._on_reward_disapproved)

        # Subscribe to badge events (Phase 4: Period Update Ownership)
        self.listen(const.SIGNAL_SUFFIX_BADGE_EARNED, self._on_badge_earned)

        # Subscribe to bonus/penalty events (Phase 4C: Bonus/Penalty Period Tracking)
        self.listen(const.SIGNAL_SUFFIX_BONUS_APPLIED, self._on_bonus_applied)
        self.listen(const.SIGNAL_SUFFIX_PENALTY_APPLIED, self._on_penalty_applied)

        # Midnight rollover - listen to SystemManager's signal (Timer Owner pattern)
        # Clears 'today' cache keys at midnight so sensors show 0 immediately
        self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)

        # Data reset completion signals - invalidate caches when data is reset
        # Each domain manager emits completion signal after reset; we listen to all
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_POINTS_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )
        self.listen(
            const.SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE,
            self._on_data_reset_complete,
        )

        # Note: Startup hydration is now triggered by CHORES_READY signal (cascade)
        # See _on_chores_ready() handler below

        const.LOGGER.debug("StatisticsManager: Event subscriptions initialized")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    @callback
    def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
        """Handle midnight rollover - invalidate all caches.

        At midnight, all 'today' values become stale. Rather than surgically
        removing only PRES_*_TODAY keys, we invalidate the entire cache.
        Lazy hydration will rebuild on next get_stats() call.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.info("StatisticsManager: Midnight rollover - clearing cache")
        self.invalidate_cache()

    async def _on_points_changed(self, payload: dict[str, Any]) -> None:
        """Handle POINTS_CHANGED event - update point statistics.

        This is called whenever EconomyManager.deposit() or .withdraw() is invoked.
        Updates period-based point_data (daily/weekly/monthly/yearly/all_time):
        - points_earned (positive deltas)
        - points_spent (negative deltas)
        - by_source breakdown
        - highest_balance (all_time only)

        Phase 7G.1 Architecture: All point stats live in point_data.periods.
        No separate point_stats dict - data is single source of truth.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - old_balance: Balance before transaction
                - new_balance: Balance after transaction
                - delta: The point change (positive or negative)
                - source: Transaction source (POINTS_SOURCE_*)
                - reference_id: Optional related entity ID
        """
        # Extract payload values
        kid_id = payload.get("kid_id", "")
        old_balance = payload.get("old_balance", 0.0)  # noqa: F841 - future use
        new_balance = payload.get("new_balance", 0.0)
        delta = payload.get("delta", 0.0)
        source = payload.get("source", "")

        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_points_changed: Kid '%s' not found",
                kid_id,
            )
            return

        # Phase 3B Tenant Rule: Guard against missing point_periods
        # EconomyManager (Landlord) creates point_periods on-demand before emitting POINTS_CHANGED
        periods_data: dict[str, Any] | None = kid_info.get(const.DATA_KID_POINT_PERIODS)
        if periods_data is None:
            const.LOGGER.warning(
                "StatisticsManager._on_points_changed: point_periods missing for kid '%s' - "
                "skipping (EconomyManager should have created it before emitting signal)",
                kid_id,
            )
            return

        # === 1) Record earned/spent to period buckets ===

        now_local = dt_now_local()

        # Determine earned vs spent based on delta sign
        # Positive delta → points_earned, Negative delta → points_spent
        if delta > 0:
            increment_key = const.DATA_KID_POINT_PERIOD_POINTS_EARNED
        else:
            increment_key = const.DATA_KID_POINT_PERIOD_POINTS_SPENT

        # Record earned OR spent using StatisticsEngine (handles daily/weekly/monthly/yearly)
        # NOTE: all_time is handled manually below due to nested bucket structure (all_time.all_time)
        self._stats_engine.record_transaction(
            periods_data,
            {increment_key: delta},
            reference_date=now_local,
            include_all_time=False,
        )

        # === 2) Record by_source to period buckets (nested structure) ===
        period_ids = self._stats_engine.get_period_keys(now_local)
        for period_key, period_id in period_ids.items():
            bucket: dict[str, Any] = periods_data.setdefault(period_key, {})
            entry: dict[str, Any] = bucket.setdefault(period_id, {})
            if const.DATA_KID_POINT_PERIOD_BY_SOURCE not in entry or not isinstance(
                entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE], dict
            ):
                entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE] = {}
            entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE].setdefault(source, 0.0)
            entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE][source] = round(
                entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE][source] + delta,
                const.DATA_FLOAT_PRECISION,
            )

        # === 3) Record by_source and highest_balance to all_time bucket ===
        all_time_bucket: dict[str, Any] = periods_data.setdefault(
            const.DATA_KID_POINT_PERIODS_ALL_TIME, {}
        )
        all_time_entry: dict[str, Any] = all_time_bucket.setdefault(
            const.PERIOD_ALL_TIME, {}
        )

        # by_source for all_time
        if (
            const.DATA_KID_POINT_PERIOD_BY_SOURCE not in all_time_entry
            or not isinstance(
                all_time_entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE], dict
            )
        ):
            all_time_entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE] = {}
        all_time_entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE].setdefault(source, 0.0)
        all_time_entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE][source] = round(
            all_time_entry[const.DATA_KID_POINT_PERIOD_BY_SOURCE][source] + delta,
            const.DATA_FLOAT_PRECISION,
        )

        # points_earned/spent tracking (all_time only - nested bucket requires manual handling)
        # record_transaction() writes to periods["all_time"] directly, but we need
        # periods["all_time"]["all_time"] for consistency with other period structures
        if delta > 0:
            current_earned = all_time_entry.get(
                const.DATA_KID_POINT_PERIOD_POINTS_EARNED, 0.0
            )
            all_time_entry[const.DATA_KID_POINT_PERIOD_POINTS_EARNED] = round(
                current_earned + delta, const.DATA_FLOAT_PRECISION
            )
        else:
            current_spent = all_time_entry.get(
                const.DATA_KID_POINT_PERIOD_POINTS_SPENT, 0.0
            )
            all_time_entry[const.DATA_KID_POINT_PERIOD_POINTS_SPENT] = round(
                current_spent + delta, const.DATA_FLOAT_PRECISION
            )

        # highest_balance tracking (all_time only)
        highest = all_time_entry.get(const.DATA_KID_POINT_PERIOD_HIGHEST_BALANCE, 0.0)
        all_time_entry[const.DATA_KID_POINT_PERIOD_HIGHEST_BALANCE] = max(
            highest, new_balance
        )

        # === 4) Prune old period data ===
        self._stats_engine.prune_history(periods_data, self.get_retention_config())

        # === 5) Persist changes ===
        self._coordinator._persist()

        # === 6) Refresh presentation cache (BEFORE notifying sensors) ===
        # Must refresh cache synchronously before async_set_updated_data() triggers sensor reads
        self._refresh_point_cache(kid_id)

        # === 7) Notify Home Assistant of data update ===
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_points_changed: kid=%s, delta=%.2f, source=%s",
            kid_id,
            delta,
            source,
        )

    async def _on_chores_ready(self, payload: dict[str, Any]) -> None:
        """Handle startup cascade - hydrate stats after chores are ready.

        Cascade Position: CHORES_READY → StatisticsManager → STATS_READY

        Hydrates the statistics cache for all kids, then signals downstream
        managers (GamificationManager) to continue their initialization.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.debug(
            "StatisticsManager: Processing CHORES_READY - hydrating cache"
        )

        # Phase 7.5.7: Startup hydration
        # Build cache for all existing kids so sensors have data immediately
        await self._hydrate_cache_all_kids()

        # Signal cascade continues
        self.emit(const.SIGNAL_SUFFIX_STATS_READY)

    async def _on_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_APPROVED event - update approval statistics.

        Records approved count and points to period buckets.
        Note: Completion and streaks are tracked separately via CHORE_COMPLETED signal.
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")
        points_awarded = payload.get("points_awarded", 0.0)
        effective_date = payload.get("effective_date")

        increments: dict[str, int | float] = {
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 1,
        }
        if points_awarded > 0:
            increments[const.DATA_KID_CHORE_DATA_PERIOD_POINTS] = points_awarded

        if self._record_chore_transaction(kid_id, chore_id, increments, effective_date):
            # Transactional Flush: cache was refreshed inside _record_chore_transaction,
            # now notify sensors that data has changed
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_approved: kid=%s, chore=%s, points=%.2f",
                kid_id,
                chore_id,
                points_awarded,
            )

    async def _on_chore_completed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_COMPLETED event - update completion and streak statistics.

        Called when completion criteria is satisfied:
        - INDEPENDENT: Immediately on approval (one kid)
        - SHARED_FIRST: First approving kid only
        - SHARED (all): All kids when last is approved

        Records:
        - Completion count (always)
        - Streak tally (if provided, max 1 per day per kid)
        - Longest streak in all_time bucket
        """
        chore_id = payload.get("chore_id", "")
        kid_ids = payload.get("kid_ids", [])
        effective_date = payload.get("effective_date")
        streak_tallies = payload.get("streak_tallies", {})  # dict: kid_id -> streak

        if not kid_ids:
            const.LOGGER.warning(
                "StatisticsManager._on_chore_completed: No kid_ids for chore=%s",
                chore_id,
            )
            return

        # Record completion for each kid (batch mode - persist once at end)
        for kid_id in kid_ids:
            # Build increments for this kid
            increments: dict[str, int | float] = {
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED: 1,
            }

            # Reset missed_streak_tally to 0 (completion breaks missed streak)
            increments[const.DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY] = 0

            # Handle streak_tally with max-1-per-day enforcement
            streak_tally = streak_tallies.get(kid_id)
            if streak_tally is not None:
                # Get periods structure to check today's bucket
                kid_info = self._get_kid(kid_id)
                if kid_info:
                    chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
                    kid_chore_data = chore_data.get(chore_id, {})
                    periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
                    daily_buckets = periods.get(
                        const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                    )

                    # Get today's bucket key
                    today_key = self._stats_engine.get_period_keys().get("daily")

                    # Check if already set today (max 1 update per day)
                    should_write_streak = True
                    if today_key and today_key in daily_buckets:
                        if (
                            const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY
                            in daily_buckets[today_key]
                        ):
                            should_write_streak = False
                            const.LOGGER.debug(
                                "StatisticsManager._on_chore_completed: SKIP streak_tally "
                                "(already set today) kid=%s, chore=%s, date=%s",
                                kid_id,
                                chore_id,
                                today_key,
                            )

                    # Add to increments if not already set today
                    if should_write_streak:
                        increments[const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY] = (
                            streak_tally
                        )

                        # Update longest_streak in all_time bucket if new high
                        all_time_container = periods.get(
                            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
                        )
                        # All-time uses nested structure: periods["all_time"]["all_time"] = {data}
                        all_time_data = all_time_container.setdefault(
                            const.PERIOD_ALL_TIME, {}
                        )
                        current_longest = all_time_data.get(
                            const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                        )
                        if streak_tally > current_longest:
                            all_time_data[
                                const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
                            ] = streak_tally

                            # Also update kid-level chore_periods for _chores sensor
                            kid_chore_periods = kid_info.get(
                                const.DATA_KID_CHORE_PERIODS
                            )
                            if kid_chore_periods is not None:
                                kid_all_time_container = kid_chore_periods.get(
                                    const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
                                )
                                kid_all_time_data = kid_all_time_container.setdefault(
                                    const.PERIOD_ALL_TIME, {}
                                )
                                kid_current_longest = kid_all_time_data.get(
                                    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                                )
                                # Update if this new streak is higher than current kid-level longest
                                if streak_tally > kid_current_longest:
                                    kid_all_time_data[
                                        const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK
                                    ] = streak_tally

            if self._record_chore_transaction(
                kid_id,
                chore_id,
                increments,
                effective_date,
                persist=False,  # Batch: persist once after loop
            ):
                self._refresh_chore_cache(kid_id)

        # Persist once after all kids updated
        self._coordinator._persist()

        # Transactional Flush: notify sensors that all batch updates are complete
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_chore_completed: chore=%s, kids=%s",
            chore_id,
            kid_ids,
        )

    async def _on_chore_claimed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_CLAIMED event - record claim count to period buckets."""
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if self._record_chore_transaction(
            kid_id, chore_id, {const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED: 1}
        ):
            # Transactional Flush: cache was refreshed inside _record_chore_transaction,
            # now notify sensors that data has changed
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_claimed: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    async def _on_chore_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DISAPPROVED event - record disapproval to period buckets."""
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if self._record_chore_transaction(
            kid_id, chore_id, {const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED: 1}
        ):
            # Transactional Flush: cache was refreshed inside _record_chore_transaction,
            # now notify sensors that data has changed
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_disapproved: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    async def _on_chore_overdue(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_OVERDUE event - record overdue to period buckets.

        Enforces max 1 overdue per day by checking today's bucket value before
        incrementing. This ensures daily buckets never exceed 1 for overdue count.
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        # Validate kid exists
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_chore_overdue: Invalid kid_id=%s",
                kid_id,
            )
            return

        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
        kid_chore_data = chore_data.get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        daily_buckets = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

        # Get today's bucket key
        today_key = self._stats_engine.get_period_keys().get("daily")

        # Check if today's bucket already has overdue >= 1 (max 1 per day rule)
        if today_key and today_key in daily_buckets:
            existing_overdue = daily_buckets[today_key].get(
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE, 0
            )
            if existing_overdue >= 1:
                const.LOGGER.debug(
                    "StatisticsManager._on_chore_overdue: SKIP (already at max 1) "
                    "kid=%s, chore=%s, date=%s, current=%d",
                    kid_id,
                    chore_id,
                    today_key,
                    existing_overdue,
                )
                return

        # Proceed with increment (will create bucket if needed)
        if self._record_chore_transaction(
            kid_id, chore_id, {const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE: 1}
        ):
            # Transactional Flush: cache was refreshed inside _record_chore_transaction,
            # now notify sensors that data has changed
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_overdue: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    async def _on_chore_missed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_MISSED event - record missed to period buckets.

        Phase 5: Handles missed_streak_tally from signal, writes to daily bucket.
        Enforces max 1 missed per day by checking today's bucket value before
        incrementing. Updates missed_longest_streak in all_time bucket if new high.
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")
        missed_streak_tally = payload.get("missed_streak_tally")

        # Validate kid exists
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_chore_missed: Invalid kid_id=%s",
                kid_id,
            )
            return

        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
        kid_chore_data = chore_data.get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        daily_buckets = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

        # Get today's bucket key
        today_key = self._stats_engine.get_period_keys().get("daily")

        # Check if today's bucket already has missed >= 1 (max 1 per day rule)
        if today_key and today_key in daily_buckets:
            existing_missed = daily_buckets[today_key].get(
                const.DATA_KID_CHORE_DATA_PERIOD_MISSED, 0
            )
            if existing_missed >= 1:
                const.LOGGER.debug(
                    "StatisticsManager._on_chore_missed: SKIP (already at max 1) "
                    "kid=%s, chore=%s, date=%s, current=%d",
                    kid_id,
                    chore_id,
                    today_key,
                    existing_missed,
                )
                return

        # Build increments: missed counter + streak_tally snapshot
        increments: dict[str, int | float] = {
            const.DATA_KID_CHORE_DATA_PERIOD_MISSED: 1,
        }

        # Add missed_streak_tally if provided (Phase 5)
        if missed_streak_tally is not None:
            increments[const.DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY] = (
                missed_streak_tally
            )

            # Update missed_longest_streak in all_time bucket if new high
            all_time_container = periods.get(
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
            )
            all_time_data = all_time_container.setdefault(const.PERIOD_ALL_TIME, {})
            current_missed_longest = all_time_data.get(
                const.DATA_KID_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK, 0
            )
            if missed_streak_tally > current_missed_longest:
                all_time_data[
                    const.DATA_KID_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK
                ] = missed_streak_tally

                # Also update kid-level chore_periods for _chores sensor
                kid_chore_periods = kid_info.get(const.DATA_KID_CHORE_PERIODS)
                if kid_chore_periods is not None:
                    kid_all_time_container = kid_chore_periods.get(
                        const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
                    )
                    kid_all_time_data = kid_all_time_container.setdefault(
                        const.PERIOD_ALL_TIME, {}
                    )
                    kid_current_missed_longest = kid_all_time_data.get(
                        const.DATA_KID_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK, 0
                    )
                    if missed_streak_tally > kid_current_missed_longest:
                        kid_all_time_data[
                            const.DATA_KID_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK
                        ] = missed_streak_tally

        # Proceed with increment (will create bucket if needed)
        if self._record_chore_transaction(kid_id, chore_id, increments):
            # Transactional Flush: cache was refreshed inside _record_chore_transaction,
            # now notify sensors that data has changed
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_missed: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    async def _on_chore_status_reset(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_STATUS_RESET event - refresh snapshot counts.

        STATUS_RESET is a quiet transition (no bucket writes needed).
        We only need to refresh the chore cache to update current_* counts.

        Uses Transactional Flush pattern: synchronous refresh then notify sensors.
        No debounce needed - cache calculation is microseconds.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - chore_id: The chore's internal ID
                - chore_name: The chore's display name
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if kid_id:
            # Transactional Flush: Refresh cache synchronously, then notify sensors
            self._refresh_chore_cache(kid_id)
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_status_reset: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    async def _on_chore_undone(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_UNDONE event - refresh snapshot counts.

        UNDONE is a quiet transition (no bucket writes needed).
        We only need to refresh the chore cache to update current_* counts.

        Note: Point reclamation is handled by EconomyManager via
        POINTS_CHANGED signal; this handler only refreshes counts.

        Uses Transactional Flush pattern: synchronous refresh then notify sensors.
        No debounce needed - cache calculation is microseconds.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - chore_id: The chore's internal ID
                - points_to_reclaim: Points that were reclaimed
        """
        kid_id = payload.get("kid_id", "")
        chore_id = payload.get("chore_id", "")

        if kid_id:
            # Transactional Flush: Refresh cache synchronously, then notify sensors
            self._refresh_chore_cache(kid_id)
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug(
                "StatisticsManager._on_chore_undone: kid=%s, chore=%s",
                kid_id,
                chore_id,
            )

    async def _on_reward_approved(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_APPROVED signal.

        Signal emitted by RewardManager when a reward is approved by parent.
        Records transaction with points deducted and approval count to BOTH
        per-reward periods and kid-level reward_periods (dual-bucket pattern).

        Phase 3: StatisticsManager (Tenant) writes to RewardManager (Landlord) structures.

        Note: Point stats are handled separately by _on_points_changed
        when EconomyManager.withdraw() is called for the reward cost.

        Uses Transactional Flush pattern: synchronous write+refresh then notify sensors.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - reward_id: The reward's internal ID
                - cost: Points deducted for reward
                - parent_name: Name of approving parent
                - effective_date: ISO timestamp for parent-lag-proof bucketing
        """
        # Extract payload values
        kid_id = payload.get("kid_id", "")
        reward_id = payload.get("reward_id", "")
        cost = payload.get("cost", 0.0)
        effective_date = payload.get("effective_date")

        if not kid_id or not reward_id:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_approved: Missing kid_id or reward_id in signal payload"
            )
            return

        # Phase 3: Record transaction to BOTH per-reward periods and kid-level reward_periods
        # RewardManager (Landlord) should have called _ensure_kid_structures(kid_id, reward_id)
        success = self._record_reward_transaction(
            kid_id=kid_id,
            reward_id=reward_id,
            increments={
                "approved": 1,
                "points": cost,  # Points deducted for this approval
            },
            effective_date=effective_date,
            persist=False,  # Persist manually after refresh for transactional flush
        )

        if not success:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_approved: Failed to record transaction for kid=%s, reward=%s",
                kid_id,
                reward_id,
            )
            return

        # Transactional Flush: Persist, refresh caches synchronously, then notify sensors
        self._coordinator._persist()
        # Point cache was already refreshed by _on_points_changed (EconomyManager.withdraw)
        # Reward cache needs update for reward-specific stats (claim counts, etc.)
        self._refresh_reward_cache(kid_id)
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_reward_approved: kid=%s, reward=%s, cost=%.2f",
            kid_id,
            reward_id,
            cost,
        )

    async def _on_reward_claimed(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_CLAIMED signal.

        Signal emitted by RewardManager when a kid claims a reward.
        Records transaction with claimed count to BOTH per-reward periods
        and kid-level reward_periods (dual-bucket pattern).

        Phase 3: StatisticsManager (Tenant) writes to RewardManager (Landlord) structures.

        Uses Transactional Flush pattern: synchronous write+refresh then notify sensors.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - reward_id: The reward's internal ID
                - reward_name: The reward's display name
                - effective_date: ISO timestamp for parent-lag-proof bucketing
        """
        kid_id = payload.get("kid_id", "")
        reward_id = payload.get("reward_id", "")
        effective_date = payload.get("effective_date")

        if not kid_id or not reward_id:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_claimed: Missing kid_id or reward_id in signal payload"
            )
            return

        # Phase 3: Record transaction to BOTH per-reward periods and kid-level reward_periods
        success = self._record_reward_transaction(
            kid_id=kid_id,
            reward_id=reward_id,
            increments={
                "claimed": 1,
            },
            effective_date=effective_date,
            persist=False,  # Persist manually after refresh for transactional flush
        )

        if not success:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_claimed: Failed to record transaction for kid=%s, reward=%s",
                kid_id,
                reward_id,
            )
            return

        # Transactional Flush: Persist, refresh cache synchronously, then notify sensors
        self._coordinator._persist()
        self._refresh_reward_cache(kid_id)
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_reward_claimed: kid=%s, reward=%s",
            kid_id,
            reward_id,
        )

    async def _on_reward_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_DISAPPROVED signal.

        Signal emitted by RewardManager when a parent disapproves a reward.
        Records transaction with disapproved count to BOTH per-reward periods
        and kid-level reward_periods (dual-bucket pattern).

        Phase 3: StatisticsManager (Tenant) writes to RewardManager (Landlord) structures.

        Uses Transactional Flush pattern: synchronous write+refresh then notify sensors.

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - reward_id: The reward's internal ID
                - reward_name: The reward's display name
                - effective_date: ISO timestamp for parent-lag-proof bucketing
        """
        kid_id = payload.get("kid_id", "")
        reward_id = payload.get("reward_id", "")
        effective_date = payload.get("effective_date")

        if not kid_id or not reward_id:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_disapproved: Missing kid_id or reward_id in signal payload"
            )
            return

        # Phase 3: Record transaction to BOTH per-reward periods and kid-level reward_periods
        success = self._record_reward_transaction(
            kid_id=kid_id,
            reward_id=reward_id,
            increments={
                "disapproved": 1,
            },
            effective_date=effective_date,
            persist=False,  # Persist manually after refresh for transactional flush
        )

        if not success:
            const.LOGGER.warning(
                "StatisticsManager._on_reward_disapproved: Failed to record transaction for kid=%s, reward=%s",
                kid_id,
                reward_id,
            )
            return

        # Transactional Flush: Persist, refresh cache synchronously, then notify sensors
        self._coordinator._persist()
        self._refresh_reward_cache(kid_id)
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_reward_disapproved: kid=%s, reward=%s",
            kid_id,
            reward_id,
        )

    async def _on_badge_earned(self, payload: dict[str, Any]) -> None:
        """Handle BADGE_EARNED signal.

        Signal emitted by GamificationManager when a badge is awarded to a kid.
        Records transaction to badges_earned periods (award_count incremented).

        Phase 4: StatisticsManager (Tenant) ONLY writes to period buckets.
        GamificationManager (Landlord) creates structure, increments award_count.

        Landlord-Tenant Contract:
        - GamificationManager creates badges_earned[badge_id] with periods structure
        - GamificationManager increments award_count (business logic)
        - StatisticsManager ONLY updates period data in existing structure

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - badge_id: The badge's internal ID
        """
        kid_id = payload.get("kid_id", "")
        badge_id = payload.get("badge_id", "")

        if not kid_id or not badge_id:
            const.LOGGER.warning(
                "StatisticsManager._on_badge_earned: Missing kid_id or badge_id"
            )
            return

        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_badge_earned: Kid not found: %s", kid_id
            )
            return

        # Tenant responsibility: Update period data ONLY (no structure creation)
        badges_earned = kid_info.get(const.DATA_KID_BADGES_EARNED, {})
        badge_entry = badges_earned.get(badge_id)

        if not badge_entry:
            # Landlord violation - structure should exist before signal emission
            const.LOGGER.warning(
                "StatisticsManager._on_badge_earned: Badge entry not found (Landlord should create): kid=%s, badge=%s",
                kid_id,
                badge_id,
            )
            return

        # Get periods bucket (Landlord should have created this)
        # Note: Use `is None` check, NOT `if not periods`, because Landlord
        # correctly creates an empty dict {} which is falsy but valid.
        periods = badge_entry.get(const.DATA_KID_BADGES_EARNED_PERIODS)
        if periods is None:
            const.LOGGER.warning(
                "StatisticsManager._on_badge_earned: Periods bucket missing (Landlord should create): kid=%s, badge=%s",
                kid_id,
                badge_id,
            )
            return

        # Tenant operation: Update period data using StatisticsEngine
        now_local = dt_now_local()
        period_mapping = self._stats_engine.get_period_keys(now_local)

        self._stats_engine.record_transaction(
            cast("dict[str, Any]", periods),
            {const.DATA_KID_BADGES_EARNED_AWARD_COUNT: 1},
            period_key_mapping=period_mapping,
        )

        # Cleanup old period data
        self._stats_engine.prune_history(
            cast("dict[str, Any]", periods), self.get_retention_config()
        )

        # Persist and notify
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_badge_earned: kid=%s, badge=%s",
            kid_id,
            badge_id,
        )

    async def _on_bonus_applied(self, payload: dict[str, Any]) -> None:
        """Handle BONUS_APPLIED signal.

        Signal emitted by EconomyManager when a bonus is applied to a kid.
        Updates period tracking for the specific bonus UUID and records ledger entry.

        Phase 4C: Bonus/Penalty Period Tracking
        - Updates item-level periods: bonuses_applied[uuid]["periods"]
        - No aggregate buckets at kid level (unlike chores/rewards)
        - Adds item_name to transaction ledger for human-readable history

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - bonus_id: The UUID of the bonus entry in bonuses_applied
                - bonus_name: Human-readable bonus name
                - points: Points added (positive value)
                - timestamp: ISO 8601 timestamp (optional, defaults to now)
        """
        kid_id = payload.get("kid_id", "")
        bonus_id = payload.get("bonus_id", "")
        points = payload.get("points", 0.0)
        bonus_name = payload.get("bonus_name", "")
        timestamp_str = payload.get("timestamp")

        # Parse timestamp or use current time
        dt_obj = dt_parse(timestamp_str) if timestamp_str else dt_now_local()
        if not dt_obj or not isinstance(dt_obj, datetime):
            dt_obj = dt_now_local()

        if not kid_id or not bonus_id:
            const.LOGGER.warning(
                "StatisticsManager._on_bonus_applied: Missing kid_id or bonus_id"
            )
            return

        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_bonus_applied: Kid not found: %s", kid_id
            )
            return

        # Tenant responsibility: Read periods created by Landlord (EconomyManager)
        bonus_applies = kid_info.get(const.DATA_KID_BONUS_APPLIES, {})
        bonus_entry = bonus_applies.get(bonus_id)
        if not bonus_entry:
            const.LOGGER.warning(
                "StatisticsManager._on_bonus_applied: Bonus entry not found (Landlord should create): kid=%s, bonus=%s",
                kid_id,
                bonus_id,
            )
            return

        # Tenant: Get periods container from Landlord-created structure
        # (record_transaction will create daily/weekly/etc buckets on-demand)
        periods = bonus_entry.get(const.DATA_KID_BONUS_PERIODS)
        if periods is None:
            const.LOGGER.warning(
                "StatisticsManager._on_bonus_applied: Periods key missing (Landlord should create): kid=%s, bonus=%s",
                kid_id,
                bonus_id,
            )
            return

        # Update all period buckets
        # Note: Do NOT pass period_key_mapping - record_transaction uses default
        # bucket structure (daily/weekly/etc) and creates date keys inside them
        self._stats_engine.record_transaction(
            periods,
            {
                const.DATA_KID_BONUS_PERIOD_APPLIES: 1,
                const.DATA_KID_BONUS_PERIOD_POINTS: points,
            },
            reference_date=dt_obj,
        )

        # Cleanup old period data
        self._stats_engine.prune_history(periods, self.get_retention_config())

        # Persist and notify
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_bonus_applied: kid=%s, bonus=%s (%s), points=%.2f",
            kid_id,
            bonus_id,
            bonus_name,
            points,
        )

    async def _on_penalty_applied(self, payload: dict[str, Any]) -> None:
        """Handle PENALTY_APPLIED signal.

        Signal emitted by EconomyManager when a penalty is applied to a kid.
        Updates period tracking for the specific penalty UUID and records ledger entry.

        Phase 4C: Bonus/Penalty Period Tracking
        - Updates item-level periods: penalties_applied[uuid]["periods"]
        - No aggregate buckets at kid level (unlike chores/rewards)
        - Adds item_name to transaction ledger for human-readable history

        Args:
            payload: Event data containing:
                - kid_id: The kid's internal ID
                - penalty_id: The UUID of the penalty entry in penalties_applied
                - penalty_name: Human-readable penalty name
                - points: Points deducted (negative value)
                - timestamp: ISO 8601 timestamp (optional, defaults to now)
        """
        kid_id = payload.get("kid_id", "")
        penalty_id = payload.get("penalty_id", "")
        points = payload.get("points", 0.0)
        penalty_name = payload.get("penalty_name", "")
        timestamp_str = payload.get("timestamp")

        # Parse timestamp or use current time
        dt_obj = dt_parse(timestamp_str) if timestamp_str else dt_now_local()
        if not dt_obj or not isinstance(dt_obj, datetime):
            dt_obj = dt_now_local()

        if not kid_id or not penalty_id:
            const.LOGGER.warning(
                "StatisticsManager._on_penalty_applied: Missing kid_id or penalty_id"
            )
            return

        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._on_penalty_applied: Kid not found: %s", kid_id
            )
            return

        # Tenant responsibility: Read periods created by Landlord (EconomyManager)
        penalty_applies = kid_info.get(const.DATA_KID_PENALTY_APPLIES, {})
        penalty_entry = penalty_applies.get(penalty_id)
        if not penalty_entry:
            const.LOGGER.warning(
                "StatisticsManager._on_penalty_applied: Penalty entry not found (Landlord should create): kid=%s, penalty=%s",
                kid_id,
                penalty_id,
            )
            return

        # Tenant: Get periods container from Landlord-created structure
        # (record_transaction will create daily/weekly/etc buckets on-demand)
        periods = penalty_entry.get(const.DATA_KID_PENALTY_PERIODS)
        if periods is None:
            const.LOGGER.warning(
                "StatisticsManager._on_penalty_applied: Periods key missing (Landlord should create): kid=%s, penalty=%s",
                kid_id,
                penalty_id,
            )
            return

        # Update all period buckets
        # Note: Do NOT pass period_key_mapping - record_transaction uses default
        # bucket structure (daily/weekly/etc) and creates date keys inside them
        self._stats_engine.record_transaction(
            periods,
            {
                const.DATA_KID_PENALTY_PERIOD_APPLIES: 1,
                const.DATA_KID_PENALTY_PERIOD_POINTS: points,
            },
            reference_date=dt_obj,
        )

        # Cleanup old period data
        self._stats_engine.prune_history(periods, self.get_retention_config())

        # Persist and notify
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "StatisticsManager._on_penalty_applied: kid=%s, penalty=%s (%s), points=%.2f",
            kid_id,
            penalty_id,
            penalty_name,
            points,
        )

    async def _on_data_reset_complete(self, payload: dict[str, Any]) -> None:
        """Handle data reset completion - invalidate affected caches.

        When any domain manager completes a data reset operation, we need to
        invalidate statistics caches so derived values are recalculated from
        the updated source data.

        Payload format (standard across all *_DATA_RESET_COMPLETE signals):
            scope: "global" | "kid" | "item_type" | "item"
            kid_id: str | None - specific kid for kid scope
            item_id: str | None - specific item for item scope

        Args:
            payload: Event data with scope, kid_id, item_id
        """
        scope = payload.get("scope", "global")
        kid_id = payload.get("kid_id")

        const.LOGGER.debug(
            "StatisticsManager: Data reset complete - scope=%s, kid_id=%s",
            scope,
            kid_id,
        )

        if scope in {"global", "item_type"}:
            # Full reset - invalidate all caches
            self.invalidate_cache()
        elif scope == "kid" and kid_id:
            # Kid-specific reset - only invalidate that kid's cache
            self.invalidate_cache(kid_id)
        elif scope == "item":
            # Item-specific reset - may affect stats, invalidate all for safety
            if kid_id:
                self.invalidate_cache(kid_id)
            else:
                self.invalidate_cache()

    # ────────────────────────────────────────────────────────────────
    # Transaction Helpers
    # ────────────────────────────────────────────────────────────────

    def _record_chore_transaction(
        self,
        kid_id: str,
        chore_id: str,
        increments: dict[str, int | float],
        effective_date: str | None = None,
        persist: bool = True,
    ) -> bool:
        """Record a chore transaction to period buckets.

        Common helper for CHORE_APPROVED, CHORE_CLAIMED, CHORE_DISAPPROVED,
        CHORE_OVERDUE, and CHORE_COMPLETED signals. Handles:
        - Getting/creating kid_chore_data.periods structure
        - Recording increments to period buckets via StatisticsEngine
        - Pruning old period data
        - Optionally persisting and refreshing cache

        Args:
            kid_id: The kid's internal ID.
            chore_id: The chore's internal ID.
            increments: Dict of metric keys to increment values.
            effective_date: ISO timestamp for parent-lag-proof bucketing.
                           If None, uses current time.
            persist: If True, calls _persist() and _refresh_chore_cache().
                    Set to False when batching multiple kids.

        Returns:
            True if successful, False if kid not found.
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: Kid '%s' not found",
                kid_id,
            )
            return False

        # Phase 3B Tenant Rule: Guard against missing landlord-owned structures
        # ChoreManager (Landlord) creates chore_data on-demand via _get_kid_chore_data()
        chore_data: dict[str, Any] | None = kid_info.get(const.DATA_KID_CHORE_DATA)
        if chore_data is None:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: chore_data missing for kid '%s' - "
                "skipping (ChoreManager should have created it before emitting signal)",
                kid_id,
            )
            return False

        # Phase 3B Tenant Rule: Guard against missing per-chore entry
        # ChoreManager creates per-chore entries on-demand via _get_kid_chore_data()
        kid_chore_data: dict[str, Any] | None = chore_data.get(chore_id)
        if kid_chore_data is None:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: chore_data entry missing for "
                "kid '%s', chore '%s' - skipping (ChoreManager should create on assignment)",
                kid_id,
                chore_id,
            )
            return False

        # Phase 3B Tenant Rule: Use ChoreManager's Landlord-created periods structure
        # ChoreManager (Landlord) should have called _ensure_kid_structures(kid_id, chore_id)
        # before emitting the signal that triggered this transaction
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS)
        if periods is None:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: periods structure missing for "
                "kid '%s', chore '%s' - ChoreManager should have called _ensure_kid_structures()",
                kid_id,
                chore_id,
            )
            return False

        # Use effective_date for parent-lag-proof bucketing
        # Parse as local timezone for period bucketing (DEVELOPMENT_STANDARDS § 6)
        bucket_dt = (
            cast(
                "datetime | None",
                dt_parse(
                    effective_date, return_type=const.HELPER_RETURN_DATETIME_LOCAL
                ),
            )
            if effective_date
            else None
        )

        # Record transaction to per-chore period buckets
        # NOTE: Do NOT pass period_mapping as period_key_mapping!
        # period_mapping contains date strings like '2026-01-31'
        # period_key_mapping expects structure keys like DATA_KID_CHORE_DATA_PERIODS_DAILY
        # Engine will use default mapping which is correct for chore periods
        self._stats_engine.record_transaction(
            periods,
            increments,
            reference_date=bucket_dt,
        )

        # PHASE 2: Also record to kid-level chore_periods bucket (v44+)
        # ChoreManager (Landlord) should have created this via _ensure_kid_structures(kid_id)
        kid_chore_periods = kid_info.get(const.DATA_KID_CHORE_PERIODS)
        if kid_chore_periods is not None:
            # Record same transaction to aggregated bucket
            self._stats_engine.record_transaction(
                kid_chore_periods,
                increments,
                reference_date=bucket_dt,
            )
        else:
            const.LOGGER.warning(
                "StatisticsManager._record_chore_transaction: kid-level chore_periods missing for "
                "kid '%s' - ChoreManager should have called _ensure_kid_structures(kid_id)",
                kid_id,
            )

        # Prune old period data from both buckets (after all writes complete)
        retention_config = self.get_retention_config()
        self._stats_engine.prune_history(periods, retention_config)
        if kid_chore_periods is not None:
            self._stats_engine.prune_history(kid_chore_periods, retention_config)

        # Optionally persist and refresh cache
        if persist:
            self._coordinator._persist()
            self._refresh_chore_cache(kid_id)

        return True

    def _record_reward_transaction(
        self,
        kid_id: str,
        reward_id: str,
        increments: dict[str, int | float],
        effective_date: str | None = None,
        persist: bool = True,
    ) -> bool:
        """Record a reward transaction to period buckets (dual-bucket pattern).

        Common helper for REWARD_APPROVED, REWARD_CLAIMED, and REWARD_DISAPPROVED
        signals. Handles:
        - Getting per-reward periods structure (reward_data[uuid].periods)
        - Getting kid-level reward_periods structure (aggregated bucket)
        - Recording increments to BOTH buckets via StatisticsEngine
        - Pruning old period data
        - Optionally persisting and refreshing cache

        Args:
            kid_id: The kid's internal ID.
            reward_id: The reward's internal ID.
            increments: Dict of metric keys to increment values.
            effective_date: ISO timestamp for parent-lag-proof bucketing.
                           If None, uses current time.
            persist: If True, calls _persist() and _refresh_reward_cache().
                    Set to False when batching multiple rewards.

        Returns:
            True if successful, False if kid not found or structures missing.
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            const.LOGGER.warning(
                "StatisticsManager._record_reward_transaction: Kid '%s' not found",
                kid_id,
            )
            return False

        # Phase 3 Tenant Rule: Guard against missing landlord-owned structures
        # RewardManager (Landlord) creates reward_data on-demand via get_kid_reward_data()
        reward_data: dict[str, Any] | None = kid_info.get(const.DATA_KID_REWARD_DATA)
        if reward_data is None:
            const.LOGGER.warning(
                "StatisticsManager._record_reward_transaction: reward_data missing for kid '%s' - "
                "skipping (RewardManager should have created it before emitting signal)",
                kid_id,
            )
            return False

        # Phase 3 Tenant Rule: Guard against missing per-reward entry
        # RewardManager creates per-reward entries on-demand via get_kid_reward_data(create=True)
        kid_reward_data: dict[str, Any] | None = reward_data.get(reward_id)
        if kid_reward_data is None:
            const.LOGGER.warning(
                "StatisticsManager._record_reward_transaction: reward_data entry missing for "
                "kid '%s', reward '%s' - skipping (RewardManager should create on redemption)",
                kid_id,
                reward_id,
            )
            return False

        # Phase 3 Tenant Rule: Use RewardManager's Landlord-created periods structure
        # RewardManager (Landlord) should have called _ensure_kid_structures(kid_id, reward_id)
        # before emitting the signal that triggered this transaction
        periods = kid_reward_data.get(const.DATA_KID_REWARD_DATA_PERIODS)
        if periods is None:
            const.LOGGER.warning(
                "StatisticsManager._record_reward_transaction: periods structure missing for "
                "kid '%s', reward '%s' - RewardManager should have called _ensure_kid_structures()",
                kid_id,
                reward_id,
            )
            return False

        # Use effective_date for parent-lag-proof bucketing
        # Parse as local timezone for period bucketing (DEVELOPMENT_STANDARDS § 6)
        bucket_dt = (
            cast(
                "datetime | None",
                dt_parse(
                    effective_date, return_type=const.HELPER_RETURN_DATETIME_LOCAL
                ),
            )
            if effective_date
            else None
        )

        # Record transaction to per-reward period buckets
        self._stats_engine.record_transaction(
            periods,
            increments,
            reference_date=bucket_dt,
        )

        # PHASE 3: Also record to kid-level reward_periods bucket (v43+)
        # RewardManager (Landlord) should have created this via _ensure_kid_structures(kid_id)
        kid_reward_periods = kid_info.get(const.DATA_KID_REWARD_PERIODS)
        if kid_reward_periods is not None:
            # Record same transaction to aggregated bucket
            self._stats_engine.record_transaction(
                kid_reward_periods,
                increments,
                reference_date=bucket_dt,
            )
        else:
            const.LOGGER.warning(
                "StatisticsManager._record_reward_transaction: kid-level reward_periods missing for "
                "kid '%s' - RewardManager should have called _ensure_kid_structures(kid_id)",
                kid_id,
            )

        # Prune old period data from both buckets (after all writes complete)
        retention_config = self.get_retention_config()
        self._stats_engine.prune_history(periods, retention_config)
        if kid_reward_periods is not None:
            self._stats_engine.prune_history(kid_reward_periods, retention_config)

        # Optionally persist and refresh cache
        if persist:
            self._coordinator._persist()
            self._refresh_reward_cache(kid_id)

        return True

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_retention_config(self) -> dict[str, int]:
        """Get retention configuration for period data pruning.

        Reads from config_entry.options for user-configurable retention limits.

        Returns:
            Dict mapping period types to retention counts.
        """
        return {
            "daily": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
            ),
            "weekly": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
            ),
            "monthly": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
            ),
            "yearly": self._coordinator.config_entry.options.get(
                const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
            ),
        }

    def get_report_rollup(
        self,
        kid_id: str,
        start_iso: str,
        end_iso: str,
    ) -> dict[str, Any]:
        """Return period rollups for report generation.

        This method is the manager-owned query boundary for report helpers.
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return self._empty_report_rollup()

        points_periods = cast(
            "dict[str, Any]",
            kid_info.get(const.DATA_KID_POINT_PERIODS, {}),
        )
        chore_periods = cast(
            "dict[str, Any]",
            kid_info.get(const.DATA_KID_CHORE_PERIODS, {}),
        )
        reward_periods = cast(
            "dict[str, Any]",
            kid_info.get(const.DATA_KID_REWARD_PERIODS, {}),
        )

        bonus_periods = [
            cast("dict[str, Any]", entry.get(const.DATA_KID_BONUS_PERIODS, {}))
            for entry in cast(
                "dict[str, Any]",
                kid_info.get(const.DATA_KID_BONUS_APPLIES, {}),
            ).values()
            if isinstance(entry, dict)
        ]
        penalty_periods = [
            cast("dict[str, Any]", entry.get(const.DATA_KID_PENALTY_PERIODS, {}))
            for entry in cast(
                "dict[str, Any]",
                kid_info.get(const.DATA_KID_PENALTY_APPLIES, {}),
            ).values()
            if isinstance(entry, dict)
        ]

        points_rollup = self._rollup_period_metrics(
            points_periods,
            [
                const.DATA_KID_POINT_PERIOD_POINTS_EARNED,
                const.DATA_KID_POINT_PERIOD_POINTS_SPENT,
            ],
            start_iso,
            end_iso,
        )
        chores_rollup = self._rollup_period_metrics(
            chore_periods,
            [
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED,
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED,
                const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED,
                const.DATA_KID_CHORE_DATA_PERIOD_MISSED,
                const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE,
            ],
            start_iso,
            end_iso,
        )
        rewards_rollup = self._rollup_period_metrics(
            reward_periods,
            [
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED,
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED,
                const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED,
                const.DATA_KID_REWARD_DATA_PERIOD_POINTS,
            ],
            start_iso,
            end_iso,
        )

        bonuses_rollup = self._rollup_period_collections(
            bonus_periods,
            [
                const.DATA_KID_BONUS_PERIOD_APPLIES,
                const.DATA_KID_BONUS_PERIOD_POINTS,
            ],
            start_iso,
            end_iso,
        )
        penalties_rollup = self._rollup_period_collections(
            penalty_periods,
            [
                const.DATA_KID_PENALTY_PERIOD_APPLIES,
                const.DATA_KID_PENALTY_PERIOD_POINTS,
            ],
            start_iso,
            end_iso,
        )

        badge_rollup = self._get_badge_rollup(kid_info)
        streak_rollup = self._get_streak_rollup(kid_info, chore_periods)

        return {
            "points": {
                "in_range_earned": round(
                    float(
                        points_rollup["in_range"][
                            const.DATA_KID_POINT_PERIOD_POINTS_EARNED
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
                "in_range_spent": round(
                    float(
                        points_rollup["in_range"][
                            const.DATA_KID_POINT_PERIOD_POINTS_SPENT
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
                "all_time_earned": round(
                    float(
                        points_rollup["all_time"][
                            const.DATA_KID_POINT_PERIOD_POINTS_EARNED
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
                "all_time_spent": round(
                    float(
                        points_rollup["all_time"][
                            const.DATA_KID_POINT_PERIOD_POINTS_SPENT
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
            },
            "chores": {
                "in_range_approved": int(
                    chores_rollup["in_range"][const.DATA_KID_CHORE_DATA_PERIOD_APPROVED]
                ),
                "in_range_claimed": int(
                    chores_rollup["in_range"][const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED]
                ),
                "in_range_disapproved": int(
                    chores_rollup["in_range"][
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED
                    ]
                ),
                "in_range_missed": int(
                    chores_rollup["in_range"][const.DATA_KID_CHORE_DATA_PERIOD_MISSED]
                ),
                "in_range_overdue": int(
                    chores_rollup["in_range"][const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE]
                ),
                "all_time_approved": int(
                    chores_rollup["all_time"][const.DATA_KID_CHORE_DATA_PERIOD_APPROVED]
                ),
                "all_time_claimed": int(
                    chores_rollup["all_time"][const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED]
                ),
                "all_time_disapproved": int(
                    chores_rollup["all_time"][
                        const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED
                    ]
                ),
                "all_time_missed": int(
                    chores_rollup["all_time"][const.DATA_KID_CHORE_DATA_PERIOD_MISSED]
                ),
                "all_time_overdue": int(
                    chores_rollup["all_time"][const.DATA_KID_CHORE_DATA_PERIOD_OVERDUE]
                ),
            },
            "rewards": {
                "in_range_approved": int(
                    rewards_rollup["in_range"][
                        const.DATA_KID_REWARD_DATA_PERIOD_APPROVED
                    ]
                ),
                "in_range_claimed": int(
                    rewards_rollup["in_range"][
                        const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED
                    ]
                ),
                "in_range_disapproved": int(
                    rewards_rollup["in_range"][
                        const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED
                    ]
                ),
                "in_range_points_spent": round(
                    float(
                        rewards_rollup["in_range"][
                            const.DATA_KID_REWARD_DATA_PERIOD_POINTS
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
                "all_time_approved": int(
                    rewards_rollup["all_time"][
                        const.DATA_KID_REWARD_DATA_PERIOD_APPROVED
                    ]
                ),
                "all_time_claimed": int(
                    rewards_rollup["all_time"][
                        const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED
                    ]
                ),
                "all_time_disapproved": int(
                    rewards_rollup["all_time"][
                        const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED
                    ]
                ),
                "all_time_points_spent": round(
                    float(
                        rewards_rollup["all_time"][
                            const.DATA_KID_REWARD_DATA_PERIOD_POINTS
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
            },
            "bonuses": {
                "in_range_applies": int(
                    bonuses_rollup["in_range"][const.DATA_KID_BONUS_PERIOD_APPLIES]
                ),
                "in_range_points": round(
                    float(
                        bonuses_rollup["in_range"][const.DATA_KID_BONUS_PERIOD_POINTS]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
                "all_time_applies": int(
                    bonuses_rollup["all_time"][const.DATA_KID_BONUS_PERIOD_APPLIES]
                ),
                "all_time_points": round(
                    float(
                        bonuses_rollup["all_time"][const.DATA_KID_BONUS_PERIOD_POINTS]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
            },
            "penalties": {
                "in_range_applies": int(
                    penalties_rollup["in_range"][const.DATA_KID_PENALTY_PERIOD_APPLIES]
                ),
                "in_range_points": round(
                    float(
                        penalties_rollup["in_range"][
                            const.DATA_KID_PENALTY_PERIOD_POINTS
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
                "all_time_applies": int(
                    penalties_rollup["all_time"][const.DATA_KID_PENALTY_PERIOD_APPLIES]
                ),
                "all_time_points": round(
                    float(
                        penalties_rollup["all_time"][
                            const.DATA_KID_PENALTY_PERIOD_POINTS
                        ]
                    ),
                    const.DATA_FLOAT_PRECISION,
                ),
            },
            "streaks": streak_rollup,
            "badges": badge_rollup,
        }

    def _empty_report_rollup(self) -> dict[str, Any]:
        """Return canonical empty report rollup structure."""
        return {
            "points": {
                "in_range_earned": 0.0,
                "in_range_spent": 0.0,
                "all_time_earned": 0.0,
                "all_time_spent": 0.0,
            },
            "chores": {
                "in_range_approved": 0,
                "in_range_claimed": 0,
                "in_range_disapproved": 0,
                "in_range_missed": 0,
                "in_range_overdue": 0,
                "all_time_approved": 0,
                "all_time_claimed": 0,
                "all_time_disapproved": 0,
                "all_time_missed": 0,
                "all_time_overdue": 0,
            },
            "rewards": {
                "in_range_approved": 0,
                "in_range_claimed": 0,
                "in_range_disapproved": 0,
                "in_range_points_spent": 0.0,
                "all_time_approved": 0,
                "all_time_claimed": 0,
                "all_time_disapproved": 0,
                "all_time_points_spent": 0.0,
            },
            "bonuses": {
                "in_range_applies": 0,
                "in_range_points": 0.0,
                "all_time_applies": 0,
                "all_time_points": 0.0,
            },
            "penalties": {
                "in_range_applies": 0,
                "in_range_points": 0.0,
                "all_time_applies": 0,
                "all_time_points": 0.0,
            },
            "streaks": {
                "current_streak": 0,
                "current_missed_streak": 0,
                "all_time_longest_streak": 0,
                "all_time_longest_missed_streak": 0,
            },
            "badges": {
                "earned_unique_count": 0,
                "all_time_award_count": 0,
                "earned_badge_names": [],
                "by_badge": {},
            },
        }

    def _rollup_period_metrics(
        self,
        periods: dict[str, Any],
        metrics: list[str],
        start_iso: str,
        end_iso: str,
    ) -> dict[str, dict[str, int | float]]:
        """Return in-range and all-time metric totals for one period container."""
        in_range = self._sum_daily_metrics(periods, metrics, start_iso, end_iso)
        all_time: dict[str, int | float] = {}
        for metric in metrics:
            all_time[metric] = self._stats_engine.get_period_total(
                periods,
                const.PERIOD_ALL_TIME,
                metric,
            )
        return {
            "in_range": in_range,
            "all_time": all_time,
        }

    def _rollup_period_collections(
        self,
        period_collections: list[dict[str, Any]],
        metrics: list[str],
        start_iso: str,
        end_iso: str,
    ) -> dict[str, dict[str, int | float]]:
        """Aggregate in-range and all-time totals across many period containers."""
        in_range: dict[str, int | float] = dict.fromkeys(metrics, 0)
        all_time: dict[str, int | float] = dict.fromkeys(metrics, 0)

        for periods in period_collections:
            period_rollup = self._rollup_period_metrics(
                periods,
                metrics,
                start_iso,
                end_iso,
            )
            for metric in metrics:
                in_range[metric] = in_range[metric] + period_rollup["in_range"][metric]
                all_time[metric] = all_time[metric] + period_rollup["all_time"][metric]

        return {
            "in_range": in_range,
            "all_time": all_time,
        }

    def _get_streak_rollup(
        self,
        kid_info: dict[str, Any],
        chore_periods: dict[str, Any],
    ) -> dict[str, int]:
        """Build streak rollup for report payloads."""
        current_streak = 0
        current_missed_streak = 0

        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
        if isinstance(kid_chore_data, dict):
            for chore_data in kid_chore_data.values():
                if not isinstance(chore_data, dict):
                    continue
                current_streak = max(
                    current_streak,
                    int(chore_data.get(const.DATA_KID_CHORE_DATA_CURRENT_STREAK, 0)),
                )
                current_missed_streak = max(
                    current_missed_streak,
                    int(
                        chore_data.get(
                            const.DATA_KID_CHORE_DATA_CURRENT_MISSED_STREAK,
                            0,
                        )
                    ),
                )

        return {
            "current_streak": current_streak,
            "current_missed_streak": current_missed_streak,
            "all_time_longest_streak": int(
                self._stats_engine.get_period_total(
                    chore_periods,
                    const.PERIOD_ALL_TIME,
                    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK,
                )
            ),
            "all_time_longest_missed_streak": int(
                self._stats_engine.get_period_total(
                    chore_periods,
                    const.PERIOD_ALL_TIME,
                    const.DATA_KID_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK,
                )
            ),
        }

    def _get_badge_rollup(self, kid_info: dict[str, Any]) -> dict[str, Any]:
        """Build badge rollup with per-badge details from kid badge data."""
        badges_earned = cast(
            "dict[str, Any]",
            kid_info.get(const.DATA_KID_BADGES_EARNED, {}),
        )
        if not isinstance(badges_earned, dict):
            return {
                "earned_unique_count": 0,
                "all_time_award_count": 0,
                "earned_badge_names": [],
                "by_badge": {},
            }

        all_time_award_count = 0
        earned_badge_names: list[str] = []
        by_badge: dict[str, dict[str, Any]] = {}

        for badge_id, badge_info in badges_earned.items():
            if not isinstance(badge_info, dict):
                continue

            badge_name = str(
                badge_info.get(const.DATA_KID_BADGES_EARNED_NAME, "")
            ).strip()
            if badge_name:
                earned_badge_names.append(badge_name)

            periods = badge_info.get(const.DATA_KID_BADGES_EARNED_PERIODS, {})
            award_count = 0
            if isinstance(periods, dict):
                all_time_bucket = periods.get(const.PERIOD_ALL_TIME, {})
                if isinstance(all_time_bucket, dict):
                    all_time_entry = all_time_bucket.get(const.PERIOD_ALL_TIME, {})
                    if isinstance(all_time_entry, dict):
                        raw_count = all_time_entry.get(
                            const.DATA_KID_BADGES_EARNED_AWARD_COUNT,
                            0,
                        )
                        if isinstance(raw_count, (int, float)):
                            award_count = int(raw_count)

            if award_count == 0:
                raw_count = badge_info.get(const.DATA_KID_BADGES_EARNED_AWARD_COUNT, 0)
                if isinstance(raw_count, (int, float)):
                    award_count = int(raw_count)

            all_time_award_count += award_count
            by_badge[str(badge_id)] = {
                "badge_id": str(badge_id),
                "badge_name": badge_name,
                "last_awarded_date": badge_info.get(
                    const.DATA_KID_BADGES_EARNED_LAST_AWARDED
                ),
                "all_time_award_count": award_count,
                "periods": periods if isinstance(periods, dict) else {},
            }

        return {
            "earned_unique_count": len(by_badge),
            "all_time_award_count": all_time_award_count,
            "earned_badge_names": sorted(earned_badge_names),
            "by_badge": by_badge,
        }

    def _sum_daily_metrics(
        self,
        periods: dict[str, Any],
        metrics: list[str],
        start_iso: str,
        end_iso: str,
    ) -> dict[str, int | float]:
        """Sum selected metrics across daily period keys in a date range."""
        parsed_start = dt_parse(start_iso)
        parsed_end = dt_parse(end_iso)
        if not isinstance(parsed_start, datetime) or not isinstance(
            parsed_end, datetime
        ):
            return dict.fromkeys(metrics, 0)

        start_key = parsed_start.date().isoformat()
        end_key = parsed_end.date().isoformat()

        daily_data = periods.get(const.PERIOD_DAILY, {})
        if not isinstance(daily_data, dict):
            return dict.fromkeys(metrics, 0)

        sums: dict[str, int | float] = dict.fromkeys(metrics, 0)
        for day_key, bucket in daily_data.items():
            if not isinstance(day_key, str) or not isinstance(bucket, dict):
                continue
            if day_key < start_key or day_key > end_key:
                continue

            for metric in metrics:
                value = bucket.get(metric, 0)
                if isinstance(value, (int, float)):
                    sums[metric] = sums[metric] + value

        return sums

    def _get_kid(self, kid_id: str) -> dict[str, Any] | None:
        """Get kid data by ID.

        Returns dict[str, Any] instead of KidData because StatisticsManager
        accesses dynamic keys like 'point_data' that aren't in the TypedDict.

        Args:
            kid_id: The internal UUID of the kid

        Returns:
            Kid data dict or None if not found
        """
        return self._coordinator.kids_data.get(kid_id)  # type: ignore[return-value]

    def get_badge_scoped_today_stats(
        self,
        kid_id: str,
        tracked_chores: list[str],
        *,
        today_iso: str,
        current_badge_progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get badge-scoped daily stats for gamification evaluation.

        Tenant-owned period read helper for GamificationManager.
        Reads chore period buckets and returns normalized stats required by
        GamificationEngine runtime context.

        Args:
            kid_id: Kid internal ID.
            tracked_chores: Chore IDs in scope for current badge.
            today_iso: Today date key (YYYY-MM-DD).
            current_badge_progress: Current per-badge progress for streak gate.

        Returns:
            Dict with keys: today_points, today_approved, total_earned,
            streak_yesterday.
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return {
                "today_points": 0.0,
                "today_approved": 0,
                "total_earned": 0.0,
                "streak_yesterday": False,
            }

        chore_data = cast("dict[str, Any]", kid_info.get(const.DATA_KID_CHORE_DATA, {}))

        total_earned = 0.0
        today_points = 0.0
        today_approved = 0

        for chore_id in tracked_chores:
            chore_entry = cast("dict[str, Any]", chore_data.get(chore_id, {}))
            periods = cast(
                "dict[str, Any]",
                chore_entry.get(const.DATA_KID_CHORE_DATA_PERIODS, {}),
            )

            total_earned += float(
                self._stats_engine.get_period_total(
                    periods,
                    const.PERIOD_ALL_TIME,
                    const.DATA_KID_CHORE_DATA_PERIOD_POINTS,
                )
            )
            today_points += float(
                self._stats_engine.get_period_total(
                    periods,
                    const.PERIOD_DAILY,
                    const.DATA_KID_CHORE_DATA_PERIOD_POINTS,
                    period_key=today_iso,
                )
            )
            today_approved += int(
                self._stats_engine.get_period_total(
                    periods,
                    const.PERIOD_DAILY,
                    const.DATA_KID_CHORE_DATA_PERIOD_APPROVED,
                    period_key=today_iso,
                )
            )

        progress = current_badge_progress or {}
        yesterday_iso = dt_add_interval(
            today_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-1,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )
        streak_yesterday = (
            str(progress.get(const.DATA_KID_BADGE_PROGRESS_LAST_UPDATE_DAY, ""))
            == str(yesterday_iso)
            and int(progress.get(const.DATA_KID_BADGE_PROGRESS_DAYS_CYCLE_COUNT, 0)) > 0
        )

        return {
            "today_points": today_points,
            "today_approved": today_approved,
            "total_earned": total_earned,
            "streak_yesterday": streak_yesterday,
        }

    def get_badge_scoped_today_completion(
        self,
        kid_id: str,
        tracked_chores: list[str],
        *,
        today_iso: str,
        only_due_today: bool,
    ) -> dict[str, Any]:
        """Get badge-scoped completion snapshot for today.

        Tenant-owned period read helper for GamificationManager.

        Args:
            kid_id: Kid internal ID.
            tracked_chores: Chore IDs in scope for current badge.
            today_iso: Today date key (YYYY-MM-DD).
            only_due_today: If True, include only chores due today.

        Returns:
            Dict with keys: approved_count, total_count, has_overdue.
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return {
                "approved_count": 0,
                "total_count": 0,
                "has_overdue": False,
            }

        chore_data = cast("dict[str, Any]", kid_info.get(const.DATA_KID_CHORE_DATA, {}))

        approved_count = 0
        total_count = 0
        has_overdue = False

        for chore_id in tracked_chores:
            chore_info = cast(
                "dict[str, Any]", self.coordinator.chores_data.get(chore_id, {})
            )
            if only_due_today and not self._is_chore_due_today_for_kid(
                chore_info, kid_id, today_iso
            ):
                continue

            chore_entry = cast("dict[str, Any]", chore_data.get(chore_id, {}))
            periods = cast(
                "dict[str, Any]",
                chore_entry.get(const.DATA_KID_CHORE_DATA_PERIODS, {}),
            )

            total_count += 1

            approved_today = int(
                self._stats_engine.get_period_total(
                    periods,
                    const.PERIOD_DAILY,
                    const.DATA_KID_CHORE_DATA_PERIOD_APPROVED,
                    period_key=today_iso,
                )
            )
            if approved_today > 0:
                approved_count += 1

            if (
                chore_entry.get(const.DATA_KID_CHORE_DATA_STATE)
                == const.CHORE_STATE_OVERDUE
            ):
                has_overdue = True

        return {
            "approved_count": approved_count,
            "total_count": total_count,
            "has_overdue": has_overdue,
        }

    def _is_chore_due_today_for_kid(
        self,
        chore_info: dict[str, Any],
        kid_id: str,
        today_iso: str,
    ) -> bool:
        """Return True if chore due date for this kid matches today."""
        per_kid_due_dates = cast(
            "dict[str, str | None]",
            chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {}),
        )
        due_date = per_kid_due_dates.get(kid_id) or chore_info.get(
            const.DATA_CHORE_DUE_DATE
        )
        if not isinstance(due_date, str):
            return False
        return due_date[:10] == today_iso

    # =========================================================================
    # Presentation Cache Methods
    # =========================================================================

    def get_stats(self, kid_id: str) -> dict[str, Any]:
        """Get presentation statistics for a kid (Phase 7.5 Cache API).

        This is the primary API for sensors and dashboard helpers.
        Returns cached PRES_* values derived from period buckets.
        If cache miss, rebuilds from buckets (lazy hydration).

        Args:
            kid_id: The kid's internal ID

        Returns:
            Dict with PRES_* keys for presentation, or empty dict if kid not found.
        """
        if kid_id not in self._stats_cache:
            # Cache miss - rebuild from buckets
            self._refresh_all_cache(kid_id)

        return self._stats_cache.get(kid_id, {})

    async def _hydrate_cache_all_kids(self) -> None:
        """Hydrate presentation cache for all existing kids at startup (Phase 7.5.7).

        Called during async_setup() to ensure sensors have data immediately.
        Runs synchronously since this is startup-time work.
        """
        kids_data = self._coordinator.kids_data
        kid_count = len(kids_data)

        if kid_count == 0:
            const.LOGGER.debug("StatisticsManager: No kids to hydrate cache for")
            return

        for kid_id in kids_data:
            self._refresh_all_cache(kid_id)

        const.LOGGER.info(
            "StatisticsManager: Hydrated stats cache for %s kids", kid_count
        )

    def _refresh_all_cache(self, kid_id: str) -> None:
        """Refresh all cache domains for a kid.

        Called on cache miss or startup hydration.
        Delegates to domain-specific refresh methods.

        Args:
            kid_id: The kid's internal ID
        """
        self._refresh_point_cache(kid_id)
        self._refresh_chore_cache(kid_id)
        self._refresh_reward_cache(kid_id)

        # Set last updated timestamp
        cache = self._stats_cache.setdefault(kid_id, {})
        cache[const.PRES_KID_LAST_UPDATED] = dt_now_local().isoformat()

    def _refresh_point_cache(self, kid_id: str) -> None:
        """Refresh point statistics cache for a kid.

        Derives temporal point stats from period buckets (point_periods).
        Only runs on point-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})
        pts_periods = kid_info.get(const.DATA_KID_POINT_PERIODS, {})

        now_local = dt_now_local()
        today_local_iso = now_local.date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        def get_period_values(
            period_key: str, period_id: str
        ) -> tuple[float, float, float, dict[str, float]]:
            """Extract earned, spent, net, and by_source from a period bucket.

            Phase 7G.1: Now reads earned/spent directly from period entry,
            derives net as (earned + spent). No longer reads points_total.
            """
            period = pts_periods.get(period_key, {})
            entry = period.get(period_id, {})
            by_source = entry.get(const.DATA_KID_POINT_PERIOD_BY_SOURCE, {})

            # Read earned/spent directly from period entry (v44+ structure)
            earned = round(
                entry.get(const.DATA_KID_POINT_PERIOD_POINTS_EARNED, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            spent = round(
                entry.get(const.DATA_KID_POINT_PERIOD_POINTS_SPENT, 0.0),
                const.DATA_FLOAT_PRECISION,
            )
            # Net is DERIVED (earned + spent, where spent is negative)
            net = round(earned + spent, const.DATA_FLOAT_PRECISION)
            return earned, spent, net, dict(by_source)

        # Daily
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_PERIODS_DAILY, today_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_TODAY] = earned
        cache[const.PRES_KID_POINTS_SPENT_TODAY] = spent
        cache[const.PRES_KID_POINTS_NET_TODAY] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_TODAY] = by_source

        # Weekly
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_PERIODS_WEEKLY, week_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_WEEK] = earned
        cache[const.PRES_KID_POINTS_SPENT_WEEK] = spent
        cache[const.PRES_KID_POINTS_NET_WEEK] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_WEEK] = by_source

        # Monthly
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_PERIODS_MONTHLY, month_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_MONTH] = earned
        cache[const.PRES_KID_POINTS_SPENT_MONTH] = spent
        cache[const.PRES_KID_POINTS_NET_MONTH] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_MONTH] = by_source

        # Yearly
        earned, spent, net, by_source = get_period_values(
            const.DATA_KID_POINT_PERIODS_YEARLY, year_local_iso
        )
        cache[const.PRES_KID_POINTS_EARNED_YEAR] = earned
        cache[const.PRES_KID_POINTS_SPENT_YEAR] = spent
        cache[const.PRES_KID_POINTS_NET_YEAR] = net
        cache[const.PRES_KID_POINTS_BY_SOURCE_YEAR] = by_source

        # Averages (derived from period aggregates)
        days_in_week = 7
        days_in_month = 30  # Approximate
        week_earned = cache.get(const.PRES_KID_POINTS_EARNED_WEEK, 0.0)
        month_earned = cache.get(const.PRES_KID_POINTS_EARNED_MONTH, 0.0)
        cache[const.PRES_KID_POINTS_AVG_PER_DAY_WEEK] = round(
            week_earned / days_in_week if week_earned else 0.0,
            const.DATA_FLOAT_PRECISION,
        )
        cache[const.PRES_KID_POINTS_AVG_PER_DAY_MONTH] = round(
            month_earned / days_in_month if month_earned else 0.0,
            const.DATA_FLOAT_PRECISION,
        )

    def _refresh_chore_cache(self, kid_id: str) -> None:
        """Refresh chore statistics cache for a kid.

        Derives temporal chore stats from chore_data periods and computes
        snapshot counts (current_overdue, current_claimed, etc.) inline.
        Only runs on chore-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})

        # === Temporal aggregates from period buckets ===
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        now_local = dt_now_local()
        today_local = now_local.date()
        today_local_iso = today_local.isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")
        year_local_iso = now_local.strftime("%Y")

        # Aggregate chore stats from all chore_data entries
        approved_today = 0
        approved_week = 0
        approved_month = 0
        approved_year = 0
        completed_today = 0
        completed_week = 0
        completed_month = 0
        completed_year = 0
        claimed_today = 0
        claimed_week = 0
        claimed_month = 0
        claimed_year = 0
        missed_today = 0
        missed_week = 0
        missed_month = 0
        missed_year = 0
        points_today = 0.0
        points_week = 0.0
        points_month = 0.0
        points_year = 0.0

        # Per-chore completed counts for top chores calculation
        chore_completed_week: dict[str, int] = {}
        chore_completed_month: dict[str, int] = {}
        chore_completed_year: dict[str, int] = {}

        # Snapshot counts (computed inline - no more generate_chore_stats() call)
        current_overdue = 0
        current_claimed = 0
        current_approved = 0
        current_due_today = 0

        for chore_id, chore_info in chore_data.items():
            periods = chore_info.get(const.DATA_KID_CHORE_DATA_PERIODS, {})

            # === Snapshot counts based on current state ===
            state = chore_info.get(const.DATA_KID_CHORE_DATA_STATE)
            if state == const.CHORE_STATE_OVERDUE:
                current_overdue += 1
            elif state == const.CHORE_STATE_CLAIMED:
                current_claimed += 1
            elif state in (
                const.CHORE_STATE_APPROVED,
                const.CHORE_STATE_APPROVED_IN_PART,
            ):
                current_approved += 1

            # Check if due today (need to look up chore definition)
            chore_def: ChoreData | dict[str, Any] = self.coordinator.chores_data.get(
                chore_id, {}
            )
            completion_criteria = chore_def.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                per_kid_due_dates = chore_def.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                due_datetime_iso = per_kid_due_dates.get(kid_id)
            else:
                due_datetime_iso = chore_def.get(const.DATA_CHORE_DUE_DATE)

            if due_datetime_iso:
                try:
                    from datetime import datetime

                    due_dt = datetime.fromisoformat(due_datetime_iso)
                    if due_dt.date() == today_local:
                        current_due_today += 1
                except (ValueError, AttributeError):
                    pass

            # Daily
            daily_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})
            today_entry = daily_periods.get(today_local_iso, {})
            approved_today += today_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_today += today_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            claimed_today += today_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            missed_today += today_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_MISSED, 0)
            points_today += today_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)

            # Weekly
            weekly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY, {})
            week_entry = weekly_periods.get(week_local_iso, {})
            week_completed = week_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            approved_week += week_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_week += week_completed
            claimed_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            missed_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_MISSED, 0)
            points_week += week_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)
            if week_completed > 0:
                chore_completed_week[chore_id] = week_completed

            # Monthly
            monthly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY, {})
            month_entry = monthly_periods.get(month_local_iso, {})
            month_completed = month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            approved_month += month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_month += month_completed
            claimed_month += month_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0
            )
            missed_month += month_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_MISSED, 0)
            points_month += month_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)
            if month_completed > 0:
                chore_completed_month[chore_id] = month_completed

            # Yearly
            yearly_periods = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_YEARLY, {})
            year_entry = yearly_periods.get(year_local_iso, {})
            year_completed = year_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            approved_year += year_entry.get(
                const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
            )
            completed_year += year_completed
            claimed_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            missed_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_MISSED, 0)
            points_year += year_entry.get(const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0)
            if year_completed > 0:
                chore_completed_year[chore_id] = year_completed

        # NOTE: all_time stats are NOT calculated here - they must be read from storage
        # Reason: Retention/pruning means we can't recalculate historical all_time by summing periods
        # All-time data lives in kid["chore_periods"]["all_time"]["all_time"] and is maintained
        # by _record_chore_transaction() writing to both per-chore and kid-level buckets

        # Store snapshot counts in cache (computed inline above)
        cache[const.PRES_KID_CHORES_CURRENT_OVERDUE] = current_overdue
        cache[const.PRES_KID_CHORES_CURRENT_CLAIMED] = current_claimed
        cache[const.PRES_KID_CHORES_CURRENT_APPROVED] = current_approved
        cache[const.PRES_KID_CHORES_CURRENT_DUE_TODAY] = current_due_today

        # Store temporal aggregates in cache
        cache[const.PRES_KID_CHORES_APPROVED_TODAY] = approved_today
        cache[const.PRES_KID_CHORES_APPROVED_WEEK] = approved_week
        cache[const.PRES_KID_CHORES_APPROVED_MONTH] = approved_month
        cache[const.PRES_KID_CHORES_APPROVED_YEAR] = approved_year
        # NOTE: all_time stats omitted from cache - must be read from storage only
        cache[const.PRES_KID_CHORES_COMPLETED_TODAY] = completed_today
        cache[const.PRES_KID_CHORES_COMPLETED_WEEK] = completed_week
        cache[const.PRES_KID_CHORES_COMPLETED_MONTH] = completed_month
        cache[const.PRES_KID_CHORES_COMPLETED_YEAR] = completed_year
        # NOTE: all_time stats omitted from cache - must be read from storage only
        cache[const.PRES_KID_CHORES_CLAIMED_TODAY] = claimed_today
        cache[const.PRES_KID_CHORES_CLAIMED_WEEK] = claimed_week
        cache[const.PRES_KID_CHORES_CLAIMED_MONTH] = claimed_month
        cache[const.PRES_KID_CHORES_CLAIMED_YEAR] = claimed_year
        # NOTE: all_time stats omitted from cache - must be read from storage only
        cache[const.PRES_KID_CHORES_MISSED_TODAY] = missed_today
        cache[const.PRES_KID_CHORES_MISSED_WEEK] = missed_week
        cache[const.PRES_KID_CHORES_MISSED_MONTH] = missed_month
        cache[const.PRES_KID_CHORES_MISSED_YEAR] = missed_year
        # NOTE: all_time stats omitted from cache - must be read from storage only
        cache[const.PRES_KID_CHORES_POINTS_TODAY] = round(
            points_today, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_WEEK] = round(
            points_week, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_MONTH] = round(
            points_month, const.DATA_FLOAT_PRECISION
        )
        cache[const.PRES_KID_CHORES_POINTS_YEAR] = round(
            points_year, const.DATA_FLOAT_PRECISION
        )
        # NOTE: all_time stats omitted from cache - must be read from storage only

        # Averages (derived from temporal aggregates)
        days_in_week = 7
        days_in_month = 30  # Approximate
        days_in_year = 365  # Approximate
        cache[const.PRES_KID_CHORES_AVG_PER_DAY_WEEK] = round(
            completed_week / days_in_week if completed_week else 0.0,
            const.DATA_FLOAT_PRECISION,
        )
        cache[const.PRES_KID_CHORES_AVG_PER_DAY_MONTH] = round(
            completed_month / days_in_month if completed_month else 0.0,
            const.DATA_FLOAT_PRECISION,
        )
        cache[const.PRES_KID_CHORES_AVG_PER_DAY_YEAR] = round(
            completed_year / days_in_year if completed_year else 0.0,
            const.DATA_FLOAT_PRECISION,
        )

        # Top chores (most completed per period)
        def get_top_chore(chore_counts: dict[str, int]) -> str:
            """Return the name of the chore with highest count, or empty string."""
            if not chore_counts:
                return ""
            top_chore_id = max(chore_counts, key=chore_counts.get)  # type: ignore[arg-type]
            chore_def: ChoreData | dict[str, Any] = self.coordinator.chores_data.get(
                top_chore_id, {}
            )
            return str(chore_def.get(const.DATA_CHORE_NAME, ""))

        cache[const.PRES_KID_TOP_CHORES_WEEK] = get_top_chore(chore_completed_week)
        cache[const.PRES_KID_TOP_CHORES_MONTH] = get_top_chore(chore_completed_month)
        cache[const.PRES_KID_TOP_CHORES_YEAR] = get_top_chore(chore_completed_year)

    def _refresh_reward_cache(self, kid_id: str) -> None:
        """Refresh reward statistics cache for a kid.

        Derives temporal reward stats from reward_data periods.
        Only runs on reward-related events.

        Args:
            kid_id: The kid's internal ID
        """
        kid_info = self._get_kid(kid_id)
        if not kid_info:
            return

        cache = self._stats_cache.setdefault(kid_id, {})
        reward_data = kid_info.get(const.DATA_KID_REWARD_DATA, {})

        now_local = dt_now_local()
        today_local_iso = now_local.date().isoformat()
        week_local_iso = now_local.strftime("%Y-W%V")
        month_local_iso = now_local.strftime("%Y-%m")

        # Aggregate reward stats from all reward_data entries
        claimed_today = 0
        claimed_week = 0
        claimed_month = 0
        approved_today = 0
        approved_week = 0
        approved_month = 0

        for _reward_id, reward_info in reward_data.items():
            periods = reward_info.get(const.DATA_KID_REWARD_DATA_PERIODS, {})

            # Daily
            daily_periods = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_DAILY, {})
            today_entry = daily_periods.get(today_local_iso, {})
            claimed_today += today_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0
            )
            approved_today += today_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )

            # Weekly
            weekly_periods = periods.get(const.DATA_KID_REWARD_DATA_PERIODS_WEEKLY, {})
            week_entry = weekly_periods.get(week_local_iso, {})
            claimed_week += week_entry.get(const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0)
            approved_week += week_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )

            # Monthly
            monthly_periods = periods.get(
                const.DATA_KID_REWARD_DATA_PERIODS_MONTHLY, {}
            )
            month_entry = monthly_periods.get(month_local_iso, {})
            claimed_month += month_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0
            )
            approved_month += month_entry.get(
                const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0
            )

        # Store in cache
        cache[const.PRES_KID_REWARDS_CLAIMED_TODAY] = claimed_today
        cache[const.PRES_KID_REWARDS_CLAIMED_WEEK] = claimed_week
        cache[const.PRES_KID_REWARDS_CLAIMED_MONTH] = claimed_month
        cache[const.PRES_KID_REWARDS_APPROVED_TODAY] = approved_today
        cache[const.PRES_KID_REWARDS_APPROVED_WEEK] = approved_week
        cache[const.PRES_KID_REWARDS_APPROVED_MONTH] = approved_month

    def invalidate_cache(self, kid_id: str | None = None) -> None:
        """Invalidate presentation cache (Phase 7.5).

        Call when kid is deleted or on midnight rollover.

        Args:
            kid_id: Specific kid to invalidate, or None to clear all.
        """
        if kid_id is None:
            self._stats_cache.clear()
            # Cancel all pending timers
            for timer in self._cache_timers.values():
                timer.cancel()
            self._cache_timers.clear()
            const.LOGGER.debug("StatisticsManager: Cleared all cache entries")
        elif kid_id in self._stats_cache:
            del self._stats_cache[kid_id]
            # Cancel any pending timer for this kid
            if kid_id in self._cache_timers:
                self._cache_timers[kid_id].cancel()
                del self._cache_timers[kid_id]
            const.LOGGER.debug(
                "StatisticsManager: Invalidated cache for kid %s", kid_id
            )

    def _schedule_cache_refresh(self, kid_id: str, domain: str = "all") -> None:
        """Schedule a debounced cache refresh for a kid (Phase 7.5).

        Uses a 500ms debounce per kid to prevent thundering herd on rapid events.
        If a refresh is already scheduled, it's cancelled and rescheduled.

        Args:
            kid_id: The kid's internal ID
            domain: Which domain to refresh: "point", "chore", "reward", or "all"
        """
        # Cancel existing timer if present
        if kid_id in self._cache_timers:
            self._cache_timers[kid_id].cancel()

        # Create the refresh callback based on domain
        @callback
        def _do_refresh() -> None:
            """Execute the cache refresh after debounce delay."""
            # Remove timer reference
            self._cache_timers.pop(kid_id, None)

            # Refresh based on domain
            if domain == "point":
                self._refresh_point_cache(kid_id)
            elif domain == "chore":
                self._refresh_chore_cache(kid_id)
            elif domain == "reward":
                self._refresh_reward_cache(kid_id)
            else:
                self._refresh_all_cache(kid_id)

            const.LOGGER.debug(
                "StatisticsManager: Refreshed %s cache for kid %s (debounced)",
                domain,
                kid_id,
            )

        # Schedule the refresh
        self._cache_timers[kid_id] = self.hass.loop.call_later(
            CACHE_REFRESH_DEBOUNCE_SECONDS, _do_refresh
        )

    # ==========================================================================
    # PUBLIC QUERY METHODS (Phase 3 Step 8 - v0.5.0 Smart Rotation)
    # ==========================================================================

    def get_chore_completed_counts(
        self, chore_id: str, kid_ids: list[str]
    ) -> dict[str, int]:
        """Get all-time completed counts for a specific chore across multiple kids.

        Used by ChoreManager._advance_rotation() for smart rotation fairness.
        Returns cumulative completed counts (work done) from all_time period bucket.
        This ensures fair rotation based on actual work performed, not parent
        approval delays.

        Args:
            chore_id: The chore's internal ID
            kid_ids: List of kid internal IDs to query

        Returns:
            Dictionary mapping kid_id -> all_time_completed_count
            Kids with no completions return 0
        """
        result: dict[str, int] = {}

        for kid_id in kid_ids:
            kid_info = self._get_kid(kid_id)
            if not kid_info:
                result[kid_id] = 0
                continue

            # Navigate to per-chore period data
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            kid_chore_data = chore_data.get(chore_id, {})
            periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})

            # Get all_time bucket (nested structure: periods["all_time"]["all_time"])
            all_time_container = periods.get(
                const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
            )
            all_time_data = all_time_container.get(const.PERIOD_ALL_TIME, {})

            # Extract completed count (work done)
            completed_count = all_time_data.get(
                const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, 0
            )
            result[kid_id] = int(completed_count)

        const.LOGGER.debug(
            "StatisticsManager.get_chore_completed_counts: chore=%s, results=%s",
            chore_id,
            result,
        )
        return result

    def get_chore_last_completed_timestamps(
        self, chore_id: str, kid_ids: list[str]
    ) -> dict[str, str | None]:
        """Get last completion timestamps for a specific chore across multiple kids.

        Used by ChoreManager._advance_rotation() for smart rotation tie-breaking.
        Uses last_completed (work date) not last_approved (parent action date)
        for fair rotation based on when kids actually did the work.

        Args:
            chore_id: The chore's internal ID
            kid_ids: List of kid internal IDs to query

        Returns:
            Dictionary mapping kid_id -> last_completed ISO timestamp or None
        """
        result: dict[str, str | None] = {}

        for kid_id in kid_ids:
            kid_info = self._get_kid(kid_id)
            if not kid_info:
                result[kid_id] = None
                continue

            # Navigate to per-chore data
            chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            kid_chore_data = chore_data.get(chore_id, {})

            # Get last_completed timestamp (when kid did the work)
            last_completed = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_LAST_COMPLETED
            )
            result[kid_id] = last_completed

        const.LOGGER.debug(
            "StatisticsManager.get_chore_last_completed_timestamps: chore=%s, results=%s",
            chore_id,
            result,
        )
        return result
