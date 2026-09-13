"""Test cycle-scoped strict mode for "(No Overdue)" badges (issue #293).

Covers the cycle-scoped lateness read used by no-overdue badge variants:

- Lateness anywhere in the cycle fails the badge, even once resolved
- A missed chore fails the badge
- Lateness before the cycle start does not leak into the current cycle
- Cycle start resolution never fabricates a window from a missing anchor

Uses scenario_minimal.yaml.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.managers.gamification_manager import GamificationManager
from custom_components.choreops.utils import dt_utils
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


CYCLE_START_OFFSET_DAYS = 4
"""Cycle start is 4 days before today, giving room on both sides."""


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def badge_cycle_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for badge cycle tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# ============================================================================
# HELPERS
# ============================================================================


def date_offset(days: int) -> str:
    """Return a local date key offset from today."""
    return (dt_utils.dt_today_local() + timedelta(days=days)).isoformat()


def seed_lateness(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
    *,
    overdue_offset_days: int | None = None,
    missed_offset_days: int | None = None,
) -> None:
    """Write lateness history onto an assignee's chore entry."""
    entry = coordinator.chore_manager._get_assignee_chore_data(assignee_id, chore_id)

    if overdue_offset_days is not None:
        entry[const.DATA_USER_CHORE_DATA_LAST_OVERDUE] = (
            f"{date_offset(overdue_offset_days)}T12:00:00+00:00"
        )
    if missed_offset_days is not None:
        entry[const.DATA_USER_CHORE_DATA_LAST_MISSED] = (
            f"{date_offset(missed_offset_days)}T12:00:00+00:00"
        )


def read_cycle_completion(
    coordinator: Any,
    assignee_id: str,
    chore_id: str,
    *,
    cycle_start_iso: str,
) -> dict[str, Any]:
    """Read the badge-scoped completion snapshot for a single chore."""
    return coordinator.statistics_manager.get_badge_scoped_today_completion(
        assignee_id,
        [chore_id],
        today_iso=dt_utils.dt_today_iso(),
        cycle_start_iso=cycle_start_iso,
        only_due_today=False,
    )


# ============================================================================
# TEST: cycle-scoped lateness
# ============================================================================


class TestCycleScopedLateness:
    """Tests for `cycle_failed` derivation."""

    @pytest.mark.parametrize(
        ("overdue_offset_days", "missed_offset_days", "expected_failed"),
        [
            pytest.param(0, None, True, id="overdue_today"),
            pytest.param(-1, None, True, id="overdue_earlier_in_cycle"),
            pytest.param(-10, None, False, id="overdue_before_cycle_start"),
            pytest.param(None, 0, True, id="missed_today"),
            pytest.param(None, -10, False, id="missed_before_cycle_start"),
            pytest.param(None, None, False, id="no_history"),
        ],
    )
    def test_cycle_failure_derived_from_lateness_history(
        self,
        badge_cycle_scenario: SetupResult,
        overdue_offset_days: int | None,
        missed_offset_days: int | None,
        expected_failed: bool,
    ) -> None:
        """Lateness on or after the cycle start fails the cycle."""
        coordinator = badge_cycle_scenario.coordinator
        assignee_id = badge_cycle_scenario.assignee_ids["Zoë"]
        chore_id = next(iter(badge_cycle_scenario.chore_ids.values()))

        seed_lateness(
            coordinator,
            assignee_id,
            chore_id,
            overdue_offset_days=overdue_offset_days,
            missed_offset_days=missed_offset_days,
        )

        result = read_cycle_completion(
            coordinator,
            assignee_id,
            chore_id,
            cycle_start_iso=date_offset(-CYCLE_START_OFFSET_DAYS),
        )

        assert result["cycle_failed"] is expected_failed

    def test_resolved_overdue_still_fails_cycle(
        self,
        badge_cycle_scenario: SetupResult,
    ) -> None:
        """A chore that was overdue earlier in the cycle keeps failing it.

        The chore is currently pending (resolved), so the live-state check alone
        would report no problem. This is the issue #293 defect.
        """
        coordinator = badge_cycle_scenario.coordinator
        assignee_id = badge_cycle_scenario.assignee_ids["Zoë"]
        chore_id = next(iter(badge_cycle_scenario.chore_ids.values()))

        seed_lateness(coordinator, assignee_id, chore_id, overdue_offset_days=-1)
        entry = coordinator.chore_manager._get_assignee_chore_data(
            assignee_id, chore_id
        )
        entry[const.DATA_USER_CHORE_DATA_STATE] = const.CHORE_STATE_PENDING

        result = read_cycle_completion(
            coordinator,
            assignee_id,
            chore_id,
            cycle_start_iso=date_offset(-CYCLE_START_OFFSET_DAYS),
        )

        assert result["has_overdue"] is False
        assert result["cycle_failed"] is True

    def test_single_day_cycle_ignores_yesterday(
        self,
        badge_cycle_scenario: SetupResult,
    ) -> None:
        """A daily badge only sees today's lateness."""
        coordinator = badge_cycle_scenario.coordinator
        assignee_id = badge_cycle_scenario.assignee_ids["Zoë"]
        chore_id = next(iter(badge_cycle_scenario.chore_ids.values()))

        seed_lateness(coordinator, assignee_id, chore_id, overdue_offset_days=-1)

        result = read_cycle_completion(
            coordinator,
            assignee_id,
            chore_id,
            cycle_start_iso=dt_utils.dt_today_iso(),
        )

        assert result["cycle_failed"] is False


# ============================================================================
# TEST: cycle start resolution
# ============================================================================


class TestResolveBadgeCycleStart:
    """Tests for `_resolve_badge_cycle_start`."""

    def test_explicit_start_date_wins(self) -> None:
        """A configured start date anchors the cycle."""
        resolved = GamificationManager._resolve_badge_cycle_start(
            {const.DATA_BADGE_RESET_SCHEDULE_START_DATE: "2026-09-01"},
            "2026-09-13",
        )

        assert resolved == "2026-09-01"

    @pytest.mark.parametrize(
        "start_date",
        [
            pytest.param(None, id="null_start_date"),
            pytest.param("", id="empty_start_date"),
        ],
    )
    def test_missing_start_date_falls_back_to_today(
        self,
        start_date: str | None,
    ) -> None:
        """An unset anchor must not fabricate earlier-in-cycle failures."""
        resolved = GamificationManager._resolve_badge_cycle_start(
            {const.DATA_BADGE_RESET_SCHEDULE_START_DATE: start_date},
            "2026-09-13",
        )

        assert resolved == "2026-09-13"
