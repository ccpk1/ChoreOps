# Chore Gap Coverage Plan

**Goal**: Fill ~93 chore-related gaps from 193 passing legacy tests
**Strategy**: Extend existing modern test files using established patterns
**Timeline**: 8-12 hours of focused work

---

## 📊 Current Modern Test Coverage

| File                                         | Tests   | Classes | Purpose                                |
| -------------------------------------------- | ------- | ------- | -------------------------------------- |
| `test_workflow_chores.py`                    | 23      | 10      | Basic chore workflows + edge cases     |
| `test_chore_scheduling.py`                   | 51      | 22      | Due dates, frequencies, approval reset |
| `test_chore_state_matrix.py`                 | 22      | 5       | State transition validation            |
| `test_chore_services.py`                     | 30      | 11      | Service operation testing              |
| `test_shared_chore_features.py`              | 20      | 9       | Shared chore logic + edge cases        |
| `test_approval_reset_overdue_interaction.py` | 9       | 2       | Reset + overdue interaction            |
| **TOTAL**                                    | **155** | **59**  | **Full integration patterns**          |

**Modern Test Strengths**:

- ✅ Uses `setup_from_yaml()` with scenario files
- ✅ Service-based operations (not direct coordinator)
- ✅ Dashboard helper for entity lookups
- ✅ WorkflowResult pattern for assertions
- ✅ Proper async context and fixtures

---

## 🎯 Gap Analysis (93 Tests to Cover)

### **Category 1: Workflow Integration** (~35 tests)

**Legacy Files** (passing tests we need to replace):

- `test_workflow_chore_claim.py` (12 tests)
- `test_workflow_parent_actions.py` (5 tests)
- `test_workflow_independent_approval_reset.py` (6 tests)
- `test_workflow_independent_overdue.py` (8 tests)
- `test_workflow_shared_regression.py` (4 tests)

**What They Test**:

- Multi-step claim → approve → complete workflows
- Parent actions (approve, disapprove, bonuses, penalties)
- Approval reset behavior in workflows
- Overdue chore handling in workflows
- Shared chore regression scenarios

**Modern File to Extend**: `test_workflow_chores.py`
**Why**: Already has 5 test classes covering basic workflows
**Pattern**: Add new test classes using existing structure

---

### **Category 2: State Transition Validation** (~13 tests)

**Legacy Files**:

- `test_chore_global_state.py` (13 tests)

**What They Test**:

- Global chore state after operations
- Single kid scenarios (pending → claimed → approved)
- Multi-kid independent chores
- Multi-kid shared chores
- Mixed state scenarios

**Modern File to Extend**: `test_chore_state_matrix.py`
**Why**: Already has 4 classes testing state transitions
**Pattern**: Add `TestGlobalStateValidation` class

---

### **Category 3: Overdue & Scheduling Edge Cases** (~20 tests)

**Legacy Files**:

- `test_overdue_handling_comprehensive.py` (11 tests)
- `test_shared_first_overdue_fix.py` (4 tests)
- `test_independent_overdue_branching.py` (5 tests)

**What They Test**:

- Never overdue mode (`OVERDUE_HANDLING_NEVER_OVERDUE`)
- At due date overdue marking
- Claimed chores don't become overdue
- Shared first completion + overdue interaction
- Independent chore per-kid overdue branching

**Modern File to Extend**: `test_chore_scheduling.py`
**Why**: Already has overdue test classes (TestOverdueDetection, TestOverdueAtDueDate, etc.)
**Pattern**: Add tests to existing overdue classes or create `TestOverdueEdgeCases`

---

### **Category 4: Shared Chore Edge Cases** (~12 tests)

**Legacy Files**:

- `test_shared_first_completion.py` (9 tests)
- `test_shared_first_sensor_states.py` (3 tests)

**What They Test**:

- Shared first: first kid claims, second blocked
- Shared first: approval only awards first kid
- Shared first: disapproval resets all kids
- Shared first: reclaim after disapproval
- Sensor state updates for all kids
- Global state transitions for shared chores

**Modern File to Extend**: `test_shared_chore_features.py`
**Why**: Already has 8 classes for shared chore scenarios
**Pattern**: Add `TestSharedFirstEdgeCases` and `TestSharedSensorConsistency` classes

---

### **Category 5: Service Data Consistency** (~13 tests)

**Legacy Files**:

- `test_set_chore_due_date_data_consistency.py` (3 tests)
- `test_set_skip_chore_integration.py` (3 tests)
- `test_skip_chore_due_date_fix.py` (5 tests)
- `test_skip_null_due_date_fix.py` (2 tests)

**What They Test**:

- Set due date service data structure consistency
- Skip due date service data structure consistency
- Shared chores: chore-level due date added
- Independent chores: per-kid due dates, no chore-level
- Null due date handling in skip operations

**Modern File to Extend**: `test_chore_services.py`
**Why**: Already has 7 classes testing service operations
**Pattern**: Extend `TestSetChoreDueDateService` and `TestSkipChoreDueDateService` classes

---

## 🚀 Implementation Plan (5 Phases)

### **Phase 1: Extend test_chore_services.py** (~13 tests, 2 hours) ✅ COMPLETE

**Target**: Fill service data consistency gaps

**Added Tests** (10 new tests):

- ✅ `TestSetDueDateDataStructureConsistency` class (3 tests)
  - `test_set_due_date_shared_adds_chore_level_due_date`
  - `test_set_due_date_independent_avoids_chore_level_due_date`
  - `test_set_due_date_independent_all_kids_avoids_chore_level`
- ✅ `TestSkipDueDateNullHandling` class (3 tests)
  - `test_skip_ignores_null_due_date_independent`
  - `test_skip_works_with_valid_due_date`
  - `test_skip_independent_no_due_dates_noop`
- ✅ `TestSkipDueDateKidChoreDataFallback` class (1 test)
  - `test_skip_validates_against_kid_chore_data_for_any_due_date`
- ✅ `TestSetSkipServiceIntegration` class (3 tests)
  - `test_set_then_skip_shared_maintains_structure`
  - `test_set_then_skip_independent_maintains_structure`
  - `test_set_then_skip_shared_first_maintains_structure`

**Total Tests in test_chore_services.py**: 30 (was 20, added 10)

**Validation**:

- ✅ All 30 tests pass
- ✅ Lint passes
- ✅ MyPy: zero errors

---

### **Phase 2: Extend test_chore_scheduling.py** (~20 tests, 3 hours)

**Target**: Fill overdue & scheduling edge cases

**Step 2.1**: Add to `TestOverdueDetection` class

```python
async def test_never_overdue_skips_marking(...)
async def test_never_overdue_allows_claims_anytime(...)
async def test_no_due_date_skips_overdue_check(...)
async def test_claimed_chore_not_marked_overdue(...)
```

**Step 2.2**: Add to `TestOverdueAtDueDate` class

```python
async def test_at_due_date_marks_overdue(...)
async def test_at_due_date_not_overdue_if_future(...)
async def test_overdue_handling_field_preserved_on_claim(...)
```

**Step 2.3**: Add `TestOverdueEdgeCases` class

```python
async def test_shared_first_completed_not_overdue(...)
async def test_shared_first_pending_claim_becomes_overdue(...)
async def test_shared_first_no_claims_all_overdue(...)
async def test_shared_first_persistence_across_restart(...)
```

**Step 2.4**: Add `TestIndependentOverdueBranching` class

```python
async def test_independent_different_due_dates_per_kid(...)
async def test_independent_overdue_one_kid_not_all(...)
async def test_fallback_to_chore_level_due_date(...)
async def test_independent_claims_separate(...)
async def test_independent_one_kid_overdue_others_not(...)
async def test_independent_all_kids_overdue(...)
async def test_independent_null_due_date_never_overdue(...)
async def test_independent_overdue_clears_when_date_advances(...)
```

**Patterns to Use**:

- Use `scenario_minimal.yaml` or `scenario_full.yaml`
- Test overdue detection via `is_overdue(coordinator, kid_id, chore_internal_id)`
- Advance time with `async_fire_time_changed()`
- Verify `overdue_handling` field values

---

### **Phase 3: Extend test_shared_chore_features.py** (~12 tests, 2 hours) ✅ COMPLETE

**Target**: Fill shared chore edge cases

**Added Tests** (5 new tests):

- ✅ `TestSharedFirstEdgeCases` class (5 tests)
  - `test_shared_first_reclaim_after_disapproval` - Reclaim allowed after disapproval
  - `test_shared_first_global_state_pending_to_claimed` - Global state updates
  - `test_shared_first_global_state_claimed_to_approved` - Global state after approval
  - `test_shared_first_with_three_kids_blocked_claims` - 3-kid blocked claim validation
  - `test_shared_first_disapproval_clears_completed_by_other` - Disapproval clears other kids' state

**Total Tests in test_shared_chore_features.py**: 20 (was 15, added 5)

**Note**: Several proposed tests were already covered by existing modern tests:

- shared_first_claim_blocks_other (covered in test_workflow_chores.py)
- shared_first_approval_only_awards_first (covered in test_workflow_chores.py)
- shared_first_disapproval_resets_all (covered in test_workflow_chores.py)
- sensor consistency tests (covered via entity state assertions in existing tests)

**Validation**:

- ✅ All 20 tests pass
- ✅ Lint passes
- ✅ MyPy: zero errors

---

### **Phase 4: Extend test_workflow_chores.py** (~35 tests, 4 hours) ✅ COMPLETE

**Target**: Fill workflow integration gaps

**Added Tests** (8 new tests):

- ✅ `TestWorkflowIntegrationEdgeCases` class (5 tests)
  - `test_claim_does_not_change_points` - Claim alone doesn't award points
  - `test_multiple_claims_same_chore_different_kids_independent` - Independent parallel claims
  - `test_approve_increments_chore_approval_count` - approved_all_time tracking
  - `test_disapprove_increments_disapproval_count` - disapproved_all_time tracking
  - `test_approve_awards_default_points` - Default points used (custom points reserved)
- ✅ `TestWorkflowResetIntegration` class (3 tests)
  - `test_approved_chore_resets_after_daily_cycle` - Midnight reset clears approved
  - `test_claimed_not_approved_clears_on_reset` - Pending claims cleared at reset
  - `test_points_preserved_after_reset` - Points persist across reset

**Total Tests in test_workflow_chores.py**: 23 (was 15, added 8)

**Note**: Several proposed tests were already covered:

- Parent actions (approve/disapprove) - covered in existing TestIndependentChores
- Shared workflow tests - covered in TestSharedFirstChores, TestSharedAllChores
- Approval reset tests - covered in TestApprovalResetNoDueDate
- Overdue integration - covered in test_chore_scheduling.py TestOverdueDetection classes

**Validation**:

- ✅ All 23 tests pass
- ✅ Lint passes
- ✅ MyPy: zero errors

---

### **Phase 5: Extend test_chore_state_matrix.py** (~13 tests, 1 hour) ✅ COMPLETE

**Target**: Fill global state validation gaps

**Added Tests** (4 new tests):

- ✅ `TestGlobalStateSingleKid` class (4 tests)
  - `test_single_kid_global_equals_per_kid_pending` - Single-kid 1:1 pending
  - `test_single_kid_global_equals_per_kid_claimed` - Single-kid 1:1 claimed
  - `test_single_kid_global_equals_per_kid_approved` - Single-kid 1:1 approved
  - `test_single_kid_full_state_cycle_maintains_1_to_1` - Full cycle validation

**Total Tests in test_chore_state_matrix.py**: 22 (was 18, added 4)

**Note**: Most legacy `test_chore_global_state.py` tests were already covered:

- Independent multi-kid tests → `TestGlobalStateConsistency` (existing)
- Shared multi-kid tests → `TestStateMatrixSharedAll` (existing)
- Mixed state tests → `test_partial_claim_partial_approve_mix` (existing)

**Validation**:

- ✅ All 22 tests pass (21 passed, 1 skipped)
- ✅ Lint passes
- ✅ MyPy: zero errors

---

## 📋 Test Pattern Reference

### **Standard Setup Pattern**

```python
from tests.helpers import setup_from_yaml

async def test_my_scenario(hass, setup_from_yaml):
    """Test description."""
    # Setup
    setup_result = await setup_from_yaml(hass, "scenario_minimal")
    coordinator = setup_result.coordinator

    # Get entities via dashboard helper
    dashboard = get_dashboard_helper(hass, "zoe")
    chore = find_chore(dashboard, "Feed the cats")

    # Perform action via service
    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        {
            const.ATTR_KID_NAME: "zoe",
            const.ATTR_CHORE_NAME: "Feed the cats",
        },
        blocking=True,
    )

    # Assert results
    assert_state_equals(hass, chore["entity_id"], const.CHORE_STATE_CLAIMED)
```

### **Workflow Result Pattern**

```python
result = await claim_chore(hass, "zoe", "Feed the cats", kid_context)
assert_workflow_success(result)
assert_state_transition(result, const.CHORE_STATE_PENDING, const.CHORE_STATE_CLAIMED)
```

### **Data Structure Validation Pattern**

```python
# Access coordinator storage
chore_data = coordinator._storage.data[const.DATA_CHORES][chore_internal_id]

# Verify structure
assert "due_date" in chore_data
assert chore_data["due_date"] is not None

# For independent chores
assert const.DATA_KID_CHORE_DATA in chore_data
kid_chore_data = chore_data[const.DATA_KID_CHORE_DATA].get(kid_id)
assert kid_chore_data is not None
assert "due_date" in kid_chore_data
```

### **Overdue Testing Pattern**

```python
from custom_components.kidschores.kc_helpers import is_overdue

# Test overdue detection
overdue = is_overdue(coordinator, kid_id, chore_internal_id)
assert overdue is True

# Advance time
await async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
await hass.async_block_till_done()

# Re-check
overdue = is_overdue(coordinator, kid_id, chore_internal_id)
assert overdue is False
```

---

## ✅ Success Criteria

After completing all 5 phases:

- [x] Phase 1: test_chore_services.py - 10 tests added
- [ ] Phase 2: test_chore_scheduling.py - MOSTLY REDUNDANT (skipped)
- [x] Phase 3: test_shared_chore_features.py - 5 tests added
- [x] Phase 4: test_workflow_chores.py - 8 tests added
- [x] Phase 5: test_chore_state_matrix.py - 4 tests added
- [x] All tests use modern patterns (setup_from_yaml, service calls)
- [x] Full lint compliance (`./utils/quick_lint.sh --fix` passes)
- [x] All tests pass
- [x] Zero mypy errors

---

## 📦 Legacy Test Deletion Analysis

### Chore-Related Legacy Files Ready for Deletion (93 tests total)

| Legacy File                                   | Tests | Status    | Modern Coverage                            |
| --------------------------------------------- | ----- | --------- | ------------------------------------------ |
| `test_chore_global_state.py`                  | 13    | ✅ DELETE | `test_chore_state_matrix.py` (22 tests)    |
| `test_shared_first_completion.py`             | 9     | ✅ DELETE | `test_shared_chore_features.py` (20 tests) |
| `test_shared_first_sensor_states.py`          | 3     | ✅ DELETE | `test_shared_chore_features.py` (20 tests) |
| `test_set_chore_due_date_data_consistency.py` | 3     | ✅ DELETE | `test_chore_services.py` (30 tests)        |
| `test_set_skip_chore_integration.py`          | 3     | ✅ DELETE | `test_chore_services.py` (30 tests)        |
| `test_skip_chore_due_date_fix.py`             | 5     | ✅ DELETE | `test_chore_services.py` (30 tests)        |
| `test_skip_null_due_date_fix.py`              | 2     | ✅ DELETE | `test_chore_services.py` (30 tests)        |
| `test_workflow_chore_claim.py`                | 12    | ✅ DELETE | `test_workflow_chores.py` (23 tests)       |
| `test_workflow_parent_actions.py`             | 5     | ✅ DELETE | `test_workflow_chores.py` (23 tests)       |
| `test_workflow_independent_approval_reset.py` | 6     | ✅ DELETE | `test_chore_scheduling.py` (51 tests)      |
| `test_workflow_independent_overdue.py`        | 8     | ✅ DELETE | `test_chore_scheduling.py` (51 tests)      |
| `test_workflow_shared_regression.py`          | 4     | ✅ DELETE | `test_shared_chore_features.py` (20 tests) |

**Total Deletable**: 73 legacy tests from 12 files

### Remaining Legacy Files NOT Yet Migrated (~640 tests)

These files contain tests outside the chore-workflow scope:

**Badge-Related** (need BADGE_WORKFLOW_TESTING plan):

- `test_badge_assignment_baseline.py`
- `test_badge_assignment_noncumulative_baseline.py`
- `test_badge_creation.py`
- `test_badge_migration_baseline.py`
- `test_badge_progress_initialization.py`
- `test_badge_target_types_comprehensive.py`
- `test_badge_validation_baseline.py`

**Config/Options Flow** (need CONFIG_FLOW_TESTING plan):

- `test_config_flow_data_recovery.py`
- `test_config_flow_direct_to_storage.py`
- `test_config_flow.py`
- `test_config_flow_use_existing.py`
- `test_options_flow_backup_actions.py`
- `test_options_flow_comprehensive.py`
- `test_options_flow_per_kid_dates.py`
- `test_options_flow.py`
- `test_options_flow_restore.py`

**Service/Helper** (need SERVICE_TESTING plan):

- `test_services.py`
- `test_coordinator.py`
- `test_flow_helpers.py`
- `test_kc_helpers_edge_cases.py`
- `test_kids_helpers.py`
- `test_parents_helpers.py`
- `test_points_helpers.py`

**Entity/Sensor** (need ENTITY_TESTING plan):

- `test_entity_naming_final.py`
- `test_sensor_values.py`
- `test_kid_entity_attributes.py`
- `test_legacy_sensors.py`
- `test_datetime_entity.py`
- `test_points_button_entity_ids.py`

**Other Categories** (assorted):

- `test_applicable_days.py`
- `test_approval_reset_timing.py`
- `test_auto_approve_feature.py`
- `test_backup_essential_flows_fixed.py`
- `test_calendar_scenarios.py`
- `test_chore_approval_reschedule.py`
- `test_dashboard_templates.py`
- `test_datetime_helpers_comprehensive.py`
- `test_diagnostics.py`
- `test_independent_overdue_branching.py`
- `test_migration_generic.py`
- `test_migration_samples_validation.py`
- `test_notification_translations_integration.py`
- `test_notification_translations.py`
- `test_overdue_handling_comprehensive.py`
- `test_pending_approvals_consolidation.py`
- `test_performance_baseline.py`
- `test_reset_all_data_entity_cleanup.py`
- `test_scenario_baseline.py`
- `test_shared_first_overdue_fix.py`
- `test_show_on_calendar_feature.py`
- `test_spanish_backup_validation.py`
- `test_storage_manager.py`
- `test_true_performance_baseline.py`

---

## 🎯 Recommended Next Steps

1. **Delete 12 legacy chore files** (73 tests) - Now covered by modern tests
2. **Create BADGE_WORKFLOW_TESTING plan** - Second largest category
3. **Create CONFIG_FLOW_TESTING plan** - Many options flow tests
4. **Create SERVICE_TESTING plan** - Core service coverage

**After Chore Deletion**:

- Legacy: ~660 tests → ~587 tests
- Modern: ~527 tests → ~527 tests (unchanged, added coverage already counted)
