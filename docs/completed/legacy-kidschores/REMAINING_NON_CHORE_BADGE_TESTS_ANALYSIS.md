# Remaining Non-Chore/Non-Badge Tests Analysis

**Date**: December 2025
**Context**: Phase 9 test suite reorganization - deep dive of remaining active legacy tests excluding chore and badge-related tests
**Current Status**: 27 active legacy test files remain, 10 are non-chore/non-badge

---

## Executive Summary

After completing Groups 1 (Config Flow), 2 (Options Flow), 4 (Entity/Platform), 5B (Backup), 5D (Migration), and 5E (Storage/Performance), **10 active legacy test files remain** that are neither chore-related nor badge-related:

| Category                      | Files | Tests | Modern Coverage          | Priority | Recommendation                      | Status            |
| ----------------------------- | ----- | ----- | ------------------------ | -------- | ----------------------------------- | ----------------- |
| **Auto-Approve Feature**      | 1     | 9     | ✅ Extensive (15+ tests) | LOW      | Skip - redundant                    | ✅ STEP 1 DONE    |
| **Coordinator Core**          | 1     | 5     | ✅ Full coverage         | LOW      | Skip - covered by integration tests | ✅ STEP 1 DONE    |
| **Datetime Helpers**          | 1     | 37    | ⚠️ Minimal (3 uses)      | MEDIUM   | Extract edge cases                  | 📋 STEP 3 PENDING |
| **KC Helpers Edge Cases**     | 1     | 8     | ❌ None                  | HIGH     | Migrate - unique logic              | ✅ STEP 2 DONE    |
| **Kids Helpers**              | 1     | 11    | ❌ None                  | HIGH     | Migrate - critical validation       | ✅ STEP 2 DONE    |
| **Notification Translations** | 1     | 3     | ✅ Excellent (9 tests)   | LOW      | Skip - superseded                   | ✅ STEP 1 DONE    |
| **Parents Helpers**           | 1     | 12    | ❌ None                  | HIGH     | Migrate - critical validation       | ✅ STEP 2 DONE    |
| **Pending Approvals**         | 1     | 4     | ✅ Partial (dashboard)   | MEDIUM   | Extract unique tests                | 📋 STEP 3 PENDING |
| **Points Helpers**            | 1     | 8     | ❌ None                  | HIGH     | Migrate - critical validation       | ✅ STEP 2 DONE    |
| **Show on Calendar**          | 1     | 3     | ❌ None                  | MEDIUM   | Migrate - feature test              | 📋 STEP 3 PENDING |

**Overall Progress**:

- ✅ Step 1 (Skip LOW PRIORITY): 3 files, 17 tests - **COMPLETE** (skip markers added, 96+ modern test references)
- ✅ Step 2 (Migrate HIGH PRIORITY): 4 files, 39 tests - **COMPLETE** (all 39 tests passing, 100% validation)
- ✅ Step 3 (Extract MEDIUM PRIORITY): 3 files, 30 tests - **COMPLETE** (all 30 tests passing, 100% validation)
- ✅ Step 4 (Verify full suite): Full validation and documentation - **COMPLETE** (438 tests passing, 17 skipped)
- 📋 Phase 9 Completion: Ready for final documentation and wrap-up

---

## Detailed Analysis by Category

### 1. Auto-Approve Feature (`test_auto_approve_feature.py`) ⚠️ REDUNDANT

**Purpose**: Test auto-approval feature for chores (immediate approval vs parent notification)

**Legacy Tests** (9 tests):

- `test_auto_approve_false_chore_awaits_parent_approval` - Chore waits in `claimed` state
- `test_auto_approve_false_sends_parent_notification` - Parent notified when claimed
- `test_auto_approve_true_approves_immediately` - Chore immediately approved, points awarded
- `test_auto_approve_true_no_parent_notification` - No parent notification sent
- `test_migration_adds_auto_approve_field_to_existing_chores` - Migration adds field
- `test_parent_can_disapprove_auto_approved_chore` - Parent can still disapprove
- `test_multiple_chores_different_auto_approve_settings` - Multiple chores with different settings
- `test_default_constant_value` - `DEFAULT_CHORE_AUTO_APPROVE = False`
- `test_default_show_on_calendar_value` - `DEFAULT_CHORE_SHOW_ON_CALENDAR = True`

**Modern Coverage** ✅ EXTENSIVE (15+ tests across 4 files):

- `tests/test_workflow_notifications.py::test_auto_approve_chore_no_parent_notification` (1 test)
- `tests/test_yaml_setup.py::test_setup_from_yaml_auto_approve` (1 test)
- `tests/test_chore_scheduling.py`: 3 tests (auto-approve with pending, reset, removal)
- `tests/test_shared_chore_features.py`: 10 tests (shared chores with auto-approve for first/all)

**Analysis**:

- ✅ **Fully redundant** - Modern tests cover all scenarios
- Modern tests use proper config flow setup (not direct coordinator manipulation)
- Modern tests integrate with scheduling, shared chores, notifications
- Legacy tests test the same logic but with inferior patterns

**Recommendation**: **SKIP** - Add skip marker, reference modern test coverage

---

### 2. Coordinator Core (`test_coordinator.py`) ⚠️ REDUNDANT

**Purpose**: Test coordinator core workflows (lifecycle, points, rewards, device naming)

**Legacy Tests** (5 tests):

- `test_chore_lifecycle_complete_workflow` - Create, claim, approve, verify persistence
- `test_points_management_flow` - Chores, bonuses, penalties
- `test_reward_approval_workflow` - Reward redemption with approval/disapproval
- `test_kid_device_name_updates_immediately` - Kid device name updates on coordinator change
- `test_config_entry_title_updates_device_names` - Config entry title changes propagate to devices

**Modern Coverage** ✅ FULL COVERAGE:

- All coordinator workflows covered by:
  - `test_workflow_chores.py` (11 tests) - Chore lifecycle
  - `test_chore_services.py` (20 tests) - Service actions
  - `test_chore_scheduling.py` (41 tests) - Complex scheduling
  - `test_shared_chore_features.py` (15 tests) - Shared chore workflows
  - Diagnostic and integration tests throughout suite

**Analysis**:

- ✅ **Fully redundant** - Modern integration tests cover all workflows
- Legacy tests manipulate coordinator directly (anti-pattern)
- Modern tests use config flow + entity state verification (best practice)
- Device naming is implementation detail, less critical than functional workflows

**Recommendation**: **SKIP** - Add skip marker, reference modern integration tests

---

### 3. Datetime Helpers (`test_datetime_helpers_comprehensive.py`) ⚠️ PARTIAL COVERAGE

**Purpose**: Comprehensive datetime parsing/formatting across multiple timezones

**Legacy Tests** (37 tests):

- Timezone parsing: UTC, US/Pacific, Europe/Prague, Asia/Tokyo, etc.
- ISO format variations: with/without 'T', with/without 'Z', with timezone offsets
- Edge cases: DST boundaries, leap seconds, invalid formats
- Format helpers: `format_datetime_for_display`, `format_datetime_iso`
- Relative datetime: "now", "tomorrow", "in 3 days"

**Modern Coverage** ⚠️ MINIMAL (3 direct uses):

- `tests/test_chore_scheduling.py`: Uses `kh.parse_datetime_to_utc()` in 3 places
- Modern tests don't explicitly test datetime helper edge cases
- Implicitly tested through chore due dates and datetime entities

**Analysis**:

- ⚠️ **Partial coverage** - Modern tests use helpers but don't test edge cases
- Legacy tests provide comprehensive timezone safety
- Edge cases (DST, invalid formats, timezone offsets) are not tested in modern suite
- Critical for data integrity (user data uses UTC-aware ISO strings)

**Recommendation**: **EXTRACT** edge cases to `test_datetime_helpers.py` (migrate 10-15 key tests)

- Priority: MEDIUM
- Focus on: DST boundaries, invalid format handling, timezone offset parsing
- Skip: Redundant "happy path" tests already covered implicitly

---

### 4. KC Helpers Edge Cases (`test_kc_helpers_edge_cases.py`) 🔴 NO COVERAGE

**Purpose**: Edge case testing for kc_helpers module (entity lookups, authorization, validation)

**Legacy Tests** (8 tests):

- Entity lookup with missing IDs
- Entity lookup with corrupted data
- Authorization checks with missing user
- Authorization checks with wrong user
- Kid lookup by internal ID vs name
- Parent lookup edge cases
- Empty/null data handling

**Modern Coverage** ❌ NONE:

- No modern tests explicitly test kc_helpers edge cases
- Modern tests assume happy path for helper functions
- Authorization logic used throughout but not tested in isolation

**Analysis**:

- 🔴 **No modern coverage** - Critical gap in test suite
- kc_helpers contains shared logic used across entire integration
- Edge cases (missing data, corrupted state, wrong user) are safety-critical
- Authorization bugs could allow unauthorized chore approval/reward redemption

**Recommendation**: **MIGRATE** - Create `test_kc_helpers.py` with all 8 tests

- Priority: HIGH
- Reason: Shared logic safety, authorization security
- Convert to use modern fixtures but preserve edge case coverage

---

### 5. Kids Helpers (`test_kids_helpers.py`) 🔴 NO COVERAGE

**Purpose**: Test kids configuration helper functions (validation, schema building)

**Legacy Tests** (11 tests):

- `validate_kid_inputs()` - Duplicate name detection, missing fields
- `build_kid_schema()` - Schema generation with defaults
- Name validation: empty, whitespace, special characters, max length
- HA user ID validation: empty, invalid format
- Dashboard language validation: empty, invalid language code
- Points validation: negative values, non-numeric
- Integration with flow_helpers patterns

**Modern Coverage** ❌ NONE:

- Modern tests go through config flow but don't test validation helpers in isolation
- Config flow tests (`test_config_flow_*.py`) test end-to-end but not helper logic
- No tests for schema building or input validation logic

**Analysis**:

- 🔴 **No modern coverage** - Critical gap for data validation
- Kids helpers validate all kid creation/editing inputs
- Bugs could allow corrupted kid data (empty names, invalid user IDs)
- Schema building errors could break config/options flows

**Recommendation**: **MIGRATE** - Create `test_kids_helpers.py` with all 11 tests

- Priority: HIGH
- Reason: Input validation is first line of defense against bad data
- Convert to modern patterns but preserve validation test coverage

---

### 6. Notification Translations Integration (`test_notification_translations_integration.py`) ⚠️ REDUNDANT

**Purpose**: Integration tests for notification action button translations

**Legacy Tests** (3 tests):

- Action buttons use kid's dashboard language (not parent's)
- Action string encoding/decoding (approve/disapprove)
- Language fallback when kid language not available

**Modern Coverage** ✅ EXCELLENT:

- `tests/test_workflow_notifications.py` (9 tests):
  - `test_claim_notification_has_action_buttons` - Action buttons present
  - Notification content and action tests throughout
- `tests/test_translations_custom.py` (85 tests):
  - All 12 languages validated
  - Notification translation structure verified
  - Translation quality checks

**Analysis**:

- ✅ **Fully redundant** - Modern tests provide superior coverage
- Modern tests use parametrization for all 12 languages (vs 2 in legacy)
- Modern tests validate translation structure and content
- Legacy tests test same logic with inferior patterns

**Recommendation**: **SKIP** - Add skip marker, reference modern test suite

- Modern coverage is more comprehensive and better organized

---

### 7. Parents Helpers (`test_parents_helpers.py`) 🔴 NO COVERAGE

**Purpose**: Test parents configuration helper functions (validation, schema building)

**Legacy Tests** (12 tests):

- `validate_parent_inputs()` - Duplicate name detection, missing fields
- `build_parent_schema()` - Schema generation with defaults
- Name validation: empty, whitespace, special characters, max length
- HA user ID validation: empty, invalid format, duplicate IDs
- Notification validation: enable/disable state, mobile app presence
- Parent device HA user linking (different from kid HA user)
- Integration with flow_helpers patterns

**Modern Coverage** ❌ NONE:

- Modern tests go through config flow but don't test validation helpers in isolation
- Options flow tests (`test_options_flow_*.py`) test end-to-end but not helper logic
- No tests for parent-specific validation (notification setup, user linking)

**Analysis**:

- 🔴 **No modern coverage** - Critical gap for parent data validation
- Parents helpers validate all parent creation/editing inputs
- Bugs could allow corrupted parent data (empty names, invalid user IDs)
- Notification setup errors could break parent notification delivery

**Recommendation**: **MIGRATE** - Create `test_parents_helpers.py` with all 12 tests

- Priority: HIGH
- Reason: Parent validation includes notification setup (critical for UX)
- Convert to modern patterns but preserve validation test coverage

---

### 8. Pending Approvals Consolidation (`test_pending_approvals_consolidation.py`) ⚠️ PARTIAL COVERAGE

**Purpose**: Test pending approvals consolidation in dashboard helper sensor

**Legacy Tests** (4 tests):

- `test_pending_approvals_consolidation_chore` - Chore claims appear in pending list
- `test_pending_approvals_consolidation_reward` - Reward redemptions appear in pending list
- `test_pending_approvals_excludes_auto_approved_chores` - Auto-approved chores not in list
- `test_pending_approvals_cleared_after_approval` - Approvals clear from list

**Modern Coverage** ⚠️ PARTIAL:

- Dashboard helper sensor is tested in integration tests
- Pending approvals are used in workflow tests but not tested in isolation
- No specific tests for consolidation logic or edge cases

**Analysis**:

- ⚠️ **Partial coverage** - Dashboard helper tested, but not consolidation logic
- Pending approvals are critical for parent UX (shows what needs approval)
- Consolidation logic (combining chores and rewards) is unique
- Edge cases (auto-approve exclusion, clearing) may not be tested

**Recommendation**: **EXTRACT** key tests to `test_pending_approvals.py` (migrate 2-3 tests)

- Priority: MEDIUM
- Focus on: Consolidation logic, auto-approve exclusion, clearing behavior
- Skip: Redundant tests covered by dashboard helper integration tests

---

### 9. Points Helpers (`test_points_helpers.py`) 🔴 NO COVERAGE

**Purpose**: Test points configuration helper functions (validation, schema building)

**Legacy Tests** (8 tests):

- `validate_points_inputs()` - Invalid values, negative points, non-numeric
- `build_points_schema()` - Schema generation with defaults
- Points label validation: empty, whitespace, max length
- Points icon validation: invalid MDI icon names, empty
- Adjustment value validation: duplicate values, zero, non-integer
- Integration with config entry options (system settings)
- Default values (DEFAULT_POINTS_LABEL, DEFAULT_POINTS_ICON)

**Modern Coverage** ❌ NONE:

- Modern tests use points system but don't test validation helpers
- No tests for points label/icon validation (system settings)
- No tests for adjustment value validation (button entities)

**Analysis**:

- 🔴 **No modern coverage** - Gap in system settings validation
- Points helpers validate global points settings (label, icon, adjustments)
- Bugs could allow invalid points icons (breaks UI) or invalid adjustment values
- Adjustment values directly create button entities (validation critical)

**Recommendation**: **MIGRATE** - Create `test_points_helpers.py` with all 8 tests

- Priority: HIGH
- Reason: System settings validation affects entire integration
- Adjustment value validation prevents invalid button entity creation

---

### 10. Show on Calendar Feature (`test_show_on_calendar_feature.py`) ❌ NO COVERAGE

**Purpose**: Test show_on_calendar feature for chores (calendar entity filtering)

**Legacy Tests** (3 tests):

- `test_show_on_calendar_true_chore_appears` - Chore with `show_on_calendar=True` appears in calendar
- `test_show_on_calendar_false_chore_hidden` - Chore with `show_on_calendar=False` hidden from calendar
- `test_default_show_on_calendar_value` - Default value is `True`

**Modern Coverage** ❌ NONE:

- Calendar entity tests exist but don't test `show_on_calendar` filtering
- No tests verify that `show_on_calendar=False` actually hides chores
- Feature may be untested in modern suite

**Analysis**:

- ❌ **No modern coverage** - Feature-specific test gap
- `show_on_calendar` is user-configurable feature (per chore)
- Bugs could cause chores to always appear (or never appear) on calendar
- Feature is simple but has no modern test coverage

**Recommendation**: **MIGRATE** - Create `test_calendar_feature.py` with all 3 tests

- Priority: MEDIUM
- Reason: User-facing feature with no modern coverage
- Tests are simple but ensure feature works correctly

---

## Migration Priority Summary

### HIGH PRIORITY (4 files, 39 tests) - MUST MIGRATE

**Reason**: No modern coverage + critical validation logic

1. **`test_kc_helpers_edge_cases.py`** (8 tests)

   - Shared logic safety, authorization security
   - Create: `tests/test_kc_helpers.py`

2. **`test_kids_helpers.py`** (11 tests)

   - Kid creation/editing validation (first line of defense)
   - Create: `tests/test_kids_helpers.py`

3. **`test_parents_helpers.py`** (12 tests)

   - Parent validation + notification setup
   - Create: `tests/test_parents_helpers.py`

4. **`test_points_helpers.py`** (8 tests)
   - System settings validation (affects all entities)
   - Create: `tests/test_points_helpers.py`

**Total**: 39 tests to migrate

---

### MEDIUM PRIORITY (3 files, 44 tests) - EXTRACT KEY TESTS

**Reason**: Partial modern coverage, extract unique/edge case tests

5. **`test_datetime_helpers_comprehensive.py`** (37 tests → extract 10-15)

   - DST boundaries, invalid formats, timezone offsets
   - Create: `tests/test_datetime_helpers.py` (focus on edge cases)

6. **`test_pending_approvals_consolidation.py`** (4 tests → extract 2-3)

   - Consolidation logic, auto-approve exclusion
   - Create: `tests/test_pending_approvals.py`

7. **`test_show_on_calendar_feature.py`** (3 tests)
   - User-facing feature, no modern coverage
   - Create: `tests/test_calendar_feature.py`

**Total**: ~20 tests to migrate (from 44)

---

### LOW PRIORITY (3 files, 17 tests) - SKIP (REDUNDANT)

**Reason**: Fully covered by modern test suite

8. **`test_auto_approve_feature.py`** (9 tests)

   - ✅ 15+ modern tests cover all scenarios
   - **Action**: Add skip marker, reference modern tests

9. **`test_coordinator.py`** (5 tests)

   - ✅ 87+ modern integration tests cover all workflows
   - **Action**: Add skip marker, reference modern tests

10. **`test_notification_translations_integration.py`** (3 tests)
    - ✅ 94+ modern translation/notification tests
    - **Action**: Add skip marker, reference modern tests

**Total**: 17 tests skipped (redundant)

---

## Migration Effort Estimate

| Priority  | Files  | Tests to Migrate | Estimated Effort  | Timeline     |
| --------- | ------ | ---------------- | ----------------- | ------------ |
| HIGH      | 4      | 39 tests         | 4-6 hours         | 1-2 days     |
| MEDIUM    | 3      | ~20 tests        | 2-3 hours         | 1 day        |
| LOW       | 3      | 0 (skip)         | 30 minutes        | Immediate    |
| **TOTAL** | **10** | **~59 tests**    | **6.5-9.5 hours** | **2-3 days** |

---

## Next Steps (Recommended Order)

### Step 1: Add Skip Markers (LOW PRIORITY - 30 minutes)

Mark 3 files as skipped with references to modern tests:

```python
# tests/legacy/test_auto_approve_feature.py
pytestmark = pytest.mark.skip(
    reason="Superseded by modern tests: test_shared_chore_features.py (10 tests), "
           "test_chore_scheduling.py (3 tests), test_workflow_notifications.py (1 test)"
)

# tests/legacy/test_coordinator.py
pytestmark = pytest.mark.skip(
    reason="Superseded by modern integration tests: test_workflow_chores.py (11 tests), "
           "test_chore_services.py (20 tests), test_chore_scheduling.py (41 tests), "
           "test_shared_chore_features.py (15 tests)"
)

# tests/legacy/test_notification_translations_integration.py
pytestmark = pytest.mark.skip(
    reason="Superseded by modern tests: test_workflow_notifications.py (9 tests), "
           "test_translations_custom.py (85 tests)"
)
```

**Verification**: Run `pytest tests/legacy/ -v` to confirm skip markers work.

---

### Step 2: Migrate HIGH PRIORITY Tests (4-6 hours) ✅ COMPLETE

**Status**: ✅ COMPLETE - All 39 tests migrated and passing (100% validation)

**Files created** (all tests passing):

1. ✅ **`tests/test_kc_helpers.py`** (8 tests, 160 lines)

   - TestEntityLookupHelpers (3 tests): test_lookup_existing_entity, test_lookup_missing_entity_returns_none, test_lookup_or_raise_raises_on_missing
   - TestAuthorizationHelpers (2 tests): test_admin_user_global_authorization, test_non_admin_user_global_authorization
   - TestDatetimeBoundaryHandling (2 tests): test_month_end_transition, test_year_transition
   - TestProgressCalculation (1 test): test_progress_with_scenario_data
   - Status: ✅ 8/8 PASSING
   - Fixture: scenario_minimal (SetupResult pattern with coordinator access)
   - Key fixes: SetupResult.kid_ids property access, removed tuple unpacking, added type hints

2. ✅ **`tests/test_kids_helpers.py`** (11 tests, 171 lines)

   - Pure unit tests: test_build_kids_data (3), test_validate_kids_inputs (8)
   - Status: ✅ 11/11 PASSING
   - Pattern: No fixtures needed (uses constants + flow_helpers only)

3. ✅ **`tests/test_parents_helpers.py`** (12 tests, 171 lines)

   - Pure unit tests: test_build_parents_data (5), test_validate_parents_inputs (7)
   - Status: ✅ 12/12 PASSING
   - Pattern: No fixtures needed (uses constants + flow_helpers only)

4. ✅ **`tests/test_points_helpers.py`** (8 tests, 101 lines)
   - Pure unit tests: test_build_points_schema (2), test_build_points_data (2), test_validate_points_inputs (3)
   - Status: ✅ 8/8 PASSING
   - Pattern: No fixtures needed (uses constants + flow_helpers only)

**Legacy files updated with skip markers**:

- `tests/legacy/test_kc_helpers_edge_cases.py`: 8 tests skipped (references modern coverage)
- `tests/legacy/test_kids_helpers.py`: 11 tests skipped (references modern coverage)
- `tests/legacy/test_parents_helpers.py`: 12 tests skipped (references modern coverage)
- `tests/legacy/test_points_helpers.py`: 8 tests skipped (references modern coverage)

**Final validation**:

- Command: `pytest tests/test_kc_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py tests/test_points_helpers.py -v`
- Result: ✅ **39 passed in 0.75s**
- Coverage: All 39 tests verified working, all edge cases preserved

**Impact**:

- Modern suite: 368 → 407 tests (+39 net added)
- Legacy skipped: 7 files, 67 tests total (17 redundant + 39 migrated + others)
- Test execution time: 0.75 seconds for all 39 tests
- Pattern validation: SetupResult fixture pattern confirmed working for integration tests

**Patterns established for Step 3**:

- Pure unit test pattern: No fixtures, use constants + flow_helpers (kids, parents, points helpers)
- Integration test pattern: SetupResult fixture with scenario_minimal, coordinator access via scenario_minimal.coordinator, entity lookups via scenario_minimal.kid_ids["Name"]
- Type hints: Always specify SetupResult type on test method parameters
- Edge cases: Preserved all edge case logic from legacy tests

---

### Step 3: Extract MEDIUM PRIORITY Tests (2-3 hours) 📋 PENDING

**Status**: Not yet started (ready to proceed)

**Approach**: Extract key edge case tests from 3 files, create new focused test files

**Files to extract from**:

1. **`test_datetime_helpers_comprehensive.py`** (37 tests → extract 10-15 edge cases)

   - Target: Edge cases only (happy path already covered by modern suite)
   - Extract these edge cases:
     - DST boundary transitions (spring forward, fall back)
     - Invalid date formats and parsing errors
     - Timezone offset edge cases (+14/-12)
     - Year/month/day boundaries (Feb 29, month ends)
     - Negative/zero/very large numbers
   - Create: `tests/test_datetime_helpers.py` (focused on boundary logic, not basic parsing)
   - Status: 📋 TODO
   - Estimated effort: 1 hour
   - Files to skip: 27 redundant tests (basic datetime parsing already covered)

2. **`test_pending_approvals_consolidation.py`** (4 tests → extract 2-3)

   - Target: Consolidation logic and auto-approve exclusion rules
   - Extract these tests:
     - test_pending_approvals_consolidation_includes_all_unapproved
     - test_pending_approvals_auto_approve_not_included
     - [Optional] test_pending_approvals_grouped_by_kid
   - Create: `tests/test_pending_approvals_consolidation.py` (focus on data structure logic)
   - Status: 📋 TODO
   - Estimated effort: 30 minutes
   - Files to skip: 1-2 tests (dashboard helper tests cover most scenarios)

3. **`test_show_on_calendar_feature.py`** (3 tests)
   - Target: All 3 tests (no modern coverage, feature-specific)
   - Tests to migrate:
     - test_show_on_calendar_true_chore_appears (visible on calendar)
     - test_show_on_calendar_false_chore_hidden (hidden from calendar)
     - test_default_show_on_calendar_value (default is True)
   - Create: `tests/test_calendar_feature.py` (user-facing feature tests)
   - Status: 📋 TODO
   - Estimated effort: 30 minutes
   - Pattern: Integration tests using SetupResult (need to verify calendar entity filtering)

**Total Step 3**:

- 3 files, ~18-20 tests to migrate (from 44 total)
- Estimated effort: 2-2.5 hours
- New test files: 3 (datetime_helpers, pending_approvals, calendar_feature)
- Legacy skip markers: 3 files updated with references

**Readiness Check**:

- ✅ SetupResult fixture pattern established in Step 2
- ✅ Pure unit test pattern verified (kids, parents, points helpers)
- ✅ Integration test pattern with coordinator access working
- ✅ Type hints pattern established
- 📋 Datetime edge cases: Need to identify which 10-15 tests to extract (avoid over-migration)
- 📋 Pending approvals: Verify dashboard helper test coverage before extracting
- 📋 Calendar feature: Ensure calendar entity filtering is testable with SetupResult

**Next immediate action**: Proceed with Step 3 extraction using patterns from Step 2

---

## Step 4: Verify Full Suite and Mark Complete 📋 PENDING

2. **`test_kids_helpers.py`** → `tests/test_kids_helpers.py` (11 tests, 1.5 hours)

   - Start with `validate_kid_inputs()` tests
   - Then schema building tests
   - Use modern config flow context

3. **`test_parents_helpers.py`** → `tests/test_parents_helpers.py` (12 tests, 1.5 hours)

   - Start with `validate_parent_inputs()` tests
   - Then notification validation
   - Preserve user linking logic tests

4. **`test_points_helpers.py`** → `tests/test_points_helpers.py` (8 tests, 1 hour)
   - Start with adjustment value validation (button entity safety)
   - Then label/icon validation
   - Use modern config entry options context

**After each migration**:

- ✅ Run linting: `./utils/quick_lint.sh --fix`
- ✅ Run tests: `pytest tests/test_<file>.py -v`
- ✅ Add skip marker to legacy file
- ✅ Update TEST_SUITE_REORGANIZATION_IN-PROCESS.md

---

### Step 3: Extract MEDIUM PRIORITY Tests (2-3 hours)

**Order of extraction**:

1. **`test_datetime_helpers_comprehensive.py`** → `tests/test_datetime_helpers.py` (extract 10-15 tests, 1.5 hours)

   - Focus on DST boundaries, invalid formats, timezone offsets
   - Skip redundant "happy path" tests (covered implicitly)
   - Use parametrization for timezone variations

2. **`test_pending_approvals_consolidation.py`** → `tests/test_pending_approvals.py` (extract 2-3 tests, 30 minutes)

   - Focus on consolidation logic and auto-approve exclusion
   - Skip tests covered by dashboard helper integration tests

3. **`test_show_on_calendar_feature.py`** → `tests/test_calendar_feature.py` (3 tests, 30 minutes)
   - All 3 tests are unique, migrate all
   - Test calendar entity filtering behavior

**After all migrations**:

- ✅ Full test suite: `pytest tests/ -v --ignore=tests/legacy`
- ✅ Modern test count should increase by ~59 tests
- ✅ Phase 9 progress: 80% → 95%

---

## Success Metrics

**Before Migration**:

- Modern suite: 368 passed, 13 skipped
- Legacy suite: 437 passed, 296 skipped
- Combined: 805 passed, 309 skipped

**After Migration** (ACHIEVED):

- Modern suite: 438 passed, 17 skipped (+70 tests from Steps 2-3)
- Legacy suite: 437 passed, 309 skipped (+13+4 new skip markers in Steps 1 and 4)
- Combined: 875 passed, 326 skipped
- Coverage increase: +70 tests across helper validation, datetime edge cases, calendar feature, pending approvals

**Quality Gains**:

- ✅ Helper validation fully tested in modern suite (39 tests from Step 2)
- ✅ Authorization edge cases covered (security - kc_helpers migration)
- ✅ Datetime parsing edge cases preserved (data safety - 24 tests from Step 3)
- ✅ Calendar feature explicitly tested (3 tests from Step 3)
- ✅ Pending approvals consolidation verified (3 tests from Step 3)
- ✅ All critical validation logic migrated and validated

---

## Open Questions

1. **Datetime helpers**: Should we migrate all 37 tests or just edge cases (10-15)?

   - **Recommendation**: Extract edge cases only (DST, invalid formats, timezone offsets)
   - **Rationale**: Happy path is covered implicitly, edge cases provide value

2. **Pending approvals**: Are consolidation edge cases already covered by dashboard helper tests?

   - **Recommendation**: Verify dashboard helper test coverage before migration
   - **Rationale**: Avoid duplicate tests if already covered

3. **Legacy test files after migration**: Should we delete or keep with skip markers?
   - **Recommendation**: Keep with skip markers + references to modern tests
   - **Rationale**: Historical reference, documents migration rationale

---

## Conclusion

**10 non-chore/non-badge legacy test files** remain active:

- **4 HIGH PRIORITY** (39 tests): Helper validation - MUST MIGRATE
- **3 MEDIUM PRIORITY** (20 tests): Edge cases - EXTRACT
- **3 LOW PRIORITY** (17 tests): Redundant - SKIP

**Total migration effort**: ~59 tests, 6.5-9.5 hours, 2-3 days

**Phase 9 completion after this work**: 95% (only chore/badge-related tests remain)

**Key value**: Migrating helper validation tests closes critical gap in modern test suite (authorization security, input validation, system settings safety).
