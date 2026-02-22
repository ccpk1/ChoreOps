"""Tests for YAML-based scenario setup using config flow.

These tests verify that the setup_from_yaml() helper correctly loads
scenario definitions and configures the integration through the config flow.
"""

# pylint: disable=redefined-outer-name

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers.setup import setup_from_yaml

# Note: mock_hass_users fixture is provided by conftest.py
# It creates real HA users via hass.auth.async_create_user()


@pytest.mark.asyncio
async def test_setup_from_yaml_scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test loading the full scenario from YAML file.

    Verifies:
    - YAML file loads successfully
    - Config flow completes without errors
    - All 3 assignees are created with correct names
    - All 2 approvers are created
    - All 18 chores are created with correct assignment
    - ID mappings are populated
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    # Verify setup succeeded
    assert result.config_entry is not None
    assert result.coordinator is not None

    # Verify assignees were created (3 assignees in scenario_full)
    assert len(result.assignee_ids) == 3
    assert "Zoë" in result.assignee_ids
    assert "Max!" in result.assignee_ids
    assert "Lila" in result.assignee_ids

    # Verify configured approvers were created.
    # approver_ids may also include approver-compatible linked-profile records.
    assert len(result.approver_ids) >= 2
    assert "Môm Astrid Stârblüm" in result.approver_ids
    assert "Dad Leo" in result.approver_ids

    # Verify chores were created (18 chores in scenario_full)
    assert len(result.chore_ids) == 18

    # Verify specific chores exist with special characters
    assert "Feed the cåts" in result.chore_ids
    assert "Wåter the plänts" in result.chore_ids
    assert "Pick up Lëgo!" in result.chore_ids

    # Verify coordinator has data
    assert len(result.coordinator.assignees_data) == 3
    assert len(result.coordinator.approvers_data) >= 2
    assert len(result.coordinator.chores_data) == 18


@pytest.mark.asyncio
async def test_setup_from_yaml_assignee_chore_assignment(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that chore assignments are correct after YAML load.

    Verifies that assignees are properly assigned to chores based on YAML config.
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    coordinator = result.coordinator

    # Get Zoë's ID
    zoe_id = result.assignee_ids["Zoë"]

    # "Feed the cåts" is assigned only to Zoë
    feed_cats_id = result.chore_ids["Feed the cåts"]
    feed_cats_data = coordinator.chores_data[feed_cats_id]
    assert zoe_id in feed_cats_data.get("assigned_assignees", [])

    # "Stär sweep" is assigned to all 3 assignees
    star_sweep_id = result.chore_ids["Stär sweep"]
    star_sweep_data = coordinator.chores_data[star_sweep_id]
    assigned = star_sweep_data.get("assigned_assignees", [])
    assert len(assigned) == 3
    assert result.assignee_ids["Zoë"] in assigned
    assert result.assignee_ids["Max!"] in assigned
    assert result.assignee_ids["Lila"] in assigned


@pytest.mark.asyncio
async def test_setup_from_yaml_completion_criteria(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that completion criteria are set correctly from YAML.

    Verifies:
    - Independent chores have independent completion
    - Shared_all chores have shared_all completion
    - Shared_first chores have shared_first completion
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    coordinator = result.coordinator

    # "Feed the cåts" should be independent
    feed_cats_id = result.chore_ids["Feed the cåts"]
    feed_cats_data = coordinator.chores_data[feed_cats_id]
    assert feed_cats_data.get("completion_criteria") == "independent"

    # "Family Dinner Prep" should be shared_all
    dinner_id = result.chore_ids["Family Dinner Prep"]
    dinner_data = coordinator.chores_data[dinner_id]
    assert dinner_data.get("completion_criteria") == "shared_all"

    # "Garage Cleanup" should be shared_first
    garage_id = result.chore_ids["Garage Cleanup"]
    garage_data = coordinator.chores_data[garage_id]
    assert garage_data.get("completion_criteria") == "shared_first"


@pytest.mark.asyncio
async def test_setup_from_yaml_auto_approve(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that auto_approve is set correctly from YAML.

    Verifies:
    - "Wåter the plänts" has auto_approve: true
    - "Feed the cåts" has auto_approve: false (default)
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    coordinator = result.coordinator

    # "Wåter the plänts" should have auto_approve
    water_id = result.chore_ids["Wåter the plänts"]
    water_data = coordinator.chores_data[water_id]
    assert water_data.get("auto_approve") is True

    # "Feed the cåts" should NOT have auto_approve
    feed_cats_id = result.chore_ids["Feed the cåts"]
    feed_cats_data = coordinator.chores_data[feed_cats_id]
    assert feed_cats_data.get("auto_approve") is False


@pytest.mark.asyncio
async def test_setup_from_yaml_system_settings(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that system settings (points) are configured from YAML.

    Verifies:
    - Points label is set to "Star Points"
    - Points icon is set to "mdi:star"
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )

    # Check config entry options for system settings
    entry = result.config_entry
    assert entry.options.get("points_label") == "Star Points"
    assert entry.options.get("points_icon") == "mdi:star"


@pytest.mark.asyncio
async def test_setup_from_yaml_file_not_found(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test that FileNotFoundError is raised for missing YAML file."""
    with pytest.raises(FileNotFoundError, match="Scenario YAML not found"):
        await setup_from_yaml(
            hass,
            mock_hass_users,
            "tests/scenarios/nonexistent.yaml",
        )
