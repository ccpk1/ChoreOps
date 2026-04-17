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

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
import pytest
import voluptuous as vol

from custom_components.choreops import const
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
    from homeassistant.helpers.entity_registry import EntityRegistry


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


def get_dashboard_helper_state(hass: HomeAssistant, assignee_slug: str) -> State:
    """Return a dashboard helper state for an assignee slug."""
    helper_state = hass.states.get(
        f"sensor.{assignee_slug}_choreops_ui_dashboard_helper"
    )
    assert helper_state is not None
    return helper_state


def get_button_entity_id(
    entity_registry: EntityRegistry,
    entry_id: str,
    assignee_id: str,
    chore_id: str,
    suffix: str,
) -> str | None:
    """Return a chore workflow button entity ID from unique-id parts."""
    unique_id = f"{entry_id}_{assignee_id}_{chore_id}{suffix}"
    return entity_registry.async_get_entity_id("button", DOMAIN, unique_id)


def _set_user_manage_capability(
    coordinator: Any,
    *,
    ha_user_id: str,
    can_manage: bool,
) -> None:
    """Set manage capability for the linked user record."""
    users = coordinator._data.get(const.DATA_USERS, {})
    for user_data in users.values():
        if not isinstance(user_data, dict):
            continue
        if user_data.get(const.DATA_USER_HA_USER_ID) == ha_user_id:
            user_data[const.DATA_USER_CAN_MANAGE] = can_manage
            return

    raise AssertionError(f"No user mapped to HA user_id={ha_user_id}")


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
                    "assigned_user_names": ["Zoë", "Max!"],
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
    async def test_requires_name_and_assigned_user_names(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore requires name and assigned_user_names fields."""
        # Missing name
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "assigned_user_names": ["Zoë"],
                    "points": 10,
                },
                blocking=True,
            )


class TestChoreCrudAuthorization:
    """Test management authorization gates on chore CRUD services."""

    @pytest.mark.asyncio
    async def test_create_chore_requires_manage_capability(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Create is denied when the linked user lacks manage permission."""
        actor_user_id = mock_hass_users["assignee1"].id
        _set_user_manage_capability(
            scenario_full.coordinator,
            ha_user_id=actor_user_id,
            can_manage=False,
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Unauthorized Create",
                    "assigned_user_names": ["Zoë"],
                    "points": 5,
                    const.SERVICE_FIELD_CONFIG_ENTRY_ID: scenario_full.config_entry.entry_id,
                },
                blocking=True,
                context=Context(user_id=actor_user_id),
            )

    @pytest.mark.asyncio
    async def test_update_chore_requires_manage_capability(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Update is denied when the linked user lacks manage permission."""
        actor_user_id = mock_hass_users["assignee1"].id
        _set_user_manage_capability(
            scenario_full.coordinator,
            ha_user_id=actor_user_id,
            can_manage=False,
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "name": "Make bed",
                    "points": 99,
                    const.SERVICE_FIELD_CONFIG_ENTRY_ID: scenario_full.config_entry.entry_id,
                },
                blocking=True,
                context=Context(user_id=actor_user_id),
            )

    @pytest.mark.asyncio
    async def test_delete_chore_requires_manage_capability(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Delete is denied when the linked user lacks manage permission."""
        actor_user_id = mock_hass_users["assignee1"].id
        _set_user_manage_capability(
            scenario_full.coordinator,
            ha_user_id=actor_user_id,
            can_manage=False,
        )

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_CHORE,
                {
                    "name": "Make bed",
                    const.SERVICE_FIELD_CONFIG_ENTRY_ID: scenario_full.config_entry.entry_id,
                },
                blocking=True,
                context=Context(user_id=actor_user_id),
            )

        # Missing assigned_user_names
        with pytest.raises(HomeAssistantError):
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
                    "assigned_user_names": ["Zoë"],
                    "points": 10,
                    "invalid_field": "should fail",  # ❌ Not in schema
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_accepts_advanced_overdue_handling_option(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore accepts advanced overdue handling values exposed by contracts."""
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Overdue Handling Contract Test",
                    "assigned_user_names": ["Zoë", "Max!"],
                    "points": 10,
                    "frequency": "daily",
                    "approval_reset_type": "at_midnight_once",
                    "overdue_handling": "at_due_date_mark_missed_and_lock",
                    "due_date": "2099-01-01T09:00:00",
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        assert "id" in response

    @pytest.mark.asyncio
    async def test_accepts_custom_frequency_fields(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore accepts custom interval fields from services.yaml docs."""
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Custom Contract Chore",
                    "assigned_user_names": ["Zoë", "Max!"],
                    "frequency": "custom",
                    "custom_interval": 6,
                    "custom_interval_unit": "months",
                    "due_date": "2099-01-01T09:00:00",
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        assert "id" in response

    @pytest.mark.asyncio
    async def test_rejects_custom_frequency_without_custom_interval(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore rejects custom frequency payloads missing interval data."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Broken Custom Chore",
                    "assigned_user_names": ["Zoë"],
                    "frequency": "custom",
                    "due_date": "2099-01-01T09:00:00",
                },
                blocking=True,
            )


# ============================================================================
# CREATE CHORE - E2E TESTS
# ============================================================================


class TestCreateChoreEndToEnd:
    """Test create_chore end-to-end functionality."""

    @pytest.mark.asyncio
    async def test_create_uses_runtime_entity_sync(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test create_chore uses the shared runtime sync path."""
        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator,
                "async_sync_chore_entities",
                new=AsyncMock(),
            ) as mock_sync,
            patch.object(
                scenario_full.coordinator,
                "async_sync_entities_after_service_create",
                new=AsyncMock(),
            ) as legacy_sync,
        ):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Runtime Sync Create Contract",
                    "assigned_user_names": ["Zoë"],
                    "points": 15,
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        mock_sync.assert_awaited_once()
        legacy_sync.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_does_not_reload_config_entry(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test chore create does not fall back to config-entry reload."""
        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                hass.config_entries, "async_reload", new=AsyncMock()
            ) as reload_entry,
        ):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "No Reload Create Chore",
                    "assigned_user_names": ["Zoë"],
                    "points": 10,
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        reload_entry.assert_not_awaited()

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
                    "assigned_user_names": ["Zoë", "Max!"],
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
        Validates: points, description, labels, assigned_user_names, completion_criteria
        """
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Attribute Test Chore",
                    "assigned_user_names": ["Zoë", "Max!", "Lila"],
                    "points": 25,
                    "description": "Verifying all attributes",
                    "labels": ["test", "e2e"],
                    "completion_criteria": "shared_first",
                    "frequency": "weekly",
                    "due_date": "2099-01-01T09:00:00",
                },
                blocking=True,
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

        helper_state = get_dashboard_helper_state(hass, "zoe")
        chores_by_label = helper_state.attributes[const.ATTR_CHORES_BY_LABEL]
        assert chore["eid"] in chores_by_label["test"]
        assert chore["eid"] in chores_by_label["e2e"]

    @pytest.mark.asyncio
    async def test_created_chore_exposes_live_status_and_buttons(
        self,
        hass: HomeAssistant,
        entity_registry: EntityRegistry,
        scenario_full: SetupResult,
    ) -> None:
        """Test service create materializes live chore sensor and workflow buttons."""
        config_entry = scenario_full.config_entry
        coordinator = scenario_full.coordinator

        with patch.object(coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Live Surface Create Chore",
                    "assigned_user_names": ["Zoë"],
                    "points": 15,
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        chore_id = response["id"]
        await hass.async_block_till_done()

        zoe_chore = find_chore_in_dashboard_helper(
            hass, "zoe", "Live Surface Create Chore"
        )
        assert zoe_chore is not None
        assert zoe_chore["eid"] is not None
        assert hass.states.get(zoe_chore["eid"]) is not None

        zoe_id = scenario_full.assignee_ids["Zoë"]
        approve_eid = get_button_entity_id(
            entity_registry,
            config_entry.entry_id,
            zoe_id,
            chore_id,
            const.BUTTON_KC_UID_SUFFIX_APPROVE,
        )
        disapprove_eid = get_button_entity_id(
            entity_registry,
            config_entry.entry_id,
            zoe_id,
            chore_id,
            const.BUTTON_KC_UID_SUFFIX_DISAPPROVE,
        )
        assert approve_eid is not None
        assert disapprove_eid is not None
        assert hass.states.get(approve_eid) is not None
        assert hass.states.get(disapprove_eid) is not None

    @pytest.mark.asyncio
    async def test_create_independent_weekly_uses_per_assignee_due_dates_only(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test service create stores independent recurring due dates per assignee only."""
        new_due_date = datetime(2099, 1, 1, 9, 0, tzinfo=UTC)

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Independent Weekly Service Test",
                    "assigned_user_names": ["Zoë", "Max!"],
                    "points": 25,
                    "frequency": "weekly",
                    "completion_criteria": "independent",
                    "due_date": new_due_date,
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        chore_id = response.get("id")
        assert isinstance(chore_id, str)

        created_chore = scenario_full.coordinator.chores_data[chore_id]
        assert created_chore.get(const.DATA_CHORE_DUE_DATE) is None

        per_assignee_due_dates = created_chore.get(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
            {},
        )
        assert set(per_assignee_due_dates) == {
            scenario_full.assignee_ids["Zoë"],
            scenario_full.assignee_ids["Max!"],
        }

        expected_due_date = new_due_date.isoformat()
        assert all(
            due_date == expected_due_date
            for due_date in per_assignee_due_dates.values()
        )


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
    async def test_rejects_completion_criteria_in_update(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update_chore rejects completion_criteria while excluded from update contract."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "completion_criteria": "rotation_simple",
                },
                blocking=True,
            )

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

    @pytest.mark.asyncio
    async def test_update_weekly_independent_without_due_date_preserves_existing_dates(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updating a weekly independent chore succeeds without resending due_date."""
        chore_id = scenario_full.chore_ids["Ørgänize Bookshelf"]
        existing_chore = scenario_full.coordinator.chores_data[chore_id]
        existing_per_assignee_due_dates = dict(
            existing_chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
        )

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "points": 42,
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        updated_chore = scenario_full.coordinator.chores_data[chore_id]
        assert updated_chore[const.DATA_CHORE_DEFAULT_POINTS] == 42
        assert updated_chore.get(const.DATA_CHORE_DUE_DATE) is None
        assert (
            updated_chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
            == existing_per_assignee_due_dates
        )

    @pytest.mark.asyncio
    async def test_update_custom_chore_preserves_existing_custom_interval(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test updating a custom chore does not require resending existing custom settings."""
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            create_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Existing Custom Chore",
                    "assigned_user_names": ["Zoë"],
                    "frequency": "custom",
                    "custom_interval": 4,
                    "custom_interval_unit": "weeks",
                    "due_date": "2099-01-01T09:00:00",
                },
                blocking=True,
                return_response=True,
            )

            assert create_response is not None
            chore_id = create_response["id"]

            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "points": 77,
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        updated_chore = scenario_full.coordinator.chores_data[chore_id]
        assert updated_chore[const.DATA_CHORE_DEFAULT_POINTS] == 77
        assert updated_chore[const.DATA_CHORE_CUSTOM_INTERVAL] == 4
        assert updated_chore[const.DATA_CHORE_CUSTOM_INTERVAL_UNIT] == "weeks"


# ============================================================================
# UPDATE CHORE - E2E TESTS
# ============================================================================


class TestUpdateChoreEndToEnd:
    """Test update_chore end-to-end functionality via dashboard helper."""

    @pytest.mark.asyncio
    async def test_assignment_change_uses_runtime_entity_sync(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test assignment changes use the shared runtime sync path."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator,
                "async_sync_chore_entities",
                new=AsyncMock(),
            ) as mock_sync,
            patch.object(
                scenario_full.coordinator,
                "async_sync_entities_after_service_create",
                new=AsyncMock(),
            ) as legacy_sync,
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "assigned_user_names": ["Max!"],
                },
                blocking=True,
                return_response=True,
            )

        mock_sync.assert_awaited_once()
        legacy_sync.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_does_not_reload_config_entry(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test chore update does not reload the config entry."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                hass.config_entries, "async_reload", new=AsyncMock()
            ) as reload_entry,
        ):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {"id": chore_id, "points": 77},
                blocking=True,
                return_response=True,
            )

        assert response is not None
        reload_entry.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_assignment_change_updates_live_entity_surfaces(
        self,
        hass: HomeAssistant,
        entity_registry: EntityRegistry,
        scenario_full: SetupResult,
    ) -> None:
        """Test assignment expansion and shrinkage update live helper and button surfaces."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]
        config_entry = scenario_full.config_entry

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "assigned_user_names": ["Zoë", "Max!"],
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        await hass.async_block_till_done()

        max_chore = find_chore_in_dashboard_helper(hass, "max", "Täke Öut Trash")
        assert max_chore is not None
        assert max_chore["eid"] is not None
        assert hass.states.get(max_chore["eid"]) is not None

        max_id = scenario_full.assignee_ids["Max!"]
        approve_eid = get_button_entity_id(
            entity_registry,
            config_entry.entry_id,
            max_id,
            chore_id,
            const.BUTTON_KC_UID_SUFFIX_APPROVE,
        )
        assert approve_eid is not None

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "assigned_user_names": ["Max!"],
                },
                blocking=True,
                return_response=True,
            )

        assert response is not None
        await hass.async_block_till_done()

        assert find_chore_in_dashboard_helper(hass, "zoe", "Täke Öut Trash") is None
        assert (
            get_button_entity_id(
                entity_registry,
                config_entry.entry_id,
                scenario_full.assignee_ids["Zoë"],
                chore_id,
                const.BUTTON_KC_UID_SUFFIX_APPROVE,
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_rename_uses_runtime_entity_sync(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test rename updates also use the shared runtime sync path."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator,
                "async_sync_chore_entities",
                new=AsyncMock(),
            ) as mock_sync,
            patch.object(
                scenario_full.coordinator,
                "async_sync_entities_after_service_create",
                new=AsyncMock(),
            ) as legacy_sync,
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "name": "Runtime Sync Renamed by Service",
                },
                blocking=True,
                return_response=True,
            )

        mock_sync.assert_awaited_once()
        legacy_sync.assert_not_awaited()

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

    @pytest.mark.asyncio
    async def test_update_independent_weekly_due_date_applies_to_all_assignees(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test update service applies one independent due date to every assigned assignee."""
        chore_id = scenario_full.chore_ids["Ørgänize Bookshelf"]
        new_due_date = datetime(2099, 2, 1, 10, 30, tzinfo=UTC)

        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPDATE_CHORE,
                {
                    "id": chore_id,
                    "due_date": new_due_date,
                },
                blocking=True,
                return_response=True,
            )

        updated_chore = scenario_full.coordinator.chores_data[chore_id]
        assert updated_chore.get(const.DATA_CHORE_DUE_DATE) is None

        per_assignee_due_dates = updated_chore.get(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
            {},
        )
        assert set(per_assignee_due_dates) == {
            scenario_full.assignee_ids["Zoë"],
            scenario_full.assignee_ids["Lila"],
        }
        assert all(
            due_date == new_due_date.isoformat()
            for due_date in per_assignee_due_dates.values()
        )


# ============================================================================
# DELETE CHORE - E2E TESTS
# ============================================================================


class TestDeleteChoreEndToEnd:
    """Test delete_chore end-to-end functionality via dashboard helper."""

    @pytest.mark.asyncio
    async def test_delete_uses_runtime_entity_sync(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test delete_chore uses the shared runtime sync path."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator,
                "async_sync_chore_entities",
                new=AsyncMock(),
            ) as mock_sync,
        ):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_CHORE,
                {"id": chore_id},
                blocking=True,
                return_response=True,
            )

        assert response is not None
        mock_sync.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_does_not_reload_config_entry(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test chore delete does not reload the config entry."""
        chore_id = scenario_full.chore_ids["Täke Öut Trash"]

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                hass.config_entries, "async_reload", new=AsyncMock()
            ) as reload_entry,
        ):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_DELETE_CHORE,
                {"id": chore_id},
                blocking=True,
                return_response=True,
            )

        assert response is not None
        reload_entry.assert_not_awaited()

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
        with patch.object(scenario_full.coordinator, "_persist", new=MagicMock()):
            create_response = await hass.services.async_call(
                DOMAIN,
                SERVICE_CREATE_CHORE,
                {
                    "name": "Delete Test Chore",
                    "assigned_user_names": ["Zoë", "Max!"],
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
