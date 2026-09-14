"""Tests for the shared missed-occurrence authority (Phase 1C).

`ChoreEngine.has_missed_occurrence_between` is the single place that answers "did
a scheduled occurrence go unmet inside this window". Two callers depend on it with
different anchors and different error policies:

- chore-level streaks (`calculate_streak`), anchored on the previous completion
- badge streaks (`StatisticsManager.has_missed_occurrence_since_advance`),
  anchored on the day the badge streak last advanced

These tests pin the helper's own contract, prove both callers agree, and lock the
two behaviours that used to live only inside `calculate_streak`: day-boundary
normalisation for day-based schedules, and the exemption for sub-day schedules.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import ChoreEngine
from custom_components.choreops.engines.schedule_engine import RecurrenceEngine
from custom_components.choreops.utils.dt_utils import (
    as_utc,
    get_default_timezone,
    set_default_timezone,
)

DAILY = {const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY}
WEEKLY_MONDAY = {
    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
    const.DATA_CHORE_APPLICABLE_DAYS: ["mon"],
}
EVERY_THREE_DAYS = {
    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
    const.DATA_CHORE_CUSTOM_INTERVAL: 3,
    const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: const.TIME_UNIT_DAYS,
}
HOURLY = {
    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
    const.DATA_CHORE_CUSTOM_INTERVAL: 1,
    const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: const.TIME_UNIT_HOURS,
}
OPEN_ENDED = {const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_NONE}


def utc_at(day: int, hour: int = 12, minute: int = 0) -> datetime:
    """Return a UTC datetime in March 2026."""
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def missed(
    chore_data: dict[str, Any],
    start: datetime,
    end: datetime,
    *,
    unusable_schedule_counts_as_miss: bool = False,
) -> bool:
    """Call the shared helper with explicit bounds."""
    return ChoreEngine.has_missed_occurrence_between(
        chore_data,
        window_start_utc=start,
        window_end_utc=end,
        unusable_schedule_counts_as_miss=unusable_schedule_counts_as_miss,
    )


def find_dst_transition(tz: ZoneInfo) -> tuple[str, str]:
    """Return the two consecutive local dates a DST transition spans."""
    day = date(2026, 1, 1)
    while day < date(2026, 12, 31):
        before = datetime.combine(day, time(12), tzinfo=tz).utcoffset()
        after = datetime.combine(
            day + timedelta(days=1), time(12), tzinfo=tz
        ).utcoffset()
        if before != after:
            return day.isoformat(), (day + timedelta(days=1)).isoformat()
        day += timedelta(days=1)
    raise AssertionError(f"No DST transition in 2026 for {tz}")


class TestWindowGuards:
    """Degenerate windows never report a miss."""

    @pytest.mark.parametrize(
        ("start", "end"),
        [
            pytest.param(utc_at(5), utc_at(1), id="inverted"),
            pytest.param(utc_at(5), utc_at(5), id="empty"),
        ],
    )
    def test_degenerate_window_is_not_a_miss(
        self,
        start: datetime,
        end: datetime,
    ) -> None:
        """An inverted or empty window has nothing to evaluate."""
        assert missed(DAILY, start, end) is False

    def test_open_ended_chore_never_reports_a_miss(self) -> None:
        """A chore with no schedule has no occurrences to miss.

        Its streak decay is a separate calendar rule inside `calculate_streak`,
        deliberately not unified here.
        """
        assert missed(OPEN_ENDED, utc_at(1), utc_at(30)) is False


class TestScheduleAwareDetection:
    """Detection follows the chore's schedule, not the calendar."""

    @pytest.mark.parametrize(
        ("chore_data", "start", "end", "expected", "case"),
        [
            pytest.param(
                DAILY,
                utc_at(1),
                utc_at(2),
                False,
                "daily_consecutive",
                id="daily_consecutive",
            ),
            pytest.param(
                DAILY, utc_at(1), utc_at(3), True, "daily_gap", id="daily_gap"
            ),
            pytest.param(
                DAILY,
                utc_at(1, 12),
                utc_at(1, 23),
                False,
                "daily_same_day",
                id="daily_same_day",
            ),
            pytest.param(
                WEEKLY_MONDAY,
                utc_at(2),
                utc_at(9),
                False,
                "weekly_consecutive",
                id="weekly_consecutive_mondays",
            ),
            pytest.param(
                WEEKLY_MONDAY,
                utc_at(2),
                utc_at(16),
                True,
                "weekly_skipped",
                id="weekly_skipped_monday",
            ),
            pytest.param(
                EVERY_THREE_DAYS,
                utc_at(1),
                utc_at(4),
                False,
                "every3_on_time",
                id="every_three_days_on_time",
            ),
            pytest.param(
                EVERY_THREE_DAYS,
                utc_at(1),
                utc_at(7),
                True,
                "every3_skipped",
                id="every_three_days_skipped",
            ),
        ],
    )
    def test_detection_follows_the_schedule(
        self,
        chore_data: dict[str, Any],
        start: datetime,
        end: datetime,
        expected: bool,
        case: str,
    ) -> None:
        """A miss is a scheduled occurrence that passed, not elapsed days."""
        assert missed(chore_data, start, end) is expected, case


class TestDayBoundaryNormalisation:
    """Day-based schedules are compared by local day, not wall-clock."""

    @pytest.mark.parametrize("hour", [0, 6, 12, 23])
    def test_time_of_day_does_not_change_the_verdict(self, hour: int) -> None:
        """Normalisation makes the answer stable within a day.

        Without it, a daily chore completed late one day and early the next would
        show a sub-day window that can contain an occurrence, producing a phantom
        miss between consecutive dates.
        """
        assert missed(DAILY, utc_at(1, hour, 30), utc_at(2, 12)) is False
        assert missed(DAILY, utc_at(1, hour, 30), utc_at(3, 12)) is True

    def test_consecutive_local_days_across_dst_are_not_a_miss(self) -> None:
        """A DST shift must not look like a skipped occurrence.

        The window spans 23 local hours here, so a naive wall-clock comparison
        misreads it. This is the normalisation's entire purpose.
        """
        tz = ZoneInfo("US/Pacific")
        original = get_default_timezone()
        set_default_timezone(tz)
        try:
            first, second = find_dst_transition(tz)
            day_one = date.fromisoformat(first)
            day_two = date.fromisoformat(second)

            start = as_utc(datetime.combine(day_one, time(23, 30), tzinfo=tz))
            end = as_utc(datetime.combine(day_two, time(0, 30), tzinfo=tz))
            assert (end - start) < timedelta(hours=2), "not a short DST window"

            assert missed(DAILY, start, end) is False

            # Same DST span, but a genuine day skipped: still a miss.
            day_three = day_two + timedelta(days=1)
            end_gap = as_utc(datetime.combine(day_three, time(0, 30), tzinfo=tz))
            assert missed(DAILY, start, end_gap) is True
        finally:
            set_default_timezone(original)


class TestSubDaySchedulesAreExempt:
    """Sub-day schedules are evaluated on real times, not day boundaries."""

    def test_hourly_occurrence_is_detected(self) -> None:
        """A 90-minute window spans more than one hourly occurrence."""
        assert missed(HOURLY, utc_at(1, 10), utc_at(1, 11, 30)) is True

    def test_hourly_window_shorter_than_the_interval_is_clean(self) -> None:
        """A 30-minute window contains no hourly occurrence."""
        assert missed(HOURLY, utc_at(1, 10), utc_at(1, 10, 30)) is False

    def test_hourly_schedule_is_not_day_normalised(self) -> None:
        """Day normalisation would collapse these bounds and hide the miss.

        Both bounds are on the same local day, so a day-aligned implementation
        would report no miss regardless of the elapsed hours.
        """
        assert missed(HOURLY, utc_at(1, 8), utc_at(1, 20)) is True


class TestCallersAgree:
    """Both callers reach the same verdict for the same chore and window."""

    CONTINUED_STREAK = 6
    BROKEN_STREAK = 1

    @pytest.mark.parametrize(
        ("chore_data", "start", "end", "expected"),
        [
            pytest.param(DAILY, utc_at(1), utc_at(2), False, id="daily_consecutive"),
            pytest.param(DAILY, utc_at(1), utc_at(3), True, id="daily_gap"),
            pytest.param(
                WEEKLY_MONDAY, utc_at(2), utc_at(9), False, id="weekly_consecutive"
            ),
            pytest.param(
                WEEKLY_MONDAY, utc_at(2), utc_at(16), True, id="weekly_skipped"
            ),
            pytest.param(
                EVERY_THREE_DAYS, utc_at(1), utc_at(4), False, id="every3_on_time"
            ),
            pytest.param(
                EVERY_THREE_DAYS, utc_at(1), utc_at(7), True, id="every3_skipped"
            ),
        ],
    )
    def test_calculate_streak_matches_the_helper(
        self,
        chore_data: dict[str, Any],
        start: datetime,
        end: datetime,
        expected: bool,
    ) -> None:
        """`calculate_streak` continues iff the helper finds no miss.

        Pins the delegating refactor: the chore-streak consumer must not develop
        its own opinion about what a missed occurrence is.
        """
        helper_says_missed = missed(chore_data, start, end)

        streak = ChoreEngine.calculate_streak(
            current_streak=5,
            previous_last_completed_iso=start.isoformat(),
            current_work_date_iso=end.isoformat(),
            chore_data=chore_data,
        )

        assert helper_says_missed is expected
        if expected:
            assert streak == self.BROKEN_STREAK
        else:
            assert streak == self.CONTINUED_STREAK

    def test_both_callers_use_the_same_day_normalisation(self) -> None:
        """The badge anchor and the chore anchor share one normalisation rule."""
        for hour in (0, 12, 23):
            helper_says_missed = missed(DAILY, utc_at(1, hour, 30), utc_at(2, 12))
            streak = ChoreEngine.calculate_streak(
                current_streak=5,
                previous_last_completed_iso=utc_at(1, hour, 30).isoformat(),
                current_work_date_iso=utc_at(2, 12).isoformat(),
                chore_data=DAILY,
            )

            assert helper_says_missed is False
            assert streak == self.CONTINUED_STREAK


class TestUnusableSchedulePolicy:
    """The two callers deliberately differ when a schedule cannot be evaluated."""

    @staticmethod
    def _raise(*_: Any, **__: Any) -> None:
        raise ValueError("unusable schedule")

    def test_default_treats_unusable_schedule_as_no_miss(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The badge path must never break a valid streak over bad data."""
        monkeypatch.setattr(RecurrenceEngine, "__init__", self._raise)

        assert missed(DAILY, utc_at(1), utc_at(3)) is False

    def test_chore_streak_treats_unusable_schedule_as_a_break(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The chore path stays conservative and resets, preserving old behaviour."""
        monkeypatch.setattr(RecurrenceEngine, "__init__", self._raise)

        assert (
            missed(
                DAILY,
                utc_at(1),
                utc_at(3),
                unusable_schedule_counts_as_miss=True,
            )
            is True
        )
