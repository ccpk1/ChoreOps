# File: const.py
"""Constants for the ChoreOps integration.

This file centralizes configuration keys, defaults, labels, domain names,
event names, and platform identifiers for consistency across the integration.
It also supports localization by defining all labels and UI texts used in sensors,
services, and options flow.
"""

from enum import StrEnum
import logging
from typing import Final
from zoneinfo import ZoneInfo

from homeassistant.const import Platform
import homeassistant.util.dt as dt_util

from .migration_pre_v50_constants import *  # noqa: F403
from .utils import dt_utils


def set_default_timezone(hass):
    """Set the default timezone based on the Home Assistant configuration."""
    global DEFAULT_TIME_ZONE  # noqa: PLW0603
    DEFAULT_TIME_ZONE = dt_util.get_time_zone(hass.config.time_zone)
    # Also configure the pure Python dt_utils module
    if DEFAULT_TIME_ZONE:
        dt_utils.set_default_timezone(DEFAULT_TIME_ZONE)


# ================================================================================================
# General / Integration Information
# ================================================================================================

CHOREOPS_TITLE: Final = "ChoreOps"
DOMAIN: Final = "choreops"
LOGGER: Final = logging.getLogger(__package__)

# Device metadata labels
DEVICE_MANUFACTURER: Final = CHOREOPS_TITLE
DEVICE_MODEL_USER_PROFILE: Final = "User Profile"
DEVICE_MODEL_SYSTEM_CONTROLS: Final = "System Controls"

# Debug Mode (for development - enables invariant assertions)
DEBUG_PIPELINE_GUARDS: Final = False  # Set True to enable guard rail assertions

# Supported platforms
PLATFORMS: Final = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.DATETIME,
    Platform.SELECT,
    Platform.SENSOR,
]

# Coordinator
COORDINATOR: Final = "coordinator"
COORDINATOR_SUFFIX: Final = "_coordinator"

# Storage
STORE: Final = "store"
STORAGE_DIRECTORY: Final = "choreops"
STORAGE_KEY: Final = "choreops_data"
STORAGE_VERSION: Final = 1
ENTRY_DATA_PENDING_STORAGE_KEY: Final = "pending_storage_key"

# Runtime flag keys (stored in hass.data, not persisted)
RUNTIME_KEY_STARTUP_BACKUP_CREATED: Final = "_startup_backup_created_"
RUNTIME_KEY_ENTITY_CLEANUP_DONE: Final = "_entity_cleanup_done_"
RUNTIME_KEY_SERVICE_REGISTRATION_COUNT: Final = "_service_registration_count_"

# Documentation URLs (injected via description_placeholders to satisfy hassfest)
DOC_URL_QUICK_START: Final = (
    "https://github.com/ccpk1/choreops/wiki/Getting-Started:-Quick-Start"
)
DOC_URL_BACKUP_RESTORE: Final = (
    "https://github.com/ccpk1/choreops/wiki/Getting-Started:-Backup-Restore"
)
DOC_URL_GENERAL_OPTIONS: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-General-Options"
)
DOC_URL_DASHBOARD_GENERATION: Final = (
    "https://github.com/ccpk1/choreops/wiki/Getting-Started:-Dashboard-Generation"
)
DOC_URL_CARD_MUSHROOM: Final = "https://github.com/piitaya/lovelace-mushroom"
DOC_URL_CARD_AUTO_ENTITIES: Final = (
    "https://github.com/thomasloven/lovelace-auto-entities"
)
DOC_URL_CARD_MINI_GRAPH: Final = "https://github.com/kalkih/mini-graph-card"
DOC_URL_CARD_BUTTON: Final = "https://github.com/custom-cards/button-card"
DOC_URL_BADGES_OVERVIEW: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Badges-Overview"
)
DOC_URL_BADGES_CUMULATIVE: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Badges-Cumulative"
)
DOC_URL_BADGES_PERIODIC: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Badges-Periodic"
)
DOC_URL_ACHIEVEMENTS_OVERVIEW: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Achievements"
)
DOC_URL_CHALLENGES_OVERVIEW: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Challenges"
)
DOC_URL_BONUSES_PENALTIES: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Points"
)
DOC_URL_CHORES: Final = "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Chores"
DOC_URL_CHORES_ADVANCED: Final = (
    "https://github.com/ccpk1/choreops/wiki/Advanced%3A-Chores"
)
DOC_URL_USERS: Final = "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Users"
DOC_URL_POINTS: Final = "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Points"
DOC_URL_REWARDS: Final = (
    "https://github.com/ccpk1/choreops/wiki/Configuration%3A-Rewards"
)
DOC_URL_MAIN_WIKI: Final = "https://github.com/ccpk1/choreops/wiki"

# Description Placeholder Keys (for hassfest compliance)
PLACEHOLDER_DOCUMENTATION_URL: Final = "documentation_url"
PLACEHOLDER_DASHBOARD_CARD_MUSHROOM_URL: Final = "dashboard_card_mushroom_url"
PLACEHOLDER_DASHBOARD_CARD_AUTO_ENTITIES_URL: Final = "dashboard_card_auto_entities_url"
PLACEHOLDER_DASHBOARD_CARD_MINI_GRAPH_URL: Final = "dashboard_card_mini_graph_url"
PLACEHOLDER_DASHBOARD_CARD_BUTTON_URL: Final = "dashboard_card_button_url"

# ==============================================================================
# Dashboard Template Configuration (v0.5.0-beta3, Schema 43)
# ==============================================================================
# Templates use style-based naming (not version-suffixed).
# Schema version is bumped ONLY for breaking Python context changes.
# Phase 1 release policy adds explicit release-source, compatibility-floor,
# and prerelease defaults for deterministic template resolution.

# Schema version for template context structure (bump when context dict changes)

# URL path prefix for generated dashboards (e.g., cod-alice, cod-admin)
DASHBOARD_URL_PATH_PREFIX: Final = "cod-"
# Legacy URL prefix retained during compatibility window
DASHBOARD_LEGACY_URL_PATH_PREFIX: Final = "kcd-"

# Available dashboard styles
DASHBOARD_STYLE_FULL: Final = "full"
DASHBOARD_STYLE_MINIMAL: Final = "minimal"
DASHBOARD_STYLE_COMPACT: Final = "compact"
DASHBOARD_STYLE_ADMIN: Final = "admin"
DASHBOARD_STYLES: Final = [
    DASHBOARD_STYLE_FULL,
    DASHBOARD_STYLE_MINIMAL,
    DASHBOARD_STYLE_COMPACT,
    DASHBOARD_STYLE_ADMIN,
]

# Release-aware remote template URL pattern (resolved by tag/ref)
DASHBOARD_RELEASE_TEMPLATE_URL_PATTERN: Final = "https://raw.githubusercontent.com/{owner}/{repo}/{ref}/templates/dashboard_{style}.yaml"

# Release source for remote dashboard template catalogs (Phase 1 policy)
DASHBOARD_RELEASE_REPO_OWNER: Final = "ccpk1"
DASHBOARD_RELEASE_REPO_NAME: Final = "choreops-ha-dashboard"
DASHBOARD_RELEASES_API_URL: Final = (
    "https://api.github.com/repos/{owner}/{repo}/releases"
)

# Supported release-tag grammar (parser contract)
# Accepted examples:
#   - COD_v0.5.0_beta3
#   - COD_v0.5.0-beta3
#   - KCD_v0.5.0_beta3
#   - KCD_v0.5.0-beta3
#   - v0.5.0-beta3
#   - v0.5.4
#   - 0.5.4
DASHBOARD_RELEASE_TAG_PATTERN: Final = (
    r"^(?:(?:KCD_|COD_)?v)?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:(?:_|-)?(?P<pre_label>beta|b)(?P<pre_num>\d+))?$"
)

# Default prerelease policy while integration is in beta cycle
DASHBOARD_RELEASE_INCLUDE_PRERELEASES_DEFAULT: Final = True

# Minimum remote dashboard release we consider compatible by default.
# Older releases are excluded from user selection in the release picker.
DASHBOARD_RELEASE_MIN_COMPAT_TAG: Final = "KCD_v0.5.0_beta1"

# MVP compatibility map fallback (used until release metadata manifest is available)
# Structure: dashboard release tag -> minimum ChoreOps integration version required.
DASHBOARD_RELEASE_MIN_INTEGRATION_BY_TAG: Final[dict[str, str]] = {
    "KCD_v0.5.4": "0.5.0"
}

# ==============================================================================
# Event Infrastructure (Phase 0: Layered Architecture Foundation)
# ==============================================================================
# Event Signal Suffixes (Manager-to-Manager Communication)
# ==============================================================================
# Used with helpers.entity_helpers.get_event_signal(entry_id, suffix) to create instance-scoped signals
# Pattern: get_event_signal(entry_id, "points_changed") → "choreops_{entry_id}_points_changed"
#
# Multi-instance isolation: Each config entry gets its own signal namespace
# - Instance 1 (entry_id=abc123): "choreops_abc123_points_changed"
# - Instance 2 (entry_id=xyz789): "choreops_xyz789_points_changed"
#
# NOTE: This is a comprehensive list based on current coordinator operations.
# Not all signals need to be implemented immediately - add as needed per phase.

# ==============================================================================
# Lifecycle Events (Boot Cascade & System Timers)
# ==============================================================================
# Boot Cascade Order (strict sequence - each signal triggers the next):
#   1. Coordinator loads data from storage
#   2. await system_manager.ensure_data_integrity() [BLOCKING]
#   3. SystemManager emits DATA_READY after migrations/cleanup
#   4. ChoreManager initializes → emits CHORES_READY
#   5. StatisticsManager hydrates → emits STATS_READY
#   6. GamificationManager evaluates → emits GAMIFICATION_READY
#   7. UIManager builds dashboard data (system ready for entity requests)
#
# Timer Events (SystemManager owns ALL async_track_time_change registrations):
#   - MIDNIGHT_ROLLOVER: Daily reset tasks (chore resets, stats rollover)
#   - PERIODIC_UPDATE: 5-minute refresh pulse (overdue checks, reminders)

# Lifecycle Events (SystemManager → Domain Managers)
SIGNAL_SUFFIX_DATA_READY: Final = "data_ready"  # Data migrated, registry clean
SIGNAL_SUFFIX_CHORES_READY: Final = "chores_ready"  # ChoreManager init complete
SIGNAL_SUFFIX_STATS_READY: Final = "stats_ready"  # StatisticsManager hydration complete
SIGNAL_SUFFIX_GAMIFICATION_READY: Final = (
    "gamification_ready"  # GamificationManager complete
)

# Timer-Triggered Events (SystemManager owns timers)
SIGNAL_SUFFIX_PERIODIC_UPDATE: Final = "periodic_update"  # 5-minute refresh pulse
SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER: Final = "midnight_rollover"  # Daily reset broadcast

# Economy Events (EconomyManager)
SIGNAL_SUFFIX_POINTS_CHANGED: Final = "points_changed"
SIGNAL_SUFFIX_TRANSACTION_FAILED: Final = "transaction_failed"
SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED: Final = (
    "points_multiplier_change_requested"
)

# Chore Events (ChoreManager)
SIGNAL_SUFFIX_CHORE_CLAIMED: Final = "chore_claimed"
SIGNAL_SUFFIX_CHORE_APPROVED: Final = "chore_approved"
SIGNAL_SUFFIX_CHORE_COMPLETED: Final = "chore_completed"
SIGNAL_SUFFIX_CHORE_DISAPPROVED: Final = "chore_disapproved"
SIGNAL_SUFFIX_CHORE_UNDONE: Final = "chore_undone"
SIGNAL_SUFFIX_CHORE_CLAIM_UNDONE: Final = "chore_claim_undone"
SIGNAL_SUFFIX_CHORE_OVERDUE: Final = "chore_overdue"
SIGNAL_SUFFIX_CHORE_MISSED: Final = "chore_missed"  # Phase 5: Missed tracking
SIGNAL_SUFFIX_CHORE_DUE_REMINDER: Final = "chore_due_reminder"
SIGNAL_SUFFIX_CHORE_DUE_WINDOW: Final = "chore_due_window"
SIGNAL_SUFFIX_CHORE_STATUS_RESET: Final = "chore_status_reset"
SIGNAL_SUFFIX_CHORE_RESCHEDULED: Final = "chore_rescheduled"
SIGNAL_SUFFIX_CHORE_ROTATION_ADVANCED: Final = "chore_rotation_advanced"  # v0.5.0

# Reward Events (RewardManager)
SIGNAL_SUFFIX_REWARD_CLAIMED: Final = "reward_claimed"
SIGNAL_SUFFIX_REWARD_APPROVED: Final = "reward_approved"
SIGNAL_SUFFIX_REWARD_DISAPPROVED: Final = "reward_disapproved"
SIGNAL_SUFFIX_REWARD_CLAIM_UNDONE: Final = "reward_claim_undone"
SIGNAL_SUFFIX_REWARD_STATUS_RESET: Final = "reward_status_reset"

# Penalty Events (PenaltyManager or EconomyManager)
SIGNAL_SUFFIX_PENALTY_APPLIED: Final = "penalty_applied"

# Bonus Events (BonusManager or EconomyManager)
SIGNAL_SUFFIX_BONUS_APPLIED: Final = "bonus_applied"

# Gamification Events (GamificationManager) - Badge
SIGNAL_SUFFIX_BADGE_EARNED: Final = "badge_earned"
SIGNAL_SUFFIX_BADGE_REVOKED: Final = "badge_revoked"

# Gamification Events (GamificationManager) - Achievement
SIGNAL_SUFFIX_ACHIEVEMENT_EARNED: Final = "achievement_earned"

# Gamification Events (GamificationManager) - Challenge
SIGNAL_SUFFIX_CHALLENGE_COMPLETED: Final = "challenge_completed"

# Gamification Events (GamificationManager) - Engine Coordination

# System/Entity Lifecycle Events - User
SIGNAL_SUFFIX_USER_CREATED: Final = "user_created"
SIGNAL_SUFFIX_USER_UPDATED: Final = "user_updated"
SIGNAL_SUFFIX_USER_DELETED: Final = "user_deleted"

# System/Entity Lifecycle Events - Chore
SIGNAL_SUFFIX_CHORE_CREATED: Final = "chore_created"
SIGNAL_SUFFIX_CHORE_UPDATED: Final = "chore_updated"
SIGNAL_SUFFIX_CHORE_DELETED: Final = "chore_deleted"

# System/Entity Lifecycle Events - Badge
SIGNAL_SUFFIX_BADGE_CREATED: Final = "badge_created"
SIGNAL_SUFFIX_BADGE_UPDATED: Final = "badge_updated"
SIGNAL_SUFFIX_BADGE_DELETED: Final = "badge_deleted"

# System/Entity Lifecycle Events - Reward
SIGNAL_SUFFIX_REWARD_CREATED: Final = "reward_created"
SIGNAL_SUFFIX_REWARD_UPDATED: Final = "reward_updated"
SIGNAL_SUFFIX_REWARD_DELETED: Final = "reward_deleted"

# System/Entity Lifecycle Events - Achievement
SIGNAL_SUFFIX_ACHIEVEMENT_CREATED: Final = "achievement_created"
SIGNAL_SUFFIX_ACHIEVEMENT_UPDATED: Final = "achievement_updated"
SIGNAL_SUFFIX_ACHIEVEMENT_DELETED: Final = "achievement_deleted"

# System/Entity Lifecycle Events - Challenge
SIGNAL_SUFFIX_CHALLENGE_CREATED: Final = "challenge_created"
SIGNAL_SUFFIX_CHALLENGE_UPDATED: Final = "challenge_updated"
SIGNAL_SUFFIX_CHALLENGE_DELETED: Final = "challenge_deleted"

# System/Entity Lifecycle Events - Penalty
SIGNAL_SUFFIX_PENALTY_CREATED: Final = "penalty_created"
SIGNAL_SUFFIX_PENALTY_UPDATED: Final = "penalty_updated"
SIGNAL_SUFFIX_PENALTY_DELETED: Final = "penalty_deleted"

# System/Entity Lifecycle Events - Bonus
SIGNAL_SUFFIX_BONUS_CREATED: Final = "bonus_created"
SIGNAL_SUFFIX_BONUS_UPDATED: Final = "bonus_updated"
SIGNAL_SUFFIX_BONUS_DELETED: Final = "bonus_deleted"

# Data Reset Completion Signals (emitted AFTER data reset work is done)
# Payload: scope: str, assignee_id: str | None, item_id: str | None
SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE: Final = "chore_data_reset_complete"
SIGNAL_SUFFIX_POINTS_DATA_RESET_COMPLETE: Final = "points_data_reset_complete"
SIGNAL_SUFFIX_BADGE_DATA_RESET_COMPLETE: Final = "badge_data_reset_complete"
SIGNAL_SUFFIX_ACHIEVEMENT_DATA_RESET_COMPLETE: Final = "achievement_data_reset_complete"
SIGNAL_SUFFIX_CHALLENGE_DATA_RESET_COMPLETE: Final = "challenge_data_reset_complete"
SIGNAL_SUFFIX_REWARD_DATA_RESET_COMPLETE: Final = "reward_data_reset_complete"
SIGNAL_SUFFIX_PENALTY_DATA_RESET_COMPLETE: Final = "penalty_data_reset_complete"
SIGNAL_SUFFIX_BONUS_DATA_RESET_COMPLETE: Final = "bonus_data_reset_complete"

# Default timezone (set once hass is available)
# pylint: disable=invalid-name
DEFAULT_TIME_ZONE: ZoneInfo | None = None

# Schema version for config→storage migration
DATA_SCHEMA_VERSION: Final = "schema_version"
SCHEMA_VERSION_TRANSITIONAL: Final = (
    42  # Set by migrate_config_to_storage(); signals "data in storage, structural
    # migration not yet run." Upgraded to SCHEMA_VERSION_STORAGE_ONLY by
    # _finalize_migration_meta() after all pre-v50 phases succeed.
)
SCHEMA_VERSION_STORAGE_ONLY: Final = (
    43  # v50: Storage-only mode aligns with v0.5.0-beta3 (schema 43)
    # Frozen: All pre-v50 migrations are hardcoded to produce this version.
)
SCHEMA_VERSION_BETA4: Final = (
    44  # v0.5.0-beta4: Post-migration tweaks, only runs after schema 43 confirmed.
)
SCHEMA_VERSION_BETA5: Final = (
    45  # v0.5.0-beta5: Unified users capability-model contract checkpoint.
)

# Float precision for stored numeric values (points, chore stats, etc.)
# Prevents Python float arithmetic drift (e.g., 27.499999999999996 → 27.5)
DATA_FLOAT_PRECISION: Final = 2

# Storage metadata section (for future v43+)
DATA_META: Final = "meta"
DATA_META_SCHEMA_VERSION: Final = "schema_version"
DATA_META_LAST_MIGRATION_DATE: Final = "last_migration_date"
DATA_META_MIGRATIONS_APPLIED: Final = "migrations_applied"
DATA_META_PENDING_EVALUATIONS: Final = "pending_evaluations"
DATA_META_LAST_MIDNIGHT_PROCESSED: Final = "last_midnight_processed"

# Storage Data Keys (Phase 2b)
# Top-level keys in .storage/choreops_data (not entity-specific DATA_ASSIGNEE_*, DATA_CHORE_*, etc.)
DATA_CONFIG_ENTRY_SETTINGS: Final = "config_entry_settings"  # Backup/restore key

# Item Type Identifiers (Phase 1 hard-fork user-first contract)
# Used in generic item lookup functions to identify item class.
ITEM_TYPE_USER: Final = "user"
ITEM_TYPE_CHORE: Final = "chore"
ITEM_TYPE_REWARD: Final = "reward"
ITEM_TYPE_PENALTY: Final = "penalty"
ITEM_TYPE_BADGE: Final = "badge"
ITEM_TYPE_BONUS: Final = "bonus"
ITEM_TYPE_ACHIEVEMENT: Final = "achievement"
ITEM_TYPE_CHALLENGE: Final = "challenge"

# User role qualifiers for user item lookups
ROLE_ASSIGNEE: Final = "assignee"
ROLE_APPROVER: Final = "approver"

# Storage Structure Keys (Phase 3 - config_flow remediation)
# Common keys used in storage file structure validation and diagnostics
DATA_KEY_VERSION: Final = "version"  # Schema version key
DATA_KEY_DATA: Final = "data"  # Main data container key
DATA_KEY_KEY: Final = "key"  # Storage manager key parameter
DATA_KEY_HOME_ASSISTANT: Final = "home_assistant"  # Diagnostic format detection

# Storage Path Segment (Phase 3)
STORAGE_PATH_SEGMENT: Final = ".storage"  # Storage directory name

# Format Strings (Phase 2b)
# Date/time format patterns used across the integration

# Update interval (seconds)
DEFAULT_UPDATE_INTERVAL: Final = 5


# ================================================================================================
# Core Constants (used by other constants)
# ================================================================================================

# Time Units
TIME_UNIT_DAY: Final = "day"
TIME_UNIT_DAYS: Final = "days"
TIME_UNIT_HOUR: Final = "hour"
TIME_UNIT_HOURS: Final = "hours"
TIME_UNIT_MINUTE: Final = "minute"
TIME_UNIT_MINUTES: Final = "minutes"
TIME_UNIT_MONTH: Final = "month"
TIME_UNIT_MONTHS: Final = "months"
TIME_UNIT_QUARTER: Final = "quarter"
TIME_UNIT_QUARTERS: Final = "quarters"
TIME_UNIT_WEEK: Final = "week"
TIME_UNIT_WEEKS: Final = "weeks"
TIME_UNIT_YEAR: Final = "year"
TIME_UNIT_YEARS: Final = "years"

# Frequencies
FREQUENCY_BIWEEKLY: Final = "biweekly"
FREQUENCY_CUSTOM: Final = "custom"
FREQUENCY_CUSTOM_1_MONTH: Final = "custom_1_month"
FREQUENCY_CUSTOM_1_QUARTER: Final = "custom_1_quarter"
FREQUENCY_CUSTOM_1_WEEK: Final = "custom_1_week"
FREQUENCY_CUSTOM_1_YEAR: Final = "custom_1_year"
FREQUENCY_CUSTOM_FROM_COMPLETE: Final = "custom_from_complete"  # CFE-2026-001 F1
FREQUENCY_DAILY: Final = "daily"
FREQUENCY_DAILY_MULTI: Final = "daily_multi"  # CFE-2026-001 F2
FREQUENCY_MONTHLY: Final = "monthly"
FREQUENCY_NONE: Final = "none"
FREQUENCY_QUARTERLY: Final = "quarterly"
FREQUENCY_WEEKLY: Final = "weekly"
FREQUENCY_YEARLY: Final = "yearly"

# Periods
PERIOD_ALL_TIME: Final = "all_time"
PERIOD_DAILY: Final = "daily"
PERIOD_WEEKLY: Final = "weekly"
PERIOD_MONTHLY: Final = "monthly"
PERIOD_YEARLY: Final = "yearly"

# Period end markers
PERIOD_DAY_END: Final = "day_end"
PERIOD_MONTH_END: Final = "month_end"
PERIOD_QUARTER_END: Final = "quarter_end"
PERIOD_WEEK_END: Final = "week_end"
PERIOD_YEAR_END: Final = "year_end"

# Period Format Strings (single source of truth for StatisticsEngine)
PERIOD_FORMAT_DAILY: Final = "%Y-%m-%d"
PERIOD_FORMAT_WEEKLY: Final = "%Y-W%V"
PERIOD_FORMAT_MONTHLY: Final = "%Y-%m"
PERIOD_FORMAT_YEARLY: Final = "%Y"

# Sentinel Values
SENTINEL_EMPTY: Final = ""
SENTINEL_NONE: Final = None
SENTINEL_NONE_TEXT: Final = "None"
SENTINEL_NO_SELECTION: Final = (
    "__none__"  # Non-empty sentinel for SelectSelector "None" option
)

# Display Values
DISPLAY_DOT: Final = "."
DISPLAY_UNKNOWN: Final = "Unknown"
DISPLAY_UNNAMED_CHORE: Final = "Unnamed Chore"
DISPLAY_UNNAMED_USER: Final = "An assignee"

# Occasion Types
OCCASION_BIRTHDAY: Final = "birthday"
OCCASION_HOLIDAY: Final = "holiday"


# ================================================================================================
# Configuration Keys (CONF_*)
# ================================================================================================

# Flow Management
# ConfigFlow steps
CONFIG_FLOW_STEP_ACHIEVEMENT_COUNT: Final = "achievement_count"
CONFIG_FLOW_STEP_ACHIEVEMENTS: Final = "achievements"
CONFIG_FLOW_STEP_BADGE_COUNT: Final = "badge_count"
CONFIG_FLOW_STEP_BADGES: Final = "badges"
CONFIG_FLOW_STEP_BONUS_COUNT: Final = "bonus_count"
CONFIG_FLOW_STEP_BONUSES: Final = "bonuses"
CONFIG_FLOW_STEP_CHALLENGE_COUNT: Final = "challenge_count"
CONFIG_FLOW_STEP_CHALLENGES: Final = "challenges"
CONFIG_FLOW_STEP_CHORE_COUNT: Final = "chore_count"
CONFIG_FLOW_STEP_CHORES: Final = "chores"
CONFIG_FLOW_STEP_FINISH: Final = "finish"
CONFIG_FLOW_STEP_DATA_RECOVERY: Final = "data_recovery"
CONFIG_FLOW_STEP_INTRO: Final = "intro"
CONFIG_FLOW_STEP_USER_COUNT: Final = "user_count"
CONFIG_FLOW_STEP_USERS: Final = "users"
CONFIG_FLOW_STEP_PENALTY_COUNT: Final = "penalty_count"
CONFIG_FLOW_STEP_PENALTIES: Final = "penalties"
CONFIG_FLOW_STEP_POINTS: Final = "points_label"
CONFIG_FLOW_STEP_RECONFIGURE: Final = "reconfigure"
CONFIG_FLOW_STEP_REWARD_COUNT: Final = "reward_count"
CONFIG_FLOW_STEP_REWARDS: Final = "rewards"

# Config Flow Abort Reasons (Phase 3b)
CONFIG_FLOW_ABORT_RECONFIGURE_FAILED: Final = "reconfigure_failed"
CONFIG_FLOW_ABORT_RECONFIGURE_SUCCESSFUL: Final = "reconfigure_successful"

# OptionsFlow Management Menus Keys
OPTIONS_FLOW_DIC_ACHIEVEMENT: Final = "achievement"
OPTIONS_FLOW_DIC_BADGE: Final = "badge"
OPTIONS_FLOW_DIC_BONUS: Final = "bonus"
OPTIONS_FLOW_DIC_CHALLENGE: Final = "challenge"
OPTIONS_FLOW_DIC_CHORE: Final = "chore"
OPTIONS_FLOW_DIC_USER: Final = "user"
OPTIONS_FLOW_DIC_PENALTY: Final = "penalty"
OPTIONS_FLOW_DIC_REWARD: Final = "reward"

# OptionsFlow Backup Management Menu
OPTIONS_FLOW_BACKUP_ACTION_SELECT: Final = "select_backup_action"
OPTIONS_FLOW_BACKUP_ACTION_CREATE: Final = "create_backup"
OPTIONS_FLOW_BACKUP_ACTION_DELETE: Final = "delete_backup"
OPTIONS_FLOW_BACKUP_ACTION_RESTORE: Final = "restore_backup"
OPTIONS_FLOW_ACTIONS_ADD: Final = "add"
OPTIONS_FLOW_ACTIONS_BACK: Final = "back"
OPTIONS_FLOW_ACTIONS_DELETE: Final = "delete"
OPTIONS_FLOW_ACTIONS_EDIT: Final = "edit"
OPTIONS_FLOW_ACHIEVEMENTS: Final = "manage_achievement"
OPTIONS_FLOW_BADGES: Final = "manage_badge"
OPTIONS_FLOW_BONUSES: Final = "manage_bonus"
OPTIONS_FLOW_CHALLENGES: Final = "manage_challenge"
OPTIONS_FLOW_CHORES: Final = "manage_chore"
OPTIONS_FLOW_DASHBOARD_GENERATOR: Final = "dashboard_generator"
OPTIONS_FLOW_GENERAL_OPTIONS: Final = "general_options"
OPTIONS_FLOW_USERS: Final = "manage_user"
OPTIONS_FLOW_PENALTIES: Final = "manage_penalty"
OPTIONS_FLOW_POINTS: Final = "manage_points"
OPTIONS_FLOW_REWARDS: Final = "manage_reward"

# OptionsFlow Steps
OPTIONS_FLOW_STEP_INIT: Final = "init"
OPTIONS_FLOW_STEP_MANAGE_ENTITY: Final = "manage_entity"
OPTIONS_FLOW_STEP_MANAGE_GENERAL_OPTIONS: Final = "manage_general_options"
OPTIONS_FLOW_STEP_MANAGE_POINTS: Final = "manage_points"
OPTIONS_FLOW_STEP_RESTORE_BACKUP: Final = "restore_backup"
OPTIONS_FLOW_STEP_SELECT_ENTITY: Final = "select_entity"

# OptionsFlow Backup Management Steps
OPTIONS_FLOW_STEP_BACKUP_ACTIONS: Final = "backup_actions_menu"
OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_DELETE: Final = "select_backup_to_delete"
OPTIONS_FLOW_STEP_SELECT_BACKUP_TO_RESTORE: Final = "select_backup_to_restore"
OPTIONS_FLOW_STEP_CREATE_MANUAL_BACKUP: Final = "create_manual_backup"
OPTIONS_FLOW_STEP_DELETE_BACKUP_CONFIRM: Final = "delete_backup_confirm"
OPTIONS_FLOW_STEP_RESTORE_BACKUP_CONFIRM: Final = "restore_backup_confirm"
OPTIONS_FLOW_STEP_PASTE_JSON_RESTORE: Final = "paste_json_restore"

# OptionsFlow Dashboard Generator Steps
OPTIONS_FLOW_STEP_DASHBOARD_GENERATOR: Final = "dashboard_generator"
OPTIONS_FLOW_STEP_DASHBOARD_CONFIGURE: Final = "dashboard_configure"
OPTIONS_FLOW_STEP_DASHBOARD_DELETE: Final = "dashboard_delete"
OPTIONS_FLOW_STEP_DASHBOARD_DELETE_CONFIRM: Final = "dashboard_delete_confirm"

OPTIONS_FLOW_STEP_ADD_ACHIEVEMENT: Final = "add_achievement"
OPTIONS_FLOW_STEP_ADD_BADGE: Final = "add_badge"
OPTIONS_FLOW_STEP_ADD_BADGE_CUMULATIVE: Final = "add_badge_cumulative"
OPTIONS_FLOW_STEP_ADD_BADGE_DAILY: Final = "add_badge_daily"
OPTIONS_FLOW_STEP_ADD_BADGE_PERIODIC: Final = "add_badge_periodic"
OPTIONS_FLOW_STEP_ADD_BADGE_SPECIAL: Final = "add_badge_special"
OPTIONS_FLOW_STEP_ADD_BADGE_ACHIEVEMENT: Final = "add_badge_achievement"
OPTIONS_FLOW_STEP_ADD_BADGE_CHALLENGE: Final = "add_badge_challenge"
OPTIONS_FLOW_STEP_ADD_BONUS: Final = "add_bonus"
OPTIONS_FLOW_STEP_ADD_CHALLENGE: Final = "add_challenge"
OPTIONS_FLOW_STEP_ADD_CHORE: Final = "add_chore"
OPTIONS_FLOW_STEP_ADD_USER: Final = "add_user"
OPTIONS_FLOW_STEP_ADD_PENALTY: Final = "add_penalty"
OPTIONS_FLOW_STEP_ADD_REWARD: Final = "add_reward"

OPTIONS_FLOW_STEP_EDIT_ACHIEVEMENT: Final = "edit_achievement"
OPTIONS_FLOW_STEP_EDIT_BONUS: Final = "edit_bonus"
OPTIONS_FLOW_STEP_EDIT_CHALLENGE: Final = "edit_challenge"
OPTIONS_FLOW_STEP_EDIT_CHORE: Final = "edit_chore"
OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DATES: Final = "edit_chore_per_user_dates"
OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DETAILS: Final = (
    "edit_chore_per_user_details"  # PKAD-2026-001
)
OPTIONS_FLOW_STEP_EDIT_BADGE_ACHIEVEMENT: Final = "edit_badge_achievement"
OPTIONS_FLOW_STEP_EDIT_BADGE_CHALLENGE: Final = "edit_badge_challenge"
OPTIONS_FLOW_STEP_EDIT_BADGE_CUMULATIVE: Final = "edit_badge_cumulative"
OPTIONS_FLOW_STEP_EDIT_BADGE_DAILY: Final = "edit_badge_daily"
OPTIONS_FLOW_STEP_EDIT_BADGE_PERIODIC: Final = "edit_badge_periodic"
OPTIONS_FLOW_STEP_EDIT_BADGE_SPECIAL: Final = "edit_badge_special"
OPTIONS_FLOW_STEP_EDIT_USER: Final = "edit_user"
OPTIONS_FLOW_STEP_EDIT_PENALTY: Final = "edit_penalty"
OPTIONS_FLOW_STEP_EDIT_REWARD: Final = "edit_reward"

OPTIONS_FLOW_STEP_DELETE_ACHIEVEMENT: Final = "delete_achievement"
OPTIONS_FLOW_STEP_DELETE_BADGE: Final = "delete_badge"
OPTIONS_FLOW_STEP_DELETE_BONUS: Final = "delete_bonus"
OPTIONS_FLOW_STEP_DELETE_CHALLENGE: Final = "delete_challenge"
OPTIONS_FLOW_STEP_DELETE_CHORE: Final = "delete_chore"
OPTIONS_FLOW_STEP_DELETE_USER: Final = "delete_user"
OPTIONS_FLOW_STEP_DELETE_PENALTY: Final = "delete_penalty"
OPTIONS_FLOW_STEP_DELETE_REWARD: Final = "delete_reward"

# CFE-2026-001: Daily Multi Times Helper Step
OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI: Final = "chores_daily_multi"

# ConfigFlow & OptionsFlow User Input Fields

# GLOBAL
CFOF_GLOBAL_INPUT_INTERNAL_ID: Final = "internal_id"
CFOF_USERS_INPUT_NAME: Final = "name"
CFOF_USERS_INPUT_HA_USER_ID: Final = "ha_user_id"
CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE: Final = "mobile_notify_service"

# DATA RECOVERY
CFOF_DATA_RECOVERY_INPUT_SELECTION: Final = "backup_selection"
CFOF_DATA_RECOVERY_INPUT_JSON_DATA: Final = "json_data"

# USER COUNT
CFOF_USERS_INPUT_COUNT: Final = "user_count"

# USERS (capability fields)
CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: Final = "associated_user_ids"
CFOF_USERS_INPUT_CAN_BE_ASSIGNED: Final = "can_be_assigned"
CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW: Final = "enable_chore_workflow"
CFOF_USERS_INPUT_ENABLE_GAMIFICATION: Final = "enable_gamification"
CFOF_USERS_INPUT_DASHBOARD_LANGUAGE: Final = "dashboard_language"
CFOF_USERS_INPUT_CAN_APPROVE: Final = "can_approve"
CFOF_USERS_INPUT_CAN_MANAGE: Final = "can_manage"

# CHORES
CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: Final = "approval_reset_type"
CFOF_CHORES_INPUT_APPLICABLE_DAYS: Final = "applicable_days"
CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
CFOF_CHORES_INPUT_CHORE_COUNT: Final = "chore_count"
CFOF_CHORES_INPUT_CUSTOM_INTERVAL: Final = "custom_interval"
CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT: Final = "custom_interval_unit"
CFOF_CHORES_INPUT_DEFAULT_POINTS: Final = "default_points"
CFOF_CHORES_INPUT_CLEAR_DUE_DATE: Final = "clear_due_date"
CFOF_CHORES_INPUT_DESCRIPTION: Final = "chore_description"
CFOF_CHORES_INPUT_DUE_DATE: Final = "due_date"
CFOF_CHORES_INPUT_ICON: Final = "icon"
CFOF_CHORES_INPUT_COMPLETION_CRITERIA: Final = "completion_criteria"
CFOF_CHORES_INPUT_LABELS: Final = "chore_labels"
# Phase 6: Aligned with DATA_CHORE_NAME = "name"
CFOF_CHORES_INPUT_NAME: Final = "name"
CFOF_CHORES_INPUT_NOTIFY_ON_APPROVAL: Final = "notify_on_approval"
CFOF_CHORES_INPUT_NOTIFY_ON_CLAIM: Final = "notify_on_claim"
CFOF_CHORES_INPUT_NOTIFY_ON_DISAPPROVAL: Final = "notify_on_disapproval"
CFOF_CHORES_INPUT_NOTIFY_ON_OVERDUE: Final = "notify_on_overdue"
CFOF_CHORES_INPUT_NOTIFY_ON_DUE_WINDOW: Final = "notify_on_due_window"
CFOF_CHORES_INPUT_NOTIFY_DUE_REMINDER: Final = "notify_due_reminder"
CFOF_CHORES_INPUT_DUE_WINDOW_OFFSET: Final = "chore_due_window_offset"
CFOF_CHORES_INPUT_DUE_REMINDER_OFFSET: Final = "chore_due_reminder_offset"
CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW: Final = "chore_claim_lock_until_window"
CFOF_CHORES_INPUT_RECURRING_FREQUENCY: Final = "recurring_frequency"
CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: Final = "daily_multi_times"  # CFE-2026-001 F2
CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: Final = "overdue_handling_type"
CFOF_CHORES_INPUT_APPROVAL_RESET_PENDING_CLAIM_ACTION: Final = (
    "approval_reset_pending_claim_action"
)
CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL: Final = "apply_template_to_all"
CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL: Final = "apply_days_to_all"  # PKAD-2026-001
CFOF_CHORES_INPUT_APPLY_TIMES_TO_ALL: Final = "apply_times_to_all"  # PKAD-2026-001
CFOF_CHORES_INPUT_AUTO_APPROVE: Final = "auto_approve"
CFOF_CHORES_INPUT_SHOW_ON_CALENDAR: Final = "show_on_calendar"
CFOF_CHORES_INPUT_NOTIFICATIONS: Final = "chore_notifications"
# rotation_order removed - unused field, assigned_user_ids defines order

# BADGES
CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
# Legacy compatibility key (migration-only)
CFOF_BADGES_INPUT_ASSIGNED_TO_LEGACY: Final = "assigned_to"
CFOF_BADGES_INPUT_ASSOCIATED_ACHIEVEMENT: Final = "associated_achievement"
CFOF_BADGES_INPUT_ASSOCIATED_CHALLENGE: Final = "associated_challenge"
CFOF_BADGES_INPUT_AWARD_ITEMS: Final = "award_items"
CFOF_BADGES_INPUT_AWARD_POINTS: Final = "award_points"
CFOF_BADGES_INPUT_BADGE_COUNT: Final = "badge_count"
CFOF_BADGES_INPUT_DESCRIPTION: Final = "badge_description"
CFOF_BADGES_INPUT_END_DATE: Final = "end_date"
CFOF_BADGES_INPUT_ICON: Final = "icon"
CFOF_BADGES_INPUT_LABELS: Final = "badge_labels"
CFOF_BADGES_INPUT_MAINTENANCE_RULES: Final = "maintenance_rules"
CFOF_BADGES_INPUT_NAME: Final = "badge_name"
CFOF_BADGES_INPUT_OCCASION_TYPE: Final = "occasion_type"
CFOF_BADGES_INPUT_POINTS_MULTIPLIER: Final = "points_multiplier"
CFOF_BADGES_INPUT_RESET_SCHEDULE: Final = "reset_schedule"
CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL: Final = "custom_interval"
CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: Final = "custom_interval_unit"
CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE: Final = "end_date"
CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS: Final = "grace_period_days"
CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY: Final = "recurring_frequency"
CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE: Final = "start_date"
CFOF_BADGES_INPUT_SELECTED_CHORES: Final = "selected_chores"
CFOF_BADGES_INPUT_START_DATE: Final = "start_date"
CFOF_BADGES_INPUT_TARGET_TYPE: Final = "target_type"
CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: Final = "threshold_value"
CFOF_BADGES_INPUT_TYPE: Final = "badge_type"

# REWARDS
# Note: Values aligned with DATA_REWARD_* constants (Phase 6 CFOF Key Alignment)
CFOF_REWARDS_INPUT_COST: Final = "cost"  # Aligned with DATA_REWARD_COST
CFOF_REWARDS_INPUT_DESCRIPTION: Final = (
    "description"  # Aligned with DATA_REWARD_DESCRIPTION
)
CFOF_REWARDS_INPUT_ICON: Final = "icon"
CFOF_REWARDS_INPUT_LABELS: Final = "reward_labels"
CFOF_REWARDS_INPUT_NAME: Final = "name"  # Aligned with DATA_REWARD_NAME
CFOF_REWARDS_INPUT_REWARD_COUNT: Final = "reward_count"

# BONUSES
CFOF_BONUSES_INPUT_BONUS_COUNT: Final = "bonus_count"
CFOF_BONUSES_INPUT_DESCRIPTION: Final = "bonus_description"
CFOF_BONUSES_INPUT_ICON: Final = "icon"
CFOF_BONUSES_INPUT_LABELS: Final = "bonus_labels"
CFOF_BONUSES_INPUT_NAME: Final = "name"  # Phase 6: Aligned with DATA_BONUS_NAME
CFOF_BONUSES_INPUT_POINTS: Final = "bonus_points"

# PENALTIES
CFOF_PENALTIES_INPUT_DESCRIPTION: Final = "penalty_description"
CFOF_PENALTIES_INPUT_ICON: Final = "icon"
CFOF_PENALTIES_INPUT_LABELS: Final = "penalty_labels"
CFOF_PENALTIES_INPUT_NAME: Final = "name"  # Phase 6: Aligned with DATA_PENALTY_NAME
CFOF_PENALTIES_INPUT_PENALTY_COUNT: Final = "penalty_count"
CFOF_PENALTIES_INPUT_POINTS: Final = "penalty_points"

# ACHIEVEMENTS
CFOF_ACHIEVEMENTS_INPUT_ACHIEVEMENT_COUNT: Final = "achievement_count"
CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
CFOF_ACHIEVEMENTS_INPUT_CRITERIA: Final = "criteria"
CFOF_ACHIEVEMENTS_INPUT_DESCRIPTION: Final = "description"
CFOF_ACHIEVEMENTS_INPUT_ICON: Final = "icon"
CFOF_ACHIEVEMENTS_INPUT_LABELS: Final = "achievement_labels"
CFOF_ACHIEVEMENTS_INPUT_NAME: Final = "name"
CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS: Final = "reward_points"
CFOF_ACHIEVEMENTS_INPUT_SELECTED_CHORE_ID: Final = "selected_chore_id"
CFOF_ACHIEVEMENTS_INPUT_TARGET_VALUE: Final = "target_value"
CFOF_ACHIEVEMENTS_INPUT_TYPE: Final = "type"

# CHALLENGES
CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
CFOF_CHALLENGES_INPUT_CHALLENGE_COUNT: Final = "challenge_count"
CFOF_CHALLENGES_INPUT_CRITERIA: Final = "criteria"
CFOF_CHALLENGES_INPUT_DESCRIPTION: Final = "description"
CFOF_CHALLENGES_INPUT_END_DATE: Final = "end_date"
CFOF_CHALLENGES_INPUT_ICON: Final = "icon"
CFOF_CHALLENGES_INPUT_LABELS: Final = "challenge_labels"
CFOF_CHALLENGES_INPUT_NAME: Final = "name"
CFOF_CHALLENGES_INPUT_REWARD_POINTS: Final = "reward_points"
CFOF_CHALLENGES_INPUT_SELECTED_CHORE_ID: Final = "selected_chore_id"
CFOF_CHALLENGES_INPUT_START_DATE: Final = "start_date"
CFOF_CHALLENGES_INPUT_TARGET_VALUE: Final = "target_value"
CFOF_CHALLENGES_INPUT_TYPE: Final = "type"

# OptionsFlow Input Fields
OPTIONS_FLOW_INPUT_ENTITY_NAME: Final = "entity_name"
OPTIONS_FLOW_INPUT_INTERNAL_ID: Final = "internal_id"
OPTIONS_FLOW_INPUT_MENU_SELECTION: Final = "menu_selection"
OPTIONS_FLOW_INPUT_MANAGE_ACTION: Final = "manage_action"

# OptionsFlow Backup Management Input Fields
CFOF_BACKUP_ACTION_SELECTION: Final = "backup_action_selection"
CFOF_BACKUP_SELECTION: Final = "backup_selection"

# OptionsFlow Data Fields
OPTIONS_FLOW_DATA_ENTITY_NAME: Final = "name"

# OptionsFlow Placeholders
OPTIONS_FLOW_PLACEHOLDER_ACTION: Final = "action"
OPTIONS_FLOW_PLACEHOLDER_ACHIEVEMENT_NAME: Final = "achievement_name"
OPTIONS_FLOW_PLACEHOLDER_BADGE_NAME: Final = "badge_name"
OPTIONS_FLOW_PLACEHOLDER_BONUS_NAME: Final = "bonus_name"
OPTIONS_FLOW_PLACEHOLDER_CHALLENGE_NAME: Final = "challenge_name"
OPTIONS_FLOW_PLACEHOLDER_CHORE_NAME: Final = "chore_name"
OPTIONS_FLOW_PLACEHOLDER_ENTITY_TYPE: Final = "entity_type"
OPTIONS_FLOW_PLACEHOLDER_TARGET_USER_NAME: Final = "user_name"
OPTIONS_FLOW_PLACEHOLDER_USER_NAME: Final = "user_name"
OPTIONS_FLOW_PLACEHOLDER_PENALTY_NAME: Final = "penalty_name"
OPTIONS_FLOW_PLACEHOLDER_REWARD_NAME: Final = "reward_name"
OPTIONS_FLOW_PLACEHOLDER_SUMMARY: Final = "summary"


# OptionsFlow Helpers
OPTIONS_FLOW_ASYNC_STEP_ADD_PREFIX: Final = "async_step_add_"
OPTIONS_FLOW_MENU_MANAGE_PREFIX: Final = "manage_"


# Global Settings
CONF_CALENDAR_SHOW_PERIOD: Final = "calendar_show_period"
CONF_POINTS_ADJUST_VALUES: Final = "points_adjust_values"
CONF_POINTS_ICON: Final = "points_icon"
CONF_POINTS_LABEL: Final = "points_label"
CONF_RETENTION_DAILY: Final = "retention_daily"
CONF_RETENTION_MONTHLY: Final = "retention_monthly"
CONF_RETENTION_WEEKLY: Final = "retention_weekly"
CONF_RETENTION_YEARLY: Final = "retention_yearly"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Backup Management Configuration
CONF_BACKUPS_MAX_RETAINED: Final = "backups_max_retained"
DEFAULT_BACKUPS_MAX_RETAINED: Final = 5  # Keep last N backups per tag (0 = disabled)

# Backup Tags (for backup filename identification)
BACKUP_TAG_RECOVERY: Final = "recovery"  # Data recovery actions
BACKUP_TAG_REMOVAL: Final = "removal"  # Integration removal
BACKUP_TAG_RESET: Final = "reset"  # Factory reset
BACKUP_TAG_DATA_RESET: Final = (
    "data-reset"  # Transactional data reset (unified service)
)
BACKUP_TAG_PRE_MIGRATION: Final = (
    "pre-migration"  # Before schema upgrade (never deleted)
)
BACKUP_TAG_MANUAL: Final = "manual"  # User-initiated (never deleted)

# System Settings (ConfigFlow & OptionsFlow)  Phase 3c: Consolidation
CFOF_SYSTEM_INPUT_POINTS_LABEL: Final = "points_label"
CFOF_SYSTEM_INPUT_POINTS_ICON: Final = "points_icon"
CFOF_SYSTEM_INPUT_UPDATE_INTERVAL: Final = "update_interval"
CFOF_SYSTEM_INPUT_CALENDAR_SHOW_PERIOD: Final = "calendar_show_period"
CFOF_SYSTEM_INPUT_RETENTION_DAILY: Final = "retention_daily"
CFOF_SYSTEM_INPUT_RETENTION_WEEKLY: Final = "retention_weekly"
CFOF_SYSTEM_INPUT_RETENTION_MONTHLY: Final = "retention_monthly"
CFOF_SYSTEM_INPUT_RETENTION_YEARLY: Final = "retention_yearly"
CFOF_SYSTEM_INPUT_POINTS_ADJUST_VALUES: Final = "points_adjust_values"

# Additional system settings form inputs (General Options)
CFOF_SYSTEM_INPUT_RETENTION_PERIODS: Final = "retention_periods"
CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES: Final = "show_legacy_entities"
CFOF_SYSTEM_INPUT_KIOSK_MODE: Final = "kiosk_mode"
CFOF_SYSTEM_INPUT_BACKUPS_MAX_RETAINED: Final = "backups_max_retained"

# Dashboard Generator Input Fields (OptionsFlow)
CFOF_DASHBOARD_INPUT_NAME: Final = "dashboard_name"
CFOF_DASHBOARD_INPUT_ASSIGNEE_SELECTION: Final = "dashboard_assignee_selection"
CFOF_DASHBOARD_INPUT_ACTION: Final = "dashboard_action"
CFOF_DASHBOARD_INPUT_UPDATE_SELECTION: Final = "dashboard_update_selection"
CFOF_DASHBOARD_INPUT_CHECK_CARDS: Final = "dashboard_check_cards"
CFOF_DASHBOARD_INPUT_TEMPLATE_PROFILE: Final = "dashboard_template_profile"
CFOF_DASHBOARD_INPUT_ADMIN_MODE: Final = "dashboard_admin_mode"
CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_GLOBAL: Final = "dashboard_admin_template_global"
CFOF_DASHBOARD_INPUT_ADMIN_TEMPLATE_PER_ASSIGNEE: Final = (
    "dashboard_admin_template_per_assignee"
)
CFOF_DASHBOARD_INPUT_ADMIN_VIEW_VISIBILITY: Final = "dashboard_admin_view_visibility"
CFOF_DASHBOARD_INPUT_SHOW_IN_SIDEBAR: Final = "dashboard_show_in_sidebar"
CFOF_DASHBOARD_INPUT_REQUIRE_ADMIN: Final = "dashboard_require_admin"
CFOF_DASHBOARD_INPUT_ICON: Final = "dashboard_icon"
CFOF_DASHBOARD_INPUT_RELEASE_SELECTION: Final = "dashboard_release_selection"
CFOF_DASHBOARD_INPUT_INCLUDE_PRERELEASES: Final = "dashboard_include_prereleases"
CFOF_DASHBOARD_SECTION_ASSIGNEE_VIEWS: Final = "section_assignee_views"
CFOF_DASHBOARD_SECTION_ADMIN_VIEWS: Final = "section_admin_views"
CFOF_DASHBOARD_SECTION_ACCESS_SIDEBAR: Final = "section_access_sidebar"
CFOF_DASHBOARD_SECTION_TEMPLATE_VERSION: Final = "section_template_version"

# Dashboard Generator Defaults
DASHBOARD_DEFAULT_NAME: Final = "Chores"

# Dashboard Generator Actions
DASHBOARD_ACTION_CREATE: Final = "create"
DASHBOARD_ACTION_UPDATE: Final = "update"
DASHBOARD_ACTION_DELETE: Final = "delete"
DASHBOARD_ACTION_EXIT: Final = "exit"

# Dashboard admin-mode options (Phase 3)
DASHBOARD_ADMIN_MODE_NONE: Final = "none"
DASHBOARD_ADMIN_MODE_GLOBAL: Final = "global"
DASHBOARD_ADMIN_MODE_PER_ASSIGNEE: Final = "per_assignee"
DASHBOARD_ADMIN_MODE_BOTH: Final = "both"
DASHBOARD_ADMIN_VIEW_VISIBILITY_ALL: Final = "all_users"
DASHBOARD_ADMIN_VIEW_VISIBILITY_LINKED_APPROVERS: Final = "linked_approvers"

# Dashboard release-mode options (Phase 3)
DASHBOARD_RELEASE_MODE_LATEST_COMPATIBLE: Final = "latest_compatible"

# Chore Custom Interval Reset Periods
CUSTOM_INTERVAL_UNIT_OPTIONS: Final = [
    SENTINEL_EMPTY,
    TIME_UNIT_HOURS,  # CFE-2026-001 F3
    TIME_UNIT_DAYS,
    TIME_UNIT_WEEKS,
    TIME_UNIT_MONTHS,
]

# Entity-Specific Configuration
# (No legacy constants - all moved to _LEGACY section at end of file)

# Notifications
NOTIFICATION_EVENT: Final = "mobile_app_notification_action"

# Legacy / Extra Entity Settings
CONF_SHOW_LEGACY_ENTITIES: Final = "show_legacy_entities"
CONF_KIOSK_MODE: Final = "kiosk_mode"

# Badge Types
BADGE_TYPE_ACHIEVEMENT_LINKED: Final = "achievement_linked"
BADGE_TYPE_CHALLENGE_LINKED: Final = "challenge_linked"
BADGE_TYPE_CUMULATIVE: Final = "cumulative"
BADGE_TYPE_DAILY: Final = "daily"
BADGE_TYPE_PERIODIC: Final = "periodic"
BADGE_TYPE_SPECIAL_OCCASION: Final = "special_occasion"

# Achievement Types
ACHIEVEMENT_TYPE_DAILY_MIN: Final = "daily_minimum"
ACHIEVEMENT_TYPE_STREAK: Final = "chore_streak"
ACHIEVEMENT_TYPE_TOTAL: Final = "chore_total"

# Challenge Types
CHALLENGE_TYPE_DAILY_MIN: Final = "daily_minimum"
CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW: Final = "total_within_window"

# Canonical target type names (shared mapper/evaluator contract)
CANONICAL_TARGET_TYPE_BADGE_AWARD_COUNT: Final = "badge_award_count"
CANONICAL_TARGET_TYPE_COMPLETION_STREAK: Final = "completion_streak"
CANONICAL_TARGET_TYPE_DAILY_MINIMUM: Final = "daily_minimum"
CANONICAL_TARGET_TYPE_TOTAL_WITH_BASELINE: Final = "total_with_baseline"
CANONICAL_TARGET_TYPE_TOTAL_WITHIN_WINDOW: Final = "total_within_window"

# Source-to-canonical mapping contracts
ACHIEVEMENT_TO_CANONICAL_TARGET_MAP: Final = {
    ACHIEVEMENT_TYPE_DAILY_MIN: CANONICAL_TARGET_TYPE_DAILY_MINIMUM,
    ACHIEVEMENT_TYPE_STREAK: CANONICAL_TARGET_TYPE_COMPLETION_STREAK,
    ACHIEVEMENT_TYPE_TOTAL: CANONICAL_TARGET_TYPE_TOTAL_WITH_BASELINE,
}

CHALLENGE_TO_CANONICAL_TARGET_MAP: Final = {
    CHALLENGE_TYPE_DAILY_MIN: CANONICAL_TARGET_TYPE_DAILY_MINIMUM,
    CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW: CANONICAL_TARGET_TYPE_TOTAL_WITHIN_WINDOW,
}


# ------------------------------------------------------------------------------------------------
# Data Keys
# ------------------------------------------------------------------------------------------------
# Pluralization: Use SINGULAR for single-field data (DATA_USER_NAME = "name"), PLURAL for
# collections (DATA_USERS = "users"). See
# ARCHITECTURE.md "Entity Plurality" (lines 926-941) for details.

# GLOBAL
DATA_ACHIEVEMENTS: Final = "achievements"
DATA_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
DATA_BADGES: Final = "badges"
DATA_BONUSES: Final = "bonuses"
DATA_CHALLENGES: Final = "challenges"
DATA_CHORES: Final = "chores"
DATA_GLOBAL_STATE_SUFFIX: Final = "_global_state"
DATA_INTERNAL_ID: Final = "internal_id"
DATA_LAST_CHANGE: Final = "last_change"
DATA_NAME: Final = "name"
DATA_APPROVERS: Final = "approvers"
DATA_USERS: Final = "users"
DATA_PENALTIES: Final = "penalties"
DATA_PROGRESS: Final = "progress"
DATA_REWARDS: Final = "rewards"

# NOTIFICATIONS (v0.5.0+ Platinum Pattern - Owned by NotificationManager)
# Separate bucket for notification history to maintain domain ownership.
# ChoreManager owns chore_data, NotificationManager owns notifications.
# Structure: notifications[assignee_id][chore_id] = {last_due_start, last_due_reminder, last_overdue}
DATA_NOTIFICATIONS: Final = "notifications"
DATA_NOTIF_LAST_DUE_START: Final = "last_due_start"
DATA_NOTIF_LAST_DUE_REMINDER: Final = "last_due_reminder"
DATA_NOTIF_LAST_OVERDUE: Final = "last_overdue"

# ASSIGNEE / USER (legacy-key backed during hard-fork transition)
DATA_USER_BADGES_EARNED_NAME: Final = "badge_name"
DATA_USER_BADGES_EARNED_LAST_AWARDED: Final = "last_awarded_date"
DATA_USER_BADGES_EARNED_AWARD_COUNT: Final = "award_count"
DATA_USER_BADGES_EARNED: Final = "badges_earned"
DATA_USER_BADGES_EARNED_PERIODS: Final = "periods"
DATA_USER_BADGES_EARNED_PERIODS_ALL_TIME: Final = "all_time"


# Badge Progress Data Structure
DATA_USER_BADGE_PROGRESS: Final = "badge_progress"

# Common Badge Progress Fields
DATA_USER_BADGE_PROGRESS_CHORES_COMPLETED: Final = "chores_completed"
DATA_USER_BADGE_PROGRESS_CHORES_CYCLE_COUNT: Final = "chores_cycle_count"
DATA_USER_BADGE_PROGRESS_CRITERIA_MET: Final = "criteria_met"
DATA_USER_BADGE_PROGRESS_CYCLE_COUNT: Final = "cycle_count"
DATA_USER_BADGE_PROGRESS_DAYS_COMPLETED: Final = "days_completed"
DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT: Final = "days_cycle_count"
DATA_USER_BADGE_PROGRESS_END_DATE: Final = "end_date"
DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY: Final = "last_update_day"
DATA_USER_BADGE_PROGRESS_NAME: Final = "name"
DATA_USER_BADGE_PROGRESS_OVERALL_PROGRESS: Final = "overall_progress"
DATA_USER_BADGE_PROGRESS_PENALTY_APPLIED: Final = "penalty_applied"
DATA_USER_BADGE_PROGRESS_POINTS_CYCLE_COUNT: Final = "points_cycle_count"
DATA_USER_BADGE_PROGRESS_RECURRING_FREQUENCY: Final = "recurring_frequency"
DATA_USER_BADGE_PROGRESS_START_DATE: Final = "start_date"
DATA_USER_BADGE_PROGRESS_STATUS: Final = "status"
DATA_USER_BADGE_PROGRESS_TARGET_THRESHOLD_VALUE: Final = "threshold_value"
DATA_USER_BADGE_PROGRESS_TARGET_TYPE: Final = "target_type"
DATA_USER_BADGE_PROGRESS_TRACKED_CHORES: Final = "tracked_chores"
DATA_USER_BADGE_PROGRESS_TYPE: Final = "badge_type"

# Note: Shared fields already defined above in Common Badge Progress Fields section

DATA_USER_BONUS_APPLIES: Final = "bonus_applies"
# Legacy completed-by-other assignee list removed in v0.5.0+ (Phase 2)
# SHARED_FIRST blocking now computed dynamically, not tracked in assignee lists

# Assignee Chore Data Structure Constants
DATA_USER_CHORE_DATA: Final = "chore_data"
DATA_USER_CHORE_DATA_STATE: Final = "state"
DATA_USER_CHORE_DATA_PENDING_CLAIM_COUNT: Final = "pending_claim_count"
DATA_USER_CHORE_DATA_NAME: Final = "name"
# due_date moved to LEGACY section - use per_assignee_due_dates at chore level instead
DATA_USER_CHORE_DATA_LAST_APPROVED: Final = "last_approved"
DATA_USER_CHORE_DATA_LAST_CLAIMED: Final = "last_claimed"
DATA_USER_CHORE_DATA_LAST_COMPLETED: Final = "last_completed"
DATA_USER_CHORE_DATA_LAST_DISAPPROVED: Final = "last_disapproved"
DATA_USER_CHORE_DATA_LAST_OVERDUE: Final = "last_overdue"
DATA_USER_CHORE_DATA_LAST_MISSED: Final = "last_missed"  # Phase 5: Last miss timestamp
DATA_USER_CHORE_DATA_LAST_LONGEST_STREAK_ALL_TIME: Final = (
    "last_longest_streak_all_time"
)
DATA_USER_CHORE_DATA_APPROVAL_PERIOD_START: Final = (
    "approval_period_start"  # INDEPENDENT: per-assignee period start
)
DATA_USER_CHORE_DATA_TOTAL_COUNT: Final = "total_count"
DATA_USER_CHORE_DATA_TOTAL_POINTS: Final = "total_points"
DATA_USER_CHORE_DATA_PERIODS: Final = "periods"
DATA_USER_CHORE_DATA_PERIODS_ALL_TIME: Final = "all_time"
DATA_USER_CHORE_DATA_PERIODS_DAILY: Final = "daily"
DATA_USER_CHORE_DATA_PERIODS_WEEKLY: Final = "weekly"
DATA_USER_CHORE_DATA_PERIODS_MONTHLY: Final = "monthly"
DATA_USER_CHORE_DATA_PERIODS_YEARLY: Final = "yearly"
DATA_USER_CHORE_DATA_PERIOD_APPROVED: Final = "approved"
DATA_USER_CHORE_DATA_PERIOD_CLAIMED: Final = "claimed"
DATA_USER_CHORE_DATA_PERIOD_COMPLETED: Final = "completed"
DATA_USER_CHORE_DATA_PERIOD_DISAPPROVED: Final = "disapproved"
DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY: Final = (
    "streak_tally"  # Daily: streak value on that day
)
DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK: Final = (
    "longest_streak"  # All-time: high water mark (HWM)
)
DATA_USER_CHORE_DATA_PERIOD_OVERDUE: Final = "overdue"
DATA_USER_CHORE_DATA_PERIOD_MISSED: Final = "missed"  # Phase 5: Period miss counter
DATA_USER_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY: Final = (
    "missed_streak_tally"  # Phase 5: Daily consecutive misses
)
DATA_USER_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK: Final = (
    "missed_longest_streak"  # Phase 5: All-time missed streak HWM
)
DATA_USER_CHORE_DATA_PERIOD_POINTS: Final = "points"
DATA_USER_CHORE_DATA_BADGE_REFS: Final = "badge_refs"

# Current Streak Values (Chore Data Level - Never Pruned)
# Phase 5: Store current streak values at chore data level to survive retention pruning
DATA_USER_CHORE_DATA_CURRENT_STREAK: Final = "current_streak"  # Completion streak
DATA_USER_CHORE_DATA_CURRENT_MISSED_STREAK: Final = (
    "current_missed_streak"  # Consecutive misses
)

# Chore Periods (Global Bucket) - v44+ (Phase 2)
DATA_USER_CHORE_PERIODS: Final = "chore_periods"
# Chore periods use the same bucket keys as chore_data periods
# (daily, weekly, monthly, yearly, all_time) - see assignee chore data period keys

# NOTE: Legacy chore stats keys and sub-keys have been
# DELETED as of v0.5.0-beta3 (schema v43). The chore_stats storage bucket was
# removed - all stats are now derived from chore_periods.all_time and
# chore_data[uuid].periods buckets. See _LEGACY constants at end of file.

# --- Last Completion Date (lives in chore_data, NOT in deleted chore_stats) ---
# --- Badge Progress Tracking ---
DATA_USER_CUMULATIVE_BADGE_PROGRESS: Final = "cumulative_badge_progress"

# Phase 3A: Only state fields stored - derived fields computed on-read
# Maintenance tracking (state fields)
DATA_USER_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: Final = "cycle_points"
DATA_USER_CUMULATIVE_BADGE_PROGRESS_STATUS: Final = "status"
DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE: Final = "maintenance_end_date"
DATA_USER_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE = (
    "maintenance_grace_end_date"
)

# Cumulative Badge Progress Computed Fields (Phase 3A)
# Dict keys for get_cumulative_badge_progress() return values
CUMULATIVE_BADGE_PROGRESS_STATUS: Final = "status"
CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS: Final = "cycle_points"
CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE: Final = (
    "maintenance_grace_end_date"
)
CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: Final = "highest_earned_badge_id"
CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME: Final = "highest_earned_badge_name"
CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_THRESHOLD: Final = "highest_earned_threshold"
CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: Final = "current_badge_id"
CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: Final = "current_badge_name"
CUMULATIVE_BADGE_PROGRESS_CURRENT_THRESHOLD: Final = "current_threshold"
CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID: Final = "next_higher_badge_id"
CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME: Final = "next_higher_badge_name"
CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_THRESHOLD: Final = "next_higher_threshold"
CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_POINTS_NEEDED: Final = "next_higher_points_needed"
CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID: Final = "next_lower_badge_id"
CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME: Final = "next_lower_badge_name"
CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_THRESHOLD: Final = "next_lower_threshold"

# Canonical user constants (runtime-facing names)
DATA_USER_POINTS: Final = "points"
DATA_USER_POINTS_MULTIPLIER: Final = "points_multiplier"
DATA_USER_LEDGER: Final = "ledger"

DATA_USER_CURRENT_STREAK: Final = "current_streak"
DATA_USER_LAST_STREAK_DATE: Final = "last_date"
# NOTE: Legacy overdue chore list removed - dead code (see legacy section)
DATA_USER_PENALTY_APPLIES: Final = "penalty_applies"

# ——————————————————————————————————————————————
# Ledger Entry Structure Constants (Phase 3 - Economy Stack)
# Used by EconomyEngine for transaction history
# ——————————————————————————————————————————————
DATA_LEDGER_TIMESTAMP: Final = "timestamp"  # ISO datetime string
DATA_LEDGER_AMOUNT: Final = "amount"  # Transaction delta (signed float)
DATA_LEDGER_BALANCE_AFTER: Final = "balance_after"  # Balance after transaction
DATA_LEDGER_SOURCE: Final = "source"  # Transaction source type (uses POINTS_SOURCE_*)
DATA_LEDGER_REFERENCE_ID: Final = "reference_id"  # Related entity ID (optional)

# Default ledger limit is defined by daily data retention, this is a hard
# limit to prevent storage bloat or performance issues.
DEFAULT_LEDGER_MAX_ENTRIES: Final = 1000

# ——————————————————————————————————————————————
# Assignee Reward Data Structure Constants (Modern - v0.5.0+)
# Supports multi-claim: assignee can claim same reward multiple times before approval
# ——————————————————————————————————————————————
DATA_USER_REWARD_DATA: Final = "reward_data"
DATA_USER_REWARD_DATA_NAME: Final = "name"
DATA_USER_REWARD_DATA_PENDING_COUNT: Final = "pending_count"  # Number of pending claims
DATA_USER_REWARD_DATA_LAST_CLAIMED: Final = "last_claimed"
DATA_USER_REWARD_DATA_LAST_APPROVED: Final = "last_approved"
DATA_USER_REWARD_DATA_LAST_DISAPPROVED: Final = "last_disapproved"

# LEGACY v43: Removed - use periods.all_time.* instead
DATA_USER_REWARD_DATA_TOTAL_CLAIMS: Final = (
    "total_claims"  # LEGACY v43: Use periods.all_time.claimed
)
DATA_USER_REWARD_DATA_TOTAL_APPROVED: Final = (
    "total_approved"  # LEGACY v43: Use periods.all_time.approved
)
DATA_USER_REWARD_DATA_TOTAL_DISAPPROVED: Final = (
    "total_disapproved"  # LEGACY v43: Use periods.all_time.disapproved
)
DATA_USER_REWARD_DATA_TOTAL_POINTS_SPENT: Final = (
    "total_points_spent"  # LEGACY v43: Use periods.all_time.points
)
DATA_USER_REWARD_DATA_NOTIFICATION_IDS: Final = "notification_ids"  # LEGACY v43: NotificationManager owns lifecycle (embeds in action buttons)

# Period-based reward tracking (aligned with chore_data and point_data patterns)
DATA_USER_REWARD_DATA_PERIODS: Final = "periods"
DATA_USER_REWARD_DATA_PERIODS_DAILY: Final = "daily"
DATA_USER_REWARD_DATA_PERIODS_WEEKLY: Final = "weekly"
DATA_USER_REWARD_DATA_PERIODS_MONTHLY: Final = "monthly"
DATA_USER_REWARD_DATA_PERIODS_YEARLY: Final = "yearly"
DATA_USER_REWARD_DATA_PERIODS_ALL_TIME: Final = "all_time"
DATA_USER_REWARD_DATA_PERIOD_CLAIMED: Final = "claimed"
DATA_USER_REWARD_DATA_PERIOD_APPROVED: Final = "approved"
DATA_USER_REWARD_DATA_PERIOD_DISAPPROVED: Final = "disapproved"
DATA_USER_REWARD_DATA_PERIOD_POINTS: Final = "points"

# Reward Periods (Global Bucket) - v43+ (Phase 3)
DATA_USER_REWARD_PERIODS: Final = "reward_periods"
# Reward periods use the same bucket keys as reward_data periods
# (daily, weekly, monthly, yearly, all_time) - see assignee reward data period keys

# NOTE: Legacy reward stats keys and sub-keys will be
# DELETED in v0.5.0-beta3 (schema v43). The reward_stats storage bucket will be
# removed - all stats will be derived from reward_periods.all_time and
# reward_data[uuid].periods buckets. See _LEGACY constants at end of file.

# Reward Stats Keys (aggregated stats across all rewards for an assignee)
DATA_USER_REWARD_STATS: Final = "reward_stats"

# --- Claimed Counts (pending approval) ---

DATA_USER_USE_PERSISTENT_NOTIFICATIONS: Final = "use_persistent_notifications"
DATA_USER_DASHBOARD_LANGUAGE: Final = "dashboard_language"

# USERS (schema 45+ capability model)
DATA_USER_ID: Final = "user_id"
DATA_USER_INTERNAL_ID: Final = "internal_id"
DATA_USER_NAME: Final = "name"
DATA_USER_HA_USER_ID: Final = "ha_user_id"
DATA_USER_MOBILE_NOTIFY_SERVICE: Final = "mobile_notify_service"
DATA_USER_ASSOCIATED_USER_IDS: Final = "associated_user_ids"
DATA_USER_CAN_APPROVE: Final = "can_approve"
DATA_USER_CAN_MANAGE: Final = "can_manage"
DATA_USER_CAN_BE_ASSIGNED: Final = "can_be_assigned"
DATA_USER_ENABLE_CHORE_WORKFLOW: Final = "enable_chore_workflow"
DATA_USER_ENABLE_GAMIFICATION: Final = "enable_gamification"

# User capability defaults
DEFAULT_USER_ENABLE_CHORE_WORKFLOW: Final = False
DEFAULT_USER_ENABLE_GAMIFICATION: Final = False

# Legacy payload compatibility window (Phase 1 contract)

# ——————————————————————————————————————————————
# Custom Translation Settings (Dashboard & Notifications)
# ——————————————————————————————————————————————
CUSTOM_TRANSLATIONS_DIR: Final = "translations_custom"
DEFAULT_DASHBOARD_LANGUAGE: Final = "en"
DEFAULT_REPORT_LANGUAGE: Final = "en"
DASHBOARD_TRANSLATIONS_SUFFIX: Final = "_dashboard"  # File naming: en_dashboard.json
NOTIFICATION_TRANSLATIONS_SUFFIX: Final = (
    "_notifications"  # File naming: en_notifications.json
)
REPORT_TRANSLATIONS_SUFFIX: Final = "_report"  # File naming: en_report.json

# ——————————————————————————————————————————————
# Assignee Point History Data Structure
# ——————————————————————————————————————————————

# Top‑level key for storing period‑by‑period point history (v43+)
DATA_USER_POINT_PERIODS: Final = "point_periods"

# Individual period buckets
DATA_USER_POINT_PERIODS_DAILY: Final = "daily"
DATA_USER_POINT_PERIODS_WEEKLY: Final = "weekly"
DATA_USER_POINT_PERIODS_MONTHLY: Final = "monthly"
DATA_USER_POINT_PERIODS_YEARLY: Final = "yearly"
DATA_USER_POINT_PERIODS_ALL_TIME: Final = "all_time"

# Within each period entry:
#   – points_earned: sum of positive deltas (v44+)
#   – points_spent: sum of negative deltas (v44+)
#   – by_source: breakdown of delta by source type
#   – highest_balance: cumulative peak (all_time bucket only, v44+)
# DEPRECATED (v44): points_total will be deleted after migration
DATA_USER_POINT_PERIOD_POINTS_EARNED: Final = "points_earned"
DATA_USER_POINT_PERIOD_POINTS_SPENT: Final = "points_spent"
DATA_USER_POINT_PERIOD_HIGHEST_BALANCE: Final = "highest_balance"
DATA_USER_POINT_PERIOD_BY_SOURCE: Final = "by_source"

# Point Sources
# --- Point Source Types (all plural) ---
POINTS_SOURCE_CHORES: Final = "chores"
POINTS_SOURCE_BONUSES: Final = "bonuses"
POINTS_SOURCE_PENALTIES: Final = "penalties"
POINTS_SOURCE_BADGES: Final = "badges"
POINTS_SOURCE_ACHIEVEMENTS: Final = "achievements"
POINTS_SOURCE_CHALLENGES: Final = "challenges"
POINTS_SOURCE_REWARDS: Final = "rewards"
POINTS_SOURCE_MANUAL: Final = "manual"
POINTS_SOURCE_OTHER: Final = "other"

# Example list of valid sources for UI/enumeration:
# Lowercase literals required by Home Assistant SelectSelector schema


# --- Averages ---
# NOTE: avg_*_week/month keys are NOT persisted (Phase 7.5). avg_per_chore is persisted.
# LEGACY constants moved to `migration_pre_v50_constants.py`

# =============================================================================
# PRESENTATION CONSTANTS (assignee scoped) - Memory-only cache keys (NOT in storage)
# =============================================================================
# These constants are used ONLY in StatisticsManager._stats_cache.
# They represent ephemeral, derived data that can be regenerated from buckets.
# Directive: Derivative Data is Ephemeral - these MUST NOT be persisted.
# See Phase 7.5: Statistics Presenter & Data Sanitization
# Naming: PRES_USER_* follows DATA_ASSIGNEE_* pattern for assignee-specific values.

# --- Presentation: Point Stats (derived from period buckets) ---
PRES_USER_POINTS_EARNED_TODAY: Final = "pres_user_points_earned_today"
PRES_USER_POINTS_EARNED_WEEK: Final = "pres_user_points_earned_week"
PRES_USER_POINTS_EARNED_MONTH: Final = "pres_user_points_earned_month"
PRES_USER_POINTS_EARNED_YEAR: Final = "pres_user_points_earned_year"

PRES_USER_POINTS_SPENT_TODAY: Final = "pres_user_points_spent_today"
PRES_USER_POINTS_SPENT_WEEK: Final = "pres_user_points_spent_week"
PRES_USER_POINTS_SPENT_MONTH: Final = "pres_user_points_spent_month"
PRES_USER_POINTS_SPENT_YEAR: Final = "pres_user_points_spent_year"

PRES_USER_POINTS_NET_TODAY: Final = "pres_user_points_net_today"
PRES_USER_POINTS_NET_WEEK: Final = "pres_user_points_net_week"
PRES_USER_POINTS_NET_MONTH: Final = "pres_user_points_net_month"
PRES_USER_POINTS_NET_YEAR: Final = "pres_user_points_net_year"

PRES_USER_POINTS_BY_SOURCE_TODAY: Final = "pres_user_points_by_source_today"
PRES_USER_POINTS_BY_SOURCE_WEEK: Final = "pres_user_points_by_source_week"
PRES_USER_POINTS_BY_SOURCE_MONTH: Final = "pres_user_points_by_source_month"
PRES_USER_POINTS_BY_SOURCE_YEAR: Final = "pres_user_points_by_source_year"

PRES_USER_POINTS_AVG_PER_DAY_WEEK: Final = "pres_user_avg_points_per_day_week"
PRES_USER_POINTS_AVG_PER_DAY_MONTH: Final = "pres_user_avg_points_per_day_month"

# --- Presentation: Chore Stats (derived from period buckets) ---
PRES_USER_CHORES_APPROVED_TODAY: Final = "pres_user_chores_approved_today"
PRES_USER_CHORES_APPROVED_WEEK: Final = "pres_user_chores_approved_week"
PRES_USER_CHORES_APPROVED_MONTH: Final = "pres_user_chores_approved_month"
PRES_USER_CHORES_APPROVED_YEAR: Final = "pres_user_chores_approved_year"

# --- Presentation: Completed Stats (work date tracking - approver-lag-proof) ---
# These track when work was DONE (claim date), not when approved.
PRES_USER_CHORES_COMPLETED_TODAY: Final = "pres_user_chores_completed_today"
PRES_USER_CHORES_COMPLETED_WEEK: Final = "pres_user_chores_completed_week"
PRES_USER_CHORES_COMPLETED_MONTH: Final = "pres_user_chores_completed_month"
PRES_USER_CHORES_COMPLETED_YEAR: Final = "pres_user_chores_completed_year"

PRES_USER_CHORES_CLAIMED_TODAY: Final = "pres_user_chores_claimed_today"
PRES_USER_CHORES_CLAIMED_WEEK: Final = "pres_user_chores_claimed_week"
PRES_USER_CHORES_CLAIMED_MONTH: Final = "pres_user_chores_claimed_month"
PRES_USER_CHORES_CLAIMED_YEAR: Final = "pres_user_chores_claimed_year"

PRES_USER_CHORES_MISSED_TODAY: Final = "pres_user_chores_missed_today"
PRES_USER_CHORES_MISSED_WEEK: Final = "pres_user_chores_missed_week"
PRES_USER_CHORES_MISSED_MONTH: Final = "pres_user_chores_missed_month"
PRES_USER_CHORES_MISSED_YEAR: Final = "pres_user_chores_missed_year"

PRES_USER_CHORES_POINTS_TODAY: Final = "pres_user_chores_points_today"
PRES_USER_CHORES_POINTS_WEEK: Final = "pres_user_chores_points_week"
PRES_USER_CHORES_POINTS_MONTH: Final = "pres_user_chores_points_month"
PRES_USER_CHORES_POINTS_YEAR: Final = "pres_user_chores_points_year"

PRES_USER_CHORES_AVG_PER_DAY_WEEK: Final = "pres_user_chores_avg_per_day_week"
PRES_USER_CHORES_AVG_PER_DAY_MONTH: Final = "pres_user_chores_avg_per_day_month"
PRES_USER_CHORES_AVG_PER_DAY_YEAR: Final = "pres_user_chores_avg_per_day_year"

PRES_USER_TOP_CHORES_WEEK: Final = "pres_user_top_chores_week"
PRES_USER_TOP_CHORES_MONTH: Final = "pres_user_top_chores_month"
PRES_USER_TOP_CHORES_YEAR: Final = "pres_user_top_chores_year"

# --- Presentation: Snapshot Counts (current state, not historical) ---
# These are volatile counts of chores in specific states RIGHT NOW.
# Derived from current chore states, NOT from period buckets.
PRES_USER_CHORES_CURRENT_OVERDUE: Final = "pres_user_chores_current_overdue"
PRES_USER_CHORES_CURRENT_CLAIMED: Final = "pres_user_chores_current_claimed"
PRES_USER_CHORES_CURRENT_APPROVED: Final = "pres_user_chores_current_approved"
PRES_USER_CHORES_CURRENT_DUE_TODAY: Final = "pres_user_chores_current_due_today"

# --- Presentation: Reward Stats (derived from period buckets) ---
PRES_USER_REWARDS_CLAIMED_TODAY: Final = "pres_user_rewards_claimed_today"
PRES_USER_REWARDS_CLAIMED_WEEK: Final = "pres_user_rewards_claimed_week"
PRES_USER_REWARDS_CLAIMED_MONTH: Final = "pres_user_rewards_claimed_month"

PRES_USER_REWARDS_APPROVED_TODAY: Final = "pres_user_rewards_approved_today"
PRES_USER_REWARDS_APPROVED_WEEK: Final = "pres_user_rewards_approved_week"
PRES_USER_REWARDS_APPROVED_MONTH: Final = "pres_user_rewards_approved_month"

# --- Presentation: Cache Metadata ---
PRES_USER_LAST_UPDATED: Final = "pres_user_last_updated"


# CHORES
DATA_CHORE_APPROVAL_RESET_TYPE: Final = "approval_reset_type"
DATA_CHORE_APPROVAL_PERIOD_START: Final = (
    "approval_period_start"  # When current approval period started
)
DATA_CHORE_APPLICABLE_DAYS: Final = "applicable_days"
DATA_CHORE_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
DATA_CHORE_CUSTOM_INTERVAL: Final = "custom_interval"
DATA_CHORE_CUSTOM_INTERVAL_UNIT: Final = "custom_interval_unit"
DATA_CHORE_DEFAULT_POINTS: Final = "default_points"
DATA_CHORE_DESCRIPTION: Final = "description"
DATA_CHORE_DUE_DATE: Final = "due_date"
DATA_CHORE_ICON: Final = "icon"
DATA_CHORE_ID: Final = "chore_id"
DATA_CHORE_INTERNAL_ID: Final = "internal_id"
DATA_CHORE_LABELS: Final = "chore_labels"
DATA_CHORE_LAST_CLAIMED: Final = "last_claimed"
DATA_CHORE_LAST_COMPLETED: Final = "last_completed"
DATA_CHORE_CLAIMED_BY: Final = "claimed_by"  # Current period: who claimed (str for INDEPENDENT/SHARED_FIRST, list[str] for SHARED_ALL)
DATA_CHORE_COMPLETED_BY: Final = "completed_by"  # Current period: who completed (str for INDEPENDENT/SHARED_FIRST, list[str] for SHARED_ALL)
DATA_CHORE_NAME: Final = "name"
DATA_CHORE_NOTIFY_ON_APPROVAL: Final = "notify_on_approval"
DATA_CHORE_NOTIFY_ON_CLAIM: Final = "notify_on_claim"
DATA_CHORE_NOTIFY_ON_DISAPPROVAL: Final = "notify_on_disapproval"
DATA_CHORE_NOTIFY_ON_OVERDUE: Final = "notify_on_overdue"
DATA_CHORE_NOTIFY_ON_DUE_WINDOW: Final = "notify_on_due_window"
DATA_CHORE_NOTIFY_DUE_REMINDER: Final = "notify_due_reminder"
DATA_CHORE_DUE_WINDOW_OFFSET: Final = "chore_due_window_offset"
DATA_CHORE_DUE_REMINDER_OFFSET: Final = "chore_due_reminder_offset"
CHORE_CLAIM_LOCK_UNTIL_WINDOW: Final = "chore_claim_lock_until_window"
DATA_CHORE_CLAIM_LOCK_UNTIL_WINDOW: Final = CHORE_CLAIM_LOCK_UNTIL_WINDOW
DATA_CHORE_AUTO_APPROVE: Final = "auto_approve"
DATA_CHORE_RECURRING_FREQUENCY: Final = "recurring_frequency"
DATA_CHORE_DAILY_MULTI_TIMES: Final = "daily_multi_times"  # CFE-2026-001 F2
DATA_CHORE_SHOW_ON_CALENDAR: Final = "show_on_calendar"
# Completion criteria
DATA_CHORE_COMPLETION_CRITERIA: Final = "completion_criteria"

# Rotation tracking (v0.5.0 Chore Logic)
DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID: Final = (
    "rotation_current_assignee_id"  # UUID of current turn holder
)
DATA_CHORE_ROTATION_CYCLE_OVERRIDE: Final = "rotation_cycle_override"  # Boolean: temp allow any assignee to claim (cleared on advancement)

DATA_CHORE_PER_ASSIGNEE_DUE_DATES: Final = "per_assignee_due_dates"
DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS: Final = (
    "per_assignee_applicable_days"  # PKAD-2026-001
)
DATA_CHORE_PER_ASSIGNEE_DAILY_MULTI_TIMES: Final = (
    "per_assignee_daily_multi_times"  # PKAD-2026-001
)
DATA_CHORE_OVERDUE_HANDLING_TYPE: Final = "overdue_handling_type"
DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: Final = (
    "approval_reset_pending_claim_action"
)

# Completion Criteria Values
COMPLETION_CRITERIA_SHARED: Final = "shared_all"
COMPLETION_CRITERIA_INDEPENDENT: Final = "independent"
COMPLETION_CRITERIA_SHARED_FIRST: Final = "shared_first"
# Rotation modes (v0.5.0 Chore Logic - Design v2: 2 types only)
COMPLETION_CRITERIA_ROTATION_SIMPLE: Final = "rotation_simple"
COMPLETION_CRITERIA_ROTATION_SMART: Final = "rotation_smart"
COMPLETION_CRITERIA_OPTIONS: Final = [
    {"value": COMPLETION_CRITERIA_INDEPENDENT, "label": "independent"},
    {"value": COMPLETION_CRITERIA_SHARED, "label": "shared_all"},
    {"value": COMPLETION_CRITERIA_SHARED_FIRST, "label": "shared_first"},
    {"value": COMPLETION_CRITERIA_ROTATION_SIMPLE, "label": "rotation_simple"},
    {"value": COMPLETION_CRITERIA_ROTATION_SMART, "label": "rotation_smart"},
]

# Approval Reset Type Values (Phase 4)
# Controls when a chore can be claimed/approved again after completion
APPROVAL_RESET_AT_MIDNIGHT_ONCE: Final = "at_midnight_once"
APPROVAL_RESET_AT_MIDNIGHT_MULTI: Final = "at_midnight_multi"
APPROVAL_RESET_AT_DUE_DATE_ONCE: Final = "at_due_date_once"
APPROVAL_RESET_AT_DUE_DATE_MULTI: Final = "at_due_date_multi"
APPROVAL_RESET_UPON_COMPLETION: Final = "upon_completion"
APPROVAL_RESET_MANUAL: Final = "manual"
APPROVAL_RESET_TYPE_OPTIONS: Final = [
    {"value": APPROVAL_RESET_AT_MIDNIGHT_ONCE, "label": "at_midnight_once"},
    {"value": APPROVAL_RESET_AT_MIDNIGHT_MULTI, "label": "at_midnight_multi"},
    {"value": APPROVAL_RESET_AT_DUE_DATE_ONCE, "label": "at_due_date_once"},
    {"value": APPROVAL_RESET_AT_DUE_DATE_MULTI, "label": "at_due_date_multi"},
    {"value": APPROVAL_RESET_UPON_COMPLETION, "label": "upon_completion"},
    {"value": APPROVAL_RESET_MANUAL, "label": "manual"},
]
DEFAULT_APPROVAL_RESET_TYPE: Final = APPROVAL_RESET_AT_MIDNIGHT_ONCE

# Overdue Handling Type Values (Phase 5)
# Controls when/if a chore shows as overdue
OVERDUE_HANDLING_AT_DUE_DATE: Final = "at_due_date"
OVERDUE_HANDLING_NEVER_OVERDUE: Final = "never_overdue"
OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Final = (
    "at_due_date_clear_at_approval_reset"
)
OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE: Final = (
    "at_due_date_clear_immediate_on_late"
)
OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED: Final = (
    "at_due_date_clear_and_mark_missed"  # Phase 5: Reset + record miss stats
)
OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK: Final = (
    "at_due_date_mark_missed_and_lock"  # v0.5.0: Lock chore on miss
)
OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL: Final = (
    "at_due_date_allow_steal"  # v0.5.0: Rotation steal window (7th type, D-06 revised)
)
OVERDUE_HANDLING_TYPE_OPTIONS: Final = [
    {"value": OVERDUE_HANDLING_NEVER_OVERDUE, "label": "never_overdue"},
    {"value": OVERDUE_HANDLING_AT_DUE_DATE, "label": "at_due_date"},
    {
        "value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
        "label": "at_due_date_clear_immediate_on_late",
    },
    {
        "value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
        "label": "at_due_date_clear_at_approval_reset",
    },
    {
        "value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED,
        "label": "at_due_date_clear_and_mark_missed",
    },
    {
        "value": OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK,
        "label": "at_due_date_mark_missed_and_lock",
    },
    {
        "value": OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL,
        "label": "at_due_date_allow_steal",
    },
]
DEFAULT_OVERDUE_HANDLING_TYPE: Final = (
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
)

# Approval Reset Pending Claim Action Values (Phase 5)
# Controls what happens to pending (unapproved) claims at approval reset
APPROVAL_RESET_PENDING_CLAIM_HOLD: Final = "hold_pending"
APPROVAL_RESET_PENDING_CLAIM_CLEAR: Final = "clear_pending"
APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE: Final = "auto_approve_pending"
APPROVAL_RESET_PENDING_CLAIM_ACTION_OPTIONS: Final = [
    {
        "value": APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
        "label": "auto_approve_pending",
    },
    {"value": APPROVAL_RESET_PENDING_CLAIM_CLEAR, "label": "clear_pending"},
    {"value": APPROVAL_RESET_PENDING_CLAIM_HOLD, "label": "hold_pending"},
]
DEFAULT_APPROVAL_RESET_PENDING_CLAIM_ACTION: Final = (
    APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE
)

# Chore approval origin values (event payload metadata)
CHORE_APPROVAL_ORIGIN_MANUAL: Final = "manual"
CHORE_APPROVAL_ORIGIN_AUTO_APPROVE: Final = "auto_approve"
CHORE_APPROVAL_ORIGIN_AUTO_RESET: Final = "auto_reset"

DATA_CHORE_STATE: Final = "state"
DATA_CHORE_TIMESTAMP: Final = "timestamp"

# BADGES
DATA_BADGE_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
# Legacy compatibility key (migration-only)
DATA_BADGE_ASSIGNED_TO_LEGACY: Final = "assigned_to"
DATA_BADGE_ASSOCIATED_ACHIEVEMENT: Final = "associated_achievement"
DATA_BADGE_ASSOCIATED_CHALLENGE: Final = "associated_challenge"
DATA_BADGE_AWARDS: Final = "awards"
DATA_BADGE_AWARDS_AWARD_ITEMS: Final = "award_items"
DATA_BADGE_AWARDS_AWARD_POINTS: Final = "award_points"
DATA_BADGE_AWARDS_AWARD_REWARD: Final = "award_reward"
DATA_BADGE_AWARDS_POINT_MULTIPLIER: Final = "points_multiplier"
DATA_BADGE_DESCRIPTION: Final = "description"
DATA_BADGE_EARNED_BY: Final = "earned_by"
DATA_BADGE_ICON: Final = "icon"
DATA_BADGE_ID: Final = "badge_id"
DATA_BADGE_INTERNAL_ID: Final = "internal_id"
DATA_BADGE_LABELS: Final = "badge_labels"
DATA_BADGE_MAINTENANCE_RULES: Final = "maintenance_rules"
DATA_BADGE_NAME: Final = "name"
DATA_BADGE_OCCASION_TYPE: Final = "occasion_type"
DATA_BADGE_RESET_SCHEDULE: Final = "reset_schedule"
DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: Final = "custom_interval"
DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: Final = "custom_interval_unit"
DATA_BADGE_RESET_SCHEDULE_END_DATE: Final = "end_date"
DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: Final = "grace_period_days"
DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: Final = "recurring_frequency"
DATA_BADGE_RESET_SCHEDULE_START_DATE: Final = "start_date"
DATA_BADGE_SPECIAL_OCCASION_TYPE: Final = "occasion_type"
DATA_BADGE_TARGET: Final = "target"
DATA_BADGE_TARGET_THRESHOLD_VALUE: Final = "threshold_value"
DATA_BADGE_TARGET_TYPE: Final = "target_type"
DATA_BADGE_TRACKED_CHORES: Final = "tracked_chores"
DATA_BADGE_TRACKED_CHORES_SELECTED_CHORES: Final = "selected_chores"
DATA_BADGE_TYPE: Final = "badge_type"

# REWARDS
DATA_REWARD_COST: Final = "cost"
DATA_REWARD_DESCRIPTION: Final = "description"
DATA_REWARD_ICON: Final = "icon"
DATA_REWARD_ID: Final = "reward_id"
DATA_REWARD_INTERNAL_ID: Final = "internal_id"
DATA_REWARD_LABELS: Final = "reward_labels"
DATA_REWARD_NAME: Final = "name"
DATA_REWARD_TIMESTAMP: Final = "timestamp"

# BONUSES
DATA_BONUS_DESCRIPTION: Final = "description"
DATA_BONUS_ICON: Final = "icon"
DATA_BONUS_ID: Final = "bonus_id"
DATA_BONUS_INTERNAL_ID: Final = "internal_id"
DATA_BONUS_LABELS: Final = "bonus_labels"
DATA_BONUS_NAME: Final = "name"
DATA_BONUS_POINTS: Final = "points"

# Bonus period tracking (item-level only, no aggregate bucket at assignee level)
DATA_USER_BONUS_PERIODS: Final = "periods"
DATA_USER_BONUS_PERIOD_APPLIES: Final = "applies"
DATA_USER_BONUS_PERIOD_POINTS: Final = "points"

# PENALTIES
DATA_PENALTY_DESCRIPTION: Final = "description"
DATA_PENALTY_ICON: Final = "icon"
DATA_PENALTY_ID: Final = "penalty_id"
DATA_PENALTY_INTERNAL_ID: Final = "internal_id"
DATA_PENALTY_LABELS: Final = "penalty_labels"
DATA_PENALTY_NAME: Final = "name"
DATA_PENALTY_POINTS: Final = "points"

# Penalty period tracking (item-level only, no aggregate bucket at assignee level)
DATA_USER_PENALTY_PERIODS: Final = "periods"
DATA_USER_PENALTY_PERIOD_APPLIES: Final = "applies"
DATA_USER_PENALTY_PERIOD_POINTS: Final = "points"

# Transaction ledger item name field (universal across all item types)
# Used in metadata to store human-readable name (chores, rewards, badges, bonuses, penalties)
DATA_LEDGER_ITEM_NAME: Final = "item_name"

# ACHIEVEMENTS
DATA_ACHIEVEMENT_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
DATA_ACHIEVEMENT_AWARDED: Final = "awarded"
DATA_ACHIEVEMENT_BASELINE: Final = "baseline"
DATA_ACHIEVEMENT_CRITERIA: Final = "criteria"
DATA_ACHIEVEMENT_CURRENT_STREAK: Final = "current_streak"
DATA_ACHIEVEMENT_CURRENT_VALUE: Final = "current_value"
DATA_ACHIEVEMENT_DESCRIPTION: Final = "description"
DATA_ACHIEVEMENT_ICON: Final = "icon"
DATA_ACHIEVEMENT_ID: Final = "achievement_id"
DATA_ACHIEVEMENT_INTERNAL_ID: Final = "internal_id"
DATA_ACHIEVEMENT_LABELS: Final = "achievement_labels"
DATA_ACHIEVEMENT_NAME: Final = "name"
DATA_ACHIEVEMENT_PROGRESS: Final = "progress"
DATA_ACHIEVEMENT_PROGRESS_SUFFIX: Final = "_achievement_progress"
DATA_ACHIEVEMENT_REWARD_POINTS: Final = "reward_points"
DATA_ACHIEVEMENT_SELECTED_CHORE_ID: Final = "selected_chore_id"
DATA_ACHIEVEMENT_SOURCE_BADGE_ID: Final = "source_badge_id"
DATA_ACHIEVEMENT_TARGET_VALUE: Final = "target_value"
DATA_ACHIEVEMENT_TYPE: Final = "type"

# CHALLENGES
DATA_CHALLENGE_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
DATA_CHALLENGE_AWARDED: Final = "awarded"
DATA_CHALLENGE_COUNT: Final = "count"
DATA_CHALLENGE_CRITERIA: Final = "criteria"
DATA_CHALLENGE_DAILY_COUNTS: Final = "daily_counts"
DATA_CHALLENGE_DESCRIPTION: Final = "description"
DATA_CHALLENGE_END_DATE: Final = "end_date"
DATA_CHALLENGE_ICON: Final = "icon"
DATA_CHALLENGE_ID: Final = "challenge_id"
DATA_CHALLENGE_INTERNAL_ID: Final = "internal_id"
DATA_CHALLENGE_LABELS: Final = "challenge_labels"
DATA_CHALLENGE_NAME: Final = "name"
DATA_CHALLENGE_PROGRESS: Final = "progress"
DATA_CHALLENGE_PROGRESS_SUFFIX: Final = "_challenge_progress"
DATA_CHALLENGE_REQUIRED_DAILY: Final = "required_daily"
DATA_CHALLENGE_REWARD_POINTS: Final = "reward_points"
DATA_CHALLENGE_SELECTED_CHORE_ID: Final = "selected_chore_id"
DATA_CHALLENGE_START_DATE: Final = "start_date"
DATA_CHALLENGE_TARGET_VALUE: Final = "target_value"
DATA_CHALLENGE_TYPE: Final = "type"

# ================================================================================================
# Default Icons
# ================================================================================================
# System Icon Defaults (user-configurable in system settings)
# ================================================================================================
DEFAULT_POINTS_ICON: Final = "mdi:star-outline"

# ================================================================================================
# Dynamic Button Icons (vary based on runtime conditions)
# ================================================================================================
DEFAULT_POINTS_ADJUST_MINUS_ICON: Final = "mdi:minus-circle-outline"
DEFAULT_POINTS_ADJUST_MINUS_MULTIPLE_ICON: Final = "mdi:minus-circle-multiple-outline"
DEFAULT_POINTS_ADJUST_PLUS_ICON: Final = "mdi:plus-circle-outline"
DEFAULT_POINTS_ADJUST_PLUS_MULTIPLE_ICON: Final = "mdi:plus-circle-multiple-outline"

# All entity icons now defined in icons.json for declarative frontend translation
# ================================================================================================

# ------------------------------------------------------------------------------------------------
# Default Values
# ------------------------------------------------------------------------------------------------
DEFAULT_ACHIEVEMENT_REWARD_POINTS: Final = 0
DEFAULT_ACHIEVEMENT_TARGET: Final = 1
DEFAULT_APPLICABLE_DAYS: list[str] = []
DEFAULT_BADGE_AWARD_POINTS: Final = 0.0
DEFAULT_BADGE_MAINTENANCE_THRESHOLD: Final = 0  # Added
DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_END_DATE: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_START_DATE: str | None = SENTINEL_NONE
DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: Final = 0
DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY = FREQUENCY_NONE
DEFAULT_BADGE_RESET_SCHEDULE = {
    DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: (
        DEFAULT_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY
    ),
    DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: (
        DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL
    ),
    DATA_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: (
        DEFAULT_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT
    ),
    DATA_BADGE_RESET_SCHEDULE_START_DATE: DEFAULT_BADGE_RESET_SCHEDULE_START_DATE,
    DATA_BADGE_RESET_SCHEDULE_END_DATE: DEFAULT_BADGE_RESET_SCHEDULE_END_DATE,
    DATA_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS: (
        DEFAULT_BADGE_RESET_SCHEDULE_GRACE_PERIOD_DAYS
    ),
}
DEFAULT_BADGE_TARGET_TYPE: Final = "points"
DEFAULT_BADGE_TARGET_THRESHOLD_VALUE: Final = 50.0
DEFAULT_BADGE_TARGET = {
    "type": DEFAULT_BADGE_TARGET_TYPE,
    "value": DEFAULT_BADGE_TARGET_THRESHOLD_VALUE,
}
DEFAULT_BONUS_POINTS: Final = 1
DEFAULT_CALENDAR_SHOW_PERIOD: Final = 90
DEFAULT_CHORE_CLAIM_LOCK_UNTIL_WINDOW: Final = False
DEFAULT_CHORE_AUTO_APPROVE: Final = False
DEFAULT_CHORE_SHOW_ON_CALENDAR: Final = True
DEFAULT_CHALLENGE_REWARD_POINTS: Final = 0
DEFAULT_RETENTION_DAILY: Final = 14
DEFAULT_RETENTION_WEEKLY: Final = 5
DEFAULT_RETENTION_MONTHLY: Final = 3
DEFAULT_RETENTION_YEARLY: Final = 3
DEFAULT_CHALLENGE_TARGET: Final = 1
DEFAULT_CHORES_UNIT: Final = "Chores"
DEFAULT_DAILY_RESET_TIME = {"hour": 0, "minute": 0, "second": 0}
DEFAULT_ASSIGNEE_POINTS_MULTIPLIER: Final = 1
DEFAULT_SHOW_LEGACY_ENTITIES: Final = False
DEFAULT_KIOSK_MODE: Final = False
DEFAULT_NOTIFY_ON_APPROVAL = True
DEFAULT_NOTIFY_ON_CLAIM = True
DEFAULT_NOTIFY_ON_DISAPPROVAL = True
DEFAULT_NOTIFY_ON_OVERDUE = True  # Notify when chore becomes overdue
DEFAULT_NOTIFY_ON_DUE_WINDOW = False  # Don't notify on due window start by default
DEFAULT_NOTIFY_DUE_REMINDER = True  # Notify on due reminder by default
DEFAULT_PENALTY_POINTS: Final = 1
DEFAULT_PENDING_CHORES_UNIT: Final = "Pending Chores"
DEFAULT_PENDING_REWARDS_UNIT: Final = "Pending Rewards"
DEFAULT_POINTS: Final = 5
DEFAULT_POINTS_ADJUST_VALUES: list[float] = [+1.0, -1.0, +2.0, -2.0, +10.0, -10.0]
DEFAULT_POINTS_LABEL: Final = "Points"
DEFAULT_POINTS_MULTIPLIER = 1.0
DEFAULT_REWARD_COST: Final = 10
DEFAULT_REMINDER_DELAY: Final = 30
DEFAULT_DUE_WINDOW_OFFSET: Final = "0d 1h 0m"  # Disabled by default
DEFAULT_DUE_REMINDER_OFFSET: Final = "0d 0h 30m"  # 30 minutes before due
DEFAULT_WEEKLY_RESET_DAY: Final = 0
DEFAULT_ZERO: Final = 0

# System Settings Defaults (for backup/restore validation)
DEFAULT_SYSTEM_SETTINGS: Final = {
    CONF_POINTS_LABEL: DEFAULT_POINTS_LABEL,
    CONF_POINTS_ICON: DEFAULT_POINTS_ICON,
    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
    CONF_CALENDAR_SHOW_PERIOD: DEFAULT_CALENDAR_SHOW_PERIOD,
    CONF_RETENTION_DAILY: DEFAULT_RETENTION_DAILY,
    CONF_RETENTION_WEEKLY: DEFAULT_RETENTION_WEEKLY,
    CONF_RETENTION_MONTHLY: DEFAULT_RETENTION_MONTHLY,
    CONF_RETENTION_YEARLY: DEFAULT_RETENTION_YEARLY,
    CONF_POINTS_ADJUST_VALUES: DEFAULT_POINTS_ADJUST_VALUES,
}


# ------------------------------------------------------------------------------------------------
# Badge Threshold Types
# ------------------------------------------------------------------------------------------------
# Badge Target Types for all supported badge logic

BADGE_TARGET_THRESHOLD_TYPE_POINTS: Final = "points"
BADGE_TARGET_THRESHOLD_TYPE_POINTS_ALL_TIME: Final = "points_all_time"
BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES: Final = "points_chores"
BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT: Final = "chore_count"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES: Final = "days_all_chores"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES = "days_80pct_chores"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES_NO_OVERDUE = (
    "days_all_chores_no_overdue"
)
BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES: Final = "days_all_due_chores"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_DUE_CHORES = "days_80pct_due_chores"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES_NO_OVERDUE = (
    "days_all_due_chores_no_overdue"
)
BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES = "days_min_3_chores"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES = "days_min_5_chores"
BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_7_CHORES = "days_min_7_chores"
BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES: Final = "streak_all_chores"
BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_CHORES = "streak_80pct_chores"
BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE = (
    "streak_all_chores_no_overdue"
)
BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES = "streak_80pct_due_chores"
BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_DUE_CHORES_NO_OVERDUE = (
    "streak_all_due_chores_no_overdue"
)

# Legacy
BADGE_THRESHOLD_TYPE_CHORE_COUNT: Final = "chore_count"


# ------------------------------------------------------------------------------------------------
# States
# ------------------------------------------------------------------------------------------------

# Chore states persisted in backend records
CHORE_STATE_APPROVED = "approved"
CHORE_STATE_APPROVED_IN_PART = "approved_in_part"
CHORE_STATE_CLAIMED = "claimed"
CHORE_STATE_CLAIMED_IN_PART = "claimed_in_part"
CHORE_STATE_INDEPENDENT = "independent"
CHORE_STATE_OVERDUE = "overdue"
CHORE_STATE_PENDING = "pending"
CHORE_STATE_UNKNOWN = "unknown"
CHORE_STATE_MISSED = "missed"

# Chore states used for display context only (not persisted)
CHORE_STATE_COMPLETED_BY_OTHER = "completed_by_other"

# Chore states calculated at runtime (not persisted)
CHORE_STATE_DUE = "due"
CHORE_STATE_WAITING = "waiting"
CHORE_STATE_NOT_MY_TURN = "not_my_turn"

# State source-of-truth contracts (Phase 5)
# - Assignee-level persisted state: workflow checkpoints stored in assignee_chore_data
# - Assignee-level derived state: display/claimability states resolved at runtime
# - Chore-level persisted state: aggregate snapshot stored on chore record
CHORE_PERSISTED_USER_STATES: Final[frozenset[str]] = frozenset(
    {
        CHORE_STATE_PENDING,
        CHORE_STATE_CLAIMED,
        CHORE_STATE_APPROVED,
        CHORE_STATE_OVERDUE,
        CHORE_STATE_MISSED,
    }
)

# Chore status context keys (get_chore_status_context return contract)
CHORE_CTX_STATE: Final = "state"
CHORE_CTX_STORED_STATE: Final = "stored_state"
CHORE_CTX_IS_OVERDUE: Final = "is_overdue"
CHORE_CTX_IS_DUE: Final = "is_due"
CHORE_CTX_HAS_PENDING_CLAIM: Final = "has_pending_claim"
CHORE_CTX_IS_APPROVED_IN_PERIOD: Final = "is_approved_in_period"
CHORE_CTX_IS_COMPLETED_BY_OTHER: Final = "is_completed_by_other"
CHORE_CTX_CAN_CLAIM: Final = "can_claim"
CHORE_CTX_CAN_CLAIM_ERROR: Final = "can_claim_error"
CHORE_CTX_LOCK_REASON: Final = "lock_reason"
CHORE_CTX_CAN_APPROVE: Final = "can_approve"
CHORE_CTX_CAN_APPROVE_ERROR: Final = "can_approve_error"
CHORE_CTX_DUE_DATE: Final = "due_date"
CHORE_CTX_AVAILABLE_AT: Final = "available_at"
CHORE_CTX_LAST_COMPLETED: Final = "last_completed"

# ==============================================================================
# Chore Scanner API (ChoreManager Internal)
# ==============================================================================
# Pattern: CHORE_SCAN_<STRUCTURE>_<FIELD>
# These constants define the internal API for ChoreManager's process_time_checks()
# scanner, which categorizes chores by time-based status in a single pass.
#
# Future item types (badges, rewards) will follow same pattern:
#   BADGE_SCAN_RESULT_*, REWARD_SCAN_ENTRY_*, etc.

# Scanner Trigger Types (process_time_checks trigger parameter values)
CHORE_SCAN_TRIGGER_MIDNIGHT: Final = "midnight"  # AT_MIDNIGHT_* chore processing
CHORE_SCAN_TRIGGER_DUE_DATE: Final = "due_date"  # AT_DUE_DATE_* chore processing

# Reset policy trigger + decision constants (Phase 1 unification)
CHORE_RESET_TRIGGER_APPROVAL: Final = "approval"

CHORE_RESET_BOUNDARY_CATEGORY_HOLD: Final = "hold"
CHORE_RESET_BOUNDARY_CATEGORY_CLEAR_ONLY: Final = "clear_only"
CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE: Final = "reset_and_reschedule"

CHORE_RESET_DECISION_HOLD: Final = "hold"
CHORE_RESET_DECISION_RESET_ONLY: Final = "reset_only"
CHORE_RESET_DECISION_RESET_AND_RESCHEDULE: Final = "reset_and_reschedule"
CHORE_RESET_DECISION_AUTO_APPROVE_PENDING: Final = "auto_approve_pending"

# Scanner Result Category Keys (process_time_checks return dict keys)
CHORE_SCAN_RESULT_OVERDUE: Final = "overdue"  # Chores past due date
CHORE_SCAN_RESULT_IN_DUE_WINDOW: Final = "in_due_window"  # Chores within due window
CHORE_SCAN_RESULT_DUE_REMINDER: Final = "due_reminder"  # Chores within reminder window
CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: Final = (
    "approval_reset_shared"  # SHARED/SHARED_FIRST resets
)
CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: Final = (
    "approval_reset_independent"  # INDEPENDENT resets
)

# Scanner Entry Field Keys (ChoreTimeEntry structure field keys)
CHORE_SCAN_ENTRY_USER_ID: Final = "user_id"  # User UUID
CHORE_SCAN_ENTRY_CHORE_ID: Final = "chore_id"  # Chore UUID
CHORE_SCAN_ENTRY_DUE_DT: Final = "due_dt"  # Due datetime object
CHORE_SCAN_ENTRY_CHORE_INFO: Final = "chore_info"  # Chore data dict
CHORE_SCAN_ENTRY_TIME_UNTIL_DUE: Final = "time_until_due"  # Time delta until due

# Reward States
REWARD_STATE_LOCKED: Final = "locked"
REWARD_STATE_AVAILABLE: Final = "available"
REWARD_STATE_REQUESTED: Final = "requested"
REWARD_STATE_APPROVED: Final = "approved"

# Badge States
BADGE_STATE_IN_PROGRESS: Final = "in_progress"
BADGE_STATE_EARNED: Final = "earned"
BADGE_STATE_ACTIVE_CYCLE: Final = "active_cycle"
CUMULATIVE_BADGE_STATE_ACTIVE = "active"
CUMULATIVE_BADGE_STATE_GRACE = "grace"
CUMULATIVE_BADGE_STATE_DEMOTED = "demoted"

# ------------------------------------------------------------------------------------------------
# Actions
# ------------------------------------------------------------------------------------------------

# Action titles for notifications (translation keys)
TRANS_KEY_NOTIF_ACTION_APPROVE: Final = "notif_action_approve"
TRANS_KEY_NOTIF_ACTION_COMPLETE: Final = "notif_action_complete"
TRANS_KEY_NOTIF_ACTION_DISAPPROVE: Final = "notif_action_disapprove"
TRANS_KEY_NOTIF_ACTION_REMIND_30: Final = "notif_action_remind_30"
TRANS_KEY_NOTIF_ACTION_SKIP: Final = "notif_action_skip"

# ================================================================================================
# NOTIFICATION TRANSLATION KEYS - Organized by Audience
# ================================================================================================
#
# Organization Philosophy:
#   - Assignee notifications: Gamified, second-person, encouraging tone
#   - Approver notifications: Informative, third-person, actionable content
#   - Grouped by category (chores, rewards, gamification) within each audience
#
# Note: This is a cosmetic organization only - no functional changes.
# All keys maintain exact same string values for translation system compatibility.
#

# ─── ASSIGNEE-FACING NOTIFICATIONS ──────────────────────────────────────────────────────────────

# Assignee: Chore Notifications (state changes, reminders, due dates)
TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED_ASSIGNEE: Final = (
    "notification_title_chore_approved_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED_ASSIGNEE: Final = (
    "notification_message_chore_approved_assignee"
)

TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED_ASSIGNEE: Final = (
    "notification_title_chore_disapproved_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED_ASSIGNEE: Final = (
    "notification_message_chore_disapproved_assignee"
)

TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE_ASSIGNEE: Final = (
    "notification_title_chore_overdue_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE_ASSIGNEE: Final = (
    "notification_message_chore_overdue_assignee"
)

TRANS_KEY_NOTIF_TITLE_CHORE_MISSED_ASSIGNEE: Final = (
    "notification_title_chore_missed_assignee"  # Phase 5
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED_ASSIGNEE: Final = (
    "notification_message_chore_missed_assignee"  # Phase 5
)


TRANS_KEY_NOTIF_TITLE_CHORE_DUE_REMINDER_ASSIGNEE: Final = (
    "notification_title_chore_due_reminder_assignee"  # Alias for due_soon
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_REMINDER_ASSIGNEE: Final = (
    "notification_message_chore_due_reminder_assignee"  # Alias for due_soon
)

TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW_ASSIGNEE: Final = (
    "notification_title_chore_due_window_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW_ASSIGNEE: Final = (
    "notification_message_chore_due_window_assignee"
)

# Assignee: Reward Notifications
TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED_ASSIGNEE: Final = (
    "notification_title_reward_approved_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED_ASSIGNEE: Final = (
    "notification_message_reward_approved_assignee"
)

TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED_ASSIGNEE: Final = (
    "notification_title_reward_disapproved_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_REWARD_DISAPPROVED_ASSIGNEE: Final = (
    "notification_message_reward_disapproved_assignee"
)

# Assignee: Gamification Notifications (badges, achievements, challenges, bonuses, penalties)
TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_ASSIGNEE: Final = (
    "notification_title_badge_earned_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_ASSIGNEE: Final = (
    "notification_message_badge_earned_assignee"
)

TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED_ASSIGNEE: Final = (
    "notification_title_achievement_earned_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_ASSIGNEE: Final = (
    "notification_message_achievement_earned_assignee"
)

TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED_ASSIGNEE: Final = (
    "notification_title_challenge_completed_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_ASSIGNEE: Final = (
    "notification_message_challenge_completed_assignee"
)

TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED_ASSIGNEE: Final = (
    "notification_title_penalty_applied_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_PENALTY_APPLIED_ASSIGNEE: Final = (
    "notification_message_penalty_applied_assignee"
)

TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED_ASSIGNEE: Final = (
    "notification_title_bonus_applied_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_BONUS_APPLIED_ASSIGNEE: Final = (
    "notification_message_bonus_applied_assignee"
)

TRANS_KEY_NOTIF_TITLE_MULTIPLIER_CHANGED_ASSIGNEE: Final = (
    "notification_title_multiplier_changed_assignee"
)
TRANS_KEY_NOTIF_MESSAGE_MULTIPLIER_CHANGED_ASSIGNEE: Final = (
    "notification_message_multiplier_changed_assignee"
)

# ─── APPROVER-FACING NOTIFICATIONS ───────────────────────────────────────────────────────────────

# Approver: Chore Claim/Approval Workflow
TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED_APPROVER: Final = (
    "notification_title_chore_claimed_approver"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED_APPROVER: Final = (
    "notification_message_chore_claimed_approver"
)

TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER_APPROVER: Final = (
    "notification_title_chore_reminder_approver"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_REMINDER_APPROVER: Final = (
    "notification_message_chore_reminder_approver"
)

# Approver: Chore overdue notification (different from assignee version)
TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE_APPROVER: Final = (
    "notification_title_chore_overdue_approver"
)
TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE_APPROVER: Final = (
    "notification_message_chore_overdue_approver"
)

# Approver: Aggregated/Tag-based Notifications
TRANS_KEY_NOTIF_TITLE_PENDING_CHORES_APPROVER: Final = (
    "notification_title_pending_chores_approver"
)
TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES_APPROVER: Final = (
    "notification_message_pending_chores_approver"
)

# Approver: Reward Claim/Approval Workflow
TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED_APPROVER: Final = (
    "notification_title_reward_claimed_approver"
)
TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_APPROVER: Final = (
    "notification_message_reward_claimed_approver"
)

TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER_APPROVER: Final = (
    "notification_title_reward_reminder_approver"
)
TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER_APPROVER: Final = (
    "notification_message_reward_reminder_approver"
)

# Approver: Gamification Notifications (informational copies)
TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_APPROVER: Final = (
    "notification_title_badge_earned_approver"
)
TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_APPROVER: Final = (
    "notification_message_badge_earned_approver"
)

TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED_APPROVER: Final = (
    "notification_title_achievement_earned_approver"
)
TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_APPROVER: Final = (
    "notification_message_achievement_earned_approver"
)

TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED_APPROVER: Final = (
    "notification_title_challenge_completed_approver"
)
TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_APPROVER: Final = (
    "notification_message_challenge_completed_approver"
)

TRANS_KEY_NOTIF_TITLE_MULTIPLIER_CHANGED_APPROVER: Final = (
    "notification_title_multiplier_changed_approver"
)
TRANS_KEY_NOTIF_MESSAGE_MULTIPLIER_CHANGED_APPROVER: Final = (
    "notification_message_multiplier_changed_approver"
)

# ─── ADMIN/SYSTEM NOTIFICATIONS ──────────────────────────────────────────────────────────────────

# System: Data Reset Notifications (admin actions)
TRANS_KEY_NOTIF_TITLE_DATA_RESET: Final = "notif_title_data_reset"
TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_GLOBAL: Final = "notif_message_data_reset_global"
TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ASSIGNEE: Final = "notif_message_data_reset_assignee"
TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ITEM_TYPE: Final = (
    "notif_message_data_reset_item_type"
)
TRANS_KEY_NOTIF_MESSAGE_DATA_RESET_ITEM: Final = "notif_message_data_reset_item"

# ================================================================================================
# End of Notification Translation Keys
# ================================================================================================
TRANS_KEY_NOTIF_ACTION_CLAIM: Final = "notif_action_claim"

# Action identifiers
ACTION_APPROVE_CHORE = "APPROVE_CHORE"
ACTION_APPROVE_REWARD = "APPROVE_REWARD"
ACTION_CLAIM_CHORE = "CLAIM_CHORE"
ACTION_COMPLETE_FOR_ASSIGNEE = "COMPLETE_FOR_ASSIGNEE"
ACTION_DISAPPROVE_CHORE = "DISAPPROVE_CHORE"
ACTION_DISAPPROVE_REWARD = "DISAPPROVE_REWARD"
ACTION_REMIND_30 = "REMIND_30"
ACTION_SKIP_CHORE = "SKIP_CHORE"


# ------------------------------------------------------------------------------------------------
# Translation Keys - Entity State Attributes
# ------------------------------------------------------------------------------------------------

# Translation keys for PURPOSE attribute values (sensor.py)
TRANS_KEY_PURPOSE_CHORE_STATUS: Final = "purpose_chore_status"
TRANS_KEY_PURPOSE_POINTS: Final = "purpose_points"
TRANS_KEY_PURPOSE_CHORES: Final = "purpose_chores"
TRANS_KEY_PURPOSE_USER_BADGES: Final = "purpose_user_badges"
TRANS_KEY_PURPOSE_BADGE_PROGRESS: Final = "purpose_badge_progress"
TRANS_KEY_PURPOSE_BADGE: Final = "purpose_badge"
TRANS_KEY_PURPOSE_SHARED_CHORE: Final = "purpose_shared_chore"
TRANS_KEY_PURPOSE_REWARD_STATUS: Final = "purpose_reward_status"
TRANS_KEY_PURPOSE_ACHIEVEMENT: Final = "purpose_achievement"
TRANS_KEY_PURPOSE_CHALLENGE: Final = "purpose_challenge"
TRANS_KEY_PURPOSE_ACHIEVEMENT_PROGRESS: Final = "purpose_achievement_progress"
TRANS_KEY_PURPOSE_CHALLENGE_PROGRESS: Final = "purpose_challenge_progress"
TRANS_KEY_PURPOSE_DASHBOARD_HELPER: Final = "purpose_dashboard_helper"
TRANS_KEY_PURPOSE_DASHBOARD_TRANSLATION: Final = "purpose_dashboard_translation"
# Legacy sensor purposes (sensor_legacy.py)

# Button purpose translation keys (button.py)
TRANS_KEY_PURPOSE_BUTTON_CHORE_CLAIM: Final = "purpose_button_chore_claim"
TRANS_KEY_PURPOSE_BUTTON_CHORE_APPROVE: Final = "purpose_button_chore_approve"
TRANS_KEY_PURPOSE_BUTTON_CHORE_DISAPPROVE: Final = "purpose_button_chore_disapprove"
TRANS_KEY_PURPOSE_BUTTON_REWARD_REDEEM: Final = "purpose_button_reward_redeem"
TRANS_KEY_PURPOSE_BUTTON_REWARD_APPROVE: Final = "purpose_button_reward_approve"
TRANS_KEY_PURPOSE_BUTTON_REWARD_DISAPPROVE: Final = "purpose_button_reward_disapprove"
TRANS_KEY_PURPOSE_BUTTON_PENALTY_APPLY: Final = "purpose_button_penalty_apply"
TRANS_KEY_PURPOSE_BUTTON_POINTS_ADJUST: Final = "purpose_button_points_adjust"
TRANS_KEY_PURPOSE_BUTTON_BONUS_APPLY: Final = "purpose_button_bonus_apply"

# Select purpose translation keys (select.py)
TRANS_KEY_PURPOSE_SELECT_CHORES: Final = "purpose_select_chores"
TRANS_KEY_PURPOSE_SELECT_REWARDS: Final = "purpose_select_rewards"
TRANS_KEY_PURPOSE_SELECT_PENALTIES: Final = "purpose_select_penalties"
TRANS_KEY_PURPOSE_SELECT_BONUSES: Final = "purpose_select_bonuses"
TRANS_KEY_PURPOSE_SELECT_USER_CHORES: Final = "purpose_select_user_chores"
TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_USER: Final = (
    "purpose_system_dashboard_admin_user"
)

# Calendar purpose translation keys (calendar.py)
TRANS_KEY_PURPOSE_CALENDAR_SCHEDULE: Final = "purpose_calendar_schedule"

# Datetime purpose translation keys (datetime.py)
TRANS_KEY_PURPOSE_DATETIME_DASHBOARD_HELPER: Final = "purpose_datetime_dashboard_helper"

# Translation keys for entity state attributes (all sensor classes)

# Dashboard Helper Sensor attributes (AssigneeDashboardHelperSensor)
TRANS_KEY_ATTR_LANGUAGE: Final = "language"

# Shared attributes across multiple sensors

# Chore-specific attributes (ChoreStatusSensor, dashboard helper chores array)


# ------------------------------------------------------------------------------------------------
# Entities Attributes
# ------------------------------------------------------------------------------------------------
ATTR_ACHIEVEMENT_NAME: Final = "achievement_name"
ATTR_ALL_EARNED_BADGES: Final = "all_earned_badges"
ATTR_APPROVAL_RESET_TYPE: Final = "approval_reset_type"
ATTR_APPROVAL_PERIOD_START: Final = "approval_period_start"
ATTR_APPLICABLE_DAYS: Final = "applicable_days"
ATTR_AWARDED: Final = "awarded"
ATTR_BADGE_AWARDS: Final = "awards"
ATTR_BONUS_BUTTON_EID: Final = "bonus_button_eid"
ATTR_CAN_APPROVE: Final = "can_approve"
ATTR_CAN_CLAIM: Final = "can_claim"
# Rotation UI attributes removed - not exposed in entity attributes
ATTR_CLAIMED_BY: Final = "claimed_by"
ATTR_COMPLETED_BY: Final = "completed_by"
ATTR_ASSIGNED_USER_NAMES: Final = "assigned_user_names"
ATTR_USER_NAME: Final = "user_name"
ATTR_ASSOCIATED_ACHIEVEMENT: Final = "associated_achievement"
ATTR_ASSOCIATED_CHALLENGE: Final = "associated_challenge"
ATTR_ASSOCIATED_CHORE: Final = "associated_chore"
ATTR_BADGE_NAME: Final = "badge_name"
ATTR_BADGE_STATUS: Final = "badge_status"
ATTR_BADGE_TYPE: Final = "badge_type"
ATTR_BONUS_NAME: Final = "bonus_name"
ATTR_BONUS_POINTS: Final = "bonus_points"
ATTR_CHALLENGE_NAME: Final = "challenge_name"
ATTR_CHORE_APPROVALS_COUNT: Final = "chore_approvals_count"
ATTR_CHORE_APPROVALS_TODAY: Final = "chore_approvals_today"
ATTR_CHORE_CLAIMS_COUNT: Final = "chore_claims_count"
ATTR_CHORE_COMPLETED_COUNT: Final = "chore_completed_count"
ATTR_CHORE_CURRENT_STREAK: Final = "chore_current_streak"
ATTR_CHORE_LONGEST_STREAK: Final = "chore_longest_streak"
ATTR_CHORE_CURRENT_MISSED_STREAK: Final = "chore_current_missed_streak"  # Phase 5
ATTR_CHORE_LONGEST_MISSED_STREAK: Final = "chore_longest_missed_streak"  # Phase 5
ATTR_CHORE_MISSED_COUNT: Final = "chore_missed_count"  # Phase 5
ATTR_CHORE_LAST_MISSED: Final = "chore_last_missed"  # Phase 5
ATTR_CHORE_POINTS_EARNED: Final = "chore_points_earned"
ATTR_CHORE_OVERDUE_COUNT: Final = "chore_overdue_count"
ATTR_CHORE_DISAPPROVED_COUNT: Final = "chore_disapproved_count"
ATTR_CHORE_LAST_LONGEST_STREAK_DATE: Final = "chore_last_longest_streak_date"
ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID: Final = "approve_button_eid"
ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID: Final = "claim_button_eid"
ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID: Final = "disapprove_button_eid"
ATTR_CHORE_NAME: Final = "chore_name"
ATTR_CLAIMED_ON: Final = "Claimed on"
ATTR_COST: Final = "cost"
ATTR_CRITERIA: Final = "criteria"
ATTR_BADGE_CUMULATIVE_CYCLE_POINTS: Final = "cycle_points"
ATTR_BADGE_CUMULATIVE_GRACE_END_DATE: Final = "maintenance_grace_end_date"
ATTR_BADGE_CUMULATIVE_MAINTENANCE_POINTS_REQUIRED: Final = "maintenance_points_required"
ATTR_BADGE_CUMULATIVE_MAINTENANCE_END_DATE: Final = "maintenance_end_date"
ATTR_BADGE_CUMULATIVE_POINTS_TO_MAINTENANCE: Final = "maintenance_points_remaining"
ATTR_CURRENT_BADGE_NAME: Final = "current_badge_name"
ATTR_CURRENT_BADGE_EID: Final = "current_badge_eid"
ATTR_CUSTOM_FREQUENCY_INTERVAL: Final = "custom_frequency_interval"
ATTR_CUSTOM_FREQUENCY_UNIT: Final = "custom_frequency_unit"
ATTR_DEFAULT_POINTS: Final = "default_points"
ATTR_DESCRIPTION: Final = "description"
ATTR_PREFIX_CHORE_STAT: Final = "chore_stat_"
ATTR_PREFIX_POINT_STAT: Final = "point_stat_"
ATTR_PURPOSE: Final = "purpose"

# PURPOSE values for sensor attributes (for translation support)
# Main sensors (sensor.py)
PURPOSE_SENSOR_POINTS: Final = "Current point balance and point stats"
PURPOSE_SENSOR_CHORES: Final = (
    "All time completed chores and chore stats (total, approved, claimed, pending)"
)
TRANS_KEY_PURPOSE_SENSOR_PENALTY_APPLIED: Final = "purpose_sensor_penalty_applied"
TRANS_KEY_PURPOSE_SENSOR_BONUS_APPLIED: Final = "purpose_sensor_bonus_applied"
# Legacy sensors (sensor_legacy.py)
TRANS_KEY_PURPOSE_SENSOR_CHORE_APPROVALS_ALL_TIME_EXTRA: Final = (
    "purpose_sensor_chore_approvals_all_time_extra"
)
TRANS_KEY_PURPOSE_SENSOR_CHORE_APPROVALS_TODAY_EXTRA: Final = (
    "purpose_sensor_chore_approvals_today_extra"
)
TRANS_KEY_PURPOSE_SENSOR_CHORE_APPROVALS_WEEK_EXTRA: Final = (
    "purpose_sensor_chore_approvals_week_extra"
)
TRANS_KEY_PURPOSE_SENSOR_CHORE_APPROVALS_MONTH_EXTRA: Final = (
    "purpose_sensor_chore_approvals_month_extra"
)
TRANS_KEY_PURPOSE_SENSOR_CHORES_PENDING_APPROVAL_EXTRA: Final = (
    "purpose_sensor_chores_pending_approval_extra"
)
TRANS_KEY_PURPOSE_SENSOR_REWARDS_PENDING_APPROVAL_EXTRA: Final = (
    "purpose_sensor_rewards_pending_approval_extra"
)
TRANS_KEY_PURPOSE_SENSOR_POINTS_EARNED_TODAY_EXTRA: Final = (
    "purpose_sensor_points_earned_today_extra"
)
TRANS_KEY_PURPOSE_SENSOR_POINTS_EARNED_WEEK_EXTRA: Final = (
    "purpose_sensor_points_earned_week_extra"
)
TRANS_KEY_PURPOSE_SENSOR_POINTS_EARNED_MONTH_EXTRA: Final = (
    "purpose_sensor_points_earned_month_extra"
)
TRANS_KEY_PURPOSE_SENSOR_POINTS_MAX_EVER_EXTRA: Final = (
    "purpose_sensor_points_max_ever_extra"
)
TRANS_KEY_PURPOSE_SENSOR_CHORE_STREAK_EXTRA: Final = "purpose_sensor_chore_streak_extra"

# PURPOSE values for button attributes (button.py)
PURPOSE_BUTTON_CHORE_CLAIM: Final = "Assignee claims completion of assigned chore"
PURPOSE_BUTTON_CHORE_APPROVE: Final = "Approver approves claimed chore"
PURPOSE_BUTTON_CHORE_DISAPPROVE: Final = "Approver disapproves claimed chore"
PURPOSE_BUTTON_REWARD_REDEEM: Final = "Assignee redeems reward using points"
PURPOSE_BUTTON_REWARD_APPROVE: Final = "Approver approves redeemed reward"
PURPOSE_BUTTON_REWARD_DISAPPROVE: Final = "Approver disapproves redeemed reward"
PURPOSE_BUTTON_PENALTY_APPLY: Final = "Approver applies penalty (deducts points)"
PURPOSE_BUTTON_POINTS_ADJUST: Final = "Approver manually adjusts assignee points"
PURPOSE_BUTTON_BONUS_APPLY: Final = "Approver applies bonus (adds points)"

# PURPOSE values for select attributes (select.py)
ATTR_DUE_DATE: Final = "due_date"
ATTR_DUE_WINDOW_START: Final = "due_window_start"
ATTR_END_DATE: Final = "end_date"
ATTR_GLOBAL_STATE: Final = "global_state"
ATTR_HIGHEST_BADGE_THRESHOLD_VALUE: Final = "highest_badge_threshold_value"
ATTR_HIGHEST_EARNED_BADGE_EID: Final = "highest_earned_badge_eid"
ATTR_HIGHEST_EARNED_BADGE_NAME: Final = "highest_earned_badge_name"
ATTR_USERS_ASSIGNED: Final = "assigned_user_names"
ATTR_USERS_EARNED: Final = "earned_user_names"
ATTR_LABELS: Final = "labels"
ATTR_LAST_APPROVED: Final = "last_approved"
ATTR_LAST_CLAIMED: Final = "last_claimed"
ATTR_LAST_COMPLETED: Final = "last_completed"
ATTR_LAST_DISAPPROVED: Final = "last_disapproved"
ATTR_LAST_OVERDUE: Final = "last_overdue"
ATTR_DASHBOARD_HELPER_EID: Final = "dashboard_helper_eid"
ATTR_SELECTED_USER_SLUG: Final = "selected_user_slug"
ATTR_SELECTED_USER_NAME: Final = "selected_user_name"
ATTR_NEXT_HIGHER_BADGE_NAME: Final = "next_higher_badge_name"
ATTR_NEXT_HIGHER_BADGE_EID: Final = "next_higher_badge_eid"
ATTR_NEXT_LOWER_BADGE_NAME: Final = "next_lower_badge_name"
ATTR_NEXT_LOWER_BADGE_EID: Final = "next_lower_badge_eid"
ATTR_OCCASION_TYPE: Final = "occasion_type"
ATTR_PENALTY_BUTTON_EID: Final = "penalty_button_eid"
ATTR_PENALTY_NAME: Final = "penalty_name"
ATTR_PENALTY_POINTS: Final = "penalty_points"
ATTR_POINTS_MULTIPLIER: Final = "points_multiplier"
ATTR_POINTS_TO_NEXT_BADGE: Final = "points_to_next_badge"
ATTR_RAW_PROGRESS: Final = "raw_progress"
ATTR_RECURRING_FREQUENCY: Final = "recurring_frequency"
ATTR_REQUIRED_CHORES: Final = "required_chores"
ATTR_RESET_SCHEDULE: Final = "reset_schedule"
ATTR_REWARD_APPROVALS_COUNT: Final = "reward_approvals_count"
ATTR_REWARD_CLAIMS_COUNT: Final = "reward_claims_count"
ATTR_REWARD_NAME: Final = "reward_name"
ATTR_REDEEMED_ON: Final = "Redeemed on"
ATTR_REWARD_POINTS: Final = "reward_points"
ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID: Final = "approve_button_eid"
ATTR_REWARD_CLAIM_BUTTON_ENTITY_ID: Final = "claim_button_eid"
ATTR_REWARD_DISAPPROVE_BUTTON_ENTITY_ID: Final = "disapprove_button_eid"

# Reward Status Sensor Attributes - Period Stats
ATTR_REWARD_PENDING_CLAIMS: Final = "pending_claims"
ATTR_REWARD_LAST_CLAIMED: Final = "last_claimed"
ATTR_REWARD_LAST_APPROVED: Final = "last_approved"
ATTR_REWARD_LAST_DISAPPROVED: Final = "last_disapproved"
ATTR_REWARD_CLAIMED_TODAY: Final = "claimed_today"
ATTR_REWARD_CLAIMED_WEEK: Final = "claimed_week"
ATTR_REWARD_CLAIMED_MONTH: Final = "claimed_month"
ATTR_REWARD_CLAIMED_YEAR: Final = "claimed_year"
ATTR_REWARD_CLAIMED_ALL_TIME: Final = "claimed_all_time"
ATTR_REWARD_APPROVED_TODAY: Final = "approved_today"
ATTR_REWARD_APPROVED_WEEK: Final = "approved_week"
ATTR_REWARD_APPROVED_MONTH: Final = "approved_month"
ATTR_REWARD_APPROVED_YEAR: Final = "approved_year"
ATTR_REWARD_APPROVED_ALL_TIME: Final = "approved_all_time"
ATTR_REWARD_DISAPPROVED_TODAY: Final = "disapproved_today"
ATTR_REWARD_DISAPPROVED_WEEK: Final = "disapproved_week"
ATTR_REWARD_DISAPPROVED_MONTH: Final = "disapproved_month"
ATTR_REWARD_DISAPPROVED_YEAR: Final = "disapproved_year"
ATTR_REWARD_DISAPPROVED_ALL_TIME: Final = "disapproved_all_time"
ATTR_REWARD_POINTS_SPENT_TODAY: Final = "points_spent_today"
ATTR_REWARD_POINTS_SPENT_WEEK: Final = "points_spent_week"
ATTR_REWARD_POINTS_SPENT_MONTH: Final = "points_spent_month"
ATTR_REWARD_POINTS_SPENT_YEAR: Final = "points_spent_year"
ATTR_REWARD_POINTS_SPENT_ALL_TIME: Final = "points_spent_all_time"
ATTR_REWARD_APPROVAL_RATE: Final = "approval_rate"
ATTR_REWARD_CLAIM_RATE_WEEK: Final = "claim_rate_week"
ATTR_REWARD_CLAIM_RATE_MONTH: Final = "claim_rate_month"
ATTR_START_DATE: Final = "start_date"
ATTR_STREAKS_BY_ACHIEVEMENT: Final = "streaks_by_achievement"
ATTR_COMPLETION_CRITERIA: Final = "completion_criteria"
ATTR_TARGET: Final = "target"
ATTR_TARGET_VALUE: Final = "target_value"

ATTR_TYPE: Final = "type"

# Dashboard Helper Sensor Attributes
ATTR_CHORES_BY_LABEL: Final = "chores_by_label"
ATTR_CHORE_CLAIMED_BY: Final = "claimed_by"
ATTR_CHORE_COMPLETED_BY: Final = "completed_by"
ATTR_CHORE_DUE_DATE: Final = "due_date"
ATTR_CHORE_IS_TODAY_AM: Final = "is_today_am"
ATTR_CHORE_LABELS: Final = "labels"
ATTR_CHORE_PRIMARY_GROUP: Final = "primary_group"

# Phase 4: Rotation and availability dashboard attributes
ATTR_CHORE_LOCK_REASON: Final = "lock_reason"
ATTR_CHORE_TURN_USER_NAME: Final = "turn_user_name"
ATTR_CHORE_AVAILABLE_AT: Final = "available_at"

# Common attributes for chores and rewards in dashboard helper
ATTR_EID: Final = "eid"
ATTR_NAME: Final = "name"
ATTR_STATUS: Final = "status"
ATTR_TIME_UNTIL_DUE: Final = "time_until_due"
ATTR_TIME_UNTIL_OVERDUE: Final = "time_until_overdue"
ATTR_CLAIMS: Final = "claims"
ATTR_APPROVALS: Final = "approvals"
ATTR_POINTS: Final = "points"
ATTR_APPLIED: Final = "applied"
ATTR_BADGE_EARNED: Final = "earned"
ATTR_EARNED_COUNT: Final = "earned_count"

# Primary Group Values
PRIMARY_GROUP_TODAY = "today"
PRIMARY_GROUP_THIS_WEEK = "this_week"
PRIMARY_GROUP_OTHER = "other"


# ================================================================================================
# Entity ID Constants (SUFFIX and MIDFIX patterns)
# ================================================================================================
#
# See docs/ARCHITECTURE.md "Entity ID Construction Patterns" for detailed explanation of:
# - SUFFIX pattern: Appended identifiers ("_points", "_badge")
# - MIDFIX pattern: Embedded between parts ("_chore_claim_", "_bonus_")
# - UNIQUE_ID construction: entry_id + [_ids] + SUFFIX
# - ENTITY_ID construction: prefix + [names] + [MIDFIX] + [names] + [SUFFIX]
#
# ================================================================================================

# ------------------------------------------------------------------------------------------------
# Sensors
# ------------------------------------------------------------------------------------------------

# Sensor Prefixes
SENSOR_KC_PREFIX: Final = "sensor.kc_"

# ------------------------------------------------------------------------------------------------
# DateTime
# ------------------------------------------------------------------------------------------------

# DateTime Prefix
DATETIME_KC_PREFIX: Final = "datetime.kc_"

# DateTime Unique ID Suffix
DATETIME_KC_UID_SUFFIX_DATE_HELPER: Final = "_dashboard_datetime_picker"

# Sensor Unique ID Suffixes
SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_SENSOR: Final = "_achievement_status"
SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR: Final = "_achievement_progress"
SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR: Final = "_badge_progress"
SENSOR_KC_UID_SUFFIX_BADGE_SENSOR: Final = "_badge_status"
SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR: Final = "_bonus_status"
SENSOR_KC_UID_SUFFIX_CHALLENGE_SENSOR: Final = "_challenge_status"
SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR: Final = "_challenge_progress"
SENSOR_KC_UID_SUFFIX_CHORES_SENSOR: Final = "_assignee_chores_summary"
SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR: Final = "_chores_completed_daily"
SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR: Final = "_chores_completed_monthly"
SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR: Final = "_chores_completed_total"
SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR: Final = "_chores_completed_weekly"
SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR: Final = "_chore_status"
SENSOR_KC_UID_SUFFIX_ASSIGNEE_BADGES_SENSOR: Final = "_assignee_badges"
SENSOR_KC_UID_SUFFIX_ASSIGNEE_HIGHEST_STREAK_SENSOR: Final = "_chores_highest_streak"
SENSOR_KC_UID_SUFFIX_ASSIGNEE_MAX_POINTS_EVER_SENSOR: Final = "_points_max_ever"
SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR: Final = "_points_earned_daily"
SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR: Final = (
    "_points_earned_monthly"
)
SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR: Final = (
    "_points_earned_weekly"
)
SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR: Final = "_assignee_points"
SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR: Final = "_penalty_status"
SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR: Final = "_chores_pending_approvals"
SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR: Final = (
    "_rewards_pending_approvals"
)
SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR: Final = "_reward_status"
SENSOR_KC_UID_SUFFIX_SHARED_CHORE_GLOBAL_STATE_SENSOR: Final = "_chore_global_status"

# Sensor Entity ID constants still in active use (runtime)
SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER: Final = "_dashboard_helper"

# System-level dashboard translation sensor (one per language in use)
SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG: Final = "_dashboard_lang"

# Translation sensor pointer attribute (on dashboard helper)
ATTR_TRANSLATION_SENSOR_EID: Final = "translation_sensor_eid"

# ------------------------------------------------------------------------------------------------
# Selects
# ------------------------------------------------------------------------------------------------

# Select Unique ID Mid & Suffixes
# Use SUFFIX pattern for consistent entity unique IDs
SELECT_KC_UID_SUFFIX_ASSIGNEE_DASHBOARD_HELPER_CHORES_SELECT: Final = (
    "_assignee_dashboard_helper_chores_select"
)
SELECT_KC_UID_SUFFIX_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE_SELECT: Final = (
    "_system_dashboard_admin_assignee_select"
)
SELECT_KC_UID_SUFFIX_BONUSES_SELECT: Final = "_select_bonuses"
SELECT_KC_UID_SUFFIX_CHORES_SELECT: Final = "_select_chores"
SELECT_KC_UID_SUFFIX_PENALTIES_SELECT: Final = "_select_penalties"
SELECT_KC_UID_SUFFIX_REWARDS_SELECT: Final = "_select_rewards"

# ------------------------------------------------------------------------------------------------
# Buttons
# ------------------------------------------------------------------------------------------------

# Button Prefixes
BUTTON_KC_PREFIX: Final = "button.kc_"

# Button Unique ID Mid & Suffixes
# Use SUFFIX pattern for consistent entity unique IDs
BUTTON_KC_UID_SUFFIX_APPROVE: Final = "_chore_approve"
BUTTON_KC_UID_SUFFIX_APPROVE_REWARD: Final = "_reward_approve"
BUTTON_KC_UID_SUFFIX_CLAIM: Final = "_chore_claim"
BUTTON_KC_UID_SUFFIX_DISAPPROVE: Final = "_chore_disapprove"
BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD: Final = "_reward_disapprove"
# New class-aligned SUFFIX constants for PREFIX/MIDFIX migration
BUTTON_KC_UID_SUFFIX_ASSIGNEE_REWARD_REDEEM: Final = "_assignee_reward_redeem_button"
BUTTON_KC_UID_SUFFIX_APPROVER_BONUS_APPLY: Final = "_approver_bonus_apply_button"
BUTTON_KC_UID_SUFFIX_APPROVER_PENALTY_APPLY: Final = "_approver_penalty_apply_button"
BUTTON_KC_UID_SUFFIX_APPROVER_POINTS_ADJUST: Final = "_approver_points_adjust_button"

# ------------------------------------------------------------------------------------------------
# Calendars
# ------------------------------------------------------------------------------------------------

# Calendar Prefixes
CALENDAR_KC_PREFIX: Final = "calendar.kc_"

# Calendar Unique ID Mid & Suffixes
CALENDAR_KC_UID_SUFFIX_CALENDAR: Final = "_assignee_calendar"

# ------------------------------------------------------------------------------------------------
# Helper Return Types
# ------------------------------------------------------------------------------------------------
HELPER_RETURN_DATE = "date"
HELPER_RETURN_DATETIME = "datetime"
HELPER_RETURN_DATETIME_LOCAL = "datetime_local"
HELPER_RETURN_DATETIME_UTC = "datetime_utc"
HELPER_RETURN_ISO_DATE = "iso_date"
HELPER_RETURN_ISO_DATETIME = "iso_datetime"
# For HA DateTimeSelector - local timezone, format: "%Y-%m-%d %H:%M:%S"
HELPER_RETURN_SELECTOR_DATETIME = "selector_datetime"

# ------------------------------------------------------------------------------------------------
# DateTime Helper Safety Limits
# ------------------------------------------------------------------------------------------------
# Maximum number of iterations allowed in date calculation loops to prevent infinite loops
# Used in dt_next_schedule() and add_interval_to_datetime() when require_future=True
MAX_DATE_CALCULATION_ITERATIONS: Final = 1000

# ------------------------------------------------------------------------------------------------
# DateTime Constants (End-of-Period Values)
# ------------------------------------------------------------------------------------------------
# Time values for end-of-day calculations (23:59:00)
END_OF_DAY_HOUR: Final = 23
END_OF_DAY_MINUTE: Final = 59
END_OF_DAY_SECOND: Final = 0

# Calendar calculations
MONTHS_PER_QUARTER: Final = 3
LAST_DAY_OF_DECEMBER: Final = 31
LAST_MONTH_OF_YEAR: Final = 12

# Weekday index for Sunday in Python's datetime.weekday() (Monday=0, Sunday=6)
SUNDAY_WEEKDAY_INDEX: Final = 6

# ISO date string slice length (YYYY-MM-DD = 10 characters)
ISO_DATE_STRING_LENGTH: Final = 10

# Month multiplier for interval calculations

# ------------------------------------------------------------------------------------------------
# Services
# ------------------------------------------------------------------------------------------------
SERVICE_APPLY_BONUS: Final = "apply_bonus"
SERVICE_APPLY_PENALTY: Final = "apply_penalty"
SERVICE_APPROVE_CHORE: Final = "approve_chore"
SERVICE_APPROVE_REWARD: Final = "approve_reward"
SERVICE_CLAIM_CHORE: Final = "claim_chore"
SERVICE_ADD_CHORE: Final = (
    "create_chore"  # Alias for SERVICE_CREATE_CHORE (test compatibility)
)
SERVICE_CREATE_CHORE: Final = "create_chore"
SERVICE_CREATE_REWARD: Final = "create_reward"
SERVICE_DELETE_CHORE: Final = "delete_chore"
SERVICE_DELETE_REWARD: Final = "delete_reward"
SERVICE_DISAPPROVE_CHORE: Final = "disapprove_chore"
SERVICE_DISAPPROVE_REWARD: Final = "disapprove_reward"

SERVICE_REDEEM_REWARD: Final = "redeem_reward"
SERVICE_REMOVE_AWARDED_BADGES: Final = "remove_awarded_badges"
SERVICE_RESET_CHORES_TO_PENDING_STATE: Final = (
    "reset_chores_to_pending_state"  # Renamed from reset_all_chores
)
# NOTE: SERVICE_RESET_ALL_DATA, SERVICE_RESET_ALL_CHORES renamed in v0.6.0 to factory_reset, reset_chores_to_pending_state
# NOTE: SERVICE_RESET_BONUSES, SERVICE_RESET_PENALTIES, SERVICE_RESET_REWARDS removed in v0.6.0
# Superseded by SERVICE_RESET_TRANSACTIONAL_DATA with scope="assignee" or "global" and item_type filter
SERVICE_RESET_OVERDUE_CHORES: Final = "reset_overdue_chores"
SERVICE_RESET_TRANSACTIONAL_DATA: Final = "reset_transactional_data"
SERVICE_SET_CHORE_DUE_DATE: Final = "set_chore_due_date"
SERVICE_SKIP_CHORE_DUE_DATE: Final = "skip_chore_due_date"
# Phase 3 Step 7 - Rotation management services (v0.5.0)
SERVICE_SET_ROTATION_TURN: Final = "set_rotation_turn"
SERVICE_RESET_ROTATION: Final = "reset_rotation"
SERVICE_OPEN_ROTATION_CYCLE: Final = "open_rotation_cycle"
SERVICE_UPDATE_CHORE: Final = "update_chore"
SERVICE_UPDATE_REWARD: Final = "update_reward"
SERVICE_GENERATE_ACTIVITY_REPORT: Final = "generate_activity_report"


# ------------------------------------------------------------------------------------------------
# Service Field Names (user-facing API for service calls)
# ------------------------------------------------------------------------------------------------
# These are the field names users see in automations/scripts. They should be:
# - User-friendly ("name" not "reward_name" for create_reward service)
# - Consistent across similar services
# - Mapped to CFOF_* constants internally via _SERVICE_TO_*_FORM_MAPPING

# Data Reset Service Fields
SERVICE_FIELD_CONFIRM_DESTRUCTIVE: Final = "confirm_destructive"
SERVICE_FIELD_SCOPE: Final = "scope"
SERVICE_FIELD_ITEM_NAME: Final = "item_name"
SERVICE_FIELD_ITEM_TYPE: Final = (
    "item_type"  # Used for both item_type scope AND item scope
)

# Data reset service scope types (NEVER use "reset" alone - always qualify)
# Scope = WHO is affected (all users vs one user)
DATA_RESET_SCOPE_GLOBAL: Final = "global"  # All users
DATA_RESET_SCOPE_USER: Final = "user"  # One user (requires assignee_name)

# Data reset service item type values (WHAT domain to reset)
# Optional - if omitted, resets ALL domains for the scope
DATA_RESET_ITEM_TYPE_POINTS: Final = (
    "points"  # Points, ledger, point_data (EconomyManager)
)
DATA_RESET_ITEM_TYPE_CHORES: Final = "chores"
DATA_RESET_ITEM_TYPE_REWARDS: Final = "rewards"
DATA_RESET_ITEM_TYPE_BADGES: Final = "badges"
DATA_RESET_ITEM_TYPE_ACHIEVEMENTS: Final = "achievements"
DATA_RESET_ITEM_TYPE_CHALLENGES: Final = "challenges"
DATA_RESET_ITEM_TYPE_PENALTIES: Final = "penalties"
DATA_RESET_ITEM_TYPE_BONUSES: Final = "bonuses"
#
# Pattern: SERVICE_FIELD_{ENTITY}_{FIELD} for entity-specific fields
#          SERVICE_FIELD_{FIELD} for cross-entity actor fields
# ------------------------------------------------------------------------------------------------

# Cross-entity service fields (used by multiple services)
SERVICE_FIELD_CONFIG_ENTRY_ID: Final = "config_entry_id"
SERVICE_FIELD_CONFIG_ENTRY_TITLE: Final = "config_entry_title"
SERVICE_FIELD_USER_NAME: Final = "user_name"
SERVICE_FIELD_USER_ID: Final = "user_id"
SERVICE_FIELD_APPROVER_NAME: Final = "approver_name"

# Chore service fields (workflow)
SERVICE_FIELD_CHORE_NAME: Final = "chore_name"
SERVICE_FIELD_CHORE_ID: Final = "chore_id"
SERVICE_FIELD_MARK_AS_MISSED: Final = (
    "mark_as_missed"  # Phase 5: Skip service parameter
)

# Chore service fields (CRUD) - user-friendly names for service calls
SERVICE_FIELD_CHORE_CRUD_ID: Final = "id"
SERVICE_FIELD_CHORE_CRUD_NAME: Final = "name"
SERVICE_FIELD_CHORE_CRUD_POINTS: Final = "points"
SERVICE_FIELD_CHORE_CRUD_DESCRIPTION: Final = "description"
SERVICE_FIELD_CHORE_CRUD_ICON: Final = "icon"
SERVICE_FIELD_CHORE_CRUD_LABELS: Final = "labels"
SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES: Final = "assigned_user_names"
SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
SERVICE_FIELD_CHORE_CRUD_FREQUENCY: Final = "frequency"
SERVICE_FIELD_CHORE_CRUD_APPLICABLE_DAYS: Final = "applicable_days"
SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA: Final = "completion_criteria"
SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET: Final = "approval_reset_type"
SERVICE_FIELD_CHORE_CRUD_PENDING_CLAIMS: Final = "pending_claims"
SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING: Final = "overdue_handling"
SERVICE_FIELD_CHORE_CRUD_CLAIM_LOCK_UNTIL_WINDOW: Final = CHORE_CLAIM_LOCK_UNTIL_WINDOW
SERVICE_FIELD_CHORE_CRUD_AUTO_APPROVE: Final = "auto_approve"
SERVICE_FIELD_CHORE_CRUD_DUE_DATE: Final = "due_date"
SERVICE_FIELD_CHORE_CRUD_DUE_WINDOW_OFFSET: Final = "due_window_offset"
SERVICE_FIELD_CHORE_CRUD_DUE_REMINDER_OFFSET: Final = "due_reminder_offset"

# ==== Test aliases for convenience (used in Phase 1 tests) ====
SERVICE_FIELD_NAME: Final = "name"  # Alias for SERVICE_FIELD_CHORE_CRUD_NAME
SERVICE_FIELD_ASSIGNED_USER_NAMES: Final = (
    "assigned_user_names"  # Alias for SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_NAMES
)
SERVICE_FIELD_ASSIGNED_USER_IDS: Final = (
    "assigned_user_ids"  # Alias for SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS
)
SERVICE_FIELD_FREQUENCY: Final = (
    "frequency"  # Alias for SERVICE_FIELD_CHORE_CRUD_FREQUENCY
)
SERVICE_FIELD_POINTS: Final = "points"  # Alias for SERVICE_FIELD_CHORE_CRUD_POINTS
SERVICE_FIELD_APPROVAL_RESET_TYPE: Final = (
    "approval_reset_type"  # Alias for SERVICE_FIELD_CHORE_CRUD_APPROVAL_RESET
)
SERVICE_FIELD_OVERDUE_HANDLING: Final = (
    "overdue_handling"  # Alias for SERVICE_FIELD_CHORE_CRUD_OVERDUE_HANDLING
)

# Reward service fields (workflow) - used by redeem_reward, approve_reward, disapprove_reward
SERVICE_FIELD_REWARD_ID: Final = "id"
SERVICE_FIELD_REWARD_NAME: Final = "reward_name"
SERVICE_FIELD_REWARD_COST_OVERRIDE: Final = "cost_override"

# Reward service fields (CRUD) - user-friendly names for service calls
SERVICE_FIELD_REWARD_CRUD_ID: Final = "id"
SERVICE_FIELD_REWARD_CRUD_NAME: Final = "name"
SERVICE_FIELD_REWARD_CRUD_COST: Final = "cost"
SERVICE_FIELD_REWARD_CRUD_DESCRIPTION: Final = "description"
SERVICE_FIELD_REWARD_CRUD_ICON: Final = "icon"
SERVICE_FIELD_REWARD_CRUD_LABELS: Final = "labels"

# Penalty service fields
SERVICE_FIELD_PENALTY_NAME: Final = "penalty_name"

# Bonus service fields
SERVICE_FIELD_BONUS_NAME: Final = "bonus_name"

# Badge service fields
SERVICE_FIELD_BADGE_NAME: Final = "badge_name"

# Shared workflow fields
SERVICE_FIELD_CHORE_DUE_DATE: Final = "due_date"
SERVICE_FIELD_CHORE_POINTS_AWARDED: Final = "points_awarded"

# Reporting service fields
SERVICE_FIELD_REPORT_NOTIFY_SERVICE: Final = "notify_service"
SERVICE_FIELD_REPORT_TITLE: Final = "report_title"
SERVICE_FIELD_REPORT_LANGUAGE: Final = "report_language"
SERVICE_FIELD_REPORT_OUTPUT_FORMAT: Final = "output_format"

# Report output modes
REPORT_OUTPUT_FORMAT_MARKDOWN: Final = "markdown"
REPORT_OUTPUT_FORMAT_HTML: Final = "html"
REPORT_OUTPUT_FORMAT_BOTH: Final = "both"

# Reporting range modes
REPORT_RANGE_MODE_LAST_7_DAYS: Final = "last_7_days"
REPORT_RANGE_MODE_LAST_30_DAYS: Final = "last_30_days"
REPORT_RANGE_MODE_CUSTOM: Final = "custom"

# Reporting style modes
REPORT_STYLE_ASSIGNEE: Final = "assignee"
REPORT_STYLE_AUTOMATION: Final = "automation"
REPORT_STYLE_BOTH: Final = "both"

# ------------------------------------------------------------------------------------------------
# Labels
# ------------------------------------------------------------------------------------------------
LABEL_DISABLED: Final = "Disabled"
LABEL_NONE: Final = ""
LABEL_POINTS: Final = "Points"

# Entity Type Labels (for error messages and translation placeholders)
LABEL_ASSIGNEE: Final = "Assignee"
LABEL_CHORE: Final = "Chore"
LABEL_REWARD: Final = "Reward"
LABEL_BADGE: Final = "Badge"
LABEL_PENALTY: Final = "Penalty"
LABEL_BONUS: Final = "Bonus"
LABEL_APPROVER: Final = "Approver"
LABEL_ACHIEVEMENT: Final = "Achievement"
LABEL_CHALLENGE: Final = "Challenge"

# Backup/Restore Labels
# (backup label constants removed - now using emoji prefixes directly)

# Migration identifiers (for schema version tracking in DATA_META_MIGRATIONS_APPLIED)
MIGRATION_DATETIME_UTC: Final = "datetime_utc"
MIGRATION_CHORE_DATA_STRUCTURE: Final = "chore_data_structure"
MIGRATION_BADGE_RESTRUCTURE: Final = "badge_restructure"
MIGRATION_CUMULATIVE_BADGE_PROGRESS: Final = "cumulative_badge_progress"
MIGRATION_BADGES_EARNED_DICT: Final = "badges_earned_dict"
MIGRATION_POINT_STATS: Final = "point_stats"
MIGRATION_CHORE_DATA_AND_STREAKS: Final = "chore_data_and_streaks"

DEFAULT_MIGRATIONS_APPLIED: Final = [
    MIGRATION_DATETIME_UTC,
    MIGRATION_CHORE_DATA_STRUCTURE,
    "assignee_data_structure",
    MIGRATION_BADGE_RESTRUCTURE,
    MIGRATION_CUMULATIVE_BADGE_PROGRESS,
    MIGRATION_BADGES_EARNED_DICT,
    MIGRATION_POINT_STATS,
    MIGRATION_CHORE_DATA_AND_STREAKS,
]


# ------------------------------------------------------------------------------------------------
# Button Prefixes (DEPRECATED - kept for migration/cleanup of legacy entities)
# ------------------------------------------------------------------------------------------------
# These PREFIX patterns are deprecated. New entities use SUFFIX pattern.
# Kept only for _extract_assignee_id_from_unique_id() and migration scripts.
# TODO: Remove after v1.0 when all users have migrated
BUTTON_BONUS_PREFIX: Final = "bonus_button_"  # DEPRECATED
BUTTON_PENALTY_PREFIX: Final = "penalty_button_"  # DEPRECATED
BUTTON_REWARD_PREFIX: Final = "reward_button_"  # DEPRECATED


# ------------------------------------------------------------------------------------------------
# Entity Registry (Single Source of Truth for Entity Creation & Cleanup)
# ------------------------------------------------------------------------------------------------
# Defines creation requirements for ALL entity types. Used for:
# - Proactive filtering at entity creation time
# - User-role feature gating (whitelist approach)
# - Extra entity cleanup when flag disabled
# - Event-based cleanup on delete/unassign
#
# Key: unique_id suffix, Value: EntityRequirement
#
# === FLAG LAYERING LOGIC ===
# Requirements define CATEGORIES, not final logic. Evaluation rules:
#
# | Requirement   | Default participant                    | Feature-gated participant                         |
# |---------------|----------------------------------------|---------------------------------------------------|
# | ALWAYS        | Created                                | Created                                           |
# | WORKFLOW      | Created                                | Only if `enable_chore_workflow=True`              |
# | GAMIFICATION  | Created                                | Only if `enable_gamification=True`                |
# | EXTRA         | If show_extra flag                     | If show_extra flag AND `enable_gamification=True` |
#
# Note: EXTRA requires BOTH show_legacy_entities system flag AND gamification.
# (Config key is still 'show_legacy_entities' for backward compatibility, but
# we call these "extra" entities in the UI and code - they're optional sensors.)
# For default participants, gamification is always enabled, so EXTRA just needs flag.
# For feature-gated participants, EXTRA needs flag AND enable_gamification=True.
#
# The should_create_entity() function in helpers/entity_helpers.py implements this logic.


class EntityRequirement(StrEnum):
    """Defines when an entity should be created.

    These are requirement CATEGORIES. The actual evaluation logic considers:
    - User role profile type (default participant vs feature-gated participant)
    - System flags (show_legacy_entities aka "extra entities" in UI)
    - Approver role flags (enable_gamification, enable_chore_workflow) for feature-gated users

    EXTRA has compound logic: requires show_legacy_entities AND gamification.
    (Originally called "legacy" - renamed to "extra" to match UI terminology.)
    """

    ALWAYS = "always"  # All assignment participants
    WORKFLOW = (
        "workflow"  # Requires enable_chore_workflow for feature-gated participants
    )
    GAMIFICATION = (
        "gamification"  # Requires enable_gamification for feature-gated participants
    )
    EXTRA = "extra"  # Requires show_legacy_entities AND gamification (optional sensors)


# Entity Registry: suffix -> EntityRequirement
# Organized by platform and requirement type
ENTITY_REGISTRY: Final[dict[str, EntityRequirement]] = {
    # === SENSORS: Always (base functionality) ===
    SENSOR_KC_UID_SUFFIX_CHORE_STATUS_SENSOR: EntityRequirement.ALWAYS,
    SENSOR_KC_UID_SUFFIX_CHORES_SENSOR: EntityRequirement.ALWAYS,
    SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER: EntityRequirement.ALWAYS,
    # === SENSORS: Gamification ===
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_BADGES_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_BADGE_PROGRESS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_BADGE_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_REWARD_STATUS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_ACHIEVEMENT_PROGRESS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_CHALLENGE_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_CHALLENGE_PROGRESS_SENSOR: EntityRequirement.GAMIFICATION,
    SENSOR_KC_UID_SUFFIX_SHARED_CHORE_GLOBAL_STATE_SENSOR: EntityRequirement.ALWAYS,
    SENSOR_KC_UID_SUFFIX_DASHBOARD_LANG: EntityRequirement.ALWAYS,
    # === SENSORS: Extra (optional, flag-controlled via show_legacy_entities) ===
    # Note: Called "extra" in UI, config key is still "show_legacy_entities" for compat
    SENSOR_KC_UID_SUFFIX_COMPLETED_TOTAL_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_COMPLETED_DAILY_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_COMPLETED_WEEKLY_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_COMPLETED_MONTHLY_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_PENDING_CHORE_APPROVALS_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_PENDING_REWARD_APPROVALS_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_HIGHEST_STREAK_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_ASSIGNEE_MAX_POINTS_EVER_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_PENALTY_APPLIES_SENSOR: EntityRequirement.EXTRA,
    SENSOR_KC_UID_SUFFIX_BONUS_APPLIES_SENSOR: EntityRequirement.EXTRA,
    # === BUTTONS: Always (base approval) ===
    BUTTON_KC_UID_SUFFIX_APPROVE: EntityRequirement.ALWAYS,
    # === BUTTONS: Workflow ===
    BUTTON_KC_UID_SUFFIX_CLAIM: EntityRequirement.WORKFLOW,
    BUTTON_KC_UID_SUFFIX_DISAPPROVE: EntityRequirement.WORKFLOW,
    # === BUTTONS: Gamification ===
    BUTTON_KC_UID_SUFFIX_APPROVER_POINTS_ADJUST: EntityRequirement.GAMIFICATION,
    BUTTON_KC_UID_SUFFIX_APPROVE_REWARD: EntityRequirement.GAMIFICATION,
    BUTTON_KC_UID_SUFFIX_DISAPPROVE_REWARD: EntityRequirement.GAMIFICATION,
    BUTTON_KC_UID_SUFFIX_ASSIGNEE_REWARD_REDEEM: EntityRequirement.GAMIFICATION,
    BUTTON_KC_UID_SUFFIX_APPROVER_BONUS_APPLY: EntityRequirement.GAMIFICATION,
    BUTTON_KC_UID_SUFFIX_APPROVER_PENALTY_APPLY: EntityRequirement.GAMIFICATION,
    # === SELECT: Always (dashboard helpers) ===
    SELECT_KC_UID_SUFFIX_ASSIGNEE_DASHBOARD_HELPER_CHORES_SELECT: EntityRequirement.ALWAYS,
    SELECT_KC_UID_SUFFIX_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE_SELECT: EntityRequirement.ALWAYS,
    # === SELECT: Extra (system-wide legacy selects) ===
    SELECT_KC_UID_SUFFIX_CHORES_SELECT: EntityRequirement.EXTRA,
    SELECT_KC_UID_SUFFIX_REWARDS_SELECT: EntityRequirement.EXTRA,
    SELECT_KC_UID_SUFFIX_BONUSES_SELECT: EntityRequirement.EXTRA,
    SELECT_KC_UID_SUFFIX_PENALTIES_SELECT: EntityRequirement.EXTRA,
    # === DATETIME: Always ===
    DATETIME_KC_UID_SUFFIX_DATE_HELPER: EntityRequirement.ALWAYS,
    # === CALENDAR: Always ===
    CALENDAR_KC_UID_SUFFIX_CALENDAR: EntityRequirement.ALWAYS,
}

# Derived lists from ENTITY_REGISTRY for efficient lookups
# Extra entities: optional sensors requiring show_legacy_entities flag
# (Called "extra" in UI; config key kept as "show_legacy_entities" for backward compat)

# ------------------------------------------------------------------------------------------------
# Errors and Warnings
# ------------------------------------------------------------------------------------------------

# Translation Keys for Phase 2b: Generic Error Templates (coordinator.py remediation)
# These 12 templates replace 41 hardcoded f-strings in coordinator.py using placeholders
# Format: TRANS_KEY_ERROR_{CATEGORY} with translation_placeholders for dynamic values
TRANS_KEY_ERROR_NOT_FOUND: Final = "not_found"  # {entity_type} '{name}' not found
TRANS_KEY_ERROR_NOT_ASSIGNED: Final = (
    "not_assigned"  # {entity} not assigned to {assignee}
)
TRANS_KEY_ERROR_INSUFFICIENT_POINTS: Final = (
    "insufficient_points"  # {assignee} has {current}, needs {required}
)
TRANS_KEY_ERROR_ALREADY_CLAIMED: Final = "already_claimed"  # {entity} already claimed
TRANS_KEY_ERROR_INVALID_FREQUENCY: Final = (
    "invalid_frequency"  # Recurring frequency '{frequency}' is not valid
)
TRANS_KEY_ERROR_MISSING_FIELD: Final = (
    "missing_field"  # Required field '{field}' is missing from {entity}
)
TRANS_KEY_ERROR_INVALID_DATE: Final = "invalid_date"  # {field} date '{date}' is invalid
TRANS_KEY_ERROR_SHARED_CHORE_ASSIGNEE: Final = (
    "shared_chore_cannot_have_assignee"  # Cannot specify assignee for SHARED chore
)
TRANS_KEY_ERROR_INVALID_DATE_FORMAT: Final = (
    "invalid_date_format"  # Invalid date format
)
TRANS_KEY_ERROR_DATE_IN_PAST: Final = "date_in_past"  # Due date cannot be in the past
TRANS_KEY_ERROR_MISSING_CHORE: Final = "missing_chore"  # Must provide chore ID or name
TRANS_KEY_ERROR_MISSING_REWARD_IDENTIFIER: Final = (
    "missing_reward_identifier"  # Must provide reward_id or reward_name
)
TRANS_KEY_ERROR_CHORE_CLAIMED_BY_OTHER: Final = (
    "chore_claimed_by_other"  # Chore already claimed by another assignee
)
TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED: Final = (
    "chore_already_approved"  # Chore already approved, try again after reset period
)
TRANS_KEY_ERROR_CHORE_PENDING_CLAIM: Final = (
    "chore_pending_claim"  # Chore has a pending claim awaiting approval
)
TRANS_KEY_ERROR_CHORE_WAITING: Final = (
    "chore_waiting"  # Chore cannot be claimed before due window opens
)
TRANS_KEY_ERROR_CHORE_NOT_MY_TURN: Final = (
    "chore_not_my_turn"  # Chore is rotation-locked to another assignee
)
TRANS_KEY_ERROR_CHORE_MISSED_LOCKED: Final = (
    "chore_missed_locked"  # Chore was missed and is now locked
)
TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER: Final = "chore_completed_by_other"  # SHARED_FIRST chore already completed by another assignee
TRANS_KEY_ERROR_CHORE_NOT_FOUND: Final = (
    "chore_not_found"  # Chore with ID '{chore_id}' not found
)
TRANS_KEY_ERROR_MISSING_CHORE_IDENTIFIER: Final = (
    "missing_chore_identifier"  # Must provide chore_id or chore_name
)
# v0.5.0 Chore Logic: Rotation & claim restriction translations
TRANS_KEY_ERROR_ROTATION_MIN_ASSIGNEES: Final = (
    "rotation_min_assignees"  # Rotation chores require at least 2 assigned assignees
)
# Phase 3 Step 7 - Rotation management service error keys (v0.5.0)
TRANS_KEY_ERROR_NOT_ROTATION: Final = "not_rotation"  # Chore is not in rotation mode
TRANS_KEY_ERROR_ASSIGNEE_NOT_ASSIGNED: Final = (
    "assignee_not_assigned"  # Assignee not assigned to this chore
)
TRANS_KEY_ERROR_NO_ASSIGNED_ASSIGNEES: Final = (
    "no_assigned_assignees"  # No assignees assigned to chore
)
# Translation keys for non-existent services removed (advance_rotation, clear_rotation_override)

TRANS_KEY_ERROR_REWARD_NOT_FOUND: Final = (
    "reward_not_found"  # Reward with ID '{reward_id}' not found
)
TRANS_KEY_ERROR_DATA_RESET_CONFIRMATION_REQUIRED: Final = (
    "data_reset_confirmation_required"  # Must set confirm_destructive: true
)
TRANS_KEY_ERROR_DATA_RESET_ASSIGNEE_NOT_FOUND: Final = (
    "data_reset_assignee_not_found"  # Assignee '{assignee_name}' not found
)
TRANS_KEY_ERROR_DATA_RESET_ITEM_NOT_FOUND: Final = (
    "data_reset_item_not_found"  # {item_type} '{item_name}' not found
)
TRANS_KEY_ERROR_DATA_RESET_INVALID_SCOPE: Final = "data_reset_invalid_scope"  # Invalid scope '{scope}'. Must be: global, user, item_type, or item
TRANS_KEY_ERROR_DATA_RESET_INVALID_ITEM_TYPE: Final = "data_reset_invalid_item_type"  # Invalid item_type '{item_type}'. Must be: assignees, chores, etc.

# Translation Keys for Phase 2-4 Error Migration (Action Templating)
# These map to templated exceptions in translations/en.json using action labels
TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION: Final = "not_authorized_action"
TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL: Final = "not_authorized_action_global"
TRANS_KEY_ERROR_CALENDAR_CREATE_NOT_SUPPORTED: Final = "calendar_create_not_supported"
TRANS_KEY_ERROR_CALENDAR_DELETE_NOT_SUPPORTED: Final = "calendar_delete_not_supported"
TRANS_KEY_ERROR_CALENDAR_UPDATE_NOT_SUPPORTED: Final = "calendar_update_not_supported"

# Action identifiers for use with TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION template
# These values are passed directly as {action} placeholder in exception messages
ERROR_ACTION_CLAIM_CHORES: Final = "claim_chores"
ERROR_ACTION_APPROVE_CHORES: Final = "approve_chores"
ERROR_ACTION_DISAPPROVE_CHORES: Final = "disapprove_chores"
ERROR_ACTION_REDEEM_REWARDS: Final = "redeem_rewards"
ERROR_ACTION_APPROVE_REWARDS: Final = "approve_rewards"
ERROR_ACTION_DISAPPROVE_REWARDS: Final = "disapprove_rewards"
ERROR_ACTION_APPLY_PENALTIES: Final = "apply_penalties"
ERROR_ACTION_APPLY_BONUSES: Final = "apply_bonuses"
ERROR_ACTION_ADJUST_POINTS: Final = "adjust_points"
ERROR_ACTION_REMOVE_BADGES: Final = "remove_badges"

TRANS_KEY_ERROR_MSG_NO_ENTRY_FOUND: Final = "error_msg_no_entry_found"
TRANS_KEY_ERROR_SERVICE_TARGET_AMBIGUOUS: Final = "service_target_ambiguous"
TRANS_KEY_ERROR_SERVICE_TARGET_TITLE_NOT_FOUND: Final = "service_target_title_not_found"

# Config Flow & Options Flow Translation Keys (Phase 2b)
# Generic templates for validation errors across config/options flows
TRANS_KEY_CFOF_DUPLICATE_NAME: Final = "duplicate_name"  # Name already exists
TRANS_KEY_CFOF_CHORE_OPTIONS_REQUIRE_ASSIGNMENT: Final = (
    "chore_options_require_assignment"  # Workflow/gamification need chore_assignment
)
TRANS_KEY_CFOF_USAGE_REQUIRES_ASSIGNMENT_OR_APPROVAL: Final = (
    "usage_requires_assignment_or_approval"
)
TRANS_KEY_CFOF_APPROVAL_REQUIRES_ASSOCIATED_USERS: Final = (
    "approval_requires_associated_users"
)
TRANS_KEY_CFOF_ASSOCIATED_USERS_REQUIRE_APPROVAL: Final = (
    "associated_users_require_approval"
)


# Unknown States (Display Translation Keys)
TRANS_KEY_DISPLAY_UNKNOWN_CHALLENGE: Final = "display_unknown_challenge"
TRANS_KEY_DISPLAY_UNKNOWN_CHORE: Final = "display_unknown_chore"
TRANS_KEY_DISPLAY_UNKNOWN_ASSIGNEE: Final = "display_unknown_assignee"
TRANS_KEY_DISPLAY_UNKNOWN_REWARD: Final = "display_unknown_reward"
TRANS_KEY_DISPLAY_UNKNOWN_ENTITY: Final = "display_unknown_entity"

# Config Flow & Options Flow Error Keys
CFOP_ERROR_ACHIEVEMENT_NAME: Final = "name"
CFOP_ERROR_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
CFOP_ERROR_BASE: Final = "base"
CFOP_ERROR_CORRUPT_FILE: Final = "corrupt_file"
CFOP_ERROR_FILE_NOT_FOUND: Final = "file_not_found"
CFOP_ERROR_INVALID_JSON: Final = "invalid_json"
# Phase 6: Aligned with CFOF_BONUSES_INPUT_NAME = "name"
CFOP_ERROR_BONUS_NAME: Final = "name"
# Phase 6: Aligned with CFOF_CHORES_INPUT_NAME = "name"
CFOP_ERROR_CHORE_NAME: Final = "name"
CFOP_ERROR_USER_NAME: Final = "name"
CFOP_ERROR_DUE_DATE: Final = "due_date"
CFOP_ERROR_END_DATE: Final = "end_date"
# Phase 6: Aligned with CFOF_PENALTIES_INPUT_NAME = "name"
CFOP_ERROR_PENALTY_NAME: Final = "name"
# Phase 6: Aligned with CFOF_REWARDS_INPUT_NAME = "name"
CFOP_ERROR_REWARD_NAME: Final = "name"
CFOP_ERROR_REWARD_COST: Final = "cost"  # Phase 6: Aligned with CFOF_REWARDS_INPUT_COST
CFOP_ERROR_SELECT_CHORE_ID: Final = "selected_chore_id"
CFOP_ERROR_START_DATE: Final = "start_date"
CFOP_ERROR_CHORE_OPTIONS: Final = (
    "chore_options"  # Workflow/gamification without assignment
)
# Additional error keys used by config_flow.py abort() calls
CFOP_ERROR_INVALID_STRUCTURE: Final = "invalid_structure"
CFOP_ERROR_UNKNOWN: Final = "unknown"
# Phase 3 additions for config_flow remediation
CFOP_ERROR_EMPTY_JSON: Final = "empty_json"  # Empty JSON data provided
CFOP_ERROR_INVALID_SELECTION: Final = "invalid_selection"  # Invalid menu selection
CFOP_ERROR_OVERDUE_RESET_COMBO: Final = "overdue_handling_type"  # Invalid combination
# Phase 3c: System Settings Consolidation
CFOP_ERROR_UPDATE_INTERVAL: Final = "update_interval"
CFOP_ERROR_CALENDAR_SHOW_PERIOD: Final = "calendar_show_period"
CFOP_ERROR_RETENTION_DAILY: Final = "retention_daily"
CFOP_ERROR_RETENTION_WEEKLY: Final = "retention_weekly"
CFOP_ERROR_RETENTION_MONTHLY: Final = "retention_monthly"
CFOP_ERROR_RETENTION_YEARLY: Final = "retention_yearly"
CFOP_ERROR_POINTS_ADJUST_VALUES: Final = "points_adjust_values"
CFOP_ERROR_CHORE_POINTS: Final = "points"  # Invalid chore points value
# CFE-2026-001: Daily Multi validation error keys
CFOP_ERROR_DAILY_MULTI_RESET: Final = "recurring_frequency"  # Uses frequency field
CFOP_ERROR_DAILY_MULTI_USER_IDS: Final = (
    "assigned_user_ids"  # Uses assigned_user_ids field
)
CFOP_ERROR_DAILY_MULTI_DUE_DATE: Final = "due_date"  # Uses due_date field
CFOP_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE: Final = (
    "due_date"  # AT_DUE_DATE_* reset types require due date
)

# ------------------------------------------------------------------------------------------------
# Dashboard Helper Sensor Attributes (Phase 2b)
# JSON keys exposed in sensor.kc_<assignee>_ui_dashboard_helper attributes for dashboard consumption
# ------------------------------------------------------------------------------------------------
ATTR_DASHBOARD_CHORES: Final = "chores"
ATTR_DASHBOARD_REWARDS: Final = "rewards"
ATTR_DASHBOARD_BONUSES: Final = "bonuses"
ATTR_DASHBOARD_PENALTIES: Final = "penalties"
ATTR_DASHBOARD_ACHIEVEMENTS: Final = "achievements"
ATTR_DASHBOARD_CHALLENGES: Final = "challenges"
ATTR_DASHBOARD_BADGES: Final = "badges"
ATTR_DASHBOARD_PENDING_APPROVALS: Final = "pending_approvals"
ATTR_DASHBOARD_POINTS_BUTTONS: Final = "points_buttons"
ATTR_DASHBOARD_USER_NAME: Final = "user_name"
ATTR_DASHBOARD_UI_TRANSLATIONS: Final = "ui_translations"


# ------------------------------------------------------------------------------------------------
# Translation Keys
# ------------------------------------------------------------------------------------------------
# Global
TRANS_KEY_LABEL_BONUS: Final = "label_bonus"
TRANS_KEY_LABEL_CHALLENGE: Final = "label_challenge"
TRANS_KEY_LABEL_CHORE: Final = "label_chore"
TRANS_KEY_LABEL_ASSIGNEE: Final = "label_assignee"
TRANS_KEY_LABEL_PENALTY: Final = "label_penalty"
TRANS_KEY_LABEL_REWARD: Final = "label_reward"

# ConfigFlow & OptionsFlow Translation Keys
# Data Recovery
TRANS_KEY_CFOF_DATA_RECOVERY_SELECTION: Final = "data_recovery_selection"

# Backup Management
TRANS_KEY_CFOF_BACKUP_ACTIONS_MENU: Final = "backup_actions_menu"
TRANS_KEY_CFOF_SELECT_BACKUP_TO_DELETE: Final = "select_backup_to_delete"
TRANS_KEY_CFOF_SELECT_BACKUP_TO_RESTORE: Final = "select_backup_to_restore"

# Badge Fields
TRANS_KEY_CFOF_BADGE_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
TRANS_KEY_CFOF_BADGE_ASSOCIATED_ACHIEVEMENT: Final = "associated_achievement"
TRANS_KEY_CFOF_BADGE_AWARD_ITEMS: Final = "award_items"
TRANS_KEY_CFOF_BADGE_ASSOCIATED_CHALLENGE: Final = "associated_challenge"
TRANS_KEY_CFOF_BADGE_OCCASION_TYPE: Final = "occasion_type"
TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_END_DATE_REQUIRED: Final = "end_date_required"
TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE: Final = "reset_schedule"
TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY: Final = "recurring_frequency"
TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_START_DATE_REQUIRED: Final = "start_date_required"
TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT: Final = "custom_interval_unit"
TRANS_KEY_CFOF_BADGE_RESET_SCHEDULE_CUSTOM_INTERVAL: Final = "custom_interval"
TRANS_KEY_CFOF_BADGE_SELECTED_CHORES: Final = "selected_chores"
TRANS_KEY_CFOF_BADGE_TARGET_TYPE: Final = "target_type"
TRANS_KEY_CFOF_BADGE_TYPE: Final = "badge_type"
TRANS_KEY_CFOF_CHORE_MUST_BE_SELECTED: Final = "a_chore_must_be_selected"
TRANS_KEY_CFOF_DUE_DATE_IN_PAST: Final = "due_date_in_past"
TRANS_KEY_CFOF_DUPLICATE_ACHIEVEMENT: Final = "duplicate_achievement"
TRANS_KEY_CFOF_DUPLICATE_BADGE: Final = "duplicate_badge"
TRANS_KEY_CFOF_DUPLICATE_BONUS: Final = "duplicate_bonus"
TRANS_KEY_CFOF_DUPLICATE_CHORE: Final = "duplicate_chore"
TRANS_KEY_CFOF_DUPLICATE_ASSIGNEE: Final = "duplicate_assignee"
TRANS_KEY_CFOF_DUPLICATE_APPROVER: Final = "duplicate_approver"
TRANS_KEY_CFOF_DUPLICATE_PENALTY: Final = "duplicate_penalty"
TRANS_KEY_CFOF_DUPLICATE_REWARD: Final = "duplicate_reward"
TRANS_KEY_CFOF_END_DATE_IN_PAST: Final = "end_date_in_past"
# Config Flow abort reason translation keys (for async_abort calls)
TRANS_KEY_CFOP_ERROR_FILE_NOT_FOUND: Final = "file_not_found"
TRANS_KEY_CFOP_ERROR_CORRUPT_FILE: Final = "corrupt_file"
TRANS_KEY_CFOP_ERROR_INVALID_STRUCTURE: Final = "invalid_structure"
TRANS_KEY_CFOP_ERROR_UNKNOWN: Final = "unknown"
TRANS_KEY_ERROR_SINGLE_INSTANCE: Final = "single_instance_allowed"
TRANS_KEY_CFOF_ERROR_AWARD_POINTS_MINIMUM: Final = "error_award_points_minimum"
TRANS_KEY_CFOF_ERROR_AWARD_INVALID_MULTIPLIER: Final = "error_award_invalid_multiplier"
TRANS_KEY_CFOF_ERROR_AWARD_INVALID_AWARD_ITEM: Final = "invalid_award_item_selected"
TRANS_KEY_CFOF_ERROR_BADGE_ACHIEVEMENT_REQUIRED: Final = (
    "error_badge_achievement_required"
)
TRANS_KEY_CFOF_ERROR_BADGE_CHALLENGE_REQUIRED: Final = "error_badge_challenge_required"
TRANS_KEY_CFOF_ERROR_BADGE_OCCASION_TYPE_REQUIRED: Final = (
    "error_badge_occasion_type_required"
)
TRANS_KEY_CFOF_BADGE_REQUIRES_ASSIGNMENT: Final = "badge_requires_assignment"
# CFE-2026-001 Error Keys
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET: Final = (
    "error_daily_multi_requires_compatible_reset"
)
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_ASSIGNEES: Final = (
    "error_daily_multi_independent_multi_assignees"
)
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_REQUIRED: Final = (
    "error_daily_multi_times_required"
)
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_INVALID_FORMAT: Final = (
    "error_daily_multi_times_invalid_format"
)
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_TOO_FEW: Final = (
    "error_daily_multi_times_too_few"
)
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_TIMES_TOO_MANY: Final = (
    "error_daily_multi_times_too_many"
)
# v0.5.0: V-05 validation error - steal mechanic compatibility
TRANS_KEY_CFOF_ERROR_ALLOW_STEAL_INCOMPATIBLE: Final = "error_allow_steal_incompatible"  # V-05: steal requires rotation + at_midnight_once + due_date
TRANS_KEY_CFOF_ERROR_DAILY_MULTI_DUE_DATE_REQUIRED: Final = (
    "error_daily_multi_due_date_required"
)
TRANS_KEY_CFOF_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE: Final = (
    "error_at_due_date_reset_requires_due_date"
)
# PKAD-2026-001 Error Keys
TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID: Final = (
    "error_per_assignee_applicable_days_invalid"
)
TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_DAILY_MULTI_TIMES_INVALID: Final = (
    "error_per_assignee_daily_multi_times_invalid"
)
TRANS_KEY_CFOF_INVALID_ACHIEVEMENT: Final = "invalid_achievement"
TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_COUNT: Final = "invalid_achievement_count"
TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_NAME: Final = "invalid_achievement_name"
TRANS_KEY_CFOF_INVALID_ACTION: Final = "invalid_action"
TRANS_KEY_CFOF_INVALID_BADGE: Final = "invalid_badge"
TRANS_KEY_CFOF_INVALID_BADGE_COUNT: Final = "invalid_badge_count"
TRANS_KEY_CFOF_INVALID_BADGE_NAME: Final = "invalid_badge_name"
TRANS_KEY_CFOF_INVALID_BADGE_TARGET_THRESHOLD_VALUE = (
    "invalid_badge_target_threshold_value"
)
TRANS_KEY_CFOF_INVALID_BADGE_TYPE: Final = "invalid_badge_type"
TRANS_KEY_CFOF_INVALID_MAINTENANCE_RULES: Final = "invalid_maintenance_rules"
TRANS_KEY_CFOF_TARGET_THRESHOLD_REQUIRED: Final = "target_threshold_required"
TRANS_KEY_CFOF_END_DATE_BEFORE_START: Final = "end_date_before_start_date"
TRANS_KEY_CFOF_INVALID_BONUS: Final = "invalid_bonus"
TRANS_KEY_CFOF_INVALID_BONUS_COUNT: Final = "invalid_bonus_count"
TRANS_KEY_CFOF_INVALID_BONUS_NAME: Final = "invalid_bonus_name"
TRANS_KEY_CFOF_INVALID_CHALLENGE: Final = "invalid_challenge"
TRANS_KEY_CFOF_INVALID_CHALLENGE_COUNT: Final = "invalid_challenge_count"
TRANS_KEY_CFOF_INVALID_CHALLENGE_NAME: Final = "invalid_challenge_name"
TRANS_KEY_CFOF_CHALLENGE_NAME_REQUIRED: Final = "err_name_required"
TRANS_KEY_CFOF_CHALLENGE_NAME_DUPLICATE: Final = "err_name_duplicate"
TRANS_KEY_CFOF_CHALLENGE_DATES_REQUIRED: Final = "err_dates_required"
TRANS_KEY_CFOF_CHALLENGE_END_BEFORE_START: Final = "err_end_before_start"
TRANS_KEY_CFOF_CHALLENGE_INVALID_DATE: Final = "err_invalid_date"
TRANS_KEY_CFOF_CHALLENGE_TARGET_INVALID: Final = "err_target_invalid"
TRANS_KEY_CFOF_CHALLENGE_POINTS_NEGATIVE: Final = "err_points_negative"
TRANS_KEY_CFOF_CHALLENGE_POINTS_INVALID: Final = "err_points_invalid"
TRANS_KEY_CFOF_INVALID_POINTS: Final = "invalid_points"  # Chore points must be >= 0
TRANS_KEY_CFOF_INVALID_CHORE: Final = "invalid_chore"
TRANS_KEY_CFOF_INVALID_CHORE_COUNT: Final = "invalid_chore_count"
TRANS_KEY_CFOF_INVALID_CHORE_NAME: Final = "invalid_chore_name"
TRANS_KEY_CFOF_INVALID_OVERDUE_RESET_COMBINATION: Final = (
    "invalid_overdue_reset_combination"
)
TRANS_KEY_CFOF_NO_ASSIGNEES_ASSIGNED: Final = "no_assignees_assigned"
TRANS_KEY_CFOF_ACHIEVEMENT_NO_ASSIGNEES_ASSIGNED: Final = (
    "achievement_no_assignees_assigned"
)
TRANS_KEY_CFOF_CHALLENGE_NO_ASSIGNEES_ASSIGNED: Final = (
    "challenge_no_assignees_assigned"
)
TRANS_KEY_CFOF_INVALID_DUE_DATE: Final = "invalid_due_date"
TRANS_KEY_CFOF_DATE_REQUIRED_FOR_FREQUENCY: Final = "date_required_for_frequency"
TRANS_KEY_CFOF_INVALID_ENTITY: Final = "invalid_entity"
TRANS_KEY_CFOF_INVALID_ASSIGNEE: Final = "invalid_assignee"
TRANS_KEY_CFOF_INVALID_ASSIGNEE_COUNT: Final = "invalid_assignee_count"
TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME: Final = "invalid_assignee_name"
TRANS_KEY_CFOF_INVALID_APPROVER: Final = "invalid_approver"
TRANS_KEY_CFOF_INVALID_USER_COUNT: Final = "invalid_user_count"
TRANS_KEY_CFOF_INVALID_APPROVER_NAME: Final = "invalid_approver_name"

# Approver Chore Capability Translation Keys

TRANS_KEY_CFOF_INVALID_PENALTY: Final = "invalid_penalty"
TRANS_KEY_CFOF_INVALID_PENALTY_COUNT: Final = "invalid_penalty_count"
TRANS_KEY_CFOF_INVALID_PENALTY_NAME: Final = "invalid_penalty_name"
TRANS_KEY_CFOF_INVALID_REWARD: Final = "invalid_reward"
TRANS_KEY_CFOF_INVALID_REWARD_COUNT: Final = "invalid_reward_count"
TRANS_KEY_CFOF_INVALID_REWARD_NAME: Final = "invalid_reward_name"
TRANS_KEY_CFOF_INVALID_REWARD_COST: Final = (
    "invalid_reward_cost"  # Reward cost must be >= 0
)
TRANS_KEY_CFOF_INVALID_SELECTION: Final = "invalid_selection"
TRANS_KEY_CFOF_POINTS_LABEL_REQUIRED: Final = "points_label_required"
TRANS_KEY_CFOF_MAIN_MENU: Final = "main_menu"
TRANS_KEY_CFOF_MANAGE_ACTIONS: Final = "manage_actions"
ABORT_KEY_NO_ENTITY_TEMPLATE: Final = "no_{}"
TRANS_KEY_CFOF_START_DATE_IN_PAST: Final = "start_date_in_past"

# Config-flow dynamic summary labels (intentionally not HA translation keys)
SUMMARY_LABEL_ACHIEVEMENTS: Final = "Achievements: "
SUMMARY_LABEL_BADGES: Final = "Badges: "
SUMMARY_LABEL_BONUSES: Final = "Bonuses: "
SUMMARY_LABEL_CHALLENGES: Final = "Challenges: "
SUMMARY_LABEL_CHORES: Final = "Chores: "
SUMMARY_LABEL_ASSIGNMENT_CAPABLE_USERS: Final = "Assignment-capable users: "
SUMMARY_LABEL_APPROVAL_CAPABLE_USERS: Final = "Approval-capable users: "
SUMMARY_LABEL_PENALTIES: Final = "Penalties: "
SUMMARY_LABEL_REWARDS: Final = "Rewards: "

# Phase 3c: System Settings Translation Keys
TRANS_KEY_CFOF_INVALID_UPDATE_INTERVAL: Final = "invalid_update_interval"
TRANS_KEY_CFOF_INVALID_CALENDAR_SHOW_PERIOD: Final = "invalid_calendar_show_period"
TRANS_KEY_CFOF_INVALID_RETENTION_PERIOD: Final = "invalid_retention_period"
TRANS_KEY_CFOF_INVALID_POINTS_ADJUST_VALUES: Final = "invalid_points_adjust_values"

# Dashboard Generator Translation Keys (Phase 4)
TRANS_KEY_CFOF_DASHBOARD_ASSIGNEE_SELECTION: Final = "dashboard_assignee_selection"
TRANS_KEY_CFOF_DASHBOARD_EXISTS: Final = "dashboard_exists"
TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_ERROR: Final = "dashboard_template_error"
TRANS_KEY_CFOF_DASHBOARD_RENDER_ERROR: Final = "dashboard_render_error"
TRANS_KEY_CFOF_DASHBOARD_SAVE_ERROR: Final = "dashboard_save_error"
TRANS_KEY_CFOF_DASHBOARD_NO_NAME: Final = "dashboard_no_name"
TRANS_KEY_CFOF_DASHBOARD_ACTION: Final = "dashboard_action"
TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_PROFILE: Final = "dashboard_template_profile"
TRANS_KEY_CFOF_DASHBOARD_UPDATE_SELECTION: Final = "dashboard_update_selection"
TRANS_KEY_CFOF_DASHBOARD_NO_DASHBOARDS: Final = "dashboard_no_dashboards"
TRANS_KEY_CFOF_DASHBOARD_RELEASE_INCOMPATIBLE: Final = "dashboard_release_incompatible"
TRANS_KEY_CFOF_DASHBOARD_ADMIN_MODE: Final = "dashboard_admin_mode"
TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_GLOBAL: Final = (
    "dashboard_admin_template_global"
)
TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_PER_ASSIGNEE: Final = (
    "dashboard_admin_template_per_assignee"
)
TRANS_KEY_CFOF_DASHBOARD_ADMIN_VIEW_VISIBILITY: Final = (
    "dashboard_admin_view_visibility"
)
TRANS_KEY_CFOF_DASHBOARD_RELEASE_SELECTION: Final = "dashboard_release_selection"
TRANS_KEY_CFOF_DASHBOARD_NO_ASSIGNEES_WITHOUT_ADMIN: Final = (
    "dashboard_no_assignees_no_admin"
)
TRANS_KEY_CFOF_DASHBOARD_ADMIN_GLOBAL_TEMPLATE_REQUIRED: Final = (
    "dashboard_admin_global_template_required"
)
TRANS_KEY_CFOF_DASHBOARD_ADMIN_PER_ASSIGNEE_TEMPLATE_REQUIRED: Final = (
    "dashboard_admin_per_assignee_template_required"
)
TRANS_KEY_CFOF_DASHBOARD_ADMIN_PER_ASSIGNEE_NEEDS_ASSIGNEES: Final = (
    "dashboard_admin_per_assignee_needs_assignees"
)

# Flow Helpers Translation Keys
TRANS_KEY_FLOW_HELPERS_APPLICABLE_DAYS: Final = "applicable_days"
TRANS_KEY_FLOW_HELPERS_APPROVAL_RESET_PENDING_CLAIM_ACTION: Final = (
    "approval_reset_pending_claim_action"
)
TRANS_KEY_FLOW_HELPERS_APPROVAL_RESET_TYPE: Final = "approval_reset_type"
TRANS_KEY_FLOW_HELPERS_ASSIGNED_USER_IDS: Final = "assigned_user_ids"
TRANS_KEY_FLOW_HELPERS_CHORE_NOTIFICATIONS: Final = "chore_notifications"
TRANS_KEY_FLOW_HELPERS_COMPLETION_CRITERIA: Final = "completion_criteria"
TRANS_KEY_FLOW_HELPERS_ASSOCIATED_USER_IDS: Final = "associated_user_ids"
TRANS_KEY_FLOW_HELPERS_CUSTOM_INTERVAL_UNIT: Final = "custom_interval_unit"
TRANS_KEY_FLOW_HELPERS_OVERDUE_HANDLING_TYPE: Final = "overdue_handling_type"
TRANS_KEY_FLOW_HELPERS_RECURRING_FREQUENCY: Final = "recurring_frequency"

# Sensor Translation Keys
TRANS_KEY_SENSOR_ACHIEVEMENT_PROGRESS_SENSOR: Final = (
    "assignee_achievement_progress_sensor"
)
TRANS_KEY_SENSOR_ACHIEVEMENT_STATE_SENSOR: Final = "system_achievement_sensor"
TRANS_KEY_SENSOR_BADGE_SENSOR: Final = "system_badge_sensor"
TRANS_KEY_SENSOR_ASSIGNEE_BADGE_PROGRESS_SENSOR: Final = (
    "assignee_badge_progress_sensor"
)
TRANS_KEY_SENSOR_BONUS_APPLIES_SENSOR: Final = "assignee_bonus_applied_sensor"
TRANS_KEY_SENSOR_CHALLENGE_PROGRESS_SENSOR: Final = "assignee_challenge_progress_sensor"
TRANS_KEY_SENSOR_CHALLENGE_STATE_SENSOR: Final = "system_challenge_sensor"
TRANS_KEY_SENSOR_CHORES_COMPLETED_DAILY_SENSOR: Final = (
    "system_chore_approvals_daily_sensor"
)
TRANS_KEY_SENSOR_CHORES_COMPLETED_MONTHLY_SENSOR: Final = (
    "system_chore_approvals_monthly_sensor"
)
TRANS_KEY_SENSOR_CHORES_COMPLETED_TOTAL_SENSOR: Final = "system_chore_approvals_sensor"
TRANS_KEY_SENSOR_CHORES_COMPLETED_WEEKLY_SENSOR: Final = (
    "system_chore_approvals_weekly_sensor"
)
TRANS_KEY_SENSOR_CHORES_SENSOR: Final = "assignee_chores_sensor"
TRANS_KEY_SENSOR_CHORE_STATUS_SENSOR: Final = "assignee_chore_status_sensor"
TRANS_KEY_SENSOR_ASSIGNEE_HIGHEST_STREAK_SENSOR: Final = "assignee_chore_streak_sensor"
TRANS_KEY_SENSOR_ASSIGNEE_MAX_POINTS_EVER_SENSOR: Final = (
    "assignee_points_max_ever_sensor"
)
TRANS_KEY_SENSOR_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR: Final = (
    "assignee_points_earned_daily_sensor"
)
TRANS_KEY_SENSOR_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR: Final = (
    "assignee_points_earned_monthly_sensor"
)
TRANS_KEY_SENSOR_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR: Final = (
    "assignee_points_earned_weekly_sensor"
)
TRANS_KEY_SENSOR_ASSIGNEE_POINTS_SENSOR: Final = "assignee_points_sensor"
TRANS_KEY_SENSOR_ASSIGNEE_BADGES_SENSOR: Final = "assignee_badges_sensor"
TRANS_KEY_SENSOR_PENALTY_APPLIES_SENSOR: Final = "assignee_penalty_applied_sensor"
TRANS_KEY_SENSOR_PENDING_CHORES_APPROVALS_SENSOR: Final = (
    "system_chores_pending_approval_sensor"
)
TRANS_KEY_SENSOR_PENDING_REWARDS_APPROVALS_SENSOR: Final = (
    "system_rewards_pending_approval_sensor"
)
TRANS_KEY_SENSOR_REWARD_STATUS_SENSOR: Final = "assignee_reward_status_sensor"
TRANS_KEY_SENSOR_SHARED_CHORE_GLOBAL_STATUS_SENSOR: Final = (
    "system_chore_shared_state_sensor"
)
TRANS_KEY_SENSOR_DASHBOARD_TRANSLATION: Final = "system_dashboard_translation_sensor"
TRANS_KEY_SENSOR_DASHBOARD_HELPER: Final = "assignee_dashboard_helper_sensor"


# Sensor Attributes Translation Keys
TRANS_KEY_SENSOR_ATTR_ACHIEVEMENT_NAME: Final = "achievement_name"
TRANS_KEY_SENSOR_ATTR_BADGE_NAME: Final = "badge_name"
TRANS_KEY_SENSOR_ATTR_BONUS_NAME: Final = "bonus_name"
TRANS_KEY_SENSOR_ATTR_CHALLENGE_NAME: Final = "challenge_name"
TRANS_KEY_SENSOR_ATTR_CHORE_NAME: Final = "chore_name"
TRANS_KEY_SENSOR_ATTR_ASSIGNEE_NAME: Final = "user_name"
TRANS_KEY_SENSOR_ATTR_PENALTY_NAME: Final = "penalty_name"
TRANS_KEY_SENSOR_ATTR_POINTS: Final = "points"
TRANS_KEY_SENSOR_ATTR_REWARD_NAME: Final = "reward_name"

# DateTime Translation Keys
TRANS_KEY_DATETIME_DATE_HELPER: Final = "assignee_dashboard_helper_datetime_picker"

# Select Translation Keys
TRANS_KEY_SELECT_BASE: Final = "kc_select_base"
TRANS_KEY_SELECT_BONUSES: Final = "system_bonuses_select"
TRANS_KEY_SELECT_CHORES: Final = "system_chores_select"
TRANS_KEY_SELECT_CHORES_ASSIGNEE: Final = "assignee_dashboard_helper_chores_select"
TRANS_KEY_SELECT_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE: Final = (
    "system_dashboard_admin_assignee_select"
)
TRANS_KEY_SELECT_PENALTIES: Final = "system_penalties_select"
TRANS_KEY_SELECT_REWARDS: Final = "system_rewards_select"

# Select Labels
TRANS_KEY_SELECT_LABEL_ALL_BONUSES: Final = "select_label_all_bonuses"
TRANS_KEY_SELECT_LABEL_ALL_CHORES: Final = "select_label_all_chores"
TRANS_KEY_SELECT_LABEL_ALL_PENALTIES: Final = "select_label_all_penalties"
TRANS_KEY_SELECT_LABEL_ALL_REWARDS: Final = "select_label_all_rewards"

# Button Translation Keys
TRANS_KEY_BUTTON_APPROVE_CHORE_BUTTON: Final = "approver_chore_approve_button"
TRANS_KEY_BUTTON_APPROVE_REWARD_BUTTON: Final = "approver_reward_approve_button"
TRANS_KEY_BUTTON_BONUS_BUTTON: Final = "approver_bonus_apply_button"
TRANS_KEY_BUTTON_CLAIM_CHORE_BUTTON: Final = "assignee_chore_claim_button"
TRANS_KEY_BUTTON_CLAIM_REWARD_BUTTON: Final = "assignee_reward_redeem_button"
TRANS_KEY_BUTTON_DISAPPROVE_CHORE_BUTTON: Final = "approver_chore_disapprove_button"
TRANS_KEY_BUTTON_DISAPPROVE_REWARD_BUTTON: Final = "approver_reward_disapprove_button"
TRANS_KEY_BUTTON_MANUAL_ADJUSTMENT_BUTTON: Final = "approver_points_adjust_button"
TRANS_KEY_BUTTON_PENALTY_BUTTON: Final = "approver_penalty_apply_button"


# Button Attributes Translation Keys
TRANS_KEY_BUTTON_ATTR_BONUS_NAME: Final = "bonus_name"
TRANS_KEY_BUTTON_ATTR_CHORE_NAME: Final = "chore_name"
TRANS_KEY_BUTTON_ATTR_DELTA: Final = "delta"
TRANS_KEY_BUTTON_ATTR_ASSIGNEE_NAME: Final = "user_name"
TRANS_KEY_BUTTON_ATTR_PENALTY_NAME: Final = "penalty_name"
TRANS_KEY_BUTTON_ATTR_POINTS_LABEL: Final = "points_label"
TRANS_KEY_BUTTON_ATTR_REWARD_NAME: Final = "reward_name"

# Calendar Attributes Translation Keys
TRANS_KEY_CALENDAR_NAME: Final = "assignee_schedule_calendar"

# FMT Errors Translation Keys

# ------------------------------------------------------------------------------------------------
# Notification Keys
# ------------------------------------------------------------------------------------------------
NOTIFY_ACTION = "action"
NOTIFY_ACTIONS = "actions"
NOTIFY_CREATE = "create"
NOTIFY_DATA = "data"
NOTIFY_DEFAULT_APPROVER_NAME = "Approver"
NOTIFY_DOMAIN = "notify"
NOTIFY_MESSAGE = "message"
NOTIFY_NOTIFICATION_ID = "notification_id"
NOTIFY_APPROVER_NAME = "approver_name"
NOTIFY_PERSISTENT_NOTIFICATION = "persistent_notification"
NOTIFY_TITLE = "title"

# Notification Tag System (v0.5.0+)
# Tags enable smart notification replacement: same tag = replace in-place, no stacking
NOTIFY_TAG = "tag"
NOTIFY_TAG_PREFIX = "choreops"
NOTIFY_TAG_TYPE_PENDING = "pending"  # Pending chore approvals
NOTIFY_TAG_TYPE_REWARDS = "rewards"  # Reward claims pending
NOTIFY_TAG_TYPE_SYSTEM = "system"  # System notifications (achievements, etc.)
NOTIFY_TAG_TYPE_STATUS = "status"  # Status update replacements
NOTIFY_TAG_TYPE_OVERDUE = "overdue"  # Overdue chore notifications
NOTIFY_TAG_TYPE_DUE_WINDOW = "due_window"  # Due window chore notifications


# ------------------------------------------------------------------------------------------------
# List Keys
# ------------------------------------------------------------------------------------------------

# Recurring Frequency
CHORE_FREQUENCY_OPTIONS = [
    FREQUENCY_NONE,
    FREQUENCY_DAILY,
    FREQUENCY_DAILY_MULTI,
    FREQUENCY_WEEKLY,
    PERIOD_WEEK_END,
    FREQUENCY_BIWEEKLY,
    FREQUENCY_MONTHLY,
    PERIOD_MONTH_END,
    FREQUENCY_QUARTERLY,
    PERIOD_QUARTER_END,
    FREQUENCY_YEARLY,
    PERIOD_YEAR_END,
    FREQUENCY_CUSTOM,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
]

# Frequency options for config flow (excludes DAILY_MULTI which requires helper step)
# DAILY_MULTI is available in Options flow after initial setup
CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW = [
    FREQUENCY_NONE,
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
    PERIOD_WEEK_END,
    FREQUENCY_BIWEEKLY,
    FREQUENCY_MONTHLY,
    PERIOD_MONTH_END,
    FREQUENCY_QUARTERLY,
    PERIOD_QUARTER_END,
    FREQUENCY_YEARLY,
    PERIOD_YEAR_END,
    FREQUENCY_CUSTOM,
    FREQUENCY_CUSTOM_FROM_COMPLETE,
]

# Weekday Options
WEEKDAY_OPTIONS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}

# Weekday name to integer mapping (0=Monday, 6=Sunday)
# Used for converting UI selections to RecurrenceEngine-compatible format
WEEKDAY_NAME_TO_INT: Final[dict[str, int]] = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

# Badge Type to Options Flow Add Step Name Mapping
OPTIONS_FLOW_ADD_STEP: Final = {
    BADGE_TYPE_ACHIEVEMENT_LINKED: OPTIONS_FLOW_STEP_ADD_BADGE_ACHIEVEMENT,
    BADGE_TYPE_CHALLENGE_LINKED: OPTIONS_FLOW_STEP_ADD_BADGE_CHALLENGE,
    BADGE_TYPE_CUMULATIVE: OPTIONS_FLOW_STEP_ADD_BADGE_CUMULATIVE,
    BADGE_TYPE_DAILY: OPTIONS_FLOW_STEP_ADD_BADGE_DAILY,
    BADGE_TYPE_PERIODIC: OPTIONS_FLOW_STEP_ADD_BADGE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION: OPTIONS_FLOW_STEP_ADD_BADGE_SPECIAL,
}

# Badge Type to Options Flow Edit Step Name Mapping
OPTIONS_FLOW_EDIT_STEP: Final = {
    BADGE_TYPE_ACHIEVEMENT_LINKED: OPTIONS_FLOW_STEP_EDIT_BADGE_ACHIEVEMENT,
    BADGE_TYPE_CHALLENGE_LINKED: OPTIONS_FLOW_STEP_EDIT_BADGE_CHALLENGE,
    BADGE_TYPE_CUMULATIVE: OPTIONS_FLOW_STEP_EDIT_BADGE_CUMULATIVE,
    BADGE_TYPE_DAILY: OPTIONS_FLOW_STEP_EDIT_BADGE_DAILY,
    BADGE_TYPE_PERIODIC: OPTIONS_FLOW_STEP_EDIT_BADGE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION: OPTIONS_FLOW_STEP_EDIT_BADGE_SPECIAL,
}

# Badge Type to Config Flow Step Name Mapping
CONFIG_FLOW_STEP = {
    BADGE_TYPE_ACHIEVEMENT_LINKED: CONFIG_FLOW_STEP_ACHIEVEMENTS,
    BADGE_TYPE_CHALLENGE_LINKED: CONFIG_FLOW_STEP_CHALLENGES,
    BADGE_TYPE_CUMULATIVE: CONFIG_FLOW_STEP_BADGES,
    BADGE_TYPE_DAILY: CONFIG_FLOW_STEP_BADGES,
    BADGE_TYPE_PERIODIC: CONFIG_FLOW_STEP_BADGES,
    BADGE_TYPE_SPECIAL_OCCASION: CONFIG_FLOW_STEP_BADGES,
}

AWARD_ITEMS_KEY_POINTS = "points"
AWARD_ITEMS_KEY_POINTS_MULTIPLIER = "multiplier"
AWARD_ITEMS_KEY_REWARDS = "rewards"
AWARD_ITEMS_KEY_BONUSES = "bonuses"

AWARD_ITEMS_LABEL_POINTS = "POINTS:"
AWARD_ITEMS_LABEL_POINTS_MULTIPLIER = "POINTS MULTIPLIER:"
AWARD_ITEMS_LABEL_REWARD = "REWARD:"
AWARD_ITEMS_LABEL_BONUS = "BONUS:"
AWARD_ITEMS_LABEL_PENALTY = "PENALTY:"

AWARD_ITEMS_PREFIX_REWARD = "reward:"
AWARD_ITEMS_PREFIX_BONUS = "bonus:"
AWARD_ITEMS_PREFIX_PENALTY = "penalty:"

# DEPRECATED - Badge Threshold Type

# Badge Cumulative Reset Period


# Badge Periodic Reset Schedule
BADGE_RESET_SCHEDULE_OPTIONS = [
    {"value": FREQUENCY_NONE, "label": "None"},
    {"value": FREQUENCY_DAILY, "label": "Daily"},
    {"value": FREQUENCY_WEEKLY, "label": "Weekly"},
    {"value": FREQUENCY_BIWEEKLY, "label": "Biweekly"},
    {"value": FREQUENCY_MONTHLY, "label": "Monthly"},
    {"value": FREQUENCY_QUARTERLY, "label": "Quarterly"},
    {"value": FREQUENCY_YEARLY, "label": "Yearly"},
    {"value": PERIOD_WEEK_END, "label": "Week-End"},
    {"value": PERIOD_MONTH_END, "label": "Month-End"},
    {"value": PERIOD_QUARTER_END, "label": "Quarter-End"},
    {"value": PERIOD_YEAR_END, "label": "Year-End"},
    {"value": FREQUENCY_CUSTOM, "label": "Custom (define period below)"},
]

# Badge target handler constants for handler mapping keys

# Badge Special Occasion Types
OCCASION_TYPE_OPTIONS = [OCCASION_BIRTHDAY, OCCASION_HOLIDAY, FREQUENCY_CUSTOM]

# Lowercase literals required by Home Assistant SelectSelector schema
TARGET_TYPE_OPTIONS = [
    {"value": BADGE_TARGET_THRESHOLD_TYPE_POINTS, "label": "Points Earned"},
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_POINTS_CHORES,
        "label": "Points Earned (From Chores)",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_CHORE_COUNT,
        "label": "Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES,
        "label": "Days Selected Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_CHORES,
        "label": "Days 80% of Selected Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_CHORES_NO_OVERDUE,
        "label": "Days Selected Chores Completed (No Overdue)",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES,
        "label": "Days Selected Due Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_80PCT_DUE_CHORES,
        "label": "Days 80% of Selected Due Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_SELECTED_DUE_CHORES_NO_OVERDUE,
        "label": "Days Selected Due Chores Completed (No Overdue)",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_3_CHORES,
        "label": "Days Minimum 3 Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_5_CHORES,
        "label": "Days Minimum 5 Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_DAYS_MIN_7_CHORES,
        "label": "Days Minimum 7 Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES,
        "label": "Streak: Selected Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_CHORES,
        "label": "Streak: 80% of Selected Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_CHORES_NO_OVERDUE,
        "label": "Streak: Selected Chores Completed (No Overdue)",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_STREAK_80PCT_DUE_CHORES,
        "label": "Streak: 80% of Selected Due Chores Completed",
    },
    {
        "value": BADGE_TARGET_THRESHOLD_TYPE_STREAK_SELECTED_DUE_CHORES_NO_OVERDUE,
        "label": "Streak: Selected Due Chores Completed (No Overdue)",
    },
]


# Badge types for include_target component
INCLUDE_TARGET_BADGE_TYPES = [
    BADGE_TYPE_CUMULATIVE,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_DAILY,
    BADGE_TYPE_SPECIAL_OCCASION,
]

# Badge types for include_special_occasion component
INCLUDE_SPECIAL_OCCASION_BADGE_TYPES = [
    BADGE_TYPE_SPECIAL_OCCASION,
]

# Badge types for include_achievement_linked component
INCLUDE_ACHIEVEMENT_LINKED_BADGE_TYPES = [
    BADGE_TYPE_ACHIEVEMENT_LINKED,
]

# Badge types for include_challenge_linked component
INCLUDE_CHALLENGE_LINKED_BADGE_TYPES = [
    BADGE_TYPE_CHALLENGE_LINKED,
]

# Badge types for include_tracked_chores component
INCLUDE_TRACKED_CHORES_BADGE_TYPES = [BADGE_TYPE_PERIODIC, BADGE_TYPE_DAILY]

# Badge types for include_assigned_user_ids component
INCLUDE_ASSIGNED_USER_IDS_BADGE_TYPES = [
    BADGE_TYPE_CUMULATIVE,
    BADGE_TYPE_DAILY,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION,
]

# Badge types for include_awards component
INCLUDE_AWARDS_BADGE_TYPES = [
    BADGE_TYPE_CUMULATIVE,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_DAILY,
    BADGE_TYPE_SPECIAL_OCCASION,
    BADGE_TYPE_ACHIEVEMENT_LINKED,
    BADGE_TYPE_CHALLENGE_LINKED,
]

# Badge types for include_award-penalties component
INCLUDE_PENALTIES_BADGE_TYPES = [
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_DAILY,
]


# Badge types for include_reset_schedule component
INCLUDE_RESET_SCHEDULE_BADGE_TYPES = [
    BADGE_TYPE_CUMULATIVE,
    BADGE_TYPE_PERIODIC,
    BADGE_TYPE_SPECIAL_OCCASION,
    BADGE_TYPE_DAILY,
]

# Achievement Type Options
ACHIEVEMENT_TYPE_OPTIONS = [
    {"value": ACHIEVEMENT_TYPE_STREAK, "label": "Chore Streak"},
    {"value": ACHIEVEMENT_TYPE_TOTAL, "label": "Chore Total"},
    {"value": ACHIEVEMENT_TYPE_DAILY_MIN, "label": "Daily Minimum Chores"},
]

# Challenge Type Options
CHALLENGE_TYPE_OPTIONS = [
    {"value": CHALLENGE_TYPE_DAILY_MIN, "label": "Minimum Chores per Day"},
    {
        "value": CHALLENGE_TYPE_TOTAL_WITHIN_WINDOW,
        "label": "Total Chores within Period",
    },
]

# Reward Options


# ================================================================================================
# DEPRECATED CONSTANTS (Currently active in existing version, planned for future refactoring)
# These reference CONSTANTS that are actively used in production code.
# They are marked for eventual replacement when underlying features are refactored.
# Must be named as _DEPRECATED and organized in the dedicates section at the bottom of const.py.
# DO NOT DELETE - would break installations without migration.
# ================================================================================================

# Not in use at this time

# ================================================================================================
# LEGACY CONSTANTS for one-time data conversion only (migration support)
# These reference constants that are replaced during migration.
# After migration completes, these keys NO LONGER EXIST in storage.
# Remove in KC-vNext after migration support is dropped.
# Must be named as _LEGACY and organized in the dedicates section at the bottom of const.py.
# DO NOT DELETE - would break migrations for upgrading users.
# ================================================================================================
# Legacy constants are defined in `migration_pre_v50_constants.py` and re-exported here.
