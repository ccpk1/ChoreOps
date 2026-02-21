"""Test HA User ID clearing functionality via options flow.

Validates that users can properly clear HA user links for kids and parents
through the options flow interface, following the established Stårblüm family patterns.
"""

from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
import pytest

from tests.helpers import (
    # Parent form constants
    CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT,
    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS,
    CFOF_PARENTS_INPUT_CAN_APPROVE,
    CFOF_PARENTS_INPUT_CAN_MANAGE,
    CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW,
    CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION,
    CFOF_PARENTS_INPUT_HA_USER,
    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE,
    CFOF_PARENTS_INPUT_NAME,
    # Common constants
    DATA_PARENT_HA_USER_ID,
    OPTIONS_FLOW_ACTIONS_EDIT,
    OPTIONS_FLOW_INPUT_ENTITY_NAME,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_KIDS,
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_USERS,
    SENTINEL_NO_SELECTION,
)
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: Zoë, Mom, basic setup."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestHaUserIdClearing:
    """Test HA User ID clearing via options flow."""

    async def test_kid_management_not_exposed_in_options_menu(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Test that kid management route is not available in hard-fork options menu."""
        config_entry = scenario_minimal.config_entry

        # Step 1: Open options flow and verify init step
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Step 2: Attempt removed kid management route and assert validation error
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
            )

    async def test_parent_ha_user_id_can_be_cleared(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that parent HA user ID can be set and then cleared through options flow."""
        config_entry = scenario_minimal.config_entry
        coordinator = config_entry.runtime_data

        if not coordinator.parents_data:
            pytest.skip("Scenario has no user-role profiles to edit")

        approver_candidates = [
            (user_id, user_data)
            for user_id, user_data in coordinator.parents_data.items()
            if user_data.get("can_approve", False) or user_data.get("can_manage", False)
        ]
        if not approver_candidates:
            approver_candidates = list(coordinator.parents_data.items())
        assert approver_candidates, "Expected at least one editable managed user"
        parent_id, parent_data = approver_candidates[0]
        parent_name = str(parent_data.get(CFOF_PARENTS_INPUT_NAME, ""))

        assert parent_name

        # Step 1: Navigate to parents management (init -> select entity type)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_USERS},
        )

        # Step 2: Select edit action
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_EDIT},
        )

        # Step 3: Select the parent to edit by name
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_ENTITY_NAME: parent_name},
        )

        # Step 4: Set a HA user ID first - provide ALL required form fields
        # Use a real HA user ID from the mock_hass_users fixture
        test_ha_user = mock_hass_users["parent2"]  # Different user to avoid original
        associated_kids = [
            kid_id
            for kid_id, kid_data in coordinator.kids_data.items()
            if not kid_data.get("is_shadow_kid", False)
        ][:1]
        with patch(
            "custom_components.choreops.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            result = await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={
                    CFOF_PARENTS_INPUT_NAME: parent_name,
                    CFOF_PARENTS_INPUT_HA_USER: test_ha_user.id,  # Set a user ID
                    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: associated_kids,
                    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE: SENTINEL_NO_SELECTION,
                    CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: True,
                    CFOF_PARENTS_INPUT_CAN_APPROVE: False,
                    CFOF_PARENTS_INPUT_CAN_MANAGE: False,
                    CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW: False,
                    CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION: False,
                },
            )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify user ID was set
        coordinator = config_entry.runtime_data
        parent_data = coordinator.parents_data.get(parent_id, {})
        assert parent_data.get(DATA_PARENT_HA_USER_ID) == test_ha_user.id

        # Step 5: Edit again to clear the HA user ID
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_USERS},
        )

        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_EDIT},
        )

        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_ENTITY_NAME: parent_name},
        )

        # Step 6: Submit with SENTINEL_NO_SELECTION (None option selected) - ALL required fields
        with patch(
            "custom_components.choreops.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            result = await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={
                    CFOF_PARENTS_INPUT_NAME: parent_name,
                    CFOF_PARENTS_INPUT_HA_USER: SENTINEL_NO_SELECTION,  # Clear the user ID
                    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: associated_kids,
                    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE: SENTINEL_NO_SELECTION,
                    CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: True,
                    CFOF_PARENTS_INPUT_CAN_APPROVE: False,
                    CFOF_PARENTS_INPUT_CAN_MANAGE: False,
                    CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW: False,
                    CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION: False,
                },
            )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Step 7: Verify user ID was cleared
        coordinator_after = config_entry.runtime_data
        parent_data_after = coordinator_after.parents_data.get(parent_id, {})
        ha_user_id_after = parent_data_after.get(DATA_PARENT_HA_USER_ID, "NOT_FOUND")

        assert ha_user_id_after == "", (
            f"Expected empty string, got '{ha_user_id_after}'"
        )
