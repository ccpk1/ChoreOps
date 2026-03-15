# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Calendar platform for ChoreOps integration.

Provides a read-only calendar view of chore due dates and schedule information.
"""

import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import const
from .coordinator import ChoreOpsConfigEntry
from .engines.schedule_engine import (
    RecurrenceEngine,
    calculate_next_due_date_from_chore_info,
    calculate_next_multi_daily_due,
)
from .helpers.device_helpers import create_assignee_device_info_from_coordinator
from .helpers.entity_helpers import (
    get_event_signal,
    should_create_entity_for_user_assignee,
)
from .type_defs import ChoreData
from .utils.dt_utils import dt_now_local, dt_parse

if TYPE_CHECKING:
    from .type_defs import ScheduleConfig

# Platinum requirement: Parallel Updates
# Set to 0 (unlimited) for coordinator-based entities that don't poll
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreOpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ChoreOps calendar platform."""
    coordinator = entry.runtime_data
    if not coordinator:
        const.LOGGER.error("Coordinator not found for entry %s", entry.entry_id)
        return

    calendar_show_period_days = entry.options.get(
        const.CONF_CALENDAR_SHOW_PERIOD, const.DEFAULT_CALENDAR_SHOW_PERIOD
    )
    calendar_duration = datetime.timedelta(days=calendar_show_period_days)

    entities = []
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        # Use registry-based creation decision for future flexibility
        if should_create_entity_for_user_assignee(
            const.CALENDAR_KC_UID_SUFFIX_CALENDAR,
            coordinator,
            assignee_id,
        ):
            assignee_name = assignee_info.get(
                const.DATA_USER_NAME,
                f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}",
            )
            entities.append(
                AssigneeScheduleCalendar(
                    coordinator, assignee_id, assignee_name, entry, calendar_duration
                )
            )
    async_add_entities(entities)


class AssigneeScheduleCalendar(CalendarEntity):
    """Calendar entity representing an assignee's combined chores + challenges."""

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_CALENDAR_NAME

    def __init__(
        self,
        coordinator,
        assignee_id: str,
        assignee_name: str,
        config_entry,
        calendar_duration,
    ):
        """Initialize the calendar entity.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            config_entry: ConfigEntry for this integration instance.
            calendar_duration: Duration (in days) for calendar event generation window.
        """
        super().__init__()
        self.coordinator = coordinator
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._config_entry = config_entry
        self._calendar_duration = calendar_duration
        self._attr_unique_id = f"{config_entry.entry_id}_{assignee_id}{const.CALENDAR_KC_UID_SUFFIX_CALENDAR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.CALENDAR_KC_PREFIX}{assignee_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, config_entry
        )
        self._events_cache: dict[tuple[str, str, int], list[CalendarEvent]] = {}
        self._max_cache_entries = 8
        self._recurrence_engine_cache: dict[
            tuple[str, int, str, tuple[int, ...], str], RecurrenceEngine
        ] = {}
        self._rrule_cache: dict[tuple[str, int, str, tuple[int, ...], str], str] = {}

    def _get_timed_event_bounds(
        self,
        chore_id: str,
        due_dt: datetime.datetime,
    ) -> tuple[datetime.datetime, datetime.datetime]:
        """Return start/end bounds for a timed chore event."""
        event_start = self.coordinator.chore_manager.get_calendar_event_start(
            chore_id, due_dt
        )
        return event_start, due_dt

    async def async_added_to_hass(self) -> None:
        """Subscribe to mutation signals that invalidate calendar caches."""
        await super().async_added_to_hass()

        invalidation_signals = (
            const.SIGNAL_SUFFIX_CHORE_CREATED,
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            const.SIGNAL_SUFFIX_CHORE_DELETED,
            const.SIGNAL_SUFFIX_CHORE_RESCHEDULED,
            const.SIGNAL_SUFFIX_CHORE_STATUS_RESET,
            const.SIGNAL_SUFFIX_CHALLENGE_CREATED,
            const.SIGNAL_SUFFIX_CHALLENGE_UPDATED,
            const.SIGNAL_SUFFIX_CHALLENGE_DELETED,
        )

        for suffix in invalidation_signals:
            signal = get_event_signal(self._config_entry.entry_id, suffix)
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass, signal, self._on_calendar_data_changed
                )
            )

    def _clear_event_caches(self) -> None:
        """Clear all read-path caches used by this calendar entity."""
        self._events_cache.clear()
        self._recurrence_engine_cache.clear()
        self._rrule_cache.clear()

    @callback
    def _on_calendar_data_changed(self, _payload: dict[str, Any] | None = None) -> None:
        """Invalidate cached event artifacts when underlying data mutates."""
        self._clear_event_caches()
        self.async_write_ha_state()

    def _build_cache_revision(self) -> int:
        """Build a lightweight revision token for this assignee's visible calendar data."""
        revision = 0

        for chore in self.coordinator.chores_data.values():
            if self._assignee_id not in chore.get(
                const.DATA_CHORE_ASSIGNED_USER_IDS, []
            ):
                continue
            if not chore.get(const.DATA_CHORE_SHOW_ON_CALENDAR, True):
                continue

            completion_criteria = chore.get(
                const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
            )
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                due_date = chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}).get(
                    self._assignee_id
                )
                applicable_days = tuple(
                    chore.get(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}).get(
                        self._assignee_id, []
                    )
                )
            else:
                due_date = chore.get(const.DATA_CHORE_DUE_DATE)
                applicable_days = tuple(chore.get(const.DATA_CHORE_APPLICABLE_DAYS, []))

            chore_token = (
                chore.get(const.DATA_CHORE_INTERNAL_ID, const.SENTINEL_EMPTY),
                chore.get(
                    const.DATA_CHORE_RECURRING_FREQUENCY,
                    const.FREQUENCY_NONE,
                ),
                due_date,
                chore.get(
                    const.DATA_CHORE_DUE_WINDOW_OFFSET,
                    const.DEFAULT_DUE_WINDOW_OFFSET,
                ),
                chore.get(const.DATA_CHORE_DAILY_MULTI_TIMES, const.SENTINEL_EMPTY),
                applicable_days,
                chore.get(const.DATA_CHORE_CUSTOM_INTERVAL, 1),
                chore.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, const.TIME_UNIT_DAYS),
            )
            revision ^= hash(chore_token)

        for challenge in self.coordinator.challenges_data.values():
            if self._assignee_id not in challenge.get(
                const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
            ):
                continue

            challenge_token = (
                challenge.get(const.DATA_CHALLENGE_INTERNAL_ID, const.SENTINEL_EMPTY),
                challenge.get(const.DATA_CHALLENGE_START_DATE),
                challenge.get(const.DATA_CHALLENGE_END_DATE),
            )
            revision ^= hash(challenge_token)

        return revision

    def _get_cached_events(
        self,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return cached events for a window or generate and cache them."""
        cache_key = (
            window_start.isoformat(),
            window_end.isoformat(),
            self._build_cache_revision(),
        )
        cached = self._events_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        events = self._generate_all_events(window_start, window_end)
        self._events_cache[cache_key] = events
        if len(self._events_cache) > self._max_cache_entries:
            oldest_key = next(iter(self._events_cache))
            del self._events_cache[oldest_key]

        return list(events)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """
        Return CalendarEvent objects for:
         - chores assigned to this assignee
         - challenges assigned to this assignee
        overlapping [start_date, end_date].
        """
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=local_tz)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=local_tz)
        return self._get_cached_events(start_date, end_date)

    async def async_create_event(self, **kwargs) -> None:
        """Create a new event - not supported for read-only calendar."""
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_CALENDAR_CREATE_NOT_SUPPORTED,
        )

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event - not supported for read-only calendar."""
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_CALENDAR_DELETE_NOT_SUPPORTED,
        )

    async def async_update_event(
        self,
        uid: str,
        event: dict,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Update an event - not supported for read-only calendar."""
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_CALENDAR_UPDATE_NOT_SUPPORTED,
        )

    def _event_overlaps_window(
        self,
        event: CalendarEvent,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> bool:
        """Check if event overlaps [window_start, window_end]."""
        sdt = event.start
        edt = event.end
        if isinstance(sdt, datetime.date) and not isinstance(sdt, datetime.datetime):
            tz = dt_util.get_time_zone(self.hass.config.time_zone)
            sdt = datetime.datetime.combine(sdt, datetime.time.min, tzinfo=tz)
        if isinstance(edt, datetime.date) and not isinstance(edt, datetime.datetime):
            tz = dt_util.get_time_zone(self.hass.config.time_zone)
            edt = datetime.datetime.combine(edt, datetime.time.min, tzinfo=tz)
        if not sdt or not edt:
            return False
        return (edt > window_start) and (sdt < window_end)

    def _add_event_if_overlaps(
        self,
        events: list[CalendarEvent],
        event: CalendarEvent,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Add event to list if it overlaps the window."""
        if self._event_overlaps_window(event, window_start, window_end):
            events.append(event)

    def _get_applicable_days_for_assignee(self, chore: dict) -> list[int]:
        """Get applicable days for this calendar's assignee.

        PKAD-2026-001: For INDEPENDENT chores, use per_assignee_applicable_days.
        For SHARED chores, use chore-level applicable_days.
        Empty list = all days applicable (fallback behavior preserved).

        Args:
            chore: Chore data dict

        Returns:
            List of weekday integers (0=Mon...6=Sun), or empty for all days
        """
        completion_criteria = chore.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            per_assignee_days = chore.get(
                const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}
            )
            if self._assignee_id in per_assignee_days:
                return per_assignee_days[self._assignee_id]
            # Fallback to chore-level (backward compat for un-migrated data)
            return chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])

        # SHARED chores: use chore-level
        return chore.get(const.DATA_CHORE_APPLICABLE_DAYS, [])

    def _generate_non_recurring_with_due_date(
        self,
        events: list[CalendarEvent],
        chore_id: str,
        summary: str,
        description: str,
        due_dt: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate event for non-recurring chore with due date."""
        event_start, event_end = self._get_timed_event_bounds(chore_id, due_dt)
        e = CalendarEvent(
            summary=summary,
            start=event_start,
            end=event_end,
            description=description,
        )
        self._add_event_if_overlaps(events, e, window_start, window_end)

    def _generate_non_recurring_without_due_date(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        applicable_days: list[int],
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate events for non-recurring chore without due date on applicable days."""
        if not applicable_days:
            return

        gen_start = window_start
        gen_end = min(
            window_end,
            dt_now_local() + self._calendar_duration,
        )
        current = gen_start
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        while current <= gen_end:
            if current.weekday() in applicable_days:
                # Create full-day event from 00:00:00 to 23:59:59 in local timezone
                day_start = datetime.datetime.combine(
                    current.date(), datetime.time(0, 0, 0), tzinfo=local_tz
                )
                day_end = datetime.datetime.combine(
                    current.date(), datetime.time(23, 59, 59), tzinfo=local_tz
                )
                e = CalendarEvent(
                    summary=summary,
                    start=day_start,
                    end=day_end,
                    description=description,
                )
                self._add_event_if_overlaps(events, e, window_start, window_end)
            current += datetime.timedelta(days=1)

    def _daily_horizon_days(self) -> int:
        """Return the calendar expansion horizon in days for daily frequencies."""
        return max(1, self._calendar_duration.days // 3)

    def _daily_window_end(
        self,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> datetime.datetime:
        """Return capped generation end for daily and daily-multi recurrences."""
        return min(
            window_end,
            window_start + datetime.timedelta(days=self._daily_horizon_days()),
        )

    def _scheduled_window_end(
        self,
        recurring: str,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> datetime.datetime:
        """Return the generation horizon for schedule-backed calendar expansion."""
        if recurring in (const.FREQUENCY_DAILY, const.FREQUENCY_DAILY_MULTI):
            return self._daily_window_end(window_start, window_end)
        return window_end

    def _build_schedule_chore_info(
        self,
        chore: dict,
        applicable_days: list[int],
    ) -> ChoreData:
        """Build chore info for schedule calculations using assignee-specific days."""
        chore_info_for_calc = dict(chore)
        chore_info_for_calc[const.DATA_CHORE_APPLICABLE_DAYS] = list(applicable_days)
        return cast("ChoreData", chore_info_for_calc)

    def _next_scheduled_occurrence(
        self,
        chore_info: ChoreData,
        current_due_utc: datetime.datetime,
    ) -> datetime.datetime | None:
        """Return the next due occurrence using the chore scheduling source of truth."""
        recurring = chore_info.get(
            const.DATA_CHORE_RECURRING_FREQUENCY,
            const.FREQUENCY_NONE,
        )
        if recurring == const.FREQUENCY_DAILY_MULTI:
            return calculate_next_multi_daily_due(
                chore_info,
                current_due_utc,
                reference_time=current_due_utc,
            )

        return calculate_next_due_date_from_chore_info(
            current_due_utc,
            chore_info,
            reference_time=current_due_utc,
        )

    def _add_daily_multi_occurrence_event(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        occurrence_utc: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Add one DAILY_MULTI slot occurrence using the persisted due-time series."""
        local_occurrence = dt_util.as_local(occurrence_utc)
        hour = local_occurrence.hour
        if hour < 12:
            time_label = "Morning"
        elif hour < 17:
            time_label = "Afternoon"
        else:
            time_label = "Evening"

        event_summary = f"{summary} ({time_label})"
        event_end = occurrence_utc + datetime.timedelta(minutes=15)
        event = CalendarEvent(
            summary=event_summary,
            start=occurrence_utc,
            end=event_end,
            description=description,
        )
        self._add_event_if_overlaps(events, event, window_start, window_end)

    def _generate_schedule_source_events(
        self,
        events: list[CalendarEvent],
        chore_id: str,
        summary: str,
        description: str,
        chore_info: ChoreData,
        due_dt: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate due-dated recurrence events from the scheduling source of truth."""
        recurring = chore_info.get(
            const.DATA_CHORE_RECURRING_FREQUENCY,
            const.FREQUENCY_NONE,
        )
        generation_end = self._scheduled_window_end(
            recurring,
            window_start,
            window_end,
        )

        current_due_utc = due_dt
        iterations = 0
        while (
            current_due_utc <= generation_end
            and iterations < const.MAX_DATE_CALCULATION_ITERATIONS
        ):
            if recurring == const.FREQUENCY_DAILY_MULTI:
                self._add_daily_multi_occurrence_event(
                    events,
                    summary,
                    description,
                    current_due_utc,
                    window_start,
                    window_end,
                )
            else:
                event_start, event_end = self._get_timed_event_bounds(
                    chore_id,
                    current_due_utc,
                )
                event = CalendarEvent(
                    summary=summary,
                    start=event_start,
                    end=event_end,
                    description=description,
                )
                self._add_event_if_overlaps(events, event, window_start, window_end)

            next_due_utc = self._next_scheduled_occurrence(
                chore_info,
                current_due_utc,
            )
            if next_due_utc is None or next_due_utc <= current_due_utc:
                return

            current_due_utc = next_due_utc
            iterations += 1

        if iterations >= const.MAX_DATE_CALCULATION_ITERATIONS:
            const.LOGGER.warning(
                "Calendar: Max schedule iterations reached for %s",
                summary,
            )

    def _generate_recurring_daily_with_due_date(
        self,
        events: list[CalendarEvent],
        chore_id: str,
        summary: str,
        description: str,
        due_dt: datetime.datetime,
        applicable_days: list[int],
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate daily recurring timed events via the recurrence engine."""
        self._generate_recurring_with_due_date(
            events,
            chore_id,
            summary,
            description,
            due_dt,
            const.FREQUENCY_DAILY,
            1,
            const.TIME_UNIT_DAYS,
            window_start,
            window_end,
            applicable_days=applicable_days,
        )

    def _generate_recurring_with_due_date(
        self,
        events: list[CalendarEvent],
        chore_id: str,
        summary: str,
        description: str,
        due_dt: datetime.datetime,
        recurring: str,
        interval: int,
        unit: str,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
        applicable_days: list[int] | None = None,
    ) -> None:
        """Generate recurring 1-hour timed events using RecurrenceEngine.

        Creates RFC 5545 RRULE-compatible events for iCal export.
        Each occurrence is rendered as a 1-hour block.

        Args:
            events: List to append events to
            summary: Event summary (chore name)
            description: Event description
            due_dt: First occurrence time (UTC)
            recurring: Frequency constant (WEEKLY, MONTHLY, etc.)
            interval: Interval value for CUSTOM frequencies
            unit: Time unit for CUSTOM frequencies (days, weeks, etc.)
            window_start: Calendar window start
            window_end: Calendar window end
            applicable_days: Weekday constraints (0=Mon, 6=Sun), or None/[]
        """
        # Build ScheduleConfig for RecurrenceEngine
        # Convert applicable_days format if provided
        app_days = applicable_days or []

        engine_cache_key = (
            recurring,
            interval,
            unit,
            tuple(app_days),
            due_dt.isoformat(),
        )

        engine = self._recurrence_engine_cache.get(engine_cache_key)
        if engine is None:
            schedule_config = {
                "frequency": recurring,
                "interval": interval,
                "interval_unit": unit,
                "base_date": due_dt.isoformat(),
                "applicable_days": app_days,
            }

            try:
                engine = RecurrenceEngine(cast("ScheduleConfig", schedule_config))
            except Exception as err:  # pylint: disable=broad-except
                const.LOGGER.warning(
                    "Calendar: Failed to create RecurrenceEngine for %s: %s",
                    summary,
                    err,
                )
                return

            self._recurrence_engine_cache[engine_cache_key] = engine

        # Generate RRULE string for iCal export (add to TIMED events only)
        rrule_str = self._rrule_cache.get(engine_cache_key)
        if rrule_str is None:
            rrule_str = engine.to_rrule_string()
            self._rrule_cache[engine_cache_key] = rrule_str

        lead_time = self.coordinator.chore_manager.get_calendar_event_lead_time(
            chore_id
        )

        # Get all occurrences in the window using engine
        try:
            occurrences = engine.get_occurrences(
                start=window_start,
                end=window_end + lead_time,
                limit=100,
            )
        except Exception as err:  # pylint: disable=broad-except
            const.LOGGER.warning(
                "Calendar: Failed to get occurrences for %s: %s",
                summary,
                err,
            )
            return

        # Create pre-due events for each occurrence
        for occurrence_utc in occurrences:
            event_start, event_end = self._get_timed_event_bounds(
                chore_id, occurrence_utc
            )
            e = CalendarEvent(
                summary=summary,
                start=event_start,
                end=event_end,
                description=description,
                rrule=rrule_str or None,
            )
            self._add_event_if_overlaps(events, e, window_start, window_end)

    def _generate_recurring_daily_without_due_date(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        applicable_days: list[int],
        gen_start: datetime.datetime,
        cutoff: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate full-day events for daily recurring chore without due date."""
        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        current = gen_start
        while current <= cutoff:
            if applicable_days and current.weekday() not in applicable_days:
                current += datetime.timedelta(days=1)
                continue
            # Create full-day event from 00:00:00 to 23:59:59 in local timezone
            day_start = datetime.datetime.combine(
                current.date(), datetime.time(0, 0, 0), tzinfo=local_tz
            )
            day_end = datetime.datetime.combine(
                current.date(), datetime.time(23, 59, 59), tzinfo=local_tz
            )
            e = CalendarEvent(
                summary=summary,
                start=day_start,
                end=day_end,
                description=description,
            )
            self._add_event_if_overlaps(events, e, window_start, window_end)
            current += datetime.timedelta(days=1)

    def _generate_recurring_weekly_biweekly_without_due_date(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        recurring: str,
        gen_start: datetime.datetime,
        cutoff: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate multi-day block events for weekly/biweekly recurring chore without due date."""
        week_delta = 7 if recurring == const.FREQUENCY_WEEKLY else 14
        current = gen_start
        # align to Monday
        while current.weekday() != 0:
            current += datetime.timedelta(days=1)
        while current <= cutoff:
            # multi-day block from Monday..Sunday (or 2 weeks for biweekly)
            block_days = 6 if recurring == const.FREQUENCY_WEEKLY else 13
            start_block = current
            end_block = current + datetime.timedelta(days=block_days)
            e = CalendarEvent(
                summary=summary,
                start=start_block.date(),
                end=end_block.date() + datetime.timedelta(days=1),
                description=description,
            )
            self._add_event_if_overlaps(events, e, window_start, window_end)
            current += datetime.timedelta(days=week_delta)

    def _generate_recurring_monthly_without_due_date(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        gen_start: datetime.datetime,
        cutoff: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate full-month block events for monthly recurring chore without due date."""
        cur = gen_start
        while cur <= cutoff:
            first_day = cur.replace(day=1)
            next_month = first_day + datetime.timedelta(days=32)
            next_month = next_month.replace(day=1)
            last_day = next_month - datetime.timedelta(days=1)

            e = CalendarEvent(
                summary=summary,
                start=first_day.date(),
                end=last_day.date() + datetime.timedelta(days=1),
                description=description,
            )
            self._add_event_if_overlaps(events, e, window_start, window_end)
            cur = next_month

    def _generate_recurring_custom_without_due_date(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        applicable_days: list[int],
        interval: int,
        unit: str,
        gen_start: datetime.datetime,
        cutoff: datetime.datetime,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate custom interval events for custom recurring chore without due date."""
        if unit == const.TIME_UNIT_DAYS:
            step = datetime.timedelta(days=interval)
        elif unit == const.TIME_UNIT_WEEKS:
            step = datetime.timedelta(weeks=interval)
        elif unit == const.TIME_UNIT_MONTHS:
            step = datetime.timedelta(days=30 * interval)
        else:
            step = datetime.timedelta(days=interval)

        current = gen_start
        while current <= cutoff:
            # Check applicable days
            if applicable_days and current.weekday() not in applicable_days:
                current += step
                continue
            e = CalendarEvent(
                summary=summary,
                start=current.date(),
                end=current.date() + step,
                description=description,
            )
            self._add_event_if_overlaps(events, e, window_start, window_end)
            current += step

    def _generate_recurring_daily_multi_with_due_date(
        self,
        events: list[CalendarEvent],
        summary: str,
        description: str,
        chore: dict,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> None:
        """Generate DAILY_MULTI calendar events from the scheduling source of truth."""
        schedule_chore = self._build_schedule_chore_info(
            chore,
            self._get_applicable_days_for_assignee(chore),
        )
        due_date_str = chore.get(const.DATA_CHORE_DUE_DATE)
        due_dt = dt_parse(due_date_str) if due_date_str else None
        if not isinstance(due_dt, datetime.datetime):
            return

        self._generate_schedule_source_events(
            events,
            chore.get(const.DATA_CHORE_INTERNAL_ID, const.SENTINEL_EMPTY),
            summary,
            description,
            schedule_chore,
            due_dt,
            window_start,
            window_end,
        )

    def _generate_events_for_chore(
        self,
        chore: dict,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Generate calendar events for a chore within the given time window.

        ChoreOps calendars only surface chores with anchored due dates. Date-less
        chores are intentionally excluded from calendar output.

        Args:
            chore: Chore dictionary with configuration data
            window_start: Start of calendar window
            window_end: End of calendar window

        Returns:
            List of CalendarEvent objects for this chore
        """
        events: list[CalendarEvent] = []

        chore_id = chore.get(const.DATA_CHORE_INTERNAL_ID, const.SENTINEL_EMPTY)
        summary = chore.get(
            const.DATA_CHORE_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_CHORE
        )
        description = chore.get(const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY)
        recurring = chore.get(
            const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )
        # PKAD-2026-001: Use per-assignee applicable_days for INDEPENDENT chores
        applicable_days = self._get_applicable_days_for_assignee(chore)

        # Parse chore due_date using battle-tested helper
        # For INDEPENDENT chores, use per-assignee due date only; for SHARED, use chore-level
        completion_criteria = chore.get(
            const.DATA_CHORE_COMPLETION_CRITERIA, const.SENTINEL_EMPTY
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            per_assignee_due_dates = chore.get(
                const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
            )
            due_date_str = per_assignee_due_dates.get(self._assignee_id)
            # No fallback - INDEPENDENT chores must have per-assignee due dates
        else:
            due_date_str = chore.get(const.DATA_CHORE_DUE_DATE)
        due_dt: datetime.datetime | None = None
        if due_date_str:
            parsed = dt_parse(due_date_str)
            if isinstance(parsed, datetime.datetime):
                due_dt = parsed

        if not due_dt:
            return events

        # --- Non-recurring chores ---
        if recurring == const.FREQUENCY_NONE:
            self._generate_non_recurring_with_due_date(
                events,
                chore_id,
                summary,
                description,
                due_dt,
                window_start,
                window_end,
            )
            return events

        # --- Recurring chores with a due_date ---
        if due_dt < window_start:
            return events

        schedule_chore = self._build_schedule_chore_info(chore, applicable_days)

        if recurring in (
            const.FREQUENCY_DAILY,
            const.FREQUENCY_WEEKLY,
            const.FREQUENCY_BIWEEKLY,
            const.FREQUENCY_MONTHLY,
            const.FREQUENCY_QUARTERLY,
            const.FREQUENCY_YEARLY,
            const.FREQUENCY_CUSTOM,
            const.FREQUENCY_CUSTOM_FROM_COMPLETE,
            const.FREQUENCY_DAILY_MULTI,
        ):
            self._generate_schedule_source_events(
                events,
                chore_id,
                summary,
                description,
                schedule_chore,
                due_dt,
                window_start,
                window_end,
            )

        return events

    def _generate_events_for_challenge(
        self,
        challenge: dict,
        window_start: datetime.datetime,
        window_end: datetime.datetime,
    ) -> list[CalendarEvent]:
        """
        Produce a single multi-day event for each challenge that has valid start_date/end_date.
        Only if it overlaps the requested [window_start, window_end].
        """
        events: list[CalendarEvent] = []

        challenge_name = challenge.get(
            const.DATA_CHALLENGE_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_CHALLENGE
        )
        description = challenge.get(
            const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
        )
        start_str = challenge.get(const.DATA_CHALLENGE_START_DATE)
        end_str = challenge.get(const.DATA_CHALLENGE_END_DATE)
        if not start_str or not end_str:
            return events  # no valid date range => skip

        # Parse to local timezone directly
        local_start = dt_parse(
            start_str,
            default_tzinfo=const.DEFAULT_TIME_ZONE,
            return_type=const.HELPER_RETURN_DATETIME_LOCAL,
        )
        local_end = dt_parse(
            end_str,
            default_tzinfo=const.DEFAULT_TIME_ZONE,
            return_type=const.HELPER_RETURN_DATETIME_LOCAL,
        )
        if not local_start or not local_end:
            return events  # parsing failed => skip

        # If the challenge times are midnight-based, we can treat them as all-day.
        # But let's keep it simpler => always treat as an all-day block from date(start) to date(end)+1
        # so the user sees a big multi-day block.
        # Type guard: narrow datetime | date | str | None to datetime before comparisons and .date() calls
        if not isinstance(local_start, datetime.datetime) or not isinstance(
            local_end, datetime.datetime
        ):
            return events  # type check failed => skip
        if local_start > window_end or local_end < window_start:
            return events  # out of range

        # Build an all-day event from local_start.date() to local_end.date() + 1 day
        ev = CalendarEvent(
            summary=f"{const.TRANS_KEY_LABEL_CHALLENGE}: {challenge_name}",
            start=local_start.date(),
            end=local_end.date() + datetime.timedelta(days=1),
            description=description,
        )

        # Overlap check (similar logic):
        def overlaps(e: CalendarEvent) -> bool:
            sdt = e.start
            edt = e.end
            # convert if needed
            tz = dt_util.get_time_zone(self.hass.config.time_zone)
            if isinstance(sdt, datetime.date) and not isinstance(
                sdt, datetime.datetime
            ):
                sdt = datetime.datetime.combine(sdt, datetime.time.min, tzinfo=tz)
            if isinstance(edt, datetime.date) and not isinstance(
                edt, datetime.datetime
            ):
                edt = datetime.datetime.combine(edt, datetime.time.min, tzinfo=tz)
            return bool(sdt and edt and (edt > window_start) and (sdt < window_end))

        if overlaps(ev):
            events.append(ev)

        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return a single "current" event (chore or challenge) if one is active now (±1h)."""
        now = dt_util.as_local(dt_util.now())
        window_start = now - datetime.timedelta(hours=1)
        window_end = now + datetime.timedelta(hours=1)
        all_events = self._get_cached_events(window_start, window_end)
        for e in all_events:
            # Convert date->datetime for comparison
            tz = dt_util.get_time_zone(self.hass.config.time_zone)
            sdt = e.start
            edt = e.end
            if isinstance(sdt, datetime.date) and not isinstance(
                sdt, datetime.datetime
            ):
                sdt = datetime.datetime.combine(sdt, datetime.time.min, tzinfo=tz)
            if isinstance(edt, datetime.date) and not isinstance(
                edt, datetime.datetime
            ):
                edt = datetime.datetime.combine(edt, datetime.time.min, tzinfo=tz)
            if sdt and edt and sdt <= now < edt:
                return e
        return None

    def _generate_all_events(
        self, window_start: datetime.datetime, window_end: datetime.datetime
    ) -> list[CalendarEvent]:
        """Generate chores + challenges for this assignee in the given window."""
        events = []
        # chores
        for chore in self.coordinator.chores_data.values():
            if self._assignee_id in chore.get(const.DATA_CHORE_ASSIGNED_USER_IDS, []):
                if not chore.get(const.DATA_CHORE_SHOW_ON_CALENDAR, True):
                    continue
                events.extend(
                    self._generate_events_for_chore(chore, window_start, window_end)
                )
        # challenges
        for challenge in self.coordinator.challenges_data.values():
            if self._assignee_id in challenge.get(
                const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
            ):
                events.extend(
                    self._generate_events_for_challenge(
                        challenge, window_start, window_end
                    )
                )
        return events

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_CALENDAR_SCHEDULE,
            const.ATTR_USER_NAME: self._assignee_name,
        }
