"""Test interactions between approval_reset_type and overdue_handling_type.

This module tests the behavior when:
- approval_reset_type = AT_MIDNIGHT_ONCE (or AT_MIDNIGHT_MULTI)
- overdue_handling_type = AT_DUE_DATE_THEN_RESET

AT_DUE_DATE_THEN_RESET only works with AT_MIDNIGHT_* reset types because
the reset must occur AFTER the due date to allow the overdue window.

Question answered: What happens to chores in different states when midnight reset runs?

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.util import dt as dt_util
import pytest

from custom_components.kidschores import const
from custom_components.kidschores.const import (
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    DATA_CHORE_APPROVAL_PERIOD_START,
    DATA_CHORE_ASSIGNED_KIDS,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_PER_KID_DUE_DATES,
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START,
)
from custom_components.kidschores.utils.dt_utils import dt_now_utc
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def setup_at_due_date_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with AT_DUE_DATE_ONCE + AT_DUE_DATE_THEN_RESET chore."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_approval_reset_overdue.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS (following test_chore_scheduling.py patterns)
# ============================================================================


def get_kid_state_for_chore(coordinator: Any, kid_id: str, chore_id: str) -> str:
    """Get the current chore state for a specific kid.

    Uses the same logic as the sensor to determine state based on
    approval period timestamps, not just the cached state field.

    Phase 2: completed_by_other is now computed dynamically for SHARED_FIRST chores.
    """
    # Check approval status first (same order as sensor.py line 750)
    if coordinator.chore_manager.chore_is_approved_in_period(kid_id, chore_id):
        return const.CHORE_STATE_APPROVED

    # Phase 2: Compute completed_by_other for SHARED_FIRST chores
    chore = coordinator.chores_data.get(chore_id, {})
    if (
        chore.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        == const.COMPLETION_CRITERIA_SHARED_FIRST
    ):
        # Check if another kid has claimed or approved this chore
        assigned_kids = chore.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        for other_kid_id in assigned_kids:
            if other_kid_id == kid_id:
                continue
            other_kid_data = coordinator.kids_data.get(other_kid_id, {})
            other_chore_data = other_kid_data.get(const.DATA_KID_CHORE_DATA, {}).get(
                chore_id, {}
            )
            other_state = other_chore_data.get(
                const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
            )
            if other_state in (const.CHORE_STATE_CLAIMED, const.CHORE_STATE_APPROVED):
                return (
                    "completed_by_other"  # String literal - constant removed in Phase 2
                )

    if coordinator.chore_manager.chore_has_pending_claim(kid_id, chore_id):
        return const.CHORE_STATE_CLAIMED
    if coordinator.chore_manager.chore_is_overdue(kid_id, chore_id):
        return const.CHORE_STATE_OVERDUE
    if coordinator.chore_manager.chore_is_due(kid_id, chore_id):
        return const.CHORE_STATE_DUE
    return const.CHORE_STATE_PENDING


def get_expected_reset_display_state(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> str:
    """Compute exact expected post-reset display state.

    After a successful reset we expect the chore to be neither approved nor overdue.
    Display should then be:
    - DUE when current time is inside due window
    - otherwise PENDING
    """
    now_utc = dt_now_utc()
    due_dt = coordinator.chore_manager.get_due_date(chore_id, kid_id)
    due_window_start = coordinator.chore_manager.get_due_window_start(chore_id, kid_id)

    if (
        due_dt is not None
        and due_window_start is not None
        and due_window_start <= now_utc <= due_dt
    ):
        return const.CHORE_STATE_DUE

    return const.CHORE_STATE_PENDING


def set_chore_due_date_to_past(
    coordinator: Any,
    chore_id: str,
    kid_id: str | None = None,
    days_ago: int = 1,
    now_utc: datetime | None = None,
) -> datetime:
    """Set chore due date to the past WITHOUT resetting state.

    This is a copy of the helper from test_chore_scheduling.py.
    """
    if now_utc is None:
        now_utc = datetime.now(UTC)

    past_date = now_utc - timedelta(days=days_ago)
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
        per_kid_due_dates = chore_info.setdefault(DATA_CHORE_PER_KID_DUE_DATES, {})
        if kid_id:
            per_kid_due_dates[kid_id] = past_date_iso
            kid_info = coordinator.kids_data.get(kid_id, {})
            kid_chore_data = kid_info.get(DATA_KID_CHORE_DATA, {}).get(chore_id, {})
            if kid_chore_data:
                kid_chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    period_start_iso
                )
        else:
            for assigned_kid_id in chore_info.get(DATA_CHORE_ASSIGNED_KIDS, []):
                per_kid_due_dates[assigned_kid_id] = past_date_iso
                kid_info = coordinator.kids_data.get(assigned_kid_id, {})
                kid_chore_data = kid_info.get(DATA_KID_CHORE_DATA, {}).get(chore_id, {})
                if kid_chore_data:
                    kid_chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                        period_start_iso
                    )
    else:
        chore_info[DATA_CHORE_DUE_DATE] = past_date_iso
        chore_info[DATA_CHORE_APPROVAL_PERIOD_START] = period_start_iso

    return past_date


def set_chore_due_date_to_future(
    coordinator: Any,
    chore_id: str,
    kid_id: str | None = None,
    days_ahead: int = 1,
    now_utc: datetime | None = None,
) -> datetime:
    """Set chore due date to the future."""
    if now_utc is None:
        now_utc = datetime.now(UTC)

    future_date = now_utc + timedelta(days=days_ahead)
    future_date = future_date.replace(hour=17, minute=0, second=0, microsecond=0)
    future_date_iso = dt_util.as_utc(future_date).isoformat()

    chore_info = coordinator.chores_data.get(chore_id, {})
    criteria = chore_info.get(
        DATA_CHORE_COMPLETION_CRITERIA,
        COMPLETION_CRITERIA_SHARED,
    )

    if criteria == COMPLETION_CRITERIA_INDEPENDENT:
        per_kid_due_dates = chore_info.setdefault(DATA_CHORE_PER_KID_DUE_DATES, {})
        if kid_id:
            per_kid_due_dates[kid_id] = future_date_iso
        else:
            for assigned_kid_id in chore_info.get(DATA_CHORE_ASSIGNED_KIDS, []):
                per_kid_due_dates[assigned_kid_id] = future_date_iso
    else:
        chore_info[DATA_CHORE_DUE_DATE] = future_date_iso

    return future_date


def set_per_kid_due_dates_mixed(
    coordinator: Any,
    chore_id: str,
    kid1_id: str,
    kid2_id: str,
    kid1_days_ago: int = 1,
    kid2_days_ahead: int = 2,
    now_utc: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Set different due dates for two kids: one past, one future.

    Args:
        coordinator: KidsChoresDataCoordinator instance
        chore_id: Chore UUID to update
        kid1_id: First kid UUID (will get past due date)
        kid2_id: Second kid UUID (will get future due date)
        kid1_days_ago: Days in past for kid1's due date
        kid2_days_ahead: Days in future for kid2's due date

    Returns:
        Tuple of (past_date, future_date) as datetime objects
    """
    past_date = set_chore_due_date_to_past(
        coordinator,
        chore_id,
        kid_id=kid1_id,
        days_ago=kid1_days_ago,
        now_utc=now_utc,
    )
    future_date = set_chore_due_date_to_future(
        coordinator,
        chore_id,
        kid_id=kid2_id,
        days_ahead=kid2_days_ahead,
        now_utc=now_utc,
    )
    return past_date, future_date


# ============================================================================
# TEST CLASS: AT_DUE_DATE_ONCE + AT_DUE_DATE_THEN_RESET Interaction
# ============================================================================


class TestApprovalResetOverdueInteraction:
    """Test interactions between approval reset and overdue handling.

    Scenario: approval_reset_type=AT_MIDNIGHT_ONCE + overdue_handling_type=AT_DUE_DATE_THEN_RESET

    Expected behaviors:
    1. APPROVED state at reset → Reset to PENDING (ready for next period)
    2. PENDING (claimed) at reset → Depends on pending_claim_action, may become overdue
    3. PENDING (unclaimed) past due date → Marked OVERDUE
    4. OVERDUE state at reset → Cleared to PENDING ("then_reset" behavior)
    """

    @pytest.mark.asyncio
    async def test_approved_chore_resets_to_pending_at_due_date(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test that an approved chore resets to PENDING when due date passes.

        Scenario: Kid completed chore, it's approved. Due date passes.
        Expected: Chore resets to PENDING for next period.
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        chore_id = setup_at_due_date_scenario.chore_ids["AtDueDateOnce Reset Chore"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Approve the chore (kid claims and parent approves)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Test User")
            await coordinator.chore_manager.approve_chore("Parent", kid_id, chore_id)

        # Verify approved state
        assert coordinator.chore_manager.chore_is_approved_in_period(kid_id, chore_id)
        initial_state = get_kid_state_for_chore(coordinator, kid_id, chore_id)
        assert initial_state == const.CHORE_STATE_APPROVED

        # Set due date to the past
        set_chore_due_date_to_past(
            coordinator, chore_id, kid_id=kid_id, now_utc=fixed_now
        )

        # Trigger reset cycle (this is what happens at the scheduled reset time)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # Verify reset and exact deterministic display based on due-window timing
        final_state = get_kid_state_for_chore(coordinator, kid_id, chore_id)
        expected_display = get_expected_reset_display_state(
            coordinator, kid_id, chore_id
        )
        assert final_state == expected_display, (
            f"Expected APPROVED chore post-reset display={expected_display}, got {final_state}"
        )
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            kid_id, chore_id
        )
        assert not coordinator.chore_manager.chore_is_overdue(kid_id, chore_id)

    @pytest.mark.asyncio
    async def test_unclaimed_pending_becomes_overdue_at_due_date(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test that an unclaimed PENDING chore becomes OVERDUE at due date.

        Scenario: Chore assigned but not claimed. Due date passes.
        Expected: Chore marked OVERDUE via periodic update (not midnight reset).

        Note: We use _on_periodic_update here because that's what detects
        overdue during the day. _on_midnight_rollover would also detect
        overdue but then immediately reset it due to clear_at_approval_reset.
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        chore_id = setup_at_due_date_scenario.chore_ids["AtDueDateOnce Reset Chore"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Verify initial pending state (no claim)
        assert not coordinator.chore_manager.chore_has_pending_claim(kid_id, chore_id)
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            kid_id, chore_id
        )

        # Set due date to the past
        set_chore_due_date_to_past(
            coordinator, chore_id, kid_id=kid_id, now_utc=fixed_now
        )

        # Trigger overdue check via periodic update (simulating due date passing)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_periodic_update(now_utc=fixed_now)

        # Verify overdue status
        assert coordinator.chore_manager.chore_is_overdue(kid_id, chore_id), (
            "Expected unclaimed PENDING chore to become OVERDUE at due date"
        )
        final_state = get_kid_state_for_chore(coordinator, kid_id, chore_id)
        assert final_state == const.CHORE_STATE_OVERDUE

    @pytest.mark.asyncio
    async def test_claimed_pending_with_clear_action_becomes_overdue(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test claimed PENDING chore with CLEAR action becomes OVERDUE then resets.

        Scenario: Kid claimed chore (pending_claim_action=CLEAR). Due date passes.
        Expected: Pending claim is cleared, then marked OVERDUE, then reset at next cycle.
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        chore_id = setup_at_due_date_scenario.chore_ids["AtDueDateOnce Reset Chore"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Claim the chore
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Test User")

        # Verify claimed state
        assert coordinator.chore_manager.chore_has_pending_claim(kid_id, chore_id)

        # Set due date to the past
        set_chore_due_date_to_past(
            coordinator, chore_id, kid_id=kid_id, now_utc=fixed_now
        )

        # Trigger reset cycle (which clears pending claims before overdue check runs)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # With CLEAR action, pending claim should be cleared and state reset to PENDING
        assert not coordinator.chore_manager.chore_has_pending_claim(
            kid_id, chore_id
        ), "Expected pending claim to be cleared after reset"
        final_state = get_kid_state_for_chore(coordinator, kid_id, chore_id)
        expected_display = get_expected_reset_display_state(
            coordinator, kid_id, chore_id
        )
        assert final_state == expected_display
        assert not coordinator.chore_manager.chore_is_overdue(kid_id, chore_id)

    @pytest.mark.asyncio
    async def test_overdue_resets_to_pending_then_reset_behavior(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test OVERDUE chore is cleared at reset with AT_DUE_DATE_THEN_RESET.

        The AT_DUE_DATE_THEN_RESET overdue handling type is designed to:
        1. Mark chore OVERDUE when due date passes (if not completed)
        2. Clear the OVERDUE status at the next reset cycle

        This only works with AT_MIDNIGHT_* reset types (at_midnight_once,
        at_midnight_multi) because the reset must occur AFTER the due date
        to allow the overdue window.

        Scenario: Chore is overdue. Reset cycle runs.
        Expected: OVERDUE status cleared, reset to PENDING.
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        chore_id = setup_at_due_date_scenario.chore_ids["AtDueDateOnce Reset Chore"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Set due date to past
        set_chore_due_date_to_past(
            coordinator, chore_id, kid_id=kid_id, now_utc=fixed_now
        )

        # Mark overdue via periodic update (simulates mid-day due date passing)
        # This is the correct flow: due date passes → becomes OVERDUE
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_periodic_update(now_utc=fixed_now)

        # Verify overdue status
        assert coordinator.chore_manager.chore_is_overdue(kid_id, chore_id), (
            "Expected chore to be OVERDUE after due date passes"
        )

        # Now trigger midnight rollover - this should clear OVERDUE with "then_reset"
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # EXPECTED BEHAVIOR: OVERDUE status IS cleared with AT_DUE_DATE_THEN_RESET
        # The reset logic includes OVERDUE in states_to_skip when overdue_handling
        # is NOT AT_DUE_DATE_THEN_RESET, but INCLUDES it when it IS "then_reset"
        assert not coordinator.chore_manager.chore_is_overdue(kid_id, chore_id), (
            "OVERDUE status should be cleared at reset with AT_DUE_DATE_THEN_RESET"
        )
        final_state = get_kid_state_for_chore(coordinator, kid_id, chore_id)
        expected_display = get_expected_reset_display_state(
            coordinator, kid_id, chore_id
        )
        assert final_state == expected_display
        assert not coordinator.chore_manager.chore_is_overdue(kid_id, chore_id)

    @pytest.mark.asyncio
    async def test_future_due_date_no_overdue_or_reset(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test that chores with future due dates are not reset or marked overdue.

        Scenario: Chore due date is in the future.
        Expected: No overdue marking, no reset triggered.
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        chore_id = setup_at_due_date_scenario.chore_ids["AtDueDateOnce Reset Chore"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Approve the chore
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Test User")
            await coordinator.chore_manager.approve_chore("Parent", kid_id, chore_id)

        # Set due date to the future
        set_chore_due_date_to_future(
            coordinator, chore_id, kid_id=kid_id, now_utc=fixed_now
        )

        # Trigger reset cycle
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # Verify chore was NOT reset (due date in future)
        assert coordinator.chore_manager.chore_is_approved_in_period(
            kid_id, chore_id
        ), "Expected approved chore with future due date to NOT be reset"

        # Trigger overdue check
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # Verify NOT marked overdue
        assert not coordinator.chore_manager.chore_is_overdue(kid_id, chore_id), (
            "Expected chore with future due date to NOT be marked overdue"
        )


# ============================================================================
# TEST CLASS: Validation of AT_DUE_DATE_THEN_RESET Combinations
# ============================================================================


class TestOverdueResetValidation:
    """Test validation rejects invalid AT_DUE_DATE_THEN_RESET combinations.

    AT_DUE_DATE_THEN_RESET only makes sense with AT_MIDNIGHT_* reset types
    because the reset must happen AFTER the due date.

    Invalid combinations:
    - AT_DUE_DATE_ONCE + AT_DUE_DATE_THEN_RESET (same trigger moment)
    - AT_DUE_DATE_MULTI + AT_DUE_DATE_THEN_RESET (same trigger moment)
    - UPON_COMPLETION + AT_DUE_DATE_THEN_RESET (reset never fires if not completed)

    Valid combinations:
    - AT_MIDNIGHT_ONCE + AT_DUE_DATE_THEN_RESET ✓
    - AT_MIDNIGHT_MULTI + AT_DUE_DATE_THEN_RESET ✓
    """

    @pytest.mark.asyncio
    async def test_at_due_date_once_with_then_reset_rejected(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that AT_DUE_DATE_ONCE + AT_DUE_DATE_THEN_RESET is rejected."""
        # Import flow_helpers to test validation directly
        from custom_components.kidschores.helpers import flow_helpers as fh

        # Create minimal chore input with invalid combination
        user_input = {
            const.CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë"],
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
            const.CFOF_CHORES_INPUT_ICON: "mdi:check",
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.CFOF_CHORES_INPUT_AUTO_APPROVE: False,
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: True,
            const.CFOF_CHORES_INPUT_LABELS: [],
            const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
            ],
            const.CFOF_CHORES_INPUT_NOTIFICATIONS: [],
        }

        # Create kids_dict mapping name to UUID (like coordinator does)
        kids_dict = {"Zoë": "kid_001"}

        # Validate using validate_chores_inputs
        errors, _due_date_str = fh.validate_chores_inputs(
            user_input=user_input,
            kids_dict=kids_dict,
            existing_chores={},
        )

        # Verify validation rejected the combination
        assert errors, (
            "Expected validation to reject AT_DUE_DATE_ONCE + AT_DUE_DATE_THEN_RESET"
        )
        assert const.CFOP_ERROR_OVERDUE_RESET_COMBO in errors, (
            f"Expected error key {const.CFOP_ERROR_OVERDUE_RESET_COMBO}, got {errors}"
        )

    @pytest.mark.asyncio
    async def test_upon_completion_with_clear_at_approval_reset_accepted(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that UPON_COMPLETION + AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET is accepted.

        This combination is valid because UPON_COMPLETION provides immediate reset
        on approval, which effectively clears the overdue status immediately.
        """
        from custom_components.kidschores.helpers import flow_helpers as fh

        user_input = {
            const.CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë"],
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
            const.CFOF_CHORES_INPUT_ICON: "mdi:check",
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.CFOF_CHORES_INPUT_AUTO_APPROVE: False,
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: True,
            const.CFOF_CHORES_INPUT_LABELS: [],
            const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
            ],
            const.CFOF_CHORES_INPUT_NOTIFICATIONS: [],
        }

        kids_dict = {"Zoë": "kid_001"}

        errors, _due_date_str = fh.validate_chores_inputs(
            user_input=user_input,
            kids_dict=kids_dict,
            existing_chores={},
        )

        # Should be accepted - UPON_COMPLETION provides immediate reset
        assert not errors, f"Expected no errors, got {errors}"

    @pytest.mark.asyncio
    async def test_at_midnight_once_with_then_reset_accepted(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that AT_MIDNIGHT_ONCE + AT_DUE_DATE_THEN_RESET is accepted."""
        from custom_components.kidschores.helpers import flow_helpers as fh

        user_input = {
            const.CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë"],
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
            const.CFOF_CHORES_INPUT_ICON: "mdi:check",
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.CFOF_CHORES_INPUT_AUTO_APPROVE: False,
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: True,
            const.CFOF_CHORES_INPUT_LABELS: [],
            const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
            ],
            const.CFOF_CHORES_INPUT_NOTIFICATIONS: [],
        }

        kids_dict = {"Zoë": "kid_001"}

        errors, _due_date_str = fh.validate_chores_inputs(
            user_input=user_input,
            kids_dict=kids_dict,
            existing_chores={},
        )

        assert not errors, (
            f"Expected no validation errors for valid combination, got {errors}"
        )

    @pytest.mark.asyncio
    async def test_at_midnight_multi_with_then_reset_accepted(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that AT_MIDNIGHT_MULTI + AT_DUE_DATE_THEN_RESET is accepted."""
        from custom_components.kidschores.helpers import flow_helpers as fh

        user_input = {
            const.CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë"],
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
            const.CFOF_CHORES_INPUT_ICON: "mdi:check",
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.CFOF_CHORES_INPUT_AUTO_APPROVE: False,
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: True,
            const.CFOF_CHORES_INPUT_LABELS: [],
            const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
            ],
            const.CFOF_CHORES_INPUT_NOTIFICATIONS: [],
        }

        kids_dict = {"Zoë": "kid_001"}

        errors, _due_date_str = fh.validate_chores_inputs(
            user_input=user_input,
            kids_dict=kids_dict,
            existing_chores={},
        )

        assert not errors, (
            f"Expected no validation errors for valid combination, got {errors}"
        )


# ============================================================================
# TEST CLASS: Per-Kid Reset Isolation (Phase 1 - HIGH PRIORITY)
# ============================================================================


class TestPerKidResetIsolation:
    """Test that INDEPENDENT chores reset only for kids with past due dates.

    This tests Finding #1 from TEST_AUDIT_FINDINGS_IN-PROCESS.md:
    Verify that INDEPENDENT chores with multiple kids only reset for kids
    whose due dates have passed, not all assigned kids simultaneously.

    Key behavior:
    - INDEPENDENT chore with kids A and B
    - Kid A has due date in PAST → should reset to PENDING
    - Kid B has due date in FUTURE → should stay APPROVED
    - Reset operation should respect per-kid due dates
    """

    @pytest.mark.asyncio
    async def test_independent_multi_kid_reset_respects_per_kid_due_dates(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test that INDEPENDENT chore resets only for kid with past due date.

        Scenario:
        - 2 kids (Zoë, Max) both complete INDEPENDENT chore
        - Zoë's due date set to PAST
        - Max's due date set to FUTURE
        - Trigger reset cycle

        Expected:
        - Zoë's chore: APPROVED → PENDING (due date passed)
        - Max's chore: APPROVED → APPROVED (due date in future)
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid1_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        kid2_id = setup_at_due_date_scenario.kid_ids["Max!"]
        chore_id = setup_at_due_date_scenario.chore_ids["Multi Kid Reset Test"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Both kids claim and get approved
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid1_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Parent", kid1_id, chore_id)
            await coordinator.chore_manager.claim_chore(kid2_id, chore_id, "Max!")
            await coordinator.chore_manager.approve_chore("Parent", kid2_id, chore_id)

        # Verify both approved
        assert (
            get_kid_state_for_chore(coordinator, kid1_id, chore_id)
            == const.CHORE_STATE_APPROVED
        )
        assert (
            get_kid_state_for_chore(coordinator, kid2_id, chore_id)
            == const.CHORE_STATE_APPROVED
        )

        # Set kid1 due date to PAST, kid2 due date to FUTURE
        _past_date, _future_date = set_per_kid_due_dates_mixed(
            coordinator,
            chore_id,
            kid1_id,
            kid2_id,
            kid1_days_ago=1,
            kid2_days_ahead=2,
            now_utc=fixed_now,
        )

        # Trigger reset cycle (this is what runs at midnight)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # ASSERT: Kid1 (past due date) should reset and resolve to exact display state.
        kid1_state = get_kid_state_for_chore(coordinator, kid1_id, chore_id)
        kid1_expected_display = get_expected_reset_display_state(
            coordinator, kid1_id, chore_id
        )
        assert kid1_state == kid1_expected_display, (
            f"Kid1 with past due date should display {kid1_expected_display}, got {kid1_state}"
        )
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            kid1_id, chore_id
        )
        assert not coordinator.chore_manager.chore_is_overdue(kid1_id, chore_id)

        # ASSERT: Kid2 (future due date) should remain APPROVED
        kid2_state = get_kid_state_for_chore(coordinator, kid2_id, chore_id)
        assert kid2_state == const.CHORE_STATE_APPROVED, (
            f"Kid2 with future due date should stay APPROVED, got {kid2_state}"
        )

    @pytest.mark.asyncio
    async def test_independent_all_kids_reset_when_all_past_due(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test that ALL kids reset when ALL their due dates have passed.

        Scenario:
        - 2 kids (Zoë, Max) both complete INDEPENDENT chore
        - BOTH kids' due dates set to PAST
        - Trigger reset cycle

        Expected:
        - Both kids: APPROVED → PENDING (all due dates passed)
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid1_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        kid2_id = setup_at_due_date_scenario.kid_ids["Max!"]
        chore_id = setup_at_due_date_scenario.chore_ids["Multi Kid Reset Test"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Both kids claim and get approved
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid1_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Parent", kid1_id, chore_id)
            await coordinator.chore_manager.claim_chore(kid2_id, chore_id, "Max!")
            await coordinator.chore_manager.approve_chore("Parent", kid2_id, chore_id)

        # Verify both approved
        assert (
            get_kid_state_for_chore(coordinator, kid1_id, chore_id)
            == const.CHORE_STATE_APPROVED
        )
        assert (
            get_kid_state_for_chore(coordinator, kid2_id, chore_id)
            == const.CHORE_STATE_APPROVED
        )

        # Set BOTH due dates to PAST
        set_chore_due_date_to_past(
            coordinator, chore_id, kid_id=kid1_id, days_ago=1, now_utc=fixed_now
        )
        set_chore_due_date_to_past(
            coordinator, chore_id, kid_id=kid2_id, days_ago=1, now_utc=fixed_now
        )

        # Trigger reset cycle
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # ASSERT: BOTH kids should reset to PENDING
        kid1_state = get_kid_state_for_chore(coordinator, kid1_id, chore_id)
        kid2_state = get_kid_state_for_chore(coordinator, kid2_id, chore_id)

        kid1_expected_display = get_expected_reset_display_state(
            coordinator, kid1_id, chore_id
        )
        kid2_expected_display = get_expected_reset_display_state(
            coordinator, kid2_id, chore_id
        )

        assert kid1_state == kid1_expected_display, (
            f"Kid1 with past due date should display {kid1_expected_display}, got {kid1_state}"
        )
        assert kid2_state == kid2_expected_display, (
            f"Kid2 with past due date should display {kid2_expected_display}, got {kid2_state}"
        )
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            kid1_id, chore_id
        )
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            kid2_id, chore_id
        )
        assert not coordinator.chore_manager.chore_is_overdue(kid1_id, chore_id)
        assert not coordinator.chore_manager.chore_is_overdue(kid2_id, chore_id)

    @pytest.mark.asyncio
    async def test_independent_no_kids_reset_when_all_future_due(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Test that NO kids reset when ALL due dates are in future.

        Scenario:
        - 2 kids (Zoë, Max) both complete INDEPENDENT chore
        - BOTH kids' due dates set to FUTURE
        - Trigger reset cycle

        Expected:
        - Both kids: APPROVED → APPROVED (no due dates passed)
        """
        coordinator = setup_at_due_date_scenario.coordinator
        kid1_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        kid2_id = setup_at_due_date_scenario.kid_ids["Max!"]
        chore_id = setup_at_due_date_scenario.chore_ids["Multi Kid Reset Test"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        # Both kids claim and get approved
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid1_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Parent", kid1_id, chore_id)
            await coordinator.chore_manager.claim_chore(kid2_id, chore_id, "Max!")
            await coordinator.chore_manager.approve_chore("Parent", kid2_id, chore_id)

        # Verify both approved
        assert (
            get_kid_state_for_chore(coordinator, kid1_id, chore_id)
            == const.CHORE_STATE_APPROVED
        )
        assert (
            get_kid_state_for_chore(coordinator, kid2_id, chore_id)
            == const.CHORE_STATE_APPROVED
        )

        # Set BOTH due dates to FUTURE
        set_chore_due_date_to_future(
            coordinator, chore_id, kid_id=kid1_id, days_ahead=2, now_utc=fixed_now
        )
        set_chore_due_date_to_future(
            coordinator, chore_id, kid_id=kid2_id, days_ahead=3, now_utc=fixed_now
        )

        # Trigger reset cycle
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        # ASSERT: BOTH kids should stay APPROVED (no reset)
        kid1_state = get_kid_state_for_chore(coordinator, kid1_id, chore_id)
        kid2_state = get_kid_state_for_chore(coordinator, kid2_id, chore_id)

        assert kid1_state == const.CHORE_STATE_APPROVED, (
            f"Kid1 with future due date should stay APPROVED, got {kid1_state}"
        )
        assert kid2_state == const.CHORE_STATE_APPROVED, (
            f"Kid2 with future due date should stay APPROVED, got {kid2_state}"
        )

    @pytest.mark.asyncio
    async def test_reset_updates_only_past_due_kid_approval_period_start(
        self,
        hass: HomeAssistant,
        setup_at_due_date_scenario: SetupResult,
    ) -> None:
        """Reset updates approval period start only for kids actually reset."""
        coordinator = setup_at_due_date_scenario.coordinator
        kid1_id = setup_at_due_date_scenario.kid_ids["Zoë"]
        kid2_id = setup_at_due_date_scenario.kid_ids["Max!"]
        chore_id = setup_at_due_date_scenario.chore_ids["Multi Kid Reset Test"]
        fixed_now = datetime(2026, 2, 14, 0, 5, tzinfo=UTC)

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid1_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Parent", kid1_id, chore_id)
            await coordinator.chore_manager.claim_chore(kid2_id, chore_id, "Max!")
            await coordinator.chore_manager.approve_chore("Parent", kid2_id, chore_id)

        set_per_kid_due_dates_mixed(
            coordinator,
            chore_id,
            kid1_id,
            kid2_id,
            kid1_days_ago=1,
            kid2_days_ahead=2,
            now_utc=fixed_now,
        )

        kid1_before = coordinator.kids_data[kid1_id][DATA_KID_CHORE_DATA][chore_id].get(
            DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
        )
        kid2_before = coordinator.kids_data[kid2_id][DATA_KID_CHORE_DATA][chore_id].get(
            DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
        )

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager._on_midnight_rollover(now_utc=fixed_now)

        kid1_after = coordinator.kids_data[kid1_id][DATA_KID_CHORE_DATA][chore_id].get(
            DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
        )
        kid2_after = coordinator.kids_data[kid2_id][DATA_KID_CHORE_DATA][chore_id].get(
            DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START
        )

        assert kid1_after is not None and kid1_before is not None
        assert datetime.fromisoformat(kid1_after) > datetime.fromisoformat(kid1_before)
        assert kid2_after == kid2_before
