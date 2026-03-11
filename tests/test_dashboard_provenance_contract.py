"""Tests for dashboard provenance and helper identity contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers import dashboard_builder as builder
from tests.helpers import SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER, construct_entity_id
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


def test_build_multi_view_dashboard_preserves_view_local_button_card_templates() -> (
    None
):
    """Builder preserves view-local button-card templates without hoisting."""
    views = [
        {
            "title": "Zoe",
            "path": "zoe",
            "cards": [],
            "button_card_templates": {
                "choreops_chore_row_v1": {"show_name": True},
            },
        }
    ]

    config = builder.build_multi_view_dashboard(views)

    assert "button_card_templates" not in config
    assert config["views"][0]["button_card_templates"] == {
        "choreops_chore_row_v1": {"show_name": True}
    }


def test_build_dashboard_provenance_includes_required_metadata_keys() -> None:
    """Provenance builder returns required metadata keys for stamped dashboards."""
    provenance = builder._build_dashboard_provenance(
        integration_entry_id="entry-123",
        template_id="user-chores-standard-v1",
        requested_release_selection=const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
        effective_release_ref="0.0.1-beta.3",
        resolution_reason="pinned_tag",
        pinned_release_tag="0.0.1-beta.3",
        include_prereleases=False,
        generated_at="2026-03-02T00:00:00+00:00",
    )

    assert provenance[const.ATTR_INTEGRATION_ENTRY_ID] == "entry-123"
    assert (
        provenance[const.DASHBOARD_PROVENANCE_KEY_TEMPLATE_ID]
        == "user-chores-standard-v1"
    )
    assert provenance[const.DASHBOARD_PROVENANCE_KEY_SOURCE_TYPE] == "remote_release"
    assert provenance[const.DASHBOARD_PROVENANCE_KEY_EFFECTIVE_REF] == "0.0.1-beta.3"
    assert provenance[const.DASHBOARD_PROVENANCE_KEY_GENERATED_AT] == (
        "2026-03-02T00:00:00+00:00"
    )


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


@pytest.mark.asyncio
async def test_system_dashboard_helper_includes_shared_admin_identity_contract(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """System dashboard helper exposes shared-admin lookup identity fields."""
    config_entry = scenario_minimal.config_entry

    helper_states = [
        state
        for state in hass.states.async_all("sensor")
        if state.attributes.get(const.ATTR_PURPOSE)
        == const.TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_HELPER
    ]

    assert len(helper_states) == 1

    attrs = helper_states[0].attributes
    assert attrs[const.ATTR_INTEGRATION_ENTRY_ID] == config_entry.entry_id
    assert attrs[const.ATTR_DASHBOARD_LOOKUP_KEY] == (
        f"{config_entry.entry_id}:{const.ATTR_UI_ROOT_SHARED_ADMIN}"
    )
    assert isinstance(attrs[const.ATTR_UI_CONTROL], dict)
    assert attrs[const.ATTR_USER_DASHBOARD_HELPERS] == {
        assignee_id: construct_entity_id(
            "sensor", user_name, SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        for user_name, assignee_id in scenario_minimal.assignee_ids.items()
    }
    assert isinstance(attrs[const.ATTR_TRANSLATION_SENSOR_EID], str)
