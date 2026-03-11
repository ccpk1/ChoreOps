"""Tests for schema45 user-unification migration contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.migration_pre_v50 import (
    PreV50Migrator,
    async_apply_schema45_user_contract,
)
from custom_components.choreops.migration_pre_v50_constants import (
    DATA_USER_BADGE_PROGRESS_ASSIGNED_USER_IDS_LEGACY,
    DATA_USER_BADGE_PROGRESS_ASSOCIATED_ACHIEVEMENT_LEGACY,
    DATA_USER_BADGE_PROGRESS_ASSOCIATED_CHALLENGE_LEGACY,
    DATA_USER_BADGE_PROGRESS_CHORES_COMPLETED_LEGACY,
    DATA_USER_BADGE_PROGRESS_DAYS_COMPLETED_LEGACY,
    DATA_USER_BADGE_PROGRESS_OCCASION_TYPE_LEGACY,
    DATA_USER_BADGE_PROGRESS_PENALTY_APPLIED_LEGACY,
    DATA_USER_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE_LEGACY,
    DATA_USER_BADGE_PROGRESS_TARGET_TYPE_LEGACY,
    DATA_USER_BADGE_PROGRESS_TRACKED_CHORES_LEGACY,
    DATA_USER_BADGE_PROGRESS_TYPE_LEGACY,
)
from custom_components.choreops.store import ChoreOpsStore

LEGACY_ASSIGNEES_BUCKET = "assignees"


@dataclass
class _DummyCoordinator:
    """Minimal coordinator stub for migration function tests."""

    _data: dict[str, Any]

    @property
    def assignees_data(self) -> dict[str, dict[str, Any]]:
        """Return assignment-capable users for pre-v50 approver migration helpers."""
        users_raw = self._data.get(const.DATA_USERS, {})
        if not isinstance(users_raw, dict):
            return {}
        return {
            user_id: user_data
            for user_id, user_data in users_raw.items()
            if isinstance(user_data, dict)
        }


async def test_schema45_migration_moves_assignees_to_users_and_sets_defaults() -> None:
    """Migrate legacy assignees bucket to users and stamp capability defaults."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            LEGACY_ASSIGNEES_BUCKET: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                    const.DATA_USER_HA_USER_ID: "ha-assignee-1",
                }
            },
            const.DATA_APPROVERS: {},
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert const.DATA_USERS in coordinator._data
    assert LEGACY_ASSIGNEES_BUCKET not in coordinator._data
    assert summary["users_migrated"] == 1
    assert summary["linked_approver_merges"] == 0
    assert summary["standalone_approver_creations"] == 0

    user_data = coordinator._data[const.DATA_USERS]["assignee-1"]
    assert user_data[const.DATA_USER_CAN_APPROVE] is False
    assert user_data[const.DATA_USER_CAN_MANAGE] is False
    assert user_data[const.DATA_USER_CAN_BE_ASSIGNED] is True
    assert user_data[const.DATA_USER_ENABLE_CHORE_WORKFLOW] is True
    assert user_data[const.DATA_USER_ENABLE_GAMIFICATION] is True
    assert user_data[const.DATA_USER_HA_USER_ID] == "ha-assignee-1"

    meta = coordinator._data[const.DATA_META]
    assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_CURRENT
    assert meta[const.DATA_META_SHARED_ADMIN_UI_CONTROL] == {}
    assert "schema45_user_contract_hook" in meta[const.DATA_META_MIGRATIONS_APPLIED]
    assert (
        const.MIGRATION_SCHEMA45_SHARED_ADMIN_UI_CONTROL
        in meta[const.DATA_META_MIGRATIONS_APPLIED]
    )
    assert summary["shared_admin_ui_control_backfilled"] == 1


async def test_schema45_migration_backfills_shared_admin_bucket_idempotently() -> None:
    """Schema45 backfills shared-admin UI control once and preserves existing data."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_CURRENT,
                const.DATA_META_MIGRATIONS_APPLIED: [
                    "schema45_user_contract_hook",
                ],
            },
            const.DATA_USERS: {
                "user-1": {
                    const.DATA_USER_NAME: "Alex",
                    const.DATA_USER_UI_PREFERENCES: {},
                }
            },
        }
    )

    first_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]
    coordinator._data[const.DATA_META][const.DATA_META_SHARED_ADMIN_UI_CONTROL] = {
        "admin": {"header_collapse": True}
    }

    second_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    meta = coordinator._data[const.DATA_META]
    assert meta[const.DATA_META_SHARED_ADMIN_UI_CONTROL] == {
        "admin": {"header_collapse": True}
    }
    assert (
        const.MIGRATION_SCHEMA45_SHARED_ADMIN_UI_CONTROL
        in meta[const.DATA_META_MIGRATIONS_APPLIED]
    )
    assert first_summary["shared_admin_ui_control_backfilled"] == 1
    assert second_summary["shared_admin_ui_control_backfilled"] == 0


async def test_schema45_migration_merges_linked_approver_into_existing_user() -> None:
    """Linked approver should enrich assignee-origin user capabilities."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                    const.DATA_USER_HA_USER_ID: "ha-assignee-1",
                }
            },
            const.DATA_APPROVERS: {
                "approver-1": {
                    const.DATA_USER_NAME: "Sam",
                    const.DATA_USER_HA_USER_ID: "ha-approver-1",
                    "linked_shadow_kid_id": "assignee-1",
                    "allow_chore_assignment": True,
                    const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                    const.DATA_USER_ENABLE_GAMIFICATION: False,
                    const.DATA_USER_ASSOCIATED_USER_IDS: ["assignee-2", "assignee-1"],
                }
            },
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert summary["linked_approver_merges"] == 1
    user_data = coordinator._data[const.DATA_USERS]["assignee-1"]
    assert user_data[const.DATA_USER_CAN_APPROVE] is True
    assert user_data[const.DATA_USER_CAN_MANAGE] is True
    assert user_data[const.DATA_USER_CAN_BE_ASSIGNED] is True
    assert user_data[const.DATA_USER_ENABLE_CHORE_WORKFLOW] is False
    assert user_data[const.DATA_USER_ENABLE_GAMIFICATION] is False
    assert user_data[const.DATA_USER_ASSOCIATED_USER_IDS] == [
        "assignee-2",
        "assignee-1",
    ]


async def test_schema45_migration_handles_collision_and_is_idempotent() -> None:
    """Standalone approver collision is remapped once and stable on rerun."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "shared-id": {
                    const.DATA_USER_NAME: "Assignee",
                    const.DATA_USER_HA_USER_ID: "ha-assignee",
                }
            },
            const.DATA_APPROVERS: {
                "shared-id": {
                    const.DATA_USER_NAME: "Approver",
                    const.DATA_USER_HA_USER_ID: "ha-approver",
                }
            },
        }
    )

    first_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]
    users_after_first = coordinator._data[const.DATA_USERS].copy()

    second_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert first_summary["approver_id_collisions"] == 1
    assert first_summary["standalone_approver_creations"] == 1
    assert second_summary["standalone_approver_creations"] == 0
    assert second_summary["approver_id_collisions"] == 0

    meta = coordinator._data[const.DATA_META]
    remap = meta["schema45_approver_id_remap"]
    assert remap["shared-id"].startswith("shared-id_approver_")

    assert coordinator._data[const.DATA_USERS] == users_after_first


async def test_schema45_migration_remaps_legacy_kid_keys() -> None:
    """Legacy kid-based keys are remapped to canonical assignee keys."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                }
            },
            const.DATA_APPROVERS: {
                "approver-1": {
                    const.CONF_ASSOCIATED_ASSIGNEES_LEGACY: ["assignee-1"],
                }
            },
            const.DATA_CHORES: {
                "chore-1": {
                    const.CONF_ASSIGNED_ASSIGNEES_LEGACY: ["assignee-1"],
                    "per_kid_due_dates": {"assignee-1": "2026-02-22T12:00:00+00:00"},
                    "per_kid_applicable_days": {"assignee-1": [0, 1]},
                    "per_kid_daily_multi_times": {"assignee-1": ["09:00"]},
                    "rotation_current_kid_id": "assignee-1",
                }
            },
            const.DATA_ACHIEVEMENTS: {
                "achievement-1": {
                    const.CONF_ACHIEVEMENT_ASSIGNED_ASSIGNEES_LEGACY: ["assignee-1"]
                }
            },
            const.DATA_CHALLENGES: {
                "challenge-1": {
                    const.CONF_CHALLENGE_ASSIGNED_ASSIGNEES_LEGACY: ["assignee-1"],
                    const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW,
                    const.DATA_CHALLENGE_TARGET_VALUE: 3,
                }
            },
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    chore = coordinator._data[const.DATA_CHORES]["chore-1"]
    assert chore[const.DATA_CHORE_ASSIGNED_USER_IDS] == ["assignee-1"]
    assert chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] == {
        "assignee-1": "2026-02-22T12:00:00+00:00"
    }
    assert chore[const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS] == {
        "assignee-1": [0, 1]
    }
    assert chore[const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES] == {
        "assignee-1": ["09:00"]
    }
    assert chore[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] == "assignee-1"

    assert const.CONF_ASSIGNED_ASSIGNEES_LEGACY not in chore
    assert "per_kid_due_dates" not in chore
    assert "per_kid_applicable_days" not in chore
    assert "per_kid_daily_multi_times" not in chore
    assert "rotation_current_kid_id" not in chore

    achievement = coordinator._data[const.DATA_ACHIEVEMENTS]["achievement-1"]
    badges = coordinator._data[const.DATA_BADGES]
    migrated_badge = badges["migrated_challenge_challenge-1"]
    assert achievement[const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS] == ["assignee-1"]
    assert migrated_badge[const.DATA_BADGE_ASSIGNED_USER_IDS] == ["assignee-1"]
    assert coordinator._data[const.DATA_CHALLENGES] == {}
    assert const.CONF_ACHIEVEMENT_ASSIGNED_ASSIGNEES_LEGACY not in achievement

    assert summary["kid_key_remaps"] >= 7


async def test_schema45_migration_merges_linked_parent_after_pre_v50_approver_stage() -> (
    None
):
    """Pre-v50 approver stage preserves legacy parent link/flags for schema45 merge."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "shadow-1": {
                    const.DATA_USER_NAME: "Alex",
                    const.DATA_USER_HA_USER_ID: "ha-alex",
                    const.DATA_USER_CAN_BE_ASSIGNED: True,
                    const.DATA_USER_ENABLE_CHORE_WORKFLOW: True,
                    const.DATA_USER_ENABLE_GAMIFICATION: True,
                },
                "kid-2": {
                    const.DATA_USER_NAME: "Taylor",
                    const.DATA_USER_HA_USER_ID: "ha-taylor",
                    const.DATA_USER_CAN_BE_ASSIGNED: True,
                },
            },
            const.DATA_APPROVERS: {},
        }
    )

    migrator = PreV50Migrator(coordinator)  # type: ignore[arg-type]
    migrator._create_approver(
        "parent-1",
        {
            const.DATA_USER_NAME: "Alex Parent",
            const.DATA_USER_HA_USER_ID: "ha-alex",
            const.DATA_USER_ASSOCIATED_USER_IDS: ["kid-2"],
            "linked_shadow_kid_id": "shadow-1",
            "allow_chore_assignment": True,
            const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
            const.DATA_USER_ENABLE_GAMIFICATION: False,
        },
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert summary["linked_approver_merges"] == 1
    assert summary["standalone_approver_creations"] == 0

    shadow_user = coordinator._data[const.DATA_USERS]["shadow-1"]
    assert shadow_user[const.DATA_USER_CAN_APPROVE] is True
    assert shadow_user[const.DATA_USER_CAN_MANAGE] is True
    assert shadow_user[const.DATA_USER_CAN_BE_ASSIGNED] is True
    assert shadow_user[const.DATA_USER_ENABLE_CHORE_WORKFLOW] is False
    assert shadow_user[const.DATA_USER_ENABLE_GAMIFICATION] is False
    assert shadow_user[const.DATA_USER_ASSOCIATED_USER_IDS] == ["kid-2"]

    assert "parent-1" not in coordinator._data[const.DATA_USERS]


async def test_schema45_converts_challenges_and_removes_challenge_linked_badges() -> (
    None
):
    """Schema45 converts supported challenges and removes challenge-linked badges."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                }
            },
            const.DATA_APPROVERS: {},
            const.DATA_BADGES: {
                "challenge-linked-1": {
                    const.DATA_BADGE_INTERNAL_ID: "challenge-linked-1",
                    const.DATA_BADGE_NAME: "Legacy Linked Badge",
                    const.DATA_BADGE_TYPE: const.BADGE_TYPE_CHALLENGE_LINKED,
                },
                "existing-name": {
                    const.DATA_BADGE_INTERNAL_ID: "existing-name",
                    const.DATA_BADGE_NAME: "Summer Sprint",
                    const.DATA_BADGE_TYPE: const.BADGE_TYPE_PERIODIC,
                },
            },
            const.DATA_CHALLENGES: {
                "challenge-total": {
                    const.DATA_CHALLENGE_NAME: "Summer Sprint",
                    const.DATA_CHALLENGE_DESCRIPTION: "Complete chores this month",
                    const.DATA_CHALLENGE_ICON: "mdi:run-fast",
                    const.DATA_CHALLENGE_LABELS: ["seasonal"],
                    const.DATA_CHALLENGE_ASSIGNED_USER_IDS: ["assignee-1"],
                    const.DATA_CHALLENGE_REWARD_POINTS: 50,
                    const.DATA_CHALLENGE_TARGET_VALUE: 20,
                    const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW,
                },
                "challenge-daily": {
                    const.DATA_CHALLENGE_NAME: "Weekend Warrior",
                    const.DATA_CHALLENGE_DESCRIPTION: "Do chores daily",
                    const.DATA_CHALLENGE_ICON: "mdi:calendar-star",
                    const.DATA_CHALLENGE_LABELS: ["daily"],
                    const.DATA_CHALLENGE_ASSIGNED_USER_IDS: ["assignee-1"],
                    const.DATA_CHALLENGE_REWARD_POINTS: 25,
                    const.DATA_CHALLENGE_TARGET_VALUE: 3,
                    const.DATA_CHALLENGE_SELECTED_CHORE_ID: "chore-1",
                    const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_DAILY_MIN,
                },
            },
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert summary["converted_challenges"] == 2
    assert summary["removed_challenge_linked_badges"] == 1
    assert summary["renamed_challenges_name_collision"] == 1
    assert summary["skipped_challenges_existing_badge"] == 0
    assert summary["skipped_challenges_invalid_type"] == 0

    assert coordinator._data[const.DATA_CHALLENGES] == {}
    badges = coordinator._data[const.DATA_BADGES]
    assert "challenge-linked-1" not in badges

    total_badge = badges["migrated_challenge_challenge-total"]
    assert total_badge[const.DATA_BADGE_NAME] == "Summer Sprint_2"
    assert total_badge[const.DATA_BADGE_TYPE] == const.BADGE_TYPE_PERIODIC
    assert total_badge[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE] == (
        const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT
    )
    assert (
        total_badge[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_THRESHOLD_VALUE]
        == 20.0
    )

    daily_badge = badges["migrated_challenge_challenge-daily"]
    assert daily_badge[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE] == (
        const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES
    )
    assert (
        daily_badge[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_THRESHOLD_VALUE]
        == 1.0
    )
    assert daily_badge[const.DATA_BADGE_TRACKED_CHORES][
        const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES
    ] == ["chore-1"]


async def test_schema45_kidschores_data_31_challenge_fixture_conversion() -> None:
    """Schema31-style challenge records convert and clear challenge container."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_LEGACY_BASELINE,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            LEGACY_ASSIGNEES_BUCKET: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                }
            },
            const.DATA_APPROVERS: {},
            const.DATA_BADGES: {},
            const.DATA_CHALLENGES: {
                "legacy-31": {
                    const.DATA_CHALLENGE_NAME: "Legacy 31 Challenge",
                    const.DATA_CHALLENGE_DESCRIPTION: "Legacy payload conversion",
                    const.DATA_CHALLENGE_ICON: "mdi:star",
                    const.CONF_CHALLENGE_ASSIGNED_ASSIGNEES_LEGACY: ["assignee-1"],
                    const.DATA_CHALLENGE_REWARD_POINTS: 15,
                    const.DATA_CHALLENGE_TARGET_VALUE: 5,
                    const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_DAILY_MIN,
                }
            },
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert summary["converted_challenges"] == 1
    assert coordinator._data[const.DATA_CHALLENGES] == {}
    migrated = coordinator._data[const.DATA_BADGES]["migrated_challenge_legacy-31"]
    assert migrated[const.DATA_BADGE_ASSIGNED_USER_IDS] == ["assignee-1"]
    assert migrated[const.DATA_BADGE_TARGET][const.DATA_BADGE_TARGET_TYPE] == (
        const.BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES
    )


async def test_schema45_challenge_conversion_idempotent_no_duplicate_badges() -> None:
    """Running schema45 hook twice does not duplicate migrated challenge badges."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                }
            },
            const.DATA_APPROVERS: {},
            const.DATA_BADGES: {},
            const.DATA_CHALLENGES: {
                "challenge-1": {
                    const.DATA_CHALLENGE_NAME: "Idempotent Challenge",
                    const.DATA_CHALLENGE_ASSIGNED_USER_IDS: ["assignee-1"],
                    const.DATA_CHALLENGE_REWARD_POINTS: 10,
                    const.DATA_CHALLENGE_TARGET_VALUE: 10,
                    const.DATA_CHALLENGE_TYPE: const.CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW,
                }
            },
        }
    )

    first_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]
    first_badges = coordinator._data[const.DATA_BADGES].copy()

    second_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert first_summary["converted_challenges"] == 1
    assert second_summary["converted_challenges"] == 0
    assert second_summary["skipped_challenges_existing_badge"] == 0
    assert coordinator._data[const.DATA_BADGES] == first_badges


async def test_schema45_migration_removes_legacy_penalty_applied_from_badge_progress() -> (
    None
):
    """Schema45 strips retired legacy fields from users.badge_progress entries."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_USERS: {
                "assignee-1": {
                    const.DATA_USER_NAME: "Alex",
                    const.DATA_USER_BADGE_PROGRESS: {
                        "badge-1": {
                            const.DATA_USER_BADGE_PROGRESS_NAME: "Legacy Badge",
                            DATA_USER_BADGE_PROGRESS_TYPE_LEGACY: const.BADGE_TYPE_PERIODIC,
                            DATA_USER_BADGE_PROGRESS_TARGET_TYPE_LEGACY: "points",
                            DATA_USER_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE_LEGACY: 10,
                            DATA_USER_BADGE_PROGRESS_CHORES_COMPLETED_LEGACY: {
                                "chore-1": True
                            },
                            DATA_USER_BADGE_PROGRESS_DAYS_COMPLETED_LEGACY: {
                                "2026-03-07": True
                            },
                            DATA_USER_BADGE_PROGRESS_ASSIGNED_USER_IDS_LEGACY: [
                                "assignee-1"
                            ],
                            DATA_USER_BADGE_PROGRESS_TRACKED_CHORES_LEGACY: ["chore-1"],
                            DATA_USER_BADGE_PROGRESS_OCCASION_TYPE_LEGACY: "birthday",
                            DATA_USER_BADGE_PROGRESS_ASSOCIATED_ACHIEVEMENT_LEGACY: "achievement-1",
                            DATA_USER_BADGE_PROGRESS_ASSOCIATED_CHALLENGE_LEGACY: "challenge-1",
                            DATA_USER_BADGE_PROGRESS_PENALTY_APPLIED_LEGACY: False,
                        }
                    },
                }
            },
            const.DATA_APPROVERS: {},
            const.DATA_BADGES: {},
            const.DATA_CHALLENGES: {},
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    progress = coordinator._data[const.DATA_USERS]["assignee-1"][
        const.DATA_USER_BADGE_PROGRESS
    ]["badge-1"]
    assert DATA_USER_BADGE_PROGRESS_TYPE_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_TARGET_TYPE_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_CHORES_COMPLETED_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_DAYS_COMPLETED_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_ASSIGNED_USER_IDS_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_TRACKED_CHORES_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_OCCASION_TYPE_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_ASSOCIATED_ACHIEVEMENT_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_ASSOCIATED_CHALLENGE_LEGACY not in progress
    assert DATA_USER_BADGE_PROGRESS_PENALTY_APPLIED_LEGACY not in progress
    assert summary["removed_penalty_applied_fields"] == 1
    assert summary["removed_retired_badge_progress_fields"] == 10


def test_store_default_structure_uses_users_bucket() -> None:
    """Fresh store default structure should initialize canonical users model."""
    default_structure = ChoreOpsStore.get_default_structure()

    assert const.DATA_USERS in default_structure
    assert LEGACY_ASSIGNEES_BUCKET not in default_structure
    assert const.DATA_APPROVERS not in default_structure
    assert (
        default_structure[const.DATA_META][const.DATA_META_SCHEMA_VERSION]
        == const.SCHEMA_VERSION_CURRENT
    )
