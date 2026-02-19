# File: helpers/auth_helpers.py
"""Authorization helper functions for KidsChores.

Functions that check user permissions for KidsChores operations.
All functions here require a `hass` object for auth system access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from .. import const

if TYPE_CHECKING:
    from homeassistant.auth.models import User
    from homeassistant.core import HomeAssistant

    from ..coordinator import KidsChoresDataCoordinator


# ==============================================================================
# Coordinator Access
# ==============================================================================


def _get_kidschores_coordinator(
    hass: HomeAssistant,
) -> KidsChoresDataCoordinator | None:
    """Retrieve KidsChores coordinator from config entry runtime_data.

    Args:
        hass: HomeAssistant instance

    Returns:
        KidsChoresDataCoordinator if found, None otherwise
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
    """Return whether kiosk mode is enabled in active KidsChores options.

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

type AuthorizationAction = Literal["approval", "management"]

AUTH_ACTION_APPROVAL: Final[AuthorizationAction] = "approval"
AUTH_ACTION_MANAGEMENT: Final[AuthorizationAction] = "management"


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

    return False


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

    coordinator: KidsChoresDataCoordinator | None = _get_kidschores_coordinator(hass)
    if not coordinator:
        return False

    users = coordinator._data.get(const.DATA_USERS, {})
    if isinstance(users, dict) and users:
        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue
            if user_data.get(const.DATA_USER_HA_USER_ID) == user.id and user_data.get(
                const.DATA_USER_CAN_MANAGE,
                False,
            ):
                return True
        return False

    # Legacy fallback during migration
    for parent in coordinator.parents_data.values():
        if parent.get(const.DATA_PARENT_HA_USER_ID) == user.id:
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

    coordinator: KidsChoresDataCoordinator | None = _get_kidschores_coordinator(hass)
    if not coordinator:
        return False

    users = coordinator._data.get(const.DATA_USERS, {})
    if isinstance(users, dict) and users:
        for user_data in users.values():
            if not isinstance(user_data, dict):
                continue
            if user_data.get(const.DATA_USER_HA_USER_ID) == user.id and user_data.get(
                const.DATA_USER_CAN_APPROVE,
                False,
            ):
                return True

        target_data = users.get(target_user_id)
        if isinstance(target_data, dict):
            linked_ha_id = target_data.get(const.DATA_USER_HA_USER_ID)
            can_be_assigned = target_data.get(const.DATA_USER_CAN_BE_ASSIGNED, True)
            if linked_ha_id and linked_ha_id == user.id and can_be_assigned:
                return True
        return False

    # Legacy fallback during migration
    for parent in coordinator.parents_data.values():
        if parent.get(const.DATA_PARENT_HA_USER_ID) == user.id:
            return True

    kid_info = coordinator.kids_data.get(target_user_id)
    if not kid_info:
        return False

    linked_ha_id = kid_info.get(const.DATA_KID_HA_USER_ID)
    if linked_ha_id and linked_ha_id == user.id:
        return True

    return False
