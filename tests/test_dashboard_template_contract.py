"""Minimal dashboard template marker contract tests."""

from __future__ import annotations

from pathlib import Path

TEMPLATES_ROOT = Path("custom_components/choreops/dashboards/templates")


def _read_template(name: str) -> str:
    """Read a vendored dashboard template file."""
    return (TEMPLATES_ROOT / name).read_text(encoding="utf-8")


def test_user_templates_include_required_snippet_markers() -> None:
    """User templates include canonical user snippet markers."""
    required_markers = [
        "template_snippets.meta_stamp",
        "template_snippets.user_override_helper",
        "template_snippets.user_setup",
        "template_snippets.user_validation",
    ]

    for template_name in ("user-gamification-v1.yaml", "user-minimal-v1.yaml"):
        content = _read_template(template_name)
        for marker in required_markers:
            assert marker in content


def test_admin_templates_include_required_snippet_markers() -> None:
    """Admin templates include canonical admin snippet markers."""
    shared_required_markers = [
        "template_snippets.meta_stamp",
        "template_snippets.user_override_helper",
        "template_snippets.admin_setup_shared",
        "template_snippets.admin_validation_missing_selector",
        "template_snippets.admin_validation_invalid_selection",
    ]
    peruser_required_markers = [
        "template_snippets.meta_stamp",
        "template_snippets.user_override_helper",
        "template_snippets.admin_setup_peruser",
        "template_snippets.admin_validation_missing_selector",
        "template_snippets.admin_validation_invalid_selection",
    ]

    shared_content = _read_template("admin-shared-v1.yaml")
    peruser_content = _read_template("admin-peruser-v1.yaml")

    for marker in shared_required_markers:
        assert marker in shared_content

    for marker in peruser_required_markers:
        assert marker in peruser_content


def test_templates_keep_card_header_and_section_markers() -> None:
    """Templates preserve required card-header and numbered-section comments."""
    for template_name in (
        "user-gamification-v1.yaml",
        "user-minimal-v1.yaml",
        "admin-shared-v1.yaml",
        "admin-peruser-v1.yaml",
    ):
        content = _read_template(template_name)
        assert "{#-- =====" in content
        assert "CARD ===== --#}" in content
        assert "{#-- 1. " in content


def test_user_chores_template_uses_button_card_template_contract() -> None:
    """User chores template defines and uses a named button-card row template."""
    content = _read_template("user-chores-v1.yaml")

    assert "button_card_templates" in content
    assert "choreops_chore_row_v1" in content
    assert "'template': 'choreops_chore_row_v1'" in content
    assert "template_shared.chore_row_user_chores_v1" not in content

    legacy_row_helper = TEMPLATES_ROOT / "shared" / "chore_row_user_chores_v1.yaml"
    assert not legacy_row_helper.exists()
