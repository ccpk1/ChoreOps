# File: helpers/dashboard_helpers.py
"""Dashboard generation helper functions for ChoreOps.

Provides context building and template rendering support for generating
Lovelace dashboards via the ChoreOps Options Flow.

All functions here require a `hass` object or interact with HA APIs.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
import re
import textwrap
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict, cast

from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
import voluptuous as vol

from .. import const
from ..utils.dt_utils import dt_now_iso

if TYPE_CHECKING:
    from ..coordinator import ChoreOpsDataCoordinator
    from ..type_defs import AssigneeData


DASHBOARD_CONFIGURE_SECTION_KEYS = (
    const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS,
    const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
    const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
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
    description: NotRequired[str]
    preferences_doc_asset_path: NotRequired[str]
    dependencies_required: NotRequired[list[str]]
    dependencies_recommended: NotRequired[list[str]]
    dependencies_required_metadata: NotRequired[dict[str, DashboardDependencyMetadata]]
    dependencies_recommended_metadata: NotRequired[
        dict[str, DashboardDependencyMetadata]
    ]
    shared_contract_version: NotRequired[int]
    shared_fragments_required: NotRequired[list[str]]
    shared_fragments_optional: NotRequired[list[str]]


class DashboardDependencyMetadata(TypedDict):
    """Manifest-provided metadata for a dependency id."""

    name: NotRequired[str]
    url: NotRequired[str]


class DashboardReleaseAssets(TypedDict):
    """Prepared release assets for one selected dashboard release."""

    requested_release_selection: str
    release_ref: str
    resolution_reason: str
    execution_source: str
    strict_pin: bool
    allow_local_fallback: bool
    manifest_asset: str
    template_definitions: list[DashboardTemplateDefinition]
    template_assets: dict[str, str]
    translation_assets: dict[str, str]
    preference_assets: dict[str, str]


_VALID_TEMPLATE_ID_RE = re.compile(r"^[a-z0-9]+-[a-z0-9-]+-v[0-9]+$")
_VALID_LIFECYCLE_STATES = frozenset({"active", "deprecated", "archived"})
_SELECTABLE_LIFECYCLE_STATES = frozenset({"active", "deprecated"})
_VALID_AUDIENCES = frozenset({"user", "approver", "mixed"})
_VALID_SOURCE_TYPES = frozenset({"vendored", "remote"})
_VALID_DEPENDENCY_ID_RE = re.compile(r"^ha-card:[a-z0-9][a-z0-9_-]*$")
_VALID_SHARED_FRAGMENT_ID_RE = re.compile(r"^[a-z0-9_][a-z0-9_./-]*$")
_SHARED_TEMPLATE_MARKER_RE = re.compile(
    r"<<\s*template_shared\.([a-zA-Z0-9_./-]+)\s*>>"
)
_SHARED_TEMPLATE_MARKER_LINE_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)<<\s*template_shared\.(?P<fragment_id>[a-zA-Z0-9_./-]+)\s*>>\s*$"
)
_TEMPLATE_SHARED_PREFIX = "templates/shared/"

_manifest_template_definitions_state: dict[str, Any] = {
    "cache": (),
    "loaded": False,
    "warned": False,
}


def _shared_fragment_id_to_source_path(fragment_id: str) -> str:
    """Convert shared fragment id to source asset path."""
    return f"{_TEMPLATE_SHARED_PREFIX}{fragment_id}.yaml"


def get_shared_fragment_source_paths_for_definitions(
    definitions: list[DashboardTemplateDefinition],
) -> list[str]:
    """Return deterministic source paths for required shared fragments."""
    source_paths: set[str] = set()
    for definition in definitions:
        for fragment_id in definition.get("shared_fragments_required", []):
            source_paths.add(_shared_fragment_id_to_source_path(fragment_id))
    return sorted(source_paths)


def compile_prepared_template_assets(
    template_assets: dict[str, str],
    *,
    template_definitions: list[DashboardTemplateDefinition] | None = None,
) -> dict[str, str]:
    """Validate and compose prepared template assets for runtime usage."""
    normalized_template_assets = {
        source_path: content
        for source_path, content in template_assets.items()
        if isinstance(source_path, str) and isinstance(content, str)
    }

    if template_definitions:
        for definition in template_definitions:
            source_path = definition.get("source_path")
            template_id = definition.get("template_id", "unknown")
            if not isinstance(source_path, str) or not source_path.strip():
                continue

            for fragment_id in definition.get("shared_fragments_required", []):
                shared_source_path = _shared_fragment_id_to_source_path(fragment_id)
                if shared_source_path not in normalized_template_assets:
                    raise HomeAssistantError(
                        "Prepared release payload is missing required shared "
                        f"fragment '{fragment_id}' for template '{template_id}'"
                    )

    return _compose_prepared_template_assets(normalized_template_assets)


def _compose_prepared_template_assets(
    template_assets: dict[str, str],
) -> dict[str, str]:
    """Compose shared-fragment markers for prepared template assets.

    Shared fragment source paths use `templates/shared/<fragment_id>.yaml` and are
    composed into non-shared `templates/*.yaml` outputs. Shared source assets are
    not written to runtime template folders.
    """
    fragments: dict[str, str] = {}
    composed_templates: dict[str, str] = {}

    for source_path, content in template_assets.items():
        if not isinstance(source_path, str) or not isinstance(content, str):
            continue
        if source_path.startswith(_TEMPLATE_SHARED_PREFIX) and source_path.endswith(
            ".yaml"
        ):
            fragment_id = (
                Path(source_path)
                .relative_to(Path(_TEMPLATE_SHARED_PREFIX))
                .with_suffix("")
                .as_posix()
            )
            fragments[fragment_id] = content

    def resolve_fragment(fragment_id: str, stack: tuple[str, ...]) -> str:
        if fragment_id in stack:
            cycle = " -> ".join((*stack, fragment_id))
            raise HomeAssistantError(
                f"Circular shared template fragment reference detected: {cycle}"
            )
        if fragment_id not in fragments:
            raise HomeAssistantError(f"Missing shared template fragment: {fragment_id}")

        fragment_source = fragments[fragment_id]

        def _replace_line(match: re.Match[str]) -> str:
            indent = match.group("indent")
            nested_id = match.group("fragment_id")
            resolved_nested = resolve_fragment(nested_id, (*stack, fragment_id))
            return textwrap.indent(resolved_nested, indent)

        def _replace_inline(match: re.Match[str]) -> str:
            nested_id = match.group(1)
            return resolve_fragment(nested_id, (*stack, fragment_id))

        composed_fragment = _SHARED_TEMPLATE_MARKER_LINE_RE.sub(
            _replace_line,
            fragment_source,
        )
        return _SHARED_TEMPLATE_MARKER_RE.sub(_replace_inline, composed_fragment)

    for source_path, content in template_assets.items():
        if not isinstance(source_path, str) or not isinstance(content, str):
            continue
        if not source_path.startswith("templates/"):
            continue
        if source_path.startswith(_TEMPLATE_SHARED_PREFIX):
            continue

        def _replace_root_line(match: re.Match[str]) -> str:
            indent = match.group("indent")
            fragment_id = match.group("fragment_id")
            resolved = resolve_fragment(fragment_id, ())
            return textwrap.indent(resolved, indent)

        def _replace_root_inline(match: re.Match[str]) -> str:
            fragment_id = match.group(1)
            return resolve_fragment(fragment_id, ())

        composed = _SHARED_TEMPLATE_MARKER_LINE_RE.sub(_replace_root_line, content)
        composed = _SHARED_TEMPLATE_MARKER_RE.sub(_replace_root_inline, composed)
        if _SHARED_TEMPLATE_MARKER_RE.search(composed):
            raise HomeAssistantError(
                f"Unresolved template_shared marker remains in {source_path}"
            )
        composed_templates[source_path] = composed

    return composed_templates


def reset_manifest_template_definitions_cache() -> None:
    """Reset cached dashboard manifest template definitions.

    Use this after replacing local dashboard manifest/template files so new
    runtime selections and lookups observe updated on-disk contracts.
    """
    _manifest_template_definitions_state["cache"] = ()
    _manifest_template_definitions_state["loaded"] = False
    _manifest_template_definitions_state["warned"] = False


def _resolve_dashboard_asset_target_path(
    dashboards_root: Path,
    relative_path: str,
) -> Path:
    """Resolve release asset path under dashboards root with traversal guard."""
    normalized_parts = Path(relative_path).parts
    if not normalized_parts:
        raise HomeAssistantError("Dashboard release asset path is empty")
    if any(part in ("", ".", "..") for part in normalized_parts):
        raise HomeAssistantError(
            f"Dashboard release asset path is invalid: {relative_path}"
        )

    target_path = dashboards_root.joinpath(*normalized_parts).resolve()
    dashboards_root_resolved = dashboards_root.resolve()
    if not str(target_path).startswith(str(dashboards_root_resolved)):
        raise HomeAssistantError(
            f"Dashboard release asset path escapes dashboards root: {relative_path}"
        )
    return target_path


def _replace_managed_dashboard_assets_from_release(
    prepared_assets: DashboardReleaseAssets,
    *,
    component_root: Path | None = None,
) -> None:
    """Overwrite managed local dashboard assets from prepared release payload."""
    if component_root is None:
        component_root = Path(__file__).parent.parent
    dashboards_root = component_root / Path(const.DASHBOARD_MANIFEST_PATH).parent

    manifest_asset = prepared_assets.get("manifest_asset")
    if not isinstance(manifest_asset, str) or not manifest_asset.strip():
        raise HomeAssistantError("Prepared release payload missing manifest content")

    prepared_template_assets_raw = prepared_assets.get("template_assets", {})
    if not isinstance(prepared_template_assets_raw, dict):
        prepared_template_assets_raw = {}

    prepared_template_definitions_raw = prepared_assets.get("template_definitions", [])
    prepared_template_definitions: list[DashboardTemplateDefinition] = []
    if isinstance(prepared_template_definitions_raw, list):
        for definition in prepared_template_definitions_raw:
            if isinstance(definition, dict):
                prepared_template_definitions.append(definition)

    normalized_template_assets = {
        source_path: content
        for source_path, content in prepared_template_assets_raw.items()
        if isinstance(source_path, str) and isinstance(content, str)
    }

    compile_prepared_template_assets(
        normalized_template_assets,
        template_definitions=prepared_template_definitions,
    )

    managed_asset_groups: dict[str, dict[str, str]] = {
        const.DASHBOARD_TEMPLATES_DIR: normalized_template_assets,
        const.DASHBOARD_TRANSLATIONS_DIR: prepared_assets.get("translation_assets", {}),
        const.PREFERENCES_DOCS_DIR: prepared_assets.get("preference_assets", {}),
    }

    for directory in (
        const.DASHBOARD_TEMPLATES_DIR,
        const.DASHBOARD_TRANSLATIONS_DIR,
        const.PREFERENCES_DOCS_DIR,
    ):
        target_directory = component_root / directory
        if target_directory.exists():
            for file_path in sorted(target_directory.rglob("*"), reverse=True):
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    with contextlib.suppress(OSError):
                        file_path.rmdir()
        target_directory.mkdir(parents=True, exist_ok=True)

    for expected_prefix, assets in managed_asset_groups.items():
        if not isinstance(assets, dict):
            continue
        prefix = f"{Path(expected_prefix).name}/"
        for source_path, content in assets.items():
            if not isinstance(source_path, str) or not isinstance(content, str):
                continue
            if not source_path.startswith(prefix):
                continue

            target_path = _resolve_dashboard_asset_target_path(
                dashboards_root,
                source_path,
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

    manifest_target = dashboards_root / Path(const.DASHBOARD_MANIFEST_PATH).name
    manifest_target.write_text(manifest_asset, encoding="utf-8")


async def async_apply_prepared_dashboard_release_assets(
    hass: Any,
    prepared_assets: DashboardReleaseAssets,
) -> None:
    """Persist prepared release assets as the local dashboard baseline.

    This applies selected release files to local disk so dashboard template
    rendering and dashboard translation sensors read the selected release going
    forward.
    """
    await hass.async_add_executor_job(
        _replace_managed_dashboard_assets_from_release,
        prepared_assets,
    )
    reset_manifest_template_definitions_cache()
    await async_prime_manifest_template_definitions(hass)

    from .translation_helpers import clear_translation_cache

    clear_translation_cache()


def get_local_dashboard_release_version() -> str | None:
    """Return bundled dashboard registry release_version when available."""
    manifest_path = Path(__file__).parent.parent / const.DASHBOARD_MANIFEST_PATH
    try:
        raw_manifest = manifest_path.read_text(encoding="utf-8")
        manifest_data = json.loads(raw_manifest)
    except (OSError, json.JSONDecodeError):
        return None

    release_version = manifest_data.get("release_version")
    if isinstance(release_version, str) and release_version.strip():
        return release_version.strip()
    return None


async def async_get_local_dashboard_release_version(hass: Any) -> str | None:
    """Return bundled dashboard registry release_version without blocking loop."""
    return await hass.async_add_executor_job(get_local_dashboard_release_version)


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
    description = template.get("description", "")

    preferences_doc_asset_path: str | None = None
    preferences = template.get("preferences")
    if isinstance(preferences, dict):
        raw_doc_asset_path = preferences.get("doc_asset_path")
        if isinstance(raw_doc_asset_path, str) and raw_doc_asset_path.strip():
            preferences_doc_asset_path = raw_doc_asset_path.strip()

    shared_contract_version_raw = template.get("shared_contract_version")
    shared_fragments_required_raw = template.get("shared_fragments_required")
    shared_fragments_optional_raw = template.get("shared_fragments_optional")
    has_shared_contract_fields = any(
        key in template
        for key in (
            "shared_contract_version",
            "shared_fragments_required",
            "shared_fragments_optional",
        )
    )

    shared_contract_version: int | None = None
    shared_fragments_required: list[str] = []
    shared_fragments_optional: list[str] = []

    if has_shared_contract_fields:
        if not isinstance(shared_contract_version_raw, int) or isinstance(
            shared_contract_version_raw, bool
        ):
            return None
        if shared_contract_version_raw != 1:
            return None
        shared_contract_version = shared_contract_version_raw

        if not isinstance(shared_fragments_required_raw, list):
            return None
        if shared_fragments_optional_raw is not None and not isinstance(
            shared_fragments_optional_raw, list
        ):
            return None

        for fragment_id_raw in shared_fragments_required_raw:
            if not isinstance(fragment_id_raw, str):
                return None
            fragment_id = fragment_id_raw.strip()
            if (
                not fragment_id
                or not _VALID_SHARED_FRAGMENT_ID_RE.match(fragment_id)
                or fragment_id in shared_fragments_required
            ):
                return None
            shared_fragments_required.append(fragment_id)

        for fragment_id_raw in shared_fragments_optional_raw or []:
            if not isinstance(fragment_id_raw, str):
                return None
            fragment_id = fragment_id_raw.strip()
            if (
                not fragment_id
                or not _VALID_SHARED_FRAGMENT_ID_RE.match(fragment_id)
                or fragment_id in shared_fragments_optional
                or fragment_id in shared_fragments_required
            ):
                return None
            shared_fragments_optional.append(fragment_id)

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
    dependencies_required_metadata: dict[str, DashboardDependencyMetadata] = {}
    dependencies_recommended_metadata: dict[str, DashboardDependencyMetadata] = {}
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

        dependency_name = dependency.get("name")
        if dependency_name is not None:
            if not isinstance(dependency_name, str) or not dependency_name.strip():
                return None
            dependency_name = dependency_name.strip()

        dependency_url = dependency.get("url")
        if dependency_url is not None:
            if not isinstance(dependency_url, str) or not dependency_url.strip():
                return None
            dependency_url = dependency_url.strip()
            if not dependency_url.startswith(("https://", "http://")):
                return None

        if dependency_id in seen_required:
            return None
        seen_required.add(dependency_id)
        dependencies_required.append(dependency_id)

        metadata: DashboardDependencyMetadata = {}
        if isinstance(dependency_name, str):
            metadata["name"] = dependency_name
        if isinstance(dependency_url, str):
            metadata["url"] = dependency_url
        if metadata:
            dependencies_required_metadata[dependency_id] = metadata

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

        dependency_name = dependency.get("name")
        if dependency_name is not None:
            if not isinstance(dependency_name, str) or not dependency_name.strip():
                return None
            dependency_name = dependency_name.strip()

        dependency_url = dependency.get("url")
        if dependency_url is not None:
            if not isinstance(dependency_url, str) or not dependency_url.strip():
                return None
            dependency_url = dependency_url.strip()
            if not dependency_url.startswith(("https://", "http://")):
                return None

        if dependency_id in seen_recommended:
            return None
        seen_recommended.add(dependency_id)
        dependencies_recommended.append(dependency_id)

        metadata = {}
        if isinstance(dependency_name, str):
            metadata["name"] = dependency_name
        if isinstance(dependency_url, str):
            metadata["url"] = dependency_url
        if metadata:
            dependencies_recommended_metadata[dependency_id] = metadata

    seen_template_ids.add(template_id)
    normalized_definition: DashboardTemplateDefinition = DashboardTemplateDefinition(
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
        description=description.strip() if isinstance(description, str) else "",
        dependencies_required=dependencies_required,
        dependencies_recommended=dependencies_recommended,
        dependencies_required_metadata=dependencies_required_metadata,
        dependencies_recommended_metadata=dependencies_recommended_metadata,
    )
    if preferences_doc_asset_path is not None:
        normalized_definition["preferences_doc_asset_path"] = preferences_doc_asset_path
    if shared_contract_version is not None:
        normalized_definition["shared_contract_version"] = shared_contract_version
        normalized_definition["shared_fragments_required"] = shared_fragments_required
        normalized_definition["shared_fragments_optional"] = shared_fragments_optional
    return normalized_definition


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


def _load_manifest_template_definitions() -> tuple[DashboardTemplateDefinition, ...]:
    """Load dashboard template definitions from bundled manifest.

    Manifest is the authoritative source for template identity and file paths.
    """
    if bool(_manifest_template_definitions_state["loaded"]):
        return cast(
            "tuple[DashboardTemplateDefinition, ...]",
            _manifest_template_definitions_state["cache"],
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        _manifest_template_definitions_state["cache"] = (
            _read_manifest_template_definitions_from_disk()
        )
        _manifest_template_definitions_state["loaded"] = True
        _manifest_template_definitions_state["warned"] = False
        return cast(
            "tuple[DashboardTemplateDefinition, ...]",
            _manifest_template_definitions_state["cache"],
        )

    if not bool(_manifest_template_definitions_state["warned"]):
        const.LOGGER.warning(
            "Dashboard manifest cache not loaded yet; returning empty definitions"
        )
        _manifest_template_definitions_state["warned"] = True
    return cast(
        "tuple[DashboardTemplateDefinition, ...]",
        _manifest_template_definitions_state["cache"],
    )


def _read_manifest_template_definitions_from_disk() -> tuple[
    DashboardTemplateDefinition, ...
]:
    """Read and parse bundled dashboard manifest from disk."""
    manifest_path = Path(__file__).parent.parent / const.DASHBOARD_MANIFEST_PATH
    try:
        raw_manifest = manifest_path.read_text(encoding="utf-8")
        manifest_data = json.loads(raw_manifest)
    except (OSError, json.JSONDecodeError) as err:
        const.LOGGER.warning("Unable to read dashboard manifest: %s", err)
        return ()

    return _parse_manifest_template_definitions(manifest_data)


async def async_prime_manifest_template_definitions(hass: Any) -> None:
    """Load and cache dashboard template definitions without blocking the loop."""
    if bool(_manifest_template_definitions_state["loaded"]):
        return

    _manifest_template_definitions_state["cache"] = await hass.async_add_executor_job(
        _read_manifest_template_definitions_from_disk
    )
    _manifest_template_definitions_state["loaded"] = True
    _manifest_template_definitions_state["warned"] = False


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


def get_dependency_metadata_for_templates_from_definitions(
    template_ids: list[str],
    definitions: list[DashboardTemplateDefinition],
) -> dict[str, DashboardDependencyMetadata]:
    """Return merged dependency metadata for selected template IDs."""
    definition_by_template_id = {
        definition["template_id"]: definition for definition in definitions
    }

    merged: dict[str, DashboardDependencyMetadata] = {}
    for template_id in template_ids:
        definition = definition_by_template_id.get(template_id)
        if definition is None:
            continue

        for metadata_map_key in (
            "dependencies_required_metadata",
            "dependencies_recommended_metadata",
        ):
            metadata_map = definition.get(metadata_map_key, {})
            if not isinstance(metadata_map, dict):
                continue

            for dependency_id, metadata in metadata_map.items():
                if dependency_id not in merged:
                    merged[dependency_id] = {}

                dependency_metadata = merged[dependency_id]
                if (
                    "name" not in dependency_metadata
                    and isinstance(metadata.get("name"), str)
                    and metadata["name"].strip()
                ):
                    dependency_metadata["name"] = metadata["name"].strip()

                if (
                    "url" not in dependency_metadata
                    and isinstance(metadata.get("url"), str)
                    and metadata["url"].strip()
                ):
                    dependency_metadata["url"] = metadata["url"].strip()

    return merged


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
        source_path=Path(const.DASHBOARD_MANIFEST_PATH).name,
    )
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            async with session.get(manifest_url) as response:
                if response.status != 200:
                    return []
                payload = await response.json(content_type=None)
    except (TimeoutError, TypeError, ValueError, Exception):
        return []

    if not isinstance(payload, dict):
        return []
    return list(_parse_manifest_template_definitions(payload))


async def _fetch_release_assets_by_path(
    hass: Any,
    *,
    release_ref: str,
    source_paths: list[str],
) -> dict[str, str]:
    """Fetch a list of release assets and return content keyed by source path."""
    from . import dashboard_builder as builder

    unique_paths = [path for path in sorted(set(source_paths)) if path]
    if not unique_paths:
        return {}

    tasks = [
        builder.fetch_release_asset_text(
            hass,
            release_ref=release_ref,
            source_path=source_path,
        )
        for source_path in unique_paths
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    fetched_assets: dict[str, str] = {}
    for source_path, result in zip(unique_paths, results, strict=True):
        if isinstance(result, Exception):
            raise HomeAssistantError(
                f"Unable to fetch release asset '{source_path}': {result}"
            ) from result
        if isinstance(result, BaseException):
            raise HomeAssistantError(
                f"Unable to fetch release asset '{source_path}': {result}"
            ) from result
        fetched_assets[source_path] = result

    return fetched_assets


def _read_local_dashboard_asset_text(source_path: str) -> str:
    """Read one local dashboard asset by source path."""
    component_root = Path(__file__).parent.parent
    dashboards_root = component_root / Path(const.DASHBOARD_MANIFEST_PATH).parent
    asset_path = _resolve_dashboard_asset_target_path(dashboards_root, source_path)
    return asset_path.read_text(encoding="utf-8")


async def _load_local_assets_by_path(
    hass: Any,
    *,
    source_paths: list[str],
) -> dict[str, str]:
    """Load local dashboard assets keyed by source path."""
    unique_paths = [path for path in sorted(set(source_paths)) if path]
    if not unique_paths:
        return {}

    tasks = [
        hass.async_add_executor_job(_read_local_dashboard_asset_text, source_path)
        for source_path in unique_paths
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    loaded_assets: dict[str, str] = {}
    for source_path, result in zip(unique_paths, results, strict=True):
        if isinstance(result, Exception):
            raise HomeAssistantError(
                f"Unable to load local dashboard asset '{source_path}': {result}"
            ) from result
        if isinstance(result, BaseException):
            raise HomeAssistantError(
                f"Unable to load local dashboard asset '{source_path}': {result}"
            ) from result
        loaded_assets[source_path] = result

    return loaded_assets


async def async_prepare_dashboard_release_assets(
    hass: Any,
    *,
    release_selection: str,
    include_prereleases: bool,
) -> DashboardReleaseAssets:
    """Prepare selected-release assets for dashboard flow session reuse.

    Fetches and validates remote contract assets for Step 1 submit:
    - manifest definitions
    - template source files referenced by manifest
    - dashboard translation file(s)
    - preferences docs referenced by manifest
    """
    from . import dashboard_builder as builder

    release_ref: str
    resolution_reason: str
    execution_source: str
    strict_pin = release_selection not in {
        const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED,
        const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
        const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
    }

    if release_selection == const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED:
        local_release = await async_get_local_dashboard_release_version(hass)
        if not local_release:
            raise HomeAssistantError(
                "Local dashboard registry does not expose release_version"
            )
        release_ref = local_release
        resolution_reason = "current_installed"
        execution_source = "local_bundled"
    elif release_selection in (
        const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
        const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
    ):
        resolution = await builder.resolve_dashboard_release_selection(
            hass,
            pinned_release_tag=None,
            include_prereleases=False,
        )
        selected_tag = resolution.selected_tag
        if not selected_tag:
            raise HomeAssistantError(
                "No compatible online dashboard release is currently available"
            )
        release_ref = selected_tag
        resolution_reason = resolution.reason
        execution_source = "remote_release"
    else:
        release_ref = release_selection
        resolution_reason = "explicit_release_selected"
        execution_source = "remote_release"

    if release_selection == const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED:
        template_definitions = get_dashboard_template_definitions()
    else:
        template_definitions = await fetch_remote_manifest_template_definitions(
            hass,
            release_ref,
        )
    if not template_definitions:
        raise HomeAssistantError(
            f"Dashboard registry data is unavailable for release '{release_ref}'"
        )

    template_paths = [
        definition["source_path"]
        for definition in template_definitions
        if isinstance(definition.get("source_path"), str)
    ] + get_shared_fragment_source_paths_for_definitions(template_definitions)
    if release_selection == const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED:
        template_assets = await _load_local_assets_by_path(
            hass,
            source_paths=template_paths,
        )
    else:
        template_assets = await _fetch_release_assets_by_path(
            hass,
            release_ref=release_ref,
            source_paths=template_paths,
        )

    from .translation_helpers import get_available_dashboard_languages

    available_languages = await get_available_dashboard_languages(hass)
    translation_paths = [
        f"translations/{language}{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"
        for language in available_languages
    ]
    if release_selection == const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED:
        translation_assets = await _load_local_assets_by_path(
            hass,
            source_paths=translation_paths,
        )
    else:
        translation_assets = await _fetch_release_assets_by_path(
            hass,
            release_ref=release_ref,
            source_paths=translation_paths,
        )

    preferences_paths = [
        str(preferences_doc_asset_path)
        for definition in template_definitions
        if isinstance(
            (
                preferences_doc_asset_path := definition.get(
                    "preferences_doc_asset_path"
                )
            ),
            str,
        )
        and preferences_doc_asset_path.strip()
    ]
    if release_selection == const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED:
        preference_assets = await _load_local_assets_by_path(
            hass,
            source_paths=preferences_paths,
        )
        manifest_asset = await hass.async_add_executor_job(
            _read_local_dashboard_asset_text,
            Path(const.DASHBOARD_MANIFEST_PATH).name,
        )
    else:
        preference_assets = await _fetch_release_assets_by_path(
            hass,
            release_ref=release_ref,
            source_paths=preferences_paths,
        )
        manifest_asset = await builder.fetch_release_asset_text(
            hass,
            release_ref=release_ref,
            source_path=Path(const.DASHBOARD_MANIFEST_PATH).name,
        )

    return DashboardReleaseAssets(
        requested_release_selection=release_selection,
        release_ref=release_ref,
        resolution_reason=resolution_reason,
        execution_source=execution_source,
        strict_pin=strict_pin,
        allow_local_fallback=not strict_pin,
        manifest_asset=manifest_asset,
        template_definitions=template_definitions,
        template_assets=template_assets,
        translation_assets=translation_assets,
        preference_assets=preference_assets,
    )


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
    return ""


def get_default_admin_global_template_id() -> str:
    """Return default admin template ID for shared/global admin views."""
    admin_template_ids = get_admin_template_ids()
    preferred_template_id = "admin-shared-v1"
    if preferred_template_id in admin_template_ids:
        return preferred_template_id
    return get_default_admin_template_id()


def get_default_admin_per_assignee_template_id() -> str:
    """Return default admin template ID for per-assignee admin views."""
    admin_template_ids = get_admin_template_ids()
    preferred_template_id = "admin-peruser-v1"
    if preferred_template_id in admin_template_ids:
        return preferred_template_id
    return get_default_admin_template_id()


def normalize_template_id(template_id: str, *, admin_template: bool) -> str:
    """Normalize template ID to a manifest-supported value."""
    candidates = (
        get_admin_template_ids() if admin_template else get_assignee_template_ids()
    )
    if template_id in candidates:
        return template_id
    if candidates:
        return candidates[0]
    return ""


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


class DashboardMetaContext(TypedDict):
    """Metadata context injected into dashboard templates."""

    integration_entry_id: str
    template_id: str
    release_ref: str | None
    release_version: str | None
    generated_at: str


class DashboardTemplateSnippetsContext(TypedDict):
    """Reusable snippet strings injected into dashboard templates."""

    user_setup: str
    user_validation: str
    user_validation_compact: str
    admin_setup_shared: str
    admin_setup_peruser: str
    admin_validation_missing_selector: str
    admin_validation_invalid_selection: str
    admin_validation_dashboard_helper: str
    admin_validation_missing_selector_compact: str
    admin_validation_invalid_selection_compact: str
    user_override_helper: str
    meta_stamp: str


class DashboardContext(TypedDict):
    """Full context for dashboard template rendering.

    Passed to the Python Jinja2 environment with << >> delimiters.
    For assignee dashboards, only the context key is used.
    For admin dashboard, no context is needed (fully dynamic).
    """

    assignee: DashboardAssigneeContext
    user: DashboardUserContext
    integration: dict[str, str]
    dashboard_meta: DashboardMetaContext
    template_snippets: DashboardTemplateSnippetsContext


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


def _escape_jinja_single_quote(value: str) -> str:
    """Escape value for embedding in single-quoted Jinja set statements."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _indent_for_yaml_template_block(snippet: str) -> str:
    """Indent snippet newlines so inserted Jinja stays inside YAML block scalars."""
    yaml_block_content_indent = " " * 18
    return snippet.replace("\n", f"\n{yaml_block_content_indent}")


def _format_template_snippet(snippet: str) -> str:
    """Apply YAML-safety formatting to inserted snippets without inner blank lines."""
    return _indent_for_yaml_template_block(snippet)


def _build_template_snippets(
    *,
    assignee_name: str,
    assignee_id: str,
    integration_entry_id: str,
    template_id: str,
    release_ref: str | None,
    release_version: str | None,
    generated_at: str,
) -> DashboardTemplateSnippetsContext:
    """Build reusable insertable snippet payloads for templates."""
    escaped_name = _escape_jinja_single_quote(assignee_name)
    escaped_assignee_id = _escape_jinja_single_quote(assignee_id)
    escaped_entry_id = _escape_jinja_single_quote(integration_entry_id)
    effective_release = release_ref or release_version or "local"
    meta_stamp = (
        "{#-- META STAMP: "
        f"{_escape_jinja_single_quote(template_id)} • "
        f"{_escape_jinja_single_quote(effective_release)} • "
        f"{_escape_jinja_single_quote(generated_at)}"
        " --#}"
    )

    user_setup = (
        f"{{%- set fallback_name = '{escaped_name}' -%}}\n"
        "{%- set name = fallback_name -%}\n"
        f"{{%- set user_id = '{escaped_assignee_id}' -%}}\n"
        f"{{%- set entry_id = '{escaped_entry_id}' -%}}\n"
        "{%- set lookup_key = entry_id ~ ':' ~ user_id -%}\n"
        "{%- if not (use_override_dashboard_helper | default(false, true)) -%}\n"
        "  {%- set dashboard_helper = integration_entities('choreops')\n"
        "      | select('search', '^sensor\\\\.')\n"
        "      | list\n"
        "      | expand\n"
        "      | selectattr('attributes.purpose', 'defined')\n"
        "      | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')\n"
        "      | selectattr('attributes.dashboard_lookup_key', 'eq', lookup_key)\n"
        "      | map(attribute='entity_id')\n"
        "      | first\n"
        '      | default("err-dashboard_helper_missing", true) -%}\n'
        "{%- endif -%}"
        "\n"
        "{%- set resolved_name = (state_attr(dashboard_helper, 'user_name') if dashboard_helper not in ['err-dashboard_helper_missing', '', None] else '') | default('', true) -%}\n"
        "{%- if resolved_name != '' -%}\n"
        "  {%- set name = resolved_name -%}\n"
        "{%- endif -%}"
    )

    user_validation = (
        "{#-- Validation: Check if user context is configured --#}\n"
        "{%- if name == '' -%}\n"
        "  {{\n"
        "    {\n"
        "      'type': 'markdown',\n"
        "      'content': \"⚠️ **Dashboard Not Configured**\\n\\nNo user context is available for this card.\\n\\nReload ChoreOps and regenerate dashboards if this persists.\"\n"
        "    }\n"
        "  }},\n"
        "  {%- set skip_render = true -%}\n"
        "{%- elif states(dashboard_helper) in ['unknown', 'unavailable'] -%}\n"
        "  {{\n"
        "    {\n"
        "      'type': 'markdown',\n"
        '      \'content\': "⚠️ **Dashboard Configuration Error**\\n\\nCannot find: `" ~ dashboard_helper ~ "`\\n\\nThe dashboard helper is unavailable for this user."\n'
        "    }\n"
        "  }},\n"
        "  {%- set skip_render = true -%}\n"
        "{%- else -%}\n"
        "  {%- set skip_render = false -%}\n"
        "{%- endif -%}"
    )

    user_validation_compact = (
        "{%- if name == '' or states(dashboard_helper) in ['unknown', 'unavailable'] -%}\n"
        "  {%- set skip_render = true -%}\n"
        "{%- else -%}\n"
        "  {%- set skip_render = false -%}\n"
        "{%- endif -%}"
    )

    admin_setup_shared = (
        f"{{%- set entry_id = '{escaped_entry_id}' -%}}\n"
        "{%- if use_override_dashboard_helper | default(false, true) -%}\n"
        "  {%- set admin_selector_eid = dashboard_helper -%}\n"
        "{%- else -%}\n"
        "  {%- set admin_selector_eid = integration_entities('choreops')\n"
        "      | select('match', '^select\\\\.')\n"
        "      | list\n"
        "      | expand\n"
        "      | selectattr('attributes.purpose', 'defined')\n"
        "      | selectattr('attributes.purpose', 'eq', 'purpose_system_dashboard_admin_user')\n"
        "      | selectattr('attributes.integration_entry_id', 'eq', entry_id)\n"
        "      | map(attribute='entity_id')\n"
        "      | first\n"
        "      | default('', true) -%}\n"
        "{%- endif -%}"
    )

    admin_setup_peruser = (
        f"{{%- set fallback_name = '{escaped_name}' -%}}\n"
        "{%- set name = fallback_name -%}\n"
        f"{{%- set user_id = '{escaped_assignee_id}' -%}}\n"
        f"{{%- set entry_id = '{escaped_entry_id}' -%}}\n"
        "{%- set lookup_key = entry_id ~ ':' ~ user_id -%}\n"
        "{%- if use_override_dashboard_helper | default(false, true) -%}\n"
        "  {%- set admin_selector_eid = dashboard_helper -%}\n"
        "{%- else -%}\n"
        "  {%- set admin_selector_eid = integration_entities('choreops')\n"
        "      | select('search', '^sensor\\\\.')\n"
        "      | list\n"
        "      | expand\n"
        "      | selectattr('attributes.purpose', 'defined')\n"
        "      | selectattr('attributes.purpose', 'eq', 'purpose_dashboard_helper')\n"
        "      | selectattr('attributes.dashboard_lookup_key', 'eq', lookup_key)\n"
        "      | map(attribute='entity_id')\n"
        "      | first\n"
        "      | default('', true) -%}\n"
        "{%- endif -%}"
        "\n"
        "{%- set resolved_name = (state_attr(admin_selector_eid, 'user_name') if admin_selector_eid not in ['', None] else '') | default('', true) -%}\n"
        "{%- if resolved_name != '' -%}\n"
        "  {%- set name = resolved_name -%}\n"
        "{%- endif -%}"
    )

    admin_validation_missing_selector = (
        "{%- if admin_selector_eid == '' -%}\n"
        "  {{\n"
        "    {\n"
        "      'type': 'markdown',\n"
        "      'content': \"⚠️ **Admin Selector Not Found**\\n\\nThe admin selector entity could not be resolved for this dashboard context.\"\n"
        "    }\n"
        "  }},\n"
        "  {%- set skip_render = true -%}\n"
        "{%- else -%}\n"
        "  {%- set skip_render = false -%}\n"
        "{%- endif -%}"
    )

    admin_validation_invalid_selection = (
        "{%- if not skip_render and states(admin_selector_eid) in ['None', '', 'unknown', 'unavailable'] -%}\n"
        "  {{\n"
        "    {\n"
        "      'type': 'markdown',\n"
        "      'content': \"ℹ️ **No User Selected**\\n\\nSelect a user from the admin selector to continue.\"\n"
        "    }\n"
        "  }},\n"
        "  {%- set skip_render = true -%}\n"
        "{%- endif -%}"
    )

    admin_validation_dashboard_helper = (
        "{%- if not skip_render and states(dashboard_helper) in ['unknown', 'unavailable'] -%}\n"
        "  {{\n"
        "    {\n"
        "      'type': 'markdown',\n"
        '      \'content\': "⚠️ **Dashboard Configuration Error**\\n\\nCannot find: `" ~ dashboard_helper ~ "`\\n\\nThe dashboard helper is unavailable for user `" ~ name ~ "`.\\n\\nCheck Settings → Integrations → ChoreOps and verify the user is configured."\n'
        "    }\n"
        "  }},\n"
        "  {%- set skip_render = true -%}\n"
        "{%- endif -%}"
    )

    admin_validation_missing_selector_compact = (
        "{%- if admin_selector_eid == '' -%}\n"
        "  {%- set skip_render = true -%}\n"
        "{%- else -%}\n"
        "  {%- set skip_render = false -%}\n"
        "{%- endif -%}"
    )

    admin_validation_invalid_selection_compact = (
        "{%- if not skip_render and states(admin_selector_eid) in ['None', '', 'unknown', 'unavailable'] -%}\n"
        "  {%- set skip_render = true -%}\n"
        "{%- endif -%}"
    )

    user_override_helper = (
        "{#-- Optional advanced override; leave empty for auto-lookup --#}\n"
        "{#-- Set override_dashboard_helper to a dashboard helper entity_id to force this card to use it and skip dynamic helper/selector lookups --#}\n"
        "{%- set override_dashboard_helper = '' -%}\n"
        "{%- set use_override_dashboard_helper = override_dashboard_helper != '' -%}\n"
        "{%- if use_override_dashboard_helper -%}\n"
        "  {%- set dashboard_helper = override_dashboard_helper -%}\n"
        "{%- endif -%}"
    )

    return DashboardTemplateSnippetsContext(
        user_setup=_format_template_snippet(user_setup),
        user_validation=_format_template_snippet(user_validation),
        user_validation_compact=_format_template_snippet(user_validation_compact),
        admin_setup_shared=_format_template_snippet(admin_setup_shared),
        admin_setup_peruser=_format_template_snippet(admin_setup_peruser),
        admin_validation_missing_selector=_format_template_snippet(
            admin_validation_missing_selector
        ),
        admin_validation_invalid_selection=_format_template_snippet(
            admin_validation_invalid_selection
        ),
        admin_validation_dashboard_helper=_format_template_snippet(
            admin_validation_dashboard_helper
        ),
        admin_validation_missing_selector_compact=_format_template_snippet(
            admin_validation_missing_selector_compact
        ),
        admin_validation_invalid_selection_compact=_format_template_snippet(
            admin_validation_invalid_selection_compact
        ),
        user_override_helper=_format_template_snippet(user_override_helper),
        meta_stamp=_format_template_snippet(meta_stamp),
    )


def build_dashboard_context(
    assignee_name: str,
    *,
    assignee_id: str,
    integration_entry_id: str,
    template_profile: str | None = None,
    release_ref: str | None = None,
    release_version: str | None = None,
    generated_at: str | None = None,
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
    template_id = template_profile or "unknown-template"
    generated_timestamp = generated_at or dt_now_iso()

    return DashboardContext(
        assignee=build_assignee_context(assignee_name),
        user=DashboardUserContext(
            name=assignee_name,
            slug=slugify(assignee_name),
            user_id=assignee_id,
        ),
        integration={"entry_id": integration_entry_id},
        dashboard_meta=DashboardMetaContext(
            integration_entry_id=integration_entry_id,
            template_id=template_id,
            release_ref=release_ref,
            release_version=release_version,
            generated_at=generated_timestamp,
        ),
        template_snippets=_build_template_snippets(
            assignee_name=assignee_name,
            assignee_id=assignee_id,
            integration_entry_id=integration_entry_id,
            template_id=template_id,
            release_ref=release_ref,
            release_version=release_version,
            generated_at=generated_timestamp,
        ),
    )


def build_admin_dashboard_context(
    *,
    integration_entry_id: str,
    template_profile: str | None = None,
    release_ref: str | None = None,
    release_version: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build admin/global dashboard template context."""
    template_id = template_profile or "unknown-template"
    generated_timestamp = generated_at or dt_now_iso()
    return {
        "integration": {"entry_id": integration_entry_id},
        "user": {},
        "assignee": {},
        const.DASHBOARD_CONTEXT_KEY_META: {
            const.ATTR_INTEGRATION_ENTRY_ID: integration_entry_id,
            const.DASHBOARD_PROVENANCE_KEY_TEMPLATE_ID: template_id,
            const.DASHBOARD_PROVENANCE_KEY_EFFECTIVE_REF: release_ref,
            const.DASHBOARD_META_KEY_RELEASE_VERSION: release_version,
            const.DASHBOARD_PROVENANCE_KEY_GENERATED_AT: generated_timestamp,
        },
        const.DASHBOARD_CONTEXT_KEY_SNIPPETS: _build_template_snippets(
            assignee_name="",
            assignee_id="",
            integration_entry_id=integration_entry_id,
            template_id=template_id,
            release_ref=release_ref,
            release_version=release_version,
            generated_at=generated_timestamp,
        ),
    }


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
    installed_release_version: str | None = None,
) -> list[selector.SelectOptionDict]:
    """Build Step 1 release selector options.

    Option order is fixed:
    1) current installed
    2) latest stable
    3) explicit compatible tags
    """
    _ = installed_release_version

    options: list[selector.SelectOptionDict] = [
        selector.SelectOptionDict(
            value=const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED,
            label=const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
            label=const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
        ),
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
    show_release_controls: bool | None = None,
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
    if show_release_controls is None:
        show_release_controls = include_release_controls

    if template_profile_default is None:
        template_profile_default = get_default_assignee_template_id()

    if admin_template_global_default is None:
        admin_template_global_default = get_default_admin_global_template_id()

    if admin_template_per_assignee_default is None:
        admin_template_per_assignee_default = (
            get_default_admin_per_assignee_template_id()
        )

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
    if show_release_controls:
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

    if show_release_controls:
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
        List of dicts with:
        - `value`: dashboard URL path (stable internal selection value)
        - `label`: friendly name with `(cod-...)` path suffix
    """
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    discovered_dashboards: list[dict[str, str]] = []

    if LOVELACE_DATA not in hass.data:
        return discovered_dashboards

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
                    config_title = config.get("title")
                    if isinstance(config_title, str) and config_title.strip():
                        title = config_title.strip()
                    else:
                        # Get title from views if available
                        views = config.get("views", [])
                        if views and isinstance(views, list) and len(views) > 0:
                            first_view = views[0]
                            if isinstance(first_view, dict):
                                view_title = first_view.get("title")
                                if isinstance(view_title, str) and view_title.strip():
                                    title = view_title.strip()

            discovered_dashboards.append(
                {
                    "value": url_path,
                    "title": str(title).strip() or url_path,
                }
            )

    if not discovered_dashboards:
        return []

    dashboards: list[dict[str, str]] = []
    for dashboard in sorted(
        discovered_dashboards, key=lambda item: item["title"].casefold()
    ):
        url_path = dashboard["value"]
        title = dashboard["title"]
        display_path = url_path
        if display_path.startswith(const.DASHBOARD_LEGACY_URL_PATH_PREFIX):
            display_path = display_path.replace(
                const.DASHBOARD_LEGACY_URL_PATH_PREFIX,
                const.DASHBOARD_URL_PATH_PREFIX,
                1,
            )
        label = f"{title} ({display_path})"
        dashboards.append({"value": url_path, "label": label})

    return dashboards


def build_dashboard_action_schema(
    *,
    release_tags: list[str] | None = None,
    installed_release_version: str | None = None,
    release_selection_default: str = const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED,
) -> vol.Schema:
    """Build schema for Step 1 dashboard mode and release selection.

    Returns:
        Voluptuous schema for action and release controls.
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
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION,
                default=release_selection_default,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=build_dashboard_release_selection_options(
                        release_tags,
                        installed_release_version,
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=const.TRANS_KEY_CFOF_DASHBOARD_RELEASE_SELECTION,
                )
            ),
        },
        extra=vol.ALLOW_EXTRA,
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


def build_dashboard_missing_dependencies_schema(
    continue_default: bool = False,
    *,
    show_dependency_bypass: bool = True,
) -> vol.Schema:
    """Build schema for final dashboard review step."""
    if not show_dependency_bypass:
        return vol.Schema({})

    return vol.Schema(
        {
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS,
                default=continue_default,
            ): selector.BooleanSelector(),
        }
    )


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
