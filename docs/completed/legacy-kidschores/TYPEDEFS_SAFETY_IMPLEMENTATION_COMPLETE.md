# TypedDicts Implementation Plan – Phase 1a (Deep Dive)

## Initiative snapshot

- **Name / Code**: `type_defs.py` (Phase 1a: Safety & Cleanup)
- **Target release / milestone**: **v0.5.0** (current beta)
- **Owner / driver(s)**: Strategic Planning Agent → Implementation Team
- **Status**: 🔄 IN PROGRESS — Integration phase restructured

## Summary & immediate steps

| Phase / Step                    | Description                                    | % complete | Quick notes                                  |
| ------------------------------- | ---------------------------------------------- | ---------- | -------------------------------------------- |
| Phase 1a – Design               | Complete data model enumeration                | 100%       | **409 DATA\_\* constants**, 10 entity types  |
| Phase 1a – Implementation       | Create `type_defs.py` with all TypedDicts      | 100%       | **~793 LOC**, 29 TypedDict classes created   |
| Phase 1a – Legacy Cleanup       | Remove \_LEGACY constants from production code | 100%       | ✅ **16 usages removed** from 4 files        |
| Phase 1a – Integration Analysis | Document mypy error categories                 | 100%       | ✅ **444 errors** in 9 files (see breakdown) |
| Phase 1a – Integration          | Update coordinator type hints                  | 100%       | ✅ **COMPLETE** - 0 mypy errors              |
| Phase 1a – Validation           | Validate mypy + test suite                     | 100%       | ✅ 0 mypy errors, 740/740 tests pass         |

### Key objective

Create `custom_components/kidschores/type_defs.py` with TypedDict definitions for all KidsChores entity data structures. This eliminates risky dictionary diving (`kid.get('ponits', 0)`) by enabling IDE autocomplete and mypy static analysis. No runtime behavior changes; purely a type safety layer.

### Summary of deep-dive analysis (January 18, 2026)

**Data Inventory Completed:**

- **409 total DATA\_\* constants** defined in `const.py`
- **10 entity types**: Kid, Parent, Chore, Badge, Reward, Penalty, Bonus, Achievement, Challenge + nested structures
- **Deeply nested structures identified**: Kid has 5 nested TypedDicts; Badge has 3; Chore has 2

**Access Pattern Analysis:**
| Entity | Bracket `[]` accesses | `.get()` accesses | Total | Risk Level |
|--------|----------------------|-------------------|-------|------------|
| `kid_info` | 77 | 95 | 172 | 🔴 High |
| `chore_info` | 84 | 210 | 294 | 🔴 High |
| `badge_info` | ~30 | ~60 | ~90 | 🟡 Medium |
| `reward_info` | ~15 | ~30 | ~45 | 🟢 Low |
| Others | ~50 | ~100 | ~150 | 🟡 Medium |

**Key Findings:**

1. **mypy baseline is clean**: `mypy coordinator.py` returns 0 errors (v1.19.0)
2. **Python 3.13+ required**: Can use modern `TypedDict` syntax without import from `typing_extensions`
3. **sensor.py is largest consumer**: 126 references to `coordinator.` data properties
4. **No TypedDicts in tests**: Tests use fixtures, won't break

### Next steps (short term)

1. ✅ Enumerate all data keys by entity type (COMPLETE - see Appendix A)
2. Create TypedDict classes in `type_defs.py` for each model (23+ classes)
3. Update `coordinator.py` data properties to return typed dicts
4. Run mypy validation (expected: 0 new errors)
5. Run full test suite (740 tests)

### Risks / blockers

| Risk                                 | Severity | Mitigation                                                             |
| ------------------------------------ | -------- | ---------------------------------------------------------------------- |
| **Circular imports**                 | � Low    | ✅ RESOLVED: `type_defs.py` imports ONLY from `const.py`, no functions |
| **NotRequired abuse**                | 🟢 Low   | ✅ RESOLVED: Fields documented, TypedDicts clean                       |
| **Runtime behavior change**          | 🟢 Low   | TypedDict is purely static analysis; no runtime enforcement            |
| **.setdefault() patterns**           | 🟢 Low   | ✅ RESOLVED: 50+ patterns work with typed collections                  |
| **Test fixture updates**             | 🟢 Low   | Tests don't construct dicts directly; use coordinator methods          |
| **\_LEGACY constants in production** | 🟢 Low   | ✅ RESOLVED: 16 usages cleaned from 4 files                            |
| **Hidden mypy errors revealed**      | 🟢 Low   | ✅ RESOLVED: 444 errors reduced to **0 errors**                        |
| **Dynamic key access patterns**      | 🟢 Low   | ✅ RESOLVED: ~10 places use proper casting and type annotations        |

### References

- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) – Data model overview
- [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Typing patterns
- [AGENTS.md](../../AGENTS.md) – KidsChores quality standards (Silver tier: 100% type hints mandatory)
- [Analysis document](./COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md#phase-1-safety--cleanup) – Strategic context

### Decisions & completion check

**Decisions captured:**

1. ✅ Use `TypedDict` (not `dataclass`) – preserves dict-like access patterns
2. ✅ Use `NotRequired` for optional fields – Python 3.11+ (we require 3.13)
3. ✅ Import from `typing` directly – no `typing_extensions` needed
4. ✅ All nested structures get their own TypedDict – better IDE support
5. ✅ Document "dynamically created" fields in docstrings – fields created by `.setdefault()`
6. ✅ **Phased integration** – Update properties first, then method signatures, then local variables
7. ✅ **Legacy cleanup complete** – All `_LEGACY` constants removed from production code (migration_pre_v50.py is the only location)
8. ✅ **Full integration approved** – User chose Option 1: Fix all 444 errors

**Completion confirmation:**

- [x] `type_defs.py` created with 23+ TypedDict classes (27 classes, ~700 LOC)
- [x] ~~**BLOCKER**~~: \_LEGACY constants removed from production code (16 usages in 4 files) ✅
- [x] ~~**BLOCKER**~~: mypy error categories documented and remediation plan created ✅
- [x] **Phase A**: TypedDict fields updated (`completed_by`, `claimed_by` added) ✅
- [x] **Phase B**: Helper signatures updated (`Mapping[str, Any]`) ✅
- [x] **Phase C**: Data properties typed: `kids_data -> KidsCollection` ✅ (revealed 412 errors)
- [x] **Phase D**: Variable annotations added (~130 across files) ✅
- [x] **Phase E**: Numeric casting added (~28 locations) ✅
- [x] **Phase F**: Method signatures updated (~25 methods) ✅
- [x] **Phase G**: Nested narrowing added (~40 locations) ✅
- [x] **Phase H**: Dynamic key access resolved (~6 locations) ✅
- [x] mypy validation on type_defs.py: 0 errors
- [x] mypy validation on all files after integration: **0 errors** (444 → 0) ✅
- [x] Full test suite passes: `pytest tests/ -v` (740 tests)
- [x] Linting passes: `./utils/quick_lint.sh --fix` (9.5+/10)
- [ ] Ready for code review + merge into feature/parent-chores branch

---

## Detailed phase tracking

### Phase 1a – Design (COMPLETE via Deep-Dive Analysis)

**Goal**: Map all entity data structures to TypedDict definitions. Enumerate every key used in `coordinator.py` by entity type.

**Status**: ✅ Analysis complete – see Appendix A for full data inventory

**Key findings from enumeration:**

| Entity Type         | Unique Keys Used | Nested Structures | Highest Usage Key             |
| ------------------- | ---------------- | ----------------- | ----------------------------- |
| **KidData**         | 186 unique       | 5 nested dicts    | `DATA_KID_NAME` (53×)         |
| **ChoreData**       | 34 unique        | 3 nested dicts    | `DATA_CHORE_NAME` (77×)       |
| **BadgeData**       | 26 unique        | 3 nested dicts    | `DATA_BADGE_NAME` (28×)       |
| **ParentData**      | 12 unique        | 0 nested          | `DATA_PARENT_NAME` (14×)      |
| **RewardData**      | 8 unique         | 0 nested          | `DATA_REWARD_NAME` (16×)      |
| **PenaltyData**     | 7 unique         | 0 nested          | `DATA_PENALTY_NAME` (10×)     |
| **BonusData**       | 7 unique         | 0 nested          | `DATA_BONUS_NAME` (11×)       |
| **AchievementData** | 18 unique        | 1 nested          | `DATA_ACHIEVEMENT_NAME` (12×) |
| **ChallengeData**   | 20 unique        | 2 nested          | `DATA_CHALLENGE_NAME` (13×)   |

**Nested TypedDict requirements identified:**

```
KidData
├── KidChoreDataEntry (per-chore tracking: state, timestamps, periods)
│   └── KidChoreDataPeriods (daily/weekly/monthly/yearly/all_time)
├── KidBadgeProgress (per-badge progress tracking)
├── KidRewardDataEntry (per-reward tracking)
│   └── KidRewardDataPeriods (daily/weekly/monthly/yearly)
├── KidCumulativeBadgeProgress (cumulative badge state)
├── KidPointStats (point earning/spending statistics)
├── KidChoreStats (chore completion statistics)
└── BadgesEarnedEntry (earned badge info)

ChoreData
├── PerKidDueDates (kid_id → due_date mapping)
├── PerKidApplicableDays (kid_id → day list mapping)
└── PerKidDailyMultiTimes (kid_id → time slots mapping)

BadgeData
├── BadgeTarget (threshold_value, target_type, maintenance_rules)
├── BadgeResetSchedule (frequency, interval, grace period)
└── BadgeAwards (points, multiplier, award_items)

AchievementData
└── AchievementProgress (kid_id → progress value mapping)

ChallengeData
├── ChallengeProgress (kid_id → progress value mapping)
└── ChallengeDailyCounts (kid_id → date → count mapping)
```

---

### Phase 1a – Implementation

**Goal**: Create `type_defs.py` with production-ready TypedDict definitions (~600 LOC, 23+ classes).

**Steps / detailed work items**

#### Step 1: Create file scaffold with imports

```python
"""Type definitions for KidsChores data structures.

Uses TypedDict for type-safe dictionary access without changing runtime behavior.
All entity data is persisted in .storage/kidschores_data as dicts; these types
document the expected structure for IDE autocomplete and mypy validation.

IMPORTANT: This file must NOT import from coordinator.py, kc_helpers.py, or
any file that imports coordinator to avoid circular dependencies.
Only import from const.py (constants) and typing (type machinery).
"""
from typing import NotRequired, TypedDict

from . import const  # Safe: const.py has no imports from this package
```

- Status: ✅ COMPLETE | Owner: Implementation lead
- **Trap to avoid**: Do NOT import `Any` – forces explicit typing

#### Step 2: Implement leaf/simple TypedDicts first (no nesting)

**2a. ParentData** (~15 fields, no nesting)

```python
class ParentData(TypedDict):
    """Type definition for a parent entity.

    Parent fields are all required once created via _create_parent().
    """
    internal_id: str  # Always present (set in _create_parent)
    name: str
    ha_user_id: str
    associated_kids: list[str]  # List of kid UUIDs
    enable_notifications: bool
    mobile_notify_service: str
    use_persistent_notifications: bool
    dashboard_language: str
    allow_chore_assignment: bool
    enable_chore_workflow: bool
    enable_gamification: bool
    linked_shadow_kid_id: NotRequired[str | None]  # Only set if shadow kid created
```

- Status: ✅ COMPLETE | Owner: Implementation lead

**2b. RewardData, PenaltyData, BonusData** (~8 fields each)

```python
class RewardData(TypedDict):
    """Type definition for a reward entity."""
    internal_id: str
    name: str
    cost: float
    description: str
    icon: str
    labels: list[str]
    # Removed in v0.5.0: timestamp field was never used

class PenaltyData(TypedDict):
    """Type definition for a penalty entity."""
    internal_id: str
    name: str
    points: float
    description: str
    icon: str
    labels: list[str]

class BonusData(TypedDict):
    """Type definition for a bonus entity."""
    internal_id: str
    name: str
    points: float
    description: str
    icon: str
    labels: list[str]
```

- Status: ✅ COMPLETE | Owner: Implementation lead
- **Trap to avoid**: Don't add fields from const.py that aren't actually used in coordinator

#### Step 3: Implement ChoreData with nested structures

**3a. Chore nested dicts**

```python
class ChorePerKidDueDates(TypedDict, total=False):
    """Per-kid due date mapping. Key is kid_id (UUID string)."""
    # Dynamic keys: kid_id -> ISO datetime string or None

class ChorePerKidApplicableDays(TypedDict, total=False):
    """Per-kid applicable weekdays. Key is kid_id (UUID string)."""
    # Dynamic keys: kid_id -> list of weekday ints (0=Mon, 6=Sun)

class ChorePerKidDailyMultiTimes(TypedDict, total=False):
    """Per-kid daily multi times. Key is kid_id (UUID string)."""
    # Dynamic keys: kid_id -> list of time strings "HH:MM"
```

- **Critical trap**: These have DYNAMIC keys (kid UUIDs). Cannot enumerate all keys.
- **Solution**: Use `TypedDict` with `total=False` and document that keys are kid_ids

**3b. ChoreData main class**

```python
class ChoreData(TypedDict):
    """Type definition for a chore entity.

    Created via build_default_chore_data() in kc_helpers.py or _create_chore().
    See kc_helpers.py:588 for canonical field list.
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
    labels: list[str]
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
    notify_on_reminder: NotRequired[bool]

    # Calendar and features
    show_on_calendar: NotRequired[bool]
    auto_approve: NotRequired[bool]

    # Completion criteria
    completion_criteria: str  # SHARED, SHARED_FIRST, INDEPENDENT
```

- Status: ✅ COMPLETE | Owner: Implementation lead
- **Trap**: `build_default_chore_data()` in kc_helpers.py is the SOURCE OF TRUTH. Cross-reference!

#### Step 4: Implement BadgeData with nested structures

**4a. Badge nested dicts**

```python
class BadgeTarget(TypedDict, total=False):
    """Badge target/threshold configuration."""
    threshold_value: float
    target_type: str  # POINTS, CHORE_COUNT, DAYS_*, STREAK_*
    maintenance_rules: NotRequired[float]  # For cumulative badges

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
```

**4b. BadgeData main class**

```python
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
```

- Status: ✅ COMPLETE | Owner: Implementation lead

#### Step 5: Implement KidData with ALL nested structures (MOST COMPLEX)

**5a. Kid chore tracking nested dicts (deepest nesting)**

```python
class KidChoreDataPeriodEntry(TypedDict, total=False):
    """Period-level stats for a single chore (daily/weekly/monthly/yearly/all_time)."""
    approved: int
    claimed: int
    disapproved: int
    overdue: int
    points: float
    longest_streak: int

class KidChoreDataPeriods(TypedDict, total=False):
    """Period containers for chore tracking. Keys are period identifiers."""
    # Dynamic keys: date strings "2026-01-18" or "all_time"
    daily: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    weekly: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    monthly: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    yearly: NotRequired[dict[str, KidChoreDataPeriodEntry]]
    all_time: NotRequired[KidChoreDataPeriodEntry]

class KidChoreDataEntry(TypedDict, total=False):
    """Per-chore tracking data for a single kid-chore combination.

    Created dynamically via setdefault() in coordinator methods.
    Key fields are added incrementally as chore is claimed/approved.
    """
    # State tracking (primary)
    state: str  # PENDING, CLAIMED, APPROVED, OVERDUE
    pending_claim_count: NotRequired[int]  # For multi-claim chores
    name: NotRequired[str]  # Denormalized chore name

    # Timestamps
    last_approved: NotRequired[str]  # ISO datetime
    last_claimed: NotRequired[str]  # ISO datetime
    last_disapproved: NotRequired[str]  # ISO datetime
    last_overdue: NotRequired[str]  # ISO datetime
    approval_period_start: NotRequired[str]  # ISO datetime

    # Statistics
    total_count: NotRequired[int]  # Deprecated? Check usage
    total_points: NotRequired[float]  # Deprecated? Check usage

    # Period tracking
    periods: NotRequired[KidChoreDataPeriods]

    # Badge references (which badges track this chore for this kid)
    badge_refs: NotRequired[list[str]]  # List of badge UUIDs

    # Streak tracking
    last_longest_streak_all_time: NotRequired[int]
```

- **Critical trap**: Fields are added INCREMENTALLY via `.setdefault()`. Most are NotRequired.
- **Trap location**: coordinator.py lines 4586-4804 (the `_update_chore_data_for_kid` method)

**5b. Kid badge progress nested dicts**

```python
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

class KidCumulativeBadgeProgress(TypedDict, total=False):
    """Cumulative badge progress tracking for a kid.

    Single structure per kid (not per-badge).
    """
    status: str  # active, grace, demoted
    cycle_points: float
    maintenance_end_date: NotRequired[str]  # ISO date
    maintenance_grace_end_date: NotRequired[str]  # ISO date
    baseline: NotRequired[float]

    # Current badge info (denormalized)
    current_badge_id: NotRequired[str]
    current_badge_name: NotRequired[str]
    current_threshold: NotRequired[float]

    # Next badge info
    next_higher_badge_id: NotRequired[str]
    next_higher_badge_name: NotRequired[str]
    next_higher_threshold: NotRequired[float]
    next_higher_points_needed: NotRequired[float]

    # Demotion info
    next_lower_badge_id: NotRequired[str]
    next_lower_badge_name: NotRequired[str]
    next_lower_threshold: NotRequired[float]

    # Highest earned
    highest_earned_badge_id: NotRequired[str]
    highest_earned_badge_name: NotRequired[str]
    highest_earned_threshold: NotRequired[float]
```

**5c. Kid reward/point tracking**

```python
class KidRewardDataPeriods(TypedDict, total=False):
    """Period containers for reward tracking."""
    daily: NotRequired[dict[str, int]]  # date -> count
    weekly: NotRequired[dict[str, int]]
    monthly: NotRequired[dict[str, int]]
    yearly: NotRequired[dict[str, int]]

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

class KidPointStats(TypedDict, total=False):
    """Point earning/spending statistics."""
    earned_all_time: float
    spent_all_time: float
    net_all_time: float
    highest_balance: NotRequired[float]

    # Period breakdowns
    earned_today: NotRequired[float]
    earned_week: NotRequired[float]
    earned_month: NotRequired[float]
    earned_year: NotRequired[float]
    spent_today: NotRequired[float]
    spent_week: NotRequired[float]
    spent_month: NotRequired[float]
    spent_year: NotRequired[float]
    net_today: NotRequired[float]
    net_week: NotRequired[float]
    net_month: NotRequired[float]
    net_year: NotRequired[float]

    # Averages
    avg_per_day_week: NotRequired[float]
    avg_per_day_month: NotRequired[float]
    avg_per_chore: NotRequired[float]

    # Streaks
    earning_streak_current: NotRequired[int]
    earning_streak_longest: NotRequired[int]

    # By source (chores, badges, bonuses, penalties)
    by_source_today: NotRequired[dict[str, float]]
    by_source_week: NotRequired[dict[str, float]]
    by_source_month: NotRequired[dict[str, float]]
    by_source_year: NotRequired[dict[str, float]]
    by_source_all_time: NotRequired[dict[str, float]]

class KidChoreStats(TypedDict, total=False):
    """Chore completion statistics."""
    # Totals by period
    approved_today: int
    approved_week: int
    approved_month: int
    approved_year: int
    approved_all_time: int
    claimed_today: NotRequired[int]
    claimed_week: NotRequired[int]
    claimed_month: NotRequired[int]
    claimed_year: NotRequired[int]
    claimed_all_time: NotRequired[int]
    disapproved_today: NotRequired[int]
    disapproved_week: NotRequired[int]
    disapproved_month: NotRequired[int]
    disapproved_year: NotRequired[int]
    disapproved_all_time: NotRequired[int]
    overdue_today: NotRequired[int]
    overdue_week: NotRequired[int]
    overdue_month: NotRequired[int]
    overdue_year: NotRequired[int]
    overdue_all_time: NotRequired[int]

    # Current state counts
    current_approved: NotRequired[int]
    current_claimed: NotRequired[int]
    current_overdue: NotRequired[int]
    current_due_today: NotRequired[int]

    # Points from chores
    total_points_from_chores_today: NotRequired[float]
    total_points_from_chores_week: NotRequired[float]
    total_points_from_chores_month: NotRequired[float]
    total_points_from_chores_year: NotRequired[float]
    total_points_from_chores_all_time: NotRequired[float]

    # Streaks
    longest_streak_all_time: NotRequired[int]
    longest_streak_week: NotRequired[int]
    longest_streak_month: NotRequired[int]
    longest_streak_year: NotRequired[int]

    # Most completed
    most_completed_chore_all_time: NotRequired[str]
    most_completed_chore_week: NotRequired[str]
    most_completed_chore_month: NotRequired[str]
    most_completed_chore_year: NotRequired[str]

    # Averages
    avg_per_day_week: NotRequired[float]
    avg_per_day_month: NotRequired[float]

class BadgesEarnedEntry(TypedDict, total=False):
    """Entry in badges_earned dict."""
    badge_name: str
    last_awarded_date: NotRequired[str]  # ISO datetime
    award_count: int
    periods: NotRequired[KidRewardDataPeriods]  # Reuse structure
```

**5d. KidData main class (FINALLY)**

```python
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
    is_shadow: NotRequired[bool]
    linked_parent_id: NotRequired[str | None]

    # Notifications
    enable_notifications: bool
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

    # Legacy chore fields (deprecated but may exist in storage)
    chore_claims_legacy: NotRequired[dict[str, int]]
    chore_streaks_legacy: NotRequired[dict[str, int]]

    # Reward tracking
    reward_data: dict[str, KidRewardDataEntry]  # reward_id -> entry

    # Penalty/bonus application tracking
    penalty_applies: dict[str, bool]  # penalty_id -> applied?
    bonus_applies: dict[str, bool]  # bonus_id -> applied?

    # Point statistics
    point_stats: NotRequired[KidPointStats]
    point_data: NotRequired[dict[str, Any]]  # Legacy period data

    # Current streak (daily approval streak)
    current_streak: NotRequired[int]
    last_streak_date: NotRequired[str]  # ISO date

    # Overdue tracking
    overdue_chores: NotRequired[list[str]]  # Chore UUIDs
    overdue_notifications: NotRequired[dict[str, str]]  # chore_id -> notification_id
    completed_by_other_chores: NotRequired[list[str]]  # Shared chores completed by others
```

- Status: ✅ COMPLETE | Owner: Implementation lead
- **This is the largest class**: 60+ fields when counting nested structures
- **Trap**: Many fields are created via `.setdefault()` at runtime, hence heavy use of `NotRequired`

#### Step 6: Implement AchievementData and ChallengeData

```python
class AchievementProgress(TypedDict, total=False):
    """Per-kid achievement progress. Key is kid_id."""
    # Dynamic keys: kid_id -> progress value (int or float)

class AchievementData(TypedDict):
    """Type definition for an achievement entity."""
    internal_id: str
    name: str
    achievement_type: str  # CHORE_COUNT, STREAK, etc.
    criteria: str  # Description of criteria
    description: str
    icon: str
    labels: list[str]

    # Target
    target_value: int
    baseline: NotRequired[int]
    selected_chore_id: NotRequired[str]  # Chore UUID for chore-specific

    # Assignment
    assigned_kids: list[str]  # Kid UUIDs

    # Progress tracking (per-kid)
    progress: dict[str, int]  # kid_id -> current progress
    current_value: NotRequired[dict[str, int]]  # kid_id -> current value (deprecated?)

    # Award status
    awarded: dict[str, bool]  # kid_id -> awarded?
    last_awarded_date: NotRequired[dict[str, str]]  # kid_id -> ISO datetime
    reward_points: float

class ChallengeDailyCounts(TypedDict, total=False):
    """Per-kid daily counts for challenges. Key is kid_id."""
    # Dynamic keys: kid_id -> dict[date_str, int]

class ChallengeProgress(TypedDict, total=False):
    """Per-kid challenge progress. Key is kid_id."""
    # Dynamic keys: kid_id -> progress value

class ChallengeData(TypedDict):
    """Type definition for a challenge entity."""
    internal_id: str
    name: str
    challenge_type: str  # CHORE_COUNT, DAILY_MIN, etc.
    criteria: str
    description: str
    icon: str
    labels: list[str]

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
    progress: dict[str, int]  # kid_id -> progress
    count: NotRequired[dict[str, int]]  # kid_id -> count (deprecated?)
    daily_counts: NotRequired[dict[str, dict[str, int]]]  # kid_id -> date -> count

    # Award status
    awarded: dict[str, bool]  # kid_id -> awarded?
    reward_points: float
```

- Status: ✅ COMPLETE | Owner: Implementation lead

#### Step 7: Create type aliases and exports

```python
# Type aliases for dynamic key dicts (improve readability)
KidId = str  # UUID string
ChoreId = str  # UUID string
BadgeId = str  # UUID string
RewardId = str  # UUID string
ISODatetime = str  # ISO 8601 datetime string
ISODate = str  # ISO 8601 date string (no time)

# Collection type aliases (for coordinator data properties)
KidsCollection = dict[KidId, KidData]
ChoresCollection = dict[ChoreId, ChoreData]
BadgesCollection = dict[BadgeId, BadgeData]
RewardsCollection = dict[RewardId, RewardData]
PenaltiesCollection = dict[str, PenaltyData]
BonusesCollection = dict[str, BonusData]
ParentsCollection = dict[str, ParentData]
AchievementsCollection = dict[str, AchievementData]
ChallengesCollection = dict[str, ChallengeData]

# Exports (for * import)
__all__ = [
    # Main entity types
    "KidData", "ParentData", "ChoreData", "BadgeData",
    "RewardData", "PenaltyData", "BonusData",
    "AchievementData", "ChallengeData",
    # Nested types
    "KidChoreDataEntry", "KidChoreDataPeriods", "KidChoreDataPeriodEntry",
    "KidBadgeProgress", "KidCumulativeBadgeProgress",
    "KidRewardDataEntry", "KidRewardDataPeriods",
    "KidPointStats", "KidChoreStats", "BadgesEarnedEntry",
    "ChorePerKidDueDates", "ChorePerKidApplicableDays", "ChorePerKidDailyMultiTimes",
    "BadgeTarget", "BadgeResetSchedule", "BadgeAwards",
    "AchievementProgress", "ChallengeProgress", "ChallengeDailyCounts",
    # Collection aliases
    "KidsCollection", "ChoresCollection", "BadgesCollection",
    "RewardsCollection", "PenaltiesCollection", "BonusesCollection",
    "ParentsCollection", "AchievementsCollection", "ChallengesCollection",
    # ID type aliases
    "KidId", "ChoreId", "BadgeId", "RewardId", "ISODatetime", "ISODate",
]
```

- Status: ✅ COMPLETE | Owner: Implementation lead

---

### Phase 1a – Legacy Cleanup (NEW - BLOCKER)

**Goal**: Remove all `_LEGACY` constant usages from production code. Per project policy, `_LEGACY` constants belong ONLY in `migration_pre_v50.py`. The migration script handles backward compatibility so production code stays clean.

**Exclusions (NOT legacy constants)**:

- `CONF_SHOW_LEGACY_ENTITIES` / `show_legacy_entities` – User-facing config option, not a legacy constant
- `sensor_legacy.py` filename – Platform name for legacy sensor entities (disabled by default)
- Comments containing "\_LEGACY" for documentation

---

#### Research Findings (Definitive Answers)

**Q1: Are `chore_claims_legacy` and `chore_streaks_legacy` still written to storage?**

✅ **CONFIRMED: Migration handles these. They should NOT be in production code.**

Evidence from `migration_pre_v50.py`:

- Lines 779-818: `_migrate_legacy_kid_chore_data_and_streaks()` reads `DATA_KID_CHORE_STREAKS_LEGACY` and migrates to `kid_chore_data[chore_id].periods[*].longest_streak`
- Lines 920-922: Reads `DATA_KID_CHORE_CLAIMS_LEGACY` and migrates to period stats
- Lines 1909-1910: `_remove_legacy_kid_fields_v50()` explicitly **deletes** these fields after migration

**Conclusion**: These fields are migrated then deleted. Production code should NOT reference them.

**Q2: Can we remove these fields entirely from production code?**

✅ **YES. The migration script:**

1. Reads legacy data during upgrade
2. Migrates to modern `kid_chore_data[chore_id]` structure
3. Deletes the legacy fields (lines 1909-1910)

The coordinator.py code that creates/cleans these fields is **redundant** because:

- New installations never have these fields
- Existing installations have them migrated + deleted by migration_pre_v50.py

**Q3: What is the canonical source for per-kid due dates?**

✅ **CONFIRMED: `chores_data[chore_id][per_kid_due_dates][kid_id]` is the source of truth.**

Evidence:

- `const.py` line 3284-3286: `DATA_KID_CHORE_DATA_DUE_DATE_LEGACY` comment says "Use chore_info[per_kid_due_dates][kid_id] instead"
- `migration_pre_v50.py` lines 2143-2155: `_cleanup_legacy_kid_chore_due_dates_v50()` **deletes** the legacy `due_date` field from `kid_chore_data`
- `kc_helpers.py` lines 1042-1044: Modern code reads from `chore_info.get(per_kid_due_dates, {}).get(kid_id)`
- `coordinator.py` lines 1507-1510: Modern code writes to `chore_info[per_kid_due_dates]`

**Due Date Architecture:**
| Chore Type | Source of Truth | Legacy Location (removed) |
|------------|-----------------|---------------------------|
| **SHARED** | `chores_data[chore_id][due_date]` | N/A |
| **INDEPENDENT** | `chores_data[chore_id][per_kid_due_dates][kid_id]` | `kids_data[kid_id][chore_data][chore_id][due_date]` ← LEGACY |

**Q4: What about flow_helpers.py using `CONF_ACHIEVEMENT_SELECTED_CHORE_ID_LEGACY`?**

✅ **Simple fix: Use modern constant. Same string value, cleaner code.**

Both constants have value `"selected_chore_id"`:

- `DATA_ACHIEVEMENT_SELECTED_CHORE_ID` (modern, line 1184)
- `CONF_ACHIEVEMENT_SELECTED_CHORE_ID_LEGACY` (legacy, line 3134)

Production code (`coordinator.py` lines 739, 1901, 1952, etc.) correctly uses `DATA_ACHIEVEMENT_SELECTED_CHORE_ID`. The flow_helpers usage is just reading existing data's `selected_chore_id` key—should use modern constant for consistency.

---

#### Cleanup Actions (Updated with Definitive Instructions)

**Step 1: Remove legacy field handling from coordinator.py (11 usages)**

| Lines     | Action      | Reason                                                       |
| --------- | ----------- | ------------------------------------------------------------ |
| 623-638   | **DELETE**  | Legacy dict cleanup. Migration already removes these fields. |
| 715-727   | **DELETE**  | Orphan cleanup for legacy dicts. Not needed post-migration.  |
| 1022-1023 | **DELETE**  | Kid creation shouldn't init legacy fields.                   |
| 1045      | **DELETE**  | Kid creation shouldn't init legacy streaks dict.             |
| 4831      | **DELETE**  | Don't write to legacy location. Modern: `per_kid_due_dates`  |
| 10502     | **REPLACE** | Check `per_kid_due_dates` instead of legacy kid_chore_data   |

**Step 2: Update options_flow.py (1 usage)**

| Line | Action      | Reason                                              |
| ---- | ----------- | --------------------------------------------------- |
| 1961 | **REPLACE** | Clear `per_kid_due_dates[kid_id]` instead of legacy |

**Step 3: Update flow_helpers.py (2 usages)**

| Lines | Action      | Reason                                                             |
| ----- | ----------- | ------------------------------------------------------------------ |
| 3290  | **REPLACE** | Use `DATA_ACHIEVEMENT_SELECTED_CHORE_ID` (same value, modern name) |
| 3414  | **REPLACE** | Use `DATA_CHALLENGE_SELECTED_CHORE_ID` (same value, modern name)   |

**Step 4: Update type_defs.py (2 usages)**

| Lines   | Action     | Reason                                                                                |
| ------- | ---------- | ------------------------------------------------------------------------------------- |
| 551-552 | **DELETE** | Remove `chore_claims_legacy` and `chore_streaks_legacy` fields from KidData TypedDict |

**Step 5: Validation**

- [x] `grep -r "_LEGACY" custom_components/kidschores/*.py | grep -v migration_pre_v50.py | grep -v SHOW_LEGACY | grep -v const.py | grep -v "#"` returns 0 results ✅
- [x] All tests pass: `pytest tests/ -v` → 740/740 passed ✅
- [x] mypy passes: `mypy custom_components/kidschores/` → 0 errors ✅
- [x] lint passes: `./utils/quick_lint.sh --fix` → All checks passed ✅

**Status: ✅ COMPLETE** (Legacy Cleanup phase finished)

---

### Phase 1a – Integration Analysis

**Status**: ✅ COMPLETE (January 18, 2026)

**Goal**: Document and categorize the mypy errors revealed by TypedDict integration. When data properties are changed from `dict[str, Any]` to typed collections (e.g., `KidsCollection`), mypy enforces type correctness on all consuming code.

**Test Methodology**: Temporarily changed 9 data property return types in coordinator.py to TypedDict collections, ran mypy, captured all errors.

---

#### Summary Statistics

| Metric                 | Value |
| ---------------------- | ----- |
| **Total errors**       | 444   |
| **Files affected**     | 9     |
| **Unique error types** | ~25   |

**Errors by File:**
| File | Error Count | % of Total |
|------|-------------|------------|
| coordinator.py | 199 | 45% |
| sensor.py | 171 | 39% |
| sensor_legacy.py | 23 | 5% |
| migration_pre_v50.py | 23 | 5% |
| button.py | 18 | 4% |
| kc_helpers.py | 5 | 1% |
| services.py | 2 | <1% |
| select.py | 2 | <1% |
| notification_action_handler.py | 1 | <1% |

---

#### Error Category Analysis (Detailed)

| Count | Error Type                                                                        | Root Cause                                       | Fix Strategy                                            | Effort |
| ----- | --------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------- | ------ |
| 47    | `Need type annotation for "kid_info"`                                             | Variables from `.get()` need explicit type       | Add `kid_info: KidData \| None = ...`                   | EASY   |
| 20    | `Unsupported operand types for + ("object" and "int")`                            | Math on untyped `.get()` returns                 | Cast to `int` or `float` after `.get()`                 | EASY   |
| 20    | `Item "int" of "int \| dict[...]" has no attribute "get"`                         | Union types from nested `.get()` chains          | Narrow with `isinstance()` or explicit checks           | MEDIUM |
| 19    | `Item "object" of "object \| Any" has no attribute "__iter__"`                    | Iteration over untyped result                    | Add type narrowing                                      | MEDIUM |
| 16    | `Need type annotation for "chore_info"`                                           | Same as kid_info                                 | Add explicit type annotation                            | EASY   |
| 12    | `No overload variant of "get" matches argument types "str", "str"`                | Default value type mismatch                      | Use correct default type or None                        | EASY   |
| 9     | `Need type annotation for "reward_info"`                                          | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 8     | `TypedDict "KidChoreDataEntry" has no key "completed_by"`                         | Missing key in TypedDict definition              | Add `completed_by: NotRequired[list[str]]` to TypedDict | EASY   |
| 7     | `Need type annotation for "progress_data"`                                        | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 6     | `TypedDict key must be a string literal`                                          | Dynamic key access `kid_info[variable]`          | Refactor to avoid dynamic keys on TypedDict             | HARD   |
| 6     | `No overload variant of "get" matches argument types "str", "dict[Never, Never]"` | Empty dict `{}` default doesn't match TypedDict  | Use typed empty dict or None                            | MEDIUM |
| 6     | `Item "object" of "object \| Any" has no attribute "get"`                         | Untyped nested dict access                       | Add intermediate type annotations                       | MEDIUM |
| 6     | `Argument 3 to "get_entity_name_or_log_error"`                                    | Helper signature expects `dict[Any, Any]`        | Update signature to `Mapping[str, Any]`                 | EASY   |
| 6     | `Argument 1 to "_reschedule_chore_next_due_date_for_kid"`                         | Method signature expects `dict[str, Any]`        | Update method signature to `ChoreData`                  | MEDIUM |
| 5     | `Argument 1 to "_reschedule_chore_next_due_date"`                                 | Same pattern                                     | Update method signature to `ChoreData`                  | MEDIUM |
| 5     | `Need type annotation for "challenge"`                                            | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 5     | `Need type annotation for "badge_info"`                                           | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 5     | `Need type annotation for "achievement"`                                          | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 4     | `Unsupported operand types for + ("object" and "float")`                          | Math on untyped `.get()` returns                 | Cast to `float` after `.get()`                          | EASY   |
| 4     | `No overload variant of "round" matches argument types`                           | Calling `round()` on untyped value               | Cast to numeric type first                              | EASY   |
| 4     | `Need type annotation for "penalty_info"`                                         | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 4     | `Need type annotation for "bonus_info"`                                           | Same pattern                                     | Add explicit type annotation                            | EASY   |
| 4     | `Incompatible types (str \| None, variable has type str)`                         | Nullable field assigned to non-nullable          | Handle None case explicitly                             | MEDIUM |
| 4     | `Argument 1 to "parse_datetime_to_utc"`                                           | Function expects `str`, got `str \| None`        | Add None guard before call                              | EASY   |
| 4     | `Argument 1 to "_get_badge_in_scope_chores_list"`                                 | Method expects `dict[Any, Any]`, got `BadgeData` | Update method signature                                 | MEDIUM |
| ~200  | (remaining variations)                                                            | Combinations of above patterns                   | Case-by-case fixes                                      | VARIES |

---

#### Fix Strategy Categories

**Category A: Variable Annotations (EASY - ~130 errors)**

Most common pattern. Simple mechanical fix.

```python
# Before (triggers "Need type annotation")
kid_info = self.kids_data.get(kid_id)

# After
kid_info: KidData | None = self.kids_data.get(kid_id)
```

**Affected variables**: `kid_info` (47), `chore_info` (16), `reward_info` (9), `progress_data` (7), `challenge` (5), `badge_info` (5), `achievement` (5), `penalty_info` (4), `bonus_info` (4), `other_kid_info` (3), etc.

---

**Category B: Numeric Type Casting (EASY - ~28 errors)**

Arithmetic on `.get()` returns fails because result is `object`.

```python
# Before (triggers "Unsupported operand types")
total = kid_info.get("points", 0) + 10

# After
points = kid_info.get("points", 0)
total = int(points) + 10  # Or: float(points) for float fields
```

---

**Category C: Helper Function Signatures (EASY - ~20 errors)**

Helpers expect `dict[Any, Any]` but receive TypedDict.

```python
# Before
def get_entity_name_or_log_error(
    entity_type: str, entity_id: str, data: dict[Any, Any]
) -> str:

# After (TypedDict is compatible with Mapping)
from typing import Mapping
def get_entity_name_or_log_error(
    entity_type: str, entity_id: str, data: Mapping[str, Any]
) -> str:
```

---

**Category D: Method Signatures (MEDIUM - ~25 errors)**

Internal methods expect `dict[str, Any]` but receive TypedDict.

```python
# Before
def _reschedule_chore_next_due_date(self, chore_info: dict[str, Any]) -> None:

# After
def _reschedule_chore_next_due_date(self, chore_info: ChoreData) -> None:
```

**Methods to update:**

- `_reschedule_chore_next_due_date`
- `_reschedule_chore_next_due_date_for_kid`
- `_check_overdue_for_chore`
- `_is_approval_after_reset_boundary`
- `_get_badge_in_scope_chores_list`
- `_reset_independent_chore_status`
- `_reset_shared_chore_status`
- etc.

---

**Category E: Missing TypedDict Keys (EASY - ~10 errors)**

TypedDict definition missing keys that code accesses.

```python
# Error: TypedDict "KidChoreDataEntry" has no key "completed_by"

# Fix: Add to type_defs.py
class KidChoreDataEntry(TypedDict, total=False):
    # ... existing fields ...
    completed_by: NotRequired[list[str]]  # Add missing field
    claimed_by: NotRequired[list[str]]    # Add missing field
```

---

**Category F: Nested Dict Type Narrowing (MEDIUM - ~40 errors)**

Chained `.get()` returns `object` which can't be iterated or accessed.

```python
# Before (triggers "__iter__" error)
for item in kid_info.get("chore_data", {}).get(chore_id, {}).get("periods", []):

# After (add intermediate annotations)
chore_data: dict[str, KidChoreDataEntry] = kid_info.get("chore_data", {})
entry: KidChoreDataEntry | None = chore_data.get(chore_id)
if entry:
    periods = entry.get("periods", [])
    for item in periods:
```

---

**Category G: Dynamic Key Access (HARD - ~6 errors)**

TypedDict requires literal string keys. Dynamic access fails.

```python
# Error: TypedDict key must be a string literal
field_key = const.DATA_KID_NAME  # Variable, not literal
value = kid_info[field_key]

# Options:
# 1. Use literal key directly
value = kid_info["name"]

# 2. Use cast (loses type safety)
from typing import cast
value = cast(str, kid_info[field_key])

# 3. Convert to regular dict (explicit opt-out)
value = dict(kid_info)[field_key]
```

---

#### Recommended Fix Order

1. **Phase A: TypedDict completeness** (10 min)
   - Add missing fields to `type_defs.py` (`completed_by`, `claimed_by`)

2. **Phase B: Helper signatures** (30 min)
   - Update `get_entity_name_or_log_error` and similar to use `Mapping[str, Any]`

3. **Phase C: Variable annotations** (2-3 hours)
   - Add type annotations to ~130 variables across all files
   - Mechanical work, low risk

4. **Phase D: Method signatures** (1 hour)
   - Update internal method signatures to accept TypedDicts

5. **Phase E: Numeric casting** (1 hour)
   - Add explicit casts where arithmetic is performed

6. **Phase F: Nested narrowing** (2 hours)
   - Add intermediate type annotations for nested access

7. **Phase G: Dynamic keys** (30 min)
   - Review 6 cases, refactor or use cast as appropriate

**Estimated total effort**: ~8-10 hours

---

## Phase 1a – Integration Execution Plan (DETAILED)

**Status**: ✅ APPROVED - Proceeding with full integration

**Strategy**: Work through errors in dependency order. Start with type_defs.py fixes, then helper signatures, then propagate types through coordinator.py, finally fix consuming files.

### Execution Phase A: TypedDict Completeness (10 min)

**Goal**: Add missing fields to `type_defs.py` revealed by error analysis.

**Step A.1**: Add missing fields to `KidChoreDataEntry`

```python
# File: custom_components/kidschores/type_defs.py
# Location: KidChoreDataEntry class (around line 92)

class KidChoreDataEntry(TypedDict, total=False):
    # ... existing fields ...
    completed_by: list[str]    # Kids who completed (for multi-claim/shared chores)
    claimed_by: list[str]      # Kids who have claimed (for multi-claim/shared chores)
```

**Validation**: `mypy custom_components/kidschores/type_defs.py` → 0 errors

---

### Execution Phase B: Helper Signatures (30 min)

**Goal**: Update helper functions to accept `Mapping[str, Any]` (TypedDict-compatible).

**Step B.1**: Update `kc_helpers.py` helper signatures

```python
# File: custom_components/kidschores/kc_helpers.py
# Add import at top
from typing import Mapping

# Update these function signatures:
# Line ~149: get_entity_name_or_log_error
def get_entity_name_or_log_error(
    entity_type: str, entity_id: str, data: Mapping[str, Any]
) -> str:

# Line ~178: validate_entity_exists_and_get_name
def validate_entity_exists_and_get_name(
    entity_type: str, entity_id: str, data: Mapping[str, Any] | None
) -> str | None:

# Line ~207: get_optional_entity_name
def get_optional_entity_name(
    entity_type: str, entity_id: str, data: Mapping[str, Any] | None
) -> str | None:
```

**Step B.2**: Update `flow_helpers.py` validation helpers (if any)

```python
# Review for any functions that take `dict[str, Any]` entity data
# Update to `Mapping[str, Any]` where TypedDict will be passed
```

**Validation**: `mypy custom_components/kidschores/kc_helpers.py` → 0 errors

---

### Execution Phase C: Coordinator Property Types (15 min)

**Goal**: Add TypedDict return types to data properties in coordinator.py.

**Step C.1**: Add imports to coordinator.py

```python
# File: custom_components/kidschores/coordinator.py
# Location: Top of file, after existing imports (around line 50)

from .type_defs import (
    # Main entity types
    KidData, ParentData, ChoreData, BadgeData,
    RewardData, PenaltyData, BonusData,
    AchievementData, ChallengeData,
    # Nested types
    KidChoreData, KidChoreDataEntry, KidChoreDataPeriods,
    BadgeProgress, BadgeMilestones,
    # Collection aliases
    KidsCollection, ChoresCollection, BadgesCollection,
    RewardsCollection, PenaltiesCollection, BonusesCollection,
    ParentsCollection, AchievementsCollection, ChallengesCollection,
)
```

**Step C.2**: Update data property return types

```python
# File: custom_components/kidschores/coordinator.py
# Location: Data property section (lines ~2598-2660)

@property
def kids_data(self) -> KidsCollection:
    """Return the kids data."""
    return self._data.get(const.DATA_KIDS, {})

@property
def parents_data(self) -> ParentsCollection:
    """Return the parents data."""
    return self._data.get(const.DATA_PARENTS, {})

@property
def chores_data(self) -> ChoresCollection:
    """Return the chores data."""
    return self._data.get(const.DATA_CHORES, {})

@property
def badges_data(self) -> BadgesCollection:
    """Return the badges data."""
    return self._data.get(const.DATA_BADGES, {})

@property
def rewards_data(self) -> RewardsCollection:
    """Return the rewards data."""
    return self._data.get(const.DATA_REWARDS, {})

@property
def penalties_data(self) -> PenaltiesCollection:
    """Return the penalties data."""
    return self._data.get(const.DATA_PENALTIES, {})

@property
def bonuses_data(self) -> BonusesCollection:
    """Return the bonuses data."""
    return self._data.get(const.DATA_BONUSES, {})

@property
def achievements_data(self) -> AchievementsCollection:
    """Return the achievements data."""
    return self._data.get(const.DATA_ACHIEVEMENTS, {})

@property
def challenges_data(self) -> ChallengesCollection:
    """Return the challenges data."""
    return self._data.get(const.DATA_CHALLENGES, {})
```

**Validation**: Run mypy to capture newly revealed errors (expected: many)

---

### Execution Phase D: Variable Annotations (2-3 hours)

**Goal**: Add explicit type annotations to variables where mypy requires them.

**Strategy**: Work file-by-file, starting with highest error count.

**Step D.1**: coordinator.py variable annotations (~50 annotations)

**Common patterns to apply:**

```python
# Pattern 1: Entity lookup with .get()
kid_info: KidData | None = self.kids_data.get(kid_id)
chore_info: ChoreData | None = self.chores_data.get(chore_id)
badge_info: BadgeData | None = self.badges_data.get(badge_id)
reward_info: RewardData | None = self.rewards_data.get(reward_id)
penalty_info: PenaltyData | None = self.penalties_data.get(penalty_id)
bonus_info: BonusData | None = self.bonuses_data.get(bonus_id)
achievement: AchievementData | None = self.achievements_data.get(ach_id)
challenge: ChallengeData | None = self.challenges_data.get(challenge_id)
parent_info: ParentData | None = self.parents_data.get(parent_id)

# Pattern 2: Other kid lookup
other_kid_info: KidData | None = self.kids_data.get(other_kid_id)

# Pattern 3: Nested chore_data access
chore_data: dict[str, KidChoreDataEntry] = kid_info.get("chore_data", {})
entry: KidChoreDataEntry | None = chore_data.get(chore_id)

# Pattern 4: Badge progress
progress: BadgeProgress | None = badge_info.get("progress", {}).get(kid_id)
```

**Step D.2**: sensor.py variable annotations (~60 annotations)

Same patterns as D.1, focused on sensor entity value extraction.

**Step D.3**: Remaining files (~20 annotations total)

- sensor_legacy.py: ~8
- migration_pre_v50.py: ~8
- button.py: ~4
- select.py: ~2
- services.py: ~2
- notification_action_handler.py: ~1

**Validation checkpoint after each file**: `mypy <file>` to track progress

---

### Execution Phase E: Numeric Casting (1 hour)

**Goal**: Add explicit casts where arithmetic operations are performed.

**Step E.1**: Identify all numeric operation errors

Common patterns:

```python
# Before (fails: Unsupported operand types for + ("object" and "int"))
points = kid_info.get("points", 0) + 10

# After (explicit cast)
points = int(kid_info.get("points", 0)) + 10

# Alternative (type-safe default)
points = kid_info.get("points") or 0
total = points + 10  # Now mypy knows points is int
```

**Step E.2**: Apply fixes to coordinator.py (~20 locations)

Focus areas:

- Points calculations
- Streak calculations
- Quantity handling
- Duration calculations

**Step E.3**: Apply fixes to sensor.py (~8 locations)

**Validation**: `mypy` should report fewer errors after this phase

---

### Execution Phase F: Method Signatures (1 hour)

**Goal**: Update internal method signatures to accept TypedDicts.

**Decision**: Keep `_create_*` and `_update_*` method signatures as `dict[str, Any]` because:

1. These methods receive user input (always `dict[str, Any]`)
2. TypedDict benefit is on READ side, not WRITE side
3. Avoids need for `cast()` at every call site

**Step F.1**: Update internal READ-only methods in coordinator.py

Methods that READ entity data but don't create/update:

```python
def _reschedule_chore_next_due_date(self, chore_info: ChoreData) -> None:
def _reschedule_chore_next_due_date_for_kid(
    self, kid_id: str, chore_id: str, chore_info: ChoreData
) -> None:
def _check_overdue_for_chore(self, chore_id: str, chore_info: ChoreData) -> None:
def _is_approval_after_reset_boundary(
    self, chore_id: str, chore_info: ChoreData, kid_id: str
) -> bool:
def _get_badge_in_scope_chores_list(self, badge_info: BadgeData) -> list[str]:
def _reset_independent_chore_status(
    self, kid_id: str, chore_id: str, chore_info: ChoreData
) -> None:
def _reset_shared_chore_status(
    self, kid_id: str, chore_id: str, chore_info: ChoreData
) -> None:
```

**Validation**: Check that callers pass the correct types

---

### Execution Phase G: Nested Type Narrowing (1.5 hours)

**Goal**: Add intermediate type annotations for complex nested access.

**Step G.1**: Identify nested access patterns

```python
# Before (fails: "__iter__" not in "object")
for period, counts in kid_info.get("chore_data", {}).get(chore_id, {}).get("periods", {}).items():

# After (add intermediate steps with annotations)
chore_data: dict[str, KidChoreDataEntry] = kid_info.get("chore_data", {})
entry: KidChoreDataEntry = chore_data.get(chore_id, {})
periods: KidChoreDataPeriods = entry.get("periods", {})
for period, counts in periods.items():
```

**Step G.2**: Apply to coordinator.py (~30 locations)

Focus areas:

- Badge progress calculations
- Chore period tracking
- Achievement milestone checks

**Step G.3**: Apply to sensor.py (~10 locations)

---

### Execution Phase H: Dynamic Key Access (30 min)

**Goal**: Handle the 6 cases where variable keys are used with TypedDict.

**Strategy options per case:**

1. **Refactor to literal keys** (preferred if possible)
2. **Use getattr pattern** for known attribute access
3. **Use cast()** as last resort (document why)

**Step H.1**: Review each dynamic key access case

```python
# Identify each case in error output
# Evaluate: Can this be refactored to use literal key?
# If not: Add cast() with comment explaining why
```

---

### Validation Checkpoints

After each phase, run validation:

```bash
# Quick check (single file)
mypy custom_components/kidschores/<file>.py

# Full integration check
mypy custom_components/kidschores/

# Test suite (ensure no regressions)
pytest tests/ -v --tb=line

# Linting
./utils/quick_lint.sh --fix
```

**Success criteria for each phase:**

- Phase A-B: mypy errors should decrease
- Phase C: Large spike initially, then decrease as D progresses
- Phase D-G: Steady decrease in errors
- Phase H: Should reach 0 errors
- Final: `mypy` = 0 errors, 740/740 tests pass, lint clean

---

### Effort Tracking

| Phase                | Est. Time | Errors Fixed   | Cumulative    |
| -------------------- | --------- | -------------- | ------------- |
| A: TypedDict fields  | 10 min    | ~10            | ~10           |
| B: Helper signatures | 30 min    | ~20            | ~30           |
| C: Property types    | 15 min    | +300 (reveals) | ~330 revealed |
| D: Variables         | 2-3 hours | ~130           | ~160 fixed    |
| E: Numeric casts     | 1 hour    | ~28            | ~188 fixed    |
| F: Method sigs       | 1 hour    | ~25            | ~213 fixed    |
| G: Nested narrowing  | 1.5 hours | ~40            | ~253 fixed    |
| H: Dynamic keys      | 30 min    | ~6             | ~259 fixed    |

**Total estimated**: 7-9 hours (slightly better than initial 8-10 estimate with improved strategy)

---

#### Decision Point (RESOLVED)

**Option 1: Full TypedDict Integration (8-10 hours)** ← **SELECTED**

- Fix all 444 errors across 9 files
- Full type safety for all data access
- Significant effort for v0.5.0 timeline

~~**Option 2: Partial Integration (2-3 hours)**~~
~~- Update helper signatures only (Category B, C)~~
~~- Add annotations to coordinator.py only (most critical)~~
~~- Leave sensor.py and others for v0.5.1~~

~~**Option 3: Defer to v0.5.1**~~
~~- `type_defs.py` is created and ready~~
~~- Legacy cleanup is complete (immediate value)~~
~~- Full integration can be done post-release~~

~~**Recommendation**: Option 3 for v0.5.0.~~

**Decision (User approved)**: Proceed with Option 1 - Full TypedDict Integration

---

#### Category 1: Variable Annotation Missing (EASY - ~70 errors)

**Pattern:**

```python
kid_info = self.kids_data.get(kid_id)  # mypy: Need type annotation
```

**Fix:**

```python
kid_info: KidData | None = self.kids_data.get(kid_id)
```

**Files affected:** coordinator.py (44+), sensor.py, button.py

#### Category 2: Helper Function Signatures (MEDIUM - ~20 errors)

**Pattern:**

```python
def get_entity_name_or_log_error(entity_type: str, entity_id: str,
                                   data: dict[Any, Any]) -> str:
# Called with: get_entity_name_or_log_error("kid", kid_id, kid_info)
# mypy: Argument 3 has incompatible type "KidData"
```

**Fix:** Update helper signature to accept TypedDicts:

```python
from typing import Mapping
def get_entity_name_or_log_error(entity_type: str, entity_id: str,
                                   data: Mapping[str, Any]) -> str:
```

#### Category 3: Dynamic Key Access (HARD - ~10 errors)

**Pattern:**

```python
field_key = const.DATA_KID_NAME  # string variable
value = kid_info[field_key]  # mypy: TypedDict key must be literal
```

**Issue:** TypedDict requires literal keys for type safety. Dynamic keys bypass the type system.

**Options:**

1. **Refactor to literal keys** – Replace variable with actual key
2. **Use cast()** – `cast(str, kid_info[field_key])` (loses safety)
3. **Use dict()** – `dict(kid_info)[field_key]` (explicit opt-out)

#### Category 4: Missing TypedDict Keys (MEDIUM - ~5 errors)

**Pattern:**

```python
kid_chore_data[chore_id].get("completed_by")  # mypy: no key "completed_by"
```

**Fix:** Add missing keys to TypedDict definition with `NotRequired`:

```python
class KidChoreDataEntry(TypedDict, total=False):
    completed_by: NotRequired[list[str]]  # Add missing key
```

#### Category 5: Nested Dict Type Narrowing (MEDIUM - ~20 errors)

**Pattern:**

```python
periods = kid_chore_data.get("periods", {})
daily = periods.get("daily", {})  # mypy: "object" has no attribute "get"
```

**Fix:** Add explicit type annotation to intermediate:

```python
periods: KidChoreDataPeriods = kid_chore_data.get("periods", {})
```

---

### Phase 1a – Integration (UPDATED - BLOCKED)

**Status:** BLOCKED until Legacy Cleanup and Integration Analysis phases complete

**Goal**: Update `coordinator.py` to use TypedDict types. **Phased approach to minimize risk.**

**Prerequisites:**

- [ ] Legacy Cleanup complete (no \_LEGACY constants in production code)
- [ ] Integration Analysis complete (error categories documented)
- [ ] Remediation strategy approved for each error category

#### Integration Step 1: Add imports (LOW RISK)

```python
# At top of coordinator.py, after existing imports
from .type_defs import (
    # Main entity types
    KidData, ParentData, ChoreData, BadgeData,
    RewardData, PenaltyData, BonusData,
    AchievementData, ChallengeData,
    # Collection aliases
    KidsCollection, ChoresCollection, BadgesCollection,
    RewardsCollection, PenaltiesCollection, BonusesCollection,
    ParentsCollection, AchievementsCollection, ChallengesCollection,
)
```

- Status: Not started | Owner: Implementation lead
- **Risk**: None – import only, no usage yet

#### Integration Step 2: Update data properties (LOW RISK)

```python
# coordinator.py lines 2598-2643
@property
def kids_data(self) -> KidsCollection:
    """Return the kids data."""
    return self._data.get(const.DATA_KIDS, {})

@property
def parents_data(self) -> ParentsCollection:
    """Return the parents data."""
    return self._data.get(const.DATA_PARENTS, {})

@property
def chores_data(self) -> ChoresCollection:
    """Return the chores data."""
    return self._data.get(const.DATA_CHORES, {})

# ... repeat for all 9 data properties
```

- Status: Not started | Owner: Implementation lead
- **Risk**: Low – only changes return type annotation
- **Impact**: ~20 lines changed
- **Trap**: After this change, `kids_data.get(kid_id)` returns `KidData | None`. All downstream code benefits from typing.

#### Integration Step 3: Update `_create_*` method signatures (MEDIUM RISK)

```python
# Example: _create_kid (line 990)
def _create_kid(self, kid_id: str, kid_data: KidData) -> None:
    # ... body unchanged

# Example: _create_chore (line 1318)
def _create_chore(self, chore_id: str, chore_data: ChoreData) -> None:
    # ... body unchanged
```

**Methods to update (8 total):**
| Method | Line | Parameter Change |
|--------|------|------------------|
| `_create_kid` | 990 | `kid_data: KidData` |
| `_create_parent` | 1064 | `parent_data: ParentData` |
| `_create_chore` | 1318 | `chore_data: ChoreData` |
| `_create_badge` | 1703 | `badge_data: BadgeData` |
| `_create_reward` | 1737 | `reward_data: RewardData` |
| `_create_bonus` | 1785 | `bonus_data: BonusData` |
| `_create_penalty` | 1832 | `penalty_data: PenaltyData` |
| `_create_achievement` | 1879 | `achievement_data: AchievementData` |
| `_create_challenge` | 1979 | `challenge_data: ChallengeData` |

- Status: Not started | Owner: Implementation lead
- **Risk**: Medium – mypy may flag type mismatches in callers
- **Trap**: `_create_*` methods are called from config flow with user input. User input is `dict[str, Any]`, not `TypedDict`. Need to either:
  1. Keep signatures as `dict[str, Any]` (loses type benefit)
  2. Add `cast()` at call sites (tedious)
  3. Use `Unpack[TypedDict]` pattern (complex)

**Decision needed**: Keep `_create_*` as `dict[str, Any]` for now; TypedDict benefit is on READ side.

#### Integration Step 4: Update `_update_*` method signatures (MEDIUM RISK)

Same pattern as create methods. **10 methods**.

- Status: Not started | Owner: Implementation lead
- **Risk**: Medium – same caller concerns

#### Integration Step 5: Update local variable annotations (DEFER - LOW PRIORITY)

```python
# Before
kid_info = self.kids_data.get(kid_id)

# After (explicit)
kid_info: KidData | None = self.kids_data.get(kid_id)

# Or: leave as-is (mypy infers from property return type)
```

**Decision**: Skip explicit local annotations. After Step 2 (property typing), mypy automatically infers `kid_info` type from `kids_data` return type. Manual annotations are redundant and add maintenance burden.

- Status: **DEFERRED** – let type inference do the work
- **Effort saved**: ~100+ lines of annotation changes

#### Integration Step 6: Update kc_helpers.py (LOW RISK)

```python
# kc_helpers.py - update build_default_chore_data return type
def build_default_chore_data(
    chore_id: str, chore_data: dict[str, Any]
) -> ChoreData:
    """..."""
```

**Functions to update:**
| Function | Line | Change |
|----------|------|--------|
| `build_default_chore_data` | 588 | Return type `ChoreData` |

- Status: Not started | Owner: Implementation lead
- **Risk**: Low – only return type change
- **Note**: Input remains `dict[str, Any]` since it comes from user input

---

### Phase 1a – Testing & Validation

**Goal**: Ensure mypy passes and all 740 tests pass.

#### Validation Step 1: Run mypy on new file

```bash
mypy custom_components/kidschores/type_defs.py
```

- Expected: 0 errors (new file, self-contained)

#### Validation Step 2: Run mypy on coordinator

```bash
mypy custom_components/kidschores/coordinator.py
```

- Expected: 0 errors (current baseline is clean)
- **Trap**: If we change `_create_*` signatures to TypedDict, callers may fail type check

#### Validation Step 3: Run mypy on entire integration

```bash
mypy custom_components/kidschores/
```

- Expected: 0 errors
- **Note**: May need to update imports in other files if they use entity data

#### Validation Step 4: Run linting

```bash
./utils/quick_lint.sh --fix
```

- Expected: 9.5+/10 score

#### Validation Step 5: Run full test suite

```bash
pytest tests/ -v --tb=line
```

- Expected: 740/740 pass
- **Runtime**: ~10 minutes

#### Validation Step 6: Smoke test in HA

- Start HA with integration
- Create kid, chore, badge via UI
- Claim and approve chore
- Check `home-assistant.log` for errors

---

## Testing & validation

### Tests executed

- [ ] Unit tests: `pytest tests/test_workflow_chores.py -v`
- [ ] Full suite: `pytest tests/ -v` (740 tests)
- [ ] Type check: `mypy custom_components/kidschores/`
- [ ] Linting: `./utils/quick_lint.sh --fix`
- [ ] Integration: Manual HA startup

### Validation success criteria

- [ ] mypy: 0 errors across all files
- [ ] Ruff/PyLint: 9.5+/10 score
- [ ] Pytest: 740/740 tests pass
- [ ] No runtime errors in HA logs

---

## Notes & follow-up

### What TypedDict does NOT change (IMPORTANT)

TypedDict is **static analysis only** — all runtime error handling must remain:

| Still Required                  | Why                                                 |
| ------------------------------- | --------------------------------------------------- | ---------------- |
| `if kid_info is None:` checks   | `.get()` still returns `T                           | None` at runtime |
| `.get(key, default)` patterns   | Storage data could be incomplete/corrupted          |
| `try/except` around data access | Migration failures, manual edits, partial writes    |
| Input validation in config flow | User input remains `dict[str, Any]`                 |
| Dynamic key existence checks    | `chore_data[chore_id]` — UUID validity not enforced |

**Do NOT remove any existing null checks, default fallbacks, or exception handlers.**

TypedDict benefits are:

- IDE autocomplete for valid keys
- mypy catching typos in key names
- Documentation of expected structure
- Compile-time error detection

---

### Critical traps identified during deep-dive

1. **Dynamic key dicts**: Many TypedDicts have dynamic keys (kid UUIDs, chore UUIDs, date strings). Use `total=False` and document the key pattern.

2. **`.setdefault()` pattern**: 50+ calls in coordinator create nested structures dynamically. All fields in those structures must be `NotRequired`.

3. **Input vs. stored data**: User input from config flow is `dict[str, Any]`. Don't try to type `_create_*` parameters as TypedDict.

4. **Deeply nested structures**: `KidData.chore_data[chore_id].periods.daily["2026-01-18"].approved` is 5 levels deep. Test IDE autocomplete works.

5. **Circular import risk**: `type_defs.py` must ONLY import from `const.py`. Never import coordinator, kc_helpers, etc.

### Effort estimate (revised)

| Task                                         | Estimated Hours |
| -------------------------------------------- | --------------- |
| Create `type_defs.py` (600 LOC, 23+ classes) | 8-12            |
| Update coordinator properties                | 2-3             |
| Update kc_helpers functions                  | 1-2             |
| mypy fixes                                   | 2-4             |
| Testing and validation                       | 2-3             |
| **Total**                                    | **15-24 hours** |

### Follow-up for Phase 2

After type_defs.py is complete and integrated:

- Phase 2 (schedule_engine.py) can use these types for pure function interfaces
- Badge `applicable_days` feature becomes easier to implement with typed ChoreData

---

## Appendix A: Complete Data Key Inventory

### A.1 KidData keys (186 unique keys used in coordinator)

<details>
<summary>Click to expand full list</summary>

**Core fields (always present after \_create_kid):**

- `DATA_KID_INTERNAL_ID` (13×)
- `DATA_KID_NAME` (53×)
- `DATA_KID_POINTS` (11×)
- `DATA_KID_POINTS_MULTIPLIER` (6×)
- `DATA_KID_BADGES_EARNED` (13×)
- `DATA_KID_REWARD_DATA` (14×)
- `DATA_KID_PENALTY_APPLIES` (11×)
- `DATA_KID_BONUS_APPLIES` (11×)
- `DATA_KID_ENABLE_NOTIFICATIONS` (4×)
- `DATA_KID_MOBILE_NOTIFY_SERVICE` (3×)
- `DATA_KID_USE_PERSISTENT_NOTIFICATIONS` (3×)

**Chore tracking (dynamically created):**

- `DATA_KID_CHORE_DATA` (41×)
- `DATA_KID_CHORE_DATA_STATE` (12×)
- `DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT` (13×)
- `DATA_KID_CHORE_DATA_LAST_APPROVED` (5×)
- `DATA_KID_CHORE_DATA_LAST_CLAIMED` (6×)
- ... (see full grep output above)

**Badge progress (dynamically created):**

- `DATA_KID_BADGE_PROGRESS` (17×)
- `DATA_KID_CUMULATIVE_BADGE_PROGRESS` (12×)
- ... (see full grep output above)

**Statistics (dynamically created):**

- `DATA_KID_CHORE_STATS` (12×)
- `DATA_KID_POINT_STATS` (4×)
- ... (see full grep output above)

</details>

### A.2 ChoreData keys (34 unique keys)

<details>
<summary>Click to expand full list</summary>

- `DATA_CHORE_NAME` (77×)
- `DATA_CHORE_ASSIGNED_KIDS` (45×)
- `DATA_CHORE_COMPLETION_CRITERIA` (35×)
- `DATA_CHORE_PER_KID_DUE_DATES` (27×)
- `DATA_CHORE_STATE` (21×)
- `DATA_CHORE_DUE_DATE` (21×)
- `DATA_CHORE_RECURRING_FREQUENCY` (12×)
- `DATA_CHORE_DAILY_MULTI_TIMES` (12×)
- ... (see full grep output above)

</details>

### A.3 BadgeData keys (26 unique keys)

<details>
<summary>Click to expand full list</summary>

- `DATA_BADGE_NAME` (28×)
- `DATA_BADGE_TARGET` (13×)
- `DATA_BADGE_TARGET_THRESHOLD_VALUE` (12×)
- `DATA_BADGE_ASSIGNED_TO` (12×)
- `DATA_BADGE_EARNED_BY` (10×)
- `DATA_BADGE_TYPE` (7×)
- ... (see full grep output above)

</details>

---

## Implementation Checklist (Ready to Start)

- [ ] Read this entire plan document
- [ ] Create `type_defs.py` file with scaffold
- [ ] Implement simple types first: Parent, Reward, Penalty, Bonus
- [ ] Implement ChoreData with nested types
- [ ] Implement BadgeData with nested types
- [ ] Implement KidData with ALL nested types (largest task)
- [ ] Implement Achievement and Challenge types
- [ ] Add type aliases and exports
- [ ] Update coordinator data properties
- [ ] Update kc_helpers build_default_chore_data
- [ ] Run mypy validation
- [ ] Run full test suite
- [ ] Code review + merge to feature/parent-chores

**Phase 2 (schedule_engine.py)**:

- After Phase 1a complete, extract `_calculate_next_due_date_from_info`, `_calculate_next_multi_daily_due`, etc.
- Use `ChoreData` TypedDict for pure function interfaces
- Effort: 24–40 hours

### Dependency notes

- **No external dependencies**: TypedDict is in `typing` (Python 3.8+)
- **No test changes required**: Tests use fixtures, not direct dict construction
- **No dashboard changes**: Dashboard reads coordinator's published sensors (dashboard helper sensor)

---

## Implementation Checklist (Ready to Start)

- [ ] Read full analysis document: [COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md](./COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md)
- [ ] Review storage schema v42 in [ARCHITECTURE.md](../ARCHITECTURE.md) to confirm data model
- [ ] Enumerate all data keys (Phase 1a design, step 1–6)
- [ ] Create `type_defs.py` with all TypedDict definitions
- [ ] Update coordinator imports and key method signatures
- [ ] Run mypy, linting, full test suite
- [ ] Code review + merge to feature branch
- [ ] Close this plan document, move to `docs/completed/`
