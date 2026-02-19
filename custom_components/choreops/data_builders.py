"""Entity lifecycle management helpers.

This module is the SINGLE SOURCE OF TRUTH for:
- Entity field defaults
- Business logic validation
- Complete entity structure building
- CFOF→DATA key mapping (where still needed)

## Key Concepts (v0.5.0+)

### CFOF Key Alignment (Phase 6)
Most CFOF_* constant values are now aligned with DATA_* values:
- CFOF_*_INPUT_NAME = "name" = DATA_*_NAME (for assignees, approvers, rewards, etc.)
- This means user_input from forms can often be passed directly to build_*() functions

### Build Functions
Each entity type has a `build_<entity>()` function that:
- Takes user_input or mapped data (DATA_* keys)
- Generates internal_id (UUID) for new entities
- Sets timestamps (created_at, updated_at)
- Applies field defaults
- Returns complete entity dict ready for storage

### Validation Functions
Each entity type has a `validate_<entity>_data()` function that:
- Takes data with DATA_* keys
- Performs business rule validation
- Returns dict of errors (empty if valid)
- Is called by flow_helpers.validate_*_inputs() (UI layer)

### Mapping Functions (Legacy/Complex Only)
For entities with complex transformations (chores, badges), mapping functions exist:
- `map_cfof_to_chore_data()` - Handles daily_multi_times parsing
- Achievements/Challenges mappings retained for documentation/filtering

Consumers:
- options_flow.py (UI entity management)
- services.py (programmatic entity management)
- coordinator.py (thin storage wrapper)

See Also:
- flow_helpers.py: UI-specific validation and schema building
- type_defs.py: TypedDict definitions for type safety
"""

from __future__ import annotations

import datetime
from typing import Any, cast
import uuid

from . import const
from .type_defs import AssigneeData, BadgeData, ChoreData, RewardData, UserData
from .utils.dt_utils import dt_now_utc, dt_parse

# ==============================================================================
# HELPER FUNCTIONS FOR FIELD NORMALIZATION
# ==============================================================================


def _normalize_list_field(value: Any) -> list[Any]:
    """Normalize a field that should be a list.

    Handles cases where the value might be:
    - Already a list → return as-is
    - None → return empty list
    - Other types → return as list

    This prevents bugs like list("08:00") → ['0', '8', ':', '0', '0']
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    # For strings, don't iterate character by character
    # This shouldn't happen for list fields, but be safe
    if isinstance(value, str):
        return [value] if value else []
    return list(value) if value else []


def _normalize_dict_field(value: Any) -> dict[str, Any]:
    """Normalize a field that should be a dict.

    Handles cases where the value might be:
    - Already a dict → return as-is
    - None → return empty dict
    """
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _pass_through_field(value: Any, default: Any = None) -> Any:
    """Pass field value through as-is, returning default if None.

    For fields that can be various types (string, list, etc.) and should
    not be normalized.
    """
    return value if value is not None else default


def _normalize_name_field(raw_name: Any) -> str:
    """Normalize user name values for validation and storage."""
    return str(raw_name).strip() if raw_name else ""


def _resolve_user_input_field(
    user_input: dict[str, Any],
    existing: dict[str, Any] | None,
    cfof_key: str,
    data_key: str,
    default: Any,
) -> Any:
    """Resolve field value using precedence: user_input > existing > default."""
    if cfof_key in user_input:
        return user_input[cfof_key]
    if existing is not None:
        return existing.get(data_key, default)
    return default


def _normalize_user_select_value(value: Any) -> str:
    """Normalize selector sentinel values used by user-profile forms."""
    if value in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
        return ""
    return str(value) if value else ""


def _resolve_or_create_internal_id(existing: dict[str, Any] | None) -> str:
    """Resolve existing internal ID or generate a new UUID."""
    if existing is None:
        return str(uuid.uuid4())
    return str(existing.get(const.DATA_USER_INTERNAL_ID, str(uuid.uuid4())))


# ==============================================================================
# EXCEPTIONS
# ==============================================================================


class EntityValidationError(Exception):
    """Validation error with field-specific information for form highlighting.

    This exception is raised when business logic validation fails in entity
    creation or update. The field attribute allows options_flow to map the
    error back to the specific form field that caused the failure.

    Attributes:
        field: The CFOF_* constant identifying the form field that failed
        translation_key: The TRANS_KEY_* constant for the error message
        placeholders: Optional dict for translation string placeholders

    Example:
        raise EntityValidationError(
            field=const.CFOF_REWARDS_INPUT_COST,
            translation_key=const.TRANS_KEY_INVALID_REWARD_COST,
            placeholders={"value": str(cost)},
        )
    """

    def __init__(
        self,
        field: str,
        translation_key: str,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize EntityValidationError.

        Args:
            field: The CFOF_* constant for the field that failed validation
            translation_key: The TRANS_KEY_* constant for error message
            placeholders: Optional dict for translation placeholders
        """
        self.field = field
        self.translation_key = translation_key
        self.placeholders = placeholders or {}
        super().__init__(translation_key)


# ==============================================================================
# REWARDS
# ==============================================================================

# Note: CFOF_REWARDS_INPUT_* values are now aligned with DATA_REWARD_* values
# (Phase 6 CFOF Key Alignment), so no mapping function is needed.
# build_reward() accepts keys directly from UI forms.


def validate_reward_data(
    data: dict[str, Any],
    existing_rewards: dict[str, Any] | None = None,
    *,
    is_update: bool = False,
    current_reward_id: str | None = None,
) -> dict[str, str]:
    """Validate reward business rules - SINGLE SOURCE OF TRUTH.

    This function contains all reward validation logic used by both:
    - Options Flow (UI) via flow_helpers.validate_rewards_inputs()
    - Services (API) via handle_create_reward() / handle_update_reward()

    Works with DATA_* keys (canonical storage format).

    Args:
        data: Reward data dict with DATA_* keys
        existing_rewards: All existing rewards for duplicate checking (optional)
        is_update: True if updating existing reward (some validations skip)
        current_reward_id: ID of reward being updated (to exclude from duplicate check)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty (create) or not blank (update if provided)
        2. Name not duplicate
        3. Cost >= 0 (if provided)
    """
    errors: dict[str, str] = {}

    # === 1. Name validation ===
    name = data.get(const.DATA_REWARD_NAME, "")
    if isinstance(name, str):
        name = name.strip()

    if not is_update and not name:
        errors[const.CFOP_ERROR_REWARD_NAME] = const.TRANS_KEY_CFOF_INVALID_REWARD_NAME
        return errors

    if is_update and const.DATA_REWARD_NAME in data and not name:
        errors[const.CFOP_ERROR_REWARD_NAME] = const.TRANS_KEY_CFOF_INVALID_REWARD_NAME
        return errors

    # === 2. Duplicate name check ===
    if name and existing_rewards:
        for reward_id, reward_data in existing_rewards.items():
            if reward_id == current_reward_id:
                continue  # Skip self when updating
            if reward_data.get(const.DATA_REWARD_NAME) == name:
                errors[const.CFOP_ERROR_REWARD_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_REWARD
                )
                return errors

    # === 3. Cost >= 0 ===
    if const.DATA_REWARD_COST in data:
        cost = data[const.DATA_REWARD_COST]
        try:
            if float(cost) < 0:
                errors[const.CFOP_ERROR_REWARD_COST] = (
                    const.TRANS_KEY_CFOF_INVALID_REWARD_COST
                )
                return errors
        except (ValueError, TypeError):
            errors[const.CFOP_ERROR_REWARD_COST] = (
                const.TRANS_KEY_CFOF_INVALID_REWARD_COST
            )
            return errors

    return errors


def build_reward(
    user_input: dict[str, Any],
    existing: RewardData | None = None,
) -> RewardData:
    """Build reward data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for reward field handling.
    One function handles both create (existing=None) and update (existing=RewardData).

    Args:
        user_input: Data with DATA_* keys (may have missing fields)
        existing: None for create, existing RewardData for update

    Returns:
        Complete RewardData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        reward = build_reward({DATA_REWARD_NAME: "New Reward"})

        # UPDATE mode - preserves existing fields not in user_input
        reward = build_reward({DATA_REWARD_COST: 50}, existing=old_reward)
    """
    is_create = existing is None

    def get_field(
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default.

        Priority:
        1. If data_key in user_input → use user_input value
        2. If existing is not None → use existing value (update mode)
        3. Fall back to default (create mode)
        """
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(const.DATA_REWARD_NAME, "")
    name = str(raw_name).strip() if raw_name else ""

    # In create mode, name is required
    # In update mode, name is only validated if provided
    if is_create and not name:
        raise EntityValidationError(
            field=const.DATA_REWARD_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
        )
    # If name was explicitly provided but is empty/whitespace, reject it
    if const.DATA_REWARD_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.DATA_REWARD_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_REWARD_NAME,
        )

    # --- Build complete reward structure ---
    # For internal_id: generate new UUID for create, preserve existing for update
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_REWARD_INTERNAL_ID, str(uuid.uuid4()))

    return RewardData(
        internal_id=internal_id,
        name=name,
        cost=float(get_field(const.DATA_REWARD_COST, const.DEFAULT_REWARD_COST)),
        description=str(get_field(const.DATA_REWARD_DESCRIPTION, const.SENTINEL_EMPTY)),
        icon=str(get_field(const.DATA_REWARD_ICON, const.SENTINEL_EMPTY)),
        reward_labels=list(get_field(const.DATA_REWARD_LABELS, [])),
    )


# --- Reward Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_reward():
# - CONFIG fields: Add to _REWARD_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)
#
# NOTE: Rewards have no runtime fields on the reward record itself.
# All runtime state is in assignee-side DATA_USER_REWARD_DATA structure.

_REWARD_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_REWARD_INTERNAL_ID,
        const.DATA_REWARD_NAME,
        # Configuration
        const.DATA_REWARD_COST,
        const.DATA_REWARD_DESCRIPTION,
        const.DATA_REWARD_ICON,
        const.DATA_REWARD_LABELS,
    }
)

# --- Reward user runtime fields (for data_reset_rewards) ---
# These are user-record runtime structures owned by RewardManager.
# On data reset: CLEAR these structures for affected assignee-capable users.
# Note: reward_stats will be deleted in v43; reward_periods holds aggregated all-time stats.

_REWARD_USER_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_USER_REWARD_DATA,  # Per-reward claim tracking
        const.DATA_USER_REWARD_PERIODS,  # Aggregated reward periods (v43+, all_time bucket)
    }
)


# ==============================================================================
# BONUSES & PENALTIES (Unified)
# ==============================================================================

# Note: CFOF_BONUSES_INPUT_* and CFOF_PENALTIES_INPUT_* values are now aligned
# with DATA_BONUS_* and DATA_PENALTY_* values (Phase 6 CFOF Key Alignment),
# so no mapping function is needed. build_bonus_or_penalty() accepts keys
# directly from UI forms.


def validate_bonus_or_penalty_data(
    data: dict[str, Any],
    entity_type: str,  # "bonus" or "penalty"
    existing_entities: dict[str, Any] | None = None,
    *,
    is_update: bool = False,
    current_entity_id: str | None = None,
) -> dict[str, str]:
    """Validate bonus/penalty business rules - SINGLE SOURCE OF TRUTH.

    This function contains all bonus/penalty validation logic used by both:
    - Options Flow (UI) via flow_helpers.validate_bonuses_inputs() / validate_penalties_inputs()
    - Services (API) - when bonus/penalty CRUD services are added

    Works with DATA_* keys (canonical storage format).

    Args:
        data: Entity data dict with DATA_* keys
        entity_type: "bonus" or "penalty"
        existing_entities: All existing entities for duplicate checking (optional)
        is_update: True if updating existing entity (some validations skip)
        current_entity_id: ID of entity being updated (to exclude from duplicate check)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty (create) or not blank (update if provided)
        2. Name not duplicate
    """
    errors: dict[str, str] = {}

    # Determine field names based on entity type
    if entity_type == "bonus":
        name_key = const.DATA_BONUS_NAME
        error_field = const.CFOP_ERROR_BONUS_NAME
        invalid_name_key = const.TRANS_KEY_CFOF_INVALID_BONUS_NAME
        duplicate_key = const.TRANS_KEY_CFOF_DUPLICATE_BONUS
    elif entity_type == "penalty":
        name_key = const.DATA_PENALTY_NAME
        error_field = const.CFOP_ERROR_PENALTY_NAME
        invalid_name_key = const.TRANS_KEY_CFOF_INVALID_PENALTY_NAME
        duplicate_key = const.TRANS_KEY_CFOF_DUPLICATE_PENALTY
    else:
        raise ValueError(
            f"entity_type must be 'bonus' or 'penalty', got: {entity_type}"
        )

    # === 1. Name validation ===
    name = data.get(name_key, "")
    if isinstance(name, str):
        name = name.strip()

    if not is_update and not name:
        errors[error_field] = invalid_name_key
        return errors

    if is_update and name_key in data and not name:
        errors[error_field] = invalid_name_key
        return errors

    # === 2. Duplicate name check ===
    if name and existing_entities:
        for entity_id, entity_data in existing_entities.items():
            if entity_id == current_entity_id:
                continue  # Skip self when updating
            if entity_data.get(name_key) == name:
                errors[error_field] = duplicate_key
                return errors

    return errors


def build_bonus_or_penalty(
    user_input: dict[str, Any],
    entity_type: str,  # "bonus" or "penalty"
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build bonus or penalty data for create or update operations.

    Bonuses and penalties are 95% identical - only differing in:
    - Points sign: positive for bonus, negative for penalty
    - Storage location: DATA_BONUSES vs DATA_PENALTIES
    - Default icon constant

    This unified function handles both entity types to eliminate code duplication.

    Args:
        user_input: Data with DATA_* keys (may have missing fields)
        entity_type: "bonus" or "penalty"
        existing: None for create, existing entity data for update

    Returns:
        Complete dict ready for storage with DATA_* keys

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)
        ValueError: If entity_type is not "bonus" or "penalty"

    Examples:
        # CREATE bonus - generates UUID, applies defaults
        bonus = build_bonus_or_penalty({DATA_BONUS_NAME: "Extra Credit"}, "bonus")

        # UPDATE penalty - preserves existing fields not in user_input
        penalty = build_bonus_or_penalty({DATA_PENALTY_POINTS: 10}, "penalty", existing=old)
    """
    if entity_type not in ("bonus", "penalty"):
        raise ValueError(
            f"entity_type must be 'bonus' or 'penalty', got: {entity_type}"
        )

    is_bonus = entity_type == "bonus"
    is_create = existing is None

    # --- Field key mapping (different constants for bonus vs penalty) ---
    name_key = const.DATA_BONUS_NAME if is_bonus else const.DATA_PENALTY_NAME
    desc_key = (
        const.DATA_BONUS_DESCRIPTION if is_bonus else const.DATA_PENALTY_DESCRIPTION
    )
    labels_key = const.DATA_BONUS_LABELS if is_bonus else const.DATA_PENALTY_LABELS
    points_key = const.DATA_BONUS_POINTS if is_bonus else const.DATA_PENALTY_POINTS
    icon_key = const.DATA_BONUS_ICON if is_bonus else const.DATA_PENALTY_ICON
    internal_id_key = (
        const.DATA_BONUS_INTERNAL_ID if is_bonus else const.DATA_PENALTY_INTERNAL_ID
    )

    # --- Default values (different for bonus vs penalty) ---
    default_points = (
        const.DEFAULT_BONUS_POINTS if is_bonus else const.DEFAULT_PENALTY_POINTS
    )
    default_icon = const.SENTINEL_EMPTY  # Empty = use icons.json translation
    invalid_name_key = (
        const.TRANS_KEY_CFOF_INVALID_BONUS_NAME
        if is_bonus
        else const.TRANS_KEY_CFOF_INVALID_PENALTY_NAME
    )

    def get_field(data_key: str, default: Any) -> Any:
        """Get field value: user_input > existing > default."""
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(name_key, "")
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=name_key,
            translation_key=invalid_name_key,
        )
    if name_key in user_input and not name:
        raise EntityValidationError(
            field=name_key,
            translation_key=invalid_name_key,
        )

    # --- Points: positive for bonus, negative for penalty ---
    raw_points = get_field(points_key, default_points)
    # Ensure correct sign: bonus = positive, penalty = negative
    stored_points = abs(float(raw_points)) if is_bonus else -abs(float(raw_points))

    # --- Internal ID: generate new for create, preserve for update ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(internal_id_key, str(uuid.uuid4()))

    return {
        name_key: name,
        desc_key: str(get_field(desc_key, const.SENTINEL_EMPTY)),
        labels_key: list(get_field(labels_key, [])),
        points_key: stored_points,
        icon_key: str(get_field(icon_key, default_icon)),
        internal_id_key: internal_id,
    }


# --- Bonus Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_bonus_or_penalty():
# - CONFIG fields: Add to _BONUS_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)
#
# NOTE: Bonuses have no runtime fields on the bonus record itself.
# All runtime state is in assignee-side DATA_USER_BONUS_APPLIES structure.

_BONUS_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_BONUS_INTERNAL_ID,
        const.DATA_BONUS_NAME,
        # Configuration
        const.DATA_BONUS_POINTS,
        const.DATA_BONUS_DESCRIPTION,
        const.DATA_BONUS_ICON,
        const.DATA_BONUS_LABELS,
    }
)

# --- Bonus user runtime fields (for data_reset_bonuses) ---
# These are user-record runtime structures owned by EconomyManager.
# On data reset: CLEAR these structures for affected assignee-capable users.

_BONUS_USER_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_USER_BONUS_APPLIES,  # Active bonus tracking
    }
)

# --- Penalty Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_bonus_or_penalty():
# - CONFIG fields: Add to _PENALTY_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)
#
# NOTE: Penalties have no runtime fields on the penalty record itself.
# All runtime state is in assignee-side DATA_USER_PENALTY_APPLIES structure.

_PENALTY_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_PENALTY_INTERNAL_ID,
        const.DATA_PENALTY_NAME,
        # Configuration
        const.DATA_PENALTY_POINTS,
        const.DATA_PENALTY_DESCRIPTION,
        const.DATA_PENALTY_ICON,
        const.DATA_PENALTY_LABELS,
    }
)

# --- Penalty user runtime fields (for data_reset_penalties) ---
# These are user-record runtime structures owned by EconomyManager.
# On data reset: CLEAR these structures for affected assignee-capable users.

_PENALTY_USER_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_USER_PENALTY_APPLIES,  # Active penalty tracking
    }
)


# ==============================================================================
# USER PROFILES - ASSIGNMENT CAPABILITY SURFACE
# ==============================================================================

# Note: This section handles USER records with assignment capability.
# Storage keys remain DATA_USER_*; "assignee" terminology is legacy role UX only.
# USER form surfaces use CFOF_USERS_INPUT_* keys; any legacy aliases are
# normalized before these builders are called.


def validate_user_assignment_profile_data(
    data: dict[str, Any],
    existing_assignees: dict[str, Any] | None = None,
    existing_users: dict[str, Any] | None = None,
    *,
    is_update: bool = False,
    current_assignee_id: str | None = None,
) -> dict[str, str]:
    """Validate assignment-capable USER profile business rules.

    This is the canonical implementation for assignment-profile validation used by:
    - Options Flow (UI) via sectioned USER-form validation wrappers
    - Services (API) via handle_create_assignee() / handle_update_assignee()

    Works with DATA_* keys (canonical storage format).

    Args:
        data: User-record data dict with DATA_USER_* keys
        existing_assignees: All existing assignment-capable users for duplicate
            checking (optional)
        existing_users: User records with approval capabilities for
            cross-validation (optional)
        is_update: True if updating existing assignee (some validations skip)
        current_assignee_id: ID of assignment-capable user being updated (excluded
            from duplicate checks)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty (create) or not blank (update if provided)
        2. Name not duplicate among assignment-capable users
        3. Name not conflict with assignment-enabled approval-capable users
    """
    errors: dict[str, str] = {}

    # === 1. Name validation ===
    name = _normalize_name_field(data.get(const.DATA_USER_NAME, ""))

    if not is_update and not name:
        errors[const.CFOP_ERROR_USER_NAME] = const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
        return errors

    if is_update and const.DATA_USER_NAME in data and not name:
        errors[const.CFOP_ERROR_USER_NAME] = const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
        return errors

    # === 2. Duplicate name check among assignees (exclude approver-linked profiles) ===
    # Approver-linked profiles are managed by the approver linkage system -
    # their name conflicts are
    # handled by rule 3 (approver name conflict check)
    if name and existing_assignees:
        for assignee_id, assignee_data in existing_assignees.items():
            if assignee_id == current_assignee_id:
                continue  # Skip self when updating
            if not assignee_data.get(const.DATA_USER_CAN_BE_ASSIGNED, True):
                continue  # Approver-linked profiles handled by approver validation
            if assignee_data.get(const.DATA_USER_NAME) == name:
                errors[const.CFOP_ERROR_USER_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_ASSIGNEE
                )
                return errors

    # === 3. Conflict with assignment-enabled user profiles ===
    # Check conflicts only for assignment-enabled approvers
    # Approvers without assignment capability do not create linked assignee-like profiles
    if name and existing_users:
        for approver_data in existing_users.values():
            if approver_data.get(const.DATA_USER_CAN_BE_ASSIGNED, False):
                if approver_data.get(const.DATA_USER_NAME) == name:
                    errors[const.CFOP_ERROR_USER_NAME] = (
                        const.TRANS_KEY_CFOF_DUPLICATE_NAME
                    )
                    return errors

    return errors


def build_user_assignment_profile(
    user_input: dict[str, Any],
    existing: AssigneeData | None = None,
) -> AssigneeData:
    """Build assignment-capable USER profile data for create/update operations.

    This is the canonical builder for assignment-profile field handling. One function
    handles both create (existing=None) and update (existing=AssigneeData).

    Args:
        user_input: Form/service data with USER-surface CFOF_* keys
        existing: None for create, existing AssigneeData for update

    Returns:
        Complete AssigneeData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies defaults for missing fields
        user_profile = build_user_assignment_profile({CFOF_USERS_INPUT_NAME: "Alice"})

        # UPDATE mode - preserves existing fields not in user_input
        user_profile = build_user_assignment_profile({CFOF_USERS_INPUT_DASHBOARD_LANGUAGE: "es"}, existing=old_assignee)

        # Create mode with approval-derived assignment defaults
        user_profile = build_user_assignment_profile(approver_derived_input)
    """
    is_create = existing is None
    existing_data = cast("dict[str, Any] | None", existing)

    # --- Name validation (required for create, optional for update) ---
    raw_name = _resolve_user_input_field(
        user_input,
        existing_data,
        const.CFOF_USERS_INPUT_NAME,
        const.DATA_USER_NAME,
        "",
    )
    name = _normalize_name_field(raw_name)

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_USERS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME,
        )
    if const.CFOF_USERS_INPUT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_USERS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME,
        )

    # --- Internal ID: generate for create, preserve for update ---
    internal_id = _resolve_or_create_internal_id(existing_data)

    # --- Handle HA user and notification service sentinels ---
    ha_user_id = _normalize_user_select_value(
        _resolve_user_input_field(
            user_input,
            existing_data,
            const.CFOF_USERS_INPUT_HA_USER_ID,
            const.DATA_USER_HA_USER_ID,
            "",
        )
    )

    notify_service = _normalize_user_select_value(
        _resolve_user_input_field(
            user_input,
            existing_data,
            const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE,
            const.DATA_USER_MOBILE_NOTIFY_SERVICE,
            const.SENTINEL_EMPTY,
        )
    )

    # --- Build complete assignment-capable USER structure ---
    # Include runtime fields expected for assignment workflows
    assignee_data: AssigneeData = {
        # Core identification
        const.DATA_USER_INTERNAL_ID: internal_id,
        const.DATA_USER_NAME: name,
        # Points (runtime initialized)
        const.DATA_USER_POINTS: float(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_GLOBAL_INPUT_INTERNAL_ID,  # Not a real form field
                const.DATA_USER_POINTS,
                const.DEFAULT_ZERO,
            )
            if existing
            else const.DEFAULT_ZERO
        ),
        const.DATA_USER_POINTS_MULTIPLIER: float(
            existing.get(
                const.DATA_USER_POINTS_MULTIPLIER,
                const.DEFAULT_ASSIGNEE_POINTS_MULTIPLIER,
            )
            if existing
            else const.DEFAULT_ASSIGNEE_POINTS_MULTIPLIER
        ),
        # Linkage
        const.DATA_USER_HA_USER_ID: ha_user_id,
        # Notifications
        const.DATA_USER_MOBILE_NOTIFY_SERVICE: notify_service,
        const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS: (
            existing.get(const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS, False)
            if existing
            else False
        ),
        const.DATA_USER_DASHBOARD_LANGUAGE: str(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_DASHBOARD_LANGUAGE,
                const.DATA_USER_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            )
        ),
        # Badge tracking (runtime initialized)
        const.DATA_USER_BADGES_EARNED: (
            existing.get(const.DATA_USER_BADGES_EARNED, {}) if existing else {}
        ),
        # Reward tracking (runtime initialized)
        const.DATA_USER_REWARD_DATA: (
            existing.get(const.DATA_USER_REWARD_DATA, {}) if existing else {}
        ),
        # Penalty/bonus tracking (runtime initialized)
        const.DATA_USER_PENALTY_APPLIES: (
            existing.get(const.DATA_USER_PENALTY_APPLIES, {}) if existing else {}
        ),
        const.DATA_USER_BONUS_APPLIES: (
            existing.get(const.DATA_USER_BONUS_APPLIES, {}) if existing else {}
        ),
        # NOTE: DATA_KID_OVERDUE_CHORES removed - dead code, overdue tracked in chore_data[chore_id].state
    }

    return assignee_data


# ==============================================================================
# USER PROFILES - APPROVAL CAPABILITY SURFACE
# ==============================================================================
# Note: This section handles USER records with approval/management capability.
# Storage keys remain DATA_USER_*; "approver" terminology is legacy role UX only.
# USER form surfaces use CFOF_USERS_INPUT_* keys; any legacy aliases are
# normalized before these builders are called.


def validate_user_profile_data(
    data: dict[str, Any],
    existing_users: dict[str, Any] | None = None,
    existing_assignees: dict[str, Any] | None = None,
    *,
    is_update: bool = False,
    current_user_id: str | None = None,
) -> dict[str, str]:
    """Validate approval-capable USER profile business rules.

    This is the canonical implementation for approval-capability validation used by:
    - Options Flow (UI) via flow_helpers.validate_users_inputs()
    - Services (API) via handle_create_approver() / handle_update_approver()

    Works with DATA_* keys (canonical storage format).

    Args:
        data: User-profile data dict with DATA_* keys
        existing_users: All existing user profiles for duplicate checking
        existing_assignees: Assignment-capable users for cross-validation (optional)
        is_update: True if updating existing user profile (some validations skip)
        current_user_id: ID of user profile being updated (to exclude from duplicate check)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty (create) or not blank (update if provided)
        2. Name not duplicate among user profiles
        3. Name not conflict with assignment-capable users (when assignment is enabled)
        4. Workflow/gamification require assignment enablement
        5. At least one of assignment or approval must be enabled
        6. Approval requires non-empty associated users list
    """
    errors: dict[str, str] = {}

    # === 1. Name validation ===
    name = _normalize_name_field(data.get(const.DATA_USER_NAME, ""))

    if not is_update and not name:
        errors[const.CFOP_ERROR_USER_NAME] = const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME
        return errors

    if is_update and const.DATA_USER_NAME in data and not name:
        errors[const.CFOP_ERROR_USER_NAME] = const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME
        return errors

    # === 2. Duplicate name check among user profiles ===
    if name and existing_users:
        for user_id, user_data in existing_users.items():
            if user_id == current_user_id:
                continue  # Skip self when updating
            if user_data.get(const.DATA_USER_NAME) == name:
                errors[const.CFOP_ERROR_USER_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_APPROVER
                )
                return errors

    # === 3. Conflict with assignees (only when assignment is enabled) ===
    # When assignment is enabled, a linked profile record may use this name
    assignment_enabled = data.get(const.DATA_USER_CAN_BE_ASSIGNED, False)
    if assignment_enabled and name and existing_assignees:
        for assignee_id, assignee_data in existing_assignees.items():
            assignee_internal_id = assignee_data.get(const.DATA_USER_INTERNAL_ID)
            if current_user_id is not None and current_user_id in {
                assignee_id,
                assignee_internal_id,
            }:
                continue
            if assignee_data.get(const.DATA_USER_NAME) == name:
                errors[const.CFOP_ERROR_USER_NAME] = const.TRANS_KEY_CFOF_DUPLICATE_NAME
                return errors

    has_usage_context = any(
        key in data
        for key in (
            const.DATA_USER_CAN_BE_ASSIGNED,
            const.DATA_USER_ENABLE_CHORE_WORKFLOW,
            const.DATA_USER_ENABLE_GAMIFICATION,
            const.DATA_USER_CAN_APPROVE,
            const.DATA_USER_ASSOCIATED_USER_IDS,
        )
    )

    if not has_usage_context:
        return errors

    # === 4. Workflow/gamification require assignment enablement ===
    enable_chore_workflow = data.get(const.DATA_USER_ENABLE_CHORE_WORKFLOW, False)
    enable_gamification = data.get(const.DATA_USER_ENABLE_GAMIFICATION, False)
    if (enable_chore_workflow or enable_gamification) and not assignment_enabled:
        errors[const.CFOP_ERROR_CHORE_OPTIONS] = (
            const.TRANS_KEY_CFOF_CHORE_OPTIONS_REQUIRE_ASSIGNMENT
        )
        return errors

    associated_users = data.get(const.DATA_USER_ASSOCIATED_USER_IDS, [])

    # === 5. At least one of assignment or approval must be enabled ===
    can_approve = bool(data.get(const.DATA_USER_CAN_APPROVE, False))
    if not assignment_enabled and not can_approve:
        errors[const.CFOP_ERROR_CHORE_OPTIONS] = (
            const.TRANS_KEY_CFOF_USAGE_REQUIRES_ASSIGNMENT_OR_APPROVAL
        )
        return errors

    # === 6. Associated users require approval enablement ===
    if not can_approve and associated_users:
        errors[const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS] = (
            const.TRANS_KEY_CFOF_ASSOCIATED_USERS_REQUIRE_APPROVAL
        )
        return errors

    # === 7. Approval requires non-empty associated users list ===
    if can_approve and not associated_users:
        errors[const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS] = (
            const.TRANS_KEY_CFOF_APPROVAL_REQUIRES_ASSOCIATED_USERS
        )
        return errors

    return errors


def build_user_profile(
    user_input: dict[str, Any],
    existing: UserData | None = None,
) -> UserData:
    """Build approval-capable USER profile data for create or update operations.

    This is the canonical builder for approval-capability field handling. One
    function handles both create (existing=None) and update
    (existing=UserData).

    Args:
        user_input: Form/service data with role-aware CFOF_* keys
        existing: None for create, existing UserData for update

    Returns:
        Complete UserData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies defaults for missing fields
        user_profile = build_user_profile({CFOF_USERS_INPUT_NAME: "Dad"})

        # UPDATE mode - preserves existing fields not in user_input
        user_profile = build_user_profile({CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: ["uuid1"]}, existing=old)
    """
    is_create = existing is None
    existing_data = cast("dict[str, Any] | None", existing)

    # --- Name validation (required for create, optional for update) ---
    raw_name = _resolve_user_input_field(
        user_input,
        existing_data,
        const.CFOF_USERS_INPUT_NAME,
        const.DATA_USER_NAME,
        "",
    )
    name = _normalize_name_field(raw_name)

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_USERS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME,
        )
    if const.CFOF_USERS_INPUT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_USERS_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME,
        )

    # --- Internal ID: generate for create, preserve for update ---
    internal_id = _resolve_or_create_internal_id(existing_data)

    # --- Handle HA user and notification service sentinels ---
    ha_user_id = _normalize_user_select_value(
        _resolve_user_input_field(
            user_input,
            existing_data,
            const.CFOF_USERS_INPUT_HA_USER_ID,
            const.DATA_USER_HA_USER_ID,
            "",
        )
    )

    notify_service = _normalize_user_select_value(
        _resolve_user_input_field(
            user_input,
            existing_data,
            const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE,
            const.DATA_USER_MOBILE_NOTIFY_SERVICE,
            "",
        )
    )

    associated_assignees = list(
        _resolve_user_input_field(
            user_input,
            existing_data,
            const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
            const.DATA_USER_ASSOCIATED_USER_IDS,
            [],
        )
    )

    # --- Build complete user-profile structure ---
    user_profile_data: dict[str, Any] = {
        const.DATA_USER_INTERNAL_ID: internal_id,
        const.DATA_USER_NAME: name,
        const.DATA_USER_HA_USER_ID: ha_user_id,
        const.DATA_USER_ASSOCIATED_USER_IDS: associated_assignees,
        const.DATA_USER_MOBILE_NOTIFY_SERVICE: notify_service,
        const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS: (
            existing.get(const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS, False)
            if existing
            else False
        ),
        const.DATA_USER_DASHBOARD_LANGUAGE: str(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_DASHBOARD_LANGUAGE,
                const.DATA_USER_DASHBOARD_LANGUAGE,
                const.DEFAULT_DASHBOARD_LANGUAGE,
            )
        ),
        const.DATA_USER_CAN_BE_ASSIGNED: bool(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
                const.DATA_USER_CAN_BE_ASSIGNED,
                False,
            )
        ),
        const.DATA_USER_ENABLE_CHORE_WORKFLOW: bool(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW,
                const.DATA_USER_ENABLE_CHORE_WORKFLOW,
                False,
            )
        ),
        const.DATA_USER_ENABLE_GAMIFICATION: bool(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION,
                const.DATA_USER_ENABLE_GAMIFICATION,
                False,
            )
        ),
        const.DATA_USER_CAN_APPROVE: bool(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_CAN_APPROVE,
                const.DATA_USER_CAN_APPROVE,
                False,
            )
        ),
        const.DATA_USER_CAN_MANAGE: bool(
            _resolve_user_input_field(
                user_input,
                existing_data,
                const.CFOF_USERS_INPUT_CAN_MANAGE,
                const.DATA_USER_CAN_MANAGE,
                False,
            )
        ),
    }
    return cast("UserData", user_profile_data)


# --- User profile preserve fields (for data_reset_users) ---
# MAINTENANCE CONTRACT: When adding fields to build_user_assignment_profile():
# - USER PROFILE CONFIG fields: Add here (preserved during user-profile data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)

_USER_MANAGER_PROFILE_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # System identity (never changes)
        const.DATA_USER_INTERNAL_ID,
        # User-configured fields
        const.DATA_USER_NAME,
        const.DATA_USER_HA_USER_ID,
        const.DATA_USER_MOBILE_NOTIFY_SERVICE,
        const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
        const.DATA_USER_DASHBOARD_LANGUAGE,
    }
)


# --- Economy manager user runtime fields (for data_reset_points) ---
# These are user-record runtime fields owned by EconomyManager.
# EconomyManager creates these on-demand before recording transactions.
# On data reset: reset points to 0, clear ledger, clear point stats/data.

_ECONOMY_USER_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_USER_POINTS,  # Current point balance
        const.DATA_USER_POINTS_MULTIPLIER,  # Reset to DEFAULT_ASSIGNEE_POINTS_MULTIPLIER
        const.DATA_USER_LEDGER,  # Transaction history
        const.DATA_USER_POINT_PERIODS,  # Period point breakdowns (EconomyManager owns, v43+)
    }
)


# ==============================================================================
# CHORES
# ==============================================================================

# Note: Most CFOF_CHORES_INPUT_* values are aligned with DATA_CHORE_* values
# (Phase 6 CFOF Key Alignment). However, transform_chore_cfof_to_data() is
# still needed for complex fields:
# - daily_multi_times: CSV string → int list
# - per_assignee_due_dates: per-assignee override parsing
# See flow_helpers.transform_chore_cfof_to_data() for details.


def validate_chore_data(
    data: dict[str, Any],
    existing_chores: dict[str, Any] | None = None,
    *,
    is_update: bool = False,
    current_chore_id: str | None = None,
) -> dict[str, str]:
    """Validate chore business rules - SINGLE SOURCE OF TRUTH.

    This function contains all chore validation logic used by both:
    - Options Flow (UI) via flow_helpers.validate_chores_inputs()
    - Services (API) via handle_create_chore() / handle_update_chore()

    Works with DATA_* keys (canonical storage format).

    Args:
        data: Chore data dict with DATA_* keys
        existing_chores: All existing chores for duplicate checking (optional)
        is_update: True if updating existing chore (some validations skip)
        current_chore_id: ID of chore being updated (to exclude from duplicate check)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty (create) or not blank (update if provided)
        2. Name not duplicate
        3. At least one assignee assigned (create only)
        4. Points >= 0 (if provided)
        5. Due date not in past (if provided)
        6. DAILY_MULTI + reset type combination
        7. Overdue + reset type combination
        8. DAILY_MULTI requires due_date (unless INDEPENDENT multi-assignee)
        9. AT_DUE_DATE_* reset types require due_date
    """
    errors: dict[str, str] = {}

    # === 1. Name validation ===
    name = data.get(const.DATA_CHORE_NAME, "")
    if isinstance(name, str):
        name = name.strip()

    if not is_update and not name:
        errors[const.CFOP_ERROR_CHORE_NAME] = const.TRANS_KEY_CFOF_INVALID_CHORE_NAME
        return errors

    if is_update and const.DATA_CHORE_NAME in data and not name:
        errors[const.CFOP_ERROR_CHORE_NAME] = const.TRANS_KEY_CFOF_INVALID_CHORE_NAME
        return errors

    # === 2. Duplicate name check ===
    if name and existing_chores:
        for chore_id, chore_data in existing_chores.items():
            if chore_id == current_chore_id:
                continue  # Skip self when updating
            if chore_data.get(const.DATA_CHORE_NAME) == name:
                errors[const.CFOP_ERROR_CHORE_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_CHORE
                )
                return errors

    # === 3. Assigned assignees validation (create only) ===
    assigned_assignees = data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
    if not is_update and not assigned_assignees:
        errors[const.CFOP_ERROR_ASSIGNED_USER_IDS] = (
            const.TRANS_KEY_CFOF_NO_ASSIGNEES_ASSIGNED
        )
        return errors

    # === 4. Points >= 0 ===
    if const.DATA_CHORE_DEFAULT_POINTS in data:
        points = data[const.DATA_CHORE_DEFAULT_POINTS]
        try:
            if float(points) < 0:
                errors[const.CFOP_ERROR_CHORE_POINTS] = (
                    const.TRANS_KEY_CFOF_INVALID_POINTS
                )
                return errors
        except (ValueError, TypeError):
            errors[const.CFOP_ERROR_CHORE_POINTS] = const.TRANS_KEY_CFOF_INVALID_POINTS
            return errors

    # === 5. Due date not in past ===
    due_date_raw = data.get(const.DATA_CHORE_DUE_DATE)
    due_dt: datetime.datetime | None = None
    if due_date_raw:
        try:
            parsed = dt_parse(
                due_date_raw,
                default_tzinfo=const.DEFAULT_TIME_ZONE,
                return_type=const.HELPER_RETURN_DATETIME_UTC,
            )
            # Type guard: ensure we got a datetime
            if parsed and isinstance(parsed, datetime.datetime):
                due_dt = parsed
            if due_dt and due_dt < dt_now_utc():
                errors[const.CFOP_ERROR_DUE_DATE] = (
                    const.TRANS_KEY_CFOF_DUE_DATE_IN_PAST
                )
                return errors
        except (ValueError, TypeError, AttributeError):
            errors[const.CFOP_ERROR_DUE_DATE] = const.TRANS_KEY_CFOF_INVALID_DUE_DATE
            return errors

    # === Extract config for combination validations ===
    recurring_frequency = data.get(
        const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE
    )
    approval_reset = data.get(
        const.DATA_CHORE_APPROVAL_RESET_TYPE, const.DEFAULT_APPROVAL_RESET_TYPE
    )
    overdue_handling = data.get(
        const.DATA_CHORE_OVERDUE_HANDLING_TYPE, const.DEFAULT_OVERDUE_HANDLING_TYPE
    )
    completion_criteria = data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
    )

    # === 6. DAILY_MULTI + reset type validation ===
    if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
        incompatible_reset_types = {
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }
        if approval_reset in incompatible_reset_types:
            errors[const.CFOP_ERROR_DAILY_MULTI_RESET] = (
                const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET
            )
            return errors

    # === 7. Overdue + reset combination validation ===
    if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET:
        valid_reset_types = {
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
            const.APPROVAL_RESET_UPON_COMPLETION,
        }
        if approval_reset not in valid_reset_types:
            errors[const.CFOP_ERROR_OVERDUE_RESET_COMBO] = (
                const.TRANS_KEY_CFOF_INVALID_OVERDUE_RESET_COMBINATION
            )
            return errors

    # === Check if INDEPENDENT multi-assignee (special case for due date requirements) ===
    is_independent_multiassignee = (
        completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
        and len(assigned_assignees) >= 2
    )

    # === 8. DAILY_MULTI requires due_date ===
    if (
        recurring_frequency == const.FREQUENCY_DAILY_MULTI
        and not due_date_raw
        and not is_independent_multiassignee
    ):
        errors[const.CFOP_ERROR_DAILY_MULTI_DUE_DATE] = (
            const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_DUE_DATE_REQUIRED
        )
        return errors

    # === 9. AT_DUE_DATE_* reset types require due_date ===
    if approval_reset in (
        const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
        const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
    ):
        if not due_date_raw and not is_independent_multiassignee:
            errors[const.CFOP_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE] = (
                const.TRANS_KEY_CFOF_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE
            )
            return errors

    # === V-03: Rotation requires ≥ 2 assigned assignees ===
    rotation_criteria = {
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        const.COMPLETION_CRITERIA_ROTATION_SMART,
    }
    if completion_criteria in rotation_criteria:
        if len(assigned_assignees) < 2:
            errors[const.CFOP_ERROR_ASSIGNED_USER_IDS] = (
                const.TRANS_KEY_ERROR_ROTATION_MIN_ASSIGNEES
            )
            return errors

    # === V-05: at_due_date_allow_steal compatibility ===
    if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL:
        # Must be a rotation chore
        if (
            completion_criteria not in rotation_criteria
            or approval_reset != const.APPROVAL_RESET_AT_MIDNIGHT_ONCE
            or not due_date_raw
        ):
            errors[const.CFOP_ERROR_OVERDUE_RESET_COMBO] = (
                const.TRANS_KEY_CFOF_ERROR_ALLOW_STEAL_INCOMPATIBLE
            )
            return errors

    return errors


def build_chore(
    user_input: dict[str, Any],
    existing: ChoreData | None = None,
) -> ChoreData:
    """Build chore data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for chore field handling.
    One function handles both create (existing=None) and update (existing=ChoreData).

    NOTE: This function does NOT validate for duplicates or complex business rules.
    Use flow_helpers.validate_chores_inputs() for validation, then
    flow_helpers.transform_chore_cfof_to_data() to convert form keys to DATA_* keys.
    This function handles field defaults and type coercion only.

    Args:
        user_input: Form/service data with DATA_* keys (pre-validated by flow_helpers)
        existing: None for create, existing ChoreData for update

    Returns:
        Complete ChoreData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        chore = build_chore({DATA_CHORE_NAME: "Clean Room", DATA_CHORE_ASSIGNED_USER_IDS: [...]})

        # UPDATE mode - preserves existing fields not in user_input
        chore = build_chore({DATA_CHORE_DEFAULT_POINTS: 15}, existing=old_chore)
    """
    is_create = existing is None

    def get_field(
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default.

        NOTE: Uses DATA_* keys directly (not CFOF_*) since chore data
        is pre-processed by flow_helpers.transform_chore_cfof_to_data().
        """
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(const.DATA_CHORE_NAME, "")
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_CHORES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_CHORE_NAME,
        )
    if const.DATA_CHORE_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_CHORES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_CHORE_NAME,
        )

    # --- Internal ID: generate for create, preserve for update ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_CHORE_INTERNAL_ID, str(uuid.uuid4()))

    # --- Handle custom interval fields based on frequency ---
    recurring_frequency = get_field(
        const.DATA_CHORE_RECURRING_FREQUENCY,
        const.FREQUENCY_NONE,
    )
    is_custom_frequency = recurring_frequency in (
        const.FREQUENCY_CUSTOM,
        const.FREQUENCY_CUSTOM_FROM_COMPLETE,
    )

    custom_interval = (
        get_field(const.DATA_CHORE_CUSTOM_INTERVAL, None)
        if is_custom_frequency
        else None
    )
    custom_interval_unit = (
        get_field(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, None)
        if is_custom_frequency
        else None
    )

    # --- Build complete chore structure ---
    # Extract values needed for rotation genesis logic
    assigned_assignees_value = get_field(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
    completion_criteria_value = get_field(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )

    # Cast to ChoreData - all required fields are populated
    return cast(
        "ChoreData",
        {
            # Core identification
            const.DATA_CHORE_INTERNAL_ID: internal_id,
            const.DATA_CHORE_NAME: name,
            # State - always starts as PENDING for new chores
            const.DATA_CHORE_STATE: get_field(
                const.DATA_CHORE_STATE,
                const.CHORE_STATE_PENDING,
            ),
            # Points and configuration
            const.DATA_CHORE_DEFAULT_POINTS: float(
                get_field(const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_POINTS)
            ),
            const.DATA_CHORE_APPROVAL_RESET_TYPE: get_field(
                const.DATA_CHORE_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
            const.DATA_CHORE_OVERDUE_HANDLING_TYPE: get_field(
                const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            ),
            const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: get_field(
                const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            ),
            # Description and display
            const.DATA_CHORE_DESCRIPTION: str(
                get_field(const.DATA_CHORE_DESCRIPTION, const.SENTINEL_EMPTY)
            ),
            const.DATA_CHORE_LABELS: list(get_field(const.DATA_CHORE_LABELS, [])),
            const.DATA_CHORE_ICON: str(
                get_field(const.DATA_CHORE_ICON, const.SENTINEL_EMPTY)
            ),
            # Assignment
            const.DATA_CHORE_ASSIGNED_USER_IDS: list(assigned_assignees_value),
            # Scheduling
            const.DATA_CHORE_RECURRING_FREQUENCY: recurring_frequency,
            const.DATA_CHORE_CUSTOM_INTERVAL: custom_interval,
            const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: custom_interval_unit,
            const.DATA_CHORE_DAILY_MULTI_TIMES: _pass_through_field(
                get_field(const.DATA_CHORE_DAILY_MULTI_TIMES, None), None
            ),
            # Due dates
            const.DATA_CHORE_DUE_DATE: get_field(const.DATA_CHORE_DUE_DATE, None),
            const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: _normalize_dict_field(
                get_field(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
            ),
            const.DATA_CHORE_APPLICABLE_DAYS: _normalize_list_field(
                get_field(const.DATA_CHORE_APPLICABLE_DAYS, [])
            ),
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS: _normalize_dict_field(
                get_field(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {})
            ),
            const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES: _normalize_dict_field(
                get_field(const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES, {})
            ),
            # Due window configuration (per-chore offsets)
            const.DATA_CHORE_DUE_WINDOW_OFFSET: get_field(
                const.DATA_CHORE_DUE_WINDOW_OFFSET, const.DEFAULT_DUE_WINDOW_OFFSET
            ),
            const.DATA_CHORE_DUE_REMINDER_OFFSET: get_field(
                const.DATA_CHORE_DUE_REMINDER_OFFSET, const.DEFAULT_DUE_REMINDER_OFFSET
            ),
            # Runtime tracking (preserve existing values on update)
            const.DATA_CHORE_LAST_COMPLETED: get_field(
                const.DATA_CHORE_LAST_COMPLETED, None
            ),
            const.DATA_CHORE_LAST_CLAIMED: get_field(
                const.DATA_CHORE_LAST_CLAIMED, None
            ),
            const.DATA_CHORE_APPROVAL_PERIOD_START: get_field(
                const.DATA_CHORE_APPROVAL_PERIOD_START,
                dt_now_utc().isoformat(),  # Default to now for new SHARED chores
            ),
            const.DATA_CHORE_CLAIMED_BY: list(
                get_field(const.DATA_CHORE_CLAIMED_BY, [])
            ),
            const.DATA_CHORE_COMPLETED_BY: list(
                get_field(const.DATA_CHORE_COMPLETED_BY, [])
            ),
            # Notifications
            const.DATA_CHORE_NOTIFY_ON_CLAIM: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
                )
            ),
            const.DATA_CHORE_NOTIFY_ON_APPROVAL: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_APPROVAL,
                    const.DEFAULT_NOTIFY_ON_APPROVAL,
                )
            ),
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                    const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
                )
            ),
            const.DATA_CHORE_NOTIFY_ON_OVERDUE: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_OVERDUE,
                    const.DEFAULT_NOTIFY_ON_OVERDUE,
                )
            ),
            # Due window notifications (Phase 2)
            const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW,
                    const.DEFAULT_NOTIFY_ON_DUE_WINDOW,
                )
            ),
            const.DATA_CHORE_NOTIFY_DUE_REMINDER: bool(
                get_field(
                    const.DATA_CHORE_NOTIFY_DUE_REMINDER,
                    const.DEFAULT_NOTIFY_DUE_REMINDER,
                )
            ),
            # Calendar and features
            const.DATA_CHORE_SHOW_ON_CALENDAR: bool(
                get_field(
                    const.DATA_CHORE_SHOW_ON_CALENDAR,
                    const.DEFAULT_CHORE_SHOW_ON_CALENDAR,
                )
            ),
            const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW: bool(
                get_field(
                    const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
                    const.DEFAULT_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
                )
            ),
            const.DATA_CHORE_AUTO_APPROVE: bool(
                get_field(
                    const.DATA_CHORE_AUTO_APPROVE,
                    const.DEFAULT_CHORE_AUTO_APPROVE,
                )
            ),
            # Completion criteria
            const.DATA_CHORE_COMPLETION_CRITERIA: get_field(
                const.DATA_CHORE_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            ),
            # Rotation tracking (v0.5.0 Chore Logic)
            const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID: get_field(
                const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID,
                (
                    assigned_assignees_value[0]
                    if (
                        is_create
                        and assigned_assignees_value
                        and completion_criteria_value
                        in (
                            const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
                            const.COMPLETION_CRITERIA_ROTATION_SMART,
                        )
                    )
                    else None
                ),
            ),
            # rotation_order removed - unused field, assigned_assignees defines order
            const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE: get_field(
                const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE, False
            ),
        },
    )


# --- Chore Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_chore():
# - CONFIG fields: Add to _CHORE_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)

_CHORE_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_CHORE_INTERNAL_ID,
        const.DATA_CHORE_NAME,
        # Points and configuration
        const.DATA_CHORE_DEFAULT_POINTS,
        const.DATA_CHORE_APPROVAL_RESET_TYPE,
        const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
        # Description and display
        const.DATA_CHORE_DESCRIPTION,
        const.DATA_CHORE_LABELS,
        const.DATA_CHORE_ICON,
        # Assignment (per-assignee CONFIG, not runtime)
        const.DATA_CHORE_ASSIGNED_USER_IDS,
        # Scheduling configuration
        const.DATA_CHORE_RECURRING_FREQUENCY,
        const.DATA_CHORE_CUSTOM_INTERVAL,
        const.DATA_CHORE_CUSTOM_INTERVAL_UNIT,
        const.DATA_CHORE_DAILY_MULTI_TIMES,
        # Due date configuration (per-assignee CONFIG)
        const.DATA_CHORE_DUE_DATE,
        const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
        const.DATA_CHORE_APPLICABLE_DAYS,
        const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS,
        const.DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES,
        # Due window configuration
        const.DATA_CHORE_DUE_WINDOW_OFFSET,
        const.DATA_CHORE_DUE_REMINDER_OFFSET,
        # Notification settings
        const.DATA_CHORE_NOTIFY_ON_CLAIM,
        const.DATA_CHORE_NOTIFY_ON_APPROVAL,
        const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
        const.DATA_CHORE_NOTIFY_ON_OVERDUE,
        # Calendar and features
        const.DATA_CHORE_SHOW_ON_CALENDAR,
        const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
        const.DATA_CHORE_AUTO_APPROVE,
        # Completion criteria
        const.DATA_CHORE_COMPLETION_CRITERIA,
    }
)

# --- Chore Runtime Fields (cleared on FULL data reset) ---
# These are fields in the chore record that track runtime state.
# On FULL chore data reset, they are CLEARED to their defaults.
#
# NOTE: Per-assignee tracking lists (claimed_by, completed_by) are cleared entirely
# on full reset. Per-assignee CONFIG (assigned_assignees, per_assignee_due_dates) is PRESERVED.

_CHORE_RUNTIME_DATA_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_CHORE_STATE,  # Reset to PENDING
        const.DATA_CHORE_LAST_COMPLETED,  # Clear to None
        const.DATA_CHORE_LAST_CLAIMED,  # Clear to None
        const.DATA_CHORE_APPROVAL_PERIOD_START,  # Reset to now
        const.DATA_CHORE_CLAIMED_BY,  # Clear to []
        const.DATA_CHORE_COMPLETED_BY,  # Clear to []
    }
)

# --- Chore Per-Assignee Runtime Lists (for PER-KID data reset) ---
# These are chore-level lists that track assignee_ids for runtime state.
# On PER-KID data reset: REMOVE the specific assignee_id from these lists.
# On FULL data reset: CLEAR these lists entirely (handled by build_chore defaults).
#
# MAINTENANCE CONTRACT: When adding new chore-level assignee tracking lists,
# add them here so per-assignee data reset removes the assignee from them.

_CHORE_PER_ASSIGNEE_RUNTIME_LISTS: frozenset[str] = frozenset(
    {
        const.DATA_CHORE_CLAIMED_BY,  # List of assignee_ids who claimed
        const.DATA_CHORE_COMPLETED_BY,  # List of assignee_ids who completed
    }
)

# --- Chore user runtime fields (for data_reset_chores) ---
# These are user-record runtime structures owned by ChoreManager.
# ChoreManager creates these on-demand before recording data (not at assignee genesis).
# On data reset: CLEAR these structures for affected assignee-capable users.
# Note: chore_stats deleted in v43; chore_periods holds aggregated all-time stats.

_CHORE_USER_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_USER_CHORE_DATA,  # Per-chore tracking (ChoreManager creates on-demand)
        const.DATA_USER_CHORE_PERIODS,  # Aggregated chore periods (v43+, all_time bucket)
    }
)


# ==============================================================================
# BADGES
# ==============================================================================

# Note: Badges intentionally use embedded CFOF→DATA key mapping within
# build_badge() rather than separate aligned constants. This is because badge
# fields vary significantly by badge_type (cumulative vs periodic vs daily etc).
# The embedded mapping provides type-specific field handling in one place.


def build_badge(
    user_input: dict[str, Any],
    existing: BadgeData | None = None,
    *,
    badge_type: str = const.BADGE_TYPE_CUMULATIVE,
) -> BadgeData:
    """Build badge data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for badge field handling.
    One function handles both create (existing=None) and update (existing=BadgeData).

    Note: Unlike other entity types where CFOF keys are aligned with DATA keys
    (Phase 6), badges use embedded mapping due to badge_type-specific fields.

    Badge types have different required components:
    - CUMULATIVE: target (points-only), awards
    - DAILY: target, awards, assigned_user_ids
    - PERIODIC: target, awards, assigned_user_ids, reset_schedule, tracked_chores
    - SPECIAL_OCCASION: special_occasion_type
    - ACHIEVEMENT_LINKED: associated_achievement
    - CHALLENGE_LINKED: associated_challenge

    Args:
        user_input: Form/service data with CFOF_* keys (may have missing fields)
        existing: None for create, existing BadgeData for update
        badge_type: Type of badge being created/updated

    Returns:
        Complete BadgeData TypedDict ready for storage

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies const.DEFAULT_* for missing fields
        badge = build_badge(
            {CFOF_BADGES_INPUT_NAME: "Super Star"},
            badge_type=const.BADGE_TYPE_CUMULATIVE
        )

        # UPDATE mode - preserves existing fields not in user_input
        badge = build_badge(
            {CFOF_BADGES_INPUT_NAME: "Renamed Badge"},
            existing=old_badge,
            badge_type=old_badge["badge_type"]
        )
    """
    is_create = existing is None

    def get_field(
        cfof_key: str,
        data_key: str,
        default: Any,
    ) -> Any:
        """Get field value: user_input > existing > default."""
        if cfof_key in user_input:
            return user_input[cfof_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(
        const.CFOF_BADGES_INPUT_NAME,
        const.DATA_BADGE_NAME,
        "",
    )
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.CFOF_BADGES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_BADGE_NAME,
        )
    if const.CFOF_BADGES_INPUT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.CFOF_BADGES_INPUT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_BADGE_NAME,
        )

    # --- Generate or preserve internal_id ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_BADGE_INTERNAL_ID, str(uuid.uuid4()))

    # --- Determine which components this badge type includes ---
    include_target = badge_type in const.INCLUDE_TARGET_BADGE_TYPES
    include_special_occasion = badge_type in const.INCLUDE_SPECIAL_OCCASION_BADGE_TYPES
    include_achievement_linked = (
        badge_type in const.INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES
    )
    include_challenge_linked = badge_type in const.INCLUDE_CHALLENGE_LINKED_BADGE_TYPES
    include_tracked_chores = badge_type in const.INCLUDE_TRACKED_CHORES_BADGE_TYPES
    include_assigned_user_ids = (
        badge_type in const.INCLUDE_ASSIGNED_USER_IDS_BADGE_TYPES
    )
    include_awards = badge_type in const.INCLUDE_AWARDS_BADGE_TYPES
    include_reset_schedule = badge_type in const.INCLUDE_RESET_SCHEDULE_BADGE_TYPES

    # --- Build base badge data ---
    badge_data: dict[str, Any] = {
        const.DATA_BADGE_INTERNAL_ID: internal_id,
        const.DATA_BADGE_NAME: name,
        const.DATA_BADGE_TYPE: badge_type,
        const.DATA_BADGE_DESCRIPTION: str(
            get_field(
                const.CFOF_BADGES_INPUT_DESCRIPTION,
                const.DATA_BADGE_DESCRIPTION,
                const.SENTINEL_EMPTY,
            )
        ),
        const.DATA_BADGE_LABELS: list(
            get_field(
                const.CFOF_BADGES_INPUT_LABELS,
                const.DATA_BADGE_LABELS,
                [],
            )
        ),
        const.DATA_BADGE_ICON: str(
            get_field(
                const.CFOF_BADGES_INPUT_ICON,
                const.DATA_BADGE_ICON,
                const.SENTINEL_EMPTY,
            )
        ),
        # earned_by is runtime state, preserve on update or empty on create
        const.DATA_BADGE_EARNED_BY: (
            existing.get(const.DATA_BADGE_EARNED_BY, []) if existing else []
        ),
    }

    # --- Target Component ---
    if include_target:
        existing_target = existing.get(const.DATA_BADGE_TARGET, {}) if existing else {}

        # For nested dict fields, get directly from user_input or existing nested dict
        if const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE in user_input:
            threshold_value_input = user_input[
                const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE
            ]
        elif existing_target:
            threshold_value_input = existing_target.get(
                const.DATA_BADGE_TARGET_THRESHOLD_VALUE,
                const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE,
            )
        else:
            threshold_value_input = const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE

        try:
            threshold_value = float(threshold_value_input)
        except (TypeError, ValueError, AttributeError):
            const.LOGGER.warning(
                "Could not parse target threshold value '%s'. Using default.",
                threshold_value_input,
            )
            threshold_value = float(const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE)

        if const.CFOF_BADGES_INPUT_MAINTENANCE_RULES in user_input:
            maintenance_rules_input = user_input[
                const.CFOF_BADGES_INPUT_MAINTENANCE_RULES
            ]
        elif existing_target:
            maintenance_rules_input = existing_target.get(
                const.DATA_BADGE_MAINTENANCE_RULES,
                const.DEFAULT_BADGE_MAINTENANCE_THRESHOLD,
            )
        else:
            maintenance_rules_input = const.DEFAULT_BADGE_MAINTENANCE_THRESHOLD

        target_dict: dict[str, Any] = {
            const.DATA_BADGE_TARGET_THRESHOLD_VALUE: threshold_value,
            const.DATA_BADGE_MAINTENANCE_RULES: maintenance_rules_input,
        }

        # Set target_type: cumulative badges always use "points_all_time", others use input or default
        if badge_type == const.BADGE_TYPE_CUMULATIVE:
            target_type = const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_ALL_TIME
        elif const.CFOF_BADGES_INPUT_TARGET_TYPE in user_input:
            target_type = user_input[const.CFOF_BADGES_INPUT_TARGET_TYPE]
        elif existing_target:
            target_type = existing_target.get(
                const.DATA_BADGE_TARGET_TYPE,
                const.DEFAULT_BADGE_TARGET_TYPE,
            )
        else:
            target_type = const.DEFAULT_BADGE_TARGET_TYPE

        target_dict[const.DATA_BADGE_TARGET_TYPE] = target_type

        badge_data[const.DATA_BADGE_TARGET] = target_dict

    # --- Special Occasion Component ---
    if include_special_occasion:
        badge_data[const.DATA_BADGE_SPECIAL_OCCASION_TYPE] = str(
            get_field(
                const.CFOF_BADGES_INPUT_OCCASION_TYPE,
                const.DATA_BADGE_SPECIAL_OCCASION_TYPE,
                const.SENTINEL_EMPTY,
            )
        )

    # --- Achievement-Linked Component ---
    if include_achievement_linked:
        achievement_id = get_field(
            const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT,
            const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT,
            const.SENTINEL_EMPTY,
        )
        # Convert sentinel to empty string for storage
        if achievement_id in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
            achievement_id = ""
        badge_data[const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT] = achievement_id

    # --- Challenge-Linked Component ---
    if include_challenge_linked:
        challenge_id = get_field(
            const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE,
            const.DATA_BADGE_ASSOCIATED_CHALLENGE,
            const.SENTINEL_EMPTY,
        )
        # Convert sentinel to empty string for storage
        if challenge_id in (const.SENTINEL_EMPTY, const.SENTINEL_NO_SELECTION):
            challenge_id = ""
        badge_data[const.DATA_BADGE_ASSOCIATED_CHALLENGE] = challenge_id

    # --- Tracked Chores Component ---
    if include_tracked_chores:
        # Handle nested existing value directly
        if const.CFOF_BADGES_INPUT_SELECTED_CHORES in user_input:
            selected_chores = user_input[const.CFOF_BADGES_INPUT_SELECTED_CHORES]
        elif existing:
            existing_tracked = existing.get(const.DATA_BADGE_TRACKED_CHORES, {})
            selected_chores = existing_tracked.get(
                const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES, []
            )
        else:
            selected_chores = []

        if not isinstance(selected_chores, list):
            selected_chores = [selected_chores] if selected_chores else []
        selected_chores = [
            chore_id
            for chore_id in selected_chores
            if chore_id and chore_id != const.SENTINEL_EMPTY
        ]

        badge_data[const.DATA_BADGE_TRACKED_CHORES] = {
            const.DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES: selected_chores
        }

    # --- Assigned To Component ---
    if include_assigned_user_ids:
        assigned = get_field(
            const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS,
            const.DATA_BADGE_ASSIGNED_USER_IDS,
            [],
        )
        if not isinstance(assigned, list):
            assigned = [assigned] if assigned else []
        assigned = [
            assignee_id
            for assignee_id in assigned
            if assignee_id and assignee_id != const.SENTINEL_EMPTY
        ]
        badge_data[const.DATA_BADGE_ASSIGNED_USER_IDS] = assigned

    # --- Awards Component ---
    if include_awards:
        existing_awards = existing.get(const.DATA_BADGE_AWARDS, {}) if existing else {}

        # Get award points from user_input or existing nested dict
        if const.CFOF_BADGES_INPUT_AWARD_POINTS in user_input:
            points_input = user_input[const.CFOF_BADGES_INPUT_AWARD_POINTS]
        elif existing_awards:
            points_input = existing_awards.get(
                const.DATA_BADGE_AWARDS_AWARD_POINTS,
                const.DEFAULT_BADGE_AWARD_POINTS,
            )
        else:
            points_input = const.DEFAULT_BADGE_AWARD_POINTS

        try:
            points = float(points_input)
        except (TypeError, ValueError, AttributeError):
            const.LOGGER.warning(
                "Could not parse award points value '%s'. Using default.",
                points_input,
            )
            points = float(const.DEFAULT_BADGE_AWARD_POINTS)

        if const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER in user_input:
            multiplier = user_input[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER]
        elif existing_awards:
            multiplier = existing_awards.get(
                const.DATA_BADGE_AWARDS_POINT_MULTIPLIER,
                const.SENTINEL_NONE,
            )
        else:
            multiplier = const.SENTINEL_NONE

        if const.CFOF_BADGES_INPUT_AWARD_ITEMS in user_input:
            award_items = user_input[const.CFOF_BADGES_INPUT_AWARD_ITEMS]
        elif existing_awards:
            award_items = existing_awards.get(
                const.DATA_BADGE_AWARDS_AWARD_ITEMS,
                [],
            )
        else:
            award_items = []

        if not isinstance(award_items, list):
            award_items = [award_items] if award_items else []

        badge_data[const.DATA_BADGE_AWARDS] = {
            const.DATA_BADGE_AWARDS_AWARD_POINTS: points,
            const.DATA_BADGE_AWARDS_POINT_MULTIPLIER: multiplier,
            const.DATA_BADGE_AWARDS_AWARD_ITEMS: award_items,
        }

    # --- Reset Schedule Component ---
    if include_reset_schedule:
        existing_schedule = (
            existing.get(const.DATA_BADGE_RESET_SCHEDULE, {}) if existing else {}
        )

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY in user_input:
            recurring_frequency = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY
            ]
        elif existing_schedule:
            recurring_frequency = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                const.FREQUENCY_WEEKLY,
            )
        else:
            recurring_frequency = const.FREQUENCY_WEEKLY

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE in user_input:
            start_date = user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE]
        elif existing_schedule:
            start_date = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_START_DATE, None
            )
        else:
            start_date = None
        start_date = None if start_date in (None, "") else start_date

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE in user_input:
            end_date = user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE]
        elif existing_schedule:
            end_date = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_END_DATE, None
            )
        else:
            end_date = None
        end_date = None if end_date in (None, "") else end_date

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS in user_input:
            grace_period_days = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS
            ]
        elif existing_schedule:
            grace_period_days = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
                const.DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
            )
        else:
            grace_period_days = const.DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL in user_input:
            custom_interval = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL
            ]
        elif existing_schedule:
            custom_interval = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL,
                const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL,
            )
        else:
            custom_interval = const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL

        if const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT in user_input:
            custom_interval_unit = user_input[
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
            ]
        elif existing_schedule:
            custom_interval_unit = existing_schedule.get(
                const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
                const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
            )
        else:
            custom_interval_unit = (
                const.DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
            )

        badge_data[const.DATA_BADGE_RESET_SCHEDULE] = {
            const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: recurring_frequency,
            const.DATA_BADGE_RESET_SCHEDULE_START_DATE: start_date,
            const.DATA_BADGE_RESET_SCHEDULE_END_DATE: end_date,
            const.DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: grace_period_days,
            const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: custom_interval,
            const.DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: custom_interval_unit,
        }

    # Cast to BadgeData - the dict has all required keys based on badge_type
    return cast("BadgeData", badge_data)


# --- Badge Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_badge():
# - CONFIG fields: Add to _BADGE_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)
#
# NOTE: Badges have complex, type-dependent structures. The preserve set includes
# all base fields and nested config dicts (target, awards, reset_schedule, etc.).
# The only true RUNTIME field is 'earned_by' (list of assignee_ids who earned the badge).

_BADGE_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_BADGE_INTERNAL_ID,
        const.DATA_BADGE_NAME,
        const.DATA_BADGE_TYPE,
        # Description and display
        const.DATA_BADGE_DESCRIPTION,
        const.DATA_BADGE_LABELS,
        const.DATA_BADGE_ICON,
        # Type-specific config dicts (entire nested structures are config)
        const.DATA_BADGE_TARGET,  # Threshold/maintenance rules (config)
        const.DATA_BADGE_AWARDS,  # Points/multiplier/items (config)
        const.DATA_BADGE_RESET_SCHEDULE,  # Periodic reset rules (config)
        const.DATA_BADGE_TRACKED_CHORES,  # Tracked chore selection (config)
        # Assignment and linking (config)
        const.DATA_BADGE_ASSIGNED_USER_IDS,
        const.DATA_BADGE_SPECIAL_OCCASION_TYPE,
        const.DATA_BADGE_ASSOCIATED_ACHIEVEMENT,
        const.DATA_BADGE_ASSOCIATED_CHALLENGE,
    }
)

# --- Badge user runtime fields (for data_reset_badges) ---
# These are user-record runtime structures owned by GamificationManager.
# On data reset: CLEAR these structures for affected assignee-capable users.

_BADGE_USER_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {
        const.DATA_USER_BADGES_EARNED,  # Badge award history
        const.DATA_USER_BADGE_PROGRESS,  # Current badge progress
        const.DATA_USER_CUMULATIVE_BADGE_PROGRESS,  # Cumulative badge tracking
    }
)


# ==============================================================================
# ACHIEVEMENTS
# ==============================================================================

# Note: CFOF_ACHIEVEMENTS_INPUT_* values are now aligned with DATA_ACHIEVEMENT_*
# values (Phase 6 CFOF Key Alignment). map_cfof_to_achievement_data() is retained
# for explicit key filtering, but performs mostly identity mapping.

# Mapping from CFOF_* form keys to DATA_* storage keys for achievements
# NOTE (Phase 6 CFOF Key Alignment): Most CFOF_* values now equal DATA_* values
# (e.g., CFOF_ACHIEVEMENTS_INPUT_NAME = "name" = DATA_ACHIEVEMENT_NAME).
# This mapping is retained for explicit documentation and future-proofing,
# but currently performs identity mapping for most fields.
_CFOF_TO_ACHIEVEMENT_DATA_MAPPING: dict[str, str] = {
    const.CFOF_ACHIEVEMENTS_INPUT_NAME: const.DATA_ACHIEVEMENT_NAME,
    const.CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION: const.DATA_ACHIEVEMENT_DESCRIPTION,
    const.CFOF_ACHIEVEMENTS_INPUT_LABELS: const.DATA_ACHIEVEMENT_LABELS,
    const.CFOF_ACHIEVEMENTS_INPUT_ICON: const.DATA_ACHIEVEMENT_ICON,
    const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS: const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
    const.CFOF_ACHIEVEMENTS_INPUT_TYPE: const.DATA_ACHIEVEMENT_TYPE,
    const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID: const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID,
    const.CFOF_ACHIEVEMENTS_INPUT_CRITERIA: const.DATA_ACHIEVEMENT_CRITERIA,
    const.CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE: const.DATA_ACHIEVEMENT_TARGET_VALUE,
    const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS: const.DATA_ACHIEVEMENT_REWARD_POINTS,
}


def map_cfof_to_achievement_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert CFOF_* form keys to DATA_* storage keys for achievements.

    NOTE (Phase 6 CFOF Key Alignment): Since CFOF_* values are now aligned with
    DATA_* values, this function performs mostly identity mapping. User_input can
    be passed directly to build_achievement() for fields with aligned keys.
    This function is retained for explicit key filtering and documentation.

    Args:
        user_input: Dict with CFOF_ACHIEVEMENTS_INPUT_* keys from UI forms

    Returns:
        Dict with DATA_ACHIEVEMENT_* keys for build_achievement() consumption
    """
    return {
        _CFOF_TO_ACHIEVEMENT_DATA_MAPPING.get(key, key): value
        for key, value in user_input.items()
        if key in _CFOF_TO_ACHIEVEMENT_DATA_MAPPING
    }


def validate_achievement_data(
    data: dict[str, Any],
    existing_achievements: dict[str, Any] | None = None,
    *,
    current_achievement_id: str | None = None,
) -> dict[str, str]:
    """Validate achievement business rules - SINGLE SOURCE OF TRUTH.

    This function contains all achievement validation logic used by both:
    - Options Flow (UI) via flow_helpers.validate_achievements_inputs()
    - Services (API) if added in future

    Works with DATA_* keys (canonical storage format).

    Args:
        data: Achievement data dict with DATA_* keys
        existing_achievements: All existing achievements for duplicate checking
        current_achievement_id: ID of achievement being updated (exclude from dupe check)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty
        2. Name not duplicate
        3. Streak type requires chore selection
    """
    errors: dict[str, str] = {}

    # === 1. Name not empty ===
    name = data.get(const.DATA_ACHIEVEMENT_NAME, "")
    if isinstance(name, str):
        name = name.strip()

    if not name:
        errors[const.CFOP_ERROR_ACHIEVEMENT_NAME] = (
            const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_NAME
        )
        return errors

    # === 2. Duplicate name check ===
    if name and existing_achievements:
        for ach_id, ach_data in existing_achievements.items():
            if ach_id == current_achievement_id:
                continue  # Skip self when updating
            if ach_data.get(const.DATA_ACHIEVEMENT_NAME) == name:
                errors[const.CFOP_ERROR_ACHIEVEMENT_NAME] = (
                    const.TRANS_KEY_CFOF_DUPLICATE_ACHIEVEMENT
                )
                return errors

    # === 3. At least one assignee must be assigned ===
    assigned_assignees = data.get(const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, [])
    if not assigned_assignees:
        errors[const.CFOP_ERROR_ASSIGNED_USER_IDS] = (
            const.TRANS_KEY_CFOF_ACHIEVEMENT_NO_ASSIGNEES_ASSIGNED
        )
        return errors

    # === 4. Streak type requires chore selection ===
    achievement_type = data.get(const.DATA_ACHIEVEMENT_TYPE)
    if achievement_type == const.ACHIEVEMENT_TYPE_STREAK:
        chore_id = data.get(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID)
        if not chore_id or chore_id in (
            const.SENTINEL_EMPTY,
            const.SENTINEL_NONE_TEXT,
            const.SENTINEL_NO_SELECTION,
        ):
            errors[const.CFOP_ERROR_SELECT_CHORE_ID] = (
                const.TRANS_KEY_CFOF_CHORE_MUST_BE_SELECTED
            )
            return errors

    return errors


def build_achievement(
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build achievement data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for achievement field handling.
    One function handles both create (existing=None) and update (existing=dict).

    Args:
        user_input: Data with DATA_* keys (may have missing fields)
        existing: None for create, existing achievement data for update

    Returns:
        Complete dict ready for storage with DATA_* keys

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies defaults
        achievement = build_achievement({DATA_ACHIEVEMENT_NAME: "First Streak"})

        # UPDATE mode - preserves existing fields not in user_input
        achievement = build_achievement({DATA_ACHIEVEMENT_TARGET_VALUE: 10}, existing=old)
    """
    is_create = existing is None

    def get_field(data_key: str, default: Any) -> Any:
        """Get field value: user_input > existing > default."""
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(const.DATA_ACHIEVEMENT_NAME, "")
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.DATA_ACHIEVEMENT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_NAME,
        )
    if const.DATA_ACHIEVEMENT_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.DATA_ACHIEVEMENT_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_NAME,
        )

    # --- Generate or preserve internal_id ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(
            const.DATA_ACHIEVEMENT_INTERNAL_ID, str(uuid.uuid4())
        )

    # --- Build complete achievement structure ---
    return {
        const.DATA_ACHIEVEMENT_INTERNAL_ID: internal_id,
        const.DATA_ACHIEVEMENT_NAME: name,
        const.DATA_ACHIEVEMENT_DESCRIPTION: str(
            get_field(const.DATA_ACHIEVEMENT_DESCRIPTION, const.SENTINEL_EMPTY)
        ),
        const.DATA_ACHIEVEMENT_LABELS: _normalize_list_field(
            get_field(const.DATA_ACHIEVEMENT_LABELS, [])
        ),
        const.DATA_ACHIEVEMENT_ICON: str(
            get_field(const.DATA_ACHIEVEMENT_ICON, const.SENTINEL_EMPTY)
        ),
        const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: _normalize_list_field(
            get_field(const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS, [])
        ),
        const.DATA_ACHIEVEMENT_TYPE: str(
            get_field(const.DATA_ACHIEVEMENT_TYPE, const.ACHIEVEMENT_TYPE_STREAK)
        ),
        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: str(
            get_field(const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY)
        ),
        const.DATA_ACHIEVEMENT_CRITERIA: str(
            get_field(const.DATA_ACHIEVEMENT_CRITERIA, const.SENTINEL_EMPTY)
        ).strip(),
        const.DATA_ACHIEVEMENT_TARGET_VALUE: float(
            get_field(
                const.DATA_ACHIEVEMENT_TARGET_VALUE, const.DEFAULT_ACHIEVEMENT_TARGET
            )
        ),
        const.DATA_ACHIEVEMENT_REWARD_POINTS: float(
            get_field(
                const.DATA_ACHIEVEMENT_REWARD_POINTS,
                const.DEFAULT_ACHIEVEMENT_REWARD_POINTS,
            )
        ),
        # Progress tracking - preserve from existing or initialize empty
        const.DATA_ACHIEVEMENT_PROGRESS: dict(
            get_field(const.DATA_ACHIEVEMENT_PROGRESS, {})
        ),
    }


# --- Achievement Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_achievement():
# - CONFIG fields: Add to _ACHIEVEMENT_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)
#
# NOTE: Achievements store progress directly on the achievement record (not assignee-side).
# On data reset, PROGRESS is cleared but CONFIG fields are preserved.

_ACHIEVEMENT_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_ACHIEVEMENT_INTERNAL_ID,
        const.DATA_ACHIEVEMENT_NAME,
        # Description and display
        const.DATA_ACHIEVEMENT_DESCRIPTION,
        const.DATA_ACHIEVEMENT_LABELS,
        const.DATA_ACHIEVEMENT_ICON,
        # Configuration
        const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS,
        const.DATA_ACHIEVEMENT_TYPE,
        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID,
        const.DATA_ACHIEVEMENT_CRITERIA,
        const.DATA_ACHIEVEMENT_TARGET_VALUE,
        const.DATA_ACHIEVEMENT_REWARD_POINTS,
        # NOTE: PROGRESS is NOT preserved - it's the only runtime field
    }
)


# ==============================================================================
# CHALLENGES
# ==============================================================================

# Note: CFOF_CHALLENGES_INPUT_* values are now aligned with DATA_CHALLENGE_*
# values (Phase 6 CFOF Key Alignment). map_cfof_to_challenge_data() is retained
# for explicit key filtering and date handling, but performs mostly identity mapping.

# Mapping from CFOF_* form keys to DATA_* storage keys for challenges
# NOTE (Phase 6 CFOF Key Alignment): Most CFOF_* values now equal DATA_* values
# (e.g., CFOF_CHALLENGES_INPUT_NAME = "name" = DATA_CHALLENGE_NAME).
# This mapping is retained for explicit documentation and future-proofing,
# but currently performs identity mapping for most fields.
_CFOF_TO_CHALLENGE_DATA_MAPPING: dict[str, str] = {
    const.CFOF_CHALLENGES_INPUT_NAME: const.DATA_CHALLENGE_NAME,
    const.CFOF_CHALLENGES_INPUT_DESCRIPTION: const.DATA_CHALLENGE_DESCRIPTION,
    const.CFOF_CHALLENGES_INPUT_LABELS: const.DATA_CHALLENGE_LABELS,
    const.CFOF_CHALLENGES_INPUT_ICON: const.DATA_CHALLENGE_ICON,
    const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS: const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
    const.CFOF_CHALLENGES_INPUT_TYPE: const.DATA_CHALLENGE_TYPE,
    const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID: const.DATA_CHALLENGE_SELECTED_CHORE_ID,
    const.CFOF_CHALLENGES_INPUT_CRITERIA: const.DATA_CHALLENGE_CRITERIA,
    const.CFOF_CHALLENGES_INPUT_TARGET_VALUE: const.DATA_CHALLENGE_TARGET_VALUE,
    const.CFOF_CHALLENGES_INPUT_REWARD_POINTS: const.DATA_CHALLENGE_REWARD_POINTS,
    const.CFOF_CHALLENGES_INPUT_START_DATE: const.DATA_CHALLENGE_START_DATE,
    const.CFOF_CHALLENGES_INPUT_END_DATE: const.DATA_CHALLENGE_END_DATE,
}


def map_cfof_to_challenge_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert CFOF_* form keys to DATA_* storage keys for challenges.

    NOTE (Phase 6 CFOF Key Alignment): Since CFOF_* values are now aligned with
    DATA_* values, this function performs mostly identity mapping. User_input can
    be passed directly to build_challenge() for fields with aligned keys.
    This function is retained for explicit key filtering and documentation.

    Args:
        user_input: Dict with CFOF_CHALLENGES_INPUT_* keys from UI forms

    Returns:
        Dict with DATA_CHALLENGE_* keys for build_challenge() consumption
    """
    return {
        _CFOF_TO_CHALLENGE_DATA_MAPPING.get(key, key): value
        for key, value in user_input.items()
        if key in _CFOF_TO_CHALLENGE_DATA_MAPPING
    }


def validate_challenge_data(
    data: dict[str, Any],
    existing_challenges: dict[str, Any] | None = None,
    *,
    current_challenge_id: str | None = None,
) -> dict[str, str]:
    """Validate challenge business rules - SINGLE SOURCE OF TRUTH.

    This function contains all challenge validation logic used by both:
    - Options Flow (UI) via flow_helpers.validate_challenges_inputs()
    - Services (API) if added in future

    Works with DATA_* keys (canonical storage format).

    Args:
        data: Challenge data dict with DATA_* keys
        existing_challenges: All existing challenges for duplicate checking
        current_challenge_id: ID of challenge being updated (exclude from dupe check)

    Returns:
        Dict of errors: {error_field: translation_key}
        Empty dict means validation passed.

    Validation Rules:
        1. Name not empty
        2. Name not duplicate
        3. Dates required and valid
        4. End date after start date
        5. Target value > 0
        6. Reward points >= 0
    """
    errors: dict[str, str] = {}

    # === 1. Name not empty ===
    name = data.get(const.DATA_CHALLENGE_NAME, "")
    if isinstance(name, str):
        name = name.strip()

    if not name:
        errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_NAME_REQUIRED
        return errors

    # === 2. At least one assignee must be assigned ===
    assigned_assignees = data.get(const.DATA_CHALLENGE_ASSIGNED_USER_IDS, [])
    if not assigned_assignees:
        errors[const.CFOP_ERROR_ASSIGNED_USER_IDS] = (
            const.TRANS_KEY_CFOF_CHALLENGE_NO_ASSIGNEES_ASSIGNED
        )
        return errors

    # === 3. Duplicate name check (case-insensitive) ===
    if name and existing_challenges:
        for chal_id, chal_data in existing_challenges.items():
            if chal_id == current_challenge_id:
                continue  # Skip self when updating
            if chal_data.get(const.DATA_CHALLENGE_NAME, "").lower() == name.lower():
                errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_NAME_DUPLICATE
                return errors

    # === 4. Dates required ===
    start_date_raw = data.get(const.DATA_CHALLENGE_START_DATE)
    end_date_raw = data.get(const.DATA_CHALLENGE_END_DATE)

    if not start_date_raw or not end_date_raw:
        errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_DATES_REQUIRED
        return errors

    # === 5. Date parsing and end > start validation ===
    try:
        start_dt = dt_parse(
            start_date_raw,
            default_tzinfo=const.DEFAULT_TIME_ZONE,
            return_type=const.HELPER_RETURN_DATETIME_UTC,
        )
        end_dt = dt_parse(
            end_date_raw,
            default_tzinfo=const.DEFAULT_TIME_ZONE,
            return_type=const.HELPER_RETURN_DATETIME_UTC,
        )

        # Type guard: ensure both are datetime.datetime
        if not isinstance(start_dt, datetime.datetime):
            errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_INVALID_DATE
            return errors
        if not isinstance(end_dt, datetime.datetime):
            errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_INVALID_DATE
            return errors

        # End must be after start
        if end_dt <= start_dt:
            errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_END_BEFORE_START
            return errors

    except (ValueError, TypeError) as ex:
        const.LOGGER.warning("Challenge date parsing error: %s", ex)
        errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_INVALID_DATE
        return errors

    # === 6. Target value > 0 ===
    if const.DATA_CHALLENGE_TARGET_VALUE in data:
        try:
            target = float(data[const.DATA_CHALLENGE_TARGET_VALUE])
            if target <= 0:
                errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_TARGET_INVALID
                return errors
        except (ValueError, TypeError):
            errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_TARGET_INVALID
            return errors

    # === 7. Reward points >= 0 ===
    if const.DATA_CHALLENGE_REWARD_POINTS in data:
        try:
            points = float(data[const.DATA_CHALLENGE_REWARD_POINTS])
            if points < 0:
                errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_POINTS_NEGATIVE
                return errors
        except (ValueError, TypeError):
            errors["base"] = const.TRANS_KEY_CFOF_CHALLENGE_POINTS_INVALID
            return errors

    return errors


def build_challenge(
    user_input: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build challenge data for create or update operations.

    This is the SINGLE SOURCE OF TRUTH for challenge field handling.
    One function handles both create (existing=None) and update (existing=dict).

    Args:
        user_input: Data with DATA_* keys (may have missing fields)
        existing: None for create, existing challenge data for update


    Returns:
        Complete dict ready for storage with DATA_* keys

    Raises:
        EntityValidationError: If name validation fails (empty/whitespace)

    Examples:
        # CREATE mode - generates UUID, applies defaults
        challenge = build_challenge({DATA_CHALLENGE_NAME: "Weekly Goal"})

        # UPDATE mode - preserves existing fields not in user_input
        challenge = build_challenge({DATA_CHALLENGE_TARGET_VALUE: 5}, existing=old)
    """
    is_create = existing is None

    def get_field(data_key: str, default: Any) -> Any:
        """Get field value: user_input > existing > default."""
        if data_key in user_input:
            return user_input[data_key]
        if existing is not None:
            return existing.get(data_key, default)
        return default

    # --- Name validation (required for create, optional for update) ---
    raw_name = get_field(const.DATA_CHALLENGE_NAME, "")
    name = str(raw_name).strip() if raw_name else ""

    if is_create and not name:
        raise EntityValidationError(
            field=const.DATA_CHALLENGE_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_CHALLENGE_NAME,
        )
    if const.DATA_CHALLENGE_NAME in user_input and not name:
        raise EntityValidationError(
            field=const.DATA_CHALLENGE_NAME,
            translation_key=const.TRANS_KEY_CFOF_INVALID_CHALLENGE_NAME,
        )

    # --- Generate or preserve internal_id ---
    if is_create or existing is None:
        internal_id = str(uuid.uuid4())
    else:
        internal_id = existing.get(const.DATA_CHALLENGE_INTERNAL_ID, str(uuid.uuid4()))

    # --- Build complete challenge structure ---
    return {
        const.DATA_CHALLENGE_INTERNAL_ID: internal_id,
        const.DATA_CHALLENGE_NAME: name,
        const.DATA_CHALLENGE_DESCRIPTION: str(
            get_field(const.DATA_CHALLENGE_DESCRIPTION, const.SENTINEL_EMPTY)
        ),
        const.DATA_CHALLENGE_LABELS: _normalize_list_field(
            get_field(const.DATA_CHALLENGE_LABELS, [])
        ),
        const.DATA_CHALLENGE_ICON: str(
            get_field(const.DATA_CHALLENGE_ICON, const.SENTINEL_EMPTY)
        ),
        const.DATA_CHALLENGE_ASSIGNED_USER_IDS: _normalize_list_field(
            get_field(const.DATA_CHALLENGE_ASSIGNED_USER_IDS, [])
        ),
        const.DATA_CHALLENGE_TYPE: str(
            get_field(const.DATA_CHALLENGE_TYPE, const.CHALLENGE_TYPE_DAILY_MIN)
        ),
        const.DATA_CHALLENGE_SELECTED_CHORE_ID: str(
            get_field(const.DATA_CHALLENGE_SELECTED_CHORE_ID, const.SENTINEL_EMPTY)
        ),
        const.DATA_CHALLENGE_CRITERIA: str(
            get_field(const.DATA_CHALLENGE_CRITERIA, const.SENTINEL_EMPTY)
        ).strip(),
        const.DATA_CHALLENGE_TARGET_VALUE: float(
            get_field(const.DATA_CHALLENGE_TARGET_VALUE, const.DEFAULT_CHALLENGE_TARGET)
        ),
        const.DATA_CHALLENGE_REWARD_POINTS: float(
            get_field(
                const.DATA_CHALLENGE_REWARD_POINTS,
                const.DEFAULT_CHALLENGE_REWARD_POINTS,
            )
        ),
        const.DATA_CHALLENGE_START_DATE: str(
            get_field(const.DATA_CHALLENGE_START_DATE, const.SENTINEL_EMPTY)
        ),
        const.DATA_CHALLENGE_END_DATE: str(
            get_field(const.DATA_CHALLENGE_END_DATE, const.SENTINEL_EMPTY)
        ),
        # Progress tracking - preserve from existing or initialize empty
        const.DATA_CHALLENGE_PROGRESS: dict(
            get_field(const.DATA_CHALLENGE_PROGRESS, {})
        ),
    }


# --- Challenge Data Reset Support ---
# MAINTENANCE CONTRACT: When adding fields to build_challenge():
# - CONFIG fields: Add to _CHALLENGE_DATA_RESET_PRESERVE_FIELDS (preserved during data reset)
# - RUNTIME fields: No change needed (auto-cleared to defaults on data reset)
#
# NOTE: Challenges store progress directly on the challenge record (not assignee-side).
# On data reset, PROGRESS is cleared but CONFIG fields are preserved.

_CHALLENGE_DATA_RESET_PRESERVE_FIELDS: frozenset[str] = frozenset(
    {
        # Core identification
        const.DATA_CHALLENGE_INTERNAL_ID,
        const.DATA_CHALLENGE_NAME,
        # Description and display
        const.DATA_CHALLENGE_DESCRIPTION,
        const.DATA_CHALLENGE_LABELS,
        const.DATA_CHALLENGE_ICON,
        # Configuration
        const.DATA_CHALLENGE_ASSIGNED_USER_IDS,
        const.DATA_CHALLENGE_TYPE,
        const.DATA_CHALLENGE_SELECTED_CHORE_ID,
        const.DATA_CHALLENGE_CRITERIA,
        const.DATA_CHALLENGE_TARGET_VALUE,
        const.DATA_CHALLENGE_REWARD_POINTS,
        const.DATA_CHALLENGE_START_DATE,
        const.DATA_CHALLENGE_END_DATE,
        # NOTE: PROGRESS is NOT preserved - it's the only runtime field
    }
)
