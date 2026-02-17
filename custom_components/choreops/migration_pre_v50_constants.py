"""Legacy constants used for migration compatibility only.

These constants are intentionally isolated from `const.py` so production
runtime constants stay focused on active schema/runtime behavior.
"""

from typing import Final

DATA_KID_POINT_STATS_AVG_PER_DAY_WEEK_LEGACY: Final = (
    "avg_points_per_day_week"  # DERIVED from weekly period
)

DATA_KID_POINT_STATS_AVG_PER_DAY_MONTH_LEGACY: Final = (
    "avg_points_per_day_month"  # DERIVED from monthly period
)

DATA_KID_POINT_STATS_AVG_PER_CHORE_LEGACY: Final = (
    "avg_points_per_chore"  # DERIVED from all-time stats
)

DATA_KID_POINT_STATS_HIGHEST_BALANCE_ALL_TIME_LEGACY: Final = (
    "highest_balance_all_time"  # Use periods.all_time.all_time.highest_balance
)

DATA_KID_POINTS_EARNED_ALL_TIME_LEGACY: Final = (
    "points_earned_all_time"  # Use periods.all_time.all_time.points_earned
)

DATA_KID_POINTS_SPENT_ALL_TIME_LEGACY: Final = (
    "points_spent_all_time"  # Use periods.all_time.all_time.points_spent
)

DATA_KID_POINTS_NET_ALL_TIME_LEGACY: Final = (
    "points_net_all_time"  # DERIVED: earned + spent
)

DATA_KID_POINTS_BY_SOURCE_ALL_TIME_LEGACY: Final = (
    "points_by_source_all_time"  # Use periods.all_time.all_time.by_source
)

CONF_SCHEMA_VERSION_LEGACY: Final = "schema_version"

CONF_ACHIEVEMENTS_LEGACY: Final = "achievements"

CONF_BADGES_LEGACY: Final = "badges"

CONF_BONUSES_LEGACY: Final = "bonuses"

CONF_CHALLENGES_LEGACY: Final = "challenges"

CONF_CHORES_LEGACY: Final = "chores"

CONF_KIDS_LEGACY: Final = "kids"

CONF_PARENTS_LEGACY: Final = "parents"

CONF_PENALTIES_LEGACY: Final = "penalties"

CONF_REWARDS_LEGACY: Final = "rewards"

CONF_COST_LEGACY: Final = "cost"

CONF_DASHBOARD_LANGUAGE_LEGACY: Final = "dashboard_language"

CONF_HA_USER_LEGACY: Final = "ha_user"

CONF_INTERNAL_ID_LEGACY: Final = "internal_id"

CONF_POINTS_LEGACY: Final = "points"

CONF_SHARED_CHORE_LEGACY: Final = "shared_chore"

CONF_COMPLETION_CRITERIA_LEGACY: Final = "completion_criteria"

CONF_ACHIEVEMENT_ASSIGNED_KIDS_LEGACY: Final = "assigned_kids"

CONF_ACHIEVEMENT_CRITERIA_LEGACY: Final = "criteria"

CONF_ACHIEVEMENT_LABELS_LEGACY: Final = "achievement_labels"

CONF_ACHIEVEMENT_REWARD_POINTS_LEGACY: Final = "reward_points"

CONF_ACHIEVEMENT_SELECTED_CHORE_ID_LEGACY: Final = "selected_chore_id"

CONF_ACHIEVEMENT_TARGET_VALUE_LEGACY: Final = "target_value"

CONF_ACHIEVEMENT_TYPE_LEGACY: Final = "type"

CONF_BONUS_DESCRIPTION_LEGACY: Final = "bonus_description"

CONF_BONUS_LABELS_LEGACY: Final = "bonus_labels"

CONF_BONUS_NAME_LEGACY: Final = "bonus_name"

CONF_BONUS_POINTS_LEGACY: Final = "bonus_points"

CONF_CHALLENGE_ASSIGNED_KIDS_LEGACY: Final = "assigned_kids"

CONF_CHALLENGE_CRITERIA_LEGACY: Final = "criteria"

CONF_CHALLENGE_END_DATE_LEGACY: Final = "end_date"

CONF_CHALLENGE_LABELS_LEGACY: Final = "challenge_labels"

CONF_CHALLENGE_REWARD_POINTS_LEGACY: Final = "reward_points"

CONF_CHALLENGE_SELECTED_CHORE_ID_LEGACY: Final = "selected_chore_id"

CONF_CHALLENGE_START_DATE_LEGACY: Final = "start_date"

CONF_CHALLENGE_TARGET_VALUE_LEGACY: Final = "target_value"

CONF_CHALLENGE_TYPE_LEGACY: Final = "type"

CONF_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY: Final = "allow_multiple_claims_per_day"

CONF_APPLICABLE_DAYS_LEGACY: Final = "applicable_days"

CONF_APPROVAL_RESET_PENDING_CLAIM_ACTION_LEGACY: Final = (
    "approval_reset_pending_claim_action"
)

CONF_APPROVAL_RESET_TYPE_LEGACY: Final = "approval_reset_type"

CONF_ASSIGNED_KIDS_LEGACY: Final = "assigned_kids"

CONF_CHORE_AUTO_APPROVE_LEGACY: Final = "auto_approve"

CONF_CHORE_DESCRIPTION_LEGACY: Final = "chore_description"

CONF_CHORE_LABELS_LEGACY: Final = "chore_labels"

CONF_CHORE_NAME_LEGACY: Final = "chore_name"

CONF_CUSTOM_INTERVAL_LEGACY: Final = "custom_interval"

CONF_CUSTOM_INTERVAL_UNIT_LEGACY: Final = "custom_interval_unit"

CONF_DEFAULT_POINTS_LEGACY: Final = "default_points"

CONF_DUE_DATE_LEGACY: Final = "due_date"

CONF_OVERDUE_HANDLING_TYPE_LEGACY: Final = "overdue_handling_type"

CONF_RECURRING_FREQUENCY_LEGACY: Final = "recurring_frequency"

CONF_CHORE_SHOW_ON_CALENDAR_LEGACY: Final = "show_on_calendar"

CONF_ENABLE_MOBILE_NOTIFICATIONS_LEGACY: Final = "enable_mobile_notifications"

CONF_ENABLE_PERSISTENT_NOTIFICATIONS_LEGACY: Final = "enable_persistent_notifications"

CONF_MOBILE_NOTIFY_SERVICE_LEGACY: Final = "mobile_notify_service"

CONF_CHORE_NOTIFICATIONS_LEGACY: Final = "chore_notifications"

CONF_ASSOCIATED_KIDS_LEGACY: Final = "associated_kids"

CONF_HA_USER_ID_LEGACY: Final = "ha_user_id"

CONF_PARENT_NAME_LEGACY: Final = "parent_name"

CONF_PENALTY_DESCRIPTION_LEGACY: Final = "penalty_description"

CONF_PENALTY_LABELS_LEGACY: Final = "penalty_labels"

CONF_PENALTY_NAME_LEGACY: Final = "penalty_name"

CONF_PENALTY_POINTS_LEGACY: Final = "penalty_points"

CONF_REWARD_COST_LEGACY: Final = "reward_cost"

CONF_REWARD_DESCRIPTION_LEGACY: Final = "reward_description"

CONF_REWARD_LABELS_LEGACY: Final = "reward_labels"

CONF_REWARD_NAME_LEGACY: Final = "reward_name"

CFOF_CHORES_INPUT_PARTIAL_ALLOWED_LEGACY: Final = "partial_allowed"

CONF_PARTIAL_ALLOWED_LEGACY: Final = "partial_allowed"

DATA_KID_TODAY_CHORE_APPROVALS_LEGACY: Final = (
    "today_chore_approvals"  # Use periods structure instead. [DELETE BEFORE PROD]
)

DATA_CHORE_PARTIAL_ALLOWED_LEGACY: Final = "partial_allowed"

DATA_PENDING_CHORE_APPROVALS_LEGACY: Final = "pending_chore_approvals"

DATA_PENDING_REWARD_APPROVALS_LEGACY: Final = "pending_reward_approvals"

DATA_LINKED_USERS_LEGACY: Final = "linked_users"

DEFAULT_BADGE_THRESHOLD_VALUE_LEGACY: Final = 50

DEFAULT_PARTIAL_ALLOWED_LEGACY = False

ATTR_PARTIAL_ALLOWED_LEGACY: Final = "partial_allowed"

DATA_KID_BADGES_LEGACY: Final = (
    "badges"  # Used in _migrate_kid_badges(), remove when migration dropped
)

DATA_KID_CHORE_APPROVALS_LEGACY: Final = "chore_approvals"

DATA_KID_CHORE_CLAIMS_LEGACY: Final = (
    "chore_claims"  # LEGACY: Migration only - use chore_data structure
)

DATA_KID_CHORE_STREAKS_LEGACY: Final = (
    "chore_streaks"  # LEGACY: Migration only - use chore_data structure
)

DATA_KID_COMPLETED_CHORES_MONTHLY_LEGACY = (
    "completed_chores_monthly"  # LEGACY: Migration only
)

DATA_KID_COMPLETED_CHORES_TOTAL_LEGACY = (
    "completed_chores_total"  # LEGACY: Migration only
)

DATA_KID_COMPLETED_CHORES_TODAY_LEGACY = (
    "completed_chores_today"  # LEGACY: Migration only
)

DATA_KID_COMPLETED_CHORES_WEEKLY_LEGACY = (
    "completed_chores_weekly"  # LEGACY: Migration only
)

DATA_KID_COMPLETED_CHORES_YEARLY_LEGACY = (
    "completed_chores_yearly"  # LEGACY: Migration only
)

DATA_KID_POINTS_EARNED_MONTHLY_LEGACY: Final = "points_earned_monthly"

DATA_KID_POINTS_EARNED_TODAY_LEGACY: Final = "points_earned_today"

DATA_KID_POINTS_EARNED_WEEKLY_LEGACY: Final = "points_earned_weekly"

DATA_KID_POINTS_EARNED_YEARLY_LEGACY: Final = "points_earned_yearly"

DATA_KID_APPROVED_CHORES_LEGACY: Final = "approved_chores"

DATA_KID_CLAIMED_CHORES_LEGACY: Final = (
    "claimed_chores"  # LEGACY: Migration only - use chore_data structure
)

DATA_KID_MAX_POINTS_EVER_LEGACY: Final = (
    "max_points_ever"  # Legacy field - use POINT_STATS_EARNED_ALL_TIME instead
)

DATA_KID_MAX_STREAK_LEGACY: Final = (
    "max_streak"  # Legacy field - use CHORE_STATS_LONGEST_STREAK_ALL_TIME instead
)

DATA_KID_OVERDUE_CHORES_LEGACY: Final = "overdue_chores"

DATA_KID_PENDING_REWARDS_LEGACY: Final = "pending_rewards"

DATA_KID_REDEEMED_REWARDS_LEGACY: Final = "redeemed_rewards"

DATA_KID_REWARD_APPROVALS_LEGACY: Final = "reward_approvals"

DATA_KID_REWARD_CLAIMS_LEGACY: Final = "reward_claims"

DATA_CHORE_ALLOW_MULTIPLE_CLAIMS_PER_DAY_LEGACY: Final = "allow_multiple_claims_per_day"

DATA_CHORE_SHARED_CHORE_LEGACY: Final = (
    "shared_chore"  # LEGACY: Use completion_criteria
)

DATA_KID_CHORE_DATA_DUE_DATE_LEGACY: Final = (
    "due_date"  # LEGACY: Use chore_info[per_kid_due_dates][kid_id] instead
)

DATA_KID_ENABLE_NOTIFICATIONS_LEGACY: Final = "enable_notifications"

DATA_PARENT_ENABLE_NOTIFICATIONS_LEGACY: Final = "enable_notifications"

DATA_KID_OVERDUE_NOTIFICATIONS_LEGACY: Final = (
    "overdue_notifications"  # LEGACY: Dead code, pop from storage
)

DATA_CHORE_ASSIGNED_TO_LEGACY: Final = (
    "assigned_to"  # LEGACY: Never used, replaced by assigned_kids
)

DATA_CHORE_LAST_OVERDUE_NOTIFICATION_LEGACY: Final = (
    "last_overdue_notification"  # LEGACY: Superseded by DATA_NOTIFICATIONS bucket
)

DATA_BADGE_CHORE_COUNT_TYPE_LEGACY = (
    "chore_count_type"  # Read in _migrate_badge_schema()
)

DATA_BADGE_POINTS_MULTIPLIER_LEGACY = (
    "points_multiplier"  # Read in _migrate_badge_schema()
)

DATA_BADGE_THRESHOLD_TYPE_LEGACY = (
    "threshold_type"  # Read in _migrate_badge_schema(), deleted after
)

DATA_BADGE_THRESHOLD_VALUE_LEGACY = (
    "threshold_value"  # Read in _migrate_badge_schema(), deleted after
)

DATA_KID_POINT_DATA_LEGACY: Final = (
    "point_data"  # v42 top-level key → v43+ use DATA_KID_POINT_PERIODS
)

DATA_KID_POINT_DATA_PERIODS_LEGACY: Final = (
    "periods"  # v42 nested key → v43+ flat structure
)

DATA_KID_POINT_DATA_PERIOD_POINTS_TOTAL_LEGACY: Final = (
    "points_total"  # v42 NET value → v43+ use earned+spent
)

DATA_KID_POINT_STATS_LEGACY: Final = "point_stats"

DATA_KID_POINT_STATS_EARNED_TODAY_LEGACY: Final = "points_earned_today"

DATA_KID_POINT_STATS_EARNED_WEEK_LEGACY: Final = "points_earned_week"

DATA_KID_POINT_STATS_EARNED_MONTH_LEGACY: Final = "points_earned_month"

DATA_KID_POINT_STATS_EARNED_YEAR_LEGACY: Final = "points_earned_year"

DATA_KID_POINT_STATS_EARNED_ALL_TIME_LEGACY: Final = "points_earned_all_time"

DATA_KID_POINT_STATS_BY_SOURCE_TODAY_LEGACY: Final = "points_by_source_today"

DATA_KID_POINT_STATS_BY_SOURCE_WEEK_LEGACY: Final = "points_by_source_week"

DATA_KID_POINT_STATS_BY_SOURCE_MONTH_LEGACY: Final = "points_by_source_month"

DATA_KID_POINT_STATS_BY_SOURCE_YEAR_LEGACY: Final = "points_by_source_year"

DATA_KID_POINT_STATS_BY_SOURCE_ALL_TIME_LEGACY: Final = "points_by_source_all_time"

DATA_KID_POINT_STATS_SPENT_TODAY_LEGACY: Final = "points_spent_today"

DATA_KID_POINT_STATS_SPENT_WEEK_LEGACY: Final = "points_spent_week"

DATA_KID_POINT_STATS_SPENT_MONTH_LEGACY: Final = "points_spent_month"

DATA_KID_POINT_STATS_SPENT_YEAR_LEGACY: Final = "points_spent_year"

DATA_KID_POINT_STATS_SPENT_ALL_TIME_LEGACY: Final = "points_spent_all_time"

DATA_KID_POINT_STATS_NET_TODAY_LEGACY: Final = "points_net_today"

DATA_KID_POINT_STATS_NET_WEEK_LEGACY: Final = "points_net_week"

DATA_KID_POINT_STATS_NET_MONTH_LEGACY: Final = "points_net_month"

DATA_KID_POINT_STATS_NET_YEAR_LEGACY: Final = "points_net_year"

DATA_KID_POINT_STATS_NET_ALL_TIME_LEGACY: Final = "points_net_all_time"

DATA_KID_POINT_STATS_EARNING_STREAK_CURRENT_LEGACY: Final = (
    "points_earning_streak_current"
)

DATA_KID_POINT_STATS_EARNING_STREAK_LONGEST_LEGACY: Final = (
    "points_earning_streak_longest"
)

DATA_KID_CHORE_STATS_LEGACY: Final = "chore_stats"

DATA_CHORE_TOTAL_POINTS_LEGACY: Final = (
    "total_points"  # Removed from chore items in v44+
)

DATA_KID_CHORE_STATS_APPROVED_TODAY_LEGACY: Final = "approved_today"

DATA_KID_CHORE_STATS_APPROVED_WEEK_LEGACY: Final = "approved_week"

DATA_KID_CHORE_STATS_APPROVED_MONTH_LEGACY: Final = "approved_month"

DATA_KID_CHORE_STATS_APPROVED_YEAR_LEGACY: Final = "approved_year"

DATA_KID_CHORE_STATS_APPROVED_ALL_TIME_LEGACY: Final = "approved_all_time"

DATA_KID_CHORE_STATS_COMPLETED_TODAY_LEGACY: Final = "completed_today"

DATA_KID_CHORE_STATS_COMPLETED_WEEK_LEGACY: Final = "completed_week"

DATA_KID_CHORE_STATS_COMPLETED_MONTH_LEGACY: Final = "completed_month"

DATA_KID_CHORE_STATS_COMPLETED_YEAR_LEGACY: Final = "completed_year"

DATA_KID_CHORE_STATS_COMPLETED_ALL_TIME_LEGACY: Final = "completed_all_time"

DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_ALL_TIME_LEGACY: Final = (
    "most_completed_chore_all_time"
)

DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_WEEK_LEGACY: Final = (
    "most_completed_chore_week"
)

DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_MONTH_LEGACY: Final = (
    "most_completed_chore_month"
)

DATA_KID_CHORE_STATS_MOST_COMPLETED_CHORE_YEAR_LEGACY: Final = (
    "most_completed_chore_year"
)

DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_TODAY_LEGACY: Final = (
    "total_points_from_chores_today"
)

DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_WEEK_LEGACY: Final = (
    "total_points_from_chores_week"
)

DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_MONTH_LEGACY: Final = (
    "total_points_from_chores_month"
)

DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_YEAR_LEGACY: Final = (
    "total_points_from_chores_year"
)

DATA_KID_CHORE_STATS_TOTAL_POINTS_FROM_CHORES_ALL_TIME_LEGACY: Final = (
    "total_points_from_chores_all_time"
)

DATA_KID_CHORE_STATS_OVERDUE_TODAY_LEGACY: Final = "overdue_today"

DATA_KID_CHORE_STATS_OVERDUE_WEEK_LEGACY: Final = "overdue_week"

DATA_KID_CHORE_STATS_OVERDUE_MONTH_LEGACY: Final = "overdue_month"

DATA_KID_CHORE_STATS_OVERDUE_YEAR_LEGACY: Final = "overdue_year"

DATA_KID_CHORE_STATS_OVERDUE_ALL_TIME_LEGACY: Final = "overdue_count_all_time"

DATA_KID_CHORE_STATS_CLAIMED_TODAY_LEGACY: Final = "claimed_today"

DATA_KID_CHORE_STATS_CLAIMED_WEEK_LEGACY: Final = "claimed_week"

DATA_KID_CHORE_STATS_CLAIMED_MONTH_LEGACY: Final = "claimed_month"

DATA_KID_CHORE_STATS_CLAIMED_YEAR_LEGACY: Final = "claimed_year"

DATA_KID_CHORE_STATS_CLAIMED_ALL_TIME_LEGACY: Final = "claimed_all_time"

DATA_KID_CHORE_STATS_DISAPPROVED_TODAY_LEGACY: Final = "disapproved_today"

DATA_KID_CHORE_STATS_DISAPPROVED_WEEK_LEGACY: Final = "disapproved_week"

DATA_KID_CHORE_STATS_DISAPPROVED_MONTH_LEGACY: Final = "disapproved_month"

DATA_KID_CHORE_STATS_DISAPPROVED_YEAR_LEGACY: Final = "disapproved_year"

DATA_KID_CHORE_STATS_DISAPPROVED_ALL_TIME_LEGACY: Final = "disapproved_all_time"

DATA_KID_CHORE_STATS_LONGEST_STREAK_WEEK_LEGACY: Final = "longest_streak_week"

DATA_KID_CHORE_STATS_LONGEST_STREAK_MONTH_LEGACY: Final = "longest_streak_month"

DATA_KID_CHORE_STATS_LONGEST_STREAK_YEAR_LEGACY: Final = "longest_streak_year"

DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME_LEGACY: Final = "longest_streak_all_time"

DATA_KID_CHORE_STATS_AVG_PER_DAY_WEEK_LEGACY: Final = "avg_per_day_week"

DATA_KID_CHORE_STATS_AVG_PER_DAY_MONTH_LEGACY: Final = "avg_per_day_month"

DATA_KID_CHORE_STATS_CURRENT_DUE_TODAY_LEGACY: Final = "current_due_today"

DATA_KID_CHORE_STATS_CURRENT_OVERDUE_LEGACY: Final = "current_overdue"

DATA_KID_CHORE_STATS_CURRENT_CLAIMED_LEGACY: Final = "current_claimed"

DATA_KID_CHORE_STATS_CURRENT_APPROVED_LEGACY: Final = "current_approved"

ENTITY_SUFFIX_BADGES_LEGACY: Final = "_badges"

ENTITY_SUFFIX_REWARD_CLAIMS_LEGACY: Final = "_reward_claims"

ENTITY_SUFFIX_REWARD_APPROVALS_LEGACY: Final = "_reward_approvals"

ENTITY_SUFFIX_CHORE_CLAIMS_LEGACY: Final = "_chore_claims"

ENTITY_SUFFIX_CHORE_APPROVALS_LEGACY: Final = "_chore_approvals"

ENTITY_SUFFIX_STREAK_LEGACY: Final = "_streak"

SELECT_KC_UID_MIDFIX_CHORES_SELECT_LEGACY: Final = "_select_chores_"

ENTITY_SUFFIXES_LEGACY: Final = [
    ENTITY_SUFFIX_BADGES_LEGACY,
    ENTITY_SUFFIX_REWARD_CLAIMS_LEGACY,
    ENTITY_SUFFIX_REWARD_APPROVALS_LEGACY,
    ENTITY_SUFFIX_CHORE_CLAIMS_LEGACY,
    ENTITY_SUFFIX_CHORE_APPROVALS_LEGACY,
    ENTITY_SUFFIX_STREAK_LEGACY,
]

CFOF_CHORES_INPUT_NOTIFY_ON_REMINDER_LEGACY: Final = "notify_on_reminder"
