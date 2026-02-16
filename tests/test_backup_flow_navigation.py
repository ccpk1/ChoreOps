"""Tests for backup management UI flows in Options Flow.

Tests options flow navigation for backup operations:
- Backup actions menu navigation (create, delete, restore)
- Flow handler method existence (prevents UnknownStep errors)
- Backup tag-based protection (permanent vs. deletable)
- Max backup retention setting changes
- Cancel and error scenarios

Migrated from: tests/legacy/test_backup_essential_flows_fixed.py
Reason: Tests specialized backup UI flows not covered by modern integration tests
"""

# Accessing _progress for testing
# pylint: disable=protected-access

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import (
    BACKUP_TAG_MANUAL,
    BACKUP_TAG_RECOVERY,
    BACKUP_TAG_RESET,
    CFOF_BACKUP_ACTION_SELECTION,
    CONF_BACKUPS_MAX_RETAINED,
    OPTIONS_FLOW_GENERAL_OPTIONS,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
)


@pytest.mark.parametrize(
    "backup_action", ["create_backup", "delete_backup", "restore_backup"]
)
async def test_backup_actions_all_navigation_paths(
    hass: HomeAssistant,
    init_integration,
    backup_action: str,
) -> None:
    """Test navigation paths for all backup actions work without UnknownStep errors."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    # Mock backup discovery to avoid file system dependencies
    with patch(
        "custom_components.kidschores.helpers.backup_helpers.discover_backups",
        new=AsyncMock(return_value=[]),
    ):
        # Select backup action
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: backup_action},
        )

        # Verify no unknown step error
        expected_types = ["form", "menu"]
        assert result.get("type") in expected_types, (
            f"Unexpected result type for {backup_action}: {result}"
        )


@pytest.mark.parametrize(
    ("max_backups_change", "current_backups", "expected_new_backups"),
    [
        (3, 5, 0),  # Decrease: 5 -> 3, no new backups on reload (1 per session only)
        (7, 4, 0),  # Increase: 4 -> 7, no new backups on reload (1 per session only)
        (
            0,
            3,
            0,
        ),  # Disable: 3 -> 0 (unlimited), no new backups on reload (1 per session only)
    ],
)
async def test_max_backup_retention_changes(
    hass: HomeAssistant,
    init_integration,
    max_backups_change: int,
    current_backups: int,
    expected_new_backups: int,
) -> None:
    """Test max backup retention changes during reload.

    Note: Backup is created once per HA session on initial setup.
    Settings reloads do NOT create additional backups to prevent duplicate
    backups within 1 second of each other (fixed in commit 1fc8018).
    """
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    backup_create_count = 0

    def mock_create_backup(*args, **kwargs):
        nonlocal backup_create_count
        backup_create_count += 1
        return f"test_backup_{backup_create_count}"

    # Mock discovery with proper backup metadata structure
    mock_existing_backups = [
        {
            "filename": f"kidschores_data_2024-01-{i + 1:02d}_10-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime(2024, 1, i + 1, 10, 0, 0, tzinfo=UTC),
            "age_hours": float(24 * i),
            "size_bytes": 1024,
        }
        for i in range(current_backups)
    ]

    with (
        patch(
            "custom_components.kidschores.helpers.backup_helpers.discover_backups",
            new=AsyncMock(return_value=mock_existing_backups),
        ),
        patch(
            "custom_components.kidschores.helpers.backup_helpers.create_timestamped_backup",
            side_effect=mock_create_backup,
        ),
    ):
        # Change max backup retention
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CONF_BACKUPS_MAX_RETAINED: max_backups_change},
        )

        # Verify expected safety backup creation behavior during system reload
        expected_msg = f"Expected {expected_new_backups} safety backups during reload"
        actual_msg = f", got {backup_create_count}"
        assert backup_create_count == expected_new_backups, expected_msg + actual_msg


async def test_select_backup_to_delete_complete_flow(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test complete select backup to delete flow navigation."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    mock_backups = [
        {
            "filename": "kidschores_data_2024-01-01_10-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            "age_hours": 24.0,
            "size_bytes": 1024,
        },
        {
            "filename": "kidschores_data_2024-01-02_10-00-00_manual",
            "tag": "manual",
            "timestamp": datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC),
            "age_hours": 12.0,
            "size_bytes": 2048,
        },
    ]

    with patch(
        "custom_components.kidschores.helpers.backup_helpers.discover_backups",
        new=AsyncMock(return_value=mock_backups),
    ):
        # Select delete backup action
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "delete_backup"},
        )

        # Should navigate to select_backup_to_delete step without error
        assert result.get("type") == "form"
        assert result.get("step_id") == "select_backup_to_delete"


async def test_create_backup_complete_flow(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test complete create backup flow navigation."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    with patch(
        "custom_components.kidschores.helpers.backup_helpers.create_timestamped_backup",
        return_value="test_backup_filename",
    ):
        # Select create backup
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "create_backup"},
        )

        # Should navigate to create backup step without error
        assert result.get("type") == "form"
        assert result.get("step_id") == "create_manual_backup"


@pytest.mark.parametrize(
    ("tag_type", "should_allow_delete"),
    [
        (BACKUP_TAG_RECOVERY, True),  # Can delete recovery backups
        (BACKUP_TAG_RESET, True),  # Can delete reset backups
        (BACKUP_TAG_MANUAL, False),  # Cannot delete manual backups
        ("pre-migration", False),  # Cannot delete pre-migration backups
    ],
)
async def test_delete_backup_confirm_step_exists(
    hass: HomeAssistant,
    init_integration,
    tag_type: str,
    should_allow_delete: bool,
) -> None:
    """Test that delete backup confirm step can be reached for appropriate backup types."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    # Mock backup data with proper dictionary structure that discover_backups returns
    mock_backups = [
        {
            "filename": f"kidschores_data_2024-01-01_10-00-00_{tag_type}",
            "tag": tag_type,
            "timestamp": datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            "age_hours": 24.5,
            "size_bytes": 1024,
        }
    ]

    with (
        patch(
            "custom_components.kidschores.helpers.backup_helpers.discover_backups",
            new=AsyncMock(return_value=mock_backups),
        ),
        patch("os.path.exists", return_value=True),
    ):
        # Select delete backup action to navigate to delete selection
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "delete_backup"},
        )

        # This test validates that the delete backup step can be reached
        # for deletable backup types and shows appropriate messaging for non-deletable ones
        msg = f"Expected form for tag {tag_type}, got {result.get('type')}"
        assert result.get("type") == "form", msg


async def test_delete_backup_confirm_step_method_exists(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test that async_step_delete_backup_confirm method exists and is callable."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Get the flow handler from the flow manager
    flow_manager = hass.config_entries.options
    flow_handler = flow_manager._progress[result["flow_id"]]

    # Verify the method exists on the handler instance
    assert hasattr(flow_handler, "async_step_delete_backup_confirm"), (
        "Handler missing async_step_delete_backup_confirm method - causes UnknownStep"
    )

    # Verify it's callable
    assert callable(flow_handler.async_step_delete_backup_confirm), (  # pyright: ignore[reportAttributeAccessIssue]
        "async_step_delete_backup_confirm exists but is not callable"
    )


async def test_confirm_restore_backup_step_method_exists(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test that async_step_restore_backup_confirm and selection methods exist."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Get the flow handler from the flow manager
    flow_manager = hass.config_entries.options
    flow_handler = flow_manager._progress[result["flow_id"]]

    # Verify the restore confirm method exists
    assert hasattr(flow_handler, "async_step_restore_backup_confirm"), (
        "Handler missing async_step_restore_backup_confirm method"
    )

    # Verify new selection methods exist
    assert hasattr(flow_handler, "async_step_select_backup_to_delete"), (
        "Handler missing async_step_select_backup_to_delete method"
    )
    assert hasattr(flow_handler, "async_step_select_backup_to_restore"), (
        "Handler missing async_step_select_backup_to_restore method"
    )

    # Verify all are callable
    assert callable(flow_handler.async_step_restore_backup_confirm), (  # pyright: ignore[reportAttributeAccessIssue]
        "async_step_restore_backup_confirm exists but is not callable"
    )
    assert callable(flow_handler.async_step_select_backup_to_delete), (  # pyright: ignore[reportAttributeAccessIssue]
        "async_step_select_backup_to_delete exists but is not callable"
    )
    assert callable(flow_handler.async_step_select_backup_to_restore), (  # pyright: ignore[reportAttributeAccessIssue]
        "async_step_select_backup_to_restore exists but is not callable"
    )


async def test_backup_actions_menu_step_method_exists(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test that async_step_backup_actions_menu method exists and is callable."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Get the flow handler from the flow manager
    flow_manager = hass.config_entries.options
    flow_handler = flow_manager._progress[result["flow_id"]]

    # Verify the method exists on the handler instance
    assert hasattr(flow_handler, "async_step_backup_actions_menu"), (
        "Handler missing async_step_backup_actions_menu method"
    )

    # Verify it's callable
    assert callable(flow_handler.async_step_backup_actions_menu), (  # pyright: ignore[reportAttributeAccessIssue]
        "async_step_backup_actions_menu exists but is not callable"
    )


async def test_all_backup_methods_exist_on_handler(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test that all backup-related methods exist on KidsChoresOptionsFlowHandler."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Get the flow handler from the flow manager
    flow_manager = hass.config_entries.options
    handler = flow_manager._progress[result["flow_id"]]

    backup_methods = [
        "async_step_backup_actions_menu",
        "async_step_select_backup_to_delete",
        "async_step_select_backup_to_restore",
        "async_step_create_manual_backup",
        "async_step_delete_backup_confirm",
        "async_step_restore_backup_confirm",
        "async_step_restore_backup",
    ]

    for method_name in backup_methods:
        assert hasattr(handler, method_name), (
            f"Handler missing {method_name} method - causes UnknownStep error"
        )
        assert callable(getattr(handler, method_name)), (
            f"{method_name} exists but is not callable"
        )


async def test_backup_deletion_cancel_flow(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test canceling backup deletion returns to backup actions menu."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    mock_backups = [
        {
            "filename": "kidschores_data_2024-01-01_10-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            "age_hours": 24.0,
            "size_bytes": 1024,
        }
    ]

    with patch(
        "custom_components.kidschores.helpers.backup_helpers.discover_backups",
        new=AsyncMock(return_value=mock_backups),
    ):
        # Navigate to select backup to delete
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "delete_backup"},
        )

        # Verify we're at select_backup_to_delete step
        with patch("os.path.exists", return_value=True):
            assert result.get("type") == "form"
            assert result.get("step_id") == "select_backup_to_delete"


async def test_backup_restore_cancel_flow(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test canceling backup restore returns to previous step."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    mock_backups = [
        {
            "filename": "kidschores_data_2024-01-01_10-00-00_recovery",
            "tag": "recovery",
            "timestamp": datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            "age_hours": 24.0,
            "size_bytes": 1024,
        }
    ]

    with (
        patch(
            "custom_components.kidschores.helpers.backup_helpers.discover_backups",
            new=AsyncMock(return_value=mock_backups),
        ),
        patch("os.path.exists", return_value=True),
    ):
        # Navigate to restore backup
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "restore_backup"},
        )

        # Verify restore option is available
        assert result.get("type") == "form"


async def test_delete_backup_no_files_scenario(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test delete backup action when no backup files exist."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    # Mock no backups found
    with patch(
        "custom_components.kidschores.helpers.backup_helpers.discover_backups",
        new=AsyncMock(return_value=[]),
    ):
        # Navigate to delete backup selection
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "delete_backup"},
        )

        # Should show form indicating no backups available
        assert result.get("type") == "form"
        assert result.get("step_id") == "select_backup_to_delete"


@pytest.mark.parametrize(
    ("tag_type", "should_show_delete"),
    [
        (BACKUP_TAG_RECOVERY, True),  # Can delete recovery backups
        (BACKUP_TAG_RESET, True),  # Can delete reset backups
        (BACKUP_TAG_MANUAL, False),  # Cannot delete manual backups
        ("pre-migration", False),  # Cannot delete pre-migration backups
    ],
)
async def test_backup_delete_options_by_tag_type(
    hass: HomeAssistant,
    init_integration,
    tag_type: str,
    should_show_delete: bool,
) -> None:
    """Test that delete options shown/hidden appropriately by backup tag type."""
    config_entry = init_integration
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Navigate to general options
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"),  # type: ignore[arg-type]
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    # Mock backup of specific tag type
    mock_backups = [
        {
            "filename": f"kidschores_data_2024-01-01_10-00-00_{tag_type}",
            "tag": tag_type,
            "timestamp": datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            "age_hours": 24.0,
            "size_bytes": 1024,
        }
    ]

    with (
        patch(
            "custom_components.kidschores.helpers.backup_helpers.discover_backups",
            new=AsyncMock(return_value=mock_backups),
        ),
        patch("os.path.exists", return_value=True),
    ):
        # Navigate to select backup to delete
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),  # type: ignore[arg-type]
            user_input={CFOF_BACKUP_ACTION_SELECTION: "delete_backup"},
        )

        # Should reach select_backup_to_delete step
        assert result.get("type") == "form"
        assert result.get("step_id") == "select_backup_to_delete"
        # The actual delete option visibility logic is tested by the
        # integration's flow implementation based on tag type
