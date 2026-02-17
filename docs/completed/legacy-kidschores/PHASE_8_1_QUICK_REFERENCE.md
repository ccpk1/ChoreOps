# Phase 8.1 Documentation Migration - Quick Reference

## 📋 Strategic Decision Summary

### Which Docs to Bring Up from tests/legacy/ to tests/

#### **TIER 1: MOVE Immediately** (Essential Long-term Reference)
- ✅ `TESTING_GUIDE.md` (1524 lines) → Master technical reference
- ✅ `README.md` → Test suite overview & onboarding
- ✅ `TEST_FIXTURE_GUIDE.md` (412 lines) → conftest.py helper reference
- ✅ `TEST_CREATION_TEMPLATE.md` (156 lines) → Test pattern examples
- ✅ `TEST_SCENARIOS.md` (298 lines) → Scenario fixture documentation

**Total: 5 files, ~2,500 lines of essential reference**

#### **TIER 2: CONSOLIDATE** (Redundant Content)
- ⚠️ `TESTDATA_CATALOG.md` → Merge into TEST_SCENARIOS.md (Appendix A)
- ⚠️ `SCENARIO_FULL_COVERAGE.md` → Merge into TEST_SCENARIOS.md (Appendix B)
- ⚠️ `TESTING_AGENT_INSTRUCTIONS.md` → Archive (duplicate of tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)

#### **TIER 3: ARCHIVE** (Historical Reference)
- 📦 Other legacy docs → tests/legacy/archive/ (reference only)

---

## 🎯 Why This Structure?

| Criterion | Tier 1 | Tier 2 | Tier 3 |
|-----------|--------|--------|--------|
| **Used daily by developers?** | ✅ Yes | ⚠️ Sometimes | ❌ No |
| **Essential for test writing?** | ✅ Yes | ⚠️ Overlaps Tier 1 | ❌ Historical |
| **Active development ref?** | ✅ Yes | ⚠️ Redundant | ❌ Archive |
| **Bring to tests/?** | ✅ YES | ⚠️ Consolidate | ❌ Archive |

---

## 📊 File-by-File Decision Matrix

| File | Location | Lines | Priority | Action | Rationale |
|------|----------|-------|----------|--------|-----------|
| `TESTING_GUIDE.md` | legacy/ | 1524 | **P1** | MOVE to tests/ | Comprehensive master reference - essential for all test development |
| `README.md` | legacy/ | 408 | **P1** | MOVE as README_TESTING.md | Onboarding & Stårblüm family background - needed by new contributors |
| `TEST_FIXTURE_GUIDE.md` | legacy/ | 412 | **P1** | MOVE to tests/ | Complete conftest.py fixture reference - must be in tests/ with other fixtures |
| `TEST_CREATION_TEMPLATE.md` | legacy/ | 156 | **P1** | MOVE to tests/ | Template & examples for writing new tests - belongs in tests/ |
| `TEST_SCENARIOS.md` | legacy/ | 298 | **P2** | MOVE + CONSOLIDATE | Merge TESTDATA_CATALOG + SCENARIO_FULL_COVERAGE into appendices |
| `TESTDATA_CATALOG.md` | legacy/ | 287 | **P2** | CONSOLIDATE | Overlaps with TEST_SCENARIOS.md - merge as Appendix A |
| `SCENARIO_FULL_COVERAGE.md` | legacy/ | 156 | **P2** | CONSOLIDATE | Entity mapping overlaps TEST_SCENARIOS - merge as Appendix B |
| `TESTING_AGENT_INSTRUCTIONS.md` | legacy/ | 227 | **P3** | ARCHIVE | Duplicate of tests/AGENT_TEST_CREATION_INSTRUCTIONS.md (keep modern version) |
| Other docs | legacy/ | ? | **P3** | ARCHIVE | Historical reference only |

---

## ✅ Result After Phase 8.1

### tests/ folder (Long-term Home)
```
tests/
├── README_TESTING.md              ✅ MOVED (onboarding)
├── TESTING_GUIDE.md               ✅ MOVED (master reference)
├── TEST_FIXTURE_GUIDE.md          ✅ MOVED (fixtures)
├── TEST_CREATION_TEMPLATE.md      ✅ MOVED (patterns)
├── TEST_SCENARIOS.md              ✅ MOVED + CONSOLIDATED
├── AGENT_TEST_CREATION_INSTRUCTIONS.md (modern, kept)
├── PHASE_8_1_EXECUTION_PLAN.md    (this plan - can delete after)
├── conftest.py
├── helpers/
├── scenarios/
└── test_*.py files
```

### tests/legacy/archive/ (Historical Reference)
```
tests/legacy/archive/
├── README.md                      (archive index)
├── TESTDATA_CATALOG.md            (consolidated into TEST_SCENARIOS.md)
├── SCENARIO_FULL_COVERAGE.md      (consolidated into TEST_SCENARIOS.md)
├── TESTING_GUIDE.md               (reference copy)
├── TESTING_AGENT_INSTRUCTIONS.md  (duplicate of tests/ version)
└── [other historical docs]
```

### tests/legacy/ (Test Files Only)
```
tests/legacy/
├── conftest.py
├── test_*.py files (~70+ files)
├── testdata_*.yaml
├── migration_samples/
├── __snapshots__/
└── archive/                        (historical reference)
```

---

## ⏱️ Execution Timeline

| Phase | Task | Est. Time |
|-------|------|-----------|
| **8.1.1** | Move 5 P1 docs to tests/ | 30 min |
| **8.1.2** | Consolidate P2 docs (merge appendices) | 45 min |
| **8.1.3** | Update cross-references in main docs | 30 min |
| **8.1.4** | Create archive, verify everything | 15 min |
| **8.1.5** | Run tests & linting | 15 min |
| **Total** | Full Phase 8.1 Execution | ~2.5 hours |

---

## 🔗 Reference Documents

- **Master Plan**: `docs/in-process/TEST_SUITE_REORGANIZATION_IN-PROCESS.md` (Phase 8)
- **Execution Plan**: `tests/PHASE_8_1_EXECUTION_PLAN.md` (detailed steps)
- **This Document**: `tests/PHASE_8_1_QUICK_REFERENCE.md` (this file)

---

## ✨ Key Principle

> **Consolidate in tests/, Archive in legacy/archive/, Keep legacy/ for test files only**

This ensures:
- 📍 Single source of truth (all test docs in tests/)
- 🧹 Clean structure (legacy folder is test files, not docs)
- 📚 Preserved history (archive folder keeps reference)
- 🚀 Developer friendly (docs where they need them)

---

**Ready to Execute Phase 8.1?** → Start with `tests/PHASE_8_1_EXECUTION_PLAN.md`

