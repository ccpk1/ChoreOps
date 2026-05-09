"""UI Manager for ChoreOps dashboard and translation sensor features.

Responsible for:
- Translation sensor lifecycle (creation, lookup, cleanup)
- Datetime helper midnight bumping
- Dashboard language management

This manager owns all UI-related features that were previously in the Coordinator,
following the Platinum Architecture principle of Infrastructure-Only Coordinator.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .. import const
from .base_manager import BaseManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator


@dataclass(slots=True)
class HelperShardRuntimePlan:
    """Runtime shard allocation for one user and payload family."""

    family: str
    mode: Literal["inline", "sharded"]
    shard_item_ids: list[list[str]]
    expected_shard_count: int
    last_accepted_serialized_size: int
    last_reconciliation_outcome: str


class UIManager(BaseManager):
    """Manager for UI features including translation sensors and datetime helpers.

    This manager centralizes all dashboard/UI-related functionality that doesn't
    belong in the Coordinator's infrastructure-only role.
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: ChoreOpsDataCoordinator
    ) -> None:
        """Initialize UI manager.

        Args:
            hass: Home Assistant instance
            coordinator: Approver coordinator managing this integration instance
        """
        super().__init__(hass, coordinator)

        # Track which translation sensors have been created
        self._translation_sensors_created: set[str] = set()

        # Callback for adding new translation sensors dynamically
        self._sensor_add_entities_callback: Callable[..., None] | None = None

        # Dashboard optimization: track when pending approvals change
        # Flags are True on first load to force initial attribute build
        self._pending_chore_changed: bool = True
        self._pending_reward_changed: bool = True

        # Runtime-owned shard plans keyed by payload family then user ID.
        self._helper_shard_plans: dict[str, dict[str, HelperShardRuntimePlan]] = {
            const.HELPER_SHARD_FAMILY_CHORES: {}
        }

    async def async_setup(self) -> None:
        """Set up the UI manager.

        Called once during coordinator initialization.
        Subscribes to user deletion events to clean up unused translation sensors.
        Subscribes to chore/reward events to track pending approval changes.
        """
        # Listen for user deletion to clean up translation sensors
        # Follows Platinum Architecture: UIManager reacts to signals instead of
        # being called directly by UserManager
        self.listen(const.SIGNAL_SUFFIX_USER_DELETED, self._on_user_deleted)

        # Listen for chore state changes that affect pending approvals
        # These signals are already emitted by ChoreManager - no coupling needed
        self.listen(const.SIGNAL_SUFFIX_CHORE_CLAIMED, self._on_chore_changed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_changed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DISAPPROVED, self._on_chore_changed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_UNDONE, self._on_chore_changed)
        self.listen(const.SIGNAL_SUFFIX_CHORE_STATUS_RESET, self._on_chore_changed)

        # Listen for reward state changes that affect pending approvals
        # These signals are already emitted by RewardManager - no coupling needed
        self.listen(const.SIGNAL_SUFFIX_REWARD_CLAIMED, self._on_reward_changed)
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._on_reward_changed)
        self.listen(const.SIGNAL_SUFFIX_REWARD_DISAPPROVED, self._on_reward_changed)
        self.listen(const.SIGNAL_SUFFIX_REWARD_STATUS_RESET, self._on_reward_changed)

        # Listen for midnight rollover to bump datetime helpers
        self.listen(const.SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER, self._on_midnight_rollover)

        await self.async_prepare_startup_chore_shard_plans()

        const.LOGGER.debug("UIManager setup complete for entry %s", self.entry_id)

    async def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
        """Handle midnight rollover - bump datetime helpers past current time.

        Follows Platinum Architecture (Choreography): UIManager reacts
        to MIDNIGHT_ROLLOVER signal and performs its own nightly tasks.

        Args:
            payload: Event data (unused, but required by signal handler signature)
        """
        const.LOGGER.debug("UIManager: Processing midnight rollover")
        now = dt_util.utcnow()
        try:
            await self.bump_past_datetime_helpers(now)
        except Exception:
            const.LOGGER.exception("UIManager: Error during midnight rollover")

    def _on_user_deleted(self, payload: dict[str, Any]) -> None:
        """Handle user deletion - clean up unused translation sensors.

        Follows Platinum Architecture (Choreography): UIManager reacts to
        KID_DELETED/PARENT_DELETED signals and cleans its own domain
        (translation sensors that are no longer needed).

        Args:
            payload: Event data (assignee_id/approver_id - not used, we scan all users)
        """
        # Don't need payload data - just check if any languages are now unused
        self.remove_unused_translation_sensors()

        user_id = payload.get(const.DATA_USER_ID)
        if isinstance(user_id, str) and user_id:
            self.clear_helper_shard_plan(user_id, const.HELPER_SHARD_FAMILY_CHORES)
            self._remove_chore_shard_entities_for_user(user_id)

    def _on_chore_changed(self, payload: dict[str, Any]) -> None:
        """Handle chore state change - mark pending approvals as changed.

        Args:
            payload: Event data (not used, just sets flag)
        """
        self._pending_chore_changed = True

    def _on_reward_changed(self, payload: dict[str, Any]) -> None:
        """Handle reward state change - mark pending approvals as changed.

        Args:
            payload: Event data (not used, just sets flag)
        """
        self._pending_reward_changed = True

    # -------------------------------------------------------------------------------------
    # Pending Approval Change Tracking (Dashboard Optimization)
    # -------------------------------------------------------------------------------------

    @property
    def pending_chore_changed(self) -> bool:
        """Return whether pending chore approvals have changed since last reset."""
        return self._pending_chore_changed

    @property
    def pending_reward_changed(self) -> bool:
        """Return whether pending reward approvals have changed since last reset."""
        return self._pending_reward_changed

    def reset_pending_change_flags(self) -> None:
        """Reset the pending change flags after UI has processed the changes.

        Called by dashboard helper sensor after rebuilding attributes.
        """
        self._pending_chore_changed = False
        self._pending_reward_changed = False

    def get_dashboard_ui_control(self, user_id: str) -> dict[str, Any]:
        """Return resolved dashboard UI control values for one user.

        This exposes a dashboard-safe copy of the persisted per-user UI control
        payload so templates can consume dynamic keys without backend path
        registration.
        """
        return deepcopy(self._get_user_ui_preferences(user_id))

    def get_shared_admin_ui_control(self) -> dict[str, Any]:
        """Return resolved dashboard UI control values for the shared admin view."""
        data_meta = self.coordinator._data.get(const.DATA_META, {})
        if not isinstance(data_meta, dict):
            return {}

        shared_admin_ui_control = data_meta.get(const.DATA_META_SHARED_ADMIN_UI_CONTROL)
        if not isinstance(shared_admin_ui_control, dict):
            return {}

        return deepcopy(shared_admin_ui_control)

    def _get_user_ui_preferences(self, user_id: str) -> dict[str, Any]:
        """Return the persisted UI preferences bucket for one user."""
        user_record: Any = self.coordinator.assignees_data.get(user_id, {})
        if not isinstance(user_record, dict):
            return {}

        ui_preferences = user_record.get(const.DATA_USER_UI_PREFERENCES)
        if not isinstance(ui_preferences, dict):
            return {}

        return ui_preferences

    # -------------------------------------------------------------------------------------
    # Translation Sensor Lifecycle Management
    # -------------------------------------------------------------------------------------

    def register_translation_sensor_callback(
        self, async_add_entities: Callable[..., None]
    ) -> None:
        """Register the callback for dynamically adding translation sensors.

        Called by sensor.py during async_setup_entry to enable dynamic sensor creation.

        Args:
            async_add_entities: The callback function from sensor platform setup
        """
        self._sensor_add_entities_callback = async_add_entities

    async def async_prepare_startup_chore_shard_plans(self) -> None:
        """Build startup chore shard plans from current coordinator data."""
        await self.async_reconcile_chore_shards_for_users(
            list(self.coordinator.assignees_data),
            registry_only=True,
        )

    async def async_reconcile_chore_shards_for_users(
        self,
        user_ids: list[str],
        *,
        registry_only: bool = False,
    ) -> None:
        """Rebuild chore shard plans and reconcile shard helper entities."""
        if not user_ids:
            return

        from ..sensor import AssigneeDashboardChoreShardSensor, build_chore_shard_plan

        entity_registry = er.async_get(self.hass)
        created_sensors: list[AssigneeDashboardChoreShardSensor] = []

        for user_id in sorted(set(user_ids)):
            user_data = self.coordinator.assignees_data.get(user_id)
            if not isinstance(user_data, dict):
                self.clear_helper_shard_plan(user_id, const.HELPER_SHARD_FAMILY_CHORES)
                self._remove_chore_shard_entities_for_user(user_id)
                continue

            user_name = user_data.get(const.DATA_USER_NAME)
            if not isinstance(user_name, str) or not user_name:
                continue

            previous_plan = self.get_helper_shard_plan(
                user_id, const.HELPER_SHARD_FAMILY_CHORES
            )
            plan = build_chore_shard_plan(
                self.hass,
                self.coordinator,
                self.coordinator.config_entry,
                user_id,
                user_name,
                previous_plan=previous_plan,
            )
            self.set_helper_shard_plan(user_id, const.HELPER_SHARD_FAMILY_CHORES, plan)

            existing_entries = self._get_existing_chore_shard_entries(user_id)
            live_shard_indexes = self._get_live_chore_shard_indexes(existing_entries)
            expected_indexes = set(range(1, plan.expected_shard_count + 1))

            removed_count = 0
            for shard_index, entity_entry in existing_entries.items():
                if shard_index in expected_indexes:
                    continue
                entity_registry.async_remove(entity_entry.entity_id)
                removed_count += 1

            created_count = 0
            if not registry_only and self._sensor_add_entities_callback is not None:
                for shard_index in sorted(expected_indexes):
                    if shard_index in live_shard_indexes:
                        continue
                    created_sensors.append(
                        AssigneeDashboardChoreShardSensor(
                            self.coordinator,
                            self.coordinator.config_entry,
                            user_id,
                            user_name,
                            shard_index,
                        )
                    )
                    created_count += 1

            missing_count = max(plan.expected_shard_count - len(existing_entries), 0)
            if registry_only and missing_count > 0:
                plan.last_reconciliation_outcome = (
                    f"planned_missing={missing_count} removed={removed_count}"
                )
            else:
                plan.last_reconciliation_outcome = (
                    f"created={created_count} removed={removed_count}"
                )

        if created_sensors and self._sensor_add_entities_callback is not None:
            self._sensor_add_entities_callback(created_sensors)

    async def async_finalize_chore_shards_for_users(
        self,
        user_ids: list[str],
        *,
        registry_only: bool = True,
    ) -> None:
        """Refresh shard plans from the settled registry and republish helper state."""
        if registry_only:
            await asyncio.sleep(0)
        await self.async_reconcile_chore_shards_for_users(
            user_ids,
            registry_only=registry_only,
        )
        self.coordinator.async_update_listeners()
        if not registry_only:
            self.hass.async_create_task(
                self.async_finalize_chore_shards_for_users(
                    user_ids,
                    registry_only=True,
                )
            )

    def clear_runtime_state(self) -> None:
        """Clear runtime-only UI manager state on unload."""
        self._translation_sensors_created.clear()
        self._helper_shard_plans = {const.HELPER_SHARD_FAMILY_CHORES: {}}
        self._sensor_add_entities_callback = None

    def get_helper_shard_plan(
        self, user_id: str, family: str
    ) -> HelperShardRuntimePlan | None:
        """Return the runtime shard plan for one user and family."""
        return self._helper_shard_plans.get(family, {}).get(user_id)

    def set_helper_shard_plan(
        self, user_id: str, family: str, plan: HelperShardRuntimePlan
    ) -> None:
        """Store the runtime shard plan for one user and family."""
        self._helper_shard_plans.setdefault(family, {})[user_id] = plan

    def clear_helper_shard_plan(self, user_id: str, family: str) -> None:
        """Drop one runtime shard plan entry if present."""
        family_plans = self._helper_shard_plans.get(family)
        if family_plans is not None:
            family_plans.pop(user_id, None)

    def get_chore_shard_helper_eids(self, user_id: str) -> list[str]:
        """Return ordered chore shard helper entity IDs for one user."""
        plan = self.get_helper_shard_plan(user_id, const.HELPER_SHARD_FAMILY_CHORES)
        if plan is None or plan.expected_shard_count == 0:
            return []

        return [
            entity_entry.entity_id
            for shard_index in range(1, plan.expected_shard_count + 1)
            if (
                entity_entry := self._get_existing_chore_shard_entries(user_id).get(
                    shard_index
                )
            )
        ]

    def get_chore_shard_unique_id(self, user_id: str, shard_index: int) -> str:
        """Return the stable unique ID for one chore shard helper."""
        return (
            f"{self.coordinator.config_entry.entry_id}_{user_id}_{shard_index}"
            f"{const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_CHORE_SHARD_HELPER}"
        )

    def _get_existing_chore_shard_entries(
        self, user_id: str
    ) -> dict[int, er.RegistryEntry]:
        """Return existing chore shard registry entries keyed by shard index."""
        entity_registry = er.async_get(self.hass)
        prefix = f"{self.coordinator.config_entry.entry_id}_{user_id}_"
        suffix = const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_CHORE_SHARD_HELPER
        shard_entries: dict[int, er.RegistryEntry] = {}

        for entry in entity_registry.entities.values():
            unique_id = entry.unique_id
            if not unique_id.startswith(prefix) or not unique_id.endswith(suffix):
                continue

            shard_index = unique_id[len(prefix) : -len(suffix)]
            if not shard_index.isdigit():
                continue

            shard_entries[int(shard_index)] = entry

        return shard_entries

    def _get_live_chore_shard_indexes(
        self, existing_entries: dict[int, er.RegistryEntry]
    ) -> set[int]:
        """Return shard indexes that currently have live states in Home Assistant."""
        return {
            shard_index
            for shard_index, entity_entry in existing_entries.items()
            if self.hass.states.get(entity_entry.entity_id) is not None
        }

    def _remove_chore_shard_entities_for_user(self, user_id: str) -> None:
        """Remove all chore shard helper entities for one user."""
        entity_registry = er.async_get(self.hass)
        for entity_entry in self._get_existing_chore_shard_entries(user_id).values():
            entity_registry.async_remove(entity_entry.entity_id)

    def mark_translation_sensor_created(self, lang_code: str) -> None:
        """Mark that a translation sensor for this language has been created.

        Args:
            lang_code: ISO language code (e.g., 'en', 'es', 'de')
        """
        self._translation_sensors_created.add(lang_code)

    def is_translation_sensor_created(self, lang_code: str) -> bool:
        """Check if a translation sensor exists for the given language code.

        Args:
            lang_code: ISO language code (e.g., 'en', 'es', 'de')

        Returns:
            True if sensor has been created, False otherwise
        """
        return lang_code in self._translation_sensors_created

    def get_translation_sensor_eid(self, lang_code: str) -> str | None:
        """Get the entity ID for a translation sensor given a language code.

        Looks up the entity ID from the registry using the unique_id.
        Falls back to English ('en') if the requested language isn't found.
        Returns None only if neither the requested language nor English exist.

        Args:
            lang_code: ISO language code (e.g., 'en', 'es', 'de')

        Returns:
            Entity ID if found in registry (requested or fallback), None otherwise
        """
        from homeassistant.helpers.entity_registry import async_get

        entity_registry = async_get(self.hass)
        unique_id = (
            f"{self.coordinator.config_entry.entry_id}_"
            f"{lang_code}{const.SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG}"
        )
        entity_id = entity_registry.async_get_entity_id(
            "sensor", const.DOMAIN, unique_id
        )

        # If requested language not found and it's not already English, fall back to English
        if entity_id is None and lang_code != "en":
            unique_id_en = (
                f"{self.coordinator.config_entry.entry_id}_"
                f"en{const.SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG}"
            )
            entity_id = entity_registry.async_get_entity_id(
                "sensor", const.DOMAIN, unique_id_en
            )

        return entity_id

    async def ensure_translation_sensor_exists(self, lang_code: str) -> str | None:
        """Ensure a translation sensor exists for the given language code.

        If the sensor doesn't exist, creates it dynamically using the stored
        async_add_entities callback. Returns the entity ID.

        This is called when an assignee's dashboard language changes to a new language
        that doesn't have a translation sensor yet.

        Args:
            lang_code: ISO language code (e.g., 'en', 'es', 'de')

        Returns:
            The entity ID of the translation sensor if available in registry,
            otherwise None
        """
        # Import here to avoid circular dependency
        from ..sensor import SystemDashboardTranslationSensor

        # Try to get entity ID from registry
        eid = self.get_translation_sensor_eid(lang_code)

        # If sensor already exists in registry, return the entity ID
        if eid:
            return eid

        # If sensor was marked as created but not in registry yet, return None.
        # The caller should retry after entity registry update.
        if lang_code in self._translation_sensors_created:
            return None

        # If no callback registered (shouldn't happen), log warning and return fallback
        if self._sensor_add_entities_callback is None:
            const.LOGGER.warning(
                "Cannot create translation sensor for '%s': no callback registered",
                lang_code,
            )
            # Fallback to English if available
            if const.DEFAULT_DASHBOARD_LANGUAGE in self._translation_sensors_created:
                fallback_eid = self.get_translation_sensor_eid(
                    const.DEFAULT_DASHBOARD_LANGUAGE
                )
                if fallback_eid:
                    return fallback_eid
            return None

        # Create the new translation sensor
        const.LOGGER.info(
            "Creating translation sensor for newly-used language: %s", lang_code
        )
        new_sensor = SystemDashboardTranslationSensor(
            self.coordinator, self.coordinator.config_entry, lang_code
        )
        self._sensor_add_entities_callback([new_sensor])
        self._translation_sensors_created.add(lang_code)

        # Return registry-resolved entity ID if available now; otherwise None.
        return self.get_translation_sensor_eid(lang_code)

    def get_languages_in_use(self) -> set[str]:
        """Get all unique dashboard languages currently in use by assignees and approvers.

        Used to determine which translation sensors are needed.

        Returns:
            Set of ISO language codes in use (always includes 'en' as fallback)
        """
        languages: set[str] = set()
        for assignee_info in self.coordinator.assignees_data.values():
            lang = assignee_info.get(
                const.DATA_USER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            )
            languages.add(lang)
        for approver_info in self.coordinator.approvers_data.values():
            lang = approver_info.get(
                const.DATA_USER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            )
            languages.add(lang)
        # Always include English as fallback
        languages.add(const.DEFAULT_DASHBOARD_LANGUAGE)
        return languages

    def get_shared_admin_dashboard_language(self) -> str:
        """Resolve the stable shared-admin dashboard language.

        The shared admin language is backend-owned and must not depend on the
        currently selected user in the admin UI.
        """
        users = self.coordinator.users_data
        if not users:
            return const.DEFAULT_DASHBOARD_LANGUAGE

        language_counts: dict[str, int] = {}
        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue

            language = user_data.get(const.DATA_USER_DASHBOARD_LANGUAGE)
            resolved_language = (
                language
                if isinstance(language, str) and language
                else const.DEFAULT_DASHBOARD_LANGUAGE
            )
            language_counts[resolved_language] = (
                language_counts.get(resolved_language, 0) + 1
            )

        if not language_counts:
            return const.DEFAULT_DASHBOARD_LANGUAGE

        winning_count = max(language_counts.values())
        winning_languages = {
            language
            for language, count in language_counts.items()
            if count == winning_count
        }
        if len(winning_languages) == 1:
            return next(iter(winning_languages))

        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue
            if not (
                user_data.get(const.DATA_USER_CAN_APPROVE, False)
                or user_data.get(const.DATA_USER_CAN_MANAGE, False)
                or bool(user_data.get(const.DATA_USER_ASSOCIATED_USER_IDS))
            ):
                continue

            language = user_data.get(const.DATA_USER_DASHBOARD_LANGUAGE)
            resolved_language = (
                language
                if isinstance(language, str) and language
                else const.DEFAULT_DASHBOARD_LANGUAGE
            )
            if resolved_language in winning_languages:
                return resolved_language

        return const.DEFAULT_DASHBOARD_LANGUAGE

    def remove_unused_translation_sensors(self) -> None:
        """Remove translation sensors for languages no longer in use.

        This is an optimization to avoid keeping unused sensors in memory.
        Called when an assignee/approver is deleted or their language is changed.

        Note: Entity removal is handled via entity registry; we just update tracking.
        """
        languages_in_use = self.get_languages_in_use()
        unused_languages = self._translation_sensors_created - languages_in_use

        if not unused_languages:
            return

        # Get entity registry and remove unused translation sensors
        entity_registry = er.async_get(self.hass)
        for lang_code in unused_languages:
            eid = self.get_translation_sensor_eid(lang_code)
            if eid:  # Only try to remove if entity exists in registry
                entity_entry = entity_registry.async_get(eid)
                if entity_entry:
                    const.LOGGER.info(
                        "Removing unused translation sensor: %s (language: %s)",
                        eid,
                        lang_code,
                    )
                    entity_registry.async_remove(eid)
            self._translation_sensors_created.discard(lang_code)

    # -------------------------------------------------------------------------------------
    # Datetime Helper Management
    # -------------------------------------------------------------------------------------

    async def bump_past_datetime_helpers(self, _now: datetime) -> None:
        """Advance all datetime helpers to tomorrow at 9 AM.

        Called during midnight processing to advance date/time pickers
        to the next day at 9 AM, regardless of current value.

        This is a Dashboard UX feature to ensure datetime helpers always show
        a future date when assignees check their dashboard in the morning.

        Args:
            _now: Current datetime (provided by async_track_time_change, unused)
        """
        if not self.hass:
            return

        # Get entity registry to find datetime helper entities by unique_id pattern
        entity_registry = er.async_get(self.hass)

        # Find all datetime helper entities using unique_id pattern
        for assignee_id, assignee_info in self.coordinator.assignees_data.items():
            assignee_name = assignee_info.get(
                const.DATA_USER_NAME, f"Assignee {assignee_id}"
            )

            # Construct unique_id pattern (matches datetime.py)
            expected_unique_id = (
                f"{self.coordinator.config_entry.entry_id}_"
                f"{assignee_id}{const.DATETIME_KC_UID_SUFFIX_DATE_HELPER}"
            )

            # Find entity by unique_id
            entity_entry = entity_registry.async_get_entity_id(
                "datetime", const.DOMAIN, expected_unique_id
            )

            if not entity_entry:
                continue

            # Set to tomorrow at 9 AM local time
            tomorrow = dt_util.now() + timedelta(days=1)
            tomorrow_9am = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

            await self.hass.services.async_call(
                "datetime",
                "set_datetime",
                {
                    "entity_id": entity_entry,
                    "datetime": tomorrow_9am.isoformat(),
                },
                blocking=False,
            )
            const.LOGGER.debug(
                "Advanced datetime helper for %s to %s",
                assignee_name,
                tomorrow_9am.isoformat(),
            )
