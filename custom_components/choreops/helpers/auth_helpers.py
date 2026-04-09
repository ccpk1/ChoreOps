# File: helpers/auth_helpers.py
"""Authorization helper functions for ChoreOps.

Functions that check user permissions for ChoreOps operations.
All functions here require a `hass` object for auth system access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from .. import const

if TYPE_CHECKING:
    from collections.abc import Mapping

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


def is_admin_approval_bypass_enabled(hass: HomeAssistant) -> bool:
    """Return whether Home Assistant admins bypass approval link checks."""
    entries = hass.config_entries.async_entries(const.DOMAIN)
    if not entries:
        return const.DEFAULT_ADMIN_APPROVAL_BYPASS

    for entry in entries:
        if entry.state.name == "LOADED":
            return entry.options.get(
                const.CONF_ADMIN_APPROVAL_BYPASS,
                const.DEFAULT_ADMIN_APPROVAL_BYPASS,
            )

    return const.DEFAULT_ADMIN_APPROVAL_BYPASS


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
    user_name = user.name if isinstance(user.name, str) else ""
    normalized_name = "".join(ch for ch in user_name.lower() if ch.isalnum())

    return ha_user_ref == user.id or normalized_ref == normalized_name


def _get_record_ha_user_ref(user_data: Mapping[str, object]) -> str | None:
    """Return HA user reference from canonical or compatibility keys."""
    for key in (const.DATA_USER_HA_USER_ID,):
        value = user_data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _get_associated_user_ids(user_data: Mapping[str, object]) -> set[str]:
    """Return normalized associated user IDs for a user record."""
    associated_user_ids = user_data.get(const.DATA_USER_ASSOCIATED_USER_IDS)
    if not isinstance(associated_user_ids, list):
        return set()

    return {
        associated_user_id
        for associated_user_id in associated_user_ids
        if isinstance(associated_user_id, str) and associated_user_id
    }


def _get_target_user_aliases(
    users: dict[str, object],
    target_user_id: str,
) -> set[str]:
    """Return all known identifiers that may refer to the target user."""
    target_aliases = {target_user_id}

    target_user_data = users.get(target_user_id)
    if isinstance(target_user_data, dict):
        internal_id = target_user_data.get(const.DATA_USER_INTERNAL_ID)
        if isinstance(internal_id, str) and internal_id:
            target_aliases.add(internal_id)

    for user_key, user_data in users.items():
        if not isinstance(user_data, dict):
            continue

        internal_id = user_data.get(const.DATA_USER_INTERNAL_ID)
        if internal_id == target_user_id:
            target_aliases.add(user_key)

    return target_aliases


def _find_user_record_for_ha_user(
    users: dict[str, object],
    user: User,
) -> dict[str, object] | None:
    """Return the canonical user record linked to a Home Assistant user."""
    for user_data in users.values():
        if not isinstance(user_data, dict):
            continue

        if _ha_user_ref_matches(user, _get_record_ha_user_ref(user_data)):
            return user_data

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
            user, approver_record.get(const.DATA_USER_HA_USER_ID)
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

    admin_approval_bypass_enabled = is_admin_approval_bypass_enabled(hass)
    if user.is_admin:
        return admin_approval_bypass_enabled

    coordinator: ChoreOpsDataCoordinator | None = _get_choreops_coordinator(hass)
    if not coordinator:
        return False

    users = coordinator._data.get(const.DATA_USERS, {})
    if isinstance(users, dict) and users:
        actor_user_data = _find_user_record_for_ha_user(users, user)
        if actor_user_data is not None:
            if not actor_user_data.get(const.DATA_USER_CAN_APPROVE, False):
                return False

            associated_user_ids = _get_associated_user_ids(actor_user_data)
            if not associated_user_ids:
                return False

            target_aliases = _get_target_user_aliases(users, target_user_id)
            return bool(associated_user_ids & target_aliases)

        if _all_users_unlinked(users):
            return True

    # Legacy fallback during migration
    for approver_record in coordinator.approvers_data.values():
        if not _ha_user_ref_matches(
            user, approver_record.get(const.DATA_USER_HA_USER_ID)
        ):
            continue

        if not approver_record.get(const.DATA_USER_CAN_APPROVE, False):
            return False

        associated_user_ids = _get_associated_user_ids(approver_record)
        if not associated_user_ids:
            return False

        return target_user_id in associated_user_ids

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
            linked_ha_id = assignee_info.get(const.DATA_USER_HA_USER_ID)
            if _ha_user_ref_matches(user, linked_ha_id):
                return True
        return False

    # Legacy fallback during migration
    for approver_record in coordinator.approvers_data.values():
        if _ha_user_ref_matches(
            user, approver_record.get(const.DATA_USER_HA_USER_ID)
        ) and approver_record.get(const.DATA_USER_CAN_APPROVE, False):
            return True

    assignee_info = coordinator.assignees_data.get(target_user_id)
    if not assignee_info:
        return False

    linked_ha_id = assignee_info.get(const.DATA_USER_HA_USER_ID)
    if _ha_user_ref_matches(user, linked_ha_id):
        return True

    return False
