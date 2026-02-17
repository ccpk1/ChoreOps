# Testing Documentation Migration Plan

**Date**: January 10, 2026  
**Objective**: Migrate relevant test documentation from `tests/legacy/` to `tests/` while archiving or consolidating outdated content.

**Current State**: 
- Primary docs: `tests/legacy/` (11 markdown files)
- Modern docs: `tests/` (1 markdown file)
- Test files: Split between `tests/legacy/` (~70 files) and `tests/` (~15 files)

---

## 📋 Documentation Inventory & Analysis

### Markdown Files in tests/legacy/

| File | Purpose | Size | Priority | Status | Action |
|------|---------|------|----------|--------|--------|
| **README.md** | Overview of test suite & Stårblüm family | 408 lines | HIGH | ✅ Core | ➡️ **MOVE** to tests/ (update links) |
| **TESTING_AGENT_INSTRUCTIONS.md** | Quick guide for AI agents/automation | 227 lines | HIGH | ✅ Current | ➡️ **MOVE** to tests/ |
| **TESTING_GUIDE.md** | Comprehensive technical guide | 1524 lines | CRITICAL | ✅ Master | ➡️ **MOVE** to tests/ (primary reference) |
| **TEST_CREATION_TEMPLATE.md** | Template for writing new tests | 156 lines | HIGH | ✅ Active | ➡️ **MOVE** to tests/ |
| **TEST_FIXTURE_GUIDE.md** | Complete conftest.py helper reference | 412 lines | HIGH | ✅ Active | ➡️ **MOVE** to tests/ |
| **TEST_SCENARIOS.md** | Scenario fixture documentation | 298 lines | HIGH | ✅ Active | ➡️ **MOVE** to tests/ |
| **TESTDATA_CATALOG.md** | Complete testdata yaml reference | 287 lines | MEDIUM | ⚠️ Dated | ➡️ **CONSOLIDATE** (merge into TESTDATA_SCENARIOS.md) |
| **SCENARIO_FULL_COVERAGE.md** | Full scenario details & entity mapping | 156 lines | MEDIUM | ⚠️ Legacy | ➡️ **CONSOLIDATE** (merge into TEST_SCENARIOS.md) |
| **TESTING_LEGACY_GUIDE.md** | _If exists_ | ? | LOW | ⏭️ Skip | ➡️ **ARCHIVE** |

**Currently in tests/ (modern):**
- `AGENT_TEST_CREATION_INSTRUCTIONS.md` (94 lines) - Duplicate of TESTING_AGENT_INSTRUCTIONS.md in legacy

---

## 📊 Documentation Dependency Map

```
TESTING_GUIDE.md (PRIMARY REFERENCE)
├── References: TEST_FIXTURE_GUIDE.md (conftest helpers)
├── References: TEST_SCENARIOS.md (fixture usage)
├── References: TEST_CREATION_TEMPLATE.md (patterns)
└── References: TESTDATA_CATALOG.md (yaml format)

TESTING_AGENT_INSTRUCTIONS.md (QUICK START)
├── References: TESTING_GUIDE.md (detailed guidance)
└── References: TEST_CREATION_TEMPLATE.md (patterns)

README.md (OVERVIEW)
├── Introduces: Stårblüm family
└── References: All other docs

TEST_FIXTURES.md, TEST_SCENARIOS.md, TESTDATA_CATALOG.md
└── Form interconnected reference library
```

---

## 🎯 Migration Strategy

### Phase 1: MOVE Files (Core Documentation)
**Action**: Copy to tests/, update all internal links

**Files to MOVE:**
1. ✅ `README.md` → `tests/README.md` (update cross-references)
2. ✅ `TESTING_GUIDE.md` → `tests/TESTING_GUIDE.md` (master reference)
3. ✅ `TESTING_AGENT_INSTRUCTIONS.md` → `tests/TESTING_AGENT_INSTRUCTIONS.md` (agent quick-start)
4. ✅ `TEST_CREATION_TEMPLATE.md` → `tests/TEST_CREATION_TEMPLATE.md` (patterns)
5. ✅ `TEST_FIXTURE_GUIDE.md` → `tests/TEST_FIXTURE_GUIDE.md` (conftest reference)
6. ✅ `TEST_SCENARIOS.md` → `tests/TEST_SCENARIOS.md` (fixture scenarios)

**Why MOVE (not copy)?** 
- Consolidates all test documentation in single location
- Reduces confusion about "which version is current"
- Single source of truth for contributors

**Action post-move:**
- Delete from `tests/legacy/`
- Update all references in code/docs
- Ensure copilot instructions point to new location

---

### Phase 2: CONSOLIDATE Files (Redundant Content)
**Action**: Merge overlapping content into primary docs, archive source

**Files to CONSOLIDATE:**

#### 2.1 `TESTDATA_CATALOG.md` → `TEST_SCENARIOS.md`
**Problem**: Duplicate coverage of testdata yaml files
- TESTDATA_CATALOG: Lists all yaml files (287 lines)
- TEST_SCENARIOS: Explains scenario fixtures & usage (298 lines)

**Solution**: 
- Keep TEST_SCENARIOS.md as primary
- Add TESTDATA_CATALOG content as "Appendix: YAML File Reference"
- Include entity counts, field descriptions, usage examples
- Archive original TESTDATA_CATALOG.md

#### 2.2 `SCENARIO_FULL_COVERAGE.md` → `TEST_SCENARIOS.md`
**Problem**: Duplicate scenario documentation
- SCENARIO_FULL_COVERAGE: Detailed entity mapping (156 lines)
- TEST_SCENARIOS: Overview of all scenarios (298 lines)

**Solution**:
- Merge SCENARIO_FULL_COVERAGE entity tables into TEST_SCENARIOS.md "Full Scenario Reference"
- Archive original SCENARIO_FULL_COVERAGE.md

---

### Phase 3: ARCHIVE Files (Historical Reference)
**Action**: Move to `tests/legacy/archive/` for reference, document deprecation

**Files to ARCHIVE:**
- TESTDATA_CATALOG.md (consolidated into TEST_SCENARIOS.md)
- SCENARIO_FULL_COVERAGE.md (consolidated into TEST_SCENARIOS.md)
- Any other outdated scenario docs

**Archive Location**: `tests/legacy/archive/README.md` with index of archived docs

---

### Phase 4: REMOVE Redundant Files
**Action**: Delete duplicate or superseded content

**Files to DELETE:**
1. `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` (→ Keep only in tests/)
   - Duplicate of `tests/legacy/TESTING_AGENT_INSTRUCTIONS.md`
   - Consolidate: Keep modern `tests/TESTING_AGENT_INSTRUCTIONS.md`, delete legacy version

---

## 📁 Final Structure (Post-Migration)

```
tests/
├── README.md                            # ✅ MOVED: Test suite overview
├── TESTING_GUIDE.md                     # ✅ MOVED: Master technical reference
├── TESTING_AGENT_INSTRUCTIONS.md        # ✅ MOVED: AI agent quick-start
├── TEST_CREATION_TEMPLATE.md            # ✅ MOVED: Test pattern examples
├── TEST_FIXTURE_GUIDE.md                # ✅ MOVED: conftest.py helpers
├── TEST_SCENARIOS.md                    # ✅ MOVED + CONSOLIDATED
│                                          # (includes SCENARIO_FULL_COVERAGE + TESTDATA_CATALOG)
├── __init__.py
├── conftest.py
├── scenarios/
├── helpers/
├── modern_tests/                        # (if organized separately)
│   ├── test_approval_reset_overdue_interaction.py
│   ├── test_chore_scheduling.py
│   ├── test_config_flow_fresh_start.py
│   └── ...
└── legacy/
    ├── archive/                         # 🔒 Historical reference only
    │   ├── README.md
    │   ├── TESTDATA_CATALOG.md          # (consolidated into TEST_SCENARIOS.md)
    │   ├── SCENARIO_FULL_COVERAGE.md    # (consolidated into TEST_SCENARIOS.md)
    │   └── [other archived docs]
    ├── __init__.py
    ├── conftest.py
    ├── test_*.py                        # Legacy test files (phase out over time)
    ├── testdata_scenario_*.yaml
    └── migration_samples/
```

---

## 🔗 Documentation Links & References

### Currently Documented In (Update These)

**In copilot-instructions.md:**
```
"Testing": [tests/TESTING_AGENT_INSTRUCTIONS.md](../tests/TESTING_AGENT_INSTRUCTIONS.md) (Patterns, execution)
```

**In ARCHITECTURE.md:**
```
- **Testing**: [tests/TESTING_GUIDE.md](../tests/TESTING_GUIDE.md) (Patterns, execution)
```

**In CODE_REVIEW_GUIDE.md:**
```
Reference Documents
- [TESTING_GUIDE.md](../tests/TESTING_GUIDE.md) - Testing patterns and troubleshooting
```

### Links to Update Post-Migration

1. All `../tests/legacy/` → `../tests/`
2. Update README references in main integration docs
3. Update conftest/workflow imports if any (usually not needed)

---

## 📋 Implementation Checklist

### Step 1: Copy Core Docs
- [ ] Copy `tests/legacy/README.md` → `tests/README.md`
- [ ] Copy `tests/legacy/TESTING_GUIDE.md` → `tests/TESTING_GUIDE.md`
- [ ] Copy `tests/legacy/TESTING_AGENT_INSTRUCTIONS.md` → `tests/TESTING_AGENT_INSTRUCTIONS.md`
- [ ] Copy `tests/legacy/TEST_CREATION_TEMPLATE.md` → `tests/TEST_CREATION_TEMPLATE.md`
- [ ] Copy `tests/legacy/TEST_FIXTURE_GUIDE.md` → `tests/TEST_FIXTURE_GUIDE.md`
- [ ] Copy `tests/legacy/TEST_SCENARIOS.md` → `tests/TEST_SCENARIOS.md`

### Step 2: Consolidate Overlapping Content
- [ ] Read TESTDATA_CATALOG.md content
- [ ] Read SCENARIO_FULL_COVERAGE.md content
- [ ] Merge both into TEST_SCENARIOS.md with new "Appendix" sections
- [ ] Verify all information is preserved
- [ ] Test navigation/links work correctly

### Step 3: Create Archive Directory
- [ ] Create `tests/legacy/archive/` directory
- [ ] Create `tests/legacy/archive/README.md` with index
- [ ] Move TESTDATA_CATALOG.md → archive/
- [ ] Move SCENARIO_FULL_COVERAGE.md → archive/
- [ ] Add deprecation notes to archived files

### Step 4: Update All References
- [ ] Update copilot-instructions.md links
- [ ] Update ARCHITECTURE.md links
- [ ] Update CODE_REVIEW_GUIDE.md links
- [ ] Search codebase for other references: `grep -r "tests/legacy" --include="*.md" --include="*.py"`
- [ ] Fix all found references

### Step 5: Cleanup
- [ ] Delete duplicate `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` (keep modern version only)
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Verify no import errors
- [ ] Verify all links work

### Step 6: Documentation Update
- [ ] Update this plan with "COMPLETED" status
- [ ] Add migration summary to RELEASE_CHECKLIST.md or similar

---

## ✅ Benefits of Migration

1. **Single Source of Truth**: All test docs in `tests/`, no split/confusion
2. **Easier Navigation**: Cleaner directory structure for contributors
3. **Reduced Maintenance**: One consolidated reference instead of multiple overlapping docs
4. **Preserved History**: Archive keeps historical reference for research
5. **Better Discoverability**: Modern test docs easy to find
6. **Cleaner Legacy Folder**: Legacy folder becomes test files only, not documentation

---

## 🚀 Migration Timeline

- **Phase 1 (MOVE)**: 30 mins (copy 6 files, update ~15 references)
- **Phase 2 (CONSOLIDATE)**: 45 mins (merge overlapping content)
- **Phase 3 (ARCHIVE)**: 15 mins (organize archive, create index)
- **Phase 4 (CLEANUP)**: 30 mins (delete duplicates, verify all links)
- **Phase 5 (TEST)**: 15 mins (run tests, verify nothing broke)

**Total Estimated Time**: 2-2.5 hours

---

## Questions to Resolve Before Starting

1. Should legacy test FILES move out of `tests/legacy/`, or stay there during gradual phase-out?
   - **Current Plan**: Keep test files in `tests/legacy/`, docs move to `tests/`
   - **Rationale**: Gradual migration reduces breaking changes

2. Should we create a separate `tests/modern/` or `tests/active/` folder for new tests?
   - **Current Plan**: No, keep all active tests in `tests/` root
   - **Rationale**: Simpler structure, modern conftest.py serves both

3. When should we deprecate/remove legacy test files?
   - **Current Plan**: Document deprecation in README, remove gradually as functionality covered by modern tests

---

**Status**: Ready for execution  
**Next Step**: Confirm Phase 1-3 approach, then execute migration

