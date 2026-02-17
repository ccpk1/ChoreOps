# Blueprint: Chore Logic v0.5.0 — Implementation Specification

_Supporting document for [CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md)_
_All design decisions resolved. **Rotation Design v2 applied** (2026-02-12): 2 rotation criteria + steal-as-overdue._
_See plan document "⚠️ ROTATION DESIGN v2" section for authoritative behavioral definitions._
_See plan document "⚠️ APPROVAL CYCLE PROCESSING MODEL" section for mandatory three-lane vocabulary._

---

## Table of Contents

1. [Data Model Changes](#1-data-model-changes)
2. [Logic Adapter Pattern — Specification & Refactoring Guide](#2-logic-adapter-pattern)
3. [8-Tier FSM — State Resolution Engine](#3-8-tier-fsm)
4. [Rotation Advancement — Complete Flow](#4-rotation-advancement)
5. [Claim Restriction — Due Window Blocking](#5-claim-restriction)
6. [Missed Lock — 6th Overdue Strategy](#6-missed-lock)
7. [Criteria Transition — Mutable Completion Criteria](#7-criteria-transition)
8. [Service Changes — Schema & Handlers](#8-service-changes)
9. [Migration Extension — v44 Backfill](#9-migration-extension)
10. [Dashboard & Sensor Integration](#10-dashboard-sensor-integration)
11. [Statistics Integration — Smart Rotation Query](#11-statistics-integration)
12. [Notification Wiring](#12-notification-wiring)
13. [Validation Rules — Complete Set](#13-validation-rules)
14. [Constant & Translation Inventory](#14-constant-translation-inventory)

---

## 1. Data Model Changes

### 1.1 New Fields in `ChoreData` TypedDict

**File**: `custom_components/kidschores/type_defs.py`

```python
class ChoreData(TypedDict):
    # ... existing fields unchanged ...

    # NEW — Due Window Claim Restrictions (D-04)
    claim_restriction_enabled: NotRequired[bool]

    # NEW — Rotation State (D-05, D-12)
    rotation_current_kid_id: NotRequired[str | None]   # UUID of current turn holder
    rotation_cycle_override: NotRequired[bool]          # True = any kid can claim
```

### 1.2 New Completion Criteria Values (D-05 revised, D-12)

**File**: `custom_components/kidschores/const.py`

```python
# Existing (unchanged)
COMPLETION_CRITERIA_SHARED: Final = "shared_all"
COMPLETION_CRITERIA_INDEPENDENT: Final = "independent"
COMPLETION_CRITERIA_SHARED_FIRST: Final = "shared_first"

# NEW — Rotation sub-types (D-05 revised: 2 types, NOT 3)
COMPLETION_CRITERIA_ROTATION_SIMPLE: Final = "rotation_simple"
COMPLETION_CRITERIA_ROTATION_SMART: Final = "rotation_smart"
# NOTE: rotation_steal REMOVED — steal mechanic is now an overdue handling type (D-06 revised)

# Update options list — 5 entries total
COMPLETION_CRITERIA_OPTIONS: Final = [
    {"value": COMPLETION_CRITERIA_SHARED, "label": "shared_all"},
    {"value": COMPLETION_CRITERIA_INDEPENDENT, "label": "independent"},
    {"value": COMPLETION_CRITERIA_SHARED_FIRST, "label": "shared_first"},
    {"value": COMPLETION_CRITERIA_ROTATION_SIMPLE, "label": "rotation_simple"},
    {"value": COMPLETION_CRITERIA_ROTATION_SMART, "label": "rotation_smart"},
]
```

### 1.3 New Overdue Handling Types (D-02, D-06 revised)

```python
# Existing 5 types unchanged
# NEW — 6th type: strict lock until midnight
OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK: Final = "at_due_date_mark_missed_and_lock"

# NEW — 7th type: steal window for rotation chores (D-06 revised)
OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL: Final = "at_due_date_allow_steal"

# Update options list — 7 entries total
OVERDUE_HANDLING_TYPE_OPTIONS: Final = [
    # ... existing 5 entries ...
    {"value": OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK,
     "label": "at_due_date_mark_missed_and_lock"},
    {"value": OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL,
     "label": "at_due_date_allow_steal"},
]
```

### 1.4 New Chore States (Display-Only, Calculated)

```python
# These are CALCULATED states — they do not persist in storage.
# The engine resolves them at runtime based on chore config + time.
CHORE_STATE_WAITING: Final = "waiting"         # Before due window opens
CHORE_STATE_NOT_MY_TURN: Final = "not_my_turn" # Rotation: another kid's turn
CHORE_STATE_MISSED: Final = "missed"           # Strict lock: past due, locked out
```

### 1.5 Storage Key Constants

```python
DATA_CHORE_CLAIM_RESTRICTION_ENABLED: Final = "claim_restriction_enabled"
DATA_CHORE_ROTATION_CURRENT_KID_ID: Final = "rotation_current_kid_id"
DATA_CHORE_ROTATION_CYCLE_OVERRIDE: Final = "rotation_cycle_override"
```

---

## 2. Logic Adapter Pattern

### 2.1 Specification (D-12)

**Purpose**: Prevent "gremlin code" across ~60 criteria check sites. Two static methods that classify criteria values into behavioral categories.

**File**: `custom_components/kidschores/engines/chore_engine.py`

```python
@staticmethod
def is_single_claimer_mode(chore_data: ChoreData | dict[str, Any]) -> bool:
    """Return True if only one kid can claim/complete per cycle.

    Covers shared_first AND all rotation types. These criteria share
    the same claim-blocking behavior: once one kid claims, others cannot.

    Use this instead of checking '== COMPLETION_CRITERIA_SHARED_FIRST' directly.
    """
    criteria = chore_data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )
    return criteria in (
        const.COMPLETION_CRITERIA_SHARED_FIRST,
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        const.COMPLETION_CRITERIA_ROTATION_SMART,
    )

@staticmethod
def is_rotation_mode(chore_data: ChoreData | dict[str, Any]) -> bool:
    """Return True if chore uses any rotation sub-type.

    Used for rotation-specific logic: turn advancement, override,
    steal-via-overdue mechanics. NOT for claim-blocking (use is_single_claimer_mode).
    """
    criteria = chore_data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )
    return criteria in (
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        const.COMPLETION_CRITERIA_ROTATION_SMART,
    )
```

### 2.2 Updated `is_shared_chore()`

```python
@staticmethod
def is_shared_chore(chore_data: ChoreData | dict[str, Any]) -> bool:
    """Return True if chore involves multiple kids (shared or rotation).

    Updated to include rotation types — rotation chores ARE multi-kid chores.
    """
    criteria = chore_data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_SHARED,
    )
    return criteria in (
        const.COMPLETION_CRITERIA_SHARED,
        const.COMPLETION_CRITERIA_SHARED_FIRST,
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        const.COMPLETION_CRITERIA_ROTATION_SMART,
    )
```

### 2.3 Refactoring Guide — Adapter Adoption

**Strategy**: Replace inline criteria checks with adapter calls. The three-way branching pattern transforms:

```
BEFORE (current pattern — repeated ~60 times):
┌─────────────────────────────────────────────────────┐
│ if criteria == SHARED_FIRST:                        │
│     # single-claimer logic                          │
│ elif criteria == SHARED:                            │
│     # all-kids logic                                │
│ else:  # INDEPENDENT                               │
│     # per-kid logic                                 │
└─────────────────────────────────────────────────────┘

AFTER (adapter pattern — rotation works automatically):
┌─────────────────────────────────────────────────────┐
│ if ChoreEngine.is_single_claimer_mode(chore):       │
│     # shared_first + rotation_* all get this path   │
│ elif criteria == SHARED:                            │
│     # all-kids logic (unchanged)                    │
│ else:  # INDEPENDENT                               │
│     # per-kid logic (unchanged)                     │
└─────────────────────────────────────────────────────┘
```

**File-by-file adoption priority** (by impact density):

| Priority | File                             | Sites | Refactoring Notes                                                                                              |
| -------- | -------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------- |
| 1        | `managers/chore_manager.py`      | 25    | Heaviest target. Each `== SHARED_FIRST` → `is_single_claimer_mode()`. Test after.                              |
| 2        | `engines/chore_engine.py`        | 10    | Update `can_claim_chore()`, `compute_global_state()`, `calculate_transition()`.                                |
| 3        | `options_flow.py`                | 6     | Per-kid step gating. `INDEPENDENT`-only checks can remain as-is.                                               |
| 4        | `helpers/flow_helpers.py`        | 5     | Form building. `transform_chore_cfof_to_data()` per-kid date routing.                                          |
| 5        | `sensor.py`                      | 4     | Entity creation gating + attribute routing.                                                                    |
| 6        | `data_builders.py`               | 3     | Validation + build defaults.                                                                                   |
| 7        | `services.py`                    | 3     | Service input validation.                                                                                      |
| 8        | `schedule_engine.py`             | 2     | Per-kid vs chore-level date/day routing.                                                                       |
| 9        | `helpers/entity_helpers.py`      | 1     | **Bug fix**: `cleanup_orphaned_shared_state_sensors()` checks `SHARED` only, misses `SHARED_FIRST` + rotation. |
| 10       | `managers/statistics_manager.py` | 1     | Daily snapshot due-date lookup.                                                                                |

**Directive**: Convert file-by-file, running `pytest tests/` after each file. Do NOT attempt all 60 sites in one commit.

---

## 3. 8-Tier FSM

### 3.1 State Priority Diagram

```
                           ┌──────────────┐
                           │ P1: approved │  ← is_approved_in_period
                           └──────┬───────┘
                                  │ no
                           ┌──────▼───────┐
                           │ P2: claimed  │  ← has_pending_claim
                           └──────┬───────┘
                                  │ no
                    ┌─────────────▼──────────────┐
                    │ P3: not_my_turn             │  ← is_rotation_mode AND
                    │   (allow_steal exception:   │     kid ≠ current_turn AND
                    │    skip if overdue_handling  │     NOT (allow_steal AND past_due)
                    │    == allow_steal + past due)│     AND override == False
                    └─────────────┬──────────────┘
                                  │ no
                     ┌────────────▼────────────┐
                     │ P4: missed              │  ← overdue == mark_missed_and_lock
                     │   (terminal until reset) │     AND now > due_date
                     └────────────┬────────────┘
                                  │ no
                      ┌───────────▼───────────┐
                      │ P5: overdue           │  ← relaxed overdue type
                      │   (still claimable)    │     AND now > due_date
                      └───────────┬───────────┘
                                  │ no
                       ┌──────────▼──────────┐
                       │ P6: waiting         │  ← claim_restriction AND
                       │   (before window)    │     now < window_start
                       └──────────┬──────────┘
                                  │ no
                        ┌─────────▼─────────┐
                        │ P7: due           │  ← in due window
                        │   (claim now!)     │     window_start ≤ now ≤ due_date
                        └─────────┬─────────┘
                                  │ no
                         ┌────────▼────────┐
                         │ P8: pending     │  ← default fallback
                         └─────────────────┘
```

### 3.2 Engine Method Specification

**File**: `custom_components/kidschores/engines/chore_engine.py`

```python
@staticmethod
def resolve_kid_chore_state(
    chore_data: ChoreData | dict[str, Any],
    kid_id: str,
    now: datetime,
    *,
    is_approved_in_period: bool,
    has_pending_claim: bool,
    due_date: datetime | None,
    due_window_start: datetime | None,
) -> tuple[str, str | None]:
    """Resolve the calculated display state for a kid's chore.

    Returns (state, lock_reason) tuple. lock_reason is non-None only
    for blocking states (waiting, not_my_turn, missed).

    Priority order (first match wins):
      P1: approved, P2: claimed, P3: not_my_turn, P4: missed,
      P5: overdue, P6: waiting, P7: due, P8: pending
    """
    # P1 — Approved takes absolute precedence
    if is_approved_in_period:
        return (const.CHORE_STATE_APPROVED, None)

    # P2 — Pending claim awaiting parent action
    if has_pending_claim:
        return (const.CHORE_STATE_CLAIMED, None)

    # P3 — Rotation: not this kid's turn
    if ChoreEngine.is_rotation_mode(chore_data):
        current_turn = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
        override = chore_data.get(const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE, False)

        if kid_id != current_turn and not override:
            overdue_handling = chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)

            # STEAL EXCEPTION: overdue handling is allow_steal + past due date
            # In that case, not_my_turn blocking lifts — any kid can claim
            if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL:
                if due_date is not None and now > due_date:
                    pass  # Fall through — steal window is active
                else:
                    return (const.CHORE_STATE_NOT_MY_TURN, "not_my_turn")
            else:
                # Simple and Smart without steal: strict turn enforcement
                return (const.CHORE_STATE_NOT_MY_TURN, "not_my_turn")

    # P4 — Missed lock (strict: no claiming allowed)
    overdue_type = chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
    if (
        overdue_type == const.OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK
        and due_date is not None
        and now > due_date
    ):
        return (const.CHORE_STATE_MISSED, "missed")

    # P5 — Overdue (relaxed: still claimable)
    if (
        overdue_type in _RELAXED_OVERDUE_TYPES
        and due_date is not None
        and now > due_date
    ):
        return (const.CHORE_STATE_OVERDUE, None)

    # P6 — Waiting (claim restriction: before window opens)
    claim_restricted = chore_data.get(
        const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED, False
    )
    if (
        claim_restricted
        and due_window_start is not None
        and now < due_window_start
    ):
        return (const.CHORE_STATE_WAITING, "waiting")

    # P7 — Due (inside the claim window)
    if (
        due_window_start is not None
        and due_date is not None
        and due_window_start <= now <= due_date
    ):
        return (const.CHORE_STATE_DUE, None)

    # P8 — Default
    return (const.CHORE_STATE_PENDING, None)


# Module-level constant for P5 check
_RELAXED_OVERDUE_TYPES: Final = frozenset({
    const.OVERDUE_HANDLING_AT_DUE_DATE,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
    const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED,
})
```

### 3.3 Integration with `can_claim_chore()`

The existing `can_claim_chore()` gains three new early-exit paths. The method signature is unchanged.

```python
@staticmethod
def can_claim_chore(
    kid_chore_data: dict[str, Any],
    chore_data: ChoreData | dict[str, Any],
    has_pending_claim: bool,
    is_approved_in_period: bool,
    other_kid_states: dict[str, str] | None = None,
    *,
    # NEW parameters for FSM integration
    resolved_state: str | None = None,
    lock_reason: str | None = None,
) -> tuple[bool, str | None]:
    """Determine if a kid can claim a chore.

    NEW: If resolved_state is provided (from resolve_kid_chore_state),
    use it for early blocking checks before falling through to existing logic.
    """
    # NEW — FSM-based blocking (P3, P4, P6 states)
    if resolved_state in (
        const.CHORE_STATE_MISSED,
        const.CHORE_STATE_WAITING,
        const.CHORE_STATE_NOT_MY_TURN,
    ):
        return (False, lock_reason or resolved_state)

    # EXISTING — shared_first blocking (now uses adapter)
    if ChoreEngine.is_single_claimer_mode(chore_data) and other_kid_states:
        for other_state in other_kid_states.values():
            if other_state in (const.CHORE_STATE_CLAIMED, const.CHORE_STATE_APPROVED):
                return (False, "other_kid_active")

    # EXISTING — multi-claim check
    is_multi = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA) in (...)
    # ... rest unchanged ...
```

**Alternative approach** (simpler — let the manager compute state first and pass it):

The manager's `can_claim_chore()` method already calls the engine. It can call `resolve_kid_chore_state()` first, then pass the result to the engine's `can_claim_chore()`. This keeps the engine methods focused:

```
Manager.can_claim_chore(kid_id, chore_id):
  1. Gather context (approved flag, claimed flag, due dates)
  2. resolved_state, lock_reason = ChoreEngine.resolve_kid_chore_state(...)
  3. can_claim, reason = ChoreEngine.can_claim_chore(..., resolved_state=resolved_state, lock_reason=lock_reason)
  4. return (can_claim, reason)
```

---

## 4. Rotation Advancement

### 4.1 Flow Diagram — `_advance_rotation()` after Approval

```
approve_chore(kid_id, chore_id, parent_name)
  │
  ├─ [existing approval logic: state changes, points, stats]
  │
  ├─ _persist()  ← existing persist point
  │
  ├─ emit(SIGNAL_SUFFIX_CHORE_APPROVED, ...)  ← existing signal
  │
  ├─►_advance_rotation(chore_id, kid_id)  ← NEW insertion point
  │     │
  │     ├─ if not is_rotation_mode(chore): return
  │     │
  │     ├─ Reset override: rotation_cycle_override = False  (D-15)
  │     │
  │     ├─ Determine next turn:
  │     │    ├─ rotation_simple → calculate_next_turn_simple()
  │     │    └─ rotation_smart  → query stats → calculate_next_turn_smart()
  │     │
  │     ├─ Write: rotation_current_kid_id = next_kid_id
  │     │
  │     ├─ _persist()  ← second persist for rotation state
  │     │
  │     └─ emit(SIGNAL_SUFFIX_ROTATION_ADVANCED, {
  │           chore_id, previous_kid_id, new_kid_id, method
  │         })
  │
  └─ [existing upon_completion reset check]
```

### 4.2 Turn Calculation — Simple (Round-Robin)

**File**: `custom_components/kidschores/engines/chore_engine.py`

```python
@staticmethod
def calculate_next_turn_simple(
    assigned_kids: list[str],
    current_kid_id: str | None,
) -> str:
    """Calculate next turn using round-robin order.

    Used by rotation_simple. Advances to the next kid in assigned_kids
    list order, wrapping around at the end.
    Resilience: if current_kid_id is not in list, reset to first kid.
    """
    if not assigned_kids:
        return ""  # Defensive — should never happen (V-03 prevents)

    if current_kid_id is None or current_kid_id not in assigned_kids:
        return assigned_kids[0]

    current_index = assigned_kids.index(current_kid_id)
    next_index = (current_index + 1) % len(assigned_kids)
    return assigned_kids[next_index]
```

### 4.3 Turn Calculation — Smart

```python
@staticmethod
def calculate_next_turn_smart(
    assigned_kids: list[str],
    approved_counts: dict[str, int],
    last_approved_timestamps: dict[str, str | None],
) -> str:
    """Calculate next turn using fairness-weighted selection.

    Sort criteria (ascending = higher priority):
      1. Approved count (fewest completions → highest priority)
      2. Last approved timestamp (oldest/None → highest priority)
      3. List position in assigned_kids (tie-break)

    Returns the kid_id who should go next.
    """
    if not assigned_kids:
        return ""

    def sort_key(kid_id: str) -> tuple[int, str, int]:
        count = approved_counts.get(kid_id, 0)
        timestamp = last_approved_timestamps.get(kid_id) or ""
        position = assigned_kids.index(kid_id)
        return (count, timestamp, position)

    return min(assigned_kids, key=sort_key)
```

### 4.4 Manager Method — `_advance_rotation()`

**File**: `custom_components/kidschores/managers/chore_manager.py`

```python
async def _advance_rotation(self, chore_id: str, approved_kid_id: str) -> None:
    """Advance rotation to next kid after a successful approval.

    Called from approve_chore() after the approval persist.
    Handles simple (round-robin) and smart (fairness-weighted).
    Always resets rotation_cycle_override (D-15).

    Note on steal (D-18): When a non-turn-holder completes via
    at_due_date_allow_steal, the turn advances normally from the
    completer — NOT back to the skipped turn-holder.
    """
    chore_data = self._data.get(const.DATA_CHORES, {}).get(chore_id)
    if not chore_data or not ChoreEngine.is_rotation_mode(chore_data):
        return

    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if len(assigned_kids) < 2:
        return  # Safety — V-03 should prevent this

    previous_kid_id = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
    criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)

    # Determine next turn
    if criteria == const.COMPLETION_CRITERIA_ROTATION_SMART:
        # Query stats for fairness-weighted selection (D-08)
        approved_counts = self._coordinator.statistics_manager.get_chore_approved_counts(
            chore_id, assigned_kids
        )
        last_timestamps = self._coordinator.statistics_manager.get_chore_last_approved_timestamps(
            chore_id, assigned_kids
        )
        next_kid_id = ChoreEngine.calculate_next_turn_smart(
            assigned_kids, approved_counts, last_timestamps
        )
        method = "smart"
    else:
        # rotation_simple: round-robin advancement
        next_kid_id = ChoreEngine.calculate_next_turn_simple(
            assigned_kids, previous_kid_id
        )
        method = "simple"

    # Write rotation state
    chore_data[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = next_kid_id
    chore_data[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False  # D-15
    self._coordinator._persist()

    # Signal (after persist — per DEVELOPMENT_STANDARDS.md § 5.3)
    self.emit(
        const.SIGNAL_SUFFIX_ROTATION_ADVANCED,
        chore_id=chore_id,
        previous_kid_id=previous_kid_id or "",
        new_kid_id=next_kid_id,
        method=method,
    )

    const.LOGGER.debug(
        "Rotation advanced for chore %s: %s → %s (method=%s)",
        chore_id, previous_kid_id, next_kid_id, method,
    )
```

### 4.5 Insertion Point in `approve_chore()`

```
Location: After the existing _persist() and CHORE_APPROVED signal emission,
          before the UPON_COMPLETION reset check.

Pseudocode insertion:
    # ... existing approval logic ...
    self._coordinator._persist()
    self.emit(const.SIGNAL_SUFFIX_CHORE_APPROVED, ...)

    # NEW — Advance rotation after successful approval
    await self._advance_rotation(chore_id, kid_id)

    # ... existing upon_completion reset check ...
```

### 4.6 Rotation Resilience — Kid Deletion

In the existing `KID_DELETED` signal handler in `chore_manager.py`:

```python
# After removing deleted kid from assigned_kids:
if ChoreEngine.is_rotation_mode(chore_data):
    current_turn = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
    remaining_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

    if current_turn == deleted_kid_id:
        if remaining_kids:
            chore_data[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = remaining_kids[0]
        else:
            chore_data[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = None
            chore_data[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False
```

---

## 5. Claim Restriction

### 5.1 Concept

A per-chore boolean (`claim_restriction_enabled`). When `True`, kids cannot claim the chore until the due window opens. The due window start is calculated from `due_date - due_window_offset`.

### 5.2 Integration Points

**Already exists**: `check_due_window()` and `calculate_due_window_start()` in `chore_engine.py`. The restriction only needs to be **enforced** — the calculation infrastructure is present.

**New enforcement in FSM** (§3 above): Priority 6 (`waiting`) blocks claims when `claim_restriction_enabled AND now < due_window_start`.

**Flow helpers**: Add `BooleanSelector` for `claim_restriction_enabled` in `build_chore_schema()`:

```python
vol.Optional(
    const.CFOF_CHORES_INPUT_CLAIM_RESTRICTION,
    default=default.get(const.CFOF_CHORES_INPUT_CLAIM_RESTRICTION, False),
): selector.BooleanSelector(),
```

**Validation rule V-02**: If `claim_restriction_enabled == True`, then `due_window_offset` must exist and parse to duration > 0.

---

## 6. Missed Lock

### 6.1 Concept (D-02)

The 6th overdue handling type: `at_due_date_mark_missed_and_lock`. When the due date passes:

1. Kid's chore state becomes `missed` (Priority 4 in FSM)
2. `can_claim` returns `False` with reason `"missed"`
3. Miss is recorded via `_record_missed_chore()` (existing)
4. State is **locked** — kid cannot claim until the approval reset boundary fires
5. Only `at_midnight_*` `approval_reset_type` values are compatible (D-03 validation) — the overdue policy at the approval reset boundary unlocks the `missed` state

### 6.2 Scanner Integration

**File**: `custom_components/kidschores/managers/chore_manager.py` — `_run_time_scanner()`

The scanner already categorizes chores by overdue type. Add a new path:

```python
# In the scanner's overdue detection section:
if overdue_type == const.OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK:
    # Check if kid's state should transition to missed
    kid_chore_state = kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE)
    if kid_chore_state in (const.CHORE_STATE_PENDING, const.CHORE_STATE_DUE):
        # Lock the state
        kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = const.CHORE_STATE_MISSED
        state_modified = True

        # Record miss stat (existing method, extended payload)
        self._record_missed_chore(
            kid_id, chore_id, chore_name,
            due_date=due_date_str,      # D-07: extended payload
            reason="strict_lock",        # D-07: extended payload
        )
```

**Important distinction from existing `clear_and_mark_missed`**:

- **Existing** (`clear_and_mark_missed`): At due date: records miss → at approval reset boundary: overdue policy clears overdue status and resets chore state to `pending`
- **New** (`mark_missed_and_lock`): At due date: records miss + locks in `missed` state → at approval reset boundary: overdue policy unlocks `missed` state and resets chore state to `pending`

### 6.3 Overdue Policy at Approval Reset Boundary

In `_process_approval_boundary_resets()`, when the approval reset boundary fires (Lane 1) for `at_midnight_*` chores, the overdue policy (Lane 2) executes:

```python
# After checking if kid state needs reset:
if kid_state == const.CHORE_STATE_MISSED:
    # Overdue policy: unlock missed state, reset chore state to pending
    kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = const.CHORE_STATE_PENDING
    state_modified = True

    # For rotation chores: if missed kid was turn holder, advance rotation
    if ChoreEngine.is_rotation_mode(chore_data):
        current_turn = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
        if current_turn == kid_id:
            await self._advance_rotation(chore_id, kid_id)

# For allow_steal rotation chores: overdue policy at approval reset boundary
# clears overdue status even if no one claimed (pure miss). Chore state resets
# to pending and _advance_rotation handles turn advancement (D-17).
overdue_handling = chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL:
    if kid_state == const.CHORE_STATE_OVERDUE:
        kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = const.CHORE_STATE_PENDING
        state_modified = True

        if ChoreEngine.is_rotation_mode(chore_data):
            current_turn = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
            if current_turn == kid_id:
                # Record missed stat for skipped turn-holder, then advance
                await self._advance_rotation(chore_id, kid_id)
```

---

## 7. Criteria Transition

### 7.1 Concept (D-11)

`completion_criteria` is mutable. When a user changes it (via options flow or update service), the system must clean up/initialize rotation fields.

### 7.2 Engine Method — Pure Computation

**File**: `custom_components/kidschores/engines/chore_engine.py`

```python
@staticmethod
def get_criteria_transition_actions(
    old_criteria: str,
    new_criteria: str,
    assigned_kids: list[str],
) -> dict[str, Any]:
    """Compute field changes needed when completion_criteria changes.

    Returns a dict of {field_name: new_value} to apply to chore data.
    Returns empty dict if no field changes needed.
    """
    was_rotation = old_criteria in (
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        const.COMPLETION_CRITERIA_ROTATION_SMART,
    )
    is_rotation = new_criteria in (
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        const.COMPLETION_CRITERIA_ROTATION_SMART,
    )

    if was_rotation and not is_rotation:
        # Rotation → non-rotation: clear rotation fields
        return {
            const.DATA_CHORE_ROTATION_CURRENT_KID_ID: None,
            const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE: False,
        }

    if not was_rotation and is_rotation:
        # Non-rotation → rotation: initialize rotation genesis
        return {
            const.DATA_CHORE_ROTATION_CURRENT_KID_ID: (
                assigned_kids[0] if assigned_kids else None
            ),
            const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE: False,
        }

    # Rotation → different rotation type: keep existing turn
    # Same category: no changes needed
    return {}
```

### 7.3 Manager Method — Orchestration

**File**: `custom_components/kidschores/managers/chore_manager.py`

```python
def _handle_criteria_transition(
    self,
    chore_id: str,
    old_criteria: str,
    new_criteria: str,
) -> None:
    """Apply field changes when completion_criteria is modified.

    Called from update_chore() when criteria has changed.
    Validates constraints and applies engine-computed transitions.
    """
    chore_data = self._data.get(const.DATA_CHORES, {}).get(chore_id)
    if not chore_data:
        return

    assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])

    # Get transition actions from engine (pure computation)
    actions = ChoreEngine.get_criteria_transition_actions(
        old_criteria, new_criteria, assigned_kids
    )

    # Apply each field change
    for field, value in actions.items():
        chore_data[field] = value

    if actions:
        const.LOGGER.debug(
            "Criteria transition for chore %s: %s → %s, applied %s",
            chore_id, old_criteria, new_criteria, list(actions.keys()),
        )
```

### 7.4 Service Handler Integration

In the update chore handler (`services.py`), after mapping fields:

```python
# Detect criteria change
old_criteria = existing_chore.get(const.DATA_CHORE_COMPLETION_CRITERIA)
new_criteria = updates.get(const.DATA_CHORE_COMPLETION_CRITERIA)

if new_criteria and new_criteria != old_criteria:
    coordinator.chore_manager._handle_criteria_transition(
        chore_id, old_criteria, new_criteria
    )
```

---

## 8. Service Changes

### 8.1 Remove Immutability Guard (D-11)

**File**: `custom_components/kidschores/services.py` — Lines 784-788

**DELETE** this block:

```python
# Block completion_criteria changes (immutable after creation)
if const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA in call.data:
    raise HomeAssistantError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_COMPLETION_CRITERIA_IMMUTABLE,
    )
```

### 8.2 Add `completion_criteria` to `UPDATE_CHORE_SCHEMA`

```python
UPDATE_CHORE_SCHEMA = vol.Schema({
    # ... existing fields ...
    vol.Optional(const.SERVICE_FIELD_CHORE_CRUD_COMPLETION_CRITERIA): vol.In(
        _COMPLETION_CRITERIA_VALUES
    ),
})
```

**Update** `_COMPLETION_CRITERIA_VALUES` to include new rotation types:

```python
_COMPLETION_CRITERIA_VALUES = [
    const.COMPLETION_CRITERIA_INDEPENDENT,
    const.COMPLETION_CRITERIA_SHARED_FIRST,
    const.COMPLETION_CRITERIA_SHARED,
    const.COMPLETION_CRITERIA_ROTATION_SIMPLE,   # NEW
    const.COMPLETION_CRITERIA_ROTATION_SMART,    # NEW
]
```

### 8.3 New Rotation Services

Three new services, all following the existing registration pattern in `async_setup_services()`:

#### `set_rotation_turn`

```python
SERVICE_SET_ROTATION_TURN_SCHEMA = vol.Schema({
    vol.Required(const.SERVICE_FIELD_CHORE_ID): cv.string,
    vol.Required(const.SERVICE_FIELD_ROTATION_KID_ID): cv.string,
})

async def _handle_set_rotation_turn(call: ServiceCall) -> None:
    """Set the current turn holder for a rotation chore."""
    chore_id = call.data[const.SERVICE_FIELD_CHORE_ID]
    kid_id = call.data[const.SERVICE_FIELD_ROTATION_KID_ID]

    chore_data = coordinator.chores_data.get(chore_id)
    if not chore_data:
        raise ServiceValidationError(...)

    if not ChoreEngine.is_rotation_mode(chore_data):
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_NOT_ROTATION_CHORE,
        )

    assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if kid_id not in assigned:
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_KID_NOT_ASSIGNED,
        )

    await coordinator.chore_manager.set_rotation_turn(chore_id, kid_id)
```

#### `reset_rotation`

```python
SERVICE_RESET_ROTATION_SCHEMA = vol.Schema({
    vol.Required(const.SERVICE_FIELD_CHORE_ID): cv.string,
})

async def _handle_reset_rotation(call: ServiceCall) -> None:
    """Reset rotation to the first assigned kid."""
    chore_id = call.data[const.SERVICE_FIELD_CHORE_ID]
    # Validate is_rotation_mode, then delegate
    await coordinator.chore_manager.reset_rotation(chore_id)
```

#### `open_rotation_cycle`

```python
SERVICE_OPEN_ROTATION_CYCLE_SCHEMA = vol.Schema({
    vol.Required(const.SERVICE_FIELD_CHORE_ID): cv.string,
})

async def _handle_open_rotation_cycle(call: ServiceCall) -> None:
    """Temporarily allow any kid to claim (override turn restriction)."""
    chore_id = call.data[const.SERVICE_FIELD_CHORE_ID]
    # Validate is_rotation_mode, then delegate
    await coordinator.chore_manager.open_rotation_cycle(chore_id)
```

### 8.4 ChoreManager Methods for New Services

```python
async def set_rotation_turn(self, chore_id: str, kid_id: str) -> None:
    """Manually set the current turn holder. Emits ROTATION_ADVANCED."""
    chore = self._data[const.DATA_CHORES][chore_id]
    previous = chore.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
    chore[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = kid_id
    chore[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False
    self._coordinator._persist()
    self.emit(const.SIGNAL_SUFFIX_ROTATION_ADVANCED,
              chore_id=chore_id, previous_kid_id=previous or "",
              new_kid_id=kid_id, method="manual")

async def reset_rotation(self, chore_id: str) -> None:
    """Reset rotation to assigned_kids[0]."""
    chore = self._data[const.DATA_CHORES][chore_id]
    assigned = chore.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    previous = chore.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
    chore[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = assigned[0] if assigned else None
    chore[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False
    self._coordinator._persist()
    self.emit(const.SIGNAL_SUFFIX_ROTATION_ADVANCED,
              chore_id=chore_id, previous_kid_id=previous or "",
              new_kid_id=assigned[0] if assigned else "", method="manual")

async def open_rotation_cycle(self, chore_id: str) -> None:
    """Enable cycle override — any kid can claim this cycle."""
    chore = self._data[const.DATA_CHORES][chore_id]
    chore[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = True
    self._coordinator._persist()
    self.emit(const.SIGNAL_SUFFIX_CHORE_UPDATED, chore_id=chore_id)
```

---

## 9. Migration Extension

### 9.1 Backfill Pattern (D-13)

**File**: `custom_components/kidschores/migration_pre_v50.py` — inside `_migrate_to_schema_44()`

Add as a new step after existing v44 tweaks, **before** the schema version stamp:

```python
# --- NEW: Backfill chore rotation/restriction fields (v0.5.0) ---
chores = self.coordinator._data.get(const.DATA_CHORES, {})
backfilled_count = 0
for chore_data in chores.values():
    changed = False
    if const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED not in chore_data:
        chore_data[const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED] = False
        changed = True
    if const.DATA_CHORE_ROTATION_CURRENT_KID_ID not in chore_data:
        chore_data[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = None
        changed = True
    if const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE not in chore_data:
        chore_data[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = False
        changed = True
    if changed:
        backfilled_count += 1

if backfilled_count:
    const.LOGGER.info(
        "PreV50Migrator: Backfilled rotation/restriction fields on %s chores",
        backfilled_count,
    )
```

**Note**: Existing chores all have non-rotation `completion_criteria` values, so `rotation_current_kid_id = None` is correct — no rotation genesis needed during migration.

---

## 10. Dashboard & Sensor Integration

### 10.1 Sensor — `KidChoreStatusSensor` (D-16)

**File**: `custom_components/kidschores/sensor.py`

The existing sensor already exposes `can_claim` and `can_approve` via `extra_state_attributes()`. The pipeline:

```
ChoreEngine.can_claim_chore()     ← Pure logic (extended with FSM states)
     ↓
ChoreManager.can_claim_chore()    ← Gathers data, delegates to engine
     ↓
KidChoreStatusSensor.extra_state_attributes()  ← Exposes as HA attribute
     ↓
Dashboard YAML: state_attr(chore.eid, 'can_claim')  ← Jinja2 consumption
```

**New attributes to add** in `extra_state_attributes()`:

```python
# After the existing can_claim/can_approve block:
resolved_state, lock_reason = self.coordinator.chore_manager.get_resolved_state(
    self._kid_id, self._chore_id
)
attributes[const.ATTR_CHORE_LOCK_REASON] = lock_reason

# For rotation chores: expose current turn holder's name
if ChoreEngine.is_rotation_mode(chore_data):
    turn_kid_id = chore_data.get(const.DATA_CHORE_ROTATION_CURRENT_KID_ID)
    turn_kid_name = self._resolve_kid_name(turn_kid_id)
    attributes[const.ATTR_CHORE_TURN_KID_NAME] = turn_kid_name
else:
    attributes[const.ATTR_CHORE_TURN_KID_NAME] = None

# For claim restriction: expose when window opens
if (
    chore_data.get(const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED)
    and lock_reason == "waiting"
):
    attributes[const.ATTR_CHORE_AVAILABLE_AT] = due_window_start_iso
else:
    attributes[const.ATTR_CHORE_AVAILABLE_AT] = None
```

### 10.2 Dashboard Helper — UI Manager

**File**: `custom_components/kidschores/managers/ui_manager.py`

The dashboard helper currently returns 6 fields per chore. Add 3-4 new fields:

```python
return {
    # Existing 6 fields (unchanged)
    const.ATTR_EID: chore_eid,
    const.ATTR_NAME: chore_name,
    const.ATTR_STATUS: status,
    const.ATTR_CHORE_LABELS: chore_labels,
    const.ATTR_CHORE_PRIMARY_GROUP: primary_group,
    const.ATTR_CHORE_IS_TODAY_AM: is_today_am,

    # NEW — Rotation & Restriction metadata
    const.ATTR_CHORE_LOCK_REASON: lock_reason,        # "waiting"|"not_my_turn"|"missed"|None
    const.ATTR_CHORE_TURN_KID_NAME: turn_kid_name,    # "Alice"|None (only for rotation)
    const.ATTR_CHORE_AVAILABLE_AT: available_at,       # ISO datetime|None (only if waiting)
}
```

**Note**: `can_claim` deliberately NOT duplicated in dashboard helper — dashboard consumes it via `state_attr(chore.eid, 'can_claim')` as documented.

---

## 11. Statistics Integration

### 11.1 Smart Rotation Query (D-08)

**File**: `custom_components/kidschores/managers/statistics_manager.py`

Two new public methods:

```python
def get_chore_approved_counts(
    self,
    chore_id: str,
    kid_ids: list[str],
) -> dict[str, int]:
    """Return all-time approved count per kid for a specific chore.

    Used by smart rotation to determine fairness-weighted turn.
    """
    result: dict[str, int] = {}
    kids_data = self._coordinator._data.get(const.DATA_KIDS, {})

    for kid_id in kid_ids:
        kid_info = kids_data.get(kid_id, {})
        chore_stats = (
            kid_info
            .get(const.DATA_KID_CHORE_DATA, {})
            .get(chore_id, {})
            .get(const.DATA_KID_CHORE_DATA_PERIODS, {})
            .get("all_time", {})
            .get("all_time", {})
        )
        result[kid_id] = chore_stats.get(
            const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0
        )

    return result

def get_chore_last_approved_timestamps(
    self,
    chore_id: str,
    kid_ids: list[str],
) -> dict[str, str | None]:
    """Return last approved timestamp per kid for a specific chore.

    Used by smart rotation for tie-breaking (oldest completion → highest priority).
    """
    result: dict[str, str | None] = {}
    kids_data = self._coordinator._data.get(const.DATA_KIDS, {})

    for kid_id in kid_ids:
        kid_info = kids_data.get(kid_id, {})
        chore_data = (
            kid_info
            .get(const.DATA_KID_CHORE_DATA, {})
            .get(chore_id, {})
        )
        result[kid_id] = chore_data.get("last_approved_timestamp")

    return result
```

**Note**: The `last_approved_timestamp` field may need to be tracked explicitly. If it doesn't exist in the current per-kid chore data, add it as a new field set during `_on_chore_approved()`.

---

## 12. Notification Wiring

### 12.1 Subscribe to CHORE_MISSED

**File**: `custom_components/kidschores/managers/notification_manager.py`

In `async_setup()`, add:

```python
self.listen(const.SIGNAL_SUFFIX_CHORE_MISSED, self._handle_chore_missed)
```

### 12.2 Handler

```python
def _handle_chore_missed(self, payload: dict[str, Any]) -> None:
    """Notify parents and kid when a chore is missed (strict lock)."""
    kid_id = payload.get("kid_id", "")
    chore_id = payload.get("chore_id", "")
    chore_name = payload.get("chore_name", "Unknown Chore")
    reason = payload.get("reason", "")
    due_date = payload.get("due_date", "")

    # Reuse notify_on_overdue flag (missed is stricter form of overdue)
    chore_info = self.coordinator.chores_data.get(chore_id)
    if not chore_info:
        return
    if not chore_info.get(
        const.DATA_CHORE_NOTIFY_ON_OVERDUE, const.DEFAULT_NOTIFY_ON_OVERDUE
    ):
        return

    # Dedup check
    if not self._should_send_chore_notification(kid_id, chore_id, "missed"):
        return

    # Notify kid
    self.hass.async_create_task(
        self.notify_kid_translated(
            kid_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_MISSED,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED,
            message_data={"chore_name": chore_name, "due_date": due_date},
        )
    )

    # Notify parents
    self.hass.async_create_task(
        self.notify_parents_translated(
            kid_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_MISSED,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED,
            message_data={"chore_name": chore_name, "due_date": due_date},
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(chore_id, kid_id),
        )
    )

    self._record_chore_notification_sent(kid_id, chore_id, "missed")
```

---

## 13. Validation Rules

### 13.1 Complete Rule Set

**File**: `custom_components/kidschores/data_builders.py` — `validate_chore_data()`

Add to existing validation rules:

| ID       | Rule                                                                                                              | Error Key                                             |
| -------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **V-01** | `mark_missed_and_lock` requires `at_midnight_*` `approval_reset_type` (D-03)                                      | `TRANS_KEY_VALIDATION_MISSED_LOCK_RESET_INCOMPATIBLE` |
| **V-02** | `claim_restriction_enabled == True` requires `due_window_offset` with duration > 0                                | `TRANS_KEY_VALIDATION_CLAIM_RESTRICTION_NO_WINDOW`    |
| **V-03** | All rotation types require `len(assigned_kids) >= 2` (D-14)                                                       | `TRANS_KEY_VALIDATION_ROTATION_MIN_KIDS`              |
| **V-04** | `at_due_date_allow_steal` requires rotation criteria + `at_midnight_once` `approval_reset_type` + due date (D-06) | `TRANS_KEY_VALIDATION_ALLOW_STEAL_INCOMPATIBLE`       |

```python
# V-01 — Missed lock requires at_midnight_* approval_reset_type
overdue_type = data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE)
reset_type = data.get(const.DATA_CHORE_APPROVAL_RESET_TYPE)
if overdue_type == const.OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK:
    allowed_resets = {
        const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        const.APPROVAL_RESET_AT_MIDNIGHT_PLUS_RESCHEDULE,
    }
    if reset_type not in allowed_resets:
        errors["overdue_handling_type"] = const.TRANS_KEY_VALIDATION_MISSED_LOCK_RESET_INCOMPATIBLE

# V-02 — Claim restriction requires due window
claim_restricted = data.get(const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED, False)
if claim_restricted:
    offset = data.get(const.DATA_CHORE_DUE_WINDOW_OFFSET)
    if not offset or dt_parse_duration(offset) is None:
        errors["claim_restriction_enabled"] = const.TRANS_KEY_VALIDATION_CLAIM_RESTRICTION_NO_WINDOW

# V-03 — Rotation requires ≥ 2 kids
criteria = data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
rotation_criteria = {
    const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
    const.COMPLETION_CRITERIA_ROTATION_SMART,
}
if criteria in rotation_criteria:
    assigned = data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if len(assigned) < 2:
        errors["assigned_kids"] = const.TRANS_KEY_VALIDATION_ROTATION_MIN_KIDS

# V-04 — at_due_date_allow_steal requires rotation criteria + at_midnight_once approval_reset_type + due date
if overdue_type == const.OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL:
    # Must be a rotation chore
    if criteria not in rotation_criteria:
        errors["overdue_handling_type"] = const.TRANS_KEY_VALIDATION_ALLOW_STEAL_INCOMPATIBLE
    # Must have at_midnight_once approval_reset_type (steal window needs daily recurrence)
    elif reset_type != const.APPROVAL_RESET_AT_MIDNIGHT_ONCE:
        errors["overdue_handling_type"] = const.TRANS_KEY_VALIDATION_ALLOW_STEAL_INCOMPATIBLE
    # Must have a due date (defines when steal window opens)
    else:
        due_date = data.get(const.DATA_CHORE_DUE_DATE)
        if not due_date:
            errors["overdue_handling_type"] = const.TRANS_KEY_VALIDATION_ALLOW_STEAL_INCOMPATIBLE
```

### 13.2 Build Defaults

In `build_chore()`:

```python
chore_dict[const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED] = _resolve(
    const.DATA_CHORE_CLAIM_RESTRICTION_ENABLED, False
)
chore_dict[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = _resolve(
    const.DATA_CHORE_ROTATION_CURRENT_KID_ID, None
)
chore_dict[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] = _resolve(
    const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE, False
)

# Rotation genesis: auto-set first kid as turn holder on creation
if criteria in rotation_criteria and not existing:
    assigned = chore_dict.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
    if assigned:
        chore_dict[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] = assigned[0]
```

---

## 14. Constant & Translation Inventory

### 14.1 New Constants (by category)

**Completion Criteria** (2):

- `COMPLETION_CRITERIA_ROTATION_SIMPLE`
- `COMPLETION_CRITERIA_ROTATION_SMART`

**Overdue Handling** (2):

- `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK`
- `OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL` ← NEW (rotation-only, lifts not_my_turn at due date)

**Chore States** (3):

- `CHORE_STATE_WAITING`
- `CHORE_STATE_NOT_MY_TURN`
- `CHORE_STATE_MISSED`

**Storage Keys** (3):

- `DATA_CHORE_CLAIM_RESTRICTION_ENABLED`
- `DATA_CHORE_ROTATION_CURRENT_KID_ID`
- `DATA_CHORE_ROTATION_CYCLE_OVERRIDE`

**Signal** (1):

- `SIGNAL_SUFFIX_ROTATION_ADVANCED`

**Services** (3):

- `SERVICE_SET_ROTATION_TURN`
- `SERVICE_RESET_ROTATION`
- `SERVICE_OPEN_ROTATION_CYCLE`

**Service Fields** (1):

- `SERVICE_FIELD_ROTATION_KID_ID`

**Config Flow** (1):

- `CFOF_CHORES_INPUT_CLAIM_RESTRICTION`

**Attributes** (3):

- `ATTR_CHORE_LOCK_REASON`
- `ATTR_CHORE_TURN_KID_NAME`
- `ATTR_CHORE_AVAILABLE_AT`

**Translation Keys** (~15 new):

- State labels: `TRANS_KEY_CHORE_STATE_WAITING`, `TRANS_KEY_CHORE_STATE_NOT_MY_TURN`, `TRANS_KEY_CHORE_STATE_MISSED`
- Criteria labels: `TRANS_KEY_ROTATION_SIMPLE`, `TRANS_KEY_ROTATION_SMART`
- Overdue labels: `TRANS_KEY_OVERDUE_MARK_MISSED_AND_LOCK`, `TRANS_KEY_OVERDUE_AT_DUE_DATE_ALLOW_STEAL`
- Notification: `TRANS_KEY_NOTIF_TITLE_CHORE_MISSED`, `TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED`, `TRANS_KEY_NOTIF_TITLE_STEAL_WINDOW_OPEN`, `TRANS_KEY_NOTIF_MESSAGE_STEAL_WINDOW_OPEN`
- Validation errors: `TRANS_KEY_VALIDATION_MISSED_LOCK_RESET_INCOMPATIBLE`, `TRANS_KEY_VALIDATION_CLAIM_RESTRICTION_NO_WINDOW`, `TRANS_KEY_VALIDATION_ROTATION_MIN_KIDS`, `TRANS_KEY_VALIDATION_ALLOW_STEAL_INCOMPATIBLE`
- Service errors: `TRANS_KEY_ERROR_NOT_ROTATION_CHORE`, `TRANS_KEY_ERROR_KID_NOT_ASSIGNED`
- Service descriptions: 3 services × (name + description + fields)

**Constants to REMOVE**:

- `COMPLETION_CRITERIA_ROTATION_STEAL` (moved to overdue handling)
- `TRANS_KEY_CRITERIA_ROTATION_STEAL` (replaced by `TRANS_KEY_OVERDUE_AT_DUE_DATE_ALLOW_STEAL`)
- `TRANS_KEY_VALIDATION_ROTATION_STEAL_NO_DUE_DATE` (replaced by `TRANS_KEY_VALIDATION_ALLOW_STEAL_INCOMPATIBLE`)
- `TRANS_KEY_ERROR_COMPLETION_CRITERIA_IMMUTABLE` (D-11: guard removed)

### 14.2 Translation Entries (en.json additions)

```json
{
  "entity": {
    "sensor": {
      "chore_status_sensor": {
        "state": {
          "waiting": "Waiting",
          "not_my_turn": "Not my turn",
          "missed": "Missed"
        },
        "state_attributes": {
          "lock_reason": { "name": "Lock reason" },
          "turn_kid_name": { "name": "Current turn" },
          "available_at": { "name": "Available at" }
        }
      }
    }
  },
  "services": {
    "set_rotation_turn": {
      "name": "Set rotation turn",
      "description": "Manually set which kid's turn it is for a rotation chore.",
      "fields": {
        "chore_id": { "name": "Chore", "description": "The chore to update." },
        "rotation_kid_id": {
          "name": "Kid",
          "description": "The kid who should be the current turn holder."
        }
      }
    },
    "reset_rotation": {
      "name": "Reset rotation",
      "description": "Reset the rotation order back to the first assigned kid.",
      "fields": {
        "chore_id": { "name": "Chore", "description": "The chore to reset." }
      }
    },
    "open_rotation_cycle": {
      "name": "Open rotation cycle",
      "description": "Temporarily allow any assigned kid to claim this rotation chore, regardless of whose turn it is.",
      "fields": {
        "chore_id": { "name": "Chore", "description": "The chore to open." }
      }
    }
  },
  "exceptions": {
    "not_rotation_chore": {
      "message": "This chore does not use rotation. Only rotation chores support this action."
    },
    "kid_not_assigned": {
      "message": "The specified kid is not assigned to this chore."
    },
    "missed_lock_reset_incompatible": {
      "message": "The 'mark missed and lock' overdue strategy requires a midnight-based approval reset type (at_midnight_once or at_midnight_multi)."
    },
    "claim_restriction_no_window": {
      "message": "Claim restriction requires a due window offset to be configured."
    },
    "rotation_min_kids": {
      "message": "Rotation chores require at least two assigned kids."
    },
    "allow_steal_incompatible": {
      "message": "The 'allow steal' overdue strategy requires a rotation chore with at_midnight_once approval reset type and a due date configured."
    }
  },
  "selector": {
    "completion_criteria": {
      "options": {
        "rotation_simple": "Rotation Simple (Turn-holder only, strict order)",
        "rotation_smart": "Rotation Smart (Turn-holder only, fairness-weighted)"
      }
    },
    "overdue_handling_type": {
      "options": {
        "at_due_date_mark_missed_and_lock": "Mark missed and lock until reset",
        "at_due_date_allow_steal": "Allow steal (any kid can claim after due date)"
      }
    }
  }
}
```

---

## Appendix A — File Impact Summary

| File                               | Section          | Change Description                                                                                           |
| ---------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ |
| `const.py`                         | Constants        | ~28 new constants (2 criteria, 2 overdue, 3 states, etc.), remove 3 (rotation_steal + related)               |
| `type_defs.py`                     | TypedDict        | 3 new NotRequired fields on ChoreData                                                                        |
| `data_builders.py`                 | build + validate | 3 defaults + 4 validation rules (V-01..V-04, where V-04 validates allow_steal compatibility)                 |
| `engines/chore_engine.py`          | Logic            | 2 adapters + FSM (P3 checks overdue_handling for steal) + 2 rotation helpers + transition helper             |
| `managers/chore_manager.py`        | Orchestration    | \_advance_rotation + scanner + midnight (D-17 pure miss) + transition + 3 service methods + adapter adoption |
| `managers/statistics_manager.py`   | Query            | 2 new public methods                                                                                         |
| `managers/ui_manager.py`           | Dashboard        | 3 new chore attributes                                                                                       |
| `managers/notification_manager.py` | Wiring           | CHORE_MISSED subscription + steal window open notification                                                   |
| `helpers/flow_helpers.py`          | Forms            | claim_restriction selector + 2 criteria options + 7th overdue option (allow_steal)                           |
| `helpers/entity_helpers.py`        | Bug fix          | cleanup_orphaned_shared_state_sensors SHARED_FIRST                                                           |
| `options_flow.py`                  | Edit form        | claim_restriction + criteria transition on save + V-04 allow_steal validation                                |
| `services.py`                      | API              | Remove guard + add criteria to update (5 values) + 3 new services                                            |
| `services.yaml`                    | Descriptions     | 3 new service entries                                                                                        |
| `migration_pre_v50.py`             | Backfill         | 3 fields on all existing chores                                                                              |
| `sensor.py`                        | Attributes       | lock_reason, turn_kid_name, available_at + adapter adoption                                                  |
| `translations/en.json`             | i18n             | ~15 new keys, remove 3 (rotation_steal related), fix rotation_simple/smart descriptions                      |

## Appendix B — Test Matrix (Key Scenarios)

| #   | Scenario                                                              | Type       | Expected Result                                                     |
| --- | --------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------- |
| 1   | `rotation_simple`: Create → Claim kid A → Approve → Check turn        | Service    | Turn advances to kid B                                              |
| 2   | `rotation_simple`: Kid B claims when Kid A's turn                     | Service    | Blocked: `not_my_turn`                                              |
| 3   | `allow_steal`: Kid B claims after due date (steal window open)        | Service    | Allowed (not_my_turn lifted)                                        |
| 4   | `allow_steal`: Kid B claims before due date                           | Service    | Blocked: `not_my_turn`                                              |
| 5   | `rotation_smart`: 3 kids, counts 5/3/4 → approve                      | Service    | Turn goes to kid B (count 3)                                        |
| 6   | `open_rotation_cycle` → Kid B claims (not their turn)                 | Service    | Allowed (override active)                                           |
| 7   | After override claim approved → check override                        | Service    | Override cleared (D-15)                                             |
| 8   | `set_rotation_turn` to Kid C → check turn                             | Service    | Turn is Kid C                                                       |
| 9   | `reset_rotation` → check turn                                         | Service    | Turn is assigned_kids[0]                                            |
| 10  | Rotation chore, delete current turn kid                               | Signal     | Turn auto-advances to remaining[0]                                  |
| 11  | `mark_missed_and_lock`: past due → attempt claim                      | Service    | Blocked: `missed`                                                   |
| 12  | `mark_missed_and_lock`: approval reset boundary fires → attempt claim | Service    | Allowed (overdue policy unlocked `missed`, chore state → `pending`) |
| 13  | `claim_restriction`: claim before window                              | Service    | Blocked: `waiting`                                                  |
| 14  | `claim_restriction`: claim in window                                  | Service    | Allowed                                                             |
| 15  | Update criteria: `independent` → `rotation_simple`                    | Service    | `rotation_current_kid_id` set                                       |
| 16  | Update criteria: `rotation_simple` → `independent`                    | Service    | rotation fields cleared                                             |
| 17  | Update criteria: rotation + 1 kid                                     | Service    | Validation error: min 2 kids                                        |
| 18  | `allow_steal` + non-rotation chore                                    | Validation | Error (V-04)                                                        |
| 19  | `mark_missed_and_lock` + `upon_completion` `approval_reset_type`      | Validation | Error (V-01)                                                        |
| 20  | `allow_steal` + non-`at_midnight_once` `approval_reset_type`          | Validation | Error (V-04)                                                        |
| 21  | `allow_steal` + no due date                                           | Validation | Error (V-04)                                                        |
| 22  | `allow_steal`: Pure miss → approval reset boundary fires (D-17)       | Service    | Overdue policy advances turn to next kid                            |
| 23  | `allow_steal`: After steal → turn from completer (D-18)               | Service    | Turn advances from stealer                                          |
| 24  | FSM P3 > P5: rotation not-my-turn even when overdue                   | Engine     | `not_my_turn` (not `overdue`)                                       |
| 25  | FSM P1 > P3: rotation approved overrides not-my-turn                  | Engine     | `approved`                                                          |
| 26  | Migration: existing chores get new fields                             | Migration  | All 3 fields backfilled                                             |
