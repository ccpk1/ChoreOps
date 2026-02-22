# File: helpers/entity_helpers.py
"""Entity registry helper functions for ChoreOps.

Functions that interact with Home Assistant's entity registry for querying,
parsing unique IDs, and removing entities.

All functions here require a `hass` object or interact with HA registries.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import (
    RegistryEntry,
    async_entries_for_config_entry,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.label_registry import async_get as async_get_label_registry

from .. import const

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator


# ==============================================================================
# Event Signal Helpers (Manager Communication)
# ==============================================================================


def get_event_signal(entry_id: str, suffix: str) -> str:
    """Build instance-scoped event signal name for dispatcher.

    This ensures complete isolation between multiple ChoreOps config entries.
    Each instance gets its own signal namespace using its config_entry.entry_id.

    Format: 'choreops_{entry_id}_{suffix}'

    Multi-instance example:
        - Instance 1 (entry_id="abc123"):
          get_event_signal("abc123", "points_changed") → "choreops_abc123_points_changed"
        - Instance 2 (entry_id="xyz789"):
          get_event_signal("xyz789", "points_changed") → "choreops_xyz789_points_changed"

    Managers can emit/listen without cross-talk between instances.

    Args:
        entry_id: ConfigEntry.entry_id from coordinator
        suffix: Signal suffix constant from const.py (e.g., SIGNAL_SUFFIX_POINTS_CHANGED)

    Returns:
        Fully qualified signal name scoped to this integration instance

    Example:
        >>> from .. import const
        >>> get_event_signal("abc123", const.SIGNAL_SUFFIX_POINTS_CHANGED)
        'choreops_abc123_points_changed'
    """
    return f"{const.DOMAIN}_{entry_id}_{suffix}"


# ==============================================================================
# Entity Registry Queries
# ==============================================================================


def get_integration_entities(
    hass: HomeAssistant,
    entry_id: str,
    platform: str | None = None,
) -> list[RegistryEntry]:
    """Get all integration entities, optionally filtered by platform.

    Centralizes entity registry queries used across multiple coordinator
    methods. Read-only utility - does not modify entities.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID to filter entities.
        platform: Optional platform filter (e.g., "button", "sensor").
            If None, returns all platforms.

    Returns:
        List of RegistryEntry objects matching criteria.

    Example:
        # Get all sensor entities for this integration
        sensors = get_integration_entities(hass, entry.entry_id, "sensor")

        # Get all entities regardless of platform
        all_entities = get_integration_entities(hass, entry.entry_id)
    """
    entity_registry = async_get_entity_registry(hass)

    # Get only entities from THIS config entry (not all system entities)
    entities = async_entries_for_config_entry(entity_registry, entry_id)

    if platform:
        entities = [e for e in entities if e.domain == platform]

    return entities


def get_points_adjustment_buttons(
    hass: HomeAssistant,
    entry_id: str,
    assignee_id: str,
) -> list[dict[str, Any]]:
    """Get all point adjustment buttons for a assignee with parsed display info.

    Searches for buttons matching the pattern:
    {entry_id}_{assignee_id}_{slugified_delta}_approver_points_adjust_button

    Uses config entry filtering for performance (O(n) where n = our entities only).
    Returns sorted list by delta value (negatives first, then positives).

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        assignee_id: Assignee's internal_id (UUID).

    Returns:
        List of dicts sorted by delta value:
        [
            {"eid": "button.xyz", "name": "Points +5", "delta": 5.0},
            {"eid": "button.abc", "name": "Points -2", "delta": -2.0},
        ]

    Example:
        buttons = get_points_adjustment_buttons(hass, entry.entry_id, assignee_id)
        button_eids = [b["eid"] for b in buttons]

    Note:
        Consolidates button parsing logic previously duplicated in sensor.py
        and button.py. No type guards needed - we control all our unique_ids.
    """
    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)

    # Get only entities from THIS config entry (not all system entities)
    entities = er.async_entries_for_config_entry(entity_registry, entry_id)

    button_suffix = const.BUTTON_KC_UID_SUFFIX_APPROVER_POINTS_ADJUST
    prefix_pattern = f"{entry_id}_{assignee_id}_"
    temp_buttons = []

    for entity in entities:
        # Filter to buttons with the approver points adjust suffix
        if (
            entity.domain != "button"
            or button_suffix not in entity.unique_id
            or not entity.unique_id.startswith(prefix_pattern)
        ):
            continue

        # Extract delta from unique_id
        # Format: {entry_id}_{assignee_id}_{slugified_delta}_approver_points_adjust_button
        try:
            prefix_part = entity.unique_id.split(button_suffix)[0]
            delta_slug = prefix_part.split("_")[-1]
            # Convert slugified delta back to float (replace 'neg' prefix and 'p' decimal)
            delta_str = delta_slug.replace("neg", "-").replace("p", ".")
            delta_value = float(delta_str)

            # Format display name (keep + for positive, - for negative)
            if delta_value >= 0:
                display_name = f"Points +{delta_str}"
            else:
                display_name = f"Points {delta_str}"

        except (ValueError, IndexError):
            # Fallback for malformed unique_ids
            delta_value = 0
            display_name = "Points +0"

        temp_buttons.append(
            {
                "eid": entity.entity_id,
                "name": display_name,
                "delta": delta_value,
            }
        )

    # Sort by delta value (negatives first, then positives, all ascending)
    from typing import cast

    temp_buttons.sort(key=lambda x: cast("float", x["delta"]))

    return temp_buttons


def parse_entity_reference(
    unique_id: str,
    prefix: str,
) -> tuple[str, ...] | None:
    """Parse entity unique_id into component parts after removing prefix.

    Used to extract assignee IDs, chore IDs, etc. from entity unique IDs.
    Read-only utility - does not modify entities.

    Args:
        unique_id: Entity unique_id (e.g., "entry_123_assignee_456_chore_789").
        prefix: Config entry prefix to strip (e.g., "entry_123_").

    Returns:
        Tuple of ID components after prefix, or None if invalid format.

    Example:
        >>> parse_entity_reference("entry_123_assignee_456_chore_789", "entry_123_")
        ('assignee_456', 'chore_789')

        >>> parse_entity_reference("invalid", "entry_123_")
        None

    Note:
        Uses underscore delimiters. Returns None for malformed IDs.
    """
    if not unique_id.startswith(prefix):
        return None

    # Strip prefix and split by underscore
    remainder = unique_id[len(prefix) :]
    if not remainder:
        return None

    # Split into component parts
    parts = remainder.split("_")
    if not parts or any(not part for part in parts):
        return None

    return tuple(parts)


def build_orphan_detection_regex(
    valid_ids: list[str],
    separator: str = "_",
) -> re.Pattern[str]:
    """Build compiled regex for O(n) orphan detection.

    Creates a regex pattern that matches ANY of the provided valid IDs,
    enabling efficient detection of orphaned references in unique_ids.

    Args:
        valid_ids: List of valid internal IDs to match against.
        separator: Delimiter used in unique_ids (default: "_").

    Returns:
        Compiled regex pattern for matching valid IDs.

    Example:
        >>> pattern = build_orphan_detection_regex(['uuid1', 'uuid2'])
        >>> bool(pattern.search('entry_uuid1_sensor'))
        True
        >>> bool(pattern.search('entry_uuid3_sensor'))
        False
    """
    if not valid_ids:
        # Return pattern that never matches
        return re.compile(r"(?!)")

    # Escape IDs for regex safety
    escaped_ids = [re.escape(id_str) for id_str in valid_ids]

    # Build pattern: separator + ID + (separator or end)
    pattern = (
        f"{re.escape(separator)}({'|'.join(escaped_ids)})(?:{re.escape(separator)}|$)"
    )

    return re.compile(pattern)


def remove_entities_by_item_id(
    hass: HomeAssistant,
    entry_id: str,
    item_id: str,
) -> int:
    """Remove all entities whose unique_id references the given item_id.

    Called when deleting assignees, chores, rewards, penalties, bonuses, badges.
    Uses delimiter matching to prevent false positives (e.g., assignee_1 should
    not match assignee_10).

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID prefix for unique_id matching.
        item_id: The UUID of the deleted item.

    Returns:
        Count of removed entities.
    """
    perf_start = time.perf_counter()
    ent_reg = async_get_entity_registry(hass)
    prefix = f"{entry_id}_"
    item_id_str = str(item_id)
    removed_count = 0

    # Get only entities from THIS config entry (not all system entities)
    entities = async_entries_for_config_entry(ent_reg, entry_id)

    for entity_entry in entities:
        unique_id = str(entity_entry.unique_id)

        # Safety: verify our entry prefix
        if not unique_id.startswith(prefix):
            continue

        # Match item_id with proper delimiters (midfix or suffix)
        # Patterns: ..._{item_id}_... or ..._{item_id}
        if f"_{item_id_str}_" in unique_id or unique_id.endswith(f"_{item_id_str}"):
            ent_reg.async_remove(entity_entry.entity_id)
            removed_count += 1
            const.LOGGER.debug(
                "Removed entity %s (uid: %s) for deleted item %s",
                entity_entry.entity_id,
                unique_id,
                item_id_str,
            )

    perf_elapsed = time.perf_counter() - perf_start
    if removed_count > 0:
        const.LOGGER.info(
            "Removed %d entities for deleted item in %.3fs",
            removed_count,
            perf_elapsed,
        )

    return removed_count


# ==============================================================================
# Entity ID Lookups
# ==============================================================================


def get_first_choreops_entry(hass: HomeAssistant) -> str | None:
    """Get the entry_id of the first loaded ChoreOps config entry.

    Args:
        hass: HomeAssistant instance

    Returns:
        Config entry ID string, or None if no loaded entries
    """
    entries = hass.config_entries.async_entries(const.DOMAIN)
    for entry in entries:
        if entry.state.name == "LOADED":
            return entry.entry_id
    return None


def get_entity_id_from_unique_id(
    hass: HomeAssistant,
    unique_id: str,
    domain: str | None = None,
) -> str | None:
    """Get entity_id from a unique_id using registry lookup.

    Uses Home Assistant's built-in entity registry lookup for O(1) performance
    when domain is known, or searches all common domains as fallback.

    Args:
        hass: HomeAssistant instance
        unique_id: The unique_id to look up
        domain: Optional entity domain (sensor, button, etc.) for faster lookup.
            If None, searches all common ChoreOps domains.

    Returns:
        entity_id string, or None if not found

    Example:
        # Fast path with known domain
        eid = get_entity_id_from_unique_id(hass, "abc-123", "sensor")

        # Slower fallback without domain
        eid = get_entity_id_from_unique_id(hass, "abc-123")

    Note:
        Optimized from O(n) iteration to O(1) registry lookup when domain known.
        For unknown domains, searches common ChoreOps entity types.
    """
    entity_registry = async_get_entity_registry(hass)

    if domain:
        # Fast path: O(1) direct lookup if domain known
        return entity_registry.async_get_entity_id(domain, const.DOMAIN, unique_id)

    # Fallback: search all common ChoreOps domains (rare case)
    # Only searches domains we actually use in this integration
    for domain_type in ["sensor", "button", "select", "datetime", "calendar"]:
        eid = entity_registry.async_get_entity_id(domain_type, const.DOMAIN, unique_id)
        if eid:
            return eid

    return None


def get_friendly_label(hass: HomeAssistant, label_name: str) -> str:
    """Get a friendly display name for a label.

    Args:
        hass: HomeAssistant instance
        label_name: The label ID/name to look up

    Returns:
        Label's display name, or the label_name if not found
    """
    label_registry = async_get_label_registry(hass)
    label_entry = label_registry.async_get_label(label_name)
    if label_entry:
        return label_entry.name
    return label_name


# ==============================================================================
# Item Lookup Helpers (Domain Items in Storage)
# Basic ID/name lookups returning None, and error-raising variants for services.
# These operate on Domain Items (Assignee, Chore, Reward, etc.), NOT HA Entities.
# ==============================================================================


def get_item_id_by_name(
    coordinator: ChoreOpsDataCoordinator, item_type: str, item_name: str
) -> str | None:
    """Look up a Domain Item's internal ID (UUID) by name.

    Searches the storage for a Domain Item (Assignee, Chore, Reward, etc.) by its name
    and returns the internal_id (UUID) if found. This is NOT looking up an HA Entity.

    Args:
        coordinator: The ChoreOps data coordinator.
        item_type: The type of Domain Item ("assignee", "chore", "reward", "penalty",
            "badge", "bonus", "approver", "achievement", "challenge").
        item_name: The name of the Item to look up.

    Returns:
        The internal ID (UUID) of the Item, or None if not found.

    Raises:
        ValueError: If item_type is not recognized.
    """
    # Map item type to (data dict, name key constant)
    item_map = {
        const.ENTITY_TYPE_ASSIGNEE: (
            coordinator.assignees_data,
            const.DATA_ASSIGNEE_NAME,
        ),
        const.ENTITY_TYPE_CHORE: (coordinator.chores_data, const.DATA_CHORE_NAME),
        const.ENTITY_TYPE_REWARD: (coordinator.rewards_data, const.DATA_REWARD_NAME),
        const.ENTITY_TYPE_PENALTY: (
            coordinator.penalties_data,
            const.DATA_PENALTY_NAME,
        ),
        const.ENTITY_TYPE_BADGE: (coordinator.badges_data, const.DATA_BADGE_NAME),
        const.ENTITY_TYPE_BONUS: (coordinator.bonuses_data, const.DATA_BONUS_NAME),
        const.ENTITY_TYPE_APPROVER: (
            coordinator.approvers_data,
            const.DATA_APPROVER_NAME,
        ),
        const.ENTITY_TYPE_ACHIEVEMENT: (
            coordinator.achievements_data,
            const.DATA_ACHIEVEMENT_NAME,
        ),
        const.ENTITY_TYPE_CHALLENGE: (
            coordinator.challenges_data,
            const.DATA_CHALLENGE_NAME,
        ),
    }

    if item_type not in item_map:
        raise ValueError(
            f"Unknown item_type: {item_type}. Valid options: {', '.join(item_map.keys())}"
        )

    data_dict, name_key = item_map[item_type]
    data_dict = cast("dict[str, Any]", data_dict)
    for item_id, item_info in data_dict.items():
        if item_info.get(name_key) == item_name:
            return item_id
    return None


def get_item_id_or_raise(
    coordinator: ChoreOpsDataCoordinator, item_type: str, item_name: str
) -> str:
    """Look up a Domain Item's internal ID (UUID) by name, or raise error if not found.

    Generic version for service handlers. Centralizes error handling pattern
    for Item lookups across services. This is NOT looking up an HA Entity.

    Args:
        coordinator: The ChoreOps data coordinator.
        item_type: The type of Domain Item ("assignee", "chore", "reward", "penalty",
            "badge", "bonus", "approver", "achievement", "challenge").
        item_name: The name of the Item to look up.

    Returns:
        The internal ID (UUID) of the Item.

    Raises:
        HomeAssistantError: If the Item is not found in storage.
    """
    item_id = get_item_id_by_name(coordinator, item_type, item_name)
    if not item_id:
        raise HomeAssistantError(
            f"{item_type.capitalize()} item '{item_name}' not found"
        )
    return item_id


def get_item_name_or_log_error(
    item_type: str,
    item_id: str,
    item_data: Mapping[str, Any],
    name_key: str,
) -> str | None:
    """Get Domain Item name from storage data, log error if missing (data corruption detection).

    Args:
        item_type: Type of Domain Item (for logging) e.g. 'assignee', 'chore', 'reward'
        item_id: Internal ID/UUID of the Item (for logging)
        item_data: Dict containing the Item's data from storage
        name_key: Key to look up name in item_data

    Returns:
        Item name if present, None if missing (with error log).
        A missing name indicates data corruption in storage.
    """
    # If item_data is empty dict, item was likely deleted (race during cleanup)
    # Return None silently instead of logging corruption error
    if not item_data:
        return None

    name = item_data.get(name_key)
    if not name:
        const.LOGGER.error(
            "Data corruption: %s item %s missing %s. HA Entity will not be created. "
            "This indicates a storage issue or validation bypass.",
            item_type,
            item_id,
            name_key,
        )
        return None
    return name


def get_assignee_name_by_id(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> str | None:
    """Retrieve the assignee name for a given internal ID.

    Args:
        coordinator: The ChoreOps data coordinator.
        assignee_id: The internal ID (UUID) of the assignee to look up.

    Returns:
        The assignee name, or None if not found.
    """
    assignee_info = coordinator.assignees_data.get(assignee_id)
    if assignee_info:
        return assignee_info.get(const.DATA_ASSIGNEE_NAME)
    return None


# ==============================================================================
# Orphan Entity Removal
# ==============================================================================


async def remove_entities_by_validator(
    hass: HomeAssistant,
    entry_id: str,
    *,
    platforms: list[str] | None = None,
    suffix: str | None = None,
    midfix: str | None = None,
    is_valid: Callable[[str], bool],
    entity_type: str = "entity",
) -> int:
    """Remove entities that fail a validation check.

    Core helper for removing orphaned entities whose underlying data relationship
    no longer exists. Uses efficient platform filtering and consistent logging.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID for filtering entities.
        platforms: Platforms to scan (None = all platforms for this entry).
        suffix: Only check entities with this UID suffix.
        midfix: Only check entities containing this string.
        is_valid: Callback(unique_id) → True if entity should be kept.
        entity_type: Display name for logging.

    Returns:
        Count of removed entities.

    Example:
        # Remove entities referencing deleted assignees
        removed = await remove_entities_by_validator(
            hass, entry_id,
            platforms=["sensor"],
            is_valid=lambda uid: extract_assignee_id(uid) in valid_assignee_ids,
            entity_type="assignee sensor",
        )
    """
    perf_start = time.perf_counter()
    prefix = f"{entry_id}_"
    removed_count = 0
    scanned_count = 0

    ent_reg = async_get_entity_registry(hass)

    # Get entities to scan (platform-filtered or all for this entry)
    if platforms:
        entities_to_scan = []
        for platform in platforms:
            entities_to_scan.extend(get_integration_entities(hass, entry_id, platform))
    else:
        entities_to_scan = get_integration_entities(hass, entry_id)

    for entity_entry in list(entities_to_scan):
        unique_id = str(entity_entry.unique_id)

        # Apply prefix filter
        if not unique_id.startswith(prefix):
            continue

        # Apply suffix filter if specified
        if suffix and not unique_id.endswith(suffix):
            continue

        # Apply midfix filter if specified
        if midfix and midfix not in unique_id:
            continue

        scanned_count += 1

        # Check validity - remove if not valid
        if not is_valid(unique_id):
            const.LOGGER.debug(
                "Removing orphaned %s: %s (uid: %s)",
                entity_type,
                entity_entry.entity_id,
                unique_id,
            )
            ent_reg.async_remove(entity_entry.entity_id)
            removed_count += 1

    perf_elapsed = time.perf_counter() - perf_start
    if removed_count > 0:
        const.LOGGER.info(
            "Removed %d orphaned %s(s) in %.3fs",
            removed_count,
            entity_type,
            perf_elapsed,
        )
    else:
        const.LOGGER.debug(
            "PERF: orphan scan for %s: %d checked in %.3fs, none removed",
            entity_type,
            scanned_count,
            perf_elapsed,
        )

    return removed_count


async def remove_orphaned_shared_chore_sensors(
    hass: HomeAssistant,
    entry_id: str,
    chores_data: dict[str, Any],
) -> int:
    """Remove shared chore sensors for chores no longer marked as shared.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        chores_data: Dict of chore_id → chore_info.

    Returns:
        Count of removed entities.
    """
    prefix = f"{entry_id}_"
    suffix = const.DATA_GLOBAL_STATE_SUFFIX

    def is_valid(unique_id: str) -> bool:
        chore_id = unique_id[len(prefix) : -len(suffix)]
        chore_info = chores_data.get(chore_id)
        return bool(
            chore_info
            and chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            == const.COMPLETION_CRITERIA_SHARED
        )

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.SENSOR],
        suffix=suffix,
        is_valid=is_valid,
        entity_type="shared chore sensor",
    )


async def remove_orphaned_assignee_chore_entities(
    hass: HomeAssistant,
    entry_id: str,
    assignees_data: dict[str, Any],
    chores_data: dict[str, Any],
) -> int:
    """Remove assignee-chore entities for assignees no longer assigned.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        assignees_data: Dict of assignee_id → assignee_info.
        chores_data: Dict of chore_id → chore_info.

    Returns:
        Count of removed entities.
    """
    if not assignees_data or not chores_data:
        return 0

    prefix = f"{entry_id}_"

    # Build valid assignee-chore combinations
    valid_combinations: set[tuple[str, str]] = set()
    for chore_id, chore_info in chores_data.items():
        for assignee_id in chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, []):
            valid_combinations.add((assignee_id, chore_id))

    # Build regex for efficient extraction
    assignee_ids = "|".join(re.escape(assignee_id) for assignee_id in assignees_data)
    chore_ids = "|".join(re.escape(chore_id) for chore_id in chores_data)
    pattern = re.compile(rf"^({assignee_ids})_({chore_ids})")

    def is_valid(unique_id: str) -> bool:
        core = unique_id[len(prefix) :]
        match = pattern.match(core)
        if not match:
            return True  # Not a assignee-chore entity, keep it
        return (match.group(1), match.group(2)) in valid_combinations

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.SENSOR, const.Platform.BUTTON],
        is_valid=is_valid,
        entity_type="assignee-chore entity",
    )


async def remove_orphaned_progress_entities(
    hass: HomeAssistant,
    entry_id: str,
    domain_data: dict[str, Any],
    *,
    entity_type: str,
    progress_suffix: str,
    assigned_assignees_key: str,
) -> int:
    """Remove progress entities for assignees no longer assigned (generic).

    Used for badges, achievements, and challenges.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        domain_data: Dict of approver_entity_id → entity_info (e.g., badges_data).
        entity_type: Display name for logging (e.g., "badge", "achievement").
        progress_suffix: Suffix for progress sensors.
        assigned_assignees_key: Key in entity_info for assigned assignees list.

    Returns:
        Count of removed entities.
    """
    prefix = f"{entry_id}_"

    def is_valid(unique_id: str) -> bool:
        core_id = unique_id[len(prefix) : -len(progress_suffix)]
        parts = core_id.split("_", 1)
        if len(parts) != 2:
            return True  # Can't parse, keep it

        assignee_id, approver_entity_id = parts
        approver_info = domain_data.get(approver_entity_id)
        return bool(
            approver_info
            and assignee_id in approver_info.get(assigned_assignees_key, [])
        )

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.SENSOR],
        suffix=progress_suffix,
        is_valid=is_valid,
        entity_type=f"{entity_type} progress sensor",
    )


async def remove_orphaned_manual_adjustment_buttons(
    hass: HomeAssistant,
    entry_id: str,
    current_deltas: set[float],
) -> int:
    """Remove manual adjustment buttons with obsolete delta values.

    Args:
        hass: HomeAssistant instance.
        entry_id: Config entry ID.
        current_deltas: Set of currently valid delta values.

    Returns:
        Count of removed entities.
    """
    button_suffix = const.BUTTON_KC_UID_SUFFIX_APPROVER_POINTS_ADJUST

    def is_valid(unique_id: str) -> bool:
        # New format: {entry_id}_{assignee_id}_{slugified_delta}_approver_points_adjust_button
        if button_suffix not in unique_id:
            return False
        try:
            # Extract the part before the suffix
            prefix_part = unique_id.split(button_suffix, maxsplit=1)[0]
            # Get last segment which is the slugified delta
            delta_slug = prefix_part.split("_")[-1]
            # Convert slugified delta back to float (replace 'neg' prefix and 'p' decimal)
            delta_str = delta_slug.replace("neg", "-").replace("p", ".")
            delta = float(delta_str)
            return delta in current_deltas
        except (ValueError, IndexError):
            const.LOGGER.warning(
                "Could not parse delta from adjustment button uid: %s", unique_id
            )
            return True  # Can't parse, keep it

    return await remove_entities_by_validator(
        hass,
        entry_id,
        platforms=[const.Platform.BUTTON],
        midfix=button_suffix,
        is_valid=is_valid,
        entity_type="manual adjustment button",
    )


# ==============================================================================
# Profile gating helpers
# Capability-aware workflow/gamification gating with legacy compatibility.
# ==============================================================================


def is_shadow_assignee(coordinator: ChoreOpsDataCoordinator, assignee_id: str) -> bool:
    """Return False; shadow-profile runtime behavior is migration-only."""
    return False


def is_linked_profile(coordinator: ChoreOpsDataCoordinator, assignee_id: str) -> bool:
    """Return False; linked-profile runtime behavior is migration-only."""
    return False


def is_user_approval_profile(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> bool:
    """Return whether this user currently maps to an approval-profile record.

    Phase 3 bridge: this currently maps to legacy shadow-profile semantics
    and is intentionally behavior-compatible with existing entity creation
    logic while naming migrates to capability-oriented terminology.
    """
    return is_user_feature_gated_profile(coordinator, assignee_id)


def is_user_feature_gated_profile(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> bool:
    """Return whether this user follows feature-gated entity creation rules.

    Phase 3 bridge: this currently maps to legacy shadow-profile semantics
    and is intentionally behavior-compatible while runtime naming migrates
    to capability-oriented terminology.
    """
    return is_linked_profile(coordinator, assignee_id)


def is_user_assignment_participant(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> bool:
    """Return whether a user is allowed to participate in assignment workflows.

    Schema45+ contract uses capability flags (`can_be_assigned`) as the
    canonical participation signal. During migration, legacy assignee records that
    still carry shadow markers keep backward-compatible behavior.

    Args:
        coordinator: The ChoreOps data coordinator.
        assignee_id: Internal user/assignee ID.

    Returns:
        True when assignment participation is enabled.
    """
    assignee_info = cast(
        "dict[str, Any]", coordinator.assignees_data.get(assignee_id, {})
    )

    # Canonical schema45+ capability
    if const.DATA_USER_CAN_BE_ASSIGNED in assignee_info:
        return bool(assignee_info.get(const.DATA_USER_CAN_BE_ASSIGNED, True))

    # Legacy fallback during migration window
    if const.DATA_ASSIGNEE_IS_SHADOW in assignee_info:
        return not bool(assignee_info.get(const.DATA_ASSIGNEE_IS_SHADOW, False))

    return True


def get_approver_for_linked_profile(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> dict[str, Any] | None:
    """Return None; linked-profile runtime lookup is migration-only."""
    return None


def get_approver_for_shadow_assignee(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> dict[str, Any] | None:
    """Backward-compatible alias for linked-profile approver lookup."""
    return get_approver_for_linked_profile(coordinator, assignee_id)


def should_create_workflow_buttons(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> bool:
    """Determine if claim/disapprove buttons should be created for a assignee.

    Workflow buttons (Claim, Disapprove) are created for:
    - Assignment participants using default profile behavior
    - Feature-gated profiles with enable_chore_workflow=True

    They are NOT created for:
    - Feature-gated profiles with enable_chore_workflow=False

    Args:
        coordinator: The ChoreOps data coordinator.
        assignee_id: The internal ID (UUID) of the user/assignee record.

    Returns:
        True if workflow buttons should be created, False otherwise.
    """
    if not is_user_assignment_participant(coordinator, assignee_id):
        return False

    if not is_user_feature_gated_profile(coordinator, assignee_id):
        return True  # Default assignment participants always get workflow buttons

    approver_data = get_approver_for_linked_profile(coordinator, assignee_id)
    if approver_data:
        return approver_data.get(const.DATA_APPROVER_ENABLE_CHORE_WORKFLOW, False)
    return False


def should_create_gamification_entities(
    coordinator: ChoreOpsDataCoordinator, assignee_id: str
) -> bool:
    """Determine if gamification entities should be created for a assignee.

    Gamification entities (points sensors, badge progress, reward/bonus/penalty
    buttons, points adjust buttons) are created for:
    - Assignment participants using default profile behavior
    - Feature-gated profiles with enable_gamification=True

    They are NOT created for:
    - Feature-gated profiles with enable_gamification=False

    Args:
        coordinator: The ChoreOps data coordinator.
        assignee_id: The internal ID (UUID) of the user/assignee record.

    Returns:
        True if gamification entities should be created, False otherwise.
    """
    if not is_user_assignment_participant(coordinator, assignee_id):
        return False

    if not is_user_feature_gated_profile(coordinator, assignee_id):
        return True  # Default assignment participants always get gamification

    approver_data = get_approver_for_linked_profile(coordinator, assignee_id)
    if approver_data:
        return approver_data.get(const.DATA_APPROVER_ENABLE_GAMIFICATION, False)
    return False


def should_create_entity(
    unique_id_suffix: str,
    *,
    is_feature_gated_profile: bool = False,
    is_approval_profile: bool = False,
    is_assignment_participant: bool = True,
    is_shadow_assignee: bool = False,
    workflow_enabled: bool = True,
    gamification_enabled: bool = True,
    extra_enabled: bool = False,
) -> bool:
    """Determine if an entity should be created based on its suffix and context.

    Single source of truth for entity creation decisions. Uses ENTITY_REGISTRY.

    === FLAG LAYERING LOGIC ===
    | Requirement   | Default profile       | Feature-gated profile                |
    |---------------|-----------------------|--------------------------------------|
    | ALWAYS        | Created               | Created                              |
    | WORKFLOW      | Created               | Only if workflow_enabled=True        |
    | GAMIFICATION  | Created               | Only if gamification_enabled=True    |
    | EXTRA         | If extra_enabled      | If extra_enabled AND gamification    |

    Args:
        unique_id_suffix: The entity's unique_id suffix (e.g., "_chore_status")
        is_feature_gated_profile: Preferred profile-gating flag for platform code.
        is_approval_profile: Capability-oriented profile flag used by platform code.
        is_assignment_participant: Whether this user participates in assignment scope.
        is_shadow_assignee: Legacy compatibility flag (deprecated; maps to approval profile)
        workflow_enabled: Whether workflow is enabled for gated profiles.
        gamification_enabled: Whether gamification is enabled for gated profiles.
        extra_enabled: Whether show_legacy_entities (extra entities) flag is enabled

    Returns:
        True if entity should be created, False otherwise.
    """
    # Find the matching registry entry
    requirement: const.EntityRequirement | None = None
    for suffix, req in const.ENTITY_REGISTRY.items():
        if unique_id_suffix.endswith(suffix):
            requirement = req
            break

    feature_gated_profile = (
        is_feature_gated_profile or is_approval_profile or is_shadow_assignee
    )

    # Unknown suffix - default to gamification for gated profiles
    if requirement is None:
        if not is_assignment_participant:
            return False
        return not feature_gated_profile or gamification_enabled

    # Check requirement against context
    match requirement:
        case const.EntityRequirement.ALWAYS:
            return True
        case const.EntityRequirement.WORKFLOW:
            return not feature_gated_profile or workflow_enabled
        case const.EntityRequirement.GAMIFICATION:
            return not feature_gated_profile or gamification_enabled
        case const.EntityRequirement.EXTRA:
            # EXTRA requires BOTH extra flag AND gamification
            # Default profiles: always have gamification, so just check flag
            # Feature-gated profiles: need flag AND gamification_enabled
            if not extra_enabled:
                return False
            return not feature_gated_profile or gamification_enabled

    return False
