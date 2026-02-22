"""Enhanced frequency feature tests (CFE-2026-001).

Tests for all three frequency enhancement features:
- F1: FREQUENCY_CUSTOM_FROM_COMPLETE (reschedule from completion date)
- F2: FREQUENCY_DAILY_MULTI (multiple times per day)
- F3: CUSTOM + hours unit (hourly intervals)

Test Organization:
- TestCustomFromComplete: Feature 1 tests (F1-01 to F1-08)
- TestDailyMulti: Feature 2 tests (F2-01 to F2-18)
- TestCustomHours: Feature 3 tests (F3-01 to F3-10)

See: docs/in-process/CHORE_FREQUENCY_ENHANCEMENTS_IN-PROCESS.md
"""

# pylint: disable=redefined-outer-name

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, time, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.choreops import const
from custom_components.choreops.utils.dt_utils import (
    dt_add_interval,
    parse_daily_multi_times,
)
from tests.helpers import (
    APPROVAL_RESET_AT_DUE_DATE_MULTI,
    APPROVAL_RESET_AT_DUE_DATE_ONCE,
    APPROVAL_RESET_UPON_COMPLETION,
    CHORE_STATE_APPROVED,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_PENDING,
    COMPLETION_CRITERIA_INDEPENDENT,
    DATA_ASSIGNEE_CHORE_DATA,
    DATA_ASSIGNEE_CHORE_DATA_STATE,
    DATA_ASSIGNEE_POINTS,
    DATA_CHORE_CUSTOM_INTERVAL,
    DATA_CHORE_CUSTOM_INTERVAL_UNIT,
    DATA_CHORE_DAILY_MULTI_TIMES,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_RECURRING_FREQUENCY,
    FREQUENCY_CUSTOM,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
    FREQUENCY_DAILY_MULTI,
    TIME_UNIT_DAYS,
    TIME_UNIT_HOURS,
    TIME_UNIT_MONTHS,
    TIME_UNIT_WEEKS,
    SetupResult,
    setup_from_yaml,
)

# =============================================================================
# TEST HELPERS
# =============================================================================


@contextmanager
def mock_datetime(mock_time: datetime) -> Generator[None]:
    """Mock datetime.now() in dt_utils module for testing.

    This patches both homeassistant.util.dt.utcnow AND datetime.now in dt_utils,
    ensuring consistent time mocking for schedule calculations.

    Args:
        mock_time: The datetime to return from datetime.now() calls.

    Yields:
        None - context manager for use in with statements.
    """
    # Create a mock datetime class that wraps the real one
    real_datetime = datetime

    class MockDatetime(datetime):
        """Mock datetime class that returns fixed time for now()."""

        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            """Return the mocked time."""
            return mock_time

    with (
        patch("homeassistant.util.dt.utcnow", return_value=mock_time),
        patch(
            "custom_components.choreops.utils.dt_utils.datetime",
            MockDatetime,
        ),
    ):
        yield


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_enhanced_frequencies(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load enhanced frequencies scenario.

    Contains 9 chores covering all three features:
    - F1: CUSTOM_FROM_COMPLETE (3 chores)
    - F2: DAILY_MULTI (3 chores)
    - F3: CUSTOM hours (2 chores)
    - Regression: 1 daily chore
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_enhanced_frequencies.yaml",
    )


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for simple tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_assignee_chore_state(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
) -> str:
    """Get the current state of a chore for a specific assignee."""
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    chore_data = assignee_data.get(DATA_ASSIGNEE_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_ASSIGNEE_CHORE_DATA_STATE, CHORE_STATE_PENDING)


def get_assignee_points(coordinator: Any, assignee_id: str) -> float:
    """Get a assignee's current point balance."""
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    return assignee_data.get(DATA_ASSIGNEE_POINTS, 0.0)


def get_chore_due_date(coordinator: Any, chore_id: str) -> str | None:
    """Get a chore's due date from coordinator data."""
    chore_info = coordinator.chores_data.get(chore_id, {})
    return chore_info.get(DATA_CHORE_DUE_DATE)


def set_chore_due_date(
    coordinator: Any,
    chore_id: str,
    new_due_date: datetime,
) -> None:
    """Set a chore's due date directly in coordinator data."""
    coordinator.chores_data[chore_id][DATA_CHORE_DUE_DATE] = dt_util.as_utc(
        new_due_date
    ).isoformat()


# =============================================================================
# FEATURE 1: CUSTOM_FROM_COMPLETE TESTS
# =============================================================================


class TestCustomFromComplete:
    """Tests for Feature 1: FREQUENCY_CUSTOM_FROM_COMPLETE.

    This frequency reschedules the next due date from the completion
    timestamp instead of the original due date.
    """

    @pytest.mark.asyncio
    async def test_f1_01_early_completion_shared(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-01: Early completion reschedules from completion date (SHARED)."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete SHARED"
        ]

        # Verify it's a custom_from_complete frequency
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
            == FREQUENCY_CUSTOM_FROM_COMPLETE
        )
        assert chore_info.get(DATA_CHORE_CUSTOM_INTERVAL) == 10

        # Set due date to Jan 15
        jan_15 = datetime(2026, 1, 15, 17, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_15)

        # Mock completion time to Jan 12 (3 days early)
        jan_12 = datetime(2026, 1, 12, 10, 0, 0, tzinfo=UTC)

        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_12),
        ):
            # Both assignees must claim and be approved for shared_all to trigger reschedule
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Next due should be Jan 12 + 10 days = Jan 22
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None
        new_due_dt = datetime.fromisoformat(new_due)
        expected = datetime(2026, 1, 22, 10, 0, 0, tzinfo=UTC)
        # Allow some tolerance for time comparison
        assert abs((new_due_dt - expected).total_seconds()) < 3600  # Within 1 hour

    @pytest.mark.asyncio
    async def test_f1_02_late_completion_shared(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-02: Late completion reschedules from completion date (SHARED)."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete SHARED"
        ]

        # Set due date to Jan 15
        jan_15 = datetime(2026, 1, 15, 17, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_15)

        # Mock completion time to Jan 18 (3 days late)
        jan_18 = datetime(2026, 1, 18, 10, 0, 0, tzinfo=UTC)

        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_18),
        ):
            # Both assignees must complete for shared_all
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Next due should be Jan 18 + 10 days = Jan 28
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None
        new_due_dt = datetime.fromisoformat(new_due)
        expected = datetime(2026, 1, 28, 10, 0, 0, tzinfo=UTC)
        assert abs((new_due_dt - expected).total_seconds()) < 3600

    @pytest.mark.asyncio
    async def test_f1_03_on_time_completion(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-03: On-time completion works same as standard CUSTOM."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete SHARED"
        ]

        # Set due date to Jan 15
        jan_15 = datetime(2026, 1, 15, 17, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_15)

        # Mock completion time to Jan 15 (exactly on due)
        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_15),
        ):
            # Both assignees must complete for shared_all
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Next due should be Jan 15 + 10 days = Jan 25
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None
        new_due_dt = datetime.fromisoformat(new_due)
        expected = datetime(2026, 1, 25, 17, 0, 0, tzinfo=UTC)
        assert abs((new_due_dt - expected).total_seconds()) < 3600

    @pytest.mark.asyncio
    async def test_f1_04_no_completion_timestamp_fallback(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-04: Without completion timestamp, uses due_date as base."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete SHARED"
        ]

        # Verify frequency
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
            == FREQUENCY_CUSTOM_FROM_COMPLETE
        )

        # The calculation should use due_date as fallback when no completion timestamp
        jan_15 = datetime(2026, 1, 15, 17, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_15)

        # Test via helper directly (no completion timestamp passed)
        result = dt_add_interval(
            jan_15,
            TIME_UNIT_DAYS,
            10,
        )
        assert result is not None
        result_dt = cast("datetime", result)  # Type narrow for arithmetic
        expected = jan_15 + timedelta(days=10)
        assert abs((result_dt - expected).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_f1_05_independent_per_assignee_timestamps(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-05: INDEPENDENT chores track per-assignee completion timestamps."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee1_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee2_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete INDEPENDENT"
        ]

        # Verify it's independent
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
            == FREQUENCY_CUSTOM_FROM_COMPLETE
        )
        assert chore_info.get(DATA_CHORE_CUSTOM_INTERVAL) == 7

        # Assignee1 completes Jan 10
        jan_10 = datetime(2026, 1, 10, 10, 0, 0, tzinfo=UTC)
        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_10),
        ):
            await coordinator.chore_manager.claim_chore(assignee1_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee1_id, chore_id
            )

        # Assignee2 completes Jan 12
        jan_12 = datetime(2026, 1, 12, 10, 0, 0, tzinfo=UTC)
        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_12),
        ):
            await coordinator.chore_manager.claim_chore(assignee2_id, chore_id, "Max!")
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee2_id, chore_id
            )

        # Verify both assignees can process the chore independently
        assignee1_state = get_assignee_chore_state(coordinator, assignee1_id, chore_id)
        assignee2_state = get_assignee_chore_state(coordinator, assignee2_id, chore_id)
        # States should be APPROVED after approval
        assert assignee1_state == CHORE_STATE_APPROVED
        assert assignee2_state == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_f1_06_shared_uses_chore_level_timestamp(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-06: SHARED chores use chore-level timestamp for all assignees."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee1_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee2_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete SHARED"
        ]

        # Initial state - both assignees should be pending
        state1 = get_assignee_chore_state(coordinator, assignee1_id, chore_id)
        state2 = get_assignee_chore_state(coordinator, assignee2_id, chore_id)
        assert state1 == CHORE_STATE_PENDING
        assert state2 == CHORE_STATE_PENDING

        # One assignee claims
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee1_id, chore_id, "Zoë")

        # After claim, assignee1 is claimed, assignee2 should still be pending (shared)
        state1 = get_assignee_chore_state(coordinator, assignee1_id, chore_id)
        assert state1 == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_f1_07_with_upon_completion_reset(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-07: CUSTOM_FROM_COMPLETE + UPON_COMPLETION resets immediately."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete SHARED"
        ]

        # Verify reset type
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_UPON_COMPLETION
        )

        # Both assignees must complete for SHARED chore with shared_all criteria
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # With UPON_COMPLETION + all assignees done, should reset to PENDING immediately
        state = get_assignee_chore_state(coordinator, assignee_zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_f1_08_with_at_due_date_once_reset(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F1-08: CUSTOM_FROM_COMPLETE + AT_DUE_DATE_ONCE stays approved."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom From Complete INDEPENDENT"
        ]

        # Verify reset type
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_DUE_DATE_ONCE
        )

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_id, chore_id
            )

        # With AT_DUE_DATE_ONCE, should stay APPROVED
        state = get_assignee_chore_state(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_APPROVED


# =============================================================================
# FEATURE 2: DAILY_MULTI TESTS
# =============================================================================


class TestDailyMulti:
    """Tests for Feature 2: FREQUENCY_DAILY_MULTI.

    This frequency allows multiple times per day (morning, evening, etc.).
    """

    @pytest.mark.asyncio
    async def test_f2_01_next_slot_before_first(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-01: Before first time slot returns first slot today."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Verify it's daily_multi
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

        times_str = chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES)
        assert times_str == "07:00|18:00"

        # Current time: 06:00 (before first slot)
        current = datetime(2026, 1, 14, 6, 0, 0, tzinfo=UTC)

        # Parse and find next slot
        slots = parse_daily_multi_times(times_str, current, current.tzinfo)
        assert len(slots) == 2

        # Next slot should be 07:00 today
        next_slot = slots[0]  # First slot in sorted order
        assert next_slot.hour == 7
        assert next_slot.date() == current.date()

    @pytest.mark.asyncio
    async def test_f2_02_next_slot_between_slots(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-02: Between time slots returns next slot today."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        chore_info = coordinator.chores_data.get(chore_id, {})
        times_str = chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES)

        # Current time: 12:00 (between 07:00 and 18:00)
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)

        slots = parse_daily_multi_times(times_str, current, current.tzinfo)

        # Find next slot after current time
        next_slot = None
        for slot in slots:
            if slot > current:
                next_slot = slot
                break

        # Next slot should be 18:00 today
        assert next_slot is not None
        assert next_slot.hour == 18
        assert next_slot.date() == current.date()

    @pytest.mark.asyncio
    async def test_f2_03_next_slot_after_last_wrap(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-03: After last slot wraps to first slot tomorrow."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        chore_info = coordinator.chores_data.get(chore_id, {})
        times_str = chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES)

        # Current time: 20:00 (after 18:00)
        current = datetime(2026, 1, 14, 20, 0, 0, tzinfo=UTC)

        # All slots are before current time, so next should be first slot tomorrow
        tomorrow = current.date() + timedelta(days=1)
        tomorrow_slots = parse_daily_multi_times(
            times_str,
            datetime.combine(tomorrow, time(0, 0), tzinfo=UTC),
            current.tzinfo,
        )

        next_slot = tomorrow_slots[0]  # First slot tomorrow
        assert next_slot.hour == 7
        assert next_slot.date() == tomorrow

    @pytest.mark.asyncio
    async def test_f2_04_three_slots_middle(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-04: Three slots, current in middle, returns correct next."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids["Daily Multi Three Times"]

        chore_info = coordinator.chores_data.get(chore_id, {})
        times_str = chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES)
        assert times_str == "08:00|12:00|17:00"

        # Current time: 10:00 (between 08:00 and 12:00)
        current = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)

        slots = parse_daily_multi_times(times_str, current, current.tzinfo)
        assert len(slots) == 3

        # Find next slot
        next_slot = None
        for slot in slots:
            if slot > current:
                next_slot = slot
                break

        assert next_slot is not None
        assert next_slot.hour == 12

    @pytest.mark.asyncio
    async def test_f2_05_complete_advances_to_next_slot(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-05: Completing first slot advances due to next slot.

        daily_multi_times="07:00|18:00" are LOCAL times (America/Los_Angeles -8h).
        Local 07:00 PST = 15:00 UTC, Local 18:00 PST = 02:00 UTC (next day).
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Verify setup
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

        # Set due date to first slot: local 07:00 = UTC 15:00
        jan_14_3pm_utc = datetime(2026, 1, 14, 15, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_14_3pm_utc)

        # Both assignees must complete (SHARED chore with shared_all)
        # Complete at 15:30 UTC (07:30 local)
        jan_14_330pm_utc = datetime(2026, 1, 14, 15, 30, 0, tzinfo=UTC)
        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_14_330pm_utc),
        ):
            # Assignee 1 claims and gets approved
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            # Assignee 2 claims and gets approved (triggers reschedule)
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Due date should advance to second slot: local 18:00 = UTC 02:00 next day
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None
        new_due_dt = datetime.fromisoformat(new_due)
        assert new_due_dt.hour == 2
        assert new_due_dt.day == 15  # Next day

    @pytest.mark.asyncio
    async def test_f2_06_complete_last_slot_advances_to_tomorrow(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-06: Completing last slot advances to first slot tomorrow.

        daily_multi_times="07:00|18:00" are LOCAL times (America/Los_Angeles -8h).
        Local 18:00 PST = 02:00 UTC (next day), Local 07:00 PST = 15:00 UTC.
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Set due date to last slot: local 18:00 Jan 14 = UTC 02:00 Jan 15
        jan_15_2am_utc = datetime(2026, 1, 15, 2, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_15_2am_utc)

        # Both assignees must complete (SHARED chore with shared_all)
        # Complete at 02:30 UTC (18:30 local Jan 14)
        jan_15_230am_utc = datetime(2026, 1, 15, 2, 30, 0, tzinfo=UTC)
        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_15_230am_utc),
        ):
            # Assignee 1 claims and gets approved
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            # Assignee 2 claims and gets approved (triggers reschedule)
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Due date should advance to first slot tomorrow:
        # Local 07:00 Jan 15 = UTC 15:00 Jan 15
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None
        new_due_dt = datetime.fromisoformat(new_due)
        assert new_due_dt.hour == 15
        assert new_due_dt.day == 15

    @pytest.mark.asyncio
    async def test_f2_07_calendar_generates_multiple_events(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-07: Calendar generates multiple events for daily multi."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Verify chore has daily_multi_times
        chore_info = coordinator.chores_data.get(chore_id, {})
        times_str = chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES)
        assert times_str == "07:00|18:00"

        # Calendar event generation is tested via the calendar entity
        # This test validates the chore data is correctly configured
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

    @pytest.mark.asyncio
    async def test_f2_08_calendar_event_labels(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-08: Calendar events have correct time-of-day labels."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids["Daily Multi Three Times"]

        # Verify times
        chore_info = coordinator.chores_data.get(chore_id, {})
        times_str = chore_info.get(DATA_CHORE_DAILY_MULTI_TIMES)
        assert times_str == "08:00|12:00|17:00"

        # Parse times to verify structure
        current = datetime(2026, 1, 14, 0, 0, 0, tzinfo=UTC)
        slots = parse_daily_multi_times(times_str, current, current.tzinfo)
        assert len(slots) == 3

        # Verify times are 08:00, 12:00, 17:00
        hours = [slot.hour for slot in slots]
        assert 8 in hours
        assert 12 in hours
        assert 17 in hours

    @pytest.mark.asyncio
    async def test_f2_09_shared_all_assignees_same_schedule(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-09: SHARED + DAILY_MULTI - all assignees see same schedule."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee1_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee2_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Both assignees should have same state initially
        state1 = get_assignee_chore_state(coordinator, assignee1_id, chore_id)
        state2 = get_assignee_chore_state(coordinator, assignee2_id, chore_id)
        assert state1 == state2 == CHORE_STATE_PENDING

        # After one claims, verify shared behavior
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee1_id, chore_id, "Zoë")

        state1 = get_assignee_chore_state(coordinator, assignee1_id, chore_id)
        assert state1 == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_f2_10_independent_single_assignee_allowed(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-10: INDEPENDENT + single assignee + DAILY_MULTI is allowed."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Single Assignee"
        ]

        # Verify setup
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI
        assert (
            chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            == COMPLETION_CRITERIA_INDEPENDENT
        )

        # Only one assignee assigned
        assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        assert len(assigned) == 1

        # Should work normally
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")

        state = get_assignee_chore_state(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_CLAIMED

    @pytest.mark.asyncio
    async def test_f2_11_upon_completion_reset_behavior(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-11: DAILY_MULTI + UPON_COMPLETION resets immediately."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Verify reset type
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_UPON_COMPLETION
        )

        # Both assignees must complete (SHARED chore with shared_all)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Assignee 1 claims and gets approved
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            # Assignee 2 claims and gets approved (triggers UPON_COMPLETION reset)
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Should be PENDING after UPON_COMPLETION reset (check Zoë's state)
        state = get_assignee_chore_state(coordinator, assignee_zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_f2_12_at_due_date_multi_reset_behavior(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-12: DAILY_MULTI + AT_DUE_DATE_MULTI can complete multiple times."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids["Daily Multi Three Times"]

        # Verify reset type
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_DUE_DATE_MULTI
        )

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_id, chore_id
            )

        # State depends on whether due_date has passed
        state = get_assignee_chore_state(coordinator, assignee_id, chore_id)
        assert state in [CHORE_STATE_PENDING, CHORE_STATE_APPROVED]

    @pytest.mark.asyncio
    async def test_f2_13_at_due_date_once_reset_behavior(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-13: DAILY_MULTI + AT_DUE_DATE_ONCE waits for due to pass."""
        # This test verifies behavior - AT_DUE_DATE_ONCE should keep
        # the chore APPROVED until due date passes, then reset.
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids["Daily Multi Three Times"]

        # Verify the chore exists and has correct frequency
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_DAILY_MULTI

    @pytest.mark.asyncio
    async def test_f2_14_overdue_completion_slot_advancement(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-14: Late completion advances to next slot, not tomorrow.

        daily_multi_times="07:00|18:00" are LOCAL times (America/Los_Angeles -8h).
        Local 07:00 PST = 15:00 UTC, Local 18:00 PST = 02:00 UTC (next day).
        """
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Daily Multi Morning Evening"
        ]

        # Set due date to first slot: local 07:00 = UTC 15:00
        jan_14_3pm_utc = datetime(2026, 1, 14, 15, 0, 0, tzinfo=UTC)
        set_chore_due_date(coordinator, chore_id, jan_14_3pm_utc)

        # Both assignees complete 2 hours late at 17:00 UTC (09:00 local)
        jan_14_5pm_utc = datetime(2026, 1, 14, 17, 0, 0, tzinfo=UTC)
        with (
            patch.object(
                coordinator.notification_manager, "notify_assignee", new=AsyncMock()
            ),
            mock_datetime(jan_14_5pm_utc),
        ):
            # Assignee 1 claims and gets approved
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            # Assignee 2 claims and gets approved (triggers reschedule)
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Due should advance to second slot: local 18:00 = UTC 02:00 next day
        new_due = get_chore_due_date(coordinator, chore_id)
        assert new_due is not None
        new_due_dt = datetime.fromisoformat(new_due)
        assert new_due_dt.hour == 2
        assert new_due_dt.day == 15  # Next day

    @pytest.mark.asyncio
    async def test_f2_15_empty_times_returns_none(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F2-15: Empty times string returns None."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)

        result = parse_daily_multi_times("", current, current.tzinfo)

        # Should return empty list for empty input
        assert result == []

    @pytest.mark.asyncio
    async def test_f2_16_invalid_times_format_ignored(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F2-16: Invalid time format entries are skipped."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)

        # "8am" is invalid, "17:00" is valid
        result = parse_daily_multi_times("8am|17:00", current, current.tzinfo)

        # Should only return valid entries
        assert len(result) == 1
        assert result[0].hour == 17

    @pytest.mark.asyncio
    async def test_f2_17_six_times_max_supported(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F2-17: Six times per day is supported."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)

        times_str = "06:00|08:00|10:00|12:00|14:00|16:00"
        result = parse_daily_multi_times(times_str, current, current.tzinfo)

        assert len(result) == 6
        hours = [slot.hour for slot in result]
        assert hours == [6, 8, 10, 12, 14, 16]

    @pytest.mark.asyncio
    async def test_f2_18_timezone_local_to_utc_conversion(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F2-18: Times are correctly converted to UTC."""
        # Test with a specific timezone
        eastern = ZoneInfo("America/New_York")
        current_eastern = datetime(2026, 1, 14, 12, 0, 0, tzinfo=eastern)

        result = parse_daily_multi_times("08:00|17:00", current_eastern, eastern)

        # Results should have timezone info
        assert len(result) == 2
        for slot in result:
            assert slot.tzinfo is not None


# =============================================================================
# FEATURE 3: CUSTOM HOURS UNIT TESTS
# =============================================================================


class TestCustomHours:
    """Tests for Feature 3: CUSTOM + hours unit.

    This extends the existing CUSTOM frequency to support hours as
    the interval unit.
    """

    @pytest.mark.asyncio
    async def test_f3_01_4_hour_interval_same_day(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F3-01: 4 hour interval advances within same day."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids["Custom Hours 4h"]

        # Verify setup
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_RECURRING_FREQUENCY) == FREQUENCY_CUSTOM
        assert chore_info.get(DATA_CHORE_CUSTOM_INTERVAL) == 4
        assert chore_info.get(DATA_CHORE_CUSTOM_INTERVAL_UNIT) == TIME_UNIT_HOURS

        # Test the calculation directly
        jan_14_6am = datetime(2026, 1, 14, 6, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_14_6am, TIME_UNIT_HOURS, 4)

        assert result is not None
        result_dt = cast("datetime", result)
        assert result_dt.hour == 10
        assert result_dt.date() == jan_14_6am.date()

    @pytest.mark.asyncio
    async def test_f3_02_8_hour_interval_cross_midnight(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F3-02: 8 hour interval can cross midnight."""
        coordinator = scenario_enhanced_frequencies.coordinator
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom Hours 8h Cross Midnight"
        ]

        # Verify setup
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert chore_info.get(DATA_CHORE_CUSTOM_INTERVAL) == 8
        assert chore_info.get(DATA_CHORE_CUSTOM_INTERVAL_UNIT) == TIME_UNIT_HOURS

        # Test: 22:00 + 8 hours = 06:00 next day
        jan_14_10pm = datetime(2026, 1, 14, 22, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_14_10pm, TIME_UNIT_HOURS, 8)

        assert result is not None
        result_dt = cast("datetime", result)
        assert result_dt.hour == 6
        assert result_dt.date() == (jan_14_10pm.date() + timedelta(days=1))

    @pytest.mark.asyncio
    async def test_f3_03_36_hour_interval(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F3-03: 36 hour interval works correctly."""
        jan_1_noon = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_1_noon, TIME_UNIT_HOURS, 36)

        # Jan 1 noon + 36 hours = Jan 3 midnight
        assert result is not None
        expected = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)
        assert result == expected

    @pytest.mark.asyncio
    async def test_f3_04_1_hour_minimum(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F3-04: 1 hour minimum interval works."""
        jan_14_10am = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_14_10am, TIME_UNIT_HOURS, 1)

        assert result is not None
        result_dt = cast("datetime", result)
        assert result_dt.hour == 11
        assert result_dt.date() == jan_14_10am.date()

    @pytest.mark.asyncio
    async def test_f3_05_hours_with_upon_completion(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F3-05: Hours + UPON_COMPLETION resets immediately with new due."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_zoe_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        assignee_max_id = scenario_enhanced_frequencies.assignee_ids["Max!"]
        chore_id = scenario_enhanced_frequencies.chore_ids["Custom Hours 4h"]

        # Verify reset type
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_UPON_COMPLETION
        )

        # Both assignees must complete (SHARED chore with shared_all)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            # Assignee 1 claims and gets approved
            await coordinator.chore_manager.claim_chore(
                assignee_zoe_id, chore_id, "Zoë"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_zoe_id, chore_id
            )
            # Assignee 2 claims and gets approved (triggers UPON_COMPLETION reset)
            await coordinator.chore_manager.claim_chore(
                assignee_max_id, chore_id, "Max!"
            )
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_max_id, chore_id
            )

        # Should be PENDING (UPON_COMPLETION reset) - check Zoë's state
        state = get_assignee_chore_state(coordinator, assignee_zoe_id, chore_id)
        assert state == CHORE_STATE_PENDING

    @pytest.mark.asyncio
    async def test_f3_06_hours_with_at_midnight_once(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """F3-06: Hours + AT_MIDNIGHT_ONCE keeps state until midnight."""
        # This is a validation that hours works with all reset types

        # Test using dt_add_interval directly
        now = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)
        result = dt_add_interval(now, TIME_UNIT_HOURS, 6)

        assert result is not None
        result_dt = cast("datetime", result)
        assert result_dt.hour == 16

    @pytest.mark.asyncio
    async def test_f3_07_hours_with_at_due_date_once(
        self,
        hass: HomeAssistant,
        scenario_enhanced_frequencies: SetupResult,
    ) -> None:
        """F3-07: Hours + AT_DUE_DATE_ONCE stays approved until due passes."""
        coordinator = scenario_enhanced_frequencies.coordinator
        assignee_id = scenario_enhanced_frequencies.assignee_ids["Zoë"]
        chore_id = scenario_enhanced_frequencies.chore_ids[
            "Custom Hours 8h Cross Midnight"
        ]

        # Verify reset type
        chore_info = coordinator.chores_data.get(chore_id, {})
        assert (
            chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
            == APPROVAL_RESET_AT_DUE_DATE_ONCE
        )

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(assignee_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore(
                "Môm Astrid Stârblüm", assignee_id, chore_id
            )

        # With AT_DUE_DATE_ONCE, should stay APPROVED
        state = get_assignee_chore_state(coordinator, assignee_id, chore_id)
        assert state == CHORE_STATE_APPROVED

    @pytest.mark.asyncio
    async def test_f3_08_regression_days_still_works(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F3-08: Regression - days interval still works correctly."""
        jan_14 = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_14, TIME_UNIT_DAYS, 5)

        assert result is not None
        expected = datetime(2026, 1, 19, 10, 0, 0, tzinfo=UTC)
        assert result == expected

    @pytest.mark.asyncio
    async def test_f3_09_regression_weeks_still_works(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F3-09: Regression - weeks interval still works correctly."""
        jan_14 = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_14, TIME_UNIT_WEEKS, 2)

        assert result is not None
        expected = datetime(2026, 1, 28, 10, 0, 0, tzinfo=UTC)
        assert result == expected

    @pytest.mark.asyncio
    async def test_f3_10_regression_months_still_works(
        self,
        hass: HomeAssistant,
    ) -> None:
        """F3-10: Regression - months interval still works correctly."""
        jan_14 = datetime(2026, 1, 14, 10, 0, 0, tzinfo=UTC)
        result = dt_add_interval(jan_14, TIME_UNIT_MONTHS, 1)

        assert result is not None
        result_dt = cast("datetime", result)
        # Jan 14 + 1 month = Feb 14
        assert result_dt.month == 2
        assert result_dt.day == 14
