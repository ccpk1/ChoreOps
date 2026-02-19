# File: flow_helpers.py
"""Helpers for the ChoreOps integration's Config and Options flow.

Provides schema builders, UI validation wrappers, and data transformation for
internal_id-based entity management.

## UNIFIED VALIDATION & DATA BUILDING ARCHITECTURE (v0.5.0+) ##

All entity types follow a consistent pattern across two modules:

### flow_helpers.py (This Module) - UI Layer
**Responsibilities:**
1. Schema Building: `build_<entity>_schema()` - Voluptuous schemas for HA UI forms
2. UI Validation: `validate_<entity>_inputs()` - Transform CFOF_* keys and validate
3. Data Building (simple): `build_<entity>_data()` - For system settings only

### data_builders.py - Core Logic Layer
**Responsibilities:**
1. Core Validation: `validate_<entity>_data()` - Single source of truth validation
2. Entity Building: `build_<entity>()` - Build complete entity with UUIDs, timestamps
3. Complex Mapping: `map_cfof_to_<entity>_data()` - Only for entities with complex fields

## LAYER ARCHITECTURE ##

### Layer 1: Schema Building (flow_helpers)
**Function:** `build_<entity>_schema(default, assignees_dict, ...) -> vol.Schema`
**Purpose:** Construct voluptuous schemas for Home Assistant UI forms
**Keys:** Uses CFOF_* constants (Config Flow / Options Flow form field names)

### Layer 2: UI Validation Wrapper (flow_helpers)
**Function:** `validate_<entity>_inputs(user_input, existing_dict, ...) -> errors_dict`
**Purpose:** Transform CFOF_* keys to DATA_* keys and delegate to data_builders
**Returns:** Error dict (empty = no errors)

### Layer 3: Core Validation (data_builders)
**Function:** `validate_<entity>_data(data, existing_dict, ...) -> errors_dict`
**Purpose:** Core validation logic with DATA_* keys - the authoritative validation
**Keys:** Uses DATA_* constants (storage format)

### Layer 4: Entity Building (data_builders)
**Function:** `build_<entity>(data, existing=None) -> normalized_dict`
**Purpose:** Build complete entity structure with defaults, UUIDs, timestamps
**Returns:** Fully normalized entity dict ready for storage

## CALL SITE PATTERNS ##

### Simple Entities (Aligned Keys - Most Common)
For entities with CFOF_* values aligned with DATA_* values:
```python
# Step 1: UI validation (transforms keys internally)
errors = fh.validate_reward_inputs(user_input, existing_rewards)

if not errors:
    try:
        # Step 2: Build entity directly from user_input (keys are aligned!)
        reward = db.build_reward(user_input)
        internal_id = reward[const.DATA_REWARD_INTERNAL_ID]

        # Step 3: Direct storage write
        coordinator._data[const.DATA_REWARDS][internal_id] = dict(reward)
        coordinator._persist()

    except EntityValidationError as err:
        errors[err.field] = err.translation_key
```

### Complex Entities (Require Mapping)
For entities with complex field transformations (e.g., daily_multi_times parsing):
```python
# Step 1: UI validation
errors = fh.validate_chore_inputs(user_input, existing_chores, ...)

if not errors:
    try:
        # Step 2: Map complex fields (daily_multi_times string → list, etc.)
        data_input = db.map_cfof_to_chore_data(user_input)

        # Step 3: Build entity from mapped data
        chore = db.build_chore(data_input)
        internal_id = chore[const.DATA_CHORE_INTERNAL_ID]

        # Step 4: Direct storage write
        coordinator._data[const.DATA_CHORES][internal_id] = dict(chore)
        coordinator._persist()

    except EntityValidationError as err:
        errors[err.field] = err.translation_key
```

## KEY MAPPING (Phase 6 CFOF Key Alignment) ##

CFOF_* constant values are now aligned with DATA_* values where possible,
eliminating the need for mapping functions. This simplifies the call site pattern.

**Entities with aligned keys (pass user_input directly to build_*()):**
- Users: `CFOF_USERS_INPUT_NAME = "name"` matches `DATA_USER_NAME = "name"`
- Rewards: `CFOF_REWARDS_INPUT_NAME = "name"` matches `DATA_REWARD_NAME = "name"`
- Bonuses: `CFOF_BONUSES_INPUT_NAME = "name"` matches `DATA_BONUS_NAME = "name"`
- Penalties: `CFOF_PENALTIES_INPUT_NAME = "name"` matches `DATA_PENALTY_NAME = "name"`
- Achievements: `CFOF_ACHIEVEMENTS_INPUT_NAME = "name"` matches `DATA_ACHIEVEMENT_NAME`
- Challenges: `CFOF_CHALLENGES_INPUT_NAME = "name"` matches `DATA_CHALLENGE_NAME`
- Chores: `CFOF_CHORES_INPUT_NAME = "name"` matches `DATA_CHORE_NAME = "name"`

**Entities requiring explicit CFOF→DATA mapping (complex transformations):**
- Chores: `db.map_cfof_to_chore_data()` - Handles daily_multi_times string→list parsing
  and per-assignee configuration mapping (simple field keys are aligned)

**Entities with embedded key mapping (complex conditional fields):**
- Badges: `build_badge()` handles CFOF→DATA mapping internally via get_field() closure
  (Badge fields vary by badge_type, so mapping is embedded in build function)

## BENEFITS OF THIS ARCHITECTURE ##

1. **Single Source of Truth:** All validation logic lives in data_builders
2. **DRY:** No duplicate validation between config_flow and options_flow
3. **Testable:** data_builders validation can be unit tested in isolation
4. **Consistent:** Same pattern for all entity types
5. **Type Safe:** Clear key transformation at well-defined boundaries
6. **Simplified Keys:** CFOF_* and DATA_* values aligned where possible
7. **Centralized Building:** All entity construction in data_builders.build_*()
"""

# pyright: reportArgumentType=false
# Reason: Voluptuous schema definitions use dynamic typing that pyright cannot infer.
# The selector.SelectSelector and vol.Schema patterns are runtime-validated by Home Assistant.

import datetime
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv, selector
import voluptuous as vol

from .. import const
from ..utils.dt_utils import dt_parse, dt_parse_duration
from . import translation_helpers as th

# =============================================================================
# INPUT VALIDATION HELPERS
# =============================================================================


def validate_duration_string(value: str) -> str:
    """Validate duration string format and reasonable range.

    Args:
        value: Duration string like "30m", "1d 6h", "0" (disabled)

    Returns:
        Original value if valid

    Raises:
        vol.Invalid: If format is invalid or value out of range
    """
    if not value or value.strip() == "0":
        return value  # "0" or empty = disabled (valid)

    td = dt_parse_duration(value)
    if td is None:
        raise vol.Invalid(
            f"Invalid duration format: '{value}'. "
            "Expected format: '30m', '1h', '1d 6h 30m', or '0' to disable."
        )

    # Range check: 1 minute to 30 days
    from datetime import timedelta

    if td < timedelta(minutes=1):
        raise vol.Invalid("Duration must be at least 1 minute")
    if td > timedelta(days=30):
        raise vol.Invalid("Duration must not exceed 30 days")

    return value


# ----------------------------------------------------------------------------------
# POINTS SCHEMA
# ----------------------------------------------------------------------------------


def build_points_schema(
    default_label=const.DEFAULT_POINTS_LABEL, default_icon=const.DEFAULT_POINTS_ICON
):
    """Build a schema for points label & icon."""
    return vol.Schema(
        {
            vol.Required(
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL, default=default_label
            ): str,
            vol.Optional(
                const.CFOF_SYSTEM_INPUT_POINTS_ICON, default=default_icon
            ): selector.IconSelector(),
        }
    )


def build_points_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build points configuration data from user input.

    Converts form input (CONF_* keys) to system settings format.

    Args:
        user_input: Dictionary containing user inputs from the form.

    Returns:
        Dictionary with points label and icon configuration.
    """
    return {
        const.CONF_POINTS_LABEL: user_input.get(
            const.CFOF_SYSTEM_INPUT_POINTS_LABEL, const.DEFAULT_POINTS_LABEL
        ),
        const.CONF_POINTS_ICON: user_input.get(
            const.CFOF_SYSTEM_INPUT_POINTS_ICON, const.DEFAULT_POINTS_ICON
        ),
    }


def validate_points_inputs(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate points configuration inputs.

    Args:
        user_input: Dictionary containing user inputs from the form.

    Returns:
        Dictionary of errors (empty if validation passes).
    """
    errors = {}

    points_label = user_input.get(const.CFOF_SYSTEM_INPUT_POINTS_LABEL, "").strip()

    # Validate label is not empty
    if not points_label:
        errors["base"] = const.TRANS_KEY_CFOF_POINTS_LABEL_REQUIRED

    return errors


# ----------------------------------------------------------------------------------
# USER PROFILE SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------

# Section organization (intentional):
# 1) Sectioned USER-form pipeline for current config/options UX
#    - constants: USER_SECTION_* and USER_*_FIELDS
#    - internals: _build/_normalize/_map/_validate *_impl helpers
#    - public wrappers: build_user_schema, normalize_user_form_input,
#      map_user_form_errors, validate_users_inputs
#
# Sectioned schema + validation is the only supported path for USER forms.


USER_SECTION_IDENTITY_PROFILE = "section_identity_profile"
USER_SECTION_SYSTEM_USAGE = "section_system_usage"
USER_SECTION_ADMIN_APPROVAL = "section_admin_approval"

# Section field group contracts:
# - Identity profile: personal mapping and notification preferences
# - System usage: assignment + workflow/gamification capability flags
# - Admin approval: approval/management flags and associated user links

USER_IDENTITY_FIELDS = (
    const.CFOF_USERS_INPUT_NAME,
    const.CFOF_USERS_INPUT_HA_USER_ID,
    const.CFOF_USERS_INPUT_DASHBOARD_LANGUAGE,
    const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE,
)

USER_SYSTEM_USAGE_FIELDS = (
    const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
    const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW,
    const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION,
)

USER_ADMIN_APPROVAL_FIELDS = (
    const.CFOF_USERS_INPUT_CAN_APPROVE,
    const.CFOF_USERS_INPUT_CAN_MANAGE,
    const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
)


def _build_user_section_suggested_values_impl(
    flat_values: dict[str, Any],
) -> dict[str, Any]:
    """Build sectioned suggested values from flat persisted user values."""
    return {
        USER_SECTION_IDENTITY_PROFILE: {
            key: flat_values[key] for key in USER_IDENTITY_FIELDS if key in flat_values
        },
        USER_SECTION_SYSTEM_USAGE: {
            key: flat_values[key]
            for key in USER_SYSTEM_USAGE_FIELDS
            if key in flat_values
        },
        USER_SECTION_ADMIN_APPROVAL: {
            key: flat_values[key]
            for key in USER_ADMIN_APPROVAL_FIELDS
            if key in flat_values
        },
    }


def _normalize_user_form_input_impl(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize user form payload for sectioned and non-sectioned modes.

    Home Assistant `section()` wraps values under section keys. This helper
    flattens those values so downstream validation/builders consume one shape.
    """
    normalized: dict[str, Any] = dict(user_input)
    for section_key in (
        USER_SECTION_IDENTITY_PROFILE,
        USER_SECTION_SYSTEM_USAGE,
        USER_SECTION_ADMIN_APPROVAL,
    ):
        section_data = normalized.pop(section_key, None)
        if isinstance(section_data, dict):
            normalized.update(section_data)
    return normalized


async def _build_user_schema_impl(
    hass,
    users,
    assignees_dict,
):
    """Build sectioned USER-form schema for add/edit user profile.

    Uses static defaults for optional fields - use suggested_value for edit forms.

    Notification configuration simplified to single service selector:
    - Service selected = notifications enabled to that service
    - None selected = notifications disabled
    """
    # Use SENTINEL_NO_SELECTION for "None" option - empty string doesn't work reliably
    user_options = [
        {"value": const.SENTINEL_NO_SELECTION, "label": const.LABEL_NONE}
    ] + [{"value": user.id, "label": user.name} for user in users]
    assignee_options = [
        {"value": assignee_id, "label": assignee_name}
        for assignee_name, assignee_id in assignees_dict.items()
    ]
    # Notification service options: None = disabled, service = enabled
    notify_options = [
        {"value": const.SENTINEL_NO_SELECTION, "label": const.LABEL_DISABLED},
        *_get_notify_services(hass),
    ]

    # Get available dashboard languages
    language_options = await th.get_available_dashboard_languages(hass)

    identity_fields: dict[Any, Any] = {
        vol.Required(const.CFOF_USERS_INPUT_NAME, default=const.SENTINEL_EMPTY): str,
        vol.Optional(
            const.CFOF_USERS_INPUT_HA_USER_ID,
            default=const.SENTINEL_NO_SELECTION,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=user_options,
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=False,
            )
        ),
        vol.Optional(
            const.CFOF_USERS_INPUT_DASHBOARD_LANGUAGE,
            default=const.DEFAULT_DASHBOARD_LANGUAGE,
        ): selector.LanguageSelector(
            selector.LanguageSelectorConfig(
                languages=language_options,
                native_name=True,
            )
        ),
        vol.Optional(
            const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE,
            default=const.SENTINEL_NO_SELECTION,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=cast("list[selector.SelectOptionDict]", notify_options),
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=False,
            )
        ),
    }

    usage_fields: dict[Any, Any] = {
        vol.Optional(
            const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
            default=False,
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW,
            default=False,
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION,
            default=False,
        ): selector.BooleanSelector(),
    }

    admin_fields: dict[Any, Any] = {
        vol.Optional(
            const.CFOF_USERS_INPUT_CAN_APPROVE,
            default=False,
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_USERS_INPUT_CAN_MANAGE,
            default=False,
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
            default=[],
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=cast("list[selector.SelectOptionDict]", assignee_options),
                translation_key=const.TRANS_KEY_FLOW_HELPERS_ASSOCIATED_USER_IDS,
                multiple=True,
            )
        ),
    }

    return vol.Schema(
        {
            vol.Optional(USER_SECTION_IDENTITY_PROFILE): section(
                vol.Schema(identity_fields)
            ),
            vol.Optional(USER_SECTION_SYSTEM_USAGE): section(vol.Schema(usage_fields)),
            vol.Optional(USER_SECTION_ADMIN_APPROVAL): section(
                vol.Schema(admin_fields),
                {"collapsed": True},
            ),
        },
        extra=vol.ALLOW_EXTRA,
    )


def _map_user_form_errors_impl(errors: dict[str, str]) -> dict[str, str]:
    """Map field-level errors to section aliases for sectioned UI rendering.

    This preserves original field keys and additionally maps section keys so
    the UI can highlight collapsed groups with validation issues.
    """
    mapped_errors: dict[str, str] = {}

    field_to_section: dict[str, str] = {
        **dict.fromkeys(USER_IDENTITY_FIELDS, USER_SECTION_IDENTITY_PROFILE),
        **dict.fromkeys(USER_SYSTEM_USAGE_FIELDS, USER_SECTION_SYSTEM_USAGE),
        **dict.fromkeys(USER_ADMIN_APPROVAL_FIELDS, USER_SECTION_ADMIN_APPROVAL),
    }

    field_aliases = {
        const.CFOP_ERROR_CHORE_OPTIONS: const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
    }

    for error_field, translation_key in errors.items():
        mapped_errors[error_field] = translation_key

        normalized_field = field_aliases.get(error_field, error_field)
        mapped_errors[normalized_field] = translation_key

        if normalized_field == const.CFOP_ERROR_BASE:
            continue

        if section_key := field_to_section.get(normalized_field):
            mapped_errors[section_key] = translation_key
            mapped_errors[f"{section_key}.{normalized_field}"] = translation_key

    return mapped_errors


def _validate_users_inputs_impl(
    user_input: dict[str, Any],
    existing_users: dict[str, Any] | None = None,
    existing_assignees: dict[str, Any] | None = None,
    *,
    current_user_id: str | None = None,
) -> dict[str, str]:
    """Validate sectioned USER-form configuration inputs.

    This is a UI-specific wrapper that:
    1. Extracts DATA_* values from user_input (keys are aligned: CFOF_* = DATA_*)
    2. Calls data_builders.validate_user_profile_data() (single source of truth)

    Note: Since Phase 6 CFOF Key Alignment, CFOF_USERS_INPUT_NAME = "name"
    matches DATA_USER_NAME = "name", so no key transformation is needed.

    Args:
        user_input: Dictionary containing user inputs from the form (CFOF_* keys).
        existing_users: Optional dictionary of existing user profiles for duplicate checking.
        existing_assignees: Optional dictionary of existing assignee profiles for cross-validation.
        current_user_id: ID of user profile being edited (to exclude from duplicate check).

    Returns:
        Dictionary of errors (empty if validation passes).
    """
    from .. import data_builders as db

    # Build DATA_* dict for shared validation
    data_dict: dict[str, Any] = {
        const.DATA_USER_NAME: user_input.get(const.CFOF_USERS_INPUT_NAME, ""),
    }

    if const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS in user_input:
        data_dict[const.DATA_USER_ASSOCIATED_USER_IDS] = user_input.get(
            const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
            [],
        )
    if const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED in user_input:
        data_dict[const.DATA_USER_CAN_BE_ASSIGNED] = user_input.get(
            const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
            False,
        )
    if const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW in user_input:
        data_dict[const.DATA_USER_ENABLE_CHORE_WORKFLOW] = user_input.get(
            const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW,
            False,
        )
    if const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION in user_input:
        data_dict[const.DATA_USER_ENABLE_GAMIFICATION] = user_input.get(
            const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION,
            False,
        )
    if const.CFOF_USERS_INPUT_CAN_APPROVE in user_input:
        data_dict[const.DATA_USER_CAN_APPROVE] = user_input.get(
            const.CFOF_USERS_INPUT_CAN_APPROVE,
            False,
        )
    if const.CFOF_USERS_INPUT_CAN_MANAGE in user_input:
        data_dict[const.DATA_USER_CAN_MANAGE] = user_input.get(
            const.CFOF_USERS_INPUT_CAN_MANAGE,
            False,
        )

    # Call shared validation (single source of truth)
    is_update = current_user_id is not None
    return db.validate_user_profile_data(
        data_dict,
        existing_users,
        existing_assignees,
        is_update=is_update,
        current_user_id=current_user_id,
    )


def build_user_section_suggested_values(flat_values: dict[str, Any]) -> dict[str, Any]:
    """Public wrapper for sectioned suggested values in USER form."""
    return _build_user_section_suggested_values_impl(flat_values)


def normalize_user_form_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Public wrapper to normalize USER-form payload shape."""
    return _normalize_user_form_input_impl(user_input)


async def build_user_schema(hass, users, assignees_dict):
    """Public schema builder for sectioned USER-form surfaces.

    Args:
        hass: Home Assistant instance.
        users: Available Home Assistant users.
        assignees_dict: Mapping of display name to internal ID for association field.
    """
    return await _build_user_schema_impl(hass, users, assignees_dict)


def map_user_form_errors(errors: dict[str, str]) -> dict[str, str]:
    """Public wrapper for section-aware USER-form error mapping."""
    return _map_user_form_errors_impl(errors)


def validate_users_inputs(
    user_input: dict[str, Any],
    existing_users: dict[str, Any] | None = None,
    existing_assignees: dict[str, Any] | None = None,
    *,
    current_user_id: str | None = None,
) -> dict[str, str]:
    """Public wrapper for sectioned USER-form validation rules."""
    return _validate_users_inputs_impl(
        user_input,
        existing_users,
        existing_assignees,
        current_user_id=current_user_id,
    )


# ----------------------------------------------------------------------------------
# CHORES SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------

CHORE_SECTION_ROOT_FORM = "section_root_form"
CHORE_SECTION_SCHEDULE = "section_schedule"
CHORE_SECTION_ADVANCED_CONFIGURATIONS = "section_advanced_configurations"

CHORE_SECTION_KEYS = (
    CHORE_SECTION_ROOT_FORM,
    CHORE_SECTION_SCHEDULE,
    CHORE_SECTION_ADVANCED_CONFIGURATIONS,
)

CHORE_ROOT_FORM_FIELDS = (
    const.CFOF_CHORES_INPUT_NAME,
    const.CFOF_CHORES_INPUT_DESCRIPTION,
    const.CFOF_CHORES_INPUT_ICON,
    const.CFOF_CHORES_INPUT_DEFAULT_POINTS,
    const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS,
    const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
)

CHORE_SCHEDULE_FIELDS = (
    const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    const.CFOF_CHORES_INPUT_DUE_DATE,
    const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE,
    const.CFOF_CHORES_INPUT_APPLICABLE_DAYS,
    const.CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET,
    const.CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW,
    const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL,
    const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT,
)

CHORE_ADVANCED_CONFIGURATION_FIELDS = (
    const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
    const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    const.CFOF_CHORES_INPUT_AUTO_APPROVE,
    const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
    const.CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET,
    const.CFOF_CHORES_INPUT_NOTIFICATIONS,
    const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR,
    const.CFOF_CHORES_INPUT_LABELS,
)


def normalize_chore_form_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize chore form input for sectioned and non-sectioned payloads.

    Home Assistant `section()` wraps form values under section keys. This helper
    flattens those values so existing validation and transform logic can remain
    unchanged.
    """
    normalized: dict[str, Any] = dict(user_input)
    for section_key in CHORE_SECTION_KEYS:
        section_data = normalized.pop(section_key, None)
        if isinstance(section_data, dict):
            normalized.update(section_data)
    return normalized


def build_chore_section_suggested_values(flat_values: dict[str, Any]) -> dict[str, Any]:
    """Build sectioned suggested values from a flat chore form dictionary."""
    return {
        CHORE_SECTION_ROOT_FORM: {
            key: flat_values[key]
            for key in CHORE_ROOT_FORM_FIELDS
            if key in flat_values
        },
        CHORE_SECTION_SCHEDULE: {
            key: flat_values[key] for key in CHORE_SCHEDULE_FIELDS if key in flat_values
        },
        CHORE_SECTION_ADVANCED_CONFIGURATIONS: {
            key: flat_values[key]
            for key in CHORE_ADVANCED_CONFIGURATION_FIELDS
            if key in flat_values
        },
    }


def map_chore_form_errors(errors: dict[str, str]) -> dict[str, str]:
    """Map chore validation errors to form field keys for sectioned UI rendering.

    Preserves original keys and adds aliases for current form field keys.
    For sectioned forms, also maps field errors to the approver section key.

    Home Assistant's expandable form renderer binds error records at the
    section container level, so nested child keys are not always displayed.
    Emitting section-level keys ensures validation errors remain visible in the
    sectioned UX while keeping flat-key compatibility for tests and any legacy
    payloads.
    """

    mapped_errors: dict[str, str] = {}

    # Validation may emit historical/legacy field aliases.
    field_aliases = {
        const.CFOP_ERROR_CHORE_POINTS: const.CFOF_CHORES_INPUT_DEFAULT_POINTS,
    }

    field_to_section: dict[str, str] = {
        **dict.fromkeys(CHORE_ROOT_FORM_FIELDS, CHORE_SECTION_ROOT_FORM),
        **dict.fromkeys(CHORE_SCHEDULE_FIELDS, CHORE_SECTION_SCHEDULE),
        **dict.fromkeys(
            CHORE_ADVANCED_CONFIGURATION_FIELDS, CHORE_SECTION_ADVANCED_CONFIGURATIONS
        ),
    }

    for error_field, translation_key in errors.items():
        mapped_errors[error_field] = translation_key

        normalized_field = field_aliases.get(error_field, error_field)
        mapped_errors[normalized_field] = translation_key

        if normalized_field == const.CFOP_ERROR_BASE:
            continue

        if section_key := field_to_section.get(normalized_field):
            mapped_errors[section_key] = translation_key
            mapped_errors[f"{section_key}.{normalized_field}"] = translation_key

    return mapped_errors


def build_chore_schema(
    assignees_dict: dict[str, str],
    default: dict[str, Any] | None = None,
    frequency_options: list[str] | None = None,
) -> vol.Schema:
    """Build a schema for chores, referencing existing assignees by name.

    Uses internal_id for entity management.
    Dynamically adds "clear due date" checkbox when editing with existing date.

    Note: Uses static defaults to enable field clearing.
    For edit forms, use add_suggested_values_to_schema() to show current values.

    Args:
        assignees_dict: Mapping of assignee names to internal IDs.
        default: Default values for form fields (edit mode).
        frequency_options: List of frequency options to show. Defaults to
            const.CHORE_FREQUENCY_OPTIONS (all frequencies). Config flow should pass
            const.CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW to exclude DAILY_MULTI.
    """
    default = default or {}
    frequency_options = frequency_options or const.CHORE_FREQUENCY_OPTIONS

    assignee_choices = {k: k for k in assignees_dict}

    # Build schema fields in approved UX order grouped by sections
    root_form_fields: dict[Any, Any] = {
        vol.Required(const.CFOF_CHORES_INPUT_NAME, default=const.SENTINEL_EMPTY): str,
        vol.Optional(
            const.CFOF_CHORES_INPUT_DESCRIPTION,
            default=const.SENTINEL_EMPTY,
        ): str,
        vol.Optional(
            const.CFOF_CHORES_INPUT_ICON,
            default=const.SENTINEL_EMPTY,
        ): selector.IconSelector(),
        vol.Required(
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS,
            default=default.get(
                const.CFOF_CHORES_INPUT_DEFAULT_POINTS, const.DEFAULT_POINTS
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                mode=selector.NumberSelectorMode.BOX,
                min=0,
                step=0.1,
            )
        ),
        vol.Required(
            const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS,
            default=default.get(const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS, []),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(assignee_choices.keys()),
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=const.TRANS_KEY_FLOW_HELPERS_ASSIGNED_USER_IDS,
            )
        ),
        vol.Required(
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
            default=default.get(
                const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
                const.COMPLETION_CRITERIA_INDEPENDENT,
            ),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=cast(
                    "list[selector.SelectOptionDict]", const.COMPLETION_CRITERIA_OPTIONS
                ),
                translation_key=const.TRANS_KEY_FLOW_HELPERS_COMPLETION_CRITERIA,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }

    schedule_fields: dict[Any, Any] = {
        vol.Required(
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
            default=default.get(
                const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY, const.FREQUENCY_NONE
            ),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=frequency_options,
                translation_key=const.TRANS_KEY_FLOW_HELPERS_RECURRING_FREQUENCY,
            )
        ),
        vol.Optional(
            const.CFOF_CHORES_INPUT_DUE_DATE,
            default=default.get(const.CFOF_CHORES_INPUT_DUE_DATE),
        ): vol.Any(None, selector.DateTimeSelector()),
        # Keep clear_due_date directly under due_date for consistent UX.
        vol.Optional(
            const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE,
            default=False,
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_CHORES_INPUT_APPLICABLE_DAYS,
            # Explicitly check for None to preserve empty list [] (when user clears all days)
            # Storage may have null when per_assignee_applicable_days is source of truth
            default=(
                default.get(const.CFOF_CHORES_INPUT_APPLICABLE_DAYS)
                if default.get(const.CFOF_CHORES_INPUT_APPLICABLE_DAYS) is not None
                else const.DEFAULT_APPLICABLE_DAYS
            ),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": key, "label": label}
                    for key, label in const.WEEKDAY_OPTIONS.items()
                ],
                multiple=True,
                translation_key=const.TRANS_KEY_FLOW_HELPERS_APPLICABLE_DAYS,
            )
        ),
        vol.Optional(
            const.CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET,
            default=default.get(
                const.CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET,
                const.DEFAULT_DUE_WINDOW_OFFSET,
            ),
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(
            const.CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW,
            default=default.get(
                const.CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW,
                default.get(
                    const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
                    const.DEFAULT_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
                ),
            ),
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL,
            default=default.get(const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL, None),
        ): vol.Any(
            None,
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX, min=1, step=1
                )
            ),
        ),
        vol.Optional(
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT,
            default=default.get(const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT, None),
        ): vol.Any(
            None,
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=const.CUSTOM_INTERVAL_UNIT_OPTIONS,
                    translation_key=const.TRANS_KEY_FLOW_HELPERS_CUSTOM_INTERVAL_UNIT,
                    multiple=False,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        ),
    }

    advanced_configuration_fields: dict[Any, Any] = {
        vol.Required(
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
            default=default.get(
                const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
                const.DEFAULT_APPROVAL_RESET_TYPE,
            ),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=cast(
                    "list[selector.SelectOptionDict]", const.APPROVAL_RESET_TYPE_OPTIONS
                ),
                translation_key=const.TRANS_KEY_FLOW_HELPERS_APPROVAL_RESET_TYPE,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            default=default.get(
                const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            ),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=cast(
                    "list[selector.SelectOptionDict]",
                    const.APPROVAL_RESET_PENDING_CLAIM_ACTION_OPTIONS,
                ),
                translation_key=const.TRANS_KEY_FLOW_HELPERS_APPROVAL_RESET_PENDING_CLAIM_ACTION,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            const.CFOF_CHORES_INPUT_AUTO_APPROVE,
            default=default.get(
                const.CFOF_CHORES_INPUT_AUTO_APPROVE,
                const.DEFAULT_CHORE_AUTO_APPROVE,
            ),
        ): selector.BooleanSelector(),
        vol.Required(
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
            default=default.get(
                const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
                const.DEFAULT_OVERDUE_HANDLING_TYPE,
            ),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=cast(
                    "list[selector.SelectOptionDict]",
                    const.OVERDUE_HANDLING_TYPE_OPTIONS,
                ),
                translation_key=const.TRANS_KEY_FLOW_HELPERS_OVERDUE_HANDLING_TYPE,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            const.CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET,
            default=default.get(
                const.CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET,
                const.DEFAULT_DUE_REMINDER_OFFSET,
            ),
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Optional(
            const.CFOF_CHORES_INPUT_NOTIFICATIONS,
            default=_build_notification_defaults(default),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    const.DATA_CHORE_NOTIFY_ON_CLAIM,
                    const.DATA_CHORE_NOTIFY_ON_APPROVAL,
                    const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL,
                    const.DATA_CHORE_NOTIFY_ON_OVERDUE,
                    const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW,
                    const.DATA_CHORE_NOTIFY_DUE_REMINDER,
                ],
                multiple=True,
                translation_key=const.TRANS_KEY_FLOW_HELPERS_CHORE_NOTIFICATIONS,
            )
        ),
        vol.Required(
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR,
            default=default.get(const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR, True),
        ): selector.BooleanSelector(),
        vol.Optional(
            const.CFOF_CHORES_INPUT_LABELS,
            default=[],
        ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
    }

    schema_fields: dict[Any, Any] = {
        vol.Optional(CHORE_SECTION_ROOT_FORM): section(vol.Schema(root_form_fields)),
        vol.Optional(CHORE_SECTION_SCHEDULE): section(
            vol.Schema(schedule_fields), {"collapsed": True}
        ),
        vol.Optional(CHORE_SECTION_ADVANCED_CONFIGURATIONS): section(
            vol.Schema(advanced_configuration_fields), {"collapsed": True}
        ),
    }

    # Keep backward compatibility for flat test payloads while rendering
    # sectioned UI for real flows.
    return vol.Schema(schema_fields, extra=vol.ALLOW_EXTRA)


def validate_chores_inputs(
    user_input: dict[str, Any],
    assignees_dict: dict[str, Any],
    existing_chores: dict[str, Any] | None = None,
    *,
    current_chore_id: str | None = None,
) -> tuple[dict[str, str], str | None]:
    """Validate chore configuration inputs for Options Flow.

    This is a UI-specific wrapper that:
    1. Extracts DATA_* values from user_input (most keys are aligned: CFOF_* = DATA_*)
    2. Calls data_builders.validate_chore_data() (single source of truth)
    3. Handles UI-specific concerns (clear_due_date checkbox, assignees_dict mapping)

    Note: Since Phase 6 CFOF Key Alignment, simple fields like name, description,
    points are aligned. Chores still require transform_chore_cfof_to_data() for
    complex fields (daily_multi_times parsing, per_assignee_due_dates, notification mapping).

    Args:
        user_input: Dictionary containing user inputs from the form (CFOF_* keys).
        assignees_dict: Dictionary mapping assignee names to assignee internal_ids (UUIDs).
        existing_chores: Optional dictionary of existing chores for duplicate checking.
        current_chore_id: ID of chore being edited (to exclude from duplicate check).

    Returns:
        Tuple of (errors_dict, due_date_str_or_none).
        - errors_dict: Dictionary of errors (empty if validation passes).
        - due_date_str: Validated due date as ISO string, or None if not provided/cleared.
    """
    from .. import data_builders as db

    errors: dict[str, str] = {}

    # === Transform CFOF_* keys to DATA_* keys for shared validation ===
    # Form field key uses *_IDS for legacy compatibility, but selector values are names.
    assigned_user_names = user_input.get(const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS, [])
    assigned_user_ids = [
        assignees_dict[assignee_name]
        for assignee_name in assigned_user_names
        if assignee_name in assignees_dict
    ]

    # Handle due date (UI-specific: clear_due_date checkbox)
    clear_due_date = user_input.get(const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False)
    due_date_str: str | None = None

    if clear_due_date:
        const.LOGGER.debug("validate_chores_inputs: user cleared due date via checkbox")
        due_date_str = None
    elif user_input.get(const.CFOF_CHORES_INPUT_DUE_DATE):
        raw_due = user_input[const.CFOF_CHORES_INPUT_DUE_DATE]
        const.LOGGER.debug(
            "validate_chores_inputs: raw_due input = %s (type: %s)",
            raw_due,
            type(raw_due).__name__,
        )
        try:
            due_dt = dt_parse(
                raw_due,
                default_tzinfo=const.DEFAULT_TIME_ZONE,
                return_type=const.HELPER_RETURN_DATETIME_UTC,
            )
            # Type guard: narrow datetime | date | str | None to datetime
            if due_dt and not isinstance(due_dt, datetime.datetime):
                const.LOGGER.warning(
                    "validate_chores_inputs: due_dt is not datetime: %s", type(due_dt)
                )
                errors[const.CFOP_ERROR_DUE_DATE] = (
                    const.TRANS_KEY_CFOF_INVALID_DUE_DATE
                )
                return errors, None
            if due_dt:
                due_date_str = due_dt.isoformat()
        except (ValueError, TypeError, AttributeError) as exc:
            const.LOGGER.warning(
                "validate_chores_inputs: exception parsing due date: %s", exc
            )
            errors[const.CFOP_ERROR_DUE_DATE] = const.TRANS_KEY_CFOF_INVALID_DUE_DATE
            return errors, None

    # Build DATA_* dict for shared validation
    data_dict: dict[str, Any] = {
        const.DATA_CHORE_NAME: user_input.get(const.CFOF_CHORES_INPUT_NAME, ""),
        const.DATA_CHORE_ASSIGNED_USER_IDS: assigned_user_ids,
        const.DATA_CHORE_RECURRING_FREQUENCY: user_input.get(
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY, const.FREQUENCY_NONE
        ),
        const.DATA_CHORE_APPROVAL_RESET_TYPE: user_input.get(
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
            const.DEFAULT_APPROVAL_RESET_TYPE,
        ),
        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: user_input.get(
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        ),
        const.DATA_CHORE_COMPLETION_CRITERIA: user_input.get(
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        ),
    }

    # Only include due_date if we have one (allows clearing)
    if due_date_str:
        data_dict[const.DATA_CHORE_DUE_DATE] = due_date_str

    # Include points if provided
    if const.CFOF_CHORES_INPUT_DEFAULT_POINTS in user_input:
        data_dict[const.DATA_CHORE_DEFAULT_POINTS] = user_input[
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS
        ]

    # === Call shared validation (single source of truth) ===
    is_update = current_chore_id is not None
    errors = db.validate_chore_data(
        data_dict,
        existing_chores,
        is_update=is_update,
        current_chore_id=current_chore_id,
    )

    if errors:
        return errors, None

    return errors, due_date_str


def transform_chore_cfof_to_data(
    user_input: dict[str, Any],
    assignees_dict: dict[str, Any],
    due_date_str: str | None,
    existing_per_assignee_due_dates: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Transform chore form input to storage format for complex fields only.

    Since Phase 6 CFOF Key Alignment, simple chore fields (name, description, points)
    use aligned keys and pass through directly. This function handles the complex
    transformations that still require processing:

    - Converts assigned assignee names to UUIDs (assignee_dict lookup)
    - Builds per_assignee_due_dates dict (INDEPENDENT vs SHARED logic)
    - Extracts notification selections from consolidated field
    - Handles completion_criteria logic for per-assignee configuration

    Note: Simple field keys are now aligned (CFOF_CHORES_INPUT_NAME = \"name\" = DATA_CHORE_NAME),
    so no key renaming is needed for those fields.

    Args:
        user_input: Dictionary containing user inputs from the form (CFOF_* keys).
        assignees_dict: Dictionary mapping assignee names to assignee internal_ids (UUIDs).
        due_date_str: Validated due date as ISO string (from validate_chores_inputs).
        existing_per_assignee_due_dates: Optional dictionary of existing per-assignee due dates
            to preserve when editing INDEPENDENT chores.

    Returns:
        Dictionary with DATA_* keys ready for data_builders.build_chore().
    """
    # Form field key uses *_IDS for legacy compatibility, but selector values are names.
    assigned_user_names = user_input.get(const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS, [])
    assigned_user_ids = [
        assignees_dict[assignee_name]
        for assignee_name in assigned_user_names
        if assignee_name in assignees_dict
    ]

    # Get completion criteria
    completion_criteria = user_input.get(
        const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )

    # Check if user explicitly wants to clear the date
    clear_due_date = user_input.get(const.CFOF_CHORES_INPUT_CLEAR_DUE_DATE, False)

    # Build per_assignee_due_dates for ALL chores (SHARED + INDEPENDENT)
    per_assignee_due_dates: dict[str, str | None] = {}
    for assignee_id in assigned_user_ids:
        if (
            existing_per_assignee_due_dates
            and completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and assignee_id in existing_per_assignee_due_dates
            and not clear_due_date
        ):
            per_assignee_due_dates[assignee_id] = existing_per_assignee_due_dates[
                assignee_id
            ]
        else:
            per_assignee_due_dates[assignee_id] = due_date_str

    # Clean up custom interval fields if not using custom frequency
    recurring_freq = user_input.get(const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY)
    if recurring_freq not in (
        const.FREQUENCY_CUSTOM,
        const.FREQUENCY_CUSTOM_FROM_COMPLETE,
    ):
        custom_interval = None
        custom_interval_unit = None
    else:
        custom_interval = user_input.get(const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL)
        custom_interval_unit = user_input.get(
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT
        )

    # Extract notification selections from consolidated field
    notifications = user_input.get(const.CFOF_CHORES_INPUT_NOTIFICATIONS, [])

    # Build DATA_* keyed dict
    return {
        const.DATA_CHORE_NAME: user_input.get(const.CFOF_CHORES_INPUT_NAME, "").strip(),
        const.DATA_CHORE_DEFAULT_POINTS: user_input.get(
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS, const.DEFAULT_POINTS
        ),
        const.DATA_CHORE_COMPLETION_CRITERIA: completion_criteria,
        const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: per_assignee_due_dates,
        const.DATA_CHORE_APPROVAL_RESET_TYPE: user_input.get(
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
            const.DEFAULT_APPROVAL_RESET_TYPE,
        ),
        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: user_input.get(
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
            const.DEFAULT_OVERDUE_HANDLING_TYPE,
        ),
        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: user_input.get(
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
            const.DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
        ),
        const.DATA_CHORE_ASSIGNED_USER_IDS: assigned_user_ids,
        const.DATA_CHORE_DESCRIPTION: user_input.get(
            const.CFOF_CHORES_INPUT_DESCRIPTION, const.SENTINEL_EMPTY
        ),
        const.DATA_CHORE_LABELS: user_input.get(const.CFOF_CHORES_INPUT_LABELS, []),
        const.DATA_CHORE_ICON: user_input.get(
            const.CFOF_CHORES_INPUT_ICON, const.SENTINEL_EMPTY
        ),
        const.DATA_CHORE_RECURRING_FREQUENCY: user_input.get(
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY, const.SENTINEL_EMPTY
        ),
        const.DATA_CHORE_CUSTOM_INTERVAL: custom_interval,
        const.DATA_CHORE_CUSTOM_INTERVAL_UNIT: custom_interval_unit,
        # For INDEPENDENT chores, chore-level due_date is cleared
        const.DATA_CHORE_DUE_DATE: (
            None
            if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            else due_date_str
        ),
        # Convert weekday strings ("mon", "tue") to integers (0, 1, ...)
        const.DATA_CHORE_APPLICABLE_DAYS: [
            const.WEEKDAY_NAME_TO_INT[day]
            for day in user_input.get(
                const.CFOF_CHORES_INPUT_APPLICABLE_DAYS,
                const.DEFAULT_APPLICABLE_DAYS,
            )
            if day in const.WEEKDAY_NAME_TO_INT
        ],
        const.DATA_CHORE_DAILY_MULTI_TIMES: user_input.get(
            const.CFOF_CHORES_INPUT_DAILY_MULTI_TIMES
        ),
        # Notification fields from consolidated selector
        const.DATA_CHORE_NOTIFY_ON_CLAIM: (
            const.DATA_CHORE_NOTIFY_ON_CLAIM in notifications
        ),
        const.DATA_CHORE_NOTIFY_ON_APPROVAL: (
            const.DATA_CHORE_NOTIFY_ON_APPROVAL in notifications
        ),
        const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL: (
            const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL in notifications
        ),
        const.DATA_CHORE_NOTIFY_ON_OVERDUE: (
            const.DATA_CHORE_NOTIFY_ON_OVERDUE in notifications
        ),
        const.DATA_CHORE_SHOW_ON_CALENDAR: user_input.get(
            const.CFOF_CHORES_INPUT_SHOW_ON_CALENDAR,
            const.DEFAULT_CHORE_SHOW_ON_CALENDAR,
        ),
        const.DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW: user_input.get(
            const.CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW,
            const.DEFAULT_CHORE_CLAIM_LOCK_UNTIL_WINDOW,
        ),
        const.DATA_CHORE_AUTO_APPROVE: user_input.get(
            const.CFOF_CHORES_INPUT_AUTO_APPROVE,
            const.DEFAULT_CHORE_AUTO_APPROVE,
        ),
        # Due window fields (Phase 2 - due window feature)
        const.DATA_CHORE_DUE_WINDOW_OFFSET: user_input.get(
            const.CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET,
            const.DEFAULT_DUE_WINDOW_OFFSET,
        ),
        const.DATA_CHORE_DUE_REMINDER_OFFSET: user_input.get(
            const.CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET,
            const.DEFAULT_DUE_REMINDER_OFFSET,
        ),
        # Due window notification fields from consolidated selector
        const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW: (
            const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW in notifications
        ),
        const.DATA_CHORE_NOTIFY_DUE_REMINDER: (
            const.DATA_CHORE_NOTIFY_DUE_REMINDER in notifications
        ),
    }


# ----------------------------------------------------------------------------------
# DAILY_MULTI VALIDATION FUNCTIONS
# ----------------------------------------------------------------------------------


def validate_chore_frequency_reset_combination(
    recurring_frequency: str,
    approval_reset_type: str,
) -> dict[str, str]:
    """Validate frequency and reset type combination.

    Args:
        recurring_frequency: The chore's recurring frequency.
        approval_reset_type: The chore's approval reset type.

    Returns:
        Dictionary of errors (empty if validation passes).
        Key is error field (CFOP_ERROR_*), value is translation key.
    """
    errors: dict[str, str] = {}

    if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
        # DAILY_MULTI incompatible with AT_MIDNIGHT_* reset types
        # Rationale: DAILY_MULTI needs immediate slot advancement, but
        # AT_MIDNIGHT_* keeps chore APPROVED until midnight (blocks slots)
        incompatible_reset_types = {
            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        }
        if approval_reset_type in incompatible_reset_types:
            errors[const.CFOP_ERROR_DAILY_MULTI_RESET] = (
                const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET
            )

    return errors


def validate_daily_multi_assignees(
    recurring_frequency: str,
    completion_criteria: str,
    assigned_assignees: list[str],
    per_assignee_times: dict[str, str] | None = None,
) -> dict[str, str]:
    """Validate DAILY_MULTI assignee assignment rules.

    Args:
        recurring_frequency: The chore's recurring frequency.
        completion_criteria: The chore's completion criteria.
        assigned_assignees: List of assigned assignee IDs or names.
        per_assignee_times: Per-assignee times dict (if provided, allows multi-assignees).

    Returns:
        Dictionary of errors (empty if validation passes).
        Key is error field (CFOP_ERROR_*), value is translation key.

    PKAD-2026-001: Now allows DAILY_MULTI + INDEPENDENT + multi-assignees
    when per_assignee_times is provided (each assignee has own time slots).
    """
    errors: dict[str, str] = {}

    if recurring_frequency == const.FREQUENCY_DAILY_MULTI:
        # DAILY_MULTI + INDEPENDENT: allowed if per_assignee_times exists
        # (each assignee gets their own time slots)
        if (
            completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT
            and len(assigned_assignees) > 1
            and not per_assignee_times
        ):
            errors[const.CFOP_ERROR_DAILY_MULTI_USER_IDS] = (
                const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_ASSIGNEES
            )

    return errors


def validate_per_assignee_applicable_days(
    per_assignee_days: dict[str, list[int]],
) -> tuple[bool, str | None]:
    """Validate per-assignee applicable days structure.

    Args:
        per_assignee_days: {assignee_id: [0, 3], ...} where 0=Mon, 6=Sun

    Returns:
        Tuple of (is_valid, error_key_or_none)

    Validation Rules (PKAD-2026-001):
    - Empty dict allowed (use chore-level defaults)
    - Each assignee value must be list of integers (0-6)
    - Empty list = all days applicable (valid)
    - No duplicate days in single assignee's list
    """
    if not per_assignee_days:
        return (True, None)  # Empty = use defaults

    for _assignee_id, days in per_assignee_days.items():
        if not isinstance(days, list):
            return (
                False,
                const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID,
            )

        if not days:
            continue  # Empty list = all days (valid)

        for day in days:
            if not isinstance(day, int) or day < 0 or day > 6:
                return (
                    False,
                    const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID,
                )

        # Check for duplicates
        if len(days) != len(set(days)):
            return (
                False,
                const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID,
            )

    return (True, None)


def validate_per_assignee_daily_multi_times(
    per_assignee_times: dict[str, str],
    frequency: str,
) -> tuple[bool, str | None]:
    """Validate per-assignee daily multi-times (only for DAILY_MULTI frequency).

    Args:
        per_assignee_times: {assignee_id: "08:00|17:00", ...}
        frequency: Chore recurring frequency

    Returns:
        Tuple of (is_valid, error_key_or_none)

    Note (PKAD-2026-001): Reuses existing validate_daily_multi_times() for format validation.
    """
    if frequency != const.FREQUENCY_DAILY_MULTI:
        return (True, None)  # Not applicable

    if not per_assignee_times:
        return (True, None)  # Empty = use chore-level times

    for _assignee_id, times_str in per_assignee_times.items():
        if not times_str or not times_str.strip():
            continue  # Empty = use chore-level default

        # Reuse existing validation
        errors = validate_daily_multi_times(times_str)
        if errors:
            return (
                False,
                const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_DAILY_MULTI_TIMES_INVALID,
            )

    return (True, None)


def validate_daily_multi_times(times_str: str) -> dict[str, str]:
    """Validate daily multi times format.

    Args:
        times_str: Pipe-separated time string (e.g., "08:00|17:00").

    Returns:
        Dictionary of errors (empty if validation passes).
        Key is error field ("base"), value is translation key.

    Validation rules:
        - Must have at least 2 times
        - Must have at most 6 times
        - Each time must be in HH:MM format (24-hour)
        - Hours must be 0-23, minutes must be 0-59
    """
    errors: dict[str, str] = {}

    if not times_str or not times_str.strip():
        errors["base"] = const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_REQUIRED
        return errors

    # Split and clean entries
    entries = [t.strip() for t in times_str.split("|") if t.strip()]

    # Validate count
    if len(entries) < 2:
        errors["base"] = const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_TOO_FEW
        return errors

    if len(entries) > 6:
        errors["base"] = const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_TOO_MANY
        return errors

    # Validate format of each entry
    import re

    time_pattern = re.compile(r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$")

    for entry in entries:
        if not time_pattern.match(entry):
            errors["base"] = const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_INVALID_FORMAT
            return errors

    return errors


# ----------------------------------------------------------------------------------
# BADGES - Layer 1: Schema + Layer 2: UI Validation Wrapper
# Note: Badges use embedded key mapping in build_badge() due to conditional fields
# that vary by badge_type. This is appropriate because badge fields differ significantly
# per type (cumulative vs periodic), making a simple aligned-key approach impractical.
# No separate map_cfof_to_badge_data() function exists - mapping is in data_builders.
# ----------------------------------------------------------------------------------


# --- Consolidated Schema Function ---
def build_badge_common_schema(
    default: dict[str, Any] | None = None,
    assignees_dict: dict[str, Any] | None = None,
    chores_dict: dict[str, Any] | None = None,
    rewards_dict: dict[str, Any] | None = None,
    challenges_dict: dict[str, Any] | None = None,
    achievements_dict: dict[str, Any] | None = None,
    bonuses_dict: dict[str, Any] | None = None,
    penalties_dict: dict[str, Any] | None = None,
    badge_type: str = const.BADGE_TYPE_CUMULATIVE,
) -> dict[vol.Marker, Any]:
    """
    Build a Voluptuous schema for badge configuration.

    This function creates a schema with structural defaults only. Actual field
    values should be populated using `add_suggested_values_to_schema()` after
    schema creation.

    Args:
        default: Optional dict for backwards compatibility. When None (recommended),
                 the schema uses static defaults suitable for new badges.
        assignees_dict: Dictionary of available assignees for the assigned_user_ids selector.
        chores_dict: Dictionary of available chores for the tracked selector.
        rewards_dict: Dictionary of available rewards for the awards selector.
        challenges_dict: Dictionary of available challenges for linked badges.
        achievements_dict: Dictionary of available achievements for linked badges.
        bonuses_dict: Dictionary of available bonuses for the awards selector.
        penalties_dict: Dictionary of available penalties for the awards selector.
        badge_type: The type of the badge (cumulative, daily, periodic, etc.).

    Returns:
        A dictionary representing the Voluptuous schema fields.

    Note:
        The recommended pattern is to call this with `default=None`, then apply
        actual values via `add_suggested_values_to_schema()`. The `default`
        parameter is maintained for backwards compatibility with existing code.
    """
    default = default or {}
    assignees_dict = assignees_dict or {}
    chores_dict = chores_dict or {}
    rewards_dict = rewards_dict or {}
    challenges_dict = challenges_dict or {}
    achievements_dict = achievements_dict or {}
    bonuses_dict = bonuses_dict or {}
    penalties_dict = penalties_dict or {}
    # Initialize schema fields
    schema_fields = {}

    # --- Set include_ flags based on badge type ---
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
    include_penalties = badge_type in const.INCLUDE_PENALTIES_BADGE_TYPES
    include_reset_schedule = badge_type in const.INCLUDE_RESET_SCHEDULE_BADGE_TYPES

    is_cumulative = badge_type == const.BADGE_TYPE_CUMULATIVE
    is_periodic = badge_type == const.BADGE_TYPE_PERIODIC
    is_daily = badge_type == const.BADGE_TYPE_DAILY
    is_special_occasion = badge_type == const.BADGE_TYPE_SPECIAL_OCCASION

    const.LOGGER.debug(
        "Build Badge Common Schema - Badge Type: %s, Default: %s", badge_type, default
    )

    # --- Start Common Schema ---
    # Schema defines structure with static defaults. Actual values are applied
    # via add_suggested_values_to_schema() in the calling flow.
    schema_fields.update(
        {
            vol.Required(const.CFOF_BADGES_INPUT_NAME): str,
            vol.Optional(
                const.CFOF_BADGES_INPUT_DESCRIPTION,
                default="",
            ): str,
            vol.Optional(
                const.CFOF_BADGES_INPUT_LABELS,
                default=[],
            ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
            vol.Optional(const.CFOF_BADGES_INPUT_ICON): selector.IconSelector(),
        }
    )
    # --- End Common Schema ---

    # --- Target Component Schema ---
    if include_target:
        # Filter target_type_options based on whether tracked chores are included
        # For daily badges, filter out all streak targets
        if badge_type == const.BADGE_TYPE_DAILY:
            streak_types = {
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_CHORES,
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE,
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES,
                const.BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_DUE_CHORES_NO_OVERDUE,
            }
            target_type_options = [
                option
                for option in const.TARGET_TYPE_OPTIONS or []
                if option["value"] not in streak_types
            ]
        else:
            target_type_options = [
                option
                for option in const.TARGET_TYPE_OPTIONS or []
                if include_tracked_chores
                or option["value"]
                in (
                    const.BADGE_TARGET_THRESHOLD_TYPE_POINTS,
                    const.BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES,
                    const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
                )
            ]

        if not (is_cumulative or is_special_occasion):
            # Include the target_type field for non-cumulative badges
            schema_fields.update(
                {
                    vol.Required(
                        const.CFOF_BADGES_INPUT_TARGET_TYPE,
                        default=const.DEFAULT_BADGE_TARGET_TYPE,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=cast(
                                "list[selector.SelectOptionDict]", target_type_options
                            ),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key=const.TRANS_KEY_CFOF_BADGE_TARGET_TYPE,
                        )
                    ),
                }
            )

        # Always include the threshold field unless it's a special occasion
        if not is_special_occasion:
            schema_fields.update(
                {
                    vol.Required(
                        const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
                        default=float(const.DEFAULT_BADGE_TARGET_THRESHOLD_VALUE),
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                mode=selector.NumberSelectorMode.BOX,
                                min=0,
                                step=1,
                            )
                        ),
                        vol.Coerce(float),
                        vol.Range(min=0),
                    ),
                }
            )

        # Add maintenance rules only if cumulative
        if is_cumulative:
            schema_fields.update(
                {
                    vol.Optional(
                        const.CFOF_BADGES_INPUT_MAINTENANCE_RULES,
                        default=const.DEFAULT_BADGE_MAINTENANCE_THRESHOLD,
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                mode=selector.NumberSelectorMode.BOX,
                                min=0,
                                step=1,
                            )
                        ),
                        vol.Coerce(int),
                        vol.Range(min=0),
                    ),
                }
            )

    # --- Special Occasion Component Schema ---
    if include_special_occasion:
        occasion_type_options = const.OCCASION_TYPE_OPTIONS or []
        schema_fields.update(
            {
                vol.Required(
                    const.CFOF_BADGES_INPUT_OCCASION_TYPE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=occasion_type_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_OCCASION_TYPE,
                    )
                )
            }
        )

    # --- Achievement-Linked Component Schema ---
    if include_achievement_linked:
        achievement_options = [
            {"value": const.SENTINEL_NO_SELECTION, "label": const.LABEL_NONE}
        ] + [
            {
                "value": achievement_id,
                "label": achievement.get(
                    const.DATA_ACHIEVEMENT_NAME, const.SENTINEL_NONE_TEXT
                ),
            }
            for achievement_id, achievement in achievements_dict.items()
        ]
        schema_fields.update(
            {
                vol.Required(
                    const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT,
                    default=const.SENTINEL_NO_SELECTION,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=achievement_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_ASSOCIATED_ACHIEVEMENT,
                    )
                )
            }
        )

    # --- Challenge-Linked Component Schema ---
    if include_challenge_linked:
        challenge_options = [
            {"value": const.SENTINEL_NO_SELECTION, "label": const.LABEL_NONE}
        ] + [
            {
                "value": challenge_id,
                "label": challenge.get(
                    const.DATA_CHALLENGE_NAME, const.SENTINEL_NONE_TEXT
                ),
            }
            for challenge_id, challenge in challenges_dict.items()
        ]
        schema_fields.update(
            {
                vol.Required(
                    const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE,
                    default=const.SENTINEL_NO_SELECTION,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=challenge_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_ASSOCIATED_CHALLENGE,
                    )
                )
            }
        )

    # --- Tracked Chores Component Schema ---
    if include_tracked_chores:
        chore_options = [{"value": const.SENTINEL_EMPTY, "label": const.LABEL_NONE}]
        chore_options += [
            {
                "value": chore_id,
                "label": chore.get(const.DATA_CHORE_NAME, const.SENTINEL_NONE_TEXT),
            }
            for chore_id, chore in chores_dict.items()
        ]
        schema_fields.update(
            {
                vol.Optional(
                    const.CFOF_BADGES_INPUT_SELECTED_CHORES,
                    default=[],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=cast("list[selector.SelectOptionDict]", chore_options),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_SELECTED_CHORES,
                    )
                )
            }
        )

    # --- Assigned To Component Schema ---
    if include_assigned_user_ids:
        assignee_options = [{"value": const.SENTINEL_EMPTY, "label": const.LABEL_NONE}]
        assignee_options += [
            {
                "value": assignee_id,
                "label": assignee.get(const.DATA_USER_NAME, const.SENTINEL_NONE_TEXT),
            }
            for assignee_id, assignee in assignees_dict.items()
        ]
        schema_fields.update(
            {
                vol.Optional(
                    const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS,
                    default=[],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=cast(
                            "list[selector.SelectOptionDict]", assignee_options
                        ),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_ASSIGNED_USER_IDS,
                    )
                )
            }
        )

    # --- Awards Component Schema ---
    if include_awards:
        award_items_options = []

        award_items_options.append(
            {
                "value": const.AWARD_ITEMS_KEY_POINTS,
                "label": const.AWARD_ITEMS_LABEL_POINTS,
            }
        )

        if is_cumulative:
            award_items_options.append(
                {
                    "value": (const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER),
                    "label": (const.AWARD_ITEMS_LABEL_POINTS_MULTIPLIER),
                }
            )

        if rewards_dict:
            for reward_id, reward in rewards_dict.items():
                reward_name = reward.get(const.DATA_REWARD_NAME, reward_id)
                label = f"{const.AWARD_ITEMS_LABEL_REWARD} {reward_name}"
                award_items_options.append(
                    {
                        "value": f"{const.AWARD_ITEMS_PREFIX_REWARD}{reward_id}",
                        "label": label,
                    }
                )
        if bonuses_dict:
            for bonus_id, bonus in bonuses_dict.items():
                bonus_name = bonus.get(const.DATA_BONUS_NAME, bonus_id)
                label = f"{const.AWARD_ITEMS_LABEL_BONUS} {bonus_name}"
                award_items_options.append(
                    {
                        "value": f"{const.AWARD_ITEMS_PREFIX_BONUS}{bonus_id}",
                        "label": label,
                    }
                )
        if include_penalties:
            if penalties_dict:
                for penalty_id, penalty in penalties_dict.items():
                    label = f"{const.AWARD_ITEMS_LABEL_PENALTY} {penalty.get(const.DATA_PENALTY_NAME, penalty_id)}"
                    award_items_options.append(
                        {
                            "value": f"{const.AWARD_ITEMS_PREFIX_PENALTY}{penalty_id}",
                            "label": label,
                        }
                    )

        schema_fields.update(
            {
                vol.Optional(
                    const.CFOF_BADGES_INPUT_AWARD_ITEMS,
                    default=[],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=cast(
                            "list[selector.SelectOptionDict]", award_items_options
                        ),
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=const.TRANS_KEY_CFOF_BADGE_AWARD_ITEMS,
                    )
                )
            }
        )

        schema_fields.update(
            {
                vol.Optional(
                    const.CFOF_BADGES_INPUT_AWARD_POINTS,
                    default=float(const.DEFAULT_BADGE_AWARD_POINTS),
                ): vol.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX,
                            min=0.0,
                            step=0.1,
                        )
                    ),
                    vol.Coerce(float),
                    vol.Range(min=0.0),
                ),
            }
        )
        # Points multiplier is only relevant for cumulative badges
        if is_cumulative:
            schema_fields.update(
                {
                    vol.Optional(const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER): vol.Any(
                        None,
                        vol.All(
                            selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    step=0.1,
                                    min=0.1,
                                )
                            ),
                            vol.Coerce(float),
                            vol.Range(min=0.1),
                        ),
                    ),
                }
            )

    # --- Reset Component Schema ---
    if include_reset_schedule:
        # For BADGE_TYPE_DAILY hide reset schedule fields - values forced in validation
        if not is_daily:
            # Build the schema fields for other badge types
            schema_fields.update(
                {
                    # Recurring Frequency
                    vol.Required(
                        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        default=const.DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=cast(
                                "list[selector.SelectOptionDict]",
                                const.BADGE_RESET_SCHEDULE_OPTIONS,
                            ),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key=const.TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
                        )
                    ),
                    # Custom Interval
                    vol.Optional(
                        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL,
                    ): vol.Any(
                        None,
                        vol.All(
                            selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    step=1,
                                )
                            ),
                            vol.Coerce(int),
                            vol.Range(min=0),
                        ),
                    ),
                    # Custom Interval Unit
                    vol.Optional(
                        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
                    ): vol.Any(
                        None,
                        selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=const.CUSTOM_INTERVAL_UNIT_OPTIONS,
                                mode=selector.SelectSelectorMode.DROPDOWN,
                                translation_key=const.TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT,
                            )
                        ),
                    ),
                }
            )

            # Conditionally add Start Date for periodic badges
            if is_periodic:
                schema_fields.update(
                    {
                        vol.Optional(
                            const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE,
                        ): vol.Any(None, selector.DateSelector()),
                    }
                )

            # End Date
            schema_fields.update(
                {
                    vol.Optional(
                        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE,
                    ): vol.Any(None, selector.DateSelector()),
                }
            )

            # Grace Period Days for cumulative badges
            if is_cumulative:
                schema_fields.update(
                    {
                        vol.Optional(
                            const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
                            default=const.DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS,
                        ): vol.All(
                            selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    mode=selector.NumberSelectorMode.BOX,
                                    min=0,
                                    step=1,
                                )
                            ),
                            vol.Coerce(int),
                            vol.Range(min=0),
                        ),
                    }
                )

    const.LOGGER.debug("Build Badge Common Schema - Returning Schema Fields")
    return schema_fields


# --- Consolidated Validation Function ---
def validate_badge_common_inputs(
    user_input: dict[str, Any],
    internal_id: str | None,
    existing_badges: dict[str, Any] | None = None,
    rewards_dict: dict[str, Any] | None = None,
    bonuses_dict: dict[str, Any] | None = None,
    penalties_dict: dict[str, Any] | None = None,
    badge_type: str = const.BADGE_TYPE_CUMULATIVE,
) -> dict[str, str]:
    """
    Validate common badge inputs and selected component inputs.

    Args:
        user_input: The dictionary containing user inputs from the form.
        internal_id: The internal ID for the badge (None when adding new).
        existing_badges: Dictionary of existing badges for uniqueness checks.
        badge_type: The type of the badge (cumulative, daily, periodic).
            Default is cumulative.

    Returns:
        A dictionary of validation errors {field_key: error_message}.
    """
    errors: dict[str, str] = {}
    existing_badges = existing_badges or {}

    rewards_dict = rewards_dict or {}
    bonuses_dict = bonuses_dict or {}
    penalties_dict = penalties_dict or {}

    # --- Set include_ flags based on badge type ---
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

    is_cumulative = badge_type == const.BADGE_TYPE_CUMULATIVE
    is_periodic = badge_type == const.BADGE_TYPE_PERIODIC
    is_daily = badge_type == const.BADGE_TYPE_DAILY
    is_special_occasion = badge_type == const.BADGE_TYPE_SPECIAL_OCCASION

    # --- Start Common Validation ---
    badge_name = user_input.get(const.CFOF_BADGES_INPUT_NAME, "").strip()

    # Feature Change v4.2: Validate assigned_user_ids for badge types that support it
    if include_assigned_user_ids:
        assigned_user_ids = user_input.get(
            const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS, []
        )
        if not assigned_user_ids or len(assigned_user_ids) == 0:
            errors[const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS] = (
                const.TRANS_KEY_CFOF_BADGE_REQUIRES_ASSIGNMENT
            )

    if not badge_name:
        errors[const.CFOF_BADGES_INPUT_NAME] = const.TRANS_KEY_CFOF_INVALID_BADGE_NAME

    # Validate badge is not duplicate (exclude the badge being edited)
    for badge_id, badge_info in existing_badges.items():
        if badge_id == internal_id:
            continue  # Skip the badge being edited
        if (
            badge_info.get(const.DATA_BADGE_NAME, "").strip().lower()
            == badge_name.lower()
        ):
            errors[const.CFOF_BADGES_INPUT_NAME] = const.TRANS_KEY_CFOF_DUPLICATE_BADGE
            break
    # --- End Common Validation ---

    # --- Target Component Validation ---
    if include_target:
        # Special Occasion badge handling - force target type and threshold value
        if is_special_occasion:
            # Force special occasion badges to use points with threshold 1
            user_input[const.CFOF_BADGES_INPUT_TARGET_TYPE] = (
                const.BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT
            )
            user_input[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = 1

        # Cumulative badge handling
        elif is_cumulative:
            # Cumulative badges always use points - set in data_builders.py

            # Validate threshold value
            target_threshold = user_input.get(
                const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE
            )

            if target_threshold is None or str(target_threshold).strip() == "":
                errors[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = (
                    const.TRANS_KEY_CFOF_TARGET_THRESHOLD_REQUIRED
                )
            else:
                try:
                    value = float(target_threshold)
                    if value <= 0:
                        errors[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = (
                            const.TRANS_KEY_CFOF_INVALID_BADGE_TARGET_THRESHOLD_VALUE
                        )
                except (TypeError, ValueError):
                    errors[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = (
                        const.TRANS_KEY_CFOF_INVALID_BADGE_TARGET_THRESHOLD_VALUE
                    )

            # Validate maintenance rules
            maintenance_rules = user_input.get(
                const.CFOF_BADGES_INPUT_MAINTENANCE_RULES
            )
            if maintenance_rules is None or maintenance_rules < 0:
                errors[const.CFOF_BADGES_INPUT_MAINTENANCE_RULES] = (
                    const.TRANS_KEY_CFOF_INVALID_MAINTENANCE_RULES
                )
        else:
            # Regular badge validation
            target_threshold = user_input.get(
                const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE
            )

            if target_threshold is None or str(target_threshold).strip() == "":
                errors[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = (
                    const.TRANS_KEY_CFOF_TARGET_THRESHOLD_REQUIRED
                )
            else:
                try:
                    value = float(target_threshold)
                    if value <= 0:
                        errors[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = (
                            const.TRANS_KEY_CFOF_INVALID_BADGE_TARGET_THRESHOLD_VALUE
                        )
                except (TypeError, ValueError):
                    errors[const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE] = (
                        const.TRANS_KEY_CFOF_INVALID_BADGE_TARGET_THRESHOLD_VALUE
                    )

        # Handle maintenance rules for non-cumulative badges
        if not is_cumulative:
            # If not cumulative, set maintenance rules to Zero
            user_input[const.CFOF_BADGES_INPUT_MAINTENANCE_RULES] = const.DEFAULT_ZERO

    # --- Special Occasion Validation ---
    if include_special_occasion:
        occasion_type = user_input.get(
            const.CFOF_BADGES_INPUT_OCCASION_TYPE, const.SENTINEL_EMPTY
        )
        if not occasion_type or occasion_type == const.SENTINEL_EMPTY:
            errors[const.CFOF_BADGES_INPUT_OCCASION_TYPE] = (
                const.TRANS_KEY_CFOF_ERROR_BADGE_OCCASION_TYPE_REQUIRED
            )

    # --- Achievement-Linked Validation ---
    if include_achievement_linked:
        achievement_id = user_input.get(
            const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT, const.SENTINEL_EMPTY
        )
        if not achievement_id or achievement_id in (
            const.SENTINEL_EMPTY,
            const.SENTINEL_NO_SELECTION,
        ):
            errors[const.CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT] = (
                const.TRANS_KEY_CFOF_ERROR_BADGE_ACHIEVEMENT_REQUIRED
            )

    # --- Challenge-Linked Validation ---
    if include_challenge_linked:
        challenge_id = user_input.get(
            const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE, const.SENTINEL_EMPTY
        )
        if not challenge_id or challenge_id in (
            const.SENTINEL_EMPTY,
            const.SENTINEL_NO_SELECTION,
        ):
            errors[const.CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE] = (
                const.TRANS_KEY_CFOF_ERROR_BADGE_CHALLENGE_REQUIRED
            )

    # --- Tracked Chores Component Validation ---
    if include_tracked_chores:
        selected_chores = user_input.get(const.CFOF_BADGES_INPUT_SELECTED_CHORES, [])
        if not isinstance(selected_chores, list):
            errors[const.CFOF_BADGES_INPUT_SELECTED_CHORES] = (
                "invalid_format_list_expected"  # Use translation keys
            )

    # --- Assigned To Component Validation ---
    if include_assigned_user_ids:
        assigned = user_input.get(const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS, [])
        if not isinstance(assigned, list):
            errors[const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS] = (
                "invalid_format_list_expected"  # Use translation keys
            )
        # Optional: Check existence of assignee IDs here if needed

    # --- Awards Component Validation ---
    award_items_valid_values = None
    if include_awards:
        # ...existing award_mode logic...

        award_items = user_input.get(const.CFOF_BADGES_INPUT_AWARD_ITEMS, [])
        if not isinstance(award_items, list):
            award_items = [award_items] if award_items else []

        # If award_items_valid_values is not provided, build it here
        if award_items_valid_values is None:
            award_items_valid_values = [
                const.AWARD_ITEMS_KEY_POINTS,
                const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER,
            ]
            if rewards_dict:
                award_items_valid_values += [
                    f"{const.AWARD_ITEMS_PREFIX_REWARD}{reward_id}"
                    for reward_id in rewards_dict
                ]
            if bonuses_dict:
                award_items_valid_values += [
                    f"{const.AWARD_ITEMS_PREFIX_BONUS}{bonus_id}"
                    for bonus_id in bonuses_dict
                ]
            if penalties_dict:
                award_items_valid_values += [
                    f"{const.AWARD_ITEMS_PREFIX_PENALTY}{penalty_id}"
                    for penalty_id in penalties_dict
                ]

        # 1. POINTS: logic
        if const.AWARD_ITEMS_KEY_POINTS in award_items:
            points = user_input.get(
                const.CFOF_BADGES_INPUT_AWARD_POINTS, const.DEFAULT_ZERO
            )
            try:
                if float(points) <= const.DEFAULT_ZERO:
                    errors[const.CFOF_BADGES_INPUT_AWARD_POINTS] = (
                        const.TRANS_KEY_CFOF_ERROR_AWARD_POINTS_MINIMUM
                    )
            except (TypeError, ValueError):
                errors[const.CFOF_BADGES_INPUT_AWARD_POINTS] = (
                    const.TRANS_KEY_CFOF_ERROR_AWARD_POINTS_MINIMUM
                )
        else:
            user_input[const.CFOF_BADGES_INPUT_AWARD_POINTS] = const.DEFAULT_ZERO

        # 2. POINTS MULTIPLIER: logic
        if const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER in award_items:
            multiplier = user_input.get(
                const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER,
                const.DEFAULT_POINTS_MULTIPLIER,
            )
            try:
                if float(multiplier) <= const.DEFAULT_ZERO:
                    errors[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER] = (
                        const.TRANS_KEY_CFOF_ERROR_AWARD_INVALID_MULTIPLIER
                    )
            except (TypeError, ValueError):
                errors[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER] = (
                    const.TRANS_KEY_CFOF_ERROR_AWARD_INVALID_MULTIPLIER
                )
        else:
            user_input[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER] = const.SENTINEL_NONE

        # 3. All selected award_items must be valid
        for item in award_items:
            if item not in award_items_valid_values:
                errors[const.CFOF_BADGES_INPUT_AWARD_ITEMS] = (
                    const.TRANS_KEY_CFOF_ERROR_AWARD_INVALID_AWARD_ITEM
                )
                break

    # --- Reset Component Validation ---
    if include_reset_schedule:
        recurring_frequency = user_input.get(
            const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY,
            const.DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY,
        )

        # Clear custom interval fields if not custom
        if recurring_frequency != const.FREQUENCY_CUSTOM:
            # Note: END_DATE not cleared - can be used as reference date
            user_input.update(
                {
                    const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE: const.SENTINEL_NONE,
                    const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL: const.SENTINEL_NONE,
                    const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: const.SENTINEL_NONE,
                }
            )

        start_date = user_input.get(const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE)
        end_date = user_input.get(const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE)

        if recurring_frequency == const.FREQUENCY_CUSTOM:
            # Validate start and end dates for periodic badges
            # If no custom interval and custom interval unit, then it will just do a one time reset
            if is_periodic and not start_date:
                errors[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] = (
                    const.TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_START_DATE_REQUIRED
                )
            if not end_date:
                errors[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] = (
                    const.TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_END_DATE_REQUIRED
                )
            elif start_date and end_date < start_date:
                errors[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] = (
                    const.TRANS_KEY_CFOF_END_DATE_BEFORE_START
                )

        # Validate grace period for cumulative badges
        if is_cumulative:
            grace_period_days = user_input.get(
                const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS
            )
            if grace_period_days is None or grace_period_days < 0:
                errors[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS] = (
                    "invalid_grace_period_days"
                )
        else:
            # Set grace period to zero for non-cumulative badges
            user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS] = (
                const.DEFAULT_ZERO
            )

        if is_daily:
            user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY] = (
                const.FREQUENCY_DAILY
            )

        # Special occasion is just a periodic badge that has a start and end date of the same day.
        if is_special_occasion:
            user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] = (
                user_input.get(const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE)
            )

    return errors


# ----------------------------------------------------------------------------------
# REWARDS SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------


def build_reward_schema(default=None):
    """Build a schema for rewards, keyed by internal_id in the dict.

    Note: Uses static defaults to enable field clearing.
    For edit forms, use add_suggested_values_to_schema() to show current values.
    """
    default = default or {}

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_REWARDS_INPUT_NAME, default=const.SENTINEL_EMPTY
            ): str,
            vol.Optional(
                const.CFOF_REWARDS_INPUT_DESCRIPTION,
                default=const.SENTINEL_EMPTY,
            ): str,
            vol.Optional(
                const.CFOF_REWARDS_INPUT_LABELS,
                default=[],
            ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
            vol.Required(
                const.CFOF_REWARDS_INPUT_COST,
                default=const.DEFAULT_REWARD_COST,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
            vol.Optional(
                const.CFOF_REWARDS_INPUT_ICON,
                default=const.SENTINEL_EMPTY,
            ): selector.IconSelector(),
        }
    )


def validate_rewards_inputs(
    user_input: dict[str, Any],
    existing_rewards: dict[str, Any] | None = None,
    *,
    current_reward_id: str | None = None,
) -> dict[str, str]:
    """Validate reward configuration inputs for Options Flow.

    This is a UI-specific wrapper that:
    1. Extracts DATA_* values from user_input (keys are aligned: CFOF_* = DATA_*)
    2. Calls data_builders.validate_reward_data() (single source of truth)

    Note: Since Phase 6 CFOF Key Alignment, CFOF_REWARDS_INPUT_NAME = "name"
    matches DATA_REWARD_NAME = "name". User_input can be passed directly to
    data_builders.build_reward() after validation.

    Args:
        user_input: Dictionary containing user inputs from the form (CFOF_* keys).
        existing_rewards: Optional dictionary of existing rewards for duplicate checking.
        current_reward_id: ID of reward being edited (to exclude from duplicate check).

    Returns:
        Dictionary of errors (empty if validation passes).
    """
    from .. import data_builders as db

    # Build DATA_* dict for shared validation
    data_dict: dict[str, Any] = {
        const.DATA_REWARD_NAME: user_input.get(const.CFOF_REWARDS_INPUT_NAME, ""),
    }

    # Include cost if provided
    if const.CFOF_REWARDS_INPUT_COST in user_input:
        data_dict[const.DATA_REWARD_COST] = user_input[const.CFOF_REWARDS_INPUT_COST]

    # Call shared validation (single source of truth)
    is_update = current_reward_id is not None
    return db.validate_reward_data(
        data_dict,
        existing_rewards,
        is_update=is_update,
        current_reward_id=current_reward_id,
    )


# ----------------------------------------------------------------------------------
# BONUSES SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------


def build_bonus_schema(default=None):
    """Build a schema for bonuses, keyed by internal_id in the dict.

    Stores bonus_points as positive in the form, converted to negative internally.
    Uses static defaults for optional fields - use suggested_value for edit forms.
    """
    default = default or {}
    bonus_name_default = default.get(const.DATA_BONUS_NAME, const.SENTINEL_EMPTY)

    # Display bonus points as positive for user input
    display_points = (
        abs(default.get(const.CFOF_BONUSES_INPUT_POINTS, const.DEFAULT_BONUS_POINTS))
        if default
        else const.DEFAULT_BONUS_POINTS
    )

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_BONUSES_INPUT_NAME, default=bonus_name_default
            ): str,
            vol.Optional(
                const.CFOF_BONUSES_INPUT_DESCRIPTION,
                default=const.SENTINEL_EMPTY,  # Static default enables clearing
            ): str,
            vol.Optional(
                const.CFOF_BONUSES_INPUT_LABELS,
                default=[],  # Static default enables clearing
            ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
            vol.Required(
                const.CFOF_BONUSES_INPUT_POINTS, default=display_points
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
            vol.Optional(
                const.CFOF_BONUSES_INPUT_ICON,
                default=const.SENTINEL_EMPTY,  # Static default enables clearing
            ): selector.IconSelector(),
        }
    )


def validate_bonuses_inputs(
    user_input: dict[str, Any],
    existing_bonuses: dict[str, Any] | None = None,
    *,
    current_bonus_id: str | None = None,
) -> dict[str, str]:
    """Validate bonus configuration inputs for Options Flow.

    This is a UI-specific wrapper that:
    1. Extracts DATA_* values from user_input (keys are aligned: CFOF_* = DATA_*)
    2. Calls data_builders.validate_bonus_or_penalty_data() (single source of truth)

    Note: Since Phase 6 CFOF Key Alignment, CFOF_BONUSES_INPUT_NAME = "name"
    matches DATA_BONUS_NAME = "name". User_input can be passed directly to
    data_builders.build_bonus() after validation.

    Args:
        user_input: Dictionary containing user inputs from the form (CFOF_* keys).
        existing_bonuses: Optional dictionary of existing bonuses for duplicate checking.
        current_bonus_id: ID of bonus being edited (to exclude from duplicate check).

    Returns:
        Dictionary of errors (empty if validation passes).
    """
    from .. import data_builders as db

    # Build DATA_* dict for shared validation
    data_dict: dict[str, Any] = {
        const.DATA_BONUS_NAME: user_input.get(const.CFOF_BONUSES_INPUT_NAME, ""),
    }

    # Call shared validation (single source of truth)
    is_update = current_bonus_id is not None
    return db.validate_bonus_or_penalty_data(
        data_dict,
        "bonus",
        existing_bonuses,
        is_update=is_update,
        current_entity_id=current_bonus_id,
    )


# ----------------------------------------------------------------------------------
# PENALTIES SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------


def build_penalty_schema(default=None):
    """Build a schema for penalties, keyed by internal_id in the dict.

    Stores penalty_points as positive in the form, converted to negative internally.
    Uses static defaults for optional fields - use suggested_value for edit forms.
    """
    default = default or {}
    penalty_name_default = default.get(const.DATA_PENALTY_NAME, const.SENTINEL_EMPTY)

    # Display penalty points as positive for user input
    display_points = (
        abs(
            default.get(const.CFOF_PENALTIES_INPUT_POINTS, const.DEFAULT_PENALTY_POINTS)
        )
        if default
        else const.DEFAULT_PENALTY_POINTS
    )

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_PENALTIES_INPUT_NAME, default=penalty_name_default
            ): str,
            vol.Optional(
                const.CFOF_PENALTIES_INPUT_DESCRIPTION,
                default=const.SENTINEL_EMPTY,  # Static default enables clearing
            ): str,
            vol.Optional(
                const.CFOF_PENALTIES_INPUT_LABELS,
                default=[],  # Static default enables clearing
            ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
            vol.Required(
                const.CFOF_PENALTIES_INPUT_POINTS, default=display_points
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
            vol.Optional(
                const.CFOF_PENALTIES_INPUT_ICON,
                default=const.SENTINEL_EMPTY,  # Static default enables clearing
            ): selector.IconSelector(),
        }
    )


def validate_penalties_inputs(
    user_input: dict[str, Any],
    existing_penalties: dict[str, Any] | None = None,
    *,
    current_penalty_id: str | None = None,
) -> dict[str, str]:
    """Validate penalty configuration inputs for Options Flow.

    This is a UI-specific wrapper that:
    1. Extracts DATA_* values from user_input (keys are aligned: CFOF_* = DATA_*)
    2. Calls data_builders.validate_bonus_or_penalty_data() (single source of truth)

    Note: Since Phase 6 CFOF Key Alignment, CFOF_PENALTIES_INPUT_NAME = "name"
    matches DATA_PENALTY_NAME = "name". User_input can be passed directly to
    data_builders.build_penalty() after validation.

    Args:
        user_input: Dictionary containing user inputs from the form (CFOF_* keys).
        existing_penalties: Optional dictionary of existing penalties for duplicate checking.
        current_penalty_id: ID of penalty being edited (to exclude from duplicate check).

    Returns:
        Dictionary of errors (empty if validation passes).
    """
    from .. import data_builders as db

    # Build DATA_* dict for shared validation
    data_dict: dict[str, Any] = {
        const.DATA_PENALTY_NAME: user_input.get(const.CFOF_PENALTIES_INPUT_NAME, ""),
    }

    # Call shared validation (single source of truth)
    is_update = current_penalty_id is not None
    return db.validate_bonus_or_penalty_data(
        data_dict,
        "penalty",
        existing_penalties,
        is_update=is_update,
        current_entity_id=current_penalty_id,
    )


# Penalty points are stored as negative internally, but displayed as positive in the form.
def process_penalty_form_input(user_input: dict) -> dict:
    """Ensure penalty points are negative internally."""
    data = dict(user_input)
    data[const.DATA_PENALTY_POINTS] = -abs(data[const.CFOF_PENALTIES_INPUT_POINTS])
    return data


# ----------------------------------------------------------------------------------
# ACHIEVEMENTS SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------


def build_achievement_schema(assignees_dict, chores_dict, default=None):
    """Build a schema for achievements, keyed by internal_id.

    Note: default parameter is kept for backwards compatibility but should NOT
    be used. Instead, use add_suggested_values_to_schema() after schema creation.
    This allows users to clear optional fields (suggested values vs defaults).
    """
    assignee_options = [
        {"value": assignee_id, "label": assignee_name}
        for assignee_name, assignee_id in assignees_dict.items()
    ]

    chore_options = [{"value": const.SENTINEL_EMPTY, "label": const.LABEL_NONE}]
    for chore_id, chore_data in chores_dict.items():
        chore_name = chore_data.get(const.DATA_CHORE_NAME, f"Chore {chore_id[:6]}")
        chore_options.append({"value": chore_id, "label": chore_name})

    return vol.Schema(
        {
            vol.Required(const.CFOF_ACHIEVEMENTS_INPUT_NAME): str,
            vol.Optional(
                const.CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION,
                default="",
            ): str,
            vol.Optional(
                const.CFOF_ACHIEVEMENTS_INPUT_LABELS,
                default=[],
            ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
            vol.Optional(const.CFOF_ACHIEVEMENTS_INPUT_ICON): selector.IconSelector(),
            vol.Required(
                const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS,
                default=[],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=cast("list[selector.SelectOptionDict]", assignee_options),
                    translation_key=const.TRANS_KEY_FLOW_HELPERS_ASSIGNED_USER_IDS,
                    multiple=True,
                )
            ),
            vol.Required(
                const.CFOF_ACHIEVEMENTS_INPUT_TYPE,
                default=const.ACHIEVEMENT_TYPE_STREAK,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=cast(
                        "list[selector.SelectOptionDict]",
                        const.ACHIEVEMENT_TYPE_OPTIONS,
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            # If type == "chore_streak", let the user choose the chore to track:
            vol.Optional(
                const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID,
                default=const.SENTINEL_EMPTY,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=cast("list[selector.SelectOptionDict]", chore_options),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=False,
                )
            ),
            # For non-streak achievements the user can type criteria freely:
            vol.Optional(
                const.CFOF_ACHIEVEMENTS_INPUT_CRITERIA,
                default="",
            ): str,
            vol.Required(
                const.CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE,
                default=const.DEFAULT_ACHIEVEMENT_TARGET,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
            vol.Required(
                const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS,
                default=const.DEFAULT_ACHIEVEMENT_REWARD_POINTS,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
        }
    )


def validate_achievements_inputs(
    user_input: dict[str, Any],
    existing_achievements: dict[str, Any] | None = None,
    *,
    current_achievement_id: str | None = None,
) -> dict[str, str]:
    """Validate achievement form inputs - UI wrapper for data_builders.

    Extracts DATA_* values from user_input and calls the single source of truth
    validation function in data_builders.

    Note: Since Phase 6 CFOF Key Alignment, CFOF_ACHIEVEMENTS_INPUT_NAME = "name"
    matches DATA_ACHIEVEMENT_NAME = "name". User_input can be passed directly to
    data_builders.build_achievement() after validation.

    Args:
        user_input: Form data with CFOF_* keys (values aligned with DATA_*)
        existing_achievements: Existing achievements for duplicate checking
        current_achievement_id: ID of achievement being edited (exclude from dupe check)

    Returns:
        Dict of errors (empty if validation passes)
    """
    from .. import data_builders as db

    # Transform CFOF_* keys to DATA_* keys
    assigned_assignees = user_input.get(
        const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS, []
    )
    if not isinstance(assigned_assignees, list):
        assigned_assignees = [assigned_assignees] if assigned_assignees else []

    data = {
        const.DATA_ACHIEVEMENT_NAME: user_input.get(
            const.CFOF_ACHIEVEMENTS_INPUT_NAME, ""
        ),
        const.DATA_ACHIEVEMENT_TYPE: user_input.get(
            const.CFOF_ACHIEVEMENTS_INPUT_TYPE, const.ACHIEVEMENT_TYPE_STREAK
        ),
        const.DATA_ACHIEVEMENT_SELECTED_CHORE_ID: user_input.get(
            const.CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID, const.SENTINEL_EMPTY
        ),
        const.DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: assigned_assignees,
    }

    return db.validate_achievement_data(
        data,
        existing_achievements,
        current_achievement_id=current_achievement_id,
    )


# ----------------------------------------------------------------------------------
# CHALLENGES SCHEMA (Layer 1: Schema + Layer 2: UI Validation Wrapper)
# ----------------------------------------------------------------------------------


def build_challenge_schema(assignees_dict, chores_dict, default=None):
    """Build a schema for challenges, referencing assignees by name (like chores).

    Args:
        assignees_dict: Mapping of assignee names to internal IDs (same as chores).
        chores_dict: Mapping of chore IDs to chore data for selection.
        default: Optional dict with default/suggested values for the form.
                 For DateTimeSelector fields, values must be in "%Y-%m-%d %H:%M:%S"
                 format (local timezone, space separator - NOT ISO format with T).
    """
    default = default or {}
    # Use names as values (same pattern as chores)
    assignee_choices = list(assignees_dict.keys())

    chore_options = [{"value": const.SENTINEL_EMPTY, "label": const.LABEL_NONE}]
    for chore_id, chore_data in chores_dict.items():
        chore_name = chore_data.get(const.DATA_CHORE_NAME, f"Chore {chore_id[:6]}")
        chore_options.append({"value": chore_id, "label": chore_name})

    return vol.Schema(
        {
            vol.Required(const.CFOF_CHALLENGES_INPUT_NAME): str,
            vol.Optional(
                const.CFOF_CHALLENGES_INPUT_DESCRIPTION,
                default="",
            ): str,
            vol.Optional(
                const.CFOF_CHALLENGES_INPUT_LABELS,
                default=[],
            ): selector.LabelSelector(selector.LabelSelectorConfig(multiple=True)),
            vol.Optional(const.CFOF_CHALLENGES_INPUT_ICON): selector.IconSelector(),
            vol.Required(
                const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS,
                default=[],
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=assignee_choices,
                    translation_key=const.TRANS_KEY_FLOW_HELPERS_ASSIGNED_USER_IDS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                const.CFOF_CHALLENGES_INPUT_TYPE,
                default=const.CHALLENGE_TYPE_DAILY_MIN,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=cast(
                        "list[selector.SelectOptionDict]", const.CHALLENGE_TYPE_OPTIONS
                    ),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            # If type == "chore_streak", let the user choose the chore to track:
            vol.Optional(
                const.CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID,
                default=const.SENTINEL_EMPTY,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=cast("list[selector.SelectOptionDict]", chore_options),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=False,
                )
            ),
            # For non-streak challenges the user can type criteria freely:
            vol.Optional(
                const.CFOF_CHALLENGES_INPUT_CRITERIA,
                default="",
            ): str,
            vol.Required(
                const.CFOF_CHALLENGES_INPUT_TARGET_VALUE,
                default=const.DEFAULT_CHALLENGE_TARGET,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
            vol.Required(
                const.CFOF_CHALLENGES_INPUT_REWARD_POINTS,
                default=const.DEFAULT_CHALLENGE_REWARD_POINTS,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    step=0.1,
                )
            ),
            vol.Optional(
                const.CFOF_CHALLENGES_INPUT_START_DATE,
                default=default.get(const.CFOF_CHALLENGES_INPUT_START_DATE),
            ): vol.Any(None, selector.DateTimeSelector()),
            vol.Optional(
                const.CFOF_CHALLENGES_INPUT_END_DATE,
                default=default.get(const.CFOF_CHALLENGES_INPUT_END_DATE),
            ): vol.Any(None, selector.DateTimeSelector()),
        }
    )


def validate_challenges_inputs(
    user_input: dict[str, Any],
    existing_challenges: dict[str, Any] | None = None,
    *,
    current_challenge_id: str | None = None,
) -> dict[str, str]:
    """Validate challenge form inputs - UI wrapper for data_builders.

    Extracts DATA_* values from user_input and calls the single source of truth
    validation function in data_builders.

    Note: Since Phase 6 CFOF Key Alignment, CFOF_CHALLENGES_INPUT_NAME = "name"
    matches DATA_CHALLENGE_NAME = "name". User_input can be passed directly to
    data_builders.build_challenge() after validation.

    Args:
        user_input: Form data with CFOF_* keys (values aligned with DATA_*)
        existing_challenges: Existing challenges for duplicate checking
        current_challenge_id: ID of challenge being edited (exclude from dupe check)

    Returns:
        Dict of errors (empty if validation passes)
    """
    from .. import data_builders as db

    # Transform CFOF_* keys to DATA_* keys
    assigned_assignees = user_input.get(
        const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS, []
    )
    if not isinstance(assigned_assignees, list):
        assigned_assignees = [assigned_assignees] if assigned_assignees else []

    data = {
        const.DATA_CHALLENGE_NAME: user_input.get(const.CFOF_CHALLENGES_INPUT_NAME, ""),
        const.DATA_CHALLENGE_ASSIGNED_USER_IDS: assigned_assignees,
        const.DATA_CHALLENGE_START_DATE: user_input.get(
            const.CFOF_CHALLENGES_INPUT_START_DATE
        ),
        const.DATA_CHALLENGE_END_DATE: user_input.get(
            const.CFOF_CHALLENGES_INPUT_END_DATE
        ),
        const.DATA_CHALLENGE_TARGET_VALUE: user_input.get(
            const.CFOF_CHALLENGES_INPUT_TARGET_VALUE, 0
        ),
        const.DATA_CHALLENGE_REWARD_POINTS: user_input.get(
            const.CFOF_CHALLENGES_INPUT_REWARD_POINTS, 0
        ),
    }

    return db.validate_challenge_data(
        data,
        existing_challenges,
        current_challenge_id=current_challenge_id,
    )


# ----------------------------------------------------------------------------------
# GENERAL OPTIONS SCHEMA
# ----------------------------------------------------------------------------------


def build_general_options_schema(default: dict | None = None) -> vol.Schema:
    """Build schema for general options including points adjust values and update interval."""
    default = default or {}
    current_values = default.get(const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES)
    if current_values and isinstance(current_values, list):
        default_points_str = "|".join(str(v) for v in current_values)
    else:
        default_points_str = "|".join(
            str(v) for v in const.DEFAULT_POINTS_ADJUST_VALUES
        )

    default_interval = default.get(
        const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
    )
    default_calendar_period = default.get(
        const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD, const.DEFAULT_CALENDAR_SHOW_PERIOD
    )

    # Consolidated retention periods (pipe-separated: Daily|Weekly|Monthly|Yearly)
    default_retention_daily = default.get(
        const.CFOF_SYSTEM_INPUT_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
    )
    default_retention_weekly = default.get(
        const.CFOF_SYSTEM_INPUT_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
    )
    default_retention_monthly = default.get(
        const.CFOF_SYSTEM_INPUT_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
    )
    default_retention_yearly = default.get(
        const.CFOF_SYSTEM_INPUT_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
    )
    default_retention_periods = format_retention_periods(
        default_retention_daily,
        default_retention_weekly,
        default_retention_monthly,
        default_retention_yearly,
    )

    default_show_legacy_entities = default.get(
        const.CONF_SHOW_LEGACY_ENTITIES, const.DEFAULT_SHOW_LEGACY_ENTITIES
    )
    default_kiosk_mode = default.get(const.CONF_KIOSK_MODE, const.DEFAULT_KIOSK_MODE)

    return vol.Schema(
        {
            vol.Required(
                const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES, default=default_points_str
            ): str,
            vol.Required(
                const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL, default=default_interval
            ): cv.positive_int,
            vol.Required(
                const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD,
                default=default_calendar_period,
            ): cv.positive_int,
            vol.Required(
                const.CFOF_SYSTEM_INPUT_RETENTION_PERIODS,
                default=default_retention_periods,
            ): str,
            vol.Required(
                const.CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES,
                default=default_show_legacy_entities,
            ): selector.BooleanSelector(),
            vol.Required(
                const.CFOF_SYSTEM_INPUT_KIOSK_MODE,
                default=default_kiosk_mode,
            ): selector.BooleanSelector(),
            vol.Required(
                const.CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED,
                default=default.get(
                    const.CONF_BACKUPS_MAX_RETAINED,
                    const.DEFAULT_BACKUPS_MAX_RETAINED,
                ),
            ): cv.positive_int,
            vol.Optional(
                const.CFOF_BACKUP_ACTION_SELECTION,
                default=const.OPTIONS_FLOW_BACKUP_ACTION_SELECT,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        const.OPTIONS_FLOW_BACKUP_ACTION_SELECT,
                        const.OPTIONS_FLOW_BACKUP_ACTION_CREATE,
                        const.OPTIONS_FLOW_BACKUP_ACTION_RESTORE,
                        const.OPTIONS_FLOW_BACKUP_ACTION_DELETE,
                    ],
                    translation_key=const.TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def format_retention_periods(daily: int, weekly: int, monthly: int, yearly: int) -> str:
    """Format retention periods as pipe-separated string for display.

    Args:
        daily: Daily retention count
        weekly: Weekly retention count
        monthly: Monthly retention count
        yearly: Yearly retention count

    Returns:
        Pipe-separated string (e.g., "7|4|12|3")
    """
    return f"{daily}|{weekly}|{monthly}|{yearly}"


def parse_retention_periods(retention_str: str) -> tuple[int, int, int, int]:
    """Parse pipe-separated retention periods string.

    Args:
        retention_str: Pipe-separated string (e.g., "7|4|12|3")

    Returns:
        Tuple of (daily, weekly, monthly, yearly) as integers

    Raises:
        ValueError: If format is invalid or values are not positive integers
    """
    try:
        parts = [p.strip() for p in retention_str.split("|")]
        if len(parts) != 4:
            raise ValueError(
                f"Expected 4 values (Daily|Weekly|Monthly|Yearly), got {len(parts)}"
            )

        daily, weekly, monthly, yearly = [int(p) for p in parts]

        if not all(v > 0 for v in [daily, weekly, monthly, yearly]):
            raise ValueError("All retention values must be positive integers")

        return daily, weekly, monthly, yearly
    except (ValueError, AttributeError) as ex:
        raise ValueError(
            f"Invalid retention format. Expected 'Daily|Weekly|Monthly|Yearly' "
            f"(e.g., '7|4|12|3'): {ex}"
        ) from ex


# ----------------------------------------------------------------------------------
# SYSTEM SETTINGS CONSOLIDATION
# ----------------------------------------------------------------------------------


def build_all_system_settings_schema(
    default_points_label: str | None = None,
    default_points_icon: str | None = None,
    default_update_interval: int | None = None,
    default_calendar_show_period: int | None = None,
    default_retention_daily: int | None = None,
    default_retention_weekly: int | None = None,
    default_retention_monthly: int | None = None,
    default_retention_yearly: int | None = None,
    default_points_adjust_values: list[int] | None = None,
) -> vol.Schema:
    """Build form schema for all 9 system settings.

    Combines points schema, update interval, calendar period, retention periods,
    and points adjust values into a single comprehensive schema.

    Args:
        default_points_label: Points label (e.g., "Points", "Stars")
        default_points_icon: MDI icon for points
        default_update_interval: Coordinator update interval in minutes
        default_calendar_show_period: Calendar lookback period in days
        default_retention_daily: Days retention for daily history
        default_retention_weekly: Weeks retention for weekly history
        default_retention_monthly: Months retention for monthly history
        default_retention_yearly: Years retention for yearly history
        default_points_adjust_values: List of point adjustment values

    Returns:
        vol.Schema with all 9 system settings fields
    """
    # Use defaults if not provided
    defaults = {
        "points_label": default_points_label or const.DEFAULT_POINTS_LABEL,
        "points_icon": default_points_icon or const.DEFAULT_POINTS_ICON,
        "update_interval": default_update_interval or const.DEFAULT_UPDATE_INTERVAL,
        "calendar_show_period": default_calendar_show_period
        or const.DEFAULT_CALENDAR_SHOW_PERIOD,
        "retention_daily": default_retention_daily or const.DEFAULT_RETENTION_DAILY,
        "retention_weekly": default_retention_weekly or const.DEFAULT_RETENTION_WEEKLY,
        "retention_monthly": default_retention_monthly
        or const.DEFAULT_RETENTION_MONTHLY,
        "retention_yearly": default_retention_yearly or const.DEFAULT_RETENTION_YEARLY,
        "points_adjust_values": default_points_adjust_values
        or const.DEFAULT_POINTS_ADJUST_VALUES,
    }

    # Build combined schema from points + other settings
    points_fields = build_points_schema(
        default_label=defaults["points_label"],
        default_icon=defaults["points_icon"],
    )

    # Add update interval field
    update_interval_fields = {
        vol.Required(
            const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL, default=defaults["update_interval"]
        ): cv.positive_int,
    }

    # Add calendar period field
    calendar_fields = {
        vol.Required(
            const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD,
            default=defaults["calendar_show_period"],
        ): cv.positive_int,
    }

    # Add retention period fields
    retention_fields = {
        vol.Required(
            const.CFOF_SYSTEM_INPUT_RETENTION_DAILY, default=defaults["retention_daily"]
        ): cv.positive_int,
        vol.Required(
            const.CFOF_SYSTEM_INPUT_RETENTION_WEEKLY,
            default=defaults["retention_weekly"],
        ): cv.positive_int,
        vol.Required(
            const.CFOF_SYSTEM_INPUT_RETENTION_MONTHLY,
            default=defaults["retention_monthly"],
        ): cv.positive_int,
        vol.Required(
            const.CFOF_SYSTEM_INPUT_RETENTION_YEARLY,
            default=defaults["retention_yearly"],
        ): cv.positive_int,
    }

    # Convert points adjust values list to pipe-separated string for form field
    points_adjust_default = defaults["points_adjust_values"]
    if isinstance(points_adjust_default, list):
        points_adjust_str = "|".join(str(v) for v in points_adjust_default)
    else:
        points_adjust_str = str(points_adjust_default)

    # Add points adjust values field (simple string, parsed during validation)
    adjust_values_fields = {
        vol.Required(
            const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES,
            default=points_adjust_str,
        ): str,
    }

    # Combine all fields
    all_fields = {
        **points_fields.schema,
        **update_interval_fields,
        **calendar_fields,
        **retention_fields,
        **adjust_values_fields,
    }

    return vol.Schema(all_fields)


def validate_all_system_settings(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate all 9 system settings.

    Validates points label/icon, update interval, calendar period,
    retention periods, and points adjust values.

    Args:
        user_input: Form input from user

    Returns:
        dict: Errors dictionary (empty if valid)
    """
    errors: dict[str, str] = {}

    # Validate points using existing function
    points_errors = validate_points_inputs(user_input)
    if points_errors:
        errors.update(points_errors)

    # Validate update interval
    update_interval = user_input.get(const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL)
    if update_interval is not None and not isinstance(update_interval, int):
        try:
            int(update_interval)
        except (ValueError, TypeError):
            errors[const.CFOP_ERROR_UPDATE_INTERVAL] = (
                const.TRANS_KEY_CFOF_INVALID_UPDATE_INTERVAL
            )

    # Validate calendar show period
    calendar_period = user_input.get(const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD)
    if calendar_period is not None and not isinstance(calendar_period, int):
        try:
            int(calendar_period)
        except (ValueError, TypeError):
            errors[const.CFOP_ERROR_CALENDAR_SHOW_PERIOD] = (
                const.TRANS_KEY_CFOF_INVALID_CALENDAR_SHOW_PERIOD
            )

    # Validate retention periods (all positive ints)
    for field, error_key in [
        (const.CFOF_SYSTEM_INPUT_RETENTION_DAILY, const.CFOP_ERROR_RETENTION_DAILY),
        (const.CFOF_SYSTEM_INPUT_RETENTION_WEEKLY, const.CFOP_ERROR_RETENTION_WEEKLY),
        (const.CFOF_SYSTEM_INPUT_RETENTION_MONTHLY, const.CFOP_ERROR_RETENTION_MONTHLY),
        (const.CFOF_SYSTEM_INPUT_RETENTION_YEARLY, const.CFOP_ERROR_RETENTION_YEARLY),
    ]:
        value = user_input.get(field)
        if value is not None and not isinstance(value, int):
            try:
                int(value)
            except (ValueError, TypeError):
                errors[error_key] = const.TRANS_KEY_CFOF_INVALID_RETENTION_PERIOD

    # Validate points adjust values (parse pipe-separated string)
    adjust_values = user_input.get(const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES)
    if adjust_values is not None:
        if isinstance(adjust_values, str):
            try:
                # Parse pipe-separated values to list of floats (handles decimal separators)
                parsed_values = [
                    float(v.strip().replace(",", "."))
                    for v in adjust_values.split("|")
                    if v.strip()
                ]
                # Update user_input with parsed list for downstream processing
                user_input[const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES] = parsed_values
            except (ValueError, TypeError):
                errors[const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES] = (
                    const.TRANS_KEY_CFOF_INVALID_POINTS_ADJUST_VALUES
                )
        elif not isinstance(adjust_values, list):
            errors[const.CFOP_ERROR_POINTS_ADJUST_VALUES] = (
                const.TRANS_KEY_CFOF_INVALID_POINTS_ADJUST_VALUES
            )

    return errors


def build_all_system_settings_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build 9-key system settings options dictionary from user input.

    Extracts all 9 system setting values from user input and returns
    a dictionary ready for config_entry.options.

    Args:
        user_input: Form input from user (assumed valid)

    Returns:
        dict: 9-key dictionary with system settings
    """
    # Build points settings using existing function
    points_data = build_points_data(user_input)

    # Extract other settings
    settings_data = {
        const.CONF_UPDATE_INTERVAL: user_input.get(
            const.CFOF_SYSTEM_INPUT_UPDATE_INTERVAL, const.DEFAULT_UPDATE_INTERVAL
        ),
        const.CONF_CALENDAR_SHOW_PERIOD: user_input.get(
            const.CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD,
            const.DEFAULT_CALENDAR_SHOW_PERIOD,
        ),
        const.CONF_RETENTION_DAILY: user_input.get(
            const.CFOF_SYSTEM_INPUT_RETENTION_DAILY, const.DEFAULT_RETENTION_DAILY
        ),
        const.CONF_RETENTION_WEEKLY: user_input.get(
            const.CFOF_SYSTEM_INPUT_RETENTION_WEEKLY, const.DEFAULT_RETENTION_WEEKLY
        ),
        const.CONF_RETENTION_MONTHLY: user_input.get(
            const.CFOF_SYSTEM_INPUT_RETENTION_MONTHLY, const.DEFAULT_RETENTION_MONTHLY
        ),
        const.CONF_RETENTION_YEARLY: user_input.get(
            const.CFOF_SYSTEM_INPUT_RETENTION_YEARLY, const.DEFAULT_RETENTION_YEARLY
        ),
    }

    # Handle points adjust values - should already be converted to floats by validation
    points_adjust_values = user_input.get(
        const.CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES,
        const.DEFAULT_POINTS_ADJUST_VALUES,
    )

    settings_data[const.CONF_POINTS_ADJUST_VALUES] = points_adjust_values

    # Combine points + other settings into single dict
    return {**points_data, **settings_data}


# ----------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------------------------------


def _build_notification_defaults(default: dict[str, Any]) -> list[str]:
    """Build default notification options from config.

    Args:
        default: Dictionary containing existing configuration defaults.

    Returns:
        List of selected notification option values.
    """
    notifications = []
    if default.get(
        const.CFOF_CHORES_INPUT_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
    ):
        notifications.append(const.DATA_CHORE_NOTIFY_ON_CLAIM)
    if default.get(
        const.CFOF_CHORES_INPUT_NOTIFY_ON_APPROVAL, const.DEFAULT_NOTIFY_ON_APPROVAL
    ):
        notifications.append(const.DATA_CHORE_NOTIFY_ON_APPROVAL)
    if default.get(
        const.CFOF_CHORES_INPUT_NOTIFY_ON_DISAPPROVAL,
        const.DEFAULT_NOTIFY_ON_DISAPPROVAL,
    ):
        notifications.append(const.DATA_CHORE_NOTIFY_ON_DISAPPROVAL)
    if default.get(
        const.CFOF_CHORES_INPUT_NOTIFY_ON_DUE_WINDOW,
        const.DEFAULT_NOTIFY_ON_DUE_WINDOW,
    ):
        notifications.append(const.DATA_CHORE_NOTIFY_ON_DUE_WINDOW)
    if default.get(
        const.CFOF_CHORES_INPUT_NOTIFY_DUE_REMINDER,
        const.DEFAULT_NOTIFY_DUE_REMINDER,
    ):
        notifications.append(const.DATA_CHORE_NOTIFY_DUE_REMINDER)
    if default.get(
        const.CFOF_CHORES_INPUT_NOTIFY_ON_OVERDUE,
        const.DEFAULT_NOTIFY_ON_OVERDUE,
    ):
        notifications.append(const.DATA_CHORE_NOTIFY_ON_OVERDUE)
    return notifications


def _get_notify_services(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return a list of all notify.* services as value/label dictionaries for selector options."""
    services_list = []
    all_services = hass.services.async_services()
    if const.NOTIFY_DOMAIN in all_services:
        for service_name in all_services[const.NOTIFY_DOMAIN]:
            fullname = f"{const.NOTIFY_DOMAIN}.{service_name}"
            services_list.append({"value": fullname, "label": fullname})
    return services_list
