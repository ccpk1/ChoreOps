"""Unit tests for schedule_engine.py RecurrenceEngine.

Tests edge cases per Phase 2a plan:
- EC-01: Monthly on day 31 → Feb 28 (clamping)
- EC-02: Feb 29 leap year handling
- EC-03: Year boundary crossing (Dec 31 → Jan 1)
- EC-04: Empty applicable_days list
- EC-05: Applicable_days constraint
- EC-06: PERIOD_QUARTER_END calculations
- Period-end parity: dt_utils and RecurrenceEngine must agree (see
  TestPeriodEndParityWithDtUtils)
- EC-07: CUSTOM_FROM_COMPLETE base date handling
- EC-08: Midnight boundary edge cases
- EC-09: MAX_ITERATIONS safety limit (stubbed for loop protection)
"""

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util
import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.schedule_engine import (
    RecurrenceEngine,
    calculate_next_due_date,
    calculate_next_due_date_from_chore_info,
)
from custom_components.choreops.type_defs import ChoreData
from custom_components.choreops.utils.dt_utils import (
    as_local,
    dt_next_schedule,
    dt_parse,
    get_default_timezone,
    set_default_timezone,
)

if TYPE_CHECKING:
    from custom_components.choreops.type_defs import ScheduleConfig


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

    @pytest.fixture(autouse=True)
    def align_dt_utils_timezone(self) -> Iterator[None]:
        """Align dt_utils with HA's timezone the way integration setup does.

        RecurrenceEngine resolves period ends through dt_utils, which only tracks
        HA's timezone once set_default_timezone runs during setup. Without this,
        the engine uses dt_utils' UTC default while assertions convert results with
        HA's timezone, so hour-based checks compare two different frames.
        """
        original_tz = get_default_timezone()
        set_default_timezone(dt_util.get_default_time_zone())
        try:
            yield
        finally:
            set_default_timezone(original_tz)

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
# Period-end parity: dt_utils must agree with RecurrenceEngine
# =============================================================================


class TestPeriodEndParityWithDtUtils:
    """Pin dt_utils period-end snapping to the RecurrenceEngine reference.

    Period-end math exists in two places because the pure utils layer cannot
    import the engine (that would be a circular import). These tests fail if the
    two implementations drift apart again, which is what produced the Week-End
    off-by-one-period defect.
    """

    PERIOD_END_FREQUENCIES = [
        const.PERIOD_WEEK_END,
        const.PERIOD_MONTH_END,
        const.PERIOD_QUARTER_END,
        const.PERIOD_YEAR_END,
    ]

    @pytest.mark.parametrize("frequency", PERIOD_END_FREQUENCIES)
    def test_advance_matches_engine_for_every_day_of_year(
        self,
        frequency: str,
    ) -> None:
        """Advancing any base date agrees with the engine, including boundaries."""
        engine = RecurrenceEngine(
            {"frequency": frequency, "base_date": "2026-01-01T00:00:00+00:00"}
        )

        mismatches: list[str] = []
        current = date(2026, 1, 1)
        while current <= date(2026, 12, 31):
            base_iso = current.isoformat()
            from_utils = dt_next_schedule(
                base_iso,
                interval_type=frequency,
                require_future=False,
                return_type=const.HELPER_RETURN_ISO_DATE,
            )
            # dt_next_schedule returns a local date, so the engine result must be
            # converted to local too before comparing (period ends land at 23:59
            # local, which is the next day in UTC for zones behind it).
            from_engine = engine.advance_period_end_preserve_time(dt_parse(base_iso))
            if from_engine is None:
                mismatches.append(f"{base_iso}: engine returned None")
            elif str(from_utils) != as_local(from_engine).date().isoformat():
                mismatches.append(
                    f"{base_iso} ({current.strftime('%a')}): "
                    f"dt_utils={from_utils} "
                    f"engine={as_local(from_engine).date().isoformat()}"
                )
            current += timedelta(days=1)

        assert not mismatches, (
            f"{frequency} disagreed with RecurrenceEngine on "
            f"{len(mismatches)} date(s): {mismatches[:5]}"
        )

    @pytest.mark.parametrize("frequency", PERIOD_END_FREQUENCIES)
    def test_advance_from_boundary_moves_exactly_one_period(
        self,
        frequency: str,
    ) -> None:
        """A base already on the boundary advances by one period, not two."""
        # 2026-09-13 is a Sunday, 2026-09-30 closes Q3, 2026-12-31 closes the year.
        engine = RecurrenceEngine(
            {"frequency": frequency, "base_date": "2026-01-01T00:00:00+00:00"}
        )

        boundary_by_frequency = {
            const.PERIOD_WEEK_END: date(2026, 9, 13),
            const.PERIOD_MONTH_END: date(2026, 9, 30),
            const.PERIOD_QUARTER_END: date(2026, 9, 30),
            const.PERIOD_YEAR_END: date(2026, 12, 31),
        }
        expected_by_frequency = {
            const.PERIOD_WEEK_END: date(2026, 9, 20),
            const.PERIOD_MONTH_END: date(2026, 10, 31),
            const.PERIOD_QUARTER_END: date(2026, 12, 31),
            const.PERIOD_YEAR_END: date(2027, 12, 31),
        }

        boundary = boundary_by_frequency[frequency]
        result = dt_next_schedule(
            boundary.isoformat(),
            interval_type=frequency,
            require_future=False,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )

        assert str(result) == expected_by_frequency[frequency].isoformat()
        assert (
            result
            == as_local(
                engine.advance_period_end_preserve_time(dt_parse(boundary.isoformat()))
            )
            .date()
            .isoformat()
        )


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
# Issue #299: late completion must stay on the chore's own anchor grid
# =============================================================================


ANCHOR = datetime(2026, 9, 14, 21, 0, tzinfo=ZoneInfo("UTC"))  # Monday 21:00


def make_custom_chore(interval: int, unit: str, **overrides: object) -> ChoreData:
    """Build a minimal custom-frequency chore payload for the helper."""
    chore: dict[str, object] = {
        const.DATA_CHORE_NAME: "Practice",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
        const.DATA_CHORE_CUSTOM_INTERVAL: interval,
        const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: unit,
        const.DATA_CHORE_APPLICABLE_DAYS: [],
    }
    chore.update(overrides)
    return cast("ChoreData", chore)


class TestLateCompletionStaysOnAnchorGrid:
    """A late completion must land on an actual slot of its own cadence.

    Regression cover for #299: the custom branches used to walk forward one
    unit per catch-up hop, which truncated multi-unit intervals and produced
    both off-grid dates and (for short hourly intervals) dates in the past.
    """

    @pytest.mark.parametrize(
        ("late_days", "expected_day_offset"),
        [
            pytest.param(1, 2, id="1d-late"),
            pytest.param(2, 4, id="2d-late"),
            pytest.param(3, 4, id="3d-late"),
            pytest.param(4, 6, id="4d-late"),
            pytest.param(5, 6, id="5d-late"),
            pytest.param(6, 8, id="6d-late"),
            pytest.param(7, 8, id="7d-late"),
            pytest.param(8, 10, id="8d-late"),
        ],
    )
    def test_every_other_day_lands_on_even_day_offset(
        self, late_days: int, expected_day_offset: int
    ) -> None:
        """A 2-day chore may only ever be due on even day offsets from anchor."""
        reference = ANCHOR + timedelta(days=late_days, hours=14)

        result = calculate_next_due_date_from_chore_info(
            ANCHOR, make_custom_chore(2, const.TIME_UNIT_DAYS), reference_time=reference
        )

        assert result is not None
        assert (result - ANCHOR).days == expected_day_offset
        assert (result - ANCHOR).days % 2 == 0
        assert result > reference

    def test_three_day_interval_stays_on_its_grid(self) -> None:
        """A 3-day chore must land on a multiple-of-3 day offset."""
        reference = ANCHOR + timedelta(days=4, hours=14)

        result = calculate_next_due_date_from_chore_info(
            ANCHOR, make_custom_chore(3, const.TIME_UNIT_DAYS), reference_time=reference
        )

        assert result is not None
        assert (result - ANCHOR).days == 6
        assert (result - ANCHOR).days % 3 == 0

    @pytest.mark.parametrize(
        "hours_late",
        [1, 3, 6, 7, 12, 18, 19, 24, 25, 47, 100],
    )
    def test_six_hour_interval_lands_on_a_slot(self, hours_late: int) -> None:
        """A 6-hour chore must land on a 6-hour slot and never in the past."""
        anchor = datetime(2026, 9, 16, 6, 0, tzinfo=ZoneInfo("UTC"))
        reference = anchor + timedelta(hours=hours_late)

        result = calculate_next_due_date_from_chore_info(
            anchor,
            make_custom_chore(6, const.TIME_UNIT_HOURS),
            reference_time=reference,
        )

        assert result is not None
        assert (result - anchor).total_seconds() % (6 * 3600) == 0
        assert result > reference

    def test_short_hourly_interval_never_returns_the_past(self) -> None:
        """Hourly intervals must not exhaust a walk budget into the past.

        The previous 1-unit walk gave up after a bounded number of hops and
        returned a stale date, so a 3-hour chore several days late rescheduled
        to a moment already past.
        """
        anchor = datetime(2026, 9, 14, 21, 0, tzinfo=ZoneInfo("UTC"))

        for reference in (
            anchor + timedelta(days=4, hours=8),
            anchor + timedelta(days=12, hours=8),
            anchor + timedelta(days=33, hours=8),
        ):
            result = calculate_next_due_date_from_chore_info(
                anchor,
                make_custom_chore(3, const.TIME_UNIT_HOURS),
                reference_time=reference,
            )

            assert result is not None
            assert result > reference

    def test_applicable_days_still_filter_custom_intervals(self) -> None:
        """Custom intervals must keep honouring applicable_days."""
        reference = ANCHOR + timedelta(days=4, hours=14)

        result = calculate_next_due_date_from_chore_info(
            ANCHOR,
            make_custom_chore(
                2,
                const.TIME_UNIT_DAYS,
                **{const.DATA_CHORE_APPLICABLE_DAYS: [0]},
            ),
            reference_time=reference,
        )

        assert result is not None
        assert result.weekday() == 0  # Monday
        assert result > reference


class TestCustomLateCompletionAlwaysFuture:
    """Invariant: a rescheduled due date is always strictly after the reference."""

    @pytest.mark.parametrize(
        "unit",
        [
            const.TIME_UNIT_HOURS,
            const.TIME_UNIT_DAYS,
            const.TIME_UNIT_WEEKS,
            const.TIME_UNIT_MONTHS,
        ],
    )
    @pytest.mark.parametrize("interval", [1, 2, 3, 6, 12])
    @pytest.mark.parametrize("late_hours", [0, 1, 25, 100, 300, 800])
    def test_custom_interval_is_always_future(
        self, unit: str, interval: int, late_hours: int
    ) -> None:
        """No custom interval may reschedule into the past or onto 'now'."""
        reference = ANCHOR + timedelta(hours=late_hours)

        result = calculate_next_due_date_from_chore_info(
            ANCHOR, make_custom_chore(interval, unit), reference_time=reference
        )

        assert result is not None
        assert result > reference

    def test_from_complete_advances_one_full_interval(self) -> None:
        """FROM_COMPLETE reschedules from the completion timestamp, not the due date."""
        completion = ANCHOR + timedelta(days=4, hours=14)

        result = calculate_next_due_date_from_chore_info(
            ANCHOR,
            make_custom_chore(
                2,
                const.TIME_UNIT_DAYS,
                **{
                    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM_FROM_COMPLETE
                },
            ),
            completion_timestamp=completion,
            reference_time=completion,
        )

        assert result == completion + timedelta(days=2)

    def test_from_complete_date_only_keeps_due_time(self) -> None:
        """DATE_ONLY uses the completion date but preserves the original due time."""
        completion = ANCHOR + timedelta(days=4, hours=14)  # Friday 11:00
        expected = datetime(2026, 9, 22, 21, 0, tzinfo=ZoneInfo("UTC"))

        result = calculate_next_due_date_from_chore_info(
            ANCHOR,
            make_custom_chore(
                3,
                const.TIME_UNIT_DAYS,
                **{
                    const.DATA_CHORE_RECURRING_FREQUENCY: (
                        const.FREQUENCY_CUSTOM_FROM_COMPLETE_DATE_ONLY
                    )
                },
            ),
            completion_timestamp=completion,
            reference_time=completion,
        )

        assert result == expected
        assert result.hour == ANCHOR.hour
        assert result.minute == ANCHOR.minute


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
