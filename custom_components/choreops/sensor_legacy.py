# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Legacy sensors for the ChoreOps integration.

This file contains optional legacy sensors that are maintained for backward compatibility.
These sensors are only created when CONF_SHOW_LEGACY_ENTITIES is enabled in config options.

Legacy sensors are candidates for deprecation in future versions as their data is now
available as attributes on modern sensor entities, providing better data organization
without entity clutter.

Available Legacy Sensors (13 total):

Assignee Chore Completion Sensors (4):
1. AssigneeChoreCompletionSensor - Total chores completed (data in AssigneeChoresSensor attributes)
2. AssigneeChoreCompletionDailySensor - Daily chores completed (data in AssigneeChoreCompletionSensor attributes)
3. AssigneeChoreCompletionWeeklySensor - Weekly chores completed (data in AssigneeChoreCompletionSensor attributes)
4. AssigneeChoreCompletionMonthlySensor - Monthly chores completed (data in AssigneeChoreCompletionSensor attributes)

Pending Approval Sensors (2):
5. SystemChoresPendingApprovalSensor - Pending chore approvals (global)
6. SystemRewardsPendingApprovalSensor - Pending reward approvals (global)

Assignee Points Earned Sensors (4):
7. AssigneePointsEarnedDailySensor - Daily points earned (data in AssigneePointsSensor attributes)
8. AssigneePointsEarnedWeeklySensor - Weekly points earned (data in AssigneePointsSensor attributes)
9. AssigneePointsEarnedMonthlySensor - Monthly points earned (data in AssigneePointsSensor attributes)
10. AssigneePointsMaxEverSensor - Maximum points ever reached (data in AssigneePointsSensor attributes)

Streak Sensor (1):
11. AssigneeChoreStreakSensor - Highest chore streak (data in AssigneePointsSensor attributes)

Bonus/Penalty Application Sensors (2):
12. AssigneePenaltyAppliedSensor - Penalty application count (data in dashboard helper bonuses/penalties list)
13. AssigneeBonusAppliedSensor - Bonus application count (data in dashboard helper bonuses/penalties list)
"""

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_registry import async_get

from . import const
from .coordinator import ChoreOpsDataCoordinator
from .entity import ChoreOpsCoordinatorEntity
from .helpers.device_helpers import (
    create_assignee_device_info_from_coordinator,
    create_system_device_info,
)
from .helpers.entity_helpers import get_assignee_name_by_id, get_friendly_label

if TYPE_CHECKING:
    from .type_defs import AssigneeData, BonusData, ChoreData, PenaltyData, RewardData

# Platinum requirement: Parallel Updates
# Set to 0 (unlimited) for coordinator-based entities that don't poll
PARALLEL_UPDATES = 0

# ------------------------------------------------------------------------------------------
# KID CHORE COMPLETION SENSORS
# ------------------------------------------------------------------------------------------


class AssigneeChoreCompletionSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking total chores completed by assignee since integration start.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_*'
    attributes on the AssigneeChoresSensor entity.

    Phase 4.5 Migration: Now uses 'completed' metric (work date) instead of 'approved' metric
    (approval date) for accurate work completion tracking.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_TOTAL_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ) -> None:
        """Initialize the legacy total chores sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_TOTAL_SENSOR}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the total number of chores completed by the assignee.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        v43+: Reads from chore_periods.all_time bucket (chore_stats deleted).
        """
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        # v43+: chore_stats deleted, use chore_periods.all_time
        # Cast to dict[str, Any] since chore_periods is a runtime-added bucket
        chore_periods: dict[str, Any] = cast(
            "dict[str, Any]", assignee_info.get(const.DATA_ASSIGNEE_CHORE_PERIODS, {})
        )
        all_time: dict[str, Any] = cast(
            "dict[str, Any]",
            chore_periods.get(const.DATA_ASSIGNEE_CHORE_DATA_PERIODS_ALL_TIME, {}),
        )
        return all_time.get(
            const.DATA_ASSIGNEE_CHORE_DATA_PERIOD_COMPLETED, const.DEFAULT_ZERO
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_ALL_TIME_EXTRA,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


class AssigneeChoreCompletionDailySensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed today.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_today'
    attribute on the AssigneeChoresSensor entity.

    Phase 4.5 Migration: Uses 'completed' metric (work date) instead of 'approved' metric.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_DAILY_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ) -> None:
        """Initialize the legacy daily chores sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_DAILY_SENSOR}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the number of chores completed today.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        return stats.get(const.PRES_ASSIGNEE_CHORES_COMPLETED_TODAY, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_TODAY_EXTRA,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


class AssigneeChoreCompletionWeeklySensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed this week.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_week'
    attribute on the AssigneeChoresSensor entity.

    Phase 4.5 Migration: Uses 'completed' metric (work date) instead of 'approved' metric.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_WEEKLY_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ) -> None:
        """Initialize the legacy weekly chores sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_WEEKLY_SENSOR}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the number of chores completed this week.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        return stats.get(const.PRES_ASSIGNEE_CHORES_COMPLETED_WEEK, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_WEEK_EXTRA,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


class AssigneeChoreCompletionMonthlySensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking chores completed this month.

    NOTE: This sensor is legacy/optional. Data is now available as 'chore_stat_chores_completed_month'
    attribute on the AssigneeChoresSensor entity.

    Phase 4.5 Migration: Uses 'completed' metric (work date) instead of 'approved' metric.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_CHORES_COMPLETED_MONTHLY_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ) -> None:
        """Initialize the legacy monthly chores sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR}"
        self._attr_native_unit_of_measurement = const.DEFAULT_CHORES_UNIT
        # Icon defined in icons.json
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_SUFFIX_CHORES_COMPLETED_MONTHLY_SENSOR}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the number of chores completed this month.

        Phase 4.5: Uses 'completed' metric (work date) for accurate tracking.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        return stats.get(const.PRES_ASSIGNEE_CHORES_COMPLETED_MONTH, const.DEFAULT_ZERO)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_APPROVALS_MONTH_EXTRA,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


# ------------------------------------------------------------------------------------------
# PENDING APPROVAL SENSORS
# ------------------------------------------------------------------------------------------


class SystemChoresPendingApprovalSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor listing all pending chore approvals."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENDING_CHORES_APPROVALS_SENSOR

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
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
        grouped_by_assignee: dict[str, list[dict[str, Any]]] = {}

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for approval in approvals:
            assignee_id = approval[const.DATA_ASSIGNEE_ID]
            chore_id = approval[const.DATA_CHORE_ID]
            assignee_name = (
                get_assignee_name_by_id(self.coordinator, assignee_id)
                or const.TRANS_KEY_DISPLAY_UNKNOWN_ASSIGNEE
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
                    approve_unique_id = f"{self._entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
                    disapprove_unique_id = f"{self._entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"

                    approve_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, approve_unique_id
                    )
                    disapprove_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, disapprove_unique_id
                    )
                except (KeyError, ValueError, AttributeError):
                    pass

            if assignee_name not in grouped_by_assignee:
                grouped_by_assignee[assignee_name] = []

            grouped_by_assignee[assignee_name].append(
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
        result.update(grouped_by_assignee)
        return result


class SystemRewardsPendingApprovalSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor listing all pending reward approvals (computed from assignee reward data).

    Note: Computed dynamically from assignee reward data structure, not from deprecated
    storage key. The reward data is stored per-assignee, and pending count is calculated
    at runtime from entries with pending_count > 0.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENDING_REWARDS_APPROVALS_SENSOR

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
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
        grouped_by_assignee: dict[str, list[dict[str, Any]]] = {}

        try:
            entity_registry = async_get(self.hass)
        except (KeyError, ValueError, AttributeError):
            entity_registry = None

        for approval in approvals:
            assignee_id = approval[const.DATA_ASSIGNEE_ID]
            reward_id = approval[const.DATA_REWARD_ID]
            assignee_name = (
                get_assignee_name_by_id(self.coordinator, assignee_id)
                or const.TRANS_KEY_DISPLAY_UNKNOWN_ASSIGNEE
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
                    approve_unique_id = f"{self._entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
                    disapprove_unique_id = f"{self._entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"

                    approve_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, approve_unique_id
                    )
                    disapprove_button_eid = entity_registry.async_get_entity_id(
                        "button", const.DOMAIN, disapprove_unique_id
                    )
                except (KeyError, ValueError, AttributeError):
                    pass

            if assignee_name not in grouped_by_assignee:
                grouped_by_assignee[assignee_name] = []

            grouped_by_assignee[assignee_name].append(
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
        result.update(grouped_by_assignee)
        return result


# ------------------------------------------------------------------------------------------
# KID POINTS EARNED SENSORS
# ------------------------------------------------------------------------------------------


class AssigneePointsEarnedDailySensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points an assignee earned today.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_today'
    attribute on the AssigneePointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return how many net points the assignee has earned so far today.

        Phase 7.5: Uses presentation cache instead of persisted stats.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        value = stats.get(const.PRES_ASSIGNEE_POINTS_NET_TODAY, const.DEFAULT_ZERO)
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
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


class AssigneePointsEarnedWeeklySensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points an assignee earned this week.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_week'
    attribute on the AssigneePointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return how many net points the assignee has earned this week.

        Phase 7.5: Uses presentation cache instead of persisted stats.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        value = stats.get(const.PRES_ASSIGNEE_POINTS_NET_WEEK, const.DEFAULT_ZERO)
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
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


class AssigneePointsEarnedMonthlySensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor for how many net points an assignee earned this month.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_points_net_month'
    attribute on the AssigneePointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return how many net points the assignee has earned this month.

        Phase 7.5: Uses presentation cache instead of persisted stats.
        """
        stats = self.coordinator.statistics_manager.get_stats(self._assignee_id)
        value = stats.get(const.PRES_ASSIGNEE_POINTS_NET_MONTH, const.DEFAULT_ZERO)
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
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


class AssigneePointsMaxEverSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor showing the maximum points an assignee has ever reached.

    NOTE: This sensor is legacy/optional. Data is now available as 'point_stat_highest_balance'
    attribute on the AssigneePointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_MAX_POINTS_EVER_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry,
        assignee_id: str,
        assignee_name: str,
        points_label: str,
        points_icon: str,
    ) -> None:
        """Initialize the legacy max points sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            points_label: Customizable label for points currency.
            points_icon: Customizable icon for points display.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._points_label = points_label
        self._points_icon = points_icon
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_MAX_POINTS_EVER_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_POINTS: points_label,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the highest points total the assignee has ever reached."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        # Read highest_balance from point_periods.all_time.all_time (v43+)
        periods: dict[str, Any] = assignee_info.get(
            const.DATA_ASSIGNEE_POINT_PERIODS, {}
        )
        all_time_periods: dict[str, Any] = periods.get(
            const.DATA_ASSIGNEE_POINT_PERIODS_ALL_TIME, {}
        )
        all_time_bucket: dict[str, Any] = all_time_periods.get(
            const.DATA_ASSIGNEE_POINT_PERIODS_ALL_TIME, {}
        )
        value = all_time_bucket.get(
            const.DATA_ASSIGNEE_POINT_PERIOD_HIGHEST_BALANCE, const.DEFAULT_ZERO
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
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
        }


# ------------------------------------------------------------------------------------------
# STREAK SENSOR
# ------------------------------------------------------------------------------------------


class AssigneeChoreStreakSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor returning the highest current streak among streak-type achievements for an assignee.

    NOTE: This sensor is legacy/optional. Data is now available as chore_stats attributes
    on the AssigneePointsSensor entity.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_ASSIGNEE_HIGHEST_STREAK_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_HIGHEST_STREAK_SENSOR}"
        # No unit of measurement - streak is a count, not a duration
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # Legacy entity_id template kept as a comment-only reference
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> int:
        """Return the highest current streak among all streak achievements for the assignee.

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
                progress_for_assignee = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(self._assignee_id)
                if isinstance(progress_for_assignee, dict):
                    current_streak = progress_for_assignee.get(
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
                progress_for_assignee = achievement.get(
                    const.DATA_ACHIEVEMENT_PROGRESS, {}
                ).get(self._assignee_id)

                if isinstance(progress_for_assignee, dict):
                    streaks[achievement_name] = progress_for_assignee.get(
                        const.DATA_ACHIEVEMENT_CURRENT_STREAK, const.DEFAULT_ZERO
                    )

                elif isinstance(progress_for_assignee, int):
                    streaks[achievement_name] = progress_for_assignee

        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_CHORE_STREAK_EXTRA,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_STREAKS_BY_ACHIEVEMENT: streaks,
        }

    @property
    def icon(self) -> str | None:
        """Return an icon for 'highest streak'."""
        return None  # Icon defined in icons.json


# ------------------------------------------------------------------------------------------
# KID BONUS/PENALTY APPLICATION SENSORS (LEGACY - Data available in dashboard helper)
# ------------------------------------------------------------------------------------------


class AssigneePenaltyAppliedSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking how many times each penalty has been applied to an assignee.

    NOTE: This sensor is legacy/optional. Data is now available in the dashboard helper
    sensor's penalties attribute list. This sensor is maintained for backward compatibility.

    Migration Path:
    - Dashboard helper: penalties[].application_count
    - Direct access: coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_PENALTY_APPLIES][penalty_id]

    Counts penalty applications for individual assignee/penalty combinations. Provides penalty
    metadata including points deducted, description, and button entity ID for UI integration.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_PENALTY_APPLIES_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
        penalty_id: str,
        penalty_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            penalty_id: Unique identifier for the penalty.
            penalty_name: Display name of the penalty.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._penalty_id = penalty_id
        self._penalty_name = penalty_name

        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_PENALTY_NAME: penalty_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_PENALTY_APPLIES_SENSOR}{penalty_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the number of times the penalty has been applied."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        penalty_applies = assignee_info.get(const.DATA_ASSIGNEE_PENALTY_APPLIES, {})
        penalty_entry = penalty_applies.get(self._penalty_id)
        if not penalty_entry:
            return const.DEFAULT_ZERO

        periods = penalty_entry.get(const.DATA_ASSIGNEE_PENALTY_PERIODS, {})
        return self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_PENALTY_PERIOD_APPLIES,
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

        # Get the ApproverPenaltyApplyButton entity_id
        penalty_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{self._penalty_id}{const.BUTTON_KC_UID_SUFFIX_APPROVER_PENALTY_APPLY}"
            penalty_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_PENALTY_APPLIED,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
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


class AssigneeBonusAppliedSensor(ChoreOpsCoordinatorEntity, SensorEntity):
    """Legacy sensor tracking how many times each bonus has been applied to an assignee.

    NOTE: This sensor is legacy/optional. Data is now available in the dashboard helper
    sensor's bonuses attribute list. This sensor is maintained for backward compatibility.

    Migration Path:
    - Dashboard helper: bonuses[].application_count
    - Direct access: coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_BONUS_APPLIES][bonus_id]

    Counts bonus applications for individual assignee/bonus combinations. Provides bonus
    metadata including points awarded, description, and button entity ID for UI integration.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = const.TRANS_KEY_SENSOR_BONUS_APPLIES_SENSOR

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ConfigEntry,
        assignee_id: str,
        assignee_name: str,
        bonus_id: str,
        bonus_name: str,
    ):
        """Initialize the sensor.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            bonus_id: Unique identifier for the bonus.
            bonus_name: Display name of the bonus.
        """
        super().__init__(coordinator)
        # Enable/disable based on config option
        show_legacy = entry.options.get(const.CONF_SHOW_LEGACY_ENTITIES, False)
        self._attr_entity_registry_enabled_default = show_legacy
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._bonus_id = bonus_id
        self._bonus_name = bonus_name

        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_SENSOR_ATTR_BONUS_NAME: bonus_name,
        }
        # Strip redundant "bonus" suffix from entity_id (bonus_name often ends with "Bonus")
        bonus_slug = bonus_name.lower().replace(" ", "_")
        bonus_slug = bonus_slug.removesuffix("_bonus")  # Remove "_bonus" suffix
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.SENSOR_KC_PREFIX}{assignee_name}{const.SENSOR_KC_EID_MIDFIX_BONUS_APPLIES_SENSOR}{bonus_slug}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def native_value(self) -> Any:
        """Return the number of times the bonus has been applied."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        bonus_applies = assignee_info.get(const.DATA_ASSIGNEE_BONUS_APPLIES, {})
        bonus_entry = bonus_applies.get(self._bonus_id)
        if not bonus_entry:
            return const.DEFAULT_ZERO

        periods = bonus_entry.get(const.DATA_ASSIGNEE_BONUS_PERIODS, {})
        return self.coordinator.stats.get_period_total(
            periods,
            const.PERIOD_ALL_TIME,
            const.DATA_ASSIGNEE_BONUS_PERIOD_APPLIES,
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

        # Get the ApproverBonusApplyButton entity_id
        bonus_button_eid = None
        try:
            entity_registry = async_get(self.hass)
            unique_id = f"{self._entry.entry_id}_{self._assignee_id}_{self._bonus_id}{const.BUTTON_KC_UID_SUFFIX_APPROVER_BONUS_APPLY}"
            bonus_button_eid = entity_registry.async_get_entity_id(
                "button", const.DOMAIN, unique_id
            )
        except (KeyError, ValueError, AttributeError):
            pass

        return {
            const.ATTR_PURPOSE: const.PURPOSE_SENSOR_BONUS_APPLIED,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
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
