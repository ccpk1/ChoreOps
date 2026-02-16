"""Chore scheduling tests - due dates, overdue detection, and frequency behavior.

This module tests:
1. Due date loading from YAML scenario (with relative past/future dates)
2. Overdue state detection based on due dates and overdue_handling_type
3. Frequency effects on due date behavior (once vs recurring)
4. Due date changes after chore approval (rescheduling behavior)

Phase 3 of the Chore Workflow Testing initiative.
See: docs/in-process/CHORE_WORKFLOW_TESTING_IN-PROCESS.md

Test Organization:
- TestDueDateLoading: Verify due dates load correctly from YAML
- TestOverdueDetection: Verify overdue state based on due date and handling type
- TestFrequencyEffects: Verify once vs daily/weekly behavior

===============================================================================
REFERENCE: Approval Reset Types (5 options)
===============================================================================
Controls WHEN a chore becomes available again after completion/approval.

  APPROVAL_RESET_AT_MIDNIGHT_ONCE ("at_midnight_once")
    - Chore resets at midnight, can only be completed ONCE per day
    - After approval, cannot claim again until after midnight

  APPROVAL_RESET_AT_MIDNIGHT_MULTI ("at_midnight_multi")
    - Chore resets at midnight, can be completed MULTIPLE times per day
    - After approval, can claim again immediately (until midnight)

  APPROVAL_RESET_AT_DUE_DATE_ONCE ("at_due_date_once")
    - Chore resets when due date passes, can only be completed ONCE per cycle
    - After approval, cannot claim again until after due date passes

  APPROVAL_RESET_AT_DUE_DATE_MULTI ("at_due_date_multi")
    - Chore resets when due date passes, can be completed MULTIPLE times per cycle
    - After approval, can claim again immediately (until due date)

  APPROVAL_RESET_UPON_COMPLETION ("upon_completion")
    - Chore resets immediately after approval (continuous availability)
    - After approval, can claim again immediately

Coordinator method: _process_approval_boundary(trigger, now_utc, *, skip_time_check=False)
  - Called by scheduled tasks to reset chore states based on approval_reset_type
  - Handles both AT_MIDNIGHT_* and AT_DUE_DATE_* reset types

===============================================================================
REFERENCE: Overdue Handling Types (3 options)
===============================================================================
Controls HOW overdue status is handled when due date passes.

  OVERDUE_HANDLING_AT_DUE_DATE ("at_due_date")
    - Chore becomes OVERDUE when due date passes (standard behavior)
    - Stays overdue until claimed/approved or manually reset

  OVERDUE_HANDLING_NEVER_OVERDUE ("never_overdue")
    - Chore NEVER gets marked overdue, even if past due date
    - Useful for optional/flexible tasks

  OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET ("at_due_date_clear_at_approval_reset")
    - Chore becomes OVERDUE at due date
    - AUTOMATICALLY resets to PENDING at next approval reset cycle
    - The reset happens in _process_approval_boundary() or
      _reset_independent_chore_status() / _reset_shared_chore_status()
    - When should_clear_overdue=True, OVERDUE state is NOT skipped during reset

Coordinator method: _process_time_checks()
  - Checks all chores and marks them OVERDUE based on overdue_handling_type
  - Does NOT reset chores - that's handled by the reset methods above
===============================================================================
"""

# pylint: disable=redefined-outer-name

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.core import Context, HomeAssistant
import pytest

from custom_components.kidschores import const
from custom_components.kidschores.utils.dt_utils import dt_now_utc, dt_to_utc
from tests.helpers import (
    APPROVAL_RESET_AT_DUE_DATE_MULTI,
    APPROVAL_RESET_AT_DUE_DATE_ONCE,
    APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    APPROVAL_RESET_AT_MIDNIGHT_ONCE,
    APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
    APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    APPROVAL_RESET_PENDING_CLAIM_HOLD,
    APPROVAL_RESET_UPON_COMPLETION,
    ATTR_CAN_CLAIM,
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PENDING,
    CHORE_STATE_WAITING,
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    DATA_CHORE_APPLICABLE_DAYS,
    DATA_CHORE_APPROVAL_PERIOD_START,
    DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    DATA_CHORE_APPROVAL_RESET_TYPE,
    DATA_CHORE_ASSIGNED_KIDS,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_DEFAULT_POINTS,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_NAME,
    DATA_CHORE_OVERDUE_HANDLING_TYPE,
    DATA_CHORE_PER_KID_DUE_DATES,
    DATA_CHORE_RECURRING_FREQUENCY,
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START,
    DATA_KID_CHORE_DATA_STATE,
    DATA_KID_NAME,
    DATA_KID_POINTS,
    DOMAIN,
    FREQUENCY_DAILY,
    FREQUENCY_NONE,
    FREQUENCY_WEEKLY,
    OVERDUE_HANDLING_AT_DUE_DATE,
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
    OVERDUE_HANDLING_NEVER_OVERDUE,
    SERVICE_UPDATE_CHORE,
    TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED,
    SetupResult,
    claim_chore,
    find_chore,
    get_dashboard_helper,
    setup_from_yaml,
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def set_chore_due_date_to_past(
    coordinator: Any,
    chore_id: str,
    kid_id: str | None = None,
    days_ago: int = 1,
) -> datetime:
    """Set a chore's due date to a past date for testing overdue behavior.

    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  WHY THIS HELPER EXISTS                                                  ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║  await coordinator.chore_manager.set_due_date() INTENTIONALLY:                         ║
    ║    1. Resets chore state to PENDING                                      ║
    ║    2. Clears pending_claim_count to 0                                    ║
    ║    3. Resets approval_period_start to now                                ║
    ║                                                                          ║
    ║  This is correct behavior for production (changing due date = new period)║
    ║  but breaks tests that need to simulate "time passing" while PRESERVING  ║
    ║  current claim/approval state (e.g., testing claimed chores don't        ║
    ║  become overdue).                                                        ║
    ║                                                                          ║
    ║  This helper directly modifies the data structures to:                   ║
    ║    - Set due date to the past                                            ║
    ║    - Set approval_period_start BEFORE the past due date                  ║
    ║    - NOT touch state or pending_claim_count                              ║
    ╚══════════════════════════════════════════════════════════════════════════╝

    Storage locations by completion_criteria:
      SHARED:      due_date at chore level, approval_period_start at chore level
      INDEPENDENT: due_date per-kid, approval_period_start per-kid in kid_chore_data

    Args:
        coordinator: KidsChoresDataCoordinator
        chore_id: The chore's internal UUID
        kid_id: For independent chores, the kid's UUID (or None to set all)
        days_ago: How many days in the past (default: 1 = yesterday)

    Returns:
        The past datetime that was set
    """
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    # Calculate past due date
    past_date = datetime.now(UTC) - timedelta(days=days_ago)
    past_date = past_date.replace(hour=17, minute=0, second=0, microsecond=0)
    past_date_iso = dt_util.as_utc(past_date).isoformat()

    # Approval period start must be BEFORE the past due date
    # (so any claims made "now" are valid for this period)
    period_start = past_date - timedelta(days=1)
    period_start_iso = dt_util.as_utc(period_start).isoformat()

    chore_info = coordinator.chores_data.get(chore_id, {})
    criteria = chore_info.get(
        DATA_CHORE_COMPLETION_CRITERIA,
        COMPLETION_CRITERIA_SHARED,
    )

    # Update due date and approval_period_start WITHOUT resetting state
    if criteria == COMPLETION_CRITERIA_INDEPENDENT:
        # INDEPENDENT: due date and approval_period_start are per-kid
        per_kid_due_dates = chore_info.setdefault(DATA_CHORE_PER_KID_DUE_DATES, {})
        if kid_id:
            # Single kid
            per_kid_due_dates[kid_id] = past_date_iso
            kid_info = coordinator.kids_data.get(kid_id, {})
            kid_chore_data = kid_info.get(DATA_KID_CHORE_DATA, {}).get(chore_id, {})
            if kid_chore_data:
                kid_chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                    period_start_iso
                )
        else:
            # All assigned kids
            for assigned_kid_id in chore_info.get(DATA_CHORE_ASSIGNED_KIDS, []):
                per_kid_due_dates[assigned_kid_id] = past_date_iso
                kid_info = coordinator.kids_data.get(assigned_kid_id, {})
                kid_chore_data = kid_info.get(DATA_KID_CHORE_DATA, {}).get(chore_id, {})
                if kid_chore_data:
                    kid_chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = (
                        period_start_iso
                    )
    else:
        # SHARED: due date and approval_period_start are at chore level
        chore_info[DATA_CHORE_DUE_DATE] = past_date_iso
        chore_info[DATA_CHORE_APPROVAL_PERIOD_START] = period_start_iso

    return past_date


def get_chore_due_date(
    coordinator: Any,
    chore_id: str,
) -> datetime | None:
    """Get the due date for a chore (global/template level).

    For INDEPENDENT chores, this is the template; per-kid dates are in per_kid_due_dates.
    For SHARED chores, this is the authoritative due date.

    Args:
        coordinator: KidsChoresDataCoordinator
        chore_id: The chore's internal UUID

    Returns:
        datetime object if due date exists, None otherwise
    """
    chore_info = coordinator.chores_data.get(chore_id, {})
    due_str = chore_info.get(DATA_CHORE_DUE_DATE)
    if not due_str:
        return None
    return dt_to_utc(due_str)


def get_kid_due_date(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> datetime | None:
    """Get the due date for a chore for a specific kid.

    For INDEPENDENT chores, reads from per_kid_due_dates.
    For SHARED chores, falls back to chore-level due date.

    Args:
        coordinator: KidsChoresDataCoordinator
        kid_id: The kid's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        datetime object if due date exists, None otherwise
    """
    chore_info = coordinator.chores_data.get(chore_id, {})

    # Check per-kid due dates first (INDEPENDENT chores)
    per_kid_due_dates = chore_info.get(DATA_CHORE_PER_KID_DUE_DATES, {})
    if kid_id in per_kid_due_dates:
        due_str = per_kid_due_dates[kid_id]
        if due_str:
            return dt_to_utc(due_str)

    # Fall back to chore-level due date (SHARED chores or template)
    due_str = chore_info.get(DATA_CHORE_DUE_DATE)
    if not due_str:
        return None
    return dt_to_utc(due_str)


def get_kid_chore_state(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> str:
    """Get the current state of a chore for a specific kid.

    Args:
        coordinator: KidsChoresDataCoordinator
        kid_id: The kid's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        State string (e.g., 'pending', 'claimed', 'approved', 'overdue')
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_chore_by_name(
    coordinator: Any,
    name: str,
) -> tuple[str, dict[str, Any]] | None:
    """Find a chore by name.

    Args:
        coordinator: KidsChoresDataCoordinator
        name: Chore name to find

    Returns:
        Tuple of (chore_id, chore_info) or None if not found
    """
    for chore_id, chore_info in coordinator.chores_data.items():
        if chore_info.get(DATA_CHORE_NAME) == name:
            return chore_id, chore_info
    return None


def get_kid_by_name(
    coordinator: Any,
    name: str,
) -> tuple[str, dict[str, Any]] | None:
    """Find a kid by name.

    Args:
        coordinator: KidsChoresDataCoordinator
        name: Kid name to find

    Returns:
        Tuple of (kid_id, kid_info) or None if not found
    """
    for kid_id, kid_info in coordinator.kids_data.items():
        if kid_info.get(DATA_KID_NAME) == name:
            return kid_id, kid_info
    return None


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scheduling_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scheduling scenario using modern setup_from_yaml().

    Returns:
        SetupResult with config_entry, coordinator, kid_ids, chore_ids maps
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_scheduling.yaml",
    )


# =============================================================================
# TEST CLASS: Due Date Loading
# =============================================================================


class TestDueDateLoading:
    """Test that due dates load correctly from YAML scenario."""

    @pytest.mark.asyncio
    async def test_future_due_date_is_in_future(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test that chores with due_date_relative='future' have future due dates."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        # "Reset Midnight Once" has due_date_relative: "future"
        chore_id = chore_map["Reset Midnight Once"]
        due_date = get_kid_due_date(coordinator, zoe_id, chore_id)

        assert due_date is not None, "Due date should be set"
        now_utc = datetime.now(UTC)
        assert due_date > now_utc, f"Due date {due_date} should be in the future"

    @pytest.mark.asyncio
    async def test_past_due_date_is_in_past(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test that we can set a due date to the past via coordinator."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        # "Overdue At Due Date" - set due date to past via coordinator
        # (Config flow rejects past dates, so we modify after setup)
        chore_id = chore_map["Overdue At Due Date"]
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        due_date = get_kid_due_date(coordinator, zoe_id, chore_id)

        assert due_date is not None, "Due date should be set"
        now_utc = datetime.now(UTC)
        assert due_date < now_utc, f"Due date {due_date} should be in the past"

    @pytest.mark.asyncio
    async def test_all_scheduling_chores_have_due_dates(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test that all chores in scheduling scenario have due dates set."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        for chore_name, chore_id in chore_map.items():
            due_date = get_kid_due_date(coordinator, zoe_id, chore_id)
            assert due_date is not None, f"Chore '{chore_name}' should have a due date"

    @pytest.mark.asyncio
    async def test_due_date_is_timezone_aware(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test that due dates are timezone-aware (UTC)."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Once"]
        due_date = get_kid_due_date(coordinator, zoe_id, chore_id)

        assert due_date is not None
        assert due_date.tzinfo is not None, "Due date should be timezone-aware"


# =============================================================================
# TEST CLASS: Overdue Detection
# =============================================================================


class TestOverdueDetection:
    """Test overdue state detection based on due dates and overdue_handling_type."""

    @pytest.mark.asyncio
    async def test_past_due_at_due_date_is_overdue(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: overdue_handling_type='at_due_date' with past due date → OVERDUE state.

        "Overdue At Due Date" - set due date to past via coordinator, then check overdue.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue At Due Date"]

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger overdue check by calling the coordinator's check method
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is OVERDUE
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_OVERDUE, (
            f"Chore with past due date and at_due_date handling should be OVERDUE, got {state}"
        )

        # Also verify using coordinator's chore_is_overdue method
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id) is True

    @pytest.mark.asyncio
    async def test_past_due_never_overdue_stays_pending(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: overdue_handling_type='never_overdue' with past due date → stays PENDING.

        "Overdue Never" - set to past but should NOT become overdue.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue Never"]

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is still PENDING (not overdue)
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            f"Chore with never_overdue should stay PENDING, got {state}"
        )

        # Also verify using coordinator's chore_is_overdue method
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id) is False

    @pytest.mark.asyncio
    async def test_future_due_not_overdue(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Future due date should NOT be overdue."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Once"]

        # Trigger overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is PENDING (not overdue)
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            f"Chore with future due date should be PENDING, got {state}"
        )

        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id) is False

    @pytest.mark.asyncio
    async def test_weekly_overdue_is_detected(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Weekly chore with past due date becomes overdue.

        "Weekly Overdue" - set to past and verify it becomes overdue.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Weekly Overdue"]

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=3)

        # Trigger overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is OVERDUE
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_OVERDUE, (
            f"Weekly chore with past due date should be OVERDUE, got {state}"
        )


# =============================================================================
# TEST CLASS: Frequency Effects
# =============================================================================


class TestFrequencyEffects:
    """Test frequency-specific behavior for due dates and chore lifecycle."""

    @pytest.mark.asyncio
    async def test_one_time_chore_has_due_date(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: One-time chore has a due date set."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["One Time Task"]

        # Verify due date exists
        due_date = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date is not None, "One-time chore should have a due date"

        # Verify frequency (recurring_frequency: "none" for one-time chores)
        chore_info = coordinator.chores_data.get(chore_id, {})
        frequency = chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
        assert frequency == FREQUENCY_NONE, (
            f"One-time chore should have 'none' frequency, got {frequency}"
        )

    @pytest.mark.asyncio
    async def test_daily_chore_frequency(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Daily chores have correct frequency setting."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Once"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        frequency = chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
        assert frequency == FREQUENCY_DAILY, (
            f"Daily chore should have 'daily' frequency, got {frequency}"
        )

    @pytest.mark.asyncio
    async def test_weekly_chore_frequency(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Weekly chores have correct frequency setting."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Once"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        frequency = chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
        assert frequency == FREQUENCY_WEEKLY


# =============================================================================
# TEST CLASS: Chore Configuration Verification
# =============================================================================


class TestChoreConfigurationVerification:
    """Verify that scheduling scenario chores have correct configuration."""

    @pytest.mark.asyncio
    async def test_approval_reset_types_loaded(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: All 5 approval reset types are loaded from scenario."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        expected = {
            "Reset Midnight Once": APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            "Reset Midnight Multi": APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            "Reset Due Date Once": APPROVAL_RESET_AT_DUE_DATE_ONCE,
            "Reset Due Date Multi": APPROVAL_RESET_AT_DUE_DATE_MULTI,
            "Reset Upon Completion": APPROVAL_RESET_UPON_COMPLETION,
        }

        for chore_name, expected_type in expected.items():
            chore_id = chore_map[chore_name]
            chore_info = coordinator.chores_data.get(chore_id, {})
            actual_type = chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            assert actual_type == expected_type, (
                f"'{chore_name}' should have approval_reset_type={expected_type}, got {actual_type}"
            )

    @pytest.mark.asyncio
    async def test_overdue_handling_types_loaded(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: All 3 overdue handling types are loaded from scenario."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        expected = {
            "Overdue At Due Date": OVERDUE_HANDLING_AT_DUE_DATE,
            "Overdue Never": OVERDUE_HANDLING_NEVER_OVERDUE,
            "Overdue Then Reset": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
        }

        for chore_name, expected_type in expected.items():
            chore_id = chore_map[chore_name]
            chore_info = coordinator.chores_data.get(chore_id, {})
            actual_type = chore_info.get(DATA_CHORE_OVERDUE_HANDLING_TYPE)
            assert actual_type == expected_type, (
                f"'{chore_name}' should have overdue_handling_type={expected_type}, got {actual_type}"
            )

    @pytest.mark.asyncio
    async def test_pending_claim_actions_loaded(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: All 3 pending claim actions are loaded from scenario."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        expected = {
            "Pending Hold": APPROVAL_RESET_PENDING_CLAIM_HOLD,
            "Pending Clear": APPROVAL_RESET_PENDING_CLAIM_CLEAR,
            "Pending Auto Approve": APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
        }

        for chore_name, expected_type in expected.items():
            chore_id = chore_map[chore_name]
            chore_info = coordinator.chores_data.get(chore_id, {})
            actual_type = chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            assert actual_type == expected_type, (
                f"'{chore_name}' should have pending_claim_action={expected_type}, got {actual_type}"
            )

    @pytest.mark.asyncio
    async def test_scenario_has_18_chores(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Scheduling scenario has exactly 18 chores."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        assert len(chore_map) == 18, f"Expected 18 chores, got {len(chore_map)}"
        assert len(coordinator.chores_data) == 18

    @pytest.mark.asyncio
    async def test_all_chores_assigned_to_zoe(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: All chores in scheduling scenario are assigned to Zoë."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        for chore_name, chore_id in chore_map.items():
            chore_info = coordinator.chores_data.get(chore_id, {})
            assigned = chore_info.get(DATA_CHORE_ASSIGNED_KIDS, [])
            assert zoe_id in assigned, f"'{chore_name}' should be assigned to Zoë"


# =============================================================================
# TEST CLASS: Approval Reset Tests (Phase 4)
# =============================================================================


class TestApprovalResetAtMidnightOnce:
    """Test AT_MIDNIGHT_ONCE approval reset behavior.

    Expected behavior:
    - Only ONE approval allowed per approval period (midnight-to-midnight)
    - Due date should NOT change on approval
    - Due date should be rescheduled at midnight reset
    - State should remain APPROVED until midnight reset

    KNOWN BUG: Currently, approval reschedules due date immediately.
    These tests document expected behavior and will reveal the bug.
    """

    @pytest.mark.asyncio
    async def test_at_midnight_once_due_date_unchanged_on_approval(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """BUG REPRODUCTION: AT_MIDNIGHT_ONCE should NOT reschedule due date on approval.

        Expected: Approval → state=APPROVED, due_date unchanged
        Bug: Due date is rescheduled immediately on approval
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Once"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify chore has correct reset type
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_MIDNIGHT_ONCE
        )

        # Get due date before approval
        due_date_before = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date_before is not None, "Chore should have a due date"

        # Claim and approve the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify state is APPROVED
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_APPROVED

        # Get due date after approval
        due_date_after = get_kid_due_date(coordinator, zoe_id, chore_id)

        # BUG: Due date should NOT change on approval for AT_MIDNIGHT_ONCE
        # This assertion documents expected behavior - it may fail due to the bug
        assert due_date_after == due_date_before, (
            f"AT_MIDNIGHT_ONCE: Due date should NOT change on approval. "
            f"Before: {due_date_before}, After: {due_date_after}"
        )

    @pytest.mark.asyncio
    async def test_at_midnight_once_blocks_second_approval(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_MIDNIGHT_ONCE should block second approval in same period."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Once"]

        # First claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify state is APPROVED
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_APPROVED

        # Verify chore_is_approved_in_period returns True
        assert coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        ), "Should be approved in current period"

        # Verify cannot approve again (_can_approve_chore should return False)
        can_approve, error_key = coordinator.chore_manager.can_approve_chore(
            zoe_id, chore_id
        )
        assert not can_approve, "Should not be able to approve again"
        assert error_key == TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED, (
            f"Error should be already_approved, got {error_key}"
        )


class TestApprovalResetAtMidnightMulti:
    """Test AT_MIDNIGHT_MULTI approval reset behavior.

    Expected behavior:
    - MULTIPLE approvals allowed per approval period
    - Due date should NOT change on approval
    - Due date should be rescheduled at midnight reset
    - State resets to PENDING immediately after approval (allowing re-claim)
    """

    @pytest.mark.asyncio
    async def test_at_midnight_multi_allows_multiple_approvals(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_MIDNIGHT_MULTI allows multiple claim-approve cycles in same period."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Multi"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify chore has correct reset type
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_MIDNIGHT_MULTI
        )

        # First claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # MULTI should allow another claim immediately
        # _can_claim_chore should return True for MULTI types
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "AT_MIDNIGHT_MULTI should allow re-claim after approval"


class TestApprovalResetUponCompletion:
    """Test UPON_COMPLETION approval reset behavior.

    Expected behavior:
    - This is the only type that SHOULD reschedule due date on approval
    - State resets to PENDING immediately after approval
    - Due date advances to next recurrence
    """

    @pytest.mark.asyncio
    async def test_upon_completion_reschedules_due_date(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: UPON_COMPLETION should reschedule due date immediately on approval."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Upon Completion"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify chore has correct reset type
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_UPON_COMPLETION
        )

        # Get due date before approval
        due_date_before = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date_before is not None, "Chore should have a due date"

        # Claim and approve the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Get due date after approval
        due_date_after = get_kid_due_date(coordinator, zoe_id, chore_id)

        # UPON_COMPLETION SHOULD reschedule due date on approval
        assert due_date_after is not None, "Due date should still exist"
        assert due_date_after > due_date_before, (
            f"UPON_COMPLETION: Due date SHOULD advance on approval. "
            f"Before: {due_date_before}, After: {due_date_after}"
        )

    @pytest.mark.asyncio
    async def test_upon_completion_resets_to_pending(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: UPON_COMPLETION should reset state to PENDING immediately."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Upon Completion"]

        # Claim and approve the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # State should be PENDING (not APPROVED) because UPON_COMPLETION resets immediately
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            f"UPON_COMPLETION should reset to PENDING, got {state}"
        )


class TestApprovalResetAtDueDateOnce:
    """Test AT_DUE_DATE_ONCE approval reset behavior.

    Expected behavior:
    - Only ONE approval allowed until due date passes
    - Due date should NOT change on approval
    - Due date should be rescheduled when it passes (at due date reset)
    """

    @pytest.mark.asyncio
    async def test_at_due_date_once_due_date_unchanged_on_approval(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_ONCE should NOT reschedule due date on approval."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Once"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify chore has correct reset type
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_DUE_DATE_ONCE
        )

        # Get due date before approval
        due_date_before = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date_before is not None, "Chore should have a due date"

        # Claim and approve the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify state is APPROVED
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_APPROVED

        # Get due date after approval - should be unchanged
        due_date_after = get_kid_due_date(coordinator, zoe_id, chore_id)

        # Like AT_MIDNIGHT_ONCE, due date should NOT change on approval
        assert due_date_after == due_date_before, (
            f"AT_DUE_DATE_ONCE: Due date should NOT change on approval. "
            f"Before: {due_date_before}, After: {due_date_after}"
        )

    @pytest.mark.asyncio
    async def test_at_due_date_once_blocks_second_approval(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_ONCE should block second approval before due date."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Once"]

        # First claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify cannot approve again
        can_approve, error_key = coordinator.chore_manager.can_approve_chore(
            zoe_id, chore_id
        )
        assert not can_approve, "Should not be able to approve again before due date"
        assert error_key == TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED, (
            f"Error should be already_approved, got {error_key}"
        )


class TestApprovalResetAtDueDateMulti:
    """Test AT_DUE_DATE_MULTI approval reset behavior.

    Expected behavior:
    - MULTIPLE approvals allowed until due date passes
    - Due date should NOT change on approval (multi-claim within same period)
    - After each approval, chore resets to PENDING for another claim
    - When due date passes, reset happens (via midnight check or due date trigger)
    """

    @pytest.mark.asyncio
    async def test_at_due_date_multi_allows_multiple_approvals(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_MULTI allows multiple claim-approve cycles in same period."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Multi"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify chore has correct reset type
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_DUE_DATE_MULTI
        )

        # First claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # MULTI should allow another claim immediately
        # _can_claim_chore should return True for MULTI types
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "AT_DUE_DATE_MULTI should allow re-claim after approval"

        # Second claim and approve should work
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify can still claim again (multi allows unlimited before due date)
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "AT_DUE_DATE_MULTI should allow another re-claim"

    @pytest.mark.asyncio
    async def test_at_due_date_multi_due_date_unchanged_on_approval(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_MULTI should NOT reschedule due date on approval."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Multi"]

        # Get due date before approval
        due_date_before = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date_before is not None, "Chore should have a due date"

        # First approval
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Due date should remain unchanged
        due_date_after_first = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date_after_first == due_date_before, (
            f"AT_DUE_DATE_MULTI: Due date should NOT change on first approval. "
            f"Before: {due_date_before}, After: {due_date_after_first}"
        )

        # Second approval
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Due date should still remain unchanged
        due_date_after_second = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert due_date_after_second == due_date_before, (
            f"AT_DUE_DATE_MULTI: Due date should NOT change on second approval. "
            f"Before: {due_date_before}, After: {due_date_after_second}"
        )

    @pytest.mark.asyncio
    async def test_at_due_date_multi_tracks_approval_count(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_MULTI allows multiple approvals in sequence."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Multi"]

        # Track points earned to verify multiple approvals work
        initial_points = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)

        # First approval
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        points_after_first = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)
        assert points_after_first > initial_points, "First approval should grant points"

        # Second approval
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        points_after_second = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)
        assert points_after_second > points_after_first, (
            "Second approval should grant additional points"
        )

        # Third approval - verify unlimited approvals
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        points_after_third = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)
        assert points_after_third > points_after_second, (
            "Third approval should grant additional points"
        )


# =============================================================================
# PHASE 5: OVERDUE HANDLING TESTS
# Tests for overdue_handling_type: at_due_date, never_overdue, at_due_date_then_reset
# =============================================================================


class TestOverdueAtDueDate:
    """Tests for overdue_handling_type: at_due_date (default behavior)."""

    @pytest.mark.asyncio
    async def test_at_due_date_becomes_overdue_when_past(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Chore with at_due_date becomes OVERDUE when past due date."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue At Due Date"]

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Run the overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is now OVERDUE
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        current_state = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)

        assert current_state == CHORE_STATE_OVERDUE, (
            f"at_due_date chore with past due date should be OVERDUE, got {current_state}"
        )

        # Verify chore_is_overdue helper returns True
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "chore_is_overdue() should return True for OVERDUE state"
        )

    @pytest.mark.asyncio
    async def test_at_due_date_future_not_overdue(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Chore with at_due_date and future due date is NOT overdue."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        # Use a chore with future due date
        chore_id = chore_map["Reset Midnight Once"]  # Has due_date_relative: "future"

        # Run overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is NOT overdue
        assert not coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "Chore with future due date should not be overdue"
        )


class TestOverdueNeverOverdue:
    """Tests for overdue_handling_type: never_overdue."""

    @pytest.mark.asyncio
    async def test_never_overdue_stays_pending_when_past_due(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Chore with never_overdue stays PENDING even when past due date."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue Never"]

        # Verify chore has never_overdue setting
        chore_info = coordinator.chores_data.get(chore_id, {})
        overdue_type = chore_info.get(DATA_CHORE_OVERDUE_HANDLING_TYPE)
        assert overdue_type == OVERDUE_HANDLING_NEVER_OVERDUE, (
            f"Test chore should have never_overdue handling, got {overdue_type}"
        )

        # Get initial state - should be PENDING or None (not yet initialized)
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        initial_state_value = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)
        assert initial_state_value in (None, CHORE_STATE_PENDING), (
            f"Initial state should be None or PENDING, got {initial_state_value}"
        )

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Run overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is STILL PENDING or None (not overdue despite past due date)
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        current_state = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)

        assert current_state in (None, CHORE_STATE_PENDING), (
            f"never_overdue chore should stay PENDING/None, got {current_state}"
        )

        # Verify chore_is_overdue helper returns False
        assert not coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "chore_is_overdue() should return False for never_overdue chore"
        )


class TestOverdueThenReset:
    """Tests for overdue_handling_type: at_due_date_then_reset."""

    @pytest.mark.asyncio
    async def test_at_due_date_then_reset_becomes_overdue(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Chore with at_due_date_then_reset becomes OVERDUE when past due."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue Then Reset"]

        # Verify chore has at_due_date_clear_at_approval_reset setting
        chore_info = coordinator.chores_data.get(chore_id, {})
        overdue_type = chore_info.get(DATA_CHORE_OVERDUE_HANDLING_TYPE)
        assert overdue_type == OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET, (
            f"Test chore should have at_due_date_clear_at_approval_reset handling, got {overdue_type}"
        )

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Run overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is OVERDUE
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        current_state = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)

        assert current_state == CHORE_STATE_OVERDUE, (
            f"at_due_date_then_reset chore should be OVERDUE, got {current_state}"
        )

        # Verify chore_is_overdue helper returns True
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "chore_is_overdue() should return True for OVERDUE state"
        )

    @pytest.mark.asyncio
    async def test_at_due_date_then_reset_resets_after_overdue_window(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: at_due_date_then_reset chore resets to PENDING after overdue window.

        The THEN_RESET behavior means when the approval reset cycle runs,
        the OVERDUE state is cleared and chore returns to PENDING.

        Key mechanism: _process_approval_boundary() checks overdue_handling_type
        and when it's AT_DUE_DATE_THEN_RESET, the OVERDUE state is NOT skipped
        during reset (should_clear_overdue = True).
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue Then Reset"]

        # Set due date to past to trigger overdue
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Run overdue check - should become overdue
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify chore is overdue
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        assert kid_chore_data.get(DATA_KID_CHORE_DATA_STATE) == CHORE_STATE_OVERDUE

        # Run the daily reset - this is what clears AT_DUE_DATE_THEN_RESET chores
        # The reset method checks overdue_handling_type and clears OVERDUE state
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # After reset, the chore should be back to PENDING
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        current_state = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)

        assert current_state == CHORE_STATE_PENDING, (
            f"at_due_date_then_reset should reset to PENDING after window, got {current_state}"
        )

    @pytest.mark.asyncio
    async def test_at_due_date_then_reset_preserves_overdue_before_reset(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: at_due_date_then_reset maintains OVERDUE until reset trigger.

        The chore stays overdue and is visible as such until the reset mechanism runs.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue Then Reset"]

        # Set due date to past
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=2)

        # Run overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify chore is marked overdue
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "Chore should be marked overdue before reset"
        )

        # Without running reset, chore should stay overdue
        # Run overdue check again (simulates time passing but no reset)
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Still overdue
        assert coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id), (
            "Chore should remain overdue until explicit reset"
        )


class TestOverdueClaimedChoreNotOverdue:
    """Tests to ensure claimed chores are not marked overdue."""

    @pytest.mark.asyncio
    async def test_claimed_chore_not_marked_overdue(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: A claimed chore should NOT be marked as overdue."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        # Use a chore with at_due_date handling
        chore_id = chore_map["Overdue At Due Date"]

        # Claim the chore first
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Verify state is CLAIMED
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        state_before = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)
        assert state_before == CHORE_STATE_CLAIMED, (
            f"State should be CLAIMED after claim, got {state_before}"
        )

        # Set due date to past AFTER claiming (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Run overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify state is STILL CLAIMED (not overdue)
        kid_chore_data = coordinator.chore_manager.get_chore_data_for_kid(
            zoe_id, chore_id
        )
        state_after = kid_chore_data.get(DATA_KID_CHORE_DATA_STATE)

        assert state_after == CHORE_STATE_CLAIMED, (
            f"Claimed chore should stay CLAIMED, not become overdue. Got {state_after}"
        )


class TestIsOverdueHelper:
    """Tests for the coordinator.chore_manager.chore_is_overdue() helper method."""

    @pytest.mark.asyncio
    async def test_is_overdue_returns_true_for_overdue_state(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: chore_is_overdue() returns True when chore state is OVERDUE."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Overdue At Due Date"]

        # Set due date to past (config flow rejects past dates)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Run overdue check to mark chore as overdue
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify chore_is_overdue returns True
        result = coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id)
        assert result is True, "chore_is_overdue() should return True for OVERDUE chore"

    @pytest.mark.asyncio
    async def test_is_overdue_returns_false_for_pending_state(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: chore_is_overdue() returns False when chore state is PENDING."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        # Use a chore with future due date (won't be overdue)
        chore_id = chore_map["Reset Midnight Once"]

        # Run overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify chore_is_overdue returns False
        result = coordinator.chore_manager.chore_is_overdue(zoe_id, chore_id)
        assert result is False, (
            "chore_is_overdue() should return False for PENDING chore"
        )

    @pytest.mark.asyncio
    async def test_is_overdue_returns_false_for_nonexistent_chore(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: chore_is_overdue() returns False for non-existent chore."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]

        # Use a fake chore ID
        fake_chore_id = "nonexistent-chore-id-12345"

        # Verify chore_is_overdue returns False (not an error)
        result = coordinator.chore_manager.chore_is_overdue(zoe_id, fake_chore_id)
        assert result is False, (
            "chore_is_overdue() should return False for non-existent chore"
        )


# =============================================================================
# TEST CLASS: Pending Claim Action Tests (Phase 6)
# These tests verify what happens to claimed-but-not-approved chores at reset.
# =============================================================================


class TestPendingClaimHold:
    """Tests for approval_reset_pending_claim_action: hold_pending.

    When reset occurs, claimed chores with HOLD action should retain their claim.
    """

    @pytest.mark.asyncio
    async def test_pending_hold_retains_claim_after_reset(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: HOLD pending claim is retained after reset."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Hold"]

        # Verify chore has correct pending claim action
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_HOLD
        )

        # Claim the chore (but don't approve)
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Verify state is CLAIMED
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_CLAIMED

        # Verify has pending claim
        assert coordinator.chore_manager.chore_has_pending_claim(zoe_id, chore_id), (
            "Should have pending claim before reset"
        )

        # Trigger reset (simulate midnight reset)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify state is STILL CLAIMED (hold action keeps the claim)
        state_after = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_after == CHORE_STATE_CLAIMED, (
            f"HOLD action should retain claimed state, got {state_after}"
        )

        # Verify still has pending claim
        assert coordinator.chore_manager.chore_has_pending_claim(zoe_id, chore_id), (
            "Should still have pending claim after reset with HOLD action"
        )

    @pytest.mark.asyncio
    async def test_pending_hold_no_points_awarded(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: HOLD pending claim does NOT award points on reset."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Hold"]

        # Get points before
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_before = kid_info.get(DATA_KID_POINTS, 0)

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify points unchanged (no auto-approval)
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_after = kid_info.get(DATA_KID_POINTS, 0)

        assert points_after == points_before, (
            f"HOLD action should NOT award points. Before: {points_before}, After: {points_after}"
        )


class TestPendingClaimClear:
    """Tests for approval_reset_pending_claim_action: clear_pending.

    When reset occurs, claimed chores with CLEAR action should be reset to PENDING.
    """

    @pytest.mark.asyncio
    async def test_pending_clear_resets_to_pending(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: CLEAR pending claim resets state to PENDING."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Clear"]

        # Verify chore has correct pending claim action
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_CLEAR
        )

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Verify state is CLAIMED
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_CLAIMED

        # Set due date to past so reset will process the chore
        # (reset checks if now > due_date before processing)
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify state is PENDING (claim was cleared)
        state_after = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_after == CHORE_STATE_PENDING, (
            f"CLEAR action should reset to PENDING, got {state_after}"
        )

    @pytest.mark.asyncio
    async def test_pending_clear_removes_pending_claim(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: CLEAR pending claim removes pending claim status."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Clear"]

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Verify has pending claim before reset
        assert coordinator.chore_manager.chore_has_pending_claim(zoe_id, chore_id), (
            "Should have pending claim before reset"
        )

        # Set due date to past so reset will process the chore
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify pending claim is cleared
        assert not coordinator.chore_manager.chore_has_pending_claim(
            zoe_id, chore_id
        ), "Should NOT have pending claim after reset with CLEAR action"

    @pytest.mark.asyncio
    async def test_pending_clear_no_points_awarded(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: CLEAR pending claim does NOT award points on reset."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Clear"]

        # Get points before
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_before = kid_info.get(DATA_KID_POINTS, 0)

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Set due date to past so reset will process the chore
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify points unchanged
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_after = kid_info.get(DATA_KID_POINTS, 0)

        assert points_after == points_before, (
            f"CLEAR action should NOT award points. Before: {points_before}, After: {points_after}"
        )


class TestPendingClaimAutoApprove:
    """Tests for approval_reset_pending_claim_action: auto_approve_pending.

    When reset occurs, claimed chores with AUTO_APPROVE action should be
    automatically approved (awarding points) before reset.
    """

    @pytest.mark.asyncio
    async def test_pending_auto_approve_awards_points(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE pending claim awards points on reset."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Auto Approve"]

        # Verify chore has correct pending claim action
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION)
            == APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE
        )

        # Get chore points value
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)
        assert chore_points > 0, "Test chore should have points defined"

        # Get points before
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_before = kid_info.get(DATA_KID_POINTS, 0)

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Set due date to past so reset will process the chore
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify points awarded (auto-approval happened)
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_after = kid_info.get(DATA_KID_POINTS, 0)

        assert points_after == points_before + chore_points, (
            f"AUTO_APPROVE should award {chore_points} points. "
            f"Before: {points_before}, After: {points_after}, Expected: {points_before + chore_points}"
        )

    @pytest.mark.asyncio
    async def test_pending_auto_approve_then_resets_to_pending(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE pending claim resets to PENDING after auto-approval."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Auto Approve"]

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Verify state is CLAIMED before reset
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_CLAIMED

        # Set due date to past so reset will process the chore
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify state is PENDING after reset (auto-approval + reset)
        state_after = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_after == CHORE_STATE_PENDING, (
            f"AUTO_APPROVE should reset to PENDING after approval, got {state_after}"
        )

    @pytest.mark.asyncio
    async def test_pending_auto_approve_removes_pending_claim(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AUTO_APPROVE pending claim removes pending claim status."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Auto Approve"]

        # Claim the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")

        # Verify has pending claim before reset
        assert coordinator.chore_manager.chore_has_pending_claim(zoe_id, chore_id), (
            "Should have pending claim before reset"
        )

        # Set due date to past so reset will process the chore
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify pending claim is cleared after auto-approval and reset
        assert not coordinator.chore_manager.chore_has_pending_claim(
            zoe_id, chore_id
        ), "Should NOT have pending claim after auto-approval"


class TestPendingClaimEdgeCases:
    """Edge case tests for pending claim actions."""

    @pytest.mark.asyncio
    async def test_approved_chore_not_affected_by_pending_claim_action(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Already approved chores are not affected by pending claim action."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Hold"]

        # Claim and approve the chore normally
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify state is APPROVED
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_APPROVED

        # Verify no pending claim (already approved)
        assert not coordinator.chore_manager.chore_has_pending_claim(
            zoe_id, chore_id
        ), "Approved chore should not have pending claim"

        # Set due date to past so reset will process the chore
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # State should be PENDING after reset (normal reset behavior)
        state_after = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_after == CHORE_STATE_PENDING, (
            f"Approved chore should reset to PENDING, got {state_after}"
        )

    @pytest.mark.asyncio
    async def test_unclaimed_chore_not_affected_by_pending_claim_action(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Unclaimed chores are not affected by pending claim action settings."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        _chore_id = chore_map[
            "Pending Auto Approve"
        ]  # Keep for clarity, intentionally unused

        # Get points before (no claim, no approval)
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_before = kid_info.get(DATA_KID_POINTS, 0)

        # Don't claim - just trigger reset
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Verify points unchanged (no pending claim to auto-approve)
        kid_info = coordinator.kids_data.get(zoe_id, {})
        points_after = kid_info.get(DATA_KID_POINTS, 0)

        assert points_after == points_before, (
            f"Unclaimed chore should NOT award points on reset. "
            f"Before: {points_before}, After: {points_after}"
        )


# =============================================================================
# PHASE 7: APPLICABLE DAYS TESTS
# Tests for weekday filtering on due date calculations
# =============================================================================


class TestApplicableDays:
    """Tests for applicable_days weekday filtering.

    Applicable days limits which days of the week a chore can be completed.
    When a chore is approved with applicable_days set, the next due date
    should snap to the next applicable day rather than just advancing by frequency.

    Key behaviors:
    - Empty list = all days applicable (no filtering)
    - Weekday-only = Mon-Fri (skip Sat/Sun)
    - Weekend-only = Sat-Sun (skip Mon-Fri)
    - Specific days = only those days
    """

    @pytest.mark.asyncio
    async def test_applicable_days_loaded_from_yaml(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Applicable days are loaded correctly from YAML scenario."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        # Weekday-only chore
        weekday_id = chore_map["Weekday Only Task"]
        weekday_info = coordinator.chores_data.get(weekday_id, {})
        weekday_days = weekday_info.get(DATA_CHORE_APPLICABLE_DAYS, [])

        assert weekday_days == [0, 1, 2, 3, 4], (
            f"Weekday chore should have Mon-Fri (0-4), got {weekday_days}"
        )

        # Weekend-only chore
        weekend_id = chore_map["Weekend Only Task"]
        weekend_info = coordinator.chores_data.get(weekend_id, {})
        weekend_days = weekend_info.get(DATA_CHORE_APPLICABLE_DAYS, [])

        assert weekend_days == [5, 6], (
            f"Weekend chore should have Sat-Sun (5-6), got {weekend_days}"
        )

        # MWF chore
        mwf_id = chore_map["MWF Task"]
        mwf_info = coordinator.chores_data.get(mwf_id, {})
        mwf_days = mwf_info.get(DATA_CHORE_APPLICABLE_DAYS, [])

        assert mwf_days == [0, 2, 4], (
            f"MWF chore should have Mon/Wed/Fri (0, 2, 4), got {mwf_days}"
        )

    @pytest.mark.asyncio
    async def test_empty_applicable_days_defaults_to_all_days(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Empty/missing applicable_days means no filtering (all days valid)."""
        coordinator = scheduling_scenario.coordinator
        chore_map = scheduling_scenario.chore_ids

        # Use a chore WITHOUT applicable_days set in YAML
        # System should store empty list (meaning no filtering - all days valid)
        chore_id = chore_map["Reset Upon Completion"]
        chore_info = coordinator.chores_data.get(chore_id, {})
        applicable_days = chore_info.get(DATA_CHORE_APPLICABLE_DAYS, [])

        # Empty list means "no restriction" = all days valid
        assert applicable_days == [], (
            f"Chore without applicable_days should store empty list, got {applicable_days}"
        )

    @pytest.mark.asyncio
    async def test_applicable_days_affects_next_due_date(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Upon completion, next due date respects applicable_days."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        # Use MWF chore (Mon/Wed/Fri only)
        chore_id = chore_map["MWF Task"]

        # Claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Get the new due date
        new_due_date = get_kid_due_date(coordinator, zoe_id, chore_id)
        assert new_due_date is not None, "Should have a new due date after approval"

        # Verify the due date falls on an applicable day (Mon=0, Wed=2, Fri=4)
        applicable_weekdays = {0, 2, 4}  # Mon, Wed, Fri
        assert new_due_date.weekday() in applicable_weekdays, (
            f"MWF Task due date should fall on Mon/Wed/Fri, but got "
            f"weekday {new_due_date.weekday()} ({new_due_date})"
        )


# ============================================================================
# SECTION 8: MULTI-WEEK SCHEDULING TESTS
# Tests for biweekly and monthly frequency edge cases
# ============================================================================


class TestMultiWeekScheduling:
    """Tests for multi-week scheduling frequencies (biweekly, monthly).

    Multi-week chores have longer intervals between due dates:
    - Biweekly: 14 days between due dates
    - Monthly: ~30 days, handling month boundaries

    Uses entity state as source of truth per AGENT_TEST_CREATION_INSTRUCTIONS.md.
    """

    @pytest.mark.asyncio
    async def test_biweekly_chore_reschedules_14_days(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Biweekly chore reschedules 14 days after approval."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Biweekly Task"]

        # Get chore entity ID from dashboard helper (Rule 3: Dashboard Helper is source)
        helper_eid = "sensor.zoe_kidschores_ui_dashboard_helper"
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None, "Dashboard helper should exist"

        # Find Biweekly Task in chores list
        chores = helper_state.attributes.get("chores", [])
        biweekly_chore = next(
            (c for c in chores if c.get("name") == "Biweekly Task"), None
        )
        assert biweekly_chore is not None, "Biweekly Task should be in chores list"
        chore_eid = biweekly_chore["eid"]

        # Get initial due date from entity state
        chore_state = hass.states.get(chore_eid)
        assert chore_state is not None, "Chore entity should exist"
        initial_due_str = chore_state.attributes.get("due_date")
        assert initial_due_str is not None, "Should have initial due date"
        initial_due_date = dt_to_utc(initial_due_str)

        # Claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)
        await hass.async_block_till_done()

        # Get new due date from entity state (refreshed)
        chore_state = hass.states.get(chore_eid)
        assert chore_state is not None, "Chore entity should still exist"
        new_due_str = chore_state.attributes.get("due_date")
        assert new_due_str is not None, "Should have new due date after approval"
        new_due_date = dt_to_utc(new_due_str)
        assert new_due_date is not None, "New due date should parse"
        assert initial_due_date is not None, "Initial due date should parse"

        # Calculate the difference
        date_diff = new_due_date - initial_due_date
        expected_days = 14  # Biweekly = 14 days

        assert date_diff.days == expected_days, (
            f"Biweekly chore should reschedule {expected_days} days ahead, "
            f"but got {date_diff.days} days (from {initial_due_date} to {new_due_date})"
        )

    @pytest.mark.asyncio
    async def test_monthly_chore_reschedules_approximately_30_days(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Monthly chore reschedules approximately 30 days after approval.

        Monthly scheduling can vary slightly based on month length (28-31 days).
        We verify it's in the expected range.

        Uses entity state as source of truth per AGENT_TEST_CREATION_INSTRUCTIONS.md.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Monthly Task"]

        # Get chore entity ID from dashboard helper (Rule 3: Dashboard Helper is source)
        helper_eid = "sensor.zoe_kidschores_ui_dashboard_helper"
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None, "Dashboard helper should exist"

        # Find Monthly Task in chores list
        chores = helper_state.attributes.get("chores", [])
        monthly_chore = next(
            (c for c in chores if c.get("name") == "Monthly Task"), None
        )
        assert monthly_chore is not None, "Monthly Task should be in chores list"
        chore_eid = monthly_chore["eid"]

        # Get initial due date from entity state
        chore_state = hass.states.get(chore_eid)
        assert chore_state is not None, "Chore entity should exist"
        initial_due_str = chore_state.attributes.get("due_date")
        assert initial_due_str is not None, "Should have initial due date"
        initial_due_date = dt_to_utc(initial_due_str)

        # Claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)
        await hass.async_block_till_done()

        # Get new due date from entity state (refreshed)
        chore_state = hass.states.get(chore_eid)
        assert chore_state is not None, "Chore entity should still exist"
        new_due_str = chore_state.attributes.get("due_date")
        assert new_due_str is not None, "Should have new due date after approval"
        new_due_date = dt_to_utc(new_due_str)
        assert new_due_date is not None, "New due date should parse"
        assert initial_due_date is not None, "Initial due date should parse"

        # Calculate the difference
        date_diff = new_due_date - initial_due_date

        # Monthly adds 28-31 days, PLUS applicable_days snapping can add up to 6 more days
        # (e.g., if monthly lands on Tuesday but chore only runs on Monday, it snaps forward)
        # Total range: 28-37 days
        assert 28 <= date_diff.days <= 37, (
            f"Monthly chore should reschedule 28-37 days ahead "
            f"(28-31 base + up to 6 for applicable_days snapping), "
            f"but got {date_diff.days} days (from {initial_due_date} to {new_due_date})"
        )


# =============================================================================
# TEST CLASS: Time Boundary Crossing Scenarios
# =============================================================================


class TestTimeBoundaryCrossing:
    """Test approval reset behavior across time boundaries (midnight, due date).

    These tests verify that approval reset logic correctly handles:
    - Approval period transitions at midnight
    - Due date boundary crossing for AT_DUE_DATE_* modes
    - Period start tracking accuracy

    Migrated from legacy test_approval_reset_timing.py - behavior extraction only.
    """

    @pytest.mark.asyncio
    async def test_at_midnight_once_allows_claim_after_midnight(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_MIDNIGHT_ONCE allows new claim after midnight boundary.

        Behavior: If approval happened yesterday but period_start is today,
        the chore should be claimable again (new approval period).
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Once"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify chore has correct reset type
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_MIDNIGHT_ONCE
        )

        # Simulate: approval was yesterday, period_start is today (midnight passed)
        yesterday = (datetime.now(UTC).replace(hour=12) - timedelta(days=1)).isoformat()
        today_midnight = (
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
        )

        # Set last_approved to yesterday via kid_chore_data
        kid_data = coordinator.kids_data.setdefault(zoe_id, {})
        chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {}).setdefault(
            chore_id, {}
        )
        chore_data["last_approved"] = yesterday
        chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = today_midnight
        chore_data[DATA_KID_CHORE_DATA_STATE] = CHORE_STATE_PENDING
        coordinator._persist()

        # Approval was before period_start → not approved in current period
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        ), "Approval from yesterday should not count in today's period"

        # Should be allowed to claim (new period)
        can_claim, error_key = coordinator.chore_manager.can_claim_chore(
            zoe_id, chore_id
        )
        assert can_claim, "Should be able to claim after midnight boundary"
        assert error_key is None

    @pytest.mark.asyncio
    async def test_at_midnight_multi_period_resets_at_midnight(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_MIDNIGHT_MULTI period resets at midnight for fresh approval tracking.

        Behavior: Even with MULTI mode, the approval count resets at midnight.
        Approvals from before period_start don't count in the new period.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Midnight Multi"]

        # Simulate: approval was yesterday at 11pm, period_start is today at midnight
        yesterday_11pm = (
            datetime.now(UTC).replace(hour=23, minute=0, second=0) - timedelta(days=1)
        ).isoformat()
        today_midnight = (
            datetime.now(UTC)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .isoformat()
        )

        # Set up state
        kid_data = coordinator.kids_data.setdefault(zoe_id, {})
        chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {}).setdefault(
            chore_id, {}
        )
        chore_data["last_approved"] = yesterday_11pm
        chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = today_midnight
        chore_data[DATA_KID_CHORE_DATA_STATE] = CHORE_STATE_PENDING
        coordinator._persist()

        # Approval was before period_start → not in current period
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        ), "Approval from before midnight should not count in today's period"

        # Should be claimable (new period)
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "Should be claimable after midnight reset"

    @pytest.mark.asyncio
    async def test_at_due_date_once_allows_claim_after_due_date_passes(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_ONCE allows new claim after due date boundary.

        Behavior: If approval happened before the last due date reset,
        the chore should be claimable again (new cycle).
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Due Date Once"]

        # Simulate: approval was 3 days ago, period_start is now (due date passed)
        three_days_ago = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        now = datetime.now(UTC).isoformat()

        # Set up state
        kid_data = coordinator.kids_data.setdefault(zoe_id, {})
        chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {}).setdefault(
            chore_id, {}
        )
        chore_data["last_approved"] = three_days_ago
        chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now
        chore_data[DATA_KID_CHORE_DATA_STATE] = CHORE_STATE_PENDING
        coordinator._persist()

        # Approval was before period_start → not in current period
        assert not coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        ), "Old approval should not count after due date passed"

        # Should be claimable
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "Should be claimable after due date boundary"

    @pytest.mark.asyncio
    async def test_upon_completion_ignores_period_start_entirely(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: UPON_COMPLETION mode ignores period_start for claim decisions.

        Behavior: UPON_COMPLETION always allows re-claiming regardless of
        when the last approval was or what period_start says.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Reset Upon Completion"]

        # Claim and approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # UPON_COMPLETION should reset to PENDING immediately
        state = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING, (
            "UPON_COMPLETION should reset state to PENDING after approval"
        )

        # Should be immediately claimable again
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "UPON_COMPLETION should always allow re-claim"

    @pytest.mark.asyncio
    async def test_approval_period_boundary_exact_flip_reflects_in_sensor_state(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Approval-in-period flips exactly when period_start moves past approval time."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Midnight Once"]

        now_utc = datetime.now(UTC)
        approved_at = now_utc.isoformat()

        kid_data = coordinator.kids_data.setdefault(zoe_id, {})
        chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {}).setdefault(
            chore_id, {}
        )
        chore_data["last_approved"] = approved_at
        chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = approved_at
        chore_data[DATA_KID_CHORE_DATA_STATE] = CHORE_STATE_PENDING
        coordinator._persist()
        coordinator.async_set_updated_data(coordinator._data)
        await hass.async_block_till_done()

        assert coordinator.chore_manager.chore_is_approved_in_period(zoe_id, chore_id)

        dashboard = get_dashboard_helper(hass, "zoe")
        chore = find_chore(dashboard, "Reset Midnight Once")
        assert chore is not None
        sensor = hass.states.get(chore["eid"])
        assert sensor is not None
        assert sensor.state == CHORE_STATE_APPROVED

        period_after = (now_utc + timedelta(seconds=1)).isoformat()
        chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = period_after
        coordinator._persist()
        coordinator.async_set_updated_data(coordinator._data)
        await hass.async_block_till_done()

        assert not coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        )

        dashboard_after = get_dashboard_helper(hass, "zoe")
        chore_after = find_chore(dashboard_after, "Reset Midnight Once")
        assert chore_after is not None
        sensor_after = hass.states.get(chore_after["eid"])
        assert sensor_after is not None
        assert sensor_after.state != CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_waiting_window_transition_stays_stable_across_periodic_updates(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Waiting lock transitions waiting -> claimable -> due without drift."""
        coordinator = scheduling_scenario.coordinator
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Once"]
        now = datetime.now(UTC)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "chore_claim_lock_until_window": True,
                "due_window_offset": "2h",
                "due_date": now + timedelta(hours=5),
            },
            blocking=True,
        )
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        waiting_chore = find_chore(
            get_dashboard_helper(hass, "zoe"), "Reset Due Date Once"
        )
        assert waiting_chore is not None
        waiting_sensor = hass.states.get(waiting_chore["eid"])
        assert waiting_sensor is not None
        assert waiting_sensor.state == CHORE_STATE_WAITING
        assert waiting_sensor.attributes.get(ATTR_CAN_CLAIM) is False

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "due_date": now + timedelta(minutes=90),
            },
            blocking=True,
        )
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()

        in_window_chore = find_chore(
            get_dashboard_helper(hass, "zoe"), "Reset Due Date Once"
        )
        assert in_window_chore is not None
        in_window_sensor = hass.states.get(in_window_chore["eid"])
        assert in_window_sensor is not None
        assert in_window_sensor.state == const.CHORE_STATE_DUE
        assert in_window_sensor.attributes.get(ATTR_CAN_CLAIM) is True

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "due_date": now + timedelta(minutes=10),
            },
            blocking=True,
        )
        await coordinator.chore_manager._on_periodic_update(
            now_utc=dt_to_utc(now + timedelta(minutes=11))
        )
        await hass.async_block_till_done()

        past_due_chore = find_chore(
            get_dashboard_helper(hass, "zoe"), "Reset Due Date Once"
        )
        assert past_due_chore is not None
        past_due_sensor = hass.states.get(past_due_chore["eid"])
        assert past_due_sensor is not None
        assert past_due_sensor.state == const.CHORE_STATE_DUE


# =============================================================================
# TEST CLASS: Shared Chore Approval Reset Scenarios
# =============================================================================


@pytest.fixture
async def shared_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load shared chore scenario for multi-kid approval reset tests."""
    return await setup_from_yaml(
        hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml"
    )


class TestSharedChoreApprovalReset:
    """Test approval reset behavior for shared chores across multiple kids.

    Shared chores have different approval tracking than independent chores:
    - SHARED_ALL: All assigned kids must complete before chore is done
    - SHARED_FIRST: First kid to claim owns it, others can't claim

    Approval period tracking for shared chores is at the CHORE level,
    not the per-kid level like independent chores.
    """

    @pytest.mark.asyncio
    async def test_shared_all_midnight_once_per_kid_tracking(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: SHARED_ALL with AT_MIDNIGHT_ONCE tracks each kid independently.

        Behavior: Each kid can claim and be approved once per period.
        The chore is fully complete only when ALL kids are approved.
        """
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Clear"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify setup
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_MIDNIGHT_ONCE
        )

        # Zoë claims and gets approved
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Zoë is now approved for this period
        assert coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        ), "Zoë should be approved in current period"

        # Zoë cannot claim again (ONCE mode)
        can_claim_zoe, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert not can_claim_zoe, "Zoë should not be able to claim again (ONCE mode)"

        # Max can still claim (independent per-kid tracking for SHARED_ALL)
        can_claim_max, _ = coordinator.chore_manager.can_claim_chore(max_id, chore_id)
        assert can_claim_max, "Max should be able to claim (independent tracking)"

    @pytest.mark.asyncio
    async def test_shared_first_midnight_once_blocks_all_kids_after_first(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: SHARED_FIRST with AT_MIDNIGHT_ONCE blocks all kids after first approval.

        Behavior: Once first kid claims and is approved, NO other kid can claim
        until the next approval period (midnight reset).

        Note: This chore (Shared First Pending Hold) is only assigned to Zoë & Max.
        """
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared First Pending Hold"]
        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify setup
        assert chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == "shared_first"
        assert (
            chore_info.get(DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_MIDNIGHT_ONCE
        )

        # Max can claim before anyone has claimed
        can_claim_max_before, _ = coordinator.chore_manager.can_claim_chore(
            max_id, chore_id
        )
        assert can_claim_max_before, "Max can claim before anyone claims"

        # Zoë claims first
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Max is now blocked from claiming (shared_first - first claimer wins)
        can_claim_max, _ = coordinator.chore_manager.can_claim_chore(max_id, chore_id)
        assert not can_claim_max, "Max blocked (Zoë claimed first)"

        # Approve Zoë
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # After approval, still blocked (ONCE mode, same period)
        can_claim_max, _ = coordinator.chore_manager.can_claim_chore(max_id, chore_id)
        assert not can_claim_max, "Max still blocked (ONCE mode, same period)"

    @pytest.mark.asyncio
    async def test_shared_all_uses_chore_level_period_start(
        self,
        hass: HomeAssistant,
        shared_scenario: SetupResult,
    ) -> None:
        """Test: SHARED chores track approval period consistently across all kids.

        Behavior: For shared chores with completion_criteria='shared_all',
        when one kid completes and gets approved, the approval tracking
        should be consistent for determining period boundaries.
        """
        coordinator = shared_scenario.coordinator
        zoe_id = shared_scenario.kid_ids["Zoë"]
        max_id = shared_scenario.kid_ids["Max!"]
        chore_map = shared_scenario.chore_ids

        chore_id = chore_map["Shared All Pending Clear"]

        # Claim and approve Zoë to trigger approval tracking
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.approve_chore("parent", zoe_id, chore_id)

        # Verify Zoë is approved in current period
        zoe_approved = coordinator.chore_manager.chore_is_approved_in_period(
            zoe_id, chore_id
        )
        assert zoe_approved, "Zoë should be approved in current period"

        # For SHARED_ALL chores, Max can still complete (he hasn't yet)
        # Check Max's can_claim state (should be able to claim since it's SHARED_ALL)
        max_can_claim, _ = coordinator.chore_manager.can_claim_chore(max_id, chore_id)
        # SHARED_ALL: all kids must complete, so Max should be able to claim
        assert max_can_claim, "Max should still be able to claim SHARED_ALL chore"


class TestPendingClaimActionBehavior:
    """Test pending claim action behavior at reset boundaries.

    Covers the 3 pending_claim_action values:
    - clear_pending: Claimed chore reverts to PENDING state at reset
    - hold_pending: Claimed chore remains in CLAIMED state after reset
    - auto_approve_pending: Claimed chore is auto-approved at reset (awards points)

    These tests verify behavior when a chore is CLAIMED (not yet approved)
    and the approval reset period triggers.
    """

    @pytest.fixture
    async def scheduling_scenario(
        self, hass: HomeAssistant, mock_hass_users: dict[str, Any]
    ) -> SetupResult:
        """Load scheduling scenario with all pending claim action types."""
        return await setup_from_yaml(
            hass,
            mock_hass_users,
            "tests/scenarios/scenario_scheduling.yaml",
        )

    @pytest.mark.asyncio
    async def test_clear_pending_reverts_claimed_to_pending(
        self, hass: HomeAssistant, scheduling_scenario: SetupResult
    ) -> None:
        """Test clear_pending: claimed chore reverts to PENDING at reset."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Clear"]

        # Set due date to past so reset will trigger
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Claim but don't approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Verify chore is CLAIMED
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_CLAIMED

        # Trigger reset (simulating midnight reset for daily chores)
        # The reset method checks approval_reset_pending_claim_action
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # After reset with clear_pending, chore should be PENDING
        state_after = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_after == CHORE_STATE_PENDING, (
            "clear_pending should revert CLAIMED to PENDING at reset"
        )

    @pytest.mark.asyncio
    async def test_hold_pending_retains_claimed_after_reset(
        self, hass: HomeAssistant, scheduling_scenario: SetupResult
    ) -> None:
        """Test hold_pending: claimed chore stays CLAIMED after reset."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Hold"]

        # Set due date to past so reset would normally trigger
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Claim but don't approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Verify chore is CLAIMED
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_CLAIMED

        # Trigger reset (simulating midnight reset for daily chores)
        # The reset method checks approval_reset_pending_claim_action
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # After reset with hold_pending, chore should still be CLAIMED
        state_after = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_after == CHORE_STATE_CLAIMED, (
            "hold_pending should keep CLAIMED status after reset"
        )

    @pytest.mark.asyncio
    async def test_auto_approve_pending_approves_and_awards_points(
        self, hass: HomeAssistant, scheduling_scenario: SetupResult
    ) -> None:
        """Test auto_approve_pending: claimed chore is approved and awards points."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_map = scheduling_scenario.chore_ids

        chore_id = chore_map["Pending Auto Approve"]

        # Get initial points using existing pattern from this file
        zoe_points_before = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)

        # Get chore points for later comparison (before setting due date to past)
        chore_info = coordinator.chores_data.get(chore_id, {})
        chore_points = chore_info.get(DATA_CHORE_DEFAULT_POINTS, 0)

        # Set due date to past so reset will trigger
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Claim but don't approve
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Verify chore is CLAIMED and points unchanged
        state_before = get_kid_chore_state(coordinator, zoe_id, chore_id)
        assert state_before == CHORE_STATE_CLAIMED
        assert (
            coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0) == zoe_points_before
        )

        # Trigger reset (simulating midnight reset for daily chores)
        # The reset method checks approval_reset_pending_claim_action
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # After reset with auto_approve_pending, points should be awarded
        zoe_points_after = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)
        assert zoe_points_after == zoe_points_before + chore_points, (
            "auto_approve_pending should award points at reset"
        )


# =============================================================================
# TEST CLASS: Edge Cases - Approval Reset Types
# =============================================================================


class TestApprovalResetEdgeCases:
    """Test edge cases and error conditions for approval reset types."""

    @pytest.mark.asyncio
    async def test_at_due_date_reset_without_due_date_once(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_ONCE reset type without due date should never reset.

        Edge case: If a chore is configured with APPROVAL_RESET_AT_DUE_DATE_ONCE
        but has no due date set, the chore should never reset and can only be
        completed once ever (until manually reset or due date is added).
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]

        # Use existing chore with AT_DUE_DATE_ONCE reset type
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Once"]

        # Clear the due date using the proper service method to simulate edge case
        await coordinator.chore_manager.set_due_date(chore_id, None, kid_id=zoe_id)

        # Verify no due date is set (for INDEPENDENT chores, check per-kid due dates)
        chore_info = coordinator.chores_data.get(chore_id, {})
        per_kid_dues = chore_info.get(DATA_CHORE_PER_KID_DUE_DATES, {})
        assert per_kid_dues.get(zoe_id) is None, (
            "Chore should have no due date for this kid"
        )

        # Initial state should be pending
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_PENDING

        # Should be able to claim initially
        can_claim, _ = coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        assert can_claim, "Should be able to claim chore initially"

        # Claim and approve the chore
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
        assert get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_CLAIMED

        await coordinator.chore_manager.approve_chore("Parent", zoe_id, chore_id)

        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )

        # Trigger daily reset (this should NOT reset the chore due to no due date)
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # State should remain APPROVED (not reset to PENDING)
        assert (
            get_kid_chore_state(coordinator, zoe_id, chore_id) == CHORE_STATE_APPROVED
        )

        # Should NOT be able to claim again
        can_claim, error_key = coordinator.chore_manager.can_claim_chore(
            zoe_id, chore_id
        )
        assert not can_claim, (
            "Should not be able to claim chore again without due date reset"
        )
        assert error_key == TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED

        # Should NOT be able to approve again
        can_approve, error_key = coordinator.chore_manager.can_approve_chore(
            zoe_id, chore_id
        )
        assert not can_approve, (
            "Should not be able to approve chore again without due date reset"
        )
        assert error_key == TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED

    @pytest.mark.asyncio
    async def test_at_due_date_reset_without_due_date_multi(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: AT_DUE_DATE_MULTI reset type without due date allows multiple claims.

        Edge case: If a chore is configured with APPROVAL_RESET_AT_DUE_DATE_MULTI
        but has no due date set, the chore should allow multiple claims/approvals
        immediately (acting like UPON_COMPLETION reset type).
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]

        # Use existing chore with AT_DUE_DATE_MULTI reset type
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Multi"]

        # Clear the due date using the proper service method to simulate edge case
        await coordinator.chore_manager.set_due_date(chore_id, None, kid_id=zoe_id)

        # Verify no due date is set (for INDEPENDENT chores, check per-kid due dates)
        chore_info = coordinator.chores_data.get(chore_id, {})
        per_kid_dues = chore_info.get(DATA_CHORE_PER_KID_DUE_DATES, {})
        assert per_kid_dues.get(zoe_id) is None, (
            "Chore should have no due date for this kid"
        )

        # Should allow multiple claims/approvals even without due date
        for attempt in range(1, 4):  # Test 3 consecutive approvals
            # Should be able to claim
            can_claim, error_key = coordinator.chore_manager.can_claim_chore(
                zoe_id, chore_id
            )
            assert can_claim, (
                f"Attempt {attempt}: Should be able to claim chore (error: {error_key})"
            )

            # Claim and approve
            await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Test User")
            assert (
                get_kid_chore_state(coordinator, zoe_id, chore_id)
                == CHORE_STATE_CLAIMED
            ), f"Attempt {attempt}: Should be claimed after claim_chore"

            await coordinator.chore_manager.approve_chore("Parent", zoe_id, chore_id)

            assert (
                get_kid_chore_state(coordinator, zoe_id, chore_id)
                == CHORE_STATE_APPROVED
            )

        # After multiple approvals, trigger reset should not change behavior
        await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_now_utc())

        # Should still be able to claim again (MULTI allows multiple claims)
        can_claim, error_key = coordinator.chore_manager.can_claim_chore(
            zoe_id, chore_id
        )
        assert can_claim, (
            f"After reset: Should still be able to claim chore (error: {error_key})"
        )


# =============================================================================
# TEST CLASS: Due Window Claim Lock Behavior
# =============================================================================


class TestDueWindowClaimLockBehavior:
    """Test waiting lock transitions around due-window boundaries."""

    @pytest.mark.asyncio
    async def test_can_claim_blocks_before_window_then_allows_in_window(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Workflow path: lock blocks button claim before window, allows claim in window."""
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Once"]
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        kid_context = Context(user_id=mock_hass_users["kid1"].id)
        now = datetime.now(UTC)

        # Configure waiting lock + due window via service API (no direct data injection)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "chore_claim_lock_until_window": True,
                "due_window_offset": "2h",
                "due_date": now + timedelta(hours=6),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        dashboard_before = get_dashboard_helper(hass, "zoe")
        chore_before = find_chore(dashboard_before, "Reset Due Date Once")
        assert chore_before is not None, "Chore must exist in dashboard helper"

        chore_sensor_before = hass.states.get(chore_before["eid"])
        assert chore_sensor_before is not None
        assert chore_sensor_before.state == CHORE_STATE_WAITING
        assert chore_sensor_before.attributes.get(ATTR_CAN_CLAIM) is False
        assert chore_sensor_before.attributes.get("lock_reason") == CHORE_STATE_WAITING
        assert chore_sensor_before.attributes.get("available_at") is not None

        # Phase 5 contract: waiting is display-only (derived), not persisted
        kid_chore_data = scheduling_scenario.coordinator.kids_data[zoe_id][
            DATA_KID_CHORE_DATA
        ][chore_id]
        assert kid_chore_data.get(DATA_KID_CHORE_DATA_STATE) == CHORE_STATE_PENDING

        blocked_claim = await claim_chore(
            hass,
            "zoe",
            "Reset Due Date Once",
            kid_context,
        )
        assert blocked_claim.state_before == CHORE_STATE_WAITING
        assert blocked_claim.state_after == CHORE_STATE_WAITING
        assert blocked_claim.points_changed == 0.0

        chore_sensor_after_block = hass.states.get(chore_before["eid"])
        assert chore_sensor_after_block is not None
        assert chore_sensor_after_block.state == CHORE_STATE_WAITING

        # Move due date into active window: due in 1h with 2h window => claim now allowed
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "due_date": now + timedelta(hours=1),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        dashboard_in_window = get_dashboard_helper(hass, "zoe")
        chore_in_window = find_chore(dashboard_in_window, "Reset Due Date Once")
        assert chore_in_window is not None

        chore_sensor_in_window = hass.states.get(chore_in_window["eid"])
        assert chore_sensor_in_window is not None
        assert chore_sensor_in_window.attributes.get(ATTR_CAN_CLAIM) is True
        assert chore_sensor_in_window.attributes.get("lock_reason") is None

        allowed_claim = await claim_chore(
            hass,
            "zoe",
            "Reset Due Date Once",
            kid_context,
        )
        assert allowed_claim.success, (
            f"Claim should succeed in due window: {allowed_claim.error}"
        )

        chore_sensor_after_claim = hass.states.get(chore_in_window["eid"])
        assert chore_sensor_after_claim is not None
        assert chore_sensor_after_claim.state == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_manager_can_claim_transitions_from_waiting_to_allowed(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Manager path: can_claim_chore blocks before window and allows in window."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Once"]
        now = datetime.now(UTC)

        # Pre-window: waiting lock should block manager-level can_claim check
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "chore_claim_lock_until_window": True,
                "due_window_offset": "2h",
                "due_date": now + timedelta(hours=6),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        can_claim_pre, error_pre = coordinator.chore_manager.can_claim_chore(
            zoe_id, chore_id
        )
        assert not can_claim_pre
        assert error_pre is not None

        status_ctx_pre = coordinator.chore_manager.get_chore_status_context(
            zoe_id, chore_id
        )
        assert status_ctx_pre["state"] == CHORE_STATE_WAITING
        assert status_ctx_pre["lock_reason"] == CHORE_STATE_WAITING
        assert status_ctx_pre["available_at"] is not None

        # In-window: waiting lock clears and claim becomes allowed
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "due_date": now + timedelta(hours=1),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        can_claim_in_window, error_in_window = (
            coordinator.chore_manager.can_claim_chore(zoe_id, chore_id)
        )
        assert can_claim_in_window
        assert error_in_window is None

        status_ctx_in_window = coordinator.chore_manager.get_chore_status_context(
            zoe_id, chore_id
        )
        assert status_ctx_in_window["lock_reason"] is None
        assert status_ctx_in_window["available_at"] is None

    @pytest.mark.asyncio
    async def test_sensor_available_at_present_only_while_waiting(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Sensor contract: available_at exists only during waiting lock."""
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Once"]
        now = datetime.now(UTC)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "chore_claim_lock_until_window": True,
                "due_window_offset": "90m",
                "due_date": now + timedelta(hours=4),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        dashboard_waiting = get_dashboard_helper(hass, "zoe")
        chore_waiting = find_chore(dashboard_waiting, "Reset Due Date Once")
        assert chore_waiting is not None
        waiting_sensor = hass.states.get(chore_waiting["eid"])
        assert waiting_sensor is not None
        assert waiting_sensor.state == CHORE_STATE_WAITING
        assert waiting_sensor.attributes.get("lock_reason") == CHORE_STATE_WAITING
        assert waiting_sensor.attributes.get("available_at") is not None

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "due_date": now + timedelta(minutes=30),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        dashboard_due = get_dashboard_helper(hass, "zoe")
        chore_due = find_chore(dashboard_due, "Reset Due Date Once")
        assert chore_due is not None
        due_sensor = hass.states.get(chore_due["eid"])
        assert due_sensor is not None
        assert due_sensor.attributes.get(ATTR_CAN_CLAIM) is True
        assert due_sensor.attributes.get("lock_reason") is None
        assert due_sensor.attributes.get("available_at") is None

    @pytest.mark.asyncio
    async def test_lock_disabled_keeps_pending_without_waiting_attributes(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """When lock-until-window is disabled, future due date stays claimable."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.kid_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Due Date Once"]
        now = datetime.now(UTC)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_CHORE,
            {
                "id": chore_id,
                "chore_claim_lock_until_window": False,
                "due_window_offset": "3h",
                "due_date": now + timedelta(hours=6),
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        can_claim, error_key = coordinator.chore_manager.can_claim_chore(
            zoe_id, chore_id
        )
        assert can_claim
        assert error_key is None

        status_ctx = coordinator.chore_manager.get_chore_status_context(
            zoe_id, chore_id
        )
        assert status_ctx["state"] == CHORE_STATE_PENDING
        assert status_ctx["lock_reason"] is None
        assert status_ctx["available_at"] is None

        dashboard = get_dashboard_helper(hass, "zoe")
        chore = find_chore(dashboard, "Reset Due Date Once")
        assert chore is not None
        chore_sensor = hass.states.get(chore["eid"])
        assert chore_sensor is not None
        assert chore_sensor.state == CHORE_STATE_PENDING
        assert chore_sensor.attributes.get(ATTR_CAN_CLAIM) is True
        assert chore_sensor.attributes.get("lock_reason") is None
        assert chore_sensor.attributes.get("available_at") is None
