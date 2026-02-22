"""Test the setup helper functions.

These tests verify that setup_scenario and related helpers properly
navigate the config flow and create entities.
"""

# pylint: disable=redefined-outer-name

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import (
    SetupResult,
    setup_minimal_scenario,
    setup_multi_assignee_scenario,
    setup_scenario,
)


@pytest.mark.asyncio
async def test_setup_minimal_scenario(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_minimal_scenario creates 1 assignee, 1 approver, 1 chore."""
    result = await setup_minimal_scenario(hass, mock_hass_users)

    assert isinstance(result, SetupResult)
    assert result.config_entry is not None
    assert result.coordinator is not None

    # Verify assignee was created
    assert "Zoë" in result.assignee_ids
    assert result.assignee_ids["Zoë"] is not None

    # Verify approver was created
    assert "Mom" in result.approver_ids

    # Verify chore was created
    assert "Clean Room" in result.chore_ids

    # Verify coordinator has the data
    assignee_names = {
        assignee_data.get("name")
        for assignee_data in result.coordinator.assignees_data.values()
        if isinstance(assignee_data, dict)
    }
    approver_names = {
        approver_data.get("name")
        for approver_data in result.coordinator.approvers_data.values()
        if isinstance(approver_data, dict)
    }
    assert "Zoë" in assignee_names
    assert "Mom" in approver_names
    assert len(result.coordinator.chores_data) == 1


@pytest.mark.asyncio
async def test_setup_scenario_custom_config(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_scenario with custom configuration."""
    result = await setup_scenario(
        hass,
        mock_hass_users,
        {
            "points": {"label": "Stars", "icon": "mdi:star"},
            "assignees": [
                {"name": "Alex", "ha_user": "assignee1"},
                {"name": "Sarah", "ha_user": "assignee2"},
            ],
            "approvers": [
                {
                    "name": "Dad",
                    "ha_user": "approver1",
                    "assignees": ["Alex", "Sarah"],
                }
            ],
            "chores": [
                {
                    "name": "Do Homework",
                    "assigned_to": ["Alex"],
                    "points": 20.0,
                },
                {
                    "name": "Feed Cat",
                    "assigned_to": ["Alex", "Sarah"],
                    "points": 5.0,
                    "completion_criteria": "shared_all",
                },
            ],
        },
    )

    # Verify assignees
    assert "Alex" in result.assignee_ids
    assert "Sarah" in result.assignee_ids
    assignee_names = {
        assignee_data.get("name")
        for assignee_data in result.coordinator.assignees_data.values()
        if isinstance(assignee_data, dict)
    }
    assert {"Alex", "Sarah"}.issubset(assignee_names)

    # Verify approver
    assert "Dad" in result.approver_ids
    approver_names = {
        approver_data.get("name")
        for approver_data in result.coordinator.approvers_data.values()
        if isinstance(approver_data, dict)
    }
    assert "Dad" in approver_names

    # Verify chores
    assert "Do Homework" in result.chore_ids
    assert "Feed Cat" in result.chore_ids
    assert len(result.coordinator.chores_data) == 2

    # Verify points setting
    assert result.config_entry.options["points_label"] == "Stars"
    assert result.config_entry.options["points_icon"] == "mdi:star"


@pytest.mark.asyncio
async def test_setup_multi_assignee_scenario(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_multi_assignee_scenario creates multiple assignees with shared chore."""
    result = await setup_multi_assignee_scenario(
        hass,
        mock_hass_users,
        assignee_names=["Assignee1", "Assignee2", "Assignee3"],
        approver_name="Approver",
        shared_chore_name="Group Task",
    )

    # Verify all assignees created
    assert "Assignee1" in result.assignee_ids
    assert "Assignee2" in result.assignee_ids
    assert "Assignee3" in result.assignee_ids
    assignee_names = {
        assignee_data.get("name")
        for assignee_data in result.coordinator.assignees_data.values()
        if isinstance(assignee_data, dict)
    }
    assert {"Assignee1", "Assignee2", "Assignee3"}.issubset(assignee_names)

    # Verify shared chore
    assert "Group Task" in result.chore_ids


@pytest.mark.asyncio
async def test_setup_scenario_no_chores(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_scenario works with no chores configured."""
    result = await setup_scenario(
        hass,
        mock_hass_users,
        {
            "assignees": [{"name": "Solo Assignee", "ha_user": "assignee1"}],
            "approvers": [{"name": "Solo Approver", "ha_user": "approver1"}],
            # No chores
        },
    )

    assert "Solo Assignee" in result.assignee_ids
    assert "Solo Approver" in result.approver_ids
    assert len(result.chore_ids) == 0
    assert len(result.coordinator.chores_data) == 0


@pytest.mark.asyncio
async def test_setup_scenario_no_approvers(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_scenario works with no approvers configured."""
    result = await setup_scenario(
        hass,
        mock_hass_users,
        {
            "assignees": [{"name": "Orphan Assignee", "ha_user": "assignee1"}],
            # No approvers
            "chores": [
                {"name": "Self Chore", "assigned_to": ["Orphan Assignee"], "points": 5}
            ],
        },
    )

    assert "Orphan Assignee" in result.assignee_ids
    assert isinstance(result.approver_ids, dict)
    assert "Self Chore" in result.chore_ids
