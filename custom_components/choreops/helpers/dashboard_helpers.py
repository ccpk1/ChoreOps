# File: helpers/dashboard_helpers.py
"""Dashboard generation helper functions for KidsChores.

Provides context building and template rendering support for generating
Lovelace dashboards via the KidsChores Options Flow.

All functions here require a `hass` object or interact with HA APIs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

from .. import const

if TYPE_CHECKING:
    from ..coordinator import KidsChoresDataCoordinator
    from ..type_defs import KidData


DASHBOARD_CONFIGURE_SECTION_KEYS = (
    const.CFOF_DASHBOARD_SECTION_KID_VIEWS,
    const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
    const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
    const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION,
)

_TEMPLATE_DISPLAY_LABELS: dict[str, str] = {
    const.DASHBOARD_STYLE_FULL: "Full",
    const.DASHBOARD_STYLE_MINIMAL: "Minimal",
    const.DASHBOARD_STYLE_COMPACT: "Compact",
    const.DASHBOARD_STYLE_ADMIN: "Admin",
}


def _humanize_template_key(style_key: str) -> str:
    """Convert template key to human-friendly title format."""
    normalized = style_key.replace("_", " ").replace("-", " ").strip()
    return normalized.title() if normalized else style_key


def _extract_template_metadata_title(style_key: str) -> str | None:
    """Return static display title for known template keys.

    This intentionally avoids runtime file I/O in the options flow path.
    """
    return _TEMPLATE_DISPLAY_LABELS.get(style_key)


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


class DashboardKidContext(TypedDict):
    """Minimal context for a kid in dashboard generation.

    The dashboard templates only need these two values - all other data
    (entity IDs, points, chores) is discovered at runtime via HA Jinja2
    using the `name` to find the dashboard_helper sensor.
    """

    name: str  # Exact display name (used in `{%- set name = '...' -%}`)
    slug: str  # URL-safe slug (used in `path:` only)


class DashboardContext(TypedDict):
    """Full context for dashboard template rendering.

    Passed to the Python Jinja2 environment with << >> delimiters.
    For kid dashboards, only `kid` is used.
    For admin dashboard, no context is needed (fully dynamic).
    """

    kid: DashboardKidContext


# ==============================================================================
# Context Builder Functions
# ==============================================================================


def build_kid_context(kid_name: str) -> DashboardKidContext:
    """Build minimal context for a single kid dashboard.

    Args:
        kid_name: The kid's exact display name from storage.

    Returns:
        DashboardKidContext with name and URL-safe slug.

    Example:
        >>> build_kid_context("Alice")
        {"name": "Alice", "slug": "alice"}
        >>> build_kid_context("María José")
        {"name": "María José", "slug": "maria_jose"}
    """
    return DashboardKidContext(
        name=kid_name,
        slug=slugify(kid_name),
    )


def build_dashboard_context(
    kid_name: str,
    *,
    template_profile: str | None = None,
) -> DashboardContext:
    """Build full context for dashboard template rendering.

    This is the dict passed to the Jinja2 template engine with << >> delimiters.

    Args:
        kid_name: The kid's exact display name from storage.
        template_profile: Optional template profile for future granular flows.
            Phase 2 scaffolding keeps context shape unchanged.

    Returns:
        DashboardContext ready for template rendering.

    Example:
        >>> ctx = build_dashboard_context("Alice")
        >>> ctx["kid"]["name"]
        'Alice'
        >>> ctx["kid"]["slug"]
        'alice'
    """
    _ = template_profile

    return DashboardContext(
        kid=build_kid_context(kid_name),
    )


def resolve_kid_template_profile(
    kid_name: str,
    default_style: str,
    kid_template_profiles: dict[str, str] | None = None,
) -> str:
    """Resolve template profile for a kid with safe fallback.

    Args:
        kid_name: Kid display name.
        default_style: Default selected style.
        kid_template_profiles: Optional per-kid profile mapping.

    Returns:
        Resolved style/profile for this kid.
    """
    if not kid_template_profiles:
        return default_style

    resolved = kid_template_profiles.get(kid_name, default_style)
    if resolved in const.DASHBOARD_STYLES:
        return resolved

    return default_style


def get_all_kid_names(coordinator: KidsChoresDataCoordinator) -> list[str]:
    """Get list of all kid names from coordinator.

    Args:
        coordinator: KidsChoresDataCoordinator instance.

    Returns:
        List of kid display names, sorted alphabetically.
    """
    kids_data = coordinator.kids_data
    names: list[str] = []
    for kid_info in kids_data.values():
        kid_info_typed: KidData = kid_info
        name = kid_info_typed.get(const.DATA_KID_NAME, "")
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
            value=const.DASHBOARD_STYLE_FULL,
            label=resolve_template_display_label(const.DASHBOARD_STYLE_FULL),
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_STYLE_MINIMAL,
            label=resolve_template_display_label(const.DASHBOARD_STYLE_MINIMAL),
        ),
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
            value=const.DASHBOARD_ADMIN_MODE_PER_KID,
            label=const.DASHBOARD_ADMIN_MODE_PER_KID,
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
            value=const.DASHBOARD_STYLE_ADMIN,
            label=resolve_template_display_label(const.DASHBOARD_STYLE_ADMIN),
        )
    ]


def build_dashboard_admin_view_visibility_options() -> list[selector.SelectOptionDict]:
    """Build visibility options for admin views."""
    return [
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
            label=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
        ),
        selector.SelectOptionDict(
            value=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS,
            label=const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS,
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


def build_dashboard_kid_options(
    coordinator: KidsChoresDataCoordinator,
) -> list[selector.SelectOptionDict]:
    """Build kid selection options for dashboard generator form.

    Args:
        coordinator: KidsChoresDataCoordinator instance.

    Returns:
        List of SelectOptionDict for kid multi-selector.
    """
    kid_names = get_all_kid_names(coordinator)
    return [selector.SelectOptionDict(value=name, label=name) for name in kid_names]


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
    coordinator: KidsChoresDataCoordinator,
    *,
    include_release_controls: bool,
    release_tags: list[str] | None = None,
    selected_kids_default: list[str] | None = None,
    template_profile_default: str = const.DASHBOARD_STYLE_FULL,
    admin_mode_default: str = const.DASHBOARD_ADMIN_MODE_GLOBAL,
    admin_template_global_default: str = const.DASHBOARD_STYLE_ADMIN,
    admin_template_per_kid_default: str = const.DASHBOARD_STYLE_ADMIN,
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
    kid_options = build_dashboard_kid_options(coordinator)
    kid_names = get_all_kid_names(coordinator)
    default_selected_kids = selected_kids_default or kid_names

    kid_view_fields: dict[vol.Marker, Any] = {
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

    if kid_options:
        kid_view_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_KID_SELECTION,
                default=default_selected_kids,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=kid_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_KID_SELECTION,
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
        const.DASHBOARD_ADMIN_MODE_PER_KID,
        const.DASHBOARD_ADMIN_MODE_BOTH,
    ):
        admin_view_fields[
            vol.Optional(
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_KID,
                default=admin_template_per_kid_default,
            )
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=build_dashboard_admin_template_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_PER_KID,
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
        vol.Optional(const.CFOF_DASHBOARD_SECTION_KID_VIEWS): section(
            vol.Schema(kid_view_fields)
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


def get_existing_kidschores_dashboards(
    hass: Any,
) -> list[dict[str, str]]:
    """Get list of existing KidsChores dashboards.

    Scans the lovelace dashboards collection for dashboards
    with url_path starting with 'kcd-' (our namespace).

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

    # Check dashboards dict for kcd-* entries
    for url_path in lovelace_data.dashboards:
        # Skip None or non-string keys
        if not url_path or not isinstance(url_path, str):
            continue
        if url_path.startswith("kcd-"):
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
    dashboards = get_existing_kidschores_dashboards(hass)

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
    }

    # Initialize all as not installed
    installed = dict.fromkeys(card_patterns, False)

    # Try to check lovelace resources
    try:
        # Try to get lovelace resources collection from data
        lovelace_resources = hass.data.get("lovelace_resources")

        if lovelace_resources is None:
            lovelace_resources = hass.data.get("lovelace")

        if lovelace_resources is None:
            const.LOGGER.debug("No lovelace data found in hass.data")
            return installed

        # Get all resources
        resources = []
        if hasattr(lovelace_resources, "resources"):
            # Try direct resources attribute (LovelaceData.resources)
            resources_obj = lovelace_resources.resources
            if hasattr(resources_obj, "async_items"):
                # ResourceStorageCollection.async_items() returns list directly (not coroutine)
                resources = resources_obj.async_items()
            elif hasattr(resources_obj, "items"):
                resources = list(resources_obj.items())
        elif hasattr(lovelace_resources, "async_items"):
            resources = lovelace_resources.async_items()
        elif hasattr(lovelace_resources, "items"):
            resources = lovelace_resources.items()

        const.LOGGER.debug(
            "Checking %d lovelace resources for custom cards", len(resources)
        )

        for resource in resources:
            resource_url = ""
            if isinstance(resource, dict):
                resource_url = str(resource.get("url", "")).lower()
            elif hasattr(resource, "url"):
                resource_url = str(resource.url).lower()

            for card_type, pattern in card_patterns.items():
                if pattern in resource_url:
                    installed[card_type] = True

    except (AttributeError, KeyError, TypeError) as ex:
        const.LOGGER.warning("Unable to check custom card installation: %s", ex)

    const.LOGGER.debug("Custom card status: %s", installed)
    return installed
