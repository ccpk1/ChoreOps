"""Test HA User ID clearing functionality via options flow.

Validates that users can properly clear HA user links for kids and parents
through the options flow interface, following the established Stårblüm family patterns.
"""

from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from tests.helpers import (
    # Kid form constants
    CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE,
    CFOF_KIDS_INPUT_HA_USER,
    CFOF_KIDS_INPUT_KID_NAME,
    CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE,
    # Parent form constants
    CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT,
    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS,
    CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW,
    CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION,
    CFOF_PARENTS_INPUT_HA_USER,
    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE,
    CFOF_PARENTS_INPUT_NAME,
    # Common constants
    DATA_KID_HA_USER_ID,
    DATA_PARENT_HA_USER_ID,
    OPTIONS_FLOW_ACTIONS_EDIT,
    OPTIONS_FLOW_INPUT_ENTITY_NAME,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_KIDS,
    OPTIONS_FLOW_PARENTS,
    OPTIONS_FLOW_STEP_EDIT_KID,
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_STEP_MANAGE_ENTITY,
    OPTIONS_FLOW_STEP_SELECT_ENTITY,
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

    async def test_kid_ha_user_id_can_be_cleared(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that kid HA user ID can be set and then cleared through options flow."""
        config_entry = scenario_minimal.config_entry
        kid_name = "Zoë"
        kid_id = scenario_minimal.kid_ids[kid_name]

        # Step 1: Navigate to kids management (init -> select entity type)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY

        # Step 2: Select edit kid action (manage_entity -> select action)
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_EDIT},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_SELECT_ENTITY

        # Step 3: Select the kid to edit by name (select_entity -> choose kid)
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_ENTITY_NAME: kid_name},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_KID

        # Step 4: Set a HA user ID first - provide ALL required form fields
        # Use a real HA user ID from the mock_hass_users fixture
        test_ha_user = mock_hass_users["kid2"]  # Different user to avoid original
        with patch(
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            result = await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={
                    CFOF_KIDS_INPUT_KID_NAME: "Zoë",
                    CFOF_KIDS_INPUT_HA_USER: test_ha_user.id,  # Set a user ID
                    CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: "en",
                    CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE: SENTINEL_NO_SELECTION,
                },
            )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify user ID was set
        coordinator = config_entry.runtime_data
        kid_data = coordinator.kids_data.get(kid_id, {})
        assert kid_data.get(DATA_KID_HA_USER_ID) == test_ha_user.id

        # Step 5: Edit again to clear the HA user ID
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_KIDS},
        )

        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_EDIT},
        )

        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_ENTITY_NAME: kid_name},
        )

        # Step 6: Submit with SENTINEL_NO_SELECTION (None option selected) - ALL required fields
        with patch(
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            result = await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={
                    CFOF_KIDS_INPUT_KID_NAME: "Zoë",
                    CFOF_KIDS_INPUT_HA_USER: SENTINEL_NO_SELECTION,  # Clear the user ID
                    CFOF_KIDS_INPUT_DASHBOARD_LANGUAGE: "en",
                    CFOF_KIDS_INPUT_MOBILE_NOTIFY_SERVICE: SENTINEL_NO_SELECTION,
                },
            )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Step 7: Verify user ID was cleared
        coordinator_after = config_entry.runtime_data
        kid_data_after = coordinator_after.kids_data.get(kid_id, {})
        ha_user_id_after = kid_data_after.get(DATA_KID_HA_USER_ID, "NOT_FOUND")

        assert ha_user_id_after == "", (
            f"Expected empty string, got '{ha_user_id_after}'"
        )

    async def test_parent_ha_user_id_can_be_cleared(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that parent HA user ID can be set and then cleared through options flow."""
        config_entry = scenario_minimal.config_entry
        parent_name = "Môm Astrid Stârblüm"
        parent_id = scenario_minimal.parent_ids[parent_name]

        # Step 1: Navigate to parents management (init -> select entity type)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_PARENTS},
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
        with patch(
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            result = await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={
                    CFOF_PARENTS_INPUT_NAME: parent_name,
                    CFOF_PARENTS_INPUT_HA_USER: test_ha_user.id,  # Set a user ID
                    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: [],
                    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE: SENTINEL_NO_SELECTION,
                    CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: False,
                    CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW: False,
                    CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION: False,
                },
            )

        # Verify user ID was set
        coordinator = config_entry.runtime_data
        parent_data = coordinator.parents_data.get(parent_id, {})
        assert parent_data.get(DATA_PARENT_HA_USER_ID) == test_ha_user.id

        # Step 5: Edit again to clear the HA user ID
        result = await hass.config_entries.options.async_configure(
            result.get("flow_id"),
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_PARENTS},
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
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            result = await hass.config_entries.options.async_configure(
                result.get("flow_id"),
                user_input={
                    CFOF_PARENTS_INPUT_NAME: parent_name,
                    CFOF_PARENTS_INPUT_HA_USER: SENTINEL_NO_SELECTION,  # Clear the user ID
                    CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: [],
                    CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE: SENTINEL_NO_SELECTION,
                    CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT: False,
                    CFOF_PARENTS_INPUT_ENABLE_CHORE_WORKFLOW: False,
                    CFOF_PARENTS_INPUT_ENABLE_GAMIFICATION: False,
                },
            )

        # Step 7: Verify user ID was cleared
        coordinator_after = config_entry.runtime_data
        parent_data_after = coordinator_after.parents_data.get(parent_id, {})
        ha_user_id_after = parent_data_after.get(DATA_PARENT_HA_USER_ID, "NOT_FOUND")

        assert ha_user_id_after == "", (
            f"Expected empty string, got '{ha_user_id_after}'"
        )
