# Statistics Engine - Strategic Analysis

**Status**: Analysis Complete | **Decision**: Recommended BEFORE Chore Operations
**Author**: KidsChores Strategist | **Date**: 2026-01-19
**Supporting Doc**: [STATISTICS_ENGINE_DEEP_DIVE_SUP_ANALYSIS.md](./STATISTICS_ENGINE_DEEP_DIVE_SUP_ANALYSIS.md)

---

## Executive Summary

**Recommendation: YES - High Priority, Extract Statistics Engine BEFORE Chore Operations**

### Why Statistics Engine First?

1. **Quadruple Duplication Confirmed**: Chore stats, Point stats, Reward period tracking, AND Badge earning all use nearly identical nested period structures (`daily`/`weekly`/`monthly`/`yearly`)
2. **🚨 CRITICAL BUG FOUND**: Reward period data **never gets cleaned up** - storage leak requiring immediate fix
3. **Chore Operations Depends On It**: Extracting chore operations will be cleaner if statistics updates are already abstracted
4. **High Value, Low Risk**: Statistics are pure math with no business logic coupling - easier to extract and test
5. **Unified Streak Logic**: 3 separate streak implementations can collapse into 1
6. **Foundation for Future**: Achievement tracking, Challenge progress, and analytics will also benefit

### Impact Assessment

| Metric              | Current State                  | After Statistics Engine       |
| ------------------- | ------------------------------ | ----------------------------- |
| Code duplication    | ~500 lines (4 implementations) | ~150 lines (1 implementation) |
| Period update logic | 4 variations                   | 1 unified method              |
| Streak calculations | 3 implementations              | 1 unified method              |
| Retention cleanup   | Missing for Rewards!           | Integrated & consistent       |
| Test surface area   | 4 separate test patterns       | 1 comprehensive suite         |
| Future additions    | Copy/paste pattern             | Call `record_transaction()`   |

### 🚨 Issues Discovered

1. **Reward Retention Missing** (coordinator.py:3927-3988)
   - `_increment_reward_period_counter()` doesn't call `cleanup_period_data()`
   - Rewards feature is **new in this beta** - not yet in production
   - Must include retention cleanup when implementing StatisticsEngine

2. **Week Format Inconsistency**
   - Chores use: `strftime("%Y-W%V")`
   - Rewards use: `isocalendar()` formatting
   - Both resolve same but maintenance hazard

---

## 1. Evidence of Duplication

### 1.1 Chore Period Updates (coordinator.py)

**Location**: Lines 4652-4886 (`_update_chore_data_for_kid`)

```python
# Pattern 1: Chore statistics
def update_periods(increments: dict, periods: list):
    for period_key, period_id in periods:
        period_data_dict = periods_data[period_key].setdefault(
            period_id, period_default.copy()
        )
        for key, val in period_default.items():
            period_data_dict.setdefault(key, val)
        for inc_key, inc_val in increments.items():
            period_data_dict[inc_key] += inc_val

# Called with:
update_periods(
    {const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 1,
     const.DATA_KID_CHORE_DATA_PERIOD_POINTS: points_awarded},
    period_keys,  # [(daily, today_iso), (weekly, week_iso), ...]
)
```

**Structure**:

- `periods.daily[2026-01-19]`: `{approved: 1, claimed: 0, disapproved: 0, overdue: 0, points: 5.0, longest_streak: 1}`
- `periods.weekly[2026-W03]`: Same structure
- `periods.monthly[2026-01]`: Same structure
- `periods.yearly[2026]`: Same structure

### 1.2 Point Period Updates (coordinator.py)

**Location**: Lines 5268-5301 (`update_kid_points`)

```python
# Pattern 2: Point statistics (nearly identical logic)
period_entry.setdefault(
    const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE,
    {}
).update({source_id: period_entry.get(const.DATA_KID_POINT_DATA_PERIOD_BY_SOURCE, {}).get(source_id, 0.0) + delta})
```

**Structure**:

- `periods.daily[2026-01-19]`: `{points_total: 15.0, by_source: {chore_abc: 10.0, bonus_xyz: 5.0}}`
- `periods.weekly[2026-W03]`: Same structure
- `periods.monthly[2026-01]`: Same structure
- `periods.yearly[2026]`: Same structure

### 1.3 Reward Period Updates (coordinator.py)

**Location**: Lines 3927-3989 (`_increment_reward_period_counter`)

```python
# Pattern 3: Reward statistics (yet another variation)
def _get_period_entry(bucket: dict, period_id: str) -> dict:
    if period_id not in bucket:
        bucket[period_id] = {
            const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED: 0,
            const.DATA_KID_REWARD_DATA_PERIOD_APPROVED: 0,
            const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED: 0,
            const.DATA_KID_REWARD_DATA_PERIOD_POINTS: 0,
        }
    return bucket[period_id]

# Increment counter in each period bucket
daily = periods.setdefault(const.DATA_KID_REWARD_DATA_PERIODS_DAILY, {})
_get_period_entry(daily, daily_key)[counter_key] = (
    _get_period_entry(daily, daily_key).get(counter_key, 0) + amount
)
# Repeated for weekly, monthly, yearly
```

**Structure**:

- `periods.daily[2026-01-19]`: `{claimed: 1, approved: 0, disapproved: 0, points: 50}`
- `periods.weekly[2026-W03]`: Same structure
- `periods.monthly[2026-01]`: Same structure
- `periods.yearly[2026]`: Same structure

### 1.4 Common Cleanup Logic (kc_helpers.py)

**Location**: Lines 731-846 (`cleanup_period_data`)

```python
# This is already semi-generic but still requires passing explicit constants
kh.cleanup_period_data(
    self,
    periods_data=periods_data,
    period_keys={
        "daily": const.DATA_KID_CHORE_DATA_PERIODS_DAILY,
        "weekly": const.DATA_KID_CHORE_DATA_PERIODS_WEEKLY,
        "monthly": const.DATA_KID_CHORE_DATA_PERIODS_MONTHLY,
        "yearly": const.DATA_KID_CHORE_DATA_PERIODS_YEARLY,
    },
    retention_daily=self.config_entry.options.get(...),
    retention_weekly=self.config_entry.options.get(...),
    retention_monthly=self.config_entry.options.get(...),
    retention_yearly=self.config_entry.options.get(...),
)
```

---

## 2. Proposed Solution: StatisticsEngine

### 2.1 Core Design

**File**: `custom_components/kidschores/engines/statistics.py`

**Key Insight**: StatisticsEngine does NOT need ScheduleEngine - period keys are simpler than recurrence.

```python
"""Statistics Engine - Unified time-series tracking for KidsChores.

Handles all period-based (daily/weekly/monthly/yearly) data aggregation
for Chores, Points, Rewards, Badges, and future entities. Eliminates
duplication by providing a single transaction recording interface.

Integration: Injected into Coordinator at init time.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Literal
from datetime import date, timedelta
import logging

from homeassistant.util import dt as dt_util

from .. import const
from .. import kc_helpers as kh

if TYPE_CHECKING:
    from ..coordinator import KidsChoresDataCoordinator

_LOGGER = logging.getLogger(__name__)

PeriodType = Literal["daily", "weekly", "monthly", "yearly", "all_time"]

class StatisticsEngine:
    """Unified statistics tracking for all KidsChores entities."""

    def __init__(
        self,
        retention_daily: int = const.DEFAULT_RETENTION_DAILY,
        retention_weekly: int = const.DEFAULT_RETENTION_WEEKLY,
        retention_monthly: int = const.DEFAULT_RETENTION_MONTHLY,
        retention_yearly: int = const.DEFAULT_RETENTION_YEARLY,
    ):
        """Initialize StatisticsEngine with retention configuration."""
        self._retention = {
            "daily": retention_daily,
            "weekly": retention_weekly,
            "monthly": retention_monthly,
            "yearly": retention_yearly,
        }

    def get_period_keys(self) -> dict[str, str]:
        """Get current period keys in standardized format.

        Returns:
            Dict with keys: daily, weekly, monthly, yearly
            All use consistent ISO formats from const.py
        """
        now_local = kh.dt_now_local()
        today_local = kh.dt_today_local()
        return {
            "daily": today_local.isoformat(),
            "weekly": now_local.strftime(const.PERIOD_FORMAT_WEEKLY),
            "monthly": now_local.strftime(const.PERIOD_FORMAT_MONTHLY),
            "yearly": now_local.strftime(const.PERIOD_FORMAT_YEARLY),
        }

    def record_transaction(
        self,
        period_data: dict[str, Any],
        increments: dict[str, float | int],
        *,
        include_all_time: bool = False,
        auto_prune: bool = True,
    ) -> None:
        """Record a transaction across all period buckets.

        Args:
            period_data: The 'periods' dict from entity
            increments: Dict of {metric_key: value} to add
            include_all_time: Whether to also update all_time bucket
            auto_prune: Whether to clean up old data after recording
        """
        keys = self.get_period_keys()

        for period_type in ["daily", "weekly", "monthly", "yearly"]:
            self._update_bucket(period_data, period_type, keys[period_type], increments)

        if include_all_time:
            self._update_bucket(period_data, "all_time", const.PERIOD_ALL_TIME, increments)

        if auto_prune:
            self.prune_history(period_data)

    def update_streak(
        self,
        container: dict,
        streak_key: str = const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK,
        last_date_key: str | None = None,
    ) -> int:
        """Update streak calculation with unified logic.

        Rules:
        - Same day: No change, return current
        - Yesterday: Increment by 1
        - Any other gap: Reset to 1

        Returns: Current streak value after update
        """
        today = kh.dt_today_local()

        # Get last update date if tracking
        last_date = None
        if last_date_key:
            last_str = container.get(last_date_key)
            if last_str:
                try:
                    last_date = date.fromisoformat(last_str)
                except (ValueError, TypeError):
                    last_date = None

        current = container.get(streak_key, 0)

        # Same day - no change
        if last_date == today:
            return current

        # Yesterday - increment
        if last_date == today - timedelta(days=1):
            new_streak = current + 1
        else:
            # Gap or first time - reset to 1
            new_streak = 1

        container[streak_key] = new_streak
        if last_date_key:
            container[last_date_key] = today.isoformat()

        return new_streak

    def prune_history(
        self,
        period_data: dict[str, Any],
        period_keys: dict[str, str] | None = None,
    ) -> int:
        """Remove old period data based on retention config.

        Args:
            period_data: The periods dict to prune
            period_keys: Optional mapping of period type to dict key names
                        (defaults to standard naming)

        Returns: Number of entries pruned
        """
        # Uses logic from kh.cleanup_period_data but integrated
        # ... implementation details ...

    def _update_bucket(
        self,
        period_data: dict,
        period_type: str,
        period_id: str,
        increments: dict[str, float | int],
    ) -> None:
        metrics: list[str],
        operation: Literal["add", "set"],
    ) -> None:
        """Update a specific period bucket."""
        # Get or create bucket
        bucket_key = self._get_bucket_key(period_type)
        bucket = period_data.setdefault(bucket_key, {})

        # Get or create period entry
        period_entry = bucket.setdefault(period_id, {})

        # Update each metric
        for metric in metrics:
            if operation == "add":
                period_entry[metric] = period_entry.get(metric, 0) + value
            elif operation == "set":
                period_entry[metric] = value

    def _get_bucket_key(self, period_type: PeriodType) -> str:
        """Map logical period type to storage constant."""
        mapping = {
            "daily": "daily",     # Could map to const.DATA_KID_CHORE_DATA_PERIODS_DAILY
            "weekly": "weekly",
            "monthly": "monthly",
            "yearly": "yearly",
            "all_time": "all_time",
        }
        return mapping[period_type]

    def prune_history(
        self,
        period_data: dict,
        retention_settings: dict[str, int] | None = None,
    ) -> None:
        """Unified cleanup logic for old period data.

        Replaces: kc_helpers.cleanup_period_data

        Args:
            period_data: The 'periods' dict to clean
            retention_settings: Optional override {daily: 30, weekly: 12, monthly: 6, yearly: 2}
        """
        # Get retention from settings or use defaults
        settings = retention_settings or self.coordinator.get_retention_settings()

        today_local = self.scheduler.get_today_local()

        # Daily cleanup
        cutoff_daily = self.scheduler.add_interval(
            today_local.isoformat(),
            "days",
            -settings.get("daily", const.DEFAULT_RETENTION_DAILY),
        )
        self._prune_bucket(period_data, "daily", cutoff_daily)

        # Weekly cleanup
        cutoff_weekly = self.scheduler.add_interval(
            today_local.isoformat(),
            "weeks",
            -settings.get("weekly", const.DEFAULT_RETENTION_WEEKLY),
        )
        self._prune_bucket(period_data, "weekly", cutoff_weekly)

        # Monthly cleanup
        cutoff_monthly = self.scheduler.add_interval(
            today_local.isoformat(),
            "months",
            -settings.get("monthly", const.DEFAULT_RETENTION_MONTHLY),
        )
        self._prune_bucket(period_data, "monthly", cutoff_monthly)

        # Yearly cleanup
        cutoff_yearly = self.scheduler.add_interval(
            today_local.isoformat(),
            "years",
            -settings.get("yearly", const.DEFAULT_RETENTION_YEARLY),
        )
        self._prune_bucket(period_data, "yearly", cutoff_yearly)

    def _prune_bucket(
        self,
        period_data: dict,
        period_type: PeriodType,
        cutoff: str,
    ) -> None:
        """Remove old entries from a specific bucket."""
        bucket_key = self._get_bucket_key(period_type)
        bucket = period_data.get(bucket_key, {})

        for period_id in list(bucket.keys()):
            if period_id < cutoff:
                del bucket[period_id]

    def calculate_streak(
        self,
        daily_data: dict[str, dict],
        metric_key: str = "approved_count",
    ) -> int:
        """Calculate current streak from daily period data.

        Used for: Chore streaks, Point earning streaks

        Args:
            daily_data: The periods['daily'] dict
            metric_key: Which counter to check (e.g., 'approved_count')

        Returns:
            Current streak count (consecutive days with metric > 0)
        """
        today_local = self.scheduler.get_today_local()
        streak = 0

        # Walk backwards from today
        current_date = today_local
        while True:
            date_iso = current_date.isoformat()
            day_entry = daily_data.get(date_iso, {})

            if day_entry.get(metric_key, 0) > 0:
                streak += 1
                current_date = current_date - timedelta(days=1)
            else:
                break

        return streak
```

### 2.2 Integration Pattern

**Before (in coordinator.py)**:

```python
# Chore approved - update periods manually
def _update_chore_data_for_kid(self, kid_id, chore_id, points_awarded, *, state=None):
    # ... 100+ lines of period update logic ...

    def update_periods(increments: dict, periods: list):
        for period_key, period_id in periods:
            period_data_dict = periods_data[period_key].setdefault(
                period_id, period_default.copy()
            )
            for inc_key, inc_val in increments.items():
                period_data_dict[inc_key] += inc_val

    update_periods(
        {const.DATA_KID_CHORE_DATA_PERIOD_APPROVED: 1,
         const.DATA_KID_CHORE_DATA_PERIOD_POINTS: points_awarded},
        period_keys,
    )
```

**After (in coordinator.py)**:

```python
# Chore approved - delegate to StatisticsEngine
def _update_chore_data_for_kid(self, kid_id, chore_id, points_awarded, *, state=None):
    kid_chore_periods = kid_info['chore_data'][chore_id]['periods']

    # Record chore completion
    self.stats_engine.record_transaction(
        period_data=kid_chore_periods,
        value=1,
        metrics=['approved_count']
    )

    # Record points from chore
    self.stats_engine.record_transaction(
        period_data=kid_chore_periods,
        value=points_awarded,
        metrics=['points_total']
    )
```

---

## 3. Benefits vs Risks

### 3.1 Benefits

| Benefit                   | Impact                    | Evidence                                                         |
| ------------------------- | ------------------------- | ---------------------------------------------------------------- |
| **Eliminate Duplication** | 300+ lines removed        | 3 separate implementations → 1                                   |
| **Unified Time Logic**    | No drift between entities | ScheduleEngine provides single source of truth for period keys   |
| **Consistent Retention**  | Same cleanup everywhere   | `prune_history()` replaces `kh.cleanup_period_data()`            |
| **Shared Streak Calc**    | Chores + Badges + Points  | `calculate_streak()` eliminates 3 variations                     |
| **Future-Proof**          | Easy to add new entities  | Badge stats, Challenge tracking just call `record_transaction()` |
| **Testable**              | Single test suite         | Mock ScheduleEngine, verify all period types in one place        |

### 3.2 Risks

| Risk                   | Severity | Mitigation                                              |
| ---------------------- | -------- | ------------------------------------------------------- |
| Breaking existing data | HIGH     | Migration required to ensure backwards compatibility    |
| Coordinator coupling   | MEDIUM   | Pass coordinator explicitly, limit surface area         |
| Performance overhead   | LOW      | Method calls are cheap; current code also loops periods |
| Test complexity        | LOW      | Easier to test single implementation than 3 variations  |

---

## 4. Order of Operations: Why Before Chore Operations

### 4.1 Current Plan (Per COORDINATOR_CHORE_OPERATIONS_IN-PROCESS.md)

**Phase 2.5a: Chore Operations** - Extract 20+ methods (~1,200 lines):

- ✅ `_update_chore_data_for_kid` (lines 4610-4886) - **DEPENDS ON STATISTICS**
- ✅ `_recalculate_chore_stats_for_kid` (lines 4887-5405) - **READS STATISTICS**
- ✅ Methods like `_process_chore_claim`, `_process_chore_approval` - **UPDATE STATISTICS**

**Problem**: If we extract Chore Operations first:

1. We copy the existing duplicated period update logic into ChoreOperations
2. Then we have to refactor it again when StatisticsEngine is added
3. Double the work, double the test updates

### 4.2 Revised Plan: Statistics First

**Sequence**:

1. **Phase 2.5-STATS (NEW)**: Extract Statistics Engine (1-2 weeks)
   - Create `engines/statistics.py`
   - Update Chore period updates to use `record_transaction()`
   - Update Point period updates to use `record_transaction()`
   - Update Reward period updates to use `record_transaction()`
   - Replace `kh.cleanup_period_data()` with `stats_engine.prune_history()`
   - Test suite: 782 tests must pass unchanged

2. **Phase 2.5a**: Extract Chore Operations (2-3 weeks)
   - Now ChoreOperations just calls `self.stats_engine.record_transaction()`
   - Cleaner extraction, less code duplication
   - Easier to test (mock stats_engine instead of inspecting period dicts)

3. **Phase 2.5b-f**: Extract remaining operations (4-6 weeks)
   - Badge, Reward, Achievement, Points, Notification operations
   - All benefit from StatisticsEngine foundation

### 4.3 Comparison

| Approach             | Time to Complete | Code Duplication                | Test Complexity      | Risk   |
| -------------------- | ---------------- | ------------------------------- | -------------------- | ------ |
| **Chores First**     | 8-10 weeks       | Medium (copied then refactored) | High (change twice)  | Medium |
| **Statistics First** | 8-10 weeks       | Low (done once)                 | Medium (change once) | Low    |

**Winner**: Statistics First saves double-work risk and reduces risk of introducing bugs during refactor.

---

## 5. Implementation Plan (Revised with Deep Dive Findings)

See `STATISTICS_ENGINE_IN-PROCESS.md` (to be created) for detailed plan.
See `STATISTICS_ENGINE_DEEP_DIVE_SUP_ANALYSIS.md` for complete validation.

### Phase 0: Pre-Work (2 days) - **NEW FROM DEEP DIVE**

- [ ] Add `const.py` constants for period formats:
  - `PERIOD_FORMAT_DAILY = "%Y-%m-%d"`
  - `PERIOD_FORMAT_WEEKLY = "%Y-W%V"`
  - `PERIOD_FORMAT_MONTHLY = "%Y-%m"`
  - `PERIOD_FORMAT_YEARLY = "%Y"`
- [ ] Document current test coverage for period-related logic
- [ ] Verify all 4 entity types' period structures are compatible
- [ ] Note: Rewards retention will be added as part of StatisticsEngine (new feature, not in production yet)

### Phase 1: Engine Creation (5-7 days)

- [ ] Create `engines/` directory with `__init__.py`
- [ ] Create `engines/statistics.py` with `StatisticsEngine` class:
  - `get_period_keys()` - unified key generation
  - `record_transaction()` - main entry point
  - `update_streak()` - unified streak logic
  - `prune_history()` - retention cleanup
- [ ] Inject into Coordinator via `__init__`
- [ ] Add unit tests (target: 95%+ coverage)
  - Basic transaction recording
  - Period key format consistency
  - Streak calculation edge cases (DST, year rollover)
  - Retention pruning

### Phase 2: Chore Integration (5-7 days)

- [ ] Replace `update_periods()` in `_update_chore_data_for_kid` with `stats.record_transaction()`
- [ ] Replace streak calculation (lines 4750-4795) with `stats.update_streak()`
- [ ] Replace `kh.cleanup_period_data()` call with `stats.prune_history()`
- [ ] Update tests to verify period data unchanged
- [ ] Validate 782 tests pass (zero regressions)

### Phase 3: Point Integration (3-5 days)

- [ ] Replace point period updates in `update_kid_points()` with `stats.record_transaction()`
- [ ] Update `_recalculate_point_stats_for_kid` to read from same structure
- [ ] Remove duplicated retention cleanup call
- [ ] Validate tests pass

### Phase 4: Reward + Badge Integration (4-5 days)

- [ ] Replace `_increment_reward_period_counter` with `stats.record_transaction()`
- [ ] **Ensure retention cleanup now happens for rewards** (fixing the leak)
- [ ] Replace `_update_badges_earned_for_kid` period logic with `stats.record_transaction()`
- [ ] Validate tests pass

### Phase 5: Cleanup & Documentation (2-3 days)

- [ ] Remove `kh.cleanup_period_data()` from `kc_helpers.py` (now deprecated)
- [ ] Update `ARCHITECTURE.md` with StatisticsEngine section
- [ ] Add migration notes if storage structure changes
- [ ] Performance benchmark before/after
- [ ] Final test run with coverage report

**Total Estimated Time**: 21-29 working days (4-5 weeks)

---

## 6. Decision Criteria (Updated with Deep Dive Findings)

### Should We Proceed?

**YES if**:

- ✅ Quadruple duplication confirmed (Chores/Points/Rewards/Badges) - **CONFIRMED**
- ✅ Similar structure across entities - **CONFIRMED** (all use daily/weekly/monthly/yearly)
- ✅ Extraction cleaner than current state - **CONFIRMED** (~500 lines removed)
- ✅ Testable in isolation - **CONFIRMED** (no ScheduleEngine dependency needed)
- ✅ Foundation for future features - **CONFIRMED** (Achievements, Challenges, Analytics)
- ✅ **Critical bug fix required** - **CONFIRMED** (Reward retention leak)

**NO if**:

- ❌ Only 1-2 uses of pattern - **FALSE** (4 confirmed, more future)
- ❌ Entities have different period structures - **FALSE** (all identical)
- ❌ Extraction introduces coupling - **MITIGATED** (stateless engine, explicit params)
- ❌ No time for 4-5 week refactor - **EVALUATE** (but saves time vs later)

**Verdict**: **PROCEED WITH STATISTICS ENGINE BEFORE CHORE OPERATIONS**

---

## 7. References

- `ARCHITECTURE.md` - Data model, storage schema
- `DEVELOPMENT_STANDARDS.md` - Engine naming conventions
- `COORDINATOR_REFACTOR_ANALYSIS_IN-PROCESS.md` - Overall refactoring strategy
- `COORDINATOR_CHORE_OPERATIONS_IN-PROCESS.md` - Chore extraction plan (will be updated)
- `kc_helpers.py` lines 731-846 - Current cleanup logic
- **NEW**: `STATISTICS_ENGINE_DEEP_DIVE_SUP_ANALYSIS.md` - Detailed validation and trap analysis

---

## Appendix A: Affected Code Locations

### Current Implementations

| File             | Method                             | Lines     | Purpose                | Retention Cleanup        |
| ---------------- | ---------------------------------- | --------- | ---------------------- | ------------------------ |
| `coordinator.py` | `_update_chore_data_for_kid`       | 4610-4886 | Chore period updates   | ✅ Yes                   |
| `coordinator.py` | `_recalculate_chore_stats_for_kid` | 4887-5405 | Chore stat aggregation | N/A (read-only)          |
| `coordinator.py` | `update_kid_points`                | 5268-5378 | Point period updates   | ✅ Yes                   |
| `coordinator.py` | `_recalculate_point_stats_for_kid` | 5408-5564 | Point stat aggregation | N/A (read-only)          |
| `coordinator.py` | `_increment_reward_period_counter` | 3927-3989 | Reward period updates  | ❌ Missing (new feature) |
| `coordinator.py` | `_update_badges_earned_for_kid`    | 6820-6920 | Badge period updates   | ✅ Yes                   |
| `kc_helpers.py`  | `cleanup_period_data`              | 731-846   | Retention cleanup      | N/A (called by above)    |

### After StatisticsEngine

| File                    | New Location           | Replaces                     | Lines Saved    |
| ----------------------- | ---------------------- | ---------------------------- | -------------- |
| `engines/statistics.py` | `record_transaction()` | All 4 period update patterns | ~350           |
| `engines/statistics.py` | `update_streak()`      | 3 streak implementations     | ~80            |
| `engines/statistics.py` | `prune_history()`      | `kh.cleanup_period_data()`   | ~120           |
| **Total**               |                        |                              | **~550 lines** |

---

## Appendix B: Test Strategy (Updated)

### Test Scenarios

1. **Basic Transaction Recording**
   - Record single chore approval → verify all 4 period buckets updated
   - Record multiple approvals same day → verify increments work
   - Record points award → verify float precision maintained (DATA_FLOAT_PRECISION)

2. **Period Key Generation**
   - Verify consistent format across all entity types
   - Test week boundary (Sunday→Monday) consistent
   - Test year boundary (Dec 31 → Jan 1)

3. **Streak Calculation (Unified)**
   - Same day update → no change
   - Yesterday update → increment
   - Gap > 1 day → reset to 1
   - DST transition handling
   - Year rollover handling

4. **Retention Cleanup**
   - Create period data spanning 2 years
   - Call `prune_history()` with default settings
   - Verify old data deleted, recent data kept
   - **NEW**: Verify rewards now get cleaned up

5. **Integration with Coordinator**
   - Use existing test scenarios (Stårblüm Family)
   - Run full test suite (782 tests)
   - Verify NO behavior changes
   - Snapshot comparison of period data structures

### Coverage Target

- **Unit tests**: 95%+ for StatisticsEngine class
- **Integration tests**: All existing coordinator tests must pass (782)
- **Edge cases**: Timezone boundaries, DST transitions, leap years
- **Regression**: Zero tolerance for existing test failures

---

## Next Steps

1. ✅ **Deep Dive Complete**: See `STATISTICS_ENGINE_DEEP_DIVE_SUP_ANALYSIS.md`
2. **Create Implementation Plan**: `STATISTICS_ENGINE_IN-PROCESS.md` with full phase breakdown
3. **Prioritize Hotfix**: Consider fixing reward retention leak before full refactor
4. **Update Chore Operations Plan**: Modify `COORDINATOR_CHORE_OPERATIONS_IN-PROCESS.md` to depend on StatisticsEngine
5. **User Approval**: Confirm statistics-first approach before implementation

---

**Status**: Deep dive analysis complete. Awaiting user approval to proceed.
**Critical Finding**: Reward period data retention leak must be addressed.
**Next Document**: `STATISTICS_ENGINE_IN-PROCESS.md` (detailed implementation plan)
