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

import pytest

from custom_components.choreops.const import (
    DATA_KID_POINTS,
    DATA_KID_REWARD_DATA,
    DATA_KID_REWARD_DATA_PENDING_COUNT,
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
    """Load full scenario: 3 kids, 2 parents, 8 chores, 3 rewards."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_kid_points(coordinator: Any, kid_id: str) -> float:
    """Get current points for a kid."""
    kid_info = coordinator.kids_data.get(kid_id, {})
    return kid_info.get(DATA_KID_POINTS, 0.0)


def get_pending_reward_count(coordinator: Any, kid_id: str, reward_id: str) -> int:
    """Get pending claim count for a kid's reward."""
    kid_info = coordinator.kids_data.get(kid_id, {})
    reward_data = kid_info.get(DATA_KID_REWARD_DATA, {})
    reward_entry = reward_data.get(reward_id, {})
    return reward_entry.get(DATA_KID_REWARD_DATA_PENDING_COUNT, 0)


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

        When a parent approves a reward with cost_override < reward's stored cost,
        the kid should have only the override amount deducted from their points.

        Use case: "Weekend special" - kid earns reward at discounted price.
        """
        coordinator = scenario_full.coordinator

        # Get test entities
        kid_id = scenario_full.kid_ids["Zoë"]
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        # Verify reward's stored cost (should be 50 per scenario_full.yaml)
        reward_info = coordinator.rewards_data.get(reward_id, {})
        stored_cost = reward_info.get(DATA_REWARD_COST, 0)
        assert stored_cost == 50, f"Expected reward cost 50, got {stored_cost}"

        # Give kid enough points to afford the reward
        starting_points = 100.0
        coordinator.kids_data[kid_id][DATA_KID_POINTS] = starting_points

        with patch.object(
            coordinator.notification_manager, "notify_kid", new=AsyncMock()
        ):
            with patch.object(
                coordinator.notification_manager,
                "notify_parents_translated",
                new=AsyncMock(),
            ):
                # Kid claims the reward (redeem is the claim method)
                await coordinator.reward_manager.redeem(
                    parent_name="Môm Astrid Stârblüm",
                    kid_id=kid_id,
                    reward_id=reward_id,
                )

                # Verify reward is pending approval
                pending_count = get_pending_reward_count(coordinator, kid_id, reward_id)
                assert pending_count == 1, "Reward should be pending after claim"

                # Parent approves with lesser cost (20 instead of 50)
                lesser_cost = 20.0
                await coordinator.reward_manager.approve(
                    parent_name="Môm Astrid Stârblüm",
                    kid_id=kid_id,
                    reward_id=reward_id,
                    cost_override=lesser_cost,
                )

        # Verify: Only the override amount was deducted
        final_points = get_kid_points(coordinator, kid_id)
        expected_points = starting_points - lesser_cost  # 100 - 20 = 80

        assert final_points == expected_points, (
            f"Expected {expected_points} points after lesser cost override, "
            f"got {final_points}. Should deduct {lesser_cost}, not {stored_cost}."
        )

        # Verify: Pending count is cleared
        pending_after = get_pending_reward_count(coordinator, kid_id, reward_id)
        assert pending_after == 0, "Pending count should be 0 after approval"
