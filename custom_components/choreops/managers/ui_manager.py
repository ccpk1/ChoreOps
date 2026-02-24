"""UI Manager for ChoreOps dashboard and translation sensor features.

Responsible for:
- Translation sensor lifecycle (creation, lookup, cleanup)
- Datetime helper midnight bumping
- Dashboard language management

This manager owns all UI-related features that were previously in the Coordinator,
following the Platinum Architecture principle of Infrastructure-Only Coordinator.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .. import const
from .base_manager import BaseManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator


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

    async def ensure_translation_sensor_exists(self, lang_code: str) -> str:
        """Ensure a translation sensor exists for the given language code.

        If the sensor doesn't exist, creates it dynamically using the stored
        async_add_entities callback. Returns the entity ID.

        This is called when an assignee's dashboard language changes to a new language
        that doesn't have a translation sensor yet.

        Args:
            lang_code: ISO language code (e.g., 'en', 'es', 'de')

        Returns:
            The entity ID of the translation sensor (existing or newly created)
        """
        # Import here to avoid circular dependency
        from ..sensor import SystemDashboardTranslationSensor

        # Try to get entity ID from registry
        eid = self.get_translation_sensor_eid(lang_code)

        # If sensor already exists in registry, return the entity ID
        if eid:
            return eid

        # If sensor was marked as created but not in registry, use constructed entity_id
        if lang_code in self._translation_sensors_created:
            # Construct expected entity_id (sensor exists but not yet in registry)
            return (
                f"{const.SENSOR_KC_PREFIX}"
                f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
            )

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
            # Last resort: construct expected entity_id
            return (
                f"{const.SENSOR_KC_PREFIX}"
                f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
            )

        # Create the new translation sensor
        const.LOGGER.info(
            "Creating translation sensor for newly-used language: %s", lang_code
        )
        new_sensor = SystemDashboardTranslationSensor(
            self.coordinator, self.coordinator.config_entry, lang_code
        )
        self._sensor_add_entities_callback([new_sensor])
        self._translation_sensors_created.add(lang_code)

        # Return expected entity_id (sensor not yet in registry)
        return (
            f"{const.SENSOR_KC_PREFIX}"
            f"{const.SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}{lang_code}"
        )

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
                const.DATA_APPROVER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            )
            languages.add(lang)
        # Always include English as fallback
        languages.add(const.DEFAULT_DASHBOARD_LANGUAGE)
        return languages

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
