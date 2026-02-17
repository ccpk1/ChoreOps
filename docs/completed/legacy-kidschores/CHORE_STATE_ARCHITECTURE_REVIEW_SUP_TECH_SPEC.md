# Technical Specification: Chore State Architecture Hardening

> **Parent**: `CHORE_STATE_ARCHITECTURE_REVIEW_IN-PROCESS.md`
> **Target**: v0.5.0-beta4 · Schema 44
> **Purpose**: Pseudo-code, API definitions, logic flows for builder handoff
> **Status**: Ready for implementation
> **Execution Order**: Phase 1 → 2 → 3 → 4 → 5 → 6 → 7 (sequential, not parallel)

---

## Table of Contents

1. [Phase 1 – Pipeline Ordering Fix](#phase-1--pipeline-ordering-fix)
2. [Phase 2 – COMPLETED_BY_OTHER Elimination](#phase-2--completed_by_other-elimination)
3. [Phase 3 – APPROVAL_RESET_MANUAL](#phase-3--approval_reset_manual)
4. [Phase 4 – Pipeline Guard Rails](#phase-4--pipeline-guard-rails)
5. [Phase 5 – Missed State Tracking](#phase-5--missed-state-tracking)
6. [Phase 6 – Due Window Lock](#phase-6--due-window-lock)
7. [Phase 7 – Rotation Chores](#phase-7--rotation-chores)
8. [Schema Migration Strategy](#schema-migration-strategy)
9. [Cross-Phase Test Matrix](#cross-phase-test-matrix)

---

## Phase 1 – Pipeline Ordering Fix

**Goal**: Fix Reset-Before-Overdue evaluation order, auto-approve atomicity, non-recurring past-due guard, and persist batching.

**Fixes**: Gremlins #4 (Re-Overdue Loop / Issue #237), #5 (Phantom Overdue After Reset), #6 (Auto-Approve Race)

### 1.1 Affected Files

| File                        | Method(s)                                   | Change Type                  |
| --------------------------- | ------------------------------------------- | ---------------------------- |
| `managers/chore_manager.py` | `_on_midnight_rollover()` (L145)            | Reorder pipeline             |
| `managers/chore_manager.py` | `_on_periodic_update()` (L184)              | Reorder pipeline             |
| `managers/chore_manager.py` | `_process_approval_reset_entries()` (L1468) | Return type + persist param  |
| `managers/chore_manager.py` | `_process_overdue()` (L1311)                | Persist param + idempotency  |
| `managers/chore_manager.py` | `_claim_chore_locked()` (L296)              | Auto-approve atomicity       |
| `managers/chore_manager.py` | `_approve_chore_locked()` (L450)            | Non-recurring past-due guard |

### 1.2 Pipeline Reorder — Logic Flow

**Current order** (WRONG — both handlers):

```
scan → _process_overdue() → _process_approval_reset_entries()
```

**New order** (CORRECT):

```
scan → _process_approval_reset_entries() → filter overdue → _process_overdue()
```

#### 1.2.1 `_on_midnight_rollover()` — New Implementation

```python
async def _on_midnight_rollover(
    self,
    payload: dict[str, Any] | None = None,
    *,
    now_utc: datetime | None = None,
    trigger: str = "midnight",
) -> int:
    """Handle midnight rollover - perform nightly chore maintenance."""
    const.LOGGER.debug("ChoreManager: Processing midnight rollover")
    if now_utc is None:
        now_utc = dt_util.utcnow()
    try:
        # Single-pass scan with midnight trigger
        scan = self.process_time_checks(now_utc, trigger=trigger)

        # Phase A: Resets FIRST (returns count + set of reset pairs)
        reset_count, reset_pairs = await self._process_approval_reset_entries(
            scan, now_utc, trigger, persist=False
        )

        # Phase B: Overdue, EXCLUDING anything just reset
        filtered_overdue = [
            e for e in scan["overdue"]
            if (e["kid_id"], e["chore_id"]) not in reset_pairs
        ]
        await self._process_overdue(filtered_overdue, now_utc, persist=False)

        # Phase C: Single persist for all changes
        if reset_count > 0 or filtered_overdue:
            self._coordinator._persist()
            self._coordinator.async_set_updated_data(self._coordinator._data)

        return reset_count
    except Exception:
        const.LOGGER.exception("ChoreManager: Error during midnight rollover")
        return 0
```

#### 1.2.2 `_on_periodic_update()` — New Implementation

```python
async def _on_periodic_update(
    self,
    payload: dict[str, Any] | None = None,
    *,
    now_utc: datetime | None = None,
    trigger: str = "due_date",
) -> int:
    """Handle periodic update - perform interval maintenance tasks."""
    try:
        if now_utc is None:
            now_utc = dt_util.utcnow()

        # Single-pass scan categorizes ALL actionable items
        scan = self.process_time_checks(now_utc, trigger=trigger)

        # Phase A: Resets FIRST
        reset_count, reset_pairs = await self._process_approval_reset_entries(
            scan, now_utc, trigger, persist=False
        )

        # Phase B: Overdue, EXCLUDING anything just reset
        filtered_overdue = [
            e for e in scan["overdue"]
            if (e["kid_id"], e["chore_id"]) not in reset_pairs
        ]
        await self._process_overdue(filtered_overdue, now_utc, persist=False)

        # Phase C: Notifications (read-only, no persist needed)
        self._process_due_window(scan["in_due_window"])
        self._process_due_reminder(scan["due_reminder"])

        # Phase D: Single persist for all state changes
        if reset_count > 0 or filtered_overdue:
            self._coordinator._persist()
            self._coordinator.async_set_updated_data(self._coordinator._data)

        return reset_count
    except Exception:
        const.LOGGER.exception("ChoreManager: Error during periodic update")
        return 0
```

### 1.3 `_process_approval_reset_entries()` — API Change

**Current signature**:

```python
async def _process_approval_reset_entries(
    self, scan, now_utc, trigger="due_date"
) -> int:
```

**New signature**:

```python
async def _process_approval_reset_entries(
    self,
    scan: dict[str, list[ChoreTimeEntry]],
    now_utc: datetime,
    trigger: str = "due_date",
    *,
    persist: bool = True,  # NEW: backward-compatible default
) -> tuple[int, set[tuple[str, str]]]:  # NEW: return reset pairs
```

**Key changes inside method body**:

```python
async def _process_approval_reset_entries(
    self,
    scan: dict[str, list[ChoreTimeEntry]],
    now_utc: datetime,
    trigger: str = "due_date",
    *,
    persist: bool = True,
) -> tuple[int, set[tuple[str, str]]]:
    """Process approval boundary reset entries from unified scan.

    Returns:
        Tuple of (reset_count, reset_pairs) where reset_pairs is a set
        of (kid_id, chore_id) tuples that were reset in this pass.
    """
    reset_count = 0
    reset_pairs: set[tuple[str, str]] = set()  # NEW: track what was reset

    # Process SHARED/SHARED_FIRST chores (existing loop)
    for entry in scan.get("approval_reset_shared", []):
        chore_id = entry["chore_id"]
        # ... existing category check ...

        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        for kid_id in assigned_kids:
            if not kid_id:
                continue
            # ... existing pending claim handling ...
            self._transition_chore_state(
                kid_id, chore_id, const.CHORE_STATE_PENDING,
                reset_approval_period=True, clear_ownership=True,
            )
            reset_count += 1
            reset_pairs.add((kid_id, chore_id))  # NEW: track pair

    # Process INDEPENDENT chores (existing loop)
    for entry in scan.get("approval_reset_independent", []):
        chore_id = entry["chore_id"]
        # ... existing per-kid loop ...
        for kid_entry in kid_entries:
            kid_id = kid_entry["kid_id"]
            # ... existing category check ...
            self._transition_chore_state(
                kid_id, chore_id, const.CHORE_STATE_PENDING,
                reset_approval_period=True, clear_ownership=True,
            )
            reset_count += 1
            reset_pairs.add((kid_id, chore_id))  # NEW: track pair

    if reset_count > 0:
        const.LOGGER.debug(
            "Approval boundary resets (%s): %d kid(s) reset",
            trigger, reset_count,
        )

    # Conditional persist (NEW)
    if persist and reset_count > 0:
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)

    return reset_count, reset_pairs  # CHANGED: return tuple
```

### 1.4 `_process_overdue()` — API Change

**Current signature**:

```python
async def _process_overdue(
    self, entries: list[ChoreTimeEntry], now_utc: datetime
) -> None:
```

**New signature**:

```python
async def _process_overdue(
    self,
    entries: list[ChoreTimeEntry],
    now_utc: datetime,
    *,
    persist: bool = True,  # NEW: backward-compatible default
) -> None:
```

**Key changes inside method body**:

```python
async def _process_overdue(
    self,
    entries: list[ChoreTimeEntry],
    now_utc: datetime,
    *,
    persist: bool = True,
) -> None:
    """Process overdue entries - mark as overdue and emit signals."""
    if not entries:
        return

    marked_count = 0
    for entry in entries:
        chore_id = entry["chore_id"]
        kid_id = entry["kid_id"]
        # ... existing validation ...

        # Calculate and apply state transition via Engine
        effects = ChoreEngine.calculate_transition(
            chore_data=chore_data,
            actor_kid_id=kid_id,
            action=CHORE_ACTION_OVERDUE,
            kids_assigned=kids_assigned,
            kid_name=kid_name,
        )

        for effect in effects:
            self._apply_effect(effect, chore_id)

        self._update_global_state(chore_id)

        # REMOVED: per-entry persist (was line 1366)
        # self._coordinator._persist()  # ← DELETE THIS LINE

        # Emit signal (unchanged)
        days_overdue = (now_utc - due_dt).days
        self.emit(
            const.SIGNAL_SUFFIX_CHORE_OVERDUE,
            kid_id=kid_id, kid_name=kid_name,
            chore_id=chore_id,
            chore_name=chore_data.get(const.DATA_CHORE_NAME, ""),
            days_overdue=days_overdue, due_date=due_dt.isoformat(),
            chore_labels=chore_data.get(const.DATA_CHORE_LABELS, []),
        )
        marked_count += 1

    if marked_count > 0:
        const.LOGGER.debug("Processed %d overdue chore(s)", marked_count)

    # Conditional persist (NEW — only if persist=True)
    if persist and marked_count > 0:
        self._coordinator._persist()
        self._coordinator.async_set_updated_data(self._coordinator._data)
```

### 1.5 Auto-Approve Atomicity Fix

**Location**: `_claim_chore_locked()` (L397-400)

**Current code** (race condition):

```python
if auto_approve:
    self.hass.async_create_task(
        self.approve_chore("auto_approve", kid_id, chore_id)
    )
```

**New code** (atomic):

```python
if auto_approve:
    # Atomic: call locked impl directly (already inside lock)
    await self._approve_chore_locked("auto_approve", kid_id, chore_id)
```

**Why this works**: `_claim_chore_locked()` is called from `claim_chore()` which holds the per-kid+chore lock. Calling `_approve_chore_locked()` directly avoids the lock re-acquisition that `approve_chore()` would attempt (which would deadlock). Since we're already inside the lock context, calling the `_locked` variant is safe.

**Required**: The persist call at L403 (`self._coordinator._persist()`) happens AFTER the auto-approve returns. Since `_approve_chore_locked()` persists internally, the L403 persist is redundant for auto-approve cases. To align with the persist-batching invariant established in §1.2, the conditional persist is **required**:

```python
if auto_approve:
    await self._approve_chore_locked("auto_approve", kid_id, chore_id)
    # _approve_chore_locked already persisted; skip our persist
else:
    # Only persist claim if not auto-approving (approve handles its own persist)
    self._coordinator._persist()
```

> **Builder**: Verify `_approve_chore_locked()` persists internally before applying this pattern. If it delegates to pipeline persist (Phase 1), adjust accordingly.

### 1.6 Non-Recurring Past-Due Guard

**Location**: `_approve_chore_locked()` after UPON_COMPLETION reset block (~L669)

**Insert after the `should_reset_immediately` block (after L669), before the "non-UPON_COMPLETION" comment at L670**:

```python
        # === NON-RECURRING PAST-DUE GUARD (Phase 1) ===
        # For FREQUENCY_NONE chores that just reset via UPON_COMPLETION:
        # Clear the past due date so the next scan doesn't immediately re-overdue.
        # The chore stays PENDING indefinitely until user sets a new due date.
        if should_reset_immediately:
            frequency = chore_data.get(
                const.DATA_CHORE_FREQUENCY, const.FREQUENCY_NONE
            )
            if frequency == const.FREQUENCY_NONE:
                completion_criteria = chore_data.get(
                    const.DATA_CHORE_COMPLETION_CRITERIA,
                    const.COMPLETION_CRITERIA_INDEPENDENT,
                )
                if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
                    # Clear per-kid due date
                    per_kid_dates = chore_data.get(
                        const.DATA_CHORE_PER_KID_DUE_DATES, {}
                    )
                    per_kid_dates.pop(kid_id, None)
                else:
                    # Clear chore-level due date (SHARED/SHARED_FIRST)
                    chore_data.pop(const.DATA_CHORE_DUE_DATE, None)

                const.LOGGER.debug(
                    "Cleared past due date for non-recurring chore %s "
                    "after UPON_COMPLETION reset (prevents re-overdue)",
                    chore_id,
                )
```

### 1.7 Test Scenarios — Phase 1

| #     | Test Name                                        | Validates                                                     |
| ----- | ------------------------------------------------ | ------------------------------------------------------------- |
| T1.1  | `test_midnight_processes_reset_before_overdue`   | Pipeline order: reset runs before overdue                     |
| T1.2  | `test_periodic_processes_reset_before_overdue`   | Same for periodic handler                                     |
| T1.3  | `test_overdue_excluded_when_chore_just_reset`    | Filtered overdue list excludes reset pairs                    |
| T1.4  | `test_upon_completion_freq_none_clears_due_date` | Non-recurring guard: due date cleared                         |
| T1.5  | `test_upon_completion_freq_none_no_re_overdue`   | Full cycle: approve → reset → no overdue                      |
| T1.6  | `test_auto_approve_is_atomic_with_claim`         | Auto-approve runs inline, not as background task              |
| T1.7  | `test_auto_approve_shared_first_no_race`         | SHARED_FIRST + auto-approve: no intermediate state leak       |
| T1.8  | `test_pipeline_single_persist_per_tick`          | Verify persist called once per pipeline, not per entry        |
| T1.9  | `test_process_approval_reset_returns_pairs`      | Return type is `tuple[int, set[tuple[str, str]]]`             |
| T1.10 | `test_gremlin_4_re_overdue_loop_fixed`           | Issue #237 regression: freq_none + upon_completion + past due |
| T1.11 | `test_gremlin_5_phantom_overdue_after_reset`     | No false overdue stats on reset+overdue tick                  |

**Test pattern** (service-based, using scenario fixtures):

```python
async def test_upon_completion_freq_none_no_re_overdue(
    hass: HomeAssistant,
    coordinator: KidsChoresCoordinator,
    scenario_medium,  # Has kids + chores set up
) -> None:
    """Approve chore with upon_completion + freq_none: no re-overdue."""
    # Setup: Create chore with upon_completion, frequency_none, past due date
    chore_id = await create_test_chore(
        coordinator,
        approval_reset=const.APPROVAL_RESET_UPON_COMPLETION,
        frequency=const.FREQUENCY_NONE,
        due_date=dt_now_iso(hours=-24),  # 24h in the past
    )
    kid_id = scenario_medium["kids"][0]["internal_id"]

    # Act: Kid claims → parent approves
    await hass.services.async_call(DOMAIN, "claim_chore", {
        SERVICE_FIELD_KID_ID: kid_id,
        SERVICE_FIELD_CHORE_ID: chore_id,
    })
    await hass.services.async_call(DOMAIN, "approve_chore", {
        SERVICE_FIELD_KID_ID: kid_id,
        SERVICE_FIELD_CHORE_ID: chore_id,
    })

    # Verify: Chore is PENDING (reset by UPON_COMPLETION), NOT overdue
    kid_chore = coordinator.chore_manager._get_kid_chore_data(kid_id, chore_id)
    assert kid_chore[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING

    # Verify: Due date was cleared (non-recurring guard)
    chore_data = coordinator.chores_data[chore_id]
    assert chore_data.get(const.DATA_CHORE_DUE_DATE) is None

    # Act: Run periodic update (should NOT mark overdue)
    await coordinator.chore_manager._on_periodic_update(now_utc=dt_util.utcnow())

    # Verify: Still PENDING, not OVERDUE
    kid_chore = coordinator.chore_manager._get_kid_chore_data(kid_id, chore_id)
    assert kid_chore[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
```

### 1.8 Validation Commands

```bash
pytest tests/test_chore_scheduling.py tests/test_approval_reset_overdue_interaction.py -v
pytest tests/ -v --tb=line
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
```

---

## Phase 2 – COMPLETED_BY_OTHER Elimination

**Goal**: Remove `COMPLETED_BY_OTHER` as a persisted state. Make SHARED_FIRST blocking a computed check in `can_claim()`. Sensors still display `completed_by_other` as a computed display state for dashboard compatibility.

**Decision D4 Condition**: Sensors must still present `completed_by_other` as a display state to the dashboard.

### 2.1 Affected Files

| File                        | Method(s)                                         | Change Type                                |
| --------------------------- | ------------------------------------------------- | ------------------------------------------ |
| `engines/chore_engine.py`   | `VALID_TRANSITIONS` (L91)                         | Remove entry                               |
| `engines/chore_engine.py`   | `can_claim_chore()` (L431)                        | Add `other_kids_states` param              |
| `engines/chore_engine.py`   | `_plan_claim_effects()` (L243)                    | Remove other-kid effects                   |
| `engines/chore_engine.py`   | `_plan_approve_effects()` (L286)                  | Remove other-kid effects                   |
| `engines/chore_engine.py`   | `_plan_disapprove_effects()` (L322)               | Only reset actor                           |
| `engines/chore_engine.py`   | `_plan_undo_effects()` (L368)                     | Only reset actor                           |
| `engines/chore_engine.py`   | `compute_global_chore_state()` (L783)             | Update counting                            |
| `managers/chore_manager.py` | `can_claim_chore()` (L2442)                       | Pass other kids' states                    |
| `managers/chore_manager.py` | `get_chore_status_context()` (L2537)              | Compute display state                      |
| `managers/chore_manager.py` | `_transition_chore_state()` (L2830)               | Remove list management                     |
| `const.py`                  | Keep `CHORE_STATE_COMPLETED_BY_OTHER`             | Still used for display                     |
| `const.py`                  | Remove `DATA_KID_COMPLETED_BY_OTHER_CHORES` usage | Storage cleanup                            |
| `migration_pre_v50.py`      | New migration function                            | Convert states + remove lists              |
| Dashboard YAML              | State map references                              | No change needed (display state preserved) |

### 2.2 Engine Changes — `VALID_TRANSITIONS`

**Remove** the COMPLETED_BY_OTHER entry from the FSM:

```python
# BEFORE (L91-128):
VALID_TRANSITIONS: dict[str, list[str]] = {
    const.CHORE_STATE_PENDING: [
        const.CHORE_STATE_CLAIMED,
        const.CHORE_STATE_OVERDUE,
        const.CHORE_STATE_COMPLETED_BY_OTHER,  # ← REMOVE THIS LINE
    ],
    # ...
    # From COMPLETED_BY_OTHER: Reset at scheduled time  ← REMOVE BLOCK
    const.CHORE_STATE_COMPLETED_BY_OTHER: [              # ← REMOVE
        const.CHORE_STATE_PENDING,                        # ← REMOVE
    ],                                                    # ← REMOVE
    # ...
}

# AFTER:
VALID_TRANSITIONS: dict[str, list[str]] = {
    const.CHORE_STATE_PENDING: [
        const.CHORE_STATE_CLAIMED,
        const.CHORE_STATE_OVERDUE,
    ],
    const.CHORE_STATE_CLAIMED: [
        const.CHORE_STATE_APPROVED,
        const.CHORE_STATE_PENDING,
        const.CHORE_STATE_OVERDUE,
    ],
    const.CHORE_STATE_APPROVED: [
        const.CHORE_STATE_PENDING,
    ],
    const.CHORE_STATE_OVERDUE: [
        const.CHORE_STATE_CLAIMED,
        const.CHORE_STATE_PENDING,
        const.CHORE_STATE_APPROVED,
    ],
    # Global states (unchanged)
    const.CHORE_STATE_CLAIMED_IN_PART: [...],
    const.CHORE_STATE_APPROVED_IN_PART: [...],
}
```

### 2.3 Engine Changes — `can_claim_chore()`

**New signature** with backward-compatible `other_kids_states` parameter:

```python
@staticmethod
def can_claim_chore(
    kid_chore_data: dict[str, Any],
    chore_data: ChoreData | dict[str, Any],
    has_pending_claim: bool,
    is_approved_in_period: bool,
    *,
    other_kids_states: dict[str, str] | None = None,  # NEW
) -> tuple[bool, str | None]:
    """Check if a kid can claim a specific chore.

    Args:
        kid_chore_data: The kid's tracking data for this chore
        chore_data: The chore definition
        has_pending_claim: Result of chore_has_pending_claim()
        is_approved_in_period: Result of chore_is_approved_in_period()
        other_kids_states: For SHARED_FIRST - dict mapping other kid IDs
            to their current state for this chore. If any other kid is
            CLAIMED or APPROVED, this kid cannot claim.

    Returns:
        Tuple of (can_claim: bool, error_key: str | None)
    """
    current_state = kid_chore_data.get(
        const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
    )

    # REMOVED: Check 1 for COMPLETED_BY_OTHER state (no longer stored)
    # OLD: if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER: ...

    # NEW Check 1: SHARED_FIRST blocking via other kids' states
    criteria = chore_data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )
    if (
        criteria == const.COMPLETION_CRITERIA_SHARED_FIRST
        and other_kids_states
    ):
        blocking_states = {const.CHORE_STATE_CLAIMED, const.CHORE_STATE_APPROVED}
        for other_kid_id, other_state in other_kids_states.items():
            if other_state in blocking_states:
                return (False, const.TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER)

    # Check 2: pending claim blocks (unchanged)
    allow_multiple = ChoreEngine.chore_allows_multiple_claims(chore_data)
    if not allow_multiple and has_pending_claim:
        return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)

    # Check 3: already approved (unchanged)
    if not allow_multiple and is_approved_in_period:
        return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

    return (True, None)
```

### 2.4 Manager Changes — `can_claim_chore()` Wrapper

**Location**: `managers/chore_manager.py` L2442

```python
def can_claim_chore(self, kid_id: str, chore_id: str) -> tuple[bool, str | None]:
    """Check if a kid can claim a specific chore."""
    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

    # REMOVED: Check 1 for COMPLETED_BY_OTHER state
    # OLD: if current_state == const.CHORE_STATE_COMPLETED_BY_OTHER: ...

    # NEW: Build other_kids_states for SHARED_FIRST blocking
    chore_data = self._coordinator.chores_data.get(chore_id, {})
    criteria = chore_data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )
    other_kids_states: dict[str, str] | None = None
    if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        other_kids_states = {}
        for other_kid_id in assigned_kids:
            if other_kid_id and other_kid_id != kid_id:
                other_data = self._get_kid_chore_data(other_kid_id, chore_id)
                other_kids_states[other_kid_id] = other_data.get(
                    const.DATA_KID_CHORE_DATA_STATE,
                    const.CHORE_STATE_PENDING,
                )

    # Delegate to engine (allow_multiple and approved checks unchanged)
    allow_multiple_claims = self._chore_allows_multiple_claims(chore_id)
    if not allow_multiple_claims and self.chore_has_pending_claim(kid_id, chore_id):
        return (False, const.TRANS_KEY_ERROR_CHORE_PENDING_CLAIM)
    if not allow_multiple_claims and self.chore_is_approved_in_period(kid_id, chore_id):
        return (False, const.TRANS_KEY_ERROR_CHORE_ALREADY_APPROVED)

    return ChoreEngine.can_claim_chore(
        kid_chore_data=kid_chore_data,
        chore_data=chore_data,
        has_pending_claim=self.chore_has_pending_claim(kid_id, chore_id),
        is_approved_in_period=self.chore_is_approved_in_period(kid_id, chore_id),
        other_kids_states=other_kids_states,  # NEW
    )
```

> **Builder Note**: The manager wrapper currently duplicates some checks that the engine also does. After adding `other_kids_states`, the manager can be simplified to delegate entirely to the engine. Consider consolidating to avoid check duplication — but only if all checks pass through the engine consistently.

### 2.5 Engine Changes — `_plan_claim_effects()` Simplification

**Current** (L243-284): SHARED_FIRST emits effects for actor + ALL other kids (COMPLETED_BY_OTHER).

**New**: SHARED_FIRST only emits effect for actor kid:

```python
@staticmethod
def _plan_claim_effects(
    criteria: str,
    actor_kid_id: str,
    kids_assigned: list[str],
    kid_name: str,
) -> list[TransitionEffect]:
    """Plan effects for a claim action."""
    effects: list[TransitionEffect] = []

    # ALL criteria types: only actor transitions on claim
    # SHARED_FIRST blocking is now handled by can_claim_chore()
    effects.append(
        TransitionEffect(
            kid_id=actor_kid_id,
            new_state=const.CHORE_STATE_CLAIMED,
            update_stats=True,
            set_claimed_by=kid_name,
        )
    )

    # REMOVED: SHARED_FIRST no longer sets other kids to COMPLETED_BY_OTHER
    # OLD: for other_kid_id in kids_assigned:
    #          if other_kid_id != actor_kid_id:
    #              effects.append(TransitionEffect(
    #                  kid_id=other_kid_id,
    #                  new_state=const.CHORE_STATE_COMPLETED_BY_OTHER, ...))

    return effects
```

### 2.6 Engine Changes — `_plan_approve_effects()` Simplification

**Current** (L286-320): SHARED_FIRST emits COMPLETED_BY_OTHER for other kids on approve.

**New**: Only emit effect for actor:

```python
@staticmethod
def _plan_approve_effects(
    criteria: str,
    actor_kid_id: str,
    kids_assigned: list[str],
    kid_name: str,
    points: float,
) -> list[TransitionEffect]:
    """Plan effects for an approve action."""
    effects: list[TransitionEffect] = []

    effects.append(
        TransitionEffect(
            kid_id=actor_kid_id,
            new_state=const.CHORE_STATE_APPROVED,
            update_stats=True,
            points=points,
            set_completed_by=kid_name,
        )
    )

    # REMOVED: SHARED_FIRST no longer updates other kids' state on approve
    # Other kids stay PENDING; can_claim() blocks them via other_kids_states

    return effects
```

### 2.7 Engine Changes — `_plan_disapprove_effects()` & `_plan_undo_effects()`

**Current**: SHARED_FIRST resets ALL kids (including those in COMPLETED_BY_OTHER).

**New**: SHARED_FIRST only resets the actor (other kids are already PENDING):

```python
@staticmethod
def _plan_disapprove_effects(
    criteria: str,
    actor_kid_id: str,
    kids_assigned: list[str],
    is_overdue: bool,
) -> list[TransitionEffect]:
    """Plan effects for a disapprove action."""
    effects: list[TransitionEffect] = []
    target_state = (
        const.CHORE_STATE_OVERDUE if is_overdue else const.CHORE_STATE_PENDING
    )

    # ALL criteria: only actor transitions on disapprove
    # SHARED_FIRST: other kids are already PENDING (never changed state)
    effects.append(
        TransitionEffect(
            kid_id=actor_kid_id,
            new_state=target_state,
            update_stats=True,
            clear_claimed_by=True,
            clear_completed_by=True,
        )
    )

    # REMOVED: SHARED_FIRST loop over all kids
    # OLD: for kid_id in kids_assigned: effects.append(...)

    return effects
```

**Same pattern for `_plan_undo_effects()`** — only actor transitions, `update_stats=False`.

### 2.8 Engine Changes — `compute_global_chore_state()`

**Current** (L783-855): Counts COMPLETED_BY_OTHER implicitly.

**New**: SHARED_FIRST logic unchanged (already works correctly without COMPLETED_BY_OTHER counting):

```python
# SHARED_FIRST block (L836-843) — NO CHANGE NEEDED
# Current logic already looks for APPROVED > CLAIMED > OVERDUE > PENDING
# With Phase 2, other kids stay PENDING while actor is CLAIMED/APPROVED
# So count_claimed=1 and count_pending=N-1 → returns CLAIMED ✓
# count_approved=1 and count_pending=N-1 → returns APPROVED ✓
```

The existing SHARED_FIRST block at L836-843 already handles this correctly because:

- When actor claims: `count_claimed=1, count_pending=N-1` → `count_claimed > 0` → returns `CLAIMED` ✓
- When actor approved: `count_approved=1, count_pending=N-1` → `count_approved > 0` → returns `APPROVED` ✓
- When disapproved: all PENDING → `count_pending == total` → returns `PENDING` ✓

**No code change needed in `compute_global_chore_state()`.** Verify with tests.

### 2.9 Manager Changes — `_transition_chore_state()` List Removal

**Location**: L2841-2850

**Remove entire block**:

```python
# REMOVE THIS BLOCK:
# Manage completed_by_other_chores list
# Sensors check this list for COMPLETED_BY_OTHER state display
completed_by_other_list = kid_info.setdefault(
    const.DATA_KID_COMPLETED_BY_OTHER_CHORES, []
)
if new_state == const.CHORE_STATE_COMPLETED_BY_OTHER:
    if chore_id not in completed_by_other_list:
        completed_by_other_list.append(chore_id)
elif chore_id in completed_by_other_list:
    completed_by_other_list.remove(chore_id)
```

### 2.10 Manager Changes — `get_chore_status_context()` Computed Display State

**Location**: L2537. Replace the `completed_by_other_chores` list lookup with a computed check.

```python
def get_chore_status_context(self, kid_id: str, chore_id: str) -> dict[str, Any]:
    """Return all derived chore states for a kid+chore in one call."""
    # Single data fetch
    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

    # Pre-compute all status flags
    has_pending = ChoreEngine.chore_has_pending_claim(kid_chore_data)
    is_overdue = ChoreEngine.chore_is_overdue(kid_chore_data)
    is_due = self.chore_is_due(kid_id, chore_id)
    is_approved = self.chore_is_approved_in_period(kid_id, chore_id)
    can_claim, claim_error = self.can_claim_chore(kid_id, chore_id)
    can_approve, approve_error = self.can_approve_chore(kid_id, chore_id)

    # CHANGED: Compute completed_by_other from other kids' states
    # instead of reading from stored list
    chore_data = self._coordinator.chores_data.get(chore_id, {})
    criteria = chore_data.get(
        const.DATA_CHORE_COMPLETION_CRITERIA,
        const.COMPLETION_CRITERIA_INDEPENDENT,
    )
    is_completed_by_other = False
    claimed_by_kid_name: str | None = None

    if criteria == const.COMPLETION_CRITERIA_SHARED_FIRST:
        assigned_kids = chore_data.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        for other_kid_id in assigned_kids:
            if other_kid_id and other_kid_id != kid_id:
                other_data = self._get_kid_chore_data(other_kid_id, chore_id)
                other_state = other_data.get(
                    const.DATA_KID_CHORE_DATA_STATE,
                    const.CHORE_STATE_PENDING,
                )
                if other_state in {
                    const.CHORE_STATE_CLAIMED,
                    const.CHORE_STATE_APPROVED,
                }:
                    is_completed_by_other = True
                    # Get the other kid's name for display
                    claimed_by_kid_name = other_data.get(
                        const.DATA_CHORE_CLAIMED_BY, None
                    )
                    break

    # Raw stored state
    stored_state = kid_chore_data.get(
        const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
    )

    # Derive display state (priority unchanged)
    # approved > completed_by_other > claimed > overdue > due > pending
    if is_approved:
        display_state = const.CHORE_STATE_APPROVED
    elif is_completed_by_other:
        display_state = const.CHORE_STATE_COMPLETED_BY_OTHER  # Still used for DISPLAY
    elif has_pending:
        display_state = const.CHORE_STATE_CLAIMED
    elif is_overdue:
        display_state = const.CHORE_STATE_OVERDUE
    elif is_due:
        display_state = const.CHORE_STATE_DUE
    else:
        display_state = const.CHORE_STATE_PENDING

    return {
        "state": display_state,
        "stored_state": stored_state,
        "is_overdue": is_overdue,
        "is_due": is_due,
        "has_pending_claim": has_pending,
        "is_approved_in_period": is_approved,
        "is_completed_by_other": is_completed_by_other,
        "claimed_by_kid_name": claimed_by_kid_name,  # NEW: who claimed it
        "can_claim": can_claim,
        "can_claim_error": claim_error,
        "can_approve": can_approve,
        "can_approve_error": approve_error,
        "due_date": (
            due_dt.isoformat()
            if (due_dt := self.get_due_date(chore_id, kid_id))
            else None
        ),
        "last_completed": self.get_chore_last_completed(chore_id, kid_id),
    }
```

**Key insight**: The display state `completed_by_other` is COMPUTED from other kids' live states, not read from a stored list. The dashboard still receives the same state string and renders correctly. No dashboard YAML changes needed for this.

### 2.11 Schema Migration

**Location**: `migration_pre_v50.py` — add new migration function.

> **Note**: Schema version increment and migration details depend on whether other phases also need migration. Since this is all schema 44, the migration should be part of the schema 44 migration or a new schema 45 if 44 is already stamped.

**Builder decision**: If schema 44 is already applied, bump to 45. If schema 44 is in-flight, include in 44.

```python
def _migrate_completed_by_other_elimination(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate: Remove COMPLETED_BY_OTHER state and kid lists.

    Phase 2 of Chore State Architecture Hardening:
    - Convert any stored 'completed_by_other' states to 'pending'
    - Remove 'completed_by_other_chores' lists from kid_info
    """
    kids = data.get("kids", {})
    chores = data.get("chores", {})

    for kid_id, kid_info in kids.items():
        # Remove the completed_by_other_chores tracking list
        kid_info.pop("completed_by_other_chores", None)

        # Convert any COMPLETED_BY_OTHER states to PENDING
        chore_data_map = kid_info.get("chore_data", {})
        for chore_id, kid_chore_data in chore_data_map.items():
            if kid_chore_data.get("state") == "completed_by_other":
                kid_chore_data["state"] = "pending"
                # Clear ownership since state is now PENDING
                kid_chore_data.pop("claimed_by", None)
                kid_chore_data.pop("completed_by", None)

    return data
```

### 2.12 Dashboard Impact Assessment

**Dashboard YAML references** (`kc_dashboard_all.yaml` lines ~449, 467, 477, 486):

- State map key: `completed_by_other` → icon color grey
- Badge color: blue
- Badge icon: `mdi:lock`

**No change needed**: The `get_chore_status_context()` still returns `completed_by_other` as a display state. The sensor exposes this to the dashboard. The dashboard reads the display state, not stored state. **Full backward compatibility**.

### 2.13 Test Scenarios — Phase 2

| #     | Test Name                                           | Validates                                                                  |
| ----- | --------------------------------------------------- | -------------------------------------------------------------------------- |
| T2.1  | `test_shared_first_claim_other_kids_stay_pending`   | Other kids remain PENDING on claim                                         |
| T2.2  | `test_shared_first_claim_blocks_other_kids`         | `can_claim()` returns False for other kids                                 |
| T2.3  | `test_shared_first_approve_other_kids_stay_pending` | Other kids remain PENDING on approve                                       |
| T2.4  | `test_shared_first_disapprove_only_resets_actor`    | Only actor transitions, others unchanged                                   |
| T2.5  | `test_shared_first_undo_only_resets_actor`          | Only actor transitions, others unchanged                                   |
| T2.6  | `test_shared_first_display_state_computed`          | `get_chore_status_context()` returns `completed_by_other` for blocked kids |
| T2.7  | `test_shared_first_display_includes_claimant_name`  | `claimed_by_kid_name` populated                                            |
| T2.8  | `test_global_state_shared_first_no_cbo`             | `compute_global_chore_state()` correct without COMPLETED_BY_OTHER          |
| T2.9  | `test_migration_converts_cbo_states`                | Schema migration: COMPLETED_BY_OTHER → PENDING                             |
| T2.10 | `test_migration_removes_cbo_lists`                  | Schema migration: list removed from kid_info                               |
| T2.11 | `test_no_completed_by_other_in_transitions`         | VALID_TRANSITIONS has no CBO entry                                         |

---

## Phase 3 – APPROVAL_RESET_MANUAL

**Goal**: Add `APPROVAL_RESET_MANUAL` option that never auto-resets.

### 3.1 Affected Files

| File                      | Change                                              |
| ------------------------- | --------------------------------------------------- |
| `const.py` (~L1418)       | Add `APPROVAL_RESET_MANUAL` constant                |
| `const.py` (~L1419)       | Add to `APPROVAL_RESET_TYPE_OPTIONS` list           |
| `engines/chore_engine.py` | No change (already returns False for unknown types) |
| `translations/en.json`    | Add label for manual reset                          |
| Tests                     | New test for manual reset behavior                  |

### 3.2 Constant Addition

```python
# const.py — after APPROVAL_RESET_UPON_COMPLETION (L1418)
APPROVAL_RESET_MANUAL: Final = "manual"

# Update options list (L1419-1425)
APPROVAL_RESET_TYPE_OPTIONS: Final = [
    {"value": APPROVAL_RESET_AT_MIDNIGHT_ONCE, "label": "at_midnight_once"},
    {"value": APPROVAL_RESET_AT_MIDNIGHT_MULTI, "label": "at_midnight_multi"},
    {"value": APPROVAL_RESET_AT_DUE_DATE_ONCE, "label": "at_due_date_once"},
    {"value": APPROVAL_RESET_AT_DUE_DATE_MULTI, "label": "at_due_date_multi"},
    {"value": APPROVAL_RESET_UPON_COMPLETION, "label": "upon_completion"},
    {"value": APPROVAL_RESET_MANUAL, "label": "manual"},  # NEW
]
```

### 3.3 Engine Verification

`should_process_at_boundary()` (L960-994) already returns `False` for any type not in `midnight_types` or `due_date_types`. Since `"manual"` is neither, it naturally falls through to `return False`. **No engine change needed.**

`calculate_boundary_action()` is never called for MANUAL because `should_process_at_boundary()` filters it out first.

### 3.4 Translation Entry

```json
{
  "options_flow": {
    "step": {
      "chore_settings": {
        "data": {
          "approval_reset_type": {
            "options": {
              "manual": "Manual reset only"
            }
          }
        }
      }
    }
  }
}
```

> **Builder Note**: Check exact translation JSON structure — may be in a different key path depending on how option selectors are translated. Search for existing `"at_midnight_once"` translation to find the right path.

### 3.5 Test Scenarios — Phase 3

| #    | Test Name                                           | Validates                              |
| ---- | --------------------------------------------------- | -------------------------------------- |
| T3.1 | `test_manual_reset_stays_approved_through_midnight` | Chore doesn't reset at midnight        |
| T3.2 | `test_manual_reset_stays_approved_through_periodic` | Chore doesn't reset at periodic        |
| T3.3 | `test_manual_reset_can_be_reset_via_service`        | `reset_chore_to_pending` service works |
| T3.4 | `test_manual_reset_appears_in_options_flow`         | Option shows in chore settings         |

---

## Phase 4 – Pipeline Guard Rails

**Goal**: Add debug-mode invariant enforcement. **Debug only — not production assertions.**

### 4.1 Affected Files

| File                        | Change                                        |
| --------------------------- | --------------------------------------------- |
| `managers/chore_manager.py` | Add `_assert_single_state_per_tick()` helper  |
| `managers/chore_manager.py` | Add idempotency guard in `_process_overdue()` |
| `docs/ARCHITECTURE.md`      | Document driver interaction matrix            |

### 4.2 Debug-Mode State Validator

```python
def _assert_single_state_per_tick(
    self,
    modified_pairs: set[tuple[str, str]],
    kid_id: str,
    chore_id: str,
    operation: str,
) -> None:
    """Debug-mode check: ensure no (kid, chore) is modified twice per tick.

    Only logs warnings — does NOT raise exceptions in production.

    Args:
        modified_pairs: Set of (kid_id, chore_id) already modified this tick
        kid_id: Current kid being modified
        chore_id: Current chore being modified
        operation: Description of the operation ("overdue", "reset", etc.)
    """
    pair = (kid_id, chore_id)
    if pair in modified_pairs:
        const.LOGGER.warning(
            "INVARIANT VIOLATION: (%s, %s) modified twice in same tick. "
            "Operation: %s. Previous operations already applied. "
            "This indicates a pipeline ordering issue",
            kid_id, chore_id, operation,
        )
    modified_pairs.add(pair)
```

**Usage in pipeline handlers**:

```python
async def _on_periodic_update(self, ...):
    scan = self.process_time_checks(now_utc, trigger=trigger)
    modified_pairs: set[tuple[str, str]] = set()  # Track per tick

    # Phase A: Resets
    reset_count, reset_pairs = await self._process_approval_reset_entries(
        scan, now_utc, trigger, persist=False
    )
    modified_pairs.update(reset_pairs)

    # Phase B: Overdue
    for entry in filtered_overdue:
        self._assert_single_state_per_tick(
            modified_pairs, entry["kid_id"], entry["chore_id"], "overdue"
        )
    await self._process_overdue(filtered_overdue, now_utc, persist=False)
    # ...
```

### 4.3 Idempotency Guard in `_process_overdue()`

```python
# Inside the loop, before applying effects:
kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)
current_state = kid_chore_data.get(
    const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING
)
if current_state == const.CHORE_STATE_OVERDUE:
    const.LOGGER.debug(
        "Chore %s already OVERDUE for kid %s, skipping",
        chore_id, kid_id,
    )
    continue  # Already overdue, skip
```

### 4.4 Driver Interaction Matrix (for ARCHITECTURE.md)

```markdown
## Logic Driver Interaction Matrix

| Combination                           | Behavior                          | Notes         |
| ------------------------------------- | --------------------------------- | ------------- |
| UPON_COMPLETION + FREQ_NONE           | Reset immediately, clear due date | Phase 1 guard |
| AT*MIDNIGHT*\* + HOLD_PENDING         | Keep CLAIMED through midnight     | By design     |
| AT_DUE_DATE + OVERDUE_AT_DUE_DATE     | Overdue blocks reset              | By design     |
| AT_DUE_DATE + CLEAR_AT_APPROVAL_RESET | Overdue clears at reset           | By design     |
| SHARED_FIRST + AUTO_APPROVE           | Atomic claim+approve              | Phase 1 fix   |
| MANUAL + any                          | Never auto-resets                 | Phase 3       |
| SHARED_FIRST + UPON_COMPLETION        | Reset when all approved           | Existing      |
```

### 4.5 Test Scenarios — Phase 4

| #    | Test Name                                     | Validates                                |
| ---- | --------------------------------------------- | ---------------------------------------- |
| T4.1 | `test_invariant_warns_on_double_modification` | Warning logged when pair modified twice  |
| T4.2 | `test_idempotent_overdue_processing`          | Already-OVERDUE chore skipped            |
| T4.3 | `test_all_gremlins_produce_single_outcome`    | Each Gremlin config → one state per tick |

---

## Phase 5 – Missed State Tracking

**Goal**: Track when chores are missed (overdue at reset boundary) for statistics and gamification.

**Decision Point**: ✅ Scope confirmed with refinements (2026-02-09).

### 5.1 Concept

When a chore reaches a reset boundary while OVERDUE, it can be "missed" — the kid failed to complete it in the period. This is controlled by a new overdue handling option that records accountability metrics while resetting the chore.

**Behavioral Options**:

- **`OVERDUE_HANDLING_BLOCKING`** - Stays OVERDUE until completed (no reset, no miss recorded)
- **`OVERDUE_HANDLING_CLEAR_AT_APPROVAL_RESET`** - Resets to PENDING without recording miss (existing behavior, unchanged)
- **`OVERDUE_HANDLING_CLEAR_AND_MARK_MISSED`** - NEW: Resets to PENDING AND records missed stats

**No Migration Required**: New option is additive. Existing chores continue with their current behavior.

### 5.2 Proposed Data Model

```python
# New overdue handling constant in const.py
OVERDUE_HANDLING_CLEAR_AND_MARK_MISSED: Final = "clear_and_mark_missed"
# Add to OVERDUE_HANDLING_OPTIONS list

# New kid chore data field (top-level timestamp)
DATA_KID_CHORE_DATA_LAST_MISSED: Final = "last_missed"

# New period bucket fields (matches existing pattern: approved, claimed, overdue, etc.)
DATA_KID_CHORE_DATA_PERIOD_MISSED: Final = "missed"
DATA_KID_CHORE_DATA_PERIOD_MISSED_STREAK_TALLY: Final = "missed_streak_tally"
DATA_KID_CHORE_DATA_PERIOD_MISSED_LONGEST_STREAK: Final = "missed_longest_streak"

# New signal
SIGNAL_SUFFIX_CHORE_MISSED: Final = "chore_missed"

# New service field for manual skip
SERVICE_FIELD_MARK_AS_MISSED: Final = "mark_as_missed"

# New translation keys
TRANS_KEY_NOTIF_TITLE_CHORE_MISSED: Final = "notif_title_chore_missed"
TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED: Final = "notif_message_chore_missed"
TRANS_KEY_SERVICE_MARK_AS_MISSED: Final = "service_mark_as_missed"
TRANS_KEY_SERVICE_MARK_AS_MISSED_DESC: Final = "service_mark_as_missed_desc"
```

**Data Structure Pattern (matches existing chore stats):**

```json
{
  "kid_chore_data": {
    "chore_uuid": {
      "last_missed": "2026-02-09T10:30:00+00:00", // Top-level timestamp (like last_approved)
      "periods": {
        "daily": {
          "2026-02-09": {
            "missed": 1, // Count for this day (like approved, claimed)
            "missed_streak_tally": 3 // Current consecutive misses (like streak_tally)
          }
        },
        "weekly": {
          "2026-W06": {
            "missed": 2 // Week total
          }
        },
        "monthly": {
          "2026-02": {
            "missed": 5 // Month total
          }
        },
        "yearly": {
          "2026": {
            "missed": 5 // Year total
          }
        },
        "all_time": {
          "all_time": {
            "missed": 12, // Lifetime total (never decreases)
            "missed_longest_streak": 5 // High-water mark (NO missed_streak_tally here)
          }
        }
      }
    }
  }
}
```

**Key Points:**

- **last_missed**: Top-level timestamp (like `last_approved`, `last_claimed`)
- **missed**: Period bucket counter (like `approved`, `claimed`, `overdue`)
- **missed_streak_tally**: Daily-only field tracking current consecutive misses (like `streak_tally` for completions)
- **missed_longest_streak**: All-time high-water mark only (like `longest_streak`)
- **Pattern**: Exactly matches how existing chore statistics are structured

### 5.3 Logic Flow

**Automated Recording (Reset Boundary)**:

```
Reset boundary reached for OVERDUE chore:
  IF overdue_handling == OVERDUE_HANDLING_CLEAR_AND_MARK_MISSED:
    1. Call _record_chore_missed(kid_id, chore_id)
  2. Reset to PENDING (existing behavior)
  3. Reschedule due date (existing behavior)
```

**Manual Recording (Skip Service)**:

```
kidschores.skip_chore_due_date service called:
  IF mark_as_missed == True:
    1. Call _record_chore_missed(kid_id, chore_id)
  2. Reset/reschedule chore (existing behavior)
```

**Helper Method** (new in `managers/chore_manager.py`):

```python
def _record_chore_missed(self, kid_id: str, chore_id: str) -> None:
    """Record that a chore was missed (delegate to StatisticsManager).

    Updates:
    - last_missed (top-level timestamp)
    - Emits SIGNAL_SUFFIX_CHORE_MISSED for StatisticsManager to record period stats

    StatisticsManager handles:
    - missed (period bucket counter)
    - missed_streak_tally (daily consecutive misses)
    - missed_longest_streak (all-time high-water mark)
    """
    kid_chore_data = self._get_kid_chore_data(kid_id, chore_id)

    # Update top-level timestamp (like last_approved, last_claimed)
    kid_chore_data[const.DATA_KID_CHORE_DATA_LAST_MISSED] = dt_now_iso()

    # Emit signal for StatisticsManager to handle period buckets
    # (matches pattern: CHORE_APPROVED, CHORE_CLAIMED, CHORE_OVERDUE)
    self.emit(
        const.SIGNAL_SUFFIX_CHORE_MISSED,
        kid_id=kid_id,
        chore_id=chore_id,
    )
```

**StatisticsManager Handler** (new in `managers/statistics_manager.py`):

```python
@callback
def _on_chore_missed(self, payload: dict[str, Any]) -> None:
    """Handle CHORE_MISSED event - record missed to period buckets.

    Records:
    - missed count to daily/weekly/monthly/yearly/all_time buckets
    - missed_streak_tally to daily bucket (current consecutive misses)
    - missed_longest_streak to all_time bucket (high-water mark)

    Follows same pattern as _on_chore_overdue, _on_chore_approved, etc.
    """
    kid_id = payload.get("kid_id", "")
    chore_id = payload.get("chore_id", "")

    # Prepare increments for period buckets
    increments = {const.DATA_KID_CHORE_DATA_PERIOD_MISSED: 1}

    # Record transaction to period buckets (daily/weekly/monthly/yearly/all_time)
    # Engine will handle streak_tally and longest_streak calculations
    if self._record_chore_transaction(kid_id, chore_id, increments):
        # Transactional Flush: cache was refreshed inside _record_chore_transaction
        self._coordinator.async_set_updated_data(self._coordinator._data)
        const.LOGGER.debug(
            "StatisticsManager._on_chore_missed: kid=%s, chore=%s",
            kid_id,
            chore_id,
        )
```

**Location for Automated Call**: Inside `_process_approval_reset_entries()`, when resetting a chore that is currently OVERDUE:

```python
# Before transitioning to PENDING:
if kid_state == const.CHORE_STATE_OVERDUE:
    overdue_handling = chore_data.get(
        const.DATA_CHORE_OVERDUE_HANDLING,
        const.OVERDUE_HANDLING_BLOCKING,
    )
    if overdue_handling == const.OVERDUE_HANDLING_CLEAR_AND_MARK_MISSED:
        self._record_chore_missed(kid_id, chore_id)
```

**Streak Tally Reset on Approval** (handled automatically):

```python
# On successful approval, the missed streak naturally breaks
# StatisticsManager already handles this via _on_chore_approved signal
# which records an approval to the period buckets
# The streak_tally calculation in StatisticsEngine will see the approval
# and reset missed_streak_tally to 0 automatically
# No explicit code needed in _approve_chore_locked() - pattern matches existing streak behavior
```

**Use Cases for Missed Streak Tally**:

- **Tally = 1**: "Reminder notification"
- **Tally = 3**: "Needs Attention alert to Parent"
- **Tally = 5**: "Deduct allowance/points"

This distinguishes between "forgot once" vs "stopped doing this chore entirely."

**Access Pattern for Dashboard/Automations**:

```python
# From sensor attributes or periods data:
daily_bucket = kid_chore_data["periods"]["daily"][today_key]
current_missed_streak = daily_bucket.get("missed_streak_tally", 0)

all_time_bucket = kid_chore_data["periods"]["all_time"]["all_time"]
total_missed = all_time_bucket.get("missed", 0)
longest_missed_streak = all_time_bucket.get("missed_longest_streak", 0)

# Last missed timestamp (top-level):
last_missed_iso = kid_chore_data.get("last_missed")
```

### 5.4 Affected Files

| File                             | Change                                                                                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `const.py`                       | Add OVERDUE_HANDLING_CLEAR_AND_MARK_MISSED, DATA_KID_CHORE_DATA_LAST_MISSED, DATA_KID_CHORE_DATA_PERIOD_MISSED\*, SIGNAL, SERVICE_FIELD, TRANS_KEY constants |
| `managers/chore_manager.py`      | Add `_record_chore_missed()` helper method                                                                                                                   |
| `managers/chore_manager.py`      | Call `_record_chore_missed()` in `_process_approval_reset_entries()`                                                                                         |
| `managers/statistics_manager.py` | Add `_on_chore_missed()` signal handler                                                                                                                      |
| `managers/statistics_manager.py` | Subscribe to SIGNAL_SUFFIX_CHORE_MISSED in `async_initialize()`                                                                                              |
| `engines/statistics_engine.py`   | Ensure streak_tally/longest_streak logic handles missed metric (should already work)                                                                         |
| `services.py`                    | Add `mark_as_missed` parameter to `skip_chore_due_date` service                                                                                              |
| `services.yaml`                  | Update `skip_chore_due_date` schema with new boolean field                                                                                                   |
| `sensor.py`                      | Expose missed stats from period buckets as sensor attributes                                                                                                 |
| `managers/ui_manager.py`         | Include missed stats in dashboard helper sensor (from periods.all_time)                                                                                      |
| `helpers/flow_helpers.py`        | Add CLEAR_AND_MARK_MISSED to overdue handling selector                                                                                                       |
| `translations/en.json`           | Add notification text, service field text, overdue handling option label                                                                                     |

### 5.5 Test Scenarios — Phase 5

| #     | Test Name                                              | Validates                                                                 |
| ----- | ------------------------------------------------------ | ------------------------------------------------------------------------- |
| T5.1  | `test_missed_recorded_with_clear_and_mark_missed`      | Missed count incremented in period buckets when overdue_handling triggers |
| T5.2  | `test_no_missed_recorded_with_clear_at_approval_reset` | No missed stats when using standard clear (backward compat)               |
| T5.3  | `test_missed_streak_tally_increments`                  | missed_streak_tally increments in daily bucket on consecutive misses      |
| T5.4  | `test_missed_streak_tally_resets_on_approval`          | missed_streak_tally resets to 0 when chore completed                      |
| T5.5  | `test_missed_longest_streak_high_water_mark`           | missed_longest_streak tracks highest consecutive miss count in all_time   |
| T5.6  | `test_manual_skip_with_mark_as_missed_true`            | Service parameter records miss to period buckets manually                 |
| T5.7  | `test_manual_skip_with_mark_as_missed_false`           | Service parameter skips without recording miss                            |
| T5.8  | `test_missed_signal_emitted`                           | CHORE_MISSED signal emitted with correct payload                          |
| T5.9  | `test_missed_data_in_sensor_attributes`                | Sensor exposes missed stats from period buckets                           |
| T5.10 | `test_missed_stats_in_multiple_period_buckets`         | Missed recorded to daily/weekly/monthly/yearly/all_time buckets           |
| T5.11 | `test_tiered_intervention_missed_streak_tally`         | Dashboard/automation can check daily missed_streak_tally for alerts       |
| T5.12 | `test_last_missed_timestamp_updated`                   | Top-level last_missed timestamp updated on miss                           |

---

## Phase 6 – Due Window Lock

**Goal**: Restrict claims until a configurable window before the due date opens.

**Decision Point**: ⚠️ Confirm scope before building.

### 6.1 Concept

Some chores should only be claimable within a window before their due date (e.g., "Take out trash" only claimable starting 2 hours before due). This prevents kids from claiming chores too early.

### 6.2 Proposed Data Model

```python
# New chore config field
DATA_CHORE_CLAIM_WINDOW_HOURS: Final = "claim_window_hours"
DEFAULT_CLAIM_WINDOW_HOURS: Final = 0  # 0 = no restriction (always claimable)

# New error translation
TRANS_KEY_ERROR_CHORE_NOT_IN_CLAIM_WINDOW: Final = "error_chore_not_in_claim_window"
```

### 6.3 Logic Flow — Enhanced `can_claim_chore()`

```python
# In Engine's can_claim_chore(), add new check:

# Check N: Due window lock
claim_window_hours = chore_data.get(
    const.DATA_CHORE_CLAIM_WINDOW_HOURS,
    const.DEFAULT_CLAIM_WINDOW_HOURS,
)
if claim_window_hours > 0 and due_date:
    # due_date must be passed as parameter or computed
    window_start = due_date - timedelta(hours=claim_window_hours)
    if now_utc < window_start:
        return (False, const.TRANS_KEY_ERROR_CHORE_NOT_IN_CLAIM_WINDOW)
```

**Challenge**: Engine methods are currently pure (no `now_utc` parameter). Options:

1. Pass `now_utc` as parameter to `can_claim_chore()` — cleanest
2. Move check to Manager wrapper only — pragmatic

**Recommendation**: Option 1 — add `now_utc: datetime | None = None` parameter. When None, skip the check (backward compatible).

### 6.4 Affected Files

| File                        | Change                                                    |
| --------------------------- | --------------------------------------------------------- |
| `const.py`                  | Add DATA*CHORE_CLAIM_WINDOW_HOURS, DEFAULT*_, TRANS*KEY*_ |
| `engines/chore_engine.py`   | Add window check in `can_claim_chore()`                   |
| `managers/chore_manager.py` | Pass `now_utc` and `due_date` to engine                   |
| `data_builders.py`          | Add `claim_window_hours` to `build_chore()`               |
| `helpers/flow_helpers.py`   | Add window hours field to chore creation/edit flow        |
| `translations/en.json`      | Add error message and flow label                          |

### 6.5 Test Scenarios — Phase 6

| #    | Test Name                                      | Validates                       |
| ---- | ---------------------------------------------- | ------------------------------- |
| T6.1 | `test_claim_blocked_before_window`             | Can't claim before window opens |
| T6.2 | `test_claim_allowed_in_window`                 | Can claim within window         |
| T6.3 | `test_claim_window_zero_no_restriction`        | Default (0) = always claimable  |
| T6.4 | `test_claim_window_no_due_date_no_restriction` | No due date = always claimable  |

---

## Phase 7 – Rotation Chores

**Goal**: Add rotation assignment mode for shared chores where kids take turns.

**Decision Point**: ⚠️ Confirm scope before building. This is the largest feature phase.

### 7.1 Concept

A new completion criteria: `COMPLETION_CRITERIA_ROTATION`. Kids take turns completing the chore in a round-robin fashion. Only the current turn's kid can claim.

### 7.2 Proposed Data Model

```python
# New completion criteria
COMPLETION_CRITERIA_ROTATION: Final = "rotation"

# New chore config fields
DATA_CHORE_ROTATION_INDEX: Final = "rotation_index"      # Current turn index
DATA_CHORE_ROTATION_ORDER: Final = "rotation_order"       # Ordered kid ID list
DATA_CHORE_ROTATION_ADVANCE: Final = "rotation_advance"   # When to advance
# "on_approval" = advance after approved
# "on_reset" = advance at reset boundary

# New translation
TRANS_KEY_ERROR_CHORE_NOT_YOUR_TURN: Final = "error_chore_not_your_turn"
```

### 7.3 Logic Flow

```
ROTATION chore lifecycle:
  1. rotation_order = [kid_A, kid_B, kid_C]
  2. rotation_index = 0 → kid_A's turn
  3. Only kid_A can claim (can_claim blocks others with "not_your_turn")
  4. kid_A claims → kid_A CLAIMED, others PENDING
  5. kid_A approved → advance:
     - If rotation_advance="on_approval": index → 1 (kid_B next)
     - If rotation_advance="on_reset": advance happens at reset boundary
  6. At reset: kid_B's turn
```

### 7.4 Engine Changes

```python
# In can_claim_chore():
if criteria == const.COMPLETION_CRITERIA_ROTATION:
    rotation_order = chore_data.get(const.DATA_CHORE_ROTATION_ORDER, [])
    rotation_index = chore_data.get(const.DATA_CHORE_ROTATION_INDEX, 0)
    if rotation_order:
        current_turn_kid = rotation_order[rotation_index % len(rotation_order)]
        kid_id = kid_chore_data.get("kid_id")  # Need kid_id in context
        if kid_id != current_turn_kid:
            return (False, const.TRANS_KEY_ERROR_CHORE_NOT_YOUR_TURN)

# _plan_claim_effects: ROTATION same as INDEPENDENT (only actor)
# _plan_approve_effects: ROTATION same as INDEPENDENT
# _plan_disapprove_effects: ROTATION same as INDEPENDENT
# _plan_undo_effects: ROTATION same as INDEPENDENT
```

**Note**: Rotation only changes `can_claim()` blocking and adds index advancement logic. All effect planning is identical to INDEPENDENT mode.

### 7.5 Manager Changes

```python
# In _approve_chore_locked(), after approval:
if criteria == const.COMPLETION_CRITERIA_ROTATION:
    rotation_advance = chore_data.get(
        const.DATA_CHORE_ROTATION_ADVANCE, "on_approval"
    )
    if rotation_advance == "on_approval":
        self._advance_rotation(chore_id)

# In _process_approval_reset_entries(), after reset:
if criteria == const.COMPLETION_CRITERIA_ROTATION:
    rotation_advance = chore_data.get(
        const.DATA_CHORE_ROTATION_ADVANCE, "on_approval"
    )
    if rotation_advance == "on_reset":
        self._advance_rotation(chore_id)

def _advance_rotation(self, chore_id: str) -> None:
    """Advance the rotation index to the next kid."""
    chore_data = self._coordinator.chores_data.get(chore_id, {})
    rotation_order = chore_data.get(const.DATA_CHORE_ROTATION_ORDER, [])
    if not rotation_order:
        return
    current = chore_data.get(const.DATA_CHORE_ROTATION_INDEX, 0)
    chore_data[const.DATA_CHORE_ROTATION_INDEX] = (current + 1) % len(rotation_order)
```

### 7.6 Affected Files

| File                        | Change                                                                           |
| --------------------------- | -------------------------------------------------------------------------------- |
| `const.py`                  | Add COMPLETION*CRITERIA_ROTATION, DATA_CHORE_ROTATION*_, TRANS*KEY*_             |
| `engines/chore_engine.py`   | Add rotation check in `can_claim_chore()`, update `compute_global_chore_state()` |
| `managers/chore_manager.py` | Add `_advance_rotation()`, add hooks in approve and reset                        |
| `data_builders.py`          | Add rotation fields to `build_chore()`                                           |
| `helpers/flow_helpers.py`   | Add rotation config to chore creation/edit flow                                  |
| `sensor.py`                 | Expose rotation_index, current_turn_kid as attributes                            |
| `managers/ui_manager.py`    | Include rotation info in dashboard helper                                        |
| `translations/en.json`      | Add labels and error messages                                                    |

### 7.7 Dependency on Phase 2

**Critical**: Phase 2 (COMPLETED_BY_OTHER elimination) MUST be done first. Without it, rotation would need to manage COMPLETED_BY_OTHER states for non-turn kids, which is exactly the bloat Phase 2 removes.

With Phase 2 complete: non-turn kids stay PENDING, `can_claim()` blocks them. Clean and simple.

### 7.8 Test Scenarios — Phase 7

| #    | Test Name                                   | Validates                            |
| ---- | ------------------------------------------- | ------------------------------------ |
| T7.1 | `test_rotation_only_current_turn_can_claim` | Non-turn kids blocked                |
| T7.2 | `test_rotation_advances_on_approval`        | Index increments after approve       |
| T7.3 | `test_rotation_advances_on_reset`           | Index increments at reset boundary   |
| T7.4 | `test_rotation_wraps_around`                | Index wraps to 0 after last kid      |
| T7.5 | `test_rotation_global_state`                | Global state tracks current turn kid |
| T7.6 | `test_rotation_disapprove_no_advance`       | Disapprove doesn't advance turn      |
| T7.7 | `test_rotation_with_kid_removal`            | Handles kid removed from rotation    |

---

## Schema Migration Strategy

### Migration Scope

**Phase 2** requires schema migration (COMPLETED_BY_OTHER state + list removal). Other phases add new fields but don't require migration of existing data.

### Schema Version Decision

If schema 44 is already stamped on existing installs:

- **Bump to schema 45** for Phase 2 migration
- All new fields from Phases 5-7 have defaults and don't need migration

If schema 44 is still in development:

- **Include Phase 2 migration in schema 44**

### Migration Function Template

```python
def _migrate_chore_state_hardening(data: dict[str, Any]) -> dict[str, Any]:
    """Schema N: Chore state architecture hardening.

    Changes:
    - Remove completed_by_other_chores lists from kid data
    - Convert COMPLETED_BY_OTHER states to PENDING
    - Add missed_count/missed_streak defaults (Phase 5)
    """
    kids = data.get("kids", {})

    for kid_id, kid_info in kids.items():
        # Phase 2: Remove completed_by_other_chores list
        kid_info.pop("completed_by_other_chores", None)

        # Phase 2: Convert COMPLETED_BY_OTHER states
        chore_data_map = kid_info.get("chore_data", {})
        for chore_id, kid_chore_data in chore_data_map.items():
            if kid_chore_data.get("state") == "completed_by_other":
                kid_chore_data["state"] = "pending"
                kid_chore_data.pop("claimed_by", None)
                kid_chore_data.pop("completed_by", None)

    # Stamp schema version
    meta = data.setdefault("meta", {})
    meta["schema_version"] = NEW_SCHEMA_VERSION

    return data
```

---

## Cross-Phase Test Matrix

### Regression Test Coverage

| Phase     | New Tests | Modified Tests | Total    |
| --------- | --------- | -------------- | -------- |
| Phase 1   | 11        | ~20-30         | ~35      |
| Phase 2   | 11        | ~15-20         | ~28      |
| Phase 3   | 4         | ~2-3           | ~6       |
| Phase 4   | 3         | 0              | ~3       |
| Phase 5   | 4         | ~5             | ~9       |
| Phase 6   | 4         | ~3             | ~7       |
| Phase 7   | 7         | ~5             | ~12      |
| **Total** | **44**    | **~55**        | **~100** |

### Test Execution Strategy

After each phase:

```bash
# Phase-specific tests
pytest tests/test_<specific>.py -v

# Full regression
pytest tests/ -v --tb=line

# Quality gates
./utils/quick_lint.sh --fix
mypy custom_components/kidschores/
```

### Cross-Phase Integration Tests

After ALL phases:
| # | Test Name | Validates |
|---|-----------|-----------|
| X1 | `test_shared_first_full_lifecycle_post_hardening` | Claim→Approve→Reset with no CBO state |
| X2 | `test_rotation_with_missed_tracking` | Phase 5+7 interaction |
| X3 | `test_manual_reset_with_claim_window` | Phase 3+6 interaction |
| X4 | `test_full_pipeline_all_driver_combos` | All 5 drivers with guard rails |

---

## Appendix: Constants Quick Reference

### Existing Constants (Keep)

```python
CHORE_STATE_COMPLETED_BY_OTHER = "completed_by_other"  # Keep for display
TRANS_KEY_ERROR_CHORE_COMPLETED_BY_OTHER                # Keep for can_claim error
```

### Constants to Add

```python
# Phase 3
APPROVAL_RESET_MANUAL: Final = "manual"

# Phase 5
DATA_KID_CHORE_DATA_MISSED_COUNT: Final = "missed_count"
DATA_KID_CHORE_DATA_LAST_MISSED: Final = "last_missed"
DATA_KID_CHORE_DATA_MISSED_STREAK: Final = "missed_streak"
SIGNAL_SUFFIX_CHORE_MISSED: Final = "chore_missed"
TRANS_KEY_NOTIF_TITLE_CHORE_MISSED: Final = "notif_title_chore_missed"
TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED: Final = "notif_message_chore_missed"

# Phase 6
DATA_CHORE_CLAIM_WINDOW_HOURS: Final = "claim_window_hours"
DEFAULT_CLAIM_WINDOW_HOURS: Final = 0
TRANS_KEY_ERROR_CHORE_NOT_IN_CLAIM_WINDOW: Final = "error_chore_not_in_claim_window"

# Phase 7
COMPLETION_CRITERIA_ROTATION: Final = "rotation"
DATA_CHORE_ROTATION_INDEX: Final = "rotation_index"
DATA_CHORE_ROTATION_ORDER: Final = "rotation_order"
DATA_CHORE_ROTATION_ADVANCE: Final = "rotation_advance"
TRANS_KEY_ERROR_CHORE_NOT_YOUR_TURN: Final = "error_chore_not_your_turn"
```

### Constants to Deprecate (Phase 2)

```python
DATA_KID_COMPLETED_BY_OTHER_CHORES  # No longer written; migration removes from storage
```

---

## Appendix: File Change Summary

| File                        | Phase 1                                   | Phase 2                                             | Phase 3      | Phase 4       | Phase 5          | Phase 6        | Phase 7                   |
| --------------------------- | ----------------------------------------- | --------------------------------------------------- | ------------ | ------------- | ---------------- | -------------- | ------------------------- |
| `const.py`                  | —                                         | Keep CBO const                                      | Add MANUAL   | —             | Add MISSED\_\*   | Add WINDOW\_\* | Add ROTATION\_\*          |
| `engines/chore_engine.py`   | —                                         | VALID*TRANS, can_claim, plan*\* × 4, compute_global | Verify only  | —             | —                | can_claim      | can_claim, compute_global |
| `managers/chore_manager.py` | Handlers × 2, process × 2, claim, approve | can_claim, status_context, transition               | —            | Guards × 2    | approve, reset   | can_claim      | approve, reset, advance   |
| `data_builders.py`          | —                                         | —                                                   | —            | —             | —                | build_chore    | build_chore               |
| `helpers/flow_helpers.py`   | —                                         | —                                                   | Options list | —             | —                | Flow field     | Flow field                |
| `migration_pre_v50.py`      | —                                         | Migration fn                                        | —            | —             | —                | —              | —                         |
| `sensor.py`                 | —                                         | Attr update                                         | —            | —             | Expose missed    | —              | Expose rotation           |
| `managers/ui_manager.py`    | —                                         | —                                                   | —            | —             | Dashboard helper | —              | Dashboard helper          |
| `translations/en.json`      | —                                         | —                                                   | Manual label | —             | Notif text       | Error msg      | Error msg + labels        |
| `docs/ARCHITECTURE.md`      | —                                         | —                                                   | —            | Driver matrix | —                | —              | —                         |
| Dashboard YAML              | —                                         | No change needed                                    | —            | —             | —                | —              | —                         |

---

> **Builder Note**: Execute phases sequentially. Each phase's tests must pass before proceeding. Run full quality gates (`quick_lint.sh`, `mypy`, `pytest`) after each phase. Phase 2 is the riskiest (most files, schema migration); Phase 1 is the highest priority (fixes active bugs). Phase 3 is the quickest win.
