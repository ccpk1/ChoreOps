"""Chore Engine - Pure logic for chore state transitions and calculations.

This engine provides stateless, pure Python functions for:
- State transition validation and calculation
- TransitionEffect planning for multi-assignee scenarios
- Point calculations with multipliers
- Completion criteria logic (SHARED, INDEPENDENT, SHARED_FIRST)
- Query functions for chore status checks

ARCHITECTURE: This is a pure logic engine with NO Home Assistant dependencies.
All functions are static methods that operate on passed-in data.
State management belongs in ChoreManager.

See docs/ARCHITECTURE.md for the Engine vs Manager distinction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import const
from ..utils.dt_utils import dt_parse_duration, dt_to_utc

if TYPE_CHECKING:
    from datetime import datetime

    from ..type_defs import AssigneeData, ChoreData, ScheduleConfig


# =============================================================================
# CHORE ACTION CONSTANTS
# =============================================================================

# Actions that can be performed on a chore (used by calculate_transition)
CHORE_ACTION_CLAIM = "claim"
CHORE_ACTION_APPROVE = "approve"
CHORE_ACTION_DISAPPROVE = "disapprove"
CHORE_ACTION_UNDO = "undo"
CHORE_ACTION_RESET = "reset"
CHORE_ACTION_OVERDUE = "overdue"

# Relaxed overdue types (P5 FSM check - v0.5.0)
# These types transition to overdue state but keep chores claimable
_RELAXED_OVERDUE_TYPES: frozenset[str] = frozenset(
    {
        const.OVERDUE_HANDLING_AT_DUE_DATE,
        const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
        const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
        const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED,
    }
)


# =============================================================================
# TRANSITION EFFECT DATA STRUCTURE
# =============================================================================


@dataclass
class TransitionEffect:
    """Effect of a chore state transition for a single assignee.

    Returned by ChoreEngine.calculate_transition() to describe
    what should happen for each affected assignee.

    Attributes:
        assignee_id: The assignee affected by this transition
        new_state: Target chore state for this assignee
        update_stats: Whether this transition counts toward stats (streaks, totals)
                     True for normal actions, False for undo/corrections
        points: Points to award (positive) or deduct (negative), 0 for no change
        clear_claimed_by: Whether to clear claimed_by field
        clear_completed_by: Whether to clear completed_by field
        set_claimed_by: Name to set as claimed_by (or None)
        set_completed_by: Name to set as completed_by (or None)
    """

    assignee_id: str
    new_state: str
    update_stats: bool = True
    points: float = 0.0
    clear_claimed_by: bool = False
    clear_completed_by: bool = False
    set_claimed_by: str | None = None
    set_completed_by: str | None = None


# =============================================================================
# CHORE ENGINE
# =============================================================================


class ChoreEngine:
    """Pure logic engine for chore state transitions and calculations.

    All methods are static - no instance state. This enables easy unit testing
    without any Home Assistant mocking.
    """

    # Valid state transitions matrix
    VALID_TRANSITIONS: dict[str, list[str]] = {
        # From PENDING: Can be claimed or go overdue
        const.CHORE_STATE_PENDING: [
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_OVERDUE,
        ],
        # From CLAIMED: Awaiting approver decision
        const.CHORE_STATE_CLAIMED: [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_PENDING,  # Disapproved or undo
            const.CHORE_STATE_OVERDUE,  # Due date passed while claimed
        ],
        # From APPROVED: Reset for next occurrence
        const.CHORE_STATE_APPROVED: [
            const.CHORE_STATE_PENDING,  # Scheduled reset
        ],
        # From OVERDUE: Can still be claimed or reset
        const.CHORE_STATE_OVERDUE: [
            const.CHORE_STATE_CLAIMED,  # Assignee claims overdue chore
            const.CHORE_STATE_PENDING,  # Manual/scheduled reset
            const.CHORE_STATE_APPROVED,  # Approver completes on behalf
        ],
        # Global states (multi-assignee aggregation)
        const.CHORE_STATE_CLAIMED_IN_PART: [
            const.CHORE_STATE_APPROVED_IN_PART,
            const.CHORE_STATE_CLAIMED,
            const.CHORE_STATE_PENDING,
        ],
        const.CHORE_STATE_APPROVED_IN_PART: [
            const.CHORE_STATE_APPROVED,
            const.CHORE_STATE_PENDING,
        ],
    }

    # =========================================================================
    # STATE TRANSITION LOGIC
    # =========================================================================

    @staticmethod
    def can_transition(current_state: str, target_state: str) -> bool:
        """Validate if a state transition is allowed.

        Args:
            current_state: Current chore state
            target_state: Desired new state

        Returns:
            True if transition is valid, False otherwise
        """
        valid_targets = ChoreEngine.VALID_TRANSITIONS.get(current_state, [])
        return target_state in valid_targets

    @staticmethod
    def calculate_transition(
        chore_data: ChoreData | dict[str, Any],
        actor_assignee_id: str,
        action: str,
        assigned_assignees: list[str] | None = None,
        assignee_name: str = "Unknown",
        skip_stats: bool = False,
        is_overdue: bool = False,
        **legacy_kwargs: Any,
    ) -> list[TransitionEffect]:
        """Calculate transition effects for ALL assignees based on ONE action.

        This is the core planning method. It determines what state changes
        and side effects should occur for each assigned assignee when one assignee
        performs an action.

        Args:
            chore_data: The chore being acted upon
            actor_assignee_id: The assignee performing the action
            action: One of CHORE_ACTION_* values
            assigned_assignees: All assignees assigned to this chore
            assignee_name: Display name of actor assignee (for claimed_by/completed_by)
            skip_stats: If True, mark effects as update_stats=False
            is_overdue: If True, chore is past due (for disapprove action)

        Returns:
            List of TransitionEffect describing changes for each affected assignee
        """
        effects: list[TransitionEffect] = []
        if assigned_assignees is None:
            legacy_assigned_assignees = legacy_kwargs.pop("assignees_assigned", None)
            assigned_assignees = (
                legacy_assigned_assignees
                if isinstance(legacy_assigned_assignees, list)
                else []
            )

        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        points = float(chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, 0.0))

        # === CLAIM ACTION ===
        if action == CHORE_ACTION_CLAIM:
            effects = ChoreEngine._plan_claim_effects(
                completion_criteria,
                actor_assignee_id,
                assigned_assignees,
                assignee_name,
            )

        # === APPROVE ACTION ===
        elif action == CHORE_ACTION_APPROVE:
            effects = ChoreEngine._plan_approve_effects(
                completion_criteria,
                actor_assignee_id,
                assigned_assignees,
                assignee_name,
                points,
            )

        # === DISAPPROVE ACTION ===
        elif action == CHORE_ACTION_DISAPPROVE:
            effects = ChoreEngine._plan_disapprove_effects(
                completion_criteria,
                actor_assignee_id,
                assigned_assignees,
                is_overdue,
            )

        # === UNDO ACTION ===
        elif action == CHORE_ACTION_UNDO:
            effects = ChoreEngine._plan_undo_effects(
                completion_criteria,
                actor_assignee_id,
                assigned_assignees,
                is_overdue,
            )
            # Undo never updates stats
            skip_stats = True

        # === RESET ACTION (scheduled) ===
        elif action == CHORE_ACTION_RESET:
            effects = ChoreEngine._plan_reset_effects(assigned_assignees)

        # === OVERDUE ACTION ===
        elif action == CHORE_ACTION_OVERDUE:
            effects.append(
                TransitionEffect(
                    assignee_id=actor_assignee_id,
                    new_state=const.CHORE_STATE_OVERDUE,
                    update_stats=True,
                )
            )

        # Apply skip_stats flag if set
        if skip_stats:
            for effect in effects:
                effect.update_stats = False

        return effects

    @staticmethod
    def _plan_claim_effects(
        criteria: str,
        actor_assignee_id: str,
        assigned_assignees: list[str],
        assignee_name: str,
    ) -> list[TransitionEffect]:
        """Plan effects for a claim action.

        Phase 2: SHARED_FIRST no longer sets completed_by_other state.
        Blocking is computed dynamically in can_claim_chore().
        """
        effects: list[TransitionEffect] = []

        # All criteria: Only actor transitions to CLAIMED
        # SHARED_FIRST blocking is computed in validation, not stored
        effects.append(
            TransitionEffect(
                assignee_id=actor_assignee_id,
                new_state=const.CHORE_STATE_CLAIMED,
                update_stats=True,
                set_claimed_by=assignee_name,
            )
        )

        return effects

    @staticmethod
    def _plan_approve_effects(
        criteria: str,
        actor_assignee_id: str,
        assigned_assignees: list[str],
        assignee_name: str,
        points: float,
    ) -> list[TransitionEffect]:
        """Plan effects for an approve action.

        Phase 2: SHARED_FIRST no longer sets completed_by_other state.
        Other assignees remain in their current state (pending/overdue).
        """
        effects: list[TransitionEffect] = []

        # Only the approving assignee transitions to APPROVED
        effects.append(
            TransitionEffect(
                assignee_id=actor_assignee_id,
                new_state=const.CHORE_STATE_APPROVED,
                update_stats=True,
                points=points,
                set_completed_by=assignee_name,
            )
        )

        # SHARED_FIRST: No state changes for other assignees
        # They stay pending/overdue and are blocked by computed logic

        return effects

    @staticmethod
    def _plan_disapprove_effects(
        criteria: str,
        actor_assignee_id: str,
        assigned_assignees: list[str],
        is_overdue: bool,
    ) -> list[TransitionEffect]:
        """Plan effects for a disapprove action.

        Args:
            criteria: Completion criteria (SHARED, INDEPENDENT, SHARED_FIRST)
            actor_assignee_id: The assignee being disapproved
            assigned_assignees: All assignees assigned to chore
            is_overdue: If True, chore is past due (return to overdue state)
        """
        effects: list[TransitionEffect] = []

        # Determine target state: overdue if past due date, otherwise pending
        target_state = (
            const.CHORE_STATE_OVERDUE if is_overdue else const.CHORE_STATE_PENDING
        )

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Reset ALL assignees to target state (overdue or pending)
            for assignee_id in assigned_assignees:
                effects.append(
                    TransitionEffect(
                        assignee_id=assignee_id,
                        new_state=target_state,
                        update_stats=(
                            assignee_id == actor_assignee_id
                        ),  # Only actor gets stat
                        clear_claimed_by=True,
                        clear_completed_by=True,
                    )
                )
        else:
            # INDEPENDENT or SHARED: Only actor transitions
            effects.append(
                TransitionEffect(
                    assignee_id=actor_assignee_id,
                    new_state=target_state,
                    update_stats=True,
                )
            )

        return effects

    @staticmethod
    def _plan_undo_effects(
        criteria: str,
        actor_assignee_id: str,
        assigned_assignees: list[str],
        is_overdue: bool,
    ) -> list[TransitionEffect]:
        """Plan effects for an undo (assignee self-undo) action.

        Args:
            criteria: Completion criteria (SHARED, INDEPENDENT, SHARED_FIRST)
            actor_assignee_id: The assignee performing the undo
            assigned_assignees: All assignees assigned to chore
            is_overdue: If True, chore is past due (return to overdue state)
        """
        effects: list[TransitionEffect] = []

        # Determine target state: overdue if past due date, otherwise pending
        target_state = (
            const.CHORE_STATE_OVERDUE if is_overdue else const.CHORE_STATE_PENDING
        )

        if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
            # SHARED_FIRST: Reset ALL assignees to target state (overdue or pending)
            for assignee_id in assigned_assignees:
                effects.append(
                    TransitionEffect(
                        assignee_id=assignee_id,
                        new_state=target_state,
                        update_stats=False,  # Undo never updates stats
                        clear_claimed_by=True,
                        clear_completed_by=True,
                    )
                )
        else:
            effects.append(
                TransitionEffect(
                    assignee_id=actor_assignee_id,
                    new_state=target_state,
                    update_stats=False,
                )
            )

        return effects

    @staticmethod
    def _plan_reset_effects(assigned_assignees: list[str]) -> list[TransitionEffect]:
        """Plan effects for a scheduled reset."""
        return [
            TransitionEffect(
                assignee_id=assignee_id,
                new_state=const.CHORE_STATE_PENDING,
                update_stats=False,
                clear_claimed_by=True,
                clear_completed_by=True,
            )
            for assignee_id in assigned_assignees
        ]

    # =========================================================================
    # VALIDATION LOGIC
    # =========================================================================

    @staticmethod
    def can_claim_chore(
        assignee_chore_data: dict[str, Any],
        chore_data: ChoreData | dict[str, Any],
        has_pending_claim: bool,
        is_approved_in_period: bool,
        other_assignee_states: dict[str, str] | None = None,
        *,
        resolved_state: str | None = None,
        lock_reason: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check if a chore can be claimed by a specific assignee.

        v0.5.0 FSM integration: If resolved_state is provided (from
        resolve_assignee_chore_state), check for blocking states first.

        Args:
            assignee_chore_data: The assignee's tracking data for this chore
            chore_data: The chore definition
            has_pending_claim: Result of chore_has_pending_claim()
            is_approved_in_period: Result of chore_is_approved_in_period()
            other_assignee_states: Dict mapping assignee_id -> state for single-claimer check
                            (optional, only needed for single-claimer chores)
            resolved_state: Pre-calculated state from resolve_assignee_chore_state()
            lock_reason: Lock reason from resolve_assignee_chore_state()

        Returns:
            Tuple of (can_claim: bool, error_key: str | None)
        """
        # NEW — FSM-based blocking (v0.5.0 P3, P4, P6 states)
        if resolved_state in (
            const.CHORE_STATE_MISSED,
            const.CHORE_STATE_WAITING,
            const.CHORE_STATE_NOT_MY_TURN,
        ):
            claim_lock_reason = lock_reason or resolved_state
            if claim_lock_reason == const.CHORE_STATE_WAITING:
                return (False, const.TRANS_KEY_ERROR_CHORE_WAITING)
            if claim_lock_reason == const.CHORE_STATE_NOT_MY_TURN:
                return (False, const.TRANS_KEY_ERROR_CHORE_NOT_MY_TURN)
            if claim_lock_reason == const.CHORE_STATE_MISSED:
                return (False, const.TRANS_KEY_ERROR_CHORE_MISSED_LOCKED)
            return (False, const.TRANS_KEY_ERROR_ALREADY_CLAIMED)

        # Check multi-claim allowed
        allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)

        # Check 1: single-claimer blocking (shared_first + rotation via adapter)
        if ChoreEngine.is_single_claimer_mode(chore_data):
            if other_assignee_states:
                for other_state in other_assignee_states.values():
                    if other_state in (
                        const.CHORE_STATE_CLAIMED,
                        const.CHORE_STATE_APPROVED,
                    ):
                        return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

        # Check 2: pending claim blocks new claims (unless multi-claim)
        if not allow_multiple and has_pending_claim:
            return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

        # Check 3: already approved in current period (unless multi-claim)
        if not allow_multiple and is_approved_in_period:
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    @staticmethod
    def can_approve_chore(
        assignee_chore_data: dict[str, Any],
        chore_data: ChoreData | dict[str, Any],
        is_approved_in_period: bool,
    ) -> tuple[bool, str | None]:
        """Check if a chore can be approved for a specific assignee.

        Phase 2: completed_by_other check removed - SHARED_FIRST blocking
        only affects claims, not approvals (approver can still approve anyone).

        Args:
            assignee_chore_data: The assignee's tracking data for this chore
            chore_data: The chore definition
            is_approved_in_period: Result of chore_is_approved_in_period()

        Returns:
            Tuple of (can_approve: bool, error_key: str | None)
        """
        # Check: already approved (unless multi-claim)
        allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)
        if not allow_multiple and is_approved_in_period:
            return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

        return (True, None)

    @staticmethod
    def chore_has_pending_claim(
        assignee_chore_data: dict[str, Any],
    ) -> bool:
        """Check if a chore has a pending claim.

        Uses the pending_count counter which is incremented on claim and
        decremented on approve/disapprove.
        """
        pending_count = assignee_chore_data.get(
            const.DATA_USER_CHORE_DATA_PENDING_CLAIM_COUNT, 0
        )
        return pending_count > 0

    @staticmethod
    def chore_is_overdue(
        assignee_chore_data: dict[str, Any],
    ) -> bool:
        """Check if a chore is in overdue state for a specific assignee."""
        current_state = assignee_chore_data.get(const.DATA_USER_CHORE_DATA_STATE)
        return current_state == const.CHORE_STATE_OVERDUE

    @staticmethod
    def chore_allows_multiple_claims(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore allows multiple claims per approval period."""
        approval_reset_type = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        return approval_reset_type in (
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        )

    @staticmethod
    def is_shared_chore(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore uses shared completion criteria."""
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        return criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        )

    @staticmethod
    def uses_chore_level_due_date(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore uses a single chore-level due date.

        Returns True for completion criteria where due dates are shared across
        all assigned assignees.
        """
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        return criteria in (
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
        )

    @staticmethod
    def is_rotation_mode(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore uses rotation completion criteria.

        Returns True for rotation_simple and rotation_smart.
        Part of Logic Adapter pattern (D-12) for v0.5.0 rotation feature.
        """
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        return criteria in (
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
        )

    @staticmethod
    def is_single_claimer_mode(chore_data: ChoreData | dict[str, Any]) -> bool:
        """Check if chore allows only one assignee to claim per cycle.

        Returns True for shared_first and all rotation types.
        Part of Logic Adapter pattern (D-12) - prevents gremlin code across
        ~60 existing shared_first check sites.

        This adapter enables rotation types to transapproverly inherit the
        "single claimer" behavior without modifying existing three-way branches.
        """
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        return criteria in (
            const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
        )

    @staticmethod
    def get_chore_data_for_assignee(
        assignee_data: AssigneeData | dict[str, Any],
        chore_id: str,
    ) -> dict[str, Any]:
        """Get the chore data dict for a specific assignee+chore combination."""
        chore_tracking = assignee_data.get(const.DATA_USER_CHORE_DATA, {})
        return (
            chore_tracking.get(chore_id, {}) if isinstance(chore_tracking, dict) else {}
        )

    # =========================================================================
    # STATE RESOLUTION (v0.5.0 FSM)
    # =========================================================================

    @staticmethod
    def resolve_assignee_chore_state(
        chore_data: ChoreData | dict[str, Any],
        assignee_id: str,
        now: datetime,
        *,
        is_approved_in_period: bool,
        has_pending_claim: bool,
        due_date: datetime | None,
        due_window_start: datetime | None,
    ) -> tuple[str, str | None]:
        """Resolve the calculated display state for an assignee's chore.

        8-tier FSM evaluates conditions in priority order (first match wins).
        Returns (state, lock_reason) tuple. lock_reason is non-None only
        for blocking states (waiting, not_my_turn, missed).

        Priority order:
          P1: approved   P2: claimed      P3: not_my_turn  P4: missed
          P5: overdue    P6: waiting      P7: due          P8: pending

        Args:
            chore_data: The chore definition
            assignee_id: The assignee's internal ID
            now: Current datetime (timezone-aware)
            is_approved_in_period: Whether assignee already approved this cycle
            has_pending_claim: Whether assignee has unapproved claim
            due_date: Chore due date (timezone-aware), or None
            due_window_start: Claim window start (timezone-aware), or None

        Returns:
            Tuple of (state_string, lock_reason_or_None)
        """
        # P1 — Approved takes absolute precedence
        if is_approved_in_period:
            return (const.CHORE_STATE_APPROVED, None)

        # P2 — Pending claim awaiting approver action
        if has_pending_claim:
            return (const.CHORE_STATE_CLAIMED, None)

        # P3 — Rotation: not this assignee's turn
        if ChoreEngine.is_rotation_mode(chore_data):
            current_turn = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID)
            override = chore_data.get(const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE, False)

            if assignee_id != current_turn and not override:
                overdue_handling = chore_data.get(
                    const.DATA_CHORE_OVERDUE_HANDLING_TYPE
                )

                # STEAL EXCEPTION: overdue handling is allow_steal + past due date
                # In that case, not_my_turn blocking lifts — any assignee can claim
                if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL:
                    if due_date is not None and now > due_date:
                        pass  # Fall through — steal window is active
                    else:
                        return (
                            const.CHORE_STATE_NOT_MY_TURN,
                            const.CHORE_STATE_NOT_MY_TURN,
                        )
                else:
                    # Simple and Smart without steal: strict turn enforcement
                    return (
                        const.CHORE_STATE_NOT_MY_TURN,
                        const.CHORE_STATE_NOT_MY_TURN,
                    )

        # P4 — Missed lock (strict: no claiming allowed)
        overdue_type = chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
        if (
            overdue_type == const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
            and due_date is not None
            and now > due_date
        ):
            return (const.CHORE_STATE_MISSED, const.CHORE_STATE_MISSED)

        # P4.5 — Rotation steal window opened
        # For at_due_date_allow_steal, once past due the not_my_turn lock is
        # lifted (P3) and the chore should present as overdue/claimable.
        if (
            overdue_type == const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL
            and due_date is not None
            and now > due_date
        ):
            return (const.CHORE_STATE_OVERDUE, None)

        # P5 — Overdue (relaxed: still claimable)
        if (
            overdue_type in _RELAXED_OVERDUE_TYPES
            and due_date is not None
            and now > due_date
        ):
            return (const.CHORE_STATE_OVERDUE, None)

        # P6 — Waiting (claim window has not opened yet)
        claim_lock_until_window = bool(
            chore_data.get(
                const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
                const.DEFAULT_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
            )
        )
        if (
            claim_lock_until_window
            and due_window_start is not None
            and due_date is not None
            and now < due_window_start
        ):
            return (const.CHORE_STATE_WAITING, const.CHORE_STATE_WAITING)

        # P7 — Due (inside the claim window)
        if (
            due_window_start is not None
            and due_date is not None
            and due_window_start <= now <= due_date
        ):
            return (const.CHORE_STATE_DUE, None)

        # P8 — Default
        return (const.CHORE_STATE_PENDING, None)

    # =========================================================================
    # DUE DATE & SCHEDULING QUERIES
    # =========================================================================

    @staticmethod
    def get_due_date_for_assignee(
        chore_data: ChoreData | dict[str, Any],
        assignee_id: str | None,
    ) -> str | None:
        """Get the due date ISO string for a chore, handling completion criteria.

        For SHARED/SHARED_FIRST chores: Returns chore-level due date.
        For INDEPENDENT chores: Returns per-assignee due date if assignee_id provided.
        If assignee_id is None: Always returns chore-level due date.

        Args:
            chore_data: The chore definition
            assignee_id: The assignee's internal ID, or None for chore-level due date

        Returns:
            ISO timestamp string of due date, or None if not configured.
        """
        if assignee_id is None:
            # No assignee specified - use chore-level due date
            return chore_data.get(const.DATA_CHORE_DUE_DATE)

        # Check completion criteria
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Use per-assignee due dates
            per_assignee_due_dates = chore_data.get(
                const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
            )
            return per_assignee_due_dates.get(assignee_id)

        # SHARED or SHARED_FIRST: Use chore-level due date
        return chore_data.get(const.DATA_CHORE_DUE_DATE)

    @staticmethod
    def get_last_completed_for_assignee(
        chore_data: ChoreData | dict[str, Any],
        assignee_data: AssigneeData | dict[str, Any],
        assignee_id: str | None,
    ) -> str | None:
        """Get the last_completed timestamp for an assignee+chore combination.

        For SHARED/SHARED_FIRST chores: Returns chore-level last_completed.
        For INDEPENDENT chores: Returns per-assignee last_completed from assignee_data.
        If assignee_id is None: Always returns chore-level last_completed.

        Args:
            chore_data: The chore definition
            assignee_data: The assignee's data dict (needed for INDEPENDENT)
            assignee_id: The assignee's internal ID, or None for chore-level

        Returns:
            ISO timestamp string of last completion, or None if never completed.
        """
        if assignee_id is None:
            # No assignee specified - use chore-level last_completed
            return chore_data.get(const.DATA_CHORE_LAST_COMPLETED)

        # Check completion criteria
        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )

        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: Use per-assignee last_completed from assignee_chore_data
            chore_id = chore_data.get(const.DATA_CHORE_INTERNAL_ID, "")
            assignee_chore_data = ChoreEngine.get_chore_data_for_assignee(
                assignee_data, chore_id
            )
            return assignee_chore_data.get(const.DATA_USER_CHORE_DATA_LAST_COMPLETED)

        # SHARED or SHARED_FIRST: Use chore-level last_completed
        return chore_data.get(const.DATA_CHORE_LAST_COMPLETED)

    @staticmethod
    def chore_is_due(
        due_date_iso: str | None,
        due_window_offset_str: str | None,
        now: datetime,
    ) -> bool:
        """Check if a chore is in the due window (approaching due date).

        A chore is in the due window if:
        - It has a due_window_offset > 0 configured
        - Current time is within: (due_date - due_window_offset) <= now < due_date
        - This method only checks timing, not chore state

        Args:
            due_date_iso: ISO timestamp of the due date, or None
            due_window_offset_str: Duration string like "1d 6h 30m", or None
            now: Current UTC datetime

        Returns:
            True if the chore is in the due window, False otherwise.
        """

        if not due_date_iso:
            return False

        # Parse due window offset
        due_window_td = dt_parse_duration(due_window_offset_str)
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return False

        # Parse due date
        due_date_dt = dt_to_utc(due_date_iso)
        if not due_date_dt:
            return False

        # Calculate due window start
        due_window_start = due_date_dt - due_window_td

        # In due window if: due_window_start <= now <= due_date
        return due_window_start <= now <= due_date_dt

    @staticmethod
    def get_due_window_start(
        due_date_iso: str | None,
        due_window_offset_str: str | None,
    ) -> datetime | None:
        """Calculate when the due window starts for a chore.

        Returns the datetime when the due window begins (due_date - offset),
        or None if the chore has no due date or no due window configured.
        Returns None if due window offset is 0 (disabled).

        Args:
            due_date_iso: ISO timestamp of the due date, or None
            due_window_offset_str: Duration string like "1d 6h 30m", or None

        Returns:
            datetime when due window starts, or None if not applicable.
        """

        if not due_date_iso:
            return None

        # Parse due window offset
        due_window_td = dt_parse_duration(due_window_offset_str)
        if not due_window_td or due_window_td.total_seconds() <= 0:
            return None

        # Parse due date
        due_date_dt = dt_to_utc(due_date_iso)
        if not due_date_dt:
            return None

        return due_date_dt - due_window_td

    @staticmethod
    def is_approved_in_period(
        assignee_chore_data: dict[str, Any],
        period_start_iso: str | None,
    ) -> bool:
        """Check if a chore is already approved in the current approval period.

        A chore is considered approved in the current period if:
        - last_approved timestamp exists, AND EITHER:
          a. period_start doesn't exist (chore was never reset, approval is valid), OR
          b. last_approved >= period_start

        Args:
            assignee_chore_data: The assignee's tracking data for this chore
            period_start_iso: ISO timestamp of approval period start, or None

        Returns:
            True if approved in current period, False otherwise.
        """

        last_approved = assignee_chore_data.get(
            const.DATA_USER_CHORE_DATA_LAST_APPROVED
        )
        if not last_approved:
            return False

        if not period_start_iso:
            # No period_start means chore was never reset after being created.
            # Since last_approved exists (checked above), the approval is still valid.
            return True

        approved_dt = dt_to_utc(last_approved)
        period_start_dt = dt_to_utc(period_start_iso)

        if approved_dt is None or period_start_dt is None:
            return False

        return approved_dt >= period_start_dt

    # =========================================================================
    # ROTATION HELPERS (v0.5.0)
    # =========================================================================

    @staticmethod
    def calculate_next_turn_simple(
        assigned_assignees: list[str],
        current_assignee_id: str,
    ) -> str:
        """Calculate next turn for rotation_simple (strict round-robin).

        Args:
            assigned_assignees: Ordered list of assignee UUIDs assigned to the chore
            current_assignee_id: UUID of the current turn holder

        Returns:
            UUID of the next turn holder (wraps around at end of list)
        """
        if not assigned_assignees:
            # Should never happen (rotation requires ≥2 assignees), but defensive
            return current_assignee_id

        try:
            current_index = assigned_assignees.index(current_assignee_id)
            next_index = (current_index + 1) % len(assigned_assignees)
            return assigned_assignees[next_index]
        except ValueError:
            # Resilience: current_assignee_id not in list → reset to first
            return assigned_assignees[0]

    @staticmethod
    def calculate_next_turn_smart(
        assigned_assignees: list[str],
        completed_counts: dict[str, int],
        last_completed_timestamps: dict[str, str | None],
    ) -> str:
        """Calculate next turn for rotation_smart (fairness-weighted).

        Sorts assignees by:
        1. Ascending completion count (fewest completions first)
        2. Ascending last_completed timestamp (oldest work date first, None = never = first)
        3. List-order position (tie-breaker)

        Uses completed counts (work done) and last_completed timestamps (work dates)
        for fair rotation based on actual work performed, not approver approval delays.

        Args:
            assigned_assignees: Ordered list of assignee UUIDs assigned to the chore
            completed_counts: Dict mapping assignee_id -> completion count for this chore
            last_completed_timestamps: Dict mapping assignee_id -> last_completed ISO timestamp or None

        Returns:
            UUID of the assignee who should get the next turn
        """
        if not assigned_assignees:
            # Should never happen, but defensive
            return assigned_assignees[0] if assigned_assignees else ""

        def sort_key(assignee_id: str) -> tuple[int, str, int]:
            count = completed_counts.get(assignee_id, 0)
            timestamp = last_completed_timestamps.get(assignee_id)
            # None sorts first (never completed)
            timestamp_str = timestamp if timestamp is not None else ""
            position = assigned_assignees.index(assignee_id)
            return (count, timestamp_str, position)

        sorted_assignees = sorted(assigned_assignees, key=sort_key)
        return sorted_assignees[0]

    @staticmethod
    def get_criteria_transition_actions(
        old_criteria: str,
        new_criteria: str,
        chore_data: ChoreData | dict[str, Any],
    ) -> dict[str, Any]:
        """Get field changes needed when switching completion criteria.

        Supports mutable completion_criteria (D-11). Manager applies
        these changes when user edits chore criteria.

        Args:
            old_criteria: Current completion_criteria value
            new_criteria: Target completion_criteria value
            chore_data: The chore definition (for assigned_assignees access)

        Returns:
            Dict of field changes to apply (field_name -> new_value)
        """
        changes: dict[str, Any] = {}

        old_is_rotation = old_criteria in (
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
        )
        new_is_rotation = new_criteria in (
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
        )

        # Non-rotation → rotation: Initialize rotation fields
        if not old_is_rotation and new_is_rotation:
            assigned_assignees = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
            if assigned_assignees:
                changes[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = (
                    assigned_assignees[0]
                )
            changes[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False

        # Rotation → non-rotation: Clear rotation fields
        elif old_is_rotation and not new_is_rotation:
            changes[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = None
            changes[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False

        # Rotation → different rotation: Keep existing turn (no reset)

        return changes

    # =========================================================================
    # POINT CALCULATIONS
    # =========================================================================

    @staticmethod
    def calculate_points(
        chore_data: ChoreData | dict[str, Any],
        multiplier: float = 1.0,
    ) -> float:
        """Calculate points for chore completion with optional multiplier.

        Args:
            chore_data: The chore definition
            multiplier: Point multiplier (default 1.0)

        Returns:
            Calculated points, rounded to DATA_FLOAT_PRECISION
        """
        base_points = float(
            chore_data.get(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
        )
        result = base_points * multiplier
        return round(result, const.DATA_FLOAT_PRECISION)

    # =========================================================================
    # GLOBAL STATE CALCULATION
    # =========================================================================

    @staticmethod
    def compute_global_chore_state(
        chore_data: ChoreData | dict[str, Any],
        assignee_states: dict[str, str],
    ) -> str:
        """Compute the aggregate chore state from per-assignee states.

        Args:
            chore_data: The chore definition
            assignee_states: Dict mapping assignee_id to their current state

        Returns:
            The global chore state string
        """
        if not assignee_states:
            return const.CHORE_STATE_UNKNOWN

        assigned_assignees = list(assignee_states.keys())
        total = len(assigned_assignees)

        if total == 1:
            return next(iter(assignee_states.values()))

        # Count states (v0.5.0: added waiting, not_my_turn, missed, due)
        count_pending = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_PENDING
        )
        count_claimed = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_CLAIMED
        )
        count_approved = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_APPROVED
        )
        count_overdue = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_OVERDUE
        )
        count_waiting = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_WAITING
        )
        count_not_my_turn = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_NOT_MY_TURN
        )
        count_missed = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_MISSED
        )
        count_due = sum(
            1 for s in assignee_states.values() if s == const.CHORE_STATE_DUE
        )

        # All same state
        if count_pending == total:
            return const.CHORE_STATE_PENDING
        if count_claimed == total:
            return const.CHORE_STATE_CLAIMED
        if count_approved == total:
            return const.CHORE_STATE_APPROVED
        if count_overdue == total:
            return const.CHORE_STATE_OVERDUE
        if count_waiting == total:
            return const.CHORE_STATE_WAITING
        if count_missed == total:
            return const.CHORE_STATE_MISSED
        if count_due == total:
            return const.CHORE_STATE_DUE

        criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )

        # SINGLE_CLAIMER (shared_first + rotation): Track active assignee's state
        if ChoreEngine.is_single_claimer_mode(chore_data):
            if count_approved > 0:
                return const.CHORE_STATE_APPROVED
            if count_claimed > 0:
                return const.CHORE_STATE_CLAIMED
            if count_overdue > 0:
                return const.CHORE_STATE_OVERDUE
            if count_missed > 0:
                return const.CHORE_STATE_MISSED
            if count_due > 0:
                return const.CHORE_STATE_DUE
            if count_waiting > 0:
                return const.CHORE_STATE_WAITING
            # Rotation: not_my_turn is cosmetic for non-turn-holders
            if count_not_my_turn > 0:
                # If ANY assignee can claim (not all blocked), show pending
                if count_pending > 0 or count_due > 0:
                    return const.CHORE_STATE_PENDING
                # All blocked by rotation → show not_my_turn
                return const.CHORE_STATE_NOT_MY_TURN
            return const.CHORE_STATE_PENDING

        # SHARED: Partial states
        if criteria == const.COMPLETION_CRITERIA_SHARED:
            if count_overdue > 0:
                return const.CHORE_STATE_OVERDUE
            if count_approved > 0:
                return const.CHORE_STATE_APPROVED_IN_PART
            if count_claimed > 0:
                return const.CHORE_STATE_CLAIMED_IN_PART
            return const.CHORE_STATE_UNKNOWN

        # INDEPENDENT: Different states
        return const.CHORE_STATE_INDEPENDENT

    # =========================================================================
    # STREAK CALCULATION (Schedule-Aware)
    # =========================================================================

    @staticmethod
    def calculate_streak(
        current_streak: int,
        previous_last_completed_iso: str | None,
        current_work_date_iso: str,
        chore_data: ChoreData | dict[str, Any],
    ) -> int:
        """Calculate new streak value based on schedule-aware logic.

        Must be called BEFORE updating last_completed timestamp, using the
        previous value to determine if the schedule gap was missed.

        Args:
            current_streak: The streak value from the previous day (or 0)
            previous_last_completed_iso: ISO timestamp of LAST completion (work date)
            current_work_date_iso: ISO timestamp of THIS completion (effective_date)
            chore_data: Chore definition containing frequency/schedule info

        Returns:
            New streak value: 1 if first completion or streak broken,
                             current_streak + 1 if on-time
        """
        from .schedule_engine import RecurrenceEngine

        # First completion ever = streak of 1
        if not previous_last_completed_iso:
            return 1

        # Get schedule configuration from chore
        frequency = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )

        # No schedule (manual/one-time chore) = simple daily logic
        if frequency == const.FREQUENCY_NONE:
            # Check if previous completion was yesterday (simple streak)
            prev_dt = dt_to_utc(previous_last_completed_iso)
            current_dt = dt_to_utc(current_work_date_iso)
            if prev_dt and current_dt:
                days_diff = (current_dt.date() - prev_dt.date()).days
                if days_diff <= 1:
                    return current_streak + 1
            return 1  # Broke streak

        # Build schedule config for RecurrenceEngine
        applicable_days = chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
        # Convert day names to integers if needed (RecurrenceEngine expects ints)
        applicable_days_int: list[int] = []
        for d in applicable_days:
            if isinstance(d, str):
                day_int = const.WEEKDAY_NAME_TO_INT.get(d.lower())
                if day_int is not None:
                    applicable_days_int.append(day_int)
            elif isinstance(d, int):
                applicable_days_int.append(d)

        # Build config dict - use explicit values to satisfy type checker
        interval_raw = chore_data.get(const.DATA_CHORE_CUSTOM_INTERVAL)
        interval_unit_raw = chore_data.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT)
        daily_multi_raw = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES)

        schedule_config: ScheduleConfig = {
            "frequency": str(frequency),
            "interval": int(interval_raw) if interval_raw else 1,
            "interval_unit": str(interval_unit_raw)
            if interval_unit_raw
            else const.TIME_UNIT_DAYS,
            "base_date": previous_last_completed_iso,
            "applicable_days": applicable_days_int,
            "daily_multi_times": str(daily_multi_raw) if daily_multi_raw else "",
        }

        try:
            engine = RecurrenceEngine(schedule_config)

            # Parse timestamps to datetime for engine
            prev_dt = dt_to_utc(previous_last_completed_iso)
            current_dt = dt_to_utc(current_work_date_iso)

            if not prev_dt or not current_dt:
                return 1  # Can't calculate, reset streak

            # Check if any scheduled occurrences were missed
            if engine.has_missed_occurrences(prev_dt, current_dt):
                return 1  # Broke streak

            return current_streak + 1  # On-time, continue streak

        except Exception:
            # If schedule calculation fails, fallback to simple daily logic
            return 1

    # =========================================================================
    # TIMER BOUNDARY DECISION METHODS
    # =========================================================================

    @staticmethod
    def should_process_at_boundary(
        approval_reset_type: str,
        trigger: str,
    ) -> bool:
        """Check if chore should be processed for this trigger.

        Determines if a chore's approval_reset_type matches the current timer
        trigger. This is the first filter in the approval boundary gatekeeper.

        Args:
            approval_reset_type: Chore's configured reset type (AT_MIDNIGHT_*,
                AT_DUE_DATE_*, UPON_COMPLETION)
            trigger: Current trigger type ("midnight" or "due_date")

        Returns:
            True if chore should be processed for this trigger:
            - AT_MIDNIGHT_ONCE/MULTI → True for trigger=const.TRIGGER_MIDNIGHT
            - AT_DUE_DATE_ONCE/MULTI → True for trigger=const.TRIGGER_DUE_DATE
            - UPON_COMPLETION → Always False (handled in approve workflow)
        """
        midnight_types = {
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }
        due_date_types = {
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
        }

        if trigger == "midnight":
            return approval_reset_type in midnight_types
        if trigger == "due_date":
            return approval_reset_type in due_date_types
        return False

    @staticmethod
    def calculate_boundary_action(
        current_state: str,
        overdue_handling: str,
        pending_claims_handling: str,
        recurring_frequency: str,
        has_due_date: bool,
    ) -> str:
        """Calculate what action to take for a chore at approval boundary.

        This is the core decision logic for the approval boundary gatekeeper.
        It evaluates the chore's current state and configuration to determine
        the appropriate action.

        Args:
            current_state: Current chore state (PENDING, CLAIMED, APPROVED, OVERDUE)
            overdue_handling: Chore's overdue_handling_type setting
            pending_claims_handling: Chore's pending_claim_action setting
            recurring_frequency: Chore's frequency (DAILY, WEEKLY, NONE, etc.)
            has_due_date: Whether the chore has a due date configured

        Returns:
            Action string:
            - "reset_and_reschedule": Reset state + calculate next due date
            - "reset_only": Reset state without rescheduling (no due date)
            - "hold": Skip processing, preserve current state
            - "skip": No action needed (already PENDING or non-recurring approved)
        """
        # PENDING state = nothing to do
        if current_state == const.CHORE_STATE_PENDING:
            return "skip"

        # APPROVED state = always reset (approval_reset_type already filtered)
        # Note: Non-recurring chores with AT_MIDNIGHT_* still reset at midnight.
        # The approval_reset_type determines WHEN resets happen, not frequency.
        if current_state == const.CHORE_STATE_APPROVED:
            return "reset_and_reschedule" if has_due_date else "reset_only"

        # CLAIMED state = check pending_claims_handling
        if current_state == const.CHORE_STATE_CLAIMED:
            if pending_claims_handling == const.APPROVAL_RESET_PENDING_CLAIM_HOLD:
                return "hold"
            # CLEAR and AUTO_APPROVE both proceed with reset
            # (AUTO_APPROVE approval is handled by the manager, not engine)
            return "reset_and_reschedule" if has_due_date else "reset_only"

        # OVERDUE state = check overdue_handling
        if current_state == const.CHORE_STATE_OVERDUE:
            # AT_DUE_DATE = hold until manually completed
            if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE:
                return "hold"
            # CLEAR_AT_APPROVAL_RESET = clear overdue and reset
            if (
                overdue_handling
                == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
            ):
                return "reset_and_reschedule" if has_due_date else "reset_only"
            # CLEAR_AND_MARK_MISSED = record miss then reset
            if (
                overdue_handling
                == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED
            ):
                return "reset_and_reschedule" if has_due_date else "reset_only"
            # CLEAR_IMMEDIATE_ON_LATE = already handled when due passed, skip
            if (
                overdue_handling
                == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
            ):
                return "skip"
            # NEVER_OVERDUE = shouldn't be in OVERDUE state, but skip if so
            if overdue_handling == const.OVERDUE_HANDLING_NEVER_OVERDUE:
                return "skip"

        # Default: skip unknown states
        return "skip"

    @staticmethod
    def get_boundary_category(
        chore_data: ChoreData | dict[str, Any],
        assignee_state: str,
        trigger: str,
    ) -> str | None:
        """Get categorization for batch approval boundary processing.

        Combines should_process_at_boundary and calculate_boundary_action
        into a single categorization call for efficient batch processing.

        Args:
            chore_data: Chore configuration dict
            assignee_state: Current state for this assignee (or chore-level for SHARED)
            trigger: Current trigger type ("midnight" or "due_date")

        Returns:
            Category string or None:
            - "reset_and_reschedule": Needs reset with due date update
            - "reset_only": Needs reset without due date update
            - "hold": Should be skipped (preserve state)
            - None: Not in scope for this trigger or skip
        """
        # Check if chore is in scope for this trigger
        approval_reset_type = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        if not ChoreEngine.should_process_at_boundary(approval_reset_type, trigger):
            return None

        # Get configuration values
        overdue_handling = chore_data.get(
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.OVERDUE_HANDLING_AT_DUE_DATE,
        )
        pending_claims_handling = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
        )
        recurring_frequency = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY,
            const.FREQUENCY_NONE,
        )

        # Check for due date
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_SHARED,
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # INDEPENDENT: check per_assignee_due_dates
            per_assignee_due_dates = chore_data.get(
                const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
            )
            has_due_date = bool(per_assignee_due_dates)
        else:
            # SHARED/SHARED_FIRST: check chore-level due_date
            has_due_date = bool(chore_data.get(const.DATA_CHORE_DUE_DATE))

        # Calculate action
        action = ChoreEngine.calculate_boundary_action(
            current_state=assignee_state,
            overdue_handling=overdue_handling,
            pending_claims_handling=pending_claims_handling,
            recurring_frequency=recurring_frequency,
            has_due_date=has_due_date,
        )

        # Map action to category (skip → None)
        if action == "skip":
            return None
        return action
