"""Minimal dashboard context contract tests."""

from __future__ import annotations

from pathlib import Path

from custom_components.choreops import const
from custom_components.choreops.helpers import dashboard_helpers as dh


def test_build_dashboard_context_includes_meta_and_snippets() -> None:
    """Dashboard context includes required metadata and snippet keys."""
    context = dh.build_dashboard_context(
        "Zoe",
        assignee_id="user-123",
        integration_entry_id="entry-123",
        template_profile="user-chores-standard-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    assert (
        context[const.DASHBOARD_CONTEXT_KEY_META][
            const.DASHBOARD_PROVENANCE_KEY_TEMPLATE_ID
        ]
        == "user-chores-standard-v1"
    )
    assert (
        context[const.DASHBOARD_CONTEXT_KEY_META][
            const.DASHBOARD_PROVENANCE_KEY_GENERATED_AT
        ]
        == "2026-03-02T00:00:00+00:00"
    )

    snippets = context[const.DASHBOARD_CONTEXT_KEY_SNIPPETS]
    assert const.DASHBOARD_SNIPPET_KEY_USER_SETUP in snippets
    assert const.DASHBOARD_SNIPPET_KEY_USER_VALIDATION in snippets
    assert const.DASHBOARD_SNIPPET_KEY_META_STAMP in snippets


def test_build_admin_dashboard_context_includes_meta_and_snippets() -> None:
    """Admin context includes required metadata and admin snippet keys."""
    context = dh.build_admin_dashboard_context(
        integration_entry_id="entry-123",
        template_profile="admin-shared-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    assert (
        context[const.DASHBOARD_CONTEXT_KEY_META][
            const.DASHBOARD_PROVENANCE_KEY_TEMPLATE_ID
        ]
        == "admin-shared-v1"
    )

    snippets = context[const.DASHBOARD_CONTEXT_KEY_SNIPPETS]
    assert const.DASHBOARD_SNIPPET_KEY_ADMIN_SETUP_SHARED in snippets
    assert const.DASHBOARD_SNIPPET_KEY_ADMIN_VALIDATION_MISSING_SELECTOR in snippets
    assert const.DASHBOARD_SNIPPET_KEY_META_STAMP in snippets

    admin_setup = snippets[const.DASHBOARD_SNIPPET_KEY_ADMIN_SETUP_SHARED]
    assert "shared_admin_helper_eid" in admin_setup
    assert (
        "shared_admin_ui = state_attr(shared_admin_translation_sensor_eid, 'ui_translations')"
        in admin_setup
    )
    assert "user_dashboard_helpers" in admin_setup
    assert "helper_sensor_entities = helper_entity_ids.values | expand" in admin_setup
    assert "summary_helper = helper_sensor_entities[0].entity_id" in admin_setup
    assert (
        "selected_user_id = state_attr(selected_dashboard_helper, 'user_id')"
        in admin_setup
    )
    assert "ui_root = namespace(" in admin_setup
    assert "shared_admin=shared_admin_ui_control" in admin_setup
    assert "selected_user=selected_user_ui_control" in admin_setup


def test_build_admin_peruser_dashboard_context_uses_shared_admin_translation() -> None:
    """Per-user admin context resolves shared-admin translations from system helper."""
    context = dh.build_admin_dashboard_context(
        integration_entry_id="entry-123",
        template_profile="admin-peruser-v1",
        release_ref="0.0.1-beta.3",
        generated_at="2026-03-02T00:00:00+00:00",
    )

    admin_setup = context[const.DASHBOARD_CONTEXT_KEY_SNIPPETS][
        const.DASHBOARD_SNIPPET_KEY_ADMIN_SETUP_PERUSER
    ]
    assert "shared_admin_helper_eid" in admin_setup
    assert "shared_admin_translation_sensor_eid" in admin_setup
    assert (
        "shared_admin_ui = state_attr(shared_admin_translation_sensor_eid, 'ui_translations')"
        in admin_setup
    )


def test_admin_templates_do_not_override_language_with_selected_user_translation() -> (
    None
):
    """Admin templates keep Ops Center language on the shared-admin sensor."""
    templates_root = (
        Path(__file__).resolve().parents[1]
        / "custom_components/choreops/dashboards/templates"
    )

    for template_name in ("admin-shared-v1.yaml", "admin-peruser-v1.yaml"):
        content = (templates_root / template_name).read_text(encoding="utf-8")
        assert (
            "state_attr(selected_translation_sensor, 'ui_translations')" not in content
        )
        assert "state_attr(translation_sensor, 'ui_translations')" not in content
        assert "helper_ui.get(" not in content
