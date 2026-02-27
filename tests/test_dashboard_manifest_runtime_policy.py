"""Runtime policy tests for dashboard manifest merge and lifecycle behavior."""

from __future__ import annotations

from custom_components.choreops.helpers import dashboard_helpers as dh


def _definition(
    template_id: str,
    *,
    audience: str = "user",
    lifecycle_state: str = "active",
    required: list[str] | None = None,
) -> dh.DashboardTemplateDefinition:
    """Build a minimal valid dashboard template definition for tests."""
    return dh.DashboardTemplateDefinition(
        template_id=template_id,
        source_path=f"templates/{template_id}.yaml",
        source_type="vendored",
        source_ref=None,
        audience=audience,
        lifecycle_state=lifecycle_state,
        min_integration_version="0.5.0",
        max_integration_version=None,
        maintainer="ccpk1",
        display_name=template_id,
        dependencies_required=required or [],
        dependencies_recommended=[],
    )


def test_merge_manifest_template_definitions_is_deterministic() -> None:
    """Merge keeps local order, applies overrides, and appends remote-only IDs sorted."""
    local = [
        _definition("user-minimal-v1", required=["ha-card:auto-entities"]),
        _definition("admin-shared-v1", audience="approver"),
    ]
    remote = [
        _definition("user-minimal-v1", required=["ha-card:mushroom-template-card"]),
        _definition("user-gamification-v1"),
    ]

    merged = dh.merge_manifest_template_definitions(local, remote)

    assert [definition["template_id"] for definition in merged] == [
        "user-minimal-v1",
        "admin-shared-v1",
        "user-gamification-v1",
    ]
    assert merged[0]["dependencies_required"] == ["ha-card:mushroom-template-card"]


def test_nonselectable_template_ids_include_archived_and_unknown() -> None:
    """Archived and missing templates are treated as non-selectable."""
    definitions = [
        _definition("user-minimal-v1", lifecycle_state="active"),
        _definition(
            "admin-peruser-v1", audience="approver", lifecycle_state="archived"
        ),
    ]

    nonselectable = dh.get_nonselectable_template_ids_from_definitions(
        ["user-minimal-v1", "admin-peruser-v1", "unknown-template-v1"],
        definitions,
    )

    assert nonselectable == ["admin-peruser-v1", "unknown-template-v1"]


def test_parse_manifest_template_definitions_skips_invalid_remote_records() -> None:
    """Invalid/duplicate records are ignored when parsing remote manifest payloads."""
    payload = {
        "schema_version": 1,
        "templates": [
            {
                "template_id": "user-minimal-v1",
                "display_name": "Minimal",
                "audience": "user",
                "category": "minimal",
                "lifecycle_state": "active",
                "min_integration_version": "0.5.0",
                "maintainer": "ccpk1",
                "source": {
                    "type": "vendored",
                    "path": "templates/user-minimal-v1.yaml",
                },
                "dependencies": {
                    "required": [{"id": "ha-card:auto-entities"}],
                    "recommended": [],
                },
            },
            {
                "template_id": "user-minimal-v1",
                "display_name": "Duplicate",
                "audience": "user",
                "category": "minimal",
                "lifecycle_state": "active",
                "min_integration_version": "0.5.0",
                "maintainer": "ccpk1",
                "source": {
                    "type": "vendored",
                    "path": "templates/user-minimal-v1.yaml",
                },
                "dependencies": {
                    "required": [{"id": "ha-card:auto-entities"}],
                    "recommended": [],
                },
            },
            {
                "template_id": "bad-template-id",
                "display_name": "Invalid",
                "audience": "user",
                "category": "minimal",
                "lifecycle_state": "active",
                "min_integration_version": "0.5.0",
                "maintainer": "ccpk1",
                "source": {"type": "vendored", "path": "templates/invalid.yaml"},
                "dependencies": {
                    "required": [{"id": "bad-prefix:auto-entities"}],
                    "recommended": [],
                },
            },
        ],
    }

    definitions = dh._parse_manifest_template_definitions(payload)
    assert [definition["template_id"] for definition in definitions] == [
        "user-minimal-v1"
    ]
