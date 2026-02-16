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
    setup_multi_kid_scenario,
    setup_scenario,
)


@pytest.mark.asyncio
async def test_setup_minimal_scenario(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_minimal_scenario creates 1 kid, 1 parent, 1 chore."""
    result = await setup_minimal_scenario(hass, mock_hass_users)

    assert isinstance(result, SetupResult)
    assert result.config_entry is not None
    assert result.coordinator is not None

    # Verify kid was created
    assert "Zoë" in result.kid_ids
    assert result.kid_ids["Zoë"] is not None

    # Verify parent was created
    assert "Mom" in result.parent_ids

    # Verify chore was created
    assert "Clean Room" in result.chore_ids

    # Verify coordinator has the data
    assert len(result.coordinator.kids_data) == 1
    assert len(result.coordinator.parents_data) == 1
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
            "kids": [
                {"name": "Alex", "ha_user": "kid1"},
                {"name": "Sarah", "ha_user": "kid2"},
            ],
            "parents": [
                {
                    "name": "Dad",
                    "ha_user": "parent1",
                    "kids": ["Alex", "Sarah"],
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

    # Verify kids
    assert "Alex" in result.kid_ids
    assert "Sarah" in result.kid_ids
    assert len(result.coordinator.kids_data) == 2

    # Verify parent
    assert "Dad" in result.parent_ids
    assert len(result.coordinator.parents_data) == 1

    # Verify chores
    assert "Do Homework" in result.chore_ids
    assert "Feed Cat" in result.chore_ids
    assert len(result.coordinator.chores_data) == 2

    # Verify points setting
    assert result.config_entry.options["points_label"] == "Stars"
    assert result.config_entry.options["points_icon"] == "mdi:star"


@pytest.mark.asyncio
async def test_setup_multi_kid_scenario(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_multi_kid_scenario creates multiple kids with shared chore."""
    result = await setup_multi_kid_scenario(
        hass,
        mock_hass_users,
        kid_names=["Kid1", "Kid2", "Kid3"],
        parent_name="Parent",
        shared_chore_name="Group Task",
    )

    # Verify all kids created
    assert "Kid1" in result.kid_ids
    assert "Kid2" in result.kid_ids
    assert "Kid3" in result.kid_ids
    assert len(result.coordinator.kids_data) == 3

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
            "kids": [{"name": "Solo Kid", "ha_user": "kid1"}],
            "parents": [{"name": "Solo Parent", "ha_user": "parent1"}],
            # No chores
        },
    )

    assert "Solo Kid" in result.kid_ids
    assert "Solo Parent" in result.parent_ids
    assert len(result.chore_ids) == 0
    assert len(result.coordinator.chores_data) == 0


@pytest.mark.asyncio
async def test_setup_scenario_no_parents(
    hass: HomeAssistant, mock_hass_users: dict
) -> None:
    """Test setup_scenario works with no parents configured."""
    result = await setup_scenario(
        hass,
        mock_hass_users,
        {
            "kids": [{"name": "Orphan Kid", "ha_user": "kid1"}],
            # No parents
            "chores": [
                {"name": "Self Chore", "assigned_to": ["Orphan Kid"], "points": 5}
            ],
        },
    )

    assert "Orphan Kid" in result.kid_ids
    assert len(result.parent_ids) == 0
    assert "Self Chore" in result.chore_ids
