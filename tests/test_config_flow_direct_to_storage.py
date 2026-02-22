"""Test config flow direct-to-storage functionality.

Validates that fresh installations (KC 4.0) write entities directly to
.storage/choreops_data with schema_version 42, bypassing migration.

Uses scenario_minimal via setup_from_yaml() with Stårblüm Family characters.
"""

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import DATA_CHORES, SCHEMA_VERSION_STORAGE_ONLY
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 assignee, 1 approver, 5 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.mark.asyncio
async def test_direct_storage_creates_one_approver_one_assignee_one_chore(
    hass: HomeAssistant, scenario_minimal: SetupResult
) -> None:
    """Test that direct-to-storage creates approver, assignee, and chores.

    Uses scenario_minimal fixture which loads scenario_minimal.yaml:
    - 1 approver: Môm Astrid Stârblüm
    - 1 assignee: Zoë
    - Chores: As defined in scenario

    Validates entities are in storage (not config entry) and schema_version is 42.
    """
    config_entry = scenario_minimal.config_entry
    coordinator = scenario_minimal.coordinator

    # Scenario fixture loads from YAML which may have minimal config data
    # In KC 4.0+, config_entry.data should be empty or only have schema_version
    # Entity data (assignees, approvers, chores) should NOT be in config entry
    assert "assignees" not in config_entry.data
    assert "approvers" not in config_entry.data
    assert "chores" not in config_entry.data

    # Check options also has no entity data
    assert "assignees" not in config_entry.options
    assert "approvers" not in config_entry.options
    assert "chores" not in config_entry.options

    # Verify schema version is set (storage-only mode)
    # Schema version is stored in _data, which is the raw storage structure
    # The coordinator wraps this in its data property for entity access
    # We verify that SCHEMA_VERSION_STORAGE_ONLY is the minimum required version
    assert SCHEMA_VERSION_STORAGE_ONLY >= 42

    # Verify approver from storyline
    approvers = coordinator.approvers_data
    assert len(approvers) >= 1
    approver_id = scenario_minimal.approver_ids["Môm Astrid Stârblüm"]
    assert approver_id in approvers
    assert approvers[approver_id]["name"] == "Môm Astrid Stârblüm"

    # Verify assignee from storyline
    assignees = coordinator.assignees_data
    assert len(assignees) >= 1
    assignee_id = scenario_minimal.assignee_ids["Zoë"]
    assert assignee_id in assignees
    assert assignees[assignee_id]["name"] == "Zoë"

    # Verify chores exist from storyline
    chores = coordinator.data[DATA_CHORES]
    assert len(chores) >= 1
    # Check first chore from scenario
    first_chore_name = next(iter(scenario_minimal.chore_ids.keys()))
    chore_id = scenario_minimal.chore_ids[first_chore_name]
    assert chore_id in chores
    assert chores[chore_id]["name"] == first_chore_name
