"""Tests for admin button authorization fail-closed behavior (Issue #247).

Covers:
- Anonymous (user_id=None) presses on admin buttons are denied when auth is enforced
- The admin_button_auth toggle flips between fail-closed (default) and fail-open
- Authorized admin/approver presses still succeed
- Kiosk mode does NOT bypass admin button auth
- Options-flow persistence of the admin_button_auth toggle
- Shared _ensure_admin_authorized helper unit tests
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from custom_components.choreops.button import _ensure_admin_authorized
from custom_components.choreops.helpers.auth_helpers import (
    AUTH_ACTION_APPROVAL,
    AUTH_ACTION_MANAGEMENT,
    is_admin_button_auth_enforced,
)
from custom_components.choreops.helpers.entity_helpers import (
    get_points_adjustment_buttons,
)
from tests.helpers import (
    CHORE_STATE_CLAIMED,
    OPTIONS_FLOW_GENERAL_OPTIONS,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    SetupResult,
    claim_chore,
    find_bonus,
    find_chore,
    find_penalty,
    get_chore_buttons,
    get_dashboard_helper,
    setup_from_yaml,
)
from tests.helpers.workflows import find_reward, get_reward_buttons


async def _press_button(
    hass: HomeAssistant,
    button_eid: str,
    context: Context,
) -> None:
    """Press a button entity with explicit error propagation."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {"entity_id": button_eid},
        blocking=True,
        context=context,
    )


def _get_schema_default_value(data_schema: Any, field_key: str) -> Any:
    """Return the default value for a voluptuous schema field."""
    for schema_key in data_schema.schema:
        normalized_key = getattr(schema_key, "schema", schema_key)
        if normalized_key != field_key:
            continue

        default = getattr(schema_key, "default", None)
        if callable(default):
            return default()
        return default

    return None


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for chore claim button tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario for reward/bonus/penalty/points button coverage."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# =============================================================================
# Shared helper unit tests
# =============================================================================


async def test_ensure_admin_authorized_denies_anonymous_when_enforced(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Anonymous press is denied when admin button auth is enforced."""
    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _ensure_admin_authorized(
                hass,
                None,
                scenario_minimal.assignee_ids["Zoë"],
                AUTH_ACTION_APPROVAL,
                const.ERROR_ACTION_APPROVE_CHORES,
            )


async def test_ensure_admin_authorized_denies_unauthorized_when_enforced(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Unauthorized user is denied when admin button auth is enforced."""
    unauthorized_context = Context(user_id=mock_hass_users["assignee2"].id)
    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=True,
        ),
        patch(
            "custom_components.choreops.button.is_user_authorized_for_action",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(HomeAssistantError):
            await _ensure_admin_authorized(
                hass,
                unauthorized_context,
                scenario_minimal.assignee_ids["Zoë"],
                AUTH_ACTION_APPROVAL,
                const.ERROR_ACTION_APPROVE_CHORES,
            )


async def test_ensure_admin_authorized_returns_name_when_authorized(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Authorized user returns their display name when auth is enforced."""
    admin_context = Context(user_id=mock_hass_users["admin"].id)
    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=True,
        ),
        patch(
            "custom_components.choreops.button.is_user_authorized_for_action",
            new=AsyncMock(return_value=True),
        ),
    ):
        approver_name = await _ensure_admin_authorized(
            hass,
            admin_context,
            scenario_minimal.assignee_ids["Zoë"],
            AUTH_ACTION_APPROVAL,
            const.ERROR_ACTION_APPROVE_CHORES,
        )

    assert approver_name == "Admin User"


async def test_ensure_admin_authorized_allows_anonymous_when_not_enforced(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Anonymous press is allowed (legacy) when admin button auth is not enforced."""
    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=False,
        ),
        patch(
            "custom_components.choreops.button.is_user_authorized_for_action",
            new=AsyncMock(return_value=False),
        ),
    ):
        approver_name = await _ensure_admin_authorized(
            hass,
            None,
            scenario_minimal.assignee_ids["Zoë"],
            AUTH_ACTION_APPROVAL,
            const.ERROR_ACTION_APPROVE_CHORES,
        )

    assert approver_name == const.DISPLAY_UNKNOWN


async def test_ensure_admin_authorized_management_action(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Management action (no target) is enforced for anonymous presses."""
    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _ensure_admin_authorized(
                hass,
                None,
                None,
                AUTH_ACTION_MANAGEMENT,
                const.ERROR_ACTION_APPLY_BONUSES,
            )


# =============================================================================
# Anonymous press denial on admin buttons (fail-closed default)
# =============================================================================


async def test_anonymous_denied_chore_approve_button(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Anonymous chore approve press is denied when auth is enforced."""
    assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
    claim_result = await claim_chore(hass, "zoe", "Make bed", context=assignee_context)
    assert claim_result.success is True

    dashboard = get_dashboard_helper(hass, "zoe")
    chore = find_chore(dashboard, "Make bed")
    assert chore is not None

    buttons = get_chore_buttons(hass, chore["eid"])
    approve_button_eid = buttons["approve"]
    assert approve_button_eid

    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, approve_button_eid, Context(user_id=None))

    chore_state = hass.states.get(chore["eid"])
    assert chore_state is not None
    assert chore_state.state == CHORE_STATE_CLAIMED


async def test_anonymous_denied_chore_disapprove_button(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Anonymous chore disapprove press (approver branch) is denied when enforced."""
    assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
    claim_result = await claim_chore(hass, "zoe", "Make bed", context=assignee_context)
    assert claim_result.success is True

    dashboard = get_dashboard_helper(hass, "zoe")
    chore = find_chore(dashboard, "Make bed")
    assert chore is not None

    buttons = get_chore_buttons(hass, chore["eid"])
    disapprove_button_eid = buttons["disapprove"]
    assert disapprove_button_eid

    # Kiosk disabled so anonymous does NOT take the undo branch; must hit approver branch
    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=True,
        ),
        patch(
            "custom_components.choreops.button.is_kiosk_mode_enabled",
            return_value=False,
        ),
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, disapprove_button_eid, Context(user_id=None))

    chore_state = hass.states.get(chore["eid"])
    assert chore_state is not None
    assert chore_state.state == CHORE_STATE_CLAIMED


async def test_anonymous_denied_reward_approve_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Anonymous reward approve press is denied when auth is enforced."""
    coordinator = scenario_full.coordinator
    assignee_id = scenario_full.assignee_ids["Zoë"]
    coordinator.users_data[assignee_id][const.DATA_USER_POINTS] = 100.0
    await coordinator.async_refresh()

    assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
    dashboard = get_dashboard_helper(hass, "zoe")
    reward = find_reward(dashboard, "Extra Screen Time")
    assert reward is not None

    claim_button_eid = get_reward_buttons(hass, reward["eid"])["claim"]
    assert claim_button_eid

    with patch.object(
        coordinator.notification_manager, "notify_assignee", new=AsyncMock()
    ):
        await _press_button(hass, claim_button_eid, assignee_context)

    buttons = get_reward_buttons(hass, reward["eid"])
    approve_button_eid = buttons["approve"]
    assert approve_button_eid

    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, approve_button_eid, Context(user_id=None))

    reward_state = hass.states.get(reward["eid"])
    assert reward_state is not None
    assert reward_state.state == const.REWARD_STATE_REQUESTED


async def test_anonymous_denied_reward_disapprove_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Anonymous reward disapprove press (approver branch) is denied when enforced."""
    coordinator = scenario_full.coordinator
    assignee_id = scenario_full.assignee_ids["Zoë"]
    coordinator.users_data[assignee_id][const.DATA_USER_POINTS] = 100.0
    await coordinator.async_refresh()

    assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
    dashboard = get_dashboard_helper(hass, "zoe")
    reward = find_reward(dashboard, "Extra Screen Time")
    assert reward is not None

    claim_button_eid = get_reward_buttons(hass, reward["eid"])["claim"]
    assert claim_button_eid

    with patch.object(
        coordinator.notification_manager, "notify_assignee", new=AsyncMock()
    ):
        await _press_button(hass, claim_button_eid, assignee_context)

    reward_state = hass.states.get(reward["eid"])
    assert reward_state is not None
    disapprove_button_eid = reward_state.attributes.get(
        const.ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID
    )
    assert disapprove_button_eid

    # Kiosk disabled so anonymous does NOT take the undo branch; must hit approver branch
    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=True,
        ),
        patch(
            "custom_components.choreops.button.is_kiosk_mode_enabled",
            return_value=False,
        ),
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, disapprove_button_eid, Context(user_id=None))

    reward_state = hass.states.get(reward["eid"])
    assert reward_state is not None
    assert reward_state.state == const.REWARD_STATE_REQUESTED


async def test_anonymous_denied_bonus_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Anonymous bonus press is denied when auth is enforced."""
    dashboard = get_dashboard_helper(hass, "zoe")
    bonus = find_bonus(dashboard, "Extra Effort")
    assert bonus is not None

    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, bonus["eid"], Context(user_id=None))


async def test_anonymous_denied_penalty_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Anonymous penalty press is denied when auth is enforced."""
    dashboard = get_dashboard_helper(hass, "zoe")
    penalty = find_penalty(dashboard, "Missed Chore")
    assert penalty is not None

    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, penalty["eid"], Context(user_id=None))


async def test_anonymous_denied_points_adjust_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Anonymous points-adjust press is denied when auth is enforced."""
    assignee_id = scenario_full.assignee_ids["Zoë"]
    buttons = get_points_adjustment_buttons(
        hass,
        scenario_full.config_entry.entry_id,
        assignee_id,
    )
    assert buttons

    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, str(buttons[0]["eid"]), Context(user_id=None))


# =============================================================================
# Toggle-off (fail-open) allows anonymous presses
# =============================================================================


async def test_toggle_off_allows_anonymous_bonus_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Anonymous bonus press is allowed when admin button auth is not enforced."""
    dashboard = get_dashboard_helper(hass, "zoe")
    bonus = find_bonus(dashboard, "Extra Effort")
    assert bonus is not None

    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=False,
        ),
        patch(
            "custom_components.choreops.button.is_user_authorized_for_action",
            new=AsyncMock(return_value=False),
        ),
    ):
        # Should NOT raise when toggle is off (legacy fail-open)
        await _press_button(hass, bonus["eid"], Context(user_id=None))


async def test_toggle_off_allows_anonymous_points_adjust_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Anonymous points-adjust press is allowed when auth is not enforced."""
    assignee_id = scenario_full.assignee_ids["Zoë"]
    buttons = get_points_adjustment_buttons(
        hass,
        scenario_full.config_entry.entry_id,
        assignee_id,
    )
    assert buttons

    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=False,
        ),
        patch(
            "custom_components.choreops.button.is_user_authorized_for_action",
            new=AsyncMock(return_value=False),
        ),
    ):
        await _press_button(hass, str(buttons[0]["eid"]), Context(user_id=None))


# =============================================================================
# Authorized admin presses succeed
# =============================================================================


async def test_authorized_admin_allowed_bonus_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Authorized admin bonus press succeeds when auth is enforced."""
    dashboard = get_dashboard_helper(hass, "zoe")
    bonus = find_bonus(dashboard, "Extra Effort")
    assert bonus is not None

    admin_context = Context(user_id=mock_hass_users["admin"].id)
    with patch(
        "custom_components.choreops.button.is_admin_button_auth_enforced",
        return_value=True,
    ):
        await _press_button(hass, bonus["eid"], admin_context)


# =============================================================================
# Kiosk mode does NOT bypass admin button auth
# =============================================================================


async def test_kiosk_enabled_still_denies_anonymous_admin_button(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Kiosk mode must NOT allow anonymous admin button presses."""
    dashboard = get_dashboard_helper(hass, "zoe")
    bonus = find_bonus(dashboard, "Extra Effort")
    assert bonus is not None

    with (
        patch(
            "custom_components.choreops.button.is_admin_button_auth_enforced",
            return_value=True,
        ),
        patch(
            "custom_components.choreops.button.is_kiosk_mode_enabled",
            return_value=True,
        ),
    ):
        with pytest.raises(HomeAssistantError):
            await _press_button(hass, bonus["eid"], Context(user_id=None))


# =============================================================================
# Options-flow toggle persistence
# =============================================================================


async def test_options_flow_saves_admin_button_auth_toggle(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """General options flow should persist the admin_button_auth toggle."""
    config_entry = scenario_minimal.config_entry

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_MANAGE_GENERAL_OPTIONS

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES: "1|-1|2|-2|10|-10",
            const.CFOF_SYSTEM_INPUT_DASHBOARD_POINTS_PRECISION: (
                const.DASHBOARD_POINTS_PRECISION_FIXED_2
            ),
            const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL: 5,
            const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD: 90,
            const.CFOF_SYSTEM_INPUT_RETENTION_PERIODS: "14|5|3|3",
            const.CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES: False,
            const.CFOF_SYSTEM_INPUT_KIOSK_MODE: True,
            const.CFOF_SYSTEM_INPUT_ADMIN_APPROVAL_BYPASS: False,
            const.CFOF_SYSTEM_INPUT_ADMIN_BUTTON_AUTH: False,
            const.CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED: 5,
        },
    )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_INIT

    updated_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.options.get(const.CONF_ADMIN_BUTTON_AUTH) is False

    reopened_result = await hass.config_entries.options.async_init(
        config_entry.entry_id
    )
    reopened_result = await hass.config_entries.options.async_configure(
        reopened_result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_GENERAL_OPTIONS},
    )

    assert (
        reopened_result.get("step_id") == const.OPTIONS_FLOW_STEP_MANAGE_GENERAL_OPTIONS
    )
    assert reopened_result.get("data_schema") is not None
    assert (
        _get_schema_default_value(
            reopened_result["data_schema"],
            const.CFOF_SYSTEM_INPUT_ADMIN_BUTTON_AUTH,
        )
        is False
    )


async def test_admin_button_auth_defaults_to_enforced(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """admin_button_auth should default to enforced (fail-closed) when not set."""
    assert is_admin_button_auth_enforced(hass) is True
