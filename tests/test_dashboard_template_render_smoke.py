"""Minimal render smoke tests for dashboard templates."""

from __future__ import annotations

from pathlib import Path

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
    assert rendered["views"][0]["title"] == "ChoreOps Admin"
    assert rendered["views"][0]["path"] == "admin"
    assert isinstance(rendered["views"][0].get("sections"), list)


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
