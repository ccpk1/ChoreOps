# Phase 6B Detailed Execution Plan

## Status: ✅ COMPLETE (2025-01-29)

## Executive Summary

**Goal**: Update streak calculation to use `last_completed` (when work was done) instead of `last_approved` (when parent approved). This makes streaks "parent-lag-proof" - a kid who claims Monday but gets approved Wednesday still gets Monday credit.

**Scope**:

- 1 engine file (`chore_engine.py`)
- 1 manager file (`chore_manager.py`)
- 1 test file (`test_workflow_streak_schedule.py`)

**Estimated Changes**: ~25 lines modified across 3 files

---

## Pre-Implementation Checklist

- [x] Constant `DATA_KID_CHORE_DATA_LAST_COMPLETED` exists in `const.py` (line 798)
- [x] `_set_last_completed_timestamp()` correctly writes to per-kid for INDEPENDENT (line 3060-3063)
- [x] Tests pass before changes: `pytest tests/test_workflow_streak_schedule.py -v`

## Validation Results (2025-01-29)

```
✅ Lint: All checks passed (ruff + boundary checks)
✅ MyPy: 0 errors (46 source files)
✅ Streak tests: 11/11 passed
✅ Full suite: 1148 passed, 2 skipped, 3 warnings
```

---

## Step-by-Step Implementation

### Step 1: Update `ChoreEngine.calculate_streak()` Parameter Names

**File**: `custom_components/kidschores/engines/chore_engine.py`
**Line**: 793-812

**Current**:

```python
@staticmethod
def calculate_streak(
    current_streak: int,
    previous_last_approved_iso: str | None,
    now_iso: str,
    chore_data: ChoreData | dict[str, Any],
) -> int:
    """Calculate new streak value based on schedule-aware logic.

    Must be called BEFORE updating last_approved timestamp, using the
    previous value to determine if the schedule gap was missed.

    Args:
        current_streak: The streak value from the previous day (or 0)
        previous_last_approved_iso: ISO timestamp of last approval BEFORE this one
        now_iso: Current ISO timestamp (the new approval time)
        chore_data: Chore definition containing frequency/schedule info
```

**New**:

```python
@staticmethod
def calculate_streak(
    current_streak: int,
    previous_last_completed_iso: str | None,
    current_work_date_iso: str,
    chore_data: ChoreData | dict[str, Any],
) -> int:
    """Calculate new streak value based on schedule-aware logic.

    Must be called BEFORE updating last_completed timestamp, using the
    previous value to determine if the schedule gap was missed.

    Args:
        current_streak: The streak value from the previous day (or 0)
        previous_last_completed_iso: ISO timestamp of LAST completion (work date)
        current_work_date_iso: ISO timestamp of THIS completion (effective_date)
        chore_data: Chore definition containing frequency/schedule info
```

**Also update internal references** (line 821, 832, 840, 857, 873):

- `previous_last_approved_iso` → `previous_last_completed_iso`
- `now_iso` → `current_work_date_iso`
- `now_dt` → `current_dt`

---

### Step 2: Update Capture of Previous Value in ChoreManager

**File**: `custom_components/kidschores/managers/chore_manager.py`
**Line**: 2280-2283

**Current**:

```python
        previous_last_approved = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_APPROVED
        )
```

**New** (add after existing, keep `previous_last_approved` for other uses):

```python
        previous_last_approved = kid_chore_data.get(
            const.DATA_KID_CHORE_DATA_LAST_APPROVED
        )

        # Get previous last_completed for streak calculation
        # INDEPENDENT: per-kid, SHARED: chore-level
        completion_criteria = chore_data.get(
            const.DATA_CHORE_COMPLETION_CRITERIA,
            const.COMPLETION_CRITERIA_INDEPENDENT,
        )
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            previous_last_completed = kid_chore_data.get(
                const.DATA_KID_CHORE_DATA_LAST_COMPLETED
            )
        else:
            previous_last_completed = chore_data.get(
                const.DATA_CHORE_LAST_COMPLETED
            )
```

---

### Step 3: Update `calculate_streak()` Call in ChoreManager

**File**: `custom_components/kidschores/managers/chore_manager.py`
**Line**: 2343-2348

**Current**:

```python
        # Calculate streak using schedule-aware logic
        new_streak = ChoreEngine.calculate_streak(
            current_streak=previous_streak,
            previous_last_approved_iso=previous_last_approved,
            now_iso=now_iso,
            chore_data=chore_data,
        )
```

**New**:

```python
        # Calculate streak using schedule-aware logic (parent-lag-proof)
        # Uses last_completed (work date) not last_approved (parent action date)
        new_streak = ChoreEngine.calculate_streak(
            current_streak=previous_streak,
            previous_last_completed_iso=previous_last_completed,
            current_work_date_iso=effective_date_iso,
            chore_data=chore_data,
        )
```

---

### Step 4: Update Test Helper Function

**File**: `tests/test_workflow_streak_schedule.py`
**Line**: 168-181

**Current**:

```python
def set_last_approved(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
    last_approved_dt: datetime,
) -> None:
    """Set last approved timestamp for a chore.

    DATA INJECTION: Setting last_approved for streak testing - approved per Rule 2.1
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.setdefault(chore_id, {})
    per_chore[DATA_KID_CHORE_DATA_LAST_APPROVED] = last_approved_dt.isoformat()
```

**New** (rename function and update field):

```python
def set_last_completed(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
    last_completed_dt: datetime,
) -> None:
    """Set last completed timestamp for a chore (for streak testing).

    DATA INJECTION: Setting last_completed for streak testing - approved per Rule 2.1

    Note: For INDEPENDENT chores, sets per-kid last_completed.
    For SHARED chores, would need to set chore-level (not implemented here
    as streak tests use INDEPENDENT chores via Reset Upon Completion).
    """
    kid_data = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_data.setdefault(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.setdefault(chore_id, {})
    per_chore[DATA_KID_CHORE_DATA_LAST_COMPLETED] = last_completed_dt.isoformat()
```

---

### Step 5: Update Test Imports

**File**: `tests/test_workflow_streak_schedule.py`
**Line**: ~45 (imports section)

**Add to imports from tests.helpers or const**:

```python
from custom_components.kidschores.const import (
    ...
    DATA_KID_CHORE_DATA_LAST_COMPLETED,  # ADD THIS
)
```

---

### Step 6: Update All Test Calls

**File**: `tests/test_workflow_streak_schedule.py`

Find and replace all occurrences:

- `set_last_approved(` → `set_last_completed(`

**Locations** (search for `set_last_approved`):

- Line ~264: `set_last_approved(coordinator, kid_id, chore_id, yesterday_utc)`
- Line ~299: `set_last_approved(coordinator, kid_id, chore_id, two_days_ago_utc)`
- Line ~337: `set_last_approved(coordinator, kid_id, chore_id, one_week_ago_utc)`
- Line ~373: `set_last_approved(coordinator, kid_id, chore_id, two_weeks_ago_utc)`
- Line ~413: `set_last_approved(coordinator, kid_id, chore_id, three_days_ago_utc)`
- Line ~453: `set_last_approved(coordinator, kid_id, chore_id, four_days_ago_utc)`
- Line ~495: `set_last_approved(coordinator, kid_id, chore_id, yesterday_utc)`
- Line ~568: `set_last_approved(coordinator, kid_id, chore_id, now_utc)`

---

## Validation Gates

After implementation, run in order:

```bash
# 1. Lint check
./utils/quick_lint.sh --fix

# 2. Type check
mypy custom_components/kidschores/

# 3. Streak tests specifically
pytest tests/test_workflow_streak_schedule.py -v

# 4. Full test suite
pytest tests/ -v --tb=line
```

**Success Criteria**:

- ✅ Lint: All checks pass
- ✅ MyPy: 0 errors
- ✅ Streak tests: 11/11 pass
- ✅ Full suite: 1148+ tests pass

---

## Fallback Behavior

**Q: What if `last_completed` is None (first-time or legacy data)?**

A: The fallback is already handled:

1. `ChoreEngine.calculate_streak()` returns `1` if `previous_last_completed_iso` is `None` (line 820)
2. First approval ever correctly starts streak at 1
3. Legacy data without `last_completed` will get streak=1, then populate going forward

---

## Files Changed Summary

| File                                     | Lines Changed | Type                     |
| ---------------------------------------- | ------------- | ------------------------ |
| `engines/chore_engine.py`                | ~15           | Parameter rename         |
| `managers/chore_manager.py`              | ~15           | Read logic + call update |
| `tests/test_workflow_streak_schedule.py` | ~15           | Helper + calls           |

**Total**: ~45 lines across 3 files

---

## Rollback Plan

If tests fail unexpectedly:

1. `git checkout -- custom_components/kidschores/engines/chore_engine.py`
2. `git checkout -- custom_components/kidschores/managers/chore_manager.py`
3. `git checkout -- tests/test_workflow_streak_schedule.py`

---

## Post-Implementation

- [ ] Update plan document with completion status
- [ ] Commit with message: `fix(streak): use last_completed for parent-lag-proof streaks`
