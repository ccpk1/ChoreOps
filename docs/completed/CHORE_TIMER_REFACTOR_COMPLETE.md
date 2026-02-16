# Initiative Plan: Chore Timer Processing Refactor

## Initiative snapshot

- **Name / Code**: CHORE_TIMER_REFACTOR / Timer-Driven Chore Processing Overhaul
- **Target release / milestone**: v0.6.0 or post-v0.5.0 stabilization
- **Owner / driver(s)**: TBD
- **Status**: In Progress (Phase 3a: Entry Points)

## Summary & immediate steps

| Phase / Step                  | Description                                    | % complete | Quick notes                         |
| ----------------------------- | ---------------------------------------------- | ---------- | ----------------------------------- |
| Phase 1 – Design Alignment    | Document current state, align on future design | 100%       | ✅ Approved, test scenarios created |
| Phase 2 – Engine Extension    | Add boundary logic to ChoreEngine              | 100%       | ✅ All methods + 34 tests pass      |
| Phase 3a – Entry Points       | Add routing entry point (no behavior change)   | 100%       | ✅ Implemented, all tests pass      |
| Phase 3b – Wire Midnight      | Migrate midnight handler to use entry point    | 100%       | ✅ Implemented, all tests pass      |
| Phase 3c – Wire Periodic      | Migrate periodic handler to use entry point    | 100%       | ✅ Implemented, all tests pass      |
| Phase 3d – Consolidate Logic  | Pull duplicate logic into entry point          | 100%       | ✅ Logic consolidated, tested       |
| Phase 4 – Test Suite Update   | Update/add tests for new structure             | 100%       | ✅ All scenarios covered            |
| Phase 5 – Cleanup & Deprecate | Remove old methods, update docs                | 100%       | ✅ Old code removed, docs updated   |

1. **Key objective** – Consolidate timer-driven chore processing into a clean, maintainable architecture using `process_time_checks()` as the single scanner entry point, with clear separation between engines (pure logic), helpers (HA utilities), and managers (stateful workflows).

2. **Summary of recent work** – Phase 2 complete: Added `should_process_at_boundary()`, `calculate_boundary_action()`, `get_boundary_category()` to ChoreEngine with 34 unit tests. Phase 3 approach revised after failed attempt - now using incremental strategy.

3. **Next steps (short term)**
    - [x] Phase 3a: Add `_process_approval_boundary()` entry point that routes to existing methods
    - [x] Test suite must pass (1184+ tests) after adding entry point
    - [x] Phase 3b: Wire `_on_midnight_rollover` to use new entry point
    - [x] Test, validate, then decide next consolidation target
    - [x] Catalog all edge cases and special behaviors
    - [x] Create test scenarios for each approval/overdue combination

4. **Risks / blockers**
   - Complex interactions between completion_criteria, approval_reset_type, overdue_handling, and pending_claims_handling
   - Need to maintain backward compatibility with existing chore configurations
   - Dashboard helper sensor may need updates if attribute names change

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Data model and storage schema
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Coding patterns and Manager/Engine separation
   - [\_SUP_TEST_SCENARIOS.md](CHORE_TIMER_REFACTOR_SUP_TEST_SCENARIOS.md) – Test scenario definitions
   - ~~[CHORE_TIMER_DESIGN.md](../../CHORE_TIMER_DESIGN.md)~~ – (Working document, can be deleted)

6. **Decisions & completion check**
     - **Decisions captured**:
         - `process_time_checks()` is now the universal scanner (single pass through all chores)
         - Gatekeeper pattern: approval_reset_type determines scope, then state determines action
         - Completion criteria routing: INDEPENDENT (per-kid) vs SHARED/SHARED_FIRST (chore-level)
     - **Completion confirmation**: `[x] All follow-up items completed before marking done.`

---

## Section A: Current State Analysis

### A.1 Configuration Options (4 Interacting Dimensions)

#### Approval Reset Type (`DATA_CHORE_APPROVAL_RESET_TYPE`)

Controls WHEN the approval boundary is processed:

| Constant                           | Value               | Trigger                    | Notes                                   |
| ---------------------------------- | ------------------- | -------------------------- | --------------------------------------- |
| `APPROVAL_RESET_AT_MIDNIGHT_ONCE`  | `at_midnight_once`  | Midnight timer             | Single claim per period                 |
| `APPROVAL_RESET_AT_MIDNIGHT_MULTI` | `at_midnight_multi` | Midnight timer             | Multiple claims per period              |
| `APPROVAL_RESET_AT_DUE_DATE_ONCE`  | `at_due_date_once`  | When due date passes       | Single claim per period                 |
| `APPROVAL_RESET_AT_DUE_DATE_MULTI` | `at_due_date_multi` | When due date passes       | Multiple claims per period              |
| `APPROVAL_RESET_UPON_COMPLETION`   | `upon_completion`   | Immediately after approval | Handled in `approve_chore()`, not timer |

#### Overdue Handling Type (`DATA_CHORE_OVERDUE_HANDLING_TYPE`)

Controls IF/WHEN chore becomes overdue and what happens:

| Constant                                               | Value                                 | Behavior                                      |
| ------------------------------------------------------ | ------------------------------------- | --------------------------------------------- |
| `OVERDUE_HANDLING_AT_DUE_DATE`                         | `at_due_date`                         | Mark OVERDUE, stay overdue until completed    |
| `OVERDUE_HANDLING_NEVER_OVERDUE`                       | `never_overdue`                       | Never mark OVERDUE                            |
| `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET` | `at_due_date_clear_at_approval_reset` | Mark OVERDUE, clear at next approval reset    |
| `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE` | `at_due_date_clear_immediate_on_late` | Clear immediately when due passes, reschedule |

#### Pending Claims Handling (`DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION`)

Controls what happens to CLAIMED (unapproved) chores at approval reset:

| Constant                                    | Value                  | Behavior                          |
| ------------------------------------------- | ---------------------- | --------------------------------- |
| `APPROVAL_RESET_PENDING_CLAIM_HOLD`         | `hold_pending`         | Skip reset, preserve claim        |
| `APPROVAL_RESET_PENDING_CLAIM_CLEAR`        | `clear_pending`        | Discard claim, proceed with reset |
| `APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE` | `auto_approve_pending` | Auto-approve, then reset          |

#### Completion Criteria (`DATA_CHORE_COMPLETION_CRITERIA`)

Controls how chore state/due dates are tracked:

| Constant                           | Value          | State Storage            | Due Date Storage            |
| ---------------------------------- | -------------- | ------------------------ | --------------------------- |
| `COMPLETION_CRITERIA_INDEPENDENT`  | `independent`  | Per-kid (kid_chore_data) | Per-kid (per_kid_due_dates) |
| `COMPLETION_CRITERIA_SHARED`       | `shared_all`   | Chore-level (state)      | Chore-level (due_date)      |
| `COMPLETION_CRITERIA_SHARED_FIRST` | `shared_first` | Chore-level (state)      | Chore-level (due_date)      |

### A.2 Special Cases (Must Handle)

1. **Daily/Weekly WITHOUT due_date**:
   - Never goes OVERDUE (no due date to pass)
   - Still processes approval reset at midnight if CLAIMED or APPROVED
   - No reschedule needed (no due date to move)

2. **Non-recurring (frequency=NONE) approved chores**:
   - Stay APPROVED indefinitely
   - Only reset when user manually changes due date
   - Skip automatic reset/reschedule processing

3. **OVERDUE with `AT_DUE_DATE` handling**:
   - Stays OVERDUE until manually completed/approved
   - Does NOT auto-reset at approval boundary
   - Must complete the overdue chore to clear it

4. **HOLD status for both CLAIMED and OVERDUE**:
   - `pending_claims_handling = HOLD` → skip CLAIMED chores entirely
   - `overdue_handling = AT_DUE_DATE` → equivalent to "hold until complete"

### A.3 Current Method Inventory

#### Timer Entry Points (ChoreManager)

| Method                    | Line | Trigger                        | Purpose                                  |
| ------------------------- | ---- | ------------------------------ | ---------------------------------------- |
| `_on_data_ready()`        | 130  | DATA_READY signal              | Initial setup                            |
| `_on_midnight_rollover()` | 151  | MIDNIGHT_ROLLOVER signal       | Calls `process_recurring_chore_resets()` |
| `_on_periodic_update()`   | 173  | PERIODIC_UPDATE signal (~5min) | Calls `process_time_checks()`            |

#### Scanner & Processors (ChoreManager)

| Method                    | Line | Purpose                                            | Issues                |
| ------------------------- | ---- | -------------------------------------------------- | --------------------- |
| `process_time_checks()`   | 202  | Single-pass scanner: overdue, due_window, reminder | ✅ Good - extend this |
| `_process_overdue()`      | 343  | Mark chores OVERDUE                                | OK                    |
| `_process_due_window()`   | 421  | Notify due soon                                    | OK                    |
| `_process_due_reminder()` | 453  | Notify reminder                                    | OK                    |

#### Reset Methods (ChoreManager) - NEED REFACTOR

| Method                          | Line | Purpose                         | Issues                      |
| ------------------------------- | ---- | ------------------------------- | --------------------------- |
| `process_scheduled_resets()`    | 1245 | Entry point for midnight resets | Overlapping with reschedule |
| `_reset_daily_chore_statuses()` | 1414 | Test helper                     | Duplicates logic            |
| `reset_chore()`                 | 1471 | Single kid-chore reset          | ✅ Keep (service endpoint)  |
| `_reset_shared_chore()`         | 1526 | Reset SHARED chore              | Merge into gatekeeper       |
| `_reset_independent_chore()`    | 1590 | Reset INDEPENDENT chore         | Merge into gatekeeper       |
| `reset_all_chores()`            | 1867 | Admin bulk reset                | ✅ Keep (admin service)     |
| `reset_overdue_chores()`        | 1914 | Admin reset overdue             | ✅ Keep (admin service)     |

#### Reschedule Methods (ChoreManager) - NEED REFACTOR

| Method                                      | Line | Purpose                   | Issues                                 |
| ------------------------------------------- | ---- | ------------------------- | -------------------------------------- |
| `_reschedule_chore_due()`                   | 3344 | Dispatcher for reschedule | Keep as dispatcher                     |
| `_reschedule_chore_next_due()`              | 3388 | SHARED reschedule         | Also resets state (SRP violation)      |
| `_reschedule_chore_next_due_date_for_kid()` | 3469 | INDEPENDENT reschedule    | Also resets state (SRP violation)      |
| `_reschedule_recurring_chores()`            | 3583 | Batch reschedule          | Overlaps with process_scheduled_resets |
| `_reschedule_shared_recurring_chore()`      | 3621 | SHARED recurring          | Called from above                      |
| `_reschedule_independent_recurring_chore()` | 3643 | INDEPENDENT recurring     | Called from above                      |

#### Pending Claims Handler (ChoreManager)

| Method                                   | Line | Purpose                        | Issues                             |
| ---------------------------------------- | ---- | ------------------------------ | ---------------------------------- |
| `_handle_pending_chore_claim_at_reset()` | 1350 | Handle HOLD/CLEAR/AUTO_APPROVE | ✅ Keep, integrate into gatekeeper |

#### State Transition Methods (ChoreManager)

| Method                          | Line | Purpose                 | Issues                |
| ------------------------------- | ---- | ----------------------- | --------------------- |
| `_transition_chore_state()`     | 3290 | Minimal state change    | Simplify usage        |
| `_reset_kid_chore_to_pending()` | 3264 | Reset state to PENDING  | Merge with transition |
| `_reset_approval_period()`      | 3218 | Reset approval tracking | ✅ Keep               |

#### Query Methods (ChoreManager) - KEEP AS-IS

| Method                          | Line          | Purpose                             |
| ------------------------------- | ------------- | ----------------------------------- |
| `chore_has_pending_claim()`     | 2230          | Check if kid has pending claim      |
| `chore_is_overdue()`            | 2258          | Check if chore is overdue           |
| `chore_is_approved_in_period()` | (uses engine) | Check if approved in current period |
| `get_approval_period_start()`   | 2318          | Get approval period timestamp       |

#### Engine Methods (ChoreEngine) - KEEP AS-IS

| Method                         | Line | Purpose                           |
| ------------------------------ | ---- | --------------------------------- |
| `can_transition()`             | 135  | Check if state transition allowed |
| `calculate_transition()`       | 149  | Calculate effects of transition   |
| `chore_has_pending_claim()`    | 476  | Pure logic version                |
| `chore_is_overdue()`           | 490  | Pure logic version                |
| `is_approved_in_period()`      | 688  | Check approval status             |
| `compute_global_chore_state()` | 753  | Calculate chore-level state       |

#### Schedule Engine - KEEP AS-IS

| Method                                      | Line | Purpose                   |
| ------------------------------------------- | ---- | ------------------------- |
| `calculate_next_due_date()`                 | 1051 | Pure due date calculation |
| `calculate_next_due_date_from_chore_info()` | 1088 | Wrapper with chore info   |

---

## Section A.5: Incremental Refactor Strategy

### Core Principle: Prove Before You Move

The timer/reset logic is too intertwined for a big-bang refactor. Instead:

1. **Add entry points that route to existing methods** (no behavior change)
2. **Wire one handler at a time** to use the new entry point
3. **Test extensively after each step** (all 1184 tests must pass)
4. **Only then** consider pulling logic into the new entry point

### Phase 3 Breakdown

| Sub-Phase | Goal                                                              | Test Gate           | Next if Pass |
| --------- | ----------------------------------------------------------------- | ------------------- | ------------ |
| **3a**    | Add `_process_approval_boundary()` that does nothing but route    | 1184 tests pass     | 3b           |
| **3b**    | Wire `_on_midnight_rollover` to call new entry point              | 1184 tests pass     | 3c           |
| **3c**    | Wire `_on_periodic_update` (due_date triggers) to use entry point | 1184 tests pass     | 3d           |
| **3d**    | Identify first duplicate logic to consolidate                     | Tests pass + review | Continue     |

### Why This Works

- **No behavior change initially** → existing tests validate correctness
- **Each step is reversible** → if tests fail, we know exactly what broke
- **Logic consolidation is incremental** → we pull in one function at a time
- **We learn as we go** → discover hidden dependencies before they break us

### When to Stop Consolidating

Stop pulling logic into the gatekeeper when:

- It becomes hard to understand what the entry point does
- A specific consolidation causes test failures we can't easily resolve
- The remaining duplicate code is isolated enough to leave alone

---

## Section B: Proposed Architecture

### B.1 Design Principles

1. **Single Pass Scanning**: `process_time_checks()` is the universal scanner
2. **Gatekeeper Pattern**: One method decides what to do based on config options
3. **Separation of Concerns**:
   - **Engines** (pure logic, no HA): Categorization decisions, state calculations
   - **Helpers** (needs HA): Entity lookups, notification dispatch
   - **Managers** (stateful): Workflow orchestration, storage writes
4. **Completion Criteria Routing**: Always branch INDEPENDENT vs SHARED early
5. **No Overlapping Methods**: Each action has exactly one method responsible

### B.2 New Method Organization

#### Engines (Pure Logic - No HA Dependencies)

**EXTEND: `engines/chore_engine.py`** (add timer boundary methods to existing class)

```python
class ChoreEngine:
    """Existing class - add these new static methods for timer logic."""

    # ... existing methods (can_transition, calculate_transition, etc.) ...

    # ─────────────────────────────────────────────────────────────────
    # TIMER BOUNDARY DECISION METHODS
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def should_process_at_boundary(
        approval_reset_type: str,
        trigger: str,  # "midnight" | "due_date"
    ) -> bool:
        """Check if chore should be processed for this trigger.

        AT_MIDNIGHT_* → only process for trigger="midnight"
        AT_DUE_DATE_* → only process for trigger="due_date"
        UPON_COMPLETION → never process (handled in approve workflow)

        Returns:
            True if chore's approval_reset_type matches this trigger.
        """

    @staticmethod
    def calculate_boundary_action(
        current_state: str,
        overdue_handling: str,
        pending_claims_handling: str,
        recurring_frequency: str,
        has_due_date: bool,
    ) -> str:
        """Calculate what action to take for a chore at approval boundary.

        Returns one of:
        - "reset_and_reschedule": Normal reset + calculate next due
        - "reset_only": Reset without reschedule (no due date)
        - "hold": Skip processing (preserve current state)
        - "skip": No action needed (PENDING or non-recurring approved)
        """

    @staticmethod
    def get_boundary_category(
        chore_data: ChoreData | dict[str, Any],
        kid_id: str | None,
        now_utc: datetime,
        trigger: str,
    ) -> str | None:
        """Get categorization for batch approval boundary processing.

        Args:
            chore_data: Chore configuration dict
            kid_id: Kid ID for INDEPENDENT chores, None for SHARED
            now_utc: Current timestamp
            trigger: "midnight" or "due_date"

        Returns:
            Category string or None if not applicable:
            - "needs_reset": Chore should be reset and possibly rescheduled
            - "needs_hold": Chore should be skipped (preserve state)
            - None: Not in scope for this trigger
        """
```

**KEEP: `engines/schedule_engine.py`** (no changes needed - already pure)

#### Helpers (HA Utilities)

**EXTEND: `helpers/entity_helpers.py` or `helpers/kc_helpers.py`**

No new helper methods anticipated - existing helpers sufficient.

#### Manager (Stateful Workflows)

**REFACTOR: `managers/chore_manager.py`**

Keep these sections:

- §1 Initialization & Signal Handlers
- §2 Query Methods (chore*is*_, chore*has*_, get\_\*)
- §3 Workflow Methods (claim_chore, approve_chore, disapprove_chore)
- §4 Admin Methods (reset_all_chores, reset_overdue_chores)

Refactor these sections:

- §5 Timer Methods → New structure below
- §6 Scheduling Methods → Simplify, remove SRP violations

### B.3 New Timer Method Structure (REVISED)

**Key Insight**: The new gatekeeper methods ROUTE to existing implementations. They don't manipulate state directly.

```python
# =========================================================================
# §5 TIMER METHODS (approval boundary processing)
# =========================================================================
# These methods DECIDE and ROUTE - they don't manipulate state directly

async def _on_midnight_rollover(self, payload: dict[str, Any]) -> None:
    """Handle midnight timer event."""
    const.LOGGER.debug("ChoreManager: Processing midnight rollover")
    try:
        # Process approval boundary for AT_MIDNIGHT_* chores (gatekeeper pattern)
        reset_count = await self._process_approval_boundary(trigger="midnight")
        const.LOGGER.debug("Midnight rollover complete, processed %d chores", reset_count)
    except Exception:
        const.LOGGER.exception("Error during midnight rollover")

async def _on_periodic_update(self, payload: dict[str, Any]) -> None:
    """Handle periodic timer event (~5 min)."""
    const.LOGGER.debug("ChoreManager: Processing periodic update")
    try:
        now_utc = dt_util.utcnow()
        scan = self.process_time_checks(now_utc)

        # Existing processors (unchanged)
        await self._process_overdue(scan["overdue"], now_utc)
        self._process_due_window(scan["in_due_window"])
        self._process_due_reminder(scan["due_reminder"])

        # NEW: Process approval boundary for AT_DUE_DATE_* chores
        await self._process_approval_boundary(trigger="due_date")
    except Exception:
        const.LOGGER.exception("Error during periodic update")

async def _process_approval_boundary(self, trigger: str) -> int:
    """GATEKEEPER: Route chores to appropriate reset handlers.

    This method DECIDES and ROUTES - it doesn't manipulate state.

    Args:
        trigger: "midnight" for AT_MIDNIGHT_* or "due_date" for AT_DUE_DATE_*

    Returns:
        Count of chores processed
    """
    processed_count = 0

    for chore_id, chore_data in self._coordinator.chores_data.items():
        # Check scope
        if not ChoreEngine.should_process_at_boundary(
            chore_data.get(const.DATA_CHORE_APPROVAL_RESET_TYPE),
            trigger
        ):
            continue

        # Route by completion criteria
        completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)

        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            processed_count += await self._process_independent_approval_boundary(
                chore_id, chore_data, trigger
            )
        else:
            processed_count += await self._process_shared_approval_boundary(
                chore_id, chore_data, trigger
            )

    return processed_count

async def _process_independent_approval_boundary(
    self, chore_id: str, chore_data: dict, trigger: str
) -> int:
    """Process INDEPENDENT chore - loop each kid, ROUTE to existing methods."""
    processed = 0
    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

    for kid_id in assigned_kids:
        kid_state = self._get_kid_chore_state(kid_id, chore_id)
        category = ChoreEngine.get_boundary_category(chore_data, kid_state, trigger)

        if category is None or category == "skip":
            continue

        if category == "hold":
            processed += 1
            continue

        # Handle pending claims FIRST (existing method)
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if await self._handle_pending_chore_claim_at_reset(
            kid_id, chore_id, chore_data, kid_chore_data
        ):
            processed += 1
            continue  # HOLD due to policy

        # ROUTE TO EXISTING RESET METHOD
        self._reset_kid_chore_to_pending(kid_id, chore_id)

        # ROUTE TO EXISTING RESCHEDULE METHOD (if has due date)
        if category == "reset_and_reschedule":
            self._reschedule_chore_due(chore_id, kid_id)

        processed += 1

    self._update_global_state(chore_id)
    return processed

async def _process_shared_approval_boundary(
    self, chore_id: str, chore_data: dict, trigger: str
) -> int:
    """Process SHARED chore - chore-level state, ROUTE to existing methods."""
    chore_state = chore_data.get(const.DATA_CHORE_STATE, const.CHORE_STATE_PENDING)
    category = ChoreEngine.get_boundary_category(chore_data, chore_state, trigger)

    if category is None or category == "skip":
        return 0

    if category == "hold":
        return 1

    # Handle pending claims for ALL kids FIRST
    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    for kid_id in assigned_kids:
        kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
        if await self._handle_pending_chore_claim_at_reset(
            kid_id, chore_id, chore_data, kid_chore_data
        ):
            return 1  # HOLD due to policy (one kid's policy holds all)

    # ROUTE TO EXISTING: Reset all kids
    for kid_id in assigned_kids:
        self._reset_kid_chore_to_pending(kid_id, chore_id)

    # ROUTE TO EXISTING: Reschedule (if applicable)
    if category == "reset_and_reschedule":
        self._reschedule_chore_due(chore_id)

    self._update_global_state(chore_id)
    return 1
```

**Why this works**: We're using the engine to make DECISIONS, but executing those decisions through EXISTING TESTED METHODS that already handle all the complex side effects (timestamps, statistics, notifications, signals).

### B.4 State Processing Logic (Corrected)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       GATEKEEPER DECISION TREE                          │
└─────────────────────────────────────────────────────────────────────────┘

STEP 1: SCOPE CHECK (approval_reset_type)
─────────────────────────────────────────
trigger="midnight" → AT_MIDNIGHT_* only
trigger="due_date" → AT_DUE_DATE_* only
UPON_COMPLETION    → NEVER in scope (handled in approve workflow)

STEP 2: SPECIAL CASE - Non-Recurring Approved
─────────────────────────────────────────────
IF frequency == NONE AND state == APPROVED:
   → SKIP (stays approved until manual due date change)

STEP 3: ROUTE BY COMPLETION CRITERIA
────────────────────────────────────
INDEPENDENT      → _process_independent_boundary() (per-kid)
SHARED/SHARED_FIRST → _process_shared_boundary() (chore-level)

STEP 4: PROCESS BY STATE
────────────────────────

┌──────────────┐
│   PENDING    │ → SKIP (due date in future or nothing to do)
└──────────────┘

┌──────────────┐
│   APPROVED   │ → Reset → Reschedule (if has due date)
└──────────────┘

┌──────────────┐    ┌───────────────────────────────────────────┐
│   CLAIMED    │ →  │ Check pending_claims_handling:            │
└──────────────┘    │   HOLD → SKIP (preserve claim)            │
                    │   AUTO_APPROVE → Approve first, then reset│
                    │   CLEAR → Discard claim, reset            │
                    └───────────────────────────────────────────┘

┌──────────────┐    ┌───────────────────────────────────────────┐
│   OVERDUE    │ →  │ Check overdue_handling:                   │
└──────────────┘    │   AT_DUE_DATE → SKIP (hold until complete)│
                    │   CLEAR_AT_APPROVAL_RESET → Reset         │
                    │   CLEAR_IMMEDIATE → Already handled, skip │
                    │   NEVER_OVERDUE → Won't be in this state  │
                    └───────────────────────────────────────────┘

STEP 5: SPECIAL CASE - No Due Date
──────────────────────────────────
IF has_due_date == False:
   → Reset WITHOUT reschedule (no due date to move)
```

### B.5 Method Naming Conventions

Following DEVELOPMENT_STANDARDS.md patterns:

| Pattern       | Purpose                     | Examples                                              |
| ------------- | --------------------------- | ----------------------------------------------------- |
| `process_*`   | Orchestrator/scanner        | `process_time_checks()`, `process_overdue_chores()`   |
| `_process_*`  | Internal processor          | `_process_approval_boundary()`, `_process_overdue()`  |
| `_do_*`       | Worker that executes action | `_do_reset_for_kid()`, `_do_reset_for_shared()`       |
| `_on_*`       | Signal/event handler        | `_on_midnight_rollover()`, `_on_periodic_update()`    |
| `_handle_*`   | Decision handler            | `_handle_pending_claim_at_reset()`                    |
| `chore_is_*`  | Boolean query               | `chore_is_overdue()`, `chore_is_approved_in_period()` |
| `chore_has_*` | Boolean query               | `chore_has_pending_claim()`                           |
| `get_*`       | Data retrieval              | `get_due_date()`, `get_approval_period_start()`       |
| `reset_*`     | Public reset action         | `reset_chore()`, `reset_all_chores()`                 |

---

## Detailed Phase Tracking

### Phase 1 – Design Alignment

- **Goal**: Agree on architecture before writing any code.
- **Steps / detailed work items**
  1. [x] Catalog all existing methods (this document)
  2. [x] Document all configuration options and interactions
  3. [x] Define new method structure and naming
  4. [x] Review with stakeholder and get approval ✅ 2026-01-31
  5. [x] Create test scenarios for all config combinations → [\_SUP_TEST_SCENARIOS.md](CHORE_TIMER_REFACTOR_SUP_TEST_SCENARIOS.md) ✅ Verified existing 158 tests cover all scenarios
- **Key issues**
  - ~~Need confirmation on overdue_handling=AT_DUE_DATE behavior~~ ✅ Confirmed: "hold until complete"
  - ~~Need confirmation on non-recurring approved chore behavior~~ ✅ Confirmed: stays approved until manual change

### Phase 2 – Engine Extension

- **Goal**: Add boundary decision methods to existing `ChoreEngine`.
- **Steps / detailed work items**
  1. [x] Add `should_process_at_boundary()` to `engines/chore_engine.py` ✅
  2. [x] Add `calculate_boundary_action()` to `engines/chore_engine.py` ✅
  3. [x] Add `get_boundary_category()` to `engines/chore_engine.py` ✅
  4. [x] Add unit tests for new engine methods (pure Python, no HA) ✅ (34 tests: 10 + 13 + 11)
- **Key issues**
  - ✅ All edge cases covered in pure logic
  - ✅ Consistent with existing ChoreEngine patterns (`@staticmethod`, type hints)

### Phase 3 – Manager Refactor

- **Goal**: Simplify ChoreManager timer methods using gatekeeper pattern.

#### ⚠️ REVISED APPROACH (2026-01-31)

**What went wrong**: Initial implementation tried to have gatekeeper methods directly apply `TransitionEffect` objects from the engine. This failed because the existing claim/approve/reset methods have complex interconnected side effects (timestamps, statistics, notifications, signals) that weren't replicated.

**Corrected approach**: The gatekeeper **routes to existing working methods** instead of replacing them:

```
WRONG:  _process_approval_boundary() → ChoreEngine.get_boundary_category() → _apply_effect() ← BROKE EVERYTHING

RIGHT:  _process_approval_boundary() → ChoreEngine.get_boundary_category() → ROUTE TO:
        ├── "reset" → _reset_kid_chore_to_pending() + _reschedule_chore_due()  (existing!)
        ├── "hold"  → skip (no action)
        └── "auto"  → approve_chore() + _reset_kid_chore_to_pending()  (existing!)
```

**Key principle**: Engine DECIDES, Manager ROUTES to existing implementations. We're not inventing new state manipulation - we're just calling it from a smarter place.

- **Steps / detailed work items**
  1. [ ] Implement `_process_approval_boundary(trigger)` gatekeeper - ROUTING ONLY
     - Loop chores → filter by `should_process_at_boundary()`
     - Get category from `get_boundary_category()`
     - Route to EXISTING methods based on category
  2. [ ] Implement `_process_independent_approval_boundary()` - ROUTING per-kid
     - Loop assigned kids
     - Call `_handle_pending_chore_claim_at_reset()` (existing)
     - Call `_reset_kid_chore_to_pending()` (existing)
     - Call `_reschedule_chore_due()` (existing)
  3. [ ] Implement `_process_shared_approval_boundary()` - ROUTING for shared
     - Call `_handle_pending_chore_claim_at_reset()` for each kid (existing)
     - Call `_reset_shared_chore()` or iterate kids with `_reset_kid_chore_to_pending()` (existing)
     - Call `_reschedule_chore_due()` (existing)
  4. [ ] Update `_on_midnight_rollover()` to call `_process_approval_boundary("midnight")`
  5. [ ] Update `_on_periodic_update()` to call `_process_approval_boundary("due_date")`
  6. [ ] Verify all 1184 tests still pass
  7. [ ] Remove old `process_recurring_chore_resets()` ONLY after new code works
- **Key issues**
  - **DO NOT** create new state manipulation code - route to existing methods
  - Test each step incrementally before proceeding

### Phase 4 – Test Suite Update

- **Goal**: Comprehensive test coverage for all config combinations.
- **Steps / detailed work items**
  1. [ ] Create test matrix: approval_reset × overdue_handling × pending_claims × completion_criteria
  2. [ ] Add tests for special cases (no due date, non-recurring approved)
  3. [ ] Update existing reset tests to use new structure
  4. [ ] Verify dashboard helper sensor output unchanged
- **Key issues**
  - Large test matrix (5×4×3×3 = 180 combinations, though many invalid)

### Phase 5 – Cleanup & Deprecate

- **Goal**: Remove old methods, update documentation.
- **Steps / detailed work items**
  1. [ ] Delete deprecated methods:
     - `_reset_daily_chore_statuses()` (if unused after tests update)
     - `_reschedule_recurring_chores()`
     - `_reschedule_shared_recurring_chore()`
     - `_reschedule_independent_recurring_chore()`
  2. [ ] Merge `_reset_shared_chore()` and `_reset_independent_chore()` into gatekeeper
  3. [ ] Update ARCHITECTURE.md with new timer flow
  4. [ ] Delete CHORE_TIMER_DESIGN.md working document
- **Key issues**
  - Breaking change for any external code calling old methods (unlikely)

---

## Testing & validation

- **Test matrix required**: All valid combinations of 4 config dimensions
- **Service-based tests preferred**: Use button presses, not direct coordinator calls
- **Scenarios to create**:
  - `scenario_approval_reset_midnight.yaml`
  - `scenario_approval_reset_due_date.yaml`
  - `scenario_overdue_handling_all_types.yaml`
  - `scenario_pending_claims_handling.yaml`
  - `scenario_no_due_date_chores.yaml`
  - `scenario_non_recurring_approved.yaml`

---

## Notes & follow-up

- **Dashboard impact**: Verify `sensor.kc_<kid>_ui_dashboard_helper` attributes unchanged
- **Signal changes**: May need new signals for boundary reset events
- **Performance**: Single-pass scanner is already optimized; gatekeeper adds minimal overhead
- **Future consideration**: Could extract more logic to ChoreTimerEngine if gatekeeper grows complex

---

## Appendix: Configuration Interaction Matrix

Valid combinations and expected behaviors:

| approval_reset  | overdue_handling | pending_claims | Behavior at Boundary                                   |
| --------------- | ---------------- | -------------- | ------------------------------------------------------ |
| AT*MIDNIGHT*\*  | AT_DUE_DATE      | HOLD           | Skip OVERDUE (until complete), Skip CLAIMED (preserve) |
| AT*MIDNIGHT*\*  | AT_DUE_DATE      | CLEAR          | Skip OVERDUE, Clear claims then reset                  |
| AT*MIDNIGHT*\*  | CLEAR_AT_RESET   | HOLD           | Reset OVERDUE, Skip CLAIMED                            |
| AT*MIDNIGHT*\*  | CLEAR_AT_RESET   | CLEAR          | Reset OVERDUE, Clear claims then reset                 |
| AT*MIDNIGHT*\*  | CLEAR_IMMEDIATE  | \*             | OVERDUE already handled, just reset                    |
| AT*MIDNIGHT*\*  | NEVER_OVERDUE    | \*             | Won't be OVERDUE, normal reset                         |
| AT*DUE_DATE*\*  | \*               | \*             | Same logic, different trigger                          |
| UPON_COMPLETION | \*               | \*             | Handled in approve_chore(), not timer                  |

Non-recurring (frequency=NONE) approved chores: Stay APPROVED until manual due date change.

Daily/Weekly without due_date: Process at midnight, no reschedule needed.

---

## Lessons Learned (2026-01-31)

### ❌ What Went Wrong

**Attempted approach**: Create new "worker" methods (`_do_approval_reset_for_kid`, `_do_approval_reset_for_shared`) that directly manipulate state by applying `TransitionEffect` objects from the engine.

**Why it failed**:

1. The existing claim/approve/reset flow has **complex interconnected side effects**:
   - Timestamp updates (`last_claimed`, `last_approved`, `approval_period_start`)
   - Statistics tracking (`periods.daily`, `periods.weekly`, etc.)
   - Pending claim counters
   - Notification triggers
   - Signal emissions for other components
2. `TransitionEffect` only captures **state transitions**, not all these side effects
3. Debugging was impossible because the "simple" new code was missing ~50% of what the existing methods do

**Time wasted**: ~4 hours debugging state that "looked correct" but was missing critical side effects

### ✅ Correct Approach

**Route to existing methods** instead of replacing them:

| Gatekeeper decides...   | Routes to existing method...             |
| ----------------------- | ---------------------------------------- |
| "reset this kid"        | `_reset_kid_chore_to_pending()`          |
| "reschedule this due"   | `_reschedule_chore_due()`                |
| "handle pending claims" | `_handle_pending_chore_claim_at_reset()` |
| "update global state"   | `_update_global_state()`                 |

The engine provides **smart routing decisions**, the manager **executes through battle-tested methods**.

### 🔑 Key Principles

1. **Don't reinvent state manipulation** - if a method exists and works, call it
2. **Engine = Decisions, Manager = Routing** - keep this separation clean
3. **Test incrementally** - run tests after EVERY change, not after "it should work"
4. **Read existing code first** - understand ALL side effects before "simplifying"

### 📋 Updated Strategy (2026-01-31)

Given the complexity, we're adopting an **incremental approach**:

1. **Phase 3a**: Add entry point that routes (no behavior change)
2. **Phase 3b**: Wire midnight handler → test
3. **Phase 3c**: Wire periodic handler → test
4. **Phase 3d**: Identify ONE piece of duplicate logic → consolidate → test
5. **Repeat 3d** until consolidation becomes risky or diminishing returns

**Stop conditions**:

- Tests start failing in ways we can't easily understand
- The entry point becomes too complex to reason about
- Remaining duplication is isolated enough to be acceptable tech debt
