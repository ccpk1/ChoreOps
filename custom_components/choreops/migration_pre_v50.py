"""Migration logic for pre-v50 schema data.

This module handles one-time migrations from pre-v50 (legacy) data structures
to the v50+ storage-only architecture. These migrations are only executed
when upgrading from legacy configurations to the modern data model.

DEPRECATION NOTICE: This module can be removed in the future when the vast majority
of users have upgraded past v50. The migration logic is frozen and will not be
modified further. Modern installations (KC-v0.5.0+) skip this module entirely via
lazy import to avoid any runtime cost.
"""

from collections import Counter, defaultdict
import copy
from datetime import datetime
import random
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from . import const, data_builders as db
from .coordinator import ChoreOpsDataCoordinator
from .helpers import backup_helpers as bh, entity_helpers as eh
from .helpers.entity_helpers import get_item_id_by_name
from .utils.dt_utils import (
    dt_add_interval,
    dt_next_schedule,
    dt_now_local,
    dt_to_utc,
    dt_today_iso,
)
from .utils.math_utils import parse_points_adjust_values

if TYPE_CHECKING:
    from .store import ChoreOpsStore


LEGACY_STORAGE_KEY = "kidschores_data"
LEGACY_STORAGE_PREFIX = "kidschores_"
LEGACY_STORAGE_KEY_TRANSITIONAL = "choreops_data"
LEGACY_STORAGE_PREFIX_TRANSITIONAL = "choreops_"
LEGACY_MIGRATION_PERFORMED_KEY = "migration_performed"
LEGACY_MIGRATION_KEY_VERSION_KEY = "migration_key_version"
LEGACY_MIGRATION_ORPHAN_PREFIX = "legacy_orphan"
LEGACY_BUTTON_UID_MIDFIX_ADJUST_POINTS = "_points_adjust_"
LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY = "notify_on_reminder"
LEGACY_CHORE_NOTIFY_ON_REMINDER_DEFAULT = True
LEGACY_APPROVER_LINKED_PROFILE_KEY = "linked_shadow_assignee_id"


def has_legacy_migration_performed_marker(data: dict[str, Any]) -> bool:
    """Return True when pre-v50 legacy migration marker is present."""
    return LEGACY_MIGRATION_PERFORMED_KEY in data


def _remap_legacy_key_in_record(
    record: dict[str, Any],
    legacy_key: str,
    canonical_key: str,
) -> int:
    """Remap one legacy key in a record to canonical key.

    Returns:
        1 when a remap occurred, otherwise 0.
    """
    if legacy_key not in record:
        return 0

    legacy_value = record.pop(legacy_key)
    if canonical_key not in record:
        record[canonical_key] = legacy_value
    return 1


def _normalize_legacy_kid_keys(data: dict[str, Any]) -> int:
    """Normalize legacy `*kid*` keys to canonical `*assignee*` keys.

    This migration-only shim protects schema45+ bootstraps that bypass the
    full pre-v50 migration pipeline and still contain legacy key names.

    Returns:
        Total number of remapped keys.
    """
    remap_count = 0

    chores = data.get(const.DATA_CHORES, {})
    if isinstance(chores, dict):
        for chore_raw in chores.values():
            if not isinstance(chore_raw, dict):
                continue
            chore = cast("dict[str, Any]", chore_raw)
            remap_count += _remap_legacy_key_in_record(
                chore,
                const.CONF_ASSIGNED_ASSIGNEES_LEGACY,
                const.DATA_CHORE_ASSIGNED_USER_IDS,
            )
            remap_count += _remap_legacy_key_in_record(
                chore,
                "assigned_assignees",
                const.DATA_CHORE_ASSIGNED_USER_IDS,
            )
            remap_count += _remap_legacy_key_in_record(
                chore,
                "per_kid_due_dates",
                const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
            )
            remap_count += _remap_legacy_key_in_record(
                chore,
                "per_kid_applicable_days",
                const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS,
            )
            remap_count += _remap_legacy_key_in_record(
                chore,
                "per_kid_daily_multi_times",
                const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES,
            )
            remap_count += _remap_legacy_key_in_record(
                chore,
                "rotation_current_kid_id",
                const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID,
            )

    achievements = data.get(const.DATA_ACHIEVEMENTS, {})
    if isinstance(achievements, dict):
        for achievement_raw in achievements.values():
            if not isinstance(achievement_raw, dict):
                continue
            achievement = cast("dict[str, Any]", achievement_raw)
            remap_count += _remap_legacy_key_in_record(
                achievement,
                const.CONF_ACHIEVEMENT_ASSIGNED_ASSIGNEES_LEGACY,
                const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
            )
            remap_count += _remap_legacy_key_in_record(
                achievement,
                "assigned_assignees",
                const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
            )

    challenges = data.get(const.DATA_CHALLENGES, {})
    if isinstance(challenges, dict):
        for challenge_raw in challenges.values():
            if not isinstance(challenge_raw, dict):
                continue
            challenge = cast("dict[str, Any]", challenge_raw)
            remap_count += _remap_legacy_key_in_record(
                challenge,
                const.CONF_CHALLENGE_ASSIGNED_ASSIGNEES_LEGACY,
                const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
            )
            remap_count += _remap_legacy_key_in_record(
                challenge,
                "assigned_assignees",
                const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
            )

    badges = data.get(const.DATA_BADGES, {})
    if isinstance(badges, dict):
        for badge_raw in badges.values():
            if not isinstance(badge_raw, dict):
                continue
            badge = cast("dict[str, Any]", badge_raw)
            remap_count += _remap_legacy_key_in_record(
                badge,
                const.DATA_BADGE_ASSIGNED_TO_LEGACY,
                const.DATA_BADGE_ASSIGNED_USER_IDS,
            )
            remap_count += _remap_legacy_key_in_record(
                badge,
                const.CFOF_BADGES_INPUT_ASSIGNED_TO_LEGACY,
                const.DATA_BADGE_ASSIGNED_USER_IDS,
            )

    approvers = data.get(const.DATA_APPROVERS, {})
    if isinstance(approvers, dict):
        for approver_raw in approvers.values():
            if not isinstance(approver_raw, dict):
                continue
            approver = cast("dict[str, Any]", approver_raw)
            remap_count += _remap_legacy_key_in_record(
                approver,
                const.CONF_ASSOCIATED_ASSIGNEES_LEGACY,
                const.DATA_USER_ASSOCIATED_USER_IDS,
            )
            remap_count += _remap_legacy_key_in_record(
                approver,
                "associated_assignees",
                const.DATA_USER_ASSOCIATED_USER_IDS,
            )

    return remap_count


async def async_apply_schema45_user_contract(
    coordinator: ChoreOpsDataCoordinator,
) -> dict[str, int]:
    """Apply schema 45 contract hook before DATA_READY emission.

    Phase 1 contract checkpoint:
    - Executes in SystemManager.ensure_data_integrity() before DATA_READY.
    - Idempotently stamps migration metadata for schema-45 contract readiness.
    - Does not perform structural migration yet (handled in Phase 2).

    Args:
        coordinator: Integration coordinator instance.
    """
    data = coordinator._data
    meta = data.setdefault(const.DATA_META, {})
    applied = meta.setdefault(const.DATA_META_MIGRATIONS_APPLIED, [])
    if not isinstance(applied, list):
        applied = []
        meta[const.DATA_META_MIGRATIONS_APPLIED] = applied

    legacy_assignees_keys = (
        "assignees",
        const.CONF_ASSIGNEES_LEGACY,
    )
    legacy_approvers_key = const.CONF_APPROVERS_LEGACY

    canonical_assignees_raw = data.get(const.DATA_USERS)
    canonical_assignees: dict[str, Any] = (
        canonical_assignees_raw if isinstance(canonical_assignees_raw, dict) else {}
    )

    for legacy_assignees_key in legacy_assignees_keys:
        legacy_assignees = data.get(legacy_assignees_key)
        if isinstance(legacy_assignees, dict):
            for assignee_id, assignee_data in legacy_assignees.items():
                canonical_assignees.setdefault(assignee_id, assignee_data)
        if legacy_assignees_key != const.DATA_USERS:
            data.pop(legacy_assignees_key, None)

    data[const.DATA_USERS] = canonical_assignees

    canonical_approvers = data.get(const.DATA_APPROVERS)
    legacy_approvers = data.get(legacy_approvers_key)
    if not isinstance(canonical_approvers, dict):
        if isinstance(legacy_approvers, dict):
            canonical_approvers = legacy_approvers
    elif isinstance(legacy_approvers, dict):
        for approver_id, approver_data in legacy_approvers.items():
            canonical_approvers.setdefault(approver_id, approver_data)

    if isinstance(canonical_approvers, dict):
        data[const.DATA_APPROVERS] = canonical_approvers

    if legacy_approvers_key != const.DATA_APPROVERS:
        data.pop(legacy_approvers_key, None)

    kid_key_remaps = _normalize_legacy_kid_keys(data)

    users_raw = data.get(const.DATA_USERS)
    users: dict[str, Any] = users_raw if isinstance(users_raw, dict) else {}
    data[const.DATA_USERS] = users

    approvers_raw = data.get(const.DATA_APPROVERS, {})
    approvers: dict[str, Any] = approvers_raw if isinstance(approvers_raw, dict) else {}

    remap_key = "schema45_approver_id_remap"
    remap_raw = meta.get(remap_key, {})
    remap: dict[str, str] = remap_raw if isinstance(remap_raw, dict) else {}
    meta[remap_key] = remap

    users_migrated = 0
    linked_approver_merges = 0
    standalone_approver_creations = 0
    approver_id_collisions = 0
    approver_id_remap_added = 0

    for user_id, user_data_raw in users.items():
        if not isinstance(user_data_raw, dict):
            continue
        user_data = cast("dict[str, Any]", user_data_raw)
        user_data.setdefault(const.DATA_USER_INTERNAL_ID, user_id)
        user_data.setdefault(const.DATA_USER_ID, user_id)
        user_data.setdefault(
            const.DATA_USER_HA_USER_ID,
            user_data.get(const.DATA_USER_HA_USER_ID),
        )
        user_data.setdefault(const.DATA_USER_CAN_APPROVE, False)
        user_data.setdefault(const.DATA_USER_CAN_MANAGE, False)
        user_data.setdefault(const.DATA_USER_CAN_BE_ASSIGNED, True)
        if user_data.get(const.DATA_USER_CAN_BE_ASSIGNED, False):
            user_data.setdefault(const.DATA_USER_ENABLE_CHORE_WORKFLOW, True)
            user_data.setdefault(const.DATA_USER_ENABLE_GAMIFICATION, True)
        users_migrated += 1

    for approver_id, approver_data_raw in approvers.items():
        if not isinstance(approver_data_raw, dict):
            continue

        approver_data = cast("dict[str, Any]", approver_data_raw)
        linked_profile_id = approver_data.get(LEGACY_APPROVER_LINKED_PROFILE_KEY)
        if isinstance(linked_profile_id, str) and linked_profile_id in users:
            target_id = linked_profile_id
            linked_approver_merges += 1
            target_user = cast("dict[str, Any]", users[target_id])
            target_user[const.DATA_USER_CAN_APPROVE] = True
            target_user[const.DATA_USER_CAN_MANAGE] = True
            target_user.setdefault(const.DATA_USER_CAN_BE_ASSIGNED, True)
            target_user.setdefault(
                const.DATA_USER_HA_USER_ID,
                approver_data.get(const.DATA_USER_HA_USER_ID),
            )
            continue

        mapped_approver_id = remap.get(approver_id, approver_id)
        target_id = mapped_approver_id
        if target_id in users and target_id == approver_id:
            approver_id_collisions += 1
            suffix_index = 1
            while True:
                candidate_id = f"{approver_id}_approver_{suffix_index}"
                if candidate_id not in users:
                    target_id = candidate_id
                    remap[approver_id] = target_id
                    approver_id_remap_added += 1
                    break
                suffix_index += 1

        if target_id in users:
            target_user = cast("dict[str, Any]", users[target_id])
        else:
            target_user = {
                const.DATA_USER_INTERNAL_ID: target_id,
                const.DATA_USER_ID: target_id,
                const.DATA_USER_NAME: approver_data.get(const.DATA_USER_NAME, ""),
                const.DATA_USER_HA_USER_ID: approver_data.get(
                    const.DATA_USER_HA_USER_ID
                ),
                const.DATA_USER_CAN_BE_ASSIGNED: False,
            }
            users[target_id] = target_user
            standalone_approver_creations += 1

        target_user[const.DATA_USER_CAN_APPROVE] = True
        target_user[const.DATA_USER_CAN_MANAGE] = True
        target_user.setdefault(const.DATA_USER_CAN_BE_ASSIGNED, False)
        target_user.setdefault(
            const.DATA_USER_HA_USER_ID,
            approver_data.get(const.DATA_USER_HA_USER_ID),
        )

    # Users is the canonical identity container for schema45+.
    data[const.DATA_USERS] = users
    data.pop(const.DATA_APPROVERS, None)

    contract_marker = "schema45_user_contract_hook"
    if contract_marker not in applied:
        applied.append(contract_marker)

    meta[const.DATA_META_SCHEMA_VERSION] = const.SCHEMA_VERSION_BETA5

    summary = {
        "users_migrated": users_migrated,
        "linked_approver_merges": linked_approver_merges,
        "standalone_approver_creations": standalone_approver_creations,
        "approver_id_collisions": approver_id_collisions,
        "approver_id_remap_entries_total": len(remap),
        "approver_id_remap_entries_added": approver_id_remap_added,
        "kid_key_remaps": kid_key_remaps,
    }
    meta["schema45_last_summary"] = summary
    const.LOGGER.debug(
        "Schema45 migration summary: users=%d linked_merges=%d standalone_approvers=%d collisions=%d remap_total=%d remap_added=%d",
        summary["users_migrated"],
        summary["linked_approver_merges"],
        summary["standalone_approver_creations"],
        summary["approver_id_collisions"],
        summary["approver_id_remap_entries_total"],
        summary["approver_id_remap_entries_added"],
    )
    return summary


def _discover_legacy_storage_artifacts_sync(
    storage_root: str,
) -> dict[str, Any]:
    """Discover legacy ChoreOps storage files and backups.

    Args:
        storage_root: Absolute path to Home Assistant `.storage` directory.

    Returns:
        Discovery payload with candidate active files and backup files.
    """
    from pathlib import Path

    storage_dir = Path(storage_root)

    candidate_active_paths = [
        storage_dir / LEGACY_STORAGE_KEY,
        storage_dir / LEGACY_STORAGE_KEY_TRANSITIONAL,
    ]

    active_files = [str(path) for path in candidate_active_paths if path.exists()]

    backup_candidates: list[Path] = []
    for candidate_dir in (storage_dir,):
        if not candidate_dir.exists():
            continue
        backup_candidates.extend(
            path
            for path in candidate_dir.glob(f"{LEGACY_STORAGE_PREFIX}*.json")
            if path.is_file()
        )
        backup_candidates.extend(
            path
            for path in candidate_dir.glob(
                f"{LEGACY_STORAGE_PREFIX_TRANSITIONAL}*.json"
            )
            if path.is_file()
        )

    deduped_candidates: dict[str, Path] = {
        str(path): path for path in backup_candidates
    }

    backup_candidates = list(deduped_candidates.values())
    backup_candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    return {
        "active_files": active_files,
        "backup_files": [str(path) for path in backup_candidates],
    }


def _extract_storage_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    """Extract storage payload from known export/store formats.

    Supported inputs:
    - Diagnostic export format (`home_assistant` + `data`)
    - Store format (`version` + `data`)
    - Raw storage payload format
    """
    if const.DATA_KEY_HOME_ASSISTANT in data and const.DATA_KEY_DATA in data:
        payload = data.get(const.DATA_KEY_DATA)
        return payload if isinstance(payload, dict) else None

    if const.DATA_KEY_VERSION in data and const.DATA_KEY_DATA in data:
        payload = data.get(const.DATA_KEY_DATA)
        return payload if isinstance(payload, dict) else None

    return data


def _looks_like_choreops_storage_data(data: dict[str, Any]) -> bool:
    """Return True if payload appears to be ChoreOps storage data."""
    return any(
        key in data
        for key in (
            const.DATA_META,
            const.DATA_USERS,
            const.DATA_CHORES,
            const.DATA_BADGES,
            const.DATA_REWARDS,
        )
    )


def normalize_bonus_penalty_apply_shapes(data: dict[str, Any]) -> dict[str, int]:
    """Normalize assignee bonus/penalty apply counters to period dict records.

    This is a schema-agnostic safety normalization for imported payloads where
    `bonus_applies` / `penalty_applies` may still contain integer counters.

    Returns summary counts for transformed entries.
    """
    bonuses_data = data.get(const.DATA_BONUSES, {})
    penalties_data = data.get(const.DATA_PENALTIES, {})

    users_raw = data.get(const.DATA_USERS)
    if isinstance(users_raw, dict):
        users = users_raw
    else:
        legacy_users = data.get("kids")
        users = legacy_users if isinstance(legacy_users, dict) else {}

    transformed_bonus = 0
    transformed_penalty = 0

    for user_info_raw in users.values():
        if not isinstance(user_info_raw, dict):
            continue
        user_info = cast("dict[str, Any]", user_info_raw)

        bonus_applies_raw = user_info.get(const.DATA_USER_BONUS_APPLIES)
        bonus_applies: dict[str, Any]
        if isinstance(bonus_applies_raw, dict):
            bonus_applies = bonus_applies_raw
        else:
            bonus_applies = {}
            user_info[const.DATA_USER_BONUS_APPLIES] = bonus_applies

        for bonus_id, entry in list(bonus_applies.items()):
            if isinstance(entry, dict):
                periods = entry.get(const.DATA_USER_BONUS_PERIODS)
                if not isinstance(periods, dict):
                    periods = {}
                    entry[const.DATA_USER_BONUS_PERIODS] = periods
                for period_type in (
                    const.PERIOD_DAILY,
                    const.PERIOD_WEEKLY,
                    const.PERIOD_MONTHLY,
                    const.PERIOD_YEARLY,
                    const.PERIOD_ALL_TIME,
                ):
                    periods.setdefault(period_type, {})
                continue

            apply_count = int(entry) if isinstance(entry, (int, float)) else 0
            bonus_points = 0.0
            bonus_info = bonuses_data.get(bonus_id)
            if isinstance(bonus_info, dict):
                bonus_points = float(bonus_info.get(const.DATA_BONUS_POINTS, 0.0))

            bonus_applies[bonus_id] = {
                const.DATA_USER_BONUS_PERIODS: {
                    const.PERIOD_DAILY: {},
                    const.PERIOD_WEEKLY: {},
                    const.PERIOD_MONTHLY: {},
                    const.PERIOD_YEARLY: {},
                    const.PERIOD_ALL_TIME: {
                        const.PERIOD_ALL_TIME: {
                            const.DATA_USER_BONUS_PERIOD_APPLIES: apply_count,
                            const.DATA_USER_BONUS_PERIOD_POINTS: round(
                                bonus_points * apply_count,
                                const.DATA_FLOAT_PRECISION,
                            ),
                        }
                    },
                }
            }
            transformed_bonus += 1

        penalty_applies_raw = user_info.get(const.DATA_USER_PENALTY_APPLIES)
        penalty_applies: dict[str, Any]
        if isinstance(penalty_applies_raw, dict):
            penalty_applies = penalty_applies_raw
        else:
            penalty_applies = {}
            user_info[const.DATA_USER_PENALTY_APPLIES] = penalty_applies

        for penalty_id, entry in list(penalty_applies.items()):
            if isinstance(entry, dict):
                periods = entry.get(const.DATA_USER_PENALTY_PERIODS)
                if not isinstance(periods, dict):
                    periods = {}
                    entry[const.DATA_USER_PENALTY_PERIODS] = periods
                for period_type in (
                    const.PERIOD_DAILY,
                    const.PERIOD_WEEKLY,
                    const.PERIOD_MONTHLY,
                    const.PERIOD_YEARLY,
                    const.PERIOD_ALL_TIME,
                ):
                    periods.setdefault(period_type, {})
                continue

            apply_count = int(entry) if isinstance(entry, (int, float)) else 0
            penalty_points = 0.0
            penalty_info = penalties_data.get(penalty_id)
            if isinstance(penalty_info, dict):
                penalty_points = float(penalty_info.get(const.DATA_PENALTY_POINTS, 0.0))

            penalty_applies[penalty_id] = {
                const.DATA_USER_PENALTY_PERIODS: {
                    const.PERIOD_DAILY: {},
                    const.PERIOD_WEEKLY: {},
                    const.PERIOD_MONTHLY: {},
                    const.PERIOD_YEARLY: {},
                    const.PERIOD_ALL_TIME: {
                        const.PERIOD_ALL_TIME: {
                            const.DATA_USER_PENALTY_PERIOD_APPLIES: apply_count,
                            const.DATA_USER_PENALTY_PERIOD_POINTS: round(
                                penalty_points * apply_count,
                                const.DATA_FLOAT_PRECISION,
                            ),
                        }
                    },
                }
            }
            transformed_penalty += 1

    return {
        "bonus_entries_transformed": transformed_bonus,
        "penalty_entries_transformed": transformed_penalty,
    }


async def async_discover_legacy_choreops_artifacts(
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Discover legacy ChoreOps artifacts that can be migrated.

    This checks for legacy active files and legacy backup files under both
    `.storage/` and `.storage/choreops/`.

    Args:
        hass: Home Assistant instance.

    Returns:
        Dict with discovery details and migration eligibility.
    """
    storage_root = hass.config.path(const.STORAGE_PATH_SEGMENT)
    discovered = await hass.async_add_executor_job(
        _discover_legacy_storage_artifacts_sync,
        storage_root,
    )

    active_files = cast("list[str]", discovered["active_files"])
    backup_files = cast("list[str]", discovered["backup_files"])

    return {
        "has_migration_candidate": bool(active_files or backup_files),
        "active_files": active_files,
        "backup_files": backup_files,
    }


async def async_get_data_recovery_capabilities(
    hass: HomeAssistant,
) -> dict[str, bool]:
    """Return data-recovery capabilities for config flow selection rendering.

    Args:
        hass: Home Assistant instance.

    Returns:
        Dictionary containing booleans for available recovery options.
    """
    from pathlib import Path

    from .store import ChoreOpsStore

    store = ChoreOpsStore(hass)
    storage_path = Path(store.get_storage_path())
    legacy_storage_path = Path(
        hass.config.path(const.STORAGE_PATH_SEGMENT, LEGACY_STORAGE_KEY)
    )
    transitional_legacy_storage_path = Path(
        hass.config.path(
            const.STORAGE_PATH_SEGMENT,
            LEGACY_STORAGE_KEY_TRANSITIONAL,
        )
    )

    storage_file_exists = await hass.async_add_executor_job(storage_path.exists)
    legacy_storage_exists = await hass.async_add_executor_job(
        legacy_storage_path.exists
    )
    transitional_legacy_storage_exists = await hass.async_add_executor_job(
        transitional_legacy_storage_path.exists
    )

    legacy_artifacts = await async_discover_legacy_choreops_artifacts(hass)
    has_legacy_candidates = bool(legacy_artifacts.get("has_migration_candidate"))

    return {
        "has_current_active_file": bool(
            storage_file_exists
            or legacy_storage_exists
            or transitional_legacy_storage_exists
        ),
        "has_legacy_candidates": has_legacy_candidates,
    }


async def async_prepare_current_active_storage(
    hass: HomeAssistant,
    destination_storage_key: str = const.STORAGE_KEY,
) -> dict[str, Any]:
    """Validate and normalize current active data file into scoped storage.

    This operation is non-destructive for legacy source files and writes the
    normalized wrapped storage payload to the current scoped destination.

    Args:
        hass: Home Assistant instance.

    Returns:
        Result payload with:
        - `prepared`: bool
        - `error`: str | None (`file_not_found`, `corrupt_file`,
          `invalid_structure`, `unknown`)
    """
    import json
    from pathlib import Path

    from .store import ChoreOpsStore

    try:
        store = ChoreOpsStore(hass, destination_storage_key)
        destination_path = Path(store.get_storage_path())
        legacy_storage_path = Path(
            hass.config.path(const.STORAGE_PATH_SEGMENT, LEGACY_STORAGE_KEY)
        )
        transitional_legacy_storage_path = Path(
            hass.config.path(
                const.STORAGE_PATH_SEGMENT,
                LEGACY_STORAGE_KEY_TRANSITIONAL,
            )
        )

        destination_exists = await hass.async_add_executor_job(destination_path.exists)
        legacy_exists = await hass.async_add_executor_job(legacy_storage_path.exists)
        transitional_legacy_exists = await hass.async_add_executor_job(
            transitional_legacy_storage_path.exists
        )

        if (
            not destination_exists
            and not legacy_exists
            and not transitional_legacy_exists
        ):
            return {
                "prepared": False,
                "error": "file_not_found",
            }

        source_path = destination_path
        if not destination_exists:
            source_path = (
                legacy_storage_path
                if legacy_exists
                else transitional_legacy_storage_path
            )

        source_text = await hass.async_add_executor_job(source_path.read_text, "utf-8")
        try:
            source_data = json.loads(source_text)
        except json.JSONDecodeError:
            return {
                "prepared": False,
                "error": "corrupt_file",
            }

        if not isinstance(source_data, dict):
            return {
                "prepared": False,
                "error": "invalid_structure",
            }

        if not bh.validate_backup_json(source_text):
            return {
                "prepared": False,
                "error": "invalid_structure",
            }

        payload = _extract_storage_payload(source_data)
        if payload is None:
            return {
                "prepared": False,
                "error": "invalid_structure",
            }

        summary = normalize_bonus_penalty_apply_shapes(payload)
        if (
            summary["bonus_entries_transformed"]
            or summary["penalty_entries_transformed"]
        ):
            const.LOGGER.info(
                "Normalized imported apply counters during prepare_current_active: bonus=%d penalty=%d",
                summary["bonus_entries_transformed"],
                summary["penalty_entries_transformed"],
            )

        wrapped_data = {
            const.DATA_KEY_VERSION: 1,
            "minor_version": 1,
            const.DATA_KEY_KEY: destination_storage_key,
            const.DATA_KEY_DATA: payload,
        }

        await hass.async_add_executor_job(
            lambda: destination_path.parent.mkdir(parents=True, exist_ok=True)
        )
        await hass.async_add_executor_job(
            destination_path.write_text,
            json.dumps(wrapped_data, indent=2),
            "utf-8",
        )

        if source_path == legacy_storage_path:
            const.LOGGER.info(
                "Copied legacy active data file into scoped ChoreOps storage"
            )
        else:
            const.LOGGER.info("Using current active storage file")

        return {
            "prepared": True,
            "error": None,
        }

    except Exception as err:
        const.LOGGER.error("Preparing current active storage failed: %s", err)
        return {
            "prepared": False,
            "error": "unknown",
        }


async def async_migrate_from_legacy_choreops_storage(
    hass: HomeAssistant,
    destination_storage_key: str = const.STORAGE_KEY,
) -> dict[str, Any]:
    """Migrate legacy ChoreOps storage into ChoreOps storage.

    Migration is non-destructive: source files are never modified or deleted.
    The function reads the best available legacy source and writes a wrapped
    Home Assistant storage payload to `.storage/choreops/choreops_data`.

    Args:
        hass: Home Assistant instance.

    Returns:
        Result dictionary with:
        - `migrated`: bool
        - `source_path`: str | None
        - `source_kind`: str | None (`active` or `backup`)
        - `settings`: dict[str, Any]
        - `error`: str | None
    """
    import json
    from pathlib import Path

    artifacts = await async_discover_legacy_choreops_artifacts(hass)
    active_files = cast("list[str]", artifacts["active_files"])
    backup_files = cast("list[str]", artifacts["backup_files"])

    source_path: str | None = None
    source_kind: str | None = None
    if active_files:
        source_path = active_files[0]
        source_kind = "active"
    elif backup_files:
        source_path = backup_files[0]
        source_kind = "backup"

    if source_path is None or source_kind is None:
        return {
            "migrated": False,
            "source_path": None,
            "source_kind": None,
            "settings": {},
            "error": "no_legacy_source",
        }

    try:
        source_text = await hass.async_add_executor_job(
            Path(source_path).read_text,
            "utf-8",
        )
        source_data = json.loads(source_text)
    except (OSError, ValueError) as err:
        const.LOGGER.error(
            "Failed reading legacy migration source %s: %s", source_path, err
        )
        return {
            "migrated": False,
            "source_path": source_path,
            "source_kind": source_kind,
            "settings": {},
            "error": "invalid_json",
        }

    if not isinstance(source_data, dict):
        return {
            "migrated": False,
            "source_path": source_path,
            "source_kind": source_kind,
            "settings": {},
            "error": "invalid_structure",
        }

    payload = _extract_storage_payload(source_data)
    if payload is None or not _looks_like_choreops_storage_data(payload):
        return {
            "migrated": False,
            "source_path": source_path,
            "source_kind": source_kind,
            "settings": {},
            "error": "invalid_structure",
        }

    summary = normalize_bonus_penalty_apply_shapes(payload)
    if summary["bonus_entries_transformed"] or summary["penalty_entries_transformed"]:
        const.LOGGER.info(
            "Normalized imported apply counters during migrate_from_legacy: bonus=%d penalty=%d",
            summary["bonus_entries_transformed"],
            summary["penalty_entries_transformed"],
        )

    from .store import ChoreOpsStore

    store = ChoreOpsStore(hass, destination_storage_key)
    destination_path = Path(store.get_storage_path())
    destination_dir = destination_path.parent

    destination_exists = await hass.async_add_executor_job(destination_path.exists)
    if destination_exists:
        try:
            backup_name = await bh.create_timestamped_backup(
                hass,
                store,
                const.BACKUP_TAG_RECOVERY,
                None,
            )
            if backup_name:
                const.LOGGER.info(
                    "Created ChoreOps safety backup before migration: %s",
                    backup_name,
                )
        except Exception as err:
            const.LOGGER.warning(
                "Failed to create safety backup before legacy migration: %s", err
            )

    wrapped_data = {
        const.DATA_KEY_VERSION: 1,
        "minor_version": 1,
        const.DATA_KEY_KEY: destination_storage_key,
        const.DATA_KEY_DATA: payload,
    }

    await hass.async_add_executor_job(
        lambda: destination_dir.mkdir(parents=True, exist_ok=True)
    )
    await hass.async_add_executor_job(
        destination_path.write_text,
        json.dumps(wrapped_data, indent=2),
        "utf-8",
    )

    settings: dict[str, Any] = {}
    raw_settings = source_data.get(const.DATA_CONFIG_ENTRY_SETTINGS)
    if isinstance(raw_settings, dict):
        validated = bh.validate_config_entry_settings(raw_settings)
        settings = {
            key: validated.get(key, default)
            for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
        }

    const.LOGGER.info(
        "Migrated legacy ChoreOps data from %s (%s) into %s",
        source_path,
        source_kind,
        destination_path,
    )
    const.LOGGER.info(
        "Legacy ChoreOps files were not removed. You can remove the old ChoreOps "
        "integration manually after validating ChoreOps"
    )

    return {
        "migrated": True,
        "source_path": source_path,
        "source_kind": source_kind,
        "settings": settings,
        "error": None,
    }


# ================================================================================================
# KC 3.x → 4.x Config-to-Storage Migration (runs BEFORE coordinator init)
# ================================================================================================


async def migrate_config_to_storage(
    hass: HomeAssistant, entry: ConfigEntry, store: "ChoreOpsStore"
) -> None:
    """One-time migration: Move entity data from config_entry.options to storage.

    This migration runs once to transition from the legacy KC 3.x "config as source of truth"
    architecture to the new KC 4.x "storage as source of truth" architecture.

    System settings (points_label, points_icon, update_interval) remain in config.
    All entity definitions (assignees, chores, badges, etc.) move to storage.

    Args:
        hass: Home Assistant instance
        entry: Config entry to migrate
        store: Initialized store instance

    """
    storage_data = store.data

    # Check schema version - support both v41 (top-level) and v42+ (meta section)
    # v41 format: {"schema_version": 41, "assignees": {...}}
    # v42+ format: {"meta": {"schema_version": 42}, "assignees": {...}}
    meta_section = storage_data.get(const.DATA_META, {})
    storage_version = meta_section.get(
        const.DATA_META_SCHEMA_VERSION,
        storage_data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
    )

    # Check if migration is needed
    # Skip if version is at or past the transitional stamp (42+)
    # Version 42 = config→storage done, structural migration pending
    # Version 43+ = fully migrated
    if storage_version >= const.SCHEMA_VERSION_TRANSITIONAL:
        const.LOGGER.info(
            "INFO: Storage schema version %s already >= %s, skipping config→storage migration",
            storage_version,
            const.SCHEMA_VERSION_TRANSITIONAL,
        )
        return

    # Check if config has entity data to migrate
    config_has_entities = any(
        key in entry.options
        for key in [
            const.CONF_ASSIGNEES_LEGACY,
            "assignees",
            const.CONF_CHORES_LEGACY,
            const.CONF_BADGES_LEGACY,
            const.CONF_REWARDS_LEGACY,
            const.CONF_APPROVERS_LEGACY,
            "approvers",
            const.CONF_PENALTIES_LEGACY,
            const.CONF_BONUSES_LEGACY,
            const.CONF_ACHIEVEMENTS_LEGACY,
            const.CONF_CHALLENGES_LEGACY,
        ]
    )

    # Also check if storage already has entity data (handles storage-based v3.x installations)
    storage_has_entities = any(
        len(storage_data.get(key, {})) > 0
        for key in [
            const.DATA_USERS,
            const.DATA_CHORES,
            const.DATA_BADGES,
            const.DATA_REWARDS,
        ]
    )

    # Only treat as clean install if BOTH config and storage are empty
    if not config_has_entities and not storage_has_entities:
        const.LOGGER.info(
            "INFO: No entity data in config or storage, setting storage version to %s (clean install)",
            const.SCHEMA_VERSION_BETA4,
        )
        # Clean install - set version in meta section and save
        from homeassistant.util import dt as dt_util

        storage_data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_LAST_MIGRATION_DATE: dt_util.utcnow().isoformat(),
            const.DATA_META_MIGRATIONS_APPLIED: [],
        }
        store.set_data(storage_data)
        await store.async_save()
        return

    # Storage-only data (Config Flow import path): let coordinator handle all migrations
    if not config_has_entities and storage_has_entities:
        const.LOGGER.info(
            "INFO: Storage has data but config is empty (schema v%s). Coordinator will handle migrations.",
            storage_version,
        )
        return

    # Migration needed: config has entities and storage version < 42
    const.LOGGER.info("INFO: ========================================")
    const.LOGGER.info(
        "INFO: Starting config→storage migration (schema version %s → %s)",
        storage_version,
        const.SCHEMA_VERSION_STORAGE_ONLY,
    )

    # Create backup of storage data before migration
    # Set flag to prevent duplicate backup in schema migrations
    backup_flag_key = f"{const.DOMAIN}_pre_migration_backup_created"
    try:
        backup_name = await bh.create_timestamped_backup(
            hass, store, const.BACKUP_TAG_PRE_MIGRATION
        )
        if backup_name:
            const.LOGGER.info("INFO: Created pre-migration backup: %s", backup_name)
            hass.data[backup_flag_key] = True
        else:
            const.LOGGER.warning("WARNING: No data available for pre-migration backup")
    except Exception as err:
        const.LOGGER.warning("WARNING: Failed to create pre-migration backup: %s", err)

    # Define fields that should NOT be migrated from config (relational/runtime fields)
    # IMPORTANT: These fields in OLD config data may have stale/incorrect data:
    # - Relational fields may contain entity NAMES instead of INTERNAL_IDS
    # - Runtime state fields should never come from config
    # By excluding these fields, we preserve the correct data already in storage
    excluded_fields_by_type = {
        const.DATA_CHORES: {
            "assigned_assignees",  # May contain names instead of internal_ids
            "state",
            "last_completed",
            "last_claimed",
        },
        const.DATA_APPROVERS: {
            "associated_assignees",  # May contain names instead of internal_ids
        },
        const.DATA_BADGES: {
            "assigned_to",  # May contain names instead of internal_ids
        },
        const.DATA_ACHIEVEMENTS: {
            "assigned_assignees",  # May contain names instead of internal_ids
            "selected_chore_id",  # May contain name instead of internal_id
            "progress",  # Runtime data
        },
        const.DATA_CHALLENGES: {
            "assigned_assignees",  # May contain names instead of internal_ids
            "selected_chore_id",  # May contain name instead of internal_id
            "progress",  # Runtime data
        },
    }

    # Merge entity data from config into storage (preserving existing state)
    entity_sections = [
        ((const.CONF_ASSIGNEES_LEGACY, "assignees"), const.DATA_USERS),
        ((const.CONF_APPROVERS_LEGACY, "approvers"), const.DATA_APPROVERS),
        ((const.CONF_CHORES_LEGACY,), const.DATA_CHORES),
        ((const.CONF_BADGES_LEGACY,), const.DATA_BADGES),
        ((const.CONF_REWARDS_LEGACY,), const.DATA_REWARDS),
        ((const.CONF_PENALTIES_LEGACY,), const.DATA_PENALTIES),
        ((const.CONF_BONUSES_LEGACY,), const.DATA_BONUSES),
        ((const.CONF_ACHIEVEMENTS_LEGACY,), const.DATA_ACHIEVEMENTS),
        ((const.CONF_CHALLENGES_LEGACY,), const.DATA_CHALLENGES),
    ]

    for config_keys, data_key in entity_sections:
        config_key_used = config_keys[0]
        config_entities: dict[str, Any] = {}
        for config_key_candidate in config_keys:
            candidate = entry.options.get(config_key_candidate, {})
            if isinstance(candidate, dict) and candidate:
                config_entities = candidate
                config_key_used = config_key_candidate
                break

        if config_entities:
            # Merge config entities into storage (config is source of truth for definitions)
            if data_key not in storage_data:
                storage_data[data_key] = {}

            # Get excluded fields for this entity type
            excluded_fields = excluded_fields_by_type.get(data_key, set())

            # For each entity from config, merge with existing storage data
            # Preserve all existing runtime data, only update definition fields
            for entity_id, config_entity_data in config_entities.items():
                if entity_id in storage_data[data_key]:
                    # Entity exists in storage - update only definition fields, preserve runtime data
                    existing_entity = storage_data[data_key][entity_id]
                    # Only update fields that are not excluded
                    for field, value in config_entity_data.items():
                        if field not in excluded_fields:
                            existing_entity[field] = value
                else:
                    # New entity - add from config
                    storage_data[data_key][entity_id] = config_entity_data

                # For assignees, remove dead overdue_notifications field if present
                if config_key_used in {const.CONF_ASSIGNEES_LEGACY, "assignees"}:
                    storage_data[data_key][entity_id].pop(
                        const.DATA_ASSIGNEE_OVERDUE_NOTIFICATIONS_LEGACY, None
                    )

            const.LOGGER.debug(
                "DEBUG: Migrated %s %s from config to storage",
                len(config_entities),
                config_key_used,
            )

    # Set TRANSITIONAL schema version in meta section
    # This signals "data is in storage, but structural migration has not run yet."
    # _finalize_migration_meta() upgrades to SCHEMA_VERSION_STORAGE_ONLY (43) after
    # all pre-v50 phases succeed. This prevents the premature-stamp bug (#243).
    from homeassistant.util import dt as dt_util

    storage_data[const.DATA_META] = {
        const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_TRANSITIONAL,
        const.DATA_META_LAST_MIGRATION_DATE: dt_util.utcnow().isoformat(),
        const.DATA_META_MIGRATIONS_APPLIED: ["config_to_storage"],
    }
    # Remove old top-level schema_version if present
    storage_data.pop(const.DATA_SCHEMA_VERSION, None)

    # Save merged data to storage
    store.set_data(storage_data)
    await store.async_save()

    # Build new config with ONLY system settings
    new_options = {
        const.CONF_POINTS_LABEL: entry.options.get(
            const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
        ),
        const.CONF_POINTS_ICON: entry.options.get(
            const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON
        ),
        const.CONF_UPDATE_INTERVAL: entry.options.get(
            const.CONF_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
        ),
        const.CONF_POINTS_ADJUST_VALUES: entry.options.get(
            const.CONF_POINTS_ADJUST_VALUES, const.DEFAULT_POINTS_ADJUST_VALUES
        ),
        const.CONF_CALENDAR_SHOW_PERIOD: entry.options.get(
            const.CONF_CALENDAR_SHOW_PERIOD, const.DEFAULT_CALENDAR_SHOW_PERIOD
        ),
        const.CONF_RETENTION_DAILY: entry.options.get(
            const.CONF_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
        ),
        const.CONF_RETENTION_WEEKLY: entry.options.get(
            const.CONF_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
        ),
        const.CONF_RETENTION_MONTHLY: entry.options.get(
            const.CONF_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
        ),
        const.CONF_RETENTION_YEARLY: entry.options.get(
            const.CONF_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
        ),
        const.CONF_SCHEMA_VERSION_LEGACY: const.SCHEMA_VERSION_STORAGE_ONLY,
    }

    # Update config entry with cleaned options
    hass.config_entries.async_update_entry(entry, options=new_options)

    const.LOGGER.info(
        "INFO: ✓ Config→storage migration complete! Entity data now in storage, system settings in config."
    )
    const.LOGGER.info("INFO: ========================================")


# ================================================================================================
# Coordinator Data Migrations (run AFTER coordinator init, when storage schema < 50)
# ================================================================================================


class PreV50Migrator:
    """Handles all pre-v50 schema migrations.

    This class encapsulates the legacy migration logic that transforms
    pre-v50 data structures to the modern storage-only v50+ format.
    All migrations are one-time operations executed on first coordinator startup
    for users upgrading from older versions.

    Attributes:
        coordinator: Reference to the ChoreOpsDataCoordinator instance.
    """

    # This migration class intentionally accesses coordinator private methods and data

    def __init__(self, coordinator: "ChoreOpsDataCoordinator") -> None:
        """Initialize the migrator with coordinator reference.

        Args:
            coordinator: The ChoreOpsDataCoordinator instance to migrate data for.
        """
        self.coordinator = coordinator

    def _normalize_legacy_assignee_buckets(self) -> None:
        """Normalize legacy assignee buckets into canonical users bucket.

        Pre-v50 phase methods read and clean assignee records from
        ``DATA_USERS``. Legacy imports can still provide assignees in
        ``assignees`` or ``kids`` buckets. Normalize once at pipeline start
        so all subsequent migration phases operate on the canonical container.
        """
        data = self.coordinator._data

        users_raw = data.get(const.DATA_USERS)
        users: dict[str, Any] = users_raw if isinstance(users_raw, dict) else {}

        legacy_assignee_keys = (
            "assignees",
            const.CONF_ASSIGNEES_LEGACY,
        )

        for legacy_key in legacy_assignee_keys:
            legacy_assignees = data.get(legacy_key)
            if isinstance(legacy_assignees, dict):
                for assignee_id, assignee_data in legacy_assignees.items():
                    users.setdefault(assignee_id, assignee_data)
            data.pop(legacy_key, None)

        data[const.DATA_USERS] = users

    async def run_all_migrations(self) -> None:
        """Execute all pre-v50 migrations in the correct order.

        Migrations are run sequentially with proper error handling and logging.
        Each migration is idempotent - it can be run multiple times without
        causing data corruption or duplication.
        """
        const.LOGGER.info(
            "Starting pre-v50 schema migrations for upgrade to modern format"
        )

        # Create pre-migration backup before any schema transformations
        # Skip if config→storage migration already created one this session
        backup_flag_key = f"{const.DOMAIN}_pre_migration_backup_created"
        if not self.coordinator.hass.data.get(backup_flag_key, False):
            try:
                backup_name = await bh.create_timestamped_backup(
                    self.coordinator.hass,
                    self.coordinator.store,
                    const.BACKUP_TAG_PRE_MIGRATION,
                )
                if backup_name:
                    const.LOGGER.info("Created pre-migration backup: %s", backup_name)
                    self.coordinator.hass.data[backup_flag_key] = True
            except Exception as ex:
                const.LOGGER.warning(
                    "Failed to create pre-migration backup (migration will continue): %s",
                    ex,
                )
        else:
            const.LOGGER.debug(
                "Skipping schema migration backup (config→storage backup already created)"
            )

        # ===================================================================
        # ATOMIC MIGRATION: deepcopy snapshot for rollback on failure (#243)
        # If ANY phase fails, restore data to pre-migration state so the
        # fallback cascade (nuclear rebuild → auto-restore) works on clean data.
        # ===================================================================
        snapshot = copy.deepcopy(self.coordinator._data)

        try:
            # Normalize legacy assignee buckets early so all migration phases,
            # especially legacy-field cleanup, run against canonical users.
            self._normalize_legacy_assignee_buckets()

            # Phase 1: Schema migrations (data structure transformations)
            self._migrate_datetime_wrapper()
            self._migrate_stored_datetimes()
            self._migrate_chore_data()
            self._migrate_assignee_data()
            self._migrate_legacy_assignee_chore_data_and_streaks()
            self._migrate_badges()
            self._migrate_assignee_legacy_badges_to_cumulative_progress()
            self._migrate_assignee_legacy_badges_to_badges_earned()
            self._migrate_legacy_point_stats()

            # Phase 2: Config sync (KC 3.x entity data from config → storage)
            # Phase 2: Independent chores migration (populate per-assignee due dates)
            self._migrate_independent_chores()

            # Phase 2a: Per-assignee applicable days migration (PKAD-2026-001)
            self._migrate_per_assignee_applicable_days()

            # Phase 2b: Approval reset type migration (allow_multiple_claims_per_day → approval_reset_type)
            self._migrate_approval_reset_type()

            # Phase 2c: Timestamp-based chore tracking migration
            # - Initialize approval_period_start for chores
            # - Delete deprecated claimed_chores/approved_chores lists from assignees
            self._migrate_to_timestamp_tracking()

            # Phase 2d: Reward data migration to period-based structure
            # - Migrate pending_rewards[] → reward_data[id].pending_count
            # - Migrate reward_claims{} → reward_data[id].total_claims
            # - Migrate reward_approvals{} → reward_data[id].total_approved
            self._migrate_reward_data_to_periods()

            # Phase 3: Config sync (KC 3.x entity data from config → storage)
            const.LOGGER.info("Migrating KC 3.x config data to storage")
            self._initialize_data_from_config()

            # Phase 4: Add new optional chore fields (defaults for existing chores)
            self._add_chore_optional_fields()

            # Phase 4b: Stats consolidation - Migrate max_points_ever → periods.all_time,
            # MUST run BEFORE _remove_legacy_fields which deletes max_points_ever
            self._consolidate_point_stats()

            # Phase 5: Clean up all legacy fields that have been migrated
            # This removes fields that were READ during migration but are no longer needed
            self._remove_legacy_fields()

            # Phase 6: Round all float values to standard precision
            # Fixes Python float arithmetic drift (e.g., 27.499999999999996 → 27.5)
            self._round_float_precision()

            # Phase 7: v50 cleanup - Remove legacy due_date fields from assignee-level chore_data
            # for independent chores (single source of truth is now chore_info[per_assignee_due_dates])
            storage_version = self.coordinator._data.get(const.DATA_META, {}).get(
                const.DATA_META_SCHEMA_VERSION, 42
            )
            if storage_version < 50:
                self._cleanup_assignee_chore_data_due_dates_v50()

            # Phase 7a: v50 notification simplification - Migrate 3-field notification config
            # to single service selector (service presence = enabled, empty = disabled)
            self._simplify_notification_config_v50()

            # Phase 8: Clean up orphaned/deprecated dynamic entities
            # This is called unconditionally because _initialize_data_from_config() only
            # calls this for KC 3.x config migrations, leaving storage-only users with
            # orphaned entities from previous versions (e.g., integer-delta buttons).
            self.remove_deprecated_button_entities()
            self.remove_deprecated_sensor_entities()

            # Phase 9: Strip temporal stats from storage (Phase 7.5 - The Great Stripping)
            # Derivative Data is Ephemeral - clock-based stats MUST NOT be saved to JSON.
            # These fields are now derived on-demand from period buckets (point_data.periods).
            # Keep: earned_all_time, highest_balance_all_time, longest_streak_all_time (High-Water Marks)
            self._strip_temporal_stats()

            # Phase 10: Backfill 'completed' metric from 'approved' (v0.5.0-beta4)
            # New approver-lag-proof statistics track work completion by claim date, not approval date.
            # Historical approvals have no 'completed' tracking - backfill with approved counts.
            self._migrate_completed_metric()

            # Phase 11 (4B): Move badge award_count from root to periods.all_time.all_time (v43)
            # "Lean Item" pattern - remove root-level duplication, use periods as canonical source
            # Matches Phase 2 (chore total_points) and Phase 3 (reward total_*)
            self._migrate_badge_award_count_to_periods()

            # Phase 11: Flatten point_data → point_periods (v42 → v43, v0.5.0-beta3)
            # Remove nested structure and transform points_total → points_earned/spent
            self._migrate_point_periods_v43()

            # Phase 12: Chore periods migration (v43) - "Lean Chore Architecture"
            # - Create assignee-level chore_periods bucket for aggregated history
            # - Remove total_points from individual chore items (use periods.all_time.points)
            # - Delete chore_stats dict entirely (now fully ephemeral)
            self._migrate_chore_periods_v43()

            # Phase 12b: Reward periods migration (v43) - "Lean Reward Architecture"
            # - Create assignee-level reward_periods bucket for aggregated history
            # - Remove total_* fields from reward_data items (use periods.all_time.*)
            # - Remove notification_ids from reward_data items (NotificationManager owns lifecycle)
            # - Delete reward_stats dict entirely (now fully ephemeral)
            self._migrate_reward_periods_v43()

            # Phase 12c: Bonus/Penalty periods migration (v43) - "Lean Item Period Tracking"
            # - Add periods structure to global bonuses_data[uuid] and penalties_data[uuid]
            # - No assignee-level aggregate buckets needed (unlike chores/rewards)
            # - Ledger enhancement: item_name field already added in Phase 4C.4
            self._migrate_bonus_penalty_periods_v43()

            # Phase 13: Finalize migration metadata (MUST be last)
            # Sets v50+ meta section and cleans up legacy keys
            self._finalize_migration_meta()

        except Exception:
            # ROLLBACK: Restore data to pre-migration snapshot (#243 defense)
            # This ensures the fallback cascade works on clean, untransformed data.
            const.LOGGER.warning(
                "Pre-v50 migration failed — rolling back to pre-migration snapshot. "
                "Fallback cascade will attempt recovery"
            )
            self.coordinator._data = snapshot
            raise

        const.LOGGER.info("All pre-v50 migrations completed successfully")

    # =========================================================================
    # Pre-v50 Migration Cascade (#243 Hardening)
    # =========================================================================
    # These methods implement the full migration cascade including fallback
    # layers for recovering from failed migrations. Called by SystemManager's
    # ensure_data_integrity() via run_full_pre_v50_cascade().
    #
    # DEPRECATION: Remove with the rest of this module when v50 support dropped.
    # =========================================================================

    async def run_full_pre_v50_cascade(self, current_version: int) -> None:
        """Run the complete pre-v50 migration cascade with fallback layers.

        This is the single entry point called by SystemManager.ensure_data_integrity().
        Handles:
        - Premature schema stamp detection (#243 v0.5.0b3 bug)
        - Schema 42->43 structural migrations (with deepcopy rollback)
        - Nuclear rebuild fallback (build_*() with existing= data)
        - Auto-restore from pre-migration backup
        - Schema 43->44 (beta4 tweaks)

        Args:
            current_version: Schema version detected by Coordinator
        """
        # Step 0: Detect premature stamp from v0.5.0b3 bug
        current_version = self._detect_premature_stamp(current_version)

        # Step 1: Execute pre-v50 migrations if needed (with fallback cascade)
        if current_version < const.SCHEMA_VERSION_STORAGE_ONLY:
            await self._run_migration_with_fallback(current_version)

        # Step 2: Schema 44 gate (beta 4 tweaks) — only after schema 43 confirmed
        meta = self.coordinator._data.get(const.DATA_META, {})
        post_migration_version = meta.get(
            const.DATA_META_SCHEMA_VERSION,
            self.coordinator._data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
        )
        if post_migration_version == const.SCHEMA_VERSION_STORAGE_ONLY:
            self._migrate_to_schema_44()

    def _detect_premature_stamp(self, current_version: int) -> int:
        """Detect and fix premature schema stamp from v0.5.0b3 bug (#243).

        Old code stamped schema 43 BEFORE structural migrations ran.
        If schema says 43/44 but legacy key "migration_performed" is still
        present, the data was never actually transformed. Downgrade to 42
        (TRANSITIONAL) so the structural migration pipeline runs properly.
        Safe because all migration phases are idempotent.

        Args:
            current_version: Schema version from storage meta.

        Returns:
            Corrected version (42 if premature stamp detected, else unchanged).
        """
        if (
            current_version >= const.SCHEMA_VERSION_STORAGE_ONLY
            and has_legacy_migration_performed_marker(self.coordinator._data)
        ):
            const.LOGGER.warning(
                "PreV50Migrator: Detected premature schema stamp (v%s with "
                "legacy keys still present). Downgrading to %s to re-run "
                "structural migrations (#243 recovery)",
                current_version,
                const.SCHEMA_VERSION_TRANSITIONAL,
            )
            current_version = const.SCHEMA_VERSION_TRANSITIONAL
            meta = self.coordinator._data.get(const.DATA_META, {})
            meta[const.DATA_META_SCHEMA_VERSION] = const.SCHEMA_VERSION_TRANSITIONAL
            self.coordinator._data[const.DATA_META] = meta
        return current_version

    async def _run_migration_with_fallback(self, current_version: int) -> None:
        """Run pre-v50 migrations with 3-layer fallback cascade (#243).

        Layer 1: Atomic migration (deepcopy rollback on failure)
        Layer 2: Nuclear rebuild via build_*() with existing= data
        Layer 3: Auto-restore from pre-migration backup

        Args:
            current_version: Schema version before migration
        """
        # Layer 1: Try normal migration (has internal deepcopy rollback)
        try:
            await self.run_all_migrations()
            const.LOGGER.info(
                "PreV50Migrator: Migrated from schema %s to %s",
                current_version,
                const.SCHEMA_VERSION_STORAGE_ONLY,
            )
            return
        except Exception:
            const.LOGGER.warning(
                "PreV50Migrator: Pre-v50 migration failed (schema %s). "
                "Attempting nuclear rebuild",
                current_version,
            )

        # Layer 2: Nuclear rebuild — pass all items through build_*()
        rebuild_ok = self._attempt_nuclear_rebuild()
        if rebuild_ok:
            wipe_count = self._wipe_all_kc_entities()
            const.LOGGER.info(
                "PreV50Migrator: Nuclear rebuild succeeded. "
                "Wiped %s entities (platforms will recreate them)",
                wipe_count,
            )
            return

        const.LOGGER.warning(
            "PreV50Migrator: Nuclear rebuild also failed. "
            "Attempting auto-restore from pre-migration backup"
        )

        # Layer 3: Auto-restore from pre-migration backup
        restored = await self._attempt_auto_restore()
        if restored:
            const.LOGGER.info(
                "PreV50Migrator: Auto-restored from pre-migration backup. "
                "Migration will retry on next restart"
            )
            return

        # All layers failed — need user intervention
        raise ConfigEntryNotReady(
            "Migration failed and automatic recovery was not possible. "
            "Please go to Configure \u2192 General Options \u2192 Restore from backup."
        )

    def _attempt_nuclear_rebuild(self) -> bool:
        """Rebuild all items through build_*() preserving user definitions (#243).

        This is the automated \"Option 2\" — remove + re-add with existing data.
        Each item is passed through its canonical builder with existing= parameter,
        which preserves config fields and regenerates runtime structure.

        Returns:
            True if rebuild succeeded, False on failure.
        """
        from homeassistant.util import dt as dt_util

        const.LOGGER.info("PreV50Migrator: Attempting nuclear rebuild via build_*()")

        # Entity type -> (bucket key, builder callable, extra kwargs)
        bucket_builders: list[tuple[str, str, Any]] = [
            (const.DATA_USERS, "assignee", None),
            (const.DATA_CHORES, "chore", None),
            (const.DATA_REWARDS, "reward", None),
            (const.DATA_BADGES, "badge", None),
            (const.DATA_PENALTIES, "penalty", None),
            (const.DATA_BONUSES, "bonus", None),
            (const.DATA_ACHIEVEMENTS, "achievement", None),
            (const.DATA_CHALLENGES, "challenge", None),
            (const.DATA_APPROVERS, "approver", None),
        ]

        try:
            for bucket_key, builder_name, _ in bucket_builders:
                items = self.coordinator._data.get(bucket_key, {})
                rebuilt_items: dict[str, Any] = {}

                for item_id, item_data in items.items():
                    try:
                        rebuilt = self._rebuild_single_item(db, builder_name, item_data)
                        rebuilt_items[item_id] = rebuilt
                    except Exception:
                        const.LOGGER.warning(
                            "PreV50Migrator: Failed to rebuild %s item %s, skipping",
                            builder_name,
                            item_id,
                        )

                self.coordinator._data[bucket_key] = rebuilt_items

            # Stamp schema 43 — rebuilt data IS valid v50 structure
            self.coordinator._data[const.DATA_META] = {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
                const.DATA_META_LAST_MIGRATION_DATE: datetime.now(
                    dt_util.UTC
                ).isoformat(),
                const.DATA_META_MIGRATIONS_APPLIED: [
                    "nuclear_rebuild_after_migration_failure"
                ],
                const.DATA_META_PENDING_EVALUATIONS: [],
            }

            const.LOGGER.info("PreV50Migrator: Nuclear rebuild completed successfully")
            return True

        except Exception:
            const.LOGGER.warning(
                "PreV50Migrator: Nuclear rebuild failed \u2014 data may be inconsistent"
            )
            return False

    @staticmethod
    def _rebuild_single_item(
        db_module: Any, builder_name: str, item_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Rebuild a single item through its canonical builder.

        Uses empty user_input so get_field() falls through to existing= values.
        This avoids CFOF/DATA key collisions (e.g., CFOF_GLOBAL_INPUT_INTERNAL_ID
        matching DATA_KID_INTERNAL_ID, both = \"internal_id\").

        Args:
            db_module: data_builders module
            builder_name: One of 'assignee', 'chore', 'reward', 'badge', etc.
            item_data: Existing item data from storage.

        Returns:
            Rebuilt item data with correct schema.
        """
        empty: dict[str, Any] = {}
        if builder_name == "assignee":
            return dict(
                db_module.build_user_assignment_profile(
                    user_input=empty,
                    existing=item_data,
                )
            )
        if builder_name == "chore":
            return dict(db_module.build_chore(user_input=empty, existing=item_data))
        if builder_name == "reward":
            return dict(db_module.build_reward(user_input=empty, existing=item_data))
        if builder_name == "badge":
            return dict(db_module.build_badge(user_input=empty, existing=item_data))
        if builder_name == "penalty":
            return dict(
                db_module.build_bonus_or_penalty(
                    user_input=empty,
                    entity_type="penalty",
                    existing=item_data,
                )
            )
        if builder_name == "bonus":
            return dict(
                db_module.build_bonus_or_penalty(
                    user_input=empty,
                    entity_type="bonus",
                    existing=item_data,
                )
            )
        if builder_name == "achievement":
            return dict(
                db_module.build_achievement(user_input=empty, existing=item_data)
            )
        if builder_name == "challenge":
            return dict(db_module.build_challenge(user_input=empty, existing=item_data))
        if builder_name == "approver":
            return dict(
                db_module.build_user_profile(user_input=empty, existing=item_data)
            )

        msg = f"Unknown builder: {builder_name}"
        raise ValueError(msg)

    def _wipe_all_kc_entities(self) -> int:
        """Remove all ChoreOps entities from the entity registry.

        Platforms will recreate them on next startup with correct structure.

        Returns:
            Count of entities removed.
        """
        entity_reg = er.async_get(self.coordinator.hass)
        entries = er.async_entries_for_config_entry(
            entity_reg, self.coordinator.config_entry.entry_id
        )
        count = 0
        for entry in entries:
            entity_reg.async_remove(entry.entity_id)
            count += 1
        return count

    async def _attempt_auto_restore(self) -> bool:
        """Auto-restore from the most recent pre-migration backup (#243).

        This automates the proven manual path: Options -> General -> Restore.
        After restore, schema version will be < 43 so migration retries on
        next restart.

        Returns:
            True if restore succeeded, False if no backup or restore failed.
        """
        hass = self.coordinator.hass
        try:
            backups = await bh.discover_backups(hass, self.coordinator.store)
        except Exception:
            const.LOGGER.warning(
                "PreV50Migrator: Failed to discover backups for auto-restore"
            )
            return False

        # Find most recent pre-migration backup (list is sorted newest-first)
        pre_migration_backup = None
        for backup_info in backups:
            if backup_info.get("tag") == const.BACKUP_TAG_PRE_MIGRATION:
                pre_migration_backup = backup_info
                break

        if not pre_migration_backup:
            const.LOGGER.warning(
                "PreV50Migrator: No pre-migration backup found for auto-restore"
            )
            return False

        try:
            import json
            from pathlib import Path

            filename = pre_migration_backup["filename"]
            backup_path = Path(hass.config.path(".storage", filename))

            if not await hass.async_add_executor_job(backup_path.exists):
                const.LOGGER.warning(
                    "PreV50Migrator: Backup file not found: %s", filename
                )
                return False

            # Read and validate backup JSON
            backup_str = await hass.async_add_executor_job(
                backup_path.read_text, "utf-8"
            )
            if not bh.validate_backup_json(backup_str):
                const.LOGGER.warning(
                    "PreV50Migrator: Pre-migration backup validation failed"
                )
                return False

            backup_data = json.loads(backup_str)

            # Handle HA storage wrapper format ({"version": N, "data": {...}})
            if "version" in backup_data and "data" in backup_data:
                backup_data = backup_data["data"]

            # Restore the backup data
            self.coordinator.store.set_data(backup_data)
            await self.coordinator.store.async_save()
            self.coordinator._data = backup_data

            const.LOGGER.info(
                "PreV50Migrator: Successfully restored from pre-migration backup: %s",
                filename,
            )
            return True

        except Exception:
            const.LOGGER.warning(
                "PreV50Migrator: Failed to restore from pre-migration backup"
            )
            return False

    def _cleanup_legacy_notify_on_reminder(self) -> None:
        """Clean up legacy notify_on_reminder field from chores.

        LEGACY MIGRATION (Schema 44 / v0.5.0-beta4):
        - Old system: notify_on_reminder (bool) → hardcoded 30-minute reminder
        - New system: notify_due_reminder (bool) + chore_due_reminder_offset (string)

        This migration:
        1. Reads legacy notify_on_reminder value from each chore
        2. If notify_due_reminder doesn't exist, copies the legacy bool value
        3. Deletes the legacy notify_on_reminder field from storage

        After migration deployed broadly (v0.6.0+), remove:
        - LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY
        - LEGACY_CHORE_NOTIFY_ON_REMINDER_DEFAULT
        - Translation key "notify_on_reminder" from all language files
        - Legacy field checks from notification_manager.py
        """
        const.LOGGER.info(
            "PreV50Migrator: Migrating legacy notify_on_reminder to notify_due_reminder"
        )

        chores = self.coordinator._data.get(const.DATA_CHORES, {})
        migrated_count = 0

        for _chore_id, chore_data in chores.items():
            # Skip if chore already has notify_due_reminder configured
            if const.DATA_CHORE_NOTIFY_DUE_REMINDER in chore_data:
                # Clean up legacy field even if new field exists
                if LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY in chore_data:
                    del chore_data[LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY]
                    migrated_count += 1
                continue

            # Read legacy value (default True to preserve existing behavior)
            legacy_value = chore_data.get(
                LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY,
                LEGACY_CHORE_NOTIFY_ON_REMINDER_DEFAULT,
            )

            # Copy to new field
            chore_data[const.DATA_CHORE_NOTIFY_DUE_REMINDER] = bool(legacy_value)

            # Delete legacy field
            if LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY in chore_data:
                del chore_data[LEGACY_CHORE_NOTIFY_ON_REMINDER_KEY]

            migrated_count += 1

        const.LOGGER.info(
            "PreV50Migrator: Migrated %d chores from notify_on_reminder to notify_due_reminder",
            migrated_count,
        )

    def _enable_notify_on_overdue(self) -> None:
        """Auto-enable notify_on_overdue for existing chores.

        SCHEMA 44 MIGRATION (v0.5.0-beta4):
        - New field: notify_on_overdue (bool) controls overdue notifications
        - Previous behavior: Always sent overdue notifications (no user control)
        - This migration: Sets notify_on_overdue=True for all existing chores
          to preserve the previous always-send behavior

        For new chores, default is True (see DEFAULT_NOTIFY_ON_OVERDUE).
        """
        const.LOGGER.info(
            "PreV50Migrator: Auto-enabling notify_on_overdue for existing chores"
        )

        chores = self.coordinator._data.get(const.DATA_CHORES, {})
        enabled_count = 0

        for _chore_id, chore_data in chores.items():
            # Only set if field doesn't exist (avoid overwriting user preference)
            if const.DATA_CHORE_NOTIFY_ON_OVERDUE not in chore_data:
                chore_data[const.DATA_CHORE_NOTIFY_ON_OVERDUE] = True
                enabled_count += 1

        const.LOGGER.info(
            "PreV50Migrator: Auto-enabled notify_on_overdue for %d chores",
            enabled_count,
        )

    def _convert_applicable_days_to_integers(self) -> None:
        """Convert string day names to integers in applicable_days fields.

        SCHEMA 44 MIGRATION (v0.5.0-beta4):
        - Bug fix: RecurrenceEngine requires integer weekdays (0-6), not strings
        - Legacy data: Some chores have string day names like ["sun", "mon"]
        - This migration: Converts all string day names to integers using WEEKDAY_NAME_TO_INT
        - Affects: applicable_days (chore-level) and per_assignee_applicable_days (independent)

        After this migration, all applicable_days fields contain only integers,
        eliminating the need for defensive conversions at read-time.
        """
        const.LOGGER.info(
            "PreV50Migrator: Converting string day names to integers in applicable_days"
        )

        chores = self.coordinator._data.get(const.DATA_CHORES, {})
        converted_chores = 0
        converted_per_assignee = 0

        for _chore_id, chore_data in chores.items():
            chore_name = chore_data.get("name", "unknown")

            # Convert chore-level applicable_days (for SHARED chores)
            if chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS):
                original_days = chore_data[const.DATA_CHORE_APPLICABLE_DAYS]
                converted_days = [
                    const.WEEKDAY_NAME_TO_INT.get(day, day)
                    if isinstance(day, str)
                    else day
                    for day in original_days
                ]
                if converted_days != original_days:
                    const.LOGGER.debug(
                        "PreV50Migrator: Converting chore '%s' applicable_days: %s → %s",
                        chore_name,
                        original_days,
                        converted_days,
                    )
                    chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = converted_days
                    converted_chores += 1

            # Convert per-assignee applicable_days (for INDEPENDENT chores)
            if chore_data.get(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS):
                per_assignee_days = chore_data[
                    const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS
                ]
                for assignee_id, days_list in per_assignee_days.items():
                    original_days = days_list
                    converted_days = [
                        const.WEEKDAY_NAME_TO_INT.get(day, day)
                        if isinstance(day, str)
                        else day
                        for day in original_days
                    ]
                    if converted_days != original_days:
                        const.LOGGER.debug(
                            "PreV50Migrator: Converting chore '%s' per-assignee days for %s: %s → %s",
                            chore_name,
                            assignee_id,
                            original_days,
                            converted_days,
                        )
                        per_assignee_days[assignee_id] = converted_days
                        converted_per_assignee += 1

        const.LOGGER.info(
            "PreV50Migrator: Converted %d chore-level and %d per-assignee applicable_days",
            converted_chores,
            converted_per_assignee,
        )

    def _cleanup_legacy_assignee_chore_badge_refs(self) -> None:
        """Remove legacy badge_refs from assignee chore records.

        SCHEMA 44 MIGRATION (v0.5.0-beta4):
        - Legacy field: assignee_chore_data.<chore_id>.badge_refs
        - Current architecture: badge scope is resolved dynamically from badge
          definitions and assignment, so this denormalized cache is redundant.

        This migration removes `badge_refs` from all assignee chore records to reduce
        storage churn and prevent stale reference data.
        """
        const.LOGGER.info(
            "PreV50Migrator: Removing legacy badge_refs from assignee chore records"
        )

        assignees = self.coordinator._data.get(const.DATA_USERS, {})
        removed_count = 0

        for assignee_data in assignees.values():
            assignee_chore_data = assignee_data.get(const.DATA_USER_CHORE_DATA, {})
            if not isinstance(assignee_chore_data, dict):
                continue

            for chore_data in assignee_chore_data.values():
                if not isinstance(chore_data, dict):
                    continue

                if const.DATA_USER_CHORE_DATA_BADGE_REFS in chore_data:
                    del chore_data[const.DATA_USER_CHORE_DATA_BADGE_REFS]
                    removed_count += 1

        const.LOGGER.info(
            "PreV50Migrator: Removed badge_refs from %d assignee chore records",
            removed_count,
        )

    def _migrate_to_schema_44(self) -> None:
        """Apply schema 44 (beta 4) tweaks.

        Only runs when current_version == 43, confirming all pre-v50 migrations
        completed successfully. This is the safe place to add beta 4 changes
        without touching frozen schema 43 migration code.

        Schema 44 tweaks are intentionally minimal — the gate infrastructure
        is what matters for future extensibility.
        """
        from homeassistant.util import dt as dt_util

        const.LOGGER.info("PreV50Migrator: Applying schema 44 (beta 4) tweaks")

        # --- Add beta 4 tweaks here as needed ---
        # Clean up legacy notify_on_reminder field (hardcoded 30min → configurable)
        self._cleanup_legacy_notify_on_reminder()

        # Auto-enable notify_on_overdue for existing chores (preserve behavior)
        self._enable_notify_on_overdue()

        # Convert string day names to integers in applicable_days (RecurrenceEngine fix)
        self._convert_applicable_days_to_integers()

        # Remove legacy chore badge_refs from assignee chore records
        self._cleanup_legacy_assignee_chore_badge_refs()

        # v0.5.0 Chore Logic: Backfill rotation fields for all chores
        self._backfill_rotation_fields()

        # Phase 2 (v0.5.0-beta4): Eliminate completed_by_other state
        # Convert any existing assignee chore states from "completed_by_other" to "pending"
        # and remove completed_by_other_chores lists from assignee data
        assignees = self.coordinator._data.get(const.DATA_USERS, {})
        chores_migrated = 0
        lists_removed = 0

        for assignee_data in assignees.values():
            # Remove completed_by_other_chores list (no longer used)
            # Note: Using deprecated constant name as string literal since
            # the constant itself was removed in Phase 2
            if "completed_by_other_chores" in assignee_data:
                del assignee_data["completed_by_other_chores"]
                lists_removed += 1

            # Convert all completed_by_other states to pending
            chore_data_map = assignee_data.get(const.DATA_USER_CHORE_DATA, {})
            for chore_data in chore_data_map.values():
                current_state = chore_data.get(const.DATA_USER_CHORE_DATA_STATE)
                if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
                    chore_data[const.DATA_USER_CHORE_DATA_STATE] = (
                        const.CHORE_STATE_PENDING
                    )
                    chores_migrated += 1

        if chores_migrated > 0 or lists_removed > 0:
            const.LOGGER.info(
                "Phase 2 migration: Converted %d completed_by_other states to pending, "
                "removed %d completed_by_other_chores lists",
                chores_migrated,
                lists_removed,
            )

        # Cumulative Badge Progress Cleanup (v0.5.0-beta4)
        # Remove deprecated baseline field, derived fields (now computed on-read),
        # and reset cycle_points for badges without maintenance
        baseline_removed = 0
        derived_removed = 0
        cycle_reset = 0

        # Fields to strip from cumulative_badge_progress (computed on-read now)
        DERIVED_PROGRESS_FIELDS = [
            "current_badge_id",
            "current_badge_name",
            "current_threshold",
            "highest_earned_badge_id",
            "highest_earned_badge_name",
            "highest_earned_threshold",
            "next_higher_badge_id",
            "next_higher_badge_name",
            "next_higher_threshold",
            "next_higher_points_needed",
            "next_lower_badge_id",
            "next_lower_badge_name",
            "next_lower_threshold",
        ]

        for assignee_data in assignees.values():
            progress = assignee_data.get(const.DATA_USER_CUMULATIVE_BADGE_PROGRESS, {})
            if not progress:
                continue

            # Remove baseline field (deprecated - acquisition uses total_points_earned)
            if "baseline" in progress:
                del progress["baseline"]
                baseline_removed += 1

            # Remove all derived fields (now computed via get_cumulative_badge_progress)
            for field in DERIVED_PROGRESS_FIELDS:
                if field in progress:
                    del progress[field]
                    derived_removed += 1

            # Reset cycle_points to 0 if current badge doesn't have maintenance enabled
            # Note: Must use get_cumulative_badge_levels() since current_badge_id no longer stored
            # For migration simplicity, we skip this check - cycle_points will naturally
            # reset to 0 on next maintenance cycle or demotion
            # Original logic kept for reference but disabled:
            # current_badge_id = progress.get(CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID)
            # This field no longer exists after derived field removal above

        if baseline_removed > 0 or derived_removed > 0 or cycle_reset > 0:
            const.LOGGER.info(
                "Cumulative badge progress cleanup: Removed %d baseline fields, "
                "%d derived fields, reset %d cycle_points for badges without maintenance",
                baseline_removed,
                derived_removed,
                cycle_reset,
            )

        # --- Cumulative Badge Data Integrity (v0.5.0-beta4 hotfix) ---
        # Fixes corrupted data where assignees have invalid DEMOTED status with null
        # maintenance dates (causes infinite re-promotion loop at runtime).
        # Also deduplicates earned_by lists and initialises missing progress dicts.
        badges = self.coordinator._data.get(const.DATA_BADGES, {})

        # Build lookup: badge_id → maintenance_enabled (bool)
        cumulative_badges_by_id: dict[str, dict[str, Any]] = {}
        for bid, bdata in badges.items():
            if bdata.get(const.DATA_BADGE_TYPE) != const.BADGE_TYPE_CUMULATIVE:
                continue
            cumulative_badges_by_id[bid] = bdata

        def _badge_maintenance_enabled(bdata: dict[str, Any]) -> bool:
            """Return True if badge has active maintenance schedule."""
            target = bdata.get(const.DATA_BADGE_TARGET, {})
            maint_threshold = float(target.get(const.DATA_BADGE_MAINTENANCE_RULES, 0))
            rs = bdata.get(const.DATA_BADGE_RESET_SCHEDULE, {})
            freq = rs.get(
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                const.FREQUENCY_NONE,
            )
            return freq != const.FREQUENCY_NONE and maint_threshold > 0

        def _compute_maintenance_dates(
            bdata: dict[str, Any],
        ) -> tuple[str | None, str | None]:
            """Compute (end_date, grace_end_date) from badge reset_schedule."""
            rs = bdata.get(const.DATA_BADGE_RESET_SCHEDULE, {})
            freq = rs.get(
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                const.FREQUENCY_NONE,
            )
            if freq == const.FREQUENCY_NONE:
                return (None, None)

            today_iso = dt_today_iso()
            next_end: str | None = None

            if freq == const.FREQUENCY_CUSTOM:
                c_interval = rs.get(const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL)
                c_unit = rs.get(const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT)
                if c_interval and c_unit:
                    result = dt_add_interval(
                        today_iso,
                        interval_unit=c_unit,
                        delta=int(c_interval),
                        require_future=True,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
                    next_end = str(result) if result else None
            else:
                result = dt_next_schedule(
                    today_iso,
                    interval_type=freq,
                    require_future=True,
                    return_type=const.HELPER_RETURN_ISO_DATE,
                )
                next_end = str(result) if result else None

            next_grace: str | None = None
            grace_days = int(
                rs.get(const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS, 0)
            )
            if next_end:
                if grace_days > 0:
                    g_result = dt_add_interval(
                        next_end,
                        interval_unit=const.TIME_UNIT_DAYS,
                        delta=grace_days,
                        return_type=const.HELPER_RETURN_ISO_DATE,
                    )
                    next_grace = str(g_result) if g_result else next_end
                else:
                    # No grace period — grace end matches maintenance end
                    next_grace = next_end

            return (next_end, next_grace)

        # Task 1: Dedup earned_by lists on all badges
        dedup_count = 0
        for bdata in badges.values():
            earned_by = bdata.get(const.DATA_BADGE_EARNED_BY)
            if earned_by and isinstance(earned_by, list):
                unique = list(dict.fromkeys(earned_by))  # preserves order
                if len(unique) != len(earned_by):
                    bdata[const.DATA_BADGE_EARNED_BY] = unique
                    dedup_count += 1

        if dedup_count > 0:
            const.LOGGER.info(
                "Badge migration: Deduplicated earned_by on %d badge(s)",
                dedup_count,
            )

        # Task 2-4: Per-assignee progress repair
        status_repaired = 0
        dates_initialised = 0
        progress_created = 0

        # Build sorted cumulative badge list (lowest → highest threshold)
        sorted_cumulative = sorted(
            cumulative_badges_by_id.items(),
            key=lambda item: float(
                item[1]
                .get(const.DATA_BADGE_TARGET, {})
                .get(const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0)
            ),
        )

        for assignee_id, assignee_data in assignees.items():
            # Task 2: Ensure cumulative_badge_progress exists
            progress = assignee_data.get(const.DATA_USER_CUMULATIVE_BADGE_PROGRESS)
            if progress is None:
                assignee_data[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS] = {
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: 0,
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_STATUS: (
                        const.CUMULATIVE_BADGE_STATE_ACTIVE
                    ),
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE: None,
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE: None,
                }
                progress_created += 1
                continue  # freshly initialised, no further repair needed

            if not isinstance(progress, dict):
                continue

            # Find assignee's highest earned cumulative badge
            badges_earned = assignee_data.get(const.DATA_USER_BADGES_EARNED, {})
            highest_badge_data: dict[str, Any] | None = None
            for bid, bdata in sorted_cumulative:
                # Check assignment: empty list = all assignees
                assigned = bdata.get(const.DATA_BADGE_ASSIGNED_USER_IDS, [])
                if assigned and assignee_id not in assigned:
                    continue
                if bid in badges_earned:
                    highest_badge_data = bdata

            current_status = progress.get(
                const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_STATUS
            )
            end_date = progress.get(
                const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
            )

            # Task 3: Repair invalid DEMOTED status when maintenance is not enabled
            if (
                current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED
                and highest_badge_data is not None
                and not _badge_maintenance_enabled(highest_badge_data)
            ):
                progress[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
                    const.CUMULATIVE_BADGE_STATE_ACTIVE
                )
                progress[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0
                progress[
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
                ] = None
                progress[
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
                ] = None
                status_repaired += 1
                const.LOGGER.debug(
                    "Badge migration: Repaired DEMOTED→ACTIVE for assignee %s "
                    "(badge has no maintenance)",
                    assignee_id,
                )
                continue  # dates correctly set to None

            # Task 4: Initialise maintenance dates for DEMOTED/ACTIVE with maintenance
            # enabled but null dates (legacy data corruption)
            if (
                highest_badge_data is not None
                and _badge_maintenance_enabled(highest_badge_data)
                and end_date is None
            ):
                new_end, new_grace = _compute_maintenance_dates(highest_badge_data)
                progress[
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE
                ] = new_end
                progress[
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
                ] = new_grace
                # If status was DEMOTED with null dates, repair to ACTIVE
                if current_status == const.CUMULATIVE_BADGE_STATE_DEMOTED:
                    progress[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
                        const.CUMULATIVE_BADGE_STATE_ACTIVE
                    )
                    progress[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 0
                    status_repaired += 1
                dates_initialised += 1
                const.LOGGER.debug(
                    "Badge migration: Initialised maintenance dates for assignee %s "
                    "(end=%s, grace=%s)",
                    assignee_id,
                    new_end,
                    new_grace,
                )

        # Task 5: Convert cumulative badge target_type from "points" to "points_all_time"
        # This clarifies the architectural distinction between periodic points (daily/weekly)
        # and all-time lifetime points used by cumulative badges.
        target_type_migrated = 0
        for _badge_id, badge_data in badges.items():
            badge_type = badge_data.get(const.DATA_BADGE_TYPE)
            if badge_type != const.BADGE_TYPE_CUMULATIVE:
                continue  # Only cumulative badges need this migration

            target = badge_data.get(const.DATA_BADGE_TARGET)
            if not target:
                continue  # No target to migrate

            current_target_type = target.get(const.DATA_BADGE_TARGET_TYPE)
            if current_target_type == const.BADGE_TARGET_THRESHOLD_TYPE_POINTS:
                # Migrate to the explicit all-time points target type
                target[const.DATA_BADGE_TARGET_TYPE] = (
                    const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_ALL_TIME
                )
                target_type_migrated += 1
                const.LOGGER.debug(
                    "Badge migration: Converted cumulative badge %s target_type "
                    "from 'points' to 'points_all_time'",
                    _badge_id,
                )

        if target_type_migrated > 0:
            const.LOGGER.info(
                "Badge target type migration: Converted %d cumulative badges "
                "from 'points' to 'points_all_time'",
                target_type_migrated,
            )

        if (
            status_repaired > 0
            or dates_initialised > 0
            or progress_created > 0
            or target_type_migrated > 0
        ):
            const.LOGGER.info(
                "Badge data integrity: Repaired %d invalid DEMOTED states, "
                "initialised %d maintenance date sets, created %d missing progress dicts, "
                "migrated %d cumulative badge target types",
                status_repaired,
                dates_initialised,
                progress_created,
                target_type_migrated,
            )

        # Stamp schema 44
        meta = self.coordinator._data.get(const.DATA_META, {})
        applied = list(meta.get(const.DATA_META_MIGRATIONS_APPLIED, []))
        applied.append("schema_44_beta4")

        self.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
            const.DATA_META_LAST_MIGRATION_DATE: datetime.now(dt_util.UTC).isoformat(),
            const.DATA_META_MIGRATIONS_APPLIED: applied,
            const.DATA_META_PENDING_EVALUATIONS: meta.get(
                const.DATA_META_PENDING_EVALUATIONS, []
            ),
        }

        const.LOGGER.info("PreV50Migrator: Schema 44 migration complete")

    def _backfill_rotation_fields(self) -> None:
        """Add rotation_current_assignee_id and rotation_cycle_override to all chores.

        For existing rotation_* chores: initialize current_assignee_id if not present.
        For non-rotation chores: add fields as None/False (clean data model).
        """
        const.LOGGER.info(
            "PreV50Migrator: Backfilling rotation fields for v0.5.0 Chore Logic"
        )

        chores = self.coordinator._data.get(const.DATA_CHORES, {})
        backfilled_count = 0
        initialized_rotation_count = 0

        for _chore_id, chore_data in chores.items():
            criteria = chore_data.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            is_rotation = criteria in (
                const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
                const.COMPLETION_CRITERIA_ROTATION_SMART,
            )
            assigned_assignees = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])

            # Add fields if missing (backward compat)
            if const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID not in chore_data:
                if is_rotation and assigned_assignees:
                    chore_data[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = (
                        assigned_assignees[0]
                    )
                    initialized_rotation_count += 1
                else:
                    chore_data[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = None
                backfilled_count += 1

            # rotation_order removed - unused field, assigned_assignees defines order

            if const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE not in chore_data:
                chore_data[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False
                backfilled_count += 1

        const.LOGGER.info(
            "Backfilled %d rotation fields, initialized %d rotation chores",
            backfilled_count,
            initialized_rotation_count,
        )

    def _migrate_point_periods_v43(self) -> None:
        """Flatten point_data → point_periods and transform field names (v42 → v43).

        v42 structure (nested):
            assignee["point_data"]["periods"][period_type][period_key] = {
                "points_total": 100.0,  # NET value (earned - spent)
                "by_source": {"chores": 150.0, "manual": -50.0}
            }
            assignee["point_stats"]["highest_balance"] = 2980.0  # Separate bucket

        v43 structure (flat):
            assignee["point_periods"][period_type][period_key] = {
                "points_earned": 150.0,  # Sum of positive by_source values
                "points_spent": -50.0,    # Sum of negative by_source values
                "by_source": {"chores": 150.0, "manual": -50.0}
            }
            assignee["point_periods"]["all_time"]["all_time"]["highest_balance"] = 2980.0

        Transformations:
        1. Flatten: point_data.periods → point_periods
        2. Calculate: points_earned (sum positive by_source), points_spent (sum negative)
        3. Remove: points_total (replaced by earned/spent)
        4. Extract: highest_balance from point_stats → point_periods.all_time.all_time
        5. Remove: point_stats bucket (deprecated)

        This migration is idempotent - safe to run multiple times.
        """
        const.LOGGER.info("Starting v42 → v43 migration: point_data → point_periods")

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        migrated_count = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)

            # Skip if already migrated to v43 structure
            if const.DATA_USER_POINT_PERIODS in assignee_info:
                const.LOGGER.debug(
                    "Assignee '%s' (%s) already has point_periods - skipping",
                    assignee_name,
                    assignee_id,
                )
                continue

            # Extract v42 structures
            point_data = assignee_info.pop(const.DATA_ASSIGNEE_POINT_DATA_LEGACY, {})
            point_stats = assignee_info.pop(const.DATA_ASSIGNEE_POINT_STATS_LEGACY, {})
            periods = point_data.get(const.DATA_ASSIGNEE_POINT_DATA_PERIODS_LEGACY, {})

            # Initialize flat v43 structure
            point_periods: dict[str, Any] = {}

            # Transform each period bucket
            for period_type, entries in periods.items():
                point_periods[period_type] = {}

                if period_type == const.DATA_USER_POINT_PERIODS_ALL_TIME:
                    # all_time is single dict: {"all_time": {data}}
                    # Special handling: points_earned = highest_balance
                    for period_key, data in entries.items():
                        transformed = self._transform_period_entry(
                            data, is_all_time=True
                        )
                        point_periods[period_type][period_key] = transformed
                else:
                    # daily/weekly/monthly/yearly are nested: {"2025-11": {data}}
                    for period_key, data in entries.items():
                        transformed = self._transform_period_entry(
                            data, is_all_time=False
                        )
                        point_periods[period_type][period_key] = transformed

            # Extract highest_balance from point_stats → all_time bucket
            if highest_balance := point_stats.get(
                const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE
            ):
                point_periods.setdefault(
                    const.DATA_USER_POINT_PERIODS_ALL_TIME, {}
                ).setdefault(const.PERIOD_ALL_TIME, {})[
                    const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE
                ] = highest_balance

                # For all_time: points_earned should equal highest_balance
                # points_spent = (sum of by_source) - highest_balance
                all_time_entry = point_periods[const.DATA_USER_POINT_PERIODS_ALL_TIME][
                    const.PERIOD_ALL_TIME
                ]
                by_source = all_time_entry.get(
                    const.DATA_USER_POINT_PERIOD_BY_SOURCE, {}
                )
                current_balance = sum(by_source.values())
                all_time_entry[const.DATA_USER_POINT_PERIOD_POINTS_EARNED] = (
                    highest_balance
                )
                all_time_entry[const.DATA_USER_POINT_PERIOD_POINTS_SPENT] = (
                    current_balance - highest_balance
                )

            # Set new structure
            assignee_info[const.DATA_USER_POINT_PERIODS] = point_periods
            migrated_count += 1

            const.LOGGER.debug(
                "Migrated assignee '%s' (%s): point_data → point_periods",
                assignee_name,
                assignee_id,
            )

        const.LOGGER.info(
            "Completed v42 → v43 migration: %d assignees migrated to point_periods",
            migrated_count,
        )

    def _migrate_chore_periods_v43(self) -> None:
        """Create assignee-level chore_periods bucket and remove deprecated fields (v43).

        v42 structure:
            assignee["chore_stats"] = {...}  # Aggregated dict (to be deleted)
            assignee["chore_data"][uuid]["total_points"] = 150.0  # Redundant field
            assignee["chore_data"][uuid]["periods"]["all_time"]["all_time"]["points"] = 150.0  # Canonical

        v43 structure:
            assignee["chore_periods"] = {}  # New: Aggregated across ALL chores, survives deletion
            assignee["chore_data"][uuid]["periods"]...  # Keep per-chore periods
            # REMOVED: assignee["chore_stats"] (now fully ephemeral - generated on-demand)
            # REMOVED: assignee["chore_data"][uuid]["total_points"] (use periods.all_time.points)

        This migration (Phase 12 - Lean Chore Architecture):
        1. Creates empty chore_periods bucket at assignee level (StatisticsEngine populates on-demand)
        2. Removes total_points from each chore item (periods.all_time.points is canonical)
        3. Deletes chore_stats dict entirely (now fully ephemeral - generate_chore_stats())

        This migration is idempotent - safe to run multiple times.
        """
        const.LOGGER.info(
            "Starting v43 migration: Create chore_periods, remove total_points, delete chore_stats"
        )

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        assignees_migrated = 0
        items_cleaned = 0
        stats_deleted = 0
        backfilled_count = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)

            # Step 1: Create chore_periods bucket if missing (Landlord genesis)
            # AND backfill all_time from per-chore periods to preserve historical totals
            if const.DATA_USER_CHORE_PERIODS not in assignee_info:
                assignee_info[const.DATA_USER_CHORE_PERIODS] = {}
                assignees_migrated += 1
                const.LOGGER.debug(
                    "Created chore_periods bucket for assignee '%s' (%s)",
                    assignee_name,
                    assignee_id,
                )

            # Step 1b: Backfill chore_periods from per-chore periods
            # This aggregates all chore_data[uuid].periods into global buckets
            chore_periods = assignee_info[const.DATA_USER_CHORE_PERIODS]

            # Check if backfill is needed: either all_time doesn't exist,
            # OR all_time exists but has zeros while per-chore data has real values
            needs_backfill = (
                const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME not in chore_periods
            )
            if not needs_backfill:
                # Check if existing all_time is empty/zero
                existing_all_time = chore_periods.get(
                    const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME, {}
                ).get(const.PERIOD_ALL_TIME, {})
                existing_approved = existing_all_time.get(
                    const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                )
                existing_completed = existing_all_time.get(
                    const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED, 0
                )
                # If both are zero, check if per-chore data has non-zero values
                if existing_approved == 0 and existing_completed == 0:
                    chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
                    for _cid, chore_item in chore_data.items():
                        per_chore_all_time = (
                            chore_item.get(const.DATA_USER_CHORE_DATA_PERIODS, {})
                            .get(const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME, {})
                            .get(const.PERIOD_ALL_TIME, {})
                        )
                        if (
                            per_chore_all_time.get(
                                const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                            )
                            > 0
                        ):
                            needs_backfill = True
                            const.LOGGER.info(
                                "Re-aggregating chore_periods for assignee '%s' - "
                                "found per-chore data but assignee-level was zero",
                                assignee_name,
                            )
                            break

            if needs_backfill:
                # Aggregate all-time stats from all chores
                total_approved = 0
                total_completed = 0
                total_claimed = 0
                total_points = 0.0
                max_longest_streak = 0

                # Period aggregation buckets (by date/week/month/year key)
                daily_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )
                weekly_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )
                monthly_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )
                yearly_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )

                chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
                for _chore_id, chore_item in chore_data.items():
                    periods = chore_item.get(const.DATA_USER_CHORE_DATA_PERIODS, {})

                    # All-time aggregation (nested: periods["all_time"]["all_time"])
                    all_time = periods.get(
                        const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME, {}
                    ).get(const.PERIOD_ALL_TIME, {})
                    total_approved += all_time.get(
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                    )
                    total_completed += all_time.get(
                        const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED, 0
                    )
                    total_claimed += all_time.get(
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED, 0
                    )
                    total_points += all_time.get(
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS, 0.0
                    )
                    # Track MAX longest_streak (not SUM)
                    chore_streak = all_time.get(
                        const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
                    )
                    max_longest_streak = max(max_longest_streak, chore_streak)

                    # Aggregate daily periods
                    for date_key, daily_data in periods.get(
                        const.PERIOD_DAILY, {}
                    ).items():
                        daily_totals[date_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED
                        ] += daily_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                        )
                        daily_totals[date_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED
                        ] += daily_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED, 0
                        )
                        daily_totals[date_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS
                        ] += daily_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS, 0.0
                        )
                        daily_totals[date_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE
                        ] += daily_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE, 0
                        )
                        daily_totals[date_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED
                        ] += daily_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED, 0
                        )
                        # streak_tally: Take MAX per date (highest streak on that day)
                        current_tally = daily_totals[date_key].get(
                            const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY, 0
                        )
                        chore_tally = daily_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY, 0
                        )
                        daily_totals[date_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY
                        ] = max(current_tally, chore_tally)

                    # Aggregate weekly periods
                    for week_key, weekly_data in periods.get(
                        const.PERIOD_WEEKLY, {}
                    ).items():
                        weekly_totals[week_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED
                        ] += weekly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                        )
                        weekly_totals[week_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED
                        ] += weekly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED, 0
                        )
                        weekly_totals[week_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS
                        ] += weekly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS, 0.0
                        )
                        weekly_totals[week_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE
                        ] += weekly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE, 0
                        )
                        weekly_totals[week_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED
                        ] += weekly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED, 0
                        )

                    # Aggregate monthly periods
                    for month_key, monthly_data in periods.get(
                        const.PERIOD_MONTHLY, {}
                    ).items():
                        monthly_totals[month_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED
                        ] += monthly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                        )
                        monthly_totals[month_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED
                        ] += monthly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED, 0
                        )
                        monthly_totals[month_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS
                        ] += monthly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS, 0.0
                        )
                        monthly_totals[month_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE
                        ] += monthly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE, 0
                        )
                        monthly_totals[month_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED
                        ] += monthly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED, 0
                        )

                    # Aggregate yearly periods
                    for year_key, yearly_data in periods.get(
                        const.PERIOD_YEARLY, {}
                    ).items():
                        yearly_totals[year_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED
                        ] += yearly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED, 0
                        )
                        yearly_totals[year_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED
                        ] += yearly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED, 0
                        )
                        yearly_totals[year_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS
                        ] += yearly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS, 0.0
                        )
                        yearly_totals[year_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE
                        ] += yearly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE, 0
                        )
                        yearly_totals[year_key][
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED
                        ] += yearly_data.get(
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED, 0
                        )

                # Store aggregated all_time bucket (nested: all_time.all_time for consistency)
                chore_periods[const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME] = {
                    const.PERIOD_ALL_TIME: {
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: total_approved,
                        const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED: total_completed,
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: total_claimed,
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS: round(
                            total_points, const.DATA_FLOAT_PRECISION
                        ),
                        const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK: max_longest_streak,
                    }
                }

                # Store aggregated period buckets (convert defaultdict to dict)
                if daily_totals:
                    chore_periods[const.PERIOD_DAILY] = {
                        k: dict(v) for k, v in daily_totals.items()
                    }
                if weekly_totals:
                    chore_periods[const.PERIOD_WEEKLY] = {
                        k: dict(v) for k, v in weekly_totals.items()
                    }
                if monthly_totals:
                    chore_periods[const.PERIOD_MONTHLY] = {
                        k: dict(v) for k, v in monthly_totals.items()
                    }
                if yearly_totals:
                    chore_periods[const.PERIOD_YEARLY] = {
                        k: dict(v) for k, v in yearly_totals.items()
                    }

                backfilled_count += 1
                const.LOGGER.debug(
                    "Backfilled chore_periods for assignee '%s': "
                    "all_time(approved=%d, completed=%d, points=%.2f, longest_streak=%d), "
                    "daily=%d, weekly=%d, monthly=%d, yearly=%d",
                    assignee_name,
                    total_approved,
                    total_completed,
                    total_points,
                    max_longest_streak,
                    len(daily_totals),
                    len(weekly_totals),
                    len(monthly_totals),
                    len(yearly_totals),
                )

            # Step 2: Remove total_points from each chore item
            chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
            for _chore_id, chore_item in chore_data.items():
                if const.DATA_CHORE_TOTAL_POINTS_LEGACY in chore_item:
                    chore_item.pop(const.DATA_CHORE_TOTAL_POINTS_LEGACY)
                    items_cleaned += 1

            # Step 3: Delete chore_stats dict (now fully ephemeral)
            if const.DATA_ASSIGNEE_CHORE_STATS_LEGACY in assignee_info:
                assignee_info.pop(const.DATA_ASSIGNEE_CHORE_STATS_LEGACY)
                stats_deleted += 1
                const.LOGGER.debug(
                    "Deleted chore_stats for assignee '%s' (now ephemeral)",
                    assignee_name,
                )

            # Step 4: Remove unused dead fields (never referenced in codebase)
            if "overall_chore_streak" in assignee_info:
                assignee_info.pop("overall_chore_streak")
            if "last_chore_date" in assignee_info:
                assignee_info.pop("last_chore_date")

            # Step 5: Clean up per-chore period bucket structure
            # Remove longest_streak from daily/weekly/monthly/yearly (should only be in all_time)
            # Remove streak_tally from weekly/monthly/yearly/all_time (should only be in daily)
            chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
            for chore_item in chore_data.values():
                periods = chore_item.get(const.DATA_USER_CHORE_DATA_PERIODS, {})

                # Clean daily: remove longest_streak (keep streak_tally)
                for daily_bucket in periods.get(const.PERIOD_DAILY, {}).values():
                    daily_bucket.pop(
                        const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK, None
                    )

                # Clean weekly/monthly/yearly: remove both longest_streak and streak_tally
                for period_type in (
                    const.PERIOD_WEEKLY,
                    const.PERIOD_MONTHLY,
                    const.PERIOD_YEARLY,
                ):
                    for period_bucket in periods.get(period_type, {}).values():
                        period_bucket.pop(
                            const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK, None
                        )
                        period_bucket.pop(
                            const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY, None
                        )

                # Clean all_time: remove streak_tally (keep longest_streak)
                all_time = periods.get(const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME, {})
                if isinstance(all_time, dict):
                    all_time.pop(const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY, None)

            # Step 6: Clear broken per-chore temporal periods
            # Earlier migrations incorrectly populated yearly/monthly/weekly/daily
            # with cumulative all_time values instead of period-specific values.
            # CRITICAL FIX: Only clear if data appears broken (single bucket with all-time key)
            # Preserve legitimate period data from beta2+ installations.
            chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
            for chore_item in chore_data.values():
                periods = chore_item.get(const.DATA_USER_CHORE_DATA_PERIODS, {})

                # Clear temporal period buckets ONLY if broken (single "all_time" key)
                for period_type in (
                    const.PERIOD_DAILY,
                    const.PERIOD_WEEKLY,
                    const.PERIOD_MONTHLY,
                    const.PERIOD_YEARLY,
                ):
                    if period_type in periods:
                        period_bucket = periods[period_type]
                        # Broken data has single key "all_time" with cumulative values
                        # Valid data has date keys like "2026-02-01", "2026-W05", "2026-02", "2026"
                        if (
                            len(period_bucket) == 1
                            and const.PERIOD_ALL_TIME in period_bucket
                        ):
                            # Broken format detected - clear it
                            periods[period_type] = {}
                            const.LOGGER.debug(
                                "Cleared broken %s period data for chore '%s' (assignee '%s')",
                                period_type,
                                chore_item.get(const.DATA_CHORE_NAME, "unknown"),
                                assignee_name,
                            )
                        # Otherwise preserve existing valid period data

        const.LOGGER.info(
            "Completed v43 chore_periods migration: "
            "%d assignees got chore_periods bucket, %d backfilled all_time, "
            "%d items had total_points removed, %d chore_stats deleted",
            assignees_migrated,
            backfilled_count,
            items_cleaned,
            stats_deleted,
        )

    def _migrate_reward_periods_v43(self) -> None:
        """Create assignee-level reward_periods bucket and remove deprecated fields (v43).

        v42 structure:
            assignee["reward_stats"] = {...}  # Aggregated dict (to be deleted)
            assignee["reward_data"][uuid]["total_claims"] = 40  # Redundant field
            assignee["reward_data"][uuid]["total_approved"] = 10  # Redundant field
            assignee["reward_data"][uuid]["total_disapproved"] = 0  # Redundant field
            assignee["reward_data"][uuid]["total_points_spent"] = 1000.0  # Redundant field
            assignee["reward_data"][uuid]["notification_ids"] = [...]  # NotificationManager owns
            assignee["reward_data"][uuid]["periods"]["all_time"]["all_time"]["claimed"] = 40  # Canonical

        v43 structure:
            assignee["reward_periods"] = {}  # New: Aggregated across ALL rewards, survives deletion
            assignee["reward_data"][uuid]["periods"]...  # Keep per-reward periods
            # REMOVED: assignee["reward_stats"] (now fully ephemeral - generate_reward_stats())
            # REMOVED: assignee["reward_data"][uuid]["total_*"] (use periods.all_time.*)
            # REMOVED: assignee["reward_data"][uuid]["notification_ids"] (NotificationManager owns)

        This migration (Phase 12b - Lean Reward Architecture):
        1. Creates empty reward_periods bucket at assignee level (StatisticsEngine populates on-demand)
        2. Removes total_* fields from each reward item (periods.all_time.* is canonical)
        3. Removes notification_ids from each reward item (NotificationManager owns lifecycle)
        4. Deletes reward_stats dict entirely (now fully ephemeral)

        This migration is idempotent - safe to run multiple times.
        """
        const.LOGGER.info(
            "Starting v43 reward_periods migration: Create reward_periods, "
            "remove total_*/notification_ids, delete reward_stats"
        )

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        assignees_migrated = 0
        items_cleaned = 0
        stats_deleted = 0
        backfilled_count = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)

            # Step 1: Create reward_periods bucket if missing (Landlord genesis)
            # AND backfill all_time from per-reward periods to preserve historical totals
            if const.DATA_USER_REWARD_PERIODS not in assignee_info:
                assignee_info[const.DATA_USER_REWARD_PERIODS] = {}
                assignees_migrated += 1
                const.LOGGER.debug(
                    "Created reward_periods bucket for assignee '%s' (%s)",
                    assignee_name,
                    assignee_id,
                )

            # Step 1b: Backfill reward_periods from per-reward periods
            # This aggregates all reward_data[uuid].periods into global buckets
            reward_periods = assignee_info[const.DATA_USER_REWARD_PERIODS]

            # Check if backfill is needed
            needs_backfill = (
                const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME not in reward_periods
            )
            if not needs_backfill:
                # Check if existing all_time is empty/zero
                existing_all_time = reward_periods.get(
                    const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME, {}
                ).get(const.PERIOD_ALL_TIME, {})
                existing_approved = existing_all_time.get("approved", 0)
                existing_claimed = existing_all_time.get("claimed", 0)
                # If both are zero, check if per-reward data has non-zero values
                if existing_approved == 0 and existing_claimed == 0:
                    reward_data = assignee_info.get(const.DATA_USER_REWARD_DATA, {})
                    for _rid, reward_item in reward_data.items():
                        per_reward_all_time = (
                            reward_item.get(const.DATA_USER_REWARD_DATA_PERIODS, {})
                            .get(const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME, {})
                            .get(const.PERIOD_ALL_TIME, {})
                        )
                        if per_reward_all_time.get("approved", 0) > 0:
                            needs_backfill = True
                            const.LOGGER.info(
                                "Re-aggregating reward_periods for assignee '%s' - "
                                "found per-reward data but assignee-level was zero",
                                assignee_name,
                            )
                            break

            if needs_backfill:
                # Aggregate all-time stats from all rewards
                total_claimed = 0
                total_approved = 0
                total_disapproved = 0
                total_points = 0.0

                # Period aggregation buckets (by date/week/month/year key)
                daily_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )
                weekly_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )
                monthly_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )
                yearly_totals: dict[str, dict[str, int | float]] = defaultdict(
                    lambda: defaultdict(int)
                )

                reward_data = assignee_info.get(const.DATA_USER_REWARD_DATA, {})
                for _reward_id, reward_item in reward_data.items():
                    periods = reward_item.get(const.DATA_USER_REWARD_DATA_PERIODS, {})

                    # Aggregate all_time totals from periods (preferred source)
                    all_time_data = periods.get(
                        const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME, {}
                    ).get(const.PERIOD_ALL_TIME, {})

                    # Fallback: If periods.all_time doesn't exist, read from total_* fields
                    # (for data migrated from v40 → v42 but not yet to period structure)
                    if not all_time_data:
                        claimed_from_total = reward_item.get(
                            const.DATA_USER_REWARD_DATA_TOTAL_CLAIMS, 0
                        )
                        approved_from_total = reward_item.get(
                            const.DATA_USER_REWARD_DATA_TOTAL_APPROVED, 0
                        )
                        disapproved_from_total = reward_item.get(
                            const.DATA_USER_REWARD_DATA_TOTAL_DISAPPROVED, 0
                        )
                        points_from_total = reward_item.get(
                            const.DATA_USER_REWARD_DATA_TOTAL_POINTS_SPENT, 0.0
                        )

                        # Populate per-reward periods.all_time.all_time from total_* fields
                        if not periods:
                            periods = reward_item[
                                const.DATA_USER_REWARD_DATA_PERIODS
                            ] = {
                                const.DATA_USER_REWARD_DATA_PERIODS_DAILY: {},
                                const.DATA_USER_REWARD_DATA_PERIODS_WEEKLY: {},
                                const.DATA_USER_REWARD_DATA_PERIODS_MONTHLY: {},
                                const.DATA_USER_REWARD_DATA_PERIODS_YEARLY: {},
                                const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME: {},
                            }

                        all_time_bucket = periods.setdefault(
                            const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME, {}
                        )
                        all_time_bucket[const.PERIOD_ALL_TIME] = {
                            "claimed": claimed_from_total,
                            "approved": approved_from_total,
                            "disapproved": disapproved_from_total,
                            "points": points_from_total,
                        }

                        total_claimed += claimed_from_total
                        total_approved += approved_from_total
                        total_disapproved += disapproved_from_total
                        total_points += points_from_total
                    else:
                        # Use period data (modern structure)
                        total_claimed += all_time_data.get("claimed", 0)
                        total_approved += all_time_data.get("approved", 0)
                        total_disapproved += all_time_data.get("disapproved", 0)
                        total_points += all_time_data.get("points", 0.0)

                    # Aggregate daily periods
                    for day_key, daily_data in periods.get(
                        const.PERIOD_DAILY, {}
                    ).items():
                        daily_totals[day_key]["claimed"] += daily_data.get("claimed", 0)
                        daily_totals[day_key]["approved"] += daily_data.get(
                            "approved", 0
                        )
                        daily_totals[day_key]["disapproved"] += daily_data.get(
                            "disapproved", 0
                        )
                        daily_totals[day_key]["points"] += daily_data.get("points", 0.0)

                    # Aggregate weekly periods
                    for week_key, weekly_data in periods.get(
                        const.PERIOD_WEEKLY, {}
                    ).items():
                        weekly_totals[week_key]["claimed"] += weekly_data.get(
                            "claimed", 0
                        )
                        weekly_totals[week_key]["approved"] += weekly_data.get(
                            "approved", 0
                        )
                        weekly_totals[week_key]["disapproved"] += weekly_data.get(
                            "disapproved", 0
                        )
                        weekly_totals[week_key]["points"] += weekly_data.get(
                            "points", 0.0
                        )

                    # Aggregate monthly periods
                    for month_key, monthly_data in periods.get(
                        const.PERIOD_MONTHLY, {}
                    ).items():
                        monthly_totals[month_key]["claimed"] += monthly_data.get(
                            "claimed", 0
                        )
                        monthly_totals[month_key]["approved"] += monthly_data.get(
                            "approved", 0
                        )
                        monthly_totals[month_key]["disapproved"] += monthly_data.get(
                            "disapproved", 0
                        )
                        monthly_totals[month_key]["points"] += monthly_data.get(
                            "points", 0.0
                        )

                    # Aggregate yearly periods
                    for year_key, yearly_data in periods.get(
                        const.PERIOD_YEARLY, {}
                    ).items():
                        yearly_totals[year_key]["claimed"] += yearly_data.get(
                            "claimed", 0
                        )
                        yearly_totals[year_key]["approved"] += yearly_data.get(
                            "approved", 0
                        )
                        yearly_totals[year_key]["disapproved"] += yearly_data.get(
                            "disapproved", 0
                        )
                        yearly_totals[year_key]["points"] += yearly_data.get(
                            "points", 0.0
                        )

                # Store aggregated all_time bucket (nested: all_time.all_time for consistency)
                reward_periods[const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME] = {
                    const.PERIOD_ALL_TIME: {
                        "claimed": total_claimed,
                        "approved": total_approved,
                        "disapproved": total_disapproved,
                        "points": round(total_points, const.DATA_FLOAT_PRECISION),
                    }
                }

                # Store aggregated period buckets (convert defaultdict to dict)
                if daily_totals:
                    reward_periods[const.PERIOD_DAILY] = {
                        k: dict(v) for k, v in daily_totals.items()
                    }
                if weekly_totals:
                    reward_periods[const.PERIOD_WEEKLY] = {
                        k: dict(v) for k, v in weekly_totals.items()
                    }
                if monthly_totals:
                    reward_periods[const.PERIOD_MONTHLY] = {
                        k: dict(v) for k, v in monthly_totals.items()
                    }
                if yearly_totals:
                    reward_periods[const.PERIOD_YEARLY] = {
                        k: dict(v) for k, v in yearly_totals.items()
                    }

                backfilled_count += 1
                const.LOGGER.debug(
                    "Backfilled reward_periods for assignee '%s': "
                    "all_time(claimed=%d, approved=%d, disapproved=%d, points=%.2f), "
                    "daily=%d, weekly=%d, monthly=%d, yearly=%d",
                    assignee_name,
                    total_claimed,
                    total_approved,
                    total_disapproved,
                    total_points,
                    len(daily_totals),
                    len(weekly_totals),
                    len(monthly_totals),
                    len(yearly_totals),
                )

            # Step 2.5: Flatten malformed nested keys in reward_periods
            # Some legacy data may have nested keys like "2026-02-03": {"2026-02-03": {...}}
            # This flattens them to "2026-02-03": {"claimed": 3, ...}
            flattened_count = 0
            for period_type in [
                const.PERIOD_DAILY,
                const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY,
            ]:
                if period_type not in reward_periods:
                    continue

                period_bucket = reward_periods[period_type]
                for period_key, period_data in list(period_bucket.items()):
                    # Check if period_data has a nested key matching period_key
                    if isinstance(period_data, dict) and period_key in period_data:
                        # Extract the nested data and replace
                        nested_data = period_data[period_key]
                        if isinstance(nested_data, dict):
                            period_bucket[period_key] = nested_data
                            flattened_count += 1
                            const.LOGGER.debug(
                                "Flattened nested key '%s' in %s reward_periods for assignee '%s'",
                                period_key,
                                period_type,
                                assignee_name,
                            )

            if flattened_count > 0:
                const.LOGGER.info(
                    "Flattened %d malformed nested keys in reward_periods for assignee '%s'",
                    flattened_count,
                    assignee_name,
                )

            # Step 3: Remove total_* fields from each reward item
            reward_data = assignee_info.get(const.DATA_USER_REWARD_DATA, {})
            for _reward_id, reward_item in reward_data.items():
                # Step 3a: Flatten malformed nested keys in per-reward periods
                if const.DATA_USER_REWARD_DATA_PERIODS in reward_item:
                    periods = reward_item[const.DATA_USER_REWARD_DATA_PERIODS]
                    per_reward_flattened = 0
                    for period_type in [
                        const.PERIOD_DAILY,
                        const.PERIOD_WEEKLY,
                        const.PERIOD_MONTHLY,
                        const.PERIOD_YEARLY,
                    ]:
                        if period_type not in periods:
                            continue

                        period_bucket = periods[period_type]
                        for period_key, period_data in list(period_bucket.items()):
                            # Check if period_data has a nested key matching period_key
                            if (
                                isinstance(period_data, dict)
                                and period_key in period_data
                            ):
                                # Extract the nested data and replace
                                nested_data = period_data[period_key]
                                if isinstance(nested_data, dict):
                                    period_bucket[period_key] = nested_data
                                    per_reward_flattened += 1

                    if per_reward_flattened > 0:
                        const.LOGGER.debug(
                            "Flattened %d malformed nested keys in per-reward periods for reward %s, assignee '%s'",
                            per_reward_flattened,
                            _reward_id,
                            assignee_name,
                        )

                # Step 3b: Remove total_* fields
                removed_fields = []
                if const.DATA_USER_REWARD_DATA_TOTAL_CLAIMS in reward_item:
                    del reward_item[const.DATA_USER_REWARD_DATA_TOTAL_CLAIMS]
                    removed_fields.append("total_claims")
                    items_cleaned += 1
                if const.DATA_USER_REWARD_DATA_TOTAL_APPROVED in reward_item:
                    del reward_item[const.DATA_USER_REWARD_DATA_TOTAL_APPROVED]
                    removed_fields.append("total_approved")
                    items_cleaned += 1
                if const.DATA_USER_REWARD_DATA_TOTAL_DISAPPROVED in reward_item:
                    del reward_item[const.DATA_USER_REWARD_DATA_TOTAL_DISAPPROVED]
                    removed_fields.append("total_disapproved")
                    items_cleaned += 1
                if const.DATA_USER_REWARD_DATA_TOTAL_POINTS_SPENT in reward_item:
                    del reward_item[const.DATA_USER_REWARD_DATA_TOTAL_POINTS_SPENT]
                    removed_fields.append("total_points_spent")
                    items_cleaned += 1

                # Step 3c: Remove notification_ids (NotificationManager owns lifecycle)
                if "notification_ids" in reward_item:
                    del reward_item["notification_ids"]
                    removed_fields.append("notification_ids")
                    items_cleaned += 1

                if removed_fields:
                    const.LOGGER.debug(
                        "Cleaned reward item for assignee '%s': removed %s",
                        assignee_name,
                        ", ".join(removed_fields),
                    )

            # Step 4: Delete reward_stats dict (now fully ephemeral)
            if const.DATA_USER_REWARD_STATS in assignee_info:
                del assignee_info[const.DATA_USER_REWARD_STATS]
                stats_deleted += 1
                const.LOGGER.debug(
                    "Deleted reward_stats dict for assignee '%s' (%s)",
                    assignee_name,
                    assignee_id,
                )

        const.LOGGER.info(
            "Completed v43 reward_periods migration: "
            "%d assignees got reward_periods bucket, %d backfilled all_time, "
            "%d items cleaned (total_*/notification_ids), %d reward_stats deleted",
            assignees_migrated,
            backfilled_count,
            items_cleaned,
            stats_deleted,
        )

    def _migrate_bonus_penalty_periods_v43(self) -> None:
        """Transform assignee.bonus_applies and assignee.penalty_applies to dicts with periods (v43).

        Phase 4C: Bonus/Penalty Period Tracking
        - Transform assignee.bonus_applies from {bonus_id: count} to {bonus_id: {periods: {...}}}
        - Transform assignee.penalty_applies from {penalty_id: count} to {penalty_id: {periods: {...}}}
        - Backfill all_time.all_time from old integer counters
        - Periods structure: assignee.bonus_applies[bonus_id].periods.daily.2026-02-04

        This migration (Phase 12c):
        1. For each assignee, transform bonus_applies counters to dicts with periods
        2. For each assignee, transform penalty_applies counters to dicts with periods
        3. Backfill all_time.all_time bucket with historical count × points

        This migration is idempotent - safe to run multiple times.
        """
        const.LOGGER.info(
            "Starting v43 bonus/penalty periods migration: "
            "Transform assignee.bonus_applies and assignee.penalty_applies from counters to period dicts"
        )

        bonuses_data = self.coordinator._data.get(const.DATA_BONUSES, {})
        penalties_data = self.coordinator._data.get(const.DATA_PENALTIES, {})
        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        assignees_migrated = 0
        bonus_entries_transformed = 0
        penalty_entries_transformed = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id[:8])
            assignee_changed = False

            # Transform bonus_applies from integer counters to period dicts
            bonus_applies = assignee_info.get(const.DATA_USER_BONUS_APPLIES, {})
            for bonus_id, value in list(bonus_applies.items()):
                # Check if already migrated (dict with periods) or needs migration (integer)
                if isinstance(value, int):
                    # OLD FORMAT: integer count - transform to dict with periods
                    apply_count = value
                    bonus_info = bonuses_data.get(bonus_id)
                    if not bonus_info:
                        const.LOGGER.warning(
                            "Bonus %s not found in bonuses_data (assignee=%s), skipping",
                            bonus_id,
                            assignee_name,
                        )
                        continue

                    bonus_points = bonus_info.get(const.DATA_BONUS_POINTS, 0.0)
                    bonus_name = bonus_info.get(const.DATA_BONUS_NAME, "Unknown")

                    # Create new structure with periods
                    bonus_applies[bonus_id] = {
                        const.DATA_USER_BONUS_PERIODS: {
                            const.PERIOD_DAILY: {},
                            const.PERIOD_WEEKLY: {},
                            const.PERIOD_MONTHLY: {},
                            const.PERIOD_YEARLY: {},
                            const.PERIOD_ALL_TIME: {
                                const.PERIOD_ALL_TIME: {
                                    const.DATA_USER_BONUS_PERIOD_APPLIES: apply_count,
                                    const.DATA_USER_BONUS_PERIOD_POINTS: round(
                                        bonus_points * apply_count,
                                        const.DATA_FLOAT_PRECISION,
                                    ),
                                }
                            },
                        }
                    }
                    bonus_entries_transformed += 1
                    assignee_changed = True
                    const.LOGGER.debug(
                        "Transformed bonus '%s' for assignee '%s': %d applies → %.2f points",
                        bonus_name,
                        assignee_name,
                        apply_count,
                        bonus_points * apply_count,
                    )
                elif isinstance(value, dict):
                    # ALREADY MIGRATED: ensure all period types exist
                    periods = value.get(const.DATA_USER_BONUS_PERIODS, {})
                    for period_type in [
                        const.PERIOD_DAILY,
                        const.PERIOD_WEEKLY,
                        const.PERIOD_MONTHLY,
                        const.PERIOD_YEARLY,
                        const.PERIOD_ALL_TIME,
                    ]:
                        if period_type not in periods:
                            periods[period_type] = {}
                            assignee_changed = True

            # Transform penalty_applies from integer counters to period dicts
            penalty_applies = assignee_info.get(const.DATA_USER_PENALTY_APPLIES, {})
            for penalty_id, value in list(penalty_applies.items()):
                # Check if already migrated (dict with periods) or needs migration (integer)
                if isinstance(value, int):
                    # OLD FORMAT: integer count - transform to dict with periods
                    apply_count = value
                    penalty_info = penalties_data.get(penalty_id)
                    if not penalty_info:
                        const.LOGGER.warning(
                            "Penalty %s not found in penalties_data (assignee=%s), skipping",
                            penalty_id,
                            assignee_name,
                        )
                        continue

                    penalty_points = penalty_info.get(const.DATA_PENALTY_POINTS, 0.0)
                    penalty_name = penalty_info.get(const.DATA_PENALTY_NAME, "Unknown")

                    # Create new structure with periods
                    penalty_applies[penalty_id] = {
                        const.DATA_USER_PENALTY_PERIODS: {
                            const.PERIOD_DAILY: {},
                            const.PERIOD_WEEKLY: {},
                            const.PERIOD_MONTHLY: {},
                            const.PERIOD_YEARLY: {},
                            const.PERIOD_ALL_TIME: {
                                const.PERIOD_ALL_TIME: {
                                    const.DATA_USER_PENALTY_PERIOD_APPLIES: apply_count,
                                    const.DATA_USER_PENALTY_PERIOD_POINTS: round(
                                        penalty_points * apply_count,
                                        const.DATA_FLOAT_PRECISION,
                                    ),
                                }
                            },
                        }
                    }
                    penalty_entries_transformed += 1
                    assignee_changed = True
                    const.LOGGER.debug(
                        "Transformed penalty '%s' for assignee '%s': %d applies → %.2f points",
                        penalty_name,
                        assignee_name,
                        apply_count,
                        penalty_points * apply_count,
                    )
                elif isinstance(value, dict):
                    # ALREADY MIGRATED: ensure all period types exist
                    periods = value.get(const.DATA_USER_PENALTY_PERIODS, {})
                    for period_type in [
                        const.PERIOD_DAILY,
                        const.PERIOD_WEEKLY,
                        const.PERIOD_MONTHLY,
                        const.PERIOD_YEARLY,
                        const.PERIOD_ALL_TIME,
                    ]:
                        if period_type not in periods:
                            periods[period_type] = {}
                            assignee_changed = True

            if assignee_changed:
                assignees_migrated += 1

        const.LOGGER.info(
            "Completed v43 bonus/penalty periods migration: "
            "%d assignees processed, %d bonus entries transformed, %d penalty entries transformed",
            assignees_migrated,
            bonus_entries_transformed,
            penalty_entries_transformed,
        )

    def _transform_period_entry(
        self, data: dict[str, Any], is_all_time: bool = False
    ) -> dict[str, Any]:
        """Transform a single period entry from v42 → v43 format.

        Args:
            data: v42 period entry with points_total and by_source
            is_all_time: If True, skip earned/spent calculation (handled specially)

        Returns:
            v43 period entry with points_earned, points_spent, and by_source
        """
        # Remove deprecated points_total (v42 field)
        data.pop(const.DATA_ASSIGNEE_POINT_DATA_PERIOD_POINTS_TOTAL_LEGACY, None)

        if not is_all_time:
            # For temporal periods: Calculate earned/spent from by_source
            by_source = data.get(const.DATA_USER_POINT_PERIOD_BY_SOURCE, {})
            points_earned = sum(v for v in by_source.values() if v > 0)
            points_spent = sum(v for v in by_source.values() if v < 0)

            # Add new fields
            data[const.DATA_USER_POINT_PERIOD_POINTS_EARNED] = points_earned
            data[const.DATA_USER_POINT_PERIOD_POINTS_SPENT] = points_spent
        # else: all_time earned/spent set specially based on highest_balance

        return data

    def _finalize_migration_meta(self) -> None:
        """Set up v50+ meta section and clean legacy keys.

        This MUST run at the end of all migrations because:
        1. Schema version should only be updated after ALL migrations succeed
        2. Legacy keys might be needed during migration (safety)

        This method will be REMOVED when migration_pre_v50.py is dropped.
        """
        from homeassistant.util import dt as dt_util

        # Set modern meta section
        self.coordinator._data[const.DATA_META] = {
            const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
            const.DATA_META_LAST_MIGRATION_DATE: datetime.now(dt_util.UTC).isoformat(),
            const.DATA_META_MIGRATIONS_APPLIED: const.DEFAULT_MIGRATIONS_APPLIED,
            const.DATA_META_PENDING_EVALUATIONS: [],
        }

        # Remove old top-level schema_version if present (v42 → v50)
        self.coordinator._data.pop(const.DATA_SCHEMA_VERSION, None)

        # Hard-fork cleanup: approvers bucket is legacy-only and must not persist
        # beyond migration. User role records are canonical in DATA_USERS.
        self.coordinator._data.pop(const.DATA_APPROVERS, None)

        # Clean up legacy beta keys (KC 4.x beta, schema v41)
        if LEGACY_MIGRATION_PERFORMED_KEY in self.coordinator._data:
            const.LOGGER.debug("Cleaning up legacy key: migration_performed")
            del self.coordinator._data[LEGACY_MIGRATION_PERFORMED_KEY]
        if LEGACY_MIGRATION_KEY_VERSION_KEY in self.coordinator._data:
            const.LOGGER.debug("Cleaning up legacy key: migration_key_version")
            del self.coordinator._data[LEGACY_MIGRATION_KEY_VERSION_KEY]

        const.LOGGER.debug(
            "Migration meta finalized: schema_version=%s",
            const.SCHEMA_VERSION_STORAGE_ONLY,
        )

    def _migrate_independent_chores(self) -> None:
        """Populate per_assignee_due_dates for all INDEPENDENT chores (one-time migration).

        For each INDEPENDENT chore, populate per_assignee_due_dates with template values
        for all assigned assignees. SHARED chores don't need per-assignee structure.
        This is a one-time migration during upgrade to v42+ schema.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        for chore_info in chores_data.values():
            # Ensure completion_criteria is set by reading legacy shared_chore field
            if const.DATA_CHORE_COMPLETION_CRITERIA not in chore_info:
                # Read legacy shared_chore boolean to determine criteria
                # Default to False (INDEPENDENT) for backward compatibility
                shared_chore = chore_info.get(
                    const.DATA_CHORE_SHARED_CHORE_LEGACY, False
                )
                if shared_chore:
                    chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
                        const.COMPLETION_CRITERIA_SHARED
                    )
                else:
                    chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
                        const.COMPLETION_CRITERIA_INDEPENDENT
                    )
                const.LOGGER.debug(
                    "Migrated chore '%s' from shared_chore=%s to completion_criteria=%s",
                    chore_info.get(const.DATA_CHORE_NAME),
                    shared_chore,
                    chore_info[const.DATA_CHORE_COMPLETION_CRITERIA],
                )

            # Remove legacy shared_chore field after migration
            if const.DATA_CHORE_SHARED_CHORE_LEGACY in chore_info:
                del chore_info[const.DATA_CHORE_SHARED_CHORE_LEGACY]
                const.LOGGER.debug(
                    "Removed legacy shared_chore field from chore '%s'",
                    chore_info.get(const.DATA_CHORE_NAME),
                )

            # For SHARED chores, no per_assignee_due_dates needed
            # For INDEPENDENT chores, populate per_assignee_due_dates if missing
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                if const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES not in chore_info:
                    template_due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)
                    assigned_assignees = chore_info.get(
                        const.DATA_CHORE_ASSIGNED_USER_IDS, []
                    )
                    chore_info[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = dict.fromkeys(
                        assigned_assignees, template_due_date
                    )
                    const.LOGGER.debug(
                        "Migrated INDEPENDENT chore '%s' with per-assignee dates",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

                # Clean up legacy chore-level due_date for INDEPENDENT chores
                # The authoritative due_date is now per-assignee in assignee_chore_data
                if const.DATA_CHORE_DUE_DATE in chore_info:
                    del chore_info[const.DATA_CHORE_DUE_DATE]
                    const.LOGGER.debug(
                        "Removed legacy chore-level due_date from INDEPENDENT chore '%s'",
                        chore_info.get(const.DATA_CHORE_NAME),
                    )

    def _migrate_per_assignee_applicable_days(self) -> None:
        """Populate per_assignee_applicable_days for INDEPENDENT chores (one-time migration).

        For each INDEPENDENT chore with chore-level applicable_days:
        1. Create per_assignee_applicable_days with same value for all assigned assignees
        2. Clear chore-level applicable_days to None

        Empty list means "all days applicable" (not "never scheduled").
        SHARED chores keep chore-level applicable_days unchanged.

        PKAD-2026-001: Per-assignee applicable days feature migration.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        migrated_count = 0

        for _chore_id, chore_info in chores_data.items():
            # Only INDEPENDENT chores need per-assignee migration
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                != const.COMPLETION_CRITERIA_INDEPENDENT
            ):
                continue

            # Skip if per_assignee_applicable_days already exists
            if const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS in chore_info:
                continue

            # Get template from chore-level applicable_days
            template_days = chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
            assigned_assignees = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])

            # Populate per-assignee structure (copy list for each assignee)
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS] = {
                assignee_id: template_days[:] if template_days else []
                for assignee_id in assigned_assignees
            }

            # Clear chore-level applicable_days (single source of truth)
            if const.DATA_CHORE_APPLICABLE_DAYS in chore_info:
                del chore_info[const.DATA_CHORE_APPLICABLE_DAYS]

            migrated_count += 1
            const.LOGGER.debug(
                "Migrated INDEPENDENT chore '%s' with per-assignee applicable_days",
                chore_info.get(const.DATA_CHORE_NAME),
            )

        if migrated_count > 0:
            const.LOGGER.info(
                "Migrated %d INDEPENDENT chores to per-assignee applicable_days",
                migrated_count,
            )

    def _migrate_approval_reset_type(self) -> None:
        """Migrate allow_multiple_claims_per_day boolean to approval_reset_type enum.

        Conversion:
        - allow_multiple_claims_per_day=True  → approval_reset_type=AT_MIDNIGHT_MULTI
        - allow_multiple_claims_per_day=False → approval_reset_type=AT_MIDNIGHT_ONCE
        - Missing field → approval_reset_type=AT_MIDNIGHT_ONCE (default)

        After migration, the deprecated field is removed from chore data.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        migrated_count = 0

        for chore_id, chore_info in chores_data.items():
            # Skip if already migrated (has approval_reset_type)
            if const.DATA_CHORE_APPROVAL_RESET_TYPE in chore_info:
                continue

            # Read legacy boolean field
            allow_multiple = chore_info.get(
                const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY, False
            )

            # Convert to new enum value
            if allow_multiple:
                new_value = const.APPROVAL_RESET_AT_MIDNIGHT_MULTI
            else:
                new_value = const.APPROVAL_RESET_AT_MIDNIGHT_ONCE

            chore_info[const.DATA_CHORE_APPROVAL_RESET_TYPE] = new_value
            migrated_count += 1

            const.LOGGER.debug(
                "Migrated chore '%s' (%s): allow_multiple=%s → approval_reset_type=%s",
                chore_info.get(const.DATA_CHORE_NAME),
                chore_id,
                allow_multiple,
                new_value,
            )

            # Remove deprecated field after migration
            if const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY in chore_info:
                del chore_info[const.DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY]

        if migrated_count > 0:
            const.LOGGER.info(
                "Migrated %s chores from allow_multiple_claims_per_day to approval_reset_type",
                migrated_count,
            )

    def _migrate_to_timestamp_tracking(self) -> None:
        """Migrate from list-based to timestamp-based chore claim/approval tracking.

        This migration:
        1. Initializes approval_period_start for INDEPENDENT chores (per-assignee in assignee_chore_data)
        2. Initializes approval_period_start for SHARED chores (at chore level)
        3. DELETES deprecated claimed_chores and approved_chores lists from assignee data

        The new timestamp-based system uses:
        - last_claimed_time: When assignee last claimed the chore
        - last_approved_time: When assignee's claim was last approved
        - approval_period_start: Start of current approval window (reset changes this)

        Note: The deprecated lists are deleted because v0.4.0 uses timestamp-only tracking.
        """
        from homeassistant.util import dt as dt_util

        now_utc_iso = datetime.now(dt_util.UTC).isoformat()
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})

        # Phase 1: Initialize approval_period_start for chores
        chores_migrated = 0
        for chore_id, chore_info in chores_data.items():
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )

            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                # INDEPENDENT chores: Initialize per-assignee approval_period_start in assignee_chore_data
                assigned_assignees = chore_info.get(
                    const.DATA_CHORE_ASSIGNED_USER_IDS, []
                )
                for assignee_id in assigned_assignees:
                    assignee_info = assignees_data.get(assignee_id)
                    if not assignee_info:
                        continue

                    # Ensure assignee_chore_data structure exists
                    if const.DATA_USER_CHORE_DATA not in assignee_info:
                        assignee_info[const.DATA_USER_CHORE_DATA] = {}
                    assignee_chore_data = assignee_info[const.DATA_USER_CHORE_DATA]

                    # Ensure chore_tracking entry exists for this chore
                    if chore_id not in assignee_chore_data:
                        assignee_chore_data[chore_id] = {}
                    chore_tracking = assignee_chore_data[chore_id]

                    # Only initialize if not already set
                    if (
                        const.DATA_USER_CHORE_DATA_APPROVAL_PERIOD_START
                        not in chore_tracking
                    ):
                        chore_tracking[
                            const.DATA_USER_CHORE_DATA_APPROVAL_PERIOD_START
                        ] = now_utc_iso
                        chores_migrated += 1
            # SHARED/SHARED_FIRST chores: Initialize approval_period_start at chore level
            elif const.DATA_CHORE_APPROVAL_PERIOD_START not in chore_info:
                chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_utc_iso
                chores_migrated += 1

        # Phase 2: DELETE deprecated lists from assignee data
        assignees_cleaned = 0
        deprecated_keys = [
            const.DATA_ASSIGNEE_CLAIMED_CHORES_LEGACY,
            const.DATA_ASSIGNEE_APPROVED_CHORES_LEGACY,
        ]

        for assignee_id, assignee_info in assignees_data.items():
            removed_any = False
            for key in deprecated_keys:
                if key in assignee_info:
                    del assignee_info[key]
                    removed_any = True

            if removed_any:
                assignees_cleaned += 1
                const.LOGGER.debug(
                    "Removed deprecated claim/approval lists from assignee '%s' (%s)",
                    assignee_info.get(const.DATA_USER_NAME),
                    assignee_id,
                )

        if chores_migrated > 0 or assignees_cleaned > 0:
            const.LOGGER.info(
                "Timestamp tracking migration: initialized %s chore periods, "
                "cleaned deprecated lists from %s assignees",
                chores_migrated,
                assignees_cleaned,
            )

    def _migrate_datetime(self, dt_str: str) -> str:
        """Convert a datetime string to a UTC-aware ISO string.

        Args:
            dt_str: The datetime string to convert.

        Returns:
            UTC-aware ISO format datetime string, or original string if conversion fails.
        """
        if not isinstance(dt_str, str):
            return dt_str

        try:
            dt_obj_utc = dt_to_utc(dt_str)
            if dt_obj_utc:
                return dt_obj_utc.isoformat()
            raise ValueError("Parsed datetime is None")
        except (ValueError, TypeError, AttributeError) as err:
            const.LOGGER.warning(
                "WARNING: Migrate DateTime - Error migrating datetime '%s': %s",
                dt_str,
                err,
            )
            return dt_str

    def _migrate_datetime_wrapper(self) -> None:
        """Wrapper to expose datetime migration as standalone step."""
        # This is a no-op in the context of run_all_migrations since datetime
        # conversion is called by _migrate_stored_datetimes

    def _migrate_stored_datetimes(self) -> None:
        """Walk through stored data and convert known datetime fields to UTC-aware ISO strings."""
        # For each chore, migrate due_date, last_completed, and last_claimed
        for chore_info in self.coordinator._data.get(const.DATA_CHORES, {}).values():
            if chore_info.get(const.DATA_CHORE_DUE_DATE):
                chore_info[const.DATA_CHORE_DUE_DATE] = self._migrate_datetime(
                    chore_info[const.DATA_CHORE_DUE_DATE]
                )
            if chore_info.get(const.DATA_CHORE_LAST_COMPLETED):
                chore_info[const.DATA_CHORE_LAST_COMPLETED] = self._migrate_datetime(
                    chore_info[const.DATA_CHORE_LAST_COMPLETED]
                )
            if chore_info.get(const.DATA_CHORE_LAST_CLAIMED):
                chore_info[const.DATA_CHORE_LAST_CLAIMED] = self._migrate_datetime(
                    chore_info[const.DATA_CHORE_LAST_CLAIMED]
                )
        # v0.4.0: Remove chore queue - now computed from timestamps
        # (skip timestamp migration, just delete the key)
        self.coordinator._data.pop(const.DATA_PENDING_CHORE_APPROVALS_LEGACY, None)

        # Migrate timestamps in pending REWARD approvals before deletion
        # These may contain historical approval data with timestamps that need proper format
        for approval in self.coordinator._data.get(
            const.DATA_PENDING_REWARD_APPROVALS_LEGACY, []
        ):
            if approval.get(const.DATA_CHORE_TIMESTAMP):
                approval[const.DATA_CHORE_TIMESTAMP] = self._migrate_datetime(
                    approval[const.DATA_CHORE_TIMESTAMP]
                )

        # v0.4.0: Remove reward queue - also now computed from per-assignee reward_data
        # After migration, delete the legacy key since approvals are computed dynamically
        self.coordinator._data.pop(const.DATA_PENDING_REWARD_APPROVALS_LEGACY, None)

        # pre-v0.5.0: Remove orphaned linked_users key from early development
        # Feature was never implemented in production, clean up any test/dev data
        self.coordinator._data.pop(const.DATA_LINKED_USERS_LEGACY, None)

        # Migrate datetime on Challenges
        for challenge_info in self.coordinator._data.get(
            const.DATA_CHALLENGES, {}
        ).values():
            start_date = challenge_info.get(const.DATA_CHALLENGE_START_DATE)
            if not isinstance(start_date, str) or not start_date.strip():
                challenge_info[const.DATA_CHALLENGE_START_DATE] = None
            else:
                challenge_info[const.DATA_CHALLENGE_START_DATE] = (
                    self._migrate_datetime(start_date)
                )

            end_date = challenge_info.get(const.DATA_CHALLENGE_END_DATE)
            if not isinstance(end_date, str) or not end_date.strip():
                challenge_info[const.DATA_CHALLENGE_END_DATE] = None
            else:
                challenge_info[const.DATA_CHALLENGE_END_DATE] = self._migrate_datetime(
                    end_date
                )

    def _migrate_chore_data(self) -> None:
        """Migrate each chore's data to include new fields if missing."""
        chores = self.coordinator._data.get(const.DATA_CHORES, {})
        for chore_info in chores.values():
            chore_info.setdefault(
                const.CONF_APPLICABLE_DAYS_LEGACY, const.DEFAULT_APPLICABLE_DAYS
            )
            chore_info.setdefault(
                const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
            )
            chore_info.setdefault(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            )
            chore_info.setdefault(
                const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
            )
            # Remove legacy partial_allowed field (unused stub)
            chore_info.pop(const.DATA_CHORE_PARTIAL_ALLOWED_LEGACY, None)
            # Remove obsolete fields from pre-v0.5.0 (never used in v0.5.0+)
            chore_info.pop(const.DATA_CHORE_ASSIGNED_TO_LEGACY, None)
            chore_info.pop(const.DATA_CHORE_LAST_OVERDUE_NOTIFICATION_LEGACY, None)
        const.LOGGER.info("Chore data migration complete.")

    def _migrate_assignee_data(self) -> None:
        """Migrate each assignee's data to include new fields if missing."""
        assignees = self.coordinator._data.get(const.DATA_USERS, {})
        migrated_count = 0
        for assignee_id, assignee_info in assignees.items():
            # Remove dead overdue_notifications field (never populated, superseded by
            # DATA_NOTIFICATIONS bucket with DATA_NOTIF_LAST_OVERDUE for dedup)
            if const.DATA_ASSIGNEE_OVERDUE_NOTIFICATIONS_LEGACY in assignee_info:
                assignee_info.pop(const.DATA_ASSIGNEE_OVERDUE_NOTIFICATIONS_LEGACY)
                const.LOGGER.debug(
                    "DEBUG: Removed dead overdue_notifications field from assignee '%s'",
                    assignee_id,
                )
            # Ensure cumulative_badge_progress exists (initialized empty, populated later)
            if const.DATA_USER_CUMULATIVE_BADGE_PROGRESS not in assignee_info:
                assignee_info[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS] = {}
                const.LOGGER.debug(
                    "DEBUG: Added cumulative_badge_progress field to assignee '%s'",
                    assignee_id,
                )
        const.LOGGER.info(
            "INFO: Assignee data migration complete. Migrated %s assignees.",
            migrated_count,
        )

    def _migrate_legacy_assignee_chore_data_and_streaks(self) -> None:
        """Migrate legacy streak and stats data to the new assignee chores structure (period-based).

        This function will automatically run through all assignees and all assigned chores.
        Data that only needs to be migrated once per assignee is handled separately from per-chore data.
        """
        for assignee_id, assignee_info in self.coordinator.assignees_data.items():
            # --- Per-assignee migration (run once per assignee) ---
            # Only migrate these once per assignee, not per chore
            chore_stats = assignee_info.setdefault(
                const.DATA_ASSIGNEE_CHORE_STATS_LEGACY, {}
            )
            legacy_streaks = assignee_info.get(
                const.DATA_ASSIGNEE_CHORE_STREAKS_LEGACY, {}
            )
            legacy_max = 0
            last_longest_streak_date = None

            # Find the max streak and last date across all chores for this assignee
            for _chore_id, legacy_streak in legacy_streaks.items():  # type: ignore[attr-defined]
                max_streak = legacy_streak.get(const.DATA_ASSIGNEE_MAX_STREAK_LEGACY, 0)
                if max_streak > legacy_max:
                    legacy_max = max_streak
                    last_longest_streak_date = legacy_streak.get(
                        const.DATA_USER_LAST_STREAK_DATE
                    )

            if legacy_max > chore_stats.get(
                const.DATA_ASSIGNEE_CHORE_STATS_LONGEST_STREAK_ALL_TIME_LEGACY, 0
            ):
                chore_stats[
                    const.DATA_ASSIGNEE_CHORE_STATS_LONGEST_STREAK_ALL_TIME_LEGACY
                ] = legacy_max
                # Store the date on any one chore (will be set per-chore below as well)
                if last_longest_streak_date:
                    for chore_data in assignee_info.get(
                        const.DATA_USER_CHORE_DATA, {}
                    ).values():
                        chore_data[
                            const.DATA_USER_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME
                        ] = last_longest_streak_date

            # Migrate all-time completed count from legacy (once per assignee)
            # Note: approved_year is NOT set here - it's derived from period buckets
            # (see line ~1008 where legacy approvals populate periods.yearly.approved)
            chore_stats[const.DATA_ASSIGNEE_CHORE_STATS_APPROVED_ALL_TIME_LEGACY] = (
                assignee_info.get(const.DATA_ASSIGNEE_COMPLETED_CHORES_TOTAL_LEGACY, 0)
            )

            # Migrate all-time claimed count from legacy (use max of any chore's claims or completed_chores_total)
            legacy_claim_map = cast(
                "dict[str, int]",
                assignee_info.get(const.DATA_ASSIGNEE_CHORE_CLAIMS_LEGACY, {}),
            )
            all_claims = [
                legacy_claim_map.get(chore_id, 0)
                for chore_id in self.coordinator.chores_data
            ]
            completed_total_raw = assignee_info.get(
                const.DATA_ASSIGNEE_COMPLETED_CHORES_TOTAL_LEGACY,
                0,
            )
            completed_total = (
                int(completed_total_raw)
                if isinstance(completed_total_raw, int | float)
                else 0
            )
            all_claims.append(completed_total)
            chore_stats[const.DATA_ASSIGNEE_CHORE_STATS_CLAIMED_ALL_TIME_LEGACY] = (
                max(all_claims) if all_claims else 0
            )

            # --- Per-chore migration (run for each assigned chore) ---
            for chore_id, chore_info in self.coordinator.chores_data.items():
                assigned_assignees = chore_info.get(
                    const.DATA_CHORE_ASSIGNED_USER_IDS, []
                )
                if assigned_assignees and assignee_id not in assigned_assignees:
                    continue

                # Ensure new structure exists
                if const.DATA_USER_CHORE_DATA not in assignee_info:
                    assignee_info[const.DATA_USER_CHORE_DATA] = {}

                chore_data_dict = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
                if chore_id not in chore_data_dict:
                    chore_name = chore_info.get(const.DATA_CHORE_NAME, chore_id)
                    chore_data_dict[chore_id] = {
                        const.DATA_USER_CHORE_DATA_NAME: chore_name,
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
                        const.DATA_USER_CHORE_DATA_LAST_CLAIMED: None,
                        const.DATA_USER_CHORE_DATA_LAST_APPROVED: None,
                        const.DATA_USER_CHORE_DATA_LAST_DISAPPROVED: None,
                        const.DATA_USER_CHORE_DATA_LAST_OVERDUE: None,
                        const.DATA_USER_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME: None,
                        const.DATA_USER_CHORE_DATA_PERIODS: {
                            const.DATA_USER_CHORE_DATA_PERIODS_DAILY: {},
                            const.DATA_USER_CHORE_DATA_PERIODS_WEEKLY: {},
                            const.DATA_USER_CHORE_DATA_PERIODS_MONTHLY: {},
                            const.DATA_USER_CHORE_DATA_PERIODS_YEARLY: {},
                            const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME: {},
                        },
                        const.DATA_USER_CHORE_DATA_BADGE_REFS: [],
                    }

                assignee_chore_data = chore_data_dict[chore_id]

                # Ensure pending_claim_count exists for existing records (added in v42)
                if (
                    const.DATA_USER_CHORE_DATA_PENDING_CLAIM_COUNT
                    not in assignee_chore_data
                ):
                    assignee_chore_data[
                        const.DATA_USER_CHORE_DATA_PENDING_CLAIM_COUNT
                    ] = 0

                periods = assignee_chore_data[const.DATA_USER_CHORE_DATA_PERIODS]

                # --- Migrate legacy current streaks for this chore ---
                legacy_streak = legacy_streaks.get(chore_id, {})  # type: ignore[attr-defined]
                last_date = legacy_streak.get(const.DATA_USER_LAST_STREAK_DATE)
                if last_date:
                    # Daily
                    daily_data = periods[
                        const.DATA_USER_CHORE_DATA_PERIODS_DAILY
                    ].setdefault(
                        last_date,
                        {
                            const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                            const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                            const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                            const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                            const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                            const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY: 0,
                        },
                    )
                    daily_data[const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY] = (
                        legacy_streak.get(const.DATA_USER_CURRENT_STREAK, 0)
                    )

                # Handle all_time separately for longest_streak (not streak_tally)
                # all_time uses nested structure: periods["all_time"]["all_time"] = {data}
                all_time_container = periods[
                    const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME
                ].setdefault(const.PERIOD_ALL_TIME, {})
                if (
                    const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK
                    not in all_time_container
                ):
                    all_time_container[
                        const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK
                    ] = legacy_streak.get(const.DATA_ASSIGNEE_MAX_STREAK_LEGACY, 0)

                # Weekly/monthly/yearly DON'T get streak fields
                for period_key, period_fmt in [
                    (const.DATA_USER_CHORE_DATA_PERIODS_WEEKLY, "%Y-W%V"),
                    (const.DATA_USER_CHORE_DATA_PERIODS_MONTHLY, "%Y-%m"),
                    (const.DATA_USER_CHORE_DATA_PERIODS_YEARLY, "%Y"),
                ]:
                    if last_date:
                        try:
                            dt = datetime.fromisoformat(last_date)
                            period_id = dt.strftime(period_fmt)
                        except (ValueError, TypeError):
                            period_id = None
                    else:
                        period_id = None

                    if period_id:
                        periods[period_key].setdefault(
                            period_id,
                            {
                                const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                                const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                                const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                                const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                                const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                            },
                        )

                # --- Migrate claim/approval counts for this chore ---
                claims = assignee_info.get(
                    const.DATA_ASSIGNEE_CHORE_CLAIMS_LEGACY, {}
                ).get(  # type: ignore[attr-defined]
                    chore_id, 0
                )
                approvals = assignee_info.get(
                    const.DATA_ASSIGNEE_CHORE_APPROVALS_LEGACY, {}
                ).get(  # type: ignore[attr-defined]
                    chore_id, 0
                )

                # --- Migrate period completion and claim counts for this chore ---
                now_local = dt_now_local()
                today_iso = now_local.date().isoformat()
                week_iso = now_local.strftime("%Y-W%V")
                month_iso = now_local.strftime("%Y-%m")
                year_iso = now_local.strftime("%Y")

                # Daily
                daily_data = periods[
                    const.DATA_USER_CHORE_DATA_PERIODS_DAILY
                ].setdefault(
                    today_iso,
                    {
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY: 0,
                    },
                )
                # No per chore data available for daily period

                # Weekly
                _weekly_stats = periods[
                    const.DATA_USER_CHORE_DATA_PERIODS_WEEKLY
                ].setdefault(
                    week_iso,
                    {
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                    },
                )
                # No per chore data available for weekly period

                # Monthly
                _monthly_stats = periods[
                    const.DATA_USER_CHORE_DATA_PERIODS_MONTHLY
                ].setdefault(
                    month_iso,
                    {
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                    },
                )
                # No per chore data available for monthly period

                # Yearly - create empty bucket for current year (legacy totals go to all_time only)
                # Don't populate yearly with legacy totals - they span multiple years
                periods[const.DATA_USER_CHORE_DATA_PERIODS_YEARLY].setdefault(
                    year_iso,
                    {
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED: 0,
                    },
                )

                # --- Migrate legacy all-time stats into the new all_time period for this chore ---
                all_time_data = periods[
                    const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME
                ].setdefault(
                    const.PERIOD_ALL_TIME,
                    {
                        const.DATA_USER_CHORE_DATA_PERIOD_APPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS: 0.0,
                        const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_OVERDUE: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK: 0,
                        const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED: 0,
                    },
                )

                # Map legacy totals to all time data
                all_time_data[const.DATA_USER_CHORE_DATA_PERIOD_APPROVED] = approvals
                all_time_data[const.DATA_USER_CHORE_DATA_PERIOD_CLAIMED] = claims
                # Backfill completed = approved (wasn't tracked historically)
                all_time_data[const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED] = approvals

                # Calculate points from approvals × default_points
                chore_info = self.coordinator._data.get(const.DATA_CHORES, {}).get(
                    chore_id, {}
                )
                default_points = chore_info.get(
                    const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
                )
                try:
                    estimated_points = float(approvals) * float(default_points)
                except (ValueError, TypeError):
                    estimated_points = 0.0
                all_time_data[const.DATA_USER_CHORE_DATA_PERIOD_POINTS] = round(
                    estimated_points, const.DATA_FLOAT_PRECISION
                )

    def _migrate_badges(self) -> None:
        """Migrate legacy badges into cumulative badges and ensure all required fields exist.

        For badges whose threshold_type is set to the legacy value (e.g. BADGE_THRESHOLD_TYPE_CHORE_COUNT),
        compute the new threshold as the legacy count multiplied by the average default points across all chores.
        Also, set reset fields to empty and disable periodic resets.
        For any badge, ensure all required fields and nested structures exist using constants.
        """
        badges_dict = self.coordinator._data.get(const.DATA_BADGES, {})
        chores_dict = self.coordinator._data.get(const.DATA_CHORES, {})

        # Calculate the average default points over all chores.
        total_points = 0.0
        count = 0
        for chore_info in chores_dict.values():
            try:
                default_points = float(
                    chore_info.get(
                        const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
                    )
                )
                total_points += default_points
                count += 1
            except (ValueError, TypeError, KeyError):
                continue

        # If there are no chores, we fallback to DEFAULT_POINTS.
        average_points = (total_points / count) if count > 0 else const.DEFAULT_POINTS

        # Process each badge.
        for badge_info in badges_dict.values():
            # --- Legacy migration logic ---
            if badge_info.get(const.DATA_BADGE_TYPE) == const.BADGE_TYPE_CUMULATIVE:
                # If the badge is already moved to cumulative, skip legacy migration.
                pass
            else:
                # Check if the badge uses the legacy "chore_count" threshold type if so estimate points and assign.
                if (
                    badge_info.get(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY)
                    == const.BADGE_THRESHOLD_TYPE_CHORE_COUNT
                ):
                    old_threshold = badge_info.get(
                        const.DATA_BADGE_THRESHOLD_VALUE_LEGACY,
                        const.DEFAULT_BADGE_THRESHOLD_VALUE_LEGACY,
                    )
                    try:
                        # Multiply the legacy count by the average default points.
                        new_threshold = float(old_threshold) * average_points
                    except (ValueError, TypeError):
                        new_threshold = old_threshold

                    # Force to points type and set new value
                    badge_info[const.DATA_BADGE_THRESHOLD_TYPE_LEGACY] = (
                        const.CONF_POINTS_LEGACY
                    )
                    badge_info[const.DATA_BADGE_THRESHOLD_VALUE_LEGACY] = new_threshold

                    # Also update the target structure immediately
                    badge_info.setdefault(const.DATA_BADGE_TARGET, {})
                    badge_info[const.DATA_BADGE_TARGET][
                        const.DATA_BADGE_TARGET_TYPE
                    ] = const.CONF_POINTS_LEGACY
                    badge_info[const.DATA_BADGE_TARGET][
                        const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                    ] = new_threshold

                    const.LOGGER.info(
                        "INFO: Legacy Chore Count Badge '%s' migrated: Old threshold %s -> New threshold %s (average_points=%.2f)",
                        badge_info.get(const.DATA_BADGE_NAME),
                        old_threshold,
                        new_threshold,
                        average_points,
                    )

                    # Remove legacy fields now so they can't overwrite later
                    badge_info.pop(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY, None)
                    badge_info.pop(const.DATA_BADGE_THRESHOLD_VALUE_LEGACY, None)

                # Set badge type to cumulative if not already set
                if const.DATA_BADGE_TYPE not in badge_info:
                    badge_info[const.DATA_BADGE_TYPE] = const.BADGE_TYPE_CUMULATIVE

            # --- Ensure all required fields and nested structures exist using constants ---

            # assigned_user_ids: Historically unassigned badges (missing or empty)
            # applied to ALL assignees
            if (
                const.DATA_BADGE_ASSIGNED_USER_IDS not in badge_info
                or not badge_info[const.DATA_BADGE_ASSIGNED_USER_IDS]
            ):
                # Get all assignee IDs from the assignees dictionary
                all_assignee_ids = list(
                    self.coordinator._data.get(const.DATA_USERS, {}).keys()
                )
                badge_info[const.DATA_BADGE_ASSIGNED_USER_IDS] = all_assignee_ids
                const.LOGGER.info(
                    "Badge '%s' had no/empty assigned_user_ids field - assigned to all %d assignees",
                    badge_info.get(const.DATA_BADGE_NAME, "unknown"),
                    len(all_assignee_ids),
                )

            # reset_schedule
            if const.DATA_BADGE_RESET_SCHEDULE not in badge_info:
                badge_info[const.DATA_BADGE_RESET_SCHEDULE] = {
                    const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: const.FREQUENCY_NONE,
                    const.DATA_BADGE_RESET_SCHEDULE_START_DATE: None,
                    const.DATA_BADGE_RESET_SCHEDULE_END_DATE: None,
                    const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: 0,
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: None,
                    const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: None,
                }

            # awards
            if const.DATA_BADGE_AWARDS not in badge_info or not isinstance(
                badge_info[const.DATA_BADGE_AWARDS], dict
            ):
                badge_info[const.DATA_BADGE_AWARDS] = {}
            # Preserve existing award_items if present, otherwise default to multiplier
            # (multiplier was the only award type in the original badges before award_items existed)
            if (
                const.DATA_BADGE_AWARDS_AWARD_ITEMS
                not in badge_info[const.DATA_BADGE_AWARDS]
            ):
                badge_info[const.DATA_BADGE_AWARDS][
                    const.DATA_BADGE_AWARDS_AWARD_ITEMS
                ] = [const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER]
            badge_info[const.DATA_BADGE_AWARDS].setdefault(
                const.DATA_BADGE_AWARDS_AWARD_POINTS, 0
            )
            badge_info[const.DATA_BADGE_AWARDS].setdefault(
                const.DATA_BADGE_AWARDS_AWARD_REWARD, ""
            )
            badge_info[const.DATA_BADGE_AWARDS].setdefault(
                const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                badge_info.get(
                    const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY,
                    const.DEFAULT_POINTS_MULTIPLIER,
                ),
            )

            # target
            if const.DATA_BADGE_TARGET not in badge_info or not isinstance(
                badge_info[const.DATA_BADGE_TARGET], dict
            ):
                badge_info[const.DATA_BADGE_TARGET] = {}
            badge_info[const.DATA_BADGE_TARGET].setdefault(
                const.DATA_BADGE_TARGET_TYPE,
                badge_info.get(
                    const.DATA_BADGE_THRESHOLD_TYPE_LEGACY,
                    const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                ),
            )
            badge_info[const.DATA_BADGE_TARGET].setdefault(
                const.DATA_BADGE_TARGET_THRESHOLD_VALUE,
                badge_info.get(const.DATA_BADGE_THRESHOLD_VALUE_LEGACY, 0),
            )
            badge_info[const.DATA_BADGE_TARGET].setdefault(
                const.DATA_BADGE_MAINTENANCE_RULES, 0
            )

            # --- Migrate threshold_type/value to target if not already done ---
            if const.DATA_BADGE_THRESHOLD_TYPE_LEGACY in badge_info:
                badge_info[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE] = (
                    badge_info.get(const.DATA_BADGE_THRESHOLD_TYPE_LEGACY)
                )
            if const.DATA_BADGE_THRESHOLD_VALUE_LEGACY in badge_info:
                badge_info[const.DATA_BADGE_TARGET][
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                ] = badge_info.get(const.DATA_BADGE_THRESHOLD_VALUE_LEGACY)

            # Migrate points_multiplier to awards.points_multiplier if not already done
            if const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY in badge_info:
                badge_info[const.DATA_BADGE_AWARDS][
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER
                ] = float(
                    badge_info.get(
                        const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY,
                        const.DEFAULT_POINTS_MULTIPLIER,
                    )
                )

            # --- Clean up any legacy fields that might exist outside the new nested structure ---
            legacy_fields = [
                const.DATA_BADGE_THRESHOLD_TYPE_LEGACY,
                const.DATA_BADGE_THRESHOLD_VALUE_LEGACY,
                const.DATA_BADGE_CHORE_COUNT_TYPE_LEGACY,
                const.DATA_BADGE_POINTS_MULTIPLIER_LEGACY,
            ]
            for field in legacy_fields:
                if field in badge_info:
                    del badge_info[field]

        self.coordinator._persist(immediate=True)  # Migration must be immediate
        self.coordinator.async_set_updated_data(self.coordinator._data)

        const.LOGGER.info(
            "INFO: Badge Migration - Completed migration of legacy badges to new structure"
        )

    def _migrate_assignee_legacy_badges_to_cumulative_progress(self) -> None:
        """Set cumulative badge progress for each assignee based on legacy badges earned.

        For each assignee, set their current cumulative badge to the highest-value badge
        (by points threshold) from their legacy earned badges list.
        Also set their cumulative cycle points to their current points balance to avoid losing progress.
        """
        for assignee_info in self.coordinator.assignees_data.values():
            legacy_badge_names = assignee_info.get(
                const.DATA_ASSIGNEE_BADGES_LEGACY, []
            )
            if not legacy_badge_names:
                continue

            # Find the highest-value cumulative badge earned by this assignee
            highest_badge = None
            highest_points = -1
            for badge_name in legacy_badge_names:  # type: ignore[attr-defined]
                # Find badge_id by name and ensure it's cumulative
                badge_id = None
                for b_id, b_info in self.coordinator.badges_data.items():
                    if (
                        b_info.get(const.DATA_BADGE_NAME) == badge_name
                        and b_info.get(const.DATA_BADGE_TYPE)
                        == const.BADGE_TYPE_CUMULATIVE
                    ):
                        badge_id = b_id
                        break
                if not badge_id:
                    continue
                badge_info = self.coordinator.badges_data[badge_id]
                points = int(
                    float(
                        badge_info.get(const.DATA_BADGE_TARGET, {}).get(
                            const.DATA_BADGE_TARGET_THRESHOLD_VALUE, 0
                        )
                    )
                )
                if points > highest_points:
                    highest_points = points
                    highest_badge = badge_info

            # Set the current cumulative badge progress for this assignee
            # Phase 3A: Only write state fields - derived fields computed on-read
            if highest_badge:
                progress = assignee_info.setdefault(
                    const.DATA_USER_CUMULATIVE_BADGE_PROGRESS,
                    {},  # type: ignore[typeddict-item]
                )
                # Set cycle points to current points balance to avoid losing progress
                progress[const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = (
                    assignee_info.get(const.DATA_USER_POINTS, 0.0)
                )

    def _migrate_assignee_legacy_badges_to_badges_earned(self) -> None:
        """One-time migration from legacy 'badges' list to structured 'badges_earned' dict for each assignee."""
        const.LOGGER.info(
            "INFO: Migration - Starting legacy badges to badges_earned migration"
        )
        today_local_iso = dt_today_iso()

        for assignee_id, assignee_info in self.coordinator.assignees_data.items():
            legacy_badge_names = assignee_info.get(
                const.DATA_ASSIGNEE_BADGES_LEGACY, []
            )
            badges_earned = assignee_info.setdefault(const.DATA_USER_BADGES_EARNED, {})

            for badge_name in legacy_badge_names:  # type: ignore[attr-defined]
                badge_id = get_item_id_by_name(
                    self.coordinator, const.ITEM_TYPE_BADGE, badge_name
                )

                if not badge_id:
                    badge_id = f"{LEGACY_MIGRATION_ORPHAN_PREFIX}_{random.randint(100000, 999999)}"
                    const.LOGGER.warning(
                        "WARNING: Migrate - Badge '%s' not found in badge data. Assigning legacy orphan ID '%s' for assignee '%s'.",
                        badge_name,
                        badge_id,
                        assignee_info.get(const.DATA_USER_NAME, assignee_id),
                    )

                if badge_id in badges_earned:
                    const.LOGGER.debug(
                        "DEBUG: Migration - Badge '%s' (%s) already in badges_earned for assignee '%s', skipping.",
                        badge_name,
                        badge_id,
                        assignee_id,
                    )
                    continue

                # Phase 4B: Create badge entry WITHOUT award_count at root
                # award_count will be written to periods.all_time.all_time by StatisticsManager
                # on next badge award (Tenant handles counter, Landlord creates structure only)
                badges_earned[badge_id] = {
                    const.DATA_USER_BADGES_EARNED_NAME: badge_name,
                    const.DATA_USER_BADGES_EARNED_LAST_AWARDED: today_local_iso,
                    const.DATA_USER_BADGES_EARNED_PERIODS: {},  # Tenant populates
                }

                const.LOGGER.info(
                    "INFO: Migration - Migrated badge '%s' (%s) to badges_earned for assignee '%s'.",
                    badge_name,
                    badge_id,
                    assignee_info.get(const.DATA_USER_NAME, assignee_id),
                )

            # Cleanup: remove the legacy badges list after migration
            if const.DATA_ASSIGNEE_BADGES_LEGACY in assignee_info:
                del assignee_info[const.DATA_ASSIGNEE_BADGES_LEGACY]  # type: ignore[typeddict-item]

        self.coordinator._persist(immediate=True)  # Migration must be immediate
        self.coordinator.async_set_updated_data(self.coordinator._data)

    def _migrate_legacy_point_stats(self) -> None:
        """Initialize period structure for legacy data - actual migration done by _consolidate_point_stats.

        NOTE: Legacy point stat fields (points_earned_today/weekly/monthly/yearly, max_points_ever)
        are rolling counters WITHOUT time attribution. They CANNOT be written to specific
        period buckets (daily/weekly/monthly/yearly) as they don't represent activity in those
        specific periods.

        The actual migration of max_points_ever → all_time bucket is handled by _consolidate_point_stats
        at Phase 4b (BEFORE legacy fields are deleted). This function just ensures the period structure exists.
        """
        for assignee_info_raw in self.coordinator.assignees_data.values():
            assignee_info = cast("dict[str, Any]", assignee_info_raw)
            # Get or create point_data periods structure (v42 LEGACY structure)
            point_data = assignee_info.setdefault(
                const.DATA_ASSIGNEE_POINT_DATA_LEGACY, {}
            )
            periods = point_data.setdefault(
                const.DATA_ASSIGNEE_POINT_DATA_PERIODS_LEGACY, {}
            )

            # Ensure all_time bucket exists (structure only - values set by _consolidate_point_stats)
            all_time_bucket = periods.setdefault(
                const.DATA_USER_POINT_PERIODS_ALL_TIME, {}
            )
            all_time_bucket.setdefault(
                const.PERIOD_ALL_TIME,
                {
                    const.DATA_USER_POINT_PERIOD_POINTS_EARNED: 0.0,
                    const.DATA_USER_POINT_PERIOD_POINTS_SPENT: 0.0,
                    const.DATA_USER_POINT_PERIOD_BY_SOURCE: {},
                    const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE: 0.0,
                },
            )

        const.LOGGER.info("Period structure initialized for point stats.")

    def _migrate_completed_metric(self) -> None:
        """Backfill 'completed' metric from 'approved' in period buckets (v0.5.0-beta4).

        Phase 4 introduces approver-lag-proof statistics: the 'completed' metric tracks
        work completion by claim date (when assignee did the work), not approval date.

        Historical approvals have no 'completed' tracking because this feature didn't exist.
        Backfill assumption: completed = approved (best estimate for pre-Phase 4 data).

        This migration is idempotent: if 'completed' already exists in a bucket, skip it.
        """
        const.LOGGER.info(
            "Starting 'completed' metric backfill migration (v0.5.0-beta4)"
        )

        assignees_data: dict[str, Any] = self.coordinator._data.get(
            const.DATA_USERS, {}
        )
        if not assignees_data:
            const.LOGGER.info(
                "No assignees data found, skipping completed metric migration"
            )
            return

        buckets_migrated: int = 0

        for _assignee_id, assignee_info in assignees_data.items():
            chore_data: dict[str, Any] = assignee_info.get(
                const.DATA_USER_CHORE_DATA, {}
            )

            for _chore_id, chore_info in chore_data.items():
                periods: dict[str, Any] = chore_info.get(
                    const.DATA_USER_CHORE_DATA_PERIODS, {}
                )

                # Iterate all period types using constants
                for period_type in [
                    const.DATA_USER_CHORE_DATA_PERIODS_DAILY,
                    const.DATA_USER_CHORE_DATA_PERIODS_WEEKLY,
                    const.DATA_USER_CHORE_DATA_PERIODS_MONTHLY,
                    const.DATA_USER_CHORE_DATA_PERIODS_YEARLY,
                ]:
                    period_buckets: dict[str, Any] = periods.get(period_type, {})

                    for _period_key, bucket in period_buckets.items():
                        # Use constants for metric keys
                        approved_key = const.DATA_USER_CHORE_DATA_PERIOD_APPROVED
                        completed_key = const.DATA_USER_CHORE_DATA_PERIOD_COMPLETED

                        # Only backfill if approved exists and completed doesn't
                        if approved_key in bucket and completed_key not in bucket:
                            bucket[completed_key] = bucket[approved_key]
                            buckets_migrated += 1

        const.LOGGER.info(
            "✓ Completed metric backfill: Migrated %d period buckets", buckets_migrated
        )

    def _migrate_badge_award_count_to_periods(self) -> None:
        """Move badge award_count from root to periods.all_time.all_time (Phase 4B, v43).

        "Lean Item" pattern: Remove root-level award_count duplication, use periods
        as canonical source. Matches Phase 2 (chore total_points) and Phase 3 (reward total_*).

        Migration logic:
        1. Read award_count from badge_entry root
        2. Create periods.all_time.all_time structure if missing
        3. Write award_count to periods.all_time.all_time.award_count
        4. Delete award_count from root

        Idempotent: If award_count not in root, skip. If already in periods, preserve it.
        """
        const.LOGGER.info(
            "Starting badge award_count migration to periods (Phase 4B, v43)"
        )

        assignees_data: dict[str, Any] = self.coordinator._data.get(
            const.DATA_USERS, {}
        )
        if not assignees_data:
            const.LOGGER.info(
                "No assignees data found, skipping badge award_count migration"
            )
            return

        badges_migrated: int = 0

        for assignee_id, assignee_info in assignees_data.items():
            badges_earned: dict[str, Any] = assignee_info.get(
                const.DATA_USER_BADGES_EARNED, {}
            )

            # Handle legacy v41 list format (should already be migrated to dict by _migrate_badges)
            if not isinstance(badges_earned, dict):
                const.LOGGER.debug(
                    "Assignee '%s' has legacy list format badges_earned, skipping",
                    assignee_info.get(const.DATA_USER_NAME, assignee_id),
                )
                continue

            for badge_id, badge_entry in badges_earned.items():
                # Skip if award_count not at root (already migrated or never existed)
                if const.DATA_USER_BADGES_EARNED_AWARD_COUNT not in badge_entry:
                    continue

                count = badge_entry.pop(const.DATA_USER_BADGES_EARNED_AWARD_COUNT)

                # Ensure periods structure exists
                periods = badge_entry.setdefault(
                    const.DATA_USER_BADGES_EARNED_PERIODS, {}
                )
                all_time_bucket = periods.setdefault(
                    const.DATA_USER_BADGES_EARNED_PERIODS_ALL_TIME, {}
                )
                all_time_data = all_time_bucket.setdefault(const.PERIOD_ALL_TIME, {})

                # Write count to periods (preserve existing value if already present)
                if const.DATA_USER_BADGES_EARNED_AWARD_COUNT not in all_time_data:
                    all_time_data[const.DATA_USER_BADGES_EARNED_AWARD_COUNT] = count
                    badges_migrated += 1

                    const.LOGGER.debug(
                        "Migrated badge '%s' award_count=%d to periods for assignee '%s'",
                        badge_entry.get(const.DATA_USER_BADGES_EARNED_NAME, badge_id),
                        count,
                        assignee_info.get(const.DATA_USER_NAME, assignee_id),
                    )

        const.LOGGER.info(
            "✓ Badge award_count migration: Migrated %d badges", badges_migrated
        )

    # -------------------------------------------------------------------------------------
    # KC 3.x Config Sync to Storage (v41→v42 Migration Compatibility)
    # -------------------------------------------------------------------------------------
    # These methods handle one-time migration of entity data from config_entry.options
    # to .storage/choreops_data when upgrading from KC 3.x (schema <42) to KC 4.x (schema 42+).
    # NOTE: CRUD methods (_create_assignee, _update_chore, etc.) remain in coordinator as they
    # are actively used by options_flow.py for v4.2+ entity management.

    def _initialize_data_from_config(self) -> None:
        """Migrate entity data from config_entry.options to storage (KC 3.x→4.x compatibility).

        This method is ONLY called once when storage_schema_version < 42.
        For v4.2+ users, entity data is already in storage and config contains only system settings.
        """
        options = self.coordinator.config_entry.options

        # Skip if no KC 3.x config data present (pure storage migration, no config sync needed)
        if not options or not options.get(const.CONF_ASSIGNEES_LEGACY):
            const.LOGGER.info(
                "No KC 3.x config data - skipping config sync (already using storage-only mode)"
            )
            return

        # Retrieve configuration dictionaries from config entry options (KC 3.x architecture)
        config_sections = {
            const.DATA_USERS: options.get(const.CONF_ASSIGNEES_LEGACY, {}),
            const.DATA_APPROVERS: options.get(const.CONF_APPROVERS_LEGACY, {}),
            const.DATA_CHORES: options.get(const.CONF_CHORES_LEGACY, {}),
            const.DATA_BADGES: options.get(const.CONF_BADGES_LEGACY, {}),
            const.DATA_REWARDS: options.get(const.CONF_REWARDS_LEGACY, {}),
            const.DATA_PENALTIES: options.get(const.CONF_PENALTIES_LEGACY, {}),
            const.DATA_BONUSES: options.get(const.CONF_BONUSES_LEGACY, {}),
            const.DATA_ACHIEVEMENTS: options.get(const.CONF_ACHIEVEMENTS_LEGACY, {}),
            const.DATA_CHALLENGES: options.get(const.CONF_CHALLENGES_LEGACY, {}),
        }

        # Ensure minimal structure
        self._ensure_minimal_structure()

        # Initialize each section using private helper
        for section_key, data_dict in config_sections.items():
            init_func = getattr(self, f"_initialize_{section_key}", None)
            if init_func:  # pylint: disable=using-constant-test
                init_func(data_dict)
            else:
                self.coordinator._data.setdefault(section_key, data_dict)
                const.LOGGER.warning(
                    "WARNING: No initializer found for section '%s'", section_key
                )

        # Recalculate Badges on reload (marks all assignees dirty for evaluation)
        self.coordinator.gamification_manager.recalculate_all_badges()

    def _ensure_minimal_structure(self) -> None:
        """Ensure that all necessary data sections are present in storage."""
        for key in [
            const.DATA_USERS,
            const.DATA_APPROVERS,
            const.DATA_CHORES,
            const.DATA_BADGES,
            const.DATA_REWARDS,
            const.DATA_PENALTIES,
            const.DATA_BONUSES,
            const.DATA_ACHIEVEMENTS,
            const.DATA_CHALLENGES,
        ]:
            self.coordinator._data.setdefault(key, {})

        for key in [
            const.DATA_PENDING_CHORE_APPROVALS_LEGACY,
            const.DATA_PENDING_REWARD_APPROVALS_LEGACY,
        ]:
            if not isinstance(self.coordinator._data.get(key), list):
                self.coordinator._data[key] = []

        # v0.4.0: Remove chore queue - computed from timestamps
        self.coordinator._data.pop(const.DATA_PENDING_CHORE_APPROVALS_LEGACY, None)

    # -- Entity Type Wrappers (delegate to _sync_entities) --

    def _initialize_assignees(self, assignees_dict: dict[str, Any]) -> None:
        """Initialize assignees from config data."""
        self._sync_entities(
            const.DATA_USERS,
            assignees_dict,
            self._create_assignee,
            self._update_assignee,
        )

    def _initialize_approvers(self, approvers_dict: dict[str, Any]) -> None:
        """Initialize approvers from config data."""
        self._sync_entities(
            const.DATA_APPROVERS,
            approvers_dict,
            self._create_approver,
            self._update_approver,
        )

    def _initialize_chores(self, chores_dict: dict[str, Any]) -> None:
        """Initialize chores from config data."""
        self._sync_entities(
            const.DATA_CHORES,
            chores_dict,
            self._create_chore,
            self._update_chore,
        )

    def _initialize_badges(self, badges_dict: dict[str, Any]) -> None:
        """Initialize badges from config data."""
        self._sync_entities(
            const.DATA_BADGES,
            badges_dict,
            self._create_badge,
            self._update_badge,
        )

    def _initialize_rewards(self, rewards_dict: dict[str, Any]) -> None:
        """Initialize rewards from config data."""
        self._sync_entities(
            const.DATA_REWARDS,
            rewards_dict,
            self._create_reward,
            self._update_reward,
        )

    def _initialize_penalties(self, penalties_dict: dict[str, Any]) -> None:
        """Initialize penalties from config data."""
        self._sync_entities(
            const.DATA_PENALTIES,
            penalties_dict,
            self._create_penalty,
            self._update_penalty,
        )

    def _initialize_achievements(self, achievements_dict: dict[str, Any]) -> None:
        """Initialize achievements from config data."""
        self._sync_entities(
            const.DATA_ACHIEVEMENTS,
            achievements_dict,
            self._create_achievement,
            self._update_achievement,
        )

    def _initialize_challenges(self, challenges_dict: dict[str, Any]) -> None:
        """Initialize challenges from config data."""
        self._sync_entities(
            const.DATA_CHALLENGES,
            challenges_dict,
            self._create_challenge,
            self._update_challenge,
        )

    def _initialize_bonuses(self, bonuses_dict: dict[str, Any]) -> None:
        """Initialize bonuses from config data."""
        self._sync_entities(
            const.DATA_BONUSES,
            bonuses_dict,
            self._create_bonus,
            self._update_bonus,
        )

    def _sync_entities(
        self,
        section: str,
        config_data: dict[str, Any],
        create_method,
        update_method,
    ) -> None:
        """Synchronize entities in a given data section based on config_data.

        Compares config data against storage, calling create/update methods as needed.
        This is the core sync engine for KC 3.x→4.x migration.
        """
        existing_ids = set(self.coordinator._data[section].keys())
        config_ids = set(config_data.keys())

        # Identify entities to remove
        entities_to_remove = existing_ids - config_ids
        for entity_id in entities_to_remove:
            # Remove entity from data
            del self.coordinator._data[section][entity_id]

            # Remove entity from HA registry
            eh.remove_entities_by_item_id(
                self.coordinator.hass,
                self.coordinator.config_entry.entry_id,
                entity_id,
            )

            # Cleanup references to deleted entity
            if section == const.DATA_USERS:
                # Remove deleted assignee from approvers' assignees lists
                for approver in self.coordinator._data.get(
                    const.DATA_APPROVERS, {}
                ).values():
                    if entity_id in approver.get(
                        const.DATA_USER_ASSOCIATED_USER_IDS, []
                    ):
                        approver[const.DATA_USER_ASSOCIATED_USER_IDS].remove(entity_id)

            if section == const.DATA_REWARDS:
                # Remove deleted reward from root-level pending approvals (legacy schema)
                # In KC 3.x, pending_reward_approvals was at data root, not per-assignee
                approvals = self.coordinator._data.get(
                    const.DATA_PENDING_REWARD_APPROVALS_LEGACY, []
                )
                self.coordinator._data[const.DATA_PENDING_REWARD_APPROVALS_LEGACY] = [
                    a for a in approvals if a.get("reward_id") != entity_id
                ]

        # Add or update entities
        for entity_id, entity_body in config_data.items():
            if entity_id not in self.coordinator._data[section]:
                create_method(entity_id, entity_body)
            else:
                update_method(entity_id, entity_body)

        # Remove orphaned chore-related entities (using entity_helpers directly)
        if section == const.DATA_CHORES:
            self.coordinator.hass.async_create_task(
                eh.remove_orphaned_shared_chore_sensors(
                    self.coordinator.hass,
                    self.coordinator.config_entry.entry_id,
                    self.coordinator.chores_data,
                )
            )
            self.coordinator.hass.async_create_task(
                eh.remove_orphaned_assignee_chore_entities(
                    self.coordinator.hass,
                    self.coordinator.config_entry.entry_id,
                    self.coordinator.assignees_data,
                    self.coordinator.chores_data,
                )
            )

        # Remove orphaned achievement and challenges sensors
        self.coordinator.hass.async_create_task(
            eh.remove_orphaned_progress_entities(
                self.coordinator.hass,
                self.coordinator.config_entry.entry_id,
                self.coordinator.achievements_data,
                entity_type="achievement",
                progress_suffix=const.DATA_ACHIEVEMENT_PROGRESS_SUFFIX,
                assigned_assignees_key=const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
            )
        )
        self.coordinator.hass.async_create_task(
            eh.remove_orphaned_progress_entities(
                self.coordinator.hass,
                self.coordinator.config_entry.entry_id,
                self.coordinator.challenges_data,
                entity_type="challenge",
                progress_suffix=const.DATA_CHALLENGE_PROGRESS_SUFFIX,
                assigned_assignees_key=const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
            )
        )

        # Remove deprecated sensors (sync method - no async_create_task needed)
        self.remove_deprecated_entities(
            self.coordinator.hass, self.coordinator.config_entry
        )

        # Remove deprecated/orphaned dynamic entities
        self.remove_deprecated_button_entities()
        self.remove_deprecated_sensor_entities()

    def _add_chore_optional_fields(self) -> None:
        """Add new optional fields to existing chores during migration.

        This adds default values for fields introduced in later versions:
        - show_on_calendar (defaults to True)
        - auto_approve (defaults to False)
        - overdue_handling_type (defaults to AT_DUE_DATE)
        - approval_reset_pending_claim_action (defaults to CLEAR_PENDING)

        These fields are added during pre-v42 migration. For v42+ data,
        they are already set by flow_helpers.py during entity creation.
        """
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})
        for chore_id, chore_data in chores_data.items():
            # Add show_on_calendar field (new optional field, defaults to True)
            if const.DATA_CHORE_SHOW_ON_CALENDAR not in chore_data:
                chore_data[const.DATA_CHORE_SHOW_ON_CALENDAR] = True
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added show_on_calendar field",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

            # Add auto_approve field (new optional field, defaults to False)
            if const.DATA_CHORE_AUTO_APPROVE not in chore_data:
                chore_data[const.DATA_CHORE_AUTO_APPROVE] = False
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added auto_approve field",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

            # Add overdue_handling_type field (defaults to AT_DUE_DATE)
            if const.DATA_CHORE_OVERDUE_HANDLING_TYPE not in chore_data:
                chore_data[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
                    const.DEFAULT_OVERDUE_HANDLING_TYPE
                )
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added overdue_handling_type field",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

            # Migrate old overdue_handling_type value string (v0.5.0 rename)
            # "at_due_date_then_reset" → "at_due_date_clear_at_approval_reset"
            if (
                chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
                == "at_due_date_then_reset"
            ):
                chore_data[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
                    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
                )
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): updated overdue_handling_type "
                    "from 'at_due_date_then_reset' to '%s'",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
                )

            # Add approval_reset_pending_claim_action field (defaults to CLEAR_PENDING)
            if const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION not in chore_data:
                chore_data[const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION] = (
                    const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION
                )
                const.LOGGER.debug(
                    "Migrated chore '%s' (%s): added approval_reset_pending_claim_action",
                    chore_data.get(const.DATA_CHORE_NAME),
                    chore_id,
                )

    def _migrate_reward_data_to_periods(self) -> None:
        """Migrate legacy reward tracking to period-based reward_data structure.

        Legacy fields (per assignee):
        - pending_rewards: list[str]  (reward_ids waiting approval)
        - reward_claims: dict[str, int]  (reward_id → claim count)
        - reward_approvals: dict[str, int]  (reward_id → approval count)
        - redeemed_rewards: list[str]  (reward_ids approved, used for "approved today")

        Modern structure (per assignee, per reward):
        - reward_data[reward_id].pending_count
        - reward_data[reward_id].total_claims
        - reward_data[reward_id].total_approved
        - reward_data[reward_id].total_points_spent
        - reward_data[reward_id].periods.{daily,weekly,monthly,yearly}

        This migration is idempotent - existing reward_data entries are preserved.
        Legacy fields are kept for backward compatibility during transition.
        """
        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        rewards_data = self.coordinator._data.get(const.DATA_REWARDS, {})
        migrated_assignees = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_migrated = False

            # Ensure reward_data dict exists
            if const.DATA_USER_REWARD_DATA not in assignee_info:
                assignee_info[const.DATA_USER_REWARD_DATA] = {}

            reward_data = assignee_info[const.DATA_USER_REWARD_DATA]

            # Migrate pending_rewards[] → reward_data[id].pending_count
            pending_rewards = assignee_info.get(
                const.DATA_ASSIGNEE_PENDING_REWARDS_LEGACY, []
            )
            if pending_rewards:
                # Count occurrences of each reward_id
                pending_counts = Counter(pending_rewards)
                for reward_id, count in pending_counts.items():
                    if reward_id not in reward_data:
                        reward_data[reward_id] = self._create_empty_reward_entry(
                            reward_id, rewards_data
                        )
                    # Only migrate if pending_count is 0 (not already set)
                    if (
                        reward_data[reward_id].get(
                            const.DATA_USER_REWARD_DATA_PENDING_COUNT, 0
                        )
                        == 0
                    ):
                        reward_data[reward_id][
                            const.DATA_USER_REWARD_DATA_PENDING_COUNT
                        ] = count
                        assignee_migrated = True

            # Migrate reward_claims{} → reward_data[id].total_claims
            reward_claims = assignee_info.get(
                const.DATA_ASSIGNEE_REWARD_CLAIMS_LEGACY, {}
            )
            for reward_id, claim_count in reward_claims.items():
                if reward_id not in reward_data:
                    reward_data[reward_id] = self._create_empty_reward_entry(
                        reward_id, rewards_data
                    )
                # Only migrate if total_claims is 0 (not already set)
                if (
                    reward_data[reward_id].get(
                        const.DATA_USER_REWARD_DATA_TOTAL_CLAIMS, 0
                    )
                    == 0
                ):
                    reward_data[reward_id][const.DATA_USER_REWARD_DATA_TOTAL_CLAIMS] = (
                        claim_count
                    )
                    assignee_migrated = True

            # Migrate reward_approvals{} → reward_data[id].total_approved
            reward_approvals = assignee_info.get(
                const.DATA_ASSIGNEE_REWARD_APPROVALS_LEGACY, {}
            )
            for reward_id, approval_count in reward_approvals.items():
                if reward_id not in reward_data:
                    reward_data[reward_id] = self._create_empty_reward_entry(
                        reward_id, rewards_data
                    )
                # Only migrate if total_approved is 0 (not already set)
                if (
                    reward_data[reward_id].get(
                        const.DATA_USER_REWARD_DATA_TOTAL_APPROVED, 0
                    )
                    == 0
                ):
                    reward_data[reward_id][
                        const.DATA_USER_REWARD_DATA_TOTAL_APPROVED
                    ] = approval_count
                    # Estimate total_points_spent from approvals * reward cost
                    reward_info = rewards_data.get(reward_id, {})
                    cost = reward_info.get(const.DATA_REWARD_COST, 0)
                    if cost > 0:
                        reward_data[reward_id][
                            const.DATA_USER_REWARD_DATA_TOTAL_POINTS_SPENT
                        ] = approval_count * cost
                    assignee_migrated = True

            if assignee_migrated:
                migrated_assignees += 1
                const.LOGGER.debug(
                    "Migrated reward data for assignee '%s' (%s)",
                    assignee_info.get(const.DATA_USER_NAME, ""),
                    assignee_id,
                )

        if migrated_assignees > 0:
            const.LOGGER.info(
                "Reward data migration complete. Migrated %d assignees to period-based structure.",
                migrated_assignees,
            )

    def _create_empty_reward_entry(
        self, reward_id: str, rewards_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an empty reward_data entry with all fields initialized.

        Args:
            reward_id: The reward's internal ID
            rewards_data: The rewards data dict for looking up reward name

        Returns:
            A new reward_data entry dict with all fields initialized.
        """
        return {
            const.DATA_USER_REWARD_DATA_NAME: rewards_data.get(reward_id, {}).get(
                const.DATA_REWARD_NAME, ""
            ),
            const.DATA_USER_REWARD_DATA_PENDING_COUNT: 0,
            const.DATA_USER_REWARD_DATA_NOTIFICATION_IDS: [],
            const.DATA_USER_REWARD_DATA_LAST_CLAIMED: None,
            const.DATA_USER_REWARD_DATA_LAST_APPROVED: None,
            const.DATA_USER_REWARD_DATA_LAST_DISAPPROVED: None,
            const.DATA_USER_REWARD_DATA_TOTAL_CLAIMS: 0,
            const.DATA_USER_REWARD_DATA_TOTAL_APPROVED: 0,
            const.DATA_USER_REWARD_DATA_TOTAL_DISAPPROVED: 0,
            const.DATA_USER_REWARD_DATA_TOTAL_POINTS_SPENT: 0,
            const.DATA_USER_REWARD_DATA_PERIODS: {
                const.DATA_USER_REWARD_DATA_PERIODS_DAILY: {},
                const.DATA_USER_REWARD_DATA_PERIODS_WEEKLY: {},
                const.DATA_USER_REWARD_DATA_PERIODS_MONTHLY: {},
                const.DATA_USER_REWARD_DATA_PERIODS_YEARLY: {},
                const.DATA_USER_REWARD_DATA_PERIODS_ALL_TIME: {},
            },
        }

    def _remove_legacy_fields(self) -> None:
        """Remove all legacy fields from data after migration is complete.

        During migration, legacy fields are READ to populate new structures,
        but they must be REMOVED from the final v42+ data to ensure clean
        data structures and pass validation tests.

        This method removes ALL legacy fields that have been superseded by
        the new data model. Some individual migration methods already remove
        their specific fields (e.g., shared_chore, allow_multiple_claims_per_day),
        but this method provides comprehensive cleanup for fields that were
        only read during aggregation migrations.

        Legacy fields removed:
        - Assignees: chore_claims, chore_streaks, chore_approvals, today_chore_approvals,
                completed_chores_*, points_earned_*, pending_rewards, redeemed_rewards,
                reward_claims, reward_approvals
        - Top-level: pending_chore_approvals, pending_reward_approvals (if legacy format)

        Fields NOT removed (still in use or not fully migrated):
        - Assignees: max_streak (backward compat, used by legacy sensors)
        - Assignees: badges (already removed by _migrate_assignee_legacy_badges_to_cumulative_progress)
        - Chores: shared_chore, allow_multiple_claims_per_day (already removed inline)
        - Badges: threshold_type, threshold_value, etc. (already removed inline)
        """
        assignees_cleaned = 0
        fields_removed_count = 0

        # Legacy assignee fields to remove after migration
        assignee_legacy_fields = [
            # Chore tracking (migrated to chore_data and chore_stats)
            const.DATA_ASSIGNEE_CHORE_CLAIMS_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STREAKS_LEGACY,
            const.DATA_ASSIGNEE_CHORE_APPROVALS_LEGACY,
            # Chore approvals today (migrated to periods structure)
            const.DATA_ASSIGNEE_TODAY_CHORE_APPROVALS_LEGACY,
            # Completed chores counters (migrated to chore_stats)
            const.DATA_ASSIGNEE_COMPLETED_CHORES_TOTAL_LEGACY,
            const.DATA_ASSIGNEE_COMPLETED_CHORES_MONTHLY_LEGACY,
            const.DATA_ASSIGNEE_COMPLETED_CHORES_WEEKLY_LEGACY,
            const.DATA_ASSIGNEE_COMPLETED_CHORES_TODAY_LEGACY,
            const.DATA_ASSIGNEE_COMPLETED_CHORES_YEARLY_LEGACY,
            # Points earned tracking (migrated to point_stats)
            const.DATA_ASSIGNEE_POINTS_EARNED_TODAY_LEGACY,
            const.DATA_ASSIGNEE_POINTS_EARNED_WEEKLY_LEGACY,
            const.DATA_ASSIGNEE_POINTS_EARNED_MONTHLY_LEGACY,
            const.DATA_ASSIGNEE_POINTS_EARNED_YEARLY_LEGACY,
            # Reward tracking (migrated to reward_data)
            const.DATA_ASSIGNEE_PENDING_REWARDS_LEGACY,
            const.DATA_ASSIGNEE_REDEEMED_REWARDS_LEGACY,
            const.DATA_ASSIGNEE_REWARD_CLAIMS_LEGACY,
            const.DATA_ASSIGNEE_REWARD_APPROVALS_LEGACY,
            # Point statistics (max_points_ever migrated to point_stats.highest_balance_all_time)
            const.DATA_ASSIGNEE_MAX_POINTS_EVER_LEGACY,
            # Dead code fields (v0.5.0+ - overdue tracked in chore_data[chore_id].state)
            const.DATA_ASSIGNEE_OVERDUE_CHORES_LEGACY,
        ]

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        for assignee_id, assignee_info in assignees_data.items():
            removed_any = False
            for field in assignee_legacy_fields:
                if field in assignee_info:
                    del assignee_info[field]
                    removed_any = True
                    fields_removed_count += 1
                    const.LOGGER.debug(
                        "Removed legacy field '%s' from assignee '%s'",
                        field,
                        assignee_info.get(const.DATA_USER_NAME, assignee_id),
                    )
            if removed_any:
                assignees_cleaned += 1

        if assignees_cleaned > 0:
            const.LOGGER.info(
                "Legacy field cleanup: removed %s fields from %s assignees",
                fields_removed_count,
                assignees_cleaned,
            )
        else:
            const.LOGGER.debug("Legacy field cleanup: no legacy fields found to remove")

    def _round_float_precision(self) -> None:
        """Round all stored float values to standard precision (DATA_FLOAT_PRECISION).

        Python float arithmetic can cause precision drift, e.g., 2.2 * 12.5 = 27.499999999999996
        instead of 27.5. This migration cleans up any existing drifted values by rounding
        to DATA_FLOAT_PRECISION (2 decimal places) for consistent storage.

        Affected fields per assignee:
        - points: Current point balance
        - points_multiplier: Point earning multiplier
        - point_stats.*: All point statistics
        - point_data.periods.*: All period point values
        - chore_stats.*: All chore statistics (total_points_from_chores_*)
        - chore_data.*.periods.*: All chore period point values
        - cumulative_badge_progress.*: baseline, cycle_points, etc.
        """
        precision = const.DATA_FLOAT_PRECISION
        assignees_cleaned = 0
        values_rounded = 0

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)
            rounded_any = False

            # --- Top-level assignee float fields ---
            for field in [
                const.DATA_USER_POINTS,
                const.DATA_USER_POINTS_MULTIPLIER,
            ]:
                if field in assignee_info and isinstance(
                    assignee_info[field], (int, float)
                ):
                    old_val = assignee_info[field]
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        assignee_info[field] = new_val
                        rounded_any = True
                        values_rounded += 1

            # --- point_stats fields ---
            point_stats = assignee_info.get(const.DATA_ASSIGNEE_POINT_STATS_LEGACY, {})
            for key, val in list(point_stats.items()):
                if isinstance(val, (int, float)):
                    old_val = val
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        point_stats[key] = new_val
                        rounded_any = True
                        values_rounded += 1
                elif isinstance(val, dict):
                    # Handle nested by_source dicts
                    for nested_key, nested_val in list(val.items()):
                        if isinstance(nested_val, (int, float)):
                            old_val = nested_val
                            new_val = round(float(old_val), precision)
                            if old_val != new_val:
                                val[nested_key] = new_val
                                rounded_any = True
                                values_rounded += 1

            # --- point_data.periods.*.* ---
            point_data = assignee_info.get(const.DATA_ASSIGNEE_POINT_DATA_LEGACY, {})
            periods = point_data.get(const.DATA_ASSIGNEE_POINT_DATA_PERIODS_LEGACY, {})
            for period_type in list(periods.keys()):
                period_dict = periods.get(period_type, {})
                for _, period_data in list(period_dict.items()):
                    if isinstance(period_data, dict):
                        for field_key, field_val in list(period_data.items()):
                            if isinstance(field_val, (int, float)):
                                old_val = field_val
                                new_val = round(float(old_val), precision)
                                if old_val != new_val:
                                    period_data[field_key] = new_val
                                    rounded_any = True
                                    values_rounded += 1
                            elif isinstance(field_val, dict):
                                # by_source nested dict
                                for nested_key, nested_val in list(field_val.items()):
                                    if isinstance(nested_val, (int, float)):
                                        old_val = nested_val
                                        new_val = round(float(old_val), precision)
                                        if old_val != new_val:
                                            field_val[nested_key] = new_val
                                            rounded_any = True
                                            values_rounded += 1

            # --- chore_stats fields ---
            chore_stats = assignee_info.get(const.DATA_ASSIGNEE_CHORE_STATS_LEGACY, {})
            for key, val in list(chore_stats.items()):
                if isinstance(val, (int, float)) and "points" in key.lower():
                    old_val = val
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        chore_stats[key] = new_val
                        rounded_any = True
                        values_rounded += 1

            # --- chore_data.*.periods.*.* points fields ---
            chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
            for _, chore_info in list(chore_data.items()):
                chore_periods = chore_info.get(const.DATA_USER_CHORE_DATA_PERIODS, {})
                for _period_type, period_dict in list(chore_periods.items()):
                    for _, period_values in list(period_dict.items()):
                        if isinstance(period_values, dict):
                            points_val = period_values.get(
                                const.DATA_USER_CHORE_DATA_PERIOD_POINTS
                            )
                            if points_val is not None and isinstance(
                                points_val, (int, float)
                            ):
                                old_val = points_val
                                new_val = round(float(old_val), precision)
                                if old_val != new_val:
                                    period_values[
                                        const.DATA_USER_CHORE_DATA_PERIOD_POINTS
                                    ] = new_val
                                    rounded_any = True
                                    values_rounded += 1

            # --- cumulative_badge_progress ---
            # Only cycle_points remains after Phase 3A cleanup (derived fields removed)
            cumulative = assignee_info.get(
                const.DATA_USER_CUMULATIVE_BADGE_PROGRESS, {}
            )
            for field in [
                const.DATA_USER_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS,
            ]:
                if field in cumulative and isinstance(cumulative[field], (int, float)):
                    old_val = cumulative[field]
                    new_val = round(float(old_val), precision)
                    if old_val != new_val:
                        cumulative[field] = new_val
                        rounded_any = True
                        values_rounded += 1

            if rounded_any:
                assignees_cleaned += 1
                const.LOGGER.debug(
                    "Rounded float precision for assignee '%s'", assignee_name
                )

        if values_rounded > 0:
            const.LOGGER.info(
                "Float precision cleanup: rounded %s values across %s assignees to %s decimal places",
                values_rounded,
                assignees_cleaned,
                precision,
            )
        else:
            const.LOGGER.debug("Float precision cleanup: no values needed rounding")

    def _cleanup_assignee_chore_data_due_dates_v50(self) -> None:
        """Remove legacy due_date fields from assignee-level chore_data for independent chores (v50 migration).

        In v50, the single source of truth for independent chore due dates is
        chore_info[per_assignee_due_dates][assignee_id]. The assignee-level chore_data[chore_id][due_date]
        field is now deprecated and should be removed during migration.

        This migration:
        1. Iterates all assignees and their chore_data entries
        2. Checks if the chore is INDEPENDENT (completion_criteria)
        3. Removes the due_date field from assignee-level chore_data if present

        SHARED chores don't have per-assignee due dates, so they're skipped.
        """
        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        chores_data = self.coordinator._data.get(const.DATA_CHORES, {})

        cleaned_count = 0
        assignees_affected = 0

        for assignee_info in assignees_data.values():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, "Unknown")
            assignee_chore_data = assignee_info.get(const.DATA_USER_CHORE_DATA, {})
            assignee_had_cleanup = False

            for chore_id in list(assignee_chore_data.keys()):
                # Get chore info to check completion criteria
                chore_info = chores_data.get(chore_id, {})
                completion_criteria = chore_info.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA
                )

                # Only clean up INDEPENDENT chores (SHARED chores don't have per-assignee dates)
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # Check if legacy due_date field exists in assignee-level chore_data
                    if (
                        const.DATA_ASSIGNEE_CHORE_DATA_DUE_DATE_LEGACY
                        in assignee_chore_data[chore_id]
                    ):
                        del assignee_chore_data[chore_id][
                            const.DATA_ASSIGNEE_CHORE_DATA_DUE_DATE_LEGACY
                        ]
                        cleaned_count += 1
                        assignee_had_cleanup = True
                        const.LOGGER.debug(
                            "Removed legacy due_date from assignee '%s' chore_data for chore '%s'",
                            assignee_name,
                            chore_info.get(const.DATA_CHORE_NAME, chore_id),
                        )

            if assignee_had_cleanup:
                assignees_affected += 1

        if cleaned_count > 0:
            const.LOGGER.info(
                "v50 cleanup: Removed %s legacy due_date fields from assignee-level chore_data across %s assignees",
                cleaned_count,
                assignees_affected,
            )
        else:
            const.LOGGER.debug(
                "v50 cleanup: No legacy due_date fields found in assignee-level chore_data"
            )

    def _simplify_notification_config_v50(self) -> None:
        """Remove redundant enable_notifications field from assignee and approver data.

        The enable_notifications field was always derived from bool(mobile_notify_service),
        making it redundant. This migration removes the field from storage data.

        Migration Actions:
        ————————————————————————————————————————————————————————————————————————
        1. Remove enable_notifications from all assignees
        2. Remove enable_notifications from all approvers

        The notification logic now checks mobile_notify_service directly:
        - If mobile_notify_service has value → send mobile notification
        - Else if use_persistent_notifications → send persistent notification
        - Else → no notification

        Refs: coordinator._notify_assignee(), coordinator._notify_approvers()
        """
        const.LOGGER.info("INFO: ==========================================")
        const.LOGGER.info(
            "INFO: Schema v50: Removing redundant enable_notifications field"
        )

        assignees_data = self.coordinator.assignees_data
        approvers_data = self.coordinator.approvers_data
        changes_made = False

        # Process all assignees - just remove the field
        for _assignee_id, assignee_info in assignees_data.items():
            # Cast to Any to bypass TypedDict strict key checking for legacy field removal
            assignee_dict = cast("dict[str, Any]", assignee_info)
            if "enable_notifications" in assignee_dict:
                assignee_dict.pop("enable_notifications")
                const.LOGGER.debug(
                    "DEBUG:   Assignee '%s': Removed enable_notifications field",
                    assignee_info.get(const.DATA_USER_NAME, "Unknown"),
                )
                changes_made = True

        # Process all approvers - just remove the field
        for _approver_id, approver_info in approvers_data.items():
            # Cast to Any to bypass TypedDict strict key checking for legacy field removal
            approver_dict = cast("dict[str, Any]", approver_info)
            if "enable_notifications" in approver_dict:
                approver_dict.pop("enable_notifications")
                const.LOGGER.debug(
                    "DEBUG:   Approver '%s': Removed enable_notifications field",
                    approver_info.get(const.DATA_USER_NAME, "Unknown"),
                )
                changes_made = True

        if changes_made:
            const.LOGGER.info(
                "INFO:   ✓ Removed enable_notifications field from entities"
            )
        else:
            const.LOGGER.info(
                "INFO:   ℹ No enable_notifications fields found (already clean)"
            )

        const.LOGGER.info("INFO: ==========================================")

    def _consolidate_point_stats(self) -> None:
        """Migrate point_stats → periods.all_time using current balance as baseline.

        Phase 7b: Stats Consolidation
        The point_stats dict was generated from periods. Now we store all_time values
        directly in the all_time period bucket, eliminating the redundant dict.

        MIGRATION STRATEGY:
        Use assignee's CURRENT POINTS BALANCE as the baseline for all_time stats.
        This ensures the math works: points_earned + points_spent = current balance.

        What this migration does:
        1. Set all_time.points_earned = current assignee points balance
        2. Set all_time.points_spent = 0.0 (fresh start)
        3. Set all_time.by_source.other = current assignee points (pre-migration activity)
        4. Set all_time.highest_balance = max(current balance, old highest if available)
        5. Delete legacy point_stats key from assignee_info
        6. Convert points_total → points_earned in period buckets
        """
        const.LOGGER.info("Phase 7b: Consolidating point_stats → periods.all_time")

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        if not assignees_data:
            const.LOGGER.info("  No assignees found, skipping stats consolidation")
            return

        stats_migrated = 0
        buckets_converted = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)

            # Get assignee's CURRENT points balance - this is the source of truth
            current_balance = float(assignee_info.get(const.DATA_USER_POINTS, 0.0))

            # Get point_data container
            point_data = assignee_info.get(const.DATA_ASSIGNEE_POINT_DATA_LEGACY, {})
            if not point_data:
                # Create point_data if it doesn't exist
                point_data = {}
                assignee_info[const.DATA_ASSIGNEE_POINT_DATA_LEGACY] = point_data

            # Get or create periods container
            periods = point_data.setdefault(
                const.DATA_ASSIGNEE_POINT_DATA_PERIODS_LEGACY, {}
            )

            # --- Step 1: Set up all_time bucket ---
            # Get or create all_time period type
            all_time_periods = periods.setdefault(
                const.DATA_USER_POINT_PERIODS_ALL_TIME, {}
            )

            # Get or create the all_time bucket (nested: all_time.all_time)
            all_time_bucket = all_time_periods.setdefault(const.PERIOD_ALL_TIME, {})

            # Find highest known historical value from legacy sources:
            # 1. Legacy max_points_ever (v30/v31/v40 - direct assignee field)
            # 2. Current balance (fallback minimum)

            # Source 1: Legacy max_points_ever (the original field in v30/v31/v40beta1)
            legacy_max_points = float(
                assignee_info.get(const.DATA_ASSIGNEE_MAX_POINTS_EVER_LEGACY, 0.0)
            )

            # Use max_points_ever if available, otherwise fall back to current balance
            historical_earned = max(legacy_max_points, current_balance)

            const.LOGGER.debug(
                "  %s: max_points_ever=%.2f, current=%.2f, using=%.2f",
                assignee_name,
                legacy_max_points,
                current_balance,
                historical_earned,
            )

            # MIGRATION STRATEGY:
            # points_earned = highest known historical value (represents all earnings ever)
            # points_spent = offset to bring net down to current balance
            # by_source.other = current balance (net pre-migration activity, unknown +/-)
            # Math: earned + spent = current_balance
            #
            # Example: highest=2980, current=1504 → earned=2980, spent=-1476
            # Check: 2980 + (-1476) = 1504 ✓
            calculated_spent = current_balance - historical_earned

            # ALWAYS overwrite to ensure clean state
            all_time_bucket[const.DATA_USER_POINT_PERIOD_POINTS_EARNED] = (
                historical_earned
            )
            all_time_bucket[const.DATA_USER_POINT_PERIOD_POINTS_SPENT] = (
                calculated_spent
            )
            all_time_bucket[const.DATA_USER_POINT_PERIOD_BY_SOURCE] = {
                const.POINTS_SOURCE_OTHER: current_balance
            }
            all_time_bucket[const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE] = (
                historical_earned
            )

            stats_migrated += 1

            # Delete legacy point_stats if present
            if const.DATA_ASSIGNEE_POINT_STATS_LEGACY in assignee_info:
                del assignee_info[const.DATA_ASSIGNEE_POINT_STATS_LEGACY]

            const.LOGGER.debug(
                "  Set all_time for %s: earned=%.2f, spent=%.2f, net=%.2f, highest=%.2f",
                assignee_name,
                historical_earned,
                calculated_spent,
                current_balance,
                all_time_bucket[const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE],
            )

            # --- Step 2: Convert points_total → points_earned in all period buckets ---
            for _period_type, period_buckets in periods.items():
                if not isinstance(period_buckets, dict):
                    continue

                for _bucket_id, bucket_data in period_buckets.items():
                    if not isinstance(bucket_data, dict):
                        continue

                    # Check for legacy points_total field
                    if (
                        const.DATA_ASSIGNEE_POINT_DATA_PERIOD_POINTS_TOTAL_LEGACY
                        in bucket_data
                    ):
                        total = bucket_data.pop(
                            const.DATA_ASSIGNEE_POINT_DATA_PERIOD_POINTS_TOTAL_LEGACY
                        )

                        # points_total was net (earned + spent where spent is negative)
                        # For non-all_time buckets, treat positive as earned, negative as spent
                        if (
                            const.DATA_USER_POINT_PERIOD_POINTS_EARNED
                            not in bucket_data
                        ):
                            if total >= 0:
                                bucket_data[
                                    const.DATA_USER_POINT_PERIOD_POINTS_EARNED
                                ] = total
                                bucket_data[
                                    const.DATA_USER_POINT_PERIOD_POINTS_SPENT
                                ] = 0
                            else:
                                bucket_data[
                                    const.DATA_USER_POINT_PERIOD_POINTS_EARNED
                                ] = 0
                                bucket_data[
                                    const.DATA_USER_POINT_PERIOD_POINTS_SPENT
                                ] = total

                        buckets_converted += 1

        const.LOGGER.info(
            "  Stats consolidated: %d point_stats migrated, %d buckets converted",
            stats_migrated,
            buckets_converted,
        )

    def _strip_temporal_stats(self) -> None:
        """Remove temporal (clock-derived) fields from point_stats and chore_stats (Phase 7.5).

        Phase 7.5 Directive: Derivative Data is Ephemeral
        Clock-based statistics (today, week, month) MUST NOT be persisted to JSON storage.
        These values are now derived on-demand from period buckets (point_data.periods).

        High-Water Marks to KEEP (require persistence):
        - points_earned_all_time: Cumulative total (bucket aggregate)
        - points_spent_all_time: Cumulative spent (bucket aggregate)
        - highest_balance_all_time: All-time peak balance (cannot be recalculated from buckets)
        - longest_streak_all_time: Peak streak (cannot be recalculated from buckets)
        - approved_all_time: Cumulative chore completions (bucket aggregate)

        Temporal fields to STRIP (now derived from buckets):
        - Point stats: earned/spent/net_today/week/month/year, avg_*, by_source_today/week/month
        - Chore stats: approved/claimed/overdue/disapproved_today/week/month/year, avg_*
        - Most completed: most_completed_chore_week/month/year (all-time kept)
        """
        const.LOGGER.info(
            "Phase 9: Stripping temporal stats from storage (Phase 7.5 - The Great Stripping)"
        )

        # Define temporal fields to strip from point_stats
        # Note: We use the raw string values to match what's actually in storage
        point_stats_temporal_fields = [
            # Earned (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_POINT_STATS_EARNED_TODAY_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_EARNED_WEEK_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_EARNED_MONTH_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_EARNED_YEAR_LEGACY,
            # Spent (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_POINT_STATS_SPENT_TODAY_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_SPENT_WEEK_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_SPENT_MONTH_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_SPENT_YEAR_LEGACY,
            # Net (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_POINT_STATS_NET_TODAY_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_NET_WEEK_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_NET_MONTH_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_NET_YEAR_LEGACY,
            # By-source breakdowns (temporal periods)
            const.DATA_ASSIGNEE_POINT_STATS_BY_SOURCE_TODAY_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_BY_SOURCE_WEEK_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_BY_SOURCE_MONTH_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_BY_SOURCE_YEAR_LEGACY,
            # Averages (derived values)
            const.DATA_ASSIGNEE_POINT_STATS_AVG_PER_DAY_WEEK_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_AVG_PER_DAY_MONTH_LEGACY,
            const.DATA_ASSIGNEE_POINT_STATS_AVG_PER_CHORE_LEGACY,
        ]

        # Define temporal fields to strip from chore_stats (using LEGACY constants)
        chore_stats_temporal_fields = [
            # Approved counts (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_APPROVED_TODAY_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_APPROVED_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_APPROVED_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_APPROVED_YEAR_LEGACY,
            # Claimed counts (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_CLAIMED_TODAY_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_CLAIMED_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_CLAIMED_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_CLAIMED_YEAR_LEGACY,
            # Overdue counts (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_OVERDUE_TODAY_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_OVERDUE_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_OVERDUE_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_OVERDUE_YEAR_LEGACY,
            # Disapproved counts (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_DISAPPROVED_TODAY_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_DISAPPROVED_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_DISAPPROVED_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_DISAPPROVED_YEAR_LEGACY,
            # Total points from chores (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_TODAY_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_YEAR_LEGACY,
            # Most completed chore (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_MOST_COMPLETED_CHORE_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_MOST_COMPLETED_CHORE_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_MOST_COMPLETED_CHORE_YEAR_LEGACY,
            # Longest streaks (temporal periods - all-time stays)
            const.DATA_ASSIGNEE_CHORE_STATS_LONGEST_STREAK_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_LONGEST_STREAK_MONTH_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_LONGEST_STREAK_YEAR_LEGACY,
            # Averages (derived values)
            const.DATA_ASSIGNEE_CHORE_STATS_AVG_PER_DAY_WEEK_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_AVG_PER_DAY_MONTH_LEGACY,
            # Current counts (live state, not historical)
            const.DATA_ASSIGNEE_CHORE_STATS_CURRENT_DUE_TODAY_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_CURRENT_OVERDUE_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_CURRENT_CLAIMED_LEGACY,
            const.DATA_ASSIGNEE_CHORE_STATS_CURRENT_APPROVED_LEGACY,
        ]

        assignees_data = self.coordinator._data.get(const.DATA_USERS, {})
        assignees_processed = 0
        point_fields_removed = 0
        chore_fields_removed = 0

        for assignee_id, assignee_info in assignees_data.items():
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)
            assignee_had_changes = False

            # Strip temporal fields from point_stats
            point_stats = assignee_info.get(const.DATA_ASSIGNEE_POINT_STATS_LEGACY, {})
            for field in point_stats_temporal_fields:
                if field in point_stats:
                    del point_stats[field]
                    point_fields_removed += 1
                    assignee_had_changes = True

            # Strip temporal fields from chore_stats
            chore_stats = assignee_info.get(const.DATA_ASSIGNEE_CHORE_STATS_LEGACY, {})
            for field in chore_stats_temporal_fields:
                if field in chore_stats:
                    del chore_stats[field]
                    chore_fields_removed += 1
                    assignee_had_changes = True

            if assignee_had_changes:
                assignees_processed += 1
                const.LOGGER.debug(
                    "Stripped temporal stats from assignee '%s'",
                    assignee_name,
                )

        total_removed = point_fields_removed + chore_fields_removed
        if total_removed > 0:
            const.LOGGER.info(
                "Phase 9 complete: Removed %s temporal fields from %s assignees "
                "(point_stats: %s, chore_stats: %s)",
                total_removed,
                assignees_processed,
                point_fields_removed,
                chore_fields_removed,
            )
        else:
            const.LOGGER.debug(
                "Phase 9 complete: No temporal stats fields found to strip (already clean)"
            )

    # -------------------------------------------------------------------------------------
    # Migration-only methods (extracted from coordinator.py)
    # These methods are ONLY called during pre-v0.5.0 migrations
    # -------------------------------------------------------------------------------------

    def remove_deprecated_entities(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Remove old/deprecated sensor entities from the entity registry that are no longer used."""

        ent_reg = er.async_get(hass)

        # Get only entities from this config entry (not all system entities)
        entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

        for entity_entry in entities:
            # No type guard needed - we control all our unique_ids (all strings)
            if any(
                entity_entry.unique_id.endswith(suffix)
                for suffix in const.ENTITY_SUFFIXES_LEGACY
            ):
                ent_reg.async_remove(entity_entry.entity_id)
                const.LOGGER.debug(
                    "DEBUG: Removed deprecated Entity '%s', UID '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )

    def remove_deprecated_button_entities(self) -> None:
        """Remove dynamic button entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Chore Buttons ---
        # For each chore, create expected unique IDs for claim, approve, and disapprove buttons
        for chore_id, chore_info in self.coordinator.chores_data.items():
            for assignee_id in chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, []):
                # Expected unique_id formats:
                uid_claim = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}"
                uid_approve = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}"
                uid_disapprove = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{chore_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE}"
                allowed_uids.update({uid_claim, uid_approve, uid_disapprove})

        # --- Reward Buttons ---
        # For each assignee and reward, add expected unique IDs for reward claim, approve, and disapprove buttons.
        for assignee_id in self.coordinator.assignees_data:
            for reward_id in self.coordinator.rewards_data:
                # The reward claim button might be built with a dedicated prefix:
                uid_claim = f"{self.coordinator.config_entry.entry_id}_{const.BUTTON_REWARD_PREFIX}{assignee_id}_{reward_id}"
                uid_approve = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE_REWARD}"
                uid_disapprove = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{reward_id}{const.BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD}"
                allowed_uids.update({uid_claim, uid_approve, uid_disapprove})

        # --- Penalty Buttons ---
        for assignee_id in self.coordinator.assignees_data:
            for penalty_id in self.coordinator.penalties_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{const.BUTTON_PENALTY_PREFIX}{assignee_id}_{penalty_id}"
                allowed_uids.add(uid)

        # --- Bonus Buttons ---
        for assignee_id in self.coordinator.assignees_data:
            for bonus_id in self.coordinator.bonuses_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{const.BUTTON_BONUS_PREFIX}{assignee_id}_{bonus_id}"
                allowed_uids.add(uid)

        # --- Points Adjust Buttons ---
        # Determine the list of adjustment delta values from configuration or defaults.
        raw_values = self.coordinator.config_entry.options.get(
            const.CONF_POINTS_ADJUST_VALUES
        )
        if not raw_values:
            points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        elif isinstance(raw_values, str):
            points_adjust_values = parse_points_adjust_values(raw_values)
            if not points_adjust_values:
                points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        elif isinstance(raw_values, list):
            try:
                points_adjust_values = [float(v) for v in raw_values]
            except (ValueError, TypeError):
                points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES
        else:
            points_adjust_values = const.DEFAULT_POINTS_ADJUST_VALUES

        for assignee_id in self.coordinator.assignees_data:
            for delta in points_adjust_values:
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}{LEGACY_BUTTON_UID_MIDFIX_ADJUST_POINTS}{delta}"
                allowed_uids.add(uid)

        # --- Now remove any button entity whose unique_id is not in allowed_uids ---
        entry_entities = er.async_entries_for_config_entry(
            ent_reg,
            self.coordinator.config_entry.entry_id,
        )
        for entity_entry in entry_entities:
            # Only check buttons from our platform (choreops)
            if entity_entry.platform != const.DOMAIN or entity_entry.domain != "button":
                continue

            # If this button doesn't match our whitelist, remove it
            # This catches old entities from previous configs, migrations, or different entry_ids
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Button '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_sensor_entities(self) -> None:
        """Remove dynamic sensor entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Chore Status Sensors ---
        # For each chore, create expected unique IDs for chore status sensors
        for chore_id, chore_info in self.coordinator.chores_data.items():
            for assignee_id in chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, []):
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{chore_id}{const.SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR}"
                allowed_uids.add(uid)

        # --- Shared Chore Global State Sensors ---
        for chore_id, chore_info in self.coordinator.chores_data.items():
            if (
                chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
                == const.COMPLETION_CRITERIA_SHARED
            ):
                uid = f"{self.coordinator.config_entry.entry_id}_{chore_id}{const.DATA_GLOBAL_STATE_SUFFIX}"
                allowed_uids.add(uid)

        # --- Reward Status Sensors ---
        for reward_id in self.coordinator.rewards_data:
            for assignee_id in self.coordinator.assignees_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{reward_id}{const.SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR}"
                allowed_uids.add(uid)

        # --- Penalty/Bonus Apply Sensors ---
        for assignee_id in self.coordinator.assignees_data:
            for penalty_id in self.coordinator.penalties_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{penalty_id}{const.SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR}"
                allowed_uids.add(uid)
            for bonus_id in self.coordinator.bonuses_data:
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{bonus_id}{const.SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR}"
                allowed_uids.add(uid)

        # --- Achievement Progress Sensors ---
        for achievement_id, achievement in self.coordinator.achievements_data.items():
            for assignee_id in achievement.get(
                const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, []
            ):
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{achievement_id}{const.SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR}"
                allowed_uids.add(uid)

        # --- Challenge Progress Sensors ---
        for challenge_id, challenge in self.coordinator.challenges_data.items():
            for assignee_id in challenge.get(
                const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
            ):
                uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{challenge_id}{const.SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR}"
                allowed_uids.add(uid)

        # --- Assignee-specific sensors (not dynamic based on chores/rewards) ---
        # These are created once per assignee and don't need validation against dynamic data
        for assignee_id in self.coordinator.assignees_data:
            # Standard assignee sensors
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_BADGES_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_MAX_POINTS_EVER_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_HIGHEST_STREAK_SENSOR}"
            )
            allowed_uids.add(
                f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER}"
            )

            # Badge progress sensors
            badge_progress_data = self.coordinator.assignees_data[assignee_id].get(
                const.DATA_USER_BADGE_PROGRESS, {}
            )
            for badge_id, progress_info in badge_progress_data.items():
                badge_type = progress_info.get(const.DATA_USER_BADGE_PROGRESS_TYPE)
                if badge_type != const.BADGE_TYPE_CUMULATIVE:
                    uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}_{badge_id}{const.SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR}"
                    allowed_uids.add(uid)

        # --- Global sensors (not assignee-specific) ---
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR}"
        )

        # --- Now remove any sensor entity whose unique_id is not in allowed_uids ---
        entry_entities = er.async_entries_for_config_entry(
            ent_reg,
            self.coordinator.config_entry.entry_id,
        )
        for entity_entry in entry_entities:
            # Only check sensors from our platform (choreops)
            if entity_entry.platform != const.DOMAIN or entity_entry.domain != "sensor":
                continue

            # If this sensor doesn't match our whitelist, remove it
            # This catches old entities from previous configs, migrations, or different entry_ids
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Sensor '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_calendar_entities(self) -> None:
        """Remove dynamic calendar entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Assignee Calendar Entities ---
        for assignee_id in self.coordinator.assignees_data:
            uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.CALENDAR_KC_UID_SUFFIX_CALENDAR}"
            allowed_uids.add(uid)

        # --- Now remove any calendar entity whose unique_id is not in allowed_uids ---
        entry_entities = er.async_entries_for_config_entry(
            ent_reg,
            self.coordinator.config_entry.entry_id,
        )
        for entity_entry in entry_entities:
            # Only check calendars from our platform (choreops)
            if (
                entity_entry.platform != const.DOMAIN
                or entity_entry.domain != "calendar"
            ):
                continue

            # If this calendar doesn't match our whitelist, remove it
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Calendar '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_datetime_entities(self) -> None:
        """Remove dynamic datetime entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Assignee Dashboard Date Helper Entities ---
        for assignee_id in self.coordinator.assignees_data:
            uid = f"{self.coordinator.config_entry.entry_id}_{assignee_id}{const.DATETIME_KC_UID_SUFFIX_DATE_HELPER}"
            allowed_uids.add(uid)

        # --- Now remove any datetime entity whose unique_id is not in allowed_uids ---
        entry_entities = er.async_entries_for_config_entry(
            ent_reg,
            self.coordinator.config_entry.entry_id,
        )
        for entity_entry in entry_entities:
            # Only check datetime from our platform (choreops)
            if (
                entity_entry.platform != const.DOMAIN
                or entity_entry.domain != "datetime"
            ):
                continue

            # If this datetime doesn't match our whitelist, remove it
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Datetime '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def remove_deprecated_select_entities(self) -> None:
        """Remove dynamic select entities that are not present in the current configuration."""
        ent_reg = er.async_get(self.coordinator.hass)

        # Build the set of expected unique_ids ("whitelist")
        allowed_uids = set()

        # --- Global Select Entities (system-level) ---
        # These are NOT assignee-specific
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_CHORES_SELECT}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_REWARDS_SELECT}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_PENALTIES_SELECT}"
        )
        allowed_uids.add(
            f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_SUFFIX_BONUSES_SELECT}"
        )

        # --- Assignee-specific Dashboard Helper Select Entities ---
        for assignee_id in self.coordinator.assignees_data:
            uid = f"{self.coordinator.config_entry.entry_id}{const.SELECT_KC_UID_MIDFIX_CHORES_SELECT_LEGACY}{assignee_id}"
            allowed_uids.add(uid)

        # --- Now remove any select entity whose unique_id is not in allowed_uids ---
        entry_entities = er.async_entries_for_config_entry(
            ent_reg,
            self.coordinator.config_entry.entry_id,
        )
        for entity_entry in entry_entities:
            # Only check selects from our platform (choreops)
            if entity_entry.platform != const.DOMAIN or entity_entry.domain != "select":
                continue

            # If this select doesn't match our whitelist, remove it
            if entity_entry.unique_id not in allowed_uids:
                const.LOGGER.info(
                    "INFO: Removing orphaned/deprecated Select '%s' with unique_id '%s'",
                    entity_entry.entity_id,
                    entity_entry.unique_id,
                )
                ent_reg.async_remove(entity_entry.entity_id)

    def _create_assignee(self, assignee_id: str, assignee_data: dict[str, Any]) -> None:
        """Create a new assignee entity during migration.

        This is a local copy for migration only - production code uses
        data_builders.build_user_assignment_profile() + direct storage writes.
        """
        self.coordinator._data[const.DATA_USERS][assignee_id] = {
            const.DATA_USER_NAME: assignee_data.get(
                const.DATA_USER_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_USER_POINTS: assignee_data.get(
                const.DATA_USER_POINTS, const.DEFAULT_ZERO
            ),
            const.DATA_USER_BADGES_EARNED: assignee_data.get(
                const.DATA_USER_BADGES_EARNED, {}
            ),
            const.DATA_USER_HA_USER_ID: assignee_data.get(const.DATA_USER_HA_USER_ID),
            const.DATA_USER_INTERNAL_ID: assignee_id,
            const.DATA_USER_POINTS_MULTIPLIER: assignee_data.get(
                const.DATA_USER_POINTS_MULTIPLIER,
                const.DEFAULT_ASSIGNEE_POINTS_MULTIPLIER,
            ),
            const.DATA_USER_PENALTY_APPLIES: assignee_data.get(
                const.DATA_USER_PENALTY_APPLIES, {}
            ),
            const.DATA_USER_BONUS_APPLIES: assignee_data.get(
                const.DATA_USER_BONUS_APPLIES, {}
            ),
            const.DATA_USER_REWARD_DATA: assignee_data.get(
                const.DATA_USER_REWARD_DATA, {}
            ),
            const.DATA_ASSIGNEE_ENABLE_NOTIFICATIONS_LEGACY: assignee_data.get(
                const.DATA_ASSIGNEE_ENABLE_NOTIFICATIONS_LEGACY, True
            ),
            const.DATA_USER_MOBILE_NOTIFY_SERVICE: assignee_data.get(
                const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            ),
            const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS: assignee_data.get(
                const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS, True
            ),
            # NOTE: DATA_KID_OVERDUE_CHORES removed - dead code, overdue tracked in chore_data[chore_id].state
        }

        const.LOGGER.debug(
            "DEBUG: Assignee Added (migration) - '%s', ID '%s'",
            self.coordinator._data[const.DATA_USERS][assignee_id][const.DATA_USER_NAME],
            assignee_id,
        )

    def _update_assignee(self, assignee_id: str, assignee_data: dict[str, Any]):
        """Update an existing assignee entity, only updating fields present in assignee_data."""

        assignees = self.coordinator._data.setdefault(const.DATA_USERS, {})
        existing = assignees.get(assignee_id, {})
        # Only update fields present in assignee_data, preserving all others
        existing.update(assignee_data)
        assignees[assignee_id] = existing

        assignee_name = existing.get(const.DATA_USER_NAME, const.SENTINEL_EMPTY)
        const.LOGGER.debug(
            "DEBUG: Assignee Updated - '%s', ID '%s'",
            assignee_name,
            assignee_id,
        )

    def _create_approver(self, approver_id: str, approver_data: dict[str, Any]):
        associated_assignees_ids = []
        for assignee_id in approver_data.get(const.DATA_USER_ASSOCIATED_USER_IDS, []):
            if assignee_id in self.coordinator.assignees_data:
                associated_assignees_ids.append(assignee_id)
            else:
                const.LOGGER.warning(
                    "WARNING: Approver '%s': Assignee ID '%s' not found. Skipping assignment to approver",
                    approver_data.get(const.DATA_USER_NAME, approver_id),
                    assignee_id,
                )

        self.coordinator._data[const.DATA_APPROVERS][approver_id] = {
            const.DATA_USER_NAME: approver_data.get(
                const.DATA_USER_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_USER_HA_USER_ID: approver_data.get(
                const.DATA_USER_HA_USER_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_USER_ASSOCIATED_USER_IDS: associated_assignees_ids,
            const.DATA_APPROVER_ENABLE_NOTIFICATIONS_LEGACY: approver_data.get(
                const.DATA_APPROVER_ENABLE_NOTIFICATIONS_LEGACY, True
            ),
            const.DATA_USER_MOBILE_NOTIFY_SERVICE: approver_data.get(
                const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            ),
            const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS: approver_data.get(
                const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
                True,
            ),
            const.DATA_USER_INTERNAL_ID: approver_id,
            # Approver chore capability fields (v0.6.0+)
            const.DATA_USER_DASHBOARD_LANGUAGE: approver_data.get(
                const.DATA_USER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
            const.DATA_USER_ENABLE_CHORE_WORKFLOW: approver_data.get(
                const.DATA_USER_ENABLE_CHORE_WORKFLOW,
                const.DEFAULT_USER_ENABLE_CHORE_WORKFLOW,
            ),
            const.DATA_USER_ENABLE_GAMIFICATION: approver_data.get(
                const.DATA_USER_ENABLE_GAMIFICATION,
                const.DEFAULT_USER_ENABLE_GAMIFICATION,
            ),
            LEGACY_APPROVER_LINKED_PROFILE_KEY: approver_data.get(
                LEGACY_APPROVER_LINKED_PROFILE_KEY
            ),
        }
        const.LOGGER.debug(
            "DEBUG: Approver Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_APPROVERS][approver_id][
                const.DATA_USER_NAME
            ],
            approver_id,
        )

    def _update_approver(self, approver_id: str, approver_data: dict[str, Any]):
        approver_info = self.coordinator._data[const.DATA_APPROVERS][approver_id]
        approver_info[const.DATA_USER_NAME] = approver_data.get(
            const.DATA_USER_NAME, approver_info[const.DATA_USER_NAME]
        )
        approver_info[const.DATA_USER_HA_USER_ID] = approver_data.get(
            const.DATA_USER_HA_USER_ID,
            approver_info[const.DATA_USER_HA_USER_ID],
        )

        # Update associated_assignees
        updated_assignees = []
        for assignee_id in approver_data.get(const.DATA_USER_ASSOCIATED_USER_IDS, []):
            if assignee_id in self.coordinator.assignees_data:
                updated_assignees.append(assignee_id)
            else:
                const.LOGGER.warning(
                    "WARNING: Approver '%s': Assignee ID '%s' not found. Skipping assignment to approver",
                    approver_info[const.DATA_USER_NAME],
                    assignee_id,
                )
        approver_info[const.DATA_USER_ASSOCIATED_USER_IDS] = updated_assignees
        approver_info[const.DATA_APPROVER_ENABLE_NOTIFICATIONS_LEGACY] = (
            approver_data.get(
                const.DATA_APPROVER_ENABLE_NOTIFICATIONS_LEGACY,
                approver_info.get(
                    const.DATA_APPROVER_ENABLE_NOTIFICATIONS_LEGACY, True
                ),
            )
        )
        approver_info[const.DATA_USER_MOBILE_NOTIFY_SERVICE] = approver_data.get(
            const.DATA_USER_MOBILE_NOTIFY_SERVICE,
            approver_info.get(
                const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            ),
        )
        approver_info[const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS] = approver_data.get(
            const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
            approver_info.get(const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS, True),
        )
        # Approver chore capability fields (v0.6.0+)
        approver_info[const.DATA_USER_DASHBOARD_LANGUAGE] = approver_data.get(
            const.DATA_USER_DASHBOARD_LANGUAGE,
            approver_info.get(
                const.DATA_USER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
        )
        approver_info[const.DATA_USER_ENABLE_CHORE_WORKFLOW] = approver_data.get(
            const.DATA_USER_ENABLE_CHORE_WORKFLOW,
            approver_info.get(
                const.DATA_USER_ENABLE_CHORE_WORKFLOW,
                const.DEFAULT_USER_ENABLE_CHORE_WORKFLOW,
            ),
        )
        approver_info[const.DATA_USER_ENABLE_GAMIFICATION] = approver_data.get(
            const.DATA_USER_ENABLE_GAMIFICATION,
            approver_info.get(
                const.DATA_USER_ENABLE_GAMIFICATION,
                const.DEFAULT_USER_ENABLE_GAMIFICATION,
            ),
        )
        # Update shadow assignee link if provided
        if LEGACY_APPROVER_LINKED_PROFILE_KEY in approver_data:
            approver_info[LEGACY_APPROVER_LINKED_PROFILE_KEY] = approver_data.get(
                LEGACY_APPROVER_LINKED_PROFILE_KEY
            )

        const.LOGGER.debug(
            "DEBUG: Approver Updated - '%s', ID '%s'",
            approver_info[const.DATA_USER_NAME],
            approver_id,
        )

    def _create_chore(self, chore_id: str, chore_data: dict[str, Any]):
        # Use data_builders to build complete chore structure with all defaults
        # For migration, we pass chore_data with internal_id already set
        chore_data[const.DATA_CHORE_INTERNAL_ID] = chore_id
        self.coordinator._data[const.DATA_CHORES][chore_id] = db.build_chore(
            chore_data, existing=None
        )
        const.LOGGER.debug(
            "DEBUG: Chore Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_CHORES][chore_id][const.DATA_CHORE_NAME],
            chore_id,
        )

    def _update_chore(self, chore_id: str, chore_data: dict[str, Any]):
        """Update chore data (simplified for migration - no notifications or reload detection)."""
        chore_info = self.coordinator._data[const.DATA_CHORES][chore_id]
        chore_info[const.DATA_CHORE_NAME] = chore_data.get(
            const.DATA_CHORE_NAME, chore_info[const.DATA_CHORE_NAME]
        )
        chore_info[const.DATA_CHORE_STATE] = chore_data.get(
            const.DATA_CHORE_STATE, chore_info[const.DATA_CHORE_STATE]
        )
        chore_info[const.DATA_CHORE_DEFAULT_POINTS] = chore_data.get(
            const.DATA_CHORE_DEFAULT_POINTS, chore_info[const.DATA_CHORE_DEFAULT_POINTS]
        )
        chore_info[const.DATA_CHORE_APPROVAL_RESET_TYPE] = chore_data.get(
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            chore_info.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
        )
        chore_info[const.DATA_CHORE_DESCRIPTION] = chore_data.get(
            const.DATA_CHORE_DESCRIPTION, chore_info[const.DATA_CHORE_DESCRIPTION]
        )
        chore_info[const.DATA_CHORE_LABELS] = chore_data.get(
            const.DATA_CHORE_LABELS,
            chore_info.get(const.DATA_CHORE_LABELS, []),
        )
        chore_info[const.DATA_CHORE_ICON] = chore_data.get(
            const.DATA_CHORE_ICON, chore_info[const.DATA_CHORE_ICON]
        )

        # assigned_assignees now contains UUIDs directly from flow helpers (no conversion needed)
        # Simplified for migration - just update the list directly (no entity cleanup needed)
        chore_info[const.DATA_CHORE_ASSIGNED_USER_IDS] = chore_data.get(
            const.DATA_CHORE_ASSIGNED_USER_IDS,
            chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, []),
        )
        chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY,
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY],
        )

        # Handle due_date based on completion criteria to avoid KeyError
        completion_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,  # Legacy default
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # For INDEPENDENT chores: chore-level due_date should remain None
            # (per_assignee_due_dates are authoritative)
            chore_info[const.DATA_CHORE_DUE_DATE] = None
        else:
            # For SHARED chores: update chore-level due_date normally
            chore_info[const.DATA_CHORE_DUE_DATE] = chore_data.get(
                const.DATA_CHORE_DUE_DATE, chore_info.get(const.DATA_CHORE_DUE_DATE)
            )

        chore_info[const.DATA_CHORE_LAST_COMPLETED] = chore_data.get(
            const.DATA_CHORE_LAST_COMPLETED,
            chore_info.get(const.DATA_CHORE_LAST_COMPLETED),
        )
        chore_info[const.DATA_CHORE_LAST_CLAIMED] = chore_data.get(
            const.DATA_CHORE_LAST_CLAIMED, chore_info.get(const.DATA_CHORE_LAST_CLAIMED)
        )
        chore_info[const.DATA_CHORE_APPLICABLE_DAYS] = chore_data.get(
            const.DATA_CHORE_APPLICABLE_DAYS,
            chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
        )
        chore_info[const.DATA_CHORE_NOTIFY_ON_CLAIM] = chore_data.get(
            const.DATA_CHORE_NOTIFY_ON_CLAIM,
            chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
            ),
        )
        chore_info[const.DATA_CHORE_NOTIFY_ON_APPROVAL] = chore_data.get(
            const.DATA_CHORE_NOTIFY_ON_APPROVAL,
            chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            ),
        )
        chore_info[const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL] = chore_data.get(
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
            chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
            ),
        )

        if chore_info[const.DATA_CHORE_RECURRING_FREQUENCY] in (
            const.FREQUENCY_CUSTOM,
            const.FREQUENCY_CUSTOM_FROM_COMPLETE,
        ):
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL] = chore_data.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            )
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = chore_data.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            )
        else:
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL] = None
            chore_info[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] = None

        # CFE-2026-001: Handle DAILY_MULTI times field
        if (
            chore_info[const.DATA_CHORE_RECURRING_FREQUENCY]
            == const.FREQUENCY_DAILY_MULTI
        ):
            chore_info[const.DATA_CHORE_DAILY_MULTI_TIMES] = chore_data.get(
                const.DATA_CHORE_DAILY_MULTI_TIMES,
                chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, ""),
            )
        else:
            # Clear times if frequency changed away from DAILY_MULTI
            chore_info[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

        # Component 8: Handle completion_criteria changes (INDEPENDENT ↔ SHARED)
        old_criteria = chore_info.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,  # Legacy default
        )
        new_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            old_criteria,  # Keep existing if not provided
        )

        # Update completion_criteria
        chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = new_criteria

        # Update per_assignee_due_dates if provided in chore_data (from flow)
        if const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES in chore_data:
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = chore_data[
                const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES
            ]

        # PKAD-2026-001: Update per_assignee_applicable_days if provided (from flow)
        if const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS in chore_data:
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS] = chore_data[
                const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS
            ]

        # PKAD-2026-001: Update per_assignee_daily_multi_times if provided (from flow)
        if const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES in chore_data:
            chore_info[const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES] = chore_data[
                const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES
            ]

        const.LOGGER.debug(
            "DEBUG: Chore Updated - '%s', ID '%s'",
            chore_info[const.DATA_CHORE_NAME],
            chore_id,
        )

    def _create_badge(self, badge_id: str, badge_data: dict[str, Any]):
        """Create a new badge entity."""
        self.coordinator._data.setdefault(const.DATA_BADGES, {})[badge_id] = badge_data
        const.LOGGER.debug(
            "DEBUG: Badge Created - '%s', ID '%s'",
            badge_data.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY),
            badge_id,
        )

    def _update_badge(self, badge_id: str, badge_data: dict[str, Any]):
        """Update an existing badge entity, only updating fields present in badge_data."""
        badges = self.coordinator._data.setdefault(const.DATA_BADGES, {})
        existing = badges.get(badge_id, {})
        existing.update(badge_data)
        badges[badge_id] = existing
        const.LOGGER.debug(
            "DEBUG: Badge Updated - '%s', ID '%s'",
            existing.get(const.DATA_BADGE_NAME, const.SENTINEL_EMPTY),
            badge_id,
        )

    def _create_reward(self, reward_id: str, reward_data: dict[str, Any]):
        self.coordinator._data[const.DATA_REWARDS][reward_id] = {
            const.DATA_REWARD_NAME: reward_data.get(
                const.DATA_REWARD_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_REWARD_COST: reward_data.get(
                const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST
            ),
            const.DATA_REWARD_DESCRIPTION: reward_data.get(
                const.DATA_REWARD_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_REWARD_LABELS: reward_data.get(const.DATA_REWARD_LABELS, []),
            const.DATA_REWARD_ICON: reward_data.get(
                const.DATA_REWARD_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_REWARD_INTERNAL_ID: reward_id,
        }
        const.LOGGER.debug(
            "DEBUG: Reward Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_REWARDS][reward_id][
                const.DATA_REWARD_NAME
            ],
            reward_id,
        )

    def _update_reward(self, reward_id: str, reward_data: dict[str, Any]):
        reward_info = self.coordinator._data[const.DATA_REWARDS][reward_id]
        reward_info[const.DATA_REWARD_NAME] = reward_data.get(
            const.DATA_REWARD_NAME, reward_info[const.DATA_REWARD_NAME]
        )
        reward_info[const.DATA_REWARD_COST] = reward_data.get(
            const.DATA_REWARD_COST, reward_info[const.DATA_REWARD_COST]
        )
        reward_info[const.DATA_REWARD_DESCRIPTION] = reward_data.get(
            const.DATA_REWARD_DESCRIPTION, reward_info[const.DATA_REWARD_DESCRIPTION]
        )
        reward_info[const.DATA_REWARD_LABELS] = reward_data.get(
            const.DATA_REWARD_LABELS, reward_info.get(const.DATA_REWARD_LABELS, [])
        )
        reward_info[const.DATA_REWARD_ICON] = reward_data.get(
            const.DATA_REWARD_ICON, reward_info[const.DATA_REWARD_ICON]
        )
        const.LOGGER.debug(
            "DEBUG: Reward Updated - '%s', ID '%s'",
            reward_info[const.DATA_REWARD_NAME],
            reward_id,
        )

    def _create_bonus(self, bonus_id: str, bonus_data: dict[str, Any]):
        self.coordinator._data[const.DATA_BONUSES][bonus_id] = {
            const.DATA_BONUS_NAME: bonus_data.get(
                const.DATA_BONUS_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_BONUS_POINTS: bonus_data.get(
                const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS
            ),
            const.DATA_BONUS_DESCRIPTION: bonus_data.get(
                const.DATA_BONUS_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_BONUS_LABELS: bonus_data.get(const.DATA_BONUS_LABELS, []),
            const.DATA_BONUS_ICON: bonus_data.get(
                const.DATA_BONUS_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_BONUS_INTERNAL_ID: bonus_id,
        }
        const.LOGGER.debug(
            "DEBUG: Bonus Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_BONUSES][bonus_id][const.DATA_BONUS_NAME],
            bonus_id,
        )

    def _update_bonus(self, bonus_id: str, bonus_data: dict[str, Any]):
        bonus_info = self.coordinator._data[const.DATA_BONUSES][bonus_id]
        bonus_info[const.DATA_BONUS_NAME] = bonus_data.get(
            const.DATA_BONUS_NAME, bonus_info[const.DATA_BONUS_NAME]
        )
        bonus_info[const.DATA_BONUS_POINTS] = bonus_data.get(
            const.DATA_BONUS_POINTS, bonus_info[const.DATA_BONUS_POINTS]
        )
        bonus_info[const.DATA_BONUS_DESCRIPTION] = bonus_data.get(
            const.DATA_BONUS_DESCRIPTION, bonus_info[const.DATA_BONUS_DESCRIPTION]
        )
        bonus_info[const.DATA_BONUS_LABELS] = bonus_data.get(
            const.DATA_BONUS_LABELS, bonus_info.get(const.DATA_BONUS_LABELS, [])
        )
        bonus_info[const.DATA_BONUS_ICON] = bonus_data.get(
            const.DATA_BONUS_ICON, bonus_info[const.DATA_BONUS_ICON]
        )
        const.LOGGER.debug(
            "DEBUG: Bonus Updated - '%s', ID '%s'",
            bonus_info[const.DATA_BONUS_NAME],
            bonus_id,
        )

    def _create_penalty(self, penalty_id: str, penalty_data: dict[str, Any]):
        self.coordinator._data[const.DATA_PENALTIES][penalty_id] = {
            const.DATA_PENALTY_NAME: penalty_data.get(
                const.DATA_PENALTY_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_PENALTY_POINTS: penalty_data.get(
                const.DATA_PENALTY_POINTS, -const.DEFAULT_PENALTY_POINTS
            ),
            const.DATA_PENALTY_DESCRIPTION: penalty_data.get(
                const.DATA_PENALTY_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_PENALTY_LABELS: penalty_data.get(const.DATA_PENALTY_LABELS, []),
            const.DATA_PENALTY_ICON: penalty_data.get(
                const.DATA_PENALTY_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_PENALTY_INTERNAL_ID: penalty_id,
        }
        const.LOGGER.debug(
            "DEBUG: Penalty Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_PENALTIES][penalty_id][
                const.DATA_PENALTY_NAME
            ],
            penalty_id,
        )

    def _update_penalty(self, penalty_id: str, penalty_data: dict[str, Any]):
        penalty_info = self.coordinator._data[const.DATA_PENALTIES][penalty_id]
        penalty_info[const.DATA_PENALTY_NAME] = penalty_data.get(
            const.DATA_PENALTY_NAME, penalty_info[const.DATA_PENALTY_NAME]
        )
        penalty_info[const.DATA_PENALTY_POINTS] = penalty_data.get(
            const.DATA_PENALTY_POINTS, penalty_info[const.DATA_PENALTY_POINTS]
        )
        penalty_info[const.DATA_PENALTY_DESCRIPTION] = penalty_data.get(
            const.DATA_PENALTY_DESCRIPTION, penalty_info[const.DATA_PENALTY_DESCRIPTION]
        )
        penalty_info[const.DATA_PENALTY_LABELS] = penalty_data.get(
            const.DATA_PENALTY_LABELS, penalty_info.get(const.DATA_PENALTY_LABELS, [])
        )
        penalty_info[const.DATA_PENALTY_ICON] = penalty_data.get(
            const.DATA_PENALTY_ICON, penalty_info[const.DATA_PENALTY_ICON]
        )
        const.LOGGER.debug(
            "DEBUG: Penalty Updated - '%s', ID '%s'",
            penalty_info[const.DATA_PENALTY_NAME],
            penalty_id,
        )

    def _create_achievement(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ):
        self.coordinator._data[const.DATA_ACHIEVEMENTS][achievement_id] = {
            const.DATA_ACHIEVEMENT_NAME: achievement_data.get(
                const.DATA_ACHIEVEMENT_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_DESCRIPTION: achievement_data.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_LABELS: achievement_data.get(
                const.DATA_ACHIEVEMENT_LABELS, []
            ),
            const.DATA_ACHIEVEMENT_ICON: achievement_data.get(
                const.DATA_ACHIEVEMENT_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: achievement_data.get(
                const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, []
            ),
            const.DATA_ACHIEVEMENT_TYPE: achievement_data.get(
                const.DATA_ACHIEVEMENT_TYPE, const.ACHIEVEMENT_TYPE_STREAK
            ),
            const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: achievement_data.get(
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_CRITERIA: achievement_data.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.DATA_ACHIEVEMENT_TARGET_VALUE: achievement_data.get(
                const.DATA_ACHIEVEMENT_TARGET_VALUE, const.DEFAULT_ACHIEVEMENT_TARGET
            ),
            const.DATA_ACHIEVEMENT_REWARD_POINTS: achievement_data.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS,
                const.DEFAULT_ACHIEVEMENT_REWARD_POINTS,
            ),
            const.DATA_ACHIEVEMENT_PROGRESS: achievement_data.get(
                const.DATA_ACHIEVEMENT_PROGRESS, {}
            ),
            const.DATA_ACHIEVEMENT_INTERNAL_ID: achievement_id,
        }
        const.LOGGER.debug(
            "DEBUG: Achievement Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_ACHIEVEMENTS][achievement_id][
                const.DATA_ACHIEVEMENT_NAME
            ],
            achievement_id,
        )

    def _update_achievement(
        self, achievement_id: str, achievement_data: dict[str, Any]
    ):
        achievement_info = self.coordinator._data[const.DATA_ACHIEVEMENTS][
            achievement_id
        ]
        achievement_info[const.DATA_ACHIEVEMENT_NAME] = achievement_data.get(
            const.DATA_ACHIEVEMENT_NAME, achievement_info[const.DATA_ACHIEVEMENT_NAME]
        )
        achievement_info[const.DATA_ACHIEVEMENT_DESCRIPTION] = achievement_data.get(
            const.DATA_ACHIEVEMENT_DESCRIPTION,
            achievement_info[const.DATA_ACHIEVEMENT_DESCRIPTION],
        )
        achievement_info[const.DATA_ACHIEVEMENT_LABELS] = achievement_data.get(
            const.DATA_ACHIEVEMENT_LABELS,
            achievement_info.get(const.DATA_ACHIEVEMENT_LABELS, []),
        )
        achievement_info[const.DATA_ACHIEVEMENT_ICON] = achievement_data.get(
            const.DATA_ACHIEVEMENT_ICON, achievement_info[const.DATA_ACHIEVEMENT_ICON]
        )
        achievement_info[const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS] = (
            achievement_data.get(
                const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
                achievement_info[const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS],
            )
        )
        achievement_info[const.DATA_ACHIEVEMENT_TYPE] = achievement_data.get(
            const.DATA_ACHIEVEMENT_TYPE, achievement_info[const.DATA_ACHIEVEMENT_TYPE]
        )
        achievement_info[const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID] = (
            achievement_data.get(
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID,
                achievement_info.get(
                    const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
                ),
            )
        )
        achievement_info[const.DATA_ACHIEVEMENT_CRITERIA] = achievement_data.get(
            const.DATA_ACHIEVEMENT_CRITERIA,
            achievement_info[const.DATA_ACHIEVEMENT_CRITERIA],
        )
        achievement_info[const.DATA_ACHIEVEMENT_TARGET_VALUE] = achievement_data.get(
            const.DATA_ACHIEVEMENT_TARGET_VALUE,
            achievement_info[const.DATA_ACHIEVEMENT_TARGET_VALUE],
        )
        achievement_info[const.DATA_ACHIEVEMENT_REWARD_POINTS] = achievement_data.get(
            const.DATA_ACHIEVEMENT_REWARD_POINTS,
            achievement_info[const.DATA_ACHIEVEMENT_REWARD_POINTS],
        )
        const.LOGGER.debug(
            "DEBUG: Achievement Updated - '%s', ID '%s'",
            achievement_info[const.DATA_ACHIEVEMENT_NAME],
            achievement_id,
        )

    def _create_challenge(self, challenge_id: str, challenge_data: dict[str, Any]):
        self.coordinator._data[const.DATA_CHALLENGES][challenge_id] = {
            const.DATA_CHALLENGE_NAME: challenge_data.get(
                const.DATA_CHALLENGE_NAME, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_DESCRIPTION: challenge_data.get(
                const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_LABELS: challenge_data.get(
                const.DATA_CHALLENGE_LABELS, []
            ),
            const.DATA_CHALLENGE_ICON: challenge_data.get(
                const.DATA_CHALLENGE_ICON, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_ASSIGNED_USER_IDS: challenge_data.get(
                const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
            ),
            const.DATA_CHALLENGE_TYPE: challenge_data.get(
                const.DATA_CHALLENGE_TYPE, const.CHALLENGE_TYPE_DAILY_MIN
            ),
            const.DATA_CHALLENGE_SELECTED_CHORE_ID: challenge_data.get(
                const.DATA_CHALLENGE_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_CRITERIA: challenge_data.get(
                const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.DATA_CHALLENGE_TARGET_VALUE: challenge_data.get(
                const.DATA_CHALLENGE_TARGET_VALUE, const.DEFAULT_CHALLENGE_TARGET
            ),
            const.DATA_CHALLENGE_REWARD_POINTS: challenge_data.get(
                const.DATA_CHALLENGE_REWARD_POINTS,
                const.DEFAULT_CHALLENGE_REWARD_POINTS,
            ),
            const.DATA_CHALLENGE_START_DATE: (
                challenge_data.get(const.DATA_CHALLENGE_START_DATE)
                if challenge_data.get(const.DATA_CHALLENGE_START_DATE) not in [None, {}]
                else None
            ),
            const.DATA_CHALLENGE_END_DATE: (
                challenge_data.get(const.DATA_CHALLENGE_END_DATE)
                if challenge_data.get(const.DATA_CHALLENGE_END_DATE) not in [None, {}]
                else None
            ),
            const.DATA_CHALLENGE_PROGRESS: challenge_data.get(
                const.DATA_CHALLENGE_PROGRESS, {}
            ),
            const.DATA_CHALLENGE_INTERNAL_ID: challenge_id,
        }
        const.LOGGER.debug(
            "DEBUG: Challenge Added - '%s', ID '%s'",
            self.coordinator._data[const.DATA_CHALLENGES][challenge_id][
                const.DATA_CHALLENGE_NAME
            ],
            challenge_id,
        )

    def _update_challenge(self, challenge_id: str, challenge_data: dict[str, Any]):
        challenge_info = self.coordinator._data[const.DATA_CHALLENGES][challenge_id]
        challenge_info[const.DATA_CHALLENGE_NAME] = challenge_data.get(
            const.DATA_CHALLENGE_NAME, challenge_info[const.DATA_CHALLENGE_NAME]
        )
        challenge_info[const.DATA_CHALLENGE_DESCRIPTION] = challenge_data.get(
            const.DATA_CHALLENGE_DESCRIPTION,
            challenge_info[const.DATA_CHALLENGE_DESCRIPTION],
        )
        challenge_info[const.DATA_CHALLENGE_LABELS] = challenge_data.get(
            const.DATA_CHALLENGE_LABELS,
            challenge_info.get(const.DATA_CHALLENGE_LABELS, []),
        )
        challenge_info[const.DATA_CHALLENGE_ICON] = challenge_data.get(
            const.DATA_CHALLENGE_ICON, challenge_info[const.DATA_CHALLENGE_ICON]
        )
        challenge_info[const.DATA_CHALLENGE_ASSIGNED_USER_IDS] = challenge_data.get(
            const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
            challenge_info[const.DATA_CHALLENGE_ASSIGNED_USER_IDS],
        )
        challenge_info[const.DATA_CHALLENGE_TYPE] = challenge_data.get(
            const.DATA_CHALLENGE_TYPE, challenge_info[const.DATA_CHALLENGE_TYPE]
        )
        challenge_info[const.DATA_CHALLENGE_SELECTED_CHORE_ID] = challenge_data.get(
            const.DATA_CHALLENGE_SELECTED_CHORE_ID,
            challenge_info.get(
                const.DATA_CHALLENGE_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
        )
        challenge_info[const.DATA_CHALLENGE_CRITERIA] = challenge_data.get(
            const.DATA_CHALLENGE_CRITERIA, challenge_info[const.DATA_CHALLENGE_CRITERIA]
        )
        challenge_info[const.DATA_CHALLENGE_TARGET_VALUE] = challenge_data.get(
            const.DATA_CHALLENGE_TARGET_VALUE,
            challenge_info[const.DATA_CHALLENGE_TARGET_VALUE],
        )
        challenge_info[const.DATA_CHALLENGE_REWARD_POINTS] = challenge_data.get(
            const.DATA_CHALLENGE_REWARD_POINTS,
            challenge_info[const.DATA_CHALLENGE_REWARD_POINTS],
        )
        challenge_info[const.DATA_CHALLENGE_START_DATE] = (
            challenge_data.get(const.DATA_CHALLENGE_START_DATE)
            if challenge_data.get(const.DATA_CHALLENGE_START_DATE) not in [None, {}]
            else None
        )
        challenge_info[const.DATA_CHALLENGE_END_DATE] = (
            challenge_data.get(const.DATA_CHALLENGE_END_DATE)
            if challenge_data.get(const.DATA_CHALLENGE_END_DATE) not in [None, {}]
            else None
        )
        const.LOGGER.debug(
            "DEBUG: Challenge Updated - '%s', ID '%s'",
            challenge_info[const.DATA_CHALLENGE_NAME],
            challenge_id,
        )


# ================================================================================================
# UID Suffix Migration (v0.5.0) - Standalone Entity Registry Update
# ================================================================================================


@callback
def async_migrate_uid_suffixes_v0_5_0(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Migrate entity unique_ids from generic to explicit suffixes (v0.5.1).

    This one-time migration updates entity unique_ids to use entity-type-scoped
    suffixes (e.g., '_status' → '_chore_status') to enable reliable pattern matching
    for shadow assignee entity gating logic.

    The migration is idempotent - entities with new suffixes are skipped.
    Gated by schema version check in __init__.py (only runs if schema < 43).

    Args:
        hass: Home Assistant instance
        config_entry: ChoreOps config entry

    """
    # Mapping of old UID suffixes → new UID suffixes (all hardcoded for migration)
    # CRITICAL: Old suffixes must be EXACT legacy patterns, not substrings of new ones
    uid_migration_map: dict[str, str] = {
        # BUTTONS - Chore/Reward/Entity actions
        # NOTE: These generic suffixes like "_approve" can match the end of new
        # suffixes like "_chore_approve", so we MUST check for new suffixes first
        "_approve": "_chore_approve",
        "_claim": "_chore_claim",
        "_unclaim": "_chore_unclaim",
        "_approve_reward": "_reward_approve",
        "_approve_all_rewards": "_assignee_approve_all_rewards",
        "_remove_assignee_rewards": "_assignee_remove_all_rewards",
        "_claim_partial_reward": "_reward_claim_partial",
        "_delete_chore": "_chore_delete",
        "_delete_reward": "_reward_delete",
        "_delete_bonus": "_bonus_delete",
        "_delete_penalty": "_penalty_delete",
        "_delete_achievement": "_achievement_delete",
        "_delete_badge": "_badge_delete",
        "_delete_challenge": "_challenge_delete",
        "_reset_badge": "_badge_reset",
        # SENSORS - Entity status
        "_status": "_chore_status",
        "_reward_status": "_reward_status",
        "_bonus_status": "_bonus_status",
        "_penalty_status": "_penalty_status",
        "_achievement_status": "_achievement_status",
        "_badge_status": "_badge_status",
        "_challenge_status": "_challenge_status",
        # SENSORS - Assignee aggregations
        "_chores": "_assignee_chores_summary",
        "_points": "_assignee_points",
        "_dashboard_helper": "_assignee_dashboard_helper",
        # SELECTS
        "_chores_select": "_select_chores",
        "_rewards_select": "_select_rewards",
        # DATETIME
        "_date_helper": "_dashboard_datetime_picker",
        # CALENDAR
        "_calendar": "_assignee_calendar",
    }

    # Build set of NEW suffixes (migration targets) for idempotency check
    # If entity already ends with a NEW suffix, it's already migrated - skip it
    new_suffixes: set[str] = set(uid_migration_map.values())

    const.LOGGER.info(
        "Starting UID suffix migration (v0.5.0) for config entry %s",
        config_entry.entry_id,
    )

    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    migration_count = 0
    skip_count = 0
    already_migrated_count = 0

    for entry in registry_entries:
        # IDEMPOTENCY CHECK: Skip if entity already has a NEW suffix
        # This prevents re-migrating already-migrated entities
        has_new_suffix = any(
            entry.unique_id.endswith(new_suffix) for new_suffix in new_suffixes
        )
        if has_new_suffix:
            already_migrated_count += 1
            continue

        # Check if unique_id ends with any old suffix
        old_suffix = None
        for old, _ in uid_migration_map.items():
            if entry.unique_id.endswith(old):
                old_suffix = old
                break

        if not old_suffix:
            skip_count += 1
            continue

        # Build new unique_id by replacing suffix
        new_unique_id = (
            entry.unique_id.removesuffix(old_suffix) + uid_migration_map[old_suffix]
        )

        const.LOGGER.debug(
            "Migrating entity '%s' unique_id from '%s' to '%s'",
            entry.entity_id,
            entry.unique_id,
            new_unique_id,
        )

        try:
            entity_registry.async_update_entity(
                entry.entity_id, new_unique_id=new_unique_id
            )
            migration_count += 1
        except ValueError as err:
            # Conflict: new unique_id already exists (shouldn't happen in practice)
            const.LOGGER.warning(
                "Cannot migrate entity '%s' from '%s' to '%s': %s",
                entry.entity_id,
                entry.unique_id,
                new_unique_id,
                err,
            )

    const.LOGGER.info(
        "UID suffix migration (v0.5.1) complete: %s migrated, %s already done, %s skipped",
        migration_count,
        already_migrated_count,
        skip_count,
    )
