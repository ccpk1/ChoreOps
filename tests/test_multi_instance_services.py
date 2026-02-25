"""Pragmatic multi-instance service isolation regressions.

Focused coverage for high-risk paths:
- Ambiguous service routing when multiple entries are loaded
- Explicit `config_entry_id` routing isolation
- Service lifecycle on unload with multiple loaded entries
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from custom_components.choreops.services import _resolve_target_entry_id
from tests.helpers.setup import setup_scenario

if TYPE_CHECKING:
    from tests.helpers import SetupResult


@pytest.fixture
async def dual_minimal_scenarios(
    hass,
    mock_hass_users: dict[str, Any],
) -> tuple[SetupResult, SetupResult]:
    """Set up two independent ChoreOps entries with overlapping names."""
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

    first = await setup_scenario(
        hass,
        mock_hass_users,
        scenario,
    )
    second = await setup_scenario(
        hass,
        mock_hass_users,
        scenario,
    )
    return first, second


@pytest.mark.asyncio
async def test_claim_service_requires_explicit_target_when_two_entries_loaded(
    hass,
    dual_minimal_scenarios: tuple[SetupResult, SetupResult],
) -> None:
    """Service call without target must fail when multiple entries are loaded."""
    _first, _second = dual_minimal_scenarios

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_CLAIM_CHORE,
            {
                const.SERVICE_FIELD_USER_NAME: "Zoë",
                const.SERVICE_FIELD_CHORE_NAME: "Make bed",
            },
            blocking=True,
        )


@pytest.mark.asyncio
async def test_claim_service_targets_only_selected_entry(
    hass,
    dual_minimal_scenarios: tuple[SetupResult, SetupResult],
) -> None:
    """Explicit target fields resolve to the selected loaded config entry."""
    first, second = dual_minimal_scenarios

    resolved_by_id = _resolve_target_entry_id(
        hass,
        {const.SERVICE_FIELD_CONFIG_ENTRY_ID: second.config_entry.entry_id},
    )
    assert resolved_by_id == second.config_entry.entry_id

    resolved_by_title = _resolve_target_entry_id(
        hass,
        {const.SERVICE_FIELD_CONFIG_ENTRY_TITLE: first.config_entry.title},
    )
    assert resolved_by_title == first.config_entry.entry_id


@pytest.mark.asyncio
async def test_unloading_one_entry_keeps_domain_services_for_other_entry(
    hass,
    dual_minimal_scenarios: tuple[SetupResult, SetupResult],
) -> None:
    """Unloading one config entry must not deregister services globally."""
    first, second = dual_minimal_scenarios

    assert hass.services.has_service(const.DOMAIN, const.SERVICE_CLAIM_CHORE)

    unload_ok = await hass.config_entries.async_unload(first.config_entry.entry_id)
    assert unload_ok is True
    await hass.async_block_till_done()

    assert hass.services.has_service(const.DOMAIN, const.SERVICE_CLAIM_CHORE)
    resolved = _resolve_target_entry_id(hass, {})
    assert resolved == second.config_entry.entry_id
