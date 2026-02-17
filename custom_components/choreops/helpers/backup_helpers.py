"""Backup utilities for KidsChores integration.

Handles creating, discovering, validating, and cleaning up storage backups.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any, cast

from homeassistant.util import dt as dt_util

from .. import const

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _read_text_file(path: str) -> str:
    """Read a UTF-8 text file from disk.

    This helper is used with hass.async_add_executor_job in async contexts.
    """
    return Path(path).read_text(encoding="utf-8")


def _write_text_file(path: str, content: str) -> None:
    """Write UTF-8 text content to disk.

    This helper is used with hass.async_add_executor_job in async contexts.
    """
    Path(path).write_text(content, encoding="utf-8")


def augment_backup_with_settings(
    backup_data: dict[str, Any],
    config_entry_options: dict[str, Any],
) -> dict[str, Any]:
    """Add config_entry_settings to backup data.

    Args:
        backup_data: Existing storage data with "version" and "data" keys
        config_entry_options: The config_entry.options dict

    Returns:
        Augmented backup data with config_entry_settings section
    """
    # Extract only the 9 system settings
    settings = {
        key: config_entry_options.get(key, default)
        for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
    }

    # Add to backup data (non-destructive)
    augmented = dict(backup_data)
    augmented[const.DATA_CONFIG_ENTRY_SETTINGS] = settings
    return augmented


def validate_config_entry_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate config_entry_settings from backup.

    Returns only valid key-value pairs. Invalid entries logged and skipped.
    Missing keys NOT added (caller merges with defaults).

    Args:
        settings: Settings dict from backup file

    Returns:
        Dictionary with only valid settings
    """
    valid = {}
    for key, default_val in const.DEFAULT_SYSTEM_SETTINGS.items():
        if key in settings:
            value = settings[key]
            # Type-check against default value's type
            if type(value) is type(default_val):
                valid[key] = value
            else:
                const.LOGGER.warning(
                    "Invalid type for %s: expected %s, got %s",
                    key,
                    type(default_val).__name__,
                    type(value).__name__,
                )
    return valid


async def create_timestamped_backup(
    hass: HomeAssistant,
    store,
    tag: str,
    config_entry: ConfigEntry | None = None,
) -> str | None:
    """Create a timestamped backup file with specified tag.

    Args:
        hass: Home Assistant instance
        store: Store instance
        tag: Backup tag (e.g., 'recovery', 'removal', 'reset', 'pre-migration', 'manual')
        config_entry: Optional config entry to capture settings from

    Returns:
        Filename of created backup (e.g., 'choreops_data_2025-12-18_14-30-22_removal')
        or None if backup creation failed or backups are disabled.

    File naming format: choreops_data_YYYY-MM-DD_HH-MM-SS_<tag>
    Example: choreops_data_2025-12-18_14-30-22_removal

    Note: If config_entry is provided and max_backups is 0, no backup is created.
    """
    # Check if backups are disabled (max_backups = 0)
    if config_entry:
        max_backups = int(
            config_entry.options.get(const.CONF_BACKUPS_MAX_RETAINED)
            or const.DEFAULT_BACKUPS_MAX_RETAINED
        )
        if max_backups == 0:
            const.LOGGER.debug(
                "Backups disabled (max_backups=0), skipping %s backup", tag
            )
            # Still cleanup existing backups even though we're not creating a new one
            await cleanup_old_backups(hass, store, config_entry)
            return None

    try:
        # Get current UTC timestamp in filesystem-safe ISO 8601 format
        timestamp = dt_util.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{const.STORAGE_KEY}_{timestamp}_{tag}"

        # Get storage file path
        storage_path = store.get_storage_path()

        # Check if source file exists (non-blocking)
        if not await hass.async_add_executor_job(os.path.exists, storage_path):
            const.LOGGER.warning("Storage file does not exist, cannot create backup")
            return None

        # Ensure scoped storage directory exists (non-blocking)
        storage_dir = hass.config.path(".storage", const.STORAGE_DIRECTORY)
        await hass.async_add_executor_job(
            lambda: os.makedirs(storage_dir, exist_ok=True)
        )

        # Copy file to backup location (non-blocking)
        backup_path = hass.config.path(".storage", const.STORAGE_DIRECTORY, filename)
        await hass.async_add_executor_job(shutil.copy2, storage_path, backup_path)

        # Augment backup with config_entry settings if provided
        if config_entry:
            try:
                # Read backup file
                backup_str = await hass.async_add_executor_job(
                    _read_text_file, backup_path
                )
                backup_data = json.loads(backup_str)

                # Augment with settings (convert MappingProxyType to dict)
                augmented = augment_backup_with_settings(
                    backup_data, dict(config_entry.options)
                )

                # Write augmented version back
                await hass.async_add_executor_job(
                    _write_text_file,
                    backup_path,
                    json.dumps(augmented, indent=2),
                )
                const.LOGGER.debug(
                    "Augmented backup %s with config_entry settings", filename
                )
            except (OSError, ValueError, KeyError) as ex:
                const.LOGGER.warning(
                    "Failed to augment backup with settings: %s (backup still valid)",
                    ex,
                )

        const.LOGGER.debug("Created backup: %s", filename)

        # Automatically cleanup old backups after successful creation
        if config_entry:
            await cleanup_old_backups(hass, store, config_entry)

        return filename

    except (OSError, ValueError) as ex:
        const.LOGGER.error("Failed to create backup with tag %s: %s", tag, ex)
        return None


async def cleanup_old_backups(
    hass: HomeAssistant,
    store,
    config_entry: ConfigEntry,
    max_backups: int | None = None,
) -> None:
    """Delete old backups beyond max_backups limit per tag.

    Args:
        hass: Home Assistant instance
        store: Store instance (unused but kept for API consistency)
        config_entry: Config entry to get max_backups setting from
        max_backups: Optional override for max backups (for testing/explicit control)

    Behavior:
        - Gets max_backups from parameter if provided, else from config_entry (defaults to 5 if None/missing)
        - If max_backups is 0, deletes ALL backups (backups disabled)
        - Keeps newest N backups per tag (e.g., 5 manual, 5 recovery, etc.)
        - Retention applies equally to ALL backup types
        - Logs warnings for deletion failures but continues processing
    """
    # Get max_backups from parameter if provided, otherwise from config entry with proper default handling
    if max_backups is None:
        max_backups = int(
            config_entry.options.get(const.CONF_BACKUPS_MAX_RETAINED)
            or const.DEFAULT_BACKUPS_MAX_RETAINED
        )
    else:
        max_backups = int(max_backups)  # Ensure it's an integer

    try:
        # Discover all backups
        backups_list = await discover_backups(hass, store)

        if max_backups == 0:
            const.LOGGER.info(
                "Backups disabled (max_backups=0), deleting all %d existing backups",
                len(backups_list),
            )
        else:
            const.LOGGER.debug(
                "Backup cleanup: found %d total backups", len(backups_list)
            )

        # Group backups by tag
        backups_by_tag: dict[str, list[dict]] = {}
        for backup in backups_list:
            tag = backup.get("tag", "unknown")  # Handle backups without tag
            if tag not in backups_by_tag:
                backups_by_tag[tag] = []
            backups_by_tag[tag].append(backup)

        const.LOGGER.debug(
            "Backup cleanup: tags found: %s", list(backups_by_tag.keys())
        )

        # Process each tag - retention applies to ALL tags equally
        for tag, tag_backups in backups_by_tag.items():
            const.LOGGER.debug(
                "Processing %d backups for tag '%s'", len(tag_backups), tag
            )

            # Sort by timestamp (newest first) - use defensive programming for missing timestamp
            tag_backups.sort(
                key=lambda b: b.get("timestamp", "1970-01-01T00:00:00.000000+00:00"),
                reverse=True,
            )

            # Delete oldest backups beyond max_backups (applies to all tags: recovery, reset, etc.)
            backups_to_delete = tag_backups[max_backups:]
            const.LOGGER.debug(
                "Tag '%s': keeping %d newest, deleting %d oldest (max_backups=%d)",
                tag,
                min(len(tag_backups), max_backups),
                len(backups_to_delete),
                max_backups,
            )

            for backup in backups_to_delete:
                try:
                    backup_path = hass.config.path(
                        ".storage", const.STORAGE_DIRECTORY, backup["filename"]
                    )
                    await hass.async_add_executor_job(os.remove, backup_path)
                    const.LOGGER.info(
                        "Cleaned up old %s backup: %s", tag, backup["filename"]
                    )
                except OSError as ex:
                    const.LOGGER.warning(
                        "Failed to delete backup %s: %s", backup["filename"], ex
                    )

    except (OSError, ValueError) as ex:
        const.LOGGER.error("Failed during backup cleanup: %s", ex)


async def discover_backups(hass: HomeAssistant, store) -> list[dict]:
    """Scan .storage/ directory for backup files and return metadata list.

    Args:
        hass: Home Assistant instance
        store: Store instance (unused but kept for API consistency)

    Returns:
        List of backup metadata dictionaries with keys:
        - filename: str (e.g., 'choreops_data_2025-12-18_14-30-22_removal')
        - tag: str (e.g., 'recovery', 'removal', 'reset', 'pre-migration', 'manual')
        - timestamp: datetime (parsed from filename)
        - age_hours: float (hours since backup creation)
        - size_bytes: int (file size in bytes)

    File naming format: choreops_data_YYYY-MM-DD_HH-MM-SS_<tag>
    Invalid filenames are skipped with debug log.
    """
    backups_list: list[dict[str, Any]] = []
    storage_dir = hass.config.path(".storage", const.STORAGE_DIRECTORY)

    try:
        # Check if storage directory exists (non-blocking)
        if not await hass.async_add_executor_job(os.path.exists, storage_dir):
            const.LOGGER.warning("Storage directory does not exist: %s", storage_dir)
            return backups_list

        # Get directory listing (non-blocking)
        filenames = await hass.async_add_executor_job(os.listdir, storage_dir)
        storage_prefix = f"{const.STORAGE_KEY}_"
        for filename in filenames:
            # Match format: choreops_data_YYYY-MM-DD_HH-MM-SS_<tag>
            if not filename.startswith(storage_prefix):
                continue

            # Skip active file (no timestamp/tag suffix)
            if filename == const.STORAGE_KEY:
                continue

            # Parse filename: choreops_data_YYYY-MM-DD_HH-MM-SS_<tag>
            try:
                # Remove '{storage_key}_' prefix
                suffix = filename[len(storage_prefix) :]

                # Split into timestamp and tag parts
                # Format: YYYY-MM-DD_HH-MM-SS_<tag>
                parts = suffix.rsplit("_", 1)  # Split from right to get tag
                if len(parts) != 2:
                    const.LOGGER.debug("Skipping invalid backup filename: %s", filename)
                    continue

                timestamp_str, tag = parts

                # Parse timestamp (format: YYYY-MM-DD_HH-MM-SS)
                # Split date and time parts, convert time hyphens to colons
                # YYYY-MM-DD_HH-MM-SS -> YYYY-MM-DD HH:MM:SS
                date_part, time_part = timestamp_str.split("_", 1)
                time_part_clean = time_part.replace("-", ":")
                timestamp_str_clean = f"{date_part} {time_part_clean}"
                timestamp = datetime.datetime.strptime(
                    timestamp_str_clean, "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=datetime.UTC)

                # Calculate age
                age_hours = (dt_util.utcnow() - timestamp).total_seconds() / 3600

                # Get file size (non-blocking)
                file_path = os.path.join(storage_dir, filename)
                size_bytes = await hass.async_add_executor_job(
                    os.path.getsize, file_path
                )

                backups_list.append(
                    {
                        "filename": filename,
                        "tag": tag,
                        "timestamp": timestamp,
                        "age_hours": age_hours,
                        "size_bytes": size_bytes,
                    }
                )

            except (ValueError, OSError) as ex:
                const.LOGGER.debug("Skipping invalid backup file %s: %s", filename, ex)
                continue

    except OSError as ex:
        const.LOGGER.error("Failed to scan storage directory: %s", ex)

    # Sort by timestamp (newest first)
    backups_list.sort(
        key=lambda b: cast("datetime.datetime", b["timestamp"]), reverse=True
    )
    return backups_list


def format_backup_age(age_hours: float) -> str:
    """Convert hours to human-readable age string.

    Args:
        age_hours: Age in hours (can be fractional)

    Returns:
        Human-readable string like:
        - "2 minutes ago"
        - "1 hour ago"
        - "5 hours ago"
        - "2 days ago"
        - "3 weeks ago"

    Precision:
        - < 1 hour: minutes
        - < 24 hours: hours
        - < 7 days: days
        - >= 7 days: weeks
    """
    if age_hours < 1:
        minutes = max(1, int(age_hours * 60))  # Always show at least 1 minute
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    if age_hours < 24:
        hours = int(age_hours)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    if age_hours < 168:  # 7 days
        days = int(age_hours / 24)
        return f"{days} day{'s' if days != 1 else ''} ago"

    weeks = int(age_hours / 168)
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


def validate_backup_json(json_str: str) -> bool:
    """Validate JSON structure of backup data.

    Args:
        json_str: JSON string to validate

    Returns:
        True if JSON is valid and contains expected top-level keys.
        False if JSON is malformed or missing required structure.

    Supported formats:
        1. Diagnostic format (KC 4.0+ diagnostic exports):
            {
                "home_assistant": {...},
                "custom_components": {...},
                "integration_manifest": {...},
                "data": {
                    "kids": dict,
                    "parents": dict,
                    ...
                }
            }

        2. Modern format (schema_version 42):
            {
                "schema_version": 42,
                "kids": dict,
                "parents": dict,
                ...
            }

        3. Legacy format (no schema_version - KC 3.0/3.1/early 4.0beta):
            {
                "kids": dict,
                "parents": dict,
                ...
            }

        4. Store format (version 1 - KC 3.0/3.1/4.0beta1):
            {
                "version": 1,
                "minor_version": 1,
                "key": "kidschores_data",
                "data": {
                    "kids": dict,
                    "parents": dict,
                    ...
                }
            }

    Minimum requirements:
        - Valid JSON syntax
        - Top-level object (dict)
        - If Store format, version must be 1 (only version supported)
        - Contains at least one entity type key (kids, parents, chores, rewards)
    """
    try:
        data = json.loads(json_str)

        # Must be a dictionary
        if not isinstance(data, dict):
            const.LOGGER.debug("Backup JSON is not a dictionary")
            return False

        # Handle diagnostic format (KC 4.0+ diagnostic exports)
        if "home_assistant" in data and "data" in data:
            const.LOGGER.debug("Detected diagnostic export format")
            # Diagnostic format wraps storage data in "data" key with metadata
            if not isinstance(data["data"], dict):
                const.LOGGER.debug("Diagnostic format 'data' is not a dictionary")
                return False
            data = data["data"]  # Unwrap for entity validation

        # Handle Store format (KC 3.0/3.1/4.0beta1) - version 1 only
        elif "version" in data:
            store_version = data.get("version")
            if store_version != 1:
                const.LOGGER.warning(
                    "Unsupported Store version %s - only version 1 (KC 3.x/4.0beta) is supported",
                    store_version,
                )
                return False
            # Store format wraps data in "data" key
            if "data" not in data:
                const.LOGGER.debug("Store format missing 'data' wrapper")
                return False
            data = data["data"]  # Unwrap for entity validation

        # schema_version is optional - old backups won't have it and will be migrated

        # Must have at least one entity type
        entity_keys = {
            "kids",
            "parents",
            "chores",
            "rewards",
            "bonuses",
            "penalties",
            "achievements",
            "challenges",
            "badges",
        }
        if not any(key in data for key in entity_keys):
            const.LOGGER.debug("Backup JSON missing all entity type keys")
            return False

        return True

    except json.JSONDecodeError as ex:
        const.LOGGER.debug("Invalid JSON in backup: %s", ex)
        return False
    except (TypeError, ValueError) as ex:
        const.LOGGER.debug("Unexpected error validating backup JSON: %s", ex)
        return False
