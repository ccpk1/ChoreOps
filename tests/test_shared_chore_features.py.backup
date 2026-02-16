"""Tests for SHARED and SHARED_FIRST chore auto-approve and pending claim actions.

This test module verifies that auto_approve and approval_reset_pending_claim_action
settings work correctly for shared chores (completion_criteria: shared_all and shared_first).

Test coverage:
- SHARED_ALL auto-approve: Each kid's claim auto-approves for that kid
- SHARED_ALL pending claim actions: HOLD, CLEAR, AUTO_APPROVE behavior at reset
- SHARED_FIRST auto-approve: First kid to claim gets auto-approved
- SHARED_FIRST pending claim actions: HOLD, CLEAR, AUTO_APPROVE behavior at reset

Uses scenario_shared.yaml which includes 8 specialized chores for these tests.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from tests.helpers import (
    # Pending claim action constants
    APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
    APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    APPROVAL_RESET_PENDING_CLAIM_HOLD,
    # State constants
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_COMPLETED_BY_OTHER,
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
    DATA_KID_POINTS,
    # Frequency
    FREQUENCY_DAILY,
    # Setup helpers
    SetupResult,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from custom_components.kidschores.coordinator import KidsChoresDataCoordinator


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
# HELPER FUNCTIONS
# =============================================================================


def get_kid_chore_state(
    coordinator: "KidsChoresDataCoordinator",
    kid_id: str,
    chore_id: str,
) -> str:
    """Get the state of a chore for a specific kid."""
    from tests.helpers.constants import DATA_KID_CHORE_DATA, DATA_KID_CHORE_DATA_STATE

    kid_info = coordinator.kids_data.get(kid_id, {})
    kid_chore_data = kid_info.get(DATA_KID_CHORE_DATA, {})
    chore_entry = kid_chore_data.get(chore_id, {})
    return chore_entry.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_kid_points(coordinator: "KidsChoresDataCoordinator", kid_id: str) -> float:
    """Get kid's current points."""
    kid_info = coordinator.kids_data.get(kid_id, {})
    return kid_info.get(DATA_KID_POINTS, 0.0)


def set_chore_due_date_to_past(
    coordinator: "KidsChoresDataCoordinator",
    chore_id: str,
    days_ago: int = 1,
) -> None:
    """Set a SHARED chore's due date to the past for reset testing.

    For SHARED chores, due_date and approval_period_start are at chore level.
    This helper directly modifies data WITHOUT triggering coordinator side effects.

    Args:
        coordinator: The coordinator instance
        chore_id: The chore's internal ID
        days_ago: How many days in the past to set the due date
    """
    chore_info = coordinator.chores_data.get(chore_id, {})

    # Calculate past date
    past_date = dt_util.utcnow() - timedelta(days=days_ago)
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
    ) -> None:
        """Test: First kid claiming shared_all auto-approve chore gets approved."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Auto Approve"]

        # Verify chore configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )

        # Get points before
        points_before = get_kid_points(coordinator, zoe_id)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Claim the chore (should auto-approve)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Verify Zoë's state is APPROVED
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_APPROVED, f"Expected APPROVED, got {state}"

        # Verify points awarded
        points_after = get_kid_points(coordinator, zoe_id)
        assert points_after == points_before + 12.0  # Chore is worth 12 points

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_second_kid(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: Second kid can also claim and get auto-approved (shared_all)."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Auto Approve"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # First kid claims
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Get Max's points before
        max_points_before = get_kid_points(coordinator, max_id)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Second kid claims (should also auto-approve)
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Verify Max's state is APPROVED
        max_state = get_kid_chore_state(coordinator, max_id, chore_id)
        assert max_state == CHORE_STATE_APPROVED, f"Expected APPROVED, got {max_state}"

        # Verify Max got points
        max_points_after = get_kid_points(coordinator, max_id)
        assert max_points_after == max_points_before + 12.0

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_all_kids_get_points(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: All assigned kids can get points from shared_all auto-approve."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        lila_id = shared_scenario.kid_ids["Lila"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Auto Approve"]

        # Get initial points
        zoe_before = get_kid_points(coordinator, zoe_id)
        max_before = get_kid_points(coordinator, max_id)
        lila_before = get_kid_points(coordinator, lila_id)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # All kids claim (each should auto-approve)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")
            await coordinator.chore_manager.claim_chore(lila_id, chore_id, "Lila")

        # Wait for all auto-approve tasks to complete
        await hass.async_block_till_done()

        # All should have APPROVED state
        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )
        assert (
            get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_APPROVED
        )
        assert (
            get_kid_chore_state(coordinator, lila_id, chore_id) == CHORE_STATE_APPROVED
        )

        # All should have received points
        assert get_kid_points(coordinator, zoe_id) == zoe_before + 12.0
        assert get_kid_points(coordinator, max_id) == max_before + 12.0
        assert get_kid_points(coordinator, lila_id) == lila_before + 12.0


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
    ) -> None:
        """Test: First kid to claim shared_first auto-approve gets approved."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Auto Approve"]

        # Verify chore configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        # Get points before
        points_before = get_kid_points(coordinator, zoe_id)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # First kid claims (should auto-approve)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Verify Zoë's state is APPROVED
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_APPROVED, f"Expected APPROVED, got {state}"

        # Verify points awarded
        points_after = get_kid_points(coordinator, zoe_id)
        assert points_after == points_before + 15.0  # Chore is worth 15 points

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_others_completed_by_other(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: Other kids get completed_by_other when first kid claims."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        lila_id = shared_scenario.kid_ids["Lila"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Auto Approve"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Zoë claims first (auto-approve)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Zoë should be APPROVED
        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )

        # Max and Lila should be COMPLETED_BY_OTHER
        max_state = get_kid_chore_state(coordinator, max_id, chore_id)
        lila_state = get_kid_chore_state(coordinator, lila_id, chore_id)
        assert max_state == CHORE_STATE_COMPLETED_BY_OTHER, f"Max: {max_state}"
        assert lila_state == CHORE_STATE_COMPLETED_BY_OTHER, f"Lila: {lila_state}"

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_only_winner_gets_points(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: Only the winning kid gets points in shared_first auto-approve."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Auto Approve"]

        # Get initial points
        zoe_before = get_kid_points(coordinator, zoe_id)
        max_before = get_kid_points(coordinator, max_id)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Zoë claims first
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Only Zoë should have points increase
        assert get_kid_points(coordinator, zoe_id) == zoe_before + 15.0
        assert get_kid_points(coordinator, max_id) == max_before  # No change


# =============================================================================
# SHARED_ALL PENDING CLAIM ACTION TESTS
# =============================================================================


class TestSharedAllPendingClaimHold:
    """Tests for shared_all chores with pending_claim_action: hold_pending."""

    @pytest.mark.asyncio
    async def test_shared_all_hold_retains_claims_after_reset(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: HOLD action retains all kids' claims after reset."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Hold"]

        # Verify configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_HOLD
        )

        # Both kids claim
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

        # Verify both CLAIMED before reset
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_CLAIMED

        # Trigger reset (HOLD chores are exempt from due date check)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Both should STILL be CLAIMED (hold action)
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_CLAIMED


class TestSharedAllPendingClaimClear:
    """Tests for shared_all chores with pending_claim_action: clear_pending."""

    @pytest.mark.asyncio
    async def test_shared_all_clear_resets_all_claims(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: CLEAR action resets all kids' claims to PENDING."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Clear"]

        # Verify configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_CLEAR
        )

        # Both kids claim
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

        # Set due date to past so reset will process
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Both should be PENDING (claims cleared)
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_shared_all_clear_no_points_awarded(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: CLEAR action does NOT award points."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Clear"]

        # Get points before
        zoe_before = get_kid_points(coordinator, zoe_id)
        max_before = get_kid_points(coordinator, max_id)

        # Both kids claim
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

        # Set due date to past and trigger reset
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # No points should have been awarded
        assert get_kid_points(coordinator, zoe_id) == zoe_before
        assert get_kid_points(coordinator, max_id) == max_before


class TestSharedAllPendingClaimAutoApprove:
    """Tests for shared_all chores with pending_claim_action: auto_approve_pending."""

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_pending_awards_points(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE action awards points to all kids with pending claims."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Auto Approve"]

        # Verify configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE
        )
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        # Get points before
        zoe_before = get_kid_points(coordinator, zoe_id)
        max_before = get_kid_points(coordinator, max_id)

        # Both kids claim
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

        # Set due date to past and trigger reset
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Both should have received points (auto-approval)
        assert get_kid_points(coordinator, zoe_id) == zoe_before + chore_points
        assert get_kid_points(coordinator, max_id) == max_before + chore_points

    @pytest.mark.asyncio
    async def test_shared_all_auto_approve_pending_then_resets(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE action approves then resets to PENDING."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Auto Approve"]

        # Both kids claim
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

        # Set due date to past and trigger reset
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Both should be PENDING after auto-approval + reset
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING


# =============================================================================
# SHARED_FIRST PENDING CLAIM ACTION TESTS
# =============================================================================


class TestSharedFirstPendingClaimHold:
    """Tests for shared_first chores with pending_claim_action: hold_pending."""

    @pytest.mark.asyncio
    async def test_shared_first_hold_retains_claimer(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: HOLD action retains the claimer's claim after reset."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Hold"]

        # Verify configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_HOLD
        )

        # Zoë claims first (Max becomes completed_by_other)
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Verify states before reset
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED
        assert (
            get_kid_chore_state(coordinator, max_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )

        # Trigger reset (HOLD chores are exempt from due date check)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Zoë should STILL be CLAIMED (hold action)
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED


class TestSharedFirstPendingClaimClear:
    """Tests for shared_first chores with pending_claim_action: clear_pending."""

    @pytest.mark.asyncio
    async def test_shared_first_clear_resets_everyone(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: CLEAR action resets everyone to PENDING (new race)."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Clear"]

        # Verify configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_CLEAR
        )

        # Zoë claims first
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Set due date to past and trigger reset
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Both should be PENDING (race reset)
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING


class TestSharedFirstPendingClaimAutoApprove:
    """Tests for shared_first chores with pending_claim_action: auto_approve_pending."""

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_pending_awards_to_claimer(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE action awards points only to the claimer."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Auto Approve"]

        # Verify configuration
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE
        )
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        # Get points before
        zoe_before = get_kid_points(coordinator, zoe_id)
        max_before = get_kid_points(coordinator, max_id)

        # Zoë claims first (Max becomes completed_by_other)
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Set due date to past and trigger reset
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Only Zoë should have received points
        assert get_kid_points(coordinator, zoe_id) == zoe_before + chore_points
        assert get_kid_points(coordinator, max_id) == max_before  # No change

    @pytest.mark.asyncio
    async def test_shared_first_auto_approve_pending_then_resets_all(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE action approves claimer then resets all to PENDING."""
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Auto Approve"]

        # Zoë claims first
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Set due date to past and trigger reset
        set_chore_due_date_to_past(coordinator, chore_id, days_ago=1)
        await coordinator.chore_manager._reset_daily_chore_statuses([FREQUENCY_DAILY])

        # Both should be PENDING after reset (new race begins)
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING


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
    ) -> None:
        """Test: After disapproval, ANY kid can claim (new race begins).

        Legacy: test_shared_first_reclaim_after_disapproval
        When a shared_first chore is disapproved, all kids reset to pending.
        This means the chore becomes a new race - a different kid can win.
        """
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        # Use a non-auto-approve shared_first chore
        chore_id = chore_map["Shared First Pending Clear"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Zoë claims first (Max becomes completed_by_other)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

            assert (
                get_kid_chore_state(coordinator, zoe_id, chore_id)
                == CHORE_STATE_CLAIMED
            )
            assert (
                get_kid_chore_state(coordinator, max_id, chore_id)
                == CHORE_STATE_COMPLETED_BY_OTHER
            )

            # Parent disapproves Zoë - this resets all kids
            await coordinator.chore_manager.disapprove_chore("Mom", zoe_id, chore_id)

            # Both should be reset to PENDING
            assert (
                get_kid_chore_state(coordinator, zoe_id, chore_id)
                == CHORE_STATE_PENDING
            )
            assert (
                get_kid_chore_state(coordinator, max_id, chore_id)
                == CHORE_STATE_PENDING
            )

            # NOW: Max can claim (new race!)
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max")

            # Max should be CLAIMED, Zoë should be COMPLETED_BY_OTHER
            assert (
                get_kid_chore_state(coordinator, max_id, chore_id)
                == CHORE_STATE_CLAIMED
            )
            assert (
                get_kid_chore_state(coordinator, zoe_id, chore_id)
                == CHORE_STATE_COMPLETED_BY_OTHER
            )

    @pytest.mark.asyncio
    async def test_shared_first_global_state_pending_to_claimed(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: Global chore state transitions from pending to claimed.

        Legacy: test_shared_first_global_state_pending_to_claimed
        The chore's global state (DATA_CHORE_STATE) tracks overall status.
        """
        from tests.helpers.constants import DATA_CHORE_STATE

        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Clear"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Initial global state (may be None/pending)
        initial_state = chore_info.get(DATA_CHORE_STATE)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # First kid claims
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

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
    ) -> None:
        """Test: Global chore state transitions from claimed to approved.

        Legacy: test_shared_first_global_state_claimed_to_approved
        """
        from tests.helpers.constants import DATA_CHORE_STATE

        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Clear"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # First kid claims
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

            # Verify claimed state
            claimed_state = coordinator.chores_data[chore_id].get(DATA_CHORE_STATE)
            assert claimed_state == CHORE_STATE_CLAIMED

            # Parent approves
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)

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
    ) -> None:
        """Test: Three-kid shared_first - second and third kids blocked.

        Legacy: test_shared_first_with_three_kids
        When one kid claims, all other kids immediately get completed_by_other.
        """
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        lila_id = shared_scenario.kid_ids["Lila"]
        chore_map = shared_scenario.chore_ids

        # Use auto-approve chore (3 kids assigned)
        chore_id = chore_map["Shared First Auto Approve"]

        # Get initial points
        zoe_before = get_kid_points(coordinator, zoe_id)
        max_before = get_kid_points(coordinator, max_id)
        lila_before = get_kid_points(coordinator, lila_id)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Zoë claims first (auto-approved)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # Zoë should be APPROVED (auto-approve chore)
        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )
        assert get_kid_points(coordinator, zoe_id) == zoe_before + 15.0

        # Max and Lila should be COMPLETED_BY_OTHER with NO points
        assert (
            get_kid_chore_state(coordinator, max_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )
        assert (
            get_kid_chore_state(coordinator, lila_id, chore_id)
            == CHORE_STATE_COMPLETED_BY_OTHER
        )
        assert get_kid_points(coordinator, max_id) == max_before  # No points
        assert get_kid_points(coordinator, lila_id) == lila_before  # No points

    @pytest.mark.asyncio
    async def test_shared_first_disapproval_clears_completed_by_other(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: Disapproval clears completed_by_other state for all kids.

        Legacy: test_shared_first_disapproval_resets_all_kids
        When the claimer is disapproved, ALL kids (including those in
        completed_by_other state) should reset to pending.
        """
        from tests.helpers.constants import DATA_KID_COMPLETED_BY_OTHER_CHORES

        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Clear"]

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            # Zoë claims (Max becomes completed_by_other)
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

            # Verify Max is in completed_by_other
            max_completed_by_other = coordinator.kids_data[max_id].get(
                DATA_KID_COMPLETED_BY_OTHER_CHORES, []
            )
            assert chore_id in max_completed_by_other

            # Disapprove Zoë
            await coordinator.chore_manager.disapprove_chore("Mom", zoe_id, chore_id)

        # Max should no longer have chore in completed_by_other
        max_completed_by_other = coordinator.kids_data[max_id].get(
            DATA_KID_COMPLETED_BY_OTHER_CHORES, []
        )
        assert chore_id not in max_completed_by_other, (
            "Chore should be removed from completed_by_other after disapproval"
        )

        # Both should be PENDING
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING
        assert get_kid_chore_state(coordinator, max_id, chore_id) == CHORE_STATE_PENDING
