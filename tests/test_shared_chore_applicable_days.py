"""Regression tests for legacy string applicable_days on shared read paths.

Issue #257 follow-up: PR #258 fixed the write boundary and the INDEPENDENT
read path, but shared chores already stored with weekday name strings
(["wed"]) still flowed raw into day-matching logic. These tests pin the
read-side coercion at every live funnel:

- calendar._get_applicable_days_for_assignee (calendar event generation)
- chore_manager.get_applicable_days_for_assignee (daily applicability)
- calculate_next_due_date_from_chore_info (schedule engine, mixed lists)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.calendar import AssigneeScheduleCalendar
from custom_components.choreops.engines.schedule_engine import (
    calculate_next_due_date_from_chore_info,
)
from custom_components.choreops.managers.chore_manager import ChoreManager
from tests.helpers import (
    DATA_CHORE_APPLICABLE_DAYS,
    DATA_CHORE_ASSIGNED_USER_IDS,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_INTERNAL_ID,
    DATA_CHORE_NAME,
    DATA_CHORE_RECURRING_FREQUENCY,
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
    SetupResult,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ASSIGNEE_ID = "assignee-1"


def _build_lightweight_calendar() -> AssigneeScheduleCalendar:
    """Create a calendar instance for unit-level funnel tests."""
    calendar = object.__new__(AssigneeScheduleCalendar)
    calendar._assignee_id = ASSIGNEE_ID
    calendar._assignee_name = "Leo"
    return calendar


def _shared_chore(days: list[Any]) -> dict[str, Any]:
    """Build a minimal SHARED chore with the given applicable days."""
    return {
        DATA_CHORE_INTERNAL_ID: "chore-1",
        DATA_CHORE_NAME: "Trash Day",
        DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
        DATA_CHORE_ASSIGNED_USER_IDS: [ASSIGNEE_ID],
        DATA_CHORE_RECURRING_FREQUENCY: FREQUENCY_WEEKLY,
        DATA_CHORE_APPLICABLE_DAYS: days,
    }


class TestSharedChoreLegacyDayCoercion:
    """Legacy string days stored on shared chores must coerce on read."""

    def test_calendar_funnel_coerces_shared_and_per_assignee_days(self) -> None:
        """Calendar funnel returns integers for names on both chore paths."""
        calendar = _build_lightweight_calendar()

        shared_chore = _shared_chore(["wed"])
        assert calendar._get_applicable_days_for_assignee(shared_chore) == [2]

        # Per-assignee path (INDEPENDENT fallback) also coerces
        independent_chore = {
            DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS: {
                ASSIGNEE_ID: ["mon", "fri"]
            },
        }
        assert calendar._get_applicable_days_for_assignee(independent_chore) == [
            0,
            4,
        ]

        # Integer storage passes through unchanged
        assert calendar._get_applicable_days_for_assignee(_shared_chore([2])) == [2]

    def test_chore_manager_funnel_coerces_legacy_days(self) -> None:
        """ChoreManager funnel returns integers for names on both paths."""
        manager = object.__new__(ChoreManager)

        assert manager.get_applicable_days_for_assignee(
            _shared_chore(["wed"]), ASSIGNEE_ID
        ) == [2]

        independent_chore = {
            DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS: {ASSIGNEE_ID: ["sat"]},
        }
        assert manager.get_applicable_days_for_assignee(
            independent_chore, ASSIGNEE_ID
        ) == [5]

    @pytest.mark.asyncio
    async def test_no_due_date_daily_matches_today_with_legacy_days(
        self,
        hass: HomeAssistant,
        mock_hass_users: dict[str, Any],
        scenario_minimal: SetupResult,
    ) -> None:
        """A shared daily chore stored with ["wed"] is applicable on Wednesday."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]

        chore_id = "legacy-days-chore"
        coordinator.chores_data[chore_id] = {
            DATA_CHORE_INTERNAL_ID: chore_id,
            DATA_CHORE_NAME: "Legacy Days Chore",
            DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
            DATA_CHORE_ASSIGNED_USER_IDS: [zoe_id],
            DATA_CHORE_RECURRING_FREQUENCY: FREQUENCY_DAILY,
            DATA_CHORE_APPLICABLE_DAYS: ["wed"],
        }

        manager = coordinator.chore_manager
        chore_info = coordinator.chores_data[chore_id]

        assert manager.no_due_date_daily_matches_today(
            chore_info, zoe_id, local_weekday=2
        )
        assert not manager.no_due_date_daily_matches_today(
            chore_info, zoe_id, local_weekday=3
        )

    def test_schedule_engine_handles_mixed_name_and_integer_days(self) -> None:
        """Mixed [0, "wed"] no longer crashes the first-element type sniff."""
        chore_info = {
            DATA_CHORE_NAME: "Mixed Days Chore",
            DATA_CHORE_RECURRING_FREQUENCY: FREQUENCY_WEEKLY,
            DATA_CHORE_APPLICABLE_DAYS: [0, "wed"],
        }
        current_due = datetime(2025, 1, 15, 12, 0, 0) + timedelta(days=7)

        next_due = calculate_next_due_date_from_chore_info(current_due, chore_info)

        assert next_due is not None
        assert isinstance(next_due, datetime)
        assert next_due.weekday() in (0, 2)


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant, mock_hass_users: dict[str, Any]
) -> SetupResult:
    """Load minimal scenario (Zoë with daily chores)."""
    return await setup_from_yaml(
        hass, mock_hass_users, "tests/scenarios/scenario_minimal.yaml"
    )
