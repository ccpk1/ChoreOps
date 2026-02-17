# File: button.py
# pyright: reportIncompatibleVariableOverride=false
# ^ Suppresses Pylance warnings about @property overriding @cached_property from base classes.
#   This is intentional: our entities compute dynamic values on each access,
#   so we use @property instead of @cached_property to avoid stale cached data.
"""Buttons for KidsChores integration.

Features:
1) Chore Buttons (Claim & Approve) with user-defined or default icons.
2) Reward Buttons using user-defined or default icons.
3) Penalty Buttons using user-defined or default icons.
4) Bonus Buttons using user-defined or default icons.
5) ParentPointsAdjustButton: manually increments/decrements a kid's points.
6) ParentRewardApproveButton: allows parents to approve rewards claimed by kids.

"""

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import const
from .coordinator import KidsChoresConfigEntry, KidsChoresDataCoordinator
from .entity import KidsChoresCoordinatorEntity
from .helpers.auth_helpers import (
    is_kiosk_mode_enabled,
    is_user_authorized_for_global_action,
    is_user_authorized_for_kid,
)
from .helpers.device_helpers import create_kid_device_info_from_coordinator
from .helpers.entity_helpers import (
    get_friendly_label,
    get_kid_name_by_id,
    is_shadow_kid,
    should_create_entity,
    should_create_gamification_entities,
    should_create_workflow_buttons,
)

if TYPE_CHECKING:
    from .type_defs import BonusData, ChoreData, KidData, PenaltyData, RewardData

# Platinum requirement: Parallel Updates
# Set to 1 (serialized) for action buttons that modify state
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KidsChoresConfigEntry,
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
        assigned_kids_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

        # If user defined an icon, use it; else fallback to SENTINEL_EMPTY for chore claim
        chore_claim_icon = chore_info.get(const.DATA_CHORE_ICON, const.SENTINEL_EMPTY)
        # For "approve," use a distinct icon
        chore_approve_icon = chore_info.get(const.DATA_CHORE_ICON, const.SENTINEL_EMPTY)

        for kid_id in assigned_kids_ids:
            kid_name = (
                get_kid_name_by_id(coordinator, kid_id)
                or f"{const.TRANS_KEY_LABEL_KID} {kid_id}"
            )

            # Get flag states for unified entity creation decisions
            is_shadow = is_shadow_kid(coordinator, kid_id)
            workflow_enabled = should_create_workflow_buttons(coordinator, kid_id)
            gamification_enabled = should_create_gamification_entities(
                coordinator, kid_id
            )

            # Claim Button - WORKFLOW requirement
            if should_create_entity(
                const.BUTTON_KC_UID_SUFFIX_CLAIM,
                is_shadow_kid=is_shadow,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
            ):
                entities.append(
                    KidChoreClaimButton(
                        coordinator=coordinator,
                        entry=entry,
                        kid_id=kid_id,
                        kid_name=kid_name,
                        chore_id=chore_id,
                        chore_name=chore_name,
                        icon=chore_claim_icon,
                    )
                )

            # Approve Button - ALWAYS requirement
            if should_create_entity(
                const.BUTTON_KC_UID_SUFFIX_APPROVE,
                is_shadow_kid=is_shadow,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
            ):
                entities.append(
                    ParentChoreApproveButton(
                        coordinator=coordinator,
                        entry=entry,
                        kid_id=kid_id,
                        kid_name=kid_name,
                        chore_id=chore_id,
                        chore_name=chore_name,
                        icon=chore_approve_icon,
                    )
                )

            # Disapprove Button - WORKFLOW requirement
            if should_create_entity(
                const.BUTTON_KC_UID_SUFFIX_DISAPPROVE,
                is_shadow_kid=is_shadow,
                workflow_enabled=workflow_enabled,
                gamification_enabled=gamification_enabled,
            ):
                entities.append(
                    ParentChoreDisapproveButton(
                        coordinator=coordinator,
                        entry=entry,
                        kid_id=kid_id,
                        kid_name=kid_name,
                        chore_id=chore_id,
                        chore_name=chore_name,
                    )
                )

    # Create reward buttons (Redeem, Approve & Disapprove)
    # Only for regular kids or shadow kids with gamification enabled
    for kid_id, kid_info in coordinator.kids_data.items():
        # Skip shadow kids without gamification
        if not should_create_gamification_entities(coordinator, kid_id):
            continue

        kid_name = kid_info.get(
            const.DATA_KID_NAME, f"{const.TRANS_KEY_LABEL_KID} {kid_id}"
        )
        for reward_id, reward_info in coordinator.rewards_data.items():
            # Icon from storage (empty = use icons.json translation)
            reward_icon = reward_info.get(const.DATA_REWARD_ICON, const.SENTINEL_EMPTY)
            # Redeem Reward Button
            entities.append(
                KidRewardRedeemButton(
                    coordinator=coordinator,
                    entry=entry,
                    kid_id=kid_id,
                    kid_name=kid_name,
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
                ParentRewardApproveButton(
                    coordinator=coordinator,
                    entry=entry,
                    kid_id=kid_id,
                    kid_name=kid_name,
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
                ParentRewardDisapproveButton(
                    coordinator=coordinator,
                    entry=entry,
                    kid_id=kid_id,
                    kid_name=kid_name,
                    reward_id=reward_id,
                    reward_name=reward_info.get(
                        const.DATA_REWARD_NAME,
                        f"{const.TRANS_KEY_LABEL_REWARD} {reward_id}",
                    ),
                )
            )

    # Create penalty buttons
    # Only for regular kids or shadow kids with gamification enabled
    for kid_id, kid_info in coordinator.kids_data.items():
        # Skip shadow kids without gamification
        if not should_create_gamification_entities(coordinator, kid_id):
            continue

        kid_name = kid_info.get(
            const.DATA_KID_NAME, f"{const.TRANS_KEY_LABEL_KID} {kid_id}"
        )
        for penalty_id, penalty_info in coordinator.penalties_data.items():
            # Icon from storage (empty = use icons.json translation)
            penalty_icon = penalty_info.get(
                const.DATA_PENALTY_ICON, const.SENTINEL_EMPTY
            )
            entities.append(
                ParentPenaltyApplyButton(
                    coordinator=coordinator,
                    entry=entry,
                    kid_id=kid_id,
                    kid_name=kid_name,
                    penalty_id=penalty_id,
                    penalty_name=penalty_info.get(
                        const.DATA_PENALTY_NAME,
                        f"{const.TRANS_KEY_LABEL_PENALTY} {penalty_id}",
                    ),
                    icon=penalty_icon,
                )
            )

    # Create bonus buttons
    # Only for regular kids or shadow kids with gamification enabled
    for kid_id, kid_info in coordinator.kids_data.items():
        # Skip shadow kids without gamification
        if not should_create_gamification_entities(coordinator, kid_id):
            continue

        kid_name = kid_info.get(
            const.DATA_KID_NAME, f"{const.TRANS_KEY_LABEL_KID} {kid_id}"
        )
        for bonus_id, bonus_info in coordinator.bonuses_data.items():
            # If no user-defined icon, fallback to SENTINEL_EMPTY
            bonus_icon = bonus_info.get(const.DATA_BONUS_ICON, const.SENTINEL_EMPTY)
            entities.append(
                ParentBonusApplyButton(
                    coordinator=coordinator,
                    entry=entry,
                    kid_id=kid_id,
                    kid_name=kid_name,
                    bonus_id=bonus_id,
                    bonus_name=bonus_info.get(
                        const.DATA_BONUS_NAME,
                        f"{const.TRANS_KEY_LABEL_BONUS} {bonus_id}",
                    ),
                    icon=bonus_icon,
                )
            )

    # Create "points adjustment" buttons for each kid (±1, ±2, ±10, etc.)
    # Get normalized float values from EconomyManager (single source of truth)
    points_adjust_values = coordinator.economy_manager.adjustment_deltas
    const.LOGGER.debug(
        "DEBUG: Button - PointsAdjustValue - Using adjustment deltas: %s",
        points_adjust_values,
    )

    # Create a points adjust button for each kid and each delta value
    # Only for regular kids or shadow kids with gamification enabled
    for kid_id, kid_info in coordinator.kids_data.items():
        # Skip shadow kids without gamification
        if not should_create_gamification_entities(coordinator, kid_id):
            continue

        kid_name = kid_info.get(
            const.DATA_KID_NAME, f"{const.TRANS_KEY_LABEL_KID} {kid_id}"
        )
        for delta in points_adjust_values:
            const.LOGGER.debug(
                "DEBUG: Creating ParentPointsAdjustButton for Kid '%s' with delta %s",
                kid_name,
                delta,
            )
            entities.append(
                ParentPointsAdjustButton(
                    coordinator=coordinator,
                    entry=entry,
                    kid_id=kid_id,
                    kid_name=kid_name,
                    delta=delta,
                    points_label=points_label,
                )
            )

    async_add_entities(entities)


# ------------------ Chore Buttons ------------------
class KidChoreClaimButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to claim a chore as done (set chore state=claimed).

    Allows kids to mark chores as completed. Validates user authorization
    against kid ID, calls coordinator.claim_chore(), and triggers refresh.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_CLAIM_CHORE_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        chore_id: str,
        chore_name: str,
        icon: str,
    ):
        """Initialize the claim chore button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
            icon: Icon override from chore configuration or default.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}"
        )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_CHORE_NAME: chore_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_CHORE_CLAIM}{chore_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
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
                        "Kiosk mode enabled: skipping kid auth check for chore claim button"
                    )
                elif not await is_user_authorized_for_kid(
                    self.hass, user_id, self._kid_id
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
                        "Kiosk mode disabled: enforcing kid auth check for chore claim button"
                    )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            user_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

            await self.coordinator.chore_manager.claim_chore(
                kid_id=self._kid_id,
                chore_id=self._chore_id,
                user_name=user_name,
            )
            const.LOGGER.info(
                "INFO: Chore '%s' claimed by Kid '%s' (User: %s)",
                self._chore_name,
                self._kid_name,
                user_name,
            )
            # No need to call async_request_refresh() - ChoreManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Claim Chore '%s' for Kid '%s': %s",
                self._chore_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Claim Chore '%s' for Kid '%s': %s",
                self._chore_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ParentChoreApproveButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to approve a claimed chore for a kid (set chore state=approved or partial).

    Parent-only button that approves claimed chores, awards points, triggers badge
    calculations, and handles multi-kid shared chore logic (partial vs full approval).
    Validates global parent authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_APPROVE_CHORE_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        chore_id: str,
        chore_name: str,
        icon: str,
    ):
        """Initialize the approve chore button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
            icon: Icon override from chore configuration or default approval icon.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = (
            f"{entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
        )
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_CHORE_NAME: chore_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_CHORE_APPROVAL}{chore_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates global parent authorization, retrieves parent name from context,
        calls coordinator.approve_chore() to award points and update state, triggers
        badge calculations and notifications, and refreshes all dependent entities.

        Raises:
            HomeAssistantError: If user not authorized for global parent actions.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_global_action(
                self.hass, user_id, const.SERVICE_APPROVE_CHORE
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPROVE_CHORES
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

            await self.coordinator.chore_manager.approve_chore(
                parent_name=parent_name,
                kid_id=self._kid_id,
                chore_id=self._chore_id,
            )
            const.LOGGER.info(
                "INFO: Chore '%s' approved for Kid '%s'",
                self._chore_name,
                self._kid_name,
            )
            # No need to call async_request_refresh() - ChoreManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Approve Chore '%s' for Kid '%s': %s",
                self._chore_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to approve Chore '%s' for Kid '%s': %s",
                self._chore_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ParentChoreDisapproveButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to disapprove a chore.

    Parent-only button that rejects pending chore approvals, removes from approval queue,
    and resets chore state to available. Validates pending approval exists before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_DISAPPROVE_CHORE_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        chore_id: str,
        chore_name: str,
        icon: str | None = None,
    ):
        """Initialize the disapprove chore button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            chore_id: Unique identifier for the chore.
            chore_name: Display name of the chore.
            icon: Icon override, defaults to disapprove icon.
        """

        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._chore_id = chore_id
        self._chore_name = chore_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
        self._attr_icon = icon
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_CHORE_NAME: chore_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_CHORE_DISAPPROVAL}{chore_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates pending approval exists for this kid/chore combination, checks
        global parent authorization, retrieves parent name from context, calls
        coordinator.disapprove_chore() to remove from approval queue and reset state.

        Raises:
            HomeAssistantError: If no pending approval found or user not authorized.
        """
        try:
            # Check if there's a pending approval for this kid and chore.
            pending_approvals = self.coordinator.chore_manager.pending_chore_approvals
            if not any(
                approval[const.DATA_KID_ID] == self._kid_id
                and approval[const.DATA_CHORE_ID] == self._chore_id
                for approval in pending_approvals
            ):
                raise HomeAssistantError(
                    f"No pending approval found for chore '{self._chore_name}' for kid '{self._kid_name}'."
                )

            user_id = self._context.user_id if self._context else None

            # Check if user is the kid (for undo) or a parent/admin (for disapproval)
            kid_info: KidData = cast(
                "KidData", self.coordinator.kids_data.get(self._kid_id, {})
            )
            kid_ha_user_id = kid_info.get(const.DATA_KID_HA_USER_ID)
            is_kid = user_id and kid_ha_user_id and user_id == kid_ha_user_id

            if is_kid:
                # Kid undo: Remove own claim without stat tracking
                await self.coordinator.chore_manager.undo_claim(
                    kid_id=self._kid_id,
                    chore_id=self._chore_id,
                )
                const.LOGGER.info(
                    "INFO: Chore '%s' undo by Kid '%s' (claim removed)",
                    self._chore_name,
                    self._kid_name,
                )
            else:
                # Parent/admin disapproval: Requires authorization and tracks stats
                if user_id and not await is_user_authorized_for_global_action(
                    self.hass, user_id, const.SERVICE_DISAPPROVE_CHORE
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
                parent_name = (
                    user_obj.name if user_obj else None
                ) or const.DISPLAY_UNKNOWN

                await self.coordinator.chore_manager.disapprove_chore(
                    parent_name=parent_name,
                    kid_id=self._kid_id,
                    chore_id=self._chore_id,
                )
                const.LOGGER.info(
                    "INFO: Chore '%s' disapproved for Kid '%s' by parent '%s'",
                    self._chore_name,
                    self._kid_name,
                    parent_name,
                )
            # No need to call async_request_refresh() - ChoreManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Disapprove Chore '%s' for Kid '%s': %s",
                self._chore_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Disapprove Chore '%s' for Kid '%s': %s",
                self._chore_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_CHORE_NAME: self._chore_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Reward Buttons ------------------
class KidRewardRedeemButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to redeem a reward for a kid.

    Allows kids to spend points on rewards. Validates user authorization against kid ID,
    checks sufficient points balance, deducts points, creates pending reward approval,
    and triggers coordinator refresh.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_CLAIM_REWARD_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        reward_id: str,
        reward_name: str,
        icon: str,
    ):
        """Initialize the reward button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
            icon: Icon override from reward configuration or default.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_KID_REWARD_REDEEM}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_REWARD_CLAIM}{reward_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates user authorization for kid, retrieves user name from context,
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
                        "Kiosk mode enabled: skipping kid auth check for reward redeem button"
                    )
                elif not await is_user_authorized_for_kid(
                    self.hass, user_id, self._kid_id
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
                        "Kiosk mode disabled: enforcing kid auth check for reward redeem button"
                    )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

            await self.coordinator.reward_manager.redeem(
                parent_name=parent_name,
                kid_id=self._kid_id,
                reward_id=self._reward_id,
            )
            const.LOGGER.info(
                "INFO: Reward '%s' redeemed for Kid '%s' by Parent '%s'",
                self._reward_name,
                self._kid_name,
                parent_name,
            )
            # No need to call async_request_refresh() - RewardManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Redeem Reward '%s' for Kid '%s': %s",
                self._reward_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Redeem Reward '%s' for Kid '%s': %s",
                self._reward_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ParentRewardApproveButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button for parents to approve a reward claimed by a kid.

    Parent-only button that confirms reward redemption, removes from pending approval
    queue, and triggers notifications. Validates global parent authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_APPROVE_REWARD_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        reward_id: str,
        reward_name: str,
        icon: str,
    ):
        """Initialize the approve reward button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
            icon: Icon override from reward configuration or default.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_REWARD_APPROVAL}{reward_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates global parent authorization, retrieves parent name from context,
        calls reward_manager.approve() to confirm redemption and deduct points,
        triggers notifications, and refreshes all dependent entities.

        Raises:
            HomeAssistantError: If user not authorized for global parent actions.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_global_action(
                self.hass, user_id, const.SERVICE_APPROVE_REWARD
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPROVE_REWARDS
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

            # Approve the reward
            await self.coordinator.reward_manager.approve(
                parent_name=parent_name,
                kid_id=self._kid_id,
                reward_id=self._reward_id,
            )

            const.LOGGER.info(
                "INFO: Reward '%s' approved for Kid '%s' by Parent '%s'",
                self._reward_name,
                self._kid_name,
                parent_name,
            )
            # No need to call async_request_refresh() - RewardManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Approve Reward '%s' for Kid '%s': %s",
                self._reward_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Approve Reward '%s' for Kid '%s': %s",
                self._reward_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


class ParentRewardDisapproveButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to disapprove a reward.

    Parent-only button that rejects pending reward redemptions, refunds points to kid,
    and removes from approval queue. Validates pending approval exists before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_DISAPPROVE_REWARD_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        reward_id: str,
        reward_name: str,
        icon: str | None = None,
    ):
        """Initialize the disapprove reward button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            reward_id: Unique identifier for the reward.
            reward_name: Display name of the reward.
            icon: Icon override, defaults to disapprove icon.
        """

        super().__init__(coordinator)
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._reward_id = reward_id
        self._reward_name = reward_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_REWARD_NAME: reward_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_REWARD_DISAPPROVAL}{reward_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
        )

    def press(self) -> None:
        """Synchronous press - not used, Home Assistant calls async_press."""

    async def async_press(self) -> None:
        """Handle the button press event.

        Validates pending approval exists for this kid/reward combination, checks
        global parent authorization, retrieves parent name from context, calls
        reward_manager.disapprove() to remove from approval queue (no refund - points
        weren't deducted at claim time).

        Raises:
            HomeAssistantError: If no pending approval found or user not authorized.
        """
        try:
            # Check if there's a pending approval for this kid and reward.
            pending_approvals = self.coordinator.reward_manager.get_pending_approvals()
            if not any(
                approval[const.DATA_KID_ID] == self._kid_id
                and approval[const.DATA_REWARD_ID] == self._reward_id
                for approval in pending_approvals
            ):
                raise HomeAssistantError(
                    f"No pending approval found for reward '{self._reward_name}' for kid '{self._kid_name}'."
                )

            user_id = self._context.user_id if self._context else None

            # Check if user is the kid (for undo) or a parent/admin (for disapproval)
            kid_info: KidData = cast(
                "KidData", self.coordinator.kids_data.get(self._kid_id, {})
            )
            kid_ha_user_id = kid_info.get(const.DATA_KID_HA_USER_ID)
            is_kid = user_id and kid_ha_user_id and user_id == kid_ha_user_id

            if is_kid:
                # Kid undo: Remove own reward claim without stat tracking
                await self.coordinator.reward_manager.undo_claim(
                    kid_id=self._kid_id,
                    reward_id=self._reward_id,
                )
                const.LOGGER.info(
                    "INFO: Reward '%s' undo by Kid '%s' (claim removed)",
                    self._reward_name,
                    self._kid_name,
                )
            else:
                # Parent/admin disapproval: Requires authorization and tracks stats
                if user_id and not await is_user_authorized_for_global_action(
                    self.hass, user_id, const.SERVICE_DISAPPROVE_REWARD
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
                parent_name = (
                    user_obj.name if user_obj else None
                ) or const.DISPLAY_UNKNOWN

                await self.coordinator.reward_manager.disapprove(
                    parent_name=parent_name,
                    kid_id=self._kid_id,
                    reward_id=self._reward_id,
                )
                const.LOGGER.info(
                    "INFO: Reward '%s' disapproved for Kid '%s' by Parent '%s'",
                    self._reward_name,
                    self._kid_name,
                    parent_name,
                )
            # No need to call async_request_refresh() - RewardManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Disapprove Reward '%s' for Kid '%s': %s",
                self._reward_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Disapprove Reward '%s' for Kid '%s': %s",
                self._reward_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_REWARD_NAME: self._reward_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Bonus Button ------------------
class ParentBonusApplyButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to apply a bonus for a kid.

    Parent-only button that adds points to kid's balance based on bonus configuration.
    Validates global parent authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_BONUS_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        bonus_id: str,
        bonus_name: str,
        icon: str,
    ):
        """Initialize the bonus button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            bonus_id: Unique identifier for the bonus.
            bonus_name: Display name of the bonus.
            icon: Icon override from bonus configuration or default.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._bonus_id = bonus_id
        self._bonus_name = bonus_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{bonus_id}{const.BUTTON_KC_UID_SUFFIX_PARENT_BONUS_APPLY}"
        self._user_icon = icon
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_BONUS_NAME: bonus_name,
        }
        # Strip redundant "bonus" suffix from entity_id (bonus_name often ends with "Bonus")
        bonus_slug = bonus_name.lower().replace(" ", "_")
        bonus_slug = bonus_slug.removesuffix("_bonus")  # Remove "_bonus" suffix
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_BONUS}{bonus_slug}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
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

        Validates global parent authorization, retrieves parent name from context,
        calls economy_manager.apply_bonus() to add points to kid's balance based on bonus
        configuration, and triggers coordinator refresh.

        Raises:
            HomeAssistantError: If user not authorized for global parent actions.
        """
        try:
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_global_action(
                self.hass, user_id, const.SERVICE_APPLY_BONUS
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPLY_BONUSES
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN

            await self.coordinator.economy_manager.apply_bonus(
                parent_name=parent_name,
                kid_id=self._kid_id,
                bonus_id=self._bonus_id,
            )
            const.LOGGER.info(
                "INFO: Bonus '%s' applied to Kid '%s' by Parent '%s'",
                self._bonus_name,
                self._kid_name,
                parent_name,
            )
            # No need to call async_request_refresh() - EconomyManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Apply Bonus '%s' for Kid '%s': %s",
                self._bonus_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Apply Bonus '%s' for Kid '%s': %s",
                self._bonus_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_BONUS_NAME: self._bonus_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Penalty Button ------------------
class ParentPenaltyApplyButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button to apply a penalty for a kid.

    Parent-only button that deducts points from kid's balance based on penalty
    configuration. Validates global parent authorization before execution.
    """

    _attr_has_entity_name = True
    _attr_translation_key = const.TRANS_KEY_BUTTON_PENALTY_BUTTON

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        penalty_id: str,
        penalty_name: str,
        icon: str,
    ):
        """Initialize the penalty button.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            penalty_id: Unique identifier for the penalty.
            penalty_name: Display name of the penalty.
            icon: Icon override from penalty configuration or default.
        """

        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._penalty_id = penalty_id
        self._penalty_name = penalty_name
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{penalty_id}{const.BUTTON_KC_UID_SUFFIX_PARENT_PENALTY_APPLY}"
        self._user_icon = icon
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
            const.TRANS_KEY_BUTTON_ATTR_PENALTY_NAME: penalty_name,
        }
        # Moving to HA native best practice: auto-generate entity_id from unique_id + has_entity_name
        # rather than manually constructing to support HA core change 01309191283 (Jan 14, 2026)
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_MIDFIX_PENALTY}{penalty_name}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
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

        Validates global parent authorization, retrieves parent name from context,
        calls economy_manager.apply_penalty() to deduct points from kid's balance based
        on penalty configuration, and triggers coordinator refresh.

        Raises:
            HomeAssistantError: If user not authorized for global parent actions.
        """
        try:
            const.LOGGER.debug(
                "DEBUG: ParentPenaltyApplyButton.async_press called for kid=%s, penalty=%s",
                self._kid_id,
                self._penalty_id,
            )
            user_id = self._context.user_id if self._context else None
            const.LOGGER.debug("Context user_id=%s", user_id)

            if user_id and not await is_user_authorized_for_global_action(
                self.hass, user_id, const.SERVICE_APPLY_PENALTY
            ):
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                    translation_placeholders={
                        "action": const.ERROR_ACTION_APPLY_PENALTIES
                    },
                )

            user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None
            parent_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN
            const.LOGGER.debug("About to call economy_manager.apply_penalty")

            await self.coordinator.economy_manager.apply_penalty(
                parent_name=parent_name,
                kid_id=self._kid_id,
                penalty_id=self._penalty_id,
            )
            const.LOGGER.debug("economy_manager.apply_penalty completed")
            const.LOGGER.info(
                "INFO: Penalty '%s' applied to Kid '%s' by Parent '%s'",
                self._penalty_name,
                self._kid_name,
                parent_name,
            )
            # No need to call async_request_refresh() - EconomyManager emits signals
            # that trigger StatisticsManager to persist and update coordinator

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to Apply Penalty '%s' for Kid '%s': %s",
                self._penalty_name,
                self._kid_name,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to Apply Penalty '%s' for Kid '%s': %s",
                self._penalty_name,
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            const.ATTR_PENALTY_NAME: self._penalty_name,
            const.ATTR_LABELS: friendly_labels,
        }

        return attributes


# ------------------ Points Adjust Buttons ------------------
class ParentPointsAdjustButton(KidsChoresCoordinatorEntity, ButtonEntity):
    """Button that increments or decrements a kid's points by 'delta'.

    Parent-only button for manual points adjustments. Creates multiple button instances
    per kid based on configured delta values (e.g., +1, +10, -2). Validates global
    parent authorization before execution.
    """

    _attr_has_entity_name = True
    # Note: translation_key set dynamically in __init__ based on delta sign

    def __init__(
        self,
        coordinator: KidsChoresDataCoordinator,
        entry: KidsChoresConfigEntry,
        kid_id: str,
        kid_name: str,
        delta: float,
        points_label: str,
    ):
        """Initialize the points adjust buttons.

        Args:
            coordinator: KidsChoresDataCoordinator instance for data access and updates.
            entry: KidsChoresConfigEntry for this integration instance.
            kid_id: Unique identifier for the kid.
            kid_name: Display name of the kid.
            delta: Points adjustment value (positive for increment, negative for decrement).
            points_label: User-configured label for points (e.g., "Points", "Stars").
        """
        super().__init__(coordinator)
        self._entry = entry
        self._kid_id = kid_id
        self._kid_name = kid_name
        self._delta = delta
        self._points_label = str(points_label)

        # Slugify delta for unique_id (replace decimal point and negative sign)
        # Examples: 1.0 -> 1p0, -1.0 -> neg1p0, 10.0 -> 10p0
        delta_slug = str(abs(delta)).replace(".", "p")
        if delta < 0:
            delta_slug = f"neg{delta_slug}"
        self._attr_unique_id = f"{entry.entry_id}_{kid_id}_{delta_slug}{const.BUTTON_KC_UID_SUFFIX_PARENT_POINTS_ADJUST}"

        # Pass numeric delta to translation - template handles increment/decrement text
        # This allows proper localization of "Increment" vs "Decrement" in each language
        self._attr_translation_placeholders = {
            const.TRANS_KEY_BUTTON_ATTR_KID_NAME: kid_name,
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
        # self.entity_id = f"{const.BUTTON_KC_PREFIX}{kid_name}{const.BUTTON_KC_EID_SUFFIX_POINTS}_{sign_text}"
        self._attr_device_info = create_kid_device_info_from_coordinator(
            self.coordinator, kid_id, kid_name, entry
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

        Validates global parent authorization, uses EconomyManager.deposit() or
        .withdraw() based on delta sign, and logs adjustment.

        Raises:
            HomeAssistantError: If user not authorized for global parent actions.
        """
        try:
            const.LOGGER.debug(
                "ParentPointsAdjustButton._internal_press_logic: entity_id=%s, kid=%s, delta=%s",
                self.entity_id,
                self._kid_name,
                self._delta,
            )
            user_id = self._context.user_id if self._context else None
            if user_id and not await is_user_authorized_for_global_action(
                self.hass, user_id, const.SERVICE_ADJUST_POINTS
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
                    kid_id=self._kid_id,
                    amount=self._delta,
                    source=const.POINTS_SOURCE_MANUAL,
                    item_name=item_name,
                )
            else:
                await self.coordinator.economy_manager.withdraw(
                    kid_id=self._kid_id,
                    amount=abs(self._delta),
                    source=const.POINTS_SOURCE_MANUAL,
                    item_name=item_name,
                )
            const.LOGGER.info(
                "INFO: Adjusted points for Kid '%s' by %d.",
                self._kid_name,
                self._delta,
            )
            # No need to call async_request_refresh() - StatisticsManager handles
            # persistence and coordinator updates via POINTS_CHANGED signal

        except HomeAssistantError as e:
            const.LOGGER.error(
                "ERROR: Authorization failed to adjust points for Kid '%s' by %d: %s",
                self._kid_name,
                self._delta,
                e,
            )
        except (KeyError, ValueError, AttributeError) as e:
            const.LOGGER.error(
                "ERROR: Failed to adjust points for Kid '%s' by %d: %s",
                self._kid_name,
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
            const.ATTR_KID_NAME: self._kid_name,
            "delta": self._delta,
            "kid_id": self._kid_id,
        }
