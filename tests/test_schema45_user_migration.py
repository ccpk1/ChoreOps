"""Tests for schema45 user-unification migration contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.migration_pre_v50 import (
    async_apply_schema45_user_contract,
)
from custom_components.choreops.store import KidsChoresStore


@dataclass
class _DummyCoordinator:
    """Minimal coordinator stub for migration function tests."""

    _data: dict[str, Any]


async def test_schema45_migration_moves_kids_to_users_and_sets_defaults() -> None:
    """Migrate legacy kids bucket to users and stamp capability defaults."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_KIDS: {
                "kid-1": {
                    const.DATA_KID_NAME: "Alex",
                    const.DATA_KID_HA_USER_ID: "ha-kid-1",
                }
            },
            const.DATA_PARENTS: {},
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert const.DATA_USERS in coordinator._data
    assert const.DATA_KIDS not in coordinator._data
    assert summary["users_migrated"] == 1
    assert summary["linked_parent_merges"] == 0
    assert summary["standalone_parent_creations"] == 0

    user_data = coordinator._data[const.DATA_USERS]["kid-1"]
    assert user_data[const.DATA_USER_CAN_APPROVE] is False
    assert user_data[const.DATA_USER_CAN_MANAGE] is False
    assert user_data[const.DATA_USER_CAN_BE_ASSIGNED] is True
    assert user_data[const.DATA_USER_HA_USER_ID] == "ha-kid-1"

    meta = coordinator._data[const.DATA_META]
    assert meta[const.DATA_META_SCHEMA_VERSION] == const.SCHEMA_VERSION_BETA5
    assert "schema45_user_contract_hook" in meta[const.DATA_META_MIGRATIONS_APPLIED]


async def test_schema45_migration_merges_linked_parent_into_existing_user() -> None:
    """Linked parent should enrich kid-origin user capabilities."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_KIDS: {
                "kid-1": {
                    const.DATA_KID_NAME: "Alex",
                    const.DATA_KID_HA_USER_ID: "ha-kid-1",
                }
            },
            const.DATA_PARENTS: {
                "parent-1": {
                    const.DATA_PARENT_NAME: "Sam",
                    const.DATA_PARENT_HA_USER_ID: "ha-parent-1",
                    const.DATA_PARENT_LINKED_SHADOW_KID_ID: "kid-1",
                }
            },
        }
    )

    summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert summary["linked_parent_merges"] == 1
    user_data = coordinator._data[const.DATA_USERS]["kid-1"]
    assert user_data[const.DATA_USER_CAN_APPROVE] is True
    assert user_data[const.DATA_USER_CAN_MANAGE] is True
    assert user_data[const.DATA_USER_CAN_BE_ASSIGNED] is True


async def test_schema45_migration_handles_collision_and_is_idempotent() -> None:
    """Standalone parent collision is remapped once and stable on rerun."""
    coordinator = _DummyCoordinator(
        _data={
            const.DATA_META: {
                const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_BETA4,
                const.DATA_META_MIGRATIONS_APPLIED: [],
            },
            const.DATA_KIDS: {
                "shared-id": {
                    const.DATA_KID_NAME: "Kid",
                    const.DATA_KID_HA_USER_ID: "ha-kid",
                }
            },
            const.DATA_PARENTS: {
                "shared-id": {
                    const.DATA_PARENT_NAME: "Parent",
                    const.DATA_PARENT_HA_USER_ID: "ha-parent",
                }
            },
        }
    )

    first_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]
    users_after_first = coordinator._data[const.DATA_USERS].copy()

    second_summary = await async_apply_schema45_user_contract(coordinator)  # type: ignore[arg-type]

    assert first_summary["parent_id_collisions"] == 1
    assert first_summary["standalone_parent_creations"] == 1
    assert second_summary["standalone_parent_creations"] == 0
    assert second_summary["parent_id_collisions"] == 0

    meta = coordinator._data[const.DATA_META]
    remap = meta["schema45_parent_id_remap"]
    assert remap["shared-id"].startswith("shared-id_parent_")

    assert coordinator._data[const.DATA_USERS] == users_after_first


def test_store_default_structure_uses_users_bucket() -> None:
    """Fresh store default structure should initialize canonical users model."""
    default_structure = KidsChoresStore.get_default_structure()

    assert const.DATA_USERS in default_structure
    assert const.DATA_KIDS not in default_structure
    assert const.DATA_PARENTS not in default_structure
    assert (
        default_structure[const.DATA_META][const.DATA_META_SCHEMA_VERSION]
        == const.SCHEMA_VERSION_BETA5
    )
