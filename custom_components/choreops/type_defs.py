"""Type definitions for KidsChores data structures.

ARCHITECTURE DECISION: HYBRID APPROACH (TypedDict + dict[str, Any])
===================================================================

This file uses a **hybrid type strategy** to balance type safety with practical
code patterns:

1. **TypedDict for STATIC structures** (fixed keys known at design time):
   - Entity definitions: ParentData, ChoreData, BadgeData, etc.
   - Configuration objects: ScheduleConfig, BadgeTarget, etc.
   - ✅ Benefit: Full type safety, IDE autocomplete, catch bugs early

2. **dict[str, Any] for DYNAMIC structures** (keys determined at runtime):
   - Per-kid tracking: kid_chore_data[chore_id][dynamic_field]
   - Period aggregations: stats_data[period_key][dynamic_stat_type]
   - ✅ Benefit: Honest about runtime patterns, no type: ignore noise

WHY THIS APPROACH?
==================
The codebase uses dynamic key patterns extensively (field_name variables,
period_key lookups, etc.). TypedDict requires literal string keys, making it
fundamentally incompatible with these patterns.

Previous attempt to use TypedDict everywhere resulted in:
- 150+ errors requiring # type: ignore[literal-required] suppressions
- Type checking effectively disabled where it was most needed
- Dishonest type annotations (claimed static structure, used dynamically)

This hybrid approach:
- Uses TypedDict where keys are truly fixed
- Uses dict[str, Any] where keys are dynamic
- Results in clean mypy output without widespread suppressions
- Documents actual code behavior instead of aspirational structure

See docs/ARCHITECTURE.md and docs/DEVELOPMENT_STANDARDS.md for details.

IMPORTANT: This file must NOT import from coordinator.py, *helpers.py, or
any file that imports coordinator to avoid circular dependencies.
Only import from const.py (constants) and typing (type machinery).

NOTE: TypedDict is STATIC ANALYSIS ONLY. All runtime error handling
(null checks, .get() defaults, try/except) must remain in coordinator.py.
TypedDict does NOT enforce types at runtime.
"""

from typing import Any, Literal, NotRequired, TypedDict

# =============================================================================
# Type Aliases (for readability)
# =============================================================================

KidId = str  # UUID string
UserId = str  # UUID string (canonical schema45+ identity)
ChoreId = str  # UUID string
BadgeId = str  # UUID string
RewardId = str  # UUID string
ISODatetime = str  # ISO 8601 datetime string "2026-01-18T12:30:00+00:00"
ISODate = str  # ISO 8601 date string (no time) "2026-01-18"


# =============================================================================
# Simple Entity Types (no nesting)
# =============================================================================


class ParentData(TypedDict):
    """Type definition for a parent entity.

    Parent fields are all required once created via _create_parent().
    """

    internal_id: str  # Always present (set in _create_parent)
    name: str
    ha_user_id: str
    associated_kids: list[str]  # List of kid UUIDs
    mobile_notify_service: str
    use_persistent_notifications: bool
    dashboard_language: str
    allow_chore_assignment: bool
    enable_chore_workflow: bool
    enable_gamification: bool
    linked_shadow_kid_id: NotRequired[str | None]  # Only set if shadow kid created


# =============================================================================
# Reporting service response contracts
# =============================================================================


class ReportRangeResult(TypedDict):
    """Resolved report range metadata.

    Used by report helper functions and returned in service responses.
    """

    mode: str
    start_iso: str
    end_iso: str
    timezone: str


class ReportDailyBlock(TypedDict):
    """Daily activity aggregate block for markdown reports."""

    date: str
    earned: float
    spent: float
    net: float
    transactions: int
    markdown_section: str


class ReportDeliveryStatus(TypedDict):
    """Delivery status metadata for report notifications."""

    notify_attempted: bool
    notify_service: str | None
    delivered: bool


class ActivityReportResponse(TypedDict):
    """Response payload for generate_activity_report service."""

    range: ReportRangeResult
    scope: dict[str, Any]
    summary: dict[str, float | int]
    daily: list[ReportDailyBlock]
    markdown: str
    html: NotRequired[str]
    supplemental: dict[str, Any]
    delivery: ReportDeliveryStatus


class RewardData(TypedDict):
    """Type definition for a reward entity."""

    internal_id: str
    name: str
    cost: float
    description: str
    icon: str
    reward_labels: list[str]


class PenaltyData(TypedDict):
    """Type definition for a penalty entity."""

    internal_id: str
    name: str
    points: float
    description: str
    icon: str
    penalty_labels: list[str]
    periods: NotRequired[dict[str, Any]]  # Phase 4C: Period tracking


class BonusData(TypedDict):
    """Type definition for a bonus entity."""

    internal_id: str
    name: str
    points: float
    description: str
    icon: str
    bonus_labels: list[str]
    periods: NotRequired[dict[str, Any]]  # Phase 4C: Period tracking


# =============================================================================
# Chore Types (with nested structures)
# =============================================================================


class ChorePerKidDueDates(TypedDict, total=False):
    """Per-kid due date mapping.

    Keys are kid_id (UUID string), values are ISO datetime string or None.
    Using total=False because keys are dynamic (kid UUIDs).
    """


class ChorePerKidApplicableDays(TypedDict, total=False):
    """Per-kid applicable weekdays.

    Keys are kid_id (UUID string), values are list of weekday ints (0=Mon, 6=Sun).
    Using total=False because keys are dynamic (kid UUIDs).
    """


class ChorePerKidDailyMultiTimes(TypedDict, total=False):
    """Per-kid daily multi times.

    Keys are kid_id (UUID string), values are list of time strings "HH:MM".
    Using total=False because keys are dynamic (kid UUIDs).
    """


class ChoreData(TypedDict):
    """Type definition for a chore entity.

    Created via data_builders.build_chore().
    See data_builders.py for canonical field list.
    """

    # Core identification
    internal_id: str
    name: str
    state: str  # PENDING, CLAIMED, APPROVED, OVERDUE

    # Points and configuration
    default_points: float
    approval_reset_type: str
    overdue_handling_type: str
    approval_reset_pending_claim_action: str

    # Description and display
    description: str
    chore_labels: list[str]
    icon: str

    # Assignment
    assigned_kids: list[str]  # List of kid UUIDs

    # Scheduling
    recurring_frequency: str
    custom_interval: NotRequired[int | None]
    custom_interval_unit: NotRequired[str | None]
    daily_multi_times: NotRequired[list[str]]  # For DAILY_MULTI frequency

    # Due dates
    due_date: NotRequired[str | None]  # ISO datetime
    per_kid_due_dates: dict[str, str | None]  # kid_id -> ISO datetime
    applicable_days: list[str]  # Weekday names or ints
    per_kid_applicable_days: NotRequired[dict[str, list[str]]]
    per_kid_daily_multi_times: NotRequired[dict[str, list[str]]]

    # Due window configuration (per-chore offsets)
    due_window_offset: NotRequired[
        str | None
    ]  # Duration string "1d 6h 30m" or "0" disabled
    due_reminder_offset: NotRequired[
        str | None
    ]  # Duration string for reminder notification

    # Runtime tracking (set during chore lifecycle)
    last_completed: NotRequired[str | None]  # ISO datetime
    last_claimed: NotRequired[str | None]  # ISO datetime
    approval_period_start: NotRequired[str | None]  # ISO datetime
    claimed_by: NotRequired[list[str]]  # List of kid UUIDs
    completed_by: NotRequired[list[str]]  # List of kid UUIDs (for shared chores)

    # Notifications
    notify_on_claim: bool
    notify_on_approval: bool
    notify_on_disapproval: bool
    notify_on_overdue: NotRequired[bool]  # v0.5.0-beta4 schema 44+

    # Calendar and features
    show_on_calendar: NotRequired[bool]
    auto_approve: NotRequired[bool]

    # Completion criteria
    completion_criteria: str  # SHARED, SHARED_FIRST, INDEPENDENT, ROTATION_*

    # Rotation tracking (v0.5.0 Chore Logic - only for rotation_* criteria)
    rotation_current_kid_id: NotRequired[
        str | None
    ]  # kid_id UUID of current turn holder
    rotation_cycle_override: NotRequired[
        bool
    ]  # Boolean: temp allow any kid to claim (cleared on advancement)

    # Claims restriction (v0.5.0 Chore Logic - blocks claims before due window)
    chore_claim_lock_until_window: NotRequired[bool]


ResetTrigger = Literal[
    "approval",
    "due_date",
    "midnight",
]

ResetBoundaryCategory = Literal[
    "hold",
    "clear_only",
    "reset_and_reschedule",
]

ResetDecision = Literal[
    "hold",
    "reset_only",
    "reset_and_reschedule",
    "auto_approve_pending",
]


class ResetContext(TypedDict, total=False):
    """Policy input contract for reset decisioning."""

    trigger: ResetTrigger
    approval_reset_type: str
    overdue_handling_type: str
    completion_criteria: str
    all_kids_approved: bool
    approval_after_reset: bool
    boundary_category: ResetBoundaryCategory | None
    has_pending_claim: bool
    pending_claim_action: str


class ResetApplyContext(TypedDict, total=False):
    """Execution contract for applying a reset action."""

    kid_id: str
    chore_id: str
    decision: ResetDecision
    reschedule_kid_id: str | None
    allow_reschedule: bool


# =============================================================================
# Badge Types (with nested structures)
# =============================================================================


class BadgeTarget(TypedDict, total=False):
    """Badge target/threshold configuration."""

    threshold_value: float
    target_type: str  # POINTS, CHORE_COUNT, DAYS_*, STREAK_*
    maintenance_rules: NotRequired[float]  # For cumulative badges


# Canonical target contract for unified target tracking initiative.
# This type is additive in Phase 1 and is used as a cross-goal mapping contract
# for badges, achievements, and challenges in later phases.
CanonicalTargetType = Literal[
    "unknown_target",
    "points",
    "points_chores",
    "chore_count",
    "daily_completion",
    "daily_completion_due",
    "daily_completion_no_overdue",
    "daily_completion_due_no_overdue",
    "daily_minimum",
    "completion_streak",
    "completion_streak_due",
    "completion_streak_no_overdue",
    "completion_streak_due_no_overdue",
    "streak",
    "streak_due",
    "streak_no_overdue",
    "streak_due_no_overdue",
    "total_with_baseline",
    "total_within_window",
    "badge_award_count",
]


class CanonicalTargetDefinition(TypedDict, total=False):
    """Canonical target mapping for badge/achievement/challenge evaluation.

    Phase 1 contract only: this defines target-mapping shape and does not
    change runtime behavior yet.
    """

    target_type: CanonicalTargetType
    threshold_value: float
    source_entity_type: Literal["badge", "achievement", "challenge"]
    source_item_id: str
    source_raw_type: str
    use_due_only_scope: NotRequired[bool]
    require_no_overdue: NotRequired[bool]
    min_count_required: NotRequired[int]
    percent_required: NotRequired[float]
    baseline_value: NotRequired[float]
    source_badge_id: NotRequired[str]
    tracked_chore_ids: NotRequired[list[str]]


class BadgeResetSchedule(TypedDict, total=False):
    """Badge reset/recurrence schedule."""

    recurring_frequency: str
    custom_interval: NotRequired[int]
    custom_interval_unit: NotRequired[str]
    start_date: NotRequired[str]  # ISO date
    end_date: NotRequired[str]  # ISO date
    grace_period_days: NotRequired[int]


class BadgeAwards(TypedDict, total=False):
    """Badge award configuration."""

    award_points: NotRequired[float]
    point_multiplier: NotRequired[float]
    award_items: NotRequired[list[str]]  # Future: physical rewards


class BadgeData(TypedDict):
    """Type definition for a badge entity."""

    internal_id: str
    name: str
    badge_type: str  # PERIODIC, CUMULATIVE
    occasion_type: NotRequired[str]

    # Assignment
    assigned_to: list[str]  # List of kid UUIDs
    earned_by: list[str]  # List of kid UUIDs who earned it

    # Configuration
    target: BadgeTarget
    reset_schedule: NotRequired[BadgeResetSchedule]
    awards: NotRequired[BadgeAwards]
    tracked_chores: NotRequired[dict[str, list[str]]]  # selected_chores key

    # Linkage
    associated_achievement: NotRequired[str]  # Achievement UUID
    associated_challenge: NotRequired[str]  # Challenge UUID


# =============================================================================
# Kid Nested Types (chore tracking - deepest nesting)
# =============================================================================


class KidChoreDataPeriodEntry(TypedDict, total=False):
    """Period-level stats for a single chore (daily/weekly/monthly/yearly/all_time)."""

    approved: int
    claimed: int
    disapproved: int
    overdue: int
    points: float
    longest_streak: int


# Dynamic structure - keys are period types accessed via period_key variable
KidChoreDataPeriods = dict[str, Any]
"""Period containers for chore tracking.

Keys: 'daily', 'weekly', 'monthly', 'yearly', 'all_time'
Values: dict[date_str, KidChoreDataPeriodEntry] or KidChoreDataPeriodEntry

Used dynamically as: periods_data[period_key] where period_key is a variable.
"""


# Dynamic structure - accessed with variable keys (field_name, etc.)
# Using dict[str, Any] instead of TypedDict because code uses patterns like:
#   chore_entry[field_name] = value  # where field_name is a variable
KidChoreDataEntry = dict[str, Any]
"""Per-chore tracking data for a single kid-chore combination.

Created dynamically via setdefault() in coordinator methods.
Key fields are added incrementally as chore is claimed/approved.

Common keys (not exhaustive, keys added at runtime):

- state: str (PENDING, CLAIMED, APPROVED, OVERDUE)
- pending_claim_count: int (for multi-claim chores)
- name: str (denormalized chore name)
- last_approved: str (ISO datetime)
- last_claimed: str (ISO datetime)
- last_disapproved: str (ISO datetime)
- last_overdue: str (ISO datetime)
- approval_period_start: str (ISO datetime)
- total_count: int
- total_points: float
- periods: KidChoreDataPeriods
- last_longest_streak_all_time: int
- claimed_by: str | list[str] (who claimed)
- completed_by: str | list[str] (who completed)

Note: Notification timestamps (last_notified_due_window, last_notified_due_reminder)
are stored in a separate DATA_NOTIFICATIONS bucket owned by NotificationManager
(Platinum domain separation pattern, v0.5.0+).
"""


# =============================================================================
# Kid Nested Types (badge progress)
# =============================================================================


class KidBadgeProgress(TypedDict, total=False):
    """Per-badge progress tracking for a kid.

    Created dynamically in _manage_badge_maintenance().
    """

    name: NotRequired[str]  # Denormalized badge name
    badge_type: NotRequired[str]  # PERIODIC or CUMULATIVE
    status: NotRequired[str]  # active, grace, demoted, earned

    # Progress counters
    cycle_count: NotRequired[int]
    days_cycle_count: NotRequired[int]
    days_completed: NotRequired[int]
    chores_completed: NotRequired[int]
    chores_cycle_count: NotRequired[int]
    chores_today: NotRequired[int]
    points_cycle_count: NotRequired[float]
    points_today: NotRequired[float]
    approved_count: NotRequired[int]
    total_count: NotRequired[int]

    # Target info (denormalized from badge)
    target_type: NotRequired[str]
    threshold_value: NotRequired[float]
    overall_progress: NotRequired[float]  # 0.0 to 1.0
    criteria_met: NotRequired[bool]

    # Schedule info
    recurring_frequency: NotRequired[str]
    start_date: NotRequired[str]  # ISO date
    end_date: NotRequired[str]  # ISO date
    last_update_day: NotRequired[str]  # ISO date
    last_awarded: NotRequired[str]  # ISO datetime

    # Chore tracking
    tracked_chores: NotRequired[list[str]]  # Chore UUIDs
    today_completed: NotRequired[list[str]]  # Chore UUIDs completed today
    penalty_applied: NotRequired[bool]

    # Special occasion fields
    occasion_type: NotRequired[str]  # Birthday, holiday, etc.

    # Linked entity fields
    associated_achievement: NotRequired[str]  # Achievement UUID
    associated_challenge: NotRequired[str]  # Challenge UUID


class KidCumulativeBadgeProgress(TypedDict, total=False):
    """Cumulative badge progress tracking for a kid.

    Single structure per kid (not per-badge).

    Phase 3A: Compute-on-Read architecture - only store state fields.
    All derived fields (current/next/highest badge info) computed on-read
    via GamificationManager.get_cumulative_badge_progress().
    """

    # State fields (stored)
    status: str  # active, grace, demoted
    cycle_points: float
    maintenance_end_date: NotRequired[str | None]  # ISO date string or None
    maintenance_grace_end_date: NotRequired[str | None]  # ISO date string or None


# =============================================================================
# Kid Nested Types (reward/point tracking)
# =============================================================================


# Dynamic structure - period stats aggregation
PeriodicStatsEntry = dict[str, Any]
"""Stats entry for a single period (day/week/month/year).

Used as values in the daily/weekly/monthly/yearly period dicts.

Common keys: 'claimed' (int), 'approved' (int), 'disapproved' (int)
"""


class KidRewardDataPeriods(TypedDict, total=False):
    """Period containers for reward tracking.

    Keys within each period dict are date strings.
    """

    daily: NotRequired[dict[str, PeriodicStatsEntry]]  # date -> stats
    weekly: NotRequired[dict[str, PeriodicStatsEntry]]
    monthly: NotRequired[dict[str, PeriodicStatsEntry]]
    yearly: NotRequired[dict[str, PeriodicStatsEntry]]
    all_time: NotRequired[dict[str, PeriodicStatsEntry]]


class KidRewardDataEntry(TypedDict, total=False):
    """Per-reward tracking data for a single kid-reward combination."""

    name: NotRequired[str]  # Denormalized reward name
    pending_count: int
    total_claims: NotRequired[int]
    total_approved: NotRequired[int]
    total_disapproved: NotRequired[int]
    total_points_spent: NotRequired[float]
    last_claimed: NotRequired[str]  # ISO datetime
    last_approved: NotRequired[str]  # ISO datetime
    last_disapproved: NotRequired[str]  # ISO datetime
    notification_ids: NotRequired[list[str]]  # For persistent notifications
    periods: NotRequired[KidRewardDataPeriods]


# === Kid Data Structure ===


# Dynamic structure - aggregated stats accessed with variable keys
KidChoreStats = dict[str, Any]
"""Chore completion statistics.

Common keys (added dynamically at runtime):

- approved_today/week/month/year/all_time: int
- claimed_today/week/month/year/all_time: int
- disapproved_today/week/month/year/all_time: int
- overdue_today/week/month/year/all_time: int
- current_approved/claimed/overdue/due_today: int
- total_points_from_chores_today/week/month/year/all_time: float
- longest_streak_all_time/week/month/year: int
- most_completed_chore_all_time/week/month/year: str
- avg_per_day_week/month: float
"""


class BadgesEarnedEntry(TypedDict, total=False):
    """Entry in badges_earned dict."""

    badge_name: str
    last_awarded_date: NotRequired[str]  # ISO datetime
    award_count: int
    periods: NotRequired[KidRewardDataPeriods]  # Reuse structure


# =============================================================================
# KidData Main Type (the largest one)
# =============================================================================


class KidData(TypedDict):
    """Type definition for a kid entity.

    Created via _create_kid() in coordinator.py.
    Many fields are added incrementally via setdefault() during runtime.
    """

    # Core identification
    internal_id: str
    name: str

    # Points
    points: float
    points_multiplier: float

    # Linkage
    ha_user_id: NotRequired[str | None]
    is_shadow_kid: NotRequired[bool]
    linked_parent_id: NotRequired[str | None]

    # Notifications
    mobile_notify_service: str
    use_persistent_notifications: bool
    dashboard_language: NotRequired[str]

    # Badge tracking
    badges_earned: dict[str, BadgesEarnedEntry]  # badge_id -> entry
    badge_progress: NotRequired[dict[str, KidBadgeProgress]]  # badge_id -> progress
    cumulative_badge_progress: NotRequired[KidCumulativeBadgeProgress]

    # Chore tracking (the big nested structure)
    chore_data: NotRequired[dict[str, KidChoreDataEntry]]  # chore_id -> entry
    chore_stats: NotRequired[KidChoreStats]

    # Reward tracking
    reward_data: dict[str, KidRewardDataEntry]  # reward_id -> entry
    reward_stats: NotRequired[dict[str, Any]]  # Aggregated reward statistics

    # Penalty/bonus application tracking (v43+: transformed to period dicts)
    penalty_applies: dict[str, dict[str, Any]]  # penalty_id -> {periods: {...}}
    bonus_applies: dict[str, dict[str, Any]]  # bonus_id -> {periods: {...}}

    # Point statistics and period data (v43+)
    point_periods: NotRequired[dict[str, Any]]  # Flat period tracking structure

    # Current streak (daily approval streak)
    current_streak: NotRequired[int]
    last_streak_date: NotRequired[str]  # ISO date

    # Overdue tracking
    overdue_chores: NotRequired[list[str]]  # Chore UUIDs
    # completed_by_other_chores removed in v0.5.0+ (Phase 2)
    # SHARED_FIRST blocking computed dynamically, not tracked in kid lists


class UserData(KidData):
    """Canonical user record type for schema45+ unified model.

    Phase 3 bridge: `UserData` currently reuses the `KidData` shape so
    runtime refactors can migrate manager/platform code incrementally.
    """


# =============================================================================
# Achievement Types
# =============================================================================


class AchievementProgress(TypedDict, total=False):
    """Per-kid achievement progress tracking.

    Stored in achievement_info["progress"][kid_id].
    Used for streak-based and count-based achievements.
    """

    # For streak achievements
    current_streak: int  # Current streak count
    last_date: str | None  # ISO date of last streak contribution

    # For total/count achievements
    count: int  # Total count towards achievement

    # Award status
    awarded: bool  # Whether achievement has been awarded


class AchievementData(TypedDict):
    """Type definition for an achievement entity."""

    internal_id: str
    name: str
    achievement_type: str  # CHORE_COUNT, STREAK, etc.
    criteria: str  # Description of criteria
    description: str
    icon: str
    achievement_labels: list[str]

    # Target
    target_value: int
    baseline: NotRequired[int]
    selected_chore_id: NotRequired[str]  # Chore UUID for chore-specific

    # Assignment
    assigned_kids: list[str]  # Kid UUIDs

    # Progress tracking (per-kid)
    progress: dict[str, AchievementProgress]  # kid_id -> progress data
    current_value: NotRequired[dict[str, int]]  # kid_id -> current value

    # Award status
    awarded: dict[str, bool]  # kid_id -> awarded?
    last_awarded_date: NotRequired[dict[str, str]]  # kid_id -> ISO datetime
    reward_points: float


# =============================================================================
# Challenge Types
# =============================================================================


class ChallengeDailyCounts(TypedDict, total=False):
    """Per-kid daily counts for challenges.

    Keys are kid_id (UUID string), values are dict[date_str, int].
    Using total=False because keys are dynamic.
    """


class ChallengeProgress(TypedDict, total=False):
    """Per-kid challenge progress tracking.

    Stored in challenge_info["progress"][kid_id].
    Used for count-based and daily minimum challenges.
    """

    # For count-based challenges
    count: int  # Total count towards challenge target

    # For daily minimum challenges
    daily_counts: dict[str, int]  # ISO date -> count for that day

    # Award status
    awarded: bool  # Whether challenge has been awarded


class ChallengeData(TypedDict):
    """Type definition for a challenge entity."""

    internal_id: str
    name: str
    challenge_type: str  # CHORE_COUNT, DAILY_MIN, etc.
    criteria: str
    description: str
    icon: str
    challenge_labels: list[str]

    # Target
    target_value: int
    required_daily: NotRequired[int]  # For daily minimum challenges
    selected_chore_id: NotRequired[str]  # Chore UUID

    # Assignment
    assigned_kids: list[str]

    # Schedule
    start_date: str  # ISO date
    end_date: str  # ISO date

    # Progress tracking
    progress: dict[str, ChallengeProgress]  # kid_id -> progress data
    count: NotRequired[dict[str, int]]  # kid_id -> count
    daily_counts: NotRequired[dict[str, dict[str, int]]]  # kid_id -> date -> count

    # Award status
    awarded: dict[str, bool]  # kid_id -> awarded?
    reward_points: float


# =============================================================================
# Schedule Engine Configuration
# =============================================================================


class ScheduleConfig(TypedDict, total=False):
    """Configuration for RecurrenceEngine in schedule_engine.py.

    Used to calculate next occurrences for chores, badges, and challenges.
    All fields are optional (total=False) to support partial configuration.
    """

    frequency: str  # FREQUENCY_* or PERIOD_*_END constant from const.py
    interval: int  # Interval count for FREQUENCY_CUSTOM (default: 1)
    interval_unit: str  # TIME_UNIT_* constant (days, weeks, months, etc.)
    base_date: str  # ISO datetime string - starting point for calculations
    applicable_days: list[int]  # Weekday integers (0=Mon, 6=Sun) for filtering
    reference_datetime: str  # ISO datetime - "after" reference for next occurrence
    daily_multi_times: str  # Pipe-separated times for FREQUENCY_DAILY_MULTI (e.g., "08:00|12:00|18:00")


# =============================================================================
# Collection Type Aliases (for coordinator data properties)
# =============================================================================

KidsCollection = dict[KidId, KidData]
UsersCollection = dict[UserId, UserData]
ChoresCollection = dict[ChoreId, ChoreData]
BadgesCollection = dict[BadgeId, BadgeData]
RewardsCollection = dict[RewardId, RewardData]
PenaltiesCollection = dict[str, PenaltyData]
BonusesCollection = dict[str, BonusData]
ParentsCollection = dict[str, ParentData]
AchievementsCollection = dict[str, AchievementData]
ChallengesCollection = dict[str, ChallengeData]

# Per-kid progress type aliases (used in sensor.py for type annotations)
# These are the per-kid progress entries from the progress dict
# Using union with dict[str, Any] to handle empty dict {} default values
AchievementProgressData = AchievementProgress | dict[str, Any]
ChallengeProgressData = ChallengeProgress | dict[str, Any]


# =============================================================================
# Gamification Engine Types (Phase 5 - Engine/Manager Architecture)
# =============================================================================
# Used by GamificationEngine for pure evaluation logic and GamificationManager
# for coordination. These types ensure consistent data shapes between components.


class _EvaluationContextRequired(TypedDict):
    """Required fields for EvaluationContext."""

    # Required: Core kid identifiers
    kid_id: str  # Kid UUID
    kid_name: str  # For logging/debugging

    # Required: Point data
    current_points: float  # Current point balance
    total_points_earned: float  # All-time points earned (from point_stats)

    # Required: Progress tracking
    # v43+: chore_stats deleted from storage, now use chore_periods.all_time bucket
    chore_periods_all_time: dict[str, Any]  # Aggregated chore period stats (all_time)
    badge_progress: dict[str, KidBadgeProgress]  # Per-badge progress tracking
    cumulative_badge_progress: KidCumulativeBadgeProgress  # Cumulative badge state
    badges_earned: dict[str, BadgesEarnedEntry]  # Already earned badges
    achievement_progress: dict[str, AchievementProgress]  # Per-achievement progress
    challenge_progress: dict[str, ChallengeProgress]  # Per-challenge progress

    # Required: Date context
    today_iso: str  # Today's date as ISO string


class EvaluationContext(_EvaluationContextRequired, total=False):
    """Minimal data needed to evaluate gamification criteria.

    This is the input to GamificationEngine.evaluate_* methods.
    Contains only the data needed for evaluation - NOT the full KidData.
    Built by GamificationManager._build_evaluation_context() from coordinator data.

    Design principle: Pass only what's needed. Don't pass entire KidData object.

    Inherits required fields from _EvaluationContextRequired.
    Additional optional fields defined below.
    """

    # Optional: Current entity being evaluated (set by Manager before calling engine)
    current_badge_progress: KidBadgeProgress  # Progress for badge being evaluated
    current_achievement_progress: AchievementProgress  # Progress for achievement
    current_challenge_progress: ChallengeProgress  # Progress for challenge

    # Optional: Pre-computed daily stats (set by Manager for daily evaluations)
    today_stats: dict[str, Any]  # Today's computed stats
    today_completion: dict[str, Any]  # Today's completion state (all tracked)
    today_completion_due: dict[str, Any]  # Today's completion (due today only)


class TargetProgressMutationState(TypedDict, total=False):
    """Canonical progress fields for idempotent target mutation.

    Same-day idempotency rules:
    - `last_update_day` is the gate key for same-day re-evaluation.
    - `days_cycle_count` and `streak_count` can increment at most once per day.
    - Re-evaluation on the same `today_iso` must not double-increment counters.
    - Undo/regression paths must reference `last_update_day` before decrement/reset.
    """

    last_update_day: ISODate
    days_cycle_count: NotRequired[int]
    streak_count: NotRequired[int]
    points_cycle_count: NotRequired[float]
    chores_cycle_count: NotRequired[int]
    today_approved_count: NotRequired[int]
    today_total_count: NotRequired[int]
    today_has_overdue: NotRequired[bool]
    was_incremented_today: NotRequired[bool]


class CriterionResult(TypedDict):
    """The result of a single criterion check.

    Returned by criterion handler functions (e.g., _evaluate_points).
    Multiple CriterionResults can be combined for multi-criteria badges.
    """

    criterion_type: str  # Type identifier (e.g., "points", "streak_all_chores")
    met: bool  # True if criterion threshold is satisfied
    progress: float  # 0.0 to 1.0 (capped at 1.0)
    threshold: float  # Target value to meet criterion
    current_value: float  # Current achieved value
    reason: str  # Human-readable explanation


class EvaluationResult(TypedDict):
    """The final verdict on a badge/achievement/challenge.

    Returned by GamificationEngine.evaluate_badge(), evaluate_achievement(), etc.
    This is the RAW evaluation result - the Manager determines earned/kept/notify logic.
    """

    entity_id: str  # Badge/Achievement/Challenge UUID
    entity_type: str  # "badge", "achievement", or "challenge"
    entity_name: str  # For logging/notifications
    criteria_met: bool  # True if all criteria are satisfied
    overall_progress: float  # 0.0 to 1.0 average across criteria
    criterion_results: list[CriterionResult]  # Individual criterion outcomes
    reason: str  # Optional explanation (for edge cases)
    evaluated_at: str  # ISO timestamp of evaluation


class GamificationBatchResult(TypedDict):
    """Results from evaluating all gamification for a kid.

    Returned by GamificationEngine.evaluate_all() or GamificationManager._evaluate_pending_kids().
    Provides a complete picture of what changed for a single kid.
    """

    kid_id: str
    kid_name: str
    badge_results: list[EvaluationResult]
    achievement_results: list[EvaluationResult]
    challenge_results: list[EvaluationResult]
    # Action lists (IDs of entities that need state changes)
    badges_to_award: list[str]  # Badge IDs to award
    badges_to_revoke: list[str]  # Badge IDs to revoke (maintenance failure)
    achievements_to_award: list[str]  # Achievement IDs to award
    challenges_to_complete: list[str]  # Challenge IDs to mark complete
    # Summary flags
    had_changes: bool  # True if any state changed
    evaluation_duration_ms: float  # Performance tracking


# =============================================================================
# Ledger Types (Economy Stack - Phase 3)
# =============================================================================
# Used by EconomyEngine and EconomyManager for transaction history


class LedgerEntry(TypedDict):
    """A single transaction record in a kid's point ledger.

    Created by: EconomyEngine.create_ledger_entry()
    Stored in: KidData["ledger"] (list of entries)
    Managed by: EconomyManager (append, prune, persist)
    """

    timestamp: str  # ISO datetime string
    amount: float  # Transaction delta (positive=deposit, negative=withdraw)
    balance_after: float  # Balance after this transaction
    source: str  # Transaction type: "chore_approval", "reward_redemption", etc.
    reference_id: str | None  # Related entity ID (chore_id, reward_id, etc.)


# =============================================================================
# Event Payload Types (Manager-to-Manager Communication)
# =============================================================================
# Used for type-safe event payloads in BaseManager.emit() calls


class PointsChangedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_POINTS_CHANGED (past tense).

    Emitted by: EconomyManager.deposit(), EconomyManager.withdraw()
    Consumed by: GamificationManager (badge evaluation), NotificationManager
    """

    kid_id: str  # Required
    old_balance: float  # Required
    new_balance: float  # Required
    delta: float  # Required (positive for deposit, negative for withdraw)
    source: str  # Required: "chore_approval", "reward_redemption", "penalty", etc.
    reference_id: str | None  # Optional: chore_id, reward_id, etc.


class TransactionFailedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_TRANSACTION_FAILED.

    Emitted by: EconomyManager when transaction cannot complete
    Consumed by: NotificationManager (alert user)
    """

    kid_id: str  # Required
    attempted_amount: float  # Required
    current_balance: float  # Required
    failure_reason: str  # Required: "insufficient_funds", "daily_limit_exceeded", etc.
    reference_id: str | None  # Optional: reward_id, penalty_id causing the attempt


class ChoreClaimedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_CLAIMED.

    Emitted by: ChoreManager.claim()
    Consumed by: NotificationManager (parent notification)

    Phase 5 additions: chore_labels, update_stats for badge/achievement filtering.
    """

    kid_id: str  # Required
    chore_id: str  # Required
    kid_name: str  # Required: For notification display
    chore_name: str  # Required
    user_name: str  # Required (who initiated claim)
    chore_labels: list[str]  # For badge criteria filtering (e.g., "kitchen", "daily")
    update_stats: bool  # Whether this counts toward stats (False for undo/corrections)


class ChoreApprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_APPROVED.

    Emitted by: ChoreManager.approve()
    Consumed by: EconomyManager (point deposit), StatisticsManager (approval count)

    Phase 5 additions: chore_labels, multiplier_applied, previous_state, update_stats.
    Phase 6 additions: effective_date (when kid did work, for parent-lag proof stats).
    Phase 8 change: Removed streak_tally (moved to ChoreCompletedEvent).
    """

    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    points_awarded: float  # Required
    is_shared: bool  # Required
    is_multi_claim: bool  # Required
    chore_name: str  # For notification/display
    chore_labels: list[str]  # For badge criteria (e.g., "Clean 5 Kitchen chores")
    multiplier_applied: float  # For point calculation verification
    previous_state: str  # To detect re-approvals vs new approvals
    update_stats: bool  # Whether to update statistics (False for corrections)
    effective_date: str  # ISO timestamp when kid did work (last_claimed with fallbacks)
    approval_origin: str  # Optional origin hint (manual, auto_approve, auto_reset)
    notify_kid: bool  # Whether kid-facing approval notification should be sent


class ChoreCompletedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_COMPLETED.

    Emitted by: ChoreManager.approve() (after completion criteria satisfied)
    Consumed by: StatisticsManager (completion count + streak tracking)

    Completion criteria determines kid_ids:
    - INDEPENDENT: [approving_kid_id]
    - SHARED_FIRST: [approving_kid_id]
    - SHARED (all): [all assigned kid_ids] when last kid approved

    streak_tallies maps each kid_id to their calculated streak value.
    StatisticsManager writes these to period buckets with max-1-per-day guard.
    """

    chore_id: str  # Required
    kid_ids: list[str]  # Required: Kids who get completion credit
    effective_date: str  # Required: ISO timestamp when work was done
    streak_tallies: dict[str, int]  # Required: kid_id -> streak value


class ChoreMissedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_MISSED.

    Emitted by: ChoreManager._record_chore_missed()
    Consumed by: StatisticsManager (missed count + missed_streak_tally tracking)

    Phase 5: Records missed chores (automated from OVERDUE resets or manual skip).
    missed_streak_tally is the consecutive missed count, stored at chore level
    and written to daily buckets by StatisticsManager.
    """

    kid_id: str  # Required
    chore_id: str  # Required
    kid_name: str  # Required: For notification display (standard)
    missed_streak_tally: int  # Required: Consecutive missed count


class ChoreDisapprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_DISAPPROVED.

    Emitted by: ChoreManager.disapprove()
    Consumed by: GamificationManager (streak reset?), NotificationManager

    Phase 5 additions: chore_labels, previous_state, update_stats.
    """

    kid_id: str  # Required
    chore_id: str  # Required
    parent_name: str  # Required
    reason: str | None  # Optional: disapproval reason
    chore_name: str  # For notification/display
    chore_labels: list[str]  # For badge criteria filtering
    previous_state: str  # The state before disapproval (for audit/undo)
    update_stats: bool  # Whether this counts toward stats


class ChoreOverdueEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_OVERDUE.

    Emitted by: ChoreManager._check_overdue_chores()
    Consumed by: NotificationManager, GamificationManager (badge/streak impacts)

    Phase 5 addition: chore_labels for badge criteria filtering.
    """

    kid_id: str  # Required
    chore_id: str  # Required
    kid_name: str  # Required: For notification display
    chore_name: str  # Required
    days_overdue: int  # Required
    due_date: str  # Required: ISO format
    chore_labels: list[str]  # For badge criteria filtering


class ChoreRescheduledEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHORE_RESCHEDULED (not skipped).

    Emitted by: ChoreManager.skip_chore_due_date()
    Consumed by: NotificationManager (optional notification)
    """

    kid_id: str | None  # Optional: If kid-specific, else null for all assigned kids
    chore_id: str  # Required
    chore_name: str  # Required
    old_due_date: str  # Required: ISO format
    new_due_date: str  # Required: ISO format
    rescheduled_by: str  # Required: parent_name or "system"


class RewardClaimedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_REWARD_CLAIMED.

    Emitted by: RewardManager.claim()
    Consumed by: NotificationManager (parent notification)
    """

    kid_id: str  # Required
    reward_id: str  # Required
    kid_name: str  # Required: For notification display
    reward_name: str  # Required
    points: float  # Required: Cost of reward
    actions: list[dict[str, str]]  # Notification action buttons
    extra_data: dict[str, str]  # Notification extra data


class RewardApprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_REWARD_APPROVED.

    Emitted by: RewardManager.approve()
    Consumed by: NotificationManager, GamificationManager (milestone tracking?)
    """

    kid_id: str  # Required
    reward_id: str  # Required
    reward_name: str  # Required
    points_spent: float  # Required
    parent_name: str  # Required


class RewardDisapprovedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_REWARD_DISAPPROVED.

    Emitted by: RewardManager.disapprove()
    Consumed by: NotificationManager
    """

    kid_id: str  # Required
    reward_id: str  # Required
    reward_name: str  # Required
    parent_name: str  # Required
    reason: str | None  # Optional: disapproval reason


class BadgeEarnedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BADGE_EARNED.

    Emitted by: GamificationManager._apply_badge_result()
    Consumed by:
        - EconomyManager: points, multiplier, bonuses, penalties
        - RewardManager: reward grants (free)
        - NotificationManager: kid/parent notifications

    This is the "Award Manifest" - GamificationManager builds it and domain
    experts (Banker, Inventory) pick up their respective items.
    """

    # Required fields
    kid_id: str
    badge_id: str
    kid_name: str  # For notification display
    badge_name: str

    # The Award Manifest (all handled by listeners, not GamificationManager)
    points: float  # EconomyManager deposits
    multiplier: float | None  # EconomyManager updates (Banker owns currency rules)
    reward_ids: list[str]  # RewardManager grants (free, cost=0)
    bonus_ids: list[str]  # EconomyManager applies
    penalty_ids: list[str]  # EconomyManager applies


class BadgeRevokedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BADGE_REVOKED (intentional removal).

    Emitted by: GamificationManager (maintenance decay, manual removal)
    Consumed by: NotificationManager
    """

    kid_id: str  # Required
    badge_id: str  # Required
    badge_name: str  # Required
    reason: str  # Required: "maintenance_decay", "manual_removal", etc.


class AchievementUnlockedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_ACHIEVEMENT_EARNED.

    Emitted by: GamificationManager.evaluate_achievements()
    Consumed by: NotificationManager
    """

    kid_id: str  # Required
    achievement_id: str  # Required
    kid_name: str  # Required: For notification display
    achievement_name: str  # Required
    milestone_reached: str  # Required: Description of what was achieved


class ChallengeCompletedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_CHALLENGE_COMPLETED.

    Emitted by: GamificationManager.evaluate_challenges()
    Consumed by: NotificationManager, EconomyManager (challenge rewards)
    """

    kid_id: str  # Required
    challenge_id: str  # Required
    kid_name: str  # Required: For notification display
    challenge_name: str  # Required
    points_awarded: float  # Required
    completion_date: str  # Required: ISO format


class PenaltyAppliedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_PENALTY_APPLIED.

    Emitted by: EconomyManager.apply_penalty() (or PenaltyManager)
    Consumed by: NotificationManager, GamificationManager (badge impacts?)
    """

    kid_id: str  # Required
    penalty_id: str  # Required
    penalty_name: str  # Required
    points_deducted: float  # Required
    parent_name: str  # Required
    reason: str | None  # Optional


class BonusAppliedEvent(TypedDict, total=False):
    """Event payload for SIGNAL_SUFFIX_BONUS_APPLIED.

    Emitted by: EconomyManager.apply_bonus() (or BonusManager)
    Consumed by: NotificationManager, GamificationManager (badge impacts?)
    """

    kid_id: str  # Required
    bonus_id: str  # Required
    bonus_name: str  # Required
    points_added: float  # Required
    parent_name: str  # Required
    reason: str | None  # Optional


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "AchievementData",
    # Achievement/Challenge nested types
    "AchievementProgress",
    "AchievementProgressData",
    # Event Payload Types
    "AchievementUnlockedEvent",
    "AchievementsCollection",
    "ActivityReportResponse",
    "BadgeAwards",
    "BadgeData",
    "BadgeEarnedEvent",
    "BadgeId",
    "BadgeResetSchedule",
    "BadgeRevokedEvent",
    # Badge nested types
    "BadgeTarget",
    "BadgesCollection",
    "BadgesEarnedEntry",
    "BonusAppliedEvent",
    "BonusData",
    "BonusesCollection",
    "ChallengeCompletedEvent",
    "ChallengeDailyCounts",
    "ChallengeData",
    "ChallengeProgress",
    "ChallengeProgressData",
    "ChallengesCollection",
    "ChoreApprovedEvent",
    "ChoreClaimedEvent",
    "ChoreCompletedEvent",
    "ChoreData",
    "ChoreDisapprovedEvent",
    "ChoreId",
    "ChoreOverdueEvent",
    "ChorePerKidApplicableDays",
    "ChorePerKidDailyMultiTimes",
    # Chore nested types
    "ChorePerKidDueDates",
    "ChoreRescheduledEvent",
    "ChoresCollection",
    # Gamification Engine types (Phase 5)
    "CriterionResult",
    "EvaluationContext",
    "EvaluationResult",
    "GamificationBatchResult",
    "ISODate",
    "ISODatetime",
    "KidBadgeProgress",
    # Kid nested types
    "KidChoreDataEntry",
    "KidChoreDataPeriodEntry",
    "KidChoreDataPeriods",
    "KidChoreStats",
    "KidCumulativeBadgeProgress",
    # Main entity types
    "KidData",
    # ID type aliases
    "KidId",
    "KidRewardDataEntry",
    "KidRewardDataPeriods",
    # Collection aliases
    "KidsCollection",
    # Ledger types (Economy Stack)
    "LedgerEntry",
    "ParentData",
    "ParentsCollection",
    "PenaltiesCollection",
    "PenaltyAppliedEvent",
    "PenaltyData",
    "PeriodicStatsEntry",
    "PointsChangedEvent",
    "ReportDailyBlock",
    "ReportDeliveryStatus",
    "ReportRangeResult",
    "ResetApplyContext",
    "ResetBoundaryCategory",
    "ResetContext",
    "ResetDecision",
    "ResetTrigger",
    "RewardApprovedEvent",
    "RewardData",
    "RewardDisapprovedEvent",
    "RewardId",
    "RewardsCollection",
    # Schedule Engine
    "ScheduleConfig",
    "TransactionFailedEvent",
]
