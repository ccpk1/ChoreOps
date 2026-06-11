# Initiative Plan: Primary & Backup Chore Type (Failover Rotation)

## Initiative snapshot

- **Name / Code**: `rotation_primary_backup` — Primary & Backup Chore Type
- **Target release / milestone**: TBD (post-v0.5.0+)
- **Owner / driver(s)**: TBD
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                   | Description                                                   | % complete | Quick notes                                                          |
| ------------------------------ | ------------------------------------------------------------- | ---------- | -------------------------------------------------------------------- |
| Phase 0 – Verification pass    | Assumption check, hardcoded list inventory, doc inventory     | ✅ 100%    | Found 6 CRIT hardcoded tuples + 9 doc files to update                |
| Phase 1 – Foundation           | Constants, type defs, criteria registration, CRIT fixes       | 0%         | 1 new criteria + 1 new derived state + 6 hardcoded list additions    |
| Phase 2 – Core implementation  | Engine FSM, manager advance/reset (refined), state resolution | 0%         | Narrow changes in `_advance_rotation` + P3 resolver + reset boundary  |
| Phase 3 – UX & notifications   | Translations, standby_backup state, overdue notification      | 0%         | Reuse steal alert wording; new translation keys                      |
| Phase 4 – Testing              | Rotation FSM tests, boundary tests, regression                | 0%         | Follow `test_rotation_fsm_states.py` patterns                        |
| Phase 5a – Dashboard templates | Status maps, icons, sort order, i18n (choreops-dashboards)    | 0%         | 9 template files + 12+ translation files touched                     |
| Phase 5b – Docs & wiki         | 9 documentation files across 3 repos                          | 0%         | Wiki, architecture, design guide, release checklist                  |

1. **Key objective** – Introduce a `rotation_primary_backup` completion criteria where the first assigned user is always the primary (permanent turn-holder default). Backups see `standby_backup` state and can claim based on the `backup_access` field: `anytime` (claim immediately), `on_overdue` (claim after due date), or `manual_only` (admin must intervene). Backup activation also occurs when the primary is paused or when an admin uses `set_rotation_turn`. After every completion, the turn always resets to the primary.

2. **Summary of recent work** – Strategic analysis completed 2026-06-05. All design decisions captured (see Decisions section). 90%+ code reuse from existing rotation infrastructure confirmed.

3. **Next steps (short term)** – Phase 1: Add `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` constant, `CHORE_STATE_STANDBY_BACKUP` derived state, register in criteria options and engine adapters.

4. **Risks / blockers**
   - `standby_backup` is a new derived UI state — must be added to `CHORE_UI_ASSIGNEE_STATES` and all state-allowlist frozensets that need to include it.
   - Reset-boundary force-to-primary must not interfere with `rotation_cycle_override` (open cycle) or manual turn overrides that are mid-cycle.
   - Notification wording for backup activation must not confuse users — backup should understand they are helping, not taking over permanently.
   - **Pause coexistence**: The user chore pause feature (shipped v0.5.0+) adds `paused`/`blocked_paused` states, `_is_chore_paused_for_assignee()` helper, and `_advance_rotation_past_paused_assignee()` method. Primary-backup's reset-boundary force-to-primary is the only surface needing explicit pause awareness. See Phase 2 key issues for the full coexistence audit.

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
     - D-1: Accountability stays with turn-holder (existing rotation model). Backup turn-holders are not penalized with missed/overdue when chore opens to them on overdue.
     - D-2: Backup claim gating uses the `backup_access` field — three modes: `anytime` (immediate), `on_overdue` (after due date), `manual_only` (admin intervention required).
     - D-3: Primary is implicit — `assigned_user_ids[0]`. No explicit `primary_assignee_id` field. Guard rails via documentation and validation.
     - D-4: `backup_access` field is independent of `overdue_handling`. Claim gating and penalty behavior are separate dimensions. Smart rotation among backups deferred to future.
     - D-5: Administrative controls reuse existing services — no new backend endpoints. `update_chore` (reorder assignees) changes the primary. `set_rotation_turn` assigns turn to a backup. `open_rotation_cycle` (already registered as `choreops.open_rotation_cycle`) lifts the standby lock for one cycle. Template-only changes: button labels and one new "Open to All Backups" button.
     - G-3/T-4: New derived UI state `standby_backup` for backups who are not the active turn-holder (replaces `not_my_turn` for this criteria only).
     - T-1: Manual turn override does NOT survive approval reset — turn always snaps back to primary at reset boundary.
     - T-5: If no backups are designated (single assignee), the chore operates gracefully. Does NOT auto-convert to `independent`.
     - O-1: "User paused" auto-failover — already implemented via `_advance_rotation_past_paused_assignee()`. Manual turn override deferred.
     - O-2: MVP notification leverages existing steal/due notification infrastructure with narrow wording adjustments.
     - O-3: Dashboard "Backup Duty" filter deferred to follow-up (dashboard template change).
     - O-4: Primary completion rate badge deferred; documented as known gap.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

## Implementation traps (code-verified 2026-06-11)

These were discovered during a detailed audit of the actual code against the plan's assumptions. They must be accounted for during implementation.

### Trap 1: `_advance_rotation` dispatches by `method`, not `completion_criteria`

The plan originally described inserting a `completion_criteria == ROTATION_PRIMARY_BACKUP` early-return before the method dispatch. But the actual method at `chore_manager.py:5113` translates criteria to method inside the `if method == "auto"` block and then dispatches by the resulting `method` value. The primary-backup handler must go **inside** the `"auto"` block as a `elif completion_criteria == ROTATION_PRIMARY_BACKUP` that sets `new_assignee_id = assigned[0]` directly. Phase 2 Step 1 has been updated to reflect this.

### Trap 2: `backup_access.on_overdue` with no due date locks backups out permanently

The P3 resolver gates the overdue window on `due_date is not None and now > due_date`. If a primary-backup chore uses `backup_access = on_overdue` but has no explicit due date (e.g., a daily recurring chore where the due date is computed at runtime), the backup **can never claim** because the overdue window never opens — `standby_backup` is enforced forever. This must be validated against in `data_builders.py`: when `completion_criteria == ROTATION_PRIMARY_BACKUP` and `backup_access == BACKUP_ACCESS_ON_OVERDUE`, require a due date.

### Trap 3: P0 pause guard beats P3 `standby_backup` (correct but subtle)

The pause P0 guard at `chore_manager.py:4129` runs BEFORE `resolve_assignee_chore_state()`. A paused backup sees **`paused`**, not `standby_backup`. This is correct — pause is a stronger administrative state — but it also means: if a backup is paused and later unpaused, they will immediately see `standby_backup` (or the appropriate state for their position in the rotation). If the admin expected them to become the active turn-holder on unpause, they need to check the rotation position first. Document this in the wiki.

### Trap 4: Primary paused → backup becomes active (intentional, must document)

This is the expected behavior per CRIT-2: when the primary is paused, `_advance_rotation_past_paused_assignee()` (line 5854) advances the turn past them in real time, and the next reset boundary's force-to-primary skips them (per the updated Phase 2 Step 2). The backup sees the chore as a **normal required chore** — with due dates, notifications, overdue penalties, and point earnings — just as if they were the primary. This is the desired behavior but must be clearly documented: pausing the primary is the mechanism for activating backups.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 0 – Verification Pass (Assumption Check & Gap Inventory)

**Date**: 2026-06-05 | **Status**: Complete

- **Goal**: Verify every assumption in the plan against actual code paths, identify all hardcoded criteria lists that need updating, catalog documentation touch points.

- **Findings**:

  #### A. Hardcoded criteria lists requiring `rotation_primary_backup` addition

  The following locations hardcode completion criteria tuples and MUST be updated. These were missed in the initial plan draft.

  | # | File | Line | Context | Action |
  |---|------|------|---------|--------|
  | **CRIT-1** | `chore_manager.py` | ~674 | `can_claim_chore` — builds `other_assignee_states` dict for single-claimer blocking | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-2** | `chore_manager.py` | ~4828 | `_remove_name_from_ownership_list` — clears chore-level ownership fields for single-claimer modes | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-3** | `chore_engine.py` | ~578 | `uses_chore_level_due_date` — primary-backup uses chore-level due dates (same as all rotation types) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-4** | `services.py` | ~217 | `_uses_chore_level_due_date` (duplicate of CRIT-3 in services module) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-5** | `data_builders.py` | ~1375 | `_uses_chore_level_due_date` (duplicate of CRIT-3 in data_builders) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-6** | `services.py` | ~735 | `_COMPLETION_CRITERIA_VALUES` — master list of valid completion criteria for service validation | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-7** | `chore_engine.py` | ~1046 | `get_criteria_transition_actions` — `old_is_rotation`/`new_is_rotation` checks. Without this, criteria transitions to/from primary_backup won't initialize/clear rotation fields (`DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID`, `rotation_cycle_override`) | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-8** | `data_builders.py` | ~1853 | `build_chore` — `DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID` initialization only happens for ROTATION_SIMPLE and ROTATION_SMART. New primary_backup chores won't get a turn-holder set on creation | ADD `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` |
  | **CRIT-9** | `chore_manager.py` | ~5086 | `_handle_criteria_transition` — ≥2 assignee validation check for `new_is_rotation`. **Deliberately excluded** primary_backup per T-5 (single assignee allowed). Primary_backup with 1 assignee (primary only, no backups) must work | **Do NOT add** — but verify the transition actions (CRIT-7) still run for single-assignee primary_backup |

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
  | SAFE-13 | `notification_manager.py` | 2655 | Due window notification filtering — uses `is_rotation_mode()` | Covered by step 1.3. Only turn-holder gets notified. Correct for primary_backup. |
  | SAFE-14 | `notification_manager.py` | 2725 | Due reminder notification filtering — uses `is_rotation_mode()` | Same as SAFE-13. |
  | SAFE-15 | `services.py` | 1029-1070 | Rotation service schemas (`set_rotation_turn`, `reset_rotation`, `open_rotation_cycle`) — no criteria-specific validation in schemas | Delegates to ChoreManager which uses `is_rotation_mode()`. Covered. |
  | SAFE-16 | `options_flow.py` | 1120,1435,1595,1673 | Per-assignee field routing — checks `== INDEPENDENT` (not a tuple check) | Primary_backup is not INDEPENDENT, correctly skips per-assignee fields. |
  | SAFE-17 | `flow_helpers.py` | 893-903 | Build chore schema — uses `COMPLETION_CRITERIA_OPTIONS` from const.py | Covered by adding to options list in Phase 1 step 1. |
  | SAFE-18 | `engines/chore_engine.py` | 1171 | `compute_global_chore_state` single-claimer branch — overridden by `resolve_rotation_global_state` for rotation types | Primary_backup enters single-claimer branch then gets overridden by rotation resolver. Safe. |

  #### C. Assumptions verified

  | Assumption | Verification | Result |
  |------------|-------------|--------|
  | `is_rotation_mode()` covers primary_backup | Step 1.3 adds to tuple at line 595 | ✅ Correct, all rotation-aware code paths inherit |
  | `is_single_claimer_mode()` covers primary_backup | Step 1.4 adds to tuple at line 614 | ✅ Correct, all single-claimer code paths inherit |
  | P3 sub-branch placement is safe | New branch inside `is_rotation_mode()` block, BEFORE generic `not_my_turn` return at line 696-705 | ✅ Correct — primary_backup returns `standby_backup`, simple/smart continue to `not_my_turn` |
  | Force-to-primary at reset boundary doesn't break rotation signals | `_advance_rotation` captures `previous_assignee_id` BEFORE modifying `rotation_current_assignee_id` (line ~4968 before ~5028) | ✅ Correct — signal payload has correct previous |
  | No-conflict with `rotation_cycle_override` | `_is_rotation_open_claim_cycle` covers primary_backup via `is_rotation_mode()` | ✅ Correct |
  | `backup_available` claim mode triggers for primary_backup | `get_chore_status_context` resolves via `claim_error_to_claim_mode` mapping from sentinel | ✅ Correct after Phase 2 Step 4 |
  | Completion criteria display label auto-resolves in dashboards | `ui.get(completion_type_key, ...)` where key comes from entity attribute | ✅ Correct — only translation key needed, no template logic |
  | Single-assignee primary-backup doesn't crash | P3 returns `standby_backup` for `assignee_id != current_turn`. With 1 assignee, primary IS turn holder, so condition never true. | ✅ Correct — no standby_backup shown for solo primary |

  #### D. Reset-boundary ordering refinement

  The initial plan placed force-to-primary BEFORE `_advance_rotation`. This would cause `_advance_rotation` to capture `previous_assignee_id = primary` (since turn was already reset). **Correction**: Force-to-primary should run AFTER the `if completed_by_assignee_id:` block but still within the `if new_state == CHORE_STATE_PENDING and reset_approval_period:` scope. This ensures:
  1. If someone completed: `_advance_rotation` captures correct previous (backup), sets new=primary
  2. If nobody completed: force-to-primary runs as a fallback (manual override survived into new cycle)

  Revised placement in `_transition_chore_state`:
  ```python
  if new_state == const.CHORE_STATE_PENDING and reset_approval_period:
      if completed_by_assignee_id:
          rotation_signal_payload = self._advance_rotation(...)

      # Primary-backup: force turn to primary at reset boundary
      # (after _advance_rotation so signal captures correct previous_assignee_id)
      if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == \
              const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
          assigned = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
          if assigned:
              chore_info[const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID] = assigned[0]
  ```

  #### E. Documentation inventory

  Files requiring updates (beyond the plan itself):

  | Doc | What to add |
  |-----|------------|
  | `choreops-wiki/Configuration:-Chores.md` | New "Rotation — Primary & Backup" subsection under Completion Criteria, explaining implicit primary, backup_access modes, pause interaction, and accountability model |
  | `choreops-wiki/Advanced:-Chores.md` | New section or subsection covering primary-backup: when to use, how backup activation works, rotation comparison table, known limitations |
  | `choreops-wiki/Configuration:-Users.md` | Note that for primary-backup chores, first assigned user in list is the primary |
  | `choreops/docs/ARCHITECTURE.md` | Add `standby_backup` to the derived UI state listing if `CHORE_UI_ASSIGNEE_STATES` is documented there |
  | `choreops/docs/DEVELOPMENT_STANDARDS.md` | No change needed — pattern is identical to existing rotation criteria |
  | `choreops/docs/DASHBOARD_UI_DESIGN_GUIDELINE.md` | Add `standby_backup`, `backup_available`, `blocked_standby_backup` to the blocked/exception states table |
  | `choreops/docs/QUALITY_REFERENCE.md` | No change needed unless new quality rule is affected |
  | `choreops-dashboards/translations/en_dashboard.json` | 3 new i18n keys (already in Phase 5a) |
  | `choreops-wiki/_Sidebar.md` | May need link update if new wiki page is created |

- **Key issues**
  - CRIT-1 through CRIT-8 are **mandatory pre-merge requirements**. Missing any of these would cause runtime bugs: `can_claim_chore` would not build `other_assignee_states` for primary-backup chores, breaking single-claimer blocking; `_remove_name_from_ownership_list` would not clear ownership fields correctly; due date lookups would use wrong storage path.
  - The `choreops-wiki` repo is a separate repository — wiki updates must be coordinated with the integration release.
  - reset-boundary ordering (item D) is a subtle but important refinement from the initial plan.

### Phase 1 – Foundation (Constants, Types, Criteria Registration)

- **Goal**: Register the new completion criteria and derived UI state so all downstream code can reference them. Zero behavioral changes — just wiring.

- **Steps / detailed work items**

  1. `[ ]` **Add `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` constant** in `custom_components/choreops/const.py` (~line 1462, after `COMPLETION_CRITERIA_ROTATION_SMART`):
     ```python
     COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP: Final = "rotation_primary_backup"
     ```
     Add to `COMPLETION_CRITERIA_OPTIONS` list (~line 1462-1468) with label `"rotation_primary_backup"`.

  2. `[ ]` **Add `CHORE_STATE_STANDBY_BACKUP` derived UI state** in `custom_components/choreops/const.py` (~line 1864, in the "Derived UI-only states" block after `CHORE_STATE_NOT_MY_TURN`):
     ```python
     CHORE_STATE_STANDBY_BACKUP: Final = "standby_backup"
     ```
     Add to `CHORE_UI_ASSIGNEE_STATES` frozenset (~line 1889).

  3. `[ ]` **Add criteria to `ChoreEngine.is_rotation_mode()`** in `custom_components/choreops/engines/chore_engine.py` (~line 595, return tuple):
     ```python
     return criteria in (
         const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
         const.COMPLETION_CRITERIA_ROTATION_SMART,
         const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
     )
     ```

  4. `[ ]` **Add criteria to `ChoreEngine.is_single_claimer_mode()`** in `custom_components/choreops/engines/chore_engine.py` (~line 614, return tuple):
     ```python
     return criteria in (
         const.COMPLETION_CRITERIA_SHARED_FIRST,
         const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
         const.COMPLETION_CRITERIA_ROTATION_SMART,
         const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
     )
     ```

  5. `[ ]` **Add translation key constant** for the new criteria label in `custom_components/choreops/const.py` (~line 3648 area, near `TRANS_KEY_FLOW_HELPERS_COMPLETION_CRITERIA`):
     ```python
     TRANS_KEY_COMPLETION_CRITERIA_PRIMARY_BACKUP: Final = "completion_criteria_primary_backup"
     ```

  6. `[ ]` **Add validation guard** in `custom_components/choreops/data_builders.py` — the existing `validate_chore_data()` or criteria-transition handler in `_handle_criteria_transition()` (~line 5063) must include `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` in its "requires ≥2 assignees" check (it already checks rotation types via `new_is_rotation` which will pick up the new criteria via `is_rotation_mode()`).

  7. `[ ]` **Add `standby_backup` claim mode constants** in `custom_components/choreops/const.py` (~line 1926, after `CHORE_CLAIM_MODE_BLOCKED_NOT_MY_TURN`):
     ```python
     CHORE_CLAIM_MODE_BLOCKED_STANDBY_BACKUP: Final = "blocked_standby_backup"
     CHORE_CLAIM_MODE_BACKUP_AVAILABLE: Final = "backup_available"
     ```
     Add both to `CHORE_CLAIM_MODES` frozenset.

     **Icons** (verified MDI 7.x):
     - `blocked_standby_backup`: `mdi:shield-account-outline` — "you're a backup, can't claim"
     - `backup_available`: `mdi:shield-check-outline` — "you're a backup, can claim anytime"

  8. `[ ]` **Add `backup_access` storage field and constants** in `custom_components/choreops/const.py`:
     ```python
     DATA_CHORE_BACKUP_ACCESS: Final = "backup_access"
     BACKUP_ACCESS_ANYTIME: Final = "anytime"
     BACKUP_ACCESS_ON_OVERDUE: Final = "on_overdue"
     BACKUP_ACCESS_MANUAL_ONLY: Final = "manual_only"
     BACKUP_ACCESS_OPTIONS: Final = [
         {"value": BACKUP_ACCESS_ANYTIME, "label": "backup_access_anytime"},
         {"value": BACKUP_ACCESS_ON_OVERDUE, "label": "backup_access_on_overdue"},
         {"value": BACKUP_ACCESS_MANUAL_ONLY, "label": "backup_access_manual_only"},
     ]
     ```
     Add to `UserData` TypedDict in `type_defs.py` (as `NotRequired[str]`).

     **Options flow behavior**: `build_chore()` always sets `backup_access = "anytime"` as a default. In `_handle_criteria_transition()`, when transitioning TO `rotation_primary_backup`, ensure it exists (default to `"anytime"`). When transitioning AWAY, leave it (harmless). The field always shows in the options flow; when the criteria is NOT primary-backup, display a label like "N/A — only applies to Rotation — Primary & Backup" since HA options flow doesn't support dynamic field visibility.

  9. `[ ]` **CRIT-1: Add to `can_claim_chore` `other_assignee_states` check** in `custom_components/choreops/managers/chore_manager.py` (~line 674-679). The existing tuple must include `COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP` so the single-claimer blocking logic builds the `other_assignee_states` dict for primary-backup chores:
     ```python
     if completion_criteria in (
         const.COMPLETION_CRITERIA_SHARED_FIRST,
         const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
         const.COMPLETION_CRITERIA_ROTATION_SMART,
         const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
     ):
     ```

  9. `[ ]` **CRIT-2: Add to `_remove_name_from_ownership_list`** in `custom_components/choreops/managers/chore_manager.py` (~line 4828-4834). Same tuple addition — primary-backup uses chore-level ownership (like all single-claimer modes):
     ```python
     if completion_criteria in (
         const.COMPLETION_CRITERIA_SHARED_FIRST,
         const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
         const.COMPLETION_CRITERIA_ROTATION_SMART,
         const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
     ):
     ```

  10. `[ ]` **CRIT-3: Add to `uses_chore_level_due_date` in chore_engine.py** (~line 578-583):
      ```python
      return criteria in (
          const.COMPLETION_CRITERIA_SHARED,
          const.COMPLETION_CRITERIA_SHARED_FIRST,
          const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
          const.COMPLETION_CRITERIA_ROTATION_SMART,
          const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
      )
      ```

  11. `[ ]` **CRIT-4: Add to `_uses_chore_level_due_date` in services.py** (~line 217-222). Same tuple as CRIT-3.

  12. `[ ]` **CRIT-5: Add to `_uses_chore_level_due_date` in data_builders.py** (~line 1375-1382). Same tuple as CRIT-3.

  13. `[ ]` **CRIT-6: Add to `_COMPLETION_CRITERIA_VALUES` in services.py** (~line 735-740). This is the master validation list for service calls — without it, services would reject `rotation_primary_backup` as invalid:
      ```python
      _COMPLETION_CRITERIA_VALUES = [
          const.COMPLETION_CRITERIA_INDEPENDENT,
          const.COMPLETION_CRITERIA_SHARED,
          const.COMPLETION_CRITERIA_SHARED_FIRST,
          const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
          const.COMPLETION_CRITERIA_ROTATION_SMART,
          const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
      ]
      ```

  14. `[ ]` **CRIT-7: Add to `get_criteria_transition_actions` in chore_engine.py** (~line 1046-1051). The `old_is_rotation` and `new_is_rotation` checks must include primary_backup so that criteria transitions properly initialize/clear rotation fields:
      ```python
      old_is_rotation = old_criteria in (
          const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
          const.COMPLETION_CRITERIA_ROTATION_SMART,
          const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
      )
      new_is_rotation = new_criteria in (
          const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
          const.COMPLETION_CRITERIA_ROTATION_SMART,
          const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
      )
      ```

  15. `[ ]` **CRIT-8: Add to `build_chore` in data_builders.py** (~line 1853-1870). The `DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID` initialization tuple must include primary_backup so newly created chores get a turn-holder set to the first assignee:
      ```python
      if (
          is_create
          and assigned_assignees_value
          and completion_criteria_value
          in (
              const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
              const.COMPLETION_CRITERIA_ROTATION_SMART,
              const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP,  # NEW
          )
      )
      ```

  16. `[ ]` **CRIT-9: Verify (but do NOT add) `_handle_criteria_transition` ≥2 validation** (~line 5086-5092). Per T-5, primary_backup allows single-assignee operation. The existing tuple should NOT include primary_backup — this is intentional. Verify via test that transitioning a 1-assignee chore to primary_backup succeeds.

- **Key issues**
  - **CRIT-1 through CRIT-8 are mandatory**: These are not "nice to have" — missing any one causes runtime bugs.
  - **CRIT-7 is the most subtle**: Without it, changing an existing chore to `rotation_primary_backup` from the UI leaves `rotation_current_assignee_id` unset. The chore would have no turn-holder and all assignees would see `standby_backup`.
  - **CRIT-8 is equally critical**: Without it, newly created primary_backup chores have no turn-holder.
  - **CRIT-9 is a deliberate exclusion**: Adding primary_backup to the ≥2 validation would block single-backup configurations. T-5 explicitly allows this.
  - **Consider refactoring**: The 8 duplicated tuple patterns suggest extracting centralized helper functions. Out of scope for this feature but worth tracking as tech debt.

---

### Phase 2 – Core Implementation (Engine FSM + Manager Turn Logic)

- **Goal**: Implement the two behavioral deltas that distinguish primary-backup from standard rotation: (a) turn always resets to primary (index 0) after completion, and (b) non-turn backups see `standby_backup` instead of `not_my_turn`.

- **Steps / detailed work items**

  1. `[ ]` **Modify `_advance_rotation()`** in `custom_components/choreops/managers/chore_manager.py` (~line 5113, inside the `if method == "auto"` dispatch block). Add primary-backup as a new criteria-to-method dispatch BEFORE the simple/smart translation, and set `new_assignee_id` directly to `assigned[0]`:

     **⚠️ TRAP**: The `_advance_rotation` method dispatches by `method` parameter, not `completion_criteria`. The `method == "auto"` block translates criteria to method. The primary-backup handler must be inserted HERE — inside the `"auto"` block — not as a standalone early-return before the method dispatch:

     ```python
     if method == "auto":
         # Determine method from completion criteria
         if completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SIMPLE:
             method = "simple"
         elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SMART:
             method = "smart"
         elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
             new_assignee_id = assigned_assignees[0] if assigned_assignees else None
             # Skip method dispatch — primary-backup always snaps to primary
             # Fall through to the metadata update + signal payload below
     ```
     No need for a separate if/elif block after the dispatch — the value flows naturally into the metadata update at lines ~5162-5167.

  2. `[ ]` **Add reset-boundary force-to-primary (pause-aware)** in `_transition_chore_state()` in `custom_components/choreops/managers/chore_manager.py` (~line 4677, after the existing `_advance_rotation` call). **Placement refined by verification pass**: force-to-primary runs AFTER `_advance_rotation` (so signal captures correct `previous_assignee_id`) but still within the `if new_state == CHORE_STATE_PENDING and reset_approval_period:` scope. This handles the "nobody completed, midnight passes" case where a manual turn override from a previous cycle leaks into the new one.

     **Pause interaction (CRIT-2 from cross-analysis):** The force-to-primary must check whether the primary is paused using the existing `_is_chore_paused_for_assignee()` helper (see `chore_manager.py` line 4062). If the primary is paused, snap to the first non-paused backup. If ALL assignees are paused, freeze at current turn (do not change `rotation_current_assignee_id`).

     ```python
     if new_state == const.CHORE_STATE_PENDING and reset_approval_period:
         # Advance rotation (primary-backup sets new=primary within _advance_rotation)
         if completed_by_assignee_id:
             rotation_signal_payload = self._advance_rotation(
                 chore_id, completed_by_assignee_id, method="auto"
             )

         # Primary-backup: force turn to primary at every reset boundary
         # Pause-aware: skips paused primary, freezes if all paused
         if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == \
                 const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
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

  3. `[ ]` **Modify `resolve_assignee_chore_state()` P3 block** in `custom_components/choreops/engines/chore_engine.py` (~line 676-710). For primary-backup chores, non-turn assignees see `standby_backup`. Claim gating is controlled by the new `backup_access` field (see new Phase 1 step 17 below), NOT by `overdue_handling`:

     ```python
     # Inside P3: if primary-backup and not turn-holder
     if (
         completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP
         and assignee_id != current_turn
         and not override
     ):
         backup_access = chore_data.get(
             const.DATA_CHORE_BACKUP_ACCESS, const.BACKUP_ACCESS_ANYTIME
         )

         if due_date is not None and now > due_date:
             # Backups with anytime or on_overdue can claim when overdue
             if backup_access in (
                 const.BACKUP_ACCESS_ANYTIME,
                 const.BACKUP_ACCESS_ON_OVERDUE,
             ):
                 pass  # Fall through — overdue, claimable, shows as "Backup needed"
             else:  # manual_only
                 return (const.CHORE_STATE_STANDBY_BACKUP, const.CHORE_STATE_STANDBY_BACKUP)
         else:
             # Not yet overdue — only anytime backups can claim
             if backup_access == const.BACKUP_ACCESS_ANYTIME:
                 return (const.CHORE_STATE_STANDBY_BACKUP, const.BACKUP_AVAILABLE_SENTINEL)
             else:
                 return (const.CHORE_STATE_STANDBY_BACKUP, const.CHORE_STATE_STANDBY_BACKUP)
     ```

     **Sentinels**: `BACKUP_AVAILABLE_SENTINEL` is a sentinel value used to signal "standby_backup state but claimable." In `get_chore_status_context()`, it maps to `claim_mode = CHORE_CLAIM_MODE_BACKUP_AVAILABLE` and `can_claim = True`. This allows the dashboard to show `mdi:shield-check-outline` ("you're a backup and can claim") vs `mdi:shield-account-outline` ("you're a backup and cannot claim").

  4. `[ ]` **Update `get_chore_status_context()` claim mode mapping** in `custom_components/choreops/managers/chore_manager.py` (~line 4114-4140). Add `standby_backup` to the `claim_error_to_claim_mode` mapping:
     ```python
     const.TRANS_KEY_ERROR_CHORE_STANDBY_BACKUP: const.CHORE_CLAIM_MODE_BLOCKED_STANDBY_BACKUP,
     ```
     And map `BACKUP_AVAILABLE_SENTINEL` → `CHORE_CLAIM_MODE_BACKUP_AVAILABLE` with `can_claim = True`.

  5. `[ ]` **Update `_is_rotation_open_claim_cycle()`** — verify it already handles `rotation_primary_backup` via `is_rotation_mode()`. Since step 1.3 adds the criteria to `is_rotation_mode()`, no code change needed. But verify with a targeted test.

  6. `[ ]` **Update `chore_counts_toward_due_today_summary()`** in `custom_components/choreops/managers/chore_manager.py` (~line 4171). The `standby_backup` state should NOT count toward due-today for the backup assignee (like `not_my_turn` currently doesn't count). Add `CHORE_STATE_STANDBY_BACKUP` to the early-return exclusion list alongside `CHORE_STATE_NOT_MY_TURN`.

  7. `[ ]` **Update `_collect_normalized_assignee_persisted_states()`** — no change needed. `standby_backup` is a DERIVED (UI-only) state, never persisted. The persisted state for a backup who hasn't acted is `pending`, which is already handled.

- **Key issues**
  - **P3 ordering is critical**: The `standby_backup` check must happen inside the `is_rotation_mode()` block but BEFORE the generic `not_my_turn` return. If placed after, simple/smart rotation chores would also show `standby_backup`.
  - **`standby_backup` vs `not_my_turn` lock_reason**: Both use their state string as the lock reason (consistent with existing pattern). Sensors/UI use this for display logic.
  - **Reset boundary ordering**: Force-to-primary must happen AFTER `_advance_rotation` is called in `_transition_chore_state`, so the signal payload captures the correct "previous" assignee.
  - **Pause coexistence (v0.5.0+)**: The user chore pause feature shipped before primary-backup. Key surfaces already handled:
    - P0 guard in `get_chore_status_context` (line 4129) is criteria-agnostic — returns `paused` for any criteria. No change needed for primary-backup. ✅
    - `can_claim_chore` pause guard (line 3859) already blocks claims for paused users regardless of criteria. ✅
    - `set_rotation_turn` pause guard (line 5290) already rejects setting turn to a paused user. ✅
    - `_advance_rotation_past_paused_assignee()` (line 5854) handles rotation advance past paused turn-holders in real time. Since it uses `is_rotation_mode()`, it automatically covers primary-backup. ✅
    - `_advance_rotation()` (line 5071) has NO internal pause skip loop. The cross-analysis (CRIT-1) incorrectly predicted one — the implementations are in separate methods and do not conflict. ✅
    - The reset-boundary force-to-primary (Step 2 above) is the only location needing explicit pause awareness. ⚠️

---

### Phase 3 – UX & Notifications (Translations, Display, Wording)

- **Goal**: Ensure user-facing strings are translatable, the `standby_backup` state is properly labeled, and notification wording makes sense for the primary-backup relationship.

- **Steps / detailed work items**

  1. `[ ]` **Add `standby_backup` translation strings** in `custom_components/choreops/translations/en.json` under `entity.sensor.chore_status.state`:
     ```json
     "standby_backup": "Standby (backup)"
     ```
     And under `entity.sensor.chore_status.state_attributes.claim_mode.state`:
     ```json
     "blocked_standby_backup": "You are a backup for this chore"
     "backup_available": "Backup — you can claim this chore"
     ```

  2. `[ ]` **Add completion criteria label translation** in `custom_components/choreops/translations/en.json` under `config.step.chore_settings.data.completion_criteria.options`:
     ```json
     "rotation_primary_backup": "Rotation - primary & backup"
     ```

  3. `[ ]` **Add new translation key constants** in `custom_components/choreops/const.py`:
     ```python
     TRANS_KEY_ERROR_CHORE_STANDBY_BACKUP: Final = "chore_standby_backup"
     ```
     And add the corresponding error message in `en.json` under `exceptions`:
     ```json
     "chore_standby_backup": "You are a backup for {chore_name}. The primary assignee has first responsibility."
     ```

  4. `[ ]` **Add dedicated backup-needed notification** in `custom_components/choreops/translations/en_notifications.json`. When a primary-backup chore with `backup_access` of `anytime` or `on_overdue` becomes overdue, notify all backups:
     - Title: "Backup needed: {chore_name}"
     - Message: "{primary_name} hasn't completed {chore_name}. It's now available for you to claim."
     This is a new notification template key (not reusing the `allow_steal` notification).

  5. `[ ]` **Add `can_claim_error` translation** for `standby_backup` so the UI shows an appropriate reason when a backup tries to claim before their turn is active or steal window is open.

  6. `[ ]` **Update `services.yaml`** if any new service parameters are needed for primary-backup chores. Initial assessment: none — `set_rotation_turn` and `open_rotation_cycle` already work.

- **Key issues**
  - Notification template scoping: A dedicated backup-needed notification template is the right approach (not sharing with rotation `allow_steal`). The backup relationship is different from the steal window concept.
  - `standby_backup` vs `not_my_turn` icon differentiation: Consider a distinct icon (`mdi:shield-account-outline` vs `mdi:account-cancel`) so dashboards can visually distinguish "you're a backup" from "it's not your turn in the rotation."

---

### Phase 4 – Testing

- **Goal**: Full coverage of the new criteria's FSM states, turn-reset behavior, steal interaction, and boundary conditions.

- **Steps / detailed work items**

  1. `[ ]` **Create test class `TestRotationPrimaryBackupChores`** in `tests/test_rotation_fsm_states.py` (or new dedicated file `tests/test_rotation_primary_backup.py`). Follow the pattern of `TestRotationSimpleChores`.

  2. `[ ]` **Test: Primary always sees chore as claimable** — Primary (assignee[0]) should see `pending`/`due`/`waiting` (never `standby_backup`) regardless of turn state.

  3. `[ ]` **Test: Backup with `backup_access.anytime` can claim immediately** — Backup (assignee[1]) should see `standby_backup` state with `backup_available` claim mode. Can claim at any time. No `overdue` required.

  4. `[ ]` **Test: Backup with `backup_access.on_overdue` must wait** — Backup sees `standby_backup` with `blocked_standby_backup` claim mode before due date. After due date, sees `overdue` (claimable).

  4a. `[ ]` **Test: Backup with `backup_access.manual_only` can never claim directly** — Backup always sees `standby_backup` with `blocked_standby_backup`. Only admin `set_rotation_turn` or pause can activate.

  5. `[ ]` **Test: Manual turn override (`set_rotation_turn`)** — Approver sets turn to backup. Backup should now see `pending`/`due` (not `standby_backup`). Primary should now see `standby_backup`.

  6. `[ ]` **Test: Turn resets to primary after approval** — Backup completes chore → chore approved → turn resets to primary. Primary should again be the active turn-holder.

  7. `[ ]` **Test: Turn resets to primary at midnight boundary** — Backup is turn-holder, midnight passes → reset boundary fires → turn snaps back to primary. Primary should be turn-holder at next poll.

  8. `[ ]` **Test: `open_rotation_cycle` works** — Open cycle allows any backup to claim. First claimer wins (shared_first behavior). After completion, turn resets to primary.

  9. `[ ]` **Test: Single assignee (no backups) works gracefully** — Chore with only one assignee (primary, no backups) should behave like a normal rotation chore with one person. No crashes, no `standby_backup` shown (since primary is always turn-holder).

  10. `[ ]` **Test: Accountability stats** — Backup who completes chore during active turn gets completion credit. Primary does NOT get missed stat when backup completes during backup's turn window. Primary gets missed/overdue stat when nobody completes by due date (since primary is always turn-holder at reset).

  11. `[ ]` **Test: Dashboard `due_today` filter** — `standby_backup` chores should NOT count toward the backup's due-today summary.

  12. `[ ]` **Test: Regression — existing rotation types unaffected** — Run existing `TestRotationSimpleChores` and `TestRotationSmartChores` to confirm no regressions.

  13. `[ ]` **Test: Primary paused → backup becomes active** — Pause the primary. Verify backup sees normal `pending`/`due`/`waiting` state on the chore, not `standby_backup`.

  14. `[ ]` **Test: Backup paused → sees `paused` not `standby_backup`** — Pause a backup. Verify they see `paused` state, not `standby_backup` (P0 guard beats P3 standby).

- **Key issues**
  - Test fixtures: Reuse `scenario_shared` from existing rotation tests. May need a new scenario YAML fixture for primary-backup with specific overdue handling configuration.
  - Snapshot tests: If snapshot testing is used for entity states, will need `--snapshot-update` for new `standby_backup` state snapshots.

---

### Phase 5a – Dashboard Template Updates (choreops-dashboards repo)

- **Goal**: Update all dashboard templates and translations to recognize the new `standby_backup` state, the new `blocked_standby_backup` claim mode, and the new `rotation_primary_backup` completion criteria display label.

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
     "standby_backup": "Standby (Backup)",
     "blocked_standby_backup": "Standby Backup",
     "rotation_primary_backup": "Rotation - Primary & Backup"
     ```
     The `rotation_primary_backup` key is used by `ui.get(completion_type_key, ...)` when the entity attribute `completion_criteria` equals `"rotation_primary_backup"`. No template code change needed for criteria display — it's purely a translation lookup.

  2. `[ ]` **Update `status_map` in admin-shared-v1.yaml** (~line 1472, after `'not_my_turn'` entry):
     ```yaml
     'standby_backup': ui.get('standby_backup', 'err-standby_backup'),
     ```
     And in the blocked claim-mode section (~line 1480, after `'blocked_not_my_turn'`):
     ```yaml
     'blocked_standby_backup': ui.get('standby_backup', 'err-standby_backup'),
     'backup_available': ui.get('standby_backup', 'err-standby_backup'),
     ```

  3. `[ ]` **Update `status_color_map` in admin-shared-v1.yaml** (~line 1524-1529, after `'not_my_turn'` and `'blocked_not_my_turn'` entries):
     ```yaml
     'standby_backup': 'var(--disabled-text-color)',
     'blocked_standby_backup': 'var(--disabled-text-color)',
     'backup_available': 'var(--primary-color)',
     ```
     `backup_available` uses primary-color to signal actionability (like `claimable`), while `standby_backup`/`blocked_standby_backup` stay muted.

  4. `[ ]` **Apply identical changes to admin-peruser-v1.yaml** — `status_map` at ~line 1404/1412, `status_color_map` at ~line 1456/1461. Same entries as steps 2-3.

  5. `[ ]` **Update shared `button_card_template_chore_row_v1.yaml`** — this is the most critical file as it's used by ALL user-facing chore row cards:
     - **`statusMap`** (~line 149): Add `standby_backup: i18n('standby_backup', 'err-standby_backup'),` and `blocked_standby_backup: i18n('standby_backup', 'err-standby_backup'),` after the `blocked_not_my_turn` entry.
     - **`claimModeIconMap`** (~line 199): Add entries for the new backup claim modes:
       ```yaml
       blocked_standby_backup: 'mdi:shield-account-outline',   # Can't claim
       backup_available: 'mdi:shield-check-outline',           # Can claim anytime
       ```
     - **`stealAccent` background-color detection** (~line 16): No change needed for primary-backup — the `steal_available` check is rotation-specific.

  6. `[ ]` **Update `user-chores-essential-v1.yaml`** — multiple locations:
     - **`pref_exclude_states` comment** (~line 208): Add `standby_backup` to the example list so users know they can filter it out:
       ```yaml
       {%- set pref_exclude_states = [] -%}  {#-- Example: ['completed', 'completed_by_other', 'not_my_turn', 'standby_backup', 'missed'] --#}
       ```
     - **`statusMap` in action button** (~line 674-682): Add `'standby_backup': ui.get('standby_backup', 'err-standby_backup'),` and `'blocked_standby_backup': ui.get('standby_backup', 'err-standby_backup'),`
     - **Sort order comment** (~line 464): Update to show `standby_backup` in the actionability chain:
       ```yaml
       {#-- Actionability sort: overdue, due, pending, waiting, claimed, completed, completed_by_other, standby_backup, not_my_turn, missed --#}
       ```
     - **Sort order logic** (~line 482-484): Add `standby_backup` with priority 7 (bumping `not_my_turn` to 8 and `missed` to 9):
       ```yaml
       {%- elif chore_state == 'standby_backup' -%}
         {%- set state_priority = 7 -%}
       {%- elif chore_state == 'not_my_turn' -%}
         {%- set state_priority = 8 -%}
       {%- elif chore_state == 'missed' -%}
         {%- set state_priority = 9 -%}
       ```

  7. `[ ]` **Apply equivalent changes to `user-chores-lite-v1.yaml` and `user-chores-standard-v1.yaml`** — these share the same statusMap/sort-order patterns. Search for `not_my_turn` in each file and add `standby_backup` entries adjacent.

  8. `[ ]` **Sync vendored copies**: Run `python utils/sync_dashboard_assets.py` from the choreops-dashboards repo to mirror all changes into `custom_components/choreops/dashboards/`. Then run `python utils/sync_dashboard_assets.py --check` to verify parity.

  9. `[ ]` **Add non-English translation stubs** in `choreops-dashboards/translations/` — add the 3 new keys to ALL localized dashboard JSON files with English placeholder values. Crowdin will handle proper translation:
     ```json
     "standby_backup": "Standby (Backup)",
     "blocked_standby_backup": "Standby Backup",
     "rotation_primary_backup": "Rotation - Primary & Backup"
     ```

- **Key issues**
  - **Sort order decision**: `standby_backup` is placed BETWEEN `completed_by_other` (priority 6) and `not_my_turn` (priority 7→8). Rationale: standby_backup is more actionable than `not_my_turn` (backup CAN become active via overdue steal or manual override) but less actionable than `completed_by_other` (which is a definitive terminal state).
  - **Icon choice**: `mdi:shield-account-outline` conveys "protective/backup role" and is visually distinct from `mdi:account-lock-outline` (used for `not_my_turn`).
  - **No classic templates**: The `*-kidschores-classic.yaml` templates use a different architecture (markdown-based, not button-card). They read `completion_criteria` attribute for display but use a `state_map` that maps criteria values to display strings. Adding `"rotation_primary_backup": "Rotation - Primary & Backup"` to that map may be needed if those templates are still supported. Check with product owner.
  - **Sync contract**: After canonical edits in `choreops-dashboards/`, the sync script must produce byte-identical vendored copies. Any drift breaks the parity contract (per DEVELOPMENT_STANDARDS.md §1.3).

  10. `[ ]` **Update admin dashboard rotation controls** — In both `admin-shared-v1.yaml` and `admin-peruser-v1.yaml`, the per-chore rotation controls need conditionally different labels for primary-backup chores. Zero new services needed — all three actions use existing service calls:

      **No backend work**. The services already exist:
      - `choreops.update_chore` with reordered `assigned_user_names` = changing primary
      - `choreops.set_rotation_turn` = assigning turn to a backup
      - `choreops.open_rotation_cycle` (registered at `services.py:3320`) = opening to all backups

      **Template-only changes** (conditional on `completion_criteria == "rotation_primary_backup"`):

      | Current button | Primary-backup label | Service call |
      |---------------|---------------------|--------------|
      | "Move to Front" | **"Make Primary"** | `choreops.update_chore` with reordered names |
      | "Set Turn" | **"Assign Turn"** | `choreops.set_rotation_turn` |
      | *(no button)* | **"Open to All Backups"** | `choreops.open_rotation_cycle` |

      The third button ("Open to All Backups") is a new addition — it lifts the `standby_backup` restriction for one cycle for all backups, first claimer wins. The cycle override auto-clears at the next approval reset.

### Phase 5b – Documentation & Wiki Updates

- **Goal**: Update all user-facing and developer-facing documentation across the `choreops` repo, `choreops-wiki` repo, and `choreops-dashboards` repo.

- **Documentation inventory** (from Phase 0 verification):

  | # | Doc | Repo | What to add |
  |---|-----|------|------------|
  | DOC-1 | `Configuration:-Chores.md` | `choreops-wiki` | New "Rotation — Primary & Backup" subsection under Completion Criteria. Explain: implicit primary (first assigned user), three backup_access modes (anytime/on_overdue/manual_only), pause interaction, accountability model (turn-holder gets missed/overdue stats). |
  | DOC-2 | `Advanced:-Chores.md` | `choreops-wiki` | New section or subsection: when primary-backup is appropriate (single-owner chores needing fallback), how it differs from standard rotation (always snaps to primary, backups see `standby_backup` not `not_my_turn`), rotation comparison table. |
  | DOC-3 | `Configuration:-Users.md` | `choreops-wiki` | Note: for primary-backup chores, the first user in the assigned list is always the primary. Order matters. |
  | DOC-4 | `ARCHITECTURE.md` | `choreops` | Add `standby_backup` to derived UI state documentation (alongside `not_my_turn`, `waiting`, `due`, etc.). The state listing is in the const.py section reference. |
  | DOC-5 | `DASHBOARD_UI_DESIGN_GUIDELINE.md` | `choreops` | Add `standby_backup` to the state color/style reference table. Add `blocked_standby_backup` to claim mode icon table. |
  | DOC-6 | `en_dashboard.json` | `choreops-dashboards` | Already covered in Phase 5a step 1 (3 new i18n keys) |
  | DOC-7 | All locale `*_dashboard.json` | `choreops-dashboards` | Already covered in Phase 5a step 9 (English placeholder stubs for Crowdin) |
  | DOC-8 | `RELEASE_CHECKLIST.md` | `choreops` | Add release note entry for new `rotation_primary_backup` criteria and `standby_backup` state |
  | DOC-9 | `_Sidebar.md` | `choreops-wiki` | Review if new wiki page structure requires sidebar link update |

- **Steps / detailed work items**

  1. `[ ]` **DOC-1: Update `Configuration:-Chores.md`** — Add "Rotation — Primary & Backup" subsection after the "Rotation Smart" section. Template:
     ```markdown
     ### Rotation — Primary & Backup

     Permanent primary owner with designated backups for fallback.

     - The **first assigned user** is always the primary (permanent turn-holder)
     - Backups see "Standby (Backup)" status and cannot claim unless:
       - An approver manually sets the turn to them, or
       - The chore becomes overdue with "Allow steal" enabled
     - After every completion, the turn always resets to the primary
     - Accountability stays with the turn-holder (primary by default)
     - Best for chores with a clear owner who occasionally needs coverage
     ```

  2. `[ ]` **DOC-2: Update `Advanced:-Chores.md`** — Add primary-backup section covering: conceptual model (primary = owner, backup = fallback), activation triggers (manual + overdue steal), comparison to standard rotation (key difference: always snaps to primary, not round-robin), known limitations (no smart rotation among backups, no "backup duty" dashboard filter).

  3. `[ ]` **DOC-3: Update `Configuration:-Users.md`** — Add note in the user assignment section: "For Rotation — Primary & Backup chores, the first user in the assigned list is always the primary. Reorder users to change the primary."

  4. `[ ]` **DOC-4: Update `ARCHITECTURE.md`** — In the state constants reference section, add `standby_backup` to the derived UI state listing.

  5. `[ ]` **DOC-5: Update `DASHBOARD_UI_DESIGN_GUIDELINE.md`** — Add `standby_backup` row to state color table (color: `var(--disabled-text-color)`, same tier as `not_my_turn`). Add `blocked_standby_backup` to claim mode icon table (icon: `mdi:shield-account-outline`).

  6. `[ ]` **DOC-8: Update `RELEASE_CHECKLIST.md`** — Add release note entry under the appropriate category (likely "enh: feature").

  7. `[ ]` **DOC-9: Review wiki sidebar** — Check if `_Sidebar.md` needs a new link for primary-backup content.

- **Key issues**
  - Wiki updates are in a **separate repository** (`choreops-wiki`). They must be coordinated with the integration release but are not blocking for code merge.
  - The `ARCHITECTURE.md` state listing should stay in sync with `const.py` — if the architecture doc enumerates states literally, add `standby_backup`. If it references `const.py` as source of truth, a brief mention suffices.
  - `DASHBOARD_UI_DESIGN_GUIDELINE.md` may be stale — verify it's actively maintained before investing in updates.

## Testing & validation

- Tests executed (describe suites, commands, results).
  - `pytest tests/test_rotation_fsm_states.py -v` — existing rotation FSM tests must pass unchanged.
  - `pytest tests/test_workflow_chores.py -v` — existing rotation workflow tests must pass unchanged.
  - New tests in Phase 4 cover primary-backup specific paths.
- Outstanding tests (not run and why).
  - Dashboard filter tests deferred (dashboard template change, separate repo).
  - Notification delivery tests may need `mobile_notify_service` mock if notification template changes are made.
- Links to failing logs or CI runs if relevant.
  - N/A (not started).

## Notes & follow-up

- **Architecture decisions**:
  - `standby_backup` is a derived UI-only state (never persisted). It follows the same pattern as `not_my_turn`, `waiting`, `due`, `completed`, and `completed_by_other`.
  - Primary-backup reuses ALL existing rotation storage fields (`rotation_current_assignee_id`, `rotation_cycle_override`). No new storage fields needed.
  - The `_advance_rotation` method for primary-backup simply sets `new_assignee_id = assigned_assignees[0]` — it doesn't calculate next turn at all.

- **Code surface area estimate (revised after Phase 0 verification)**:
  - **Integration repo (`choreops`)**:
    - `const.py`: ~15 lines (new constants + frozenset entries + criteria options entry)
    - `chore_engine.py`: ~25 lines (add to `is_rotation_mode` + `is_single_claimer_mode` + `uses_chore_level_due_date` + CRIT-7 `get_criteria_transition_actions` + P3 branch)
    - `chore_manager.py`: ~30 lines (advance_rotation early-return + reset boundary force + claim_mode mapping + CRIT-1 `can_claim_chore` + CRIT-2 ownership clear)
    - `services.py`: ~8 lines (CRIT-4 due date check + CRIT-6 criteria values list)
    - `data_builders.py`: ~6 lines (CRIT-5 due date check + CRIT-8 rotation field initialization)
    - `translations/en.json`: ~15 lines (new state, criteria label, error message)
    - `tests/`: ~200 lines (new test class)
    - **Subtotal**: ~90 lines production, ~200 lines test (was ~60, increased by CRIT-1 through CRIT-6)
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
  - Dashboard "Backup Duty" filter section.
  - Primary completion rate badge/achievement.
  - `standby_backup` icon differentiation (translation-based icon support).

> **Plan created**: 2026-06-05 | **Last updated**: 2026-06-05 | **Based on**: Strategic analysis of rotation infrastructure reuse for primary-backup failover pattern.
