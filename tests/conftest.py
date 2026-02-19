"""Modern test fixtures for ChoreOps integration tests.

This conftest provides ONLY the core fixtures needed for modern testing:
1. pytest_plugins for HA test framework
2. auto_enable_custom_integrations autouse fixture
3. mock_hass_users for authorization testing
4. mock_config_entry for basic integration setup
5. init_integration for full integration setup

Modern tests get entity IDs from the dashboard helper sensor - NEVER construct them.
See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for the proper pattern.

For legacy tests using direct coordinator manipulation, see tests/legacy/conftest.py.
"""

# pylint: disable=redefined-outer-name

from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.choreops.const import DOMAIN

# ---------------------------------------------------------------------------
# Core pytest plugin registration (REQUIRED at top-level)
# ---------------------------------------------------------------------------

pytest_plugins = "pytest_homeassistant_custom_component"


# ---------------------------------------------------------------------------
# Pytest command-line options
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    """Add custom command-line options for test suite.

    Options:
    - --migration-file: Path to migration data file for generic migration tests
    """
    parser.addoption(
        "--migration-file",
        action="store",
        default=None,
        help="Path to migration data file for generic migration tests",
    )


# ---------------------------------------------------------------------------
# Autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: Any,  # Required fixture dependency
) -> Any:
    """Enable custom integrations in all tests."""
    return


# ---------------------------------------------------------------------------
# User fixtures for authorization testing
# ---------------------------------------------------------------------------


@pytest.fixture
async def mock_hass_users(hass: HomeAssistant) -> dict[str, Any]:
    """Create mock Home Assistant users for testing.

    User keys match ha_user values expected in test YAML files:
    - admin: System admin
    - approver1-approver25: Approver users (can approve chores)
    - assignee1-assignee100: Assignee users (can claim chores)

    Supports scenarios from minimal (3 assignees) to stress (100 assignees, 25 approvers).

    Usage in tests:
        from homeassistant.core import Context
        assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
        approver_context = Context(user_id=mock_hass_users["approver1"].id)
    """
    users: dict[str, Any] = {}

    # Admin user
    users["admin"] = await hass.auth.async_create_user(
        "Admin User",
        group_ids=["system-admin"],
    )

    # Create 25 approver users (covers stress scenario)
    for i in range(1, 26):
        users[f"approver{i}"] = await hass.auth.async_create_user(
            f"Approver {i}",
            group_ids=["system-users"],
        )

    # Create 100 assignee users (covers stress scenario)
    for i in range(1, 101):
        users[f"assignee{i}"] = await hass.auth.async_create_user(
            f"Assignee {i}",
            group_ids=["system-users"],
        )

    return users


# ---------------------------------------------------------------------------
# Config entry fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a minimal config entry for ChoreOps.

    Note: ChoreOps v4.2+ stores entity data in .storage/choreops_data,
    NOT in config_entry.data. The config_entry only holds system settings.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="ChoreOps",
        data={},  # Empty - data lives in storage
        options={},
        unique_id=None,
    )


@pytest.fixture
def mock_storage_data() -> dict[str, dict]:
    """Provide empty storage structure for testing initialization."""
    return {
        "meta": {"schema_version": 44},
        "assignees": {},
        "approvers": {},
        "chores": {},
        "badges": {},
        "rewards": {},
        "bonuses": {},
        "penalties": {},
        "achievements": {},
        "challenges": {},
        "pending_approvals": {"chores": {}, "rewards": {}},
    }


@pytest.fixture
def mock_storage_manager(mock_storage_data: dict) -> MagicMock:
    """Provide a mocked storage manager for unit testing without file I/O."""
    manager = MagicMock()
    manager.async_load.return_value = mock_storage_data
    manager.get_data.return_value = mock_storage_data
    manager.async_save.return_value = None
    return manager


# ---------------------------------------------------------------------------
# Integration setup fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up ChoreOps integration with empty data.

    This loads the integration fully (coordinator + all entity platforms)
    but with no assignees, chores, etc. Use scenario fixtures for populated data.

    Returns the config entry after successful setup.
    """
    mock_config_entry.add_to_hass(hass)

    # Set up lovelace before our integration (it's a dependency)
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()

    # Patch storage to avoid filesystem access (using HA's Store directly)
    with patch(
        "homeassistant.helpers.storage.Store.async_load",
        return_value={
            "meta": {"schema_version": 44},
            "assignees": {},
            "approvers": {},
            "chores": {},
            "badges": {},
            "rewards": {},
            "bonuses": {},
            "penalties": {},
            "achievements": {},
            "challenges": {},
            "pending_approvals": {"chores": {}, "rewards": {}},
        },
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
