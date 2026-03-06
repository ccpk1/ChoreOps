"""Minimal render smoke tests for dashboard templates."""

from __future__ import annotations

from pathlib import Path

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
    template_str = _read_template("user-minimal-v1.yaml")
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-minimal-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe Chores"
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
    template_str = _read_template("user-chores-v1.yaml")
    shared_template_str = _read_template(
        "shared/button_card_template_user_chores_row_v1.yaml"
    )
    template_str = dh.compile_prepared_template_assets(
        {
            "templates/user-chores-v1.yaml": template_str,
            "templates/shared/button_card_template_user_chores_row_v1.yaml": (
                shared_template_str
            ),
        }
    )["templates/user-chores-v1.yaml"]
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-chores-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe Chores"
    assert rendered["views"][0]["path"] == "zoe"
    assert isinstance(rendered["views"][0].get("sections"), list)
    assert isinstance(rendered.get("button_card_templates"), dict)
    assert "choreops_chore_row_v1" in rendered["button_card_templates"]


def test_user_game_full_template_renders_with_button_card_templates() -> None:
    """Game full template renders as full dashboard with root templates."""
    template_str = _read_template("user-game-full-v1.yaml")
    shared_template_str = _read_template(
        "shared/button_card_template_user_chores_row_v1.yaml"
    )
    template_str = dh.compile_prepared_template_assets(
        {
            "templates/user-game-full-v1.yaml": template_str,
            "templates/shared/button_card_template_user_chores_row_v1.yaml": (
                shared_template_str
            ),
        }
    )["templates/user-game-full-v1.yaml"]
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-game-full-v1",
        release_ref="0.0.1-beta.4",
        generated_at="2026-03-06T00:00:00+00:00",
    )

    rendered = builder.render_dashboard_template(template_str, dict(context))

    assert isinstance(rendered.get("views"), list)
    assert len(rendered["views"]) == 1
    assert rendered["views"][0]["title"] == "Zoe Game Full"
    assert rendered["views"][0]["path"] == "zoe"
    assert isinstance(rendered["views"][0].get("sections"), list)
    assert isinstance(rendered.get("button_card_templates"), dict)
    assert "choreops_chore_row_v1" in rendered["button_card_templates"]
