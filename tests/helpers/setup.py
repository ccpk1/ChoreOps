"""Setup helpers for ChoreOps test configuration.

This module provides declarative test setup that navigates the config flow
based on scenario dictionaries, allowing tests to focus on behavior rather
than flow navigation boilerplate.

Example:
    # Instead of 50+ lines of config flow navigation:
    result = await setup_scenario(hass, mock_hass_users, {
        "points": {"label": "Stars", "icon": "mdi:star"},
        "assignees": [{"name": "Zoë", "ha_user": "assignee1"}],
        "approvers": [{"name": "Mom", "ha_user": "approver1", "assignees": ["Zoë"]}],
        "chores": [{"name": "Clean Room", "assigned_to": ["Zoë"], "points": 10}],
    })
    # Access: result.config_entry, result.coordinator, result.assignee_ids["Zoë"]

YAML-based setup:
    # Load scenario from YAML file:
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml"
    )
"""

from dataclasses import dataclass, field
from datetime import UTC
import logging
from pathlib import Path
import re
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import yaml

from custom_components.choreops import const
from custom_components.choreops.coordinator import ChoreOpsDataCoordinator
from tests.helpers.flow_test_helpers import FlowTestHelper

_LOGGER = logging.getLogger(__name__)

# Valid ha_user patterns: assignee1-assignee999, approver1-approver999
_VALID_HA_USER_PATTERN = re.compile(r"^(assignee|approver)\d+$")

# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class SetupResult:
    """Result from setup_scenario containing all configured entities.

    Attributes:
        config_entry: The created ConfigEntry
        coordinator: The ChoreOpsCoordinator instance
        assignee_ids: Canonical map of assignee display names to internal UUIDs
        approver_ids: Canonical map of approver display names to internal UUIDs
        assignee_ids: Compatibility alias for assignee_ids
        approver_ids: Compatibility alias for approver_ids
        chore_ids: Map of chore names to their internal UUIDs
        final_result: The final config flow result
    """

    config_entry: ConfigEntry
    coordinator: ChoreOpsDataCoordinator
    assignee_ids: dict[str, str] = field(default_factory=dict)
    approver_ids: dict[str, str] = field(default_factory=dict)
    chore_ids: dict[str, str] = field(default_factory=dict)
    reward_ids: dict[str, str] = field(default_factory=dict)
    penalty_ids: dict[str, str] = field(default_factory=dict)
    bonus_ids: dict[str, str] = field(default_factory=dict)
    badge_ids: dict[str, str] = field(default_factory=dict)
    achievement_ids: dict[str, str] = field(default_factory=dict)
    challenge_ids: dict[str, str] = field(default_factory=dict)
    final_result: ConfigFlowResult | None = None


# =============================================================================
# INTERNAL HELPERS
# =============================================================================


def _require_data_schema(result: ConfigFlowResult) -> Any:
    """Return the data_schema ensuring it exists."""
    data_schema = result.get("data_schema")
    assert data_schema is not None, f"data_schema missing from result: {result}"
    return data_schema


def _find_field_in_schema(data_schema: Any, field_key: str) -> Any | None:
    """Find a schema field in flat or sectioned voluptuous schemas."""

    def _match_field(schema_map: Any, key: str) -> Any | None:
        for schema_key, schema_value in schema_map.items():
            normalized_key = getattr(schema_key, "schema", schema_key)
            if normalized_key == key:
                return schema_value
        return None

    field = _match_field(data_schema.schema, field_key)
    if field is not None:
        return field

    for section_obj in data_schema.schema.values():
        nested_schema = getattr(section_obj, "schema", None)
        nested_map = getattr(nested_schema, "schema", None)
        if nested_map is None:
            continue
        field = _match_field(nested_map, field_key)
        if field is not None:
            return field

    return None


def _extract_assignee_ids_from_schema(result: ConfigFlowResult) -> list[str]:
    """Extract assignee IDs from the approver step schema.

    When on approver configuration step, the associated_assignees field contains
    the options with assignee UUIDs that were created in previous steps.

    Args:
        result: Config flow result on approver_count or approvers step

    Returns:
        List of assignee internal UUIDs available in the form
    """
    data_schema = _require_data_schema(result)
    associated_assignees_field = _find_field_in_schema(
        data_schema,
        const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
    )
    assert associated_assignees_field is not None, (
        "associated_assignees field not found in schema"
    )

    assignee_options = associated_assignees_field.config["options"]
    return [option["value"] for option in assignee_options]


def _extract_assignee_names_from_schema(result: ConfigFlowResult) -> list[str]:
    """Extract assignee names from the chore step schema.

    When on chore configuration step, the assigned_assignees field contains
    the options with assignee names for assignment.

    Args:
        result: Config flow result on chores step

    Returns:
        List of assignee names available in the form
    """
    data_schema = _require_data_schema(result)
    assigned_assignees_field = _find_field_in_schema(
        data_schema,
        const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS,
    )
    assert assigned_assignees_field is not None, (
        "assigned_assignees field not found in schema"
    )

    assignee_options = assigned_assignees_field.config["options"]
    return [option["value"] for option in assignee_options]


# =============================================================================
# STEP CONFIGURATION HELPERS
# =============================================================================


async def _configure_points_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    points_config: dict[str, Any],
) -> ConfigFlowResult:
    """Configure the points/system settings step.

    Args:
        hass: Home Assistant instance
        result: Current flow result on POINTS step
        points_config: Dict with optional keys:
            - label: Points label (default: "Points")
            - icon: Points icon (default: "mdi:star-outline")

    Returns:
        Updated flow result at USER_COUNT step
    """
    assert result.get("step_id") == const.CONFIG_FLOW_STEP_POINTS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_SYSTEM_INPUT_POINTS_LABEL: points_config.get("label", "Points"),
            const.CFOF_SYSTEM_INPUT_POINTS_ICON: points_config.get(
                "icon", "mdi:star-outline"
            ),
        },
    )

    assert result.get("step_id") == const.CONFIG_FLOW_STEP_USER_COUNT
    return result


async def _configure_assignee_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    mock_hass_users: dict[str, Any],
    assignee_config: dict[str, Any],
) -> ConfigFlowResult:
    """Configure a single assignable user step.

    Args:
        hass: Home Assistant instance
        result: Current flow result on USERS step
        mock_hass_users: Mock users dict from fixture
        assignee_config: Dict with keys:
            - name: Assignee name (required)
            - ha_user: Key in mock_hass_users (required)
            - dashboard_language: Language code (default: "en")
            - mobile_notify_service: str (default: "") - set to enable notifications

    Returns:
        Updated flow result
    """
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_USERS_INPUT_NAME: assignee_config["name"],
            const.CFOF_USERS_INPUT_HA_USER_ID: mock_hass_users[
                assignee_config["ha_user"]
            ].id,
            const.CFOF_USERS_INPUT_DASHBOARD_LANGUAGE: assignee_config.get(
                "dashboard_language", "en"
            ),
            const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE: assignee_config.get(
                "mobile_notify_service"
            )
            or const.SENTINEL_NO_SELECTION,
        },
    )


async def _configure_approver_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    mock_hass_users: dict[str, Any],
    approver_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure a single approver step.

    Args:
        hass: Home Assistant instance
        result: Current flow result on PARENTS step
        mock_hass_users: Mock users dict from fixture
        approver_config: Dict with keys:
            - name: Approver name (required)
            - ha_user: Key in mock_hass_users (required)
            - assignees: List of assignee names to associate (default: all)
            - mobile_notify_service: str (default: "") - set to enable notifications
            - allow_chore_assignment: bool (default: False) - creates shadow assignee
            - enable_chore_workflow: bool (default: False) - shadow assignee claim/disapprove
            - enable_gamification: bool (default: False) - shadow assignee points/badges
        assignee_name_to_id: Map of assignee names to their UUIDs

    Returns:
        Updated flow result
    """
    # Determine associated assignee IDs
    associated_assignee_names = approver_config.get(
        "assignees", list(assignee_name_to_id.keys())
    )
    associated_assignee_ids = [
        assignee_name_to_id[name]
        for name in associated_assignee_names
        if name in assignee_name_to_id
    ]

    # Mobile notify service handling - service presence enables notifications
    mobile_service = (
        approver_config.get("mobile_notify_service") or const.SENTINEL_NO_SELECTION
    )

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            const.CFOF_USERS_INPUT_NAME: approver_config["name"],
            const.CFOF_USERS_INPUT_HA_USER_ID: mock_hass_users[
                approver_config["ha_user"]
            ].id,
            const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: associated_assignee_ids,
            const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE: mobile_service,
            # Approver chore assignment fields (shadow assignee support)
            const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED: approver_config.get(
                "can_be_assigned",
                approver_config.get("allow_chore_assignment", False),
            ),
            const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW: approver_config.get(
                "enable_chore_workflow", False
            ),
            const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION: approver_config.get(
                "enable_gamification", False
            ),
            # Hard-fork role model: scenario "approvers" represent approver/admin users
            # unless explicitly overridden per scenario.
            const.CFOF_USERS_INPUT_CAN_APPROVE: approver_config.get(
                "can_approve", True
            ),
            const.CFOF_USERS_INPUT_CAN_MANAGE: approver_config.get("can_manage", True),
        },
    )


def _build_chore_notifications(chore_config: dict[str, Any]) -> list[str]:
    """Build notification list from chore config.

    Handles both formats:
    - notifications: ["notify_on_claim", "notify_on_approval"]  (list format)
    - notify_on_claim: true  (legacy boolean format)

    Args:
        chore_config: Chore configuration dict

    Returns:
        List of notification event constants
    """
    notifications = chore_config.get("notifications", [])

    # Also check for legacy boolean format (notify_on_claim: true)
    if chore_config.get("notify_on_claim", False):
        if const.DATA_CHORE_NOTIFY_ON_CLAIM not in notifications:
            notifications.append(const.DATA_CHORE_NOTIFY_ON_CLAIM)

    return notifications


async def _configure_chore_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    chore_config: dict[str, Any],
) -> ConfigFlowResult:
    """Configure a single chore step.

    Args:
        hass: Home Assistant instance
        result: Current flow result on CHORES step
        chore_config: Dict with keys:
            - name: Chore name (required)
            - assigned_to: List of assignee names (required)
            - points: Points value (default: 10.0)
            - description: Chore description (default: "")
            - icon: MDI icon (default: "mdi:check")
            - completion_criteria: "independent"/"shared_all"/"shared_first"
              (default: "independent")
            - recurring_frequency: "daily"/"weekly"/"monthly"/"custom"/"none"
              (default: "daily")
            - auto_approve: bool (default: False)
            - show_on_calendar: bool (default: True)
            - notify_on_claim: bool (default: True) - Send notification when claimed
            - labels: List of labels (default: [])
            - applicable_days: List of day codes (default: all days for daily)
            - notifications: List of notification events (default: [])
            - due_date: ISO date string (default: None)
            - custom_interval: int (default: None)
            - custom_interval_unit: str (default: None)
            - approval_reset_type: str (default: "automatic")
            - approval_reset_pending_claim_action: str (default: from const)
            - overdue_handling_type: str (default: "none")

    Returns:
        Updated flow result
    """
    recurring_freq = chore_config.get("recurring_frequency", "daily")
    # CFE-2026-001 F2: daily_multi is NOT supported in config_flow schema.
    # Use 'daily' as placeholder - frequency will be injected post-setup.
    if recurring_freq == const.FREQUENCY_DAILY_MULTI:
        recurring_freq = const.FREQUENCY_DAILY
    # applicable_days: if not specified, means "any day" (no restriction)
    applicable_days = chore_config.get("applicable_days", [])

    user_input = {
        const.CFOF_CHORES_INPUT_NAME: chore_config["name"],
        const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: chore_config["assigned_to"],
        const.CFOF_CHORES_INPUT_DEFAULT_POINTS: chore_config.get("points", 10.0),
        const.CFOF_CHORES_INPUT_DESCRIPTION: chore_config.get("description", ""),
        const.CFOF_CHORES_INPUT_ICON: chore_config.get("icon", "mdi:check"),
        const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: chore_config.get(
            "completion_criteria", "independent"
        ),
        const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: recurring_freq,
        const.CFOF_CHORES_INPUT_AUTO_APPROVE: chore_config.get("auto_approve", False),
        const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: chore_config.get(
            "show_on_calendar", True
        ),
        const.CFOF_CHORES_INPUT_LABELS: chore_config.get("labels", []),
        const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: applicable_days,
        const.CFOF_CHORES_INPUT_NOTIFICATIONS: _build_chore_notifications(chore_config),
        const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: chore_config.get(
            "approval_reset_type", const.DEFAULT_APPROVAL_RESET_TYPE
        ),
        const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: chore_config.get(
            "approval_reset_pending_claim_action",
            const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
        ),
        const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: chore_config.get(
            "overdue_handling_type", const.DEFAULT_OVERDUE_HANDLING_TYPE
        ),
    }

    # Add optional fields if provided
    # Handle relative due dates in multiple formats
    due_dt = None
    if "due_date_relative" in chore_config:
        # Simple format: "past" (yesterday) or "future" (tomorrow)
        from datetime import datetime, timedelta

        now = datetime.now(UTC)
        if chore_config["due_date_relative"] == "past":
            due_dt = now - timedelta(days=1)
        else:  # "future"
            due_dt = now + timedelta(days=1)
        # Set to 5 PM for consistency
        due_dt = due_dt.replace(hour=17, minute=0, second=0, microsecond=0)
    elif "due_date" in chore_config and chore_config["due_date"] is not None:
        due_date_val = chore_config["due_date"]
        # Handle relative format: "+1d17:00" (future) or "-3d17:00" (past)
        if isinstance(due_date_val, str) and due_date_val[0] in "+-":
            from datetime import datetime, timedelta
            import re

            match = re.match(r"([+-])(\d+)d(\d{2}):(\d{2})", due_date_val)
            if match:
                sign, days, hour, minute = match.groups()
                now = datetime.now(UTC)
                delta = timedelta(days=int(days))
                due_dt = now + delta if sign == "+" else now - delta
                due_dt = due_dt.replace(
                    hour=int(hour), minute=int(minute), second=0, microsecond=0
                )
            else:
                # Static date string - parse it
                from datetime import datetime

                try:
                    due_dt = datetime.fromisoformat(due_date_val)
                except ValueError:
                    due_dt = None
        else:
            # Static date string - parse it
            from datetime import datetime

            try:
                if isinstance(due_date_val, str):
                    due_dt = datetime.fromisoformat(due_date_val)
                else:
                    due_dt = due_date_val
            except (ValueError, TypeError):
                due_dt = None

    # If we have a due_dt, check if it's in the past and adjust
    if due_dt is not None:
        from datetime import datetime, timedelta

        now = datetime.now(UTC)
        if due_dt < now:
            # Past due date - adjust to 1 week from now, keeping same time
            original_dt = due_dt
            due_dt = now + timedelta(weeks=1)
            due_dt = due_dt.replace(
                hour=original_dt.hour,
                minute=original_dt.minute,
                second=0,
                microsecond=0,
            )
        user_input[const.CFOF_CHORES_INPUT_DUE_DATE] = due_dt.isoformat()
    if "custom_interval" in chore_config:
        user_input[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL] = chore_config[
            "custom_interval"
        ]
    if "custom_interval_unit" in chore_config:
        user_input[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT] = chore_config[
            "custom_interval_unit"
        ]
    # NOTE: daily_multi_times is NOT supported in config_flow schema.
    # It's handled via options_flow helper step (async_step_chores_daily_multi).
    # Post-setup injection happens in setup_scenario() after all chores are created.

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )


async def _configure_reward_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    reward_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure reward step using FlowTestHelper converter.

    Args:
        hass: Home Assistant instance
        result: Current flow result on REWARDS step
        reward_config: Dict with reward fields (name, cost, icon, etc)
        assignee_name_to_id: Mapping from assignee names to internal_ids

    Returns:
        Updated flow result
    """
    # Translate assignee names to IDs in assigned_to field
    reward_config = reward_config.copy()
    if "assigned_to" in reward_config:
        names = reward_config["assigned_to"]
        reward_config["assigned_to"] = [
            assignee_name_to_id[name] for name in names if name in assignee_name_to_id
        ]

    form_data = FlowTestHelper.build_reward_form_data(reward_config)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=form_data
    )


async def _configure_penalty_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    penalty_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure penalty step using FlowTestHelper converter.

    Args:
        hass: Home Assistant instance
        result: Current flow result on PENALTIES step
        penalty_config: Dict with penalty fields (name, points, icon, etc)
        assignee_name_to_id: Mapping from assignee names to internal_ids

    Returns:
        Updated flow result
    """
    # Translate assignee names to IDs in assigned_to field
    penalty_config = penalty_config.copy()
    if "assigned_to" in penalty_config:
        names = penalty_config["assigned_to"]
        penalty_config["assigned_to"] = [
            assignee_name_to_id[name] for name in names if name in assignee_name_to_id
        ]

    form_data = FlowTestHelper.build_penalty_form_data(penalty_config)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=form_data
    )


async def _configure_bonus_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    bonus_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure bonus step using FlowTestHelper converter.

    Args:
        hass: Home Assistant instance
        result: Current flow result on BONUSES step
        bonus_config: Dict with bonus fields (name, points, icon, etc)
        assignee_name_to_id: Mapping from assignee names to internal_ids

    Returns:
        Updated flow result
    """
    # Translate assignee names to IDs in assigned_to field
    bonus_config = bonus_config.copy()
    if "assigned_to" in bonus_config:
        names = bonus_config["assigned_to"]
        bonus_config["assigned_to"] = [
            assignee_name_to_id[name] for name in names if name in assignee_name_to_id
        ]

    form_data = FlowTestHelper.build_bonus_form_data(bonus_config)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=form_data
    )


async def _configure_badge_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    badge_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure badge step using FlowTestHelper converter.

    Args:
        hass: Home Assistant instance
        result: Current flow result on BADGES step
        badge_config: Dict with badge fields (name, type, assigned_to, etc)
        assignee_name_to_id: Mapping of assignee names to UUIDs for translation

    Returns:
        Updated flow result
    """
    # Translate assignee names to IDs in assigned_to field
    badge_config = badge_config.copy()
    if "assigned_to" in badge_config:
        names = badge_config["assigned_to"]
        badge_config["assigned_to"] = [
            assignee_name_to_id[name] for name in names if name in assignee_name_to_id
        ]

    form_data = FlowTestHelper.build_badge_form_data(badge_config)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=form_data
    )


async def _add_badge_via_options_flow(
    hass: HomeAssistant,
    entry_id: str,
    badge_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> None:
    """Add a badge via options flow (supports all badge types).

    Badge flow has 4 steps:
    1. Navigate to badges menu
    2. Select "Add" action
    3. Select badge type
    4. Submit badge details

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        badge_config: Dict with badge fields (name, type, assigned_to, etc)
        assignee_name_to_id: Mapping of assignee names to UUIDs for translation
    """
    from homeassistant.data_entry_flow import FlowResultType

    # Translate assignee names to IDs in assigned_to field
    badge_config = badge_config.copy()
    if "assigned_to" in badge_config:
        names = badge_config["assigned_to"]
        badge_config["assigned_to"] = [
            assignee_name_to_id[name] for name in names if name in assignee_name_to_id
        ]

    badge_type = badge_config.get("type", const.BADGE_TYPE_CUMULATIVE)
    badge_name = badge_config.get("name", "Unknown")

    # Step 1: Start options flow and navigate to badges menu
    result = await hass.config_entries.options.async_init(entry_id)
    assert result.get("type") == FlowResultType.FORM, (
        f"Badge '{badge_name}' Step 1 failed: expected FORM, got {result.get('type')}"
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_BADGES},
    )
    assert result.get("type") == FlowResultType.FORM, (
        f"Badge '{badge_name}' Step 1b failed: expected FORM, got {result}"
    )

    # Step 2: Select "Add" action
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.OPTIONS_FLOW_INPUT_MANAGE_ACTION: const.OPTIONS_FLOW_ACTIONS_ADD
        },
    )
    assert result.get("type") == FlowResultType.FORM, (
        f"Badge '{badge_name}' Step 2 failed: expected FORM, got {result}"
    )

    # Step 3: Select badge type
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={const.CFOF_BADGES_INPUT_TYPE: badge_type},
    )
    assert result.get("type") == FlowResultType.FORM, (
        f"Badge '{badge_name}' Step 3 failed: expected FORM, got {result}"
    )

    # Step 4: Submit badge details using FlowTestHelper
    form_data = FlowTestHelper.build_badge_form_data(badge_config)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=form_data,
    )
    # After successful add, should return to init menu
    assert result.get("type") == FlowResultType.FORM, (
        f"Badge '{badge_name}' Step 4 failed: expected FORM, got {result}"
    )
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_INIT, (
        f"Badge '{badge_name}' Step 4 failed: expected init, got {result.get('step_id')}"
    )


async def _configure_achievement_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    achievement_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure achievement step using FlowTestHelper converter.

    Args:
        hass: Home Assistant instance
        result: Current flow result on ACHIEVEMENTS step
        achievement_config: Dict with achievement fields (name, type, assigned_assignees, etc)
        assignee_name_to_id: Mapping from assignee names to internal_ids

    Returns:
        Updated flow result
    """
    # Translate assignee names to IDs in assigned_to field
    achievement_config = achievement_config.copy()
    if "assigned_to" in achievement_config:
        names = achievement_config["assigned_to"]
        achievement_config["assigned_to"] = [
            assignee_name_to_id[name] for name in names if name in assignee_name_to_id
        ]

    form_data = FlowTestHelper.build_achievement_form_data(achievement_config)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=form_data
    )


async def _configure_challenge_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    challenge_config: dict[str, Any],
    assignee_name_to_id: dict[str, str],
) -> ConfigFlowResult:
    """Configure challenge step using FlowTestHelper converter.

    Args:
        hass: Home Assistant instance
        result: Current flow result on CHALLENGES step
        challenge_config: Dict with challenge fields (name, type, assigned_assignees, etc)
        assignee_name_to_id: Mapping from assignee names to internal_ids (unused for challenges)

    Returns:
        Updated flow result
    """
    # NOTE: Unlike chores, challenges expect assignee NAMES (not UUIDs) in the form
    # because the challenge form's SelectSelector uses assignee names as options.
    # Do NOT convert names to IDs here.
    challenge_config = challenge_config.copy()

    # Adjust dates if they're in the past (same pattern as chore due dates)
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    for date_field in ["start_date", "end_date"]:
        if date_field in challenge_config:
            date_str = challenge_config[date_field]
            if isinstance(date_str, str):
                try:
                    date_dt = datetime.fromisoformat(date_str)
                    if date_dt < now:
                        # Past date - adjust to 1 week from now, keeping same time
                        adjusted_dt = now + timedelta(weeks=1)
                        adjusted_dt = adjusted_dt.replace(
                            hour=date_dt.hour,
                            minute=date_dt.minute,
                            second=0,
                            microsecond=0,
                        )
                        challenge_config[date_field] = adjusted_dt.isoformat()
                        const.LOGGER.warning(
                            "Challenge '%s' %s was in the past (%s), adjusted to %s",
                            challenge_config.get("name", "Unknown"),
                            date_field,
                            date_str,
                            challenge_config[date_field],
                        )
                except (ValueError, TypeError):
                    pass  # Invalid date format - let validator catch it

    form_data = FlowTestHelper.build_challenge_form_data(challenge_config)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=form_data
    )


async def _skip_remaining_counts(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    start_step: str,
) -> ConfigFlowResult:
    """Skip all remaining count steps from the given start step to FINISH.

    Args:
        hass: Home Assistant instance
        result: Current flow result
        start_step: Current step ID (e.g., BADGE_COUNT, CHORE_COUNT)

    Returns:
        Flow result at FINISH step
    """
    # Define the count steps sequence after chores
    skip_sequence = [
        (
            const.CONFIG_FLOW_STEP_BADGE_COUNT,
            const.CFOF_BADGES_INPUT_BADGE_COUNT,
            const.CONFIG_FLOW_STEP_REWARD_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_REWARD_COUNT,
            const.CFOF_REWARDS_INPUT_REWARD_COUNT,
            const.CONFIG_FLOW_STEP_PENALTY_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_PENALTY_COUNT,
            const.CFOF_PENALTIES_INPUT_PENALTY_COUNT,
            const.CONFIG_FLOW_STEP_BONUS_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_BONUS_COUNT,
            const.CFOF_BONUSES_INPUT_BONUS_COUNT,
            const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
            const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT,
            const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
        ),
        (
            const.CONFIG_FLOW_STEP_CHALLENGE_COUNT,
            const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT,
            const.CONFIG_FLOW_STEP_FINISH,
        ),
    ]

    # Find starting point in sequence
    started = False
    for step_id, input_key, next_step in skip_sequence:
        if result.get("step_id") == step_id:
            started = True
        if started and result.get("step_id") == step_id:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={input_key: 0}
            )
            assert result.get("step_id") == next_step

    return result


# =============================================================================
# MAIN SETUP FUNCTION
# =============================================================================


async def setup_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
    scenario: dict[str, Any],
) -> SetupResult:
    """Set up a complete ChoreOps scenario via config flow.

    This function navigates the entire config flow based on a declarative
    scenario dictionary, creating the specified assignees, approvers, and chores.

    Args:
        hass: Home Assistant instance
        mock_hass_users: Mock users dictionary from fixture
        scenario: Configuration dict with optional keys:
            - points: {"label": str, "icon": str}
            - assignees: List of assignee configs (see _configure_assignee_step)
            - approvers: List of approver configs (see _configure_approver_step)
            - chores: List of chore configs (see _configure_chore_step)

    Returns:
        SetupResult with config_entry, coordinator, and ID mappings

    Example:
        result = await setup_scenario(hass, mock_hass_users, {
            "points": {"label": "Stars", "icon": "mdi:star"},
            "assignees": [
                {"name": "Zoë", "ha_user": "assignee1"},
                {"name": "Max", "ha_user": "assignee2"},
            ],
            "approvers": [
                {"name": "Mom", "ha_user": "approver1", "assignees": ["Zoë", "Max"]},
            ],
            "chores": [
                {"name": "Clean Room", "assigned_to": ["Zoë"], "points": 15},
                {"name": "Do Dishes", "assigned_to": ["Zoë", "Max"], "points": 10},
            ],
        })

        # Access created entities:
        assignee_id = result.assignee_ids["Zoë"]
        chore_id = result.chore_ids["Clean Room"]
        coordinator = result.coordinator
    """
    assignees_config = scenario.get("assignees", [])
    approvers_config = scenario.get("approvers", [])
    chores_config = scenario.get("chores", [])
    badges_config = scenario.get("badges", [])
    rewards_config = scenario.get("rewards", [])
    penalties_config = scenario.get("penalties", [])
    bonuses_config = scenario.get("bonuses", [])
    achievements_config = scenario.get("achievements", [])
    challenges_config = scenario.get("challenges", [])
    points_config = scenario.get("points", {})

    assignee_name_to_id: dict[str, str] = {}
    approver_name_to_id: dict[str, str] = {}
    chore_name_to_id: dict[str, str] = {}
    badge_name_to_id: dict[str, str] = {}
    reward_name_to_id: dict[str, str] = {}
    penalty_name_to_id: dict[str, str] = {}
    bonus_name_to_id: dict[str, str] = {}
    achievement_name_to_id: dict[str, str] = {}
    challenge_name_to_id: dict[str, str] = {}

    # -----------------------------------------------------------------
    # Start config flow
    # Note: No mock of async_setup_entry - we want real setup to run
    # so that coordinator and hass.data are properly populated
    # -----------------------------------------------------------------
    result = await hass.config_entries.flow.async_init(
        const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.CONFIG_FLOW_STEP_DATA_RECOVERY

    # Skip data recovery (fresh start)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"backup_selection": "start_fresh"}
    )
    assert result.get("step_id") == const.CONFIG_FLOW_STEP_INTRO

    # Skip intro
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result.get("step_id") == const.CONFIG_FLOW_STEP_POINTS

    # -----------------------------------------------------------------
    # Configure points
    # -----------------------------------------------------------------
    result = await _configure_points_step(hass, result, points_config)

    # -----------------------------------------------------------------
    # Configure users (single count step for assignable + approver users)
    # -----------------------------------------------------------------
    assignee_count = len(assignees_config)
    approver_count = len(approvers_config)
    total_user_count = assignee_count + approver_count

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_USERS_INPUT_COUNT: total_user_count},
    )

    if total_user_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_USERS

        for i, assignee_config in enumerate(assignees_config):
            result = await _configure_assignee_step(
                hass, result, mock_hass_users, assignee_config
            )

            if i < assignee_count - 1 or approver_count > 0:
                # More users to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_USERS
            else:
                # Last user - should advance to chore count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHORE_COUNT

        # Note: assignee IDs will be extracted after we enter the PARENTS step
        # (they're embedded in the associated_assignees selector, not available here)
    elif total_user_count == 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHORE_COUNT

    if approver_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_USERS

        # NOW extract assignee IDs from the PARENTS step schema
        # (only available when on actual approvers form, not approver_count form)
        if assignee_count > 0:
            actual_assignee_ids = _extract_assignee_ids_from_schema(result)
            for j, assignee_config in enumerate(assignees_config):
                if j < len(actual_assignee_ids):
                    assignee_name_to_id[assignee_config["name"]] = actual_assignee_ids[
                        j
                    ]

        for i, approver_config in enumerate(approvers_config):
            result = await _configure_approver_step(
                hass, result, mock_hass_users, approver_config, assignee_name_to_id
            )

            if i < approver_count - 1:
                # More approvers to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_USERS
            else:
                # Last approver - should advance to chore count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHORE_COUNT
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHORE_COUNT

    # -----------------------------------------------------------------
    # Configure chores
    # -----------------------------------------------------------------
    chore_count = len(chores_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_CHORES_INPUT_CHORE_COUNT: chore_count},
    )

    if chore_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHORES

        for i, chore_config in enumerate(chores_config):
            result = await _configure_chore_step(hass, result, chore_config)

            if i < chore_count - 1:
                # More chores to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHORES
            else:
                # Last chore - should advance to badge count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_BADGE_COUNT
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_BADGE_COUNT

    # -----------------------------------------------------------------
    # Configure badges - SKIP in config flow (only cumulative badges work)
    # Badges will be added via options flow after setup completes
    # -----------------------------------------------------------------
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_BADGES_INPUT_BADGE_COUNT: 0},
    )
    assert result.get("step_id") == const.CONFIG_FLOW_STEP_REWARD_COUNT

    # -----------------------------------------------------------------
    # Configure rewards
    # -----------------------------------------------------------------
    reward_count = len(rewards_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_REWARDS_INPUT_REWARD_COUNT: reward_count},
    )

    if reward_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_REWARDS

        for i, reward_config in enumerate(rewards_config):
            result = await _configure_reward_step(
                hass, result, reward_config, assignee_name_to_id
            )

            if i < reward_count - 1:
                # More rewards to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_REWARDS
            else:
                # Last reward - should advance to penalty count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_PENALTY_COUNT
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_PENALTY_COUNT

    # -----------------------------------------------------------------
    # Configure penalties
    # -----------------------------------------------------------------
    penalty_count = len(penalties_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_PENALTIES_INPUT_PENALTY_COUNT: penalty_count},
    )

    if penalty_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_PENALTIES

        for i, penalty_config in enumerate(penalties_config):
            result = await _configure_penalty_step(
                hass, result, penalty_config, assignee_name_to_id
            )

            if i < penalty_count - 1:
                # More penalties to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_PENALTIES
            else:
                # Last penalty - should advance to bonus count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_BONUS_COUNT
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_BONUS_COUNT

    # -----------------------------------------------------------------
    # Configure bonuses
    # -----------------------------------------------------------------
    bonus_count = len(bonuses_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_BONUSES_INPUT_BONUS_COUNT: bonus_count},
    )

    if bonus_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_BONUSES

        for i, bonus_config in enumerate(bonuses_config):
            result = await _configure_bonus_step(
                hass, result, bonus_config, assignee_name_to_id
            )

            if i < bonus_count - 1:
                # More bonuses to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_BONUSES
            else:
                # Last bonus - should advance to achievement count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT

    # -----------------------------------------------------------------
    # Configure achievements
    # -----------------------------------------------------------------
    achievement_count = len(achievements_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: achievement_count},
    )

    if achievement_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_ACHIEVEMENTS

        for i, achievement_config in enumerate(achievements_config):
            result = await _configure_achievement_step(
                hass, result, achievement_config, assignee_name_to_id
            )

            if i < achievement_count - 1:
                # More achievements to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_ACHIEVEMENTS
            else:
                # Last achievement - should advance to challenge count
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHALLENGE_COUNT
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHALLENGE_COUNT

    # -----------------------------------------------------------------
    # Configure challenges
    # -----------------------------------------------------------------
    challenge_count = len(challenges_config)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={const.CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: challenge_count},
    )

    if challenge_count > 0:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHALLENGES

        for i, challenge_config in enumerate(challenges_config):
            result = await _configure_challenge_step(
                hass, result, challenge_config, assignee_name_to_id
            )

            if i < challenge_count - 1:
                # More challenges to configure
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_CHALLENGES
            else:
                # Last challenge - should advance to finish
                assert result.get("step_id") == const.CONFIG_FLOW_STEP_FINISH
    else:
        assert result.get("step_id") == const.CONFIG_FLOW_STEP_FINISH

    # -----------------------------------------------------------------
    # Finish config flow
    # -----------------------------------------------------------------
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    config_entry = result.get("result")
    assert config_entry is not None, "Config entry not created"

    # -------------------------------------------------------------------------
    # Wait for integration setup to complete
    # CREATE_ENTRY triggers async_setup_entry automatically
    # -------------------------------------------------------------------------
    await hass.async_block_till_done()

    # Get coordinator from config entry runtime_data
    coordinator = config_entry.runtime_data

    # -------------------------------------------------------------------------
    # Add badges via options flow (supports all badge types)
    # Config flow only supports cumulative badges, so we add all via options
    # -------------------------------------------------------------------------
    if badges_config:
        for badge_config in badges_config:
            await _add_badge_via_options_flow(
                hass, config_entry.entry_id, badge_config, assignee_name_to_id
            )
            await hass.async_block_till_done()
        await hass.async_block_till_done()
        # IMPORTANT: Get fresh coordinator reference after badge adds
        # Each badge add triggers a config entry reload, creating a new coordinator
        coordinator = config_entry.runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # -------------------------------------------------------------------------
    # Map names to IDs from coordinator data
    # -------------------------------------------------------------------------
    # Update assignee IDs from coordinator (they should match but let's be sure)
    for assignee_id, assignee_data in coordinator.assignees_data.items():
        assignee_name = assignee_data.get(const.DATA_USER_NAME)
        if assignee_name:
            assignee_name_to_id[assignee_name] = assignee_id

    # Map approver names to IDs
    for approver_id, approver_data in coordinator.approvers_data.items():
        approver_name = approver_data.get(const.DATA_USER_NAME)
        if approver_name:
            approver_name_to_id[approver_name] = approver_id

    # Map chore names to IDs
    for chore_id, chore_data in coordinator.chores_data.items():
        chore_name = chore_data.get(const.DATA_CHORE_NAME)
        if chore_name:
            chore_name_to_id[chore_name] = chore_id

    # -------------------------------------------------------------------------
    # CFE-2026-001 F2: Post-setup injection of daily_multi frequency and times
    # The config_flow doesn't support daily_multi in its schema (it's
    # handled via options_flow helper step). For test scenarios, we inject
    # both the frequency and times directly into coordinator chore data.
    # -------------------------------------------------------------------------
    chores_config = scenario.get("chores", [])
    for chore_config in chores_config:
        chore_name = chore_config.get("name")
        if not chore_name or chore_name not in chore_name_to_id:
            continue
        chore_id = chore_name_to_id[chore_name]
        chore_data = coordinator.chores_data.get(chore_id)
        if not chore_data:
            continue

        # Inject daily_multi frequency if specified
        if chore_config.get("recurring_frequency") == const.FREQUENCY_DAILY_MULTI:
            chore_data[const.DATA_CHORE_RECURRING_FREQUENCY] = (
                const.FREQUENCY_DAILY_MULTI
            )

        # Inject daily_multi_times if specified
        if "daily_multi_times" in chore_config:
            chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = chore_config[
                "daily_multi_times"
            ]
    # Persist after any daily_multi injections
    if any(
        c.get("recurring_frequency") == const.FREQUENCY_DAILY_MULTI
        or "daily_multi_times" in c
        for c in chores_config
    ):
        coordinator._persist()

    # Map badge names to IDs
    for badge_id, badge_data in coordinator.badges_data.items():
        badge_name = badge_data.get(const.DATA_BADGE_NAME)
        if badge_name:
            badge_name_to_id[badge_name] = badge_id

    # Map reward names to IDs
    for reward_id, reward_data in coordinator.rewards_data.items():
        reward_name = reward_data.get(const.DATA_REWARD_NAME)
        if reward_name:
            reward_name_to_id[reward_name] = reward_id

    # Map penalty names to IDs
    for penalty_id, penalty_data in coordinator.penalties_data.items():
        penalty_name = penalty_data.get(const.DATA_PENALTY_NAME)
        if penalty_name:
            penalty_name_to_id[penalty_name] = penalty_id

    # Map bonus names to IDs
    for bonus_id, bonus_data in coordinator.bonuses_data.items():
        bonus_name = bonus_data.get(const.DATA_BONUS_NAME)
        if bonus_name:
            bonus_name_to_id[bonus_name] = bonus_id

    # Map achievement names to IDs
    for achievement_id, achievement_data in coordinator.achievements_data.items():
        achievement_name = achievement_data.get(const.DATA_ACHIEVEMENT_NAME)
        if achievement_name:
            achievement_name_to_id[achievement_name] = achievement_id

    # Map challenge names to IDs
    for challenge_id, challenge_data in coordinator.challenges_data.items():
        challenge_name = challenge_data.get(const.DATA_CHALLENGE_NAME)
        if challenge_name:
            challenge_name_to_id[challenge_name] = challenge_id

    # -------------------------------------------------------------------------
    # CRITICAL: Refresh coordinator to update sensor states with button entity IDs
    # After all platforms are set up, sensors need to re-write their state
    # to include button entity IDs that may have been registered after sensors.
    # Without this, sensor attributes may have None for button entity IDs.
    # -------------------------------------------------------------------------
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    return SetupResult(
        config_entry=config_entry,
        coordinator=coordinator,
        assignee_ids=assignee_name_to_id,
        approver_ids=approver_name_to_id,
        chore_ids=chore_name_to_id,
        badge_ids=badge_name_to_id,
        reward_ids=reward_name_to_id,
        penalty_ids=penalty_name_to_id,
        bonus_ids=bonus_name_to_id,
        achievement_ids=achievement_name_to_id,
        challenge_ids=challenge_name_to_id,
        final_result=result,
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def setup_minimal_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
    assignee_name: str = "Zoë",
    approver_name: str = "Mom",
    chore_name: str = "Clean Room",
    chore_points: float = 10.0,
) -> SetupResult:
    """Set up a minimal scenario with 1 assignee, 1 approver, 1 chore.

    This is a convenience wrapper around setup_scenario for simple test cases.

    Args:
        hass: Home Assistant instance
        mock_hass_users: Mock users dictionary from fixture
        assignee_name: Name for the assignee (default: "Zoë")
        approver_name: Name for the approver (default: "Mom")
        chore_name: Name for the chore (default: "Clean Room")
        chore_points: Points for the chore (default: 10.0)

    Returns:
        SetupResult with created entities
    """
    return await setup_scenario(
        hass,
        mock_hass_users,
        {
            "assignees": [{"name": assignee_name, "ha_user": "assignee1"}],
            "approvers": [{"name": approver_name, "ha_user": "approver1"}],
            "chores": [
                {
                    "name": chore_name,
                    "assigned_to": [assignee_name],
                    "points": chore_points,
                }
            ],
        },
    )


async def setup_multi_assignee_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
    assignee_names: list[str] | None = None,
    approver_name: str = "Mom",
    shared_chore_name: str = "Shared Chore",
) -> SetupResult:
    """Set up a scenario with multiple assignees sharing chores.

    Args:
        hass: Home Assistant instance
        mock_hass_users: Mock users dictionary from fixture
        assignee_names: List of assignee names (default: ["Zoë", "Max"])
        approver_name: Name for the approver (default: "Mom")
        shared_chore_name: Name for the shared chore (default: "Shared Chore")

    Returns:
        SetupResult with created entities
    """
    if assignee_names is None:
        assignee_names = ["Zoë", "Max"]

    assignees = [
        {"name": name, "ha_user": f"assignee{i + 1}"}
        for i, name in enumerate(assignee_names)
    ]

    return await setup_scenario(
        hass,
        mock_hass_users,
        {
            "assignees": assignees,
            "approvers": [{"name": approver_name, "ha_user": "approver1"}],
            "chores": [
                {
                    "name": shared_chore_name,
                    "assigned_to": assignee_names,
                    "points": 15.0,
                    "completion_criteria": "shared_all",
                }
            ],
        },
    )


# =============================================================================
# YAML-BASED SETUP
# =============================================================================


def _validate_ha_user_fields(scenario: dict[str, Any]) -> None:
    """Validate that ha_user fields use standardized keys.

    ha_user must match pattern: assignee1, assignee2, ..., approver1, approver2, ...
    These keys correspond to entries in the mock_hass_users fixture.

    The 'name' field can contain any Unicode characters - only ha_user is restricted.

    Raises:
        ValueError: If invalid ha_user values are found, with detailed error message.
    """
    invalid_entries: list[str] = []

    # Check assignees
    for assignee in scenario.get("assignees", []):
        ha_user = assignee.get("ha_user", "")
        if not _VALID_HA_USER_PATTERN.match(ha_user):
            invalid_entries.append(
                f"Assignee '{assignee.get('name', 'unknown')}' has invalid ha_user: '{ha_user}'"
            )

    # Check approvers
    for approver in scenario.get("approvers", []):
        ha_user = approver.get("ha_user", "")
        if not _VALID_HA_USER_PATTERN.match(ha_user):
            invalid_entries.append(
                f"Approver '{approver.get('name', 'unknown')}' has invalid ha_user: '{ha_user}'"
            )

    if invalid_entries:
        error_msg = (
            "Scenario YAML has invalid ha_user values. "
            "ha_user must use standardized keys like 'assignee1', 'assignee2', 'approver1', 'approver2' "
            "(matching mock_hass_users fixture keys). "
            "The 'name' field can contain any characters.\n\n"
            "Invalid entries:\n" + "\n".join(f"  - {e}" for e in invalid_entries)
        )
        _LOGGER.error(error_msg)
        raise ValueError(error_msg)


def _transform_yaml_to_scenario(yaml_data: dict[str, Any]) -> dict[str, Any]:
    """Transform YAML data to setup_scenario() format.

    The YAML format uses more descriptive keys that need to be mapped to
    the setup_scenario() expected format.

    YAML format (example):
        system:
          points_label: "Star Points"
          points_icon: "mdi:star"
        assignees:
          - name: "Zoë"
            ha_user: "assignee1"
            dashboard_language: "en"
        approvers:
          - name: "Mom"
            ha_user: "approver1"
            assignees: ["Zoë"]
        chores:
          - name: "Clean Room"
            assigned_to: ["Zoë"]
            points: 10.0

    setup_scenario format:
        points: {"label": "Star Points", "icon": "mdi:star"}
        assignees: [{"name": "Zoë", "ha_user": "assignee1", ...}]
        approvers: [{"name": "Mom", "ha_user": "approver1", "assignees": ["Zoë"]}]
        chores: [{"name": "Clean Room", "assigned_to": ["Zoë"], "points": 10.0}]

    Args:
        yaml_data: Raw YAML data from file

    Returns:
        Transformed scenario dict for setup_scenario()
    """
    scenario: dict[str, Any] = {}

    # Transform system -> points
    system = yaml_data.get("system", {})
    if system:
        scenario["points"] = {
            "label": system.get("points_label", "Points"),
            "icon": system.get("points_icon", "mdi:star-outline"),
        }

    # Assignees: direct passthrough (keys already match)
    assignees = yaml_data.get("assignees", [])
    if assignees:
        scenario["assignees"] = assignees

    # Approvers: direct passthrough (keys already match)
    approvers = yaml_data.get("approvers", [])
    if approvers:
        scenario["approvers"] = approvers

    # Chores: direct passthrough (keys already match)
    chores = yaml_data.get("chores", [])
    if chores:
        scenario["chores"] = chores

    # Badges: direct passthrough (keys already match)
    badges = yaml_data.get("badges", [])
    if badges:
        scenario["badges"] = badges

    # Rewards: direct passthrough (keys already match)
    rewards = yaml_data.get("rewards", [])
    if rewards:
        scenario["rewards"] = rewards

    # Penalties: direct passthrough (keys already match)
    penalties = yaml_data.get("penalties", [])
    if penalties:
        scenario["penalties"] = penalties

    # Bonuses: direct passthrough (keys already match)
    bonuses = yaml_data.get("bonuses", [])
    if bonuses:
        scenario["bonuses"] = bonuses

    # Achievements: direct passthrough (keys already match)
    achievements = yaml_data.get("achievements", [])
    if achievements:
        scenario["achievements"] = achievements

    # Challenges: direct passthrough (keys already match)
    challenges = yaml_data.get("challenges", [])
    if challenges:
        scenario["challenges"] = challenges

    # Validate ha_user fields use standardized keys
    _validate_ha_user_fields(scenario)

    return scenario


async def setup_from_yaml(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
    yaml_path: str | Path,
) -> SetupResult:
    """Set up a ChoreOps scenario from a YAML file.

    This function loads a scenario definition from YAML and passes it to
    setup_scenario() for config flow navigation.

    Args:
        hass: Home Assistant instance
        mock_hass_users: Mock users dictionary from fixture
        yaml_path: Path to YAML scenario file (absolute or relative to workspace)

    Returns:
        SetupResult with config_entry, coordinator, and ID mappings

    Example:
        result = await setup_from_yaml(
            hass,
            mock_hass_users,
            "tests/scenarios/scenario_full.yaml"
        )

        # Access created entities:
        assignee_id = result.assignee_ids["Zoë"]
        chore_id = result.chore_ids["Feed the cåts"]
        coordinator = result.coordinator

    YAML File Format:
        system:
          points_label: "Star Points"
          points_icon: "mdi:star"
        assignees:
          - name: "Zoë"
            ha_user: "assignee1"  # Key in mock_hass_users fixture
        approvers:
          - name: "Mom"
            ha_user: "approver1"  # Key in mock_hass_users fixture
            assignees: ["Zoë"]  # List of assignee names to associate
        chores:
          - name: "Clean Room"
            assigned_to: ["Zoë"]  # List of assignee names
            points: 10.0
            completion_criteria: "independent"  # or "shared_all", "shared_first"
    """
    # Resolve path
    path = Path(yaml_path)
    if not path.is_absolute():
        # Relative paths are resolved from the assigneeschores-ha workspace root
        workspace_root = Path(__file__).parent.parent.parent
        path = workspace_root / path

    if not path.exists():
        raise FileNotFoundError(f"Scenario YAML not found: {path}")

    # Load YAML
    with open(path, encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)

    # Transform to setup_scenario format
    scenario = _transform_yaml_to_scenario(yaml_data)

    # Run setup
    return await setup_scenario(hass, mock_hass_users, scenario)
