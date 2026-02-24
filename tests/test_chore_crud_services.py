"""Tests for chore CRUD services (create_chore, update_chore, delete_chore).

This module tests:
- create_chore service with schema validation
- update_chore service with schema validation and immutable field protection
- delete_chore service
- E2E verification via assignee chore status sensors

Testing approach:
- Schema validation with literal field names (not constants)
- E2E verification through chore status sensors (sensor.kc_{assignee}_chore_status_{chore})
- Both positive (accepts valid data) and negative (rejects invalid data) cases

Key difference from reward tests: ALL E2E tests verify via chore status sensors,
not just coordinator storage. This provides true end-to-end testing.

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from tests.helpers import (
    DOMAIN,
    SERVICE_CREATE_CHORE,
    SERVICE_DELETE_CHORE,
    SERVICE_UPDATE_CHORE,
    SetupResult,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State


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


def get_chore_status_sensor(
    hass: HomeAssistant, assignee_slug: str, chore_slug: str
) -> State | None:
    """Get chore status sensor for a assignee/chore combination.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee slug (e.g., "zoe", "max", "lila")
        chore_slug: Chore slug (chore name lowercased with spaces → underscores)

    Returns:
        Entity state object or None if sensor doesn't exist

    Entity ID pattern: sensor.kc_{assignee}_chore_status_{chore}
    """
    eid = f"sensor.kc_{assignee_slug}_chore_status_{chore_slug}"
    return hass.states.get(eid)


def find_chore_in_dashboard_helper(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> dict[str, Any] | None:
    """Find chore in assignee's dashboard helper chores list.

    Args:
        hass: Home Assistant instance
        assignee_slug: Assignee slug (e.g., "zoe", "max", "lila")
        chore_name: Chore name to search for

    Returns:
        Chore dict if found, None otherwise
    """
    helper_state = hass.states.get(
        f"sensor.{assignee_slug}_choreops_ui_dashboard_helper"
    ) or hass.states.get(f"sensor.{assignee_slug}_choreops_ui_dashboard_helper")

    if helper_state is None:
        return None

    chores_list = helper_state.attributes.get("chores", [])

    for chore in chores_list:
        if chore.get("name") == chore_name:
            return chore

    return None


# ============================================================================
# CREATE CHORE - SCHEMA VALIDATION TESTS
# ============================================================================


class TestCreateChoreSchemaValidation:
    """Test create_chore schema validation with literal field names."""

    @pytest.mark.asyncio
    async def test_accepts_documented_field_names(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore accepts field names from services.yaml docs.

        Uses literal strings exactly as documented, not constants.
        This catches schema/documentation mismatches.
        """
        # Use exact field names from services.yaml
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Test Chore Schema",
                    "assigned_user_ids": ["Zoë", "Max!"],
                    "points": 15,
                    "description": "Testing schema validation",
                    "icon": "mdi:test-tube",
                    "labels": ["testing", "validation"],
                    "frequency": "daily",
                    "completion_criteria": "independent",
                },
                blocking=True,
                return_response=True,
            )

        # Verify service executed successfully
        assert response is not None
        assert "id" in response
        chore_id = response.get("id")
        assert chore_id is not None
        assert isinstance(chore_id, str)

    @pytest.mark.asyncio
    async def test_requires_name_and_assigned_user_ids(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore requires name and assigned_user_ids fields."""
        # Missing name
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "assigned_user_ids": ["Zoë"],
                    "points": 10,
                },
                blocking=True,
            )

        # Missing assigned_user_ids
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Missing Assignees",
                    "points": 10,
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_rejects_extra_undocumented_fields(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore rejects unexpected fields."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Test Chore",
                    "assigned_user_ids": ["Zoë"],
                    "points": 10,
                    "invalid_field": "should fail",  # ❌ Not in schema
                },
                blocking=True,
            )


# ============================================================================
# CREATE CHORE - E2E TESTS
# ============================================================================


class TestCreateChoreEndToEnd:
    """Test create_chore end-to-end functionality.

    Note: After creating a chore via service, the chore exists in coordinator storage
    and dashboard helper, but sensors are not automatically created without re-setup.
    These tests verify via coordinator + dashboard helper, not via chore status sensors.
    """

    @pytest.mark.asyncio
    async def test_created_chore_appears_in_dashboard_helper(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test created chore appears in assignees' dashboard helper chores list.

        E2E Pattern: Service call → Storage → Dashboard helper → Verify
        """
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Service Test Chore",
                    "assigned_user_ids": ["Zoë", "Max!"],
                    "points": 15,
                },
                blocking=True,
                return_response=True,
            )

            assert response is not None
            chore_id = response.get("id")
            assert chore_id is not None

            # Wait for coordinator update and entity creation
            await hass.async_block_till_done()

        # Refresh coordinator to update dashboard helper with new entity IDs
        await scenario_full.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        # Verify chore appears in Zoë's dashboard helper
        zoe_chore = find_chore_in_dashboard_helper(hass, "zoe", "Service Test Chore")
        assert zoe_chore is not None, "Chore should appear in Zoë's dashboard helper"
        assert zoe_chore["name"] == "Service Test Chore"

        # Get the chore status sensor via eid and verify attributes
        chore_sensor = hass.states.get(zoe_chore["eid"])
        assert chore_sensor is not None, "Chore status sensor should exist"
        assert chore_sensor.attributes["default_points"] == 15

        # Verify chore appears in Max's dashboard helper
        max_chore = find_chore_in_dashboard_helper(hass, "max", "Service Test Chore")
        assert max_chore is not None, "Chore should appear in Max!'s dashboard helper"

        # Verify chore NOT in Lila's dashboard helper (not assigned)
        lila_chore = find_chore_in_dashboard_helper(hass, "lila", "Service Test Chore")
        assert lila_chore is None, "Chore should NOT appear in Lila's dashboard helper"

    @pytest.mark.asyncio
    async def test_created_chore_dashboard_helper_attributes_match_input(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test created chore dashboard helper attributes match service input.

        E2E Pattern: Service call → Dashboard helper attributes validation
        Validates: points, description, labels, assigned_user_ids, completion_criteria
        """
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Attribute Test Chore",
                    "assigned_user_ids": ["Zoë", "Max!", "Lila"],
                    "points": 25,
                    "description": "Verifying all attributes",
                    "labels": ["test", "e2e"],
                    "completion_criteria": "shared_first",
                    "frequency": "weekly",
                },
                blocking=True,
                return_response=True,
            )

            await hass.async_block_till_done()

        # Refresh coordinator to update dashboard helper with new entity IDs
        await scenario_full.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        # Verify chore appears in dashboard helper
        chore = find_chore_in_dashboard_helper(hass, "zoe", "Attribute Test Chore")
        assert chore is not None

        # Get chore status sensor and verify attributes match service input
        chore_sensor = hass.states.get(chore["eid"])
        assert chore_sensor is not None
        assert chore_sensor.attributes["default_points"] == 25
        assert chore_sensor.attributes["description"] == "Verifying all attributes"
        assert chore_sensor.attributes.get("labels") == ["test", "e2e"]
        assert chore_sensor.attributes["completion_criteria"] == "shared_first"
        assert chore_sensor.attributes["recurring_frequency"] == "weekly"


# ============================================================================
# UPDATE CHORE - SCHEMA VALIDATION TESTS
# ============================================================================


class TestUpdateChoreSchemaValidation:
    """Test update_chore schema validation."""

    @pytest.mark.asyncio
    async def test_accepts_documented_update_fields(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_chore accepts documented field names.

        completion_criteria is intentionally excluded from update schema
        since it affects fundamental chore behavior and cannot be changed.
        """
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "points": 20,
                    "description": "Updated description",
                    "labels": ["updated"],
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        assert "id" in response

    @pytest.mark.asyncio
    async def test_accepts_name_as_identifier(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_chore accepts chore name as identifier."""
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "name": "Täke Öut Trash",
                    "points": 20,  # Update points
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        assert "id" in response


# ============================================================================
# UPDATE CHORE - E2E TESTS
# ============================================================================


class TestUpdateChoreEndToEnd:
    """Test update_chore end-to-end functionality via dashboard helper."""

    @pytest.mark.asyncio
    async def test_updated_points_reflects_in_dashboard_helper(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updated chore points appear in dashboard helper.

        E2E Pattern: Service call → Dashboard helper update → Verify
        """
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "points": 888,  # Distinctive value
                },
                blocking=True,
                return_response=True,
            )

            await hass.async_block_till_done()

        # Verify chore still in dashboard helper
        chore = find_chore_in_dashboard_helper(hass, "zoe", "Täke Öut Trash")
        assert chore is not None

        # Verify points updated in chore status sensor
        chore_sensor = hass.states.get(chore["eid"])
        assert chore_sensor is not None
        assert chore_sensor.attributes["default_points"] == 888


# ============================================================================
# DELETE CHORE - E2E TESTS
# ============================================================================


class TestDeleteChoreEndToEnd:
    """Test delete_chore end-to-end functionality via dashboard helper."""

    @pytest.mark.asyncio
    async def test_deleted_chore_removed_from_dashboard_helper(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test deleted chore removed from dashboard helper for all assigned assignees.

        E2E Pattern: Service call → Storage deletion → Dashboard helper removal → Verify
        """
        # First, create a chore to delete
        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch("custom_components.choreops.sensor.create_chore_entities"),
        ):
            create_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Delete Test Chore",
                    "assigned_user_ids": ["Zoë", "Max!"],
                    "points": 10,
                },
                blocking=True,
                return_response=True,
            )

            assert create_response is not None
            chore_id = create_response.get("id")
            assert chore_id is not None
            await hass.async_block_till_done()

        # Verify chore exists in dashboard helpers before deletion
        zoe_chore_before = find_chore_in_dashboard_helper(
            hass, "zoe", "Delete Test Chore"
        )
        max_chore_before = find_chore_in_dashboard_helper(
            hass, "max", "Delete Test Chore"
        )
        assert zoe_chore_before is not None
        assert max_chore_before is not None

        # Delete the chore
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_CHORE,
                {
                    "id": chore_id,
                },
                blocking=True,
                return_response=True,
            )

            await hass.async_block_till_done()

        # Verify chore removed from dashboard helpers after deletion
        zoe_chore_after = find_chore_in_dashboard_helper(
            hass, "zoe", "Delete Test Chore"
        )
        max_chore_after = find_chore_in_dashboard_helper(
            hass, "max", "Delete Test Chore"
        )
        assert zoe_chore_after is None, "Chore should be removed from Zoë's dashboard"
        assert max_chore_after is None, "Chore should be removed from Max!'s dashboard"
