# Phase 11: Legacy Test Status Report

**Date Completed**: January 2026  
**Status**: ✅ COMPLETE  
**Test Suite Health**: 652 passed, 536 skipped (1,188 total)

## Executive Summary

Analyzed the full legacy test suite and categorized all 214 passing (non-skipped) tests into 10 functional categories. This provides a clear roadmap for prioritizing future migration work in Phase 7.

### Key Findings

```
Legacy Test Suite Overview
┌─────────────────────────────────────────────────┐
│ tests/legacy/ directory: 733 test cases         │
│                                                 │
│ ✅ Passing: 214 (29%)    [Active coverage]     │
│ ⏭️  Skipped: 519 (71%)    [Deprecated/migrated]│
└─────────────────────────────────────────────────┘
```

**Total KidsChores Test Suite** (combined modern + legacy):
- **652 tests passing** (active regression coverage)
- **536 tests skipped** (deprecated or migrated)
- **1,188 total test cases**

## Legacy Test Categories (Passing Tests Only: 214)

### 1. Approval Reset & Timing (38 tests) 🔴 HIGH PRIORITY

**File**: `test_approval_reset_timing.py`

**What it covers**:
- All 5 approval reset types (at_midnight_once, at_midnight_multi, at_due_date_once, at_due_date_multi, upon_completion)
- Migration logic from legacy allow_multiple field
- Badge completion interaction with approval periods
- Dashboard helper sensor reflecting approval state
- Sensor attributes tracking approval period details

**Why migrate**:
- Core system behavior, critical for regression coverage
- All scenarios testable via coordinator methods
- Could benefit from service-call refactoring

**Migration effort**: Medium (requires refactoring approval reset service calls)

### 2. Badge Features (38 tests) 🟡 MEDIUM PRIORITY

**Files** (6 files):
- `test_badge_target_types_comprehensive.py` (21 tests)
- `test_badge_assignment_noncumulative_baseline.py` (6 tests)
- `test_badge_creation.py` (4 tests)
- `test_badge_progress_initialization.py` (3 tests)
- `test_badge_validation_baseline.py` (2 tests)
- `test_badge_assignment_baseline.py` (2 tests)

**What it covers**:
- Badge awarding logic across all badge types (cumulative, daily, weekly, periodic, special occasion)
- Target type evaluation (chore_count, points, days_min, days_80pct, streak_selected_chores, streak_80pct)
- Badge progress initialization and cleanup
- Cumulative badge assignment and evaluation

**Why migrate**:
- Complex logic benefits from modern test patterns
- Some tests are borderline internal unit tests vs. integration tests
- Could extract core awarding logic to modern service tests

**Migration effort**: High (complex target type logic, may need refactoring)

### 3. Core Services (20 tests) 🔴 HIGH PRIORITY

**File**: `test_services.py`

**What it covers**:
- All coordinator service methods:
  - `approve_chore()` - Grant approval and points
  - `disapprove_chore()` - Reset approval
  - `claim_chore()` - Claim chore for kid
  - `apply_bonus()`, `apply_penalty()` - Point adjustments
  - `approve_reward()`, `redeem_reward()` - Reward workflows
  - `reset_all_chores()`, `reset_all_rewards()`, etc. - Bulk operations

**Why migrate**:
- Foundational service functionality
- Directly testable via services (no internal API dependency)
- All scenarios representable in modern test patterns

**Migration effort**: Easy-Medium (straightforward service call replacement)

### 4. Overdue & Scheduling (28 tests) 🟡 MEDIUM PRIORITY

**Files** (5 files):
- `test_overdue_handling_comprehensive.py` (11 tests)
- `test_applicable_days.py` (7 tests)
- `test_skip_chore_due_date_fix.py` (5 tests)
- `test_set_chore_due_date_data_consistency.py` (3 tests)
- `test_skip_null_due_date_fix.py` (2 tests)

**What it covers**:
- Overdue marking logic (never_overdue, at_due_date)
- Applicable days filtering (day of week, frequency interaction)
- Due date calculations (per-kid vs. chore-level)
- Skip chore operations (data consistency)
- Null due date edge cases

**Why migrate**:
- Important for scheduling behavior
- Testable via set_chore_due_date service
- Some tests are edge case verification (could remain in legacy)

**Migration effort**: Medium (some complex state transitions, scheduling calculations)

### 5. Workflows (19 tests) 🔴 HIGH PRIORITY

**Files** (4 files):
- `test_workflow_chore_claim.py` (8 tests)
- `test_workflow_parent_actions.py` (5 tests)
- `test_workflow_independent_approval_reset.py` (3 tests)
- `test_workflow_shared_regression.py` (3 tests)

**What it covers**:
- End-to-end claim → approve → points workflows
- Multi-kid independent and shared chore scenarios
- Parent actions (apply penalty, reset chores)
- Approval reset interaction with shared chores
- Regression test for shared chore state bugs

**Why migrate**:
- High-value integration tests
- Perfect candidates for modern workflow helper patterns
- Already use scenario-based approach

**Migration effort**: Easy (already use service calls, good patterns)

### 6. Sensors & Attributes (17 tests) 🟡 READY FOR MIGRATION

**Files** (3 files):
- `test_sensor_values.py` (13 tests)
- `test_kid_entity_attributes.py` (2 tests)
- `test_legacy_sensors.py` (2 tests)

**What it covers**:
- Sensor value calculations (points, completed chores)
- Entity attributes and display names
- Legacy sensor creation flags
- Dashboard helper sensor data structure

**Why migrate**:
- Entity-focused tests, minimal coordinator dependency
- Already well-suited for modern test patterns
- Could be moved with minimal changes

**Migration effort**: Easy (mostly entity-focused assertions)

### 7. Chore State & Logic (16 tests) 🔴 HIGH PRIORITY

**Files** (2 files):
- `test_chore_global_state.py` (13 tests)
- `test_chore_approval_reschedule.py` (3 tests)

**What it covers**:
- Global chore state (pending, claimed, approved, completed_by_other)
- Multi-kid independent vs. shared state tracking
- State transitions on approval/disapproval
- Due date advancement on approval

**Why migrate**:
- Core state machine behavior
- Testable via service calls
- Good candidates for state matrix testing

**Migration effort**: Easy-Medium (good existing patterns in modern tests)

### 8. Data Management (15 tests) 🟡 MEDIUM PRIORITY

**Files** (3 files):
- `test_scenario_baseline.py` (7 tests)
- `test_config_flow_data_recovery.py` (5 tests)
- `test_set_skip_chore_integration.py` (3 tests)

**What it covers**:
- Scenario loading and validation (test data structure)
- Config flow data recovery from backup/paste
- Chore skipping and data consistency
- Entity count validation

**Why migrate**:
- Mostly infrastructure testing
- Config flow data recovery is important for users
- Skip chore testing is integration validation

**Migration effort**: Medium (some config flow patterns needed)

### 9. Shared Chore Features (12 tests) 🔴 HIGH PRIORITY

**Files** (2 files):
- `test_shared_first_completion.py` (9 tests)
- `test_shared_first_sensor_states.py` (3 tests)

**What it covers**:
- Shared_first completion logic (first claimer wins)
- Multi-kid approval workflows for shared_first
- Sensor state synchronization for shared chores
- Disapproval reset behavior (all kids reset)

**Why migrate**:
- Shared_first is complex unique feature
- Critical for multi-kid household scenarios
- Good candidates for comprehensive matrix testing

**Migration effort**: Easy-Medium (already use service patterns)

### 10. Diagnostics & System (7 tests) 🟢 LOW PRIORITY

**File**: `test_diagnostics.py`

**What it covers**:
- Diagnostics export data structure
- Config entry and device diagnostics
- Data consistency validation
- Storage data exposure

**Why migrate**:
- System-level testing, less critical
- Could remain in legacy as specification tests
- Low dependency on coordinator internals

**Migration effort**: Easy (mostly data structure verification)

### 11. Performance Testing (4 tests) 🟡 KEEP IN LEGACY

**File**: `test_true_performance_baseline.py`

**What it covers**:
- Coordinator update timing
- Operation timing breakdown
- Stress test with large datasets
- Performance regression baseline

**Why keep in legacy**:
- Needs direct coordinator access to profile
- Not suitable for modern integration test patterns
- Valuable for performance regression monitoring
- Can run separately as optional benchmark

**Migration effort**: N/A (keep in legacy)

## Migration Priority Matrix

### 🔴 HIGH PRIORITY (96 tests) – Start Here

These are core behavior tests that should be migrated first for maximum impact:

| Test File                           | Tests | Effort | Why High Priority          |
| ----------------------------------- | ----- | ------ | -------------------------- |
| test_approval_reset_timing.py       | 38    | MED    | Core approval system       |
| test_services.py                    | 20    | EASY   | Foundational services      |
| test_workflow_chore_claim.py        | 8     | EASY   | Critical workflows         |
| test_chore_global_state.py          | 13    | MED    | State machine behavior     |
| test_shared_first_completion.py     | 9     | MED    | Shared chore logic         |
| test_workflow_parent_actions.py     | 5     | EASY   | Parent workflows           |
| test_chore_approval_reschedule.py   | 3     | EASY   | State transitions          |

**Estimated effort**: 8-12 hours  
**Impact**: 96 tests moved, highest coverage value

### 🟡 MEDIUM PRIORITY (91 tests) – Then These

These should be migrated after high priority, as they support feature-specific testing:

| Category                | Tests | Effort | Notes                              |
| ----------------------- | ----- | ------ | ---------------------------------- |
| Badge Features          | 38    | HARD   | Complex logic, may need refactor   |
| Overdue & Scheduling    | 28    | MED    | Some edge cases, keep in legacy    |
| Sensors & Attributes    | 17    | EASY   | Ready now, minimal changes needed  |
| Data Management         | 15    | MED    | Config flow patterns needed        |

**Estimated effort**: 10-15 hours  
**Impact**: 91 tests moved, fills coverage gaps

### 🟢 READY NOW (17 tests)

These can be migrated immediately with minimal effort:
- **Sensors & Attributes** (17 tests) – Entity-focused, easily movabl

### 🔵 KEEP IN LEGACY (4 tests)

- **Performance Testing** (4 tests) – Needs direct coordinator access

## Recommended Migration Strategy

### Phase 1: Foundation (38 + 20 = 58 tests, ~6-8 hours)

```
Week 1:
  1. Migrate test_services.py (20 tests) → modern patterns
     - All service calls already properly structured
     - Minimal changes needed
  
  2. Migrate test_approval_reset_timing.py (38 tests) → phase-specific test
     - May create test_approval_reset.py for modern version
     - Keep approval period state validation
```

### Phase 2: Workflows (19 + 12 = 31 tests, ~4-6 hours)

```
Week 2:
  1. Migrate test_workflow_chore_claim.py (8 tests)
  2. Migrate test_shared_first_completion.py (9 tests)
  3. Migrate remaining workflow tests (5 + 3 + 3 = 11 tests)
```

### Phase 3: State & Logic (16 + 28 = 44 tests, ~6-8 hours)

```
Week 3:
  1. Migrate test_chore_global_state.py (13 tests)
  2. Migrate test_overdue_handling_comprehensive.py (11 tests)
  3. Migrate test_applicable_days.py (7 tests)
  4. Migrate other scheduling tests (5 + 5 = 10 tests)
```

### Phase 4: Features & Data (38 + 17 + 15 = 70 tests, ~10-15 hours)

```
Week 4-5:
  1. Migrate badge tests (38 tests) – complex, needs design
  2. Migrate sensor tests (17 tests) – easy, do first
  3. Migrate data management tests (15 tests)
```

**Total estimated time**: 26-37 hours across 4 phases

## Success Criteria for Migration

Each migrated test file should meet these criteria before removing from legacy:

1. ✅ **Modern version created** with equivalent test coverage
2. ✅ **All tests passing** in modern suite (pytest run successful)
3. ✅ **Linting clean** (pylint, ruff, mypy all pass)
4. ✅ **Service-based** (uses coordinator services, not direct state access)
5. ✅ **No duplicate coverage** (modern suite doesn't have redundant tests)
6. ✅ **Proper fixtures** (uses scenario YAML or setup_integration helpers)
7. ✅ **Documented** (notes on what test covers and why important)

## Migration Archive Plan

Once a test file is migrated:

1. **Archive in legacy/archive/** with migration_date
2. **Mark with comment** at top of file: `# MIGRATED TO: tests/test_*.py`
3. **Keep skip marker** temporarily for 1 release (v0.5.2)
4. **Remove completely** in v0.5.3+

## Next Steps

1. ✅ Phase 11 complete – Legacy test suite analyzed
2. ⏳ **Start Phase 7 migration** with HIGH priority tests
   - Start: test_services.py (20 tests, easy)
   - Then: test_approval_reset_timing.py (38 tests, foundation)
3. ⏳ **Track progress** – Update this document as tests migrate
4. ⏳ **Monitor coverage** – Ensure modern suite provides equivalent coverage

## Related Documents

- [TEST_SUITE_REORGANIZATION_IN-PROCESS.md](../in-process/TEST_SUITE_REORGANIZATION_IN-PROCESS.md) – Overall reorganization plan
- [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) – Modern test patterns
- [tests/README.md](../../tests/README.md) – Test suite overview

---

**Completion date**: January 2026  
**Completed by**: KidsChores Development Team  
**Test suite status**: 652 passed, 536 skipped ✅
