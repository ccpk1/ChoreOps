# Phase 6B Prerequisite: Per-Kid `last_completed` Field Fix

## Problem Statement

During Phase 6B implementation, a foundational bug was discovered:

**Missing Constant**: `DATA_KID_CHORE_DATA_LAST_COMPLETED` was never defined in `const.py`

**Result**: The code incorrectly uses `DATA_CHORE_LAST_COMPLETED` (chore-level) for all chores, including INDEPENDENT chores where each kid should have their own `last_completed` timestamp.

## Architectural Requirement

| Chore Type          | `last_completed` Storage Location                             | Reason                                                |
| ------------------- | ------------------------------------------------------------- | ----------------------------------------------------- |
| INDEPENDENT         | Per-kid: `kid_chore_data[DATA_KID_CHORE_DATA_LAST_COMPLETED]` | Each kid completes independently; needs own timestamp |
| SHARED (SHARED_ALL) | Chore-level: `chore_data[DATA_CHORE_LAST_COMPLETED]`          | One completion for all; max of all kids' claims       |
| SHARED_FIRST        | Chore-level: `chore_data[DATA_CHORE_LAST_COMPLETED]`          | First kid wins; single timestamp                      |

## Timestamp Field Semantics

| Field            | Location           | Purpose                             | Used For                            |
| ---------------- | ------------------ | ----------------------------------- | ----------------------------------- |
| `last_claimed`   | Per-kid            | When kid clicked claim button       | Audit trail, claim timestamp        |
| `last_approved`  | Per-kid            | When parent approved                | Financial timestamp, points deposit |
| `last_completed` | VARIES (see above) | When work was done (effective_date) | **Streak calculation**, scheduling  |

**Critical**: Streaks are based on `last_completed`, NOT `last_approved` (fixes parent-lag-proof gap).

## Fix Implementation

### Step 1: Add Constant ✅ DONE

**File**: `const.py` line ~800

```python
DATA_KID_CHORE_DATA_LAST_COMPLETED: Final = "last_completed"
```

**Comment added**: Explains per-kid vs chore-level usage, streak calculation purpose.

### Step 2: Update `_set_last_completed_timestamp()` ✅ DONE

**File**: `chore_manager.py` line ~3057

**Before** (bug):

```python
if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
    # Use this kid's effective_date
    chore_data[const.DATA_CHORE_LAST_COMPLETED] = effective_date_iso
```

**After** (fix):

```python
if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
    # INDEPENDENT: Store in per-kid data (each kid has their own completion)
    kid_chore_data_item = self._get_kid_chore_data(kid_id, chore_id)
    kid_chore_data_item[const.DATA_KID_CHORE_DATA_LAST_COMPLETED] = (
        effective_date_iso
    )
```

### Step 3: Update Streak Calculation Read Path ⏳ TODO

**File**: `chore_manager.py` approval flow (line ~2280)

**Current** (uses `last_approved` for streak):

```python
previous_last_approved = kid_chore_data.get(
    const.DATA_KID_CHORE_DATA_LAST_APPROVED
)
```

**Required** (use `last_completed` for streak):

```python
# Get previous last_completed for streak calculation
# For INDEPENDENT: read from per-kid data
# For SHARED: read from chore-level data
completion_criteria = chore_data.get(
    const.DATA_CHORE_COMPLETION_CRITERIA,
    const.COMPLETION_CRITERIA_INDEPENDENT
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

### Step 4: Update ChoreEngine.calculate_streak() Parameters ⏳ TODO

**File**: `chore_engine.py` line ~793

**Current parameters**:

```python
def calculate_streak(
    current_streak: int,
    previous_last_approved_iso: str | None,
    now_iso: str,
    chore_data: ChoreData | dict[str, Any],
) -> int:
```

**New parameters** (clarified naming):

```python
def calculate_streak(
    current_streak: int,
    previous_last_completed_iso: str | None,
    current_work_date_iso: str,  # effective_date (when work was done)
    chore_data: ChoreData | dict[str, Any],
) -> int:
```

### Step 5: Update ChoreManager Call to calculate_streak() ⏳ TODO

**File**: `chore_manager.py` line ~2343

**Current call**:

```python
new_streak = ChoreEngine.calculate_streak(
    current_streak=previous_streak,
    previous_last_approved_iso=previous_last_approved,
    now_iso=now_iso,
    chore_data=chore_data,
)
```

**New call**:

```python
new_streak = ChoreEngine.calculate_streak(
    current_streak=previous_streak,
    previous_last_completed_iso=previous_last_completed,
    current_work_date_iso=effective_date_iso,
    chore_data=chore_data,
)
```

## Validation

After implementation:

1. `./utils/quick_lint.sh --fix` → Pass
2. `mypy custom_components/kidschores/` → 0 errors
3. `pytest tests/ -v` → All pass (especially `test_workflow_streak_*`)

## Impact on Phase 6B

This fix is a **prerequisite** for Phase 6B steps 1-2. The Phase 6B plan can proceed after this fix is validated.

---

**Status**: Partially implemented (Steps 1-2 done, Steps 3-5 remaining)
