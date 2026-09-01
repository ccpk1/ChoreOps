"""Contract tests for dashboard recurring-filter grouping (issue #272)."""

from __future__ import annotations

from pathlib import Path
import re

TEMPLATES_ROOT = Path("custom_components/choreops/dashboards/templates")
PREFERENCES_ROOT = Path("custom_components/choreops/dashboards/preferences")

# Step 5 daily-recurring filter: all daily chores in the today bucket (dated
# or dateless) are relocated when pref_include_daily_recurring_in_today is false.
DAILY_DISCRIMINATOR = (
    "chore_primary_group == 'today' and "
    "chore_recurring_frequency == 'daily' and "
    "not pref_include_daily_recurring_in_today"
)

# Removed in favor of pref_exclude_group_list: no chore can be in 'this_week'
# without a due date, so a weekly-recurring filter can never match.
REMOVED_WEEKLY_PREF = "pref_include_weekly_recurring_in_this_week"

INLINE_STEP5_TEMPLATES = (
    "user-chores-essential-v1.yaml",
    "user-chores-lite-v1.yaml",
    "user-kidschores-classic-v1.yaml",
)

# Templates whose pref coercions must use the string-default pattern.
# Jinja's default(x, true) boolean flag replaces FALSY values, so a
# user-set false would be silently reset to the default. The string
# default only substitutes for undefined inputs.
COERCION_TEMPLATES = (
    "user-chores-essential-v1.yaml",
    "user-chores-lite-v1.yaml",
    "user-kidschores-classic-v1.yaml",
    "shared/chore_engine/context_v1.yaml",
)


def _read_template(name: str) -> str:
    """Read a vendored dashboard template file."""
    return (TEMPLATES_ROOT / name).read_text(encoding="utf-8")


def test_shared_prepare_groups_gates_daily_filter_on_frequency() -> None:
    """Shared chore engine relocates daily chores from the today bucket."""
    content = _read_template("shared/chore_engine/prepare_groups_v1.yaml")

    assert DAILY_DISCRIMINATOR in content
    assert REMOVED_WEEKLY_PREF not in content


def test_inline_templates_gate_daily_filter_on_frequency() -> None:
    """Inline grouping templates relocate daily chores from the today bucket."""
    for template_name in INLINE_STEP5_TEMPLATES:
        content = _read_template(template_name)
        assert DAILY_DISCRIMINATOR in content, template_name
        assert REMOVED_WEEKLY_PREF not in content, template_name


def test_weekly_pref_removed_from_all_templates_and_defaults() -> None:
    """Weekly recurring pref is fully removed from templates and coercion."""
    for template_name in (
        "user-chores-essential-v1.yaml",
        "user-chores-lite-v1.yaml",
        "user-chores-standard-v1.yaml",
        "user-gamification-premier-v1.yaml",
        "user-kidschores-classic-v1.yaml",
        "shared/chore_engine/context_v1.yaml",
    ):
        assert REMOVED_WEEKLY_PREF not in _read_template(template_name), template_name


def test_weekly_pref_removed_from_preference_docs() -> None:
    """Preference docs drop the weekly pref and clarify daily pref scope."""
    for doc_name in (
        "user-chores-essential-v1.md",
        "user-chores-lite-v1.md",
        "user-chores-standard-v1.md",
        "user-gamification-premier-v1.md",
        "user-kidschores-classic-v1.md",
    ):
        doc_path = Path("custom_components/choreops/dashboards/preferences") / doc_name
        content = doc_path.read_text(encoding="utf-8")
        assert REMOVED_WEEKLY_PREF not in content, doc_name
        assert "recurring daily chores" in content, doc_name


def test_pref_coercions_use_string_default_pattern() -> None:
    """YAML pref coercions preserve user-set false values."""
    boolean_default = re.compile(r"pref_\w+ \| default\((?:true|false), true\)")
    for template_name in COERCION_TEMPLATES:
        content = _read_template(template_name)
        assert not boolean_default.search(content), (
            f"{template_name} uses boolean-default coercion which resets "
            "user-set false values"
        )


def test_daily_pref_coercion_preserves_false() -> None:
    """The daily pref coercion chain keeps a user-set false intact."""
    import jinja2

    env = jinja2.Environment()
    for template_name in COERCION_TEMPLATES:
        content = _read_template(template_name)
        match = re.search(
            r"set pref_include_daily_recurring_in_today = "
            r"\(pref_include_daily_recurring_in_today ([^%]+?)\) == 'true' -%}",
            content,
        )
        assert match, template_name
        chain = f"(pref_include_daily_recurring_in_today {match.group(1)}) == 'true'"
        rendered_false = env.from_string(
            "{%- set pref_include_daily_recurring_in_today = false -%}"
            f"{{%- set pref_include_daily_recurring_in_today = {chain} -%}}"
            "{{ pref_include_daily_recurring_in_today }}"
        ).render()
        assert rendered_false == "False", (
            f"{template_name} coercion resets user-set false to {rendered_false}"
        )
