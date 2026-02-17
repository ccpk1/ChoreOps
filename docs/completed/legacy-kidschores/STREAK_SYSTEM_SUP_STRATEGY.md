# Streak System: Strategic Analysis & Future Direction

**Supporting Doc for**: STATISTICS_ENGINE_IN-PROCESS.md
**Created**: 2026-01-20
**Purpose**: Comprehensive analysis of streak tracking with recommendations

---

## Executive Summary

**Current Problem**: Streaks only count consecutive calendar days, making them useless for chores with non-daily schedules (every 3 days, weekly, etc.).

**Root Cause**: Streak logic predates schedule-aware tools (ScheduleEngine, period data lookback).

**Recommendation**: Transition to **schedule-aware consistency tracking** that measures "completed on-time vs expected" rather than "consecutive days."

---

## Current State Analysis

### What We Track Now

**Per-Chore, Per-Period**:

```python
periods["daily"]["2026-01-19"]["longest_streak"] = 5  # Best daily streak this day
periods["weekly"]["2026-W03"]["longest_streak"] = 5   # Best weekly streak this week
periods["monthly"]["2026-01"]["longest_streak"] = 5   # Best monthly streak
periods["yearly"]["2026"]["longest_streak"] = 5       # Best yearly streak
periods["all_time"]["all_time"]["longest_streak"] = 5 # Best ever
```

**Kid-Level Aggregate**:

```python
chore_stats["longest_streak_all_time"] = 5  # Best streak across ALL chores
```

### Current Algorithm

```python
# On approval:
yesterday_streak = periods["daily"][yesterday_iso].get("longest_streak", 0)
if yesterday_streak > 0:
    today_streak = yesterday_streak + 1  # Continue streak
else:
    today_streak = 1  # Start new streak

# Store everywhere
periods["daily"][today_iso]["longest_streak"] = today_streak
if today_streak > periods["all_time"]["all_time"]["longest_streak"]:
    periods["all_time"]["all_time"]["longest_streak"] = today_streak
```

### Limitations

| Chore Type                                                      | Current Behavior                | User Impact                      |
| --------------------------------------------------------------- | ------------------------------- | -------------------------------- |
| Daily chore (applicable_days: all)                              | ✅ Streak increments daily      | Works as intended                |
| Every 3 days (`APPROVAL_RESET_UPON_COMPLETION` + 72hr interval) | ❌ Max streak = 1               | Zero recognition for consistency |
| Weekly (Mon/Wed/Fri only)                                       | ❌ Streak breaks Tue/Thu        | False negatives                  |
| Monthly (1st of month)                                          | ❌ Max streak = 1               | Zero recognition for consistency |
| Custom schedule (every Tue/Thu)                                 | ❌ Breaks on non-scheduled days | False negatives                  |

**Bottom Line**: Current system assumes daily cadence, penalizes all other schedules.

---

## Available Tools & Data

### Tools We Have

1. **ScheduleEngine** (`schedule_engine.py`)
   - Can calculate next occurrence date for any recurrence pattern
   - Knows if chore was "due" on a given day
   - Handles complex patterns (every N days, specific weekdays, month-end, etc.)

2. **Period Data** (via StatisticsEngine)
   - Historical approval dates stored in `periods["daily"][date_iso]`
   - Can look back arbitrary timeframes (retention permitting)
   - Provides basis for "was it completed when expected?" checks

3. **Chore Configuration**
   - `approval_reset_type`: Defines recurrence behavior
   - `applicable_days`: Which weekdays chore is available
   - `per_kid_applicable_days`: Per-kid schedule overrides
   - Due date intervals for custom schedules

### Data Available Per Approval

- `today_iso`: Current date
- `periods["daily"]`: Historical daily data (subject to retention)
- `approval_reset_type`: Chore's recurrence pattern
- `applicable_days`: Scheduled days for this chore
- Last completion date (from `last_approved` field)

---

## Ideal Solution: Schedule-Aware Consistency Tracking

### Concept

Instead of "consecutive days," track **"consecutive completions on expected occurrences."**

**Example 1**: Every 3 days chore

```
Day 1: Complete ✅ (streak=1)
Day 2: Not due (streak unchanged)
Day 3: Not due (streak unchanged)
Day 4: Complete ✅ (streak=2) ← First "expected" occurrence after Day 1
Day 5-6: Not due
Day 7: Complete ✅ (streak=3)
Day 8-9: Not due
Day 10: Miss ❌ (streak resets to 0)
```

**Example 2**: Monday/Wednesday/Friday chore

```
Mon: Complete ✅ (streak=1)
Tue: Not due (streak unchanged)
Wed: Complete ✅ (streak=2) ← Next scheduled day
Thu: Not due
Fri: Complete ✅ (streak=3)
Sat: Not due
Sun: Not due
Mon: Complete ✅ (streak=4)
Wed: Miss ❌ (streak resets to 0) ← Broke on scheduled day
```

### Algorithm

```python
def calculate_schedule_aware_streak(
    chore_id: str,
    kid_id: str,
    today: date,
) -> int:
    """Calculate streak based on chore's actual schedule."""

    # Get chore schedule config
    schedule_config = get_schedule_config(chore_id, kid_id)

    # Get last approval date
    last_approved = get_last_approved_date(chore_id, kid_id)

    if not last_approved:
        return 1  # First completion

    # Calculate next expected occurrence after last approval
    next_expected = schedule_engine.get_next_occurrence(
        schedule_config,
        reference_date=last_approved,
    )

    # Check if today is an expected occurrence
    if today < next_expected:
        # Completed early or not due yet - no change
        return get_current_streak(chore_id, kid_id)

    if today == next_expected:
        # Completed on exact expected date - increment
        return get_current_streak(chore_id, kid_id) + 1

    # Check if any expected occurrence was missed between last_approved and today
    missed_any = schedule_engine.has_missed_occurrences(
        schedule_config,
        start_date=last_approved,
        end_date=today,
    )

    if missed_any:
        # Missed at least one expected occurrence - reset
        return 1
    else:
        # Completed late but no occurrences missed - increment
        return get_current_streak(chore_id, kid_id) + 1
```

### Benefits

✅ Works for **all chore types** (daily, weekly, custom intervals)
✅ Measures actual **consistency** vs schedule expectations
✅ No false negatives (breaks on non-scheduled days)
✅ No false positives (completing daily doesn't count as "streak" for weekly chore)
✅ Leverages existing ScheduleEngine infrastructure

### Challenges

⚠️ **Complexity**: Requires schedule evaluation on every approval
⚠️ **Retention**: Lookback limited by daily period retention (default 30 days)
⚠️ **Performance**: ScheduleEngine calls on every approval (acceptable if cached)
⚠️ **Migration**: Existing streak data meaningless under new definition

---

## Alternative Approaches

### Option A: Hybrid - Calendar Days + Frequency Multiplier

**Concept**: Keep day-based streaks, but scale by chore frequency.

```python
# Daily chore: 7 consecutive days = streak 7
# Every-3-days chore: 7 consecutive occurrences = streak 21 (7 * 3)
# Weekly chore: 4 consecutive weeks = streak 28 (4 * 7)

effective_streak = occurrences_completed * days_between_occurrences
```

**Pros**:

- Simpler than full schedule-aware
- Rewards less-frequent chores fairly (4 weeks = higher streak value)
- Minimal changes to existing logic

**Cons**:

- Still tracks "occurrences" not "days," so partially misleading
- Doesn't solve breaks on non-scheduled days
- Multiplier feels artificial ("21-day streak" when only 7 completions)

---

### Option B: Dual Metrics - Calendar Streak + Consistency Streak

**Concept**: Track both types separately.

```python
chore_data[chore_id] = {
    "calendar_streak": 5,  # Consecutive calendar days (current system)
    "consistency_streak": 12,  # Consecutive scheduled occurrences (new)
    "consistency_percentage": 85,  # % of expected occurrences completed
}
```

**Pros**:

- Preserves existing calendar streaks (no breaking changes)
- Adds new consistency metric without removing old
- Users can choose which to display/track

**Cons**:

- Doubles storage/computation
- Two different "streak" definitions confusing to users
- Calendar streak still useless for non-daily chores

---

### Option C: Simplify - Single All-Time Streak Only

**Concept**: Eliminate per-period streaks (daily/weekly/monthly/yearly), keep only all-time.

```python
chore_data[chore_id] = {
    "current_streak": 5,  # Current streak (schedule-aware)
    "longest_streak_all_time": 12,  # Best ever
    # Remove: longest_streak_week, longest_streak_month, longest_streak_year
}
```

**Pros**:

- Reduces complexity significantly
- Easier to explain ("your best streak ever")
- Faster computation (no per-period updates)

**Cons**:

- Loses granularity (can't see "best week this month")
- Removes potential dashboard features ("weekly improvement")
- May not satisfy users who like detailed stats

---

### Option D: Completion Percentage Instead of Streaks

**Concept**: Replace streaks with **completion rate** over rolling windows.

```python
chore_stats = {
    "completion_rate_7d": 85.7,  # % of expected occurrences in last 7 days
    "completion_rate_30d": 91.2,  # Last 30 days
    "completion_rate_all_time": 88.5,  # Since chore creation
}
```

**Pros**:

- More forgiving than streaks (one miss doesn't reset)
- Better measure of long-term consistency
- Works universally for all chore types

**Cons**:

- Less motivating than streaks (no "don't break the chain" effect)
- Requires lookback across retention window
- Fundamentally different UX (not a "streak")

---

## Recommended Path Forward

### Phase 1: Enhanced Streak (Schedule-Aware)

**Implement ideal solution** with schedule-aware consistency tracking.

**Changes Required**:

1. Add `ScheduleEngine.has_missed_occurrences(start, end, schedule_config)` method
2. Add `ScheduleEngine.get_next_occurrence(from_date, schedule_config)` method
3. Update `_update_chore_data_for_kid()` to use new streak algorithm
4. Migrate existing streaks → reset to 0 (clean slate)

**Timeline**: 5-7 days (including tests)

**User Impact**:

- ✅ All chore types now support meaningful streaks
- ⚠️ Existing streaks reset (one-time breaking change)
- ✅ Future-proof for new schedule types

---

### Phase 2: Add Completion Rate (Optional)

**Add complementary metric** alongside streaks.

```python
chore_stats["completion_rate_30d"] = calculate_completion_rate(
    chore_id, kid_id, days=30
)
```

**Timeline**: 2-3 days
**User Impact**: Additive feature, no breaking changes

---

### Phase 3: Simplify Storage (Tech Debt)

**Remove per-period longest_streak** (weekly/monthly/yearly).

**Rationale**: With schedule-aware streaks, "best week" is less meaningful (could be 1 completion for weekly chore, or 7 for daily).

**Timeline**: 1-2 days
**User Impact**: None (if these aren't displayed)

---

## Decision Criteria

| Criterion                 | Ideal (Schedule-Aware) | Hybrid (Multiplier) | Dual Metrics | Simplified   | Percentage    |
| ------------------------- | ---------------------- | ------------------- | ------------ | ------------ | ------------- |
| Works for all chore types | ✅                     | ⚠️ Partially        | ✅           | ✅           | ✅            |
| Measures true consistency | ✅                     | ❌                  | ✅           | ✅           | ✅            |
| Low complexity            | ❌ High                | ✅                  | ❌ Medium    | ✅           | ⚠️ Medium     |
| Backwards compatible      | ❌ Reset               | ✅                  | ✅           | ❌ Data loss | ❌ New metric |
| Uses existing tools       | ✅ ScheduleEngine      | ✅                  | ✅           | ✅           | ✅            |
| User motivation           | ✅ High                | ⚠️ Confusing        | ✅ High      | ✅ Medium    | ⚠️ Low        |
| Implementation time       | 5-7 days               | 2-3 days            | 7-10 days    | 3-4 days     | 4-5 days      |

---

## Questions for Decision

1. **Breaking change acceptable?** Resetting streaks to implement schedule-aware logic?

2. **Per-period streaks valuable?** Do users care about "longest streak this week" vs just "longest ever"?

3. **Completion rate additive?** Would completion percentage be useful alongside (or instead of) streaks?

4. **Migration complexity?** Worth building backward-compatible hybrid vs clean break?

5. **Performance concerns?** ScheduleEngine calls on every approval acceptable?

---

## Proposed Decision Framework

**Tier 1 (Must Have)**:

- ✅ Support all chore frequencies
- ✅ Measure true consistency
- ✅ Use existing tools (ScheduleEngine)

**Tier 2 (Nice to Have)**:

- ⚠️ Preserve existing streak data
- ⚠️ Keep per-period granularity
- ⚠️ Zero breaking changes

**Tier 3 (Optional)**:

- Add completion rate metrics
- Dashboard visualizations for trends
- Leaderboards based on consistency

**Recommendation**: Prioritize Tier 1, accept breaking change for clean architecture.

---

## Next Steps

1. **Review this analysis** with stakeholders
2. **Decide on approach** (schedule-aware recommended)
3. **Create implementation plan** (separate from Statistics Engine)
4. **Prototype ScheduleEngine extensions** needed
5. **Test with sample chore schedules** (daily, weekly, custom)
6. **Plan migration strategy** (reset vs preserve)

---

## References

- `schedule_engine.py` - RecurrenceEngine for occurrence calculations
- `statistics_engine.py` - Period data management
- Lines 4737-4795 in `coordinator.py` - Current streak implementation
- `const.py` lines 1055-1067 - Approval reset types
