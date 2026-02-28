"""Options flow tests for dashboard release selection UX."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
import pytest
import voluptuous as vol

from custom_components.choreops import const
from custom_components.choreops.helpers import dashboard_helpers as dh
from custom_components.choreops.options_flow import ChoreOpsOptionsFlowHandler
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from collections.abc import Generator

    from homeassistant.core import HomeAssistant


DEFAULT_ASSIGNEE_TEMPLATE_ID = dh.get_default_assignee_template_id()
DEFAULT_ADMIN_TEMPLATE_ID = dh.get_default_admin_template_id()

if not hasattr(const, "CFOF_DASHBOARD_INPUT_CHECK_CARDS"):
    const.CFOF_DASHBOARD_INPUT_CHECK_CARDS = "dashboard_check_cards"


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


@pytest.fixture(autouse=True)
def _patch_dashboard_dependency_checks() -> Generator[None]:
    """Default dependency-check patch for dashboard options flow tests.

    Individual tests can override with nested patches when validating
    missing required/recommended behavior.
    """
    with (
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_dependency_ids_for_templates_from_definitions",
            return_value=(set(), set()),
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.check_dashboard_dependency_ids_installed",
            return_value={},
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def _patch_dashboard_release_asset_prepare() -> Generator[None]:
    """Default release-asset prep patch for Step 1 submit tests."""
    with patch(
        "custom_components.choreops.helpers.dashboard_helpers.async_prepare_dashboard_release_assets",
        return_value={
            "release_ref": "0.5.4",
            "manifest_asset": "{}",
            "template_definitions": [],
            "template_assets": {},
            "translation_assets": {"translations/en_dashboard.json": "{}"},
            "preference_assets": {},
        },
    ):
        yield


@pytest.fixture(autouse=True)
def _patch_dashboard_release_asset_apply() -> Generator[None]:
    """Default patch for persisting prepared release assets locally."""
    with patch(
        "custom_components.choreops.helpers.dashboard_helpers.async_apply_prepared_dashboard_release_assets",
        return_value=None,
    ):
        yield


@pytest.mark.asyncio
async def test_dashboard_release_asset_prep_cache_reuses_same_selection(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Flow-session release prep cache fetches once for same selection."""
    flow = ChoreOpsOptionsFlowHandler(scenario_minimal.config_entry)
    flow.hass = hass

    prepare_mock = AsyncMock(
        return_value={
            "release_ref": "0.5.4",
            "manifest_asset": "{}",
            "template_definitions": [],
            "template_assets": {},
            "translation_assets": {"translations/en_dashboard.json": "{}"},
            "preference_assets": {},
        }
    )

    with patch(
        "custom_components.choreops.helpers.dashboard_helpers.async_prepare_dashboard_release_assets",
        prepare_mock,
    ):
        await flow._async_prepare_dashboard_release_assets(
            const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
        )
        await flow._async_prepare_dashboard_release_assets(
            const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE,
        )

    assert prepare_mock.await_count == 1


@pytest.mark.asyncio
async def test_dashboard_step1_applies_selected_release_assets_locally(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Step 1 applies prepared release assets to local dashboard files."""
    config_entry = scenario_minimal.config_entry

    prepared_assets = {
        "release_ref": "0.5.4",
        "manifest_asset": '{"release_version": "0.5.4"}',
        "template_definitions": [],
        "template_assets": {},
        "translation_assets": {"translations/en_dashboard.json": "{}"},
        "preference_assets": {},
    }

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.async_prepare_dashboard_release_assets",
            return_value=prepared_assets,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.async_apply_prepared_dashboard_release_assets",
            new=AsyncMock(),
        ) as apply_mock,
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
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.4",
            },
        )

    assert result.get("step_id") == "dashboard_create"
    assert apply_mock.await_count == 1
    assert apply_mock.await_args_list[0].args[1] == prepared_assets


@pytest.mark.asyncio
async def test_dashboard_step1_returns_with_actionable_error_when_asset_prep_fails(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Step 1 submit returns to dashboard generator when release prep fails."""
    config_entry = scenario_minimal.config_entry

    with patch(
        "custom_components.choreops.helpers.dashboard_helpers.async_prepare_dashboard_release_assets",
        side_effect=HomeAssistantError("release outage"),
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
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
            },
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert result.get("errors", {}).get(const.CFOP_ERROR_BASE) == (
        const.TRANS_KEY_CFOF_DASHBOARD_RELEASE_ASSET_PREP_FAILED
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


def _section_field_default(
    schema: vol.Schema,
    section_key: str,
    field_key: str,
) -> Any:
    """Return default value for a nested section field in a voluptuous schema."""
    for marker, section_obj in schema.schema.items():
        marker_schema = getattr(marker, "schema", marker)
        if marker_schema != section_key:
            continue

        nested_schema = getattr(section_obj, "schema", None)
        if isinstance(nested_schema, vol.Schema):
            nested_dict = nested_schema.schema
        elif isinstance(nested_schema, dict):
            nested_dict = nested_schema
        else:
            return None

        for nested_marker in nested_dict:
            nested_marker_schema = getattr(nested_marker, "schema", nested_marker)
            if nested_marker_schema != field_key:
                continue
            default = getattr(nested_marker, "default", vol.UNDEFINED)
            if default is vol.UNDEFINED:
                return None
            if callable(default):
                return default()
            return default

    return None


async def _ack_template_details_if_needed(
    hass: HomeAssistant,
    flow_id: str,
    result: dict[str, Any],
    *,
    auto_submit_dependency_step: bool = True,
) -> dict[str, Any]:
    """Advance through dependency review step when shown in the dashboard flow."""

    if (
        auto_submit_dependency_step
        and result.get("step_id")
        == const.OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES
    ):
        schema_fields = _schema_field_names(result["data_schema"])
        if const.CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS not in schema_fields:
            return await hass.config_entries.options.async_configure(
                flow_id,
                user_input={},
            )

        placeholders = result.get("description_placeholders", {})
        missing_required_markdown = str(
            placeholders.get(
                const.PLACEHOLDER_DASHBOARD_MISSING_REQUIRED_DEPENDENCIES,
                "- None",
            )
        ).strip()
        bypass_required = missing_required_markdown != "- None"
        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS: bypass_required,
            },
        )

    return result


def test_dashboard_template_labels_are_human_friendly() -> None:
    """Template selector labels use metadata/humanized values instead of raw keys."""
    assignee_options = dh.build_dashboard_template_profile_options()
    admin_options = dh.build_dashboard_admin_template_options()

    assert any(
        str(option["value"]) == DEFAULT_ASSIGNEE_TEMPLATE_ID
        for option in assignee_options
    )
    assert any(
        str(option["value"]) == DEFAULT_ADMIN_TEMPLATE_ID for option in admin_options
    )

    for option in assignee_options + admin_options:
        value = str(option["value"])
        label = str(option["label"])
        assert label == dh.resolve_template_display_label(value)


def test_update_selection_labels_are_friendly_and_disambiguate_duplicates() -> None:
    """Update selector shows title first and always appends cod-path suffix."""
    options = [
        {"value": "cod-family", "label": "Family Chores (cod-family)"},
        {"value": "cod-family-2", "label": "Family Chores (cod-family-2)"},
        {"value": "cod-kids", "label": "Kids Board (cod-kids)"},
    ]

    with patch(
        "custom_components.choreops.helpers.dashboard_helpers.get_existing_choreops_dashboards",
        return_value=options,
    ):
        schema = dh.build_dashboard_update_selection_schema(object())

    assert schema is not None
    marker = next(iter(schema.schema))
    selector_value = schema.schema[marker]
    selector_config = selector_value.config
    rendered_options = selector_config.get("options", [])
    options_by_value = {
        str(option["value"]): str(option["label"]) for option in rendered_options
    }
    assert options_by_value["cod-kids"] == "Kids Board (cod-kids)"
    assert options_by_value["cod-family"] == "Family Chores (cod-family)"
    assert options_by_value["cod-family-2"] == "Family Chores (cod-family-2)"


def test_get_existing_dashboards_prefers_config_title_over_url_path() -> None:
    """Dashboard discovery uses dashboard config title for selector-friendly labels."""

    class _FakeDashboard:
        def __init__(self, config: dict[str, Any]) -> None:
            self.config = config

    class _FakeLovelaceData:
        def __init__(self) -> None:
            self.dashboards = {
                "cod-chores": _FakeDashboard({"title": "Chores"}),
            }

    class _FakeHass:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {
                "lovelace": _FakeLovelaceData(),
            }

    options = dh.get_existing_choreops_dashboards(_FakeHass())
    assert options == [{"value": "cod-chores", "label": "Chores (cod-chores)"}]


@pytest.mark.asyncio
async def test_dashboard_update_step_shows_release_controls(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Step 1 shows release controls while Step 3 keeps shared schema."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
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
        generator_fields = _schema_field_names(result["data_schema"])
        assert const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION in generator_fields

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_INPUT_ACTION: const.DASHBOARD_ACTION_UPDATE,
                const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
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
    assert const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION not in fields
    assert const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES not in fields
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY in fields


@pytest.mark.asyncio
async def test_dashboard_update_selection_preloads_selected_dashboard_icon_default(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Selecting an update target preloads Step 3 icon default from dashboard metadata."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_get_dashboard_update_metadata",
            return_value={
                "url_path": "kcd-chores",
                "title": "Chores",
                "icon": "mdi:star-circle",
            },
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
            },
        )
        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: "kcd-chores"},
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    icon_default = _section_field_default(
        result["data_schema"],
        const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
        const.CFOF_DASHBOARD_INPUT_ICON,
    )
    assert icon_default == "mdi:star-circle"


@pytest.mark.asyncio
async def test_dashboard_update_step_gracefully_handles_release_discovery_error(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update path continues when release discovery is unavailable."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            side_effect=HomeAssistantError("HTTP 404 fetching releases"),
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
                const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
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


@pytest.mark.asyncio
async def test_dashboard_create_approver_visibility_passes_linked_approver_users(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create path passes linked approver HA users when admin visibility uses approver scope."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_dependency_ids_for_templates_from_definitions",
            return_value=(set(), set()),
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.check_dashboard_dependency_ids_installed",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_ASSIGNEE: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        result = await _ack_template_details_if_needed(
            hass,
            flow_id,
            result,
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_create_dashboard.await_count == 1
    kwargs = mock_create_dashboard.await_args.kwargs
    assert kwargs["admin_mode"] == const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE
    assert kwargs["admin_view_visibility"] == (
        const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS
    )
    admin_visible_user_ids = kwargs.get("admin_visible_user_ids")
    assert isinstance(admin_visible_user_ids, list)
    assert len(admin_visible_user_ids) > 0


@pytest.mark.asyncio
async def test_dashboard_create_passes_release_parity_args_to_builder(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow forwards release selection args for builder parity."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_dependency_ids_for_templates_from_definitions",
            return_value=(set(), set()),
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.check_dashboard_dependency_ids_installed",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        result = await _ack_template_details_if_needed(
            hass,
            flow_id,
            result,
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_create_dashboard.await_args.kwargs
    assert "include_prereleases" in kwargs
    assert kwargs["include_prereleases"] is False
    prepared_assets = kwargs.get("prepared_release_assets")
    assert isinstance(prepared_assets, dict)
    assert kwargs["requested_release_selection"] == (
        const.DASHBOARD_RELEASE_MODE_CURRENT_INSTALLED
    )
    assert kwargs["pinned_release_tag"] == (
        await dh.async_get_local_dashboard_release_version(hass)
    )


@pytest.mark.asyncio
async def test_dashboard_create_latest_stable_uses_prepared_release_ref_as_pin(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow execution pins to the Step 1 prepared release_ref for latest stable."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_dependency_ids_for_templates_from_definitions",
            return_value=(set(), set()),
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.check_dashboard_dependency_ids_installed",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
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
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: const.DASHBOARD_RELEASE_MODE_LATEST_STABLE,
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        result = await _ack_template_details_if_needed(
            hass,
            flow_id,
            result,
        )

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_create_dashboard.await_args.kwargs
    assert kwargs["pinned_release_tag"] == "0.5.4"
    assert kwargs["requested_release_selection"] == (
        const.DASHBOARD_RELEASE_MODE_LATEST_STABLE
    )
    assert kwargs["resolution_reason"] == "latest_compatible"
    assert isinstance(kwargs["prepared_release_assets"], dict)


@pytest.mark.asyncio
async def test_dashboard_create_blocks_missing_required_template_dependencies(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow pauses at missing dependency helper until user acknowledges bypass."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
            mock_create_dashboard,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_dependency_ids_for_templates_from_definitions",
            return_value=({"ha-card:auto-entities"}, set()),
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.check_dashboard_dependency_ids_installed",
            return_value={"ha-card:auto-entities": False},
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        result = await _ack_template_details_if_needed(
            hass,
            flow_id,
            result,
            auto_submit_dependency_step=False,
        )

        assert (
            result.get("step_id")
            == const.OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES
        )
        assert mock_create_dashboard.await_count == 0

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS: False},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
        assert mock_create_dashboard.await_count == 0

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        assert (
            result.get("step_id")
            == const.OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS: True},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
        assert mock_create_dashboard.await_count == 1


@pytest.mark.asyncio
async def test_dashboard_create_continues_when_only_recommended_dependencies_missing(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow continues when only recommended dependencies are missing."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
            mock_create_dashboard,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_dependency_ids_for_templates_from_definitions",
            return_value=(set(), {"ha-card:mini-graph-card"}),
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.check_dashboard_dependency_ids_installed",
            return_value={"ha-card:mini-graph-card": False},
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_create_dashboard.await_count == 1


@pytest.mark.asyncio
async def test_dashboard_create_template_details_review_step_default_on(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow routes Step 3 submissions to dependency review."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )

        assert (
            result.get("step_id")
            == const.OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={},
        )
        assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
        assert mock_create_dashboard.await_count == 1


@pytest.mark.asyncio
async def test_dashboard_create_blocks_nonselectable_lifecycle_templates(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow blocks when selected templates are archived or unknown."""
    config_entry = scenario_minimal.config_entry
    mock_create_dashboard = AsyncMock(return_value="kcd-chores")

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
            mock_create_dashboard,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_helpers.get_nonselectable_template_ids_from_definitions",
            return_value=[DEFAULT_ASSIGNEE_TEMPLATE_ID],
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    assert (
        result.get("errors", {}).get(const.CFOP_ERROR_BASE)
        == const.TRANS_KEY_CFOF_DASHBOARD_NONSELECTABLE_TEMPLATES
    )
    assert mock_create_dashboard.await_count == 0


@pytest.mark.asyncio
async def test_dashboard_create_uses_sectioned_configure_schema(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create path uses the shared sectioned configure form."""
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
        const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
    ]

    fields = _schema_field_names(result["data_schema"])
    assert const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE in fields
    assert const.CFOF_DASHBOARD_INPUT_ADMIN_MODE in fields
    assert const.CFOF_DASHBOARD_INPUT_ICON in fields
    assert const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION not in fields
    assert const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES not in fields


@pytest.mark.asyncio
async def test_dashboard_create_fetches_release_tags_for_selector(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Create flow fetches compatible release tags for template version selector."""
    config_entry = scenario_minimal.config_entry

    with (
        patch(
            "custom_components.choreops.helpers.dashboard_builder.async_check_dashboard_exists",
            return_value=False,
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.0.1-beta.1"],
        ) as mock_discover_releases,
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
    assert mock_discover_releases.call_count >= 1


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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_choreops_dashboard_views",
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
                const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    assert mock_update_dashboard.await_count == 1
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["assignee_names"] == ["Zoë"]
    assert kwargs["admin_view_visibility"] == const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL


@pytest.mark.asyncio
async def test_dashboard_update_per_assignee_mode_submits_without_rerender_stall(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow submits when per-assignee mode uses existing template defaults."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_choreops_dashboard_views",
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
                const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["admin_mode"] == const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE


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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
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
        const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS,
        const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR,
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
    """Update flow executes against prepared effective release ref."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_choreops_dashboard_views",
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
                const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["pinned_release_tag"] == "0.5.4"
    assert kwargs["include_prereleases"] is False


@pytest.mark.asyncio
async def test_dashboard_update_passes_per_assignee_admin_mode_to_builder(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow forwards per-assignee admin mode so builder can apply layout changes."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_choreops_dashboard_views",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["admin_mode"] == const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE


def test_dashboard_builder_normalizes_admin_mode_aliases() -> None:
    """Builder normalization maps label-like values to canonical admin modes."""
    from custom_components.choreops.helpers import dashboard_builder as builder

    assert (
        builder._normalize_admin_mode("Per Assignee")
        == const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_choreops_dashboard_views",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:shield-star",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: True,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: False,
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["icon"] == "mdi:shield-star"
    assert kwargs["require_admin"] is True
    assert kwargs["show_in_sidebar"] is False


@pytest.mark.asyncio
async def test_dashboard_update_linked_approvers_visibility_submits(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Update flow with linked-approvers visibility submits and advances."""
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["0.5.4", "0.5.3"],
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.update_choreops_dashboard_views",
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
                const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: ["Zoë"],
                },
                const.CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: {
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "0.5.3",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["admin_view_visibility"] == (
        const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS
    )


@pytest.mark.asyncio
async def test_dashboard_configure_validation_no_assignees_and_no_admin(
    hass: HomeAssistant,
    scenario_minimal: SetupResult,
) -> None:
    """Step 2 blocks submit when no assignees and admin mode none."""
    config_entry = scenario_minimal.config_entry

    with patch(
        "custom_components.choreops.helpers.dashboard_builder.create_choreops_dashboard",
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
                const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: DEFAULT_ASSIGNEE_TEMPLATE_ID,
                const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_NONE,
                const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: [],
                const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
            },
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE
    assert result.get("errors") == {
        const.CFOP_ERROR_BASE: const.TRANS_KEY_CFOF_DASHBOARD_NO_ASSIGNEES_WITHOUT_ADMIN
    }
