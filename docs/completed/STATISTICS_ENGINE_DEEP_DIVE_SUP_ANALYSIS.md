# Statistics Engine - Deep Dive Analysis (Supporting Document)

**Parent Document**: `STATISTICS_ENGINE_ANALYSIS_IN-PROCESS.md`
**Purpose**: Comprehensive validation, opportunity identification, and trap analysis
**Date**: 2026-01-19

---

## 1. Codebase Validation ✓ CONFIRMED

### 1.1 Duplication Pattern Matrix

| Entity Type       | Period Update Location             | Lines     | Period Keys                          | Retention Cleanup                  |
| ----------------- | ---------------------------------- | --------- | ------------------------------------ | ---------------------------------- |
| **Chores**        | `_update_chore_data_for_kid`       | 4660-4885 | daily/weekly/monthly/yearly/all_time | ✅ Uses `kh.cleanup_period_data()` |
| **Points**        | `update_kid_points`                | 5313-5378 | daily/weekly/monthly/yearly          | ✅ Uses `kh.cleanup_period_data()` |
| **Rewards**       | `_increment_reward_period_counter` | 3927-3988 | daily/weekly/monthly/yearly          | ❌ **NO CLEANUP** - Trap!          |
| **Badges Earned** | `_update_badges_earned_for_kid`    | 6845-6911 | daily/weekly/monthly/yearly          | ✅ Uses `kh.cleanup_period_data()` |

**Finding**: Reward period data doesn't have cleanup - this is a **new feature in beta** (not production). StatisticsEngine will add retention cleanup.

### 1.2 Period Key Generation Patterns (Potential Inconsistency)

```python
# Chores (coordinator.py:4660-4664) - Uses strftime "%Y-W%V"
today_local_iso = today_local.isoformat()
week_local_iso = now_local.strftime("%Y-W%V")
month_local_iso = now_local.strftime("%Y-%m")
year_local_iso = now_local.strftime("%Y")

# Rewards (coordinator.py:3943-3946) - Uses isocalendar() directly
daily_key = now.strftime("%Y-%m-%d")
weekly_key = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"  # Different format!
monthly_key = now.strftime("%Y-%m")
yearly_key = now.strftime("%Y")
```

**⚠️ TRAP IDENTIFIED**: Week format inconsistency:

- Chores use: `strftime("%Y-W%V")` → `"2026-W03"` (ISO week, respects locale)
- Rewards use: `isocalendar()` → `"2026-W03"` (ISO week, explicit)

Both resolve to same value, but different code paths = maintenance hazard. StatisticsEngine must unify.

### 1.3 Streak Calculation Locations

| Feature                    | Method                                 | Lines     | Pattern                 |
| -------------------------- | -------------------------------------- | --------- | ----------------------- |
| **Chore Streaks**          | `_update_chore_data_for_kid`           | 4750-4780 | yesterday + 1 or 1      |
| **Achievement Streaks**    | `_update_streak_progress`              | 8911-8940 | yesterday + 1 or 1      |
| **Badge Day Cycles**       | `_manage_cumulative_badge_maintenance` | 6537      | Progress counter        |
| **kc_helpers Streak Read** | `get_today_chore_and_point_progress`   | 898-903   | Reads from daily period |

**Analysis**: Two distinct streak calculation implementations:

1. `_update_chore_data_for_kid` (embedded in period update)
2. `_update_streak_progress` (standalone helper for achievements)

Both use same logic but different data structures. **HIGH VALUE** extraction target.

---

## 2. High-Value Opportunities

### 2.1 Unified Streak Engine (Must-Have)

**Current State**: 3 separate implementations reading/writing streak data
**Opportunity**: Single `StatisticsEngine.update_streak()` method

```python
# Proposed unified interface
def update_streak(
    self,
    container: dict,  # periods or progress dict
    streak_key: str = DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK,
    last_date_key: str = DATA_KID_LAST_STREAK_DATE,
    reference_date: date | None = None,
) -> int:
    """Update streak, returning new streak value.

    Rules:
    - Same day: No change
    - Yesterday: Increment
    - Any other: Reset to 1

    Returns: Current streak count after update
    """
```

**Impact**:

- Eliminates ~80 lines of duplicated streak logic
- Single test suite for streak edge cases (DST, year rollover, etc.)
- Future: Weekly/Monthly streak patterns (streak across weeks, not days)

### 2.2 Period Aggregation Queries (Nice-to-Have)

**Current State**: Dashboard helper manually aggregates period data
**Opportunity**: Built-in aggregation methods

```python
# Proposed API
def aggregate_periods(
    self,
    periods_data: dict,
    period_type: Literal["daily", "weekly", "monthly", "yearly"],
    field: str,
    operation: Literal["sum", "max", "min", "avg", "count"],
    limit: int = 7,  # Last N periods
) -> float:
    """Aggregate field across periods.

    Example: Sum of approved chores in last 7 days
    """
```

**Impact**:

- Dashboard helper simplification
- Future analytics features (graphs, trends)
- Consistent aggregation logic

### 2.3 Transaction History (Future Foundation)

**Current State**: Period data only stores aggregates, not individual events
**Opportunity**: Optional transaction log for auditing

```python
class StatisticsEngine:
    def record_transaction(
        self,
        ...,
        log_transaction: bool = False,  # Optional detailed logging
    ):
        if log_transaction:
            self._append_to_history(entity_type, entity_id, ...)
```

**Impact**:

- Undo capability for accidental approvals
- Detailed audit trail for parent review
- Not v1 requirement, but architecture should allow it

---

## 3. Traps & Pitfalls to Avoid

### 3.1 ⚠️ MEDIUM: Reward Retention Missing

**Problem**: `_increment_reward_period_counter()` doesn't call `cleanup_period_data()`
**Location**: coordinator.py lines 3927-3988
**Context**: Rewards is a **new feature in this beta** - not yet in production

**Solution in StatisticsEngine**:

- `record_transaction()` must accept retention config
- Auto-prune on every write (or batch via scheduled job)
- No migration needed - feature is new

### 3.2 ⚠️ HIGH: Week Format String Variation

**Problem**: Two different ways to generate week keys
**Locations**:

- `coordinator.py:4662` uses `strftime("%Y-W%V")`
- `coordinator.py:3944` uses `f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"`

**Solution in StatisticsEngine**:

- Single `_get_period_keys()` method
- Centralized format strings in `const.py`:
  ```python
  PERIOD_FORMAT_DAILY = "%Y-%m-%d"
  PERIOD_FORMAT_WEEKLY = "%Y-W%V"  # Single source of truth
  PERIOD_FORMAT_MONTHLY = "%Y-%m"
  PERIOD_FORMAT_YEARLY = "%Y"
  ```

### 3.3 ⚠️ MEDIUM: All-Time Period Special Case

**Problem**: Chores have `all_time` period bucket, others don't
**Evidence**:

- Chores: `DATA_KID_CHORE_DATA_PERIODS_ALL_TIME` (line 4678)
- Points/Rewards/Badges: No all_time period

**Solution**:

- StatisticsEngine should support optional `all_time` period
- Configuration per entity type: `include_all_time: bool = False`
- Default to False for backwards compatibility

### 3.4 ⚠️ MEDIUM: Timezone Boundary Edge Cases

**Problem**: Period key generation uses local time, but streak logic uses dates
**Potential Issue**: 11:30 PM approval → streak calculates for "today" → midnight passes → streak broken?

**Current Mitigation**: Already using `dt_today_local()` consistently
**Verify in Tests**: DST transition scenarios, year-end rollover

### 3.5 ⚠️ LOW: Float Precision in Period Totals

**Problem**: Points are floats with precision handling scattered
**Evidence**: `const.DATA_FLOAT_PRECISION` used in multiple places
**Solution**: StatisticsEngine enforces precision on all float operations

---

## 4. Dependency Analysis

### 4.1 Schedule Engine Integration

**Current Import**: `from .schedule_engine import snap_to_weekday`
**StatisticsEngine Needs**:

- `snap_to_weekday` for applicable day filtering (not direct dependency)
- Period key generation (can be self-contained)

**Recommendation**: StatisticsEngine does NOT need ScheduleEngine

- Period keys are simpler than recurrence patterns
- Avoid unnecessary coupling
- Update original analysis: Remove ScheduleEngine dependency claim

### 4.2 Coordinator Integration Points

StatisticsEngine will be called from:

| Method                             | Purpose             | Frequency |
| ---------------------------------- | ------------------- | --------- |
| `_update_chore_data_for_kid`       | Chore state changes | High      |
| `update_kid_points`                | Points earned/spent | High      |
| `_increment_reward_period_counter` | Reward claims       | Medium    |
| `_update_badges_earned_for_kid`    | Badge awards        | Low       |
| `_recalculate_chore_stats_for_kid` | Stats aggregation   | Medium    |
| `_recalculate_point_stats_for_kid` | Stats aggregation   | Medium    |

**Injection Pattern**:

```python
class KidsChoresDataCoordinator:
    def __init__(self, ...):
        self.stats = StatisticsEngine(
            retention_config=self._get_retention_config()
        )
```

### 4.3 Test Impact Assessment

**Current Test Count**: 782 tests
**Tests Likely Affected**:

- `test_workflow_*.py` - Verify entity states (should pass unchanged)
- `test_chore_*.py` - Chore state transitions
- `test_badge_*.py` - Badge earning periods
- `test_options_flow_*.py` - Retention settings

**Test Strategy**:

1. Phase 1: New StatisticsEngine unit tests (add ~50-80 tests)
2. Phase 2-4: Existing tests must pass without modification
3. Snapshot tests may need update if period data structure changes

---

## 5. Enhanced Implementation Phases

### Phase 0: Pre-Work (2 days) - NEW

- [ ] Create `const.py` additions:
  - `PERIOD_FORMAT_*` constants
  - `STATISTICS_*` constants for new keys
- [ ] Verify all 4 entity types use consistent period structure
- [ ] Document current test coverage for period-related logic
- [ ] **Fix reward retention leak** in current code (hotfix before refactor)

### Phase 1: Core Engine (5-7 days)

- [ ] Create `engines/` directory structure
- [ ] Create `engines/__init__.py` with exports
- [ ] Create `engines/statistics.py` with:
  - `StatisticsEngine` class
  - `record_transaction()` - main entry point
  - `prune_history()` - retention cleanup
  - `update_streak()` - unified streak calculation
  - `get_period_keys()` - centralized key generation
- [ ] Unit tests: 95%+ coverage target
- [ ] Type hints: 100% with strict mypy

### Phase 2: Chore Integration (5-7 days)

- [ ] Refactor `_update_chore_data_for_kid` to use `stats.record_transaction()`
- [ ] Refactor streak calculation to use `stats.update_streak()`
- [ ] Verify `_recalculate_chore_stats_for_kid` still works
- [ ] Run full test suite (782 tests)
- [ ] Verify chore period data unchanged (snapshot comparison)

### Phase 3: Point Integration (3-5 days)

- [ ] Refactor `update_kid_points` to use `stats.record_transaction()`
- [ ] Verify `_recalculate_point_stats_for_kid` still works
- [ ] Remove duplicated retention cleanup call
- [ ] Run full test suite

### Phase 4: Reward + Badge Integration (3-5 days)

- [ ] Refactor `_increment_reward_period_counter` to use `stats.record_transaction()`
- [ ] **Add retention cleanup to rewards** (fixing the leak)
- [ ] Refactor `_update_badges_earned_for_kid` to use `stats.record_transaction()`
- [ ] Run full test suite

### Phase 5: Cleanup & Documentation (2-3 days)

- [ ] Remove `kh.cleanup_period_data()` from `kc_helpers.py`
- [ ] Update `ARCHITECTURE.md` with StatisticsEngine section
- [ ] Add migration notes for storage changes (if any)
- [ ] Performance benchmarking
- [ ] Final test run with coverage report

---

## 6. Risk Assessment Matrix

| Risk                           | Likelihood | Impact | Mitigation                     |
| ------------------------------ | ---------- | ------ | ------------------------------ |
| Breaking existing period data  | Low        | HIGH   | Extensive snapshot testing     |
| Streak calculation regression  | Medium     | Medium | Dedicated streak test suite    |
| Retention cleanup changes data | Low        | Medium | Backup before migration        |
| Type errors in refactor        | Medium     | Low    | Strict mypy, gradual migration |
| Test flakiness from timing     | Low        | Low    | Use frozen time in tests       |
| Performance regression         | Low        | Low    | Benchmark before/after         |

---

## 7. Success Metrics

| Metric                             | Current | Target | Notes                         |
| ---------------------------------- | ------- | ------ | ----------------------------- |
| Period update implementations      | 4       | 1      | Single `record_transaction()` |
| Streak calculation implementations | 3       | 1      | Single `update_streak()`      |
| Lines of duplicated code           | ~450    | ~150   | After extraction              |
| Test coverage (new code)           | N/A     | 95%+   | StatisticsEngine              |
| Existing tests passing             | 782     | 782    | No regressions                |
| Type hint coverage                 | N/A     | 100%   | Strict mypy                   |

---

## 8. Recommended Changes to Original Plan

Based on this deep dive, update `STATISTICS_ENGINE_ANALYSIS_IN-PROCESS.md`:

1. **Remove ScheduleEngine dependency** - Not needed for period keys
2. **Add Phase 0** - Pre-work for constants and reward hotfix
3. **Highlight reward retention leak** as critical fix
4. **Add unified streak engine** as must-have feature
5. **Add period key format unification** as explicit goal
6. **Update timeline**: 3-4 weeks → 4-5 weeks (adding Phase 0)

---

## 9. Decision Required

**Proceed with Statistics Engine extraction?**

✅ **YES** - High confidence based on:

- Quadruple duplication confirmed (Chores/Points/Rewards/Badges)
- Critical bug found (Reward retention leak)
- Clear extraction boundary (period operations)
- High value streak unification opportunity
- Foundation for future features

**Recommended Next Step**: Create `STATISTICS_ENGINE_IN-PROCESS.md` with detailed implementation plan incorporating these findings.

---

## Appendix: Code References

### A. Chore Period Update (coordinator.py:4697-4717)

```python
def update_periods(increments: dict, periods: list):
    for period_key, period_id in periods:
        period_data_dict = periods_data[period_key].setdefault(
            period_id, period_default.copy()
        )
        for key, val in period_default.items():
            period_data_dict.setdefault(key, val)
        for inc_key, inc_val in increments.items():
            period_data_dict[inc_key] += inc_val
```

### B. Reward Period Update (coordinator.py:3970-3988)

```python
daily = periods.setdefault(const.DATA_KID_REWARD_DATA_PERIODS_DAILY, {})
_get_period_entry(daily, daily_key)[counter_key] = (
    _get_period_entry(daily, daily_key).get(counter_key, 0) + amount
)
# Repeated for weekly, monthly, yearly...
# NO CLEANUP CALL
```

### C. Streak Update (coordinator.py:8911-8940)

```python
def _update_streak_progress(
    self, progress: AchievementProgress, today: date
) -> None:
    # If already updated today, do nothing
    if last_date == today:
        return
    # If yesterday was the last update, increment
    if last_date == today - timedelta(days=1):
        progress[const.DATA_KID_CURRENT_STREAK] = current_streak + 1
    # Reset to 1 if not done yesterday
    else:
        progress[const.DATA_KID_CURRENT_STREAK] = 1
```

### D. Cleanup Period Data (kc_helpers.py:731-830)

```python
def cleanup_period_data(
    self,
    periods_data: dict,
    period_keys: dict,
    retention_daily: int | None = None,
    ...
):
    # Daily: keep configured days
    cutoff_daily = dt_add_interval(...)
    for day in list(daily_data.keys()):
        if day < cutoff_daily:
            del daily_data[day]
    # Repeated for weekly, monthly, yearly...
```
