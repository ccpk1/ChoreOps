"""Test shadow kid button entity creation based on workflow configuration.

This module tests conditional button creation for shadow kids:

1. Shadow kid with workflow disabled (approval-only mode):
   - ONLY Approve button created
   - NO Claim or Disapprove buttons

2. Shadow kid with workflow enabled (full workflow mode):
   - Claim, Approve, and Disapprove buttons all created
   - Same behavior as regular kids

3. Regular kid buttons (control group):
   - Always has all three buttons (Claim, Approve, Disapprove)

Button creation is controlled by:
- Shadow kid marker (is_shadow_kid=True)
- Parent's enable_chore_workflow flag

Test patterns follow tests/AGENT_TEST_CREATION_INSTRUCTIONS.md:
- Approach B (Service Calls + Entity State) for button press validation
- Entity registry lookups for entity existence
- State verification via entity states

See scenario_parent_shadow_kids.yaml for test data configuration.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
import pytest

from tests.helpers import (
    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID,
    ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID,
    SetupResult,
    setup_from_yaml,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


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
    - Dad: allow_chore_assignment=True, enable_chore_workflow=False
           Shadow kid with ONLY Approve button
    - Mom: allow_chore_assignment=False (no shadow kid)
    - Zoë: regular kid (all buttons)
    - Chores: "Mow lawn" (Dad only), "Make bed" (Sarah only),
              "Take out trash" (Dad + Sarah)
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_parent_shadow_kids.yaml",
    )
    # Ensure all entities are fully created before tests run
    await hass.async_block_till_done()
    return result


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def button_entity_exists(entity_registry: er.EntityRegistry, entity_id: str) -> bool:
    """Check if button entity exists in entity registry."""
    return entity_registry.async_get(entity_id) is not None


# ============================================================================
# SHADOW KID BUTTON CREATION TESTS (APPROVAL-ONLY MODE)
# ============================================================================


class TestShadowKidApprovalOnlyButtons:
    """Tests for shadow kid buttons when workflow disabled (approval-only)."""

    async def test_shadow_kid_has_approve_button_only(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
        entity_registry: er.EntityRegistry,
    ) -> None:
        """Shadow kid with workflow=False has ONLY Approve button."""
        # Get Dad's dashboard helper (Rule 3: Dashboard Helper as Single Source of Truth)
        from tests.helpers.workflows import get_dashboard_helper

        # Wait for dashboard helper to be fully populated
        helper_attrs = None
        for _ in range(10):  # Retry up to 10 times
            try:
                helper_attrs = get_dashboard_helper(hass, "dad_leo")
                if helper_attrs.get("chores"):
                    break
            except ValueError:
                pass
            await hass.async_block_till_done()
            import asyncio

            await asyncio.sleep(0.1)

        assert helper_attrs is not None, "Dad's dashboard helper should exist"

        # Verify Dad is a shadow kid with workflow disabled
        assert helper_attrs.get("is_shadow_kid") is True, "Dad should be a shadow kid"
        assert helper_attrs.get("chore_workflow_enabled") is False, (
            "Dad should have workflow disabled"
        )

        # Get chores from dashboard helper
        chores_list = helper_attrs.get("chores", [])
        assert len(chores_list) > 0, "Dad should have chores assigned"

        # Test first chore (should be "Mow lawn")
        chore_info = chores_list[0]
        assert chore_info["name"] == "Mow lawn"
        chore_sensor_eid = chore_info["eid"]

        # Get button IDs from chore sensor attributes (Rule 4: Button IDs from chore sensor)
        chore_state = hass.states.get(chore_sensor_eid)
        assert chore_state is not None, f"Chore sensor {chore_sensor_eid} should exist"

        claim_button_id = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)
        approve_button_id = chore_state.attributes.get(
            ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
        )
        disapprove_button_id = chore_state.attributes.get(
            ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID
        )

        # Verify Approve button EXISTS (shadow kid with workflow disabled has ONLY approve)
        assert approve_button_id is not None, (
            "Approve button should exist for shadow kid with workflow disabled"
        )
        # Ensure button entity is fully created before checking its state
        await hass.async_block_till_done()
        assert hass.states.get(approve_button_id) is not None

        # Verify Claim button DOES NOT EXIST (no claim for approval-only mode)
        assert claim_button_id is None, (
            "Claim button should NOT exist for shadow kid with workflow disabled"
        )

        # Verify Disapprove button DOES NOT EXIST (no disapprove for approval-only mode)
        assert disapprove_button_id is None, (
            "Disapprove button should NOT exist for shadow kid with workflow disabled"
        )

    async def test_approve_button_works_from_pending_state(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
        entity_registry: er.EntityRegistry,
    ) -> None:
        """Approve button transitions chore from PENDING to APPROVED."""
        # Get Dad's dashboard helper (Rule 3: Dashboard Helper as Single Source of Truth)
        from tests.helpers.workflows import get_dashboard_helper

        # Wait for dashboard helper to be fully populated
        helper_attrs = None
        for _ in range(10):  # Retry up to 10 times
            try:
                helper_attrs = get_dashboard_helper(hass, "dad_leo")
                if helper_attrs.get("chores"):
                    break
            except ValueError:
                pass
            await hass.async_block_till_done()
            await asyncio.sleep(0.1)

        assert helper_attrs is not None, "Dashboard helper should exist"

        # Get chores from dashboard helper
        chores_list = helper_attrs.get("chores", [])
        chore_info = next(c for c in chores_list if c.get("name") == "Mow lawn")
        chore_status_sensor = chore_info.get("eid")

        # Get approve button ID from chore sensor attributes (Rule 4: Button IDs from chore sensor)
        chore_state = hass.states.get(chore_status_sensor)
        assert chore_state is not None, (
            f"Chore sensor {chore_status_sensor} should exist"
        )

        approve_button_id = chore_state.attributes.get(
            ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
        )
        assert approve_button_id is not None, (
            f"Approve button should exist. Sensor attributes: {chore_state.attributes}"
        )

        # Initial state should be "pending" (chore just assigned)
        initial_state = hass.states.get(chore_status_sensor)
        assert initial_state is not None, (
            f"Chore sensor {chore_status_sensor} should exist"
        )
        assert initial_state.state == "pending", (
            f"Initial chore state should be 'pending' but was '{initial_state.state}'. "
            f"This may indicate test isolation issues - each test should get fresh state."
        )

        # Press Approve button
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {"entity_id": approve_button_id},
            blocking=True,
        )

        # Verify state transitioned to "approved"
        final_state = hass.states.get(chore_status_sensor)
        assert final_state is not None
        assert final_state.state == "approved", (
            "Chore should transition from PENDING to APPROVED"
        )


# ============================================================================
# SHADOW KID BUTTON CREATION TESTS (FULL WORKFLOW MODE)
# ============================================================================


@pytest.fixture
async def shadow_kid_workflow_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with workflow-enabled shadow kid.

    Configuration:
    - Dad: allow_chore_assignment=True, enable_chore_workflow=True
           Creates shadow kid with full workflow (claim/disapprove enabled)
    - Mom: allow_chore_assignment=False (no shadow kid)
    - Zoë: regular kid
    - Chores: "Mow lawn" (Dad only), "Make bed" (Sarah only),
              "Take out trash" (Dad + Sarah)
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_parent_shadow_kids_workflow.yaml",
    )
    # Ensure all entities are fully created before tests run
    await hass.async_block_till_done()
    return result


async def test_shadow_kid_with_workflow_enabled_has_all_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    shadow_kid_workflow_scenario: SetupResult,
) -> None:
    """Shadow kid with workflow=True has Claim, Approve, Disapprove buttons."""
    # Get Dad's dashboard helper (Dad is the shadow kid with workflow enabled)
    from tests.helpers.workflows import get_dashboard_helper

    # Wait for dashboard helper to be fully populated
    helper_attrs = None
    for _ in range(10):  # Retry up to 10 times
        try:
            helper_attrs = get_dashboard_helper(hass, "dad_leo")
            if helper_attrs.get("chores"):
                break
        except ValueError:
            pass
        await hass.async_block_till_done()
        await asyncio.sleep(0.1)

    assert helper_attrs is not None, "Dad's dashboard helper should exist"

    # Verify Dad is a shadow kid with workflow enabled
    assert helper_attrs.get("is_shadow_kid") is True, "Dad should be a shadow kid"
    assert helper_attrs.get("chore_workflow_enabled") is True, (
        "Dad should have workflow enabled"
    )

    # Get chores from dashboard helper
    chores_list = helper_attrs.get("chores", [])
    assert len(chores_list) > 0, "Dad should have chores assigned"

    # Test first chore (should be "Mow lawn")
    chore_info = chores_list[0]
    assert chore_info["name"] == "Mow lawn"
    chore_sensor_eid = chore_info["eid"]

    # Get button IDs from chore sensor attributes
    chore_state = hass.states.get(chore_sensor_eid)
    assert chore_state is not None, f"Chore sensor {chore_sensor_eid} should exist"

    claim_button = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)
    approve_button = chore_state.attributes.get(ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID)
    disapprove_button = chore_state.attributes.get(
        ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID
    )

    # Verify all three button types exist for workflow-enabled shadow kid
    assert claim_button is not None, (
        "Claim button should exist for workflow-enabled shadow kid"
    )
    assert approve_button is not None, (
        "Approve button should exist for workflow-enabled shadow kid"
    )
    assert disapprove_button is not None, (
        "Disapprove button should exist for workflow-enabled shadow kid"
    )

    approve_entity = entity_registry.async_get(approve_button)
    disapprove_entity = entity_registry.async_get(disapprove_button)
    claim_entity = entity_registry.async_get(claim_button)

    assert claim_entity is not None, f"Claim button {claim_button} should exist"
    assert approve_entity is not None, f"Approve button {approve_button} should exist"
    assert disapprove_entity is not None, (
        f"Disapprove button {disapprove_button} should exist"
    )

    # Verify buttons are available in Home Assistant
    claim_state = hass.states.get(claim_button)
    approve_state = hass.states.get(approve_button)
    disapprove_state = hass.states.get(disapprove_button)

    assert claim_state is not None, "Claim button state should be available"
    assert approve_state is not None, "Approve button state should be available"
    assert disapprove_state is not None, "Disapprove button state should be available"


# ============================================================================
# BUTTON COUNT VALIDATION TESTS
# ============================================================================


class TestButtonCountValidation:
    """Tests validating button entity counts across scenarios."""

    async def test_button_count_for_shadow_kid_approval_only(
        self,
        hass: HomeAssistant,
        shadow_kid_scenario: SetupResult,
        entity_registry: er.EntityRegistry,
    ) -> None:
        """Shadow kid with workflow=False has fewer buttons than regular kid."""
        # Get Dad's dashboard helper (Rule 3: Dashboard Helper as Single Source of Truth)
        from tests.helpers.workflows import get_dashboard_helper

        # Wait for dashboard helper to be fully populated
        dad_helper_attrs = None
        for _ in range(10):  # Retry up to 10 times
            try:
                dad_helper_attrs = get_dashboard_helper(hass, "dad_leo")
                if dad_helper_attrs.get("chores"):
                    break
            except ValueError:
                pass
            await hass.async_block_till_done()
            await asyncio.sleep(0.1)

        assert dad_helper_attrs is not None, "Dad's dashboard helper should exist"
        assert dad_helper_attrs.get("is_shadow_kid") is True, (
            "Dad should be a shadow kid"
        )
        assert dad_helper_attrs.get("chore_workflow_enabled") is False, (
            "Dad should have workflow disabled"
        )

        # Get Zoë's dashboard helper (Rule 3: Dashboard Helper as Single Source of Truth)
        from tests.helpers.workflows import get_dashboard_helper

        zoe_helper_attrs = get_dashboard_helper(hass, "zoe")
        assert zoe_helper_attrs.get("is_shadow_kid") is False, (
            "Zoë should be a regular kid"
        )

        # Count CHORE button entities for Dad by reading from chore sensors
        # (Rule 4: Button IDs from chore sensor attributes)
        dad_button_ids = []
        for chore in dad_helper_attrs.get("chores", []):
            chore_sensor_eid = chore.get("eid")
            chore_state = hass.states.get(chore_sensor_eid)
            if chore_state:
                # Collect all button entity IDs from chore sensor
                if btn_id := chore_state.attributes.get(
                    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID
                ):
                    dad_button_ids.append(btn_id)
                if btn_id := chore_state.attributes.get(
                    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
                ):
                    dad_button_ids.append(btn_id)
                if btn_id := chore_state.attributes.get(
                    ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID
                ):
                    dad_button_ids.append(btn_id)

        # Count CHORE button entities for Zoë by reading from chore sensors
        zoe_button_ids = []
        for chore in zoe_helper_attrs.get("chores", []):
            chore_sensor_eid = chore.get("eid")
            chore_state = hass.states.get(chore_sensor_eid)
            if chore_state:
                # Collect all button entity IDs from chore sensor
                if btn_id := chore_state.attributes.get(
                    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID
                ):
                    zoe_button_ids.append(btn_id)
                if btn_id := chore_state.attributes.get(
                    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
                ):
                    zoe_button_ids.append(btn_id)
                if btn_id := chore_state.attributes.get(
                    ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID
                ):
                    zoe_button_ids.append(btn_id)

        # Dad should have fewer buttons than Zoë
        # Dad: 1 Approve button per chore (2 chores = 2 buttons)
        # Zoë: 3 buttons per chore (2 chores = 6 buttons)
        assert len(dad_button_ids) < len(zoe_button_ids), (
            f"Shadow kid (workflow=False) should have fewer buttons. "
            f"Dad: {len(dad_button_ids)}, Zoë: {len(zoe_button_ids)}"
        )

        # Specific counts based on scenario:
        # Dad has "Mow lawn" (1 button) + "Take out trash" (1 button) = 2 buttons
        assert len(dad_button_ids) == 2, (
            f"Expected 2 buttons for Dad, got {len(dad_button_ids)}"
        )

        # Zoë has "Make bed" (3 buttons) + "Take out trash" (3 buttons) = 6 buttons
        assert len(zoe_button_ids) == 6, (
            f"Expected 6 buttons for Zoë, got {len(zoe_button_ids)}"
        )
