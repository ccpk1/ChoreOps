# Implementation Plan: User Chore Pause — Phases 1–3

**Created**: 2026-06-08 | **Based on**: `USER_CHORE_PAUSE_PLAN_IN-PROCESS.md` v1 (746 lines, 7 phases, 17 edge cases, 14+ decisions)

---

## Rules of engagement

| Rule | Detail |
|------|--------|
| **Source of truth** | This document is the authoritative implementation spec for Phases 1–3. The main plan (`USER_CHORE_PAUSE_PLAN_IN-PROCESS.md`) is the design authority. |
| **Deviation requires approval** | Any change to this implementation plan, or any deviation discovered during coding, must be flagged and approved before proceeding. Update this document AND the main plan. |
| **Progress tracking** | After completing each step, check the box and note any issues. After completing each phase, run the phase validation checklist and record results before moving to the next phase. |
| **Main plan sync** | After each phase completes, update the main plan's Summary table percentage and add a dated note under "Summary of recent work." |
| **Blueprint reference** | Code snippets in this plan follow existing patterns from the codebase. Where a pattern is referenced, the source file and line range are noted. |
| **Validation gates** | Every phase ends with a checklist. All items must pass before the phase is complete. |

---

## Phase 1 — Storage & Constants

**Goal**: Add user-level pause fields to the data model. Zero behavioral changes — just wiring constants, type definitions, validation, and the options flow UI.

**Estimated code surface**: ~18 lines across 5 files + translation entries.

### Step 1.1: Add storage and state constants

**File**: `custom_components/choreops/const.py`
**Blueprint**: Existing `DATA_USER_*` constants at ~line 1235, existing `CHORE_STATE_*` derived states at ~line 1859, existing `CHORE_CLAIM_MODE_*` at ~line 1926.

```python
# === Insert near line 1235 (alongside existing DATA_USER_* fields) ===
DATA_USER_CHORES_PAUSED: Final = "chores_paused"
DATA_USER_CHORES_PAUSED_UNTIL: Final = "chores_paused_until"

# === Insert near line 1859 (in "Derived UI-only states" block, after CHORE_STATE_NOT_MY_TURN) ===
CHORE_STATE_PAUSED: Final = "paused"

# === Insert near line 1926 (after CHORE_CLAIM_MODE_BLOCKED_MISSED_LOCKED) ===
CHORE_CLAIM_MODE_BLOCKED_PAUSED: Final = "blocked_paused"

# === Scope 2 & 3 architectural hooks (DEFERRED — add near the above for future use) ===
DATA_CHORE_PAUSED: Final = "paused"          # Scope 2: bool on chore record
DATA_CHORE_PAUSED_FOR: Final = "paused_for"   # Scope 3: list[user_id] on chore record
```

Also add `CHORE_STATE_PAUSED` to the `CHORE_UI_ASSIGNEE_STATES` frozenset (~line 1889) and `CHORE_CLAIM_MODE_BLOCKED_PAUSED` to the `CHORE_CLAIM_MODES` frozenset (~line 1928).

### Step 1.2: Add CFOF constants

**File**: `custom_components/choreops/const.py`
**Blueprint**: Existing `CFOF_USERS_INPUT_*` constants.

```python
# === Insert near existing CFOF_USERS_INPUT_* constants ===
CFOF_USERS_INPUT_CHORES_PAUSED: Final = "chores_paused"
CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: Final = "chores_paused_until"
```

### Step 1.3: Add translation key constants

**File**: `custom_components/choreops/const.py`
**Blueprint**: Existing `TRANS_KEY_*` constants.

```python
# === Insert near existing TRANS_KEY_ERROR_CHORE_* constants ===
TRANS_KEY_ERROR_CHORE_PAUSED: Final = "chore_paused"
```

### Step 1.4: Update UserData TypedDict

**File**: `custom_components/choreops/type_defs.py`, line ~662
**Blueprint**: Existing `NotRequired` fields on `UserData` (e.g., `can_be_assigned`).

```python
class UserData(TypedDict):
    # ... existing fields ...
    can_be_assigned: NotRequired[bool]
    # === NEW: insert after can_be_assigned ===
    chores_paused: NotRequired[bool]
    chores_paused_until: NotRequired[str | None]  # UTC ISO datetime or None
```

### Step 1.5: Update data builders — defaults and validation

**File**: `custom_components/choreops/data_builders.py`
**Blueprint**: `build_user_profile()` at line ~1104, `build_user_assignment_profile()` at line ~769.

**Defaults** — in both `build_user_profile()` and `build_user_assignment_profile()`, add to the returned dict:

```python
const.DATA_USER_CHORES_PAUSED: False,
const.DATA_USER_CHORES_PAUSED_UNTIL: None,
```

**Validation** — in the validation section of `data_builders.py`, find or add user data validation. Ensure:
- `chores_paused` is a boolean (reject non-boolean values)
- If `chores_paused` is `False`, `chores_paused_until` should be cleared to `None`
- If `chores_paused_until` is provided and `chores_paused` is `True`, validate it's a valid ISO datetime and in the future (or today)

### Step 1.6: Update options flow — edit user screen

**File**: `custom_components/choreops/flow_helpers.py` (schema builder)
**Blueprint**: Existing `build_user_schema()` or equivalent function that builds the voluptuous schema for the edit user step.

Add to the schema:

```python
vol.Optional(
    const.CFOF_USERS_INPUT_CHORES_PAUSED,
    default=current_user.get(const.DATA_USER_CHORES_PAUSED, False),
): cv.boolean,
vol.Optional(
    const.CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL,
    default=current_user.get(const.DATA_USER_CHORES_PAUSED_UNTIL),
    description={"suggested_value": "Optional. If set, chores automatically resume after this date."},
): selector.DateTimeSelector(),
```

**File**: `custom_components/choreops/options_flow.py` (~line 836, `async_step_edit_user`)
**Blueprint**: Existing field handling in the edit user step — how other fields are read from `user_input` and written to storage.

In the step handler that processes user input from the edit user form:
- Read `chores_paused` and `chores_paused_until` from `user_input`
- Pass them through validation (Step 1.5)
- Pass them to the data builder which applies defaults and validation
- Persist via `coordinator._persist_and_update()`
- Emit `SIGNAL_SUFFIX_USER_UPDATED`

### Step 1.7: Add translations

**File**: `custom_components/choreops/translations/en.json`
**Blueprint**: Existing translation structure under `entity`, `config`, `exceptions`.

```json
{
  "entity": {
    "sensor": {
      "chore_status_sensor": {
        "state": {
          "paused": "Paused"
        },
        "state_attributes": {
          "claim_mode": {
            "state": {
              "blocked_paused": "Chores are paused for this user"
            }
          }
        }
      }
    }
  },
  "config": {
    "step": {
      "edit_user": {
        "data": {
          "chores_paused": "Pause chores",
          "chores_paused_until": "Paused until (optional)"
        },
        "description": {
          "chores_paused_until": "If set, chores automatically resume after this date"
        }
      }
    }
  },
  "exceptions": {
    "chore_paused": "Chores are currently paused for {user_name}."
  }
}
```

### Phase 1 — Validation Checklist

```markdown
[ ] const.py: All 6 new constants present (DATA_USER_*, CHORE_STATE_*, CHORE_CLAIM_MODE_*, DATA_CHORE_*, CFOF_*, TRANS_KEY_*)
[ ] const.py: CHORE_UI_ASSIGNEE_STATES frozenset includes "paused"
[ ] const.py: CHORE_CLAIM_MODES frozenset includes "blocked_paused"
[ ] type_defs.py: UserData TypedDict has chores_paused and chores_paused_until fields
[ ] data_builders.py: build_user_profile() includes default chores_paused: False
[ ] data_builders.py: build_user_assignment_profile() includes default chores_paused: False
[ ] data_builders.py: Validation rejects non-boolean chores_paused
[ ] data_builders.py: Validation clears chores_paused_until when chores_paused is False
[ ] flow_helpers.py: Edit user schema includes both pause fields
[ ] options_flow.py: Edit user step reads and persists both pause fields
[ ] translations/en.json: All 4 translation keys present (state, claim_mode, form fields, exception)
[ ] ./utils/quick_lint.sh --fix passes with zero errors
[ ] mypy custom_components/choreops/ passes with zero errors
[ ] No behavioral changes — existing tests still pass (python -m pytest tests/ -x --tb=short)
```

---

## Phase 2 — Unified P0 Guard (Core Behavioral Change)

**Goal**: Implement `_is_chore_paused_for_assignee()` helper and insert guard clauses at the P0 display layer, all signal-emission points, due-today calculations, rotation, midnight reset, and auto-re-enable.

**Estimated code surface**: ~50 lines across `chore_manager.py` and `statistics_manager.py`.

### Step 2.1: Add `_is_chore_paused_for_assignee()` helper

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: ~line 3980, immediately before `get_chore_status_context()`
**Blueprint**: Existing private helper methods in `ChoreManager` (e.g., `_get_assignee_chore_data`).

```python
def _is_chore_paused_for_assignee(self, assignee_id: str, chore_id: str) -> bool:
    """Check all pause scopes. Returns True if chore should show as paused.

    Checks three sources (composed via OR):
      1. User-level: DATA_USER_CHORES_PAUSED on user record (MVP)
      2. Chore-level: DATA_CHORE_PAUSED on chore record (future)
      3. Chore×User: DATA_CHORE_PAUSED_FOR list on chore record (future)

    MVP implements scope 1 only; scopes 2 & 3 are architectural hooks
    that return False until their storage fields exist.
    """
    chore_data = self._coordinator._data.get(const.DATA_CHORES, {}).get(chore_id, {})
    user_data = self._coordinator._data.get(const.DATA_USERS, {}).get(assignee_id, {})

    # Scope 1: User-level — all chores paused for this user (MVP)
    if user_data.get(const.DATA_USER_CHORES_PAUSED):
        return True

    # Scope 2: Chore-level — this chore paused for all users (future)
    if chore_data.get(const.DATA_CHORE_PAUSED):
        return True

    # Scope 3: Chore×User — this chore paused for this specific user (future)
    if assignee_id in chore_data.get(const.DATA_CHORE_PAUSED_FOR, []):
        return True

    return False
```

### Step 2.2: P0 guard in `get_chore_status_context()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~3988, as the FIRST check in `get_chore_status_context()`, before `_get_assignee_chore_data()`
**Blueprint**: The existing return dict structure in this function (keys documented at line ~3991-4012).

```python
def get_chore_status_context(
    self, assignee_id: str, chore_id: str
) -> dict[str, Any]:
    """Return all derived chore states for a assignee+chore in one call."""

    # P0: Check if chore processing is paused for this assignee
    if self._is_chore_paused_for_assignee(assignee_id, chore_id):
        return {
            # All 15 CHORE_CTX_* keys (const.py:1942-1956) must be set
            const.CHORE_CTX_STATE: const.CHORE_STATE_PAUSED,
            const.CHORE_CTX_STORED_STATE: None,
            const.CHORE_CTX_IS_OVERDUE: False,
            const.CHORE_CTX_IS_DUE: False,
            const.CHORE_CTX_HAS_PENDING_CLAIM: False,
            const.CHORE_CTX_IS_APPROVED_IN_PERIOD: False,
            const.CHORE_CTX_IS_COMPLETED_BY_OTHER: False,
            const.CHORE_CTX_CAN_CLAIM: False,
            const.CHORE_CTX_CAN_CLAIM_ERROR: None,
            const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_BLOCKED_PAUSED,
            const.CHORE_CTX_CAN_APPROVE: False,
            const.CHORE_CTX_CAN_APPROVE_ERROR: None,
            const.CHORE_CTX_DUE_DATE: None,
            const.CHORE_CTX_AVAILABLE_AT: None,
            const.CHORE_CTX_LAST_COMPLETED: None,
        }

    # ... existing code continues below (single data fetch, FSM resolution) ...
```

### Step 2.3: Guard in `_process_overdue()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~2025, inside the per-entry loop in `_process_overdue()`, after the idempotency check but before any state transition
**Blueprint**: Existing `continue` guards in the same loop.

```python
async def _process_overdue(self, overdue_entries, now_utc, *, persist=True):
    # ... existing loop ...
    for entry in overdue_entries:
        assignee_id = entry[const.CHORE_SCAN_ENTRY_USER_ID]
        chore_id = entry[const.CHORE_SCAN_ENTRY_CHORE_ID]

        # ... existing idempotency guard ...

        # NEW: Skip paused users/chores — no overdue processing
        if self._is_chore_paused_for_assignee(assignee_id, chore_id):
            continue

        # ... existing state transition logic ...
```

### Step 2.4: Guard in `_record_chore_missed()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~5634, at function entry
**Blueprint**: Existing early-return guards.

```python
def _record_chore_missed(self, assignee_id, chore_id, ...):
    """Record a chore as missed."""

    # NEW: Skip paused users/chores — no missed recording
    if self._is_chore_paused_for_assignee(assignee_id, chore_id):
        return

    # ... existing logic ...
```

### Step 2.5: Guard in `_advance_rotation()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~4960. After determining candidate `new_assignee_id` (for any rotation type), before signal payload construction
**Blueprint**: Existing rotation calculation logic at lines ~4943-5037.

```python
def _advance_rotation(
    self, chore_id: str, completing_assignee_id: str, method: str = "auto"
) -> dict[str, Any] | None:
    # ... existing early-exit and setup ...

    # Step A: Determine candidate (criteria-specific)
    completion_criteria = chore_data.get(const.DATA_CHORE_COMPLETION_CRITERIA)
    assigned = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])

    if completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
        new_assignee_id = assigned[0] if assigned else None
    elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SIMPLE:
        new_assignee_id = self._calculate_next_turn_simple(...)
    else:  # smart (and any future rotation types)
        new_assignee_id = self._calculate_next_turn_smart(...)

    # Step B: Skip paused assignees (shared, criteria-agnostic)
    if new_assignee_id is not None and assigned:
        idx = assigned.index(new_assignee_id)
        for _ in range(len(assigned)):
            if not self._is_chore_paused_for_assignee(new_assignee_id, chore_id):
                break
            idx = (idx + 1) % len(assigned)
            new_assignee_id = assigned[idx]
        else:
            # ALL assignees paused — freeze at current position
            new_assignee_id = None

    # ... existing signal payload construction continues below ...
```

**Coordination note**: If primary-backup chore type is implemented first, refactor so Step B runs AFTER primary-backup's `assigned[0]` candidate. If pause is implemented first, primary-backup later adds its criteria branch before Step B. See `CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md` CRIT-1.

### Step 2.6: Guard in `chore_counts_toward_due_today_summary()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~4193 (display_state exclusion) and ~4202 (claim_mode exclusion)
**Blueprint**: Existing exclusion tuples in this function.

```python
def chore_counts_toward_due_today_summary(self, assignee_id, chore_id, ...):
    # ... existing setup ...

    # === Add CHORE_STATE_PAUSED to this exclusion tuple (~line 4193): ===
    if display_state in (
        const.CHORE_STATE_CLAIMED,
        const.CHORE_STATE_COMPLETED,
        const.CHORE_STATE_COMPLETED_BY_OTHER,
        const.CHORE_STATE_NOT_MY_TURN,
        const.CHORE_STATE_OVERDUE,
        const.CHORE_STATE_MISSED,
        const.CHORE_STATE_PAUSED,  # NEW
    ):
        return False

    # === Add CHORE_CLAIM_MODE_BLOCKED_PAUSED to this exclusion tuple (~line 4202): ===
    if claim_mode in (
        const.CHORE_CLAIM_MODE_BLOCKED_COMPLETED_BY_OTHER,
        const.CHORE_CLAIM_MODE_BLOCKED_ALREADY_APPROVED,
        const.CHORE_CLAIM_MODE_BLOCKED_PENDING_CLAIM,
        const.CHORE_CLAIM_MODE_BLOCKED_NOT_MY_TURN,
        const.CHORE_CLAIM_MODE_BLOCKED_MISSED_LOCKED,
        const.CHORE_CLAIM_MODE_BLOCKED_PAUSED,  # NEW
    ):
        return False

    # ... existing due-today logic continues ...
```

### Step 2.7: Guard in `_is_chore_due_today_for_assignee()`

**File**: `custom_components/choreops/managers/statistics_manager.py`
**Location**: Line ~2354, at function entry
**Blueprint**: Existing early-return guards in statistics_manager.

```python
def _is_chore_due_today_for_assignee(
    self, chore_info: dict[str, Any], assignee_id: str, today_iso: str
) -> bool:
    """Return True if this chore is assignee-actionable today."""

    # NEW: Paused users have no actionable chores
    user_data = self.coordinator._data.get(const.DATA_USERS, {}).get(assignee_id, {})
    if user_data.get(const.DATA_USER_CHORES_PAUSED):
        return False

    # ... existing logic ...
```

**Note**: This guard uses direct data access rather than `_is_chore_paused_for_assignee()` because `statistics_manager.py` is in a different module. The direct check is equivalent for Scope 1 (the only implemented scope). When Scopes 2/3 are added, this guard should be refactored to call the shared helper or a statistics-level equivalent.

### Step 2.8: Guard in `set_rotation_turn()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~5124, after existing assignment validation
**Blueprint**: Existing `ServiceValidationError` raises in this function.

```python
async def set_rotation_turn(self, chore_id: str, assignee_id: str) -> None:
    # ... existing rotation mode validation ...
    # ... existing assignment validation ...

    # NEW: Reject setting turn to a paused user
    if self._is_chore_paused_for_assignee(assignee_id, chore_id):
        raise ServiceValidationError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_CHORE_PAUSED,
            translation_placeholders={
                "user_name": get_assignee_name_by_id(self._coordinator, assignee_id),
            },
        )

    # ... existing turn-setting logic ...
```

### Step 2.9: Guard in `_process_approval_reset_entries()`

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Two insertion points — SHARED loop at ~line 2283, INDEPENDENT loop at ~line 2343
**Blueprint**: Existing `continue` guards in the same loops.

```python
async def _process_approval_reset_entries(self, scan, now_utc, trigger, *, persist=True):
    # === SHARED loop (~line 2283): ===
    for entry in scan.get(const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED, []):
        chore_id = entry["chore_id"]
        assigned_assignees = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        for assignee_id in assigned_assignees:
            if not assignee_id:
                continue
            # NEW: Skip paused users — no midnight reset processing
            if self._is_chore_paused_for_assignee(assignee_id, chore_id):
                continue
            # ... existing reset logic ...

    # === INDEPENDENT loop (~line 2343): ===
    for entry in scan.get(const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT, []):
        chore_id = entry["chore_id"]
        for assignee_entry in assignee_entries:
            assignee_id = assignee_entry[const.CHORE_SCAN_ENTRY_USER_ID]
            # NEW: Skip paused users — no midnight reset processing
            if self._is_chore_paused_for_assignee(assignee_id, chore_id):
                continue
            # ... existing reset logic ...
```

### Step 2.10: Auto-re-enable hook at midnight

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: In `_on_midnight_rollover()` at line ~334, AFTER the existing midnight processing (`_process_approval_reset_entries` and `_process_overdue`) completes
**Blueprint**: The existing midnight handler structure — Phase A (resets), Phase B (overdue), Phase C (persist).

### Step 2.11: Advance rotation past paused turn-holders (real-time + safety net)

**Behavior**: When a user is paused, any rotation chore where they are the current turn-holder must advance the turn to the next available non-paused assignee in real time — not waiting for midnight. This prevents "black hole" scenarios where a chore becomes unclaimable because the turn-holder is paused and no steal option is enabled.

**Two mechanisms**:

**Primary (real-time)**: `_advance_rotation_past_paused_assignee()` method on ChoreManager, called when a user is paused via `set_user_chores_paused()`. This is the main mechanism and handles all cases instantly.

**Secondary (midnight safety net)**: Phase C in `_on_midnight_rollover()` catches edge cases where a user was paused through a path that didn't call the real-time method (backup restore, direct data manipulation, schema migration).

```python
def _advance_rotation_past_paused_assignee(self, assignee_id: str) -> None:
    """Advance rotation turn past a paused assignee for all rotation chores.

    Scans all rotation chores where this user is the current turn-holder
    and advances to the next available non-paused assignee. If all assignees
    are paused, the rotation freezes at the current position.
    """
    chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
    for chore_id, chore_info in chores_data.items():
        if not ChoreEngine.is_rotation_mode(chore_info):
            continue
        current_turn = chore_info.get(
            const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID
        )
        if current_turn != assignee_id:
            continue
        assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        if not assigned or assignee_id not in assigned:
            continue
        idx = assigned.index(assignee_id)
        for _ in range(len(assigned)):
            idx = (idx + 1) % len(assigned)
            candidate = assigned[idx]
            if candidate == assignee_id:
                break  # Full cycle, all paused
            if not self._is_chore_paused_for_assignee(candidate, chore_id):
                chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = candidate
                break
```

**Behavior by scenario**:

| Scenario | Before (gap) | After (fix) |
|----------|-------------|-------------|
| Turn-holder paused, backups available | Stuck until midnight (or forever if AT_DUE_DATE) | Advances immediately to next available backup |
| Turn-holder paused, ALL backups also paused | Frozen (correct) | Frozen (no change) |
| User unpaused | No advance needed — they re-enter rotation at next cycle | No change |
| Paused user is NOT turn-holder | No advance needed | No change |
| Midnight rollover | No rotation advance for paused | Safety net catches any missed rotations |

```python
async def _on_midnight_rollover(self, payload=None, *, now_utc=None, trigger=...):
    """Handle midnight rollover - perform nightly chore maintenance."""
    # ... existing Phase A and Phase B ...

    # Phase C (existing): Persist if state was modified
    if state_modified:
        self._coordinator._persist_and_update()

    # === NEW: Phase D — Auto-unpause expired pauses ===
    now_utc = now_utc or dt_util.utcnow()
    now_iso = now_utc.isoformat()
    users_data = self._coordinator._data.get(const.DATA_USERS, {})
    unpaused_count = 0

    for user_id, user_data in users_data.items():
        if not user_data.get(const.DATA_USER_CHORES_PAUSED):
            continue
        until_str = user_data.get(const.DATA_USER_CHORES_PAUSED_UNTIL)
        if until_str and until_str < now_iso:
            user_data[const.DATA_USER_CHORES_PAUSED] = False
            user_data.pop(const.DATA_USER_CHORES_PAUSED_UNTIL, None)
            unpaused_count += 1

    if unpaused_count > 0:
        self._coordinator._persist_and_update()
        const.LOGGER.info("Auto-unpaused %d user(s) at midnight", unpaused_count)

    return reset_count
```

**Timing note**: This runs AFTER Phase A and B. Auto-unpaused users will be processed normally at the NEXT midnight (24h later). This avoids the "immediate overdue" surprise at the exact moment of unpause.

### Phase 2 — Validation Checklist

```markdown
[ ] Step 2.1: _is_chore_paused_for_assignee() exists and checks all three scopes
[ ] Step 2.2: get_chore_status_context() returns paused context as first check, with ALL 15 CHORE_CTX keys
[ ] Step 2.3: _process_overdue() skips paused entries with continue
[ ] Step 2.4: _record_chore_missed() early-returns for paused
[ ] Step 2.5: _advance_rotation() skips paused in criteria-agnostic loop; all-paused freezes
[ ] Step 2.6: chore_counts_toward_due_today_summary() excludes paused in BOTH exclusion tuples
[ ] Step 2.7: _is_chore_due_today_for_assignee() returns False for paused
[ ] Step 2.8: set_rotation_turn() raises ServiceValidationError for paused target
[ ] Step 2.9: _process_approval_reset_entries() skips paused in BOTH loops (SHARED + INDEPENDENT)
[ ] Step 2.10: Midnight auto-re-enable hook clears expired pauses after Phase A/B
[ ] Step 2.10: Auto-unpause runs AFTER reset entries (unpaused users processed next midnight)
[ ] ./utils/quick_lint.sh --fix passes with zero errors
[ ] mypy custom_components/choreops/ passes with zero errors
[ ] All existing tests still pass (python -m pytest tests/ -x --tb=short)
[ ] Manual verification: pause a user in storage, confirm midnight hook auto-clears when date passes
```

---

## Phase 3 — Signal Suppression Verification

**Goal**: Confirm all signal emission points are guarded. Add the `can_claim_chore` guard. Verify downstream consumers (notification, statistics, dashboard helper, calendar) are covered. No new behavioral code — verification + one guard.

### Step 3.1: Verify `SIGNAL_SUFFIX_CHORE_OVERDUE` suppression

**Check**: `_process_overdue()` emits this signal. Step 2.3 skips paused entries before the emit.
**Verification**: Trace the emission path — `_process_overdue` → signal emit. Confirm the `continue` in Step 2.3 runs before any `self.emit(SIGNAL_SUFFIX_CHORE_OVERDUE, ...)` call.
**Result**: ✅ Already covered. No action needed.

### Step 3.2: Verify `SIGNAL_SUFFIX_CHORE_MISSED` suppression

**Check**: `_record_chore_missed()` emits this signal. Step 2.4 returns early before the emit.
**Verification**: Confirm the early return in Step 2.4 runs before any signal emit.
**Result**: ✅ Already covered. No action needed.

### Step 3.3: Verify `SIGNAL_SUFFIX_CHORE_APPROVED` / `CHORE_COMPLETED` suppression at midnight

**Check**: `_process_approval_reset_entries()` emits these via `_emit_approval_signal_plans()`. Step 2.9 skips paused entries before they reach the signal plan collection.
**Verification**: Trace from the loop guards (Step 2.9) through `_apply_boundary_auto_approvals()` → `_emit_approval_signal_plans()`. Confirm paused entries never reach `_apply_boundary_auto_approvals()`.
**Result**: ✅ Already covered. No action needed.

### Step 3.4: Add `can_claim_chore` guard

**File**: `custom_components/choreops/managers/chore_manager.py`
**Location**: Line ~674, at the top of `can_claim_chore()`
**Blueprint**: Existing early-return guards in this function.

```python
def can_claim_chore(
    self,
    assignee_id: str,
    chore_id: str,
    assignee_chore_data: dict[str, Any] | None = None,
    chore_data: dict[str, Any] | None = None,
) -> tuple[bool, str | None]:
    """Check if an assignee can claim a chore."""

    # NEW: Block claim for paused users
    if self._is_chore_paused_for_assignee(assignee_id, chore_id):
        return (False, const.TRANS_KEY_ERROR_CHORE_PAUSED)

    # ... existing logic ...
```

This prevents claim/approve/disapprove service calls from reaching `_transition_chore_state` for paused users. It is the last line of defense — even if the P0 display guard shows `paused`, this ensures the action is blocked at the service level.

### Step 3.5: Verify calendar entity

**Check**: `custom_components/choreops/calendar.py` — calendar events for paused users.
**Verification**: Confirm paused chores still appear on the calendar. This is by design (calendar is an informational surface, not an action surface). If filtering is desired, it's a follow-up.
**Result**: ✅ No action needed. Documented as edge case #6.

### Step 3.6: Verify dashboard helper

**Check**: `AssigneeDashboardHelperSensor._build_payload` — paused chores should appear in the helper payload.
**Verification**: The P0 guard returns `state=paused`. Sensors read this via `get_chore_status_context()`. The helper aggregates sensor states. Paused chores will naturally appear with state `"paused"` — no special handling needed.
**Result**: ✅ No action needed.

### Step 3.7: Verify `SIGNAL_SUFFIX_USER_UPDATED` consumer refresh

**Check**: When `choreops.pause_user_chores` emits `SIGNAL_SUFFIX_USER_UPDATED`, all sensors and helpers that depend on user data must refresh.
**Verification**: Trace the signal to entity listeners in `sensor.py` and `coordinator.py`. Confirm `async_update_listeners()` is called in the persist path (it is — `_persist_and_update()` does this).
**Result**: ✅ Covered. No action needed.

### Phase 3 — Validation Checklist

```markdown
[ ] Step 3.1: CHORE_OVERDUE signal path verified — guarded by Step 2.3
[ ] Step 3.2: CHORE_MISSED signal path verified — guarded by Step 2.4
[ ] Step 3.3: CHORE_APPROVED/COMPLETED at midnight verified — guarded by Step 2.9
[ ] Step 3.4: can_claim_chore() returns (False, "chore_paused") for paused users
[ ] Step 3.5: Calendar entity confirmed — paused chores appear (by design)
[ ] Step 3.6: Dashboard helper confirmed — paused chores appear with state "paused"
[ ] Step 3.7: SIGNAL_SUFFIX_USER_UPDATED consumer refresh confirmed
[ ] ./utils/quick_lint.sh --fix passes with zero errors
[ ] mypy custom_components/choreops/ passes with zero errors
[ ] All existing tests still pass (python -m pytest tests/ -x --tb=short)
```

---

## Progress sync with main plan

After completing each phase, update `USER_CHORE_PAUSE_PLAN_IN-PROCESS.md`:

| Phase | Main plan update |
|-------|-----------------|
| Phase 1 | Update Summary table: Phase 1 → 100%. Add dated note to "Summary of recent work." |
| Phase 2 | Update Summary table: Phase 2 → 100%. Add dated note. Verify decision record still matches implementation. |
| Phase 3 | Update Summary table: Phase 3 → 100%. Add dated note. Confirm "Risks / blockers" items are resolved. |

Any deviation discovered during implementation must be:
1. Documented in this file under a "Deviations" section at the bottom
2. Reflected in the main plan if it changes a decision or phase scope
3. Approved before proceeding to the next step

> **Implementation plan created**: 2026-06-08 | **Phases covered**: 1–3 | **Next**: Phase 4–7 implementation plan (separate document)
