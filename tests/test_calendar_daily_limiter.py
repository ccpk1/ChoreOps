"""Tests for daily calendar expansion limiter behavior."""

from __future__ import annotations

import datetime

from freezegun import freeze_time
from homeassistant.components.calendar import CalendarEvent

from custom_components.kidschores import const
from custom_components.kidschores.calendar import KidScheduleCalendar


def _build_calendar(duration_days: int) -> KidScheduleCalendar:
    """Create a lightweight calendar instance for unit-level method tests."""
    calendar = object.__new__(KidScheduleCalendar)
    calendar._calendar_duration = datetime.timedelta(days=duration_days)
    calendar._kid_id = "kid-1"
    calendar._events_cache = {}
    calendar._max_cache_entries = 8
    calendar._recurrence_engine_cache = {}
    calendar._rrule_cache = {}
    return calendar


def _attach_fake_coordinator(calendar: KidScheduleCalendar) -> None:
    """Attach minimal coordinator data needed by cache revision logic."""
    calendar.coordinator = type(
        "FakeCoordinator",
        (),
        {
            "chores_data": {},
            "challenges_data": {},
        },
    )()


def test_daily_window_end_uses_one_third_horizon() -> None:
    """Daily horizon uses floor(show_period/3) with a minimum of 1 day."""
    calendar = _build_calendar(90)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=90)

    assert calendar._daily_horizon_days() == 30
    assert calendar._daily_window_end(window_start, window_end) == (
        window_start + datetime.timedelta(days=30)
    )

    short_calendar = _build_calendar(2)
    assert short_calendar._daily_horizon_days() == 1


def test_event_window_cache_reuses_generation_for_same_revision() -> None:
    """Same window + same revision returns cached results."""
    calendar = _build_calendar(90)
    _attach_fake_coordinator(calendar)

    calls: dict[str, int] = {"count": 0}

    def _generate(
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> list[CalendarEvent]:
        calls["count"] += 1
        return [
            CalendarEvent(
                summary="cached",
                start=window_start,
                end=window_start + datetime.timedelta(hours=1),
                description="",
            )
        ]

    calendar._generate_all_events = _generate  # type: ignore[method-assign]

    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=1)

    first = calendar._get_cached_events(window_start, window_end)
    second = calendar._get_cached_events(window_start, window_end)

    assert calls["count"] == 1
    assert len(first) == 1
    assert len(second) == 1


def test_event_window_cache_invalidates_when_chore_revision_changes() -> None:
    """Cache key revision changes when relevant chore fields are updated."""
    calendar = _build_calendar(90)
    _attach_fake_coordinator(calendar)

    chore_id = "chore-1"
    calendar.coordinator.chores_data[chore_id] = {
        const.DATA_CHORE_INTERNAL_ID: chore_id,
        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1"],
        const.DATA_CHORE_SHOW_ON_CALENDAR: True,
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_DUE_DATE: "2025-01-01T10:00:00+00:00",
        const.DATA_CHORE_APPLICABLE_DAYS: [],
    }

    calls: dict[str, int] = {"count": 0}

    def _generate(
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> list[CalendarEvent]:
        calls["count"] += 1
        return []

    calendar._generate_all_events = _generate  # type: ignore[method-assign]

    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=1)

    calendar._get_cached_events(window_start, window_end)
    calendar._get_cached_events(window_start, window_end)

    calendar.coordinator.chores_data[chore_id][const.DATA_CHORE_DUE_DATE] = (
        "2025-01-02T10:00:00+00:00"
    )
    calendar._get_cached_events(window_start, window_end)

    assert calls["count"] == 2


def test_calendar_data_changed_handler_clears_caches() -> None:
    """Signal handler clears all calendar caches and triggers state write."""
    calendar = _build_calendar(90)

    event_key = ("2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00", 123)
    recurrence_key = (
        const.FREQUENCY_DAILY,
        1,
        const.TIME_UNIT_DAYS,
        (),
        "2025-01-01T08:00:00+00:00",
    )

    calendar._events_cache[event_key] = []
    calendar._recurrence_engine_cache[recurrence_key] = object()  # type: ignore[assignment]
    calendar._rrule_cache[recurrence_key] = "FREQ=DAILY"

    writes: dict[str, int] = {"count": 0}

    def _mark_write() -> None:
        writes["count"] += 1

    calendar.async_write_ha_state = _mark_write  # type: ignore[method-assign]

    calendar._on_calendar_data_changed({"chore_id": "chore-1"})

    assert calendar._events_cache == {}
    assert calendar._recurrence_engine_cache == {}
    assert calendar._rrule_cache == {}
    assert writes["count"] == 1


@freeze_time("2025-01-01 00:00:00")
def test_daily_without_due_date_is_capped_to_daily_horizon() -> None:
    """DAILY no-due generation receives capped cutoff instead of full window."""
    calendar = _build_calendar(90)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=90)

    captured: dict[str, datetime.datetime] = {}

    def _capture_daily(
        events: list,
        summary: str,
        description: str,
        applicable_days: list[int],
        gen_start: datetime.datetime,
        cutoff: datetime.datetime,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> None:
        captured["cutoff"] = cutoff

    calendar._generate_recurring_daily_without_due_date = _capture_daily  # type: ignore[method-assign]

    chore = {
        const.DATA_CHORE_NAME: "Daily chore",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_APPLICABLE_DAYS: [],
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
    }

    calendar._generate_events_for_chore(chore, window_start, window_end)

    assert captured["cutoff"] == window_start + datetime.timedelta(days=30)


@freeze_time("2025-01-01 00:00:00")
def test_daily_multi_is_capped_but_weekly_is_not() -> None:
    """DAILY_MULTI uses 1/3 window cap while WEEKLY keeps full window."""
    calendar = _build_calendar(90)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=90)

    captured_multi: dict[str, datetime.datetime] = {}
    captured_weekly: dict[str, datetime.datetime] = {}

    def _capture_multi(
        events: list,
        summary: str,
        description: str,
        chore: dict,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> None:
        captured_multi["window_end"] = end

    def _capture_weekly(
        events: list,
        summary: str,
        description: str,
        recurring: str,
        gen_start: datetime.datetime,
        cutoff: datetime.datetime,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> None:
        captured_weekly["cutoff"] = cutoff

    calendar._generate_recurring_daily_multi_with_due_date = _capture_multi  # type: ignore[method-assign]
    calendar._generate_recurring_weekly_biweekly_without_due_date = _capture_weekly  # type: ignore[method-assign]

    multi_chore = {
        const.DATA_CHORE_NAME: "Daily multi",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY_MULTI,
        const.DATA_CHORE_DAILY_MULTI_TIMES: "08:00|12:00|18:00",
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        const.DATA_CHORE_DUE_DATE: "2025-01-10T08:00:00+00:00",
    }

    weekly_chore = {
        const.DATA_CHORE_NAME: "Weekly chore",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
    }

    calendar._generate_events_for_chore(multi_chore, window_start, window_end)
    calendar._generate_events_for_chore(weekly_chore, window_start, window_end)

    assert captured_multi["window_end"] == window_start + datetime.timedelta(days=30)
    assert captured_weekly["cutoff"] == window_end
