# File: __init__.py
"""Initialization file for the ChoreOps integration.

Handles setting up the integration, including loading configuration entries,
initializing data storage, and preparing the coordinator for data handling.

Key Features:
- Config entry setup and unload support.
- Coordinator initialization for data synchronization.
- Storage management for persistent data handling.
"""

# Legitimate internal access to coordinator._persist()

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from . import const
from .coordinator import ChoreOpsConfigEntry, ChoreOpsDataCoordinator
from .helpers import backup_helpers as bh, dashboard_helpers as dh
from .helpers.storage_helpers import get_entry_storage_key_from_entry
from .notification_action_handler import async_handle_notification_action
from .services import async_setup_services, async_unload_services
from .store import ChoreOpsStore

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant


async def _update_all_assignee_device_names(
    hass: HomeAssistant, entry: ChoreOpsConfigEntry
) -> None:
    """Update all assignee device names when config entry title changes.

    When the integration name (config entry title) changes, all assignee device
    names need to be updated since they include the title in the format:
    "{assignee_name} ({entry.title})".

    Args:
        hass: Home Assistant instance
        entry: Config entry with potentially new title

    """
    from homeassistant.helpers import device_registry as dr

    from .helpers.device_helpers import get_assignee_device_identifier

    # Get coordinator from runtime_data (modern HA pattern)
    coordinator = entry.runtime_data
    if not coordinator:
        const.LOGGER.debug(
            "Coordinator not found for entry %s, skipping device name updates",
            entry.entry_id,
        )
        return

    device_registry = dr.async_get(hass)
    updated_count = 0

    # Update device name for each assignee
    for assignee_id, assignee_data in coordinator.assignees_data.items():
        assignee_name = assignee_data.get(const.DATA_USER_NAME, "Unknown")
        device = device_registry.async_get_device(
            identifiers={
                (const.DOMAIN, get_assignee_device_identifier(entry, assignee_id))
            }
        )

        if device:
            new_device_name = f"{assignee_name} ({entry.title})"
            # Only update if name actually changed
            if device.name != new_device_name:
                device_registry.async_update_device(device.id, name=new_device_name)
                const.LOGGER.debug(
                    "Updated device name for assignee '%s' (ID: %s) to '%s'",
                    assignee_name,
                    assignee_id,
                    new_device_name,
                )
                updated_count += 1

    if updated_count > 0:
        const.LOGGER.info(
            "Updated %d assignee device names for new integration title: %s",
            updated_count,
            entry.title,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ChoreOpsConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    const.LOGGER.info("INFO: Starting setup for ChoreOps entry: %s", entry.entry_id)

    # Set the home assistant configured timezone for date/time operations
    # Must be done early before any components that use datetime helpers
    const.set_default_timezone(hass)

    # Prime dashboard manifest definitions from disk in executor so
    # options/config flows can resolve template defaults without blocking.
    await dh.async_prime_manifest_template_definitions(hass)

    # Initialize entry-scoped storage manager to ensure multi-entry isolation.
    scoped_storage_key = get_entry_storage_key_from_entry(entry)
    store = ChoreOpsStore(hass, scoped_storage_key)

    # Config flow stages data into a pending flow-scoped storage key before entry_id exists.
    # Move that staged payload into this entry's scoped storage on first setup.
    pending_storage_key = entry.data.get(const.ENTRY_DATA_PENDING_STORAGE_KEY)
    if not pending_storage_key:
        pending_storage_key = entry.options.get(const.ENTRY_DATA_PENDING_STORAGE_KEY)

    if not isinstance(pending_storage_key, str) or not pending_storage_key:
        pending_storage_key = await store.async_find_latest_pending_storage_key()
        if pending_storage_key:
            const.LOGGER.warning(
                "Recovered pending flow storage key from disk scan: %s",
                pending_storage_key,
            )

    if isinstance(pending_storage_key, str) and pending_storage_key:
        pending_store = ChoreOpsStore(hass, pending_storage_key)
        await pending_store.async_initialize(allow_legacy_fallback=False)
        pending_data = dict(pending_store.data)

        await store.async_initialize(allow_legacy_fallback=False)
        if await store.async_adopt_data_if_empty(pending_data):
            const.LOGGER.info(
                "Moved pending flow storage %s into scoped key %s",
                pending_storage_key,
                scoped_storage_key,
            )

        await pending_store.async_delete_storage()

        # Clear one-time pending marker from config entry data.
        cleaned_data = dict(entry.data)
        cleaned_data.pop(const.ENTRY_DATA_PENDING_STORAGE_KEY, None)
        hass.config_entries.async_update_entry(entry, data=cleaned_data)

    # Allow legacy root-key fallback only for first integration instance.
    # Additional entries must stay isolated and start empty unless explicitly restored.
    allow_legacy_fallback = len(hass.config_entries.async_entries(const.DOMAIN)) <= 1
    await store.async_initialize(allow_legacy_fallback=allow_legacy_fallback)

    # DEBUG: Check what was loaded from storage
    loaded_data = store.data
    const.LOGGER.debug(
        "DEBUG: __init__ after storage load: %d users, %d assignees, %d chores, %d badges",
        len(loaded_data.get(const.DATA_USERS, {})),
        len(loaded_data.get(const.DATA_USERS, {})),
        len(loaded_data.get(const.DATA_CHORES, {})),
        len(loaded_data.get(const.DATA_BADGES, {})),
    )

    # PHASE 2: Migrate entity data from config to storage (one-time hand-off) - LEGACY MIGRATION
    # This must happen BEFORE coordinator initialization to ensure coordinator
    # loads from storage-only mode (schema_version >= 43)
    from .migration_pre_v50 import (
        async_migrate_uid_suffixes_v0_5_0,
        migrate_config_to_storage,
        normalize_bonus_penalty_apply_shapes,
    )

    await migrate_config_to_storage(hass, entry, store)

    normalization_summary = normalize_bonus_penalty_apply_shapes(store.data)
    if (
        normalization_summary["bonus_entries_transformed"]
        or normalization_summary["penalty_entries_transformed"]
    ):
        await store.async_save()
        const.LOGGER.info(
            "Normalized apply counters during setup: bonus=%d penalty=%d",
            normalization_summary["bonus_entries_transformed"],
            normalization_summary["penalty_entries_transformed"],
        )

    # PHASE 3: Migrate entity unique_ids from generic to explicit suffixes
    # Only needed for upgrades from < schema 43 (0.5.0b3). Fresh installs and already-upgraded
    # installations have schema >= 43 and skip this.
    meta_section = loaded_data.get(const.DATA_META, {})
    schema_version = meta_section.get(
        const.DATA_META_SCHEMA_VERSION,
        loaded_data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
    )
    if schema_version < 43:
        async_migrate_uid_suffixes_v0_5_0(hass, entry)

    # PHASE 4: Create coordinator with access to current config
    temp_coordinator = ChoreOpsDataCoordinator(hass, entry, store)
    await temp_coordinator.async_config_entry_first_refresh()

    # Create safety backup only on true first startup (not on reloads)
    # Use a persistent flag across reloads to prevent duplicate backups
    startup_backup_key = (
        f"{const.DOMAIN}{const.RUNTIME_KEY_STARTUP_BACKUP_CREATED}{entry.entry_id}"
    )

    # Check if we've already created a startup backup for this entry in this HA session
    if not hass.data.get(startup_backup_key, False):
        # Mark that we're creating the backup (before the actual creation)
        # This prevents race conditions if multiple reloads happen simultaneously
        hass.data[startup_backup_key] = True

        backup_name = await bh.create_timestamped_backup(
            hass, store, const.BACKUP_TAG_RECOVERY, entry
        )
        if backup_name:
            const.LOGGER.info(
                "Created startup recovery backup: %s (automatic safety backup)",
                backup_name,
            )
        else:
            const.LOGGER.warning(
                "Failed to create startup backup - continuing with setup"
            )
    else:
        const.LOGGER.debug("Skipping startup backup on settings reload")

    # Always cleanup old backups based on current retention setting
    # This ensures changes to max_backups are applied immediately
    await bh.cleanup_old_backups(hass, store, entry)

    # Coordinator was already created in PHASE 4 (before cleanup)
    # Reuse the temp_coordinator instance instead of creating a new one
    coordinator = temp_coordinator

    # Store coordinator in runtime_data (modern HA pattern)
    # Store is accessible via coordinator.store
    entry.runtime_data = coordinator

    # Initialize all managers (v0.5.x+)
    # Each manager's async_setup() subscribes to relevant events
    # Critical managers: fail-fast if setup fails (raise ConfigEntryNotReady)
    # Non-critical managers: log warning but continue (degraded functionality)

    # CRITICAL: Economy (points tracking)
    try:
        await coordinator.economy_manager.async_setup()
    except Exception as err:
        raise ConfigEntryNotReady(f"Economy manager setup failed: {err}") from err

    # CRITICAL: Chore (core workflow)
    try:
        await coordinator.chore_manager.async_setup()
    except Exception as err:
        raise ConfigEntryNotReady(f"Chore manager setup failed: {err}") from err

    # CRITICAL: Reward (economy rewards)
    try:
        await coordinator.reward_manager.async_setup()
    except Exception as err:
        raise ConfigEntryNotReady(f"Reward manager setup failed: {err}") from err

    # NON-CRITICAL: Notification (notifications continue without manager)
    try:
        await coordinator.notification_manager.async_setup()
    except Exception as err:
        const.LOGGER.warning(
            "Notification manager setup failed (notifications may not work): %s", err
        )

    # NON-CRITICAL: Gamification (badges/achievements optional)
    try:
        await coordinator.gamification_manager.async_setup()
    except Exception as err:
        const.LOGGER.warning(
            "Gamification manager setup failed (badges/achievements disabled): %s", err
        )

    # NON-CRITICAL: Statistics (historical data optional)
    try:
        await coordinator.statistics_manager.async_setup()
    except Exception as err:
        const.LOGGER.warning(
            "Statistics manager setup failed (stats disabled): %s", err
        )

    # NON-CRITICAL: System (entity cleanup still works via HA registry)
    try:
        await coordinator.system_manager.async_setup()
    except Exception as err:
        const.LOGGER.warning(
            "System manager setup failed (some cleanup may not work): %s", err
        )

    # Dashboard storage dedupe (v0.5.0 migration safety)
    # Remove stale duplicate cod-/kcd- records to prevent Lovelace panel collisions
    # on subsequent Home Assistant startups.
    try:
        from .helpers import dashboard_builder as dbuilder

        dedupe_removed = await dbuilder.async_dedupe_choreops_dashboards(hass)
        removed_total = sum(dedupe_removed.values())
        if removed_total > 0:
            const.LOGGER.info(
                "Startup dashboard dedupe removed %d duplicate entries: %s",
                removed_total,
                dedupe_removed,
            )
    except HomeAssistantError as err:
        const.LOGGER.warning("Startup dashboard dedupe failed: %s", err)

    # Set up services required by the integration.
    async_setup_services(hass)

    # Forward the setup to supported platforms (sensors, buttons, etc.).
    await hass.config_entries.async_forward_entry_setups(entry, const.PLATFORMS)

    # Fresh startup entity cleanup (NOT on reload)
    # Uses runtime key pattern same as backup to detect true first startup
    cleanup_key = (
        f"{const.DOMAIN}{const.RUNTIME_KEY_ENTITY_CLEANUP_DONE}{entry.entry_id}"
    )
    if not hass.data.get(cleanup_key, False):
        hass.data[cleanup_key] = True
        # Run unified conditional entity cleanup (extra, workflow, gamification)
        removed = await coordinator.system_manager.remove_conditional_entities()
        if removed > 0:
            const.LOGGER.info("Fresh startup: removed %d conditional entities", removed)

    # Data-driven orphan removal (always runs - handles deleted/changed data)
    # SystemManager runs all orphan checks: assignee-chore, shared, badges,
    # achievements, challenges, manual adjustment buttons
    await coordinator.system_manager.run_startup_safety_net()

    # Register update listener for config entry changes (e.g., title changes)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Listen for notification actions from the companion app.
    # Wrapped in async_on_unload to ensure cleanup when integration is unloaded.
    async def handle_notification_event(event: Event) -> None:
        """Handle notification action events."""
        await async_handle_notification_action(hass, event)

    entry.async_on_unload(
        hass.bus.async_listen(const.NOTIFICATION_EVENT, handle_notification_event)
    )

    const.LOGGER.info("INFO: ChoreOps setup complete for entry: %s", entry.entry_id)
    return True


async def async_update_options(hass: HomeAssistant, entry: ChoreOpsConfigEntry) -> None:
    """Handle options update (e.g., integration name change, feature flags).

    This is called when the config entry is updated, including when the user
    changes the integration name, feature flags (show_extra_entities,
    enable_chore_workflow, enable_gamification), or other options.

    Cleans up stale entities before reload to ensure immediate registry updates.

    Args:
        hass: Home Assistant instance
        entry: Updated config entry

    """
    const.LOGGER.info(
        "Config entry options updated for %s, cleaning up stale entities",
        entry.entry_id,
    )

    # Get coordinator from runtime_data (modern HA pattern)
    coordinator = entry.runtime_data

    # CRITICAL: Update coordinator's config_entry reference to use NEW options.
    # Without this, remove_conditional_entities() reads from stale options and
    # entities remain unavailable instead of being removed from the registry.
    # The `entry` parameter contains the updated options from async_update_entry().
    const.LOGGER.info(
        "DEBUG: Old coordinator options - show_legacy_entities=%s",
        coordinator.config_entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES),
    )
    const.LOGGER.info(
        "DEBUG: New entry options - show_legacy_entities=%s",
        entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES),
    )
    coordinator.config_entry = entry
    const.LOGGER.info(
        "DEBUG: Updated coordinator.config_entry reference, calling cleanup"
    )

    # Remove entities no longer allowed by feature flags (extra, workflow, gamification)
    removed_count = await coordinator.system_manager.remove_conditional_entities()
    const.LOGGER.info("DEBUG: Cleanup removed %d entities", removed_count)

    # Run full orphan cleanup as safety net (catches data-driven orphans too)
    await coordinator.system_manager.run_startup_safety_net()

    # Update all assignee device names in case title changed
    await _update_all_assignee_device_names(hass, entry)

    # Reload the config entry to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ChoreOpsConfigEntry) -> bool:
    """Unload a config entry."""
    const.LOGGER.info("INFO: Unloading ChoreOps entry: %s", entry.entry_id)

    # Force immediate save of any pending changes before unload
    # Access coordinator from runtime_data (modern HA pattern)
    coordinator = entry.runtime_data
    if coordinator:
        coordinator._persist(immediate=True)  # Unload must be immediate
        const.LOGGER.debug("Forced immediate persist before unload")

    # Clear translation cache to prevent stale translations on reload
    from .helpers.translation_helpers import clear_translation_cache

    clear_translation_cache()
    const.LOGGER.debug("Cleared translation cache on unload")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, const.PLATFORMS)

    if unload_ok:
        # Unload services
        await async_unload_services(hass)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ChoreOpsConfigEntry) -> None:
    """Handle removal of a config entry.

    Creates a backup before deletion to allow data recovery if integration
    is re-added. Backup is tagged with 'removal' for easy identification.

    Args:
        hass: Home Assistant instance
        entry: Config entry being removed

    """
    const.LOGGER.info("INFO: Removing ChoreOps entry: %s", entry.entry_id)

    # Always derive owned store from config entry so remove works even if runtime_data is missing.
    store = ChoreOpsStore(hass, get_entry_storage_key_from_entry(entry))

    # Create backup before deletion (allows data recovery on re-add)
    backup_name = await bh.create_timestamped_backup(
        hass,
        store,
        const.BACKUP_TAG_REMOVAL,
        config_entry=entry,
        storage_key=store.storage_key,
    )
    if backup_name:
        const.LOGGER.info(
            "Created removal backup: %s (integration can be re-added to restore data)",
            backup_name,
        )
    else:
        const.LOGGER.warning(
            "Failed to create removal backup - data will be permanently deleted"
        )

    # Delete only this entry-owned active storage file.
    await store.async_delete_storage()
    const.LOGGER.info("ChoreOps storage file deleted for entry: %s", entry.entry_id)
