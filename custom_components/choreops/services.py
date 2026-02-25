# File: services.py
"""Defines custom services for the ChoreOps integration.

These services allow direct actions through scripts or automations.
Includes UI editor support with selectors for dropdowns and text inputs.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util
import voluptuous as vol

from . import const
from .helpers import flow_helpers, report_helpers, translation_helpers
from .helpers.auth_helpers import (
    AUTH_ACTION_APPROVAL,
    AUTH_ACTION_MANAGEMENT,
    AUTH_ACTION_PARTICIPATION,
    is_user_authorized_for_action,
)
from .helpers.entity_helpers import get_first_choreops_entry, get_item_id_or_raise
from .utils.dt_utils import dt_parse

if TYPE_CHECKING:
    from .coordinator import ChoreOpsDataCoordinator
    from .type_defs import ChoreData


def _get_coordinator_by_entry_id(
    hass: HomeAssistant, entry_id: str
) -> "ChoreOpsDataCoordinator":
    """Get coordinator from config entry ID using runtime_data.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID string

    Returns:
        ChoreOpsDataCoordinator instance

    Raises:
        HomeAssistantError: If entry not found or not loaded
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry:
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
        )
    return cast("ChoreOpsDataCoordinator", entry.runtime_data)


# --- Service Schemas ---

# Common schema base patterns for DRY principle
_ASSIGNEE_CHORE_BASE = {
    vol.Required(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_CHORE_NAME): cv.string,
}

_APPROVER_ASSIGNEE_CHORE_BASE = {
    vol.Required(const.SERVICE_FIELD_APPROVER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_CHORE_NAME): cv.string,
}

_APPROVER_ASSIGNEE_REWARD_BASE = {
    vol.Required(const.SERVICE_FIELD_APPROVER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_REWARD_NAME): cv.string,
}

_APPROVER_ASSIGNEE_PENALTY_BASE = {
    vol.Required(const.SERVICE_FIELD_APPROVER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_PENALTY_NAME): cv.string,
}

_APPROVER_ASSIGNEE_BONUS_BASE = {
    vol.Required(const.SERVICE_FIELD_APPROVER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Required(const.SERVICE_FIELD_BONUS_NAME): cv.string,
}

# Service schemas using base patterns
CLAIM_CHORE_SCHEMA = vol.Schema(_ASSIGNEE_CHORE_BASE)

APPROVE_CHORE_SCHEMA = vol.Schema(
    {
        **_APPROVER_ASSIGNEE_CHORE_BASE,  # type: ignore[misc]
        vol.Optional(const.SERVICE_FIELD_CHORE_POINTS_AWARDED): vol.Coerce(float),
    }
)

DISAPPROVE_CHORE_SCHEMA = vol.Schema(_APPROVER_ASSIGNEE_CHORE_BASE)

REDEEM_REWARD_SCHEMA = vol.Schema(_APPROVER_ASSIGNEE_REWARD_BASE)

APPROVE_REWARD_SCHEMA = vol.Schema(
    {
        **_APPROVER_ASSIGNEE_REWARD_BASE,  # type: ignore[misc]
        vol.Optional(const.SERVICE_FIELD_REWARD_COST_OVERRIDE): vol.Coerce(float),
    }
)

DISAPPROVE_REWARD_SCHEMA = vol.Schema(_APPROVER_ASSIGNEE_REWARD_BASE)

APPLY_PENALTY_SCHEMA = vol.Schema(_APPROVER_ASSIGNEE_PENALTY_BASE)

APPLY_BONUS_SCHEMA = vol.Schema(_APPROVER_ASSIGNEE_BONUS_BASE)

# Optional filter base patterns for reset operations
_OPTIONAL_ASSIGNEE_FILTER = {vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string}

_OPTIONAL_ASSIGNEE_PENALTY_FILTER = {
    vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Optional(const.SERVICE_FIELD_PENALTY_NAME): cv.string,
}

_OPTIONAL_ASSIGNEE_BONUS_FILTER = {
    vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Optional(const.SERVICE_FIELD_BONUS_NAME): cv.string,
}

_OPTIONAL_ASSIGNEE_REWARD_FILTER = {
    vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
    vol.Optional(const.SERVICE_FIELD_REWARD_NAME): cv.string,
}

RESET_OVERDUE_CHORES_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_CHORE_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
    }
)

REMOVE_AWARDED_BADGES_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_USER_NAME): vol.Any(cv.string, None),
        vol.Optional(const.SERVICE_FIELD_BADGE_NAME): vol.Any(cv.string, None),
    }
)

RESET_CHORES_TO_PENDING_STATE_SCHEMA = vol.Schema(
    {}
)  # Renamed from RESET_ALL_CHORES_SCHEMA

# Unified Data Reset Service V2 (replaces reset_rewards, reset_penalties, reset_bonuses)
RESET_TRANSACTIONAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(const.SERVICE_FIELD_CONFIRM_DESTRUCTIVE): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_SCOPE): vol.In(
            [const.DATA_RESET_SCOPE_GLOBAL, const.DATA_RESET_SCOPE_USER]
        ),
        vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_ITEM_TYPE): vol.In(
            [
                const.DATA_RESET_ITEM_TYPE_POINTS,
                const.DATA_RESET_ITEM_TYPE_CHORES,
                const.DATA_RESET_ITEM_TYPE_REWARDS,
                const.DATA_RESET_ITEM_TYPE_BADGES,
                const.DATA_RESET_ITEM_TYPE_ACHIEVEMENTS,
                const.DATA_RESET_ITEM_TYPE_CHALLENGES,
                const.DATA_RESET_ITEM_TYPE_PENALTIES,
                const.DATA_RESET_ITEM_TYPE_BONUSES,
            ]
        ),
        vol.Optional(const.SERVICE_FIELD_ITEM_NAME): cv.string,
    }
)

SET_CHORE_DUE_DATE_SCHEMA = vol.Schema(
    {
        vol.Required(const.SERVICE_FIELD_CHORE_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_DUE_DATE): vol.Any(cv.string, None),
        vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_USER_ID): cv.string,
    }
)

SKIP_CHORE_DUE_DATE_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_CHORE_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_USER_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_MARK_AS_MISSED, default=False): cv.boolean,
    }
)

GENERATE_ACTIVITY_REPORT_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_REPORT_LANGUAGE): cv.string,
        vol.Optional(const.SERVICE_FIELD_REPORT_NOTIFY_SERVICE): cv.string,
        vol.Optional(const.SERVICE_FIELD_REPORT_TITLE): cv.string,
        vol.Optional(
            const.SERVICE_FIELD_REPORT_OUTPUT_FORMAT,
            default=const.REPORT_OUTPUT_FORMAT_MARKDOWN,
        ): vol.In(
            [
                const.REPORT_OUTPUT_FORMAT_MARKDOWN,
                const.REPORT_OUTPUT_FORMAT_HTML,
                const.REPORT_OUTPUT_FORMAT_BOTH,
            ]
        ),
    }
)

# ==============================================================================
# REWARD CRUD SCHEMAS (using data_builders pattern)
# ==============================================================================

# NOTE: cost is REQUIRED for create_reward - no invisible defaults for automations
CREATE_REWARD_SCHEMA = vol.Schema(
    {
        vol.Required(const.SERVICE_FIELD_REWARD_CRUD_NAME): cv.string,
        vol.Required(const.SERVICE_FIELD_REWARD_CRUD_COST): vol.Coerce(float),
        vol.Optional(
            const.SERVICE_FIELD_REWARD_CRUD_DESCRIPTION, default=""
        ): cv.string,
        vol.Optional(
            const.SERVICE_FIELD_REWARD_CRUD_ICON, default=const.SENTINEL_EMPTY
        ): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_LABELS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

# NOTE: Either reward_id OR name must be provided (resolved in handler)
UPDATE_REWARD_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_COST): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_DESCRIPTION): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_ICON): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_LABELS): vol.All(
            cv.ensure_list, [cv.string]
        ),
    }
)

# NOTE: Either reward_id OR name must be provided (resolved in handler)
DELETE_REWARD_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_REWARD_CRUD_NAME): cv.string,
    }
)

# ============================================================================
# CHORE CRUD SCHEMAS
# ============================================================================
# NOTE: Chore services use DATA_* keys directly (unlike rewards which use CFOF_* keys)
# because build_chore() in data_builders expects pre-processed DATA_* keys.
#
# Field validation:
# - name: required for create, optional for update
# - assigned_user_names: required for create (list of assignee names resolved to UUIDs)
# - completion_criteria: allowed for create and update (validated in Manager)
# - Other fields use defaults from const.DEFAULT_*

# Enum validators for select fields
_CHORE_FREQUENCY_VALUES = [
    const.FREQUENCY_NONE,
    const.FREQUENCY_DAILY,
    const.FREQUENCY_WEEKLY,
    const.FREQUENCY_BIWEEKLY,
    const.FREQUENCY_MONTHLY,
    const.FREQUENCY_QUARTERLY,
    const.FREQUENCY_YEARLY,
    const.FREQUENCY_CUSTOM,
    const.FREQUENCY_CUSTOM_FROM_COMPLETE,
    # Period-end frequencies
    const.PERIOD_WEEK_END,
    const.PERIOD_MONTH_END,
    const.PERIOD_QUARTER_END,
    const.PERIOD_YEAR_END,
]

_COMPLETION_CRITERIA_VALUES = [
    const.COMPLETION_CRITERIA_INDEPENDENT,
    const.COMPLETION_CRITERIA_SHARED_FIRST,
    const.COMPLETION_CRITERIA_SHARED,
    const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
    const.COMPLETION_CRITERIA_ROTATION_SMART,
]

_APPROVAL_RESET_VALUES = [
    const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
    const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
    const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
    const.APPROVAL_RESET_UPON_COMPLETION,
]

_PENDING_CLAIMS_VALUES = [
    const.APPROVAL_RESET_PENDING_CLAIM_HOLD,
    const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
]

_OVERDUE_HANDLING_VALUES = [
    const.OVERDUE_HANDLING_AT_DUE_DATE,
    const.OVERDUE_HANDLING_NEVER_OVERDUE,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
]

# Days of week - using raw values since there are no individual DAY_* constants
_DAY_OF_WEEK_VALUES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

CREATE_CHORE_SCHEMA = vol.Schema(
    {
        vol.Required(const.SERVICE_FIELD_CHORE_CRUD_NAME): cv.string,
        # Canonical public contract: callers provide assignee display names.
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES): vol.All(
            cv.ensure_list, [cv.string]
        ),
        # Compatibility exception: legacy automations still send name lists under
        # assigned_user_ids. We accept this field during transition and normalize
        # to real UUIDs in the handler before any storage/update operations.
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_POINTS): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DESCRIPTION, default=""): cv.string,
        vol.Optional(
            const.SERVICE_FIELD_CHORE_CRUD_ICON, default=const.SENTINEL_EMPTY
        ): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_LABELS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_FREQUENCY): vol.In(
            _CHORE_FREQUENCY_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS): vol.All(
            cv.ensure_list, [vol.In(_DAY_OF_WEEK_VALUES)]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA): vol.In(
            _COMPLETION_CRITERIA_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET): vol.In(
            _APPROVAL_RESET_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS): vol.In(
            _PENDING_CLAIMS_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING): vol.In(
            _OVERDUE_HANDLING_VALUES
        ),
        vol.Optional(
            const.SERVICE_FIELD_CHORE_CRUD_CLAIM_LOCK_UNTIL_WINDOW
        ): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE): cv.datetime,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_WINDOW_OFFSET): vol.All(
            cv.string, flow_helpers.validate_duration_string
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_REMINDER_OFFSET): vol.All(
            cv.string, flow_helpers.validate_duration_string
        ),
    }
)

# NOTE: Either chore_id OR name must be provided (resolved in handler)
# completion_criteria IS allowed in update (mutable, with transition handling in Manager)
UPDATE_CHORE_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_NAME): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA): vol.In(
            _COMPLETION_CRITERIA_VALUES
        ),
        # Canonical input key (names in payload).
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES): vol.All(
            cv.ensure_list, [cv.string]
        ),
        # Compatibility exception: keep accepting legacy key in updates so
        # existing automations do not break. Handler normalizes values to UUIDs.
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_POINTS): vol.Coerce(float),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DESCRIPTION): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ICON): vol.Any(None, "", cv.icon),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_LABELS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_FREQUENCY): vol.In(
            _CHORE_FREQUENCY_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS): vol.All(
            cv.ensure_list, [vol.In(_DAY_OF_WEEK_VALUES)]
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET): vol.In(
            _APPROVAL_RESET_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS): vol.In(
            _PENDING_CLAIMS_VALUES
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING): vol.In(
            _OVERDUE_HANDLING_VALUES
        ),
        vol.Optional(
            const.SERVICE_FIELD_CHORE_CRUD_CLAIM_LOCK_UNTIL_WINDOW
        ): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE): cv.boolean,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE): cv.datetime,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_WINDOW_OFFSET): vol.All(
            cv.string, flow_helpers.validate_duration_string
        ),
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_DUE_REMINDER_OFFSET): vol.All(
            cv.string, flow_helpers.validate_duration_string
        ),
    }
)

# NOTE: Either chore_id OR name must be provided (resolved in handler)
DELETE_CHORE_SCHEMA = vol.Schema(
    {
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_NAME): cv.string,
    }
)

# Map service fields to DATA_* storage keys
# This bridges user-friendly service API → internal storage keys
# NOTE: Chores use DATA_* keys (unlike rewards which use CFOF_* keys)
_SERVICE_TO_CHORE_DATA_MAPPING: dict[str, str] = {
    const.SERVICE_FIELD_CHORE_CRUD_NAME: const.DATA_CHORE_NAME,
    const.SERVICE_FIELD_CHORE_CRUD_POINTS: const.DATA_CHORE_DEFAULT_POINTS,
    const.SERVICE_FIELD_CHORE_CRUD_DESCRIPTION: const.DATA_CHORE_DESCRIPTION,
    const.SERVICE_FIELD_CHORE_CRUD_ICON: const.DATA_CHORE_ICON,
    const.SERVICE_FIELD_CHORE_CRUD_LABELS: const.DATA_CHORE_LABELS,
    # Internal canonical assignment storage is always UUIDs in
    # DATA_CHORE_ASSIGNED_USER_IDS. Handler normalization ensures this mapping
    # only receives IDs, even when legacy callers provide name lists.
    const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS: const.DATA_CHORE_ASSIGNED_USER_IDS,
    const.SERVICE_FIELD_CHORE_CRUD_FREQUENCY: const.DATA_CHORE_RECURRING_FREQUENCY,
    const.SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS: const.DATA_CHORE_APPLICABLE_DAYS,
    const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA: const.DATA_CHORE_COMPLETION_CRITERIA,
    const.SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET: const.DATA_CHORE_APPROVAL_RESET_TYPE,
    const.SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS: const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    const.SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING: const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
    const.SERVICE_FIELD_CHORE_CRUD_CLAIM_LOCK_UNTIL_WINDOW: const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
    const.SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE: const.DATA_CHORE_AUTO_APPROVE,
    const.SERVICE_FIELD_CHORE_CRUD_DUE_WINDOW_OFFSET: const.DATA_CHORE_DUE_WINDOW_OFFSET,
    const.SERVICE_FIELD_CHORE_CRUD_DUE_REMINDER_OFFSET: const.DATA_CHORE_DUE_REMINDER_OFFSET,
    # NOTE: due_date is handled specially via set_chore_due_date() hook
}

# Map service fields to DATA_* storage keys for rewards
# This bridges user-friendly service API → internal storage keys
# NOTE: Now matches chore pattern (DATA_* keys directly)
_SERVICE_TO_REWARD_DATA_MAPPING: dict[str, str] = {
    const.SERVICE_FIELD_REWARD_CRUD_NAME: const.DATA_REWARD_NAME,
    const.SERVICE_FIELD_REWARD_CRUD_COST: const.DATA_REWARD_COST,
    const.SERVICE_FIELD_REWARD_CRUD_DESCRIPTION: const.DATA_REWARD_DESCRIPTION,
    const.SERVICE_FIELD_REWARD_CRUD_ICON: const.DATA_REWARD_ICON,
    const.SERVICE_FIELD_REWARD_CRUD_LABELS: const.DATA_REWARD_LABELS,
}

# ==============================================================================
# ROTATION MANAGEMENT SCHEMAS (Phase 3 Step 7 - v0.5.0)
# ==============================================================================

# Set rotation turn to specific assignee
SET_ROTATION_TURN_SCHEMA = vol.Schema(
    {
        # Either chore_id OR chore_name required
        vol.Optional(const.SERVICE_FIELD_CHORE_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_NAME): cv.string,
        # Either assignee_id OR assignee_name required
        vol.Optional(const.SERVICE_FIELD_USER_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_USER_NAME): cv.string,
    }
)

# Reset rotation to first assigned assignee
RESET_ROTATION_SCHEMA = vol.Schema(
    {
        # Either chore_id OR chore_name required
        vol.Optional(const.SERVICE_FIELD_CHORE_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_NAME): cv.string,
    }
)

# Open rotation cycle (allow any assignee to claim once)
OPEN_ROTATION_CYCLE_SCHEMA = vol.Schema(
    {
        # Either chore_id OR chore_name required
        vol.Optional(const.SERVICE_FIELD_CHORE_ID): cv.string,
        vol.Optional(const.SERVICE_FIELD_CHORE_NAME): cv.string,
    }
)


def _map_service_to_data_keys(
    service_data: dict[str, Any],
    mapping: dict[str, str],
) -> dict[str, Any]:
    """Convert service field names to DATA_* storage keys.

    Args:
        service_data: Data from service call with user-friendly field names
        mapping: Dict mapping service field names to DATA_* constants

    Returns:
        Dict with DATA_* keys for data_builders consumption
    """
    return {
        mapping[key]: value for key, value in service_data.items() if key in mapping
    }


# --- Setup Services ---
def async_setup_services(hass: HomeAssistant):
    """Register ChoreOps services."""

    # ==========================================================================
    # RESET SERVICE HANDLERS
    # ==========================================================================

    # ========================================================================
    # CHORE SERVICE HANDLERS
    # ========================================================================

    async def handle_create_chore(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.create_chore service call.

        Creates a new chore using data_builders.build_chore() for consistent
        field handling with the Options Flow UI.

        Args:
            call: Service call with name, assigned assignees, and optional fields

        Returns:
            Dict with chore_id of the created chore

        Raises:
            HomeAssistantError: If no coordinator available or validation fails
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Create Chore: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve assignee names to UUIDs.
        # Exception by design: during contract migration we accept legacy payloads
        # that still put names under assigned_user_ids.
        assignee_names = call.data.get(
            const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES
        )
        if assignee_names is None:
            assignee_names = call.data.get(
                const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS
            )
        if not assignee_names:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_FIELD,
                translation_placeholders={
                    "field": (
                        f"{const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES}"
                        f"/{const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS}"
                    ),
                    "entity": const.LABEL_CHORE,
                },
            )

        assignee_ids = []
        for assignee_name in assignee_names:
            try:
                assignee_id = get_item_id_or_raise(
                    coordinator,
                    const.ITEM_TYPE_USER,
                    assignee_name,
                    role=const.ROLE_ASSIGNEE,
                )
                assignee_ids.append(assignee_id)
            except HomeAssistantError as err:
                const.LOGGER.warning("Create Chore - assignee lookup failed: %s", err)
                raise

        # Map service fields to DATA_* keys
        data_input = _map_service_to_data_keys(
            dict(call.data), _SERVICE_TO_CHORE_DATA_MAPPING
        )
        # Override assigned assignees with resolved UUIDs
        data_input[const.DATA_CHORE_ASSIGNED_USER_IDS] = assignee_ids

        # Extract due_date for special handling (not passed to build_chore)
        due_date_input = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE)

        # Include due_date in validation if provided
        if due_date_input:
            data_input[const.DATA_CHORE_DUE_DATE] = due_date_input

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_chore_data(
            data_input,
            coordinator.chores_data,
            is_update=False,
            current_chore_id=None,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # Create chore via ChoreManager (handles build, persist, signal)
            chore_dict = coordinator.chore_manager.create_chore(data_input)
            internal_id = str(chore_dict[const.DATA_CHORE_INTERNAL_ID])

            # Handle due_date via chore_manager (respects SHARED/INDEPENDENT)
            # Note: set_due_date handles its own persist
            if due_date_input:
                await coordinator.chore_manager.set_due_date(
                    internal_id, due_date_input, assignee_id=None
                )

            # Create chore status sensor entities for all assigned assignees
            from .sensor import create_chore_entities

            create_chore_entities(coordinator, internal_id)

            const.LOGGER.info(
                "Service created chore '%s' with ID: %s",
                chore_dict[const.DATA_CHORE_NAME],
                internal_id,
            )

            return {const.SERVICE_FIELD_CHORE_CRUD_ID: internal_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
                translation_placeholders=err.placeholders,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_CREATE_CHORE,
        handle_create_chore,
        schema=CREATE_CHORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_update_chore(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.update_chore service call.

        Updates an existing chore using data_builders.build_chore() for consistent
        field handling with the Options Flow UI. Only provided fields are updated.

        Accepts either chore_id OR name to identify the chore:
        - name: User-friendly, looks up ID by name (recommended)
        - id: Direct UUID for advanced automation use

        Supports criteria transitions with automatic field cleanup via Manager.

        Args:
            call: Service call with chore identifier and optional update fields

        Returns:
            Dict with chore_id of the updated chore

        Raises:
            HomeAssistantError: If chore not found, validation fails, or neither
                chore_id nor name provided
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore: either chore_id or name must be provided
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_NAME)

        # If name provided without chore_id, look up the ID
        if not chore_id and chore_name:
            try:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Update Chore: %s", err)
                raise

        # Validate we have a chore_id at this point
        if not chore_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_CHORE_IDENTIFIER,
            )

        if chore_id not in coordinator.chores_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_CHORE_NOT_FOUND,
                translation_placeholders={const.SERVICE_FIELD_CHORE_CRUD_ID: chore_id},
            )

        existing_chore = coordinator.chores_data[chore_id]

        # Build data input, excluding name if it was used for lookup
        service_data = dict(call.data)
        if not call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ID) and chore_name:
            # name was used for lookup, not for renaming
            service_data.pop(const.SERVICE_FIELD_CHORE_CRUD_NAME, None)

        # Resolve assignee names to UUIDs if assignees are being updated.
        # Exception by design: keep reading legacy assigned_user_ids payloads as
        # name lists for backward compatibility with existing automations.
        assignee_names = service_data.get(
            const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES
        )
        if assignee_names is None and (
            const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS in service_data
        ):
            assignee_names = service_data[
                const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS
            ]

        if assignee_names is not None:
            assignee_ids = []
            for assignee_name in assignee_names:
                try:
                    assignee_id = get_item_id_or_raise(
                        coordinator,
                        const.ITEM_TYPE_USER,
                        assignee_name,
                        role=const.ROLE_ASSIGNEE,
                    )
                    assignee_ids.append(assignee_id)
                except HomeAssistantError as err:
                    const.LOGGER.warning(
                        "Update Chore - assignee lookup failed: %s", err
                    )
                    raise
            service_data[const.SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS] = (
                assignee_ids
            )

        # Map service fields to DATA_* keys
        data_input = _map_service_to_data_keys(
            service_data, _SERVICE_TO_CHORE_DATA_MAPPING
        )

        # Extract due_date for special handling
        due_date_input = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_DUE_DATE)

        # Include due_date in validation if provided
        if due_date_input is not None:
            data_input[const.DATA_CHORE_DUE_DATE] = due_date_input

        # For update: merge with existing data for accurate validation
        # (assigned_user_ids may not be in data_input if not being updated)
        validation_data = dict(data_input)
        if const.DATA_CHORE_ASSIGNED_USER_IDS not in validation_data:
            validation_data[const.DATA_CHORE_ASSIGNED_USER_IDS] = existing_chore.get(
                const.DATA_CHORE_ASSIGNED_USER_IDS, []
            )
        # Similarly for other fields needed for combination validation
        for key in (
            const.DATA_CHORE_RECURRING_FREQUENCY,
            const.DATA_CHORE_APPROVAL_RESET_TYPE,
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
            const.DATA_CHORE_COMPLETION_CRITERIA,
        ):
            if key not in validation_data:
                validation_data[key] = existing_chore.get(key)

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_chore_data(
            validation_data,
            coordinator.chores_data,
            is_update=True,
            current_chore_id=chore_id,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # Update chore via ChoreManager (handles build, persist, signal)
            chore_dict = coordinator.chore_manager.update_chore(chore_id, data_input)

            # Handle due_date via chore_manager (respects SHARED/INDEPENDENT)
            # Note: set_due_date handles its own persist
            if due_date_input is not None:
                await coordinator.chore_manager.set_due_date(
                    chore_id, due_date_input, assignee_id=None
                )

            const.LOGGER.info(
                "Service updated chore '%s' with ID: %s",
                chore_dict[const.DATA_CHORE_NAME],
                chore_id,
            )

            return {const.SERVICE_FIELD_CHORE_CRUD_ID: chore_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_UPDATE_CHORE,
        handle_update_chore,
        schema=UPDATE_CHORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_delete_chore(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.delete_chore service call.

        Deletes a chore and cleans up all references.

        Accepts either chore_id OR name to identify the chore:
        - name: User-friendly, looks up ID by name (recommended)
        - id: Direct UUID for advanced automation use

        Args:
            call: Service call with chore identifier

        Returns:
            Dict with chore_id of the deleted chore

        Raises:
            HomeAssistantError: If chore not found or neither
                chore_id nor name provided
        """
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore: either chore_id or name must be provided
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_CRUD_NAME)

        # If name provided without chore_id, look up the ID
        if not chore_id and chore_name:
            try:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Delete Chore: %s", err)
                raise

        # Validate we have a chore_id at this point
        if not chore_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_CHORE_IDENTIFIER,
            )

        # Use Manager-owned CRUD method (handles cleanup and persistence)
        coordinator.chore_manager.delete_chore(chore_id)

        const.LOGGER.info("Service deleted chore with ID: %s", chore_id)

        return {const.SERVICE_FIELD_CHORE_CRUD_ID: chore_id}

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DELETE_CHORE,
        handle_delete_chore,
        schema=DELETE_CHORE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_claim_chore(call: ServiceCall):
        """Handle claiming a chore."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Claim Chore: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        user_id = call.context.user_id
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        chore_name = call.data[const.SERVICE_FIELD_CHORE_NAME]

        # Map assignee_name and chore_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            chore_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Claim Chore: %s", err)
            raise

        # Check if user is authorized
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_PARTICIPATION,
            target_user_id=assignee_id,
        ):
            const.LOGGER.warning(
                "Claim Chore: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_CLAIM_CHORES},
            )

        # Process chore claim via ChoreManager
        await coordinator.chore_manager.claim_chore(
            assignee_id=assignee_id,
            chore_id=chore_id,
            user_name=f"user:{user_id}",
        )

        const.LOGGER.info(
            "Chore '%s' claimed by assignee '%s' by user '%s'",
            chore_name,
            assignee_name,
            user_id,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        handle_claim_chore,
        schema=CLAIM_CHORE_SCHEMA,
    )

    async def handle_approve_chore(call: ServiceCall):
        """Handle approving a claimed chore."""
        entry_id = get_first_choreops_entry(hass)

        if not entry_id:
            const.LOGGER.warning(
                "Approve Chore: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        user_id = call.context.user_id
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        points_awarded = call.data.get(const.SERVICE_FIELD_CHORE_POINTS_AWARDED)

        # Resolve assignee_id (either from assignee_id or assignee_name)
        assignee_id = call.data.get(const.SERVICE_FIELD_USER_ID)
        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)

        if not assignee_id and not assignee_name:
            raise HomeAssistantError(
                "Either assignee_id or assignee_name must be provided"
            )

        if assignee_name and not assignee_id:
            try:
                assignee_id = get_item_id_or_raise(
                    coordinator,
                    const.ITEM_TYPE_USER,
                    assignee_name,
                    role=const.ROLE_ASSIGNEE,
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Approve Chore: %s", err)
                raise

        # Resolve chore_id (either from chore_id or chore_name)
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_NAME)

        if not chore_id and not chore_name:
            raise HomeAssistantError("Either chore_id or chore_name must be provided")

        if chore_name and not chore_id:
            try:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Approve Chore: %s", err)
                raise
            approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        # Ensure IDs are resolved (type safety)
        if not assignee_id:
            raise HomeAssistantError("Could not resolve assignee_id")
        if not chore_id:
            assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)

        # Check if user is authorized
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        ):
            const.LOGGER.warning(
                "Approve Chore: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPROVE_CHORES},
            )

        # Approve chore and assign points
        try:
            await coordinator.chore_manager.approve_chore(
                approver_name,
                assignee_id=assignee_id,
                chore_id=chore_id,
                points_override=points_awarded,
            )
            const.LOGGER.info(
                "Chore '%s' approved for assignee '%s' by approver '%s'. Points Awarded: %s",
                chore_name,
                assignee_name,
                approver_name,
                points_awarded,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPROVE_CHORE,
        handle_approve_chore,
        schema=APPROVE_CHORE_SCHEMA,
    )

    async def handle_disapprove_chore(call: ServiceCall):
        """Handle disapproving a chore."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Disapprove Chore: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        chore_name = call.data[const.SERVICE_FIELD_CHORE_NAME]

        # Map assignee_name and chore_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            chore_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Disapprove Chore: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        ):
            const.LOGGER.warning(
                "Disapprove Chore: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={
                    "action": const.ERROR_ACTION_DISAPPROVE_CHORES
                },
            )

        # Disapprove the chore via ChoreManager
        await coordinator.chore_manager.disapprove_chore(
            approver_name,
            assignee_id=assignee_id,
            chore_id=chore_id,
        )
        const.LOGGER.info(
            "Chore '%s' disapproved for assignee '%s' by approver '%s'",
            chore_name,
            assignee_name,
            approver_name,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DISAPPROVE_CHORE,
        handle_disapprove_chore,
        schema=DISAPPROVE_CHORE_SCHEMA,
    )

    async def handle_set_chore_due_date(call: ServiceCall):
        """Handle setting (or clearing) the due date of a chore.

        For INDEPENDENT chores, optionally specify assignee_id or assignee_name.
        For SHARED chores, assignee_id is ignored (single due date for all assignees).
        """
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Set Chore Due Date: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        chore_name = call.data[const.SERVICE_FIELD_CHORE_NAME]
        due_date_input = call.data.get(const.SERVICE_FIELD_CHORE_DUE_DATE)
        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)
        assignee_id = call.data.get(const.SERVICE_FIELD_USER_ID)

        # Look up the chore by name:
        try:
            chore_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_CHORE, chore_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Set Chore Due Date: %s", err)
            raise

        # If assignee_name is provided, resolve it to assignee_id
        if assignee_name and not assignee_id:
            try:
                assignee_id = get_item_id_or_raise(
                    coordinator,
                    const.ITEM_TYPE_USER,
                    assignee_name,
                    role=const.ROLE_ASSIGNEE,
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Set Chore Due Date: %s", err)
                raise

        # Validate that if assignee_id is provided, the chore is INDEPENDENT and assignee is assigned
        if assignee_id:
            chore_info: ChoreData = cast(
                "ChoreData", coordinator.chores_data.get(chore_id, {})
            )
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            # Reject assignee_id for SHARED and SHARED_FIRST chores
            # (they use chore-level due dates, not per-assignee)
            if completion_criteria in (
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            ):
                const.LOGGER.warning(
                    "Set Chore Due Date: Cannot specify assignee_id for %s chore '%s'",
                    completion_criteria,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_SHARED_CHORE_ASSIGNEE,
                    translation_placeholders={"chore_name": str(chore_name)},
                )

            assigned_user_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
            if assignee_id not in assigned_user_ids:
                const.LOGGER.warning(
                    "Set Chore Due Date: Assignee '%s' not assigned to chore '%s'",
                    assignee_id,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": str(assignee_name or assignee_id),
                        "assignee": str(chore_name),
                    },
                )

        if due_date_input:
            try:
                # Convert the provided date to UTC-aware datetime
                due_dt_raw = dt_parse(
                    due_date_input,
                    return_type=const.HELPER_RETURN_DATETIME_UTC,
                )
                # Ensure due_dt is a datetime object (not date or str)
                if due_dt_raw and not isinstance(due_dt_raw, datetime):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_INVALID_DATE_FORMAT,
                    )
                due_dt: datetime | None = due_dt_raw  # type: ignore[assignment]
                if (
                    due_dt
                    and isinstance(due_dt, datetime)
                    and due_dt < dt_util.utcnow()
                ):
                    raise HomeAssistantError(
                        translation_domain=const.DOMAIN,
                        translation_key=const.TRANS_KEY_ERROR_DATE_IN_PAST,
                    )

            except HomeAssistantError as err:
                const.LOGGER.error(
                    "Set Chore Due Date: Invalid due date '%s': %s",
                    due_date_input,
                    err,
                )
                raise

            # Update the chore’s due_date:
            await coordinator.chore_manager.set_due_date(chore_id, due_dt, assignee_id)
            const.LOGGER.info(
                "Set due date for chore '%s' (ID: %s) to %s",
                chore_name,
                chore_id,
                due_date_input,
            )
        else:
            # Clear the due date by setting it to None
            await coordinator.chore_manager.set_due_date(chore_id, None, assignee_id)
            const.LOGGER.info(
                "Cleared due date for chore '%s' (ID: %s)", chore_name, chore_id
            )

        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SET_CHORE_DUE_DATE,
        handle_set_chore_due_date,
        schema=SET_CHORE_DUE_DATE_SCHEMA,
    )

    async def handle_skip_chore_due_date(call: ServiceCall) -> None:
        """Handle skipping the due date on a chore by rescheduling it to the next due date.

        For INDEPENDENT chores, you can optionally specify assignee_name or assignee_id.
        For SHARED chores, you must not specify a assignee.
        """
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Skip Chore Due Date: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Get parameters: either chore_id or chore_name must be provided.
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_NAME)

        try:
            if not chore_id and chore_name:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Skip Chore Due Date: %s", err)
            raise

        if not chore_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_CHORE,
            )

        # Get assignee parameters (for INDEPENDENT chores only)
        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)
        assignee_id = call.data.get(const.SERVICE_FIELD_USER_ID)

        # Resolve assignee_name to assignee_id if provided
        if assignee_name and not assignee_id:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )

        # Validate assignee_id (if provided)
        if assignee_id:
            chore_info: ChoreData = cast(
                "ChoreData", coordinator.chores_data.get(chore_id, {})
            )
            completion_criteria = chore_info.get(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            )
            # Reject assignee_id for SHARED and SHARED_FIRST chores
            # (they use chore-level due dates, not per-assignee)
            if completion_criteria in (
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            ):
                const.LOGGER.warning(
                    "Skip Chore Due Date: Cannot specify assignee_id for %s chore '%s'",
                    completion_criteria,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_SHARED_CHORE_ASSIGNEE,
                    translation_placeholders={"chore_name": str(chore_name)},
                )

            assigned_user_ids = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
            if assignee_id not in assigned_user_ids:
                const.LOGGER.warning(
                    "Skip Chore Due Date: Assignee '%s' not assigned to chore '%s'",
                    assignee_id,
                    chore_name,
                )
                raise HomeAssistantError(
                    translation_domain=const.DOMAIN,
                    translation_key=const.TRANS_KEY_ERROR_NOT_ASSIGNED,
                    translation_placeholders={
                        "entity": str(assignee_name or assignee_id),
                        "assignee": str(chore_name),
                    },
                )

        # Record miss if requested (for INDEPENDENT chores, requires assignee_id)
        mark_as_missed = call.data.get(const.SERVICE_FIELD_MARK_AS_MISSED, False)
        if mark_as_missed:
            if assignee_id:
                # INDEPENDENT chore - record miss for specific assignee
                coordinator.chore_manager._record_chore_missed(assignee_id, chore_id)
            else:
                # SHARED chore - record miss for all assigned assignees
                chore_info = cast(
                    "ChoreData", coordinator.chores_data.get(chore_id, {})
                )
                assigned_user_ids = chore_info.get(
                    const.DATA_CHORE_ASSIGNED_USER_IDS, []
                )
                for assigned_assignee_id in assigned_user_ids:
                    coordinator.chore_manager._record_chore_missed(
                        assigned_assignee_id, chore_id
                    )

        await coordinator.chore_manager.skip_due_date(chore_id, assignee_id)
        assignee_context = (
            f" for assignee '{assignee_name or assignee_id}'" if assignee_id else ""
        )
        const.LOGGER.info(
            "Skipped due date for chore '%s' (ID: %s)%s",
            chore_name or chore_id,
            chore_id,
            assignee_context,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SKIP_CHORE_DUE_DATE,
        handle_skip_chore_due_date,
        schema=SKIP_CHORE_DUE_DATE_SCHEMA,
    )

    # ==========================================================================
    # REWARD SERVICE HANDLERS
    # ==========================================================================

    async def handle_create_reward(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.create_reward service call.

        Creates a new reward using data_builders.build_reward() for consistent
        field handling with the Options Flow UI.

        Args:
            call: Service call with name, cost, description, icon, labels

        Returns:
            Dict with reward_id of the created reward

        Raises:
            HomeAssistantError: If no coordinator available or validation fails
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Create Reward: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Map service fields to DATA_* keys for data_builders
        data_input = _map_service_to_data_keys(
            dict(call.data), _SERVICE_TO_REWARD_DATA_MAPPING
        )

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_reward_data(
            data_input,
            coordinator.rewards_data,
            is_update=False,
            current_reward_id=None,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # Create reward via RewardManager (handles build, persist, signal)
            reward_dict = coordinator.reward_manager.create_reward(data_input)
            internal_id = str(reward_dict[const.DATA_REWARD_INTERNAL_ID])

            const.LOGGER.info(
                "Service created reward '%s' with ID: %s",
                reward_dict[const.DATA_REWARD_NAME],
                internal_id,
            )

            return {const.SERVICE_FIELD_REWARD_ID: internal_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
                translation_placeholders=err.placeholders,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_CREATE_REWARD,
        handle_create_reward,
        schema=CREATE_REWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_update_reward(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.update_reward service call.

        Updates an existing reward using data_builders.build_reward() for consistent
        field handling with the Options Flow UI. Only provided fields are updated.

        Accepts either id OR name to identify the reward:
        - name: User-friendly, looks up ID by name (recommended)
        - id: Direct UUID for advanced automation use

        Args:
            call: Service call with reward identifier and optional update fields

        Returns:
            Dict with reward_id of the updated reward

        Raises:
            HomeAssistantError: If reward not found, validation fails, or neither
                id nor name provided
        """
        from . import data_builders as db
        from .data_builders import EntityValidationError

        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve reward: either id or name must be provided
        reward_id = call.data.get(const.SERVICE_FIELD_REWARD_CRUD_ID)
        reward_name = call.data.get(const.SERVICE_FIELD_REWARD_CRUD_NAME)

        # If name provided without id, look up the ID
        if not reward_id and reward_name:
            try:
                reward_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_REWARD, reward_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Update Reward: %s", err)
                raise

        # Validate we have a reward_id at this point
        if not reward_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_REWARD_IDENTIFIER,
            )

        if reward_id not in coordinator.rewards_data:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_REWARD_NOT_FOUND,
                translation_placeholders={const.SERVICE_FIELD_REWARD_ID: reward_id},
            )

        # Build data input, excluding reward_name if it was used for lookup
        # (don't treat lookup name as a rename request)
        service_data = dict(call.data)
        if not call.data.get(const.SERVICE_FIELD_REWARD_ID) and reward_name:
            # reward_name was used for lookup, not for renaming
            # Only include it in data_input if there's ALSO a reward_id (explicit rename)
            service_data.pop(const.SERVICE_FIELD_REWARD_NAME, None)

        data_input = _map_service_to_data_keys(
            service_data, _SERVICE_TO_REWARD_DATA_MAPPING
        )

        # Validate using shared validation (single source of truth)
        validation_errors = db.validate_reward_data(
            data_input,
            coordinator.rewards_data,
            is_update=True,
            current_reward_id=reward_id,
        )
        if validation_errors:
            # Get first error and raise
            error_field, error_key = next(iter(validation_errors.items()))
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=error_key,
            )

        try:
            # Update reward via RewardManager (handles build, persist, signal)
            reward_dict = coordinator.reward_manager.update_reward(
                reward_id, data_input
            )

            const.LOGGER.info(
                "Service updated reward '%s' with ID: %s",
                reward_dict[const.DATA_REWARD_NAME],
                reward_id,
            )

            return {const.SERVICE_FIELD_REWARD_ID: reward_id}

        except EntityValidationError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=err.translation_key,
            ) from err

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_UPDATE_REWARD,
        handle_update_reward,
        schema=UPDATE_REWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_delete_reward(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.delete_reward service call.

        Deletes a reward and cleans up all references.

        Accepts either id OR name to identify the reward:
        - name: User-friendly, looks up ID by name (recommended)
        - id: Direct UUID for advanced automation use

        Args:
            call: Service call with reward identifier

        Returns:
            Dict with reward_id of the deleted reward

        Raises:
            HomeAssistantError: If reward not found or neither
                id nor name provided
        """
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve reward: either id or name must be provided
        reward_id = call.data.get(const.SERVICE_FIELD_REWARD_CRUD_ID)
        reward_name = call.data.get(const.SERVICE_FIELD_REWARD_CRUD_NAME)

        # If name provided without id, look up the ID
        if not reward_id and reward_name:
            try:
                reward_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_REWARD, reward_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Delete Reward: %s", err)
                raise

        # Validate we have a reward_id at this point
        if not reward_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MISSING_REWARD_IDENTIFIER,
            )

        # Use Manager-owned CRUD method (handles cleanup and persistence)
        coordinator.reward_manager.delete_reward(reward_id)

        const.LOGGER.info("Service deleted reward with ID: %s", reward_id)

        return {const.SERVICE_FIELD_REWARD_ID: reward_id}

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DELETE_REWARD,
        handle_delete_reward,
        schema=DELETE_REWARD_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def handle_redeem_reward(call: ServiceCall):
        """Handle redeeming a reward (claiming without deduction)."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Redeem Reward: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        reward_name = call.data[const.SERVICE_FIELD_REWARD_NAME]

        # Map assignee_name and reward_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            reward_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_REWARD, reward_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Redeem Reward: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        ):
            const.LOGGER.warning(
                "Redeem Reward: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_REDEEM_REWARDS},
            )

        # Check if assignee has enough points
        assignee_info = coordinator.assignees_data.get(assignee_id)
        reward_info = coordinator.rewards_data.get(reward_id)
        if not assignee_info:
            const.LOGGER.warning("Redeem Reward: Assignee not found")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_ASSIGNEE,
                    "name": assignee_name or "unknown",
                },
            )
        if not reward_info:
            const.LOGGER.warning("Redeem Reward: Reward not found")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_FOUND,
                translation_placeholders={
                    "entity_type": const.LABEL_REWARD,
                    "name": reward_name or "unknown",
                },
            )

        if assignee_info[const.DATA_USER_POINTS] < reward_info.get(
            const.DATA_REWARD_COST, const.DEFAULT_ZERO
        ):
            const.LOGGER.warning(
                "Redeem Reward: %s", const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INSUFFICIENT_POINTS,
                translation_placeholders={
                    "assignee_name": assignee_name,
                    "reward_name": reward_name,
                },
            )

        # Process reward claim without deduction
        try:
            await coordinator.reward_manager.redeem(
                approver_name,
                assignee_id=assignee_id,
                reward_id=reward_id,
            )
            const.LOGGER.info(
                "Reward '%s' claimed by assignee '%s' and pending approval by approver '%s'",
                reward_name,
                assignee_name,
                approver_name,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_REDEEM_REWARD,
        handle_redeem_reward,
        schema=REDEEM_REWARD_SCHEMA,
    )

    async def handle_approve_reward(call: ServiceCall):
        """Handle approving a reward claimed by a assignee."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Approve Reward: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        user_id = call.context.user_id
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        reward_name = call.data[const.SERVICE_FIELD_REWARD_NAME]

        # Map assignee_name and reward_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            reward_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_REWARD, reward_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Approve Reward: %s", err)
            raise

        # Check if user is authorized
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        ):
            const.LOGGER.warning(
                "Approve Reward: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPROVE_REWARDS},
            )

        # Approve reward redemption and deduct points
        # Extract optional cost_override (None if not provided)
        cost_override = call.data.get(const.SERVICE_FIELD_REWARD_COST_OVERRIDE)

        try:
            await coordinator.reward_manager.approve(
                approver_name,
                assignee_id=assignee_id,
                reward_id=reward_id,
                cost_override=cost_override,
            )
            const.LOGGER.info(
                "Reward '%s' approved for assignee '%s' by approver '%s'%s",
                reward_name,
                assignee_name,
                approver_name,
                f" (cost override: {cost_override})"
                if cost_override is not None
                else "",
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPROVE_REWARD,
        handle_approve_reward,
        schema=APPROVE_REWARD_SCHEMA,
    )

    async def handle_disapprove_reward(call: ServiceCall):
        """Handle disapproving a reward."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Disapprove Reward: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        reward_name = call.data[const.SERVICE_FIELD_REWARD_NAME]

        # Map assignee_name and reward_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            reward_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_REWARD, reward_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Disapprove Reward: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        ):
            const.LOGGER.warning(
                "Disapprove Reward: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={
                    "action": const.ERROR_ACTION_DISAPPROVE_REWARDS
                },
            )

        # Disapprove the reward
        await coordinator.reward_manager.disapprove(
            approver_name,
            assignee_id=assignee_id,
            reward_id=reward_id,
        )
        const.LOGGER.info(
            "Reward '%s' disapproved for assignee '%s' by approver '%s'",
            reward_name,
            assignee_name,
            approver_name,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DISAPPROVE_REWARD,
        handle_disapprove_reward,
        schema=DISAPPROVE_REWARD_SCHEMA,
    )

    # NOTE: reset_rewards service REMOVED - superseded by reset_transactional_data
    # with scope="assignee" or scope="global" and item_type="rewards"

    # ==========================================================================
    # PENALTY SERVICE HANDLERS
    # ==========================================================================

    async def handle_apply_penalty(call: ServiceCall):
        """Handle applying a penalty."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Apply Penalty: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        penalty_name = call.data[const.SERVICE_FIELD_PENALTY_NAME]

        # Map assignee_name and penalty_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            penalty_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_PENALTY, penalty_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Apply Penalty: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_MANAGEMENT,
        ):
            const.LOGGER.warning(
                "Apply Penalty: %s", const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION
            )
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPLY_PENALTIES},
            )

        # Apply penalty
        try:
            await coordinator.economy_manager.apply_penalty(
                approver_name,
                assignee_id=assignee_id,
                penalty_id=penalty_id,
            )
            const.LOGGER.info(
                "Penalty '%s' applied for assignee '%s' by approver '%s'",
                penalty_name,
                assignee_name,
                approver_name,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPLY_PENALTY,
        handle_apply_penalty,
        schema=APPLY_PENALTY_SCHEMA,
    )

    # NOTE: reset_penalties service REMOVED - superseded by reset_transactional_data
    # with scope="assignee" or scope="global" and item_type="penalties"

    # ==========================================================================
    # BONUS SERVICE HANDLERS
    # ==========================================================================

    async def handle_apply_bonus(call: ServiceCall):
        """Handle applying a bonus."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Apply Bonus: %s", const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)
        approver_name = call.data[const.SERVICE_FIELD_APPROVER_NAME]
        assignee_name = call.data[const.SERVICE_FIELD_USER_NAME]
        bonus_name = call.data[const.SERVICE_FIELD_BONUS_NAME]

        # Map assignee_name and bonus_name to internal_ids
        try:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                assignee_name,
                role=const.ROLE_ASSIGNEE,
            )
            bonus_id = get_item_id_or_raise(
                coordinator, const.ITEM_TYPE_BONUS, bonus_name
            )
        except HomeAssistantError as err:
            const.LOGGER.warning("Apply Bonus: %s", err)
            raise

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_MANAGEMENT,
        ):
            const.LOGGER.warning("Apply Bonus: User not authorized")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION,
                translation_placeholders={"action": const.ERROR_ACTION_APPLY_BONUSES},
            )

        # Apply bonus
        try:
            await coordinator.economy_manager.apply_bonus(
                approver_name, assignee_id=assignee_id, bonus_id=bonus_id
            )
            const.LOGGER.info(
                "Bonus '%s' applied for assignee '%s' by approver '%s'",
                bonus_name,
                assignee_name,
                approver_name,
            )
            await coordinator.async_request_refresh()
        except HomeAssistantError:  # pylint: disable=try-except-raise  # Log before re-raise
            raise

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_APPLY_BONUS,
        handle_apply_bonus,
        schema=APPLY_BONUS_SCHEMA,
    )

    # NOTE: reset_bonuses service REMOVED - superseded by reset_transactional_data
    # with scope="assignee" or scope="global" and item_type="bonuses"

    # ==========================================================================
    # BADGE SERVICE HANDLERS
    # ==========================================================================

    async def handle_remove_awarded_badges(call: ServiceCall):
        """Handle removing awarded badges."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Remove Awarded Badges: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)
        badge_name = call.data.get(const.SERVICE_FIELD_BADGE_NAME)

        # Check if user is authorized
        user_id = call.context.user_id
        if user_id and not await is_user_authorized_for_action(
            hass,
            user_id,
            AUTH_ACTION_MANAGEMENT,
        ):
            const.LOGGER.warning("Remove Awarded Badges: User not authorized.")
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL,
                translation_placeholders={"action": const.ERROR_ACTION_REMOVE_BADGES},
            )

        # Log action based on parameters provided
        if assignee_name is None and badge_name is None:
            const.LOGGER.info("Removing all badges for all assignees.")
        elif assignee_name is None:
            const.LOGGER.info("Removing badge '%s' for all assignees.", badge_name)
        elif badge_name is None:
            const.LOGGER.info("Removing all badges for assignee '%s'.", assignee_name)
        else:
            const.LOGGER.info(
                "Removing badge '%s' for assignee '%s'.", badge_name, assignee_name
            )

        # Remove awarded badges via GamificationManager
        coordinator.gamification_manager.remove_awarded_badges(
            assignee_name,
            badge_name,
        )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_REMOVE_AWARDED_BADGES,
        handle_remove_awarded_badges,
        schema=REMOVE_AWARDED_BADGES_SCHEMA,
    )

    # ==========================================================================
    # ROTATION MANAGEMENT SERVICE HANDLERS (Phase 3 Step 7 - v0.5.0)
    # ==========================================================================

    async def handle_set_rotation_turn(call: ServiceCall) -> None:
        """Set rotation turn to a specific assignee."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning("Set Rotation Turn: No ChoreOps entry found")
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore_id (either from chore_id or chore_name)
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_NAME)

        if not chore_id and not chore_name:
            raise HomeAssistantError("Either chore_id or chore_name must be provided")

        if chore_name and not chore_id:
            try:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Set Rotation Turn: %s", err)
                raise

        if not chore_id:
            raise HomeAssistantError("Could not resolve chore_id")

        # Resolve assignee_id (either from assignee_id or assignee_name)
        assignee_id = call.data.get(const.SERVICE_FIELD_USER_ID)
        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)

        if not assignee_id and not assignee_name:
            raise HomeAssistantError(
                "Either assignee_id or assignee_name must be provided"
            )

        if assignee_name and not assignee_id:
            try:
                assignee_id = get_item_id_or_raise(
                    coordinator,
                    const.ITEM_TYPE_USER,
                    assignee_name,
                    role=const.ROLE_ASSIGNEE,
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Set Rotation Turn: %s", err)
                raise

        if not assignee_id:
            raise HomeAssistantError("Could not resolve assignee_id")

        # Delegate to ChoreManager
        await coordinator.chore_manager.set_rotation_turn(chore_id, assignee_id)

        # Refresh coordinator to update entity states
        await coordinator.async_request_refresh()

    async def handle_reset_rotation(call: ServiceCall) -> None:
        """Reset rotation to first assigned assignee."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning("Reset Rotation: No ChoreOps entry found")
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore_id (either from chore_id or chore_name)
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_NAME)

        if not chore_id and not chore_name:
            raise HomeAssistantError("Either chore_id or chore_name must be provided")

        if chore_name and not chore_id:
            try:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Reset Rotation: %s", err)
                raise

        if not chore_id:
            raise HomeAssistantError("Could not resolve chore_id")

        # Delegate to ChoreManager
        await coordinator.chore_manager.reset_rotation(chore_id)

        # Refresh coordinator to update entity states
        await coordinator.async_request_refresh()

    async def handle_open_rotation_cycle(call: ServiceCall) -> None:
        """Open rotation cycle - allow any assignee to claim once."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning("Open Rotation Cycle: No ChoreOps entry found")
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Resolve chore_id (either from chore_id or chore_name)
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_NAME)

        if not chore_id and not chore_name:
            raise HomeAssistantError("Either chore_id or chore_name must be provided")

        if chore_name and not chore_id:
            try:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
            except HomeAssistantError as err:
                const.LOGGER.warning("Open Rotation Cycle: %s", err)
                raise

        if not chore_id:
            raise HomeAssistantError("Could not resolve chore_id")

        # Delegate to ChoreManager
        await coordinator.chore_manager.open_rotation_cycle(chore_id)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SET_ROTATION_TURN,
        handle_set_rotation_turn,
        schema=SET_ROTATION_TURN_SCHEMA,
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_ROTATION,
        handle_reset_rotation,
        schema=RESET_ROTATION_SCHEMA,
    )

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_OPEN_ROTATION_CYCLE,
        handle_open_rotation_cycle,
        schema=OPEN_ROTATION_CYCLE_SCHEMA,
    )

    # ==========================================================================
    # REPORTING SERVICE HANDLERS
    # ==========================================================================

    async def handle_generate_activity_report(call: ServiceCall) -> dict[str, Any]:
        """Handle assigneeschores.generate_activity_report service call."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)
        assignee_id: str | None = None
        if assignee_name:
            assignee_id = get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                str(assignee_name),
                role=const.ROLE_ASSIGNEE,
            )

        try:
            range_result = report_helpers.resolve_report_range(
                mode=const.REPORT_RANGE_MODE_LAST_7_DAYS,
                start_date=None,
                end_date=None,
                timezone_name=hass.config.time_zone,
            )
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=const.DOMAIN,
                translation_key=const.TRANS_KEY_ERROR_INVALID_DATE_FORMAT,
            ) from err

        report_language = _resolve_report_language(
            coordinator.assignees_data,
            assignee_id,
            cast(
                "str | None",
                call.data.get(const.SERVICE_FIELD_REPORT_LANGUAGE),
            ),
        )
        report_output_format = cast(
            "str",
            call.data.get(
                const.SERVICE_FIELD_REPORT_OUTPUT_FORMAT,
                const.REPORT_OUTPUT_FORMAT_MARKDOWN,
            ),
        )

        report_response = report_helpers.build_activity_report(
            assignees_data=coordinator.assignees_data,
            range_result=range_result,
            assignee_id=assignee_id,
            report_title=cast(
                "str | None",
                call.data.get(const.SERVICE_FIELD_REPORT_TITLE),
            ),
            report_style=const.REPORT_STYLE_ASSIGNEE,
            stats_manager=coordinator.statistics_manager,
            report_translations=await translation_helpers.load_report_translation(
                hass,
                language=report_language,
            ),
            include_supplemental=False,
        )

        html_body: str | None = None
        if report_output_format in {
            const.REPORT_OUTPUT_FORMAT_HTML,
            const.REPORT_OUTPUT_FORMAT_BOTH,
        }:
            html_body = report_helpers.convert_markdown_to_html(
                report_response["markdown"]
            )
            report_response["html"] = html_body

        notify_service = cast(
            "str | None",
            call.data.get(const.SERVICE_FIELD_REPORT_NOTIFY_SERVICE),
        )
        notify_attempted = notify_service is not None and notify_service.strip() != ""
        delivered = False

        if notify_attempted and notify_service is not None:
            notify_service_name = notify_service.strip()
            if "." in notify_service_name:
                notify_domain, notify_action = notify_service_name.split(".", 1)
            else:
                notify_domain, notify_action = "notify", notify_service_name

            if hass.services.has_service(notify_domain, notify_action):
                try:
                    notify_message = _strip_yaml_block_wrapper(
                        report_response["markdown"]
                    )
                    notify_payload: dict[str, Any] = {
                        "title": call.data.get(const.SERVICE_FIELD_REPORT_TITLE)
                        or "ChoreOps Activity Report",
                        "message": notify_message,
                    }

                    if (
                        report_output_format
                        in {
                            const.REPORT_OUTPUT_FORMAT_HTML,
                            const.REPORT_OUTPUT_FORMAT_BOTH,
                        }
                        and html_body is not None
                    ):
                        notify_payload["data"] = {
                            "html": _strip_yaml_block_wrapper(html_body)
                        }

                    await hass.services.async_call(
                        notify_domain,
                        notify_action,
                        notify_payload,
                        blocking=True,
                    )
                    delivered = True
                except HomeAssistantError as err:
                    const.LOGGER.warning(
                        "Report notify delivery failed for %s: %s",
                        notify_service_name,
                        err,
                    )
            else:
                const.LOGGER.warning(
                    "Report notify service not found: %s",
                    notify_service_name,
                )

        delivery_status: dict[str, Any] = {
            "notify_attempted": notify_attempted,
            "notify_service": notify_service,
            "delivered": delivered,
        }

        assignee_ready_report = report_response["markdown"]
        if (
            report_output_format == const.REPORT_OUTPUT_FORMAT_HTML
            and html_body is not None
        ):
            assignee_ready_report = html_body
        assignee_ready_report = _strip_yaml_block_wrapper(assignee_ready_report)

        response_payload: dict[str, Any] = {
            "report": assignee_ready_report,
            "output_format": report_output_format,
            "report_language": report_language,
            "report_window_days": 7,
            "delivery": delivery_status,
        }
        if report_output_format == const.REPORT_OUTPUT_FORMAT_BOTH:
            response_payload["markdown"] = report_response["markdown"]
            if html_body is not None:
                response_payload["html"] = html_body

        return response_payload

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_GENERATE_ACTIVITY_REPORT,
        handle_generate_activity_report,
        schema=GENERATE_ACTIVITY_REPORT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    def _resolve_report_language(
        assignees_data: dict[str, Any],
        assignee_id: str | None,
        requested_language: str | None,
    ) -> str:
        """Resolve report language with explicit > assignee preference > default order."""
        if requested_language:
            return requested_language

        if assignee_id is not None:
            assignee_info = assignees_data.get(assignee_id, {})
            if isinstance(assignee_info, dict):
                preferred = assignee_info.get(const.DATA_USER_DASHBOARD_LANGUAGE)
                if isinstance(preferred, str) and preferred:
                    return preferred

        return const.DEFAULT_REPORT_LANGUAGE

    def _strip_yaml_block_wrapper(message: str) -> str:
        """Strip top-level YAML block scalar wrapper from message text when present."""
        lines = message.splitlines()
        if not lines:
            return message

        first_line = lines[0].strip()
        if ":" not in first_line or not first_line.endswith(("|", "|-", "|+")):
            return message

        payload_lines = lines[1:]
        if not payload_lines:
            return ""

        if all(line.startswith("  ") or line == "" for line in payload_lines):
            payload_lines = [line.removeprefix("  ") for line in payload_lines]

        return "\n".join(payload_lines).lstrip("\n")

    # ==========================================================================
    # RESET SERVICE HANDLERS
    # ==========================================================================

    async def handle_reset_chores_to_pending_state(_call: ServiceCall):
        """Handle manually resetting all chores to pending, clearing claims/approvals."""
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Reset Chores To Pending State: No ChoreOps entry found"
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Delegate to ChoreManager
        await coordinator.chore_manager.reset_all_chore_states_to_pending()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_CHORES_TO_PENDING_STATE,
        handle_reset_chores_to_pending_state,
        schema=RESET_CHORES_TO_PENDING_STATE_SCHEMA,
    )

    async def handle_reset_overdue_chores(call: ServiceCall) -> None:
        """Handle resetting overdue chores."""

        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning(
                "Reset Overdue Chores: %s",
                const.TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND,
            )
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Get parameters
        chore_id = call.data.get(const.SERVICE_FIELD_CHORE_ID)
        chore_name = call.data.get(const.SERVICE_FIELD_CHORE_NAME)
        assignee_name = call.data.get(const.SERVICE_FIELD_USER_NAME)

        # Map names to IDs (optional parameters)
        try:
            if not chore_id and chore_name:
                chore_id = get_item_id_or_raise(
                    coordinator, const.ITEM_TYPE_CHORE, chore_name
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Overdue Chores: %s", err)
            raise

        assignee_id: str | None = None
        try:
            if assignee_name:
                assignee_id = get_item_id_or_raise(
                    coordinator,
                    const.ITEM_TYPE_USER,
                    assignee_name,
                    role=const.ROLE_ASSIGNEE,
                )
        except HomeAssistantError as err:
            const.LOGGER.warning("Reset Overdue Chores: %s", err)
            raise

        await coordinator.chore_manager.reset_overdue_chores(
            chore_id=chore_id, assignee_id=assignee_id
        )

        const.LOGGER.info(
            "Reset overdue chores (chore_id=%s, assignee_id=%s)", chore_id, assignee_id
        )

        await coordinator.async_request_refresh()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_OVERDUE_CHORES,
        handle_reset_overdue_chores,
        schema=RESET_OVERDUE_CHORES_SCHEMA,
    )

    # ==========================================================================
    # UNIFIED DATA RESET SERVICE (V2)
    # ==========================================================================

    async def handle_reset_transactional_data(call: ServiceCall) -> None:
        """Handle unified data reset service.

        Delegates to SystemManager.orchestrate_data_reset() for validation,
        backup creation, and domain manager orchestration.

        Args:
            call: Service call with confirm_destructive, scope, assignee_name,
                  item_type, item_name fields
        """
        entry_id = get_first_choreops_entry(hass)
        if not entry_id:
            const.LOGGER.warning("Reset Transactional Data: No ChoreOps entry found")
            return

        coordinator = _get_coordinator_by_entry_id(hass, entry_id)

        # Delegate to SystemManager for orchestration
        # SystemManager handles: validation, backup, manager calls, notification
        await coordinator.system_manager.orchestrate_data_reset(dict(call.data))

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_RESET_TRANSACTIONAL_DATA,
        handle_reset_transactional_data,
        schema=RESET_TRANSACTIONAL_DATA_SCHEMA,
    )

    const.LOGGER.info("ChoreOps services have been registered successfully")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister ChoreOps services when unloading the integration."""
    services = [
        const.SERVICE_CLAIM_CHORE,
        const.SERVICE_APPROVE_CHORE,
        const.SERVICE_CREATE_CHORE,
        const.SERVICE_CREATE_REWARD,
        const.SERVICE_DELETE_CHORE,
        const.SERVICE_DELETE_REWARD,
        const.SERVICE_DISAPPROVE_CHORE,
        const.SERVICE_REDEEM_REWARD,
        const.SERVICE_DISAPPROVE_REWARD,
        const.SERVICE_APPLY_PENALTY,
        const.SERVICE_APPLY_BONUS,
        const.SERVICE_APPROVE_REWARD,
        const.SERVICE_RESET_CHORES_TO_PENDING_STATE,  # Renamed from SERVICE_RESET_ALL_CHORES
        const.SERVICE_RESET_OVERDUE_CHORES,
        const.SERVICE_RESET_TRANSACTIONAL_DATA,
        # NOTE: SERVICE_RESET_PENALTIES, SERVICE_RESET_BONUSES, SERVICE_RESET_REWARDS
        # removed in v0.6.0 - superseded by SERVICE_RESET_TRANSACTIONAL_DATA
        const.SERVICE_UPDATE_CHORE,
        const.SERVICE_UPDATE_REWARD,
        const.SERVICE_REMOVE_AWARDED_BADGES,
        const.SERVICE_SET_CHORE_DUE_DATE,
        const.SERVICE_SKIP_CHORE_DUE_DATE,
        # Phase 3 Step 7 - Rotation management services (v0.5.0)
        const.SERVICE_SET_ROTATION_TURN,
        const.SERVICE_RESET_ROTATION,
        const.SERVICE_OPEN_ROTATION_CYCLE,
        const.SERVICE_GENERATE_ACTIVITY_REPORT,
    ]

    for service in services:
        if hass.services.has_service(const.DOMAIN, service):
            hass.services.async_remove(const.DOMAIN, service)

    const.LOGGER.info("ChoreOps services have been unregistered")
