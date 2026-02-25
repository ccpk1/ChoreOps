"""Tests for conditional entity cleanup in SystemManager."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers.device_helpers import (
    get_assignee_device_identifier,
)
from custom_components.choreops.managers.system_manager import SystemManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_remove_conditional_entities_respects_user_feature_flags(
    hass: HomeAssistant,
) -> None:
    """Cleanup removes workflow/gamification entities when user flags are disabled."""
    assignee_id = "user-1"
    entry_id = "entry-1"

    coordinator = SimpleNamespace(
        config_entry=SimpleNamespace(
            entry_id=entry_id,
            options={const.CONF_SHOW_LEGACY_ENTITIES: False},
        ),
        users_data={
            assignee_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: True,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
        approvers_data={
            assignee_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: True,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
    )

    manager = SystemManager(hass, coordinator)

    claim_entry = SimpleNamespace(
        unique_id=f"{entry_id}_{assignee_id}{const.BUTTON_KC_UID_SUFFIX_CLAIM}",
        entity_id="button.claim",
    )
    points_entry = SimpleNamespace(
        unique_id=f"{entry_id}_{assignee_id}{const.SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR}",
        entity_id="sensor.points",
    )
    approve_entry = SimpleNamespace(
        unique_id=f"{entry_id}_{assignee_id}{const.BUTTON_KC_UID_SUFFIX_APPROVE}",
        entity_id="button.approve",
    )

    fake_registry = MagicMock()

    with (
        patch(
            "custom_components.choreops.managers.system_manager.er.async_get",
            return_value=fake_registry,
        ),
        patch(
            "custom_components.choreops.managers.system_manager.er.async_entries_for_config_entry",
            return_value=[claim_entry, points_entry, approve_entry],
        ),
    ):
        removed = await manager.remove_conditional_entities()

    assert removed == 2
    fake_registry.async_remove.assert_any_call("button.claim")
    fake_registry.async_remove.assert_any_call("sensor.points")
    assert fake_registry.async_remove.call_count == 2


@pytest.mark.asyncio
async def test_remove_conditional_entities_removes_empty_non_assignment_device(
    hass: HomeAssistant,
) -> None:
    """Cleanup removes empty user device when user is no longer assignment participant."""
    user_id = "user-1"
    entry_id = "entry-1"

    coordinator = SimpleNamespace(
        config_entry=SimpleNamespace(
            entry_id=entry_id,
            options={const.CONF_SHOW_LEGACY_ENTITIES: False},
        ),
        users_data={
            user_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: False,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
        approvers_data={},
    )

    manager = SystemManager(hass, coordinator)

    fake_entity_registry = MagicMock()
    fake_device_registry = MagicMock()
    fake_device_registry.async_get_device.return_value = SimpleNamespace(id="device-1")

    with (
        patch(
            "custom_components.choreops.managers.system_manager.er.async_get",
            return_value=fake_entity_registry,
        ),
        patch(
            "custom_components.choreops.managers.system_manager.er.async_entries_for_config_entry",
            return_value=[],
        ),
        patch(
            "custom_components.choreops.managers.system_manager.dr.async_get",
            return_value=fake_device_registry,
        ),
    ):
        await manager.remove_conditional_entities(user_ids=[user_id])

    fake_device_registry.async_get_device.assert_called_once_with(
        identifiers={
            (
                const.DOMAIN,
                get_assignee_device_identifier(coordinator.config_entry, user_id),
            )
        }
    )
    fake_device_registry.async_remove_device.assert_called_once_with("device-1")


@pytest.mark.asyncio
async def test_remove_conditional_entities_keeps_device_with_remaining_entities(
    hass: HomeAssistant,
) -> None:
    """Cleanup keeps device when at least one config-entry entity is still attached."""
    user_id = "user-1"
    entry_id = "entry-1"

    coordinator = SimpleNamespace(
        config_entry=SimpleNamespace(
            entry_id=entry_id,
            options={const.CONF_SHOW_LEGACY_ENTITIES: False},
        ),
        users_data={
            user_id: {
                const.DATA_USER_CAN_BE_ASSIGNED: False,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_USER_ENABLE_GAMIFICATION: False,
            }
        },
        approvers_data={},
    )

    manager = SystemManager(hass, coordinator)

    fake_entity_registry = MagicMock()
    fake_device_registry = MagicMock()
    fake_device_registry.async_get_device.return_value = SimpleNamespace(id="device-1")
    attached_entity = SimpleNamespace(
        unique_id=f"{entry_id}_{user_id}_helper",
        entity_id="sensor.user_helper",
        device_id="device-1",
    )

    with (
        patch(
            "custom_components.choreops.managers.system_manager.er.async_get",
            return_value=fake_entity_registry,
        ),
        patch(
            "custom_components.choreops.managers.system_manager.er.async_entries_for_config_entry",
            return_value=[attached_entity],
        ),
        patch(
            "custom_components.choreops.managers.system_manager.dr.async_get",
            return_value=fake_device_registry,
        ),
    ):
        await manager.remove_conditional_entities(user_ids=[user_id])

    fake_device_registry.async_remove_device.assert_not_called()
