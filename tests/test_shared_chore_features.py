"""Tests for SHARED and SHARED_FIRST chore auto-approve and pending claim actions.

This test module verifies that auto_approve and approval_reset_pending_claim_action
settings work correctly for shared chores (completion_criteria: shared_all and shared_first).

COMPLIANT WITH AGENT_TEST_CREATION_INSTRUCTIONS.md:
- Rule 2: Uses button presses with Context for claim/approve/disapprove workflows
- Rule 3: Uses dashboard helper as single source of entity IDs
- Rule 4: Gets button IDs from chore sensor attributes
- Rule 5: All service calls use Context for user authorization
- Rule 6: Coordinator data access only for internal logic verification and reset operations

Test coverage:
- SHARED_ALL auto-approve: Each kid's claim auto-approves for that kid
- SHARED_ALL pending claim actions: HOLD, CLEAR, AUTO_APPROVE behavior at reset
- SHARED_FIRST auto-approve: First kid to claim gets auto-approved
- SHARED_FIRST pending claim actions: HOLD, CLEAR, AUTO_APPROVE behavior at reset

NOTE: Reset operations use direct coordinator API because resets are internal
scheduler operations not exposed through button entities.

Uses scenario_shared.yaml which includes 8 specialized chores for these tests.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context, HomeAssistant
import pytest

from custom_components.choreops.utils.dt_utils import dt_now_utc
from tests.helpers import (
    # Pending claim action constants
    APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
    APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    APPROVAL_RESET_PENDING_CLAIM_HOLD,
    # State constants
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    # Phase 2: "completed_by_other" removed - use "completed_by_other" string literal
    CHORE_STATE_PENDING,
    # Completion criteria
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    # Data constants
    DATA_CHORE_APPROVAL_PERIOD_START,
    DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_DEFAULT_POINTS,
    DATA_CHORE_DUE_DATE,
    # Frequency
    SetupResult,
    setup_from_yaml,
)
from tests.helpers.workflows import (
    approve_chore,
    claim_chore,
    disapprove_chore,
    find_chore,
    get_dashboard_helper,
    get_kid_points,
)

if TYPE_CHECKING:
    from custom_components.choreops.coordinator import KidsChoresDataCoordinator
    from custom_components.choreops.type_defs import ChoreData


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def shared_scenario(
    hass: HomeAssistant, mock_hass_users: dict[str, Any]
) -> SetupResult:
    """Load the shared chore scenario with auto-approve and pending claim chores."""
    return await setup_from_yaml(
        hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml"
    )


# =============================================================================
# HELPER FUNCTIONS - State Verification via Sensor Entities
# =============================================================================


def get_chore_state_from_sensor(
    hass: HomeAssistant, kid_slug: str, chore_name: str
) -> str:
    """Get chore state from sensor entity (what the user sees in UI).

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe", "max", "lila")
        chore_name: Display name of chore

    Returns:
        State string from sensor entity
    """
    dashboard = get_dashboard_helper(hass, kid_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return "not_found"

    chore_state = hass.states.get(chore["eid"])
    return chore_state.state if chore_state else "unavailable"


def get_points_from_sensor(hass: HomeAssistant, kid_slug: str) -> float:
    """Get kid's points from sensor entity.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug

    Returns:
        Current point balance
    """
    return get_kid_points(hass, kid_slug)


def set_chore_due_date_to_past(
    coordinator: "KidsChoresDataCoordinator",
    chore_id: str,
    days_ago: int = 1,
) -> None:
    """Set a SHARED chore's due date to the past for reset testing.

    For SHARED chores, due_date and approval_period_start are at chore level.
    This helper directly modifies data WITHOUT triggering coordinator side effects.

    NOTE: This is acceptable as it's setting up test conditions for internal
    scheduler operations (reset), not simulating user actions.

    Args:
        coordinator: The coordinator instance
        chore_id: The chore's internal ID
        days_ago: How many days in the past to set the due date
    """
    chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})

    # Calculate past date
    past_date = dt_now_utc() - timedelta(days=days_ago)
    past_date_iso = past_date.isoformat()

    # Set approval_period_start BEFORE the past due date
    approval_start = past_date - timedelta(days=1)
    approval_start_iso = approval_start.isoformat()

    # SHARED chores: due_date and approval_period_start at chore level
    chore_info[DATA_CHORE_DUE_DATE] = past_date_iso
    chore_info[DATA_CHORE_APPROVAL_PERIOD_START] = approval_start_iso


# =============================================================================
# SHARED_ALL AUTO-APPROVE TESTS
# =============================================================================


class TestSharedAllAutoApprove:
    """Tests for shared_all chores with auto_approve=True.

    When a shared_all chore has auto_approve enabled, each kid's claim
    should automatically be approved for that kid (awarding points).
    """

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_first_kid(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: First kid claiming shared_all auto-approve chore gets approved."""
        coordinator = shared_scenario.coordinator

        # Verify chore configuration
        chore_id = shared_scenario.chore_ids["Shared All Auto Approve"]
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )

        # Get points before
        points_before = get_points_from_sensor(hass, "zoe")

        # Claim the chore via button press (should auto-approve)
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        result = await claim_chore(hass, "zoe", "Shared All Auto Approve", kid_context)
        assert result.success, f"Claim failed: {result.error}"

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Verify Zoë's state is APPROVED
        state = get_chore_state_from_sensor(hass, "zoe", "Shared All Auto Approve")
        assert state == CHORE_STATE_APPROVED, f"Expected APPROVED, got {state}"

        # Verify points awarded (chore is worth 12 points)
        points_after = get_points_from_sensor(hass, "zoe")
        assert points_after == points_before + 12.0

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_second_kid(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Second kid can also claim and get auto-approved (shared_all)."""
        # First kid claims
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared All Auto Approve", kid1_context)
        await hass.async_block_till_done()

        # Get Max's points before
        max_points_before = get_points_from_sensor(hass, "max")

        # Second kid claims (should also auto-approve)
        kid2_context = Context(user_id=mock_hass_users["kid2"].id)
        result = await claim_chore(hass, "max", "Shared All Auto Approve", kid2_context)
        assert result.success, f"Claim failed: {result.error}"

        await hass.async_block_till_done()

        # Verify Max's state is APPROVED
        max_state = get_chore_state_from_sensor(hass, "max", "Shared All Auto Approve")
        assert max_state == CHORE_STATE_APPROVED, f"Expected APPROVED, got {max_state}"

        # Verify Max got points
        max_points_after = get_points_from_sensor(hass, "max")
        assert max_points_after == max_points_before + 12.0

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_all_kids_get_points(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: All assigned kids can get points from shared_all auto-approve."""
        # Get initial points
        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")
        lila_before = get_points_from_sensor(hass, "lila")

        # All kids claim via button presses (each should auto-approve)
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)
        kid3_ctx = Context(user_id=mock_hass_users["kid3"].id)

        await claim_chore(hass, "zoe", "Shared All Auto Approve", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Auto Approve", kid2_ctx)
        await claim_chore(hass, "lila", "Shared All Auto Approve", kid3_ctx)

        # Wait for all auto-approve tasks to complete
        await hass.async_block_till_done()

        # All should have APPROVED state
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Auto Approve")
            == CHORE_STATE_APPROVED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Auto Approve")
            == CHORE_STATE_APPROVED
        )
        assert (
            get_chore_state_from_sensor(hass, "lila", "Shared All Auto Approve")
            == CHORE_STATE_APPROVED
        )

        # All should have received points (12 each)
        assert get_points_from_sensor(hass, "zoe") == zoe_before + 12.0
        assert get_points_from_sensor(hass, "max") == max_before + 12.0
        assert get_points_from_sensor(hass, "lila") == lila_before + 12.0


# =============================================================================
# SHARED_FIRST AUTO-APPROVE TESTS
# =============================================================================


class TestSharedFirstAutoApprove:
    """Tests for shared_first chores with auto_approve=True.

    When a shared_first chore has auto_approve enabled, the first kid to claim
    gets auto-approved and all other kids get 'completed_by_other' state.
    """

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_winner_gets_approved(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: First kid to claim shared_first auto-approve gets approved."""
        coordinator = shared_scenario.coordinator

        # Verify chore configuration
        chore_id = shared_scenario.chore_ids["Shared First Auto Approve"]
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        # Get points before
        points_before = get_points_from_sensor(hass, "zoe")

        # First kid claims via button press (should auto-approve)
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        result = await claim_chore(
            hass, "zoe", "Shared First Auto Approve", kid_context
        )
        assert result.success, f"Claim failed: {result.error}"

        await hass.async_block_till_done()

        # Verify Zoë's state is APPROVED
        state = get_chore_state_from_sensor(hass, "zoe", "Shared First Auto Approve")
        assert state == CHORE_STATE_APPROVED, f"Expected APPROVED, got {state}"

        # Verify points awarded (15 points)
        points_after = get_points_from_sensor(hass, "zoe")
        assert points_after == points_before + 15.0

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_others_completed_by_other(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Other kids get completed_by_other when first kid claims."""
        # Zoë claims first via button press (auto-approve)
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Auto Approve", kid_context)
        await hass.async_block_till_done()

        # Zoë should be APPROVED
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Auto Approve")
            == CHORE_STATE_APPROVED
        )

        # Max and Lila should be COMPLETED_BY_OTHER
        max_state = get_chore_state_from_sensor(
            hass, "max", "Shared First Auto Approve"
        )
        lila_state = get_chore_state_from_sensor(
            hass, "lila", "Shared First Auto Approve"
        )
        assert max_state == "completed_by_other", f"Max: {max_state}"
        assert lila_state == "completed_by_other", f"Lila: {lila_state}"

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_only_winner_gets_points(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Only the winning kid gets points in shared_first auto-approve."""
        # Get initial points
        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")

        # Zoë claims first via button press
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Auto Approve", kid_context)
        await hass.async_block_till_done()

        # Only Zoë should have points increase (15 points)
        assert get_points_from_sensor(hass, "zoe") == zoe_before + 15.0
        assert get_points_from_sensor(hass, "max") == max_before  # No change


# =============================================================================
# SHARED_ALL PENDING CLAIM ACTION TESTS
#
# NOTE: These tests use direct coordinator API for reset operations because
# resets are internal scheduler operations not exposed through button entities.
# =============================================================================


class TestSharedAllPendingClaimHold:
    """Tests for shared_all chores with pending_claim_action: hold_pending."""

    @pytest.mark.asyncio
    async def test_shared_all_hold_retains_claims_after_reset(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: HOLD action retains all kids' claims after reset."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared All Pending Hold"]

        # Verify configuration
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_HOLD
        )

        # Both kids claim via button presses
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        await claim_chore(hass, "zoe", "Shared All Pending Hold", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Pending Hold", kid2_ctx)

        # Verify both CLAIMED before reset
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Pending Hold")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Pending Hold")
            == CHORE_STATE_CLAIMED
        )

        # Trigger reset (INTERNAL API - HOLD chores are exempt from due date check)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Both should STILL be CLAIMED (hold action)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Pending Hold")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Pending Hold")
            == CHORE_STATE_CLAIMED
        )


class TestSharedAllPendingClaimClear:
    """Tests for shared_all chores with pending_claim_action: clear_pending."""

    @pytest.mark.asyncio
    async def test_shared_all_clear_resets_all_claims(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: CLEAR action resets all kids' claims to PENDING."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared All Pending Clear"]

        # Verify configuration
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_CLEAR
        )

        # Both kids claim via button presses
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        await claim_chore(hass, "zoe", "Shared All Pending Clear", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Pending Clear", kid2_ctx)

        # Set due date to past so reset will process
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)

        # Trigger reset (INTERNAL API)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Both should be PENDING (claims cleared)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Pending Clear")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Pending Clear")
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_shared_all_clear_no_points_awarded(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: CLEAR action does NOT award points."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared All Pending Clear"]

        # Get points before
        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")

        # Both kids claim via button presses
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        await claim_chore(hass, "zoe", "Shared All Pending Clear", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Pending Clear", kid2_ctx)

        # Set due date to past and trigger reset (INTERNAL API)
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # No points should have been awarded
        assert get_points_from_sensor(hass, "zoe") == zoe_before
        assert get_points_from_sensor(hass, "max") == max_before


class TestSharedAllPendingClaimAutoApprove:
    """Tests for shared_all chores with pending_claim_action: auto_approve_pending."""

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_pending_awards_points(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: AUTO_APPROVE action awards points to all kids with pending claims."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared All Pending Auto Approve"]

        # Verify configuration
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE
        )
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        # Get points before
        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")

        # Both kids claim via button presses
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        await claim_chore(hass, "zoe", "Shared All Pending Auto Approve", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Pending Auto Approve", kid2_ctx)

        # Set due date to past and trigger reset (INTERNAL API)
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Both should have received points (auto-approval)
        assert get_points_from_sensor(hass, "zoe") == zoe_before + chore_points
        assert get_points_from_sensor(hass, "max") == max_before + chore_points

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_pending_then_resets(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: AUTO_APPROVE action approves then resets to PENDING."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared All Pending Auto Approve"]

        # Both kids claim via button presses
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        await claim_chore(hass, "zoe", "Shared All Pending Auto Approve", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Pending Auto Approve", kid2_ctx)

        # Set due date to past and trigger reset (INTERNAL API)
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Both should be PENDING after auto-approval + reset
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Pending Auto Approve")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Pending Auto Approve")
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_pending_second_midnight_is_stable(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Shared_all auto-approve reset is idempotent across consecutive midnights.

        Regression intent: ensure first midnight performs auto-approve+reset exactly once,
        and a second midnight with no new claims does not re-award points or alter state.
        """
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared All Pending Auto Approve"]

        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")

        await claim_chore(hass, "zoe", "Shared All Pending Auto Approve", kid1_ctx)
        await claim_chore(hass, "max", "Shared All Pending Auto Approve", kid2_ctx)

        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Pending Auto Approve")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Pending Auto Approve")
            == CHORE_STATE_PENDING
        )

        zoe_after_first = get_points_from_sensor(hass, "zoe")
        max_after_first = get_points_from_sensor(hass, "max")
        assert zoe_after_first == zoe_before + chore_points
        assert max_after_first == max_before + chore_points

        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared All Pending Auto Approve")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared All Pending Auto Approve")
            == CHORE_STATE_PENDING
        )
        assert get_points_from_sensor(hass, "zoe") == zoe_after_first
        assert get_points_from_sensor(hass, "max") == max_after_first


# =============================================================================
# SHARED_FIRST PENDING CLAIM ACTION TESTS
#
# NOTE: These tests use direct coordinator API for reset operations because
# resets are internal scheduler operations not exposed through button entities.
# =============================================================================


class TestSharedFirstPendingClaimHold:
    """Tests for shared_first chores with pending_claim_action: hold_pending."""

    @pytest.mark.asyncio
    async def test_shared_first_hold_retains_claimer(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: HOLD action retains the claimer's claim after reset."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared First Pending Hold"]

        # Verify configuration
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_HOLD
        )

        # Zoë claims first via button press (Max becomes completed_by_other)
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Pending Hold", kid_ctx)

        # Verify states before reset
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Hold")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Pending Hold")
            == "completed_by_other"
        )

        # Trigger reset (INTERNAL API - HOLD chores are exempt from due date check)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Zoë should STILL be CLAIMED (hold action)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Hold")
            == CHORE_STATE_CLAIMED
        )


class TestSharedFirstPendingClaimClear:
    """Tests for shared_first chores with pending_claim_action: clear_pending."""

    @pytest.mark.asyncio
    async def test_shared_first_clear_resets_everyone(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: CLEAR action resets everyone to PENDING (new race)."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared First Pending Clear"]

        # Verify configuration
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_CLEAR
        )

        # Zoë claims first via button press
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Pending Clear", kid_ctx)

        # Set due date to past and trigger reset (INTERNAL API)
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Both should be PENDING (race reset)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Clear")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Pending Clear")
            == CHORE_STATE_PENDING
        )


class TestSharedFirstPendingClaimAutoApprove:
    """Tests for shared_first chores with pending_claim_action: auto_approve_pending."""

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_pending_awards_to_claimer(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: AUTO_APPROVE action awards points only to the claimer."""
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared First Pending Auto Approve"]

        # Verify configuration
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE
        )
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        # Get points before
        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")

        # Zoë claims first via button press (Max becomes completed_by_other)
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Pending Auto Approve", kid_ctx)

        # Set due date to past and trigger reset (INTERNAL API)
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Only Zoë should have received points
        assert get_points_from_sensor(hass, "zoe") == zoe_before + chore_points
        assert get_points_from_sensor(hass, "max") == max_before  # No change

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_pending_then_resets_all(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: AUTO_APPROVE action approves claimer then resets all to PENDING."""
        coordinator = shared_scenario.coordinator
        chore_id: str = shared_scenario.chore_ids["Shared First Pending Auto Approve"]

        # Zoë claims first via button press
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Pending Auto Approve", kid_ctx)

        # Set due date to past and trigger reset (INTERNAL API)
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Both should be PENDING after reset (new race begins)
        assert (
            get_chore_state_from_sensor(
                hass, "zoe", "Shared First Pending Auto Approve"
            )
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(
                hass, "max", "Shared First Pending Auto Approve"
            )
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_pending_second_midnight_is_stable(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Shared_first auto-approve reset is idempotent across consecutive midnights.

        Regression intent: ensure first midnight awards only winner and resets all,
        and second midnight with no new claim does not re-award or regress state.
        """
        coordinator = shared_scenario.coordinator
        chore_id: str = shared_scenario.chore_ids["Shared First Pending Auto Approve"]

        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)

        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")

        await claim_chore(hass, "zoe", "Shared First Pending Auto Approve", kid_ctx)

        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(
                hass, "zoe", "Shared First Pending Auto Approve"
            )
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(
                hass, "max", "Shared First Pending Auto Approve"
            )
            == CHORE_STATE_PENDING
        )

        zoe_after_first = get_points_from_sensor(hass, "zoe")
        max_after_first = get_points_from_sensor(hass, "max")
        assert zoe_after_first == zoe_before + chore_points
        assert max_after_first == max_before

        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(
                hass, "zoe", "Shared First Pending Auto Approve"
            )
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(
                hass, "max", "Shared First Pending Auto Approve"
            )
            == CHORE_STATE_PENDING
        )
        assert get_points_from_sensor(hass, "zoe") == zoe_after_first
        assert get_points_from_sensor(hass, "max") == max_after_first


# =============================================================================
# SHARED_FIRST EDGE CASE TESTS
# =============================================================================


class TestSharedFirstEdgeCases:
    """Tests for shared_first edge cases from legacy test coverage.

    These tests cover scenarios that aren't fully addressed by the auto-approve
    and pending claim action tests above:
    - Reclaim after disapproval (new race begins)
    - Global chore state transitions
    - Sensor consistency across kids
    """

    @pytest.mark.asyncio
    async def test_shared_first_reclaim_after_disapproval(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: After disapproval, ANY kid can claim (new race begins).

        Legacy: test_shared_first_reclaim_after_disapproval
        When a shared_first chore is disapproved, all kids reset to pending.
        This means the chore becomes a new race - a different kid can win.
        """
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Zoë claims first via button press (Max becomes completed_by_other)
        await claim_chore(hass, "zoe", "Shared First Pending Clear", kid1_ctx)

        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Clear")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Pending Clear")
            == "completed_by_other"
        )

        # Parent disapproves Zoë via button press - this resets all kids
        await disapprove_chore(hass, "zoe", "Shared First Pending Clear", parent_ctx)

        # Both should be reset to PENDING
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Clear")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Pending Clear")
            == CHORE_STATE_PENDING
        )

        # NOW: Max can claim (new race!)
        await claim_chore(hass, "max", "Shared First Pending Clear", kid2_ctx)

        # Max should be CLAIMED, Zoë should be COMPLETED_BY_OTHER
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Pending Clear")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Clear")
            == "completed_by_other"
        )

    @pytest.mark.asyncio
    async def test_shared_first_global_state_pending_to_claimed(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Global chore state transitions from pending to claimed.

        Legacy: test_shared_first_global_state_pending_to_claimed
        The chore's global state (DATA_CHORE_STATE) tracks overall status.

        NOTE: Uses coordinator data access to verify global state (internal data).
        """
        from tests.helpers.constants import DATA_CHORE_STATE

        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared First Pending Clear"]
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )

        # Initial global state (may be None/pending)
        initial_state = chore_info.get(DATA_CHORE_STATE)

        # First kid claims via button press
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Pending Clear", kid_ctx)

        # Global state should now be CLAIMED
        claimed_state = coordinator.chores_data[chore_id].get(DATA_CHORE_STATE)
        assert claimed_state == CHORE_STATE_CLAIMED, (
            f"Global state should be 'claimed' after first kid claims, "
            f"was: {initial_state}, now: {claimed_state}"
        )

    @pytest.mark.asyncio
    async def test_shared_first_global_state_claimed_to_approved(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Global chore state transitions from claimed to approved.

        Legacy: test_shared_first_global_state_claimed_to_approved

        NOTE: Uses coordinator data access to verify global state (internal data).
        """
        from tests.helpers.constants import DATA_CHORE_STATE

        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Shared First Pending Clear"]

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # First kid claims via button press
        await claim_chore(hass, "zoe", "Shared First Pending Clear", kid_ctx)

        # Verify claimed state
        claimed_state = coordinator.chores_data[chore_id].get(DATA_CHORE_STATE)
        assert claimed_state == CHORE_STATE_CLAIMED

        # Parent approves via button press
        await approve_chore(hass, "zoe", "Shared First Pending Clear", parent_ctx)

        # Global state should now be APPROVED
        approved_state = coordinator.chores_data[chore_id].get(DATA_CHORE_STATE)
        assert approved_state == CHORE_STATE_APPROVED, (
            f"Global state should be 'approved', got: {approved_state}"
        )

    @pytest.mark.asyncio
    async def test_shared_first_with_three_kids_blocked_claims(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Three-kid shared_first - second and third kids blocked.

        Legacy: test_shared_first_with_three_kids
        When one kid claims, all other kids immediately get completed_by_other.
        """
        # Get initial points
        zoe_before = get_points_from_sensor(hass, "zoe")
        max_before = get_points_from_sensor(hass, "max")
        lila_before = get_points_from_sensor(hass, "lila")

        # Zoë claims first via button press (auto-approved - this is auto-approve chore)
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Shared First Auto Approve", kid_ctx)
        await hass.async_block_till_done()

        # Zoë should be APPROVED (auto-approve chore)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Auto Approve")
            == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == zoe_before + 15.0

        # Max and Lila should be COMPLETED_BY_OTHER with NO points
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Auto Approve")
            == "completed_by_other"
        )
        assert (
            get_chore_state_from_sensor(hass, "lila", "Shared First Auto Approve")
            == "completed_by_other"
        )
        assert get_points_from_sensor(hass, "max") == max_before  # No points
        assert get_points_from_sensor(hass, "lila") == lila_before  # No points

    @pytest.mark.asyncio
    async def test_shared_first_disapproval_clears_completed_by_other(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Disapproval clears completed_by_other state for all kids.

        Legacy: test_shared_first_disapproval_resets_all_kids
        When the claimer is disapproved, ALL kids (including those blocked
        by completed_by_other status) should reset to pending.

        Phase 2: Tests computed completed_by_other logic via helper function.
        """
        from tests.test_chore_state_matrix import is_in_completed_by_other

        coordinator = shared_scenario.coordinator
        max_id = shared_scenario.kid_ids["Max!"]
        chore_id = shared_scenario.chore_ids["Shared First Pending Clear"]

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Zoë claims via button press (Max becomes blocked by completed_by_other)
        await claim_chore(hass, "zoe", "Shared First Pending Clear", kid_ctx)

        # Verify Max sees completed_by_other (computed check via helper)
        assert is_in_completed_by_other(coordinator, max_id, chore_id)

        # Disapprove Zoë via button press
        await disapprove_chore(hass, "zoe", "Shared First Pending Clear", parent_ctx)

        # Max should no longer see completed_by_other (computed check via helper)
        assert not is_in_completed_by_other(coordinator, max_id, chore_id), (
            "Chore should no longer be completed_by_other after disapproval"
        )

        # Both should be PENDING (verified via sensor)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Shared First Pending Clear")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Shared First Pending Clear")
            == CHORE_STATE_PENDING
        )


class TestSharedFirstRaceConditions:
    """Test race conditions in shared_first chores.

    Verifies that when multiple kids claim a shared_first chore concurrently:
    - Only ONE kid gets APPROVED (winner)
    - All others get COMPLETED_BY_OTHER (losers)
    - Points awarded only to winner
    - No double-point awards

    Uses asyncio.create_task() to simulate concurrent claims.
    """

    @pytest.mark.asyncio
    async def test_concurrent_claims_one_winner_only(
        self,
        hass: HomeAssistant,
        shared_scenario: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that concurrent claims result in exactly ONE winner.

        Scenario:
        - 3 kids (Zoë, Max, Lila) all claim the SAME shared_first chore simultaneously
        - Use asyncio.create_task() to simulate true concurrency

        Expected:
        - Exactly 1 kid: APPROVED (the winner - determined by race)
        - Exactly 2 kids: COMPLETED_BY_OTHER (the losers)

        NOTE: We don't assert WHICH kid wins (non-deterministic), just that
        exactly one winner exists and others are marked correctly.
        """
        from tests.helpers import claim_chore

        # Use "Shared First Auto Approve" chore for instant approval on claim
        chore_name = "Shared First Auto Approve"

        # Create concurrent claim tasks for all 3 kids
        zoe_ctx = Context(user_id=mock_hass_users["kid1"].id)
        max_ctx = Context(user_id=mock_hass_users["kid2"].id)
        lila_ctx = Context(user_id=mock_hass_users["kid3"].id)

        # Fire all 3 claims simultaneously
        import asyncio

        tasks = [
            asyncio.create_task(claim_chore(hass, "zoe", chore_name, zoe_ctx)),
            asyncio.create_task(claim_chore(hass, "max", chore_name, max_ctx)),
            asyncio.create_task(claim_chore(hass, "lila", chore_name, lila_ctx)),
        ]

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

        # Give entities time to update
        await hass.async_block_till_done()

        # Collect final states
        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        max_state = get_chore_state_from_sensor(hass, "max", chore_name)
        lila_state = get_chore_state_from_sensor(hass, "lila", chore_name)

        states = [zoe_state, max_state, lila_state]

        # Assert exactly 1 APPROVED
        approved_count = states.count(CHORE_STATE_APPROVED)
        assert approved_count == 1, (
            f"Expected exactly 1 APPROVED, got {approved_count}. "
            f"States: Zoë={zoe_state}, Max={max_state}, Lila={lila_state}"
        )

        # Assert exactly 2 COMPLETED_BY_OTHER
        completed_by_other_count = states.count("completed_by_other")
        assert completed_by_other_count == 2, (
            f"Expected exactly 2 COMPLETED_BY_OTHER, got {completed_by_other_count}. "
            f"States: Zoë={zoe_state}, Max={max_state}, Lila={lila_state}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_claims_one_point_award_only(
        self,
        hass: HomeAssistant,
        shared_scenario: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that concurrent claims award points to exactly ONE kid.

        Scenario:
        - 3 kids claim shared_first chore simultaneously
        - Chore worth 15 points (Shared First Auto Approve)

        Expected:
        - Winner gets +15 points
        - Losers get 0 points (no change)
        - Total system points increase = 15 (not 30 or 45)

        This ensures no double/triple point awards from race conditions.
        """
        from tests.helpers import claim_chore, get_kid_points

        chore_name = "Shared First Auto Approve"

        # Record starting points for all kids
        zoe_start = get_kid_points(hass, "zoe")
        max_start = get_kid_points(hass, "max")
        lila_start = get_kid_points(hass, "lila")
        total_start = zoe_start + max_start + lila_start

        # Fire concurrent claims
        zoe_ctx = Context(user_id=mock_hass_users["kid1"].id)
        max_ctx = Context(user_id=mock_hass_users["kid2"].id)
        lila_ctx = Context(user_id=mock_hass_users["kid3"].id)

        import asyncio

        tasks = [
            asyncio.create_task(claim_chore(hass, "zoe", chore_name, zoe_ctx)),
            asyncio.create_task(claim_chore(hass, "max", chore_name, max_ctx)),
            asyncio.create_task(claim_chore(hass, "lila", chore_name, lila_ctx)),
        ]

        await asyncio.gather(*tasks)
        await hass.async_block_till_done()

        # Get ending points
        zoe_end = get_kid_points(hass, "zoe")
        max_end = get_kid_points(hass, "max")
        lila_end = get_kid_points(hass, "lila")
        total_end = zoe_end + max_end + lila_end

        # Calculate point deltas
        zoe_delta = zoe_end - zoe_start
        max_delta = max_end - max_start
        lila_delta = lila_end - lila_start

        # Assert total system increase is 15 (chore default_points)
        total_delta = total_end - total_start
        assert total_delta == 15.0, (
            f"Expected total +15 points, got {total_delta}. "
            f"Deltas: Zoë={zoe_delta}, Max={max_delta}, Lila={lila_delta}"
        )

        # Assert exactly 1 kid got +15, others got 0
        deltas = [zoe_delta, max_delta, lila_delta]
        winners = [d for d in deltas if d == 15.0]
        losers = [d for d in deltas if d == 0.0]

        assert len(winners) == 1, (
            f"Expected exactly 1 kid with +15 points, got {len(winners)}. "
            f"Deltas: {deltas}"
        )
        assert len(losers) == 2, (
            f"Expected exactly 2 kids with 0 point change, got {len(losers)}. "
            f"Deltas: {deltas}"
        )
