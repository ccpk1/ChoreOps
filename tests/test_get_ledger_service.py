"""Tests for the get_ledger service (structured ledger dump)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from tests.helpers import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario: 3 assignees, 2 approvers, 8 chores, 3 rewards."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


async def _call_get_ledger(
    hass: HomeAssistant,
    *,
    user_name: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Invoke the get_ledger service and return its response."""
    data: dict[str, Any] = {}
    if user_name is not None:
        data[const.SERVICE_FIELD_USER_NAME] = user_name
    if limit is not None:
        data[const.SERVICE_FIELD_LEDGER_LIMIT] = limit

    response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_GET_LEDGER,
        data,
        blocking=True,
        return_response=True,
    )
    assert isinstance(response, dict)
    return response


async def test_get_ledger_returns_all_users_by_default(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """get_ledger returns entries for all users when no user_name is given."""
    coordinator = scenario_full.coordinator
    zoe_id = scenario_full.assignee_ids["Zoë"]
    max_id = scenario_full.assignee_ids["Max!"]

    await coordinator.economy_manager.deposit(
        assignee_id=zoe_id,
        amount=10.0,
        source=const.POINTS_SOURCE_MANUAL,
        item_name="For being a very good kid",
    )
    await coordinator.economy_manager.deposit(
        assignee_id=max_id,
        amount=5.0,
        source=const.POINTS_SOURCE_BONUSES,
        item_name="Extra effort",
    )

    response = await _call_get_ledger(hass)

    assert response["assignee_id"] is None
    assert response["assignee_name"] is None
    assert response["count"] >= 2
    assert response["truncated"] is False

    # Multi-user entries carry assignee identity
    sources = {entry[const.DATA_LEDGER_SOURCE] for entry in response["entries"]}
    assert const.POINTS_SOURCE_MANUAL in sources
    assert const.POINTS_SOURCE_BONUSES in sources

    # Every multi-user entry has assignee fields
    for entry in response["entries"]:
        assert const.DATA_USER_INTERNAL_ID in entry
        assert const.DATA_USER_NAME in entry


async def test_get_ledger_filters_to_single_user(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """get_ledger with user_name returns only that user's entries."""
    coordinator = scenario_full.coordinator
    zoe_id = scenario_full.assignee_ids["Zoë"]
    max_id = scenario_full.assignee_ids["Max!"]

    await coordinator.economy_manager.deposit(
        assignee_id=zoe_id,
        amount=10.0,
        source=const.POINTS_SOURCE_MANUAL,
        item_name="For being a very good kid",
    )
    await coordinator.economy_manager.deposit(
        assignee_id=max_id,
        amount=5.0,
        source=const.POINTS_SOURCE_BONUSES,
        item_name="Extra effort",
    )

    response = await _call_get_ledger(hass, user_name="Zoë")

    assert response["assignee_id"] == zoe_id
    assert response["assignee_name"] == "Zoë"
    assert response["count"] >= 1

    # Single-user entries do NOT carry per-entry assignee fields
    for entry in response["entries"]:
        assert const.DATA_USER_INTERNAL_ID not in entry
        assert const.DATA_USER_NAME not in entry
        assert entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_MANUAL


async def test_get_ledger_includes_source_label(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """get_ledger includes a human-readable source_label."""
    coordinator = scenario_full.coordinator
    zoe_id = scenario_full.assignee_ids["Zoë"]

    await coordinator.economy_manager.deposit(
        assignee_id=zoe_id,
        amount=10.0,
        source=const.POINTS_SOURCE_MANUAL,
        item_name="For being a very good kid",
    )

    response = await _call_get_ledger(hass, user_name="Zoë")

    assert response["count"] >= 1
    manual_entries = [
        entry
        for entry in response["entries"]
        if entry[const.DATA_LEDGER_SOURCE] == const.POINTS_SOURCE_MANUAL
    ]
    assert manual_entries
    assert manual_entries[0]["source_label"] == "Adjustment"


async def test_get_ledger_limit_returns_most_recent(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """get_ledger with a limit returns the most recent entries and flags truncation."""
    coordinator = scenario_full.coordinator
    zoe_id = scenario_full.assignee_ids["Zoë"]

    for i in range(5):
        await coordinator.economy_manager.deposit(
            assignee_id=zoe_id,
            amount=float(i + 1),
            source=const.POINTS_SOURCE_MANUAL,
            item_name=f"Adjustment {i + 1}",
        )

    response = await _call_get_ledger(hass, user_name="Zoë", limit=2)

    assert response["count"] == 2
    assert response["limit"] == 2
    assert response["truncated"] is True

    # Most recent two entries are the last two deposits
    item_names = [entry[const.DATA_LEDGER_ITEM_NAME] for entry in response["entries"]]
    assert item_names == ["Adjustment 4", "Adjustment 5"]


async def test_get_ledger_summary_totals(
    hass: HomeAssistant,
    scenario_full: SetupResult,
) -> None:
    """get_ledger summary reflects earned/spent/net across returned entries."""
    coordinator = scenario_full.coordinator
    zoe_id = scenario_full.assignee_ids["Zoë"]

    await coordinator.economy_manager.deposit(
        assignee_id=zoe_id,
        amount=10.0,
        source=const.POINTS_SOURCE_MANUAL,
        item_name="Deposit",
    )
    await coordinator.economy_manager.withdraw(
        assignee_id=zoe_id,
        amount=4.0,
        source=const.POINTS_SOURCE_PENALTIES,
        item_name="Penalty",
    )

    response = await _call_get_ledger(hass, user_name="Zoë")

    assert response["summary"]["total_earned"] == 10.0
    assert response["summary"]["total_spent"] == 4.0
    assert response["summary"]["net"] == 6.0
