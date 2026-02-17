# Step 4: Badge Operations Migration Plan

## Initiative snapshot

- **Name / Code**: Step 4 - Badge Operations → GamificationManager + DELETE
- **Target release / milestone**: v0.5.0 (Phase 6 Coordinator Slim)
- **Owner / driver(s)**: AI Agent (Strategic Planning)
- **Status**: ✅ COMPLETE
- **Parent Plan**: [PHASE6_COORDINATOR_SLIM_IN-PROCESS.md](PHASE6_COORDINATOR_SLIM_IN-PROCESS.md)

## Summary & immediate steps

| Phase / Step               | Description                                          | % complete | Quick notes                               |
| -------------------------- | ---------------------------------------------------- | ---------- | ----------------------------------------- |
| Phase 1 – Dependency Graph | Map internal call dependencies between badge methods | 100%       | ✅ Complete - documented in plan          |
| Phase 2 – Helper Migration | Move shared helpers to GamificationManager           | 100%       | ✅ 4 methods added (~215 lines)           |
| Phase 3 – Core Migration   | Move award/demote/remove to GamificationManager      | 100%       | ✅ 6 methods added (~630 lines)           |
| Phase 4 – Progress Methods | Move progress sync/calculation methods               | 100%       | ✅ 2 methods added (~560 lines)           |
| Phase 5 – Wire Callers     | Update services.py, options_flow.py, coordinator.py  | 100%       | ✅ All callers wired, 1,395 lines deleted |
| Phase 6 – Validation       | Run tests, lint, mypy                                | 100%       | ✅ 1098 passed, mypy clean, lint OK       |

1. **Key objective** – Migrate 13 badge methods (~1,400 lines) from coordinator.py to GamificationManager while maintaining all existing functionality.
2. **Summary of recent work** – **STEP 4 COMPLETE**: All 13 badge methods migrated to GamificationManager, 1,395 lines deleted from coordinator.py, all validation passed.
3. **Next steps (short term)** – Update parent plan, archive this plan.
4. **Risks / blockers**:
   - Complex interdependencies between badge methods (internal call chain)
   - Methods called from multiple locations (services.py, options_flow.py, coordinator.py, gamification_manager.py)
   - `_sync_badge_progress_for_kid()` is ~370 lines and central to badge lifecycle
   - `_award_badge()` calls multiple other managers (economy_manager, reward_manager)
5. **References**:
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Data model, storage schema
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Naming conventions, patterns
   - [PHASE6_COORDINATOR_SLIM_IN-PROCESS.md](PHASE6_COORDINATOR_SLIM_IN-PROCESS.md) – Parent plan
6. **Decisions & completion check**
   - **Decisions captured**:
     - Migration must preserve `process_award_items()` as a pure utility (can stay in coordinator as thin wrapper or move)
     - `_recalculate_all_badges()` is already a thin wrapper (~15 lines) that delegates to GamificationManager
     - **DECISION**: Keep `_recalculate_all_badges()` in coordinator as thin wrapper (9+ external call sites)
   - **Completion confirmation**: `[ ]` All follow-up items completed before marking Step 4 done

---

## Critical Analysis: Method Dependency Graph

### Internal Call Chain (Coordinator Badge Methods)

```
┌─ _award_badge() ─────────────────────────────────────────────────┐
│   └─ _update_badges_earned_for_kid()                             │
│   └─ process_award_items()                                       │
│   └─ economy_manager.deposit()          [external - already done]│
│   └─ reward_manager._grant_to_kid()     [external - already done]│
│   └─ economy_manager.apply_bonus()      [external - already done]│
│   └─ _persist() + async_set_updated_data()                       │
└──────────────────────────────────────────────────────────────────┘

┌─ _demote_cumulative_badge() ─────────────────────────────────────┐
│   └─ _update_point_multiplier_for_kid()                          │
│   └─ _persist() + async_set_updated_data()                       │
└──────────────────────────────────────────────────────────────────┘

┌─ remove_awarded_badges() ────────────────────────────────────────┐
│   └─ _remove_awarded_badges_by_id()                              │
│       └─ _update_point_multiplier_for_kid()                      │
│   └─ _persist() + async_set_updated_data()                       │
└──────────────────────────────────────────────────────────────────┘

┌─ _sync_badge_progress_for_kid() ─────────────────────────────────┐
│   └─ _get_badge_in_scope_chores_list()                           │
│   └─ kh.dt_* helpers (external)                                  │
│   └─ (NO persist - caller handles)                               │
└──────────────────────────────────────────────────────────────────┘

┌─ _get_cumulative_badge_progress() ───────────────────────────────┐
│   └─ _get_cumulative_badge_levels()                              │
│   └─ (NO persist - read-only computation)                        │
└──────────────────────────────────────────────────────────────────┘

┌─ _update_chore_badge_references_for_kid() ───────────────────────┐
│   └─ _get_badge_in_scope_chores_list()                           │
│   └─ (NO persist - caller handles)                               │
└──────────────────────────────────────────────────────────────────┘

┌─ _recalculate_all_badges() [THIN WRAPPER] ───────────────────────┐
│   └─ gamification_manager._mark_dirty() for all kids             │
│   └─ _persist() + async_set_updated_data()                       │
└──────────────────────────────────────────────────────────────────┘
```

### External Callers by File

| Method                                     | Location                | Line(s)         | Call Pattern                                     |
| ------------------------------------------ | ----------------------- | --------------- | ------------------------------------------------ |
| `_award_badge()`                           | gamification_manager.py | 385             | `await self.coordinator._award_badge(...)`       |
| `_demote_cumulative_badge()`               | gamification_manager.py | 402             | `self.coordinator._demote_cumulative_badge(...)` |
| `remove_awarded_badges()`                  | services.py             | 2236            | `coordinator.remove_awarded_badges(...)`         |
| `_recalculate_all_badges()`                | options_flow.py         | 1103,1226,1877, | `coordinator._recalculate_all_badges()`          |
|                                            |                         | 2070,2344,2356  |                                                  |
| `_recalculate_all_badges()`                | migration_pre_v50.py    | 1521            | `self.coordinator._recalculate_all_badges()`     |
| `_sync_badge_progress_for_kid()`           | options_flow.py         | 2343,2354       | `coordinator._sync_badge_progress_for_kid(...)`  |
| `_sync_badge_progress_for_kid()`           | coordinator.py          | 1346            | `self._sync_badge_progress_for_kid(...)`         |
| `_get_cumulative_badge_progress()`         | coordinator.py          | 1348            | `self._get_cumulative_badge_progress(...)`       |
| `_get_badge_in_scope_chores_list()`        | coordinator.py          | 2320,2911,3110  | `self._get_badge_in_scope_chores_list(...)`      |
| `_update_badges_earned_for_kid()`          | coordinator.py          | 1930            | `self._update_badges_earned_for_kid(...)`        |
| `process_award_items()`                    | coordinator.py          | 1944            | `self.process_award_items(...)`                  |
| `_update_point_multiplier_for_kid()`       | coordinator.py          | 2126,2464,2511, | `self._update_point_multiplier_for_kid(...)`     |
|                                            |                         | 2571,2621       |                                                  |
| `_remove_awarded_badges_by_id()`           | coordinator.py          | 1341,2405       | `self._remove_awarded_badges_by_id(...)`         |
| `_update_chore_badge_references_for_kid()` | coordinator.py          | 325             | `self._update_chore_badge_references_for_kid()`  |
| `_get_cumulative_badge_levels()`           | coordinator.py          | 2666            | `self._get_cumulative_badge_levels(...)`         |

---

## Detailed Phase Tracking

### Phase 1 – Dependency Graph (Complete Analysis)

- **Goal**: Verify all method dependencies and determine safe migration order.
- **Status**: ✅ COMPLETE (documented above)

**Migration Order (Bottom-Up)**:

1. Helper methods with NO internal dependencies first
2. Methods that only call helpers second
3. Complex methods that call other methods last

**Recommended Migration Order**:

```
TIER 1 (No dependencies - migrate first):
├── process_award_items()           # Pure utility, no internal calls
├── _get_badge_in_scope_chores_list()  # Pure utility, no internal calls
├── _get_cumulative_badge_levels()  # Pure utility, no internal calls
└── _update_point_multiplier_for_kid()  # Only reads data, no internal calls

TIER 2 (Depends on Tier 1):
├── _update_badges_earned_for_kid() # Uses stats engine (external)
├── _update_chore_badge_references_for_kid()  # Uses _get_badge_in_scope_chores_list
├── _get_cumulative_badge_progress()  # Uses _get_cumulative_badge_levels
└── _remove_awarded_badges_by_id()  # Uses _update_point_multiplier_for_kid

TIER 3 (Depends on Tier 1+2):
├── _sync_badge_progress_for_kid()  # Uses _get_badge_in_scope_chores_list
├── remove_awarded_badges()         # Uses _remove_awarded_badges_by_id
├── _demote_cumulative_badge()      # Uses _update_point_multiplier_for_kid
└── _award_badge()                  # Uses multiple Tier 1+2 methods

TIER 4 (Already thin wrapper):
└── _recalculate_all_badges()       # Just marks kids dirty (keep as-is or remove)
```

---

### Phase 2 – Helper Migration (~200 lines)

- **Goal**: Move pure helper methods to GamificationManager first (safest, no side effects).
- **Status**: ✅ COMPLETE

**Methods to migrate (TIER 1)**:

| Method                               | Lines in Coordinator | Dependencies      | Notes                            |
| ------------------------------------ | -------------------- | ----------------- | -------------------------------- |
| `process_award_items()`              | 2138-2161 (~25)      | None              | Pure utility, parses award_items |
| `_get_badge_in_scope_chores_list()`  | 1846-1895 (~55)      | None              | Pure utility, filters chores     |
| `_get_cumulative_badge_levels()`     | 3149-3228 (~90)      | None              | Pure utility, calculates tiers   |
| `_update_point_multiplier_for_kid()` | 2162-2186 (~25)      | None (just reads) | Updates kid's multiplier field   |

**Steps**:

- [x] **2.1** Add `process_award_items()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Copy method signature and body from coordinator.py lines 2138-2161
  - Remove `self.` prefix for rewards_dict/bonuses_dict/penalties_dict (pass as params)
  - Method already takes all data as parameters (good design!)

- [x] **2.2** Add `get_badge_in_scope_chores_list()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Copy from coordinator.py lines 1846-1895
  - Change `self.chores_data` → `self.coordinator.chores_data`
  - Make public (remove underscore prefix)

- [x] **2.3** Add `get_cumulative_badge_levels()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Copy from coordinator.py lines 3149-3228
  - Change `self.kids_data` → `self.coordinator.kids_data`
  - Change `self.badges_data` → `self.coordinator.badges_data`
  - Make public (remove underscore prefix)

- [x] **2.4** Add `update_point_multiplier_for_kid()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Copy from coordinator.py lines 2162-2186
  - Change `self.kids_data` → `self.coordinator.kids_data`
  - Change `self.badges_data` → `self.coordinator.badges_data`
  - Make public (remove underscore prefix)

- [x] **2.5** Run validation ✅
  - Lint: ✅ Passed (ruff format 112 files unchanged, pre-existing test file issues only)
  - MyPy: ✅ Success: no issues found in 36 source files
  - Tests: ✅ 1098 passed, 2 skipped, 2 deselected

**Key issues**:

- None - all helpers migrated successfully

---

### Phase 3 – Core Migration (~700 lines)

- **Goal**: Move badge award/demote/remove methods to GamificationManager (TIER 2 + TIER 3).
- **Status**: ✅ COMPLETE

**Methods to migrate**:

| Method                                     | Lines in Coordinator | Dependencies                               |
| ------------------------------------------ | -------------------- | ------------------------------------------ |
| `_update_badges_earned_for_kid()`          | 2188-2279 (~95)      | stats engine (external)                    |
| `_update_chore_badge_references_for_kid()` | 2282-2335 (~55)      | \_get_badge_in_scope_chores_list (Phase 2) |
| `_get_cumulative_badge_progress()`         | 2649-2763 (~135)     | \_get_cumulative_badge_levels (Phase 2)    |
| `_remove_awarded_badges_by_id()`           | 2407-2630 (~225)     | \_update_point_multiplier (Phase 2)        |
| `_demote_cumulative_badge()`               | 2089-2135 (~50)      | \_update_point_multiplier (Phase 2)        |
| `remove_awarded_badges()`                  | 2337-2405 (~70)      | \_remove_awarded_badges_by_id (this phase) |

**Steps**:

- [x] **3.1** Add `update_badges_earned_for_kid()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Changed data access: `self.kids_data` → `self.coordinator.kids_data`, etc.
  - Changed `self.stats` → `self.coordinator.stats` (StatisticsEngine access)

- [x] **3.2** Add `update_chore_badge_references_for_kid()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Updated internal call to `self.get_badge_in_scope_chores_list()`

- [x] **3.3** Add `get_cumulative_badge_progress()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Updated internal call to `self.get_cumulative_badge_levels()`

- [x] **3.4** Add `demote_cumulative_badge()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Updated internal call to `self.update_point_multiplier_for_kid()`
  - Updated `_apply_badge_result()` call to use new method location

- [x] **3.5** Add `remove_awarded_badges()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Updated internal call to `self.remove_awarded_badges_by_id()`
  - Added `HomeAssistantError` import

- [x] **3.6** Add `remove_awarded_badges_by_id()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Updated internal call to `self.update_point_multiplier_for_kid()`
  - Preserved all HomeAssistantError handling patterns

- [x] **3.7** Run validation ✅
  - Lint: ✅ Passed (ruff check 14 errors - all pre-existing in test files)
  - Ruff format: 1 file reformatted (gamification_manager.py)
  - MyPy: ✅ Success: no issues found in 36 source files
  - Tests: ✅ 1098 passed, 2 skipped, 2 deselected

**Key issues**:

- None - all 6 methods migrated successfully
- `HomeAssistantError` import added for remove_awarded_badges methods
- File organization maintained with clear section headers

---

### Phase 4 – Progress Methods (~500 lines)

- **Goal**: Move the large badge progress sync method and award_badge.
- **Status**: ✅ COMPLETE

**Methods to migrate**:

| Method                           | Lines in Coordinator | Dependencies                             |
| -------------------------------- | -------------------- | ---------------------------------------- |
| `_sync_badge_progress_for_kid()` | 2782-3147 (~370)     | \_get_badge_in_scope_chores_list, kh.\*  |
| `_award_badge()`                 | 1900-2087 (~190)     | All Phase 2+3 methods, external managers |

**Steps**:

- [x] **4.1** Add `sync_badge_progress_for_kid()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Migrated ~370 lines from coordinator.py
  - Updated internal calls: `self.get_badge_in_scope_chores_list()`
  - Uses `kh.dt_*` helpers (no changes needed)
  - NO persist call - caller handles persistence

- [x] **4.2** Add `award_badge()` to GamificationManager ✅
  - File: `managers/gamification_manager.py`
  - Migrated ~190 lines from coordinator.py
  - Updated ALL internal calls to local methods
  - Updated external manager calls to use `self.coordinator.*`
  - Updated notification calls to use `self.coordinator._notify_*`
  - Updated `_apply_badge_result()` to call `self.award_badge()` instead of `self.coordinator._award_badge()`
  - Added `date` import for type hints
  - Added `KidData`, `KidBadgeProgress` to TYPE_CHECKING imports

- [x] **4.3** Run validation ✅
  - Lint: ✅ Passed (pre-existing test file issues only)
  - Ruff format: 112 files unchanged
  - MyPy: ✅ Success: no issues found in 36 source files
  - Tests: ✅ 1098 passed, 2 skipped, 2 deselected

**Key issues**:

- None - both methods migrated successfully
- Fixed mypy type issue with multiplier assignment (needed explicit float conversion)
- `_apply_badge_result()` now calls local `award_badge()` and `demote_cumulative_badge()` methods

---

### Phase 5 – Wire Callers & DELETE Coordinator Methods

- **Goal**: Update all external callers to use GamificationManager, then DELETE from coordinator.

#### 5A. Update External Callers

**services.py updates**:

- [x] **5A.1** Update `handle_remove_awarded_badges()` (line 2236)
  - Old: `coordinator.remove_awarded_badges(kid_name=kid_name, badge_name=badge_name)`
  - New: `coordinator.gamification_manager.remove_awarded_badges(kid_name=kid_name, badge_name=badge_name)`

**options_flow.py updates**:

- [x] **5A.2** Update all `_recalculate_all_badges()` calls (6 locations)
  - Lines: 1103, 1226, 1877, 2070, 2344, 2356
  - **DECISION**: Keep as `coordinator._recalculate_all_badges()` - thin wrapper stays in coordinator
  - Note: 9+ external call sites, cleaner to keep thin wrapper

- [x] **5A.3** Update `_sync_badge_progress_for_kid()` calls (2 locations)
  - Lines: 2343, 2354
  - Old: `coordinator._sync_badge_progress_for_kid(kid_id)`
  - New: `coordinator.gamification_manager.sync_badge_progress_for_kid(kid_id)`

**migration_pre_v50.py updates**:

- [x] **5A.4** Update `_recalculate_all_badges()` call (line 1521)
  - **DECISION**: Keep as `self.coordinator._recalculate_all_badges()` - thin wrapper stays in coordinator

**gamification_manager.py updates** (internal calls become self.):

- [x] **5A.5** Update `_apply_badge_result()` (lines 385, 402)
  - Done in Phase 4 - internal calls now use self.award_badge() and self.demote_cumulative_badge()

**coordinator.py internal updates**:

- [x] **5A.6** Update `delete_badge_entity()` method (lines 1341-1352)
  - Old: `self._remove_awarded_badges_by_id(badge_id=badge_id)`
  - New: `self.gamification_manager.remove_awarded_badges_by_id(badge_id=badge_id)`
  - Old: `cumulative_progress = self._get_cumulative_badge_progress(kid_id)`
  - New: `cumulative_progress = self.gamification_manager.get_cumulative_badge_progress(kid_id)`

- [x] **5A.7** Update `_update_chore_badge_references_for_kid()` calls (line 325)
  - Old: `self._update_chore_badge_references_for_kid()`
  - New: `self.gamification_manager.update_chore_badge_references_for_kid()`

#### 5B. DELETE Coordinator Badge Methods

**DELETED these methods from coordinator.py** (~1,378 lines removed):

- [x] **5B.1** DELETE `_get_badge_in_scope_chores_list()` (~50 lines)
- [x] **5B.2** DELETE `_award_badge()` (~190 lines)
- [x] **5B.3** DELETE `_demote_cumulative_badge()` (~45 lines)
- [x] **5B.4** DELETE `process_award_items()` (~25 lines)
- [x] **5B.5** DELETE `_update_point_multiplier_for_kid()` (~25 lines)
- [x] **5B.6** DELETE `_update_badges_earned_for_kid()` (~90 lines)
- [x] **5B.7** DELETE `_update_chore_badge_references_for_kid()` (~55 lines)
- [x] **5B.8** DELETE `remove_awarded_badges()` (~70 lines)
- [x] **5B.9** DELETE `_remove_awarded_badges_by_id()` (~225 lines)
- [x] **5B.10** KEEP `_recalculate_all_badges()` as thin wrapper (~15 lines) - 9+ external call sites
- [x] **5B.11** DELETE `_get_cumulative_badge_progress()` (~115 lines)
- [x] **5B.12** DELETE `_sync_badge_progress_for_kid()` (~370 lines)
- [x] **5B.13** DELETE `_get_cumulative_badge_levels()` (~80 lines)

**Actual line reduction**: 1,378 lines from coordinator.py (3596 → 2218 lines)

#### 5C. Validation

- [x] **5C.1** Run quick lint - Passed (pre-existing test issues only)

- [x] **5C.2** Run mypy on all affected files - Success: no issues found in 36 source files

- [x] **5C.3** Run full test suite - 1098 passed, 2 skipped, 2 deselected

**Key issues**:

- ✅ All 12+ call sites updated across 5 files
- ✅ 12 methods deleted from coordinator.py (kept thin wrapper)
- ✅ All tests pass

- [ ] **5C.1** Run quick lint

  ```bash
  ./utils/quick_lint.sh --fix
  ```

- [ ] **5C.2** Run mypy on all affected files

  ```bash
  mypy custom_components/kidschores/coordinator.py
  mypy custom_components/kidschores/services.py
  mypy custom_components/kidschores/options_flow.py
  mypy custom_components/kidschores/managers/gamification_manager.py
  mypy custom_components/kidschores/migration_pre_v50.py
  ```

- [ ] **5C.3** Run full test suite
  ```bash
  python -m pytest tests/ -v --tb=line
  ```

**Key issues**:

- 12+ call sites to update across 5 files
- Deletion order matters - delete in reverse dependency order (TIER 3 → TIER 1)
- Keep `_recalculate_all_badges()` as convenience wrapper if heavily used

---

### Phase 6 – Final Validation

- **Goal**: Comprehensive validation of all badge functionality.

**Steps**:

- [x] **6.1** Verify gamification_manager.py has all 13 methods
- [x] **6.2** Verify coordinator.py no longer has badge methods (except thin wrappers if kept)
- [x] **6.3** Run full test suite with coverage
  ```bash
  pytest tests/ -v --cov=custom_components.kidschores --cov-report term-missing
  ```
  **Result**: 1098 passed, 2 skipped, 69% coverage
- [x] **6.4** Run integration tests for badge scenarios
  ```bash
  pytest tests/test_badge*.py tests/test_gamification*.py -v
  ```
  **Result**: 57 passed, 2 skipped
- [x] **6.5** Update PHASE6_COORDINATOR_SLIM_IN-PROCESS.md Step 4 to 100%

**Key issues**:

- ✅ All tests pass
- ✅ MyPy clean (no issues found)

---

## Method Migration Reference

### Final GamificationManager Public API After Migration

```python
class GamificationManager(BaseManager):
    # === Evaluation (existing) ===
    async def _evaluate_kid(self, kid_id: str) -> None
    async def _evaluate_badge_for_kid(self, context, badge_id, badge_data) -> None
    async def _evaluate_achievement_for_kid(...) -> None
    async def _evaluate_challenge_for_kid(...) -> None

    # === Badge Helpers (NEW - Phase 2) ===
    def process_award_items(self, award_items, rewards_dict, bonuses_dict, penalties_dict) -> tuple
    def get_badge_in_scope_chores_list(self, badge_info, kid_id, kid_assigned_chores=None) -> list
    def get_cumulative_badge_levels(self, kid_id) -> tuple[dict|None, dict|None, dict|None, float, float]
    def update_point_multiplier_for_kid(self, kid_id) -> None

    # === Badge Core (NEW - Phase 3) ===
    def update_badges_earned_for_kid(self, kid_id, badge_id) -> None
    def update_chore_badge_references_for_kid(self, include_cumulative_badges=False) -> None
    def get_cumulative_badge_progress(self, kid_id) -> dict[str, Any]
    def remove_awarded_badges_by_id(self, kid_id=None, badge_id=None) -> None
    def demote_cumulative_badge(self, kid_id) -> None
    def remove_awarded_badges(self, kid_name=None, badge_name=None) -> None

    # === Badge Progress (NEW - Phase 4) ===
    def sync_badge_progress_for_kid(self, kid_id) -> None
    async def award_badge(self, kid_id, badge_id) -> None

    # === Recalculation (thin wrapper) ===
    def recalculate_all_badges(self) -> None  # Just marks all kids dirty
```

### Coordinator Thin Wrappers to Consider Keeping

```python
# Option A: Keep as convenience methods in coordinator.py
def _recalculate_all_badges(self):
    """Convenience wrapper - delegates to GamificationManager."""
    self.gamification_manager.recalculate_all_badges()

# Option B: Remove entirely and update all 7 callers to use gamification_manager directly
```

**Recommendation**: Keep `_recalculate_all_badges()` as thin wrapper since it's called from 7 locations and the wrapper is only 3 lines.

---

## Risk Mitigation

1. **Complex Dependencies**: Migration order (Tier 1 → Tier 4) ensures dependencies exist before methods that use them
2. **Large Methods**: `_sync_badge_progress_for_kid()` (~370 lines) - migrate as-is, refactor later if needed
3. **Notification Calls**: `_award_badge()` calls coordinator notification helpers - prefix with `self.coordinator.`
4. **External Manager Calls**: `_award_badge()` calls economy_manager/reward_manager - prefix with `self.coordinator.`
5. **HomeAssistantError**: Preserve existing error handling patterns in `remove_awarded_badges*()`

---

## Estimated Effort

| Phase     | Methods | Lines          | Estimated Time      |
| --------- | ------- | -------------- | ------------------- |
| Phase 1   | 0       | 0              | 10 min (analysis)   |
| Phase 2   | 4       | ~200           | 20 min              |
| Phase 3   | 6       | ~700           | 40 min              |
| Phase 4   | 2       | ~560           | 30 min              |
| Phase 5   | 0       | ~1,400 deleted | 30 min              |
| Phase 6   | 0       | 0              | 15 min (validation) |
| **Total** | 13      | ~1,400         | **~2.5 hours**      |

---

## Definition of Done

- [x] All 13 badge methods exist in `gamification_manager.py`
- [x] All 13 badge methods DELETED from `coordinator.py` (or converted to thin wrappers)
- [x] All 12+ call sites updated to use `gamification_manager`
- [x] `./utils/quick_lint.sh --fix` passes
- [x] `mypy custom_components/kidschores/` reports zero errors
- [x] `python -m pytest tests/ -v` shows all 1098+ tests pass
- [x] PHASE6_COORDINATOR_SLIM_IN-PROCESS.md Step 4 marked 100% complete
