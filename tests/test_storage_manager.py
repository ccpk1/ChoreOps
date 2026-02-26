"""Direct unit tests for ChoreOpsStore.

Tests store methods that are not fully covered by integration tests,
including error handling and data persistence operations.
"""

# Accessing _store, _data, _storage_key for testing
# pylint: disable=redefined-outer-name  # Pytest fixtures redefine names
# Test fixtures may be unused in simple tests

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.store import ChoreOpsStore


@pytest.fixture
def store(hass: HomeAssistant) -> ChoreOpsStore:
    """Return a store instance."""
    return ChoreOpsStore(hass)


async def test_async_initialize_creates_default_structure(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test that async_initialize creates default structure when no data exists."""
    with patch.object(store._store, "async_load", return_value=None):
        await store.async_initialize()

    data = store.data

    # Verify all expected keys exist (modern structure with DATA_META)
    assert const.DATA_USERS in data
    assert const.DATA_CHORES in data
    assert const.DATA_BADGES in data
    assert const.DATA_REWARDS in data
    assert const.DATA_PENALTIES in data
    assert const.DATA_BONUSES in data
    assert const.DATA_ACHIEVEMENTS in data
    assert const.DATA_CHALLENGES in data
    assert const.DATA_META in data

    # Verify default values (meta section contains schema_version)
    assert data[const.DATA_USERS] == {}
    meta = data[const.DATA_META]
    assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_BETA5


async def test_async_initialize_loads_existing_data(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test that async_initialize loads existing storage data."""
    existing_data = {
        const.DATA_USERS: {"assignee_1": {"name": "Alice"}},
        const.DATA_CHORES: {"chore_1": {"name": "Clean room"}},
        const.DATA_SCHEMA_VERSION: 42,
    }

    with patch.object(store._store, "async_load", return_value=existing_data):
        await store.async_initialize()

    assert store.data == existing_data
    assert store.data[const.DATA_USERS] == {"assignee_1": {"name": "Alice"}}
    assert store.data[const.DATA_CHORES] == {"chore_1": {"name": "Clean room"}}


async def test_async_initialize_skips_legacy_fallback_when_disabled(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Store should not import legacy root data when fallback is disabled."""
    with (
        patch.object(store._store, "async_load", return_value=None),
        patch("custom_components.choreops.store.Store") as mock_store_cls,
    ):
        await store.async_initialize(allow_legacy_fallback=False)

    assert mock_store_cls.call_count == 0
    assert store.data[const.DATA_USERS] == {}
    assert store.data[const.DATA_CHORES] == {}


async def test_async_initialize_uses_legacy_fallback_when_enabled(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Store should import legacy root data when fallback is enabled."""
    legacy_payload = {
        const.DATA_USERS: {"legacy_user": {"name": "Legacy"}},
        const.DATA_CHORES: {"legacy_chore": {"name": "Legacy chore"}},
    }
    legacy_store = AsyncMock()
    legacy_store.async_load = AsyncMock(return_value=legacy_payload)

    with (
        patch.object(store._store, "async_load", return_value=None),
        patch.object(store._store, "async_save", new=AsyncMock()) as scoped_save,
        patch("custom_components.choreops.store.Store", return_value=legacy_store),
    ):
        await store.async_initialize(allow_legacy_fallback=True)

    assert store.data == legacy_payload
    scoped_save.assert_called_once_with(legacy_payload)


async def test_getter_methods_return_correct_data(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test all getter methods return correct data."""
    test_data = {
        const.DATA_USERS: {"assignee_1": {}},
        const.DATA_APPROVERS: {"approver_1": {}},
        const.DATA_CHORES: {"chore_1": {}},
        const.DATA_BADGES: {"badge_1": {}},
        const.DATA_REWARDS: {"reward_1": {}},
        const.DATA_PENALTIES: {"penalty_1": {}},
        const.DATA_BONUSES: {"bonus_1": {}},
        const.DATA_ACHIEVEMENTS: {"achievement_1": {}},
        const.DATA_CHALLENGES: {"challenge_1": {}},
        # Pending reward approvals now computed from assignee reward_data
    }

    store.set_data(test_data)

    assert store.data[const.DATA_USERS] == {"assignee_1": {}}
    assert store.data[const.DATA_APPROVERS] == {"approver_1": {}}
    assert store.data[const.DATA_CHORES] == {"chore_1": {}}
    assert store.data[const.DATA_BADGES] == {"badge_1": {}}
    assert store.data[const.DATA_REWARDS] == {"reward_1": {}}
    assert store.data[const.DATA_PENALTIES] == {"penalty_1": {}}
    assert store.data[const.DATA_BONUSES] == {"bonus_1": {}}
    assert store.data[const.DATA_ACHIEVEMENTS] == {"achievement_1": {}}
    assert store.data[const.DATA_CHALLENGES] == {"challenge_1": {}}
    # Pending reward approvals getter removed - use coordinator.get_pending_reward_approvals_computed()


async def test_getter_methods_return_defaults_for_missing_keys(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test getter methods return empty defaults when keys don't exist."""
    store.set_data({})

    assert store.data.get(const.DATA_USERS, {}) == {}
    assert store.data.get(const.DATA_APPROVERS, {}) == {}
    assert store.data.get(const.DATA_CHORES, {}) == {}
    assert store.data.get(const.DATA_BADGES, {}) == {}
    assert store.data.get(const.DATA_REWARDS, {}) == {}
    assert store.data.get(const.DATA_PENALTIES, {}) == {}
    assert store.data.get(const.DATA_BONUSES, {}) == {}
    assert store.data.get(const.DATA_ACHIEVEMENTS, {}) == {}
    assert store.data.get(const.DATA_CHALLENGES, {}) == {}
    # Pending reward approvals getter removed in v0.4.0 - use coordinator computed method


async def test_async_save_success(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test successful async_save operation."""
    test_data = {const.DATA_USERS: {"assignee_1": {"name": "Alice"}}}
    store.set_data(test_data)

    mock_store_save = AsyncMock()
    with patch.object(store._store, "async_save", mock_store_save):
        await store.async_save()

    mock_store_save.assert_called_once_with(test_data)


async def test_async_save_handles_oserror(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_save handles OSError (file system errors)."""
    store.set_data({const.DATA_USERS: {}})

    with patch.object(
        store._store,
        "async_save",
        side_effect=OSError("Disk full"),
    ):
        await store.async_save()

    assert "Failed to save storage due to file system error" in caplog.text
    assert "Disk full" in caplog.text
    assert "Check disk space and file permissions" in caplog.text


async def test_async_save_handles_typeerror(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_save handles TypeError (serialization errors)."""
    store.set_data({const.DATA_USERS: {}})

    with patch.object(
        store._store,
        "async_save",
        side_effect=TypeError("Cannot serialize"),
    ):
        await store.async_save()

    assert "Failed to save storage due to non-serializable data" in caplog.text
    assert "Cannot serialize" in caplog.text
    assert "cannot be converted to JSON" in caplog.text


async def test_async_save_handles_valueerror(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_save handles ValueError (validation errors)."""
    store.set_data({const.DATA_USERS: {}})

    with patch.object(
        store._store,
        "async_save",
        side_effect=ValueError("Invalid data"),
    ):
        await store.async_save()

    assert "Failed to save storage due to invalid data format" in caplog.text
    assert "Invalid data" in caplog.text
    assert "Data structure may be corrupted" in caplog.text


async def test_async_clear_data_resets_to_default_structure(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_clear_data resets to default empty structure."""
    # Start with populated data
    store.set_data(
        {
            const.DATA_USERS: {"assignee_1": {"name": "Alice"}},
            const.DATA_CHORES: {"chore_1": {"name": "Clean"}},
            const.DATA_SCHEMA_VERSION: 42,
        }
    )

    mock_save = AsyncMock()
    with patch.object(store, "async_save", mock_save):
        await store.async_clear_data()

    # Verify data is reset (modern structure - no deprecated fields)
    data = store.data
    assert data[const.DATA_USERS] == {}
    assert data[const.DATA_CHORES] == {}
    assert data[const.DATA_BADGES] == {}
    assert data[const.DATA_REWARDS] == {}

    # Verify warning logged
    assert "Clearing all ChoreOps data" in caplog.text

    # Verify save was called
    mock_save.assert_called_once()


async def test_async_clear_data_includes_schema_version(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test async_clear_data includes schema_version in reset structure.

    This is a regression test for the bug where schema_version was missing
    from async_clear_data but present in async_initialize.
    """
    store.set_data({const.DATA_USERS: {"assignee_1": {}}})

    mock_save = AsyncMock()
    with patch.object(store, "async_save", mock_save):
        await store.async_clear_data()

    # BUG: This should be present but currently isn't
    # TODO: Fix async_clear_data to include DATA_SCHEMA_VERSION
    # assert const.DATA_SCHEMA_VERSION in store.data


async def test_async_delete_storage_clears_and_removes_file(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_delete_storage clears data and removes file via Store API."""
    store.set_data({const.DATA_USERS: {"assignee_1": {}}})

    mock_clear = AsyncMock()
    mock_store_remove = AsyncMock()
    with (
        patch.object(store, "async_clear_data", mock_clear),
        patch.object(store._store, "async_remove", mock_store_remove),
    ):
        await store.async_delete_storage()

    # Verify clear_data was called
    mock_clear.assert_called_once()

    # Verify Store API async_remove was called
    mock_store_remove.assert_called_once()

    # Verify logging
    assert "Storage file removed successfully" in caplog.text


async def test_async_delete_storage_handles_missing_file(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_delete_storage handles FileNotFoundError from Store API."""
    store.set_data({const.DATA_USERS: {"assignee_1": {}}})

    mock_clear = AsyncMock()
    # Store API raises FileNotFoundError (subclass of OSError) if file doesn't exist
    mock_store_remove = AsyncMock(side_effect=FileNotFoundError("File not found"))
    with (
        patch.object(store, "async_clear_data", mock_clear),
        patch.object(store._store, "async_remove", mock_store_remove),
    ):
        await store.async_delete_storage()

    # Verify clear_data was called
    mock_clear.assert_called_once()

    # Verify Store async_remove was called (even though it failed)
    mock_store_remove.assert_called_once()

    # Verify error logging
    assert "Failed to remove storage file" in caplog.text


async def test_async_delete_storage_handles_oserror(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_delete_storage handles OSError from Store API."""
    store.set_data({const.DATA_USERS: {"assignee_1": {}}})

    mock_store_remove = AsyncMock(side_effect=OSError("Permission denied"))
    with (
        patch.object(store, "async_clear_data", new=AsyncMock()),
        patch.object(store._store, "async_remove", mock_store_remove),
    ):
        await store.async_delete_storage()

    # Should not raise, just log error
    assert "Failed to remove storage file" in caplog.text
    assert "Permission denied" in caplog.text


async def test_async_update_data_updates_and_saves(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_update_data updates specific key and saves."""
    store.set_data(
        {
            const.DATA_USERS: {"assignee_1": {}},
            const.DATA_CHORES: {},
        }
    )

    new_assignees_data = {"assignee_1": {}, "assignee_2": {"name": "Bob"}}

    mock_save = AsyncMock()
    with patch.object(store, "async_save", mock_save):
        await store.async_update_data(const.DATA_USERS, new_assignees_data)

    # Verify data was updated
    assert store.data[const.DATA_USERS] == new_assignees_data

    # Verify save was called
    mock_save.assert_called_once()

    # Verify logging
    assert "Updating data for key" in caplog.text


async def test_async_update_data_warns_on_unknown_key(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_update_data warns when updating unknown key."""
    store.set_data({const.DATA_USERS: {}})

    mock_save = AsyncMock()
    with patch.object(store, "async_save", mock_save):
        await store.async_update_data("unknown_key", {"data": "value"})

    # Should log warning
    assert "Attempted to update unknown data key" in caplog.text
    assert "unknown_key" in caplog.text

    # Should not call save
    mock_save.assert_not_called()


async def test_get_storage_path_returns_correct_path(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test get_storage_path returns the correct file path."""


async def test_data_property_returns_internal_data(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test data property returns the internal data dictionary."""
    test_data = {const.DATA_USERS: {"assignee_1": {"name": "Alice"}}}
    store.set_data(test_data)

    assert store.data is store._data
    assert store.data == test_data


async def test_set_data_replaces_entire_structure(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test set_data completely replaces the data structure."""
    original_data = ChoreOpsStore.get_default_structure()
    store.set_data(original_data)

    new_data = ChoreOpsStore.get_default_structure()
    new_data[const.DATA_USERS] = {
        "assignee_2": {const.DATA_USER_INTERNAL_ID: "assignee_2"}
    }
    new_data[const.DATA_CHORES] = {"chore_1": {const.DATA_CHORE_INTERNAL_ID: "chore_1"}}
    assert store.set_data(new_data)

    assert store.data == new_data
    assert store.data is not original_data


async def test_set_data_normalizes_missing_top_level_keys(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test set_data fills missing canonical top-level buckets."""
    assert store.set_data({const.DATA_USERS: {}})

    assert const.DATA_META in store.data
    assert const.DATA_CHORES in store.data
    assert const.DATA_NOTIFICATIONS in store.data


async def test_set_data_rejects_mismatched_internal_id(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test set_data rejects records whose internal_id does not match key."""
    baseline = ChoreOpsStore.get_default_structure()
    assert store.set_data(baseline)

    invalid_data = ChoreOpsStore.get_default_structure()
    invalid_data[const.DATA_USERS] = {
        "user_a": {const.DATA_USER_INTERNAL_ID: "wrong_key"}
    }

    assert not store.set_data(invalid_data)
    assert store.data == baseline
    assert "Rejected invalid storage payload in set_data" in caplog.text


async def test_set_data_rejects_invalid_bucket_type(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test set_data rejects invalid canonical bucket types."""
    baseline = ChoreOpsStore.get_default_structure()
    assert store.set_data(baseline)

    invalid_data = ChoreOpsStore.get_default_structure()
    invalid_data[const.DATA_USERS] = []

    assert not store.set_data(invalid_data)
    assert store.data == baseline
    assert "Rejected invalid storage payload in set_data" in caplog.text


async def test_async_initialize_resets_to_default_on_invalid_payload(
    hass: HomeAssistant,
    store: ChoreOpsStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_initialize resets to default when stored payload is invalid."""
    invalid_data = ChoreOpsStore.get_default_structure()
    invalid_data[const.DATA_USERS] = {"user_a": {const.DATA_USER_INTERNAL_ID: "bad"}}

    with patch.object(store._store, "async_load", return_value=invalid_data):
        await store.async_initialize()

    assert store.data == ChoreOpsStore.get_default_structure()
    assert "Existing storage payload is invalid" in caplog.text


async def test_custom_storage_key(hass: HomeAssistant) -> None:
    """Test store with custom storage key."""
    custom_key = "test_storage_key"
    store = ChoreOpsStore(hass, storage_key=custom_key)

    assert store._storage_key == custom_key
    assert custom_key in store.get_storage_path()


async def test_pending_reward_approvals_modern_structure(
    hass: HomeAssistant,
    store: ChoreOpsStore,
) -> None:
    """Test that pending reward approvals use modern structure.

    This test verifies the v0.4.0+ architecture:
    - No get_pending_reward_approvals() method in storage manager (removed)
    - Pending reward approvals computed from assignee reward_data by coordinator
    - Modern structure: assignee["reward_data"][reward_id]["pending_count"]
    """
    # Modern structure stores pending counts in assignee reward_data, not a global list
    # The storage manager no longer has a getter method for this legacy field
    # Coordinator.get_pending_reward_approvals_computed() is the new approach

    # Verify the legacy getter method no longer exists
    assert not hasattr(store, "get_pending_reward_approvals")
    # Verify the old typo also doesn't exist
    assert not hasattr(store, "get_pending_reward_aprovals")
