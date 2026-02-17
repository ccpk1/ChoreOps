"""Test shadow kid entity creation via options flow.

Tests that verify shadow kid devices and entities are created immediately
when enabling parent chore assignment capabilities through options flow.

Bug reproduction: Shadow kid entities should be created immediately after
options flow completes, but currently require a manual config reload.
"""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.choreops import const
from tests.helpers import (
    DATA_KID_NAME,
    DATA_PARENT_LINKED_SHADOW_KID_ID,
    DATA_PARENT_NAME,
    DOMAIN,
    OPTIONS_FLOW_PARENTS,
    OPTIONS_FLOW_STEP_ADD_PARENT,
    OPTIONS_FLOW_STEP_EDIT_PARENT,
    OPTIONS_FLOW_STEP_INIT,
    SetupResult,
)
from tests.helpers.flow_test_helpers import FlowTestHelper

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
async def init_integration_with_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Initialize integration with minimal scenario for shadow kid testing."""
    from tests.helpers.setup import setup_from_yaml

    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# =========================================================================
# Shadow Kid Entity Creation Tests
# =========================================================================


class TestShadowKidEntityCreation:
    """Tests for shadow kid entity creation via options flow."""

    async def test_add_parent_with_chore_assignment_creates_shadow_kid_entities(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        device_registry: dr.DeviceRegistry,
        init_integration_with_scenario: SetupResult,
    ) -> None:
        """Shadow kid entities should be created immediately when adding parent with chore assignment.

        Bug reproduction test:
        1. Add parent via options flow with allow_chore_assignment=True
        2. Options flow completes successfully
        3. Shadow kid entities should exist immediately (currently fails)
        4. Manual reload shows entities (workaround)

        Expected: Shadow kid sensor entities appear after options flow completes
        Actual: Entities only appear after manual config reload
        """
        config_entry = init_integration_with_scenario.config_entry
        coordinator = init_integration_with_scenario.coordinator

        # Verify no shadow kid exists before adding parent

        initial_entities = [
            e
            for e in entity_registry.entities.values()
            if e.platform == DOMAIN and "shadow" in str(e.original_name).lower()
        ]
        assert len(initial_entities) == 0, (
            "No shadow kid entities should exist initially"
        )

        # Add parent with chore assignment enabled
        yaml_parent = {
            "name": "Test Parent",
            "icon": "mdi:account-tie",
            "ha_user_name": "",
            "allow_chore_assignment": True,  # This should create shadow kid
            "enable_chore_workflow": True,
            "enable_gamification": False,
        }

        # Build form data including shadow kid fields
        form_data = FlowTestHelper.build_parent_form_data(yaml_parent)

        result = await FlowTestHelper.add_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            OPTIONS_FLOW_STEP_ADD_PARENT,
            form_data,
        )

        # Verify options flow completed successfully
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify parent was created in coordinator
        parent_names = [p["name"] for p in coordinator.parents_data.values()]
        assert "Test Parent" in parent_names

        # Get the parent to verify shadow kid was linked
        parent_id = next(
            pid
            for pid, pdata in coordinator.parents_data.items()
            if pdata["name"] == "Test Parent"
        )
        parent_data = coordinator.parents_data[parent_id]

        # Verify shadow kid was created in coordinator storage
        from tests.helpers import DATA_PARENT_LINKED_SHADOW_KID_ID

        shadow_kid_id = parent_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Shadow kid should be linked to parent"
        assert shadow_kid_id in coordinator.kids_data, (
            "Shadow kid should exist in coordinator"
        )

        # CRITICAL TEST: Verify shadow kid entities are created in entity registry
        # This is the bug - entities are NOT created until manual reload
        shadow_kid_entities = [
            e
            for e in entity_registry.entities.values()
            if e.platform == DOMAIN and shadow_kid_id in e.unique_id
        ]

        # Expected entities for shadow kid (with gamification disabled):
        # - sensor.kc_<parent>_chores (always)
        # - sensor.kc_<parent>_ui_dashboard_helper (always)
        # - button.kc_<parent>_chore_approval_* (always for each chore)
        # - button.kc_<parent>_chore_claim_* (if workflow enabled)
        # - button.kc_<parent>_chore_disapproval_* (if workflow enabled)
        # Note: points sensor requires enable_gamification=True

        assert len(shadow_kid_entities) >= 2, (
            f"Shadow kid should have at least 2 entities (chores sensor + dashboard helper), "
            f"found {len(shadow_kid_entities)}"
        )

        # Verify specific entity types exist
        entity_types = {e.domain for e in shadow_kid_entities}
        assert "sensor" in entity_types, "Shadow kid should have sensor entities"

        # Verify dashboard helper exists
        dashboard_helper_entities = [
            e for e in shadow_kid_entities if "dashboard_helper" in e.entity_id
        ]
        assert len(dashboard_helper_entities) == 1, (
            "Shadow kid should have dashboard helper sensor"
        )

        # Verify device was created for shadow kid
        shadow_kid_device = device_registry.async_get_device(
            identifiers={(DOMAIN, shadow_kid_id)}
        )
        assert shadow_kid_device is not None, "Shadow kid device should exist"
        assert (
            shadow_kid_device.name is not None
            and "Test Parent" in shadow_kid_device.name
        ), "Shadow kid device name should reference parent"

    async def test_edit_parent_to_enable_chore_assignment_creates_shadow_kid(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        init_integration_with_scenario: SetupResult,
    ) -> None:
        """Shadow kid entities created when editing parent to enable chore assignment.

        Tests:
        1. Add parent via options flow WITHOUT chore assignment
        2. Edit parent to enable chore assignment
        3. Shadow kid should be created with entities
        """
        config_entry = init_integration_with_scenario.config_entry
        coordinator = init_integration_with_scenario.coordinator

        # First add parent WITHOUT chore assignment
        yaml_parent = {
            "name": "Test Parent",
            "icon": "mdi:account-tie",
            "ha_user_name": "",
            "allow_chore_assignment": False,  # Initially disabled
            "enable_chore_workflow": False,
            "enable_gamification": False,
        }

        form_data = FlowTestHelper.build_parent_form_data(yaml_parent)

        await FlowTestHelper.add_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            OPTIONS_FLOW_STEP_ADD_PARENT,
            form_data,
        )

        # Verify parent exists without shadow kid
        parent_id = next(
            pid
            for pid, pdata in coordinator.parents_data.items()
            if pdata["name"] == "Test Parent"
        )
        parent_data = coordinator.parents_data[parent_id]

        assert parent_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID) is None, (
            "Parent should not have shadow kid initially"
        )

        # Now EDIT parent to enable chore assignment using the helper
        updated_form_data = FlowTestHelper.build_parent_form_data(
            {
                **yaml_parent,
                "allow_chore_assignment": True,
                "enable_chore_workflow": True,
            }
        )

        result = await FlowTestHelper.edit_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            "Test Parent",
            updated_form_data,
        )

        # Verify edit completed (returns to init step)
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Wait for entities to be created after edit
        await hass.async_block_till_done()

        # CRITICAL: Get fresh coordinator after options flow (integration reloads)
        # Old coordinator reference is stale after options flow changes
        fresh_coordinator = await FlowTestHelper.get_coordinator(hass)
        assert fresh_coordinator is not None, "Coordinator should exist after reload"

        # Re-fetch parent data from FRESH coordinator
        parent_data = fresh_coordinator.parents_data[parent_id]
        shadow_kid_id = parent_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Shadow kid should be created after edit"
        assert shadow_kid_id in fresh_coordinator.kids_data, "Shadow kid should exist"

        # CRITICAL TEST: Verify shadow kid entities exist immediately
        shadow_kid_entities = [
            e
            for e in entity_registry.entities.values()
            if e.platform == DOMAIN and shadow_kid_id in e.unique_id
        ]

        assert len(shadow_kid_entities) >= 2, (
            f"Shadow kid should have entities immediately after edit, "
            f"found {len(shadow_kid_entities)}"
        )

    async def test_edit_parent_enable_chore_assignment_rejects_name_conflict(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        init_integration_with_scenario: SetupResult,
    ) -> None:
        """Validation rejects enabling chore assignment when name conflicts with kid.

        Scenario: A parent was added without chore assignment (no name conflict check).
        Later, the parent is edited to enable chore assignment, but the parent's
        name matches an existing kid's name. This should be rejected because
        enabling chore assignment would create a shadow kid with a duplicate name.
        """
        config_entry = init_integration_with_scenario.config_entry
        coordinator = init_integration_with_scenario.coordinator

        # Get existing kid name from scenario
        existing_kid_id = list(coordinator.kids_data.keys())[0]
        existing_kid_name = coordinator.kids_data[existing_kid_id].get(
            DATA_KID_NAME, "Test"
        )

        # Add parent with SAME NAME as existing kid, but WITHOUT chore assignment
        # This should succeed because without chore assignment, no shadow kid is created
        yaml_parent = {
            "name": existing_kid_name,  # Same as existing kid!
            "icon": "mdi:account-tie",
            "ha_user_name": "",
            "allow_chore_assignment": False,  # No chore assignment = no conflict
            "enable_chore_workflow": False,
            "enable_gamification": False,
        }

        form_data = FlowTestHelper.build_parent_form_data(yaml_parent)
        result = await FlowTestHelper.add_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            OPTIONS_FLOW_STEP_ADD_PARENT,
            form_data,
        )

        # Adding parent without chore assignment should succeed (returns to init step)
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT, (
            f"Adding parent without chore assignment should succeed, got: {result}"
        )

        # Refresh coordinator after add
        await hass.async_block_till_done()
        coordinator = await FlowTestHelper.get_coordinator(hass)

        # Find the newly added parent
        parent_id = next(
            pid
            for pid, pdata in coordinator.parents_data.items()
            if pdata.get(DATA_PARENT_NAME) == existing_kid_name
        )

        # Capture kid count before attempted edit
        kid_count_before = len(coordinator.kids_data)

        # Now try to EDIT parent to enable chore assignment
        # This should FAIL because enabling it would create shadow kid with duplicate name
        edit_form_data = FlowTestHelper.build_parent_form_data(
            {
                **yaml_parent,
                "allow_chore_assignment": True,  # Try to enable - should fail
            }
        )

        result = await FlowTestHelper.edit_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            existing_kid_name,
            edit_form_data,
        )

        # Should get validation error and stay on edit form
        assert result.get("type") == FlowResultType.FORM, (
            f"Should return form with error, got: {result.get('type')}"
        )
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_PARENT, (
            f"Should stay on edit_parent step, got: {result.get('step_id')}"
        )
        assert result.get("errors") == {
            const.CFOP_ERROR_PARENT_NAME: const.TRANS_KEY_CFOF_DUPLICATE_NAME
        }, f"Should have duplicate name error, got: {result.get('errors')}"

        # Refresh coordinator and verify no shadow kid was created
        await hass.async_block_till_done()
        coordinator = await FlowTestHelper.get_coordinator(hass)

        # Parent should still exist without shadow kid
        parent_data = coordinator.parents_data.get(parent_id)
        assert parent_data is not None, "Parent should still exist"
        assert parent_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID) is None, (
            "Parent should not have shadow kid after rejected edit"
        )

        # Kid count should be unchanged (no shadow kid created)
        assert len(coordinator.kids_data) == kid_count_before, (
            f"Kid count should be unchanged, was {kid_count_before}, "
            f"now {len(coordinator.kids_data)}"
        )

    async def test_disable_chore_assignment_removes_shadow_kid_entities(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        device_registry: dr.DeviceRegistry,
        init_integration_with_scenario: SetupResult,
    ) -> None:
        """Shadow kid entities removed when disabling parent chore assignment.

        Tests:
        1. Add parent with chore assignment (creates shadow kid)
        2. Edit parent to disable chore assignment
        3. Shadow kid and its entities should be removed
        """
        config_entry = init_integration_with_scenario.config_entry

        # Add parent WITH chore assignment (creates shadow kid)
        yaml_parent = {
            "name": "Test Parent",
            "icon": "mdi:account-tie",
            "ha_user_name": "",
            "allow_chore_assignment": True,
            "enable_chore_workflow": True,
            "enable_gamification": False,
        }

        form_data = FlowTestHelper.build_parent_form_data(yaml_parent)

        await FlowTestHelper.add_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            OPTIONS_FLOW_STEP_ADD_PARENT,
            form_data,
        )

        # CRITICAL: Get fresh coordinator after options flow (integration reloads)
        coordinator_after_add = await FlowTestHelper.get_coordinator(hass)
        assert coordinator_after_add is not None, "Coordinator should exist after add"

        # Verify shadow kid exists
        parent_id = next(
            pid
            for pid, pdata in coordinator_after_add.parents_data.items()
            if pdata["name"] == "Test Parent"
        )
        shadow_kid_id = coordinator_after_add.parents_data[parent_id].get(
            DATA_PARENT_LINKED_SHADOW_KID_ID
        )
        assert shadow_kid_id is not None, "Shadow kid should exist initially"

        # Edit parent to DISABLE chore assignment using the helper
        updated_form_data = FlowTestHelper.build_parent_form_data(
            {
                **yaml_parent,
                "allow_chore_assignment": False,
                "enable_chore_workflow": False,
            }
        )

        await FlowTestHelper.edit_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            "Test Parent",
            updated_form_data,
        )

        # CRITICAL: Get fresh coordinator after options flow
        coordinator_after_edit = await FlowTestHelper.get_coordinator(hass)
        assert coordinator_after_edit is not None, "Coordinator should exist after edit"

        # Verify shadow kid link removed from parent
        parent_data = coordinator_after_edit.parents_data[parent_id]
        assert parent_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID) is None, (
            "Shadow kid link should be removed from parent"
        )

        # Verify shadow kid UNLINKED (not deleted) - data preserved with _unlinked suffix
        # The new unlink behavior preserves the kid to avoid data loss on accidental toggle
        assert shadow_kid_id in coordinator_after_edit.kids_data, (
            "Shadow kid should be preserved (unlinked, not deleted)"
        )
        unlinked_kid_data = coordinator_after_edit.kids_data[shadow_kid_id]
        assert unlinked_kid_data.get("is_shadow_kid") is False, (
            "Shadow kid should be converted to regular kid"
        )
        assert "_unlinked" in unlinked_kid_data.get("name", ""), (
            "Unlinked kid name should have _unlinked suffix"
        )
        assert unlinked_kid_data.get("linked_parent_id") is None, (
            "Unlinked kid should have no parent link"
        )

        # Entities remain but are renamed with the kid - verify they still exist
        remaining_entities = [
            e
            for e in entity_registry.entities.values()
            if e.platform == DOMAIN and shadow_kid_id in e.unique_id
        ]
        # Entities should still exist for the unlinked kid
        assert len(remaining_entities) > 0, "Unlinked kid entities should be preserved"

        # Verify kid device still exists (renamed)
        kid_device = device_registry.async_get_device(
            identifiers={(DOMAIN, shadow_kid_id)}
        )
        assert kid_device is not None, "Unlinked kid device should be preserved"


class TestShadowKidNameConflicts:
    """Test name conflicts between shadow kids and regular kids."""

    async def test_parent_cannot_be_added_with_existing_kid_name(
        self, hass: HomeAssistant, init_integration_with_scenario: SetupResult
    ) -> None:
        """Test that parent with chore assignment cannot be added with same name as existing kid.

        When can_do_chores is enabled, a shadow kid entity is created with the parent's name.
        This would conflict with an existing kid of the same name, so validation rejects it.
        """
        config_entry = init_integration_with_scenario.config_entry
        coordinator = init_integration_with_scenario.coordinator

        # Capture original parent count (scenario has 1 parent)
        original_parent_count = len(coordinator.parents_data)

        # Get existing kid name from scenario (should be "Zoë" from minimal)
        existing_kids = list(coordinator.kids_data.values())
        assert len(existing_kids) >= 1, "Scenario should have at least one kid"
        existing_kid_name = existing_kids[0][const.DATA_KID_NAME]

        # Try to add parent with same name as existing kid AND chore assignment enabled
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_PARENTS},
        )

        # Select "Add" action
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                const.OPTIONS_FLOW_INPUT_MANAGE_ACTION: const.OPTIONS_FLOW_ACTIONS_ADD
            },
        )

        # Try to add parent with existing kid's name AND chore assignment (should conflict)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                const.CFOF_PARENTS_INPUT_NAME: existing_kid_name,
                const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: True,  # Creates shadow kid
            },
        )

        # Should get validation error (shadow kid would have duplicate name)
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "add_parent"
        assert result.get("errors") == {
            const.CFOP_ERROR_PARENT_NAME: const.TRANS_KEY_CFOF_DUPLICATE_NAME
        }

        # Verify no new parent was created (count unchanged)
        assert len(coordinator.parents_data) == original_parent_count

    async def test_kid_cannot_be_added_with_existing_parent_name(
        self, hass: HomeAssistant, init_integration_with_scenario: SetupResult
    ) -> None:
        """Test that kid cannot be added with same name as shadow kid parent.

        When a parent has can_do_chores enabled, their name is used for a shadow kid.
        Adding a regular kid with the same name would create a naming conflict.
        """
        config_entry = init_integration_with_scenario.config_entry
        coordinator = init_integration_with_scenario.coordinator

        # Capture original parent count before we start
        original_parent_count = len(coordinator.parents_data)

        # First add a parent WITH chore assignment (creates shadow kid)
        yaml_parent = {
            "name": "ParentTest",
            "icon": "mdi:account-tie",
            "ha_user_name": "",
            "allow_chore_assignment": True,  # This creates a shadow kid
            "enable_chore_workflow": True,
            "enable_gamification": False,
        }

        form_data = FlowTestHelper.build_parent_form_data(yaml_parent)
        await FlowTestHelper.add_entity_via_options_flow(
            hass,
            config_entry.entry_id,
            OPTIONS_FLOW_PARENTS,
            OPTIONS_FLOW_STEP_ADD_PARENT,
            form_data,
        )

        # Verify parent was created (original + 1)
        assert len(coordinator.parents_data) == original_parent_count + 1
        # Get the newly added parent by finding one named "ParentTest"
        parent_data = next(
            p
            for p in coordinator.parents_data.values()
            if p[const.DATA_PARENT_NAME] == "ParentTest"
        )
        parent_name = parent_data[const.DATA_PARENT_NAME]
        assert parent_name == "ParentTest"

        # Capture kid count AFTER adding parent+shadow kid
        # (includes original kids plus the new shadow kid)
        kid_count_after_parent = len(coordinator.kids_data)

        # Now try to add kid with same name as shadow kid parent
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_KIDS},
        )

        # Select "Add" action
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                const.OPTIONS_FLOW_INPUT_MANAGE_ACTION: const.OPTIONS_FLOW_ACTIONS_ADD
            },
        )

        # Try to add kid with parent's name (should conflict)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                const.CFOF_KIDS_INPUT_KID_NAME: "ParentTest",  # Same as parent
            },
        )

        # Should get validation error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "add_kid"
        assert result.get("errors") == {
            const.CFOP_ERROR_KID_NAME: const.TRANS_KEY_CFOF_DUPLICATE_NAME
        }

        # Verify no additional kid was created (count unchanged since adding parent)
        assert len(coordinator.kids_data) == kid_count_after_parent

    async def test_shadow_kid_cannot_have_same_name_as_regular_kid(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        init_integration_with_scenario: SetupResult,
    ) -> None:
        """Verify validation prevents parent from having same name as existing kid.

        When a parent with chore assignment would create a shadow kid, the
        validation should reject the parent if the name matches an existing
        kid name (to prevent the shadow kid from having a duplicate name).
        """
        config_entry = init_integration_with_scenario.config_entry
        coordinator = init_integration_with_scenario.coordinator

        # Capture original counts
        original_parent_count = len(coordinator.parents_data)
        original_kid_count = len(coordinator.kids_data)

        # Get the existing kid from scenario (should be "Zoë" from minimal)
        existing_kids = list(coordinator.kids_data.values())
        assert len(existing_kids) >= 1, "Scenario should have at least one kid"

        # Rename existing kid to "John" to set up conflict test
        existing_kid_id = list(coordinator.kids_data.keys())[0]
        coordinator._data[const.DATA_KIDS][existing_kid_id][const.DATA_KID_NAME] = (
            "John"
        )

        # Try to add parent named "John" with chore assignment enabled
        # This would create shadow kid also named "John" - validation should reject
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_PARENTS},
        )

        # Select "Add" action
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                const.OPTIONS_FLOW_INPUT_MANAGE_ACTION: const.OPTIONS_FLOW_ACTIONS_ADD
            },
        )

        # Try to add parent with kid's name (should be rejected)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                const.CFOF_PARENTS_INPUT_NAME: "John",  # Same as existing kid
                const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: True,
            },
        )

        # Should get validation error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "add_parent"
        assert result.get("errors") == {
            const.CFOP_ERROR_PARENT_NAME: const.TRANS_KEY_CFOF_DUPLICATE_NAME
        }

        # Verify no new parent or shadow kid was created
        assert len(coordinator.parents_data) == original_parent_count
        assert len(coordinator.kids_data) == original_kid_count
