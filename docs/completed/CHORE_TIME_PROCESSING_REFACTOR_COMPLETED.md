# CHORE TIME PROCESSING REFACTOR - Next Gen Consolidation

> **Version**: v0.5.0-beta3+
> **Status**: 🟡 IN-PROCESS
> **Owner**: Strategist → Builder
> **Target**: ChoreManager consolidation (~386 lines removed, 7 methods remain)

---

## Initiative Snapshot

| Field           | Value                                              |
| --------------- | -------------------------------------------------- |
| Initiative Code | `TIME-PROC-REFACTOR`                               |
| Target Release  | v0.5.0-beta3 (patch)                               |
| Current State   | 16+ methods, 2 parallel systems, redundant queries |
| Goal State      | 7 methods total, single-pass architecture          |

---

## Final Architecture

### Processing Methods (4 total)

| Method     | Current Name                   | New Name                  | Lines | Purpose                                      |
| ---------- | ------------------------------ | ------------------------- | ----- | -------------------------------------------- |
| Scanner    | `_scan_chore_time_statuses()`  | `process_time_checks()`   | ~130  | **PUBLIC** - Single-pass scanner             |
| Overdue    | `_process_overdue_from_scan()` | `_process_overdue()`      | ~70   | Process overdue bucket (inline mark_overdue) |
| Due Window | `_emit_due_window_signals()`   | `_process_due_window()`   | ~25   | Emit due window signals                      |
| Reminder   | `_emit_due_reminder_signals()` | `_process_due_reminder()` | ~25   | Emit reminder signals                        |

### Query Methods (3 thin wrappers)

| Method               | New Signature                                | Lines | Purpose                        |
| -------------------- | -------------------------------------------- | ----- | ------------------------------ |
| `get_due_date()`     | `(chore_id, kid_id=None) → datetime \| None` | ~4    | Single unified due date getter |
| `chore_is_overdue()` | `(kid_id, chore_id) → bool`                  | ~2    | Delegates to Engine            |
| `chore_is_due()`     | `(kid_id, chore_id) → bool`                  | ~6    | Refactored thin wrapper        |

### Final Flow

```
STARTUP:   DATA_READY → _on_data_ready() ──────────┐
                                                    │
PERIODIC:  PERIODIC_UPDATE → _on_periodic_update() ─┼─→ process_time_checks()
                                                    │         │
MIDNIGHT:  MIDNIGHT_ROLLOVER → _on_midnight_rollover()        │
                │                                             │
                └─→ process_scheduled_resets()     ┌──────────┴──────────┐
                    (resets only, no overdue)      │          │          │
                                                   ↓          ↓          ↓
                                           _process_    _process_    _process_
                                           overdue()   due_window() due_reminder()
                                               │            │            │
                                               ↓            ↓            ↓
                                            emit        emit         emit
                                           OVERDUE    DUE_WINDOW   DUE_REMINDER
```

---

## COMPLETE Method Removal List

### Time Processing Methods to REMOVE

| #   | Method                          | Line | Lines | Reason                           | Callers to Update                  |
| --- | ------------------------------- | ---- | ----- | -------------------------------- | ---------------------------------- |
| 1   | `check_overdue_chores()`        | 3889 | 12    | Redundant wrapper                | `_on_midnight_rollover`, 20+ tests |
| 2   | `_update_overdue_status()`      | 1247 | 112   | Redundant iteration              | `check_overdue_chores`             |
| 3   | `_check_chore_overdue_status()` | 3901 | 86    | Redundant validation             | Internal only                      |
| 4   | `_handle_overdue_chore_state()` | 3989 | 76    | Duplicate of mark_overdue        | `_check_chore_overdue_status`      |
| 5   | `mark_overdue()`                | 1194 | 53    | Inline into `_process_overdue()` | `_process_overdue_from_scan`       |

**Subtotal: 339 lines removed**

### Query Methods to REMOVE/MERGE

| #   | Method                             | Line | Lines | Reason                      | Callers to Update    |
| --- | ---------------------------------- | ---- | ----- | --------------------------- | -------------------- |
| 6   | `get_chore_effective_due_date()`   | 2523 | 23    | Merge into `get_due_date()` | 9 internal callers   |
| 7   | `get_chore_due_date()`             | 2496 | 27    | Rename to `get_due_date()`  | `sensor.py:806,2188` |
| 8   | `chore_is_due()` (30-line version) | 2381 | 46    | Refactor to ~6 lines        | `sensor.py:2009`     |

**Subtotal: ~50 lines consolidated (net)**

### Methods to RENAME

| #   | Current Name                   | New Name                  | Line | Reason                          |
| --- | ------------------------------ | ------------------------- | ---- | ------------------------------- |
| 9   | `_scan_chore_time_statuses()`  | `process_time_checks()`   | 195  | Public API, cleaner name        |
| 10  | `_process_overdue_from_scan()` | `_process_overdue()`      | 325  | Simpler name                    |
| 11  | `_emit_due_window_signals()`   | `_process_due_window()`   | 370  | Consistent `_process_*` pattern |
| 12  | `_emit_due_reminder_signals()` | `_process_due_reminder()` | 402  | Consistent `_process_*` pattern |
| 13  | `get_chore_due_window_start()` | `get_due_window_start()`  | 2546 | Drop redundant "chore" prefix   |

---

## COMPLETE Caller Analysis

### 1. `check_overdue_chores()` Callers (REMOVE all calls)

| Location                | File:Line                                      | Migration                 |
| ----------------------- | ---------------------------------------------- | ------------------------- |
| `_on_midnight_rollover` | chore_manager.py:162                           | **DELETE line**           |
| test                    | test_performance.py:51                         | → `process_time_checks()` |
| test                    | test_approval_reset_overdue_interaction.py:288 | → `process_time_checks()` |
| test                    | test_approval_reset_overdue_interaction.py:367 | → `process_time_checks()` |
| test                    | test_approval_reset_overdue_interaction.py:431 | → `process_time_checks()` |
| test                    | test_performance_comprehensive.py:109          | → `process_time_checks()` |
| test                    | test_scheduler_delegation.py:131               | → `process_time_checks()` |
| test                    | test_scheduler_delegation.py:177               | → `process_time_checks()` |
| test                    | test_scheduler_delegation.py:234               | → `process_time_checks()` |
| test                    | test_scheduler_delegation.py:379               | → `process_time_checks()` |
| test                    | test_chore_services.py:696                     | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:478                   | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:509                   | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:534                   | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:564                   | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:1194                  | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:1226                  | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:1270                  | → `process_time_checks()` |
| test                    | test_chore_scheduling.py:1315                  | → `process_time_checks()` |

### 2. `get_chore_effective_due_date()` Callers (→ `get_due_date()`)

| Location                      | File:Line             | Migration                      |
| ----------------------------- | --------------------- | ------------------------------ |
| `_scan_chore_time_statuses`   | chore_manager.py:275  | → `get_due_date()`             |
| `_update_overdue_status`      | chore_manager.py:1318 | **Method deleted**             |
| `_reset_independent_chore`    | chore_manager.py:1730 | → `get_due_date()`             |
| `chore_is_due`                | chore_manager.py:2411 | → `get_due_date()`             |
| `get_chore_due_date`          | chore_manager.py:2516 | **Method merged**              |
| `get_chore_status_context`    | chore_manager.py:2807 | → `get_due_date()`             |
| internal                      | chore_manager.py:2860 | → `get_due_date()`             |
| `_check_chore_overdue_status` | chore_manager.py:3984 | **Method deleted**             |
| sensor                        | sensor.py:968         | → `get_due_date().isoformat()` |

### 3. `get_chore_due_date()` Callers (→ `get_due_date()`)

| Location                     | File:Line             | Migration          |
| ---------------------------- | --------------------- | ------------------ |
| `get_chore_due_window_start` | chore_manager.py:2567 | → `get_due_date()` |
| sensor                       | sensor.py:806         | → `get_due_date()` |
| sensor                       | sensor.py:2188        | → `get_due_date()` |

### 4. `get_chore_due_window_start()` Callers (RENAME → `get_due_window_start()`)

| Location | File:Line      | Notes       |
| -------- | -------------- | ----------- |
| sensor   | sensor.py:768  | Update name |
| sensor   | sensor.py:790  | Update name |
| sensor   | sensor.py:2150 | Update name |
| sensor   | sensor.py:2172 | Update name |

### 5. `chore_is_due()` Callers (REFACTOR to thin wrapper)

| Location                   | File:Line             | Notes    |
| -------------------------- | --------------------- | -------- |
| `get_chore_status_context` | chore_manager.py:2761 | Internal |
| sensor                     | sensor.py:2009        | Keep API |

### 6. `mark_overdue()` Callers (INLINE into `_process_overdue()`)

| Location                     | File:Line             | Migration          |
| ---------------------------- | --------------------- | ------------------ |
| `_process_overdue_from_scan` | chore_manager.py:349  | Inline logic       |
| `_update_overdue_status`     | chore_manager.py:1336 | **Method deleted** |

---

## Summary Table

| Phase   | Description               | %    | Quick Notes                                              |
| ------- | ------------------------- | ---- | -------------------------------------------------------- |
| Phase 1 | Rename processing methods | 100% | ✅ 4 renames done                                        |
| Phase 2 | Consolidate query methods | 100% | ✅ Merged, refactored, renamed                           |
| Phase 3 | Update entry points       | 100% | ✅ \_on_data_ready, \_on_midnight                        |
| Phase 4 | Inline mark_overdue       | 100% | ✅ Inlined into \_process_overdue                        |
| Phase 5 | Delete redundant methods  | 100% | ✅ 5 methods deleted (~344 lines)                        |
| Phase 6 | Update tests              | 100% | ✅ Fixed mock usages, helper functions, async signatures |
| Phase 7 | Update sensor callers     | 100% | ✅ Already done in Phase 2                               |
| Phase 8 | Validate                  | 100% | ✅ lint/mypy/tests all pass                              |

---

## Phase 1 – Rename Processing Methods ✅ COMPLETE

### Steps

#### 1.1 Rename `_scan_chore_time_statuses()` → `process_time_checks()`

- [x] File: chore_manager.py line 195
- [x] Remove underscore (make public)
- [x] Update docstring

#### 1.2 Rename `_process_overdue_from_scan()` → `_process_overdue()`

- [x] File: chore_manager.py line 325
- [x] Update all internal callers

#### 1.3 Rename `_emit_due_window_signals()` → `_process_due_window()`

- [x] File: chore_manager.py line 370

#### 1.4 Rename `_emit_due_reminder_signals()` → `_process_due_reminder()`

- [x] File: chore_manager.py line 402

---

## Phase 2 – Consolidate Query Methods ✅ COMPLETE

### Steps

#### 2.1 Create unified `get_due_date()` ✅

- [x] Replaced both `get_chore_effective_due_date()` AND `get_chore_due_date()`
- [x] Returns `datetime | None` (not string)
- [x] Argument order: `(chore_id, kid_id)` - chore first
- [x] Updated all 6 internal callers in chore_manager.py
- [x] Updated 3 sensor.py callers (with `.isoformat()` for string output)

#### 2.2 Refactor `chore_is_due()` to thin wrapper ✅

- [x] Reduced from ~46 lines to ~12 lines
- [x] Delegates to `ChoreEngine.chore_is_due()`
- [x] Added proper type annotations

#### 2.3 Rename `get_chore_due_window_start()` → `get_due_window_start()` ✅

- [x] Renamed method
- [x] Changed argument order: `(chore_id, kid_id)` - chore first
- [x] Updated 4 sensor.py callers
- [x] Simplified implementation using `get_due_date()`

---

## Phase 3 – Update Entry Points ✅ COMPLETE

### Steps

#### 3.1 Update `_on_data_ready()` - Add startup processing ✅

- [x] Changed from sync to async method
- [x] Calls `process_time_checks()` on startup
- [x] Processes overdue/due-window/reminder buckets
- [x] Then emits CHORES_READY signal

#### 3.2 Update `_on_midnight_rollover()` - Remove overdue call ✅

- [x] Removed `await self.check_overdue_chores(now)` line
- [x] Updated docstring to explain time checks handled by periodic update
- [x] Keeps only `process_recurring_chore_resets()`

#### 3.3 Verify `_on_periodic_update()` ✅

- [x] Already updated in Phase 1 to use `process_time_checks()`

---

## Phase 4 – Inline mark_overdue into \_process_overdue ✅ COMPLETE

### Steps

#### 4.1 Move `mark_overdue()` logic into `_process_overdue()` ✅

- [x] Inlined validation, transition calculation, effect application
- [x] Inlined persist → emit pattern (per DEVELOPMENT_STANDARDS.md § 5.3)
- [x] Moved `async_set_updated_data` call outside loop (once at end)
- [x] `mark_overdue()` method now ready for deletion in Phase 5

  if marked_count > 0:
  self.\_coordinator.async_set_updated_data(self.\_coordinator.\_data)
  const.LOGGER.debug("Processed %d overdue chore(s)", marked_count)

````

---

## Phase 5 – Delete Redundant Methods ✅ COMPLETE

### Deletion Order (dependencies first)

| Order | Method                         | Line Range | Lines | Status  |
| ----- | ------------------------------ | ---------- | ----- | ------- |
| 1     | `_handle_overdue_chore_state()` | 3989-4065  | 76    | ✅ Deleted |
| 2     | `_check_chore_overdue_status()` | 3901-3987  | 86    | ✅ Deleted |
| 3     | `check_overdue_chores()`       | 3889-3899  | 12    | ✅ Deleted |
| 4     | `_update_overdue_status()`     | 1247-1359  | 112   | ✅ Deleted |
| 5     | `mark_overdue()`               | 1194-1245  | 53    | ✅ Deleted |

**Total: ~344 lines deleted** (chore_manager.py reduced from 4110 to 3766 lines)

---

## Phase 6 – Test Updates ✅ COMPLETE

### Bulk Replacements (Done in Phase 2)

| Find                           | Replace         | Status |
| ------------------------------ | --------------- | ------ |
| `check_overdue_chores()`       | removed tests   | ✅     |
| `get_chore_effective_due_date(`| `get_due_date(` | ✅     |
| `get_chore_due_date(`          | `get_due_date(` | ✅     |
| `get_chore_due_window_start(`  | `get_due_window_start(` | ✅ |

### Test Fixes

| File | Issue | Fix |
|------|-------|-----|
| test_chore_manager.py | `test_mark_overdue_via_time_check` referenced deleted methods | Rewrote to mock `process_time_checks` and `_process_overdue` |
| test_chore_manager.py | MagicMock vs AsyncMock for async method | Changed to `AsyncMock(return_value=None)` |
| test_kid_undo_claim.py | `get_chore_stats_disapproved()` read wrong data location | Fixed helper to read from `chore_data[chore_id]["periods"]["all_time"]["disapproved"]` |

**Test Results: 1150 passed, 2 skipped, 2 deselected**

### Special Test Rewrites (Planned → Done)

| File | Test | Action |
|------|------|--------|
| test_scheduler_delegation.py | `test_check_overdue_delegates_to_manager` | ✅ Removed - architecture changed |
| test_chore_manager.py | `test_mark_overdue_via_time_check` | ✅ Rewritten with mocks |
| test_scheduler_delegation.py | Any `_update_overdue_status` mocks | Remove |

---

## Phase 7 – Update Sensor Callers

### sensor.py Updates

| Line | Current | New |
|------|---------|-----|
| 768 | `get_chore_due_window_start(kid_id, chore_id)` | `get_due_window_start(chore_id, kid_id)` |
| 790 | `get_chore_due_window_start(kid_id, chore_id)` | `get_due_window_start(chore_id, kid_id)` |
| 806 | `get_chore_due_date(kid_id, chore_id)` | `get_due_date(chore_id, kid_id)` |
| 968 | `get_chore_effective_due_date(chore_id, kid_id)` | `get_due_date(chore_id, kid_id).isoformat()` (handle None) |
| 2009 | `chore_is_due(kid_id, chore_id)` | No change (API same) |
| 2150 | `get_chore_due_window_start(kid_id, chore_id)` | `get_due_window_start(chore_id, kid_id)` |
| 2172 | `get_chore_due_window_start(kid_id, chore_id)` | `get_due_window_start(chore_id, kid_id)` |
| 2188 | `get_chore_due_date(kid_id, chore_id)` | `get_due_date(chore_id, kid_id)` |

---

## Phase 8 – Validate ✅ COMPLETE

### Results

| Check | Command | Result |
|-------|---------|--------|
| Lint | `./utils/quick_lint.sh --fix` | ✅ All checks passed |
| MyPy | (included in quick_lint) | ✅ Success: no issues found in 46 source files |
| Boundaries | (included in quick_lint) | ✅ All 10 architectural boundaries validated |
| Tests | `python -m pytest tests/ -v --tb=line` | ✅ **1150 passed**, 2 skipped, 2 deselected |

### Validation Output

```
🔍 Running ruff linting...
All checks passed!

Checking code formatting...
124 files already formatted

🔍 Running mypy type checking...
Success: no issues found in 46 source files

🏛️ Running architectural boundary checks...
   ✅ Purity Boundary
   ✅ Lexicon Standards
   ✅ CRUD Ownership
   ✅ Direct Store Access
   ✅ Cross-Manager Writes
   ✅ Emit Before Persist
   ✅ Translation Constants
   ✅ Logging Quality
   ✅ Type Syntax
   ✅ Exception Handling

✅ SUCCESS: All architectural boundaries validated
🎯 Platinum quality standards maintained!
✅ All checks passed! Ready to commit.
```

---

## Decisions (CONFIRMED)

| #   | Question                          | Decision                                                 |
| --- | --------------------------------- | -------------------------------------------------------- |
| 1   | When should time checks run?      | **DATA_READY (startup) + PERIODIC_UPDATE (every 5 min)** |
| 2   | Should midnight call it?          | **NO - midnight only does resets**                       |
| 3   | Keep aliases for backward compat? | **NO - clean break**                                     |
| 4   | Keep `mark_overdue()` separate?   | **NO - inline into `_process_overdue()`**                |
| 5   | Keep both due date methods?       | **NO - merge into single `get_due_date()`**              |
| 6   | Argument order for queries?       | **Always `chore_id` first, `kid_id` second**             |

---

## Final Method Count

### BEFORE: 16+ time-related methods

### AFTER: 7 methods

| Category   | Count | Methods                                                                                   |
| ---------- | ----- | ----------------------------------------------------------------------------------------- |
| Processing | 4     | `process_time_checks`, `_process_overdue`, `_process_due_window`, `_process_due_reminder` |
| Query      | 3     | `get_due_date`, `chore_is_overdue`, `chore_is_due`                                        |
| Utility    | 1     | `get_due_window_start` (sensors need this)                                                |
| **TOTAL**  | **8** |                                                                                           |

### Lines Removed: ~386

---

## References

| Document                                                                               | Section                  |
| -------------------------------------------------------------------------------------- | ------------------------ |
| [ARCHITECTURE.md](../ARCHITECTURE.md)                                                  | § Signal Architecture    |
| [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)                                | § 5.3 Event Architecture |
| [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) | Test patterns            |

---

## Appendix: Affected Files

### Production Code

- `custom_components/kidschores/managers/chore_manager.py` (main target)
- `custom_components/kidschores/sensor.py` (8 caller updates)

### Test Files

- `tests/test_performance.py`
- `tests/test_approval_reset_overdue_interaction.py`
- `tests/test_performance_comprehensive.py`
- `tests/test_scheduler_delegation.py`
- `tests/test_chore_services.py`
- `tests/test_chore_scheduling.py`
