"""Chore workflow tests using YAML scenarios.

These tests verify the complete claim → approve → points cycle
for all chore types using real config flow setup.

COMPLIANT WITH AGENT_TEST_CREATION_INSTRUCTIONS.md:
- Rule 2: Uses button presses with Context (not direct coordinator API)
- Rule 3: Uses dashboard helper as single source of entity IDs
- Rule 4: Gets button IDs from chore sensor attributes
- Rule 5: All service calls use Context for user authorization
- Rule 6: Coordinator data access only for internal logic verification

Test Organization:
- TestIndependentChores: Single-kid and multi-kid independent chores
- TestSharedFirstChores: Race-to-complete chores
- TestSharedAllChores: All-must-complete chores
- TestAutoApprove: Instant approval on claim
"""

# pylint: disable=redefined-outer-name
# hass fixture required for HA test setup

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import Context, HomeAssistant
import pytest

from custom_components.kidschores.utils.dt_utils import dt_now_utc
from tests.helpers import (
    ATTR_GLOBAL_STATE,
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_CLAIMED_IN_PART,
    CHORE_STATE_MISSED,
    CHORE_STATE_NOT_MY_TURN,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PENDING,
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_CUSTOM_INTERVAL,
    DATA_CHORE_CUSTOM_INTERVAL_UNIT,
    DATA_CHORE_DAILY_MULTI_TIMES,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_RECURRING_FREQUENCY,
    DOMAIN,
    FREQUENCY_CUSTOM,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
    FREQUENCY_DAILY,
    FREQUENCY_DAILY_MULTI,
    FREQUENCY_NONE,
    SERVICE_RESET_CHORES_TO_PENDING_STATE,
    TIME_UNIT_DAYS,
    TIME_UNIT_HOURS,
)
from tests.helpers.constants import ATTR_CHORE_CURRENT_STREAK
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.helpers.workflows import (
    approve_chore,
    claim_chore,
    disapprove_chore,
    find_chore,
    get_dashboard_helper,
    get_kid_points,
)

if TYPE_CHECKING:
    from custom_components.kidschores.type_defs import ChoreData, KidData


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 kid, 1 parent, 5 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load shared scenario: 3 kids, 1 parent, 8 shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def scenario_approval_reset_no_due_date(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scenario for testing approval reset with frequency=none, no due date."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_approval_reset_no_due_date.yaml",
    )


@pytest.fixture
async def scenario_enhanced_frequencies(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load enhanced frequencies scenario for Phase 5 tests.

    Contains chores with DAILY_MULTI, CUSTOM_FROM_COMPLETE, and CUSTOM hours.
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_enhanced_frequencies.yaml",
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
        kid_slug: Kid's slug (e.g., "zoe")
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


def get_chore_global_state_from_sensor(
    hass: HomeAssistant, kid_slug: str, chore_name: str
) -> str:
    """Get chore global state from sensor entity attributes.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        chore_name: Display name of chore

    Returns:
        Global state string from sensor attributes
    """
    dashboard = get_dashboard_helper(hass, kid_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return "not_found"

    chore_state = hass.states.get(chore["eid"])
    if chore_state is None:
        return "unavailable"

    return chore_state.attributes.get(ATTR_GLOBAL_STATE, "")


def get_chore_attributes_from_sensor(
    hass: HomeAssistant, kid_slug: str, chore_name: str
) -> dict[str, Any]:
    """Get all chore sensor attributes for a kid/chore pair."""
    dashboard = get_dashboard_helper(hass, kid_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return {}

    chore_state = hass.states.get(chore["eid"])
    if chore_state is None:
        return {}

    return dict(chore_state.attributes)


def get_points_from_sensor(hass: HomeAssistant, kid_slug: str) -> float:
    """Get kid's points from sensor entity.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug

    Returns:
        Current point balance
    """
    return get_kid_points(hass, kid_slug)


# =============================================================================
# INDEPENDENT CHORE TESTS
# =============================================================================


class TestIndependentChores:
    """Tests for chores with completion_criteria='independent'."""

    @pytest.mark.asyncio
    async def test_claim_changes_state_to_claimed(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Claiming a chore changes state from pending to claimed."""
        # Initial state should be pending (verified via sensor)
        initial_state = get_chore_state_from_sensor(hass, "zoe", "Make bed")
        assert initial_state == CHORE_STATE_PENDING

        # Claim the chore via button press with kid context
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        result = await claim_chore(hass, "zoe", "Make bed", kid_context)

        assert result.success, f"Claim failed: {result.error}"

        # State should now be claimed (verified via sensor)
        new_state = get_chore_state_from_sensor(hass, "zoe", "Make bed")
        assert new_state == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_approve_grants_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Approving a claimed chore grants points to the kid."""
        initial_points = get_points_from_sensor(hass, "zoe")

        # Claim the chore (kid context)
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", "Make bed", kid_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        # Approve the chore (parent context)
        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        approve_result = await approve_chore(hass, "zoe", "Make bed", parent_context)
        assert approve_result.success, f"Approve failed: {approve_result.error}"

        # Points should increase by chore value (5 points)
        final_points = get_points_from_sensor(hass, "zoe")
        assert final_points == initial_points + 5.0

        # State should be approved (verified via sensor)
        state = get_chore_state_from_sensor(hass, "zoe", "Make bed")
        assert state == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_disapprove_resets_to_pending(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Disapproving a claimed chore resets it to pending state."""
        # Claim the chore
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", "Make bed", kid_context)
        assert claim_result.success

        # Verify claimed via sensor
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_CLAIMED
        )

        # Disapprove (parent context)
        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        disapprove_result = await disapprove_chore(
            hass, "zoe", "Make bed", parent_context
        )
        assert disapprove_result.success, (
            f"Disapprove failed: {disapprove_result.error}"
        )

        # State should be reset to pending
        state = get_chore_state_from_sensor(hass, "zoe", "Make bed")
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_disapprove_does_not_grant_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Disapproving a chore does not change point balance."""
        initial_points = get_points_from_sensor(hass, "zoe")

        # Claim and disapprove
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Make bed", kid_context)

        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await disapprove_chore(hass, "zoe", "Make bed", parent_context)

        # Points should be unchanged
        final_points = get_points_from_sensor(hass, "zoe")
        assert final_points == initial_points

    @pytest.mark.asyncio
    async def test_pre_window_claim_lock_shows_waiting_and_blocks_claim(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Independent chore resolves to waiting before due window when lock enabled."""
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator
        chore_name = "Make bed"
        chore_id = scenario_minimal.chore_ids[chore_name]
        kid_id = scenario_minimal.kid_ids["Zoë"]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = {
            kid_id: (dt_now_utc() + timedelta(hours=3)).isoformat()
        }
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(hours=3)
        ).isoformat()
        chore_info[const.DATA_CHORE_DUE_WINDOW_OFFSET] = "1h"
        chore_info[const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW] = True

        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name)
            == const.CHORE_STATE_WAITING
        )
        attrs = get_chore_attributes_from_sensor(hass, "zoe", chore_name)
        assert attrs.get(const.ATTR_CAN_CLAIM) is False
        assert attrs.get(const.ATTR_CHORE_LOCK_REASON) == const.CHORE_STATE_WAITING

    @pytest.mark.asyncio
    async def test_pre_window_without_claim_lock_stays_pending_and_claimable(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Independent chore stays pending before due window when lock disabled."""
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator
        chore_name = "Make bed"
        chore_id = scenario_minimal.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(hours=3)
        ).isoformat()
        chore_info[const.DATA_CHORE_DUE_WINDOW_OFFSET] = "1h"
        chore_info[const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW] = False

        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name) == CHORE_STATE_PENDING
        )
        attrs = get_chore_attributes_from_sensor(hass, "zoe", chore_name)
        assert attrs.get(const.ATTR_CAN_CLAIM) is True
        assert attrs.get(const.ATTR_CHORE_LOCK_REASON) is None


# =============================================================================
# AUTO-APPROVE TESTS
# =============================================================================


class TestAutoApprove:
    """Tests for chores with auto_approve=True."""

    @pytest.mark.asyncio
    async def test_claim_triggers_instant_approval(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Claiming an auto-approve chore immediately grants approval and points."""
        initial_points = get_points_from_sensor(hass, "zoe")

        # Claim the auto-approve chore (Brush teeth = 3 points, auto_approve=true)
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        result = await claim_chore(hass, "zoe", "Brush teeth", kid_context)
        assert result.success, f"Claim failed: {result.error}"

        # Wait for auto-approve task to complete
        await hass.async_block_till_done()

        # State should be approved (skipped claimed)
        state = get_chore_state_from_sensor(hass, "zoe", "Brush teeth")
        assert state == CHORE_STATE_APPROVED

        # Points should have increased
        final_points = get_points_from_sensor(hass, "zoe")
        assert final_points == initial_points + 3.0


# =============================================================================
# SHARED_FIRST CHORE TESTS
# =============================================================================


class TestSharedFirstChores:
    """Tests for chores with completion_criteria='shared_first'.

    In shared_first chores:
    1. When one kid claims, all others immediately get 'completed_by_other'
    2. Only the claiming kid can be approved for points
    3. On disapproval, everyone resets to pending
    """

    @pytest.mark.asyncio
    async def test_claim_blocks_other_kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """First kid to claim blocks all other kids immediately."""
        # Zoë claims first
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        result = await claim_chore(hass, "zoe", "Take out trash", kid_context)
        assert result.success, f"Claim failed: {result.error}"

        # Zoë should be claimed
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Take out trash")
            == CHORE_STATE_CLAIMED
        )

        # Max and Lila should immediately be completed_by_other
        assert (
            get_chore_state_from_sensor(hass, "max", "Take out trash")
            == "completed_by_other"
        )
        assert (
            get_chore_state_from_sensor(hass, "lila", "Take out trash")
            == "completed_by_other"
        )

    @pytest.mark.asyncio
    async def test_secondary_kid_remains_completed_by_other_when_due_and_overdue(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Secondary kid stays completed_by_other even after due date passes.

        This is a focused regression for shared_first display priority:
        completed_by_other must take precedence over due/overdue for blocked kids.
        """
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared First Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        # Zoë claims first; Max becomes secondary blocked kid
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        # Secondary kid baseline state/attributes from chore status sensor
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == "completed_by_other"
        )
        max_attrs_before = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs_before.get(const.ATTR_CAN_CLAIM) is False
        assert max_attrs_before.get(const.ATTR_GLOBAL_STATE) == CHORE_STATE_CLAIMED
        assert max_attrs_before.get(const.ATTR_CHORE_LOCK_REASON) is None

        # Force chore past due date WITHOUT resetting state/ownership.
        # Do not use set_due_date() here because that API intentionally resets
        # chore state for all kids to begin a fresh cycle.
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Regression expectation: secondary kid must remain completed_by_other
        # (not due/overdue) while blocked from claiming.
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == "completed_by_other"
        )
        max_attrs_after = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs_after.get(const.ATTR_CAN_CLAIM) is False

    @pytest.mark.asyncio
    async def test_approve_grants_points_to_claimer_only(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Approving the claimer grants them points, others remain blocked."""
        initial_zoe_points = get_points_from_sensor(hass, "zoe")
        initial_max_points = get_points_from_sensor(hass, "max")
        initial_lila_points = get_points_from_sensor(hass, "lila")

        # Zoë claims
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Take out trash", kid_context)

        # Parent approves Zoë
        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await approve_chore(hass, "zoe", "Take out trash", parent_context)

        # Zoë should be approved with points (5 points)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Take out trash")
            == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == initial_zoe_points + 5.0

        # Max and Lila remain completed_by_other, no points
        assert (
            get_chore_state_from_sensor(hass, "max", "Take out trash")
            == "completed_by_other"
        )
        assert get_points_from_sensor(hass, "max") == initial_max_points

        assert (
            get_chore_state_from_sensor(hass, "lila", "Take out trash")
            == "completed_by_other"
        )
        assert get_points_from_sensor(hass, "lila") == initial_lila_points

    @pytest.mark.asyncio
    async def test_auto_approve_secondary_kid_remains_completed_by_other_when_overdue(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Auto-approve shared_first keeps secondary kid blocked across overdue."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared First Auto Approve"
        chore_id = scenario_shared.chore_ids[chore_name]

        initial_zoe_points = get_points_from_sensor(hass, "zoe")
        initial_max_points = get_points_from_sensor(hass, "max")

        # Zoë claims; auto-approve should immediately complete for Zoë
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"
        await hass.async_block_till_done()

        # Winner approved, secondary blocked by completed_by_other
        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name) == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == initial_zoe_points + 15.0
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == "completed_by_other"
        )
        max_attrs_before = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs_before.get(const.ATTR_CAN_CLAIM) is False
        assert get_points_from_sensor(hass, "max") == initial_max_points

        # Force due date to the past WITHOUT reset, then run periodic update
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Secondary kid remains completed_by_other and blocked after overdue pass
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == "completed_by_other"
        )
        max_attrs_after = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs_after.get(const.ATTR_CAN_CLAIM) is False

    @pytest.mark.asyncio
    async def test_disapprove_resets_all_kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Disapproving the claimer resets ALL kids to pending."""
        # Zoë claims (Max becomes completed_by_other)
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Organize garage", kid_context)

        assert (
            get_chore_state_from_sensor(hass, "max", "Organize garage")
            == "completed_by_other"
        )

        # Disapprove Zoë
        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await disapprove_chore(hass, "zoe", "Organize garage", parent_context)

        # Both should be reset to pending
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Organize garage")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Organize garage")
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_secondary_kid_stays_completed_by_other_in_due_window(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Secondary shared_first kid remains completed_by_other inside due window."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared First Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(minutes=30)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == "completed_by_other"
        )
        max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs.get(const.ATTR_CAN_CLAIM) is False

    @pytest.mark.asyncio
    async def test_disapprove_after_past_due_resets_all_shared_first_kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Disapprove clears shared_first winner/secondary states even when past due."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared First Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        parent_context = Context(user_id=mock_hass_users["parent1"].id)

        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        disapprove_result = await disapprove_chore(
            hass, "zoe", chore_name, parent_context
        )
        assert disapprove_result.success, (
            f"Disapprove failed: {disapprove_result.error}"
        )

        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name) == CHORE_STATE_OVERDUE
        )
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_OVERDUE
        )


# =============================================================================
# SHARED_ALL CHORE TESTS
# =============================================================================


class TestSharedAllChores:
    """Tests for chores with completion_criteria='shared_all'.

    In shared_all chores:
    - Each kid can claim and be approved independently
    - Each kid gets their own points when approved
    - All kids share the same global state tracking
    """

    @pytest.mark.asyncio
    async def test_secondary_kid_not_blocked_and_overdue_claimable_when_due_passes(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Shared_all secondary kid is not blocked and becomes overdue (claimable)."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared All Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        # Pin pre-overdue state: move due date far enough out that kid2 is not in
        # due window and should resolve to PENDING before any overdue transition.
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(days=2)
        ).isoformat()

        # Zoë claims first, but Max should remain claimable (shared_all semantics)
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name) == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_PENDING
        )

        max_attrs_before = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs_before.get(const.ATTR_CAN_CLAIM) is True
        assert (
            max_attrs_before.get(const.ATTR_GLOBAL_STATE) == CHORE_STATE_CLAIMED_IN_PART
        )

        # Force due date to past (no reset API) and run scheduler periodic update
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        # Shared_all secondary kid should transition to overdue and remain claimable
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_OVERDUE
        )
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) != "completed_by_other"
        )

        max_attrs_after = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs_after.get(const.ATTR_CAN_CLAIM) is True
        assert max_attrs_after.get(const.ATTR_GLOBAL_STATE) == CHORE_STATE_OVERDUE

    @pytest.mark.asyncio
    async def test_secondary_kid_enters_due_state_before_overdue_for_shared_all(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Shared_all secondary kid can be pinned to due state and remains claimable."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared All Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        # Configure due date inside due window (> now, < default 1h offset)
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(minutes=30)
        ).isoformat()

        # Zoë claims first; Max remains independently claimable in shared_all
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        # Secondary kid should resolve to DUE (not completed_by_other)
        assert get_chore_state_from_sensor(hass, "max", chore_name) == "due"
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) != "completed_by_other"
        )

        max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs.get(const.ATTR_CAN_CLAIM) is True
        assert max_attrs.get(const.ATTR_GLOBAL_STATE) == CHORE_STATE_CLAIMED_IN_PART

    @pytest.mark.asyncio
    async def test_secondary_kid_enters_missed_when_strict_overdue_lock_enabled(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Shared_all secondary kid resolves to missed under strict overdue lock."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared All Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        # Configure strict missed lock and past due
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
        )
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()

        # Zoë claims first to ensure shared_all global remains in-part while Max hits missed
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_MISSED
        )
        max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs.get(const.ATTR_CAN_CLAIM) is False
        assert max_attrs.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_MISSED

    @pytest.mark.asyncio
    async def test_each_kid_gets_points_on_approval(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Each kid gets points when they individually get approved."""
        initial_zoe = get_points_from_sensor(hass, "zoe")
        initial_max = get_points_from_sensor(hass, "max")

        # Walk the dog = shared_all, Zoë + Max, 8 pts

        # Zoë claims and gets approved
        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        parent_context = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "Walk the dog", kid1_context)
        await approve_chore(hass, "zoe", "Walk the dog", parent_context)

        # Zoë gets points immediately
        assert get_points_from_sensor(hass, "zoe") == initial_zoe + 8.0

        # Max claims and gets approved
        kid2_context = Context(user_id=mock_hass_users["kid2"].id)
        await claim_chore(hass, "max", "Walk the dog", kid2_context)
        await approve_chore(hass, "max", "Walk the dog", parent_context)

        # Max gets points
        assert get_points_from_sensor(hass, "max") == initial_max + 8.0

    @pytest.mark.asyncio
    async def test_three_kid_shared_all(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Three-kid shared_all chore - each gets points independently."""
        initial_zoe = get_points_from_sensor(hass, "zoe")
        initial_max = get_points_from_sensor(hass, "max")
        initial_lila = get_points_from_sensor(hass, "lila")

        # Family dinner cleanup = shared_all, 10 pts
        parent_context = Context(user_id=mock_hass_users["parent1"].id)

        # All three claim and get approved one by one
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Family dinner cleanup", kid1_ctx)
        await approve_chore(hass, "zoe", "Family dinner cleanup", parent_context)
        assert get_points_from_sensor(hass, "zoe") == initial_zoe + 10.0

        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)
        await claim_chore(hass, "max", "Family dinner cleanup", kid2_ctx)
        await approve_chore(hass, "max", "Family dinner cleanup", parent_context)
        assert get_points_from_sensor(hass, "max") == initial_max + 10.0

        kid3_ctx = Context(user_id=mock_hass_users["kid3"].id)
        await claim_chore(hass, "lila", "Family dinner cleanup", kid3_ctx)
        await approve_chore(hass, "lila", "Family dinner cleanup", parent_context)
        assert get_points_from_sensor(hass, "lila") == initial_lila + 10.0

    @pytest.mark.asyncio
    async def test_approved_state_tracked_per_kid(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Each kid has independent state tracking."""
        # Only Zoë completes the chore
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "Family dinner cleanup", kid1_ctx)
        await approve_chore(hass, "zoe", "Family dinner cleanup", parent_ctx)

        # Zoë is approved
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Family dinner cleanup")
            == CHORE_STATE_APPROVED
        )

        # Max and Lila are still pending
        assert (
            get_chore_state_from_sensor(hass, "max", "Family dinner cleanup")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "lila", "Family dinner cleanup")
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_secondary_kid_waiting_before_window_when_claim_lock_enabled_shared_all(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Shared_all secondary kid resolves to waiting pre-window when lock enabled."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared All Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(hours=3)
        ).isoformat()
        chore_info[const.DATA_CHORE_DUE_WINDOW_OFFSET] = "1h"
        chore_info[const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW] = True

        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "max", chore_name)
            == const.CHORE_STATE_WAITING
        )
        max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs.get(const.ATTR_CAN_CLAIM) is False
        assert max_attrs.get(const.ATTR_CHORE_LOCK_REASON) == const.CHORE_STATE_WAITING

    @pytest.mark.asyncio
    async def test_secondary_kid_pending_pre_window_when_claim_lock_disabled_shared_all(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Shared_all secondary kid stays pending pre-window when lock disabled."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared All Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(hours=3)
        ).isoformat()
        chore_info[const.DATA_CHORE_DUE_WINDOW_OFFSET] = "1h"
        chore_info[const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW] = False

        kid1_context = Context(user_id=mock_hass_users["kid1"].id)
        claim_result = await claim_chore(hass, "zoe", chore_name, kid1_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"

        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "max", chore_name) == CHORE_STATE_PENDING
        )
        max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert max_attrs.get(const.ATTR_CAN_CLAIM) is True
        assert max_attrs.get(const.ATTR_CHORE_LOCK_REASON) is None


class TestRotationSimpleChores:
    """Tests for chores with completion_criteria='rotation_simple'."""

    @pytest.mark.asyncio
    async def test_non_turn_kid_stays_not_my_turn_and_locked_when_due_passes(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Non-turn kid remains not_my_turn (not overdue/due) in rotation_simple."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Vacuum Living Room"
        chore_id = scenario_shared.chore_ids[chore_name]

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        max_state = get_chore_state_from_sensor(hass, "max", chore_name)

        # Exactly one kid should be blocked as not_my_turn in simple rotation
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and max_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            max_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "max"

        assert non_turn_slug, (
            "Expected exactly one non-turn kid in not_my_turn state for rotation_simple"
        )

        attrs_before = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_before.get(const.ATTR_CAN_CLAIM) is False
        assert attrs_before.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN

        # Force due date into the past and run scheduler periodic update.
        # Rotation lock should still take precedence for non-turn kid.
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, non_turn_slug, chore_name)
            == CHORE_STATE_NOT_MY_TURN
        )
        attrs_after = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_after.get(const.ATTR_CAN_CLAIM) is False
        assert attrs_after.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN

    @pytest.mark.asyncio
    async def test_non_turn_kid_stays_not_my_turn_before_due_when_allow_steal_enabled(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Rotation simple non-turn kid remains locked before steal window opens."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Vacuum Living Room"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL
        )
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(minutes=30)
        ).isoformat()

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        max_state = get_chore_state_from_sensor(hass, "max", chore_name)
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and max_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            max_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "max"

        assert non_turn_slug, "Expected one non-turn kid before steal window opens"
        attrs = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs.get(const.ATTR_CAN_CLAIM) is False
        assert attrs.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN

    @pytest.mark.asyncio
    async def test_non_turn_kid_transitions_to_overdue_when_allow_steal_enabled_and_past_due(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Rotation simple non-turn kid becomes overdue/claimable after due in steal mode."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Vacuum Living Room"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL
        )
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(minutes=30)
        ).isoformat()

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        max_state = get_chore_state_from_sensor(hass, "max", chore_name)
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and max_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            max_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "max"

        assert non_turn_slug, "Expected one non-turn kid before steal window opens"

        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, non_turn_slug, chore_name)
            == CHORE_STATE_OVERDUE
        )
        attrs_after = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_after.get(const.ATTR_CAN_CLAIM) is True
        assert attrs_after.get(const.ATTR_CHORE_LOCK_REASON) is None


class TestRotationSmartChores:
    """Tests for chores with completion_criteria='rotation_smart'."""

    @pytest.mark.asyncio
    async def test_non_turn_kid_stays_not_my_turn_and_locked_when_due_passes(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Non-turn kid remains not_my_turn (not overdue/due) in rotation_smart."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Clean Bathroom Mirror"
        chore_id = scenario_shared.chore_ids[chore_name]

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        lila_state = get_chore_state_from_sensor(hass, "lila", chore_name)

        # Exactly one kid should be blocked as not_my_turn in smart rotation
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and lila_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            lila_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "lila"

        assert non_turn_slug, (
            "Expected exactly one non-turn kid in not_my_turn state for rotation_smart"
        )

        attrs_before = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_before.get(const.ATTR_CAN_CLAIM) is False
        assert attrs_before.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN

        # Force due date into the past and run scheduler periodic update.
        # Rotation lock should still take precedence for non-turn kid.
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, non_turn_slug, chore_name)
            == CHORE_STATE_NOT_MY_TURN
        )
        attrs_after = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_after.get(const.ATTR_CAN_CLAIM) is False
        assert attrs_after.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN

    @pytest.mark.asyncio
    async def test_non_turn_kid_transitions_to_overdue_when_allow_steal_and_past_due(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Rotation smart non-turn kid moves from not_my_turn to overdue when steal opens."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Clean Bathroom Mirror"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL
        )
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(minutes=30)
        ).isoformat()

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        lila_state = get_chore_state_from_sensor(hass, "lila", chore_name)
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and lila_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            lila_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "lila"

        assert non_turn_slug, "Expected one non-turn kid before steal window opens"

        attrs_before = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_before.get(const.ATTR_CAN_CLAIM) is False
        assert attrs_before.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN

        # Open steal window by passing due date
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, non_turn_slug, chore_name)
            == CHORE_STATE_OVERDUE
        )
        attrs_after = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs_after.get(const.ATTR_CAN_CLAIM) is True
        assert attrs_after.get(const.ATTR_CHORE_LOCK_REASON) is None

    @pytest.mark.asyncio
    async def test_rotation_override_bypasses_not_my_turn_for_non_turn_kid(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Rotation override allows non-turn kid claim without immediate state flip."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Clean Bathroom Mirror"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() + timedelta(days=2)
        ).isoformat()

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        lila_state = get_chore_state_from_sensor(hass, "lila", chore_name)
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and lila_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            lila_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "lila"

        assert non_turn_slug, "Expected one non-turn kid before override"

        chore_info[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = True
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        kid_ctx_by_slug = {
            "zoe": Context(user_id=mock_hass_users["kid1"].id),
            "lila": Context(user_id=mock_hass_users["kid3"].id),
        }
        claim_result = await claim_chore(
            hass,
            non_turn_slug,
            chore_name,
            kid_ctx_by_slug[non_turn_slug],
        )
        assert claim_result.success, (
            f"Expected override to permit claim for {non_turn_slug}: "
            f"{claim_result.error}"
        )

    @pytest.mark.asyncio
    async def test_non_turn_kid_remains_not_my_turn_under_strict_missed_policy(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Rotation smart non-turn lock keeps precedence over strict missed when not in turn."""
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Clean Bathroom Mirror"
        chore_id = scenario_shared.chore_ids[chore_name]

        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
        )
        chore_info[const.DATA_CHORE_DUE_DATE] = (
            dt_now_utc() - timedelta(minutes=5)
        ).isoformat()

        zoe_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        lila_state = get_chore_state_from_sensor(hass, "lila", chore_name)
        non_turn_slug = ""
        if (
            zoe_state == CHORE_STATE_NOT_MY_TURN
            and lila_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "zoe"
        elif (
            lila_state == CHORE_STATE_NOT_MY_TURN
            and zoe_state != CHORE_STATE_NOT_MY_TURN
        ):
            non_turn_slug = "lila"

        assert non_turn_slug, "Expected one non-turn kid for rotation_smart"

        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, non_turn_slug, chore_name)
            == CHORE_STATE_NOT_MY_TURN
        )
        attrs = get_chore_attributes_from_sensor(hass, non_turn_slug, chore_name)
        assert attrs.get(const.ATTR_CAN_CLAIM) is False
        assert attrs.get(const.ATTR_CHORE_LOCK_REASON) == CHORE_STATE_NOT_MY_TURN


# =============================================================================
# APPROVAL RESET WITH NO DUE DATE TESTS (frequency="none")
# =============================================================================


class TestApprovalResetNoDueDate:
    """Test approval reset for chores with frequency='none' and no due_date.

    Key Insight from coordinator.py:
    - frequency="none" chores are ALWAYS included in reset checks
    - If no due_date_str exists, no date check blocks reset
    - Result: These chores reset immediately when _process_approval_boundary() runs

    NOTE: These tests use direct coordinator API for triggering resets,
    which is acceptable because reset is an internal scheduler operation
    not exposed through button entities.
    """

    @pytest.mark.asyncio
    async def test_independent_chore_resets_after_approval(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """INDEPENDENT chore with no due date resets from APPROVED to PENDING."""
        coordinator = scenario_approval_reset_no_due_date.coordinator

        # Verify chore has no due date and frequency="none"
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Independent"
        ]
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_NONE
        assert chore_info.get(DATA_CHORE_DUE_DATE) is None

        initial_kid1_points = get_points_from_sensor(hass, "zoe")

        # Kid1 claims and gets approved
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "No Due Date Independent", kid1_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Independent")
            == CHORE_STATE_CLAIMED
        )

        await approve_chore(hass, "zoe", "No Due Date Independent", parent_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Independent")
            == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == initial_kid1_points + 10.0

        # Kid2 remains pending (independent chore)
        assert (
            get_chore_state_from_sensor(hass, "max", "No Due Date Independent")
            == CHORE_STATE_PENDING
        )

        # Trigger approval reset (INTERNAL API - acceptable for scheduler operations)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # Kid1 should reset to PENDING (ready for next round)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Independent")
            == CHORE_STATE_PENDING
        )

        # Kid2 still pending (was never claimed)
        assert (
            get_chore_state_from_sensor(hass, "max", "No Due Date Independent")
            == CHORE_STATE_PENDING
        )

        # Points remain (reset doesn't remove points)
        assert get_points_from_sensor(hass, "zoe") == initial_kid1_points + 10.0

    @pytest.mark.asyncio
    async def test_shared_first_chore_resets_after_approval(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """SHARED_FIRST chore with no due date resets all kids to PENDING."""
        coordinator = scenario_approval_reset_no_due_date.coordinator

        # Verify chore configuration
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Shared First"
        ]
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_NONE
        assert chore_info.get(DATA_CHORE_DUE_DATE) is None
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        initial_kid1_points = get_points_from_sensor(hass, "zoe")

        # Kid1 claims (Kid2 becomes completed_by_other)
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "No Due Date Shared First", kid1_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Shared First")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "No Due Date Shared First")
            == "completed_by_other"
        )

        # Kid1 gets approved
        await approve_chore(hass, "zoe", "No Due Date Shared First", parent_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Shared First")
            == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == initial_kid1_points + 15.0

        # Trigger approval reset (INTERNAL API)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # BOTH kids should reset to PENDING (shared_first resets all)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Shared First")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "No Due Date Shared First")
            == CHORE_STATE_PENDING
        )

        # Points remain
        assert get_points_from_sensor(hass, "zoe") == initial_kid1_points + 15.0

    @pytest.mark.asyncio
    async def test_shared_all_chore_resets_after_approval(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """SHARED_ALL chore with no due date resets each kid independently."""
        coordinator = scenario_approval_reset_no_due_date.coordinator

        # Verify chore configuration
        chore_id = scenario_approval_reset_no_due_date.chore_ids[
            "No Due Date Shared All"
        ]
        chore_info: ChoreData | dict[str, Any] = coordinator.chores_data.get(
            chore_id, {}
        )
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_NONE
        assert chore_info.get(DATA_CHORE_DUE_DATE) is None
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )

        initial_kid1_points = get_points_from_sensor(hass, "zoe")
        initial_kid2_points = get_points_from_sensor(hass, "max")

        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Kid1 claims and gets approved
        await claim_chore(hass, "zoe", "No Due Date Shared All", kid1_ctx)
        await approve_chore(hass, "zoe", "No Due Date Shared All", parent_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Shared All")
            == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == initial_kid1_points + 20.0

        # Kid2 claims and gets approved
        await claim_chore(hass, "max", "No Due Date Shared All", kid2_ctx)
        await approve_chore(hass, "max", "No Due Date Shared All", parent_ctx)
        assert (
            get_chore_state_from_sensor(hass, "max", "No Due Date Shared All")
            == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "max") == initial_kid2_points + 20.0

        # Trigger approval reset (INTERNAL API)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # BOTH kids should reset to PENDING
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Shared All")
            == CHORE_STATE_PENDING
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "No Due Date Shared All")
            == CHORE_STATE_PENDING
        )

        # Points remain for both
        assert get_points_from_sensor(hass, "zoe") == initial_kid1_points + 20.0
        assert get_points_from_sensor(hass, "max") == initial_kid2_points + 20.0

    @pytest.mark.asyncio
    async def test_claimed_but_not_approved_also_resets(
        self,
        hass: HomeAssistant,
        scenario_approval_reset_no_due_date: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Chores in CLAIMED state (not approved) also reset to PENDING."""
        coordinator = scenario_approval_reset_no_due_date.coordinator

        # Kid1 claims but does NOT get approved
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "No Due Date Independent", kid1_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Independent")
            == CHORE_STATE_CLAIMED
        )

        # Trigger approval reset (INTERNAL API)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # Should reset to PENDING (default pending_claim_action is "clear")
        assert (
            get_chore_state_from_sensor(hass, "zoe", "No Due Date Independent")
            == CHORE_STATE_PENDING
        )


# =============================================================================
# WORKFLOW INTEGRATION EDGE CASES
# =============================================================================


class TestWorkflowIntegrationEdgeCases:
    """Tests for edge cases in chore workflows from legacy test coverage.

    These tests cover scenarios that ensure the full workflow integration
    behaves correctly in edge cases.
    """

    @pytest.mark.asyncio
    async def test_claim_does_not_change_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Claiming a chore does NOT award points (only approval does)."""
        initial_points = get_points_from_sensor(hass, "zoe")

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Make bed", kid_ctx)

        # Points should NOT change on claim
        final_points = get_points_from_sensor(hass, "zoe")
        assert final_points == initial_points, (
            "Points should not change on claim, only on approval"
        )

    @pytest.mark.asyncio
    async def test_multiple_claims_same_chore_different_kids_independent(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Independent chores allow multiple kids to claim.

        Each kid tracks their own state for independent chores.
        Walk the dog is shared_all (acts like independent per-kid tracking).
        """
        kid1_ctx = Context(user_id=mock_hass_users["kid1"].id)
        kid2_ctx = Context(user_id=mock_hass_users["kid2"].id)

        # Both kids can claim the same chore
        await claim_chore(hass, "zoe", "Walk the dog", kid1_ctx)
        await claim_chore(hass, "max", "Walk the dog", kid2_ctx)

        # Both should be CLAIMED (independent tracking)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Walk the dog")
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_chore_state_from_sensor(hass, "max", "Walk the dog")
            == CHORE_STATE_CLAIMED
        )

    @pytest.mark.asyncio
    async def test_approve_increments_chore_approval_count(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Approval increments the kid's chore approval count stats.

        StatisticsManager records approval counts in period buckets (including all_time)
        via _on_chore_approved listener.
        """
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        # Get initial approval count from period all_time bucket
        kid_info: KidData | dict[str, Any] = coordinator.kids_data.get(kid_id, {})
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        all_time_container = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
        all_time = all_time_container.get(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        )
        initial_count = all_time.get(const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0)

        # Claim and approve via button presses
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        await approve_chore(hass, "zoe", "Make bed", parent_ctx)

        # Get final approval count from period all_time bucket
        kid_info = coordinator.kids_data.get(kid_id, {})
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        all_time_container = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
        all_time = all_time_container.get(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        )
        final_count = all_time.get(const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0)

        assert final_count == initial_count + 1, (
            f"Approval count should increment: {initial_count} -> {final_count}"
        )

    @pytest.mark.asyncio
    async def test_disapprove_increments_disapproval_count(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Disapproval increments disapproval count.

        StatisticsManager records disapproval counts in period buckets (including all_time)
        via _on_chore_disapproved listener.
        """
        from custom_components.kidschores import const

        coordinator = scenario_minimal.coordinator
        kid_id = scenario_minimal.kid_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        # Get initial disapproval count from period all_time bucket
        kid_info: KidData | dict[str, Any] = coordinator.kids_data.get(kid_id, {})
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        all_time_container = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
        all_time = all_time_container.get(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        )
        initial_count = all_time.get(const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0)

        # Claim and disapprove via button presses
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        await disapprove_chore(hass, "zoe", "Make bed", parent_ctx)

        # Get final disapproval count from period all_time bucket
        kid_info = coordinator.kids_data.get(kid_id, {})
        kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        all_time_container = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
        all_time = all_time_container.get(
            const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}
        )
        final_count = all_time.get(const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0)

        assert final_count == initial_count + 1, (
            f"Disapproval count should increment: {initial_count} -> {final_count}"
        )

    @pytest.mark.asyncio
    async def test_approve_awards_default_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Approval awards the chore's default points.

        Note: points_awarded parameter is reserved for future feature.
        Currently, approval always uses the chore's default_points value.
        """
        initial_points = get_points_from_sensor(hass, "zoe")

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        await approve_chore(hass, "zoe", "Make bed", parent_ctx)

        final_points = get_points_from_sensor(hass, "zoe")
        assert final_points == initial_points + 5.0, (
            f"Should award default points (5): "
            f"{initial_points} + 5 = {initial_points + 5.0}, got {final_points}"
        )

    @pytest.mark.asyncio
    async def test_streak_updates_only_on_approval_not_claim_or_reset(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Current streak changes only on approval-completion events."""
        coordinator = scenario_minimal.coordinator
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        attrs_before = get_chore_attributes_from_sensor(hass, "zoe", "Make bed")
        streak_before = int(attrs_before.get(ATTR_CHORE_CURRENT_STREAK, 0) or 0)

        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        attrs_after_claim = get_chore_attributes_from_sensor(hass, "zoe", "Make bed")
        streak_after_claim = int(
            attrs_after_claim.get(ATTR_CHORE_CURRENT_STREAK, 0) or 0
        )
        assert streak_after_claim == streak_before

        await approve_chore(hass, "zoe", "Make bed", parent_ctx)
        attrs_after_approve = get_chore_attributes_from_sensor(hass, "zoe", "Make bed")
        streak_after_approve = int(
            attrs_after_approve.get(ATTR_CHORE_CURRENT_STREAK, 0) or 0
        )
        assert streak_after_approve == streak_before + 1

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        attrs_after_reset = get_chore_attributes_from_sensor(hass, "zoe", "Make bed")
        streak_after_reset = int(
            attrs_after_reset.get(ATTR_CHORE_CURRENT_STREAK, 0) or 0
        )
        assert streak_after_reset == streak_after_approve

    @pytest.mark.asyncio
    async def test_independent_kid_undo_claim_round_trip_sensor_consistency(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Kid undo claim round-trip preserves points and allows clean re-completion.

        Flow: pending -> claimed -> kid undo via disapprove button -> pending ->
        re-claim -> parent approve -> approved, with points awarded exactly once.
        """
        initial_points = get_points_from_sensor(hass, "zoe")

        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        parent_context = Context(user_id=mock_hass_users["parent1"].id)

        claim_result = await claim_chore(hass, "zoe", "Make bed", kid_context)
        assert claim_result.success, f"Claim failed: {claim_result.error}"
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_CLAIMED
        )

        # Kid pressing disapprove acts as undo-claim path in button handler
        undo_result = await disapprove_chore(hass, "zoe", "Make bed", kid_context)
        assert undo_result.success, f"Undo claim failed: {undo_result.error}"
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_PENDING
        )
        assert get_points_from_sensor(hass, "zoe") == initial_points

        reclaim_result = await claim_chore(hass, "zoe", "Make bed", kid_context)
        assert reclaim_result.success, f"Re-claim failed: {reclaim_result.error}"
        approve_result = await approve_chore(hass, "zoe", "Make bed", parent_context)
        assert approve_result.success, f"Approve failed: {approve_result.error}"
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_APPROVED
        )
        assert get_points_from_sensor(hass, "zoe") == initial_points + 5.0

    @pytest.mark.asyncio
    async def test_reset_service_mixed_states_restores_sensor_baseline(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Reset service restores mixed chore states to baseline user-visible states.

        Coverage target: shared_all approved, shared_first claimed/blocked, and
        rotation_simple claimed lock all reset safely via public reset service.
        """
        kid_context_zoe = Context(user_id=mock_hass_users["kid1"].id)
        parent_context = Context(user_id=mock_hass_users["parent1"].id)

        # Shared all: move one kid to approved
        claim_shared_all = await claim_chore(
            hass, "zoe", "Family dinner cleanup", kid_context_zoe
        )
        assert claim_shared_all.success, (
            f"Shared all claim failed: {claim_shared_all.error}"
        )
        approve_shared_all = await approve_chore(
            hass, "zoe", "Family dinner cleanup", parent_context
        )
        assert approve_shared_all.success, (
            f"Shared all approve failed: {approve_shared_all.error}"
        )

        # Shared first: claimer blocks other kids
        claim_shared_first = await claim_chore(
            hass, "zoe", "Take out trash", kid_context_zoe
        )
        assert claim_shared_first.success, (
            f"Shared first claim failed: {claim_shared_first.error}"
        )

        # Rotation: current turn holder claims to create claimed/not_my_turn split
        rotation_turn_slug: str | None = None
        for slug in ("zoe", "max", "lila"):
            rotation_chore = find_chore(
                get_dashboard_helper(hass, slug), "Dishes Rotation"
            )
            assert rotation_chore is not None
            if rotation_chore["status"] == CHORE_STATE_PENDING:
                rotation_turn_slug = slug
                break
        assert rotation_turn_slug is not None

        rotation_user_id = {
            "zoe": mock_hass_users["kid1"].id,
            "max": mock_hass_users["kid2"].id,
            "lila": mock_hass_users["kid3"].id,
        }[rotation_turn_slug]
        claim_rotation = await claim_chore(
            hass,
            rotation_turn_slug,
            "Dishes Rotation",
            Context(user_id=rotation_user_id),
        )
        assert claim_rotation.success, f"Rotation claim failed: {claim_rotation.error}"
        await hass.async_block_till_done()

        points_before_reset = {
            "zoe": get_points_from_sensor(hass, "zoe"),
            "max": get_points_from_sensor(hass, "max"),
            "lila": get_points_from_sensor(hass, "lila"),
        }

        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_CHORES_TO_PENDING_STATE,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Shared chores baseline: all pending for all kids
        for slug in ("zoe", "max", "lila"):
            assert (
                get_chore_state_from_sensor(hass, slug, "Family dinner cleanup")
                == CHORE_STATE_PENDING
            )
            assert (
                get_chore_state_from_sensor(hass, slug, "Take out trash")
                == CHORE_STATE_PENDING
            )

        # Rotation baseline: exactly one claimable holder, others locked not_my_turn
        rotation_pending_count = 0
        rotation_locked_count = 0
        for slug in ("zoe", "max", "lila"):
            rotation_chore = find_chore(
                get_dashboard_helper(hass, slug), "Dishes Rotation"
            )
            assert rotation_chore is not None
            sensor_state = hass.states.get(rotation_chore["eid"])
            assert sensor_state is not None
            if sensor_state.state == CHORE_STATE_PENDING:
                rotation_pending_count += 1
                assert sensor_state.attributes.get("can_claim") is True
            else:
                rotation_locked_count += 1
                assert sensor_state.state == CHORE_STATE_NOT_MY_TURN
                assert sensor_state.attributes.get("can_claim") is False

        assert rotation_pending_count == 1
        assert rotation_locked_count == 2

        # Reset should not alter already-awarded point balances
        assert get_points_from_sensor(hass, "zoe") == points_before_reset["zoe"]
        assert get_points_from_sensor(hass, "max") == points_before_reset["max"]
        assert get_points_from_sensor(hass, "lila") == points_before_reset["lila"]


class TestWorkflowResetIntegration:
    """Tests for approval reset integration in workflows.

    These tests verify that approval reset works correctly within
    the full workflow context.

    NOTE: Reset triggers use direct coordinator API because resets are
    internal scheduler operations not exposed through button entities.
    """

    @pytest.mark.asyncio
    async def test_approved_chore_resets_after_daily_cycle(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Approved daily chore resets to pending after reset cycle.

        After approval and reset, the chore should be ready for next day.
        """
        coordinator = scenario_minimal.coordinator

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Complete the workflow: claim -> approve
        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        await approve_chore(hass, "zoe", "Make bed", parent_ctx)

        # Verify approved
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_APPROVED
        )

        # Trigger daily reset (INTERNAL API)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # Should be back to PENDING (ready for next day)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_claimed_not_approved_clears_on_reset(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Claimed but not approved chores clear on reset (default behavior).

        The default pending_claim_action is "clear", so claimed chores
        should reset to pending when the approval period resets.
        """
        coordinator = scenario_minimal.coordinator

        # Claim but don't approve
        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_CLAIMED
        )

        # Trigger daily reset (INTERNAL API)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # Should be reset to PENDING (claim cleared)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_points_preserved_after_reset(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test: Points are preserved after reset (reset doesn't remove points).

        Validates that reset only affects chore states, not point balances.
        """
        coordinator = scenario_minimal.coordinator

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        await approve_chore(hass, "zoe", "Make bed", parent_ctx)

        # Record points after approval
        points_after_approval = get_points_from_sensor(hass, "zoe")
        assert points_after_approval > 0

        # Trigger reset (INTERNAL API)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        await hass.async_block_till_done()

        # Points should be unchanged
        points_after_reset = get_points_from_sensor(hass, "zoe")
        assert points_after_reset == points_after_approval, (
            "Reset should not affect point balance"
        )


# =============================================================================
# Enhanced Frequency Workflow Tests (CFE-2026-001, CFE-2026-002, CFE-2026-003)
# =============================================================================


class TestEnhancedFrequencyWorkflows:
    """Integration/workflow tests for Phase 5 enhanced frequency features.

    Tests the complete workflow for:
    - DAILY_MULTI: Multiple time slots per day
    - CUSTOM_FROM_COMPLETE: Reschedule from completion date
    - CUSTOM hours: Sub-daily intervals in hours

    These tests use the enhanced_frequencies scenario which contains chores
    configured with the Phase 5 frequency enhancements.
    """

    @pytest.mark.asyncio
    async def test_wf_01_daily_multi_claim_approve_workflow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """WF-01: DAILY_MULTI chore claim/approve workflow.

        Tests that a DAILY_MULTI chore can be claimed and approved,
        verifying the complete workflow operates correctly.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids["Daily Multi Single Kid"]

        # Verify this is a DAILY_MULTI chore with correct configuration
        chore: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI
        assert chore.get(DATA_CHORE_DAILY_MULTI_TIMES) == "09:00|21:00"

        # Initial state should be PENDING
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Daily Multi Single Kid")
            == CHORE_STATE_PENDING
        )

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Claim the chore
        await claim_chore(hass, "zoe", "Daily Multi Single Kid", kid_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Daily Multi Single Kid")
            == CHORE_STATE_CLAIMED
        )

        # Approve the chore
        await approve_chore(hass, "zoe", "Daily Multi Single Kid", parent_ctx)

        # After approval, state should change (APPROVED or PENDING based on reset)
        final_state = get_chore_state_from_sensor(hass, "zoe", "Daily Multi Single Kid")
        assert final_state in [CHORE_STATE_APPROVED, CHORE_STATE_PENDING]

    @pytest.mark.asyncio
    async def test_wf_02_custom_from_complete_claim_approve_workflow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """WF-02: CUSTOM_FROM_COMPLETE chore claim/approve workflow.

        Tests that a CUSTOM_FROM_COMPLETE chore can be claimed and approved,
        verifying the frequency type is handled correctly.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete Single"
        ]

        # Verify this is a CUSTOM_FROM_COMPLETE chore
        chore: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})
        assert (
            chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_CUSTOM_FROM_COMPLETE
        )
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL) == 5

        # Initial state should be PENDING
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Custom From Complete Single")
            == CHORE_STATE_PENDING
        )

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Claim the chore
        await claim_chore(hass, "zoe", "Custom From Complete Single", kid_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Custom From Complete Single")
            == CHORE_STATE_CLAIMED
        )

        # Approve the chore
        await approve_chore(hass, "zoe", "Custom From Complete Single", parent_ctx)

        # After approval with UPON_COMPLETION reset, should be PENDING
        final_state = get_chore_state_from_sensor(
            hass, "zoe", "Custom From Complete Single"
        )
        assert final_state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_wf_03_custom_hours_claim_approve_workflow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """WF-03: CUSTOM hours interval claim/approve workflow.

        Tests that a CUSTOM frequency chore with hours unit can be
        claimed and approved, verifying hourly intervals work correctly.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom Hours 8h Cross Midnight"
        ]

        # Verify this is a CUSTOM chore with hours unit
        chore: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_CUSTOM
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL_UNIT) == TIME_UNIT_HOURS
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL) == 8

        # Initial state should be PENDING
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Custom Hours 8h Cross Midnight")
            == CHORE_STATE_PENDING
        )

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Claim the chore
        await claim_chore(hass, "zoe", "Custom Hours 8h Cross Midnight", kid_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Custom Hours 8h Cross Midnight")
            == CHORE_STATE_CLAIMED
        )

        # Approve the chore
        await approve_chore(hass, "zoe", "Custom Hours 8h Cross Midnight", parent_ctx)

        # After approval, state should change
        final_state = get_chore_state_from_sensor(
            hass, "zoe", "Custom Hours 8h Cross Midnight"
        )
        assert final_state in [CHORE_STATE_APPROVED, CHORE_STATE_PENDING]

    @pytest.mark.asyncio
    async def test_wf_04_existing_daily_not_affected(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """WF-04: Regression test - standard DAILY chores unchanged.

        Verify that existing DAILY frequency chores still work correctly
        after Phase 5 enhancements. This is a regression test to ensure
        backwards compatibility with baseline chore types.
        """
        coordinator = scenario_minimal.coordinator
        chore_id = scenario_minimal.chore_ids["Make bed"]

        # Verify this is indeed a DAILY chore
        chore: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        # Standard workflow: claim -> approve
        await claim_chore(hass, "zoe", "Make bed", kid_ctx)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_CLAIMED
        )

        await approve_chore(hass, "zoe", "Make bed", parent_ctx)

        # Should be APPROVED (standard behavior)
        assert (
            get_chore_state_from_sensor(hass, "zoe", "Make bed") == CHORE_STATE_APPROVED
        )

    @pytest.mark.asyncio
    async def test_wf_05_daily_multi_upon_completion_advances_due_date_and_ui_consistency(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """WF-05: DAILY_MULTI + UPON_COMPLETION advances due date and keeps UI coherent.

        Best-in-class checks:
        - Due date advances after approval
        - Sensor state is pending again (new slot/cycle availability)
        - Dashboard helper and sensor agree on the same visible state
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_name = "Daily Multi Single Kid"
        chore_id = scenario_enhanced_frequencies.chore_ids[chore_name]
        kid_id = scenario_enhanced_frequencies.kid_ids["Zoë"]

        chore: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})
        assert chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

        initial_due_dt = coordinator.chore_manager.get_due_date(chore_id, kid_id)
        assert initial_due_dt is not None

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", chore_name, kid_ctx)
        await approve_chore(hass, "zoe", chore_name, parent_ctx)
        await hass.async_block_till_done()

        updated_due_dt = coordinator.chore_manager.get_due_date(chore_id, kid_id)
        assert updated_due_dt is not None
        assert updated_due_dt > initial_due_dt, (
            "Daily multi due date should advance after approval"
        )

        # UI-facing state consistency: dashboard helper and sensor must agree
        sensor_state = get_chore_state_from_sensor(hass, "zoe", chore_name)
        assert sensor_state == CHORE_STATE_PENDING
        dashboard = get_dashboard_helper(hass, "zoe")
        dashboard_chore = find_chore(dashboard, chore_name)
        assert dashboard_chore is not None
        assert dashboard_chore["status"] == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_wf_06_custom_from_complete_due_date_anchored_to_completion_timestamp(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """WF-06: CUSTOM_FROM_COMPLETE reschedules from completion time (not old due date).

        Best-in-class checks:
        - Reads completion timestamp from kid chore data
        - Verifies new due date is interval-anchored to completion
        - Verifies UI returns to pending for immediate next-cycle visibility
        """
        from custom_components.kidschores import const

        coordinator = scenario_enhanced_frequencies.coordinator
        chore_name = "Custom From Complete Single"
        chore_id = scenario_enhanced_frequencies.chore_ids[chore_name]
        kid_id = scenario_enhanced_frequencies.kid_ids["Zoë"]

        chore: ChoreData | dict[str, Any] = coordinator.chores_data.get(chore_id, {})
        assert (
            chore.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_CUSTOM_FROM_COMPLETE
        )
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL) == 5
        assert chore.get(DATA_CHORE_CUSTOM_INTERVAL_UNIT) == TIME_UNIT_DAYS

        kid_ctx = Context(user_id=mock_hass_users["kid1"].id)
        parent_ctx = Context(user_id=mock_hass_users["parent1"].id)

        await claim_chore(hass, "zoe", chore_name, kid_ctx)
        await approve_chore(hass, "zoe", chore_name, parent_ctx)
        await hass.async_block_till_done()

        kid_chore_data: KidData | dict[str, Any] = coordinator.kids_data.get(
            kid_id, {}
        ).get(const.DATA_KID_CHORE_DATA, {})
        chore_entry = kid_chore_data.get(chore_id, {})
        completion_anchor_iso = chore_entry.get(const.DATA_KID_CHORE_DATA_LAST_CLAIMED)
        new_due_dt = coordinator.chore_manager.get_due_date(chore_id, kid_id)

        assert isinstance(completion_anchor_iso, str)
        assert new_due_dt is not None

        completion_anchor_dt = dt_now_utc().__class__.fromisoformat(
            completion_anchor_iso
        )
        anchor_delta = new_due_dt - completion_anchor_dt

        # Allow small scheduling jitter while requiring interval anchoring behavior
        assert abs(anchor_delta - timedelta(days=5)) <= timedelta(minutes=2), (
            f"Expected ~5 days from completion anchor, got {anchor_delta}"
        )
        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name) == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_wf_07_independent_per_kid_due_dates_produce_divergent_ui_states(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """WF-07: Same chore shows different UI states for primary/secondary kids.

        Best-in-class checks:
        - One kid in due window (DUE), another before window (WAITING)
        - Claim lock + lock reason are asserted from UI sensor attributes
        - Dashboard helper reflects the same divergent statuses for each kid
        """
        from custom_components.kidschores import const

        coordinator = scenario_shared.coordinator
        chore_name = "Shared All Pending Hold"
        chore_id = scenario_shared.chore_ids[chore_name]
        zoe_id = scenario_shared.kid_ids["Zoë"]
        max_id = scenario_shared.kid_ids["Max!"]
        lila_id = scenario_shared.kid_ids["Lila"]

        now = dt_now_utc()
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
            const.COMPLETION_CRITERIA_INDEPENDENT
        )
        chore_info[const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW] = True
        chore_info[const.DATA_CHORE_DUE_WINDOW_OFFSET] = "1h"
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = {
            zoe_id: (now + timedelta(minutes=30)).isoformat(),
            max_id: (now + timedelta(hours=3)).isoformat(),
            lila_id: (now + timedelta(hours=3)).isoformat(),
        }
        chore_info[const.DATA_CHORE_DUE_DATE] = (now + timedelta(hours=3)).isoformat()

        await coordinator.chore_manager._on_periodic_update(now_utc=now)
        await hass.async_block_till_done()

        assert (
            get_chore_state_from_sensor(hass, "zoe", chore_name)
            == const.CHORE_STATE_DUE
        )
        assert (
            get_chore_state_from_sensor(hass, "max", chore_name)
            == const.CHORE_STATE_WAITING
        )

        zoe_attrs = get_chore_attributes_from_sensor(hass, "zoe", chore_name)
        max_attrs = get_chore_attributes_from_sensor(hass, "max", chore_name)
        assert zoe_attrs.get(const.ATTR_CAN_CLAIM) is True
        assert zoe_attrs.get(const.ATTR_CHORE_LOCK_REASON) is None
        assert max_attrs.get(const.ATTR_CAN_CLAIM) is False
        assert max_attrs.get(const.ATTR_CHORE_LOCK_REASON) == const.CHORE_STATE_WAITING

        zoe_dashboard = get_dashboard_helper(hass, "zoe")
        max_dashboard = get_dashboard_helper(hass, "max")
        zoe_chore = find_chore(zoe_dashboard, chore_name)
        max_chore = find_chore(max_dashboard, chore_name)
        assert zoe_chore is not None
        assert max_chore is not None
        assert zoe_chore["status"] == const.CHORE_STATE_DUE
        assert max_chore["status"] == const.CHORE_STATE_WAITING
