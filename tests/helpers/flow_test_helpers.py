"""Shared test helpers for config and options flow testing.

This module provides reusable utilities for both config flow and options flow tests:
1. YAML scenario data → flow form data converters
2. Entity verification helpers
3. Common flow navigation patterns

Usage:
    from tests.helpers.flow_test_helpers import FlowTestHelper

    # Convert YAML assignee to form data
    form_data = FlowTestHelper.build_assignee_form_data(yaml_assignee)

    # Verify entities created after flow
    await FlowTestHelper.verify_entity_counts(hass, {"assignees": 2, "chores": 5})
"""

from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from tests.helpers import (
    # Badge constants
    BADGE_TYPE_CUMULATIVE,
    BADGE_TYPE_DAILY,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION,
    # Config/Options flow field names - Achievements
    CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS,
    CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION,
    CFOF_ACHIEVEMENTS_INPUT_ICON,
    CFOF_ACHIEVEMENTS_INPUT_NAME,
    CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS,
    CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE,
    CFOF_ACHIEVEMENTS_INPUT_TYPE,
    CFOF_APPROVERS_INPUT_HA_USER,
    CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE,
    CFOF_APPROVERS_INPUT_NAME,
    CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME,
    CFOF_ASSIGNEES_INPUT_HA_USER,
    CFOF_ASSIGNEES_INPUT_MOBILE_NOTIFY_SERVICE,
    # Config/Options flow field names - Badges
    CFOF_BADGES_INPUT_ASSIGNED_USER_IDS,
    CFOF_BADGES_INPUT_AWARD_ITEMS,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_END_DATE,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_MAINTENANCE_RULES,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_OCCASION_TYPE,
    CFOF_BADGES_INPUT_SELECTED_CHORES,
    CFOF_BADGES_INPUT_START_DATE,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TARGET_TYPE,
    CFOF_BONUSES_INPUT_DESCRIPTION,
    CFOF_BONUSES_INPUT_ICON,
    CFOF_BONUSES_INPUT_NAME,
    CFOF_BONUSES_INPUT_POINTS,
    # Config/Options flow field names - Challenges
    CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS,
    CFOF_CHALLENGES_INPUT_DESCRIPTION,
    CFOF_CHALLENGES_INPUT_END_DATE,
    CFOF_CHALLENGES_INPUT_ICON,
    CFOF_CHALLENGES_INPUT_NAME,
    CFOF_CHALLENGES_INPUT_REWARD_POINTS,
    CFOF_CHALLENGES_INPUT_START_DATE,
    CFOF_CHALLENGES_INPUT_TARGET_VALUE,
    CFOF_CHALLENGES_INPUT_TYPE,
    # Config/Options flow field names - Chores
    CFOF_CHORES_INPUT_ASSIGNED_USER_IDS,
    CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
    CFOF_CHORES_INPUT_DEFAULT_POINTS,
    CFOF_CHORES_INPUT_DESCRIPTION,
    CFOF_CHORES_INPUT_ICON,
    CFOF_CHORES_INPUT_NAME,
    CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    # Config/Options flow field names - Penalties
    CFOF_PENALTIES_INPUT_DESCRIPTION,
    CFOF_PENALTIES_INPUT_ICON,
    CFOF_PENALTIES_INPUT_NAME,
    CFOF_PENALTIES_INPUT_POINTS,
    # Config/Options flow field names - Rewards
    CFOF_REWARDS_INPUT_COST,
    CFOF_REWARDS_INPUT_DESCRIPTION,
    CFOF_REWARDS_INPUT_ICON,
    CFOF_REWARDS_INPUT_NAME,
    CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
    CFOF_USERS_INPUT_CAN_APPROVE,
    # Config/Options flow field names - Approvers
    CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
    CFOF_USERS_INPUT_CAN_MANAGE,
    # Config/Options flow field names - Assignees
    CFOF_USERS_INPUT_DASHBOARD_LANGUAGE,
    CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW,
    CFOF_USERS_INPUT_ENABLE_GAMIFICATION,
    # Domain and coordinator
    DOMAIN,
    # Options flow navigation constants
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_ACTIONS_EDIT,
    OPTIONS_FLOW_INPUT_ENTITY_NAME,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    # Sentinel values
    SENTINEL_NO_SELECTION,
)


class FlowTestHelper:
    """Unified helper for config and options flow testing."""

    # =========================================================================
    # YAML → Form Data Converters
    # =========================================================================

    @staticmethod
    def build_assignee_form_data(yaml_assignee: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML assignee data to flow form input.

        Args:
            yaml_assignee: Assignee data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        # Convert empty string to sentinel (HA SelectSelector issue)
        ha_user = yaml_assignee.get("ha_user_name", SENTINEL_NO_SELECTION)
        if ha_user == "":
            ha_user = SENTINEL_NO_SELECTION
        # Convert empty mobile_notify_service to sentinel
        notify_service = yaml_assignee.get(
            "mobile_notify_service", SENTINEL_NO_SELECTION
        )
        if notify_service == "":
            notify_service = SENTINEL_NO_SELECTION
        return {
            CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: yaml_assignee["name"],
            CFOF_ASSIGNEES_INPUT_HA_USER: ha_user,
            CFOF_USERS_INPUT_DASHBOARD_LANGUAGE: yaml_assignee.get(
                "dashboard_language", "en"
            ),
            CFOF_ASSIGNEES_INPUT_MOBILE_NOTIFY_SERVICE: notify_service,
        }

    @staticmethod
    def build_approver_form_data(yaml_approver: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML approver data to flow form input.

        Args:
            yaml_approver: Approver data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        # Convert empty string to sentinel (HA SelectSelector issue)
        ha_user = yaml_approver.get("ha_user_name", SENTINEL_NO_SELECTION)
        if ha_user == "":
            ha_user = SENTINEL_NO_SELECTION
        # Convert empty mobile_notify_service to sentinel
        notify_service = yaml_approver.get(
            "mobile_notify_service", SENTINEL_NO_SELECTION
        )
        if notify_service == "":
            notify_service = SENTINEL_NO_SELECTION
        return {
            CFOF_APPROVERS_INPUT_NAME: yaml_approver["name"],
            CFOF_APPROVERS_INPUT_HA_USER: ha_user,
            CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: yaml_approver.get(
                "associated_assignees", []
            ),
            CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE: notify_service,
            CFOF_USERS_INPUT_CAN_BE_ASSIGNED: yaml_approver.get(
                "can_be_assigned",
                yaml_approver.get("allow_chore_assignment", False),
            ),
            CFOF_USERS_INPUT_CAN_APPROVE: yaml_approver.get("can_approve", False),
            CFOF_USERS_INPUT_CAN_MANAGE: yaml_approver.get("can_manage", False),
            CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW: yaml_approver.get(
                "enable_chore_workflow", False
            ),
            CFOF_USERS_INPUT_ENABLE_GAMIFICATION: yaml_approver.get(
                "enable_gamification", False
            ),
        }

    @staticmethod
    def build_chore_form_data(
        yaml_chore: dict[str, Any],
        assignee_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Convert YAML chore data to flow form input.

        Args:
            yaml_chore: Chore data from scenario YAML file
            assignee_names: List of available assignee names for assignment

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        # Map YAML "type" to flow "recurring_frequency"
        frequency_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "once": "once",
            "custom": "custom",
        }
        yaml_type = yaml_chore.get("type", "once")
        recurring_frequency = frequency_map.get(yaml_type, "once")

        return {
            CFOF_CHORES_INPUT_NAME: yaml_chore["name"],
            CFOF_CHORES_INPUT_DEFAULT_POINTS: yaml_chore.get("points", 10),
            CFOF_CHORES_INPUT_ICON: yaml_chore.get("icon", "mdi:check"),
            CFOF_CHORES_INPUT_DESCRIPTION: yaml_chore.get("description", ""),
            CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: yaml_chore.get("assigned_to", []),
            CFOF_CHORES_INPUT_RECURRING_FREQUENCY: recurring_frequency,
            CFOF_CHORES_INPUT_COMPLETION_CRITERIA: yaml_chore.get(
                "completion_criteria", "independent"
            ),
        }

    @staticmethod
    def build_reward_form_data(yaml_reward: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML reward data to flow form input.

        Args:
            yaml_reward: Reward data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_REWARDS_INPUT_NAME: yaml_reward["name"],
            CFOF_REWARDS_INPUT_COST: yaml_reward.get("cost", 50),
            CFOF_REWARDS_INPUT_ICON: yaml_reward.get("icon", "mdi:gift"),
            CFOF_REWARDS_INPUT_DESCRIPTION: yaml_reward.get("description", ""),
        }

    @staticmethod
    def build_penalty_form_data(yaml_penalty: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML penalty data to flow form input.

        Args:
            yaml_penalty: Penalty data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_PENALTIES_INPUT_NAME: yaml_penalty["name"],
            CFOF_PENALTIES_INPUT_POINTS: yaml_penalty.get("points", 5),
            CFOF_PENALTIES_INPUT_ICON: yaml_penalty.get("icon", "mdi:alert"),
            CFOF_PENALTIES_INPUT_DESCRIPTION: yaml_penalty.get("description", ""),
        }

    @staticmethod
    def build_bonus_form_data(yaml_bonus: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML bonus data to flow form input.

        Args:
            yaml_bonus: Bonus data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_BONUSES_INPUT_NAME: yaml_bonus["name"],
            CFOF_BONUSES_INPUT_POINTS: yaml_bonus.get("points", 10),
            CFOF_BONUSES_INPUT_ICON: yaml_bonus.get("icon", "mdi:star"),
            CFOF_BONUSES_INPUT_DESCRIPTION: yaml_bonus.get("description", ""),
        }

    @staticmethod
    def build_badge_form_data(yaml_badge: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML badge data to flow form input.

        Args:
            yaml_badge: Badge data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        # YAML uses "type", converter maps to badge_type internally
        badge_type = yaml_badge.get("type", BADGE_TYPE_CUMULATIVE)

        # Build award_items list based on what's provided
        award_items: list[str] = []
        award_points = yaml_badge.get("award_points", 0)
        if award_points and float(award_points) > 0:
            award_items.append("points")  # AWARD_ITEMS_KEY_POINTS

        form_data = {
            CFOF_BADGES_INPUT_NAME: yaml_badge["name"],
            CFOF_BADGES_INPUT_ICON: yaml_badge.get("icon", "mdi:medal"),
            CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: yaml_badge.get(
                "assigned_user_ids", []
            ),
            CFOF_BADGES_INPUT_AWARD_POINTS: float(award_points),
            CFOF_BADGES_INPUT_AWARD_ITEMS: award_items,
        }

        if badge_type == BADGE_TYPE_CUMULATIVE:
            # For cumulative badges: threshold_value and maintenance_rules
            # YAML uses "threshold_value"; also accept "target_threshold_value"
            form_data[CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = yaml_badge.get(
                "threshold_value", yaml_badge.get("target_threshold_value", 10)
            )
            # Maintenance rules required by validation (default 0 = no maintenance)
            form_data[CFOF_BADGES_INPUT_MAINTENANCE_RULES] = yaml_badge.get(
                "maintenance_rules", 0
            )
            # target_type handled internally by data_builders.py (forced to "points")
        elif badge_type in (BADGE_TYPE_PERIODIC, BADGE_TYPE_DAILY):
            # Periodic/Daily badges have target_type and threshold
            form_data[CFOF_BADGES_INPUT_TARGET_TYPE] = yaml_badge.get(
                "target_type", "chore_count"
            )
            form_data[CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = yaml_badge.get(
                "target_threshold_value", 10
            )
            # Optional: tracked chores (specific chores to track)
            if "selected_chores" in yaml_badge:
                form_data[CFOF_BADGES_INPUT_SELECTED_CHORES] = yaml_badge.get(
                    "selected_chores", []
                )
            # Optional: date range for periodic badges
            if "start_date" in yaml_badge:
                form_data[CFOF_BADGES_INPUT_START_DATE] = yaml_badge.get("start_date")
            if "end_date" in yaml_badge:
                form_data[CFOF_BADGES_INPUT_END_DATE] = yaml_badge.get("end_date")
        elif badge_type == BADGE_TYPE_SPECIAL_OCCASION:
            # Special occasion badges have occasion_type
            form_data[CFOF_BADGES_INPUT_OCCASION_TYPE] = yaml_badge.get(
                "occasion_type", "birthday"
            )

        return form_data

    @staticmethod
    def build_achievement_form_data(yaml_achievement: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML achievement data to flow form input.

        Args:
            yaml_achievement: Achievement data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_ACHIEVEMENTS_INPUT_NAME: yaml_achievement["name"],
            CFOF_ACHIEVEMENTS_INPUT_ICON: yaml_achievement.get("icon", "mdi:trophy"),
            CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION: yaml_achievement.get(
                "description", ""
            ),
            CFOF_ACHIEVEMENTS_INPUT_TYPE: yaml_achievement.get("type", "chore_count"),
            CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE: yaml_achievement.get(
                "target_value", 10
            ),
            CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS: yaml_achievement.get(
                "reward_points", 50
            ),
            CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS: yaml_achievement.get(
                "assigned_to", []
            ),
        }

    @staticmethod
    def build_challenge_form_data(yaml_challenge: dict[str, Any]) -> dict[str, Any]:
        """Convert YAML challenge data to flow form input.

        Args:
            yaml_challenge: Challenge data from scenario YAML file

        Returns:
            Dictionary suitable for flow.async_configure() user_input
        """
        return {
            CFOF_CHALLENGES_INPUT_NAME: yaml_challenge["name"],
            CFOF_CHALLENGES_INPUT_ICON: yaml_challenge.get("icon", "mdi:flag"),
            CFOF_CHALLENGES_INPUT_DESCRIPTION: yaml_challenge.get("description", ""),
            CFOF_CHALLENGES_INPUT_TYPE: yaml_challenge.get("type", "daily_minimum"),
            CFOF_CHALLENGES_INPUT_TARGET_VALUE: yaml_challenge.get("target_value", 5),
            CFOF_CHALLENGES_INPUT_REWARD_POINTS: yaml_challenge.get(
                "reward_points", 100
            ),
            CFOF_CHALLENGES_INPUT_START_DATE: yaml_challenge.get("start_date"),
            CFOF_CHALLENGES_INPUT_END_DATE: yaml_challenge.get("end_date"),
            CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS: yaml_challenge.get(
                "assigned_to", []
            ),
        }

    # =========================================================================
    # Entity Verification Helpers
    # =========================================================================

    @staticmethod
    async def get_coordinator(hass: HomeAssistant) -> Any:
        """Get the ChoreOps coordinator from config entry runtime_data.

        Args:
            hass: Home Assistant instance

        Returns:
            ChoreOpsDataCoordinator instance
        """
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state.name == "LOADED":
                return entry.runtime_data
        return None

    @staticmethod
    async def verify_entity_counts(
        hass: HomeAssistant,
        expected: dict[str, int],
    ) -> dict[str, bool]:
        """Verify expected entity counts exist after flow completion.

        Args:
            hass: Home Assistant instance
            expected: Dict mapping entity type to expected count
                      Keys: "assignees", "approvers", "chores", "rewards", etc.

        Returns:
            Dict mapping entity type to pass/fail boolean
        """
        coordinator = await FlowTestHelper.get_coordinator(hass)
        if not coordinator:
            return dict.fromkeys(expected, False)

        actual_counts = {
            "assignees": len(coordinator.assignees_data),
            "approvers": len(coordinator.approvers_data),
            "chores": len(coordinator.chores_data),
            "rewards": len(coordinator.rewards_data),
            "penalties": len(coordinator.penalties_data),
            "bonuses": len(coordinator.bonuses_data),
            "badges": len(coordinator.badges_data),
            "achievements": len(coordinator.achievements_data),
            "challenges": len(coordinator.challenges_data),
        }

        results = {}
        for entity_type, expected_count in expected.items():
            actual = actual_counts.get(entity_type, 0)
            results[entity_type] = actual == expected_count
            if not results[entity_type]:
                # Log mismatch for debugging
                pass  # Tests will assert on results

        return results

    @staticmethod
    async def get_entity_by_name(
        hass: HomeAssistant,
        entity_type: str,
        name: str,
    ) -> dict[str, Any] | None:
        """Find an entity by name in coordinator data.

        Args:
            hass: Home Assistant instance
            entity_type: Type ("assignees", "chores", "rewards", etc.)
            name: Entity name to find

        Returns:
            Entity data dict or None if not found
        """
        coordinator = await FlowTestHelper.get_coordinator(hass)
        if not coordinator:
            return None

        data_map = {
            "assignees": coordinator.assignees_data,
            "approvers": coordinator.approvers_data,
            "chores": coordinator.chores_data,
            "rewards": coordinator.rewards_data,
            "penalties": coordinator.penalties_data,
            "bonuses": coordinator.bonuses_data,
            "badges": coordinator.badges_data,
            "achievements": coordinator.achievements_data,
            "challenges": coordinator.challenges_data,
        }

        data = data_map.get(entity_type, {})
        for entity_data in data.values():
            if entity_data.get("name") == name:
                return entity_data

        return None

    # =========================================================================
    # Options Flow Navigation Helpers
    # =========================================================================

    @staticmethod
    async def navigate_to_entity_menu(
        hass: HomeAssistant,
        entry_id: str,
        entity_type: str,
    ) -> ConfigFlowResult:
        """Navigate options flow to a specific entity management menu.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            entity_type: Menu to navigate to (use OPTIONS_FLOW_* constants)

        Returns:
            Flow result at the manage_entity step
        """
        # Start options flow
        init_result = await hass.config_entries.options.async_init(entry_id)

        # Select entity type menu
        return await hass.config_entries.options.async_configure(
            init_result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: entity_type},
        )

    @staticmethod
    async def add_entity_via_options_flow(
        hass: HomeAssistant,
        entry_id: str,
        menu_type: str,
        add_step: str,
        form_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Add an entity via the options flow.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            menu_type: Menu type constant (OPTIONS_FLOW_KIDS, etc.)
            add_step: Add step constant (OPTIONS_FLOW_STEP_ADD_KID, etc.)
            form_data: Form data for the new entity

        Returns:
            Final flow result
        """
        # Navigate to entity menu
        menu_result = await FlowTestHelper.navigate_to_entity_menu(
            hass, entry_id, menu_type
        )

        # Select "Add" action
        add_result = await hass.config_entries.options.async_configure(
            menu_result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Submit form data
        return await hass.config_entries.options.async_configure(
            add_result["flow_id"],
            user_input=form_data,
        )

    @staticmethod
    async def edit_entity_via_options_flow(
        hass: HomeAssistant,
        entry_id: str,
        menu_type: str,
        entity_name: str,
        form_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Edit an entity via the options flow.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID
            menu_type: Menu type constant (OPTIONS_FLOW_USERS, etc.)
            entity_name: Name of the entity to edit
            form_data: Updated form data for the entity

        Returns:
            Final flow result
        """
        # Navigate to entity menu
        menu_result = await FlowTestHelper.navigate_to_entity_menu(
            hass, entry_id, menu_type
        )

        # Select "Edit" action
        edit_action_result = await hass.config_entries.options.async_configure(
            menu_result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_EDIT},
        )

        # Select entity by name
        select_result = await hass.config_entries.options.async_configure(
            edit_action_result["flow_id"],
            user_input={OPTIONS_FLOW_INPUT_ENTITY_NAME: entity_name},
        )

        # Submit updated form data
        return await hass.config_entries.options.async_configure(
            select_result["flow_id"],
            user_input=form_data,
        )


# =========================================================================
# YAML Scenario Loading (shared with legacy)
# =========================================================================


def load_scenario_yaml(scenario_name: str) -> dict[str, Any]:
    """Load a test scenario YAML file.

    Args:
        scenario_name: Name of the scenario (minimal, medium, full, performance_stress)

    Returns:
        Dictionary containing the scenario data
    """
    import os

    import yaml

    # Try modern location first, then legacy
    scenario_path = os.path.join(
        os.path.dirname(__file__), f"testdata_scenario_{scenario_name}.yaml"
    )
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(
            os.path.dirname(__file__),
            "legacy",
            f"testdata_scenario_{scenario_name}.yaml",
        )

    with open(scenario_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_scenario_entity_counts(scenario_data: dict[str, Any]) -> dict[str, int]:
    """Get entity counts from a loaded scenario.

    Args:
        scenario_data: Scenario data loaded from YAML

    Returns:
        Dict mapping entity type to count
    """
    family = scenario_data.get("family", {})
    return {
        "assignees": len(family.get("assignees", [])),
        "approvers": len(family.get("approvers", [])),
        "chores": len(scenario_data.get("chores", [])),
        "rewards": len(scenario_data.get("rewards", [])),
        "penalties": len(scenario_data.get("penalties", [])),
        "bonuses": len(scenario_data.get("bonuses", [])),
        "badges": len(scenario_data.get("badges", [])),
        "achievements": len(scenario_data.get("achievements", [])),
        "challenges": len(scenario_data.get("challenges", [])),
    }
