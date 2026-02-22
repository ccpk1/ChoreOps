# File: helpers/auth_helpers.py
"""Authorization helper functions for ChoreOps.

Functions that check user permissions for ChoreOps operations.
All functions here require a `hass` object for auth system access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from .. import const

if TYPE_CHECKING:
    from homeassistant.auth.models import User
    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator


# ==============================================================================
# Coordinator Access
# ==============================================================================


def _get_choreops_coordinator(
    hass: HomeAssistant,
) -> ChoreOpsDataCoordinator | None:
    """Retrieve ChoreOps coordinator from config entry runtime_data.

    Args:
        hass: HomeAssistant instance

    Returns:
        ChoreOpsDataCoordinator if found, None otherwise
    """
    entries = hass.config_entries.async_entries(const.DOMAIN)
    if not entries:
        return None

    # Get first loaded entry
    for entry in entries:
        if entry.state.name == "LOADED":
            return entry.runtime_data
    return None


def is_kiosk_mode_enabled(hass: HomeAssistant) -> bool:
    """Return whether kiosk mode is enabled in active ChoreOps options.

    Args:
        hass: HomeAssistant instance

    Returns:
        True when kiosk mode option is enabled, False otherwise
    """
    entries = hass.config_entries.async_entries(const.DOMAIN)
    if not entries:
        return const.DEFAULT_KIOSK_MODE

    for entry in entries:
        if entry.state.name == "LOADED":
            return entry.options.get(const.CONF_KIOSK_MODE, const.DEFAULT_KIOSK_MODE)

    return const.DEFAULT_KIOSK_MODE


# ==============================================================================
# Authorization Checks
# ==============================================================================

type AuthorizationAction = Literal["approval", "management", "participation"]

AUTH_ACTION_APPROVAL: Final[AuthorizationAction] = "approval"
AUTH_ACTION_MANAGEMENT: Final[AuthorizationAction] = "management"
AUTH_ACTION_PARTICIPATION: Final[AuthorizationAction] = "participation"


async def is_user_authorized_for_action(
    hass: HomeAssistant,
    user_id: str,
    action: AuthorizationAction,
    target_user_id: str | None = None,
) -> bool:
    """Check authorization for a capability action.

    Precedence order:
    1) Home Assistant admin override
    2) Explicit capability checks
    3) Deny

    Args:
        hass: Home Assistant instance.
        user_id: Home Assistant user ID.
        action: Action contract (`approval` or `management`).
        target_user_id: Target user ID for approval-scoped checks.

    Returns:
        True when permission is granted, else False.
    """
    if action == AUTH_ACTION_MANAGEMENT:
        return await _has_management_authority(hass, user_id)

    if action == AUTH_ACTION_APPROVAL:
        if target_user_id is None:
            return False
        return await _has_approval_authority_for_target(
            hass,
            user_id,
            target_user_id,
        )

    if action == AUTH_ACTION_PARTICIPATION:
        if target_user_id is None:
            return False
        return await _has_participation_authority_for_target(
            hass,
            user_id,
            target_user_id,
        )

    return False


def _ha_user_ref_matches(user: User, ha_user_ref: str | None) -> bool:
    """Return whether a stored HA user reference matches this HA user.

    Runtime data may contain either the HA user ID or a stable name-style
    reference from fixture/scenario setup.
    """
    if not ha_user_ref:
        return False

    normalized_ref = "".join(ch for ch in ha_user_ref.lower() if ch.isalnum())
    normalized_name = "".join(ch for ch in user.name.lower() if ch.isalnum())

    return ha_user_ref == user.id or normalized_ref == normalized_name


def _get_record_ha_user_ref(user_data: dict[str, object]) -> str | None:
    """Return HA user reference from canonical or compatibility keys."""
    for key in (
        const.DATA_USER_HA_USER_ID,
        const.DATA_APPROVER_HA_USER_ID,
        const.DATA_ASSIGNEE_HA_USER_ID,
    ):
        value = user_data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _all_users_unlinked(users: dict[str, object]) -> bool:
    """Return True when all user records have no HA user linkage."""
    found_user_record = False
    for user_data in users.values():
        if not isinstance(user_data, dict):
            continue
        found_user_record = True
        if _get_record_ha_user_ref(user_data) not in (None, ""):
            return False
    return found_user_record


async def _has_management_authority(
    hass: HomeAssistant,
    user_id: str,
) -> bool:
    """Check whether a user can perform management actions."""
    if not user_id:
        return False

    user: User | None = await hass.auth.async_get_user(user_id)
    if not user:
        return False

    if user.is_admin:
        return True

    coordinator: ChoreOpsDataCoordinator | None = _get_choreops_coordinator(hass)
    if not coordinator:
        return False

    users = coordinator._data.get(const.DATA_USERS, {})
    if isinstance(users, dict) and users:
        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue
            if _ha_user_ref_matches(
                user,
                _get_record_ha_user_ref(user_data),
            ) and user_data.get(
                const.DATA_USER_CAN_MANAGE,
                False,
            ):
                return True

    # Legacy fallback during migration
    for approver_record in coordinator.approvers_data.values():
        if _ha_user_ref_matches(
            user, approver_record.get(const.DATA_APPROVER_HA_USER_ID)
        ) and approver_record.get(const.DATA_USER_CAN_MANAGE, False):
            return True

    return False


async def _has_approval_authority_for_target(
    hass: HomeAssistant,
    user_id: str,
    target_user_id: str,
) -> bool:
    """Check whether a user can perform approval actions for a target user."""
    if not user_id:
        return False

    user: User | None = await hass.auth.async_get_user(user_id)
    if not user:
        return False

    if user.is_admin:
        return True

    coordinator: ChoreOpsDataCoordinator | None = _get_choreops_coordinator(hass)
    if not coordinator:
        return False

    users = coordinator._data.get(const.DATA_USERS, {})
    if isinstance(users, dict) and users:
        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue
            if _ha_user_ref_matches(
                user,
                _get_record_ha_user_ref(user_data),
            ) and user_data.get(
                const.DATA_USER_CAN_APPROVE,
                False,
            ):
                return True

        if _all_users_unlinked(users):
            return True

    # Legacy fallback during migration
    for approver_record in coordinator.approvers_data.values():
        if _ha_user_ref_matches(
            user, approver_record.get(const.DATA_APPROVER_HA_USER_ID)
        ) and approver_record.get(const.DATA_USER_CAN_APPROVE, False):
            return True

    return False


async def _has_participation_authority_for_target(
    hass: HomeAssistant,
    user_id: str,
    target_user_id: str,
) -> bool:
    """Check whether a user can perform participation actions for a target user."""
    if not user_id:
        return False

    user: User | None = await hass.auth.async_get_user(user_id)
    if not user:
        return False

    if user.is_admin:
        return True

    coordinator: ChoreOpsDataCoordinator | None = _get_choreops_coordinator(hass)
    if not coordinator:
        return False

    users = coordinator._data.get(const.DATA_USERS, {})
    if isinstance(users, dict) and users:
        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue
            if _ha_user_ref_matches(
                user,
                _get_record_ha_user_ref(user_data),
            ) and user_data.get(
                const.DATA_USER_CAN_APPROVE,
                False,
            ):
                return True

        target_data = users.get(target_user_id)
        if isinstance(target_data, dict):
            linked_ha_id = _get_record_ha_user_ref(target_data)
            can_be_assigned = target_data.get(const.DATA_USER_CAN_BE_ASSIGNED, True)
            if _ha_user_ref_matches(user, linked_ha_id) and can_be_assigned:
                return True
            if can_be_assigned and linked_ha_id in (None, ""):
                return True

        for user_key, user_data in users.items():
            if not isinstance(user_data, dict):
                continue
            if not _ha_user_ref_matches(user, _get_record_ha_user_ref(user_data)):
                continue
            if not user_data.get(const.DATA_USER_CAN_BE_ASSIGNED, True):
                continue

            user_internal_id = user_data.get(const.DATA_USER_INTERNAL_ID)
            if target_user_id in {user_key, user_internal_id}:
                return True

        assignee_info = coordinator.assignees_data.get(target_user_id)
        if assignee_info:
            linked_ha_id = assignee_info.get(const.DATA_ASSIGNEE_HA_USER_ID)
            if _ha_user_ref_matches(user, linked_ha_id):
                return True
            if linked_ha_id in (None, ""):
                return True
        return False

    # Legacy fallback during migration
    for approver_record in coordinator.approvers_data.values():
        if _ha_user_ref_matches(
            user, approver_record.get(const.DATA_APPROVER_HA_USER_ID)
        ) and approver_record.get(const.DATA_USER_CAN_APPROVE, False):
            return True

    assignee_info = coordinator.assignees_data.get(target_user_id)
    if not assignee_info:
        return False

    linked_ha_id = assignee_info.get(const.DATA_ASSIGNEE_HA_USER_ID)
    if _ha_user_ref_matches(user, linked_ha_id):
        return True
    if linked_ha_id in (None, ""):
        return True

    return False
