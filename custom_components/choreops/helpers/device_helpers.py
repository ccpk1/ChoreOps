# File: helpers/device_helpers.py
"""Device registry helper functions for ChoreOps.

Functions that construct DeviceInfo objects for Home Assistant's device registry.
All functions here use HA-specific DeviceInfo/DeviceEntryType types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .. import const
from .entity_helpers import is_linked_profile

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from ..coordinator import ChoreOpsDataCoordinator


# ==============================================================================
# Device Info Construction
# ==============================================================================


def create_assignee_device_info(
    assignee_id: str,
    assignee_name: str,
    config_entry: ConfigEntry,
    *,
    is_feature_gated_profile: bool = False,
) -> DeviceInfo:
    """Create device info for an assignee profile.

    Args:
        assignee_id: Internal ID (UUID) of the assignee
        assignee_name: Display name of the assignee
        config_entry: Config entry for this integration instance
        is_feature_gated_profile: If True, this profile follows conditional
            feature gating behavior during migration.

    Returns:
        DeviceInfo dict for the assignee device
    """
    # Keep legacy parameter for compatibility; all profiles now use unified model label.
    _ = is_feature_gated_profile

    return DeviceInfo(
        identifiers={(const.DOMAIN, assignee_id)},
        name=f"{assignee_name} ({config_entry.title})",
        manufacturer=const.DEVICE_MANUFACTURER,
        model=const.DEVICE_MODEL_USER_PROFILE,
        entry_type=DeviceEntryType.SERVICE,
    )


def create_assignee_device_info_from_coordinator(
    coordinator: ChoreOpsDataCoordinator,
    assignee_id: str,
    assignee_name: str,
    config_entry: ConfigEntry,
) -> DeviceInfo:
    """Create device info for an assignee profile, auto-detecting gating status.

    This is a convenience wrapper around create_assignee_device_info that looks up
    the feature-gated profile status from the coordinator's assignees_data.

    Args:
        coordinator: The ChoreOpsCoordinator instance
        assignee_id: Internal ID (UUID) of the assignee
        assignee_name: Display name of the assignee
        config_entry: Config entry for this integration instance

    Returns:
        DeviceInfo dict for the assignee device with correct model
    """
    is_feature_gated_profile = is_linked_profile(coordinator, assignee_id)
    return create_assignee_device_info(
        assignee_id,
        assignee_name,
        config_entry,
        is_feature_gated_profile=is_feature_gated_profile,
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
        manufacturer=const.DEVICE_MANUFACTURER,
        model=const.DEVICE_MODEL_SYSTEM_CONTROLS,
        entry_type=DeviceEntryType.SERVICE,
    )
