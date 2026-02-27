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


async def _ack_template_details_if_needed(
    hass: HomeAssistant,
    flow_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Continue through template details review when that step is shown."""
    if result.get("step_id") != const.OPTIONS_FLOW_STEP_DASHBOARD_TEMPLATE_DETAILS:
        return result

    return await hass.config_entries.options.async_configure(
        flow_id,
        user_input={const.CFOF_DASHBOARD_INPUT_TEMPLATE_DETAILS_ACK: True},
    )


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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["v0.5.4", "v0.5.3"],
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
        result = await _ack_template_details_if_needed(hass, flow_id, result)

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
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_create_dashboard.await_args.kwargs
    assert "include_prereleases" in kwargs
    assert kwargs["include_prereleases"] is (
        const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT
    )
    assert kwargs["pinned_release_tag"] is None


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
        result = await _ack_template_details_if_needed(hass, flow_id, result)

        assert (
            result.get("step_id")
            == const.OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES
        )
        assert mock_create_dashboard.await_count == 0

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_DEPENDENCY_BYPASS: False},
        )
        assert (
            result.get("step_id")
            == const.OPTIONS_FLOW_STEP_DASHBOARD_MISSING_DEPENDENCIES
        )
        assert result.get("errors", {}).get(const.CFOP_ERROR_BASE) == (
            const.TRANS_KEY_CFOF_DASHBOARD_DEPENDENCY_ACK_REQUIRED
        )
        assert mock_create_dashboard.await_count == 0

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
    """Create flow shows template details review by default."""
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
            result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_TEMPLATE_DETAILS
        )
        placeholders = result.get("description_placeholders", {})
        assert "Gamification (User)" in placeholders.get(
            const.PLACEHOLDER_DASHBOARD_TEMPLATE_DETAILS, ""
        )

        result = await hass.config_entries.options.async_configure(
            flow_id,
            user_input={const.CFOF_DASHBOARD_INPUT_TEMPLATE_DETAILS_ACK: True},
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
    assert "Selected templates are unavailable for generation" in str(
        result.get("errors", {}).get(const.CFOP_ERROR_BASE, "")
    )
    assert mock_create_dashboard.await_count == 0


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
        const.CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS,
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["v0.5.4", "v0.5.3"],
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
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "v0.5.3",
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
            return_value=["v0.5.4", "v0.5.3"],
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
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "v0.5.3",
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
            return_value=["v0.5.4", "v0.5.3"],
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
        const.CFOF_DASHBOARD_INPUT_TEMPLATE_DETAILS_REVIEW,
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
            "custom_components.choreops.helpers.dashboard_builder.async_dedupe_choreops_dashboards",
            return_value={},
        ),
        patch(
            "custom_components.choreops.helpers.dashboard_builder.discover_compatible_dashboard_release_tags",
            return_value=["v0.5.4", "v0.5.3"],
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
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE: const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: DEFAULT_ADMIN_TEMPLATE_ID,
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL,
                },
                const.CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: {
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: True,
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: False,
                    const.CFOF_DASHBOARD_INPUT_ICON: "mdi:clipboard-list",
                },
                const.CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: {
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: False,
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "v0.5.3",
                },
            },
        )
        result = await _ack_template_details_if_needed(hass, flow_id, result)

    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR
    kwargs = mock_update_dashboard.await_args.kwargs
    assert kwargs["pinned_release_tag"] == "v0.5.3"


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
            return_value=["v0.5.4", "v0.5.3"],
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
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "v0.5.3",
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
            return_value=["v0.5.4", "v0.5.3"],
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
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "v0.5.3",
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
            return_value=["v0.5.4", "v0.5.3"],
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
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: "v0.5.3",
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
