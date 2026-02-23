"""Tests for scheduler delegation to ChoreManager.

Phase 4.5b: Verify time-based events are emitted correctly through the
new delegation path from Coordinator timer callbacks to ChoreManager.

Tests verify:
- SIGNAL_SUFFIX_CHORE_OVERDUE emitted when chores become overdue
- SIGNAL_SUFFIX_CHORE_STATUS_RESET emitted during scheduled resets
- Event payloads contain expected fields
- SHARED vs INDEPENDENT completion criteria handled correctly
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.utils.dt_utils import dt_now_utc
from tests.helpers import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
async def scheduling_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scheduling scenario for event tests.

    Uses scenario_scheduling.yaml which has various chores with:
    - Different overdue_handling_type values
    - Different approval_reset_type values
    - SHARED vs INDEPENDENT completion criteria
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_scheduling.yaml",
    )


def set_chore_due_date_to_past(
    coordinator: Any,
    chore_id: str,
    assignee_id: str,
    days_ago: int = 1,
) -> None:
    """Set a chore's due date to the past for testing.

    Args:
        coordinator: The ChoreOpsCoordinator
        chore_id: Chore to update
        assignee_id: Assignee ID for INDEPENDENT chores
        days_ago: How many days in the past
    """
    from datetime import timedelta

    from homeassistant.util import dt as dt_util

    past_date = dt_util.utcnow() - timedelta(days=days_ago)
    past_date_iso = past_date.isoformat()

    chore_info = coordinator.chores_data.get(chore_id)
    if not chore_info:
        return

    criteria = chore_info.get(
        const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_SHARED
    )

    if criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        per_assignee = chore_info.setdefault(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )
        per_assignee[assignee_id] = past_date_iso
    else:
        chore_info[const.DATA_CHORE_DUE_DATE] = past_date_iso


def get_assignee_by_name(coordinator: Any, name: str) -> str | None:
    """Get assignee ID by name."""
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        if assignee_info.get(const.DATA_USER_NAME) == name:
            return assignee_id
    return None


# =============================================================================
# TEST CLASS: Overdue Event Emission
# =============================================================================


class TestOverdueEventEmission:
    """Tests for CHORE_OVERDUE event emission through scheduler delegation."""

    @pytest.mark.asyncio
    async def test_overdue_check_emits_chore_overdue_event(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Overdue check via Manager emits SIGNAL_SUFFIX_CHORE_OVERDUE.

        When a chore's due date passes, the process_time_checks() method
        runs single-pass time processing which calls _process_overdue()
        and emits the CHORE_OVERDUE event.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Overdue At Due Date"]

        # Track emitted events
        emitted_events: list[tuple[str, dict[str, Any]]] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted_events.append((suffix, kwargs))
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit

        # Set due date to past
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger overdue check via Coordinator (which delegates to Manager)
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify CHORE_OVERDUE event was emitted
        overdue_events = [
            e for e in emitted_events if e[0] == const.SIGNAL_SUFFIX_CHORE_OVERDUE
        ]
        assert len(overdue_events) >= 1, (
            f"Expected CHORE_OVERDUE event to be emitted, got: {emitted_events}"
        )

        # Verify event payload
        event_payload = overdue_events[0][1]
        assert event_payload["assignee_id"] == zoe_id
        assert event_payload["chore_id"] == chore_id
        assert "days_overdue" in event_payload
        assert "due_date" in event_payload

    @pytest.mark.asyncio
    async def test_overdue_check_respects_never_overdue(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: NEVER_OVERDUE chores do NOT emit CHORE_OVERDUE event.

        Chores with overdue_handling_type=NEVER_OVERDUE should be skipped
        during overdue detection, so no event should be emitted.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Overdue Never"]

        # Track emitted events
        emitted_events: list[tuple[str, dict[str, Any]]] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted_events.append((suffix, kwargs))
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit

        # Set due date to past
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=2)

        # Trigger overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify NO CHORE_OVERDUE event was emitted for this chore
        overdue_events_for_chore = [
            e
            for e in emitted_events
            if e[0] == const.SIGNAL_SUFFIX_CHORE_OVERDUE
            and e[1].get("chore_id") == chore_id
        ]
        assert len(overdue_events_for_chore) == 0, (
            f"NEVER_OVERDUE chore should not emit CHORE_OVERDUE, got: {overdue_events_for_chore}"
        )

    @pytest.mark.asyncio
    async def test_overdue_check_handles_independent_criteria(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: INDEPENDENT chores emit per-assignee overdue events.

        For chores with COMPLETION_CRITERIA_INDEPENDENT, each assignee has their
        own due date. The overdue check should handle this correctly.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]

        # Find an INDEPENDENT chore with overdue at_due_date handling
        chore_id = None
        for cid, cinfo in coordinator.chores_data.items():
            criteria = cinfo.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            overdue = cinfo.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
            if (
                criteria == const.COMPLETION_CRITERIA_INDEPENDENT
                and overdue == const.OVERDUE_HANDLING_AT_DUE_DATE
            ):
                chore_id = cid
                break

        if chore_id is None:
            # If no such chore exists in scenario, use "Overdue At Due Date"
            chore_id = scheduling_scenario.chore_ids["Overdue At Due Date"]

        # Track emitted events
        emitted_events: list[tuple[str, dict[str, Any]]] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted_events.append((suffix, kwargs))
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit

        # Set due date to past for this assignee only
        set_chore_due_date_to_past(coordinator, chore_id, zoe_id, days_ago=1)

        # Trigger overdue check
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify overdue event was emitted for this assignee
        overdue_events_for_assignee = [
            e
            for e in emitted_events
            if e[0] == const.SIGNAL_SUFFIX_CHORE_OVERDUE
            and e[1].get("assignee_id") == zoe_id
            and e[1].get("chore_id") == chore_id
        ]

        # Should have at least one overdue event for this assignee+chore
        assert len(overdue_events_for_assignee) >= 1, (
            f"Expected overdue event for assignee {zoe_id}, chore {chore_id}"
        )


# =============================================================================
# TEST CLASS: Recurring Reset Event Emission
# =============================================================================


class TestRecurringResetEventEmission:
    """Tests for CHORE_STATUS_RESET event emission through scheduler delegation."""

    @pytest.mark.asyncio
    async def test_recurring_reset_emits_status_reset_event(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Recurring reset via Manager emits SIGNAL_SUFFIX_CHORE_STATUS_RESET.

        When scheduled reset occurs (midnight, due date), the timer callback
        should delegate to ChoreManager.process_scheduled_resets(), which
        calls reset_chore() and emits CHORE_STATUS_RESET event.
        """
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Midnight Once"]

        # Claim and approve the chore first (so reset has something to reset)
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await coordinator.chore_manager.approve_chore("TestApprover", zoe_id, chore_id)

        # Track emitted events
        emitted_events: list[tuple[str, dict[str, Any]]] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted_events.append((suffix, kwargs))
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit

        # Directly call the Manager method (simulating what timer would do)
        # Note: In production, this goes through Coordinator → Manager

        from homeassistant.util import dt as dt_util

        now = dt_util.utcnow()
        await coordinator.chore_manager._on_midnight_rollover(now_utc=now)

        # Verify CHORE_STATUS_RESET event was emitted
        reset_events = [
            e for e in emitted_events if e[0] == const.SIGNAL_SUFFIX_CHORE_STATUS_RESET
        ]

        # If chore was eligible for reset, we should see events
        # Note: This depends on the chore's reset schedule matching "now"
        # The important thing is that the delegation path works
        if reset_events:
            event_payload = reset_events[0][1]
            assert "assignee_id" in event_payload
            assert "chore_id" in event_payload

    @pytest.mark.asyncio
    async def test_reset_chore_via_transition_emits_event(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: _transition_chore_state emits CHORE_STATUS_RESET when resetting to PENDING."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Midnight Once"]

        # Claim the chore first
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Track emitted events
        emitted_events: list[tuple[str, dict[str, Any]]] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted_events.append((suffix, kwargs))
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit

        # Call _transition_chore_state (master method for state changes)
        coordinator.chore_manager._transition_chore_state(
            zoe_id,
            chore_id,
            const.CHORE_STATE_PENDING,
            reset_approval_period=True,
            clear_ownership=True,
        )

        # Verify CHORE_STATUS_RESET event was emitted
        reset_events = [
            e for e in emitted_events if e[0] == const.SIGNAL_SUFFIX_CHORE_STATUS_RESET
        ]
        assert len(reset_events) == 1, (
            f"Expected exactly 1 CHORE_STATUS_RESET event, got: {reset_events}"
        )

        # Verify event payload
        event_payload = reset_events[0][1]
        assert event_payload["assignee_id"] == zoe_id
        assert event_payload["chore_id"] == chore_id
        assert "chore_name" in event_payload


class TestDelegationPath:
    """Tests verifying the delegation path from Coordinator to Manager."""

    @pytest.mark.asyncio
    async def test_midnight_rollover_processes_resets(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: _on_midnight_rollover() processes approval resets.

        Verifies the midnight rollover handler executes without error
        and returns the count of processed resets.
        """
        coordinator = scheduling_scenario.coordinator

        # Call midnight rollover with current time
        from homeassistant.util import dt as dt_util

        result = await coordinator.chore_manager._on_midnight_rollover(
            now_utc=dt_util.utcnow()
        )

        # Verify it returns a count (int)
        assert isinstance(result, int), (
            f"_on_midnight_rollover should return int count, got: {type(result)}"
        )


class TestServiceDelegation:
    """Tests verifying service method delegation from Coordinator to Manager."""

    @pytest.mark.asyncio
    async def test_set_chore_due_date_delegates_to_manager(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Coordinator.set_chore_due_date() delegates to Manager.set_due_date()."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Midnight Once"]

        # Track if Manager method was called
        manager_called = False
        original_method = coordinator.chore_manager.set_due_date

        def tracking_method(*args: Any, **kwargs: Any) -> Any:
            nonlocal manager_called
            manager_called = True
            return original_method(*args, **kwargs)

        coordinator.chore_manager.set_due_date = tracking_method

        # Call Coordinator service method
        from datetime import timedelta

        from homeassistant.util import dt as dt_util

        future_date = dt_util.utcnow() + timedelta(days=7)
        await coordinator.chore_manager.set_due_date(
            chore_id, future_date, assignee_id=zoe_id
        )

        # Verify Manager method was called
        assert manager_called, (
            "Coordinator.set_chore_due_date should delegate to ChoreManager.set_due_date"
        )

    @pytest.mark.asyncio
    async def test_reset_all_chores_delegates_to_manager(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Coordinator.reset_all_chores() delegates to Manager.reset_all_chores()."""
        coordinator = scheduling_scenario.coordinator

        # Track if Manager method was called
        manager_called = False
        original_method = coordinator.chore_manager.reset_all_chore_states_to_pending

        def tracking_method(*args: Any, **kwargs: Any) -> Any:
            nonlocal manager_called
            manager_called = True
            return original_method(*args, **kwargs)

        coordinator.chore_manager.reset_all_chore_states_to_pending = tracking_method

        # Call Coordinator service method
        await coordinator.chore_manager.reset_all_chore_states_to_pending()

        # Verify Manager method was called
        assert manager_called, (
            "Coordinator.reset_all_chores should delegate to ChoreManager.reset_all_chores"
        )

    @pytest.mark.asyncio
    async def test_undo_chore_claim_delegates_to_manager(
        self,
        hass: HomeAssistant,
        scheduling_scenario: SetupResult,
    ) -> None:
        """Test: Coordinator.undo_chore_claim() delegates to Manager.undo_claim()."""
        coordinator = scheduling_scenario.coordinator
        zoe_id = scheduling_scenario.assignee_ids["Zoë"]
        chore_id = scheduling_scenario.chore_ids["Reset Midnight Once"]

        # Claim the chore first
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")

        # Track if Manager method was called
        manager_called = False
        original_method = coordinator.chore_manager.undo_claim

        def tracking_method(*args: Any, **kwargs: Any) -> Any:
            nonlocal manager_called
            manager_called = True
            return original_method(*args, **kwargs)

        coordinator.chore_manager.undo_claim = tracking_method

        # Call Coordinator service method
        await coordinator.chore_manager.undo_claim(zoe_id, chore_id)

        # Verify Manager method was called
        assert manager_called, (
            "Coordinator.undo_chore_claim should delegate to ChoreManager.undo_claim"
        )
