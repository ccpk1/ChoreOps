"""Tests for conditional entity cleanup in SystemManager."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from custom_components.choreops import const
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
                const.DATA_APPROVER_ALLOW_CHORE_ASSIGNMENT: True,
                const.DATA_APPROVER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_APPROVER_ENABLE_GAMIFICATION: False,
            }
        },
        approvers_data={
            assignee_id: {
                const.DATA_APPROVER_ALLOW_CHORE_ASSIGNMENT: True,
                const.DATA_APPROVER_ENABLE_CHORE_WORKFLOW: False,
                const.DATA_APPROVER_ENABLE_GAMIFICATION: False,
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
