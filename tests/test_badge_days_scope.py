"""Days-family scope coverage for badge target types (Phase 4).

The Days family shares the day-status layer with the Streak family, so decision 8
applies the eligible scope to both: a chore that is not owed today must not sit in
a percentage denominator. Unlike the Streak family it *accumulates* - a missed day
does not reset it - so the cases here assert day counts rather than run lengths.

Three deliberate distinctions are pinned, because each could otherwise read as a
bug:

- The percentage variants (`Days 100%`, `Days 80%`) score against the chores owed
  today, so a non-due chore no longer makes a day unmet.
- The absolute-count variants (`Days Minimum 3/5/7`) keep the all-selected scope
  (decision 10). A non-due chore is an impossible obstacle to a ratio but extra
  credit to a count, and applying the eligible scope there would make the
  threshold unreachable.
- A selected chore with no schedule still counts as available every day
  (decision 11), so a badge scoped to open one-timers is never permanently neutral.

Uses scenario_minimal.yaml.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from tests.helpers.setup import SetupResult, setup_from_yaml
from tests.test_badge_streak_midnight_reset import (
    PeriodicDayReplay,
    _add_periodic_badge,
    day_key,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


DAILY_CHORES = ("Make bed", "Brush teeth", "Do homework")
"""The three daily chores in scenario_minimal."""

WEEKLY_CHORE = "Clean room"
MONTHLY_CHORE = "Organize closet"
"""Chores that are scheduled today in the calendar sense but not owed today."""

MIXED_SCOPE = (*DAILY_CHORES, WEEKLY_CHORE, MONTHLY_CHORE)
"""Five selected chores, only the dailies owed - a 3/5 ratio, not 5/5."""

ELIGIBLE_IN_MIXED = len(DAILY_CHORES)


@pytest.fixture
async def days_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for the Days-family tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


async def _days_replay(
    hass: HomeAssistant,
    setup: SetupResult,
    *,
    target_type: str,
    threshold: int,
    tracked_chore_names: tuple[str, ...] = MIXED_SCOPE,
) -> PeriodicDayReplay:
    """Create a Days badge and return the replay driving it."""
    badge_id = await _add_periodic_badge(
        hass,
        setup,
        target_type=target_type,
        threshold=threshold,
        tracked_chore_names=tracked_chore_names,
    )
    return PeriodicDayReplay(
        setup,
        badge_id,
        tracked_chore_names=tracked_chore_names,
    )


def _assert_scope_precondition(setup: SetupResult, replay: PeriodicDayReplay) -> None:
    """Assert the scenario really presents a 3-of-5 eligible day.

    Without this the ratio assertions below could pass because every selected
    chore was owed, which is the case the eligible scope is supposed to change.
    """
    owed = replay.owed_today(day_key(0))
    assert owed == ELIGIBLE_IN_MIXED, (
        f"expected {ELIGIBLE_IN_MIXED} of {len(MIXED_SCOPE)} selected chores to be "
        f"owed today, but the eligible scope reported {owed}"
    )


# ============================================================================
# TESTS: the percentage variants score against the chores owed today
# ============================================================================


class TestPercentDaysUseEligibleScope:
    """`Days 100%` and `Days 80%` must ignore chores that are not owed."""

    async def test_all_percent_days_advance_on_a_partial_selected_scope(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """Completing only the owed chores must satisfy a 100% days badge.

        Before the eligible scope this day scored 3/5 = 60%, so it could never be
        met and the badge stalled on every day a non-daily chore was selected.
        """
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=2,
        )
        _assert_scope_precondition(days_scenario, replay)

        await replay.advance_day(day_key(-1), approved_count=ELIGIBLE_IN_MIXED)

        assert replay.days_cycle_count == 1, (
            "the day did not count even though every owed chore was completed; "
            "a non-due selected chore is still sitting in the denominator"
        )

    async def test_eighty_percent_days_advance_on_a_partial_selected_scope(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """The 80% variant must also score the eligible fraction.

        This is the sharp discriminator: 3/3 clears 80% while the all-selected
        3/5 = 60% would not, so the assertion fails if the scope regresses.
        """
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES,
            threshold=2,
        )
        _assert_scope_precondition(days_scenario, replay)

        await replay.advance_day(day_key(-1), approved_count=ELIGIBLE_IN_MIXED)

        assert replay.days_cycle_count == 1, (
            "the eligible fraction 3/3 did not clear the 80% threshold, so the day "
            "is still being scored against all five selected chores"
        )

    async def test_unmet_owed_chore_still_holds_the_day(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """The eligible scope must not make the day unconditionally satisfiable."""
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=2,
        )
        _assert_scope_precondition(days_scenario, replay)

        # One owed chore left undone: 2/3 fails the 100% requirement.
        await replay.advance_day(day_key(-1), approved_count=ELIGIBLE_IN_MIXED - 1)

        assert replay.days_cycle_count == 0, (
            "a day with an owed chore left undone counted toward the badge"
        )


# ============================================================================
# TESTS: the absolute-count variants keep the all-selected scope (decision 10)
# ============================================================================


class TestMinimumCountKeepsAllSelectedScope:
    """`Days Minimum N` counts completions regardless of due date."""

    async def test_minimum_five_is_satisfiable_with_only_three_owed(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """A count badge must not become unreachable when few chores are owed.

        Five chores are selected but only three are owed, so an eligible scope
        would cap the day at three completions and `Days Minimum 5` could never be
        met again. The count variants therefore keep counting every selected chore.
        """
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES,
            threshold=1,
        )
        _assert_scope_precondition(days_scenario, replay)

        await replay.advance_day(day_key(-1), approved_count=len(MIXED_SCOPE))

        assert replay.days_cycle_count == 1, (
            "completing all five selected chores did not satisfy `Days Minimum 5`; "
            "the eligible scope has leaked into the absolute-count variants"
        )

    async def test_minimum_five_is_not_met_by_the_owed_chores_alone(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """Three completions must not satisfy a minimum of five.

        Pairs with the case above: together they prove the count is absolute
        rather than a ratio, in both directions.
        """
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES,
            threshold=1,
        )
        _assert_scope_precondition(days_scenario, replay)

        await replay.advance_day(day_key(-1), approved_count=ELIGIBLE_IN_MIXED)

        assert replay.days_cycle_count == 0, (
            "three completions satisfied a minimum of five, so the threshold is "
            "being applied as a ratio"
        )


# ============================================================================
# TESTS: a selected chore with no schedule stays available (decision 11)
# ============================================================================


class TestDatelessOneTimeChoreStaysInScope:
    """A chore with no due date and no recurrence must not be dropped."""

    async def test_dateless_one_time_chore_counts_toward_the_day(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """Completing an open one-timer must still help a ratio badge.

        `_is_chore_scheduled_today_for_assignee` reports it as never due today, so
        a strict eligible scope would silently exclude a chore the user explicitly
        selected.
        """
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=1,
            tracked_chore_names=(MONTHLY_CHORE,),
        )
        chore_id = days_scenario.chore_ids[MONTHLY_CHORE]
        chore_info = days_scenario.coordinator.chores_data[chore_id]
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE
        chore_info[const.DATA_CHORE_DUE_DATE] = None
        chore_info[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {}

        assert replay.owed_today(day_key(0)) == 1, (
            "an open one-timer was dropped from the badge scope, so completing it "
            "would stop helping and missing it would stop mattering"
        )

        await replay.advance_day(day_key(-1), approved_count=1)

        assert replay.days_cycle_count == 1, (
            "completing a dateless one-time chore did not count toward the badge"
        )

    async def test_badge_of_only_open_one_timers_does_not_stall(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """A badge scoped entirely to open one-timers must still be earnable.

        Every selected chore is undated with no recurrence, so a strict eligible
        scope would leave the eligible count at zero on every day. The day would
        then read as neutral forever and the badge could neither advance nor
        break - permanently inert.
        """
        one_timers = (MONTHLY_CHORE, WEEKLY_CHORE)
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=2,
            tracked_chore_names=one_timers,
        )
        for chore_name in one_timers:
            chore_info = days_scenario.coordinator.chores_data[
                days_scenario.chore_ids[chore_name]
            ]
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE
            chore_info[const.DATA_CHORE_DUE_DATE] = None
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {}

        assert replay.owed_today(day_key(0)) == len(one_timers), (
            "an all-one-timer badge has no eligible chores, so it can never advance"
        )

        await replay.advance_day(day_key(-2), approved_count=len(one_timers))
        await replay.advance_day(day_key(-1), approved_count=len(one_timers))

        assert replay.days_cycle_count == 2, (
            "a badge scoped only to open one-timers stalled instead of accumulating"
        )
        assert replay.criteria_met is True


# ============================================================================
# TESTS: the worked-answers table from the plan
# ============================================================================


class TestWorkedAnswersAreUnchanged:
    """Five selected chores, three dated and two dateless dailies."""

    async def test_missing_a_dated_and_a_dateless_chore_weigh_the_same(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """Both dateless dailies are eligible, so the outcomes do not change.

        The plan's reference table: with five selected chores where the two
        undated ones are daily recurring, the eligible count equals the selected
        count, so this initiative alters nothing. The cases that change are the
        ones where a chore is genuinely unavailable - covered above.
        """
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES,
            threshold=1,
        )

        # Four of the five completed: 4/5 = 80%, which clears the threshold.
        await replay.advance_day(day_key(-1), approved_count=len(MIXED_SCOPE) - 1)

        assert replay.days_cycle_count == 1, (
            "a day with four of five chores completed did not clear the 80% threshold"
        )

    async def test_a_single_missed_owed_chore_fails_the_full_percentage(
        self,
        hass: HomeAssistant,
        days_scenario: SetupResult,
    ) -> None:
        """Two of three owed chores is 67%, which must not satisfy 100%."""
        replay = await _days_replay(
            hass,
            days_scenario,
            target_type=const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
            threshold=1,
        )
        _assert_scope_precondition(days_scenario, replay)

        await replay.advance_day(day_key(-1), approved_count=1)

        assert replay.days_cycle_count == 0, (
            "a partially completed day satisfied a 100% days badge"
        )
