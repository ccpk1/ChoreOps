"""Test parent shadow kid creation and configuration.

This module tests the parent-as-kid functionality via shadow kid profiles:

1. Shadow kid creation:
   - Created during initial config flow when allow_chore_assignment=True
   - Created in options flow when enabling chore assignment for existing parent
   - NOT created when allow_chore_assignment=False

2. Shadow kid attributes:
   - is_shadow_kid=True marker
   - linked_parent_id points to parent internal_id
   - Parent has linked_shadow_kid_id pointing to shadow kid
   - Shadow kid inherits parent name

3. Shadow kid in chore assignment:
   - Shadow kid appears in kid lists for chore assignment
   - Chores can be assigned to shadow kid
   - Shadow kid can claim/complete chores

4. Configuration flags:
   - enable_chore_workflow controls claim/approve buttons
   - enable_gamification controls points/badges

5. Deletion behaviors:
   - Deleting shadow kid directly disables parent's allow_chore_assignment
   - Deleting parent cascades to delete linked shadow kid

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.helpers import (
    DATA_CHORE_ASSIGNED_KIDS,
    DATA_CHORE_NAME,
    DATA_KID_CHORE_DATA,
    DATA_KID_IS_SHADOW,
    DATA_KID_LINKED_PARENT_ID,
    DATA_KID_NAME,
    DATA_KID_POINTS,
    DATA_PARENT_ALLOW_CHORE_ASSIGNMENT,
    DATA_PARENT_ENABLE_CHORE_WORKFLOW,
    DATA_PARENT_ENABLE_GAMIFICATION,
    DATA_PARENT_LINKED_SHADOW_KID_ID,
    DATA_PARENT_NAME,
    SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER,
    SetupResult,
    construct_entity_id,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def shadow_kid_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with parent shadow kid configuration.

    Configuration:
    - Dad: allow_chore_assignment=True, enable_gamification=True
           Creates shadow kid linked to Dad
    - Mom: allow_chore_assignment=False (no shadow kid)
    - Sarah: regular kid
    - Chores: "Mow lawn" (Dad only), "Make bed" (Sarah only),
              "Take out trash" (Dad + Sarah)
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_parent_shadow_kids.yaml",
    )


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up full scenario: 3 kids (Zoë, Max!, Lila), 2 parents, many chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_parent_by_name(coordinator: Any, name: str) -> tuple[str, dict[str, Any]]:
    """Find parent by name, return (parent_id, parent_data)."""
    for parent_id, parent_data in coordinator.parents_data.items():
        if parent_data.get(DATA_PARENT_NAME) == name:
            return parent_id, parent_data
    raise ValueError(f"Parent '{name}' not found")


def get_kid_by_name(coordinator: Any, name: str) -> tuple[str, dict[str, Any]]:
    """Find kid by name, return (kid_id, kid_data)."""
    for kid_id, kid_data in coordinator.kids_data.items():
        if kid_data.get(DATA_KID_NAME) == name:
            return kid_id, kid_data
    raise ValueError(f"Kid '{name}' not found")


def get_shadow_kid_for_parent(
    coordinator: Any, parent_id: str
) -> tuple[str, dict[str, Any]] | None:
    """Find shadow kid linked to parent, return (kid_id, kid_data) or None."""
    for kid_id, kid_data in coordinator.kids_data.items():
        if kid_data.get(DATA_KID_IS_SHADOW) is True:
            if kid_data.get(DATA_KID_LINKED_PARENT_ID) == parent_id:
                return kid_id, kid_data
    return None


def get_chore_by_name(coordinator: Any, name: str) -> tuple[str, dict[str, Any]]:
    """Find chore by name, return (chore_id, chore_data)."""
    for chore_id, chore_data in coordinator.chores_data.items():
        if chore_data.get(DATA_CHORE_NAME) == name:
            return chore_id, chore_data
    raise ValueError(f"Chore '{name}' not found")


# ============================================================================
# SHADOW KID CREATION TESTS
# ============================================================================


class TestShadowKidCreation:
    """Tests for shadow kid creation during config flow."""

    async def test_shadow_kid_created_when_allow_chore_assignment_true(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid is created when allow_chore_assignment=True."""
        coordinator = shadow_kid_scenario.coordinator

        # Find Dad (who has allow_chore_assignment=True)
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")

        # Verify Dad has linked_shadow_kid_id
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have linked_shadow_kid_id set"

        # Verify shadow kid exists
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)
        assert shadow_kid_data is not None, (
            f"Shadow kid with id {shadow_kid_id} should exist"
        )

    async def test_shadow_kid_not_created_when_allow_chore_assignment_false(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid is NOT created when allow_chore_assignment=False."""
        coordinator = shadow_kid_scenario.coordinator

        # Find Mom (who has allow_chore_assignment=False)
        mom_id, mom_data = get_parent_by_name(coordinator, "Môm Astrid Stârblüm")

        # Verify Mom does NOT have linked_shadow_kid_id
        shadow_kid_id = mom_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is None, "Mom should NOT have linked_shadow_kid_id"

        # Double-check: no shadow kid with linked_parent_id=mom_id
        shadow_kid = get_shadow_kid_for_parent(coordinator, mom_id)
        assert shadow_kid is None, "No shadow kid should be linked to Mom"


# ============================================================================
# SHADOW KID ATTRIBUTES TESTS
# ============================================================================


class TestShadowKidAttributes:
    """Tests for shadow kid attribute configuration."""

    async def test_shadow_kid_has_is_shadow_marker(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid has is_shadow_kid=True marker."""
        coordinator = shadow_kid_scenario.coordinator

        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)

        assert shadow_kid_data is not None
        assert shadow_kid_data.get(DATA_KID_IS_SHADOW) is True

    async def test_shadow_kid_has_linked_parent_id(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid has linked_parent_id pointing to parent."""
        coordinator = shadow_kid_scenario.coordinator

        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have shadow kid"
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)

        assert shadow_kid_data is not None
        assert shadow_kid_data.get(DATA_KID_LINKED_PARENT_ID) == dad_id

    async def test_shadow_kid_inherits_parent_name(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid name matches parent name."""
        coordinator = shadow_kid_scenario.coordinator

        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have shadow kid"
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)

        assert shadow_kid_data is not None
        assert shadow_kid_data.get(DATA_KID_NAME) == "Dad Leo"

    async def test_shadow_kid_has_initial_zero_points(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid starts with zero points."""
        coordinator = shadow_kid_scenario.coordinator

        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have shadow kid"
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)

        assert shadow_kid_data is not None
        assert shadow_kid_data.get(DATA_KID_POINTS, 0) == 0

    async def test_parent_configuration_flags_stored(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Parent configuration flags are stored correctly."""
        coordinator = shadow_kid_scenario.coordinator

        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")

        # Verify Dad's configuration flags
        assert dad_data.get(DATA_PARENT_ALLOW_CHORE_ASSIGNMENT) is True
        assert dad_data.get(DATA_PARENT_ENABLE_CHORE_WORKFLOW) is False
        assert dad_data.get(DATA_PARENT_ENABLE_GAMIFICATION) is True

        # Verify Mom's configuration (all disabled/default)
        mom_id, mom_data = get_parent_by_name(coordinator, "Môm Astrid Stârblüm")
        assert mom_data.get(DATA_PARENT_ALLOW_CHORE_ASSIGNMENT) is False


# ============================================================================
# SHADOW KID IN CHORE ASSIGNMENT TESTS
# ============================================================================


class TestShadowKidChoreAssignment:
    """Tests for shadow kid chore assignment."""

    async def test_shadow_kid_appears_in_kids_data(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid appears in coordinator.kids_data."""
        coordinator = shadow_kid_scenario.coordinator

        # Find Dad's shadow kid
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)

        # Verify shadow kid is in kids_data
        assert shadow_kid_id in coordinator.kids_data

    async def test_chore_assigned_to_shadow_kid_only(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Chore can be assigned only to shadow kid."""
        coordinator = shadow_kid_scenario.coordinator

        # Find "Mow lawn" chore (assigned to Dad only)
        chore_id, chore_data = get_chore_by_name(coordinator, "Mow lawn")

        # Get Dad's shadow kid
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)

        # Verify assignment
        assigned_kids = chore_data.get(DATA_CHORE_ASSIGNED_KIDS, [])
        assert shadow_kid_id in assigned_kids
        assert len(assigned_kids) == 1  # Only shadow kid assigned

    async def test_chore_assigned_to_regular_kid_only(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Chore can be assigned only to regular kid."""
        coordinator = shadow_kid_scenario.coordinator

        # Find "Make bed" chore (assigned to Sarah only)
        chore_id, chore_data = get_chore_by_name(coordinator, "Make bed")

        # Get Sarah's kid id
        sarah_id, sarah_data = get_kid_by_name(coordinator, "Zoë")

        # Verify assignment
        assigned_kids = chore_data.get(DATA_CHORE_ASSIGNED_KIDS, [])
        assert sarah_id in assigned_kids
        assert len(assigned_kids) == 1  # Only Sarah assigned

    async def test_chore_assigned_to_shadow_kid_and_regular_kid(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Chore can be assigned to both shadow kid and regular kid."""
        coordinator = shadow_kid_scenario.coordinator

        # Find "Take out trash" chore (assigned to Dad and Sarah)
        chore_id, chore_data = get_chore_by_name(coordinator, "Take out trash")

        # Get Dad's shadow kid and Sarah
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        sarah_id, sarah_data = get_kid_by_name(coordinator, "Zoë")

        # Verify assignment
        assigned_kids = chore_data.get(DATA_CHORE_ASSIGNED_KIDS, [])
        assert shadow_kid_id in assigned_kids
        assert sarah_id in assigned_kids
        assert len(assigned_kids) == 2

    async def test_shadow_kid_has_chore_data_structure(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Shadow kid has chore_data structure for assigned chores."""
        coordinator = shadow_kid_scenario.coordinator

        # Get Dad's shadow kid
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have shadow kid"
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)
        assert shadow_kid_data is not None, "Shadow kid should exist"

        # Shadow kid should have chore_data dict
        chore_data = shadow_kid_data.get(DATA_KID_CHORE_DATA, {})
        assert isinstance(chore_data, dict)


# ============================================================================
# REGULAR KID DISTINCTION TESTS
# ============================================================================


class TestRegularKidDistinction:
    """Tests to verify regular kids are not affected by shadow kid feature."""

    async def test_regular_kid_not_marked_as_shadow(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Regular kid is NOT marked as shadow kid."""
        coordinator = shadow_kid_scenario.coordinator

        sarah_id, sarah_data = get_kid_by_name(coordinator, "Zoë")

        # Verify Sarah is NOT a shadow kid
        assert sarah_data.get(DATA_KID_IS_SHADOW) is not True

    async def test_regular_kid_has_no_linked_parent(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Regular kid does NOT have linked_parent_id."""
        coordinator = shadow_kid_scenario.coordinator

        sarah_id, sarah_data = get_kid_by_name(coordinator, "Zoë")

        # Verify Sarah has no linked parent
        assert sarah_data.get(DATA_KID_LINKED_PARENT_ID) is None


# ============================================================================
# DATA INTEGRITY TESTS
# ============================================================================


class TestDataIntegrity:
    """Tests for data integrity and consistency."""

    async def test_total_kid_count_includes_shadow_kids(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Total kid count includes shadow kids."""
        coordinator = shadow_kid_scenario.coordinator

        # Expected: Sarah (regular) + Dad (shadow) = 2 kids
        # (Mom has no shadow kid)
        assert len(coordinator.kids_data) == 2

    async def test_total_parent_count_correct(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Total parent count is correct."""
        coordinator = shadow_kid_scenario.coordinator

        # Expected: Dad + Mom = 2 parents
        assert len(coordinator.parents_data) == 2

    async def test_bidirectional_link_integrity(
        self,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Verify parent -> shadow kid and shadow kid -> parent links match."""
        coordinator = shadow_kid_scenario.coordinator

        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have shadow kid"
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)
        assert shadow_kid_data is not None, "Shadow kid should exist"

        # Verify bidirectional link
        assert shadow_kid_data.get(DATA_KID_LINKED_PARENT_ID) == dad_id
        assert dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID) == shadow_kid_id

    async def test_dashboard_helper_exposes_shadow_kid_capabilities(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Dashboard helper sensor exposes shadow kid capability flags."""
        coordinator = shadow_kid_scenario.coordinator

        # Get Dad's shadow kid
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have shadow kid"

        # Get shadow kid name
        shadow_kid_data = coordinator.kids_data.get(shadow_kid_id)
        assert shadow_kid_data is not None, "Shadow kid should exist"
        shadow_kid_name = shadow_kid_data.get(DATA_KID_NAME)

        # Get dashboard helper sensor
        dashboard_helper_eid = construct_entity_id(
            "sensor", shadow_kid_name, SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        dashboard_state = hass.states.get(dashboard_helper_eid)
        assert dashboard_state is not None, (
            f"Dashboard helper should exist: {dashboard_helper_eid}"
        )

        # Verify shadow kid flags exposed
        attrs = dashboard_state.attributes
        assert attrs.get("is_shadow_kid") is True, "Should be marked as shadow kid"
        assert attrs.get("chore_workflow_enabled") is False, (
            "Dad has workflow disabled (approval-only)"
        )
        assert attrs.get("gamification_enabled") is True, (
            "Dad has gamification enabled (per scenario YAML)"
        )

        # Verify regular kid does NOT have these flags set
        sarah_dashboard_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        sarah_state = hass.states.get(sarah_dashboard_eid)
        assert sarah_state is not None, "Sarah's dashboard helper should exist"

        sarah_attrs = sarah_state.attributes
        assert sarah_attrs.get("is_shadow_kid") is False, (
            "Regular kid should not be shadow"
        )
        assert sarah_attrs.get("chore_workflow_enabled") is True, (
            "Regular kids always have workflow"
        )
        assert sarah_attrs.get("gamification_enabled") is True, (
            "Regular kids always have gamification"
        )


# ============================================================================
# DELETION TESTS
# ============================================================================


class TestShadowKidDeletion:
    """Test deletion behaviors for shadow kids and their linked parents.

    Tests verify:
    1. Direct shadow kid deletion disables parent's allow_chore_assignment
    2. Parent deletion cascades to delete linked shadow kid
    3. Regular kid deletion is unaffected by shadow kid logic
    """

    async def test_delete_shadow_kid_disables_parent_chore_assignment(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Deleting shadow kid directly should disable parent's chore assignment.

        Expected behavior:
        1. Find Dad's shadow kid
        2. Delete shadow kid via coordinator.delete_kid_entity()
        3. Parent's allow_chore_assignment should be False
        4. Parent's linked_shadow_kid_id should be None
        5. Shadow kid should be UNLINKED (not deleted) to preserve data
        """
        coordinator = shadow_kid_scenario.coordinator

        # Find Dad and his shadow kid
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have a shadow kid"
        assert shadow_kid_id in coordinator.kids_data, "Shadow kid should exist"

        # Verify initial state
        assert dad_data.get(DATA_PARENT_ALLOW_CHORE_ASSIGNMENT) is True

        # Delete the shadow kid directly
        coordinator.user_manager.delete_kid(shadow_kid_id)

        # Refresh parent data
        _, updated_dad_data = get_parent_by_name(coordinator, "Dad Leo")

        # Verify: Parent's chore assignment flag disabled
        assert updated_dad_data.get(DATA_PARENT_ALLOW_CHORE_ASSIGNMENT) is False, (
            "Parent's allow_chore_assignment should be disabled after shadow kid deletion"
        )

        # Verify: Parent's link cleared
        assert updated_dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID) is None, (
            "Parent's linked_shadow_kid_id should be None after shadow kid deletion"
        )

        # Verify: Shadow kid UNLINKED (not deleted) - data preserved
        # The unlink behavior preserves the kid to avoid data loss on accidental toggle
        assert shadow_kid_id in coordinator.kids_data, (
            "Shadow kid should be preserved (unlinked, not deleted)"
        )
        unlinked_kid_data = coordinator.kids_data[shadow_kid_id]
        assert unlinked_kid_data.get("is_shadow_kid") is False, (
            "Shadow kid should be converted to regular kid"
        )
        assert "_unlinked" in unlinked_kid_data.get("name", ""), (
            "Unlinked kid name should have _unlinked suffix"
        )
        assert unlinked_kid_data.get("linked_parent_id") is None, (
            "Unlinked kid should have no parent link"
        )

    async def test_delete_parent_cascades_to_shadow_kid(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Deleting parent with shadow kid should cascade UNLINK the shadow kid.

        Expected behavior:
        1. Find Dad and his shadow kid
        2. Delete parent via coordinator.delete_parent_entity()
        3. Shadow kid should be UNLINKED (not deleted) to preserve data
        4. Parent should no longer exist
        """
        coordinator = shadow_kid_scenario.coordinator

        # Find Dad and his shadow kid
        dad_id, dad_data = get_parent_by_name(coordinator, "Dad Leo")
        shadow_kid_id = dad_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID)
        assert shadow_kid_id is not None, "Dad should have a shadow kid"
        assert shadow_kid_id in coordinator.kids_data, "Shadow kid should exist"
        assert dad_id in coordinator.parents_data, "Dad should exist"

        # Delete the parent
        coordinator.user_manager.delete_parent(dad_id)

        # Verify: Parent removed
        assert dad_id not in coordinator.parents_data, (
            "Parent should be removed from parents_data"
        )

        # Verify: Shadow kid cascade UNLINKED (not deleted) - data preserved
        # The unlink behavior preserves the kid to avoid data loss
        assert shadow_kid_id in coordinator.kids_data, (
            "Shadow kid should be preserved (unlinked, not deleted)"
        )
        unlinked_kid_data = coordinator.kids_data[shadow_kid_id]
        assert unlinked_kid_data.get("is_shadow_kid") is False, (
            "Shadow kid should be converted to regular kid"
        )
        assert "_unlinked" in unlinked_kid_data.get("name", ""), (
            "Unlinked kid name should have _unlinked suffix"
        )
        assert unlinked_kid_data.get("linked_parent_id") is None, (
            "Unlinked kid should have no parent link"
        )

    async def test_delete_parent_without_shadow_kid(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
    ) -> None:
        """Deleting parent without shadow kid should work normally.

        Expected behavior:
        1. Find Mom (no shadow kid)
        2. Delete parent via coordinator.delete_parent_entity()
        3. Parent should be deleted
        4. No cascade effects
        """
        coordinator = shadow_kid_scenario.coordinator

        # Find Mom (no shadow kid)
        mom_id, mom_data = get_parent_by_name(coordinator, "Môm Astrid Stârblüm")
        assert mom_data.get(DATA_PARENT_LINKED_SHADOW_KID_ID) is None, (
            "Mom should not have a shadow kid"
        )
        assert mom_id in coordinator.parents_data, "Mom should exist"

        # Count kids before deletion
        kids_count_before = len(coordinator.kids_data)

        # Delete the parent
        coordinator.user_manager.delete_parent(mom_id)

        # Verify: Parent removed
        assert mom_id not in coordinator.parents_data, (
            "Parent should be removed from parents_data"
        )

        # Verify: No kids affected
        assert len(coordinator.kids_data) == kids_count_before, (
            "No kids should be affected when deleting parent without shadow kid"
        )
