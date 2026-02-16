# Schedule-Aware Streaks: Edge Cases & Traps

**Supporting Doc for**: STREAK_SYSTEM_SUP_IMPLEMENTATION.md
**Created**: 2026-01-20
**Purpose**: Identify edge cases and design safeguards

---

## Critical Edge Cases

### 1. Manual Due Date Reschedule (Vacation/Trip)

**Scenario**: Kid goes on vacation, parent reschedules chore forward 1 week.

```
Mon: Chore due (every Mon/Wed/Fri)
Wed: Kid leaves for vacation
Parent action: Reschedule due date to next Monday
Fri: (original due date) - Kid not home
Mon: Kid returns, completes chore
```

**Problem with naive implementation**:

- `has_missed_occurrences(last_Monday, next_Monday)` would show Wed & Fri as "missed"
- Streak breaks despite parent explicitly excusing absence

**Solution Options**:

**Option A: Track reschedule events**

```python
chore_data["rescheduled_dates"] = ["2026-01-19"]  # Dates that were manually moved
# In streak calculation, exclude rescheduled dates from missed check
```

❌ **Problem**: Complex, requires new data structure, migration

**Option B: Update base_date on reschedule**

```python
# When parent reschedules:
kid_chore_data["base_date_override"] = new_due_date
# Streak engine uses override as new baseline
```

⚠️ **Problem**: Changes future schedule, might not be desired

**Option C: Ignore misses if gap > threshold**

```python
# If time between approvals > 14 days, assume intentional gap
# Don't break streak, just don't increment
if days_since_last > 14:
    return current_streak  # Hold steady, don't increment or reset
```

⚠️ **Problem**: Arbitrary threshold, doesn't distinguish vacation from laziness

**Option D: Require explicit streak preservation** (Recommended)

```python
# Parent action: "Excuse absence" checkbox when rescheduling
if chore_data.get("excuse_next_miss"):
    # Next miss doesn't break streak
    chore_data["excuse_next_miss"] = False  # One-time use
```

✅ **Benefits**:

- Explicit parent control
- No ambiguity
- Simple implementation

---

### 2. Approval Reset Type Complexity

**Current Reset Types**:

- `at_midnight_once` - Daily reset, one claim
- `at_midnight_multi` - Daily reset, multiple claims
- `at_due_date_once` - Due date based
- `at_due_date_multi` - Due date based, multiple
- `upon_completion` - Custom interval from approval

**Problem**: Different reset types have different "expected occurrence" semantics.

#### Case 2A: `at_midnight_once` vs `at_midnight_multi`

**Question**: Does claiming twice in one day count as 2 streaks or 1?

```
Daily chore, at_midnight_multi:
8am: Kid completes → Count 1
2pm: Kid completes again → Count 2 or still 1?
```

**Resolution**: Streak = unique **days** with at least one approval, not total approvals.

- Multiple claims same day = still streak of 1 for that day
- Streak increments daily, not per-approval

#### Case 2B: `upon_completion` with long intervals

**Every 30 days chore**:

```
Day 1: Approve → streak 1
Day 31: Approve → streak 2
Day 61: Approve → streak 3
Day 100: Approve (late, should be Day 91) → streak reset or 1?
```

**Resolution**: Use `has_missed_occurrences()` as designed - Day 91 was missed, reset to 1.

#### Case 2C: Due date chores with flexible timing

**Chore due "by end of week"**:

```
Monday: Chore becomes available
Sunday: Chore due
Kid completes Wednesday - is this "on time" for streak?
```

**Problem**: Schedule engine needs to know "availability window" vs "due deadline".

**Resolution**: For due-date chores, use **due date** as the occurrence, not availability start.

- If approved before due date: counts as on-time
- If approved after due date but before next occurrence: late but doesn't break streak
- If approved after next occurrence arrives: breaks streak

---

### 3. Shared Chores & Multi-Kid Tracking

#### Case 3A: Shared First

**Setup**: Chore shared by 3 kids (first to claim wins).

```
Monday (scheduled day):
- Kid A claims & gets approved → A's streak = 1
- Kid B & C miss (because A already claimed)
```

**Question**: Do B & C's streaks break?

**Resolution**: Shared-first chores should **not** break non-claimer streaks.

- Only track streak for kid who actually claims
- Other kids: streak stays unchanged (neither increment nor reset)

#### Case 3B: Shared All

**Setup**: All 3 kids must complete.

```
Monday (scheduled day):
- Kid A completes → A's streak = 1
- Kid B completes → B's streak = 1
- Kid C misses → C's streak = 0 (reset)
```

**Resolution**: Each kid tracked independently for shared-all.

---

### 4. Auto-Approval Chores

**Setup**: Chore auto-approves on claim (no parent approval step).

**Question**: What's the "approval date" for streak calculation?

```
Monday: Kid claims (auto-approved)
→ Use claim timestamp as "approval date"
```

**Resolution**: For auto-approve chores, treat `last_claimed` as `last_approved` for streak purposes.

```python
if chore_is_auto_approve:
    last_completion = kid_chore_data.get("last_claimed")
else:
    last_completion = kid_chore_data.get("last_approved")
```

---

### 5. Per-Kid Schedule Overrides

**Setup**: Chore has different schedules per kid.

```
Chore baseline: Mon/Wed/Fri
Kid A override: Mon/Wed/Fri (same)
Kid B override: Tue/Thu (different)
```

**Challenge**: Schedule engine needs kid-specific config.

**Resolution**: Build schedule config with per-kid overrides:

```python
def _build_schedule_config_for_chore(self, chore_id: str, kid_id: str):
    # Get per-kid applicable_days override
    per_kid_days = chore_data.get("per_kid_applicable_days", {})
    applicable_days = per_kid_days.get(
        kid_id,
        chore_data.get("applicable_days", [])
    )

    return {
        "applicable_days": applicable_days,  # Kid-specific
        ...
    }
```

✅ Already handles this in implementation design.

---

### 6. Chore Schedule Changes Mid-Streak

**Scenario**: Parent changes chore from daily to weekly.

```
Week 1-2: Daily chore, kid has 14-day streak
Parent changes to: Weekly (Mon only)
Week 3 Monday: Kid completes
```

**Question**: Is this continuation (15) or reset (1)?

**Problem**: Old streak was "14 consecutive days", new metric is "weeks completed".

**Resolution Options**:

**Option A: Reset on schedule change**

```python
# When chore schedule changes:
chore_data["schedule_change_date"] = today
# In streak calc: if schedule changed since last approval, reset
```

**Option B: Preserve streak value but change meaning**

```python
# Keep streak value, just interpret differently going forward
# 14 days → becomes "14 completions" under new schedule
```

**Recommendation**: Option A (reset on schedule change)

- Cleanest semantics
- Avoids confusion about "what does streak mean?"
- Document in UI: "Changing schedule will reset streaks"

---

### 7. Chore Disabled/Paused

**Scenario**: Parent disables chore for 2 weeks (kid's surgery recovery).

```
Monday: Last approval (streak = 10)
Parent: Disable chore
<2 weeks pass>
Parent: Re-enable chore
Monday: Kid completes
```

**Question**: Continue streak (11) or reset (1)?

**Resolution**: **Pause streak while disabled**

```python
if chore_is_disabled:
    # Don't calculate streak at all
    # On re-enable, use last_approved date from before disable
    # Next approval continues streak if within expected timeframe
    pass
```

**Implementation**:

- Track `chore_data["disabled_date"]`
- Exclude disabled period from `has_missed_occurrences()` range
- On re-enable, calculate from last approval before disable

---

### 8. Grace Periods & Same-Day Timing

**Scenario**: Chore due 8pm, kid completes 11:59pm.

```
8pm: Due time
11:59pm: Kid claims & approves
```

**Question**: On-time (streak continues) or late (streak resets)?

**Problem**: ScheduleEngine works with dates, not times.

**Resolution**: **Grace period = end of day**

```python
# ScheduleEngine compares dates, not times
# Any approval on scheduled date = on-time
# Example: Daily chore
#   Expected: 2026-01-19
#   Completed: 2026-01-19 23:59:59 → ON TIME ✅
#   Completed: 2026-01-20 00:00:01 → LATE (missed 1/19)
```

This aligns with user expectations - "I did it today" means before midnight.

---

### 9. Overdue Then Approved

**Scenario**: Chore goes overdue, then parent approves anyway.

```
Monday 8am: Due
Tuesday 10am: Still pending (overdue)
Tuesday 2pm: Parent approves
```

**Question**: Does overdue state affect streak?

**Resolution**: **Approval time is source of truth**

- Overdue is a display state, not a streak factor
- `has_missed_occurrences()` checks scheduled dates, not overdue status
- If approved Tuesday but Monday was scheduled → missed Monday → reset

**No special handling needed** - natural behavior is correct.

---

### 10. Multiple Claims Per Day (at_midnight_multi)

**Scenario**: Daily chore, kid completes 3 times in one day.

```
Monday 8am: Claim & approve
Monday 2pm: Claim & approve
Monday 8pm: Claim & approve
```

**Question**: 3 streaks or 1?

**Resolution**: **Streak = days, not claims**

```python
# Only increment streak once per day
daily_data = periods["daily"][today_iso]
if "longest_streak" already updated today:
    return  # Don't increment again
else:
    daily_data["longest_streak"] = new_streak
```

**Implementation**: Check if today's daily bucket already has streak recorded.

---

### 11. Early Completion (Before Scheduled)

**Scenario**: Weekly Monday chore, kid completes on Saturday.

```
Last Monday: Completed (streak = 5)
Saturday (2 days early): Completes again
Next Monday: (scheduled day)
```

**Question**: Does Saturday count toward streak?

**Options**:

**Option A: Early counts** (Proactive behavior rewarded)

```python
# Saturday counts as "next week's completion"
# Monday becomes "already done"
```

**Option B: Early doesn't count** (Only scheduled days count)

```python
# Saturday ignored for streak purposes
# Monday is still the "expected" completion
```

**Option C: Early allowed with limits** (Recommended)

```python
# Can complete up to 1 occurrence early
next_expected = engine.get_next_occurrence(last_approved)
if current <= next_expected + timedelta(days=2):  # 2-day early grace
    # Count as on-time
else:
    # Too early, doesn't count yet
```

**Recommendation**: Option C with configurable early grace period.

---

### 12. Approval vs Claim Timing Mismatch

**Scenario**: Kid claims Monday, parent approves Wednesday.

```
Monday 9am: Kid claims
<2 days pass, no approval>
Wednesday 3pm: Parent finally approves
```

**Question**: Use claim date or approval date for streak?

**Resolution**: **Always use approval date**

- Approval is the authoritative "completion" event
- Claim is just a request
- Schedule-aware streak checks if approval happened on expected date

---

## Recommended Safeguards

### 1. Fallback on Schedule Engine Failure

```python
try:
    if engine.has_missed_occurrences(last_approved, current):
        new_streak = 1
    else:
        new_streak = prev_streak + 1
except Exception as ex:
    # Schedule calculation failed - be conservative
    LOGGER.warning("Streak calc failed: %s", ex)
    # Default: increment (don't punish kid for system error)
    new_streak = prev_streak + 1
```

### 2. Maximum Lookback Window

```python
# Limit lookback to prevent expensive calculations
MAX_LOOKBACK_DAYS = 90

if (current - last_approved).days > MAX_LOOKBACK_DAYS:
    # Gap too large - reset streak
    new_streak = 1
else:
    # Normal calculation
    if engine.has_missed_occurrences(...):
        new_streak = 1
```

### 3. Schedule Change Detection

```python
# Track last schedule config hash
chore_data["schedule_hash"] = hash_schedule_config(config)

if current_hash != chore_data.get("schedule_hash"):
    # Schedule changed - reset streak
    new_streak = 1
    chore_data["schedule_hash"] = current_hash
```

### 4. Excuse/Skip Mechanism

```python
# Parent button: "Excuse next miss"
if parent_excused_absence:
    chore_data["excused_until"] = next_due_date

# In streak calc:
if chore_data.get("excused_until") and current < excused_until:
    # This miss is excused, hold streak
    return current_streak  # Don't increment or reset
```

---

## Decision Matrix

| Edge Case         | Behavior                 | Rationale                 |
| ----------------- | ------------------------ | ------------------------- |
| Manual reschedule | Add "excuse miss" button | Explicit parent control   |
| Multi claims/day  | Count as 1 day           | Streak = days, not claims |
| Shared first      | Only track claimer       | Non-claimers unaffected   |
| Shared all        | Track each independently | Each kid's responsibility |
| Auto-approve      | Use claim date           | Claim = completion        |
| Per-kid schedule  | Kid-specific config      | Already handled           |
| Schedule change   | Reset streak             | Avoid semantic confusion  |
| Chore disabled    | Pause streak             | Exclude disabled time     |
| Grace period      | End of scheduled day     | Date-based, not time      |
| Overdue→Approved  | Use approval date        | Approval is truth         |
| Early completion  | Allow 2-day early grace  | Reward proactive          |
| Claim≠Approval    | Use approval date        | Approval authoritative    |

---

## Implementation Priorities

### Phase 1 (MVP) - Must Have

- ✅ Basic schedule-aware streak
- ✅ Per-kid schedule support
- ✅ Auto-approve handling
- ✅ Shared chore logic
- ✅ Fallback on errors

### Phase 2 - Nice to Have

- 🔲 "Excuse miss" button for parents
- 🔲 Schedule change detection → reset
- 🔲 Chore disable → pause streak
- 🔲 Early completion grace period

### Phase 3 - Advanced

- 🔲 Streak preservation on reschedule
- 🔲 Streak analytics (completion rate, etc.)
- 🔲 UI indicator for "streak at risk"

---

## Testing Requirements

Each edge case needs explicit test coverage:

```python
# tests/test_streak_edge_cases.py

def test_streak_multi_claims_same_day():
    """Multiple approvals same day = 1 streak day."""

def test_streak_shared_first_non_claimer():
    """Shared-first: non-claimer streak unaffected."""

def test_streak_auto_approve_uses_claim_date():
    """Auto-approve chores use claim timestamp."""

def test_streak_schedule_change_resets():
    """Changing schedule resets streak."""

def test_streak_early_completion_within_grace():
    """Completing 2 days early counts."""

def test_streak_fallback_on_engine_error():
    """Engine error doesn't break streak unfairly."""
```

---

## Open Questions for Decision

1. **Excuse mechanism**: Manual button vs automatic detection?
2. **Early grace period**: 0, 1, 2, or configurable days?
3. **Long gap threshold**: 90 days reasonable or adjust?
4. **Schedule change**: Auto-reset or warn user first?
5. **Disabled chore**: Pause streak or just ignore period?

---

**Recommendation**: Start with Phase 1 MVP, add Phase 2 based on user feedback.
