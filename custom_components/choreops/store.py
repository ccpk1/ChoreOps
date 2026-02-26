# File: store.py
"""Handles persistent data storage for the ChoreOps integration.

Uses Home Assistant's Storage helper to save and load chore-related data, ensuring
the state is preserved across restarts. This includes data for users, chores,
badges, rewards, penalties, and their statuses.
"""

from __future__ import annotations

from pathlib import Path
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

    @staticmethod
    def get_entity_bucket_keys() -> tuple[str, ...]:
        """Return canonical entity bucket keys for payload checks and migrations."""
        excluded_keys = {const.DATA_META, const.DATA_NOTIFICATIONS}
        return tuple(
            key
            for key in ChoreOpsStore.get_default_structure()
            if key not in excluded_keys
        )

    @staticmethod
    def has_entity_payload_in_data(data: dict[str, Any]) -> bool:
        """Return True when any canonical entity bucket in data is non-empty."""
        return any(
            bool(data.get(bucket)) for bucket in ChoreOpsStore.get_entity_bucket_keys()
        )

    def has_entity_payload(self) -> bool:
        """Return True when this store currently has any entity payload."""
        return ChoreOpsStore.has_entity_payload_in_data(self._data)

    def is_entity_payload_empty(self) -> bool:
        """Return True when all canonical entity buckets are empty."""
        return not self.has_entity_payload()

    async def async_adopt_data_if_empty(self, source_data: dict[str, Any]) -> bool:
        """Adopt source data only when source has entities and current store is empty."""
        if not ChoreOpsStore.has_entity_payload_in_data(source_data):
            return False

        if not self.is_entity_payload_empty():
            return False

        self.set_data(dict(source_data))
        await self.async_save()
        return True

    async def async_find_latest_pending_storage_key(self) -> str | None:
        """Find the most recent pending flow storage key from disk."""
        storage_dir = Path(self.hass.config.path(".storage", const.STORAGE_DIRECTORY))
        storage_root = Path(self.hass.config.path(".storage"))
        pending_pattern = f"{const.STORAGE_KEY}_pending_*"

        def _scan_pending_storage_key() -> str | None:
            pending_candidates: list[Path] = []

            if storage_dir.exists():
                pending_candidates.extend(storage_dir.glob(pending_pattern))

            if storage_root.exists():
                pending_candidates.extend(storage_root.glob(pending_pattern))
                pending_candidates.extend(storage_root.glob(f"**/{pending_pattern}"))

            pending_candidates = sorted(
                pending_candidates,
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )

            if not pending_candidates:
                return None

            return pending_candidates[0].name

        return await self.hass.async_add_executor_job(_scan_pending_storage_key)

    async def async_initialize(self, *, allow_legacy_fallback: bool = True) -> None:
        """Load data from storage during startup.

        If no data exists, initializes with an empty structure.

        Args:
            allow_legacy_fallback: When True, attempts one-time import from
                legacy root storage keys if scoped storage is missing. For
                additional config entries this should be False to prevent
                unintended data cloning across instances.
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
            if allow_legacy_fallback:
                from . import migration_pre_v50 as mp50

                legacy_keys = [
                    mp50.LEGACY_STORAGE_KEY,
                    mp50.LEGACY_STORAGE_KEY_TRANSITIONAL,
                ]
                for legacy_key in legacy_keys:
                    legacy_store: Store = Store(
                        self.hass,
                        const.STORAGE_VERSION,
                        legacy_key,
                    )
                    legacy_data = await legacy_store.async_load()
                    if legacy_data is not None:
                        if not self.set_data(legacy_data):
                            const.LOGGER.error(
                                "ERROR: Legacy storage payload from %s is invalid; initializing defaults",
                                legacy_key,
                            )
                            self._data = ChoreOpsStore.get_default_structure()
                            return
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
            if not self.set_data(existing_data):
                const.LOGGER.error(
                    "ERROR: Existing storage payload is invalid; resetting to default structure"
                )
                self._data = ChoreOpsStore.get_default_structure()
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

    @property
    def storage_key(self) -> str:
        """Return the resolved storage key for this store instance."""
        return self._storage_key

    def get_storage_path(self) -> str:
        """Get the storage file path.

        Returns:
            str: The absolute path to the storage file.
        """
        return self._store.path

    @staticmethod
    def _get_entity_internal_id_map() -> dict[str, str]:
        """Return entity bucket to required internal id field mapping."""
        return {
            const.DATA_USERS: const.DATA_USER_INTERNAL_ID,
            const.DATA_CHORES: const.DATA_CHORE_INTERNAL_ID,
            const.DATA_BADGES: const.DATA_BADGE_INTERNAL_ID,
            const.DATA_REWARDS: const.DATA_REWARD_INTERNAL_ID,
            const.DATA_PENALTIES: const.DATA_PENALTY_INTERNAL_ID,
            const.DATA_BONUSES: const.DATA_BONUS_INTERNAL_ID,
            const.DATA_ACHIEVEMENTS: const.DATA_ACHIEVEMENT_INTERNAL_ID,
            const.DATA_CHALLENGES: const.DATA_CHALLENGE_INTERNAL_ID,
        }

    @staticmethod
    def _extract_schema_version(data: dict[str, Any]) -> int | None:
        """Extract schema version from modern or legacy metadata fields."""
        schema_value = data.get(const.DATA_SCHEMA_VERSION)
        if isinstance(schema_value, int):
            return schema_value

        meta_section = data.get(const.DATA_META)
        if isinstance(meta_section, dict):
            schema_value = meta_section.get(const.DATA_META_SCHEMA_VERSION)
            if isinstance(schema_value, int):
                return schema_value

        return None

    @staticmethod
    def _normalize_and_validate_data(
        new_data: dict[str, Any],
    ) -> tuple[bool, dict[str, Any], str | None]:
        """Normalize and validate payload before replacing in-memory store data."""
        default_structure = ChoreOpsStore.get_default_structure()
        normalized_data = dict(new_data)

        # Validate canonical top-level key types.
        for key, default_value in default_structure.items():
            if key not in normalized_data:
                continue

            value = normalized_data.get(key)
            if not isinstance(value, type(default_value)):
                return (
                    False,
                    normalized_data,
                    (
                        f"Top-level key '{key}' has invalid type "
                        f"{type(value).__name__}; expected {type(default_value).__name__}"
                    ),
                )

        # Legacy payloads (pre-storage-only) are accepted.
        schema_version = ChoreOpsStore._extract_schema_version(normalized_data)
        if (
            schema_version is not None
            and schema_version < const.SCHEMA_VERSION_STORAGE_ONLY
        ):
            return True, normalized_data, None

        # Unknown schema payloads are accepted for backward compatibility.
        if schema_version is None:
            return True, normalized_data, None

        # Validate canonical entity buckets for obvious corruption.
        for (
            bucket_key,
            internal_id_key,
        ) in ChoreOpsStore._get_entity_internal_id_map().items():
            if bucket_key not in normalized_data:
                continue

            bucket_value = normalized_data.get(bucket_key)
            if not isinstance(bucket_value, dict):
                return (
                    False,
                    normalized_data,
                    (
                        f"Entity bucket '{bucket_key}' has invalid type "
                        f"{type(bucket_value).__name__}; expected dict"
                    ),
                )

            for item_key, item_value in bucket_value.items():
                if not isinstance(item_value, dict):
                    return (
                        False,
                        normalized_data,
                        (
                            f"Entity bucket '{bucket_key}' item '{item_key}' "
                            "must be a dict"
                        ),
                    )

                internal_id_value = item_value.get(internal_id_key)
                if not isinstance(internal_id_value, str) or not internal_id_value:
                    item_value[internal_id_key] = item_key
                    continue

                if internal_id_value != item_key:
                    item_value[internal_id_key] = item_key

        return True, normalized_data, None

    def set_data(self, new_data: dict[str, Any]) -> bool:
        """Replace the in-memory data structure when payload is valid.

        Returns:
            True when payload is accepted and applied, False when rejected.
        """
        valid, normalized_data, validation_error = self._normalize_and_validate_data(
            new_data
        )
        if not valid:
            const.LOGGER.error(
                "ERROR: Rejected invalid storage payload in set_data: %s",
                validation_error,
            )
            return False

        const.LOGGER.debug(
            "DEBUG: Storage manager set_data called with: %s entities",
            {
                "users": len(normalized_data.get(const.DATA_USERS, {})),
                "chores": len(normalized_data.get(const.DATA_CHORES, {})),
                "badges": len(normalized_data.get(const.DATA_BADGES, {})),
                "rewards": len(normalized_data.get(const.DATA_REWARDS, {})),
                "penalties": len(normalized_data.get(const.DATA_PENALTIES, {})),
                "bonuses": len(normalized_data.get(const.DATA_BONUSES, {})),
                "achievements": len(normalized_data.get(const.DATA_ACHIEVEMENTS, {})),
                "challenges": len(normalized_data.get(const.DATA_CHALLENGES, {})),
                "total_keys": len(normalized_data.keys()),
            },
        )
        self._data = normalized_data
        return True

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
            key: The data key to update (e.g., const.DATA_USERS, const.DATA_CHORES).
            value: The new value for the specified key.

        Note:
            If the key doesn't exist, a warning is logged and no update occurs.
            Valid keys are defined in const.py (DATA_USERS, DATA_CHORES, etc.).
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
