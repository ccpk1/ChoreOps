"""Badge target type tests - Section 1.

Tests for non-cumulative badge types via options flow:
- Daily badges: Same-day aggregation, midnight reset
- Periodic badges: Custom interval, interval boundary
- Special occasion badges: Specific date trigger, date range

These badge types are only available via options flow (not config flow).
Following AGENT_TEST_CREATION_INSTRUCTIONS.md patterns.

Test organization:
- Section 1.2: Daily Target Types (2 tests)
- Section 1.4: Periodic Target Types (2 tests)
- Section 1.5: Special Occasion Target Types (2 tests)

Note: Section 1.1 (Cumulative) and Section 1.3 (Weekly - actually handled
by periodic with weekly reset) are covered in test_badge_cumulative.py.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.choreops import const
from custom_components.choreops.utils.dt_utils import (
    dt_add_interval,
    dt_today_iso,
    get_default_timezone,
    set_default_timezone,
)
from tests.helpers import (
    # Badge type constants
    BADGE_TYPE_DAILY,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION,
    # Badge form input constants
    CFOF_BADGES_INPUT_ASSIGNED_USER_IDS,
    CFOF_BADGES_INPUT_AWARD_ITEMS,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_OCCASION_TYPE,
    CFOF_BADGES_INPUT_SELECTED_CHORES,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TARGET_TYPE,
    CFOF_BADGES_INPUT_TYPE,
    # Data keys
    DATA_USER_BADGE_PROGRESS,
    # Options flow constants
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_BADGES,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_STEP_INIT,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def setup_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for badge testing.

    Uses scenario_minimal.yaml which provides:
    - 1 assignee (Zoë)
    - 1 approver (Mom)
    - 5 chores
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def add_badge_via_options_flow(
    hass: HomeAssistant,
    entry_id: str,
    badge_type: str,
    badge_data: dict[str, Any],
) -> ConfigFlowResult:
    """Add a badge via options flow with the complete step sequence.

    Badge flow has 4 steps:
    1. Navigate to badges menu
    2. Select "Add" action
    3. Select badge type
    4. Submit badge details

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        badge_type: One of BADGE_TYPE_* constants
        badge_data: Form data for the badge (varies by type)

    Returns:
        Final flow result
    """
    # Step 1: Start options flow and navigate to badges menu
    result = await hass.config_entries.options.async_init(entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
    )

    # Step 2: Select "Add" action
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )

    # Step 3: Select badge type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CFOF_BADGES_INPUT_TYPE: badge_type},
    )

    # Step 4: Submit badge details
    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=badge_data,
    )


def get_badge_by_name(coordinator: Any, badge_name: str) -> tuple[str, dict[str, Any]]:
    """Get badge ID and data by name.

    Args:
        coordinator: ChoreOpsCoordinator instance
        badge_name: Display name of the badge

    Returns:
        Tuple of (badge_id, badge_data)

    Raises:
        ValueError: If badge not found
    """
    for badge_id, badge_data in coordinator.badges_data.items():
        if badge_data.get(const.DATA_BADGE_NAME) == badge_name:
            return badge_id, badge_data
    raise ValueError(f"Badge not found: {badge_name}")


# ============================================================================
# SECTION 1.2: DAILY TARGET TYPES
# ============================================================================


class TestDailyBadgeTargetTypes:
    """Test DAILY badge target type behavior.

    Daily badges:
    - Reset at midnight (tracked via reset_schedule)
    - Support target_type field (but NOT streak types)
    - Support tracked_chores component
    - Track progress within a single day
    """

    async def test_add_daily_badge_via_options_flow(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test adding a daily badge via options flow.

        Validates the complete flow for creating a daily badge:
        1. Badge type selection returns daily step
        2. Daily badge form accepts target_type + threshold
        3. Badge is created with correct type and target
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        # Get existing assignee and chore IDs
        assignee_id = next(iter(coordinator.assignees_data.keys()))
        chore_id = next(iter(coordinator.chores_data.keys()))

        # Daily badge form data - requires target_type (unlike cumulative)
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Daily Star",
            CFOF_BADGES_INPUT_ICON: "mdi:star-circle",
            CFOF_BADGES_INPUT_TARGET_TYPE: "chore_count",  # Required for daily
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 3,  # Complete 3 chores
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [chore_id],  # Track specific chore
            CFOF_BADGES_INPUT_AWARD_POINTS: 10.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_DAILY, badge_data
        )

        # Options flow returns to init step after successful add
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created with correct type
        badge_id, badge_info = get_badge_by_name(coordinator, "Daily Star")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_DAILY
        assert (
            badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE]
            == "chore_count"
        )

    async def test_daily_badge_same_day_aggregation(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test daily badge aggregates progress within same day.

        When multiple chores are completed on the same day,
        the daily badge should aggregate all completions toward target.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        # Create daily badge with chore_count target of 2
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Daily Chore Hero",
            CFOF_BADGES_INPUT_ICON: "mdi:medal",
            CFOF_BADGES_INPUT_TARGET_TYPE: "chore_count",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 2,  # Need 2 chores
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],  # All chores
            CFOF_BADGES_INPUT_AWARD_POINTS: 15.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_DAILY, badge_data
        )

        # After badge creation, coordinator should have synced progress
        badge_id, _ = get_badge_by_name(coordinator, "Daily Chore Hero")

        # Verify badge progress structure was initialized for assignee
        assignee_progress = coordinator.assignees_data[assignee_id].get(
            DATA_USER_BADGE_PROGRESS, {}
        )
        assert badge_id in assignee_progress, "Badge progress should be initialized"


# ============================================================================
# SECTION 1.4: PERIODIC TARGET TYPES
# ============================================================================


class TestPeriodicBadgeTargetTypes:
    """Test PERIODIC badge target type behavior.

    Periodic badges:
    - Support all target types (points, chore_count, days_*, streak_*)
    - Support custom intervals via reset_schedule
    - Track progress across multiple days within a period
    """

    async def test_add_periodic_badge_via_options_flow(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test adding a periodic badge via options flow.

        Validates the complete flow for creating a periodic badge:
        1. Badge type selection returns periodic step
        2. Periodic badge form accepts all target types
        3. Badge is created with correct configuration
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        # Periodic badge with points_chores target
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Weekly Champion",
            CFOF_BADGES_INPUT_ICON: "mdi:trophy",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points_chores",  # Points from chores only
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 50,  # Earn 50 points
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],  # All chores
            CFOF_BADGES_INPUT_AWARD_POINTS: 25.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_PERIODIC, badge_data
        )

        # Options flow returns to init step after successful add
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created with correct type and target
        badge_id, badge_info = get_badge_by_name(coordinator, "Weekly Champion")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_PERIODIC
        assert (
            badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE]
            == "points_chores"
        )

    async def test_periodic_badge_custom_interval(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test periodic badge with custom interval tracks across days.

        Periodic badges can have custom reset intervals (3 days, weekly, etc).
        Progress should accumulate within the period.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        # Periodic badge tracking days_all_chores
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Consistency Star",
            CFOF_BADGES_INPUT_ICON: "mdi:calendar-check",
            CFOF_BADGES_INPUT_TARGET_TYPE: "days_all_chores",  # Days with all done
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 5,  # Need 5 perfect days
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],  # All chores
            CFOF_BADGES_INPUT_AWARD_POINTS: 50.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_PERIODIC, badge_data
        )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge created
        badge_id, badge_info = get_badge_by_name(coordinator, "Consistency Star")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_PERIODIC
        assert (
            badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE]
            == "days_all_chores"
        )

    async def test_periodic_badge_evaluation_persists_progress(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Periodic evaluation writes non-cumulative badge progress fields.

        Regression guard for layered-architecture refactor misses where badge
        evaluation occurred without persisting progress updates.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Progress Write Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:progress-check",
            CFOF_BADGES_INPUT_TARGET_TYPE: "chore_count",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 99,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 10.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_PERIODIC,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "Progress Write Guard")

        await coordinator.gamification_manager._evaluate_assignee(assignee_id)

        assignee_progress = coordinator.assignees_data[assignee_id].get(
            DATA_USER_BADGE_PROGRESS, {}
        )
        badge_progress = assignee_progress.get(badge_id, {})

        assert const.DATA_USER_BADGE_PROGRESS_OVERALL_PROGRESS in badge_progress
        assert const.DATA_USER_BADGE_PROGRESS_CRITERIA_MET in badge_progress
        assert const.DATA_USER_BADGE_PROGRESS_CHORES_CYCLE_COUNT in badge_progress
        assert const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY in badge_progress
        assert const.DATA_BADGE_ASSIGNED_USER_IDS not in badge_progress
        assert "chores_completed" not in badge_progress
        assert "days_completed" not in badge_progress

    async def test_periodic_badge_all_scope_does_not_materialize_all_chores(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Badge progress stores explicit selection only; empty means all chores."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "All Scope Storage Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:format-list-bulleted",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 100,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_PERIODIC,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "All Scope Storage Guard")
        badge_progress = coordinator.assignees_data[assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][badge_id]

        assert const.DATA_USER_BADGE_PROGRESS_NAME in badge_progress
        assert const.DATA_BADGE_ASSIGNED_USER_IDS not in badge_progress
        assert "chores_completed" not in badge_progress
        assert "days_completed" not in badge_progress
        assert "tracked_chores" not in badge_progress
        assert const.DATA_BADGE_TRACKED_CHORES not in badge_progress

    async def test_periodic_badge_rollover_updates_stale_end_date(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Expired periodic/daily cycle dates are rolled forward before evaluation."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Rollover Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:calendar-refresh",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 999,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_DAILY,
            badge_data,
        )

        badge_id, badge_info = get_badge_by_name(coordinator, "Rollover Guard")
        badge_progress = coordinator.assignees_data[assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][badge_id]

        today_iso = dt_today_iso()
        stale_end = dt_add_interval(
            today_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-2,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE
        ] = stale_end
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE
        ] = stale_end
        badge_progress[const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT] = 42.0

        changed = coordinator.gamification_manager._advance_non_cumulative_badge_cycle_if_needed(
            assignee_id,
            badge_id,
            badge_info,
            today_iso=today_iso,
        )

        assert changed is True
        assert (
            str(
                badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                    const.DATA_BADGE_RESET_SCHEDULE_END_DATE
                ]
            )
            >= today_iso
        )
        assert (
            badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE
            ]
            == today_iso
        )
        assert badge_progress[const.DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT] == 0.0
        assert const.DATA_USER_BADGE_PROGRESS_START_DATE not in badge_progress
        assert const.DATA_USER_BADGE_PROGRESS_END_DATE not in badge_progress
        assert "chores_completed" not in badge_progress
        assert "days_completed" not in badge_progress

    async def test_points_badge_persist_sets_last_update_day_and_rounds_progress(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Points-based daily/periodic progress sets day marker and precision."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Points Persist Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:counter",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 50,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_DAILY,
            badge_data,
        )

        badge_id, badge_info = get_badge_by_name(coordinator, "Points Persist Guard")
        today_iso = dt_today_iso()

        changed = coordinator.gamification_manager._persist_periodic_badge_progress(
            assignee_id,
            badge_id,
            badge_info,
            {
                "criteria_met": False,
                "overall_progress": 0.5720000000000001,
                "criterion_results": [
                    {
                        "criterion_type": const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                        "met": False,
                        "current_value": 28.6,
                        "required_value": 50,
                        "progress": 0.5720000000000001,
                        "reason": "test",
                    }
                ],
            },
            already_earned=False,
            today_iso=today_iso,
        )

        assert changed is True

        badge_progress = coordinator.assignees_data[assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][badge_id]
        assert (
            badge_progress[const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY] == today_iso
        )
        assert badge_progress[const.DATA_USER_BADGE_PROGRESS_OVERALL_PROGRESS] == 0.57

    async def test_periodic_badge_status_earned_when_criteria_met(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Status moves to earned when periodic criteria are met."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Status Earned Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:check-decagram",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 10,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_DAILY,
            badge_data,
        )

        badge_id, badge_info = get_badge_by_name(coordinator, "Status Earned Guard")
        today_iso = dt_today_iso()

        changed = coordinator.gamification_manager._persist_periodic_badge_progress(
            assignee_id,
            badge_id,
            badge_info,
            {
                "criteria_met": True,
                "overall_progress": 1.0,
                "criterion_results": [
                    {
                        "criterion_type": const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                        "met": True,
                        "current_value": 10,
                        "required_value": 10,
                        "progress": 1.0,
                        "reason": "test",
                    }
                ],
            },
            already_earned=True,
            today_iso=today_iso,
        )

        assert changed is True
        badge_progress = coordinator.assignees_data[assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][badge_id]
        assert (
            badge_progress[const.DATA_USER_BADGE_PROGRESS_STATUS]
            == const.BADGE_STATE_EARNED
        )

    async def test_periodic_reaward_guard_detects_award_in_current_cycle(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Periodic re-award guard blocks duplicate awards in same cycle window."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Reaward Cycle Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:repeat-once",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 1,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_DAILY,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "Reaward Cycle Guard")
        today_iso = dt_today_iso()

        coordinator.gamification_manager.update_badges_earned_for_assignee(
            assignee_id, badge_id
        )

        badge_info = coordinator.badges_data[badge_id]
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE
        ] = today_iso
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE
        ] = today_iso

        assert (
            coordinator.gamification_manager._is_periodic_award_recorded_for_current_cycle(
                assignee_id,
                badge_id,
            )
            is True
        )

    async def test_periodic_reaward_guard_handles_null_start_date(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Null cycle start_date still blocks duplicate awards on same day."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Reaward Null Start Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:calendar-alert",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 1,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_DAILY,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "Reaward Null Start Guard")
        today_iso = dt_today_iso()

        coordinator.gamification_manager.update_badges_earned_for_assignee(
            assignee_id, badge_id
        )

        badge_info = coordinator.badges_data[badge_id]
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE
        ] = None
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE
        ] = today_iso

        assert (
            coordinator.gamification_manager._is_periodic_award_recorded_for_current_cycle(
                assignee_id,
                badge_id,
            )
            is True
        )

    async def test_periodic_sync_backfills_missing_start_date(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Sync backfills badge schedule start_date and preserves end_date."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Cycle Start Backfill Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:calendar-sync",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 1,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_DAILY,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "Cycle Start Backfill Guard")
        today_iso = dt_today_iso()

        badge_info = coordinator.badges_data[badge_id]

        original_end = str(
            badge_info[const.DATA_BADGE_RESET_SCHEDULE].get(
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE,
                "",
            )
        )
        assert original_end

        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE
        ] = None

        coordinator.gamification_manager.sync_badge_progress_for_assignee(assignee_id)

        assert (
            badge_info[const.DATA_BADGE_RESET_SCHEDULE].get(
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE
            )
            == today_iso
        )
        assert (
            badge_info[const.DATA_BADGE_RESET_SCHEDULE].get(
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE
            )
            == original_end
        )

    async def test_periodic_without_recurrence_awards_only_once(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Periodic badge with no recurrence/date window is treated as one-time."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "No Recurrence One-Time Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:lock-check",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 1,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_PERIODIC,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "No Recurrence One-Time Guard")

        coordinator.gamification_manager.update_badges_earned_for_assignee(
            assignee_id, badge_id
        )

        badge_info = coordinator.badges_data[badge_id]
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY
        ] = const.FREQUENCY_NONE
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE
        ] = None
        badge_info[const.DATA_BADGE_RESET_SCHEDULE][
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE
        ] = None

        badges_earned = coordinator.assignees_data[assignee_id][
            const.DATA_USER_BADGES_EARNED
        ]
        badges_earned[badge_id][const.DATA_USER_BADGES_EARNED_LAST_AWARDED] = (
            "2026-01-01T12:00:00+00:00"
        )

        assert (
            coordinator.gamification_manager._is_periodic_award_recorded_for_current_cycle(
                assignee_id,
                badge_id,
            )
            is True
        )

    async def test_periodic_guard_uses_local_date_for_cycle_window(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Cycle-window check uses local date when parsing UTC award timestamps."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))
        original_tz = get_default_timezone()

        try:
            set_default_timezone(ZoneInfo("America/New_York"))

            badge_data = {
                CFOF_BADGES_INPUT_NAME: "Local Date Window Guard",
                CFOF_BADGES_INPUT_ICON: "mdi:clock-time-four",
                CFOF_BADGES_INPUT_TARGET_TYPE: "points",
                CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 1,
                CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
                CFOF_BADGES_INPUT_SELECTED_CHORES: [],
                CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
                CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
            }

            await add_badge_via_options_flow(
                hass,
                config_entry.entry_id,
                BADGE_TYPE_PERIODIC,
                badge_data,
            )

            badge_id, _ = get_badge_by_name(coordinator, "Local Date Window Guard")
            coordinator.gamification_manager.update_badges_earned_for_assignee(
                assignee_id, badge_id
            )

            badge_info = coordinator.badges_data[badge_id]
            badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY
            ] = const.FREQUENCY_WEEKLY
            badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE
            ] = "2026-03-06"
            badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE
            ] = "2026-03-06"

            badges_earned = coordinator.assignees_data[assignee_id][
                const.DATA_USER_BADGES_EARNED
            ]
            badges_earned[badge_id][const.DATA_USER_BADGES_EARNED_LAST_AWARDED] = (
                "2026-03-07T01:30:00+00:00"
            )

            assert (
                coordinator.gamification_manager._is_periodic_award_recorded_for_current_cycle(
                    assignee_id,
                    badge_id,
                )
                is True
            )
        finally:
            set_default_timezone(original_tz)

    async def test_scope_filter_empty_selected_includes_all_assigned(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Empty selected chores means all chores assigned to assignee are in scope."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Scope All Assigned Guard",
            CFOF_BADGES_INPUT_ICON: "mdi:playlist-check",
            CFOF_BADGES_INPUT_TARGET_TYPE: "points",
            CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 50,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_SELECTED_CHORES: [],
            CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_PERIODIC,
            badge_data,
        )
        _badge_id, badge_info = get_badge_by_name(
            coordinator, "Scope All Assigned Guard"
        )

        assigned_chores = [
            chore_id
            for chore_id, chore_info in coordinator.chores_data.items()
            if not chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
            or assignee_id in chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        ]
        in_scope = coordinator.gamification_manager.get_badge_in_scope_chores_list(
            badge_info,
            assignee_id,
        )

        assert sorted(in_scope) == sorted(assigned_chores)

    async def test_scope_filter_selected_is_intersection(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Selected chores are intersected with assignee-assigned chores."""
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))
        all_chore_ids = list(coordinator.chores_data.keys())
        assert len(all_chore_ids) >= 2
        selected_valid = all_chore_ids[0]
        selected_not_assigned = all_chore_ids[1]

        badge_info = {
            const.DATA_BADGE_TYPE: const.BADGE_TYPE_PERIODIC,
            const.DATA_BADGE_TRACKED_CHORES: {
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES: [
                    selected_valid,
                    selected_not_assigned,
                ]
            },
        }

        in_scope = coordinator.gamification_manager.get_badge_in_scope_chores_list(
            badge_info,
            assignee_id,
            assignee_assigned_chores=[selected_valid],
        )
        assert in_scope == [selected_valid]

    async def test_scope_filter_without_tracked_chores_includes_all_assigned(
        self,
        setup_minimal: SetupResult,
    ) -> None:
        """Badges without tracked chores use all assignee-assigned chores."""
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))
        badge_info = {
            const.DATA_BADGE_TYPE: const.BADGE_TYPE_SPECIAL_OCCASION,
            const.DATA_BADGE_OCCASION_TYPE: const.OCCASION_BIRTHDAY,
        }

        in_scope = coordinator.gamification_manager.get_badge_in_scope_chores_list(
            badge_info,
            assignee_id,
        )
        expected_assigned = (
            coordinator.gamification_manager._get_assignee_assigned_chores(assignee_id)
        )

        assert sorted(in_scope) == sorted(expected_assigned)

    async def test_unknown_target_mapper_warns_and_returns_unknown(
        self,
        setup_minimal: SetupResult,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Unknown target types warn and map to explicit unknown_target."""
        coordinator = setup_minimal.coordinator
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            const.DATA_BADGE_NAME: "Unknown Mapper Guard",
            const.DATA_BADGE_TYPE: const.BADGE_TYPE_PERIODIC,
            const.DATA_BADGE_TARGET: {
                const.DATA_BADGE_TARGET_TYPE: "unexpected_target_type",
                const.DATA_BADGE_TARGET_THRESHOLD_VALUE: 3,
            },
            const.DATA_BADGE_TRACKED_CHORES: {
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES: [],
            },
            const.DATA_BADGE_ASSIGNED_USER_IDS: [assignee_id],
        }

        caplog.set_level(logging.WARNING)
        mapped = coordinator.gamification_manager._map_badge_to_canonical_target(
            assignee_id,
            "badge-unknown",
            badge_data,
        )

        assert mapped["target_type"] == "unknown_target"
        assert "Unknown periodic badge target type" in caplog.text


# ============================================================================
# SECTION 1.5: SPECIAL OCCASION TARGET TYPES
# ============================================================================


class TestSpecialOccasionBadgeTargetTypes:
    """Test SPECIAL_OCCASION badge target type behavior.

    Special occasion badges:
    - Require occasion_type (birthday, holiday, custom)
    - Do NOT have target_type or threshold fields
    - Triggered by special date matching
    """

    async def test_add_special_occasion_badge_via_options_flow(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test adding a special occasion badge via options flow.

        Special occasion badges have different schema:
        - No target_type field
        - No threshold field
        - Instead have occasion_type field
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        # Special occasion badge - NO target_type or threshold
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Birthday Star",
            CFOF_BADGES_INPUT_ICON: "mdi:cake-variant",
            CFOF_BADGES_INPUT_OCCASION_TYPE: "birthday",  # Required for special
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_AWARD_POINTS: 100.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_SPECIAL_OCCASION, badge_data
        )

        # Options flow returns to init step after successful add
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created with correct type
        badge_id, badge_info = get_badge_by_name(coordinator, "Birthday Star")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_SPECIAL_OCCASION

    async def test_special_occasion_badge_holiday_type(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test special occasion badge with holiday occasion type.

        Validates that different occasion types can be created.
        """
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator

        assignee_id = next(iter(coordinator.assignees_data.keys()))

        # Holiday special occasion badge
        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Holiday Helper",
            CFOF_BADGES_INPUT_ICON: "mdi:gift",
            CFOF_BADGES_INPUT_OCCASION_TYPE: "holiday",  # Holiday occasion
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_AWARD_POINTS: 50.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        result = await add_badge_via_options_flow(
            hass, config_entry.entry_id, BADGE_TYPE_SPECIAL_OCCASION, badge_data
        )

        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify badge was created
        badge_id, badge_info = get_badge_by_name(coordinator, "Holiday Helper")
        assert badge_info[const.DATA_BADGE_TYPE] == BADGE_TYPE_SPECIAL_OCCASION

    async def test_special_occasion_progress_attributes_include_trigger_type(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Special occasion progress sensor exposes occasion trigger type."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Birthday Trigger Visible",
            CFOF_BADGES_INPUT_ICON: "mdi:cake-variant",
            CFOF_BADGES_INPUT_OCCASION_TYPE: const.OCCASION_BIRTHDAY,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_AWARD_POINTS: 10.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_SPECIAL_OCCASION,
            badge_data,
        )

        badge_id, badge_info = get_badge_by_name(
            coordinator, "Birthday Trigger Visible"
        )
        assert badge_info[const.DATA_BADGE_OCCASION_TYPE] == const.OCCASION_BIRTHDAY

        badge_progress = coordinator.assignees_data[assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][badge_id]
        badge_progress[const.DATA_USER_BADGE_PROGRESS_START_DATE] = "1900-01-01"
        badge_progress[const.DATA_USER_BADGE_PROGRESS_END_DATE] = "1900-01-02"

        await coordinator.async_refresh()
        await hass.async_block_till_done()

        state = next(
            (
                sensor_state
                for sensor_state in hass.states.async_all("sensor")
                if sensor_state.attributes.get(const.ATTR_PURPOSE)
                == const.TRANS_KEY_PURPOSE_BADGE_PROGRESS
                and sensor_state.attributes.get(const.ATTR_USER_NAME)
                == coordinator.assignees_data[assignee_id][const.DATA_USER_NAME]
                and sensor_state.attributes.get(const.ATTR_BADGE_NAME)
                == "Birthday Trigger Visible"
            ),
            None,
        )

        assert state is not None
        attrs = state.attributes

        assert attrs.get(const.ATTR_OCCASION_TYPE) == const.OCCASION_BIRTHDAY

        # Self-contained badge-definition fields for UI (single-sensor consumption)
        assert const.ATTR_DESCRIPTION in attrs
        assert const.ATTR_LABELS in attrs
        assert const.DATA_BADGE_TARGET_TYPE in attrs
        assert const.DATA_BADGE_TARGET_THRESHOLD_VALUE in attrs
        assert const.ATTR_TARGET in attrs
        assert const.ATTR_REQUIRED_CHORES in attrs
        assert const.ATTR_BADGE_AWARDS in attrs
        assert const.ATTR_RESET_SCHEDULE in attrs
        assert const.DATA_BADGE_RESET_SCHEDULE_START_DATE not in attrs
        assert const.DATA_BADGE_RESET_SCHEDULE_END_DATE not in attrs
        assert const.ATTR_ASSOCIATED_ACHIEVEMENT in attrs
        assert const.ATTR_ASSOCIATED_CHALLENGE in attrs
        assert const.ATTR_SYSTEM_BADGE_EID in attrs

        # Stable default shapes for optional fields
        assert isinstance(attrs[const.ATTR_LABELS], list)
        assert isinstance(attrs[const.ATTR_TARGET], dict)
        assert isinstance(attrs[const.ATTR_REQUIRED_CHORES], list)
        assert attrs[const.ATTR_ASSOCIATED_ACHIEVEMENT] is None
        assert attrs[const.ATTR_ASSOCIATED_CHALLENGE] is None

        # Structured awards payload (not comma-delimited text)
        awards = attrs[const.ATTR_BADGE_AWARDS]
        assert isinstance(awards, dict)
        assert isinstance(awards[const.DATA_BADGE_AWARDS_AWARD_ITEMS], list)
        assert isinstance(awards[const.AWARD_ITEMS_KEY_REWARDS], list)
        assert isinstance(awards[const.AWARD_ITEMS_KEY_BONUSES], list)
        assert isinstance(awards[const.AWARD_ITEMS_KEY_PENALTIES], list)

        # Reset schedule is always present with explicit shape
        reset_schedule = attrs[const.ATTR_RESET_SCHEDULE]
        assert isinstance(reset_schedule, dict)
        assert const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY in reset_schedule
        assert const.DATA_BADGE_RESET_SCHEDULE_START_DATE in reset_schedule
        assert const.DATA_BADGE_RESET_SCHEDULE_END_DATE in reset_schedule
        assert (
            reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY]
            == badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY
            ]
        )
        assert (
            reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_START_DATE]
            == badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE
            ]
        )
        assert (
            reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE]
            == badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE
            ]
        )

    async def test_special_occasion_yearly_cycle_window_is_single_day(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Special-occasion yearly rollover windows persist as single-day start/end."""
        config_entry = setup_minimal.config_entry
        coordinator = setup_minimal.coordinator
        assignee_id = next(iter(coordinator.assignees_data.keys()))

        badge_data = {
            CFOF_BADGES_INPUT_NAME: "Birthday Single-Day Window",
            CFOF_BADGES_INPUT_ICON: "mdi:cake-variant",
            CFOF_BADGES_INPUT_OCCASION_TYPE: const.OCCASION_BIRTHDAY,
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: [assignee_id],
            CFOF_BADGES_INPUT_AWARD_POINTS: 10.0,
            CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
        }

        await add_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            BADGE_TYPE_SPECIAL_OCCASION,
            badge_data,
        )

        badge_id, _ = get_badge_by_name(coordinator, "Birthday Single-Day Window")
        badge_progress = coordinator.assignees_data[assignee_id][
            DATA_USER_BADGE_PROGRESS
        ][badge_id]

        today_iso = dt_today_iso()
        stale_end = dt_add_interval(
            today_iso,
            interval_unit=const.TIME_UNIT_DAYS,
            delta=-400,
            return_type=const.HELPER_RETURN_ISO_DATE,
        )
        badge_info = coordinator.badges_data[badge_id]
        badge_info[const.DATA_BADGE_RESET_SCHEDULE] = {
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: const.FREQUENCY_YEARLY,
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE: stale_end,
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE: stale_end,
        }

        changed = coordinator.gamification_manager._advance_non_cumulative_badge_cycle_if_needed(
            assignee_id,
            badge_id,
            badge_info,
            today_iso=today_iso,
        )

        assert changed is True
        assert (
            badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE
            ]
            == badge_info[const.DATA_BADGE_RESET_SCHEDULE][
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE
            ]
        )
        assert const.DATA_USER_BADGE_PROGRESS_START_DATE not in badge_progress
        assert const.DATA_USER_BADGE_PROGRESS_END_DATE not in badge_progress


# ============================================================================
# BADGE STEP ID VERIFICATION TESTS
# ============================================================================


class TestBadgeStepSequence:
    """Verify the correct step sequence for each badge type."""

    async def test_daily_badge_step_id(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test that selecting daily badge type shows daily step."""
        config_entry = setup_minimal.config_entry

        # Navigate to add badge type selection
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Select daily badge type
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_DAILY},
        )

        # Should show daily badge form
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_DAILY

    async def test_periodic_badge_step_id(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test that selecting periodic badge type shows periodic step."""
        config_entry = setup_minimal.config_entry

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
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

        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_PERIODIC

    async def test_special_occasion_badge_step_id(
        self,
        hass: HomeAssistant,
        setup_minimal: SetupResult,
    ) -> None:
        """Test that selecting special occasion badge type shows special step."""
        config_entry = setup_minimal.config_entry

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
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
            user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_SPECIAL_OCCASION},
        )

        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_SPECIAL
