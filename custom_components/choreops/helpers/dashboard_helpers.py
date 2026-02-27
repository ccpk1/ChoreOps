# File: helpers/dashboard_helpers.py
"""Dashboard generation helper functions for ChoreOps.

Provides context building and template rendering support for generating
Lovelace dashboards via the ChoreOps Options Flow.

All functions here require a `hass` object or interact with HA APIs.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
import voluptuous as vol

from .. import const

if TYPE_CHECKING:
    from ..coordinator import ChoreOpsDataCoordinator
    from ..type_defs import AssigneeData


DASHBOARD_CONFIGURE_SECTION_KEYS = (
    const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS,
    const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
    const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
    const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION,
)


class DashboardTemplateDefinition(TypedDict):
    """Manifest-backed dashboard template definition."""

    template_id: str
    source_path: str
    source_type: str
    source_ref: str | None
    audience: str
    lifecycle_state: str
    min_integration_version: str
    max_integration_version: str | None
    maintainer: str
    display_name: NotRequired[str]
    dependencies_required: NotRequired[list[str]]
    dependencies_recommended: NotRequired[list[str]]


_VALID_TEMPLATE_ID_RE = re.compile(r"^[a-z0-9]+-[a-z0-9-]+-v[0-9]+$")
_VALID_LIFECYCLE_STATES = frozenset({"active", "deprecated", "archived"})
_SELECTABLE_LIFECYCLE_STATES = frozenset({"active", "deprecated"})
_VALID_AUDIENCES = frozenset({"user", "approver", "mixed"})
_VALID_SOURCE_TYPES = frozenset({"vendored", "remote"})
_VALID_DEPENDENCY_ID_RE = re.compile(r"^ha-card:[a-z0-9][a-z0-9_-]*$")


def _validate_and_normalize_template_definition(
    template: dict[str, Any],
    *,
    seen_template_ids: set[str],
) -> DashboardTemplateDefinition | None:
    """Validate and normalize a single template record from manifest payload."""
    template_id = template.get("template_id")
    if not isinstance(template_id, str):
        return None
    template_id = template_id.strip()
    if not template_id or not _VALID_TEMPLATE_ID_RE.match(template_id):
        return None
    if template_id in seen_template_ids:
        return None

    source = template.get("source")
    if not isinstance(source, dict):
        return None
    source_path = source.get("path")
    source_type = source.get("type")
    source_ref = source.get("ref")
    if not isinstance(source_path, str) or not source_path.strip():
        return None
    if not isinstance(source_type, str):
        return None
    source_type = source_type.strip()
    if source_type not in _VALID_SOURCE_TYPES:
        return None
    if source_type == "remote":
        if not isinstance(source_ref, str) or not source_ref.strip():
            return None
        source_ref = source_ref.strip()
    elif source_ref is not None and not isinstance(source_ref, str):
        return None

    audience = template.get("audience")
    lifecycle_state = template.get("lifecycle_state")
    min_integration_version = template.get("min_integration_version")
    max_integration_version = template.get("max_integration_version")
    maintainer = template.get("maintainer")
    display_name = template.get("display_name", "")

    if not isinstance(audience, str):
        return None
    audience = audience.strip()
    if audience not in _VALID_AUDIENCES:
        return None

    if not isinstance(lifecycle_state, str):
        return None
    lifecycle_state = lifecycle_state.strip()
    if lifecycle_state not in _VALID_LIFECYCLE_STATES:
        return None

    if (
        not isinstance(min_integration_version, str)
        or not min_integration_version.strip()
    ):
        return None
    min_integration_version = min_integration_version.strip()

    if max_integration_version is not None:
        if (
            not isinstance(max_integration_version, str)
            or not max_integration_version.strip()
        ):
            return None
        max_integration_version = max_integration_version.strip()

    if not isinstance(maintainer, str) or not maintainer.strip():
        return None
    maintainer = maintainer.strip()

    dependencies_required: list[str] = []
    dependencies_recommended: list[str] = []
    dependencies_obj = template.get("dependencies")
    if not isinstance(dependencies_obj, dict):
        return None

    required_list = dependencies_obj.get("required")
    if not isinstance(required_list, list):
        return None
    recommended_list = dependencies_obj.get("recommended")
    if not isinstance(recommended_list, list):
        return None

    seen_required: set[str] = set()
    for dependency in required_list:
        if not isinstance(dependency, dict):
            return None
        dependency_id = dependency.get("id")
        if not isinstance(dependency_id, str):
            return None
        dependency_id = dependency_id.strip()
        if not dependency_id or not _VALID_DEPENDENCY_ID_RE.match(dependency_id):
            return None
        if dependency_id in seen_required:
            return None
        seen_required.add(dependency_id)
        dependencies_required.append(dependency_id)

    seen_recommended: set[str] = set()
    for dependency in recommended_list:
        if not isinstance(dependency, dict):
            return None
        dependency_id = dependency.get("id")
        if not isinstance(dependency_id, str):
            return None
        dependency_id = dependency_id.strip()
        if not dependency_id or not _VALID_DEPENDENCY_ID_RE.match(dependency_id):
            return None
        if dependency_id in seen_recommended:
            return None
        seen_recommended.add(dependency_id)
        dependencies_recommended.append(dependency_id)

    seen_template_ids.add(template_id)
    return DashboardTemplateDefinition(
        template_id=template_id,
        source_path=source_path.strip(),
        source_type=source_type,
        source_ref=source_ref,
        audience=audience,
        lifecycle_state=lifecycle_state,
        min_integration_version=min_integration_version,
        max_integration_version=max_integration_version,
        maintainer=maintainer,
        display_name=display_name.strip() if isinstance(display_name, str) else "",
        dependencies_required=dependencies_required,
        dependencies_recommended=dependencies_recommended,
    )


def _parse_manifest_template_definitions(
    manifest_data: dict[str, Any],
) -> tuple[DashboardTemplateDefinition, ...]:
    """Parse and validate template definitions from a manifest payload."""
    schema_version = manifest_data.get("schema_version")
    if schema_version != 1:
        return ()

    templates = manifest_data.get("templates")
    if not isinstance(templates, list):
        return ()

    definitions: list[DashboardTemplateDefinition] = []
    seen_template_ids: set[str] = set()
    for template in templates:
        if not isinstance(template, dict):
            continue
        normalized = _validate_and_normalize_template_definition(
            template,
            seen_template_ids=seen_template_ids,
        )
        if normalized is None:
            continue
        definitions.append(normalized)

    return tuple(definitions)


def _is_template_selectable(definition: DashboardTemplateDefinition) -> bool:
    """Return True when lifecycle state allows runtime selection."""
    return definition.get("lifecycle_state", "") in _SELECTABLE_LIFECYCLE_STATES


@lru_cache(maxsize=1)
def _load_manifest_template_definitions() -> tuple[DashboardTemplateDefinition, ...]:
    """Load dashboard template definitions from bundled manifest.

    Manifest is the authoritative source for template identity and file paths.
    """
    manifest_path = Path(__file__).parent.parent / const.DASHBOARD_MANIFEST_PATH
    try:
        raw_manifest = manifest_path.read_text(encoding="utf-8")
        manifest_data = json.loads(raw_manifest)
    except (OSError, json.JSONDecodeError) as err:
        const.LOGGER.warning("Unable to read dashboard manifest: %s", err)
        return ()

    return _parse_manifest_template_definitions(manifest_data)


def get_dashboard_template_definitions() -> list[DashboardTemplateDefinition]:
    """Return all manifest-defined dashboard templates."""
    return list(_load_manifest_template_definitions())


def get_dashboard_template_ids() -> list[str]:
    """Return all manifest-defined template IDs in manifest order."""
    return [
        definition["template_id"]
        for definition in _load_manifest_template_definitions()
        if _is_template_selectable(definition)
    ]


def is_admin_template_id(template_id: str) -> bool:
    """Return True when template ID is reserved for admin views."""
    return template_id.startswith(const.DASHBOARD_TEMPLATE_ID_ADMIN_PREFIX)


def get_assignee_template_ids() -> list[str]:
    """Return manifest template IDs intended for assignee views."""
    return [
        definition["template_id"]
        for definition in _load_manifest_template_definitions()
        if _is_template_selectable(definition) and definition.get("audience") == "user"
    ]


def get_admin_template_ids() -> list[str]:
    """Return manifest template IDs intended for admin views."""
    return [
        definition["template_id"]
        for definition in _load_manifest_template_definitions()
        if _is_template_selectable(definition)
        and definition.get("audience") in {"approver", "mixed"}
    ]


def merge_manifest_template_definitions(
    local_definitions: list[DashboardTemplateDefinition],
    remote_definitions: list[DashboardTemplateDefinition],
) -> list[DashboardTemplateDefinition]:
    """Merge local baseline with remote overrides by template ID.

    Merge behavior is deterministic:
    - Preserve local ordering for local templates.
    - Override local records by template_id when remote record is valid.
    - Append remote-only records sorted by template_id.
    """
    remote_by_template_id: dict[str, DashboardTemplateDefinition] = {
        definition["template_id"]: definition for definition in remote_definitions
    }

    merged: list[DashboardTemplateDefinition] = []
    local_ids: set[str] = set()
    for local_definition in local_definitions:
        template_id = local_definition["template_id"]
        local_ids.add(template_id)
        merged.append(remote_by_template_id.get(template_id, local_definition))

    remote_only = sorted(
        (
            definition
            for definition in remote_definitions
            if definition["template_id"] not in local_ids
        ),
        key=lambda definition: definition["template_id"],
    )
    merged.extend(remote_only)
    return merged


def get_dependency_ids_for_templates_from_definitions(
    template_ids: list[str],
    definitions: list[DashboardTemplateDefinition],
) -> tuple[set[str], set[str]]:
    """Return merged required/recommended dependency IDs from provided definitions."""
    definition_by_template_id = {
        definition["template_id"]: definition for definition in definitions
    }

    required: set[str] = set()
    recommended: set[str] = set()
    for template_id in template_ids:
        definition = definition_by_template_id.get(template_id)
        if definition is None:
            continue
        required.update(definition.get("dependencies_required", []))
        recommended.update(definition.get("dependencies_recommended", []))

    return required, recommended


def get_nonselectable_template_ids_from_definitions(
    template_ids: list[str],
    definitions: list[DashboardTemplateDefinition],
) -> list[str]:
    """Return selected template IDs that are not runtime-selectable by lifecycle."""
    definition_by_template_id = {
        definition["template_id"]: definition for definition in definitions
    }
    nonselectable: list[str] = []
    for template_id in template_ids:
        definition = definition_by_template_id.get(template_id)
        if definition is None:
            nonselectable.append(template_id)
            continue
        if not _is_template_selectable(definition):
            nonselectable.append(template_id)
    return sorted(set(nonselectable))


async def fetch_remote_manifest_template_definitions(
    hass: Any,
    release_ref: str,
) -> list[DashboardTemplateDefinition]:
    """Fetch and validate remote manifest template definitions for a release ref."""
    manifest_url = const.DASHBOARD_RELEASE_TEMPLATE_URL_PATTERN.format(
        owner=const.DASHBOARD_RELEASE_REPO_OWNER,
        repo=const.DASHBOARD_RELEASE_REPO_NAME,
        ref=release_ref,
        source_path="manifest.json",
    )
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            async with session.get(manifest_url) as response:
                if response.status != 200:
                    return []
                payload = await response.json(content_type=None)
    except (TimeoutError, TypeError, ValueError):
        return []

    if not isinstance(payload, dict):
        return []
    return list(_parse_manifest_template_definitions(payload))


def get_template_source_path(template_id: str) -> str | None:
    """Return manifest source path for a template ID."""
    for definition in _load_manifest_template_definitions():
        if definition["template_id"] == template_id:
            return definition["source_path"]
    return None


def get_template_dependency_ids(template_id: str) -> tuple[list[str], list[str]]:
    """Return required and recommended dependency IDs for a template."""
    for definition in _load_manifest_template_definitions():
        if definition["template_id"] != template_id:
            continue
        return (
            list(definition.get("dependencies_required", [])),
            list(definition.get("dependencies_recommended", [])),
        )
    return ([], [])


def get_dependency_ids_for_templates(
    template_ids: list[str],
) -> tuple[set[str], set[str]]:
    """Return merged required/recommended dependency IDs for selected templates."""
    required: set[str] = set()
    recommended: set[str] = set()

    for template_id in template_ids:
        template_required, template_recommended = get_template_dependency_ids(
            template_id
        )
        required.update(template_required)
        recommended.update(template_recommended)

    return required, recommended


def get_default_assignee_template_id() -> str:
    """Return default assignee template ID from manifest."""
    assignee_template_ids = get_assignee_template_ids()
    if assignee_template_ids:
        return assignee_template_ids[0]

    template_ids = get_dashboard_template_ids()
    if template_ids:
        return template_ids[0]

    return ""


def get_default_admin_template_id() -> str:
    """Return default admin template ID from manifest."""
    admin_template_ids = get_admin_template_ids()
    if admin_template_ids:
        return admin_template_ids[0]

    return get_default_assignee_template_id()


def normalize_template_id(template_id: str, *, admin_template: bool) -> str:
    """Normalize template ID to a manifest-supported value."""
    candidates = (
        get_admin_template_ids() if admin_template else get_assignee_template_ids()
    )
    if template_id in candidates:
        return template_id
    if candidates:
        return candidates[0]
    return template_id


def _humanize_template_key(style_key: str) -> str:
    """Convert template key to human-friendly title format."""
    normalized = style_key.replace("_", " ").replace("-", " ").strip()
    return normalized.title() if normalized else style_key


def _extract_template_metadata_title(style_key: str) -> str | None:
    """Return manifest display name for a template key when available."""
    for template_definition in _load_manifest_template_definitions():
        if template_definition["template_id"] != style_key:
            continue
        display_name = template_definition.get("display_name")
        if isinstance(display_name, str) and display_name:
            return display_name
        return None
    return None


def resolve_template_display_label(style_key: str) -> str:
    """Resolve template label via metadata title, humanized key, or raw key."""
    metadata_title = _extract_template_metadata_title(style_key)
    if metadata_title:
        return metadata_title

    humanized_key = _humanize_template_key(style_key)
    if humanized_key and humanized_key != style_key:
        return humanized_key

    return style_key


# ==============================================================================
# Dashboard Context TypedDicts
# ==============================================================================


class DashboardAssigneeContext(TypedDict):
    """Minimal context for an assignee in dashboard generation.

    The dashboard templates only need these two values - all other data
    (entity IDs, points, chores) is discovered at runtime via HA Jinja2
    using the `name` to find the dashboard_helper sensor.
    """

    name: str  # Exact display name (used in `{%- set name = '...' -%}`)
    slug: str  # URL-safe slug (used in `path:` only)


class DashboardUserContext(TypedDict):
    """Identity-oriented context for dashboard generation."""

    name: str
    slug: str
    user_id: str


class DashboardContext(TypedDict):
    """Full context for dashboard template rendering.

    Passed to the Python Jinja2 environment with << >> delimiters.
    For assignee dashboards, only the context key is used.
    For admin dashboard, no context is needed (fully dynamic).
    """

    assignee: DashboardAssigneeContext
    user: DashboardUserContext
    integration: dict[str, str]


# ==============================================================================
# Context Builder Functions
# ==============================================================================


def build_assignee_context(assignee_name: str) -> DashboardAssigneeContext:
    """Build minimal context for a single assignee dashboard.

    Args:
        assignee_name: The assignee's exact display name from storage.

    Returns:
        DashboardAssigneeContext with name and URL-safe slug.

    Example:
        >>> build_assignee_context("Alice")
        {"name": "Alice", "slug": "alice"}
        >>> build_assignee_context("María José")
        {"name": "María José", "slug": "maria_jose"}
    """
    return DashboardAssigneeContext(
        name=assignee_name,
        slug=slugify(assignee_name),
    )


def build_dashboard_context(
    assignee_name: str,
    *,
    assignee_id: str,
    integration_entry_id: str,
    template_profile: str | None = None,
) -> DashboardContext:
    """Build full context for dashboard template rendering.

    This is the dict passed to the Jinja2 template engine with << >> delimiters.

    Args:
        assignee_name: The assignee's exact display name from storage.
        assignee_id: Internal user ID for identity-based lookups.
        integration_entry_id: Config entry ID for instance-scoped lookups.
        template_profile: Optional template profile for future granular flows.
            Phase 2 scaffolding keeps context shape unchanged.

    Returns:
        DashboardContext ready for template rendering.

    Example:
        >>> ctx = build_dashboard_context(
        ...     "Alice",
        ...     assignee_id="abc123",
        ...     integration_entry_id="entry123",
        ... )
        >>> ctx["assignee"]["name"]
        'Alice'
        >>> ctx["assignee"]["slug"]
        'alice'
    """
    _ = template_profile

    return DashboardContext(
        assignee=build_assignee_context(assignee_name),
        user=DashboardUserContext(
            name=assignee_name,
            slug=slugify(assignee_name),
            user_id=assignee_id,
        ),
        integration={"entry_id": integration_entry_id},
    )


def resolve_assignee_template_profile(
    assignee_name: str,
    default_style: str,
    assignee_template_profiles: dict[str, str] | None = None,
) -> str:
    """Resolve template profile for an assignee with safe fallback.

    Args:
        assignee_name: Assignee display name.
        default_style: Default selected style.
        assignee_template_profiles: Optional per-assignee profile mapping.

    Returns:
        Resolved style/profile for this assignee.
    """
    if not assignee_template_profiles:
        return default_style

    resolved = assignee_template_profiles.get(assignee_name, default_style)
    return normalize_template_id(resolved, admin_template=False)


def get_all_assignee_names(coordinator: ChoreOpsDataCoordinator) -> list[str]:
    """Get list of all assignee names from coordinator.

    Args:
        coordinator: ChoreOpsDataCoordinator instance.

    Returns:
        List of assignee display names, sorted alphabetically.
    """
    assignees_data = coordinator.assignees_data
    names: list[str] = []
    for assignee_info in assignees_data.values():
        assignee_info_typed: AssigneeData = assignee_info
        name = assignee_info_typed.get(const.DATA_USER_NAME, "")
        if name:
            names.append(name)
    return sorted(names)


# ==============================================================================
# Options Flow Schema Builders
# ==============================================================================


def build_dashboard_template_profile_options() -> list[selector.SelectOptionDict]:
    """Build template profile options.

    Admin profile is excluded because it is managed by include-admin toggle.
    """
    return [
        selector.SelectOptionDict(
            value=template_id,
            label=resolve_template_display_label(template_id),
        )
        for template_id in get_assignee_template_ids()
    ]


def build_dashboard_admin_mode_options() -> list[selector.SelectOptionDict]:
    """Build admin mode options for dashboard configuration step."""
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_MODE_NONE,
            label=const.DASHBOARD_ADMIN_MODE_NONE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_MODE_GLOBAL,
            label=const.DASHBOARD_ADMIN_MODE_GLOBAL,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
            label=const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_MODE_BOTH,
            label=const.DASHBOARD_ADMIN_MODE_BOTH,
        ),
    ]


def build_dashboard_admin_template_options() -> list[selector.SelectOptionDict]:
    """Build admin template options.

    Current MVP supports a single admin template profile.
    """
    return [
        selector.SelectOptionDict(
            value=template_id,
            label=resolve_template_display_label(template_id),
        )
        for template_id in get_admin_template_ids()
    ]


def build_dashboard_admin_view_visibility_options() -> list[selector.SelectOptionDict]:
    """Build visibility options for admin views."""
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
            label=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS,
            label=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS,
        ),
    ]


def build_dashboard_release_selection_options(
    release_tags: list[str] | None,
) -> list[selector.SelectOptionDict]:
    """Build update-only template version selector options.

    The first option keeps the existing automatic newest-compatible behavior.
    Additional options allow explicitly selecting a discovered compatible tag.
    """
    options: list[selector.SelectOptionDict] = [
        selector.SelectOptionDict(
            value=const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
            label=const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
        )
    ]
    if not release_tags:
        return options

    for tag in release_tags:
        options.append(selector.SelectOptionDict(value=tag, label=tag))
    return options


def build_dashboard_assignee_options(
    coordinator: ChoreOpsDataCoordinator,
) -> list[selector.SelectOptionDict]:
    """Build assignee selection options for dashboard generator form.

    Args:
        coordinator: ChoreOpsDataCoordinator instance.

    Returns:
        List of SelectOptionDict for assignee multi-selector.
    """
    assignee_names = get_all_assignee_names(coordinator)
    return [
        selector.SelectOptionDict(value=name, label=name) for name in assignee_names
    ]


def build_dashboard_create_name_schema() -> vol.Schema:
    """Build schema for Step 1 create path (dashboard name only)."""
    return vol.Schema(
        {
            vol.Required(
                const.CFOF_DASHBOARD_INPUT_NAME,
                default=const.DASHBOARD_DEFAULT_NAME,
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )
        }
    )


def build_dashboard_configure_schema(
    coordinator: ChoreOpsDataCoordinator,
    *,
    include_release_controls: bool,
    release_tags: list[str] | None = None,
    selected_assignees_default: list[str] | None = None,
    template_profile_default: str | None = None,
    admin_mode_default: str = const.DASHBOARD_ADMIN_MODE_GLOBAL,
    admin_template_global_default: str | None = None,
    admin_template_per_assignee_default: str | None = None,
    admin_view_visibility_default: str = const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
    show_in_sidebar_default: bool = True,
    require_admin_default: bool = False,
    icon_default: str = "mdi:clipboard-list",
    include_prereleases_default: bool = (
        const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT
    ),
    release_selection_default: str = const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
) -> vol.Schema:
    """Build unified Step 2 dashboard configuration schema."""
    if template_profile_default is None:
        template_profile_default = get_default_assignee_template_id()

    if admin_template_global_default is None:
        admin_template_global_default = get_default_admin_template_id()

    if admin_template_per_assignee_default is None:
        admin_template_per_assignee_default = get_default_admin_template_id()

    template_profile_default = normalize_template_id(
        template_profile_default,
        admin_template=False,
    )
    admin_template_global_default = normalize_template_id(
        admin_template_global_default,
        admin_template=True,
    )
    admin_template_per_assignee_default = normalize_template_id(
        admin_template_per_assignee_default,
        admin_template=True,
    )

    assignee_options = build_dashboard_assignee_options(coordinator)
    assignee_names = get_all_assignee_names(coordinator)
    default_selected_assignees = selected_assignees_default or assignee_names

    assignee_view_fields: dict[vol.Marker, Any] = {
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE,
            default=template_profile_default,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_template_profile_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_PROFILE,
            )
        ),
    }

    if assignee_options:
        assignee_view_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION,
                default=default_selected_assignees,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=assignee_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ASSIGNEE_SELECTION,
            )
        )

    admin_view_fields: dict[vol.Marker, Any] = {
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_ADMIN_MODE,
            default=admin_mode_default,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_admin_mode_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_MODE,
            )
        ),
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY,
            default=admin_view_visibility_default,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_admin_view_visibility_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_VIEW_VISIBILITY,
            )
        ),
    }

    if not include_release_controls or admin_mode_default in (
        const.DASHBOARD_ADMIN_MODE_GLOBAL,
        const.DASHBOARD_ADMIN_MODE_BOTH,
    ):
        admin_view_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL,
                default=admin_template_global_default,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_admin_template_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_GLOBAL,
            )
        )

    if not include_release_controls or admin_mode_default in (
        const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
        const.DASHBOARD_ADMIN_MODE_BOTH,
    ):
        admin_view_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_ASSIGNEE,
                default=admin_template_per_assignee_default,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_admin_template_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_PER_ASSIGNEE,
            )
        )

    access_sidebar_fields: dict[vol.Marker, Any] = {
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_ICON,
            default=icon_default,
        ): selector.IconSelector(),
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN,
            default=require_admin_default,
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR,
            default=show_in_sidebar_default,
        ): selector.BooleanSelector(),
    }

    template_version_fields: dict[vol.Marker, Any] = {}
    if include_release_controls:
        template_version_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES,
                default=include_prereleases_default,
            )
        ] = selector.BooleanSelector()

        template_version_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION,
                default=release_selection_default,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_release_selection_options(release_tags),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_RELEASE_SELECTION,
            )
        )

    sectioned_schema_fields: dict[vol.Marker, Any] = {
        vol.Optional(const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS): section(
            vol.Schema(assignee_view_fields)
        ),
        vol.Optional(const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS): section(
            vol.Schema(admin_view_fields)
        ),
        vol.Optional(const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR): section(
            vol.Schema(access_sidebar_fields),
            {"collapsed": True},
        ),
    }

    if include_release_controls:
        sectioned_schema_fields[
            vol.Optional(const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION)
        ] = section(
            vol.Schema(template_version_fields),
            {"collapsed": True},
        )

    return vol.Schema(sectioned_schema_fields, extra=vol.ALLOW_EXTRA)


def normalize_dashboard_configure_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize dashboard configure payload from sectioned form fields."""
    normalized: dict[str, Any] = dict(user_input)
    for section_key in DASHBOARD_CONFIGURE_SECTION_KEYS:
        section_data = normalized.pop(section_key, None)
        if isinstance(section_data, dict):
            normalized.update(section_data)
    return normalized


# ==============================================================================
# Dashboard Discovery Functions
# ==============================================================================


def get_existing_choreops_dashboards(
    hass: Any,
) -> list[dict[str, str]]:
    """Get list of existing ChoreOps dashboards.

    Scans the lovelace dashboards collection for dashboards
    with url_path starting with cod-/kcd- (our namespace).

    Args:
        hass: Home Assistant instance.

    Returns:
        List of dicts with 'value' (url_path) and 'label' (title).
    """
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    dashboards: list[dict[str, str]] = []

    if LOVELACE_DATA not in hass.data:
        return dashboards

    lovelace_data = hass.data[LOVELACE_DATA]

    # Check dashboards dict for cod-/kcd- entries
    for url_path in lovelace_data.dashboards:
        # Skip None or non-string keys
        if not url_path or not isinstance(url_path, str):
            continue
        if url_path.startswith(
            (
                const.DASHBOARD_URL_PATH_PREFIX,
                const.DASHBOARD_LEGACY_URL_PATH_PREFIX,
            )
        ):
            # Try to get the title from the panel
            title = url_path  # Fallback
            if hasattr(lovelace_data.dashboards[url_path], "config"):
                config = lovelace_data.dashboards[url_path].config
                if config and isinstance(config, dict):
                    # Get title from views if available
                    views = config.get("views", [])
                    if views and isinstance(views, list) and len(views) > 0:
                        title = views[0].get("title", url_path)

            dashboards.append(
                {
                    "value": url_path,
                    "label": (
                        f"{title} ({url_path})" if title != url_path else url_path
                    ),
                }
            )

    return dashboards


def build_dashboard_action_schema(
    check_cards_default: bool = True,
) -> vol.Schema:
    """Build schema for dashboard action selection.

    Args:
        check_cards_default: Default value for the check cards checkbox.

    Returns:
        Voluptuous schema for action selection.
    """
    action_options = [
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_CREATE,
            label=const.DASHBOARD_ACTION_CREATE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_UPDATE,
            label=const.DASHBOARD_ACTION_UPDATE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_DELETE,
            label=const.DASHBOARD_ACTION_DELETE,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ACTION_EXIT,
            label=const.DASHBOARD_ACTION_EXIT,
        ),
    ]

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_DASHBOARD_INPUT_ACTION,
                default=const.DASHBOARD_ACTION_CREATE,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=action_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ACTION,
                )
            ),
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS,
                default=check_cards_default,
            ): selector.BooleanSelector(),
        }
    )


def build_dashboard_update_selection_schema(
    hass: Any,
) -> vol.Schema | None:
    """Build schema for selecting one existing dashboard to update."""
    dashboards = get_existing_choreops_dashboards(hass)

    if not dashboards:
        return None

    dashboard_options = [
        selector.SelectOptionDict(value=d["value"], label=d["label"])
        for d in dashboards
    ]

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=dashboard_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=False,
                    translation_key=const.TRANS_KEY_CFOF_DASHBOARD_UPDATE_SELECTION,
                )
            ),
        }
    )


async def check_custom_cards_installed(hass: Any) -> dict[str, bool]:
    """Check if required custom Lovelace cards are installed.

    Args:
        hass: Home Assistant instance.

    Returns:
        Dict mapping card type to installation status.
        Example: {"mushroom": True, "auto_entities": False, "mini_graph": True}
    """
    # Card URL patterns to detect
    card_patterns = {
        "mushroom": "mushroom",
        "auto_entities": "auto-entities",
        "mini_graph": "mini-graph-card",
        "button_card": "button-card",
    }

    # Initialize all as not installed
    installed = dict.fromkeys(card_patterns, False)

    # Try to check lovelace resources
    try:
        resource_urls = _get_lovelace_resource_urls(hass)
        const.LOGGER.debug(
            "Checking %d lovelace resources for custom cards", len(resource_urls)
        )

        for card_type, pattern in card_patterns.items():
            aliases = _card_pattern_aliases(pattern)
            found_in_resources = any(
                alias in resource_url
                for resource_url in resource_urls
                for alias in aliases
            )
            if found_in_resources:
                installed[card_type] = True
                continue

            installed[card_type] = await _is_card_present_in_filesystem(hass, aliases)

    except (AttributeError, KeyError, TypeError) as ex:
        const.LOGGER.warning("Unable to check custom card installation: %s", ex)

    const.LOGGER.debug("Custom card status: %s", installed)
    return installed


def _get_lovelace_resource_urls(hass: Any) -> list[str]:
    """Return lowercase Lovelace resource URLs from Home Assistant runtime."""
    lovelace_resources = hass.data.get("lovelace_resources")
    if lovelace_resources is None:
        lovelace_resources = hass.data.get("lovelace")

    if lovelace_resources is None:
        const.LOGGER.debug("No lovelace data found in hass.data")
        return []

    resources: list[Any] = []
    if hasattr(lovelace_resources, "resources"):
        resources_obj = lovelace_resources.resources
        if hasattr(resources_obj, "async_items"):
            resources = list(resources_obj.async_items())
        elif hasattr(resources_obj, "items"):
            resources = list(resources_obj.items())
    elif hasattr(lovelace_resources, "async_items"):
        resources = list(lovelace_resources.async_items())
    elif hasattr(lovelace_resources, "items"):
        resources = list(lovelace_resources.items())

    resource_urls: list[str] = []
    for resource in resources:
        if isinstance(resource, dict):
            resource_urls.append(str(resource.get("url", "")).lower())
        elif hasattr(resource, "url"):
            resource_urls.append(str(resource.url).lower())

    return resource_urls


def _dependency_aliases(dependency_id: str) -> set[str]:
    """Return resource URL aliases that can satisfy a dependency ID."""
    normalized_id = dependency_id.lower()
    if not normalized_id.startswith("ha-card:"):
        return set()

    package_name = normalized_id.split(":", 1)[1]
    aliases = {package_name}
    if package_name.startswith("mushroom-"):
        aliases.add("mushroom")
    return aliases


def _card_pattern_aliases(pattern: str) -> set[str]:
    """Return normalized aliases for card pattern matching."""
    aliases = {pattern.lower()}
    aliases.add(pattern.replace("_", "-").lower())
    aliases.add(pattern.replace("-", "_").lower())
    if pattern.endswith("-card"):
        aliases.add(pattern[: -len("-card")].lower())
    return aliases


def _filesystem_has_card_alias(community_path: Path, aliases: set[str]) -> bool:
    """Return True if any alias appears under www/community."""
    if not community_path.exists() or not community_path.is_dir():
        return False

    lowered_aliases = {alias.lower() for alias in aliases if alias}
    if not lowered_aliases:
        return False

    for path in community_path.rglob("*"):
        candidate = str(path.relative_to(community_path)).lower()
        if any(alias in candidate for alias in lowered_aliases):
            return True

    return False


async def _is_card_present_in_filesystem(hass: Any, aliases: set[str]) -> bool:
    """Check card presence via filesystem fallback for YAML-mode installs."""
    community_path = Path(hass.config.path("www/community"))
    return await hass.async_add_executor_job(
        _filesystem_has_card_alias,
        community_path,
        aliases,
    )


async def check_dashboard_dependency_ids_installed(
    hass: Any,
    dependency_ids: set[str],
) -> dict[str, bool]:
    """Return installation status for dashboard manifest dependency IDs."""
    installed: dict[str, bool] = {}
    if not dependency_ids:
        return installed

    try:
        resource_urls = _get_lovelace_resource_urls(hass)
        for dependency_id in sorted(dependency_ids):
            aliases = _dependency_aliases(dependency_id)
            if not aliases:
                installed[dependency_id] = False
                continue

            found_in_resources = any(
                alias in resource_url
                for resource_url in resource_urls
                for alias in aliases
            )
            if found_in_resources:
                installed[dependency_id] = True
                continue

            installed[dependency_id] = await _is_card_present_in_filesystem(
                hass,
                aliases,
            )
    except (AttributeError, KeyError, TypeError) as ex:
        const.LOGGER.warning("Unable to check dashboard dependencies: %s", ex)
        for dependency_id in dependency_ids:
            installed[dependency_id] = False

    return installed
