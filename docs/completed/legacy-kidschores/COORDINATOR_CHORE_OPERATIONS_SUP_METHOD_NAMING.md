# Chore Method Naming Analysis & Standardization Proposal

**Created**: January 20, 2026
**Purpose**: Analyze all chore-related method names across coordinator.py and coordinator_chore_operations.py for standardization opportunities

## Summary

After extraction of 46 methods (3,688 lines) to `coordinator_chore_operations.py`, we now have chore operations split across multiple files. This analysis identifies naming inconsistencies and proposes standardization patterns.

## Current Method Inventory

### coordinator_chore_operations.py (46 methods)

#### Service Entry Points (Public API - 5 methods)

| Current Name         | Visibility | Async   | Pattern               | Notes                 |
| -------------------- | ---------- | ------- | --------------------- | --------------------- |
| `claim_chore`        | Public     | No      | `<verb>_chore`        | ✅ Standard           |
| `approve_chore`      | Public     | **Yes** | `<verb>_chore`        | ✅ Standard           |
| `disapprove_chore`   | Public     | No      | `<verb>_chore`        | ✅ Standard           |
| `undo_chore_claim`   | Public     | No      | `undo_chore_<noun>`   | ⚠️ Inconsistent order |
| `update_chore_state` | Public     | No      | `<verb>_chore_<noun>` | ✅ Standard           |

**Naming Issue**: `undo_chore_claim` breaks pattern (should be `undo_claim_chore` or `unclaim_chore`)

#### State Machine & Core Logic (4 methods)

| Current Name                 | Visibility | Pattern                        | Notes                    |
| ---------------------------- | ---------- | ------------------------------ | ------------------------ |
| `_process_chore_state`       | Private    | `_<verb>_chore_<noun>`         | ✅ Standard              |
| `_update_chore_data_for_kid` | Private    | `_<verb>_chore_<noun>_for_kid` | ✅ Standard              |
| `_can_claim_chore`           | Private    | `_can_<verb>_chore`            | ✅ Standard (validation) |
| `_can_approve_chore`         | Private    | `_can_<verb>_chore`            | ✅ Standard (validation) |

#### Tracking & Helper Methods (3 methods)

| Current Name                        | Visibility | Pattern                                   | Notes                                |
| ----------------------------------- | ---------- | ----------------------------------------- | ------------------------------------ |
| `_set_chore_claimed_completed_by`   | Private    | `_set_chore_<adjective>_<adjective>_by`   | ⚠️ Long, unclear                     |
| `_clear_chore_claimed_completed_by` | Private    | `_clear_chore_<adjective>_<adjective>_by` | ⚠️ Long, unclear                     |
| `_get_kid_chore_data`               | Private    | `_get_kid_chore_<noun>`                   | ⚠️ Inconsistent (chore vs kid first) |

**Naming Issues**:

- `_set_chore_claimed_completed_by` - overly long, hard to parse
- `_clear_chore_claimed_completed_by` - same issue
- `_get_kid_chore_data` - puts kid before chore (rest of codebase uses chore-first)

#### Query Helper Methods (9 methods)

| Current Name                           | Visibility | Pattern                                    | Notes                       |
| -------------------------------------- | ---------- | ------------------------------------------ | --------------------------- |
| `has_pending_claim`                    | Public     | `has_<adjective>_<noun>`                   | ✅ Standard (boolean query) |
| `is_overdue`                           | Public     | `is_<adjective>`                           | ✅ Standard (boolean query) |
| `is_approved_in_current_period`        | Public     | `is_<adjective>_in_<noun>`                 | ✅ Standard (boolean query) |
| `_count_pending_chores_for_kid`        | Private    | `_count_<adjective>_chores_for_kid`        | ✅ Standard                 |
| `_get_latest_pending_chore`            | Private    | `_get_<adjective>_<adjective>_chore`       | ✅ Standard                 |
| `_allows_multiple_claims`              | Private    | `_allows_<adjective>_<noun>`               | ✅ Standard (boolean query) |
| `_get_effective_due_date`              | Private    | `_get_<adjective>_<noun>_<noun>`           | ✅ Standard                 |
| `get_pending_chore_approvals_computed` | Public     | `get_<adjective>_chore_<noun>_<adjective>` | ⚠️ Suffix position unclear  |
| `_is_approval_after_reset_boundary`    | Private    | `_is_<noun>_after_<noun>_<noun>`           | ✅ Standard                 |

**Naming Issue**: `get_pending_chore_approvals_computed` - unclear why "computed" suffix

#### Overdue Logic & Reminders (4 methods)

| Current Name                | Visibility | Async   | Pattern                             | Notes               |
| --------------------------- | ---------- | ------- | ----------------------------------- | ------------------- |
| `_check_overdue_for_chore`  | Private    | No      | `_check_<adjective>_for_chore`      | ✅ Standard         |
| `_check_overdue_chores`     | Private    | **Yes** | `_check_<adjective>_chores`         | ✅ Standard         |
| `_notify_overdue_chore`     | Private    | No      | `_notify_<adjective>_chore`         | ✅ Standard         |
| `_apply_overdue_if_due`     | Private    | No      | `_apply_<adjective>_if_<adjective>` | ⚠️ Redundant naming |
| `_check_due_date_reminders` | Private    | **Yes** | `_check_<noun>_<noun>_<noun>`       | ⚠️ Missing "chore"  |

**Naming Issues**:

- `_apply_overdue_if_due` - "if_due" is redundant (overdue IS due)
- `_check_due_date_reminders` - should be `_check_chore_due_date_reminders` for clarity

#### Scheduling & Reset Methods (13 methods)

| Current Name                              | Visibility | Async   | Pattern                                          | Notes              |
| ----------------------------------------- | ---------- | ------- | ------------------------------------------------ | ------------------ |
| `_reschedule_shared_recurring_chore`      | Private    | No      | `_reschedule_<type>_<freq>_chore`                | ✅ Standard        |
| `_reschedule_independent_recurring_chore` | Private    | No      | `_reschedule_<type>_<freq>_chore`                | ✅ Standard        |
| `_reset_shared_chore_status`              | Private    | No      | `_reset_<type>_chore_<noun>`                     | ✅ Standard        |
| `_reset_independent_chore_status`         | Private    | No      | `_reset_<type>_chore_<noun>`                     | ✅ Standard        |
| `_reschedule_chore_next_due_date`         | Private    | No      | `_reschedule_chore_<noun>_<noun>_<noun>`         | ✅ Standard        |
| `_reschedule_chore_next_due_date_for_kid` | Private    | No      | `_reschedule_chore_<noun>_<noun>_<noun>_for_kid` | ✅ Standard        |
| `_handle_recurring_chore_resets`          | Private    | **Yes** | `_handle_<freq>_chore_<noun>`                    | ✅ Standard        |
| `_reset_chore_counts`                     | Private    | **Yes** | `_reset_chore_<noun>`                            | ✅ Standard        |
| `_reschedule_recurring_chores`            | Private    | **Yes** | `_reschedule_<freq>_chores`                      | ✅ Standard        |
| `_reset_daily_chore_statuses`             | Private    | **Yes** | `_reset_<freq>_chore_<noun>`                     | ✅ Standard        |
| `set_chore_due_date`                      | Public     | No      | `set_chore_<noun>_<noun>`                        | ✅ Standard        |
| `skip_chore_due_date`                     | Public     | No      | `skip_chore_<noun>_<noun>`                       | ✅ Standard        |
| `_handle_pending_claim_at_reset`          | Private    | No      | `_handle_<adjective>_<noun>_at_<noun>`           | ⚠️ Missing "chore" |

**Naming Issue**: `_handle_pending_claim_at_reset` - should be `_handle_chore_pending_claim_at_reset`

#### Chore Management (2 methods)

| Current Name           | Visibility | Async | Pattern                    | Notes       |
| ---------------------- | ---------- | ----- | -------------------------- | ----------- |
| `reset_all_chores`     | Public     | No    | `reset_<scope>_chores`     | ✅ Standard |
| `reset_overdue_chores` | Public     | No    | `reset_<adjective>_chores` | ✅ Standard |

#### Properties (2 properties)

| Current Name              | Type     | Pattern                    | Notes       |
| ------------------------- | -------- | -------------------------- | ----------- |
| `pending_chore_approvals` | Property | `<adjective>_chore_<noun>` | ✅ Standard |
| `pending_chore_changed`   | Property | `<adjective>_chore_<verb>` | ✅ Standard |

---

### coordinator.py (Remaining Chore Methods - 11 methods)

#### Entity Management (6 methods)

| Current Name                          | Visibility | Async | Pattern                          | Notes       |
| ------------------------------------- | ---------- | ----- | -------------------------------- | ----------- |
| `update_chore_entity`                 | Public     | No    | `<verb>_chore_<noun>`            | ✅ Standard |
| `delete_chore_entity`                 | Public     | No    | `<verb>_chore_<noun>`            | ✅ Standard |
| `_create_chore`                       | Private    | No    | `_<verb>_chore`                  | ✅ Standard |
| `_update_chore`                       | Private    | No    | `_<verb>_chore`                  | ✅ Standard |
| `_assign_kid_to_independent_chores`   | Private    | No    | `_assign_kid_to_<type>_chores`   | ✅ Standard |
| `_remove_kid_from_independent_chores` | Private    | No    | `_remove_kid_from_<type>_chores` | ✅ Standard |

#### Cleanup & Orphan Removal (5 methods)

| Current Name                             | Visibility | Async   | Pattern                                   | Notes                      |
| ---------------------------------------- | ---------- | ------- | ----------------------------------------- | -------------------------- |
| `_remove_orphaned_shared_chore_sensors`  | Private    | **Yes** | `_remove_<adjective>_<type>_chore_<noun>` | ✅ Standard                |
| `_remove_orphaned_kid_chore_entities`    | Private    | **Yes** | `_remove_<adjective>_kid_chore_<noun>`    | ✅ Standard                |
| `_remove_kid_chore_entities`             | Private    | No      | `_remove_kid_chore_<noun>`                | ✅ Standard                |
| `_cleanup_chore_from_kid`                | Private    | No      | `_cleanup_chore_from_kid`                 | ⚠️ Inconsistent (kid last) |
| `_cleanup_deleted_chore_references`      | Private    | No      | `_cleanup_<adjective>_chore_<noun>`       | ✅ Standard                |
| `_cleanup_deleted_chore_in_achievements` | Private    | No      | `_cleanup_<adjective>_chore_in_<noun>`    | ✅ Standard                |
| `_cleanup_deleted_chore_in_challenges`   | Private    | No      | `_cleanup_<adjective>_chore_in_<noun>`    | ✅ Standard                |
| `_clear_due_soon_reminder`               | Private    | No      | `_clear_<adjective>_<adjective>_<noun>`   | ⚠️ Missing "chore"         |

**Naming Issues**:

- `_cleanup_chore_from_kid` - inconsistent order (chore before kid)
- `_clear_due_soon_reminder` - should be `_clear_chore_due_soon_reminder`

---

## Naming Pattern Analysis

### Observed Patterns (Good)

1. **Public Service Methods**: `<verb>_chore` (claim_chore, approve_chore, disapprove_chore)
2. **Public Queries**: `is_<adjective>` or `has_<noun>` (is_overdue, has_pending_claim)
3. **Private State Updates**: `_<verb>_chore_<noun>` (\_process_chore_state, \_update_chore_data_for_kid)
4. **Private Queries**: `_<verb>_<adjective>_chore[s]` (\_get_latest_pending_chore)
5. **Validation Methods**: `_can_<verb>_chore` (\_can_claim_chore, \_can_approve_chore)
6. **Scheduling Methods**: `_reschedule_<type>_<freq>_chore` or `_reset_<type>_chore_<noun>`
7. **Cleanup Methods**: `_cleanup_<adjective>_chore_<context>` or `_remove_<adjective>_<noun>`

### Inconsistencies Found (10 issues)

| #   | Method                                 | Issue                                            | Impact | Proposed Fix                                              |
| --- | -------------------------------------- | ------------------------------------------------ | ------ | --------------------------------------------------------- |
| 1   | `undo_chore_claim`                     | Word order breaks pattern                        | Low    | `unclaim_chore` or `undo_claim_chore`                     |
| 2   | `_set_chore_claimed_completed_by`      | Overly long, hard to parse                       | Medium | `_set_chore_claimant` or `_set_chore_tracking_fields`     |
| 3   | `_clear_chore_claimed_completed_by`    | Overly long, hard to parse                       | Medium | `_clear_chore_claimant` or `_clear_chore_tracking_fields` |
| 4   | `_get_kid_chore_data`                  | Inconsistent ordering (kid-first vs chore-first) | Low    | `_get_chore_data_for_kid`                                 |
| 5   | `get_pending_chore_approvals_computed` | Unclear suffix "\_computed"                      | Low    | `get_pending_chore_approvals` (drop suffix)               |
| 6   | `_apply_overdue_if_due`                | Redundant naming                                 | Low    | `_apply_chore_overdue_state`                              |
| 7   | `_check_due_date_reminders`            | Missing "chore" for clarity                      | Medium | `_check_chore_due_date_reminders`                         |
| 8   | `_handle_pending_claim_at_reset`       | Missing "chore" for clarity                      | Medium | `_handle_chore_pending_claim_at_reset`                    |
| 9   | `_cleanup_chore_from_kid`              | Inconsistent ordering                            | Low    | `_cleanup_kid_from_chore` (to match remove pattern)       |
| 10  | `_clear_due_soon_reminder`             | Missing "chore" for clarity                      | Medium | `_clear_chore_due_soon_reminder`                          |

---

## Standardization Proposals

### Option 1: Minimal Changes (Recommended for v0.5.0)

**Only fix high-impact inconsistencies** (breaking pattern or causing confusion):

| Current                             | Proposed                               | Reason           | Breaking?    |
| ----------------------------------- | -------------------------------------- | ---------------- | ------------ |
| `_set_chore_claimed_completed_by`   | `_set_chore_tracking_fields`           | Clearer, shorter | No (private) |
| `_clear_chore_claimed_completed_by` | `_clear_chore_tracking_fields`         | Clearer, shorter | No (private) |
| `_check_due_date_reminders`         | `_check_chore_due_date_reminders`      | Clarity          | No (private) |
| `_handle_pending_claim_at_reset`    | `_handle_chore_pending_claim_at_reset` | Clarity          | No (private) |
| `_clear_due_soon_reminder`          | `_clear_chore_due_soon_reminder`       | Clarity          | No (private) |

**Impact**: 5 renames, all private methods → **0 breaking changes**

### Option 2: Full Standardization (Recommended for v0.6.0+)

Apply all 10 fixes above, including public method changes:

| Current                                | Proposed                      | Reason                | Breaking?        |
| -------------------------------------- | ----------------------------- | --------------------- | ---------------- |
| `undo_chore_claim`                     | `unclaim_chore`               | Pattern consistency   | **Yes** (public) |
| `_get_kid_chore_data`                  | `_get_chore_data_for_kid`     | Ordering consistency  | No (private)     |
| `get_pending_chore_approvals_computed` | `get_pending_chore_approvals` | Remove unclear suffix | **Yes** (public) |
| `_apply_overdue_if_due`                | `_apply_chore_overdue_state`  | Clearer intent        | No (private)     |
| `_cleanup_chore_from_kid`              | `_cleanup_kid_from_chore`     | Pattern consistency   | No (private)     |
| + 5 from Option 1                      |                               |                       |                  |

**Impact**: 10 renames, **2 breaking changes** (service methods, requires deprecation)

### Option 3: Comprehensive Refactor (Future consideration)

Additional improvements beyond naming:

- Consolidate `_set/clear_chore_tracking_fields` into single method with mode parameter
- Split `_process_chore_state` (290 lines) into smaller state-specific handlers
- Extract `_update_chore_data_for_kid` statistics logic to statistics_engine.py

**Impact**: Significant refactor, deferred to separate initiative

---

## Recommendation

**For v0.5.0 release**:

1. **Apply Option 1 (Minimal Changes)** - 5 private method renames, 0 breaking changes
2. **Document Option 2 issues** as technical debt for v0.6.0
3. **Defer Option 3** to dedicated refactoring initiative

**Rationale**:

- v0.5.0 is already a major extraction/refactor - minimize risk
- Private method renames are safe and improve code clarity
- Public method changes require deprecation cycle (add in v0.6.0, remove in v0.7.0)
- Gives time for dashboard and integrations to adapt

---

## Implementation Plan

### Phase 6A: Private Method Renames (v0.5.0) - SAFE

**Est: 1-2 hours**

1. `[ ]` Rename `_set_chore_claimed_completed_by` → `_set_chore_tracking_fields`
2. `[ ]` Rename `_clear_chore_claimed_completed_by` → `_clear_chore_tracking_fields`
3. `[ ]` Rename `_check_due_date_reminders` → `_check_chore_due_date_reminders`
4. `[ ]` Rename `_handle_pending_claim_at_reset` → `_handle_chore_pending_claim_at_reset`
5. `[ ]` Rename `_clear_due_soon_reminder` → `_clear_chore_due_soon_reminder`

**Validation**:

```bash
# Find all call sites (should all be internal)
grep -r "_set_chore_claimed_completed_by" custom_components/kidschores/
grep -r "_clear_chore_claimed_completed_by" custom_components/kidschores/
grep -r "_check_due_date_reminders" custom_components/kidschores/
grep -r "_handle_pending_claim_at_reset" custom_components/kidschores/
grep -r "_clear_due_soon_reminder" custom_components/kidschores/

# Run tests
python -m pytest tests/ -x -q --tb=line
./utils/quick_lint.sh --fix
```

### Phase 6B: Public Method Deprecation (v0.6.0) - REQUIRES PLANNING

**Est: 4-6 hours**

1. `[ ]` Add deprecated wrapper `undo_chore_claim` → calls `unclaim_chore`
2. `[ ]` Add deprecated wrapper `get_pending_chore_approvals_computed` → calls `get_pending_chore_approvals`
3. `[ ]` Update services.yaml with deprecation warnings
4. `[ ]` Update documentation
5. `[ ]` Add CHANGELOG.md entry with migration guide

**Validation**:

- Ensure old service calls still work (backward compatibility)
- Test both old and new method names
- Verify dashboard doesn't break

### Phase 6C: Deprecation Removal (v0.7.0)

**Est: 1 hour**

1. `[ ]` Remove deprecated wrappers
2. `[ ]` Update CHANGELOG.md
3. `[ ]` Update breaking changes documentation

---

## Decision Required

**Which option should we implement for v0.5.0?**

- [ ] **Option 1: Minimal Changes** (5 private renames, 0 breaking) - **RECOMMENDED**
- [ ] **Option 2: Full Standardization** (10 renames, 2 breaking)
- [ ] **Option 3: Defer all renames** to v0.6.0 (no changes in v0.5.0)

**User decision needed before proceeding with Phase 6.**
