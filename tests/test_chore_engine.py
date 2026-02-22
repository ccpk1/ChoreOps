"""Tests for ChoreEngine - pure logic, no HA fixtures needed.

These tests validate the ChoreEngine's pure Python functions without
requiring any Home Assistant mocking or integration setup.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import (
    CHORE_ACTION_APPROVE,
    CHORE_ACTION_CLAIM,
    CHORE_ACTION_DISAPPROVE,
    CHORE_ACTION_OVERDUE,
    CHORE_ACTION_RESET,
    CHORE_ACTION_UNDO,
    ChoreEngine,
)

# =============================================================================
# TEST: STATE TRANSITION VALIDATION
# =============================================================================


class TestStateTransitions:
    """Test state transition validation."""

    def test_pending_to_claimed_allowed(self) -> None:
        """PENDING → CLAIMED is a valid transition."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_PENDING, const.CHORE_STATE_CLAIMED
        )

    def test_pending_to_overdue_allowed(self) -> None:
        """PENDING → OVERDUE is a valid transition."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_PENDING, const.CHORE_STATE_OVERDUE
        )

    # Phase 2: test_pending_to_completed_by_other_allowed REMOVED
    # COMPLETED_BY_OTHER is now a computed display state, not a stored FSM state

    def test_claimed_to_approved_allowed(self) -> None:
        """CLAIMED → APPROVED is a valid transition."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_CLAIMED, const.CHORE_STATE_APPROVED
        )

    def test_claimed_to_pending_allowed(self) -> None:
        """CLAIMED → PENDING is valid (disapproval or undo)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_CLAIMED, const.CHORE_STATE_PENDING
        )

    def test_claimed_to_overdue_allowed(self) -> None:
        """CLAIMED → OVERDUE is valid (due date passed while claimed)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_CLAIMED, const.CHORE_STATE_OVERDUE
        )

    def test_approved_to_pending_allowed(self) -> None:
        """APPROVED → PENDING is valid (reset for recurrence)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_APPROVED, const.CHORE_STATE_PENDING
        )

    def test_approved_to_claimed_not_allowed(self) -> None:
        """APPROVED → CLAIMED is NOT valid."""
        assert not ChoreEngine.can_transition(
            const.CHORE_STATE_APPROVED, const.CHORE_STATE_CLAIMED
        )

    def test_overdue_to_claimed_allowed(self) -> None:
        """OVERDUE → CLAIMED is valid (assignee claims overdue chore)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_OVERDUE, const.CHORE_STATE_CLAIMED
        )

    def test_overdue_to_approved_allowed(self) -> None:
        """OVERDUE → APPROVED is valid (approver completes on behalf)."""
        assert ChoreEngine.can_transition(
            const.CHORE_STATE_OVERDUE, const.CHORE_STATE_APPROVED
        )

    # Phase 2: completed_by_other transition tests REMOVED
    # completed_by_other is now a computed blocking state, not in FSM

    def test_unknown_state_has_no_transitions(self) -> None:
        """UNKNOWN state has no valid outgoing transitions."""
        assert not ChoreEngine.can_transition(
            const.CHORE_STATE_UNKNOWN, const.CHORE_STATE_PENDING
        )


# =============================================================================
# TEST: CALCULATE_TRANSITION - CLAIM ACTION
# =============================================================================


class TestCalculateTransitionClaim:
    """Test transition effect planning for claim actions."""

    def test_claim_independent_affects_only_actor(self) -> None:
        """INDEPENDENT: Claim only affects the claiming assignee."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_CLAIM,
            assignees_assigned=["assignee-1", "assignee-2", "assignee-3"],
            assignee_name="Sarah",
        )

        assert len(effects) == 1
        assert effects[0].assignee_id == "assignee-1"
        assert effects[0].new_state == const.CHORE_STATE_CLAIMED
        assert effects[0].update_stats is True
        assert effects[0].set_claimed_by == "Sarah"

    def test_claim_shared_affects_only_actor(self) -> None:
        """SHARED: Claim only affects the claiming assignee."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_CLAIM,
            assignees_assigned=["assignee-1", "assignee-2"],
            assignee_name="Sarah",
        )

        assert len(effects) == 1
        assert effects[0].assignee_id == "assignee-1"
        assert effects[0].new_state == const.CHORE_STATE_CLAIMED

    def test_claim_shared_first_affects_all_assignees(self) -> None:
        """SHARED_FIRST: Claiming assignee → CLAIMED (Phase 2: no state change for others)."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_CLAIM,
            assignees_assigned=["assignee-1", "assignee-2", "assignee-3"],
            assignee_name="Sarah",
        )

        # Phase 2: Only 1 effect (actor), other assignees remain in their current state
        assert len(effects) == 1

        # Actor assignee gets CLAIMED state
        actor_effect = effects[0]
        assert actor_effect.assignee_id == "assignee-1"
        assert actor_effect.new_state == const.CHORE_STATE_CLAIMED
        assert actor_effect.update_stats is True
        assert actor_effect.set_claimed_by == "Sarah"


# =============================================================================
# TEST: CALCULATE_TRANSITION - APPROVE ACTION
# =============================================================================


class TestCalculateTransitionApprove:
    """Test transition effect planning for approve actions."""

    def test_approve_independent_awards_points(self) -> None:
        """INDEPENDENT: Approve awards points to actor only."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_DEFAULT_POINTS: 15.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_APPROVE,
            assignees_assigned=["assignee-1", "assignee-2"],
            assignee_name="Sarah",
        )

        assert len(effects) == 1
        assert effects[0].assignee_id == "assignee-1"
        assert effects[0].new_state == const.CHORE_STATE_APPROVED
        assert effects[0].update_stats is True
        assert effects[0].points == 15.0
        assert effects[0].set_completed_by == "Sarah"

    def test_approve_shared_first_updates_all(self) -> None:
        """SHARED_FIRST: Approve updates actor only (Phase 2: no state change for others)."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 20.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_APPROVE,
            assignees_assigned=["assignee-1", "assignee-2"],
            assignee_name="Sarah",
        )

        # Phase 2: Only 1 effect (actor), blocking is computed not stored
        assert len(effects) == 1

        actor_effect = effects[0]
        assert actor_effect.assignee_id == "assignee-1"
        assert actor_effect.new_state == const.CHORE_STATE_APPROVED
        assert actor_effect.points == 20.0
        assert actor_effect.update_stats is True
        assert actor_effect.set_completed_by == "Sarah"


# =============================================================================
# TEST: CALCULATE_TRANSITION - DISAPPROVE ACTION
# =============================================================================


class TestCalculateTransitionDisapprove:
    """Test transition effect planning for disapprove actions."""

    def test_disapprove_independent_resets_actor_only(self) -> None:
        """INDEPENDENT: Disapprove only resets the actor."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_DISAPPROVE,
            assignees_assigned=["assignee-1", "assignee-2"],
        )

        assert len(effects) == 1
        assert effects[0].assignee_id == "assignee-1"
        assert effects[0].new_state == const.CHORE_STATE_PENDING
        assert effects[0].update_stats is True

    def test_disapprove_shared_first_resets_all(self) -> None:
        """SHARED_FIRST: Disapprove resets ALL assignees to pending."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_DISAPPROVE,
            assignees_assigned=["assignee-1", "assignee-2", "assignee-3"],
        )

        assert len(effects) == 3

        for effect in effects:
            assert effect.new_state == const.CHORE_STATE_PENDING
            assert effect.clear_claimed_by is True
            assert effect.clear_completed_by is True

        # Only actor gets stat update
        actor_effect = next(e for e in effects if e.assignee_id == "assignee-1")
        assert actor_effect.update_stats is True

        other_effects = [e for e in effects if e.assignee_id != "assignee-1"]
        for effect in other_effects:
            assert effect.update_stats is False


# =============================================================================
# TEST: CALCULATE_TRANSITION - UNDO ACTION
# =============================================================================


class TestCalculateTransitionUndo:
    """Test transition effect planning for undo actions."""

    def test_undo_never_updates_stats(self) -> None:
        """Undo action should always set update_stats=False."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_UNDO,
            assignees_assigned=["assignee-1"],
        )

        assert all(e.update_stats is False for e in effects)

    def test_undo_shared_first_resets_all(self) -> None:
        """SHARED_FIRST: Undo resets ALL assignees."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_UNDO,
            assignees_assigned=["assignee-1", "assignee-2"],
        )

        assert len(effects) == 2
        for effect in effects:
            assert effect.new_state == const.CHORE_STATE_PENDING
            assert effect.update_stats is False
            assert effect.clear_claimed_by is True


# =============================================================================
# TEST: CALCULATE_TRANSITION - RESET ACTION
# =============================================================================


class TestCalculateTransitionReset:
    """Test transition effect planning for reset actions."""

    def test_reset_affects_all_assignees(self) -> None:
        """Reset transitions all assigned assignees to pending."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",  # Actor doesn't matter for reset
            action=CHORE_ACTION_RESET,
            assignees_assigned=["assignee-1", "assignee-2", "assignee-3"],
        )

        assert len(effects) == 3
        for effect in effects:
            assert effect.new_state == const.CHORE_STATE_PENDING
            assert effect.update_stats is False
            assert effect.clear_claimed_by is True
            assert effect.clear_completed_by is True


# =============================================================================
# TEST: CALCULATE_TRANSITION - OVERDUE ACTION
# =============================================================================


class TestCalculateTransitionOverdue:
    """Test transition effect planning for overdue actions."""

    def test_overdue_affects_only_actor(self) -> None:
        """Overdue only marks the specified assignee as overdue."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_OVERDUE,
            assignees_assigned=["assignee-1", "assignee-2"],
        )

        assert len(effects) == 1
        assert effects[0].assignee_id == "assignee-1"
        assert effects[0].new_state == const.CHORE_STATE_OVERDUE
        assert effects[0].update_stats is True


# =============================================================================
# TEST: SKIP_STATS FLAG
# =============================================================================


class TestSkipStatsFlag:
    """Test the skip_stats parameter."""

    def test_skip_stats_overrides_all_effects(self) -> None:
        """When skip_stats=True, all effects have update_stats=False."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
            const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        }

        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_assignee_id="assignee-1",
            action=CHORE_ACTION_APPROVE,
            assignees_assigned=["assignee-1", "assignee-2"],
            skip_stats=True,
        )

        assert all(e.update_stats is False for e in effects)


# =============================================================================
# TEST: STATE RESOLUTION - WAITING LOCK (P6)
# =============================================================================


class TestResolveAssigneeChoreStateWaiting:
    """Test P6 waiting lock behavior in chore state resolution."""

    def test_pre_window_returns_waiting_with_lock_reason(self) -> None:
        """Before due window opens, lock-until-window chore resolves to WAITING."""
        now = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        due_window_start = now + timedelta(hours=2)
        due_date = now + timedelta(hours=6)

        chore_data = {
            const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW: True,
        }

        state, lock_reason = ChoreEngine.resolve_assignee_chore_state(
            chore_data=chore_data,
            assignee_id="assignee-1",
            now=now,
            is_approved_in_period=False,
            has_pending_claim=False,
            due_date=due_date,
            due_window_start=due_window_start,
        )

        assert state == const.CHORE_STATE_WAITING
        assert lock_reason == const.CHORE_STATE_WAITING

    def test_in_window_returns_due_without_lock_reason(self) -> None:
        """Inside due window, chore resolves to DUE and is claimable."""
        now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        due_window_start = now - timedelta(minutes=30)
        due_date = now + timedelta(hours=2)

        chore_data = {
            const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW: True,
        }

        state, lock_reason = ChoreEngine.resolve_assignee_chore_state(
            chore_data=chore_data,
            assignee_id="assignee-1",
            now=now,
            is_approved_in_period=False,
            has_pending_claim=False,
            due_date=due_date,
            due_window_start=due_window_start,
        )

        assert state == const.CHORE_STATE_DUE
        assert lock_reason is None

    def test_pre_window_lock_disabled_returns_pending(self) -> None:
        """Before due window, lock-disabled chore remains PENDING."""
        now = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        due_window_start = now + timedelta(hours=2)
        due_date = now + timedelta(hours=6)

        chore_data = {
            const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW: False,
        }

        state, lock_reason = ChoreEngine.resolve_assignee_chore_state(
            chore_data=chore_data,
            assignee_id="assignee-1",
            now=now,
            is_approved_in_period=False,
            has_pending_claim=False,
            due_date=due_date,
            due_window_start=due_window_start,
        )

        assert state == const.CHORE_STATE_PENDING
        assert lock_reason is None


# =============================================================================
# TEST: VALIDATION - CAN CLAIM
# =============================================================================


class TestCanClaimChore:
    """Test claim validation logic."""

    def test_completed_by_other_blocks_claim(self) -> None:
        """Phase 2: SHARED_FIRST with other assignee CLAIMED/APPROVED blocks claim."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        # Phase 2: Blocking computed from other assignees' states
        other_assignee_states = {"other-assignee": const.CHORE_STATE_CLAIMED}

        can_claim, error = ChoreEngine.can_claim_chore(
            assignee_chore_data,
            chore_data,
            has_pending_claim=False,
            is_approved_in_period=False,
            other_assignee_states=other_assignee_states,
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER

    def test_pending_claim_blocks_new_claim(self) -> None:
        """Cannot claim if there's already a pending claim (single-claim)."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            assignee_chore_data,
            chore_data,
            has_pending_claim=True,
            is_approved_in_period=False,
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM

    def test_already_approved_blocks_claim(self) -> None:
        """Cannot claim if already approved in period (single-claim)."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            assignee_chore_data,
            chore_data,
            has_pending_claim=False,
            is_approved_in_period=True,
        )

        assert can_claim is False
        assert error == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED

    def test_multi_claim_allows_pending(self) -> None:
        """Multi-claim chore allows claiming even with pending claim."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            assignee_chore_data,
            chore_data,
            has_pending_claim=True,
            is_approved_in_period=False,
        )

        assert can_claim is True
        assert error is None

    def test_upon_completion_allows_pending(self) -> None:
        """UPON_COMPLETION chore allows claiming even with pending."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
        }

        can_claim, error = ChoreEngine.can_claim_chore(
            assignee_chore_data,
            chore_data,
            has_pending_claim=True,
            is_approved_in_period=True,
        )

        assert can_claim is True
        assert error is None

    def test_valid_claim_succeeds(self) -> None:
        """Normal claim with no blockers succeeds."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        chore_data: dict[str, object] = {}

        can_claim, error = ChoreEngine.can_claim_chore(
            assignee_chore_data,
            chore_data,
            has_pending_claim=False,
            is_approved_in_period=False,
        )

        assert can_claim is True
        assert error is None


# =============================================================================
# TEST: VALIDATION - CAN APPROVE
# =============================================================================


class TestCanApproveChore:
    """Test approve validation logic."""

    # Phase 2: test_completed_by_other_blocks_approve REMOVED
    # completed_by_other is not a stored state, blocking only applies to claims

    def test_already_approved_blocks_single_claim(self) -> None:
        """Single-claim chore cannot be approved twice in period."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }

        can_approve, error = ChoreEngine.can_approve_chore(
            assignee_chore_data, chore_data, is_approved_in_period=True
        )

        assert can_approve is False
        assert error == const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED

    def test_multi_claim_allows_multiple_approvals(self) -> None:
        """Multi-claim chore allows multiple approvals in period."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
        }
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }

        can_approve, error = ChoreEngine.can_approve_chore(
            assignee_chore_data, chore_data, is_approved_in_period=True
        )

        assert can_approve is True
        assert error is None

    def test_valid_approve_succeeds(self) -> None:
        """Normal approval with no blockers succeeds."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
        }
        chore_data: dict[str, object] = {}

        can_approve, error = ChoreEngine.can_approve_chore(
            assignee_chore_data, chore_data, is_approved_in_period=False
        )

        assert can_approve is True
        assert error is None


# =============================================================================
# TEST: QUERY FUNCTIONS
# =============================================================================


class TestQueryFunctions:
    """Test query/lookup functions."""

    def test_chore_has_pending_claim_true(self) -> None:
        """Returns True when pending_claim_count > 0."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_PENDING_CLAIM_COUNT: 2,
        }
        assert ChoreEngine.chore_has_pending_claim(assignee_chore_data) is True

    def test_chore_has_pending_claim_false(self) -> None:
        """Returns False when pending_claim_count is 0 or missing."""
        assert ChoreEngine.chore_has_pending_claim({}) is False
        assert (
            ChoreEngine.chore_has_pending_claim(
                {const.DATA_ASSIGNEE_CHORE_DATA_PENDING_CLAIM_COUNT: 0}
            )
            is False
        )

    def test_chore_is_overdue_true(self) -> None:
        """Returns True when state is OVERDUE."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
        }
        assert ChoreEngine.chore_is_overdue(assignee_chore_data) is True

    def test_chore_is_overdue_false(self) -> None:
        """Returns False when state is not OVERDUE."""
        assignee_chore_data = {
            const.DATA_ASSIGNEE_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
        }
        assert ChoreEngine.chore_is_overdue(assignee_chore_data) is False

    def test_chore_allows_multiple_claims_midnight_multi(self) -> None:
        """AT_MIDNIGHT_MULTI allows multiple claims."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }
        assert ChoreEngine.chore_allows_multiple_claims(chore_data) is True

    def test_chore_allows_multiple_claims_due_date_multi(self) -> None:
        """AT_DUE_DATE_MULTI allows multiple claims."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
        }
        assert ChoreEngine.chore_allows_multiple_claims(chore_data) is True

    def test_chore_allows_multiple_claims_upon_completion(self) -> None:
        """UPON_COMPLETION allows multiple claims."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
        }
        assert ChoreEngine.chore_allows_multiple_claims(chore_data) is True

    def test_chore_allows_multiple_claims_once_types(self) -> None:
        """ONCE types do not allow multiple claims."""
        for reset_type in [
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
        ]:
            chore_data = {const.DATA_CHORE_APPROVAL_RESET_TYPE: reset_type}
            assert ChoreEngine.chore_allows_multiple_claims(chore_data) is False

    def test_is_shared_chore_shared(self) -> None:
        """SHARED criteria is a shared chore."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        assert ChoreEngine.is_shared_chore(chore_data) is True

    def test_is_shared_chore_shared_first(self) -> None:
        """SHARED_FIRST criteria is a shared chore."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        assert ChoreEngine.is_shared_chore(chore_data) is True

    def test_is_shared_chore_independent(self) -> None:
        """INDEPENDENT criteria is NOT a shared chore."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }
        assert ChoreEngine.is_shared_chore(chore_data) is False

    def test_get_chore_data_for_assignee_exists(self) -> None:
        """Returns chore data when it exists."""
        assignee_data = {
            const.DATA_ASSIGNEE_CHORE_DATA: {
                "chore-123": {"state": "claimed", "streak": 5},
            }
        }
        result = ChoreEngine.get_chore_data_for_assignee(assignee_data, "chore-123")
        assert result == {"state": "claimed", "streak": 5}

    def test_get_chore_data_for_assignee_not_exists(self) -> None:
        """Returns empty dict when chore data doesn't exist."""
        assignee_data = {const.DATA_ASSIGNEE_CHORE_DATA: {}}
        result = ChoreEngine.get_chore_data_for_assignee(assignee_data, "chore-999")
        assert result == {}

    def test_get_chore_data_for_assignee_no_tracking(self) -> None:
        """Returns empty dict when assignee has no chore_data."""
        assignee_data: dict[str, object] = {}
        result = ChoreEngine.get_chore_data_for_assignee(assignee_data, "chore-123")
        assert result == {}


# =============================================================================
# TEST: POINT CALCULATIONS
# =============================================================================


class TestPointCalculations:
    """Test point calculation functions."""

    def test_calculate_points_no_multiplier(self) -> None:
        """Calculate points with default multiplier (1.0)."""
        chore_data = {const.DATA_CHORE_DEFAULT_POINTS: 10.0}
        result = ChoreEngine.calculate_points(chore_data)
        assert result == 10.0

    def test_calculate_points_with_multiplier(self) -> None:
        """Calculate points with custom multiplier."""
        chore_data = {const.DATA_CHORE_DEFAULT_POINTS: 10.0}
        result = ChoreEngine.calculate_points(chore_data, multiplier=1.5)
        assert result == 15.0

    def test_calculate_points_uses_default_when_missing(self) -> None:
        """Uses DEFAULT_POINTS when chore has no points defined."""
        chore_data: dict[str, object] = {}
        result = ChoreEngine.calculate_points(chore_data)
        assert result == const.DEFAULT_POINTS

    def test_calculate_points_rounds_to_precision(self) -> None:
        """Points are rounded to DATA_FLOAT_PRECISION."""
        chore_data = {const.DATA_CHORE_DEFAULT_POINTS: 10.0}
        result = ChoreEngine.calculate_points(chore_data, multiplier=0.333)
        # 10.0 * 0.333 = 3.33, rounded to 2 decimal places
        assert result == 3.33


# =============================================================================
# TEST: GLOBAL STATE CALCULATION
# =============================================================================


class TestComputeGlobalChoreState:
    """Test global state calculation from per-assignee states."""

    def test_empty_states_returns_unknown(self) -> None:
        """Empty assignee_states returns UNKNOWN."""
        result = ChoreEngine.compute_global_chore_state({}, {})
        assert result == const.CHORE_STATE_UNKNOWN

    def test_single_assignee_returns_their_state(self) -> None:
        """Single assignee: global state is their state."""
        assignee_states = {"assignee-1": const.CHORE_STATE_CLAIMED}
        result = ChoreEngine.compute_global_chore_state({}, assignee_states)
        assert result == const.CHORE_STATE_CLAIMED

    def test_all_pending_returns_pending(self) -> None:
        """All assignees pending: global state is PENDING."""
        assignee_states = {
            "assignee-1": const.CHORE_STATE_PENDING,
            "assignee-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state({}, assignee_states)
        assert result == const.CHORE_STATE_PENDING

    def test_all_approved_returns_approved(self) -> None:
        """All assignees approved: global state is APPROVED."""
        assignee_states = {
            "assignee-1": const.CHORE_STATE_APPROVED,
            "assignee-2": const.CHORE_STATE_APPROVED,
        }
        result = ChoreEngine.compute_global_chore_state({}, assignee_states)
        assert result == const.CHORE_STATE_APPROVED

    def test_shared_first_with_claimed_returns_claimed(self) -> None:
        """SHARED_FIRST: One claimed, others pending → CLAIMED (Phase 2)."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_CLAIMED,
            "assignee-2": const.CHORE_STATE_PENDING,  # Phase 2: no longer COMPLETED_BY_OTHER
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_CLAIMED

    def test_shared_first_with_approved_returns_approved(self) -> None:
        """SHARED_FIRST: One approved, others pending → APPROVED (Phase 2)."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED_FIRST,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_APPROVED,
            "assignee-2": const.CHORE_STATE_PENDING,  # Phase 2: no longer COMPLETED_BY_OTHER
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_APPROVED

    def test_shared_partial_claimed_returns_claimed_in_part(self) -> None:
        """SHARED: Some claimed, some pending → CLAIMED_IN_PART."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_CLAIMED,
            "assignee-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_CLAIMED_IN_PART

    def test_shared_partial_approved_returns_approved_in_part(self) -> None:
        """SHARED: Some approved, some pending → APPROVED_IN_PART."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_APPROVED,
            "assignee-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_APPROVED_IN_PART

    def test_independent_mixed_returns_independent(self) -> None:
        """INDEPENDENT: Mixed states → INDEPENDENT."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_APPROVED,
            "assignee-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_INDEPENDENT

    def test_overdue_takes_precedence_in_shared(self) -> None:
        """SHARED: If any assignee is overdue, global is OVERDUE."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_OVERDUE,
            "assignee-2": const.CHORE_STATE_PENDING,
        }
        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_OVERDUE


# =============================================================================
# TEST: TIMER BOUNDARY DECISION METHODS
# =============================================================================


class TestShouldProcessAtBoundary:
    """Test should_process_at_boundary() - trigger scope filtering."""

    # -------------------------------------------------------------------------
    # Midnight trigger tests
    # -------------------------------------------------------------------------

    def test_midnight_once_matches_midnight_trigger(self) -> None:
        """AT_MIDNIGHT_ONCE should process for midnight trigger."""
        assert ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE, "midnight"
        )

    def test_midnight_multi_matches_midnight_trigger(self) -> None:
        """AT_MIDNIGHT_MULTI should process for midnight trigger."""
        assert ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI, "midnight"
        )

    def test_midnight_once_skips_due_date_trigger(self) -> None:
        """AT_MIDNIGHT_ONCE should NOT process for due_date trigger."""
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE, "due_date"
        )

    def test_midnight_multi_skips_due_date_trigger(self) -> None:
        """AT_MIDNIGHT_MULTI should NOT process for due_date trigger."""
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI, "due_date"
        )

    # -------------------------------------------------------------------------
    # Due date trigger tests
    # -------------------------------------------------------------------------

    def test_due_date_once_matches_due_date_trigger(self) -> None:
        """AT_DUE_DATE_ONCE should process for due_date trigger."""
        assert ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE, "due_date"
        )

    def test_due_date_multi_matches_due_date_trigger(self) -> None:
        """AT_DUE_DATE_MULTI should process for due_date trigger."""
        assert ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI, "due_date"
        )

    def test_due_date_once_skips_midnight_trigger(self) -> None:
        """AT_DUE_DATE_ONCE should NOT process for midnight trigger."""
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_DUE_DATE_ONCE, "midnight"
        )

    def test_due_date_multi_skips_midnight_trigger(self) -> None:
        """AT_DUE_DATE_MULTI should NOT process for midnight trigger."""
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_DUE_DATE_MULTI, "midnight"
        )

    # -------------------------------------------------------------------------
    # UPON_COMPLETION tests
    # -------------------------------------------------------------------------

    def test_upon_completion_never_timer_driven(self) -> None:
        """UPON_COMPLETION should never process for any timer trigger."""
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_UPON_COMPLETION, "midnight"
        )
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_UPON_COMPLETION, "due_date"
        )

    # -------------------------------------------------------------------------
    # Edge cases
    # -------------------------------------------------------------------------

    def test_unknown_trigger_returns_false(self) -> None:
        """Unknown trigger type should return False."""
        assert not ChoreEngine.should_process_at_boundary(
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE, "unknown"
        )


class TestCalculateBoundaryAction:
    """Test calculate_boundary_action() - core decision logic."""

    # -------------------------------------------------------------------------
    # PENDING state tests
    # -------------------------------------------------------------------------

    def test_pending_state_always_skips(self) -> None:
        """PENDING state = nothing to do, always skip."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_PENDING,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "skip"

    # -------------------------------------------------------------------------
    # APPROVED state tests
    # -------------------------------------------------------------------------

    def test_approved_recurring_with_due_date_resets_and_reschedules(self) -> None:
        """APPROVED recurring chore with due date → reset_and_reschedule."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_APPROVED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "reset_and_reschedule"

    def test_approved_recurring_without_due_date_resets_only(self) -> None:
        """APPROVED recurring chore without due date → reset_only."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_APPROVED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=False,
        )
        assert result == "reset_only"

    def test_approved_non_recurring_with_due_date_resets_and_reschedules(self) -> None:
        """Non-recurring APPROVED chore resets based on approval_reset_type.

        Even for non-recurring chores, APPROVED state resets at the boundary.
        The approval_reset_type (AT_MIDNIGHT_*, AT_DUE_DATE_*) determines
        WHEN resets happen, not recurring_frequency.
        """
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_APPROVED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_NONE,
            has_due_date=True,
        )
        assert result == "reset_and_reschedule"

    def test_approved_non_recurring_without_due_date_resets_only(self) -> None:
        """Non-recurring APPROVED chore without due date → reset_only."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_APPROVED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_NONE,
            has_due_date=False,
        )
        assert result == "reset_only"

    # -------------------------------------------------------------------------
    # CLAIMED state tests
    # -------------------------------------------------------------------------

    def test_claimed_with_hold_policy_holds(self) -> None:
        """CLAIMED + HOLD policy → hold (preserve claim)."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_CLAIMED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_HOLD,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "hold"

    def test_claimed_with_clear_policy_resets_and_reschedules(self) -> None:
        """CLAIMED + CLEAR policy with due date → reset_and_reschedule."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_CLAIMED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "reset_and_reschedule"

    def test_claimed_with_auto_approve_resets_and_reschedules(self) -> None:
        """CLAIMED + AUTO_APPROVE with due date → reset_and_reschedule."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_CLAIMED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "reset_and_reschedule"

    def test_claimed_with_clear_no_due_date_resets_only(self) -> None:
        """CLAIMED + CLEAR policy without due date → reset_only."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_CLAIMED,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=False,
        )
        assert result == "reset_only"

    # -------------------------------------------------------------------------
    # OVERDUE state tests
    # -------------------------------------------------------------------------

    def test_overdue_at_due_date_holds(self) -> None:
        """OVERDUE + AT_DUE_DATE handling → hold until manual completion."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_OVERDUE,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "hold"

    def test_overdue_clear_at_reset_resets_and_reschedules(self) -> None:
        """OVERDUE + CLEAR_AT_APPROVAL_RESET → reset_and_reschedule."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_OVERDUE,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "reset_and_reschedule"

    def test_overdue_clear_at_reset_no_due_date_resets_only(self) -> None:
        """OVERDUE + CLEAR_AT_APPROVAL_RESET without due date → reset_only."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_OVERDUE,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=False,
        )
        assert result == "reset_only"

    def test_overdue_clear_immediate_skips(self) -> None:
        """OVERDUE + CLEAR_IMMEDIATE_ON_LATE → skip (already handled)."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_OVERDUE,
            overdue_handling=const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "skip"

    def test_overdue_never_overdue_skips(self) -> None:
        """OVERDUE + NEVER_OVERDUE → skip (shouldn't be in OVERDUE state)."""
        result = ChoreEngine.calculate_boundary_action(
            current_state=const.CHORE_STATE_OVERDUE,
            overdue_handling=const.OVERDUE_HANDLING_NEVER_OVERDUE,
            pending_claims_handling=const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            recurring_frequency=const.FREQUENCY_DAILY,
            has_due_date=True,
        )
        assert result == "skip"


class TestGetBoundaryCategory:
    """Test get_boundary_category() - combined categorization."""

    # -------------------------------------------------------------------------
    # Out of scope tests
    # -------------------------------------------------------------------------

    def test_midnight_chore_on_due_date_trigger_returns_none(self) -> None:
        """Midnight-reset chore should return None for due_date trigger."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "due_date"
        )
        assert result is None

    def test_due_date_chore_on_midnight_trigger_returns_none(self) -> None:
        """Due-date-reset chore should return None for midnight trigger."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        assert result is None

    def test_upon_completion_returns_none_for_any_trigger(self) -> None:
        """UPON_COMPLETION should return None for any timer trigger."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
        }
        assert (
            ChoreEngine.get_boundary_category(
                chore_data, const.CHORE_STATE_APPROVED, "midnight"
            )
            is None
        )
        assert (
            ChoreEngine.get_boundary_category(
                chore_data, const.CHORE_STATE_APPROVED, "due_date"
            )
            is None
        )

    # -------------------------------------------------------------------------
    # In scope - returns category
    # -------------------------------------------------------------------------

    def test_approved_midnight_chore_returns_reset_and_reschedule(self) -> None:
        """APPROVED midnight chore with due date → reset_and_reschedule."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_DUE_DATE: "2025-01-31T10:00:00",
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        assert result == "reset_and_reschedule"

    def test_claimed_hold_policy_returns_hold(self) -> None:
        """CLAIMED chore with HOLD policy → hold."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                const.APPROVAL_RESET_PENDING_CLAIM_HOLD
            ),
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_CLAIMED, "midnight"
        )
        assert result == "hold"

    def test_pending_state_returns_none(self) -> None:
        """PENDING state should return None (skip maps to None)."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_PENDING, "midnight"
        )
        assert result is None

    # -------------------------------------------------------------------------
    # INDEPENDENT vs SHARED due date detection
    # -------------------------------------------------------------------------

    def test_independent_chore_checks_per_assignee_due_dates(self) -> None:
        """INDEPENDENT chore checks per_assignee_due_dates for has_due_date."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: {
                "assignee-1": "2025-01-31T10:00:00"
            },
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        assert result == "reset_and_reschedule"

    def test_independent_chore_without_per_assignee_due_dates_resets_only(self) -> None:
        """INDEPENDENT chore without per_assignee_due_dates → reset_only."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: {},
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        assert result == "reset_only"

    def test_shared_chore_checks_chore_level_due_date(self) -> None:
        """SHARED chore checks chore-level due_date."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
            const.DATA_CHORE_DUE_DATE: "2025-01-31T10:00:00",
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        assert result == "reset_and_reschedule"

    def test_shared_chore_without_due_date_resets_only(self) -> None:
        """SHARED chore without due_date → reset_only."""
        chore_data = {
            const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
            # No DATA_CHORE_DUE_DATE key
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        assert result == "reset_only"

    # -------------------------------------------------------------------------
    # Default values tests
    # -------------------------------------------------------------------------

    def test_uses_default_values_for_missing_config(self) -> None:
        """Should use defaults when config keys are missing."""
        # Minimal chore data - relies on defaults
        chore_data = {
            # Approval reset defaults to AT_MIDNIGHT_ONCE
            # Overdue handling defaults to AT_DUE_DATE
            # Pending claims defaults to CLEAR
            # Recurring frequency defaults to NONE
            # Completion criteria defaults to SHARED
        }
        result = ChoreEngine.get_boundary_category(
            chore_data, const.CHORE_STATE_APPROVED, "midnight"
        )
        # APPROVED → reset_only (no due_date = reset_only)
        # approval_reset_type determines WHEN, not frequency
        assert result == "reset_only"


# =============================================================================
# TEST: DUE WINDOW START CALCULATION
# =============================================================================


class TestGetDueWindowStart:
    """Test due-window start calculation and invalid-input handling."""

    def test_valid_due_window_start(self) -> None:
        """Returns due_date - offset for valid inputs."""
        result = ChoreEngine.get_due_window_start(
            "2026-01-15T12:00:00+00:00",
            "2h",
        )
        assert result == datetime(2026, 1, 15, 10, 0, tzinfo=UTC)

    def test_missing_due_date_returns_none(self) -> None:
        """Returns None when no due date is provided."""
        result = ChoreEngine.get_due_window_start(None, "2h")
        assert result is None

    def test_zero_or_invalid_offset_returns_none(self) -> None:
        """Returns None for zero/invalid due window offsets."""
        assert (
            ChoreEngine.get_due_window_start(
                "2026-01-15T12:00:00+00:00",
                "0m",
            )
            is None
        )
        assert (
            ChoreEngine.get_due_window_start(
                "2026-01-15T12:00:00+00:00",
                "not-a-duration",
            )
            is None
        )

    def test_invalid_due_date_returns_none(self) -> None:
        """Returns None when due_date cannot be parsed."""
        result = ChoreEngine.get_due_window_start("invalid-date", "2h")
        assert result is None


# =============================================================================
# TEST: CRITERIA TRANSITION ACTIONS
# =============================================================================


class TestCriteriaTransitionActions:
    """Test field-change planning for mutable completion criteria."""

    def test_non_rotation_to_rotation_with_assignees_initializes_turn(self) -> None:
        """Transition to rotation initializes current turn and override flag."""
        chore_data = {const.DATA_CHORE_ASSIGNED_ASSIGNEES: ["assignee-1", "assignee-2"]}

        changes = ChoreEngine.get_criteria_transition_actions(
            const.COMPLETION_CRITERIA_INDEPENDENT,
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            chore_data,
        )

        assert changes == {
            const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID: "assignee-1",
            const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE: False,
        }

    def test_non_rotation_to_rotation_without_assignees_sets_override_only(
        self,
    ) -> None:
        """No assigned assignees means no current turn id is set."""
        chore_data: dict[str, object] = {const.DATA_CHORE_ASSIGNED_ASSIGNEES: []}

        changes = ChoreEngine.get_criteria_transition_actions(
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
            chore_data,
        )

        assert changes == {const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE: False}

    def test_rotation_to_non_rotation_clears_rotation_fields(self) -> None:
        """Transition away from rotation clears turn and override."""
        changes = ChoreEngine.get_criteria_transition_actions(
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_SHARED,
            {const.DATA_CHORE_ASSIGNED_ASSIGNEES: ["assignee-1", "assignee-2"]},
        )

        assert changes == {
            const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID: None,
            const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE: False,
        }

    def test_rotation_to_rotation_keeps_existing_turn(self) -> None:
        """Switching between rotation modes leaves turn fields unchanged."""
        changes = ChoreEngine.get_criteria_transition_actions(
            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            const.COMPLETION_CRITERIA_ROTATION_SMART,
            {const.DATA_CHORE_ASSIGNED_ASSIGNEES: ["assignee-1", "assignee-2"]},
        )

        assert changes == {}


# =============================================================================
# TEST: GLOBAL STATE EDGE CASES
# =============================================================================


class TestComputeGlobalChoreStateEdges:
    """Cover mixed-state edge cases for global state aggregation."""

    def test_single_claimer_not_my_turn_with_pending_shows_pending(self) -> None:
        """If any assignee can claim, single-claimer mode remains globally pending."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_NOT_MY_TURN,
            "assignee-2": const.CHORE_STATE_PENDING,
        }

        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_PENDING

    def test_single_claimer_all_not_my_turn_shows_not_my_turn(self) -> None:
        """All blocked by rotation yields not_my_turn global state."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_NOT_MY_TURN,
            "assignee-2": const.CHORE_STATE_NOT_MY_TURN,
        }

        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_NOT_MY_TURN

    def test_shared_due_and_pending_returns_unknown(self) -> None:
        """Mixed DUE/PENDING in shared mode currently resolves to UNKNOWN."""
        chore_data = {
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        }
        assignee_states = {
            "assignee-1": const.CHORE_STATE_DUE,
            "assignee-2": const.CHORE_STATE_PENDING,
        }

        result = ChoreEngine.compute_global_chore_state(chore_data, assignee_states)
        assert result == const.CHORE_STATE_UNKNOWN
