# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Legacy sensors for the KidsChores integration.

This file contains optional legacy sensors that are maintained for backward compatibility.
These sensors are only created when CONF_SHOW_LEGACY_ENTITIES is enabled in config options.

Legacy sensors are candidates for deprecation in future versions as their data is now
available as attributes on modern sensor entities, providing better data organization
without entity clutter.

Available Legacy Sensors (13 total):

Kid Chore Completion Sensors (4):
1. KidChoreCompletionSensor - Total chores completed (data in KidChoresSensor attributes)
2. KidChoreCompletionDailySensor - Daily chores completed (data in KidChoreCompletionSensor attributes)
3. KidChoreCompletionWeeklySensor - Weekly chores completed (data in KidChoreCompletionSensor attributes)
4. KidChoreCompletionMonthlySensor - Monthly chores completed (data in KidChoreCompletionSensor attributes)

Pending Approval Sensors (2):
5. SystemChoresPendingApprovalSensor - Pending chore approvals (global)
6. SystemRewardsPendingApprovalSensor - Pending reward approvals (global)

Kid Points Earned Sensors (4):
7. KidPointsEarnedDailySensor - Daily points earned (data in KidPointsSensor attributes)
8. KidPointsEarnedWeeklySensor - Weekly points earned (data in KidPointsSensor attributes)
9. KidPointsEarnedMonthlySensor - Monthly points earned (data in KidPointsSensor attributes)
10. KidPointsMaxEverSensor - Maximum points ever reached (data in KidPointsSensor attributes)

Streak Sensor (1):
11. KidChoreStreakSensor - Highest chore streak (data in KidPointsSensor attributes)

Bonus/Penalty Application Sensors (2):
12. KidPenaltyAppliedSensor - Penalty application count (data in dashboard helper bonuses/penalties list)
13. KidBonusAppliedSensor - Bonus application count (data in dashboard helper bonuses/penalties list)
"""

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_registry import async_get

from . import const
from .coordinator import KidsChoresDataCoordinator
from .entity import KidsChoresCoordinatorEntity
from .helpers.device_helpers import (
    create_kid_device_info_from_coordinator,
    create_system_device_info,
)
from .helpers.entity_helpers import get_friendly_label, get_kid_name_by_id

if TYPE_CHECKING:
    from .type_defs import BonusData, ChoreData, KidData, PenaltyData, RewardData

# Platinum requirement: Parallel Updates
# Set to 0 (unlimited) for coordinator-based entities that don't poll
PARALLEL_UPDATES = 0

# ------------------------------------------------------------------------------------------
# KID CHORE COMPLETION SENSORS
# ------------------------------------------------------------------------------------------


class KidChoreCompletionSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking total chores completed by kid since integration start.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_*'
    attributes on the KidChoresSensor entity.

    Phase 4.5 Migration: Now uses 'completed' metric (work date) instead of 'approved' metric
    (approval date) for accurate work completion tracking.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_TOTAL_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy total chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_TOTAL_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the total number of chores completed by the kid.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        v43+: Reads from chore_periods.all_time bucket (chore_stats deleted).
        """
        kid_info: KidData = cast(
            "KidData", self.coordinator.kids_data.get(self._kid_id, {})
        )
        # v43+: chore_stats deleted, use chore_periods.all_time
        # Cast to dict[str, Any] since chore_periods is a runtime-added bucket
        chore_periods: dict[str, Any] = cast(
            "dict[str, Any]", kid_info.get(const.DATA_KID_CHORE_PERIODS, {})
        )
        all_time: dict[str, Any] = cast(
            "dict[str, Any]",
            chore_periods.get(const.DATA_KID_CHORE_DATA_PERIODS_ALL_TIME, {}),
        )
        return all_time.get(
            const.DATA_KID_CHORE_DATA_PERIOD_COMPLETED, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_ALL_TIME_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidChoreCompletionDailySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed today.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_today'
    attribute on the KidChoresSensor entity.

    Phase 4.5 Migration: Uses 'completed' metric (work date) instead of 'approved' metric.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_DAILY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy daily chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_DAILY_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the number of chores completed today.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._kid_id)
        return stats.get(const.PRES_KID_CHORES_COMPLETED_TODAY, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_TODAY_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidChoreCompletionWeeklySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed this week.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_week'
    attribute on the KidChoresSensor entity.

    Phase 4.5 Migration: Uses 'completed' metric (work date) instead of 'approved' metric.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_WEEKLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy weekly chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_WEEKLY_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the number of chores completed this week.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._kid_id)
        return stats.get(const.PRES_KID_CHORES_COMPLETED_WEEK, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_WEEK_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidChoreCompletionMonthlySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed this month.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_month'
    attribute on the KidChoresSensor entity.

    Phase 4.5 Migration: Uses 'completed' metric (work date) instead of 'approved' metric.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_MONTHLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the legacy monthly chores sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_MONTHLY_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the number of chores completed this month.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._kid_id)
        return stats.get(const.PRES_KID_CHORES_COMPLETED_MONTH, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_MONTH_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


# ------------------------------------------------------------------------------------------
# PENDING APPROVAL SENSORS
# ------------------------------------------------------------------------------------------


class SystemChoresPendingApprovalSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor listing all pending chore approvals."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENDING_CHORES_APPROVALS_SENSOR

    def __init__(
        self, coordinator: KidsChoresDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        # Icon defined in icons.json
        self._attr_native_unit_of_measurement = const.DEFAULT_PENDING_CHORES_UNIT
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        self._attr_device_info = create_system_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return a summary of pending chore approvals."""
        approvals = self.coordinator.chore_manager.pending_chore_approvals
        return f"{len(approvals)}"

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, Any]]]:
        """Return detailed pending chores."""
        approvals = self.coordinator.chore_manager.pending_chore_approvals
        grouped_by_kid: dict[str, list[dict[str, Any]]] = {}

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for approval in approvals:
            kid_id = approval[const.DATA_KID_ID]
            chore_id = approval[const.DATA_CHORE_ID]
            kid_name = (
                get_kid_name_by_id(self.coordinator, kid_id)
                or const.TRANS_KEY_DISPLAY_UNKNOWN_KID
            )
            chore_info: ChoreData = cast(
                "ChoreData", self.coordinator.chores_data.get(chore_id, {})
            )
            chore_name = chore_info.get(
                const.DATA_CHORE_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_CHORE
            )

            timestamp = approval[const.DATA_CHORE_TIMESTAMP]

            # Get approve and disapprove button entity IDs using direct lookup
            approve_button_eid = None
            disapprove_button_eid = None
            if entity_registry:
                try:
                    approve_unique_id = f"{self._entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
                    disapprove_unique_id = f"{self._entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"

                    approve_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, approve_unique_id
                    )
                    disapprove_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, disapprove_unique_id
                    )
                except (KeyError, ValueError, AttributeError):
                    pass

            if kid_name not in grouped_by_kid:
                grouped_by_kid[kid_name] = []

            grouped_by_kid[kid_name].append(
                {
                    const.ATTR_CHORE_NAME: chore_name,
                    const.ATTR_CLAIMED_ON: timestamp,
                    const.ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID: approve_button_eid,
                    const.ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID: disapprove_button_eid,
                }
            )

        # Add purpose at top level before returning
        result: dict[str, Any] = {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORES_PENDING_APPROVAL_EXTRA,
        }
        result.update(grouped_by_kid)
        return result


class SystemRewardsPendingApprovalSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor listing all pending reward approvals (computed from kid reward data).

    Note: Computed dynamically from kid_reward_data structure, not from deprecated
    storage key. The reward data is stored per-kid, and pending count is calculated
    at runtime from entries with pending_count > 0.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENDING_REWARDS_APPROVALS_SENSOR

    def __init__(
        self, coordinator: KidsChoresDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
        # Icon defined in icons.json
        self._attr_native_unit_of_measurement = const.DEFAULT_PENDING_REWARDS_UNIT
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{const.SENSOR_KC_EID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
        self._attr_device_info = create_system_device_info(entry)

    @property
    def native_value(self) -> str:
        """Return a summary of pending reward approvals."""
        approvals = self.coordinator.reward_manager.get_pending_approvals()
        return f"{len(approvals)}"

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, Any]]]:
        """Return detailed pending rewards."""
        approvals = self.coordinator.reward_manager.get_pending_approvals()
        grouped_by_kid: dict[str, list[dict[str, Any]]] = {}

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for approval in approvals:
            kid_id = approval[const.DATA_KID_ID]
            reward_id = approval[const.DATA_REWARD_ID]
            kid_name = (
                get_kid_name_by_id(self.coordinator, kid_id)
                or const.TRANS_KEY_DISPLAY_UNKNOWN_KID
            )
            reward_info: RewardData = cast(
                "RewardData", self.coordinator.rewards_data.get(reward_id, {})
            )
            reward_name = reward_info.get(
                const.DATA_REWARD_NAME, const.TRANS_KEY_DISPLAY_UNKNOWN_REWARD
            )

            timestamp = approval[const.DATA_REWARD_TIMESTAMP]

            # Get approve and disapprove button entity IDs using direct lookup
            approve_button_eid = None
            disapprove_button_eid = None
            if entity_registry:
                try:
                    approve_unique_id = f"{self._entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
                    disapprove_unique_id = f"{self._entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"

                    approve_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, approve_unique_id
                    )
                    disapprove_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, disapprove_unique_id
                    )
                except (KeyError, ValueError, AttributeError):
                    pass

            if kid_name not in grouped_by_kid:
                grouped_by_kid[kid_name] = []

            grouped_by_kid[kid_name].append(
                {
                    const.ATTR_REWARD_NAME: reward_name,
                    const.ATTR_REDEEMED_ON: timestamp,
                    const.ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID: approve_button_eid,
                    const.ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID: disapprove_button_eid,
                }
            )

        # Add purpose at top level before returning
        result: dict[str, Any] = {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_REWARDS_PENDING_APPROVAL_EXTRA,
        }
        result.update(grouped_by_kid)
        return result


# ------------------------------------------------------------------------------------------
# KID POINTS EARNED SENSORS
# ------------------------------------------------------------------------------------------


class KidPointsEarnedDailySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points a kid earned today.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_today'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_EARNED_DAILY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_EARNED_DAILY_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return how many net points the kid has earned so far today.

        Phase 7.5: Uses presentation cache instead of persisted stats.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._kid_id)
        value = stats.get(const.PRES_KID_POINTS_NET_TODAY, const.DEFAULT_ZERO)
        return int(cast("float | int", value))

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Use the points' custom icon if set, else fallback."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_POINTS_EARNED_TODAY_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidPointsEarnedWeeklySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points a kid earned this week.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_week'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_EARNED_WEEKLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_EARNED_WEEKLY_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return how many net points the kid has earned this week.

        Phase 7.5: Uses presentation cache instead of persisted stats.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._kid_id)
        value = stats.get(const.PRES_KID_POINTS_NET_WEEK, const.DEFAULT_ZERO)
        return int(cast("float | int", value))

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Use the points' custom icon if set, else fallback."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_POINTS_EARNED_WEEK_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidPointsEarnedMonthlySensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points a kid earned this month.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_month'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_POINTS_EARNED_MONTHLY_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_POINTS_EARNED_MONTHLY_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return how many net points the kid has earned this month.

        Phase 7.5: Uses presentation cache instead of persisted stats.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._kid_id)
        value = stats.get(const.PRES_KID_POINTS_NET_MONTH, const.DEFAULT_ZERO)
        return int(cast("float | int", value))

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the points label."""
        return self._points_label or const.LABEL_POINTS

    @property
    def icon(self) -> str:
        """Use the points' custom icon if set, else fallback."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_POINTS_EARNED_MONTH_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


class KidPointsMaxEverSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor showing the maximum points a kid has ever reached.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_highest_balance'
    attribute on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_MAX_POINTS_EVER_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry,
        kid_id: str,
        kid_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the legacy max points sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_MAX_POINTS_EVER_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_POINTS: points_label,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_MAX_POINTS_EARNED_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the highest points total the kid has ever reached."""
        kid_info: KidData = cast(
            "KidData", self.coordinator.kids_data.get(self._kid_id, {})
        )
        # Read highest_balance from point_periods.all_time.all_time (v43+)
        periods: dict[str, Any] = kid_info.get(const.DATA_KID_POINT_PERIODS, {})
        all_time_periods: dict[str, Any] = periods.get(
            const.DATA_KID_POINT_PERIODS_ALL_TIME, {}
        )
        all_time_bucket: dict[str, Any] = all_time_periods.get(
            const.DATA_KID_POINT_PERIODS_ALL_TIME, {}
        )
        value = all_time_bucket.get(
            const.DATA_KID_POINT_PERIOD_HIGHEST_BALANCE, const.DEFAULT_ZERO
        )
        return int(value)

    @property
    def icon(self) -> str:
        """Use the same icon as points or any custom icon you prefer."""
        return self._points_icon or const.DEFAULT_POINTS_ICON

    @property
    def native_unit_of_measurement(self) -> str:
        """Optionally display the same points label for consistency."""
        return self._points_label or const.LABEL_POINTS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_POINTS_MAX_EVER_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
        }


# ------------------------------------------------------------------------------------------
# STREAK SENSOR
# ------------------------------------------------------------------------------------------


class KidChoreStreakSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor returning the highest current streak among streak-type achievements for a kid.

    NOTE: This sensor is legacy/optional. Data is now available as chore_stats attributes
    on the KidPointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_KID_HIGHEST_STREAK_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}{const.SENSOR_KC_UID_SUFFIX_KID_HIGHEST_STREAK_SENSOR}"
        # No unit of measurement - streak is a count, not a duration
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_SUFFIX_KID_HIGHEST_STREAK_SENSOR}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the highest current streak among all streak achievements for the kid.

        v43+: chore_stats deleted. Streak data now comes from achievement progress.
        For backward compatibility, we return 0 if no streak achievements exist.
        """
        # v43+: chore_stats deleted - longest_streak_all_time was never truly persistent
        # This sensor now returns the maximum streak from achievement progress
        max_streak = 0
        for achievement in self.coordinator.achievements_data.values():
            if (
                achievement.get(const.DATA_ACHIEVEMENT_TYPE)
                == const.ACHIEVEMENT_TYPE_STREAK
            ):
                progress_for_kid = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(self._kid_id)
                if isinstance(progress_for_kid, dict):
                    current_streak = progress_for_kid.get(
                        const.DATA_ACHIEVEMENT_CURRENT_STREAK, 0
                    )
                    max_streak = max(max_streak, current_streak)
        return max_streak

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes including individual streaks per achievement."""
        streaks: dict[str, int] = {}
        for achievement in self.coordinator.achievements_data.values():
            if (
                achievement.get(const.DATA_ACHIEVEMENT_TYPE)
                == const.ACHIEVEMENT_TYPE_STREAK
            ):
                achievement_name = achievement.get(
                    const.DATA_ACHIEVEMENT_NAME, const.DISPLAY_UNKNOWN
                )
                progress_for_kid = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(self._kid_id)

                if isinstance(progress_for_kid, dict):
                    streaks[achievement_name] = progress_for_kid.get(
                        const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                    )

                elif isinstance(progress_for_kid, int):
                    streaks[achievement_name] = progress_for_kid

        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_STREAK_EXTRA,
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_STREAKS_BY_ACHIEVEMENT: streaks,
        }

    @property
    def icon(self) -> str | None:
        """Return an icon for 'highest streak'."""
        return None  # Icon defined in icons.json


# ------------------------------------------------------------------------------------------
# KID BONUS/PENALTY APPLICATION SENSORS (LEGACY - Data available in dashboard helper)
# ------------------------------------------------------------------------------------------


class KidPenaltyAppliedSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking how many times each penalty has been applied to a kid.

    NOTE: This sensor is legacy/optional. Data is now available in the dashboard helper
    sensor's penalties attribute list. This sensor is maintained for backward compatibility.

    Migration Path:
    - Dashboard helper: penalties[].application_count
    - Direct access: coordinator.kids_data[kid_id][DATA_KID_PENALTY_APPLIES][penalty_id]

    Counts penalty applications for individual kid/penalty combinations. Provides penalty
    metadata including points deducted, description, and button entity ID for UI integration.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENALTY_APPLIES_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        penalty_id: str,
        penalty_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            penalty_id: Unique identifier for the penalty.
            penalty_name: Display name of the penalty.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._penalty_id = penalty_id
        self._penalty_name = penalty_name

        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_PENALTY_NAME: penalty_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_PENALTY_APPLIES_SENSOR}{penalty_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the number of times the penalty has been applied."""
        kid_info: KidData = cast(
            "KidData", self.coordinator.kids_data.get(self._kid_id, {})
        )
        penalty_applies = kid_info.get(const.DATA_KID_PENALTY_APPLIES, {})
        penalty_entry = penalty_applies.get(self._penalty_id)
        if not penalty_entry:
            return const.DEFAULT_ZERO

        periods = penalty_entry.get(const.DATA_KID_PENALTY_PERIODS, {})
        return self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_KID_PENALTY_PERIOD_APPLIES,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose additional details like penalty points and description."""
        penalty_info: PenaltyData = cast(
            "PenaltyData", self.coordinator.penalties_data.get(self._penalty_id, {})
        )

        stored_labels = penalty_info.get(const.DATA_PENALTY_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        # Get the ParentPenaltyApplyButton entity_id
        penalty_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            unique_id = f"{self._entry.entry_id}_{self._kid_id}_{self._penalty_id}{const.BUTTON_KC_UID_SUFFIX_PARENT_PENALTY_APPLY}"
            penalty_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_PENALTY_APPLIED,
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_PENALTY_NAME: self._penalty_name,
            const.ATTR_DESCRIPTION: penalty_info.get(
                const.DATA_PENALTY_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_PENALTY_POINTS: penalty_info.get(
                const.DATA_PENALTY_POINTS, const.DEFAULT_PENALTY_POINTS
            ),
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_PENALTY_BUTTON_EID: penalty_button_eid,
        }

    @property
    def icon(self):
        """Return the chore's custom icon if set, else fallback."""
        penalty_info: PenaltyData = cast(
            "PenaltyData", self.coordinator.penalties_data.get(self._penalty_id, {})
        )
        return penalty_info.get(const.DATA_PENALTY_ICON, const.SENTINEL_EMPTY)


class KidBonusAppliedSensor(KidsChoresCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking how many times each bonus has been applied to a kid.

    NOTE: This sensor is legacy/optional. Data is now available in the dashboard helper
    sensor's bonuses attribute list. This sensor is maintained for backward compatibility.

    Migration Path:
    - Dashboard helper: bonuses[].application_count
    - Direct access: coordinator.kids_data[kid_id][DATA_KID_BONUS_APPLIES][bonus_id]

    Counts bonus applications for individual kid/bonus combinations. Provides bonus
    metadata including points awarded, description, and button entity ID for UI integration.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_BONUS_APPLIES_SENSOR

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: ConfigEntry,
        kid_id: str,
        kid_name: str,
        bonus_id: str,
        bonus_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            bonus_id: Unique identifier for the bonus.
            bonus_name: Display name of the bonus.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._bonus_id = bonus_id
        self._bonus_name = bonus_name

        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_SENSOR_ATTR_BONUS_NAME: bonus_name,
        }
        # Strip redundant "bonus" suffix from entity_id (bonus_name often ends with "Bonus")
        bonus_slug = bonus_name.lower().replace(" ", "_")
        bonus_slug = bonus_slug.removesuffix("_bonus")  # Remove "_bonus" suffix
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{kid_name}{const.SENSOR_KC_EID_MIDFIX_BONUS_APPLIES_SENSOR}{bonus_slug}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the number of times the bonus has been applied."""
        kid_info: KidData = cast(
            "KidData", self.coordinator.kids_data.get(self._kid_id, {})
        )
        bonus_applies = kid_info.get(const.DATA_KID_BONUS_APPLIES, {})
        bonus_entry = bonus_applies.get(self._bonus_id)
        if not bonus_entry:
            return const.DEFAULT_ZERO

        periods = bonus_entry.get(const.DATA_KID_BONUS_PERIODS, {})
        return self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_KID_BONUS_PERIOD_APPLIES,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose additional details like bonus points and description."""
        bonus_info: BonusData = cast(
            "BonusData", self.coordinator.bonuses_data.get(self._bonus_id, {})
        )

        stored_labels = bonus_info.get(const.DATA_BONUS_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        # Get the ParentBonusApplyButton entity_id
        bonus_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            unique_id = f"{self._entry.entry_id}_{self._kid_id}_{self._bonus_id}{const.BUTTON_KC_UID_SUFFIX_PARENT_BONUS_APPLY}"
            bonus_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_BONUS_APPLIED,
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_BONUS_NAME: self._bonus_name,
            const.ATTR_DESCRIPTION: bonus_info.get(
                const.DATA_BONUS_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.ATTR_BONUS_POINTS: bonus_info.get(
                const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS
            ),
            const.ATTR_LABELS: friendly_labels,
            const.ATTR_BONUS_BUTTON_EID: bonus_button_eid,
        }

    @property
    def icon(self):
        """Return the bonus's custom icon if set, else fallback."""
        bonus_info: BonusData = cast(
            "BonusData", self.coordinator.bonuses_data.get(self._bonus_id, {})
        )
        return bonus_info.get(const.DATA_BONUS_ICON, const.SENTINEL_EMPTY)
