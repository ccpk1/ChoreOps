# Coordinator Chore Operations - Method Analysis & Categorization

**Supporting document for**: [COORDINATOR_CHORE_OPERATIONS_IN-PROCESS.md](COORDINATOR_CHORE_OPERATIONS_IN-PROCESS.md)

**Analysis Date**: January 20, 2026

---

## Executive Summary

### Key Findings

| Metric                               | Value              |
| ------------------------------------ | ------------------ |
| **Total methods in coordinator.py**  | 186 methods        |
| **Current file line count**          | 11,483 lines       |
| **Chore-related methods identified** | 45 methods         |
| **Estimated extractable lines**      | ~3,200 lines (28%) |
| **Tests referencing chore methods**  | 14 test files      |
| **Total tests to validate**          | 852 tests          |

### High-Value Opportunities Identified

1. **Larger extraction scope**: The original plan estimated ~1,200 lines. Analysis shows **~3,200 lines** of extractable chore logic.
2. **Method naming inconsistencies**: 12 methods have non-standard naming (opportunity for Phase 6 rename)
3. **Documentation gaps**: Several methods lack complete docstrings (can be improved during extraction)
4. **Cross-domain coupling**: 3 methods bridge chore→badge logic (acceptable but should be documented)

### Critical Traps to Avoid

1. **`update_kid_points()` dependency**: Called from `_process_chore_state()` - must NOT be extracted (lives in points domain)
2. **`_check_badges_for_kid()` calls**: Several chore methods trigger badge checks - these calls stay in place
3. **`approve_chore()` is async**: Only async chore method - requires special handling in operations class
4. **`_persist()` calls scattered**: 15+ calls within chore methods - all must be preserved exactly

---

## Complete Method Inventory

### Category 1: Service Entry Points (Public API)

These are called by button entities and services - **highest priority for extraction**.

| Method                 | Line | Async   | Lines | Calls                                                                                                                                                                                                                                                   |
| ---------------------- | ---- | ------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `claim_chore()`        | 2970 | No      | ~200  | `_can_claim_chore`, `_process_chore_state`, `_set_chore_claimed_completed_by`, `_count_pending_chores_for_kid`, `_notify_parents_translated`                                                                                                            |
| `approve_chore()`      | 3170 | **YES** | ~498  | `_can_approve_chore`, `_process_chore_state`, `_update_chore_data_for_kid`, `_reschedule_chore_next_due_date_for_kid`, `_check_overdue_chores`, `_notify_kid_translated`, `_notify_parents_translated`, `update_kid_points` (via \_process_chore_state) |
| `disapprove_chore()`   | 3668 | No      | ~121  | `_update_chore_data_for_kid`, `_process_chore_state`, `_clear_chore_claimed_completed_by`, `_notify_kid_translated`, `_notify_parents_translated`                                                                                                       |
| `undo_chore_claim()`   | 3789 | No      | ~85   | `_process_chore_state`, `_clear_chore_claimed_completed_by`, `_notify_parents_translated`                                                                                                                                                               |
| `update_chore_state()` | 3874 | No      | ~30   | `_process_chore_state`                                                                                                                                                                                                                                  |

### Category 2: State Machine & Core Logic (Internal)

Central state processing - **critical complexity**.

| Method                            | Line | Lines | Complexity | Notes                                                                              |
| --------------------------------- | ---- | ----- | ---------- | ---------------------------------------------------------------------------------- |
| `_process_chore_state()`          | 4300 | ~291  | **HIGH**   | Central state machine. Handles 6 states, multi-kid logic, global state computation |
| `_update_chore_data_for_kid()`    | 4591 | ~330  | **HIGH**   | Statistics engine, period tracking, nested data structure updates                  |
| `_can_claim_chore()`              | 4209 | ~42   | Medium     | Validation logic                                                                   |
| `_can_approve_chore()`            | 4251 | ~49   | Medium     | Validation logic                                                                   |
| `has_pending_claim()`             | 3992 | ~18   | Low        | Query helper                                                                       |
| `is_overdue()`                    | 4071 | ~16   | Low        | Query helper                                                                       |
| `is_approved_in_current_period()` | 4176 | ~33   | Low        | Query helper                                                                       |

### Category 3: Tracking & Helper Methods

Support methods for state management.

| Method                                   | Line | Lines | Notes                                       |
| ---------------------------------------- | ---- | ----- | ------------------------------------------- |
| `_set_chore_claimed_completed_by()`      | 2857 | ~86   | Handles INDEPENDENT/SHARED_FIRST/SHARED_ALL |
| `_clear_chore_claimed_completed_by()`    | 2943 | ~27   | Clears tracking fields                      |
| `_get_kid_chore_data()`                  | 3904 | ~10   | Simple accessor                             |
| `_count_pending_chores_for_kid()`        | 4010 | ~25   | Aggregation helper                          |
| `_get_latest_pending_chore()`            | 4035 | ~36   | Query helper                                |
| `_get_approval_period_start()`           | 4150 | ~26   | Query helper                                |
| `_allows_multiple_claims()`              | 2678 | ~24   | Query helper                                |
| `_get_effective_due_date()`              | 2648 | ~30   | Due date resolver                           |
| `get_pending_chore_approvals_computed()` | 4087 | ~32   | Dashboard helper data                       |

### Category 4: Scheduling & Reset Methods

Chore lifecycle management.

| Method                                      | Line  | Lines | Notes                            |
| ------------------------------------------- | ----- | ----- | -------------------------------- |
| `_reschedule_chore_next_due_date()`         | 9626  | ~84   | SHARED chore rescheduling        |
| `_reschedule_chore_next_due_date_for_kid()` | 9710  | ~126  | INDEPENDENT per-kid rescheduling |
| `_reschedule_shared_recurring_chore()`      | 9043  | ~34   | Recurring SHARED handler         |
| `_reschedule_independent_recurring_chore()` | 9077  | ~66   | Recurring INDEPENDENT handler    |
| `_reset_shared_chore_status()`              | 9255  | ~77   | Midnight reset SHARED            |
| `_reset_independent_chore_status()`         | 9332  | ~90   | Midnight reset INDEPENDENT       |
| `_handle_pending_claim_at_reset()`          | 9194  | ~61   | Pending claim handling at reset  |
| `_calculate_next_due_date_from_info()`      | 9494  | ~132  | Pure calculation helper          |
| `_calculate_next_multi_daily_due()`         | 9422  | ~72   | Multi-daily calculation          |
| `_is_approval_after_reset_boundary()`       | 9836  | ~73   | Late approval detection          |
| `set_chore_due_date()`                      | 9909  | ~147  | Manual due date setting          |
| `skip_chore_due_date()`                     | 10056 | ~157  | Skip to next due date            |
| `reset_all_chores()`                        | 10213 | ~51   | Bulk reset                       |
| `reset_overdue_chores()`                    | 10264 | ~135  | Selective reset                  |

### Category 5: Async Scheduled Operations

Background tasks - **special handling needed**.

| Method                             | Line | Async   | Lines | Notes                     |
| ---------------------------------- | ---- | ------- | ----- | ------------------------- |
| `_check_overdue_chores()`          | 8753 | **YES** | ~51   | Background overdue check  |
| `_check_due_date_reminders()`      | 8804 | **YES** | ~118  | Reminder scheduling       |
| `_handle_recurring_chore_resets()` | 8968 | **YES** | ~21   | Orchestrates resets       |
| `_reset_chore_counts()`            | 8989 | **YES** | ~16   | Counter reset             |
| `_reschedule_recurring_chores()`   | 9005 | **YES** | ~38   | Orchestrates rescheduling |
| `_reset_daily_chore_statuses()`    | 9143 | **YES** | ~51   | Daily status reset        |

### Category 6: Overdue Handling

Overdue-specific logic.

| Method                       | Line | Lines | Notes                    |
| ---------------------------- | ---- | ----- | ------------------------ |
| `_apply_overdue_if_due()`    | 8476 | ~73   | Overdue state transition |
| `_check_overdue_for_chore()` | 8549 | ~98   | Per-chore overdue check  |
| `_notify_overdue_chore()`    | 8647 | ~106  | Overdue notification     |
| `_clear_due_soon_reminder()` | 168  | ~17   | Reminder cleanup         |

### Category 7: Badge Bridge Methods

Methods that connect chores to badges - **stay in operations class** but document coupling.

| Method                                     | Line | Lines | Notes                                                    |
| ------------------------------------------ | ---- | ----- | -------------------------------------------------------- |
| `_update_chore_badge_references_for_kid()` | 6460 | ~64   | Updates badge tracked_chores when chore claimed/approved |
| `_recalculate_chore_stats_for_kid()`       | 4921 | ~20   | Stats recalculation                                      |

### NOT Extracted (Lives in Other Domains)

These methods stay in coordinator.py or other operations classes:

| Method                          | Line | Reason                                                |
| ------------------------------- | ---- | ----------------------------------------------------- |
| `_create_chore()`               | 1320 | Entity CRUD operations (separate domain)              |
| `_update_chore()`               | 1350 | Entity CRUD operations (separate domain)              |
| `delete_chore_entity()`         | 2296 | Entity CRUD operations (separate domain)              |
| `update_chore_entity()`         | 2273 | Entity CRUD operations (separate domain)              |
| `_check_badges_for_kid()`       | 5549 | Badge domain (called by chore methods, not extracted) |
| `_check_achievements_for_kid()` | 8094 | Achievement domain                                    |
| `_check_challenges_for_kid()`   | 8293 | Challenge domain                                      |
| `update_kid_points()`           | 4941 | Points domain                                         |

---

## Method Naming Analysis

### Current Inconsistencies Found

| Current Name                           | Issue                               | Proposed Standard Name                          |
| -------------------------------------- | ----------------------------------- | ----------------------------------------------- |
| `claim_chore`                          | OK                                  | Keep as-is                                      |
| `approve_chore`                        | OK                                  | Keep as-is                                      |
| `disapprove_chore`                     | OK                                  | Keep as-is                                      |
| `undo_chore_claim`                     | Inconsistent with `claim_chore`     | `undo_claim_chore`                              |
| `update_chore_state`                   | Public but only used for bulk state | `set_chore_state` (more accurate)               |
| `has_pending_claim`                    | OK                                  | Keep as-is                                      |
| `is_overdue`                           | OK                                  | Keep as-is                                      |
| `is_approved_in_current_period`        | Too long                            | `is_approved_this_period`                       |
| `_get_effective_due_date`              | OK                                  | Keep as-is                                      |
| `_allows_multiple_claims`              | Should match boolean pattern        | `_is_multi_claim_chore` or `_can_multi_claim`   |
| `_handle_pending_claim_at_reset`       | OK                                  | Keep as-is                                      |
| `_recalculate_chore_stats_for_kid`     | OK                                  | Keep as-is                                      |
| `get_pending_chore_approvals_computed` | Redundant "computed"                | `get_pending_chore_approvals` (rename property) |
| `_is_approval_after_reset_boundary`    | OK but long                         | `_is_late_approval`                             |
| `reset_all_chores`                     | OK                                  | Keep as-is                                      |
| `reset_overdue_chores`                 | OK                                  | Keep as-is                                      |

### Naming Convention Standards (For Phase 6)

```
Public service methods:    verb_noun()           → claim_chore(), approve_chore()
Query methods (bool):      is_*() or has_*()     → is_overdue(), has_pending_claim()
Query methods (data):      get_*()               → get_pending_chore_approvals()
Internal state changes:    _verb_noun()          → _process_chore_state()
Internal helpers:          _verb_noun_for_noun() → _update_chore_data_for_kid()
Validation:                _can_verb_noun()      → _can_claim_chore()
```

---

## Cross-Domain Dependencies Map

```
claim_chore()
├── _can_claim_chore() ..................... ✅ In scope
├── _process_chore_state() ................ ✅ In scope
│   └── update_kid_points() ............... ❌ NOT extracted (points domain)
├── _set_chore_claimed_completed_by() ..... ✅ In scope
├── _count_pending_chores_for_kid() ....... ✅ In scope
├── _clear_due_soon_reminder() ............ ✅ In scope
├── _notify_parents_translated() .......... ❌ NOT extracted (notification domain)
└── _persist() ............................ ❌ NOT extracted (core coordinator)

approve_chore() [ASYNC]
├── _get_approval_lock() .................. ❌ NOT extracted (core coordinator)
├── _can_approve_chore() .................. ✅ In scope
├── _process_chore_state() ................ ✅ In scope
│   └── update_kid_points() ............... ❌ NOT extracted (points domain)
├── _update_chore_data_for_kid() .......... ✅ In scope
├── _update_streak_progress() ............. ❌ NOT extracted (achievement domain)
├── _is_approval_after_reset_boundary() ... ✅ In scope
├── _reschedule_chore_next_due_date() ..... ✅ In scope
├── _reschedule_chore_next_due_date_for_kid() ✅ In scope
├── is_approved_in_current_period() ....... ✅ In scope
├── _count_pending_chores_for_kid() ....... ✅ In scope
├── _get_latest_pending_chore() ........... ✅ In scope
├── _check_overdue_chores() [ASYNC] ....... ✅ In scope (but calls back to coordinator)
├── _notify_kid_translated() .............. ❌ NOT extracted (notification domain)
├── _notify_parents_translated() .......... ❌ NOT extracted (notification domain)
├── clear_notification_for_parents() ...... ❌ NOT extracted (notification domain)
├── _clear_due_soon_reminder() ............ ✅ In scope
└── _persist() ............................ ❌ NOT extracted (core coordinator)
```

---

## Extraction Line Count Summary

| Category             | Methods | Est. Lines |
| -------------------- | ------- | ---------- |
| Service Entry Points | 5       | ~934       |
| State Machine & Core | 7       | ~779       |
| Tracking & Helpers   | 9       | ~298       |
| Scheduling & Reset   | 14      | ~1,256     |
| Async Scheduled Ops  | 6       | ~295       |
| Overdue Handling     | 4       | ~294       |
| Badge Bridge         | 2       | ~84        |
| **TOTAL**            | **47**  | **~3,940** |

**Adjusted estimate after overlap**: ~3,200 lines (accounting for shared line ranges)

---

## Risk Assessment

### High Risk Items

1. **`approve_chore()` async nature**
   - Only async method in chore operations
   - Uses `self._get_approval_lock()` from coordinator
   - Calls `self._check_overdue_chores()` which is also async
   - **Mitigation**: ChoreOperations class must be designed to support async methods properly

2. **`_process_chore_state()` centrality**
   - Called by 8+ other methods
   - Contains nested function `inc_stat()` at line 4695
   - 291 lines of complex state machine logic
   - **Mitigation**: Extract as unit, don't modify internal structure

3. **Statistics Engine coupling**
   - `_update_chore_data_for_kid()` calls `self.stats.get_period_keys()`
   - StatisticsEngine is stored on coordinator as `self.stats`
   - **Mitigation**: Operations class inherits from coordinator, `self.stats` accessible via MRO

### Medium Risk Items

4. **15+ `_persist()` calls**
   - Scattered throughout chore methods
   - Must preserve all calls exactly as-is
   - **Mitigation**: Document all persist call locations, verify during extraction

5. **Achievement/Challenge updates in `approve_chore()`**
   - Lines 3400-3500 update achievement streaks and challenge progress
   - These are chore-triggered but achievement-domain logic
   - **Mitigation**: Keep in ChoreOperations (chore is the trigger point)

### Low Risk Items

6. **Query helpers** (`has_pending_claim`, `is_overdue`, etc.)
   - Simple, stateless methods
   - Easy to extract
   - **Mitigation**: Extract as group

---

## Implementation Recommendations

### Recommendation 1: Split Extraction into Two Phases

**Phase 2A**: Core operations (service entry + state machine)

- `claim_chore()`, `approve_chore()`, `disapprove_chore()`, `undo_chore_claim()`
- `_process_chore_state()`, `_update_chore_data_for_kid()`
- ~1,800 lines

**Phase 2B**: Supporting operations (scheduling + queries)

- All scheduling methods
- All query helpers
- ~1,400 lines

This reduces risk by allowing validation between phases.

### Recommendation 2: Add Method Rename Phase

**Phase 6** (new): Consistent method naming

- Rename 6-8 methods for consistency
- Update all test references
- Requires separate PR for clean git history

### Recommendation 3: Create ChoreOperations as Abstract Base

```python
class ChoreOperations:
    """Chore lifecycle operations mixin for KidsChoresDataCoordinator.

    This class is not intended to be instantiated directly.
    All methods access coordinator data via `self` (multiple inheritance).
    """

    # Type hints for IDE support (actual attrs on coordinator)
    if TYPE_CHECKING:
        kids_data: KidsCollection
        chores_data: ChoresCollection
        hass: HomeAssistant
        stats: StatisticsEngine
        # ... etc
```

### Recommendation 4: Validation Checkpoints

After each extraction batch, run:

```bash
mypy custom_components/kidschores/coordinator*.py
python -m pytest tests/ -v --tb=line -x  # Stop on first failure
```

---

## Files to Create/Modify

| File                              | Action | Notes                                              |
| --------------------------------- | ------ | -------------------------------------------------- |
| `coordinator_chore_operations.py` | CREATE | New file with ChoreOperations class                |
| `coordinator.py`                  | MODIFY | Remove extracted methods, add import               |
| `__init__.py`                     | VERIFY | No changes needed (coordinator imported as before) |
| Tests (14 files)                  | VERIFY | No changes needed (services call coordinator)      |

---

## Next Steps

1. Update main plan with revised line count estimates
2. Add Phase 6 (method renaming) to plan
3. Split Phase 2 into 2A and 2B
4. Create validation checkpoint requirements
5. Document the 47 methods with their new locations
