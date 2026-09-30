"""Tests for persistent per-assignee achievement award timestamps."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.sensor import AssigneeAchievementProgressSensor
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def setup_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict,
) -> SetupResult:
    """Load the minimal integration scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


async def test_first_award_timestamp_is_preserved_and_exposed(
    hass: HomeAssistant,
    setup_minimal: SetupResult,
) -> None:
    """The first award time survives reevaluation and appears on the sensor."""
    coordinator = setup_minimal.coordinator
    manager = coordinator.gamification_manager
    assignee_id = next(iter(coordinator.assignees_data))
    assignee_name = coordinator.assignees_data[assignee_id][const.DATA_USER_NAME]
    achievement_id = "season-aware-achievement"
    achievement_name = "Season-aware Achievement"
    first_award = "2026-09-30T12:00:00+00:00"

    coordinator.achievements_data[achievement_id] = {
        const.DATA_ACHIEVEMENT_INTERNAL_ID: achievement_id,
        const.DATA_ACHIEVEMENT_NAME: achievement_name,
        const.DATA_ACHIEVEMENT_TYPE: const.ACHIEVEMENT_TYPE_TOTAL,
        const.DATA_ACHIEVEMENT_CRITERIA: "",
        const.DATA_ACHIEVEMENT_DESCRIPTION: "",
        const.DATA_ACHIEVEMENT_ICON: "mdi:trophy",
        const.DATA_ACHIEVEMENT_LABELS: [],
        const.DATA_ACHIEVEMENT_TARGET_VALUE: 1,
        const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: [assignee_id],
        const.DATA_ACHIEVEMENT_PROGRESS: {
            assignee_id: {
                const.DATA_ACHIEVEMENT_CURRENT_VALUE: 0,
                const.DATA_ACHIEVEMENT_AWARDED: False,
            }
        },
        const.DATA_ACHIEVEMENT_REWARD_POINTS: 0,
    }

    with patch(
        "custom_components.choreops.managers.gamification_manager.dt_now_utc_iso",
        side_effect=[first_award, "2026-10-01T12:00:00+00:00"],
    ):
        await manager.award_achievement(assignee_id, achievement_id)
        await manager.award_achievement(assignee_id, achievement_id)

    achievement = coordinator.achievements_data[achievement_id]
    assert achievement[const.DATA_USER_BADGES_EARNED_LAST_AWARDED] == {
        assignee_id: first_award
    }

    sensor = AssigneeAchievementProgressSensor(
        coordinator,
        setup_minimal.config_entry,
        assignee_id,
        assignee_name,
        achievement_id,
        achievement_name,
    )
    assert sensor.extra_state_attributes[
        const.DATA_USER_BADGES_EARNED_LAST_AWARDED
    ] == first_award
