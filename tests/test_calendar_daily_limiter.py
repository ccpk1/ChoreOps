"""Tests for daily calendar expansion limiter behavior."""

from __future__ import annotations

import datetime

from freezegun import freeze_time
from homeassistant.components.calendar import CalendarEvent

from custom_components.choreops import const
from custom_components.choreops.calendar import AssigneeScheduleCalendar


def _build_calendar(duration_days: int) -> AssigneeScheduleCalendar:
    """Create a lightweight calendar instance for unit-level method tests."""
    calendar = object.__new__(AssigneeScheduleCalendar)
    calendar._calendar_duration = datetime.timedelta(days=duration_days)
    calendar._assignee_id = "assignee-1"
    calendar._assignee_name = "Leo"
    calendar._events_cache = {}
    calendar._max_cache_entries = 8
    calendar._recurrence_engine_cache = {}
    calendar._rrule_cache = {}
    calendar._dashboard_translations = {}
    calendar._config_entry = type(
        "FakeConfigEntry",
        (),
        {
            "options": {
                const.CONF_POINTS_LABEL: "Stars",
            }
        },
    )()
    return calendar


def _attach_fake_coordinator(calendar: AssigneeScheduleCalendar) -> None:
    """Attach minimal coordinator data needed by cache revision logic."""
    fake_manager = type(
        "FakeChoreManager",
        (),
        {
            "get_calendar_event_start": staticmethod(
                lambda _chore_id, due_dt: due_dt - datetime.timedelta(hours=2)
            ),
            "get_calendar_event_lead_time": staticmethod(
                lambda _chore_id: datetime.timedelta(hours=2)
            ),
        },
    )()
    calendar.coordinator = type(
        "FakeCoordinator",
        (),
        {
            "chores_data": {},
            "challenges_data": {},
            "chore_manager": fake_manager,
            "assignees_data": {
                "assignee-1": {
                    const.DATA_USER_NAME: "Leo",
                    const.DATA_USER_DASHBOARD_LANGUAGE: "en",
                },
                "assignee-2": {
                    const.DATA_USER_NAME: "Mia",
                    const.DATA_USER_DASHBOARD_LANGUAGE: "en",
                },
            },
        },
    )()


def test_build_chore_description_enriches_existing_text() -> None:
    """Calendar descriptions use a compact localized single-line format."""
    calendar = _build_calendar(30)
    _attach_fake_coordinator(calendar)
    calendar._dashboard_translations = {
        "assigned_to": "Assigned To",
        "recurrence": "Recurrence",
        "completion_criteria": "Completion Type",
        const.FREQUENCY_WEEKLY: "Weekly",
        const.COMPLETION_CRITERIA_SHARED: "Shared (All)",
    }

    chore = {
        const.DATA_CHORE_DESCRIPTION: "Roll the bins to the curb.",
        const.DATA_CHORE_ASSIGNED_USER_IDS: ["assignee-1", "assignee-2"],
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        const.DATA_CHORE_DEFAULT_POINTS: 5,
    }

    description = calendar._build_chore_description(chore)

    assert description == (
        "Roll the bins to the curb. | "
        "Assigned To: Leo, Mia | "
        "Recurrence: Weekly | "
        "Completion Type: Shared (All) | "
        "Stars: 5"
    )


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
        const.DATA_CHORE_ASSIGNED_USER_IDS: ["assignee-1"],
        const.DATA_CHORE_SHOW_ON_CALENDAR: True,
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_DUE_DATE: "2025-01-01T10:00:00+00:00",
        const.DATA_CHORE_DUE_WINDOW_OFFSET: "2h",
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


def test_event_window_cache_invalidates_when_due_window_changes() -> None:
    """Cache revision changes when due window offset changes."""
    calendar = _build_calendar(90)
    _attach_fake_coordinator(calendar)

    chore_id = "chore-1"
    calendar.coordinator.chores_data[chore_id] = {
        const.DATA_CHORE_INTERNAL_ID: chore_id,
        const.DATA_CHORE_ASSIGNED_USER_IDS: ["assignee-1"],
        const.DATA_CHORE_SHOW_ON_CALENDAR: True,
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
        const.DATA_CHORE_DUE_DATE: "2025-01-01T10:00:00+00:00",
        const.DATA_CHORE_DUE_WINDOW_OFFSET: "2h",
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

    calendar.coordinator.chores_data[chore_id][const.DATA_CHORE_DUE_WINDOW_OFFSET] = (
        "3h"
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
def test_daily_without_due_date_does_not_generate_calendar_events() -> None:
    """Date-less daily chores are intentionally excluded from the calendar."""
    calendar = _build_calendar(90)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=90)

    chore = {
        const.DATA_CHORE_NAME: "Daily chore",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_APPLICABLE_DAYS: [],
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
    }

    assert calendar._generate_events_for_chore(chore, window_start, window_end) == []


@freeze_time("2025-01-01 00:00:00")
def test_daily_multi_is_capped_but_weekly_uses_full_window() -> None:
    """Scheduled generation caps daily horizons but keeps weekly on full window."""
    calendar = _build_calendar(90)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=90)

    assert calendar._scheduled_window_end(
        const.FREQUENCY_DAILY_MULTI,
        window_start,
        window_end,
    ) == window_start + datetime.timedelta(days=30)
    assert (
        calendar._scheduled_window_end(
            const.FREQUENCY_WEEKLY,
            window_start,
            window_end,
        )
        == window_end
    )


def test_daily_with_due_date_uses_schedule_source_applicable_days(
    monkeypatch,
) -> None:
    """Daily due-dated chores call the schedule helper with assignee days."""
    calendar = _build_calendar(90)
    _attach_fake_coordinator(calendar)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=90)
    captured_calls: list[
        tuple[datetime.datetime, datetime.datetime | None, object]
    ] = []

    def _capture_next_due(
        current_due: datetime.datetime,
        chore_info: dict,
        reference_time: datetime.datetime | None = None,
    ) -> datetime.datetime | None:
        captured_calls.append(
            (
                current_due,
                reference_time,
                chore_info[const.DATA_CHORE_APPLICABLE_DAYS],
            )
        )
        if len(captured_calls) > 1:
            return None
        return current_due + datetime.timedelta(days=1)

    monkeypatch.setattr(
        "custom_components.choreops.calendar.calculate_next_due_date_from_chore_info",
        _capture_next_due,
    )

    chore = {
        const.DATA_CHORE_INTERNAL_ID: "chore-1",
        const.DATA_CHORE_NAME: "Daily chore",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        const.DATA_CHORE_DUE_DATE: "2025-01-07T19:00:00+00:00",
        const.DATA_CHORE_APPLICABLE_DAYS: [0, 2, 4],
    }

    events = calendar._generate_events_for_chore(chore, window_start, window_end)

    assert len(events) == 2
    assert captured_calls == [
        (
            datetime.datetime(2025, 1, 7, 19, 0, tzinfo=datetime.UTC),
            datetime.datetime(2025, 1, 7, 19, 0, tzinfo=datetime.UTC),
            [0, 2, 4],
        ),
        (
            datetime.datetime(2025, 1, 8, 19, 0, tzinfo=datetime.UTC),
            datetime.datetime(2025, 1, 8, 19, 0, tzinfo=datetime.UTC),
            [0, 2, 4],
        ),
    ]


def test_weekly_due_date_uses_one_scheduled_occurrence_per_cycle() -> None:
    """Weekly due-dated chores use the persisted scheduled occurrence only."""
    calendar = _build_calendar(30)
    _attach_fake_coordinator(calendar)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=15)

    chore = {
        const.DATA_CHORE_INTERNAL_ID: "chore-1",
        const.DATA_CHORE_NAME: "Weekly chore",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        const.DATA_CHORE_DUE_DATE: "2025-01-07T19:00:00+00:00",
        const.DATA_CHORE_APPLICABLE_DAYS: [0, 2, 4],
    }

    events = calendar._generate_events_for_chore(chore, window_start, window_end)

    assert len(events) == 1
    event_due_dates = [event.end for event in events]
    assert event_due_dates == [
        datetime.datetime(2025, 1, 7, 19, 0, tzinfo=datetime.UTC),
    ]
    assert [event_end.weekday() for event_end in event_due_dates] == [1]


def test_non_recurring_without_due_date_is_excluded_from_calendar() -> None:
    """Date-less one-off chores do not render on the calendar."""
    calendar = _build_calendar(30)
    window_start = datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC)
    window_end = window_start + datetime.timedelta(days=30)

    chore = {
        const.DATA_CHORE_NAME: "One-off chore",
        const.DATA_CHORE_DESCRIPTION: "",
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_NONE,
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        const.DATA_CHORE_APPLICABLE_DAYS: [0, 2, 4],
    }

    assert calendar._generate_events_for_chore(chore, window_start, window_end) == []


def test_non_recurring_due_event_uses_manager_start_and_due_end() -> None:
    """Timed events render from manager start through due time."""
    calendar = _build_calendar(30)
    _attach_fake_coordinator(calendar)
    due_dt = datetime.datetime(2025, 1, 1, 17, 0, tzinfo=datetime.UTC)
    window_start = datetime.datetime(2025, 1, 1, 14, 0, tzinfo=datetime.UTC)
    window_end = datetime.datetime(2025, 1, 1, 18, 0, tzinfo=datetime.UTC)
    events: list[CalendarEvent] = []

    calendar._generate_non_recurring_with_due_date(
        events,
        "chore-1",
        "Test chore",
        "",
        due_dt,
        window_start,
        window_end,
    )

    assert len(events) == 1
    assert events[0].start == due_dt - datetime.timedelta(hours=2)
    assert events[0].end == due_dt


def test_recurring_due_event_extends_occurrence_query_by_lead_time() -> None:
    """Recurring timed events query far enough ahead for pre-due spans."""
    calendar = _build_calendar(30)
    _attach_fake_coordinator(calendar)
    due_dt = datetime.datetime(2025, 1, 1, 17, 0, tzinfo=datetime.UTC)
    window_start = datetime.datetime(2025, 1, 1, 14, 0, tzinfo=datetime.UTC)
    window_end = datetime.datetime(2025, 1, 1, 16, 0, tzinfo=datetime.UTC)
    captured: dict[str, datetime.datetime] = {}

    class FakeEngine:
        def to_rrule_string(self) -> str:
            return "FREQ=WEEKLY;INTERVAL=1"

        def get_occurrences(
            self,
            start: datetime.datetime,
            end: datetime.datetime,
            limit: int = 100,
        ) -> list[datetime.datetime]:
            captured["start"] = start
            captured["end"] = end
            return [due_dt]

    key = (
        const.FREQUENCY_WEEKLY,
        1,
        const.TIME_UNIT_DAYS,
        (),
        due_dt.isoformat(),
    )
    calendar._recurrence_engine_cache[key] = FakeEngine()  # type: ignore[assignment]

    events: list[CalendarEvent] = []
    calendar._generate_recurring_with_due_date(
        events,
        "chore-1",
        "Test chore",
        "",
        due_dt,
        const.FREQUENCY_WEEKLY,
        1,
        const.TIME_UNIT_DAYS,
        window_start,
        window_end,
        applicable_days=[],
    )

    assert captured["start"] == window_start
    assert captured["end"] == window_end + datetime.timedelta(hours=2)
    assert len(events) == 1
    assert events[0].start == due_dt - datetime.timedelta(hours=2)
    assert events[0].end == due_dt
