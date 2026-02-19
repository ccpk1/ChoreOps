"""Tests for reward CRUD services (create_reward, update_reward).

This module tests:
- create_reward service with schema validation
- update_reward service with schema validation
- E2E verification via assignee reward sensors

Testing approach:
- Schema validation with literal field names (not constants)
- E2E verification through dashboard helper and assignee sensors
- Both positive (accepts valid data) and negative (rejects invalid data) cases

See tests/SERVICE_TESTING_PATTERNS.md for patterns used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from tests.helpers import (
    DOMAIN,
    SERVICE_CREATE_REWARD,
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
# HELPER FUNCTIONS
# ============================================================================


def find_reward_in_dashboard_helper(
    hass: HomeAssistant, assignee_slug: str, reward_name: str
) -> dict[str, Any] | None:
    """Find reward in assignee's dashboard helper rewards list.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee slug (e.g., "zoe", "max", "lila")
        reward_name: Reward name to search for

    Returns:
        Reward dict if found, None otherwise
    """
    helper_state = hass.states.get(
        f"sensor.{assignee_slug}_choreops_ui_dashboard_helper"
    ) or hass.states.get(f"sensor.{assignee_slug}_choreops_ui_dashboard_helper")

    if helper_state is None:
        return None

    rewards_list = helper_state.attributes.get("rewards", [])

    for reward in rewards_list:
        if reward.get("name") == reward_name:
            return reward

    return None


def get_assignee_reward_sensor_state(
    hass: HomeAssistant, assignee_slug: str, reward_name: str
) -> Any:
    """Get assignee's reward sensor state by reward name.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee slug (e.g., "zoe", "max", "lila")
        reward_name: Reward name to construct entity ID

    Returns:
        Entity state object or None
    """
    # Convert reward name to entity-safe format
    reward_slug = reward_name.lower().replace(" ", "_").replace("-", "_")
    reward_eid = f"sensor.kc_{assignee_slug}_reward_{reward_slug}"

    return hass.states.get(reward_eid)


# ============================================================================
# CREATE REWARD - SCHEMA VALIDATION TESTS
# ============================================================================


class TestCreateRewardSchemaValidation:
    """Test create_reward schema validation with literal field names."""

    @pytest.mark.asyncio
    async def test_accepts_documented_field_names(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_reward accepts field names from services.yaml docs.

        Uses literal strings exactly as documented, not constants.
        This catches schema/documentation mismatches.
        """
        # Use exact field names from services.yaml
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_REWARD,
            {
                "name": "Test Reward Schema",
                "cost": 75.0,
                "description": "Testing schema validation",
                "icon": "mdi:test-tube",
                "labels": ["testing", "validation"],
            },
            blocking=True,
            return_response=True,
        )

        # Verify service executed successfully
        assert response is not None
        assert "id" in response
        assert isinstance(response["id"], str)

    @pytest.mark.asyncio
    async def test_rejects_old_prefixed_field_names(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_reward rejects old entity-prefixed field names.

        After refactor: fields use simple names (name, cost)
        Old prefixed names (reward_name, reward_cost) should fail
        """
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "reward_name": "Should Fail",  # ❌ Old prefixed field name
                    "reward_cost": 75.0,  # ❌ Old prefixed field name
                    "reward_description": "Test",  # ❌ Old prefixed field name
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_requires_reward_name_field(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_reward requires reward_name field."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "cost": 75.0,  # Missing required name
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_requires_reward_cost_field(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_reward requires reward_cost field."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Missing Cost",  # Missing required cost
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_rejects_extra_undocumented_fields(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_reward rejects unexpected fields."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Test",
                    "cost": 75.0,
                    "invalid_field": "should fail",  # ❌ Not in schema
                },
                blocking=True,
            )


# ============================================================================
# CREATE REWARD - E2E TESTS
# ============================================================================


class TestCreateRewardEndToEnd:
    """Test create_reward end-to-end functionality via sensors."""

    @pytest.mark.asyncio
    async def test_created_reward_appears_in_dashboard_helper(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test created reward appears in all assignees' dashboard helpers.

        E2E Pattern: Service call → Dashboard helper update → Verify
        """
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            # Create reward via service
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Dashboard Test Reward",
                    "cost": 150.0,
                    "description": "E2E testing",
                    "icon": "mdi:test-tube",
                },
                blocking=True,
                return_response=True,
            )

            reward_id = response["id"]
            assert reward_id is not None

            # Wait for coordinator update
            await hass.async_block_till_done()

        # Verify appears in dashboard helper for all assignees
        for assignee_name, assignee_slug in [
            ("Zoë", "zoe"),
            ("Max!", "max"),
            ("Lila", "lila"),
        ]:
            reward = find_reward_in_dashboard_helper(
                hass, assignee_slug, "Dashboard Test Reward"
            )

            assert reward is not None, (
                f"Reward not found in {assignee_slug}'s dashboard helper"
            )
            assert reward["cost"] == 150.0
            # Dashboard helper doesn't include description/icon
            # Only: eid, name, status, labels, cost, claims, approvals

    @pytest.mark.asyncio
    async def test_created_reward_in_coordinator_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test created reward exists in coordinator storage with correct data."""
        coordinator = scenario_full.coordinator

        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Create reward via service
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_REWARD,
                {
                    "name": "Storage Test Reward",
                    "cost": 200.0,
                    "description": "Verify storage",
                    "icon": "mdi:database",
                    "labels": ["test", "storage"],
                },
                blocking=True,
                return_response=True,
            )

            reward_id = response["id"]

        # Verify reward exists in storage
        assert reward_id in coordinator.rewards_data

        reward_data = coordinator.rewards_data[reward_id]
        assert reward_data["name"] == "Storage Test Reward"
        assert reward_data["cost"] == 200.0
        assert reward_data["description"] == "Verify storage"
        assert reward_data["icon"] == "mdi:database"
        assert reward_data["reward_labels"] == ["test", "storage"]


# ============================================================================
# UPDATE REWARD - SCHEMA VALIDATION TESTS
# ============================================================================


class TestUpdateRewardSchemaValidation:
    """Test update_reward schema validation with literal field names."""

    @pytest.mark.asyncio
    async def test_accepts_reward_id_identifier(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward accepts reward_id as identifier."""
        # Get existing reward ID
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            # Update using reward_id
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "id": reward_id,
                    "cost": 60.0,  # Update cost
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        assert "id" in response

    @pytest.mark.asyncio
    async def test_accepts_reward_name_identifier(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward accepts reward_name as identifier."""
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            # Update using reward_name
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "name": "Extra Screen Time",
                    "cost": 65.0,  # Update cost
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        assert "id" in response

    @pytest.mark.asyncio
    async def test_rejects_old_prefixed_field_names(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward rejects old entity-prefixed field names."""
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "reward_id": reward_id,  # ❌ Old prefixed field name
                    "reward_cost": 60.0,  # ❌ Old prefixed field name
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_requires_either_reward_id_or_name(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward requires reward_id OR reward_name."""
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(
            HomeAssistantError, match="Must provide either reward_id or reward_name"
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "cost": 60.0,  # Missing identifier
                },
                blocking=True,
            )


# ============================================================================
# UPDATE REWARD - E2E TESTS
# ============================================================================


class TestUpdateRewardEndToEnd:
    """Test update_reward end-to-end functionality via sensors."""

    @pytest.mark.asyncio
    async def test_updated_cost_reflects_in_dashboard_helper(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updated reward cost appears in dashboard helpers.

        E2E Pattern: Service call → Dashboard helper update → Verify
        """
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            # Update reward cost via service
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "id": reward_id,
                    "cost": 999.0,  # Distinctive value
                },
                blocking=True,
                return_response=True,
            )

            # Wait for coordinator update
            await hass.async_block_till_done()

        # Verify cost updated in all assignees' dashboard helpers
        for assignee_slug in ["zoe", "max", "lila"]:
            reward = find_reward_in_dashboard_helper(
                hass, assignee_slug, "Extra Screen Time"
            )

            assert reward is not None
            assert reward["cost"] == 999.0, (
                f"Cost not updated in {assignee_slug}'s dashboard helper"
            )

    @pytest.mark.asyncio
    async def test_updated_description_reflects_in_coordinator_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updated reward description stored in coordinator."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Update description
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "name": "Extra Screen Time",
                    "description": "Updated via E2E test",
                },
                blocking=True,
                return_response=True,
            )

            await hass.async_block_till_done()

        # Verify description in coordinator storage
        reward_data = coordinator.rewards_data[reward_id]
        assert reward_data["description"] == "Updated via E2E test"

    @pytest.mark.asyncio
    async def test_updated_labels_reflects_in_coordinator_storage(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updated reward labels stored correctly."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Update labels via service
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "id": reward_id,
                    "labels": ["updated", "labels", "test"],
                },
                blocking=True,
                return_response=True,
            )

        # Verify labels updated in storage
        reward_data = coordinator.rewards_data[reward_id]
        assert reward_data["reward_labels"] == ["updated", "labels", "test"]

    @pytest.mark.asyncio
    async def test_update_via_name_identifier(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_reward using reward_name instead of reward_id."""
        coordinator = scenario_full.coordinator
        reward_id = scenario_full.reward_ids["Extra Screen Time"]

        with patch.object(coordinator, "_persist", new=MagicMock()):
            # Update via name (not ID)
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_REWARD,
                {
                    "name": "Extra Screen Time",
                    "cost": 777.0,  # Distinctive value
                },
                blocking=True,
                return_response=True,
            )

            await hass.async_block_till_done()

        # Verify cost updated
        reward_data = coordinator.rewards_data[reward_id]
        assert reward_data["cost"] == 777.0
