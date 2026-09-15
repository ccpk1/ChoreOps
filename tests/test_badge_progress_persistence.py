"""Persistence and status alignment tests for schedule-aware streaks (Phase 3).

Phase 2 changed the evaluators to return the *unchanged* count on a held or
neutral day. This suite pins the write path so that intent actually holds:

- A neutral day (nothing owed) must write nothing at all, so the progress record
  is left untouched and no spurious persistence is triggered.
- A break must write `0` and deliberately leave `last_update_day` stale, because
  that stale anchor is what the miss check reads until the streak restarts.
- A restart must stamp a fresh anchor, proving the stale anchor cannot block
  recovery forever.
- A neutral day must not re-award an already-earned badge.
- A cycle rollover resets the streak on purpose, and must stay distinguishable
  from a neutral day.

Uses scenario_minimal.yaml via the #294 day-replay harness.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.utils import dt_utils
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.test_badge_streak_midnight_reset import (
    PeriodicDayReplay,
    _add_periodic_badge,
    day_key,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


CHORE_WITH_A_SCHEDULE = "Organize closet"
"""A monthly chore dated well in the future.

Nothing is owed on it today, so a badge scoped only to it is neutral until its
due date arrives.
"""


@pytest.fixture
async def persistence_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the minimal scenario for persistence tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


async def _neutral_replay(
    hass: HomeAssistant,
    setup: SetupResult,
) -> tuple[PeriodicDayReplay, str]:
    """Build a replay whose badge owes nothing today."""
    badge_id = await _add_periodic_badge(
        hass,
        setup,
        tracked_chore_names=(CHORE_WITH_A_SCHEDULE,),
    )
    replay = PeriodicDayReplay(
        setup,
        badge_id,
        tracked_chore_names=(CHORE_WITH_A_SCHEDULE,),
    )
    return replay, badge_id


class TestNeutralDayWritesNothing:
    """A held day must not touch the persisted record."""

    async def test_neutral_day_leaves_the_progress_record_untouched(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """Re-evaluating a neutral day makes zero writes.

        A write here would persist and trigger an entity update on a day where
        nothing happened, which is part of why the original streak behaviour was
        hard to reason about.

        The day is evaluated once first: the badge's progress record is populated
        lazily on its first evaluation, and that initialization is a legitimate
        write. Snapshotting afterwards isolates the steady-state behaviour.
        """
        replay, _badge_id = await _neutral_replay(hass, persistence_scenario)
        replay.seed_streak(days=2, last_update_day=day_key(-1))
        await replay.start_day(day_key(0))

        before = copy.deepcopy(replay._progress())

        await replay.start_day(day_key(0))

        assert replay._progress() == before, "a neutral day modified the record"

    async def test_neutral_day_keeps_the_count_and_the_anchor(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """The count holds and `last_update_day` is not stomped by a neutral day.

        Re-stamping the anchor on a held day would move the miss window forward
        and silently hide an occurrence that was actually missed.
        """
        replay, _badge_id = await _neutral_replay(hass, persistence_scenario)
        replay.seed_streak(days=4, last_update_day=day_key(-1))

        await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 4
        assert replay.last_update_day == day_key(-1)

    async def test_neutral_day_does_not_re_award_an_earned_badge(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """An already-earned badge is not awarded again on a neutral day.

        Badges are never removed, so without this a stale high streak would keep
        paying out while no work is being done.
        """
        replay, badge_id = await _neutral_replay(hass, persistence_scenario)
        replay.seed_streak(days=4, last_update_day=day_key(-1))

        assignee_data = persistence_scenario.coordinator.assignees_data[
            persistence_scenario.assignee_ids["Zoë"]
        ]
        badges_earned = assignee_data.setdefault(const.DATA_USER_BADGES_EARNED, {})
        badges_earned[badge_id] = {
            const.DATA_USER_BADGES_EARNED_AWARD_COUNT: 1,
            const.DATA_USER_BADGES_EARNED_LAST_AWARDED: dt_utils.dt_now_utc_iso(),
        }
        before = copy.deepcopy(badges_earned[badge_id])

        await replay.start_day(day_key(0))

        assert badges_earned[badge_id] == before
        assert badges_earned[badge_id][const.DATA_USER_BADGES_EARNED_AWARD_COUNT] == 1


class TestBreakAndRestartPersistence:
    """The break writes zero and keeps the anchor the miss check needs."""

    async def test_break_writes_zero_and_leaves_the_anchor_stale(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """A broken streak persists 0 and does not advance `last_update_day`.

        The staleness is load-bearing: it is the miss check's anchor, so the
        missed occurrence keeps being detected until the streak restarts.
        """
        badge_id = await _add_periodic_badge(hass, persistence_scenario)
        replay = PeriodicDayReplay(persistence_scenario, badge_id)

        stale_anchor = day_key(-3)
        replay.seed_streak(days=3, last_update_day=stale_anchor)

        # The daily chore has occurrences the streak never credited, so an
        # occurrence was missed and the streak breaks.
        await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 0
        assert replay.last_update_day == stale_anchor, (
            "the break advanced the anchor, which would blind the miss check"
        )

    async def test_compliant_day_after_a_break_starts_a_new_streak(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """A satisfied day after a missed occurrence is credited, not discarded.

        The missed occurrence voids the previous streak, but the work done today
        still counts, so the streak restarts at 1 in the same evaluation. Leaving
        it at 0 would mean the child's compliant day earned nothing until a later
        evaluation - and the persisted-break and not-yet-persisted-break paths
        produced different answers for the identical situation.
        """
        badge_id = await _add_periodic_badge(hass, persistence_scenario)
        replay = PeriodicDayReplay(persistence_scenario, badge_id)
        replay.seed_streak(days=3, last_update_day=day_key(-3))

        await replay.complete_day(day_key(0))

        assert replay.days_cycle_count == 1
        assert replay.last_update_day == day_key(0)

    async def test_miss_without_a_satisfied_day_still_breaks(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """A missed occurrence with nothing done today still breaks to 0.

        The counterpart of the test above: credit follows from today being
        satisfied, not from the miss alone.
        """
        badge_id = await _add_periodic_badge(hass, persistence_scenario)
        replay = PeriodicDayReplay(persistence_scenario, badge_id)
        replay.seed_streak(days=3, last_update_day=day_key(-3))

        await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 0

    async def test_restarted_streak_is_not_broken_again_by_the_old_miss(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """Re-evaluating after a restart holds, because the anchor moved."""
        badge_id = await _add_periodic_badge(hass, persistence_scenario)
        replay = PeriodicDayReplay(persistence_scenario, badge_id)
        replay.seed_streak(days=3, last_update_day=day_key(-3))

        await replay.complete_day(day_key(0))
        await replay.complete_day(day_key(0))

        assert replay.days_cycle_count == 1, (
            "re-evaluating after a restart re-broke the streak"
        )


class TestCycleRolloverIsNotANeutralDay:
    """A cycle boundary resets on purpose; a neutral day must not."""

    async def test_open_cycle_does_not_reset_a_neutral_day(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """A cycle that has not ended leaves the streak alone on a neutral day.

        Guards step 4 of the phase: the rollover path must only fire on a real
        `end_date < today` boundary, never on a day the evaluator merely held.
        """
        replay, badge_id = await _neutral_replay(hass, persistence_scenario)
        badge_info = persistence_scenario.coordinator.badges_data[badge_id]
        reset_schedule = badge_info[const.DATA_BADGE_RESET_SCHEDULE]

        reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY] = (
            const.FREQUENCY_WEEKLY
        )
        reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_START_DATE] = day_key(-1)
        reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE] = day_key(6)

        replay.seed_streak(days=4, last_update_day=day_key(-1))

        await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 4

    async def test_ended_cycle_resets_the_streak(
        self,
        hass: HomeAssistant,
        persistence_scenario: SetupResult,
    ) -> None:
        """An ended cycle clears the counter, which is the badge's own rule.

        Distinguishes a genuine rollover from the neutral-day no-op above: both
        look like a held day from the evaluator's side, but only one is a reset.
        """
        replay, badge_id = await _neutral_replay(hass, persistence_scenario)
        badge_info = persistence_scenario.coordinator.badges_data[badge_id]
        reset_schedule = badge_info[const.DATA_BADGE_RESET_SCHEDULE]

        reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY] = (
            const.FREQUENCY_WEEKLY
        )
        reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_START_DATE] = day_key(-8)
        reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE] = day_key(-1)

        replay.seed_streak(days=4, last_update_day=day_key(-2))

        await replay.start_day(day_key(0))

        assert replay.days_cycle_count == 0
