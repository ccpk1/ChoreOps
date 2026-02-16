"""Unit tests for RecurrenceEngine.has_missed_occurrences() method.

Tests schedule-aware streak calculation logic:
- HMO-01 to HMO-03: Daily frequency scenarios
- HMO-04 to HMO-06: Every-N-days (custom interval) scenarios
- HMO-07 to HMO-08: Weekly frequency scenarios
- HMO-09 to HMO-10: Monthly frequency scenarios
- HMO-11 to HMO-15: Edge cases (FREQUENCY_NONE, same-day, biweekly, applicable_days)

Reference: STREAK_SYSTEM_IN-PROCESS.md Phase 3 Test Scenarios
"""

from datetime import UTC, datetime

from custom_components.kidschores import const
from custom_components.kidschores.engines.schedule_engine import RecurrenceEngine
from custom_components.kidschores.type_defs import ScheduleConfig

# =============================================================================
# Helper Functions
# =============================================================================


def make_utc_dt(
    year: int,
    month: int,
    day: int,
    hour: int = 10,
    minute: int = 0,
) -> datetime:
    """Create a UTC datetime for testing."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=UTC)


def make_config(
    frequency: str,
    base_date: str | None = None,
    interval: int | None = None,
    interval_unit: str | None = None,
    applicable_days: list[int] | None = None,
) -> ScheduleConfig:
    """Create a ScheduleConfig for testing.

    Args:
        frequency: Recurrence frequency (daily, weekly, monthly, etc.)
        base_date: ISO format base date string
        interval: Custom interval value (for FREQUENCY_CUSTOM)
        interval_unit: Custom interval unit (days, weeks, months)
        applicable_days: List of weekday integers (0=Mon, 6=Sun)

    Returns:
        ScheduleConfig TypedDict
    """
    config: ScheduleConfig = {"frequency": frequency}
    if base_date is not None:
        config["base_date"] = base_date
    if interval is not None:
        config["interval"] = interval
    if interval_unit is not None:
        config["interval_unit"] = interval_unit
    if applicable_days is not None:
        config["applicable_days"] = applicable_days
    return config


# =============================================================================
# Test Class: has_missed_occurrences()
# =============================================================================


class TestHasMissedOccurrences:
    """Tests for RecurrenceEngine.has_missed_occurrences() method."""

    # -------------------------------------------------------------------------
    # HMO-01 to HMO-03: Daily Frequency
    # -------------------------------------------------------------------------

    def test_hmo_01_daily_consecutive(self) -> None:
        """Daily chore: consecutive days = no miss (streak continues)."""
        config = make_config(
            frequency=const.FREQUENCY_DAILY,
            base_date="2026-01-01T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 1, 2, 10)

        result = engine.has_missed_occurrences(last, current)

        assert result is False, "Consecutive daily completions should not break streak"

    def test_hmo_02_daily_skip_one_day(self) -> None:
        """Daily chore: skip one day = miss (streak breaks)."""
        config = make_config(
            frequency=const.FREQUENCY_DAILY,
            base_date="2026-01-01T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 1, 3, 10)  # Skipped Jan 2

        result = engine.has_missed_occurrences(last, current)

        assert result is True, "Skipping one day should break daily streak"

    def test_hmo_03_daily_skip_two_days(self) -> None:
        """Daily chore: skip two days = miss (streak breaks)."""
        config = make_config(
            frequency=const.FREQUENCY_DAILY,
            base_date="2026-01-01T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 1, 4, 10)  # Skipped Jan 2 and Jan 3

        result = engine.has_missed_occurrences(last, current)

        assert result is True, "Skipping two days should break daily streak"

    # -------------------------------------------------------------------------
    # HMO-04 to HMO-06: Every-N-Days (Custom Interval)
    # -------------------------------------------------------------------------

    def test_hmo_04_every_3_days_on_time(self) -> None:
        """Every 3 days: completion on day 4 = no miss (streak continues)."""
        config = make_config(
            frequency=const.FREQUENCY_CUSTOM,
            base_date="2026-01-01T10:00:00+00:00",
            interval=3,
            interval_unit=const.TIME_UNIT_DAYS,
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 1, 4, 10)  # Exactly 3 days later

        result = engine.has_missed_occurrences(last, current)

        assert result is False, "Every-3-days completed on day 4 should continue streak"

    def test_hmo_05_every_3_days_early(self) -> None:
        """Every 3 days: completion on day 3 = no miss (early is OK)."""
        config = make_config(
            frequency=const.FREQUENCY_CUSTOM,
            base_date="2026-01-01T10:00:00+00:00",
            interval=3,
            interval_unit=const.TIME_UNIT_DAYS,
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 1, 3, 10)  # 2 days later (early)

        result = engine.has_missed_occurrences(last, current)

        assert result is False, "Early completion should not break streak"

    def test_hmo_06_every_3_days_late(self) -> None:
        """Every 3 days: completion on day 8 = miss (missed day 4)."""
        config = make_config(
            frequency=const.FREQUENCY_CUSTOM,
            base_date="2026-01-01T10:00:00+00:00",
            interval=3,
            interval_unit=const.TIME_UNIT_DAYS,
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 1, 8, 10)  # Missed Jan 4 occurrence

        result = engine.has_missed_occurrences(last, current)

        assert result is True, "Missing Jan 4 occurrence should break streak"

    # -------------------------------------------------------------------------
    # HMO-07 to HMO-08: Weekly Frequency
    # -------------------------------------------------------------------------

    def test_hmo_07_weekly_consecutive(self) -> None:
        """Weekly chore: consecutive weeks = no miss (streak continues)."""
        # Monday Jan 5, 2026 to Monday Jan 12, 2026 (actual Mondays)
        config = make_config(
            frequency=const.FREQUENCY_WEEKLY,
            base_date="2026-01-05T10:00:00+00:00",  # Monday Jan 5
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 5, 10)  # Monday Jan 5
        current = make_utc_dt(2026, 1, 12, 10)  # Monday Jan 12

        result = engine.has_missed_occurrences(last, current)

        assert result is False, "Consecutive weekly completions should continue streak"

    def test_hmo_08_weekly_skip(self) -> None:
        """Weekly chore: skip one week = miss (streak breaks)."""
        config = make_config(
            frequency=const.FREQUENCY_WEEKLY,
            base_date="2026-01-05T10:00:00+00:00",  # Monday Jan 5
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 5, 10)  # Monday Jan 5
        current = make_utc_dt(2026, 1, 19, 10)  # Monday Jan 19 (skipped Jan 12)

        result = engine.has_missed_occurrences(last, current)

        assert result is True, "Skipping Jan 12 should break weekly streak"

    # -------------------------------------------------------------------------
    # HMO-09 to HMO-10: Monthly Frequency
    # -------------------------------------------------------------------------

    def test_hmo_09_monthly_consecutive(self) -> None:
        """Monthly chore: consecutive months = no miss (streak continues)."""
        config = make_config(
            frequency=const.FREQUENCY_MONTHLY,
            base_date="2026-01-15T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 15, 10)
        current = make_utc_dt(2026, 2, 15, 10)

        result = engine.has_missed_occurrences(last, current)

        assert result is False, "Consecutive monthly completions should continue streak"

    def test_hmo_10_monthly_skip(self) -> None:
        """Monthly chore: skip one month = miss (streak breaks)."""
        config = make_config(
            frequency=const.FREQUENCY_MONTHLY,
            base_date="2026-01-15T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 15, 10)
        current = make_utc_dt(2026, 3, 15, 10)  # Skipped Feb 15

        result = engine.has_missed_occurrences(last, current)

        assert result is True, "Skipping Feb 15 should break monthly streak"

    # -------------------------------------------------------------------------
    # HMO-11 to HMO-15: Edge Cases
    # -------------------------------------------------------------------------

    def test_hmo_11_frequency_none_always_false(self) -> None:
        """FREQUENCY_NONE: always returns False (no schedule = no miss)."""
        config = make_config(frequency=const.FREQUENCY_NONE)
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 10)
        current = make_utc_dt(2026, 6, 1, 10)  # 5 months later

        result = engine.has_missed_occurrences(last, current)

        assert result is False, "FREQUENCY_NONE should never report missed occurrences"

    def test_hmo_12_same_day_completion_before_scheduled_time(self) -> None:
        """Same day: completion before scheduled time, then after.

        Base date 10:00. If first completion at 9AM, second at 5PM,
        the 10AM occurrence is technically between them = "missed".
        This is edge case behavior - in practice, same-day completions
        are handled by the coordinator (multi-claim logic).
        """
        config = make_config(
            frequency=const.FREQUENCY_DAILY,
            base_date="2026-01-01T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 9, 0)  # 9:00 AM (before base time)
        current = make_utc_dt(2026, 1, 1, 17, 0)  # 5:00 PM (after base time)

        result = engine.has_missed_occurrences(last, current)

        # The 10:00 occurrence falls between 9AM and 5PM
        assert result is True, "Occurrence at 10AM is between 9AM and 5PM"

    def test_hmo_12b_same_day_completion_after_scheduled_time(self) -> None:
        """Same day: both completions after scheduled time = no miss.

        If both completions are after the day's scheduled occurrence,
        no occurrence falls between them.
        """
        config = make_config(
            frequency=const.FREQUENCY_DAILY,
            base_date="2026-01-01T10:00:00+00:00",
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 1, 11, 0)  # 11:00 AM (after base time)
        current = make_utc_dt(2026, 1, 1, 17, 0)  # 5:00 PM (after base time)

        result = engine.has_missed_occurrences(last, current)

        # No occurrence between 11AM and 5PM on same day
        assert result is False, "No occurrence between both-after-scheduled completions"

    def test_hmo_13_biweekly_consecutive(self) -> None:
        """Biweekly chore: two weeks apart = no miss (streak continues)."""
        config = make_config(
            frequency=const.FREQUENCY_BIWEEKLY,
            base_date="2026-01-05T10:00:00+00:00",  # Monday Jan 5
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 5, 10)  # Monday Jan 5
        current = make_utc_dt(2026, 1, 19, 10)  # Monday Jan 19 (2 weeks)

        result = engine.has_missed_occurrences(last, current)

        assert result is False, (
            "Biweekly completions 2 weeks apart should continue streak"
        )

    def test_hmo_14_biweekly_skip(self) -> None:
        """Biweekly chore: four weeks apart = miss (skipped one biweekly)."""
        config = make_config(
            frequency=const.FREQUENCY_BIWEEKLY,
            base_date="2026-01-05T10:00:00+00:00",  # Monday Jan 5
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 5, 10)  # Monday Jan 5
        current = make_utc_dt(2026, 2, 2, 10)  # Monday Feb 2 (4 weeks, missed Jan 19)

        result = engine.has_missed_occurrences(last, current)

        assert result is True, "Missing Jan 19 biweekly occurrence should break streak"

    def test_hmo_15_applicable_days_filter(self) -> None:
        """Weekly with applicable_days: only scheduled days count.

        Weekly Monday chore: complete on consecutive Mondays.
        Tue/Wed/etc between them should not affect streak.
        """
        config = make_config(
            frequency=const.FREQUENCY_WEEKLY,
            base_date="2026-01-05T10:00:00+00:00",  # Monday Jan 5
            applicable_days=[0],  # Only Mondays (0=Mon in ScheduleConfig)
        )
        engine = RecurrenceEngine(config)

        last = make_utc_dt(2026, 1, 5, 10)  # Monday Jan 5
        current = make_utc_dt(2026, 1, 12, 10)  # Monday Jan 12

        result = engine.has_missed_occurrences(last, current)

        # Consecutive Mondays = no missed occurrence
        assert result is False, "Consecutive Mondays should not break weekly streak"
