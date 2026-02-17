# File: helpers/auth_helpers.py
"""Authorization helper functions for KidsChores.

Functions that check user permissions for KidsChores operations.
All functions here require a `hass` object for auth system access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


async def is_user_authorized_for_global_action(
    hass: HomeAssistant,
    user_id: str,
    action: str,
) -> bool:
    """Check if user is allowed to do a global action (penalty, reward, points adjust).

    Authorization rules:
      - Admin users => authorized
      - Registered KidsChores parents => authorized
      - Everyone else => not authorized

    Args:
        hass: HomeAssistant instance
        user_id: User ID to check
        action: Action name for logging purposes

    Returns:
        True if authorized, False otherwise
    """
    if not user_id:
        return False

    user: User | None = await hass.auth.async_get_user(user_id)
    if not user:
        const.LOGGER.warning("WARNING: %s: Invalid user ID '%s'", action, user_id)
        return False

    if user.is_admin:
        return True

    # Allow non-admin users if they are registered as a parent in KidsChores
    coordinator = _get_kidschores_coordinator(hass)
    if coordinator:
        for parent in coordinator.parents_data.values():
            if parent.get(const.DATA_PARENT_HA_USER_ID) == user.id:
                return True

    const.LOGGER.warning(
        "WARNING: %s: Non-admin user '%s' is not authorized in this logic",
        action,
        user.name,
    )
    return False


async def is_user_authorized_for_kid(
    hass: HomeAssistant,
    user_id: str,
    kid_id: str,
) -> bool:
    """Check if user is authorized to manage chores/rewards for a specific kid.

    Authorization rules:
      - Admin => authorized
      - If kid_info['ha_user_id'] == user.id => authorized
      - If user is a registered parent => authorized
      - Otherwise => not authorized

    Args:
        hass: HomeAssistant instance
        user_id: User ID to check
        kid_id: Kid ID to check authorization for

    Returns:
        True if authorized, False otherwise
    """
    if not user_id:
        return False

    user: User | None = await hass.auth.async_get_user(user_id)
    if not user:
        const.LOGGER.warning("WARNING: Authorization: Invalid user ID '%s'", user_id)
        return False

    # Admin => automatically allowed
    if user.is_admin:
        return True

    # Allow non-admin users if they are registered as a parent in KidsChores
    coordinator: KidsChoresDataCoordinator | None = _get_kidschores_coordinator(hass)
    if coordinator:
        for parent in coordinator.parents_data.values():
            if parent.get(const.DATA_PARENT_HA_USER_ID) == user.id:
                return True

    if not coordinator:
        const.LOGGER.warning("WARNING: Authorization: KidsChores coordinator not found")
        return False

    kid_info = coordinator.kids_data.get(kid_id)
    if not kid_info:
        const.LOGGER.warning(
            "WARNING: Authorization: Kid ID '%s' not found in coordinator data", kid_id
        )
        return False

    linked_ha_id = kid_info.get(const.DATA_KID_HA_USER_ID)
    if linked_ha_id and linked_ha_id == user.id:
        return True

    const.LOGGER.warning(
        "WARNING: Authorization: Non-admin user '%s' attempted to manage Kid ID '%s' but is not linked",
        user.name,
        kid_info.get(const.DATA_KID_NAME),
    )
    return False
