"""Contract tests for dashboard manifest dependency declarations."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from custom_components.choreops.helpers import dashboard_helpers as dh

VALID_TEMPLATE_ID_RE = re.compile(r"^[a-z0-9]+-[a-z0-9-]+-v[0-9]+$")
VALID_LIFECYCLE_STATES = {"active", "deprecated", "archived"}
VALID_AUDIENCES = {"user", "approver", "mixed"}
VALID_SOURCE_TYPES = {"vendored", "remote"}
VALID_SHARED_FRAGMENT_ID_RE = re.compile(r"^[a-z0-9_][a-z0-9_./-]*$")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dashboard_manifest() -> dict[str, Any]:
    manifest_path = (
        _project_root()
        / "custom_components/choreops/dashboards/dashboard_registry.json"
    )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _extract_custom_cards(template_path: Path) -> set[str]:
    content = template_path.read_text(encoding="utf-8")
    return set(re.findall(r"custom:([a-zA-Z0-9_-]+)", content))


def test_templates_define_dependencies_required_and_recommended() -> None:
    """Each template must declare required and recommended dependency lists."""
    manifest = _load_dashboard_manifest()
    templates = manifest.get("templates")

    assert isinstance(templates, list)
    assert templates

    for template in templates:
        assert isinstance(template, dict)
        template_id = template.get("template_id")
        assert isinstance(template_id, str) and template_id

        dependencies = template.get("dependencies")
        assert isinstance(dependencies, dict), (
            f"Template '{template_id}' must define a dependencies object"
        )

        required = dependencies.get("required")
        recommended = dependencies.get("recommended")

        assert isinstance(required, list), (
            f"Template '{template_id}' dependencies.required must be a list"
        )
        assert isinstance(recommended, list), (
            f"Template '{template_id}' dependencies.recommended must be a list"
        )

        for dependency in [*required, *recommended]:
            assert isinstance(dependency, dict)
            dependency_id = dependency.get("id")
            assert isinstance(dependency_id, str) and dependency_id.startswith(
                "ha-card:"
            ), f"Template '{template_id}' dependency id must use 'ha-card:' prefix"


def test_manifest_templates_include_required_runtime_contract_fields() -> None:
    """Template records must provide required v1 manifest/runtime contract fields."""
    manifest = _load_dashboard_manifest()
    templates = manifest.get("templates")

    assert manifest.get("schema_version") == 1
    assert isinstance(templates, list)
    assert templates

    seen_template_ids: set[str] = set()
    for template in templates:
        assert isinstance(template, dict)

        template_id = template.get("template_id")
        assert isinstance(template_id, str) and template_id
        assert VALID_TEMPLATE_ID_RE.match(template_id)
        assert template_id not in seen_template_ids
        seen_template_ids.add(template_id)

        audience = template.get("audience")
        assert isinstance(audience, str)
        assert audience in VALID_AUDIENCES

        lifecycle_state = template.get("lifecycle_state")
        assert isinstance(lifecycle_state, str)
        assert lifecycle_state in VALID_LIFECYCLE_STATES

        min_integration_version = template.get("min_integration_version")
        assert isinstance(min_integration_version, str) and min_integration_version

        maintainer = template.get("maintainer")
        assert isinstance(maintainer, str) and maintainer

        source = template.get("source")
        assert isinstance(source, dict)
        source_type = source.get("type")
        source_path = source.get("path")
        source_ref = source.get("ref")
        assert isinstance(source_type, str)
        assert source_type in VALID_SOURCE_TYPES
        assert isinstance(source_path, str) and source_path

        if source_type == "remote":
            assert isinstance(source_ref, str) and source_ref


def test_manifest_required_dependencies_cover_custom_cards_in_templates() -> None:
    """Manifest required dependencies must include every custom card used in YAML."""
    manifest = _load_dashboard_manifest()
    templates = manifest.get("templates")

    assert isinstance(templates, list)

    for template in templates:
        assert isinstance(template, dict)
        template_id = template.get("template_id")
        source = template.get("source")
        dependencies = template.get("dependencies")

        assert isinstance(template_id, str)
        assert isinstance(source, dict)
        assert isinstance(dependencies, dict)

        source_path = source.get("path")
        assert isinstance(source_path, str)

        template_file = (
            _project_root() / "custom_components/choreops/dashboards" / source_path
        )
        custom_cards_in_template = _extract_custom_cards(template_file)

        required = dependencies.get("required")
        assert isinstance(required, list)
        declared_required_ids = {
            dependency.get("id")
            for dependency in required
            if isinstance(dependency, dict) and isinstance(dependency.get("id"), str)
        }

        expected_ids = {f"ha-card:{card}" for card in custom_cards_in_template}

        missing = sorted(expected_ids - declared_required_ids)
        assert not missing, (
            f"Template '{template_id}' missing required dependency declarations: {missing}"
        )


def test_manifest_shared_contract_fields_are_valid_when_present() -> None:
    """Shared template contract fields are optional and validated when present."""
    manifest = _load_dashboard_manifest()
    templates = manifest.get("templates")

    assert isinstance(templates, list)
    assert templates

    for template in templates:
        assert isinstance(template, dict)
        template_id = template.get("template_id")
        assert isinstance(template_id, str) and template_id

        has_shared_contract = any(
            field in template
            for field in (
                "shared_contract_version",
                "shared_fragments_required",
                "shared_fragments_optional",
            )
        )
        if not has_shared_contract:
            continue

        assert template.get("shared_contract_version") == 1

        required_fragments = template.get("shared_fragments_required")
        optional_fragments = template.get("shared_fragments_optional", [])
        assert isinstance(required_fragments, list)
        assert isinstance(optional_fragments, list)

        required_seen: set[str] = set()
        for fragment_id in required_fragments:
            assert isinstance(fragment_id, str) and fragment_id
            assert VALID_SHARED_FRAGMENT_ID_RE.match(fragment_id)
            assert fragment_id not in required_seen
            required_seen.add(fragment_id)

        optional_seen: set[str] = set()
        for fragment_id in optional_fragments:
            assert isinstance(fragment_id, str) and fragment_id
            assert VALID_SHARED_FRAGMENT_ID_RE.match(fragment_id)
            assert fragment_id not in optional_seen
            assert fragment_id not in required_seen
            optional_seen.add(fragment_id)


def test_manifest_parser_allows_legacy_templates_without_shared_contract_fields() -> (
    None
):
    """Parser keeps backward compatibility when shared contract fields are omitted."""
    manifest = _load_dashboard_manifest()
    templates = manifest.get("templates")
    assert isinstance(templates, list)

    legacy_template = next(
        (
            template
            for template in templates
            if isinstance(template, dict)
            and "shared_contract_version" not in template
            and "shared_fragments_required" not in template
            and "shared_fragments_optional" not in template
        ),
        None,
    )
    assert isinstance(legacy_template, dict)

    normalized = dh._validate_and_normalize_template_definition(
        legacy_template,
        seen_template_ids=set(),
    )
    assert normalized is not None
    assert "shared_contract_version" not in normalized
    assert "shared_fragments_required" not in normalized
    assert "shared_fragments_optional" not in normalized


def test_manifest_parser_rejects_invalid_shared_contract_shapes() -> None:
    """Parser rejects invalid shared contract field combinations."""
    manifest = _load_dashboard_manifest()
    templates = manifest.get("templates")
    assert isinstance(templates, list)

    base_template = next(
        template
        for template in templates
        if isinstance(template, dict)
        and template.get("template_id") == "user-chores-v1"
    )

    missing_version_template = dict(base_template)
    missing_version_template.pop("shared_contract_version", None)
    assert (
        dh._validate_and_normalize_template_definition(
            missing_version_template,
            seen_template_ids=set(),
        )
        is None
    )

    invalid_fragment_id_template = dict(base_template)
    invalid_fragment_id_template["shared_fragments_required"] = ["Bad Fragment"]
    assert (
        dh._validate_and_normalize_template_definition(
            invalid_fragment_id_template,
            seen_template_ids=set(),
        )
        is None
    )

    overlapping_fragment_ids_template = dict(base_template)
    overlapping_fragment_ids_template["shared_fragments_required"] = [
        "rows/chore/action_v1"
    ]
    overlapping_fragment_ids_template["shared_fragments_optional"] = [
        "rows/chore/action_v1"
    ]
    assert (
        dh._validate_and_normalize_template_definition(
            overlapping_fragment_ids_template,
            seen_template_ids=set(),
        )
        is None
    )
