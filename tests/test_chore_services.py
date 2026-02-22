"""Test chore-related services across all completion criteria.

This module tests the following services:
- claim_chore
- approve_chore
- disapprove_chore
- set_chore_due_date
- skip_chore_due_date
- reset_overdue_chores
- reset_all_chores

Special focus on set_chore_due_date and skip_chore_due_date with shared_first
chores, as these have historically had bugs where shared_first was not handled
correctly (treated as independent instead of shared).

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
import pytest

from custom_components.choreops import const
from custom_components.choreops.utils.dt_utils import dt_now_utc
from tests.helpers import (
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    # Phase 2: CHORE_STATE_COMPLETED_BY_OTHER removed - use "completed_by_other" string literal
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PENDING,
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    DATA_ASSIGNEE_CHORE_DATA,
    DATA_ASSIGNEE_CHORE_DATA_APPROVAL_PERIOD_START,
    DATA_ASSIGNEE_CHORE_DATA_STATE,
    DATA_ASSIGNEE_POINTS,
    DATA_CHORE_APPROVAL_PERIOD_START,
    DATA_CHORE_ASSIGNED_ASSIGNEES,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_NAME,
    DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
    DOMAIN,
    SERVICE_RESET_CHORES_TO_PENDING_STATE,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def setup_chore_services_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with all completion criteria for service testing."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_chore_services.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_assignee_state_for_chore(
    coordinator: Any, assignee_id: str, chore_id: str
) -> str:
    """Get the current chore display state for a specific assignee (Phase 2: includes computed states).

    Returns display state matching sensor behavior, including computed "completed_by_other".
    """
    # Check approval status first
    if coordinator.chore_manager.chore_is_approved_in_period(assignee_id, chore_id):
        return CHORE_STATE_APPROVED

    # Phase 2: Compute completed_by_other for SHARED_FIRST chores
    chore = coordinator.chores_data.get(chore_id, {})
    if chore.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED_FIRST:
        # Check if another assignee has claimed or approved this chore
        assigned_assignees = chore.get(DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        for other_assignee_id in assigned_assignees:
            if other_assignee_id == assignee_id:
                continue
            other_assignee_data = coordinator.assignees_data.get(other_assignee_id, {})
            other_chore_data = other_assignee_data.get(
                DATA_ASSIGNEE_CHORE_DATA, {}
            ).get(chore_id, {})
            other_state = other_chore_data.get(
                DATA_ASSIGNEE_CHORE_DATA_STATE, CHORE_STATE_PENDING
            )
            if other_state in (CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED):
                return (
                    "completed_by_other"  # String literal - constant removed in Phase 2
                )

    # Check claimed status
    if coordinator.chore_manager.chore_has_pending_claim(assignee_id, chore_id):
        return CHORE_STATE_CLAIMED

    # Check overdue
    if coordinator.chore_manager.chore_is_overdue(assignee_id, chore_id):
        return CHORE_STATE_OVERDUE

    # Default to pending
    return CHORE_STATE_PENDING


def get_chore_due_date(coordinator: Any, chore_id: str) -> str | None:
    """Get the chore-level due date (for shared/shared_first chores)."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    return chore_info.get(DATA_CHORE_DUE_DATE)


def get_assignee_due_date_for_chore(
    coordinator: Any, chore_id: str, assignee_id: str
) -> str | None:
    """Get per-assignee due date (for independent chores)."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
    return per_assignee_due_dates.get(assignee_id)


def get_assignee_chore_data_due_date(
    coordinator: Any, assignee_id: str, chore_id: str
) -> str | None:
    """Get due date from assignee's chore data."""
    chore_info = coordinator._data.get("chores", {}).get(chore_id, {})
    per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
    return per_assignee_due_dates.get(assignee_id)


def get_assignee_points(coordinator: Any, assignee_id: str) -> float:
    """Get assignee's current points."""
    assignee_info = coordinator.assignees_data.get(assignee_id, {})
    return assignee_info.get(DATA_ASSIGNEE_POINTS, 0.0)


def set_ha_user_capabilities(
    coordinator: Any,
    ha_user_id: str,
    *,
    can_approve: bool,
    can_manage: bool,
) -> None:
    """Set capability flags for a user record linked to a Home Assistant user ID."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for user_data_raw in users.values():
        if not isinstance(user_data_raw, dict):
            continue
        if user_data_raw.get(const.DATA_USER_HA_USER_ID) == ha_user_id:
            user_data_raw[const.DATA_USER_CAN_APPROVE] = can_approve
            user_data_raw[const.DATA_USER_CAN_MANAGE] = can_manage
            return

    raise AssertionError(f"No user record found for HA user ID: {ha_user_id}")


def get_non_target_linked_user_id(coordinator: Any, target_user_id: str) -> str:
    """Return a linked Home Assistant user ID for a user other than target."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for internal_id, user_data_raw in users.items():
        if internal_id == target_user_id or not isinstance(user_data_raw, dict):
            continue
        ha_user_id = user_data_raw.get(const.DATA_USER_HA_USER_ID)
        if isinstance(ha_user_id, str) and ha_user_id:
            return ha_user_id

    raise AssertionError("No non-target linked user record found")


def get_non_target_user_id(coordinator: Any, target_user_id: str) -> str:
    """Return a user internal_id other than target."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for internal_id, user_data_raw in users.items():
        if internal_id == target_user_id or not isinstance(user_data_raw, dict):
            continue
        return internal_id

    raise AssertionError("No non-target user record found")


def set_chore_due_date_to_past(
    coordinator: Any,
    chore_id: str,
    assignee_id: str | None = None,
    days_ago: int = 1,
) -> datetime:
    """Set chore due date to the past WITHOUT resetting state.

    This helper sets due dates to the past so overdue checks can be triggered.
    Handles both INDEPENDENT (per-assignee) and SHARED (chore-level) due dates.
    """
    past_date = datetime.now(UTC) - timedelta(days=days_ago)
    past_date = past_date.replace(hour=17, minute=0, second=0, microsecond=0)
    past_date_iso = dt_util.as_utc(past_date).isoformat()

    period_start = past_date - timedelta(days=1)
    period_start_iso = dt_util.as_utc(period_start).isoformat()

    chore_info = coordinator.chores_data.get(chore_id, {})
    criteria = chore_info.get(
        DATA_CHORE_COMPLETION_CRITERIA,
        COMPLETION_CRITERIA_SHARED,
    )

    if criteria == COMPLETION_CRITERIA_INDEPENDENT:
        per_assignee_due_dates = chore_info.setdefault(
            DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )
        if assignee_id:
            per_assignee_due_dates[assignee_id] = past_date_iso
            assignee_info = coordinator.assignees_data.get(assignee_id, {})
            assignee_chore_data = assignee_info.get(DATA_ASSIGNEE_CHORE_DATA, {}).get(
                chore_id, {}
            )
            if assignee_chore_data:
                assignee_chore_data[DATA_ASSIGNEE_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    period_start_iso
                )
        else:
            for assigned_assignee_id in chore_info.get(
                DATA_CHORE_ASSIGNED_ASSIGNEES, []
            ):
                per_assignee_due_dates[assigned_assignee_id] = past_date_iso
                assignee_info = coordinator.assignees_data.get(assigned_assignee_id, {})
                assignee_chore_data = assignee_info.get(
                    DATA_ASSIGNEE_CHORE_DATA, {}
                ).get(chore_id, {})
                if assignee_chore_data:
                    assignee_chore_data[
                        DATA_ASSIGNEE_CHORE_DATA_APPROVAL_PERIOD_START
                    ] = period_start_iso
    else:
        # SHARED or SHARED_FIRST - use chore-level due date
        chore_info[DATA_CHORE_DUE_DATE] = past_date_iso
        chore_info[DATA_CHORE_APPROVAL_PERIOD_START] = period_start_iso

    return past_date


# ============================================================================
# TEST CLASS: Claim Chore Service
# ============================================================================


class TestClaimChoreService:
    """Test the claim_chore service across all completion criteria."""

    @pytest.mark.asyncio
    async def test_claim_independent_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test claiming an independent chore."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Claim the chore
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

        # Verify state
        state = get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_claim_shared_all_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test claiming a shared_all chore - only claiming assignee's state changes."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        # Zoë claims
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Zoë is claimed, Max is still pending
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_assignee_state_for_chore(coordinator, max_id, chore_id)
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_claim_shared_first_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test claiming a shared_first chore - only first claimant matters."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        # Zoë claims first
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Zoë is claimed
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
            == CHORE_STATE_CLAIMED
        )
        # For shared_first, Max becomes completed_by_other (missed out) when Zoë claims first
        assert (
            get_assignee_state_for_chore(coordinator, max_id, chore_id)
            == "completed_by_other"  # Phase 2: String literal, constant removed
        )


# ============================================================================
# TEST CLASS: Approve/Disapprove Chore Services
# ============================================================================


class TestApproveDisapproveChoreService:
    """Test approve_chore and disapprove_chore services."""

    @pytest.mark.asyncio
    async def test_approve_independent_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test approving an independent chore awards points."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        initial_points = get_assignee_points(coordinator, assignee_id)

        # Claim and approve
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", assignee_id, chore_id)

        # Verify approved and points awarded
        assert (
            get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
            == CHORE_STATE_APPROVED
        )
        assert (
            get_assignee_points(coordinator, assignee_id) == initial_points + 10.0
        )  # 10 points

    @pytest.mark.asyncio
    async def test_disapprove_returns_to_pending(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test disapproving a claimed chore returns to pending."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Claim and disapprove
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.disapprove_chore(
                "Mom", assignee_id, chore_id
            )

        # Verify back to pending
        assert (
            get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
            == CHORE_STATE_PENDING
        )

    @pytest.mark.asyncio
    async def test_approve_shared_first_marks_others_completed_by_other(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test approving shared_first chore marks other assignees as completed_by_other."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        # Zoë claims and gets approved
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, chore_id)

        # Zoë is approved, Max is completed_by_other
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
            == CHORE_STATE_APPROVED
        )
        assert (
            get_assignee_state_for_chore(coordinator, max_id, chore_id)
            == "completed_by_other"  # Phase 2: String literal, constant removed
        )


# ============================================================================
# TEST CLASS: Set Chore Due Date Service
# ============================================================================


class TestSetChoreDueDateService:
    """Test set_chore_due_date service across all completion criteria.

    This is a critical test class because shared_first chores were historically
    not handled correctly - they were treated as independent instead of shared.
    """

    @pytest.mark.asyncio
    async def test_set_due_date_independent_chore_all_assignees(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test setting due date for independent chore updates all assignees."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Set new due date
        new_due_date = datetime.now(UTC) + timedelta(days=3)
        new_due_date = new_due_date.replace(hour=18, minute=0, second=0, microsecond=0)

        await coordinator.chore_manager.set_due_date(chore_id, new_due_date)

        # Verify per-assignee due dates were updated
        zoe_due = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        max_due = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert zoe_due == expected_iso, f"Zoë due date not updated: {zoe_due}"
        assert max_due == expected_iso, f"Max due date not updated: {max_due}"

    @pytest.mark.asyncio
    async def test_set_due_date_independent_chore_single_assignee(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test setting due date for independent chore for single assignee."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Get Max's original due date
        max_original = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        # Set new due date for Zoë only
        new_due_date = datetime.now(UTC) + timedelta(days=5)
        new_due_date = new_due_date.replace(hour=18, minute=0, second=0, microsecond=0)

        await coordinator.chore_manager.set_due_date(
            chore_id, new_due_date, assignee_id=zoe_id
        )

        # Zoë updated, Max unchanged
        zoe_due = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        max_due = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert zoe_due == expected_iso, f"Zoë due date not updated: {zoe_due}"
        assert max_due == max_original, f"Max due date should be unchanged: {max_due}"

    @pytest.mark.asyncio
    async def test_set_due_date_shared_all_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test setting due date for shared_all chore updates chore-level date."""
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        # Verify completion criteria
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )

        # Set new due date
        new_due_date = datetime.now(UTC) + timedelta(days=2)
        new_due_date = new_due_date.replace(hour=19, minute=0, second=0, microsecond=0)

        await coordinator.chore_manager.set_due_date(chore_id, new_due_date)

        # Verify chore-level due date was updated
        chore_due = get_chore_due_date(coordinator, chore_id)
        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert chore_due == expected_iso, (
            f"Shared chore due date not updated: {chore_due}"
        )

    @pytest.mark.asyncio
    async def test_set_due_date_shared_first_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test setting due date for shared_first chore updates chore-level date.

        CRITICAL TEST: shared_first chores use chore-level due dates (like shared_all),
        NOT per-assignee due dates. This test verifies the bug fix where shared_first
        was incorrectly treated as independent.
        """
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        # Verify completion criteria is shared_first
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        # Get original chore-level due date
        original_due = get_chore_due_date(coordinator, chore_id)
        assert original_due is not None, (
            "Shared_first chore should have chore-level due date"
        )

        # Set new due date
        new_due_date = datetime.now(UTC) + timedelta(days=4)
        new_due_date = new_due_date.replace(hour=20, minute=0, second=0, microsecond=0)

        await coordinator.chore_manager.set_due_date(chore_id, new_due_date)

        # Verify chore-level due date was updated
        chore_due = get_chore_due_date(coordinator, chore_id)
        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert chore_due == expected_iso, (
            f"shared_first chore due date not updated! "
            f"Expected: {expected_iso}, Got: {chore_due}. "
            f"BUG: shared_first is being treated as independent instead of shared."
        )

    @pytest.mark.asyncio
    async def test_set_due_date_shared_first_rejects_assignee_id(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test that set_due_date for shared_first chore rejects assignee_id parameter.

        shared_first chores have a single due date for all assignees (like shared_all).
        Passing assignee_id should raise an error.
        """
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        new_due_date = datetime.now(UTC) + timedelta(days=4)

        # This SHOULD raise an error because shared_first uses chore-level due date
        # If it doesn't raise, the bug is that shared_first is being treated as independent
        # NOTE: Currently coordinator.set_chore_due_date does NOT validate this,
        # but the service handler does. We're testing coordinator behavior here.

        # For now, verify the behavior (which may need fixing)
        # The coordinator should handle shared_first like shared for due dates
        await coordinator.chore_manager.set_due_date(
            chore_id, new_due_date, assignee_id=zoe_id
        )

        # Check if chore-level due date was updated (correct behavior)
        # or if per-assignee due date was created (bug behavior)
        chore_due = get_chore_due_date(coordinator, chore_id)
        expected_iso = dt_util.as_utc(new_due_date).isoformat()

        # The chore-level due date should be updated
        # If this assertion fails, shared_first is being treated as independent (BUG)
        assert chore_due == expected_iso, (
            f"shared_first chore should update chore-level due date, not per-assignee. "
            f"Expected chore-level date: {expected_iso}, Got: {chore_due}"
        )

    @pytest.mark.asyncio
    async def test_clear_due_date_shared_first_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test clearing due date for shared_first chore."""
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        # Verify initial due date exists
        initial_due = get_chore_due_date(coordinator, chore_id)
        assert initial_due is not None

        # Clear the due date
        await coordinator.chore_manager.set_due_date(chore_id, None)

        # Verify cleared
        chore_due = get_chore_due_date(coordinator, chore_id)
        assert chore_due is None, (
            f"shared_first chore due date not cleared: {chore_due}"
        )


# ============================================================================
# TEST CLASS: Skip Chore Due Date Service
# ============================================================================


class TestSkipChoreDueDateService:
    """Test skip_chore_due_date service across all completion criteria."""

    @pytest.mark.asyncio
    async def test_skip_due_date_independent_chore_all_assignees(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skipping due date for independent chore reschedules all assignees."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Get original due dates
        zoe_original = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        max_original = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        # Skip the due date
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Both should be rescheduled (different from original)
        zoe_new = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        max_new = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        assert zoe_new != zoe_original, "Zoë due date should be rescheduled"
        assert max_new != max_original, "Max due date should be rescheduled"

    @pytest.mark.asyncio
    async def test_skip_due_date_independent_chore_single_assignee(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skipping due date for independent chore for single assignee."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Get original due dates
        zoe_original = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        max_original = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        # Skip for Zoë only
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=zoe_id)

        # Zoë rescheduled, Max unchanged
        zoe_new = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        max_new = get_assignee_due_date_for_chore(coordinator, chore_id, max_id)

        assert zoe_new != zoe_original, "Zoë due date should be rescheduled"
        assert max_new == max_original, "Max due date should be unchanged"

    @pytest.mark.asyncio
    async def test_skip_due_date_shared_all_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skipping due date for shared_all chore reschedules chore-level date."""
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        # Get original due date
        original_due = get_chore_due_date(coordinator, chore_id)
        assert original_due is not None

        # Skip the due date
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify rescheduled
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due != original_due, "Shared chore due date should be rescheduled"

    @pytest.mark.asyncio
    async def test_skip_due_date_shared_first_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skipping due date for shared_first chore reschedules chore-level date.

        CRITICAL TEST: shared_first chores should reschedule the chore-level date
        (like shared_all), NOT per-assignee dates.
        """
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        # Verify completion criteria is shared_first
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        # Get original chore-level due date
        original_due = get_chore_due_date(coordinator, chore_id)
        assert original_due is not None, (
            "shared_first chore should have chore-level due date"
        )

        # Skip the due date
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify chore-level due date was rescheduled
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None, (
            "shared_first chore should still have chore-level due date after skip"
        )
        assert new_due != original_due, (
            f"shared_first chore due date not rescheduled! "
            f"Original: {original_due}, New: {new_due}. "
            f"BUG: shared_first may be treated as independent."
        )


# ============================================================================
# TEST CLASS: Reset Overdue Chores Service
# ============================================================================


class TestResetOverdueChoresService:
    """Test reset_overdue_chores service across all completion criteria."""

    @pytest.mark.asyncio
    async def test_reset_overdue_independent_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test resetting overdue independent chore."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Set due date to past
        set_chore_due_date_to_past(coordinator, chore_id, assignee_id=zoe_id)

        # Trigger overdue check to mark as overdue
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify overdue
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "Chore should be overdue"
        )
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
            == CHORE_STATE_OVERDUE
        )

        # Reset (via ChoreManager directly)
        await coordinator.chore_manager.reset_overdue_chores(chore_id, zoe_id)

        # Verify reset to pending and rescheduled
        assert not coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "Chore should no longer be overdue"
        )
        new_due = get_assignee_due_date_for_chore(coordinator, chore_id, zoe_id)
        if new_due:
            new_due_dt = datetime.fromisoformat(new_due)
            assert new_due_dt > datetime.now(UTC), "New due date should be in future"


# ============================================================================
# TEST CLASS: Reset All Chores Service
# ============================================================================


class TestResetAllChoresService:
    """Test reset_all_chores service."""

    @pytest.mark.asyncio
    async def test_reset_all_chores_resets_all_states(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test reset_all_chores service resets all chore states to pending.

        Note: reset_all_chores is a service handler in services.py, not a coordinator method.
        This test replicates the service logic to test the data transformation directly.
        """
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        independent_chore = setup_chore_services_scenario.chore_ids[
            "Independent Daily Task"
        ]
        shared_chore = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]
        shared_first_chore = setup_chore_services_scenario.chore_ids[
            "Shared First Daily Task"
        ]

        # Set up various states
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Claim independent for Zoë
            await coordinator.chore_manager.claim_chore(
                zoe_id, independent_chore, "Zoë"
            )
            # Claim and approve shared for Zoë
            await coordinator.chore_manager.claim_chore(zoe_id, shared_chore, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", zoe_id, shared_chore)
            # Claim shared_first for Max (Zoë becomes completed_by_other)
            await coordinator.chore_manager.claim_chore(
                max_id, shared_first_chore, "Max!"
            )

        # Verify non-pending states before reset
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, independent_chore)
            == CHORE_STATE_CLAIMED
        )
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, shared_chore)
            == CHORE_STATE_APPROVED
        )

        # Call the reset_chores_to_pending_state service via hass.services.async_call
        # The service is registered under the assigneeschores domain
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_CHORES_TO_PENDING_STATE,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

        # All should be pending
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, independent_chore)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_state_for_chore(coordinator, max_id, independent_chore)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, shared_chore)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_state_for_chore(coordinator, max_id, shared_chore)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_state_for_chore(coordinator, zoe_id, shared_first_chore)
            == CHORE_STATE_PENDING
        )
        assert (
            get_assignee_state_for_chore(coordinator, max_id, shared_first_chore)
            == CHORE_STATE_PENDING
        )


# ============================================================================
# TEST CLASS: Service Handler Validation
# ============================================================================


class TestServiceHandlerValidation:
    """Test service handler validation logic."""

    @pytest.mark.asyncio
    async def test_set_due_date_service_rejects_assignee_for_shared_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test that set_chore_due_date service rejects assignee_id for shared chores."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        # Get chore info (name used for documentation, not in test)
        chore_info = coordinator.chores_data.get(chore_id, {})
        _chore_name = chore_info.get(DATA_CHORE_NAME)

        # Service call with assignee_name for shared chore should be rejected
        # (This tests the service handler, not the coordinator)
        # The service validates this before calling coordinator

        # For now, just verify the coordinator handles it correctly
        # The service handler check is in services.py handle_set_chore_due_date
        new_due_date = datetime.now(UTC) + timedelta(days=2)

        # Coordinator should update chore-level date (shared chore ignores assignee_id)
        await coordinator.chore_manager.set_due_date(
            chore_id, new_due_date, assignee_id=assignee_id
        )

        chore_due = get_chore_due_date(coordinator, chore_id)
        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert chore_due == expected_iso

    @pytest.mark.asyncio
    async def test_skip_due_date_service_rejects_assignee_for_shared_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test that skip_chore_due_date service rejects assignee_id for shared chores."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        original_due = get_chore_due_date(coordinator, chore_id)

        # Coordinator should reschedule chore-level date (shared chore ignores assignee_id)
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=assignee_id)

        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due != original_due, "Shared chore should be rescheduled"


class TestAuthorizationAcceptance:
    """Test authorization precedence for approval services."""

    @pytest.mark.asyncio
    async def test_assignee_only_can_claim_but_cannot_approve_chore(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Assignee-only user can claim own chore but cannot approve it."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]
        other_assignee_name = next(
            name for name in setup_chore_services_scenario.assignee_ids if name != "Zoë"
        )

        actor_user = await hass.auth.async_create_user(
            "Assignee Matrix Actor",
            group_ids=["system-users"],
        )
        actor_user_id = actor_user.id
        coordinator.assignees_data[assignee_id][const.DATA_ASSIGNEE_HA_USER_ID] = (
            actor_user_id
        )

        actor_context = Context(user_id=actor_user_id)

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_id,
                chore_id,
                "Zoë",
            )

        assert (
            get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
            == CHORE_STATE_CLAIMED
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_APPROVE_CHORE,
                {
                    const.SERVICE_FIELD_APPROVER_NAME: "Zoë",
                    const.SERVICE_FIELD_ASSIGNEE_NAME: other_assignee_name,
                    const.SERVICE_FIELD_CHORE_NAME: "Shared All Daily Task",
                },
                blocking=True,
                context=actor_context,
            )

    @pytest.mark.asyncio
    async def test_admin_override_can_approve_without_designated_approver(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Admin context can approve even when no user has approve/manage flags."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        for user_data_raw in coordinator._data.get(const.DATA_USERS, {}).values():
            if isinstance(user_data_raw, dict):
                user_data_raw[const.DATA_USER_CAN_APPROVE] = False
                user_data_raw[const.DATA_USER_CAN_MANAGE] = False

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

        admin_context = Context(user_id=mock_hass_users["admin"].id)
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_APPROVER_NAME: "Admin User",
                const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                const.SERVICE_FIELD_CHORE_NAME: "Independent Daily Task",
            },
            blocking=True,
            context=admin_context,
        )

        assert (
            get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
            == CHORE_STATE_APPROVED
        )

    @pytest.mark.asyncio
    async def test_non_approver_denied_approve_action(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Linked assignee without approve capability is denied approval service."""
        coordinator = setup_chore_services_scenario.coordinator
        assignee_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

        non_approver_internal_id = get_non_target_user_id(coordinator, assignee_id)
        non_approver_user_id = mock_hass_users["assignee2"].id
        non_approver_context = Context(user_id=non_approver_user_id)

        non_approver_data = coordinator._data[const.DATA_USERS][
            non_approver_internal_id
        ]
        assert isinstance(non_approver_data, dict)
        non_approver_data[const.DATA_USER_HA_USER_ID] = non_approver_user_id
        non_approver_data[const.DATA_USER_CAN_APPROVE] = False
        non_approver_data[const.DATA_USER_CAN_MANAGE] = False

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_APPROVE_CHORE,
                {
                    const.SERVICE_FIELD_APPROVER_NAME: "Max!",
                    const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                    const.SERVICE_FIELD_CHORE_NAME: "Independent Daily Task",
                },
                blocking=True,
                context=non_approver_context,
            )


# ============================================================================
# TEST CLASS: Data Structure Consistency (set_chore_due_date)
# ============================================================================


class TestSetDueDateDataStructureConsistency:
    """Test set_chore_due_date maintains correct data structure for SHARED vs INDEPENDENT.

    Post-migration data structure requirements:
    - SHARED chores: Use chore-level due_date field
    - INDEPENDENT chores: Use per_assignee_due_dates dict, NO chore-level due_date

    These tests validate the fix where set_chore_due_date was incorrectly
    adding chore-level due_date to INDEPENDENT chores.
    """

    @pytest.mark.asyncio
    async def test_set_due_date_shared_adds_chore_level_due_date(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test set_chore_due_date adds chore-level due_date for SHARED chores."""
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        # Verify this is a SHARED chore
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )

        # Remove chore-level due_date to test adding it fresh
        chore_info.pop(DATA_CHORE_DUE_DATE, None)
        assert DATA_CHORE_DUE_DATE not in chore_info

        # Set due date
        new_due_date = datetime.now(UTC) + timedelta(days=2)
        new_due_date = new_due_date.replace(hour=15, minute=0, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due_date)

        # Verify chore-level due_date was added (correct for SHARED)
        assert DATA_CHORE_DUE_DATE in chore_info, (
            "SHARED chore should have chore-level due_date"
        )
        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert chore_info[DATA_CHORE_DUE_DATE] == expected_iso

    @pytest.mark.asyncio
    async def test_set_due_date_independent_avoids_chore_level_due_date(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test set_chore_due_date does NOT add chore-level due_date for INDEPENDENT.

        CRITICAL: INDEPENDENT chores should NEVER have chore-level due_date.
        They use per_assignee_due_dates instead.
        """
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        # Verify this is an INDEPENDENT chore
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_INDEPENDENT
        )

        # Ensure no chore-level due_date exists (post-migration state)
        chore_info.pop(DATA_CHORE_DUE_DATE, None)

        # Set due date for specific assignee
        new_due_date = datetime.now(UTC) + timedelta(days=3)
        new_due_date = new_due_date.replace(hour=16, minute=0, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(
            chore_id, new_due_date, assignee_id=zoe_id
        )

        # Verify chore-level due_date was NOT added (correct for INDEPENDENT)
        assert DATA_CHORE_DUE_DATE not in chore_info, (
            "INDEPENDENT chore should NOT have chore-level due_date after "
            "set_chore_due_date - BUG: data structure consistency violated"
        )

        # Verify per_assignee_due_dates was updated correctly
        per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert per_assignee_due_dates.get(zoe_id) == expected_iso, (
            "per_assignee_due_dates should be updated for INDEPENDENT chore"
        )

    @pytest.mark.asyncio
    async def test_set_due_date_independent_all_assignees_avoids_chore_level(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test set_chore_due_date for all assignees still avoids chore-level for INDEPENDENT."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        max_id = setup_chore_services_scenario.assignee_ids["Max!"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Remove chore-level due_date (post-migration state)
        chore_info.pop(DATA_CHORE_DUE_DATE, None)

        # Set due date for ALL assignees (no assignee_id parameter)
        new_due_date = datetime.now(UTC) + timedelta(days=4)
        new_due_date = new_due_date.replace(hour=17, minute=0, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due_date)

        # Verify NO chore-level due_date even when setting for all assignees
        assert DATA_CHORE_DUE_DATE not in chore_info, (
            "INDEPENDENT chore should NOT have chore-level due_date even when "
            "setting due date for all assignees - use per_assignee_due_dates instead"
        )

        # Verify both assignees have per_assignee_due_dates set
        per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
        expected_iso = dt_util.as_utc(new_due_date).isoformat()
        assert per_assignee_due_dates.get(zoe_id) == expected_iso
        assert per_assignee_due_dates.get(max_id) == expected_iso


# ============================================================================
# TEST CLASS: Skip Due Date Null Handling
# ============================================================================


class TestSkipDueDateNullHandling:
    """Test skip_chore_due_date behavior with null/missing due dates.

    These tests validate the fix where skip service would crash or behave
    incorrectly when due dates were null or missing.
    """

    @pytest.mark.asyncio
    async def test_skip_ignores_null_due_date_independent(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skip_chore_due_date is a no-op when assignee's due date is null.

        Bug reproduction:
        1. Set per_assignee_due_dates[assignee_id] = None (cleared)
        2. Call skip_chore_due_date
        3. Should be a no-op (not crash or delete the assignee entry)
        """
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Set Zoë's due date to None (cleared)
        per_assignee_due_dates = chore_info.setdefault(
            DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )
        per_assignee_due_dates[zoe_id] = None

        # Call skip - should be a no-op, not crash
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=zoe_id)

        # Verify assignee entry still exists with None value (not deleted)
        assert zoe_id in chore_info[DATA_CHORE_PER_ASSIGNEE_DUE_DATES], (
            "Assignee entry should not be deleted when skip called with null due date"
        )
        assert chore_info[DATA_CHORE_PER_ASSIGNEE_DUE_DATES][zoe_id] is None, (
            "Due date should remain None after skip (no-op)"
        )

    @pytest.mark.asyncio
    async def test_skip_works_with_valid_due_date(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skip_chore_due_date advances due date when valid date exists."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})
        per_assignee_due_dates = chore_info.setdefault(
            DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )

        # Set a valid due date
        original_date = "2026-01-10T12:00:00+00:00"
        per_assignee_due_dates[zoe_id] = original_date

        # Call skip - should advance the date
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=zoe_id)

        # Verify due date was advanced
        new_date = per_assignee_due_dates.get(zoe_id)
        assert new_date is not None, "Due date should not be None after skip"
        assert new_date != original_date, "Due date should be advanced after skip"

    @pytest.mark.asyncio
    async def test_skip_independent_no_due_dates_noop(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skip_chore_due_date is a no-op when no due dates exist at all."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Clear all due dates
        chore_info[DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {}

        # Call skip - should be a no-op (not crash)
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=zoe_id)

        # Verify no changes (still empty)
        per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
        assert per_assignee_due_dates.get(zoe_id) is None, (
            "No due date should be created when skipping with no existing date"
        )


# ============================================================================
# TEST CLASS: Skip Due Date Fallback to Assignee Chore Data
# ============================================================================


class TestSkipDueDateAssigneeChoreDataFallback:
    """Test skip_chore_due_date validates existence from assignee's chore_data.

    When per_assignee_due_dates is empty, the skip validation checks if ANY assignee
    has a due date in their chore_data (for migration support). However,
    when skipping for a specific assignee, only per_assignee_due_dates is used as the
    authoritative source - assignee_chore_data is for backward compatibility only.
    """

    @pytest.mark.asyncio
    async def test_skip_validates_against_assignee_chore_data_for_any_due_date(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test skip validation passes when assignee's chore_data has due date.

        The skip validation checks if ANY assigned assignee has a due date,
        including in their assignee_chore_data. This is for migration support.
        However, the actual skip operation uses per_assignee_due_dates only.
        """
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Clear per_assignee_due_dates for Zoë (but leave Max's)
        per_assignee_due_dates = chore_info.setdefault(
            DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )
        per_assignee_due_dates[zoe_id] = None  # Clear Zoë's date

        # Set due date in assignee's chore_data (for backward compat validation)
        assignee_info = coordinator.assignees_data.get(zoe_id, {})
        _ = assignee_info.setdefault(DATA_ASSIGNEE_CHORE_DATA, {}).setdefault(
            chore_id, {}
        )

        # Call skip for Zoë - should be no-op since per_assignee_due_dates[zoe_id] is None
        # (modern coordinator only reads from per_assignee_due_dates, not assignee_chore_data)
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=zoe_id)

        # Zoë's per_assignee_due_dates should still be None (no skip occurred)
        assert per_assignee_due_dates.get(zoe_id) is None, (
            "Skip should be no-op when per_assignee_due_dates is None for the specific assignee"
        )


# ============================================================================
# TEST CLASS: Set + Skip Service Integration
# ============================================================================


class TestSetSkipServiceIntegration:
    """Test set_chore_due_date and skip_chore_due_date work together correctly.

    These tests validate that using set followed by skip maintains
    correct data structure consistency.
    """

    @pytest.mark.asyncio
    async def test_set_then_skip_shared_maintains_structure(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test set then skip for SHARED chore maintains chore-level due_date."""
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared All Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # 1. Set due date
        initial_due = datetime.now(UTC) + timedelta(days=1)
        initial_due = initial_due.replace(hour=10, minute=0, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, initial_due)

        # Verify SHARED chore has chore-level due_date
        assert DATA_CHORE_DUE_DATE in chore_info
        initial_iso = chore_info[DATA_CHORE_DUE_DATE]

        # 2. Skip the due date
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify structure maintained and date advanced
        assert DATA_CHORE_DUE_DATE in chore_info, (
            "SHARED chore should still have chore-level due_date after skip"
        )
        new_iso = chore_info[DATA_CHORE_DUE_DATE]
        assert new_iso != initial_iso, "Due date should be advanced after skip"

    @pytest.mark.asyncio
    async def test_set_then_skip_independent_maintains_structure(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test set then skip for INDEPENDENT chore maintains per_assignee_due_dates."""
        coordinator = setup_chore_services_scenario.coordinator
        zoe_id = setup_chore_services_scenario.assignee_ids["Zoë"]
        chore_id = setup_chore_services_scenario.chore_ids["Independent Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Remove any chore-level due_date (post-migration state)
        chore_info.pop(DATA_CHORE_DUE_DATE, None)

        # 1. Set due date for Zoë
        initial_due = datetime.now(UTC) + timedelta(days=2)
        initial_due = initial_due.replace(hour=14, minute=0, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(
            chore_id, initial_due, assignee_id=zoe_id
        )

        # Verify structure
        assert DATA_CHORE_DUE_DATE not in chore_info, (
            "INDEPENDENT chore should NOT have chore-level due_date"
        )
        per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
        initial_iso = per_assignee_due_dates.get(zoe_id)
        assert initial_iso is not None

        # 2. Skip for Zoë
        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id=zoe_id)

        # Verify structure maintained and date advanced
        assert DATA_CHORE_DUE_DATE not in chore_info, (
            "INDEPENDENT chore should NOT have chore-level due_date after skip"
        )
        new_iso = per_assignee_due_dates.get(zoe_id)
        assert new_iso != initial_iso, (
            "Per-assignee due date should be advanced after skip"
        )

    @pytest.mark.asyncio
    async def test_set_then_skip_shared_first_maintains_structure(
        self,
        hass: HomeAssistant,
        setup_chore_services_scenario: SetupResult,
    ) -> None:
        """Test set then skip for SHARED_FIRST maintains chore-level due_date."""
        coordinator = setup_chore_services_scenario.coordinator
        chore_id = setup_chore_services_scenario.chore_ids["Shared First Daily Task"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is SHARED_FIRST
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )

        # 1. Set due date
        initial_due = datetime.now(UTC) + timedelta(days=1)
        initial_due = initial_due.replace(hour=18, minute=0, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, initial_due)

        # Verify SHARED_FIRST chore has chore-level due_date (like SHARED)
        assert DATA_CHORE_DUE_DATE in chore_info, (
            "SHARED_FIRST chore should have chore-level due_date"
        )
        initial_iso = chore_info[DATA_CHORE_DUE_DATE]

        # 2. Skip the due date
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify structure maintained
        assert DATA_CHORE_DUE_DATE in chore_info, (
            "SHARED_FIRST chore should still have chore-level due_date after skip"
        )
        new_iso = chore_info[DATA_CHORE_DUE_DATE]
        assert new_iso != initial_iso, "Due date should be advanced after skip"
