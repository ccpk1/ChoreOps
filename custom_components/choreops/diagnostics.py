"""Diagnostics support for ChoreOps integration.

Provides comprehensive data export for troubleshooting and backup/restore.
The diagnostics JSON returns raw storage data - byte-for-byte identical to
the choreops_data file for direct paste during data recovery.
"""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import const
from .coordinator import ChoreOpsConfigEntry
from .helpers.storage_helpers import get_entry_storage_key_from_entry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ChoreOpsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Returns the raw storage data directly - byte-for-byte identical to the
    choreops_data file. This can be pasted directly during data recovery
    with no transformation needed.

    Benefits:
    - No parsing/reformatting overhead
    - Future-proof (all storage keys automatically included)
    - Direct paste during recovery
    - Coordinator migration handles schema differences
    """
    coordinator = entry.runtime_data

    # Get base storage data
    diagnostics_data = dict(coordinator.store.data)

    # Add config_entry_settings section for complete backup/restore
    diagnostics_data[const.DATA_CONFIG_ENTRY_SETTINGS] = {
        key: entry.options.get(key, default)
        for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
    }

    diagnostics_data["storage_context"] = {
        "entry_id": entry.entry_id,
        "storage_key": get_entry_storage_key_from_entry(entry),
        "storage_path": coordinator.store.get_storage_path(),
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ChoreOpsConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry.

    Provides assignee-specific view of data for troubleshooting individual assignees.
    """
    coordinator = entry.runtime_data

    # Extract assignee_id from device identifiers
    assignee_id = None
    scoped_prefix = f"{entry.entry_id}_"
    for identifier in device.identifiers:
        if identifier[0] == const.DOMAIN:
            identifier_value = identifier[1]
            if identifier_value.startswith(scoped_prefix):
                assignee_id = identifier_value[len(scoped_prefix) :]
            else:
                assignee_id = identifier_value
            break

    if not assignee_id:
        return {"error": "Could not determine assignee_id from device identifiers"}

    assignee_data = coordinator.assignees_data.get(assignee_id)
    if not assignee_data:
        return {"error": f"Assignee data not found for assignee_id: {assignee_id}"}

    # Return assignee-specific data snapshot
    return {
        "assignee_id": assignee_id,
        "assignee_data": assignee_data,
    }
