"""Modern tests for options flow entity CRUD operations.

Uses shared FlowTestHelper for YAML scenario → form data conversion.
Replaces legacy test_options_flow*.py tests with focused, reusable patterns.
"""

# pyright: reportTypedDictNotRequiredAccess=false

import datetime
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.choreops.helpers.flow_helpers import (
    CHORE_SECTION_ADVANCED_CONFIGURATIONS,
    CHORE_SECTION_ROOT_FORM,
    CHORE_SECTION_SCHEDULE,
)
from tests.helpers import (
    APPROVAL_RESET_AT_DUE_DATE_ONCE,
    APPROVAL_RESET_AT_MIDNIGHT_ONCE,
    APPROVAL_RESET_UPON_COMPLETION,
    BADGE_TYPE_CUMULATIVE,
    CFOF_BADGES_INPUT_ASSIGNED_TO,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TYPE,
    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
    CFOF_CHORES_INPUT_ASSIGNED_KIDS,
    CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
    CFOF_CHORES_INPUT_DEFAULT_POINTS,
    CFOF_CHORES_INPUT_DESCRIPTION,
    CFOF_CHORES_INPUT_DUE_DATE,
    CFOF_CHORES_INPUT_ICON,
    CFOF_CHORES_INPUT_NAME,
    CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
    CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_ROTATION_SIMPLE,
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    CONF_UPDATE_INTERVAL,
    DATA_KID_NAME,
    DOMAIN,
    FREQUENCY_DAILY,
    FREQUENCY_DAILY_MULTI,
    OPTIONS_FLOW_ACHIEVEMENTS,
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_ACTIONS_BACK,
    OPTIONS_FLOW_BADGES,
    OPTIONS_FLOW_BONUSES,
    OPTIONS_FLOW_CHALLENGES,
    OPTIONS_FLOW_CHORES,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_PENALTIES,
    OPTIONS_FLOW_REWARDS,
    OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT,
    OPTIONS_FLOW_STEP_ADD_BONUS,
    OPTIONS_FLOW_STEP_ADD_CHALLENGE,
    OPTIONS_FLOW_STEP_ADD_CHORE,
    OPTIONS_FLOW_STEP_ADD_PENALTY,
    OPTIONS_FLOW_STEP_ADD_REWARD,
    OPTIONS_FLOW_STEP_ADD_USER,
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_STEP_MANAGE_ENTITY,
    OPTIONS_FLOW_USERS,
    OVERDUE_HANDLING_AT_DUE_DATE,
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
    SCHEMA_VERSION_STORAGE_ONLY,
)
from tests.helpers.flow_test_helpers import FlowTestHelper
from tests.helpers.setup import SetupResult

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
) -> MockConfigEntry:
    """Initialize integration with minimal config for options flow testing.

    Uses patched async_setup_entry - suitable for navigation tests only.
    For tests that need coordinator, use init_integration_with_coordinator.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="KidsChores",
        data={"schema_version": SCHEMA_VERSION_STORAGE_ONLY},
        options={
            CONF_POINTS_LABEL: "Points",
            CONF_POINTS_ICON: "mdi:star",
            CONF_UPDATE_INTERVAL: 5,
        },
        entry_id="test_entry_id",
        unique_id="test_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.choreops.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture
async def init_integration_with_coordinator(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Initialize integration with a real coordinator for entity CRUD tests.

    Uses a minimal scenario with 1 kid and 1 parent so coordinator is properly
    initialized. Tests can then add more entities via options flow.
    """
    from tests.helpers.setup import setup_from_yaml

    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# =========================================================================
# Options Flow Navigation Tests
# =========================================================================


async def test_options_flow_init_shows_menu(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test options flow initializes with main menu."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT


async def test_options_flow_navigate_to_kids_menu(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test navigating to users management menu."""
    result = await FlowTestHelper.navigate_to_entity_menu(
        hass, init_integration.entry_id, OPTIONS_FLOW_USERS
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY


async def test_options_flow_navigate_to_chores_menu(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test navigating to chores management menu."""
    result = await FlowTestHelper.navigate_to_entity_menu(
        hass, init_integration.entry_id, OPTIONS_FLOW_CHORES
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY


async def test_options_flow_navigate_to_rewards_menu(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test navigating to rewards management menu."""
    result = await FlowTestHelper.navigate_to_entity_menu(
        hass, init_integration.entry_id, OPTIONS_FLOW_REWARDS
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY


async def test_options_flow_back_to_menu(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test back navigation returns to main menu."""
    # Navigate to users menu
    result = await FlowTestHelper.navigate_to_entity_menu(
        hass, init_integration.entry_id, OPTIONS_FLOW_USERS
    )

    # Go back
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_BACK},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT


# =========================================================================
# Entity Add Tests (using FlowTestHelper converters)
# =========================================================================


async def test_add_kid_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a user via options flow using YAML-style data."""
    config_entry = init_integration_with_coordinator.config_entry

    yaml_parent = {
        "name": "Test User",
        "icon": "mdi:account-tie",
        "ha_user_name": "",
        "dashboard_language": "en",
        "allow_chore_assignment": True,
    }

    form_data = FlowTestHelper.build_parent_form_data(yaml_parent)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_USERS,
        OPTIONS_FLOW_STEP_ADD_USER,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify user was created via coordinator
    coordinator = init_integration_with_coordinator.coordinator
    parent_names = [p["name"] for p in coordinator.parents_data.values()]
    assert "Test User" in parent_names


async def test_add_parent_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a parent via options flow."""
    config_entry = init_integration_with_coordinator.config_entry

    yaml_parent = {
        "name": "Test Parent",
        "icon": "mdi:account-tie",
        "ha_user_name": "",
        "enable_notifications": False,
        "allow_chore_assignment": True,
    }

    form_data = FlowTestHelper.build_parent_form_data(yaml_parent)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_USERS,
        OPTIONS_FLOW_STEP_ADD_USER,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify parent was created via coordinator
    coordinator = init_integration_with_coordinator.coordinator
    parent_names = [p["name"] for p in coordinator.parents_data.values()]
    assert "Test Parent" in parent_names


async def test_add_chore_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a chore via options flow."""
    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    # Use an existing kid from the scenario
    existing_kid_names = [k["name"] for k in coordinator.kids_data.values()]
    assert len(existing_kid_names) > 0, "Scenario should have at least one kid"
    kid_name = existing_kid_names[0]  # Use first kid from scenario

    # Now add a chore assigned to existing kid
    yaml_chore = {
        "name": "Test Chore",
        "points": 15,
        "icon": "mdi:broom",
        "type": "daily",
        "assigned_to": [kid_name],
        "auto_approve": False,
        "completion_criteria": "independent",
    }

    form_data = FlowTestHelper.build_chore_form_data(yaml_chore)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_CHORES,
        OPTIONS_FLOW_STEP_ADD_CHORE,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify chore was created via coordinator
    chore_names = [c["name"] for c in coordinator.chores_data.values()]
    assert "Test Chore" in chore_names


async def test_add_reward_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a reward via options flow."""
    config_entry = init_integration_with_coordinator.config_entry

    yaml_reward = {
        "name": "Ice Cream",
        "cost": 100,
        "icon": "mdi:ice-cream",
        "description": "Delicious treat",
    }

    form_data = FlowTestHelper.build_reward_form_data(yaml_reward)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_REWARDS,
        OPTIONS_FLOW_STEP_ADD_REWARD,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify reward was created via coordinator
    coordinator = init_integration_with_coordinator.coordinator
    reward_names = [r["name"] for r in coordinator.rewards_data.values()]
    assert "Ice Cream" in reward_names


async def test_add_penalty_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a penalty via options flow."""
    config_entry = init_integration_with_coordinator.config_entry

    yaml_penalty = {
        "name": "Late Chore",
        "points": 5,
        "icon": "mdi:clock-alert",
    }

    form_data = FlowTestHelper.build_penalty_form_data(yaml_penalty)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_PENALTIES,
        OPTIONS_FLOW_STEP_ADD_PENALTY,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify penalty was created via coordinator
    coordinator = init_integration_with_coordinator.coordinator
    penalty_names = [p["name"] for p in coordinator.penalties_data.values()]
    assert "Late Chore" in penalty_names


async def test_add_bonus_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a bonus via options flow."""
    config_entry = init_integration_with_coordinator.config_entry

    yaml_bonus = {
        "name": "Extra Effort",
        "points": 20,
        "icon": "mdi:star-plus",
    }

    form_data = FlowTestHelper.build_bonus_form_data(yaml_bonus)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_BONUSES,
        OPTIONS_FLOW_STEP_ADD_BONUS,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify bonus was created via coordinator
    coordinator = init_integration_with_coordinator.coordinator
    bonus_names = [b["name"] for b in coordinator.bonuses_data.values()]
    assert "Extra Effort" in bonus_names


async def test_add_badge_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a badge via options flow."""
    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    # Get existing kid ID for assignment
    kid_id = next(iter(coordinator.kids_data.keys()))

    # Badge flow requires 2 steps: type selection, then details
    # Step 1: Navigate to badges menu
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_BADGES},
    )

    # Step 2: Select "Add" action
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )

    # Step 3: Select badge type (cumulative)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CFOF_BADGES_INPUT_TYPE: BADGE_TYPE_CUMULATIVE},
    )

    # Step 4: Provide badge details
    # Cumulative badge schema does NOT include target_type field
    # Only includes: name, icon, assigned_to, award_points, target_threshold_value
    badge_data = {
        CFOF_BADGES_INPUT_NAME: "Chore Champion",
        CFOF_BADGES_INPUT_ICON: "mdi:medal",
        CFOF_BADGES_INPUT_ASSIGNED_TO: [kid_id],
        CFOF_BADGES_INPUT_AWARD_POINTS: 25,
        CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 100,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=badge_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify badge was created via coordinator
    badge_names = [b["name"] for b in coordinator.badges_data.values()]
    assert "Chore Champion" in badge_names


async def test_add_achievement_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding an achievement via options flow."""
    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    # Get existing kid ID for assignment
    kid_id = next(iter(coordinator.kids_data.keys()))

    yaml_achievement = {
        "name": "First Ten Chores",
        "icon": "mdi:trophy",
        "description": "Complete 10 chores",
        "type": "chore_total",  # Valid types: chore_total, chore_streak, daily_minimum
        "target_value": 10,
        "reward_points": 50,
        "assigned_to": [kid_id],
    }

    form_data = FlowTestHelper.build_achievement_form_data(yaml_achievement)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_ACHIEVEMENTS,
        OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify achievement was created via coordinator
    achievement_names = [a["name"] for a in coordinator.achievements_data.values()]
    assert "First Ten Chores" in achievement_names


async def test_add_challenge_via_options_flow(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding a challenge via options flow."""
    from homeassistant.util import dt as dt_util

    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    # Get existing kid NAME for assignment (options flow schema uses names as values)
    kid_id = next(iter(coordinator.kids_data.keys()))
    kid_name = coordinator.kids_data[kid_id][DATA_KID_NAME]

    # Calculate future dates (options flow validates dates must be in future)
    now = dt_util.utcnow()
    start_date = (now + datetime.timedelta(days=1)).isoformat()
    end_date = (now + datetime.timedelta(days=3)).isoformat()

    yaml_challenge = {
        "name": "Weekend Warrior",
        "icon": "mdi:flag",
        "description": "Complete 5 chores this weekend",
        "type": "total_within_window",  # Valid types: total_within_window, daily_minimum
        "target_value": 5,
        "reward_points": 100,
        "start_date": start_date,
        "end_date": end_date,
        "assigned_to": [
            kid_name
        ],  # Options flow schema expects kid NAMES as selector values
    }

    form_data = FlowTestHelper.build_challenge_form_data(yaml_challenge)

    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_CHALLENGES,
        OPTIONS_FLOW_STEP_ADD_CHALLENGE,
        form_data,
    )

    # Options flow returns to init step after successful add
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Verify challenge was created via coordinator
    challenge_names = [c["name"] for c in coordinator.challenges_data.values()]
    assert "Weekend Warrior" in challenge_names


# =========================================================================
# YAML Scenario-Driven Tests
# =========================================================================


async def test_add_entities_from_minimal_scenario(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test adding NEW entities based on minimal YAML scenario patterns.

    Note: The init fixture already loaded scenario_minimal, so existing entities
    (Zoë, Mom, Feed the cats, etc.) are already present. This test adds NEW
    entities that don't already exist using similar patterns.
    """
    config_entry = init_integration_with_coordinator.config_entry

    # Add a NEW user (not from scenario - that would be duplicate)
    new_parent_data = {"name": "New Scenario User", "allow_chore_assignment": True}
    form_data = FlowTestHelper.build_parent_form_data(new_parent_data)
    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_USERS,
        OPTIONS_FLOW_STEP_ADD_USER,
        form_data,
    )
    # Verify flow succeeded (returns to init)
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # After options flow add, integration reloads - get fresh coordinator
    coordinator = config_entry.runtime_data
    parent_names = [p["name"] for p in coordinator.parents_data.values()]
    assert "New Scenario User" in parent_names

    # Add a NEW reward (not the existing "Ice Créam!")
    new_reward_data = {"name": "New Scenario Reward", "cost": 50}
    form_data = FlowTestHelper.build_reward_form_data(new_reward_data)
    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_REWARDS,
        OPTIONS_FLOW_STEP_ADD_REWARD,
        form_data,
    )
    # Verify flow succeeded (returns to init)
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Get fresh coordinator again after reload
    coordinator = config_entry.runtime_data
    reward_names = [r["name"] for r in coordinator.rewards_data.values()]
    assert "New Scenario Reward" in reward_names


# =========================================================================
# Error Handling Tests
# =========================================================================


async def test_add_duplicate_kid_name_error(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test error when adding user with duplicate name."""
    config_entry = init_integration_with_coordinator.config_entry

    # Add first user
    form_data = FlowTestHelper.build_parent_form_data(
        {"name": "Duplicate User", "allow_chore_assignment": True}
    )
    await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_USERS,
        OPTIONS_FLOW_STEP_ADD_USER,
        form_data,
    )

    # Try to add user with same name
    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_USERS,
        OPTIONS_FLOW_STEP_ADD_USER,
        form_data,
    )

    # Should stay on form with error
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert "base" in errors or "name" in errors


async def test_add_duplicate_chore_name_error(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Test error when adding chore with duplicate name."""
    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    # Get existing kid name to assign chore
    kid_name = next(iter(coordinator.kids_data.values()))["name"]

    # Build chore data in YAML format (assigned_to, type)
    yaml_chore = {
        "name": "Unique Test Chore",
        "assigned_to": [kid_name],
        "type": "daily",
        "points": 10,
    }
    form_data = FlowTestHelper.build_chore_form_data(yaml_chore)

    # Add first chore
    await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_CHORES,
        OPTIONS_FLOW_STEP_ADD_CHORE,
        form_data,
    )

    # Try to add chore with same name
    result = await FlowTestHelper.add_entity_via_options_flow(
        hass,
        config_entry.entry_id,
        OPTIONS_FLOW_CHORES,
        OPTIONS_FLOW_STEP_ADD_CHORE,
        form_data,
    )

    # Should stay on form with error
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert "base" in errors or CFOF_CHORES_INPUT_NAME in errors


async def _navigate_to_add_chore_form(
    hass: HomeAssistant,
    entry_id: str,
) -> dict[str, Any]:
    """Navigate options flow to add chore form."""
    menu_result = await FlowTestHelper.navigate_to_entity_menu(
        hass, entry_id, OPTIONS_FLOW_CHORES
    )
    add_result = await hass.config_entries.options.async_configure(
        menu_result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )
    assert add_result.get("step_id") == OPTIONS_FLOW_STEP_ADD_CHORE
    return add_result


@pytest.mark.parametrize(
    ("overrides", "expected_field", "expected_error"),
    [
        (
            {CFOF_CHORES_INPUT_ASSIGNED_KIDS: []},
            CFOF_CHORES_INPUT_ASSIGNED_KIDS,
            "no_kids_assigned",
        ),
        (
            {CFOF_CHORES_INPUT_DEFAULT_POINTS: -1},
            CFOF_CHORES_INPUT_DEFAULT_POINTS,
            "invalid_points",
        ),
        (
            {
                CFOF_CHORES_INPUT_DUE_DATE: datetime.datetime.now(datetime.UTC)
                - datetime.timedelta(days=1)
            },
            CFOF_CHORES_INPUT_DUE_DATE,
            "due_date_in_past",
        ),
        (
            {
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            },
            CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
            "error_daily_multi_requires_compatible_reset",
        ),
        (
            {
                CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_AT_DUE_DATE_ONCE,
            },
            CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
            "invalid_overdue_reset_combination",
        ),
        (
            {
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                CFOF_CHORES_INPUT_DUE_DATE: None,
            },
            CFOF_CHORES_INPUT_DUE_DATE,
            "error_daily_multi_due_date_required",
        ),
        (
            {
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_AT_DUE_DATE_ONCE,
                CFOF_CHORES_INPUT_DUE_DATE: None,
            },
            CFOF_CHORES_INPUT_DUE_DATE,
            "error_at_due_date_reset_requires_due_date",
        ),
        (
            {
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_ROTATION_SIMPLE,
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["__single_kid__"],
            },
            CFOF_CHORES_INPUT_ASSIGNED_KIDS,
            "rotation_min_kids",
        ),
        (
            {
                CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: "__allow_steal__",
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
            },
            CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
            "error_allow_steal_incompatible",
        ),
    ],
    ids=[
        "no_kids_assigned",
        "invalid_points",
        "due_date_in_past",
        "daily_multi_reset_combo",
        "overdue_reset_combo",
        "daily_multi_requires_due_date",
        "at_due_date_reset_requires_due_date",
        "rotation_min_kids",
        "allow_steal_incompatible",
    ],
)
async def test_chore_validation_error_matrix_field_level_and_translated(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
    overrides: dict[str, Any],
    expected_field: str,
    expected_error: str,
) -> None:
    """Validate chore add-flow errors bind to field keys with translated keys."""
    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    kid_names = [kid[DATA_KID_NAME] for kid in coordinator.kids_data.values()]
    assert kid_names

    add_form = await _navigate_to_add_chore_form(hass, config_entry.entry_id)

    form_input: dict[str, Any] = {
        CFOF_CHORES_INPUT_NAME: "Validation Matrix Chore",
        CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
        CFOF_CHORES_INPUT_ICON: "mdi:check",
        CFOF_CHORES_INPUT_DESCRIPTION: "",
        CFOF_CHORES_INPUT_ASSIGNED_KIDS: kid_names,
        CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
        CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
        CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
        CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: OVERDUE_HANDLING_AT_DUE_DATE,
        CFOF_CHORES_INPUT_DUE_DATE: datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(days=1),
    }

    # Replace single-kid sentinel with the first real kid name for the
    # rotation-min-kids case.
    if overrides.get(CFOF_CHORES_INPUT_ASSIGNED_KIDS) == ["__single_kid__"]:
        overrides = {
            **overrides,
            CFOF_CHORES_INPUT_ASSIGNED_KIDS: [kid_names[0]],
        }

    form_input.update(overrides)

    # tests.helpers does not export this v0.5.0 overdue option yet.
    if form_input.get(CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE) == "__allow_steal__":
        form_input[CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE] = "at_due_date_allow_steal"

    result = await hass.config_entries.options.async_configure(
        add_form["flow_id"],
        user_input=form_input,
    )

    assert result.get("step_id") == OPTIONS_FLOW_STEP_ADD_CHORE
    errors = result.get("errors") or {}
    assert expected_field in errors
    assert errors[expected_field] == expected_error


async def test_chore_validation_duplicate_name_field_level_and_translated(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Validate duplicate chore name returns name field + translation key."""
    config_entry = init_integration_with_coordinator.config_entry
    coordinator = init_integration_with_coordinator.coordinator

    kid_names = [kid[DATA_KID_NAME] for kid in coordinator.kids_data.values()]
    assert kid_names

    # Create initial chore.
    first_add = await _navigate_to_add_chore_form(hass, config_entry.entry_id)
    create_input = {
        CFOF_CHORES_INPUT_NAME: "Validation Duplicate Chore",
        CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
        CFOF_CHORES_INPUT_ICON: "mdi:check",
        CFOF_CHORES_INPUT_DESCRIPTION: "",
        CFOF_CHORES_INPUT_ASSIGNED_KIDS: kid_names,
        CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
        CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
        CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
        CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: OVERDUE_HANDLING_AT_DUE_DATE,
        CFOF_CHORES_INPUT_DUE_DATE: datetime.datetime.now(datetime.UTC)
        + datetime.timedelta(days=1),
    }
    created = await hass.config_entries.options.async_configure(
        first_add["flow_id"],
        user_input=create_input,
    )
    assert created.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Attempt duplicate.
    second_add = await _navigate_to_add_chore_form(hass, config_entry.entry_id)
    duplicate = await hass.config_entries.options.async_configure(
        second_add["flow_id"],
        user_input=create_input,
    )
    assert duplicate.get("step_id") == OPTIONS_FLOW_STEP_ADD_CHORE
    errors = duplicate.get("errors") or {}
    assert CFOF_CHORES_INPUT_NAME in errors
    assert errors[CFOF_CHORES_INPUT_NAME] == "duplicate_chore"


async def test_chore_validation_no_kids_surfaces_section_error_with_section_payload(
    hass: HomeAssistant,
    init_integration_with_coordinator: SetupResult,
) -> None:
    """Validate no-kids error is visible for sectioned chore form submissions."""
    config_entry = init_integration_with_coordinator.config_entry

    add_form = await _navigate_to_add_chore_form(hass, config_entry.entry_id)

    sectioned_input: dict[str, Any] = {
        CHORE_SECTION_ROOT_FORM: {
            CFOF_CHORES_INPUT_NAME: "Section Payload No Kids",
            CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
            CFOF_CHORES_INPUT_ICON: "mdi:check",
            CFOF_CHORES_INPUT_DESCRIPTION: "",
            CFOF_CHORES_INPUT_ASSIGNED_KIDS: [],
            CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
        },
        CHORE_SECTION_SCHEDULE: {
            CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
            CFOF_CHORES_INPUT_DUE_DATE: datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(days=1),
        },
        CHORE_SECTION_ADVANCED_CONFIGURATIONS: {
            CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
            CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: OVERDUE_HANDLING_AT_DUE_DATE,
        },
    }

    result = await hass.config_entries.options.async_configure(
        add_form["flow_id"],
        user_input=sectioned_input,
    )

    assert result.get("step_id") == OPTIONS_FLOW_STEP_ADD_CHORE
    errors = result.get("errors") or {}
    assert errors.get(CHORE_SECTION_ROOT_FORM) == "no_kids_assigned"
