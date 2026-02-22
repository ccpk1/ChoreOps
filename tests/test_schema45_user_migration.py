"""Tests for schema45 user-unification migration contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.migration_pre_v50 import (
    async_apply_schema45_user_contract,
)
from custom_components.choreops.store import ChoreOpsStore


@dataclass
class _DummyCoordinator:
    """Minimal coordinator stub for migration function tests."""

    _data: dict[str, Any]


async def test_schema45_migration_moves_assignees_to_users_and_sets_defaults() -> None:
    """Migrate legacy assignees bucket to users and stamp capability defaults."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_ASSIGNEES: {
                "assignee-1": {
                    const.DATA_ASSIGNEE_NAME: "Alex",
                    const.DATA_ASSIGNEE_HA_USER_ID: "ha-assignee-1",
                }
            },
            const.DATA_APPROVERS: {},
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert const.DATA_USERS in coordinator._data
    assert const.DATA_ASSIGNEES not in coordinator._data
    assert summary["users_migrated"] == 1
    assert summary["linked_approver_merges"] == 0
    assert summary["standalone_approver_creations"] == 0

    user_data = coordinator._data[const.DATA_USERS]["assignee-1"]
    assert user_data[const.DATA_USER_CAN_APPROVE] is False
    assert user_data[const.DATA_USER_CAN_MANAGE] is False
    assert user_data[const.DATA_USER_CAN_BE_ASSIGNED] is True
    assert user_data[const.DATA_APPROVER_ENABLE_CHORE_WORKFLOW] is True
    assert user_data[const.DATA_APPROVER_ENABLE_GAMIFICATION] is True
    assert user_data[const.DATA_USER_HA_USER_ID] == "ha-assignee-1"

    meta = coordinator._data[const.DATA_META]
    assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_BETA5
    assert "schema45_user_contract_hook" in meta[const.DATA_META_MIGRATIONS_APPLIED]


async def test_schema45_migration_merges_linked_approver_into_existing_user() -> None:
    """Linked approver should enrich assignee-origin user capabilities."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_ASSIGNEES: {
                "assignee-1": {
                    const.DATA_ASSIGNEE_NAME: "Alex",
                    const.DATA_ASSIGNEE_HA_USER_ID: "ha-assignee-1",
                }
            },
            const.DATA_APPROVERS: {
                "approver-1": {
                    const.DATA_APPROVER_NAME: "Sam",
                    const.DATA_APPROVER_HA_USER_ID: "ha-approver-1",
                    const.DATA_APPROVER_LINKED_PROFILE_ID: "assignee-1",
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
    assert user_data[const.DATA_APPROVER_ENABLE_CHORE_WORKFLOW] is True
    assert user_data[const.DATA_APPROVER_ENABLE_GAMIFICATION] is True


async def test_schema45_migration_handles_collision_and_is_idempotent() -> None:
    """Standalone approver collision is remapped once and stable on rerun."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_ASSIGNEES: {
                "shared-id": {
                    const.DATA_ASSIGNEE_NAME: "Assignee",
                    const.DATA_ASSIGNEE_HA_USER_ID: "ha-assignee",
                }
            },
            const.DATA_APPROVERS: {
                "shared-id": {
                    const.DATA_APPROVER_NAME: "Approver",
                    const.DATA_APPROVER_HA_USER_ID: "ha-approver",
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


def test_store_default_structure_uses_users_bucket() -> None:
    """Fresh store default structure should initialize canonical users model."""
    default_structure = ChoreOpsStore.get_default_structure()

    assert const.DATA_USERS in default_structure
    assert const.DATA_ASSIGNEES not in default_structure
    assert const.DATA_APPROVERS not in default_structure
    assert (
        default_structure[const.DATA_META][const.DATA_META_SCHEMA_VERSION]
        == const.SCHEMA_VERSION_BETA5
    )
