"""Unit tests for backup utility functions in backup_helpers.py.

Tests low-level backup infrastructure:
- create_timestamped_backup(): Backup file creation with tags
- cleanup_old_backups(): Retention policy enforcement
- format_backup_age(): Human-readable age formatting
- validate_backup_json(): JSON structure validation

Migrated from: tests/legacy/test_flow_helpers.py
Reason: Tests specialized backup service utilities not covered by integration tests
"""

# pylint: disable=redacted-outer-name  # Pytest fixtures

import datetime
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers.backup_helpers import (
    cleanup_old_backups,
    create_timestamped_backup,
    format_backup_age,
    validate_backup_json,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_storage_manager():
    """Create mock storage manager."""
    manager = MagicMock()
    manager.data = {
        "schema_version": 42,
        "assignees": {"assignee1": {"name": "Alice", "points": 100}},
        "chores": {"chore1": {"name": "Dishes", "points": 10}},
        "rewards": {},
    }
    manager.get_all_data.return_value = manager.data
    return manager


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path.side_effect = lambda *args: os.path.join(
        "/mock/.storage", *args[1:]
    )
    # Mock async_add_executor_job to return the result directly (simulating async execution)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    return hass


@pytest.fixture
def mock_config_entry():
    """Create mock config entry for cleanup tests."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain=const.DOMAIN,
        title="ChoreOps",
        data={},
        options={},  # Empty options - tests will pass max_backups parameter
        unique_id=None,
    )


# =============================================================================


@patch("custom_components.choreops.helpers.backup_helpers.dt_util.utcnow")
@patch("custom_components.choreops.helpers.backup_helpers.shutil.copy2")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
async def test_create_timestamped_backup_success(
    mock_makedirs, mock_exists, mock_copy, mock_utcnow, mock_hass, mock_storage_manager
):
    """Test successful backup creation."""
    # Setup
    mock_utcnow.return_value = datetime.datetime(
        2024, 12, 18, 15, 30, 45, tzinfo=datetime.UTC
    )

    # Execute
    filename = await create_timestamped_backup(
        mock_hass, mock_storage_manager, "recovery"
    )

    # Verify
    assert filename == "choreops_data_2024-12-18_15-30-45_recovery"
    assert mock_copy.call_count == 1
    call_args = mock_copy.call_args[0]
    assert (
        call_args[1]
        == "/mock/.storage/choreops/choreops_data_2024-12-18_15-30-45_recovery"
    )


@patch("custom_components.choreops.helpers.backup_helpers.dt_util.utcnow")
@patch("custom_components.choreops.helpers.backup_helpers.shutil.copy2")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
async def test_create_timestamped_backup_all_tags(
    mock_makedirs, mock_exists, mock_copy, mock_utcnow, mock_hass, mock_storage_manager
):
    """Test backup creation with all tag types."""
    mock_utcnow.return_value = datetime.datetime(
        2024, 12, 18, 10, 0, 0, tzinfo=datetime.UTC
    )

    tags = ["recovery", "removal", "reset", "pre-migration", "manual"]

    for tag in tags:
        filename = await create_timestamped_backup(mock_hass, mock_storage_manager, tag)
        assert filename == f"choreops_data_2024-12-18_10-00-00_{tag}"
        assert mock_copy.call_count >= 1


@patch("builtins.open", side_effect=OSError("Disk full"))
async def test_create_timestamped_backup_write_failure(
    mock_file, mock_hass, mock_storage_manager
):
    """Test backup creation handles write failures gracefully."""
    filename = await create_timestamped_backup(
        mock_hass, mock_storage_manager, "recovery"
    )

    assert filename is None


async def test_create_timestamped_backup_no_data(mock_hass):
    """Test backup creation when no data available."""
    manager = MagicMock()
    manager.get_all_data.return_value = None

    filename = await create_timestamped_backup(mock_hass, manager, "recovery")

    assert filename is None


# =============================================================================
# TESTS: cleanup_old_backups()
# =============================================================================


@patch("custom_components.choreops.helpers.backup_helpers.discover_backups")
@patch("os.remove")
async def test_cleanup_old_backups_respects_max_limit(
    mock_remove, mock_discover, mock_hass, mock_storage_manager, mock_config_entry
):
    """Test cleanup keeps newest N backups per tag."""
    # Setup: 5 recovery backups (keep newest 3)
    mock_discover.return_value = [
        {
            "filename": "choreops_data_2024-12-18_15-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 15, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 1,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_14-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 14, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 2,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_13-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 13, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 3,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_12-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 12, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 4,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_11-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 11, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 5,
            "size_bytes": 1000,
        },
    ]

    # Execute: Keep newest 3
    await cleanup_old_backups(
        mock_hass, mock_storage_manager, mock_config_entry, max_backups=3
    )

    # Verify: Deleted oldest 2
    assert mock_remove.call_count == 2
    deleted_files = [call.args[0] for call in mock_remove.call_args_list]
    assert (
        "/mock/.storage/choreops/choreops_data_2024-12-18_12-00-00_recovery"
        in deleted_files
    )
    assert (
        "/mock/.storage/choreops/choreops_data_2024-12-18_11-00-00_recovery"
        in deleted_files
    )


@patch("custom_components.choreops.helpers.backup_helpers.discover_backups")
@patch("os.remove")
async def test_cleanup_old_backups_never_deletes_permanent_tags(
    mock_remove, mock_discover, mock_hass, mock_storage_manager, mock_config_entry
):
    """Test cleanup never deletes pre-migration or manual backups."""
    # Setup: Mix of tags
    mock_discover.return_value = [
        {
            "filename": "choreops_data_2024-12-18_15-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 15, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 1,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_10-00-00_pre-migration",
            "tag": "pre-migration",
            "timestamp": datetime.datetime(2024, 12, 18, 10, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 6,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_09-00-00_manual",
            "tag": "manual",
            "timestamp": datetime.datetime(2024, 12, 18, 9, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 7,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_08-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 8, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 8,
            "size_bytes": 1000,
        },
    ]

    # Execute: Keep only 1 per tag
    await cleanup_old_backups(
        mock_hass, mock_storage_manager, mock_config_entry, max_backups=1
    )

    # Verify: Only deleted old recovery backup
    assert mock_remove.call_count == 1
    deleted_file = mock_remove.call_args_list[0].args[0]
    assert "choreops_data_2024-12-18_08-00-00_recovery" in deleted_file


@patch("custom_components.choreops.helpers.backup_helpers.discover_backups")
@patch("os.remove")
async def test_cleanup_old_backups_disabled_when_zero(
    mock_remove, mock_discover, mock_hass, mock_storage_manager, mock_config_entry
):
    """Test cleanup deletes ALL backups when max_backups is 0 (backups disabled).

    Note: max_backups=0 means delete everything - useful when disabling backups entirely.
    """
    mock_discover.return_value = [
        {
            "filename": "choreops_data_2024-12-18_15-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 15, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 1,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_14-00-00_manual",
            "tag": "manual",
            "timestamp": datetime.datetime(2024, 12, 18, 14, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 2,
            "size_bytes": 1000,
        },
    ]

    # Execute
    await cleanup_old_backups(
        mock_hass, mock_storage_manager, mock_config_entry, max_backups=0
    )

    # Verify: All backups deleted
    assert mock_remove.call_count == 2


@patch("custom_components.choreops.helpers.backup_helpers.discover_backups")
@patch("os.remove", side_effect=OSError("Permission denied"))
async def test_cleanup_old_backups_continues_on_error(
    mock_remove, mock_discover, mock_hass, mock_storage_manager, mock_config_entry
):
    """Test cleanup continues even if individual deletion fails."""
    # Setup: 3 old backups
    mock_discover.return_value = [
        {
            "filename": "choreops_data_2024-12-18_15-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 15, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 1,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_14-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 14, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 2,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_13-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 13, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 3,
            "size_bytes": 1000,
        },
    ]

    # Execute: Keep only 1 (should try to delete 2, both fail)
    await cleanup_old_backups(
        mock_hass, mock_storage_manager, mock_config_entry, max_backups=1
    )

    # Verify: Attempted to delete both old backups despite failures
    assert mock_remove.call_count == 2


@patch("custom_components.choreops.helpers.backup_helpers.discover_backups")
@patch("os.remove")
async def test_cleanup_old_backups_handles_non_integer_max_backups(
    mock_remove, mock_discover, mock_hass, mock_storage_manager, mock_config_entry
):
    """Test cleanup handles string/float max_backups values (defensive type coercion).

    Verifies fix for TypeError: slice indices must be integers or None.
    Bug occurred when config entry options stored max_backups as string.
    Function now coerces to int defensively before slice operations.
    """
    # Setup: 5 recovery backups
    mock_discover.return_value = [
        {
            "filename": "choreops_data_2024-12-18_15-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 15, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 1,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_14-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 14, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 2,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_13-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 13, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 3,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_12-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 12, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 4,
            "size_bytes": 1000,
        },
        {
            "filename": "choreops_data_2024-12-18_11-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime.datetime(2024, 12, 18, 11, 0, 0, tzinfo=datetime.UTC),
            "age_hours": 5,
            "size_bytes": 1000,
        },
    ]

    # Test with string value (as might come from options flow)
    await cleanup_old_backups(
        mock_hass, mock_storage_manager, mock_config_entry, max_backups=int("3")
    )

    # Verify: Correctly interpreted "3" as integer and deleted oldest 2
    assert mock_remove.call_count == 2
    deleted_files = [call.args[0] for call in mock_remove.call_args_list]
    assert (
        "/mock/.storage/choreops/choreops_data_2024-12-18_12-00-00_recovery"
        in deleted_files
    )
    assert (
        "/mock/.storage/choreops/choreops_data_2024-12-18_11-00-00_recovery"
        in deleted_files
    )

    # Reset mock for second test with float
    mock_remove.reset_mock()

    # Test with float value (edge case)
    await cleanup_old_backups(
        mock_hass, mock_storage_manager, mock_config_entry, max_backups=int(2.0)
    )

    # Verify: Correctly interpreted 2.0 as integer and deleted oldest 3
    assert mock_remove.call_count == 3


# =============================================================================
# TESTS: format_backup_age()
# =============================================================================


def test_format_backup_age_minutes():
    """Test formatting for ages less than 1 hour."""
    assert format_backup_age(0.5) == "30 minutes ago"
    assert format_backup_age(0.016666) == "1 minute ago"
    assert format_backup_age(0.1) == "6 minutes ago"


def test_format_backup_age_hours():
    """Test formatting for ages between 1 and 24 hours."""
    assert format_backup_age(1) == "1 hour ago"
    assert format_backup_age(5) == "5 hours ago"
    assert format_backup_age(23.5) == "23 hours ago"


def test_format_backup_age_days():
    """Test formatting for ages between 1 day and 1 week."""
    assert format_backup_age(24) == "1 day ago"
    assert format_backup_age(48) == "2 days ago"
    assert format_backup_age(72) == "3 days ago"
    assert format_backup_age(167) == "6 days ago"


def test_format_backup_age_weeks():
    """Test formatting for ages greater than 1 week."""
    assert format_backup_age(168) == "1 week ago"
    assert format_backup_age(336) == "2 weeks ago"
    assert format_backup_age(720) == "4 weeks ago"


# =============================================================================
# TESTS: validate_backup_json()
# =============================================================================


def test_validate_backup_json_valid_minimal():
    """Test validation accepts minimal valid backup."""
    json_str = json.dumps(
        {
            "schema_version": 42,
            "assignees": {"assignee1": {"name": "Alice"}},
        }
    )

    assert validate_backup_json(json_str) is True


def test_validate_backup_json_valid_complete():
    """Test validation accepts complete backup with all entity types."""
    json_str = json.dumps(
        {
            "schema_version": 42,
            "assignees": {},
            "approvers": {},
            "chores": {},
            "rewards": {},
            "bonuses": {},
            "penalties": {},
            "achievements": {},
            "challenges": {},
            "badges": {},
        }
    )

    assert validate_backup_json(json_str) is True


def test_validate_backup_json_missing_version():
    """Test validation accepts JSON missing schema_version key (legacy format)."""
    json_str = json.dumps({"assignees": {"assignee1": {"name": "Alice"}}})

    # Old backups without schema_version are accepted - they will be migrated
    assert validate_backup_json(json_str) is True


def test_validate_backup_json_missing_entity_types():
    """Test validation rejects JSON with schema_version but no entity types."""
    json_str = json.dumps({"schema_version": 42})

    assert validate_backup_json(json_str) is False


def test_validate_backup_json_legacy_v3_format():
    """Test validation accepts legacy KC 3.0 format without schema_version."""
    # Simulates old KC 3.0 backup with badges as list, no schema_version
    json_str = json.dumps(
        {
            "assignees": [{"name": "Alice", "points": 100, "badges": []}],
            "chores": [{"name": "Dishes", "points": 10}],
            "rewards": [],
        }
    )

    # Should accept - migration will handle conversion
    assert validate_backup_json(json_str) is True


def test_validate_backup_json_not_dict():
    """Test validation rejects JSON that is not a dictionary."""
    json_str = json.dumps(["not", "a", "dict"])

    assert validate_backup_json(json_str) is False


def test_validate_backup_json_invalid_syntax():
    """Test validation rejects malformed JSON."""
    json_str = '{"schema_version": 42, "assignees": {'  # Missing closing braces

    assert validate_backup_json(json_str) is False


def test_validate_backup_json_empty_string():
    """Test validation rejects empty string."""
    assert validate_backup_json("") is False


def test_validate_backup_json_null_string():
    """Test validation rejects null JSON."""
    assert validate_backup_json("null") is False


def test_validate_backup_json_store_v1_format():
    """Test validation accepts Store version 1 format (KC 3.0/3.1/4.0beta1)."""
    # Simulates Home Assistant Store format with version 1 wrapper
    json_str = json.dumps(
        {
            "version": 1,
            "minor_version": 1,
            "key": "choreops_data",
            "data": {
                "assignees": {"assignee1": {"name": "Alice", "points": 100}},
                "chores": {"chore1": {"name": "Dishes", "points": 10}},
                "rewards": {},
            },
        }
    )

    # Should accept - Store version 1 is supported
    assert validate_backup_json(json_str) is True


def test_validate_backup_json_store_v2_rejected():
    """Test validation rejects Store version 2 (unsupported future format)."""
    # Simulates hypothetical Store version 2
    json_str = json.dumps(
        {
            "version": 2,
            "minor_version": 0,
            "key": "choreops_data",
            "data": {
                "assignees": {"assignee1": {"name": "Alice", "points": 100}},
                "chores": {},
            },
        }
    )

    # Should reject - only version 1 is supported
    assert validate_backup_json(json_str) is False


def test_validate_backup_json_store_missing_data_wrapper():
    """Test validation rejects Store format without data wrapper."""
    json_str = json.dumps(
        {
            "version": 1,
            "minor_version": 1,
            "key": "choreops_data",
            # Missing "data" key
            "assignees": {"assignee1": {"name": "Alice"}},
        }
    )

    # Should reject - Store format must have "data" wrapper
    assert validate_backup_json(json_str) is False


# =============================================================================
# TESTS: Config Entry Settings Backup/Restore
# =============================================================================


@patch("custom_components.choreops.helpers.backup_helpers.dt_util.utcnow")
@patch("custom_components.choreops.helpers.backup_helpers.shutil.copy2")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
async def test_backup_includes_config_entry_settings(
    mock_makedirs,
    mock_exists,
    mock_copy,
    mock_utcnow,
    mock_hass,
    mock_storage_manager,
):
    """Test backup includes config_entry_settings section with all 9 system settings."""
    from unittest.mock import MagicMock

    from custom_components.choreops import const

    # Setup
    mock_utcnow.return_value = datetime.datetime(
        2024, 12, 18, 15, 30, 45, tzinfo=datetime.UTC
    )

    # Create mock config entry with custom settings
    mock_config_entry = MagicMock()
    mock_config_entry.options = {
        const.CONF_POINTS_LABEL: "Stars",
        const.CONF_POINTS_ICON: "mdi:star",
        const.CONF_UPDATE_INTERVAL: 10,
        const.CONF_CALENDAR_SHOW_PERIOD: 60,
        const.CONF_RETENTION_DAILY: 5,
        const.CONF_RETENTION_WEEKLY: 3,
        const.CONF_RETENTION_MONTHLY: 2,
        const.CONF_RETENTION_YEARLY: 1,
        const.CONF_POINTS_ADJUST_VALUES: [+5.0, -5.0],
    }

    # Mock storage file path
    storage_path = "/mock/.storage/choreops_data"
    mock_storage_manager.get_storage_path.return_value = storage_path

    # Mock backup file operations
    backup_content = {"version": 1, "data": {"assignees": {}}}

    def mock_read_text(encoding="utf-8"):
        return json.dumps(backup_content)

    def mock_write_text(content, encoding="utf-8"):
        nonlocal backup_content
        backup_content = json.loads(content)

    with (
        patch("pathlib.Path.read_text", side_effect=mock_read_text),
        patch("pathlib.Path.write_text", side_effect=mock_write_text),
    ):
        # Execute
        filename = await create_timestamped_backup(
            mock_hass, mock_storage_manager, "manual", mock_config_entry
        )

    # Assert
    assert filename == "choreops_data_2024-12-18_15-30-45_manual"
    assert const.DATA_CONFIG_ENTRY_SETTINGS in backup_content

    settings = backup_content[const.DATA_CONFIG_ENTRY_SETTINGS]
    assert len(settings) == 9
    assert settings[const.CONF_POINTS_LABEL] == "Stars"
    assert settings[const.CONF_POINTS_ICON] == "mdi:star"
    assert settings[const.CONF_UPDATE_INTERVAL] == 10
    assert settings[const.CONF_CALENDAR_SHOW_PERIOD] == 60
    assert settings[const.CONF_RETENTION_DAILY] == 5
    assert settings[const.CONF_RETENTION_WEEKLY] == 3
    assert settings[const.CONF_RETENTION_MONTHLY] == 2
    assert settings[const.CONF_RETENTION_YEARLY] == 1
    assert settings[const.CONF_POINTS_ADJUST_VALUES] == [+5.0, -5.0]


@patch("custom_components.choreops.helpers.backup_helpers.dt_util.utcnow")
@patch("custom_components.choreops.helpers.backup_helpers.shutil.copy2")
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
async def test_roundtrip_preserves_all_settings(
    mock_makedirs,
    mock_exists,
    mock_copy,
    mock_utcnow,
    mock_hass,
    mock_storage_manager,
):
    """Test backup → restore roundtrip preserves all 9 system settings exactly."""
    from unittest.mock import MagicMock

    from custom_components.choreops import const
    from custom_components.choreops.helpers.backup_helpers import (
        validate_config_entry_settings,
    )

    # Setup with all custom values
    mock_utcnow.return_value = datetime.datetime(
        2024, 12, 18, 15, 30, 45, tzinfo=datetime.UTC
    )

    original_settings = {
        const.CONF_POINTS_LABEL: "Gems",
        const.CONF_POINTS_ICON: "mdi:diamond",
        const.CONF_UPDATE_INTERVAL: 15,
        const.CONF_CALENDAR_SHOW_PERIOD: 120,
        const.CONF_RETENTION_DAILY: 10,
        const.CONF_RETENTION_WEEKLY: 8,
        const.CONF_RETENTION_MONTHLY: 6,
        const.CONF_RETENTION_YEARLY: 4,
        const.CONF_POINTS_ADJUST_VALUES: [+2.5, -2.5, +7.5, -7.5],
    }

    mock_config_entry = MagicMock()
    mock_config_entry.options = original_settings

    storage_path = "/mock/.storage/choreops_data"
    mock_storage_manager.get_storage_path.return_value = storage_path

    backup_content = {"version": 1, "data": {"assignees": {}}}

    def mock_read_text(encoding="utf-8"):
        return json.dumps(backup_content)

    def mock_write_text(content, encoding="utf-8"):
        nonlocal backup_content
        backup_content = json.loads(content)

    with (
        patch("pathlib.Path.read_text", side_effect=mock_read_text),
        patch("pathlib.Path.write_text", side_effect=mock_write_text),
    ):
        # Step 1: Create backup
        await create_timestamped_backup(
            mock_hass, mock_storage_manager, "manual", mock_config_entry
        )

    # Step 2: Validate backup contains settings
    assert const.DATA_CONFIG_ENTRY_SETTINGS in backup_content
    backed_up_settings = backup_content[const.DATA_CONFIG_ENTRY_SETTINGS]

    # Step 3: Simulate restore - validate and compare
    restored_settings = validate_config_entry_settings(backed_up_settings)

    # Assert: All 9 settings preserved exactly
    assert len(restored_settings) == 9
    for key, original_value in original_settings.items():
        assert restored_settings[key] == original_value, (
            f"Setting {key} not preserved: expected {original_value}, "
            f"got {restored_settings[key]}"
        )
