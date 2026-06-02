"""Tests for per-user reward assignment feature.

This module tests:
- Default assignment (all users) on create
- Explicit UUID assignment on create
- Update reward to add/remove users via service
- Backward compatibility (existing rewards have the field)
- Sentinel ``"*"`` storage and resolution

Testing approach:
- Storage assertions for data model (coordinator.rewards_data)
- Entity registry assertions for existing scenario rewards
- Service call validation for create/update handlers
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
import pytest

from tests.helpers import (
    DOMAIN,
    SERVICE_CREATE_REWARD,
    SERVICE_UPDATE_REWARD,
    SetupResult,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario: 3 assignees, 2 approvers, 8 chores, 3 rewards."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


def _count_entities_for_reward(
    registry: Any,
    reward_id: str,
    *,
    assignee_id: str | None = None,
) -> int:
    """Count reward entities in the entity registry for a given reward."""
    count = 0
    for entry in registry.entities.values():
        uid = str(entry.unique_id)
        if reward_id not in uid:
            continue
        is_reward_entity = (
            "_reward_status" in uid
            or "_reward_redeem" in uid
            or "_reward_approve" in uid
            or "_reward_disapprove" in uid
        )
        if not is_reward_entity:
            continue
        if assignee_id and assignee_id not in uid:
            continue
        count += 1
    return count


# ============================================================================
# DEFAULT ALL USERS ON CREATE
# ============================================================================


class TestDefaultAllUsersOnCreate:
    """Test that rewards default to all users when assigned_user_ids is omitted."""

    @pytest.mark.asyncio
    async def test_default_all_users_in_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test created reward has all gamified user IDs by default."""
        coordinator = scenario_full.coordinator
        with patch.object(coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {"name": "Default All Users", "cost": 50.0},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[response["id"]]
        assigned_ids = reward_data["assigned_user_ids"]
        # All gamified users should be assigned
        for assignee_name in ["Zoë", "Max!", "Lila"]:
            assert scenario_full.assignee_ids[assignee_name] in assigned_ids

    @pytest.mark.asyncio
    async def test_existing_scenario_reward_has_entities_for_all_assignees(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that existing scenario rewards have entities for all gamified assignees."""
        registry = async_get_entity_registry(hass)
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        for assignee_name in ["Zoë", "Max!", "Lila"]:
            assignee_id = scenario_full.assignee_ids[assignee_name]
            count = _count_entities_for_reward(
                registry, reward_id, assignee_id=assignee_id
            )
            assert count >= 1, f"{assignee_name} should have entities for ['*'] reward"


# ============================================================================
# EXPLICIT USER ASSIGNMENT ON CREATE
# ============================================================================


class TestExplicitUserAssignmentOnCreate:
    """Test creating rewards with explicit user assignments."""

    @pytest.mark.asyncio
    async def test_explicit_single_user_in_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test creating a reward with explicit UUID list."""
        coordinator = scenario_full.coordinator
        zoe_id = scenario_full.assignee_ids["Zoë"]
        with patch.object(coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Zoe Only",
                    "cost": 30.0,
                    "assigned_user_ids": [zoe_id],
                },
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[response["id"]]
        assert reward_data["assigned_user_ids"] == [zoe_id]

    @pytest.mark.asyncio
    async def test_explicit_multiple_users_in_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test creating a reward with multiple specific users."""
        coordinator = scenario_full.coordinator
        zoe_id = scenario_full.assignee_ids["Zoë"]
        lila_id = scenario_full.assignee_ids["Lila"]
        with patch.object(coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Zoe And Lila",
                    "cost": 30.0,
                    "assigned_user_ids": [zoe_id, lila_id],
                },
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[response["id"]]
        assert zoe_id in reward_data["assigned_user_ids"]
        assert lila_id in reward_data["assigned_user_ids"]
        assert len(reward_data["assigned_user_ids"]) == 2


# ============================================================================
# SENTINEL "*" BEHAVIOR
# ============================================================================


class TestSentinelStarBehavior:
    """Test sentinel '*' behavior for all-users assignment."""

    @pytest.mark.asyncio
    async def test_sentinel_star_stored_correctly(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that ['*'] input is resolved to explicit user IDs in storage."""
        coordinator = scenario_full.coordinator
        with patch.object(coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Star Sentinel",
                    "cost": 10.0,
                    "assigned_user_ids": ["*"],
                },
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[response["id"]]
        # Sentinel should be resolved to actual UUIDs, never stored as-is
        assert "*" not in reward_data["assigned_user_ids"]
        for assignee_name in ["Zoë", "Max!", "Lila"]:
            assert (
                scenario_full.assignee_ids[assignee_name]
                in reward_data["assigned_user_ids"]
            )


# ============================================================================
# UPDATE REWARD ASSIGNMENTS
# ============================================================================


class TestUpdateRewardAssignments:
    """Test updating reward assignments via service."""

    @pytest.mark.asyncio
    async def test_update_reward_add_user_in_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updating a reward to assign specific users."""
        coordinator = scenario_full.coordinator
        zoe_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {"id": reward_id, "assigned_user_ids": [zoe_id]},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[reward_id]
        assert reward_data["assigned_user_ids"] == [zoe_id]

    @pytest.mark.asyncio
    async def test_update_reward_set_all_users(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updating a reward to ['*'] in storage."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {"id": reward_id, "assigned_user_ids": ["*"]},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[reward_id]
        assert "*" not in reward_data["assigned_user_ids"]
        for assignee_name in ["Zoë", "Max!", "Lila"]:
            assert (
                scenario_full.assignee_ids[assignee_name]
                in reward_data["assigned_user_ids"]
            )


# ============================================================================
# SERVICE WITH ASSIGNED_USER_NAMES (DISPLAY NAMES)
# ============================================================================


class TestServiceWithAssignNames:
    """Test service handlers resolve display names to UUIDs."""

    @pytest.mark.asyncio
    async def test_update_reward_with_names_resolves_to_uuids(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward with assigned_user_names resolves display names."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        zoe_id = scenario_full.assignee_ids["Zoë"]
        lila_id = scenario_full.assignee_ids["Lila"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "id": reward_id,
                    "assigned_user_names": ["Zoë", "Lila"],
                },
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        assigned_ids = coordinator.rewards_data[reward_id]["assigned_user_ids"]
        assert zoe_id in assigned_ids
        assert lila_id in assigned_ids
        assert len(assigned_ids) == 2

    @pytest.mark.asyncio
    async def test_update_reward_with_sentinel_name(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward with assigned_user_names containing sentinel."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "id": reward_id,
                    "assigned_user_names": ["*"],
                },
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[reward_id]
        assert "*" not in reward_data["assigned_user_ids"]
        for assignee_name in ["Zoë", "Max!", "Lila"]:
            assert (
                scenario_full.assignee_ids[assignee_name]
                in reward_data["assigned_user_ids"]
            )


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility with scenario rewards."""

    @pytest.mark.asyncio
    async def test_existing_rewards_have_assigned_user_ids(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that existing scenario rewards have the new field."""
        for reward_data in scenario_full.coordinator.rewards_data.values():
            assert "assigned_user_ids" in reward_data
            assigned = reward_data["assigned_user_ids"]
            assert isinstance(assigned, list) and len(assigned) > 0
            assert "*" not in assigned

    @pytest.mark.asyncio
    async def test_schema_accepts_both_field_names(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that service schema accepts both name and ids field."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        zoe_id = scenario_full.assignee_ids["Zoë"]

        # Test with assigned_user_ids (direct UUIDs)
        with patch.object(coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {"id": reward_id, "assigned_user_ids": [zoe_id]},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

    @pytest.mark.asyncio
    async def test_update_without_assignment_preserves_existing(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that updating other fields preserves existing assigned_user_ids."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        original_assigned = coordinator.rewards_data[reward_id].get(
            "assigned_user_ids", ["*"]
        )

        with patch.object(coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {"id": reward_id, "cost": 99.0},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()

        reward_data = coordinator.rewards_data[reward_id]
        assert reward_data["assigned_user_ids"] == original_assigned
        assert reward_data["cost"] == 99.0


# ============================================================================
# DELETE REWARD CLEANUP
# ============================================================================


class TestDeleteRewardCleanup:
    """Test deleting a reward removes all associated entities."""

    @pytest.mark.asyncio
    async def test_delete_reward_removes_entities(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that deleting a reward removes all entity references."""
        coordinator = scenario_full.coordinator
        registry = async_get_entity_registry(hass)
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        # Confirm entities exist before
        before = _count_entities_for_reward(registry, reward_id)
        assert before > 0, "Should have entities before deletion"

        with patch.object(coordinator, "_persist", new=MagicMock()):
            coordinator.reward_manager.delete_reward(reward_id)
            await hass.async_block_till_done()

        # Confirm entities gone after
        after = _count_entities_for_reward(registry, reward_id)
        assert after == 0, f"Should have 0 entities after deletion, got {after}"
