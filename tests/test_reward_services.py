"""Test reward-related services.

This module tests the following services:
- approve_reward (with cost_override parameter)

Focus on approve_reward cost_override feature:
- Approve reward at lesser cost than default
- Approve reward at zero cost (free grant)

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from custom_components.choreops.const import (
    DATA_ASSIGNEE_POINTS,
    DATA_ASSIGNEE_REWARD_DATA,
    DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT,
    DATA_REWARD_COST,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

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
# HELPER FUNCTIONS
# ============================================================================


def get_assignee_points(coordinator: Any, assignee_id: str) -> float:
    """Get current points for a assignee."""
    assignee_info = coordinator.assignees_data.get(assignee_id, {})
    return assignee_info.get(DATA_ASSIGNEE_POINTS, 0.0)


def get_pending_reward_count(coordinator: Any, assignee_id: str, reward_id: str) -> int:
    """Get pending claim count for a assignee's reward."""
    assignee_info = coordinator.assignees_data.get(assignee_id, {})
    reward_data = assignee_info.get(DATA_ASSIGNEE_REWARD_DATA, {})
    reward_entry = reward_data.get(reward_id, {})
    return reward_entry.get(DATA_ASSIGNEE_REWARD_DATA_PENDING_COUNT, 0)


def set_ha_user_capabilities(
    coordinator: Any,
    ha_user_id: str,
    *,
    can_approve: bool,
    can_manage: bool,
) -> None:
    """Set capability flags for a user record linked to a Home Assistant user ID."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for user_data_raw in users.values():
        if not isinstance(user_data_raw, dict):
            continue
        if user_data_raw.get(const.DATA_USER_HA_USER_ID) == ha_user_id:
            user_data_raw[const.DATA_USER_CAN_APPROVE] = can_approve
            user_data_raw[const.DATA_USER_CAN_MANAGE] = can_manage
            return

    raise AssertionError(f"No user record found for HA user ID: {ha_user_id}")


def get_non_target_linked_user_id(coordinator: Any, target_user_id: str) -> str:
    """Return a linked Home Assistant user ID for a user other than target."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for internal_id, user_data_raw in users.items():
        if internal_id == target_user_id or not isinstance(user_data_raw, dict):
            continue
        ha_user_id = user_data_raw.get(const.DATA_USER_HA_USER_ID)
        if isinstance(ha_user_id, str) and ha_user_id:
            return ha_user_id

    raise AssertionError("No non-target linked user record found")


def get_non_target_user_id(coordinator: Any, target_user_id: str) -> str:
    """Return a user internal_id other than target."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for internal_id, user_data_raw in users.items():
        if internal_id == target_user_id or not isinstance(user_data_raw, dict):
            continue
        return internal_id

    raise AssertionError("No non-target user record found")


# ============================================================================
# COST OVERRIDE TESTS
# ============================================================================


class TestApproveRewardCostOverride:
    """Tests for approve_reward with cost_override parameter."""

    @pytest.mark.asyncio
    async def test_approve_reward_lesser_cost_deducts_override_amount(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Approve reward at lesser cost deducts only the override amount.

        When a approver approves a reward with cost_override < reward's stored cost,
        the assignee should have only the override amount deducted from their points.

        Use case: "Weekend special" - assignee earns reward at discounted price.
        """
        coordinator = scenario_full.coordinator

        # Get test entities
        assignee_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        # Verify reward's stored cost (should be 50 per scenario_full.yaml)
        reward_info = coordinator.rewards_data.get(reward_id, {})
        stored_cost = reward_info.get(DATA_REWARD_COST, 0)
        assert stored_cost == 50, f"Expected reward cost 50, got {stored_cost}"

        # Give assignee enough points to afford the reward
        starting_points = 100.0
        coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_POINTS] = starting_points

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            with patch.object(
                coordinator.notification_manager,
                "notify_approvers_translated",
                new=AsyncMock(),
            ):
                # Assignee claims the reward (redeem is the claim method)
                await coordinator.reward_manager.redeem(
                    approver_name="Môm Astrid Stârblüm",
                    assignee_id=assignee_id,
                    reward_id=reward_id,
                )

                # Verify reward is pending approval
                pending_count = get_pending_reward_count(
                    coordinator, assignee_id, reward_id
                )
                assert pending_count == 1, "Reward should be pending after claim"

                # Approver approves with lesser cost (20 instead of 50)
                lesser_cost = 20.0
                await coordinator.reward_manager.approve(
                    approver_name="Môm Astrid Stârblüm",
                    assignee_id=assignee_id,
                    reward_id=reward_id,
                    cost_override=lesser_cost,
                )

        # Verify: Only the override amount was deducted
        final_points = get_assignee_points(coordinator, assignee_id)
        expected_points = starting_points - lesser_cost  # 100 - 20 = 80

        assert final_points == expected_points, (
            f"Expected {expected_points} points after lesser cost override, "
            f"got {final_points}. Should deduct {lesser_cost}, not {stored_cost}."
        )

        # Verify: Pending count is cleared
        pending_after = get_pending_reward_count(coordinator, assignee_id, reward_id)
        assert pending_after == 0, "Pending count should be 0 after approval"


class TestAuthorizationAcceptance:
    """Test approval capability vs management capability boundaries."""

    @pytest.mark.asyncio
    async def test_assignee_only_can_redeem_reward_but_cannot_manage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Assignee-only user can redeem own reward but cannot perform management action."""
        coordinator = scenario_full.coordinator
        assignee_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_POINTS] = 100.0

        actor_user = await hass.auth.async_create_user(
            "Reward Matrix Actor",
            group_ids=["system-users"],
        )
        actor_user_id = actor_user.id
        coordinator.assignees_data[assignee_id][const.DATA_USER_HA_USER_ID] = (
            actor_user_id
        )

        actor_context = Context(user_id=actor_user_id)

        with patch.object(
            coordinator.notification_manager,
            "notify_approvers_translated",
            new=AsyncMock(),
        ):
            await coordinator.reward_manager.redeem(
                approver_name="Zoë",
                assignee_id=assignee_id,
                reward_id=reward_id,
            )

        assert get_pending_reward_count(coordinator, assignee_id, reward_id) == 1

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_APPLY_BONUS,
                {
                    const.SERVICE_FIELD_APPROVER_NAME: "Zoë",
                    const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                    const.SERVICE_FIELD_BONUS_NAME: "Extra Effort",
                },
                blocking=True,
                context=actor_context,
            )

    @pytest.mark.asyncio
    async def test_approver_only_can_approve_reward_but_cannot_manage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """User with can_approve only can approve reward but is denied management service."""
        coordinator = scenario_full.coordinator
        assignee_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_POINTS] = 100.0

        actor_user_internal_id = get_non_target_user_id(coordinator, assignee_id)
        actor_user_id = mock_hass_users["assignee3"].id
        actor_context = Context(user_id=actor_user_id)
        actor_user_data = coordinator._data[const.DATA_USERS][actor_user_internal_id]
        assert isinstance(actor_user_data, dict)
        actor_user_data[const.DATA_USER_HA_USER_ID] = actor_user_id
        actor_user_data[const.DATA_USER_CAN_APPROVE] = True
        actor_user_data[const.DATA_USER_CAN_MANAGE] = False

        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            with patch.object(
                coordinator.notification_manager,
                "notify_approvers_translated",
                new=AsyncMock(),
            ):
                await coordinator.reward_manager.redeem(
                    approver_name="Môm Astrid Stârblüm",
                    assignee_id=assignee_id,
                    reward_id=reward_id,
                )

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_REWARD,
            {
                const.SERVICE_FIELD_APPROVER_NAME: "Lila",
                const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                const.SERVICE_FIELD_REWARD_NAME: "Extra Screen Time",
            },
            blocking=True,
            context=actor_context,
        )

        assert get_pending_reward_count(coordinator, assignee_id, reward_id) == 0

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_APPLY_BONUS,
                {
                    const.SERVICE_FIELD_APPROVER_NAME: "Lila",
                    const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                    const.SERVICE_FIELD_BONUS_NAME: "Extra Effort",
                },
                blocking=True,
                context=actor_context,
            )

    @pytest.mark.asyncio
    async def test_manager_only_can_manage_but_cannot_approve_reward(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Manager-only user can perform management service independent of assignment."""
        coordinator = scenario_full.coordinator
        assignee_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        bonus_id = scenario_full.bonus_ids["Extra Effort"]
        coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_POINTS] = 100.0

        actor_user_internal_id = get_non_target_user_id(coordinator, assignee_id)
        actor_user_id = mock_hass_users["assignee3"].id
        actor_context = Context(user_id=actor_user_id)
        actor_user_data = coordinator._data[const.DATA_USERS][actor_user_internal_id]
        assert isinstance(actor_user_data, dict)
        actor_user_data[const.DATA_USER_HA_USER_ID] = actor_user_id
        actor_user_data[const.DATA_USER_CAN_APPROVE] = False
        actor_user_data[const.DATA_USER_CAN_MANAGE] = True

        with patch.object(
            coordinator.notification_manager,
            "notify_approvers_translated",
            new=AsyncMock(),
        ):
            await coordinator.reward_manager.redeem(
                approver_name="Môm Astrid Stârblüm",
                assignee_id=assignee_id,
                reward_id=reward_id,
            )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_APPROVE_REWARD,
                {
                    const.SERVICE_FIELD_APPROVER_NAME: "Lila",
                    const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                    const.SERVICE_FIELD_REWARD_NAME: "Extra Screen Time",
                },
                blocking=True,
                context=actor_context,
            )

        points_before_bonus = get_assignee_points(coordinator, assignee_id)

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPLY_BONUS,
            {
                const.SERVICE_FIELD_APPROVER_NAME: "Lila",
                const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                const.SERVICE_FIELD_BONUS_NAME: "Extra Effort",
            },
            blocking=True,
            context=actor_context,
        )

        points_after_bonus = get_assignee_points(coordinator, assignee_id)
        bonus_amount = coordinator.bonuses_data[bonus_id][const.DATA_BONUS_POINTS]
        assert points_after_bonus == points_before_bonus + bonus_amount

    @pytest.mark.asyncio
    async def test_dual_role_user_can_approve_and_manage_reward_flows(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Dual-role user can execute both approval and management domains."""
        coordinator = scenario_full.coordinator
        assignee_id = scenario_full.assignee_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]
        bonus_id = scenario_full.bonus_ids["Extra Effort"]
        coordinator.assignees_data[assignee_id][DATA_ASSIGNEE_POINTS] = 100.0

        actor_user_internal_id = get_non_target_user_id(coordinator, assignee_id)
        actor_user_id = mock_hass_users["assignee3"].id
        actor_context = Context(user_id=actor_user_id)
        actor_user_data = coordinator._data[const.DATA_USERS][actor_user_internal_id]
        assert isinstance(actor_user_data, dict)
        actor_user_data[const.DATA_USER_HA_USER_ID] = actor_user_id
        actor_user_data[const.DATA_USER_CAN_APPROVE] = True
        actor_user_data[const.DATA_USER_CAN_MANAGE] = True

        with patch.object(
            coordinator.notification_manager,
            "notify_approvers_translated",
            new=AsyncMock(),
        ):
            await coordinator.reward_manager.redeem(
                approver_name="Môm Astrid Stârblüm",
                assignee_id=assignee_id,
                reward_id=reward_id,
            )

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_REWARD,
            {
                const.SERVICE_FIELD_APPROVER_NAME: "Lila",
                const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                const.SERVICE_FIELD_REWARD_NAME: "Extra Screen Time",
            },
            blocking=True,
            context=actor_context,
        )

        assert get_pending_reward_count(coordinator, assignee_id, reward_id) == 0

        points_before_bonus = get_assignee_points(coordinator, assignee_id)

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPLY_BONUS,
            {
                const.SERVICE_FIELD_APPROVER_NAME: "Lila",
                const.SERVICE_FIELD_ASSIGNEE_NAME: "Zoë",
                const.SERVICE_FIELD_BONUS_NAME: "Extra Effort",
            },
            blocking=True,
            context=actor_context,
        )

        points_after_bonus = get_assignee_points(coordinator, assignee_id)
        bonus_amount = coordinator.bonuses_data[bonus_id][const.DATA_BONUS_POINTS]
        assert points_after_bonus == points_before_bonus + bonus_amount
