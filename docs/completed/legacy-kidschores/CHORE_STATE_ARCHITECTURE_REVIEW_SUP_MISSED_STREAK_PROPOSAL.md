# Missed Streak Implementation Proposal

**Date**: 2026-02-09
**Status**: Proposal for review
**Related**: Phase 5 - Missed State Tracking

## Analysis: Current Completion Streak Pattern

### Storage Structure (Per-Chore)

```python
kid_info["chore_data"][chore_id]["periods"] = {
    "daily": {
        "2026-02-09": {
            "completed": 1,
            "approved": 1,
            "points": 5.0,
            "streak_tally": 3,  # ← ONLY in daily buckets
        }
    },
    "weekly": {
        "2026-W07": {
            "completed": 1,
            "approved": 1,
            "points": 5.0,
            # NO streak_tally here
        }
    },
    "all_time": {
        "all_time": {
            "completed": 45,
            "approved": 45,
            "points": 225.0,
            "longest_streak": 7,  # ← ONLY in all_time bucket
            # NO streak_tally here
        }
    }
}
```

### Key Rules from Analysis

1. **`streak_tally`**:
   - ONLY written to daily buckets (filtered by StatisticsEngine)
   - Represents the calculated streak value AT THAT MOMENT
   - Max 1 update per day (checked by StatisticsManager before writing)
   - Value is CALCULATED by ChoreEngine.calculate_streak(), not incremented

2. **`longest_streak`**:
   - ONLY written to all_time bucket
   - High-water mark logic (not simple increment)
   - Updated by StatisticsManager when new streak_tally > current longest
   - Also written to kid-level chore_periods bucket for sensor display

3. **Calculation Flow**:

   ```
   ChoreManager.approve_chore():
     1. Read previous_streak from YESTERDAY's daily bucket (or 0)
     2. Call ChoreEngine.calculate_streak(previous_streak, last_completed, effective_date, chore_data)
     3. Engine returns NEW streak value (schedule-aware logic with has_missed_occurrences check)
     4. Pass new_streak to StatisticsManager via CHORE_COMPLETED signal

   StatisticsManager._on_chore_completed():
     5. Receive streak_tally from signal payload
     6. Check if TODAY's bucket already has streak_tally (max 1 per day)
     7. If not set today, add to increments dict
     8. Before _record_chore_transaction(), check if streak_tally > longest_streak
     9. If yes, update longest_streak in all_time bucket directly
     10. Call _record_chore_transaction() which writes to daily bucket
   ```

4. **Reset Behavior**:
   - Streak resets to 1 (not 0) on first completion or broken streak
   - Broken when: has_missed_occurrences() returns True (schedule-aware)
   - For FREQUENCY_NONE: simple daily logic (days_diff <= 1)

---

## Proposed: Missed Streak Pattern

### Design Decisions

| Question                    | Decision          | Rationale                                                  |
| --------------------------- | ----------------- | ---------------------------------------------------------- |
| **When to calculate?**      | On miss recording | Miss events are discrete, not continuous                   |
| **What to calculate?**      | Simple increment  | No schedule calculation - miss is binary event             |
| **Where is history?**       | Daily buckets     | Look at yesterday's daily bucket for previous value        |
| **When to reset?**          | On completion     | Any approval of this chore resets missed streak to 0       |
| **Default for new chores?** | 0                 | No misses = 0 (unlike completion streak which starts at 1) |

### Storage Structure (Per-Chore)

```python
kid_info["chore_data"][chore_id]["periods"] = {
    "daily": {
        "2026-02-09": {
            "missed": 1,
            "missed_streak_tally": 3,  # ← Consecutive misses (yesterday was 2, +1 = 3)
        }
    },
    "weekly": {
        "2026-W07": {
            "missed": 1,
            # NO missed_streak_tally here (daily only)
        }
    },
    "all_time": {
        "all_time": {
            "missed": 12,
            "missed_longest_streak": 5,  # ← High-water mark only
            # NO missed_streak_tally here
        }
    }
}
```

### Implementation Flow

```
ChoreManager._record_chore_missed():
  1. Read previous_missed_streak from MOST RECENT daily bucket with data (or 0)
     - Search backwards through daily buckets to find last missed_streak_tally
     - This handles weekly/monthly chores where yesterday has no data
  2. Calculate new_missed_streak = previous_missed_streak + 1
  3. Update last_missed timestamp (top-level field)
  4. Emit CHORE_MISSED signal with missed_streak_tally=new_missed_streak

StatisticsManager._on_chore_missed():
  5. Receive missed_streak_tally from signal payload
  6. Check TODAY's daily bucket for existing missed (max 1 per day)
  7. If already at max 1, skip (already recorded today)
  8. Build increments: {"missed": 1, "missed_streak_tally": missed_streak_tally}
  9. Check if missed_streak_tally > missed_longest_streak in all_time
  10. If yes, update missed_longest_streak in all_time bucket directly
  11. Call _record_chore_transaction() which writes to daily bucket

ChoreManager.approve_chore():
  12. On approval, reset missed streak to 0 (write to today's daily bucket)
  13. This breaks the consecutive miss chain
```

### Reset Logic Detail

When a chore is approved, we need to explicitly reset the missed streak:

```python
# In approve_chore, after calculating completion streak
StatisticsManager._on_chore_completed():
    # Existing completion logic...

    # Reset missed streak on completion (write 0 to today's daily bucket)
    # This breaks the consecutive miss chain
    kid_info = self._get_kid(kid_id)
    if kid_info:
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
        kid_chore_data = chore_data.get(chore_id, {})
        periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
        daily_buckets = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

        today_key = self._stats_engine.get_period_keys().get("daily")
        if today_key:
            daily_buckets.setdefault(today_key, {})[
                const.DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY
            ] = 0
```

### Historical Lookup Logic

```python
def _get_previous_missed_streak(
    self, kid_id: str, chore_id: str
) -> int:
    """Get previous missed streak from most recent daily bucket.

    Searches backwards through daily buckets to find the most recent day
    with a missed_streak_tally value. This handles weekly/monthly chores
    where yesterday might not have any miss data.

    Returns:
        Most recent missed_streak_tally value, or 0 if not found
    """
    kid_info = self._get_kid(kid_id)
    if not kid_info:
        return 0

    chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})
    kid_chore_data = chore_data.get(chore_id, {})
    periods = kid_chore_data.get(const.DATA_KID_CHORE_DATA_PERIODS, {})
    daily_buckets = periods.get(const.DATA_KID_CHORE_DATA_PERIODS_DAILY, {})

    # Search backwards from yesterday (today not yet written)
    # Look back up to 365 days (covers even yearly chores)
    for days_back in range(1, 366):
        check_dt = dt_now_utc() - timedelta(days=days_back)
        check_key = check_dt.date().isoformat()

        if check_key in daily_buckets:
            bucket_data = daily_buckets[check_key]
            if const.DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY in bucket_data:
                # Found most recent streak value
                return bucket_data[const.DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY]

    # No history found = never missed before
    return 0
```

---

## Comparison Table

| Aspect                  | Completion Streak                               | Missed Streak                      |
| ----------------------- | ----------------------------------------------- | ---------------------------------- |
| **Calculation**         | ChoreEngine.calculate_streak() - schedule-aware | Simple increment: previous + 1     |
| **Reset to**            | 1 (first completion)                            | 0 (no consecutive misses)          |
| **Reset trigger**       | Missed occurrence (schedule)                    | Any completion/approval            |
| **History lookup**      | Yesterday's daily bucket                        | Most recent daily bucket with data |
| **Storage: daily**      | `streak_tally`                                  | `missed_streak_tally`              |
| **Storage: all_time**   | `longest_streak`                                | `missed_longest_streak`            |
| **Engine filtering**    | Yes (daily only)                                | Yes (same pattern)                 |
| **Max 1 per day**       | Yes                                             | Yes                                |
| **High-water mark**     | Yes (in all_time)                               | Yes (in all_time)                  |
| **Kid-level aggregate** | Yes (chore_periods)                             | Yes (chore_periods)                |

---

## Edge Cases to Handle

### 1. **New Chore (No History)**

- Previous missed streak = 0 (default)
- First miss = 1
- ✅ Simple, no special handling needed

### 2. **Miss and Complete Same Day**

- Morning: Miss recorded → streak = 3
- Evening: Completion → streak reset to 0
- Both write to same daily bucket
- ✅ Works: completion writes 0, overwrites the 3

### 3. **Multiple Misses Same Day**

- Max 1 per day rule prevents this
- First \_record_chore_missed() writes, subsequent calls skip
- ✅ Handled by existing "max 1" guard

### 4. **Chore Never Missed**

- Daily buckets have no `missed_streak_tally` key
- Historical lookup returns 0
- ✅ Works: default to 0

### 5. **Gap in Daily Buckets (Weekly/Monthly Chores)**

- Weekly chore missed Week 1 Monday (streak=1)
- Week 2 Monday: yesterday (Sunday) has no data
- Lookup searches backwards, finds Week 1 Monday with streak=1
- Today's miss becomes 2
- ✅ Works: finds most recent bucket with data

### 5b. **True Gap (Completion in Between)**

- Mon: Miss (streak=1)
- Tue: Complete (writes streak=0)
- Wed: Miss (searches back, finds Tue with streak=0)
- Today's miss becomes 1 (NOT 2)
- ✅ Correct: completion breaks the chain by writing 0

### 6. **Completion Breaks Streak**

- Mon: Miss (streak=1)
- Tue: Miss (streak=2)
- Wed: Complete (writes streak=0)
- Thu: Miss (searches back to Wed, finds streak=0, new=1 NOT 3)
- ✅ Works: completion wrote 0 to Wed's bucket, search finds it

---

## Implementation Checklist

### ChoreManager Changes

- [ ] Add `_get_previous_missed_streak()` helper method
  - [ ] Search backwards through daily buckets (up to 365 days)
  - [ ] Return first found missed_streak_tally value
  - [ ] Return 0 if no history found
- [ ] Update `_record_chore_missed()` to:
  - [ ] Call \_get_previous_missed_streak() for historical value
  - [ ] Calculate new_missed_streak = previous + 1
  - [ ] Pass missed_streak_tally in CHORE_MISSED signal payload

### StatisticsManager Changes

- [ ] Update `_on_chore_missed()` to:
  - [ ] Receive missed_streak_tally from payload
  - [ ] Add missed_streak_tally to increments dict (if not already set today)
  - [ ] Check/update missed_longest_streak in all_time bucket
  - [ ] Update kid-level chore_periods missed_longest_streak

- [ ] Update `_on_chore_completed()` to:
  - [ ] Write missed_streak_tally=0 to today's daily bucket (reset on completion)

### StatisticsEngine Changes

- [ ] Add filtering for missed_streak_tally (daily only)
- [ ] Add filtering for missed_longest_streak (skip in record_transaction)

### Const.py Changes

- [ ] Verify constants exist (already done in Phase 5 Steps 1-2)

### Test Updates

- [ ] Test missed streak increments on consecutive days (daily chore)
- [ ] Test missed streak increments on consecutive weeks (weekly chore)
- [ ] Test missed streak increments on consecutive months (monthly chore)
- [ ] Test missed streak resets to 0 on completion
- [ ] Test longest_streak high-water mark updates
- [ ] Test no history edge case (new chore)
- [ ] Test gap with completion in between (completion breaks chain)
- [ ] Test lookup finds most recent bucket (not just yesterday)

---

## CRITICAL ISSUE: Daily Bucket Retention

### The Problem

**Default retention**: 7 days of daily buckets

**Impact on weekly/monthly chores**:

- Weekly chore: last bucket is 7+ days old → **PRUNED**
- Monthly chore: last bucket is 30+ days old → **PRUNED**
- Historical lookup in daily buckets returns 0 → **streak incorrectly resets**

**Existing Bug**: Completion streaks ALREADY have this problem!

```python
# chore_manager.py line 678
last_completed_data = daily_periods.get(last_completed_date_key, {})
previous_streak = last_completed_data.get(
    const.DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY, 0  # ← Defaults to 0 if pruned!
)
```

### Solution: Store Current Streak at Chore Data Level

Instead of relying on historical daily buckets, store the "current streak" value directly in the chore data structure (persisted, not pruned):

```python
# New fields in kid_chore_data (top-level, alongside last_completed):
kid_info["chore_data"][chore_id] = {
    "name": "Make bed",
    "state": "pending",
    "last_completed": "2026-01-15T08:00:00+00:00",
    "last_missed": "2026-02-09T08:00:00+00:00",

    # NEW: Current streak values (NOT in periods, so never pruned)
    "current_streak": 5,           # Current completion streak
    "current_missed_streak": 2,    # Current consecutive misses

    "periods": {
        "daily": {
            "2026-02-09": {
                "streak_tally": 5,         # Snapshot for display/stats
                "missed_streak_tally": 2   # Snapshot for display/stats
            }
        }
    }
}
```

### Updated Flow

**On Chore Completion**:

```python
# 1. Read current_streak from chore data (never pruned)
previous_streak = kid_chore_data.get("current_streak", 0)

# 2. Calculate new streak (schedule-aware)
new_streak = ChoreEngine.calculate_streak(
    current_streak=previous_streak,
    previous_last_completed_iso=previous_last_completed,
    current_work_date_iso=effective_date_iso,
    chore_data=chore_data,
)

# 3. Store new streak at chore data level (persisted)
kid_chore_data["current_streak"] = new_streak

# 4. Also write to daily bucket as snapshot (for display)
# StatisticsManager receives streak_tally in signal, writes to today's bucket

# 5. Reset missed streak to 0
kid_chore_data["current_missed_streak"] = 0
```

**On Chore Missed**:

```python
# 1. Read current_missed_streak from chore data (never pruned)
previous_missed_streak = kid_chore_data.get("current_missed_streak", 0)

# 2. Increment (simple, no calculation)
new_missed_streak = previous_missed_streak + 1

# 3. Store new missed streak at chore data level (persisted)
kid_chore_data["current_missed_streak"] = new_missed_streak

# 4. Also write to daily bucket as snapshot (for display)
# StatisticsManager receives missed_streak_tally in signal, writes to today's bucket
```

### Constants to Add

```python
# Chore data level (persisted, never pruned)
DATA_KID_CHORE_DATA_CURRENT_STREAK: Final = "current_streak"
DATA_KID_CHORE_DATA_CURRENT_MISSED_STREAK: Final = "current_missed_streak"

# Period buckets (display/historical, may be pruned)
# These already exist:
# DATA_KID_CHORE_DATA_PERIOD_STREAK_TALLY
# DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY
```

### Benefits

1. **Never pruned**: Source of truth persists with chore data
2. **No historical lookup**: Read directly from chore data
3. **Fixes existing bug**: Completion streaks also fixed
4. **Backward compatible**: Missing field defaults to 0
5. **Simpler code**: No 365-day backward search needed
6. **Daily buckets for display**: Still have historical snapshots

### Migration

No migration needed:

- Old chores: `current_streak` and `current_missed_streak` default to 0
- First event: Calculates correctly from 0 baseline
- Daily buckets: Continue as display-only snapshots

## Questions for Review

1. **Reset value**: Should missed_streak_tally reset to 0 or null on completion?
   - **Recommendation**: 0 (explicit value shows "streak broken")

2. **Multiple kids on shared chore**: Should each kid have independent missed streaks?
   - **Recommendation**: Yes (per-kid, per-chore tracking - matches current pattern)

3. **Display**: Should sensors show current missed_streak or longest_streak or both?
   - **Recommendation**: Both available as attributes, dashboard decides

4. **Backwards compat**: Old chores with no missed data?
   - **Recommendation**: Missing field defaults to 0, works automatically

5. **Fix existing completion streak bug**: Should we also fix completion streaks to use `current_streak` field?
   - **Recommendation**: YES - this fixes the pruning bug for weekly/monthly chores

---

---

## Why Completion Streaks ≠ Missed Streaks

### Fundamental Difference

**Completion Streaks** track **schedule adherence** (pattern-based, context-dependent)
**Missed Streaks** track **consecutive failures** (event-based, context-independent)

### Completion Streaks: Schedule-Aware Calculation

**Purpose**: "Are you keeping up with the schedule pattern?"

**Example - Daily Chore**:

- Complete Mon, Tue, Wed, Thu → streak = 4 ✅
- Complete Mon, skip Tue, complete Wed → streak = 1 (Tue was missed)

**Example - Weekly Chore (Mondays)**:

- Complete Feb 1, Feb 8, Feb 15 → streak = 3 ✅
- Complete Feb 1, skip Feb 8, complete Feb 15 → streak = 1 (Feb 8 missed)

**Why Complex**:

- Must understand schedule pattern (frequency, applicable_days, interval)
- Must enumerate expected occurrences between completions
- Must detect if any were skipped
- Uses `RecurrenceEngine.has_missed_occurrences()` with full schedule context

**User Understanding**:

- Weekly streak of 10 = "10 consecutive weeks on schedule"
- Daily streak of 10 = "10 consecutive days on schedule"
- Meaning scales with chore's frequency

### Missed Streaks: Simple Event Counter

**Purpose**: "How many times in a row did you fail to complete?"

**Example - Any Chore**:

- Miss occurrence 1 → missed_streak = 1
- Miss occurrence 2 → missed_streak = 2
- Miss occurrence 3 → missed_streak = 3
- Complete → missed_streak = 0 (reset)

**Why Simple**:

- Each miss event is discrete (happened or didn't)
- Schedule pattern irrelevant (failure is failure)
- Just increment: `previous_missed_streak + 1`
- No calculation engine needed

**User Understanding**:

- Missed streak of 3 = "failed to complete 3 times in a row"
- Absolute count of consecutive failures
- Doesn't matter if chore was daily/weekly/monthly

### Event Symmetry

Despite different calculations, they follow perfect event symmetry:

| Event          | Completion Streak                   | Missed Streak | Reasoning                   |
| -------------- | ----------------------------------- | ------------- | --------------------------- |
| **Complete**   | Increment or reset (schedule-aware) | Reset to 0    | Success ends failure chain  |
| **Miss**       | Reset to 1 (broken schedule)        | Increment     | Failure ends success chain  |
| **Disapprove** | No change                           | No change     | Not a completion event      |
| **Reschedule** | No change                           | No change     | Due date ≠ schedule pattern |

**Pattern**: Each streak resets when its **opposite event** occurs.

### Why Both Use Chore-Level Storage

Despite different calculations, both need **identical storage pattern**:

**Problem**: Default daily retention is 7 days

- Weekly chore completed 14 days ago
- Daily bucket with previous streak value: **PRUNED**
- Lookup returns 0 → streak incorrectly resets

**Solution**: Store current value at chore data level (never pruned)

- `current_streak`: Latest completion streak
- `current_missed_streak`: Latest missed streak
- Daily buckets: Display snapshots only (safe to prune)

**Benefits**:

1. Source of truth persists forever
2. No history lookup needed
3. Works for all chore frequencies
4. Backward compatible (missing = 0)

### Technical vs User Documentation

**Technical Explanation** (for developers):

```
Completion streaks use ChoreEngine.calculate_streak() which calls
RecurrenceEngine.has_missed_occurrences() to detect schedule violations.
This requires full schedule context (frequency, interval, applicable_days).

Missed streaks use simple increment (previous + 1) because each miss
event is discrete and doesn't require schedule interpretation.

Both store current value at kid_chore_data level to survive retention
pruning, with daily bucket snapshots for historical display.
```

**User Explanation** (for documentation):

```
Completion Streaks reward you for staying on schedule:
- A streak of 7 on a daily chore means 7 days in a row on time
- A streak of 4 on a weekly chore means 4 weeks in a row on time
- The streak breaks when you miss a scheduled occurrence

Missed Streaks track consecutive failures:
- A missed streak of 3 means you failed to complete 3 times in a row
- It doesn't matter if the chore was daily or weekly
- The streak resets to 0 when you successfully complete the chore

Both streaks work together to show your performance pattern.
```

---

## Approval Required

This proposal needs sign-off on:

- ✅ Simple increment (not schedule-aware)
- ✅ Reset to 0 on completion
- ❌ ~~Historical lookup from daily buckets~~ → Changed due to pruning issue
- ✅ **NEW**: Store current_streak and current_missed_streak at chore data level (never pruned)
- ✅ Daily buckets as display snapshots only (not source of truth)
- ✅ Fixes existing completion streak pruning bug for weekly/monthly chores
- ✅ Explicit 0 write on completion (clear reset signal)
- ✅ Per-kid independence on shared chores (each kid tracks own streaks)
- ✅ Event symmetry: completion resets missed, miss resets completion
- ✅ Schedule-aware completion vs event-driven missed (justified by purpose)

**Status**: APPROVED. Ready for implementation.
