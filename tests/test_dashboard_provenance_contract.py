"""Tests for dashboard provenance and helper identity contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers import dashboard_builder as builder
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def test_build_multi_view_dashboard_stamps_provenance() -> None:
    """Builder includes provenance metadata when provided."""
    views = [{"title": "Zoe", "path": "zoe", "cards": []}]
    provenance = {
        const.DASHBOARD_PROVENANCE_KEY_TEMPLATE_ID: "user-full-v1",
        const.DASHBOARD_PROVENANCE_KEY_SOURCE_TYPE: "remote_release",
    }

    config = builder.build_multi_view_dashboard(views, provenance=provenance)

    assert config["views"] == views
    assert config[const.DASHBOARD_CONFIG_KEY_PROVENANCE] == provenance


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for dashboard helper identity tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.mark.asyncio
async def test_dashboard_helper_includes_lookup_identity_contract(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Dashboard helper exposes D11/D12 identity fields."""
    config_entry = scenario_minimal.config_entry

    helper_state = hass.states.get("sensor.zoe_choreops_ui_dashboard_helper")
    assert helper_state is not None

    attrs = helper_state.attributes
    user_id = attrs[const.ATTR_USER_ID]
    assert attrs[const.ATTR_INTEGRATION_ENTRY_ID] == config_entry.entry_id
    assert isinstance(user_id, str) and user_id
    assert attrs[const.ATTR_DASHBOARD_LOOKUP_KEY] == (
        f"{config_entry.entry_id}:{user_id}"
    )
