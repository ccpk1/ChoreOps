"""Regression tests for badge streak target types (issue #294).

A streak badge never accumulates past a single day. The nightly midnight
evaluation runs on a brand-new day with zero approvals, the streak evaluator
treats any unmet day as a break and resets ``days_cycle_count`` to 0, so the
next completion starts a fresh streak at 1. Any streak target with a threshold
above 1 is therefore unreachable.

These tests replay consecutive days through the real badge pipeline (evaluation
plus persistence) with an injected date key, so they lock in the user-visible
invariant rather than a specific implementation:

- An evaluation on a day that is still in progress must not break a streak that
  was intact yesterday.
- A full day with no completions must still break the streak.

Uses scenario_minimal.yaml.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import ChoreEngine
from custom_components.choreops.utils import dt_utils
from custom_components.choreops.utils.dt_utils import as_utc, get_default_timezone
from tests.helpers import (
    BADGE_TYPE_PERIODIC,
    CFOF_BADGES_INPUT_ASSIGNED_USER_IDS,
    CFOF_BADGES_INPUT_AWARD_ITEMS,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_SELECTED_CHORES,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TARGET_TYPE,
    CFOF_BADGES_INPUT_TYPE,
    DATA_USER_BADGE_PROGRESS,
    DATA_USER_CHORE_DATA_PERIOD_APPROVED,
    DATA_USER_CHORE_DATA_PERIODS,
    DATA_USER_CHORE_DATA_PERIODS_DAILY,
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_BADGES,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from homeassistant.core import HomeAssistant


ASSIGNEE_NAME = "Zoë"
TRACKED_CHORE_NAME = "Make bed"
TRACKED_CHORE_NAMES = ("Make bed", "Do homework")
"""Two independent daily chores, used to express partial day progress."""
BADGE_NAME = "Streak Regression"
STREAK_THRESHOLD = 3
"""Consecutive days required by the badge.

Above 1 on purpose: a threshold of 1 is satisfiable even when the streak is
reset every night, which is why the defect went unnoticed.
"""


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def streak_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for streak badge tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# ============================================================================
# HELPERS
# ============================================================================


def day_key(offset: int) -> str:
    """Return a local date key offset from today.

    Simulated days are expressed relative to the real clock so the replay stays
    meaningful without patching time.
    """
    return (dt_utils.dt_today_local() + timedelta(days=offset)).isoformat()


async def _add_periodic_badge(
    hass: HomeAssistant,
    setup: SetupResult,
    *,
    target_type: str = const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
    threshold: int = STREAK_THRESHOLD,
    tracked_chore_names: Sequence[str] | None = None,
) -> str:
    """Create an open-ended periodic streak badge scoped to the given chores.

    Args:
        hass: Home Assistant instance.
        setup: Scenario setup result.
        target_type: Streak target type to configure.
        threshold: Consecutive days required.
        tracked_chore_names: Chores in scope. Defaults to a single chore.

    Returns:
        The badge internal ID.
    """
    assignee_id = setup.assignee_ids[ASSIGNEE_NAME]
    chore_names = tracked_chore_names or [TRACKED_CHORE_NAME]
    chore_ids = [setup.chore_ids[name] for name in chore_names]

    result = await hass.config_entries.options.async_init(setup.config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_PERIODIC},
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CFOF_BADGES_INPUT_NAME: BADGE_NAME,
            CFOF_BADGES_INPUT_ICON: "mdi:fire",
            CFOF_BADGES_INPUT_TARGET_TYPE: target_type,
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: threshold,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: chore_ids,
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        },
    )

    for badge_id, badge_data in setup.coordinator.badges_data.items():
        if badge_data.get(const.DATA_BADGE_NAME) == BADGE_NAME:
            # Open-ended schedule: no cycle rollover to interfere with the replay.
            reset_schedule = badge_data[const.DATA_BADGE_RESET_SCHEDULE]
            reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY] = (
                const.FREQUENCY_NONE
            )
            reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_START_DATE] = None
            reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE] = None
            return badge_id

    raise AssertionError(f"Badge not created: {BADGE_NAME}")


class PeriodicDayReplay:
    """Replay consecutive days through the real streak badge pipeline.

    Each simulated day mirrors production ordering: the day starts with an
    evaluation (the nightly rollover runs at 00:00 with nothing approved yet),
    and completing the day triggers a second, event-driven evaluation.
    """

    def __init__(
        self,
        setup: SetupResult,
        badge_id: str,
        *,
        tracked_chore_names: Sequence[str] | None = None,
    ) -> None:
        self._coordinator = setup.coordinator
        self._gamification = setup.coordinator.gamification_manager
        self._assignee_id = setup.assignee_ids[ASSIGNEE_NAME]
        chore_names = tracked_chore_names or [TRACKED_CHORE_NAME]
        self._chore_ids = [setup.chore_ids[name] for name in chore_names]
        self._badge_id = badge_id

    @property
    def days_cycle_count(self) -> int:
        """Persisted consecutive-day count for the badge."""
        return int(
            self._progress().get(
                const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT,
                0,
            )
        )

    @property
    def last_update_day(self) -> str:
        """Persisted day the streak last advanced on."""
        return str(
            self._progress().get(const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY, "")
        )

    @property
    def criteria_met(self) -> bool:
        """Whether the badge criteria are currently satisfied."""
        return bool(
            self._progress().get(const.DATA_USER_BADGE_PROGRESS_CRITERIA_MET, False)
        )

    @property
    def earned(self) -> bool:
        """Whether the assignee holds the badge."""
        badges_earned = self._coordinator.assignees_data[self._assignee_id].get(
            const.DATA_USER_BADGES_EARNED, {}
        )
        return self._badge_id in badges_earned

    def _progress(self) -> dict[str, Any]:
        return self._coordinator.assignees_data[self._assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][self._badge_id]

    def _chore_info(self, chore_id: str) -> dict[str, Any]:
        """Mutable chore definition for the given chore."""
        return cast("dict[str, Any]", self._coordinator.chores_data[chore_id])

    def _record_day(self, day_iso: str, *, approved_count: int) -> None:
        """Write daily period records for the simulated day.

        The first ``approved_count`` tracked chores are marked approved, which
        lets a day be left partially complete.
        """
        for index, chore_id in enumerate(self._chore_ids):
            chore_entry = self._coordinator.chore_manager._get_assignee_chore_data(
                self._assignee_id,
                chore_id,
            )
            periods = chore_entry.setdefault(DATA_USER_CHORE_DATA_PERIODS, {})
            daily_buckets = periods.setdefault(DATA_USER_CHORE_DATA_PERIODS_DAILY, {})
            daily_buckets[day_iso] = {
                DATA_USER_CHORE_DATA_PERIOD_APPROVED: 1
                if index < approved_count
                else 0,
            }

    async def _evaluate(self, day_iso: str) -> None:
        """Run the real periodic badge evaluation against a simulated day."""
        context = self._gamification._build_evaluation_context(self._assignee_id)
        assert context is not None, "Evaluation context unavailable"
        context["today_iso"] = day_iso
        badge_info = self._coordinator.badges_data[self._badge_id]
        await self._gamification._evaluate_periodic_badge(
            self._assignee_id,
            self._badge_id,
            badge_info,
            context,
        )

    async def advance_day(self, day_iso: str, *, approved_count: int) -> None:
        """Record a partial amount of the day, then re-evaluate.

        Mirrors the mid-day evaluations triggered by individual chore
        approvals, which are the common case in production.
        """
        self._record_day(day_iso, approved_count=approved_count)
        await self._evaluate(day_iso)

    async def start_day(self, day_iso: str) -> None:
        """Evaluate at the start of a day, before anything is approved."""
        await self.advance_day(day_iso, approved_count=0)

    async def complete_day(self, day_iso: str) -> None:
        """Record every tracked chore as approved, then re-evaluate."""
        await self.advance_day(day_iso, approved_count=len(self._chore_ids))

    def seed_streak(self, *, days: int, last_update_day: str) -> None:
        """Seed an intact streak, as if it had accumulated on earlier days.

        Used by the break-semantics tests so they do not depend on streak
        accumulation, which is covered separately.
        """
        progress = self._progress()
        progress[const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT] = days
        progress[const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY] = last_update_day

    def schedule_due_date(self, day_iso: str) -> None:
        """Point the tracked chores' due date at ``day_iso`` for this assignee.

        The eligible scope reads the due date, so this is how a case makes a chore
        owed on one simulated day and not on another. The recurrence the miss check
        reads is deliberately untouched: the two halves of a schedule are
        independent, and a case has to drive both.
        """
        for chore_id in self._chore_ids:
            chore_info = self._chore_info(chore_id)
            chore_info[const.DATA_CHORE_DUE_DATE] = day_iso
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {
                self._assignee_id: day_iso
            }

    def clear_daily_period_history(self) -> None:
        """Delete every tracked chore's daily period buckets.

        Simulates the outcome of aggressive retention pruning. The streak design
        reads schedule maths on the chore definition rather than period history, so
        losing this data must not change any outcome.
        """
        for chore_id in self._chore_ids:
            chore_entry = self._coordinator.chore_manager._get_assignee_chore_data(
                self._assignee_id,
                chore_id,
            )
            periods = chore_entry.get(DATA_USER_CHORE_DATA_PERIODS, {})
            periods.pop(DATA_USER_CHORE_DATA_PERIODS_DAILY, None)

    def scheduled_occurrence_on(self, day_iso: str) -> bool:
        """Whether the recurrence places an occurrence on the given local day.

        Probes the day widened by a day on each side. Occurrences land at local
        midnight and the engine treats both bounds as exclusive, so the narrow
        window ``[day, day + 1)`` would report False on the very day an occurrence
        falls; widening it isolates that one occurrence and excludes the
        neighbouring days'.
        """
        day = date.fromisoformat(day_iso)
        local_tz = get_default_timezone()
        window_start = as_utc(
            datetime.combine(day - timedelta(days=1), time.min, tzinfo=local_tz)
        )
        window_end = as_utc(
            datetime.combine(day + timedelta(days=1), time.min, tzinfo=local_tz)
        )

        return any(
            ChoreEngine.has_missed_occurrence_between(
                self._chore_info(chore_id),
                window_start_utc=window_start,
                window_end_utc=window_end,
            )
            for chore_id in self._chore_ids
        )

    @contextmanager
    def chore_schedule(
        self,
        *,
        frequency: str,
        due_date_day_iso: str | None,
        applicable_days: Sequence[str] = (),
    ) -> Iterator[None]:
        """Apply a schedule to the tracked chores for the duration of the block.

        The harness mutates schedules instead of loading a scenario per shape, so
        one replay implementation serves every frequency. The originals are
        restored on exit, which lets a case compose several schedules in sequence.

        Args:
            frequency: Recurring frequency to apply to the tracked chores.
            due_date_day_iso: The assignee's due date, or None for a dateless
                chore that recurs on ``applicable_days``.
            applicable_days: Day codes the chore recurs on; empty means any day.
        """
        originals = {
            chore_id: deepcopy(self._chore_info(chore_id))
            for chore_id in self._chore_ids
        }

        for chore_id in self._chore_ids:
            chore_info = self._chore_info(chore_id)
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = frequency
            chore_info[const.DATA_CHORE_DUE_DATE] = due_date_day_iso
            chore_info[const.DATA_CHORE_APPLICABLE_DAYS] = list(applicable_days)
            # A per-assignee due date takes precedence over the chore-level one,
            # so it has to be overridden too or the chore stays owed.
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {
                self._assignee_id: due_date_day_iso
            }

        try:
            yield
        finally:
            for chore_id, original in originals.items():
                chore_info = self._chore_info(chore_id)
                chore_info.clear()
                chore_info.update(original)

    @contextmanager
    def neutral_day(self, day_iso: str) -> Iterator[None]:
        """Make the tracked chores neither owed nor missed on ``day_iso``.

        Both halves are required. A due date on another day keeps the chore out of
        the eligible scope, and a weekly frequency has no occurrence inside a
        window shorter than a week, so the miss check stays quiet. Defeating only
        the eligibility check would leave the miss check free to break the streak,
        which is the opposite of a neutral day.
        """
        due_date_day_iso = (date.fromisoformat(day_iso) + timedelta(days=7)).isoformat()
        with self.chore_schedule(
            frequency=const.FREQUENCY_WEEKLY,
            due_date_day_iso=due_date_day_iso,
        ):
            yield

    def owed_today(self, day_iso: str) -> int:
        """Number of tracked chores this assignee is owed on the given day.

        Cases assert this rather than trusting the scenario, because the harness
        constructs its own schedules (decision 15).
        """
        snapshot = (
            self._coordinator.statistics_manager.get_badge_scoped_today_completion(
                self._assignee_id,
                self._chore_ids,
                today_iso=day_iso,
                cycle_start_iso=day_iso,
                only_due_today=False,
            )
        )
        return int(snapshot["due_count"])


# ============================================================================
# TESTS: the streak must survive a day that is still in progress
# ============================================================================


class TestStreakSurvivesInProgressDay:
    """A day with no approvals yet is not a missed day."""

    async def test_start_of_day_evaluation_keeps_intact_streak(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """Rollover alone must not zero a streak that was intact yesterday.

        This is the issue #294 defect: yesterday's streak is intact and today
        has simply not started, yet the count is reset to 0.
        """
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)
        replay.seed_streak(days=2, last_update_day=day_key(-1))

        await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 2, (
            "Evaluating a day with no approvals yet reset the streak; "
            "an unfinished day must not break a streak that was intact yesterday"
        )

    async def test_streak_increments_on_consecutive_completed_days(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """Two consecutive completed days must produce a streak of 2."""
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)

        await replay.start_day(day_key(-2))
        await replay.complete_day(day_key(-2))

        await replay.start_day(day_key(-1))
        await replay.complete_day(day_key(-1))

        assert replay.days_cycle_count == 2, (
            "Consecutive completed days did not accumulate; "
            "the streak is restarting instead of continuing"
        )

    async def test_neutral_day_holds_without_restamping_the_anchor(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """A day where nothing is owed is a true no-op, not a re-stamp.

        The count and the anchor both have to stand still: moving the anchor on a
        neutral day would silently erase the window the miss check depends on.
        """
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)
        replay.seed_streak(days=2, last_update_day=day_key(-1))

        with replay.neutral_day(day_key(0)):
            # Without this the test could pass for the wrong reason: a day that is
            # still owed holds in-progress too, and produces the same two values.
            assert replay.owed_today(day_key(0)) == 0, (
                "the simulated neutral day is still owed, so the hold below would "
                "not be measuring a neutral day"
            )
            await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 2, (
            f"a day where nothing was owed changed the streak count "
            f"(count={replay.days_cycle_count})"
        )
        assert replay.last_update_day == day_key(-1), (
            "a neutral day moved the streak anchor; the hold must not re-stamp it"
        )


# ============================================================================
# TESTS: partial progress mid-day must not break the streak
# ============================================================================


class TestStreakSurvivesPartialProgress:
    """A day that is only partly done is not a missed day.

    Each chore approval triggers an evaluation, so a badge scoped to several
    chores is evaluated with a partial count several times per day.
    """

    async def test_partial_progress_holds_then_completion_advances(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """Half the tracked chores done holds the streak; the rest advances it."""
        badge_id = await _add_periodic_badge(
            hass,
            streak_scenario,
            tracked_chore_names=TRACKED_CHORE_NAMES,
        )
        replay = PeriodicDayReplay(
            streak_scenario,
            badge_id,
            tracked_chore_names=TRACKED_CHORE_NAMES,
        )
        replay.seed_streak(days=2, last_update_day=day_key(-1))

        # First of two chores approved mid-day.
        await replay.advance_day(day_key(0), approved_count=1)

        assert replay.days_cycle_count == 2, (
            "Partial progress mid-day broke the streak; "
            "a day is only missed once it has ended"
        )

        # Second chore approved: the day is now satisfied.
        await replay.advance_day(day_key(0), approved_count=2)

        assert replay.days_cycle_count == 3, (
            "Completing all tracked chores did not advance the streak"
        )


# ============================================================================
# TESTS: reaching the threshold must actually award the badge
# ============================================================================


class TestStreakBadgeAward:
    """The badge must be earnable once the threshold is reached."""

    async def test_badge_awards_after_threshold_consecutive_days(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """A threshold of 3 must be reachable across 3 completed days."""
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)

        for offset in (-3, -2, -1):
            await replay.start_day(day_key(offset))
            await replay.complete_day(day_key(offset))

        assert replay.days_cycle_count == STREAK_THRESHOLD
        assert replay.criteria_met is True, (
            f"{STREAK_THRESHOLD} consecutive completed days did not satisfy the "
            f"streak badge (count={replay.days_cycle_count})"
        )
        assert replay.earned is True


# ============================================================================
# TESTS: streaks must still break (guards against a fix that never resets)
# ============================================================================


class TestStreakStillBreaks:
    """A day that passes with no completions must still end the streak.

    The streak is seeded directly so these guards stay independent of the
    accumulation behaviour covered above.
    """

    async def test_missing_a_full_day_breaks_the_streak(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """The streak is 0 once a completed day is followed by an empty day."""
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)
        replay.seed_streak(days=2, last_update_day=day_key(-3))

        # A full day with no completions at all.
        await replay.start_day(day_key(-2))

        await replay.start_day(day_key(-1))

        assert replay.days_cycle_count == 0, (
            "A full day without completions did not break the streak"
        )

    async def test_streak_restarts_at_one_after_a_break(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """Completing a day after a break starts a new streak at 1."""
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)
        replay.seed_streak(days=2, last_update_day=day_key(-3))

        # Day -2 is skipped entirely.
        await replay.start_day(day_key(-2))

        await replay.start_day(day_key(-1))
        await replay.complete_day(day_key(-1))

        assert replay.days_cycle_count == 1, "A broken streak did not restart at 1"


# ============================================================================
# TESTS: the miss check runs once per badge, not once per scope variant
# ============================================================================


class TestMissCheckIsComputedOnce:
    """Both scope variants of a badge share one miss result."""

    async def test_single_miss_check_per_evaluation(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An evaluation runs the miss check once, not once per snapshot.

        The answer depends on the badge's advance day, not on the chore scope, so
        building both the all-tracked and due-only snapshots must not repeat the
        schedule evaluation.
        """
        badge_id = await _add_periodic_badge(hass, streak_scenario)
        replay = PeriodicDayReplay(streak_scenario, badge_id)

        statistics_manager = streak_scenario.coordinator.statistics_manager
        original = statistics_manager.has_missed_occurrence_since_advance
        calls: list[str] = []

        def counting(*args: Any, **kwargs: Any) -> bool:
            calls.append("call")
            return original(*args, **kwargs)

        monkeypatch.setattr(
            statistics_manager, "has_missed_occurrence_since_advance", counting
        )

        await replay.complete_day(day_key(-1))

        assert len(calls) == 1, (
            f"expected one miss check per evaluation, saw {len(calls)}"
        )


# ============================================================================
# TESTS: a chore that is not due today must not make the day unsatisfiable
# ============================================================================

MIXED_SCOPE_CHORES = ("Make bed", "Brush teeth", "Do homework", "Clean room")
"""Three daily chores plus one weekly due days from now.

The weekly chore is scheduled today in the calendar sense but is not *owed*
today, so it must not count against the day.
"""
MIXED_ELIGIBLE_COUNT = len(MIXED_SCOPE_CHORES) - 1


class TestNonDueChoreDoesNotBlockTheDay:
    """The defect the initiative exists to fix, proven end to end."""

    async def test_streak_advances_when_only_due_chores_are_done(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """Completing every owed chore satisfies the day despite an undated weekly.

        Before the eligible scope this scored 3/4, so the day could never be met
        and the streak could not accumulate even at full compliance.
        """
        badge_id = await _add_periodic_badge(
            hass,
            streak_scenario,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        replay = PeriodicDayReplay(
            streak_scenario,
            badge_id,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )

        await replay.advance_day(day_key(-1), approved_count=MIXED_ELIGIBLE_COUNT)

        assert replay.days_cycle_count == 1, (
            "a chore that was not due today blocked the day, so the streak could "
            "not start even with every owed chore completed"
        )
        assert replay.criteria_met is False  # threshold is higher than one day

    async def test_streak_accumulates_across_consecutive_days(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """The streak keeps climbing instead of breaking on the undated chore."""
        badge_id = await _add_periodic_badge(
            hass,
            streak_scenario,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )
        replay = PeriodicDayReplay(
            streak_scenario,
            badge_id,
            tracked_chore_names=MIXED_SCOPE_CHORES,
        )

        for offset in (-3, -2, -1):
            await replay.advance_day(
                day_key(offset), approved_count=MIXED_ELIGIBLE_COUNT
            )

        assert replay.days_cycle_count == STREAK_THRESHOLD, (
            "the streak did not accumulate across consecutive satisfied days"
        )
        assert replay.criteria_met is True
        assert replay.earned is True

    async def test_undated_weekly_chore_is_not_owed_today(
        self,
        hass: HomeAssistant,
        streak_scenario: SetupResult,
    ) -> None:
        """Confirms the scenario: the weekly chore is scheduled but not owed.

        Guards the test above from passing for the wrong reason - if the weekly
        were owed, the eligible count would be four and the assertion would be
        measuring something else.
        """
        chore_id = streak_scenario.chore_ids["Clean room"]
        snapshot = streak_scenario.coordinator.statistics_manager.get_badge_scoped_today_completion(
            streak_scenario.assignee_ids[ASSIGNEE_NAME],
            [chore_id],
            today_iso=dt_utils.dt_today_iso(),
            cycle_start_iso=dt_utils.dt_today_iso(),
            only_due_today=False,
        )

        assert snapshot["total_count"] == 1
        assert snapshot["due_count"] == 0
