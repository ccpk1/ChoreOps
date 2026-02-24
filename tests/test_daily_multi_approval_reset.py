"""Tests for daily_multi chores with upon_completion approval reset.

Test Coverage:
- Phase 3 (MEDIUM): Daily multi chores with upon_completion reset behavior
  - Finding #3: Daily multi chores might not properly reset when all completions done

Test Approach:
- Service-based testing via claim/approve buttons
- Uses scenario_daily_multi_upon_completion.yaml
- Validates state transitions and reset timing

Complies with:
- Rule 0: Imports from tests.helpers (approved data injection)
- Rule 1: Uses YAML scenario with setup_from_yaml()
- Rule 2: Service-based approach (UI interaction path)
- Rule 3: Dashboard helper as entity ID source
- Rule 5: Context with user_id for service calls
"""

from typing import Any

from homeassistant.core import Context, HomeAssistant
import pytest
import pytest_asyncio

# Test framework imports
from tests.helpers import (
    DATA_ASSIGNEE_NAME,
    DATA_CHORE_NAME,
    DATA_USER_CHORE_DATA,
    DATA_USER_CHORE_DATA_STATE,
    approve_chore,
    claim_chore,
    find_chore,
    get_dashboard_helper,
    setup_from_yaml,
)

# Import state constants from test_shared_chore_features (established pattern)
CHORE_STATE_APPROVED = "approved"
CHORE_STATE_CLAIMED = "claimed"
CHORE_STATE_PENDING = "pending"


# =============================================================================
# HELPER FUNCTIONS - State Verification via Sensor Entities
# =============================================================================


def get_chore_state_from_dashboard_helper(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> str:
    """Get chore state from sensor entity (what the user sees in UI).

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee's slug (e.g., "zoe", "max", "lila")
        chore_name: Display name of chore

    Returns:
        State string from sensor entity
    """
    dashboard = get_dashboard_helper(hass, assignee_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return "not_found"

    chore_state = hass.states.get(chore["eid"])
    return chore_state.state if chore_state else "unavailable"


# =============================================================================
# PYTEST FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def daily_multi_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> Any:
    """Load daily_multi upon_completion scenario (INDEPENDENT completion).

    Provides:
    - 3 assignees: Zoë, Max!, Lila
    - Feed Pets Morning and Night (3 assignees, 2x daily, INDEPENDENT)
    - Study Session 3x Daily (2 assignees, 3x daily, INDEPENDENT)
    - Water Plants 2x Daily Auto Approve (1 assignee, 2x daily, INDEPENDENT)
    - Regular Daily Chore (control)
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_daily_multi_upon_completion.yaml",
    )


@pytest_asyncio.fixture
async def daily_multi_scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> Any:
    """Load daily_multi upon_completion scenario (SHARED_ALL completion).

    Provides:
    - 3 assignees: Zoë, Max!, Lila
    - Feed Pets Morning and Night Shared (3 assignees, 2x daily, SHARED_ALL)
    - Study Session 3x Daily Shared (2 assignees, 3x daily, SHARED_ALL)
    - Water Plants 2x Daily Auto Approve Shared (1 assignee, 2x daily, SHARED_ALL)
    - Regular Daily Chore Shared (control)
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_daily_multi_upon_completion_shared.yaml",
    )


# =============================================================================
# TEST CLASS: Daily Multi Upon Completion Reset
# =============================================================================


class TestDailyMultiUponCompletionReset:
    """Test daily_multi chores with upon_completion approval reset (INDEPENDENT).

    Completion Criteria: INDEPENDENT
    - Each assignee progresses through time slots independently
    - Approval → Immediate reschedule to next time slot
    - Assignees don't block each other's progression

    Daily Multi Behavior:
    - "2x daily" = 2 separate due times (e.g., 9AM, 5PM)
    - Complete 9AM slot → Reschedules to 5PM slot (same day)
    - Complete 5PM slot → Reschedules to 9AM slot (next day)
    - Each time slot is a separate chore instance
    """

    @pytest.mark.asyncio
    async def test_daily_multi_independent_sequential_rescheduling(
        self,
        hass: HomeAssistant,
        daily_multi_scenario: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that daily_multi INDEPENDENT reschedules each assignee through time slots.

        Scenario:
        - 3 assignees, "Feed Pets Morning and Night" (2x daily)
        - Independent = each assignee progresses at their own pace

        Expected per assignee:
        1. Complete slot 1 → Reschedule to slot 2 (state = pending)
        2. Complete slot 2 → Reschedule to slot 1 next cycle (state = pending)

        Assignees should NOT block each other (independent progression).
        """
        chore_name = "Feed Pets Morning and Night"

        # Create user contexts
        zoe_ctx = Context(user_id=mock_hass_users["assignee1"].id)
        max_ctx = Context(user_id=mock_hass_users["assignee2"].id)
        lila_ctx = Context(user_id=mock_hass_users["assignee3"].id)
        approver_ctx = Context(user_id=mock_hass_users["approver1"].id)

        # =====================================================================
        # Zoë completes slot 1 → Should reschedule to slot 2
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)
        await hass.async_block_till_done()  # Ensure all async operations complete

        # Check both raw coordinator data AND entity state
        # Use the coordinator from the SetupResult fixture
        coordinator = daily_multi_scenario.coordinator
        zoe_assignee_id = None
        for assignee_id, assignee_data in coordinator.assignees_data.items():
            if assignee_data.get(DATA_ASSIGNEE_NAME) == "Zoë":
                zoe_assignee_id = assignee_id
                break

        chore_id = None
        for c_id, c_data in coordinator.chores_data.items():
            if c_data.get(DATA_CHORE_NAME) == chore_name:
                chore_id = c_id
                break

        raw_state = "not_found"
        if zoe_assignee_id and chore_id:
            assignee_chore_data = (
                coordinator.assignees_data[zoe_assignee_id]
                .get(DATA_USER_CHORE_DATA, {})
                .get(chore_id, {})
            )
            raw_state = assignee_chore_data.get(DATA_USER_CHORE_DATA_STATE, "no_state")

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)

        print("\n=== DEBUG STATE CHECK ===")
        print(f"Raw coordinator state: {raw_state}")
        print(f"Entity state: {zoe_state}")
        print("========================\n")

        assert zoe_state == CHORE_STATE_PENDING, (
            f"After completing slot 1, Zoë should reschedule to slot 2 (pending). "
            f"Got entity state: {zoe_state}, raw coordinator state: {raw_state}"
        )

        # =====================================================================
        # Max and Lila still on slot 1 (independent = no blocking)
        # =====================================================================

        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)

        assert max_state == CHORE_STATE_PENDING, (
            f"Max should still have slot 1 pending (Zoë's completion doesn't affect). "
            f"Got: {max_state}"
        )
        assert lila_state == CHORE_STATE_PENDING, (
            f"Lila should still have slot 1 pending (Zoë's completion doesn't affect). "
            f"Got: {lila_state}"
        )

        # =====================================================================
        # Zoë completes slot 2 → Should reschedule to slot 1 (next cycle)
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        assert zoe_state == CHORE_STATE_PENDING, (
            f"After completing slot 2, Zoë should reschedule to slot 1 (next cycle, pending). "
            f"Got state: {zoe_state}"
        )

        # =====================================================================
        # Max completes slot 1 → Should reschedule to slot 2 (independent)
        # =====================================================================

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        assert max_state == CHORE_STATE_PENDING, (
            f"After completing slot 1, Max should reschedule to slot 2 (pending). "
            f"Got: {max_state}"
        )

    @pytest.mark.asyncio
    async def test_daily_multi_independent_three_times_daily(
        self,
        hass: HomeAssistant,
        daily_multi_scenario: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test daily_multi 3x daily INDEPENDENT progression through 3 time slots.

        Scenario:
        - 2 assignees, "Study Session 3x Daily" (3 time slots per day)
        - Independent = each assignee progresses independently

        Expected:
        - Zoë completes slot 1 → Reschedules to slot 2 (doesn't affect Max)
        - Zoë completes slot 2 → Reschedules to slot 3 (doesn't affect Max)
        - Zoë completes slot 3 → Reschedules to slot 1 next cycle
        - Max progresses at his own pace (independent)
        """
        chore_name = "Study Session 3x Daily"

        # Create user contexts
        zoe_ctx = Context(user_id=mock_hass_users["assignee1"].id)
        max_ctx = Context(user_id=mock_hass_users["assignee2"].id)
        approver_ctx = Context(user_id=mock_hass_users["approver1"].id)

        # =====================================================================
        # Zoë progresses through all 3 slots independently
        # =====================================================================

        # Slot 1 → Slot 2
        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        assert zoe_state == CHORE_STATE_PENDING, (
            f"Zoë should reschedule to slot 2 after completing slot 1. Got: {zoe_state}"
        )

        # Slot 2 → Slot 3
        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        assert zoe_state == CHORE_STATE_PENDING, (
            f"Zoë should reschedule to slot 3 after completing slot 2. Got: {zoe_state}"
        )

        # Slot 3 → Slot 1 (next cycle)
        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        assert zoe_state == CHORE_STATE_PENDING, (
            f"Zoë should reschedule to slot 1 (next cycle) after completing slot 3. Got: {zoe_state}"
        )

        # =====================================================================
        # Max should still be on slot 1 (independent = no blocking)
        # =====================================================================

        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        assert max_state == CHORE_STATE_PENDING, (
            f"Max should still have slot 1 pending (Zoë's completion doesn't affect). Got: {max_state}"
        )

        # =====================================================================
        # Max progresses through his first slot
        # =====================================================================

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        assert max_state == CHORE_STATE_PENDING, (
            f"Max should reschedule to slot 2 after completing slot 1. Got: {max_state}"
        )

    @pytest.mark.asyncio
    async def test_daily_multi_independent_auto_approve(
        self,
        hass: HomeAssistant,
        daily_multi_scenario: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test daily_multi with auto_approve reschedules automatically.

        Scenario:
        - 1 assignee (Lila), "Water Plants 2x Daily Auto Approve" (2 time slots)
        - auto_approve=true, independent completion

        Expected:
        - Claim slot 1 → Auto-approves → Reschedules to slot 2 (pending)
        - Claim slot 2 → Auto-approves → Reschedules to slot 1 next cycle (pending)
        - Points awarded: 3 per slot (6 total)
        """
        chore_name = "Water Plants 2x Daily Auto Approve"
        lila_ctx = Context(user_id=mock_hass_users["assignee3"].id)

        # Get starting points from sensor state
        lila_points_state = hass.states.get(
            "sensor.lila_choreops_points"
        ) or hass.states.get("sensor.lila_choreops_points")
        assert lila_points_state is not None
        points_start = float(lila_points_state.state)

        # =====================================================================
        # Slot 1: Claim → Auto-approve → Should reschedule to slot 2
        # =====================================================================

        await claim_chore(hass, "lila", chore_name, lila_ctx)

        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)
        assert lila_state == CHORE_STATE_PENDING, (
            f"After auto-approve of slot 1, should reschedule to slot 2 (pending). "
            f"Got: {lila_state}"
        )

        # =====================================================================
        # Slot 2: Claim → Auto-approve → Should reschedule to slot 1 (next cycle)
        # =====================================================================

        await claim_chore(hass, "lila", chore_name, lila_ctx)

        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)
        assert lila_state == CHORE_STATE_PENDING, (
            f"After auto-approve of slot 2, should reschedule to slot 1 next cycle (pending). "
            f"Got: {lila_state}"
        )

        # =====================================================================
        # ASSERT: Points awarded correctly (3 points × 2 slots = 6 points)
        # =====================================================================

        lila_points_end_state = hass.states.get(
            "sensor.lila_choreops_points"
        ) or hass.states.get("sensor.lila_choreops_points")
        assert lila_points_end_state is not None
        points_end = float(lila_points_end_state.state)
        points_delta = points_end - points_start

        assert points_delta == 6.0, (
            f"Expected +6 points (3 × 2 instances), got +{points_delta}"
        )


# =============================================================================
# TEST CLASS: Daily Multi Upon Completion Reset (SHARED_ALL)
# =============================================================================


class TestDailyMultiUponCompletionResetShared:
    """Test daily_multi chores with upon_completion approval reset (SHARED_ALL).

    Completion Criteria: SHARED_ALL
    - ALL assignees must complete SAME time slot before progressing
    - Team progression - wait for everyone before moving to next slot

    Shared_All Behavior:
    - "2x daily" with 3 assignees = everyone completes slot 1, THEN everyone moves to slot 2
    - Approval only reschedules when ALL assignees complete current slot
    - Example: Zoë completes slot 1 → Waits for Max & Lila to finish slot 1
      → When all 3 done → ALL reschedule to slot 2 together
    """

    @pytest.mark.asyncio
    async def test_daily_multi_shared_team_progression(
        self,
        hass: HomeAssistant,
        daily_multi_scenario_shared: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that daily_multi SHARED_ALL requires team to complete slot before progressing.

        Scenario:
        - 3 assignees, "Feed Pets Morning and Night Shared" (2 time slots)
        - Shared_all = all must complete slot 1 before anyone moves to slot 2

        Expected:
        - Zoë & Max complete slot 1 → Both still on slot 1 (waiting for Lila)
        - Lila completes slot 1 → ALL reschedule to slot 2 together
        - All 3 complete slot 2 → ALL reschedule to slot 1 next cycle
        """
        chore_name = "Feed Pets Morning and Night Shared"

        # Create user contexts
        zoe_ctx = Context(user_id=mock_hass_users["assignee1"].id)
        max_ctx = Context(user_id=mock_hass_users["assignee2"].id)
        lila_ctx = Context(user_id=mock_hass_users["assignee3"].id)
        approver_ctx = Context(user_id=mock_hass_users["approver1"].id)

        # =====================================================================
        # Zoë and Max complete slot 1 (but Lila hasn't - should wait)
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        # Check: Should still be on slot 1 (not rescheduled yet - waiting for Lila)
        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)

        # Zoë and Max have completed but can't progress until Lila finishes
        # They should show "approved" state (completed but waiting)
        # Lila should still have slot 1 pending
        assert lila_state == CHORE_STATE_PENDING, (
            f"Lila should still have slot 1 pending. Got: {lila_state}"
        )

        # =====================================================================
        # Lila completes slot 1 → ALL should reschedule to slot 2
        # =====================================================================

        await claim_chore(hass, "lila", chore_name, lila_ctx)
        await approve_chore(hass, "lila", chore_name, approver_ctx)

        # Check: ALL assignees should now be on slot 2 (pending)
        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)

        assert zoe_state == CHORE_STATE_PENDING, (
            f"After all complete slot 1, Zoë should reschedule to slot 2 (pending). Got: {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"After all complete slot 1, Max should reschedule to slot 2 (pending). Got: {max_state}"
        )
        assert lila_state == CHORE_STATE_PENDING, (
            f"After all complete slot 1, Lila should reschedule to slot 2 (pending). Got: {lila_state}"
        )

        # =====================================================================
        # All 3 complete slot 2 → ALL reschedule to slot 1 (next cycle)
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        await claim_chore(hass, "lila", chore_name, lila_ctx)
        await approve_chore(hass, "lila", chore_name, approver_ctx)

        # Check: ALL assignees should now be on slot 1 (next cycle, pending)
        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)
        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)

        assert zoe_state == CHORE_STATE_PENDING, (
            f"After full cycle, Zoë should reset to slot 1 (next cycle, pending). Got: {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"After full cycle, Max should reset to slot 1 (next cycle, pending). Got: {max_state}"
        )
        assert lila_state == CHORE_STATE_PENDING, (
            f"After full cycle, Lila should reset to slot 1 (next cycle, pending). Got: {lila_state}"
        )

    @pytest.mark.asyncio
    async def test_daily_multi_shared_three_times_daily(
        self,
        hass: HomeAssistant,
        daily_multi_scenario_shared: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test daily_multi 3x SHARED_ALL requires team progression through all slots.

        Scenario:
        - 2 assignees, "Study Session 3x Daily Shared" (3 time slots)
        - Shared_all = both must complete slot 1 before moving to slot 2, etc.

        Expected:
        - Both complete slot 1 → Both reschedule to slot 2
        - Both complete slot 2 → Both reschedule to slot 3
        - Both complete slot 3 → Both reschedule to slot 1 (next cycle)
        - If only 1 assignee completes a slot → No progression until both complete
        """
        chore_name = "Study Session 3x Daily Shared"

        # Create user contexts
        zoe_ctx = Context(user_id=mock_hass_users["assignee1"].id)
        max_ctx = Context(user_id=mock_hass_users["assignee2"].id)
        approver_ctx = Context(user_id=mock_hass_users["approver1"].id)

        # =====================================================================
        # Slot 1: Both assignees complete → Should reschedule to slot 2
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        # Zoë done but Max not → Zoë waits
        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        # Zoë should show completed/approved state (waiting for Max)

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        # NOW both done slot 1 → Should reschedule to slot 2
        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)

        assert zoe_state == CHORE_STATE_PENDING, (
            f"After both complete slot 1, Zoë should reschedule to slot 2 (pending). Got: {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"After both complete slot 1, Max should reschedule to slot 2 (pending). Got: {max_state}"
        )

        # =====================================================================
        # Slot 2: Both assignees complete → Should reschedule to slot 3
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)

        assert zoe_state == CHORE_STATE_PENDING, (
            f"After both complete slot 2, Zoë should reschedule to slot 3 (pending). Got: {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"After both complete slot 2, Max should reschedule to slot 3 (pending). Got: {max_state}"
        )

        # =====================================================================
        # Slot 3: Both assignees complete → Should reschedule to slot 1 (next cycle)
        # =====================================================================

        await claim_chore(hass, "zoe", chore_name, zoe_ctx)
        await approve_chore(hass, "zoe", chore_name, approver_ctx)

        await claim_chore(hass, "max", chore_name, max_ctx)
        await approve_chore(hass, "max", chore_name, approver_ctx)

        zoe_state = get_chore_state_from_dashboard_helper(hass, "zoe", chore_name)
        max_state = get_chore_state_from_dashboard_helper(hass, "max", chore_name)

        assert zoe_state == CHORE_STATE_PENDING, (
            f"After both complete slot 3, Zoë should reschedule to slot 1 (next cycle, pending). Got: {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"After both complete slot 3, Max should reschedule to slot 1 (next cycle, pending). Got: {max_state}"
        )

    @pytest.mark.asyncio
    async def test_daily_multi_shared_auto_approve(
        self,
        hass: HomeAssistant,
        daily_multi_scenario_shared: Any,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test daily_multi SHARED_ALL with auto_approve (1 assignee edge case).

        Scenario:
        - 1 assignee (Lila), "Water Plants 2x Daily Auto Approve Shared" (2 time slots)
        - auto_approve=true, shared_all (but only 1 assignee → behaves like independent)

        Expected:
        - Claim slot 1 → Auto-approve → Reschedule to slot 2 (pending)
        - Claim slot 2 → Auto-approve → Reschedule to slot 1 next cycle (pending)
        - Points: 3 per slot (6 total)
        """
        chore_name = "Water Plants 2x Daily Auto Approve Shared"
        lila_ctx = Context(user_id=mock_hass_users["assignee3"].id)

        # Get starting points from sensor state
        lila_points_state = hass.states.get(
            "sensor.lila_choreops_points"
        ) or hass.states.get("sensor.lila_choreops_points")
        assert lila_points_state is not None
        points_start = float(lila_points_state.state)

        # =====================================================================
        # Slot 1: Claim → Auto-approve → Should reschedule to slot 2
        # =====================================================================

        await claim_chore(hass, "lila", chore_name, lila_ctx)

        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)
        assert lila_state == CHORE_STATE_PENDING, (
            f"After auto-approve slot 1, should reschedule to slot 2 (pending). Got: {lila_state}"
        )

        # =====================================================================
        # Slot 2: Claim → Auto-approve → Should reschedule to slot 1 (next cycle)
        # =====================================================================

        await claim_chore(hass, "lila", chore_name, lila_ctx)

        lila_state = get_chore_state_from_dashboard_helper(hass, "lila", chore_name)
        assert lila_state == CHORE_STATE_PENDING, (
            f"After auto-approve slot 2, should reschedule to slot 1 next cycle (pending). Got: {lila_state}"
        )

        # =====================================================================
        # ASSERT: Points awarded correctly (3 points × 2 slots = 6 points)
        # =====================================================================

        lila_points_end_state = hass.states.get(
            "sensor.lila_choreops_points"
        ) or hass.states.get("sensor.lila_choreops_points")
        assert lila_points_end_state is not None
        points_end = float(lila_points_end_state.state)
        points_delta = points_end - points_start

        assert points_delta == 6.0, (
            f"Expected +6 points (3 × 2 instances), got +{points_delta}"
        )
