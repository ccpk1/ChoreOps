"""Schedule Engine for ChoreOps.

Unified scheduling engine using a hybrid approach:
- `dateutil.rrule` for standard patterns (DAILY, WEEKLY, period-ends)
- `dateutil.relativedelta` for month/year clamping (Jan 31 + 1 month = Feb 28)

IMPORTANT: This module must NOT import from coordinator.py to avoid circular imports.
Only import from const.py, type_defs.py, and standard libraries.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

from dateutil.relativedelta import relativedelta
from dateutil.rrule import (
    DAILY,
    FR,
    MO,
    MONTHLY,
    SA,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    YEARLY,
    rrule,
)

from .. import const
from ..utils.dt_utils import (
    as_local,
    as_utc,
    dt_add_interval,
    dt_next_schedule,
    dt_now_local,
    dt_now_utc,
    dt_parse,
    parse_daily_multi_times,
    start_of_local_day,
)

if TYPE_CHECKING:
    from ..type_defs import ChoreData, ScheduleConfig


class RecurrenceEngine:
    """Unified scheduling engine using dateutil.rrule with ChoreOps extensions.

    Handles all frequency types:
    - Standard: DAILY, WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY, YEARLY
    - Custom intervals: N hours/days/weeks/months from base date
    - Period-ends: DAY_END, WEEK_END, MONTH_END, QUARTER_END, YEAR_END

    Uses rrule for pattern-based recurrence and relativedelta for clamping
    (e.g., Jan 31 + 1 month = Feb 28, not skipped).
    """

    # Mapping from ChoreOps frequency constants to rrule frequencies
    FREQUENCY_TO_RRULE: ClassVar[dict[str, int]] = {
        const.FREQUENCY_DAILY: DAILY,
        const.FREQUENCY_WEEKLY: WEEKLY,
        const.FREQUENCY_BIWEEKLY: WEEKLY,  # interval=2
        const.FREQUENCY_MONTHLY: MONTHLY,
        const.FREQUENCY_QUARTERLY: MONTHLY,  # interval=3
        const.FREQUENCY_YEARLY: YEARLY,
    }

    # Frequencies that need clamping (relativedelta instead of rrule)
    CLAMPING_FREQUENCIES: ClassVar[set[str]] = {
        const.FREQUENCY_MONTHLY,
        const.FREQUENCY_QUARTERLY,
        const.FREQUENCY_YEARLY,
        const.FREQUENCY_CUSTOM,
        const.FREQUENCY_CUSTOM_FROM_COMPLETE,
        const.FREQUENCY_CUSTOM_1_MONTH,
        const.FREQUENCY_CUSTOM_1_QUARTER,
        const.FREQUENCY_CUSTOM_1_YEAR,
    }

    # Period-end frequencies (special handling)
    PERIOD_END_FREQUENCIES: ClassVar[set[str]] = {
        const.PERIOD_DAY_END,
        const.PERIOD_WEEK_END,
        const.PERIOD_MONTH_END,
        const.PERIOD_QUARTER_END,
        const.PERIOD_YEAR_END,
    }

    def __init__(self, config: ScheduleConfig) -> None:
        """Initialize the recurrence engine with configuration.

        Args:
            config: ScheduleConfig TypedDict containing frequency, interval, etc.

        Note:
            Invalid interval values (<=0) are coerced to 1.
            Invalid applicable_days entries (outside 0-6) are filtered out.
        """
        self._config = config
        self._frequency = config.get("frequency", const.FREQUENCY_NONE)

        # Validate interval: must be positive
        interval = config.get("interval", 1)
        self._interval = max(1, interval) if interval else 1

        self._interval_unit = config.get("interval_unit", const.TIME_UNIT_DAYS)

        # Validate applicable_days: filter to valid weekday range 0-6
        raw_days = config.get("applicable_days", [])
        self._applicable_days = [d for d in raw_days if 0 <= d <= 6]

        # Parse base_date to datetime (UTC)
        base_date_str = config.get("base_date")
        self._base_date: datetime | None = None
        if base_date_str:
            self._base_date = self._parse_to_utc(base_date_str)

        # DAILY_MULTI times (pipe-separated string, e.g., "08:00|12:00|18:00")
        self._daily_multi_times = config.get("daily_multi_times", "")

    def get_next_occurrence(
        self, after: datetime | None = None, require_future: bool = True
    ) -> datetime | None:
        """Calculate the next occurrence after a reference datetime.

        Args:
            after: Reference datetime (UTC). If None, uses current time.
            require_future: If True, result must be strictly after `after`.

        Returns:
            Next occurrence as UTC datetime, or None if calculation fails.
        """
        if not self._base_date:
            const.LOGGER.debug(
                "RecurrenceEngine: No base_date provided, cannot calculate"
            )
            return None

        if self._frequency == const.FREQUENCY_NONE:
            const.LOGGER.debug(
                "RecurrenceEngine: Frequency is NONE, no calculation needed"
            )
            return None

        # Default reference to now if not provided
        reference_utc = after or dt_now_utc()

        # Route to appropriate handler
        if self._frequency == const.FREQUENCY_DAILY_MULTI:
            return self._calculate_multi_daily(reference_utc)
        if self._frequency in self.PERIOD_END_FREQUENCIES:
            return self._calculate_period_end(reference_utc, require_future)
        if self._is_custom_frequency():
            return self._calculate_with_relativedelta(reference_utc, require_future)
        if self._needs_clamping():
            return self._calculate_with_relativedelta(reference_utc, require_future)
        return self._calculate_with_rrule(reference_utc, require_future)

    def get_occurrences(
        self, start: datetime, end: datetime, limit: int = 100
    ) -> list[datetime]:
        """Generate occurrences within a date range.

        Args:
            start: Range start (UTC).
            end: Range end (UTC).
            limit: Maximum occurrences to return (safety limit).

        Returns:
            List of occurrence datetimes (UTC).
        """
        if not self._base_date or self._frequency == const.FREQUENCY_NONE:
            return []

        occurrences: list[datetime] = []
        current = self.get_next_occurrence(after=start, require_future=False)

        iteration = 0
        while current and current <= end and iteration < limit:
            if current >= start:
                occurrences.append(current)
            current = self.get_next_occurrence(after=current, require_future=True)
            iteration += 1

        return occurrences

    def has_missed_occurrences(
        self,
        last_completion: datetime,
        current_completion: datetime,
    ) -> bool:
        """Check if any scheduled occurrences were skipped between completions.

        Used for schedule-aware streak calculation. A streak continues if no
        scheduled occurrences were missed between the last completion and now.

        Args:
            last_completion: Timestamp of previous approval (UTC).
            current_completion: Timestamp of current approval (UTC).

        Returns:
            True if at least one occurrence was missed (streak breaks).
            False if current completion is on-time or early (streak continues).

        Examples:
            Daily chore: last=Jan 1, current=Jan 2 → False (on-time)
            Daily chore: last=Jan 1, current=Jan 3 → True (missed Jan 2)
            Every 3 days: last=Jan 1, current=Jan 3 → False (Jan 2 not scheduled)
            Weekly Monday: last=Jan 6, current=Jan 13 → False (consecutive Mondays)
        """
        # No schedule = no missed occurrences
        if self._frequency == const.FREQUENCY_NONE:
            return False

        # Get all occurrences between completions
        occurrences = self.get_occurrences(
            start=last_completion,
            end=current_completion,
            limit=100,
        )

        # Filter to occurrences strictly between the two completion times.
        # If any such occurrence exists, it was missed.
        #
        # NOTE: rrule.after() truncates microseconds to 0, so we must do the same
        # for current_completion to ensure an occurrence falling at "now" (same
        # second but different microseconds) is not incorrectly counted as missed.
        current_truncated = current_completion.replace(microsecond=0)
        missed = [
            occ for occ in occurrences if last_completion < occ < current_truncated
        ]

        return len(missed) > 0

    def to_rrule_string(self) -> str:
        """Generate RFC 5545 RRULE string for iCal export.

        Returns:
            RRULE string (e.g., "FREQ=WEEKLY;INTERVAL=1;BYDAY=SU")
            or empty string if not representable.
        """
        freq = self._frequency

        if freq == const.FREQUENCY_DAILY:
            return "FREQ=DAILY;INTERVAL=1"
        if freq == const.FREQUENCY_WEEKLY:
            return self._rrule_string_with_weekdays("WEEKLY", 1)
        if freq == const.FREQUENCY_BIWEEKLY:
            return self._rrule_string_with_weekdays("WEEKLY", 2)
        if freq == const.FREQUENCY_MONTHLY:
            return "FREQ=MONTHLY;INTERVAL=1"
        if freq == const.FREQUENCY_QUARTERLY:
            return "FREQ=MONTHLY;INTERVAL=3"
        if freq == const.FREQUENCY_YEARLY:
            return "FREQ=YEARLY;INTERVAL=1"
        if freq == const.PERIOD_WEEK_END:
            return "FREQ=WEEKLY;BYDAY=SU"
        if freq == const.PERIOD_MONTH_END:
            return "FREQ=MONTHLY;BYMONTHDAY=-1"
        if freq == const.PERIOD_QUARTER_END:
            return "FREQ=YEARLY;BYMONTH=3,6,9,12;BYMONTHDAY=-1"
        if freq == const.PERIOD_YEAR_END:
            return "FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=-1"

        # Custom frequencies and DAILY_MULTI don't have standard RRULE representation
        return ""

    # =========================================================================
    # Private: rrule-based calculation (DAILY, WEEKLY, BIWEEKLY)
    # =========================================================================

    def _calculate_with_rrule(
        self, reference_utc: datetime, require_future: bool
    ) -> datetime | None:
        """Calculate next occurrence using rrule (for non-clamping frequencies).

        Args:
            reference_utc: Reference datetime (UTC).
            require_future: If True, result must be after reference.

        Returns:
            Next occurrence as UTC datetime.
        """
        freq = self._frequency
        base_local = as_local(self._base_date) if self._base_date else None
        if not base_local:
            return None

        # Determine rrule frequency and interval
        rrule_freq = self.FREQUENCY_TO_RRULE.get(freq, DAILY)
        interval = 2 if freq == const.FREQUENCY_BIWEEKLY else 1

        # Map applicable_days to rrule weekday constants for native support.
        # NOTE: rrule handles weekday filtering natively via byweekday param,
        # while _calculate_with_relativedelta uses _snap_to_applicable_day
        # post-calculation. Both achieve same result, different mechanisms.
        rrule_weekdays = None
        if self._applicable_days:
            day_map = [MO, TU, WE, TH, FR, SA, SU]
            rrule_weekdays = [day_map[d] for d in self._applicable_days if 0 <= d <= 6]

        # Build rrule with native byweekday support
        # Type stubs expect Literal[0-6], but rrule accepts int at runtime
        rule = rrule(
            rrule_freq,  # type: ignore[arg-type]
            interval=interval,
            dtstart=base_local,
            byweekday=rrule_weekdays,  # Native weekday filtering
        )

        # Get next occurrence after reference (converted to local for rrule)
        reference_local = as_local(reference_utc)
        next_occurrence = rule.after(reference_local, inc=not require_future)

        if next_occurrence:
            return as_utc(next_occurrence)
        return None

    # =========================================================================
    # Private: relativedelta-based calculation (clamping frequencies)
    # =========================================================================

    def _calculate_with_relativedelta(
        self, reference_utc: datetime, require_future: bool
    ) -> datetime | None:
        """Calculate next occurrence using relativedelta (for clamping behavior).

        Handles MONTHLY, QUARTERLY, YEARLY, and CUSTOM intervals.
        Preserves clamping: Jan 31 + 1 month = Feb 28 (not skipped).

        Performance: For fixed-length intervals (hours/days/weeks), uses
        mathematical fast-forward instead of iteration to avoid O(n) loops
        on old schedules.

        Args:
            reference_utc: Reference datetime (UTC).
            require_future: If True, result must be after reference.

        Returns:
            Next occurrence as UTC datetime.
        """
        if not self._base_date:
            return None

        result = self._base_date

        # OPTIMIZATION: Fast-forward for fixed-length intervals
        # Only loop for variable-length units (months/years) where clamping matters
        if self._is_fixed_interval():
            result = self._fast_forward_fixed_interval(result, reference_utc)
        else:
            # Variable intervals (months/years) - must iterate for clamping
            delta = self._get_relativedelta()
            iteration = 0
            while iteration < const.MAX_DATE_CALCULATION_ITERATIONS:
                iteration += 1
                if require_future and result <= reference_utc:
                    result = result + delta
                    continue
                if not require_future and result < reference_utc:
                    result = result + delta
                    continue
                break

            if iteration >= const.MAX_DATE_CALCULATION_ITERATIONS:
                const.LOGGER.warning(
                    "RecurrenceEngine: Max iterations reached for %s", self._frequency
                )

        # Final adjustment if we need strictly future
        if require_future and result <= reference_utc:
            result = result + self._get_relativedelta()

        # Apply applicable_days constraint if configured
        if self._applicable_days:
            result = self._snap_to_applicable_day(result)

        return result

    def _is_fixed_interval(self) -> bool:
        """Check if the interval has a fixed length (hours/days/weeks).

        Fixed intervals can be fast-forwarded mathematically.
        Variable intervals (months/years) require iteration for clamping.
        """
        # Standard frequencies that are variable
        if self._frequency in {
            const.FREQUENCY_MONTHLY,
            const.FREQUENCY_QUARTERLY,
            const.FREQUENCY_YEARLY,
            const.FREQUENCY_CUSTOM_1_MONTH,
            const.FREQUENCY_CUSTOM_1_QUARTER,
            const.FREQUENCY_CUSTOM_1_YEAR,
        }:
            return False

        # Custom frequencies - check the unit
        if self._frequency in {
            const.FREQUENCY_CUSTOM,
            const.FREQUENCY_CUSTOM_FROM_COMPLETE,
        }:
            return self._interval_unit in {
                const.TIME_UNIT_HOURS,
                const.TIME_UNIT_DAYS,
                const.TIME_UNIT_WEEKS,
            }

        # CUSTOM_1_WEEK is fixed
        if self._frequency == const.FREQUENCY_CUSTOM_1_WEEK:
            return True

        return False

    def _fast_forward_fixed_interval(
        self, base: datetime, reference: datetime
    ) -> datetime:
        """Fast-forward to the nearest occurrence using math (not iteration).

        For fixed-length intervals (hours/days/weeks), calculates the number
        of intervals mathematically to avoid O(n) iteration.

        Args:
            base: Starting datetime.
            reference: Target datetime to catch up to.

        Returns:
            Datetime at or just before reference.
        """
        if base >= reference:
            return base

        # Calculate interval in seconds
        interval_seconds = self._get_interval_seconds()
        if interval_seconds <= 0:
            return base

        # Calculate how many complete intervals fit
        diff_seconds = (reference - base).total_seconds()
        num_intervals = int(diff_seconds // interval_seconds)

        # Jump forward
        _delta = self._get_relativedelta()
        # Use multiplication for fixed deltas (hours/days/weeks)
        if self._interval_unit == const.TIME_UNIT_HOURS:
            result = base + timedelta(hours=self._interval * num_intervals)
        elif self._interval_unit == const.TIME_UNIT_DAYS:
            result = base + timedelta(days=self._interval * num_intervals)
        elif self._interval_unit == const.TIME_UNIT_WEEKS:
            result = base + timedelta(weeks=self._interval * num_intervals)
        elif self._frequency == const.FREQUENCY_CUSTOM_1_WEEK:
            result = base + timedelta(weeks=num_intervals)
        else:
            # Fallback to relativedelta multiplication
            result = base + relativedelta(days=num_intervals)

        return result

    def _get_interval_seconds(self) -> float:
        """Get the interval length in seconds for fixed intervals."""
        if self._frequency == const.FREQUENCY_CUSTOM_1_WEEK:
            return 7 * 24 * 3600

        unit = self._interval_unit
        interval = self._interval

        if unit == const.TIME_UNIT_HOURS:
            return interval * 3600
        if unit == const.TIME_UNIT_DAYS:
            return interval * 24 * 3600
        if unit == const.TIME_UNIT_WEEKS:
            return interval * 7 * 24 * 3600

        return 0  # Variable-length interval

    def _get_relativedelta(self) -> relativedelta:
        """Build relativedelta from frequency/interval configuration.

        Returns:
            relativedelta object for the configured frequency.
        """
        freq = self._frequency

        # Standard frequencies
        if freq == const.FREQUENCY_MONTHLY:
            return relativedelta(months=1)
        if freq == const.FREQUENCY_QUARTERLY:
            return relativedelta(months=3)
        if freq == const.FREQUENCY_YEARLY:
            return relativedelta(years=1)

        # Custom_1_* shortcuts
        if freq == const.FREQUENCY_CUSTOM_1_MONTH:
            return relativedelta(months=1)
        if freq == const.FREQUENCY_CUSTOM_1_QUARTER:
            return relativedelta(months=3)
        if freq == const.FREQUENCY_CUSTOM_1_YEAR:
            return relativedelta(years=1)
        if freq == const.FREQUENCY_CUSTOM_1_WEEK:
            return relativedelta(weeks=1)

        # Custom intervals (FREQUENCY_CUSTOM and FREQUENCY_CUSTOM_FROM_COMPLETE)
        unit = self._interval_unit
        interval = self._interval

        if unit == const.TIME_UNIT_HOURS:
            return relativedelta(hours=interval)
        if unit == const.TIME_UNIT_DAYS:
            return relativedelta(days=interval)
        if unit == const.TIME_UNIT_WEEKS:
            return relativedelta(weeks=interval)
        if unit == const.TIME_UNIT_MONTHS:
            return relativedelta(months=interval)
        if unit == const.TIME_UNIT_QUARTERS:
            return relativedelta(months=interval * const.MONTHS_PER_QUARTER)
        if unit == const.TIME_UNIT_YEARS:
            return relativedelta(years=interval)

        # Default to 1 day if unknown
        return relativedelta(days=1)

    # =========================================================================
    # Private: Period-end calculation
    # =========================================================================

    def _calculate_period_end(
        self, reference_utc: datetime, require_future: bool
    ) -> datetime | None:
        """Calculate next period-end occurrence.

        Handles DAY_END, WEEK_END, MONTH_END, QUARTER_END, YEAR_END.

        Args:
            reference_utc: Reference datetime (UTC).
            require_future: If True, result must be after reference.

        Returns:
            Next period-end as UTC datetime.
        """
        freq = self._frequency
        reference_local = as_local(reference_utc)

        if freq == const.PERIOD_DAY_END:
            result = self._get_day_end(reference_local)
        elif freq == const.PERIOD_WEEK_END:
            result = self._get_week_end(reference_local)
        elif freq == const.PERIOD_MONTH_END:
            result = self._get_month_end(reference_local)
        elif freq == const.PERIOD_QUARTER_END:
            result = self._get_quarter_end(reference_local)
        elif freq == const.PERIOD_YEAR_END:
            result = self._get_year_end(reference_local)
        else:
            return None

        # If require_future and result is not after reference, advance one period
        if require_future:
            iteration = 0
            while (
                result <= reference_local
                and iteration < const.MAX_DATE_CALCULATION_ITERATIONS
            ):
                iteration += 1
                previous = result

                # Advance by one period
                if freq == const.PERIOD_DAY_END:
                    result = self._get_day_end(result + timedelta(days=1))
                elif freq == const.PERIOD_WEEK_END:
                    result = self._get_week_end(result + timedelta(days=1))
                elif freq == const.PERIOD_MONTH_END:
                    result = self._get_month_end(result + relativedelta(months=1))
                elif freq == const.PERIOD_QUARTER_END:
                    result = self._get_quarter_end(result + relativedelta(months=3))
                elif freq == const.PERIOD_YEAR_END:
                    result = self._get_year_end(result + relativedelta(years=1))

                # Break infinite loop if result didn't change
                if result == previous:
                    result = result + timedelta(hours=1)
                    # Recalculate period-end for all frequency types
                    if freq == const.PERIOD_DAY_END:
                        result = self._get_day_end(result)
                    elif freq == const.PERIOD_WEEK_END:
                        result = self._get_week_end(result)
                    elif freq == const.PERIOD_MONTH_END:
                        result = self._get_month_end(result)
                    elif freq == const.PERIOD_QUARTER_END:
                        result = self._get_quarter_end(result)
                    elif freq == const.PERIOD_YEAR_END:
                        result = self._get_year_end(result)

        return as_utc(result)

    def _get_day_end(self, dt: datetime) -> datetime:
        """Get end of day (23:59:00) for given datetime.

        Uses dt_util.start_of_local_day + timedelta for DST safety.
        Direct .replace() can fail during DST transitions.
        """
        start_of_day = start_of_local_day(dt)
        return start_of_day + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    def _get_week_end(self, dt: datetime) -> datetime:
        """Get end of week (Sunday 23:59:00) for given datetime.

        Uses dt_util.start_of_local_day + timedelta for DST safety.
        """
        # Calculate days until Sunday (0=Mon, 6=Sun)
        days_until_sunday = (const.SUNDAY_WEEKDAY_INDEX - dt.weekday()) % 7
        # If today is Sunday and days_until_sunday is 0, that's correct (this Sunday)
        sunday = dt + timedelta(days=days_until_sunday)

        # Use start_of_local_day for DST safety
        start_of_sunday = start_of_local_day(sunday)
        return start_of_sunday + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    def _get_month_end(self, dt: datetime) -> datetime:
        """Get end of month (last day 23:59:00) for given datetime.

        Uses dt_util.start_of_local_day + timedelta for DST safety.
        """
        last_day = monthrange(dt.year, dt.month)[1]
        month_end_date = dt.replace(day=last_day)
        start_of_last_day = start_of_local_day(month_end_date)
        return start_of_last_day + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    def _get_quarter_end(self, dt: datetime) -> datetime:
        """Get end of quarter (last day of Mar/Jun/Sep/Dec 23:59:00).

        Q1: Mar 31, Q2: Jun 30, Q3: Sep 30, Q4: Dec 31
        Uses dt_util.start_of_local_day + timedelta for DST safety.
        """
        # Calculate last month of current quarter (3, 6, 9, 12)
        last_month = (
            (dt.month - 1) // const.MONTHS_PER_QUARTER + 1
        ) * const.MONTHS_PER_QUARTER
        last_day = monthrange(dt.year, last_month)[1]
        quarter_end_date = dt.replace(month=last_month, day=last_day)
        start_of_last_day = start_of_local_day(quarter_end_date)
        return start_of_last_day + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    def _get_year_end(self, dt: datetime) -> datetime:
        """Get end of year (December 31 23:59:00) for given datetime.

        Uses dt_util.start_of_local_day + timedelta for DST safety.
        """
        year_end_date = dt.replace(
            month=const.LAST_MONTH_OF_YEAR, day=const.LAST_DAY_OF_DECEMBER
        )
        start_of_last_day = start_of_local_day(year_end_date)
        return start_of_last_day + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    # =========================================================================
    # Private: applicable_days handling
    # =========================================================================

    def _snap_to_applicable_day(self, dt: datetime) -> datetime:
        """Advance datetime to next applicable weekday.

        Args:
            dt: Input datetime (UTC).

        Returns:
            Datetime advanced to an applicable weekday, preserving time.
        """
        if not self._applicable_days:
            return dt

        local_dt = as_local(dt)
        iteration = 0

        while (
            local_dt.weekday() not in self._applicable_days
            and iteration < const.MAX_DATE_CALCULATION_ITERATIONS
        ):
            local_dt = local_dt + timedelta(days=1)
            iteration += 1

        return as_utc(local_dt)

    # =========================================================================
    # Private: Helper methods
    # =========================================================================

    def _is_custom_frequency(self) -> bool:
        """Check if frequency is a custom interval type."""
        return self._frequency in {
            const.FREQUENCY_CUSTOM,
            const.FREQUENCY_CUSTOM_FROM_COMPLETE,
            const.FREQUENCY_CUSTOM_1_WEEK,
            const.FREQUENCY_CUSTOM_1_MONTH,
            const.FREQUENCY_CUSTOM_1_QUARTER,
            const.FREQUENCY_CUSTOM_1_YEAR,
        }

    def _needs_clamping(self) -> bool:
        """Check if frequency needs relativedelta (month-based arithmetic).

        Returns True for frequencies that require month/year clamping:
        - MONTHLY, QUARTERLY, YEARLY (standard frequencies)
        - CUSTOM, CUSTOM_FROM_COMPLETE (custom intervals)
        - CUSTOM_1_MONTH, CUSTOM_1_QUARTER, CUSTOM_1_YEAR (shortcuts)

        These ALWAYS use relativedelta for consistent month arithmetic,
        preserving clamping behavior (e.g., Jan 31 + 1 month = Feb 28).
        """
        # These frequencies always use relativedelta for month/year arithmetic
        return self._frequency in self.CLAMPING_FREQUENCIES

    def _parse_to_utc(self, dt_str: str) -> datetime | None:
        """Parse ISO datetime string to UTC datetime.

        Args:
            dt_str: ISO 8601 datetime string.

        Returns:
            UTC datetime or None if parsing fails.
        """
        try:
            parsed = dt_parse(dt_str)
            if parsed and isinstance(parsed, datetime):
                return as_utc(parsed)
        except (ValueError, TypeError):
            const.LOGGER.debug("RecurrenceEngine: Failed to parse datetime: %s", dt_str)
        return None

    def _rrule_string_with_weekdays(self, freq: str, interval: int) -> str:
        """Generate RRULE string with optional BYDAY clause.

        Args:
            freq: RRULE frequency string (WEEKLY, MONTHLY, etc.)
            interval: Interval value.

        Returns:
            RRULE string with BYDAY if applicable_days configured.
        """
        base = f"FREQ={freq};INTERVAL={interval}"
        if not self._applicable_days:
            return base

        day_map = {0: "MO", 1: "TU", 2: "WE", 3: "TH", 4: "FR", 5: "SA", 6: "SU"}
        days = ",".join(
            day_map[d] for d in sorted(self._applicable_days) if d in day_map
        )
        if days:
            return f"{base};BYDAY={days}"
        return base

    def _calculate_multi_daily(self, reference_utc: datetime) -> datetime | None:
        """Calculate next occurrence for DAILY_MULTI frequency.

        Handles multiple time slots per day (e.g., "08:00|12:00|18:00").
        Returns the next slot strictly after reference_utc.

        Args:
            reference_utc: Reference datetime (UTC) for slot comparison.

        Returns:
            Next slot datetime (UTC), or None if no valid times configured.
        """

        if not self._daily_multi_times:
            const.LOGGER.warning(
                "RecurrenceEngine: DAILY_MULTI frequency missing times string"
            )
            return None

        # Use base_date for date reference, or reference_utc date if no base
        if self._base_date:
            current_local = as_local(self._base_date)
        else:
            current_local = as_local(reference_utc)
        current_date = current_local.date()

        # Parse times with timezone awareness (returns local-aware datetimes)
        time_slots_local = parse_daily_multi_times(
            self._daily_multi_times,
            reference_date=current_date,
            timezone_info=const.DEFAULT_TIME_ZONE,
        )

        if not time_slots_local:
            const.LOGGER.warning(
                "RecurrenceEngine: DAILY_MULTI frequency has no valid times"
            )
            return None

        # Convert time slots to UTC for comparison
        time_slots_utc = [as_utc(dt) for dt in time_slots_local]

        # Find next available slot (must be strictly after reference time)
        for slot_utc in time_slots_utc:
            if slot_utc > reference_utc:
                return slot_utc

        # Past all slots today, wrap to first slot tomorrow
        tomorrow_date = current_date + timedelta(days=1)
        tomorrow_slots = parse_daily_multi_times(
            self._daily_multi_times,
            reference_date=tomorrow_date,
            timezone_info=const.DEFAULT_TIME_ZONE,
        )
        if tomorrow_slots:
            return as_utc(tomorrow_slots[0])

        const.LOGGER.warning(
            "RecurrenceEngine: DAILY_MULTI failed to calculate next slot"
        )
        return None


# =============================================================================
# Module-level convenience functions
# =============================================================================


def add_interval(
    base_date: str | datetime,
    interval_unit: str,
    delta: int,
    end_of_period: str | None = None,
    require_future: bool = False,
    reference_datetime: datetime | None = None,
) -> datetime | None:
    """Add a time interval to a date and optionally adjust to period-end.

    This is the unified interval arithmetic function. It consolidates:
    - Basic interval addition (hours, days, weeks, months, quarters, years)
    - Period-end adjustments (DAY_END, WEEK_END, MONTH_END, QUARTER_END, YEAR_END)
    - Future-ensuring logic (loop until result > reference)

    Uses relativedelta for month/year arithmetic to preserve clamping behavior
    (e.g., Jan 31 + 1 month = Feb 28, not skipped).

    Args:
        base_date: Base date (ISO string or datetime).
        interval_unit: Time unit constant (TIME_UNIT_HOURS, TIME_UNIT_DAYS, etc.).
        delta: Number of units to add (can be negative for subtraction).
        end_of_period: Optional PERIOD_*_END constant to snap result to period end.
        require_future: If True, loop until result is strictly after reference_datetime.
        reference_datetime: Reference for require_future comparison (default: now).

    Returns:
        Result as UTC datetime, or None if base_date is invalid.

    Examples:
        # Add 3 days
        add_interval("2026-01-15T09:00:00", TIME_UNIT_DAYS, 3)
        → datetime(2026, 1, 18, 9, 0, tzinfo=UTC)

        # Add 1 month with clamping
        add_interval("2026-01-31T09:00:00", TIME_UNIT_MONTHS, 1)
        → datetime(2026, 2, 28, 9, 0, tzinfo=UTC)

        # Add 0 days but snap to month end
        add_interval("2026-01-15T09:00:00", TIME_UNIT_DAYS, 0, PERIOD_MONTH_END)
        → datetime(2026, 1, 31, 23, 59, 0, tzinfo=UTC)
    """
    # Parse base_date
    if isinstance(base_date, datetime):
        base_dt = as_utc(base_date)
    else:
        try:
            parsed = dt_parse(base_date)
            if not parsed or not isinstance(parsed, datetime):
                const.LOGGER.error(
                    "add_interval: Could not parse base_date: %s", base_date
                )
                return None
            base_dt = as_utc(parsed)
        except (ValueError, TypeError) as err:
            const.LOGGER.error("add_interval: Invalid base_date %s: %s", base_date, err)
            return None

    # Calculate interval addition using relativedelta for consistent clamping
    if interval_unit == const.TIME_UNIT_MINUTES:
        result = base_dt + timedelta(minutes=delta)
    elif interval_unit == const.TIME_UNIT_HOURS:
        result = base_dt + timedelta(hours=delta)
    elif interval_unit == const.TIME_UNIT_DAYS:
        result = base_dt + timedelta(days=delta)
    elif interval_unit == const.TIME_UNIT_WEEKS:
        result = base_dt + timedelta(weeks=delta)
    elif interval_unit == const.TIME_UNIT_MONTHS:
        result = base_dt + relativedelta(months=delta)
    elif interval_unit == const.TIME_UNIT_QUARTERS:
        result = base_dt + relativedelta(months=delta * const.MONTHS_PER_QUARTER)
    elif interval_unit == const.TIME_UNIT_YEARS:
        result = base_dt + relativedelta(years=delta)
    else:
        const.LOGGER.warning(
            "add_interval: Unsupported interval_unit %s, defaulting to days",
            interval_unit,
        )
        result = base_dt + timedelta(days=delta)

    # Apply end_of_period adjustment if specified
    if end_of_period:
        result = _apply_period_end(result, end_of_period)

    # Handle require_future: loop until result > reference
    if require_future:
        ref_utc = reference_datetime or dt_now_utc()
        if not isinstance(ref_utc, datetime):
            ref_utc = dt_now_utc()
        ref_utc = as_utc(ref_utc)

        iteration = 0
        while result <= ref_utc and iteration < const.MAX_DATE_CALCULATION_ITERATIONS:
            iteration += 1
            previous = result

            # Add interval again
            if interval_unit == const.TIME_UNIT_MINUTES:
                result = result + timedelta(minutes=delta)
            elif interval_unit == const.TIME_UNIT_HOURS:
                result = result + timedelta(hours=delta)
            elif interval_unit == const.TIME_UNIT_DAYS:
                result = result + timedelta(days=delta)
            elif interval_unit == const.TIME_UNIT_WEEKS:
                result = result + timedelta(weeks=delta)
            elif interval_unit == const.TIME_UNIT_MONTHS:
                result = result + relativedelta(months=delta)
            elif interval_unit == const.TIME_UNIT_QUARTERS:
                result = result + relativedelta(months=delta * const.MONTHS_PER_QUARTER)
            elif interval_unit == const.TIME_UNIT_YEARS:
                result = result + relativedelta(years=delta)
            else:
                result = result + timedelta(days=delta)

            # Re-apply end_of_period
            if end_of_period:
                result = _apply_period_end(result, end_of_period)

            # Break infinite loop if result didn't change
            if result == previous:
                result = result + timedelta(hours=1)
                if end_of_period:
                    result = _apply_period_end(result, end_of_period)

        if iteration >= const.MAX_DATE_CALCULATION_ITERATIONS:
            const.LOGGER.warning(
                "add_interval: Max iterations reached. base=%s, unit=%s, delta=%s",
                base_date,
                interval_unit,
                delta,
            )

    return as_utc(result)


def _apply_period_end(dt: datetime, period: str) -> datetime:
    """Apply period-end adjustment to a datetime.

    Uses dt_util.start_of_local_day + timedelta for DST safety.

    Args:
        dt: Input datetime (any timezone).
        period: PERIOD_*_END constant.

    Returns:
        Datetime adjusted to the specified period end.
    """
    # Convert to local for period calculations
    local_dt = as_local(dt)

    if period == const.PERIOD_DAY_END:
        start = start_of_local_day(local_dt)
        return start + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    if period == const.PERIOD_WEEK_END:
        days_until_sunday = (const.SUNDAY_WEEKDAY_INDEX - local_dt.weekday()) % 7
        sunday = local_dt + timedelta(days=days_until_sunday)
        start = start_of_local_day(sunday)
        return start + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    if period == const.PERIOD_MONTH_END:
        last_day = monthrange(local_dt.year, local_dt.month)[1]
        month_end = local_dt.replace(day=last_day)
        start = start_of_local_day(month_end)
        return start + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    if period == const.PERIOD_QUARTER_END:
        last_month = (
            (local_dt.month - 1) // const.MONTHS_PER_QUARTER + 1
        ) * const.MONTHS_PER_QUARTER
        last_day = monthrange(local_dt.year, last_month)[1]
        quarter_end = local_dt.replace(month=last_month, day=last_day)
        start = start_of_local_day(quarter_end)
        return start + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    if period == const.PERIOD_YEAR_END:
        year_end = local_dt.replace(
            month=const.LAST_MONTH_OF_YEAR, day=const.LAST_DAY_OF_DECEMBER
        )
        start = start_of_local_day(year_end)
        return start + timedelta(
            hours=const.END_OF_DAY_HOUR,
            minutes=const.END_OF_DAY_MINUTE,
            seconds=const.END_OF_DAY_SECOND,
        )

    # Unknown period - return unchanged
    const.LOGGER.warning("_apply_period_end: Unknown period type: %s", period)
    return dt


def calculate_next_due_date(
    base_date: str | datetime,
    frequency: str,
    interval: int = 1,
    interval_unit: str = const.TIME_UNIT_DAYS,
    applicable_days: list[int] | None = None,
    reference_datetime: datetime | None = None,
) -> datetime | None:
    """Calculate next due date using RecurrenceEngine.

    Convenience function for common scheduling calculations.

    Args:
        base_date: Base date (ISO string or datetime).
        frequency: Frequency constant (FREQUENCY_*, PERIOD_*_END).
        interval: Interval count for FREQUENCY_CUSTOM.
        interval_unit: Time unit for FREQUENCY_CUSTOM.
        applicable_days: List of valid weekday integers (0=Mon, 6=Sun).
        reference_datetime: Reference for require_future calculation.

    Returns:
        Next occurrence as UTC datetime, or None.
    """
    base_str = base_date.isoformat() if isinstance(base_date, datetime) else base_date

    config: ScheduleConfig = {
        "frequency": frequency,
        "interval": interval,
        "interval_unit": interval_unit,
        "base_date": base_str,
        "applicable_days": applicable_days or [],
    }

    engine = RecurrenceEngine(config)
    return engine.get_next_occurrence(after=reference_datetime, require_future=True)


def calculate_next_due_date_from_chore_info(
    current_due_utc: datetime | None,
    chore_info: ChoreData,
    completion_timestamp: datetime | None = None,
    reference_time: datetime | None = None,
) -> datetime | None:
    """Calculate next due date for a chore based on frequency (pure calculation helper).

    Consolidated scheduling logic used by both chore-level and per-assignee rescheduling.

    Args:
        current_due_utc: Current due date (UTC datetime, can be None)
        chore_info: Chore data dict containing frequency and configuration
        completion_timestamp: Optional completion timestamp (UTC) for
            FREQUENCY_CUSTOM_FROM_COMPLETE mode. If provided, rescheduling
            uses this as base instead of current_due_utc.
        reference_time: Reference datetime for calculations. If None, defaults
            to now. Pass explicit time for deterministic/testable behavior.

    Returns:
        datetime: Next due date (UTC) or None if calculation failed
    """
    from typing import cast

    freq = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE)

    # Initialize custom frequency parameters (used for FREQUENCY_CUSTOM and
    # FREQUENCY_CUSTOM_FROM_COMPLETE)
    custom_interval: int | None = None
    custom_unit: str | None = None

    # Validate custom frequency parameters for CUSTOM frequencies
    if freq in (const.FREQUENCY_CUSTOM, const.FREQUENCY_CUSTOM_FROM_COMPLETE):
        custom_interval = chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL)
        custom_unit = chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT)
        if custom_interval is None or custom_unit not in [
            const.TIME_UNIT_HOURS,  # CFE-2026-001: Support hours unit
            const.TIME_UNIT_DAYS,
            const.TIME_UNIT_WEEKS,
            const.TIME_UNIT_MONTHS,
        ]:
            const.LOGGER.warning(
                "Consolidation Helper - Invalid custom frequency for chore: %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return None

    # Skip if no frequency or no current due date
    if not freq or freq == const.FREQUENCY_NONE or current_due_utc is None:
        return None

    # Get applicable weekdays configuration
    raw_applicable = chore_info.get(
        const.DATA_CHORE_APPLICABLE_DAYS, const.DEFAULT_APPLICABLE_DAYS
    )
    applicable_days: list[int] = []
    if raw_applicable and isinstance(next(iter(raw_applicable), None), str):
        order = list(const.WEEKDAY_OPTIONS.keys())
        applicable_days = [
            order.index(day.lower()) for day in raw_applicable if day.lower() in order
        ]
    elif raw_applicable:
        applicable_days = [int(d) for d in raw_applicable]

    now_local = reference_time or dt_now_local()

    # Calculate next due date based on frequency
    if freq == const.FREQUENCY_CUSTOM:
        # FREQUENCY_CUSTOM: Always reschedule from current due date
        # Type narrowing: custom_unit and custom_interval are validated above
        assert custom_unit is not None
        assert custom_interval is not None

        next_due_utc = cast(
            "datetime",
            dt_add_interval(
                base_date=current_due_utc,
                interval_unit=custom_unit,
                delta=custom_interval,
                require_future=True,
                reference_datetime=reference_time,
                return_type=const.HELPER_RETURN_DATETIME,
            ),
        )
    elif freq == const.FREQUENCY_CUSTOM_FROM_COMPLETE:
        # CFE-2026-001 Feature 1: Reschedule from completion timestamp
        # Use completion_timestamp if available, fallback to current_due_utc
        # This allows intervals like "every 3 days from when they actually completed"
        assert custom_unit is not None
        assert custom_interval is not None
        base_date = completion_timestamp or current_due_utc
        if base_date is None:
            const.LOGGER.warning(
                "Consolidation Helper - No base date for CUSTOM_FROM_COMPLETE: %s",
                chore_info.get(const.DATA_CHORE_NAME),
            )
            return None
        next_due_utc = cast(
            "datetime",
            dt_add_interval(
                base_date=base_date,
                interval_unit=custom_unit,
                delta=custom_interval,
                require_future=True,
                return_type=const.HELPER_RETURN_DATETIME,
            ),
        )
    elif freq == const.FREQUENCY_DAILY_MULTI:
        # CFE-2026-001 Feature 2: Multiple times per day
        # Use dedicated helper for slot-based scheduling
        result = calculate_next_multi_daily_due(
            chore_info, current_due_utc, reference_time=reference_time
        )
        if result is None:
            return None
        next_due_utc = result
    else:
        next_due_utc = cast(
            "datetime",
            dt_next_schedule(
                base_date=current_due_utc,
                interval_type=freq,
                require_future=True,
                reference_datetime=now_local,
                return_type=const.HELPER_RETURN_DATETIME,
            ),
        )

    # Snap to applicable weekday using engine (handles internally)
    if applicable_days:
        snap_config: ScheduleConfig = {
            "frequency": const.FREQUENCY_DAILY,
            "base_date": next_due_utc.isoformat(),
            "applicable_days": applicable_days,
        }
        snap_engine = RecurrenceEngine(snap_config)
        next_due_utc = snap_engine._snap_to_applicable_day(next_due_utc)

    return next_due_utc


def calculate_next_multi_daily_due(
    chore_info: ChoreData,
    current_due_utc: datetime,
    reference_time: datetime | None = None,
) -> datetime | None:
    """Calculate next due datetime for DAILY_MULTI frequency.

    CFE-2026-001 Feature 2: Multiple times per day scheduling.
    Thin wrapper that delegates to RecurrenceEngine._calculate_multi_daily().

    Args:
        chore_info: Chore data containing daily_multi_times
        current_due_utc: Current due datetime (UTC)
        reference_time: Reference datetime (UTC) for slot comparison.
            If None, defaults to utcnow(). Pass explicit time for determinism.

    Returns:
        Next due datetime (UTC) - same day if before last slot,
        next day's first slot if past all slots today
    """
    times_raw = chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")
    # Normalize to str (could be list[str] from older data formats)
    times_str: str = (
        ",".join(times_raw) if isinstance(times_raw, list) else str(times_raw or "")
    )
    if not times_str:
        const.LOGGER.warning(
            "DAILY_MULTI frequency missing times string for chore: %s",
            chore_info.get(const.DATA_CHORE_NAME),
        )
        return None

    # Build config and delegate to RecurrenceEngine
    config: ScheduleConfig = {
        "frequency": const.FREQUENCY_DAILY_MULTI,
        "base_date": current_due_utc.isoformat(),
        "daily_multi_times": times_str,
    }

    engine = RecurrenceEngine(config)
    ref_utc = reference_time or dt_now_utc()
    return engine.get_next_occurrence(after=ref_utc, require_future=True)
