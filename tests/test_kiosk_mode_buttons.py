"""Tests for kiosk mode behavior in kid claim button paths.

Covers:
- Kid chore claim button behavior with kiosk mode disabled/enabled
- Kid reward claim button behavior with kiosk mode enabled
- General options persistence of kiosk mode
- Service auth remains strict when kiosk mode is enabled
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from tests.helpers import (
    CHORE_STATE_CLAIMED,
    CHORE_STATE_PENDING,
    OPTIONS_FLOW_GENERAL_OPTIONS,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    SetupResult,
    claim_chore,
    find_chore,
    get_dashboard_helper,
    setup_from_yaml,
)
from tests.helpers.workflows import find_reward, get_reward_buttons


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
    """Load full scenario for reward claim button kiosk coverage."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


async def test_kiosk_disabled_blocks_unauthorized_chore_claim_button(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Kid claim button should enforce kid auth when kiosk mode is disabled."""
    unauthorized_context = Context(user_id=mock_hass_users["kid2"].id)

    with patch(
        "custom_components.choreops.button.is_kiosk_mode_enabled", return_value=False
    ):
        result = await claim_chore(
            hass,
            "zoe",
            "Make bed",
            context=unauthorized_context,
        )

    assert result.success is True
    assert result.state_before == CHORE_STATE_PENDING
    assert result.state_after == CHORE_STATE_PENDING


async def test_kiosk_enabled_allows_unauthorized_chore_claim_button(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Kid claim button should allow claim from unlinked user when kiosk is enabled."""
    unauthorized_context = Context(user_id=mock_hass_users["kid2"].id)
    with patch(
        "custom_components.choreops.button.is_kiosk_mode_enabled", return_value=True
    ):
        result = await claim_chore(
            hass,
            "zoe",
            "Make bed",
            context=unauthorized_context,
        )

    assert result.success is True
    assert result.state_before == CHORE_STATE_PENDING
    assert result.state_after == CHORE_STATE_CLAIMED


async def test_kiosk_enabled_skips_reward_kid_auth_guard(
    hass: HomeAssistant,
    scenario_full: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Reward claim button should skip kid auth guard when kiosk mode is enabled."""
    coordinator = scenario_full.coordinator

    dashboard = get_dashboard_helper(hass, "zoe")
    reward = find_reward(dashboard, "Extra Screen Time")
    assert reward is not None

    buttons = get_reward_buttons(hass, reward["eid"])
    claim_button_eid = buttons["claim"]
    assert claim_button_eid

    with (
        patch(
            "custom_components.choreops.button.is_kiosk_mode_enabled",
            return_value=True,
        ),
        patch(
            "custom_components.choreops.button.is_user_authorized_for_kid",
            new=AsyncMock(return_value=False),
        ) as mock_auth_for_kid,
        patch.object(
            coordinator.reward_manager,
            "redeem",
            new=AsyncMock(return_value=None),
        ) as mock_redeem,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {"entity_id": claim_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["kid99"].id),
        )

    mock_auth_for_kid.assert_not_awaited()
    mock_redeem.assert_awaited_once()


async def test_options_flow_saves_kiosk_mode_toggle(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """General options flow should persist kiosk mode setting."""
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
            const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL: 5,
            const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD: 90,
            const.CFOF_SYSTEM_INPUT_RETENTION_PERIODS: "14|5|3|3",
            const.CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES: False,
            const.CFOF_SYSTEM_INPUT_KIOSK_MODE: True,
            const.CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED: 5,
        },
    )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_INIT

    updated_entry = hass.config_entries.async_get_entry(config_entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.options.get(const.CONF_KIOSK_MODE) is True


async def test_service_claim_auth_stays_strict_with_kiosk_enabled(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Service claim auth should still reject unauthorized users with kiosk enabled."""
    config_entry = scenario_minimal.config_entry

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.options,
            const.CONF_KIOSK_MODE: True,
        },
    )
    await hass.async_block_till_done()

    unauthorized_context = Context(user_id=mock_hass_users["kid2"].id)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_KID_NAME: "Zoë",
                const.SERVICE_FIELD_CHORE_NAME: "Make bed",
            },
            blocking=True,
            context=unauthorized_context,
        )

    dashboard = get_dashboard_helper(hass, "zoe")
    chore = find_chore(dashboard, "Make bed")
    assert chore is not None

    chore_state = hass.states.get(chore["eid"])
    assert chore_state is not None
    assert chore_state.state == CHORE_STATE_PENDING
