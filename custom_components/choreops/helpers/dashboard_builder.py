# File: helpers/dashboard_builder.py
"""Dashboard generation engine for ChoreOps.

Provides template fetching, rendering, and Lovelace dashboard creation
via Home Assistant's storage-based dashboard API.

All functions here require a `hass` object or interact with HA APIs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.frontend import (
    DATA_PANELS,
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.lovelace.const import (
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    CONF_URL_PATH,
    DEFAULT_ICON,
    DOMAIN as LOVELACE_DOMAIN,
    LOVELACE_DATA,
    MODE_STORAGE,
    ConfigNotFound,
)
from homeassistant.components.lovelace.dashboard import (
    DashboardsCollection,
    LovelaceStorage,
)
from homeassistant.const import CONF_ICON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify
import jinja2
import yaml

from .. import const
from ..utils.dt_utils import dt_now_iso
from .dashboard_helpers import (
    async_prime_manifest_template_definitions,
    build_dashboard_context,
    get_default_admin_template_id,
    get_default_assignee_template_id,
    get_template_source_path,
    normalize_template_id,
    resolve_assignee_template_profile,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Template fetch timeout in seconds
TEMPLATE_FETCH_TIMEOUT = 10


@dataclass(frozen=True, slots=True)
class DashboardReleaseSelection:
    """Resolved dashboard release selection result."""

    selected_tag: str | None
    fallback_tag: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class DashboardReleaseTag:
    """Normalized representation of a supported dashboard release tag.

    Supported formats:
            - `X.Y.Z`
        - `X.Y.Z-beta.N`
        - `X.Y.Z-rc.N`
    """

    raw_tag: str
    major: int
    minor: int
    patch: int
    prerelease_label: str | None = None
    prerelease_number: int | None = None

    @property
    def is_prerelease(self) -> bool:
        """Return True when this tag is a prerelease (beta/rc)."""
        return self.prerelease_label is not None

    @property
    def sort_key(self) -> tuple[int, int, int, int, int, int]:
        """Return deterministic key for newest-first release selection.

        Stable tags sort after prereleases for the same semantic version.
        """
        stability_rank = 0 if self.is_prerelease else 1
        prerelease_label_rank = 0
        if self.prerelease_label == "rc":
            prerelease_label_rank = 1
        prerelease_number = self.prerelease_number or 0
        return (
            self.major,
            self.minor,
            self.patch,
            stability_rank,
            prerelease_label_rank,
            prerelease_number,
        )


def parse_dashboard_release_tag(tag: str) -> DashboardReleaseTag | None:
    """Parse supported dashboard release tag formats.

    Args:
        tag: Release tag string from dashboard repository.

    Returns:
        Parsed DashboardReleaseTag for supported formats, else None.
    """
    match = re.match(const.DASHBOARD_RELEASE_TAG_PATTERN, tag)
    if match is None:
        return None

    prerelease_label = match.group("pre_label")
    prerelease_number_raw = match.group("pre_num")

    prerelease_number: int | None = None
    if prerelease_label is not None:
        # Defensive parse; regex already constrains to digits.
        prerelease_number = int(prerelease_number_raw) if prerelease_number_raw else 0

    return DashboardReleaseTag(
        raw_tag=tag,
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease_label=prerelease_label,
        prerelease_number=prerelease_number,
    )


def is_supported_dashboard_release_tag(tag: str) -> bool:
    """Return True when tag matches the supported parser contract."""
    return parse_dashboard_release_tag(tag) is not None


def release_tag_passes_prerelease_policy(
    tag: str,
    include_prereleases: bool = const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT,
) -> bool:
    """Return True when a parsed release tag passes prerelease policy.

    Args:
        tag: Release tag string to evaluate.
        include_prereleases: Whether prereleases are allowed in selection.

    Returns:
        True if tag is supported and policy allows it.
    """
    parsed_tag = parse_dashboard_release_tag(tag)
    if parsed_tag is None:
        return False

    if include_prereleases:
        return True

    return not parsed_tag.is_prerelease


def _build_release_template_url(source_path: str, release_ref: str) -> str:
    """Build release-aware remote template URL for manifest source path."""
    return const.DASHBOARD_RELEASE_TEMPLATE_URL_PATTERN.format(
        owner=const.DASHBOARD_RELEASE_REPO_OWNER,
        repo=const.DASHBOARD_RELEASE_REPO_NAME,
        ref=release_ref,
        source_path=source_path,
    )


async def fetch_release_asset_text(
    hass: HomeAssistant,
    *,
    release_ref: str,
    source_path: str,
) -> str:
    """Fetch a release asset text file by source path.

    Args:
        hass: Home Assistant instance.
        release_ref: Release tag/ref to fetch from.
        source_path: Path within the release repository.

    Returns:
        Asset content as text.

    Raises:
        HomeAssistantError: If fetch fails.
        TimeoutError: If request times out.
    """
    asset_url = _build_release_template_url(
        source_path=source_path,
        release_ref=release_ref,
    )
    return await _fetch_remote_template(hass, asset_url)


async def _fetch_dashboard_releases(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Fetch release payloads from GitHub Releases API."""
    session = async_get_clientsession(hass)
    releases_url = const.DASHBOARD_RELEASES_API_URL.format(
        owner=const.DASHBOARD_RELEASE_REPO_OWNER,
        repo=const.DASHBOARD_RELEASE_REPO_NAME,
    )

    async with asyncio.timeout(TEMPLATE_FETCH_TIMEOUT):
        async with session.get(releases_url) as response:
            if response.status != 200:
                raise HomeAssistantError(
                    f"HTTP {response.status} fetching releases from {releases_url}"
                )
            payload = await response.json(content_type=None)

    if not isinstance(payload, list):
        raise HomeAssistantError("Unexpected releases API response shape")
    return [release for release in payload if isinstance(release, dict)]


async def discover_compatible_dashboard_release_tags(
    hass: HomeAssistant,
    include_prereleases: bool = const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT,
) -> list[str]:
    """Return compatible dashboard release tags, sorted newest-first."""
    releases_payload = await _fetch_dashboard_releases(hass)

    compatible_tags: list[DashboardReleaseTag] = []

    for release in releases_payload:
        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str):
            continue

        parsed = parse_dashboard_release_tag(tag_name)
        if parsed is None:
            const.LOGGER.debug(
                "Ignoring unsupported dashboard release tag: %s", tag_name
            )
            continue

        if not release_tag_passes_prerelease_policy(
            tag_name,
            include_prereleases=include_prereleases,
        ):
            continue

        compatible_tags.append(parsed)

    compatible_tags.sort(key=lambda item: item.sort_key, reverse=True)
    return [item.raw_tag for item in compatible_tags]


async def resolve_dashboard_release_selection(
    hass: HomeAssistant,
    pinned_release_tag: str | None = None,
    include_prereleases: bool = const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT,
) -> DashboardReleaseSelection:
    """Resolve release selection from pinned/default behavior with fallback."""
    try:
        compatible_tags = await discover_compatible_dashboard_release_tags(
            hass,
            include_prereleases=include_prereleases,
        )
    except (TimeoutError, HomeAssistantError, ValueError) as err:
        if pinned_release_tag and is_supported_dashboard_release_tag(
            pinned_release_tag
        ):
            return DashboardReleaseSelection(
                selected_tag=pinned_release_tag,
                fallback_tag=None,
                reason="pinned_release_explicit",
            )
        const.LOGGER.debug("Dashboard release discovery unavailable: %s", err)
        return DashboardReleaseSelection(
            selected_tag=None,
            fallback_tag=None,
            reason="release_service_unavailable",
        )

    if not compatible_tags:
        if pinned_release_tag and is_supported_dashboard_release_tag(
            pinned_release_tag
        ):
            return DashboardReleaseSelection(
                selected_tag=pinned_release_tag,
                fallback_tag=None,
                reason="pinned_release_explicit",
            )
        return DashboardReleaseSelection(
            selected_tag=None,
            fallback_tag=None,
            reason="no_compatible_remote_release",
        )

    newest_compatible = compatible_tags[0]

    if pinned_release_tag:
        if pinned_release_tag in compatible_tags:
            return DashboardReleaseSelection(
                selected_tag=pinned_release_tag,
                fallback_tag=(
                    newest_compatible
                    if pinned_release_tag != newest_compatible
                    else None
                ),
                reason="pinned_release",
            )
        if is_supported_dashboard_release_tag(pinned_release_tag):
            return DashboardReleaseSelection(
                selected_tag=pinned_release_tag,
                fallback_tag=newest_compatible,
                reason="pinned_release_explicit",
            )
        return DashboardReleaseSelection(
            selected_tag=newest_compatible,
            fallback_tag=None,
            reason="pinned_unavailable_fallback_latest",
        )

    return DashboardReleaseSelection(
        selected_tag=newest_compatible,
        fallback_tag=None,
        reason="latest_compatible",
    )


# ==============================================================================
# Custom Exceptions
# ==============================================================================


class DashboardTemplateError(HomeAssistantError):
    """Error fetching or parsing dashboard template."""


class DashboardRenderError(HomeAssistantError):
    """Error rendering dashboard template with context."""


class DashboardExistsError(HomeAssistantError):
    """Dashboard with this URL path already exists."""


class DashboardSaveError(HomeAssistantError):
    """Error saving dashboard to Lovelace storage."""


# ==============================================================================
# Template Fetching
# ==============================================================================


async def fetch_dashboard_template(
    hass: HomeAssistant,
    style: str | None = None,
    pinned_release_tag: str | None = None,
    include_prereleases: bool = const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT,
    *,
    admin_template: bool = False,
) -> str:
    """Fetch dashboard template, trying remote first then local fallback.

    Args:
        hass: Home Assistant instance.
        style: Dashboard template ID from manifest.

    Returns:
        Template content as string.

    Raises:
        DashboardTemplateError: If both remote and local fetch fail.
    """
    await async_prime_manifest_template_definitions(hass)

    requested_style = style
    if requested_style is None:
        requested_style = (
            get_default_admin_template_id()
            if admin_template
            else get_default_assignee_template_id()
        )

    normalized_style = normalize_template_id(
        requested_style,
        admin_template=admin_template,
    )
    if not normalized_style:
        template_kind = "admin" if admin_template else "assignee"
        raise DashboardTemplateError(
            f"No {template_kind} dashboard template is available"
        )

    source_path = get_template_source_path(normalized_style)

    if source_path is None:
        raise DashboardTemplateError(f"Unknown dashboard template '{requested_style}'")

    release_selection = await resolve_dashboard_release_selection(
        hass,
        pinned_release_tag=pinned_release_tag,
        include_prereleases=include_prereleases,
    )

    release_candidates: list[str] = []
    if release_selection.selected_tag is not None:
        release_candidates.append(release_selection.selected_tag)
    if (
        release_selection.fallback_tag is not None
        and release_selection.fallback_tag not in release_candidates
    ):
        release_candidates.append(release_selection.fallback_tag)

    for index, candidate_tag in enumerate(release_candidates):
        remote_url = _build_release_template_url(
            source_path=source_path,
            release_ref=candidate_tag,
        )
        try:
            template_content = await _fetch_remote_template(hass, remote_url)
            const.LOGGER.debug(
                "Fetched dashboard template from remote release: style=%s tag=%s reason=%s",
                normalized_style,
                candidate_tag,
                release_selection.reason,
            )
            return template_content
        except (TimeoutError, HomeAssistantError) as err:
            if index + 1 < len(release_candidates):
                const.LOGGER.debug(
                    "Remote template candidate failed, trying fallback release: style=%s tag=%s err=%s",
                    normalized_style,
                    candidate_tag,
                    err,
                )
            else:
                const.LOGGER.debug(
                    "Remote template fetch failed after release resolution: style=%s reason=%s err=%s",
                    normalized_style,
                    release_selection.reason,
                    err,
                )

    # Attempt 2: Local bundled fallback
    try:
        template_content = await _fetch_local_template(
            hass,
            normalized_style,
            source_path,
        )
        const.LOGGER.debug(
            "Using bundled dashboard template for style=%s (resolution_reason=%s)",
            normalized_style,
            release_selection.reason,
        )
        return template_content
    except FileNotFoundError as err:
        const.LOGGER.error(
            "Dashboard template not found (remote and local failed): %s",
            normalized_style,
        )
        raise DashboardTemplateError(
            f"Dashboard template '{normalized_style}' not found"
        ) from err


async def _fetch_remote_template(hass: HomeAssistant, url: str) -> str:
    """Fetch template from remote URL.

    Args:
        hass: Home Assistant instance.
        url: URL to fetch template from.

    Returns:
        Template content as string.

    Raises:
        HomeAssistantError: If fetch fails or returns non-200 status.
        TimeoutError: If request times out.
    """
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(TEMPLATE_FETCH_TIMEOUT):
            async with session.get(url) as response:
                if response.status != 200:
                    raise HomeAssistantError(
                        f"HTTP {response.status} fetching template from {url}"
                    )
                return await response.text()
    except TimeoutError:
        raise
    except Exception as err:
        raise HomeAssistantError(f"Failed to fetch template: {err}") from err


async def _fetch_local_template(
    hass: HomeAssistant,
    template_id: str,
    source_path: str,
) -> str:
    """Fetch template from local bundled files.

    Args:
        hass: Home Assistant instance.
        template_id: Dashboard template ID.
        source_path: Manifest source path for the template.

    Returns:
        Template content as string.

    Raises:
        FileNotFoundError: If local template file doesn't exist.
    """
    # Source paths in manifest are relative to the dashboard manifest directory.
    component_root = Path(__file__).parent.parent
    manifest_dir = component_root / Path(const.DASHBOARD_MANIFEST_PATH).parent
    template_path = manifest_dir / source_path

    def read_template() -> str:
        return template_path.read_text(encoding="utf-8")

    # Run file I/O in executor to avoid blocking
    return await hass.async_add_executor_job(read_template)


# ==============================================================================
# Template Rendering
# ==============================================================================


def render_dashboard_template(
    template_str: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Render Jinja2 template with context and parse as YAML.

    Uses custom delimiters (<< >> for variables) to avoid conflicts
    with Home Assistant's {{ }} Jinja2 syntax in the template.

    Args:
        template_str: Raw template string with << >> placeholders.
        context: Template context dict. For assignee dashboards, use DashboardContext
            with assignee.name and assignee.slug. For admin, use empty dict {}.

    Returns:
        Parsed YAML as dict (single view object).

    Raises:
        DashboardRenderError: If template rendering or YAML parsing fails.
    """
    render_context = dict(context)

    if "<< user." in template_str and not isinstance(render_context.get("user"), dict):
        raise DashboardRenderError("Template requires 'user' context")

    if "<< assignee." in template_str and not isinstance(
        render_context.get("assignee"),
        dict,
    ):
        raise DashboardRenderError("Template requires 'assignee' context")

    # Create Jinja2 environment with custom delimiters
    # This allows << assignee.name >> for our injection while preserving
    # {{ states('sensor.x') }} for HA runtime evaluation
    #
    # IMPORTANT: Use custom comment delimiters that DON'T match {# #}
    # so that HA's Jinja2 comments are preserved in the output
    # (not stripped during our build-time render)
    env = jinja2.Environment(
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#--",
        comment_end_string="--#>",
        autoescape=False,
    )

    try:
        template = env.from_string(template_str)
        rendered = template.render(**render_context)
    except jinja2.TemplateError as err:
        const.LOGGER.error("Template rendering failed: %s", err)
        raise DashboardRenderError(f"Template rendering failed: {err}") from err

    try:
        config = yaml.safe_load(rendered)
    except yaml.YAMLError as err:
        const.LOGGER.error("YAML parsing failed: %s", err)
        raise DashboardRenderError(f"YAML parsing failed: {err}") from err

    # Template now produces a single view (list with one item) or a dict
    # Handle both cases for flexibility
    if isinstance(config, list) and len(config) > 0:
        # Template is a list (starts with '- '), return first item
        return config[0]
    if isinstance(config, dict):
        return config

    raise DashboardRenderError("Template did not produce a valid view config")


def build_multi_view_dashboard(
    views: list[dict[str, Any]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete dashboard config from multiple views.

    Args:
        views: List of view config dicts.

    Returns:
        Complete Lovelace dashboard config with views array.
    """
    dashboard_config: dict[str, Any] = {"views": views}
    if provenance:
        dashboard_config[const.DASHBOARD_CONFIG_KEY_PROVENANCE] = provenance
    return dashboard_config


def _build_dashboard_provenance(
    *,
    integration_entry_id: str,
    template_id: str,
    requested_release_selection: str,
    effective_release_ref: str | None,
    resolution_reason: str,
    pinned_release_tag: str | None,
    include_prereleases: bool,
) -> dict[str, Any]:
    """Build dashboard generation provenance metadata."""
    if requested_release_selection == const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED:
        source_type = "local_bundled"
    elif pinned_release_tag:
        source_type = "remote_release"
    else:
        source_type = "latest_compatible"
    return {
        const.ATTR_INTEGRATION_ENTRY_ID: integration_entry_id,
        const.DASHBOARD_PROVENANCE_KEY_TEMPLATE_ID: template_id,
        const.DASHBOARD_PROVENANCE_KEY_SOURCE_TYPE: source_type,
        const.DASHBOARD_PROVENANCE_KEY_SELECTED_REF: pinned_release_tag,
        const.DASHBOARD_PROVENANCE_KEY_REQUESTED_SELECTION: requested_release_selection,
        const.DASHBOARD_PROVENANCE_KEY_EFFECTIVE_REF: effective_release_ref,
        const.DASHBOARD_PROVENANCE_KEY_RESOLUTION_REASON: resolution_reason,
        const.DASHBOARD_PROVENANCE_KEY_INCLUDE_PRERELEASES: include_prereleases,
        const.DASHBOARD_PROVENANCE_KEY_GENERATED_AT: dt_now_iso(),
    }


def get_multi_view_url_path(dashboard_name: str) -> str:
    """Generate URL path for a multi-view dashboard.

    Args:
        dashboard_name: User-specified dashboard name (e.g., "Chores").

    Returns:
        Slugified URL path with cod- prefix (e.g., "cod-chores").
    """
    slug = slugify(dashboard_name.lower())
    return f"{const.DASHBOARD_URL_PATH_PREFIX}{slug}"


def _is_choreops_dashboard_url_path(url_path: str) -> bool:
    """Return True for current or legacy ChoreOps dashboard URL paths."""
    return url_path.startswith(
        (
            const.DASHBOARD_URL_PATH_PREFIX,
            const.DASHBOARD_LEGACY_URL_PATH_PREFIX,
        )
    )


def _get_collection_items(collection: DashboardsCollection) -> list[dict[str, Any]]:
    """Return dashboard items from DashboardsCollection across HA storage shapes."""
    raw_data = collection.data
    if isinstance(raw_data, dict):
        items_obj = raw_data.get("items")
        if isinstance(items_obj, list):
            return [item for item in items_obj if isinstance(item, dict)]
        return [item for item in raw_data.values() if isinstance(item, dict)]
    return []


# ==============================================================================
# Dashboard Existence Check
# ==============================================================================


def check_dashboard_exists(hass: HomeAssistant, url_path: str) -> bool:
    """Check if a dashboard with the given URL path already exists.

    Args:
        hass: Home Assistant instance.
        url_path: Dashboard URL path to check (e.g., "cod-alice").

    Returns:
        True if dashboard exists, False otherwise.
    """
    # Check frontend panels
    if DATA_PANELS in hass.data and url_path in hass.data[DATA_PANELS]:
        return True

    # Check lovelace dashboards
    if LOVELACE_DATA in hass.data:
        lovelace_data = hass.data[LOVELACE_DATA]
        if url_path in lovelace_data.dashboards:
            return True

    return False


async def async_check_dashboard_exists(hass: HomeAssistant, url_path: str) -> bool:
    """Check if a dashboard with the given URL path already exists.

    Includes runtime panel/dashboard checks and persisted collection items.

    Args:
        hass: Home Assistant instance.
        url_path: Dashboard URL path to check (e.g., "cod-alice").

    Returns:
        True if dashboard exists, False otherwise.
    """
    if check_dashboard_exists(hass, url_path):
        return True

    dashboards_collection = DashboardsCollection(hass)
    await dashboards_collection.async_load()

    for item in _get_collection_items(dashboards_collection):
        if item.get(CONF_URL_PATH) == url_path:
            return True

    return False


async def async_get_dashboard_update_metadata(
    hass: HomeAssistant,
    url_path: str,
) -> dict[str, str] | None:
    """Return minimal metadata for an existing dashboard update target.

    Returns a dict containing at least `url_path`, `title`, and `icon` when the
    dashboard exists in storage; otherwise returns None.
    """
    dashboards_collection = DashboardsCollection(hass)
    await dashboards_collection.async_load()

    for item in _get_collection_items(dashboards_collection):
        if item.get(CONF_URL_PATH) != url_path:
            continue
        title = str(item.get(CONF_TITLE, url_path) or url_path)
        icon = str(item.get(CONF_ICON, DEFAULT_ICON) or DEFAULT_ICON)
        return {
            CONF_URL_PATH: url_path,
            CONF_TITLE: title,
            CONF_ICON: icon,
        }

    return None


async def async_dedupe_choreops_dashboards(
    hass: HomeAssistant,
    url_path: str | None = None,
) -> dict[str, int]:
    """Remove duplicate ChoreOps dashboard records from collection storage.

    Keeps the most recent record for each url path and removes older duplicates.

    Args:
        hass: Home Assistant instance.
        url_path: Optional specific url path to dedupe.

    Returns:
        Mapping of url_path to number of removed duplicate records.
    """
    dashboards_collection = DashboardsCollection(hass)
    await dashboards_collection.async_load()

    matching_items: dict[str, list[dict[str, Any]]] = {}
    for item in _get_collection_items(dashboards_collection):
        item_url_path = item.get(CONF_URL_PATH)
        if not isinstance(item_url_path, str):
            continue
        if not _is_choreops_dashboard_url_path(item_url_path):
            continue
        if url_path and item_url_path != url_path:
            continue
        matching_items.setdefault(item_url_path, []).append(item)

    removed_by_path: dict[str, int] = {}

    for target_url_path, items in matching_items.items():
        if len(items) <= 1:
            continue

        # Keep newest item (last in collection order), remove older duplicates
        to_remove = items[:-1]
        removed_count = 0
        for duplicate_item in to_remove:
            duplicate_id = duplicate_item.get("id")
            if not isinstance(duplicate_id, str):
                continue
            try:
                await dashboards_collection.async_delete_item(duplicate_id)
                removed_count += 1
            except HomeAssistantError as err:
                const.LOGGER.warning(
                    "Failed to delete duplicate dashboard entry %s for %s: %s",
                    duplicate_id,
                    target_url_path,
                    err,
                )

        if removed_count > 0:
            removed_by_path[target_url_path] = removed_count
            const.LOGGER.info(
                "Deduplicated dashboard entries for %s (removed=%d)",
                target_url_path,
                removed_count,
            )

    return removed_by_path


# ==============================================================================
# Dashboard Creation
# ==============================================================================


async def create_choreops_dashboard(
    hass: HomeAssistant,
    integration_entry_id: str,
    dashboard_name: str,
    assignee_names: list[str],
    assignee_ids_by_name: dict[str, str] | None = None,
    style: str | None = None,
    assignee_template_profiles: dict[str, str] | None = None,
    include_admin: bool = True,
    admin_mode: str = const.DASHBOARD_ADMIN_MODE_GLOBAL,
    force_rebuild: bool = False,
    show_in_sidebar: bool = True,
    require_admin: bool = False,
    icon: str = "mdi:clipboard-list",
    admin_view_visibility: str = const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
    admin_visible_user_ids: list[str] | None = None,
    pinned_release_tag: str | None = None,
    include_prereleases: bool = const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT,
    prepared_release_assets: dict[str, Any] | None = None,
    requested_release_selection: str = const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
    resolution_reason: str = "latest_compatible",
) -> str:
    """Create a ChoreOps dashboard with views for multiple assignees.

    This is the main entry point for dashboard generation. It creates a single
    dashboard with multiple views (tabs) - one for each assignee plus an optional
    admin view.

    Args:
        hass: Home Assistant instance.
        integration_entry_id: Integration config entry ID for instance-scoped
            admin selector lookup.
        dashboard_name: User-specified dashboard name (e.g., "Chores").
        assignee_names: List of assignee names to create views for.
        assignee_ids_by_name: Optional assignee name->internal ID mapping.
        style: Assignee dashboard template ID from manifest.
        assignee_template_profiles: Optional per-assignee template profile map.
        include_admin: Whether to include an admin view tab.
        admin_mode: Admin layout mode (none, global, per_assignee, both).
        force_rebuild: If True, delete existing dashboard first.
        show_in_sidebar: Whether to show in sidebar.
        require_admin: Whether dashboard requires admin access.
        icon: Dashboard icon.

    Returns:
        The URL path of the created dashboard (e.g., "cod-chores").

    Raises:
        DashboardExistsError: If dashboard exists and force_rebuild is False.
        DashboardTemplateError: If template fetch fails.
        DashboardRenderError: If template rendering fails.
        DashboardSaveError: If saving to Lovelace fails.
    """
    # Check for recovery mode
    if hass.config.recovery_mode:
        raise DashboardSaveError("Cannot create dashboards in recovery mode")

    # Generate URL path and title from dashboard name
    url_path = get_multi_view_url_path(dashboard_name)
    title = dashboard_name

    # Check if dashboard already exists
    should_delete_existing = False
    if await async_check_dashboard_exists(hass, url_path):
        if not force_rebuild:
            raise DashboardExistsError(
                f"Dashboard '{url_path}' already exists. Use force_rebuild=True to overwrite."
            )
        # Defer delete until template fetch/render succeeds (non-destructive preflight)
        should_delete_existing = True

    template_cache: dict[str, str] = {}
    prepared_template_assets: dict[str, str] = {}
    strict_pin = False
    if isinstance(prepared_release_assets, dict):
        raw_template_assets = prepared_release_assets.get("template_assets")
        if isinstance(raw_template_assets, dict):
            prepared_template_assets = {
                path: content
                for path, content in raw_template_assets.items()
                if isinstance(path, str) and isinstance(content, str)
            }
        strict_pin = bool(prepared_release_assets.get("strict_pin", False))

    async def _get_template(target_style: str) -> str:
        if target_style not in template_cache:
            source_path = get_template_source_path(target_style)
            if isinstance(source_path, str) and source_path in prepared_template_assets:
                template_cache[target_style] = prepared_template_assets[source_path]
            elif strict_pin:
                raise DashboardTemplateError(
                    f"Strict release pin is missing prepared template asset for '{target_style}'"
                )
            else:
                template_cache[target_style] = await fetch_dashboard_template(
                    hass,
                    target_style,
                    pinned_release_tag=pinned_release_tag,
                    include_prereleases=include_prereleases,
                    admin_template=False,
                )
        return template_cache[target_style]

    # Ensure default style template is available for fallback behavior
    style = normalize_template_id(
        style or get_default_assignee_template_id(),
        admin_template=False,
    )
    await _get_template(style)

    # Build views for each assignee
    views: list[dict[str, Any]] = []

    for assignee_name in assignee_names:
        assignee_id = (
            assignee_ids_by_name.get(assignee_name)
            if assignee_ids_by_name is not None
            else None
        )
        if assignee_id is None:
            assignee_id = slugify(assignee_name)
        assignee_style = resolve_assignee_template_profile(
            assignee_name,
            style,
            assignee_template_profiles,
        )
        template_str = await _get_template(assignee_style)
        assignee_context = build_dashboard_context(
            assignee_name,
            assignee_id=assignee_id,
            integration_entry_id=integration_entry_id,
            template_profile=assignee_style,
        )
        # Convert TypedDict to regular dict for generic render function
        assignee_view = render_dashboard_template(template_str, dict(assignee_context))
        views.append(assignee_view)
        const.LOGGER.debug(
            "Built view for assignee: %s (template_profile=%s)",
            assignee_name,
            assignee_style,
        )

    normalized_admin_mode = _normalize_admin_mode(admin_mode)

    # Add admin view if requested
    if include_admin:
        admin_template_id = normalize_template_id(
            get_default_admin_template_id(),
            admin_template=True,
        )
        if not admin_template_id:
            raise DashboardTemplateError(
                "No admin dashboard template is available in manifest"
            )

        admin_source_path = get_template_source_path(admin_template_id)
        if (
            isinstance(admin_source_path, str)
            and admin_source_path in prepared_template_assets
        ):
            admin_template_str = prepared_template_assets[admin_source_path]
        elif strict_pin:
            raise DashboardTemplateError(
                "Strict release pin is missing prepared admin template asset"
            )
        else:
            admin_template_str = await fetch_dashboard_template(
                hass,
                admin_template_id,
                pinned_release_tag=pinned_release_tag,
                include_prereleases=include_prereleases,
                admin_template=True,
            )
        # Admin template still needs comment stripping via Jinja2 render
        # Pass empty context since admin doesn't need assignee injection
        admin_view = render_dashboard_template(
            admin_template_str,
            {"integration": {"entry_id": integration_entry_id}},
        )
        if isinstance(admin_view, dict):
            include_global_admin = normalized_admin_mode in (
                const.DASHBOARD_ADMIN_MODE_GLOBAL,
                const.DASHBOARD_ADMIN_MODE_BOTH,
            )
            include_per_assignee_admin = normalized_admin_mode in (
                const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                const.DASHBOARD_ADMIN_MODE_BOTH,
            )

            if include_global_admin:
                global_admin_view = dict(admin_view)
                global_admin_view.setdefault("title", "ChoreOps Admin")
                global_admin_view["path"] = "admin"
                if visible_entries := _build_admin_visible_users(
                    admin_view_visibility,
                    admin_visible_user_ids,
                ):
                    global_admin_view["visible"] = visible_entries
                views.append(global_admin_view)

            if include_per_assignee_admin:
                for assignee_name in assignee_names:
                    per_assignee_admin_view = dict(admin_view)
                    per_assignee_admin_view["title"] = f"Admin - {assignee_name}"
                    per_assignee_admin_view["path"] = f"admin-{slugify(assignee_name)}"
                    if visible_entries := _build_admin_visible_users(
                        admin_view_visibility,
                        admin_visible_user_ids,
                    ):
                        per_assignee_admin_view["visible"] = visible_entries
                    views.append(per_assignee_admin_view)
            const.LOGGER.debug(
                "Added admin view(s) for mode: %s",
                normalized_admin_mode,
            )

    # Combine all views into dashboard config
    dashboard_config = build_multi_view_dashboard(
        views,
        provenance=_build_dashboard_provenance(
            integration_entry_id=integration_entry_id,
            template_id=style,
            requested_release_selection=requested_release_selection,
            effective_release_ref=pinned_release_tag,
            resolution_reason=resolution_reason,
            pinned_release_tag=pinned_release_tag,
            include_prereleases=include_prereleases,
        ),
    )

    if should_delete_existing:
        await _delete_dashboard(hass, url_path)

    # Create the dashboard entry
    await _create_dashboard_entry(
        hass,
        url_path=url_path,
        title=title,
        icon=icon,
        show_in_sidebar=show_in_sidebar,
        require_admin=require_admin,
    )

    # Save the dashboard config
    await _save_dashboard_config(hass, url_path, dashboard_config)

    const.LOGGER.info(
        "Created ChoreOps dashboard: %s with %d views (style=%s, admin=%s)",
        url_path,
        len(views),
        style,
        include_admin,
    )

    return url_path


def _is_admin_view(view: dict[str, Any]) -> bool:
    """Return True if a view appears to be the admin view."""
    path = view.get("path")
    if isinstance(path, str) and path.lower() == "admin":
        return True

    title = view.get("title")
    if isinstance(title, str) and "admin" in title.lower():
        return True

    return False


def _build_admin_visible_users(
    admin_view_visibility: str,
    admin_visible_user_ids: list[str] | None,
) -> list[dict[str, str]] | None:
    """Build Home Assistant `visible` entries for admin view access control."""
    if admin_view_visibility != const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS:
        return None

    if not admin_visible_user_ids:
        return None

    visible: list[dict[str, str]] = []
    seen: set[str] = set()
    for user_id in admin_visible_user_ids:
        if not isinstance(user_id, str):
            continue
        normalized_user_id = user_id.strip()
        if not normalized_user_id or normalized_user_id in seen:
            continue
        seen.add(normalized_user_id)
        visible.append({"user": normalized_user_id})

    return visible or None


def _normalize_admin_mode(admin_mode: str) -> str:
    """Normalize admin mode labels/aliases to canonical constants."""
    normalized = admin_mode.strip().lower().replace("-", "_").replace(" ", "_")
    alias_map: dict[str, str] = {
        const.DASHBOARD_ADMIN_MODE_NONE: const.DASHBOARD_ADMIN_MODE_NONE,
        const.DASHBOARD_ADMIN_MODE_GLOBAL: const.DASHBOARD_ADMIN_MODE_GLOBAL,
        const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE: const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
        const.DASHBOARD_ADMIN_MODE_BOTH: const.DASHBOARD_ADMIN_MODE_BOTH,
        "shared": const.DASHBOARD_ADMIN_MODE_GLOBAL,
        "per_assignee": const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
        "both": const.DASHBOARD_ADMIN_MODE_BOTH,
        "none": const.DASHBOARD_ADMIN_MODE_NONE,
    }
    return alias_map.get(normalized, const.DASHBOARD_ADMIN_MODE_GLOBAL)


async def update_choreops_dashboard_views(
    hass: HomeAssistant,
    integration_entry_id: str,
    url_path: str,
    assignee_names: list[str],
    template_profile: str,
    include_admin: bool,
    assignee_ids_by_name: dict[str, str] | None = None,
    admin_mode: str = const.DASHBOARD_ADMIN_MODE_GLOBAL,
    admin_view_visibility: str = const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
    admin_visible_user_ids: list[str] | None = None,
    icon: str | None = None,
    show_in_sidebar: bool | None = None,
    require_admin: bool | None = None,
    pinned_release_tag: str | None = None,
    include_prereleases: bool = const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT,
    prepared_release_assets: dict[str, Any] | None = None,
    requested_release_selection: str = const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
    resolution_reason: str = "latest_compatible",
) -> int:
    """Update selected views on an existing dashboard without deleting it.

    Keeps existing dashboard metadata/title and preserves non-selected assignee views.

    Args:
        hass: Home Assistant instance.
        integration_entry_id: Integration config entry ID for instance-scoped
            admin selector lookup.
        url_path: Existing dashboard url path.
        assignee_names: Assignees to update in-place.
        assignee_ids_by_name: Optional assignee name->internal ID mapping.
        template_profile: Template profile to apply for updated assignee views.
        include_admin: Whether admin view should exist after update.

    Returns:
        Number of views in the updated dashboard config.

    Raises:
        DashboardSaveError: If dashboard is missing or cannot be saved.
        DashboardTemplateError: If required templates cannot be fetched.
        DashboardRenderError: If template rendering fails.
    """
    normalized_admin_mode = _normalize_admin_mode(admin_mode)
    template_profile = normalize_template_id(template_profile, admin_template=False)

    if LOVELACE_DATA not in hass.data:
        raise DashboardSaveError("Lovelace not initialized")

    lovelace_data = hass.data[LOVELACE_DATA]
    if url_path not in lovelace_data.dashboards:
        raise DashboardSaveError(f"Dashboard '{url_path}' not found")

    dashboard = lovelace_data.dashboards[url_path]
    try:
        existing_config = await dashboard.async_load(False)
    except ConfigNotFound as err:
        raise DashboardSaveError(
            f"Dashboard '{url_path}' has no stored config"
        ) from err

    if not isinstance(existing_config, dict):
        raise DashboardSaveError(f"Dashboard '{url_path}' has invalid stored config")

    existing_views_raw = existing_config.get("views", [])
    existing_views: list[dict[str, Any]] = [
        view for view in existing_views_raw if isinstance(view, dict)
    ]

    template_cache: dict[str, str] = {}
    prepared_template_assets: dict[str, str] = {}
    strict_pin = False
    if isinstance(prepared_release_assets, dict):
        raw_template_assets = prepared_release_assets.get("template_assets")
        if isinstance(raw_template_assets, dict):
            prepared_template_assets = {
                path: content
                for path, content in raw_template_assets.items()
                if isinstance(path, str) and isinstance(content, str)
            }
        strict_pin = bool(prepared_release_assets.get("strict_pin", False))

    async def _get_template(target_style: str) -> str:
        if target_style not in template_cache:
            source_path = get_template_source_path(target_style)
            if isinstance(source_path, str) and source_path in prepared_template_assets:
                template_cache[target_style] = prepared_template_assets[source_path]
            elif strict_pin:
                raise DashboardTemplateError(
                    f"Strict release pin is missing prepared template asset for '{target_style}'"
                )
            else:
                template_cache[target_style] = await fetch_dashboard_template(
                    hass,
                    target_style,
                    pinned_release_tag=pinned_release_tag,
                    include_prereleases=include_prereleases,
                    admin_template=False,
                )
        return template_cache[target_style]

    updated_assignee_views_by_path: dict[str, dict[str, Any]] = {}
    for assignee_name in assignee_names:
        assignee_id = (
            assignee_ids_by_name.get(assignee_name)
            if assignee_ids_by_name is not None
            else None
        )
        if assignee_id is None:
            assignee_id = slugify(assignee_name)
        assignee_template = await _get_template(template_profile)
        assignee_context = build_dashboard_context(
            assignee_name,
            assignee_id=assignee_id,
            integration_entry_id=integration_entry_id,
            template_profile=template_profile,
        )
        assignee_view = render_dashboard_template(
            assignee_template, dict(assignee_context)
        )
        assignee_path = assignee_view.get("path")
        if isinstance(assignee_path, str):
            updated_assignee_views_by_path[assignee_path] = assignee_view
        else:
            # Template should always provide a path; append fallback if missing
            existing_views.append(assignee_view)

    merged_views: list[dict[str, Any]] = []
    replaced_assignee_paths: set[str] = set()
    existing_admin_view: dict[str, Any] | None = None

    for view in existing_views:
        if _is_admin_view(view):
            existing_admin_view = view
            continue

        path = view.get("path")
        if isinstance(path, str) and path in updated_assignee_views_by_path:
            merged_views.append(updated_assignee_views_by_path[path])
            replaced_assignee_paths.add(path)
            continue

        merged_views.append(view)

    for path, view in updated_assignee_views_by_path.items():
        if path not in replaced_assignee_paths:
            merged_views.append(view)

    if include_admin:
        admin_template_id = normalize_template_id(
            get_default_admin_template_id(),
            admin_template=True,
        )
        if not admin_template_id:
            raise DashboardTemplateError(
                "No admin dashboard template is available in manifest"
            )

        admin_source_path = get_template_source_path(admin_template_id)
        if (
            isinstance(admin_source_path, str)
            and admin_source_path in prepared_template_assets
        ):
            admin_template = prepared_template_assets[admin_source_path]
        elif strict_pin:
            raise DashboardTemplateError(
                "Strict release pin is missing prepared admin template asset"
            )
        else:
            admin_template = await fetch_dashboard_template(
                hass,
                admin_template_id,
                pinned_release_tag=pinned_release_tag,
                include_prereleases=include_prereleases,
                admin_template=True,
            )
        admin_view = render_dashboard_template(
            admin_template,
            {"integration": {"entry_id": integration_entry_id}},
        )
        if not isinstance(admin_view, dict):
            admin_view = {}

        include_global_admin = normalized_admin_mode in (
            const.DASHBOARD_ADMIN_MODE_GLOBAL,
            const.DASHBOARD_ADMIN_MODE_BOTH,
        )
        include_per_assignee_admin = normalized_admin_mode in (
            const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
            const.DASHBOARD_ADMIN_MODE_BOTH,
        )

        if include_global_admin:
            global_admin_view = dict(admin_view)
            global_admin_view.setdefault("title", "ChoreOps Admin")
            global_admin_view["path"] = "admin"
            if visible_entries := _build_admin_visible_users(
                admin_view_visibility,
                admin_visible_user_ids,
            ):
                global_admin_view["visible"] = visible_entries
            merged_views.append(global_admin_view)

        if include_per_assignee_admin:
            for assignee_name in assignee_names:
                per_assignee_admin_view = dict(admin_view)
                per_assignee_admin_view["title"] = f"Admin - {assignee_name}"
                per_assignee_admin_view["path"] = f"admin-{slugify(assignee_name)}"
                if visible_entries := _build_admin_visible_users(
                    admin_view_visibility,
                    admin_visible_user_ids,
                ):
                    per_assignee_admin_view["visible"] = visible_entries
                merged_views.append(per_assignee_admin_view)
    elif existing_admin_view is not None:
        const.LOGGER.debug("Removed admin view from dashboard: %s", url_path)

    new_config = dict(existing_config)
    new_config[const.DASHBOARD_CONFIG_KEY_PROVENANCE] = _build_dashboard_provenance(
        integration_entry_id=integration_entry_id,
        template_id=template_profile,
        requested_release_selection=requested_release_selection,
        effective_release_ref=pinned_release_tag,
        resolution_reason=resolution_reason,
        pinned_release_tag=pinned_release_tag,
        include_prereleases=include_prereleases,
    )
    new_config["views"] = merged_views

    try:
        await dashboard.async_save(new_config)
    except HomeAssistantError as err:
        raise DashboardSaveError(f"Failed to save dashboard config: {err}") from err

    await _update_dashboard_metadata(
        hass,
        url_path=url_path,
        icon=icon,
        show_in_sidebar=show_in_sidebar,
        require_admin=require_admin,
    )

    const.LOGGER.info(
        "Updated dashboard views in-place: %s (assignees_updated=%d, include_admin=%s, views=%d)",
        url_path,
        len(assignee_names),
        include_admin,
        len(merged_views),
    )
    return len(merged_views)


async def _update_dashboard_metadata(
    hass: HomeAssistant,
    url_path: str,
    icon: str | None,
    show_in_sidebar: bool | None,
    require_admin: bool | None,
) -> None:
    """Update dashboard metadata and panel settings for an existing dashboard."""
    dashboards_collection = DashboardsCollection(hass)
    await dashboards_collection.async_load()

    dashboard_item: dict[str, Any] | None = None
    for item in _get_collection_items(dashboards_collection):
        if item.get(CONF_URL_PATH) == url_path:
            dashboard_item = item

    if dashboard_item is None:
        return

    item_id = dashboard_item.get("id")
    if not isinstance(item_id, str):
        return

    update_data: dict[str, Any] = {}
    if icon is not None:
        update_data[CONF_ICON] = icon
    if show_in_sidebar is not None:
        update_data[CONF_SHOW_IN_SIDEBAR] = show_in_sidebar
    if require_admin is not None:
        update_data[CONF_REQUIRE_ADMIN] = require_admin

    if update_data:
        await dashboards_collection.async_update_item(item_id, update_data)

    panel_exists = DATA_PANELS in hass.data and url_path in hass.data[DATA_PANELS]
    panel_kwargs: dict[str, Any] = {
        "frontend_url_path": url_path,
        "require_admin": bool(
            update_data.get(
                CONF_REQUIRE_ADMIN,
                dashboard_item.get(CONF_REQUIRE_ADMIN, False),
            )
        ),
        "config": {"mode": MODE_STORAGE},
        "update": panel_exists,
    }

    current_show_in_sidebar = bool(
        update_data.get(
            CONF_SHOW_IN_SIDEBAR,
            dashboard_item.get(CONF_SHOW_IN_SIDEBAR, True),
        )
    )
    if current_show_in_sidebar:
        panel_kwargs["sidebar_title"] = str(dashboard_item.get(CONF_TITLE, url_path))
        panel_kwargs["sidebar_icon"] = str(
            update_data.get(
                CONF_ICON,
                dashboard_item.get(CONF_ICON, DEFAULT_ICON),
            )
            or DEFAULT_ICON
        )

    async_register_built_in_panel(hass, LOVELACE_DOMAIN, **panel_kwargs)


async def _delete_dashboard(hass: HomeAssistant, url_path: str) -> None:
    """Delete an existing dashboard.

    This function removes all traces of a dashboard:
    1. Removes from DashboardsCollection (storage) - ALL matching entries
    2. Removes from lovelace_data.dashboards (runtime)
    3. Removes the frontend panel (sidebar)

    Args:
        hass: Home Assistant instance.
        url_path: Dashboard URL path to delete.
    """
    const.LOGGER.debug("Deleting dashboard: %s", url_path)

    # Step 1: Remove from DashboardsCollection (storage)
    # Delete ALL items with matching url_path (handle duplicates)
    dashboards_collection = DashboardsCollection(hass)
    await dashboards_collection.async_load()

    items_to_delete = [
        item_id
        for item in _get_collection_items(dashboards_collection)
        if item.get(CONF_URL_PATH) == url_path
        if isinstance(item_id := item.get("id"), str)
    ]

    for item_id in items_to_delete:
        try:
            await dashboards_collection.async_delete_item(item_id)
            const.LOGGER.debug(
                "Removed dashboard entry from collection: id=%s, url_path=%s",
                item_id,
                url_path,
            )
        except Exception as err:
            const.LOGGER.warning(
                "Failed to delete dashboard entry %s: %s", item_id, err
            )

    # Step 2: Remove from lovelace_data.dashboards (runtime)
    if LOVELACE_DATA in hass.data:
        lovelace_data = hass.data[LOVELACE_DATA]
        if url_path in lovelace_data.dashboards:
            dashboard = lovelace_data.dashboards.pop(url_path)
            # Delete the storage file
            try:
                await dashboard.async_delete()
            except Exception as err:
                const.LOGGER.warning(
                    "Failed to delete dashboard storage for %s: %s", url_path, err
                )
            const.LOGGER.debug("Removed dashboard from lovelace_data: %s", url_path)

    # Step 3: Remove the frontend panel
    async_remove_panel(hass, url_path, warn_if_unknown=False)
    const.LOGGER.debug("Removed dashboard panel: %s", url_path)


async def delete_choreops_dashboard(
    hass: HomeAssistant,
    url_path: str,
) -> None:
    """Delete a ChoreOps dashboard.

    Public function to delete an existing ChoreOps dashboard.
    Handles all three aspects of dashboard removal:
    1. Panel (sidebar item)
    2. Storage (config file)
    3. Collection entry (dashboard registry)

    Args:
        hass: Home Assistant instance.
        url_path: Dashboard URL path (e.g., "cod-alice").

    Raises:
        DashboardSaveError: If deletion fails.
    """
    if hass.config.recovery_mode:
        raise DashboardSaveError("Cannot delete dashboards in recovery mode")

    if not _is_choreops_dashboard_url_path(url_path):
        raise DashboardSaveError(f"Cannot delete non-ChoreOps dashboard: {url_path}")

    await _delete_dashboard(hass, url_path)

    const.LOGGER.info("Deleted ChoreOps dashboard: %s", url_path)


async def _create_dashboard_entry(
    hass: HomeAssistant,
    url_path: str,
    title: str,
    icon: str,
    show_in_sidebar: bool,
    require_admin: bool,
) -> None:
    """Create a dashboard entry in the Lovelace collection.

    This function:
    1. Creates the dashboard entry in DashboardsCollection (persists metadata)
    2. Creates LovelaceStorage object and registers it in lovelace_data.dashboards
    3. Registers the frontend panel

    Args:
        hass: Home Assistant instance.
        url_path: Dashboard URL path.
        title: Dashboard title.
        icon: Dashboard icon.
        show_in_sidebar: Whether to show in sidebar.
        require_admin: Whether dashboard requires admin access.
    """
    # Build the dashboard config dict
    dashboard_config = {
        CONF_URL_PATH: url_path,
        CONF_TITLE: title,
        CONF_ICON: icon,
        CONF_SHOW_IN_SIDEBAR: show_in_sidebar,
        CONF_REQUIRE_ADMIN: require_admin,
    }

    const.LOGGER.debug(
        "Creating dashboard entry: url_path=%s, title=%s",
        url_path,
        title,
    )

    # Step 1: Save to DashboardsCollection (persists to storage)
    dashboards_collection = DashboardsCollection(hass)
    await dashboards_collection.async_load()

    existing_items = [
        item
        for item in _get_collection_items(dashboards_collection)
        if item.get(CONF_URL_PATH) == url_path
    ]

    if len(existing_items) > 1:
        await async_dedupe_choreops_dashboards(hass, url_path=url_path)
        await dashboards_collection.async_load()
        existing_items = [
            item
            for item in _get_collection_items(dashboards_collection)
            if item.get(CONF_URL_PATH) == url_path
        ]

    created_item: dict[str, Any] | None = None

    if existing_items:
        # Reuse existing entry to keep create path idempotent
        created_item = existing_items[-1]
        const.LOGGER.debug("Reusing existing dashboard entry: %s", url_path)
    else:
        try:
            await dashboards_collection.async_create_item(dashboard_config)
            const.LOGGER.debug("Dashboard entry saved to collection: %s", url_path)
        except HomeAssistantError as err:
            const.LOGGER.error("Failed to create dashboard entry: %s", err)
            raise DashboardSaveError(
                f"Failed to create dashboard entry: {err}"
            ) from err

        for item in _get_collection_items(dashboards_collection):
            if item.get(CONF_URL_PATH) == url_path:
                created_item = item
                break

    if not created_item:
        raise DashboardSaveError(f"Dashboard '{url_path}' not found in collection")

    const.LOGGER.debug("Retrieved dashboard item with id: %s", created_item.get("id"))

    # Step 2: Create LovelaceStorage and register in lovelace_data.dashboards
    if LOVELACE_DATA not in hass.data:
        raise DashboardSaveError("Lovelace not initialized")

    lovelace_data = hass.data[LOVELACE_DATA]

    # Create or reuse storage-mode dashboard object
    if url_path in lovelace_data.dashboards:
        current_dashboard = lovelace_data.dashboards[url_path]
        current_config = getattr(current_dashboard, "config", None)
        current_id = (
            current_config.get("id") if isinstance(current_config, dict) else None
        )
        if current_id == created_item.get("id"):
            lovelace_storage = current_dashboard
        else:
            lovelace_storage = LovelaceStorage(hass, created_item)
            lovelace_data.dashboards[url_path] = lovelace_storage
    else:
        lovelace_storage = LovelaceStorage(hass, created_item)
        lovelace_data.dashboards[url_path] = lovelace_storage

    const.LOGGER.debug("LovelaceStorage created for: %s", url_path)

    # Step 3: Register the frontend panel
    panel_exists = DATA_PANELS in hass.data and url_path in hass.data[DATA_PANELS]

    panel_kwargs: dict[str, Any] = {
        "frontend_url_path": url_path,
        "require_admin": require_admin,
        "config": {"mode": MODE_STORAGE},
        "update": panel_exists,
    }

    if show_in_sidebar:
        panel_kwargs["sidebar_title"] = title
        panel_kwargs["sidebar_icon"] = icon or DEFAULT_ICON

    async_register_built_in_panel(hass, LOVELACE_DOMAIN, **panel_kwargs)

    const.LOGGER.debug("Dashboard panel registered: %s", url_path)


async def _save_dashboard_config(
    hass: HomeAssistant,
    url_path: str,
    config: dict[str, Any],
) -> None:
    """Save dashboard config to Lovelace storage.

    Args:
        hass: Home Assistant instance.
        url_path: Dashboard URL path.
        config: Lovelace dashboard config (views, cards, etc.).
    """
    if LOVELACE_DATA not in hass.data:
        const.LOGGER.error("Lovelace not initialized - LOVELACE_DATA missing")
        raise DashboardSaveError("Lovelace not initialized")

    lovelace_data = hass.data[LOVELACE_DATA]

    const.LOGGER.debug(
        "Saving dashboard config: url_path=%s, available dashboards=%s",
        url_path,
        list(lovelace_data.dashboards.keys()),
    )

    if url_path not in lovelace_data.dashboards:
        const.LOGGER.error(
            "Dashboard '%s' not found after creation. Available: %s",
            url_path,
            list(lovelace_data.dashboards.keys()),
        )
        raise DashboardSaveError(f"Dashboard '{url_path}' not found after creation")

    dashboard = lovelace_data.dashboards[url_path]

    try:
        await dashboard.async_save(config)
        const.LOGGER.debug("Dashboard config saved successfully: %s", url_path)
    except HomeAssistantError as err:
        const.LOGGER.error("Failed to save dashboard config: %s", err)
        raise DashboardSaveError(f"Failed to save dashboard config: {err}") from err
