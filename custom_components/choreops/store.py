# File: store.py
"""Handles persistent data storage for the ChoreOps integration.

Uses Home Assistant's Storage helper to save and load chore-related data, ensuring
the state is preserved across restarts. This includes data for users, chores,
badges, rewards, penalties, and their statuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from . import const

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class ChoreOpsStore:
    """Handles persistent storage operations for ChoreOps data.

    Thin wrapper around Home Assistant's Store API for loading, saving, and
    accessing ChoreOps data. Utilizes internal_id as the primary key for all entities.
    """

    def __init__(
        self, hass: HomeAssistant, storage_key: str = const.STORAGE_KEY
    ) -> None:
        """Initialize the store.

        Args:
            hass: Home Assistant core object.
            storage_key: Key to identify storage location (default: const.STORAGE_KEY).

        """
        self.hass = hass
        self._storage_key = storage_key
        scoped_storage_key = f"{const.STORAGE_DIRECTORY}/{storage_key}"
        self._store: Store = Store(hass, const.STORAGE_VERSION, scoped_storage_key)
        self._data: dict[str, Any] = {}  # In-memory data cache for quick access.

    @staticmethod
    def get_default_structure() -> dict[str, Any]:
        """Return canonical empty data structure for fresh installations.

        This is the SINGLE SOURCE OF TRUTH for ChoreOps storage schema.
        Used by:
        - Store.async_initialize() when no storage file exists
        - ConfigFlow._create_entry() when creating fresh installation
        - Coordinator._get_default_structure() delegates here

        Returns:
            dict: Default structure with all buckets and meta initialized.
        """
        return {
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA5,
                const.DATA_META_PENDING_EVALUATIONS: [],
                const.DATA_META_LAST_MIDNIGHT_PROCESSED: None,
            },
            const.DATA_USERS: {},
            const.DATA_CHORES: {},
            const.DATA_BADGES: {},
            const.DATA_REWARDS: {},
            const.DATA_PENALTIES: {},
            const.DATA_BONUSES: {},
            const.DATA_ACHIEVEMENTS: {},
            const.DATA_CHALLENGES: {},
            const.DATA_NOTIFICATIONS: {},  # Chore notification timestamps (v0.5.0+)
        }

    async def async_initialize(self) -> None:
        """Load data from storage during startup.

        If no data exists, initializes with an empty structure.
        """
        const.LOGGER.debug("DEBUG: ChoreOpsStore: Loading data from storage")
        existing_data = await self._store.async_load()

        # DEBUG: Check what async_load returned
        if existing_data:
            const.LOGGER.debug(
                "DEBUG: async_load() returned keys: %s", list(existing_data.keys())[:5]
            )

        if existing_data is None:
            # Try legacy storage keys before creating default structure.
            from . import migration_pre_v50 as mp50

            legacy_keys = [
                mp50.LEGACY_STORAGE_KEY,
            ]
            for legacy_key in legacy_keys:
                legacy_store: Store = Store(
                    self.hass,
                    const.STORAGE_VERSION,
                    legacy_key,
                )
                legacy_data = await legacy_store.async_load()
                if legacy_data is not None:
                    self._data = legacy_data
                    await self._store.async_save(self._data)
                    const.LOGGER.info(
                        "INFO: Migrated legacy storage key %s into %s",
                        legacy_key,
                        f"{const.STORAGE_DIRECTORY}/{self._storage_key}",
                    )
                    return

            # No existing data, create a new default structure.
            const.LOGGER.info("INFO: No existing storage found. Initializing new data")
            self._data = ChoreOpsStore.get_default_structure()
            const.LOGGER.debug(
                "DEBUG: Initialized with default structure: %s keys",
                len(self._data.keys()),
            )
        else:
            # Load existing data into memory.
            self._data = existing_data
            const.LOGGER.debug(
                "DEBUG: Loaded existing data from storage: %s entities",
                {
                    "users": len(self._data.get(const.DATA_USERS, {})),
                    "chores": len(self._data.get(const.DATA_CHORES, {})),
                    "badges": len(self._data.get(const.DATA_BADGES, {})),
                    "rewards": len(self._data.get(const.DATA_REWARDS, {})),
                    "penalties": len(self._data.get(const.DATA_PENALTIES, {})),
                    "bonuses": len(self._data.get(const.DATA_BONUSES, {})),
                    "achievements": len(self._data.get(const.DATA_ACHIEVEMENTS, {})),
                    "challenges": len(self._data.get(const.DATA_CHALLENGES, {})),
                    "total_keys": len(self._data.keys()),
                },
            )

    @property
    def data(self) -> dict[str, Any]:
        """Retrieve the in-memory data cache."""
        const.LOGGER.debug(
            "DEBUG: Storage manager data property accessed: %s entities",
            {
                "users": len(self._data.get(const.DATA_USERS, {})),
                "chores": len(self._data.get(const.DATA_CHORES, {})),
                "badges": len(self._data.get(const.DATA_BADGES, {})),
                "rewards": len(self._data.get(const.DATA_REWARDS, {})),
                "penalties": len(self._data.get(const.DATA_PENALTIES, {})),
                "bonuses": len(self._data.get(const.DATA_BONUSES, {})),
                "achievements": len(self._data.get(const.DATA_ACHIEVEMENTS, {})),
                "challenges": len(self._data.get(const.DATA_CHALLENGES, {})),
                "total_keys": len(self._data.keys()),
            },
        )
        return self._data

    def get_storage_path(self) -> str:
        """Get the storage file path.

        Returns:
            str: The absolute path to the storage file.
        """
        return self._store.path

    def set_data(self, new_data: dict[str, Any]) -> None:
        """Replace the entire in-memory data structure."""
        const.LOGGER.debug(
            "DEBUG: Storage manager set_data called with: %s entities",
            {
                "users": len(new_data.get(const.DATA_USERS, {})),
                "chores": len(new_data.get(const.DATA_CHORES, {})),
                "badges": len(new_data.get(const.DATA_BADGES, {})),
                "rewards": len(new_data.get(const.DATA_REWARDS, {})),
                "penalties": len(new_data.get(const.DATA_PENALTIES, {})),
                "bonuses": len(new_data.get(const.DATA_BONUSES, {})),
                "achievements": len(new_data.get(const.DATA_ACHIEVEMENTS, {})),
                "challenges": len(new_data.get(const.DATA_CHALLENGES, {})),
                "total_keys": len(new_data.keys()),
            },
        )
        self._data = new_data

    async def async_save(self) -> None:
        """Save the current data structure to storage asynchronously.

        Raises:
            No exceptions raised - errors are logged but do not stop execution.
            OSError: Logged when file system issues prevent saving.
            TypeError: Logged when data contains non-serializable types.
            ValueError: Logged when data is invalid for JSON serialization.
        """
        try:
            await self._store.async_save(self._data)
            const.LOGGER.debug("DEBUG: Data saved successfully to storage")
        except OSError as err:
            const.LOGGER.error(
                "ERROR: Failed to save storage due to file system error: %s. "
                "Check disk space and file permissions for %s",
                err,
                self._store.path,
            )
        except TypeError as err:
            const.LOGGER.error(
                "ERROR: Failed to save storage due to non-serializable data: %s. "
                "Data contains types that cannot be converted to JSON",
                err,
            )
        except ValueError as err:
            const.LOGGER.error(
                "ERROR: Failed to save storage due to invalid data format: %s. "
                "Data structure may be corrupted",
                err,
            )

    async def async_clear_data(self) -> None:
        """Clear all stored data and reset to default structure."""

        const.LOGGER.warning(
            "WARNING: Clearing all ChoreOps data and resetting storage"
        )
        # Completely clear any existing data.
        self._data.clear()

        # Set the default empty structure
        self._data = ChoreOpsStore.get_default_structure()
        await self.async_save()

    async def async_delete_storage(self) -> None:
        """Delete the storage file completely from disk.

        This clears all in-memory data and removes the storage file using
        Home Assistant's Store API for proper file handling.
        """
        # First clear in-memory data
        await self.async_clear_data()

        # Remove the file using Store API
        try:
            await self._store.async_remove()
            const.LOGGER.info(
                "INFO: Storage file removed successfully: %s",
                self._store.path,
            )
        except OSError as err:
            const.LOGGER.error(
                "ERROR: Failed to remove storage file %s: %s. Check file permissions",
                self._store.path,
                err,
            )

    async def async_update_data(self, key: str, value: Any) -> None:
        """Update a specific section of the data structure.

        Args:
            key: The data key to update (e.g., const.DATA_ASSIGNEES, const.DATA_CHORES).
            value: The new value for the specified key.

        Note:
            If the key doesn't exist, a warning is logged and no update occurs.
            Valid keys are defined in const.py (DATA_ASSIGNEES, DATA_CHORES, etc.).
        """
        if key in self._data:
            const.LOGGER.debug("DEBUG: Updating data for key: %s", key)
            self._data[key] = value
            await self.async_save()
        else:
            const.LOGGER.warning(
                "WARNING: Attempted to update unknown data key '%s'. Valid keys: %s",
                key,
                ", ".join(self._data.keys()),
            )
