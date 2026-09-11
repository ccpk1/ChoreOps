"""Regression tests for period-end badge reset cycles (issue #283).

Period-end reset schedules (Week-End, Month-End, Quarter-End, Year-End) are
calendar aligned. Three defects are covered here:

1. The FIRST cycle end landed one period in the future, because the resolver
   added a full interval before snapping to the period end.
2. Cycles never rolled over, because the next cycle end resolved to the same
   date, so counters never reset and the stored end date stayed in the past.
3. Cumulative badge maintenance end dates had the same one-period-late problem.

Rolling frequencies (weekly, biweekly, monthly, ...) are anchored to their
start date and must keep behaving exactly as before.
"""

# pylint: disable=protected-access  # Testing internal date-resolution helpers
# pylint: disable=redefined-outer-name  # Pytest fixtures redefine names

from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.managers.gamification_manager import GamificationManager
from custom_components.choreops.utils.dt_utils import (
    dt_add_interval,
    dt_next_schedule,
    dt_today_iso,
)
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
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_BADGES,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
)
from tests.helpers.setup import SetupResult, setup_from_yaml


def _manager_shell() -> GamificationManager:
    """Build a manager instance for pure date-resolution calls."""
    return GamificationManager.__new__(GamificationManager)


def _badge_with_frequency(recurring_frequency: str) -> dict[str, Any]:
    """Build the minimal badge payload used by cycle-end resolution."""
    return {
        const.DATA_BADGE_RESET_SCHEDULE: {
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: recurring_frequency,
        }
    }


@pytest.fixture
async def setup_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the minimal scenario for badge cycle testing."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


async def _add_periodic_badge(
    hass: HomeAssistant,
    entry_id: str,
    badge_data: dict[str, Any],
) -> ConfigFlowResult:
    """Add a periodic badge through the options flow."""
    result = await hass.config_entries.options.async_init(entry_id)
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
    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=badge_data,
    )


def _get_badge_by_name(coordinator: Any, badge_name: str) -> tuple[str, dict[str, Any]]:
    """Return the badge id and data matching a display name."""
    for badge_id, badge_data in coordinator.badges_data.items():
        if badge_data.get(const.DATA_BADGE_NAME) == badge_name:
            return badge_id, badge_data
    raise ValueError(f"Badge not found: {badge_name}")


class TestPeriodEndCycleRollover:
    """The next cycle end must always advance for period-end frequencies."""

    @pytest.mark.parametrize(
        ("recurring_frequency", "current_end", "expected_end"),
        [
            pytest.param(
                const.PERIOD_WEEK_END, "2026-09-20", "2026-09-27", id="week_end"
            ),
            pytest.param(
                const.PERIOD_MONTH_END, "2026-09-30", "2026-10-31", id="month_end"
            ),
            pytest.param(
                const.PERIOD_QUARTER_END, "2026-09-30", "2026-12-31", id="quarter_end"
            ),
            pytest.param(
                const.PERIOD_YEAR_END, "2026-12-31", "2027-12-31", id="year_end"
            ),
        ],
    )
    def test_period_end_cycle_advances(
        self,
        recurring_frequency: str,
        current_end: str,
        expected_end: str,
    ) -> None:
        """Each period-end frequency advances to the following period end."""
        result = GamificationManager._get_next_non_cumulative_cycle_end(
            _manager_shell(),
            _badge_with_frequency(recurring_frequency),
            current_end,
        )

        assert result == expected_end, (
            "Period-end rollover must move to the next period, "
            f"got {result} for {recurring_frequency}"
        )
        assert result > current_end

    @pytest.mark.parametrize(
        ("recurring_frequency", "current_end", "expected_end"),
        [
            pytest.param(
                const.FREQUENCY_WEEKLY, "2026-09-14", "2026-09-21", id="weekly"
            ),
            pytest.param(
                const.FREQUENCY_BIWEEKLY, "2026-09-14", "2026-09-28", id="biweekly"
            ),
            pytest.param(
                const.FREQUENCY_MONTHLY, "2026-09-30", "2026-10-30", id="monthly"
            ),
        ],
    )
    def test_rolling_frequency_cycle_unchanged(
        self,
        recurring_frequency: str,
        current_end: str,
        expected_end: str,
    ) -> None:
        """Rolling frequencies keep their existing interval-based behavior."""
        result = GamificationManager._get_next_non_cumulative_cycle_end(
            _manager_shell(),
            _badge_with_frequency(recurring_frequency),
            current_end,
        )

        assert result == expected_end


class TestInitialPeriodEndResolution:
    """The first cycle end must be the upcoming period end, not the next one."""

    @pytest.mark.parametrize(
        ("recurring_frequency", "expected_end"),
        [
            pytest.param(const.PERIOD_WEEK_END, "2026-09-13", id="week_end"),
            pytest.param(const.PERIOD_MONTH_END, "2026-09-30", id="month_end"),
            pytest.param(const.PERIOD_QUARTER_END, "2026-09-30", id="quarter_end"),
            pytest.param(const.PERIOD_YEAR_END, "2026-12-31", id="year_end"),
        ],
    )
    def test_initial_period_end_is_upcoming(
        self,
        recurring_frequency: str,
        expected_end: str,
    ) -> None:
        """A period-end cycle created mid-period ends at the upcoming period end."""
        result = GamificationManager._resolve_period_end_cycle_end(
            recurring_frequency, "2026-09-11"
        )

        assert result == expected_end

    @pytest.mark.parametrize(
        "recurring_frequency",
        [
            pytest.param(const.PERIOD_WEEK_END, id="week_end"),
            pytest.param(const.PERIOD_MONTH_END, id="month_end"),
            pytest.param(const.PERIOD_QUARTER_END, id="quarter_end"),
            pytest.param(const.PERIOD_YEAR_END, id="year_end"),
        ],
    )
    def test_initial_period_end_precedes_full_interval_advance(
        self,
        recurring_frequency: str,
    ) -> None:
        """Regression guard: the old resolver skipped a whole period ahead."""
        reference = "2026-09-11"
        resolved = GamificationManager._resolve_period_end_cycle_end(
            recurring_frequency, reference
        )
        inflated = dt_next_schedule(
            reference,
            interval_type=recurring_frequency,
            require_future=True,
            reference_datetime=reference,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )

        assert resolved is not None
        assert str(resolved) < str(inflated)


class TestCumulativeMaintenanceDates:
    """Cumulative maintenance windows use the upcoming period end."""

    @pytest.mark.parametrize(
        "recurring_frequency",
        [
            pytest.param(const.PERIOD_WEEK_END, id="week_end"),
            pytest.param(const.PERIOD_MONTH_END, id="month_end"),
            pytest.param(const.PERIOD_QUARTER_END, id="quarter_end"),
            pytest.param(const.PERIOD_YEAR_END, id="year_end"),
        ],
    )
    def test_maintenance_end_date_is_upcoming_period_end(
        self,
        recurring_frequency: str,
    ) -> None:
        """Maintenance end date matches the upcoming period end."""
        today_iso = dt_today_iso()
        end_date, grace_end_date = GamificationManager._calculate_maintenance_dates(
            _manager_shell(),
            {
                const.DATA_BADGE_RESET_SCHEDULE: {
                    const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: (
                        recurring_frequency
                    ),
                    const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: 0,
                }
            },
        )

        assert end_date == GamificationManager._resolve_period_end_cycle_end(
            recurring_frequency, today_iso
        )
        assert grace_end_date == end_date


class TestPeriodEndBadgeCreation:
    """A period-end badge created through the UI gets an upcoming cycle end."""

    async def test_week_end_badge_starts_with_upcoming_sunday(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Creating a Week-End badge must not schedule the cycle a week late."""
        coordinator = setup_minimal.coordinator
        assignee_id = next(iter(coordinator.assignees_data))

        await _add_periodic_badge(
            hass,
            setup_minimal.config_entry.entry_id,
            {
                CFOF_BADGES_INPUT_NAME: "Week End Cycle Guard",
                CFOF_BADGES_INPUT_ICON: "mdi:calendar-weekend",
                CFOF_BADGES_INPUT_TARGET_TYPE: "points",
                CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 999,
                CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
                CFOF_BADGES_INPUT_SELECTED_CHORES: [],
                CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
                CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY: (
                    const.PERIOD_WEEK_END
                ),
            },
        )

        _, badge_info = _get_badge_by_name(coordinator, "Week End Cycle Guard")
        schedule = badge_info[const.DATA_BADGE_RESET_SCHEDULE]
        end_date = schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE]
        today_iso = dt_today_iso()

        assert end_date == GamificationManager._resolve_period_end_cycle_end(
            const.PERIOD_WEEK_END, today_iso
        ), "Week-End badge should end on the upcoming Sunday"

    async def test_week_end_badge_rollover_resets_progress(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """A Week-End badge with an expired cycle rolls forward and resets."""
        coordinator = setup_minimal.coordinator
        assignee_id = next(iter(coordinator.assignees_data))
        today_iso = dt_today_iso()

        await _add_periodic_badge(
            hass,
            setup_minimal.config_entry.entry_id,
            {
                CFOF_BADGES_INPUT_NAME: "Week End Rollover Guard",
                CFOF_BADGES_INPUT_ICON: "mdi:calendar-refresh",
                CFOF_BADGES_INPUT_TARGET_TYPE: "points",
                CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 999,
                CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
                CFOF_BADGES_INPUT_SELECTED_CHORES: [],
                CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
                CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY: (
                    const.PERIOD_WEEK_END
                ),
            },
        )

        badge_id, badge_info = _get_badge_by_name(
            coordinator, "Week End Rollover Guard"
        )
        schedule = badge_info[const.DATA_BADGE_RESET_SCHEDULE]
        stale_end = dt_add_interval(
            today_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-7,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )
        schedule[const.DATA_BADGE_RESET_SCHEDULE_START_DATE] = stale_end
        schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE] = stale_end

        progress = coordinator.assignees_data[assignee_id][
            const.DATA_USER_BADGE_PROGRESS
        ][badge_id]
        progress[const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT] = 42.0

        changed = coordinator.gamification_manager._advance_non_cumulative_badge_cycle_if_needed(
            assignee_id,
            badge_id,
            badge_info,
            today_iso=today_iso,
        )

        assert changed is True, "Expired Week-End cycle must roll forward"
        assert schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE] >= today_iso
        assert progress[const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT] == 0.0
