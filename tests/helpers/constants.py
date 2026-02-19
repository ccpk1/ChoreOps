"""Test constants for ChoreOps integration tests.

This module re-exports all constants from the integration for use in tests.
Import from here, not directly from custom_components.choreops.const.

⚠️  IMPORTANT: DO NOT REMOVE "UNUSED" IMPORTS ⚠️
This is a re-export module. All imports are intentionally used by test files
via `from tests.helpers import CONSTANT_NAME`. They appear unused here but are
critical for the test suite. The file is protected by pyproject.toml
per-file-ignores:
  - F401: Prevents removal of "unused" imports
  - I001: Prevents isort from reordering sections

The imports are organized by logical sections with comment headers. DO NOT
allow any auto-formatter or linter to reorder them.

=============================================================================
QUICK REFERENCE
=============================================================================

CHORE STATUS SENSOR STATE VALUES (sensor.kc_<assignee>_chore_status_<chore>):
    - CHORE_STATE_PENDING: Initial state, chore not yet claimed
    - CHORE_STATE_CLAIMED: Assignee has claimed, awaiting approval
    - CHORE_STATE_APPROVED: Chore completed and approved
    - CHORE_STATE_OVERDUE: Past due date without completion
    - CHORE_STATE_CLAIMED_IN_PART: Partial claim (shared chores)
    - CHORE_STATE_APPROVED_IN_PART: Partial approval (shared chores)
    - "completed_by_other": Computed display state (Phase 2, not in FSM)

GLOBAL STATE ATTRIBUTE (ATTR_GLOBAL_STATE on chore status sensor):
    The global_state attribute shows the aggregated chore state across all
    assigned assignees. See test_constants.py for full documentation.

=============================================================================
"""

# pylint: disable=unused-import

from custom_components.choreops.const import (
    APPROVAL_RESET_AT_DUE_DATE_MULTI,
    APPROVAL_RESET_AT_DUE_DATE_ONCE,
    APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    # =========================================================================
    # APPROVAL RESET TYPES
    # =========================================================================
    APPROVAL_RESET_AT_MIDNIGHT_ONCE,
    APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
    APPROVAL_RESET_PENDING_CLAIM_CLEAR,
    # =========================================================================
    # PENDING CLAIM ACTIONS
    # =========================================================================
    APPROVAL_RESET_PENDING_CLAIM_HOLD,
    APPROVAL_RESET_UPON_COMPLETION,
    # =========================================================================
    # SENSOR ATTRIBUTES - Chore Status Sensor
    # =========================================================================
    ATTR_APPROVAL_RESET_TYPE,
    ATTR_CAN_APPROVE,
    ATTR_CAN_CLAIM,
    ATTR_CHORE_APPROVALS_COUNT,
    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID,
    ATTR_CHORE_CLAIMS_COUNT,
    ATTR_CHORE_CURRENT_STREAK,
    ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID,
    ATTR_CHORE_LONGEST_STREAK,
    ATTR_CHORE_POINTS_EARNED,
    ATTR_CLAIMED_BY,
    ATTR_COMPLETED_BY,
    ATTR_COMPLETION_CRITERIA,
    ATTR_COST,
    # =========================================================================
    # DASHBOARD HELPER SENSOR ATTRIBUTES
    # =========================================================================
    ATTR_DASHBOARD_ACHIEVEMENTS,
    ATTR_DASHBOARD_BADGES,
    ATTR_DASHBOARD_BONUSES,
    ATTR_DASHBOARD_CHALLENGES,
    ATTR_DASHBOARD_CHORES,
    ATTR_DASHBOARD_USER_NAME,
    ATTR_DASHBOARD_PENALTIES,
    ATTR_DASHBOARD_PENDING_APPROVALS,
    ATTR_DASHBOARD_POINTS_BUTTONS,
    ATTR_DASHBOARD_REWARDS,
    ATTR_DASHBOARD_UI_TRANSLATIONS,
    ATTR_DEFAULT_POINTS,
    ATTR_DUE_DATE,
    ATTR_GLOBAL_STATE,
    ATTR_LAST_APPROVED,
    ATTR_LAST_CLAIMED,
    ATTR_RECURRING_FREQUENCY,
    ATTR_TRANSLATION_SENSOR_EID,
    # =========================================================================
    # SENSOR ATTRIBUTES - Reward Status Sensor
    # =========================================================================
    ATTR_REWARD_APPROVALS_COUNT,
    ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID,
    ATTR_REWARD_CLAIM_BUTTON_ENTITY_ID,
    ATTR_REWARD_CLAIMS_COUNT,
    ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID,
    # =========================================================================
    # ENTITY ID COMPONENTS
    # =========================================================================
    BUTTON_KC_UID_SUFFIX_APPROVE,
    BUTTON_KC_UID_SUFFIX_CLAIM,
    BUTTON_KC_UID_SUFFIX_DISAPPROVE,
    # =========================================================================
    # CONFIG FLOW STEP IDS
    # =========================================================================
    CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT,
    CONFIG_FLOW_STEP_ACHIEVEMENTS,
    CONFIG_FLOW_STEP_BADGE_COUNT,
    CONFIG_FLOW_STEP_BADGES,
    CONFIG_FLOW_STEP_BONUS_COUNT,
    CONFIG_FLOW_STEP_BONUSES,
    CONFIG_FLOW_STEP_CHALLENGE_COUNT,
    CONFIG_FLOW_STEP_CHALLENGES,
    CONFIG_FLOW_STEP_CHORE_COUNT,
    CONFIG_FLOW_STEP_CHORES,
    CONFIG_FLOW_STEP_DATA_RECOVERY,
    CONFIG_FLOW_STEP_FINISH,
    CONFIG_FLOW_STEP_INTRO,
    CONFIG_FLOW_STEP_USER_COUNT,
    CONFIG_FLOW_STEP_USERS,
    CONFIG_FLOW_STEP_PENALTY_COUNT,
    CONFIG_FLOW_STEP_PENALTIES,
    CONFIG_FLOW_STEP_POINTS,
    CONFIG_FLOW_STEP_RECONFIGURE,
    CONFIG_FLOW_STEP_REWARD_COUNT,
    CONFIG_FLOW_STEP_REWARDS,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Assignees
    # =========================================================================
    CFOF_USERS_INPUT_DASHBOARD_LANGUAGE,
    CFOF_USERS_INPUT_NAME,
    CFOF_USERS_INPUT_HA_USER_ID,
    CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Approvers
    # =========================================================================
    CFOF_USERS_INPUT_COUNT,
    CFOF_USERS_INPUT_ASSOCIATED_USER_IDS,
    CFOF_USERS_INPUT_CAN_BE_ASSIGNED,
    CFOF_USERS_INPUT_CAN_APPROVE,
    CFOF_USERS_INPUT_CAN_MANAGE,
    CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW,
    CFOF_USERS_INPUT_ENABLE_GAMIFICATION,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Chores
    # =========================================================================
    CFOF_CHORES_INPUT_NAME,
    CFOF_CHORES_INPUT_CHORE_COUNT,
    CFOF_CHORES_INPUT_DEFAULT_POINTS,
    CFOF_CHORES_INPUT_ICON,
    CFOF_CHORES_INPUT_DESCRIPTION,
    CFOF_CHORES_INPUT_ASSIGNED_USER_IDS,
    CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
    CFOF_CHORES_INPUT_APPLICABLE_DAYS,
    CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
    CFOF_CHORES_INPUT_AUTO_APPROVE,
    CFOF_CHORES_INPUT_CUSTOM_INTERVAL,
    CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT,
    CFOF_CHORES_INPUT_DAILY_MULTI_TIMES,
    CFOF_CHORES_INPUT_DUE_DATE,
    CFOF_CHORES_INPUT_LABELS,
    CFOF_CHORES_INPUT_NOTIFICATIONS,
    CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE,
    CFOF_CHORES_INPUT_SHOW_ON_CALENDAR,
    # Per-assignee helper template checkboxes (PKAD-2026-001)
    CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL,
    CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL,
    CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Rewards
    # =========================================================================
    CFOF_REWARDS_INPUT_NAME,
    CFOF_REWARDS_INPUT_REWARD_COUNT,
    CFOF_REWARDS_INPUT_COST,
    CFOF_REWARDS_INPUT_ICON,
    CFOF_REWARDS_INPUT_DESCRIPTION,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Penalties
    # =========================================================================
    CFOF_PENALTIES_INPUT_NAME,
    CFOF_PENALTIES_INPUT_PENALTY_COUNT,
    CFOF_PENALTIES_INPUT_POINTS,
    CFOF_PENALTIES_INPUT_ICON,
    CFOF_PENALTIES_INPUT_DESCRIPTION,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Bonuses
    # =========================================================================
    CFOF_BONUSES_INPUT_NAME,
    CFOF_BONUSES_INPUT_BONUS_COUNT,
    CFOF_BONUSES_INPUT_POINTS,
    CFOF_BONUSES_INPUT_ICON,
    CFOF_BONUSES_INPUT_DESCRIPTION,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Badges
    # =========================================================================
    CFOF_BADGES_INPUT_ASSIGNED_USER_IDS,
    CFOF_BADGES_INPUT_AWARD_ITEMS,
    CFOF_BADGES_INPUT_AWARD_POINTS,
    CFOF_BADGES_INPUT_BADGE_COUNT,
    CFOF_BADGES_INPUT_END_DATE,
    CFOF_BADGES_INPUT_ICON,
    CFOF_BADGES_INPUT_MAINTENANCE_RULES,
    CFOF_BADGES_INPUT_NAME,
    CFOF_BADGES_INPUT_OCCASION_TYPE,
    CFOF_BADGES_INPUT_SELECTED_CHORES,
    CFOF_BADGES_INPUT_START_DATE,
    CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE,
    CFOF_BADGES_INPUT_TARGET_TYPE,
    CFOF_BADGES_INPUT_TYPE,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Achievements
    # =========================================================================
    CFOF_ACHIEVEMENTS_INPUT_NAME,
    CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT,
    CFOF_ACHIEVEMENTS_INPUT_ICON,
    CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION,
    CFOF_ACHIEVEMENTS_INPUT_TYPE,
    CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE,
    CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS,
    CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Challenges
    # =========================================================================
    CFOF_CHALLENGES_INPUT_NAME,
    CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT,
    CFOF_CHALLENGES_INPUT_ICON,
    CFOF_CHALLENGES_INPUT_DESCRIPTION,
    CFOF_CHALLENGES_INPUT_TYPE,
    CFOF_CHALLENGES_INPUT_TARGET_VALUE,
    CFOF_CHALLENGES_INPUT_REWARD_POINTS,
    CFOF_CHALLENGES_INPUT_START_DATE,
    CFOF_CHALLENGES_INPUT_END_DATE,
    CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - System Settings
    # =========================================================================
    CFOF_SYSTEM_INPUT_POINTS_LABEL,
    CFOF_SYSTEM_INPUT_POINTS_ICON,
    CFOF_SYSTEM_INPUT_UPDATE_INTERVAL,
    CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD,
    CFOF_SYSTEM_INPUT_RETENTION_DAILY,
    CFOF_SYSTEM_INPUT_RETENTION_WEEKLY,
    CFOF_SYSTEM_INPUT_RETENTION_MONTHLY,
    CFOF_SYSTEM_INPUT_RETENTION_YEARLY,
    CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES,
    CFOF_SYSTEM_INPUT_RETENTION_PERIODS,
    CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES,
    CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Data Recovery
    # =========================================================================
    CFOF_DATA_RECOVERY_INPUT_SELECTION,
    CFOF_DATA_RECOVERY_INPUT_JSON_DATA,
    # =========================================================================
    # OPTIONS FLOW NAVIGATION CONSTANTS
    # =========================================================================
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_STEP_MANAGE_ENTITY,
    OPTIONS_FLOW_STEP_SELECT_ENTITY,
    OPTIONS_FLOW_STEP_ADD_USER,
    OPTIONS_FLOW_STEP_EDIT_USER,
    OPTIONS_FLOW_STEP_ADD_CHORE,
    OPTIONS_FLOW_STEP_ADD_REWARD,
    OPTIONS_FLOW_STEP_ADD_PENALTY,
    OPTIONS_FLOW_STEP_ADD_BONUS,
    OPTIONS_FLOW_STEP_ADD_BADGE,
    OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT,
    OPTIONS_FLOW_STEP_ADD_CHALLENGE,
    OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI,
    # Per-assignee helper step IDs (PKAD-2026-001)
    OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DATES,
    OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DETAILS,
    OPTIONS_FLOW_STEP_EDIT_CHORE,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_USERS,
    OPTIONS_FLOW_CHORES,
    OPTIONS_FLOW_REWARDS,
    OPTIONS_FLOW_PENALTIES,
    OPTIONS_FLOW_BONUSES,
    OPTIONS_FLOW_BADGES,
    OPTIONS_FLOW_ACHIEVEMENTS,
    OPTIONS_FLOW_CHALLENGES,
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_ACTIONS_BACK,
    OPTIONS_FLOW_ACTIONS_EDIT,
    OPTIONS_FLOW_INPUT_ENTITY_NAME,
    OPTIONS_FLOW_GENERAL_OPTIONS,
    # =========================================================================
    # CONFIG/OPTIONS FLOW FIELD NAMES - Backup
    # =========================================================================
    CFOF_BACKUP_ACTION_SELECTION,
    CFOF_BACKUP_SELECTION,
    # =========================================================================
    # SYSTEM CONFIG CONSTANTS
    # =========================================================================
    CONF_POINTS_LABEL,
    CONF_POINTS_ICON,
    CONF_SHOW_LEGACY_ENTITIES,
    CONF_UPDATE_INTERVAL,
    CONF_BACKUPS_MAX_RETAINED,
    SCHEMA_VERSION_STORAGE_ONLY,
    # =========================================================================
    # BACKUP CONSTANTS
    # =========================================================================
    BACKUP_TAG_MANUAL,
    BACKUP_TAG_RECOVERY,
    BACKUP_TAG_RESET,
    # =========================================================================
    # ACTION CONSTANTS
    # =========================================================================
    ACTION_APPROVE_CHORE,
    ACTION_APPROVE_REWARD,
    ACTION_DISAPPROVE_CHORE,
    ACTION_DISAPPROVE_REWARD,
    ACTION_REMIND_30,
    # =========================================================================
    # BADGE CONSTANTS
    # =========================================================================
    BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
    BADGE_TARGET_THRESHOLD_TYPE_POINTS,
    BADGE_TYPE_CUMULATIVE,
    BADGE_TYPE_DAILY,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION,
    # =========================================================================
    # CHORE STATES
    # =========================================================================
    CHORE_STATE_APPROVED,
    CHORE_STATE_APPROVED_IN_PART,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_CLAIMED_IN_PART,
    CHORE_STATE_INDEPENDENT,
    CHORE_STATE_MISSED,  # v0.5.0
    CHORE_STATE_NOT_MY_TURN,  # v0.5.0
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PENDING,
    CHORE_STATE_UNKNOWN,
    CHORE_STATE_WAITING,  # v0.5.0
    # =========================================================================
    # COMPLETION CRITERIA
    # =========================================================================
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    COMPLETION_CRITERIA_ROTATION_SIMPLE,  # v0.5.0
    COMPLETION_CRITERIA_ROTATION_SMART,  # v0.5.0
    # =========================================================================
    # DOMAIN & COORDINATOR
    # =========================================================================
    COORDINATOR,
    # =========================================================================
    # DATA KEYS - TOP LEVEL
    # =========================================================================
    DATA_ACHIEVEMENTS,
    DATA_BADGES,
    DATA_BONUSES,
    DATA_CHALLENGES,
    # =========================================================================
    # DATA KEYS - CHORE FIELDS
    # =========================================================================
    DATA_CHORE_APPLICABLE_DAYS,
    DATA_CHORE_APPROVAL_PERIOD_START,
    DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    DATA_CHORE_APPROVAL_RESET_TYPE,
    DATA_CHORE_ASSIGNED_USER_IDS,
    DATA_CHORE_COMPLETION_CRITERIA,
    DATA_CHORE_CUSTOM_INTERVAL,
    DATA_CHORE_CUSTOM_INTERVAL_UNIT,
    DATA_CHORE_DAILY_MULTI_TIMES,
    DATA_CHORE_DEFAULT_POINTS,
    DATA_CHORE_DESCRIPTION,
    DATA_CHORE_DUE_DATE,
    DATA_CHORE_ICON,
    DATA_CHORE_INTERNAL_ID,
    DATA_CHORE_LABELS,
    DATA_CHORE_NAME,
    DATA_CHORE_OVERDUE_HANDLING_TYPE,
    DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS,
    DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES,
    DATA_CHORE_PER_ASSIGNEE_DUE_DATES,
    DATA_CHORE_RECURRING_FREQUENCY,
    DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID,  # v0.5.0
    DATA_CHORE_ROTATION_CYCLE_OVERRIDE,  # v0.5.0
    DATA_CHORE_SHOW_ON_CALENDAR,
    DATA_CHORE_STATE,
    DATA_CHORE_TIMESTAMP,
    DATA_CHORES,
    # =========================================================================
    # DATA KEYS - KID FIELDS
    # =========================================================================
    DATA_USER_BADGE_PROGRESS,
    DATA_USER_BADGES_EARNED,
    DATA_USER_CHORE_DATA,
    DATA_USER_CUMULATIVE_BADGE_PROGRESS,
    DATA_USER_CHORE_DATA_APPROVAL_PERIOD_START,
    DATA_USER_CHORE_DATA_LAST_APPROVED,
    DATA_USER_CHORE_DATA_LAST_CLAIMED,
    DATA_USER_CHORE_DATA_LAST_DISAPPROVED,
    DATA_USER_CHORE_DATA_LAST_MISSED,  # Phase 5: Missed tracking
    DATA_USER_CHORE_DATA_PENDING_CLAIM_COUNT,
    DATA_USER_CHORE_DATA_PERIODS,  # Phase 5: Period buckets structure
    DATA_USER_CHORE_DATA_PERIODS_DAILY,  # Phase 5: Daily buckets
    DATA_USER_CHORE_DATA_PERIODS_WEEKLY,  # Phase 5: Weekly buckets
    DATA_USER_CHORE_DATA_PERIODS_MONTHLY,  # Phase 5: Monthly buckets
    DATA_USER_CHORE_DATA_PERIODS_YEARLY,  # Phase 5: Yearly buckets
    DATA_USER_CHORE_DATA_PERIOD_MISSED,  # Phase 5: Missed count key
    DATA_USER_CHORE_DATA_STATE,
    DATA_USER_CHORE_DATA_TOTAL_COUNT,
    DATA_USER_CHORE_DATA_TOTAL_POINTS,
    DATA_USER_CHORE_PERIODS,  # v43+ aggregated chore periods
    DATA_USER_CHORE_DATA_PERIODS_ALL_TIME,  # v43+ all_time bucket key
    DATA_USER_CHORE_DATA_PERIOD_APPROVED,  # v43+ approved count key
    DATA_USER_CHORE_DATA_PERIOD_POINTS,  # v43+ points key
    DATA_ASSIGNEE_CHORE_STATS_LEGACY,  # v43+ moved to LEGACY, use DATA_USER_CHORE_PERIODS
    # Phase 2: DATA_KID_COMPLETED_BY_OTHER_CHORES removed (was line 419)
    DATA_USER_HA_USER_ID,
    DATA_USER_INTERNAL_ID,
    DATA_USER_NAME,
    # DATA_KID_OVERDUE_CHORES removed - dead code, see DATA_KID_OVERDUE_CHORES_LEGACY
    DATA_USER_POINT_PERIODS,  # v43+ flat structure
    DATA_ASSIGNEE_POINT_DATA_LEGACY,  # LEGACY v42 - for migration tests only
    DATA_USER_POINT_PERIOD_HIGHEST_BALANCE,  # v43+ renamed
    DATA_USER_POINT_PERIOD_POINTS_EARNED,  # v43+ renamed
    DATA_USER_POINT_PERIOD_POINTS_SPENT,  # v43+ renamed
    DATA_ASSIGNEE_POINT_DATA_PERIODS_LEGACY,  # LEGACY v42 - for migration tests only
    DATA_USER_POINT_PERIODS_ALL_TIME,  # v43+ renamed
    DATA_ASSIGNEE_POINT_STATS_LEGACY,
    DATA_USER_POINTS,
    DATA_USER_REWARD_DATA,
    DATA_USER_REWARD_DATA_PENDING_COUNT,
    DATA_USERS,
    # =========================================================================
    # DATA KEYS - PARENT FIELDS (Shadow Assignee Support)
    # =========================================================================
    DATA_USER_CAN_BE_ASSIGNED,
    DATA_USER_DASHBOARD_LANGUAGE,
    DATA_USER_ENABLE_CHORE_WORKFLOW,
    DATA_USER_ENABLE_GAMIFICATION,
    DATA_USER_ASSOCIATED_USER_IDS,
    DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
    DATA_USER_MOBILE_NOTIFY_SERVICE,
    DATA_APPROVERS,
    DATA_PENALTIES,
    # =========================================================================
    # DATA KEYS - REWARD FIELDS
    # =========================================================================
    DATA_REWARD_COST,
    DATA_REWARD_DESCRIPTION,
    DATA_REWARD_ICON,
    DATA_REWARD_INTERNAL_ID,
    DATA_REWARD_LABELS,
    DATA_REWARD_NAME,
    DATA_REWARDS,
    # =========================================================================
    # DEFAULTS
    # =========================================================================
    DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION,
    DEFAULT_APPROVAL_RESET_TYPE,
    DEFAULT_OVERDUE_HANDLING_TYPE,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_LABEL,
    DEFAULT_REWARD_COST,
    DEFAULT_ZERO,
    DOMAIN,
    CFOP_ERROR_USER_NAME,
    # =========================================================================
    # FREQUENCIES
    # =========================================================================
    FREQUENCY_CUSTOM,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
    FREQUENCY_DAILY,
    FREQUENCY_DAILY_MULTI,
    FREQUENCY_MONTHLY,
    FREQUENCY_NONE,
    FREQUENCY_WEEKLY,
    # =========================================================================
    # TIME UNITS
    # =========================================================================
    TIME_UNIT_DAYS,
    TIME_UNIT_HOURS,
    TIME_UNIT_MONTHS,
    TIME_UNIT_WEEKS,
    # =========================================================================
    # OVERDUE HANDLING TYPES
    # =========================================================================
    OVERDUE_HANDLING_AT_DUE_DATE,
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED,  # Phase 5
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
    OVERDUE_HANDLING_NEVER_OVERDUE,
    # =========================================================================
    # REWARD STATES
    # =========================================================================
    REWARD_STATE_APPROVED,
    REWARD_STATE_AVAILABLE,
    REWARD_STATE_LOCKED,
    REWARD_STATE_REQUESTED,
    # =========================================================================
    # SERVICE NAMES
    # =========================================================================
    SENTINEL_EMPTY,
    SENTINEL_NONE,
    SENTINEL_NONE_TEXT,
    SENTINEL_NO_SELECTION,
    # =========================================================================
    # TRANSLATION KEYS - NOTIFICATIONS
    # =========================================================================
    TRANS_KEY_NOTIF_ACTION_APPROVE,
    TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
    TRANS_KEY_NOTIF_ACTION_REMIND_30,
    # =========================================================================
    # NOTIFICATION DATA KEYS
    # =========================================================================
    DATA_CHORE_ID,
    DATA_USER_ID,
    DATA_REWARD_ID,
    NOTIFY_ACTION,
    NOTIFY_NOTIFICATION_ID,
    NOTIFY_TITLE,
    # =========================================================================
    # SENSOR ENTITY ID COMPONENTS
    # =========================================================================
    SENSOR_KC_PREFIX,
    SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR,
    # =========================================================================
    # TRANSLATION KEYS (for error assertions)
    # =========================================================================
    TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED,
    # =========================================================================
    # SERVICE NAMES
    # =========================================================================
    SERVICE_CREATE_CHORE,
    SERVICE_UPDATE_CHORE,
    SERVICE_DELETE_CHORE,
    SERVICE_CREATE_REWARD,
    SERVICE_DELETE_REWARD,
    SERVICE_UPDATE_REWARD,
    SERVICE_RESET_CHORES_TO_PENDING_STATE,  # Renamed from SERVICE_RESET_ALL_CHORES
    SERVICE_SKIP_CHORE_DUE_DATE,  # Phase 5
    SERVICE_SET_ROTATION_TURN,  # v0.5.0
    SERVICE_RESET_ROTATION,  # v0.5.0
    SERVICE_OPEN_ROTATION_CYCLE,  # v0.5.0
    # =========================================================================
    # SERVICE FIELD NAMES (for service call payloads)
    # =========================================================================
    SERVICE_FIELD_USER_NAME,
    SERVICE_FIELD_USER_ID,
    SERVICE_FIELD_APPROVER_NAME,
    SERVICE_FIELD_REWARD_ID,
    SERVICE_FIELD_REWARD_NAME,
    SERVICE_FIELD_REWARD_COST_OVERRIDE,
    SERVICE_FIELD_REWARD_CRUD_ID,
    SERVICE_FIELD_REWARD_CRUD_NAME,
    SERVICE_FIELD_REWARD_CRUD_COST,
    SERVICE_FIELD_REWARD_CRUD_DESCRIPTION,
    SERVICE_FIELD_REWARD_CRUD_ICON,
    SERVICE_FIELD_REWARD_CRUD_LABELS,
    SERVICE_FIELD_CHORE_ID,  # v0.5.0
    SERVICE_FIELD_CHORE_NAME,  # v0.5.0
    # =========================================================================
    # SIGNAL SUFFIXES (Phase 5)
    # =========================================================================
    SIGNAL_SUFFIX_CHORE_MISSED,
    SIGNAL_SUFFIX_CHORE_ROTATION_ADVANCED,  # v0.5.0
    # =========================================================================
    # LEGACY CONF KEYS (for migration tests)
    # =========================================================================
)

# Legacy linkage keys are migration-only in production code.
# Re-export as literals for migration-oriented tests.
DATA_ASSIGNEE_IS_SHADOW = "is_shadow_assignee"
DATA_ASSIGNEE_LINKED_APPROVER_ID = "linked_approver_id"
DATA_APPROVER_LINKED_PROFILE_ID = "linked_shadow_assignee_id"

# Test-only identity alias compatibility mappings (Phase 4A batch 6)
DATA_ASSIGNEE_NAME = DATA_USER_NAME
DATA_ASSIGNEE_INTERNAL_ID = DATA_USER_INTERNAL_ID
DATA_ASSIGNEE_HA_USER_ID = DATA_USER_HA_USER_ID
DATA_ASSIGNEE_MOBILE_NOTIFY_SERVICE = DATA_USER_MOBILE_NOTIFY_SERVICE
DATA_APPROVER_NAME = DATA_USER_NAME
DATA_APPROVER_INTERNAL_ID = DATA_USER_INTERNAL_ID
DATA_APPROVER_HA_USER_ID = DATA_USER_HA_USER_ID
DATA_APPROVER_MOBILE_NOTIFY_SERVICE = DATA_USER_MOBILE_NOTIFY_SERVICE
DATA_APPROVER_DASHBOARD_LANGUAGE = DATA_USER_DASHBOARD_LANGUAGE
DATA_APPROVER_ENABLE_CHORE_WORKFLOW = DATA_USER_ENABLE_CHORE_WORKFLOW
DATA_APPROVER_ENABLE_GAMIFICATION = DATA_USER_ENABLE_GAMIFICATION
DATA_APPROVER_ASSOCIATED_USERS = DATA_USER_ASSOCIATED_USER_IDS
DATA_APPROVER_USE_PERSISTENT_NOTIFICATIONS = DATA_USER_USE_PERSISTENT_NOTIFICATIONS
CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME = CFOF_USERS_INPUT_NAME
CFOF_ASSIGNEES_INPUT_HA_USER = CFOF_USERS_INPUT_HA_USER_ID
CFOF_ASSIGNEES_INPUT_MOBILE_NOTIFY_SERVICE = CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE
CFOF_APPROVERS_INPUT_NAME = CFOF_USERS_INPUT_NAME
CFOF_APPROVERS_INPUT_HA_USER = CFOF_USERS_INPUT_HA_USER_ID
CFOF_APPROVERS_INPUT_MOBILE_NOTIFY_SERVICE = CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE
CFOP_ERROR_ASSIGNEE_NAME = CFOP_ERROR_USER_NAME
CFOP_ERROR_APPROVER_NAME = CFOP_ERROR_USER_NAME

# Test-local entity ID pattern constants.
# These are intentionally kept in tests to avoid retaining production constants
# that only support legacy/commented entity_id patterns.
SENSOR_KC_EID_MIDFIX_CHORE_STATUS_SENSOR = "_chore_status_"
SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER = "_ui_dashboard_helper"
SENSOR_KC_EID_PREFIX_DASHBOARD_LANG = "ui_dashboard_lang_"


def construct_entity_id(platform: str, assignee_name: str, suffix: str) -> str:
    """Construct entity ID for a assignee's entity.

    Args:
        platform: Entity platform ("sensor", "button", etc.)
        assignee_name: Assignee's display name
        suffix: Entity suffix constant

    Returns:
        Full entity ID string like "sensor.sarah_choreops_points"

    Example:
        construct_entity_id("sensor", "Sarah", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER)
        # Returns: "sensor.sarah_choreops_ui_dashboard_helper"
    """
    from homeassistant.util import slugify

    assignee_slug = slugify(assignee_name)
    return f"{platform}.{assignee_slug}_choreops{suffix}"


# =============================================================================
# CONVENIENCE LISTS
# =============================================================================

CHORE_STATE_VALUES: list[str] = [
    CHORE_STATE_PENDING,
    CHORE_STATE_CLAIMED,
    CHORE_STATE_APPROVED,
    CHORE_STATE_APPROVED_IN_PART,
    CHORE_STATE_CLAIMED_IN_PART,
    CHORE_STATE_OVERDUE,
    # Phase 2: CHORE_STATE_COMPLETED_BY_OTHER removed from FSM
    # Tests may use string literal "completed_by_other" for display state verification
]

REWARD_STATE_VALUES: list[str] = [
    REWARD_STATE_LOCKED,
    REWARD_STATE_AVAILABLE,
    REWARD_STATE_REQUESTED,
    REWARD_STATE_APPROVED,
]

COMPLETION_CRITERIA_VALUES: list[str] = [
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,
    COMPLETION_CRITERIA_ROTATION_SIMPLE,
    COMPLETION_CRITERIA_ROTATION_SMART,
]
