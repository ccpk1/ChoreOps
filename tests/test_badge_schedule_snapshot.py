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
