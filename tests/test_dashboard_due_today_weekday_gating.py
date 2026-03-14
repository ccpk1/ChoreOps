"""Regression tests for no-due-date daily weekday gating."""

from __future__ import annotations

from homeassistant.util import dt as dt_util

from custom_components.choreops import const
from custom_components.choreops.managers.chore_manager import ChoreManager
from custom_components.choreops.sensor import AssigneeDashboardHelperSensor


def test_no_due_date_daily_matches_today_uses_applicable_days() -> None:
    """No-due-date daily chores only count on matching weekdays."""
    manager = object.__new__(ChoreManager)
    today_weekday = dt_util.as_local(dt_util.now()).weekday()
    other_weekday = (today_weekday + 1) % 7

    chore_info = {
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_APPLICABLE_DAYS: [today_weekday],
    }

    assert manager.no_due_date_daily_matches_today(
        chore_info,
        "assignee-1",
        local_weekday=today_weekday,
    )
    assert not manager.no_due_date_daily_matches_today(
        chore_info,
        "assignee-1",
        local_weekday=other_weekday,
    )


def test_due_today_summary_counts_matching_no_due_date_daily() -> None:
    """Due-today summary includes no-due-date daily chores only on allowed weekdays."""
    manager = object.__new__(ChoreManager)
    today_weekday = dt_util.as_local(dt_util.now()).weekday()
    manager._coordinator = type(
        "FakeCoordinator",
        (),
        {
            "chores_data": {
                "chore-1": {
                    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                    const.DATA_CHORE_APPLICABLE_DAYS: [today_weekday],
                },
                "chore-2": {
                    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                    const.DATA_CHORE_APPLICABLE_DAYS: [(today_weekday + 1) % 7],
                },
            }
        },
    )()

    status_context = {
        const.CHORE_CTX_STATE: const.CHORE_STATE_PENDING,
        const.CHORE_CTX_CLAIM_MODE: None,
        const.CHORE_CTX_IS_DUE: False,
        const.CHORE_CTX_DUE_DATE: None,
    }

    assert manager.chore_counts_toward_due_today_summary(
        "assignee-1",
        "chore-1",
        status_context=status_context,
    )
    assert not manager.chore_counts_toward_due_today_summary(
        "assignee-1",
        "chore-2",
        status_context=status_context,
    )


def test_dashboard_primary_group_only_uses_today_for_matching_daily() -> None:
    """Dashboard grouping stops forcing all date-less daily chores into today."""
    sensor = object.__new__(AssigneeDashboardHelperSensor)

    assert (
        sensor._calculate_primary_group(
            const.CHORE_STATE_PENDING,
            False,
            None,
            const.FREQUENCY_DAILY,
            True,
        )
        == const.PRIMARY_GROUP_TODAY
    )
    assert (
        sensor._calculate_primary_group(
            const.CHORE_STATE_PENDING,
            False,
            None,
            const.FREQUENCY_DAILY,
            False,
        )
        == const.PRIMARY_GROUP_OTHER
    )
