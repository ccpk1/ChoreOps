"""Chore Manager - Stateful chore operations and workflow orchestration.

This manager handles all chore state transitions and workflow coordination:
- Claiming, approving, disapproving chores
- Race condition protection via asyncio.Lock
- Event emission for downstream systems (notifications, gamification, economy)

ARCHITECTURE (v0.5.0+ Signal-First):
- ChoreManager = "The Job" (STATEFUL workflow orchestration)
- ChoreEngine = Pure state machine logic (STATELESS)
- EconomyManager = Listens to CHORE_APPROVED/UNDONE signals for point transactions
- NotificationManager = Notifications (wired via Coordinator events)

The manager delegates pure logic to ChoreEngine and uses signals
for cross-domain communication (economy, notifications, achievements).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .. import const, data_builders as db
from ..engines.chore_engine import (
    CHORE_ACTION_APPROVE,
    CHORE_ACTION_CLAIM,
    CHORE_ACTION_DISAPPROVE,
    CHORE_ACTION_OVERDUE,
    CHORE_ACTION_UNDO,
    ChoreEngine,
    TransitionEffect,
)
from ..engines.schedule_engine import calculate_next_due_date_from_chore_info
from ..helpers.entity_helpers import (
    remove_entities_by_item_id,
    remove_orphaned_kid_chore_entities,
    remove_orphaned_shared_chore_sensors,
)
from ..utils.dt_utils import (
    HELPER_RETURN_DATETIME_LOCAL,
    dt_now_iso,
    dt_parse,
    dt_parse_duration,
    dt_to_utc,
)
from .base_manager import BaseManager

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import (
        ChoreData,
        KidChoreDataEntry,
        KidData,
        ResetApplyContext,
        ResetBoundaryCategory,
        ResetContext,
        ResetDecision,
        ResetTrigger,
    )


# Type alias for scan results - uses dict for simplicity
# Keys: chore_id, kid_id, due_dt (datetime), chore_info (dict), time_until_due (timedelta)
ChoreTimeEntry = dict[str, Any]


__all__ = ["ChoreManager"]


class ChoreManager(BaseManager):
    """Manager for chore state transitions and workflow orchestration.

    Responsibilities:
    - Execute claim/approve/disapprove/undo/reset workflows
    - Protect against race conditions (asyncio locks)
    - Emit events for cross-domain communication
    - Emit signals for EconomyManager to handle point deposits

    NOT responsible for:
    - Pure state machine logic (delegated to ChoreEngine)
    - Direct notification sending (events handled by Coordinator)
    - Achievement/badge tracking (events handled by GamificationManager)
    - Point transactions (handled by EconomyManager via signals)
    """

    # =========================================================================
    # §0 LIFECYCLE & INITIALIZATION
    # =========================================================================
    # Class setup, signal subscriptions, periodic scan handlers.

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: KidsChoresDataCoordinator,
    ) -> None:
        """Initialize ChoreManager with dependencies.

        Args:
            hass: Home Assistant instance
            coordinator: Parent coordinator managing this integration
        """
        super().__init__(hass, coordinator)
        self._coordinator = coordinator

        # Locks for race condition protection (keyed by kid_id:chore_id)
        self._approval_locks: dict[str, asyncio.Lock] = {}

        # Phase 4 Guard Rails: Track state modifications per pipeline tick (debug mode)
        self._pipeline_modified_pairs: set[tuple[str, str]] = (
            set()
        )  # (kid_id, chore_id)

        # Phase 3: Time-scan caches (read-only derived values)
        # - due datetime cache: raw ISO string -> parsed UTC datetime
        # - offset cache: chore_id -> source strings + parsed timedeltas
        self._parsed_due_datetime_cache: dict[str, datetime | None] = {}
        self._offset_cache: dict[
            str,
            tuple[str | None, str | None, timedelta | None, timedelta | None],
        ] = {}
        self._max_due_cache_entries = 2048

    async def async_setup(self) -> None:
        """Set up the ChoreManager.

        Subscribes to:
        - DATA_READY: Startup initialization (recalculate stats) → emit CHORES_READY
        - KID_DELETED: Remove orphaned assignments
        - MIDNIGHT_ROLLOVER: Recurring resets and overdue checks (nightly)
        - PERIODIC_UPDATE: Due window transitions and reminders (5-min interval)
        """
        # Listen for startup cascade - DATA_READY triggers initialization
        self.listen(const.SIGNAL_SUFFIX_DATA_READY, self._on_data_ready)

        # Listen for kid deletion to remove orphaned assignments
        self.listen(const.SIGNAL_SUFFIX_KID_DELETED, self._on_kid_deleted)

        # Listen for midnight rollover to perform nightly tasks
        self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)

        # Listen for periodic updates to perform interval maintenance
        self.listen(const.SIGNAL_SUFFIX_PERIODIC_UPDATE, self._on_periodic_update)

        # Phase 3: Invalidate time-scan caches on data mutation signals
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_CREATED, self._on_time_scan_inputs_changed
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_UPDATED, self._on_time_scan_inputs_changed
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_DELETED, self._on_time_scan_inputs_changed
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_RESCHEDULED, self._on_time_scan_inputs_changed
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_STATUS_RESET, self._on_time_scan_inputs_changed
        )
        self.listen(const.SIGNAL_SUFFIX_KID_UPDATED, self._on_time_scan_inputs_changed)
        self.listen(const.SIGNAL_SUFFIX_KID_DELETED, self._on_time_scan_inputs_changed)

        const.LOGGER.debug("ChoreManager initialized for entry %s", self.entry_id)

    def _clear_time_scan_caches(self) -> None:
        """Clear cached derived values used by process_time_checks."""
        self._parsed_due_datetime_cache.clear()
        self._offset_cache.clear()

    async def _on_time_scan_inputs_changed(
        self, payload: dict[str, Any] | None = None
    ) -> None:
        """Invalidate time-scan caches when chore scheduling inputs change."""
        self._clear_time_scan_caches()

    def _parse_due_datetime_cached(self, due_str: str | None) -> datetime | None:
        """Parse due datetime once per unique ISO string and reuse thereafter."""
        if not due_str:
            return None

        if due_str in self._parsed_due_datetime_cache:
            return self._parsed_due_datetime_cache[due_str]

        parsed = dt_to_utc(due_str)
        self._parsed_due_datetime_cache[due_str] = parsed

        if len(self._parsed_due_datetime_cache) > self._max_due_cache_entries:
            self._parsed_due_datetime_cache.clear()

        return parsed

    def _get_chore_offsets_cached(
        self,
        chore_id: str,
        chore_info: dict[str, Any],
    ) -> tuple[timedelta | None, timedelta | None]:
        """Return parsed due window/reminder offsets with per-chore caching."""
        due_window_offset_str = cast(
            "str | None",
            chore_info.get(
                const.DATA_CHORE_DUE_WINDOW_OFFSET,
                const.DEFAULT_DUE_WINDOW_OFFSET,
            ),
        )
        reminder_offset_str = cast(
            "str | None",
            chore_info.get(
                const.DATA_CHORE_DUE_REMINDER_OFFSET,
                const.DEFAULT_DUE_REMINDER_OFFSET,
            ),
        )

        cached = self._offset_cache.get(chore_id)
        if (
            cached is not None
            and cached[0] == due_window_offset_str
            and cached[1] == reminder_offset_str
        ):
            return cached[2], cached[3]

        due_window_offset = dt_parse_duration(due_window_offset_str)
        reminder_offset = dt_parse_duration(reminder_offset_str)
        self._offset_cache[chore_id] = (
            due_window_offset_str,
            reminder_offset_str,
            due_window_offset,
            reminder_offset,
        )
        return due_window_offset, reminder_offset

    def _track_state_modification(self, kid_id: str, chore_id: str) -> None:
        """Track state modification for guard rail assertion (debug mode).

        Phase 4 Guard Rail: Ensures single state change per (kid_id, chore_id)
        per pipeline tick. Logs warning if same pair modified twice.

        Args:
            kid_id: Kid identifier
            chore_id: Chore identifier
        """
        if not const.DEBUG_PIPELINE_GUARDS:
            return

        pair = (kid_id, chore_id)
        if pair in self._pipeline_modified_pairs:
            const.LOGGER.warning(
                "GUARD RAIL VIOLATION: (kid=%s, chore=%s) modified TWICE in single tick. "
                "This violates the 'single state per tick' invariant.",
                kid_id,
                chore_id,
            )
        self._pipeline_modified_pairs.add(pair)

    def _reset_pipeline_tracking(self) -> None:
        """Reset pipeline modification tracking at start of new tick (debug mode).

        Phase 4 Guard Rail: Call at start of midnight_rollover and periodic_update.
        """
        if const.DEBUG_PIPELINE_GUARDS:
            self._pipeline_modified_pairs.clear()

    async def _on_data_ready(self, payload: dict[str, Any]) -> None:
        """Handle startup initialization after data integrity is verified.

        Cascade Position: DATA_READY → ChoreManager → CHORES_READY

        Time-based checks (overdue, due-window, reminders) are deferred to
        first periodic update when notifier and stats managers are ready.

        Args:
            payload: Event data (unused)
        """
        const.LOGGER.debug("ChoreManager: Processing DATA_READY")
        # Signal cascade continues - time checks run on first periodic update
        self.emit(const.SIGNAL_SUFFIX_CHORES_READY)

    async def _on_midnight_rollover(
        self,
        payload: dict[str, Any] | None = None,
        *,
        now_utc: datetime | None = None,
        trigger: str = const.CHORE_SCAN_TRIGGER_MIDNIGHT,
    ) -> int:
        """Handle midnight rollover - perform nightly chore maintenance.

        Follows Platinum Architecture (Choreography): ChoreManager reacts
        to MIDNIGHT_ROLLOVER signal and performs its own nightly tasks.

        Uses unified scanner (process_time_checks) with TRIGGER_MIDNIGHT
        to process AT_MIDNIGHT_* chores through same path as AT_DUE_DATE_*.

        Args:
            payload: Event data (unused, but required by signal handler signature)
            now_utc: Override current time (for testing). If None, uses utcnow().
            trigger: Scanner trigger type (for testing). Default "midnight".

        Returns:
            Number of chores processed.
        """
        const.LOGGER.debug("ChoreManager: Processing midnight rollover")
        if now_utc is None:
            now_utc = dt_util.utcnow()

        # Phase 4 Guard Rail: Reset modification tracking
        self._reset_pipeline_tracking()

        reset_count = 0
        state_modified = False

        try:
            # Single-pass scan with midnight trigger for AT_MIDNIGHT_* chores
            scan = self.process_time_checks(now_utc, trigger=trigger)

            # Phase A: Resets FIRST (returns count + set of reset pairs)
            reset_count, reset_pairs = await self._process_approval_reset_entries(
                scan, now_utc, trigger, persist=False
            )
            state_modified = reset_count > 0

            # Phase B: Overdue, EXCLUDING anything just reset
            filtered_overdue = [
                e
                for e in scan[const.CHORE_SCAN_RESULT_OVERDUE]
                if (
                    e[const.CHORE_SCAN_ENTRY_KID_ID],
                    e[const.CHORE_SCAN_ENTRY_CHORE_ID],
                )
                not in reset_pairs
            ]
            await self._process_overdue(filtered_overdue, now_utc, persist=False)
            state_modified = state_modified or len(filtered_overdue) > 0

            return reset_count
        except Exception:
            const.LOGGER.exception("ChoreManager: Error during midnight rollover")
            return 0
        finally:
            # Phase C: Critical - persist if ANY state was modified (prevents in-memory drift)
            # Even if Phase B failed, we must persist Phase A changes to avoid corruption.
            if state_modified:
                try:
                    self._coordinator._persist()
                    self._coordinator.async_set_updated_data(self._coordinator._data)
                except Exception:
                    const.LOGGER.exception(
                        "ChoreManager: Critical - failed to persist midnight changes"
                    )

    async def _on_periodic_update(
        self,
        payload: dict[str, Any] | None = None,
        *,
        now_utc: datetime | None = None,
        trigger: str = const.CHORE_SCAN_TRIGGER_DUE_DATE,
    ) -> int:
        """Handle periodic update - perform interval maintenance tasks.

        Follows Platinum Architecture (Choreography): ChoreManager reacts
        to PERIODIC_UPDATE signal and performs its own maintenance tasks.

        Called every ~5 minutes by Coordinator's update cycle.

        Performance Optimization (v0.5.0+):
        Uses consolidated single-pass scanner for ALL periodic checks:
        - Time-based: overdue, due_window, due_reminder notifications
        - Approval boundary: AT_DUE_DATE_* chore resets

        Previously: 2 full passes (approval_boundary + time_checks)
        Now: 1 pass categorizes everything

        Args:
            payload: Event data (unused, but required by signal handler signature)
            now_utc: Override current time (for testing). If None, uses utcnow().
            trigger: Scanner trigger type (for testing). Default "due_date".

        Returns:
            Number of approval resets processed.
        """
        # Phase 4 Guard Rail: Reset modification tracking
        self._reset_pipeline_tracking()

        reset_count = 0
        state_modified = False

        try:
            if now_utc is None:
                now_utc = dt_util.utcnow()

            # Single-pass scan categorizes ALL actionable items
            scan = self.process_time_checks(now_utc, trigger=trigger)

            # Phase A: Resets FIRST
            reset_count, reset_pairs = await self._process_approval_reset_entries(
                scan, now_utc, trigger, persist=False
            )
            state_modified = reset_count > 0

            # Phase B: Overdue, EXCLUDING anything just reset
            filtered_overdue = [
                e
                for e in scan["overdue"]
                if (e["kid_id"], e["chore_id"]) not in reset_pairs
            ]
            await self._process_overdue(filtered_overdue, now_utc, persist=False)
            state_modified = state_modified or len(filtered_overdue) > 0

            # Phase C: Notifications (read-only, no persist needed)
            self._process_due_window(scan[const.CHORE_SCAN_RESULT_IN_DUE_WINDOW])
            self._process_due_reminder(scan[const.CHORE_SCAN_RESULT_DUE_REMINDER])

            return reset_count
        except Exception:
            const.LOGGER.exception("ChoreManager: Error during periodic update")
            return 0
        finally:
            # Phase D: Critical - persist if ANY state was modified (prevents in-memory drift)
            # Even if Phase B or C failed, we must persist Phase A changes to avoid corruption.
            if state_modified:
                try:
                    self._coordinator._persist()
                    self._coordinator.async_set_updated_data(self._coordinator._data)
                except Exception:
                    const.LOGGER.exception(
                        "ChoreManager: Critical - failed to persist periodic changes"
                    )
            else:
                # Refresh listeners even when no storage changed so time-derived
                # FSM states (waiting/due/pending) are re-evaluated.
                self._coordinator.async_set_updated_data(self._coordinator._data)

    def _on_kid_deleted(self, payload: dict[str, Any]) -> None:
        """Remove deleted kid from all chore assignments.

        Follows Platinum Architecture (Choreography): ChoreManager reacts
        to KID_DELETED signal and cleans its own domain data (chore assignments).

        Args:
            payload: Event data containing kid_id
        """
        kid_id = payload.get("kid_id", "")
        if not kid_id:
            return

        # Clean own domain: remove deleted kid from chore assigned_kids
        cleaned = False
        chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
        for _, chore_info in chores_data.items():
            assigned_kids = chore_info.get(const.DATA_ASSIGNED_KIDS, [])
            if kid_id in assigned_kids:
                chore_info[const.DATA_ASSIGNED_KIDS] = [
                    k for k in assigned_kids if k != kid_id
                ]
                const.LOGGER.debug(
                    "Removed deleted kid %s from chore '%s' assigned_kids",
                    kid_id,
                    chore_info.get(const.DATA_CHORE_NAME),
                )
                cleaned = True

                # Phase 3 Step 6: Handle rotation resilience (D-06 resilience)
                # If deleted kid was the current turn-holder, reassign to first remaining kid
                if ChoreEngine.is_rotation_mode(chore_info):
                    current_turn_holder = chore_info.get(
                        const.DATA_CHORE_ROTATION_CURRENT_KID_ID
                    )
                    if current_turn_holder == kid_id:
                        remaining_kids = chore_info.get(const.DATA_ASSIGNED_KIDS, [])
                        if remaining_kids:
                            # Reassign to first remaining kid
                            chore_info[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = (
                                remaining_kids[0]
                            )
                            const.LOGGER.debug(
                                "Rotation resilience: Reassigned turn from deleted kid %s to %s for chore '%s'",
                                kid_id,
                                remaining_kids[0],
                                chore_info.get(const.DATA_CHORE_NAME),
                            )
                        else:
                            # No kids left - clear rotation metadata
                            chore_info[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = None
                            chore_info[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False
                            const.LOGGER.debug(
                                "Rotation resilience: Cleared rotation metadata for chore '%s' (no kids remaining)",
                                chore_info.get(const.DATA_CHORE_NAME),
                            )

            # Clean up per-kid data structures
            per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
                cleaned = True

            per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
            if kid_id in per_kid_days:
                del per_kid_days[kid_id]
                cleaned = True

            per_kid_multi = chore_info.get(
                const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {}
            )
            if kid_id in per_kid_multi:
                del per_kid_multi[kid_id]
                cleaned = True

        if cleaned:
            self._coordinator._persist()
            const.LOGGER.debug(
                "ChoreManager: Cleaned chore assignments for deleted kid %s",
                kid_id,
            )

    # =========================================================================
    # §1 WORKFLOW METHODS
    # =========================================================================

    async def claim_chore(
        self,
        kid_id: str,
        chore_id: str,
        user_name: str,
    ) -> None:
        """Process a chore claim request with race condition protection.

        Uses asyncio.Lock to ensure only one claim processes at a time
        per kid+chore combination, preventing duplicate claims.

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            user_name: Who initiated the claim (for notification context)

        Raises:
            HomeAssistantError: If claim validation fails
        """
        # Acquire lock for this kid+chore pair
        lock = self._get_lock(kid_id, chore_id)
        async with lock:
            await self._claim_chore_locked(kid_id, chore_id, user_name)

    async def _claim_chore_locked(
        self,
        kid_id: str,
        chore_id: str,
        user_name: str,
    ) -> None:
        """Internal claim logic executed under lock protection.

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            user_name: Who initiated the claim (for notification context)

        Raises:
            HomeAssistantError: If claim validation fails
        """
        # Validate entities exist
        self._validate_kid_and_chore(kid_id, chore_id)

        # Landlord duty: Ensure periods structures exist before statistics writes
        self._ensure_kid_structures(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        chore_name = chore_data.get(const.DATA_CHORE_NAME, "")

        # Validate assignment
        if kid_id not in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            kid_name = kid_info.get(const.DATA_KID_NAME, "")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                translation_placeholders={"entity": chore_name, "kid": kid_name},
            )

        # Get validation inputs for engine
        has_pending = ChoreEngine.chore_has_pending_claim(kid_chore_data)
        is_approved = self.chore_is_approved_in_period(kid_id, chore_id)

        # v0.5.0 FSM integration: Calculate resolved state for rotation/due window blocking
        due_date = self.get_due_date(chore_id, kid_id)
        due_window_start = self.get_due_window_start(chore_id, kid_id)
        resolved_state, lock_reason = ChoreEngine.resolve_kid_chore_state(
            chore_data=chore_data,
            kid_id=kid_id,
            due_date=due_date,
            due_window_start=due_window_start,
            has_pending_claim=has_pending,
            is_approved_in_period=is_approved,
            now=dt_util.now(),
        )

        # For SHARED_FIRST, collect other kids' states for blocking check
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        other_kid_states = None
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            other_kid_states = {}
            for other_kid_id in kids_assigned:
                if other_kid_id != kid_id and other_kid_id:
                    other_kid_chore_data = self._get_kid_chore_data(
                        other_kid_id, chore_id
                    )
                    other_kid_states[other_kid_id] = other_kid_chore_data.get(
                        const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
                    )

        # Delegate validation to engine (stateless pure logic with FSM state)
        can_claim, error_key = ChoreEngine.can_claim_chore(
            kid_chore_data=kid_chore_data,
            chore_data=chore_data,
            has_pending_claim=has_pending,
            is_approved_in_period=is_approved,
            other_kid_states=other_kid_states,
            resolved_state=resolved_state,
            lock_reason=lock_reason,
        )

        if not can_claim:
            lock_reason_error_map = {
                const.CHORE_STATE_WAITING: const.TRANS_KEY_ERROR_CHORE_WAITING,
                const.CHORE_STATE_NOT_MY_TURN: const.TRANS_KEY_ERROR_CHORE_NOT_MY_TURN,
                const.CHORE_STATE_MISSED: const.TRANS_KEY_ERROR_CHORE_MISSED_LOCKED,
            }
            normalized_error_key = (
                lock_reason_error_map.get(error_key, error_key)
                if error_key is not None
                else None
            )

            if normalized_error_key in (
                const.TRANS_KEY_ERROR_CHORE_WAITING,
                const.TRANS_KEY_ERROR_CHORE_NOT_MY_TURN,
                const.TRANS_KEY_ERROR_CHORE_MISSED_LOCKED,
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=normalized_error_key,
                )
            if error_key == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER:
                claimed_by = kid_chore_data.get(
                    const.DATA_CHORE_CLAIMED_BY, "another kid"
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_CLAIMED_BY_OTHER,
                    translation_placeholders={"claimed_by": str(claimed_by)},
                )
            if error_key == const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM,
                    translation_placeholders={"entity": chore_name},
                )
            if error_key == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED:
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED,
                )
            # Default: already approved
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_ALREADY_CLAIMED,
                translation_placeholders={"entity": chore_name},
            )

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Calculate state transitions
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_CLAIM,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        # Apply effects to coordinator data
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Set last_claimed timestamp for the claiming kid
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = dt_now_iso()

        # Update global chore state
        self._update_global_state(chore_id)

        # Increment pending claim counter
        self._increment_pending_count(kid_id, chore_id)

        # Check auto-approve
        auto_approve = chore_data.get(
            const.DATA_CHORE_AUTO_APPROVE, const.DEFAULT_CHORE_AUTO_APPROVE
        )
        if auto_approve:
            # Atomic: call locked impl directly (already inside lock)
            await self._approve_chore_locked(
                "auto_approve",
                kid_id,
                chore_id,
                approval_origin=const.CHORE_APPROVAL_ORIGIN_AUTO_APPROVE,
            )
            # _approve_chore_locked already persisted; skip our persist
        else:
            # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
            self._coordinator._persist_and_update()

        # Emit event for notification system
        # StatisticsManager._on_chore_claimed handles cache refresh and entity notification
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_CLAIMED,
            kid_id=kid_id,
            chore_id=chore_id,
            kid_name=kid_name,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            user_name=user_name,
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
            update_stats=True,
        )

        const.LOGGER.debug(
            "Claim processed: kid=%s chore=%s user=%s",
            kid_id,
            chore_id,
            user_name,
        )

    async def approve_chore(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        points_override: float | None = None,
    ) -> None:
        """Approve a chore with race condition protection.

        Uses asyncio.Lock to ensure only one approval processes at a time
        per kid+chore combination.

        Args:
            parent_name: Who is approving (for audit and notification)
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            points_override: Optional override for points (future feature)
        """
        # Acquire lock for this kid+chore pair
        lock = self._get_lock(kid_id, chore_id)
        async with lock:
            await self._approve_chore_locked(
                parent_name,
                kid_id,
                chore_id,
                points_override,
                approval_origin=const.CHORE_APPROVAL_ORIGIN_MANUAL,
            )

    async def _approve_chore_locked(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        points_override: float | None = None,
        approval_origin: str = const.CHORE_APPROVAL_ORIGIN_MANUAL,
    ) -> None:
        """Approve chore implementation (called inside lock).

        Args:
            parent_name: Who is approving
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            points_override: Optional point override
            approval_origin: Source of approval (manual, auto_approve, auto_reset)
        """
        # Validate entities exist
        self._validate_kid_and_chore(kid_id, chore_id)

        # Landlord duty: Ensure periods structures exist before statistics writes
        self._ensure_kid_structures(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Get previous state for event payload
        previous_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Get validation inputs
        is_approved = self.chore_is_approved_in_period(kid_id, chore_id)

        # Re-validate inside lock (race condition protection)
        can_approve, error_key = ChoreEngine.can_approve_chore(
            kid_chore_data=kid_chore_data,
            chore_data=chore_data,
            is_approved_in_period=is_approved,
        )

        if not can_approve:
            # Race condition: another parent already approved
            const.LOGGER.info(
                "Race condition prevented: chore '%s' for kid '%s' already processed",
                chore_data.get(const.DATA_CHORE_NAME),
                kid_info.get(const.DATA_KID_NAME),
            )
            return  # Graceful exit - expected behavior

        # Calculate points
        base_points = points_override or float(
            chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
        )
        multiplier = float(kid_info.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0))
        points_to_award = ChoreEngine.calculate_points(chore_data, multiplier)

        # Use override if specified
        if points_override is not None:
            points_to_award = round(
                points_override * multiplier, const.DATA_FLOAT_PRECISION
            )

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # =====================================================================
        # CAPTURE OLD STATE (Required for streak calculation)
        # Must happen BEFORE applying effects or updating timestamps
        # =====================================================================

        # Get previous last_completed for streak calculation (parent-lag-proof)
        previous_last_completed = self.get_chore_last_completed(chore_id, kid_id)

        # Check if this is a direct approval (no pending claim)
        # Used to set claim fields for consistency
        has_pending_claim = self.chore_has_pending_claim(kid_id, chore_id)

        # Get previous streak from last completion date (schedule-aware)
        # For weekly/biweekly chores, yesterday won't have data - must use last_completed date
        # =====================================================================
        # GET PREVIOUS STREAK VALUES FROM CHORE DATA (NOT DAILY BUCKETS)
        # =====================================================================
        # Phase 5 Fix: Read from chore data level to survive retention pruning
        # (daily buckets only retained for 7 days, breaks weekly/monthly streaks)
        previous_streak = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_CURRENT_STREAK, 0
        )

        # Calculate effects
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_APPROVE,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        # Apply effects
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # =====================================================================
        # UPDATE TIMESTAMPS AND CALCULATE STREAK
        # =====================================================================
        now_iso = dt_now_iso()

        # Calculate completion streak using schedule-aware logic
        # This checks if any scheduled occurrences were missed between completions
        previous_last_completed = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_COMPLETED
        )
        work_date_iso = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_CLAIMED, now_iso
        )
        new_streak = ChoreEngine.calculate_streak(
            current_streak=previous_streak,
            previous_last_completed_iso=previous_last_completed,
            current_work_date_iso=work_date_iso,
            chore_data=chore_data,
        )

        # Store new completion streak at chore data level (survives retention)
        kid_chore_data[const.DATA_KID_CHORE_DATA_CURRENT_STREAK] = new_streak

        # Reset missed streak to 0 on completion (completion breaks missed streak)
        kid_chore_data[const.DATA_KID_CHORE_DATA_CURRENT_MISSED_STREAK] = 0

        # Set last_approved timestamp (audit/financial timestamp)
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_APPROVED] = now_iso

        # If no pending claim existed, this is a direct approval
        # Set claim fields to match approval (combined claim+approve action)
        if not has_pending_claim:
            kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_CLAIMED] = now_iso
            kid_chore_data[const.DATA_CHORE_CLAIMED_BY] = kid_name

        # Extract effective_date (when kid did the work) for statistics/scheduling
        # Fallback hierarchy: last_claimed → last_approved → now_iso
        effective_date_iso = (
            kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
            or kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
            or now_iso
        )

        # Calculate streak using schedule-aware logic (parent-lag-proof)
        # Uses last_completed (work date) not last_approved (parent action date)
        # Phase 5 Change: Store result at chore data level (survives retention pruning)
        new_streak = ChoreEngine.calculate_streak(
            current_streak=previous_streak,
            previous_last_completed_iso=previous_last_completed,
            current_work_date_iso=effective_date_iso,
            chore_data=chore_data,
        )

        # Store current streak at chore data level (never pruned)
        kid_chore_data[const.DATA_KID_CHORE_DATA_CURRENT_STREAK] = new_streak

        # Reset missed streak to 0 on completion (failure chain broken)
        kid_chore_data[const.DATA_KID_CHORE_DATA_CURRENT_MISSED_STREAK] = 0

        # Update global chore state
        self._update_global_state(chore_id)

        # Set last_completed timestamp (always runs on approval)
        # Stored per completion criteria: INDEPENDENT in kid data, SHARED at chore level
        self._set_last_completed_timestamp(
            chore_id, kid_id, effective_date_iso, now_iso
        )

        # Decrement pending count
        self._decrement_pending_count(kid_id, chore_id)

        # Set completed_by based on completion criteria
        self._handle_completion_criteria(chore_id, kid_id, kid_name)

        # Handle UPON_COMPLETION reset type: immediately reset to PENDING
        # Other reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*) stay APPROVED until
        # scheduled reset
        # EXCEPTION: immediate_on_late option resets to PENDING when approval is late
        approval_reset = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        overdue_handling = chore_data.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        )

        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        all_kids_approved = completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
        if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
            all_kids_approved = self._all_kids_approved(chore_id, kids_assigned)

        approval_context = self._build_reset_context(
            trigger=const.CHORE_RESET_TRIGGER_APPROVAL,
            approval_reset_type=approval_reset,
            overdue_handling_type=overdue_handling,
            completion_criteria=completion_criteria,
            all_kids_approved=all_kids_approved,
            approval_after_reset=self._is_chore_approval_after_reset(
                chore_data, kid_id
            ),
        )
        reset_decision = self._decide_reset_action(approval_context)
        should_reset_immediately = reset_decision != const.CHORE_RESET_DECISION_HOLD

        if should_reset_immediately:
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                self._apply_reset_action(
                    {
                        "kid_id": kid_id,
                        "chore_id": chore_id,
                        "decision": reset_decision,
                        "reschedule_kid_id": kid_id,
                    }
                )
                self._update_global_state(chore_id)

            elif all_kids_approved:
                # Set chore-level approval_period_start ONCE for SHARED/SHARED_FIRST
                # Use FRESH timestamp to ensure it's AFTER last_approved
                reset_period_start = dt_now_iso()
                chore_data[const.DATA_CHORE_APPROVAL_PERIOD_START] = reset_period_start
                for assigned_kid_id in kids_assigned:
                    if assigned_kid_id:
                        self._apply_reset_action(
                            {
                                "kid_id": assigned_kid_id,
                                "chore_id": chore_id,
                                "decision": reset_decision,
                                "reschedule_kid_id": None,
                                "allow_reschedule": False,
                            }
                        )
                self._update_global_state(chore_id)
                if reset_decision == const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE:
                    self._reschedule_chore_due(chore_id)

        # === NON-RECURRING PAST-DUE GUARD (Phase 1) ===
        # For FREQUENCY_NONE chores that just reset via UPON_COMPLETION:
        # Clear the past due date so the next scan doesn't immediately re-overdue.
        # The chore stays PENDING indefinitely until user sets a new due date.
        if should_reset_immediately:
            frequency = chore_data.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            )
            if frequency == const.FREQUENCY_NONE:
                completion_criteria = chore_data.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA,
                    const.COMPLETION_CRITERIA_INDEPENDENT,
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # Clear per-kid due date
                    per_kid_dates = chore_data.get(
                        const.DATA_CHORE_PER_KID_DUE_DATES, {}
                    )
                    per_kid_dates.pop(kid_id, None)
                else:
                    # Clear chore-level due date (SHARED/SHARED_FIRST)
                    chore_data.pop(const.DATA_CHORE_DUE_DATE, None)

                const.LOGGER.debug(
                    "Cleared past due date for non-recurring chore %s "
                    "after UPON_COMPLETION reset (prevents re-overdue)",
                    chore_id,
                )

        # For non-UPON_COMPLETION reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*):
        # Do NOT set approval_period_start here. It is ONLY set on RESET events.
        # The chore remains approved until the scheduled reset updates approval_period_start.
        # approval_period_start was set at: initial creation, or last reset.
        # last_approved was just set above, so:
        #   is_approved = (last_approved >= approval_period_start) = True

        # Determine if shared/multi-claim for event payload
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )
        is_shared = completion_criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        )
        is_multi_claim = ChoreEngine.chore_allows_multiple_claims(chore_data)

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist_and_update()

        # Emit approval event - EconomyManager listens and handles point deposit
        # (Platinum Architecture: signal-first, no cross-manager writes)
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_APPROVED,
            kid_id=kid_id,
            kid_name=kid_name,
            chore_id=chore_id,
            parent_name=parent_name,
            base_points=base_points,  # EconomyManager applies multiplier
            apply_multiplier=True,
            points_awarded=points_to_award,  # For UI/logging (already calculated)
            is_shared=is_shared,
            is_multi_claim=is_multi_claim,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
            multiplier_applied=multiplier,
            previous_state=previous_state,
            update_stats=True,
            effective_date=effective_date_iso,
            approval_origin=approval_origin,
            notify_kid=True,
        )

        # Emit completion event based on completion criteria
        # - INDEPENDENT: Kid completed their own chore (immediate)
        # - SHARED_FIRST: Only the approving kid gets completion credit (immediate)
        # - SHARED (all): All kids get credit when last kid is approved
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # Independent: approving kid completed their chore
            self.emit(
                const.SIGNAL_SUFFIX_CHORE_COMPLETED,
                chore_id=chore_id,
                kid_ids=[kid_id],
                effective_date=effective_date_iso,
                streak_tallies={kid_id: new_streak},
            )
        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Shared first: only the kid who did the work gets completion credit
            self.emit(
                const.SIGNAL_SUFFIX_CHORE_COMPLETED,
                chore_id=chore_id,
                kid_ids=[kid_id],
                effective_date=effective_date_iso,
                streak_tallies={kid_id: new_streak},
            )
        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            # Shared (all): only emit when ALL assigned kids have been approved
            if self._all_kids_approved(chore_id, kids_assigned):
                # Calculate streak for each kid
                streak_tallies = {}
                for assigned_kid_id in kids_assigned:
                    if not assigned_kid_id:
                        continue
                    # Get kid's chore_data and yesterday's streak
                    assigned_kid_info = self._coordinator.kids_data.get(assigned_kid_id)
                    if not assigned_kid_info:
                        continue
                    kid_chore_dict: dict[str, Any] = assigned_kid_info.get(
                        const.DATA_KID_CHORE_DATA, {}
                    )
                    assigned_chore_data = kid_chore_dict.get(chore_id, {})
                    assigned_periods = assigned_chore_data.get(
                        const.DATA_KID_CHORE_DATA_PERIODS, {}
                    )
                    assigned_daily = assigned_periods.get(
                        const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {}
                    )
                    assigned_last_completed = assigned_chore_data.get(
                        const.DATA_KID_CHORE_DATA_LAST_COMPLETED
                    )
                    # Get streak from last completion date (not yesterday - schedule-aware!)
                    assigned_previous_streak = 0
                    if assigned_last_completed:
                        # Convert UTC timestamp to local timezone for bucket lookup
                        assigned_local_dt = dt_parse(
                            assigned_last_completed,
                            return_type=HELPER_RETURN_DATETIME_LOCAL,
                        )
                        if assigned_local_dt and isinstance(
                            assigned_local_dt, datetime
                        ):
                            assigned_date_key = assigned_local_dt.date().isoformat()
                            assigned_last_data = assigned_daily.get(
                                assigned_date_key, {}
                            )
                            assigned_previous_streak = assigned_last_data.get(
                                const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY, 0
                            )
                    # Calculate streak for this kid
                    assigned_streak = ChoreEngine.calculate_streak(
                        current_streak=assigned_previous_streak,
                        previous_last_completed_iso=assigned_last_completed,
                        current_work_date_iso=effective_date_iso,
                        chore_data=chore_data,
                    )
                    streak_tallies[assigned_kid_id] = assigned_streak

                self.emit(
                    const.SIGNAL_SUFFIX_CHORE_COMPLETED,
                    chore_id=chore_id,
                    kid_ids=kids_assigned,
                    effective_date=effective_date_iso,
                    streak_tallies=streak_tallies,
                )

        # StatisticsManager handles cache refresh and entity notification via signal handlers

        const.LOGGER.debug(
            "Approval processed: kid=%s chore=%s points=%.2f by=%s",
            kid_id,
            chore_id,
            points_to_award,
            parent_name,
        )

    async def disapprove_chore(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        reason: str | None = None,
    ) -> None:
        """Disapprove a chore (return to pending state).

        Args:
            parent_name: Who is disapproving (for audit)
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            reason: Optional reason for disapproval
        """
        lock = self._get_lock(kid_id, chore_id)
        async with lock:
            await self._disapprove_chore_locked(parent_name, kid_id, chore_id, reason)

    async def _disapprove_chore_locked(
        self,
        parent_name: str,
        kid_id: str,
        chore_id: str,
        reason: str | None = None,
    ) -> None:
        """Disapprove chore implementation (called inside lock).

        Args:
            parent_name: Who is disapproving
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            reason: Optional disapproval reason
        """
        self._validate_kid_and_chore(kid_id, chore_id)

        # Landlord duty: Ensure periods structures exist before statistics writes
        self._ensure_kid_structures(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        previous_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Check if chore is past its due date (not just if state is overdue)
        # Use same logic as overdue scan: due_date exists and now > due_date
        due_date = self.get_due_date(chore_id, kid_id)
        is_past_due = False
        if due_date:
            now_utc = dt_util.utcnow()
            is_past_due = (due_date - now_utc).total_seconds() < 0

        # Calculate effects
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_DISAPPROVE,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
            is_overdue=is_past_due,
        )

        # Apply effects
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Update global chore state to reflect per-kid state changes
        self._update_global_state(chore_id)

        self._decrement_pending_count(kid_id, chore_id)

        # Set last_disapproved timestamp for the disapproved kid
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_DISAPPROVED] = dt_now_iso()

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist_and_update()

        # Emit disapproval event
        # StatisticsManager._on_chore_disapproved handles cache refresh and entity notification
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_DISAPPROVED,
            kid_id=kid_id,
            kid_name=kid_name,
            chore_id=chore_id,
            parent_name=parent_name,
            reason=reason,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
            previous_state=previous_state,
            update_stats=True,
        )

        const.LOGGER.debug(
            "Disapproval processed: kid=%s chore=%s by=%s reason=%s",
            kid_id,
            chore_id,
            parent_name,
            reason or "none",
        )

    async def undo_chore(
        self,
        kid_id: str,
        chore_id: str,
        parent_name: str,
    ) -> None:
        """Undo a chore approval (reclaim points, reset state).

        Args:
            kid_id: The internal UUID of the kid
            chore_id: The internal UUID of the chore
            parent_name: Who is undoing (for audit)
        """
        self._validate_kid_and_chore(kid_id, chore_id)

        # Landlord duty: Ensure periods structures exist before statistics writes
        self._ensure_kid_structures(kid_id, chore_id)

        chore_data = self._coordinator.chores_data[chore_id]
        kid_info = self._coordinator.kids_data[kid_id]
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Get kid name for effects
        kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
        kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Get previous points to reclaim from periods.all_time.points (v43+ canonical source)
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        all_time_bucket = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
        all_time_entry = all_time_bucket.get(const.PERIOD_ALL_TIME, {})
        previous_points = all_time_entry.get(
            const.DATA_KID_CHORE_DATA_PERIOD_POINTS, 0.0
        )

        # Calculate effects with skip_stats=True (undo doesn't count for stats)
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_UNDO,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
            skip_stats=True,
        )

        # Apply effects
        for effect in effects:
            self._apply_effect(effect, chore_id)

        # Update global chore state
        self._update_global_state(chore_id)

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist_and_update()

        # Emit undo signal - EconomyManager listens and handles point withdrawal
        # (Platinum Architecture: signal-first, no cross-manager writes)
        # StatisticsManager._on_chore_undone handles cache refresh and entity notification
        if previous_points > 0:
            self.emit(
                const.SIGNAL_SUFFIX_CHORE_UNDONE,
                kid_id=kid_id,
                chore_id=chore_id,
                points_to_reclaim=previous_points,
            )

        const.LOGGER.info(
            "Chore undone: chore=%s kid=%s by=%s points_reclaimed=%.2f",
            chore_data.get(const.DATA_CHORE_NAME),
            kid_info.get(const.DATA_KID_NAME),
            parent_name,
            previous_points,
        )

    async def undo_claim(self, kid_id: str, chore_id: str) -> None:
        """Allow kid to undo their own chore claim (no stat tracking).

        This provides a way for kids to remove their claim without counting
        as a disapproval. Does NOT track stats and does NOT send notifications.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

        # Decrement pending_count
        kid_chore_entry = self._get_kid_chore_data(kid_id, chore_id)
        current_count = kid_chore_entry.get(
            const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        kid_chore_entry[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current_count - 1
        )

        # Check if chore is past its due date (same logic as parent disapproval)
        # Use same logic as overdue scan: due_date exists and now > due_date
        due_date = self.get_due_date(chore_id, kid_id)
        is_past_due = False
        if due_date:
            now_utc = dt_util.utcnow()
            is_past_due = (due_date - now_utc).total_seconds() < 0

        # Handle SHARED_FIRST: Reset ALL kids to pending
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            const.LOGGER.info(
                "SHARED_FIRST: Kid undo - resetting all kids to pending for chore '%s'",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            for other_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                # Use skip_stats via undo action through Engine
                effects = ChoreEngine.calculate_transition(
                    chore_data=chore_info,
                    actor_kid_id=other_kid_id,
                    action=CHORE_ACTION_UNDO,
                    kids_assigned=chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []),
                    skip_stats=True,
                    is_overdue=is_past_due,
                )
                for effect in effects:
                    self._apply_effect(effect, chore_id)
                # Clear claimed_by/completed_by using helper
                other_kid_info: KidData | dict[str, Any] = (
                    self._coordinator.kids_data.get(other_kid_id, {})
                )
                other_kid_chore = ChoreEngine.get_chore_data_for_kid(
                    other_kid_info, chore_id
                )
                if other_kid_chore:
                    other_kid_chore.pop(const.DATA_CHORE_CLAIMED_BY, None)
                    other_kid_chore.pop(const.DATA_CHORE_COMPLETED_BY, None)
        else:
            # Normal: only reset the kid who is undoing
            effects = ChoreEngine.calculate_transition(
                chore_data=chore_info,
                actor_kid_id=kid_id,
                action=CHORE_ACTION_UNDO,
                kids_assigned=chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []),
                skip_stats=True,
                is_overdue=is_past_due,
            )
            for effect in effects:
                self._apply_effect(effect, chore_id)

        # Update global state
        self._update_global_state(chore_id)

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        # Emit event for NotificationManager to clear parent claim notifications
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_CLAIM_UNDONE,
            kid_id=kid_id,
            chore_id=chore_id,
        )

    # =========================================================================
    # §2 TIME TRIGGER ACTIONS FOR DUE DATE AND APPROVAL RESET HANDLING
    # =========================================================================

    def _build_reset_context(
        self,
        *,
        trigger: ResetTrigger,
        approval_reset_type: str,
        overdue_handling_type: str,
        completion_criteria: str,
        all_kids_approved: bool = False,
        approval_after_reset: bool = False,
        boundary_category: ResetBoundaryCategory | None = None,
        has_pending_claim: bool = False,
        pending_claim_action: str = const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    ) -> ResetContext:
        """Build reset policy context from lane-specific inputs."""
        return {
            "trigger": trigger,
            "approval_reset_type": approval_reset_type,
            "overdue_handling_type": overdue_handling_type,
            "completion_criteria": completion_criteria,
            "all_kids_approved": all_kids_approved,
            "approval_after_reset": approval_after_reset,
            "boundary_category": boundary_category,
            "has_pending_claim": has_pending_claim,
            "pending_claim_action": pending_claim_action,
        }

    def _apply_reset_action(self, context: ResetApplyContext) -> None:
        """Apply reset side effects for a single kid/chore pair."""
        kid_id = context["kid_id"]
        chore_id = context["chore_id"]
        decision = context["decision"]
        reschedule_kid_id = context["reschedule_kid_id"]
        allow_reschedule = context.get("allow_reschedule", True)

        self._transition_chore_state(
            kid_id,
            chore_id,
            const.CHORE_STATE_PENDING,
            reset_approval_period=True,
            clear_ownership=True,
        )

        if (
            allow_reschedule
            and decision == const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE
        ):
            self._reschedule_chore_due(chore_id, reschedule_kid_id)

    def _finalize_reset_batch(
        self,
        *,
        persist: bool,
        reset_count: int,
        rotation_payloads: list[dict[str, Any]] | None,
    ) -> None:
        """Finalize reset batch with persist/update and deferred signal emit."""
        if not persist or reset_count <= 0:
            return

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        if rotation_payloads:
            for payload in rotation_payloads:
                self.emit(const.SIGNAL_SUFFIX_CHORE_ROTATION_ADVANCED, **payload)

    @staticmethod
    def _decide_reset_action(context: ResetContext) -> ResetDecision:
        """Decide reset action from shared policy context."""
        trigger = context.get("trigger")

        if trigger == const.CHORE_RESET_TRIGGER_APPROVAL:
            approval_reset_type = context.get("approval_reset_type")
            overdue_handling_type = context.get("overdue_handling_type")
            approval_after_reset = context.get("approval_after_reset", False)
            completion_criteria = context.get(
                "completion_criteria",
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )

            should_reset_immediately = False
            if approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION or (
                overdue_handling_type
                == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
                and approval_after_reset
            ):
                should_reset_immediately = True

            if not should_reset_immediately:
                return const.CHORE_RESET_DECISION_HOLD

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                return const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE

            if context.get("all_kids_approved", False):
                return const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE
            return const.CHORE_RESET_DECISION_HOLD

        boundary_category = context.get("boundary_category")
        if boundary_category is None or (
            boundary_category == const.CHORE_RESET_BOUNDARY_CATEGORY_HOLD
        ):
            return const.CHORE_RESET_DECISION_HOLD

        if context.get("has_pending_claim", False):
            pending_claim_action = context.get(
                "pending_claim_action",
                const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            )
            if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_HOLD:
                return const.CHORE_RESET_DECISION_HOLD
            if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE:
                return const.CHORE_RESET_DECISION_AUTO_APPROVE_PENDING

        if boundary_category == const.CHORE_RESET_BOUNDARY_CATEGORY_CLEAR_ONLY:
            return const.CHORE_RESET_DECISION_RESET_ONLY
        return const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE

    def process_time_checks(
        self, now_utc: datetime, trigger: str = const.CHORE_SCAN_TRIGGER_DUE_DATE
    ) -> dict[str, list[ChoreTimeEntry]]:
        """Single-pass scan of all chores, categorizing by time status.

        Performance Optimization: Instead of multiple iterations through
        all chores, this method does ONE pass and categorizes each
        (kid, chore) pair by all time-based concerns.

        Categories (time-based notifications - actionable chores only):
        - overdue: Past due date (needs overdue state transition)
        - in_due_window: Within due_window_offset of due date (notify entry)
        - due_reminder: Within reminder_offset of due date (notify soon)

        Categories (approval boundary resets - all states):
        - approval_reset_shared: SHARED/SHARED_FIRST chores past due
        - approval_reset_independent: INDEPENDENT chores with kids past due

        Args:
            now_utc: Current UTC datetime for comparison
            trigger: "due_date" (AT_DUE_DATE_*) or "midnight" (AT_MIDNIGHT_*)

        Returns:
            Dict with category keys mapping to lists of ChoreTimeEntry
        """
        result: dict[str, list[ChoreTimeEntry]] = {
            # Time-based notifications
            const.CHORE_SCAN_RESULT_OVERDUE: [],
            const.CHORE_SCAN_RESULT_IN_DUE_WINDOW: [],
            const.CHORE_SCAN_RESULT_DUE_REMINDER: [],
            # Approval boundary resets
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [],
        }

        for chore_id, chore_info in self._coordinator.chores_data.items():
            # Get assigned kids for this chore
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if not assigned_kids:
                continue

            # ─── CHORE-LEVEL CONFIG (once per chore) ───
            # Notification settings
            notify_due_window = chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW,
                const.DEFAULT_NOTIFY_ON_DUE_WINDOW,
            )
            notify_reminder = chore_info.get(
                const.DATA_CHORE_NOTIFY_DUE_REMINDER,
                const.DEFAULT_NOTIFY_DUE_REMINDER,
            )

            # Overdue handling
            overdue_handling = chore_info.get(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.OVERDUE_HANDLING_AT_DUE_DATE,
            )
            can_be_overdue = overdue_handling != const.OVERDUE_HANDLING_NEVER_OVERDUE

            # Parse offsets once per chore revision
            due_window_offset, reminder_offset = self._get_chore_offsets_cached(
                chore_id,
                cast("dict[str, Any]", chore_info),
            )

            # ─── APPROVAL BOUNDARY CONFIG (once per chore) ───
            approval_reset_type = chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            )
            should_process_reset = ChoreEngine.should_process_at_boundary(
                approval_reset_type, trigger
            )
            completion_criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            frequency = chore_info.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            )

            # ─── SHARED CHORE RESET CHECK (chore-level due_date) ───
            if should_process_reset and completion_criteria in (
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            ):
                # SHARED uses chore-level due_date
                # For AT_MIDNIGHT_*: Process if no due date OR past due date
                # For AT_DUE_DATE_*: Only process if past due date
                chore_due_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
                chore_due_utc = self._parse_due_datetime_cached(chore_due_str)

                # Determine if this chore should be included in reset scan
                include_in_reset = False
                if trigger == "midnight":
                    # AT_MIDNIGHT_*: Include if no due date OR past due date
                    # Future due dates mean the period hasn't started yet
                    if chore_due_utc is None or now_utc >= chore_due_utc:
                        include_in_reset = True
                elif chore_due_utc and now_utc >= chore_due_utc:
                    # AT_DUE_DATE_*: Include only if past due date
                    # Skip non-recurring past due (would immediately go OVERDUE)
                    if not (
                        frequency == const.FREQUENCY_NONE and now_utc > chore_due_utc
                    ):
                        include_in_reset = True

                if include_in_reset:
                    result[const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED].append(
                        {
                            const.CHORE_SCAN_ENTRY_CHORE_ID: chore_id,
                            const.CHORE_SCAN_ENTRY_CHORE_INFO: cast(
                                "dict[str, Any]", chore_info
                            ),
                            const.CHORE_SCAN_ENTRY_DUE_DT: chore_due_utc,
                        }
                    )

            # ─── KID ITERATION ───
            independent_reset_kids: list[dict[str, Any]] = []

            for kid_id in assigned_kids:
                if not kid_id:
                    continue

                # Get due date (single call per kid-chore pair)
                due_dt = self.get_due_date(chore_id, kid_id)

                # For time-based categorization, we need a due date
                if due_dt:
                    # Calculate time until due (negative = overdue)
                    time_until_due = due_dt - now_utc
                    is_past_due = time_until_due.total_seconds() < 0

                    # ─── TIME-BASED CATEGORIZATION (actionable chores only) ───
                    if self.chore_is_actionable(kid_id, chore_id):
                        entry: ChoreTimeEntry = {
                            const.CHORE_SCAN_ENTRY_CHORE_ID: chore_id,
                            const.CHORE_SCAN_ENTRY_KID_ID: kid_id,
                            const.CHORE_SCAN_ENTRY_DUE_DT: due_dt,
                            const.CHORE_SCAN_ENTRY_CHORE_INFO: cast(
                                "dict[str, Any]", chore_info
                            ),
                            const.CHORE_SCAN_ENTRY_TIME_UNTIL_DUE: time_until_due,
                        }

                        if is_past_due and can_be_overdue:
                            result[const.CHORE_SCAN_RESULT_OVERDUE].append(entry)
                        elif not is_past_due:
                            if (
                                notify_due_window
                                and due_window_offset
                                and time_until_due <= due_window_offset
                            ):
                                result[const.CHORE_SCAN_RESULT_IN_DUE_WINDOW].append(
                                    entry
                                )

                            if (
                                notify_reminder
                                and reminder_offset
                                and time_until_due <= reminder_offset
                            ):
                                result[const.CHORE_SCAN_RESULT_DUE_REMINDER].append(
                                    entry
                                )

                # ─── INDEPENDENT RESET CHECK (per-kid due_date) ───
                # For AT_MIDNIGHT_*: Include if no due date OR past due date
                # For AT_DUE_DATE_*: Only process if past due date
                if should_process_reset and completion_criteria in (
                    const.COMPLETION_CRITERIA_INDEPENDENT,
                    const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
                    const.COMPLETION_CRITERIA_ROTATION_SMART,
                ):
                    # Determine if this kid should be included in reset scan
                    include_kid_in_reset = False
                    if trigger == "midnight":
                        # AT_MIDNIGHT_*: Include if no due date OR past due date
                        # Future due dates mean the period hasn't started yet
                        if due_dt is None or now_utc >= due_dt:
                            include_kid_in_reset = True
                    elif due_dt:
                        # AT_DUE_DATE_*: Include only if past due date
                        is_past_due = (due_dt - now_utc).total_seconds() < 0
                        # Skip non-recurring past due (would immediately go OVERDUE)
                        if is_past_due and not (
                            frequency == const.FREQUENCY_NONE and now_utc > due_dt
                        ):
                            include_kid_in_reset = True

                    if include_kid_in_reset:
                        independent_reset_kids.append(
                            {
                                const.CHORE_SCAN_ENTRY_KID_ID: kid_id,
                                const.CHORE_SCAN_ENTRY_DUE_DT: due_dt,
                            }
                        )

            # ─── AGGREGATE INDEPENDENT APPROVAL RESETS ───
            if independent_reset_kids:
                result[const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT].append(
                    {
                        const.CHORE_SCAN_ENTRY_CHORE_ID: chore_id,
                        const.CHORE_SCAN_ENTRY_CHORE_INFO: cast(
                            "dict[str, Any]", chore_info
                        ),
                        "kids": independent_reset_kids,
                    }
                )

        const.LOGGER.debug(
            "Chore time scan: %d overdue, %d in_due_window, %d due_reminder, "
            "%d approval_reset_shared, %d approval_reset_independent",
            len(result[const.CHORE_SCAN_RESULT_OVERDUE]),
            len(result[const.CHORE_SCAN_RESULT_IN_DUE_WINDOW]),
            len(result[const.CHORE_SCAN_RESULT_DUE_REMINDER]),
            len(result[const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED]),
            len(result[const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT]),
        )

        return result

    async def _process_overdue(
        self,
        entries: list[ChoreTimeEntry],
        now_utc: datetime,
        *,
        persist: bool = True,
    ) -> None:
        """Process overdue entries - mark as overdue and emit signals.

        Inlines the mark_overdue() logic directly for single-pass efficiency.

        Phase 4: Idempotency guard - skip if already OVERDUE.

        Args:
            entries: List of ChoreTimeEntry for chores past due
            now_utc: Current UTC datetime
            persist: If True, persist changes immediately. If False, caller handles persist.
        """
        if not entries:
            return

        marked_count = 0
        skipped_already_overdue = 0
        skipped_already_overdue_chore_names: set[str] = set()
        # Accumulate signal data for batch emission after persist (Phase 1: Persist→Emit pattern)
        signals_to_emit: list[dict[str, Any]] = []

        for entry in entries:
            chore_id = entry["chore_id"]
            kid_id = entry["kid_id"]
            due_dt = entry["due_dt"]
            chore_info = entry["chore_info"]

            # Phase 4 Guard Rail: Idempotency - check current state before processing
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            current_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)

            if current_state == const.CHORE_STATE_OVERDUE:
                skipped_already_overdue += 1
                skipped_already_overdue_chore_names.add(
                    str(chore_info.get(const.DATA_CHORE_NAME, chore_id))
                )
                continue

            # Validate kid and chore exist
            try:
                self._validate_kid_and_chore(kid_id, chore_id)
            except HomeAssistantError as err:
                const.LOGGER.debug(
                    "Could not mark chore '%s' overdue for kid '%s': %s",
                    chore_info.get(const.DATA_CHORE_NAME, chore_id),
                    kid_id,
                    err,
                )
                continue

            # Landlord duty: Ensure periods structures exist before statistics writes
            self._ensure_kid_structures(kid_id, chore_id)

            # Get data for transition calculation
            chore_data = self._coordinator.chores_data[chore_id]
            kid_info = self._coordinator.kids_data[kid_id]
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

            # Phase 3 Step 2: Check for mark_missed_and_lock overdue handling
            overdue_handling = chore_data.get(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            )

            if (
                overdue_handling
                == const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
            ):
                # Lock the chore in MISSED state (not claimable)
                kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = (
                    const.CHORE_STATE_MISSED
                )
                self._update_global_state(chore_id)

                # Record missed stat (handles persist and signal emission)
                self._record_chore_missed(
                    kid_id, chore_id, due_date=due_dt, reason="strict_lock"
                )

                marked_count += 1
                continue  # Skip normal overdue processing
            # Calculate and apply state transition via Engine (normal overdue path)
            effects = ChoreEngine.calculate_transition(
                chore_data=chore_data,
                actor_kid_id=kid_id,
                action=CHORE_ACTION_OVERDUE,
                kids_assigned=kids_assigned,
                kid_name=kid_name,
            )

            for effect in effects:
                self._apply_effect(effect, chore_id)

            # Update global chore state
            self._update_global_state(chore_id)

            # Calculate days overdue and accumulate signal data
            days_overdue = (now_utc - due_dt).days
            signals_to_emit.append(
                {
                    "kid_id": kid_id,
                    "kid_name": kid_name,
                    "chore_id": chore_id,
                    "chore_name": chore_data.get(const.DATA_CHORE_NAME, ""),
                    "days_overdue": days_overdue,
                    "due_date": due_dt.isoformat(),
                    "chore_labels": chore_data.get(const.DATA_CHORE_LABELS, []),
                }
            )

            marked_count += 1

        if skipped_already_overdue:
            sample_names = sorted(skipped_already_overdue_chore_names)[:5]
            const.LOGGER.debug(
                "Overdue processing skip summary: %d already OVERDUE entries skipped across %d chores (sample: %s)",
                skipped_already_overdue,
                len(skipped_already_overdue_chore_names),
                ", ".join(sample_names),
            )

        if marked_count > 0:
            const.LOGGER.debug(
                "Processed %d overdue chore(s)",
                marked_count,
            )

        # === BATCH PERSIST (Phase 1) ===
        # Write once after all changes (O(n) → O(1) disk writes)
        if persist and marked_count > 0:
            self._coordinator._persist()
            self._coordinator.async_set_updated_data(self._coordinator._data)

        # === BATCH EMIT SIGNALS (Phase 1) ===
        # Emit signals AFTER persist to comply with Persist→Emit pattern
        # StatisticsManager._on_chore_overdue handles cache refresh and entity notification
        for signal_data in signals_to_emit:
            self.emit(const.SIGNAL_SUFFIX_CHORE_OVERDUE, **signal_data)

    def _process_due_window(self, entries: list[ChoreTimeEntry]) -> None:
        """Process due window entries and emit signals.

        Args:
            entries: List of ChoreTimeEntry for chores in due window
        """
        if not entries:
            return

        for entry in entries:
            chore_info = entry["chore_info"]
            time_until_due = entry["time_until_due"]
            hours_remaining = max(0, int(time_until_due.total_seconds() / 3600))

            kid_id = entry["kid_id"]
            chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown Chore")
            points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0)

            # Get kid name for signal emission
            kid_info: KidData = cast(
                "KidData", self._coordinator.kids_data.get(kid_id, {})
            )
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

            self.emit(
                const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW,
                kid_id=kid_id,
                kid_name=kid_name,
                chore_id=entry["chore_id"],
                chore_name=chore_name,
                hours=hours_remaining,
                points=points,
                due_date=entry["due_dt"].isoformat(),
            )

        const.LOGGER.debug(
            "Due window transitions - Emitted %d signal(s)",
            len(entries),
        )

    def _process_due_reminder(self, entries: list[ChoreTimeEntry]) -> None:
        """Process due reminder entries and emit signals.

        Args:
            entries: List of ChoreTimeEntry for chores within reminder window
        """
        if not entries:
            return

        for entry in entries:
            chore_info = entry["chore_info"]
            time_until_due = entry["time_until_due"]
            minutes_remaining = max(0, int(time_until_due.total_seconds() / 60))

            kid_id = entry["kid_id"]
            chore_name = chore_info.get(const.DATA_CHORE_NAME, "Unknown Chore")
            points = chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0)

            # Get kid name for signal emission
            kid_info: KidData = cast(
                "KidData", self._coordinator.kids_data.get(kid_id, {})
            )
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")

            self.emit(
                const.SIGNAL_SUFFIX_CHORE_DUE_REMINDER,
                kid_id=kid_id,
                kid_name=kid_name,
                chore_id=entry["chore_id"],
                chore_name=chore_name,
                minutes=minutes_remaining,
                points=points,
                due_date=entry["due_dt"].isoformat(),
            )

        const.LOGGER.debug(
            "Due reminders - Emitted %d signal(s)",
            len(entries),
        )

    async def _process_approval_reset_entries(
        self,
        scan: dict[str, list[ChoreTimeEntry]],
        now_utc: datetime,
        trigger: str = const.CHORE_SCAN_TRIGGER_DUE_DATE,
        *,
        persist: bool = True,
    ) -> tuple[int, set[tuple[str, str]]]:
        """Process approval boundary reset entries from unified scan.

        Handles AT_DUE_DATE_* chore resets for both SHARED and INDEPENDENT
        completion criteria. Uses ChoreEngine to determine actions.

        Args:
            scan: Result from process_time_checks() containing reset categories
            now_utc: Current UTC datetime
            trigger: Approval boundary trigger ("due_date" or "midnight")
            persist: If True, persist changes immediately. If False, caller handles persist.

        Returns:
            Tuple of (reset_count, reset_pairs) where reset_pairs is a set
            of (kid_id, chore_id) tuples that were reset in this pass.
        """
        reset_count = 0
        reset_pairs: set[tuple[str, str]] = set()
        rotation_payloads: list[dict[str, Any]] = []

        # Process SHARED/SHARED_FIRST chores
        for entry in scan.get(const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED, []):
            chore_id = entry["chore_id"]
            chore_info = entry["chore_info"]
            should_reschedule_shared = False

            # Get chore-level state
            current_state = chore_info.get(
                const.DATA_CHORE_STATE, const.CHORE_STATE_PENDING
            )

            # Use engine to determine action
            category = ChoreEngine.get_boundary_category(
                chore_data=chore_info,
                kid_state=current_state,
                trigger=trigger,
            )

            # Reset all assigned kids
            assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            for kid_id in assigned_kids:
                if not kid_id:
                    continue

                has_pending_claim = self.chore_has_pending_claim(kid_id, chore_id)
                pending_claim_action = chore_info.get(
                    const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                    const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
                )
                decision = self._decide_reset_action(
                    self._build_reset_context(
                        trigger=cast("ResetTrigger", trigger),
                        approval_reset_type=chore_info.get(
                            const.DATA_CHORE_APPROVAL_RESET_TYPE,
                            const.DEFAULT_APPROVAL_RESET_TYPE,
                        ),
                        overdue_handling_type=chore_info.get(
                            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                            const.DEFAULT_OVERDUE_HANDLING_TYPE,
                        ),
                        completion_criteria=chore_info.get(
                            const.DATA_CHORE_COMPLETION_CRITERIA,
                            const.COMPLETION_CRITERIA_INDEPENDENT,
                        ),
                        boundary_category=cast(
                            "ResetBoundaryCategory | None",
                            category,
                        ),
                        has_pending_claim=has_pending_claim,
                        pending_claim_action=pending_claim_action,
                    )
                )

                if decision == const.CHORE_RESET_DECISION_HOLD:
                    continue

                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

                # Handle pending claims (HOLD/CLEAR/AUTO_APPROVE)
                if has_pending_claim and decision in (
                    const.CHORE_RESET_DECISION_AUTO_APPROVE_PENDING,
                    const.CHORE_RESET_DECISION_RESET_ONLY,
                    const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                ):
                    if await self._handle_pending_chore_claim_at_reset(
                        kid_id, chore_id, chore_info, kid_chore_data
                    ):
                        continue  # HOLD action - skip reset for this kid

                effective_decision = decision
                if decision == const.CHORE_RESET_DECISION_AUTO_APPROVE_PENDING:
                    if category == const.CHORE_RESET_BOUNDARY_CATEGORY_CLEAR_ONLY:
                        effective_decision = const.CHORE_RESET_DECISION_RESET_ONLY
                    else:
                        effective_decision = (
                            const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE
                        )

                # Record miss if chore was overdue and mark-missed is enabled
                if current_state == const.CHORE_STATE_OVERDUE:
                    overdue_handling = chore_info.get(
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                        const.DEFAULT_OVERDUE_HANDLING_TYPE,
                    )
                    if (
                        overdue_handling
                        == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED
                    ):
                        self._record_chore_missed(kid_id, chore_id)

                # Phase 3 Step 3: Clear MISSED lock at midnight for mark_missed_and_lock strategy
                if current_state == const.CHORE_STATE_MISSED:
                    overdue_handling = chore_info.get(
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                        const.DEFAULT_OVERDUE_HANDLING_TYPE,
                    )
                    if (
                        overdue_handling
                        == const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
                        and trigger == const.CHORE_SCAN_TRIGGER_MIDNIGHT
                    ):
                        # D-17: For rotation chores, advance turn if current holder missed
                        if ChoreEngine.is_rotation_mode(chore_info):
                            current_turn_holder = chore_info.get(
                                const.DATA_CHORE_ROTATION_CURRENT_KID_ID
                            )
                            if current_turn_holder == kid_id:
                                # Advance rotation to next kid
                                rotation_payload = self._advance_rotation(
                                    chore_id, kid_id, method="auto"
                                )
                                # Collect payloads for batch emission after persist
                                if rotation_payload:
                                    rotation_payloads.append(rotation_payload)

                self._apply_reset_action(
                    {
                        "kid_id": kid_id,
                        "chore_id": chore_id,
                        "decision": effective_decision,
                        "reschedule_kid_id": None,
                        "allow_reschedule": False,
                    }
                )

                if (
                    effective_decision
                    == const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE
                ):
                    should_reschedule_shared = True

                reset_count += 1
                reset_pairs.add((kid_id, chore_id))

            if should_reschedule_shared:
                self._reschedule_chore_due(chore_id)

        # Process INDEPENDENT chores
        for entry in scan.get(const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT, []):
            chore_id = entry["chore_id"]
            chore_info = entry["chore_info"]
            kid_entries = entry.get("kids", [])

            for kid_entry in kid_entries:
                kid_id = kid_entry["kid_id"]

                # Derive state from timestamp-based checks
                if self.chore_is_overdue(kid_id, chore_id):
                    kid_state = const.CHORE_STATE_OVERDUE
                elif self.chore_has_pending_claim(kid_id, chore_id):
                    kid_state = const.CHORE_STATE_CLAIMED
                elif self.chore_is_approved_in_period(kid_id, chore_id):
                    kid_state = const.CHORE_STATE_APPROVED
                else:
                    kid_state = const.CHORE_STATE_PENDING

                # Use engine to determine action
                category = ChoreEngine.get_boundary_category(
                    chore_data=chore_info,
                    kid_state=kid_state,
                    trigger=trigger,
                )

                has_pending_claim = self.chore_has_pending_claim(kid_id, chore_id)
                pending_claim_action = chore_info.get(
                    const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                    const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
                )
                decision = self._decide_reset_action(
                    self._build_reset_context(
                        trigger=cast("ResetTrigger", trigger),
                        approval_reset_type=chore_info.get(
                            const.DATA_CHORE_APPROVAL_RESET_TYPE,
                            const.DEFAULT_APPROVAL_RESET_TYPE,
                        ),
                        overdue_handling_type=chore_info.get(
                            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                            const.DEFAULT_OVERDUE_HANDLING_TYPE,
                        ),
                        completion_criteria=chore_info.get(
                            const.DATA_CHORE_COMPLETION_CRITERIA,
                            const.COMPLETION_CRITERIA_INDEPENDENT,
                        ),
                        boundary_category=cast(
                            "ResetBoundaryCategory | None",
                            category,
                        ),
                        has_pending_claim=has_pending_claim,
                        pending_claim_action=pending_claim_action,
                    )
                )

                if decision == const.CHORE_RESET_DECISION_HOLD:
                    continue

                kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

                # Handle pending claims (HOLD/CLEAR/AUTO_APPROVE)
                if has_pending_claim and decision in (
                    const.CHORE_RESET_DECISION_AUTO_APPROVE_PENDING,
                    const.CHORE_RESET_DECISION_RESET_ONLY,
                    const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                ):
                    if await self._handle_pending_chore_claim_at_reset(
                        kid_id, chore_id, chore_info, kid_chore_data
                    ):
                        continue  # HOLD action - skip reset for this kid

                effective_decision = decision
                if decision == const.CHORE_RESET_DECISION_AUTO_APPROVE_PENDING:
                    if category == const.CHORE_RESET_BOUNDARY_CATEGORY_CLEAR_ONLY:
                        effective_decision = const.CHORE_RESET_DECISION_RESET_ONLY
                    else:
                        effective_decision = (
                            const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE
                        )

                # Record miss if chore was overdue and mark-missed is enabled
                if kid_state == const.CHORE_STATE_OVERDUE:
                    overdue_handling = chore_info.get(
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                        const.DEFAULT_OVERDUE_HANDLING_TYPE,
                    )
                    if (
                        overdue_handling
                        == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED
                    ):
                        self._record_chore_missed(kid_id, chore_id)

                # Rotation chores: on boundary reset of an approved turn holder,
                # advance to the next turn once per completed cycle.
                if (
                    kid_state == const.CHORE_STATE_APPROVED
                    and ChoreEngine.is_rotation_mode(chore_info)
                ):
                    current_turn_holder = chore_info.get(
                        const.DATA_CHORE_ROTATION_CURRENT_KID_ID
                    )
                    if current_turn_holder == kid_id:
                        rotation_payload = self._advance_rotation(
                            chore_id, kid_id, method="auto"
                        )
                        if rotation_payload:
                            rotation_payloads.append(rotation_payload)

                # Phase 3 Step 3: Clear MISSED lock at midnight for mark_missed_and_lock strategy
                if kid_state == const.CHORE_STATE_MISSED:
                    overdue_handling = chore_info.get(
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                        const.DEFAULT_OVERDUE_HANDLING_TYPE,
                    )
                    if (
                        overdue_handling
                        == const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
                        and trigger == const.CHORE_SCAN_TRIGGER_MIDNIGHT
                    ):
                        # D-17: For rotation chores, advance turn if current holder missed
                        if ChoreEngine.is_rotation_mode(chore_info):
                            current_turn_holder = chore_info.get(
                                const.DATA_CHORE_ROTATION_CURRENT_KID_ID
                            )
                            if current_turn_holder == kid_id:
                                # Advance rotation to next kid
                                rotation_payload = self._advance_rotation(
                                    chore_id, kid_id, method="auto"
                                )
                                # Collect payloads for batch emission after persist
                                if rotation_payload:
                                    rotation_payloads.append(rotation_payload)

                self._apply_reset_action(
                    {
                        "kid_id": kid_id,
                        "chore_id": chore_id,
                        "decision": effective_decision,
                        "reschedule_kid_id": kid_id,
                    }
                )

                reset_count += 1
                reset_pairs.add((kid_id, chore_id))

        if reset_count > 0:
            const.LOGGER.debug(
                "Approval boundary resets (%s): %d kid(s) reset",
                trigger,
                reset_count,
            )

        self._finalize_reset_batch(
            persist=persist,
            reset_count=reset_count,
            rotation_payloads=rotation_payloads,
        )

        return reset_count, reset_pairs

    async def _handle_pending_chore_claim_at_reset(
        self,
        kid_id: str,
        chore_id: str,
        chore_info: ChoreData,
        kid_chore_data: KidChoreDataEntry,
    ) -> bool:
        """Handle pending claim based on approval reset pending claim action.

        Called during scheduled resets (midnight, due date) to determine
        how to handle claims that weren't approved before reset.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            chore_info: The chore data dictionary
            kid_chore_data: The kid's chore data for clearing pending count

        Returns:
            True if reset should be SKIPPED for this kid (HOLD action)
            False if reset should CONTINUE (CLEAR or after AUTO_APPROVE)
        """
        # Check if kid has pending claim
        if not self.chore_has_pending_claim(kid_id, chore_id):
            return False  # No pending claim, continue with reset

        pending_claim_action = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
        )

        if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_HOLD:
            # HOLD: Skip reset for this kid, leave claim pending
            const.LOGGER.debug(
                "Chore Reset - HOLD pending claim for Kid '%s' on Chore '%s'",
                kid_id,
                chore_id,
            )
            return True  # Skip reset for this kid

        if pending_claim_action == const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE:
            # AUTO_APPROVE: Approve the pending claim before reset
            # Landlord duty: Ensure periods structures exist before statistics writes
            self._ensure_kid_structures(kid_id, chore_id)

            const.LOGGER.debug(
                "Chore Reset - AUTO_APPROVE pending claim for Kid '%s' on Chore '%s'",
                kid_id,
                chore_id,
            )
            kid_info: KidData | dict[str, Any] = self._coordinator.kids_data.get(
                kid_id, {}
            )
            kid_name = kid_info.get(const.DATA_KID_NAME, "Unknown")
            base_points = float(
                chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
            )
            multiplier = float(kid_info.get(const.DATA_KID_POINTS_MULTIPLIER, 1.0))
            points_awarded = ChoreEngine.calculate_points(chore_info, multiplier)
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            is_shared = completion_criteria in (
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            )
            is_multi_claim = ChoreEngine.chore_allows_multiple_claims(chore_info)
            previous_state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE,
                const.CHORE_STATE_PENDING,
            )
            now_iso = dt_now_iso()
            effective_date_iso = (
                kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
                or kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
                or now_iso
            )

            # Emit canonical approval signal - all approval origins follow the
            # same manager choreography path to reduce drift.
            self.emit(
                const.SIGNAL_SUFFIX_CHORE_APPROVED,
                kid_id=kid_id,
                chore_id=chore_id,
                kid_name=kid_name,
                parent_name="auto_reset",
                base_points=base_points,
                apply_multiplier=True,
                points_awarded=points_awarded,
                is_shared=is_shared,
                is_multi_claim=is_multi_claim,
                chore_name=chore_info.get(const.DATA_CHORE_NAME, ""),
                chore_labels=chore_info.get(const.DATA_CHORE_LABELS, []),
                multiplier_applied=multiplier,
                previous_state=previous_state,
                update_stats=True,
                effective_date=effective_date_iso,
                approval_origin=const.CHORE_APPROVAL_ORIGIN_AUTO_RESET,
                notify_kid=False,
            )

        # CLEAR (default) or after AUTO_APPROVE: Clear pending_claim_count
        if kid_chore_data:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

        return False  # Continue with reset

    # =========================================================================
    # §3 SERVICE METHODS (public API for Coordinator delegation)
    # =========================================================================

    async def set_due_date(
        self,
        chore_id: str,
        due_date: datetime | None,
        kid_id: str | None = None,
    ) -> None:
        """Set the due date of a chore.

        Args:
            chore_id: Chore to update
            due_date: New due date (or None to clear)
            kid_id: If provided for INDEPENDENT chores, updates only this kid's due date.
                   For SHARED chores, this parameter is ignored.

        For SHARED chores: Updates the single chore-level due date.
        For INDEPENDENT chores:
            - Does NOT set chore-level due_date (respects post-migration structure)
            - If kid_id provided: Updates only that kid's due date
            - If kid_id None: Updates all per-kid due dates
        """
        from homeassistant.util import dt as dt_util

        chore_info = self._coordinator.chores_data.get(chore_id)
        if chore_info is None:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        # Convert due_date to UTC ISO string
        new_due_date_iso = dt_util.as_utc(due_date).isoformat() if due_date else None

        # Get completion criteria
        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # Apply based on completion criteria
        if criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ):
            chore_info[const.DATA_CHORE_DUE_DATE] = new_due_date_iso
        elif criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            if kid_id:
                # Update only specified kid's due date
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                per_kid_due_dates[kid_id] = new_due_date_iso
            else:
                # Update all assigned kids' due dates
                per_kid_due_dates = chore_info.setdefault(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    per_kid_due_dates[assigned_kid_id] = new_due_date_iso

        # If due date cleared, reset frequency if needed
        if new_due_date_iso is None:
            if chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY) not in (
                const.FREQUENCY_NONE,
                const.FREQUENCY_DAILY,
                const.FREQUENCY_WEEKLY,
            ):
                chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL, None)
                chore_info.pop(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, None)

        # Reset chore state to PENDING for all assigned kids
        # Use persist=False since we persist once at the end
        for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            if assigned_kid_id:
                self._transition_chore_state(
                    assigned_kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                    clear_ownership=True,
                    persist=False,
                )

        const.LOGGER.info(
            "Due date set for chore '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    async def skip_due_date(self, chore_id: str, kid_id: str | None = None) -> None:
        """Skip the current due date of a recurring chore and reschedule it.

        Args:
            chore_id: Chore to skip
            kid_id: If provided for INDEPENDENT chores, skips only this kid's due date.
                   For SHARED chores, this parameter is ignored.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        if (
            chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE)
            == const.FREQUENCY_NONE
        ):
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INVALID_FREQUENCY,
                translation_placeholders={"frequency": "none"},
            )

        criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: skip per-kid due dates
            if kid_id:
                # Skip only specified kid
                if kid_id not in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                        translation_placeholders={
                            "kid_id": kid_id,
                            "chore_id": chore_id,
                        },
                    )
                per_kid_due_dates = chore_info.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                if not per_kid_due_dates.get(kid_id):
                    return  # No due date to skip

                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
                self._transition_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                    clear_ownership=True,
                    persist=False,
                )
            else:
                # Skip all assigned kids
                self._reschedule_chore_next_due(chore_info)
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    if (
                        assigned_kid_id
                        and assigned_kid_id in self._coordinator.kids_data
                    ):
                        self._reschedule_chore_next_due_date_for_kid(
                            chore_info, chore_id, assigned_kid_id
                        )
                        self._transition_chore_state(
                            assigned_kid_id,
                            chore_id,
                            const.CHORE_STATE_PENDING,
                            reset_approval_period=True,
                            clear_ownership=True,
                            persist=False,
                        )
        else:
            # SHARED: skip chore-level due date
            if not chore_info.get(const.DATA_CHORE_DUE_DATE):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                    translation_placeholders={
                        "field": "due_date",
                        "entity": f"chore '{chore_info.get(const.DATA_CHORE_NAME, chore_id)}'",
                    },
                )
            self._reschedule_chore_next_due(chore_info)
            for assigned_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if assigned_kid_id and assigned_kid_id in self._coordinator.kids_data:
                    self._transition_chore_state(
                        assigned_kid_id,
                        chore_id,
                        const.CHORE_STATE_PENDING,
                        reset_approval_period=True,
                        clear_ownership=True,
                        persist=False,
                    )

        const.LOGGER.info(
            "Skipped due date for chore '%s'",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
        )

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    def reset_chore_to_pending(self, chore_id: str, *, persist: bool = True) -> None:
        """Reset a specific chore to pending state for all assigned kids.

        Args:
            chore_id: The chore to reset
            persist: If True, persist and update listeners (default). Set False when
                    called as part of a larger operation that will persist later.

        This resets:
        - All assigned kids' states to PENDING
        - Approval period start time
        - Ownership claims
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            const.LOGGER.warning("Cannot reset chore %s - not found", chore_id)
            return

        reset_count = 0
        for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
            if kid_id:
                self._transition_chore_state(
                    kid_id,
                    chore_id,
                    const.CHORE_STATE_PENDING,
                    reset_approval_period=True,
                    clear_ownership=True,
                    persist=False,
                )
                reset_count += 1

        if persist and reset_count > 0:
            self._coordinator._persist()
            self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.debug(
            "Reset chore '%s' to pending for %d kids",
            chore_info.get(const.DATA_CHORE_NAME, chore_id),
            reset_count,
        )

    async def reset_all_chore_states_to_pending(self) -> None:
        """Reset all chores to pending state, clearing claims/approvals.

        This is a manual reset that:
        - Sets all chore states to PENDING
        - Resets approval_period_start for all chores
        - Emits SIGNAL_SUFFIX_CHORE_STATUS_RESET for each chore
        """
        chore_ids = list(self._coordinator.chores_data.keys())
        for chore_id in chore_ids:
            self.reset_chore_to_pending(chore_id, persist=False)

        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

        const.LOGGER.info("Manually reset all chores to pending")

    async def reset_overdue_chores(
        self, chore_id: str | None = None, kid_id: str | None = None
    ) -> None:
        """Reset overdue chore(s) to Pending state and reschedule.

        Args:
            chore_id: Optional specific chore to reset (all kids if None)
            kid_id: Optional specific kid to reset (all overdue if None)

        Branching logic:
        - INDEPENDENT chores: Reschedule per-kid due dates individually
        - SHARED chores: Reschedule chore-level due date (affects all kids)
        """
        reset_count = 0

        for iter_kid_id, iter_chore_id, chore_info in self._iter_kid_chore_pairs(
            chore_id=chore_id,
            kid_id=kid_id,
            filter_fn=self.chore_is_overdue,
        ):
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_SHARED,
            )

            self._transition_chore_state(
                iter_kid_id,
                iter_chore_id,
                const.CHORE_STATE_PENDING,
                reset_approval_period=True,
                clear_ownership=True,
                persist=False,
            )
            reset_count += 1

            # Reschedule based on completion criteria
            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, iter_chore_id, iter_kid_id
                )
            else:
                self._reschedule_chore_next_due(chore_info)

        if reset_count > 0:
            self._coordinator._persist()
            self._coordinator.async_set_updated_data(self._coordinator._data)
            const.LOGGER.debug("Reset %d overdue chore assignment(s)", reset_count)

    # =========================================================================
    # §4 CRUD METHODS (Manager-owned create/update/delete)
    # =========================================================================
    # These methods own the write operations for chore entities.
    # Called by options_flow.py and services.py - they must NOT write directly.

    def create_chore(
        self,
        user_input: dict[str, Any],
        internal_id: str | None = None,
        prebuilt: bool = False,
        immediate_persist: bool = False,
    ) -> dict[str, Any]:
        """Create a new chore in storage.

        Args:
            user_input: Chore data with DATA_* keys.
            internal_id: Optional pre-generated UUID (for form resubmissions).
            prebuilt: If True, user_input is already a complete ChoreData dict.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Complete ChoreData dict ready for use.

        Emits:
            SIGNAL_SUFFIX_CHORE_CREATED with chore_id and chore_name.
        """
        # Build complete chore data structure (or use pre-built)
        if prebuilt:
            chore_data = dict(user_input)
        else:
            chore_data = dict(db.build_chore(user_input))

        # Override internal_id if provided (for form resubmission consistency)
        if internal_id:
            chore_data[const.DATA_CHORE_INTERNAL_ID] = internal_id

        final_id = str(chore_data[const.DATA_CHORE_INTERNAL_ID])
        chore_name = str(chore_data.get(const.DATA_CHORE_NAME, ""))

        # Store in coordinator data
        self._coordinator._data[const.DATA_CHORES][final_id] = chore_data
        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        # Emit lifecycle event
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_CREATED,
            chore_id=final_id,
            chore_name=chore_name,
        )

        const.LOGGER.info(
            "Created chore '%s' (ID: %s)",
            chore_name,
            final_id,
        )

        return chore_data

    def update_chore(
        self, chore_id: str, updates: dict[str, Any], *, immediate_persist: bool = False
    ) -> dict[str, Any]:
        """Update an existing chore in storage.

        Args:
            chore_id: Internal UUID of the chore to update.
            updates: Partial chore data with DATA_* keys to merge.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Returns:
            Updated ChoreData dict.

        Raises:
            HomeAssistantError: If chore not found.

        Emits:
            SIGNAL_SUFFIX_CHORE_UPDATED with chore_id and chore_name.
        """
        chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
        if chore_id not in chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        existing = chores_data[chore_id]

        # Phase 3 Step 5: Handle completion_criteria transitions (D-11)
        # Wire transition handler for options flow (services remain immutable)
        old_criteria = existing.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        new_criteria = updates.get(const.DATA_CHORE_COMPLETION_CRITERIA)

        if new_criteria and new_criteria != old_criteria:
            # Transition handler validates, initializes/clears fields, persists, emits
            self._handle_criteria_transition(chore_id, old_criteria, new_criteria)
            # Return updated chore data (transition handler already persisted)
            return chores_data[chore_id]

        # Build updated chore (merge existing with updates)
        updated_chore = dict(db.build_chore(updates, existing=existing))

        # Store updated chore
        self._coordinator._data[const.DATA_CHORES][chore_id] = updated_chore

        # Reset states to PENDING if due dates are being updated
        # Handles both SHARED (DATA_CHORE_DUE_DATE) and INDEPENDENT (DATA_CHORE_PER_KID_DUE_DATES)
        if (
            const.DATA_CHORE_DUE_DATE in updates
            or const.DATA_CHORE_PER_KID_DUE_DATES in updates
        ):
            self.reset_chore_to_pending(chore_id, persist=False)

        # NOTE: Badge recalculation is handled by GamificationManager via
        # SIGNAL_SUFFIX_CHORE_UPDATED event (Platinum Architecture: event-driven)

        chore_name = str(updated_chore.get(const.DATA_CHORE_NAME, ""))

        # Persist then emit (transactional integrity: signal only after persist)
        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        self.emit(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id=chore_id,
            chore_name=chore_name,
        )

        # Clean up any orphaned kid-chore entities after assignment changes
        self._coordinator.hass.add_job(
            remove_orphaned_kid_chore_entities(
                self.hass,
                self._coordinator.config_entry.entry_id,
                self._coordinator.kids_data,
                self._coordinator.chores_data,
            )
        )

        const.LOGGER.debug(
            "Updated chore '%s' (ID: %s)",
            chore_name,
            chore_id,
        )

        return updated_chore

    def delete_chore(self, chore_id: str, *, immediate_persist: bool = False) -> None:
        """Delete a chore from storage and cleanup references.

        Follows Platinum Architecture (Choreography over Orchestration):
        - ChoreManager cleans its own domain data (kid chore_data)
        - Emits CHORE_DELETED signal for cross-domain cleanup
        - GamificationManager reacts to signal for achievement/challenge cleanup
        - SystemManager reacts to signal for entity registry cleanup

        Args:
            chore_id: Internal UUID of the chore to delete.
            immediate_persist: If True, persist immediately (use for config flow operations).

        Raises:
            HomeAssistantError: If chore not found.

        Emits:
            SIGNAL_SUFFIX_CHORE_DELETED with chore_id and chore_name.
        """
        chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
        if chore_id not in chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        chore_info = chores_data[chore_id]
        chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
        # Capture assigned_kids before deletion for notification cleanup
        assigned_kids = list(chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []))

        # Delete from storage
        del self._coordinator._data[const.DATA_CHORES][chore_id]

        # Remove HA entities (targeted cleanup)
        remove_entities_by_item_id(
            self.hass,
            self._coordinator.config_entry.entry_id,
            chore_id,
        )

        # Clean own domain: remove deleted chore refs from kid chore_data
        # (This is chore-tracking data that lives in kid records)
        for kid_data in self._coordinator.kids_data.values():
            kid_chore_data = kid_data.get(const.DATA_KID_CHORE_DATA, {})
            if chore_id in kid_chore_data:
                del kid_chore_data[chore_id]
                const.LOGGER.debug("Removed chore '%s' from kid chore_data", chore_id)

        # Remove orphaned shared chore sensors
        self.hass.add_job(
            remove_orphaned_shared_chore_sensors(
                self.hass,
                self._coordinator.config_entry.entry_id,
                self._coordinator.chores_data,
            )
        )

        self._coordinator._persist(immediate=immediate_persist)
        self._coordinator.async_update_listeners()

        # Emit lifecycle event (triggers GamificationManager, SystemManager, NotificationManager)
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_DELETED,
            chore_id=chore_id,
            chore_name=chore_name,
            assigned_kids=assigned_kids,
        )

        const.LOGGER.info(
            "Deleted chore '%s' (ID: %s)",
            chore_name,
            chore_id,
        )

    # =========================================================================
    # §5 QUERY METHODS (read-only state queries)
    # =========================================================================
    # These methods provide chore state queries used by sensors and dashboards.
    # They are read-only and do not modify state.

    @property
    def pending_chore_approvals(self) -> list[dict[str, Any]]:
        """Return the list of pending chore approvals (computed from timestamps)."""
        return self.get_pending_chore_approvals()

    @property
    def pending_chore_changed(self) -> bool:
        """Return whether pending chore approvals have changed since last reset."""
        return self._coordinator.ui_manager.pending_chore_changed

    def _chore_allows_multiple_claims(self, chore_id: str) -> bool:
        """Check if chore allows multiple claims. Manager provides data, Engine provides verdict."""
        return ChoreEngine.chore_allows_multiple_claims(
            self._coordinator.chores_data.get(chore_id, {})
        )

    def chore_has_pending_claim(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore has a pending claim. Manager provides data, Engine provides verdict."""
        return ChoreEngine.chore_has_pending_claim(
            self._get_kid_chore_data(kid_id, chore_id)
        )

    def chore_is_actionable(self, kid_id: str, chore_id: str) -> bool:
        """Check if a kid can take action on a chore (not pending claim, not approved).

        This is the inverse of the common "skip" check in loops. A chore is
        actionable if the kid has not claimed it AND has not been approved
        in the current period.

        Use this to filter kids in due/overdue/reminder checks.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Returns:
            True if the kid can act on this chore, False if already claimed/approved.
        """
        if self.chore_has_pending_claim(kid_id, chore_id):
            return False
        if self.chore_is_approved_in_period(kid_id, chore_id):
            return False
        return True

    def chore_is_overdue(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is in overdue state. Manager provides data, Engine provides verdict."""
        return ChoreEngine.chore_is_overdue(self._get_kid_chore_data(kid_id, chore_id))

    def chore_is_due(self, kid_id: str | None, chore_id: str) -> bool:
        """Check if chore is in due window (approaching due date).

        Thin wrapper that delegates to Engine for calculation.
        """
        due_dt = self.get_due_date(chore_id, kid_id)
        if not due_dt:
            return False
        chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        offset = cast(
            "str | None",
            chore_info.get(
                const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
            ),
        )
        return ChoreEngine.chore_is_due(due_dt.isoformat(), offset, dt_util.utcnow())

    def chore_is_approved_in_period(self, kid_id: str, chore_id: str) -> bool:
        """Check if a chore is already approved in the current approval period.

        A chore is considered approved in the current period if:
        - last_approved timestamp exists, AND
        - approval_period_start exists, AND
        - last_approved >= approval_period_start

        When approval_period_start is None, the chore has been reset to pending
        (e.g., UPON_COMPLETION reset), so return False.

        Returns:
            True if approved in current period, False otherwise.
        """
        kid_data: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})
        kid_chore_data = ChoreEngine.get_chore_data_for_kid(kid_data, chore_id)
        if not kid_chore_data:
            return False

        last_approved = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)
        if not last_approved:
            return False

        period_start = self.get_approval_period_start(kid_id, chore_id)
        if not period_start:
            # approval_period_start is None when chore has been reset to pending
            # (e.g., UPON_COMPLETION reset). Return False to indicate not approved.
            return False

        approved_dt = dt_to_utc(last_approved)
        period_start_dt = dt_to_utc(period_start)

        if approved_dt is None or period_start_dt is None:
            return False

        return approved_dt >= period_start_dt

    def get_approval_period_start(self, kid_id: str, chore_id: str) -> str | None:
        """Get the start of the current approval period for this kid+chore.

        Public read method for cross-manager queries (e.g., NotificationManager
        uses this for Schedule-Lock deduplication). Follows the "Reads OK" pattern
        from DEVELOPMENT_STANDARDS.md § 4b.

        For SHARED chores: Uses chore-level approval_period_start
        For INDEPENDENT chores: Uses per-kid approval_period_start in kid_chore_data

        Returns:
            ISO timestamp string of period start, or None if not set.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return None

        # Default to INDEPENDENT if completion_criteria not set (backward compatibility)
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Period start is per-kid in kid_chore_data
            kid_data: KidData | dict[str, Any] = self._coordinator.kids_data.get(
                kid_id, {}
            )
            kid_chore_data = ChoreEngine.get_chore_data_for_kid(kid_data, chore_id)
            return kid_chore_data.get(const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START)
        # SHARED/SHARED_FIRST/etc.: Period start is at chore level
        return chore_info.get(const.DATA_CHORE_APPROVAL_PERIOD_START)

    def get_due_date(self, chore_id: str, kid_id: str | None = None) -> datetime | None:
        """Get the due date for a chore as datetime.

        Handles INDEPENDENT vs SHARED completion criteria resolution internally.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID (for INDEPENDENT chores).
                    None = use chore-level due date (SHARED)

        Returns:
            datetime or None if no due date configured.
        """
        chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        due_str = ChoreEngine.get_due_date_for_kid(chore_info, kid_id)
        return self._parse_due_datetime_cached(due_str)

    def get_due_window_start(
        self, chore_id: str, kid_id: str | None = None
    ) -> datetime | None:
        """Calculate when the due window starts (due_date - offset).

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID (for INDEPENDENT chores).
                    None = use chore-level due date (SHARED)

        Returns:
            datetime when due window starts, or None if not applicable.
        """
        due_dt = self.get_due_date(chore_id, kid_id)
        if not due_dt:
            return None

        chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        due_window_offset_str = chore_info.get(
            const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
        )
        due_window_td = dt_parse_duration(cast("str | None", due_window_offset_str))

        # If no offset or offset is 0, due window start equals due date
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return due_dt

        return due_dt - due_window_td

    def get_pending_chore_approvals(self) -> list[dict[str, Any]]:
        """Compute pending chore approvals dynamically from timestamp data.

        A chore has a pending approval if pending_claim_count > 0.

        Returns:
            List of dicts with keys: kid_id, chore_id, timestamp
        """
        pending: list[dict[str, Any]] = []
        for kid_id, kid_info in self._coordinator.kids_data.items():
            chore_data_map = kid_info.get(const.DATA_KID_CHORE_DATA, {})
            for chore_id, chore_entry in chore_data_map.items():
                # Skip chores that no longer exist
                if chore_id not in self._coordinator.chores_data:
                    continue
                if self.chore_has_pending_claim(kid_id, chore_id):
                    pending.append(
                        {
                            const.DATA_KID_ID: kid_id,
                            const.DATA_CHORE_ID: chore_id,
                            const.DATA_CHORE_TIMESTAMP: chore_entry.get(
                                const.DATA_KID_CHORE_DATA_LAST_CLAIMED, ""
                            ),
                        }
                    )
        return pending

    def get_pending_chore_count_for_kid(self, kid_id: str) -> int:
        """Count total pending chores awaiting approval for a specific kid.

        Used for tag-based notification aggregation (v0.5.0+) to show
        "Sarah: 3 chores pending" instead of individual notifications.

        Args:
            kid_id: The internal ID of the kid.

        Returns:
            Number of chores with pending claims for this kid.
        """
        count = 0
        kid_info: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_id in chore_data:
            # Skip chores that no longer exist
            if chore_id not in self._coordinator.chores_data:
                continue
            if self.chore_has_pending_claim(kid_id, chore_id):
                count += 1

        return count

    def can_claim_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a kid can claim a specific chore.

        This helper is dual-purpose: used for claim validation AND for providing
        status information to the dashboard helper sensor.

        Phase 2: SHARED_FIRST blocking is computed from other kids' states
        instead of checking a stored completed_by_other state.

        Checks (in order):
        1. SHARED_FIRST blocking - Another kid is claimed/approved
        2. pending_claim - Already has a claim awaiting approval
        3. already_approved - Already approved in current period (if not multi-claim)

        Returns:
            Tuple of (can_claim: bool, error_key: str | None)
            - (True, None) if claim is allowed
            - (False, translation_key) if claim is blocked
        """
        # Get current kid's chore data and chore definition
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        chore_data: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )

        # Determine if this is a multi-claim mode
        allow_multiple_claims = self._chore_allows_multiple_claims(chore_id)

        # For SHARED_FIRST, collect other kids' states for blocking check
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        other_kid_states = None
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            other_kid_states = {}
            for other_kid_id in kids_assigned:
                if other_kid_id != kid_id and other_kid_id:
                    other_kid_chore_data = self._get_kid_chore_data(
                        other_kid_id, chore_id
                    )
                    other_kid_states[other_kid_id] = other_kid_chore_data.get(
                        const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
                    )

        # Check 1: pending claim blocks new claims (unless multi-claim allowed)
        # For MULTI modes, re-claiming is allowed even with a pending claim
        if not allow_multiple_claims and self.chore_has_pending_claim(kid_id, chore_id):
            return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

        # Check 2: already approved in current period (unless multi-claim allowed)
        if not allow_multiple_claims and self.chore_is_approved_in_period(
            kid_id, chore_id
        ):
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        # Check 3: Delegate to Engine for SHARED_FIRST blocking and FSM-based locking
        # v0.5.0: Calculate resolved_state to enable rotation/waiting/missed blocking
        has_pending = ChoreEngine.chore_has_pending_claim(kid_chore_data)
        is_approved = self.chore_is_approved_in_period(kid_id, chore_id)

        # Get resolved state for FSM-based claim blocking (rotation, waiting, missed)
        # Use existing helper methods to get due_date and due_window_start
        due_date = self.get_due_date(chore_id, kid_id)
        due_window_start = self.get_due_window_start(chore_id, kid_id)

        resolved_state, lock_reason = ChoreEngine.resolve_kid_chore_state(
            chore_data=chore_data,
            kid_id=kid_id,
            now=dt_util.now(),
            is_approved_in_period=is_approved,
            has_pending_claim=has_pending,
            due_date=due_date,
            due_window_start=due_window_start,
        )

        return ChoreEngine.can_claim_chore(
            kid_chore_data=kid_chore_data,
            chore_data=chore_data,
            has_pending_claim=has_pending,
            is_approved_in_period=is_approved,
            other_kid_states=other_kid_states,
            resolved_state=resolved_state,
            lock_reason=lock_reason,
        )

    def can_approve_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific kid.

        This helper is dual-purpose: used for approval validation AND for providing
        status information to the dashboard helper sensor.

        Phase 2: completed_by_other check removed - SHARED_FIRST blocking
        only affects claims, not approvals (parent can still approve anyone).

        Checks (in order):
        1. already_approved - Already approved in current period (if not multi-claim)

        Note: Unlike can_claim_chore, this does NOT check for pending claims because
        we're checking if approval is possible, not if a new claim can be made.

        Returns:
            Tuple of (can_approve: bool, error_key: str | None)
            - (True, None) if approval is allowed
            - (False, translation_key) if approval is blocked
        """
        # Check: already approved in current period (unless multi-claim allowed)
        allow_multiple_claims = self._chore_allows_multiple_claims(chore_id)

        if not allow_multiple_claims and self.chore_is_approved_in_period(
            kid_id, chore_id
        ):
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    def get_chore_last_completed(
        self,
        chore_id: str,
        kid_id: str | None = None,
    ) -> str | None:
        """Get last_completed timestamp. Manager provides data, Engine provides verdict."""
        chore_data: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        kid_data: KidData | dict[str, Any] = (
            self._coordinator.kids_data.get(kid_id, {}) if kid_id else {}
        )
        return ChoreEngine.get_last_completed_for_kid(chore_data, kid_data, kid_id)

    def get_chore_status_context(self, kid_id: str, chore_id: str) -> dict[str, Any]:
        """Return all derived chore states for a kid+chore in one call.

        Sensors should call this once and read from the returned dict
        rather than calling multiple individual wrapper methods. This
        provides O(1) lookups after a single data fetch.

        Returns:
            Dict with keys:
            - state: str (derived display state with priority)
            - stored_state: str (raw state from storage)
            - is_overdue: bool
            - is_due: bool
            - has_pending_claim: bool
            - is_approved_in_period: bool
            - is_completed_by_other: bool
            - can_claim: bool
            - can_claim_error: str | None
            - lock_reason: str | None
            - can_approve: bool
            - can_approve_error: str | None
            - due_date: str | None
            - available_at: str | None
            - last_completed: str | None

        Display state priority:
            approved > completed_by_other > claimed > overdue > due > pending
        """
        # Single data fetch
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Pre-compute all status flags using Engine methods
        has_pending = ChoreEngine.chore_has_pending_claim(kid_chore_data)
        is_overdue = ChoreEngine.chore_is_overdue(kid_chore_data)
        is_due = self.chore_is_due(kid_id, chore_id)

        # These require Manager context (approval_period_start lookup)
        is_approved = self.chore_is_approved_in_period(kid_id, chore_id)

        # Compute shared-first context and use one FSM resolution for both
        # display state and claimability checks.
        chore_data: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
            chore_id, {}
        )
        due_dt = self.get_due_date(chore_id, kid_id)
        due_window_start = self.get_due_window_start(chore_id, kid_id)

        display_state, lock_reason = ChoreEngine.resolve_kid_chore_state(
            chore_data=chore_data,
            kid_id=kid_id,
            now=dt_util.now(),
            is_approved_in_period=is_approved,
            has_pending_claim=has_pending,
            due_date=due_dt,
            due_window_start=due_window_start,
        )

        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        other_kid_states = None
        is_completed_by_other = False
        if completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            other_kid_states = {}
            for other_kid_id in kids_assigned:
                if other_kid_id != kid_id and other_kid_id:
                    other_kid_chore_data = self._get_kid_chore_data(
                        other_kid_id, chore_id
                    )
                    other_state = other_kid_chore_data.get(
                        const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
                    )
                    other_kid_states[other_kid_id] = other_state
                    other_claimed_by = other_kid_chore_data.get(
                        const.DATA_CHORE_CLAIMED_BY
                    )
                    other_completed_by = other_kid_chore_data.get(
                        const.DATA_CHORE_COMPLETED_BY
                    )
                    if (
                        other_state
                        in (const.CHORE_STATE_CLAIMED, const.CHORE_STATE_APPROVED)
                        or bool(other_claimed_by)
                        or bool(other_completed_by)
                    ):
                        is_completed_by_other = True
                        break

        can_claim, claim_error = ChoreEngine.can_claim_chore(
            kid_chore_data=kid_chore_data,
            chore_data=chore_data,
            has_pending_claim=has_pending,
            is_approved_in_period=is_approved,
            other_kid_states=other_kid_states,
            resolved_state=display_state,
            lock_reason=lock_reason,
        )

        if is_completed_by_other:
            can_claim = False
            claim_error = const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER

        can_approve, approve_error = self.can_approve_chore(kid_id, chore_id)

        # Raw stored state
        stored_state = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
        )

        # Apply completed_by_other display state for SHARED_FIRST if another kid
        # is active. This display-only state should take precedence over
        # due/overdue/pending for blocked kids.
        if is_completed_by_other and display_state in (
            const.CHORE_STATE_PENDING,
            const.CHORE_STATE_DUE,
            const.CHORE_STATE_OVERDUE,
        ):
            display_state = const.CHORE_STATE_COMPLETED_BY_OTHER

        context_lock_reason = None
        if not can_claim and lock_reason in (
            const.CHORE_STATE_WAITING,
            const.CHORE_STATE_NOT_MY_TURN,
            const.CHORE_STATE_MISSED,
        ):
            context_lock_reason = lock_reason

        available_at = None
        if context_lock_reason == const.CHORE_STATE_WAITING and due_window_start:
            available_at = due_window_start.isoformat()

        return {
            const.CHORE_CTX_STATE: display_state,
            const.CHORE_CTX_STORED_STATE: stored_state,
            const.CHORE_CTX_IS_OVERDUE: is_overdue,
            const.CHORE_CTX_IS_DUE: is_due,
            const.CHORE_CTX_HAS_PENDING_CLAIM: has_pending,
            const.CHORE_CTX_IS_APPROVED_IN_PERIOD: is_approved,
            const.CHORE_CTX_IS_COMPLETED_BY_OTHER: is_completed_by_other,
            const.CHORE_CTX_CAN_CLAIM: can_claim,
            const.CHORE_CTX_CAN_CLAIM_ERROR: claim_error,
            const.CHORE_CTX_LOCK_REASON: context_lock_reason,
            const.CHORE_CTX_CAN_APPROVE: can_approve,
            const.CHORE_CTX_CAN_APPROVE_ERROR: approve_error,
            const.CHORE_CTX_DUE_DATE: due_dt.isoformat() if due_dt else None,
            const.CHORE_CTX_AVAILABLE_AT: available_at,
            const.CHORE_CTX_LAST_COMPLETED: self.get_chore_last_completed(
                chore_id, kid_id
            ),
        }

    def get_chore_data_for_kid(
        self, kid_id: str, chore_id: str
    ) -> KidChoreDataEntry | dict[str, Any]:
        """Get the chore data dict for a specific kid+chore combination.

        Returns an empty dict if the kid or chore data doesn't exist.
        """
        kid_info: KidData = cast("KidData", self._coordinator.kids_data.get(kid_id, {}))
        return kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})

    def get_chore_claimant(self, chore_id: str) -> str | None:
        """Get the kid_id of the current claimant for a chore.

        For SHARED_FIRST chores, returns the kid who has claimed but not yet
        been approved. For other chores, returns the first kid with a pending
        claim (though typically only one would exist).

        Args:
            chore_id: The chore's internal ID

        Returns:
            kid_id of the claimant, or None if no pending claims.
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return None

        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        for kid_id in assigned_kids:
            if kid_id and self.chore_has_pending_claim(kid_id, chore_id):
                return kid_id
        return None

    def _is_chore_approval_after_reset(
        self, chore_info: ChoreData, kid_id: str
    ) -> bool:
        """Check if approval is happening after the reset boundary has passed.

        For AT_MIDNIGHT types: Due date must be before last midnight
        For AT_DUE_DATE types: Current time must be past the due date

        Returns True if "late", False otherwise.
        """
        chore_id = chore_info.get(const.DATA_CHORE_INTERNAL_ID, "")
        approval_reset_type = chore_info.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
        )

        # Get due date using unified helper
        due_date = self.get_due_date(chore_id, kid_id)
        if not due_date:
            return False

        now_utc = dt_util.utcnow()

        # AT_MIDNIGHT types: Check if due date was before last midnight
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        ):
            local_now = dt_util.as_local(now_utc)
            last_midnight_local = local_now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            last_midnight_utc = dt_util.as_utc(last_midnight_local)
            return due_date < last_midnight_utc

        # AT_DUE_DATE types: Check if past the due date
        if approval_reset_type in (
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
        ):
            return now_utc > due_date

        return False

    # =========================================================================
    # §6 HELPER METHODS (private)
    # =========================================================================

    def _ensure_kid_structures(self, kid_id: str, chore_id: str | None = None) -> None:
        """Landlord genesis - ensure kid has chore_periods bucket and per-chore periods.

        Creates empty chore_periods dict if missing. StatisticsEngine (Tenant)
        creates and writes the period sub-keys (daily/weekly/etc.) on-demand.

        Optionally ensures per-chore periods structure exists if chore_id provided.
        This maintains consistency - ChoreManager (Landlord) creates containers,
        StatisticsEngine (Tenant) populates data.

        This is the "Landlord" pattern - ChoreManager owns kid.chore_periods
        top-level dict, StatisticsEngine manages everything inside it.

        Args:
            kid_id: Kid UUID to ensure structure for
            chore_id: Optional chore UUID to ensure per-chore periods for
        """
        kids = self._coordinator._data.get(const.DATA_KIDS, {})
        kid = kids.get(kid_id)
        if kid is None:
            return  # Kid not found - caller should validate first

        # Kid-level chore_periods bucket (v44+)
        if const.DATA_KID_CHORE_PERIODS not in kid:
            kid[const.DATA_KID_CHORE_PERIODS] = {}  # Tenant populates sub-keys

        # Per-chore periods structure (if chore_id provided)
        if chore_id:
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            if (
                kid_chore_data
                and const.DATA_KID_CHORE_DATA_PERIODS not in kid_chore_data
            ):
                kid_chore_data[
                    const.DATA_KID_CHORE_DATA_PERIODS
                ] = {}  # Tenant populates sub-keys

    def _iter_kid_chore_pairs(
        self,
        chore_id: str | None = None,
        kid_id: str | None = None,
        filter_fn: Callable[[str, str], bool] | None = None,
    ) -> Iterator[tuple[str, str, ChoreData]]:
        """Iterate over (kid_id, chore_id, chore_info) pairs.

        Handles three iteration patterns:
        - chore_id only: All assigned kids for that chore
        - kid_id only: All chores assigned to that kid
        - Neither: All kid-chore pairs in the system

        Args:
            chore_id: Optional filter to specific chore
            kid_id: Optional filter to specific kid
            filter_fn: Optional filter function(kid_id, chore_id) -> bool

        Yields:
            Tuple of (kid_id, chore_id, chore_info) for each matching pair
        """
        if chore_id:
            # Specific chore: iterate its assigned kids
            chore_info = self._coordinator.chores_data.get(chore_id)
            if chore_info:
                for iter_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if iter_kid_id and iter_kid_id in self._coordinator.kids_data:
                        if kid_id and iter_kid_id != kid_id:
                            continue  # Skip if specific kid requested but doesn't match
                        if filter_fn and not filter_fn(iter_kid_id, chore_id):
                            continue
                        yield (iter_kid_id, chore_id, chore_info)
        elif kid_id:
            # Specific kid: iterate all chores assigned to them
            for iter_chore_id, chore_info in self._coordinator.chores_data.items():
                if kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if filter_fn and not filter_fn(kid_id, iter_chore_id):
                        continue
                    yield (kid_id, iter_chore_id, chore_info)
        else:
            # All: iterate all kid-chore pairs
            for iter_chore_id, chore_info in self._coordinator.chores_data.items():
                for iter_kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                    if iter_kid_id and iter_kid_id in self._coordinator.kids_data:
                        if filter_fn and not filter_fn(iter_kid_id, iter_chore_id):
                            continue
                        yield (iter_kid_id, iter_chore_id, chore_info)

    def _get_lock(self, kid_id: str, chore_id: str) -> asyncio.Lock:
        """Get or create a lock for kid+chore combination.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Returns:
            asyncio.Lock for this kid+chore pair
        """
        lock_key = f"{kid_id}:{chore_id}"
        if lock_key not in self._approval_locks:
            self._approval_locks[lock_key] = asyncio.Lock()
        return self._approval_locks[lock_key]

    def _transition_chore_state(
        self,
        kid_id: str,
        chore_id: str,
        new_state: str,
        *,
        reset_approval_period: bool = False,
        clear_ownership: bool = False,
        emit: bool = True,
        persist: bool = True,
    ) -> None:
        """Master method for chore state transitions.

        This is THE single source of truth for changing a chore's state.
        Handles all side effects: state change, global state update, persist,
        emit signal (when resetting to PENDING), and coordinator update.

        Phase 4 Guard Rail: Tracks state modification for debug-mode assertion.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            new_state: The new state to set
            reset_approval_period: If True, sets a new approval_period_start
            clear_ownership: If True, clears claimed_by and completed_by (for fresh cycle)
            emit: If True (default), emits CHORE_STATUS_RESET signal when → PENDING
            persist: If True (default), persists and updates coordinator data
        """
        # Phase 4 Guard Rail: Track modification
        self._track_state_modification(kid_id, chore_id)

        kid_info = self._coordinator.kids_data.get(kid_id)
        chore_info = self._coordinator.chores_data.get(chore_id)

        if not kid_info or not chore_info:
            return

        # Landlord duty: Ensure periods structures exist before statistics writes
        self._ensure_kid_structures(kid_id, chore_id)

        # Get or initialize kid chore data
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Update state
        kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = new_state

        # Phase 2: completed_by_other_chores list management removed
        # SHARED_FIRST blocking is now computed dynamically in can_claim_chore()
        # instead of being stored as completed_by_other state

        # Capture completed_by before optional ownership clear.
        # Rotation advancement on reset needs this value even when
        # clear_ownership=True for fresh-cycle transitions.
        completed_by_kid_id = None
        completed_by = chore_info.get(const.DATA_CHORE_COMPLETED_BY)
        if isinstance(completed_by, str):
            completed_by_kid_id = completed_by
        elif isinstance(completed_by, list) and completed_by:
            completed_by_kid_id = completed_by[0]

        # Clear ownership tracking for fresh cycle
        if clear_ownership:
            kid_chore_data.pop(const.DATA_CHORE_CLAIMED_BY, None)
            kid_chore_data.pop(const.DATA_CHORE_COMPLETED_BY, None)

        # Clear pending claim count on reset
        if new_state == const.CHORE_STATE_PENDING:
            kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = 0

            if reset_approval_period:
                now_iso = dt_now_iso()
                completion_criteria = chore_info.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                        now_iso
                    )
                else:
                    chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso

        # Update global chore state (aggregates all kids' states)
        self._update_global_state(chore_id)

        # Phase 3 Step 1: Advance rotation turn when resetting to PENDING
        # (Rotation advances at approval reset boundary, NOT on approval)
        rotation_signal_payload = None
        if new_state == const.CHORE_STATE_PENDING and reset_approval_period:
            # Advance rotation (returns payload for signal emission after persist)
            if completed_by_kid_id:
                rotation_signal_payload = self._advance_rotation(
                    chore_id, completed_by_kid_id, method="auto"
                )

        # Persist and emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        if persist:
            self._coordinator._persist()

            # Phase 3 Step 1: Emit rotation signal after persist
            if rotation_signal_payload:
                self.emit(
                    const.SIGNAL_SUFFIX_CHORE_ROTATION_ADVANCED,
                    **rotation_signal_payload,
                )

            # Emit reset signal when transitioning to PENDING
            if emit and new_state == const.CHORE_STATE_PENDING:
                self.emit(
                    const.SIGNAL_SUFFIX_CHORE_STATUS_RESET,
                    kid_id=kid_id,
                    chore_id=chore_id,
                    chore_name=chore_info.get(const.DATA_CHORE_NAME, ""),
                )

            self._coordinator.async_set_updated_data(self._coordinator._data)

    def _validate_kid_and_chore(self, kid_id: str, chore_id: str) -> None:
        """Validate kid and chore exist.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Raises:
            HomeAssistantError: If either entity not found
        """
        if chore_id not in self._coordinator.chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_CHORE,
                    "name": chore_id,
                },
            )

        if kid_id not in self._coordinator.kids_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_KID,
                    "name": kid_id,
                },
            )

    def _get_kid_chore_data(self, kid_id: str, chore_id: str) -> dict[str, Any]:
        """Get or create kid's chore data entry.

        Phase 3B Landlord/Tenant: ChoreManager owns chore_data and chore_stats.
        This method creates structures on-demand (not at kid genesis).
        StatisticsManager (tenant) writes to sub-keys but never creates top-level.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID

        Returns:
            The kid_chore_data dict for this kid+chore

        Raises:
            ValueError: If kid_id does not exist (kid was deleted)
        """
        # Defensive check: kid may have been deleted during async operations
        kid_info = self._coordinator.kids_data.get(kid_id)
        if not kid_info:
            raise ValueError(f"Kid {kid_id} does not exist (may have been deleted)")

        # Phase 3B Landlord duty: Ensure chore_data container exists
        kid_chores: dict[str, dict[str, Any]] | None = kid_info.get(
            const.DATA_KID_CHORE_DATA
        )
        if kid_chores is None:
            kid_chores = {}
            kid_info[const.DATA_KID_CHORE_DATA] = kid_chores

        # v44+: chore_stats deleted - fully ephemeral now (generate_chore_stats())
        # All stats derived on-demand from chore_periods.all_time.* buckets

        if chore_id not in kid_chores:
            # v43+: No total_points field - use periods.all_time.points as canonical source
            chore_info: ChoreData | dict[str, Any] = self._coordinator.chores_data.get(
                chore_id, {}
            )
            default_data: dict[str, Any] = {
                const.DATA_KID_CHORE_DATA_NAME: chore_info.get(
                    const.DATA_CHORE_NAME, chore_id
                ),
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
            }
            # Only set kid-level approval_period_start for INDEPENDENT chores
            # SHARED chores use chore-level approval_period_start instead
            criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                default_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    dt_now_iso()
                )
            kid_chores[chore_id] = default_data

        return kid_chores[chore_id]

    def _increment_pending_count(self, kid_id: str, chore_id: str) -> None:
        """Increment pending claim counter for kid+chore.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0)
        kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = current + 1

    def _decrement_pending_count(self, kid_id: str, chore_id: str) -> None:
        """Decrement pending claim counter for kid+chore.

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        current = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT, 0)
        kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] = max(
            0, current - 1
        )

    def _handle_completion_criteria(
        self,
        chore_id: str,
        kid_id: str,
        completing_kid_name: str,
    ) -> None:
        """Handle completed_by based on chore completion criteria.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid who completed
            completing_kid_name: Name of the completing kid
        """
        chore_data = self._coordinator.chores_data[chore_id]
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # Store in kid's own chore data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_CHORE_COMPLETED_BY] = completing_kid_name

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # Update other kids' completed_by
            for other_kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                if other_kid_id == kid_id:
                    continue
                other_chore_data = self._get_kid_chore_data(other_kid_id, chore_id)
                other_chore_data[const.DATA_CHORE_COMPLETED_BY] = completing_kid_name

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            # Append to list for all assigned kids
            for assigned_kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
                assigned_chore_data = self._get_kid_chore_data(
                    assigned_kid_id, chore_id
                )

                # Initialize as list if needed
                if (
                    const.DATA_CHORE_COMPLETED_BY not in assigned_chore_data
                    or not isinstance(
                        assigned_chore_data.get(const.DATA_CHORE_COMPLETED_BY), list
                    )
                ):
                    assigned_chore_data[const.DATA_CHORE_COMPLETED_BY] = []

                # Append if not already present
                completed_list = assigned_chore_data[const.DATA_CHORE_COMPLETED_BY]
                if (
                    isinstance(completed_list, list)
                    and completing_kid_name not in completed_list
                ):
                    completed_list.append(completing_kid_name)

    def _all_kids_approved(self, chore_id: str, assigned_kids: list[str]) -> bool:
        """Check if all assigned kids have approved the chore.

        Used for SHARED chores to determine if immediate reset should trigger.
        Only triggers reset when ALL kids have reached APPROVED state.

        Args:
            chore_id: The chore's internal ID
            assigned_kids: List of assigned kid IDs

        Returns:
            True if all kids have approved state, False otherwise
        """
        if not assigned_kids:
            return False

        for kid_id in assigned_kids:
            if not kid_id:
                continue
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )
            if state != const.CHORE_STATE_APPROVED:
                return False

        return True

    def _advance_rotation(
        self, chore_id: str, completing_kid_id: str, method: str = "auto"
    ) -> dict[str, Any] | None:
        """Advance rotation turn to next kid after approval.

        Phase 3 Step 1: Rotation turn advancement logic.
        Called after successful approval, before _persist().

        Args:
            chore_id: The chore's internal ID
            completing_kid_id: The kid who just completed the chore
            method: "auto" (normal approval), "simple" (forced simple),
                   "smart" (forced smart), or "manual" (service call)

        Returns:
            Signal payload dict for CHORE_ROTATION_ADVANCED, or None if not rotation mode.
            Caller should emit signal after _persist() succeeds.
        """
        chore_data = self._coordinator.chores_data[chore_id]

        # Early exit if not rotation mode
        if not ChoreEngine.is_rotation_mode(chore_data):
            return None

        # Capture previous turn holder for signal
        previous_kid_id = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)

        # Determine rotation type
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        # Get assigned kids list
        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # Calculate next turn based on rotation type
        new_kid_id: str | None = None

        if method == "auto":
            # Determine method from completion criteria
            if completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SIMPLE:
                method = "simple"
            elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SMART:
                method = "smart"

        if method == "simple":
            # Simple rotation: round-robin by list index
            new_kid_id = ChoreEngine.calculate_next_turn_simple(
                assigned_kids, completing_kid_id
            )

        elif method == "smart":
            # Smart rotation: fairness-weighted selection
            # Query StatisticsManager for completed counts and last completed timestamps
            # Phase 3 Step 8: Methods now implemented - smart rotation enabled
            if hasattr(
                self.coordinator.statistics_manager, "get_chore_completed_counts"
            ):
                completed_counts = (
                    self.coordinator.statistics_manager.get_chore_completed_counts(
                        chore_id, assigned_kids
                    )
                )
                last_completed_timestamps = self.coordinator.statistics_manager.get_chore_last_completed_timestamps(
                    chore_id, assigned_kids
                )

                new_kid_id = ChoreEngine.calculate_next_turn_smart(
                    assigned_kids=assigned_kids,
                    completed_counts=completed_counts,
                    last_completed_timestamps=last_completed_timestamps,
                )
            else:
                # Fallback to simple rotation until Step 8 is complete
                const.LOGGER.debug(
                    "Smart rotation methods not yet implemented, using simple rotation"
                )
                new_kid_id = ChoreEngine.calculate_next_turn_simple(
                    assigned_kids, completing_kid_id
                )

        elif method == "manual":
            # Manual method: turn was already set by service call
            # Just emit signal, don't change rotation_current_kid_id
            new_kid_id = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)

        # Update rotation metadata
        if new_kid_id:
            chore_data[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = new_kid_id

        # Clear rotation override after advancement (D-15: cleared on next approval)
        chore_data[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False

        # Return payload for caller to emit after _persist()
        return {
            "chore_id": chore_id,
            "previous_kid_id": previous_kid_id,
            "new_kid_id": new_kid_id,
            "method": method,
        }

    def _handle_criteria_transition(
        self, chore_id: str, old_criteria: str, new_criteria: str
    ) -> None:
        """Handle completion_criteria changes (D-11 — criteria is mutable).

        When user edits chore's completion_criteria field, this method:
        - Validates rotation requirements (≥2 assigned kids)
        - Initializes/clears rotation fields as needed
        - Applies field changes from Engine transition logic
        - Persists changes and emits CHORE_UPDATED signal

        Args:
            chore_id: The chore's internal ID
            old_criteria: Previous completion_criteria value
            new_criteria: New completion_criteria value

        Raises:
            ServiceValidationError: If rotation criteria with <2 assigned kids
        """
        chore_data = self._coordinator.chores_data.get(chore_id)
        if not chore_data:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
            )

        # Get transition actions from Engine
        changes = ChoreEngine.get_criteria_transition_actions(
            old_criteria=old_criteria,
            new_criteria=new_criteria,
            chore_data=chore_data,
        )

        # Validate rotation requirements (D-14: rotation requires ≥2 kids)
        new_is_rotation = new_criteria in (
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
        )
        if new_is_rotation:
            assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            if len(assigned_kids) < 2:
                raise ServiceValidationError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_ROTATION_MIN_KIDS,
                )

        # Always update the completion_criteria field itself
        changes[const.DATA_CHORE_COMPLETION_CRITERIA] = new_criteria

        # Apply field changes to storage
        for field_name, new_value in changes.items():
            chore_data[field_name] = new_value  # type: ignore[literal-required]

        # Persist changes
        self._coordinator._persist_and_update()

        # Emit CHORE_UPDATED signal (Phase 4 UX listens for dashboard refresh)
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id=chore_id,
            updated_fields=list(changes.keys()),
        )

        const.LOGGER.debug(
            "Criteria transition: chore=%s %s→%s (applied %d changes)",
            chore_id,
            old_criteria,
            new_criteria,
            len(changes),
        )

    # ==========================================================================
    # PUBLIC ROTATION MANAGEMENT METHODS (Phase 3 Step 7 - v0.5.0)
    # ==========================================================================

    async def set_rotation_turn(self, chore_id: str, kid_id: str) -> None:
        """Set rotation turn to a specific kid.

        Called by: services.handle_set_rotation_turn (manual user intervention)

        Args:
            chore_id: Internal ID of the rotation chore
            kid_id: Internal ID of the kid to receive the turn

        Raises:
            ServiceValidationError: If chore is not rotation mode or kid not assigned
        """
        chores_data = self._coordinator._data[const.DATA_CHORES]

        if chore_id not in chores_data:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
            )

        chore_info = chores_data[chore_id]

        # Validate rotation mode
        if not ChoreEngine.is_rotation_mode(chore_info):
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ROTATION,
            )

        # Validate kid is assigned
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if kid_id not in assigned_kids:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_KID_NOT_ASSIGNED,
            )

        # Set the turn
        chore_info[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = kid_id

        # Persist
        self._coordinator._persist_and_update()

        # Emit signal
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id=chore_id,
            updated_fields=[const.DATA_CHORE_ROTATION_CURRENT_KID_ID],
        )

        const.LOGGER.info(
            "Set rotation turn: chore=%s kid=%s",
            chore_id,
            kid_id,
        )

    async def reset_rotation(self, chore_id: str) -> None:
        """Reset rotation to first assigned kid.

        Called by: services.handle_reset_rotation (manual reset to start)

        Args:
            chore_id: Internal ID of the rotation chore

        Raises:
            ServiceValidationError: If chore is not rotation mode or has no assigned kids
        """
        chores_data = self._coordinator._data[const.DATA_CHORES]

        if chore_id not in chores_data:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
            )

        chore_info = chores_data[chore_id]

        # Validate rotation mode
        if not ChoreEngine.is_rotation_mode(chore_info):
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ROTATION,
            )

        # Validate has assigned kids
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if not assigned_kids:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NO_ASSIGNED_KIDS,
            )

        # Reset to first kid
        first_kid = assigned_kids[0]
        chore_info[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = first_kid

        # Persist
        self._coordinator._persist_and_update()

        # Emit signal
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id=chore_id,
            updated_fields=[const.DATA_CHORE_ROTATION_CURRENT_KID_ID],
        )

        const.LOGGER.info(
            "Reset rotation: chore=%s → kid=%s",
            chore_id,
            first_kid,
        )

    async def open_rotation_cycle(self, chore_id: str) -> None:
        """Open rotation cycle - allow any assigned kid to claim once.

        Called by: services.handle_open_rotation_cycle (override for one cycle)

        Args:
            chore_id: Internal ID of the rotation chore

        Raises:
            ServiceValidationError: If chore is not rotation mode
        """
        chores_data = self._coordinator._data[const.DATA_CHORES]

        if chore_id not in chores_data:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
            )

        chore_info = chores_data[chore_id]

        # Validate rotation mode
        if not ChoreEngine.is_rotation_mode(chore_info):
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_ROTATION,
            )

        # Set cycle override flag (temp allow any kid to claim)
        chore_info[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = True

        # Persist
        self._coordinator._persist_and_update()

        # Emit signal
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id=chore_id,
            updated_fields=[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE],
        )

        const.LOGGER.info(
            "Opened rotation cycle: chore=%s",
            chore_id,
        )

    def _apply_effect(self, effect: TransitionEffect, chore_id: str) -> None:
        """Apply a single TransitionEffect to coordinator data.

        Args:
            effect: The effect to apply
            chore_id: The chore's internal ID
        """
        kid_id = effect.kid_id
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Apply state change
        if effect.new_state:
            state_to_persist = effect.new_state
            if state_to_persist not in const.CHORE_PERSISTED_KID_STATES:
                const.LOGGER.debug(
                    "Normalizing non-persisted chore state to pending: %s",
                    state_to_persist,
                )
                state_to_persist = const.CHORE_STATE_PENDING
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = state_to_persist

        # Phase 2: completed_by_other_chores list management removed
        # SHARED_FIRST blocking is now computed dynamically in can_claim_chore()

        # v43+: Points are tracked in periods.all_time.points via StatisticsEngine
        # Don't store in deprecated total_points field - StatisticsManager handles via signals

        # Clear claimed_by
        if effect.clear_claimed_by:
            kid_chore_data.pop(const.DATA_CHORE_CLAIMED_BY, None)

        # Clear completed_by
        if effect.clear_completed_by:
            kid_chore_data.pop(const.DATA_CHORE_COMPLETED_BY, None)

        # Set claimed_by
        if effect.set_claimed_by:
            kid_chore_data[const.DATA_CHORE_CLAIMED_BY] = effect.set_claimed_by

        # Set completed_by
        if effect.set_completed_by:
            kid_chore_data[const.DATA_CHORE_COMPLETED_BY] = effect.set_completed_by

    def _update_global_state(self, chore_id: str) -> None:
        """Update the chore-level global state based on all assigned kids' states.

        This mirrors the logic from coordinator's _transition_chore_state to ensure
        the chore-level state (chores_data[chore_id][DATA_CHORE_STATE]) is consistent
        with the per-kid states (kid_chore_data[chore_id][DATA_KID_CHORE_DATA_STATE]).

        Args:
            chore_id: The chore's internal ID
        """
        chore_data = self._coordinator.chores_data.get(chore_id)
        if not chore_data:
            return

        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if not assigned_kids:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN
            return

        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_SHARED
        )

        # Single kid - use their state directly
        if len(assigned_kids) == 1:
            kid_chore_data = self._get_kid_chore_data(assigned_kids[0], chore_id)
            state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )
            chore_data[const.DATA_CHORE_STATE] = state
            return

        # Multiple kids - count states
        count_pending = 0
        count_claimed = 0
        count_approved = 0
        count_overdue = 0
        # Phase 2: count_completed_by_other removed (state eliminated from FSM)

        for kid_id in assigned_kids:
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            state = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )

            if state == const.CHORE_STATE_APPROVED:
                count_approved += 1
            elif state == const.CHORE_STATE_CLAIMED:
                count_claimed += 1
            elif state in (const.CHORE_STATE_OVERDUE, const.CHORE_STATE_MISSED):
                # Phase 2: missed maps like overdue for global state
                count_overdue += 1
            elif state == const.CHORE_STATE_NOT_MY_TURN:
                # Phase 2: not_my_turn is cosmetic, ignore for global aggregation
                # (rotation chores aggregate based on turn-holder's state)
                pass
            # Phase 2: waiting and all other states count as pending
            else:
                count_pending += 1

        total = len(assigned_kids)

        # If all kids are in the same state
        if count_pending == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING
        elif count_claimed == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED
        elif count_approved == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED
        elif count_overdue == total:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE

        # SHARED_FIRST: global state tracks the claimant's progression
        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            if count_approved > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED
            elif count_claimed > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED
            elif count_overdue > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
            else:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_PENDING

        # SHARED: partial states
        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            if count_overdue > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_OVERDUE
            elif count_approved > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_APPROVED_IN_PART
            elif count_claimed > 0:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_CLAIMED_IN_PART
            else:
                chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_UNKNOWN

        # INDEPENDENT: multiple kids with different states
        else:
            chore_data[const.DATA_CHORE_STATE] = const.CHORE_STATE_INDEPENDENT

    def _set_approval_period_start(
        self,
        chore_id: str,
        kid_id: str | None,
        timestamp: str,
    ) -> None:
        """Set the approval period start timestamp.

        Handles INDEPENDENT vs SHARED storage location:
        - INDEPENDENT: Sets per-kid approval_period_start in kid_chore_data
        - SHARED/SHARED_FIRST: Sets chore-level approval_period_start

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID (required for INDEPENDENT, can be None for SHARED)
            timestamp: ISO format timestamp to set
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return

        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            if not kid_id:
                const.LOGGER.warning(
                    "Cannot set approval_period_start for INDEPENDENT chore without kid_id"
                )
                return
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = timestamp
        else:
            # SHARED/SHARED_FIRST: chore-level
            chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = timestamp

    def _reset_approval_period(
        self,
        kid_id: str,
        chore_id: str,
        timestamp: str | None = None,
        *,
        force_update: bool = False,
    ) -> None:
        """Reset the approval period tracking for a kid+chore.

        Sets approval_period_start to mark the start of a new approval period.
        The chore_is_approved_in_period() check compares:
            last_approved >= approval_period_start

        So after calling this, if last_approved was from before the period start,
        the chore becomes claimable again because it's not approved in the current period.

        For INDEPENDENT chores: stores approval_period_start in kid_chore_data
        For SHARED chores: stores at chore level

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            timestamp: Optional timestamp to use. If None, uses current time.
                      Pass same timestamp as last_approved to ensure consistency.
            force_update: If True, always update approval_period_start even if
                         already set. Use this for scheduled resets.
                         If False (default), only set if not already set
                         (for tracking first approval in period).
        """

        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return

        now_iso = timestamp or dt_now_iso()
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_SHARED
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Store per-kid approval_period_start in kid_chore_data
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now_iso
        # SHARED/SHARED_FIRST: Store at chore level
        # Only set if not already set OR force_update is True
        # - force_update=False (default): preserves period start for all kids
        #   when multiple kids are approved in the same period
        # - force_update=True: used by scheduled resets to invalidate previous approvals
        elif force_update or not chore_info.get(const.DATA_CHORE_APPROVAL_PERIOD_START):
            chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso

    def _set_claimed_completed_by(
        self,
        chore_id: str,
        kid_id: str,
        field: str,
        value: str,
    ) -> None:
        """Set claimed_by or completed_by field.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID
            field: DATA_CHORE_CLAIMED_BY or DATA_CHORE_COMPLETED_BY
            value: The kid name to set
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        kid_chore_data[field] = value

    def _clear_claimed_completed_by(
        self,
        chore_id: str,
        kid_id: str,
        field: str,
    ) -> None:
        """Clear claimed_by or completed_by field.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid's internal ID
            field: DATA_CHORE_CLAIMED_BY or DATA_CHORE_COMPLETED_BY
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        kid_chore_data.pop(field, None)

    def _set_last_completed_timestamp(
        self,
        chore_id: str,
        kid_id: str,
        effective_date_iso: str,
        fallback_iso: str,
    ) -> None:
        """Set chore-level last_completed based on completion criteria.

        Args:
            chore_id: The chore's internal ID
            kid_id: The kid who completed (used for INDEPENDENT/SHARED_FIRST)
            effective_date_iso: When the kid did the work (claim timestamp)
            fallback_iso: Fallback timestamp if no claims found (now_iso)
        """
        chore_data = self._coordinator.chores_data[chore_id]
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Store in per-kid data (each kid has their own completion)
            kid_chore_data_item = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data_item[const.DATA_KID_CHORE_DATA_LAST_COMPLETED] = (
                effective_date_iso
            )

        elif completion_criteria == const.COMPLETION_CRITERIA_SHARED:
            # SHARED_ALL: Collect all assigned kids' last_claimed, use max
            kids_assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            claim_timestamps: list[str] = []
            for assigned_kid_id in kids_assigned:
                if not assigned_kid_id:
                    continue
                kid_chore_data_item = self._get_kid_chore_data(
                    assigned_kid_id, chore_id
                )
                claim_ts = kid_chore_data_item.get(
                    const.DATA_KID_CHORE_DATA_LAST_CLAIMED
                )
                if claim_ts:
                    claim_timestamps.append(claim_ts)
            # Use latest claim (or fallback if none found)
            chore_data[const.DATA_CHORE_LAST_COMPLETED] = (
                max(claim_timestamps) if claim_timestamps else fallback_iso
            )

        else:
            # SHARED_FIRST: Use winner's claim timestamp
            chore_data[const.DATA_CHORE_LAST_COMPLETED] = effective_date_iso

    # =========================================================================
    # §7 SCHEDULING METHODS (due date rescheduling)
    # =========================================================================
    # Handle due date recalculation after approvals and scheduled resets.
    # Called from workflow methods and timer-driven operations.

    def _record_chore_missed(
        self,
        kid_id: str,
        chore_id: str,
        due_date: datetime | None = None,
        reason: str | None = None,
    ) -> None:
        """Record that a chore was missed (delegate to StatisticsManager).

        Phase 5: Updates last_missed timestamp and calculates missed streak.
        Emits CHORE_MISSED signal for StatisticsManager to record period stats.

        Missed streak logic:
        - Simple increment (not schedule-aware): previous_missed_streak + 1
        - Stored at chore data level (survives retention pruning)
        - Reset to 0 on chore completion (in approve_chore)

        Args:
            kid_id: The kid's internal ID
            chore_id: The chore's internal ID
            due_date: Optional due date for the missed chore (D-07)
            reason: Optional reason for missed chore (D-07)
        """
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

        # Get kid name for notification standard
        kid_info: KidData | dict[str, Any] = self.coordinator.kids_data.get(kid_id, {})
        kid_name = str(kid_info.get(const.DATA_KID_NAME, "Unknown"))

        # Get previous missed streak from chore data (not from daily buckets)
        # Phase 5: Read from chore level to survive retention pruning
        previous_missed_streak = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_CURRENT_MISSED_STREAK, 0
        )

        # Calculate new missed streak (simple increment, not schedule-aware)
        new_missed_streak = previous_missed_streak + 1

        # Store current missed streak at chore data level (never pruned)
        kid_chore_data[const.DATA_KID_CHORE_DATA_CURRENT_MISSED_STREAK] = (
            new_missed_streak
        )

        # Update top-level timestamp (like last_approved, last_claimed)
        kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_MISSED] = dt_now_iso()

        # Ensure periods structure exists for StatisticsManager to write to
        # Phase 3B Landlord/Tenant: ChoreManager must create containers before emitting
        self._ensure_kid_structures(kid_id, chore_id)

        # Persist changes before emitting signal (transactional integrity)
        self.coordinator._persist_and_update()

        # Emit signal for StatisticsManager to handle period buckets
        # Pass missed_streak_tally for daily bucket snapshot (display purposes)
        # Phase 3 Step 2: Include optional due_date and reason fields (D-07)
        signal_payload: dict[str, Any] = {
            "kid_id": kid_id,
            "chore_id": chore_id,
            "kid_name": kid_name,
            "missed_streak_tally": new_missed_streak,
        }
        if due_date is not None:
            signal_payload["due_date"] = (
                due_date.isoformat() if isinstance(due_date, datetime) else due_date
            )
        if reason is not None:
            signal_payload["reason"] = reason

        self.emit(const.SIGNAL_SUFFIX_CHORE_MISSED, **signal_payload)

    def _reschedule_chore_due(
        self,
        chore_id: str,
        kid_id: str | None = None,
    ) -> None:
        """Unified dispatcher for due date rescheduling.

        Handles INDEPENDENT vs SHARED based on completion criteria:
        - INDEPENDENT + kid_id: Reschedules that kid's per-kid due date
        - INDEPENDENT + no kid_id: Reschedules all assigned kids
        - SHARED/SHARED_FIRST: Reschedules chore-level due date

        Args:
            chore_id: The chore's internal ID
            kid_id: Optional kid_id for INDEPENDENT per-kid rescheduling
        """
        chore_info = self._coordinator.chores_data.get(chore_id)
        if not chore_info:
            return

        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            if kid_id:
                # Single kid reschedule
                self._reschedule_chore_next_due_date_for_kid(
                    chore_info, chore_id, kid_id
                )
            else:
                # All assigned kids
                for assigned_kid_id in chore_info.get(
                    const.DATA_CHORE_ASSIGNED_KIDS, []
                ):
                    if assigned_kid_id:
                        self._reschedule_chore_next_due_date_for_kid(
                            chore_info, chore_id, assigned_kid_id
                        )
        else:
            # SHARED/SHARED_FIRST: chore-level
            self._reschedule_chore_next_due(chore_info)

    def _reschedule_chore_next_due(self, chore_info: ChoreData) -> None:
        """Reschedule chore's next due date (chore-level for SHARED chores)."""
        due_date_str = chore_info.get(const.DATA_CHORE_DUE_DATE)
        if not due_date_str:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Skipping (no due date for %s)",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Parse current due date
        original_due_utc = dt_to_utc(due_date_str)
        if not original_due_utc:
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Unable to parse due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Extract completion timestamp for CUSTOM_FROM_COMPLETE
        completion_utc = None
        last_completed_str = chore_info.get(const.DATA_CHORE_LAST_COMPLETED)
        if last_completed_str:
            completion_utc = dt_to_utc(last_completed_str)

        # Use schedule engine for calculation
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc,
            chore_info,
            completion_timestamp=completion_utc,
            reference_time=dt_util.utcnow(),
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule: Failed to calculate next due date for %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return

        # Update chore-level due date
        chore_info[const.DATA_CHORE_DUE_DATE] = next_due_utc.isoformat()
        chore_id = chore_info.get(const.DATA_CHORE_INTERNAL_ID)

        if not chore_id:
            const.LOGGER.error(
                "Chore Due Date - Reschedule: Missing chore_id for chore: %s",
                chore_info.get(const.DATA_CHORE_NAME, "Unknown"),
            )
            return

        # NOTE: State transitions are handled by callers (approve_chore for
        # UPON_COMPLETION, _transition_chore_state for scheduled resets).
        # This method ONLY reschedules due dates.

        const.LOGGER.info(
            "Chore Due Date - Rescheduled (SHARED): %s, from %s to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            dt_util.as_local(original_due_utc).isoformat(),
            dt_util.as_local(next_due_utc).isoformat(),
        )

    def _reschedule_chore_next_due_date_for_kid(
        self, chore_info: ChoreData, chore_id: str, kid_id: str
    ) -> None:
        """Reschedule per-kid due date (INDEPENDENT mode).

        Updates DATA_CHORE_PER_KID_DUE_DATES[kid_id].
        Used for INDEPENDENT chores (each kid has own due date).
        """
        kid_info: KidData | dict[str, Any] = self._coordinator.kids_data.get(kid_id, {})

        # Get per-kid current due date
        per_kid_due_dates = chore_info.get(const.DATA_CHORE_PER_KID_DUE_DATES, {})
        current_due_str = per_kid_due_dates.get(kid_id)

        if not current_due_str:
            const.LOGGER.debug(
                "Chore Due Date - No due date for chore %s, kid %s; preserving None",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # Parse current due date
        try:
            original_due_utc = dt_to_utc(current_due_str)
        except (ValueError, TypeError, AttributeError):
            const.LOGGER.debug(
                "Chore Due Date - Reschedule: Unable to parse due date for %s, kid %s",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            if kid_id in per_kid_due_dates:
                del per_kid_due_dates[kid_id]
            chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates
            return

        # Extract per-kid completion timestamp (Phase 5: use last_claimed for work date)
        # Fallback hierarchy: last_claimed → last_approved (backward compat)
        completion_utc = None
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        last_claimed_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
        if last_claimed_str:
            completion_utc = dt_to_utc(last_claimed_str)
        else:
            # Backward compat: fall back to last_approved for legacy data
            last_approved_str = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_LAST_APPROVED
            )
            if last_approved_str:
                completion_utc = dt_to_utc(last_approved_str)

        # Build chore info for calculation with per-kid overrides
        chore_info_for_calc = dict(chore_info)
        per_kid_applicable_days = chore_info.get(
            const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {}
        )
        if kid_id in per_kid_applicable_days:
            chore_info_for_calc[const.DATA_CHORE_APPLICABLE_DAYS] = (
                per_kid_applicable_days[kid_id]
            )
        per_kid_times = chore_info.get(const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
        if kid_id in per_kid_times:
            chore_info_for_calc[const.DATA_CHORE_DAILY_MULTI_TIMES] = per_kid_times[
                kid_id
            ]

        # Use schedule engine
        next_due_utc = calculate_next_due_date_from_chore_info(
            original_due_utc,
            cast("ChoreData", chore_info_for_calc),
            completion_timestamp=completion_utc,
            reference_time=dt_util.utcnow(),
        )
        if not next_due_utc:
            const.LOGGER.warning(
                "Chore Due Date - Reschedule: Failed to calculate next due for %s, kid %s",
                chore_info.get(const.DATA_CHORE_NAME),
                kid_id,
            )
            return

        # Update per-kid storage
        per_kid_due_dates[kid_id] = next_due_utc.isoformat()
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates

        # NOTE: State transitions are handled by callers (approve_chore for
        # UPON_COMPLETION, _transition_chore_state for scheduled resets).
        # This method ONLY reschedules due dates.

        const.LOGGER.info(
            "Chore Due Date - Rescheduled (INDEPENDENT): chore %s, kid %s, to %s",
            chore_info.get(const.DATA_CHORE_NAME),
            kid_info.get(const.DATA_KID_NAME),
            dt_util.as_local(next_due_utc).isoformat() if next_due_utc else "None",
        )

    # =========================================================================
    # DATA RESET - Transactional Data Reset for Chores Domain
    # =========================================================================

    async def data_reset_chores(
        self,
        scope: str,
        kid_id: str | None = None,
        item_id: str | None = None,
    ) -> None:
        """Reset runtime data for chores domain.

        Clears transactional/runtime data while preserving configuration.
        Uses field frozensets from data_builders as source of truth.

        Args:
            scope: Reset scope (global, kid, item_type, item)
            kid_id: Target kid ID for kid/item scopes (optional)
            item_id: Target chore ID for item scope (optional)

        Emits:
            SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE with scope, kid_id, item_id
        """
        const.LOGGER.info(
            "Data reset: chores domain - scope=%s, kid_id=%s, item_id=%s",
            scope,
            kid_id,
            item_id,
        )

        chores_data = self._coordinator.chores_data
        kids_data = self._coordinator.kids_data

        # Determine which chores to reset
        if item_id:
            # Item scope - single chore
            chore_ids = [item_id] if item_id in chores_data else []
        elif kid_id:
            # Kid scope - only chores assigned to this kid
            chore_ids = [
                chore_id
                for chore_id, chore_info in chores_data.items()
                if kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
            ]
        else:
            # Global or item_type scope - all chores
            chore_ids = list(chores_data.keys())

        # STEP 1: Clear due dates and transition chores to PENDING
        # This uses the proper state machine to handle all side effects
        for chore_id in chore_ids:
            chore_info = chores_data.get(chore_id)
            if not chore_info:
                continue

            # set_due_date(None, kid_id) clears due dates and transitions to PENDING
            # - If kid_id=None (global scope): resets all assigned kids
            # - If kid_id=<uuid> (kid scope): resets only that kid (INDEPENDENT chores)
            # Proper state machine handling: ownership clearing, global state update, signals
            await self.set_due_date(chore_id, None, kid_id=kid_id)

        # STEP 2: Clear chore-side runtime fields
        for chore_id in chore_ids:
            chore_info = chores_data.get(chore_id)
            if not chore_info:
                continue

            # Cast for dynamic field access (TypedDict requires literal keys)
            chore_dict = cast("dict[str, Any]", chore_info)

            # Clear per-kid tracking lists
            for field in db._CHORE_PER_KID_RUNTIME_LISTS:
                if kid_id:
                    # Remove specific kid from lists
                    if field in chore_dict and isinstance(chore_dict[field], list):
                        if kid_id in chore_dict[field]:
                            chore_dict[field].remove(kid_id)
                else:
                    # Clear entire list
                    chore_dict[field] = []

            # Clear per-kid configuration dicts (for kid-scope resets only)
            # These are preserved on global resets (they're config, not runtime)
            if kid_id:
                per_kid_due_dates = chore_dict.get(
                    const.DATA_CHORE_PER_KID_DUE_DATES, {}
                )
                per_kid_due_dates.pop(kid_id, None)

                per_kid_days = chore_dict.get(
                    const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {}
                )
                per_kid_days.pop(kid_id, None)

                per_kid_multi = chore_dict.get(
                    const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {}
                )
                per_kid_multi.pop(kid_id, None)

            # Clear timestamp fields
            chore_dict[const.DATA_CHORE_LAST_CLAIMED] = None
            chore_dict[const.DATA_CHORE_LAST_COMPLETED] = None

        # STEP 3: Clear kid-side runtime structures
        # Determine which kids to process
        if kid_id:
            kid_ids = [kid_id] if kid_id in kids_data else []
        else:
            kid_ids = list(kids_data.keys())

        for loop_kid_id in kid_ids:
            kid_info = kids_data.get(loop_kid_id)
            if not kid_info:
                continue

            # Cast for dynamic field access (TypedDict requires literal keys)
            kid_dict = cast("dict[str, Any]", kid_info)

            for field in db._CHORE_KID_RUNTIME_FIELDS:
                if field == const.DATA_KID_CHORE_DATA and item_id:
                    # Item scope - only clear data for specific chore
                    chore_data_dict = kid_dict.get(const.DATA_KID_CHORE_DATA, {})
                    chore_data_dict.pop(item_id, None)
                elif field in kid_dict:
                    # Clear entire structure
                    if isinstance(kid_dict[field], dict):
                        kid_dict[field] = {}
                    elif isinstance(kid_dict[field], list):
                        kid_dict[field] = []

        # Persist → Emit (per DEVELOPMENT_STANDARDS.md § 5.3)
        self._coordinator._persist_and_update()

        # Emit completion signal
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE,
            scope=scope,
            kid_id=kid_id,
            item_id=item_id,
        )

        const.LOGGER.info(
            "Data reset: chores domain complete - %d chores, %d kids affected",
            len(chore_ids),
            len(kid_ids),
        )
