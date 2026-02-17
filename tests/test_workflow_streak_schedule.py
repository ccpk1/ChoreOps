"""Integration tests for schedule-aware streak calculation.

Tests coordinator streak logic when approving chores with various schedules.

Test Organization:
- TestStreakCalculation: Core streak scenarios (STK-01 to STK-12)
- TestStreakEdgeCases: Edge cases (EDGE-01 to EDGE-04)

Data Injection Note:
These tests require direct modification of chore schedule configs and
last_approved timestamps that cannot be set through the options flow.
DATA INJECTION: Setting last_approved/frequency for streak testing -
approved per AGENT_TEST_CREATION_INSTRUCTIONS Rule 2.1

Reference: STREAK_SYSTEM_IN-PROCESS.md Phase 3 Test Scenarios
"""

# pylint: disable=redefined-outer-name
# hass fixture required for HA test setup
# pylint: disable=protected-access
# Testing internal coordinator streak logic

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

# Additional constants not in tests.helpers yet - import directly
# fmt: off
from custom_components.choreops.const import (
    DATA_CHORE_APPLICABLE_DAYS,
    DATA_CHORE_CUSTOM_INTERVAL,
    DATA_CHORE_CUSTOM_INTERVAL_UNIT,
    DATA_KID_CHORE_DATA_CURRENT_STREAK,
    DATA_KID_CHORE_DATA_LAST_COMPLETED,
    DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK,
    DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY,
    DATA_KID_CHORE_DATA_PERIODS,
    DATA_KID_CHORE_DATA_PERIODS_ALL_TIME,
    DATA_KID_CHORE_DATA_PERIODS_DAILY,
    FREQUENCY_CUSTOM,
    HELPER_RETURN_DATETIME_LOCAL,
    TIME_UNIT_DAYS,
)
from custom_components.choreops.utils.dt_utils import dt_parse, dt_today_local
from tests.helpers import (
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_RECURRING_FREQUENCY,
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_LAST_APPROVED,
    FREQUENCY_DAILY,
    FREQUENCY_NONE,
    FREQUENCY_WEEKLY,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# fmt: on


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_scheduling(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scheduling scenario: varied chore frequencies."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_scheduling.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_kid_chore_data(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> dict[str, Any]:
    """Get per-kid chore data for a specific chore.

    Args:
        coordinator: KidsChoresDataCoordinator
        kid_id: The kid's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        Dict of per-kid chore data (state, last_approved, periods, etc.)
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.get(DATA_KID_CHORE_DATA, {})
    return chore_data.get(chore_id, {})


def get_daily_streak(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
    date_iso: str,
) -> int:
    """Get the daily streak value for a specific date.

    Args:
        coordinator: KidsChoresDataCoordinator
        kid_id: The kid's internal UUID
        chore_id: The chore's internal UUID
        date_iso: Date in ISO format (YYYY-MM-DD)

    Returns:
        Streak count for that day, or 0 if not found
    """
    chore_data = get_kid_chore_data(coordinator, kid_id, chore_id)
    periods = chore_data.get(DATA_KID_CHORE_DATA_PERIODS, {})
    daily = periods.get(DATA_KID_CHORE_DATA_PERIODS_DAILY, {})
    day_data = daily.get(date_iso, {})
    return day_data.get(DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY, 0)


def get_all_time_streak(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
) -> int:
    """Get the all-time longest streak for a chore.

    Args:
        coordinator: KidsChoresDataCoordinator
        kid_id: The kid's internal UUID
        chore_id: The chore's internal UUID

    Returns:
        All-time longest streak, or 0 if not found
    """
    chore_data = get_kid_chore_data(coordinator, kid_id, chore_id)
    periods = chore_data.get(DATA_KID_CHORE_DATA_PERIODS, {})
    all_time = periods.get(DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {})
    return all_time.get(DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0)


def set_chore_frequency(
    coordinator: Any,
    chore_id: str,
    frequency: str,
    interval: int | None = None,
    interval_unit: str | None = None,
    applicable_days: list[int] | None = None,
) -> None:
    """Set chore frequency configuration.

    DATA INJECTION: Setting frequency for streak testing - approved per Rule 2.1
    """
    chore_info = coordinator.chores_data.get(chore_id, {})
    chore_info[DATA_CHORE_RECURRING_FREQUENCY] = frequency
    if interval is not None:
        chore_info[DATA_CHORE_CUSTOM_INTERVAL] = interval
    if interval_unit is not None:
        chore_info[DATA_CHORE_CUSTOM_INTERVAL_UNIT] = interval_unit
    if applicable_days is not None:
        chore_info[DATA_CHORE_APPLICABLE_DAYS] = applicable_days


def set_last_completed(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
    last_completed_dt: datetime,
) -> None:
    """Set last completed timestamp for a chore (for streak testing).

    DATA INJECTION: Setting last_completed for streak testing - approved per Rule 2.1

    Note: For INDEPENDENT chores, sets per-kid last_completed.
    For SHARED chores, would need to set chore-level (not implemented here
    as streak tests use INDEPENDENT chores via Reset Upon Completion).
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.setdefault(chore_id, {})
    per_chore[DATA_KID_CHORE_DATA_LAST_COMPLETED] = last_completed_dt.isoformat()


def set_yesterday_streak(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
    yesterday_iso: str,
    streak: int,
) -> None:
    """Set yesterday's streak value for testing continuation.

    DATA INJECTION: Setting streak for continuation testing - approved per Rule 2.1
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.setdefault(chore_id, {})
    periods = per_chore.setdefault(DATA_KID_CHORE_DATA_PERIODS, {})
    daily = periods.setdefault(DATA_KID_CHORE_DATA_PERIODS_DAILY, {})
    day_data = daily.setdefault(yesterday_iso, {})
    day_data[DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY] = streak

    # Phase 5 fix: Also set persistent current_streak that workflow expects
    per_chore[DATA_KID_CHORE_DATA_CURRENT_STREAK] = streak


# =============================================================================
# TEST CLASS: STREAK CALCULATION
# =============================================================================


class TestStreakCalculation:
    """Tests for coordinator streak calculation logic."""

    @pytest.mark.asyncio
    async def test_stk_01_first_approval_sets_streak_one(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """First approval ever sets streak to 1."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" - resets immediately after approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Ensure no prior last_approved
        kid_chore_data = get_kid_chore_data(coordinator, kid_id, chore_id)
        assert kid_chore_data.get(DATA_KID_CHORE_DATA_LAST_APPROVED) is None

        # Approve chore
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak is 1 (use local date since coordinator stores by local date)
        today_iso = dt_today_local().isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 1, "First approval should set streak to 1"

    @pytest.mark.asyncio
    async def test_stk_02_daily_consecutive_increments(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
        freezer: Any,
    ) -> None:
        """Daily consecutive approvals increment streak."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" - resets immediately after approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: daily frequency, yesterday streak=5, approved yesterday
        set_chore_frequency(coordinator, chore_id, FREQUENCY_DAILY)

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        # last_completed needs to be a UTC timestamp representing yesterday
        yesterday_utc = datetime.now(UTC) - timedelta(days=1)
        set_last_completed(coordinator, kid_id, chore_id, yesterday_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 5)

        # Approve today
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak is now 6
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 6, "Consecutive daily should increment streak to 6"

    @pytest.mark.asyncio
    async def test_stk_03_daily_break_resets(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Missing a day on daily chore resets streak to 1."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" - resets immediately after approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: daily frequency, approved 2 days ago (skipped yesterday)
        set_chore_frequency(coordinator, chore_id, FREQUENCY_DAILY)

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        two_days_ago_utc = datetime.now(UTC) - timedelta(days=2)
        set_last_completed(coordinator, kid_id, chore_id, two_days_ago_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 5)

        # Approve today (missed yesterday)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak reset to 1
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 1, "Missing a day should reset daily streak to 1"

    @pytest.mark.asyncio
    async def test_stk_04_weekly_on_time_continues(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Weekly chore approved within 7 days continues streak."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: weekly frequency, approved 7 days ago (exactly 1 week)
        set_chore_frequency(coordinator, chore_id, FREQUENCY_WEEKLY)

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()

        one_week_ago_utc = datetime.now(UTC) - timedelta(days=7)
        # Convert last_completed (UTC) to local date for streak bucket key
        one_week_ago_local = dt_parse(
            one_week_ago_utc.isoformat(), return_type=HELPER_RETURN_DATETIME_LOCAL
        )
        one_week_ago_iso = one_week_ago_local.date().isoformat()

        set_last_completed(coordinator, kid_id, chore_id, one_week_ago_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, one_week_ago_iso, 3)

        # Approve today (exactly 1 week later)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak continues (3 + 1 = 4)
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 4, "Weekly on-time approval should continue streak"

    @pytest.mark.asyncio
    async def test_stk_05_weekly_break_resets(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Weekly chore approved after 2 weeks breaks streak."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: weekly frequency, approved 14+ days ago (missed a week)
        set_chore_frequency(coordinator, chore_id, FREQUENCY_WEEKLY)

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        two_weeks_ago_utc = datetime.now(UTC) - timedelta(days=15)  # More than 14 days
        set_last_completed(coordinator, kid_id, chore_id, two_weeks_ago_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 10)

        # Approve today (missed at least one week)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak reset to 1
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 1, "Missing a week should reset weekly streak to 1"

    @pytest.mark.asyncio
    async def test_stk_06_no_frequency_uses_legacy(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Chore with FREQUENCY_NONE uses legacy day-gap logic."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: NO frequency configured
        set_chore_frequency(coordinator, chore_id, FREQUENCY_NONE)

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        yesterday_utc = datetime.now(UTC) - timedelta(days=1)
        set_last_completed(coordinator, kid_id, chore_id, yesterday_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 5)

        # Approve today
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Legacy logic: yesterday had streak, so continue
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 6, (
            "FREQUENCY_NONE should use legacy day-gap (streak continues)"
        )

    @pytest.mark.asyncio
    async def test_stk_10_every_3_days_continue(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Every-3-days chore approved on day 3 continues streak."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: every 3 days, approved 3 days ago
        set_chore_frequency(
            coordinator,
            chore_id,
            FREQUENCY_CUSTOM,
            interval=3,
            interval_unit=TIME_UNIT_DAYS,
        )

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()

        three_days_ago_utc = datetime.now(UTC) - timedelta(days=3)
        # Convert last_completed (UTC) to local date for streak bucket key
        three_days_ago_local = dt_parse(
            three_days_ago_utc.isoformat(), return_type=HELPER_RETURN_DATETIME_LOCAL
        )
        three_days_ago_iso = three_days_ago_local.date().isoformat()

        set_last_completed(coordinator, kid_id, chore_id, three_days_ago_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, three_days_ago_iso, 4)

        # Approve today (exactly 3 days later = on schedule)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak continues
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 5, "Every-3-days on-time should continue streak"

    @pytest.mark.asyncio
    async def test_stk_11_every_3_days_break(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Every-3-days chore approved on day 7 breaks streak (missed day 3)."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: every 3 days, approved 7 days ago (missed day 3)
        set_chore_frequency(
            coordinator,
            chore_id,
            FREQUENCY_CUSTOM,
            interval=3,
            interval_unit=TIME_UNIT_DAYS,
        )

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        seven_days_ago_utc = datetime.now(UTC) - timedelta(days=7)
        set_last_completed(coordinator, kid_id, chore_id, seven_days_ago_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 8)

        # Approve today (missed the day-3 occurrence)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak reset
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 1, "Missing every-3-days occurrence should reset streak"

    @pytest.mark.asyncio
    async def test_stk_12_existing_streak_preserved(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Existing streak is preserved and incremented on consecutive approval."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: daily, yesterday streak=10, approved yesterday
        set_chore_frequency(coordinator, chore_id, FREQUENCY_DAILY)

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        yesterday_utc = datetime.now(UTC) - timedelta(days=1)
        set_last_completed(coordinator, kid_id, chore_id, yesterday_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 10)

        # Approve today
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Verify streak is 11 (10 + 1)
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 11, "Existing streak should be preserved and incremented"


# =============================================================================
# TEST CLASS: EDGE CASES
# =============================================================================


class TestStreakEdgeCases:
    """Edge case tests for streak calculation."""

    @pytest.mark.asyncio
    async def test_edge_03_missing_base_date_uses_now(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Schedule config without base_date uses current time."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: daily frequency but clear due_date (base_date source)
        chore_info = coordinator.chores_data.get(chore_id)
        assert chore_info is not None, "Chore should exist"
        chore_info[DATA_CHORE_RECURRING_FREQUENCY] = FREQUENCY_DAILY
        chore_info[DATA_CHORE_DUE_DATE] = None  # Clear base_date source

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        yesterday_utc = datetime.now(UTC) - timedelta(days=1)
        set_last_completed(coordinator, kid_id, chore_id, yesterday_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 3)

        # Should not crash, should use fallback
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        # Just verify we got a streak (either continued or reset, but not crashed)
        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak >= 1, "Should have a valid streak even without base_date"

    @pytest.mark.asyncio
    async def test_edge_04_empty_applicable_days(
        self,
        hass: HomeAssistant,
        scenario_scheduling: SetupResult,
    ) -> None:
        """Empty applicable_days should not constrain occurrences."""
        coordinator = scenario_scheduling.coordinator
        kid_id = scenario_scheduling.kid_ids["Zoë"]
        # Use "Reset Upon Completion" to allow re-approval
        chore_id = scenario_scheduling.chore_ids["Reset Upon Completion"]

        # Set up: daily with empty applicable_days
        set_chore_frequency(
            coordinator,
            chore_id,
            FREQUENCY_DAILY,
            applicable_days=[],  # Empty list
        )

        # Use local dates (coordinator stores streaks by local date)
        today_local = dt_today_local()
        yesterday_local = today_local - timedelta(days=1)
        yesterday_iso = yesterday_local.isoformat()

        yesterday_utc = datetime.now(UTC) - timedelta(days=1)
        set_last_completed(coordinator, kid_id, chore_id, yesterday_utc)
        set_yesterday_streak(coordinator, kid_id, chore_id, yesterday_iso, 5)

        # Should continue streak normally (empty means no filter)
        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            await coordinator.chore_manager.claim_chore(kid_id, chore_id, "Zoë")
            await coordinator.chore_manager.approve_chore("Mom", kid_id, chore_id)

        today_iso = today_local.isoformat()
        streak = get_daily_streak(coordinator, kid_id, chore_id, today_iso)
        assert streak == 6, "Empty applicable_days should not break streak"
