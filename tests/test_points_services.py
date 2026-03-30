"""Tests for manual points adjustment service.

Coverage goals (Phase 3):
- Positive and negative signed amount behavior
- Ledger source and reason mapping
- Schema validation (zero, decimal, and missing assignee selectors)
- Assignee resolution via user_id and user_name
- Conflict handling when user_id and user_name disagree (user_id wins)
- Authorization gate (management required)
- Multi-instance routing behavior
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
import pytest
import voluptuous as vol

from custom_components.choreops import const
from custom_components.choreops.const import (
    DATA_LEDGER_AMOUNT,
    DATA_LEDGER_ITEM_NAME,
    DATA_LEDGER_SOURCE,
    DATA_USER_HA_USER_ID,
    DATA_USER_LEDGER,
    DATA_USER_POINTS,
)
from tests.helpers.setup import SetupResult, setup_from_yaml, setup_scenario

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario with multiple users and data domains."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


@pytest.fixture
async def dual_minimal_scenarios(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> tuple[SetupResult, SetupResult]:
    """Set up two independent ChoreOps entries for target-routing tests."""
    scenario = {
        "points": {"label": "Points", "icon": "mdi:star-outline"},
        "assignees": [{"name": "Zoë", "ha_user": "assignee1"}],
        "approvers": [
            {
                "name": "Môm Astrid Stârblüm",
                "ha_user": "approver1",
                "assignees": ["Zoë"],
            }
        ],
        "chores": [
            {
                "name": "Make bed",
                "assigned_to": ["Zoë"],
                "points": 5.0,
                "recurring_frequency": "daily",
            }
        ],
    }

    first = await setup_scenario(hass, mock_hass_users, scenario)
    second = await setup_scenario(hass, mock_hass_users, scenario)
    return first, second


def _get_points(coordinator: Any, assignee_id: str) -> float:
    """Return points for assignee."""
    assignee_info = coordinator.assignees_data.get(assignee_id, {})
    return float(assignee_info.get(DATA_USER_POINTS, 0.0))


def _get_last_ledger_entry(coordinator: Any, assignee_id: str) -> dict[str, Any]:
    """Return latest ledger entry for assignee."""
    ledger = coordinator.assignees_data[assignee_id].get(DATA_USER_LEDGER, [])
    assert isinstance(ledger, list)
    assert ledger
    entry = ledger[-1]
    assert isinstance(entry, dict)
    return entry


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
        if user_data.get(DATA_USER_HA_USER_ID) == ha_user_id:
            user_data[const.DATA_USER_CAN_MANAGE] = can_manage
            return

    raise AssertionError(f"No user mapped to HA user_id={ha_user_id}")


@pytest.mark.asyncio
async def test_manual_adjust_points_positive_amount_user_name(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Positive amount adds points and records manual ledger entry with reason."""
    coordinator = scenario_full.coordinator
    assignee_id = scenario_full.assignee_ids["Zoë"]
    before = _get_points(coordinator, assignee_id)

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_MANUAL_ADJUST_POINTS,
        {
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_POINTS_AMOUNT: 7.25,
            const.SERVICE_FIELD_REASON: "Excellent teamwork",
        },
        blocking=True,
    )

    after = _get_points(coordinator, assignee_id)
    assert after == before + 7.25

    ledger_entry = _get_last_ledger_entry(coordinator, assignee_id)
    assert ledger_entry[DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_MANUAL
    assert ledger_entry[DATA_LEDGER_AMOUNT] == 7.25
    assert ledger_entry[DATA_LEDGER_ITEM_NAME] == "Excellent teamwork"


@pytest.mark.asyncio
async def test_manual_adjust_points_negative_amount_user_id_with_approver_name(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Negative amount deducts points and accepts optional approver_name."""
    coordinator = scenario_full.coordinator
    assignee_id = scenario_full.assignee_ids["Zoë"]
    before = _get_points(coordinator, assignee_id)

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_MANUAL_ADJUST_POINTS,
        {
            const.SERVICE_FIELD_APPROVER_NAME: "Môm Astrid Stârblüm",
            const.SERVICE_FIELD_USER_ID: assignee_id,
            const.SERVICE_FIELD_POINTS_AMOUNT: -5.5,
            const.SERVICE_FIELD_REASON: "Missed commitment",
        },
        blocking=True,
    )

    after = _get_points(coordinator, assignee_id)
    assert after == before - 5.5

    ledger_entry = _get_last_ledger_entry(coordinator, assignee_id)
    assert ledger_entry[DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_MANUAL
    assert ledger_entry[DATA_LEDGER_AMOUNT] == -5.5
    assert ledger_entry[DATA_LEDGER_ITEM_NAME] == "Missed commitment"


@pytest.mark.asyncio
async def test_manual_adjust_points_user_id_preferred_when_name_mismatch(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """When both are provided and mismatched, user_id path takes precedence."""
    coordinator = scenario_full.coordinator
    zoe_id = scenario_full.assignee_ids["Zoë"]
    max_id = scenario_full.assignee_ids["Max!"]

    zoe_before = _get_points(coordinator, zoe_id)
    max_before = _get_points(coordinator, max_id)

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_MANUAL_ADJUST_POINTS,
        {
            const.SERVICE_FIELD_USER_ID: zoe_id,
            const.SERVICE_FIELD_USER_NAME: "Max!",
            const.SERVICE_FIELD_POINTS_AMOUNT: 3,
            const.SERVICE_FIELD_REASON: "ID wins over name",
        },
        blocking=True,
    )

    assert _get_points(coordinator, zoe_id) == zoe_before + 3
    assert _get_points(coordinator, max_id) == max_before


@pytest.mark.asyncio
async def test_manual_adjust_points_rejects_zero_excess_precision_and_missing_assignee(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """Schema rejects amount=0, precision above 2 decimals, and missing assignee."""
    _ = scenario_full
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANUAL_ADJUST_POINTS,
            {
                const.SERVICE_FIELD_USER_NAME: "Zoë",
                const.SERVICE_FIELD_POINTS_AMOUNT: 0,
                const.SERVICE_FIELD_REASON: "Invalid zero",
            },
            blocking=True,
        )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANUAL_ADJUST_POINTS,
            {
                const.SERVICE_FIELD_USER_NAME: "Zoë",
                const.SERVICE_FIELD_POINTS_AMOUNT: 1.234,
                const.SERVICE_FIELD_REASON: "Invalid precision",
            },
            blocking=True,
        )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANUAL_ADJUST_POINTS,
            {
                const.SERVICE_FIELD_POINTS_AMOUNT: 2,
                const.SERVICE_FIELD_REASON: "Missing assignee selector",
            },
            blocking=True,
        )


@pytest.mark.asyncio
async def test_manual_adjust_points_requires_manage_permission(
    hass: HomeAssistant,
    scenario_full: SetupResult,
    mock_hass_users: dict[str, Any],
) -> None:
    """Context user without manage permission is denied."""
    coordinator = scenario_full.coordinator
    assignee_id = scenario_full.assignee_ids["Zoë"]
    actor_user_id = mock_hass_users["assignee1"].id

    _set_user_manage_capability(
        coordinator,
        ha_user_id=actor_user_id,
        can_manage=False,
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANUAL_ADJUST_POINTS,
            {
                const.SERVICE_FIELD_USER_ID: assignee_id,
                const.SERVICE_FIELD_POINTS_AMOUNT: 2,
                const.SERVICE_FIELD_REASON: "Unauthorized attempt",
            },
            blocking=True,
            context=Context(user_id=actor_user_id),
        )


@pytest.mark.asyncio
async def test_manual_adjust_points_multi_instance_requires_explicit_target(
    hass: HomeAssistant,
    dual_minimal_scenarios: tuple[SetupResult, SetupResult],
) -> None:
    """With two loaded entries, missing target should fail as ambiguous."""
    _first, _second = dual_minimal_scenarios

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANUAL_ADJUST_POINTS,
            {
                const.SERVICE_FIELD_USER_NAME: "Zoë",
                const.SERVICE_FIELD_POINTS_AMOUNT: 1,
                const.SERVICE_FIELD_REASON: "Ambiguous target",
            },
            blocking=True,
        )


@pytest.mark.asyncio
async def test_manual_adjust_points_multi_instance_explicit_target_applies_once(
    hass: HomeAssistant,
    dual_minimal_scenarios: tuple[SetupResult, SetupResult],
) -> None:
    """Explicit config_entry_id applies adjustment to selected instance only."""
    first, second = dual_minimal_scenarios

    first_assignee_id = first.assignee_ids["Zoë"]
    second_assignee_id = second.assignee_ids["Zoë"]

    first_before = _get_points(first.coordinator, first_assignee_id)
    second_before = _get_points(second.coordinator, second_assignee_id)

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_MANUAL_ADJUST_POINTS,
        {
            const.SERVICE_FIELD_CONFIG_ENTRY_ID: second.config_entry.entry_id,
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_POINTS_AMOUNT: 4.75,
            const.SERVICE_FIELD_REASON: "Second entry only",
        },
        blocking=True,
    )

    assert _get_points(first.coordinator, first_assignee_id) == first_before
    assert _get_points(second.coordinator, second_assignee_id) == second_before + 4.75
