"""Tests for the schedule-aware day classification snapshot (Phase 1).

Covers the data layer that badge evaluation reads from:

- `due_count` / `approved_due_today`: the eligible scope, where a chore only
  counts when it is actionable today.
- `missed_since_advance`: whether a scheduled occurrence passed unmet since the
  badge streak last advanced.
- `ChoreEngine.build_schedule_config`: the shared schedule-config builder
  extracted from `calculate_streak`.

The `missed_since_advance` cases pin the contract traps: the window ends at the
start of today (never "now"), there is no miss without a window, and the anchor
is the streak's own advance day rather than a chore completion timestamp.

Uses scenario_minimal.yaml: 3 daily chores with no due date (always eligible)
and 2 dated chores due well in the future (not eligible today).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.chore_engine import ChoreEngine
from custom_components.choreops.utils import dt_utils
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


ELIGIBLE_TODAY = ("Make bed", "Brush teeth", "Do homework")
"""Daily chores with no due date, so they are actionable every day."""

NOT_ELIGIBLE_TODAY = ("Clean room", "Organize closet")
"""Dated chores whose due dates are in the future."""


@pytest.fixture
async def snapshot_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the minimal scenario for snapshot tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


def day_offset(days: int) -> str:
    """Return a local date key offset from today."""
    return (dt_utils.dt_today_local() + timedelta(days=days)).isoformat()


def read_snapshot(
    setup: SetupResult,
    *,
    chore_names: tuple[str, ...],
    only_due_today: bool = False,
    last_update_day_iso: str = "",
) -> dict[str, Any]:
    """Read a completion snapshot for the named chores."""
    tracked = [setup.chore_ids[name] for name in chore_names]
    return setup.coordinator.statistics_manager.get_badge_scoped_today_completion(
        setup.assignee_ids["Zoë"],
        tracked,
        today_iso=dt_utils.dt_today_iso(),
        cycle_start_iso=day_offset(-5),
        only_due_today=only_due_today,
        last_update_day_iso=last_update_day_iso,
    )


class TestEligibleScope:
    """`due_count` and `approved_due_today' express the eligible scope."""

    def test_only_due_chores_count_as_eligible(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """Dateless dailies are eligible; future-dated chores are not."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY + NOT_ELIGIBLE_TODAY,
        )

        assert snapshot["total_count"] == 5
        assert snapshot["due_count"] == len(ELIGIBLE_TODAY)

    def test_no_chores_approved_yet_yields_empty_eligible_approvals(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """Nothing is approved on a fresh scenario."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY + NOT_ELIGIBLE_TODAY,
        )

        assert snapshot["approved_count"] == 0
        assert snapshot["approved_due_today"] == 0

    def test_only_due_today_scope_matches_eligible_count(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """The due-only snapshot only contains eligible chores."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY + NOT_ELIGIBLE_TODAY,
            only_due_today=True,
        )

        assert snapshot["total_count"] == len(ELIGIBLE_TODAY)
        assert snapshot["due_count"] == len(ELIGIBLE_TODAY)

    @pytest.mark.parametrize(
        ("chore_names", "expected_due"),
        [
            pytest.param(ELIGIBLE_TODAY, 3, id="dateless_dailies_only"),
            pytest.param(NOT_ELIGIBLE_TODAY, 0, id="future_dated_only"),
            pytest.param((), 0, id="no_tracked_chores"),
        ],
    )
    def test_eligible_count_follows_chore_schedules(
        self,
        snapshot_scenario: SetupResult,
        chore_names: tuple[str, ...],
        expected_due: int,
    ) -> None:
        """Eligibility tracks each chore's schedule, not the tracked list length."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=chore_names,
        )

        assert snapshot["due_count"] == expected_due
        assert snapshot["total_count"] == len(chore_names)


class TestMissedSinceAdvance:
    """`missed_since_advance` follows the frozen contract."""

    def test_no_anchor_means_no_miss(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """A badge that never advanced has no window to evaluate."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY,
            last_update_day_iso="",
        )

        assert snapshot["missed_since_advance"] is False

    def test_unparseable_anchor_means_no_miss(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """Bad data must not break a valid streak."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY,
            last_update_day_iso="not-a-date",
        )

        assert snapshot["missed_since_advance"] is False

    def test_anchor_today_means_no_miss(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """A streak already advanced today has an empty window."""
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY,
            last_update_day_iso=day_offset(0),
        )

        assert snapshot["missed_since_advance"] is False

    def test_todays_pending_occurrence_is_not_a_miss(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """The window ends at the start of today, never at the current time.

        This is the trap that would otherwise re-create the issue #294 symptom:
        a streak advancing yesterday must not be broken mid-way through today by
        the occurrence that has not had a chance to happen yet.
        """
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=ELIGIBLE_TODAY,
            last_update_day_iso=day_offset(-1),
        )

        assert snapshot["missed_since_advance"] is False

    def test_occurrence_after_the_anchor_is_a_miss(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """A daily occurrence that passed unmet since the anchor is a miss.

        The anchor is three days back, so the daily chores had occurrences that
        were never completed.
        """
        snapshot = read_snapshot(
            snapshot_scenario,
            chore_names=("Make bed",),
            last_update_day_iso=day_offset(-3),
        )

        assert snapshot["missed_since_advance"] is True

    def test_chore_without_a_schedule_never_reports_a_miss(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """An open-ended chore has no occurrences to miss."""
        chore_id = snapshot_scenario.chore_ids["Make bed"]
        chore_info = snapshot_scenario.coordinator.chores_data[chore_id]
        original = chore_info[const.DATA_CHORE_RECURRING_FREQUENCY]
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_NONE

        try:
            snapshot = read_snapshot(
                snapshot_scenario,
                chore_names=("Make bed",),
                last_update_day_iso=day_offset(-30),
            )
        finally:
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = original

        assert snapshot["missed_since_advance"] is False

    def test_unknown_chore_id_is_skipped(
        self,
        snapshot_scenario: SetupResult,
    ) -> None:
        """A tracked chore that no longer exists must not report a miss."""
        snapshot = snapshot_scenario.coordinator.statistics_manager.get_badge_scoped_today_completion(
            snapshot_scenario.assignee_ids["Zoë"],
            ["does-not-exist"],
            today_iso=dt_utils.dt_today_iso(),
            cycle_start_iso=day_offset(-5),
            only_due_today=False,
            last_update_day_iso=day_offset(-30),
        )

        assert snapshot["missed_since_advance"] is False


class TestBuildScheduleConfig:
    """The shared schedule-config builder mirrors the chore fields."""

    def test_applicable_day_names_become_integers(self) -> None:
        """Weekday names are converted to the integers RecurrenceEngine expects."""
        config = ChoreEngine.build_schedule_config(
            {
                const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                const.DATA_CHORE_APPLICABLE_DAYS: ["mon", "wed", 5],
            },
            base_date_iso="2026-09-14T00:00:00+00:00",
        )

        assert config["applicable_days"] == [0, 2, 5]

    def test_applicable_day_names_accept_full_names_case_insensitively(self) -> None:
        """Matching is case-insensitive but only the abbreviated keys resolve."""
        config = ChoreEngine.build_schedule_config(
            {
                const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                const.DATA_CHORE_APPLICABLE_DAYS: ["MON", "wed"],
            },
            base_date_iso="2026-09-14T00:00:00+00:00",
        )

        assert config["applicable_days"] == [0, 2]

    def test_unknown_day_name_is_dropped(self) -> None:
        """An unrecognised weekday does not raise."""
        config = ChoreEngine.build_schedule_config(
            {
                const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                const.DATA_CHORE_APPLICABLE_DAYS: ["notaday"],
            },
            base_date_iso="2026-09-14T00:00:00+00:00",
        )

        assert config["applicable_days"] == []

    def test_defaults_when_custom_fields_are_absent(self) -> None:
        """Interval defaults to 1 day and daily_multi_times to empty."""
        config = ChoreEngine.build_schedule_config(
            {const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY},
            base_date_iso="2026-09-14T00:00:00+00:00",
        )

        assert config["frequency"] == const.FREQUENCY_WEEKLY
        assert config["interval"] == 1
        assert config["interval_unit"] == const.TIME_UNIT_DAYS
        assert config["daily_multi_times"] == ""
        assert config["base_date"] == "2026-09-14T00:00:00+00:00"

    def test_custom_interval_fields_are_preserved(self) -> None:
        """Explicit interval settings pass through unchanged."""
        config = ChoreEngine.build_schedule_config(
            {
                const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
                const.DATA_CHORE_CUSTOM_INTERVAL: 3,
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: const.TIME_UNIT_DAYS,
                const.DATA_CHORE_DAILY_MULTI_TIMES: "08:00,16:00",
            },
            base_date_iso="2026-09-14T00:00:00+00:00",
        )

        assert config["interval"] == 3
        assert config["interval_unit"] == const.TIME_UNIT_DAYS
        assert config["daily_multi_times"] == "08:00,16:00"

    def test_missing_frequency_falls_back_to_none(self) -> None:
        """A chore with no frequency is treated as open-ended."""
        config = ChoreEngine.build_schedule_config(
            {},
            base_date_iso="2026-09-14T00:00:00+00:00",
        )

        assert config["frequency"] == const.FREQUENCY_NONE


# ============================================================================
# Phase 1B — obligation scope
# ============================================================================

SHARED_ASSIGNEES = ("Zoë", "Max!", "Lila")
STANDBY_ASSIGNEES = ("Zoë", "Max!")
APPROVER_NAME = "Môm Astrid Stârblüm"


@pytest.fixture
async def shared_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the shared scenario: 3 assignees, shared_* and rotation chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def standby_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the primary-standby scenario: 2 assignees, one mode per chore."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_primary_standby.yaml",
    )


def counts_toward(setup: SetupResult, assignee_name: str, chore_name: str) -> bool:
    """Return whether a chore forms part of an assignee's obligation today."""
    chore_id = setup.chore_ids[chore_name]
    return setup.coordinator.statistics_manager._chore_counts_toward_today(
        chore_id,
        setup.coordinator.chores_data[chore_id],
        setup.assignee_ids[assignee_name],
        dt_utils.dt_today_iso(),
    )


def turn_holder_id(setup: SetupResult, chore_name: str) -> str:
    """Return the current turn holder's internal ID for a rotation chore."""
    chore_info = setup.coordinator.chores_data[setup.chore_ids[chore_name]]
    turn_holder = chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID]
    assert isinstance(turn_holder, str) and turn_holder, "no turn holder set"
    return turn_holder


def name_of(setup: SetupResult, assignee_id: str) -> str:
    """Return an assignee's display name from their internal ID."""
    for name, internal_id in setup.assignee_ids.items():
        if internal_id == assignee_id:
            return name
    raise AssertionError(f"Unknown assignee id: {assignee_id}")


class TestObligationScopeRotation:
    """Only the assignee who owes a rotation chore is charged for it."""

    def test_rotation_charges_exactly_one_assignee(
        self,
        shared_scenario: SetupResult,
    ) -> None:
        """A rotation chore is one assignee's obligation, not everyone's.

        Before Phase 1B every assigned assignee was charged, so a badge scoped to
        a rotation chore could never be satisfied by the non-turn assignees.
        """
        charged = [
            name
            for name in SHARED_ASSIGNEES
            if counts_toward(shared_scenario, name, "Dishes Rotation")
        ]

        assert charged == [
            name_of(shared_scenario, turn_holder_id(shared_scenario, "Dishes Rotation"))
        ]

    def test_rotation_charges_the_turn_holder(
        self,
        shared_scenario: SetupResult,
    ) -> None:
        """The assignee whose turn it is must be charged."""
        holder = name_of(
            shared_scenario, turn_holder_id(shared_scenario, "Dishes Rotation")
        )

        assert counts_toward(shared_scenario, holder, "Dishes Rotation") is True

    @pytest.mark.parametrize(
        "chore_name",
        [
            pytest.param("Dishes Rotation", id="rotation_simple_daily"),
            pytest.param("Vacuum Living Room", id="rotation_simple_weekly"),
        ],
    )
    def test_rotation_does_not_charge_non_turn_assignees(
        self,
        shared_scenario: SetupResult,
        chore_name: str,
    ) -> None:
        """Assignees who do not hold the turn cannot complete it, so it is not theirs."""
        holder_id = turn_holder_id(shared_scenario, chore_name)

        for name in SHARED_ASSIGNEES:
            if shared_scenario.assignee_ids[name] == holder_id:
                continue
            assert counts_toward(shared_scenario, name, chore_name) is False


class TestObligationScopeShared:
    """Shared modes charge the assignees who can actually act."""

    @pytest.mark.parametrize(
        "chore_name",
        [
            pytest.param("Family dinner cleanup", id="shared_all_three"),
            pytest.param("Take out trash", id="shared_first_three"),
            pytest.param("Walk the dog", id="shared_all_two_subset"),
        ],
    )
    def test_directly_assigned_assignees_are_charged(
        self,
        shared_scenario: SetupResult,
        chore_name: str,
    ) -> None:
        """Before any completion, every directly assigned assignee owes the chore."""
        assigned = shared_scenario.coordinator.chores_data[
            shared_scenario.chore_ids[chore_name]
        ][const.DATA_CHORE_ASSIGNED_USER_IDS]

        for name in SHARED_ASSIGNEES:
            if shared_scenario.assignee_ids[name] not in assigned:
                continue
            assert counts_toward(shared_scenario, name, chore_name) is True

    async def test_completed_by_other_relieves_the_other_assignees(
        self,
        shared_scenario: SetupResult,
    ) -> None:
        """A single-completer chore finished by one assignee stops being owed by others.

        This is also the completed-chore guard: the assignee who finished it must
        keep being charged, or the obligation could never be satisfied.
        """
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Take out trash"]
        zoë_id = shared_scenario.assignee_ids["Zoë"]

        await coordinator.chore_manager.approve_chore(APPROVER_NAME, zoë_id, chore_id)

        assert counts_toward(shared_scenario, "Zoë", "Take out trash") is True
        assert counts_toward(shared_scenario, "Max!", "Take out trash") is False
        assert counts_toward(shared_scenario, "Lila", "Take out trash") is False

    async def test_completed_chore_keeps_counting_for_the_completer(
        self,
        shared_scenario: SetupResult,
    ) -> None:
        """**Highest-risk trap**: a chore the assignee completed still owes.

        Excluding `completed` from the obligation would make every satisfied day
        unsatisfiable, so this asserts the deny-list default directly. The claim
        mode is asserted too, so the test cannot pass vacuously by ending up in
        some unrelated state.
        """
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Family dinner cleanup"]
        zoë_id = shared_scenario.assignee_ids["Zoë"]

        await coordinator.chore_manager.approve_chore(APPROVER_NAME, zoë_id, chore_id)

        context = coordinator.chore_manager.get_chore_status_context(zoë_id, chore_id)
        assert context[const.CHORE_CTX_CLAIM_MODE] == (
            const.CHORE_CLAIM_MODE_BLOCKED_ALREADY_APPROVED
        )
        assert counts_toward(shared_scenario, "Zoë", "Family dinner cleanup") is True

    @pytest.mark.parametrize(
        "chore_name",
        [
            pytest.param("Family dinner cleanup", id="shared_all"),
            pytest.param("Take out trash", id="shared_first"),
        ],
    )
    def test_non_rotation_modes_exclude_nothing(
        self,
        shared_scenario: SetupResult,
        chore_name: str,
    ) -> None:
        """Non-rotation modes are unchanged: every scheduled chore still counts.

        Guards against Phase 1B narrowing the scope for modes that had no
        turn-order problem to begin with. These chores are dateless dailies, so
        the obligation covers the whole tracked chore for every assignee.
        """
        chore_id = shared_scenario.chore_ids[chore_name]

        for name in SHARED_ASSIGNEES:
            snapshot = shared_scenario.coordinator.statistics_manager.get_badge_scoped_today_completion(
                shared_scenario.assignee_ids[name],
                [chore_id],
                today_iso=dt_utils.dt_today_iso(),
                cycle_start_iso=dt_utils.dt_today_iso(),
                only_due_today=False,
            )
            assert snapshot["total_count"] == 1
            assert snapshot["due_count"] == snapshot["total_count"], (
                f"{name} lost {chore_name} from the obligation scope"
            )

    async def test_snapshot_due_count_excludes_unowed_chores(
        self,
        shared_scenario: SetupResult,
    ) -> None:
        """The snapshot denominator reflects the obligation, not the assignment list.

        A shared_first chore completed by Zoë must drop out of Max's denominator
        while staying in Zoë's.
        """
        coordinator = shared_scenario.coordinator
        chore_id = shared_scenario.chore_ids["Take out trash"]
        zoë_id = shared_scenario.assignee_ids["Zoë"]

        await coordinator.chore_manager.approve_chore(APPROVER_NAME, zoë_id, chore_id)

        def due_count_for(assignee_name: str) -> int:
            snapshot = coordinator.statistics_manager.get_badge_scoped_today_completion(
                shared_scenario.assignee_ids[assignee_name],
                [chore_id],
                today_iso=dt_utils.dt_today_iso(),
                cycle_start_iso=dt_utils.dt_today_iso(),
                only_due_today=False,
            )
            assert snapshot["total_count"] == 1
            return snapshot["due_count"]

        assert due_count_for("Zoë") == 1
        assert due_count_for("Max!") == 0

    def test_unassigned_assignee_is_not_charged(
        self,
        shared_scenario: SetupResult,
    ) -> None:
        """A stale per-assignee entry cannot inflate the denominator (issue #205)."""
        chore_info = shared_scenario.coordinator.chores_data[
            shared_scenario.chore_ids["Family dinner cleanup"]
        ]
        max_id = shared_scenario.assignee_ids["Max!"]
        chore_info[const.DATA_CHORE_ASSIGNED_USER_IDS].remove(max_id)

        assert counts_toward(shared_scenario, "Max!", "Family dinner cleanup") is False
        assert counts_toward(shared_scenario, "Zoë", "Family dinner cleanup") is True


class TestObligationScopePrimaryStandby:
    """Standby assignees are charged only when the mode lets them act."""

    def test_primary_is_charged(
        self,
        standby_scenario: SetupResult,
    ) -> None:
        """The primary always owes the chore."""
        primary_id = turn_holder_id(standby_scenario, "Daily Chore (anytime)")

        assert (
            counts_toward(
                standby_scenario,
                name_of(standby_scenario, primary_id),
                "Daily Chore (anytime)",
            )
            is True
        )

    @pytest.mark.parametrize(
        ("chore_name", "standby_charged"),
        [
            pytest.param("Daily Chore (anytime)", True, id="anytime_can_act"),
            pytest.param(
                "Daily Chore (manual_only)", False, id="manual_only_cannot_act"
            ),
            pytest.param(
                "Weekly Chore (on_overdue)",
                False,
                id="on_overdue_not_yet_due",
            ),
        ],
    )
    def test_standby_charge_follows_claim_mode(
        self,
        standby_scenario: SetupResult,
        chore_name: str,
        standby_charged: bool,
    ) -> None:
        """A standby is charged only when its claim mode lets it act today."""
        primary_id = turn_holder_id(standby_scenario, chore_name)
        standby_name = next(
            name
            for name in STANDBY_ASSIGNEES
            if standby_scenario.assignee_ids[name] != primary_id
        )

        assert (
            counts_toward(standby_scenario, standby_name, chore_name) is standby_charged
        )

    def test_single_assignee_rotation_chore_is_charged(
        self,
        standby_scenario: SetupResult,
    ) -> None:
        """A rotation chore with one assignee has no standby to exclude."""
        assert counts_toward(standby_scenario, "Zoë", "Solo Chore (single)") is True
