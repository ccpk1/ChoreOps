# File: options_flow.py
"""Options Flow for the ChoreOps integration, managing entities by internal_id.

Handles add/edit/delete operations with entities referenced internally by internal_id.
Ensures consistency and reloads the integration upon changes.
"""

import asyncio
import contextlib
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
import uuid

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util
import voluptuous as vol

from . import const, data_builders as db
from .data_builders import EntityValidationError
from .helpers import backup_helpers as bh, entity_helpers as eh, flow_helpers as fh
from .helpers.storage_helpers import get_entry_storage_key_from_entry
from .utils.dt_utils import dt_now_utc, dt_parse, validate_daily_multi_times
from .utils.math_utils import parse_points_adjust_values

if TYPE_CHECKING:
    from .type_defs import BadgeData

# ----------------------------------------------------------------------------------
# INITIALIZATION & HELPERS
# ----------------------------------------------------------------------------------


def _ensure_str(value):
    """Convert anything to string safely."""
    if isinstance(value, dict):
        # Attempt to get a known key or fallback
        return str(value.get("value", next(iter(value.values()), const.SENTINEL_EMPTY)))
    return str(value)


def _sanitize_select_values(values: Any, valid_values: set[str]) -> list[str]:
    """Return only selector values that still exist in available options."""
    if not isinstance(values, list):
        return []

    return [
        value for value in values if isinstance(value, str) and value in valid_values
    ]


class ChoreOpsOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for adding/editing/deleting configuration elements."""

    def __init__(self, _config_entry: config_entries.ConfigEntry):
        """Initialize the options flow."""
        self._entry_options: dict[str, Any] = {}
        self._action: str | None = None
        self._entity_type: str | None = None
        self._reload_needed = False  # Track if reload is needed
        self._delete_confirmed = False  # Track backup deletion confirmation
        self._restore_confirmed = False  # Track backup restoration confirmation
        self._backup_to_delete: str | None = None  # Track backup file path to delete
        self._backup_to_restore: str | None = None  # Track backup filename to restore
        self._backup_delete_selection_map: dict[str, str] = {}
        self._backup_restore_selection_map: dict[str, str] = {}
        self._chore_being_edited: dict[str, Any] | None = (
            None  # For per-assignee date editing
        )
        self._chore_template_date_raw: Any = (
            None  # Template date for per-assignee helper
        )
        # Dashboard generator state
        self._dashboard_name: str = const.DASHBOARD_DEFAULT_NAME
        self._dashboard_selected_assignees: list[str] = []
        self._dashboard_template_profile: str = const.DASHBOARD_STYLE_FULL
        self._dashboard_admin_mode: str = const.DASHBOARD_ADMIN_MODE_GLOBAL
        self._dashboard_admin_template_global: str = const.DASHBOARD_STYLE_ADMIN
        self._dashboard_admin_template_per_assignee: str = const.DASHBOARD_STYLE_ADMIN
        self._dashboard_admin_view_visibility: str = (
            const.DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL
        )
        self._dashboard_show_in_sidebar: bool = True
        self._dashboard_require_admin: bool = False
        self._dashboard_icon: str = "mdi:clipboard-list"
        self._dashboard_release_selection: str = (
            const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE
        )
        self._dashboard_include_prereleases: bool = (
            const.DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT
        )
        self._dashboard_flow_mode: str = const.DASHBOARD_ACTION_CREATE
        self._dashboard_status_message: str = ""
        self._dashboard_update_url_path: str | None = None
        self._dashboard_delete_selection: list[str] = []
        self._dashboard_dedupe_removed: dict[str, int] = {}

    @staticmethod
    def _normalize_dashboard_admin_mode(admin_mode: str) -> str:
        """Normalize admin layout values from UI labels or stored constants."""
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

    # ----------------------------------------------------------------------------------
    # MAIN MENU
    # ----------------------------------------------------------------------------------

    async def async_step_init(self, user_input=None):
        """Display the main menu for the Options Flow."""
        # Check if reload is needed from previous entity add/edit operations
        if self._reload_needed and user_input is None:
            const.LOGGER.debug("Performing deferred reload after entity changes")
            self._reload_needed = False
            # Wait briefly to ensure storage writes complete before reload
            await asyncio.sleep(0.1)
            await self._reload_entry_after_entity_change()
            # Note: After reload, the flow might be invalidated, but that's expected
            # The user will need to reopen the options flow to see new sensors

        self._entry_options = dict(self.config_entry.options)

        if user_input is not None:
            selection = user_input[const.OPTIONS_FLOW_INPUT_MENU_SELECTION]

            if selection == const.OPTIONS_FLOW_POINTS:
                return await self.async_step_manage_points()

            if selection == const.OPTIONS_FLOW_GENERAL_OPTIONS:
                return await self.async_step_manage_general_options()

            if selection == const.OPTIONS_FLOW_DASHBOARD_GENERATOR:
                return await self.async_step_dashboard_generator()

            if selection.startswith(const.OPTIONS_FLOW_MENU_MANAGE_PREFIX):
                selected_entity_type = selection.replace(
                    const.OPTIONS_FLOW_MENU_MANAGE_PREFIX, const.SENTINEL_EMPTY
                )
                self._entity_type = (
                    selected_entity_type  # Directly assign selected entity type
                )
                return await self.async_step_manage_entity()

        main_menu = [
            const.OPTIONS_FLOW_POINTS,
            const.OPTIONS_FLOW_USERS,
            const.OPTIONS_FLOW_CHORES,
            const.OPTIONS_FLOW_BADGES,
            const.OPTIONS_FLOW_REWARDS,
            const.OPTIONS_FLOW_BONUSES,
            const.OPTIONS_FLOW_PENALTIES,
            const.OPTIONS_FLOW_ACHIEVEMENTS,
            const.OPTIONS_FLOW_CHALLENGES,
            const.OPTIONS_FLOW_DASHBOARD_GENERATOR,
            const.OPTIONS_FLOW_GENERAL_OPTIONS,
        ]

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_INIT,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.OPTIONS_FLOW_INPUT_MENU_SELECTION
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=main_menu,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_MAIN_MENU,
                        )
                    )
                }
            ),
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_MAIN_WIKI
            },
        )

    async def async_step_manage_entity(self, user_input=None):
        """Handle the management actions for a selected entity type.

        Presents add/edit/delete options for the selected entity.
        """
        if user_input is not None:
            self._action = user_input[const.OPTIONS_FLOW_INPUT_MANAGE_ACTION]
            # Removed normalization for entity type during selection
            # Route to the corresponding step based on action
            if self._action == const.OPTIONS_FLOW_ACTIONS_ADD:
                return await getattr(
                    self,
                    f"{const.OPTIONS_FLOW_ASYNC_STEP_ADD_PREFIX}{self._entity_type}",
                )()
            if self._action in [
                const.OPTIONS_FLOW_ACTIONS_EDIT,
                const.OPTIONS_FLOW_ACTIONS_DELETE,
            ]:
                return await self.async_step_select_entity()
            if self._action == const.OPTIONS_FLOW_ACTIONS_BACK:
                return await self.async_step_init()

        # Define manage action choices
        manage_action_choices = [
            const.OPTIONS_FLOW_ACTIONS_ADD,
            const.OPTIONS_FLOW_ACTIONS_EDIT,
            const.OPTIONS_FLOW_ACTIONS_DELETE,
            const.OPTIONS_FLOW_ACTIONS_BACK,  # Option to go back to the main menu
        ]

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_ENTITY,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.OPTIONS_FLOW_INPUT_MANAGE_ACTION
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=manage_action_choices,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_MANAGE_ACTIONS,
                        )
                    )
                }
            ),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: self._entity_type or ""
            },
        )

    async def async_step_select_entity(self, user_input=None):
        """Select an entity (assignee, chore, badge, etc.) to edit or delete based on internal_id."""
        if self._action not in [
            const.OPTIONS_FLOW_ACTIONS_EDIT,
            const.OPTIONS_FLOW_ACTIONS_DELETE,
        ]:
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACTION)

        entity_dict = self._get_entity_dict()

        # Build sorted list of entity names for consistent display order
        entity_names = []
        for _entity_id, data in entity_dict.items():
            name = data.get(
                const.OPTIONS_FLOW_DATA_ENTITY_NAME,
                const.TRANS_KEY_DISPLAY_UNKNOWN_ENTITY,
            )
            entity_names.append(name)

        entity_names = sorted(entity_names, key=str.casefold)

        if user_input is not None:
            selected_name = _ensure_str(
                user_input[const.OPTIONS_FLOW_INPUT_ENTITY_NAME]
            )
            matched_entities: list[tuple[str, dict[str, Any]]] = [
                (eid, data)
                for eid, data in entity_dict.items()
                if data.get(const.OPTIONS_FLOW_DATA_ENTITY_NAME) == selected_name
            ]

            internal_id: str | None = None
            if self._entity_type == const.OPTIONS_FLOW_DIC_USER and matched_entities:
                approver_ids = set(self._get_coordinator().approvers_data)
                preferred_approver_match = next(
                    (
                        entity
                        for entity in matched_entities
                        if entity[0] in approver_ids
                    ),
                    None,
                )
                if preferred_approver_match is not None:
                    internal_id = preferred_approver_match[0]

                preferred_match = next(
                    (
                        entity
                        for entity in matched_entities
                        if entity[1].get(const.DATA_USER_CAN_APPROVE, False)
                        or entity[1].get(const.DATA_USER_CAN_MANAGE, False)
                    ),
                    None,
                )
                if internal_id is None and preferred_match is not None:
                    internal_id = preferred_match[0]

            if internal_id is None and matched_entities:
                internal_id = matched_entities[0][0]

            if not internal_id:
                const.LOGGER.error("Selected entity '%s' not found", selected_name)
                return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ENTITY)

            # Store internal_id in context for later use
            cast("dict[str, Any]", self.context)[
                const.OPTIONS_FLOW_INPUT_INTERNAL_ID
            ] = internal_id

            # Route based on action
            if self._action == const.OPTIONS_FLOW_ACTIONS_EDIT:
                # Intercept for badges to route to the correct edit function
                if self._entity_type == const.OPTIONS_FLOW_DIC_BADGE:
                    badge_data = entity_dict[internal_id]
                    badge_type = badge_data.get(const.DATA_BADGE_TYPE)

                    # Route to the correct edit function based on badge type
                    if badge_type == const.BADGE_TYPE_CUMULATIVE:
                        return await self.async_step_edit_badge_cumulative(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_DAILY:
                        return await self.async_step_edit_badge_daily(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_PERIODIC:
                        return await self.async_step_edit_badge_periodic(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_ACHIEVEMENT_LINKED:
                        return await self.async_step_edit_badge_achievement(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_CHALLENGE_LINKED:
                        return await self.async_step_edit_badge_challenge(
                            default_data=badge_data
                        )
                    if badge_type == const.BADGE_TYPE_SPECIAL_OCCASION:
                        return await self.async_step_edit_badge_special(
                            default_data=badge_data
                        )
                    const.LOGGER.error(
                        "Unknown badge type '%s' for badge ID '%s'",
                        badge_type,
                        internal_id,
                    )
                    return self.async_abort(
                        reason=const.TRANS_KEY_CFOF_INVALID_BADGE_TYPE
                    )
                # For other entity types, route to their specific edit step
                return await getattr(
                    self,
                    f"async_step_edit_{self._entity_type}",
                )()

            if self._action == const.OPTIONS_FLOW_ACTIONS_DELETE:
                # Route to the delete step for the selected entity type
                return await getattr(
                    self,
                    f"async_step_delete_{self._entity_type}",
                )()

        if not entity_names:
            return self.async_abort(
                reason=const.ABORT_KEY_NO_ENTITY_TEMPLATE.format(self._entity_type)
            )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_SELECT_ENTITY,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.OPTIONS_FLOW_INPUT_ENTITY_NAME
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=entity_names,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    )
                }
            ),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: self._entity_type or "",
                const.OPTIONS_FLOW_PLACEHOLDER_ACTION: self._action or "",
            },
        )

    # ----------------------------------------------------------------------------------
    # POINTS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_manage_points(self, user_input=None):
        """Let user edit the points label/icon after initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_points_inputs(user_input)

            if not errors:
                # Build points configuration
                points_data = fh.build_points_data(user_input)

                # Update options
                self._entry_options = dict(self.config_entry.options)
                self._entry_options.update(points_data)
                const.LOGGER.debug(
                    "Configured points with name %s and icon %s",
                    points_data[const.CONF_POINTS_LABEL],
                    points_data[const.CONF_POINTS_ICON],
                )
                await self._update_system_settings_and_reload()

                return await self.async_step_init()

        # Get existing values from entry options
        current_label = self._entry_options.get(
            const.CONF_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
        )
        current_icon = self._entry_options.get(
            const.CONF_POINTS_ICON, const.DEFAULT_POINTS_ICON
        )

        # Build the form with existing values as defaults
        points_schema = fh.build_points_schema(
            default_label=current_label, default_icon=current_icon
        )

        # On validation error, preserve user's attempted input
        if user_input:
            points_schema = self.add_suggested_values_to_schema(
                points_schema, user_input
            )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_POINTS,
            data_schema=points_schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_POINTS
            },
        )

    # ----------------------------------------------------------------------------------
    # USERS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_user(self, user_input=None):
        """Add a new user."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        user_profiles = coordinator.users_for_management

        if user_input is not None:
            user_input = fh.normalize_user_form_input(user_input)

            # Validate inputs (check against existing user and assignee profiles)
            assignee_profiles = coordinator.assignees_data
            errors = fh.validate_users_inputs(
                user_input,
                user_profiles,
                assignee_profiles,
            )

            if not errors:
                try:
                    # Use UserManager for user-profile creation (handles linked profile internally)
                    # Immediate persist for reload
                    internal_id = coordinator.user_manager.create_user(
                        user_input, immediate_persist=True
                    )
                    user_name = user_input.get(const.CFOF_USERS_INPUT_NAME, internal_id)

                    self._mark_reload_needed()

                    const.LOGGER.debug(
                        "Added user profile '%s' with ID: %s",
                        user_name,
                        internal_id,
                    )
                    return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        # Retrieve HA users and existing assignees for linking
        users = await self.hass.auth.async_get_users()
        # Build sorted assignment-participant dict for association dropdown.
        assignees_dict = {
            assignee_data[const.DATA_USER_NAME]: assignee_id
            for assignee_id, assignee_data in coordinator.assignees_data.items()
            if eh.is_user_assignment_participant(coordinator, assignee_id)
        }

        user_schema = await fh.build_user_schema(
            self.hass, users=users, assignees_dict=assignees_dict
        )

        # On validation error, preserve user's attempted input
        if user_input:
            user_schema = self.add_suggested_values_to_schema(
                user_schema,
                fh.build_user_section_suggested_values(user_input),
            )
            user_schema = vol.Schema(user_schema.schema, extra=vol.ALLOW_EXTRA)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_USER,
            data_schema=user_schema,
            errors=fh.map_user_form_errors(errors),
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_USERS
            },
        )

    async def async_step_edit_user(self, user_input=None):
        """Edit an existing user."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        user_profiles = coordinator.users_for_management
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in user_profiles:
            const.LOGGER.error(
                "Edit user profile - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_APPROVER)

        user_profile = user_profiles[internal_id]

        if user_input is not None:
            user_input = fh.normalize_user_form_input(user_input)

            # Layer 2: UI validation (excludes current user from duplicate check)
            # Note: internal_id is already validated as str above
            # For assignment-name conflict checks: use assignment participants.
            assignment_participant_assignees = {
                assignee_id: data
                for assignee_id, data in coordinator.assignees_data.items()
                if assignee_id != str(internal_id)
                if eh.is_user_assignment_participant(coordinator, assignee_id)
            }
            errors = fh.validate_users_inputs(
                user_input,
                user_profiles,
                assignment_participant_assignees,
                current_user_id=str(internal_id),
            )

            if not errors:
                try:
                    # Build merged user-profile data using data_builders
                    updated_approver = db.build_user_profile(
                        user_input,
                        existing=user_profile,
                    )

                    # Use UserManager for user-profile update (handles linked profile create/unlink)
                    # Immediate persist for reload
                    coordinator.user_manager.update_user(
                        str(internal_id), dict(updated_approver), immediate_persist=True
                    )

                    await coordinator.system_manager.remove_conditional_entities(
                        user_ids=[str(internal_id)]
                    )

                    const.LOGGER.debug(
                        "Edited user profile '%s' with ID: %s",
                        updated_approver[const.DATA_USER_NAME],
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        # Retrieve HA users and existing assignees for linking
        users = await self.hass.auth.async_get_users()
        # Build association list from current assignment participants.
        assignees_dict = {
            assignee_data[const.DATA_USER_NAME]: assignee_id
            for assignee_id, assignee_data in coordinator.assignees_data.items()
            if eh.is_user_assignment_participant(coordinator, assignee_id)
        }
        valid_associated_user_ids = set(assignees_dict.values())

        current_associated_user_ids_raw = user_profile.get(
            const.DATA_USER_ASSOCIATED_USER_IDS,
            [],
        )
        current_associated_user_ids = (
            [
                user_id
                for user_id in current_associated_user_ids_raw
                if isinstance(user_id, str) and user_id in valid_associated_user_ids
            ]
            if isinstance(current_associated_user_ids_raw, list)
            else []
        )

        available_notify_services = {
            f"{const.NOTIFY_DOMAIN}.{service_name}"
            for service_name in self.hass.services.async_services().get(
                const.NOTIFY_DOMAIN, {}
            )
        }
        current_ha_user_id = user_profile.get(const.DATA_USER_HA_USER_ID) or ""
        current_mobile_notify_service = (
            user_profile.get(const.DATA_USER_MOBILE_NOTIFY_SERVICE) or ""
        )
        if (
            not current_mobile_notify_service
            or current_mobile_notify_service not in available_notify_services
        ):
            current_mobile_notify_service = const.SENTINEL_NO_SELECTION

        # Prepare suggested values for form (current user-profile data)
        suggested_values = {
            const.CFOF_USERS_INPUT_NAME: user_profile[const.DATA_USER_NAME],
            const.CFOF_USERS_INPUT_HA_USER_ID: (
                current_ha_user_id or const.SENTINEL_NO_SELECTION
            ),
            const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: current_associated_user_ids,
            const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE: (
                current_mobile_notify_service
            ),
            const.CFOF_USERS_INPUT_DASHBOARD_LANGUAGE: user_profile.get(
                const.DATA_USER_DASHBOARD_LANGUAGE, const.DEFAULT_DASHBOARD_LANGUAGE
            ),
            const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED: user_profile.get(
                const.DATA_USER_CAN_BE_ASSIGNED, False
            ),
            const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW: user_profile.get(
                const.DATA_USER_ENABLE_CHORE_WORKFLOW, False
            ),
            const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION: user_profile.get(
                const.DATA_USER_ENABLE_GAMIFICATION, False
            ),
            const.CFOF_USERS_INPUT_CAN_APPROVE: user_profile.get(
                const.DATA_USER_CAN_APPROVE, False
            ),
            const.CFOF_USERS_INPUT_CAN_MANAGE: user_profile.get(
                const.DATA_USER_CAN_MANAGE, False
            ),
        }

        # On validation error, merge user's attempted input with existing data
        if user_input:
            suggested_values.update(user_input)

        suggested_associated_user_ids_raw = suggested_values.get(
            const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
            [],
        )
        suggested_can_approve = bool(
            suggested_values.get(const.CFOF_USERS_INPUT_CAN_APPROVE, False)
        )
        suggested_values[const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS] = (
            [
                user_id
                for user_id in suggested_associated_user_ids_raw
                if isinstance(user_id, str) and user_id in valid_associated_user_ids
            ]
            if suggested_can_approve
            and isinstance(suggested_associated_user_ids_raw, list)
            else []
        )

        # Build schema with static defaults
        user_schema = await fh.build_user_schema(
            self.hass,
            users=users,
            assignees_dict=assignees_dict,
        )
        # Apply values as suggestions
        user_schema = self.add_suggested_values_to_schema(
            user_schema,
            fh.build_user_section_suggested_values(suggested_values),
        )
        user_schema = vol.Schema(user_schema.schema, extra=vol.ALLOW_EXTRA)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_USER,
            data_schema=user_schema,
            errors=fh.map_user_form_errors(errors),
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_USERS
            },
        )

    async def async_step_delete_user(self, user_input=None):
        """Delete a user."""
        coordinator = self._get_coordinator()
        user_profiles = coordinator.users_for_management
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in user_profiles:
            const.LOGGER.error(
                "Delete user profile - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_APPROVER)

        user_name = user_profiles[internal_id][const.DATA_USER_NAME]

        if user_input is not None:
            # Use UserManager for user-profile deletion (immediate persist for reload)
            coordinator.user_manager.delete_user(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted user profile '%s' with ID: %s",
                user_name,
                internal_id,
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_USER,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_USER_NAME: user_name
            },
        )

    # ----------------------------------------------------------------------------------
    # CHORES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_chore(self, user_input=None):
        """Add a new chore."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        chores_dict = coordinator.chores_data

        if user_input is not None:
            user_input = fh.normalize_chore_form_input(user_input)

            # Build assignees_dict for name→UUID conversion
            assignees_dict = {
                data[const.DATA_USER_NAME]: eid
                for eid, data in coordinator.assignees_data.items()
            }

            # Validate chore input
            errors, due_date_str = fh.validate_chores_inputs(
                user_input, assignees_dict, chores_dict
            )
            errors = fh.map_chore_form_errors(errors)

            if errors:
                schema = fh.build_chore_schema(assignees_dict)
                schema = self.add_suggested_values_to_schema(
                    schema,
                    fh.build_chore_section_suggested_values(user_input),
                )
                schema = vol.Schema(schema.schema, extra=vol.ALLOW_EXTRA)
                return self.async_show_form(
                    step_id=const.OPTIONS_FLOW_STEP_ADD_CHORE,
                    data_schema=schema,
                    errors=errors,
                    description_placeholders={
                        const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHORES
                    },
                )

            # Transform CFOF_* → DATA_* and build chore entity
            transformed_data = fh.transform_chore_cfof_to_data(
                user_input, assignees_dict, due_date_str
            )
            new_chore_data = db.build_chore(transformed_data)
            internal_id = new_chore_data[const.DATA_CHORE_INTERNAL_ID]
            chore_name = new_chore_data[const.DATA_CHORE_NAME]

            # Get completion criteria and assigned assignees for routing logic
            completion_criteria = new_chore_data.get(
                const.DATA_CHORE_COMPLETION_CRITERIA
            )
            assigned_assignees = new_chore_data.get(
                const.DATA_CHORE_ASSIGNED_USER_IDS, []
            )
            recurring_frequency = new_chore_data.get(
                const.DATA_CHORE_RECURRING_FREQUENCY
            )

            # For INDEPENDENT chores with assigned assignees, handle per-assignee details
            # (mirrors edit_chore logic for consistency)
            if (
                completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
                and assigned_assignees
            ):
                # Capture template values from user input before they're cleared
                clear_due_date = user_input.get(
                    const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False
                )
                raw_template_date = (
                    None
                    if clear_due_date
                    else user_input.get(const.CFOF_CHORES_INPUT_DUE_DATE)
                )
                template_applicable_days = user_input.get(
                    const.CFOF_CHORES_INPUT_APPLICABLE_DAYS, []
                )
                template_daily_multi_times = user_input.get(
                    const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES, ""
                )

                # Single assignee optimization: apply values directly, skip helper
                if len(assigned_assignees) == 1:
                    assignee_id = assigned_assignees[0]

                    # Build updates dict for single-assignee optimizations
                    single_assignee_updates: dict[str, Any] = {}

                    # Handle per-assignee due dates
                    per_assignee_due_dates: dict[str, str | None] = {}
                    if clear_due_date:
                        per_assignee_due_dates[assignee_id] = None
                    elif raw_template_date:
                        try:
                            utc_dt = dt_parse(
                                raw_template_date,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_assignee_due_dates[assignee_id] = utc_dt.isoformat()
                        except ValueError as e:
                            const.LOGGER.warning(
                                "Failed to parse date for single assignee: %s", e
                            )

                    if per_assignee_due_dates:
                        single_assignee_updates[
                            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES
                        ] = per_assignee_due_dates

                    # Apply template applicable_days to single assignee
                    if template_applicable_days:
                        # Convert day name strings to integers (0=Mon, 6=Sun)
                        days_as_ints = [
                            const.WEEKDAY_NAME_TO_INT[d]
                            for d in template_applicable_days
                            if d in const.WEEKDAY_NAME_TO_INT
                        ]
                        single_assignee_updates[
                            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS
                        ] = {assignee_id: days_as_ints}
                        # Clear chore-level (per-assignee is source of truth)
                        single_assignee_updates[const.DATA_CHORE_APPLICABLE_DAYS] = []

                    # Apply daily_multi_times to single assignee (if DAILY_MULTI)
                    if (
                        recurring_frequency == const.FREQUENCY_DAILY_MULTI
                        and template_daily_multi_times
                    ):
                        single_assignee_updates[
                            const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES
                        ] = {assignee_id: template_daily_multi_times}
                        # Clear chore-level (per-assignee is source of truth)
                        single_assignee_updates[const.DATA_CHORE_DAILY_MULTI_TIMES] = ""

                    # Build final chore with single-assignee updates merged
                    final_chore = db.build_chore(
                        single_assignee_updates, existing=new_chore_data
                    )
                    # Use Manager-owned CRUD (prebuilt=True since final_chore is ready)
                    coordinator.chore_manager.create_chore(
                        final_chore,
                        internal_id=internal_id,
                        prebuilt=True,
                        immediate_persist=True,
                    )

                    # CFE-2026-001 FIX: Single-assignee DAILY_MULTI without times
                    # needs to route to times helper (main form doesn't have times field)
                    if (
                        recurring_frequency == const.FREQUENCY_DAILY_MULTI
                        and not template_daily_multi_times
                    ):
                        self._chore_being_edited = dict(final_chore)
                        self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id
                        const.LOGGER.debug(
                            "Added single-assignee INDEPENDENT DAILY_MULTI Chore '%s' "
                            "- routing to times helper",
                            chore_name,
                        )
                        return await self.async_step_chores_daily_multi()

                    const.LOGGER.debug(
                        "Added single-assignee INDEPENDENT Chore '%s' with ID: %s",
                        chore_name,
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                # Multiple assignees: create chore, then show per-assignee details helper
                # Use Manager-owned CRUD (prebuilt=True since new_chore_data is ready)
                coordinator.chore_manager.create_chore(
                    new_chore_data,
                    internal_id=internal_id,
                    prebuilt=True,
                    immediate_persist=True,
                )

                # Store chore data and template values for helper form
                self._chore_being_edited = dict(new_chore_data)
                self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id
                self._chore_template_date_raw = raw_template_date
                self._chore_template_applicable_days = template_applicable_days
                self._chore_template_daily_multi_times = template_daily_multi_times

                const.LOGGER.debug(
                    "Added multi-assignee INDEPENDENT Chore '%s' - routing to per-assignee helper",
                    chore_name,
                )
                return await self.async_step_edit_chore_per_user_details()

            # CFE-2026-001: Check if DAILY_MULTI needs times collection
            # (non-INDEPENDENT chores with DAILY_MULTI frequency)
            if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
                # Use Manager-owned CRUD (prebuilt=True since new_chore_data is ready)
                coordinator.chore_manager.create_chore(
                    new_chore_data,
                    internal_id=internal_id,
                    prebuilt=True,
                    immediate_persist=True,
                )

                # Store chore data for helper step
                self._chore_being_edited = dict(new_chore_data)
                self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id

                const.LOGGER.debug(
                    "Added DAILY_MULTI Chore '%s' - routing to times helper",
                    chore_name,
                )
                return await self.async_step_chores_daily_multi()

            # Standard chore creation (SHARED/SHARED_FIRST or no special handling)
            # Use Manager-owned CRUD (prebuilt=True since new_chore_data is ready)
            coordinator.chore_manager.create_chore(
                new_chore_data,
                internal_id=internal_id,
                prebuilt=True,
                immediate_persist=True,
            )

            const.LOGGER.debug(
                "Added Chore '%s' with ID: %s and Due Date %s",
                chore_name,
                internal_id,
                due_date_str,
            )
            self._mark_reload_needed()
            return await self.async_step_init()

        # Use flow_helpers.build_chore_schema, passing current assignees
        assignees_dict = {
            data[const.DATA_USER_NAME]: eid
            for eid, data in coordinator.assignees_data.items()
        }
        schema = fh.build_chore_schema(assignees_dict)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_CHORE,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHORES
            },
        )

    async def async_step_edit_chore(self, user_input=None):
        """Edit an existing chore."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        chores_dict = coordinator.chores_data
        internal_id = cast("str | None", self.context.get(const.DATA_INTERNAL_ID))

        if not internal_id or internal_id not in chores_dict:
            const.LOGGER.error("Edit Chore - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHORE)

        chore_data = chores_dict[internal_id]

        if user_input is not None:
            user_input = fh.normalize_chore_form_input(user_input)

            # Build assignees_dict for name→UUID conversion
            assignees_dict = {
                data[const.DATA_USER_NAME]: eid
                for eid, data in coordinator.assignees_data.items()
            }

            # Add internal_id for validation
            # (to exclude current chore from duplicate check)
            user_input[const.CFOF_GLOBAL_INPUT_INTERNAL_ID] = internal_id

            # Build a temporary dict for duplicate checking that excludes current chore
            chores_for_validation = {
                cid: cdata for cid, cdata in chores_dict.items() if cid != internal_id
            }

            # Get existing per-assignee due dates to preserve during edit
            existing_per_assignee_due_dates = chore_data.get(
                const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
            )

            # Validate chore input
            errors, due_date_str = fh.validate_chores_inputs(
                user_input,
                assignees_dict,
                chores_for_validation,
                existing_chore=chore_data,
            )
            errors = fh.map_chore_form_errors(errors)

            if errors:
                # Merge original chore data with user's attempted input
                merged_defaults = {**chore_data, **user_input}
                schema = fh.build_chore_schema(assignees_dict)
                schema = self.add_suggested_values_to_schema(
                    schema,
                    fh.build_chore_section_suggested_values(merged_defaults),
                )
                schema = vol.Schema(schema.schema, extra=vol.ALLOW_EXTRA)
                return self.async_show_form(
                    step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE,
                    data_schema=schema,
                    errors=errors,
                    description_placeholders={
                        const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHORES
                    },
                )

            # Transform CFOF_* → DATA_* and build merged chore entity
            transformed_data = fh.transform_chore_cfof_to_data(
                user_input,
                assignees_dict,
                due_date_str,
                existing_per_assignee_due_dates,
                existing_chore=chore_data,
            )

            # Check if assigned assignees changed (for reload decision)
            old_assigned = set(chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, []))
            new_assigned = set(
                transformed_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
            )
            assignments_changed = old_assigned != new_assigned

            # Use Manager-owned CRUD (handles badge recalc and orphan cleanup)
            const.LOGGER.debug(
                "CHORE UPDATE: About to update chore %s with completion_criteria=%s",
                internal_id,
                transformed_data.get(const.DATA_CHORE_COMPLETION_CRITERIA),
            )
            merged_chore = coordinator.chore_manager.update_chore(
                str(internal_id), transformed_data, immediate_persist=True
            )
            const.LOGGER.debug(
                "CHORE UPDATE: After update, merged_chore completion_criteria=%s",
                merged_chore.get(const.DATA_CHORE_COMPLETION_CRITERIA),
            )

            new_name = merged_chore.get(
                const.DATA_CHORE_NAME,
                chore_data.get(const.DATA_CHORE_NAME),
            )
            const.LOGGER.debug("Edited Chore '%s' with ID: %s", new_name, internal_id)

            # Only reload if assignments changed (entities added/removed)
            if assignments_changed:
                const.LOGGER.debug("Chore assignments changed, marking reload needed")
                self._mark_reload_needed()

            # For INDEPENDENT chores with assigned assignees, handle per-assignee date editing
            # Use merged_chore (post-update) for routing decisions
            completion_criteria = merged_chore.get(const.DATA_CHORE_COMPLETION_CRITERIA)
            assigned_assignees = merged_chore.get(
                const.DATA_CHORE_ASSIGNED_USER_IDS, []
            )
            # PKAH-2026-002: Only INDEPENDENT chores need per-assignee details
            # SHARED and ROTATION types skip per-assignee customization
            requires_per_assignee_details = (
                completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            )
            const.LOGGER.debug(
                "ROUTING DEBUG: completion_criteria=%s, assigned_assignees=%s, requires_per_assignee=%s",
                completion_criteria,
                len(assigned_assignees),
                requires_per_assignee_details,
            )
            if requires_per_assignee_details and assigned_assignees:
                # Check if user explicitly cleared the date via checkbox
                clear_due_date = user_input.get(
                    const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False
                )

                # Capture the raw user-entered date from form input
                # (For INDEPENDENT chores, transform_chore_cfof_to_data clears
                # chore-level due_date - but we use per-assignee dates)
                # If clear checkbox is selected, don't pass template date to helper
                raw_template_date = (
                    None
                    if clear_due_date
                    else user_input.get(const.CFOF_CHORES_INPUT_DUE_DATE)
                )

                # PKAD-2026-001: Capture template applicable_days and daily_multi_times
                template_applicable_days = user_input.get(
                    const.CFOF_CHORES_INPUT_APPLICABLE_DAYS, []
                )
                template_daily_multi_times = user_input.get(
                    const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES, ""
                )

                # Single assignee optimization: skip per-assignee popup if only one assignee
                if len(assigned_assignees) == 1:
                    assignee_id = assigned_assignees[0]
                    per_assignee_due_dates = dict(
                        merged_chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
                    )

                    if clear_due_date:
                        # User explicitly cleared the date
                        per_assignee_due_dates[assignee_id] = None
                        const.LOGGER.debug(
                            "Single assignee INDEPENDENT chore: cleared due date for %s",
                            assignee_id,
                        )
                    elif raw_template_date:
                        # User set a date - apply it directly to the single assignee
                        try:
                            utc_dt = dt_parse(
                                raw_template_date,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_assignee_due_dates[assignee_id] = utc_dt.isoformat()
                                const.LOGGER.debug(
                                    "Single assignee INDEPENDENT chore: applied date %s directly to %s",
                                    utc_dt.isoformat(),
                                    assignee_id,
                                )
                        except ValueError as e:
                            const.LOGGER.warning(
                                "Failed to parse date for single assignee: %s", e
                            )
                    # else: date was blank, preserve existing per-assignee date (already done)

                    # Build additional updates dict for single-assignee case
                    single_assignee_updates: dict[str, Any] = {
                        const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: per_assignee_due_dates,
                    }

                    # PKAD-2026-001: Apply template applicable_days to single assignee
                    if template_applicable_days:
                        # Convert day name strings to integers (0=Mon, 6=Sun)
                        days_as_ints = [
                            const.WEEKDAY_NAME_TO_INT[d]
                            for d in template_applicable_days
                            if d in const.WEEKDAY_NAME_TO_INT
                        ]
                        single_assignee_updates[
                            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS
                        ] = {assignee_id: days_as_ints}
                        # Clear chore-level (per-assignee is now source of truth)
                        single_assignee_updates[const.DATA_CHORE_APPLICABLE_DAYS] = None

                    # PKAD-2026-001: Apply daily_multi_times to single assignee (if DAILY_MULTI)
                    recurring_freq = merged_chore.get(
                        const.DATA_CHORE_RECURRING_FREQUENCY
                    )
                    if (
                        recurring_freq == const.FREQUENCY_DAILY_MULTI
                        and template_daily_multi_times
                    ):
                        single_assignee_updates[
                            const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES
                        ] = {assignee_id: template_daily_multi_times}
                        # Clear chore-level (per-assignee is now source of truth)
                        single_assignee_updates[const.DATA_CHORE_DAILY_MULTI_TIMES] = (
                            None
                        )

                    # Use Manager-owned CRUD for final update
                    final_chore = coordinator.chore_manager.update_chore(
                        str(internal_id),
                        single_assignee_updates,
                        immediate_persist=True,
                    )

                    # CFE-2026-001 FIX: Single-assignee DAILY_MULTI without times
                    # needs to route to times helper (check per-assignee times too)
                    existing_per_assignee_times = final_chore.get(
                        const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES, {}
                    )
                    assignee_has_times = existing_per_assignee_times.get(assignee_id)
                    if (
                        recurring_freq == const.FREQUENCY_DAILY_MULTI
                        and not template_daily_multi_times
                        and not assignee_has_times
                    ):
                        # Store chore data with internal_id for times helper
                        self._chore_being_edited = dict(final_chore)
                        self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id
                        const.LOGGER.debug(
                            "Edited single-assignee INDEPENDENT chore to DAILY_MULTI "
                            "- routing to times helper"
                        )
                        return await self.async_step_chores_daily_multi()

                    self._mark_reload_needed()
                    return await self.async_step_init()

                # Multiple assignees: show unified per-assignee details step (PKAD-2026-001)
                # Store chore data AND template values for the helper form
                self._chore_being_edited = dict(merged_chore)
                self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id
                # Store template values for per-assignee details step
                self._chore_template_date_raw = raw_template_date
                self._chore_template_applicable_days = template_applicable_days
                self._chore_template_daily_multi_times = template_daily_multi_times
                return await self.async_step_edit_chore_per_user_details()

            # CFE-2026-001: Check if DAILY_MULTI needs times collection/update
            recurring_frequency = merged_chore.get(const.DATA_CHORE_RECURRING_FREQUENCY)
            existing_times = merged_chore.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")
            if (
                recurring_frequency == const.FREQUENCY_DAILY_MULTI
                and not existing_times
            ):
                # DAILY_MULTI selected but no times yet - route to helper
                # (already persisted above, just need to set up helper state)
                self._chore_being_edited = dict(merged_chore)
                coordinator.async_update_listeners()
                # Orphan cleanup handled by ChoreManager CRUD methods (Phase 7.3)

                self._chore_being_edited[const.DATA_INTERNAL_ID] = internal_id

                const.LOGGER.debug(
                    "Edited chore to DAILY_MULTI - routing to times helper"
                )
                return await self.async_step_chores_daily_multi()

            return await self.async_step_init()

        # Use flow_helpers.fh.build_chore_schema, passing current assignees
        assignees_dict = {
            data[const.DATA_USER_NAME]: eid
            for eid, data in coordinator.assignees_data.items()
        }

        # Create reverse mapping from internal_id to name
        id_to_name = {
            eid: data[const.DATA_USER_NAME]
            for eid, data in coordinator.assignees_data.items()
        }

        # Convert stored string to datetime for DateTimeSelector
        existing_due_str = chore_data.get(const.DATA_CHORE_DUE_DATE)
        existing_due_date = None

        # For INDEPENDENT chores, check if all per-assignee dates are the same
        # If they differ, show blank (None) since the per-assignee dates take precedence
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        per_assignee_due_dates = chore_data.get(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )
        per_assignee_applicable_days = chore_data.get(
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}
        )
        assigned_user_ids = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])

        if (
            completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and assigned_user_ids
        ):
            # Get all date values for assigned assignees (including None)
            # Use a set to check uniqueness, treating None as a distinct value
            all_assignee_dates = set()
            for assignee_id in assigned_user_ids:
                assignee_date = per_assignee_due_dates.get(assignee_id)
                all_assignee_dates.add(assignee_date)

            if len(all_assignee_dates) == 1:
                # All assigned assignees have the same date (or all None) - show it
                common_date = next(iter(all_assignee_dates))
                if common_date:  # Only show if not None
                    try:
                        existing_due_date = dt_parse(
                            common_date,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                        )
                        const.LOGGER.debug(
                            "INDEPENDENT chore: all assignees have same date: %s",
                            existing_due_date,
                        )
                    except ValueError as e:
                        const.LOGGER.error(
                            "Failed to parse common per-assignee date '%s': %s",
                            common_date,
                            e,
                        )
                else:
                    # All assignees have None - show blank
                    const.LOGGER.debug(
                        "INDEPENDENT chore: all assignees have no date, showing blank"
                    )
                    existing_due_date = None
            else:
                # Assignees have different dates (including mix of dates and None) - show blank
                const.LOGGER.debug(
                    "INDEPENDENT chore: assignees have different dates (%d unique), "
                    "showing blank due date field",
                    len(all_assignee_dates),
                )
                existing_due_date = None
        elif existing_due_str:
            try:
                # Parse to local datetime string for DateTimeSelector
                # Storage is UTC ISO; display is local timezone
                existing_due_date = dt_parse(
                    existing_due_str,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )
                const.LOGGER.debug(
                    "Processed existing_due_date for DateTimeSelector: %s",
                    existing_due_date,
                )
            except ValueError as e:
                const.LOGGER.error(
                    "Failed to parse existing_due_date '%s': %s",
                    existing_due_str,
                    e,
                )

        # For INDEPENDENT chores, check if all per-assignee applicable_days are the same
        # Similar logic to per-assignee due dates above
        existing_applicable_days_display = None
        if (
            completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and assigned_user_ids
        ):
            # Get all applicable_days for assigned assignees
            # Convert to frozenset for hashability (lists aren't hashable)
            all_assignee_days: set[frozenset[int] | None] = set()
            for assignee_id in assigned_user_ids:
                assignee_days = per_assignee_applicable_days.get(assignee_id)
                # Convert to frozenset to make it hashable for set operations
                if assignee_days is not None:
                    all_assignee_days.add(frozenset(assignee_days))
                else:
                    all_assignee_days.add(None)

            if len(all_assignee_days) == 1:
                # All assigned assignees have the same applicable_days
                common_days = next(iter(all_assignee_days))
                if common_days is not None:
                    # Convert back from frozenset to list, then to string keys
                    weekday_keys = list(const.WEEKDAY_OPTIONS.keys())
                    existing_applicable_days_display = [
                        weekday_keys[day]
                        for day in sorted(common_days)
                        if isinstance(day, int) and 0 <= day <= 6
                    ]
                    const.LOGGER.debug(
                        "INDEPENDENT chore: all assignees have same applicable_days: %s",
                        existing_applicable_days_display,
                    )
                else:
                    # All assignees have None - show empty
                    existing_applicable_days_display = []
                    const.LOGGER.debug(
                        "INDEPENDENT chore: all assignees have no applicable_days, showing empty"
                    )
            else:
                # Assignees have different applicable_days - show empty (will be per-assignee)
                existing_applicable_days_display = []
                const.LOGGER.debug(
                    "INDEPENDENT chore: assignees have different applicable_days (%d unique), "
                    "showing empty field",
                    len(all_assignee_days),
                )
        else:
            # SHARED chore or no assignees: use chore-level applicable_days
            weekday_keys = list(const.WEEKDAY_OPTIONS.keys())
            existing_applicable_days_display = [
                weekday_keys[day]
                for day in chore_data.get(
                    const.DATA_CHORE_APPLICABLE_DAYS, const.DEFAULT_APPLICABLE_DAYS
                )
                if isinstance(day, int) and 0 <= day <= 6
            ]

        # Convert assigned user IDs to names for display.
        # (assigned_user_ids already set above for per-assignee date check)
        assigned_user_names = [
            id_to_name.get(assignee_id, assignee_id)
            for assignee_id in assigned_user_ids
        ]

        # Prepare suggested values for form (current chore data)
        # Map DATA_CHORE_* fields to CFOF_CHORES_INPUT_* fields
        suggested_values = {
            const.CFOF_CHORES_INPUT_NAME: chore_data.get(const.DATA_CHORE_NAME),
            const.CFOF_CHORES_INPUT_DESCRIPTION: chore_data.get(
                const.DATA_CHORE_DESCRIPTION
            ),
            const.CFOF_CHORES_INPUT_ICON: chore_data.get(const.DATA_CHORE_ICON),
            const.CFOF_CHORES_INPUT_LABELS: chore_data.get(const.DATA_CHORE_LABELS, []),
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS: chore_data.get(
                const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS
            ),
            const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: assigned_user_names,
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: chore_data.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            ),
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: chore_data.get(
                const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
            ),
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: chore_data.get(
                const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            ),
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: chore_data.get(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            ),
            const.CFOF_CHORES_INPUT_AUTO_APPROVE: chore_data.get(
                const.DATA_CHORE_AUTO_APPROVE, const.DEFAULT_CHORE_AUTO_APPROVE
            ),
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: chore_data.get(
                const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            ),
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL: chore_data.get(
                const.DATA_CHORE_CUSTOM_INTERVAL
            ),
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT: chore_data.get(
                const.DATA_CHORE_CUSTOM_INTERVAL_UNIT
            ),
            # Use computed applicable_days (handles per-assignee for INDEPENDENT chores)
            const.CFOF_CHORES_INPUT_APPLICABLE_DAYS: existing_applicable_days_display,
            const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: chore_data.get(
                const.DATA_CHORE_DAILY_MULTI_TIMES, ""
            ),
            const.CFOF_CHORES_INPUT_DUE_DATE: existing_due_date,
            const.CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET: chore_data.get(
                const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
            ),
            const.CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW: chore_data.get(
                const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
                const.DEFAULT_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
            ),
            const.CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET: chore_data.get(
                const.DATA_CHORE_DUE_REMINDER_OFFSET, const.DEFAULT_DUE_REMINDER_OFFSET
            ),
            # Calendar and features
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: chore_data.get(
                const.DATA_CHORE_SHOW_ON_CALENDAR, const.DEFAULT_CHORE_SHOW_ON_CALENDAR
            ),
            # Notification settings (map DATA_CHORE_* to CFOF_CHORES_INPUT_* for form)
            const.CFOF_CHORES_INPUT_NOTIFY_ON_CLAIM: chore_data.get(
                const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
            ),
            const.CFOF_CHORES_INPUT_NOTIFY_ON_APPROVAL: chore_data.get(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
            ),
            const.CFOF_CHORES_INPUT_NOTIFY_ON_DISAPPROVAL: chore_data.get(
                const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
            ),
            const.CFOF_CHORES_INPUT_NOTIFY_ON_DUE_WINDOW: chore_data.get(
                const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW,
                const.DEFAULT_NOTIFY_ON_DUE_WINDOW,
            ),
            const.CFOF_CHORES_INPUT_NOTIFY_DUE_REMINDER: chore_data.get(
                const.DATA_CHORE_NOTIFY_DUE_REMINDER, const.DEFAULT_NOTIFY_DUE_REMINDER
            ),
            const.CFOF_CHORES_INPUT_NOTIFY_ON_OVERDUE: chore_data.get(
                const.DATA_CHORE_NOTIFY_ON_OVERDUE, const.DEFAULT_NOTIFY_ON_OVERDUE
            ),
        }

        # Build consolidated notifications list from individual boolean fields
        # This ensures the multi-select field shows the correct checkboxes
        # NOTE: Don't use fallback defaults here - use actual values from suggested_values
        # which already contain the correct stored values with their proper defaults applied
        notifications_list = []
        if suggested_values.get(const.CFOF_CHORES_INPUT_NOTIFY_ON_CLAIM):
            notifications_list.append(const.DATA_CHORE_NOTIFY_ON_CLAIM)
        if suggested_values.get(const.CFOF_CHORES_INPUT_NOTIFY_ON_APPROVAL):
            notifications_list.append(const.DATA_CHORE_NOTIFY_ON_APPROVAL)
        if suggested_values.get(const.CFOF_CHORES_INPUT_NOTIFY_ON_DISAPPROVAL):
            notifications_list.append(const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL)
        if suggested_values.get(const.CFOF_CHORES_INPUT_NOTIFY_ON_DUE_WINDOW):
            notifications_list.append(const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW)
        if suggested_values.get(const.CFOF_CHORES_INPUT_NOTIFY_DUE_REMINDER):
            notifications_list.append(const.DATA_CHORE_NOTIFY_DUE_REMINDER)
        if suggested_values.get(const.CFOF_CHORES_INPUT_NOTIFY_ON_OVERDUE):
            notifications_list.append(const.DATA_CHORE_NOTIFY_ON_OVERDUE)
        suggested_values[const.CFOF_CHORES_INPUT_NOTIFICATIONS] = notifications_list

        # Build schema and apply suggested values
        schema = fh.build_chore_schema(assignees_dict)
        schema = self.add_suggested_values_to_schema(
            schema,
            fh.build_chore_section_suggested_values(suggested_values),
        )
        schema = vol.Schema(schema.schema, extra=vol.ALLOW_EXTRA)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHORES
            },
        )

    # ----- Edit Per-Assignee Due Dates for INDEPENDENT Chores -----
    async def async_step_edit_chore_per_user_dates(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow editing per-assignee due dates for INDEPENDENT chores.

        Features:
        - Shows template date from main form (if set) with "Apply to All" option
        - Each assignee's current due date shown as default (editable)
        - Supports bulk application of template date to all or selected assignees
        """
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}

        # Get chore data from stored state
        chore_data = getattr(self, "_chore_being_edited", None)
        if not chore_data:
            const.LOGGER.error("Per-assignee dates step called without chore data")
            return await self.async_step_init()

        internal_id = chore_data.get(const.DATA_INTERNAL_ID)
        if not internal_id:
            const.LOGGER.error("Per-assignee dates step: missing internal_id")
            return await self.async_step_init()

        # Only allow for INDEPENDENT chores
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
            const.LOGGER.debug(
                "Per-assignee dates step skipped - not INDEPENDENT (criteria: %s)",
                completion_criteria,
            )
            return await self.async_step_init()

        assigned_assignees = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        if not assigned_assignees:
            const.LOGGER.debug(
                "Per-assignee dates step skipped - no assigned assignees"
            )
            return await self.async_step_init()

        # Get fresh per-assignee dates from storage (not from _chore_being_edited)
        stored_chore = coordinator.chores_data.get(internal_id, {})
        existing_per_assignee_dates = stored_chore.get(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )

        # Get template date from main form (if set)
        # Use the raw template date stored from form input
        # (transform_chore_cfof_to_data sets chore-level due_date to None
        # for INDEPENDENT chores - per-assignee dates are used instead)
        raw_template_date = getattr(self, "_chore_template_date_raw", None)
        template_date_str = None
        template_date_display = None
        if raw_template_date:
            try:
                # Convert to UTC ISO for storage/comparison
                utc_dt = dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_DATETIME_UTC,
                )
                if utc_dt and isinstance(utc_dt, datetime):
                    template_date_str = utc_dt.isoformat()
                # Also get display format for UI
                template_date_display = dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                )
            except (ValueError, TypeError):
                pass

        # Build name-to-id mapping for assigned assignees
        name_to_id: dict[str, str] = {}
        for assignee_id in assigned_assignees:
            assignee_info = coordinator.assignees_data.get(assignee_id, {})
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)
            name_to_id[assignee_name] = assignee_id

        if user_input is not None:
            # Check if "Apply to All" was selected
            apply_template_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, False
            )

            # Process per-assignee dates from user input
            # Field keys use assignee names for readability; map back to IDs for storage
            per_assignee_due_dates: dict[str, str | None] = {}
            for assignee_name, assignee_id in name_to_id.items():
                # Check if user wants to clear this assignee's date
                clear_field_name = f"clear_due_date_{assignee_name}"
                clear_this_assignee = user_input.get(clear_field_name, False)

                # If "Apply to All" is selected and we have a template date, use it
                if apply_template_to_all and template_date_str:
                    per_assignee_due_dates[assignee_id] = template_date_str
                    const.LOGGER.debug(
                        "Applied template date to %s: %s",
                        assignee_name,
                        template_date_str,
                    )
                elif clear_this_assignee:
                    # User explicitly cleared this assignee's date
                    per_assignee_due_dates[assignee_id] = None
                    const.LOGGER.debug("Cleared date for %s", assignee_name)
                else:
                    # Use individual date from form
                    date_value = user_input.get(assignee_name)
                    if date_value:
                        # Convert to UTC datetime, then to ISO string for storage
                        # Per quality specs: dates stored in UTC ISO format
                        try:
                            utc_dt = dt_parse(
                                date_value,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                per_assignee_due_dates[assignee_id] = utc_dt.isoformat()
                        except ValueError as e:
                            const.LOGGER.warning(
                                "Invalid date for %s: %s", assignee_name, e
                            )
                            errors[assignee_name] = (
                                const.TRANS_KEY_CFOF_INVALID_DUE_DATE
                            )

            # Validate: If ALL dates are cleared, check recurring frequency compatibility
            # Only none, daily, weekly frequencies work without due dates
            if not errors and not per_assignee_due_dates:
                stored_chore = coordinator.chores_data.get(internal_id, {})
                recurring_frequency = stored_chore.get(
                    const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
                )
                if recurring_frequency not in (
                    const.FREQUENCY_NONE,
                    const.FREQUENCY_DAILY,
                    const.FREQUENCY_WEEKLY,
                ):
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DATE_REQUIRED_FOR_FREQUENCY
                    )
                    const.LOGGER.debug(
                        "Cannot clear all dates: frequency '%s' requires due dates",
                        recurring_frequency,
                    )

            if not errors:
                # Update the chore's per_assignee_due_dates using Manager CRUD
                chores_data = coordinator.chores_data
                if internal_id in chores_data:
                    # Pass only the field to update; Manager merges with existing
                    coordinator.chore_manager.update_chore(
                        str(internal_id),
                        {
                            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: per_assignee_due_dates
                        },
                        immediate_persist=True,
                    )
                    const.LOGGER.debug(
                        "Updated per-assignee due dates for chore %s: %s",
                        internal_id,
                        per_assignee_due_dates,
                    )

                # Clear stored state
                self._chore_being_edited = None
                self._chore_template_date_raw = None
                self._mark_reload_needed()
                return await self.async_step_init()

        # Build dynamic schema with assignee names as field keys (for readable labels)
        chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")
        schema_fields: dict[Any, Any] = {}
        assignee_names_list: list[str] = []

        # Add "Apply template to all" checkbox if template date exists
        if template_date_display:
            schema_fields[
                vol.Optional(
                    const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, default=False
                )
            ] = selector.BooleanSelector()

        for assignee_name, assignee_id in name_to_id.items():
            assignee_names_list.append(assignee_name)

            # Get existing date for this assignee from storage
            existing_date = existing_per_assignee_dates.get(assignee_id)

            # Convert to local datetime string for DateTimeSelector display
            # Storage is UTC ISO; display is local timezone
            default_value = None
            if existing_date:
                with contextlib.suppress(ValueError, TypeError):
                    default_value = dt_parse(
                        existing_date,
                        default_tzinfo=const.DEFAULT_TIME_ZONE,
                        return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                    )

            # Use assignee name as field key - HA will display it as the label
            # (field keys without translations are shown as-is)
            schema_fields[vol.Optional(assignee_name, default=default_value)] = vol.Any(
                None, selector.DateTimeSelector()
            )

            # Add clear checkbox for this assignee if they have an existing date
            if existing_date:
                clear_field_name = f"clear_due_date_{assignee_name}"
                schema_fields[
                    vol.Optional(clear_field_name, default=False, description="🗑️")
                ] = selector.BooleanSelector()

        # Build description with assignee names in order
        assignee_list_text = ", ".join(assignee_names_list)

        # Build description placeholders
        description_placeholders = {
            "chore_name": chore_name,
            "assignee_names": assignee_list_text,
            const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHORES_ADVANCED,
        }

        # Add template date info if available (shows in description)
        if template_date_display:
            description_placeholders["template_date"] = (
                f"\n\nTemplate date from main form: **{template_date_display}**. "
                "Check 'Apply template date to all assignees' to use this date for everyone."
            )
        else:
            description_placeholders["template_date"] = ""

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DATES,
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    # ----- Unified Per-Assignee Details Helper -----
    async def async_step_edit_chore_per_user_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Unified helper: per-assignee days + times + due dates with templating.

        PKAD-2026-001: Consolidates configuration for INDEPENDENT chores.

        Features:
        - Applicable days multi-select per assignee (always shown for INDEPENDENT)
        - Daily multi times text input per assignee (if frequency = DAILY_MULTI)
        - Due date picker per assignee (existing functionality)
        - Template section with "Apply to All" buttons
        - Pre-populates from main form values
        """
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}

        # Get chore data from stored state
        chore_data = getattr(self, "_chore_being_edited", None)
        if not chore_data:
            const.LOGGER.error("Per-assignee details step called without chore data")
            return await self.async_step_init()

        internal_id = chore_data.get(const.DATA_INTERNAL_ID)
        if not internal_id:
            const.LOGGER.error("Per-assignee details step: missing internal_id")
            return await self.async_step_init()

        # Only for INDEPENDENT chores
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if completion_criteria != const.COMPLETION_CRITERIA_INDEPENDENT:
            const.LOGGER.debug(
                "Per-assignee details step skipped - not INDEPENDENT (criteria: %s)",
                completion_criteria,
            )
            return await self.async_step_init()

        assigned_assignees = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        if not assigned_assignees:
            const.LOGGER.debug(
                "Per-assignee details step skipped - no assigned assignees"
            )
            return await self.async_step_init()

        # Get frequency to determine if DAILY_MULTI times are needed
        recurring_frequency = chore_data.get(
            const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        )
        is_daily_multi = recurring_frequency == const.FREQUENCY_DAILY_MULTI

        # Get template values from stored state (set before routing here)
        template_applicable_days = getattr(self, "_chore_template_applicable_days", [])
        template_daily_multi_times = getattr(
            self, "_chore_template_daily_multi_times", ""
        )
        raw_template_date = getattr(self, "_chore_template_date_raw", None)

        # Convert template date to display format and validate it's not in the past
        template_date_str = None
        template_date_display = None
        if raw_template_date:
            try:
                utc_dt = dt_parse(
                    raw_template_date,
                    default_tzinfo=const.DEFAULT_TIME_ZONE,
                    return_type=const.HELPER_RETURN_DATETIME_UTC,
                )
                if utc_dt and isinstance(utc_dt, datetime):
                    # Validate template date is not in the past
                    if utc_dt < dt_now_utc():
                        const.LOGGER.warning(
                            "Template due date %s is in the past, clearing template",
                            raw_template_date,
                        )
                        # Clear template if it's in the past
                        raw_template_date = None
                        self._chore_template_date_raw = None
                    else:
                        template_date_str = utc_dt.isoformat()
                        template_date_display = dt_parse(
                            raw_template_date,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                        )
            except (ValueError, TypeError):
                const.LOGGER.warning(
                    "Invalid template due date %s, clearing template", raw_template_date
                )
                raw_template_date = None
                self._chore_template_date_raw = None

        # Build name-to-id mapping for assigned assignees
        name_to_id: dict[str, str] = {}
        for assignee_id in assigned_assignees:
            assignee_info = coordinator.assignees_data.get(assignee_id, {})
            assignee_name = assignee_info.get(const.DATA_USER_NAME, assignee_id)
            name_to_id[assignee_name] = assignee_id

        # Get existing per-assignee data from storage
        stored_chore = coordinator.chores_data.get(internal_id, {})
        existing_per_assignee_days = stored_chore.get(
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}
        )
        existing_per_assignee_times = stored_chore.get(
            const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES, {}
        )
        existing_per_assignee_dates = stored_chore.get(
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {}
        )

        if user_input is not None:
            # Process "Apply to All" actions
            apply_days_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL, False
            )
            apply_times_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL, False
            )
            apply_date_to_all = user_input.get(
                const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, False
            )

            per_assignee_applicable_days: dict[str, list[int]] = {}
            per_assignee_daily_multi_times: dict[str, str] = {}
            per_assignee_due_dates: dict[str, str | None] = {}

            for assignee_name, assignee_id in name_to_id.items():
                # Process applicable days
                if apply_days_to_all and template_applicable_days:
                    # Convert string day keys to integers for storage
                    per_assignee_applicable_days[assignee_id] = [
                        list(const.WEEKDAY_OPTIONS.keys()).index(d)
                        for d in template_applicable_days
                        if d in const.WEEKDAY_OPTIONS
                    ]
                else:
                    days_field = f"applicable_days_{assignee_name}"
                    raw_days = user_input.get(days_field, [])
                    # Convert string day keys (mon, tue...) to integers (0-6)
                    per_assignee_applicable_days[assignee_id] = [
                        list(const.WEEKDAY_OPTIONS.keys()).index(d)
                        for d in raw_days
                        if d in const.WEEKDAY_OPTIONS
                    ]

                # Process daily multi times (if applicable)
                if is_daily_multi:
                    if apply_times_to_all and template_daily_multi_times:
                        per_assignee_daily_multi_times[assignee_id] = (
                            template_daily_multi_times
                        )
                    else:
                        times_field = f"daily_multi_times_{assignee_name}"
                        per_assignee_daily_multi_times[assignee_id] = user_input.get(
                            times_field, ""
                        )

                # Process due dates
                clear_field_name = f"clear_due_date_{assignee_name}"
                clear_this_assignee = user_input.get(clear_field_name, False)

                if apply_date_to_all and template_date_str:
                    per_assignee_due_dates[assignee_id] = template_date_str
                elif clear_this_assignee:
                    per_assignee_due_dates[assignee_id] = None
                else:
                    date_value = user_input.get(f"due_date_{assignee_name}")
                    if date_value:
                        try:
                            utc_dt = dt_parse(
                                date_value,
                                default_tzinfo=const.DEFAULT_TIME_ZONE,
                                return_type=const.HELPER_RETURN_DATETIME_UTC,
                            )
                            if utc_dt and isinstance(utc_dt, datetime):
                                # Validate that due date is not in the past
                                if utc_dt < dt_now_utc():
                                    errors[const.CFOP_ERROR_BASE] = (
                                        const.TRANS_KEY_CFOF_DUE_DATE_IN_PAST
                                    )
                                else:
                                    per_assignee_due_dates[assignee_id] = (
                                        utc_dt.isoformat()
                                    )
                        except (ValueError, TypeError):
                            errors[const.CFOP_ERROR_BASE] = (
                                const.TRANS_KEY_CFOF_INVALID_DUE_DATE
                            )
                    else:
                        # Preserve existing date if field left blank
                        per_assignee_due_dates[assignee_id] = (
                            existing_per_assignee_dates.get(assignee_id)
                        )

            # Validate per-assignee structures
            is_valid_days, days_error = fh.validate_per_assignee_applicable_days(
                per_assignee_applicable_days
            )
            if not is_valid_days and days_error:
                errors[const.CFOP_ERROR_BASE] = days_error

            if is_daily_multi and not errors:
                is_valid_times, times_error = (
                    fh.validate_per_assignee_daily_multi_times(
                        per_assignee_daily_multi_times, recurring_frequency
                    )
                )
                if not is_valid_times and times_error:
                    errors[const.CFOP_ERROR_BASE] = times_error

            if not errors:
                # Store per-assignee data in chore
                chore_data[const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS] = (
                    per_assignee_applicable_days
                )
                chore_data[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = (
                    per_assignee_due_dates
                )

                if is_daily_multi:
                    chore_data[const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES] = (
                        per_assignee_daily_multi_times
                    )

                # PKAD-2026-001: For INDEPENDENT chores, clear chore-level fields
                # (per-assignee structures are now the single source of truth)
                chore_data[const.DATA_CHORE_APPLICABLE_DAYS] = None
                chore_data[const.DATA_CHORE_DUE_DATE] = None
                if is_daily_multi:
                    chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = None

                # Use Manager-owned CRUD (handles badge recalc and orphan cleanup)
                coordinator.chore_manager.update_chore(
                    str(internal_id), chore_data, immediate_persist=True
                )

                const.LOGGER.debug(
                    "Updated per-assignee details for chore %s: days=%s, dates=%s",
                    internal_id,
                    per_assignee_applicable_days,
                    per_assignee_due_dates,
                )

                # Clear stored state
                self._chore_being_edited = None
                self._chore_template_date_raw = None
                self._chore_template_applicable_days = None
                self._chore_template_daily_multi_times = None
                self._mark_reload_needed()
                return await self.async_step_init()

        # Build form schema
        schema_fields: dict[Any, Any] = {}
        assignee_names_list: list[str] = []

        # Template section - "Apply to All" checkboxes
        if template_applicable_days:
            schema_fields[
                vol.Optional(const.CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL, default=False)
            ] = selector.BooleanSelector()

        if is_daily_multi and template_daily_multi_times:
            schema_fields[
                vol.Optional(const.CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL, default=False)
            ] = selector.BooleanSelector()

        if template_date_display:
            schema_fields[
                vol.Optional(
                    const.CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL, default=False
                )
            ] = selector.BooleanSelector()

        # Per-assignee fields
        for assignee_name, assignee_id in name_to_id.items():
            assignee_names_list.append(assignee_name)

            # Applicable days multi-select
            # Convert stored integers back to string keys for selector default
            existing_days_ints = existing_per_assignee_days.get(assignee_id, [])
            weekday_keys = list(const.WEEKDAY_OPTIONS.keys())
            default_days = [
                weekday_keys[i]
                for i in existing_days_ints
                if 0 <= i < len(weekday_keys)
            ]
            # If no existing per-assignee days, use template
            if not default_days and template_applicable_days:
                default_days = template_applicable_days

            schema_fields[
                vol.Optional(f"applicable_days_{assignee_name}", default=default_days)
            ] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": key, "label": f"{assignee_name}: {label}"}
                        for key, label in const.WEEKDAY_OPTIONS.items()
                    ],
                    multiple=True,
                )
            )

            # Daily multi times text input (conditional on DAILY_MULTI)
            if is_daily_multi:
                default_times = existing_per_assignee_times.get(
                    assignee_id, template_daily_multi_times
                )
                schema_fields[
                    vol.Optional(
                        f"daily_multi_times_{assignee_name}", default=default_times
                    )
                ] = selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                )

            # Due date picker
            existing_date = existing_per_assignee_dates.get(assignee_id)
            default_date_value = None
            if existing_date:
                with contextlib.suppress(ValueError, TypeError):
                    default_date_value = dt_parse(
                        existing_date,
                        default_tzinfo=const.DEFAULT_TIME_ZONE,
                        return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
                    )

            schema_fields[
                vol.Optional(f"due_date_{assignee_name}", default=default_date_value)
            ] = vol.Any(None, selector.DateTimeSelector())

            # Add clear checkbox if date exists
            if existing_date:
                schema_fields[
                    vol.Optional(f"clear_due_date_{assignee_name}", default=False)
                ] = selector.BooleanSelector()

        # Build description placeholders
        chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")
        assignee_list_text = ", ".join(assignee_names_list)

        # Build template info section for description
        template_info_parts: list[str] = []
        if template_applicable_days:
            days_display = ", ".join(
                const.WEEKDAY_OPTIONS.get(d) or d for d in template_applicable_days
            )
            template_info_parts.append(f"**Template days:** {days_display}")
        if is_daily_multi and template_daily_multi_times:
            template_info_parts.append(
                f"**Template times:** {template_daily_multi_times}"
            )
        if template_date_display:
            template_info_parts.append(f"**Template date:** {template_date_display}")

        template_info = ""
        if template_info_parts:
            template_info = "\n\n" + "\n".join(template_info_parts)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DETAILS,
            data_schema=vol.Schema(schema_fields),
            errors=errors,
            description_placeholders={
                "chore_name": chore_name,
                "assignee_names": assignee_list_text,
                "template_info": template_info,
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHORES_ADVANCED,
            },
        )

    # ----- Daily Multi Times Helper Step -----
    async def async_step_chores_daily_multi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect daily time slots for FREQUENCY_DAILY_MULTI chores.

        CFE-2026-001 Feature 2: Helper form to collect pipe-separated times.
        Pattern follows edit_chore_per_user_dates helper.

        Features:
        - Shows chore name in title
        - Collects pipe-separated times (e.g., "08:00|17:00")
        - Validates format, count (2-6 times), and range
        - Stores validated times in chore data
        """
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}

        # Get chore data from stored state
        chore_data = getattr(self, "_chore_being_edited", None)
        if not chore_data:
            const.LOGGER.error("Daily multi times step called without chore data")
            return await self.async_step_init()

        internal_id = chore_data.get(const.DATA_INTERNAL_ID)
        if not internal_id:
            const.LOGGER.error("Daily multi times step: missing internal_id")
            return await self.async_step_init()

        chore_name = chore_data.get(const.DATA_CHORE_NAME, "Unknown")

        if user_input is not None:
            times_str = user_input.get(
                const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES, ""
            ).strip()

            # Validate the times string
            is_valid, error_key = validate_daily_multi_times(times_str)

            if not is_valid and error_key:
                errors[const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES] = error_key
            else:
                # Valid - store times in chore data using Manager CRUD
                chore_data[const.DATA_CHORE_DAILY_MULTI_TIMES] = times_str

                # Use Manager-owned CRUD (handles badge recalc and orphan cleanup)
                coordinator.chore_manager.update_chore(
                    str(internal_id), chore_data, immediate_persist=True
                )

                const.LOGGER.info(
                    "Set daily multi times for chore '%s': %s",
                    chore_name,
                    times_str,
                )

                self._mark_reload_needed()
                # Clear temp state
                self._chore_being_edited = None
                return await self.async_step_init()

        # Get existing times if editing
        existing_times = chore_data.get(const.DATA_CHORE_DAILY_MULTI_TIMES, "")

        # Build form schema
        schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES,
                    default=existing_times,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI,
            data_schema=schema,
            errors=errors,
            description_placeholders={"chore_name": chore_name},
        )

    async def async_step_delete_chore(self, user_input=None):
        """Delete a chore."""
        coordinator = self._get_coordinator()
        chores_dict = coordinator.chores_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in chores_dict:
            const.LOGGER.error("Delete Chore - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHORE)

        chore_name = chores_dict[internal_id][const.DATA_CHORE_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.chore_manager.delete_chore(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Chore '%s' with ID: %s", chore_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_CHORE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_CHORE_NAME: chore_name
            },
        )

    # ----------------------------------------------------------------------------------
    # BADGES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_badge(self, user_input=None):
        """Entry point to add a new badge."""
        if user_input is not None:
            badge_type = user_input[const.CFOF_BADGES_INPUT_TYPE]
            cast("dict[str, Any]", self.context)[const.CFOF_BADGES_INPUT_TYPE] = (
                badge_type
            )

            # Redirect to the appropriate step based on badge type
            if badge_type == const.BADGE_TYPE_CUMULATIVE:
                return await self.async_step_add_badge_cumulative()
            if badge_type == const.BADGE_TYPE_DAILY:
                return await self.async_step_add_badge_daily()
            if badge_type == const.BADGE_TYPE_PERIODIC:
                return await self.async_step_add_badge_periodic()
            if badge_type == const.BADGE_TYPE_ACHIEVEMENT_LINKED:
                return await self.async_step_add_badge_achievement()
            if badge_type == const.BADGE_TYPE_CHALLENGE_LINKED:
                return await self.async_step_add_badge_challenge()
            if badge_type == const.BADGE_TYPE_SPECIAL_OCCASION:
                return await self.async_step_add_badge_special()
            # Fallback to cumulative if unknown.
            return await self.async_step_add_badge_cumulative()

        badge_type_options = [
            const.BADGE_TYPE_CUMULATIVE,
            const.BADGE_TYPE_DAILY,
            const.BADGE_TYPE_PERIODIC,
            const.BADGE_TYPE_ACHIEVEMENT_LINKED,
            const.BADGE_TYPE_CHALLENGE_LINKED,
            const.BADGE_TYPE_SPECIAL_OCCASION,
        ]
        schema = vol.Schema(
            {
                vol.Required(const.CFOF_BADGES_INPUT_TYPE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=badge_type_options,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_TYPE,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_BADGE, data_schema=schema
        )

    # ----- Add Achievement-Linked Badge -----
    async def async_step_add_badge_achievement(self, user_input=None):
        """Handle adding an achievement-linked badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for achievement-linked badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_ACHIEVEMENT_LINKED,
            is_edit=False,
        )

    # ----- Add Challenge-Linked Badge -----
    async def async_step_add_badge_challenge(self, user_input=None):
        """Handle adding a challenge-linked badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for challenge-linked badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CHALLENGE_LINKED,
            is_edit=False,
        )

    # ----- Add Cumulative Badge (Points-only) -----
    async def async_step_add_badge_cumulative(self, user_input=None):
        """Handle adding a cumulative badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for cumulative badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CUMULATIVE,
            is_edit=False,
        )

    # ----- Add Daily Badge -----
    async def async_step_add_badge_daily(self, user_input=None):
        """Handle adding a daily badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for daily badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_DAILY,
            is_edit=False,
        )

    # ----- Add Periodic Badge -----
    async def async_step_add_badge_periodic(self, user_input=None):
        """Handle adding a periodic badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for periodic badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_PERIODIC,
            is_edit=False,
        )

    # ----- Add Special Occasion Badge -----
    async def async_step_add_badge_special(self, user_input=None):
        """Handle adding a special occasion badge."""
        # Redirect to the common function with the appropriate badge type
        # Allows customization of the UI text for special occasion badges
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_SPECIAL_OCCASION,
            is_edit=False,
        )

    # ----- Add Badge Centralized Function for All Types -----
    async def async_add_edit_badge_common(
        self,
        user_input: dict[str, Any] | None = None,
        badge_type: str = const.BADGE_TYPE_CUMULATIVE,
        default_data: dict[str, Any] | None = None,
        is_edit: bool = False,
    ):
        """Handle adding or editing a badge."""
        coordinator = self._get_coordinator()
        badges_dict = coordinator.badges_data
        chores_dict = coordinator.chores_data
        assignees_dict = coordinator.assignees_data
        rewards_dict = coordinator.rewards_data
        achievements_dict = coordinator.achievements_data
        challenges_dict = coordinator.challenges_data
        bonuses_dict = coordinator.bonuses_data
        penalties_dict = coordinator.penalties_data
        valid_assignee_ids = set(assignees_dict.keys())
        valid_chore_ids = set(chores_dict.keys())
        valid_achievement_ids = set(achievements_dict.keys())
        valid_challenge_ids = set(challenges_dict.keys())

        errors: dict[str, str] = {}

        # Determine internal_id (UUID-based primary key, persists across renames)
        if is_edit:
            # Edit mode: retrieve internal_id from context (set when user selected badge to edit)
            # Cast from context dict which returns object type
            internal_id: str | None = cast(
                "str | None", self.context.get(const.CFOF_GLOBAL_INPUT_INTERNAL_ID)
            )
            # Validate that the badge still exists (defensive: could have been deleted by another process)
            if not internal_id or internal_id not in badges_dict:
                const.LOGGER.error("Invalid Internal ID for editing badge.")
                return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE)
        else:
            # Add mode: generate new UUID and store in context for form resubmissions
            # Context persists across form validation errors (same internal_id on retry)
            internal_id = str(uuid.uuid4())
            # Cast context to dict[str, Any] since HA's ConfigFlowContext doesn't allow arbitrary keys
            # but we need to store internal_id for form resubmission across validation errors
            cast("dict[str, Any]", self.context)[
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID
            ] = internal_id

        if user_input is not None:
            # --- Validate Inputs ---
            # Badge validation is complex: checks name uniqueness, reward/bonus/penalty
            # existence, and type-specific rules (e.g., periodic requires repeat_interval)
            errors = fh.validate_badge_common_inputs(
                user_input=user_input,
                internal_id=internal_id,
                existing_badges=badges_dict,
                rewards_dict=rewards_dict,
                bonuses_dict=bonuses_dict,
                penalties_dict=penalties_dict,
                badge_type=badge_type,
            )

            badge_dict: BadgeData | None = None
            if not errors:
                # --- Build Data using data_builders (modern pattern) ---
                try:
                    if is_edit:
                        existing_badge = badges_dict.get(internal_id)
                        badge_dict = db.build_badge(
                            user_input,
                            existing=existing_badge,
                            badge_type=badge_type,
                        )
                    else:
                        badge_dict = db.build_badge(
                            user_input,
                            badge_type=badge_type,
                        )
                        # Override internal_id with the one from context
                        badge_dict[const.DATA_BADGE_INTERNAL_ID] = internal_id
                except db.EntityValidationError as err:
                    errors[err.field] = err.translation_key
                    badge_dict = None

            if not errors and badge_dict is not None:
                # Use Manager-owned CRUD methods (handles sync, recalc, persist)
                if is_edit:
                    coordinator.gamification_manager.update_badge(
                        str(internal_id),
                        user_input,
                        badge_type=badge_type,
                        immediate_persist=True,
                    )
                else:
                    coordinator.gamification_manager.create_badge(
                        user_input,
                        internal_id=internal_id,
                        badge_type=badge_type,
                        immediate_persist=True,
                    )

                const.LOGGER.debug(
                    "%s Badge '%s' with ID: %s. Data: %s",
                    "Updated" if is_edit else "Added",
                    badge_dict[const.DATA_BADGE_NAME],
                    internal_id,
                    badge_dict,
                )

                self._mark_reload_needed()
                return await self.async_step_init()

        # --- Build Schema with Suggested Values ---
        # Build suggested values from existing badge data (edit) or empty (add)
        suggested_values: dict[str, Any] = {}

        if is_edit and internal_id:
            existing_badge = badges_dict.get(internal_id, {})
            # Flatten nested badge data into CFOF_* keys for form population
            target_data = existing_badge.get(const.DATA_BADGE_TARGET, {})
            awards_data = existing_badge.get(const.DATA_BADGE_AWARDS, {})
            tracked_chores_data = existing_badge.get(
                const.DATA_BADGE_TRACKED_CHORES, {}
            )
            reset_schedule_data = existing_badge.get(
                const.DATA_BADGE_RESET_SCHEDULE, {}
            )

            suggested_values = {
                # Common fields
                const.CFOF_BADGES_INPUT_NAME: existing_badge.get(const.DATA_BADGE_NAME),
                const.CFOF_BADGES_INPUT_DESCRIPTION: existing_badge.get(
                    const.DATA_BADGE_DESCRIPTION
                ),
                const.CFOF_BADGES_INPUT_LABELS: existing_badge.get(
                    const.DATA_BADGE_LABELS, []
                ),
                const.CFOF_BADGES_INPUT_ICON: existing_badge.get(const.DATA_BADGE_ICON),
                # Target fields
                const.CFOF_BADGES_INPUT_TARGET_TYPE: target_data.get(
                    const.DATA_BADGE_TARGET_TYPE
                ),
                const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: target_data.get(
                    const.DATA_BADGE_TARGET_THRESHOLD_VALUE
                ),
                const.CFOF_BADGES_INPUT_MAINTENANCE_RULES: target_data.get(
                    const.DATA_BADGE_MAINTENANCE_RULES
                ),
                # Special occasion
                const.CFOF_BADGES_INPUT_OCCASION_TYPE: existing_badge.get(
                    const.DATA_BADGE_SPECIAL_OCCASION_TYPE
                ),
                # Linked entities
                const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT: existing_badge.get(
                    const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT
                ),
                const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE: existing_badge.get(
                    const.DATA_BADGE_ASSOCIATED_CHALLENGE
                ),
                # Tracked chores
                const.CFOF_BADGES_INPUT_SELECTED_CHORES: tracked_chores_data.get(
                    const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
                ),
                # Assigned to
                const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: existing_badge.get(
                    const.DATA_BADGE_ASSIGNED_USER_IDS, []
                ),
                # Awards
                const.CFOF_BADGES_INPUT_AWARD_ITEMS: awards_data.get(
                    const.DATA_BADGE_AWARDS_AWARD_ITEMS, []
                ),
                const.CFOF_BADGES_INPUT_AWARD_POINTS: awards_data.get(
                    const.DATA_BADGE_AWARDS_AWARD_POINTS
                ),
                const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER: awards_data.get(
                    const.DATA_BADGE_AWARDS_POINT_MULTIPLIER
                ),
                # Reset schedule
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY: (
                    reset_schedule_data.get(
                        const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY
                    )
                ),
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL: (
                    reset_schedule_data.get(
                        const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
                    )
                ),
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: (
                    reset_schedule_data.get(
                        const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
                    )
                ),
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE: (
                    reset_schedule_data.get(const.DATA_BADGE_RESET_SCHEDULE_START_DATE)
                ),
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE: (
                    reset_schedule_data.get(const.DATA_BADGE_RESET_SCHEDULE_END_DATE)
                ),
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS: (
                    reset_schedule_data.get(
                        const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS
                    )
                ),
            }

            suggested_values[const.CFOF_BADGES_INPUT_SELECTED_CHORES] = (
                _sanitize_select_values(
                    suggested_values.get(const.CFOF_BADGES_INPUT_SELECTED_CHORES, []),
                    valid_chore_ids,
                )
            )
            suggested_values[const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS] = (
                _sanitize_select_values(
                    suggested_values.get(const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS, []),
                    valid_assignee_ids,
                )
            )

            associated_achievement = suggested_values.get(
                const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT,
                const.SENTINEL_NO_SELECTION,
            )
            if (
                associated_achievement != const.SENTINEL_NO_SELECTION
                and associated_achievement not in valid_achievement_ids
            ):
                suggested_values[const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT] = (
                    const.SENTINEL_NO_SELECTION
                )

            associated_challenge = suggested_values.get(
                const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE,
                const.SENTINEL_NO_SELECTION,
            )
            if (
                associated_challenge != const.SENTINEL_NO_SELECTION
                and associated_challenge not in valid_challenge_ids
            ):
                suggested_values[const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE] = (
                    const.SENTINEL_NO_SELECTION
                )

        # On validation error, preserve user's attempted input
        if user_input:
            suggested_values.update(user_input)

        suggested_values[const.CFOF_BADGES_INPUT_SELECTED_CHORES] = (
            _sanitize_select_values(
                suggested_values.get(const.CFOF_BADGES_INPUT_SELECTED_CHORES, []),
                valid_chore_ids,
            )
        )
        suggested_values[const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS] = (
            _sanitize_select_values(
                suggested_values.get(const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS, []),
                valid_assignee_ids,
            )
        )

        associated_achievement = suggested_values.get(
            const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT,
            const.SENTINEL_NO_SELECTION,
        )
        if (
            associated_achievement != const.SENTINEL_NO_SELECTION
            and associated_achievement not in valid_achievement_ids
        ):
            suggested_values[const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT] = (
                const.SENTINEL_NO_SELECTION
            )

        associated_challenge = suggested_values.get(
            const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE,
            const.SENTINEL_NO_SELECTION,
        )
        if (
            associated_challenge != const.SENTINEL_NO_SELECTION
            and associated_challenge not in valid_challenge_ids
        ):
            suggested_values[const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE] = (
                const.SENTINEL_NO_SELECTION
            )

        # Build schema without embedded defaults (values come from suggested_values)
        schema_fields = fh.build_badge_common_schema(
            default=None,
            assignees_dict=assignees_dict,
            chores_dict=chores_dict,
            rewards_dict=rewards_dict,
            achievements_dict=achievements_dict,
            challenges_dict=challenges_dict,
            bonuses_dict=bonuses_dict,
            penalties_dict=penalties_dict,
            badge_type=badge_type,
        )
        data_schema = vol.Schema(schema_fields)

        # Apply suggested values to schema
        data_schema = self.add_suggested_values_to_schema(data_schema, suggested_values)

        # Determine step name dynamically
        step_name = (
            const.OPTIONS_FLOW_EDIT_STEP.get(badge_type)
            if is_edit
            else const.OPTIONS_FLOW_ADD_STEP.get(badge_type)
        )
        if not step_name:
            const.LOGGER.error("Invalid badge type '%s'.", badge_type)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE_TYPE)

        # Determine documentation URL based on badge type
        doc_url_map = {
            const.BADGE_TYPE_CUMULATIVE: const.DOC_URL_BADGES_CUMULATIVE,
            const.BADGE_TYPE_ACHIEVEMENT_LINKED: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_CHALLENGE_LINKED: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_DAILY: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_PERIODIC: const.DOC_URL_BADGES_OVERVIEW,
            const.BADGE_TYPE_SPECIAL_OCCASION: const.DOC_URL_BADGES_OVERVIEW,
        }
        doc_url = doc_url_map.get(badge_type, const.DOC_URL_BADGES_OVERVIEW)

        return self.async_show_form(
            step_id=step_name,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={const.PLACEHOLDER_DOCUMENTATION_URL: doc_url},
            last_step=False,
        )

    # ----- Edit Achievement-Linked Badge -----
    async def async_step_edit_badge_achievement(
        self, user_input=None, default_data=None
    ):
        """Handle editing an achievement-linked badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_ACHIEVEMENT_LINKED,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Challenge-Linked Badge -----
    async def async_step_edit_badge_challenge(self, user_input=None, default_data=None):
        """Handle editing a challenge-linked badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CHALLENGE_LINKED,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Cumulative Badge -----
    async def async_step_edit_badge_cumulative(
        self, user_input=None, default_data=None
    ):
        """Handle editing a cumulative badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_CUMULATIVE,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Daily Badge -----
    async def async_step_edit_badge_daily(self, user_input=None, default_data=None):
        """Handle editing a daily badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_DAILY,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Periodic Badge -----
    async def async_step_edit_badge_periodic(self, user_input=None, default_data=None):
        """Handle editing a periodic badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_PERIODIC,
            default_data=default_data,
            is_edit=True,
        )

    # ----- Edit Special Occasion Badge -----
    async def async_step_edit_badge_special(self, user_input=None, default_data=None):
        """Handle editing a special occasion badge."""
        return await self.async_add_edit_badge_common(
            user_input=user_input,
            badge_type=const.BADGE_TYPE_SPECIAL_OCCASION,
            default_data=default_data,
            is_edit=True,
        )

    async def async_step_delete_badge(self, user_input=None):
        """Delete a badge."""
        coordinator = self._get_coordinator()
        badges_dict = coordinator.badges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in badges_dict:
            const.LOGGER.error("Delete Badge - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BADGE)

        badge_name = badges_dict[internal_id][const.DATA_BADGE_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.gamification_manager.delete_badge(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Badge '%s' with ID: %s", badge_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BADGE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_BADGE_NAME: badge_name
            },
        )

    # ----------------------------------------------------------------------------------
    # REWARDS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_reward(self, user_input=None):
        """Add a new reward."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        rewards_dict = coordinator.rewards_data

        if user_input is not None:
            # Layer 2: UI validation (uniqueness check)
            errors = fh.validate_rewards_inputs(user_input, rewards_dict)

            if not errors:
                try:
                    # Use Manager-owned CRUD method
                    reward_data = coordinator.reward_manager.create_reward(
                        user_input, immediate_persist=True
                    )

                    const.LOGGER.debug(
                        "Added Reward '%s' with ID: %s",
                        reward_data[const.DATA_REWARD_NAME],
                        reward_data[const.DATA_REWARD_INTERNAL_ID],
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        schema = fh.build_reward_schema()

        # On validation error, preserve user's attempted input
        if user_input:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_REWARD,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_REWARDS
            },
        )

    async def async_step_edit_reward(self, user_input=None):
        """Edit an existing reward."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        rewards_dict = coordinator.rewards_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in rewards_dict:
            const.LOGGER.error("Edit Reward - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_REWARD)

        existing_reward = rewards_dict[internal_id]

        if user_input is not None:
            # Build a temporary dict for duplicate checking that excludes current reward
            rewards_for_validation = {
                rid: rdata for rid, rdata in rewards_dict.items() if rid != internal_id
            }

            # Layer 2: UI validation (uniqueness check)
            errors = fh.validate_rewards_inputs(user_input, rewards_for_validation)

            if not errors:
                try:
                    # Use Manager-owned CRUD method
                    updated_reward = coordinator.reward_manager.update_reward(
                        str(internal_id), user_input, immediate_persist=True
                    )

                    const.LOGGER.debug(
                        "Edited Reward '%s' with ID: %s",
                        updated_reward[const.DATA_REWARD_NAME],
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    # Map field-specific error for form highlighting
                    errors[err.field] = err.translation_key

        # Prepare suggested values for form (current reward data)
        suggested_values = {
            const.CFOF_REWARDS_INPUT_NAME: existing_reward.get(const.DATA_REWARD_NAME),
            const.CFOF_REWARDS_INPUT_DESCRIPTION: existing_reward.get(
                const.DATA_REWARD_DESCRIPTION
            ),
            const.CFOF_REWARDS_INPUT_LABELS: existing_reward.get(
                const.DATA_REWARD_LABELS, []
            ),
            const.CFOF_REWARDS_INPUT_COST: existing_reward.get(
                const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST
            ),
            const.CFOF_REWARDS_INPUT_ICON: existing_reward.get(const.DATA_REWARD_ICON),
        }

        # On validation error, merge user's attempted input with existing data
        if user_input:
            suggested_values.update(user_input)

        # Build schema with static defaults
        schema = fh.build_reward_schema()
        # Apply values as suggestions
        schema = self.add_suggested_values_to_schema(schema, suggested_values)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_REWARD,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_REWARDS
            },
        )

    async def async_step_delete_reward(self, user_input=None):
        """Delete a reward."""
        coordinator = self._get_coordinator()
        rewards_dict = coordinator.rewards_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in rewards_dict:
            const.LOGGER.error("Delete Reward - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_REWARD)

        reward_name = rewards_dict[internal_id][const.DATA_REWARD_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.reward_manager.delete_reward(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Reward '%s' with ID: %s", reward_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_REWARD,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_REWARD_NAME: reward_name
            },
        )

    # ----------------------------------------------------------------------------------
    # BONUSES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_bonus(self, user_input=None):
        """Add a new bonus."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        bonuses_dict = coordinator.bonuses_data

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_bonuses_inputs(user_input, bonuses_dict)

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_BONUS_NAME: user_input[const.CFOF_BONUSES_INPUT_NAME],
                    const.DATA_BONUS_DESCRIPTION: user_input.get(
                        const.CFOF_BONUSES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY
                    ),
                    const.DATA_BONUS_POINTS: user_input.get(
                        const.CFOF_BONUSES_INPUT_POINTS, const.DEFAULT_BONUS_POINTS
                    ),
                    const.DATA_BONUS_ICON: user_input.get(
                        const.CFOF_BONUSES_INPUT_ICON, const.SENTINEL_EMPTY
                    ),
                }
                # Use Manager-owned CRUD method
                bonus_data = coordinator.economy_manager.create_bonus(
                    transformed_input, immediate_persist=True
                )

                bonus_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "Added Bonus '%s' with ID: %s",
                    bonus_name,
                    bonus_data[const.DATA_BONUS_INTERNAL_ID],
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_bonus_schema()

        # On validation error, preserve user's attempted input
        if user_input:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_BONUS,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_BONUSES_PENALTIES
            },
        )

    async def async_step_edit_bonus(self, user_input=None):
        """Edit an existing bonus."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        bonuses_dict = coordinator.bonuses_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in bonuses_dict:
            const.LOGGER.error("Edit Bonus - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BONUS)

        bonus_data = bonuses_dict[internal_id]

        if user_input is not None:
            new_name = user_input[const.CFOF_BONUSES_INPUT_NAME].strip()

            # Validate using shared validator (excludes current bonus from duplicate check)
            # Note: internal_id is already validated as str above
            errors = fh.validate_bonuses_inputs(
                user_input, bonuses_dict, current_bonus_id=str(internal_id)
            )

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_BONUS_NAME: user_input.get(
                        const.CFOF_BONUSES_INPUT_NAME, bonus_data[const.DATA_BONUS_NAME]
                    ),
                    const.DATA_BONUS_DESCRIPTION: user_input.get(
                        const.CFOF_BONUSES_INPUT_DESCRIPTION,
                        bonus_data.get(
                            const.DATA_BONUS_DESCRIPTION, const.SENTINEL_EMPTY
                        ),
                    ),
                    const.DATA_BONUS_POINTS: user_input.get(
                        const.CFOF_BONUSES_INPUT_POINTS,
                        bonus_data.get(
                            const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS
                        ),
                    ),
                    const.DATA_BONUS_ICON: user_input.get(
                        const.CFOF_BONUSES_INPUT_ICON,
                        bonus_data.get(const.DATA_BONUS_ICON, const.SENTINEL_EMPTY),
                    ),
                }
                # Use Manager-owned CRUD method
                coordinator.economy_manager.update_bonus(
                    str(internal_id), transformed_input, immediate_persist=True
                )

                const.LOGGER.debug(
                    "Edited Bonus '%s' with ID: %s", new_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        # Prepare suggested values for form (current bonus data)
        suggested_values = {
            const.CFOF_BONUSES_INPUT_NAME: bonus_data.get(const.DATA_BONUS_NAME),
            const.CFOF_BONUSES_INPUT_DESCRIPTION: bonus_data.get(
                const.DATA_BONUS_DESCRIPTION
            ),
            const.CFOF_BONUSES_INPUT_LABELS: bonus_data.get(
                const.DATA_BONUS_LABELS, []
            ),
            const.CFOF_BONUSES_INPUT_POINTS: bonus_data.get(
                const.DATA_BONUS_POINTS, const.DEFAULT_BONUS_POINTS
            ),
            const.CFOF_BONUSES_INPUT_ICON: bonus_data.get(const.DATA_BONUS_ICON),
        }

        # On validation error, merge user's attempted input with existing data
        if user_input:
            suggested_values.update(user_input)

        # Build schema with static defaults
        schema = fh.build_bonus_schema()
        # Apply values as suggestions
        schema = self.add_suggested_values_to_schema(schema, suggested_values)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_BONUS,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_BONUSES_PENALTIES
            },
        )

    async def async_step_delete_bonus(self, user_input=None):
        """Delete a bonus."""
        coordinator = self._get_coordinator()
        bonuses_dict = coordinator.bonuses_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in bonuses_dict:
            const.LOGGER.error("Delete Bonus - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_BONUS)

        bonus_name = bonuses_dict[internal_id][const.DATA_BONUS_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.economy_manager.delete_bonus(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Bonus '%s' with ID: %s", bonus_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BONUS,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_BONUS_NAME: bonus_name
            },
        )

    # ----------------------------------------------------------------------------------
    # PENALTIES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_penalty(self, user_input=None):
        """Add a new penalty."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        penalties_dict = coordinator.penalties_data

        if user_input is not None:
            # Validate inputs
            errors = fh.validate_penalties_inputs(user_input, penalties_dict)

            if not errors:
                # Transform form input keys to DATA_* keys
                transformed_input = {
                    const.DATA_PENALTY_NAME: user_input[
                        const.CFOF_PENALTIES_INPUT_NAME
                    ],
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(
                        const.CFOF_PENALTIES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY
                    ),
                    const.DATA_PENALTY_POINTS: user_input.get(
                        const.CFOF_PENALTIES_INPUT_POINTS, const.DEFAULT_PENALTY_POINTS
                    ),
                    const.DATA_PENALTY_ICON: user_input.get(
                        const.CFOF_PENALTIES_INPUT_ICON, const.SENTINEL_EMPTY
                    ),
                }
                # Use Manager-owned CRUD method
                penalty_data = coordinator.economy_manager.create_penalty(
                    transformed_input, immediate_persist=True
                )

                penalty_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()
                const.LOGGER.debug(
                    "Added Penalty '%s' with ID: %s",
                    penalty_name,
                    penalty_data[const.DATA_PENALTY_INTERNAL_ID],
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        schema = fh.build_penalty_schema()

        # On validation error, preserve user's attempted input
        if user_input:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_PENALTY,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_BONUSES_PENALTIES
            },
        )

    async def async_step_edit_penalty(self, user_input=None):
        """Edit an existing penalty."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        penalties_dict = coordinator.penalties_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in penalties_dict:
            const.LOGGER.error("Edit Penalty - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PENALTY)

        penalty_data = penalties_dict[internal_id]

        if user_input is not None:
            # DEBUG: Log what HA actually sends when fields are cleared
            const.LOGGER.debug(
                "DEBUG edit_penalty user_input keys: %s", list(user_input.keys())
            )
            const.LOGGER.debug(
                "DEBUG edit_penalty DESCRIPTION in user_input: %s, value: %r",
                const.CFOF_PENALTIES_INPUT_DESCRIPTION in user_input,
                user_input.get(const.CFOF_PENALTIES_INPUT_DESCRIPTION, "KEY_MISSING"),
            )
            const.LOGGER.debug(
                "DEBUG edit_penalty ICON in user_input: %s, value: %r",
                const.CFOF_PENALTIES_INPUT_ICON in user_input,
                user_input.get(const.CFOF_PENALTIES_INPUT_ICON, "KEY_MISSING"),
            )

            new_name = user_input[const.CFOF_PENALTIES_INPUT_NAME].strip()

            # Validate using shared validator (excludes current penalty from duplicate check)
            # Note: internal_id is already validated as str above
            errors = fh.validate_penalties_inputs(
                user_input, penalties_dict, current_penalty_id=str(internal_id)
            )

            if not errors:
                # Transform form input keys to DATA_* keys
                # Note: When user clears optional fields (description, icon), Home Assistant
                # omits those keys from user_input. We use sentinel/default as fallback
                # instead of old values, so clearing a field actually clears it.
                transformed_input = {
                    const.DATA_PENALTY_NAME: user_input.get(
                        const.CFOF_PENALTIES_INPUT_NAME,
                        penalty_data[const.DATA_PENALTY_NAME],
                    ),
                    const.DATA_PENALTY_DESCRIPTION: user_input.get(
                        const.CFOF_PENALTIES_INPUT_DESCRIPTION,
                        const.SENTINEL_EMPTY,  # Use sentinel if cleared, not old value
                    ),
                    const.DATA_PENALTY_POINTS: user_input.get(
                        const.CFOF_PENALTIES_INPUT_POINTS,
                        penalty_data.get(
                            const.DATA_PENALTY_POINTS, const.DEFAULT_PENALTY_POINTS
                        ),
                    ),
                    const.DATA_PENALTY_ICON: user_input.get(
                        const.CFOF_PENALTIES_INPUT_ICON,
                        const.SENTINEL_EMPTY,  # Use default if cleared, not old value
                    ),
                }
                # Use Manager-owned CRUD method
                coordinator.economy_manager.update_penalty(
                    str(internal_id), transformed_input, immediate_persist=True
                )

                const.LOGGER.debug(
                    "Edited Penalty '%s' with ID: %s", new_name, internal_id
                )
                self._mark_reload_needed()
                return await self.async_step_init()

        # Prepare suggested values for form (current penalty data)
        suggested_values = {
            const.CFOF_PENALTIES_INPUT_NAME: penalty_data.get(const.DATA_PENALTY_NAME),
            const.CFOF_PENALTIES_INPUT_DESCRIPTION: penalty_data.get(
                const.DATA_PENALTY_DESCRIPTION
            ),
            const.CFOF_PENALTIES_INPUT_LABELS: penalty_data.get(
                const.DATA_PENALTY_LABELS, []
            ),
            const.CFOF_PENALTIES_INPUT_POINTS: abs(
                penalty_data.get(
                    const.DATA_PENALTY_POINTS, const.DEFAULT_PENALTY_POINTS
                )
            ),
            const.CFOF_PENALTIES_INPUT_ICON: penalty_data.get(const.DATA_PENALTY_ICON),
        }

        # On validation error, merge user's attempted input with existing data
        if user_input:
            suggested_values.update(user_input)

        # Build schema with static defaults
        schema = fh.build_penalty_schema()
        # Apply values as suggestions
        schema = self.add_suggested_values_to_schema(schema, suggested_values)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_PENALTY,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_BONUSES_PENALTIES
            },
        )

    async def async_step_delete_penalty(self, user_input=None):
        """Delete a penalty."""
        coordinator = self._get_coordinator()
        penalties_dict = coordinator.penalties_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in penalties_dict:
            const.LOGGER.error("Delete Penalty - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_PENALTY)

        penalty_name = penalties_dict[internal_id][const.DATA_PENALTY_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.economy_manager.delete_penalty(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Penalty '%s' with ID: %s", penalty_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_PENALTY,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_PENALTY_NAME: penalty_name
            },
        )

    # ----------------------------------------------------------------------------------
    # ACHIEVEMENTS MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_achievement(self, user_input=None):
        """Add a new achievement."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        achievements_dict = coordinator.achievements_data
        chores_dict = coordinator.chores_data

        if user_input is not None:
            # Layer 2: UI validation (uniqueness + type-specific checks)
            errors = fh.validate_achievements_inputs(user_input, achievements_dict)

            if not errors:
                try:
                    # Build assignees name to ID mapping for options flow
                    assignees_name_to_id = {
                        assignee[const.DATA_USER_NAME]: assignee[
                            const.DATA_USER_INTERNAL_ID
                        ]
                        for assignee in coordinator.data.get(
                            const.DATA_USERS, {}
                        ).values()
                    }

                    # Layer 3: Convert CFOF_* to DATA_* keys
                    data_input = db.map_cfof_to_achievement_data(user_input)

                    # Convert assigned assignees from names to IDs (options flow uses names)
                    assigned_assignees_names = data_input.get(
                        const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, []
                    )
                    if not isinstance(assigned_assignees_names, list):
                        assigned_assignees_names = (
                            [assigned_assignees_names]
                            if assigned_assignees_names
                            else []
                        )
                    data_input[const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS] = [
                        assignees_name_to_id.get(name, name)
                        for name in assigned_assignees_names
                    ]

                    # Use GamificationManager for achievement creation
                    internal_id = coordinator.gamification_manager.create_achievement(
                        data_input, immediate_persist=True
                    )
                    achievement_name = data_input.get(
                        const.DATA_ACHIEVEMENT_NAME, internal_id
                    )

                    const.LOGGER.debug(
                        "Added Achievement '%s' with ID: %s",
                        achievement_name,
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        assignees_dict = {
            assignee_data[const.DATA_USER_NAME]: assignee_id
            for assignee_id, assignee_data in coordinator.assignees_data.items()
        }

        # Build schema without defaults
        schema = fh.build_achievement_schema(
            assignees_dict=assignees_dict, chores_dict=chores_dict
        )

        # On validation error, preserve user's attempted input
        if user_input:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_ACHIEVEMENTS_OVERVIEW
            },
        )

    async def async_step_edit_achievement(self, user_input=None):
        """Edit an existing achievement."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        achievements_dict = coordinator.achievements_data

        internal_id = cast("str | None", self.context.get(const.DATA_INTERNAL_ID))
        if not internal_id or internal_id not in achievements_dict:
            const.LOGGER.error(
                "Edit Achievement - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT)

        achievement_data = achievements_dict[internal_id]

        if user_input is not None:
            # Check for duplicate names excluding current achievement
            achievements_except_current = {
                eid: data
                for eid, data in achievements_dict.items()
                if eid != internal_id
            }

            # Build assignees name to ID mapping for options flow
            assignees_name_to_id = {
                assignee[const.DATA_USER_NAME]: assignee[const.DATA_USER_INTERNAL_ID]
                for assignee in coordinator.data.get(const.DATA_USERS, {}).values()
            }

            # Layer 2: UI validation (uniqueness + type-specific checks)
            errors = fh.validate_achievements_inputs(
                user_input,
                achievements_except_current,
                current_achievement_id=internal_id,
            )

            if not errors:
                try:
                    # Layer 3: Convert CFOF_* to DATA_* keys
                    data_input = db.map_cfof_to_achievement_data(user_input)

                    # Convert assigned assignees from names to IDs (options flow uses names)
                    assigned_assignees_names = data_input.get(
                        const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, []
                    )
                    if not isinstance(assigned_assignees_names, list):
                        assigned_assignees_names = (
                            [assigned_assignees_names]
                            if assigned_assignees_names
                            else []
                        )
                    data_input[const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS] = [
                        assignees_name_to_id.get(name, name)
                        for name in assigned_assignees_names
                    ]

                    # Use GamificationManager for achievement update
                    coordinator.gamification_manager.update_achievement(
                        str(internal_id), data_input, immediate_persist=True
                    )

                    new_name = user_input[const.CFOF_ACHIEVEMENTS_INPUT_NAME].strip()
                    const.LOGGER.debug(
                        "Edited Achievement '%s' with ID: %s",
                        new_name,
                        internal_id,
                    )
                    self._mark_reload_needed()
                    return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        assignees_dict = {
            assignee_data[const.DATA_USER_NAME]: assignee_id
            for assignee_id, assignee_data in coordinator.assignees_data.items()
        }
        chores_dict = coordinator.chores_data

        # Create reverse mapping from internal_id to name
        id_to_name = {
            assignee_id: assignee_data[const.DATA_USER_NAME]
            for assignee_id, assignee_data in coordinator.assignees_data.items()
        }

        # Convert assigned user IDs to names for display
        assigned_user_ids = achievement_data.get(
            const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, []
        )
        valid_assignee_names = set(assignees_dict.keys())
        valid_chore_ids = set(chores_dict.keys())
        assigned_user_names = [
            assignee_name
            for assignee_id in assigned_user_ids
            if isinstance(assignee_id, str)
            if (assignee_name := id_to_name.get(assignee_id))
            if assignee_name in valid_assignee_names
        ]

        # Build suggested values for form (CFOF keys → existing DATA values)
        suggested_values = {
            const.CFOF_ACHIEVEMENTS_INPUT_NAME: achievement_data.get(
                const.DATA_ACHIEVEMENT_NAME
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION: achievement_data.get(
                const.DATA_ACHIEVEMENT_DESCRIPTION
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_LABELS: achievement_data.get(
                const.DATA_ACHIEVEMENT_LABELS, []
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_ICON: achievement_data.get(
                const.DATA_ACHIEVEMENT_ICON
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS: assigned_user_names,
            const.CFOF_ACHIEVEMENTS_INPUT_TYPE: achievement_data.get(
                const.DATA_ACHIEVEMENT_TYPE, const.ACHIEVEMENT_TYPE_STREAK
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID: achievement_data.get(
                const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_CRITERIA: achievement_data.get(
                const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE: achievement_data.get(
                const.DATA_ACHIEVEMENT_TARGET_VALUE, const.DEFAULT_ACHIEVEMENT_TARGET
            ),
            const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS: achievement_data.get(
                const.DATA_ACHIEVEMENT_REWARD_POINTS,
                const.DEFAULT_ACHIEVEMENT_REWARD_POINTS,
            ),
        }

        # On validation error, merge user's attempted input (preserves user changes)
        if user_input:
            suggested_values.update(user_input)

        suggested_values[const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS] = (
            _sanitize_select_values(
                suggested_values.get(const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS),
                valid_assignee_names,
            )
        )

        selected_chore_id = suggested_values.get(
            const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID,
            const.SENTINEL_EMPTY,
        )
        if (
            selected_chore_id != const.SENTINEL_EMPTY
            and selected_chore_id not in valid_chore_ids
        ):
            suggested_values[const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID] = (
                const.SENTINEL_EMPTY
            )

        # Build schema without defaults (suggestions provide the values)
        schema = fh.build_achievement_schema(
            assignees_dict=assignees_dict,
            chores_dict=chores_dict,
        )
        # Apply suggested values to schema
        schema = self.add_suggested_values_to_schema(schema, suggested_values)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_ACHIEVEMENT,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_ACHIEVEMENTS_OVERVIEW
            },
        )

    async def async_step_delete_achievement(self, user_input=None):
        """Delete an achievement."""
        coordinator = self._get_coordinator()
        achievements_dict = coordinator.achievements_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in achievements_dict:
            const.LOGGER.error(
                "Delete Achievement - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT)

        achievement_name = achievements_dict[internal_id][const.DATA_ACHIEVEMENT_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.gamification_manager.delete_achievement(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Achievement '%s' with ID: %s",
                achievement_name,
                internal_id,
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_ACHIEVEMENT,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_ACHIEVEMENT_NAME: achievement_name
            },
        )

    # ----------------------------------------------------------------------------------
    # CHALLENGES MANAGEMENT
    # ----------------------------------------------------------------------------------

    async def async_step_add_challenge(self, user_input=None):
        """Add a new challenge."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        chores_dict = coordinator.chores_data

        if user_input is not None:
            # Layer 2: UI validation (uniqueness + type-specific checks)
            errors = fh.validate_challenges_inputs(
                user_input,
                existing_challenges=coordinator.challenges_data,
                current_challenge_id=None,  # New challenge
            )

            if not errors:
                try:
                    # Build assignees name to ID mapping for options flow
                    assignees_name_to_id = {
                        assignee[const.DATA_USER_NAME]: assignee[
                            const.DATA_USER_INTERNAL_ID
                        ]
                        for assignee in coordinator.data.get(
                            const.DATA_USERS, {}
                        ).values()
                    }

                    # Layer 3: Convert CFOF_* to DATA_* keys
                    data_input = db.map_cfof_to_challenge_data(user_input)

                    # Convert assigned assignees from names to IDs (options flow uses names)
                    assigned_assignees_names = data_input.get(
                        const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
                    )
                    if not isinstance(assigned_assignees_names, list):
                        assigned_assignees_names = (
                            [assigned_assignees_names]
                            if assigned_assignees_names
                            else []
                        )
                    data_input[const.DATA_CHALLENGE_ASSIGNED_USER_IDS] = [
                        assignees_name_to_id.get(name, name)
                        for name in assigned_assignees_names
                    ]

                    # Parse dates using dt_parse (same pattern as chores)
                    # Dates from DateTimeSelector are local time - convert to UTC
                    raw_start = data_input.get(const.DATA_CHALLENGE_START_DATE)
                    raw_end = data_input.get(const.DATA_CHALLENGE_END_DATE)

                    start_dt = None
                    end_dt = None
                    if raw_start:
                        start_dt = dt_parse(
                            raw_start,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_DATETIME_UTC,
                        )
                    if raw_end:
                        end_dt = dt_parse(
                            raw_end,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_DATETIME_UTC,
                        )

                    # Validate dates are in the future (compare UTC to UTC)
                    now_utc = dt_util.utcnow()
                    if (
                        start_dt
                        and isinstance(start_dt, datetime)
                        and start_dt < now_utc
                    ):
                        errors = {
                            const.CFOP_ERROR_START_DATE: const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                        }
                    elif end_dt and isinstance(end_dt, datetime) and end_dt <= now_utc:
                        errors = {
                            const.CFOP_ERROR_END_DATE: const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                        }

                    # Store dates as ISO UTC strings
                    if start_dt and isinstance(start_dt, datetime):
                        data_input[const.DATA_CHALLENGE_START_DATE] = (
                            start_dt.isoformat()
                        )
                    if end_dt and isinstance(end_dt, datetime):
                        data_input[const.DATA_CHALLENGE_END_DATE] = end_dt.isoformat()

                    if not errors:
                        # Use GamificationManager for challenge creation
                        internal_id = coordinator.gamification_manager.create_challenge(
                            data_input, immediate_persist=True
                        )

                        challenge_name = user_input[
                            const.CFOF_CHALLENGES_INPUT_NAME
                        ].strip()
                        const.LOGGER.debug(
                            "Added Challenge '%s' with ID: %s",
                            challenge_name,
                            internal_id,
                        )
                        self._mark_reload_needed()
                        return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        # Build schema - pass date defaults for DateTimeSelector to work correctly
        assignees_dict = {
            data[const.DATA_USER_NAME]: eid
            for eid, data in coordinator.assignees_data.items()
        }

        # On error, pass user's date inputs as schema defaults (DateTimeSelector pattern)
        date_defaults = {}
        if errors and user_input:
            date_defaults = {
                const.CFOF_CHALLENGES_INPUT_START_DATE: user_input.get(
                    const.CFOF_CHALLENGES_INPUT_START_DATE
                ),
                const.CFOF_CHALLENGES_INPUT_END_DATE: user_input.get(
                    const.CFOF_CHALLENGES_INPUT_END_DATE
                ),
            }

        challenge_schema = fh.build_challenge_schema(
            assignees_dict=assignees_dict,
            chores_dict=chores_dict,
            default=date_defaults,
        )

        # On error, use suggested values to preserve other user input
        if errors and user_input:
            challenge_schema = self.add_suggested_values_to_schema(
                challenge_schema, user_input
            )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_ADD_CHALLENGE,
            data_schema=challenge_schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHALLENGES_OVERVIEW
            },
        )

    async def async_step_edit_challenge(self, user_input=None):
        """Edit an existing challenge."""
        coordinator = self._get_coordinator()
        errors: dict[str, str] = {}
        challenges_dict = coordinator.challenges_data
        internal_id = cast("str | None", self.context.get(const.DATA_INTERNAL_ID))

        if not internal_id or internal_id not in challenges_dict:
            const.LOGGER.error("Edit Challenge - Invalid Internal ID '%s'", internal_id)
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHALLENGE)

        challenge_data = challenges_dict[internal_id]

        if user_input is not None:
            # Build assignees name to ID mapping for conversion
            assignees_name_to_id = {
                assignee[const.DATA_USER_NAME]: assignee[const.DATA_USER_INTERNAL_ID]
                for assignee in coordinator.data.get(const.DATA_USERS, {}).values()
            }

            # Layer 2: UI validation (uniqueness + type-specific checks)
            errors = fh.validate_challenges_inputs(
                user_input,
                existing_challenges=coordinator.challenges_data,
                current_challenge_id=internal_id,  # Editing existing challenge
            )

            if not errors:
                try:
                    # Layer 3: Convert CFOF_* to DATA_* keys
                    data_input = db.map_cfof_to_challenge_data(user_input)

                    # Convert assigned assignees from names to IDs (form uses names)
                    assigned_assignees_names = data_input.get(
                        const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
                    )
                    if not isinstance(assigned_assignees_names, list):
                        assigned_assignees_names = (
                            [assigned_assignees_names]
                            if assigned_assignees_names
                            else []
                        )
                    data_input[const.DATA_CHALLENGE_ASSIGNED_USER_IDS] = [
                        assignees_name_to_id.get(name, name)
                        for name in assigned_assignees_names
                    ]

                    # Parse dates using dt_parse (same pattern as chores)
                    # Dates from DateTimeSelector are local time - convert to UTC
                    raw_start = data_input.get(const.DATA_CHALLENGE_START_DATE)
                    raw_end = data_input.get(const.DATA_CHALLENGE_END_DATE)

                    start_dt = None
                    end_dt = None
                    if raw_start:
                        start_dt = dt_parse(
                            raw_start,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_DATETIME_UTC,
                        )
                    if raw_end:
                        end_dt = dt_parse(
                            raw_end,
                            default_tzinfo=const.DEFAULT_TIME_ZONE,
                            return_type=const.HELPER_RETURN_DATETIME_UTC,
                        )

                    # Validate dates are in the future (compare UTC to UTC)
                    now_utc = dt_util.utcnow()
                    if (
                        start_dt
                        and isinstance(start_dt, datetime)
                        and start_dt < now_utc
                    ):
                        errors = {
                            const.CFOP_ERROR_START_DATE: const.TRANS_KEY_CFOF_START_DATE_IN_PAST
                        }
                    elif end_dt and isinstance(end_dt, datetime) and end_dt <= now_utc:
                        errors = {
                            const.CFOP_ERROR_END_DATE: const.TRANS_KEY_CFOF_END_DATE_IN_PAST
                        }

                    # Store dates as ISO UTC strings
                    if start_dt and isinstance(start_dt, datetime):
                        data_input[const.DATA_CHALLENGE_START_DATE] = (
                            start_dt.isoformat()
                        )
                    if end_dt and isinstance(end_dt, datetime):
                        data_input[const.DATA_CHALLENGE_END_DATE] = end_dt.isoformat()

                    if not errors:
                        # Use GamificationManager for challenge update
                        coordinator.gamification_manager.update_challenge(
                            str(internal_id), data_input, immediate_persist=True
                        )

                        new_name = user_input[const.CFOF_CHALLENGES_INPUT_NAME].strip()
                        const.LOGGER.debug(
                            "Edited Challenge '%s' with ID: %s",
                            new_name,
                            internal_id,
                        )
                        self._mark_reload_needed()
                        return await self.async_step_init()

                except EntityValidationError as err:
                    errors[err.field] = err.translation_key

        # Create reverse mapping from internal_id to name (for display)
        id_to_name = {
            assignee_id: data[const.DATA_USER_NAME]
            for assignee_id, data in coordinator.assignees_data.items()
        }

        # Convert assigned user IDs to names for display (schema uses names)
        assigned_user_ids = challenge_data.get(
            const.DATA_CHALLENGE_ASSIGNED_USER_IDS, []
        )
        assigned_user_names = [
            assignee_name
            for assignee_id in assigned_user_ids
            if isinstance(assignee_id, str)
            if (assignee_name := id_to_name.get(assignee_id))
            if isinstance(assignee_name, str)
        ]

        # Convert stored start/end dates to selector format for display
        # Format must be "%Y-%m-%d %H:%M:%S" (space separator, NOT ISO with T)
        start_date_display = None
        end_date_display = None
        if challenge_data.get(const.DATA_CHALLENGE_START_DATE):
            start_date_display = dt_parse(
                challenge_data[const.DATA_CHALLENGE_START_DATE],
                default_tzinfo=const.DEFAULT_TIME_ZONE,
                return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
            )
        if challenge_data.get(const.DATA_CHALLENGE_END_DATE):
            end_date_display = dt_parse(
                challenge_data[const.DATA_CHALLENGE_END_DATE],
                default_tzinfo=const.DEFAULT_TIME_ZONE,
                return_type=const.HELPER_RETURN_SELECTOR_DATETIME,
            )

        # Build schema with date defaults passed directly (like chores pattern)
        # This ensures DateTimeSelector works correctly when user only changes time
        assignees_dict = {
            data[const.DATA_USER_NAME]: assignee_id
            for assignee_id, data in coordinator.assignees_data.items()
        }
        chores_dict = coordinator.chores_data
        valid_assignee_names = set(assignees_dict.keys())
        valid_chore_ids = set(chores_dict.keys())
        challenge_schema = fh.build_challenge_schema(
            assignees_dict=assignees_dict,
            chores_dict=chores_dict,
            default={
                const.CFOF_CHALLENGES_INPUT_START_DATE: start_date_display,
                const.CFOF_CHALLENGES_INPUT_END_DATE: end_date_display,
            },
        )

        # Build suggested values from existing data (using CFOF keys for form)
        # Note: this form field stores selected names in the UI schema.
        suggested_values: dict[str, Any] = {
            const.CFOF_CHALLENGES_INPUT_NAME: challenge_data.get(
                const.DATA_CHALLENGE_NAME, ""
            ),
            const.CFOF_CHALLENGES_INPUT_DESCRIPTION: challenge_data.get(
                const.DATA_CHALLENGE_DESCRIPTION, ""
            ),
            const.CFOF_CHALLENGES_INPUT_LABELS: challenge_data.get(
                const.DATA_CHALLENGE_LABELS, []
            ),
            const.CFOF_CHALLENGES_INPUT_ICON: challenge_data.get(
                const.DATA_CHALLENGE_ICON
            ),
            const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS: assigned_user_names,
            const.CFOF_CHALLENGES_INPUT_TYPE: challenge_data.get(
                const.DATA_CHALLENGE_TYPE, const.CHALLENGE_TYPE_DAILY_MIN
            ),
            const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID: challenge_data.get(
                const.DATA_CHALLENGE_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
            ),
            const.CFOF_CHALLENGES_INPUT_CRITERIA: challenge_data.get(
                const.DATA_CHALLENGE_CRITERIA, ""
            ),
            const.CFOF_CHALLENGES_INPUT_TARGET_VALUE: challenge_data.get(
                const.DATA_CHALLENGE_TARGET_VALUE, const.DEFAULT_CHALLENGE_TARGET
            ),
            const.CFOF_CHALLENGES_INPUT_REWARD_POINTS: challenge_data.get(
                const.DATA_CHALLENGE_REWARD_POINTS,
                const.DEFAULT_CHALLENGE_REWARD_POINTS,
            ),
            const.CFOF_CHALLENGES_INPUT_START_DATE: start_date_display,
            const.CFOF_CHALLENGES_INPUT_END_DATE: end_date_display,
        }

        # On error, merge user_input to preserve their changes
        if errors and user_input:
            suggested_values.update(user_input)

        suggested_values[const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS] = (
            _sanitize_select_values(
                suggested_values.get(const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS),
                valid_assignee_names,
            )
        )

        selected_chore_id = suggested_values.get(
            const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID,
            const.SENTINEL_EMPTY,
        )
        if (
            selected_chore_id != const.SENTINEL_EMPTY
            and selected_chore_id not in valid_chore_ids
        ):
            suggested_values[const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID] = (
                const.SENTINEL_EMPTY
            )

        challenge_schema = self.add_suggested_values_to_schema(
            challenge_schema, suggested_values
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_EDIT_CHALLENGE,
            data_schema=challenge_schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_CHALLENGES_OVERVIEW
            },
        )

    async def async_step_delete_challenge(self, user_input=None):
        """Delete a challenge."""
        coordinator = self._get_coordinator()
        challenges_dict = coordinator.challenges_data
        internal_id = self.context.get(const.DATA_INTERNAL_ID)

        if not internal_id or internal_id not in challenges_dict:
            const.LOGGER.error(
                "Delete Challenge - Invalid Internal ID '%s'", internal_id
            )
            return self.async_abort(reason=const.TRANS_KEY_CFOF_INVALID_CHALLENGE)

        challenge_name = challenges_dict[internal_id][const.DATA_CHALLENGE_NAME]

        if user_input is not None:
            # Use Manager-owned CRUD method
            coordinator.gamification_manager.delete_challenge(
                str(internal_id), immediate_persist=True
            )

            const.LOGGER.debug(
                "Deleted Challenge '%s' with ID: %s", challenge_name, internal_id
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_CHALLENGE,
            data_schema=vol.Schema({}),
            description_placeholders={
                const.OPTIONS_FLOW_PLACEHOLDER_CHALLENGE_NAME: challenge_name
            },
        )

    # ----------------------------------------------------------------------------------
    # DASHBOARD GENERATOR
    # ----------------------------------------------------------------------------------

    async def async_step_dashboard_generator(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the dashboard generator action selection.

        First step: Select dashboard CRUD action.
        """
        from .helpers import dashboard_helpers as dh

        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if user wants to verify card installation
            check_cards = user_input.get(const.CFOF_DASHBOARD_INPUT_CHECK_CARDS, False)

            if check_cards:
                # Run detection and show results
                card_status = await dh.check_custom_cards_installed(self.hass)

                # Build status message
                status_lines = ["Custom Card Installation Status:"]
                all_installed = True
                for card_name, installed in card_status.items():
                    status_icon = "✅" if installed else "❌"
                    card_display = {
                        "mushroom": "Mushroom Cards",
                        "auto_entities": "Auto-Entities",
                        "mini_graph": "Mini Graph Card",
                        "button_card": "Button Card",
                    }.get(card_name, card_name)

                    status_lines.append(f"{status_icon} {card_display}")
                    if not installed:
                        all_installed = False

                # Only show error and re-display form if cards are missing
                if not all_installed:
                    status_lines.append("")
                    status_lines.append(
                        "⚠️ Missing cards detected. Install via HACS → Frontend."
                    )

                    # Show results as an error and block progression
                    errors["base"] = "\n".join(status_lines)

                    # Re-show form with status - keep checkbox checked
                    schema = dh.build_dashboard_action_schema(check_cards_default=True)
                    return self.async_show_form(
                        step_id=const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR,
                        data_schema=schema,
                        errors=errors,
                    )

                # All cards installed - proceed normally (fall through to action handling)

            # Proceed with selected action
            action = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_ACTION, const.DASHBOARD_ACTION_CREATE
                )
            )

            if action == const.DASHBOARD_ACTION_DELETE:
                return await self.async_step_dashboard_delete()
            if action == const.DASHBOARD_ACTION_UPDATE:
                return await self.async_step_dashboard_update_select()
            if action == const.DASHBOARD_ACTION_EXIT:
                return await self.async_step_init()
            # Default to create flow
            return await self.async_step_dashboard_create()

        # Show action selection
        schema = dh.build_dashboard_action_schema()
        self._dashboard_status_message = ""

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_DASHBOARD_GENERATION,
                const.PLACEHOLDER_DASHBOARD_CARD_MUSHROOM_URL: const.DOC_URL_CARD_MUSHROOM,
                const.PLACEHOLDER_DASHBOARD_CARD_AUTO_ENTITIES_URL: const.DOC_URL_CARD_AUTO_ENTITIES,
                const.PLACEHOLDER_DASHBOARD_CARD_MINI_GRAPH_URL: const.DOC_URL_CARD_MINI_GRAPH,
                const.PLACEHOLDER_DASHBOARD_CARD_BUTTON_URL: const.DOC_URL_CARD_BUTTON,
            },
        )

    async def async_step_dashboard_create(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the dashboard creation form.

        Step 1 create path: capture dashboard name only, then route to Step 2.
        """
        from .helpers import dashboard_builder as builder, dashboard_helpers as dh

        errors: dict[str, str] = {}

        if user_input is not None:
            dashboard_name = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_NAME, const.DASHBOARD_DEFAULT_NAME
                )
            ).strip()

            # Validate dashboard name
            if not dashboard_name:
                errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_DASHBOARD_NO_NAME
            else:
                url_path = builder.get_multi_view_url_path(dashboard_name)
                if await builder.async_check_dashboard_exists(self.hass, url_path):
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DASHBOARD_EXISTS
                    )
                else:
                    self._dashboard_name = dashboard_name
                    self._dashboard_update_url_path = None
                    self._dashboard_flow_mode = const.DASHBOARD_ACTION_CREATE
                    return await self.async_step_dashboard_configure()

        schema = dh.build_dashboard_create_name_schema()

        return self.async_show_form(
            step_id="dashboard_create",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_DASHBOARD_GENERATION
            },
        )

    async def async_step_dashboard_update_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an existing dashboard before applying targeted updates."""
        from .helpers import dashboard_builder as builder, dashboard_helpers as dh

        errors: dict[str, str] = {}

        if user_input is not None:
            selected_url_path = user_input.get(
                const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION
            )
            if isinstance(selected_url_path, str) and selected_url_path:
                self._dashboard_update_url_path = selected_url_path
                self._dashboard_flow_mode = const.DASHBOARD_ACTION_UPDATE
                return await self.async_step_dashboard_configure()

            errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_DASHBOARD_NO_DASHBOARDS

        dedupe_removed = await builder.async_dedupe_choreops_dashboards(self.hass)
        self._dashboard_dedupe_removed = dedupe_removed

        schema = dh.build_dashboard_update_selection_schema(self.hass)
        if schema is None:
            return self.async_abort(reason="no_dashboards_to_delete")

        return self.async_show_form(
            step_id="dashboard_update_select",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_dashboard_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Unified Step 2 dashboard configuration for create/update flows."""
        from .helpers import dashboard_builder as builder, dashboard_helpers as dh

        errors: dict[str, str] = {}
        coordinator = self._get_coordinator()
        is_update_flow = self._dashboard_flow_mode == const.DASHBOARD_ACTION_UPDATE

        if is_update_flow and not self._dashboard_update_url_path:
            return await self.async_step_dashboard_update_select()

        available_release_tags: list[str] = []
        if is_update_flow:
            try:
                available_release_tags = (
                    await builder.discover_compatible_dashboard_release_tags(self.hass)
                )
            except (TimeoutError, HomeAssistantError, ValueError) as err:
                const.LOGGER.debug(
                    "Release tags unavailable while building dashboard update schema: %s",
                    err,
                )

        if user_input is not None:
            user_input = dh.normalize_dashboard_configure_input(user_input)
            self._dashboard_dedupe_removed = {}
            selected_assignees_input = user_input.get(
                const.CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION,
                [],
            )
            selected_assignees: list[str] = (
                list(selected_assignees_input) if selected_assignees_input else []
            )

            template_profile = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE,
                    self._dashboard_template_profile,
                )
            )
            admin_mode = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_ADMIN_MODE,
                    self._dashboard_admin_mode,
                )
            )
            admin_mode = self._normalize_dashboard_admin_mode(admin_mode)
            has_admin_template_global_input = (
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL in user_input
            )
            has_admin_template_per_assignee_input = (
                const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_ASSIGNEE in user_input
            )
            admin_template_global = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL,
                    self._dashboard_admin_template_global,
                )
            ).strip()
            admin_template_per_assignee = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_ASSIGNEE,
                    self._dashboard_admin_template_per_assignee,
                )
            ).strip()
            admin_view_visibility = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY,
                    self._dashboard_admin_view_visibility,
                )
            )
            show_in_sidebar = bool(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR,
                    self._dashboard_show_in_sidebar,
                )
            )
            require_admin = bool(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN,
                    self._dashboard_require_admin,
                )
            )
            icon = str(
                user_input.get(const.CFOF_DASHBOARD_INPUT_ICON, self._dashboard_icon)
            ).strip()

            release_selection = str(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_RELEASE_SELECTION,
                    self._dashboard_release_selection,
                )
            ).strip()
            include_prereleases = bool(
                user_input.get(
                    const.CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES,
                    self._dashboard_include_prereleases,
                )
            )

            # Update flow only: when admin layout changes, rerender with newly
            # relevant template selector fields before full validation.
            if is_update_flow:
                needs_global_template = admin_mode in (
                    const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.DASHBOARD_ADMIN_MODE_BOTH,
                )
                needs_per_assignee_template = admin_mode in (
                    const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                    const.DASHBOARD_ADMIN_MODE_BOTH,
                )
                missing_global_template_selection = (
                    needs_global_template
                    and not has_admin_template_global_input
                    and not admin_template_global
                )
                missing_per_assignee_template_selection = (
                    needs_per_assignee_template
                    and not has_admin_template_per_assignee_input
                    and not admin_template_per_assignee
                )
                if (
                    missing_global_template_selection
                    or missing_per_assignee_template_selection
                ):
                    self._dashboard_selected_assignees = selected_assignees
                    self._dashboard_template_profile = template_profile
                    self._dashboard_admin_mode = admin_mode
                    self._dashboard_admin_template_global = admin_template_global
                    self._dashboard_admin_template_per_assignee = (
                        admin_template_per_assignee
                    )
                    self._dashboard_admin_view_visibility = admin_view_visibility
                    self._dashboard_show_in_sidebar = show_in_sidebar
                    self._dashboard_require_admin = require_admin
                    self._dashboard_icon = icon or "mdi:clipboard-list"
                    self._dashboard_release_selection = release_selection
                    self._dashboard_include_prereleases = include_prereleases
                    return await self.async_step_dashboard_configure()

            if not selected_assignees and admin_mode == const.DASHBOARD_ADMIN_MODE_NONE:
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_DASHBOARD_NO_ASSIGNEES_WITHOUT_ADMIN
                )
            elif (
                admin_mode
                in (
                    const.DASHBOARD_ADMIN_MODE_GLOBAL,
                    const.DASHBOARD_ADMIN_MODE_BOTH,
                )
                and not admin_template_global
            ):
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_GLOBAL_TEMPLATE_REQUIRED
                )
            elif (
                admin_mode
                in (
                    const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                    const.DASHBOARD_ADMIN_MODE_BOTH,
                )
                and not admin_template_per_assignee
            ):
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_PER_ASSIGNEE_TEMPLATE_REQUIRED
                )
            elif (
                admin_mode
                in (
                    const.DASHBOARD_ADMIN_MODE_PER_ASSIGNEE,
                    const.DASHBOARD_ADMIN_MODE_BOTH,
                )
                and not selected_assignees
            ):
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_DASHBOARD_ADMIN_PER_ASSIGNEE_NEEDS_ASSIGNEES
                )
            elif (
                is_update_flow
                and release_selection != const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE
                and available_release_tags
                and release_selection not in available_release_tags
            ):
                errors[const.CFOP_ERROR_BASE] = (
                    const.TRANS_KEY_CFOF_DASHBOARD_RELEASE_INCOMPATIBLE
                )

            if not errors:
                include_admin = admin_mode != const.DASHBOARD_ADMIN_MODE_NONE
                pinned_release_tag = (
                    release_selection
                    if is_update_flow
                    and release_selection
                    != const.DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE
                    else None
                )

                self._dashboard_selected_assignees = selected_assignees
                self._dashboard_template_profile = template_profile
                self._dashboard_admin_mode = admin_mode
                self._dashboard_admin_template_global = admin_template_global
                self._dashboard_admin_template_per_assignee = (
                    admin_template_per_assignee
                )
                self._dashboard_show_in_sidebar = show_in_sidebar
                self._dashboard_require_admin = require_admin
                self._dashboard_icon = icon or "mdi:clipboard-list"
                self._dashboard_admin_view_visibility = admin_view_visibility
                self._dashboard_release_selection = release_selection
                self._dashboard_include_prereleases = include_prereleases
                admin_visible_user_ids = (
                    self._get_user_ha_user_ids()
                    if admin_view_visibility
                    == const.DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS
                    else None
                )

                try:
                    if is_update_flow:
                        url_path = self._dashboard_update_url_path
                        if url_path is None:
                            return await self.async_step_dashboard_update_select()

                        view_count = await builder.update_choreops_dashboard_views(
                            self.hass,
                            url_path=url_path,
                            assignee_names=selected_assignees,
                            template_profile=template_profile,
                            include_admin=include_admin,
                            admin_mode=admin_mode,
                            admin_view_visibility=admin_view_visibility,
                            admin_visible_user_ids=admin_visible_user_ids,
                            icon=self._dashboard_icon,
                            show_in_sidebar=show_in_sidebar,
                            require_admin=require_admin,
                            pinned_release_tag=pinned_release_tag,
                            include_prereleases=include_prereleases,
                        )
                        self._dashboard_status_message = f"Updated {url_path} (views={view_count}, release_selection={release_selection})"
                    else:
                        dedupe_removed = await builder.async_dedupe_choreops_dashboards(
                            self.hass,
                            url_path=builder.get_multi_view_url_path(
                                self._dashboard_name
                            ),
                        )
                        self._dashboard_dedupe_removed = dedupe_removed

                        url_path = await builder.create_choreops_dashboard(
                            self.hass,
                            dashboard_name=self._dashboard_name,
                            assignee_names=selected_assignees,
                            style=template_profile,
                            assignee_template_profiles=dict.fromkeys(
                                selected_assignees, template_profile
                            )
                            if selected_assignees
                            else None,
                            include_admin=include_admin,
                            admin_mode=admin_mode,
                            force_rebuild=False,
                            show_in_sidebar=show_in_sidebar,
                            require_admin=require_admin,
                            icon=self._dashboard_icon,
                            admin_view_visibility=admin_view_visibility,
                            admin_visible_user_ids=admin_visible_user_ids,
                        )
                        self._dashboard_status_message = f"Created {url_path} (assignees={len(selected_assignees)}, admin_mode={admin_mode})"

                    return await self.async_step_dashboard_generator()
                except builder.DashboardTemplateError:
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_ERROR
                    )
                except builder.DashboardRenderError:
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DASHBOARD_RENDER_ERROR
                    )
                except builder.DashboardSaveError as err:
                    const.LOGGER.error("Dashboard save failed: %s", err)
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DASHBOARD_SAVE_ERROR
                    )
                except Exception as err:
                    const.LOGGER.error(
                        "Unexpected dashboard configure failure: %s",
                        err,
                        exc_info=True,
                    )
                    errors[const.CFOP_ERROR_BASE] = (
                        const.TRANS_KEY_CFOF_DASHBOARD_SAVE_ERROR
                    )

        schema = dh.build_dashboard_configure_schema(
            coordinator,
            include_release_controls=is_update_flow,
            release_tags=available_release_tags,
            selected_assignees_default=self._dashboard_selected_assignees,
            template_profile_default=self._dashboard_template_profile,
            admin_mode_default=self._dashboard_admin_mode,
            admin_template_global_default=self._dashboard_admin_template_global,
            admin_template_per_assignee_default=self._dashboard_admin_template_per_assignee,
            admin_view_visibility_default=self._dashboard_admin_view_visibility,
            show_in_sidebar_default=self._dashboard_show_in_sidebar,
            require_admin_default=self._dashboard_require_admin,
            icon_default=self._dashboard_icon,
            include_prereleases_default=self._dashboard_include_prereleases,
            release_selection_default=self._dashboard_release_selection,
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE,
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "mode": self._dashboard_flow_mode,
                "dashboard": self._dashboard_update_url_path or self._dashboard_name,
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_DASHBOARD_GENERATION,
            },
        )

    async def async_step_dashboard_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle dashboard deletion selection.

        Shows list of existing ChoreOps dashboards for deletion.
        """
        from .helpers import dashboard_builder as builder, dashboard_helpers as dh

        errors: dict[str, str] = {}

        if user_input is not None:
            selected_dashboard = user_input.get(
                const.CFOF_DASHBOARD_INPUT_UPDATE_SELECTION
            )
            if isinstance(selected_dashboard, str) and selected_dashboard:
                self._dashboard_delete_selection = [selected_dashboard]
                return await self.async_step_dashboard_delete_confirm()
            errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_DASHBOARD_NO_DASHBOARDS

        # Cleanup duplicate ChoreOps dashboard entries before presenting delete list
        dedupe_removed = await builder.async_dedupe_choreops_dashboards(self.hass)
        self._dashboard_dedupe_removed = dedupe_removed

        # Reuse update selector to enforce single-select deletion contract
        schema = dh.build_dashboard_update_selection_schema(self.hass)

        if schema is None:
            # No dashboards to delete - show message and go back
            return self.async_abort(reason="no_dashboards_to_delete")

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DASHBOARD_DELETE,
            data_schema=schema,
            errors=errors,
        )

    async def async_step_dashboard_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm and execute dashboard deletion."""
        from .helpers import dashboard_builder as builder

        if user_input is not None:
            url_path = self._dashboard_delete_selection[0]
            try:
                await builder.delete_choreops_dashboard(self.hass, url_path)
                const.LOGGER.info("Deleted dashboard: %s", url_path)
                self._dashboard_status_message = f"Deleted {url_path}"
            except Exception as err:
                const.LOGGER.error("Failed to delete dashboard %s: %s", url_path, err)
                self._dashboard_status_message = f"Failed to delete {url_path}: {err}"

            return await self.async_step_dashboard_generator()

        # Show confirmation
        dashboards_to_delete = ", ".join(self._dashboard_delete_selection)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DASHBOARD_DELETE_CONFIRM,
            data_schema=vol.Schema({}),
            description_placeholders={"dashboards": dashboards_to_delete},
        )

    # ----------------------------------------------------------------------------------
    # GENERAL OPTIONS
    # ----------------------------------------------------------------------------------

    async def async_step_manage_general_options(self, user_input=None):
        """Manage general options: points adjust values, update interval, retention, and backup settings."""
        # Check if this is a backup management action
        if user_input is not None and const.CFOF_BACKUP_ACTION_SELECTION in user_input:
            action = user_input[const.CFOF_BACKUP_ACTION_SELECTION]
            # Skip empty/default selection
            if action and action.strip():
                if action == "create_backup":
                    return await self.async_step_create_manual_backup()
                if action == "delete_backup":
                    return await self.async_step_select_backup_to_delete()
                if action == "restore_backup":
                    return await self.async_step_restore_from_options()

        if user_input is not None:
            # Get the raw text from the multiline text area.
            points_str = user_input.get(
                const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES, const.SENTINEL_EMPTY
            ).strip()
            if points_str:
                # Parse the values by splitting on separator.
                parsed_values = parse_points_adjust_values(points_str)
                # Always store as a list of floats.
                self._entry_options[const.CONF_POINTS_ADJUST_VALUES] = parsed_values
            else:
                # Remove the key if the field is left empty.
                self._entry_options.pop(const.CONF_POINTS_ADJUST_VALUES, None)
            # Update the update interval.
            self._entry_options[const.CONF_UPDATE_INTERVAL] = user_input.get(
                const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL
            )
            # update calendar show period
            self._entry_options[const.CONF_CALENDAR_SHOW_PERIOD] = user_input.get(
                const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD
            )
            # Parse consolidated retention periods
            retention_str = user_input.get(
                const.CFOF_SYSTEM_INPUT_RETENTION_PERIODS, ""
            ).strip()
            if retention_str:
                try:
                    daily, weekly, monthly, yearly = fh.parse_retention_periods(
                        retention_str
                    )
                    self._entry_options[const.CONF_RETENTION_DAILY] = daily
                    self._entry_options[const.CONF_RETENTION_WEEKLY] = weekly
                    self._entry_options[const.CONF_RETENTION_MONTHLY] = monthly
                    self._entry_options[const.CONF_RETENTION_YEARLY] = yearly
                except ValueError as err:
                    const.LOGGER.error("Failed to parse retention periods: %s", err)
                    # Use defaults if parsing fails
                    self._entry_options[const.CONF_RETENTION_DAILY] = (
                        const.DEFAULT_RETENTION_DAILY
                    )
                    self._entry_options[const.CONF_RETENTION_WEEKLY] = (
                        const.DEFAULT_RETENTION_WEEKLY
                    )
                    self._entry_options[const.CONF_RETENTION_MONTHLY] = (
                        const.DEFAULT_RETENTION_MONTHLY
                    )
                    self._entry_options[const.CONF_RETENTION_YEARLY] = (
                        const.DEFAULT_RETENTION_YEARLY
                    )
            # Update extra entities toggle (config key: show_legacy_entities)
            # Track old value to cleanup entities if disabled
            old_extra_enabled = self._entry_options.get(
                const.CONF_SHOW_LEGACY_ENTITIES, const.DEFAULT_SHOW_LEGACY_ENTITIES
            )
            new_extra_enabled = user_input.get(
                const.CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES,
                const.DEFAULT_SHOW_LEGACY_ENTITIES,
            )
            self._entry_options[const.CONF_SHOW_LEGACY_ENTITIES] = new_extra_enabled
            self._entry_options[const.CONF_KIOSK_MODE] = user_input.get(
                const.CFOF_SYSTEM_INPUT_KIOSK_MODE,
                const.DEFAULT_KIOSK_MODE,
            )

            # Update backup retention (count-based)
            self._entry_options[const.CONF_BACKUPS_MAX_RETAINED] = user_input.get(
                const.CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED,
                const.DEFAULT_BACKUPS_MAX_RETAINED,
            )
            const.LOGGER.debug(
                "General Options Updated: Points Adjust Values=%s, "
                "Update Interval=%s, Calendar Period to Show=%s, "
                "Retention Periods=%s, "
                "Show Legacy Entities=%s, Kiosk Mode=%s, Backup Retention=%s",
                self._entry_options.get(const.CONF_POINTS_ADJUST_VALUES),
                self._entry_options.get(const.CONF_UPDATE_INTERVAL),
                self._entry_options.get(const.CONF_CALENDAR_SHOW_PERIOD),
                retention_str,
                self._entry_options.get(const.CONF_SHOW_LEGACY_ENTITIES),
                self._entry_options.get(const.CONF_KIOSK_MODE),
                self._entry_options.get(const.CONF_BACKUPS_MAX_RETAINED),
            )

            # Cleanup EXTRA entities if flag was disabled (True → False)
            # Must happen before reload to remove entities before new ones are created
            if old_extra_enabled and not new_extra_enabled:
                coordinator = self._get_coordinator()
                removed = await coordinator.system_manager.remove_conditional_entities()
                if removed > 0:
                    const.LOGGER.info(
                        "Extra entities disabled: cleaned up %d entities", removed
                    )

            await self._update_system_settings_and_reload()
            # After saving settings, return to main menu
            return await self.async_step_init()

        general_schema = fh.build_general_options_schema(self._entry_options)
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_MANAGE_GENERAL_OPTIONS,
            data_schema=general_schema,
            description_placeholders={
                const.PLACEHOLDER_DOCUMENTATION_URL: const.DOC_URL_GENERAL_OPTIONS
            },
        )

    async def async_step_restore_backup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle restore_backup step - delegate to restore_from_options."""
        return await self.async_step_restore_from_options(user_input)

    async def async_step_restore_from_options(self, user_input=None):
        """Handle restore options from general options menu (same as config flow)."""

        errors: dict[str, str] = {}

        if user_input is not None:
            selection = user_input.get(const.CFOF_DATA_RECOVERY_INPUT_SELECTION)

            if selection == "cancel":
                # Return to backup management menu without making changes
                return await self.async_step_manage_general_options()
            if selection == "start_fresh":
                return await self._handle_start_fresh_from_options()
            if selection == "current_active":
                return await self._handle_use_current_from_options()
            if selection == "paste_json":
                return await self.async_step_restore_paste_json_options()
            if selection in self._backup_restore_selection_map:
                selected_path = self._backup_restore_selection_map[selection]
                return await self._handle_restore_backup_from_options(selected_path)

            # Otherwise treat as raw filename for backwards compatibility
            if selection:
                return await self._handle_restore_backup_from_options(selection)

            errors[const.CFOP_ERROR_BASE] = const.TRANS_KEY_CFOF_INVALID_SELECTION

        # Build selection menu
        storage_path = self._get_scoped_storage_path()
        storage_file_exists = await self.hass.async_add_executor_job(
            storage_path.exists
        )

        backups = await bh.discover_backups(
            self.hass,
            None,
            storage_key=self._get_storage_key(),
            include_importable=True,
        )
        if not isinstance(backups, list):
            backups = []  # Handle any unexpected return type

        # Build options list for SelectSelector
        # Start with fixed options that can be translated
        options = []

        # Add cancel option first (for easy access)
        options.append("cancel")

        # Only show "use current" if file actually exists
        if storage_file_exists:
            options.append("current_active")

        options.append("start_fresh")

        # Add discovered backups (human-readable labels mapped to absolute paths)
        self._backup_restore_selection_map = {}
        for backup in backups:
            label = self._format_backup_selector_label(backup, prefix="📄")
            deduped_label = label
            suffix = 2
            while deduped_label in self._backup_restore_selection_map:
                deduped_label = f"{label} • #{suffix}"
                suffix += 1

            options.append(deduped_label)
            self._backup_restore_selection_map[deduped_label] = str(
                backup.get("full_path", backup.get("filename", ""))
            )

        options.append("paste_json")

        # Build schema using SelectSelector with translation_key
        data_schema = vol.Schema(
            {
                vol.Required(
                    const.CFOF_DATA_RECOVERY_INPUT_SELECTION
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=const.TRANS_KEY_CFOF_DATA_RECOVERY_SELECTION,
                        custom_value=True,  # Allow backup filenames not in translations
                    )
                )
            }
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_RESTORE_BACKUP,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "storage_path": str(storage_path.parent),
                "backup_count": str(len(backups)),
            },
        )

    async def _handle_start_fresh_from_options(self):
        """Handle 'Start Fresh' from options - backup existing and delete, then reload."""
        import os
        from pathlib import Path

        try:
            store = self._create_scoped_store()
            storage_path = Path(store.get_storage_path())

            # Create safety backup if file exists
            storage_file_exists = await self.hass.async_add_executor_job(
                storage_path.exists
            )
            if storage_file_exists:
                backup_name = await bh.create_timestamped_backup(
                    self.hass,
                    store,
                    const.BACKUP_TAG_RECOVERY,
                    config_entry=self.config_entry,
                    storage_key=store.storage_key,
                )
                if backup_name:
                    const.LOGGER.info(
                        "Created safety backup before fresh start: %s", backup_name
                    )

                # Delete active file
                await self.hass.async_add_executor_job(os.remove, str(storage_path))
                const.LOGGER.info("Deleted active storage file for fresh start")

            # Reload the entry to reinitialize from scratch
            self._mark_reload_needed()
            return await self.async_step_init()

        except Exception as err:
            const.LOGGER.error("Fresh start failed: %s", err)
            return self.async_abort(reason="unknown")

    async def _handle_use_current_from_options(self):
        """Handle 'Use Current Active' from options - validate and reload."""
        import json

        try:
            # Get storage path without creating storage manager yet
            storage_path = self._get_scoped_storage_path()

            storage_file_exists = await self.hass.async_add_executor_job(
                storage_path.exists
            )
            if not storage_file_exists:
                return self.async_abort(reason="file_not_found")

            # Validate JSON
            data_str = await self.hass.async_add_executor_job(
                storage_path.read_text, "utf-8"
            )

            try:
                json.loads(data_str)  # Parse to validate
            except json.JSONDecodeError:
                return self.async_abort(reason="corrupt_file")

            # Validate structure
            if not bh.validate_backup_json(data_str):
                return self.async_abort(reason="invalid_structure")

            const.LOGGER.info("Using current active storage file")
            self._mark_reload_needed()
            return await self.async_step_init()

        except Exception as err:
            const.LOGGER.error("Use current failed: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_restore_paste_json_options(self, user_input=None):
        """Allow user to paste JSON data from diagnostics in options flow."""
        import json

        errors: dict[str, str] = {}

        if user_input is not None:
            json_text = user_input.get(
                const.CFOF_DATA_RECOVERY_INPUT_JSON_DATA, ""
            ).strip()

            if not json_text:
                errors[const.CFOP_ERROR_BASE] = "empty_json"
            else:
                try:
                    # Parse JSON
                    pasted_data = json.loads(json_text)

                    # Validate structure
                    if not bh.validate_backup_json(json_text):
                        errors[const.CFOP_ERROR_BASE] = "invalid_structure"
                    else:
                        # Determine data format and extract storage data
                        storage_data = pasted_data

                        # Handle diagnostic format (KC 4.0+ diagnostic exports)
                        if "home_assistant" in pasted_data and "data" in pasted_data:
                            const.LOGGER.info("Processing diagnostic export format")
                            storage_data = pasted_data["data"]
                        # Handle Store format (KC 3.0/3.1/4.0beta1)
                        elif "version" in pasted_data and "data" in pasted_data:
                            const.LOGGER.info("Processing Store format")
                            storage_data = pasted_data["data"]
                        # Raw storage data format
                        else:
                            const.LOGGER.info("Processing raw storage format")
                            storage_data = pasted_data

                        # Always wrap in HA Store format for storage file
                        wrapped_data = {
                            "version": 1,
                            "minor_version": 1,
                            "key": self._get_storage_key(),
                            "data": storage_data,
                        }

                        # Write to storage file
                        storage_path = self._get_scoped_storage_path()

                        # Write wrapped data to storage (directory created by HA/test fixtures)
                        await self.hass.async_add_executor_job(
                            storage_path.write_text,
                            json.dumps(wrapped_data, indent=2),
                            "utf-8",
                        )

                        const.LOGGER.info("Successfully imported JSON data to storage")

                        # Reload and return to init
                        self._mark_reload_needed()
                        return await self.async_step_init()

                except json.JSONDecodeError:
                    errors[const.CFOP_ERROR_BASE] = "invalid_json"
                except Exception as err:
                    const.LOGGER.error("Paste JSON failed: %s", err)
                    errors[const.CFOP_ERROR_BASE] = "unknown"

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_PASTE_JSON_RESTORE,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.CFOF_DATA_RECOVERY_INPUT_JSON_DATA
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            multiline=True,
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_paste_json_restore(self, user_input=None) -> dict[str, Any]:
        """Handle paste_json_restore step - delegate to paste_json_options."""
        return await self.async_step_restore_paste_json_options(user_input)

    async def _handle_restore_backup_from_options(self, backup_reference: str):
        """Handle restoring from a specific backup file in options flow."""
        import json
        from pathlib import Path
        import shutil

        try:
            # Get current entry storage path
            storage_path = self._get_scoped_storage_path()

            candidate_path = Path(backup_reference)
            if candidate_path.is_absolute():
                backup_path = candidate_path
            else:
                backup_path = storage_path.parent / backup_reference

            backup_file_exists = await self.hass.async_add_executor_job(
                backup_path.exists
            )
            if not backup_file_exists:
                const.LOGGER.error("Backup file not found: %s", backup_reference)
                return self.async_abort(reason="file_not_found")

            # Read and validate backup
            backup_data_str = await self.hass.async_add_executor_job(
                backup_path.read_text, "utf-8"
            )

            try:
                json.loads(backup_data_str)  # Validate parseable JSON
            except json.JSONDecodeError:
                const.LOGGER.error("Backup file has invalid JSON: %s", backup_reference)
                return self.async_abort(reason="corrupt_file")

            # Validate structure
            if not bh.validate_backup_json(backup_data_str):
                const.LOGGER.error(
                    "Backup file missing required keys: %s", backup_reference
                )
                return self.async_abort(reason="invalid_structure")

            # Create safety backup of current file if it exists
            storage_file_exists = await self.hass.async_add_executor_job(
                storage_path.exists
            )
            if storage_file_exists:
                # Create storage manager only for safety backup creation
                store = self._create_scoped_store()
                safety_backup = await bh.create_timestamped_backup(
                    self.hass,
                    store,
                    const.BACKUP_TAG_RECOVERY,
                    config_entry=self.config_entry,
                    storage_key=store.storage_key,
                )
                if safety_backup:
                    const.LOGGER.info(
                        "Created safety backup before restore: %s", safety_backup
                    )

            # Parse backup data
            backup_data = json.loads(backup_data_str)

            # Check if backup already has Home Assistant storage format
            if "version" in backup_data and "data" in backup_data:
                # Already in storage format - restore as-is
                await self.hass.async_add_executor_job(
                    shutil.copy2, str(backup_path), str(storage_path)
                )
            elif backup_path.name in {const.STORAGE_KEY, "kidschores_data"}:
                # Legacy active-store payloads copied directly into current scoped path.
                await self.hass.async_add_executor_job(
                    shutil.copy2, str(backup_path), str(storage_path)
                )
            else:
                # Raw data format (like v30, v31, v40beta1 samples)
                # Load through storage manager to add proper wrapper
                store = self._create_scoped_store()
                store.set_data(backup_data)
                await store.async_save()

            const.LOGGER.info("Restored backup: %s", backup_path.name)

            # Reload and return to init
            self._mark_reload_needed()
            return await self.async_step_init()

        except Exception as err:
            const.LOGGER.error("Restore backup failed: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_backup_actions_menu(self, user_input=None):
        """Show backup management actions menu."""

        if user_input is not None:
            action = user_input[const.CFOF_BACKUP_ACTION_SELECTION]

            if action == "create_backup":
                return await self.async_step_create_manual_backup()
            if action == "delete_backup":
                return await self.async_step_select_backup_to_delete()
            if action == "restore_backup":
                return await self.async_step_restore_from_options()
            if action == "return_to_menu":
                return await self.async_step_init()

        # Discover backups to show count
        store = self._create_scoped_store()
        backups = await bh.discover_backups(
            self.hass,
            store,
            storage_key=store.storage_key,
            include_importable=False,
        )
        backup_count = len(backups)

        # Calculate total storage usage
        total_size_mb = sum(b.get("size_bytes", 0) for b in backups) / (1024 * 1024)

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_BACKUP_ACTIONS,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        const.CFOF_BACKUP_ACTION_SELECTION,
                        description={
                            "translation_key": const.CFOF_BACKUP_ACTION_SELECTION
                        },
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                const.OPTIONS_FLOW_BACKUP_ACTION_CREATE,
                                const.OPTIONS_FLOW_BACKUP_ACTION_DELETE,
                                const.OPTIONS_FLOW_BACKUP_ACTION_RESTORE,
                                "return_to_menu",
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key=const.TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU,
                        )
                    )
                }
            ),
            description_placeholders={
                "backup_count": str(backup_count),
                "storage_size": f"{total_size_mb:.2f}",
            },
        )

    async def async_step_select_backup_to_delete(self, user_input=None):
        """Select a backup file to delete."""
        from pathlib import Path

        from . import migration_pre_v50 as mp50

        store = self._create_scoped_store()

        if user_input is not None:
            selection = user_input.get(const.CFOF_BACKUP_SELECTION)

            if selection == "cancel":
                return await self.async_step_backup_actions_menu()

            selected_path = self._backup_delete_selection_map.get(selection)
            if selected_path:
                self._backup_to_delete = selected_path
                return await self.async_step_delete_backup_confirm()

            # Extract backup filename from emoji-prefixed selection
            if selection and selection.startswith("🗑️"):
                filename = self._extract_filename_from_selection(selection)
                if filename:
                    assert filename is not None  # Type narrowing for mypy
                    self._backup_to_delete = filename
                    return await self.async_step_delete_backup_confirm()

            return await self.async_step_backup_actions_menu()

        # Discover all backups
        backups = await bh.discover_backups(
            self.hass,
            store,
            storage_key=store.storage_key,
            include_importable=False,
        )
        storage_path = Path(store.get_storage_path())
        scoped_storage_dir = storage_path.parent
        root_storage_dir = scoped_storage_dir.parent

        def _discover_legacy_root_files() -> list[dict[str, Any]]:
            """Return legacy root choreops_data* files from .storage/."""
            candidates: list[dict[str, Any]] = []

            if not root_storage_dir.exists():
                return candidates

            for path in root_storage_dir.iterdir():
                if not path.is_file():
                    continue
                if not path.name.startswith(mp50.LEGACY_STORAGE_KEY):
                    continue

                stat_info = path.stat()
                age_hours = max(
                    0.0,
                    (dt_util.utcnow().timestamp() - stat_info.st_mtime) / 3600,
                )
                candidates.append(
                    {
                        "filename": path.name,
                        "full_path": str(path),
                        "size_bytes": stat_info.st_size,
                        "age_hours": age_hours,
                    }
                )

            candidates.sort(
                key=lambda item: cast("float", item["age_hours"]),
                reverse=False,
            )
            return candidates

        legacy_root_files = await self.hass.async_add_executor_job(
            _discover_legacy_root_files
        )

        # Build backup options - EMOJI ONLY for files (no hardcoded action text)
        # All backups can be deleted (no protected backups concept)
        backup_options = []
        self._backup_delete_selection_map = {}

        for backup in backups:
            age_str = bh.format_backup_age(backup["age_hours"])
            size_kb = backup["size_bytes"] / 1024
            tag_display = backup["tag"].replace("-", " ").title()

            # Emoji-only prefix - NO hardcoded English text
            option = (
                f"🗑️ [{tag_display}] {backup['filename']} ({age_str}, {size_kb:.1f} KB)"
            )
            backup_options.append(option)
            self._backup_delete_selection_map[option] = str(
                scoped_storage_dir / backup["filename"]
            )

        for legacy_file in legacy_root_files:
            age_str = bh.format_backup_age(cast("float", legacy_file["age_hours"]))
            size_kb = cast("float", legacy_file["size_bytes"]) / 1024
            filename = cast("str", legacy_file["filename"])
            full_path = cast("str", legacy_file["full_path"])

            option = f"🗑️ [Legacy Root] {filename} ({age_str}, {size_kb:.1f} KB)"
            backup_options.append(option)
            self._backup_delete_selection_map[option] = full_path

        # Add cancel option (translated via translation_key)
        backup_options.append("cancel")

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE,
            data_schema=vol.Schema(
                {
                    vol.Required(const.CFOF_BACKUP_SELECTION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=backup_options,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE,
                            custom_value=True,
                        )
                    )
                }
            ),
            description_placeholders={
                "backup_count": str(len(backups) + len(legacy_root_files)),
            },
        )

    async def async_step_select_backup_to_restore(self, user_input=None):
        """Select a backup file to restore."""

        store = self._create_scoped_store()

        if user_input is not None:
            selection = user_input.get(const.CFOF_BACKUP_SELECTION)

            if selection == "cancel":
                return await self.async_step_backup_actions_menu()

            selected_path = self._backup_restore_selection_map.get(selection or "")
            if selected_path:
                self._backup_to_restore = selected_path
                return await self.async_step_restore_backup_confirm()

            # Extract backup filename from emoji-prefixed selection
            if selection and selection.startswith("🔄"):
                filename = self._extract_filename_from_selection(selection)
                if filename:
                    assert filename is not None  # Type narrowing for mypy
                    self._backup_to_restore = filename
                    return await self.async_step_restore_backup_confirm()

            return await self.async_step_backup_actions_menu()

        # Discover all backups
        backups = await bh.discover_backups(
            self.hass,
            store,
            storage_key=store.storage_key,
            include_importable=True,
        )

        if not backups:
            # No backups available - return to menu
            return await self.async_step_backup_actions_menu()

        # Build backup options - EMOJI ONLY for files (no hardcoded action text)
        backup_options = []
        self._backup_restore_selection_map = {}

        for backup in backups:
            option = self._format_backup_selector_label(backup, prefix="🔄")
            deduped_option = option
            suffix = 2
            while deduped_option in self._backup_restore_selection_map:
                deduped_option = f"{option} • #{suffix}"
                suffix += 1

            backup_options.append(deduped_option)
            self._backup_restore_selection_map[deduped_option] = str(
                backup.get("full_path", backup.get("filename", ""))
            )

        # Add cancel option (translated via translation_key)
        backup_options.append("cancel")

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE,
            data_schema=vol.Schema(
                {
                    vol.Required(const.CFOF_BACKUP_SELECTION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=backup_options,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key=const.TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE,
                            custom_value=True,
                        )
                    )
                }
            ),
            description_placeholders={"backup_count": str(len(backups))},
        )

    def _extract_filename_from_selection(self, selection: str) -> str | None:
        """Extract backup filename from emoji-prefixed selection.

        Format: "🔄 [Tag] filename.json (age, size)" or "🗑️ [Tag] filename.json (age, size)"
        Returns: "filename.json" or None if extraction fails
        """
        # Remove emoji prefix (first 2-3 characters depending on emoji width)
        if selection.startswith(("🔄 ", "🗑️ ")):
            display_part = selection[2:].strip()

            # Extract from "[Tag] filename.json (age, size)"
            if "] " in display_part and " (" in display_part:
                start_idx = display_part.find("] ") + 2
                end_idx = display_part.rfind(" (")
                if start_idx < end_idx:
                    return display_part[start_idx:end_idx]

        # Fallback: return None (couldn't parse)
        return None

    async def async_step_create_manual_backup(self, user_input=None):
        """Create a manual backup."""

        store = self._create_scoped_store()

        if user_input is not None:
            if user_input.get("confirm"):
                # Create manual backup
                backup_filename = await bh.create_timestamped_backup(
                    self.hass,
                    store,
                    const.BACKUP_TAG_MANUAL,
                    self.config_entry,
                    storage_key=store.storage_key,
                )

                if backup_filename:
                    const.LOGGER.info("Manual backup created: %s", backup_filename)

                    # Show success message and return to backup menu
                    const.LOGGER.info(
                        "Manual backup created successfully: %s", backup_filename
                    )
                    return await self.async_step_backup_actions_menu()
                const.LOGGER.error("Failed to create manual backup")
                return await self.async_step_backup_actions_menu()
            return await self.async_step_backup_actions_menu()

        # Get backup count and retention for placeholders
        available_backups = await bh.discover_backups(
            self.hass,
            store,
            storage_key=store.storage_key,
            include_importable=False,
        )
        backup_count = len(available_backups)
        retention = self._entry_options.get(
            const.CONF_BACKUPS_MAX_RETAINED,
            const.DEFAULT_BACKUPS_MAX_RETAINED,
        )

        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_CREATE_MANUAL_BACKUP,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "backup_count": str(backup_count),
                "retention": str(retention),
            },
        )

    async def async_step_delete_backup_confirm(self, user_input=None):
        """Confirm backup deletion."""
        from pathlib import Path

        # Get backup target path from context (set by select_backup_to_delete step)
        backup_target = getattr(self, "_backup_to_delete", None)

        if user_input is not None:
            if user_input.get("confirm"):
                store = self._create_scoped_store()
                storage_path = Path(store.get_storage_path())
                # Type guard: ensure backup_target is a string before using in Path operation
                if isinstance(backup_target, str):
                    backup_path = Path(backup_target)
                    if not backup_path.is_absolute():
                        backup_path = storage_path.parent / backup_target

                    scoped_storage_dir = storage_path.parent.resolve()
                    root_storage_dir = scoped_storage_dir.parent.resolve()
                    resolved_backup_path = backup_path.resolve()

                    is_allowed_path = resolved_backup_path.parent in {
                        scoped_storage_dir,
                        root_storage_dir,
                    }

                    if not is_allowed_path:
                        const.LOGGER.error(
                            "Refusing to delete file outside allowed storage directories: %s",
                            resolved_backup_path,
                        )
                        self._backup_to_delete = None
                        self._backup_delete_selection_map = {}
                        return await self.async_step_backup_actions_menu()

                    if backup_path.exists():
                        try:
                            await self.hass.async_add_executor_job(backup_path.unlink)
                            const.LOGGER.info("Deleted backup: %s", backup_path.name)
                        except Exception as err:
                            const.LOGGER.error(
                                "Failed to delete backup %s: %s", backup_path.name, err
                            )
                    else:
                        const.LOGGER.error("Backup file not found: %s", backup_path)
                else:
                    const.LOGGER.error("Invalid backup filename: %s", backup_target)

            # Clear the backup filename and return to backup menu
            self._backup_to_delete = None
            self._backup_delete_selection_map = {}
            return await self.async_step_backup_actions_menu()

        # Show confirmation form
        backup_display_name = (
            Path(backup_target).name if isinstance(backup_target, str) else "unknown"
        )
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_DELETE_BACKUP_CONFIRM,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"backup_filename": backup_display_name},
        )

    async def async_step_restore_backup_confirm(self, user_input=None):
        """Confirm backup restoration."""
        from pathlib import Path
        import shutil

        # Get backup filename from context (set by select_backup_to_restore step)
        backup_filename = getattr(self, "_backup_to_restore", None)

        if user_input is not None:
            if user_input.get("confirm"):
                store = self._create_scoped_store()
                storage_path = Path(store.get_storage_path())
                # Type guard: ensure backup_filename is a string before using in Path operation
                if not isinstance(backup_filename, str):
                    const.LOGGER.error("Invalid backup filename: %s", backup_filename)
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                candidate_path = Path(backup_filename)
                if candidate_path.is_absolute():
                    backup_path = candidate_path
                else:
                    backup_path = storage_path.parent / backup_filename

                if not backup_path.exists():
                    const.LOGGER.error("Backup file not found: %s", backup_filename)
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                # Read and validate backup
                try:
                    backup_data_str = await self.hass.async_add_executor_job(
                        backup_path.read_text, "utf-8"
                    )
                except Exception as err:
                    const.LOGGER.error(
                        "Failed to read backup file %s: %s", backup_filename, err
                    )
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                if not bh.validate_backup_json(backup_data_str):
                    const.LOGGER.error("Invalid backup file: %s", backup_filename)
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()

                try:
                    import json

                    # Create safety backup of current file
                    safety_backup = await bh.create_timestamped_backup(
                        self.hass,
                        store,
                        const.BACKUP_TAG_RECOVERY,
                        self.config_entry,
                        storage_key=store.storage_key,
                    )
                    const.LOGGER.info("Created safety backup: %s", safety_backup)

                    # Restore backup
                    await self.hass.async_add_executor_job(
                        shutil.copy2, backup_path, storage_path
                    )
                    const.LOGGER.info("Restored backup: %s", backup_filename)

                    # Extract and apply config_entry_settings if present
                    backup_data_str = await self.hass.async_add_executor_job(
                        backup_path.read_text, "utf-8"
                    )
                    backup_data = json.loads(backup_data_str)

                    if const.DATA_CONFIG_ENTRY_SETTINGS in backup_data:
                        settings = backup_data[const.DATA_CONFIG_ENTRY_SETTINGS]
                        validated = bh.validate_config_entry_settings(settings)

                        if validated:
                            # Merge with defaults for any missing keys
                            new_options = {
                                key: validated.get(key, default)
                                for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
                            }
                            # Update config entry with restored settings
                            self.hass.config_entries.async_update_entry(
                                self.config_entry, options=new_options
                            )
                            const.LOGGER.info(
                                "Restored %d system settings from backup",
                                len(validated),
                            )
                        else:
                            const.LOGGER.info(
                                "No valid system settings in backup, keeping current settings"
                            )
                    else:
                        const.LOGGER.info(
                            "Backup does not contain system settings, keeping current settings"
                        )

                    # Clear context and reload integration to pick up restored data
                    self._backup_to_restore = None
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )

                    return self.async_abort(reason="backup_restored")

                except Exception as err:
                    const.LOGGER.error(
                        "Failed to restore backup %s: %s", backup_filename, err
                    )
                    self._backup_to_restore = None
                    return await self.async_step_backup_actions_menu()
            else:
                # User cancelled - clear context and return to backup menu
                self._backup_to_restore = None
                return await self.async_step_backup_actions_menu()

        # Show confirmation form
        return self.async_show_form(
            step_id=const.OPTIONS_FLOW_STEP_RESTORE_BACKUP_CONFIRM,
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"backup_filename": backup_filename or "unknown"},
        )

    # ----------------------------------------------------------------------------------
    # HELPER METHODS
    # ----------------------------------------------------------------------------------

    def _get_storage_key(self) -> str:
        """Return scoped storage key for current config entry."""
        return get_entry_storage_key_from_entry(self.config_entry)

    def _create_scoped_store(self):
        """Return a scoped store bound to current config entry."""
        from .store import ChoreOpsStore

        return ChoreOpsStore(self.hass, self._get_storage_key())

    def _get_scoped_storage_path(self):
        """Return scoped storage path for current config entry."""
        from pathlib import Path

        return Path(
            self.hass.config.path(
                ".storage",
                const.STORAGE_DIRECTORY,
                self._get_storage_key(),
            )
        )

    def _format_backup_selector_label(
        self,
        backup: dict[str, Any],
        *,
        prefix: str,
    ) -> str:
        """Create date-first human-readable selector label for a backup."""
        timestamp = cast("datetime", backup["timestamp"])
        local_ts = dt_util.as_local(timestamp).strftime("%Y-%m-%d %H:%M")
        tag_display = str(backup.get("tag", "backup")).replace("-", " ").title()
        scope = str(backup.get("scope", "other"))
        if scope == "current":
            scope_display = "Current Entry"
        elif scope == "legacy":
            scope_display = "Legacy Import"
        else:
            scope_display = "Other Entry"
        return f"{prefix} {local_ts} • {tag_display} • {scope_display}"

    def _get_coordinator(self):
        """Get the coordinator from config entry runtime_data."""
        return self.config_entry.runtime_data

    def _get_entity_dict(self):
        """Retrieve appropriate entity dict based on entity_type."""
        coordinator = self._get_coordinator()

        if self._entity_type == const.OPTIONS_FLOW_DIC_USER:
            return coordinator.users_for_management

        entity_type_to_data = {
            const.OPTIONS_FLOW_DIC_CHORE: const.DATA_CHORES,
            const.OPTIONS_FLOW_DIC_BADGE: const.DATA_BADGES,
            const.OPTIONS_FLOW_DIC_REWARD: const.DATA_REWARDS,
            const.OPTIONS_FLOW_DIC_BONUS: const.DATA_BONUSES,
            const.OPTIONS_FLOW_DIC_PENALTY: const.DATA_PENALTIES,
            const.OPTIONS_FLOW_DIC_ACHIEVEMENT: const.DATA_ACHIEVEMENTS,
            const.OPTIONS_FLOW_DIC_CHALLENGE: const.DATA_CHALLENGES,
        }
        key = entity_type_to_data.get(self._entity_type or "", "")
        if not key:
            const.LOGGER.error(
                "Unknown entity type '%s'. Cannot retrieve entity dictionary",
                self._entity_type,
            )
            return {}
        return coordinator.data.get(key, {})

    def _get_user_ha_user_ids(self) -> list[str]:
        """Return distinct linked user Home Assistant user IDs."""
        coordinator = self._get_coordinator()
        approvers_data = coordinator.approvers_data

        user_ids: list[str] = []
        seen: set[str] = set()
        for approver_data in approvers_data.values():
            if not isinstance(approver_data, dict):
                continue
            user_id = approver_data.get(const.DATA_USER_HA_USER_ID)
            if not isinstance(user_id, str):
                continue
            normalized_user_id = user_id.strip()
            if not normalized_user_id or normalized_user_id in seen:
                continue
            seen.add(normalized_user_id)
            user_ids.append(normalized_user_id)

        return user_ids

    def _mark_reload_needed(self):
        """Mark that a reload is needed after the current flow completes.

        When entities (rewards, bonuses, chores, etc.) are added, edited, or deleted,
        the coordinator data is updated but new sensors are not automatically created.
        We defer the reload until the user returns to the main menu to avoid
        interrupting the flow mid-operation.
        """
        const.LOGGER.debug("Marking reload needed after entity change")
        self._reload_needed = True

    async def _reload_entry_after_entity_change(self):
        """Reload config entry after entity data changes (assignees, chores, badges, etc.).

        Runs cleanup before reload to remove orphaned entities and entities disabled by flags.
        Complementary to async_update_options (in __init__.py) which handles system settings.
        Both paths must run synchronized cleanup - see DEVELOPMENT_STANDARDS.md Section 6.
        """
        coordinator = self._get_coordinator()
        if coordinator:
            const.LOGGER.debug("Running entity cleanup before reload")

            # Update coordinator's config_entry reference to get latest options
            # (flag changes may have been staged in self._entry_options)
            coordinator.config_entry = self.config_entry

            # FLAG-DRIVEN: Remove entities disabled by feature toggles
            # Data-driven orphan cleanup is NOT done here - it's handled by:
            # 1. Managers doing targeted cleanup when they delete/update items
            # 2. Startup safety net (remove_all_orphaned_entities) catching stragglers
            const.LOGGER.debug("Checking conditional entities against feature flags")
            await coordinator.system_manager.remove_conditional_entities()

        const.LOGGER.debug(
            "Reloading entry after entity changes: %s",
            self.config_entry.entry_id,
        )
        try:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            const.LOGGER.debug("Entry reloaded successfully")
        except Exception as err:
            const.LOGGER.error(
                "Failed to reload config entry after entity changes: %s",
                err,
                exc_info=True,
            )
            # Continue despite reload failure - UI still shows menu and entities
            # will reload on next Home Assistant restart

        # Trigger immediate coordinator refresh so new entities get data right away
        # instead of waiting for the next update interval
        coordinator = self._get_coordinator()
        if coordinator:
            const.LOGGER.debug("Triggering immediate coordinator refresh after reload")
            await coordinator.async_request_refresh()
            const.LOGGER.debug("Coordinator refresh completed")

    async def _update_system_settings_and_reload(self):
        """Update system settings in config and reload (for points_label, update_interval, etc.)."""
        new_data = dict(self.config_entry.data)
        new_data[const.DATA_LAST_CHANGE] = dt_util.utcnow().isoformat()

        self.hass.config_entries.async_update_entry(
            self.config_entry, data=new_data, options=self._entry_options
        )
        const.LOGGER.debug(
            "Updating system settings. Reloading entry: %s",
            self.config_entry.entry_id,
        )
        try:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            const.LOGGER.debug("System settings updated and ChoreOps reloaded")
        except Exception as err:
            const.LOGGER.error(
                "Failed to reload config entry after system settings update: %s",
                err,
                exc_info=True,
            )
            # Continue despite reload failure - settings saved in config entry
            # and will take effect on next Home Assistant restart
