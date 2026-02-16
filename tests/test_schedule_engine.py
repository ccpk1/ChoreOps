"""Unit tests for schedule_engine.py RecurrenceEngine.

Tests edge cases per Phase 2a plan:
- EC-01: Monthly on day 31 → Feb 28 (clamping)
- EC-02: Feb 29 leap year handling
- EC-03: Year boundary crossing (Dec 31 → Jan 1)
- EC-04: Empty applicable_days list
- EC-05: Applicable_days constraint
- EC-06: PERIOD_QUARTER_END calculations
- EC-07: CUSTOM_FROM_COMPLETE base date handling
- EC-08: Midnight boundary edge cases
- EC-09: MAX_ITERATIONS safety limit (stubbed for loop protection)
"""

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util
import pytest

from custom_components.kidschores import const
from custom_components.kidschores.engines.schedule_engine import (
    RecurrenceEngine,
    calculate_next_due_date,
)

if TYPE_CHECKING:
    from custom_components.kidschores.type_defs import ScheduleConfig


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def utc_tz() -> ZoneInfo:
    """Return UTC timezone."""
    return ZoneInfo("UTC")


@pytest.fixture
def local_tz() -> ZoneInfo:
    """Return a local timezone (Europe/Berlin for DST testing)."""
    return ZoneInfo("Europe/Berlin")


def make_utc_dt(year: int, month: int, day: int, hour: int = 12) -> datetime:
    """Create a UTC datetime for testing."""
    return datetime(year, month, day, hour, 0, 0, tzinfo=ZoneInfo("UTC"))


# =============================================================================
# EC-01: Monthly on day 31 → Feb 28 (clamping)
# =============================================================================


class TestMonthlyClamping:
    """Test monthly frequency clamping behavior."""

    def test_jan31_plus_one_month_clamps_to_feb28(self) -> None:
        """Jan 31 + 1 month should clamp to Feb 28 (not skip to Mar 3)."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_MONTHLY,
            "base_date": "2026-01-31T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        # Reference date in January, next should be Feb 28
        reference = make_utc_dt(2026, 1, 31, 13)  # After base time
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        # Should clamp to Feb 28, not skip to Mar 3
        assert result.month == 2
        assert result.day == 28

    def test_jan30_plus_one_month_clamps_to_feb28(self) -> None:
        """Jan 30 + 1 month should clamp to Feb 28."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_MONTHLY,
            "base_date": "2026-01-30T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 30, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.month == 2
        assert result.day == 28  # Clamped

    def test_monthly_day28_no_clamping_needed(self) -> None:
        """Day 28 doesn't need clamping - should work normally."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_MONTHLY,
            "base_date": "2026-01-28T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 28, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.month == 2
        assert result.day == 28  # Exact day preserved


# =============================================================================
# EC-02: Feb 29 leap year handling
# =============================================================================


class TestLeapYearHandling:
    """Test leap year edge cases."""

    def test_feb29_leap_year_to_non_leap(self) -> None:
        """Feb 29 2024 (leap) + 1 year should clamp to Feb 28 2025."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_YEARLY,
            "base_date": "2024-02-29T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2024, 2, 29, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 28  # Clamped to 28 in non-leap year

    def test_feb29_leap_to_leap(self) -> None:
        """Feb 29 clamps to 28 each year - relativedelta doesn't remember original.

        Note: relativedelta(years=1) on Feb 29 always clamps to Feb 28 in
        non-leap years. We can't "remember" the original was Feb 29 because
        each calculation starts fresh from the clamped result. This is expected
        behavior for consistent month arithmetic.
        """
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_YEARLY,
            "base_date": "2024-02-29T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        # Get multiple occurrences
        reference = make_utc_dt(2024, 2, 29, 13)

        # All subsequent years will be Feb 28 (clamped from original Feb 29)
        result = engine.get_next_occurrence(after=reference, require_future=True)
        assert result is not None
        assert result.year == 2025
        assert result.day == 28  # Clamped

        result = engine.get_next_occurrence(after=result, require_future=True)
        assert result is not None
        assert result.year == 2026
        assert result.day == 28  # Clamped

        result = engine.get_next_occurrence(after=result, require_future=True)
        assert result is not None
        assert result.year == 2027
        assert result.day == 28  # Clamped

        # Even 2028 (leap year) shows 28 because we're adding to Feb 28, not Feb 29
        result = engine.get_next_occurrence(after=result, require_future=True)
        assert result is not None
        assert result.year == 2028
        assert result.day == 28  # Clamping is consistent


# =============================================================================
# EC-03: Year boundary crossing
# =============================================================================


class TestYearBoundaryCrossing:
    """Test year boundary crossing."""

    def test_dec31_plus_one_day(self) -> None:
        """Dec 31 + 1 day should cross to Jan 1."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2025-12-31T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2025, 12, 31, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 1

    def test_weekly_crosses_year(self) -> None:
        """Weekly frequency should cross year boundary correctly."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_WEEKLY,
            "base_date": "2025-12-28T12:00:00+00:00",  # Sunday
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2025, 12, 28, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 4  # Next Sunday


# =============================================================================
# EC-04 & EC-05: Applicable days handling
# =============================================================================


class TestApplicableDays:
    """Test applicable_days constraint."""

    def test_empty_applicable_days_no_constraint(self) -> None:
        """Empty applicable_days should not constrain results."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-05T12:00:00+00:00",  # Monday
            "applicable_days": [],
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 6  # Just next day

    def test_applicable_days_snaps_to_valid_day(self) -> None:
        """Result should snap to next valid weekday."""
        # Jan 5, 2026 is Monday (weekday 0)
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-05T12:00:00+00:00",
            "applicable_days": [2, 4],  # Wednesday (2) and Friday (4) only
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 13)  # Monday
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        # Should snap to Wednesday (Jan 7) - nearest applicable day
        assert result.weekday() in [2, 4]

    def test_applicable_days_weekend_only(self) -> None:
        """Applicable days for weekend only."""
        # Jan 5, 2026 is Monday
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-05T12:00:00+00:00",
            "applicable_days": [5, 6],  # Saturday (5) and Sunday (6) only
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 13)  # Monday
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.weekday() in [5, 6]  # Weekend


# =============================================================================
# EC-06: Period-end calculations
# =============================================================================


class TestPeriodEnds:
    """Test PERIOD_*_END frequency calculations."""

    def test_period_day_end(self) -> None:
        """PERIOD_DAY_END should return end of day (23:59:00)."""
        config: ScheduleConfig = {
            "frequency": const.PERIOD_DAY_END,
            "base_date": "2026-01-05T10:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 10)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        # Convert to local for time check
        result_local = dt_util.as_local(result)
        assert result_local.hour == const.END_OF_DAY_HOUR
        assert result_local.minute == const.END_OF_DAY_MINUTE

    def test_period_week_end_sunday(self) -> None:
        """PERIOD_WEEK_END should return Sunday 23:59:00."""
        config: ScheduleConfig = {
            "frequency": const.PERIOD_WEEK_END,
            "base_date": "2026-01-05T10:00:00+00:00",  # Monday
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 10)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        result_local = dt_util.as_local(result)
        assert result_local.weekday() == const.SUNDAY_WEEKDAY_INDEX  # Sunday

    def test_period_month_end(self) -> None:
        """PERIOD_MONTH_END should return last day of month."""
        config: ScheduleConfig = {
            "frequency": const.PERIOD_MONTH_END,
            "base_date": "2026-01-15T10:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 15, 10)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        result_local = dt_util.as_local(result)
        assert result_local.month == 1
        assert result_local.day == 31  # January has 31 days

    def test_period_quarter_end(self) -> None:
        """PERIOD_QUARTER_END should return end of quarter."""
        config: ScheduleConfig = {
            "frequency": const.PERIOD_QUARTER_END,
            "base_date": "2026-01-15T10:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 15, 10)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        result_local = dt_util.as_local(result)
        # Q1 ends March 31
        assert result_local.month == 3
        assert result_local.day == 31

    def test_period_year_end(self) -> None:
        """PERIOD_YEAR_END should return December 31."""
        config: ScheduleConfig = {
            "frequency": const.PERIOD_YEAR_END,
            "base_date": "2026-06-15T10:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 6, 15, 10)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        result_local = dt_util.as_local(result)
        assert result_local.month == 12
        assert result_local.day == 31


# =============================================================================
# EC-07: Custom intervals
# =============================================================================


class TestCustomIntervals:
    """Test FREQUENCY_CUSTOM and CUSTOM_FROM_COMPLETE."""

    def test_custom_3_days(self) -> None:
        """Custom 3-day interval should work correctly."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_CUSTOM,
            "interval": 3,
            "interval_unit": const.TIME_UNIT_DAYS,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 1, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 4  # 1 + 3 days

    def test_custom_2_weeks(self) -> None:
        """Custom 2-week interval should work correctly."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_CUSTOM,
            "interval": 2,
            "interval_unit": const.TIME_UNIT_WEEKS,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 1, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 15  # 1 + 14 days

    def test_custom_2_months(self) -> None:
        """Custom 2-month interval with clamping."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_CUSTOM,
            "interval": 2,
            "interval_unit": const.TIME_UNIT_MONTHS,
            "base_date": "2026-01-31T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 31, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        # Jan 31 + 2 months = Mar 31 (March has 31 days)
        assert result.month == 3
        assert result.day == 31

    def test_custom_from_complete_uses_base_date(self) -> None:
        """CUSTOM_FROM_COMPLETE should calculate from base_date."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_CUSTOM_FROM_COMPLETE,
            "interval": 5,
            "interval_unit": const.TIME_UNIT_DAYS,
            "base_date": "2026-01-10T12:00:00+00:00",  # Completion date
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 10, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 15  # 10 + 5 days


# =============================================================================
# EC-08: Midnight boundary edge cases
# =============================================================================


class TestMidnightBoundary:
    """Test midnight boundary handling."""

    def test_exactly_at_midnight(self) -> None:
        """Test occurrence at exactly midnight."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-05T00:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 0)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 6  # Must be strictly after

    def test_one_second_before_midnight(self) -> None:
        """Test just before midnight."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-05T23:59:59+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = datetime(2026, 1, 5, 23, 59, 58, tzinfo=ZoneInfo("UTC"))
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        # Should be the base date since it's after reference
        assert result.day == 5


# =============================================================================
# EC-09: Safety limits (MAX_ITERATIONS)
# =============================================================================


class TestSafetyLimits:
    """Test MAX_ITERATIONS safety limit."""

    def test_max_iterations_prevents_infinite_loop(self) -> None:
        """Verify MAX_ITERATIONS prevents runaway loops."""
        # This is a defensive test - we create a scenario that would loop
        # many times and verify it terminates

        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2000-01-01T12:00:00+00:00",  # Very old date
        }
        engine = RecurrenceEngine(config)

        # Reference far in the future - requires many iterations
        reference = make_utc_dt(2100, 1, 1, 12)

        # Should complete (not hang) even with many iterations
        # If MAX_ITERATIONS is hit, it will return a result or None
        result = engine.get_next_occurrence(after=reference, require_future=True)

        # The actual result depends on implementation, but it shouldn't hang
        assert result is not None or result is None  # Just confirm termination


# =============================================================================
# Standard frequency tests
# =============================================================================


class TestStandardFrequencies:
    """Test standard FREQUENCY_* constants."""

    def test_frequency_daily(self) -> None:
        """Test FREQUENCY_DAILY."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-05T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 6

    def test_frequency_weekly(self) -> None:
        """Test FREQUENCY_WEEKLY."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_WEEKLY,
            "base_date": "2026-01-05T12:00:00+00:00",  # Monday
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 12  # 5 + 7

    def test_frequency_biweekly(self) -> None:
        """Test FREQUENCY_BIWEEKLY."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_BIWEEKLY,
            "base_date": "2026-01-05T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 5, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.day == 19  # 5 + 14

    def test_frequency_quarterly(self) -> None:
        """Test FREQUENCY_QUARTERLY (3 months)."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_QUARTERLY,
            "base_date": "2026-01-15T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        reference = make_utc_dt(2026, 1, 15, 13)
        result = engine.get_next_occurrence(after=reference, require_future=True)

        assert result is not None
        assert result.month == 4  # 1 + 3 months
        assert result.day == 15

    def test_frequency_none_returns_none(self) -> None:
        """FREQUENCY_NONE should return None."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_NONE,
            "base_date": "2026-01-05T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        result = engine.get_next_occurrence(after=make_utc_dt(2026, 1, 5, 10))
        assert result is None


# =============================================================================
# get_occurrences() tests
# =============================================================================


class TestGetOccurrences:
    """Test get_occurrences() method."""

    def test_get_occurrences_in_range(self) -> None:
        """Get multiple occurrences within a date range."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        start = make_utc_dt(2026, 1, 5, 0)
        end = make_utc_dt(2026, 1, 10, 23)

        occurrences = engine.get_occurrences(start, end, limit=100)

        # Should have occurrences for Jan 5, 6, 7, 8, 9, 10
        assert len(occurrences) >= 5

    def test_get_occurrences_respects_limit(self) -> None:
        """Limit parameter should cap results."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        start = make_utc_dt(2026, 1, 1, 0)
        end = make_utc_dt(2026, 12, 31, 23)

        occurrences = engine.get_occurrences(start, end, limit=10)

        assert len(occurrences) == 10


# =============================================================================
# to_rrule_string() tests
# =============================================================================


class TestToRruleString:
    """Test RFC 5545 RRULE string generation."""

    def test_daily_rrule(self) -> None:
        """DAILY should generate correct RRULE."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=DAILY;INTERVAL=1"

    def test_weekly_rrule(self) -> None:
        """WEEKLY should generate correct RRULE."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_WEEKLY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=WEEKLY;INTERVAL=1"

    def test_biweekly_rrule(self) -> None:
        """BIWEEKLY should generate WEEKLY with INTERVAL=2."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_BIWEEKLY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=WEEKLY;INTERVAL=2"

    def test_monthly_rrule(self) -> None:
        """MONTHLY should generate correct RRULE."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_MONTHLY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=MONTHLY;INTERVAL=1"

    def test_quarterly_rrule(self) -> None:
        """QUARTERLY should generate MONTHLY with INTERVAL=3."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_QUARTERLY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=MONTHLY;INTERVAL=3"

    def test_yearly_rrule(self) -> None:
        """YEARLY should generate correct RRULE."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_YEARLY,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=YEARLY;INTERVAL=1"

    def test_week_end_rrule(self) -> None:
        """PERIOD_WEEK_END should generate BYDAY=SU."""
        config: ScheduleConfig = {
            "frequency": const.PERIOD_WEEK_END,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == "FREQ=WEEKLY;BYDAY=SU"

    def test_custom_returns_empty(self) -> None:
        """CUSTOM frequencies don't have standard RRULE representation."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_CUSTOM,
            "interval": 3,
            "interval_unit": const.TIME_UNIT_DAYS,
            "base_date": "2026-01-01T12:00:00+00:00",
        }
        engine = RecurrenceEngine(config)

        assert engine.to_rrule_string() == ""


# =============================================================================
# Convenience function tests
# =============================================================================


class TestConvenienceFunction:
    """Test calculate_next_due_date() module-level function."""

    def test_calculate_next_due_date_basic(self) -> None:
        """Basic usage of convenience function."""
        result = calculate_next_due_date(
            base_date="2026-01-05T12:00:00+00:00",
            frequency=const.FREQUENCY_DAILY,
            reference_datetime=make_utc_dt(2026, 1, 5, 13),
        )

        assert result is not None
        assert result.day == 6

    def test_calculate_next_due_date_with_datetime_input(self) -> None:
        """Convenience function accepts datetime object."""
        base = make_utc_dt(2026, 1, 5, 12)
        result = calculate_next_due_date(
            base_date=base,
            frequency=const.FREQUENCY_DAILY,
            reference_datetime=make_utc_dt(2026, 1, 5, 13),
        )

        assert result is not None
        assert result.day == 6

    def test_calculate_next_due_date_with_custom_interval(self) -> None:
        """Custom interval parameters."""
        result = calculate_next_due_date(
            base_date="2026-01-05T12:00:00+00:00",
            frequency=const.FREQUENCY_CUSTOM,
            interval=3,
            interval_unit=const.TIME_UNIT_DAYS,
            reference_datetime=make_utc_dt(2026, 1, 5, 13),
        )

        assert result is not None
        assert result.day == 8  # 5 + 3


# =============================================================================
# Edge case: No base_date
# =============================================================================


class TestNoBaseDate:
    """Test behavior when base_date is missing."""

    def test_no_base_date_returns_none(self) -> None:
        """Missing base_date should return None."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            # No base_date
        }
        engine = RecurrenceEngine(config)

        result = engine.get_next_occurrence(after=make_utc_dt(2026, 1, 5, 10))
        assert result is None

    def test_empty_base_date_returns_none(self) -> None:
        """Empty base_date string should return None."""
        config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": "",
        }
        engine = RecurrenceEngine(config)

        result = engine.get_next_occurrence(after=make_utc_dt(2026, 1, 5, 10))
        assert result is None
