# Approval Period Logic Fix

## Initiative snapshot

- **Name / Code**: APPROVAL_PERIOD_FIX
- **Target release / milestone**: v0.5.0-beta3 (critical bug fix)
- **Owner / driver(s)**: Development Team
- **Status**: ✅ COMPLETE
- **Completion Date**: January 29, 2026

### Completion Summary

**All phases complete** with 1146/1146 tests passing:
- ✅ Phase 1: Logic documented and confirmed
- ✅ Phase 2: All 6 write locations audited
- ✅ Phase 3: 3 fixes implemented + critical timestamp fix
- ✅ Phase 4: Full validation (lint, mypy, tests all pass)

**Key Achievement**: Fixed approval period bug that caused chores to remain "approved" after reset. Root cause was reusing timestamp variables, making `last_approved == approval_period_start` always True. Solution: use fresh `dt_now_iso()` for reset timestamp.

## Summary & immediate steps

| Phase / Step             | Description                               | % complete | Quick notes                           |
| ------------------------ | ----------------------------------------- | ---------- | ------------------------------------- |
| Phase 1 – Analysis       | Document correct approval period behavior | 100%       | Logic confirmed                       |
| Phase 2 – Gap Analysis   | Identify all code locations needing fixes | 100%       | 6 write locations audited             |
| Phase 3 – Implementation | Fix all gaps (3 fixes)                    | 100%       | All fixes + timestamp fix implemented |
| Phase 4 – Validation     | Ensure all tests pass                     | 100%       | 1146 tests passing, lint/mypy clean   |

### Quick Reference: What Needs Fixing

| Priority | Location                        | Line  | Issue                            | Fix                       |
| -------- | ------------------------------- | ----- | -------------------------------- | ------------------------- |
| **1**    | `_reset_kid_chore_to_pending()` | 3187  | Sets to `None`                   | Change to `dt_now_iso()`  |
| **2**    | `approve_chore_for_kid()`       | 2412  | Calls `_reset_approval_period()` | Remove the call           |
| **3**    | `_get_kid_chore_data()`         | ~2615 | Missing field                    | Add to default dict       |
| **4**    | `build_chore()`                 | ~1332 | Sets to `None`                   | Change to `utcnow()`      |
| **5**    | `set_due_date()`                | ~996  | Missing reset                    | Add approval period reset |

---

## Core Logic (Confirmed)

### What is `approval_period_start`?

It marks the boundary timestamp after which a `last_approved` is considered valid.

**Formula**: `is_approved = (last_approved is not None) AND (last_approved >= approval_period_start)`

### Storage Locations

| Chore Type      | `approval_period_start` Storage                               | `last_approved` Storage                    |
| --------------- | ------------------------------------------------------------- | ------------------------------------------ |
| **SHARED**      | Chore-level: `chores_data[chore_id]["approval_period_start"]` | Per-kid: `kid_chore_data["last_approved"]` |
| **INDEPENDENT** | Per-kid: `kid_chore_data["approval_period_start"]`            | Per-kid: `kid_chore_data["last_approved"]` |

### When to Set `approval_period_start`

**Rule**: `approval_period_start` is ONLY set on **RESET events** and **initial creation**, NEVER on approval.

| Event                                   | Set `approval_period_start`? | Value                        |
| --------------------------------------- | ---------------------------- | ---------------------------- |
| **Kid approval**                        | NO                           | Only `last_approved` changes |
| **Scheduled reset**                     | YES                          | Reset timestamp              |
| **Chore creation**                      | YES                          | Current time                 |
| **Kid assigned to chore (INDEPENDENT)** | YES                          | Current time                 |
| **Manual due date change**              | YES                          | Current time (resets chore)  |
| **Skip due date**                       | YES                          | Via `reset_chore()`          |
| **Overdue - CLEAR_IMMEDIATE_ON_LATE**   | YES                          | Current time (new period)    |

---

## Flow Diagrams

### INDEPENDENT Chores: `kid_chore_data["approval_period_start"]` (per-kid)

```
                    ┌─────────────────┐
                    │  Chore Created  │
                    │  / Kid Assigned │
                    └────────┬────────┘
                             │
                             ▼
              SET kid_chore_data["approval_period_start"] = now
                             │
                             ▼
                    ┌─────────────────┐
                    │    PENDING      │◄─────────────────────────────┐
                    └────────┬────────┘                              │
                             │                                       │
                             ▼                                       │
                    ┌─────────────────┐                              │
                    │  Kid Claims &   │                              │
                    │  Gets Approved  │                              │
                    └────────┬────────┘                              │
                             │                                       │
                             │ (NO change to approval_period_start)  │
                             │ (only last_approved updated)          │
                             ▼                                       │
                    ┌─────────────────┐                              │
                    │    APPROVED     │                              │
                    └────────┬────────┘                              │
                             │                                       │
                             ▼                                       │
                    ┌─────────────────┐                              │
                    │  Scheduled/     │                              │
                    │  Manual Reset   │                              │
                    └────────┬────────┘                              │
                             │                                       │
                             ▼                                       │
              SET kid_chore_data["approval_period_start"] = now      │
                             │                                       │
                             └───────────────────────────────────────┘
```

### SHARED Chores: `chore_info["approval_period_start"]` (chore-level)

```
                    ┌─────────────────┐
                    │  Chore Created  │
                    └────────┬────────┘
                             │
                             ▼
              SET chore_info["approval_period_start"] = now
                             │
                             ▼
                    ┌─────────────────┐
                    │    PENDING      │◄─────────────────────────────┐
                    │   (all kids)    │                              │
                    └────────┬────────┘                              │
                             │                                       │
              ┌──────────────┴──────────────┐                        │
              ▼                             ▼                        │
        ┌──────────┐                  ┌──────────┐                   │
        │  Kid 1   │                  │  Kid 2   │                   │
        │ Approves │                  │ Approves │                   │
        └────┬─────┘                  └────┬─────┘                   │
             │                             │                         │
             ▼                             ▼                         │
     SET kid1's last_approved      SET kid2's last_approved          │
     (NO change to chore-level     (NO change to chore-level         │
      approval_period_start)        approval_period_start)           │
             │                             │                         │
             └──────────────┬──────────────┘                         │
                            ▼                                        │
                   ┌─────────────────┐                               │
                   │  Scheduled/     │                               │
                   │  Manual Reset   │                               │
                   └────────┬────────┘                               │
                            │                                        │
                            ▼                                        │
              SET chore_info["approval_period_start"] = now          │
                            │                                        │
                            └────────────────────────────────────────┘
```

---

## Modifiers & Decision Table

| Modifier                                | Impact                               | Decision                                                                    |
| --------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------- |
| **UPON_COMPLETION**                     | May not need `approval_period_start` | **Set uniformly** - simpler code, no special cases                          |
| **Auto-approve**                        | Claim + approve together             | **No special handling** - follows completion criteria                       |
| **Pending claim at reset**              | May skip reset                       | **No special handling** - approval uses existing `approval_period_start`    |
| **SHARED_FIRST**                        | Only first kid matters               | **Same as SHARED** - chore-level `approval_period_start`                    |
| **Multi-claim**                         | Multiple approvals per period        | **No special handling** - `last_approved` is latest timestamp               |
| **No due date**                         | Reset timing changes                 | **No special handling** - AT_MIDNIGHT works normally                        |
| **Overdue - AT_DUE_DATE**               | Basic overdue                        | **Normal reset behavior** - set at scheduled reset                          |
| **Overdue - NEVER_OVERDUE**             | Never overdue                        | **Normal reset behavior** - set at scheduled reset                          |
| **Overdue - CLEAR_AT_APPROVAL_RESET**   | Clears at reset                      | **Normal reset behavior** - set at scheduled reset                          |
| **Overdue - CLEAR_IMMEDIATE_ON_LATE**   | Clears on late approval              | **Set new `approval_period_start` = now** when late approval clears overdue |
| **Service: reset_all_chores**           | Manual reset all                     | **Set `approval_period_start` = now** for all (already does this)           |
| **Service: reset_overdue_chores**       | Reset overdue chores                 | **Set `approval_period_start`** via `reset_chore()`                         |
| **Service: skip_chore_due_date**        | Skip to next period                  | **Set `approval_period_start`** via `reset_chore()`                         |
| **Service: set_chore_due_date**         | Change due date                      | **Set `approval_period_start` = now** ⚠️ GAP                                |
| **Chore creation (SHARED)**             | New chore                            | **Set `approval_period_start` = now** ⚠️ GAP                                |
| **Chore creation (INDEPENDENT)**        | New chore                            | **Set per-kid `approval_period_start` = now** ⚠️ GAP                        |
| **Kid assigned to chore (INDEPENDENT)** | New assignment                       | **Set per-kid `approval_period_start` = now** ⚠️ GAP                        |
| **Disapprove chore**                    | Returns to claimed                   | **No change** - same approval period continues                              |
| **Update chore settings**               | Config change                        | **No change** - only criteria changes might need review                     |

---

## Comprehensive Audit: All `approval_period_start` Writes

This audit identifies EVERY location that writes to `approval_period_start` to ensure:

1. No improper writes get through
2. Old bad assumptions are clearly identified
3. The correct reset-only logic is enforced

### Write Location Summary Table

| Line     | Function                        | Storage Type        | Current Value | Verdict        | Notes                                                                  |
| -------- | ------------------------------- | ------------------- | ------------- | -------------- | ---------------------------------------------------------------------- |
| **1224** | `reset_all_chores()`            | SHARED chore-level  | `now_utc_iso` | ✅ CORRECT     | Manual reset service                                                   |
| **3088** | `_reset_approval_period()`      | INDEPENDENT per-kid | `now_iso`     | ⚠️ CONDITIONAL | Called by `reset_chore()` ✅, but also by `approve_chore_for_kid()` ❌ |
| **3096** | `_reset_approval_period()`      | SHARED chore-level  | `now_iso`     | ⚠️ CONDITIONAL | Same as above                                                          |
| **3187** | `_reset_kid_chore_to_pending()` | INDEPENDENT per-kid | `None`        | ❌ WRONG       | Sets to `None` instead of `now` - breaks approval check                |
| **3236** | `_transition_chore_state()`     | INDEPENDENT per-kid | `now_iso`     | ✅ CORRECT     | Scheduler-driven reset                                                 |
| **3240** | `_transition_chore_state()`     | SHARED chore-level  | `now_iso`     | ✅ CORRECT     | Scheduler-driven reset                                                 |

### Write Location Details

#### Location 1: `reset_all_chores()` (Line 1224)

```python
chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_utc_iso
```

- **Verdict**: ✅ CORRECT - Manual reset service properly sets new period
- **Type**: SHARED chore-level
- **Called by**: Service `reset_all_chores`

#### Location 2 & 3: `_reset_approval_period()` (Lines 3088, 3096)

```python
kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now_iso  # L3088
chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso              # L3096
```

- **Verdict**: ⚠️ METHOD IS FINE, CALLER IS WRONG
- **Problem**: Called by `approve_chore_for_kid()` (line 2412) which is INCORRECT
- **Correct callers**: `reset_chore()` (line 440)
- **Fix**: Remove call from `approve_chore_for_kid()`, not the method itself

#### Location 4: `_reset_kid_chore_to_pending()` (Line 3187)

```python
kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = None
```

- **Verdict**: ❌ WRONG - Sets to `None` which breaks approval check
- **Type**: INDEPENDENT per-kid
- **Called by**: `approve_chore_for_kid()` for UPON_COMPLETION reset
- **Fix**: Change to `dt_now_iso()` to set a new valid period start

#### Locations 5 & 6: `_transition_chore_state()` (Lines 3236, 3240)

```python
kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now_iso  # L3236
chore_info[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso               # L3240
```

- **Verdict**: ✅ CORRECT - Scheduler-driven reset with proper timestamp
- **Guarded by**: `if reset_approval_period:` parameter
- **Called by**: Timer/scheduler operations

### Callers of `_reset_approval_period()` - The REAL Problem

| Call Site                 | Line | Context              | Verdict    |
| ------------------------- | ---- | -------------------- | ---------- |
| `reset_chore()`           | 440  | Manual/service reset | ✅ CORRECT |
| `approve_chore_for_kid()` | 2412 | During approval      | ❌ WRONG   |

**The core bug**: `approve_chore_for_kid()` calls `_reset_approval_period()` after setting `last_approved`,
which violates the rule that approval_period_start is ONLY set on RESET, never on approval.

---

## Missing Write Locations (Gaps)

### Gap 1: `set_chore_due_date` service

- **Location**: `chore_manager.py` `set_due_date()` (line ~996)
- **Issue**: Doesn't reset approval period when due date is manually changed
- **Fix**: Call `reset_chore(reset_approval_period=True)` for affected kids

### Gap 2: SHARED chore creation

- **Location**: `data_builders.py` `build_chore()` (line ~1332)
- **Issue**: Sets `approval_period_start` to `None` instead of `now`
- **Fix**: Set `approval_period_start` to `dt_util.utcnow().isoformat()` on creation

### Gap 3: INDEPENDENT chore creation / kid assignment

- **Location**: `chore_manager.py` `_get_kid_chore_data()` (line ~2615)
- **Issue**: Doesn't set per-kid `approval_period_start` when creating kid_chore_data
- **Fix**: Add `DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START: dt_now_iso()` to default dict

---

## Safeguards Against Bad Assumptions

### The Old (WRONG) Mental Model

```
OLD ASSUMPTION: approval_period_start marks when THIS approval happened
               → Set it when approving to track "when did we approve"
               → This creates: approval_period_start == last_approved (always)

WHY IT'S WRONG: This defeats the purpose. If both are always equal,
                then (last_approved >= approval_period_start) is ALWAYS true,
                so chores are ALWAYS considered approved until explicit state change.
```

### The New (CORRECT) Mental Model

```
CORRECT UNDERSTANDING: approval_period_start marks the PERIOD BOUNDARY
                       → Set it when RESETTING to mark "new period starts now"
                       → Approvals only update last_approved
                       → Check: last_approved >= approval_period_start

EXAMPLE TIMELINE:
  T1: Reset happens      → approval_period_start = T1
  T2: Kid 1 approves     → last_approved = T2 (no change to approval_period_start)
  T3: Kid 2 approves     → last_approved = T3 (no change to approval_period_start)
  T4: Scheduled reset    → approval_period_start = T4 (invalidates all T2, T3 approvals)

  At T3: is_approved = (T3 >= T1) = TRUE ✓
  At T4: is_approved = (T3 >= T4) = FALSE ✓ (T3 < T4)
```

### Code Review Checklist (For Future Changes)

When reviewing code that touches `approval_period_start`:

- [ ] **Question 1**: Is this a RESET event or initial creation?
  - YES → Setting `approval_period_start` is allowed
  - NO → Do NOT touch `approval_period_start`

- [ ] **Question 2**: Is this an approval/claim event?
  - YES → Only `last_approved` should change, NOT `approval_period_start`
  - NO → Continue review

- [ ] **Question 3**: Is the storage location correct?
  - SHARED chore → chore-level: `chore_info[DATA_CHORE_APPROVAL_PERIOD_START]`
  - INDEPENDENT chore → per-kid: `kid_chore_data[DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START]`

### Grep Commands to Verify No Bad Writes

After implementation, run these to verify no improper writes remain:

```bash
# Find ALL places that set approval_period_start
grep -n "approval_period_start.*=" custom_components/kidschores/managers/chore_manager.py

# Verify no writes in approval methods (should find ZERO matches)
grep -n -A5 "def.*approve" custom_components/kidschores/managers/chore_manager.py | \
  grep "approval_period_start"
```

---

## Implementation Plan (Detailed)

### Pre-Implementation Checklist (Safeguards)

These checks ensure old bad assumptions don't carry forward:

- [ ] **Understand the rule**: `approval_period_start` is ONLY set on RESET events and initial creation, NEVER on approval
- [ ] **Verify storage locations**: SHARED = chore-level, INDEPENDENT = per-kid
- [ ] **Test formula**: `is_approved = (last_approved is not None) AND (last_approved >= approval_period_start)`
- [ ] **Confirm no approval writes**: After fix, `approve_chore_for_kid()` must NOT touch `approval_period_start`

### Phase 3 – Implementation Steps

#### Step 1: Fix `_reset_kid_chore_to_pending()` (Line 3187)

**Problem**: Sets `approval_period_start = None` which breaks approval checks
**Fix**: Set to `dt_now_iso()` instead

```python
# BEFORE (WRONG):
kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = None

# AFTER (CORRECT):
kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = dt_now_iso()
```

**File**: `chore_manager.py` line 3187
**Test after**: `pytest tests/test_shared_chore_approval.py -v -k "upon_completion"`

---

#### Step 2: Remove `_reset_approval_period()` call from `approve_chore_for_kid()` (Line 2412)

**Problem**: Approval should NOT set `approval_period_start`, only `last_approved`
**Fix**: Delete the call entirely

```python
# BEFORE (WRONG):
        else:
            # For non-UPON_COMPLETION reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*):
            # Set approval_period_start to mark when this approval period began.
            # When reset happens, it will update approval_period_start to the reset time,
            # making this approval invalid (last_approved < approval_period_start).
            # Pass same timestamp to ensure approval_period_start matches last_approved.
            self._reset_approval_period(kid_id, chore_id, now_iso)

# AFTER (CORRECT):
        # For non-UPON_COMPLETION reset types (AT_MIDNIGHT_*, AT_DUE_DATE_*):
        # Do NOT set approval_period_start here. It is ONLY set on RESET events.
        # The chore remains approved until the scheduled reset updates approval_period_start.
        # approval_period_start was set at: initial creation, or last reset.
        # last_approved was just set above, so:
        #   is_approved = (last_approved >= approval_period_start) = True
```

**File**: `chore_manager.py` line ~2408-2412
**Test after**: `pytest tests/test_approval_reset_overdue_interaction.py -v`

---

#### Step 3: Set `approval_period_start` in `_get_kid_chore_data()` (Line ~2615)

**Problem**: INDEPENDENT chores don't get `approval_period_start` on kid assignment
**Fix**: Add to default dict

```python
# BEFORE:
return {
    const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
    const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
}

# AFTER:
return {
    const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
    const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT: 0,
    const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START: dt_now_iso(),
}
```

**File**: `chore_manager.py` line ~2615+
**Test after**: `pytest tests/ -v -k "independent"`

---

#### Step 4: Set `approval_period_start` in `build_chore()` (Line ~1332)

**Problem**: SHARED chores get `approval_period_start = None` instead of a valid timestamp
**Fix**: Set to current UTC time

```python
# BEFORE:
const.DATA_CHORE_APPROVAL_PERIOD_START: None,

# AFTER:
const.DATA_CHORE_APPROVAL_PERIOD_START: dt_util.utcnow().isoformat(),
```

**File**: `data_builders.py` line ~1332
**Test after**: `pytest tests/test_shared_chore_approval.py -v`

---

#### Step 5: Add approval period reset to `set_due_date()` service

**Problem**: Manually changing due date doesn't reset approval period
**Fix**: Call reset for affected kids after changing due date

**File**: `chore_manager.py` `set_due_date()` method
**Change**: After due date update, reset approval period based on completion criteria

```python
# After setting the new due date:
completion_criteria = chore_data.get(
    const.DATA_CHORE_COMPLETION_CRITERIA, const.COMPLETION_CRITERIA_INDEPENDENT
)
now_iso = dt_now_iso()

if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
    # Reset approval period for each assigned kid
    for kid_id in chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
        if kid_id:
            kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
            kid_chore_data[const.DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START] = now_iso
else:
    # Reset chore-level approval period for SHARED
    chore_data[const.DATA_CHORE_APPROVAL_PERIOD_START] = now_iso
```

**Test after**: `pytest tests/ -v -k "set_due_date"`

---

#### Step 6 (Optional): Simplify `_reset_approval_period()` method

After the above fixes, this method is only called from `reset_chore()`.

- Remove the `force_update` parameter (no longer needed)
- Remove the conditional logic for "only set if not already set"
- Simplify to always set the timestamp

**Recommendation**: Do this as a follow-up cleanup after tests pass.

---

### Phase 4 – Validation Steps

1. `[x]` Run targeted tests for each step (as noted above)
2. `[x]` Run previously failing test: `pytest tests/test_shared_chore_approval.py::test_shared_first_chore_resets_after_approval -v`
3. `[x]` Run full approval-related tests: `pytest tests/test_*approval*.py tests/test_*reset*.py -v` (18/18 passed)
4. `[x]` Run quality gates: `./utils/quick_lint.sh --fix && mypy custom_components/kidschores/` (all passed)
5. `[x]` Run full test suite: `python -m pytest tests/ -v` (1146 passed, 2 skipped)

---

### Implementation Order (Critical)

Execute in this EXACT order to avoid cascading failures:

1. **Step 1** first (fix `_reset_kid_chore_to_pending`) - fixes UPON_COMPLETION path
2. **Step 2** second (remove approval call) - stops wrong writes during approval
3. **Step 3 & 4** together (creation defaults) - ensures new chores start correctly
4. **Step 5** last (set_due_date service) - adds missing reset path
5. **Step 6** optional cleanup after all tests pass

---

## Test Commands

```bash
# Phase 1 tests (approval reset interaction)
pytest tests/test_approval_reset_overdue_interaction.py -v

# Phase 3 tests (scheduling)
pytest tests/test_chore_scheduling.py -v

# SHARED chore tests
pytest tests/test_shared_chore_approval.py -v

# Full test suite
python -m pytest tests/ -v
```

---

## References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model documentation
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Coding patterns

---

## Decisions & completion check

- **Decisions captured**:
  - `approval_period_start` is ONLY set on reset/creation, NEVER on approval
  - Use `chore_is_approved_in_period()` as canonical source of truth
  - SHARED uses chore-level timestamp, INDEPENDENT uses per-kid timestamp
  - **Critical discovery**: Use fresh `dt_now_iso()` for reset timestamp (not reused variable)
- **Completion confirmation**: `[x]` All gaps fixed and tests pass (1146/1146 tests passing)
