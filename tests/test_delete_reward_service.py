"""Tests for delete_reward service.

Tests the assigneeschores.delete_reward service which allows programmatic deletion
of rewards using either reward ID or reward name as identifier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from homeassistant.exceptions import HomeAssistantError
import pytest

from tests.helpers import (
    DOMAIN,
    SERVICE_CREATE_REWARD,
    SERVICE_DELETE_REWARD,
    SERVICE_UPDATE_REWARD,
    SetupResult,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


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


# ============================================================================
# TESTS
# ============================================================================


class TestDeleteRewardByID:
    """Test delete_reward service using reward ID."""

    @pytest.mark.asyncio
    async def test_delete_by_id_success(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test deleting a reward by ID."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        # Verify reward exists before deletion
        assert reward_id in coordinator.rewards_data

        # Mock _persist to avoid file operations
        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Delete the reward
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"id": reward_id},
                blocking=True,
                return_response=True,
            )

        # Verify service response
        assert response is not None
        assert response["id"] == reward_id

        # Verify reward was deleted from coordinator
        assert reward_id not in coordinator.rewards_data

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test deleting a non-existent reward by ID raises error."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"id": "nonexistent-id"},
                blocking=True,
                return_response=True,
            )

    @pytest.mark.asyncio
    async def test_delete_by_id_removes_from_assignee_reward_data(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test deleting a reward cleans up assignee reward_data references."""
        from custom_components.choreops import const

        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        assignee_id = scenario_full.assignee_ids["Zoë"]

        # Ensure assignee has data for this reward
        if reward_id not in coordinator.assignees_data[assignee_id].get(
            const.DATA_USER_REWARD_DATA, {}
        ):
            coordinator.assignees_data[assignee_id].setdefault(
                const.DATA_USER_REWARD_DATA, {}
            )[reward_id] = {
                const.DATA_USER_REWARD_DATA_NAME: "Extra Screen Time",
                const.DATA_USER_REWARD_DATA_PENDING_COUNT: 1,
            }

        # Mock _persist to avoid file operations
        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Delete the reward
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"id": reward_id},
                blocking=True,
                return_response=True,
            )

        # Verify cleanup: reward removed from assignee's reward_data
        assert reward_id not in coordinator.assignees_data[assignee_id].get(
            const.DATA_USER_REWARD_DATA, {}
        )


class TestDeleteRewardByName:
    """Test delete_reward service using reward name."""

    @pytest.mark.asyncio
    async def test_delete_by_name_success(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test deleting a reward by name."""
        coordinator = scenario_full.coordinator
        reward_name = "Extra Screen Time"
        reward_id = scenario_full.reward_ids[reward_name]

        # Verify reward exists before deletion
        assert reward_id in coordinator.rewards_data

        # Mock _persist to avoid file operations
        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Delete the reward using name
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"name": reward_name},
                blocking=True,
                return_response=True,
            )

        # Verify service response returns the ID that was deleted
        assert response is not None
        assert response["id"] == reward_id

        # Verify reward was deleted from coordinator
        assert reward_id not in coordinator.rewards_data

    @pytest.mark.asyncio
    async def test_delete_by_name_not_found(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test deleting a non-existent reward by name raises error."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"name": "Nonexistent Reward"},
                blocking=True,
                return_response=True,
            )


class TestDeleteRewardValidation:
    """Test delete_reward service validation."""

    @pytest.mark.asyncio
    async def test_requires_either_id_or_name(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test that delete_reward requires either id or name."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {},  # Neither id nor name provided
                blocking=True,
                return_response=True,
            )


class TestDeleteRewardIntegration:
    """Test delete_reward integration with create/update services."""

    @pytest.mark.asyncio
    async def test_create_then_delete_by_name(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test creating then deleting a reward by name."""
        coordinator = scenario_full.coordinator

        # Mock _persist to avoid file operations
        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Create a new reward
            create_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Temporary Reward",
                    "cost": 25.0,
                    "description": "Test reward for deletion",
                },
                blocking=True,
                return_response=True,
            )

            reward_id = create_response["id"]

            # Verify reward was created
            assert reward_id in coordinator.rewards_data
            assert coordinator.rewards_data[reward_id]["name"] == "Temporary Reward"

            # Delete the reward by name
            delete_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"name": "Temporary Reward"},
                blocking=True,
                return_response=True,
            )

            assert delete_response["id"] == reward_id
            assert reward_id not in coordinator.rewards_data

    @pytest.mark.asyncio
    async def test_update_then_delete(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updating a reward then deleting it."""
        coordinator = scenario_full.coordinator
        reward_name = "Extra Screen Time"
        reward_id = scenario_full.reward_ids[reward_name]

        # Mock _persist to avoid file operations
        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Update the reward
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "name": reward_name,
                    "cost": 99.0,
                },
                blocking=True,
                return_response=True,
            )

            # Verify update
            assert coordinator.rewards_data[reward_id]["cost"] == 99.0

            # Delete the updated reward
            delete_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_REWARD,
                {"id": reward_id},
                blocking=True,
                return_response=True,
            )

            assert delete_response["id"] == reward_id
            assert reward_id not in coordinator.rewards_data
