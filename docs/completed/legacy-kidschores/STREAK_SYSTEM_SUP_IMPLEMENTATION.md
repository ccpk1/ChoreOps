# Schedule-Aware Streak Implementation Design

**Supporting Doc for**: STREAK_SYSTEM_SUP_STRATEGY.md
**Created**: 2026-01-20
**Purpose**: Technical implementation plan for schedule-aware consistency tracking

---

## Overview

Transform chore streaks from "consecutive calendar days" to "consecutive completions on scheduled occurrences" using existing ScheduleEngine infrastructure.

---

## Current ScheduleEngine Capabilities

### What We Already Have

```python
class RecurrenceEngine:
    def get_next_occurrence(after: datetime, require_future: bool) -> datetime | None
        """Returns next scheduled occurrence after reference date."""

    def get_occurrences(start: datetime, end: datetime, limit: int) -> list[datetime]
        """Returns all occurrences between two dates."""
```

**Key Point**: `get_occurrences()` already provides the foundation for "did we miss any?" checks.

### What We Need to Add

```python
def has_missed_occurrences(
    self,
    last_completion: datetime,
    current_completion: datetime,
) -> bool:
    """Check if any scheduled occurrences were skipped.

    Returns:
        True if at least one occurrence between dates was missed.
        False if current_completion is on-time or early.
    """
```

**Implementation**:

```python
def has_missed_occurrences(
    self,
    last_completion: datetime,
    current_completion: datetime,
) -> bool:
    # Get all expected occurrences between the two dates (exclusive)
    expected = self.get_occurrences(
        start=last_completion,
        end=current_completion,
        limit=365  # Safety limit (1 year of daily occurrences)
    )

    # Filter to occurrences strictly between the dates
    # (exclude both last_completion and current_completion)
    missed_occurrences = [
        occ for occ in expected
        if last_completion < occ < current_completion
    ]

    return len(missed_occurrences) > 0
```

**Example Cases**:

```python
# Every 3 days chore
last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)  # Day 1
current = datetime(2026, 1, 4, 12, 0, 0, tzinfo=UTC)  # Day 4

expected = [datetime(2026, 1, 4, ...)]  # Day 4 is next occurrence
missed = []  # No occurrences strictly between Day 1 and Day 4
has_missed_occurrences() → False  # ✅ On time

# ---

last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)  # Day 1
current = datetime(2026, 1, 7, 12, 0, 0, tzinfo=UTC)  # Day 7

expected = [
    datetime(2026, 1, 4, ...),  # Day 4 - missed
    datetime(2026, 1, 7, ...)   # Day 7 - completing now
]
missed = [datetime(2026, 1, 4, ...)]  # Day 4 was skipped
has_missed_occurrences() → True  # ❌ Late (missed Day 4)
```

---

## Data Model Changes

### Storage (No Breaking Changes)

Current structure remains valid:

```python
kid_info["chore_data"][chore_id] = {
    "periods": {
        "daily": {
            "2026-01-19": {
                "claimed": 1,
                "approved": 1,
                "points": 10,
                "longest_streak": 5,  # ← Still here, different calculation
            }
        },
        "all_time": {
            "all_time": {
                "longest_streak": 12,  # ← Still tracked
            }
        }
    },
    "last_longest_streak_all_time": "2026-01-19",  # ← Keep metadata
}

kid_info["chore_stats"]["longest_streak_all_time"] = 12  # ← Keep kid-level
```

**Key Point**: Data structure unchanged; only the **calculation logic** changes.

### Algorithm Integration Points

**Where streak is calculated** (coordinator.py line ~4737):

```python
# CURRENT (day-based):
yesterday_streak = periods["daily"][yesterday_iso].get("longest_streak", 0)
today_streak = yesterday_streak + 1 if yesterday_streak > 0 else 1

# NEW (schedule-aware):
last_approved_date = kid_chore_data.get("last_approved")
schedule_config = self._build_schedule_config(chore_id, kid_id)
engine = RecurrenceEngine(schedule_config)

if not last_approved_date:
    # First completion ever
    new_streak = 1
else:
    last_approved_dt = parse_to_utc(last_approved_date)
    current_dt = now_utc

    # Check for missed occurrences
    if engine.has_missed_occurrences(last_approved_dt, current_dt):
        # Missed at least one → reset
        new_streak = 1
    else:
        # No misses → increment
        prev_streak = all_time_data.get("longest_streak", 0)
        new_streak = prev_streak + 1

# Store as before
daily_data["longest_streak"] = new_streak
```

---

## Implementation Steps

### Phase 1: Add ScheduleEngine Method (1 day)

**File**: `schedule_engine.py`

```python
def has_missed_occurrences(
    self,
    last_completion: datetime,
    current_completion: datetime,
) -> bool:
    """Check if any scheduled occurrences were missed between two completions.

    Args:
        last_completion: UTC datetime of previous approval
        current_completion: UTC datetime of current approval

    Returns:
        True if one or more scheduled occurrences were skipped.
        False if current completion is on-time or earlier than next expected.

    Example:
        # Every-3-days chore
        last = datetime(2026, 1, 1, 12, 0, 0)  # Day 1
        current = datetime(2026, 1, 4, 12, 0, 0)  # Day 4 (expected)
        has_missed_occurrences(last, current) → False  # On time

        current = datetime(2026, 1, 7, 12, 0, 0)  # Day 7 (late)
        has_missed_occurrences(last, current) → True  # Missed Day 4
    """
    if self._frequency == const.FREQUENCY_NONE:
        return False  # No schedule = no misses possible

    # Get all expected occurrences in range (exclusive of endpoints)
    expected = self.get_occurrences(
        start=last_completion,
        end=current_completion,
        limit=365,  # Safety: 1 year of daily occurrences max
    )

    # Filter to strictly between dates (exclude both endpoints)
    missed = [
        occ for occ in expected
        if last_completion < occ < current_completion
    ]

    return len(missed) > 0
```

**Tests** (`tests/test_schedule_engine.py`):

```python
def test_has_missed_occurrences_daily_chore_on_time():
    """Daily chore completed on consecutive days - no misses."""
    config = {"frequency": FREQUENCY_DAILY, "base_date": "2026-01-01"}
    engine = RecurrenceEngine(config)

    last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    current = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)

    assert not engine.has_missed_occurrences(last, current)

def test_has_missed_occurrences_daily_chore_late():
    """Daily chore skipped a day - has miss."""
    config = {"frequency": FREQUENCY_DAILY, "base_date": "2026-01-01"}
    engine = RecurrenceEngine(config)

    last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    current = datetime(2026, 1, 3, 12, 0, 0, tzinfo=UTC)  # Missed Day 2

    assert engine.has_missed_occurrences(last, current)

def test_has_missed_occurrences_every_3_days_on_time():
    """Custom 3-day interval - completed on time."""
    config = {
        "frequency": FREQUENCY_CUSTOM_FROM_COMPLETE,
        "interval": 3,
        "interval_unit": TIME_UNIT_DAYS,
        "base_date": "2026-01-01",
    }
    engine = RecurrenceEngine(config)

    last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)  # Day 1
    current = datetime(2026, 1, 4, 12, 0, 0, tzinfo=UTC)  # Day 4 (on time)

    assert not engine.has_missed_occurrences(last, current)

def test_has_missed_occurrences_every_3_days_late():
    """Custom 3-day interval - missed one occurrence."""
    config = {
        "frequency": FREQUENCY_CUSTOM_FROM_COMPLETE,
        "interval": 3,
        "interval_unit": TIME_UNIT_DAYS,
        "base_date": "2026-01-01",
    }
    engine = RecurrenceEngine(config)

    last = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)  # Day 1
    current = datetime(2026, 1, 7, 12, 0, 0, tzinfo=UTC)  # Day 7 (late - missed Day 4)

    assert engine.has_missed_occurrences(last, current)

def test_has_missed_occurrences_weekly_mon_wed_fri():
    """Weekly Mon/Wed/Fri - completed on time."""
    config = {
        "frequency": FREQUENCY_WEEKLY,
        "applicable_days": [0, 2, 4],  # Mon, Wed, Fri
        "base_date": "2026-01-05",  # Monday
    }
    engine = RecurrenceEngine(config)

    last = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)  # Monday
    current = datetime(2026, 1, 7, 12, 0, 0, tzinfo=UTC)  # Wednesday

    assert not engine.has_missed_occurrences(last, current)  # No Tuesday expected

def test_has_missed_occurrences_weekly_mon_wed_fri_missed():
    """Weekly Mon/Wed/Fri - missed Wednesday."""
    config = {
        "frequency": FREQUENCY_WEEKLY,
        "applicable_days": [0, 2, 4],  # Mon, Wed, Fri
        "base_date": "2026-01-05",  # Monday
    }
    engine = RecurrenceEngine(config)

    last = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)  # Monday
    current = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)  # Friday (missed Wed)

    assert engine.has_missed_occurrences(last, current)  # Wednesday was skipped
```

**Validation**:

```bash
python -m pytest tests/test_schedule_engine.py::test_has_missed -v
```

---

### Phase 2: Add Schedule Config Builder (1 day)

**File**: `coordinator.py`

```python
def _build_schedule_config_for_chore(
    self, chore_id: str, kid_id: str
) -> ScheduleConfig:
    """Build ScheduleConfig for streak calculation.

    Args:
        chore_id: Chore internal ID
        kid_id: Kid internal ID

    Returns:
        ScheduleConfig dict for RecurrenceEngine
    """
    chore_data = self.chores_data.get(chore_id, {})
    kid_info = self.kids_data.get(kid_id, {})

    # Get base configuration
    approval_reset_type = chore_data.get(
        const.DATA_CHORE_APPROVAL_RESET_TYPE,
        const.DEFAULT_APPROVAL_RESET_TYPE,
    )

    # Map reset type to frequency
    frequency_map = {
        const.APPROVAL_RESET_AT_MIDNIGHT_ONCE: const.FREQUENCY_DAILY,
        const.APPROVAL_RESET_AT_MIDNIGHT_MULTI: const.FREQUENCY_DAILY,
        const.APPROVAL_RESET_UPON_COMPLETION: const.FREQUENCY_CUSTOM_FROM_COMPLETE,
        # Due date types need more complex handling
    }

    frequency = frequency_map.get(approval_reset_type, const.FREQUENCY_NONE)

    # Get applicable days (with per-kid override)
    per_kid_days = chore_data.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
    applicable_days = per_kid_days.get(
        kid_id,
        chore_data.get(const.DATA_CHORE_APPLICABLE_DAYS, [])
    )

    # For custom intervals, get interval config
    interval = 1
    interval_unit = const.TIME_UNIT_DAYS
    if approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION:
        # Parse from due_date_info if available
        due_date_info = chore_data.get(const.DATA_CHORE_DUE_DATE_INFO, {})
        interval = due_date_info.get("interval", 1)
        interval_unit = due_date_info.get("interval_unit", const.TIME_UNIT_DAYS)

    # Base date = last approval or chore creation date
    kid_chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {}).get(chore_id, {})
    base_date = kid_chore_data.get(
        const.DATA_KID_CHORE_DATA_LAST_APPROVED,
        chore_data.get(const.DATA_CHORE_CREATED, kh.dt_now_iso())
    )

    return {
        "frequency": frequency,
        "interval": interval,
        "interval_unit": interval_unit,
        "applicable_days": applicable_days,
        "base_date": base_date,
    }
```

---

### Phase 3: Refactor Streak Calculation (2 days)

**File**: `coordinator.py` (lines 4737-4795)

**Before**:

```python
# Calculate today's streak based on yesterday's daily period data
yesterday_local_iso = kh.dt_add_interval(...)
yesterday_chore_data = periods_data["daily"].get(yesterday_local_iso, {})
yesterday_streak = yesterday_chore_data.get("longest_streak", 0)
today_streak = yesterday_streak + 1 if yesterday_streak > 0 else 1
```

**After**:

```python
# Calculate schedule-aware streak
schedule_config = self._build_schedule_config_for_chore(chore_id, kid_id)
engine = RecurrenceEngine(schedule_config)

last_approved_str = kid_chore_data.get(const.DATA_KID_CHORE_DATA_LAST_APPROVED)

if not last_approved_str:
    # First approval ever
    new_streak = 1
else:
    # Parse last approval to UTC datetime
    last_approved_dt = kh.parse_to_utc(last_approved_str)
    current_dt = now_utc

    # Check if any expected occurrences were missed
    try:
        if engine.has_missed_occurrences(last_approved_dt, current_dt):
            # Missed at least one scheduled occurrence → reset
            new_streak = 1
        else:
            # No misses → continue streak
            prev_streak = all_time_data.get(const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0)
            new_streak = prev_streak + 1
    except Exception as ex:
        # Fallback: if schedule calculation fails, increment conservatively
        const.LOGGER.warning(
            "Streak calculation failed for chore %s, kid %s: %s",
            chore_id, kid_id, ex
        )
        prev_streak = all_time_data.get(const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0)
        new_streak = prev_streak + 1

# Store as before (unchanged)
daily_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = new_streak
all_time_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = max(
    all_time_data.get(const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK, 0),
    new_streak
)
```

---

### Phase 4: Migration Strategy (1 day)

**Option A: Reset All Streaks** (Recommended)

```python
def _migrate_streaks_to_schedule_aware(self) -> None:
    """Reset all chore streaks for schedule-aware implementation.

    Legacy streaks were day-based and incompatible with new logic.
    Clean slate ensures consistent behavior going forward.
    """
    for kid_info in self.coordinator.kids_data.values():
        chore_data = kid_info.get(const.DATA_KID_CHORE_DATA, {})

        for chore_entry in chore_data.values():
            periods = chore_entry.get(const.DATA_KID_CHORE_DATA_PERIODS, {})

            # Reset all period longest_streaks to 0
            for period_type in ["daily", "weekly", "monthly", "yearly", "all_time"]:
                bucket = periods.get(period_type, {})
                for period_data in bucket.values():
                    period_data[const.DATA_KID_CHORE_DATA_PERIOD_LONGEST_STREAK] = 0

        # Reset kid-level all-time streak
        chore_stats = kid_info.get(const.DATA_KID_CHORE_STATS, {})
        chore_stats[const.DATA_KID_CHORE_STATS_LONGEST_STREAK_ALL_TIME] = 0

    const.LOGGER.info("Migrated streaks to schedule-aware calculation (reset to 0)")
```

**Option B: Best-Effort Preservation** (Complex, Low Value)

- Attempt to infer if old streak was "valid" under new rules
- Too complex, too many edge cases, low benefit
- **Not recommended**

---

## Testing Strategy

### Unit Tests

**ScheduleEngine** (`tests/test_schedule_engine.py`):

- 6+ tests for `has_missed_occurrences()` covering:
  - Daily chores (on-time, late)
  - Custom intervals (every N days)
  - Weekly with applicable_days
  - Edge cases (same-day, very late)

**Coordinator** (`tests/test_streak_schedule_aware.py`):

- Test streak increment for on-time approval
- Test streak reset for missed occurrence
- Test first approval (streak = 1)
- Test fallback on schedule calculation error

### Integration Tests

**Workflow Tests** (`tests/test_workflow_streaks.py`):

```python
def test_daily_chore_streak_increments():
    """Daily chore approved daily → streak increments."""
    # Day 1: Approve → streak 1
    # Day 2: Approve → streak 2
    # Day 3: Approve → streak 3

def test_every_3_days_chore_streak():
    """Every-3-days chore approved consistently → streak increments."""
    # Day 1: Approve → streak 1
    # Day 4: Approve → streak 2 (on time)
    # Day 7: Approve → streak 3

def test_every_3_days_chore_missed():
    """Every-3-days chore with miss → streak resets."""
    # Day 1: Approve → streak 1
    # Day 4: Miss (don't approve)
    # Day 7: Approve → streak 1 (reset)

def test_weekly_mon_wed_fri_streak():
    """Weekly Mon/Wed/Fri approved consistently → streak increments."""
    # Mon: Approve → streak 1
    # Wed: Approve → streak 2
    # Fri: Approve → streak 3
    # (Tue/Thu are not scheduled days, don't break streak)

def test_weekly_mon_wed_fri_missed_wednesday():
    """Weekly Mon/Wed/Fri with miss → streak resets."""
    # Mon: Approve → streak 1
    # Wed: Miss
    # Fri: Approve → streak 1 (reset)
```

---

## Performance Considerations

### ScheduleEngine Call Overhead

**Current**: O(1) - simple yesterday lookup
**New**: O(n) - where n = occurrences between last and current approval

**Mitigation**:

- `get_occurrences()` has `limit=365` safety cap
- Typical case: 1-7 day gap → negligible overhead
- Worst case: 1 year gap with daily chore → 365 iterations (acceptable)

### Caching Opportunities

RecurrenceEngine instances could be cached per chore:

```python
self._streak_engines: dict[str, RecurrenceEngine] = {}  # chore_id → engine

def _get_streak_engine(self, chore_id: str, kid_id: str) -> RecurrenceEngine:
    """Get or create cached RecurrenceEngine for streak calculation."""
    cache_key = f"{chore_id}_{kid_id}"
    if cache_key not in self._streak_engines:
        config = self._build_schedule_config_for_chore(chore_id, kid_id)
        self._streak_engines[cache_key] = RecurrenceEngine(config)
    return self._streak_engines[cache_key]
```

**Trade-off**: Added memory vs repeated instantiation cost (profile if needed).

---

## Rollout Plan

### Version 0.6.0 (Breaking Change)

1. **Implement** new schedule-aware streak logic
2. **Reset** all streaks to 0 (migration)
3. **Document** in release notes: "Streaks now track consistency with chore schedules"
4. **Update** wiki examples showing new behavior

### Communication

**Release Notes**:

```
## 🔄 Breaking Change: Schedule-Aware Streaks

Chore streaks now track **consistency with the chore's schedule** rather than consecutive calendar days.

### What Changed

- **Daily chores**: Behavior unchanged (still consecutive days)
- **Non-daily chores**: Now properly track streak (e.g., every-3-days chore can have streak > 1)
- **Weekly chores**: Streaks only break if scheduled day is missed (not every day)

### Migration Impact

All existing streaks have been reset to 0. New streaks will begin building from this release forward.

### Why This Change?

Previous implementation penalized kids for having non-daily chores. A child completing an every-3-day chore perfectly would never show improvement.
```

---

## Open Questions

1. **Achievement streaks**: Do achievement-based streaks (ACHIEVEMENT_TYPE_STREAK) need same logic?
2. **Per-kid schedules**: Does `per_kid_applicable_days` need special handling?
3. **Completion percentage**: Add alongside streaks or defer?

---

## Success Criteria

- ✅ Daily chores: behavior unchanged from current
- ✅ Every-3-days chore: can achieve streak > 1
- ✅ Weekly Mon/Wed/Fri: doesn't break on Tue/Thu
- ✅ All tests pass (824 existing + ~15 new)
- ✅ Performance: < 10ms overhead per approval
- ✅ MyPy clean, lint clean

---

## Estimated Timeline

| Phase                           | Duration | Dependencies |
| ------------------------------- | -------- | ------------ |
| 1. Add has_missed_occurrences() | 1 day    | None         |
| 2. Schedule config builder      | 1 day    | Phase 1      |
| 3. Refactor streak calculation  | 2 days   | Phase 1-2    |
| 4. Migration & cleanup          | 1 day    | Phase 3      |
| 5. Testing & validation         | 2 days   | All phases   |

**Total**: 7 days

---

**Next Action**: Implement Phase 1 (`has_missed_occurrences()` method in ScheduleEngine)
