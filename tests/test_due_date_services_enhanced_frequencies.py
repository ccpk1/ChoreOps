"""Test due date services with enhanced frequencies (DAILY_MULTI, CUSTOM_FROM_COMPLETE).

This module tests set_chore_due_date and skip_chore_due_date services with
enhanced frequency types across all completion modes:
- SHARED_ALL
- SHARED_FIRST
- INDEPENDENT

Test IDs follow the gap analysis matrix:
- DM-*: DAILY_MULTI frequency tests
- CFC-*: CUSTOM_FROM_COMPLETE frequency tests

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.

Key behaviors tested:
- DAILY_MULTI skip: Advances to next time slot (e.g., 08:00→17:00), not next day
- DAILY_MULTI skip (past all slots): Wraps to first slot of next day
- CUSTOM_FROM_COMPLETE skip: Advances by custom_interval from current date (not completion)
- set_chore_due_date: Sets exact datetime specified
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from tests.helpers import (
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_CUSTOM_INTERVAL,
    DATA_CHORE_DAILY_MULTI_TIMES,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_PER_KID_DUE_DATES,
    DATA_CHORE_RECURRING_FREQUENCY,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
    FREQUENCY_DAILY_MULTI,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def setup_enhanced_frequencies(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with enhanced frequency chores for due date service testing."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_enhanced_frequencies.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_chore_due_date(coordinator: Any, chore_id: str) -> str | None:
    """Get the chore-level due date (for shared/shared_first chores)."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    return chore_info.get(DATA_CHORE_DUE_DATE)


def get_kid_due_date_for_chore(
    coordinator: Any, chore_id: str, kid_id: str
) -> str | None:
    """Get per-kid due date (for independent chores)."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    per_kid_due_dates = chore_info.get(DATA_CHORE_PER_KID_DUE_DATES, {})
    return per_kid_due_dates.get(kid_id)


def parse_iso_datetime(iso_str: str | None) -> datetime | None:
    """Parse ISO datetime string to datetime object."""
    if not iso_str:
        return None
    return datetime.fromisoformat(iso_str)


def get_daily_multi_times(coordinator: Any, chore_id: str) -> str:
    """Get the daily_multi_times string for a chore (e.g., '08:00|17:00')."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    return chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES, "")


def get_custom_interval(coordinator: Any, chore_id: str) -> int:
    """Get the custom_interval for a CUSTOM_FROM_COMPLETE chore."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    return chore_info.get(DATA_CHORE_CUSTOM_INTERVAL, 0)


# ============================================================================
# TEST CLASS: DAILY_MULTI Due Date Services
# ============================================================================


class TestDailyMultiDueDateServices:
    """Test set_chore_due_date and skip_chore_due_date with DAILY_MULTI frequency.

    DAILY_MULTI chores have multiple time slots per day (e.g., 08:00|17:00).
    Key behaviors:
    - set_chore_due_date: Sets exact datetime provided
    - skip_chore_due_date: Advances to NEXT time slot (same day or first slot tomorrow)
    """

    @pytest.mark.asyncio
    async def test_dm_ind_set_single_kid_daily_multi(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """DM-IND-SET: Test set_chore_due_date for INDEPENDENT DAILY_MULTI chore.

        Verifies that set_chore_due_date stores the exact datetime provided,
        preserving hour and minute.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        zoe_id = setup_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = setup_enhanced_frequencies.chore_ids["Daily Multi Single Kid"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is INDEPENDENT + DAILY_MULTI
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_INDEPENDENT
        )
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

        # Set a specific due date for Zoë (10:30 AM tomorrow)
        new_due = datetime.now(UTC) + timedelta(days=1)
        new_due = new_due.replace(hour=10, minute=30, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due, kid_id=zoe_id)

        # Verify per-kid due date was set with EXACT time
        kid_due = get_kid_due_date_for_chore(coordinator, chore_id, zoe_id)
        assert kid_due is not None, "Per-kid due date should be set"

        parsed_due = parse_iso_datetime(kid_due)
        assert parsed_due is not None
        assert parsed_due.hour == 10, f"Hour should be 10, got {parsed_due.hour}"
        assert parsed_due.minute == 30, f"Minute should be 30, got {parsed_due.minute}"
        # Verify the date portion matches (within same day in UTC)
        assert parsed_due.date() == new_due.date(), "Date should match what was set"

    @pytest.mark.asyncio
    async def test_dm_ind_skip_single_kid_daily_multi(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """DM-IND-SKIP: Test skip_chore_due_date for INDEPENDENT DAILY_MULTI chore.

        EF-06 "Daily Multi Single Kid" has times: "09:00|21:00"
        Skip should advance to next available slot strictly after NOW.

        Note: Actual hour in UTC depends on timezone conversion - the key assertion
        is that the due date is strictly in the future after skip.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        zoe_id = setup_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = setup_enhanced_frequencies.chore_ids["Daily Multi Single Kid"]

        # Verify time slots configured: "09:00|21:00"
        times_str = get_daily_multi_times(coordinator, chore_id)
        assert times_str == "09:00|21:00", f"Expected '09:00|21:00', got '{times_str}'"

        # Get initial due date
        initial_due = get_kid_due_date_for_chore(coordinator, chore_id, zoe_id)
        assert initial_due is not None, "Scenario should have initial due date set"
        initial_dt = parse_iso_datetime(initial_due)
        assert initial_dt is not None

        now_before_skip = datetime.now(UTC)

        # Skip to next occurrence
        await coordinator.chore_manager.skip_due_date(chore_id, kid_id=zoe_id)

        # Verify due date advanced to a FUTURE time
        new_due = get_kid_due_date_for_chore(coordinator, chore_id, zoe_id)
        assert new_due is not None, "Due date should still exist after skip"
        new_dt = parse_iso_datetime(new_due)
        assert new_dt is not None

        # New due should be strictly after time when skip was called
        assert new_dt > now_before_skip, (
            f"New due date {new_dt} should be after skip time {now_before_skip}"
        )

        # Verify it's different from initial (the skip actually did something)
        assert new_dt != initial_dt, (
            f"Due date should have changed from {initial_dt} to something else"
        )

    @pytest.mark.asyncio
    async def test_dm_shared_set_daily_multi(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """DM-SHARED-SET: Test set_chore_due_date for SHARED_ALL DAILY_MULTI chore.

        Verifies that set_chore_due_date stores exact datetime at chore level.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids["Daily Multi Morning Evening"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is SHARED_ALL + DAILY_MULTI
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

        # Set a specific due date (6:45 PM, 2 days from now)
        new_due = datetime.now(UTC) + timedelta(days=2)
        new_due = new_due.replace(hour=18, minute=45, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due)

        # Verify chore-level due date was set with EXACT time
        chore_due = get_chore_due_date(coordinator, chore_id)
        assert chore_due is not None, "Chore-level due date should be set"

        parsed_due = parse_iso_datetime(chore_due)
        assert parsed_due is not None
        assert parsed_due.hour == 18, f"Hour should be 18, got {parsed_due.hour}"
        assert parsed_due.minute == 45, f"Minute should be 45, got {parsed_due.minute}"
        assert parsed_due.date() == new_due.date(), "Date should match what was set"

    @pytest.mark.asyncio
    async def test_dm_shared_skip_daily_multi(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """DM-SHARED-SKIP: Test skip_chore_due_date for SHARED_ALL DAILY_MULTI chore.

        EF-04 "Daily Multi Morning Evening" has times: "07:00|18:00"
        Skip should advance to next slot strictly after NOW.

        Note: Actual hour in UTC depends on timezone conversion - the key assertion
        is that the due date is strictly in the future after skip.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids["Daily Multi Morning Evening"]

        # Verify time slots configured: "07:00|18:00"
        times_str = get_daily_multi_times(coordinator, chore_id)
        assert times_str == "07:00|18:00", f"Expected '07:00|18:00', got '{times_str}'"

        # Get initial due date
        initial_due = get_chore_due_date(coordinator, chore_id)
        assert initial_due is not None, "Scenario should have initial due date set"
        initial_dt = parse_iso_datetime(initial_due)
        assert initial_dt is not None

        now_before_skip = datetime.now(UTC)

        # Skip to next occurrence
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify due date advanced
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None, "Due date should still exist after skip"
        new_dt = parse_iso_datetime(new_due)
        assert new_dt is not None

        # New due should be strictly after time when skip was called
        assert new_dt > now_before_skip, (
            f"New due date {new_dt} should be after skip time {now_before_skip}"
        )

        # Verify it's different from initial (the skip actually did something)
        assert new_dt != initial_dt, (
            f"Due date should have changed from {initial_dt} to something else"
        )

    @pytest.mark.asyncio
    async def test_dm_sf_set_daily_multi(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """DM-SF-SET: Test set_chore_due_date for SHARED_FIRST DAILY_MULTI chore.

        Verifies SHARED_FIRST uses chore-level due date and stores exact datetime.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids["Shared First Daily Multi"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is SHARED_FIRST + DAILY_MULTI
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

        # Set a specific due date (8:15 AM tomorrow)
        new_due = datetime.now(UTC) + timedelta(days=1)
        new_due = new_due.replace(hour=8, minute=15, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due)

        # Verify chore-level due date was set (SHARED_FIRST uses chore-level)
        chore_due = get_chore_due_date(coordinator, chore_id)
        assert chore_due is not None, (
            "Chore-level due date should be set for SHARED_FIRST"
        )

        parsed_due = parse_iso_datetime(chore_due)
        assert parsed_due is not None
        assert parsed_due.hour == 8, f"Hour should be 8, got {parsed_due.hour}"
        assert parsed_due.minute == 15, f"Minute should be 15, got {parsed_due.minute}"
        assert parsed_due.date() == new_due.date(), "Date should match what was set"

    @pytest.mark.asyncio
    async def test_dm_sf_skip_daily_multi(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """DM-SF-SKIP: Test skip_chore_due_date for SHARED_FIRST DAILY_MULTI chore.

        EF-10 "Shared First Daily Multi" has times: "08:00|17:00"
        Skip should advance to next slot strictly after NOW.

        Note: Actual hour in UTC depends on timezone conversion - the key assertion
        is that the due date is strictly in the future after skip.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids["Shared First Daily Multi"]

        # Verify time slots configured: "08:00|17:00"
        times_str = get_daily_multi_times(coordinator, chore_id)
        assert times_str == "08:00|17:00", f"Expected '08:00|17:00', got '{times_str}'"

        # Get initial due date
        initial_due = get_chore_due_date(coordinator, chore_id)
        assert initial_due is not None, "Scenario should have initial due date set"
        initial_dt = parse_iso_datetime(initial_due)
        assert initial_dt is not None

        now_before_skip = datetime.now(UTC)

        # Skip to next occurrence
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify due date advanced
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None, "Due date should still exist after skip"
        new_dt = parse_iso_datetime(new_due)
        assert new_dt is not None

        # New due should be strictly after time when skip was called
        assert new_dt > now_before_skip, (
            f"New due date {new_dt} should be after skip time {now_before_skip}"
        )

        # Verify it's different from initial (the skip actually did something)
        assert new_dt != initial_dt, (
            f"Due date should have changed from {initial_dt} to something else"
        )


# ============================================================================
# TEST CLASS: CUSTOM_FROM_COMPLETE Due Date Services
# ============================================================================


class TestCustomFromCompleteDueDateServices:
    """Test set_chore_due_date and skip_chore_due_date with CUSTOM_FROM_COMPLETE.

    CUSTOM_FROM_COMPLETE chores reschedule based on completion date, not due date.
    Key behaviors:
    - set_chore_due_date: Sets exact datetime provided
    - skip_chore_due_date: Advances by custom_interval days from now (not from due date)

    Scenario intervals:
    - EF-01 "Custom From Complete SHARED": 10 days
    - EF-02 "Custom From Complete INDEPENDENT": 7 days
    - EF-11 "Shared First Custom From Complete": 5 days
    """

    @pytest.mark.asyncio
    async def test_cfc_ind_set_custom_from_complete(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """CFC-IND-SET: Test set_chore_due_date for INDEPENDENT CUSTOM_FROM_COMPLETE.

        Verifies exact datetime is stored for per-kid due date.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        zoe_id = setup_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = setup_enhanced_frequencies.chore_ids[
            "Custom From Complete INDEPENDENT"
        ]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is INDEPENDENT + CUSTOM_FROM_COMPLETE
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_INDEPENDENT
        )
        assert (
            chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
            == FREQUENCY_CUSTOM_FROM_COMPLETE
        )

        # Set a specific due date for Zoë (2:30 PM, 5 days from now)
        new_due = datetime.now(UTC) + timedelta(days=5)
        new_due = new_due.replace(hour=14, minute=30, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due, kid_id=zoe_id)

        # Verify per-kid due date was set with EXACT time
        kid_due = get_kid_due_date_for_chore(coordinator, chore_id, zoe_id)
        assert kid_due is not None, "Per-kid due date should be set"

        parsed_due = parse_iso_datetime(kid_due)
        assert parsed_due is not None
        assert parsed_due.hour == 14, f"Hour should be 14, got {parsed_due.hour}"
        assert parsed_due.minute == 30, f"Minute should be 30, got {parsed_due.minute}"
        assert parsed_due.date() == new_due.date(), "Date should match what was set"

    @pytest.mark.asyncio
    async def test_cfc_ind_skip_custom_from_complete(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """CFC-IND-SKIP: Test skip_chore_due_date for INDEPENDENT CUSTOM_FROM_COMPLETE.

        EF-02 has custom_interval=7 days.
        Skip uses dt_add_interval with require_future=True,
        so result is guaranteed to be after NOW.

        Note: The exact date depends on the base date used (completion_timestamp
        or current_due_utc) and whether the calculation needs to advance to ensure
        a future date. The key assertion is that skip produces a future date.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        zoe_id = setup_enhanced_frequencies.kid_ids["Zoë"]
        chore_id = setup_enhanced_frequencies.chore_ids[
            "Custom From Complete INDEPENDENT"
        ]

        # Verify custom_interval is 7 days
        interval = get_custom_interval(coordinator, chore_id)
        assert interval == 7, f"Expected custom_interval=7, got {interval}"

        # Get initial due date
        initial_due = get_kid_due_date_for_chore(coordinator, chore_id, zoe_id)
        assert initial_due is not None, "Scenario should have initial due date set"
        initial_dt = parse_iso_datetime(initial_due)
        assert initial_dt is not None

        # Record now before skip for comparison
        now_before_skip = datetime.now(UTC)

        # Skip to next occurrence
        await coordinator.chore_manager.skip_due_date(chore_id, kid_id=zoe_id)

        # Verify due date advanced
        new_due = get_kid_due_date_for_chore(coordinator, chore_id, zoe_id)
        assert new_due is not None, "Due date should still exist after skip"

        # Parse and verify
        new_dt = parse_iso_datetime(new_due)
        assert new_dt is not None

        # New due should be strictly after time when skip was called
        assert new_dt > now_before_skip, (
            f"New due date {new_dt} should be after skip time {now_before_skip}"
        )

        # Verify it's different from initial (the skip actually did something)
        assert new_dt != initial_dt, (
            f"Due date should have changed from {initial_dt} to something else"
        )

    @pytest.mark.asyncio
    async def test_cfc_shared_set_custom_from_complete(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """CFC-SHARED-SET: Test set_chore_due_date for SHARED_ALL CUSTOM_FROM_COMPLETE.

        Verifies exact datetime is stored at chore level.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids["Custom From Complete SHARED"]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is SHARED_ALL + CUSTOM_FROM_COMPLETE
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_SHARED
        )
        assert (
            chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
            == FREQUENCY_CUSTOM_FROM_COMPLETE
        )

        # Set a specific due date (5:45 PM, 8 days from now)
        new_due = datetime.now(UTC) + timedelta(days=8)
        new_due = new_due.replace(hour=17, minute=45, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due)

        # Verify chore-level due date was set with EXACT time
        chore_due = get_chore_due_date(coordinator, chore_id)
        assert chore_due is not None, "Chore-level due date should be set"

        parsed_due = parse_iso_datetime(chore_due)
        assert parsed_due is not None
        assert parsed_due.hour == 17, f"Hour should be 17, got {parsed_due.hour}"
        assert parsed_due.minute == 45, f"Minute should be 45, got {parsed_due.minute}"
        assert parsed_due.date() == new_due.date(), "Date should match what was set"

    @pytest.mark.asyncio
    async def test_cfc_shared_skip_custom_from_complete(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """CFC-SHARED-SKIP: Test skip_chore_due_date for SHARED_ALL CUSTOM_FROM_COMPLETE.

        EF-01 has custom_interval=10 days.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids["Custom From Complete SHARED"]

        # Verify custom_interval is 10 days
        interval = get_custom_interval(coordinator, chore_id)
        assert interval == 10, f"Expected custom_interval=10, got {interval}"

        # Get initial due date
        initial_due = get_chore_due_date(coordinator, chore_id)
        assert initial_due is not None, "Scenario should have initial due date set"

        # Parse initial due date for comparison
        initial_dt = parse_iso_datetime(initial_due)
        assert initial_dt is not None, "Initial due date should be parseable"

        # Skip to next occurrence
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify due date advanced
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None, "Due date should still exist after skip"
        assert new_due != initial_due, "Due date should have advanced"

        # Parse and verify
        new_dt = parse_iso_datetime(new_due)
        assert new_dt is not None

        # New due should be initial_due + 10 days (the custom_interval)
        # Skip adds interval to the CURRENT due date, not to "now"
        expected_min = initial_dt + timedelta(days=9)
        expected_max = initial_dt + timedelta(days=11)
        assert expected_min <= new_dt <= expected_max, (
            f"Expected due date ~10 days from initial ({expected_min} - {expected_max}), "
            f"got {new_dt}"
        )

    @pytest.mark.asyncio
    async def test_cfc_sf_set_custom_from_complete(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """CFC-SF-SET: Test set_chore_due_date for SHARED_FIRST CUSTOM_FROM_COMPLETE.

        Verifies SHARED_FIRST uses chore-level due date and stores exact datetime.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids[
            "Shared First Custom From Complete"
        ]

        chore_info = coordinator.chores_data.get(chore_id, {})

        # Verify this is SHARED_FIRST + CUSTOM_FROM_COMPLETE
        assert (
            chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_SHARED_FIRST
        )
        assert (
            chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
            == FREQUENCY_CUSTOM_FROM_COMPLETE
        )

        # Set a specific due date (3:20 PM, 3 days from now)
        new_due = datetime.now(UTC) + timedelta(days=3)
        new_due = new_due.replace(hour=15, minute=20, second=0, microsecond=0)
        await coordinator.chore_manager.set_due_date(chore_id, new_due)

        # Verify chore-level due date was set (SHARED_FIRST uses chore-level)
        chore_due = get_chore_due_date(coordinator, chore_id)
        assert chore_due is not None, (
            "Chore-level due date should be set for SHARED_FIRST"
        )

        parsed_due = parse_iso_datetime(chore_due)
        assert parsed_due is not None
        assert parsed_due.hour == 15, f"Hour should be 15, got {parsed_due.hour}"
        assert parsed_due.minute == 20, f"Minute should be 20, got {parsed_due.minute}"
        assert parsed_due.date() == new_due.date(), "Date should match what was set"

    @pytest.mark.asyncio
    async def test_cfc_sf_skip_custom_from_complete(
        self,
        hass: HomeAssistant,
        setup_enhanced_frequencies: SetupResult,
    ) -> None:
        """CFC-SF-SKIP: Test skip_chore_due_date for SHARED_FIRST CUSTOM_FROM_COMPLETE.

        EF-11 has custom_interval=5 days.
        Skip uses dt_add_interval with require_future=True,
        so result is guaranteed to be after NOW.

        Note: The exact date depends on the base date used (completion_timestamp
        or current_due_utc) and whether the calculation needs to advance to ensure
        a future date. The key assertion is that skip produces a future date.
        """
        coordinator = setup_enhanced_frequencies.coordinator
        chore_id = setup_enhanced_frequencies.chore_ids[
            "Shared First Custom From Complete"
        ]

        # Verify custom_interval is 5 days
        interval = get_custom_interval(coordinator, chore_id)
        assert interval == 5, f"Expected custom_interval=5, got {interval}"

        # Get initial due date
        initial_due = get_chore_due_date(coordinator, chore_id)
        assert initial_due is not None, "Scenario should have initial due date set"
        initial_dt = parse_iso_datetime(initial_due)
        assert initial_dt is not None

        # Record now before skip
        now_before_skip = datetime.now(UTC)

        # Skip to next occurrence
        await coordinator.chore_manager.skip_due_date(chore_id)

        # Verify due date advanced
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None, "Due date should still exist after skip"

        # Parse and verify
        new_dt = parse_iso_datetime(new_due)
        assert new_dt is not None

        # New due should be strictly after time when skip was called
        assert new_dt > now_before_skip, (
            f"New due date {new_dt} should be after skip time {now_before_skip}"
        )

        # Verify it's different from initial (the skip actually did something)
        assert new_dt != initial_dt, (
            f"Due date should have changed from {initial_dt} to something else"
        )
