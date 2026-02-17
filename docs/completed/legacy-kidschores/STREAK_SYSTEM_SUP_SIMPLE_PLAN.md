# Simple Schedule-Aware Streak Implementation Plan

**Supporting Doc for**: STREAK_SYSTEM_SUP_MATRIX.md  
**Created**: 2026-01-20  
**Purpose**: Minimal viable implementation with solid foundation

---

## Core Principle

**Build extensible base logic. Document limitations. Add edge case handling later.**

---

## Current Implementation Overview

### Streak Logic Location

**File**: `custom_components/kidschores/coordinator.py`  
**Method**: `_update_kid_chore_state()` (lines ~4738-4800)

**Current Algorithm** (Day-Gap):
```python
# Lines 4738-4758 in coordinator.py
yesterday_local_iso = kh.dt_add_interval(
    today_local_iso,
    interval_unit=const.TIME_UNIT_DAYS,
    delta=-1,
    require_future=False,
    return_type=const.HELPER_RETURN_ISO_DATE,
)
yesterday_chore_data = periods_data[
    const.DATA_KID_CHORE_DATA_PERIODS_DAILY
].get(yesterday_local_iso, {})
yesterday_streak = yesterday_chore_data.get(
    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
)
today_streak = yesterday_streak + 1 if yesterday_streak > 0 else 1
```

### Existing Infrastructure We Can Use

**RecurrenceEngine** (`schedule_engine.py`):
- ✅ `get_occurrences(start, end, limit)` - Returns all occurrences in a date range
- ✅ `get_next_occurrence(after, require_future)` - Returns next scheduled occurrence
- ✅ Handles all schedule types: daily, weekly, monthly, custom intervals

**Data Already Available**:
- ✅ `kid_chore_data[DATA_KID_CHORE_DATA_LAST_APPROVED]` - When kid last approved
- ✅ Chore data has: `DATA_CHORE_RECURRING_FREQUENCY`, `DATA_CHORE_CUSTOM_INTERVAL`, `DATA_CHORE_CUSTOM_INTERVAL_UNIT`, `DATA_CHORE_APPLICABLE_DAYS`
- ✅ `periods_data["daily"][date]["longest_streak"]` - Previous streak values

### StatisticsEngine Note

**Current State**: `statistics_engine.py` has an `update_streak()` method (line 237), but it is **NOT used** for chore streaks. The coordinator uses inline logic.

**Decision**: Implement schedule-aware logic directly in coordinator to minimize refactoring. Can consolidate to StatisticsEngine in a future cleanup phase if desired.

---

## What We're Building (Minimal Version)

### Building ScheduleConfig from Chore Data

The chore data doesn't store a ready-made `ScheduleConfig`. We need to build it:

```python
# Build ScheduleConfig from chore fields
frequency = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE)

# Only compute streaks for chores with a valid frequency
if frequency and frequency != const.FREQUENCY_NONE:
    schedule_config: ScheduleConfig = {
        "frequency": frequency,
        "interval": chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL, 1),
        "interval_unit": chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, const.TIME_UNIT_DAYS),
        "applicable_days": chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
        "base_date": chore_info.get(const.DATA_CHORE_DUE_DATE) or now_utc.isoformat(),
    }
```

### Core Logic Change

**New (Schedule-Aware)**:
```python
# Get last approved time
last_approved_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)

# Determine previous streak from yesterday's period data
yesterday_streak = yesterday_chore_data.get(
    const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0
)

# Get chore frequency
frequency = chore_info.get(const.DATA_CHORE_RECURRING_FREQUENCY, const.FREQUENCY_NONE)

# Calculate streak
if not last_approved_str:
    # First approval ever
    today_streak = 1
elif not frequency or frequency == const.FREQUENCY_NONE:
    # No schedule configured - skip streak calculation
    today_streak = 0  # Or leave unchanged
else:
    # Build ScheduleConfig from chore fields
    schedule_config: ScheduleConfig = {
        "frequency": frequency,
        "interval": chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL, 1),
        "interval_unit": chore_info.get(const.DATA_CHORE_CUSTOM_INTERVAL_UNIT, const.TIME_UNIT_DAYS),
        "applicable_days": chore_info.get(const.DATA_CHORE_APPLICABLE_DAYS, []),
        "base_date": chore_info.get(const.DATA_CHORE_DUE_DATE) or now_utc.isoformat(),
    }
    
    # Check if any scheduled occurrences were missed
    try:
        engine = RecurrenceEngine(schedule_config)
        last_approved = kh.parse_datetime_to_utc(last_approved_str)
        missed = engine.has_missed_occurrences(last_approved, now_utc)
        
        if missed:
            today_streak = 1  # Broke streak
        else:
            today_streak = yesterday_streak + 1  # Continue
    except Exception:
        # Fallback to legacy day-gap logic
        today_streak = yesterday_streak + 1 if yesterday_streak > 0 else 1
```

---

## Implementation Phases

### Phase 1: Add `has_missed_occurrences()` to RecurrenceEngine

**File**: `custom_components/kidschores/schedule_engine.py`

**Add Method** (after `get_occurrences()` ~line 178):
```python
def has_missed_occurrences(
    self,
    last_completion: datetime,
    current_completion: datetime,
) -> bool:
    """Check if any scheduled occurrences were skipped between completions.
    
    Args:
        last_completion: Timestamp of previous approval (UTC)
        current_completion: Timestamp of current approval (UTC)
        
    Returns:
        True if at least one occurrence was missed (streak breaks)
        False if current completion is on-time or early (streak continues)
    
    Examples:
        Daily chore, last=Jan 1, current=Jan 2 → False (on-time)
        Daily chore, last=Jan 1, current=Jan 3 → True (missed Jan 2)
        Every 3 days, last=Jan 1, current=Jan 3 → False (Jan 2 not scheduled)
        Weekly Monday, last=Jan 6 (Mon), current=Jan 13 (Mon) → False
    """
    # Get all occurrences between completions (exclusive of last, inclusive of current window)
    occurrences = self.get_occurrences(
        start=last_completion,
        end=current_completion,
        limit=100
    )
    
    # Filter to occurrences strictly between the two completion times
    # If any such occurrence exists, it was missed
    missed = [
        occ for occ in occurrences
        if last_completion < occ < current_completion
    ]
    
    return len(missed) > 0
```

**Tests** (`tests/test_schedule_engine_streaks.py`):
- Daily consecutive (no miss)
- Daily skip one day (miss)
- Every 3 days on-time (no miss)  
- Every 3 days early (no miss)
- Every 3 days late/skip (miss)
- Weekly consecutive (no miss)
- Weekly skip (miss)
- Monthly consecutive (no miss)
- First completion ever (handle None last_completion)
- No schedule/frequency NONE (return False)

---

### Phase 2: Update Streak Logic in Coordinator

**File**: `custom_components/kidschores/coordinator.py`  
**Method**: `_update_kid_chore_state()` (around line 4738)

**Changes**:
1. Import RecurrenceEngine if not already imported
2. Replace day-gap calculation with schedule-aware check
3. Add fallback to legacy logic on errors
4. Handle chores without schedules (no streak calculation)

**Search for Edit Location**:
```bash
grep -n "yesterday_streak + 1 if yesterday_streak" coordinator.py
```

---

### Phase 3: Testing

**Unit Tests** (`tests/test_schedule_engine_streaks.py`):
- RecurrenceEngine.has_missed_occurrences() coverage

**Integration Tests** (`tests/test_workflow_chore_streaks.py`):
- Daily chore streak continues on consecutive days
- Daily chore streak breaks on skip
- Weekly chore streak continues across 7-day gap
- Existing streak (10) continues to 11 on next approval
- Chore without schedule: streak not updated (or legacy behavior)
- Error in schedule parsing: falls back to legacy logic

---

## Data Flow Diagram

```
Chore Approval Triggered
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│ _update_kid_chore_state() [coordinator.py ~line 4738]               │
│                                                                     │
│  1. Get last_approved_str from                                      │
│     kid_chore_data[DATA_KID_CHORE_DATA_LAST_APPROVED]               │
│                                                                     │
│  2. Get frequency from chore_info[DATA_CHORE_RECURRING_FREQUENCY]   │
│                                                                     │
│  3. Get yesterday_streak from                                       │
│     periods_data["daily"][yesterday_iso]["longest_streak"]          │
│                                                                     │
│  IF frequency is None or FREQUENCY_NONE:                            │
│     → Skip streak calculation (today_streak = 0)                    │
│                                                                     │
│  ELSE:                                                              │
│     → Build ScheduleConfig from chore_info fields                   │
│     → Create RecurrenceEngine(schedule_config)                      │
│     → Call engine.has_missed_occurrences(last_approved, now_utc)    │
│     → IF missed: today_streak = 1 (restart)                         │
│     → ELSE: today_streak = yesterday_streak + 1 (continue)          │
│                                                                     │
│  4. Write today_streak to periods_data (daily, weekly, monthly...)  │
│  5. Update chore_stats longest_streak_all_time if new max           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `schedule_engine.py` | Add method | `has_missed_occurrences()` (~line 178) |
| `coordinator.py` | Modify | Replace day-gap streak logic (~lines 4738-4758) |
| `tests/test_schedule_engine_streaks.py` | New file | Unit tests for `has_missed_occurrences()` |
| `tests/test_workflow_chore_streaks.py` | New/modify | Integration tests for streak scenarios |

---

## Migration Impact: NONE

**No schema changes needed!**

- ✅ Existing streak values preserved in period data
- ✅ `DATA_KID_CHORE_DATA_LAST_APPROVED` already exists
- ✅ `DATA_CHORE_RECURRING_FREQUENCY` and schedule fields already exist
- ✅ `RecurrenceEngine` already exists and handles all schedule types
- ✅ Just use better logic going forward

**User Experience**:
- Streak of 10 on Jan 19 → complete Jan 20 → streak becomes 11 ✅
- No disruption, no resets, no data loss
- Better behavior for non-daily chores immediately

---

## Known Limitations

These limitations are understood and may be considered for future enhancements based on user feedback:

### 1. Chores Without Due Dates

**Limitation**: Chores without schedule/due date configuration will not calculate streaks.

**Rationale**: 
- Streaks measure "on-time consistency" against a schedule
- Without a schedule, there's no definition of "missed occurrence"
- These chores can still track total completions via period counts

---

### 2. Historical Streak Validation

**Limitation**: Existing streak values are not retroactively validated against new schedule-aware rules.

**Example**:
- User had weekly Monday chore but legacy system counted daily completions
- Current streak of 7 will be preserved (not recalculated to 1)
- Future completions will use correct schedule-aware logic

**Rationale**: 
- Retroactive validation requires historical schedule state (not stored)
- Preserving streaks provides better user experience than resetting
- Streaks naturally correct over time as new logic applies

---

### 3. Vacation/Pause Retroactive Handling

**Limitation**: If a chore was paused during an active streak, the pause period is not retroactively accounted for.

**Example**:
- Streak of 10 from Dec 1-10
- User paused chore Dec 11-20 (pause not recorded in streak calculation)
- Resuming Dec 21 may show as missed occurrence

**Rationale**: Requires tracking pause/vacation history over time.

---

### 4. Schedule Changes Mid-Streak

**Limitation**: Schedule changes during an active streak use the new schedule for future validations.

**Example**:
- Streak of 10 with "every 1 day" schedule
- User changes to "every 3 days" on Jan 15
- Next approval validates against "every 3 days" (current schedule)

**Rationale**: Current schedule is the active rule; historical schedule tracking adds significant complexity.

---

### 5. Multi-Claim/Multi-Approval Same Day

**Limitation**: Multiple approvals on the same day only count as one streak increment.

**Example**:
- Kid claims chore 3 times on Monday (multi-claim enabled)
- Parent approves all 3 claims
- Streak increments by 1 (not 3)

**Rationale**: Streaks measure consistency over time, not quantity per day. By design.

---

### 6. Shared Chore Team Streaks

**Limitation**: Shared chores track per-kid streaks independently, not as team consistency.

**Example**:
- Shared chore between Kid A and Kid B
- Kid A completes Mon, Wed, Fri
- Kid B completes Tue, Thu, Sat
- Each kid's streak is evaluated independently

**Rationale**: Per-kid tracking is current design. Team-based streaks could be a separate feature.

---

### 7. Timezone Edge Cases

**Limitation**: Approvals near midnight (11:59pm vs 12:01am) use precise timestamp comparison.

**Example**:
- Daily chore last approved Jan 1 at 11:59pm local time
- Next approval Jan 2 at 12:01am local time
- System may interpret as consecutive days or one-day gap depending on occurrence calculation

**Rationale**: `has_missed_occurrences()` uses precise datetime math. Future enhancement could add configurable grace periods.

---

## Success Criteria

### Phase 1 Complete
- [ ] `has_missed_occurrences()` method implemented in RecurrenceEngine
- [ ] 15+ test cases pass covering daily, multi-day, weekly, monthly schedules
- [ ] Handles early completions correctly

### Phase 2 Complete
- [ ] Coordinator uses schedule-aware logic (lines 4738-4758)
- [ ] Fallback to legacy day-gap logic on errors (graceful degradation)
- [ ] Chores without schedules: explicitly handled (skip or legacy)
- [ ] All existing tests still pass

### Phase 3 Complete
- [ ] Integration tests for streak preservation scenario
- [ ] 95%+ test coverage on new logic
- [ ] Performance < 10ms per streak calculation (sanity check)

---

## Future Enhancements

The following enhancements may be considered based on user feedback and priority:

- **Vacation/Pause Awareness**: Detect pause state or `applicable_days: []` and skip missed occurrence checks
- **Schedule Change History**: Track schedule changes over time for accurate historical validation
- **Configurable Grace Periods**: Add optional `streak_grace_days` per chore for "almost on-time" buffer
- **Team Streaks**: New metric for shared chores measuring team consistency
- **Retroactive Calculation Tools**: Admin utility to rebuild streaks from historical data (requires schedule history)
- **StatisticsEngine Consolidation**: Move streak logic from coordinator inline to StatisticsEngine method (cleanup)
