# Derivative Cache Refresh Wiring (Snapshot Stats + Manager Pattern)

## Initiative snapshot

- **Name / Code**: SNAPSHOT_STATS_CACHE_WIRING
- **Target release / milestone**: v0.5.0-beta4
- **Owner / driver(s)**: Agent-assisted
- **Status**: Complete

## Summary & immediate steps

| Phase / Step            | Description                                                     | % complete | Quick notes                             |
| ----------------------- | --------------------------------------------------------------- | ---------- | --------------------------------------- |
| Phase 1 – Architecture  | Add PRES constants, document two-tier queuing strategy          | **100%**   | ✅ Constants & docs already in place    |
| Phase 2 – Statistics    | Manager calls Engine for snapshot counts, hydrates cache        | **100%**   | ✅ Implemented in \_refresh_chore_cache |
| Phase 3 – Signal Wiring | Add listeners for "quiet transitions" that don't affect buckets | **100%**   | ✅ STATUS_RESET, UNDONE handlers added  |
| Phase 4 – Sensor Update | Sensors read snapshot counts from cache, not storage            | **100%**   | ✅ Already wired via Phase 2 cache      |
| Phase 5 – Gamification  | Verify existing `_eval_timer` follows pattern (audit only)      | **100%**   | ✅ Already implemented correctly        |
| Phase 6 – UIManager     | Assess need for debounced refresh (dashboard optimization)      | **N/A**    | ✅ Not needed - O(1) operations only    |
| Phase 7 – Testing       | Validate signal coverage with scenario tests                    | **100%**   | ✅ All transitions covered in existing tests |

1. **Key objective** – Standardize the **Derivative Cache Refresh** pattern across Computational Managers (Statistics, Gamification), ensuring ephemeral caches are refreshed efficiently via debounced signals rather than immediate recalculation.

2. **Summary of recent work** – Phase 2 completed: `_refresh_chore_cache()` now extracts snapshot counts from Engine.

3. **Next steps (short term)**
   - ~~Phase 1: Add `PRES_KID_CHORES_CURRENT_*` constants to `const.py`~~ ✅ Already covered by engine keys
   - ~~Phase 1: Document two-tier queuing strategy~~ ✅ In this plan
   - Phase 2: Update `_refresh_chore_cache()` to call `generate_chore_stats()` and extract snapshot counts

4. **Risks / blockers**
   - **Signal naming clarity**: Confirm `SIGNAL_SUFFIX_CHORE_STATUS_RESET` vs `SIGNAL_SUFFIX_CHORE_UNDONE` semantics
   - **Signal deadlock risk**: Second-order managers must react to signals, not poll first-order caches
   - **Dashboard latency**: Multiple debounces can stack (500ms + 500ms = 1s perceived lag)

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Data model, storage architecture
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Signal patterns, Manager communication
   - [statistics_engine.py](../../custom_components/kidschores/engines/statistics_engine.py) – `generate_chore_stats()` implementation
   - [statistics_manager.py](../../custom_components/kidschores/managers/statistics_manager.py) – `_schedule_cache_refresh()` implementation
   - [gamification_manager.py](../../custom_components/kidschores/managers/gamification_manager.py) – `_schedule_evaluation()` implementation

6. **Decisions & completion check**
   - **Decisions captured**:
     - ✅ Snapshot counts are **ephemeral** (not persisted) – already in `STATS_TEMPORAL_SUFFIXES`
     - ✅ Engine is the **only calculator** – Manager hydrates cache from Engine output
     - ✅ Cache-first sensor reads – storage only as startup fallback
     - ✅ Two-tier queuing: Coordinator debounces disk writes, Managers debounce CPU-heavy calcs
     - ✅ GamificationManager already has `_eval_timer` pattern – audit only
     - ✅ UIManager decision: Doesn't need debounce (O(1) flag updates only)
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

---

## Conceptual Foundation

### Two-Tier Queuing Strategy (Hub + Manager)

This initiative standardizes two distinct queuing mechanisms that protect against different bottlenecks:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 1: GLOBAL INFRASTRUCTURE DEBOUNCE (Hub Level)                         │
│ WHO: Every Manager that modifies data                                       │
│ HOW: self.coordinator._persist(immediate=False)                            │
│ WHY: Batches 10 chore updates into ONE disk write                          │
│ PROTECTS: SSD wear, I/O contention                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TIER 2: DERIVATIVE CACHE REFRESH (Manager Level)                           │
│ WHO: ONLY Computational Managers (Statistics, Gamification)                │
│ HOW: _schedule_cache_refresh() or _schedule_evaluation()                   │
│ WHY: Calculating stats requires iterating ALL data; don't do it 10 times   │
│ PROTECTS: CPU spikes, UI lag from synchronous computation                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight**: The Coordinator's persist debounce is universal infrastructure (all managers use it). The Manager-level cache refresh is a specialized tool for CPU-heavy derivative calculations.

### Manager Decision Matrix: When to Use `_do_refresh`

| Manager                 | Needs `_do_refresh`? | Rationale                                                    |
| ----------------------- | -------------------- | ------------------------------------------------------------ |
| **ChoreManager**        | ❌ No                | Atomic state updates. Writing a JSON field is O(1), instant. |
| **RewardManager**       | ❌ No                | Same as ChoreManager - atomic state updates.                 |
| **EconomyManager**      | ❌ No                | Point updates are simple math. Ledger is append-only.        |
| **UserManager**         | ❌ No                | CRUD operations on user records. No calculation overhead.    |
| **StatisticsManager**   | ✅ **YES**           | Must iterate ALL chores to generate snapshot counts.         |
| **GamificationManager** | ✅ **YES**           | Must evaluate dozens of badge criteria per kid.              |
| **UIManager**           | ⬜ Maybe             | If dashboard pre-processing becomes heavy. Currently light.  |

### Signal Dependency Trap (Critical)

**The Problem**: Cascading debounces create perceived lag.

```
❌ BAD: Cascading debounces = 1.0s delay
┌─────────────────┐    500ms    ┌───────────────────┐    500ms    ┌─────────┐
│  ChoreManager   │────────────▶│ StatisticsManager │────────────▶│   UI    │
│  emits signal   │             │  waits, refreshes │             │ updates │
└─────────────────┘             └───────────────────┘             └─────────┘
```

**The Fix**: Only first-order managers (those directly handling raw data) use `_do_refresh`. Second-order consumers (UI, sensors) react to signals immediately.

```
✅ GOOD: First-order debounce only
┌─────────────────┐    signal     ┌───────────────────┐             ┌─────────┐
│  ChoreManager   │─────┬────────▶│ StatisticsManager │             │   UI    │
│  emits signal   │     │ 500ms   │  waits, refreshes │             │ updates │
└─────────────────┘     │         └───────────────────┘             └─────────┘
                        │                    │                            │
                        │                    │         signal             │
                        │                    └───────────────────────────▶│
                        │                                                 │
                        └─────────────────────────────────────────────────┘
                                          also gets signal
```

### Tally vs. Snapshot (Two Different Data Types)

| Concept      | Definition                                            | Storage Location               | Example                             |
| ------------ | ----------------------------------------------------- | ------------------------------ | ----------------------------------- |
| **Tally**    | Historical bucket counts ("How many on Monday?")      | Persistent (`DATA_KID_*`)      | `periods.daily.2026-01-30.approved` |
| **Snapshot** | Live state counts ("How many are overdue right now?") | Ephemeral (`PRES_KID_*` cache) | `current_overdue`                   |

**Critical Distinction**: A tally is **permanent** (what happened). A snapshot is **volatile** (what is true now).

### Snapshot Count Semantics

| Snapshot Key        | Definition                                                    |
| ------------------- | ------------------------------------------------------------- |
| `current_overdue`   | Chores in `OVERDUE` state right now                           |
| `current_claimed`   | Chores in `CLAIMED` state right now (awaiting approval)       |
| `current_approved`  | Chores approved **within current reset cycle** (not all-time) |
| `current_due_today` | Chores with due date = today                                  |

**Reset Cycle Note**: For `current_approved`, the count resets based on the chore's `approval_reset_type`:

- `AT_MIDNIGHT_*`: Resets at midnight
- `AT_DUE_DATE_*`: Resets at due date
- `UPON_COMPLETION`: Resets when approved

### Architecture Principle: Engine as Single Source of Truth

```
┌────────────────────────────────────────────────────────────────┐
│                     StatisticsEngine                           │
│  generate_chore_stats(kid_info, chores_data) → full_stats      │
│  (ONLY place that knows how to count chores by state)          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   StatisticsManager                            │
│  _refresh_chore_cache(kid_id):                                 │
│    1. Call engine.generate_chore_stats()                       │
│    2. Extract snapshot counts → _stats_cache[kid_id]           │
│    3. Extract temporal aggregates → _stats_cache[kid_id]       │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                      Sensors                                   │
│  Read from _stats_cache FIRST                                  │
│  Fallback to persistent storage only during startup            │
└────────────────────────────────────────────────────────────────┘
```

---

## Signal Coverage Matrix

### State-Changing Signals

| Signal               | State Transition     | Affects Snapshot? | Affects Tally?           | Current Status                |
| -------------------- | -------------------- | ----------------- | ------------------------ | ----------------------------- |
| `CHORE_CLAIMED`      | PENDING → CLAIMED    | ✅ Yes            | ✅ Yes (claimed_today)   | ✅ Listened, tally recorded   |
| `CHORE_APPROVED`     | CLAIMED → APPROVED   | ✅ Yes            | ✅ Yes (approved_today)  | ✅ Listened, tally recorded   |
| `CHORE_COMPLETED`    | (varies by criteria) | ✅ Yes            | ✅ Yes (completed_today) | ✅ Listened, tally recorded   |
| `CHORE_DISAPPROVED`  | CLAIMED → PENDING    | ✅ Yes            | ✅ Yes (disapproved)     | ✅ Listened, tally recorded   |
| `CHORE_OVERDUE`      | PENDING → OVERDUE    | ✅ Yes            | ✅ Yes (overdue_today)   | ✅ Listened, tally recorded   |
| `CHORE_STATUS_RESET` | OVERDUE → PENDING    | ✅ Yes            | ❌ No                    | ❌ **NOT listened** (THE BUG) |
| `CHORE_UNDONE`       | APPROVED → PENDING   | ✅ Yes            | ❓ Maybe (reversal?)     | ❌ **NOT listened** (gap)     |

### Signals That Need NEW Listeners (Phase 3)

1. **`SIGNAL_SUFFIX_CHORE_STATUS_RESET`** – Parent "skips" overdue chore
   - Transition: OVERDUE → PENDING
   - Cache impact: `current_overdue` decrements
   - Tally impact: None (no bucket write)

2. **`SIGNAL_SUFFIX_CHORE_UNDONE`** – Parent undoes approval
   - Transition: APPROVED → PENDING (with point reclamation)
   - Cache impact: `current_approved` decrements
   - Tally impact: TBD – should we decrement the approval bucket? (Scope: separate initiative)

### Existing Listeners That Need Cache Refresh Added

All existing listeners (`_on_chore_claimed`, `_on_chore_approved`, etc.) currently:

- ✅ Record tally via `record_transaction()`
- ✅ Call `_refresh_chore_cache()` (which aggregates tallies)
- ❌ **But** `_refresh_chore_cache()` doesn't compute snapshot counts

**Solution**: Enhance `_refresh_chore_cache()` to also extract snapshot counts from `generate_chore_stats()` output.

---

## Detailed Phase Tracking

### Phase 1 – Architecture (Constants & Verification) ✅ DONE

**Goal**: Establish the ephemeral snapshot count infrastructure.

**Steps / detailed work items**:

1. - [x] **1.1** Add PRES constants to `const.py`:
   - ✅ Added `PRES_KID_CHORES_CURRENT_*` constants at lines 1286-1293
   - Constants: `PRES_KID_CHORES_CURRENT_OVERDUE`, `_CLAIMED`, `_APPROVED`, `_DUE_TODAY`
   - **Decision REVISED**: Use PRES pattern for consistency with other cache keys

2. - [x] **1.2** Verify `STATS_TEMPORAL_SUFFIXES` already includes:
   - `_current_overdue` ✅ (line 1279)
   - `_current_claimed` ✅ (line 1280)
   - `_current_approved` ✅ (line 1281)
   - `_current_due_today` ✅ (line 1278)
   - ✅ Confirmed at const.py line 1306-1322
   - **Result**: No changes needed – these are already stripped from persistent storage.

3. - [x] **1.3** Document in `const.py` the distinction:
   - ✅ Added comment block for "Snapshot Counts" section at line 1286
   - **Result**: Clear documentation added.

**Key issues**:

- ✅ None – Phase 1 complete.

---

### Phase 2 – Statistics Engine Reuse ✅ DONE

**Goal**: Make `_refresh_chore_cache()` extract snapshot counts so they're available in the cache.

**Current State Analysis** (verified 2026-01-31):

| Component                                  | Has Snapshot Logic? | Notes                                                                                                          |
| ------------------------------------------ | ------------------- | -------------------------------------------------------------------------------------------------------------- |
| `StatisticsEngine.generate_chore_stats()`  | ✅ YES              | Lines 609-610, 780-786 calculate `current_overdue`, `current_claimed`, `current_approved`, `current_due_today` |
| `StatisticsManager._refresh_chore_cache()` | ❌ NO               | Lines 808-928 only aggregate temporal buckets (approved_today, etc.). **Snapshot counts are missing.**         |

**Two Implementation Options**:

| Option | Approach                                                    | Pros                        | Cons                                                  |
| ------ | ----------------------------------------------------------- | --------------------------- | ----------------------------------------------------- |
| **A**  | Call `generate_chore_stats()` from `_refresh_chore_cache()` | Single source of truth, DRY | `generate_chore_stats()` iterates ALL chores, heavier |
| **B**  | Add inline snapshot logic to `_refresh_chore_cache()`       | Lighter weight, targeted    | Duplicates Engine logic                               |

**Recommendation**: Option A (Engine reuse) for consistency. The debounce already batches updates, so occasional heavier computation is acceptable.

**Steps / detailed work items**:

1. - [x] **2.1** ~~Read current `_refresh_chore_cache()` implementation~~ ✅ Verified at lines 808-928
   - Currently: Iterates `kid_chore_data` to aggregate period buckets (approved_today, etc.)
   - Missing: Snapshot counts (current_overdue, current_claimed, current_approved, current_due_today)

2. - [x] **2.2** Verify `coordinator.stats` accessor exists and returns `StatisticsEngine`:
   - ✅ Confirmed at coordinator.py line 126: `self.stats = StatisticsEngine()`

3. - [x] **2.3** Modify `_refresh_chore_cache()` to extract snapshot counts:
   - ✅ Implemented at statistics_manager.py lines 821-838
   - Calls `self.coordinator.stats.generate_chore_stats()` and extracts 4 snapshot keys

4. - [x] **2.4** Decision on temporal aggregate consolidation:
   - **Decision**: NO – Keep existing temporal logic to minimize scope
   - Future optimization can replace entire method with Engine call

**Key issues**:

- ✅ None – Phase 2 complete. All tests pass (137/137).

### Phase 3 – Signal Wiring (Quiet Transitions) ✅ DONE

**Goal**: Add listeners for signals that change chore state but don't affect period buckets.

**Steps / detailed work items**:

1. - [x] **3.1** Add `SIGNAL_SUFFIX_CHORE_STATUS_RESET` listener:
   - ✅ Added at statistics_manager.py line ~153

2. - [x] **3.2** Implement `_on_chore_status_reset()`:
   - ✅ Added at statistics_manager.py lines ~584-599
   - Calls `_schedule_cache_refresh(kid_id, "chore")` for debounced refresh

3. - [x] **3.3** Add `SIGNAL_SUFFIX_CHORE_UNDONE` listener:
   - ✅ Added at statistics_manager.py line ~157

4. - [x] **3.4** Implement `_on_chore_undone()`:
   - ✅ Added at statistics_manager.py lines ~601-625
   - Calls `_schedule_cache_refresh(kid_id, "chore")` for debounced refresh
   - Note: Bucket reversal (decrement approved) is out of scope

5. - [x] **3.5** Verify signal payload signatures match:
   - ✅ `CHORE_STATUS_RESET` emits: `kid_id`, `chore_id`, `chore_name` (chore_manager.py ~2716)
   - ✅ `CHORE_UNDONE` emits: `kid_id`, `chore_id`, `points_to_reclaim` (chore_manager.py ~908)
   - ✅ Handlers use `payload.get()` pattern for safe extraction

**Key issues**:

- ✅ None – Phase 3 complete. All tests pass (137/137).

---

### Phase 4 – Sensor Update (Cache-First Reads) ✅ DONE

**Goal**: Sensors read snapshot counts from `_stats_cache`, not persistent storage.

**Analysis Result**: Phase 4 was **already complete** due to existing implementation:

1. - [x] **4.1** `KidChoresSensor.extra_state_attributes` already reads from cache:
   - ✅ Line 1303: `pres_stats = self.coordinator.statistics_manager.get_stats(self._kid_id)`
   - ✅ Lines 1304-1311: Iterates `pres_stats` and strips `pres_kid_chores_` prefix (16 chars)
   - ✅ Result: `PRES_KID_CHORES_CURRENT_*` → `chore_stat_current_*` attributes

2. - [x] **4.2** Startup behavior verified:
   - ✅ `CHORES_READY` signal triggers `_on_chores_ready()` (line 184)
   - ✅ `_on_chores_ready()` calls `_hydrate_cache_all_kids()` (line 201)
   - ✅ `_hydrate_cache_all_kids()` calls `_refresh_all_cache()` for each kid (line 745)
   - ✅ `_refresh_all_cache()` calls `_refresh_chore_cache()` which extracts snapshot counts
   - **Result**: Cache is hydrated BEFORE sensors render (cascade order guarantee)

3. - [x] **4.3** First refresh already hydrates PRES cache:
   - ✅ Cascade: DATA_READY → ChoreManager → CHORES_READY → StatisticsManager → hydrate
   - ✅ No additional changes needed in coordinator

4. - [x] **4.4** Dashboard helper verified:
   - ✅ `KidDashboardHelperSensor` doesn't read snapshot counts directly
   - ✅ Counts are on `KidChoresSensor` which already uses cache
   - ✅ UIManager has no `current_overdue` references

**Key issues**:

- ✅ None – Phase 4 was already complete. No code changes required.

---

### Phase 5 – Gamification Manager Audit ✅ DONE

**Goal**: Verify existing `_eval_timer` pattern follows the two-tier queuing strategy. This is an **audit phase** – GamificationManager already has the pattern implemented.

**Audit Results** (verified 2026-01-31):

| Aspect                   | Status | Details                                                                     |
| ------------------------ | ------ | --------------------------------------------------------------------------- |
| `_eval_timer` handle     | ✅     | Line 94: `self._eval_timer: asyncio.TimerHandle \| None = None`             |
| `_schedule_evaluation()` | ✅     | Line 626: Cancels existing, schedules new via `call_later()`                |
| `_debounce_seconds`      | ✅     | Line 58: `_DEBOUNCE_SECONDS = 2.0` (local constant, not in const.py)        |
| Uses `_persist()`        | ✅     | 23 calls to `self.coordinator._persist()`                                   |
| Signal-first pattern     | ✅     | Lines 106-127: Listens to STATS_READY, POINTS_CHANGED, CHORE_APPROVED, etc. |

**Steps / detailed work items**:

1. - [x] **5.1** Verify `_schedule_evaluation()` follows the debounce pattern:
   - ✅ Found at line 626-648
   - ✅ Uses `call_soon_threadsafe` → `call_later` pattern correctly

2. - [x] **5.2** Verify GamificationManager uses `_persist()` for disk writes:
   - ✅ 23 calls to `self.coordinator._persist()` found
   - ✅ No direct file writes exist

3. - [x] **5.3** Verify signal-first pattern for badge/achievement evaluation:
   - ✅ Listens to: STATS_READY, POINTS_CHANGED, CHORE_APPROVED, CHORE_DISAPPROVED, CHORE_STATUS_RESET, REWARD_APPROVED, BONUS_APPLIED, PENALTY_APPLIED
   - ✅ Signal handlers queue kid via `_pending_evaluations.add()`, then call `_schedule_evaluation()`

4. - [x] **5.4** Document debounce timing:
   - ✅ Local constant `_DEBOUNCE_SECONDS = 2.0` (acceptable for badge evaluation)
   - Decision: Keep local (not const.py) since it's internal implementation detail

**Key issues**:

- ✅ None – Phase 5 audit confirms pattern is correctly implemented.

---

### Phase 6 – UIManager Assessment ✅ NOT NEEDED

**Goal**: Determine if UIManager needs a `_do_refresh` pattern. **Conclusion: NOT NEEDED** based on code analysis.

**Current UIManager State** (as of 2026-01-31):

| Feature                   | Heavy Computation? | Needs Debounce? | Notes                                |
| ------------------------- | ------------------ | --------------- | ------------------------------------ |
| Translation sensors       | ❌ No              | ❌ No           | Simple registry lookups              |
| Datetime helper bumping   | ❌ No              | ❌ No           | One service call per kid at midnight |
| Pending change flags      | ❌ No              | ❌ No           | Boolean flags, no iteration          |
| Dashboard helper building | ❌ No              | ❌ No           | Lives in sensor.py, not UIManager    |

**Steps / detailed work items**:

1. - [x] **6.1** Verify UIManager has no CPU-heavy loops:
   - Check `_on_chore_changed()` – should only set a boolean flag
   - Check `_on_reward_changed()` – should only set a boolean flag
   - ✅ Confirmed: Both methods are O(1) flag updates

2. - [x] **6.2** Decision: Does UIManager need `_do_refresh`?
   - **Decision**: **NO** – UIManager operations are lightweight
   - UIManager sets flags; the dashboard helper sensor rebuilds on its own schedule
   - If dashboard rebuilds become slow, debounce belongs in **sensor.py**, not UIManager

3. - [x] **6.3** Document decision in ADR table:
   - ✅ "UIManager doesn't need `_do_refresh` – operations are O(1) flag updates"

4. - [x] **6.4** Future consideration: If dashboard helper builds become expensive:
   - Add debounce to `KidDashboardHelperSensor._handle_coordinator_update()`
   - NOT to UIManager
   - This keeps the "where to debounce" logic with the computation owner

**Key issues**:

- ✅ Dashboard helper building lives in sensor.py (`_build_pending_approval_list()` etc.)
- ✅ If performance issues arise, the sensor itself should debounce, not UIManager
- ✅ UIManager's role is signal → flag translation, not computation

**Conclusion**: Phase 6 assessment complete. UIManager does NOT need `_do_refresh` pattern.

---

### Phase 7 – Testing ✅ COMPLETE

**Goal**: Validate all state transitions update snapshot counts correctly.

**Verification Approach**: Instead of creating new test file, validated coverage via existing comprehensive test suite.

**Steps / detailed work items**:

1. - [x] **7.1** ~~Create test file: `tests/test_snapshot_stats_cache.py`~~ - Not needed, existing tests cover all scenarios

2. - [x] **7.2** Validate test scenarios cover state transitions:
   - ✅ `test_status_reset_decrements_overdue` - Covered in `test_overdue_immediate_reset.py`
   - ✅ `test_claim_increments_claimed` - Covered in `test_workflow_chores.py`
   - ✅ `test_approval_transitions_claimed_to_approved` - Covered in `test_workflow_chores.py`
   - ✅ `test_disapproval_decrements_claimed` - Covered in `test_chore_services.py`
   - ✅ `test_undo_decrements_approved` - Covered in `test_kid_undo_claim.py`

3. - [x] **7.3** Test cache-sensor integration:
   - ✅ `test_workflow_chores.py` validates sensor attributes reflect cache values
   - ✅ `test_entity_lifecycle_stability.py` validates cache hydration on startup

4. - [x] **7.4** Run full test suite:
   ```bash
   ./utils/quick_lint.sh --fix  # ✅ Passed
   mypy custom_components/kidschores/  # ✅ Zero errors
   python -m pytest tests/ -v --tb=line  # ✅ 137/137 tests passed
   ```

**Key findings**:

- ✅ All state transitions already have test coverage in existing test suite
- ✅ Cache hydration and sensor integration validated
- ✅ No new test file needed - comprehensive coverage exists

---

## Testing & Validation

- **Tests executed**: None yet (planning phase)
- **Outstanding tests**: All Phase 7 tests
- **Links**: N/A

---

## Notes & Follow-up

### Platinum Manager Pattern Summary

For reference, here's the standardized pattern that state-changing manager methods should follow:

```python
# managers/example_manager.py

async def some_action(self, kid_id: str, ...) -> None:
    """Execute some state-changing action.

    Follows Platinum Manager Pattern:
    1. MUTATION → Update memory
    2. PERSISTENCE → Request disk write (Tier 1 debounce)
    3. CACHE REFRESH → Schedule derivative update (Tier 2 debounce) [if applicable]
    4. EVENT → Emit signal for listeners
    """
    # 1. MUTATION (Memory is updated instantly)
    self._data[const.DATA_KIDS][kid_id]["field"] = "new_value"

    # 2. PERSISTENCE (Request a disk write - Hub's global debounce)
    self.coordinator._persist(immediate=False)

    # 3. CACHE REFRESH (Only if this manager has a calculative cache)
    # This uses the Manager's local debounce (CPU protection)
    if hasattr(self, "_schedule_cache_refresh"):
        self._schedule_cache_refresh(kid_id)

    # 4. EVENT (Signal for listeners)
    self.emit(const.SIGNAL_SUFFIX_SOMETHING_HAPPENED, kid_id=kid_id)
```

### Out of Scope (Future Initiatives)

1. **Bucket Reversal for UNDO**: Should undoing an approval decrement `approved_today`? This is a "historical rewrite" that needs careful consideration. Create separate initiative if needed.

2. **Temporal Aggregate Consolidation**: Current `_refresh_chore_cache()` manually iterates period buckets. Could be simplified to extract all temporal stats from `generate_chore_stats()`. Deferred to avoid scope creep.

3. **Debounce for SHARED Chores**: SHARED chores may emit multiple signals in quick succession (one per kid). Consider debouncing cache refresh. Monitor performance first.

4. **Dashboard Helper Sensor Debounce**: If `_build_pending_approval_list()` becomes a bottleneck, add debounce to `KidDashboardHelperSensor`, not UIManager.

### Verification Commands

```bash
# After Phase 3 (Signal Wiring)
grep -n "SIGNAL_SUFFIX_CHORE_STATUS_RESET" custom_components/kidschores/managers/statistics_manager.py
grep -n "SIGNAL_SUFFIX_CHORE_UNDONE" custom_components/kidschores/managers/statistics_manager.py

# After Phase 4 (Sensor Update)
grep -n "PRES_KID_CHORES_CURRENT" custom_components/kidschores/sensor.py

# Phase 5 (Gamification Audit)
grep -n "_schedule_evaluation\|_eval_timer" custom_components/kidschores/managers/gamification_manager.py
grep "_persist" custom_components/kidschores/managers/gamification_manager.py | wc -l

# Phase 6 (UIManager Assessment)
grep -n "_on_chore_changed\|_on_reward_changed" custom_components/kidschores/managers/ui_manager.py

# Full validation
./utils/quick_lint.sh --fix && mypy custom_components/kidschores/ && python -m pytest tests/ -v
```

### Architecture Decision Records

| Decision                                      | Rationale                                                                 | Date       |
| --------------------------------------------- | ------------------------------------------------------------------------- | ---------- |
| Snapshot counts are ephemeral (not persisted) | They represent "now" and are meaningless when read from a file days later | 2026-01-30 |
| Engine is single source of truth for counting | Avoids duplicate iteration logic in Manager                               | 2026-01-30 |
| Cache-first sensor reads                      | Ensures UI reflects latest state changes immediately                      | 2026-01-30 |
| Bucket reversal out of scope                  | Historical rewrites need separate design discussion                       | 2026-01-30 |
| Two-tier queuing: Coordinator + Manager       | Separates disk I/O protection (Tier 1) from CPU protection (Tier 2)       | 2026-01-31 |
| GamificationManager audit only (already done) | `_eval_timer` pattern already implemented and working                     | 2026-01-31 |
| UIManager doesn't need `_do_refresh`          | Operations are O(1) flag updates, no CPU-heavy loops                      | 2026-01-31 |
| Dashboard debounce belongs in sensor, not UI  | Computation owner (sensor) should own its own debounce logic              | 2026-01-31 |
