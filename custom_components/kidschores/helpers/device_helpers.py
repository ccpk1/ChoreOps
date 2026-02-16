# File: helpers/device_helpers.py
"""Device registry helper functions for KidsChores.

Functions that construct DeviceInfo objects for Home Assistant's device registry.
All functions here use HA-specific DeviceInfo/DeviceEntryType types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .. import const

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import KidData


# ==============================================================================
# Device Info Construction
# ==============================================================================


def create_kid_device_info(
    kid_id: str,
    kid_name: str,
    config_entry: ConfigEntry,
    *,
    is_shadow_kid: bool = False,
) -> DeviceInfo:
    """Create device info for a kid profile.

    Args:
        kid_id: Internal ID (UUID) of the kid
        kid_name: Display name of the kid
        config_entry: Config entry for this integration instance
        is_shadow_kid: If True, this is a shadow kid (parent with chore assignment)

    Returns:
        DeviceInfo dict for the kid device
    """
    # Use different model text for shadow kids vs regular kids
    model = "Parent Profile" if is_shadow_kid else "Kid Profile"

    return DeviceInfo(
        identifiers={(const.DOMAIN, kid_id)},
        name=f"{kid_name} ({config_entry.title})",
        manufacturer="KidsChores",
        model=model,
        entry_type=DeviceEntryType.SERVICE,
    )


def create_kid_device_info_from_coordinator(
    coordinator: KidsChoresDataCoordinator,
    kid_id: str,
    kid_name: str,
    config_entry: ConfigEntry,
) -> DeviceInfo:
    """Create device info for a kid profile, auto-detecting shadow kid status.

    This is a convenience wrapper around create_kid_device_info that looks up
    the shadow kid status from the coordinator's kids_data.

    Args:
        coordinator: The KidsChoresCoordinator instance
        kid_id: Internal ID (UUID) of the kid
        kid_name: Display name of the kid
        config_entry: Config entry for this integration instance

    Returns:
        DeviceInfo dict for the kid device with correct model (Kid/Parent Profile)
    """
    kid_data: KidData | None = coordinator.kids_data.get(kid_id)
    is_shadow_kid = kid_data.get(const.DATA_KID_IS_SHADOW, False) if kid_data else False
    return create_kid_device_info(
        kid_id, kid_name, config_entry, is_shadow_kid=is_shadow_kid
    )


def create_system_device_info(config_entry: ConfigEntry) -> DeviceInfo:
    """Create device info for system/global entities.

    Args:
        config_entry: Config entry for this integration instance

    Returns:
        DeviceInfo dict for the system device
    """
    return DeviceInfo(
        identifiers={(const.DOMAIN, f"{config_entry.entry_id}_system")},
        name=f"System ({config_entry.title})",
        manufacturer="KidsChores",
        model="System Controls",
        entry_type=DeviceEntryType.SERVICE,
    )
