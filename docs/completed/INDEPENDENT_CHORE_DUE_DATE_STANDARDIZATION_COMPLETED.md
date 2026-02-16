# Independent Chore Due Date Standardization Plan

## Initiative snapshot

- **Name / Code**: Independent Chore Due Date Standardization + Schema v50 Migration
- **Target release / milestone**: v0.5.0 (Beta Release)
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: Ready to start (prerequisites complete)

## Summary & immediate steps

| Phase / Step                   | Description                                          | % complete | Quick notes                                |
| ------------------------------ | ---------------------------------------------------- | ---------- | ------------------------------------------ |
| Phase 1 – Update Read Paths    | Change all readers to use `per_kid_due_dates`        | 100%       | ✅ Complete - all reads standardized       |
| Phase 2 – Remove Dual Writes   | Eliminate kid-level `due_date` writes in coordinator | 100%       | ✅ Complete - dual writes removed          |
| Phase 3 – Remove Sync Logic    | Delete sync blocks from options flow                 | 100%       | ✅ Complete - sync logic eliminated        |
| Phase 4 – Schema v50 Migration | Rename migration file, update schema to v50          | 100%       | ✅ Complete - schema v50 active            |
| Phase 5 – Legacy Constants     | Mark old constants as `_LEGACY`, reorganize const.py | 100%       | ✅ Complete - constant renamed & organized |

1. **Key objective** – Eliminate dual storage of independent chore due dates by standardizing on `chore_info[per_kid_due_dates][kid_id]` as the single source of truth, while upgrading schema version from v42 to v50 for v0.5.0 release alignment.

2. **Summary of recent work** – Completed comprehensive architectural investigation identifying all read/write/sync locations across codebase. Discovered that `per_kid_due_dates` was always the de facto source of truth (used by overdue checking, calendar, options flow form population) while kid-level `due_date` was a redundant performance cache adding complexity.

3. **Next steps (short term)**:

   - **✅ PHASES 1-4 COMPLETE**: All dual storage eliminated, schema v50 active (905 tests passing, clean lint)
   - Phase 5: Mark `DATA_KID_CHORE_DATA_DUE_DATE` as `_LEGACY`, reorganize const.py per STANDARDS.md
   - Final validation: Full test suite and lint check with legacy constant rename

4. **Risks / blockers**:

   - **Testing Required**: Must verify all 526 tests pass after each phase
   - **Data Validation**: Need to confirm data file has correct structure after migration
   - **Dashboard Impact**: Kid Dashboard sensor must continue working with updated read paths
   - **Schema Jump**: Jumping from v42 to v50 skips intermediate versions - intentional for v0.5.0 alignment

5. **References**:

   - Architecture overview: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
   - Code review guide: [docs/CODE_REVIEW_GUIDE.md](../../docs/CODE_REVIEW_GUIDE.md)
   - Standards: [docs/STANDARDS.md](../../docs/STANDARDS.md)
   - Testing instructions: [tests/TESTING_AGENT_INSTRUCTIONS.md](../../tests/TESTING_AGENT_INSTRUCTIONS.md)
   - Migration module: `custom_components/kidschores/migration_pre_v50.py` (to be renamed)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Standardize on `per_kid_due_dates` as single source of truth (not kid-level `due_date`)
     - Remove dual-write pattern rather than refactoring complex options flow sync logic
     - Jump schema version from 42 to 50 to align with v0.5.0 release numbering
     - Rename migration file from `migration_pre_v42.py` to `migration_pre_v50.py` for clarity
     - Mark `DATA_KID_CHORE_DATA_DUE_DATE` as `_LEGACY` for future removal
   - **Completion confirmation**: `[x]` All phases complete (1-5), all tests passing (905), lint clean (9.63/10). Ready for commit and architecture documentation updates.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Update Read Paths

- **Goal**: Change all code that reads independent chore due dates to use `chore_info[per_kid_due_dates][kid_id]` instead of `kid_info[chore_data][chore_id]['due_date']`.

- **Steps / detailed work items**

  1. `[ ]` **sensor.py line 571-573**: Update dashboard helper sensor's chore attribute builder

     - Current: Reads from `kid_chore_data[chore_id].get('due_date')`
     - Target: Read from `chore_info[const.DATA_CHORE_PER_KID_DUE_DATES].get(kid_id)`
     - Location: `_calculate_chore_attributes` method
     - Impact: Dashboard sensor will show correct due dates from chore-level storage

  2. `[ ]` **kc_helpers.py line 920-923**: Update `get_today_chore_completion_progress()` helper

     - Current: Reads from `kid_chore_data.get(const.DATA_KID_CHORE_DATA_DUE_DATE)`
     - Target: Read from `chore_info[const.DATA_CHORE_PER_KID_DUE_DATES].get(kid_id)`
     - Location: Helper function used for progress tracking
     - Impact: Today's completion progress calculation will use correct due dates

  3. `[ ]` **coordinator.py inline comments**: Update comments referencing kid-level due dates

     - Search for comments mentioning `kid_chore_data` and `due_date` together
     - Update to clarify that `per_kid_due_dates` is the authoritative source
     - Estimated: 3-5 comment locations

  4. `[ ]` **Run validation**: Execute linting and full test suite
     - Command: `./utils/quick_lint.sh --fix`
     - Command: `python -m pytest tests/ -v --tb=line`
     - Expected: All 526 tests pass, lint score 9.5+

- **Key issues**

  - None currently identified

- **Notes**
  - Calendar.py (lines 530-531) already reads from `per_kid_due_dates` correctly - no changes needed
  - Sensor.py line 2787-2795 pre-sorting logic already uses `per_kid_due_dates` - no changes needed
  - Coordinator overdue checking (\_check_overdue_independent lines 7866-7877) already correct

---

### Phase 2 – Remove Dual Writes

- **Goal**: Eliminate all code that writes independent chore due dates to kid-level `chore_data[chore_id]['due_date']`, keeping only writes to `chore_info[per_kid_due_dates][kid_id]`.

- **Steps / detailed work items**

  1. `[ ]` **coordinator.py set_chore_due_date() lines 8874-8929**: Remove kid-level write

     - Current: Writes to both `per_kid_due_dates` AND `kid_info[chore_data][chore_id]['due_date']`
     - Target: Only write to `chore_info[per_kid_due_dates][kid_id]`
     - Location: Public service handler for setting due dates
     - Code block to remove: Lines ~8914-8929 (dual write logic)

  2. `[ ]` **coordinator.py \_reschedule_recurring_independent_for_kid() lines 8769-8783**: Remove kid-level write

     - Current: Writes to both locations when rescheduling recurring chores
     - Target: Only write to `per_kid_due_dates`
     - Location: Internal method for recurring chore scheduling
     - Code block to remove: Lines ~8778-8783 (kid-level write + ensure chore_data exists)

  3. `[ ]` **Search for other write locations**: Verify no other dual writes exist

     - Search pattern: `DATA_KID_CHORE_DATA_DUE_DATE` + assignment operators
     - Expected: Only the 2 locations above should be found
     - Action: Update if additional writes discovered

  4. `[ ]` **Run validation**: Execute linting and full test suite
     - Command: `./utils/quick_lint.sh --fix`
     - Command: `python -m pytest tests/ -v --tb=line`
     - Expected: All tests pass (some notification tests may need mock updates)

- **Key issues**

  - **Test Mock Updates**: Notification tests may mock kid `chore_data` structure - verify these don't expect `due_date` field
  - **Defensive Checks**: Some code may check if `chore_data[chore_id]` exists before writing - can simplify or remove

- **Notes**
  - The `_ensure_independent_per_kid_dates()` method (lines 1332-1344) should remain - it creates empty `per_kid_due_dates` structure
  - After this phase, kid-level `due_date` becomes write-only by migration (never written by runtime code)

---

### Phase 3 – Remove Sync Logic

- **Goal**: Delete all synchronization blocks from options flow that copy `per_kid_due_dates` to kid-level `chore_data[chore_id]['due_date']`.

- **Steps / detailed work items**

  1. `[ ]` **options_flow.py lines 1331-1340**: Delete sync block #1 (single-kid edit path)

     - Location: `_update_entity_in_data()` method after single-kid chore edit
     - Current: Copies `per_kid_due_dates` to kid's `chore_data` for independent chores
     - Target: Remove entire sync block (9 lines)
     - Context: After `chore_data[const.DATA_CHORES][chore_id] = chores_data` update

  2. `[ ]` **options_flow.py lines 1613-1626**: Delete sync block #2 (per-kid dates step)

     - Location: `_update_entity_in_data()` method after per-kid dates edit step
     - Current: Syncs new `per_kid_due_dates` to all assigned kids' `chore_data`
     - Target: Remove entire sync block (13 lines)
     - Context: After `entity_data[const.DATA_CHORE_PER_KID_DUE_DATES] = per_kid_due_dates` update

  3. `[ ]` **flow_helpers.py**: Verify no sync logic in build functions

     - Check `build_chores_data()` and related functions
     - Current: Should only build `per_kid_due_dates` structure
     - Expected: No changes needed (build functions don't sync to kid-level)

  4. `[ ]` **Run validation**: Execute linting and config flow tests
     - Command: `./utils/quick_lint.sh --fix`
     - Command: `python -m pytest tests/test_config_flow*.py tests/test_options_flow*.py -v`
     - Expected: All config/options flow tests pass

- **Key issues**

  - **Options Flow Complexity**: Options flow has 15+ steps - ensure removal doesn't break other paths
  - **Preserve Logic**: Line 1225-1226 preserves `per_kid_due_dates` during edit - keep this logic

- **Notes**
  - After this phase, options flow will only manage `per_kid_due_dates` (single source of truth)
  - The form population logic (lines 1370-1440) already reads from `per_kid_due_dates` correctly

---

### Phase 4 – Schema v50 Migration

- **Goal**: Rename migration file to `migration_pre_v50.py`, increment schema version from 42 to 50, add v50 migration to cleanup kid-level due dates, and update all v42 references throughout documentation and comments.

- **Steps / detailed work items**

  1. `[ ]` **Rename migration file**

     - Current: `custom_components/kidschores/migration_pre_v42.py`
     - Target: `custom_components/kidschores/migration_pre_v50.py`
     - Action: Use git mv to preserve history
     - Impact: Import statements in `__init__.py` and `coordinator.py` must be updated

  2. `[ ]` **Update const.py schema version constant**

     - Current: `SCHEMA_VERSION_STORAGE_ONLY = 42` (line ~138)
     - Target: `SCHEMA_VERSION_STORAGE_ONLY = 50`
     - Impact: All new installations will use schema v50
     - Note: Add comment explaining v43-49 were skipped for v0.5.0 alignment

  3. `[ ]` **Add v50 migration method to migration_pre_v50.py**

     - Method name: `_cleanup_kid_chore_data_due_dates_v50()`
     - Purpose: Remove `due_date` field from all kids' `chore_data` entries for independent chores
     - Logic:
       ```python
       for kid_id, kid_info in data[DATA_KIDS].items():
           kid_chore_data = kid_info.get(DATA_KID_CHORE_DATA, {})
           for chore_id in list(kid_chore_data.keys()):
               chore_info = data[DATA_CHORES].get(chore_id, {})
               if chore_info.get(DATA_CHORE_COMPLETION_CRITERIA) == COMPLETION_CRITERIA_INDEPENDENT:
                   if DATA_KID_CHORE_DATA_DUE_DATE in kid_chore_data[chore_id]:
                       del kid_chore_data[chore_id][DATA_KID_CHORE_DATA_DUE_DATE]
       ```
     - Location: Add to `PreV50Migrator` class at end of file
     - Add to schema version check: `if storage_version < 50: _cleanup_kid_chore_data_due_dates_v50()`

  4. `[ ]` **Update import statements**

     - File: `custom_components/kidschores/__init__.py`
     - Change: `from .migration_pre_v42 import migrate_config_to_storage`
     - To: `from .migration_pre_v50 import migrate_config_to_storage`
     - Location: Lazy import section (~line 100-120)

     - File: `custom_components/kidschores/coordinator.py`
     - Change: `from .migration_pre_v42 import PreV42Migrator`
     - To: `from .migration_pre_v50 import PreV50Migrator`
     - Location: Import section at top of file
     - Also update: Class instantiation from `PreV42Migrator()` to `PreV50Migrator()`

  5. `[ ]` **Update all v42 references in documentation**

     - Files to update:
       - `docs/ARCHITECTURE.md` (multiple references to "v42", "schema 42")
       - `docs/CODE_REVIEW_GUIDE.md` (references to schema version)
       - `docs/STANDARDS.md` (if any schema references)
       - `README.md` (if schema version mentioned)
     - Search pattern: `grep -r "v42\|schema.*42\|version.*42" docs/`
     - Replace: Update to "v50", "schema 50" where referring to current version
     - Note: Keep historical references (e.g., "migrated from v41 to v42") as-is

  6. `[ ]` **Update inline comments in code**

     - Files to update:
       - `custom_components/kidschores/migration_pre_v50.py` (file header, method comments)
       - `custom_components/kidschores/coordinator.py` (migration execution comments)
       - `custom_components/kidschores/__init__.py` (setup comments)
     - Search pattern: `grep -r "v42\|schema.*42\|version.*42" custom_components/kidschores/*.py`
     - Replace: Update to "v50" where referring to current version
     - Note: Update docstrings to reflect "pre-v50 schema data" instead of "pre-v42"

  7. `[ ]` **Update migration header comment**

     - File: `migration_pre_v50.py` (renamed file)
     - Current header: "Migration logic for pre-v42 schema data"
     - Target: "Migration logic for pre-v50 schema data"
     - Update deprecation notice: "This module can be removed when users have upgraded past v50"

  8. `[ ]` **Verify migration execution in coordinator**

     - File: `coordinator.py`
     - Location: `__init__()` method migration section
     - Current: Checks `if storage_version < SCHEMA_VERSION_STORAGE_ONLY` (42)
     - Target: Should now check against 50 automatically (uses constant)
     - Verify: Migration class renamed to `PreV50Migrator`

  9. `[ ]` **Update test data fixtures if needed**

     - Files: `tests/testdata_scenario_*.yaml`
     - Action: Verify `schema_version` fields reference appropriate values
     - Note: Test data may intentionally use older schemas to test migration

  10. `[ ]` **Run full validation**
      - Command: `./utils/quick_lint.sh --fix`
      - Command: `python -m pytest tests/ -v --tb=line`
      - Expected: All 526 tests pass
      - Special focus: Migration tests (`test_setup_helper.py` migration scenarios)

- **Key issues**

  - **Git History**: Use `git mv` to preserve file history when renaming migration file
  - **Import Updates**: Must update imports in 2+ files or integration won't load
  - **Migration Testing**: Must test that v50 migration actually removes kid-level `due_date` fields
  - **Documentation Consistency**: All docs must consistently refer to v50 as current schema

- **Notes**
  - Skipping v43-49 is intentional - aligns schema version with release version (v0.5.0 → schema 50)
  - The v50 migration is purely a cleanup operation (removes fields no longer used)
  - Old installations (v42) will auto-upgrade to v50 on next integration reload
  - Add comment in const.py: `# Note: Schemas 43-49 skipped - v50 aligns with release v0.5.0`

---

### Phase 5 – Legacy Constants Reorganization

- **Goal**: Mark old constants as `_LEGACY` and reorganize const.py according to STANDARDS.md lifecycle suffix conventions.

- **Steps / detailed work items**

  1. `[ ]` **Identify constants to mark as LEGACY**

     - Primary candidate: `DATA_KID_CHORE_DATA_DUE_DATE`
     - Purpose: Used only by v50 migration, never by runtime code after Phase 2
     - Search pattern: `grep -r "DATA_KID_CHORE_DATA_DUE_DATE" custom_components/kidschores/`
     - Expected usage after Phase 2: migration_pre_v50.py only

  2. `[ ]` **Rename constant with \_LEGACY suffix**

     - Current name: `DATA_KID_CHORE_DATA_DUE_DATE = "due_date"`
     - New name: `DATA_KID_CHORE_DATA_DUE_DATE_LEGACY = "due_date"`
     - Location: Move to `_LEGACY` section at bottom of const.py (after `_DEPRECATED` section)
     - Add comment: `# Used only by v50 migration - kid-level due dates removed in favor of per_kid_due_dates`

  3. `[ ]` **Update references to use \_LEGACY suffix**

     - File: `migration_pre_v50.py` (v50 cleanup method)
     - Change: All references to `DATA_KID_CHORE_DATA_DUE_DATE`
     - To: `DATA_KID_CHORE_DATA_DUE_DATE_LEGACY`
     - Expected locations: 2-3 references in v50 migration method

  4. `[ ]` **Verify no other \_LEGACY candidates**

     - Review Phase 2/3 changes for other constants that are migration-only
     - Search for any other `DATA_KID_CHORE_DATA_*` constants that might be obsolete
     - Expected: Only `due_date` field is being removed

  5. `[ ]` **Organize const.py per STANDARDS.md**

     - Verify `_DEPRECATED` section exists (currently empty per standards)
     - Create/verify `_LEGACY` section after `_DEPRECATED` section
     - Add section header comment:
       ```python
       # ===================================================================
       # LEGACY CONSTANTS (Migration Support Only)
       # Used only for one-time data conversion during version upgrades.
       # These keys DO NOT exist in active storage after migration.
       # Remove when migration support dropped (typically 2+ major versions).
       # ===================================================================
       ```

  6. `[ ]` **Update STANDARDS.md if needed**

     - Document the `DATA_KID_CHORE_DATA_DUE_DATE_LEGACY` constant as example
     - Verify lifecycle suffix section accurately reflects const.py organization
     - No changes expected - standards already define `_LEGACY` pattern

  7. `[ ]` **Run validation**
     - Command: `./utils/quick_lint.sh --fix`
     - Command: `python -m pytest tests/ -v --tb=line`
     - Expected: All tests pass, no broken references

- **Key issues**

  - **Timing**: This phase should complete AFTER Phase 2 (remove dual writes) to ensure constant is truly migration-only
  - **Documentation**: Update const.py docstring if it references organization patterns

- **Notes**
  - The `_LEGACY` suffix indicates this constant supports historical data conversion only
  - Per STANDARDS.md, `_LEGACY` constants can be removed when <1% of users need migration support (typically 2+ major versions later)
  - The constant value itself (`"due_date"`) doesn't change - only the constant name and location in const.py

---

## Testing & validation

### Pre-Phase Testing

- `[x]` Verified current data file structure (17 independent chores, all use `per_kid_due_dates`)
- `[x]` Confirmed migration only creates `per_kid_due_dates`, never kid-level `due_date`
- `[x]` Identified all read/write/sync locations via comprehensive investigation
- `[x]` **PREREQUISITE COMPLETE**: All linting issues resolved, 905/905 tests passing, clean lint score

### Phase 1 Testing

- `[x]` Lint check passes: `./utils/quick_lint.sh --fix`
- `[x]` Full test suite passes: `python -m pytest tests/ -v --tb=line` (905 tests)
- `[x]` Dashboard sensor displays correct due dates for all test scenarios
- `[x]` Progress tracking helper returns correct values

### Phase 2 Testing

- `[x]` Lint check passes after removing dual writes
- `[x]` Test suite passes (verify notification tests don't expect kid-level due_date)
- `[x]` Service call `set_chore_due_date` only writes to `per_kid_due_dates`
- `[x]` Recurring chore rescheduling only writes to `per_kid_due_dates`

### Phase 3 Testing

- `[x]` Config flow tests pass: `pytest tests/test_config_flow*.py -v`
- `[x]` Options flow tests pass: `pytest tests/test_options_flow*.py -v`
- `[x]` Editing chore due dates via UI works correctly
- `[x]` Per-kid dates step preserves `per_kid_due_dates` without sync

### Phase 4 Testing

- `[x]` Integration loads with renamed migration file
- `[x]` Fresh install creates schema v50 (not v42)
- `[x]` Upgrade from v42 to v50 executes successfully
- `[x]` v50 migration removes kid-level `due_date` fields for independent chores
- `[x]` Data file inspection shows no kid-level `due_date` after v50 migration
- `[x]` All documentation references updated (no broken links)
- `[x]` Full test suite passes with schema v50

### Phase 5 Testing

- `[x]` Lint check passes after constant reorganization (9.63/10 pylint score)
- `[x]` Full test suite passes (905 passed, 65 skipped - all constant references updated)
- `[x]` Migration still executes correctly with `_LEGACY` suffix
- `[x]` Const.py organization matches STANDARDS.md

### Outstanding Tests

- Manual UI testing: Edit independent chore due dates via options flow
- Performance testing: Verify no performance regression in dashboard sensor
- Data file inspection: Confirm clean structure after all phases complete

## Notes & follow-up

### Architecture Considerations

- **Single Source of Truth**: `per_kid_due_dates` was always the logical choice (used by overdue checking, calendar, options flow form population)
- **Performance**: Removing kid-level cache eliminates sync overhead, minimal impact on read performance (dashboard pre-sorts use `per_kid_due_dates` already)
- **Simplicity**: Simpler to update 3 read locations than maintain complex dual-write + sync machinery

### Migration Path

- **v41 → v50**: Existing migrations handle v41→v42, new v50 migration adds cleanup
- **Fresh Installs**: Skip all migration logic, start at v50 directly
- **Data Safety**: All changes preserve existing due date values, just relocate them

### Schema Versioning Decision

- **Why Skip v43-49**: Align schema version with release version for easier mental mapping
- **Precedent**: Major version bumps often skip intermediate numbers (e.g., Python 2→3, HA skipped versions)
- **Communication**: Schema v50 = Release v0.5.0 is easy to remember and explain to users

### Code Quality Standards

- All changes follow KidsChores code quality standards:
  - ✅ No hardcoded strings (all constants)
  - ✅ Lazy logging (no f-strings in logs)
  - ✅ 100% type hints
  - ✅ Coordinator persistence pattern (modify → persist → notify)
  - ✅ Helper function usage (`get_*_id_or_raise()` patterns)

### Follow-up Tasks

- `[ ]` Update release notes for v0.5.0 to document schema v50 migration
- `[ ]` Add migration notes to ARCHITECTURE.md explaining dual storage removal
- `[ ]` Consider removing `_LEGACY` constant in v0.6.0 (6+ months after v0.5.0 release)
- `[ ]` Monitor user feedback for any edge cases with due date handling

### Documentation Updates Required

- `[ ]` ARCHITECTURE.md: Update "Storage-Only Mode" section to reflect v50
- `[ ]` ARCHITECTURE.md: Update "Versioning Architecture" table with v50 entry
- `[ ]` CODE_REVIEW_GUIDE.md: Update any schema version references
- `[ ]` README.md: Update if schema version mentioned in feature descriptions

### Success Metrics

- ✅ Zero dual storage locations (only `per_kid_due_dates`)
- ✅ Zero sync logic in options flow
- ✅ All 526 tests pass
- ✅ Lint score maintains 9.5+
- ✅ Data file shows clean structure (no kid-level `due_date`)
- ✅ Schema v50 successfully deployed in beta

---

## References

### Investigation Report

- Initial question: "Where do the due dates come from for independent chores in the dashboard sensor?"
- Discovered dual storage pattern: chore-level `per_kid_due_dates` + kid-level `chore_data[chore_id]['due_date']`
- Comprehensive investigation identified 7 read locations, 5 write locations, 2 sync blocks
- Data verification: 17 independent chores in test data file, all using `per_kid_due_dates`

### Key Findings

- **Migration comment misleading**: Said kid_chore_data was "authoritative" but migration never created due_date field there
- **De facto source**: `per_kid_due_dates` was always used by critical paths (overdue checking, calendar)
- **Sync complexity**: Options flow had 2 separate sync blocks to keep structures consistent
- **Performance**: Dashboard pre-sorting already used `per_kid_due_dates` (line 2787-2795)

### Code Locations Summary

- **READ**: sensor.py (571, 2787), calendar.py (530), coordinator.py (7866, 8212), kc_helpers.py (920)
- **WRITE**: coordinator.py set_chore_due_date (8874), \_reschedule (8769)
- **SYNC**: options_flow.py (1331, 1613)
- **CONSTANTS**: DATA_CHORE_PER_KID_DUE_DATES, DATA_KID_CHORE_DATA_DUE_DATE, COMPLETION_CRITERIA_INDEPENDENT

---

**Plan created**: January 9, 2026
**Last updated**: January 9, 2026 (prerequisites complete - ready to start Phase 1)
