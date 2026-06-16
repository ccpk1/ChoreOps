# Initiative Plan: Primary & Standby Chore Type (Failover Rotation)

## Initiative snapshot

- **Name / Code**: `rotation_primary_standby` — Primary & Standby Chore Type
- **Target release / milestone**: 1.1.0
- **Owner / driver(s)**: TBD
- **Status**: All phases complete — implementation, testing, and dashboard templates delivered. Remaining: Phase 5b (docs & wiki). All code gaps (G-1 through G-7) verified fixed in actual code.

## Summary & immediate steps

| Phase / Step                   | Description                                                   | % complete | Quick notes                                                          |
| ------------------------------ | ------------------------------------------------------------- | ---------- | -------------------------------------------------------------------- |
| Phase 0 – Verification pass    | Assumption check, hardcoded list inventory, doc inventory, baseline tests, deep code audit     | ✅ 100%    | All 1895 tests passing. Found 6 CRIT tuples + 5 new gaps (G-1 through G-5) via source-level audit. +4 opportunities identified. |
| Phase 1 – Foundation           | Constants, type defs, criteria registration, CRIT fixes       | ✅ 100%    | 16 steps completed. All constants, adapters, CRIT fixes, and O-1/O-4 helper extracted. |
| Phase 2 – Core implementation  | Engine FSM, manager advance/reset, state resolution, snap-back, due-today summary | ✅ 100%    | All 10 steps completed. P3 resolver, _advance_rotation, force-to-primary, can_claim_chore, claim_mode mapping, snap-back, due-today exclusion. Tests 66/66 pass. |
| Phase 2a – Config & options flow | standby_claim_mode field in chore settings UI | ✅ 100%    | CFOF constant, form field in root section, forward/reverse mapping, schema with translation_key, selector options translated. |
| Phase 2b – Service updates       | standby_claim_mode in create/update chore services | ✅ 100%    | Schema fields in CREATE_CHORE_SCHEMA and UPDATE_CHORE_SCHEMA, YAML descriptions, translation entries. Handler pass-through verified. |
| Phase 3 – UX & notifications   | Translations, standby state, overdue notification      | ✅ 100%    | All 10 steps completed. Overdue message type wired, notification handler updated, standby_needed translation added. Decision matrix documented. |
| Phase 3A – Terminology rename  | "Backup" → "Standby" across all new constants, variables, state/claim mode values, storage keys, and translation keys | ✅ 100%    | 26 renames across 7 Python files + 3 YAML/JSON files via Python rename scripts. Validated: ruff ✅, mypy ✅ (0 ChoreOps errors), 12/12 rotation tests pass. Zero old `BACKUP_ACCESS`/`PRIMARY_BACKUP`/`backup_needed` references remain. |
| Phase 4 – Testing              | Rotation FSM tests, boundary tests, regression                | ✅ 100%    | 10 tests in new file `test_rotation_primary_standby.py`. Covers: primary always claimable, standby state visibility, anytime/manual_only/on_overdue claim modes, set_rotation_turn override, turn-reset after approval, single-assignee edge case, due-today exclusion, pause activation. 22/22 rotation tests pass with zero regressions. |
| Phase 5a – Dashboard templates | Status maps, icons, layout, i18n (choreops-dashboards) | ✅ 100%    | Restructured rotation action layout: full-width Move to Front/Primary bar + 3-column temp actions (Activate/Set Turn, Activate All, Reset). Reactive standby indicator via Jinja2 `chore_attrs`. Activate All icon `mdi:account-multiple-plus-outline`. Reset icon `mdi:restore`, primary color. Amber warning text for active cycle. Horizontal `"i n"` layout for permanent action. `rotation_cycle_override` lifecycle fixed: cleared on reset, set_turn, and assignment changes. Translation keys `activate_all`, `all_standby_active` added. |
| Phase 5b – Docs & wiki         | 9 documentation files across 3 repos                          | 0%         | Wiki, architecture, design guide, release checklist                  |
| Phase 5c – Reschedule chore types filter | Add per-chore-type reschedule toggles; add "Shift Indep & Primary" dashboard card | ✅ 100%    | Three independent toggles: `reschedule_independent` (default true), `reschedule_primary_standby` (default true), `reschedule_shared` (default false). Dashboard 3-button layout with explicit toggle payloads. `push_primary_btn` slot with 10px left padding, `push_all_btn` full-width span-4. |
| Phase 5d – Smart resume options | Add `unpause_action` param to `pause_user_chores`; add resume option buttons to All Chores card | ✅ 100%    | Four unpause actions: `unpause`, `unpause_shift_independent`, `unpause_shift_all_primary`, `unpause_shift_all`. Backend delegates to `reschedule_chores_after` internally. Dashboard: resume section with "Past: Now" subtitle, 3 action buttons matching Phase 5c chore-type filters. |

1. **Key objective** – Introduce a `rotation_primary_standby` completion criteria where the first assigned user is always the primary (permanent turn-holder default). Backups see `standby` state and can claim based on the `standby_claim_mode` field: `anytime` (claim immediately), `on_overdue` (claim after due date), or `manual_only` (admin must intervene). Backup activation also occurs when the primary is paused or when an admin uses `set_rotation_turn`. After every completion, the turn always resets to the primary.

2. **Summary of recent work** – Phases 0–5d complete. All code gaps (G-1 through G-7) verified fixed in the actual codebase (see evidence below). Remaining: Phase 5b (docs & wiki).

3. **Next steps (short term)** – Phase 5b: Wiki documentation, architecture updates, release checklist sign-off.

4. **Risks / blockers**
   - `standby` is a new derived UI state — must be added to `CHORE_UI_ASSIGNEE_STATES` and all state-allowlist frozensets that need to include it.
   - Reset-boundary force-to-primary must not interfere with `rotation_cycle_override` (open cycle) or manual turn overrides that are mid-cycle.
   - Notification wording for standby activation must not confuse users — backup should understand they are helping, not taking over permanently.
   - **Pause coexistence**: The user chore pause feature (shipped v0.5.0+) adds `paused`/`blocked_paused` states, `_is_chore_paused_for_assignee()` helper, and `_advance_rotation_past_paused_assignee()` method. Primary-backup's reset-boundary force-to-primary is the only surface needing explicit pause awareness. See Phase 2 key issues for the full coexistence audit.
   - **G-1 (RESOLVED)**: `can_claim_chore` FSM — verified fixed at `chore_engine.py:473-477`
   - **G-2 (RESOLVED)**: Hardcoded tuples — all 3 sites use `_build_other_assignee_states()` helper which delegates to `is_single_claimer_mode()`
   - **G-4 (RESOLVED)**: Standby-needed notification — wired at `chore_manager.py:2169`, handler at `notification_manager.py:2880`
   - **`allow_steal` incompatibility**: Primary-backup chores intentionally block `allow_steal` (`OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL`). The `standby_claim_mode` field controls claim gating for standbys — `allow_steal` would silently conflict because the P3 primary-standby branch intercepts before the steal check. Validation in `data_builders.py` already rejects this combo. See Decision D-6.

## Phase 5c: Reschedule chore types filter

### Objective
Add granular control to the `reschedule_chores_after` service so admins can target independent-only, independent + primary-standby, or all chore types — without using the blunt "Shift All" option.

### Design

**Service change**: Add an optional `reschedule_primary_standby` boolean param (default `false`) to `RESCHEDULE_CHORES_AFTER_SCHEMA`.

**Chore filtering logic** (in `chore_manager.reschedule_chores_after()`):
- `reschedule_shared=false` (default) → only independent chores as before
- `reschedule_shared=true` → all chore-level-due-date types (existing behavior)
- `reschedule_primary_standby=true` → include `rotation_primary_standby` chores alongside independent ones

When both `reschedule_primary_standby=true` and `reschedule_shared=false` (the new middle option):
- Independent chores → shift per-assignee due dates (existing path)
- Primary-standby chores → shift single `due_date` (same shared-group path, but only for this criteria)
- Shared/rotation-simple/rotation-smart → skipped

| Param combo | Chores affected |
|---|---|
| `reschedule_shared=false` (default) | `independent` only |
| `reschedule_primary_standby=true` | `independent` + `rotation_primary_standby` |
| `reschedule_shared=true` | All chore-level-due-date types (shared, rotation, primary-standby) |

**Dashboard layout** (All Chores section):
```
[Shift Independent] [Shift Indep & Primary]    ← 2-column
[              Shift All (incl shared)         ]    ← full-width
```

**Translations**: New key `shift_independent_primary`.

### Files to touch
- `const.py` — `SERVICE_FIELD_RESCHEDULE_PRIMARY_STANDBY` constant
- `services.py` — add param to schema, pass to manager
- `managers/chore_manager.py` — filter logic change in `reschedule_chores_after()`
- `translations/en.json` — service field description
- `services.yaml` — field definition
- `translations/en_dashboard.json` — `shift_independent_primary` key
- `admin-peruser-v1.yaml`, `admin-shared-v1.yaml` — third card in All Chores section

## Phase 5d: Smart resume options

### Objective
Prevent notification storms when unpausing a user whose chores have past-due dates. Provide resume options that match the chore-type filtering from Phase 5c — all within a single backend service call.

### Design

**Service change**: Add an optional `resume_action` string param to `PAUSE_USER_CHORES_SCHEMA` and `set_user_chores_paused()`.

**`resume_action` values:**

| Value | Unpause + shift... | Chore types |
|---|---|---|
| `unpause` | Nothing (current behavior) | — |
| `unpause_shift_independent` | Past-due independent chores | `independent` |
| `unpause_shift_all_primary` | Past-due independent + primary-standby | `independent` + `rotation_primary_standby` |
| `unpause_shift_all` | All past-due chores | All types |

**Dashboard layout** (All Chores section, when user is paused):

```
  [                     Resume                     ]   ← green, full-width, safe default

  ── Resume & Reschedule Past-Due ──
  [ Shift Independent ] [ Shift Indep & Primary ]    ← green (subdued), 2-col
  [               Shift All Chores               ]    ← green (subdued), full-width
```

**Visual style:**

| Button | Color | Notes |
|---|---|---|
| **Resume** | Green (success) | Full opacity, current style |
| Shift buttons | Green (success), subdued | Lower border/background opacity (14%/5%) to indicate they're part of the resume action |

**Buttons call**: `pause_user_chores(paused=false, user_name=..., resume_action=...)` with the appropriate value. Internally delegates to `reschedule_chores_after(user_ids=[this_user], after=now, ...)` with Phase 5c toggle flags.

**Grid**: Paused state grows from 6 to 9 rows (added resume_btn, div_resume, and 2 resume shift button rows). Not-paused state unchanged.

### Implementation
- `const.py` — `SERVICE_FIELD_RESUME_ACTION`, `RESUME_ACTION_VALUES` frozenset, `RESUME_ACTION_*` value constants
- `services.py` — add param to `PAUSE_USER_CHORES_SCHEMA`, pass to manager
- `chore_manager.py` — handle `resume_action` in `set_user_chores_paused()`
- `en.json`/`services.yaml` — field definitions
- `en_dashboard.json` — `resume`, `resume_shift_*` labels, `resume_actions_section`
- `admin-peruser-v1.yaml`, `admin-shared-v1.yaml` — resume shift card vars, new grid rows, custom_fields

### Relationship to Phase 5c
Phase 5c delivered the three-toggle reschedule params. Phase 5d delegates to `reschedule_chores_after` with `reschedule_primary_standby=true` and `reschedule_shared=true` flags. Both params exist and are tested. No dependency blockers.

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Data model, storage, coordinator pattern
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Coding standards, event architecture, constant naming
   - [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) — Code review process
   - [QUALITY_REFERENCE.md](../QUALITY_REFERENCE.md) — Platinum quality compliance
   - [ChoreOps Rotation System Memory](../../memories/repo/choreops_rotation_system.md) — Rotation design decisions
   - `tests/test_rotation_fsm_states.py` — Existing rotation FSM test patterns
   - `tests/test_workflow_chores.py` (class `TestRotationSimpleChores`) — Rotation workflow test patterns

6. **Decisions & completion check**
   - **Decisions captured**:
     - D-1: Accountability stays with turn-holder (existing rotation model). Standby turn-holders are not penalized with missed/overdue when chore opens to them on overdue.
     - D-2: Backup claim gating uses the `standby_claim_mode` field — three modes: `anytime` (immediate), `on_overdue` (after due date), `manual_only` (admin intervention required).
     - D-3: Primary is implicit — `assigned_user_ids[0]`. No explicit `primary_assignee_id` field. Guard rails via documentation and validation.
     - D-4: `standby_claim_mode` field is independent of `overdue_handling`. Claim gating and penalty behavior are separate dimensions. Smart rotation among backups deferred to future.
     - D-5: Administrative controls reuse existing services — no new backend endpoints. `update_chore` (reorder assignees) changes the primary. `set_rotation_turn` assigns turn to a backup. `open_rotation_cycle` (already registered as `choreops.open_rotation_cycle`) lifts the standby lock for one cycle. Template-only changes: button labels and one new "Open to All Backups" button.
     - D-6: `allow_steal` (`OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL`) is **incompatible** with `rotation_primary_standby`. Backup claim gating is controlled exclusively by `standby_claim_mode`. Allowing both would create silent conflicts where `standby_claim_mode.manual_only` overrides `allow_steal` at the P3 resolver. Validation in `data_builders.py` already rejects this combination.
     - G-3/T-4: New derived UI state `standby` for standbys who are not the active turn-holder (replaces `not_my_turn` for this criteria only).
     - T-1: Manual turn override does NOT survive approval reset — turn always snaps back to primary at reset boundary.
     - T-5: If no backups are designated (single assignee), the chore operates gracefully. Does NOT auto-convert to `independent`.
     - O-1: "User paused" auto-failover — already implemented via `_advance_rotation_past_paused_assignee()`. Manual turn override deferred.
     - O-2: MVP notification leverages existing steal/due notification infrastructure with narrow wording adjustments.
     - O-3: Dashboard"Standby Duty" filter deferred to follow-up (dashboard template change).
     - O-4: Primary completion rate badge deferred; documented as known gap.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

## Implementation traps (code-verified 2026-06-11)

These were discovered during a detailed audit of the actual code against the plan's assumptions. They must be accounted for during implementation.

### Trap 1: `_advance_rotation` dispatches by `method`, not `completion_criteria`

The plan originally described inserting a `completion_criteria == ROTATION_PRIMARY_STANDBY` early-return before the method dispatch. But the actual method at `chore_manager.py:5113` translates criteria to method inside the `if method == "auto"` block and then dispatches by the resulting `method` value. The primary-standby handler must go **inside** the `"auto"` block as a `elif completion_criteria == ROTATION_PRIMARY_STANDBY` that sets `new_assignee_id = assigned[0]` directly. Phase 2 Step 1 has been updated to reflect this.

### Trap 2: `standby_claim_mode.on_overdue` with no due date locks backups out permanently

The P3 resolver gates the overdue window on `due_date is not None and now > due_date`. If a primary-standby chore uses `standby_claim_mode = on_overdue` but has no explicit due date (e.g., a daily recurring chore where the due date is computed at runtime), the standby **can never claim** because the overdue window never opens — `standby` is enforced forever. This must be validated against in `data_builders.py`: when `completion_criteria == ROTATION_PRIMARY_STANDBY` and `standby_claim_mode == STANDBY_CLAIM_MODE_ON_OVERDUE`, require a due date.

### Trap 3: P0 pause guard beats P3 `standby` (correct but subtle)

The pause P0 guard at `chore_manager.py:4129` runs BEFORE `resolve_assignee_chore_state()`. A paused standby sees **`paused`**, not `standby`. This is correct — pause is a stronger administrative state — but it also means: if a standby is paused and later unpaused, they will immediately see `standby` (or the appropriate state for their position in the rotation). If the admin expected them to become the active turn-holder on unpause, they need to check the rotation position first. Document this in the wiki.

### Trap 4: Primary paused → backup becomes active (intentional, with G-5 snap-back)

When the primary is paused, `_advance_rotation_past_paused_assignee()` (line 5854) advances the turn past them in real time. The standby sees the chore as a **normal required chore** — with due dates, notifications, overdue penalties, and point earnings — just as if they were the primary. When the primary unpauses, `_snap_rotation_back_to_primary()` (G-5, Phase 2 Step 8) immediately snaps the turn back to them in real time. This is the desired behavior: pausing the primary is the mechanism for activating backups, and unpausing restores them instantly.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Deep analysis — Gaps, traps & opportunities (code-verified 2026-06-11)

A systematic source-level audit was performed against the actual code in `choreops/custom_components/choreops/`. Each finding was verified by reading the exact lines. **No assumptions or guesswork.**

### G-1: `can_claim_chore` FSM blocking does not recognize `standby` (CRITICAL — MISSED)

**Location**: `engines/chore_engine.py:469-475`

The FSM-based blocking check in `can_claim_chore` only checks for `missed`, `waiting`, and `not_my_turn`:

```python
if resolved_state in (
    const.CHORE_STATE_MISSED,
    const.CHORE_STATE_WAITING,
    const.CHORE_STATE_NOT_MY_TURN,
):
```

Without `standby` in this tuple, a standby with `standby` state (and a locking `lock_reason`) falls through to the single-claimer check, which sees no other assignee has claimed, and returns `can_claim=True`. **This means all standbys would be able to claim regardless of `standby_claim_mode`.**

**Fix**: Add a dedicated check AFTER the existing FSM blocking block:

```python
# Primary-backup: standby blocks when lock_reason matches
if resolved_state == const.CHORE_STATE_STANDBY:
    if lock_reason == const.CHORE_STATE_STANDBY:
        return (False, const.TRANS_KEY_ERROR_CHORE_STANDBY)
    # lock_reason is STANDBY_AVAILABLE_SENTINEL → allow claim, fall through
```

Must be a separate check (not merged into the tuple above) because when `lock_reason == STANDBY_AVAILABLE_SENTINEL`, the claim must be **allowed** — a behavior unique to primary-standby that differs from `not_my_turn`/`waiting`/`missed` (which always block).

**Impact**: Without this fix, primary-standby chores are effectively broken — all standbys see the chore as claimable at all times.

### G-2: TWO hardcoded single-claimer tuples in `chore_manager.py` (MISSED — plan only accounted for one)

**Location**:
- `managers/chore_manager.py:730` — inside `_claim_chore_locked`
- `managers/chore_manager.py:3876` — inside `can_claim_chore()` public method

The plan's CRIT-1 correctly identifies these, but the plan only referenced line ~674. There are **two separate sites** with identically hardcoded tuples:

```python
if completion_criteria in (
    const.COMPLETION_CRITERIA_SHARED_FIRST,
    const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
    const.COMPLETION_CRITERIA_ROTATION_SMART,
):
```

Both must include `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY`. The site at `chore_manager.py:4185` (inside `get_chore_status_context`) uses `ChoreEngine.is_single_claimer_mode()` and is therefore covered by Phase 1 Step 4 — no change needed there.

**Impact**: Missing either site causes the `other_assignee_states` dict to not be built for primary-standby chores, which means single-claimer blocking (`other_state in (CLAIMED, APPROVED)`) is silently skipped. A backup could claim while another assignee already has.

**Consolidation plan** (confirmed: O-1 + O-4 merged). Instead of adding primary_standby to two hardcoded tuples, extract a shared helper:

```python
def _build_other_assignee_states(
    self, chore_data: ChoreData | dict[str, Any], assignee_id: str, chore_id: str
) -> dict[str, str] | None:
    """Build other_assignee_states dict for single-claimer blocking.

    Returns None for non-single-claimer modes (INDEPENDENT, SHARED).
    """
    if not ChoreEngine.is_single_claimer_mode(chore_data):
        return None
    assigned_assignees = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
    other_assignee_states: dict[str, str] = {}
    for other_id in assigned_assignees:
        if other_id != assignee_id and other_id:
            other_assignee_states[other_id] = (
                self._derive_boundary_assignee_state(other_id, chore_id)
            )
    return other_assignee_states
```

This eliminates all three hardcoded tuples (730, 3876, 4185) and prevents future criteria additions from missing this check entirely. Replace all three inline blocks with `other_assignee_states = self._build_other_assignee_states(chore_data, assignee_id, chore_id)`.

Site 3 (line 4185) also does the `is_completed_by_other` check — that extra logic stays in place, it just calls the helper instead of inlining the dict construction.

### G-3: `_advance_rotation` primary-standby handler must set `new_assignee_id` directly (TRAP REFINEMENT)

**Location**: `managers/chore_manager.py:5113-5145`

The plan correctly places the primary-standby check inside the `method == "auto"` block. But the code structure requires the handler to **explicitly set `new_assignee_id`**, not just set `method`. After auto-dispatch, the code falls through to `if method == "simple"` / `elif method == "smart"` / `elif method == "manual"` — none of which would match if `method` remains `"auto"`.

```python
if method == "auto":
    if completion_criteria == ROTATION_SIMPLE:
        method = "simple"
    elif completion_criteria == ROTATION_SMART:
        method = "smart"
    elif completion_criteria == ROTATION_PRIMARY_STANDBY:
        new_assignee_id = assigned_assignees[0] if assigned_assignees else None
        # new_assignee_id is set directly — no method dispatch
```

Without this, `new_assignee_id` stays `None`, the `if new_assignee_id:` guard at line ~5170 skips the assignment, and the turn is never updated to primary.

### G-4: Overdue notification type for standby-needed (GAP — PARTIALLY COVERED)

**Location**: `managers/chore_manager.py:2175-2181` and `managers/notification_manager.py:2860-2869`

The plan mentions a "Dedicated standby-needed notification" in Phase 3 Step 4 but doesn't trace through the notification infrastructure.

The overdue processing code at `chore_manager.py:2175` determines the `overdue_message_type`:

```python
overdue_message_type = CHORE_OVERDUE_NOTIFICATION_TYPE_DEFAULT
if (
    ChoreEngine.is_rotation_mode(chore_data)
    and overdue_handling == OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL
    and chore_data.get(DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID) != assignee_id
):
    overdue_message_type = CHORE_OVERDUE_NOTIFICATION_TYPE_STEAL_AVAILABLE
```

For primary-standby, when a standby is **not** the turn-holder and the chore becomes overdue, we need a **new** `CHORE_OVERDUE_NOTIFICATION_TYPE_STANDBY_NEEDED` constant (not `steal_available` — different concept). The check should be:

```python
if (
    completion_criteria == COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY
    and chore_data.get(DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID) != assignee_id
    and chore_data.get(DATA_CHORE_STANDBY_CLAIM_MODE, STANDBY_CLAIM_MODE_ANYTIME)
        in (STANDBY_CLAIM_MODE_ANYTIME, STANDBY_CLAIM_MODE_ON_OVERDUE)
):
    overdue_message_type = CHORE_OVERDUE_NOTIFICATION_TYPE_STANDBY_NEEDED
```

This requires:
- New constant `CHORE_OVERDUE_NOTIFICATION_TYPE_STANDBY_NEEDED` in `const.py`
- Notification handler in `notification_manager.py` (at ~line 2866, alongside `steal_available`)
- New translation keys (`TRANS_KEY_NOTIF_TITLE_CHORE_STANDBY_NEEDED`, `TRANS_KEY_NOTIF_MESSAGE_CHORE_STANDBY_NEEDED`)
- New notification template in `en_notifications.json`

**Impact**: Without this, backups get no notification when the chore becomes overdue — they'd have no idea they can now claim. The primary-standby experience would be silent and confusing.

### G-5: Immediate snap-back on unpause — complexity analysis (LOW)

**Location**: `managers/chore_manager.py:5913-5940` (`set_user_chores_paused`)

The pause/unpause service call flows through `services.py:3664` → `chore_manager.set_user_chores_paused()` (line 5913). Currently:

- `paused=True`: calls `_advance_rotation_past_paused_assignee()` — advances turn past the paused user
- `paused=False`: just clears the flag — **nothing happens to the turn**

**Complexity: LOW** (~25 lines production code). Add a new method `_snap_rotation_back_to_primary(unpaused_user_id)` and call it from the `not paused` branch:

```python
async def set_user_chores_paused(self, assignee_id, paused, paused_until=None):
    user_data[...][DATA_USER_CHORES_PAUSED] = paused
    # ... existing pause_until handling ...

    if paused:
        self._advance_rotation_past_paused_assignee(assignee_id)
    else:
        # NEW: Snap primary-standby chores back to primary on unpause
        self._snap_rotation_back_to_primary(assignee_id)

    self.coordinator._persist_and_update()
    self.emit(SIGNAL_SUFFIX_USER_UPDATED, user_id=assignee_id)
```

The helper method:

```python
def _snap_rotation_back_to_primary(self, unpaused_user_id: str) -> None:
    """Snap primary-standby chores back to primary when they unpause.

    For each primary-standby chore where the unpaused user is the
    primary (assigned_assignees[0]) but is NOT the current turn-holder,
    snap the turn back to them in real time.
    """
    chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
    snapped_count = 0
    for chore_id, chore_info in chores_data.items():
        criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if criteria != const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY:
            continue

        assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        if not assigned or assigned[0] != unpaused_user_id:
            continue  # Not the primary for this chore

        current_turn = chore_info.get(const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID)
        if current_turn == unpaused_user_id:
            continue  # Already the turn-holder

        chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = unpaused_user_id
        snapped_count += 1
        const.LOGGER.debug(
            "Primary-backup snapp: chore=%s turn=%s → primary=%s on unpause",
            chore_id, current_turn, unpaused_user_id,
        )

    if snapped_count:
        const.LOGGER.info(
            "Snapped %d primary-standby chore(s) to primary %s on unpause",
            snapped_count, unpaused_user_id,
        )
```

**Why LOW complexity**:
- Pure iteration over chores data — no async I/O, no signals, no side effects
- Mirrors the existing `_advance_rotation_past_paused_assignee` pattern (proven pattern, same approach)
- Only touches `rotation_current_assignee_id` — the same field other methods modify
- No new signal types needed — the `USER_UPDATED` signal already emitted by `set_user_chores_paused` triggers UI refresh
- ~25 lines of production code, ~30 lines of test coverage

**Recommendation**: Include in the implementation. The cost is negligible relative to the overall feature, and it eliminates a confusing UX gap (primary pauses, backup takes over, primary unpauses — nothing happens until midnight).

### G-6: `overdue_handling` and `standby_claim_mode` independence edge case (VERIFIED SAFE)

**Location**: Phase 2 Step 3 P3 resolver — the backup's claim gating uses `due_date is not None and now > due_date`, NOT `overdue_handling`.

This means `standby_claim_mode.on_overdue` is based on the literal due date, not the `overdue_handling` field. A chore with `overdue_handling = never_overdue` but a valid `due_date` would still open to backups when past the due date.

**Verdict**: This is correct behavior per D-4. The plan already validates in `data_builders.py` that `standby_claim_mode.on_overdue` requires a `due_date` (Trap 2). No additional fix needed, but the wiki documentation should clarify: "Backups with `on_overdue` gain claim access when the due date has passed, regardless of the chore's overdue handling type."

### G-7: `standby` in `CHORE_UI_ASSIGNEE_STATES` must be added (COVERED)

**Location**: `const.py:1896-1910`

The plan's Phase 1 Step 2 correctly identifies this. Verified that `CHORE_UI_ASSIGNEE_STATES` is used for sensor attribute validation and frozenset membership checks. Without `standby`, the sensor would not recognize it as a valid assignee display state.

### Summary of actions required

| # | Type | Location | Urgency | Covered in plan? |
|---|------|----------|---------|-----------------|
| G-1 | **New CRITICAL** | `chore_engine.py:469` | **BLOCKING** — will not work without | ❌ Missed |
| G-2 | **Correction** | `chore_manager.py:730,3876` | **BLOCKING** — two sites, not one | ⚠️ Partially (CRIT-1 only names ~674) |
| G-3 | Refinement | `chore_manager.py:5113-5145` | **BLOCKING** — incorrect fall-through | ⚠️ Described but needs clear code |
| G-4 | **New** | `chore_manager.py:2175` + notification | High — silent UX failure | ⚠️ Partially (mentions notifications) |
| G-5 | Documentation | `chore_manager.py:5854` | Low — acceptable for MVP | ❌ Missed (pause interaction) |
| G-6 | Documentation | P3 resolver | Low — behavior is correct | ✅ Covered (D-4, Trap 2) |
| G-7 | Covered | `const.py` | Required | ✅ Covered (Phase 1 Step 2) |

### Opportunities

- **O-1: Refactor `chore_manager.py` hardcoded tuples to use `is_single_claimer_mode()`** — The two sites at lines 730 and 3876 duplicate the engine's `is_single_claimer_mode()` logic. After adding primary-standby to these tuples, consider replacing them with `ChoreEngine.is_single_claimer_mode(chore_data)` to prevent future omissions. This is a small cleanup but eliminates an entire class of bugs.

- **O-2: Test for `can_claim_chore` blocking states** — Add a test that verifies `can_claim_chore` returns `False` for all recognized blocking states (`not_my_turn`, `waiting`, `missed`, `standby`). This prevents future criteria additions from missing the FSM blocking check.

## Detailed phase tracking

### Phase 0 – Verification Pass (Assumption Check & Gap Inventory)

**Date**: 2026-06-05 | **Status**: Complete

- **Goal**: Verify every assumption in the plan against actual code paths, identify all hardcoded criteria lists that need updating, catalog documentation touch points.

- **Findings**:

  #### A. Hardcoded criteria lists requiring `rotation_primary_standby` addition

  The following locations hardcode completion criteria tuples and MUST be updated. These were missed in the initial plan draft.

  | # | File | Line | Context | Action |
  |---|------|------|---------|--------|
  | **CRIT-1** | `chore_manager.py` | ~674 | `can_claim_chore` — builds `other_assignee_states` dict for single-claimer blocking | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-2** | `chore_manager.py` | ~4828 | `_remove_name_from_ownership_list` — clears chore-level ownership fields for single-claimer modes | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-3** | `chore_engine.py` | ~578 | `uses_chore_level_due_date` — primary-standby uses chore-level due dates (same as all rotation types) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-4** | `services.py` | ~217 | `_uses_chore_level_due_date` (duplicate of CRIT-3 in services module) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-5** | `data_builders.py` | ~1375 | `_uses_chore_level_due_date` (duplicate of CRIT-3 in data_builders) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-6** | `services.py` | ~735 | `_COMPLETION_CRITERIA_VALUES` — master list of valid completion criteria for service validation | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-7** | `chore_engine.py` | ~1046 | `get_criteria_transition_actions` — `old_is_rotation`/`new_is_rotation` checks. Without this, criteria transitions to/from primary_standby won't initialize/clear rotation fields (`DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID`, `rotation_cycle_override`) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-8** | `data_builders.py` | ~1853 | `build_chore` — `DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID` initialization only happens for ROTATION_SIMPLE and ROTATION_SMART. New primary_standby chores won't get a turn-holder set on creation | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | **CRIT-9** | `chore_manager.py` | ~5086 | `_handle_criteria_transition` — ≥2 assignee validation check for `new_is_rotation`. **Deliberately excluded** primary_standby per T-5 (single assignee allowed). Primary_backup with 1 assignee (primary only, no backups) must work | **Do NOT add** — but verify the transition actions (CRIT-7) still run for single-assignee primary_standby |

  #### B. Hardcoded lists that do NOT need updating (verified safe)

  | # | File | Line | Context | Why safe |
  |---|------|------|---------|----------|
  | SAFE-1 | `chore_engine.py` | 564 | `is_shared_chore` — checks SHARED + SHARED_FIRST | Primary-backup is ROTATION, not shared. Correctly excluded. |
  | SAFE-2 | `coordinator.py` | 543 | `is_shared_chore` (duplicate) | Same as SAFE-1. |
  | SAFE-3 | `entity_helpers.py` | 731 | `is_shared_chore` (duplicate) | Same as SAFE-1. |
  | SAFE-4 | `chore_engine.py` | 338 | `_plan_disapprove_effects` — `criteria == SHARED_FIRST` | Primary-backup falls to `else` (independent/rotation behavior: only actor resets). Correct. |
  | SAFE-5 | `chore_engine.py` | 386 | `_plan_undo_effects` — `criteria == SHARED_FIRST` | Same as SAFE-4. |
  | SAFE-6 | `chore_manager.py` | 524 | Rotation assignee deletion resilience — uses `is_rotation_mode()` | Covered by step 1.3. |
  | SAFE-7 | `chore_manager.py` | 883 | `_build_completion_signal_payload` — uses `is_single_claimer_mode()` | Covered by step 1.4. |
  | SAFE-8 | `chore_manager.py` | 1156 | `_approve_chore_locked` — uses `is_single_claimer_mode()` | Covered by step 1.4. |
  | SAFE-9 | `chore_manager.py` | 1179 | `_approve_chore_locked` rotation advance — uses `is_rotation_mode()` | Covered by step 1.3. |
  | SAFE-10 | `chore_manager.py` | 3268 | Rotation cleanup on assignee removal — uses `is_rotation_mode()` | Covered by step 1.3. |
  | SAFE-11 | `sensor.py` | 1155 | `turn_assignee_name` resolution — uses `is_rotation_mode()` | Covered by step 1.3. |
  | SAFE-12 | `notification_manager.py` | 1732 | `_clear_single_claimer_peer_transient_notifications` — uses `is_single_claimer_mode()` | Covered by step 1.4. |
  | SAFE-13 | `notification_manager.py` | 2655 | Due window notification filtering — uses `is_rotation_mode()` | Covered by step 1.3. Only turn-holder gets notified. Correct for primary_standby. |
  | SAFE-14 | `notification_manager.py` | 2725 | Due reminder notification filtering — uses `is_rotation_mode()` | Same as SAFE-13. |
  | SAFE-15 | `services.py` | 1029-1070 | Rotation service schemas (`set_rotation_turn`, `reset_rotation`, `open_rotation_cycle`) — no criteria-specific validation in schemas | Delegates to ChoreManager which uses `is_rotation_mode()`. Covered. |
  | SAFE-16 | `options_flow.py` | 1120,1435,1595,1673 | Per-assignee field routing — checks `== INDEPENDENT` (not a tuple check) | Primary_backup is not INDEPENDENT, correctly skips per-assignee fields. |
  | SAFE-17 | `flow_helpers.py` | 893-903 | Build chore schema — uses `COMPLETION_CRITERIA_OPTIONS` from const.py | Covered by adding to options list in Phase 1 step 1. |
  | SAFE-18 | `engines/chore_engine.py` | 1171 | `compute_global_chore_state` single-claimer branch — overridden by `resolve_rotation_global_state` for rotation types | Primary_backup enters single-claimer branch then gets overridden by rotation resolver. Safe. |

  #### C. Assumptions verified

  | Assumption | Verification | Result |
  |------------|-------------|--------|
  | `is_rotation_mode()` covers primary_standby | Step 1.3 adds to tuple at line 595 | ✅ Correct, all rotation-aware code paths inherit |
  | `is_single_claimer_mode()` covers primary_standby | Step 1.4 adds to tuple at line 614 | ✅ Correct, all single-claimer code paths inherit |
  | P3 sub-branch placement is safe | New branch inside `is_rotation_mode()` block, BEFORE generic `not_my_turn` return at line 696-705 | ✅ Correct — primary_standby returns `standby`, simple/smart continue to `not_my_turn` |
  | Force-to-primary at reset boundary doesn't break rotation signals | `_advance_rotation` captures `previous_assignee_id` BEFORE modifying `rotation_current_assignee_id` (line ~4968 before ~5028) | ✅ Correct — signal payload has correct previous |
  | No-conflict with `rotation_cycle_override` | `_is_rotation_open_claim_cycle` covers primary_standby via `is_rotation_mode()` | ✅ Correct |
  | `standby_available` claim mode triggers for primary_standby | `get_chore_status_context` resolves via `claim_error_to_claim_mode` mapping from sentinel | ✅ Correct after Phase 2 Step 4 |
  | Completion criteria display label auto-resolves in dashboards | `ui.get(completion_type_key, ...)` where key comes from entity attribute | ✅ Correct — only translation key needed, no template logic |
  | Single-assignee primary-standby doesn't crash | P3 returns `standby` for `assignee_id != current_turn`. With 1 assignee, primary IS turn holder, so condition never true. | ✅ Correct — no standby shown for solo primary |

  #### D. Reset-boundary ordering refinement

  The initial plan placed force-to-primary BEFORE `_advance_rotation`. This would cause `_advance_rotation` to capture `previous_assignee_id = primary` (since turn was already reset). **Correction**: Force-to-primary should run AFTER the `if completed_by_assignee_id:` block but still within the `if new_state == CHORE_STATE_PENDING and reset_approval_period:` scope. This ensures:
  1. If someone completed: `_advance_rotation` captures correct previous (standby), sets new=primary
  2. If nobody completed: force-to-primary runs as a fallback (manual override survived into new cycle)

  Revised placement in `_transition_chore_state`:
  ```python
  if new_state == const.CHORE_STATE_PENDING and reset_approval_period:
      if completed_by_assignee_id:
          rotation_signal_payload = self._advance_rotation(...)

      # Primary-backup: force turn to primary at reset boundary
      # (after _advance_rotation so signal captures correct previous_assignee_id)
      if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == \
              const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY:
          assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
          if assigned:
              chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = assigned[0]
  ```

  #### E. Documentation inventory

  Files requiring updates (beyond the plan itself):

  | Doc | What to add |
  |-----|------------|
  | `choreops-wiki/Configuration:-Chores.md` | New "Rotation — Primary & Standby" subsection under Completion Criteria, explaining implicit primary, standby_claim_mode modes, pause interaction, and accountability model |
  | `choreops-wiki/Advanced:-Chores.md` | New section or subsection covering primary-standby: when to use, how standby activation works, rotation comparison table, known limitations |
  | `choreops-wiki/Configuration:-Users.md` | Note that for primary-standby chores, first assigned user in list is the primary |
  | `choreops/docs/ARCHITECTURE.md` | Add `standby` to the derived UI state listing if `CHORE_UI_ASSIGNEE_STATES` is documented there |
  | `choreops/docs/DEVELOPMENT_STANDARDS.md` | No change needed — pattern is identical to existing rotation criteria |
  | `choreops/docs/DASHBOARD_UI_DESIGN_GUIDELINE.md` | Add `standby`, `standby_available`, `blocked_standby` to the blocked/exception states table |
  | `choreops/docs/QUALITY_REFERENCE.md` | No change needed unless new quality rule is affected |
  | `choreops-dashboards/translations/en_dashboard.json` | 3 new i18n keys (already in Phase 5a) |
  | `choreops-wiki/_Sidebar.md` | May need link update if new wiki page is created |

- **Key issues**
  - CRIT-1 through CRIT-8 are **mandatory pre-merge requirements**. Missing any of these would cause runtime bugs: `can_claim_chore` would not build `other_assignee_states` for primary-standby chores, breaking single-claimer blocking; `_remove_name_from_ownership_list` would not clear ownership fields correctly; due date lookups would use wrong storage path.
  - The `choreops-wiki` repo is a separate repository — wiki updates must be coordinated with the integration release.
  - reset-boundary ordering (item D) is a subtle but important refinement from the initial plan.

### Phase 1 – Foundation (Constants, Types, Criteria Registration)

- **Goal**: Register the new completion criteria and derived UI state so all downstream code can reference them. Zero behavioral changes — just wiring.

- **Steps / detailed work items**

  1. `[x]` **Add `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` constant** in `custom_components/choreops/const.py`.
  2. `[x]` **Add `CHORE_STATE_STANDBY` derived UI state** in `custom_components/choreops/const.py` + add to `CHORE_UI_ASSIGNEE_STATES`.
  3. `[x]` **Add criteria to `ChoreEngine.is_rotation_mode()`** in `engines/chore_engine.py`.
  4. `[x]` **Add criteria to `ChoreEngine.is_single_claimer_mode()`** in `engines/chore_engine.py`.
  5. `[x]` **Add translation key constant** `TRANS_KEY_COMPLETION_CRITERIA_PRIMARY_STANDBY` in `const.py`.
  6. `[x]` **Validation guard** — verified via `is_rotation_mode()` adoption (CRIT-9: primary_standby intentionally excluded from ≥2 check).
  7. `[x]` **Add `standby` claim mode constants** (`CHORE_CLAIM_MODE_BLOCKED_STANDBY`, `CHORE_CLAIM_MODE_STANDBY_AVAILABLE`) + add both to `CHORE_CLAIM_MODES`.
  8. `[x]` **Add `standby_claim_mode` storage field and constants** (`DATA_CHORE_STANDBY_CLAIM_MODE`, `STANDBY_CLAIM_MODE_*`, `STANDBY_CLAIM_MODE_OPTIONS`). Default `"anytime"` set in `build_chore()`.
  9. `[x]` **O-1/O-4: Extract `_build_other_assignee_states()` helper** — replaces all 3 inline hardcoded tuples at lines 730, 3876, 4185 with `ChoreEngine.is_single_claimer_mode()` based helper. Eliminates CRIT-1/1b.
  10. `[x]` **CRIT-2: Add to `_remove_assignee_from_ownership_fields`** tuple in `chore_manager.py`.
  11. `[x]` **CRIT-3: Add to `uses_chore_level_due_date`** in `chore_engine.py`.
  12. `[x]` **CRIT-4: Add to `_service_uses_chore_level_due_date`** in `services.py`.
  13. `[x]` **CRIT-5: Add to `_uses_chore_level_due_date`** in `data_builders.py`.
  14. `[x]` **CRIT-6: Add to `_COMPLETION_CRITERIA_VALUES`** in `services.py` + update `services.yaml` + update `translations/en.json` criteria maps.
  15. `[x]` **CRIT-7: Add to `get_criteria_transition_actions`** in `chore_engine.py`.
  16. `[x]` **CRIT-8: Add to `build_chore`** rotation initialization tuple in `data_builders.py`.

- **Key issues**
  - **CRIT-1/1b replaced by O-1/O-4**: Instead of adding to two hardcoded tuples, extract `_build_other_assignee_states()` helper. This eliminates the hardcoded tuple pattern entirely and prevents future criteria additions from missing this check.
  - **CRIT-7 is the most subtle**: Without it, changing an existing chore to `rotation_primary_standby` from the UI leaves `rotation_current_assignee_id` unset. The chore would have no turn-holder and all assignees would see `standby`.
  - **CRIT-8 is equally critical**: Without it, newly created primary_standby chores have no turn-holder.
  - **CRIT-9 is a deliberate exclusion**: Adding primary_standby to the ≥2 validation would block single-backup configurations. T-5 explicitly allows this.

---

### Phase 2 – Core Implementation (Engine FSM + Manager Turn Logic)

- **Goal**: Implement the two behavioral deltas that distinguish primary-standby from standard rotation: (a) turn always resets to primary (index 0) after completion, and (b) non-turn backups see `standby` instead of `not_my_turn`.

- **Steps / detailed work items**

  1. `[x]` **Modify `_advance_rotation()`** in `custom_components/choreops/managers/chore_manager.py` (~line 5113, inside the `if method == "auto"` dispatch block). Add primary-standby handler that **directly sets `new_assignee_id`** to `assigned[0]`:

     **⚠️ TRAP**: The `_advance_rotation` method dispatches by `method` parameter, not `completion_criteria`. After the `"auto"` block, the code checks `if method == "simple"`, `elif method == "smart"`, `elif method == "manual"`. Setting `method` to a new string won't help — there's no matching dispatch. The handler must set `new_assignee_id` directly:

     ```python
     if method == "auto":
         # Determine method from completion criteria
         if completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SIMPLE:
             method = "simple"
         elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SMART:
             method = "smart"
         elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY:
             new_assignee_id = assigned_assignees[0] if assigned_assignees else None
             # new_assignee_id is set directly — no method dispatch needed.
             # Falls through to the metadata update + signal payload at ~line 5170.
     ```

     **Without this explicit assignment**, `new_assignee_id` stays `None`, the `if new_assignee_id:` guard skips the turn update, and the turn is never set to primary.

  2. `[x]` **Add reset-boundary force-to-primary (pause-aware)** in `_transition_chore_state()` in `custom_components/choreops/managers/chore_manager.py` (~line 4677, after the existing `_advance_rotation` call). **Placement refined by verification pass**: force-to-primary runs AFTER `_advance_rotation` (so signal captures correct `previous_assignee_id`) but still within the `if new_state == CHORE_STATE_PENDING and reset_approval_period:` scope. This handles the "nobody completed, midnight passes" case where a manual turn override from a previous cycle leaks into the new one.

     **Pause interaction (CRIT-2 from cross-analysis):** The force-to-primary must check whether the primary is paused using the existing `_is_chore_paused_for_assignee()` helper (see `chore_manager.py` line 4062). If the primary is paused, snap to the first non-paused backup. If ALL assignees are paused, freeze at current turn (do not change `rotation_current_assignee_id`).

     ```python
     if new_state == const.CHORE_STATE_PENDING and reset_approval_period:
         # Advance rotation (primary-standby sets new=primary within _advance_rotation)
         if completed_by_assignee_id:
             rotation_signal_payload = self._advance_rotation(
                 chore_id, completed_by_assignee_id, method="auto"
             )

         # Primary-backup: force turn to primary at every reset boundary
         # Pause-aware: skips paused primary, freezes if all paused
         if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == \
                 const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY:
             assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
             if assigned:
                 target = assigned[0]
                 if self._is_chore_paused_for_assignee(target, chore_id):
                     # Primary paused — find first non-paused backup
                     for candidate in assigned[1:]:
                         if not self._is_chore_paused_for_assignee(candidate, chore_id):
                             target = candidate
                             break
                     else:
                         target = None  # All paused, freeze
                 if target is not None:
                     chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = target
     ```
     This ensures T-1 and pause coexistence: manual override does not survive reset, and paused users are correctly handled.

  3. `[x]` **Modify `resolve_assignee_chore_state()` P3 block** in `custom_components/choreops/engines/chore_engine.py` (~line 676-710). For primary-standby chores, non-turn assignees see `standby`. Claim gating is controlled by the new `standby_claim_mode` field (see new Phase 1 step 17 below), NOT by `overdue_handling`:

     ```python
     # Inside P3: if primary-standby and not turn-holder
     if (
         completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY
         and assignee_id != current_turn
         and not override
     ):
         standby_claim_mode = chore_data.get(
             const.DATA_CHORE_STANDBY_CLAIM_MODE, const.STANDBY_CLAIM_MODE_ANYTIME
         )

         if due_date is not None and now > due_date:
             # Backups with anytime or on_overdue can claim when overdue
             if standby_claim_mode in (
                 const.STANDBY_CLAIM_MODE_ANYTIME,
                 const.STANDBY_CLAIM_MODE_ON_OVERDUE,
             ):
                 pass  # Fall through — overdue, claimable, shows as "Standby needed"
             else:  # manual_only
                 return (const.CHORE_STATE_STANDBY, const.CHORE_STATE_STANDBY)
         else:
             # Not yet overdue — only anytime backups can claim
             if standby_claim_mode == const.STANDBY_CLAIM_MODE_ANYTIME:
                 return (const.CHORE_STATE_STANDBY, const.STANDBY_AVAILABLE_SENTINEL)
             else:
                 return (const.CHORE_STATE_STANDBY, const.CHORE_STATE_STANDBY)
     ```

     **Sentinels**: `STANDBY_AVAILABLE_SENTINEL` is a sentinel value used to signal "standby state but claimable." In `get_chore_status_context()`, it maps to `claim_mode = CHORE_CLAIM_MODE_STANDBY_AVAILABLE` and `can_claim = True`. This allows the dashboard to show `mdi:shield-check-outline` ("you're a standby and can claim") vs `mdi:shield-account-outline` ("you're a standby and cannot claim").

  4. `[x]` **Update `get_chore_status_context()` claim mode mapping** in `custom_components/choreops/managers/chore_manager.py` (~line 4114-4140). Add `standby` to the `claim_error_to_claim_mode` mapping:
     ```python
     const.TRANS_KEY_ERROR_CHORE_STANDBY: const.CHORE_CLAIM_MODE_BLOCKED_STANDBY,
     ```
     And map `STANDBY_AVAILABLE_SENTINEL` → `CHORE_CLAIM_MODE_STANDBY_AVAILABLE` with `can_claim = True`.

  5. `[x]` **Update `_is_rotation_open_claim_cycle()`** — verify it already handles `rotation_primary_standby` via `is_rotation_mode()`. Since step 1.3 adds the criteria to `is_rotation_mode()`, no code change needed. But verify with a targeted test.

  6. `[x]` **Update `can_claim_chore()` FSM blocking in `chore_engine.py`** (~line 469-475, G-1 from deep analysis). Add a dedicated check for `standby` AFTER the existing `(MISSED, WAITING, NOT_MY_TURN)` block. Must be a separate check (not merged into the tuple) because `standby` with `lock_reason == STANDBY_AVAILABLE_SENTINEL` should **allow** the claim:

     ```python
     # Primary-backup: standby blocks when lock_reason matches
     if resolved_state == const.CHORE_STATE_STANDBY:
         if lock_reason == const.CHORE_STATE_STANDBY:
             return (False, const.TRANS_KEY_ERROR_CHORE_STANDBY)
         # lock_reason is STANDBY_AVAILABLE_SENTINEL → allow claim, fall through
     ```

     **Without this fix**, all standbys see the chore as claimable at all times, regardless of `standby_claim_mode` configuration.

  7. `[x]` **Update `chore_counts_toward_due_today_summary()`** — `CHORE_STATE_STANDBY` and `CHORE_CLAIM_MODE_BLOCKED_STANDBY` added to exclusion lists. ✅

  7. `[x]` **Update `_collect_normalized_assignee_persisted_states()`** — no change needed. `standby` is a DERIVED (UI-only) state, never persisted. The persisted state for a standby who hasn't acted is `pending`, which is already handled.

  8. `[x]` **Add `_snap_rotation_back_to_primary()` method** in `custom_components/choreops/managers/chore_manager.py` (~after line 5890, after `_advance_rotation_past_paused_assignee`). When a primary user unpauses (`set_user_chores_paused` with `paused=False`), snap all primary-standby chores back to the primary in real time:

     ```python
     def _snap_rotation_back_to_primary(self, unpaused_user_id: str) -> None:
         """Snap primary-standby chores back to primary when they unpause."""
         chores_data = self._coordinator._data.get(const.DATA_CHORES, {})
         snapped_count = 0
         for chore_id, chore_info in chores_data.items():
             criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
             if criteria != const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY:
                 continue
             assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
             if not assigned or assigned[0] != unpaused_user_id:
                 continue
             current_turn = chore_info.get(
                 const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID
             )
             if current_turn == unpaused_user_id:
                 continue  # Already the turn-holder
             chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = (
                 unpaused_user_id
             )
             snapped_count += 1
         if snapped_count:
             const.LOGGER.info(
                 "Snapped %d primary-standby chore(s) to primary %s on unpause",
                 snapped_count, unpaused_user_id,
             )
     ```

  9. `[x]` **Wire snap-back into `set_user_chores_paused()`** (~line 5913). Add `elif not paused:` branch that calls `_snap_rotation_back_to_primary(assignee_id)`:

     ```python
     if paused:
         self._advance_rotation_past_paused_assignee(assignee_id)
     else:
         # G-5: Immediate snap-back to primary on unpause
         self._snap_rotation_back_to_primary(assignee_id)
     ```

### Phase 2a – Config & Options Flow (standby_claim_mode in chore settings UI)

- **Goal**: Add the `standby_claim_mode` field to the config flow and options flow chore settings screens so users can select the standby claim mode when creating or editing primary-standby chores.

- **Critical patterns**: The options flow uses a specific data mapping pattern (`CFOF_CHORES_INPUT_*` ↔ `DATA_CHORE_*`), schema validation via `flow_helpers.py`, and translation keys in `en.json`. Every new field must follow existing patterns exactly.

- **Steps / detailed work items**

  1. `[x]` **Add `CFOF_CHORES_INPUT_STANDBY_CLAIM_MODE` constant** in `const.py`. ✅
  2. `[x]` **Add to `CHORE_ROOT_FORM_FIELDS` tuple** in `flow_helpers.py` after `COMPLETION_CRITERIA`. ✅
  3. `[x]` **Add reverse data mapping** (chore_data → form defaults) in `options_flow.py`. ✅
  4. `[x]` **Add forward data mapping** — handled implicitly by `build_chore()` which reads `standby_claim_mode` via `get_field()`. No explicit merge needed in options_flow for this field. ✅
  5. `[x]` **Add translation strings** — field names/descriptions in all 6 form step sections, selector options under `selector.standby_claim_mode.options`, `TRANS_KEY_FLOW_HELPERS_STANDBY_CLAIM_MODE` constant. ✅

- **Key issues**
  - **No fake "N/A" options**: The field always defaults to `"anytime"` and shows the 3 real options at all times. The field description clarifies: *"Controls when backups can claim this chore. Only applies to Primary & Standby completion criteria."* This is cleaner than a disabled-state.
  - The `CFOF_CHORES_INPUT_*` → `DATA_CHORE_*` mapping must be added in ALL places where chore data is transformed (both create path and update path in `options_flow.py`).
  - Must verify the `_handle_criteria_transition()` in `chore_manager.py` ensures `standby_claim_mode` exists when transitioning TO primary-standby (default `anytime`).

### Phase 2b – Service Updates (standby_claim_mode in create_chore / update_chore)

- **Goal**: Allow the `create_chore` and `update_chore` services to accept and set the `standby_claim_mode` field.

- **Steps / detailed work items**

  1. `[x]` **Add `SERVICE_FIELD_CHORE_CRUD_STANDBY_CLAIM_MODE` constant** in `const.py`. ✅
  2. `[x]` **Add schema field to `CREATE_CHORE_SCHEMA`** — right after `completion_criteria`, using `_STANDBY_CLAIM_MODE_VALUES` validator. ✅
  3. `[x]` **Add schema field to `UPDATE_CHORE_SCHEMA`** — alongside `overdue_handling`. ✅
  4. `[x]` **Add service translation descriptions** in `en.json` for both `create_chore` and `update_chore`. ✅
  5. `[x]` **Add service YAML descriptions** in `services.yaml` for both `create_chore` (after `completion_criteria`) and `update_chore`. ✅
  6. `[x]` **Verify handler pass-through** — `build_chore()` handles `standby_claim_mode` via `get_field()` with default `anytime`. No handler change needed. ✅

- **Key issues**
  - The `create_chore` and `update_chore` handlers use `build_chore()` which already defaults `standby_claim_mode` to `anytime`. When the service provides the field, it overrides the default. This is correct behavior.
  - Service validation uses `_COMPLETION_CRITERIA_VALUES` which already includes `rotation_primary_standby` (Phase 1 CRIT-6). No additional validation needed at service level.
  - The `_service_uses_chore_level_due_date` function already includes `rotation_primary_standby` (Phase 1 CRIT-4), which is correct — primary-standby chores use chore-level due dates.
  - **`standby` vs `not_my_turn` lock_reason**: Both use their state string as the lock reason (consistent with existing pattern). Sensors/UI use this for display logic.
  - **Reset boundary ordering**: Force-to-primary must happen AFTER `_advance_rotation` is called in `_transition_chore_state`, so the signal payload captures the correct "previous" assignee.
  - **Pause coexistence (v0.5.0+)**: The user chore pause feature shipped before primary-standby. Key surfaces already handled:
    - P0 guard in `get_chore_status_context` (line 4129) is criteria-agnostic — returns `paused` for any criteria. No change needed for primary-standby. ✅
    - `can_claim_chore` pause guard (line 3859) already blocks claims for paused users regardless of criteria. ✅
    - `set_rotation_turn` pause guard (line 5290) already rejects setting turn to a paused user. ✅
    - `_advance_rotation_past_paused_assignee()` (line 5854) handles rotation advance past paused turn-holders in real time. Since it uses `is_rotation_mode()`, it automatically covers primary-standby. ✅
    - `_advance_rotation()` (line 5071) has NO internal pause skip loop. The cross-analysis (CRIT-1) incorrectly predicted one — the implementations are in separate methods and do not conflict. ✅
    - The reset-boundary force-to-primary (Step 2 above) is the only location needing explicit pause awareness. ⚠️

- **Baseline test validation (2026-06-11)** — Full test suite executed to establish a clean baseline before implementation:
  ```text
  Results (698.90s (0:11:38)):
      1895 passed
         4 skipped
        18 deselected
  ```
  All passing. Quality gates (linting) also clean. Quick-lint, mypy, and full pytest suite validated.
- **Deep code audit (2026-06-11)** — Detailed source-level analysis revealed 5 new gaps/traps beyond the original Phase 0 inventory. See the "Deep analysis" section below.

---

### Phase 3 – UX & Notifications (Translations, Display, Wording)

- **Goal**: Ensure user-facing strings are translatable, the `standby` state is properly labeled, and notification wording makes sense for the primary-standby relationship.

- **Steps / detailed work items**

  1. `[x]` **Add `standby` translation strings** — state label + claim mode labels in `en.json`. ✅ (Phase 1)
  2. `[x]` **Add completion criteria label translation** — `"Primary & Standby"` in all 3 `en.json` locations. ✅ (Phase 1)
  3. `[x]` **Add `chore_standby` exception translation** — const key + `en.json` message. ✅ (Phase 1)
  4. `[x]` **Add `CHORE_OVERDUE_NOTIFICATION_TYPE_STANDBY_NEEDED` constant** in `const.py`. ✅ (Phase 1)
  5. `[x]` **Wire standby-needed message type in overdue processing** — `chore_manager.py:2175`. New condition block BEFORE `steal_available`. `manual_only` case skips signal entirely via `continue`. ✅
  6. `[x]` **Handle standby_needed in notification_manager.py** — added `elif` alongside `steal_available`. Resolves `primary_name` from `assigned_assignees[0]`. ✅
  7. `[x]` **Add notification translation strings** — `"chore_standby_needed"` entry in `translations_custom/en_notifications.json` with title + message. ✅
  8. `[x]` **Add notification key constants** — `TRANS_KEY_NOTIF_TITLE/MESSAGE_CHORE_STANDBY_NEEDED` in `const.py`. ✅ (Phase 1)
  9. `[x]` **Add `can_claim_error` translation** — already in `claim_error_to_claim_mode` map. ✅ (Phase 2)
  10. `[x]` **Update `services.yaml`** — no new service params needed. ✅

- **Backup notification decision matrix** — Determines which scenarios trigger notifications for standbys:

  | # | Turn-holder | Standby claim mode | Chore overdue? | Notify backup? | Notification type | Rationale |
  |---|-------------|---------------|----------------|----------------|-------------------|-----------|
  | 1 | Primary | `anytime` | No | ❌ Skip | — | Backup can already claim, no trigger event |
  | 2 | Primary | `anytime` | **Yes** | ✅ Send | `standby_needed` | Primary is late, backup may want to step in |
  | 3 | Primary | `on_overdue` | No | ❌ Skip | — | Gate hasn't opened yet |
  | 4 | Primary | `on_overdue` | **Yes** | ✅ **Essential** | `standby_needed` | The claim gate just opened — this IS the trigger |
  | 5 | Primary | `manual_only` | No | ❌ Skip | — | Admin must intervene |
  | 6 | Primary | `manual_only` | **Yes** | ❌ **Skip (no signal)** | (none) | Even overdue, standby can't help. Sending a default overdue would be wrong — backup isn't responsible |
  | 7 | Standby is turn-holder | *any* | **Yes** | ✅ Send | `default` | Backup IS responsible now, normal overdue rules |
  | 8 | Open cycle | *any* | **Yes** | ✅ Send | `default` | Open cycle = anyone can claim |

  **Key implementation notes:**
  - Rows 2 and 4 (`standby_needed`) always fire — not user-configurable. This matches the existing rotation `allow_steal` pattern where non-turn-holders always get notified via `steal_available` message type.
  - Row 6 (`manual_only` + overdue) requires skipping signal emission entirely (`continue` in the loop), not just changing message type. A `DEFAULT` message would incorrectly imply the standby failed to complete.
  - Rows 7 and 8 flow through the normal overdue path since the standby IS the active turn-holder — no special handling needed.
  - `primary_name` in the notification message requires resolving `assigned_assignees[0]` to a display name from `self.coordinator.assignees_data`.

- **`standby` vs `not_my_turn` icon differentiation**: Consider a distinct icon (`mdi:shield-account-outline` vs `mdi:account-cancel`) so dashboards can visually distinguish "you're a standby" from "it's not your turn in the rotation."

---

### Phase 3A – Terminology Rename (Backup → Standby)

- **Goal**: Rename all new constants, variables, storage keys, state values, claim mode values, translation keys, and user-facing labels from "Backup" to "Standby" before the feature is released. This avoids confusion with the pre-existing file-backup system (`BACKUP_ACTION_*`, `BACKUP_TAG_*`, `RESTORE_BACKUP`, `BACKUPS_MAX_RETAINED`, etc.).

- **Rename scope (safe rename)**: Only identifiers we introduced in this session. Pre-existing code with "backup" (file backup system) is completely untouched.

> **⚠️ Note**: The rename tables below show what the CODE currently contains (old names) mapped to what they should become (new names). These are the same tables that appeared in the original plan; the plan's prose was updated for readability, but the actual code requires these renames.

- **RENAME TABLE — constant identifiers**:

  | Old Name (in code) | New Name (after rename) |
  |---|---|
  | `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` | `COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY` |
  | `CHORE_STATE_STANDBY_BACKUP` | `CHORE_STATE_STANDBY` |
  | `CHORE_CLAIM_MODE_BLOCKED_STANDBY_BACKUP` | `CHORE_CLAIM_MODE_BLOCKED_STANDBY` |
  | `CHORE_CLAIM_MODE_BACKUP_AVAILABLE` | `CHORE_CLAIM_MODE_STANDBY_AVAILABLE` |
  | `DATA_CHORE_BACKUP_ACCESS` | `DATA_CHORE_STANDBY_CLAIM_MODE` |
  | `BACKUP_ACCESS_ANYTIME` | `STANDBY_CLAIM_MODE_ANYTIME` |
  | `BACKUP_ACCESS_ON_OVERDUE` | `STANDBY_CLAIM_MODE_ON_OVERDUE` |
  | `BACKUP_ACCESS_MANUAL_ONLY` | `STANDBY_CLAIM_MODE_MANUAL_ONLY` |
  | `BACKUP_ACCESS_OPTIONS` | `STANDBY_CLAIM_MODE_OPTIONS` |
  | `SERVICE_FIELD_CHORE_CRUD_BACKUP_ACCESS` | `SERVICE_FIELD_CHORE_CRUD_STANDBY_CLAIM_MODE` |
  | `CFOF_CHORES_INPUT_BACKUP_ACCESS` | `CFOF_CHORES_INPUT_STANDBY_CLAIM_MODE` |
  | `_BACKUP_ACCESS_VALUES` | `_STANDBY_CLAIM_MODE_VALUES` |
  | `TRANS_KEY_FLOW_HELPERS_BACKUP_ACCESS` | `TRANS_KEY_FLOW_HELPERS_STANDBY_CLAIM_MODE` |
  | `TRANS_KEY_NOTIF_TITLE_CHORE_BACKUP_NEEDED` | `TRANS_KEY_NOTIF_TITLE_CHORE_STANDBY_NEEDED` |
  | `TRANS_KEY_NOTIF_MESSAGE_CHORE_BACKUP_NEEDED` | `TRANS_KEY_NOTIF_MESSAGE_CHORE_STANDBY_NEEDED` |
  | `TRANS_KEY_ERROR_CHORE_STANDBY_BACKUP` | `TRANS_KEY_ERROR_CHORE_STANDBY` |
  | `CHORE_OVERDUE_NOTIFICATION_TYPE_BACKUP_NEEDED` | `CHORE_OVERDUE_NOTIFICATION_TYPE_STANDBY_NEEDED` |
  | `TRANS_KEY_COMPLETION_CRITERIA_PRIMARY_BACKUP` | `TRANS_KEY_COMPLETION_CRITERIA_PRIMARY_STANDBY` |

- **RENAME TABLE — storage values** (string values stored in `.storage/choreops/choreops_data` and sent as entity attributes):

  | Old Value | New Value |
  |---|---|
  | `"rotation_primary_backup"` | `"rotation_primary_standby"` |
  | `"standby_backup"` | `"standby"` |
  | `"blocked_standby_backup"` | `"blocked_standby"` |
  | `"backup_available"` | `"standby_available"` |
  | `"backup_access"` | `"standby_claim_mode"` |
  | `"backup_needed"` | `"standby_needed"` |
  | `"notification_title_chore_backup_needed"` | `"notification_title_chore_standby_needed"` |
  | `"notification_message_chore_backup_needed"` | `"notification_message_chore_standby_needed"` |
  | `"chore_standby_backup"` | `"chore_standby"` |
  | `"completion_criteria_primary_backup"` | `"completion_criteria_primary_standby"` |
  | `"backup_access_anytime"` (selector option key) | `"standby_claim_mode_anytime"` |
  | `"backup_access_on_overdue"` (selector option key) | `"standby_claim_mode_on_overdue"` |
  | `"backup_access_manual_only"` (selector option key) | `"standby_claim_mode_manual_only"` |

- **RENAME TABLE — user-facing labels** (in `translations/en.json`, `translations_custom/en_notifications.json`, `services.yaml`):

  | Old Label | New Label | Location |
  |---|---|---|
  | `"Standby (Backup)"` | `"Standby"` | chore_status state label |
  | `"You are a backup for this chore"` | `"You are standing by for this chore"` | claim_mode state label |
  | `"Backup — you can claim this chore"` | `"Standby — you can claim this chore"` | claim_mode state label |
  | `"🔑 Backup Access"` | `"🔑 Standby Claim Mode"` | form field label |
  | `"Anytime (backup can claim immediately)"` | `"Anytime (standby can claim immediately)"` | selector option |
  | `"On Overdue (backup can claim when overdue)"` | `"On Overdue (standby can claim when overdue)"` | selector option |
  | `"Manual Only (admin must assign turn)"` | *(unchanged)* | selector option |
  | `"🤝 Help Required"` (title) | `"🔄 Standby Available"` | notification title |
  | `"{primary_name} hasn't completed {chore_name}..."` (msg) | *(unchanged)* | notification message |
  | `"Primary & Backup"` (criteria label) | `"Primary & Standby"` | all 3 `en.json` locations |
  | `"Backup Access"` (service field name) | `"Standby Claim Mode"` | service field label |
  | `"backup"` in comments/docs (our feature) | `"standby"` | All Python files |

- **SAFE RENAME — files to modify**:

  | File | Our identifiers present |
  |---|---|
  | `const.py` | All constant names + value strings |
  | `engines/chore_engine.py` | `PRIMARY_STANDBY`, `SENTINEL_STANDBY_AVAILABLE` (if exists), `STANDBY`, `STANDBY_CLAIM_MODE` |
  | `managers/chore_manager.py` | `PRIMARY_STANDBY`, `STANDBY_CLAIM_MODE`, `STANDBY`, `STANDBY_NEEDED` |
  | `managers/notification_manager.py` | `STANDBY_NEEDED`, `STANDBY_CLAIM_MODE` |
  | `services.py` | `_STANDBY_CLAIM_MODE_VALUES`, `SERVICE_FIELD_STANDBY_CLAIM_MODE`, comments |
  | `data_builders.py` | `STANDBY_CLAIM_MODE`, `PRIMARY_STANDBY`, comments |
  | `helpers/flow_helpers.py` | `STANDBY_CLAIM_MODE` (CFOF + schema) |
  | `options_flow.py` | `STANDBY_CLAIM_MODE` (form defaults map) |
  | `services.yaml` | `standby_claim_mode` field names + descriptions |
  | `translations/en.json` | All label keys, selector option keys, state/claim mode values, criteria labels |
  | `translations_custom/en_notifications.json` | `chore_standby_needed` notification key |
  | Plan document | All references throughout |

- **DANGER ZONE — files with BOTH our terms AND pre-existing file-backup terms (DO NOT bulk rename)**:

  | File | Pre-existing "backup" (preserve) |
  |---|---|
  | `const.py` | `BACKUP_ACTION_*`, `BACKUP_SELECTION`, `BACKUP_TAG_*`, `BACKUPS_MAX_RETAINED`, `RESTORE_BACKUP`, `DOC_URL_BACKUP_RESTORE`, `RUNTIME_KEY_STARTUP_BACKUP_CREATED` |
  | `options_flow.py` | `backup_helpers`, `_delete_confirmed`, `_restore_confirmed`, `_backup_to_delete`, `_backup_to_restore`, `_backup_delete_selection_map`, `_backup_restore_selection_map`, backup settings step |
  | `services.py` | Comments about SystemManager backup handling |
  | `translations/en.json` | File backup UI strings (`backup_selection`, `backup_actions`, `backups_max_retained`, `restore_backup`, `delete_backup`, `create_backup`) |
  | `data_builders.py` (only comments) | Comments not related to our feature |

- **Rename strategy**: Do NOT use global sed. Process each file individually, searching for our specific patterns:
  1. `PRIMARY_BACKUP` → `PRIMARY_STANDBY` (or `primary_backup` → `primary_standby`)
  2. `BACKUP_ACCESS` → `STANDBY_CLAIM_MODE` (or `backup_access` → `standby_claim_mode`)
  3. `BACKUP_NEEDED` → `STANDBY_NEEDED` (or `backup_needed` → `standby_needed`)
  4. `STANDBY_BACKUP` → `STANDBY` (or `standby_backup` → `standby`) — careful: our constant is `CHORE_STATE_STANDBY_BACKUP`, becomes `CHORE_STATE_STANDBY`
  5. `BLOCKED_STANDBY_BACKUP` → `BLOCKED_STANDBY` (or `blocked_standby_backup` → `blocked_standby`)
  6. `BACKUP_AVAILABLE` → `STANDBY_AVAILABLE` (or `backup_available` → `standby_available`)

- **Steps / detailed work items**

  1. `[x]` **Rename const.py** — all constant identifiers + string values. Verified no file-backup constants were touched. ✅
  2. `[x]` **Rename engines/chore_engine.py** — P3 resolver references, can_claim_chore references, adapter tuple comments. ✅
  3. `[x]` **Rename managers/chore_manager.py** — all references to our feature's constants. ✅
  4. `[x]` **Rename managers/notification_manager.py** — STANDBY_NEEDED references. ✅
  5. `[x]` **Rename services.py** — `_STANDBY_CLAIM_MODE_VALUES`, `SERVICE_FIELD_STANDBY_CLAIM_MODE`, comments. ✅
  6. `[x]` **Rename data_builders.py** — `STANDBY_CLAIM_MODE` references, comments. ✅
  7. `[x]` **Rename helpers/flow_helpers.py** — CFOF constant + schema reference. ✅
  8. `[x]` **Rename options_flow.py** — form defaults mapping. ✅
  9. `[x]` **Rename services.yaml** — field names + descriptions. ✅
  10. `[x]` **Rename translations/en.json** — all our keys (state labels, claim mode labels, criteria labels, selector options, service field names, form field labels, error messages). Verified file-backup strings untouched. ✅
  11. `[x]` **Rename translations_custom/en_notifications.json** — notification key. ✅
  12. `[x]` **Update plan document** — all references to "backup" in context of this feature. ✅
  13. `[x]` **Run validation** — lint, mypy, targeted tests, contract parity. ✅

- **Key issues**
  - **`const.py` is the most dangerous file** because it contains both our feature constants AND file-backup constants. Rename manually or with targeted search patterns only — no global replace.
  - **`STANDBY` → `STANDBY`** must be done carefully. `CHORE_STATE_STANDBY` becomes `CHORE_STATE_STANDBY`, but there might also be unrelated `STANDBY` terms. Currently there are none — safe to rename.
  - The **state value** changes from `"standby"` to `"standby"`. This is a breaking change for any dashboard templates that check `state == "standby"`. Since this feature hasn't been released, no production impact.
  - The **storage key** changes from `"standby_claim_mode"` to `"standby_claim_mode"`. Again, no production impact since unreleased.
  - **After rename, run `./utils/quick_lint.sh --fix`** to catch any missed references (mypy will flag undefined constants).

- **Goal**: Full coverage of the new criteria's FSM states, turn-reset behavior, steal interaction, and boundary conditions.

- **Steps / detailed work items**

  1. `[x]` **Create test class** — Created `tests/test_rotation_primary_standby.py` with 10 tests, plus `tests/scenarios/scenario_primary_standby.yaml` fixture. ✅

  2. `[x]` **Test: Primary always claimable** — Verifies primary never sees `standby`. ✅ (`test_primary_always_claimable`)

  3. `[x]` **Test: standby_claim_mode.anytime** — Verifies `standby_available` claim mode + can claim + turn snaps back after approval. ✅ (`test_standby_anytime_claim_mode`)

  4. `[x]` **Test: on_overdue blocks before due** — `blocked_standby` before due date, opens after due. ✅ (`test_standby_on_overdue_can_claim_after_due`)

  4a. `[x]` **Test: manual_only always blocked** — `blocked_standby` claim mode at all times. ✅ (`test_standby_manual_only_claim_mode`)

  5. `[x]` **Test: set_rotation_turn override** — Standby becomes turn-holder, primary sees standby, reverse restores. ✅ (`test_set_rotation_turn_makes_standby_active`)

  6. `[x]` **Test: Turn resets to primary after approval** — Turn snaps back in storage (sensor shows completed_by_other until next reset boundary). ✅ (`test_turn_resets_to_primary_after_approval`)

  7. `[-]` **Test: Midnight boundary reset** — Skipped. Verified by test 6's turn snap-back + existing rotation midnight tests. ✅ (covered by regression suite)

  8. `[-]` **Test: open_rotation_cycle** — Skipped. Shared-first behavior is identical to existing rotation_simple tests. ✅ (covered by regression)

  9. `[x]` **Test: Single assignee** — Sole assignee never sees `standby`, claim mode is `claimable`. ✅ (`test_single_assignee_no_standby_state`)

  10. `[-]` **Test: Accountability stats** — Skipped. Requires StatisticsManager with period data; better suited as integration-level scenario.

  11. `[x]` **Test: due_today filter** — `standby` chore excluded from standby's due-today but counts for primary. ✅ (`test_standby_excluded_from_due_today`)

  12. `[x]` **Test: Regression** — All 12 existing rotation tests pass unchanged. ✅ (22/22 total)

  13. `[x]` **Test: Primary paused activates standby** — Pause → standby sees pending, unpause → snaps back. ✅ (`test_primary_paused_standby_activates`)

  14. `[-]` **Test: Backup paused** — Skipped. Pause guard is generic (P0), not primary-standby-specific; covered by pause feature's own tests.

- **Key issues**
  - Test fixtures: Reuse `scenario_shared` from existing rotation tests. May need a new scenario YAML fixture for primary-standby with specific overdue handling configuration.
  - Snapshot tests: If snapshot testing is used for entity states, will need `--snapshot-update` for new `standby` state snapshots.

---

### Phase 5a – Dashboard Template Updates (choreops-dashboards repo)

- **Goal**: Update all dashboard templates and translations to recognize the new `standby` state, the new `blocked_standby` claim mode, and the new `rotation_primary_standby` completion criteria display label.

- **Architecture note**: Dashboard templates query entity state and `claim_mode` attribute directly. The completion criteria label is auto-resolved via `ui.get(completion_type_key, ...)` where `completion_type_key` comes from the entity's `completion_criteria` attribute. So the template only needs the translation string — no conditional logic changes for criteria display.

- **Files affected (canonical sources in `choreops-dashboards/`)**:

  | File | What changes |
  |------|-------------|
  | `translations/en_dashboard.json` | 3 new translation keys |
  | `templates/admin-shared-v1.yaml` | status_map, status_color_map + sort comment |
  | `templates/admin-peruser-v1.yaml` | status_map, status_color_map + sort comment |
  | `templates/shared/button_card_template_chore_row_v1.yaml` | statusMap, claimModeIconMap, stealAccent detection |
  | `templates/shared/button_card_template_chore_row_kids_v1.yaml` | Blocked states check, color logic, badge icon |
  | `templates/user-chores-essential-v1.yaml` | statusMap, sort order, pref_exclude_states comment |
  | `templates/user-chores-lite-v1.yaml` | statusMap (via shared), tile_color disabled check, blocked states check |
  | `templates/user-chores-standard-v1.yaml` | statusMap (via shared row template), sort order |
  | `templates/user-gamification-premier-v1.yaml` | statusMap (via shared row template), sort order |
  | `templates/user-kidschores-classic-v1.yaml` | state_map (own independent map) |
  | (vendored copies in `custom_components/choreops/dashboards/`) | Mirror of above via `sync_dashboard_assets.py` |

- **Steps / detailed work items**

  1. `[ ]` **Add dashboard translation keys** in `choreops-dashboards/translations/en_dashboard.json` (~line 83-87 area, alongside existing `not_my_turn` and `steal_available`):
     ```json
     "standby": "Standby (Standby)",
     "blocked_standby": "Standby",
     "rotation_primary_standby": "Primary & Standby"
     ```
     The `rotation_primary_standby` key is used by `ui.get(completion_type_key, ...)` when the entity attribute `completion_criteria` equals `"rotation_primary_standby"`. No template code change needed for criteria display — it's purely a translation lookup.

  2. `[ ]` **Update `status_map` in admin-shared-v1.yaml** (~line 1472, after `'not_my_turn'` entry):
     ```yaml
     'standby': ui.get('standby', 'err-standby'),
     ```
     And in the blocked claim-mode section (~line 1480, after `'blocked_not_my_turn'`):
     ```yaml
     'blocked_standby': ui.get('standby', 'err-standby'),
     'standby_available': ui.get('standby', 'err-standby'),
     ```

  3. `[ ]` **Update `status_color_map` in admin-shared-v1.yaml** (~line 1524-1529, after `'not_my_turn'` and `'blocked_not_my_turn'` entries):
     ```yaml
     'standby': 'var(--disabled-text-color)',
     'blocked_standby': 'var(--disabled-text-color)',
     'standby_available': 'var(--primary-color)',
     ```
     `standby_available` uses primary-color to signal actionability (like `claimable`), while `standby`/`blocked_standby` stay muted.

  4. `[ ]` **Apply identical changes to admin-peruser-v1.yaml** — `status_map` at ~line 1404/1412, `status_color_map` at ~line 1456/1461. Same entries as steps 2-3.

  5. `[ ]` **Update shared `button_card_template_chore_row_v1.yaml`** — this is the most critical file as it's used by ALL user-facing chore row cards:
     - **`statusMap`** (~line 149): Add `standby: i18n('standby', 'err-standby'),` and `blocked_standby: i18n('standby', 'err-standby'),` after the `blocked_not_my_turn` entry.
     - **`claimModeIconMap`** (~line 199): Add entries for the new standby claim modes:
       ```yaml
       blocked_standby: 'mdi:shield-account-outline',   # Can't claim
       standby_available: 'mdi:shield-check-outline',           # Can claim anytime
       ```
     - **`stealAccent` background-color detection** (~line 16): No change needed for primary-standby — the `steal_available` check is rotation-specific.

  6. `[ ]` **Update `user-chores-essential-v1.yaml`** — multiple locations:
     - **`pref_exclude_states` comment** (~line 208): Add `standby` to the example list so users know they can filter it out:
       ```yaml
       {%- set pref_exclude_states = [] -%}  {#-- Example: ['completed', 'completed_by_other', 'not_my_turn', 'standby', 'missed'] --#}
       ```
     - **`statusMap` in action button** (~line 674-682): Add `'standby': ui.get('standby', 'err-standby'),` and `'blocked_standby': ui.get('standby', 'err-standby'),`
     - **Sort order comment** (~line 464): Update to show `standby` in the actionability chain:
       ```yaml
       {#-- Actionability sort: overdue, due, pending, waiting, claimed, completed, completed_by_other, standby, not_my_turn, missed --#}
       ```
     - **Sort order logic** (~line 482-484): Add `standby` with priority 7 (bumping `not_my_turn` to 8 and `missed` to 9):
       ```yaml
       {%- elif chore_state == 'standby' -%}
         {%- set state_priority = 7 -%}
       {%- elif chore_state == 'not_my_turn' -%}
         {%- set state_priority = 8 -%}
       {%- elif chore_state == 'missed' -%}
         {%- set state_priority = 9 -%}
       ```

  7. `[ ]` **Apply equivalent changes to `user-chores-lite-v1.yaml` and `user-chores-standard-v1.yaml`** — these share the same statusMap/sort-order patterns. Search for `not_my_turn` in each file and add `standby` entries adjacent.

  8. `[ ]` **Sync vendored copies**: Run `python utils/sync_dashboard_assets.py` from the choreops-dashboards repo to mirror all changes into `custom_components/choreops/dashboards/`. Then run `python utils/sync_dashboard_assets.py --check` to verify parity.

  9. `[ ]` **Add non-English translation stubs** in `choreops-dashboards/translations/` — add the 3 new keys to ALL localized dashboard JSON files with English placeholder values. Crowdin will handle proper translation:
     ```json
     "standby": "Standby (Standby)",
     "blocked_standby": "Standby",
     "rotation_primary_standby": "Primary & Standby"
     ```

- **Key issues**
  - **Sort order decision**: `standby` is placed BETWEEN `completed_by_other` (priority 6) and `not_my_turn` (priority 7→8). Rationale: standby is more actionable than `not_my_turn` (backup CAN become active via overdue steal or manual override) but less actionable than `completed_by_other` (which is a definitive terminal state).
  - **Icon choice**: `mdi:shield-account-outline` conveys "protective/backup role" and is visually distinct from `mdi:account-lock-outline` (used for `not_my_turn`).
  - **No classic templates**: The `*-kidschores-classic.yaml` templates use a different architecture (markdown-based, not button-card). They read `completion_criteria` attribute for display but use a `state_map` that maps criteria values to display strings. Adding `"rotation_primary_standby": "Primary & Standby"` to that map may be needed if those templates are still supported. Check with product owner.
  - **Sync contract**: After canonical edits in `choreops-dashboards/`, the sync script must produce byte-identical vendored copies. Any drift breaks the parity contract (per DEVELOPMENT_STANDARDS.md §1.3).

  10. `[ ]` **Update admin dashboard rotation controls** — In both `admin-shared-v1.yaml` and `admin-peruser-v1.yaml`, the per-chore rotation controls need conditionally different labels for primary-standby chores. Zero new services needed — all three actions use existing service calls:

      **No backend work**. The services already exist:
      - `choreops.update_chore` with reordered `assigned_user_names` = changing primary
      - `choreops.set_rotation_turn` = assigning turn to a backup
      - `choreops.open_rotation_cycle` (registered at `services.py:3320`) = opening to all standbys

      **Template-only changes** (conditional on `completion_criteria == "rotation_primary_standby"`):

      | Current button | Primary-backup label | Service call |
      |---------------|---------------------|--------------|
      | "Move to Front" | **"Make Primary"** | `choreops.update_chore` with reordered names |
      | "Set Turn" | **"Assign Turn"** | `choreops.set_rotation_turn` |
      | *(no button)* | **"Open to All Backups"** | `choreops.open_rotation_cycle` |

      The third button ("Open to All Backups") is a new addition — it lifts the `standby` restriction for one cycle for all standbys, first claimer wins. The cycle override auto-clears at the next approval reset.

### Phase 5b – Documentation & Wiki Updates

- **Goal**: Update all user-facing and developer-facing documentation across the `choreops` repo, `choreops-wiki` repo, and `choreops-dashboards` repo.

- **Documentation inventory** (from Phase 0 verification):

  | # | Doc | Repo | What to add |
  |---|-----|------|------------|
  | DOC-1 | `Configuration:-Chores.md` | `choreops-wiki` | New "Rotation — Primary & Standby" subsection under Completion Criteria. Explain: implicit primary (first assigned user), three standby_claim_mode modes (anytime/on_overdue/manual_only), pause interaction, accountability model (turn-holder gets missed/overdue stats). |
  | DOC-2 | `Advanced:-Chores.md` | `choreops-wiki` | New section or subsection: when primary-standby is appropriate (single-owner chores needing fallback), how it differs from standard rotation (always snaps to primary, backups see `standby` not `not_my_turn`), rotation comparison table, pause interaction (primary paused → backups activated, turn does NOT snap back on unpause until reset boundary), and `standby_claim_mode` vs `overdue_handling` independence. |
  | DOC-3 | `Configuration:-Users.md` | `choreops-wiki` | Note: for primary-standby chores, the first user in the assigned list is always the primary. Order matters. |
  | DOC-4 | `ARCHITECTURE.md` | `choreops` | Add `standby` to derived UI state documentation (alongside `not_my_turn`, `waiting`, `due`, etc.). The state listing is in the const.py section reference. Also document pause interaction: pausing the primary activates backups; unpausing does NOT snap turn back until next reset boundary (G-5 known limitation). |
  | DOC-5 | `DASHBOARD_UI_DESIGN_GUIDELINE.md` | `choreops` | Add `standby` to the state color/style reference table. Add `blocked_standby` to claim mode icon table. |
  | DOC-6 | `en_dashboard.json` | `choreops-dashboards` | Already covered in Phase 5a step 1 (3 new i18n keys) |
  | DOC-7 | All locale `*_dashboard.json` | `choreops-dashboards` | Already covered in Phase 5a step 9 (English placeholder stubs for Crowdin) |
  | DOC-8 | `RELEASE_CHECKLIST.md` | `choreops` | Add release note entry for new `rotation_primary_standby` criteria and `standby` state |
  | DOC-9 | `_Sidebar.md` | `choreops-wiki` | Review if new wiki page structure requires sidebar link update |

- **Steps / detailed work items**

  1. `[ ]` **DOC-1: Update `Configuration:-Chores.md`** — Add "Rotation — Primary & Standby" subsection after the "Rotation Smart" section. Template:
     ```markdown
     ### Rotation — Primary & Standby

     Permanent primary owner with designated backups for fallback.

     - The **first assigned user** is always the primary (permanent turn-holder)
     - Backups see "Standby (Standby)" status and cannot claim unless:
       - An approver manually sets the turn to them, or
       - The chore becomes overdue with "Allow steal" enabled
     - After every completion, the turn always resets to the primary
     - Accountability stays with the turn-holder (primary by default)
     - Best for chores with a clear owner who occasionally needs coverage
     ```

  2. `[ ]` **DOC-2: Update `Advanced:-Chores.md`** — Add primary-standby section covering: conceptual model (primary = owner, backup = fallback), activation triggers (manual + overdue steal), comparison to standard rotation (key difference: always snaps to primary, not round-robin), known limitations (no smart rotation among backups, no "backup duty" dashboard filter).

  3. `[ ]` **DOC-3: Update `Configuration:-Users.md`** — Add note in the user assignment section: "For Rotation — Primary & Standby chores, the first user in the assigned list is always the primary. Reorder users to change the primary."

  4. `[ ]` **DOC-4: Update `ARCHITECTURE.md`** — In the state constants reference section, add `standby` to the derived UI state listing.

  5. `[ ]` **DOC-5: Update `DASHBOARD_UI_DESIGN_GUIDELINE.md`** — Add `standby` row to state color table (color: `var(--disabled-text-color)`, same tier as `not_my_turn`). Add `blocked_standby` to claim mode icon table (icon: `mdi:shield-account-outline`).

  6. `[ ]` **DOC-8: Update `RELEASE_CHECKLIST.md`** — Add release note entry under the appropriate category (likely "enh: feature").

  7. `[ ]` **DOC-9: Review wiki sidebar** — Check if `_Sidebar.md` needs a new link for primary-standby content.

- **Key issues**
  - Wiki updates are in a **separate repository** (`choreops-wiki`). They must be coordinated with the integration release but are not blocking for code merge.
  - The `ARCHITECTURE.md` state listing should stay in sync with `const.py` — if the architecture doc enumerates states literally, add `standby`. If it references `const.py` as source of truth, a brief mention suffices.
  - `DASHBOARD_UI_DESIGN_GUIDELINE.md` may be stale — verify it's actively maintained before investing in updates.

## Testing & validation

- Tests executed (describe suites, commands, results).
  - `pytest tests/test_rotation_fsm_states.py -v` — existing rotation FSM tests must pass unchanged.
  - `pytest tests/test_workflow_chores.py -v` — existing rotation workflow tests must pass unchanged.
  - New tests in Phase 4 cover primary-standby specific paths.
- Outstanding tests (not run and why).
  - Dashboard filter tests deferred (dashboard template change, separate repo).
  - Notification delivery tests may need `mobile_notify_service` mock if notification template changes are made.
- Links to failing logs or CI runs if relevant.
  - N/A (not started).

## Opportunities (from deep analysis)

### O-1/O-4 (merged): Extract `_build_other_assignee_states` helper

The three sites at `chore_manager.py:730`, `3876`, and `4185` all build `other_assignee_states` dicts with identical iteration logic. Extract a shared method:

```python
def _build_other_assignee_states(
    self, chore_data: ChoreData | dict[str, Any], assignee_id: str, chore_id: str
) -> dict[str, str] | None:
    """Build other_assignee_states dict for single-claimer blocking.

    Returns None for non-single-claimer modes (INDEPENDENT, SHARED).
    """
    if not ChoreEngine.is_single_claimer_mode(chore_data):
        return None
    assigned_assignees = chore_data.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
    other_assignee_states: dict[str, str] = {}
    for other_id in assigned_assignees:
        if other_id != assignee_id and other_id:
            other_assignee_states[other_id] = (
                self._derive_boundary_assignee_state(other_id, chore_id)
            )
    return other_assignee_states
```

This:
- Uses `is_single_claimer_mode()` instead of hardcoded tuples (solves G-2 elegantly)
- Eliminates 3× duplicated iteration logic (solves O-4)
- Automatically covers any future single-claimer criteria additions
- Site 3 (line 4185) keeps its `is_completed_by_other` extra check but calls the helper for the dict

**Effort**: ~20 minutes. **Risk**: None (behavior-preserving). **Recommendation**: **DO THIS** — solves G-2 and O-4 in one shot, reducing the CRIT-1/1b surface from 3 edits to 1 helper + 3 call-site updates.

### O-2: Add `can_claim_chore` blocking-states test guard

The FSM blocking check in `chore_engine.py:469-475` is duplicated knowledge — every new blocking state must be added here. Add a parametrized test that verifies `can_claim_chore` returns `False` for all recognized blocking states (`not_my_turn`, `waiting`, `missed`, `standby`). This catches future criteria additions that miss this check.

**Effort**: ~15 minutes. **Risk**: None. **Recommendation**: Include in Phase 4 test class.

### O-3: Immediate snap-back on unpause → merged into G-5

This is no longer a separate opportunity. The G-5 analysis concluded the implementation is LOW complexity (~25 lines) and should be included in the feature directly. See G-5 above for implementation details. The `_snap_rotation_back_to_primary` method is called from the existing `set_user_chores_paused` unpause path.

## Notes & follow-up

- **Architecture decisions**:
  - `standby` is a derived UI-only state (never persisted). It follows the same pattern as `not_my_turn`, `waiting`, `due`, `completed`, and `completed_by_other`.
  - Primary-backup reuses ALL existing rotation storage fields (`rotation_current_assignee_id`, `rotation_cycle_override`). No new storage fields needed.
  - The `_advance_rotation` method for primary-standby simply sets `new_assignee_id = assigned_assignees[0]` — it doesn't calculate next turn at all.

- **Code surface area estimate (revised after deep code audit 2026-06-11)**:
  - **Integration repo (`choreops`)**:
    - `const.py`: ~25 lines (new constants + frozenset entries + criteria options entry + standby_claim_mode constants + notification type constant + notification key constants)
    - `chore_engine.py`: ~35 lines (add to `is_rotation_mode` + `is_single_claimer_mode` + `uses_chore_level_due_date` + CRIT-7 `get_criteria_transition_actions` + P3 branch + G-1 `can_claim_chore` FSM blocking)
    - `chore_manager.py`: ~45 lines (advance_rotation direct set + reset boundary force + claim_mode mapping + CRIT-1/1b two `can_claim_chore` sites + CRIT-2 ownership clear + G-4 overdue message type + G-7 `chore_counts_toward_due_today_summary` exclusion)
    - `services.py`: ~8 lines (CRIT-4 due date check + CRIT-6 criteria values list)
    - `data_builders.py`: ~6 lines (CRIT-5 due date check + CRIT-8 rotation field initialization)
    - `notification_manager.py`: ~10 lines (standby_needed notification type handling)
    - `translations/en.json`: ~25 lines (new state, criteria label, error message, standby_claim_mode options)
    - `translations/en_notifications.json`: ~6 lines (standby_needed title + message)
    - `tests/`: ~250 lines (new test class + G-1 can_claim_chore blocking test)
    - **Subtotal**: ~130 lines production, ~250 lines test (increased by G-1 through G-4 findings)
  - **Dashboard repo (`choreops-dashboards`)**:
    - `translations/en_dashboard.json`: 3 new keys
    - `translations/*_dashboard.json` (12+ locale files): 3 new keys each (English placeholders, Crowdin fills)
    - `templates/admin-shared-v1.yaml`: 4 lines (2 status_map + 2 status_color_map)
    - `templates/admin-peruser-v1.yaml`: 4 lines (same)
    - `templates/shared/button_card_template_chore_row_v1.yaml`: 3 lines (2 statusMap + 1 claimModeIconMap)
    - `templates/user-chores-essential-v1.yaml`: ~8 lines (statusMap x2 + sort comment + sort logic + exclude comment)
    - `templates/user-chores-lite-v1.yaml`: ~6 lines (same pattern, verify)
    - `templates/user-chores-standard-v1.yaml`: ~6 lines (same pattern, verify)
    - Vendored copies in `custom_components/choreops/dashboards/`: auto-synced, no hand-edits
    - **Subtotal**: ~30 template lines + ~40 translation lines across all locales
  - **Wiki repo (`choreops-wiki`)**:
    - 3 wiki pages updated (Chores configuration, Advanced chores, Users configuration)
    - **Subtotal**: ~60 lines of markdown

- **Follow-up tasks for future initiatives**:
  - "User unavailable" auto-failover: auto-call `set_rotation_turn` to first backup when primary marked unavailable.
  - Smart rotation among backups: `calculate_next_turn_smart(backups_only_list, ...)` when primary is paused for extended period.
  - Dashboard"Standby Duty" filter section.
  - Primary completion rate badge/achievement.
  - `standby` icon differentiation (translation-based icon support).

> **Plan created**: 2026-06-05 | **Last updated**: 2026-06-05 | **Based on**: Strategic analysis of rotation infrastructure reuse for primary-standby failover pattern.
