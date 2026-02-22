"""Test the new immediate_on_late overdue handling option.

This module tests the behavior when:
- overdue_handling_type = AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE

This option triggers immediate reset (like UPON_COMPLETION) when a chore is
approved AFTER the reset boundary has passed (late approval).

Key scenarios:
1. Late approval → Immediate reset to PENDING with new due date
2. On-time approval → Normal scheduled reset behavior
3. Works with all approval_reset_type values
4. INDEPENDENT: Each assignee resets independently
5. SHARED: Resets when all assignees approve

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.util import dt as dt_util
import pytest

from tests.helpers import (
    APPROVAL_RESET_AT_DUE_DATE_MULTI,
    APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    APPROVAL_RESET_UPON_COMPLETION,
    # Chore states
    CHORE_STATE_APPROVED,
    CHORE_STATE_PENDING,
    # Constants for chore data access
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    DATA_ASSIGNEE_CHORE_DATA,
    DATA_ASSIGNEE_CHORE_DATA_APPROVAL_PERIOD_START,
    # Assignee chore data
    DATA_ASSIGNEE_CHORE_DATA_STATE,
    DATA_CHORE_APPROVAL_PERIOD_START,
    # Approval reset types
    DATA_CHORE_APPROVAL_RESET_TYPE,
    DATA_CHORE_ASSIGNED_ASSIGNEES,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_DUE_DATE,
    # Overdue handling
    DATA_CHORE_OVERDUE_HANDLING_TYPE,
    DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
    OVERDUE_HANDLING_AT_DUE_DATE,
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_assignee_state_for_chore(
    coordinator: Any, assignee_id: str, chore_id: str
) -> str:
    """Get the current chore state for a specific assignee."""
    assignee_chore_data = coordinator.chore_manager.get_chore_data_for_assignee(
        assignee_id, chore_id
    )
    return assignee_chore_data.get(DATA_ASSIGNEE_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def set_chore_due_date_directly(
    coordinator: Any,
    chore_id: str,
    due_date: datetime,
    assignee_id: str | None = None,
) -> None:
    """Set chore due date directly without triggering reschedule logic."""
    due_date_iso = dt_util.as_utc(due_date).isoformat()
    period_start = due_date - timedelta(days=1)
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
            per_assignee_due_dates[assignee_id] = due_date_iso
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
                per_assignee_due_dates[assigned_assignee_id] = due_date_iso
    else:
        chore_info[DATA_CHORE_DUE_DATE] = due_date_iso
        chore_info[DATA_CHORE_APPROVAL_PERIOD_START] = period_start_iso


def get_chore_due_date(
    coordinator: Any,
    chore_id: str,
    assignee_id: str | None = None,
) -> datetime | None:
    """Get chore due date (per-assignee for INDEPENDENT, chore-level for SHARED)."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    criteria = chore_info.get(
        DATA_CHORE_COMPLETION_CRITERIA,
        COMPLETION_CRITERIA_SHARED,
    )

    if criteria == COMPLETION_CRITERIA_INDEPENDENT and assignee_id:
        per_assignee_due_dates = chore_info.get(DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
        due_date_str = per_assignee_due_dates.get(assignee_id)
    else:
        due_date_str = chore_info.get(DATA_CHORE_DUE_DATE)

    if due_date_str:
        return datetime.fromisoformat(due_date_str)
    return None


def configure_chore_for_immediate_on_late(
    coordinator: Any,
    chore_id: str,
    approval_reset_type: str = APPROVAL_RESET_AT_MIDNIGHT_MULTI,
) -> None:
    """Configure a chore to use immediate_on_late overdue handling."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    chore_info[DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
        OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
    )
    chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = approval_reset_type


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def scenario_approval_reset(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with approval reset overdue chores (single assignee Zoë)."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_approval_reset_overdue.yaml",
    )


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with shared chores (multi-assignee: Zoë, Max!, Lila)."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


# ============================================================================
# TEST CLASS: AT_MIDNIGHT_MULTI + immediate_on_late
# ============================================================================


class TestImmediateOnLateAtMidnightMulti:
    """Test immediate_on_late with AT_MIDNIGHT_MULTI reset type.

    Key scenario: Chore due Tuesday 5PM, approved Wednesday 8AM (after midnight).
    Expected: Immediate reset instead of waiting until Thursday midnight.
    """

    @pytest.mark.asyncio
    async def test_late_approval_triggers_immediate_reset(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that late approval (after midnight boundary) triggers immediate reset.

        Scenario:
        - Due date: Yesterday 5PM
        - Current time: Today 8AM (after last midnight)
        - Approval: Should trigger immediate reset

        Expected:
        - State resets to PENDING immediately
        - Due date advances to next occurrence
        """
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore for immediate_on_late
        configure_chore_for_immediate_on_late(
            coordinator, chore_id, APPROVAL_RESET_AT_MIDNIGHT_MULTI
        )

        # Set due date to 2 days ago (definitively before local midnight = late)
        # Use 2 days ago to ensure it's before midnight in any timezone
        two_days_ago = datetime.now(UTC) - timedelta(days=2)
        two_days_ago = two_days_ago.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, two_days_ago, assignee_id=assignee_id
        )

        original_due_date = get_chore_due_date(coordinator, chore_id, assignee_id)

        # Claim and approve the chore (late approval)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_id, chore_id, "Test User"
            )
            await coordinator.chore_manager.approve_chore(
                "Approver", assignee_id, chore_id
            )

        # Verify immediate reset: state should be PENDING
        state = get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            f"Expected PENDING after late approval, got {state}"
        )

        # Verify due date advanced
        new_due_date = get_chore_due_date(coordinator, chore_id, assignee_id)
        assert new_due_date is not None, "Due date should be set after reschedule"
        assert new_due_date > original_due_date, (
            f"Due date should advance: was {original_due_date}, now {new_due_date}"
        )

    @pytest.mark.asyncio
    async def test_ontime_approval_normal_behavior(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that on-time approval (before midnight boundary) uses normal behavior.

        Scenario:
        - Due date: Today 5PM (future - not overdue yet)
        - Current time: Today 10AM
        - Approval: Should NOT trigger immediate reset

        Expected:
        - State stays APPROVED (waiting for scheduled reset)
        - Due date unchanged (reschedule happens at midnight)
        """
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore for immediate_on_late
        configure_chore_for_immediate_on_late(
            coordinator, chore_id, APPROVAL_RESET_AT_MIDNIGHT_MULTI
        )

        # Set due date to today 5PM (future - not late)
        today_5pm = datetime.now(UTC)
        today_5pm = today_5pm.replace(hour=17, minute=0, second=0, microsecond=0)
        # If current time is past 5PM, set to tomorrow
        if datetime.now(UTC).hour >= 17:
            today_5pm = today_5pm + timedelta(days=1)

        set_chore_due_date_directly(
            coordinator, chore_id, today_5pm, assignee_id=assignee_id
        )

        # Claim and approve the chore (on-time approval)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_id, chore_id, "Test User"
            )
            await coordinator.chore_manager.approve_chore(
                "Approver", assignee_id, chore_id
            )

        # Verify state is APPROVED (not reset)
        state = get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_APPROVED, (
            f"Expected APPROVED after on-time approval, got {state}"
        )


# ============================================================================
# TEST CLASS: AT_DUE_DATE_MULTI + immediate_on_late
# ============================================================================


class TestImmediateOnLateAtDueDateMulti:
    """Test immediate_on_late with AT_DUE_DATE_MULTI reset type."""

    @pytest.mark.asyncio
    async def test_late_approval_after_due_date_triggers_reset(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that approval after due date has passed triggers immediate reset.

        Scenario:
        - Due date: Yesterday 5PM
        - Current time: Today (after due date)
        - Approval: Should trigger immediate reset

        Expected:
        - State resets to PENDING
        - Due date advances
        """
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore for immediate_on_late with AT_DUE_DATE_MULTI
        configure_chore_for_immediate_on_late(
            coordinator, chore_id, APPROVAL_RESET_AT_DUE_DATE_MULTI
        )

        # Set due date to yesterday (past)
        yesterday = datetime.now(UTC) - timedelta(days=1)
        yesterday = yesterday.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, yesterday, assignee_id=assignee_id
        )

        original_due_date = get_chore_due_date(coordinator, chore_id, assignee_id)

        # Claim and approve the chore (late approval)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_id, chore_id, "Test User"
            )
            await coordinator.chore_manager.approve_chore(
                "Approver", assignee_id, chore_id
            )

        # Verify immediate reset
        state = get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            f"Expected PENDING after late approval with AT_DUE_DATE_MULTI, got {state}"
        )

        # Verify due date advanced
        new_due_date = get_chore_due_date(coordinator, chore_id, assignee_id)
        assert new_due_date is not None
        assert new_due_date > original_due_date


# ============================================================================
# TEST CLASS: INDEPENDENT Multi-Assignee
# ============================================================================


class TestImmediateOnLateIndependent:
    """Test immediate_on_late with INDEPENDENT completion criteria.

    Each assignee should reset independently when they approve late.
    """

    @pytest.mark.asyncio
    async def test_each_assignee_resets_independently(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test that each assignee resets independently on late approval.

        Scenario:
        - INDEPENDENT chore with 2 assignees
        - Both have due dates in the past
        - Assignee 1 approves late → Assignee 1 resets, Assignee 2 unchanged
        - Assignee 2 approves late → Assignee 2 resets

        Expected:
        - Each assignee's reset is independent
        """
        coordinator = scenario_shared.coordinator
        zoe_id = scenario_shared.assignee_ids["Zoë"]
        max_id = scenario_shared.assignee_ids["Max!"]
        # Use "Walk the dog" from scenario_shared.yaml (assigned to Zoë and Max!)
        chore_id = scenario_shared.chore_ids["Walk the dog"]

        # Configure chore for immediate_on_late and INDEPENDENT
        configure_chore_for_immediate_on_late(
            coordinator, chore_id, APPROVAL_RESET_AT_MIDNIGHT_MULTI
        )
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_COMPLETION_CRITERIA] = COMPLETION_CRITERIA_INDEPENDENT
        chore_info[DATA_CHORE_ASSIGNED_ASSIGNEES] = [zoe_id, max_id]

        # Set both assignees' due dates to 2 days ago (definitively late)
        # Use 2 days ago to ensure it's before midnight in any timezone
        two_days_ago = datetime.now(UTC) - timedelta(days=2)
        two_days_ago = two_days_ago.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, two_days_ago, assignee_id=zoe_id
        )
        set_chore_due_date_directly(
            coordinator, chore_id, two_days_ago, assignee_id=max_id
        )

        # Zoë claims and approves late
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
            await coordinator.chore_manager.approve_chore("Approver", zoe_id, chore_id)

        # Verify Zoë reset, Max unchanged
        zoe_state = get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
        max_state = get_assignee_state_for_chore(coordinator, max_id, chore_id)
        assert zoe_state == CHORE_STATE_PENDING, (
            f"Zoë should be PENDING after late approval, got {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"Max should still be PENDING (not yet claimed), got {max_state}"
        )

        # Max claims and approves late
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Test User")
            await coordinator.chore_manager.approve_chore("Approver", max_id, chore_id)

        # Verify Max also reset
        max_state = get_assignee_state_for_chore(coordinator, max_id, chore_id)
        assert max_state == CHORE_STATE_PENDING


# ============================================================================
# TEST CLASS: SHARED Multi-Assignee
# ============================================================================


class TestImmediateOnLateShared:
    """Test immediate_on_late with SHARED completion criteria.

    Chore should reset when all assignees have approved late.
    """

    @pytest.mark.asyncio
    async def test_shared_resets_when_all_assignees_approve(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test that SHARED chore resets when all assigned assignees approve late.

        Scenario:
        - SHARED chore with 2 assignees
        - Due date in the past
        - Assignee 1 approves → No reset yet
        - Assignee 2 approves → Reset triggered

        Expected:
        - Reset only happens after all assignees approve
        """
        coordinator = scenario_shared.coordinator
        assignee_ids = scenario_shared.assignee_ids
        zoe_id = assignee_ids["Zoë"]
        max_id = assignee_ids["Max!"]
        # Use "Walk the dog" - shared_all chore assigned to Zoë and Max!
        chore_id = scenario_shared.chore_ids["Walk the dog"]

        # Configure chore for immediate_on_late
        configure_chore_for_immediate_on_late(
            coordinator, chore_id, APPROVAL_RESET_AT_MIDNIGHT_MULTI
        )
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_COMPLETION_CRITERIA] = COMPLETION_CRITERIA_SHARED
        chore_info[DATA_CHORE_ASSIGNED_ASSIGNEES] = [zoe_id, max_id]

        # Set due date to 2 days ago (definitively late)
        # Use 2 days ago to ensure it's before midnight in any timezone
        two_days_ago = datetime.now(UTC) - timedelta(days=2)
        two_days_ago = two_days_ago.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(coordinator, chore_id, two_days_ago)

        original_due_date = get_chore_due_date(coordinator, chore_id)

        # Zoë claims and approves (first assignee)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
            await coordinator.chore_manager.approve_chore("Approver", zoe_id, chore_id)

        # Verify Zoë is approved but chore hasn't reset yet
        zoe_state = get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
        assert zoe_state == CHORE_STATE_APPROVED, (
            f"Zoë should be APPROVED (waiting for Max), got {zoe_state}"
        )

        # Due date should NOT have changed yet
        intermediate_due_date = get_chore_due_date(coordinator, chore_id)
        assert intermediate_due_date == original_due_date, (
            "Due date should not change until all assignees approve"
        )

        # Max claims and approves (second/last assignee)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(max_id, chore_id, "Test User")
            await coordinator.chore_manager.approve_chore("Approver", max_id, chore_id)

        # Now chore should have reset
        zoe_state = get_assignee_state_for_chore(coordinator, zoe_id, chore_id)
        max_state = get_assignee_state_for_chore(coordinator, max_id, chore_id)
        assert zoe_state == CHORE_STATE_PENDING, (
            f"Zoë should be PENDING after all approved, got {zoe_state}"
        )
        assert max_state == CHORE_STATE_PENDING, (
            f"Max should be PENDING after all approved, got {max_state}"
        )

        # Due date should have advanced
        new_due_date = get_chore_due_date(coordinator, chore_id)
        assert new_due_date is not None
        assert new_due_date > original_due_date


# ============================================================================
# TEST CLASS: Regression - Existing Options Unchanged
# ============================================================================


class TestRegressionExistingOptions:
    """Verify existing overdue_handling options still work correctly."""

    @pytest.mark.asyncio
    async def test_at_due_date_option_unchanged(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that at_due_date option still works (stays approved until reset)."""
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore with at_due_date (original behavior)
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_OVERDUE_HANDLING_TYPE] = OVERDUE_HANDLING_AT_DUE_DATE
        chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = APPROVAL_RESET_AT_MIDNIGHT_MULTI

        # Set due date to yesterday (late)
        yesterday = datetime.now(UTC) - timedelta(days=1)
        yesterday = yesterday.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, yesterday, assignee_id=assignee_id
        )

        # Claim and approve
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_id, chore_id, "Test User"
            )
            await coordinator.chore_manager.approve_chore(
                "Approver", assignee_id, chore_id
            )

        # Verify stays APPROVED (does NOT reset immediately)
        state = get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_APPROVED, (
            f"at_due_date should stay APPROVED, got {state}"
        )

    @pytest.mark.asyncio
    async def test_upon_completion_still_resets_immediately(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that UPON_COMPLETION reset type still resets immediately."""
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore with UPON_COMPLETION (should always reset immediately)
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_OVERDUE_HANDLING_TYPE] = OVERDUE_HANDLING_AT_DUE_DATE
        chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = APPROVAL_RESET_UPON_COMPLETION

        # Set due date to future (not late)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, tomorrow, assignee_id=assignee_id
        )

        # Claim and approve
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_id, chore_id, "Test User"
            )
            await coordinator.chore_manager.approve_chore(
                "Approver", assignee_id, chore_id
            )

        # Verify resets immediately (UPON_COMPLETION behavior)
        state = get_assignee_state_for_chore(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            f"UPON_COMPLETION should reset to PENDING, got {state}"
        )


# ============================================================================
# TEST CLASS: Helper Method Tests
# ============================================================================


class TestIsApprovalAfterResetBoundary:
    """Test the __is_chore_approval_after_reset helper method."""

    @pytest.mark.asyncio
    async def test_midnight_type_before_midnight_not_late(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that due date TODAY is not considered late (before midnight)."""
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = APPROVAL_RESET_AT_MIDNIGHT_MULTI

        # Set due date to today (not late - midnight hasn't passed since due date)
        today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, today, assignee_id=assignee_id
        )

        # Check boundary
        is_late = coordinator.chore_manager._is_chore_approval_after_reset(
            chore_info, assignee_id
        )
        assert not is_late, "Due date today should not be late"

    @pytest.mark.asyncio
    async def test_midnight_type_after_midnight_is_late(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that due date BEFORE last midnight is considered late.

        Note: The reset boundary uses LOCAL time midnight. A due date is "late"
        if it occurred before the last local midnight, regardless of UTC time.
        To ensure the due date is definitely "before midnight", we set it to
        2 days ago which is definitely before yesterday's midnight.
        """
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = APPROVAL_RESET_AT_MIDNIGHT_MULTI

        # Set due date to 2 days ago - definitely before last midnight in any timezone
        two_days_ago = datetime.now(UTC) - timedelta(days=2)
        two_days_ago = two_days_ago.replace(hour=12, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, two_days_ago, assignee_id=assignee_id
        )

        # Check boundary
        is_late = coordinator.chore_manager._is_chore_approval_after_reset(
            chore_info, assignee_id
        )
        assert is_late, "Due date 2 days ago should be late (before last midnight)"

    @pytest.mark.asyncio
    async def test_due_date_type_before_due_not_late(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that approval before due date is not late for AT_DUE_DATE types."""
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = APPROVAL_RESET_AT_DUE_DATE_MULTI

        # Set due date to tomorrow (future - not late)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, tomorrow, assignee_id=assignee_id
        )

        # Check boundary
        is_late = coordinator.chore_manager._is_chore_approval_after_reset(
            chore_info, assignee_id
        )
        assert not is_late, "Due date tomorrow should not be late"

    @pytest.mark.asyncio
    async def test_due_date_type_after_due_is_late(
        self,
        hass: HomeAssistant,
        scenario_approval_reset: SetupResult,
    ) -> None:
        """Test that approval after due date is late for AT_DUE_DATE types."""
        coordinator = scenario_approval_reset.coordinator
        assignee_id = scenario_approval_reset.assignee_ids["Zoë"]
        chore_id = scenario_approval_reset.chore_ids["AtDueDateOnce Reset Chore"]

        # Configure chore
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_info[DATA_CHORE_APPROVAL_RESET_TYPE] = APPROVAL_RESET_AT_DUE_DATE_MULTI

        # Set due date to yesterday (past - late)
        yesterday = datetime.now(UTC) - timedelta(days=1)
        yesterday = yesterday.replace(hour=17, minute=0, second=0, microsecond=0)
        set_chore_due_date_directly(
            coordinator, chore_id, yesterday, assignee_id=assignee_id
        )

        # Check boundary
        is_late = coordinator.chore_manager._is_chore_approval_after_reset(
            chore_info, assignee_id
        )
        assert is_late, "Due date yesterday should be late for AT_DUE_DATE type"
