# File: select.py
# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Select entities for the ChoreOps integration.

Allows the user to pick from all chores, all rewards, or all penalties
in a global manner. This is useful for automations or scripts where a
user wishes to select a chore/reward/penalty dynamically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.select import SelectEntity
from homeassistant.helpers import entity_registry as er

from . import const
from .entity import ChoreOpsCoordinatorEntity
from .helpers.device_helpers import (
    create_assignee_device_info_from_coordinator,
    create_system_device_info,
)
from .helpers.entity_helpers import (
    should_create_entity,
    should_create_entity_for_user_assignee,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import ChoreOpsConfigEntry, ChoreOpsDataCoordinator
    from .type_defs import AssigneeData

# Platinum requirement: Parallel Updates
# Set to 0 (unlimited) for coordinator-based entities that don't poll
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreOpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ChoreOps select entities from a config entry."""
    coordinator = entry.runtime_data

    # Get flag states for entity creation decisions
    extra_enabled = entry.options.get(
        const.CONF_SHOW_LEGACY_ENTITIES, const.DEFAULT_SHOW_LEGACY_ENTITIES
    )

    selects: list[SelectEntity] = []

    # System-wide select entities (extra/legacy - disabled by default)
    # All 4 use EXTRA requirement: only created when show_legacy_entities is True
    if should_create_entity(
        const.SELECT_KC_UID_SUFFIX_CHORES_SELECT,
        extra_enabled=extra_enabled,
    ):
        selects.append(SystemChoresSelect(coordinator, entry))

    if should_create_entity(
        const.SELECT_KC_UID_SUFFIX_REWARDS_SELECT,
        extra_enabled=extra_enabled,
    ):
        selects.append(SystemRewardsSelect(coordinator, entry))

    if should_create_entity(
        const.SELECT_KC_UID_SUFFIX_PENALTIES_SELECT,
        extra_enabled=extra_enabled,
    ):
        selects.append(SystemPenaltiesSelect(coordinator, entry))

    if should_create_entity(
        const.SELECT_KC_UID_SUFFIX_BONUSES_SELECT,
        extra_enabled=extra_enabled,
    ):
        selects.append(SystemBonusesSelect(coordinator, entry))

    # System-wide dashboard helper select (always created)
    # Used by admin dashboard to select which assignee's data to display
    if should_create_entity(
        const.SELECT_KC_UID_SUFFIX_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE_SELECT,
    ):
        selects.append(SystemDashboardAdminAssigneeSelect(coordinator, entry))

    # Assignee-specific dashboard helper selects (always created)
    for assignee_id in coordinator.assignees_data:
        if should_create_entity_for_user_assignee(
            const.SELECT_KC_UID_SUFFIX_ASSIGNEE_DASHBOARD_HELPER_CHORES_SELECT,
            coordinator,
            assignee_id,
        ):
            selects.append(
                AssigneeDashboardHelperChoresSelect(coordinator, entry, assignee_id)
            )

    async_add_entities(selects)


class ChoreOpsSelectBase(ChoreOpsCoordinatorEntity, SelectEntity):
    """Base class for the ChoreOps select entities.

    Provides common select functionality for choosing chores, rewards, penalties,
    or bonuses from dropdown lists. Stores selected option and updates state.
    Used by both legacy system-wide selects and assignee-specific dashboard helpers.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_BASE

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ChoreOpsConfigEntry
    ):
        """Initialize the base select entity.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._selected_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option (chore/reward/penalty name)."""
        return self._selected_option

    async def async_select_option(self, option: str) -> None:
        """When the user selects an option from the dropdown, store it.

        Args:
            option: The selected option name (chore/reward/penalty/bonus name).
        """
        self._selected_option = option
        self.async_write_ha_state()

    def select_option(self, option: str) -> None:
        """Select an option (synchronous wrapper for abstract method)."""
        # This method is required by the SelectEntity abstract class
        # but Home Assistant will call async_select_option instead
        self._selected_option = option


class SystemChoresSelect(ChoreOpsSelectBase):
    """Global select entity listing all defined chores by name (legacy).

    NOTE: Legacy entity disabled by default. Provides system-wide chore selection
    for automations. Consider using assignee-specific selects for better organization.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_CHORES

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ChoreOpsConfigEntry
    ):
        """Initialize the Chores select entity.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"{entry.entry_id}{const.SELECT_KC_UID_SUFFIX_CHORES_SELECT}"
        )
        self._attr_name = (
            f"{const.CHOREOPS_TITLE}: {const.TRANS_KEY_SELECT_LABEL_ALL_CHORES}"
        )
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.SELECT_KC_PREFIX}{const.SELECT_KC_EID_SUFFIX_ALL_CHORES}"
        # )
        self._attr_device_info = create_system_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return a list of chore names from the coordinator."""
        return [
            chore_info.get(
                const.DATA_CHORE_NAME,
                f"{const.TRANS_KEY_LABEL_CHORE} {chore_id}",
            )
            for chore_id, chore_info in self.coordinator.chores_data.items()
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SELECT_CHORES,
        }


class SystemRewardsSelect(ChoreOpsSelectBase):
    """Global select entity listing all defined rewards by name (legacy).

    NOTE: Legacy entity disabled by default. Provides system-wide reward selection
    for automations. Consider using assignee-specific reward buttons for better organization.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_REWARDS

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ChoreOpsConfigEntry
    ):
        """Initialize the Rewards select entity.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"{entry.entry_id}{const.SELECT_KC_UID_SUFFIX_REWARDS_SELECT}"
        )
        self._attr_name = (
            f"{const.CHOREOPS_TITLE}: {const.TRANS_KEY_SELECT_LABEL_ALL_REWARDS}"
        )
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.SELECT_KC_PREFIX}{const.SELECT_KC_EID_SUFFIX_ALL_REWARDS}"
        # )
        self._attr_device_info = create_system_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return a list of reward names from the coordinator."""
        return [
            reward_info.get(
                const.DATA_REWARD_NAME,
                f"{const.TRANS_KEY_LABEL_REWARD} {reward_id}",
            )
            for reward_id, reward_info in self.coordinator.rewards_data.items()
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SELECT_REWARDS,
        }


class SystemPenaltiesSelect(ChoreOpsSelectBase):
    """Global select entity listing all defined penalties by name (legacy).

    NOTE: Legacy entity disabled by default. Provides system-wide penalty selection
    for automations. Consider using penalty buttons for better organization.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_PENALTIES

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ChoreOpsConfigEntry
    ):
        """Initialize the Penalties select entity.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"{entry.entry_id}{const.SELECT_KC_UID_SUFFIX_PENALTIES_SELECT}"
        )
        self._attr_name = (
            f"{const.CHOREOPS_TITLE}: {const.TRANS_KEY_SELECT_LABEL_ALL_PENALTIES}"
        )
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.SELECT_KC_PREFIX}{const.SELECT_KC_EID_SUFFIX_ALL_PENALTIES}"
        # )
        self._attr_device_info = create_system_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return a list of penalty names from the coordinator."""
        return [
            penalty_info.get(
                const.DATA_PENALTY_NAME,
                f"{const.TRANS_KEY_LABEL_PENALTY} {penalty_id}",
            )
            for penalty_id, penalty_info in self.coordinator.penalties_data.items()
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SELECT_PENALTIES,
        }


class SystemBonusesSelect(ChoreOpsSelectBase):
    """Global select entity listing all defined bonuses by name (legacy).

    NOTE: Legacy entity disabled by default. Provides system-wide bonus selection
    for automations. Consider using bonus buttons for better organization.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_BONUSES

    def __init__(
        self, coordinator: ChoreOpsDataCoordinator, entry: ChoreOpsConfigEntry
    ):
        """Initialize the Bonuses select entity.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = (
            f"{entry.entry_id}{const.SELECT_KC_UID_SUFFIX_BONUSES_SELECT}"
        )
        self._attr_name = (
            f"{const.CHOREOPS_TITLE}: {const.TRANS_KEY_SELECT_LABEL_ALL_BONUSES}"
        )
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.SELECT_KC_PREFIX}{const.SELECT_KC_EID_SUFFIX_ALL_BONUSES}"
        # )
        self._attr_device_info = create_system_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return a list of bonus names from the coordinator."""
        return [
            bonus_info.get(
                const.DATA_BONUS_NAME,
                f"{const.TRANS_KEY_LABEL_BONUS} {bonus_id}",
            )
            for bonus_id, bonus_info in self.coordinator.bonuses_data.items()
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            const.ATTR_PURPOSE: const.PURPOSE_SELECT_BONUSES,
        }


class SystemDashboardAdminAssigneeSelect(ChoreOpsSelectBase):
    """System-level select for choosing which assignee's data to display in admin dashboard.

    Provides a dropdown of all assignee names for admin dashboard cards to reference.
    Unlike assignee-specific selects, this is a single system-wide entity that allows
    admin view cards to dynamically target any assignee without hardcoded names.

    State contains the selected assignee's name (human-readable).
    Attributes provide the assignee's dashboard helper entity ID for efficient lookups,
    eliminating the need for expensive integration_entities() queries in cards.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
    ):
        """Initialize the SystemDashboardAdminAssigneeSelect.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}{const.SELECT_KC_UID_SUFFIX_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE_SELECT}"
        # System entity - no assignee-specific placeholders needed
        self._attr_device_info = create_system_device_info(entry)

    @property
    def options(self) -> list[str]:
        """Return a list of all assignee names with a 'None' option.

        Includes both regular assignees and shadow assignees (approver accounts) since
        admin dashboard operations apply to all assignee records regardless of type.
        Returns assignee names sorted alphabetically for consistent ordering.
        Prepends 'None' option to allow clearing selection.
        """
        # Collect all assignee names (including linked profiles)
        assignee_names = []
        for assignee_id, assignee_info in self.coordinator.assignees_data.items():
            assignee_name = assignee_info.get(
                const.DATA_USER_NAME,
                f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}",
            )
            assignee_names.append(assignee_name)

        # Sort alphabetically (case-insensitive)
        assignee_names.sort(key=str.lower)

        # Start with a "None" entry and add sorted assignees
        options = [const.SENTINEL_NONE_TEXT]
        options.extend(assignee_names)
        return options

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes including dashboard helper entity ID.

        Provides efficient lookup attributes for admin dashboard cards:
        - dashboard_helper_eid: Direct entity ID of selected assignee's dashboard helper
        - selected_assignee_slug: URL-safe slug of selected assignee's name
        - purpose: Translation key for filtering/identification

        Returns empty attributes when no assignee is selected.
        """
        # Get current selection
        current_value = self.current_option
        if not current_value or current_value == const.SENTINEL_NONE_TEXT:
            return {
                const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE,
            }

        # Find assignee_id by name
        selected_assignee_id = None
        for assignee_id, assignee_info in self.coordinator.assignees_data.items():
            assignee_name = assignee_info.get(
                const.DATA_USER_NAME,
                f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}",
            )
            if assignee_name == current_value:
                selected_assignee_id = assignee_id
                break

        # If assignee not found, return minimal attributes
        if not selected_assignee_id:
            return {
                const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE,
            }

        # Look up the actual dashboard helper entity from registry
        # Pattern: unique_id = {entry_id}_{assignee_id}_dashboard_helper
        registry = er.async_get(self.hass)
        dashboard_helper_unique_id = f"{self.coordinator.config_entry.entry_id}_{selected_assignee_id}{const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER}"

        dashboard_helper_entity = registry.async_get_entity_id(
            "sensor", const.DOMAIN, dashboard_helper_unique_id
        )

        # Build attributes with actual entity_id (if found) or None
        from homeassistant.util import slugify

        assignee_slug = slugify(current_value)

        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE,
            const.ATTR_DASHBOARD_HELPER_EID: dashboard_helper_entity,
            const.ATTR_SELECTED_ASSIGNEE_SLUG: assignee_slug,
            const.ATTR_SELECTED_ASSIGNEE_NAME: current_value,
        }


class AssigneeDashboardHelperChoresSelect(ChoreOpsSelectBase):
    """Select entity listing only the chores assigned to a specific assignee (dashboard helper).

    Filters chore list to show only assignments for this assignee. Used by dashboard
    automations to dynamically select assignee-specific chores. Includes 'None' option
    for clearing selection.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_SELECT_CHORES_ASSIGNEE

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
    ):
        """Initialize the AssigneeDashboardHelperChoresSelect.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee to filter chores.
        """
        super().__init__(coordinator, entry)
        self._assignee_id = assignee_id
        assignee_data: dict[str, Any] = cast(
            "dict[str, Any]", coordinator.assignees_data.get(assignee_id, {})
        )
        assignee_name = (
            assignee_data.get(const.DATA_USER_NAME)
            or f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}"
        )
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}{const.SELECT_KC_UID_SUFFIX_ASSIGNEE_DASHBOARD_HELPER_CHORES_SELECT}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: assignee_name
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = (
        #     f"{const.SELECT_KC_PREFIX}{assignee_name}{const.SELECT_KC_EID_SUFFIX_CHORE_LIST}"
        # )
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    @property
    def options(self) -> list[str]:
        """Return a list of chore names assigned to this assignee, with a 'None' option.

        Filters coordinator.chores_data to include only chores where assignee_id is in
        the assigned_assignees list. Prepends 'None' option for clearing selection.
        Returns chore names sorted alphabetically for consistent ordering.
        """
        # Collect chore names for this assignee
        chore_names = []
        for chore_id, chore_info in self.coordinator.chores_data.items():
            if self._assignee_id in chore_info.get(
                const.DATA_CHORE_ASSIGNED_ASSIGNEES, []
            ):
                chore_name = chore_info.get(
                    const.DATA_CHORE_NAME,
                    f"{const.TRANS_KEY_LABEL_CHORE} {chore_id}",
                )
                chore_names.append(chore_name)

        # Sort alphabetically (case-insensitive)
        chore_names.sort(key=str.lower)

        # Start with a "None" entry and add sorted chores
        options = [const.SENTINEL_NONE_TEXT]
        options.extend(chore_names)
        return options

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(self._assignee_id, {})
        )
        assignee_name = assignee_info.get(
            const.DATA_USER_NAME,
            f"{const.TRANS_KEY_LABEL_ASSIGNEE} {self._assignee_id}",
        )
        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_SELECT_ASSIGNEE_CHORES,
            const.ATTR_ASSIGNEE_NAME: assignee_name,
        }
