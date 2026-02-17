# Phase 8.1 - Documentation Migration: Prioritized Action Plan

**Date**: January 10, 2026  
**Status**: Ready for Execution  
**Master Reference**: `docs/in-process/TEST_SUITE_REORGANIZATION_IN-PROCESS.md`

---

## Strategic Decision: Which Docs to Bring Up

### Current State

**tests/ folder** (modern):
- ✅ `AGENT_TEST_CREATION_INSTRUCTIONS.md` (14.6 KB) - Already present

**tests/legacy/ folder** (legacy):
- `README.md` (408 lines)
- `TESTING_GUIDE.md` (1524 lines) - **MASTER REFERENCE**
- `TESTING_AGENT_INSTRUCTIONS.md` (227 lines) - Similar to what's in tests/
- `TEST_CREATION_TEMPLATE.md` (156 lines)
- `TEST_FIXTURE_GUIDE.md` (412 lines)
- `TEST_SCENARIOS.md` (298 lines)
- `TESTDATA_CATALOG.md` (287 lines) - ⚠️ Redundant/overlaps TEST_SCENARIOS
- `SCENARIO_FULL_COVERAGE.md` (156 lines) - ⚠️ Redundant/overlaps TEST_SCENARIOS

---

## Tier 1: Essential Long-Term Reference Docs

**Bring Up IMMEDIATELY** (these are core ongoing documentation for test development):

| Priority | File | Purpose | Action | Rationale |
|----------|------|---------|--------|-----------|
| **P1** | `TESTING_GUIDE.md` | Master technical reference | MOVE to tests/ | 1524 lines of comprehensive test patterns, fixtures, debugging - essential for all test development |
| **P1** | `README.md` | Test suite overview | MOVE to tests/ | Onboarding doc for new contributors, explains Stårblüm family, structure |
| **P1** | `TEST_FIXTURE_GUIDE.md` | conftest.py helper reference | MOVE to tests/ | Reference for all available fixtures - needed for test writing |
| **P2** | `TEST_SCENARIOS.md` | Scenario fixture docs | MOVE + CONSOLIDATE | Merge in TESTDATA_CATALOG.md + SCENARIO_FULL_COVERAGE.md content |
| **P2** | `TEST_CREATION_TEMPLATE.md` | Test pattern examples | MOVE to tests/ | Template/examples for writing new tests |

**Total Priority 1-2**: 5 files, ~2,500 lines of essential reference material

---

## Tier 2: Duplicate/Redundant Docs (Archive or Consolidate)

| File | Current Location | Status | Action | Rationale |
|------|------------------|--------|--------|-----------|
| `TESTDATA_CATALOG.md` | tests/legacy/ | ⚠️ Redundant | CONSOLIDATE into TEST_SCENARIOS.md | Content overlaps with TEST_SCENARIOS - merge as Appendix A |
| `SCENARIO_FULL_COVERAGE.md` | tests/legacy/ | ⚠️ Redundant | CONSOLIDATE into TEST_SCENARIOS.md | Entity mapping content overlaps - merge as Appendix B |
| `TESTING_AGENT_INSTRUCTIONS.md` | tests/legacy/ | ✅ Duplicate | MOVE but rename | Keep - similar to tests/AGENT_TEST_CREATION_INSTRUCTIONS.md |

---

## Tier 3: Historical/Reference-Only Docs (Archive)

**Leave in tests/legacy/archive/** (reference only, not active development):

- Any other .md files not listed above
- Outdated scenario docs
- Deprecated test patterns
- Migration guides (reference only)

---

## Implementation Plan: Phase 8.1 Execution

### Step 1: Move Priority 1 Docs (30 minutes)

```bash
# Copy P1 docs from legacy to tests/
cp /workspaces/kidschores-ha/tests/legacy/TESTING_GUIDE.md /workspaces/kidschores-ha/tests/
cp /workspaces/kidschores-ha/tests/legacy/README.md /workspaces/kidschores-ha/tests/README_TESTING.md
cp /workspaces/kidschores-ha/tests/legacy/TEST_FIXTURE_GUIDE.md /workspaces/kidschores-ha/tests/
cp /workspaces/kidschores-ha/tests/legacy/TEST_CREATION_TEMPLATE.md /workspaces/kidschores-ha/tests/

# Verify copies
ls -lh /workspaces/kidschores-ha/tests/*.md | grep -E "(TESTING_GUIDE|README_TESTING|TEST_FIXTURE|TEST_CREATION)"
```

**Note on README.md**: Rename to `README_TESTING.md` in tests/ to avoid conflicts with integration's main README.md

### Step 2: Move & Consolidate Priority 2 Docs (45 minutes)

```bash
# Copy TEST_SCENARIOS.md
cp /workspaces/kidschores-ha/tests/legacy/TEST_SCENARIOS.md /workspaces/kidschores-ha/tests/

# Manually merge content:
# 1. Open tests/TEST_SCENARIOS.md
# 2. Append TESTDATA_CATALOG.md content as "Appendix A: YAML File Reference"
# 3. Append SCENARIO_FULL_COVERAGE.md content as "Appendix B: Full Scenario Reference"
# 4. Update table of contents
# 5. Verify all links work
```

### Step 3: Update Cross-References (30 minutes)

**Search for references that need updating**:

```bash
# Find all references to tests/legacy/ docs in codebase
grep -r "tests/legacy" /workspaces/kidschores-ha --include="*.md" --include="*.py" | grep -v ".pyc" | grep -v "test_"

# Expected results: copilot-instructions.md, possibly CODE_REVIEW_GUIDE.md, ARCHITECTURE.md
```

**Update**:
- [ ] `/.github/copilot-instructions.md` - Update test doc references
- [ ] `/docs/ARCHITECTURE.md` - Update test doc references  
- [ ] `/docs/CODE_REVIEW_GUIDE.md` - Update test doc references

### Step 4: Handle Duplicates (15 minutes)

```bash
# Option A: Keep only the better one
# tests/AGENT_TEST_CREATION_INSTRUCTIONS.md (current, 14.6 KB)
# vs
# tests/legacy/TESTING_AGENT_INSTRUCTIONS.md (legacy, 227 lines)

# Decision: Keep tests/AGENT_TEST_CREATION_INSTRUCTIONS.md, mark legacy version as archived
```

### Step 5: Archive Consolidation (15 minutes)

```bash
# Create archive directory
mkdir -p /workspaces/kidschores-ha/tests/legacy/archive

# Move consolidated files
mv /workspaces/kidschores-ha/tests/legacy/TESTDATA_CATALOG.md /workspaces/kidschores-ha/tests/legacy/archive/
mv /workspaces/kidschores-ha/tests/legacy/SCENARIO_FULL_COVERAGE.md /workspaces/kidschores-ha/tests/legacy/archive/

# Create archive README with index
# (see template below)

# Move original legacy versions after consolidation
mv /workspaces/kidschores-ha/tests/legacy/README.md /workspaces/kidschores-ha/tests/legacy/archive/README_LEGACY.md
mv /workspaces/kidschores-ha/tests/legacy/TESTING_GUIDE.md /workspaces/kidschores-ha/tests/legacy/archive/
# etc...
```

### Step 6: Verify Everything Works (15 minutes)

```bash
# Run tests to ensure nothing broke
python -m pytest tests/ -v --tb=line

# Check linting
./utils/quick_lint.sh --fix

# Verify doc links work
grep -r "tests/" /workspaces/kidschores-ha/tests/*.md | head -20
```

---

## Folder Structure: Before & After

### BEFORE (Current)

```
tests/
├── AGENT_TEST_CREATION_INSTRUCTIONS.md    # Modern doc
├── conftest.py
├── helpers/
├── scenarios/
├── test_*.py files
└── legacy/
    ├── README.md
    ├── TESTING_GUIDE.md
    ├── TESTING_AGENT_INSTRUCTIONS.md
    ├── TEST_CREATION_TEMPLATE.md
    ├── TEST_FIXTURE_GUIDE.md
    ├── TEST_SCENARIOS.md
    ├── TESTDATA_CATALOG.md
    ├── SCENARIO_FULL_COVERAGE.md
    ├── conftest.py
    ├── test_*.py files
    └── testdata_*.yaml files
```

### AFTER (Post-Phase 8.1)

```
tests/
├── README_TESTING.md                      # ✅ MOVED from legacy
├── TESTING_GUIDE.md                       # ✅ MOVED from legacy
├── TEST_FIXTURE_GUIDE.md                  # ✅ MOVED from legacy
├── TEST_CREATION_TEMPLATE.md              # ✅ MOVED from legacy
├── TEST_SCENARIOS.md                      # ✅ MOVED + CONSOLIDATED (includes appendices)
├── AGENT_TEST_CREATION_INSTRUCTIONS.md    # Modern doc (kept)
├── conftest.py
├── helpers/
├── scenarios/
├── test_*.py files
└── legacy/
    ├── archive/                           # 🔒 Historical reference
    │   ├── README.md (archive index)
    │   ├── README_LEGACY.md
    │   ├── TESTDATA_CATALOG.md            # (consolidated, archived)
    │   ├── SCENARIO_FULL_COVERAGE.md      # (consolidated, archived)
    │   ├── TESTING_GUIDE.md               # (reference copy)
    │   └── [other historical docs]
    ├── conftest.py
    ├── test_*.py files
    └── testdata_*.yaml files
```

**Key Changes**:
- ✅ 5 essential docs now in tests/
- ✅ Legacy folder contains test files only (no docs)
- ✅ Archive folder preserves history
- ✅ No duplicate documentation in two places

---

## Content: Archive README Template

Create `/workspaces/kidschores-ha/tests/legacy/archive/README.md`:

```markdown
# KidsChores Test Documentation Archive

This folder contains historical test documentation that has been consolidated or superseded by newer versions in `tests/`.

## Archived Documents

| File | Reason | Consolidated Into |
|------|--------|-------------------|
| `TESTDATA_CATALOG.md` | Redundant with TEST_SCENARIOS.md | tests/TEST_SCENARIOS.md (Appendix A) |
| `SCENARIO_FULL_COVERAGE.md` | Redundant with TEST_SCENARIOS.md | tests/TEST_SCENARIOS.md (Appendix B) |
| `TESTING_GUIDE.md` | Reference copy of current master | tests/TESTING_GUIDE.md |

## Active Documentation

For current test development, refer to:
- `tests/TESTING_GUIDE.md` - Master reference
- `tests/README_TESTING.md` - Test suite overview
- `tests/TEST_FIXTURE_GUIDE.md` - Fixture reference
- `tests/TEST_CREATION_TEMPLATE.md` - Test patterns
- `tests/TEST_SCENARIOS.md` - Scenario documentation

## Legacy Test Files

This folder also contains legacy test files that are being gradually migrated to modern patterns.
See `docs/in-process/TEST_SUITE_REORGANIZATION_IN-PROCESS.md` Phase 7 for migration tracking.
```

---

## Key Benefits After Phase 8.1

| Benefit | Impact |
|---------|--------|
| **Single source of truth** | All test docs in `tests/`, no split confusion |
| **Cleaner navigation** | Contributors know where to find test docs |
| **Reduced maintenance** | No duplicate docs to keep in sync |
| **Historical preservation** | Archive keeps reference without clutter |
| **Easier onboarding** | New developers find all they need in `tests/` |
| **Clear separation** | `tests/legacy/` is purely test files, not docs |

---

## Rollback Plan (If Needed)

If any issue arises:

```bash
# Restore from git
git checkout tests/legacy/  # Restores all original docs
# Then retry with different approach
```

Since we're using `cp` (not `mv`), originals remain until we explicitly delete them.

---

## Success Criteria

- [ ] 5 priority docs successfully copied to tests/
- [ ] All cross-references updated in main docs
- [ ] TEST_SCENARIOS.md includes both appendices
- [ ] Archive README created and indexed
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Linting passes: `./utils/quick_lint.sh --fix`
- [ ] No broken links in documentation
- [ ] Legacy folder contains only test files (no docs)

---

## Timeline

- **Phase 8.1 (Documentation Move)**: ~2 hours
- **Phase 8.2 (Cross-reference Updates)**: ~1 hour
- **Phase 8.3 (Verification & Cleanup)**: ~30 minutes

**Total**: ~3.5 hours for complete Phase 8 execution

---

**Owner**: KidsChores Development Team  
**Status**: ⏳ Ready to execute  
**Next Step**: Begin Phase 8.1 Step 1 (move P1 docs)

