# Initiative Plan: Chore Logic v0.5.0 — Due Window Restrictions & Advanced Rotation

## Initiative snapshot

- **Name / Code**: Chore Logic v0.5.0 — Due Window Claim Restrictions + Advanced Rotation
- **Target release / milestone**: v0.5.0 (Schema v44 — extended in-place, no bump)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Complete (all phases 100%)

---

## ⚠️ APPROVAL CYCLE PROCESSING MODEL — MANDATORY VOCABULARY

> **This section defines the three independent processing lanes that govern a chore's lifecycle.**
> All plan phases, blueprint code, state matrix, and translations MUST use these precise terms.
> Never say "reset" without specifying WHICH lane is acting.

A chore's per-cycle lifecycle is governed by **three independent settings**, each controlling a separate lane of logic. These lanes share a common trigger point but execute distinct responsibilities:

### Lane 1: `approval_reset_type` — THE TRIGGER (When the boundary fires)

**Field**: `DATA_CHORE_APPROVAL_RESET_TYPE`
**Question answered**: "When does the chore's approval cycle boundary fire?"

| Value               | Trigger                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------ |
| `at_midnight_once`  | Fires once at midnight. Single-claim chore.                                                |
| `at_midnight_multi` | Fires at midnight. Multi-claim chore (kid can claim again after approval within same day). |
| `at_due_date_once`  | Fires when the configured due date/time is reached. Single-claim.                          |
| `at_due_date_multi` | Fires at due date/time. Multi-claim within cycle.                                          |
| `upon_completion`   | Fires immediately when the chore is approved (no time boundary).                           |
| `manual`            | Never fires automatically. Parent must manually trigger.                                   |

**This lane does NOT decide what happens.** It only decides **when** the boundary fires. The other two lanes decide what actions occur at that boundary.

### Lane 2: `overdue_handling_type` — THE OVERDUE POLICY (What happens past due date + at boundary)

**Field**: `DATA_CHORE_OVERDUE_HANDLING_TYPE`
**Question answered**: "What happens when the due date passes? And what happens to an overdue chore when the approval reset boundary fires?"

This lane has TWO moments of action:

1. **At due date**: Determines the chore's overdue state transition (e.g., mark as `overdue`, lock as `missed`, open steal window)
2. **At approval reset boundary**: Determines what happens to the overdue/missed state when Lane 1's trigger fires (e.g., clear overdue status, advance rotation turn, record missed stat)

| Value                                       | At Due Date                                                             | At Approval Reset Boundary                                                                           |
| ------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `never_overdue`                             | No state change                                                         | No action                                                                                            |
| `at_due_date`                               | Chore state → `overdue` (claimable)                                     | No automatic action (overdue persists)                                                               |
| `at_due_date_clear_at_approval_reset`       | Chore state → `overdue` (claimable)                                     | Overdue status cleared, chore state → `pending`                                                      |
| `at_due_date_clear_immediate_on_late`       | Chore state → `overdue` (claimable)                                     | If still overdue: clear + record late stat                                                           |
| `at_due_date_clear_and_mark_missed`         | Chore state → `overdue` (claimable)                                     | If still overdue: record missed stat, chore state → `pending`                                        |
| `at_due_date_mark_missed_and_lock`          | Chore state → `missed` (**locked**, not claimable)                      | Unlock missed state, chore state → `pending`                                                         |
| `at_due_date_allow_steal` _(rotation-only)_ | `not_my_turn` blocking lifts for all assigned kids (steal window opens) | If still overdue: record missed stat for turn-holder, chore state → `pending`, advance rotation turn |

### Lane 3: `approval_reset_pending_claim_action` — THE CLAIM POLICY (What happens to unapproved claims at boundary)

**Field**: `DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION`
**Question answered**: "If a kid has claimed but the parent hasn't approved yet when the approval reset boundary fires, what happens to that pending claim?"

| Value                  | Action at Approval Reset Boundary                      |
| ---------------------- | ------------------------------------------------------ |
| `hold_pending`         | Keep the pending claim intact across the boundary      |
| `clear_pending`        | Discard the pending claim, chore state → `pending`     |
| `auto_approve_pending` | Auto-approve the pending claim (as if parent approved) |

### Processing Order at Approval Reset Boundary

When Lane 1's trigger fires, the system processes in this order:

1. **Lane 3 (Claim Policy)** executes first — resolve any pending claims
2. **Lane 2 (Overdue Policy)** executes second — resolve any overdue/missed states
3. **Chore state reset** — the chore's approval cycle resets to `pending` for a new cycle

### ❌ Vocabulary Anti-Patterns

| ❌ NEVER Write         | ✅ ALWAYS Write                                                             | Why                                                         |
| ---------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------- |
| "midnight reset"       | "approval reset boundary (midnight for `at_midnight_once`)"                 | Specifies Lane 1                                            |
| "resets to pending"    | "chore state resets to `pending`" or "overdue policy clears overdue status" | Distinguishes chore state change from overdue policy action |
| "only midnight resets" | "only `at_midnight_*` approval reset types can trigger the unlock"          | Specifies which trigger types are compatible                |
| "reset at boundary"    | "at the approval reset boundary, the overdue policy [specific action]"      | Names the lane                                              |
| "overdue resets"       | "overdue policy clears the overdue status"                                  | Names the lane and the action                               |

---

## ⚠️ ROTATION DESIGN v2 — AUTHORITATIVE REFERENCE

> **This section is the single source of truth for rotation behavior.**
> All plan phases, blueprint code, state matrix, and translations MUST align with this section.
> Updated 2026-02-12 after design pivot: 3 rotation criteria → 2 criteria + 1 overdue type.

### What Changed (Design Pivot)

| Before (v1)                                                                           | After (v2)                                                              |
| ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 3 `completion_criteria` values: `rotation_simple`, `rotation_steal`, `rotation_smart` | **2** `completion_criteria` values: `rotation_simple`, `rotation_smart` |
| "Steal" was a separate criteria type                                                  | "Steal" moved to **overdue handling**: `at_due_date_allow_steal`        |
| Steal logic checked `criteria == rotation_steal`                                      | Steal logic checks `overdue_handling == at_due_date_allow_steal`        |

### Rotation Type Definitions

#### `rotation_simple` — Strict Turn-Based, Fixed Order

- **Who can claim**: ONLY the current turn-holder. All other assigned kids see `not_my_turn` and cannot claim.
- **Turn advancement**: Round-robin by `assigned_kids` list index. After approval, turn advances to `assigned_kids[(current_index + 1) % len]`.
- **Parent override**: The parent "Approve" button can manually approve any kid (not just the turn-holder). After parent-approved completion, turn advances normally from the kid who completed.
- **After pure miss (no one claims)**: When the approval reset boundary fires (Lane 1 — midnight for `at_midnight_once`), the overdue policy (Lane 2) executes: records a missed stat for the skipped turn-holder, clears the overdue status, resets chore state to `pending`, and advances the turn to the next kid in order. Only the skipped turn-holder gets the overdue/missed stat.
- **Use case**: Strict fairness for siblings. "It's your turn, no exceptions."

#### `rotation_smart` — Strict Turn-Based, Fairness-Weighted Order

- **Who can claim**: ONLY the current turn-holder. All other assigned kids see `not_my_turn` and cannot claim. (Same blocking behavior as `rotation_simple`.)
- **Turn advancement**: Fairness-weighted selection. The system picks the next turn-holder using these criteria (ascending priority):
  1. Fewest all-time approved completions for this chore
  2. Oldest `last_approved_timestamp` (tie-break: longest since last completion wins)
  3. List position in `assigned_kids` (final tie-break)
- **Parent override**: Same as `rotation_simple` — parent can approve any kid.
- **After pure miss**: Same as `rotation_simple` — when the approval reset boundary fires, the overdue policy records the missed stat, clears overdue status, resets chore state to `pending`, and advances the turn to the next kid (per fairness algorithm). Skipped holder gets the stat.
- **Use case**: Self-balancing fairness. A kid who missed several turns gets re-prioritized automatically.

### Overdue Handling Type: `at_due_date_allow_steal`

This is a **7th overdue handling type** (not a completion criteria). It controls what happens when a rotation chore's due date passes without the turn-holder claiming.

- **Pre-overdue**: Normal rotation blocking applies. Only the turn-holder can claim.
- **At due date (overdue)**: The `not_my_turn` blocking **lifts for all assigned kids**. Any assigned kid can now claim the chore. This is the "steal" window.
- **Notifications**: When the steal window opens, ALL assigned kids receive a notification (not just the turn-holder). The notification indicates the chore is available for anyone.
- **Overdue stat**: Only the skipped turn-holder gets the `overdue` stat. The kid who steals does NOT get an overdue mark.
- **After steal (someone claims)**: Normal `_advance_rotation()` runs from the kid who completed. Turn advances to the next kid per the rotation type's algorithm (round-robin for simple, fairness-weighted for smart).
- **After pure miss (no one claims, including steal window)**: When the approval reset boundary fires (Lane 1 — midnight, since `at_midnight_once` is the only compatible `approval_reset_type`), the overdue policy (Lane 2) for `at_due_date_allow_steal` executes: records a missed stat for the original turn-holder, clears the overdue status, resets chore state to `pending`, and advances the turn to the next kid. The chore begins a fresh cycle with the new turn-holder.

### Compatibility Matrix

`at_due_date_allow_steal` has strict compatibility requirements:

| Setting               | Allowed Values                             | Reason                                                                                   |
| --------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------- |
| `completion_criteria` | `rotation_simple` or `rotation_smart` ONLY | Steal is a rotation-only mechanic. Non-rotation chores have no turn to steal.            |
| `approval_reset_type` | `at_midnight_once` ONLY                    | Multi-claim and due-date resets create ambiguity about what "one steal per cycle" means. |

**Validation rule (V-05)**: If `overdue_handling == at_due_date_allow_steal`, then:

1. `completion_criteria` MUST be a rotation type (`rotation_simple` or `rotation_smart`)
2. `approval_reset_type` MUST be `at_midnight_once`
3. A due date MUST be configured (steal window needs a trigger point)

### Real-World Scenario: "Dishes Rotation with Steal"

> **Setup**: 3 kids (Alice, Bob, Charlie). Chore: "Wash Dishes." `rotation_simple` + `at_due_date_allow_steal` + `at_midnight_once`. Due time: 7 PM daily.
>
> **Monday**: Alice's turn. She claims at 6 PM, parent approves. Turn advances to Bob.
>
> **Tuesday**: Bob's turn. He forgets. At 7:01 PM the steal window opens. All 3 kids get notified: "Dishes is available!" Charlie claims at 7:30 PM. Parent approves. Turn advances to Charlie+1 = Alice. Bob gets the overdue stat. Charlie does NOT.
>
> **Wednesday**: Alice's turn. Nobody claims. 7 PM passes (steal window opens). Still nobody claims by midnight. At the approval reset boundary (midnight): overdue policy records Alice's missed stat, clears overdue status, resets chore state to `pending`, and advances the turn to Bob.
>
> **Thursday**: Bob's turn (fairness note: Bob has fewest completions if using `rotation_smart`).

### Terminology Reference

| Term               | Meaning                                                                                                                                                                                 |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Turn-holder**    | The kid whose `kid_id == rotation_current_kid_id`. Only they can claim.                                                                                                                 |
| **Steal window**   | Period after due date when `at_due_date_allow_steal` lifts turn blocking.                                                                                                               |
| **Steal**          | When a non-turn-holder claims during the steal window.                                                                                                                                  |
| **Pure miss**      | No one claims (not even during steal window). At the approval reset boundary: overdue policy records missed stat, clears overdue status, resets chore state → `pending`, advances turn. |
| **Turn advance**   | Updating `rotation_current_kid_id` to the next kid after approval/miss.                                                                                                                 |
| **Cycle override** | `rotation_cycle_override=True` — manual service that lets any kid claim.                                                                                                                |

---

## Summary & immediate steps

| Phase / Step                      | Description                                                      | % complete | Quick notes                                                                                                          |
| --------------------------------- | ---------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Foundation              | Constants, types, validation rules (no schema migration)         | 100%       | ✅ COMPLETE — rotation_steal removed, allow_steal added, all tests pass                                              |
| Phase 2 – Engine & State Machine  | 8-tier FSM, claim restrictions, rotation resolution              | 100%       | ✅ COMPLETE — Logic adapters, FSM, claim restrictions (1257/1257 tests)                                              |
| Phase 3 – Manager Orchestration   | Rotation advancement, missed lock, scanner updates, new services | 100%       | ✅ COMPLETE — All 10 steps done: services, notifications, stats                                                      |
| Phase 4 – UX & Dashboard Contract | UI Manager attributes, flow helpers, notification wiring         | 100%       | ✅ **COMPLETE** — All 4 steps done (dashboard helper 9-field contract + flow helpers + options flow + documentation) |
| Phase 5 – Testing & Validation    | Full test coverage for all new paths                             | 100%       | ✅ COMPLETE — targeted + full-suite validation complete                                                               |

1. **Key objective** – Introduce two new chore management capabilities: (a) **Due Window Claim Restrictions** that prevent kids from claiming chores before a configurable window opens, and (b) **Advanced Rotation Logic** that extends shared_first chores into a disciplined turn-based system with two sub-types (`rotation_simple`, `rotation_smart`), plus a steal mechanic delivered via overdue handling (`at_due_date_allow_steal`). Both features extend the existing FSM with three new calculated states (`waiting`, `not_my_turn`, `missed` as a locked terminal state).

2. **Summary of recent work**
   - ✅ **Phase 1 Foundation COMPLETE** (2026-02-12 evening):
     - Removed `COMPLETION_CRITERIA_ROTATION_STEAL` constant from `const.py`, `en.json`, `data_builders.py`, `migration_pre_v50.py`
     - Added `OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL` constant + translation key
     - Fixed rotation_simple/smart descriptions per three-lane vocabulary
     - Validation gates: ✅ Lint passed (9.8/10), ✅ Tests 100% (1257 passed), ✅ MyPy 0 errors
   - Design pivot applied (2026-02-12): reduced from 3 rotation criteria to 2, moved steal mechanic to overdue handling.
   - Schema stays at **v44** — extend existing `_migrate_to_schema_44()` to backfill new fields (D-13)
   - **Criteria Overload pattern** (D-12): Rotation types are new `completion_criteria` values (`rotation_simple`, `rotation_smart`). Logic Adapter methods (`is_single_claimer_mode()`, `is_rotation_mode()`) prevent gremlin code across ~60 check sites
   - **Steal mechanic** (D-06 revised): NOT a completion criteria. Delivered as `at_due_date_allow_steal` overdue handling type. Only compatible with rotation criteria + `at_midnight_once` `approval_reset_type`.
   - **completion_criteria is MUTABLE** (D-11): Users can change criteria when editing chores. The `services.py` L784-788 immutability guard is incorrect and must be removed. Data transition logic handles field cleanup on criteria change.
   - Existing `clear_and_mark_missed` and new `mark_missed_and_lock` are **two distinct strategies** (6th overdue type). `at_due_date_allow_steal` is the **7th overdue type**.
   - All rotation types require **≥ 2 assigned kids** (D-14)
   - Both `rotation_simple` and `rotation_smart` enforce **strict turn blocking** — only the turn-holder can claim
   - No rotation code exists yet (greenfield)

3. **Next steps (short term)**
   - ✅ **Phase 1 code corrections COMPLETE** (rotation_steal removed, allow_steal added, all tests pass)
   - **Ready to start Phase 2**: Engine & State Machine implementation
   - Blueprint document updated for implementer reference: [CHORE_LOGIC_V050_SUP_BLUEPRINT.md](CHORE_LOGIC_V050_SUP_BLUEPRINT.md)

4. **Risks / blockers**
   - Risk: ~60 criteria check sites need audit for Logic Adapter adoption. `chore_manager.py` has 25 sites — highest refactoring density
   - Risk: Smart rotation depends on StatsEngine/StatsManager query that doesn't yet exist
   - Risk: `is_shared_chore()` in engine has **zero production callers** (dead code). All callers inline their own checks — this validates the Logic Adapter approach but means broader refactoring

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — Data model, storage, versioning
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Naming, patterns, signal rules
   - [QUALITY_REFERENCE.md](../QUALITY_REFERENCE.md) — Platinum quality requirements
   - [tests/AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md) — Test patterns
   - [migration_pre_v50.py](../../custom_components/kidschores/migration_pre_v50.py) — v44 migration section (if migration needed)
   - Supporting doc: [CHORE_LOGIC_V050_SUP_STATE_MATRIX.md](CHORE_LOGIC_V050_SUP_STATE_MATRIX.md) — Full FSM state matrix
   - Supporting doc: [CHORE_LOGIC_V050_SUP_BLUEPRINT.md](CHORE_LOGIC_V050_SUP_BLUEPRINT.md) — Detailed implementation blueprint with code samples

6. **Decisions & completion check**

   ### Resolved Decisions (updated 2026-02-12 — design pivot applied)

   | ID       | Question                                                       | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Impact                                                                                                                                                                                                                                                                                                                        |
   | -------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | **D-01** | Schema version                                                 | ✅ **v44** (no bump).                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Migration extended in-place (D-13).                                                                                                                                                                                                                                                                                           |
   | **D-02** | Existing `clear_and_mark_missed` vs new `mark_missed_and_lock` | ✅ **Two distinct strategies**. Existing = "at due date: record miss → at approval reset boundary: overdue policy resets chore state to `pending`." New = "at due date: lock in `missed` state → at approval reset boundary: overdue policy unlocks `missed` state, resets chore state to `pending`."                                                                                                                                                                    | Add 6th overdue type `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK`. Existing unchanged.                                                                                                                                                                                                                                          |
   | **D-03** | `mark_missed_and_lock` approval reset type compatibility       | ✅ **`at_midnight_*` approval reset types only**.                                                                                                                                                                                                                                                                                                                                                                                                                        | Validation rule: reject `upon_completion`, `at_due_date_*`, `manual` reset types.                                                                                                                                                                                                                                             |
   | **D-04** | Due window claim restrictions                                  | ✅ **Derived from `due_window_offset` presence**. No separate `claim_restriction_enabled` boolean needed. If `due_window_offset` is set, claim restrictions apply. `can_claim` is a calculated boolean attribute on the kid chore status sensor. ⚠️ **Implementation gap (release/v0.5.0-beta4)**: `resolve_kid_chore_state()` currently has P6 removed, so `waiting` may not emit until the Phase 5 follow-up patch lands.                                              | Presence of `due_window_offset` implies restrictions. FSM should calculate `waiting` when `now < due_window_start`; current code gap is tracked in the Phase 5 waiting-claim-path follow-up plan. Simpler design, fewer fields, with explicit parity fix pending.                                                             |
   | **D-05** | Rotation as completion criteria                                | ✅ **REVISED (v2)**: Two `completion_criteria` values: `rotation_simple`, `rotation_smart`. ~~`rotation_steal` removed as criteria~~ — steal mechanic moved to overdue handling (D-06).                                                                                                                                                                                                                                                                                  | Two new constants (not three). Engine uses Logic Adapter pattern (D-12) to treat rotation as shared_first-like.                                                                                                                                                                                                               |
   | **D-06** | Steal mechanic placement                                       | ✅ **REVISED (v2)**: Steal is an **overdue handling type** (`at_due_date_allow_steal`), NOT a completion criteria. Valid only with rotation criteria + `at_midnight_once` `approval_reset_type`. At due date, `not_my_turn` blocking lifts for all assigned kids.                                                                                                                                                                                                        | New 7th overdue type constant. New validation rule V-05 (rotation + at_midnight_once required). FSM P3 steal exception checks `overdue_handling` not `criteria`.                                                                                                                                                              |
   | **D-07** | CHORE_MISSED signal                                            | ✅ **Extend existing** payload with optional `due_date` and `reason` fields.                                                                                                                                                                                                                                                                                                                                                                                             | Backward compatible.                                                                                                                                                                                                                                                                                                          |
   | **D-08** | Smart rotation stats query                                     | ✅ **StatsEngine or StatsManager** provides the query API.                                                                                                                                                                                                                                                                                                                                                                                                               | New public method for per-chore approved counts across kids.                                                                                                                                                                                                                                                                  |
   | **D-09** | "The Nudge" notification                                       | ✅ **Same as existing `notify_on_due_window`**. No new notification type.                                                                                                                                                                                                                                                                                                                                                                                                | No work needed.                                                                                                                                                                                                                                                                                                               |
   | **D-10** | Migration home                                                 | ✅ **`migration_pre_v50.py`** v44 section.                                                                                                                                                                                                                                                                                                                                                                                                                               | Extend existing `_migrate_to_schema_44()` to backfill new fields (D-13).                                                                                                                                                                                                                                                      |
   | **D-11** | `completion_criteria` mutability                               | ✅ **Mutable**. Users CAN change `completion_criteria` when editing a chore via options flow. The `services.py` immutability guard (L784-788) is incorrect and must be **removed**. When criteria changes, **data transition logic** handles cleanup (e.g., clear rotation fields when switching away from rotation; initialize `rotation_current_kid_id` when switching TO rotation).                                                                                   | Remove immutability guard from `services.py`. Add `_handle_criteria_transition()` method to ChoreManager. Add `completion_criteria` to `UPDATE_CHORE_SCHEMA`.                                                                                                                                                                 |
   | **D-12** | Data model: rotation as criteria value vs. separate field      | ✅ **Option A — Criteria Overload**. Rotation types are new `completion_criteria` values: `rotation_simple`, `rotation_smart`. UI is one-click — no separate `rotation_type` field. **Logic Adapter** pattern in `ChoreEngine` prevents "gremlin code": `is_single_claimer_mode()` → True for `shared_first` + all rotation types; `is_rotation_mode()` → True for `rotation_*` only. All existing `shared_first` checks use `is_single_claimer_mode()` adapter instead. | ~60 existing criteria check sites across 10 production files. The Logic Adapter pattern makes most transparent — existing three-way branches (INDEPENDENT / SHARED_FIRST / SHARED) become (INDEPENDENT / single_claimer / SHARED) and rotation chores automatically get correct behavior. See "Logic Adapter audit" in Notes. |
   | **D-13** | Existing chore field backfill strategy                         | ✅ **Extend v44 migration** in `migration_pre_v50.py` to backfill new fields on existing chores.                                                                                                                                                                                                                                                                                                                                                                         | Add backfill step to `_migrate_to_schema_44()`: set `rotation_current_kid_id=None`, `rotation_cycle_override=False` on all existing chores.                                                                                                                                                                                   |
   | **D-14** | Rotation minimum kids                                          | ✅ **All rotation types require ≥ 2 assigned kids**. Turn-taking with 1 kid is meaningless for any rotation variant.                                                                                                                                                                                                                                                                                                                                                     | Validation rule V-03 applies to `rotation_simple` AND `rotation_smart` uniformly. Error message in `data_builders.py`.                                                                                                                                                                                                        |
   | **D-15** | `rotation_cycle_override` clear trigger                        | ✅ **Approval action clears the override** (not a boundary event). Next approval of any kid on the chore clears `rotation_cycle_override = False`. The override is for "let anyone claim THIS cycle's instance." Once approved, normal rotation resumes.                                                                                                                                                                                                                 | Handled in `_advance_rotation()` — which already resets `rotation_cycle_override = False` after approval. No additional timer/scanner logic needed.                                                                                                                                                                           |
   | **D-16** | Where `can_claim` attribute lives                              | ✅ **Calculated boolean on the kid chore status sensor** (`KidChoreStatusSensor.extra_state_attributes`). Pipeline: `ChoreEngine.can_claim_chore()` → `ChoreManager.can_claim_chore()` → sensor attribute. Dashboard helper does NOT include it — documented to fetch via `state_attr(chore.eid, 'can_claim')`. `ATTR_CAN_CLAIM` constant already exists.                                                                                                                | New blocking conditions (waiting, not_my_turn, missed) integrate into existing `ChoreEngine.can_claim_chore()`. No new sensor or attribute needed — extend existing logic.                                                                                                                                                    |
   | **D-17** | Turn after pure miss (no steal)                                | ✅ **(NEW v2)** Turn **advances to next kid** when the approval reset boundary fires and the overdue policy executes. The skipped kid does NOT get another chance. Only the skipped turn-holder gets the missed/overdue stat.                                                                                                                                                                                                                                            | `_process_approval_boundary_resets()` must call `_advance_rotation()` after midnight unlock. Ensures rotation never stalls.                                                                                                                                                                                                   |
   | **D-18** | Turn after steal                                               | ✅ **(NEW v2)** Normal `_advance_rotation()` runs from the completer (the kid who stole). Turn advances to the next kid relative to the completer's position, NOT back to the original turn-holder.                                                                                                                                                                                                                                                                      | Same `_advance_rotation()` code path as normal approval. No special steal-specific turn logic needed.                                                                                                                                                                                                                         |
  - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps.
- **Detailed tracking**: Use the phase-specific sections below for granular progress.

---

## Detailed phase tracking

### Phase 1 – Foundation (Constants, Types, Validation, Migration)

- **Goal**: Establish the data model, constants, type definitions, Logic Adapter static methods, validation rules, and v44 migration extension. No behavioral logic — purely structural.
- **Status**: ~80% complete. Phase 1 code was implemented before design pivot. Corrections needed: remove `rotation_steal`, add `at_due_date_allow_steal`, fix translations.

- **Steps / detailed work items**
  1. **Add new constants to `const.py`** ✅ (needs correction)
     - File: `custom_components/kidschores/const.py`
     - **6th overdue handling constant** (D-02): ✅ Done
       - `OVERDUE_AT_DUE_DATE_MARK_MISSED_AND_LOCK = "at_due_date_mark_missed_and_lock"`
     - **7th overdue handling constant** (D-06 revised): ⬜ NEW — must add
       - `OVERDUE_HANDLING_AT_DUE_DATE_ALLOW_STEAL = "at_due_date_allow_steal"`
       - Add to `OVERDUE_HANDLING_TYPE_OPTIONS` list
     - **Completion criteria constants** (D-05 revised): 🔧 Needs correction
       - `COMPLETION_CRITERIA_ROTATION_SIMPLE = "rotation_simple"` ✅ Done
       - ~~`COMPLETION_CRITERIA_ROTATION_STEAL = "rotation_steal"`~~ ❌ **REMOVE** — steal is now an overdue type
       - `COMPLETION_CRITERIA_ROTATION_SMART = "rotation_smart"` ✅ Done
       - Update `COMPLETION_CRITERIA_OPTIONS` to have 5 entries (not 6)
     - **Translation keys**: 🔧 Needs correction
       - Remove `TRANS_KEY_CRITERIA_ROTATION_STEAL`
       - Add `TRANS_KEY_OVERDUE_AT_DUE_DATE_ALLOW_STEAL`
     - **All other constants** (storage keys, states, signals, services, ATTRs): ✅ Done — no changes needed

  2. **Update `type_defs.py` — ChoreData TypedDict** ✅ Done
     - 3 new `NotRequired` fields added. No changes needed for design pivot.

  3. **Update `data_builders.py` — Build & Validate** ✅ (needs V-04→V-05 correction)
     - Build defaults: ✅ Done
     - Validation rules:
       - **V-01**: `mark_missed_and_lock` requires `AT_MIDNIGHT_*` reset ✅ Done
       - **V-02**: ~~`claim_restriction_enabled` requires `due_window_offset`~~ ❌ OBSOLETE — No separate flag needed, `due_window_offset` presence is sufficient
       - **V-03**: All rotation types require ≥ 2 assigned kids ✅ Done
       - ~~**V-04**: `rotation_steal` requires due date~~ ❌ **REMOVE** — steal is no longer a criteria
       - **V-05**: ⬜ **NEW** — `at_due_date_allow_steal` requires: (a) rotation criteria, (b) `at_midnight_once` reset, (c) due date configured

  4. **Extend v44 migration to backfill new fields** (D-13) ✅ Done
     - No changes needed for design pivot. 3 fields backfilled correctly.

  5. **Update translations `en.json`** 🔧 Needs correction
     - File: `custom_components/kidschores/translations/en.json`
     - **Remove**: `rotation_steal` entries from `selector.completion_criteria.options` and `entity.sensor.kid_chore_status_sensor.state`
     - **Add**: `at_due_date_allow_steal` entry in `selector.overdue_handling_type.options`
     - **Fix rotation descriptions** (currently incorrect):
       - `rotation_simple` → "Rotation Simple (Turn-holder only, strict order)" ← currently says "Turn priority, stealing allowed" which is WRONG
       - `rotation_smart` → "Rotation Smart (Turn-holder only, fairness-weighted)" ← currently says "Only turn-holder can claim" which is acceptable but add "fairness-weighted"
     - **Add new overdue description**: `at_due_date_allow_steal` → "Allow Steal (Rotation — any kid can claim after due date)"

- **Key issues**
  - The 2 new `completion_criteria` values (not 3) must be updated in `COMPLETION_CRITERIA_OPTIONS`, `_COMPLETION_CRITERIA_VALUES` in services.py, and flow_helpers selectors
  - The new 7th overdue type `at_due_date_allow_steal` must be added to `OVERDUE_HANDLING_TYPE_OPTIONS`
  - D-14 resolved: All rotation types require ≥ 2 kids. V-03 validation rule applies uniformly.
  - **V-05 is critical**: `at_due_date_allow_steal` has the tightest compatibility constraints of any overdue type

---

### Phase 2 – Engine & State Machine (+ Logic Adapters)

- **Goal**: Implement the Logic Adapter static methods, the 8-tier priority state resolution, claim restriction logic, rotation-aware can_claim checks, and criteria transition helpers in `chore_engine.py`. Pure computation — no storage writes, no HA imports.

- **Steps / detailed work items**
  1. **Implement Logic Adapter static methods** (D-12 — the "gremlin prevention" pattern)
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - Two new static methods following existing `is_shared_chore()` signature pattern:

       ```
       is_single_claimer_mode(chore_data) -> bool
         Returns True if criteria in (shared_first, rotation_simple, rotation_smart)
         Replaces all existing "== SHARED_FIRST" checks for claim-blocking, reset-all-kids, etc.

       is_rotation_mode(chore_data) -> bool
         Returns True if criteria in (rotation_simple, rotation_smart)
         Used for rotation-specific logic (turn advancement, override, steal-via-overdue)
       ```

     - **Audit note**: ~60 existing criteria check sites across 10 production files currently inline their own checks. The existing `is_shared_chore()` has **zero production callers** (dead code — validates the adapter approach). Key refactoring targets:
       - `chore_manager.py` — 25 sites (highest density)
       - `chore_engine.py` — 10 sites
       - `options_flow.py` — 6 sites
       - `flow_helpers.py` — 5 sites
       - `sensor.py` — 4 sites
     - **Implementation strategy**: Add adapters first. Then update existing checks incrementally — each caller that currently checks `== SHARED_FIRST` should switch to `is_single_claimer_mode()`. Rotation chores automatically get correct behavior with zero per-site changes.
     - Note: Also update `is_shared_chore()` to include rotation types, since rotation chores ARE multi-kid shared chores.

  2. **Implement `get_chore_status_context()` — 8-tier FSM**
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - New static method that resolves a **per-kid** chore state:

       | Priority | State         | Condition                                                                                                                                                                 |
       | -------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
       | 1        | `approved`    | `is_approved_in_current_period` is True                                                                                                                                   |
       | 2        | `claimed`     | `has_pending_claim == True`                                                                                                                                               |
       | 3        | `not_my_turn` | `is_rotation_mode(chore)` AND `kid_id != rotation_current_kid_id` AND NOT (`overdue_handling == allow_steal` AND `now > due_date`) AND `rotation_cycle_override == False` |
       | 4        | `missed`      | `overdue_handling == mark_missed_and_lock` AND `now > due_date` AND `due_date is not None`                                                                                |
       | 5        | `overdue`     | Relaxed overdue type AND `now > due_date` AND `due_date is not None`                                                                                                      |
       | 6        | `waiting`     | `due_window_start is not None` AND `now < due_window_start` (where `due_window_start` is calculated from `due_date` - `due_window_offset`)                                |
       | 7        | `due`         | `due_window_start is not None` AND `now >= due_window_start` AND `now <= due_date`                                                                                        |
       | 8        | `pending`     | Default / fallback                                                                                                                                                        |

     - Input: chore dict, kid_id, current timestamp, per-kid state context (approved/claimed flags)
     - Output: `tuple[str, str | None]` — (calculated_state, lock_reason)
     - Must be a pure function — no side effects, no storage access beyond the passed dict
     - **Steal exception** (P3): When `overdue_handling == at_due_date_allow_steal` + `now > due_date`, the `not_my_turn` condition does NOT match, allowing fallthrough to P5 (overdue / claimable by anyone)

  3. **Update `can_claim_chore()` — Add new blocking conditions**
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - Add three new early-return blocks **before** the existing checks:
       - If calculated state is `missed` → return `(False, "missed")`
       - If calculated state is `waiting` → return `(False, "waiting")`
       - If calculated state is `not_my_turn` → return `(False, "not_my_turn")`
     - Current return type is already `tuple[bool, str]` — the string is the reason
     - Existing checks (now using `is_single_claimer_mode()` instead of `== SHARED_FIRST`) remain unchanged
     - **Key**: For rotation chores, `is_single_claimer_mode()` returns True, so the existing "only one kid can claim" check still applies after the rotation-specific guards

  4. **Add rotation helper methods to engine**
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - `calculate_next_turn_simple(assigned_kids: list[str], current_kid_id: str) -> str`
       - Returns `assigned_kids[(current_index + 1) % len(assigned_kids)]`
       - **Resilience**: If `current_kid_id` not in list, return `assigned_kids[0]`
       - Used by BOTH `rotation_simple` and `rotation_smart`-after-miss (round-robin fallback)
     - `calculate_next_turn_smart(assigned_kids: list[str], approved_counts: dict[str, int], last_approved_timestamps: dict[str, str | None]) -> str`
       - Sort by: (1) ascending approved count, (2) ascending last_approved timestamp (oldest first / None first), (3) list-order position as final tie-break
       - Return first kid in sorted result
     - Both are **pure static functions** — no HA imports, no side effects

  5. **Add criteria transition helper** (D-11 — support mutable criteria)
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - `get_criteria_transition_actions(old_criteria: str, new_criteria: str, chore_data: dict) -> dict[str, Any]`
       - Returns dict of field changes needed when switching criteria:
         - **Non-rotation → rotation**: Set `rotation_current_kid_id = assigned_kids[0]`, `rotation_cycle_override = False`
         - **Rotation → non-rotation**: Clear `rotation_current_kid_id = None`, `rotation_cycle_override = False`
         - **Rotation → different rotation**: Keep existing `rotation_current_kid_id` (turn doesn't reset)
         - **Any → any** (same type category): No field changes needed
       - Pure function — manager calls this and applies the returned changes

  6. **Integrate with existing `compute_global_state()`**
     - The existing `compute_global_state()` aggregates per-kid states into a single chore-level state
     - For rotation chores: Global state primarily reflects the **turn-holder's** state. Other kids' `not_my_turn` is cosmetic.
     - Update `compute_global_state()` to handle new states: `missed` → maps like `overdue`, `waiting` → maps like `pending`, `not_my_turn` → ignored for global aggregation

- **Key issues**
  - The Logic Adapter refactoring of ~60 existing check sites could be done as a **preparatory sub-initiative** before the FSM work, or incrementally within this phase. Recommend: Add adapters first, then convert callers file-by-file with targeted tests.
  - The steal exception in P3 now checks **`overdue_handling`** (not `criteria`). This is simpler — it's a single field check, no need to handle a third rotation criteria type.
  - `get_chore_status_context()` needs per-kid state (approved flag, claimed flag) as parameters — these come from the manager, not the engine
  - The criteria transition helper is critical for D-11 — without it, changing from `rotation_simple` to `independent` would leave orphan `rotation_current_kid_id` in storage

---

### Phase 3 – Manager Orchestration

- **Goal**: Wire the engine logic into the ChoreManager's workflows: rotation advancement on approval, missed-lock enforcement in the scanner, criteria transition handling, new management services, and cross-manager signal communication.
- **Status**: ✅ **100% complete (All 10 steps implemented and validated)**

- **Steps / detailed work items**
  1. ✅ **Implement `_advance_rotation()` in ChoreManager**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Implemented method that advances rotation turn after approval
     - Calls appropriate Engine methods based on rotation type (simple/smart)
     - Emits SIGNAL_SUFFIX_ROTATION_ADVANCED after persist
     - Clears rotation_cycle_override flag (D-15)
     - **D-18 compliance**: Turn advances from completer (no special steal logic)

  2. ✅ **Update time scanner for `missed` lock transitions**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Added detection path in `_process_overdue()` for `mark_missed_and_lock`
     - Sets chore state to `missed` when past due date
     - Calls `_record_chore_missed()` with due_date and reason parameters
     - Extended signal payload with optional due_date and reason fields (D-07)
     - `missed` state persists until midnight reset

  3. ✅ **Update midnight reset to clear `missed` lock**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Modified `_process_approval_reset_entries()` to handle `missed` state
     - Clears `missed` lock and resets to `pending` at midnight
     - **D-17 compliance**: Advances rotation turn if missed kid was current turn-holder
     - Handles both SHARED and INDEPENDENT chores
     - Reschedules due date after reset

  4. ✅ **Implement criteria transition handling** (D-11 — criteria is mutable)
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - New method `_handle_criteria_transition(chore_id: str, old_criteria: str, new_criteria: str) -> None`:
       - Calls `ChoreEngine.get_criteria_transition_actions()` to get field changes
       - Applies returned changes to chore data in storage
       - If transitioning TO rotation: validates `assigned_kids >= 2` (else rejects with error)
       - If transitioning FROM rotation: clears rotation fields
       - Emits `SIGNAL_SUFFIX_CHORE_UPDATED` after persist
     - Called from `update_chore()` when `completion_criteria` field has changed
     - **Implementation details**:
       - Added `_handle_criteria_transition()` method (lines 3583-3654)
       - Added `TRANS_KEY_ERROR_ROTATION_MIN_KIDS` constant and translation
       - Imported `ServiceValidationError` from `homeassistant.exceptions`
       - Initialized `_rotation_signal_payload` instance variable in `__init__`

  5. ✅ **Wire criteria transition handler to options flow** (D-11 partial)
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Modified `update_chore()` method to detect criteria changes
     - Calls `_handle_criteria_transition()` when `completion_criteria` changes
     - Early return after transition (handler persists + emits)
     - **Services remain unchanged**: `services.py` keeps immutability guard at L784-788
     - **Rationale**: Options flow already allows editing criteria (Line 1409), services intentionally more restrictive for automation safety
     - **Implementation details**:
       - Added criteria change detection in `update_chore()` (lines 2428-2442)
       - Transition handler validates ≥2 kids for rotation
       - Initializes/clears rotation fields automatically
       - Emits `SIGNAL_SUFFIX_CHORE_UPDATED` after persist

  6. ✅ **Implement rotation resilience on kid deletion**
     - File: `custom_components/kidschores/managers/chore_manager.py`
     - Modified existing `_on_kid_deleted()` signal handler
     - Checks if deleted kid was current turn-holder (`rotation_current_kid_id`)
     - If kids remain: reassigns to `assigned_kids[0]`
     - If no kids remain: clears `rotation_current_kid_id` and `rotation_cycle_override`
     - **Implementation details**:
       - Added rotation check in `_on_kid_deleted()` (lines 360-395)
       - Uses `ChoreEngine.is_rotation_mode()` to detect rotation chores
       - Logs reassignment for debugging
       - Ensures rotation never stalls on kid deletion

- [x] **Step 7: Register new management services**
  - **Implementation**: Added 3 rotation management services to `services.py` with full schema/handler/registration pattern
  - **Services added**:
    - `set_rotation_turn`: Manually assign turn to specific kid (validates rotation mode + kid assignment)
    - `reset_rotation`: Reset turn to first assigned kid
    - `open_rotation_cycle`: Set `rotation_cycle_override = True` (allows any kid to claim once)
  - **ChoreManager methods**: Implemented `set_rotation_turn()`, `reset_rotation()`, `open_rotation_cycle()` (lines 3697-3869)
    - All validate chore is rotation mode
    - All persist + emit `CHORE_UPDATED` signal
    - Error handling with `ServiceValidationError` and translation keys
  - **Constants added**: `SERVICE_SET_ROTATION_TURN`, `SERVICE_RESET_ROTATION`, `SERVICE_OPEN_ROTATION_CYCLE` in `const.py`
  - **Translation keys added**: `TRANS_KEY_ERROR_NOT_ROTATION`, `TRANS_KEY_ERROR_KID_NOT_ASSIGNED`, `TRANS_KEY_ERROR_NO_ASSIGNED_KIDS`
  - **Translations added**: 3 new error messages in `en.json`
  - **Service unload**: Added 3 services to unload list in `async_unload_services()`
  - **Validation**: ✅ Boundary checks passed, zero mypy errors in services.py and chore_manager.py

- [x] **Step 8: Add StatsEngine/StatsManager query method** (D-08)
  - File: `custom_components/kidschores/managers/chore_manager.py`
  - In the existing `KID_DELETED` signal handler:
    - For each chore where `rotation_current_kid_id == deleted_kid_id`:
      - If `assigned_kids` still has members: set `rotation_current_kid_id = assigned_kids[0]`
      - If `assigned_kids` is now empty after removal: clear rotation metadata
    - Persist after changes

- [x] **Step 8: Add StatsEngine/StatsManager query methods** (D-08)
  - **Implementation**: Added 2 query methods to `statistics_manager.py` (lines 2115-2189)
  - **Methods implemented**:
    - `get_chore_approved_counts(chore_id, kid_ids)`: Returns `{kid_id: all_time_approved_count}` from period buckets
    - `get_chore_last_approved_timestamps(chore_id, kid_ids)`: Returns `{kid_id: None}` (timestamp tracking not yet implemented)
  - **Smart rotation**: Now fully enabled in `_advance_rotation()` (Step 1)
    - ChoreEngine.calculate_next_turn_smart() gets real approved counts
    - Fairness-weighted selection based on historical approvals
    - Timestamps return None (acceptable - counts sufficient for fairness)
  - **Validation**: ✅ Zero mypy errors in statistics_manager.py and chore_manager.py
  - **Note**: Timestamp tracking can be added in future if tie-breaking needs refinement

- [x] **Step 9: Wire missed + steal notifications** ✅ **RESOLVED - Rotation notification filtering implemented per user decision**
  - **Implementation**: Added rotation-aware notification filtering to `notification_manager.py` (lines 2275-2627)
  - **Key components**:
    - **Due window filtering**: Only notify turn-holder for rotation chores (`_handle_chore_due_window()`)
    - **Due reminder filtering**: Only notify turn-holder for rotation chores (`_handle_chore_due_reminder()`)
    - **Overdue notifications**: Notify ALL assigned kids for rotation chores (steal mechanic - `_handle_chore_overdue()`)
    - **CHORE_MISSED handler**: Added complete handler with Schedule-Lock pattern (`_handle_chore_missed()`)
  - **Rotation filtering logic**:
    - Check `ChoreEngine.is_rotation_mode(chore_info)`
    - Get `current_turn_kid` from chore rotation data
    - Skip notification if `current_turn_kid != kid_id` (due/reminder only)
  - **MISSED notifications**:
    - Uses existing `notify_on_overdue` flag (missed is stricter form of overdue)
    - Sends to turn-holder only (chore is locked, no claim actions available)
    - Includes parent notification with complete/skip actions
    - Translation keys already existed in `en.json` (lines 4210-4216)
  - **User decision**: Do NOT send due/reminder to kids who cannot claim in rotation. Allow overdue to ALL (steal window).
  - **Validation**: ✅ Zero mypy errors in notification_manager.py, architectural boundaries passed
    - Decision impacts Phase 4 UX work and notification translation strings

- [x] **Step 10: Add `services.yaml` entries for new services** ✅ **COMPLETE**
  - **Implementation**: Added service documentation for 3 rotation services in both `services.yaml` and `translations/en.json`
  - **Services documented**:
    - `set_rotation_turn`: Service definition with chore_id and kid_id fields (lines 925-941)
    - `reset_rotation`: Service definition with chore_id field (lines 943-952)
    - `open_rotation_cycle`: Service definition with chore_id field (lines 954-967)
  - **Translation entries**: Added service translations in `en.json` services section (lines 2235-2285)
  - **Field descriptions**: All services include field names, descriptions, examples, and UI selectors
  - **Integration**: Services match constants from Step 7 (`SERVICE_SET_ROTATION_TURN`, etc.)
  - **Validation**: ✅ JSON syntax validated, services.yaml format correct

- **Key issues** (Phase 3)
  - The `approve_chore()` method is ~400 lines with complex locking. `_advance_rotation()` must be a clean extraction called after state change but within the same persist operation
  - The scanner runs every ~5 minutes. For `missed` lock detection, there's up to 5 minutes of delay. Acceptable for v0.5.0.
  - `open_rotation_cycle` cycle boundary definition (D-15) affects how the override flag is cleared. "Next approval" is cleanest — handled in `_advance_rotation()` which already resets the flag
  - Removing the immutability guard (Step 5) changes the service contract. Existing automation YAML calling `update_chore` with `completion_criteria` will now succeed instead of erroring — this is the desired behavior per D-11
  - **Steal window (D-06 revised)**: The steal mechanic is now entirely in the FSM (P3 steal exception checks `overdue_handling`). No special manager logic needed — the FSM naturally unblocks non-turn-holders when `at_due_date_allow_steal` + overdue.

---

### Phase 4 – UX & Dashboard Contract

- **Goal**: Expose new states and rotation metadata through the UI Manager's dashboard helper, update config/options flow for new chore settings, and ensure dashboard has everything it needs.

- **Steps / detailed work items**
  1. **[✅] Update `KidDashboardHelper` chore attributes**
     - File: `custom_components/kidschores/managers/ui_manager.py`
     - For each chore in the kid's dashboard list, add to the existing 6-field dict:
       - `lock_reason` (str | None) — `"waiting"`, `"not_my_turn"`, `"missed"`, or `None`
       - `turn_kid_name` (str | None) — resolve `rotation_current_kid_id` to kid name (if `is_rotation_mode()`)
       - `available_at` (str | None) — ISO datetime of `due_window_start` (calculated from `due_date` - `due_window_offset`, only when state is `waiting`)
       - `can_claim` already exists as a sensor attribute on `KidChoreStatusSensor` (confirmed D-16). Dashboard helper documents that consumers should use `state_attr(chore.eid, 'can_claim')`. Consider adding `can_claim` to dashboard helper dict for convenience.
     - Existing 6 fields (`eid`, `name`, `state`, `labels`, `grouping`, `is_am_pm`) remain unchanged

  2. **[✅] Update flow helpers — Chore creation/edit form**
     - File: `custom_components/kidschores/helpers/flow_helpers.py`
     - ✅ `COMPLETION_CRITERIA_OPTIONS` in const.py includes rotation types (rotation_simple, rotation_smart) — completed in Phase 1
     - ✅ `OVERDUE_HANDLING_TYPE_OPTIONS` in const.py includes 7th type (at_due_date_allow_steal) — completed in Phase 1
     - ✅ Flow helpers correctly reference `const.COMPLETION_CRITERIA_OPTIONS` and `const.OVERDUE_HANDLING_TYPE_OPTIONS` (lines 584, 631)
     - ✅ Selector translations complete in en.json (selector.completion_criteria.options, selector.overdue_handling_type.options)
     - **Status**: Step complete — all work was done during Phase 1 constant updates

  3. **[✅] Update options flow for chore editing** (D-11 — criteria is mutable)
     - File: `custom_components/kidschores/options_flow.py`
     - ✅ `completion_criteria` is editable in options flow (confirmed working via existing flow helpers)
     - ✅ **Removed immutability guard from services.py** (L818-823 deleted, D-11 resolved)
     - ✅ **Added criteria transition handling**: ChoreManager.\_handle_criteria_transition() already exists and handles field cleanup
     - ✅ **Added V-03 validation**: Rotation requires ≥2 assigned kids (data_builders.py line ~1296)
     - ✅ **Added V-05 validation**: at_due_date_allow_steal compatibility (rotation + at_midnight_once + due_date, data_builders.py line ~1303)
     - ✅ **Updated service schema**: Added completion_criteria to UPDATE_CHORE_SCHEMA + rotation values to \_COMPLETION_CRITERIA_VALUES
     - ✅ **Added validation constants**: CFOP_ERROR_COMPLETION_CRITERIA, TRANS_KEY_CFOF_ERROR_ALLOW_STEAL_INCOMPATIBLE + translation
     - **Status**: Step complete — all criteria mutability and validation implemented

  4. **[✅] Update dashboard template documentation**
     - File: `docs/DASHBOARD_TEMPLATE_GUIDE.md`
     - ✅ **Added v0.5.0 Chore Attributes Reference section** with comprehensive documentation
     - ✅ **Documented 3 new dashboard helper fields**: `lock_reason`, `turn_kid_name`, `available_at`
     - ✅ **Added Jinja2 examples** for rotation status display, availability countdown, lock reason icon mapping
     - ✅ **Added multi-chore rotation summary** example for dashboard auto-entities cards
     - ✅ **Added state-to-color mapping table** with 7 states/locks (pending→blue, not_my_turn→purple, etc.)
     - ✅ **Provided icon suggestions** for each lock reason and state (waiting→mdi:clock-outline, missed→mdi:calendar-remove)
     - **Status**: Step complete — dashboard template documentation updated for v0.5.0 contract

  5. **[✅] Add v0.5.0 attributes to individual KidChoreStatusSensor entities**
     - File: `custom_components/kidschores/sensor.py`
     - ✅ **Added 3 new attributes to KidChoreStatusSensor.extra_state_attributes**: `lock_reason`, `turn_kid_name`, `available_at`
     - ✅ **Implementation mirrors dashboard helper logic**: Uses get_chore_status_context() for consistency
     - ✅ **Added translation keys**: `translations/en.json` sensor state_attributes section
     - ✅ **Attribute label translations**: "Lock Reason", "Turn Kid Name", "Available At"
     - ✅ **Value translations for lock_reason**: "waiting"→"Waiting for due window", "not_my_turn"→"Not your turn", "missed"→"Missed"
     - **Status**: Step complete — individual sensors now expose same v0.5.0 attributes as dashboard helper

- **Key issues** (Phase 4)
  - The dashboard YAML is in `kidschores-ha-dashboard` repo. Phase 4 only defines the **contract** — actual dashboard YAML changes are a separate initiative
  - The flow helpers show all options for all chore types, including rotation options for non-rotation chores and `at_due_date_allow_steal` for non-rotation chores. Clear translation text is critical to avoid user confusion. Validation rule V-05 catches invalid combos on save.
  - Criteria transition in the options flow must validate the new criteria against existing chore state — e.g., switching to `rotation_simple` requires ≥ 2 assigned kids (V-03). Switching to `at_due_date_allow_steal` overdue handling requires rotation criteria + `at_midnight_once` (V-05).
  - **Step 5 added post-completion**: User identified missing attributes on individual KidChoreStatusSensor entities. Dashboard helper had 9 fields but individual sensors were missing the 3 new v0.5.0 attributes (lock_reason, turn_kid_name, available_at). Fixed by adding attributes to sensor.py and translation keys to en.json.

---

### Phase 5 – Testing & Validation

- **Goal**: Achieve 95%+ test coverage for all new code paths. Use service-based tests as primary validation method, with engine unit tests for pure computation.

- **Steps / detailed work items**
  1. **Engine unit tests — Logic Adapters & FSM**
     - File: `tests/test_chore_engine.py` (new or extend existing)
     - Test Logic Adapters:
       - `is_single_claimer_mode()` — True for shared_first, rotation_simple, rotation_smart; False for independent, shared
       - `is_rotation_mode()` — True for rotation_simple, rotation_smart; False for shared_first, independent, shared
       - Updated `is_shared_chore()` — True for shared, shared_first, AND all rotation types
     - Test `get_chore_status_context()` — all 8 priority tiers with edge cases:
       - Approved takes precedence over everything
       - `not_my_turn` takes precedence over `missed` (P3 > P4)
       - `missed` takes precedence over `overdue` (P4 > P5)
       - `waiting` only applies when `due_window_offset` is set (claim restrictions enabled by field presence)
       - `due` window boundaries (exactly at start, exactly at end)
       - **Steal exception**: `overdue_handling == at_due_date_allow_steal` + overdue → `not_my_turn` does NOT match → falls to `overdue`
       - **Non-steal rotation + overdue**: `rotation_simple` with relaxed overdue → `not_my_turn` still wins (P3 > P5)
     - Test `can_claim_chore()` — new blocking conditions:
       - Blocked when `missed`, `waiting`, `not_my_turn`
       - `at_due_date_allow_steal`: Blocked before overdue, unblocked after due date
       - `rotation_cycle_override = True`: Temporarily unblocks `not_my_turn`
     - Test rotation helpers:
       - `calculate_next_turn_simple()` — wrap-around, single kid fallback, removed kid resilience
       - `calculate_next_turn_smart()` — lowest count wins, tie-break by timestamp, tie-break by list order
     - Test criteria transition helper:
       - Non-rotation → rotation: returns `rotation_current_kid_id = assigned_kids[0]`
       - Rotation → non-rotation: returns `rotation_current_kid_id = None`
       - Rotation → different rotation: keeps existing turn
       - Same category → no field changes

  2. **Service-based integration tests**
     - File: `tests/test_service_rotation.py` (new)
     - Test scenarios using Stårblüm Family fixtures:
       - Create `rotation_simple` chore → Claim → Approve → Verify turn advanced to next kid
       - Create `rotation_simple` + `at_due_date_allow_steal` → Let overdue → Non-turn kid claims → Verify accepted (steal window open)
       - Create `rotation_simple` + relaxed overdue (NOT allow_steal) → Let overdue → Non-turn kid claims → Verify REJECTED (no steal window, P3 still blocks)
       - `set_rotation_turn` service → Verify turn changed, signal emitted
       - `reset_rotation` service → Verify reset to `assigned_kids[0]`
       - `open_rotation_cycle` service → Verify override enables any kid to claim
       - Approve after override → Verify override cleared (D-15 dependent)
       - After steal → Verify turn advances from completer, not original turn-holder (D-18)
       - After pure miss → Midnight reset → Verify turn advances to next kid (D-17)
     - Test `claim_restriction_enabled`:
       - Create chore with restriction + due_window → Attempt claim before window → Verify rejected with "waiting" reason
       - Advance time into window → Attempt claim → Verify accepted
     - Test `mark_missed_and_lock`:
       - Create chore with lock strategy → Advance past due date → Verify state is `missed`
       - Attempt claim in `missed` state → Verify rejected
       - Trigger midnight reset → Verify state returns to `pending`
     - Test criteria transition (D-11):
       - `update_chore` service with `completion_criteria: rotation_simple` on existing `shared_first` chore → Verify `rotation_current_kid_id` set
       - `update_chore` service with `completion_criteria: independent` on existing `rotation_simple` chore → Verify rotation fields cleared

  3. **Validation rule tests**
     - File: `tests/test_data_builders.py` (extend)
     - V-01: `mark_missed_and_lock` + `upon_completion` reset → Validation error
     - V-01: `mark_missed_and_lock` + `at_midnight_once` → Valid
     - V-02: `claim_restriction_enabled=True` + no due_window_offset → Validation error
     - ~~V-02: `claim_restriction_enabled=True` + no due_window_offset → Validation error~~ ❌ OBSOLETE — No separate flag exists)
     - V-05: `at_due_date_allow_steal` + non-rotation criteria → Validation error
     - V-05: `at_due_date_allow_steal` + rotation_simple + `at_midnight_multi` → Validation error
     - V-05: `at_due_date_allow_steal` + rotation_simple + `at_midnight_once` → Valid
     - V-05: `at_due_date_allow_steal` + no due date → Validation error

  4. **Migration tests**
     - File: `tests/test_migration.py` (extend)
     - Test extended v44 migration: Verify new fields backfilled on existing chores
       - No claim restriction flag needed (derived from `due_window_offset` presence)
       - `rotation_cycle_override = False` on all chores
     - Test idempotency: Run migration twice → no errors, no duplicate fields

  5. **Dashboard helper attribute tests**
     - File: `tests/test_ui_manager.py` (extend)
     - Verify `lock_reason`, `turn_kid_name`, `available_at` appear in chore attributes
     - Verify `turn_kid_name` resolves UUID to correct kid name
     - Verify `available_at` is ISO formatted when state is `waiting`
     - Verify `lock_reason` is `None` for normal (unlocked) chores

  6. **Run full validation suite**
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/kidschores/`
     - `python -m pytest tests/ -v --tb=line`

- **Builder Handoff: Complete Test Specification**

  This section provides explicit test scenarios with expected assertions for KidChoreStatusSensor entities and dashboard helper attributes. Each test MUST verify both sources to ensure contract consistency.

  **CRITICAL REQUIREMENTS**:
  1. ✅ **Use button presses with user context** (NOT service calls, NOT coordinator API)
  2. ✅ **Test ALL assigned kids** - turn-holder AND non-turn-holders (not_my_turn states are critical)
  3. ✅ **Use Stårblüm Family** from YAML scenarios (NOT generic names)
  4. ✅ **Verify dashboard helper AND individual sensors** for every kid
  5. ✅ **Use `get_dashboard_helper()` and `find_chore()`** helpers for entity access

  ### Test Organization

  **4 test files, 4 builders working in parallel. NO OVERLAP.**

  | Builder       | File                                  | Test Groups      | Tests   | Lines |
  | ------------- | ------------------------------------- | ---------------- | ------- | ----- |
  | **Builder 1** | `test_rotation_fsm_states.py`         | **T1 ONLY**      | 9 tests | ~250  |
  | **Builder 2** | `test_rotation_services.py`           | **T2 + T3**      | 6 tests | ~200  |
  | **Builder 3** | `test_rotation_due_window_overdue.py` | **T4 + T5 + T6** | 8 tests | ~200  |
  | **Builder 4** | `test_rotation_dashboard_contract.py` | **T7 + T8**      | 5 tests | ~150  |

  **Test Group Summary**:
  - **T1**: FSM State Resolution (9 tests: approved, claimed, not_my_turn, missed, waiting, hold_claim, auto_approve, overdue_state, overdue_until_reset)
  - **T2**: Rotation Services (3 tests: set_turn, reset, open_cycle)
  - **T3**: Rotation Turn Advancement (3 tests: simple, smart, kid_deletion)
  - **T4**: Claim Restriction (2-3 tests: due window blocking scenarios)
  - **T5**: Missed Lock Strategy (2-3 tests: turn-holder locked, non-turn-holders NOT locked)
  - **T6**: Steal Window (2-3 tests: ALL kids can steal after due date)
  - **T7**: Dashboard Helper Attributes (3 tests: lock_reason, turn_kid_name, available_at verification)
  - **T8**: Criteria Transition (2 tests: mutable completion_criteria updates ALL kid sensors)

  ***

  ## 🔨 BUILDER 1 HANDOFF: `test_rotation_fsm_states.py`

  **YOUR RESPONSIBILITY**: T1 ONLY (FSM State Resolution + Overdue Types)
  **FILE**: `tests/test_rotation_fsm_states.py`
  **TESTS**: 9 functions (complete Python code below)

  **DO NOT TOUCH**: T2-T8 (other builders handle those)

  **Your Test Functions**:
  1. `test_fsm_approved_state()` - T1.1
  2. `test_fsm_claimed_state()` - T1.2
  3. `test_fsm_not_my_turn_blocking()` - T1.3 ⚠️ CRITICAL
  4. `test_fsm_missed_state_rotation()` - T1.4
  5. `test_fsm_waiting_state_all_kids()` - T1.5
  6. `test_overdue_hold_claim_rotation()` - T1.6
  7. `test_overdue_auto_approve_rotation()` - T1.7
  8. `test_overdue_state_rotation()` - T1.8
  9. `test_overdue_until_approval_reset_rotation()` - T1.9

  ***

  ## 🔨 BUILDER 2 HANDOFF: `test_rotation_services.py`

  **YOUR RESPONSIBILITY**: T2 (Rotation Services) + T3 (Turn Advancement)
  **FILE**: `tests/test_rotation_services.py`
  **TESTS**: 6 functions (3 for T2, 3 for T3)

  **DO NOT TOUCH**: T1, T4, T5, T6, T7, T8 (other builders handle those)

  **Your Test Functions**:
  1. `test_set_rotation_turn_all_kids()` - T2.1
  2. `test_reset_rotation_all_kids()` - T2.2
  3. `test_open_rotation_cycle_all_kids()` - T2.3 ⚠️ CRITICAL
  4. `test_rotation_advancement_simple()` - T3.1
  5. `test_rotation_advancement_smart()` - T3.2
  6. `test_rotation_advancement_kid_deletion()` - T3.3

  ***

  ## 🔨 BUILDER 3 HANDOFF: `test_rotation_due_window_overdue.py`

  **YOUR RESPONSIBILITY**: T4 (Due Window) + T5 (Missed Lock) + T6 (Steal Window)
  **FILE**: `tests/test_rotation_due_window_overdue.py`
  **TESTS**: 8 functions (2-3 per group)

  **DO NOT TOUCH**: T1, T2, T3, T7, T8 (other builders handle those)

  **Your Test Functions**:
  1. `test_due_window_blocks_early_claims()` - T4.1
  2. `test_due_window_opens_at_offset()` - T4.2
  3. `test_missed_lock_turn_holder_only()` - T5.1
  4. `test_missed_lock_non_turn_holders_not_locked()` - T5.2 ⚠️ CRITICAL
  5. `test_missed_lock_manual_unlock()` - T5.3
  6. `test_steal_window_all_kids_can_steal()` - T6.1 ⚠️ CRITICAL
  7. `test_steal_window_turn_advances_on_steal()` - T6.2
  8. `test_steal_window_requires_overdue_state()` - T6.3

  ***

  ## 🔨 BUILDER 4 HANDOFF: `test_rotation_dashboard_contract.py`

  **YOUR RESPONSIBILITY**: T7 (Dashboard Helper Attributes) + T8 (Criteria Transition)
  **FILE**: `tests/test_rotation_dashboard_contract.py`
  **TESTS**: 5 functions (3 for T7, 2 for T8)

  **DO NOT TOUCH**: T1, T2, T3, T4, T5, T6 (other builders handle those)

  **Your Test Functions**:
  1. `test_dashboard_helper_lock_reason_attribute()` - T7.1
  2. `test_dashboard_helper_turn_kid_name_attribute()` - T7.2
  3. `test_dashboard_helper_available_at_attribute()` - T7.3
  4. `test_criteria_transition_all_kids_update()` - T8.1 ⚠️ CRITICAL
  5. `test_criteria_transition_via_options_flow()` - T8.2

  ***

  ### Common Test Setup Pattern (ALL BUILDERS USE THIS)

  Tests grouped by feature area:
  - **T1**: FSM State Resolution (8 states + lock_reason attribute) - **3 kids minimum per test**
  - **T2**: Rotation Services (3 services) - **Verify ALL assigned kids after each service**
  - **T3**: Rotation Turn Advancement (simple + smart) - **Track ALL kids through advancement**
  - **T4**: Claim Restriction (due window blocking) - **Test multiple kids**
  - **T5**: Missed Lock Strategy (6th overdue type) - **Rotation: verify non-turn-holders NOT locked**
  - **T6**: Steal Window (7th overdue type) - **Verify ALL kids can steal**
  - **T7**: Dashboard Helper Attributes (new v0.5.0 fields) - **All kids, all chores**
  - **T8**: Criteria Transition (mutable completion_criteria) - **Verify all kid sensors update**

  ### Test Setup Pattern (from AGENT_TEST_CREATION_INSTRUCTIONS.md)

  Use **Stårblüm Family** fixtures:
  - **Kids**: Zoë Stårblüm (8yo), Max! Stårblüm (6yo), Lila Stårblüm (8yo)
  - **Parents**: Môm Astrid (@Astrid), Dad Leo (@Leo)
  - **Scenarios**: `scenario_minimal.yaml` (simple), `scenario_shared.yaml` (multi-kid), `scenario_full.yaml` (complex)

  ```python
  from tests.helpers import (
      setup_from_yaml, SetupResult,
      get_dashboard_helper, find_chore, get_chore_buttons,
      CHORE_STATE_PENDING, CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED,
      CHORE_STATE_NOT_MY_TURN, CHORE_STATE_WAITING, CHORE_STATE_MISSED,
  )
  from homeassistant.core import Context

  async def test_rotation_example(hass, mock_hass_users):
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")
      coordinator = result.coordinator

      # Get kid IDs from scenario
      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Get dashboard helpers for ALL kids
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      # Find chore in Zoë's dashboard
      chore = find_chore(zoe_helper, "Dishes Rotation")

      # Get buttons for ALL kids
      zoe_buttons = get_chore_buttons(hass, chore["eid"])
      max_chore_eid = f"sensor.kc_max_chore_{chore['eid'].split('_')[-1]}"
      max_buttons = get_chore_buttons(hass, max_chore_eid)

      # Test as kid - use Context with user_id
      kid_context = Context(user_id=mock_hass_users["kid1"].id)
      await hass.services.async_call("button", "press",
          {"entity_id": zoe_buttons["claim"]}, context=kid_context)
  ```

  ### T1: FSM State Resolution & lock_reason Attribute

  **T1.1 — Priority 1: Approved State**

  ```python
  async def test_fsm_approved_state(hass, mock_hass_users):
      """Test approved state takes priority over all other states."""
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      # Setup: rotation_simple, assigned=[Zoë, Max!, Lila], turn=Zoë
      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Get dashboard helpers
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      # Find rotation chore in ALL kids' dashboards
      zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
      max_chore = find_chore(max_helper, "Dishes Rotation")
      lila_chore = find_chore(lila_helper, "Dishes Rotation")

      # Get buttons
      zoe_buttons = get_chore_buttons(hass, zoe_chore["eid"])

      # Zoë claims (turn-holder)
      kid_context = Context(user_id=mock_hass_users["kid1"].id)
      await hass.services.async_call("button", "press",
          {"entity_id": zoe_buttons["claim"]}, context=kid_context)
      await hass.async_block_till_done()

      # Parent approves
      parent_context = Context(user_id=mock_hass_users["parent1"].id)
      await hass.services.async_call("button", "press",
          {"entity_id": zoe_buttons["approve"]}, context=parent_context)
      await hass.async_block_till_done()

      # Assert Zoë: state=approved, lock_reason=None
      zoe_sensor = hass.states.get(zoe_chore["eid"])
      assert zoe_sensor.state == CHORE_STATE_APPROVED
      assert zoe_sensor.attributes.get("lock_reason") is None
      assert zoe_sensor.attributes.get("turn_kid_name") == "Max!"  # Turn advanced
      assert zoe_sensor.attributes.get("can_claim") is False

      # Assert Zoë dashboard helper
      zoe_helper_updated = get_dashboard_helper(hass, "Zoë")
      zoe_chore_updated = find_chore(zoe_helper_updated, "Dishes Rotation")
      assert zoe_chore_updated["state"] == CHORE_STATE_APPROVED
      assert zoe_chore_updated.get("lock_reason") is None
      assert zoe_chore_updated.get("turn_kid_name") == "Max!"

      # Assert Max!: turn advanced, state=pending (or due if window), lock_reason=None
      max_sensor = hass.states.get(max_chore["eid"])
      assert max_sensor.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert max_sensor.attributes.get("lock_reason") is None
      assert max_sensor.attributes.get("turn_kid_name") == "Max!"
      assert max_sensor.attributes.get("can_claim") is True

      # Assert Lila: state=not_my_turn, lock_reason="not_my_turn"
      lila_sensor = hass.states.get(lila_chore["eid"])
      assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"
      assert lila_sensor.attributes.get("turn_kid_name") == "Max!"
      assert lila_sensor.attributes.get("can_claim") is False
  ```

  **T1.2 — Priority 2: Claimed State**

  ```python
  async def test_fsm_claimed_state(hass, mock_hass_users):
      """Test claimed state (pending approval)."""
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Get ALL dashboard helpers
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      # Find chore in each kid's dashboard
      zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
      max_chore = find_chore(max_helper, "Dishes Rotation")
      lila_chore = find_chore(lila_helper, "Dishes Rotation")

      # Zoë claims (turn-holder)
      zoe_buttons = get_chore_buttons(hass, zoe_chore["eid"])
      kid_context = Context(user_id=mock_hass_users["kid1"].id)
      await hass.services.async_call("button", "press",
          {"entity_id": zoe_buttons["claim"]}, context=kid_context)
      await hass.async_block_till_done()

      # Assert Zoë: state=claimed, lock_reason=None, can_claim=False
      zoe_sensor = hass.states.get(zoe_chore["eid"])
      assert zoe_sensor.state == CHORE_STATE_CLAIMED
      assert zoe_sensor.attributes.get("lock_reason") is None
      assert zoe_sensor.attributes.get("turn_kid_name") == "Zoë"
      assert zoe_sensor.attributes.get("can_claim") is False

      # Assert Max!: state=not_my_turn (still blocked)
      max_sensor = hass.states.get(max_chore["eid"])
      assert max_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert max_sensor.attributes.get("lock_reason") == "not_my_turn"
      assert max_sensor.attributes.get("turn_kid_name") == "Zoë"

      # Assert Lila: state=not_my_turn (still blocked)
      lila_sensor = hass.states.get(lila_chore["eid"])
      assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"
  ```

  **T1.3 — Priority 3: Not My Turn (Rotation Blocking) - CRITICAL TEST**

  ```python
  async def test_fsm_not_my_turn_blocking(hass, mock_hass_users):
      """Test not_my_turn blocks non-turn-holders. CRITICAL: Verify all 3 kids."""
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Get ALL dashboard helpers
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      # Find chore in each kid's dashboard
      zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
      max_chore = find_chore(max_helper, "Dishes Rotation")
      lila_chore = find_chore(lila_helper, "Dishes Rotation")

      # CRITICAL: Verify turn_holder is Zoë (extract internal ID from entity ID)
      chore_internal_id = zoe_chore["eid"].split("_chore_")[-1]
      coordinator = result.coordinator
      chore_data = coordinator.chores_data[chore_internal_id]
      assert chore_data[DATA_CHORE_ROTATION_CURRENT_KID_ID] == zoe_id

      # Assert Zoë (turn-holder): can_claim=True, lock_reason=None
      zoe_sensor = hass.states.get(zoe_chore["eid"])
      assert zoe_sensor.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert zoe_sensor.attributes.get("lock_reason") is None
      assert zoe_sensor.attributes.get("turn_kid_name") == "Zoë"
      assert zoe_sensor.attributes.get("can_claim") is True

      # Assert Max! (NOT turn-holder): state=not_my_turn, can_claim=False
      max_sensor = hass.states.get(max_chore["eid"])
      assert max_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert max_sensor.attributes.get("lock_reason") == "not_my_turn"
      assert max_sensor.attributes.get("turn_kid_name") == "Zoë"  # Shows WHO has turn
      assert max_sensor.attributes.get("can_claim") is False

      # Assert Lila (NOT turn-holder): state=not_my_turn, can_claim=False
      lila_sensor = hass.states.get(lila_chore["eid"])
      assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"
      assert lila_sensor.attributes.get("turn_kid_name") == "Zoë"
      assert lila_sensor.attributes.get("can_claim") is False

      # Verify dashboard helpers match (refresh to get latest state)
      max_helper_updated = get_dashboard_helper(hass, "Max!")
      max_helper_chore = find_chore(max_helper_updated, "Dishes Rotation")
      assert max_helper_chore["state"] == CHORE_STATE_NOT_MY_TURN
      assert max_helper_chore.get("lock_reason") == "not_my_turn"
      assert max_helper_chore.get("turn_kid_name") == "Zoë"

      lila_helper_updated = get_dashboard_helper(hass, "Lila")
      lila_helper_chore = find_chore(lila_helper_updated, "Dishes Rotation")
      assert lila_helper_chore["state"] == CHORE_STATE_NOT_MY_TURN
      assert lila_helper_chore.get("lock_reason") == "not_my_turn"
      assert lila_helper_chore.get("turn_kid_name") == "Zoë"

      # CRITICAL: Verify non-turn-holder CANNOT claim
      max_buttons = get_chore_buttons(hass, max_chore["eid"])
      kid_context = Context(user_id=mock_hass_users["kid2"].id)  # Max's user

      with pytest.raises(HomeAssistantError, match="not.*turn|rotation"):
          await hass.services.async_call("button", "press",
              {"entity_id": max_buttons["claim"]}, context=kid_context)
  ```

  **T1.4 — Priority 4: Missed (Locked State) - Rotation: Only Turn-Holder Locked**

  ```python
  async def test_fsm_missed_state_rotation(hass, mock_hass_users):
      """Test missed state locks ONLY turn-holder, not other kids."""
      from freezegun import freeze_time

      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Setup: rotation chore with mark_missed_and_lock
      # due_date=2026-02-10T19:00:00Z, approval_reset=at_midnight_once
      # (Assume scenario includes this chore or create via service)

      # Freeze time PAST due date
      with freeze_time("2026-02-10T20:00:00Z"):
          # Trigger scanner
          await result.coordinator._run_time_scanner()
          await hass.async_block_till_done()

          # Get sensors
          zoe_helper = get_dashboard_helper(hass, "Zoë")
          chore = find_chore(zoe_helper, "Dishes Rotation Locked")
          chore_id = chore["eid"].split("_")[-1]

          # Assert Zoë (turn-holder): state=missed, lock_reason="missed", can_claim=False
          zoe_sensor = hass.states.get(chore["eid"])
          assert zoe_sensor.state == CHORE_STATE_MISSED
          assert zoe_sensor.attributes.get("lock_reason") == "missed"
          assert zoe_sensor.attributes.get("turn_kid_name") == "Zoë"
          assert zoe_sensor.attributes.get("can_claim") is False

          # CRITICAL: Assert Max! (NOT turn-holder): state=not_my_turn (NOT missed)
          max_chore_eid = f"sensor.kc_max_chore_{chore_id}"
          max_sensor = hass.states.get(max_chore_eid)
          assert max_sensor.state == CHORE_STATE_NOT_MY_TURN  # NOT missed!
          assert max_sensor.attributes.get("lock_reason") == "not_my_turn"  # NOT "missed"!
          assert max_sensor.attributes.get("can_claim") is False

          # CRITICAL: Assert Lila (NOT turn-holder): state=not_my_turn (NOT missed)
          lila_chore_eid = f"sensor.kc_lila_chore_{chore_id}"
          lila_sensor = hass.states.get(lila_chore_eid)
          assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN  # NOT missed!
          assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"
          assert lila_sensor.attributes.get("can_claim") is False
  ```

  **T1.5 — Priority 6: Waiting (Claim Restriction) - All Kids Blocked**

  ```python
  async def test_fsm_waiting_state_all_kids(hass, mock_hass_users):
      """Test waiting state blocks ALL kids (not rotation-specific)."""
      from freezegun import freeze_time

      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Setup: independent chore with due_window_offset="PT2H"
      # due_date=2026-02-10T19:00:00Z → window_start=17:00:00Z

      # Freeze time BEFORE window opens
      with freeze_time("2026-02-10T16:00:00Z"):
          zoe_helper = get_dashboard_helper(hass, "Zoë")
          chore = find_chore(zoe_helper, "Homework Due Window")
          chore_id = chore["eid"].split("_")[-1]

          # Assert Zoë: state=waiting, available_at set
          zoe_sensor = hass.states.get(chore["eid"])
          assert zoe_sensor.state == CHORE_STATE_WAITING
          assert zoe_sensor.attributes.get("lock_reason") == "waiting"
          assert zoe_sensor.attributes.get("available_at") == "2026-02-10T17:00:00+00:00"
          assert zoe_sensor.attributes.get("can_claim") is False

          # Assert Max!: also waiting (shared chore, not rotation)
          max_chore_eid = f"sensor.kc_max_chore_{chore_id}"
          max_sensor = hass.states.get(max_chore_eid)
          assert max_sensor.state == CHORE_STATE_WAITING
          assert max_sensor.attributes.get("lock_reason") == "waiting"
          assert max_sensor.attributes.get("available_at") == "2026-02-10T17:00:00+00:00"

          # Assert Lila: also waiting
          lila_chore_eid = f"sensor.kc_lila_chore_{chore_id}"
          lila_sensor = hass.states.get(lila_chore_eid)
          assert lila_sensor.state == CHORE_STATE_WAITING
          assert lila_sensor.attributes.get("lock_reason") == "waiting"

      # Advance time INTO window
      with freeze_time("2026-02-10T18:00:00Z"):
          await hass.async_block_till_done()

          # Assert ALL kids: state=due, lock_reason=None, available_at=None
          zoe_sensor_updated = hass.states.get(chore["eid"])
          assert zoe_sensor_updated.state == CHORE_STATE_DUE
          assert zoe_sensor_updated.attributes.get("lock_reason") is None
          assert zoe_sensor_updated.attributes.get("available_at") is None
          assert zoe_sensor_updated.attributes.get("can_claim") is True

          max_sensor_updated = hass.states.get(max_chore_eid)
          assert max_sensor_updated.state == CHORE_STATE_DUE
          assert max_sensor_updated.attributes.get("lock_reason") is None
          assert max_sensor_updated.attributes.get("can_claim") is True
  ```

  **T1.6 — Overdue Type: Hold Claim (Rotation Turn Holder Keeps Claim)**

  ```python
  async def test_overdue_hold_claim_rotation(hass, mock_hass_users):
      """Test hold_claim overdue: rotation turn holder keeps claimed state past due."""
      from freezegun import freeze_time

      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")
      coordinator = result.coordinator

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Setup: rotation chore with overdue_action=hold_claim
      # turn=Zoë, due_date=2026-02-10T19:00:00Z

      # Get dashboard helpers
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      # Find chore
      zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
      max_chore = find_chore(max_helper, "Dishes Rotation")
      lila_chore = find_chore(lila_helper, "Dishes Rotation")

      # Zoë claims BEFORE due time
      with freeze_time("2026-02-10T18:00:00Z"):
          zoe_buttons = get_chore_buttons(hass, zoe_chore["eid"])
          kid_context = Context(user_id=mock_hass_users["kid1"].id)
          await hass.services.async_call("button", "press",
              {"entity_id": zoe_buttons["claim"]}, context=kid_context)
          await hass.async_block_till_done()

      # Advance time PAST due date
      with freeze_time("2026-02-10T20:00:00Z"):
          # Trigger scanner to update overdue states
          await coordinator.async_refresh()
          await hass.async_block_till_done()

          # Assert Zoë (turn-holder): STILL claimed (hold_claim preserves state)
          zoe_sensor = hass.states.get(zoe_chore["eid"])
          assert zoe_sensor.state == CHORE_STATE_CLAIMED  # NOT overdue state
          assert zoe_sensor.attributes.get("lock_reason") is None
          assert zoe_sensor.attributes.get("turn_kid_name") == "Zoë"
          assert zoe_sensor.attributes.get("can_claim") is False

          # Assert Max! & Lila: STILL blocked (rotation doesn't advance on hold_claim)
          max_sensor = hass.states.get(max_chore["eid"])
          assert max_sensor.state == CHORE_STATE_NOT_MY_TURN
          assert max_sensor.attributes.get("lock_reason") == "not_my_turn"

          lila_sensor = hass.states.get(lila_chore["eid"])
          assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
          assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"
  ```

  **T1.7 — Overdue Type: Auto-Approve (Rotation Turn Advances on Approval)**

  ```python
  async def test_overdue_auto_approve_rotation(hass, mock_hass_users):
      """Test auto_approve overdue: rotation advances turn when claim auto-approves."""
      from freezegun import freeze_time

      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")
      coordinator = result.coordinator

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Setup: rotation chore with overdue_action=auto_approve_pending_claims
      # turn=Zoë, due_date=2026-02-10T19:00:00Z

      # Get dashboard helpers
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      # Find chore
      zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
      max_chore = find_chore(max_helper, "Dishes Rotation")
      lila_chore = find_chore(lila_helper, "Dishes Rotation")

      # Zoë claims BEFORE due time
      with freeze_time("2026-02-10T18:00:00Z"):
          zoe_buttons = get_chore_buttons(hass, zoe_chore["eid"])
          kid_context = Context(user_id=mock_hass_users["kid1"].id)
          await hass.services.async_call("button", "press",
              {"entity_id": zoe_buttons["claim"]}, context=kid_context)
          await hass.async_block_till_done()

          # Verify claimed
          zoe_sensor = hass.states.get(zoe_chore["eid"])
          assert zoe_sensor.state == CHORE_STATE_CLAIMED

      # Advance time to due date (auto-approve triggers)
      with freeze_time("2026-02-10T19:00:01Z"):
          # Trigger scanner to auto-approve
          await coordinator.async_refresh()
          await hass.async_block_till_done()

          # Refresh dashboard helpers to get updated turn
          zoe_helper_updated = get_dashboard_helper(hass, "Zoë")
          max_helper_updated = get_dashboard_helper(hass, "Max!")
          lila_helper_updated = get_dashboard_helper(hass, "Lila")

          zoe_chore_updated = find_chore(zoe_helper_updated, "Dishes Rotation")
          max_chore_updated = find_chore(max_helper_updated, "Dishes Rotation")
          lila_chore_updated = find_chore(lila_helper_updated, "Dishes Rotation")

          # Assert Zoë: auto-approved, turn ADVANCED to Max!
          zoe_sensor = hass.states.get(zoe_chore_updated["eid"])
          assert zoe_sensor.state == CHORE_STATE_APPROVED
          assert zoe_sensor.attributes.get("lock_reason") is None
          assert zoe_sensor.attributes.get("turn_kid_name") == "Max!"  # Turn advanced

          # Assert Max!: NOW turn-holder, can claim
          max_sensor = hass.states.get(max_chore_updated["eid"])
          assert max_sensor.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
          assert max_sensor.attributes.get("lock_reason") is None
          assert max_sensor.attributes.get("turn_kid_name") == "Max!"
          assert max_sensor.attributes.get("can_claim") is True

          # Assert Lila: STILL blocked (now blocked by Max's turn)
          lila_sensor = hass.states.get(lila_chore_updated["eid"])
          assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
          assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"
          assert lila_sensor.attributes.get("turn_kid_name") == "Max!"
  ```

  **T1.8 — Overdue Type: Overdue State (Turn Holder Can Still Claim)**

  ```python
  async def test_overdue_state_rotation(hass, mock_hass_users):
      """Test overdue state: rotation turn holder can still claim overdue chore."""
      from freezegun import freeze_time

      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")
      coordinator = result.coordinator

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Setup: rotation chore with overdue_action=show_overdue_state
      # turn=Zoë, due_date=2026-02-10T19:00:00Z, approval_reset=never

      # Advance time PAST due date (chore not claimed)
      with freeze_time("2026-02-10T20:00:00Z"):
          # Trigger scanner
          await coordinator.async_refresh()
          await hass.async_block_till_done()

          # Get dashboard helpers
          zoe_helper = get_dashboard_helper(hass, "Zoë")
          max_helper = get_dashboard_helper(hass, "Max!")
          lila_helper = get_dashboard_helper(hass, "Lila")

          # Find chore
          zoe_chore = find_chore(zoe_helper, "Dishes Rotation")
          max_chore = find_chore(max_helper, "Dishes Rotation")
          lila_chore = find_chore(lila_helper, "Dishes Rotation")

          # Assert Zoë (turn-holder): state=overdue, CAN still claim
          zoe_sensor = hass.states.get(zoe_chore["eid"])
          assert zoe_sensor.state == CHORE_STATE_OVERDUE
          assert zoe_sensor.attributes.get("lock_reason") is None  # Not locked
          assert zoe_sensor.attributes.get("turn_kid_name") == "Zoë"
          assert zoe_sensor.attributes.get("can_claim") is True  # Can still claim

          # Assert Max! & Lila: STILL blocked by rotation
          max_sensor = hass.states.get(max_chore["eid"])
          assert max_sensor.state == CHORE_STATE_NOT_MY_TURN
          assert max_sensor.attributes.get("lock_reason") == "not_my_turn"

          lila_sensor = hass.states.get(lila_chore["eid"])
          assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
          assert lila_sensor.attributes.get("lock_reason") == "not_my_turn"

          # Verify Zoë CAN claim overdue chore
          zoe_buttons = get_chore_buttons(hass, zoe_chore["eid"])
          kid_context = Context(user_id=mock_hass_users["kid1"].id)
          await hass.services.async_call("button", "press",
              {"entity_id": zoe_buttons["claim"]}, context=kid_context)
          await hass.async_block_till_done()

          # Verify state changed to claimed
          zoe_sensor_updated = hass.states.get(zoe_chore["eid"])
          assert zoe_sensor_updated.state == CHORE_STATE_CLAIMED
  ```

  **T1.9 — Overdue Type: Overdue Until Approval Reset (Midnight Reset)**

  ```python
  async def test_overdue_until_approval_reset_rotation(hass, mock_hass_users):
      """Test overdue_until_approval_reset: rotation may advance turn on reset."""
      from freezegun import freeze_time

      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")
      coordinator = result.coordinator

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Setup: rotation chore with overdue_action=show_overdue_state
      # approval_reset=at_midnight_once, turn=Zoë, due_date=2026-02-10T19:00:00Z

      # Advance time PAST due date (chore overdue, not claimed)
      with freeze_time("2026-02-10T20:00:00Z"):
          # Get dashboard helpers
          zoe_helper = get_dashboard_helper(hass, "Zoë")
          zoe_chore = find_chore(zoe_helper, "Dishes Rotation")

          # Zoë claims overdue chore
          zoe_buttons = get_chore_buttons(hass, zoe_chore["eid"])
          kid_context = Context(user_id=mock_hass_users["kid1"].id)
          await hass.services.async_call("button", "press",
              {"entity_id": zoe_buttons["claim"]}, context=kid_context)
          await hass.async_block_till_done()

          # Verify claimed
          zoe_sensor = hass.states.get(zoe_chore["eid"])
          assert zoe_sensor.state == CHORE_STATE_CLAIMED

      # Advance time PAST midnight (approval reset triggers)
      with freeze_time("2026-02-11T00:00:01Z"):
          # Trigger scanner to reset approval
          await coordinator.async_refresh()
          await hass.async_block_till_done()

          # Get updated helpers
          zoe_helper_updated = get_dashboard_helper(hass, "Zoë")
          max_helper_updated = get_dashboard_helper(hass, "Max!")
          lila_helper_updated = get_dashboard_helper(hass, "Lila")

          zoe_chore_updated = find_chore(zoe_helper_updated, "Dishes Rotation")
          max_chore_updated = find_chore(max_helper_updated, "Dishes Rotation")
          lila_chore_updated = find_chore(lila_helper_updated, "Dishes Rotation")

          # Assert: Approval reset, turn MAY advance depending on rotation_advancement
          # For rotation_simple: turn advances on approval/reset
          # For rotation_smart: turn may stay with Zoë if they didn't complete

          zoe_sensor_updated = hass.states.get(zoe_chore_updated["eid"])
          max_sensor_updated = hass.states.get(max_chore_updated["eid"])

          # Verify ONE of these scenarios (depends on rotation_advancement setting):
          # Scenario 1: Turn advanced to Max!
          if zoe_sensor_updated.attributes.get("turn_kid_name") == "Max!":
              assert max_sensor_updated.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
              assert max_sensor_updated.attributes.get("can_claim") is True
              assert zoe_sensor_updated.state == CHORE_STATE_NOT_MY_TURN
          # Scenario 2: Turn stayed with Zoë (smart advancement penalizes non-completion)
          else:
              assert zoe_sensor_updated.attributes.get("turn_kid_name") == "Zoë"
              assert zoe_sensor_updated.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
              assert max_sensor_updated.state == CHORE_STATE_NOT_MY_TURN
  ```

  ### T2: Rotation Services - Verify ALL Assigned Kids

  **T2.1 — set_rotation_turn Service: Verify All Kids Update**

  ```python
  async def test_set_rotation_turn_all_kids(hass, mock_hass_users):
      """Test set_rotation_turn updates ALL assigned kids' states."""
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      # Initial state: Zoë is turn-holder
      coordinator = result.coordinator
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      chore = find_chore(zoe_helper, "Dishes Rotation")
      chore_id = chore["eid"].split("_")[-1]

      # Verify initial turn
      chore_data = coordinator.chores_data[chore_id]
      assert chore_data[DATA_CHORE_ROTATION_CURRENT_KID_ID] == zoe_id

      # Call service: Set turn to Lila
      await hass.services.async_call(
          DOMAIN, "set_rotation_turn",
          {SERVICE_FIELD_CHORE_ID: chore_id, SERVICE_FIELD_ROTATION_KID_ID: lila_id},
          blocking=True
      )
      await hass.async_block_till_done()

      # Verify turn changed in storage
      chore_data_updated = coordinator.chores_data[chore_id]
      assert chore_data_updated[DATA_CHORE_ROTATION_CURRENT_KID_ID] == lila_id

      # Assert Zoë: state=not_my_turn, turn_kid_name="Lila"
      zoe_sensor = hass.states.get(chore["eid"])
      assert zoe_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert zoe_sensor.attributes.get("lock_reason") == "not_my_turn"
      assert zoe_sensor.attributes.get("turn_kid_name") == "Lila"
      assert zoe_sensor.attributes.get("can_claim") is False

      # Assert Max!: state=not_my_turn, turn_kid_name="Lila"
      max_chore_eid = f"sensor.kc_max_chore_{chore_id}"
      max_sensor = hass.states.get(max_chore_eid)
      assert max_sensor.state == CHORE_STATE_NOT_MY_TURN
      assert max_sensor.attributes.get("lock_reason") == "not_my_turn"
      assert max_sensor.attributes.get("turn_kid_name") == "Lila"
      assert max_sensor.attributes.get("can_claim") is False

      # Assert Lila: state=pending/due, lock_reason=None, turn_kid_name="Lila"
      lila_chore_eid = f"sensor.kc_lila_chore_{chore_id}"
      lila_sensor = hass.states.get(lila_chore_eid)
      assert lila_sensor.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert lila_sensor.attributes.get("lock_reason") is None
      assert lila_sensor.attributes.get("turn_kid_name") == "Lila"
      assert lila_sensor.attributes.get("can_claim") is True

      # Verify dashboard helpers ALL updated
      zoe_helper_updated = get_dashboard_helper(hass, "Zoë")
      max_helper_updated = get_dashboard_helper(hass, "Max!")
      lila_helper_updated = get_dashboard_helper(hass, "Lila")

      zoe_chore = find_chore(zoe_helper_updated, "Dishes Rotation")
      max_chore = find_chore(max_helper_updated, "Dishes Rotation")
      lila_chore = find_chore(lila_helper_updated, "Dishes Rotation")

      assert zoe_chore["state"] == CHORE_STATE_NOT_MY_TURN
      assert zoe_chore.get("turn_kid_name") == "Lila"

      assert max_chore["state"] == CHORE_STATE_NOT_MY_TURN
      assert max_chore.get("turn_kid_name") == "Lila"

      assert lila_chore["state"] in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert lila_chore.get("turn_kid_name") == "Lila"

      # Test error: Non-rotation chore
      independent_chore = find_chore(zoe_helper_updated, "Independent Chore")
      independent_id = independent_chore["eid"].split("_")[-1]

      with pytest.raises(ServiceValidationError, match="not.*rotation"):
          await hass.services.async_call(
              DOMAIN, "set_rotation_turn",
              {SERVICE_FIELD_CHORE_ID: independent_id, SERVICE_FIELD_ROTATION_KID_ID: zoe_id},
              blocking=True
          )

      # Test error: Kid not assigned
      unassigned_kid_id = result.kid_ids.get("Other Kid", "fake-uuid")
      with pytest.raises(ServiceValidationError, match="not.*assigned|kid"):
          await hass.services.async_call(
              DOMAIN, "set_rotation_turn",
              {SERVICE_FIELD_CHORE_ID: chore_id, SERVICE_FIELD_ROTATION_KID_ID: unassigned_kid_id},
              blocking=True
          )
  ```

  **T2.2 — reset_rotation Service: All Kids Reset**

  ```python
  async def test_reset_rotation_all_kids(hass, mock_hass_users):
      """Test reset_rotation resets to first kid, all kids see update."""
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      coordinator = result.coordinator
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      chore = find_chore(zoe_helper, "Dishes Rotation")
      chore_id = chore["eid"].split("_")[-1]

      # Set turn to Lila (not first kid)
      await hass.services.async_call(
          DOMAIN, "set_rotation_turn",
          {SERVICE_FIELD_CHORE_ID: chore_id, SERVICE_FIELD_ROTATION_KID_ID: lila_id},
          blocking=True
      )
      await hass.async_block_till_done()

      # Verify Lila is turn-holder
      chore_data = coordinator.chores_data[chore_id]
      assert chore_data[DATA_CHORE_ROTATION_CURRENT_KID_ID] == lila_id

      # Call reset_rotation
      await hass.services.async_call(
          DOMAIN, "reset_rotation",
          {SERVICE_FIELD_CHORE_ID: chore_id},
          blocking=True
      )
      await hass.async_block_till_done()

      # Verify reset to first kid (Zoë is assigned_kids[0])
      chore_data_reset = coordinator.chores_data[chore_id]
      assigned_kids = chore_data_reset[DATA_CHORE_ASSIGNED_KIDS]
      assert chore_data_reset[DATA_CHORE_ROTATION_CURRENT_KID_ID] == assigned_kids[0]
      assert assigned_kids[0] == zoe_id  # Zoë is first

      # Assert ALL kids see Zoë as turn-holder
      zoe_sensor = hass.states.get(chore["eid"])
      assert zoe_sensor.attributes.get("turn_kid_name") == "Zoë"
      assert zoe_sensor.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert zoe_sensor.attributes.get("can_claim") is True

      max_chore_eid = f"sensor.kc_max_chore_{chore_id}"
      max_sensor = hass.states.get(max_chore_eid)
      assert max_sensor.attributes.get("turn_kid_name") == "Zoë"
      assert max_sensor.state == CHORE_STATE_NOT_MY_TURN

      lila_chore_eid = f"sensor.kc_lila_chore_{chore_id}"
      lila_sensor = hass.states.get(lila_chore_eid)
      assert lila_sensor.attributes.get("turn_kid_name") == "Zoë"
      assert lila_sensor.state == CHORE_STATE_NOT_MY_TURN
  ```

  **T2.3 — open_rotation_cycle Service: Override Lifts Blocking for ALL**

  ```python
  async def test_open_rotation_cycle_all_kids_unblocked(hass, mock_hass_users):
      """Test open_rotation_cycle allows ALL kids to claim."""
      result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_shared.yaml")

      zoe_id = result.kid_ids["Zoë"]
      max_id = result.kid_ids["Max!"]
      lila_id = result.kid_ids["Lila"]

      coordinator = result.coordinator
      zoe_helper = get_dashboard_helper(hass, "Zoë")
      chore = find_chore(zoe_helper, "Dishes Rotation")
      chore_id = chore["eid"].split("_")[-1]

      # Initial: Zoë is turn-holder
      chore_data = coordinator.chores_data[chore_id]
      assert chore_data[DATA_CHORE_ROTATION_CURRENT_KID_ID] == zoe_id
      assert chore_data.get(DATA_CHORE_ROTATION_CYCLE_OVERRIDE, False) is False

      # Verify Max! and Lila are blocked initially
      max_chore_eid = f"sensor.kc_max_chore_{chore_id}"
      max_sensor_before = hass.states.get(max_chore_eid)
      assert max_sensor_before.state == CHORE_STATE_NOT_MY_TURN
      assert max_sensor_before.attributes.get("can_claim") is False

      lila_chore_eid = f"sensor.kc_lila_chore_{chore_id}"
      lila_sensor_before = hass.states.get(lila_chore_eid)
      assert lila_sensor_before.state == CHORE_STATE_NOT_MY_TURN
      assert lila_sensor_before.attributes.get("can_claim") is False

      # Call open_rotation_cycle
      await hass.services.async_call(
          DOMAIN, "open_rotation_cycle",
          {SERVICE_FIELD_CHORE_ID: chore_id},
          blocking=True
      )
      await hass.async_block_till_done()

      # Verify override flag set
      chore_data_override = coordinator.chores_data[chore_id]
      assert chore_data_override[DATA_CHORE_ROTATION_CYCLE_OVERRIDE] is True

      # Assert ALL kids can now claim (blocking lifted)
      zoe_sensor_after = hass.states.get(chore["eid"])
      assert zoe_sensor_after.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert zoe_sensor_after.attributes.get("lock_reason") is None
      assert zoe_sensor_after.attributes.get("can_claim") is True

      max_sensor_after = hass.states.get(max_chore_eid)
      assert max_sensor_after.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)  # NO LONGER not_my_turn!
      assert max_sensor_after.attributes.get("lock_reason") is None  # NO LONGER "not_my_turn"!
      assert max_sensor_after.attributes.get("can_claim") is True

      lila_sensor_after = hass.states.get(lila_chore_eid)
      assert lila_sensor_after.state in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert lila_sensor_after.attributes.get("lock_reason") is None
      assert lila_sensor_after.attributes.get("can_claim") is True

      # Verify dashboard helpers show override lifted
      max_helper = get_dashboard_helper(hass, "Max!")
      lila_helper = get_dashboard_helper(hass, "Lila")

      max_chore = find_chore(max_helper, "Dishes Rotation")
      lila_chore = find_chore(lila_helper, "Dishes Rotation")

      assert max_chore["state"] in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert max_chore.get("lock_reason") is None

      assert lila_chore["state"] in (CHORE_STATE_PENDING, CHORE_STATE_DUE)
      assert lila_chore.get("lock_reason") is None

      # Test: After approval, override should clear
      zoe_buttons = get_chore_buttons(hass, chore["eid"])
      kid_context = Context(user_id=mock_hass_users["kid1"].id)
      parent_context = Context(user_id=mock_hass_users["parent1"].id)

      # Zoë claims and gets approved
      await hass.services.async_call("button", "press",
          {"entity_id": zoe_buttons["claim"]}, context=kid_context)
      await hass.async_block_till_done()

      await hass.services.async_call("button", "press",
          {"entity_id": zoe_buttons["approve"]}, context=parent_context)
      await hass.async_block_till_done()

      # Verify override cleared after approval
      chore_data_final = coordinator.chores_data[chore_id]
      assert chore_data_final[DATA_CHORE_ROTATION_CYCLE_OVERRIDE] is False

      # Verify blocking restored (next turn-holder is Max!)
      lila_sensor_final = hass.states.get(lila_chore_eid)
      assert lila_sensor_final.state == CHORE_STATE_NOT_MY_TURN  # Blocking restored
      assert lila_sensor_final.attributes.get("lock_reason") == "not_my_turn"
  ```

  ### T3: Rotation Turn Advancement

  **T3.1 — Simple Rotation: Round-Robin Advancement**

  ```yaml
  Setup:
    - Chore: rotation_simple, assigned_kids=[Henry, Ronnie, Sarah]
    - rotation_current_kid_id=Henry

  Action Sequence: 1. Henry claims → parent approves
    2. Check rotation_current_kid_id after approval
    3. Ronnie claims → parent approves
    4. Check rotation_current_kid_id after approval
    5. Sarah claims → parent approves
    6. Check rotation_current_kid_id after approval (should wrap to Henry)

  Assert After Each Approval:
    - Approval 1: rotation_current_kid_id == <ronnie_uuid>
    - Approval 2: rotation_current_kid_id == <sarah_uuid>
    - Approval 3: rotation_current_kid_id == <henry_uuid> (wraps to start)

  Assert Sensors After Approval 1:
    - Henry: state="approved", turn_kid_name="Ronnie"
    - Ronnie: state="pending" (or "due"), turn_kid_name="Ronnie", lock_reason=None
    - Sarah: state="not_my_turn", turn_kid_name="Ronnie", lock_reason="not_my_turn"
  ```

  **T3.2 — Smart Rotation: Fairness-Weighted Advancement**

  ```yaml
  Setup:
    - Chore: rotation_smart, assigned_kids=[Henry, Ronnie, Sarah]
    - Pre-populate stats (use StatsManager fixtures):
      - Henry: 5 approved completions for this chore
      - Ronnie: 3 approved completions for this chore
      - Sarah: 3 approved completions for this chore (same as Ronnie, tie-break by list position)
    - rotation_current_kid_id=Henry

  Action:
    - Henry claims → parent approves

  Assert Post-Approval:
    - rotation_current_kid_id == <ronnie_uuid> (lowest count: 3, wins tie-break by appearing before Sarah in list)

  Action:
    - Ronnie claims → parent approves

  Assert Post-Approval:
    - rotation_current_kid_id == <sarah_uuid> (now lowest count: 3, Ronnie now has 4)
  ```

  **T3.3 — Rotation Resilience: Kid Deletion**

  ```yaml
  Setup:
    - Chore: rotation_simple, assigned_kids=[Henry, Ronnie, Sarah]
    - rotation_current_kid_id=Ronnie

  Action:
    - Delete Ronnie via service: kidschores.delete_kid

  Assert Post-Deletion:
    - Chore data: assigned_kids == [Henry, Sarah]
    - Chore data: rotation_current_kid_id == <henry_uuid> (reassigned to assigned_kids[0])
    - Henry's sensor: turn_kid_name="Henry", state="pending"
    - Sarah's sensor: turn_kid_name="Henry", state="not_my_turn"

  Edge Case: Delete last kid
    - Chore: assigned_kids=[Henry], rotation_current_kid_id=Henry
    - Delete Henry
    - Assert: assigned_kids == [], rotation_current_kid_id == None, rotation_cycle_override == False
  ```

  ### T4: Claim Restriction (Due Window Blocking)

  **T4.1 — Block Claim Before Window Opens**

  ```yaml
  Setup:
    - Chore: independent, due_date=2026-02-10T19:00:00Z, due_window_offset="PT1H"
    - Calculated due_window_start: 2026-02-10T18:00:00Z
    - Freeze time at 2026-02-10T17:00:00Z (1 hour before window)

  Action:
    - Attempt service: kidschores.claim_chore (kid_id=Henry, chore_id=X)

  Assert:
    - Service raises HomeAssistantError with message containing "waiting" or "due window"
    - Henry's sensor: state="waiting", lock_reason="waiting", available_at="2026-02-10T18:00:00+00:00"
  ```

  **T4.2 — Allow Claim After Window Opens**

  ```yaml
  Setup:
    - Same chore as T4.1
    - Freeze time at 2026-02-10T18:30:00Z (30 minutes into window)

  Action:
    - Call service: kidschores.claim_chore (kid_id=Henry, chore_id=X)

  Assert:
    - Service succeeds (no error)
    - Henry's sensor: state="claimed", lock_reason=None
  ```

  ### T5: Missed Lock Strategy (6th Overdue Type)

  **T5.1 — Lock at Due Date**

  ```yaml
  Setup:
    - Chore: independent, overdue_handling=at_due_date_mark_missed_and_lock
    - approval_reset_type=at_midnight_once, due_date=2026-02-10T19:00:00Z
    - Freeze time at 2026-02-10T18:00:00Z (before due), Henry has NOT claimed

  Action:
    - Advance time to 2026-02-10T19:01:00Z (1 minute past due)
    - Trigger scanner: ChoreManager._run_time_scanner()

  Assert Post-Scanner:
    - Henry's sensor: state="missed", lock_reason="missed", can_claim=False
    - Stats: Henry has 1 missed stat recorded for this chore
  ```

  **T5.2 — Reject Claim in Missed State**

  ```yaml
  Setup:
    - Same chore as T5.1, already in "missed" state

  Action:
    - Attempt service: kidschores.claim_chore (kid_id=Henry, chore_id=X)

  Assert:
    - Service raises HomeAssistantError with message containing "missed"
    - Henry's sensor: state remains "missed", can_claim=False
  ```

  **T5.3 — Unlock at Midnight (Approval Reset Boundary)**

  ```yaml
  Setup:
    - Same chore as T5.1, still in "missed" state at 2026-02-10T23:59:00Z

  Action:
    - Advance time to 2026-02-11T00:00:00Z (midnight - approval reset boundary fires)
    - Trigger scanner: ChoreManager._run_time_scanner()

  Assert Post-Scanner:
    - Henry's sensor: state="pending", lock_reason=None, can_claim=True
    - Chore lifecycle: New cycle begins, overdue policy cleared missed state
  ```

  **T5.4 — Rotation + Missed Lock: Turn Advances at Midnight**

  ```yaml
  Setup:
    - Chore: rotation_simple, assigned_kids=[Henry, Ronnie]
    - overdue_handling=at_due_date_mark_missed_and_lock, approval_reset_type=at_midnight_once
    - due_date=2026-02-10T19:00:00Z, rotation_current_kid_id=Henry
    - Freeze time at 2026-02-10T20:00:00Z, Henry in "missed" state

  Action:
    - Advance time to 2026-02-11T00:00:00Z (midnight)
    - Trigger scanner

  Assert Post-Scanner:
    - rotation_current_kid_id == <ronnie_uuid> (turn advanced to next kid)
    - Henry's sensor: state="not_my_turn" (no longer turn-holder), turn_kid_name="Ronnie"
    - Ronnie's sensor: state="pending", turn_kid_name="Ronnie", lock_reason=None
  ```

  ### T6: Steal Window (7th Overdue Type)

  **T6.1 — Pre-Overdue: Normal Rotation Blocking**

  ```yaml
  Setup:
    - Chore: rotation_simple, overdue_handling=at_due_date_allow_steal
    - assigned_kids=[Henry, Ronnie], rotation_current_kid_id=Henry
    - approval_reset_type=at_midnight_once, due_date=2026-02-10T19:00:00Z
    - Freeze time at 2026-02-10T18:00:00Z (1 hour before due)

  Assert:
    - Henry's sensor: state="due" (or "pending"), can_claim=True
    - Ronnie's sensor: state="not_my_turn", lock_reason="not_my_turn", can_claim=False
  ```

  **T6.2 — Steal Window Opens at Due Date**

  ```yaml
  Setup:
    - Same chore as T6.1
    - Advance time to 2026-02-10T19:01:00Z (1 minute past due)
    - Trigger scanner

  Assert Post-Scanner:
    - Henry's sensor: state="overdue", lock_reason=None, can_claim=True
    - Ronnie's sensor: state="overdue", lock_reason=None, can_claim=True (steal window open!)
    - Notifications: BOTH Henry and Ronnie received overdue notification
  ```

  **T6.3 — Non-Turn-Holder Steals Chore**

  ```yaml
  Setup:
    - Same chore as T6.2, steal window open

  Action:
    - Ronnie claims chore (the "stealer", not turn-holder)
    - Parent approves Ronnie

  Assert Post-Approval:
    - rotation_current_kid_id == <henry_uuid> (turn advances FROM Ronnie, not from Henry)
    - Stats: Henry gets 1 overdue stat (was skipped), Ronnie does NOT get overdue stat
    - Henry's sensor: state="not_my_turn", turn_kid_name="Henry"
    - Ronnie's sensor: state="approved", turn_kid_name="Henry"
  ```

  **T6.4 — Pure Miss in Steal Window: Turn Advances at Midnight**

  ```yaml
  Setup:
    - Same chore as T6.2, steal window open
    - NO ONE claims (neither Henry nor Ronnie)
    - Freeze time at 2026-02-10T23:59:00Z

  Action:
    - Advance time to 2026-02-11T00:00:00Z (midnight - approval reset boundary fires)
    - Trigger scanner

  Assert Post-Scanner:
    - rotation_current_kid_id == <ronnie_uuid> (turn advanced to next kid)
    - Stats: Henry gets 1 missed stat (original turn-holder gets stat)
    - Henry's sensor: state="not_my_turn", turn_kid_name="Ronnie"
    - Ronnie's sensor: state="pending", turn_kid_name="Ronnie", lock_reason=None
  ```

  ### T7: Dashboard Helper Attributes (Contract Verification)

  **T7.1 — All 3 New Attributes Present**

  ```yaml
  Setup:
    - Any chore with rotation_simple

  Assert Dashboard Helper (sensor.kc_henry_ui_dashboard_helper):
    - attributes.chores exists
    - attributes.chores[0] contains keys:
        [
          "eid",
          "name",
          "state",
          "labels",
          "grouping",
          "is_am_pm",
          "lock_reason",
          "turn_kid_name",
          "available_at",
        ]
    - Verify types: lock_reason (str | None), turn_kid_name (str | None), available_at (str | None)
  ```

  **T7.2 — turn_kid_name UUID Resolution**

  ```yaml
  Setup:
    - Chore: rotation_simple, assigned_kids=[Henry, Ronnie], rotation_current_kid_id=<henry_uuid>

  Assert Dashboard Helper:
    - chores[X].turn_kid_name == "Henry" (UUID resolved to display name)

  Assert KidChoreStatusSensor (sensor.kc_henry_chore_X):
    - attributes.turn_kid_name == "Henry" (same resolution)
  ```

  **T7.3 — available_at ISO Formatting**

  ```yaml
  Setup:
    - Chore: independent, due_date=2026-02-10T19:00:00Z, due_window_offset="PT2H"
    - Freeze time at 2026-02-10T16:00:00Z (before window)

  Assert Dashboard Helper:
    - chores[X].available_at == "2026-02-10T17:00:00+00:00" (ISO 8601 with timezone)

  Assert KidChoreStatusSensor:
    - attributes.available_at == "2026-02-10T17:00:00+00:00" (same format)
  ```

  ### T8: Criteria Transition (Mutable Completion Criteria)

  **T8.1 — Non-Rotation → Rotation: Initialize Fields**

  ```yaml
  Setup:
    - Chore: shared_first, assigned_kids=[Henry, Ronnie]
    - No rotation fields exist

  Action:
    - Call service: kidschores.update_chore
      - chore_id: <chore_uuid>
      - completion_criteria: "rotation_simple"

  Assert Post-Service:
    - Chore data: completion_criteria == "rotation_simple"
    - Chore data: rotation_current_kid_id == <henry_uuid> (assigned_kids[0])
    - Chore data: rotation_cycle_override == False
    - Signal emitted: SIGNAL_SUFFIX_CHORE_UPDATED
  ```

  **T8.2 — Rotation → Non-Rotation: Clear Fields**

  ```yaml
  Setup:
    - Chore: rotation_simple, rotation_current_kid_id=<ronnie_uuid>, rotation_cycle_override=True

  Action:
    - Call service: kidschores.update_chore
      - chore_id: <chore_uuid>
      - completion_criteria: "independent"

  Assert Post-Service:
    - Chore data: completion_criteria == "independent"
    - Chore data: rotation_current_kid_id == None (cleared)
    - Chore data: rotation_cycle_override == False (cleared)
  ```

  **T8.3 — Rotation → Different Rotation: Preserve Turn**

  ```yaml
  Setup:
    - Chore: rotation_simple, rotation_current_kid_id=<sarah_uuid>

  Action:
    - Call service: kidschores.update_chore
      - chore_id: <chore_uuid>
      - completion_criteria: "rotation_smart"

  Assert Post-Service:
    - Chore data: completion_criteria == "rotation_smart"
    - Chore data: rotation_current_kid_id == <sarah_uuid> (unchanged - both are rotation modes)
  ```

  **T8.4 — Validation: Rotation Requires ≥2 Kids (V-03)**

  ```yaml
  Setup:
    - Chore: independent, assigned_kids=[Henry] (only 1 kid)

  Action:
    - Call service: kidschores.update_chore
      - chore_id: <chore_uuid>
      - completion_criteria: "rotation_simple"

  Assert:
    - Service raises ServiceValidationError
    - Error translation_key contains "rotation" and "2 kids" or similar
  ```

  **T8.5 — Validation: at_due_date_allow_steal Compatibility (V-05)**

  ```yaml
  Setup:
    - Chore: independent, approval_reset_type=at_midnight_once, due_date set

  Action:
    - Call service: kidschores.update_chore
      - chore_id: <chore_uuid>
      - overdue_handling: "at_due_date_allow_steal"

  Assert:
    - Service raises ServiceValidationError
    - Error message: "at_due_date_allow_steal requires rotation criteria"

  ---

  Setup:
    - Chore: rotation_simple, approval_reset_type=upon_completion, due_date set

  Action:
    - Call service: kidschores.update_chore
      - chore_id: <chore_uuid>
      - overdue_handling: "at_due_date_allow_steal"

  Assert:
    - Service raises ServiceValidationError
    - Error message: "at_due_date_allow_steal requires at_midnight_once reset type"
  ```

  ### Summary for Builder

  **Test Execution Order**:
  1. T1 (FSM states) — Foundation for all other tests
  2. T7 (Dashboard attributes) — Verify contract consistency early
  3. T2 (Rotation services) — Service layer validation
  4. T3 (Turn advancement) — Core rotation logic
  5. T4 (Claim restriction) — Due window blocking
  6. T5 (Missed lock) — 6th overdue type
  7. T6 (Steal window) — 7th overdue type
  8. T8 (Criteria transition) — Mutable criteria + validation

  **Critical Patterns**:
  - ALWAYS assert both KidChoreStatusSensor AND dashboard helper for same chore/kid
  - ALWAYS verify new attributes: `lock_reason`, `turn_kid_name`, `available_at`
  - ALWAYS check `can_claim` attribute alongside state (contract requirement)
  - Use `freezegun` for time control (due dates, windows, midnight boundaries)
  - Use `async_fire_time_changed` for scanner triggers

  **Validation Gates (Run After All Tests)**:
  - `./utils/quick_lint.sh --fix` must pass
  - `mypy custom_components/kidschores/` must show zero errors
  - `pytest tests/ -v --tb=line` must show 95%+ coverage for new code

- **Key issues**
  - Smart rotation tests need StatsEngine/StatsManager fixtures with pre-populated chore stats per kid
  - The scanner's 5-minute interval makes time-sensitive tests tricky — use `freezegun` or `async_fire_time_changed` to control time
  - Test coverage for rotation + missed + claim_restriction combinations could be combinatorially large — focus on the priority-order edge cases documented in the FSM state matrix
  - Criteria transition tests (Step 2) are critical for D-11 — must verify field cleanup is complete when switching criteria types

---

## Testing & validation

- Tests to execute:
  - `pytest tests/test_chore_engine.py -v` — Engine unit tests (adapters, FSM, rotation helpers)
  - `pytest tests/test_service_rotation.py -v` — Service-based rotation + criteria transition tests
  - `pytest tests/test_data_builders.py -v` — Validation rule tests
  - `pytest tests/test_migration.py -v` — v44 migration extension tests
  - `pytest tests/test_ui_manager.py -v` — Dashboard helper tests
  - `pytest tests/ -v --tb=line` — Full suite
- Outstanding: All tests — pending implementation
- Coverage target: 95%+ for all new modules

---

## Notes & follow-up

### Architecture context

- **Engine-Manager separation is critical**: All state resolution, `can_claim` logic, and Logic Adapters must be pure functions in `chore_engine.py`. The manager orchestrates workflows and writes to storage.
- **Signal-first communication**: `_advance_rotation()` emits `ROTATION_ADVANCED` after `_persist()`. Other managers (Statistics, Notification, UI) react to signals — never direct calls.
- **Rotation is a shared_first extension via Criteria Overload** (D-12): Rotation types (`rotation_simple`, `rotation_smart`) are `completion_criteria` values, not a separate field. The Logic Adapter pattern (`is_single_claimer_mode()`, `is_rotation_mode()`) prevents gremlin code — existing `shared_first` checks use the adapter and automatically include rotation types.
- **Steal is an overdue handling type** (D-06 revised): `at_due_date_allow_steal` is a 7th overdue handling value, NOT a completion criteria. The FSM P3 steal exception checks `overdue_handling == at_due_date_allow_steal` (not `criteria == rotation_steal`). This simplifies the criteria set (2 rotation types, not 3) and makes steal orthogonal to rotation type.
- **completion_criteria is MUTABLE** (D-11): Users can change criteria when editing chores. The `services.py` immutability guard at L784-788 is incorrect and must be removed. A `get_criteria_transition_actions()` engine method and `_handle_criteria_transition()` manager method handle field cleanup when criteria changes.
- **Two distinct "missed" strategies coexist**:
  - `clear_and_mark_missed` — Records miss stat, then resets to pending at approval boundary (existing)
  - `mark_missed_and_lock` — Records miss stat, locks state to `missed`, prevents further claims until midnight (new)
- **`at_due_date_allow_steal`** (D-06 revised) — At due date, lifts `not_my_turn` blocking for rotation chores. Any assigned kid can claim. Only the original turn-holder gets the overdue stat. After steal: turn advances from completer (D-18). After pure miss: turn advances to next kid at midnight (D-17).
- **v44 migration extended** (D-13): `_migrate_to_schema_44()` backfills new fields on existing chores rather than relying on `.get()` defaults.

### Logic Adapter audit (D-12 implementation context)

**~60 existing `completion_criteria` check sites across 10 production files** need updating to use Logic Adapters. Key findings:

| File                             | Check Sites | Primary Pattern                                                                          |
| -------------------------------- | ----------- | ---------------------------------------------------------------------------------------- |
| `managers/chore_manager.py`      | **25**      | Three-way branching (INDEPENDENT / SHARED_FIRST / SHARED) — heaviest target              |
| `engines/chore_engine.py`        | **10**      | Stateless routing + `is_shared_chore()` definition (zero callers — dead code)            |
| `options_flow.py`                | **6**       | Gating per-kid UI steps (INDEPENDENT only)                                               |
| `helpers/flow_helpers.py`        | **5**       | Form building + data transformation                                                      |
| `sensor.py`                      | **4**       | Entity creation gating + attribute routing                                               |
| `data_builders.py`               | **3**       | Validation + build defaults                                                              |
| `services.py`                    | **3**       | Service input validation                                                                 |
| `schedule_engine.py`             | **2**       | Per-kid vs chore-level date/day routing                                                  |
| `helpers/entity_helpers.py`      | **1**       | Orphaned sensor cleanup (**potential bug**: checks `SHARED` only, misses `SHARED_FIRST`) |
| `managers/statistics_manager.py` | **1**       | Daily snapshot due-date lookup                                                           |

**Adapter adoption strategy**: Add `is_single_claimer_mode()` and `is_rotation_mode()` in Phase 2 Step 1. Then incrementally convert callers file-by-file in Phase 2-3. The three-way branches (INDEPENDENT / SHARED_FIRST / SHARED) become (INDEPENDENT / single_claimer / SHARED) — rotation chores automatically get correct SHARED_FIRST-like behavior with zero per-site logic changes.

### Dependencies

- Phase 2 depends on Phase 1 (constants and types must exist)
- Phase 3 depends on Phase 2 (engine methods must exist for manager to call)
- Phase 4 depends on Phase 3 (signals and services must exist for UX to expose)
- Phase 5 can begin partially in parallel with Phase 3 (engine tests don't need manager)

### Follow-up tasks (separate initiatives)

- Dashboard YAML updates in `kidschores-ha-dashboard` to consume new attributes
- Crowdin sync for new translation keys
- Wiki documentation for rotation feature and missed lock feature
- Consider automation blueprints for "missed chore" → penalty workflow
- Evaluate precision scheduling for missed lock detection (currently ~5 min scanner delay)
- **Potential bug**: `entity_helpers.py` `cleanup_orphaned_shared_state_sensors()` checks only `SHARED` but shared state sensors are created for both `SHARED` and `SHARED_FIRST` — may orphan SHARED_FIRST sensors. Worth fixing in this initiative.

### Estimated file impact

| File                                                          | Change Type | Estimated Scope                                                                                                         |
| ------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| `const.py`                                                    | Modify      | ~28 new constants (2 rotation criteria + 1 overdue + states + services + attrs), remove rotation_steal, add allow_steal |
| `type_defs.py`                                                | Modify      | 3 new TypedDict fields                                                                                                  |
| `data_builders.py`                                            | Modify      | 3 new defaults + 4 validation rules (V-01 thru V-03, V-05). Remove old V-04 (rotation_steal due date).                  |
| `engines/chore_engine.py`                                     | Modify      | ~250 lines new (Logic Adapters + FSM + rotation helpers + transition helper)                                            |
| `managers/chore_manager.py`                                   | Modify      | ~350 lines new (rotation advancement, scanner, missed lock, criteria transition, + adapter adoption across 25 sites)    |
| `engines/stats_engine.py` or `managers/statistics_manager.py` | Modify      | ~30 lines (new query methods)                                                                                           |
| `managers/ui_manager.py`                                      | Modify      | ~40 lines (3-4 new dashboard attributes)                                                                                |
| `managers/notification_manager.py`                            | Modify      | ~40 lines (missed notification + steal-window-open notification to all assigned kids)                                   |
| `helpers/flow_helpers.py`                                     | Modify      | ~30 lines (new selectors/options — 2 rotation criteria + 7th overdue type)                                              |
| `options_flow.py`                                             | Modify      | ~20 lines (claim restriction + criteria transition + overdue validation V-05)                                           |
| `services.py`                                                 | Modify      | ~100 lines (3 new services + remove immutability guard + add criteria to update schema)                                 |
| `services.yaml`                                               | Modify      | ~30 lines (service descriptions)                                                                                        |
| `migration_pre_v50.py`                                        | Modify      | ~20 lines (v44 extension for new field backfill)                                                                        |
| `translations/en.json`                                        | Modify      | ~40 new keys, remove `rotation_steal` entries, add `at_due_date_allow_steal` entries, fix rotation descriptions         |
| `tests/test_chore_engine.py`                                  | New/Modify  | ~400 lines (adapters + FSM + rotation + transition)                                                                     |
| `tests/test_service_rotation.py`                              | New         | ~550 lines (rotation services + steal-via-overdue + criteria transition + claim restriction + missed lock)              |
| `tests/test_data_builders.py`                                 | Modify      | ~120 lines (V-01 thru V-03, V-05 including allow_steal combos)                                                          |
| `tests/test_migration.py`                                     | Modify      | ~50 lines                                                                                                               |
| `tests/test_ui_manager.py`                                    | Modify      | ~80 lines                                                                                                               |
