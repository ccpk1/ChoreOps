"""Minimal render smoke tests for dashboard templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import jinja2
import yaml

from custom_components.choreops import const
from custom_components.choreops.helpers import (
    dashboard_builder as builder,
    dashboard_helpers as dh,
)

TEMPLATES_ROOT = Path("custom_components/choreops/dashboards/templates")


def _read_template(name: str) -> str:
    """Read a vendored dashboard template file."""
    return (TEMPLATES_ROOT / name).read_text(encoding="utf-8")


def test_user_template_renders_without_parse_errors() -> None:
    """User template renders and parses into a dashboard dict."""
    template_str = _read_template("user-chores-essential-v1.yaml")
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-chores-essential-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe"
    assert rendered["views"][0]["path"] == "zoe"
    assert isinstance(rendered["views"][0].get("sections"), list)


def test_user_chores_lite_template_renders_without_parse_errors() -> None:
    """Chores Lite template renders and parses into a dashboard dict."""
    template_str = _read_template("user-chores-lite-v1.yaml")
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-chores-lite-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-18T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe"
    assert rendered["views"][0]["path"] == "zoe"
    assert isinstance(rendered["views"][0].get("sections"), list)


def test_admin_template_renders_without_parse_errors() -> None:
    """Admin template renders and parses into a dashboard dict."""
    template_str = _read_template("admin-shared-v1.yaml")
    context = dh.build_admin_dashboard_context(
        integration_entry_id="entry-123",
        template_profile="admin-shared-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, context)

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "OpsCenter"
    assert rendered["views"][0]["path"] == "admin"
    assert isinstance(rendered["views"][0].get("sections"), list)


def test_admin_peruser_template_renders_without_parse_errors() -> None:
    """Per-user admin template renders and parses into a dashboard dict."""
    template_str = _read_template("admin-peruser-v1.yaml")
    context = dh.build_dashboard_context(
        "Alice",
        assignee_id="user-alice",
        integration_entry_id="entry-123",
        template_profile="admin-peruser-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Alice OpsCenter"
    assert rendered["views"][0]["path"] == "admin-alice"
    assert isinstance(rendered["views"][0].get("sections"), list)


def _get_admin_peruser_filter_template(marker: str) -> str:
    """Return one rendered per-user admin auto-entities inner template by marker."""

    template_str = _read_template("admin-peruser-v1.yaml")
    context = dh.build_dashboard_context(
        "Alice",
        assignee_id="user-alice",
        integration_entry_id="entry-123",
        template_profile="admin-peruser-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-09T00:00:00+00:00",
    )
    rendered = builder.render_dashboard_template(template_str, dict(context))

    return next(
        card["filter"]["template"]
        for section in rendered["views"][0]["sections"]
        for card in section.get("cards", [])
        if isinstance(card, dict)
        and isinstance(card.get("filter"), dict)
        and marker in str(card["filter"].get("template", ""))
    )


def test_admin_peruser_management_omits_selector_controls() -> None:
    """Per-user management should not expose shared-selector controls."""

    management_template = _get_admin_peruser_filter_template("===== MANAGEMENT =====")

    assert "select.select_option" not in management_template
    assert "clear_selection" not in management_template


@dataclass
class _MockState:
    """Minimal Home Assistant-like state object for template rendering tests."""

    entity_id: str
    state: str
    attributes: dict[str, object]
    name: str


class _MockStatesProxy:
    """Home Assistant-like states helper supporting call and item access."""

    def __init__(self, mock_states: dict[str, _MockState]) -> None:
        """Initialize the proxy with known mock states."""
        self._mock_states = mock_states

    def __call__(self, entity_id: str) -> str:
        """Return one entity state string."""
        if entity_id in self._mock_states:
            return self._mock_states[entity_id].state
        return "unknown"

    def __getitem__(self, entity_id: str) -> _MockState:
        """Return one entity state object."""
        return self._mock_states[entity_id]


def _build_runtime_template_env(
    mock_states: dict[str, _MockState],
) -> tuple[
    jinja2.Environment,
    Any,
    _MockStatesProxy,
    Any,
]:
    """Build a minimal runtime Jinja environment for admin filter templates."""

    def integration_entities(_domain: str) -> list[str]:
        return list(mock_states)

    def expand_filter(values: list[object]) -> list[_MockState]:
        expanded_states: list[_MockState] = []
        for value in values:
            if isinstance(value, _MockState):
                expanded_states.append(value)
            elif isinstance(value, str) and value in mock_states:
                expanded_states.append(mock_states[value])
        return expanded_states

    states = _MockStatesProxy(mock_states)

    def state_attr(entity_id: str, attr_name: str) -> object | None:
        if entity_id in mock_states:
            return mock_states[entity_id].attributes.get(attr_name)
        return None

    def regex_replace_filter(value: object, pattern: str, replacement: str = "") -> str:
        """Mirror Home Assistant's regex_replace filter for runtime template tests."""

        return re.sub(pattern, replacement, str(value))

    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters["expand"] = expand_filter
    env.tests["search"] = lambda value, pattern: (
        __import__("re").search(pattern, value) is not None
    )
    env.filters["regex_replace"] = regex_replace_filter
    env.tests["match"] = lambda value, pattern: (
        __import__("re").match(pattern, value) is not None
    )
    return env, integration_entities, states, state_attr


def _get_admin_filter_template(template_profile: str, marker: str) -> str:
    """Return one rendered admin auto-entities inner template by marker."""

    template_str = _read_template("admin-shared-v1.yaml")
    context = dh.build_admin_dashboard_context(
        integration_entry_id="entry-123",
        template_profile=template_profile,
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-09T00:00:00+00:00",
    )
    rendered = builder.render_dashboard_template(template_str, context)

    return next(
        card["filter"]["template"]
        for section in rendered["views"][0]["sections"]
        for card in section.get("cards", [])
        if isinstance(card, dict)
        and isinstance(card.get("filter"), dict)
        and marker in str(card["filter"].get("template", ""))
    )


def _base_admin_chore_management_states(
    *,
    selected_user_name: str,
    selected_dashboard_helper: str,
    chore_selector_state: str,
    chore_items: list[dict[str, object]],
    selected_user_ui_control: dict[str, object] | None = None,
    chore_sensor_state: str = "pending",
    chore_sensor_attributes: dict[str, object] | None = None,
) -> dict[str, _MockState]:
    """Build minimal states for the admin chore-management filter tests."""

    selected_user_ui_control = selected_user_ui_control or {}
    chore_sensor_attributes = chore_sensor_attributes or {}
    mock_states = {
        "select.choreops_admin_target": _MockState(
            entity_id="select.choreops_admin_target",
            state=selected_user_name,
            attributes={
                "purpose": "purpose_system_dashboard_admin_user",
                "integration_entry_id": "entry-123",
                "dashboard_helper_eid": selected_dashboard_helper,
            },
            name="Admin Target",
        ),
        "sensor.shared_admin_dashboard_helper": _MockState(
            entity_id="sensor.shared_admin_dashboard_helper",
            state="available",
            attributes={
                "purpose": "purpose_system_dashboard_helper",
                "integration_entry_id": "entry-123",
                "dashboard_lookup_key": "entry-123:shared_admin",
                "ui_control": {},
                "user_dashboard_helpers": {
                    "user-alice": selected_dashboard_helper,
                },
                "translation_sensor_eid": "sensor.translations",
            },
            name="Shared Admin Dashboard Helper",
        ),
        selected_dashboard_helper: _MockState(
            entity_id=selected_dashboard_helper,
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Alice",
                "user_id": "user-alice",
                "ui_control": selected_user_ui_control,
                "dashboard_helpers": {
                    "translation_sensor_eid": "sensor.translations",
                    "chore_select_eid": "select.alice_chores",
                },
                "core_sensors": {},
                "chores": chore_items,
            },
            name="Alice Dashboard Helper",
        ),
        "select.alice_chores": _MockState(
            entity_id="select.alice_chores",
            state=chore_selector_state,
            attributes={
                "purpose": "purpose_select_user_chores",
                "user_name": "Alice",
            },
            name="Alice Chores",
        ),
        "sensor.translations": _MockState(
            entity_id="sensor.translations",
            state="ok",
            attributes={
                "ui_translations": {
                    "chores": "Chores",
                    "choose_chore_for_admin_actions": (
                        "Choose the chore for admin actions below."
                    ),
                    "viewing_selected_chore": "Viewing selected chore",
                    "active": "Active",
                    "select_user_to_manage_chores_first": (
                        "Select a user before managing chores."
                    ),
                    "select_chore_to_manage": "Select chore to manage",
                    "none": "None",
                }
            },
            name="Translations",
        ),
    }

    for chore_item in chore_items:
        chore_entity_id = str(chore_item["eid"])
        mock_states[chore_entity_id] = _MockState(
            entity_id=chore_entity_id,
            state=chore_sensor_state,
            attributes={
                "icon": "mdi:broom",
                "default_points": 5,
                "approval_reset_type": "at_midnight_once",
                "completion_criteria": "independent",
                "recurring_frequency": "none",
                **chore_sensor_attributes,
            },
            name=str(chore_item["name"]),
        )

    return mock_states


def _base_admin_economy_management_states(
    *,
    selected_user_name: str,
    selected_dashboard_helper: str,
    gamification_enabled: bool,
    selected_user_ui_control: dict[str, object] | None = None,
    point_buttons: list[dict[str, object]] | None = None,
    bonuses: list[dict[str, object]] | None = None,
    penalties: list[dict[str, object]] | None = None,
) -> dict[str, _MockState]:
    """Build minimal states for the admin economy-management filter tests."""

    selected_user_ui_control = selected_user_ui_control or {}
    point_buttons = point_buttons or []
    bonuses = bonuses or []
    penalties = penalties or []

    mock_states = {
        "select.choreops_admin_target": _MockState(
            entity_id="select.choreops_admin_target",
            state=selected_user_name,
            attributes={
                "purpose": "purpose_system_dashboard_admin_user",
                "integration_entry_id": "entry-123",
                "dashboard_helper_eid": selected_dashboard_helper,
            },
            name="Admin Target",
        ),
        "sensor.shared_admin_dashboard_helper": _MockState(
            entity_id="sensor.shared_admin_dashboard_helper",
            state="available",
            attributes={
                "purpose": "purpose_system_dashboard_helper",
                "integration_entry_id": "entry-123",
                "dashboard_lookup_key": "entry-123:shared_admin",
                "ui_control": {},
                "user_dashboard_helpers": {
                    "user-alice": selected_dashboard_helper,
                },
                "translation_sensor_eid": "sensor.translations",
            },
            name="Shared Admin Dashboard Helper",
        ),
        selected_dashboard_helper: _MockState(
            entity_id=selected_dashboard_helper,
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Alice",
                "user_id": "user-alice",
                "gamification_enabled": gamification_enabled,
                "ui_control": selected_user_ui_control,
                "dashboard_helpers": {
                    "translation_sensor_eid": "sensor.translations",
                },
                "core_sensors": {
                    "points_eid": "sensor.alice_points",
                },
                "points_buttons": point_buttons,
                "bonuses": bonuses,
                "penalties": penalties,
            },
            name="Alice Dashboard Helper",
        ),
        "sensor.alice_points": _MockState(
            entity_id="sensor.alice_points",
            state="231",
            attributes={
                "icon": "mdi:star-circle",
                "unit_of_measurement": "Points",
                "points_multiplier": 1.1,
                "point_stat_points_earned_week": 233,
                "point_stat_avg_points_per_day_week": 33,
            },
            name="Alice Points",
        ),
        "sensor.translations": _MockState(
            entity_id="sensor.translations",
            state="ok",
            attributes={
                "ui_translations": {
                    "points_details": "Points Details",
                    "manage_manual_adjustments": "Manage manual adjustments",
                    "viewing_selected_user": "Viewing selected user",
                    "available": "Available",
                    "active": "Active",
                    "this_week": "This Week",
                    "points_per_day": "Points / Day",
                    "weekly_performance": "Weekly Performance",
                    "bonus": "Bonus",
                    "penalty": "Penalty",
                    "applied": "Applied",
                    "none": "None",
                    "clear_applied": "Clear applied",
                }
            },
            name="Translations",
        ),
    }

    for point_button in point_buttons:
        button_eid = str(point_button["eid"])
        mock_states[button_eid] = _MockState(
            entity_id=button_eid,
            state="unknown",
            attributes={
                "icon": str(point_button.get("icon", "mdi:plus-circle-outline")),
            },
            name=str(point_button.get("name", "Points +1")),
        )

    for bonus in bonuses:
        bonus_eid = str(bonus["eid"])
        mock_states[bonus_eid] = _MockState(
            entity_id=bonus_eid,
            state="unknown",
            attributes={
                "icon": str(bonus.get("icon", "mdi:gift-outline")),
            },
            name=str(bonus.get("name", "Bonus")),
        )

    for penalty in penalties:
        penalty_eid = str(penalty["eid"])
        mock_states[penalty_eid] = _MockState(
            entity_id=penalty_eid,
            state="unknown",
            attributes={
                "icon": str(penalty.get("icon", "mdi:alert-octagon-outline")),
            },
            name=str(penalty.get("name", "Penalty")),
        )

    return mock_states


def _base_admin_system_administration_states() -> dict[str, _MockState]:
    """Build minimal states for the admin system-administration filter tests."""

    return {
        "select.choreops_admin_target": _MockState(
            entity_id="select.choreops_admin_target",
            state="None",
            attributes={
                "purpose": "purpose_system_dashboard_admin_user",
                "integration_entry_id": "entry-123",
                "dashboard_helper_eid": "",
            },
            name="Admin Target",
        ),
        "sensor.shared_admin_dashboard_helper": _MockState(
            entity_id="sensor.shared_admin_dashboard_helper",
            state="available",
            attributes={
                "purpose": "purpose_system_dashboard_helper",
                "integration_entry_id": "entry-123",
                "dashboard_lookup_key": "entry-123:shared_admin",
                "ui_control": {},
                "user_dashboard_helpers": {
                    "user-alice": "sensor.alice_dashboard_helper",
                },
                "translation_sensor_eid": "sensor.translations",
            },
            name="Shared Admin Dashboard Helper",
        ),
        "sensor.alice_dashboard_helper": _MockState(
            entity_id="sensor.alice_dashboard_helper",
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Alice",
                "user_id": "user-alice",
                "dashboard_helpers": {
                    "translation_sensor_eid": "sensor.translations",
                },
                "core_sensors": {},
            },
            name="Alice Dashboard Helper",
        ),
        "sensor.translations": _MockState(
            entity_id="sensor.translations",
            state="ok",
            attributes={
                "ui_translations": {
                    "system_administration": "System Administration",
                    "link_to_choreops_integration_configuration": "Open ChoreOps settings.",
                    "documentation_and_help": "Documentation & Help",
                    "documentation_and_help_description": (
                        "Wiki setup and advanced guides."
                    ),
                    "support_the_project": "Support the project",
                    "support_the_project_description": (
                        "Help fund support and the next release."
                    ),
                }
            },
            name="Translations",
        ),
    }


def test_admin_target_selector_template_renders_as_valid_cards() -> None:
    """Shared admin target selector inner template renders valid card configs."""
    template_str = _read_template("admin-shared-v1.yaml")
    context = dh.build_admin_dashboard_context(
        integration_entry_id="entry-123",
        template_profile="admin-shared-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-09T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, context)
    selector_template = next(
        card["filter"]["template"]
        for section in rendered["views"][0]["sections"]
        for card in section.get("cards", [])
        if isinstance(card, dict)
        and isinstance(card.get("filter"), dict)
        and "select.select_option" in str(card["filter"].get("template", ""))
    )

    mock_states = {
        "select.choreops_admin_target": _MockState(
            entity_id="select.choreops_admin_target",
            state="Alice",
            attributes={
                "purpose": "purpose_system_dashboard_admin_user",
                "integration_entry_id": "entry-123",
                "dashboard_helper_eid": "sensor.alice_dashboard_helper",
            },
            name="Admin Target",
        ),
        "sensor.shared_admin_dashboard_helper": _MockState(
            entity_id="sensor.shared_admin_dashboard_helper",
            state="available",
            attributes={
                "purpose": "purpose_system_dashboard_helper",
                "integration_entry_id": "entry-123",
                "dashboard_lookup_key": "entry-123:shared_admin",
                "ui_control": {},
                "user_dashboard_helpers": {
                    "user-alice": "sensor.alice_dashboard_helper",
                    "user-bob": "sensor.bob_dashboard_helper",
                },
                "translation_sensor_eid": "sensor.translations",
            },
            name="Shared Admin Dashboard Helper",
        ),
        "sensor.alice_dashboard_helper": _MockState(
            entity_id="sensor.alice_dashboard_helper",
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Alice",
                "ui_control": {},
                "dashboard_helpers": {"translation_sensor_eid": "sensor.translations"},
            },
            name="Alice Dashboard Helper",
        ),
        "sensor.bob_dashboard_helper": _MockState(
            entity_id="sensor.bob_dashboard_helper",
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Bob",
                "ui_control": {},
                "dashboard_helpers": {"translation_sensor_eid": "sensor.translations"},
            },
            name="Bob Dashboard Helper",
        ),
        "sensor.translations": _MockState(
            entity_id="sensor.translations",
            state="ok",
            attributes={
                "ui_translations": {
                    "none": "None",
                    "admin_target": "Admin target",
                    "choose_user_for_admin_actions": (
                        "Choose the user for admin actions below."
                    ),
                    "current_review_target": "Current review target",
                }
            },
            name="Translations",
        ),
    }

    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(selector_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )

    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["type"] == "custom:button-card"
    assert parsed[0]["entity"] == "select.choreops_admin_target"
    assert parsed[0]["tap_action"]["action"] == "call-service"
    assert parsed[0]["tap_action"]["service"] == "choreops.manage_ui_control"
    assert parsed[0]["tap_action"]["data"] == {
        "config_entry_id": "entry-123",
        "ui_control_target": "shared_admin",
        "ui_control_action": "update",
        "key": "admin-shared/admin-target-selector/header-collapse",
        "value": False,
    }
    assert parsed[0]["hold_action"]["action"] == "more-info"
    assert "Alice" in parsed[0]["custom_fields"]["target"]


def test_admin_target_selector_template_shows_guidance_without_selection() -> None:
    """Shared admin target selector shows chooser guidance when no user is selected."""
    template_str = _read_template("admin-shared-v1.yaml")
    context = dh.build_admin_dashboard_context(
        integration_entry_id="entry-123",
        template_profile="admin-shared-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-09T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, context)
    selector_template = next(
        card["filter"]["template"]
        for section in rendered["views"][0]["sections"]
        for card in section.get("cards", [])
        if isinstance(card, dict)
        and isinstance(card.get("filter"), dict)
        and "select.select_option" in str(card["filter"].get("template", ""))
    )

    mock_states = {
        "select.choreops_admin_target": _MockState(
            entity_id="select.choreops_admin_target",
            state="None",
            attributes={
                "purpose": "purpose_system_dashboard_admin_user",
                "integration_entry_id": "entry-123",
                "dashboard_helper_eid": "",
            },
            name="Admin Target",
        ),
        "sensor.shared_admin_dashboard_helper": _MockState(
            entity_id="sensor.shared_admin_dashboard_helper",
            state="available",
            attributes={
                "purpose": "purpose_system_dashboard_helper",
                "integration_entry_id": "entry-123",
                "dashboard_lookup_key": "entry-123:shared_admin",
                "ui_control": {},
                "user_dashboard_helpers": {
                    "user-alice": "sensor.alice_dashboard_helper",
                },
                "translation_sensor_eid": "sensor.translations",
            },
            name="Shared Admin Dashboard Helper",
        ),
        "sensor.alice_dashboard_helper": _MockState(
            entity_id="sensor.alice_dashboard_helper",
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Alice",
                "ui_control": {},
                "dashboard_helpers": {"translation_sensor_eid": "sensor.translations"},
            },
            name="Alice Dashboard Helper",
        ),
        "sensor.translations": _MockState(
            entity_id="sensor.translations",
            state="ok",
            attributes={
                "ui_translations": {
                    "none": "None",
                    "admin_target": "Admin target",
                    "choose_user_for_admin_actions": (
                        "Choose the user for admin actions below."
                    ),
                    "current_review_target": "Current review target",
                    "selected_user": "Selected user",
                }
            },
            name="Translations",
        ),
    }

    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(selector_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )

    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["type"] == "custom:button-card"
    assert parsed[0]["entity"] == "select.choreops_admin_target"
    assert parsed[0]["label"] == "Choose the user for admin actions below."
    assert parsed[0]["tap_action"]["action"] == "call-service"
    assert parsed[0]["tap_action"]["service"] == "choreops.manage_ui_control"
    assert parsed[0]["tap_action"]["data"] == {
        "config_entry_id": "entry-123",
        "ui_control_target": "shared_admin",
        "ui_control_action": "update",
        "key": "admin-shared/admin-target-selector/header-collapse",
        "value": False,
    }
    assert parsed[0]["hold_action"]["action"] == "more-info"


def test_admin_chore_management_hides_without_selected_user() -> None:
    """Shared admin chore management renders nothing when no user is selected."""

    chores_template = _get_admin_filter_template(
        "admin-shared-v1", "===== CHORE MANAGEMENT ====="
    )
    mock_states = {
        "select.choreops_admin_target": _MockState(
            entity_id="select.choreops_admin_target",
            state="None",
            attributes={
                "purpose": "purpose_system_dashboard_admin_user",
                "integration_entry_id": "entry-123",
                "dashboard_helper_eid": "",
            },
            name="Admin Target",
        ),
        "sensor.shared_admin_dashboard_helper": _MockState(
            entity_id="sensor.shared_admin_dashboard_helper",
            state="available",
            attributes={
                "purpose": "purpose_system_dashboard_helper",
                "integration_entry_id": "entry-123",
                "dashboard_lookup_key": "entry-123:shared_admin",
                "ui_control": {},
                "user_dashboard_helpers": {
                    "user-alice": "sensor.alice_dashboard_helper",
                },
                "translation_sensor_eid": "sensor.translations",
            },
            name="Shared Admin Dashboard Helper",
        ),
        "sensor.alice_dashboard_helper": _MockState(
            entity_id="sensor.alice_dashboard_helper",
            state="ok",
            attributes={
                "purpose": "purpose_dashboard_helper",
                "integration_entry_id": "entry-123",
                "user_name": "Alice",
                "user_id": "user-alice",
                "ui_control": {},
                "dashboard_helpers": {
                    "translation_sensor_eid": "sensor.translations",
                    "chore_select_eid": "select.alice_chores",
                },
                "core_sensors": {},
                "chores": [],
            },
            name="Alice Dashboard Helper",
        ),
        "sensor.translations": _MockState(
            entity_id="sensor.translations",
            state="ok",
            attributes={"ui_translations": {"chores": "Chores"}},
            name="Translations",
        ),
    }
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(chores_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )

    assert output.strip() == ""


def test_admin_chore_management_shows_selector_when_expanded() -> None:
    """Expanded shared admin chore management shows the chore selector."""

    chores_template = _get_admin_filter_template(
        "admin-shared-v1", "===== CHORE MANAGEMENT ====="
    )
    mock_states = _base_admin_chore_management_states(
        selected_user_name="Alice",
        selected_dashboard_helper="sensor.alice_dashboard_helper",
        chore_selector_state="None",
        chore_items=[
            {
                "name": "Wash Dishes",
                "eid": "sensor.alice_chore_wash_dishes",
                "state": "pending",
            }
        ],
        selected_user_ui_control={
            "admin-shared": {"chore-management": {"header-collapse": False}}
        },
    )
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(chores_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )
    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["type"] == "custom:button-card"
    assert parsed[0]["name"] == "Chores"
    assert parsed[1]["type"] == "entities"
    assert parsed[1]["entities"][0]["entity"] == "select.alice_chores"


def test_admin_chore_management_shows_detail_for_selected_chore() -> None:
    """Expanded shared admin chore management shows detail after chore selection."""

    chores_template = _get_admin_filter_template(
        "admin-shared-v1", "===== CHORE MANAGEMENT ====="
    )
    mock_states = _base_admin_chore_management_states(
        selected_user_name="Alice",
        selected_dashboard_helper="sensor.alice_dashboard_helper",
        chore_selector_state="Wash Dishes",
        chore_items=[
            {
                "name": "Wash Dishes",
                "eid": "sensor.alice_chore_wash_dishes",
                "state": "pending",
            }
        ],
        selected_user_ui_control={
            "admin-shared": {"chore-management": {"header-collapse": False}}
        },
    )
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(chores_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )
    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 3
    assert {"border": "none"} in parsed[0]["styles"]["card"]
    assert {"background-color": "transparent"} in parsed[0]["styles"]["card"]
    assert {"margin-top": "20px"} in parsed[0]["styles"]["card"]
    assert parsed[1]["type"] == "entities"
    assert parsed[2]["type"] == "custom:button-card"
    assert parsed[2]["entity"] == "sensor.alice_chore_wash_dishes"
    assert parsed[2]["name"] == "Wash Dishes"


def test_admin_chore_management_collapsed_selected_chore_keeps_tinted_header() -> None:
    """Collapsed shared admin chore management keeps the tinted header for context."""

    chores_template = _get_admin_filter_template(
        "admin-shared-v1", "===== CHORE MANAGEMENT ====="
    )
    mock_states = _base_admin_chore_management_states(
        selected_user_name="Alice",
        selected_dashboard_helper="sensor.alice_dashboard_helper",
        chore_selector_state="Wash Dishes",
        chore_items=[
            {
                "name": "Wash Dishes",
                "eid": "sensor.alice_chore_wash_dishes",
                "state": "pending",
            }
        ],
        selected_user_ui_control={
            "admin-shared": {"chore-management": {"header-collapse": True}}
        },
    )
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(chores_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )
    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["type"] == "custom:button-card"
    assert {
        "border": "1px solid color-mix(in srgb, var(--primary-color) 14%, var(--divider-color))"
    } in parsed[0]["styles"]["card"]
    assert {
        "background-color": "color-mix(in srgb, var(--primary-color) 14%, var(--card-background-color))"
    } in parsed[0]["styles"]["card"]


def test_admin_economy_management_hides_without_gamification() -> None:
    """Shared admin economy management renders nothing when gamification is off."""

    economy_template = _get_admin_filter_template(
        "admin-shared-v1", "===== ECONOMY MANAGEMENT ====="
    )
    mock_states = _base_admin_economy_management_states(
        selected_user_name="Alice",
        selected_dashboard_helper="sensor.alice_dashboard_helper",
        gamification_enabled=False,
    )
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(economy_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )

    assert output.strip() == ""


def test_admin_economy_management_shows_detail_stack_when_expanded() -> None:
    """Expanded shared admin economy renders header plus one wrapped detail card."""

    economy_template = _get_admin_filter_template(
        "admin-shared-v1", "===== ECONOMY MANAGEMENT ====="
    )
    mock_states = _base_admin_economy_management_states(
        selected_user_name="Alice",
        selected_dashboard_helper="sensor.alice_dashboard_helper",
        gamification_enabled=True,
        selected_user_ui_control={
            "admin-shared": {"economy-management": {"header-collapse": False}}
        },
        point_buttons=[
            {
                "eid": "button.alice_points_plus_1",
                "name": "Points +1",
                "icon": "mdi:plus-circle-outline",
            },
            {
                "eid": "button.alice_points_minus_1",
                "name": "Points -1",
                "icon": "mdi:minus-circle-outline",
            },
        ],
        bonuses=[
            {
                "eid": "button.alice_bonus_helpful",
                "name": "Helpful",
                "points": 5,
                "applied": 3,
                "icon": "mdi:gift-outline",
            }
        ],
        penalties=[
            {
                "eid": "button.alice_penalty_late",
                "name": "Late",
                "points": -2,
                "applied": 4,
                "icon": "mdi:alert-octagon-outline",
            }
        ],
    )
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(economy_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )
    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[0]["type"] == "custom:button-card"
    assert parsed[0]["name"] == "Points"
    assert {"border": "none"} in parsed[0]["styles"]["card"]
    assert {"background-color": "transparent"} in parsed[0]["styles"]["card"]
    assert {"margin-top": "12px"} in parsed[0]["styles"]["card"]
    assert parsed[1]["type"] == "custom:button-card"
    assert {"border-left": "4px solid var(--primary-color)"} in parsed[1]["styles"][
        "card"
    ]
    assert parsed[1]["custom_fields"]["hero"]["card"]["type"] == "custom:button-card"
    hero_content = parsed[1]["custom_fields"]["hero"]["card"]["custom_fields"][
        "content"
    ]
    assert "Available" in hero_content
    assert "Manage manual adjustments" not in hero_content
    assert "Points Available" not in hero_content
    assert "width:54px;height:54px" not in hero_content
    assert "📈 33 Points/Day" in hero_content
    assert parsed[1]["custom_fields"]["actions"]["card"]["type"] == "grid"
    assert parsed[1]["custom_fields"]["actions"]["card"]["columns"] == 6
    assert parsed[1]["custom_fields"]["actions"]["card"]["cards"][0]["name"] == "+1"
    assert parsed[1]["custom_fields"]["actions"]["card"]["cards"][1]["name"] == "-1"
    assert parsed[1]["custom_fields"]["ledger"]["card"]["type"] == "grid"
    assert parsed[1]["custom_fields"]["ledger"]["card"]["columns"] == 1
    assert (
        "✨ Bonus"
        in parsed[1]["custom_fields"]["ledger"]["card"]["cards"][0]["custom_fields"][
            "content"
        ]
    )
    assert (
        parsed[1]["custom_fields"]["ledger"]["card"]["cards"][0]["custom_fields"][
            "items"
        ]["card"]["cards"][0]["custom_fields"]["btn_apply"]["card"]["tap_action"][
            "data"
        ]["entity_id"]
        == "button.alice_bonus_helpful"
    )
    assert (
        parsed[1]["custom_fields"]["ledger"]["card"]["cards"][0]["custom_fields"][
            "items"
        ]["card"]["cards"][0]["custom_fields"]["btn_clear"]["card"]["tap_action"][
            "data"
        ]["item_name"]
        == "Helpful"
    )
    assert (
        parsed[1]["custom_fields"]["ledger"]["card"]["cards"][0]["custom_fields"][
            "items"
        ]["card"]["cards"][0]["custom_fields"]["btn_clear"]["card"]["icon"]
        == "mdi:eraser"
    )
    assert {"margin-top": "10px"} in parsed[1]["custom_fields"]["ledger"]["card"][
        "cards"
    ][0]["styles"]["card"]
    assert (
        "💥 Penalty"
        in parsed[1]["custom_fields"]["ledger"]["card"]["cards"][1]["custom_fields"][
            "content"
        ]
    )
    assert {"margin-top": "10px"} in parsed[1]["custom_fields"]["ledger"]["card"][
        "cards"
    ][1]["styles"]["card"]
    assert (
        parsed[1]["custom_fields"]["ledger"]["card"]["cards"][1]["custom_fields"][
            "action"
        ]["card"]["cards"][0]["icon"]
        == "mdi:eraser"
    )
    assert (
        ">-8<"
        in parsed[1]["custom_fields"]["ledger"]["card"]["cards"][1]["custom_fields"][
            "content"
        ]
    )


def test_admin_economy_points_buttons_render_when_expanded() -> None:
    """Expanded shared admin economy nests points action buttons inside the wrapper."""

    economy_points_template = _get_admin_filter_template(
        "admin-shared-v1", "===== ECONOMY MANAGEMENT ====="
    )
    mock_states = _base_admin_economy_management_states(
        selected_user_name="Alice",
        selected_dashboard_helper="sensor.alice_dashboard_helper",
        gamification_enabled=True,
        selected_user_ui_control={
            "admin-shared": {"economy-management": {"header-collapse": False}}
        },
        point_buttons=[
            {
                "eid": "button.alice_points_plus_1",
                "name": "Points +1",
                "icon": "mdi:plus-circle-outline",
            },
            {
                "eid": "button.alice_points_minus_1",
                "name": "Points -1",
                "icon": "mdi:minus-circle-outline",
            },
        ],
    )
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(economy_points_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )
    parsed = yaml.safe_load(f"[{output}]")

    assert isinstance(parsed, list)
    assert len(parsed) == 2
    assert parsed[1]["custom_fields"]["actions"]["card"]["type"] == "grid"
    assert parsed[1]["custom_fields"]["actions"]["card"]["columns"] == 6
    assert (
        parsed[1]["custom_fields"]["actions"]["card"]["cards"][0]["type"]
        == "custom:button-card"
    )
    assert (
        parsed[1]["custom_fields"]["actions"]["card"]["cards"][0]["tap_action"][
            "service"
        ]
        == "button.press"
    )
    assert (
        parsed[1]["custom_fields"]["actions"]["card"]["cards"][0]["tap_action"]["data"][
            "entity_id"
        ]
        == "button.alice_points_plus_1"
    )
    assert parsed[1]["custom_fields"]["actions"]["card"]["cards"][0]["name"] == "+1"
    assert parsed[1]["custom_fields"]["actions"]["card"]["cards"][1]["name"] == "-1"


def test_admin_system_administration_renders_link_stack() -> None:
    """System administration renders config, documentation, and support cards."""

    system_admin_template = _get_admin_filter_template(
        "admin-shared-v1", "===== SYSTEM ADMINISTRATION ====="
    )
    mock_states = _base_admin_system_administration_states()
    env, integration_entities, states, state_attr = _build_runtime_template_env(
        mock_states
    )

    output = env.from_string(system_admin_template).render(
        integration_entities=integration_entities,
        states=states,
        state_attr=state_attr,
    )
    parsed = yaml.safe_load(output)

    assert isinstance(parsed, list)
    assert len(parsed) == 3
    assert parsed[0]["icon"] == "mdi:cog-outline"
    assert parsed[0]["name"] == "System Administration"
    assert parsed[0]["entity"] == "select.choreops_admin_target"
    assert (
        parsed[0]["tap_action"]["url_path"]
        == "/config/integrations/integration/choreops"
    )
    assert parsed[1]["icon"] == "mdi:information-outline"
    assert parsed[1]["name"] == "Documentation & Help"
    assert parsed[1]["entity"] == "select.choreops_admin_target"
    assert parsed[1]["label"] == "Wiki setup and advanced guides."
    assert (
        parsed[1]["tap_action"]["url_path"] == "https://github.com/ccpk1/ChoreOps/wiki"
    )
    assert parsed[2]["icon"] == "mdi:heart"
    assert parsed[2]["name"] == "Support the project"
    assert parsed[2]["tap_action"]["url_path"] == "https://github.com/sponsors/ccpk1"


def test_user_chores_template_renders_with_button_card_templates() -> None:
    """User chores template renders as full dashboard with root templates."""
    template_str = _read_template("user-chores-standard-v1.yaml")
    chore_engine_context = _read_template("shared/chore_engine/context_v1.yaml")
    chore_engine_prepare_groups = _read_template(
        "shared/chore_engine/prepare_groups_v1.yaml"
    )
    chore_engine_header = _read_template("shared/chore_engine/header_v1.yaml")
    chore_engine_settings = _read_template("shared/chore_engine/settings_panel_v1.yaml")
    chore_engine_group_render = _read_template(
        "shared/chore_engine/group_render_v1.yaml"
    )
    standard_row_template_str = _read_template(
        "shared/button_card_template_chore_row_v1.yaml"
    )
    kids_row_template_str = _read_template(
        "shared/button_card_template_chore_row_kids_v1.yaml"
    )
    template_str = dh.compile_prepared_template_assets(
        {
            "templates/user-chores-standard-v1.yaml": template_str,
            "templates/shared/chore_engine/context_v1.yaml": chore_engine_context,
            "templates/shared/chore_engine/prepare_groups_v1.yaml": (
                chore_engine_prepare_groups
            ),
            "templates/shared/chore_engine/header_v1.yaml": chore_engine_header,
            "templates/shared/chore_engine/settings_panel_v1.yaml": (
                chore_engine_settings
            ),
            "templates/shared/chore_engine/group_render_v1.yaml": (
                chore_engine_group_render
            ),
            "templates/shared/button_card_template_chore_row_v1.yaml": (
                standard_row_template_str
            ),
            "templates/shared/button_card_template_chore_row_kids_v1.yaml": (
                kids_row_template_str
            ),
        }
    )["templates/user-chores-standard-v1.yaml"]
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-chores-standard-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe"
    assert rendered["views"][0]["path"] == "zoe"
    assert isinstance(rendered["views"][0].get("sections"), list)
    assert isinstance(rendered.get("button_card_templates"), dict)
    assert "chore_row_v1" in rendered["button_card_templates"]
    assert "chore_row_kids_v1" in rendered["button_card_templates"]


def test_user_chores_template_contains_ui_control_contract() -> None:
    """User chores template should reference the reviewed UI control contract."""
    template_str = _read_template("user-chores-standard-v1.yaml")

    assert "template_shared.chore_engine/context_v1" in template_str
    assert "template_shared.chore_engine/prepare_groups_v1" in template_str
    assert "template_shared.chore_engine/header_v1" in template_str
    assert "template_shared.chore_engine/settings_panel_v1" in template_str
    assert "template_shared.chore_engine/group_render_v1" in template_str
    assert "pref_ui_control_key_root = 'chores'" in template_str


def test_shared_chore_engine_fragment_contains_ui_control_contract() -> None:
    """Shared chores engine fragment should reference the reviewed UI control contract."""
    template_str = _read_template("shared/chore_engine/context_v1.yaml")

    assert "state_attr(dashboard_helper, 'ui_control')" in template_str
    assert "ui_control_key_root = pref_ui_control_key_root" in template_str
    assert "'/header_collapse'" in template_str
    assert "'/row_variant'" in template_str
    assert "'/exclude_completed'" in template_str
    assert "'/exclude_blocked'" in template_str
    assert "'/sort_within_groups'" in template_str


def test_user_gamification_premier_template_renders_with_button_card_templates() -> (
    None
):
    """Gamification Premier template renders as full dashboard with root templates."""
    template_str = _read_template("user-gamification-premier-v1.yaml")
    chore_engine_context = _read_template("shared/chore_engine/context_v1.yaml")
    chore_engine_prepare_groups = _read_template(
        "shared/chore_engine/prepare_groups_v1.yaml"
    )
    chore_engine_header = _read_template("shared/chore_engine/header_v1.yaml")
    chore_engine_settings = _read_template("shared/chore_engine/settings_panel_v1.yaml")
    chore_engine_group_render = _read_template(
        "shared/chore_engine/group_render_v1.yaml"
    )
    standard_row_template_str = _read_template(
        "shared/button_card_template_chore_row_v1.yaml"
    )
    kids_row_template_str = _read_template(
        "shared/button_card_template_chore_row_kids_v1.yaml"
    )
    template_str = dh.compile_prepared_template_assets(
        {
            "templates/user-gamification-premier-v1.yaml": template_str,
            "templates/shared/chore_engine/context_v1.yaml": chore_engine_context,
            "templates/shared/chore_engine/prepare_groups_v1.yaml": (
                chore_engine_prepare_groups
            ),
            "templates/shared/chore_engine/header_v1.yaml": chore_engine_header,
            "templates/shared/chore_engine/settings_panel_v1.yaml": (
                chore_engine_settings
            ),
            "templates/shared/chore_engine/group_render_v1.yaml": (
                chore_engine_group_render
            ),
            "templates/shared/button_card_template_chore_row_v1.yaml": (
                standard_row_template_str
            ),
            "templates/shared/button_card_template_chore_row_kids_v1.yaml": (
                kids_row_template_str
            ),
        }
    )["templates/user-gamification-premier-v1.yaml"]
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-gamification-premier-v1",
        release_ref="0.0.1-beta.4",
        generated_at="2026-03-06T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe"
    assert rendered["views"][0]["path"] == "zoe"
    assert isinstance(rendered["views"][0].get("sections"), list)
    assert isinstance(rendered.get("button_card_templates"), dict)
    assert "chore_row_v1" in rendered["button_card_templates"]
    assert "chore_row_kids_v1" in rendered["button_card_templates"]


def test_user_gamification_premier_template_contains_ui_control_contract() -> None:
    """Gamification Premier template should reference the reviewed UI control contract."""
    template_str = _read_template("user-gamification-premier-v1.yaml")

    assert f"{const.DOMAIN}.{const.SERVICE_MANAGE_UI_CONTROL}" in _read_template(
        "shared/chore_engine/settings_panel_v1.yaml"
    )
    assert "ui_control_key_root = 'gamification/rewards'" in template_str
    assert "template_shared.chore_engine/context_v1" in template_str
    assert "template_shared.chore_engine/prepare_groups_v1" in template_str
    assert "template_shared.chore_engine/header_v1" in template_str
    assert "template_shared.chore_engine/settings_panel_v1" in template_str
    assert "template_shared.chore_engine/group_render_v1" in template_str
    assert "pref_ui_control_key_root = 'gamification/chores'" in template_str
