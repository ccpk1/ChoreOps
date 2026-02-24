# File: managers/system_manager.py
"""System Manager for ChoreOps integration.

The "Janitor" - handles entity registry cleanup via reactive signals.

Platinum Architecture Principles:
- REACTIVE: Listens to DELETED signals, does NOT get called directly by other managers
- ISOLATED: No imports from other managers, only entity_helpers and const
- STARTUP: Runs safety net cleanup once during async_setup()

Entity Cleanup Strategy:
1. TARGETED (Domain Managers): When ChoreManager.delete_chore() runs, it calls
   entity_helpers.remove_entities_by_item_id() directly for that specific chore.
2. REACTIVE (SystemManager): Listens to *_DELETED signals for cross-domain cleanup
   (e.g., when a assignee is deleted, scrub any remaining assignee-related entities).
3. SAFETY NET (Startup): Runs remove_all_orphaned_entities() once to catch any
   orphans from crashes, incomplete deletes, or edge cases.

Signals Consumed:
- SIGNAL_SUFFIX_KID_DELETED: Scrub assignee entities from registry
- SIGNAL_SUFFIX_CHORE_DELETED: Scrub chore entities from registry
- SIGNAL_SUFFIX_REWARD_DELETED: Scrub reward entities from registry
- SIGNAL_SUFFIX_BADGE_DELETED: Scrub badge entities from registry
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .. import const
from ..helpers import backup_helpers as bh
from ..helpers.entity_helpers import (
    get_item_id_or_raise,
    get_user_role_gating_context,
    parse_entity_reference,
    remove_entities_by_item_id,
    remove_orphaned_assignee_chore_entities,
    remove_orphaned_manual_adjustment_buttons,
    remove_orphaned_progress_entities,
    remove_orphaned_shared_chore_sensors,
    should_create_entity,
)
from .base_manager import BaseManager

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator


class SystemManager(BaseManager):
    """System Manager - The Janitor.

    Handles reactive entity registry cleanup via domain signals.
    Runs startup safety net to catch orphaned entities.

    Boot Cascade Role (v0.5.0+):
    - Coordinator calls ensure_data_integrity() (BLOCKING)
    - SystemManager runs migrations, ensures meta fields, runs safety net
    - SystemManager emits DATA_READY to trigger cascade
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ChoreOpsDataCoordinator,
    ) -> None:
        """Initialize system manager.

        Args:
            hass: Home Assistant instance
            coordinator: Approver coordinator
        """
        super().__init__(hass, coordinator)

    async def async_setup(self) -> None:
        """Set up the system manager.

        Responsibilities:
        1. Timer Owner - registers ALL `async_track_time_change` calls (single source)
        2. Signal Listener - subscribes to DELETED signals for reactive cleanup

        Note: Startup safety net is called separately AFTER platform setup
        via run_startup_safety_net() - not in async_setup().
        Note: Data integrity (migrations, meta fields) is handled in ensure_data_integrity()
        which is called BLOCKING from Coordinator before managers start.
        """
        # 1. Timer Owner: Register ALL System Heartbeats
        # Midnight Rollover - single timer for all nightly tasks
        # Domain managers subscribe to MIDNIGHT_ROLLOVER and perform their own tasks
        async_track_time_change(
            self.hass,
            self._on_midnight_tick,
            **const.DEFAULT_DAILY_RESET_TIME,
        )

        # 2. Signal Listener: Subscribe to lifecycle DELETED signals
        self.listen(const.SIGNAL_SUFFIX_USER_DELETED, self._handle_assignee_deleted)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DELETED, self._handle_chore_deleted)
        self.listen(const.SIGNAL_SUFFIX_REWARD_DELETED, self._handle_reward_deleted)
        self.listen(const.SIGNAL_SUFFIX_BADGE_DELETED, self._handle_badge_deleted)

        # 3. Startup reliability safety net: catch missed midnight rollover
        await self._run_startup_midnight_catchup()

        const.LOGGER.debug(
            "SystemManager initialized: timer registered, 4 DELETED signal subscriptions for entry %s",
            self.entry_id,
        )

    @callback
    def _on_midnight_tick(self, _: datetime) -> None:
        """Handle midnight timer tick.

        Emits MIDNIGHT_ROLLOVER signal for all domain managers to react.
        Each manager subscribes and performs its own nightly tasks:
        - ChoreManager: recurring resets, overdue checks
        - UIManager: bump past datetime helpers
        """
        const.LOGGER.debug("SystemManager: Midnight rollover triggered")
        self.emit(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER)
        self._stamp_midnight_processed()

    def _stamp_midnight_processed(self) -> None:
        """Persist the timestamp of the most recent midnight rollover handling."""
        meta = self.coordinator._data.setdefault(const.DATA_META, {})
        meta[const.DATA_META_LAST_MIDNIGHT_PROCESSED] = dt_util.utcnow().isoformat()
        self.coordinator._persist()

    def _get_last_midnight_processed_utc(self) -> datetime | None:
        """Return parsed last-midnight timestamp in UTC, or None if unavailable."""
        meta = self.coordinator._data.get(const.DATA_META, {})
        raw_timestamp = meta.get(const.DATA_META_LAST_MIDNIGHT_PROCESSED)
        if not isinstance(raw_timestamp, str) or not raw_timestamp:
            return None

        parsed = dt_util.parse_datetime(raw_timestamp)
        if parsed is None:
            const.LOGGER.warning(
                "SystemManager: Invalid last_midnight_processed timestamp '%s'",
                raw_timestamp,
            )
            return None

        return dt_util.as_utc(parsed)

    async def _run_startup_midnight_catchup(self) -> None:
        """Emit midnight rollover on startup when last processed day is stale."""
        local_now = dt_util.now()
        local_today_midnight = local_now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        today_midnight_utc = dt_util.as_utc(local_today_midnight)

        last_processed_utc = self._get_last_midnight_processed_utc()
        if last_processed_utc is not None and last_processed_utc >= today_midnight_utc:
            const.LOGGER.debug(
                "SystemManager: Midnight catch-up not needed (last_processed=%s)",
                last_processed_utc.isoformat(),
            )
            return

        const.LOGGER.info(
            "SystemManager: Startup midnight catch-up triggered "
            "(last_processed=%s, today_midnight=%s)",
            last_processed_utc.isoformat() if last_processed_utc else "missing",
            today_midnight_utc.isoformat(),
        )
        self.emit(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, catch_up=True)
        self._stamp_midnight_processed()

    # =========================================================================
    # Data Integrity (Boot Cascade - called from Coordinator)
    # =========================================================================

    async def ensure_data_integrity(self, current_version: int) -> None:
        """Ensure data is migrated and clean before domain managers start.

        This is a BLOCKING call from Coordinator. No domain manager should
        see data until this method returns.

        Boot Cascade Position: Called FIRST, emits DATA_READY when complete.

        Pre-v50 migration logic (including fallback cascade, premature stamp
        detection, and schema 44 gate) lives in migration_pre_v50.py and is
        lazy-loaded only when needed. Modern v50+ installations skip it entirely.

        Args:
            current_version: Schema version detected by Coordinator
        """
        const.LOGGER.debug(
            "SystemManager: Ensuring data integrity (schema version: %s)",
            current_version,
        )

        # 1. Pre-v50 migration cascade (lazy-loaded)
        # Includes: premature-stamp detection (#243), structural migrations,
        # nuclear rebuild fallback, auto-restore, and schema 44 gate.
        # migration_performed presence means legacy data needs processing
        # regardless of reported schema version (may be prematurely stamped).
        from ..migration_pre_v50 import has_legacy_migration_performed_marker

        needs_migration = (
            current_version < const.SCHEMA_VERSION_BETA4
            or has_legacy_migration_performed_marker(self.coordinator._data)
        )
        if needs_migration:
            from ..migration_pre_v50 import PreV50Migrator

            migrator = PreV50Migrator(self.coordinator)
            await migrator.run_full_pre_v50_cascade(current_version)

        # 1b. Schema 45 contract hook (runs before DATA_READY)
        from ..migration_pre_v50 import async_apply_schema45_user_contract

        schema45_summary = await async_apply_schema45_user_contract(self.coordinator)
        const.LOGGER.info(
            "SystemManager: Schema45 migration summary users=%d linked_merges=%d standalone_approvers=%d collisions=%d remap_total=%d remap_added=%d",
            schema45_summary["users_migrated"],
            schema45_summary["linked_approver_merges"],
            schema45_summary["standalone_approver_creations"],
            schema45_summary["approver_id_collisions"],
            schema45_summary["approver_id_remap_entries_total"],
            schema45_summary["approver_id_remap_entries_added"],
        )

        # 2. Startup Safety Net (Registry validation)
        await self.run_startup_safety_net()
        const.LOGGER.info("SystemManager: Data integrity verified")

        # 3. THE BATON PASS: Data is now clean and safe
        # Signal domain managers to begin their initialization
        self.emit(const.SIGNAL_SUFFIX_DATA_READY)

    async def run_startup_safety_net(self) -> int:
        """Run startup safety net - removes orphaned entities.

        Called once during fresh startup AFTER platform setup is complete.
        This ensures all legitimate entities have been created before scanning
        for orphans.

        Returns:
            Total count of removed entities.
        """
        total_removed = await self.remove_all_orphaned_entities()
        if total_removed > 0:
            const.LOGGER.info(
                "SystemManager startup safety net removed %d orphaned entities",
                total_removed,
            )
        return total_removed

    # =========================================================================
    # Signal Handlers - Reactive Entity Cleanup
    # =========================================================================

    @callback
    def _handle_assignee_deleted(self, payload: dict[str, Any]) -> None:
        """Handle KID_DELETED signal - scrub registry for assignee entities.

        Called AFTER the assignee has been deleted from storage and _persist() called.
        The payload contains the assignee_id needed for registry scrubbing.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with assignee_id, assignee_name, was_shadow
        """
        if payload.get("user_role") != const.ROLE_ASSIGNEE:
            return

        assignee_id = payload.get("user_id")
        if not assignee_id:
            const.LOGGER.warning("USER_DELETED signal missing user_id in payload")
            return

        # Domain Managers already do targeted cleanup - this is for any stragglers
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            assignee_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted assignee %s",
                removed,
                assignee_id,
            )

    @callback
    def _handle_chore_deleted(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DELETED signal - scrub registry for chore entities.

        Called AFTER the chore has been deleted from storage and _persist() called.
        ChoreManager already calls remove_entities_by_item_id() - this catches stragglers.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with chore_id, chore_name
        """
        chore_id = payload.get("chore_id")
        if not chore_id:
            const.LOGGER.warning("CHORE_DELETED signal missing chore_id in payload")
            return

        # ChoreManager already does targeted cleanup - this is a safety net
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            chore_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted chore %s",
                removed,
                chore_id,
            )

    @callback
    def _handle_reward_deleted(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_DELETED signal - scrub registry for reward entities.

        Called AFTER the reward has been deleted from storage and _persist() called.
        RewardManager already calls remove_entities_by_item_id() - this catches stragglers.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with reward_id, reward_name
        """
        reward_id = payload.get("reward_id")
        if not reward_id:
            const.LOGGER.warning("REWARD_DELETED signal missing reward_id in payload")
            return

        # RewardManager already does targeted cleanup - this is a safety net
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            reward_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted reward %s",
                removed,
                reward_id,
            )

    @callback
    def _handle_badge_deleted(self, payload: dict[str, Any]) -> None:
        """Handle BADGE_DELETED signal - scrub registry for badge entities.

        Called AFTER the badge has been deleted from storage and _persist() called.
        GamificationManager already calls remove_entities_by_item_id() - this catches stragglers.

        Note: Must use @callback decorator to ensure this runs in the event loop
        thread, as entity registry operations require event loop context.

        Args:
            payload: Signal payload with badge_id, badge_name
        """
        badge_id = payload.get("badge_id")
        if not badge_id:
            const.LOGGER.warning("BADGE_DELETED signal missing badge_id in payload")
            return

        # GamificationManager already does targeted cleanup - this is a safety net
        removed = remove_entities_by_item_id(
            self.hass,
            self.coordinator.config_entry.entry_id,
            badge_id,
        )

        if removed > 0:
            const.LOGGER.debug(
                "SystemManager cleaned up %d remaining entities for deleted badge %s",
                removed,
                badge_id,
            )

    # =========================================================================
    # Orphan Entity Removal
    # =========================================================================

    async def remove_all_orphaned_entities(self) -> int:
        """Run all orphan cleanup methods. Called on startup.

        Consolidates all data-driven orphan removal into a single call.
        Delegates to entity_helpers functions for the actual cleanup.

        Returns:
            Total count of removed entities.
        """
        perf_start = time.perf_counter()
        total_removed = 0
        entry_id = self.coordinator.config_entry.entry_id

        # Assignee-chore assignment orphans
        total_removed += await remove_orphaned_assignee_chore_entities(
            self.hass,
            entry_id,
            self.coordinator.assignees_data,
            self.coordinator.chores_data,
        )

        # Shared chore sensor orphans
        total_removed += await remove_orphaned_shared_chore_sensors(
            self.hass, entry_id, self.coordinator.chores_data
        )

        # Badge progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.coordinator.badges_data,
            entity_type="badge",
            progress_suffix=const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR,
            assigned_assignees_key=const.DATA_BADGE_ASSIGNED_TO,
        )

        # Achievement progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.coordinator.achievements_data,
            entity_type="achievement",
            progress_suffix=const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
            assigned_assignees_key=const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
        )

        # Challenge progress orphans
        total_removed += await remove_orphaned_progress_entities(
            self.hass,
            entry_id,
            self.coordinator.challenges_data,
            entity_type="challenge",
            progress_suffix=const.DATA_CHALLENGE_PROGRESS_SUFFIX,
            assigned_assignees_key=const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
        )

        # Manual adjustment button orphans
        current_deltas = set(self.coordinator.economy_manager.adjustment_deltas)
        total_removed += await remove_orphaned_manual_adjustment_buttons(
            self.hass, entry_id, current_deltas
        )

        perf_elapsed = time.perf_counter() - perf_start
        if total_removed > 0:
            const.LOGGER.info(
                "Startup orphan cleanup: removed %d entities in %.3fs",
                total_removed,
                perf_elapsed,
            )
        else:
            const.LOGGER.debug(
                "PERF: startup orphan cleanup completed in %.3fs, no orphans found",
                perf_elapsed,
            )

        return total_removed

    async def remove_conditional_entities(
        self,
        *,
        assignee_ids: list[str] | None = None,
    ) -> int:
        """Remove entities no longer allowed by feature flags.

        Removes entities that are no longer allowed based on current flag settings.
        Uses should_create_entity() from helpers/entity_helpers.py as single source of truth.

        This consolidates:
        - Extra entity cleanup (show_legacy_entities flag)
        - Shadow assignee workflow entity cleanup
        - Shadow assignee gamification entity cleanup

        Args:
            assignee_ids: List of assignee IDs to check, or None for all assignees.
                     Use targeted assignee_ids when a specific assignee's flags change.
                     Use None for bulk cleanup (fresh startup, post-migration).

        Returns:
            Count of removed entities.

        Call patterns:
            - Options flow (extra flag changes): assignee_ids=None (affects all)
            - Options flow (approver flags change): assignee_ids=[shadow_assignee_id]
            - Unlink service: assignee_ids=[shadow_assignee_id]
            - Fresh HA startup (not reload): assignee_ids=None
            - Post-migration: assignee_ids=None
        """
        perf_start = time.perf_counter()
        ent_reg = er.async_get(self.hass)
        prefix = f"{self.coordinator.config_entry.entry_id}_"
        removed_count = 0

        # Get system-wide extra flag
        extra_enabled = self.coordinator.config_entry.options.get(
            const.CONF_SHOW_LEGACY_ENTITIES, False
        )

        # Build assignee filter set (None = check all)
        target_assignees = set(assignee_ids) if assignee_ids else None

        # Get only entities from THIS config entry (not all system entities)
        entities = er.async_entries_for_config_entry(
            ent_reg, self.coordinator.config_entry.entry_id
        )

        for entity_entry in entities:
            unique_id = str(entity_entry.unique_id)
            if not unique_id.startswith(prefix):
                continue

            # Extract assignee_id from unique_id using helper
            parts = parse_entity_reference(unique_id, prefix)
            if not parts:
                continue
            assignee_id = parts[0]

            # Skip if not in target list (when targeted)
            if target_assignees and assignee_id not in target_assignees:
                continue

            gating = get_user_role_gating_context(self.coordinator, assignee_id)

            # Check if entity should exist using unified filter
            if not should_create_entity(
                unique_id,
                is_feature_gated_profile=gating["is_feature_gated_profile"],
                is_assignment_participant=gating["is_assignment_participant"],
                workflow_enabled=gating["workflow_enabled"],
                gamification_enabled=gating["gamification_enabled"],
                extra_enabled=extra_enabled,
            ):
                const.LOGGER.debug(
                    "Removing conditional entity for assignee %s: %s",
                    assignee_id,
                    entity_entry.entity_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)
                removed_count += 1

        perf_elapsed = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: remove_conditional_entities() scanned in %.3fs, removed %d",
            perf_elapsed,
            removed_count,
        )
        if removed_count > 0:
            const.LOGGER.info(
                "Cleaned up %d conditional entit(y/ies) based on current settings",
                removed_count,
            )
        return removed_count

    # =========================================================================
    # Data Reset Orchestration
    # =========================================================================

    async def orchestrate_data_reset(self, service_data: dict[str, Any]) -> None:
        """Orchestrate transactional data reset across domain managers.

        Central orchestration for the reset_transactional_data service.
        Validates input, creates backup, calls domain managers, sends notification.

        Args:
            service_data: Service call data containing:
                - confirm_destructive: bool (required, must be True)
                - scope: str (optional, defaults to "global")
                - assignee_name: str (optional, required if scope="assignee")
                - item_type: str (optional, filters to specific domain)
                - item_name: str (optional, filters to specific item)

        Raises:
            ServiceValidationError: If validation fails (confirmation, scope, etc.)
        """
        # =====================================================================
        # 4B: Safety Validation
        # =====================================================================
        confirm = service_data.get(const.SERVICE_FIELD_CONFIRM_DESTRUCTIVE)
        if confirm is not True:  # Exact boolean check, not truthy
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_DATA_RESET_CONFIRMATION_REQUIRED,
            )

        # =====================================================================
        # 4C: Scope Parsing
        # =====================================================================
        scope = service_data.get(
            const.SERVICE_FIELD_SCOPE, const.DATA_RESET_SCOPE_GLOBAL
        )
        if not scope:
            scope = const.DATA_RESET_SCOPE_GLOBAL

        # Validate scope value
        valid_scopes = {const.DATA_RESET_SCOPE_GLOBAL, const.DATA_RESET_SCOPE_USER}
        if scope not in valid_scopes:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_DATA_RESET_INVALID_SCOPE,
                translation_placeholders={"scope": str(scope)},
            )

        assignee_name = service_data.get(const.SERVICE_FIELD_USER_NAME)
        item_type = service_data.get(const.SERVICE_FIELD_ITEM_TYPE)
        item_name = service_data.get(const.SERVICE_FIELD_ITEM_NAME)

        # Validate scope=user requires assignee_name
        if scope == const.DATA_RESET_SCOPE_USER and not assignee_name:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_DATA_RESET_INVALID_SCOPE,
                translation_placeholders={"scope": "user (requires assignee_name)"},
            )

        # Validate item_type if provided
        valid_item_types = {
            const.DATA_RESET_ITEM_TYPE_POINTS,
            const.DATA_RESET_ITEM_TYPE_CHORES,
            const.DATA_RESET_ITEM_TYPE_REWARDS,
            const.DATA_RESET_ITEM_TYPE_BADGES,
            const.DATA_RESET_ITEM_TYPE_ACHIEVEMENTS,
            const.DATA_RESET_ITEM_TYPE_CHALLENGES,
            const.DATA_RESET_ITEM_TYPE_PENALTIES,
            const.DATA_RESET_ITEM_TYPE_BONUSES,
        }
        if item_type and item_type not in valid_item_types:
            raise ServiceValidationError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_DATA_RESET_INVALID_ITEM_TYPE,
                translation_placeholders={"item_type": str(item_type)},
            )

        # =====================================================================
        # 4D: Name→ID Resolution
        # =====================================================================
        assignee_id: str | None = None
        item_id: str | None = None

        if assignee_name:
            try:
                assignee_id = get_item_id_or_raise(
                    self.coordinator,
                    const.ITEM_TYPE_USER,
                    assignee_name,
                    role=const.ROLE_ASSIGNEE,
                )
            except HomeAssistantError:
                raise ServiceValidationError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_DATA_RESET_ASSIGNEE_NOT_FOUND,
                    translation_placeholders={"assignee_name": str(assignee_name)},
                ) from None

        if item_name and item_type:
            # Map item_type to entity_type for lookup
            item_type_to_entity_type = {
                const.DATA_RESET_ITEM_TYPE_CHORES: const.ITEM_TYPE_CHORE,
                const.DATA_RESET_ITEM_TYPE_REWARDS: const.ITEM_TYPE_REWARD,
                const.DATA_RESET_ITEM_TYPE_BADGES: const.ITEM_TYPE_BADGE,
                const.DATA_RESET_ITEM_TYPE_ACHIEVEMENTS: const.ITEM_TYPE_ACHIEVEMENT,
                const.DATA_RESET_ITEM_TYPE_CHALLENGES: const.ITEM_TYPE_CHALLENGE,
                const.DATA_RESET_ITEM_TYPE_PENALTIES: const.ITEM_TYPE_PENALTY,
                const.DATA_RESET_ITEM_TYPE_BONUSES: const.ITEM_TYPE_BONUS,
            }
            entity_type = item_type_to_entity_type.get(item_type)
            if entity_type:
                try:
                    item_id = get_item_id_or_raise(
                        self.coordinator, entity_type, item_name
                    )
                except HomeAssistantError:
                    raise ServiceValidationError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_DATA_RESET_ITEM_NOT_FOUND,
                        translation_placeholders={
                            "item_type": str(item_type),
                            "item_name": str(item_name),
                        },
                    ) from None

        const.LOGGER.info(
            "Data reset orchestration: scope=%s, assignee_id=%s, item_type=%s, item_id=%s",
            scope,
            assignee_id,
            item_type,
            item_id,
        )

        # =====================================================================
        # 4E: Backup Creation
        # =====================================================================
        backup_name = await bh.create_timestamped_backup(
            self.hass,
            self.coordinator.store,
            const.BACKUP_TAG_DATA_RESET,
            self.coordinator.config_entry,
        )
        if backup_name:
            const.LOGGER.info("Data reset backup created: %s", backup_name)
        else:
            const.LOGGER.warning(
                "Data reset backup creation failed - proceeding anyway"
            )

        # =====================================================================
        # 4F: Call Managers (Based on Scope + Item Type)
        # =====================================================================
        await self._call_data_reset_managers(scope, assignee_id, item_type, item_id)

        # =====================================================================
        # 4G: Send Notification
        # =====================================================================
        await self._send_data_reset_notification(
            scope, assignee_name, item_type, item_name
        )

        const.LOGGER.info("Data reset orchestration complete")

    async def _call_data_reset_managers(
        self,
        scope: str,
        assignee_id: str | None,
        item_type: str | None,
        item_id: str | None,
    ) -> None:
        """Call domain manager data_reset methods based on scope and item_type.

        Args:
            scope: Reset scope (global or assignee)
            assignee_id: Target assignee ID (None for global scope without assignee filter)
            item_type: Domain to reset (None = all domains)
            item_id: Specific item to reset (None = all items in domain)
        """
        coord = self.coordinator

        # If item_type specified, only call that domain's manager
        if item_type:
            await self._call_single_domain_reset(scope, assignee_id, item_type, item_id)
            return

        # No item_type = reset ALL domains
        # Order: downstream → upstream (gamification → rewards → chores → economy)
        # This ensures dependent data is cleared before foundation data
        # 1. Gamification (furthest downstream - consumes points/chores)
        await coord.gamification_manager.data_reset_badges(scope, assignee_id, item_id)
        await coord.gamification_manager.data_reset_achievements(
            scope, assignee_id, item_id
        )
        await coord.gamification_manager.data_reset_challenges(
            scope, assignee_id, item_id
        )
        # 2. Rewards (intermediate - consumes points)
        await coord.reward_manager.data_reset_rewards(scope, assignee_id, item_id)
        # 3. Chores (upstream producer of points)
        await coord.chore_manager.data_reset_chores(scope, assignee_id, item_id)
        # 4. Economy (foundation - owns points, multiplier, bonuses, penalties)
        await coord.economy_manager.data_reset_points(scope, assignee_id, item_id)
        await coord.economy_manager.data_reset_penalties(scope, assignee_id, item_id)
        await coord.economy_manager.data_reset_bonuses(scope, assignee_id, item_id)

    async def _call_single_domain_reset(
        self,
        scope: str,
        assignee_id: str | None,
        item_type: str,
        item_id: str | None,
    ) -> None:
        """Call the appropriate manager for a specific item_type.

        Args:
            scope: Reset scope (global or assignee)
            assignee_id: Target assignee ID
            item_type: Domain to reset
            item_id: Specific item to reset
        """
        coord = self.coordinator

        if item_type == const.DATA_RESET_ITEM_TYPE_POINTS:
            await coord.economy_manager.data_reset_points(scope, assignee_id, item_id)
        elif item_type == const.DATA_RESET_ITEM_TYPE_CHORES:
            await coord.chore_manager.data_reset_chores(scope, assignee_id, item_id)
        elif item_type == const.DATA_RESET_ITEM_TYPE_REWARDS:
            await coord.reward_manager.data_reset_rewards(scope, assignee_id, item_id)
        elif item_type == const.DATA_RESET_ITEM_TYPE_BADGES:
            await coord.gamification_manager.data_reset_badges(
                scope, assignee_id, item_id
            )
        elif item_type == const.DATA_RESET_ITEM_TYPE_ACHIEVEMENTS:
            await coord.gamification_manager.data_reset_achievements(
                scope, assignee_id, item_id
            )
        elif item_type == const.DATA_RESET_ITEM_TYPE_CHALLENGES:
            await coord.gamification_manager.data_reset_challenges(
                scope, assignee_id, item_id
            )
        elif item_type == const.DATA_RESET_ITEM_TYPE_PENALTIES:
            await coord.economy_manager.data_reset_penalties(
                scope, assignee_id, item_id
            )
        elif item_type == const.DATA_RESET_ITEM_TYPE_BONUSES:
            await coord.economy_manager.data_reset_bonuses(scope, assignee_id, item_id)

    async def _send_data_reset_notification(
        self,
        scope: str,
        assignee_name: str | None,
        item_type: str | None,
        item_name: str | None,
    ) -> None:
        """Send notification about data reset completion.

        Args:
            scope: Reset scope used
            assignee_name: Assignee name if assignee scope
            item_type: Item type if filtered
            item_name: Item name if specific item
        """
        # Determine which message key to use based on what was reset
        if item_name and item_type:
            message_key = const.TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ITEM
            placeholders = {"item_name": str(item_name), "item_type": str(item_type)}
        elif item_type:
            message_key = const.TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ITEM_TYPE
            placeholders = {"item_type": str(item_type)}
        elif scope == const.DATA_RESET_SCOPE_USER and assignee_name:
            message_key = const.TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ASSIGNEE
            placeholders = {"assignee_name": str(assignee_name)}
        else:
            message_key = const.TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_GLOBAL
            placeholders = {}

        # Send notification to all approvers via NotificationManager
        # Use a broadcast approach - notify ALL approvers regardless of assignee association
        await self.coordinator.notification_manager.broadcast_to_all_approvers(
            title_key=const.TRANS_KEY_NOTIF_TITLE_DATA_RESET,
            message_key=message_key,
            placeholders=placeholders,
        )
