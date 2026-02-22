"""Chore state matrix tests - comprehensive state tracking verification.

This module tests that:
1. Per-assignee chore states are correctly tracked through all transitions
2. Global state (chore-level) correctly reflects aggregate of per-assignee states
3. All completion criteria types compute global state correctly

Phase 1 of the Chore Workflow Testing initiative.
See: docs/in-process/CHORE_WORKFLOW_TESTING_IN-PROCESS.md

Test Organization:
- TestStateMatrixIndependent: Single-assignee, verify per-assignee and global state match
- TestStateMatrixSharedFirst: 3 assignees, claimer=claimed, others=completed_by_other
- TestStateMatrixSharedAll: 3 assignees, partial states (claimed_in_part, approved_in_part)
- TestGlobalStateConsistency: Verify global always reflects aggregate
"""

# pylint: disable=redefined-outer-name

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import (
    # Chore states
    CHORE_STATE_APPROVED,
    CHORE_STATE_APPROVED_IN_PART,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_CLAIMED_IN_PART,
    CHORE_STATE_INDEPENDENT,
    CHORE_STATE_PENDING,
    CHORE_STATE_UNKNOWN,
    # Phase 2: DATA_KID_COMPLETED_BY_OTHER_CHORES removed (was line 38)
    COMPLETION_CRITERIA_SHARED_FIRST,
    # Data keys
    DATA_ASSIGNEE_CHORE_DATA,
    DATA_ASSIGNEE_CHORE_DATA_STATE,
    DATA_CHORE_ASSIGNED_ASSIGNEES,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_STATE,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 assignee, 1 approver, 5 chores (all independent)."""
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
    """Load shared scenario: 3 assignees, 1 approver, 8 shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_assignee_chore_state(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> str:
    """Get the current state of a chore for a specific assignee.

    This reads from assignee_chore_data which tracks per-assignee state.

    Args:
        coordinator: ChoreOpsDataCoordinator
        assignee_id: The assignee's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        State string (e.g., 'pending', 'claimed', 'approved')
    """
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    chore_data = assignee_data.get(DATA_ASSIGNEE_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_ASSIGNEE_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_global_chore_state(
    coordinator: Any,
    chore_id: str,
) -> str:
    """Get the global (chore-level) state aggregated across all assigned assignees.

    This is the state shown in the ATTR_GLOBAL_STATE attribute of chore status sensors.

    Args:
        coordinator: ChoreOpsDataCoordinator
        chore_id: The chore's internal UUID

    Returns:
        Global state string (e.g., 'pending', 'claimed', 'approved', 'claimed_in_part')
    """
    chore_info = coordinator.chores_data.get(chore_id, {})
    return chore_info.get(DATA_CHORE_STATE, CHORE_STATE_UNKNOWN)


def is_in_completed_by_other(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> bool:
    """Check if assignee sees chore as completed_by_other (Phase 2: computed dynamically).

    Args:
        coordinator: ChoreOpsDataCoordinator
        assignee_id: The assignee's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        True if chore is SHARED_FIRST and another assignee has claimed/approved
    """
    chore = coordinator.chores_data.get(chore_id, {})
    if chore.get(DATA_CHORE_COMPLETION_CRITERIA) != COMPLETION_CRITERIA_SHARED_FIRST:
        return False

    # Check if another assignee has claimed or approved this chore
    assigned_assignees = chore.get(DATA_CHORE_ASSIGNED_ASSIGNEES, [])
    for other_assignee_id in assigned_assignees:
        if other_assignee_id == assignee_id:
            continue
        other_assignee_data = coordinator.assignees_data.get(other_assignee_id, {})
        other_chore_data = other_assignee_data.get(DATA_ASSIGNEE_CHORE_DATA, {}).get(
            chore_id, {}
        )
        other_state = other_chore_data.get(
            DATA_ASSIGNEE_CHORE_DATA_STATE, CHORE_STATE_PENDING
        )
        if other_state in (CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED):
            return True
    return False


def chore_has_pending_claim(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> bool:
    """Check if assignee has a pending claim on the chore.

    Uses coordinator's method which checks timestamps.

    Args:
        coordinator: ChoreOpsDataCoordinator
        assignee_id: The assignee's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        True if assignee has pending claim
    """
    return coordinator.chore_manager.chore_has_pending_claim(assignee_id, chore_id)


# =============================================================================
# STATE MATRIX: INDEPENDENT CHORES
# =============================================================================


class TestStateMatrixIndependent:
    """Tests for independent chores - per-assignee and global state should always match."""

    @pytest.mark.asyncio
    async def test_initial_state_is_pending(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Fresh chore starts in PENDING state for both per-assignee and global."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        per_assignee_state = get_assignee_chore_state(
            coordinator, assignee_id, chore_id
        )
        global_state = get_global_chore_state(coordinator, chore_id)

        assert per_assignee_state == CHORE_STATE_PENDING
        assert global_state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_claim_changes_both_to_claimed(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Claiming sets both per-assignee and global state to CLAIMED."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

        per_assignee_state = get_assignee_chore_state(
            coordinator, assignee_id, chore_id
        )
        global_state = get_global_chore_state(coordinator, chore_id)

        assert per_assignee_state == CHORE_STATE_CLAIMED
        assert global_state == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_approve_changes_both_to_approved(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Approving sets both per-assignee and global state to APPROVED."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", assignee_id, chore_id)

        per_assignee_state = get_assignee_chore_state(
            coordinator, assignee_id, chore_id
        )
        global_state = get_global_chore_state(coordinator, chore_id)

        assert per_assignee_state == CHORE_STATE_APPROVED
        assert global_state == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_disapprove_resets_both_to_pending(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Disapproving resets both per-assignee and global state to PENDING."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.disapprove_chore(
                "Mom", assignee_id, chore_id
            )

        per_assignee_state = get_assignee_chore_state(
            coordinator, assignee_id, chore_id
        )
        global_state = get_global_chore_state(coordinator, chore_id)

        assert per_assignee_state == CHORE_STATE_PENDING
        assert global_state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_full_cycle_pending_claimed_approved_pending(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Track state through full cycle: pending → claimed → approved → (reset) → pending."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]

        states_observed = []

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Initial state
            states_observed.append(
                {
                    "step": "initial",
                    "per_assignee": get_assignee_chore_state(
                        coordinator, assignee_id, chore_id
                    ),
                    "global": get_global_chore_state(coordinator, chore_id),
                }
            )

            # Claim
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            states_observed.append(
                {
                    "step": "after_claim",
                    "per_assignee": get_assignee_chore_state(
                        coordinator, assignee_id, chore_id
                    ),
                    "global": get_global_chore_state(coordinator, chore_id),
                }
            )

            # Approve
            await coordinator.chore_manager.approve_chore("Mom", assignee_id, chore_id)
            states_observed.append(
                {
                    "step": "after_approve",
                    "per_assignee": get_assignee_chore_state(
                        coordinator, assignee_id, chore_id
                    ),
                    "global": get_global_chore_state(coordinator, chore_id),
                }
            )

        # Verify all states match expected
        assert states_observed[0]["per_assignee"] == CHORE_STATE_PENDING
        assert states_observed[0]["global"] == CHORE_STATE_PENDING

        assert states_observed[1]["per_assignee"] == CHORE_STATE_CLAIMED
        assert states_observed[1]["global"] == CHORE_STATE_CLAIMED

        assert states_observed[2]["per_assignee"] == CHORE_STATE_APPROVED
        assert states_observed[2]["global"] == CHORE_STATE_APPROVED


# =============================================================================
# STATE MATRIX: SHARED_FIRST CHORES
# =============================================================================


class TestStateMatrixSharedFirst:
    """Tests for shared_first chores - first claimer wins, others get completed_by_other."""

    @pytest.mark.asyncio
    async def test_initial_all_assignees_pending(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """All assignees start in PENDING state for shared_first chore."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Take out trash"]  # shared_first

        # All assignees should be pending
        assert (
            get_assignee_chore_state(coordinator, zoe_id, chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_chore_state(coordinator, max_id, chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_chore_state(coordinator, lila_id, chore_id)
            == CHORE_STATE_PENDING
        )

        # Global state should be pending
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_first_claimer_wins_others_blocked(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """First assignee to claim gets CLAIMED state, others get COMPLETED_BY_OTHER."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Take out trash"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Zoë claims first
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Zoë should be claimed
        assert chore_has_pending_claim(coordinator, zoe_id, chore_id) is True
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_CLAIMED

        # Max and Lila should be completed_by_other
        assert is_in_completed_by_other(coordinator, max_id, chore_id) is True
        assert is_in_completed_by_other(coordinator, lila_id, chore_id) is True

    @pytest.mark.asyncio
    async def test_approve_first_claimer_completes_chore(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Approving the first claimer sets global state to APPROVED."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Take out trash"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)

        # Zoë should be approved
        assert (
            coordinator.chore_manager.chore_is_approved_in_period(zoe_id, chore_id)
            is True
        )

        # Global state should be APPROVED (chore is complete)
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_APPROVED

        # Others remain completed_by_other
        assert is_in_completed_by_other(coordinator, max_id, chore_id) is True
        assert is_in_completed_by_other(coordinator, lila_id, chore_id) is True

    @pytest.mark.asyncio
    async def test_disapprove_resets_all_to_pending(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Disapproving the claimer resets all assignees back to PENDING."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Take out trash"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.disapprove_chore("Mom", zoe_id, chore_id)

        # Global state should be back to pending
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_PENDING

        # All assignees should no longer be in completed_by_other
        assert is_in_completed_by_other(coordinator, max_id, chore_id) is False
        assert is_in_completed_by_other(coordinator, lila_id, chore_id) is False


# =============================================================================
# STATE MATRIX: SHARED_ALL CHORES
# =============================================================================


class TestStateMatrixSharedAll:
    """Tests for shared_all chores - all assignees must complete, partial states tracked."""

    @pytest.mark.asyncio
    async def test_initial_all_assignees_pending(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """All assignees start in PENDING state for shared_all chore."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]  # shared_all

        # All assignees should be pending
        assert (
            get_assignee_chore_state(coordinator, zoe_id, chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_chore_state(coordinator, max_id, chore_id)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_chore_state(coordinator, lila_id, chore_id)
            == CHORE_STATE_PENDING
        )

        # Global state should be pending
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_one_assignee_claim_shows_claimed_in_part(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """When one assignee claims, global state becomes CLAIMED_IN_PART."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Zoë should have pending claim
        assert chore_has_pending_claim(coordinator, zoe_id, chore_id) is True

        # Global state should be claimed_in_part (not all claimed yet)
        assert (
            get_global_chore_state(coordinator, chore_id) == CHORE_STATE_CLAIMED_IN_PART
        )

    @pytest.mark.asyncio
    async def test_all_assignees_claim_shows_claimed(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """When all assignees claim, global state becomes CLAIMED."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")
            await coordinator.chore_manager.claim_chore(lila_id, chore_id, "Lila")

        # All should have pending claims
        assert chore_has_pending_claim(coordinator, zoe_id, chore_id) is True
        assert chore_has_pending_claim(coordinator, max_id, chore_id) is True
        assert chore_has_pending_claim(coordinator, lila_id, chore_id) is True

        # Global state should be claimed (all claimed)
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_one_assignee_approved_shows_approved_in_part(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """When one assignee is approved, global state becomes APPROVED_IN_PART."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # All claim
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")
            await coordinator.chore_manager.claim_chore(lila_id, chore_id, "Lila")

            # Only Zoë approved
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)

        # Zoë should be approved
        assert (
            coordinator.chore_manager.chore_is_approved_in_period(zoe_id, chore_id)
            is True
        )

        # Global state should be approved_in_part
        assert (
            get_global_chore_state(coordinator, chore_id)
            == CHORE_STATE_APPROVED_IN_PART
        )

    @pytest.mark.asyncio
    async def test_all_assignees_approved_shows_approved(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """When all assignees are approved, global state becomes APPROVED."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # All claim
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")
            await coordinator.chore_manager.claim_chore(lila_id, chore_id, "Lila")

            # All approved
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)
            await coordinator.chore_manager.approve_chore("Mom", max_id, chore_id)
            await coordinator.chore_manager.approve_chore("Mom", lila_id, chore_id)

        # All should be approved
        assert (
            coordinator.chore_manager.chore_is_approved_in_period(zoe_id, chore_id)
            is True
        )
        assert (
            coordinator.chore_manager.chore_is_approved_in_period(max_id, chore_id)
            is True
        )
        assert (
            coordinator.chore_manager.chore_is_approved_in_period(lila_id, chore_id)
            is True
        )

        # Global state should be approved (all approved)
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_partial_claim_partial_approve_mix(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Mixed states: some claimed, some approved - approved_in_part wins."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        _lila_id = scenario_shared.assignee_ids[
            "Lila"
        ]  # Lila stays pending (no action)
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Zoë claims and gets approved
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)

            # Max claims but not approved yet
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")

            # Lila hasn't claimed (pending)

        # State breakdown:
        # - Zoë: approved
        # - Max: claimed
        # - Lila: pending

        # Global state should be approved_in_part (there's at least one approval)
        assert (
            get_global_chore_state(coordinator, chore_id)
            == CHORE_STATE_APPROVED_IN_PART
        )


# =============================================================================
# GLOBAL STATE CONSISTENCY
# =============================================================================


class TestGlobalStateConsistency:
    """Verify global state always reflects correct aggregate of per-assignee states."""

    @pytest.mark.asyncio
    async def test_global_state_updates_on_each_action(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Global state updates correctly after each claim/approve action."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        chore_id = scenario_shared.chore_ids["Walk the dog"]  # shared_all, 2 assignees

        global_states_observed = []

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Initial
            global_states_observed.append(
                ("initial", get_global_chore_state(coordinator, chore_id))
            )

            # Zoë claims
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            global_states_observed.append(
                ("zoe_claim", get_global_chore_state(coordinator, chore_id))
            )

            # Max claims
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")
            global_states_observed.append(
                ("max_claim", get_global_chore_state(coordinator, chore_id))
            )

            # Zoë approved
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)
            global_states_observed.append(
                ("zoe_approve", get_global_chore_state(coordinator, chore_id))
            )

            # Max approved
            await coordinator.chore_manager.approve_chore("Mom", max_id, chore_id)
            global_states_observed.append(
                ("max_approve", get_global_chore_state(coordinator, chore_id))
            )

        # Verify progression
        assert global_states_observed[0] == ("initial", CHORE_STATE_PENDING)
        assert global_states_observed[1] == (
            "zoe_claim",
            CHORE_STATE_CLAIMED_IN_PART,
        )
        assert global_states_observed[2] == ("max_claim", CHORE_STATE_CLAIMED)
        assert global_states_observed[3] == (
            "zoe_approve",
            CHORE_STATE_APPROVED_IN_PART,
        )
        assert global_states_observed[4] == ("max_approve", CHORE_STATE_APPROVED)

    @pytest.mark.asyncio
    async def test_disapprove_in_partial_state_updates_global(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Disapproving one assignee in partial state should NOT affect other assignees' approvals.

        For SHARED_ALL chores, disapproving Max's claim should only reset Max to pending.
        Zoë's approval should remain valid - the global state should be approved_in_part.
        """
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        chore_id = scenario_shared.chore_ids["Walk the dog"]  # shared_all, 2 assignees

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Both claim
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")
            assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_CLAIMED

            # Zoë approved
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)
            assert (
                get_global_chore_state(coordinator, chore_id)
                == CHORE_STATE_APPROVED_IN_PART
            )

            # Max disapproved - only Max should reset, Zoë stays approved
            await coordinator.chore_manager.disapprove_chore("Mom", max_id, chore_id)

        # Max is now pending, Zoë is still approved = approved_in_part
        assert (
            get_global_chore_state(coordinator, chore_id)
            == CHORE_STATE_APPROVED_IN_PART
        )

    @pytest.mark.asyncio
    async def test_shared_all_three_assignee_transition_matrix_sequence(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Shared_all 3-assignee sequence follows expected claimed/approved transitions."""
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        lila_id = scenario_shared.assignee_ids["Lila"]
        chore_id = scenario_shared.chore_ids["Family dinner cleanup"]

        observed: list[str] = [get_global_chore_state(coordinator, chore_id)]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            observed.append(get_global_chore_state(coordinator, chore_id))

            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Max!")
            observed.append(get_global_chore_state(coordinator, chore_id))

            await coordinator.chore_manager.claim_chore(lila_id, chore_id, "Lila")
            observed.append(get_global_chore_state(coordinator, chore_id))

            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)
            observed.append(get_global_chore_state(coordinator, chore_id))

            await coordinator.chore_manager.approve_chore("Mom", max_id, chore_id)
            observed.append(get_global_chore_state(coordinator, chore_id))

            await coordinator.chore_manager.approve_chore("Mom", lila_id, chore_id)
            observed.append(get_global_chore_state(coordinator, chore_id))

        assert observed[0] == CHORE_STATE_PENDING
        assert observed[1] == CHORE_STATE_CLAIMED_IN_PART
        assert observed[2] == CHORE_STATE_CLAIMED_IN_PART
        assert observed[3] == CHORE_STATE_CLAIMED
        assert observed[4] == CHORE_STATE_APPROVED_IN_PART
        assert observed[5] == CHORE_STATE_APPROVED_IN_PART
        assert observed[6] == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_rotation_global_state_tracks_claim_without_losing_single_turn_pending(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Rotation chore keeps one pending turn holder and global independent on claim."""
        coordinator = scenario_shared.coordinator
        chore_id = scenario_shared.chore_ids["Dishes Rotation"]
        assigned_assignees = coordinator.chores_data[chore_id][
            DATA_CHORE_ASSIGNED_ASSIGNEES
        ]

        turn_holder = None
        for assignee_id in assigned_assignees:
            can_claim, _ = coordinator.chore_manager.can_claim_chore(
                assignee_id, chore_id
            )
            if can_claim:
                turn_holder = assignee_id
                break

        assert turn_holder is not None
        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_PENDING

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                turn_holder, chore_id, "Turn Assignee"
            )

        assert get_global_chore_state(coordinator, chore_id) == CHORE_STATE_INDEPENDENT
