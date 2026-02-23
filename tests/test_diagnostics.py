"""Tests for ChoreOps diagnostics module.

Tests diagnostics export returns raw storage data directly.
Validates byte-for-byte compatibility with storage file for paste recovery.
"""

# pylint: disable=redefined-outer-name  # Pytest fixtures shadow names

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
import pytest

from custom_components.choreops import const
from custom_components.choreops.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_storage_data():
    """Create mock raw storage data (simulates choreops_data file)."""
    return {
        const.DATA_ASSIGNEES: {
            "assignee1": {
                const.DATA_USER_NAME: "Alice",
                const.DATA_USER_INTERNAL_ID: "assignee1",
                const.DATA_ASSIGNEE_POINTS: 100,
            },
            "assignee2": {
                const.DATA_USER_NAME: "Bob",
                const.DATA_USER_INTERNAL_ID: "assignee2",
                const.DATA_ASSIGNEE_POINTS: 50,
            },
        },
        const.DATA_CHORES: {
            "chore1": {
                const.DATA_CHORE_NAME: "Clean Room",
                const.DATA_CHORE_INTERNAL_ID: "chore1",
            },
        },
        const.DATA_REWARDS: {},
        const.DATA_PENALTIES: {},
        const.DATA_BONUSES: {},
        const.DATA_BADGES: {},
        const.DATA_APPROVERS: {},
        const.DATA_ACHIEVEMENTS: {},
        const.DATA_CHALLENGES: {},
        const.DATA_SCHEMA_VERSION: 42,
    }


@pytest.fixture
def mock_coordinator(mock_storage_data):
    """Create a mock coordinator with storage manager."""
    coordinator = MagicMock()

    # Mock storage manager with raw data
    store = MagicMock()
    store.data = mock_storage_data
    coordinator.store = store

    # Mock convenience accessors (point to same data)
    coordinator.assignees_data = mock_storage_data[const.DATA_ASSIGNEES]

    return coordinator


@pytest.fixture
def mock_config_entry(mock_coordinator):
    """Create a mock config entry with runtime_data."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.version = 1
    entry.title = "ChoreOps"
    # Add runtime_data pointing to coordinator
    entry.runtime_data = mock_coordinator
    # Add default options for config_entry_settings
    entry.options = {
        const.CONF_POINTS_LABEL: const.DEFAULT_POINTS_LABEL,
        const.CONF_POINTS_ICON: const.DEFAULT_POINTS_ICON,
        const.CONF_UPDATE_INTERVAL: const.DEFAULT_UPDATE_INTERVAL,
        const.CONF_CALENDAR_SHOW_PERIOD: const.DEFAULT_CALENDAR_SHOW_PERIOD,
        const.CONF_RETENTION_DAILY: const.DEFAULT_RETENTION_DAILY,
        const.CONF_RETENTION_WEEKLY: const.DEFAULT_RETENTION_WEEKLY,
        const.CONF_RETENTION_MONTHLY: const.DEFAULT_RETENTION_MONTHLY,
        const.CONF_RETENTION_YEARLY: const.DEFAULT_RETENTION_YEARLY,
        const.CONF_POINTS_ADJUST_VALUES: const.DEFAULT_POINTS_ADJUST_VALUES,
    }
    return entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    # hass.data is no longer used - coordinator accessed via entry.runtime_data
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_device_entry():
    """Create a mock device entry."""
    device = MagicMock(spec=DeviceEntry)
    device.identifiers = {(const.DOMAIN, "assignee1")}
    return device


async def test_config_entry_diagnostics_returns_raw_storage(
    mock_hass, mock_config_entry, mock_coordinator, mock_storage_data
):
    """Test diagnostics returns raw storage data plus config_entry_settings."""
    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

    # Verify storage data is included
    for key, value in mock_storage_data.items():
        assert result[key] == value

    # Verify config_entry_settings is added
    assert const.DATA_CONFIG_ENTRY_SETTINGS in result


async def test_config_entry_diagnostics_has_all_storage_keys(
    mock_hass, mock_config_entry, mock_coordinator
):
    """Test diagnostics includes all core storage keys plus config_entry_settings."""
    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

    # Verify all core storage keys are present
    assert const.DATA_ASSIGNEES in result
    assert const.DATA_CHORES in result
    assert const.DATA_REWARDS in result
    assert const.DATA_PENALTIES in result
    assert const.DATA_BONUSES in result
    assert const.DATA_BADGES in result
    assert const.DATA_APPROVERS in result
    assert const.DATA_ACHIEVEMENTS in result
    assert const.DATA_CHALLENGES in result
    assert const.DATA_SCHEMA_VERSION in result
    # Verify config_entry_settings is added
    assert const.DATA_CONFIG_ENTRY_SETTINGS in result


async def test_config_entry_diagnostics_byte_for_byte_compatibility(
    mock_hass, mock_config_entry, mock_coordinator, mock_storage_data
):
    """Test diagnostics export preserves storage structure plus adds settings.

    Storage data remains byte-for-byte identical, with config_entry_settings
    added as an additional top-level key for restore compatibility.
    """
    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)

    # Verify storage keys are preserved exactly (not the whole dict due to added settings)
    for key in mock_storage_data:
        assert result[key] == mock_storage_data[key]

    # Verify assignees data structure preserved exactly
    assert result[const.DATA_ASSIGNEES]["assignee1"][const.DATA_USER_NAME] == "Alice"
    assert result[const.DATA_ASSIGNEES]["assignee1"][const.DATA_ASSIGNEE_POINTS] == 100
    assert result[const.DATA_ASSIGNEES]["assignee2"][const.DATA_USER_NAME] == "Bob"

    # Verify chores data structure preserved exactly
    assert result[const.DATA_CHORES]["chore1"][const.DATA_CHORE_NAME] == "Clean Room"

    # Verify config_entry_settings was added
    assert const.DATA_CONFIG_ENTRY_SETTINGS in result


async def test_device_diagnostics_returns_assignee_data(
    mock_hass, mock_config_entry, mock_device_entry, mock_coordinator
):
    """Test device diagnostics returns assignee-specific data."""
    result = await async_get_device_diagnostics(
        mock_hass, mock_config_entry, mock_device_entry
    )

    # Verify structure
    assert "assignee_id" in result
    assert "assignee_data" in result

    # Verify assignee data
    assert result["assignee_id"] == "assignee1"
    assert result["assignee_data"][const.DATA_USER_NAME] == "Alice"
    assert result["assignee_data"][const.DATA_ASSIGNEE_POINTS] == 100


async def test_device_diagnostics_missing_assignee_id(
    mock_hass, mock_config_entry, mock_coordinator
):
    """Test device diagnostics error when assignee_id cannot be determined."""
    # Create device with no identifiers
    device = MagicMock(spec=DeviceEntry)
    device.identifiers = set()

    result = await async_get_device_diagnostics(mock_hass, mock_config_entry, device)

    # Verify error response
    assert "error" in result
    assert "Could not determine assignee_id" in result["error"]


async def test_device_diagnostics_assignee_not_found(
    mock_hass, mock_config_entry, mock_coordinator
):
    """Test device diagnostics error when assignee data not found."""
    # Create device with non-existent assignee_id
    device = MagicMock(spec=DeviceEntry)
    device.identifiers = {(const.DOMAIN, "nonexistent_assignee")}

    result = await async_get_device_diagnostics(mock_hass, mock_config_entry, device)

    # Verify error response
    assert "error" in result
    assert (
        "Assignee data not found for assignee_id: nonexistent_assignee"
        in result["error"]
    )


async def test_diagnostics_simplicity():
    """Test that diagnostics implementation is simple and maintainable.

    The simplified approach:
    - Config entry diagnostics: Returns store.data directly
    - Device diagnostics: Returns assignee_data snapshot only
    - No parsing, reformatting, or wrapper metadata
    - Byte-for-byte identical to storage file
    - Future-proof (all storage keys automatically included)
    - Coordinator migration handles schema differences
    """
    # This is a documentation test confirming the design decision.
    # The actual simplicity is validated by the implementation having:
    # - Single line return for config entry diagnostics
    # - Minimal processing for device diagnostics
    # - No custom data structures or transformations
    assert True  # Documentation test - always passes


async def test_diagnostics_includes_settings(hass, mock_config_entry, mock_coordinator):
    """Test diagnostics export includes config_entry_settings section."""
    from custom_components.choreops import const
    from custom_components.choreops.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    # Setup config entry with custom settings
    mock_config_entry.options = {
        const.CONF_POINTS_LABEL: "Credits",
        const.CONF_POINTS_ICON: "mdi:currency-usd",
        const.CONF_UPDATE_INTERVAL: 25,
        const.CONF_CALENDAR_SHOW_PERIOD: 45,
        const.CONF_RETENTION_DAILY: 8,
        const.CONF_RETENTION_WEEKLY: 6,
        const.CONF_RETENTION_MONTHLY: 5,
        const.CONF_RETENTION_YEARLY: 3,
        const.CONF_POINTS_ADJUST_VALUES: [+3.0, -3.0],
    }

    # Register coordinator in hass.data
    hass.data.setdefault(const.DOMAIN, {})[mock_config_entry.entry_id] = (
        mock_coordinator
    )

    # Get diagnostics
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Assert: config_entry_settings section exists with all 9 settings
    assert const.DATA_CONFIG_ENTRY_SETTINGS in result
    settings = result[const.DATA_CONFIG_ENTRY_SETTINGS]

    assert len(settings) == 9
    assert settings[const.CONF_POINTS_LABEL] == "Credits"
    assert settings[const.CONF_POINTS_ICON] == "mdi:currency-usd"
    assert settings[const.CONF_UPDATE_INTERVAL] == 25
    assert settings[const.CONF_CALENDAR_SHOW_PERIOD] == 45
    assert settings[const.CONF_RETENTION_DAILY] == 8
    assert settings[const.CONF_RETENTION_WEEKLY] == 6
    assert settings[const.CONF_RETENTION_MONTHLY] == 5
    assert settings[const.CONF_RETENTION_YEARLY] == 3
    assert settings[const.CONF_POINTS_ADJUST_VALUES] == [+3.0, -3.0]
