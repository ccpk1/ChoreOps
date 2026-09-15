"""Schedule-matrix coverage for badge streak and days target types (Phase 4).

A streak badge counts consecutive satisfied *eligible occurrences*, so a chore's
schedule decides both whether a day is owed and whether a gap contains a missed
occurrence. This suite drives each schedule shape through the real badge pipeline
via the #294 day-replay harness and asserts the four outcomes that define the
semantics:

- an occurrence day that is completed advances the streak;
- a day where nothing is owed holds it, untouched;
- an occurrence day that passes unmet breaks it, on the following day;
- a gap that contains no missed occurrence resumes it.

Every case asserts its own preconditions on both halves of the schedule - the
eligible scope (`owed_today`) and the recurrence (`scheduled_occurrence_on`) -
because the harness constructs schedules rather than loading a scenario per
shape, and a case that mis-schedules itself would otherwise pass for the wrong
reason.

Standard frequencies get full coverage. `custom` and `custom_from_complete`
anchor occurrences to the completion or creation time rather than to the window
start the miss check supplies, so they get one deliberate case each instead of a
matrix slot (decision 16).

Uses scenario_minimal.yaml.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import ChoreEngine
from custom_components.choreops.engines.schedule_engine import RecurrenceEngine
from custom_components.choreops.utils import dt_utils
from custom_components.choreops.utils.dt_utils import as_utc, get_default_timezone
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.test_badge_streak_midnight_reset import (
    STREAK_THRESHOLD,
    PeriodicDayReplay,
    _add_periodic_badge,
    day_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from homeassistant.core import HomeAssistant


WEEKDAY_CODES = tuple(const.WEEKDAY_OPTIONS)
"""Day codes in weekday order, so index 0 is Monday."""

MON, TUE, WED, THU, FRI = 0, 1, 2, 3, 4


def weekday_code(day_iso: str) -> str:
    """Day code ('mon'..'sun') for a local date key."""
    return WEEKDAY_CODES[date.fromisoformat(day_iso).weekday()]


def offsets_for_weekdays(weekdays: Sequence[int], *, count: int) -> list[int]:
    """Offsets of the most recent ``count`` days falling on ``weekdays``.

    Returned oldest first, all on or before today. Deriving the offsets from the
    real clock keeps the replay meaningful on any day of the week, which a
    hardcoded weekday list would not be.
    """
    today = dt_utils.dt_today_local()
    offsets: list[int] = []
    offset = 0
    while len(offsets) < count:
        if (today + timedelta(days=offset)).weekday() in weekdays:
            offsets.append(offset)
        offset -= 1
    return sorted(offsets)


def offsets_every(days: int, *, step: int, count: int) -> list[int]:
    """Offsets for occurrences spaced ``step`` days apart, ending most recently.

    The final offset is 0 so the newest occurrence lands today.
    """
    return sorted(-(days - index * step) for index in range(count))


def consecutive_monthly_offsets() -> tuple[int, int]:
    """Offsets of the two most recent monthly occurrences, oldest first.

    Derived from the shipped recurrence engine rather than hand-picked, because a
    month is not a fixed number of days: offsets chosen by hand can silently land
    *between* occurrences, and the window would then contain a missed occurrence
    instead of none.
    """
    today = dt_utils.dt_today_local()
    base = today - timedelta(days=100)
    chore_data = {
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_MONTHLY,
        const.DATA_CHORE_APPLICABLE_DAYS: [],
    }
    local_tz = get_default_timezone()
    start = as_utc(datetime.combine(base, time.min, tzinfo=local_tz))
    config = ChoreEngine.build_schedule_config(
        chore_data,
        base_date_iso=start.isoformat(),
    )
    occurrences = [
        dt_utils.as_local(occurrence).date()
        for occurrence in RecurrenceEngine(config).get_occurrences(
            start, start + timedelta(days=100)
        )
    ]
    past = [occurrence for occurrence in occurrences if occurrence <= today]
    assert len(past) >= 2, "monthly schedule produced fewer than two occurrences"
    return (past[-2] - today).days, (past[-1] - today).days


@pytest.fixture
async def matrix_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for the schedule matrix."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class MatrixReplay:
    """Drive one badge over a schedule whose occurrences fall on chosen days.

    Wraps the #294 replay so a case states intent (this day is satisfied, that day
    is a missed occurrence) rather than field names. Both halves of the schedule
    are driven explicitly: ``frequency``/``applicable_days`` feed the miss check,
    while the due date set on each owed day feeds the eligible scope.
    """

    def __init__(
        self,
        replay: PeriodicDayReplay,
        *,
        frequency: str,
        applicable_days: Sequence[str] = (),
    ) -> None:
        self._replay = replay
        self._frequency = frequency
        self._applicable_days = applicable_days

    @contextmanager
    def running(self, *, first_owed_day_iso: str) -> Iterator[MatrixReplay]:
        """Apply the recurrence for the duration of the block.

        ``first_owed_day_iso`` supplies the initial due date; cases move it with
        each owed day.
        """
        with self._replay.chore_schedule(
            frequency=self._frequency,
            due_date_day_iso=first_owed_day_iso,
            applicable_days=self._applicable_days,
        ):
            yield self

    def assert_owed(self, day_iso: str, *, expected: bool) -> None:
        """Assert the eligible scope agrees with the day's intent."""
        owed = self._replay.owed_today(day_iso)
        assert owed == (1 if expected else 0), (
            f"expected {'an owed' if expected else 'a neutral'} day on {day_iso}, "
            f"but the eligible scope reported {owed} chore(s)"
        )

    def assert_occurrence(self, day_iso: str, *, expected: bool) -> None:
        """Assert the recurrence agrees with the day's intent."""
        found = self._replay.scheduled_occurrence_on(day_iso)
        assert found is expected, (
            f"expected {'an occurrence' if expected else 'no occurrence'} on "
            f"{day_iso}, but the recurrence reported {found}"
        )

    async def satisfy(self, day_iso: str, *, verify_recurrence: bool = True) -> None:
        """Complete an occurrence day, which must advance the streak.

        ``verify_recurrence`` is disabled for interval-based frequencies, where
        the recurrence rebases on the window start and a widened probe therefore
        reports a different phase than production evaluates (see the class
        docstring on ``TestBiweeklySchedule``).
        """
        self._replay.schedule_due_date(day_iso)
        self.assert_owed(day_iso, expected=True)
        if verify_recurrence:
            self.assert_occurrence(day_iso, expected=True)
        await self._replay.complete_day(day_iso)

    async def hold(self, day_iso: str, *, verify_recurrence: bool = True) -> None:
        """Pass a neutral day: nothing owed, no occurrence, streak untouched.

        ``verify_recurrence`` is disabled for interval-based frequencies for the
        same reason as ``satisfy``: the occurrence probe rebases on the window
        start and reports the wrong phase, so it cannot be an oracle there.
        """
        self._replay.schedule_due_date(day_key(offset_from(day_iso) + 7))
        self.assert_owed(day_iso, expected=False)
        if verify_recurrence:
            self.assert_occurrence(day_iso, expected=False)
        await self._replay.start_day(day_iso)

    async def miss(self, day_iso: str, *, verify_recurrence: bool = True) -> None:
        """Leave an occurrence day unmet, without evaluating it as satisfied."""
        self._replay.schedule_due_date(day_iso)
        self.assert_owed(day_iso, expected=True)
        if verify_recurrence:
            self.assert_occurrence(day_iso, expected=True)
        await self._replay.start_day(day_iso)

    async def evaluate(self, day_iso: str) -> None:
        """Evaluate a day without asserting intent, for the latching day."""
        self._replay.schedule_due_date(day_key(offset_from(day_iso) + 7))
        await self._replay.start_day(day_iso)


def offset_from(day_iso: str) -> int:
    """Offset in days from today for a local date key."""
    return (date.fromisoformat(day_iso) - dt_utils.dt_today_local()).days


async def _matrix(
    hass: HomeAssistant,
    setup: SetupResult,
    *,
    frequency: str,
    applicable_days: Sequence[str] = (),
    target_type: str = const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
    threshold: int = STREAK_THRESHOLD,
) -> tuple[PeriodicDayReplay, MatrixReplay]:
    """Create a badge and return the replay pair driving it."""
    badge_id = await _add_periodic_badge(
        hass,
        setup,
        target_type=target_type,
        threshold=threshold,
    )
    replay = PeriodicDayReplay(setup, badge_id)
    return replay, MatrixReplay(
        replay,
        frequency=frequency,
        applicable_days=applicable_days,
    )


# ============================================================================
# TESTS: specific-weekday schedules (applicable_days)
# ============================================================================


class TestSpecificWeekdaySchedule:
    """A Mon/Wed/Fri chore: consecutive occurrences, neutral days between."""

    async def test_occurrences_advance_and_between_days_hold(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """Mon -> Wed -> Fri counts three, with the days between held.

        This is decision 1's worked example: consecutive eligible occurrences
        extend the streak, and a day the chore is simply not due neither advances
        nor breaks it.
        """
        monday, wednesday, friday = offsets_for_weekdays([MON, WED, FRI], count=3)
        monday_iso = day_key(monday)
        wednesday_iso = day_key(wednesday)
        friday_iso = day_key(friday)

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
            # The recurring days are the ones the three simulated days actually
            # fall on, so the pattern is meaningful whatever today's weekday is.
            applicable_days=sorted(
                {
                    weekday_code(monday_iso),
                    weekday_code(wednesday_iso),
                    weekday_code(friday_iso),
                }
            ),
        )
        with matrix.running(first_owed_day_iso=monday_iso):
            await matrix.satisfy(monday_iso)
            assert replay.days_cycle_count == 1

            await matrix.hold(day_key(monday + 1))
            assert replay.days_cycle_count == 1, "an in-between day broke the streak"

            await matrix.satisfy(wednesday_iso)
            assert replay.days_cycle_count == 2

            await matrix.hold(day_key(wednesday + 1))
            assert replay.days_cycle_count == 2

            await matrix.satisfy(friday_iso)
            assert replay.days_cycle_count == 3, (
                "three consecutive occurrences did not accumulate; "
                "the days the chore was not due should not interrupt the streak"
            )


# ============================================================================
# TESTS: a missed occurrence followed by a neutral day
# ============================================================================


class TestMissedOccurrenceAcrossNeutralDay:
    """The decisive case for the miss check owning break detection."""

    async def test_skipped_occurrence_breaks_on_the_following_day(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A skipped Monday breaks the streak on Tuesday, where nothing is owed.

        Tuesday has no occurrence and nothing to complete, so only the miss check
        can end the streak. Without it the neutral-hold rule would keep the streak
        alive indefinitely.
        """
        monday, wednesday = offsets_for_weekdays([MON, WED], count=2)
        monday_iso = day_key(monday)

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
            applicable_days=[weekday_code(monday_iso)],
        )
        with matrix.running(first_owed_day_iso=monday_iso):
            replay.seed_streak(days=2, last_update_day=day_key(monday - 7))

            await matrix.miss(monday_iso)
            assert replay.days_cycle_count == 2, (
                "the missed day itself must not break the streak; the occurrence "
                "has not passed yet while the day is in progress"
            )

            # Tuesday owes nothing and has no occurrence, so the neutral-hold rule
            # would keep the streak alive were the miss check not consulted.
            await matrix.hold(day_key(monday + 1))

            assert replay.days_cycle_count == 0, (
                "a skipped occurrence did not break the streak on the following "
                "day, where nothing was owed and only the miss check could end it"
            )


# ============================================================================
# TESTS: weekly, biweekly and monthly schedules
# ============================================================================


class TestWeeklySchedule:
    """A weekly chore: occurrences a week apart, the days between neutral."""

    async def test_rescheduled_due_date_advances_across_neutral_week(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """Two consecutive weekly occurrences count two, across six neutral days."""
        this_week, last_week = offsets_for_weekdays([MON], count=2)[::-1]

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_WEEKLY,
            applicable_days=[weekday_code(day_key(this_week))],
        )
        with matrix.running(first_owed_day_iso=day_key(last_week)):
            await matrix.satisfy(day_key(last_week))
            assert replay.days_cycle_count == 1

            # A week of days that are not the occurrence weekday.
            for offset in range(last_week + 1, this_week):
                await matrix.hold(day_key(offset))
            assert replay.days_cycle_count == 1, (
                "a neutral week between two weekly occurrences broke the streak"
            )

            await matrix.satisfy(day_key(this_week))
            assert replay.days_cycle_count == 2


class TestBiweeklySchedule:
    """A biweekly chore: every second week, so the week between is neutral.

    The occurrence probe is disabled here. This frequency rebases on the window
    start, and its two-week interval means the base week's parity decides which
    Mondays are occurrences, so a window widened by a day to probe a single date
    lands on the opposite phase. Only the streak outcome is asserted - which is
    the behaviour that matters - rather than a probe that cannot be a valid oracle.
    """

    async def test_fortnight_gap_holds_and_advances(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """The intervening week holds, and the next occurrence advances."""
        first, second = offsets_every(14, step=14, count=2)

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_BIWEEKLY,
            applicable_days=[weekday_code(day_key(first))],
        )
        with matrix.running(first_owed_day_iso=day_key(first)):
            await matrix.satisfy(day_key(first), verify_recurrence=False)
            assert replay.days_cycle_count == 1

            await matrix.hold(day_key(first + 7), verify_recurrence=False)
            assert replay.days_cycle_count == 1, (
                "the week between two biweekly occurrences broke the streak"
            )

            await matrix.satisfy(day_key(second), verify_recurrence=False)
            assert replay.days_cycle_count == 2, (
                "the next biweekly occurrence did not advance the streak"
            )


class TestMonthlySchedule:
    """A monthly chore: a long neutral stretch must not inflate the count."""

    async def test_neutral_month_holds_without_inflating(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A neutral stretch neither advances nor breaks, matching decision 6."""
        first, second = consecutive_monthly_offsets()

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_MONTHLY,
        )
        with matrix.running(first_owed_day_iso=day_key(first)):
            await matrix.satisfy(day_key(first), verify_recurrence=False)
            assert replay.days_cycle_count == 1

            await matrix.hold(day_key((first + second) // 2))
            assert replay.days_cycle_count == 1, (
                "a neutral day advanced the streak, which would let a dormant "
                "badge inflate its count"
            )

            await matrix.satisfy(day_key(second), verify_recurrence=False)
            assert replay.days_cycle_count == 2, (
                "consecutive monthly occurrences did not accumulate"
            )


# ============================================================================
# TESTS: the motivating regression, at threshold
# ============================================================================


class TestMotivatingRegression:
    """Four dailies plus one weekly the badge cannot reach today."""

    async def test_streak_reaches_threshold_with_a_weekly_absent(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """The 100% streak badge must be earnable despite a non-due weekly.

        Before the eligible scope this capped at one and then broke, because the
        absent weekly sat in the denominator as a permanent failure.
        """
        from tests.test_badge_streak_midnight_reset import MIXED_SCOPE_CHORES

        badge_id = await _add_periodic_badge(
            hass,
            matrix_scenario,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        replay = PeriodicDayReplay(
            matrix_scenario,
            badge_id,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        eligible = len(MIXED_SCOPE_CHORES) - 1

        for offset in (-3, -2, -1):
            await replay.advance_day(day_key(offset), approved_count=eligible)

        assert replay.days_cycle_count == STREAK_THRESHOLD, (
            "the streak did not reach the threshold with a non-due chore in scope"
        )
        assert replay.criteria_met is True
        assert replay.earned is True

    async def test_partial_progress_then_completion_advances(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """Mid-day partial progress holds, and the final approval advances."""
        from tests.test_badge_streak_midnight_reset import MIXED_SCOPE_CHORES

        badge_id = await _add_periodic_badge(
            hass,
            matrix_scenario,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        replay = PeriodicDayReplay(
            matrix_scenario,
            badge_id,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        replay.seed_streak(days=2, last_update_day=day_key(-1))
        eligible = len(MIXED_SCOPE_CHORES) - 1

        await replay.advance_day(day_key(0), approved_count=eligible - 1)
        assert replay.days_cycle_count == 2, (
            "partial progress broke the streak while the day was still in progress"
        )

        await replay.advance_day(day_key(0), approved_count=eligible)
        assert replay.days_cycle_count == 3


# ============================================================================
# TESTS: the two completion-anchored custom frequencies (decision 16)
# ============================================================================


class TestCompletionAnchoredFrequencies:
    """One case each, because these do not anchor to the miss-check window."""

    async def test_custom_interval_chore_does_not_break_a_daily_streak(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A custom-interval chore in scope leaves a daily streak advancing.

        The occurrence window is derived from the badge's advance day rather than
        the chore's own completion anchor, so a long interval produces no
        occurrence inside a one-day window and cannot break the streak.
        """
        from tests.test_badge_streak_midnight_reset import (
            MIXED_SCOPE_CHORES,
            TRACKED_CHORE_NAMES,
        )

        badge_id = await _add_periodic_badge(
            hass,
            matrix_scenario,
            tracked_chore_names=TRACKED_CHORE_NAMES,
        )
        replay = PeriodicDayReplay(
            matrix_scenario,
            badge_id,
            tracked_chore_names=TRACKED_CHORE_NAMES,
        )
        custom_chore = matrix_scenario.chore_ids[MIXED_SCOPE_CHORES[-1]]
        chore_info = matrix_scenario.coordinator.chores_data[custom_chore]
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_CUSTOM
        chore_info[const.DATA_CHORE_CUSTOM_INTERVAL] = 30
        chore_info[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = const.TIME_UNIT_DAYS

        for offset in (-2, -1):
            await replay.complete_day(day_key(offset))

        assert replay.days_cycle_count == 2, (
            "a long custom-interval chore in scope interrupted a daily streak"
        )

    async def test_custom_from_complete_chore_does_not_break_a_daily_streak(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A completion-anchored chore in scope leaves a daily streak advancing."""
        from tests.test_badge_streak_midnight_reset import TRACKED_CHORE_NAMES

        badge_id = await _add_periodic_badge(
            hass,
            matrix_scenario,
            tracked_chore_names=TRACKED_CHORE_NAMES,
        )
        replay = PeriodicDayReplay(
            matrix_scenario,
            badge_id,
            tracked_chore_names=TRACKED_CHORE_NAMES,
        )
        chore_id = matrix_scenario.chore_ids[TRACKED_CHORE_NAMES[-1]]
        chore_info = matrix_scenario.coordinator.chores_data[chore_id]
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = (
            const.FREQUENCY_CUSTOM_FROM_COMPLETE
        )
        chore_info[const.DATA_CHORE_CUSTOM_INTERVAL] = 14
        chore_info[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = const.TIME_UNIT_DAYS

        for offset in (-2, -1):
            await replay.complete_day(day_key(offset))

        assert replay.days_cycle_count == 2, (
            "a completion-anchored chore in scope interrupted a daily streak"
        )


# ============================================================================
# TESTS: contract traps, including the never_overdue case
# ============================================================================


class TestStreakContractTraps:
    """The three Phase 1 traps, plus the case a lateness-flag design fails."""

    async def test_skipping_an_occurrence_breaks_without_overdue_flags(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A skipped occurrence breaks the streak even with overdue disabled.

        Lateness timestamps are never written when overdue handling is off, so a
        design reading `has_overdue` would let the streak survive indefinitely
        while nothing is done. The miss check uses schedule math instead.
        """
        first, second = offsets_every(2, step=1, count=2)[0], 0

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
        )
        with matrix.running(first_owed_day_iso=day_key(first)):
            replay.seed_streak(days=2, last_update_day=day_key(first))
            assert replay.criteria_met is False

            await matrix.miss(day_key(second))

            assert replay.days_cycle_count == 0, (
                "skipping an occurrence did not break the streak; "
                "the miss check is not the authority for break detection"
            )

    async def test_pending_occurrence_today_is_not_a_miss(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """Today's still-pending occurrence must not break the streak mid-day.

        The miss window ends at the start of today, so a chore that is merely due
        and not yet done is not a miss. Getting this wrong re-creates the #294
        symptom in a new form.
        """
        yesterday = -1

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
        )
        with matrix.running(first_owed_day_iso=day_key(0)):
            replay.seed_streak(days=2, last_update_day=day_key(yesterday))

            await matrix.evaluate(day_key(0))

            assert replay.days_cycle_count == 2, (
                "today's pending occurrence read as a miss and broke the streak "
                "before the day had a chance to be completed"
            )

    async def test_streak_added_chore_does_not_report_a_spurious_miss(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A chore added to the scope mid-streak must not break it.

        The anchor is the badge's advance day, not the chore's last completion, so
        a chore with older history cannot report a miss that predates its
        enrolment.
        """
        from tests.test_badge_streak_midnight_reset import MIXED_SCOPE_CHORES

        badge_id = await _add_periodic_badge(
            hass,
            matrix_scenario,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        replay = PeriodicDayReplay(
            matrix_scenario,
            badge_id,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        # A chore whose last completion is well before the anchor.
        added_chore = matrix_scenario.chore_ids[MIXED_SCOPE_CHORES[0]]
        chore_info = matrix_scenario.coordinator.chores_data[added_chore]
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_WEEKLY

        replay.seed_streak(days=2, last_update_day=day_key(-1))

        await replay.advance_day(day_key(0), approved_count=len(MIXED_SCOPE_CHORES) - 1)

        assert replay.days_cycle_count == 3, (
            "a chore's older completion history reported a miss that predates the "
            "badge's own anchor"
        )

    async def test_break_is_not_permanent_and_restarts_at_one(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A broken streak must restart, so a past miss cannot block recovery."""
        first, second, third = -3, -2, -1

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
        )
        with matrix.running(first_owed_day_iso=day_key(0)):
            replay.seed_streak(days=2, last_update_day=day_key(first))

            # Day -2 is skipped entirely.
            await matrix.evaluate(day_key(second))

            await matrix.satisfy(day_key(third))

            assert replay.days_cycle_count == 1, (
                "a broken streak did not restart, or the compliant day following "
                "the break earned no credit"
            )


# ============================================================================
# TESTS: the design must not depend on period history surviving
# ============================================================================


class TestIndependentOfPeriodHistory:
    """Daily period buckets are pruned by retention; streak maths must not need them.

    `DEFAULT_RETENTION_DAILY` is 14 days, so a streak over a monthly chore will
    routinely outlive its own period history. Retaining less data is simulated by
    deleting the buckets outright, which is what pruning produces and is stronger
    than merely setting a retention value that a replay never applies.
    """

    async def test_neutral_hold_survives_history_loss(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A neutral day must hold with the period buckets deleted.

        The intact-history equivalent is covered by the schedule cases above, so
        this pins only the pruned side: the hold must not read period data.
        """
        monday, _wednesday = offsets_for_weekdays([MON], count=2)
        monday_iso = day_key(monday)

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
            applicable_days=[weekday_code(monday_iso)],
        )
        with matrix.running(first_owed_day_iso=monday_iso):
            # Anchor on the Monday itself, so its occurrence falls before the
            # window and the following day is genuinely neutral rather than a
            # missed occurrence.
            replay.seed_streak(days=2, last_update_day=monday_iso)
            replay.clear_daily_period_history()

            await matrix.hold(day_key(monday + 1))

            assert replay.days_cycle_count == 2, (
                "a neutral day did not hold once its period history was pruned"
            )

    async def test_miss_is_detected_with_no_period_history_at_all(
        self,
        hass: HomeAssistant,
        matrix_scenario: SetupResult,
    ) -> None:
        """A skipped occurrence must break the streak with history deleted.

        The miss check reads schedule maths on the chore definition, not the
        completion buckets, so an empty history must not hide the break. This is
        the case a retention-dependent design gets wrong.
        """
        monday, _next = offsets_for_weekdays([MON], count=2)
        monday_iso = day_key(monday)

        replay, matrix = await _matrix(
            hass,
            matrix_scenario,
            frequency=const.FREQUENCY_DAILY,
            applicable_days=[weekday_code(monday_iso)],
        )
        with matrix.running(first_owed_day_iso=monday_iso):
            replay.seed_streak(days=2, last_update_day=day_key(monday - 7))
            replay.clear_daily_period_history()

            await matrix.evaluate(day_key(monday + 1))

            assert replay.days_cycle_count == 0, (
                "a skipped occurrence survived a break because the period history "
                "it might have read was pruned"
            )
