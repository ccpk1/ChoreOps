# Schedule-Aware Streak System: Decision Matrix

**Supporting Doc for**: STREAK_SYSTEM_SUP_STRATEGY.md
**Created**: 2026-01-20
**Purpose**: Visual reference for how streaks work across all schedule types and scenarios

---

## Quick Reference: What Counts as a Streak?

| **Legacy System**               | **Schedule-Aware System**                      |
| ------------------------------- | ---------------------------------------------- |
| ✅ Complete chore today         | ✅ Complete chore on or before due date        |
| ✅ Complete chore yesterday     | ✅ Complete chore on next scheduled occurrence |
| ❌ Skip any calendar day        | ✅ Complete early (before next occurrence)     |
| ❌ Chore scheduled every 3 days | ✅ Skip days between scheduled occurrences     |
| ❌ Weekly chore (6 days gap)    | ✅ Vacation mode (no occurrences = no breaks)  |

**Key Insight**: Schedule-aware measures **"on-time completion consistency"** not **"daily activity"**.

---

## Streak Mechanics by Schedule Type

### Daily Schedules

| Scenario            | Schedule Config              | Completion Pattern               | Legacy Streak | New Streak | Why?                                    |
| ------------------- | ---------------------------- | -------------------------------- | ------------- | ---------- | --------------------------------------- |
| **Basic Daily**     | `every: 1 day`               | Mon✅ Tue✅ Wed✅                | 3             | 3          | Same behavior                           |
| **Skip Day**        | `every: 1 day`               | Mon✅ Tue❌ Wed✅                | 0→1           | 0→1        | Missed scheduled occurrence             |
| **Weekend Off**     | `applicable_days: [Mon-Fri]` | Fri✅ [Sat❌ Sun❌] Mon✅        | 0→1           | 2          | Sat/Sun not scheduled                   |
| **Complete Early**  | `every: 1 day`               | Mon✅ (complete Tue chore) Tue✅ | 2             | 2          | Both on-time per schedule               |
| **Double Complete** | `allow_multiple: True`       | Mon✅✅ Tue✅                    | 2             | 2          | Only first completion counts for streak |

### Multi-Day Schedules

| Scenario            | Schedule Config | Completion Pattern          | Legacy Streak | New Streak | Why?                           |
| ------------------- | --------------- | --------------------------- | ------------- | ---------- | ------------------------------ |
| **Every 3 Days**    | `every: 3 days` | Mon✅ [Tue❌ Wed❌] Thu✅   | 0→1           | 2          | Tue/Wed not expected           |
| **Skip Occurrence** | `every: 3 days` | Mon✅ [Tue Wed] Thu❌ Fri✅ | 0→1           | 0→1        | Missed Thu occurrence          |
| **Complete Early**  | `every: 3 days` | Mon✅ Tue✅ [Wed] Thu✅     | 2             | 3          | Tue = early completion for Thu |
| **Late Complete**   | `every: 3 days` | Mon✅ [Tue Wed Thu] Fri✅   | 0→1           | 0→1        | Missed Thu occurrence          |

### Weekly Schedules

| Scenario           | Schedule Config     | Completion Pattern                  | Legacy Streak | New Streak | Why?                                  |
| ------------------ | ------------------- | ----------------------------------- | ------------- | ---------- | ------------------------------------- |
| **Every Monday**   | `weekly: [Monday]`  | Mon✅ [6 days] Mon✅                | 0→1           | 2          | Days between Mondays don't matter     |
| **Skip Week**      | `weekly: [Monday]`  | Mon✅ [6 days] Mon❌ [7 days] Mon✅ | 0→1           | 0→1        | Missed scheduled Monday               |
| **Complete Early** | `weekly: [Monday]`  | Mon✅ [4 days] Fri✅ [3 days] Mon✅ | 0→1           | 2          | Fri counts as early Monday completion |
| **Two Days/Week**  | `weekly: [Mon,Thu]` | Mon✅ [2 days] Thu✅ [3 days] Mon✅ | 0→1           | 3          | Each occurrence tracked separately    |

### Monthly Schedules

| Scenario           | Schedule Config      | Completion Pattern             | Legacy Streak | New Streak | Why?                             |
| ------------------ | -------------------- | ------------------------------ | ------------- | ---------- | -------------------------------- |
| **1st of Month**   | `monthly: {day: 1}`  | Jan-1✅ [29 days] Feb-1✅      | 0→1           | 2          | Days between months irrelevant   |
| **Skip Month**     | `monthly: {day: 1}`  | Jan-1✅ Feb-1❌ Mar-1✅        | 0→1           | 0→1        | Missed February occurrence       |
| **Complete Early** | `monthly: {day: 15}` | Jan-15✅ Jan-20✅ [Feb-15 due] | 0→1           | 2          | Jan-20 = early Feb-15            |
| **Last Day**       | `monthly: {day: -1}` | Jan-31✅ Feb-28✅ Mar-31✅     | 0→1           | 3          | Variable gaps don't break streak |

### Irregular Schedules

| Scenario            | Schedule Config                             | Completion Pattern          | Legacy Streak | New Streak | Why?                     |
| ------------------- | ------------------------------------------- | --------------------------- | ------------- | ---------- | ------------------------ |
| **Custom Interval** | `every: 2 weeks`                            | Week-1✅ [13 days] Week-3✅ | 0→1           | 2          | 13-day gap is normal     |
| **Weekday Only**    | `every: 1 day, applicable_days: [Mon-Fri]`  | Fri✅ [Sat❌ Sun❌] Mon✅   | 0→1           | 2          | Weekend not scheduled    |
| **First Monday**    | `monthly: {weekday: Monday, occurrence: 1}` | Jan-6✅ [28 days] Feb-3✅   | 0→1           | 2          | Variable days between OK |

---

## Edge Case Behavior Matrix

### Approval Types & Timing

| Edge Case                         | Current Behavior             | Schedule-Aware Behavior                 | Notes                                    |
| --------------------------------- | ---------------------------- | --------------------------------------- | ---------------------------------------- |
| **Claim without approval**        | No streak update             | No streak update                        | Streaks only count approvals             |
| **Multiple claims, one approval** | Streak +1                    | Streak +1                               | First approval counts                    |
| **Approve 2 claims same day**     | Streak +1                    | Streak +1                               | Only first approval extends streak       |
| **Approve claim from yesterday**  | Depends on today's streak    | Check: last_approved vs last occurrence | Uses approval timestamp, not completion  |
| **Bulk approve 5 claims**         | All trigger streak logic     | Each checks against schedule            | May restore broken streaks retroactively |
| **Disapprove then approve**       | Streak breaks on disapproval | Disapproval ignored for streaks         | Streaks measure approvals only           |

### Vacation & Pauses

| Scenario                | Schedule Config                       | Pattern                             | Legacy Result | New Result       | Implementation                  |
| ----------------------- | ------------------------------------- | ----------------------------------- | ------------- | ---------------- | ------------------------------- |
| **Pause chore 2 weeks** | `pause: 14 days`                      | Weeks 1-2: paused, Week 3: complete | Streak = 1    | Streak continues | No occurrences during pause     |
| **Manual reschedule**   | Parent pushes due date +3 days        | Complete on new date                | Streak breaks | Streak continues | Uses updated occurrence         |
| **Vacation mode**       | Set `applicable_days: []` for 10 days | No completions for 10 days          | Streak = 0    | Streak paused    | Zero occurrences = no break     |
| **Sick day**            | Skip one occurrence                   | Miss Monday chore                   | Streak = 0    | Streak = 0       | Missed occurrence breaks streak |

### Schedule Changes Mid-Streak

| Change Type                      | Example                                 | Current Streak                     | After Change     | New System Behavior                           |
| -------------------------------- | --------------------------------------- | ---------------------------------- | ---------------- | --------------------------------------------- |
| **Daily → Every 3 Days**         | Streak of 10 daily → change to 3-day    | Reset to 0                         | Preserve 10      | Streak count unchanged (measures consistency) |
| **Every 3 Days → Daily**         | Streak of 5 (15 days) → change to daily | Reset to 0                         | Preserve 5       | Next day must complete to continue            |
| **Add `applicable_days`**        | Daily → Mon-Fri only                    | Continue                           | Continue         | Weekend days removed from occurrence list     |
| **Change due time**              | 9am → 5pm                               | Continue                           | Continue         | Only date matters for streaks                 |
| **Change from weekly Mon → Tue** | Streak of 4                             | Continue if complete within 7 days | Streak continues | Next occurrence is Tuesday                    |

### Multi-Claim Chores

| Chore Type              | Allow Multiple? | Pattern                      | Streak Count               | Notes                            |
| ----------------------- | --------------- | ---------------------------- | -------------------------- | -------------------------------- |
| **Standard chore**      | No              | Complete once per occurrence | 1 per occurrence           | Normal behavior                  |
| **Multi-claim daily**   | Yes             | Complete 3x on Monday        | 1 (not 3)                  | Only first completion counts     |
| **Shared chore**        | N/A (shared)    | Kid A: Mon, Kid B: Tue       | Kid A: 1, Kid B: continues | Per-kid tracking                 |
| **Multi-claim + early** | Yes             | Mon: 2x, Tue (due): 1x       | 2                          | Mon counts as 1, Tue counts as 1 |

---

## Implementation Approach Comparison

### Option 1: Fully Schedule-Aware (Recommended)

**How It Works**:

```python
def update_streak_on_approval(chore_id, kid_id, approval_time):
    schedule = chore.schedule_config
    last_approved = kid_chore_data.last_approved_time

    # Check: Did we miss any occurrences?
    missed = ScheduleEngine.has_missed_occurrences(
        last_completion=last_approved,
        current_completion=approval_time,
        schedule=schedule
    )

    if missed:
        current_streak = 1  # Broke streak, start fresh
    else:
        current_streak = previous_streak + 1  # Continue streak
```

**Pros**:

- ✅ Works for ALL schedule types
- ✅ Accurate for real-world use cases
- ✅ Handles vacations/pauses correctly
- ✅ Future-proof for new schedule features

**Cons**:

- ❌ Requires ScheduleEngine enhancement
- ❌ More complex migration logic
- ❌ Retroactive calculation impossible (need historical schedule state)

**Migration Strategy**: Preserve all existing streak values!

- Read previous streak from period data (already there)
- On next approval, use schedule-aware logic to continue or break
- Example: Streak of 10 on Jan 19 → complete Jan 20 → check schedule → streak 11 if on-time

---

### Option 2: Hybrid (Daily Unchanged, Others Schedule-Aware)

**How It Works**:

```python
def update_streak_on_approval(chore_id, kid_id, approval_time):
    schedule = chore.schedule_config

    if schedule.is_daily():
        # Use legacy day-gap logic
        if (approval_time.date() - last_approved.date()).days == 1:
            current_streak = previous_streak + 1
        else:
            current_streak = 1
    else:
        # Use schedule-aware logic
        missed = ScheduleEngine.has_missed_occurrences(...)
        current_streak = 1 if missed else previous_streak + 1
```

**Pros**:

- ✅ No migration needed for daily chores (largest use case)
- ✅ Fixes non-daily schedules immediately
- ✅ Simpler migration

**Cons**:

- ❌ Two code paths to maintain
- ❌ Daily chores still break on vacations
- ❌ Inconsistent UX (why do daily chores break but weekly don't?)

---

### Option 3: Enhanced Day-Gap (No ScheduleEngine)

**How It Works**:

```python
def update_streak_on_approval(chore_id, kid_id, approval_time):
    schedule = chore.schedule_config
    day_gap = (approval_time.date() - last_approved.date()).days
    expected_gap = schedule.typical_interval_days()  # New helper

    if day_gap <= expected_gap + grace_days:
        current_streak = previous_streak + 1
    else:
        current_streak = 1
```

**Pros**:

- ✅ Simple implementation (no ScheduleEngine changes)
- ✅ Works for basic schedules
- ✅ Easy migration

**Cons**:

- ❌ Fails for irregular schedules (1st Monday of month)
- ❌ Can't handle `applicable_days` (weekday-only)
- ❌ No vacation/pause support
- ❌ Grace period is arbitrary (2 days? 3 days?)

---

### Option 4: Separate "Consistency Score" (Don't Call It Streaks)

**How It Works**:

```python
# New field: consistency_percentage
consistency = {
    "expected_occurrences_30d": 10,
    "completed_on_time_30d": 8,
    "percentage": 80.0,
    "current_streak": 3  # Still track streaks separately
}
```

**Pros**:

- ✅ Doesn't break existing streaks
- ✅ Provides more meaningful metric
- ✅ Works for all schedule types
- ✅ Naturally handles vacations (fewer expected occurrences)

**Cons**:

- ❌ New concept to explain to users
- ❌ Requires new UI elements
- ❌ Doesn't solve the streak problem (just adds another metric)
- ❌ More data to store

---

## Recommended Implementation Path

### Phase 1: Foundation (1 week)

- [ ] Add `has_missed_occurrences()` to ScheduleEngine
- [ ] Add `get_expected_occurrence_before()` helper
- [ ] Create test suite with 20+ schedule patterns

### Phase 2: Streak Logic (3 days)

- [ ] Refactor `update_streak()` in StatisticsEngine
- [ ] Add schedule-aware logic with fallback
- [ ] Update period bucket writes

### Phase 3: Migration (1 day - Simple!)

- [ ] **NO DATA CHANGES** - Preserve all existing streak values
- [ ] No schema bump needed (logic change only)
- [ ] Testing: Existing streaks continue correctly

### Phase 4: Testing & Validation (5 days)

- [ ] Test all 40+ scenario patterns from matrix
- [ ] Validate with Stårblüm Family test data
- [ ] Performance testing (10k chores × 100 kids)

### Phase 5: Documentation (2 days)

- [ ] Update user-facing docs
- [ ] Add streak calculation explanation to UI
- [ ] Update translations

**Total Estimated Effort**: 2-3 weeks

---

## Decision Framework

### Choose Option 1 (Fully Schedule-Aware) If:

- ✅ Users heavily use non-daily schedules
- ✅ Vacation/pause handling is critical
- ✅ Want future-proof architecture
- ✅ Want simple migration (no data changes needed!)

### Choose Option 2 (Hybrid) If:

- ✅ Most users have daily chores
- ✅ Want zero disruption for existing users
- ✅ Can tolerate two code paths
- ✅ Non-daily fixes are "nice to have"

### Choose Option 3 (Enhanced Day-Gap) If:

- ✅ Need quick fix (< 1 week effort)
- ✅ Users have simple, regular schedules only
- ✅ Don't care about complex edge cases
- ❌ **NOT RECOMMENDED** (too limited)

### Choose Option 4 (Consistency Score) If:

- ✅ Want both metrics (streaks + consistency)
- ✅ Have UI bandwidth for new elements
- ✅ Users understand percentage-based goals
- ⚠️ **DEFER** (solves different problem)

---

## User-Facing Changes

### What Users Will Notice

**Good News** ✅:

- Weekly chores now track streaks correctly
- Vacation mode doesn't break streaks
- Multi-day chores show meaningful progress

**Trade-offs** ⚠️:

- Existing streaks may reset on upgrade (Option 1)
- "Streak" now means "consecutive on-time completions" not "consecutive days"
- Daily chores: no functional change (unless using vacation mode)

### Sample UI Explanation

**Before Upgrade**:

> "Current streak: 5 days" (for daily chore)

**After Upgrade** (Option 1):

> "Current streak: 5 completions" (for any schedule)
> "Last 5 scheduled occurrences completed on-time"

**After Upgrade** (Option 2):

> "Current streak: 5 days" (for daily chore)
> "Current streak: 5 weeks" (for weekly chore)

---

## Testing Checklist

### Schedule Pattern Coverage

- [ ] Daily chores (every 1 day)
- [ ] Multi-day intervals (every 2, 3, 5, 7 days)
- [ ] Weekly schedules (single day)
- [ ] Weekly schedules (multiple days)
- [ ] Monthly schedules (specific day)
- [ ] Monthly schedules (last day)
- [ ] Monthly schedules (first Monday)
- [ ] Custom intervals (every 2 weeks)
- [ ] `applicable_days` restrictions
- [ ] Pause/vacation scenarios

### Edge Case Coverage

- [ ] Early completions
- [ ] Late completions
- [ ] Multiple claims same day
- [ ] Bulk approval (5+ claims)
- [ ] Schedule change mid-streak
- [ ] Shared chores (per-kid streaks)
- [ ] Approval reset types (midnight, manual)
- [ ] Timezone edge cases (completion at 11:59pm)

### Migration Testing

- [ ] Empty storage (new install)
- [ ] Daily chores only (legacy users)
- [ ] Mixed schedule types
- [ ] Active streaks at upgrade time
- [ ] Very long streaks (100+ days)

---

## Open Questions

1. **Grace Period**: Should we allow 1-2 day grace for "almost on-time" completions?
   - **Recommendation**: No grace period (strict on-time = clearer rules)
   - **Alternative**: Add optional `streak_grace_days` config per chore

2. **Retroactive Calculation**: Can we rebuild streaks from historical data?
   - **Challenge**: Need schedule state at approval time (not stored)
   - **Recommendation**: Fresh start (reset all streaks)

3. **UI Display**: Show "days" vs "completions" in streak count?
   - **Recommendation**: Always show "completions" for consistency
   - **Alternative**: Show "5 days" for daily, "5 completions" for others

4. **Performance**: Is `has_missed_occurrences()` fast enough?
   - **Benchmark Target**: < 50ms for 100 occurrence checks
   - **Optimization**: Cache schedule calculations per day

---

## Next Steps

1. **Decision Required**: Choose implementation option (1, 2, or 3)
2. **Review Supporting Docs**:
   - STREAK_SYSTEM_SUP_STRATEGY.md (strategic rationale)
   - STREAK_SYSTEM_SUP_IMPLEMENTATION.md (technical design)
   - STREAK_SYSTEM_SUP_EDGE_CASES.md (trap analysis)
3. **Update Main Plan**: Add streak implementation to Phase 5 or 6
4. **Spike Task**: Build `has_missed_occurrences()` prototype (2 days)

---

## Appendix: Real-World Examples

### Example 1: Weekly Laundry (Every Monday)

**Schedule**: `weekly: [Monday]`

| Date       | Action      | Legacy Streak    | New Streak (Option 1) |
| ---------- | ----------- | ---------------- | --------------------- |
| Mon Jan 6  | Complete ✅ | 1                | 1                     |
| Tue-Sun    | (nothing)   | 0 (broke on Tue) | 1 (still going)       |
| Mon Jan 13 | Complete ✅ | 1                | 2                     |
| Mon Jan 20 | Skip ❌     | 0                | 0                     |
| Mon Jan 27 | Complete ✅ | 1                | 1                     |

### Example 2: Clean Bathroom (Every 3 Days)

**Schedule**: `every: 3 days`

| Date       | Action                  | Legacy Streak | New Streak (Option 1) |
| ---------- | ----------------------- | ------------- | --------------------- |
| Mon Jan 6  | Complete ✅             | 1             | 1                     |
| Tue Jan 7  | (off schedule)          | 0 (broke)     | 1 (still going)       |
| Wed Jan 8  | (off schedule)          | 0             | 1                     |
| Thu Jan 9  | Complete ✅ (due today) | 1             | 2                     |
| Fri Jan 10 | (off schedule)          | 0 (broke)     | 2 (still going)       |
| Sun Jan 12 | Complete ✅ (due today) | 1             | 3                     |

### Example 3: Vacation Break (Weekday Chore)

**Schedule**: `every: 1 day, applicable_days: [Mon-Fri]`

| Date       | Action          | Legacy Streak    | New Streak (Option 1) |
| ---------- | --------------- | ---------------- | --------------------- |
| Fri Jan 10 | Complete ✅     | 5                | 5                     |
| Sat Jan 11 | (not scheduled) | 0 (broke on Sat) | 5 (still going)       |
| Sun Jan 12 | (not scheduled) | 0                | 5                     |
| Mon Jan 13 | Complete ✅     | 1                | 6                     |

**Key Insight**: Option 1 preserves streaks through weekends for weekday-only chores.
