# File: button.py
# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Buttons for ChoreOps integration.

Features:
1) Chore Buttons (Claim & Approve) with user-defined or default icons.
2) Reward Buttons using user-defined or default icons.
3) Penalty Buttons using user-defined or default icons.
4) Bonus Buttons using user-defined or default icons.
5) ApproverPointsAdjustButton: manually increments/decrements a assignee's points.
6) ApproverRewardApproveButton: allows approvers to approve rewards claimed by assignees.

"""

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import const
from .coordinator import ChoreOpsConfigEntry, ChoreOpsDataCoordinator
from .entity import ChoreOpsCoordinatorEntity
from .helpers.auth_helpers import (
    AUTH_ACTION_APPROVAL,
    AUTH_ACTION_MANAGEMENT,
    AUTH_ACTION_PARTICIPATION,
    is_kiosk_mode_enabled,
    is_user_authorized_for_action,
)
from .helpers.device_helpers import create_assignee_device_info_from_coordinator
from .helpers.entity_helpers import (
    get_assignee_name_by_id,
    get_friendly_label,
    is_linked_profile,
    should_create_entity,
    should_create_gamification_entities,
    should_create_workflow_buttons,
)

if TYPE_CHECKING:
    from .type_defs import AssigneeData, BonusData, ChoreData, PenaltyData, RewardData

# Platinum requirement: Parallel Updates
# Set to 1 (serialized) for action buttons that modify state
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChoreOpsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up dynamic buttons."""
    coordinator = entry.runtime_data

    points_label = entry.options.get(
        const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
    )

    entities: list[ButtonEntity] = []

    # Create buttons for chores (Claim, Approve & Disapprove)
    for chore_id, chore_info in coordinator.chores_data.items():
        chore_name = chore_info.get(
            const.DATA_CHORE_NAME, f"{const.TRANS_KEY_LABEL_CHORE} {chore_id}"
        )
        assigned_assignees_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])

        # If user defined an icon, use it; else fallback to SENTINEL_EMPTY for chore claim
        chore_claim_icon = chore_info.get(const.DATA_CHORE_ICON, const.SENTINEL_EMPTY)
        # For "approve," use a distinct icon
        chore_approve_icon = chore_info.get(const.DATA_CHORE_ICON, const.SENTINEL_EMPTY)

        for assignee_id in assigned_assignees_ids:
            assignee_name = (
                get_assignee_name_by_id(coordinator, assignee_id)
                or f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}"
            )

            # Get flag states for unified entity creation decisions
            is_linked_profile_user = is_linked_profile(coordinator, assignee_id)
            workflow_enabled = should_create_workflow_buttons(coordinator, assignee_id)
            gamification_enabled = should_create_gamification_entities(
                coordinator, assignee_id
            )

            # Claim Button - WORKFLOW requirement
            if should_create_entity(
                const.BUTTON_KC_UID_SUFFIX_CLAIM,
                is_feature_gated_profile=is_linked_profile_user,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
            ):
                entities.append(
                    AssigneeChoreClaimButton(
                        coordinator=coordinator,
                        entry=entry,
                        assignee_id=assignee_id,
                        assignee_name=assignee_name,
                        chore_id=chore_id,
                        chore_name=chore_name,
                        icon=chore_claim_icon,
                    )
                )

            # Approve Button - ALWAYS requirement
            if should_create_entity(
                const.BUTTON_KC_UID_SUFFIX_APPROVE,
                is_feature_gated_profile=is_linked_profile_user,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
            ):
                entities.append(
                    ApproverChoreApproveButton(
                        coordinator=coordinator,
                        entry=entry,
                        assignee_id=assignee_id,
                        assignee_name=assignee_name,
                        chore_id=chore_id,
                        chore_name=chore_name,
                        icon=chore_approve_icon,
                    )
                )

            # Disapprove Button - WORKFLOW requirement
            if should_create_entity(
                const.BUTTON_KC_UID_SUFFIX_DISAPPROVE,
                is_feature_gated_profile=is_linked_profile_user,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
            ):
                entities.append(
                    ApproverChoreDisapproveButton(
                        coordinator=coordinator,
                        entry=entry,
                        assignee_id=assignee_id,
                        assignee_name=assignee_name,
                        chore_id=chore_id,
                        chore_name=chore_name,
                    )
                )

    # Create reward buttons (Redeem, Approve & Disapprove)
    # Only for default participants or linked profiles with gamification enabled
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        # Skip linked profiles without gamification
        if not should_create_gamification_entities(coordinator, assignee_id):
            continue

        assignee_name = assignee_info.get(
            const.DATA_ASSIGNEE_NAME, f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}"
        )
        for reward_id, reward_info in coordinator.rewards_data.items():
            # Icon from storage (empty = use icons.json translation)
            reward_icon = reward_info.get(const.DATA_REWARD_ICON, const.SENTINEL_EMPTY)
            # Redeem Reward Button
            entities.append(
                AssigneeRewardRedeemButton(
                    coordinator=coordinator,
                    entry=entry,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    reward_id=reward_id,
                    reward_name=reward_info.get(
                        const.DATA_REWARD_NAME,
                        f"{const.TRANS_KEY_LABEL_REWARD} {reward_id}",
                    ),
                    icon=reward_icon,
                )
            )
            # Approve Reward Button
            entities.append(
                ApproverRewardApproveButton(
                    coordinator=coordinator,
                    entry=entry,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    reward_id=reward_id,
                    reward_name=reward_info.get(
                        const.DATA_REWARD_NAME,
                        f"{const.TRANS_KEY_LABEL_REWARD} {reward_id}",
                    ),
                    icon=reward_info.get(const.DATA_REWARD_ICON, const.SENTINEL_EMPTY),
                )
            )
            # Disapprove Reward Button
            entities.append(
                ApproverRewardDisapproveButton(
                    coordinator=coordinator,
                    entry=entry,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    reward_id=reward_id,
                    reward_name=reward_info.get(
                        const.DATA_REWARD_NAME,
                        f"{const.TRANS_KEY_LABEL_REWARD} {reward_id}",
                    ),
                )
            )

    # Create penalty buttons
    # Only for default participants or linked profiles with gamification enabled
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        # Skip linked profiles without gamification
        if not should_create_gamification_entities(coordinator, assignee_id):
            continue

        assignee_name = assignee_info.get(
            const.DATA_ASSIGNEE_NAME, f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}"
        )
        for penalty_id, penalty_info in coordinator.penalties_data.items():
            # Icon from storage (empty = use icons.json translation)
            penalty_icon = penalty_info.get(
                const.DATA_PENALTY_ICON, const.SENTINEL_EMPTY
            )
            entities.append(
                ApproverPenaltyApplyButton(
                    coordinator=coordinator,
                    entry=entry,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    penalty_id=penalty_id,
                    penalty_name=penalty_info.get(
                        const.DATA_PENALTY_NAME,
                        f"{const.TRANS_KEY_LABEL_PENALTY} {penalty_id}",
                    ),
                    icon=penalty_icon,
                )
            )

    # Create bonus buttons
    # Only for default participants or linked profiles with gamification enabled
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        # Skip linked profiles without gamification
        if not should_create_gamification_entities(coordinator, assignee_id):
            continue

        assignee_name = assignee_info.get(
            const.DATA_ASSIGNEE_NAME, f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}"
        )
        for bonus_id, bonus_info in coordinator.bonuses_data.items():
            # If no user-defined icon, fallback to SENTINEL_EMPTY
            bonus_icon = bonus_info.get(const.DATA_BONUS_ICON, const.SENTINEL_EMPTY)
            entities.append(
                ApproverBonusApplyButton(
                    coordinator=coordinator,
                    entry=entry,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    bonus_id=bonus_id,
                    bonus_name=bonus_info.get(
                        const.DATA_BONUS_NAME,
                        f"{const.TRANS_KEY_LABEL_BONUS} {bonus_id}",
                    ),
                    icon=bonus_icon,
                )
            )

    # Create "points adjustment" buttons for each assignee (±1, ±2, ±10, etc.)
    # Get normalized float values from EconomyManager (single source of truth)
    points_adjust_values = coordinator.economy_manager.adjustment_deltas
    const.LOGGER.debug(
        "DEBUG: Button - PointsAdjustValue - Using adjustment deltas: %s",
        points_adjust_values,
    )

    # Create a points adjust button for each assignee and each delta value
    # Only for default participants or linked profiles with gamification enabled
    for assignee_id, assignee_info in coordinator.assignees_data.items():
        # Skip linked profiles without gamification
        if not should_create_gamification_entities(coordinator, assignee_id):
            continue

        assignee_name = assignee_info.get(
            const.DATA_ASSIGNEE_NAME, f"{const.TRANS_KEY_LABEL_ASSIGNEE} {assignee_id}"
        )
        for delta in points_adjust_values:
            const.LOGGER.debug(
                "DEBUG: Creating ApproverPointsAdjustButton for Assignee '%s' with delta %s",
                assignee_name,
                delta,
            )
            entities.append(
                ApproverPointsAdjustButton(
                    coordinator=coordinator,
                    entry=entry,
                    assignee_id=assignee_id,
                    assignee_name=assignee_name,
                    delta=delta,
                    points_label=points_label,
                )
            )

    async_add_entities(entities)


# ------------------ Chore Buttons ------------------
class AssigneeChoreClaimButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to claim a chore as done (set chore state=claimed).

    Allows assignees to mark chores as completed. Validates user authorization
    against assignee ID, calls coordinator.claim_chore(), and triggers refresh.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_CLAIM_CHORE_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        chore_id: str,
        chore_name: str,
        icon: str,
    ):
        """Initialize the claim chore button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
            icon: Icon override from chore configuration or default.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_CHORE_NAME: chore_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_CHORE_CLAIM}{chore_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event."""
        try:
            user_id = self._context.user_id if self._context else None
            if user_id:
                if is_kiosk_mode_enabled(self.hass):
                    const.LOGGER.debug(
                        "Kiosk mode enabled: skipping assignee auth check for chore claim button"
                    )
                elif not await is_user_authorized_for_action(
                    self.hass,
                    user_id,
                    AUTH_ACTION_PARTICIPATION,
                    target_user_id=self._assignee_id,
                ):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                        translation_placeholders={
                            "action": const.ERROR_ACTION_CLAIM_CHORES
                        },
                    )
                else:
                    const.LOGGER.debug(
                        "Kiosk mode disabled: enforcing assignee auth check for chore claim button"
                    )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            user_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

            await self.coordinator.chore_manager.claim_chore(
                assignee_id=self._assignee_id,
                chore_id=self._chore_id,
                user_name=user_name,
            )
            const.LOGGER.info(
                "INFO: Chore '%s' claimed by Assignee '%s' (User: %s)",
                self._chore_name,
                self._assignee_name,
                user_name,
            )
            # No need to call async_request_refresh() - ChoreManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Claim Chore '%s' for Assignee '%s': %s",
                self._chore_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Claim Chore '%s' for Assignee '%s': %s",
                self._chore_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_CHORE_CLAIM,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ApproverChoreApproveButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to approve a claimed chore for a assignee (set chore state=approved or partial).

    Approver-only button that approves claimed chores, awards points, triggers badge
    calculations, and handles multi-assignee shared chore logic (partial vs full approval).
    Validates global approver authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_APPROVE_CHORE_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        chore_id: str,
        chore_name: str,
        icon: str,
    ):
        """Initialize the approve chore button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
            icon: Icon override from chore configuration or default approval icon.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_CHORE_NAME: chore_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_CHORE_APPROVAL}{chore_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates global approver authorization, retrieves approver name from context,
        calls coordinator.approve_chore() to award points and update state, triggers
        badge calculations and notifications, and refreshes all dependent entities.

        Raises:
            HomeAssistantError: If user not authorized for global approver actions.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_action(
                self.hass,
                user_id,
                AUTH_ACTION_APPROVAL,
                target_user_id=self._assignee_id,
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPROVE_CHORES
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            approver_name = (
                user_obj.name if user_obj else None
            ) or const.DISPLAY_UNKNOWN

            await self.coordinator.chore_manager.approve_chore(
                approver_name=approver_name,
                assignee_id=self._assignee_id,
                chore_id=self._chore_id,
            )
            const.LOGGER.info(
                "INFO: Chore '%s' approved for Assignee '%s'",
                self._chore_name,
                self._assignee_name,
            )
            # No need to call async_request_refresh() - ChoreManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Approve Chore '%s' for Assignee '%s': %s",
                self._chore_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to approve Chore '%s' for Assignee '%s': %s",
                self._chore_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_CHORE_APPROVE,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ApproverChoreDisapproveButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to disapprove a chore.

    Approver-only button that rejects pending chore approvals, removes from approval queue,
    and resets chore state to available. Validates pending approval exists before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_DISAPPROVE_CHORE_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        chore_id: str,
        chore_name: str,
        icon: str | None = None,
    ):
        """Initialize the disapprove chore button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
            icon: Icon override, defaults to disapprove icon.
        """

        super().__init__(coordinator)
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
        self._attr_icon = icon
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_CHORE_NAME: chore_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_CHORE_DISAPPROVAL}{chore_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates pending approval exists for this assignee/chore combination, checks
        global approver authorization, retrieves approver name from context, calls
        coordinator.disapprove_chore() to remove from approval queue and reset state.

        Raises:
            HomeAssistantError: If no pending approval found or user not authorized.
        """
        try:
            # Check if there's a pending approval for this assignee and chore.
            pending_approvals = self.coordinator.chore_manager.pending_chore_approvals
            if not any(
                approval[const.DATA_ASSIGNEE_ID] == self._assignee_id
                and approval[const.DATA_CHORE_ID] == self._chore_id
                for approval in pending_approvals
            ):
                raise HomeAssistantError(
                    f"No pending approval found for chore '{self._chore_name}' for assignee '{self._assignee_name}'."
                )

            user_id = self._context.user_id if self._context else None

            # Check if user is the assignee (for undo) or a approver/admin (for disapproval)
            assignee_info: AssigneeData = cast(
                "AssigneeData",
                self.coordinator.assignees_data.get(self._assignee_id, {}),
            )
            assignee_ha_user_id = assignee_info.get(const.DATA_ASSIGNEE_HA_USER_ID)
            is_assignee = (
                user_id and assignee_ha_user_id and user_id == assignee_ha_user_id
            )
            is_kiosk_anonymous_undo = user_id is None and is_kiosk_mode_enabled(
                self.hass
            )

            if is_assignee or is_kiosk_anonymous_undo:
                # Assignee undo: Remove own claim without stat tracking
                await self.coordinator.chore_manager.undo_claim(
                    assignee_id=self._assignee_id,
                    chore_id=self._chore_id,
                )
                const.LOGGER.info(
                    "INFO: Chore '%s' undo by Assignee '%s' (claim removed)",
                    self._chore_name,
                    self._assignee_name,
                )
            else:
                # Approver/admin disapproval: Requires authorization and tracks stats
                if user_id and not await is_user_authorized_for_action(
                    self.hass,
                    user_id,
                    AUTH_ACTION_APPROVAL,
                    target_user_id=self._assignee_id,
                ):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                        translation_placeholders={
                            "action": const.ERROR_ACTION_DISAPPROVE_CHORES
                        },
                    )

                user_obj = (
                    await self.hass.auth.async_get_user(user_id) if user_id else None
                )
                approver_name = (
                    user_obj.name if user_obj else None
                ) or const.DISPLAY_UNKNOWN

                await self.coordinator.chore_manager.disapprove_chore(
                    approver_name=approver_name,
                    assignee_id=self._assignee_id,
                    chore_id=self._chore_id,
                )
                const.LOGGER.info(
                    "INFO: Chore '%s' disapproved for Assignee '%s' by approver '%s'",
                    self._chore_name,
                    self._assignee_name,
                    approver_name,
                )
            # No need to call async_request_refresh() - ChoreManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Disapprove Chore '%s' for Assignee '%s': %s",
                self._chore_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Disapprove Chore '%s' for Assignee '%s': %s",
                self._chore_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        chore_info: ChoreData = cast(
            "ChoreData", self.coordinator.chores_data.get(self._chore_id, {})
        )
        stored_labels = chore_info.get(const.DATA_CHORE_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_CHORE_DISAPPROVE,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Reward Buttons ------------------
class AssigneeRewardRedeemButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to redeem a reward for a assignee.

    Allows assignees to spend points on rewards. Validates user authorization against assignee ID,
    checks sufficient points balance, deducts points, creates pending reward approval,
    and triggers coordinator refresh.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_CLAIM_REWARD_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        reward_id: str,
        reward_name: str,
        icon: str,
    ):
        """Initialize the reward button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
            icon: Icon override from reward configuration or default.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_ASSIGNEE_REWARD_REDEEM}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_REWARD_CLAIM}{reward_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates user authorization for assignee, retrieves user name from context,
        calls reward_manager.redeem() to create pending approval (no immediate deduction),
        and triggers coordinator refresh to update all dependent entities.

        Raises:
            HomeAssistantError: If user not authorized or insufficient points balance.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id:
                if is_kiosk_mode_enabled(self.hass):
                    const.LOGGER.debug(
                        "Kiosk mode enabled: skipping assignee auth check for reward redeem button"
                    )
                elif not await is_user_authorized_for_action(
                    self.hass,
                    user_id,
                    AUTH_ACTION_PARTICIPATION,
                    target_user_id=self._assignee_id,
                ):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                        translation_placeholders={
                            "action": const.ERROR_ACTION_REDEEM_REWARDS
                        },
                    )
                else:
                    const.LOGGER.debug(
                        "Kiosk mode disabled: enforcing assignee auth check for reward redeem button"
                    )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            approver_name = (
                user_obj.name if user_obj else None
            ) or const.DISPLAY_UNKNOWN

            await self.coordinator.reward_manager.redeem(
                approver_name=approver_name,
                assignee_id=self._assignee_id,
                reward_id=self._reward_id,
            )
            const.LOGGER.info(
                "INFO: Reward '%s' redeemed for Assignee '%s' by Approver '%s'",
                self._reward_name,
                self._assignee_name,
                approver_name,
            )
            # No need to call async_request_refresh() - RewardManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Redeem Reward '%s' for Assignee '%s': %s",
                self._reward_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Redeem Reward '%s' for Assignee '%s': %s",
                self._reward_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        reward_info: RewardData = cast(
            "RewardData", self.coordinator.rewards_data.get(self._reward_id, {})
        )
        stored_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_REWARD_REDEEM,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ApproverRewardApproveButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button for approvers to approve a reward claimed by a assignee.

    Approver-only button that confirms reward redemption, removes from pending approval
    queue, and triggers notifications. Validates global approver authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_APPROVE_REWARD_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        reward_id: str,
        reward_name: str,
        icon: str,
    ):
        """Initialize the approve reward button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
            icon: Icon override from reward configuration or default.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_REWARD_APPROVAL}{reward_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates global approver authorization, retrieves approver name from context,
        calls reward_manager.approve() to confirm redemption and deduct points,
        triggers notifications, and refreshes all dependent entities.

        Raises:
            HomeAssistantError: If user not authorized for global approver actions.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_action(
                self.hass,
                user_id,
                AUTH_ACTION_APPROVAL,
                target_user_id=self._assignee_id,
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPROVE_REWARDS
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            approver_name = (
                user_obj.name if user_obj else None
            ) or const.DISPLAY_UNKNOWN

            # Approve the reward
            await self.coordinator.reward_manager.approve(
                approver_name=approver_name,
                assignee_id=self._assignee_id,
                reward_id=self._reward_id,
            )

            const.LOGGER.info(
                "INFO: Reward '%s' approved for Assignee '%s' by Approver '%s'",
                self._reward_name,
                self._assignee_name,
                approver_name,
            )
            # No need to call async_request_refresh() - RewardManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Approve Reward '%s' for Assignee '%s': %s",
                self._reward_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Approve Reward '%s' for Assignee '%s': %s",
                self._reward_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        reward_info: RewardData = cast(
            "RewardData", self.coordinator.rewards_data.get(self._reward_id, {})
        )
        stored_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_REWARD_APPROVE,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ApproverRewardDisapproveButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to disapprove a reward.

    Approver-only button that rejects pending reward redemptions, refunds points to assignee,
    and removes from approval queue. Validates pending approval exists before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_DISAPPROVE_REWARD_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        reward_id: str,
        reward_name: str,
        icon: str | None = None,
    ):
        """Initialize the disapprove reward button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
            icon: Icon override, defaults to disapprove icon.
        """

        super().__init__(coordinator)
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_REWARD_DISAPPROVAL}{reward_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates pending approval exists for this assignee/reward combination, checks
        global approver authorization, retrieves approver name from context, calls
        reward_manager.disapprove() to remove from approval queue (no refund - points
        weren't deducted at claim time).

        Raises:
            HomeAssistantError: If no pending approval found or user not authorized.
        """
        try:
            # Check if there's a pending approval for this assignee and reward.
            pending_approvals = self.coordinator.reward_manager.get_pending_approvals()
            if not any(
                approval[const.DATA_ASSIGNEE_ID] == self._assignee_id
                and approval[const.DATA_REWARD_ID] == self._reward_id
                for approval in pending_approvals
            ):
                raise HomeAssistantError(
                    f"No pending approval found for reward '{self._reward_name}' for assignee '{self._assignee_name}'."
                )

            user_id = self._context.user_id if self._context else None

            # Check if user is the assignee (for undo) or a approver/admin (for disapproval)
            assignee_info: AssigneeData = cast(
                "AssigneeData",
                self.coordinator.assignees_data.get(self._assignee_id, {}),
            )
            assignee_ha_user_id = assignee_info.get(const.DATA_ASSIGNEE_HA_USER_ID)
            is_assignee = (
                user_id and assignee_ha_user_id and user_id == assignee_ha_user_id
            )

            if is_assignee:
                # Assignee undo: Remove own reward claim without stat tracking
                await self.coordinator.reward_manager.undo_claim(
                    assignee_id=self._assignee_id,
                    reward_id=self._reward_id,
                )
                const.LOGGER.info(
                    "INFO: Reward '%s' undo by Assignee '%s' (claim removed)",
                    self._reward_name,
                    self._assignee_name,
                )
            else:
                # Approver/admin disapproval: Requires authorization and tracks stats
                if user_id and not await is_user_authorized_for_action(
                    self.hass,
                    user_id,
                    AUTH_ACTION_APPROVAL,
                    target_user_id=self._assignee_id,
                ):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                        translation_placeholders={
                            "action": const.ERROR_ACTION_DISAPPROVE_REWARDS
                        },
                    )

                user_obj = (
                    await self.hass.auth.async_get_user(user_id) if user_id else None
                )
                approver_name = (
                    user_obj.name if user_obj else None
                ) or const.DISPLAY_UNKNOWN

                await self.coordinator.reward_manager.disapprove(
                    approver_name=approver_name,
                    assignee_id=self._assignee_id,
                    reward_id=self._reward_id,
                )
                const.LOGGER.info(
                    "INFO: Reward '%s' disapproved for Assignee '%s' by Approver '%s'",
                    self._reward_name,
                    self._assignee_name,
                    approver_name,
                )
            # No need to call async_request_refresh() - RewardManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Disapprove Reward '%s' for Assignee '%s': %s",
                self._reward_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Disapprove Reward '%s' for Assignee '%s': %s",
                self._reward_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        reward_info: RewardData = cast(
            "RewardData", self.coordinator.rewards_data.get(self._reward_id, {})
        )
        stored_labels = reward_info.get(const.DATA_REWARD_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_REWARD_DISAPPROVE,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Bonus Button ------------------
class ApproverBonusApplyButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to apply a bonus for a assignee.

    Approver-only button that adds points to assignee's balance based on bonus configuration.
    Validates global approver authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_BONUS_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        bonus_id: str,
        bonus_name: str,
        icon: str,
    ):
        """Initialize the bonus button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            bonus_id: Unique identifier for the bonus.
            bonus_name: Display name of the bonus.
            icon: Icon override from bonus configuration or default.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._bonus_id = bonus_id
        self._bonus_name = bonus_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{bonus_id}{const.BUTTON_KC_UID_SUFFIX_APPROVER_BONUS_APPLY}"
        self._user_icon = icon
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_BONUS_NAME: bonus_name,
        }
        # Strip redundant "bonus" suffix from entity_id (bonus_name often ends with "Bonus")
        bonus_slug = bonus_name.lower().replace(" ", "_")
        bonus_slug = bonus_slug.removesuffix("_bonus")  # Remove "_bonus" suffix
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_BONUS}{bonus_slug}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    @property
    def icon(self) -> str | None:
        """Return icon with user override fallback pattern.

        Returns user-configured icon if set (non-empty),
        otherwise returns None to enable icons.json translation.
        """
        return self._user_icon or None

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates global approver authorization, retrieves approver name from context,
        calls economy_manager.apply_bonus() to add points to assignee's balance based on bonus
        configuration, and triggers coordinator refresh.

        Raises:
            HomeAssistantError: If user not authorized for global approver actions.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_action(
                self.hass,
                user_id,
                AUTH_ACTION_MANAGEMENT,
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPLY_BONUSES
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            approver_name = (
                user_obj.name if user_obj else None
            ) or const.DISPLAY_UNKNOWN

            await self.coordinator.economy_manager.apply_bonus(
                approver_name=approver_name,
                assignee_id=self._assignee_id,
                bonus_id=self._bonus_id,
            )
            const.LOGGER.info(
                "INFO: Bonus '%s' applied to Assignee '%s' by Approver '%s'",
                self._bonus_name,
                self._assignee_name,
                approver_name,
            )
            # No need to call async_request_refresh() - EconomyManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Apply Bonus '%s' for Assignee '%s': %s",
                self._bonus_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Apply Bonus '%s' for Assignee '%s': %s",
                self._bonus_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        bonus_info: BonusData = cast(
            "BonusData", self.coordinator.bonuses_data.get(self._bonus_id, {})
        )
        stored_labels = bonus_info.get(const.DATA_BONUS_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_BONUS_APPLY,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_BONUS_NAME: self._bonus_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Penalty Button ------------------
class ApproverPenaltyApplyButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button to apply a penalty for a assignee.

    Approver-only button that deducts points from assignee's balance based on penalty
    configuration. Validates global approver authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_PENALTY_BUTTON

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        penalty_id: str,
        penalty_name: str,
        icon: str,
    ):
        """Initialize the penalty button.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            penalty_id: Unique identifier for the penalty.
            penalty_name: Display name of the penalty.
            icon: Icon override from penalty configuration or default.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._penalty_id = penalty_id
        self._penalty_name = penalty_name
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{penalty_id}{const.BUTTON_KC_UID_SUFFIX_APPROVER_PENALTY_APPLY}"
        self._user_icon = icon
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_PENALTY_NAME: penalty_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_MIDFIX_PENALTY}{penalty_name}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    @property
    def icon(self) -> str | None:
        """Return icon with user override fallback pattern.

        Returns user-configured icon if set (non-empty),
        otherwise returns None to enable icons.json translation.
        """
        return self._user_icon or None

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates global approver authorization, retrieves approver name from context,
        calls economy_manager.apply_penalty() to deduct points from assignee's balance based
        on penalty configuration, and triggers coordinator refresh.

        Raises:
            HomeAssistantError: If user not authorized for global approver actions.
        """
        try:
            const.LOGGER.debug(
                "DEBUG: ApproverPenaltyApplyButton.async_press called for assignee=%s, penalty=%s",
                self._assignee_id,
                self._penalty_id,
            )
            user_id = self._context.user_id if self._context else None
            const.LOGGER.debug("Context user_id=%s", user_id)

            if user_id and not await is_user_authorized_for_action(
                self.hass,
                user_id,
                AUTH_ACTION_MANAGEMENT,
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPLY_PENALTIES
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            approver_name = (
                user_obj.name if user_obj else None
            ) or const.DISPLAY_UNKNOWN
            const.LOGGER.debug("About to call economy_manager.apply_penalty")

            await self.coordinator.economy_manager.apply_penalty(
                approver_name=approver_name,
                assignee_id=self._assignee_id,
                penalty_id=self._penalty_id,
            )
            const.LOGGER.debug("economy_manager.apply_penalty completed")
            const.LOGGER.info(
                "INFO: Penalty '%s' applied to Assignee '%s' by Approver '%s'",
                self._penalty_name,
                self._assignee_name,
                approver_name,
            )
            # No need to call async_request_refresh() - EconomyManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Apply Penalty '%s' for Assignee '%s': %s",
                self._penalty_name,
                self._assignee_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Apply Penalty '%s' for Assignee '%s': %s",
                self._penalty_name,
                self._assignee_name,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Include extra state attributes for the button."""
        penalty_info: PenaltyData = cast(
            "PenaltyData", self.coordinator.penalties_data.get(self._penalty_id, {})
        )
        stored_labels = penalty_info.get(const.DATA_PENALTY_LABELS, [])
        friendly_labels = [
            get_friendly_label(self.hass, label) for label in stored_labels
        ]

        attributes: dict[str, Any] = {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_PENALTY_APPLY,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            const.ATTR_PENALTY_NAME: self._penalty_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Points Adjust Buttons ------------------
class ApproverPointsAdjustButton(ChoreOpsCoordinatorEntity, ButtonEntity):
    """Button that increments or decrements a assignee's points by 'delta'.

    Approver-only button for manual points adjustments. Creates multiple button instances
    per assignee based on configured delta values (e.g., +1, +10, -2). Validates global
    approver authorization before execution.
    """

    _attr_has_entity_name = True
    # Note: translation_key set dynamically in __init__ based on delta sign

    def __init__(
        self,
        coordinator: ChoreOpsDataCoordinator,
        entry: ChoreOpsConfigEntry,
        assignee_id: str,
        assignee_name: str,
        delta: float,
        points_label: str,
    ):
        """Initialize the points adjust buttons.

        Args:
            coordinator: ChoreOpsDataCoordinator instance for data access and updates.
            entry: ChoreOpsConfigEntry for this integration instance.
            assignee_id: Unique identifier for the assignee.
            assignee_name: Display name of the assignee.
            delta: Points adjustment value (positive for increment, negative for decrement).
            points_label: User-configured label for points (e.g., "Points", "Stars").
        """
        super().__init__(coordinator)
        self._entry = entry
        self._assignee_id = assignee_id
        self._assignee_name = assignee_name
        self._delta = delta
        self._points_label = str(points_label)

        # Slugify delta for unique_id (replace decimal point and negative sign)
        # Examples: 1.0 -> 1p0, -1.0 -> neg1p0, 10.0 -> 10p0
        delta_slug = str(abs(delta)).replace(".", "p")
        if delta < 0:
            delta_slug = f"neg{delta_slug}"
        self._attr_unique_id = f"{entry.entry_id}_{assignee_id}_{delta_slug}{const.BUTTON_KC_UID_SUFFIX_APPROVER_POINTS_ADJUST}"

        # Pass numeric delta to translation - template handles increment/decrement text
        # This allows proper localization of "Increment" vs "Decrement" in each language
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: assignee_name,
            const.TRANS_KEY_BUTTON_ATTR_DELTA: str(
                abs(delta)
            ),  # Absolute value for display
            const.TRANS_KEY_BUTTON_ATTR_POINTS_LABEL: points_label,
        }

        # Use different translation key based on delta sign for proper localization
        if delta >= 0:
            self._attr_translation_key = (
                f"{const.TRANS_KEY_BUTTON_MANUAL_ADJUSTMENT_BUTTON}_positive"
            )
        else:
            self._attr_translation_key = (
                f"{const.TRANS_KEY_BUTTON_MANUAL_ADJUSTMENT_BUTTON}_negative"
            )

        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{assignee_name}{const.BUTTON_KC_EID_SUFFIX_POINTS}_{sign_text}"
        self._attr_device_info = create_assignee_device_info_from_coordinator(
            self.coordinator, assignee_id, assignee_name, entry
        )

        # Decide the icon based on whether delta is positive or negative
        if delta >= 2:
            self._attr_icon = const.DEFAULT_POINTS_ADJUST_PLUS_MULTIPLE_ICON
        elif delta > 0:
            self._attr_icon = const.DEFAULT_POINTS_ADJUST_PLUS_ICON
        elif delta <= -2:
            self._attr_icon = const.DEFAULT_POINTS_ADJUST_MINUS_MULTIPLE_ICON
        elif delta < 0:
            self._attr_icon = const.DEFAULT_POINTS_ADJUST_MINUS_ICON
        else:
            self._attr_icon = const.DEFAULT_POINTS_ADJUST_PLUS_ICON

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle button press event."""
        await self._internal_press_logic()

    async def _internal_press_logic(self) -> None:
        """Execute the actual points adjustment logic.

        Validates global approver authorization, uses EconomyManager.deposit() or
        .withdraw() based on delta sign, and logs adjustment.

        Raises:
            HomeAssistantError: If user not authorized for global approver actions.
        """
        try:
            const.LOGGER.debug(
                "ApproverPointsAdjustButton._internal_press_logic: entity_id=%s, assignee=%s, delta=%s",
                self.entity_id,
                self._assignee_name,
                self._delta,
            )
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_action(
                self.hass,
                user_id,
                AUTH_ACTION_MANAGEMENT,
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_ADJUST_POINTS
                    },
                )

            # Use EconomyManager for point transactions
            # Use button's translated name for ledger entries (e.g., "Increment 10.0 Points", "Decrement 5.0 Points")
            # Type guard: self.name can be str | UndefinedType | None, but deposit/withdraw expect str | None
            item_name = self.name if isinstance(self.name, str) else None

            if self._delta >= 0:
                await self.coordinator.economy_manager.deposit(
                    assignee_id=self._assignee_id,
                    amount=self._delta,
                    source=const.POINTS_SOURCE_MANUAL,
                    item_name=item_name,
                )
            else:
                await self.coordinator.economy_manager.withdraw(
                    assignee_id=self._assignee_id,
                    amount=abs(self._delta),
                    source=const.POINTS_SOURCE_MANUAL,
                    item_name=item_name,
                )
            const.LOGGER.info(
                "INFO: Adjusted points for Assignee '%s' by %d.",
                self._assignee_name,
                self._delta,
            )
            # No need to call async_request_refresh() - StatisticsManager handles
            # persistence and coordinator updates via POINTS_CHANGED signal

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to adjust points for Assignee '%s' by %d: %s",
                self._assignee_name,
                self._delta,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to adjust points for Assignee '%s' by %d: %s",
                self._assignee_name,
                self._delta,
                e,
            )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes.

        Exposes delta value for dashboard templates and automations to access
        the adjustment amount without parsing the button name.
        """
        return {
            const.ATTR_PURPOSE: const.TRANS_KEY_PURPOSE_BUTTON_POINTS_ADJUST,
            const.ATTR_ASSIGNEE_NAME: self._assignee_name,
            "delta": self._delta,
            "assignee_id": self._assignee_id,
        }
