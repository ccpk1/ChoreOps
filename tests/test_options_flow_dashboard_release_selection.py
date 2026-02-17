"""Options flow tests for dashboard release selection UX."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType
import pytest
import voluptuous as vol

from custom_components.choreops import const
from custom_components.choreops.helpers import dashboard_helpers as dh
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for options flow tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


def _schema_field_names(schema: vol.Schema) -> set[str]:
    """Return field names from a voluptuous schema, including section fields."""
    names: set[str] = set()

    def _collect_fields(schema_obj: Any) -> None:
        if isinstance(schema_obj, vol.Schema):
            _collect_fields(schema_obj.schema)
            return

        if isinstance(schema_obj, dict):
            for marker, value in schema_obj.items():
                marker_schema = getattr(marker, "schema", marker)
                if isinstance(marker_schema, str):
                    names.add(marker_schema)
                _collect_fields(value)
            return

        nested_schema = getattr(schema_obj, "schema", None)
        if nested_schema is not None and nested_schema is not schema_obj:
            _collect_fields(nested_schema)

    _collect_fields(schema)
    return names


def _schema_field_order(schema: vol.Schema) -> list[str]:
    """Return top-level field order from a voluptuous schema."""
    ordered: list[str] = []
    for marker in schema.schema:
        marker_schema = getattr(marker, "schema", marker)
        if isinstance(marker_schema, str):
            ordered.append(marker_schema)
    return ordered


def _section_field_order(schema: vol.Schema, section_key: str) -> list[str]:
    """Return nested field order for a section field in a voluptuous schema."""
    for marker, section_obj in schema.schema.items():
        marker_schema = getattr(marker, "schema", marker)
        if marker_schema != section_key:
            continue
        nested_schema = getattr(section_obj, "schema", None)
        if isinstance(nested_schema, vol.Schema):
            return [
                nested_marker_schema
                for nested_marker in nested_schema.schema
                if isinstance(
                    (
                        nested_marker_schema := getattr(
                            nested_marker, "schema", nested_marker
                        )
                    ),
                    str,
                )
            ]
        if isinstance(nested_schema, dict):
            return [
                nested_marker_schema
                for nested_marker in nested_schema
                if isinstance(
                    (
                        nested_marker_schema := getattr(
                            nested_marker, "schema", nested_marker
                        )
                    ),
                    str,
                )
            ]
    return []


def test_dashboard_template_labels_are_human_friendly() -> None:
    """Template selector labels use metadata/humanized values instead of raw keys."""
    kid_options = {
        str(option["value"]): str(option["label"])
        for option in dh.build_dashboard_template_profile_options()
    }
    admin_options = {
        str(option["value"]): str(option["label"])
        for option in dh.build_dashboard_admin_template_options()
    }

    assert kid_options[const.DASHBOARD_STYLE_FULL] == "Full"
    assert kid_options[const.DASHBOARD_STYLE_MINIMAL] == "Minimal"
    assert admin_options[const.DASHBOARD_STYLE_ADMIN] == "Admin"


@pytest.mark.asyncio
async def test_dashboard_update_step_shows_release_controls(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update path Step 2 includes release controls while create path does not."""
    config_entry = scenario_minimal.config_entry

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

    fields = _schema_field_names(result["data_schema"])
    assert const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION in fields
    assert const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES in fields
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY in fields


@pytest.mark.asyncio
async def test_dashboard_create_parent_visibility_passes_linked_parent_users(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create path passes linked parent HA users when admin visibility uses parent scope."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_kidschores_dashboard",
            mock_create_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_CREATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_create"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_NAME: "Chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_KID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_KID: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_create_dashboard.await_count == 1
    kwargs = mock_create_dashboard.await_args.kwargs
    assert kwargs["admin_mode"] == const.DASHBOARD_ADMIN_MODE_PER_KID
    assert kwargs["admin_view_visibility"] == (
        const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS
    )
    admin_visible_user_ids = kwargs.get("admin_visible_user_ids")
    assert isinstance(admin_visible_user_ids, list)
    assert len(admin_visible_user_ids) > 0


@pytest.mark.asyncio
async def test_dashboard_create_uses_sectioned_configure_schema(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create path uses the unified sectioned configure form (no legacy flat schema)."""
    config_entry = scenario_minimal.config_entry

    with patch(
        "custom_components.choreops.helpers.dashboard_builder.async_check_dashboard_exists",
        return_value=False,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_CREATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_create"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_NAME: "Chores"},
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    section_order = _schema_field_order(result["data_schema"])
    assert section_order == [
        const.CFOF_DASHBOARD_SECTION_KID_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
    ]

    fields = _schema_field_names(result["data_schema"])
    assert const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE in fields
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_MODE in fields
    assert const.CFOF_DASHBOARD_INPUT_ICON in fields
    assert const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION not in fields


@pytest.mark.asyncio
async def test_dashboard_create_blocks_existing_dashboard_name(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create step blocks when dashboard URL path already exists."""
    config_entry = scenario_minimal.config_entry

    with patch(
        "custom_components.choreops.helpers.dashboard_builder.async_check_dashboard_exists",
        return_value=True,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_CREATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_create"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_NAME: "Chores"},
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "dashboard_create"
    assert result.get("errors") == {
        const.CFOP_ERROR_BASE: const.TRANS_KEY_CFOF_DASHBOARD_EXISTS
    }


@pytest.mark.asyncio
async def test_dashboard_update_accepts_sectioned_configure_payload(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update configure accepts sectioned payload and forwards normalized values."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_update_dashboard.await_count == 1
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["kid_names"] == ["Zoë"]
    assert kwargs["admin_view_visibility"] == const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL


@pytest.mark.asyncio
async def test_dashboard_update_per_kid_mode_submits_without_rerender_stall(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow submits when per-kid mode uses existing template defaults."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_KID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["admin_mode"] == const.DASHBOARD_ADMIN_MODE_PER_KID


@pytest.mark.asyncio
async def test_dashboard_update_schema_uses_expected_section_and_access_field_order(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update schema keeps expected section order and dashboard configuration order."""
    config_entry = scenario_minimal.config_entry

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    section_order = _schema_field_order(result["data_schema"])
    assert section_order == [
        const.CFOF_DASHBOARD_SECTION_KID_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
        const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION,
    ]

    access_field_order = _section_field_order(
        result["data_schema"],
        const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
    )
    assert access_field_order == [
        const.CFOF_DASHBOARD_INPUT_ICON,
        const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN,
        const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR,
    ]


@pytest.mark.asyncio
async def test_dashboard_update_non_default_release_selection_passes_pinned_tag(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Explicit release selection forwards pinned release tag to update builder."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["pinned_release_tag"] == "KCD_v0.5.3"


@pytest.mark.asyncio
async def test_dashboard_update_passes_per_kid_admin_mode_to_builder(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow forwards per-kid admin mode so builder can apply layout changes."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )
        assert result.get("step_id") == "dashboard_update_select"

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_KID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["admin_mode"] == const.DASHBOARD_ADMIN_MODE_PER_KID


def test_dashboard_builder_normalizes_admin_mode_aliases() -> None:
    """Builder normalization maps label-like values to canonical admin modes."""
    from custom_components.choreops.helpers import dashboard_builder as builder

    assert (
        builder._normalize_admin_mode("Per Kid") == const.DASHBOARD_ADMIN_MODE_PER_KID
    )
    assert builder._normalize_admin_mode("shared") == const.DASHBOARD_ADMIN_MODE_GLOBAL
    assert builder._normalize_admin_mode("Both") == const.DASHBOARD_ADMIN_MODE_BOTH


@pytest.mark.asyncio
async def test_dashboard_update_passes_icon_and_access_metadata_to_builder(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow forwards icon/sidebar/admin flags for metadata updates."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:shield-star",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: True,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: False,
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["icon"] == "mdi:shield-star"
    assert kwargs["require_admin"] is True
    assert kwargs["show_in_sidebar"] is False


@pytest.mark.asyncio
async def test_dashboard_update_linked_parents_visibility_submits(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow with linked-parents visibility submits and advances."""
    config_entry = scenario_minimal.config_entry
    mock_update_dashboard = AsyncMock(return_value=2)

    update_select_schema = vol.Schema(
        {
            vol.Required(const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION): vol.In(
                ["kcd-chores"]
            )
        }
    )

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.build_dashboard_update_selection_schema",
            return_value=update_select_schema,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_kidschores_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["KCD_v0.5.4", "KCD_v0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_kidschores_dashboard_views",
            mock_update_dashboard,
        ),
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_KID_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                    const.CFOF_DASHBOARD_INPUT_KID_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: const.DASHBOARD_STYLE_ADMIN,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "KCD_v0.5.3",
                },
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["admin_view_visibility"] == (
        const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_PARENTS
    )


@pytest.mark.asyncio
async def test_dashboard_configure_validation_no_kids_and_no_admin(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Step 2 blocks submit when no kids and admin mode none."""
    config_entry = scenario_minimal.config_entry

    with patch(
        "custom_components.choreops.helpers.dashboard_builder.create_kidschores_dashboard",
        return_value="kcd-chores",
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_DASHBOARD_GENERATOR
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_CREATE,
                const.CFOF_DASHBOARD_INPUT_CHECK_CARDS: False,
            },
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_NAME: "Chores"},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: const.DASHBOARD_STYLE_FULL,
                const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                const.CFOF_DASHBOARD_INPUT_KID_SELECTION: [],
                const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
            },
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    assert result.get("errors") == {
        const.CFOP_ERROR_BASE: const.TRANS_KEY_CFOF_DASHBOARD_NO_KIDS_WITHOUT_ADMIN
    }
