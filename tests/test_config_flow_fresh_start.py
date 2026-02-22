"""Test config flow fresh start scenarios with progressive complexity.

This module tests the ChoreOps config flow starting fresh (no backup data)
with incrementally complex scenarios:

- test_fresh_start_points_only: Just points setup
- test_fresh_start_points_and_assignee: Points + 1 assignee
- test_fresh_start_basic_family: Points + 2 assignees + 1 chore
- test_fresh_start_full_scenario: Complete scenario_full setup

Uses real Home Assistant config flow system for integration testing.
"""

# Accessing protected members for testing
# pylint: disable=redefined-outer-name  # Pytest fixtures redefine names

# pyright: reportTypedDictNotRequiredAccess=false

from typing import Any
from unittest.mock import patch
import uuid

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.choreops import const


@pytest.mark.asyncio
async def test_fresh_start_points_only(hass: HomeAssistant) -> None:
    """Test 1: Fresh config flow with just Star Points theme, no entities.

    This is the simplest possible config flow completion:
    1. Starts fresh config flow (no existing data)
    2. Sets points label to "Star Points" with star icon
    3. Sets all entity counts to 0
    4. Completes with CREATE_ENTRY
    5. Verifies config entry created with Star Points theme settings

    Foundation test for more complex scenarios.
    """

    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        # Step 1: Start fresh config flow
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_DATA_RECOVERY

        # Step 2: Choose "start fresh"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"backup_selection": "start_fresh"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_INTRO

        # Step 3: Pass intro step (empty form)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_POINTS

        # Step 4: Set Star Points theme
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USER_COUNT

        # Step 5-13: Set all entity counts to 0
        # Assignee count = 0 (skips approver_count, goes to chore_count)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Chore count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_CHORES_INPUT_CHORE_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT

        # Badge count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_REWARD_COUNT

        # Reward count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_REWARDS_INPUT_REWARD_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_PENALTY_COUNT

        # Penalty count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_PENALTIES_INPUT_PENALTY_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BONUS_COUNT

        # Bonus count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_BONUSES_INPUT_BONUS_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT

        # Achievement count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHALLENGE_COUNT

        # Challenge count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_FINISH

        # Final step: finish (empty form)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == const.CHOREOPS_TITLE

        # Verify config entry was created with Star Points settings
        config_entry = result["result"]
        assert config_entry.title == const.CHOREOPS_TITLE
        assert config_entry.domain == const.DOMAIN

        # Verify system settings in options (storage-only mode v0.5.0+)
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
        assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"
        assert config_entry.options[const.CONF_UPDATE_INTERVAL] == 5  # Default

        # Verify integration was set up
        entries = hass.config_entries.async_entries(const.DOMAIN)
        assert len(entries) == 1
        assert entries[0].entry_id == config_entry.entry_id


@pytest.mark.asyncio
async def test_fresh_start_points_and_assignee(
    hass: HomeAssistant, mock_hass_users
) -> None:
    """Test 2: Fresh config flow with Star Points + 1 assignee.

    Tests the config flow with Star Points theme plus creation of 1 assignee.
    All other entity counts remain at 0.
    """
    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        # Step 1: Start fresh config flow
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_DATA_RECOVERY

        # Step 2: Choose "start fresh"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"backup_selection": "start_fresh"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_INTRO

        # Step 3: Pass intro step (empty form)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_POINTS

        # Step 4: Configure Star Points theme
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USER_COUNT

        # Step 5: Set assignee count = 1
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 1},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Step 6: Configure the one assignee with HA user and notifications
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name="Zoë",
            assignee_ha_user_key="assignee1",
            dashboard_language="en",
            mobile_notify_service=const.SENTINEL_NO_SELECTION,  # No real notify services in test
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Step 8: Chore count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_CHORES_INPUT_CHORE_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT

        # Step 9: Badge count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_REWARD_COUNT

        # Step 10: Reward count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_REWARDS_INPUT_REWARD_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_PENALTY_COUNT

        # Step 11: Penalty count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_PENALTIES_INPUT_PENALTY_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BONUS_COUNT

        # Step 12: Bonus count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_BONUSES_INPUT_BONUS_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT

        # Step 13: Achievement count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHALLENGE_COUNT

        # Step 14: Challenge count = 0
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: 0},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_FINISH

        # Step 15: Final step - finish
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == const.CHOREOPS_TITLE

        # Verify config entry created correctly
        config_entry = result["result"]
        assert config_entry.title == const.CHOREOPS_TITLE
        assert config_entry.domain == const.DOMAIN

        # Verify Star Points theme in system settings
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
        assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"

        # Verify integration was set up and storage has properly configured assignee
        entries = hass.config_entries.async_entries(const.DOMAIN)
        assert len(entries) == 1

        # Since the integration setup is mocked, we can't check storage directly,
        # but we can verify the config entry was created with the proper title
        # In a real scenario, the assignee would be created with:
        # - Name: "Zoë"
        # - HA User ID: mock_hass_users["assignee1"].id
        # - Mobile notifications: enabled with "mobile_app_test_device"
        # - Persistent notifications: enabled
        # - Dashboard language: "en"
        assert entries[0].entry_id == config_entry.entry_id

        # Config entry created successfully - coordinator contains assignee data


@pytest.mark.asyncio
async def test_fresh_start_assignee_with_notify_services(
    hass: HomeAssistant, mock_hass_users
) -> None:
    """Test 2b: Fresh config flow with assignee configured with actual notify services.

    Tests the same scenario as test_fresh_start_points_and_assignee but with
    mock notify services available to test the mobile notification configuration.
    """

    # Set up mock notify services for the test
    async def async_register_notify_services():
        """Register mock notify services for testing."""
        hass.services.async_register(
            "notify", "mobile_app_test_phone", lambda call: None
        )
        hass.services.async_register("notify", "persistent", lambda call: None)

    await async_register_notify_services()

    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        # Step 1: Start fresh config flow
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_DATA_RECOVERY

        # Step 2: Choose "start fresh"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"backup_selection": "start_fresh"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_INTRO

        # Step 3: Pass intro step (empty form)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_POINTS

        # Step 4: Configure Star Points theme
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USER_COUNT

        # Step 5: Set assignee count = 1
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 1},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Step 6: Configure assignee with real mobile notify service
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name="Zoë",
            assignee_ha_user_key="assignee1",
            dashboard_language="en",
            mobile_notify_service="notify.mobile_app_test_phone",
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_CHORES_INPUT_CHORE_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_REWARD_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_REWARDS_INPUT_REWARD_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_PENALTY_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_PENALTIES_INPUT_PENALTY_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BONUS_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_BONUSES_INPUT_BONUS_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHALLENGE_COUNT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: 0},
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_FINISH

        # Final step: finish
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == const.CHOREOPS_TITLE

        # Verify config entry created correctly with Star Points
        config_entry = result["result"]
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
        assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"

        # Verify integration setup succeeded
        entries = hass.config_entries.async_entries(const.DOMAIN)
        assert len(entries) == 1

        # In a real scenario, the assignee would be configured with:
        # - Name: "Zoë"
        # - HA User ID: mock_hass_users["assignee1"].id
        # - Mobile notifications: enabled with "notify.mobile_app_test_phone"
        # - Persistent notifications: enabled
        # - Dashboard language: "en"


@pytest.mark.asyncio
async def test_fresh_start_with_approver_no_notifications(
    hass: HomeAssistant, mock_hass_users
) -> None:
    """Test 3a: Fresh config flow with 1 assignee + 1 approver (notifications disabled).

    Tests approver configuration with:
    - HA User ID assigned
    - Mobile and persistent notifications disabled
    - Associated with the assignee
    """
    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        # Steps 1-5: Same as other tests (fresh start, intro, points, assignee count=1, assignee config)
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "start_fresh"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 2}
        )
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name="Zoë",
            assignee_ha_user_key="assignee1",
            dashboard_language="en",
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Step 7: Configure approver with HA user but no notifications
        # Extract the assignee ID using the working pattern from test_fresh_start_with_approvers
        data_schema = _require_data_schema(result)
        associated_assignees_field = _find_field_in_schema(
            data_schema,
            const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES,
        )
        assert associated_assignees_field is not None, (
            "associated_assignees field not found in schema"
        )

        assignee_options = associated_assignees_field.config["options"]
        assert len(assignee_options) == 1, (
            f"Expected 1 assignee option, got {len(assignee_options)}"
        )

        assignee_id = assignee_options[0]["value"]  # Extract UUID from first option

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_APPROVERS_INPUT_NAME: "Môm Astrid Stârblüm",
                const.CFOF_APPROVERS_INPUT_HA_USER: mock_hass_users["approver1"].id,
                const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES: [
                    assignee_id
                ],  # Use the extracted assignee ID
                const.CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE: const.SENTINEL_NO_SELECTION,
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Steps 8-15: Set all other entity counts to 0 and finish
        for _, input_key, next_step in [
            (
                const.CONFIG_FLOW_STEP_CHORE_COUNT,
                const.CFOF_CHORES_INPUT_CHORE_COUNT,
                const.CONFIG_FLOW_STEP_BADGE_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_BADGE_COUNT,
                const.CFOF_BADGES_INPUT_BADGE_COUNT,
                const.CONFIG_FLOW_STEP_REWARD_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_REWARD_COUNT,
                const.CFOF_REWARDS_INPUT_REWARD_COUNT,
                const.CONFIG_FLOW_STEP_PENALTY_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_PENALTY_COUNT,
                const.CFOF_PENALTIES_INPUT_PENALTY_COUNT,
                const.CONFIG_FLOW_STEP_BONUS_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_BONUS_COUNT,
                const.CFOF_BONUSES_INPUT_BONUS_COUNT,
                const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
                const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT,
                const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
                const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT,
                const.CONFIG_FLOW_STEP_FINISH,
            ),
        ]:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={input_key: 0}
            )
            assert result["step_id"] == next_step

        # Final step: finish
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == const.CHOREOPS_TITLE
        config_entry = result["result"]
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"

        # Verify integration setup
        entries = hass.config_entries.async_entries(const.DOMAIN)
        assert len(entries) == 1


@pytest.mark.asyncio
async def test_fresh_start_with_approver_with_notifications(
    hass: HomeAssistant, mock_hass_users
) -> None:
    """Test 3b: Fresh config flow with 1 assignee + 1 approver (notifications enabled).

    Tests approver configuration with:
    - HA User ID assigned
    - Mobile and persistent notifications enabled
    - Mobile notify service configured
    - Associated with the assignee
    """
    # Set up mock notify services
    hass.services.async_register(
        "notify", "mobile_app_approver_phone", lambda call: None
    )
    hass.services.async_register("notify", "persistent", lambda call: None)

    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        # Steps 1-5: Same setup as previous test
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "start_fresh"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 2}
        )
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name="Max!",
            assignee_ha_user_key="assignee2",
            dashboard_language="en",
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Step 7: Configure approver with notifications enabled using helper
        assignee_ids = _extract_assignee_ids_from_schema(result)
        result = await _configure_approver_step(
            hass,
            result,
            mock_hass_users,
            associated_assignee_ids=assignee_ids,
            approver_name="Dad Leo",
            approver_ha_user_key="approver2",
            mobile_notify_service="notify.mobile_app_approver_phone",
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Skip all other entity steps using helper
        result = await _skip_all_entity_steps(hass, result)

        # Final step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        config_entry = result["result"]
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"

        # In a real scenario, the approver would be configured with:
        # - Name: "Approver Two"
        # - HA User ID: mock_hass_users["approver2"].id
        # - Mobile notifications: enabled with "notify.mobile_app_approver_phone"
        # - Persistent notifications: enabled
        # - Associated assignees: ["Sam"]


@pytest.mark.asyncio
async def test_fresh_start_two_approvers_mixed_notifications(
    hass: HomeAssistant, mock_hass_users
) -> None:
    """Test 3c: Fresh config flow with 1 assignee + 2 approvers (mixed notification settings).

    Tests complex approver configuration:
    - Approver 1: Notifications disabled, associated with assignee
    - Approver 2: Notifications enabled, associated with assignee
    - Both approvers have HA user IDs
    """
    # Set up mock notify services
    hass.services.async_register(
        "notify", "mobile_app_approver2_phone", lambda call: None
    )

    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        # Steps 1-5: Basic setup
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "start_fresh"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 3}
        )
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name="Lila",
            assignee_ha_user_key="assignee3",
            dashboard_language="en",
            mobile_notify_service=const.SENTINEL_NO_SELECTION,
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Step 7: Configure first approver (no notifications) using helper
        assignee_ids = _extract_assignee_ids_from_schema(result)
        result = await _configure_approver_step(
            hass,
            result,
            mock_hass_users,
            associated_assignee_ids=assignee_ids,
            approver_name="Môm Astrid Stârblüm",
            approver_ha_user_key="approver1",
        )
        assert result["type"] == FlowResultType.FORM
        assert (
            result["step_id"] == const.CONFIG_FLOW_STEP_USERS
        )  # Still on approvers step

        # Step 8: Configure second approver (with notifications) using helper
        assignee_ids = _extract_assignee_ids_from_schema(
            result
        )  # Re-extract for second approver
        result = await _configure_approver_step(
            hass,
            result,
            mock_hass_users,
            associated_assignee_ids=assignee_ids,
            approver_name="Dad Leo",
            approver_ha_user_key="approver2",
            mobile_notify_service="notify.mobile_app_approver2_phone",
        )
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Skip all other entity steps using helper
        result = await _skip_all_entity_steps(hass, result)

        # Final step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        config_entry = result["result"]
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
        assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"

        # In a real scenario:
        # Assignee "Lila" - HA user: assignee3, notifications: mobile disabled, persistent disabled
        # Approver "Môm Astrid Stârblüm" - HA user: approver1, notifications: all disabled, associated: ["Lila"]
        # Approver "Dad Leo" - HA user: approver2, mobile notifications enabled, associated: ["Lila"]


def _require_data_schema(result: Any) -> Any:
    """Return the data_schema ensuring it exists."""
    data_schema = result.get("data_schema")
    assert data_schema is not None
    return data_schema


def _find_field_in_schema(data_schema: Any, field_key: str) -> Any | None:
    """Find a schema field in flat or sectioned voluptuous schemas."""

    def _match_field(schema_map: Any, key: str) -> Any | None:
        for schema_key, schema_value in schema_map.items():
            normalized_key = getattr(schema_key, "schema", schema_key)
            if normalized_key == key:
                return schema_value
        return None

    field = _match_field(data_schema.schema, field_key)
    if field is not None:
        return field

    for section_obj in data_schema.schema.values():
        nested_schema = getattr(section_obj, "schema", None)
        nested_map = getattr(nested_schema, "schema", None)
        if nested_map is None:
            continue
        field = _match_field(nested_map, field_key)
        if field is not None:
            return field

    return None


async def _configure_assignee_step(
    hass: HomeAssistant,
    result: Any,
    mock_hass_users: dict[str, Any],
    *,
    assignee_name: str,
    assignee_ha_user_key: str,
    dashboard_language: str = "en",
    mobile_notify_service: str = const.SENTINEL_NO_SELECTION,
) -> Any:
    """Configure a single assignee in the config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result
        mock_hass_users: Mock users dictionary
        assignee_name: Name for the assignee (e.g., "Zoë", "Max!", "Lila")
        assignee_ha_user_key: Key in mock_hass_users (e.g., "assignee1", "assignee2", "assignee3")
        dashboard_language: Dashboard language code (default: "en")
        mobile_notify_service: Notify service (set to enable notifications)

    Returns:
        Updated config flow result after assignee configuration
    """
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_APPROVERS_INPUT_NAME: assignee_name,
            const.CFOF_APPROVERS_INPUT_HA_USER: mock_hass_users[
                assignee_ha_user_key
            ].id,
            const.CFOF_APPROVERS_INPUT_DASHBOARD_LANGUAGE: dashboard_language,
            const.CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE: mobile_notify_service,
            const.CFOF_APPROVERS_INPUT_ALLOW_CHORE_ASSIGNMENT: True,
            const.CFOF_APPROVERS_INPUT_ENABLE_CHORE_WORKFLOW: True,
            const.CFOF_APPROVERS_INPUT_ENABLE_GAMIFICATION: True,
            const.CFOF_APPROVERS_INPUT_CAN_APPROVE: False,
            const.CFOF_APPROVERS_INPUT_CAN_MANAGE: False,
            const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES: [],
        },
    )


async def _configure_approver_step(
    hass: HomeAssistant,
    result: Any,
    mock_hass_users: dict[str, Any],
    associated_assignee_ids: list[str],
    *,
    approver_name: str,
    approver_ha_user_key: str,
    mobile_notify_service: str = const.SENTINEL_NO_SELECTION,
) -> Any:
    """Configure a single approver in the config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result
        mock_hass_users: Mock users dictionary
        associated_assignee_ids: List of assignee internal IDs to associate with this approver
        approver_name: Name for the approver (e.g., "Môm Astrid Stârblüm", "Dad Leo")
        approver_ha_user_key: Key in mock_hass_users (e.g., "approver1", "approver2")
        mobile_notify_service: Notify service (set to enable notifications)

    Returns:
        Updated config flow result after approver configuration
    """
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_APPROVERS_INPUT_NAME: approver_name,
            const.CFOF_APPROVERS_INPUT_HA_USER: mock_hass_users[
                approver_ha_user_key
            ].id,
            const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES: associated_assignee_ids,
            const.CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE: mobile_notify_service,
        },
    )


# ----------------------------------------------------------------------------------
# ENHANCED REUSABLE HELPER FUNCTIONS FOR SCALABLE TEST SCENARIOS
# ----------------------------------------------------------------------------------


async def _configure_multiple_assignees_step(
    hass: HomeAssistant,
    result: Any,
    mock_hass_users: dict[str, Any],
    assignee_configs: list[dict[str, Any]],
) -> tuple[Any, dict[str, str]]:
    """Configure multiple assignees in sequence during config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result (should be on KIDS step)
        mock_hass_users: Mock users dictionary
        assignee_configs: List of assignee configuration dictionaries with keys:
            - name: Assignee name (e.g., "Zoë", "Max!", "Lila")
            - ha_user_name: Key in mock_hass_users (e.g., "assignee1", "assignee2", "assignee3")
            - dashboard_language: Dashboard language code (default: "en")
            - mobile_notify_service: Notify service name (set to enable notifications)

    Returns:
        Tuple of (final_result, name_to_id_map)
        - final_result: Updated config flow result after all assignees configured
        - name_to_id_map: Dict mapping assignee names to their internal UUIDs

    Example:
        result, assignee_ids = await _configure_multiple_assignees_step(
            hass, result, mock_hass_users,
            [
                {"name": "Zoë", "ha_user_name": "assignee1", "mobile_notify_service": "notify.mobile_app_zoe"},
                {"name": "Max!", "ha_user_name": "assignee2", "dashboard_language": "es"},
                {"name": "Lila", "ha_user_name": "assignee3"},
            ]
        )
    """
    name_to_id_map = {}

    for i, assignee_config in enumerate(assignee_configs):
        # Configure this assignee
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name=assignee_config["name"],
            assignee_ha_user_key=assignee_config["ha_user_name"],
            dashboard_language=assignee_config.get("dashboard_language", "en"),
            mobile_notify_service=assignee_config.get("mobile_notify_service", ""),
        )

        # Extract the assignee's internal ID from the config flow result
        if i < len(assignee_configs) - 1:
            # Still more users to configure - result should remain on USERS step
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

            # After each assignee is configured, the config flow advances to the next assignee
            # but we can't easily extract the ID here. Store name mapping for now.
            # The real IDs will be available when we reach the approver step.
            name_to_id_map[assignee_config["name"]] = None  # Placeholder
        else:
            # Last assignable user - result should remain on USERS step
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

            # Extract all real assignee IDs from approver step schema and map to names
            actual_assignee_ids = _extract_assignee_ids_from_schema(result)

            # Map assignee names to their actual IDs (in order they were configured)
            for j, assignee_config_item in enumerate(assignee_configs):
                if j < len(actual_assignee_ids):
                    name_to_id_map[assignee_config_item["name"]] = actual_assignee_ids[
                        j
                    ]

    return result, name_to_id_map


async def _configure_multiple_approvers_step(
    hass: HomeAssistant,
    result: Any,
    mock_hass_users: dict[str, Any],
    approver_configs: list[dict[str, Any]],
    assignee_name_to_id_map: dict[str, str],
) -> Any:
    """Configure multiple approvers in sequence during config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result (should be on PARENTS step)
        mock_hass_users: Mock users dictionary
        approver_configs: List of approver configuration dictionaries with keys:
            - name: Approver name (e.g., "Môm Astrid Stârblüm", "Dad Leo")
            - ha_user_name: Key in mock_hass_users (e.g., "approver1", "approver2")
            - associated_assignee_names: List of assignee names to associate (default: [])
            - mobile_notify_service: Notify service name (set to enable notifications)
        assignee_name_to_id_map: Map of assignee names to internal UUIDs from _configure_multiple_assignees_step

    Returns:
        Updated config flow result after all approvers configured

    Example:
        result = await _configure_multiple_approvers_step(
            hass, result, mock_hass_users,
            [
                {
                    "name": "Môm Astrid Stârblüm",
                    "ha_user_name": "approver1",
                    "associated_assignee_names": ["Zoë", "Lila"],
                    "mobile_notify_service": "notify.mobile_app_mom"
                },
                {
                    "name": "Dad Leo",
                    "ha_user_name": "approver2",
                    "associated_assignee_names": ["Max!", "Lila"],
                },
            ],
            assignee_ids
        )
    """
    for i, approver_config in enumerate(approver_configs):
        # Map associated assignee names to their internal IDs
        associated_assignee_names = approver_config.get("associated_assignee_names", [])
        associated_assignee_ids = [
            assignee_name_to_id_map[name]
            for name in associated_assignee_names
            if name in assignee_name_to_id_map
        ]

        # Configure this approver
        result = await _configure_approver_step(
            hass,
            result,
            mock_hass_users,
            associated_assignee_ids,
            approver_name=approver_config["name"],
            approver_ha_user_key=approver_config["ha_user_name"],
            mobile_notify_service=approver_config.get("mobile_notify_service", ""),
        )

        if i < len(approver_configs) - 1:
            # Still more approvers to configure
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS
        else:
            # Last approver - result should advance to chore count step
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

    return result


async def _setup_full_family_scenario(
    hass: HomeAssistant,
    result: Any,
    mock_hass_users: dict[str, Any],
    points_label: str = "Star Points",
    points_icon: str = "mdi:star",
) -> tuple[Any, dict[str, str]]:
    """Set up a complete family scenario matching scenario_full test data.

    Configures:
    - 3 assignees: Zoë, Max!, Lila (from testdata_scenario_full.yaml)
    - 2 approvers: Môm Astrid Stârblüm, Dad Leo (from testdata_scenario_full.yaml)
    - Realistic notification configurations
    - Mixed dashboard languages

    Args:
        hass: Home Assistant instance
        result: Current config flow result (should be on POINTS step)
        mock_hass_users: Mock users dictionary
        points_label: Points label for theme (default: "Star Points")
        points_icon: Points icon for theme (default: "mdi:star-circle")

    Returns:
        Tuple of (final_result, assignee_name_to_id_map)
        - final_result: Config flow result ready for entity configuration
        - assignee_name_to_id_map: Mapping of assignee names to internal UUIDs

    Example:
        result, assignee_ids = await _setup_full_family_scenario(hass, result, mock_hass_users)
        # Can now configure chores, rewards, etc. referencing assignee_ids["Zoë"], assignee_ids["Max!"], etc.
    """
    # Step 1: Configure points theme
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_SYSTEM_INPUT_POINTS_LABEL: points_label,
            const.CFOF_SYSTEM_INPUT_POINTS_ICON: points_icon,
        },
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_USER_COUNT

    # Step 2: Set total user count = 5 (3 assignable users + 2 approvers)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 5}
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

    # Step 3: Configure 3 assignees individually (proven working pattern)
    result = await _configure_assignee_step(
        hass,
        result,
        mock_hass_users,
        assignee_name="Zoë",
        assignee_ha_user_key="assignee1",
        dashboard_language="en",
    )
    result = await _configure_assignee_step(
        hass,
        result,
        mock_hass_users,
        assignee_name="Max!",
        assignee_ha_user_key="assignee2",
        dashboard_language="es",
    )
    result = await _configure_assignee_step(
        hass,
        result,
        mock_hass_users,
        assignee_name="Lila",
        assignee_ha_user_key="assignee3",
        dashboard_language="en",
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

    # Step 4: Extract assignee IDs from schema (proven working pattern)
    assignee_ids = _extract_assignee_ids_from_schema(result)

    # Configure first approver
    result = await _configure_approver_step(
        hass,
        result,
        mock_hass_users,
        associated_assignee_ids=[assignee_ids[0], assignee_ids[2]],  # Zoë, Lila
        approver_name="Môm Astrid Stârblüm",
        approver_ha_user_key="approver1",
    )

    # Configure second approver
    assignee_ids = _extract_assignee_ids_from_schema(
        result
    )  # Re-extract for second approver
    result = await _configure_approver_step(
        hass,
        result,
        mock_hass_users,
        associated_assignee_ids=[assignee_ids[1], assignee_ids[2]],  # Max!, Lila
        approver_name="Dad Leo",
        approver_ha_user_key="approver2",
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

    # Create name to ID mapping for return (assignee order: Zoë=0, Max!=1, Lila=2)
    assignee_name_to_id_map = {
        "Zoë": assignee_ids[0],
        "Max!": assignee_ids[1],
        "Lila": assignee_ids[2],
    }

    return result, assignee_name_to_id_map


# ----------------------------------------------------------------------------------
# EXISTING HELPER FUNCTIONS (keep for backward compatibility)
# ----------------------------------------------------------------------------------


async def _skip_all_entity_steps(hass: HomeAssistant, result: Any) -> Any:
    """Skip all entity configuration steps by setting counts to 0.

    Args:
        hass: Home Assistant instance
        result: Current config flow result

    Returns:
        Updated config flow result ready for finish step
    """
    for _, input_key, next_step in [
        (
            const.CONFIG_FLOW_STEP_CHORE_COUNT,
            const.CFOF_CHORES_INPUT_CHORE_COUNT,
            const.CONFIG_FLOW_STEP_BADGE_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_BADGE_COUNT,
            const.CFOF_BADGES_INPUT_BADGE_COUNT,
            const.CONFIG_FLOW_STEP_REWARD_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_REWARD_COUNT,
            const.CFOF_REWARDS_INPUT_REWARD_COUNT,
            const.CONFIG_FLOW_STEP_PENALTY_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_PENALTY_COUNT,
            const.CFOF_PENALTIES_INPUT_PENALTY_COUNT,
            const.CONFIG_FLOW_STEP_BONUS_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_BONUS_COUNT,
            const.CFOF_BONUSES_INPUT_BONUS_COUNT,
            const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
            const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT,
            const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
            const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT,
            const.CONFIG_FLOW_STEP_FINISH,
        ),
    ]:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={input_key: 0}
        )
        assert result["step_id"] == next_step

    return result


def _extract_assignee_ids_from_schema(result: Any) -> list[str]:
    """Extract assignee IDs from the config flow result schema.

    Args:
        result: Config flow result containing data schema

    Returns:
        List of assignee internal IDs available in the form
    """
    data_schema = _require_data_schema(result)
    associated_assignees_field = _find_field_in_schema(
        data_schema,
        const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES,
    )
    assert associated_assignees_field is not None, (
        "associated_assignees field not found in schema"
    )

    assignee_options = associated_assignees_field.config["options"]
    return [option["value"] for option in assignee_options]


@pytest.mark.asyncio
async def test_fresh_start_with_approvers(hass: HomeAssistant, mock_hass_users):
    """Test 5: Fresh start config flow through approvers step.

    Tests creating 1 assignee then 1 approver associated with that assignee.
    This test captures the assignee UUID properly from config flow state.
    """
    # Set up mock notify services for the test
    hass.services.async_register("notify", "mobile_app_jane_phone", lambda call: None)
    hass.services.async_register("notify", "persistent", lambda call: None)

    # Create approver user in mock system
    approver_user = mock_hass_users["approver1"]

    # Mock setup to prevent actual integration loading during config flow
    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            const.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_DATA_RECOVERY

        # Skip data recovery
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"backup_selection": "start_fresh"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_INTRO

        # Skip intro
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_POINTS

        # Configure points system
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Star Points",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USER_COUNT

        # Configure total users (1 assignable + 1 approver)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={const.CFOF_APPROVERS_INPUT_APPROVER_COUNT: 2}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Create a assignee first
        result = await _configure_assignee_step(
            hass,
            result,
            mock_hass_users,
            assignee_name="Alex",
            assignee_ha_user_key="assignee1",
            dashboard_language="en",
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == const.CONFIG_FLOW_STEP_USERS

        # Extract the assignee ID from the approver form schema options for associated_assignees field
        data_schema = _require_data_schema(result)

        # Find the associated_assignees field schema in flat or sectioned form payloads
        associated_assignees_field = _find_field_in_schema(
            data_schema,
            const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES,
        )
        assert associated_assignees_field is not None, (
            "associated_assignees field not found in schema"
        )

        # Extract the available assignee options - these are dicts with "value" and "label"
        assignee_options = associated_assignees_field.config[
            "options"
        ]  # SelectSelector options
        assert len(assignee_options) == 1, (
            f"Expected 1 assignee option, got {len(assignee_options)}"
        )

        # Get the assignee ID from the first (and only) option
        assignee_id = assignee_options[0][
            "value"
        ]  # Extract value from {"value": assignee_id, "label": assignee_name}

        # Now configure the approver associated with this assignee
        approver_input = {
            const.CFOF_APPROVERS_INPUT_NAME: "Jane Approver",
            const.CFOF_APPROVERS_INPUT_HA_USER: approver_user.id,
            const.CFOF_APPROVERS_INPUT_ASSOCIATED_ASSIGNEES: [
                assignee_id
            ],  # Use the captured assignee ID
            const.CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE: "notify.mobile_app_jane_phone",  # Include notify. prefix
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=approver_input
        )
        assert result["type"] == FlowResultType.FORM
        # Should move to entities setup - let's see what the next step is
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Skip all remaining entity steps
        for _, input_key, next_step in [
            (
                const.CONFIG_FLOW_STEP_CHORE_COUNT,
                const.CFOF_CHORES_INPUT_CHORE_COUNT,
                const.CONFIG_FLOW_STEP_BADGE_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_BADGE_COUNT,
                const.CFOF_BADGES_INPUT_BADGE_COUNT,
                const.CONFIG_FLOW_STEP_REWARD_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_REWARD_COUNT,
                const.CFOF_REWARDS_INPUT_REWARD_COUNT,
                const.CONFIG_FLOW_STEP_PENALTY_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_PENALTY_COUNT,
                const.CFOF_PENALTIES_INPUT_PENALTY_COUNT,
                const.CONFIG_FLOW_STEP_BONUS_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_BONUS_COUNT,
                const.CFOF_BONUSES_INPUT_BONUS_COUNT,
                const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
                const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT,
                const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
            ),
            (
                const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
                const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT,
                const.CONFIG_FLOW_STEP_FINISH,
            ),
        ]:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={input_key: 0}
            )
            assert result["step_id"] == next_step

        # Final step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # Verify completion
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == const.CHOREOPS_TITLE

        # Verify config entry created correctly
        config_entry = result["result"]
        assert config_entry.title == const.CHOREOPS_TITLE
        assert config_entry.domain == const.DOMAIN

        # Verify Star Points theme in system settings
        assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
        assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"

        # Config entry created successfully - coordinator contains family data


# ==============================================================================
# CHORE CONFIGURATION HELPERS
# ==============================================================================


async def _configure_chore_step(
    hass: HomeAssistant,
    result: Any,
    chore_name: str,
    assigned_assignee_names: list[str],
    points: float = 10.0,
    description: str = "",
    icon: str = "mdi:check",
    completion_criteria: str = "independent",
    recurring_frequency: str = "daily",
    auto_approve: bool = False,
    show_on_calendar: bool = True,
    labels: list[str] | None = None,
    applicable_days: list[str] | None = None,
    notifications: list[str] | None = None,
    due_date: str | None = None,
    custom_interval: int | None = None,
    custom_interval_unit: str | None = None,
    approval_reset_type: str = const.DEFAULT_APPROVAL_RESET_TYPE,
    approval_reset_pending_claim_action: str = const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    overdue_handling_type: str = const.DEFAULT_OVERDUE_HANDLING_TYPE,
) -> Any:
    """Configure a single chore step during config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result (should be on CHORES step)
        chore_name: Name of the chore (e.g., "Feed the cåts", "Wåter the plånts")
        assigned_assignee_names: List of assignee names to assign chore to (e.g., ["Zoë", "Max!"])
        points: Points awarded for completion (default: 10.0)
        description: Optional chore description (default: "")
        icon: MDI icon (default: "mdi:check")
        completion_criteria: "independent", "shared_all", or "shared_first" (default: "independent")
        recurring_frequency: "daily", "weekly", "monthly", "custom", or "none" (default: "daily")
        auto_approve: Whether to auto-approve chore (default: False)
        show_on_calendar: Whether to show on calendar (default: True)
        labels: Optional list of labels (default: None)
        applicable_days: Optional list of weekday codes (default: None)
        notifications: Optional list of notification events (default: None)
        due_date: Optional due date as ISO string (default: None)
        custom_interval: Custom interval number (for custom frequency)
        custom_interval_unit: "days", "weeks", "months" (for custom frequency)
        approval_reset_type: "automatic", "manual", "never" (default: "automatic")
        approval_reset_pending_claim_action: Action for pending claims (default: "complete_with_pending_claim")
        overdue_handling_type: "none", "reset_to_pending", "auto_disapprove" (default: "none")

    Returns:
        Updated config flow result after chore configured

    Note:
        Based on chore form fields from flow_helpers.py build_chore_schema().
        YAML mapping: type → recurring_frequency, assigned_to → assigned_assignee_names
    """
    # Prepare notifications list (empty by default)
    chore_notifications = notifications or []

    # Prepare applicable days (all days by default for daily chores)
    if applicable_days is None:
        if recurring_frequency == "daily":
            applicable_days = [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
                "sat",
                "sun",
            ]  # All weekdays
        else:
            applicable_days = ["mon"]  # Monday for weekly/monthly

    # Configure this chore
    user_input = {
        const.CFOF_CHORES_INPUT_NAME: chore_name,
        const.CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assigned_assignee_names,
        const.CFOF_CHORES_INPUT_DEFAULT_POINTS: points,
        const.CFOF_CHORES_INPUT_DESCRIPTION: description,
        const.CFOF_CHORES_INPUT_ICON: icon,
        const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: completion_criteria,
        const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: recurring_frequency,
        const.CFOF_CHORES_INPUT_AUTO_APPROVE: auto_approve,
        const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: show_on_calendar,
        const.CFOF_CHORES_INPUT_LABELS: labels or [],
        const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: applicable_days,
        const.CFOF_CHORES_INPUT_NOTIFICATIONS: chore_notifications,
        const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: approval_reset_type,
        const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: approval_reset_pending_claim_action,
        const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: overdue_handling_type,
    }

    # Add optional fields if provided
    if due_date is not None:
        user_input[const.CFOF_CHORES_INPUT_DUE_DATE] = due_date
    if custom_interval is not None:
        user_input[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL] = custom_interval
    if custom_interval_unit is not None:
        user_input[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT] = custom_interval_unit

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )


async def _configure_system_settings_step(
    hass: HomeAssistant,
    result: Any,
    points_label: str = "Points",
    points_icon: str = "mdi:star-outline",
) -> Any:
    """Configure system settings (points theme) step in config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result (should be on POINTS step)
        points_label: Label for points (default: "Points")
        points_icon: Icon for points (default: "mdi:star-outline")

    Returns:
        Updated config flow result at USER_COUNT step
    """
    assert result["step_id"] == const.CONFIG_FLOW_STEP_POINTS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_SYSTEM_INPUT_POINTS_LABEL: points_label,
            const.CFOF_SYSTEM_INPUT_POINTS_ICON: points_icon,
        },
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_USER_COUNT
    return result


async def _configure_family_step(
    hass: HomeAssistant,
    mock_hass_users,
    assignee_names: list[str],
    approver_name: str = "Môm Astrid Stârblüm",
) -> tuple[Any, dict[str, str]]:
    """Configure family (assignees + approver) during config flow.

    Args:
        hass: Home Assistant instance
        mock_hass_users: Mock user dictionary from fixture
        assignee_names: List of assignee names to create (e.g., ["Zoë", "Max!", "Lila"])
        approver_name: Approver name (default: "Môm Astrid Stârblüm")

    Returns:
        Tuple of (config_flow_result, name_to_id_map)
        - config_flow_result: Result at end ready for next step
        - name_to_id_map: Mapping of assignee names to their UUIDs
    """
    # Start config flow
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == const.CONFIG_FLOW_STEP_DATA_RECOVERY

    # Skip data recovery (fresh start)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"backup_selection": "start_fresh"}
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_INTRO

    # Skip intro
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_POINTS

    # Configure system settings
    result = await _configure_system_settings_step(
        hass,
        result,
        points_label="Star Points",  # Use Star theme by default
        points_icon="mdi:star",
    )

    # Configure multiple assignees
    assignee_configs = [
        {"name": assignee_name, "ha_user_name": f"assignee{i + 1}"}
        for i, assignee_name in enumerate(assignee_names)
    ]
    result, assignee_name_to_id_map = await _configure_multiple_assignees_step(
        hass, result, mock_hass_users, assignee_configs
    )

    # Configure single approver linked to all assignees
    assignee_ids = [
        assignee_name_to_id_map[f"assignee:{name}"] for name in assignee_names
    ]
    result = await _configure_approver_step(
        hass,
        result,
        mock_hass_users,
        associated_assignee_ids=assignee_ids,
        approver_name=approver_name,
        approver_ha_user_key="approver1",
        mobile_notify_service=const.SENTINEL_EMPTY,
    )

    # Should be at chore count step
    assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

    return result, assignee_name_to_id_map


async def _configure_multiple_chores_step(
    hass: HomeAssistant,
    result: Any,
    chore_configs: list[dict[str, Any]],
) -> tuple[Any, dict[str, str]]:
    """Configure multiple chores in sequence during config flow.

    Args:
        hass: Home Assistant instance
        result: Current config flow result (should be on CHORE_COUNT step)
        chore_configs: List of chore configuration dictionaries with keys:
            - name: Chore name (e.g., "Feed the cåts", "Wåter the plånts")
            - assigned_assignee_names: List of assignee names (e.g., ["Zoë"], ["Max!", "Lila"])
            - points: Points value (default: 10.0)
            - type: YAML type field ("daily", "weekly", "monthly", "custom")
            - icon: MDI icon (default: "mdi:check")
            - completion_criteria: "independent", "shared_all", "shared_first" (default: "independent")
            - auto_approve: Whether to auto-approve (default: False)
            - custom_interval_days: For custom frequency (maps to custom_interval)
            - All other optional fields from _configure_chore_step()

    Returns:
        Tuple of (final_result, name_to_id_map)
        - final_result: Updated config flow result after all chores configured
        - name_to_id_map: Dict mapping chore names to their internal UUIDs

    Example:
        result, chore_ids = await _configure_multiple_chores_step(
            hass, result,
            [
                {
                    "name": "Feed the cåts",
                    "assigned_assignee_names": ["Zoë"],
                    "type": "daily",
                    "points": 10,
                    "icon": "mdi:cat",
                    "completion_criteria": "independent"
                },
                {
                    "name": "Stär sweep",
                    "assigned_assignee_names": ["Zoë", "Max!", "Lila"],
                    "type": "daily",
                    "points": 20,
                    "icon": "mdi:star",
                    "completion_criteria": "independent"
                },
            ]
        )

    Note:
        Maps YAML structure to config flow format:
        - type → recurring_frequency
        - assigned_to → assigned_assignee_names
        - custom_interval_days → custom_interval + custom_interval_unit="days"
    """
    name_to_id_map = {}

    # Set chore count
    chore_count = len(chore_configs)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_CHORES_INPUT_CHORE_COUNT: chore_count}
    )

    if chore_count == 0:
        # Skip to badge count step
        assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT
        return result, name_to_id_map

    # Configure each chore
    for i, chore_config in enumerate(chore_configs):
        assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORES

        # Map YAML fields to config flow parameters
        chore_type = chore_config.get("type", "daily")
        recurring_frequency = chore_type if chore_type != "custom" else "custom"

        # Handle custom interval days
        custom_interval = None
        custom_interval_unit = None
        if "custom_interval_days" in chore_config:
            custom_interval = chore_config["custom_interval_days"]
            custom_interval_unit = "days"

        # Configure this chore
        result = await _configure_chore_step(
            hass,
            result,
            chore_name=chore_config["name"],
            assigned_assignee_names=chore_config["assigned_assignee_names"],
            points=chore_config.get("points", 10.0),
            description=chore_config.get("description", ""),
            icon=chore_config.get("icon", "mdi:check"),
            completion_criteria=chore_config.get("completion_criteria", "independent"),
            recurring_frequency=recurring_frequency,
            auto_approve=chore_config.get("auto_approve", False),
            show_on_calendar=chore_config.get("show_on_calendar", True),
            labels=chore_config.get("labels"),
            applicable_days=chore_config.get("applicable_days"),
            notifications=chore_config.get("notifications"),
            due_date=chore_config.get("due_date"),
            custom_interval=custom_interval,
            custom_interval_unit=custom_interval_unit,
            approval_reset_type=chore_config.get(
                "approval_reset_type", const.DEFAULT_APPROVAL_RESET_TYPE
            ),
            approval_reset_pending_claim_action=chore_config.get(
                "approval_reset_pending_claim_action",
                const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            ),
            overdue_handling_type=chore_config.get(
                "overdue_handling_type", const.DEFAULT_OVERDUE_HANDLING_TYPE
            ),
        )

        # Generate UUID for this chore (simulating what config flow does)
        chore_id = str(uuid.uuid4())
        name_to_id_map[f"chore:{chore_config['name']}"] = chore_id

        if i < len(chore_configs) - 1:
            # Still more chores to configure
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORES
        else:
            # Last chore - should go to badge count
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT

    return result, name_to_id_map


# Future test ideas:
# - test_fresh_start_badges_and_rewards: Focus on badge/reward system
# - test_fresh_start_challenges_and_achievements: Focus on advanced features
# - test_fresh_start_error_handling: Test validation and error paths
# - test_fresh_start_different_themes: Test various points labels/icons


async def test_fresh_start_with_single_chore(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> None:
    """Test fresh start config flow with family + single chore from testdata_scenario_full.yaml.

    This test validates:
    1. Complete family setup (assignees + approvers)
    2. Single chore configuration using helper functions
    3. YAML compatibility (chore matches "Feed the cåts" from scenario_full.yaml)
    4. Proper field mapping (type → recurring_frequency, assigned_to → assigned_assignee_names)
    """
    # Step 1: Start config flow and navigate to points step
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"backup_selection": "start_fresh"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},  # Skip intro
    )

    # Step 2: Setup family from scenario_full.yaml with Star Points theme
    result, _ = await _setup_full_family_scenario(
        hass,
        result,
        mock_hass_users,
        points_label="Star Points",
        points_icon="mdi:star",
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

    # Step 3: Configure single chore "Feed the cåts" (matches first chore in scenario_full.yaml)
    result, chore_name_to_id_map = await _configure_multiple_chores_step(
        hass,
        result,
        [
            {
                "name": "Feed the cåts",
                "assigned_assignee_names": [
                    "Zoë"
                ],  # Matches assigned_to: ["Zoë"] in YAML
                "type": "daily",  # Maps to recurring_frequency: "daily"
                "points": 10,
                "icon": "mdi:cat",
                "completion_criteria": "independent",
                "auto_approve": False,  # Default in YAML
            }
        ],
    )

    # Should proceed to badge count step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT

    # Verify chore was mapped correctly
    assert "chore:Feed the cåts" in chore_name_to_id_map
    chore_id = chore_name_to_id_map["chore:Feed the cåts"]
    assert len(chore_id) == 36  # UUID length (8-4-4-4-12 format with hyphens)

    # Complete remaining steps with 0 counts to finish config flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_REWARDS_INPUT_REWARD_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_PENALTIES_INPUT_PENALTY_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_BONUSES_INPUT_BONUS_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: 0},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},  # Final finish step
    )

    # Should complete successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == const.CHOREOPS_TITLE

    # Verify the config entry was created
    config_entry = result["result"]
    assert config_entry.domain == const.DOMAIN
    assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
    assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"


async def test_fresh_start_with_all_scenario_chores(
    hass: HomeAssistant, mock_hass_users
) -> None:
    """Test fresh start config flow with all 18 chores from scenario_full.yaml."""
    # TEMP: Use simpler approach until family step is fixed
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"backup_selection": "start_fresh"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Use existing helper to setup the full family (3 assignees + 1 approver)
    result, _ = await _setup_full_family_scenario(
        hass,
        result,
        mock_hass_users,
        points_label="Star Points",
        points_icon="mdi:star",
    )
    assert result["step_id"] == const.CONFIG_FLOW_STEP_CHORE_COUNT

    # Configure all 18 chores from scenario_full.yaml
    all_scenario_chores = [
        # === INDEPENDENT CHORES (Single Assignee) ===
        {
            "name": "Feed the cåts",
            "assigned_assignee_names": ["Zoë"],
            "type": "daily",
            "points": 10,
            "icon": "mdi:cat",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        {
            "name": "Wåter the plänts",
            "assigned_assignee_names": ["Zoë"],
            "type": "daily",
            "points": 8,
            "icon": "mdi:watering-can",
            "completion_criteria": "independent",
            "auto_approve": True,
        },
        {
            "name": "Pick up Lëgo!",
            "assigned_assignee_names": ["Max!"],
            "type": "weekly",
            "points": 15,
            "icon": "mdi:lego",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        {
            "name": "Charge Røbot",
            "assigned_assignee_names": ["Max!"],
            "type": "daily",
            "points": 10,
            "icon": "mdi:robot",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        {
            "name": "Paint the rãinbow",
            "assigned_assignee_names": ["Lila"],
            "type": "weekly",
            "points": 15,
            "icon": "mdi:palette",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        {
            "name": "Sweep the p@tio",
            "assigned_assignee_names": ["Lila"],
            "type": "daily",
            "points": 10,
            "icon": "mdi:broom",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        # === INDEPENDENT CHORES (Multi Assignee) ===
        {
            "name": "Stär sweep",
            "assigned_assignee_names": ["Zoë", "Max!", "Lila"],
            "type": "daily",
            "points": 20,
            "icon": "mdi:star",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        {
            "name": "Ørgänize Bookshelf",
            "assigned_assignee_names": ["Zoë", "Lila"],
            "type": "weekly",
            "points": 18,
            "icon": "mdi:bookshelf",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        {
            "name": "Deep Clean Tøy Chest",
            "assigned_assignee_names": ["Max!"],
            "type": "monthly",
            "points": 30,
            "icon": "mdi:treasure-chest",
            "completion_criteria": "independent",
            "auto_approve": False,
        },
        # === SHARED_ALL CHORES ===
        {
            "name": "Family Dinner Prep",
            "assigned_assignee_names": ["Zoë", "Max!", "Lila"],
            "type": "daily",
            "points": 15,
            "icon": "mdi:food",
            "completion_criteria": "shared_all",
            "auto_approve": False,
        },
        {
            "name": "Weekend Yärd Work",
            "assigned_assignee_names": ["Zoë", "Max!", "Lila"],
            "type": "weekly",
            "points": 25,
            "icon": "mdi:tree",
            "completion_criteria": "shared_all",
            "auto_approve": False,
        },
        {
            "name": "Sibling Rööm Cleanup",
            "assigned_assignee_names": ["Max!", "Lila"],
            "type": "weekly",
            "points": 20,
            "icon": "mdi:broom-clean",
            "completion_criteria": "shared_all",
            "auto_approve": False,
        },
        # === SHARED_FIRST CHORES ===
        {
            "name": "Garage Cleanup",
            "assigned_assignee_names": ["Zoë", "Max!"],
            "type": "weekly",
            "points": 25,
            "icon": "mdi:garage",
            "completion_criteria": "shared_first",
            "auto_approve": False,
        },
        {
            "name": "Täke Öut Trash",
            "assigned_assignee_names": ["Zoë", "Max!", "Lila"],
            "type": "daily",
            "points": 12,
            "icon": "mdi:delete",
            "completion_criteria": "shared_first",
            "auto_approve": False,
        },
        {
            "name": "Wåsh Family Car",
            "assigned_assignee_names": ["Zoë", "Lila"],
            "type": "weekly",
            "points": 30,
            "icon": "mdi:car-wash",
            "completion_criteria": "shared_first",
            "auto_approve": False,
        },
        {
            "name": "Måil Pickup Race",
            "assigned_assignee_names": ["Zoë", "Max!", "Lila"],
            "type": "daily",
            "points": 8,
            "icon": "mdi:mailbox",
            "completion_criteria": "shared_first",
            "auto_approve": False,
        },
        # === CUSTOM FREQUENCY CHORES ===
        {
            "name": "Refill Bird Fëeder",
            "assigned_assignee_names": ["Zoë"],
            "type": "custom",
            "points": 8,
            "icon": "mdi:bird",
            "completion_criteria": "independent",
            "auto_approve": False,
            "custom_interval_days": 3,
        },
        {
            "name": "Clëan Pool Fïlter",
            "assigned_assignee_names": ["Max!", "Lila"],
            "type": "custom",
            "points": 22,
            "icon": "mdi:pool",
            "completion_criteria": "shared_first",
            "auto_approve": False,
            "custom_interval_days": 5,
        },
    ]

    result, chore_name_to_id_map = await _configure_multiple_chores_step(
        hass, result, all_scenario_chores
    )

    # Should proceed to badge count step
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == const.CONFIG_FLOW_STEP_BADGE_COUNT

    # Verify all 18 chores were mapped correctly
    assert len(chore_name_to_id_map) == 18  # Just the 18 chores

    # Verify specific chore mappings exist
    expected_chore_names = [
        "Feed the cåts",
        "Wåter the plänts",
        "Pick up Lëgo!",
        "Charge Røbot",
        "Paint the rãinbow",
        "Sweep the p@tio",
        "Stär sweep",
        "Ørgänize Bookshelf",
        "Deep Clean Tøy Chest",
        "Family Dinner Prep",
        "Weekend Yärd Work",
        "Sibling Rööm Cleanup",
        "Garage Cleanup",
        "Täke Öut Trash",
        "Wåsh Family Car",
        "Måil Pickup Race",
        "Refill Bird Fëeder",
        "Clëan Pool Fïlter",
    ]

    for chore_name in expected_chore_names:
        chore_key = f"chore:{chore_name}"
        assert chore_key in chore_name_to_id_map, (
            f"Missing chore mapping for {chore_name}"
        )
        chore_id = chore_name_to_id_map[chore_key]
        assert len(chore_id) == 36  # UUID length

    # Complete remaining steps with 0 counts to finish config flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_REWARDS_INPUT_REWARD_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_PENALTIES_INPUT_PENALTY_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_BONUSES_INPUT_BONUS_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: 0},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: 0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},  # Final finish step
    )

    # Should complete successfully
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == const.CHOREOPS_TITLE

    # Verify the config entry was created with correct settings
    config_entry = result["result"]
    assert config_entry.domain == const.DOMAIN
    assert config_entry.options[const.CONF_POINTS_LABEL] == "Star Points"
    assert config_entry.options[const.CONF_POINTS_ICON] == "mdi:star"
