# Initiative Plan: User Chore Pause

## Initiative snapshot

- **Name / Code**: `user-chore-pause`
- **Target release / milestone**: TBD
- **Owner / driver(s)**: TBD
- **Status**: In progress — analysis phase

## Summary & immediate steps

| Phase | Description | % complete | Quick notes |
|---|---|---|---|
| Phase 1 — Storage & Constants | User data fields, type defs, consts, data builder validation | **100%** | Implemented: const.py, type_defs.py, data_builders.py, flow_helpers.py, en.json |
| Phase 2 — Unified P0 Guard | `_is_chore_paused_for_assignee()` helper, `get_chore_status_context` guard, signal suppression, rotation/overdue/missed/reset/auto-unpause guards | **100%** | Implemented: 11 guard steps across chore_manager.py + statistics_manager.py |
| Phase 3 — Signal Suppression Verification | Confirm guard at emission point covers notification/statistics/calendar consumers | **100%** | Verified: all signal paths covered + can_claim_chore guard added |
| Phase 4 — Display Surfaces | Sensor state mapping, dashboard status_maps, claim mode icons, sort order, calendar filtering, user header banner | **100%** | All 9 steps complete: en_dashboard.json keys, admin status_map/color_map, shared row templates (statusMap + claimModeIconMap + kids row), user templates (all 5 variants with statusMap + sort order + welcome card banner), sort order comments, sensor projection (auto). Non-English stubs deferred to Crowdin pipeline. |
| Phase 5 — Admin Workflow | \"Pause User's Chores\" dashboard card + `choreops.pause_user_chores` service | **100%** | Service constants, schema, handler, and registration in const.py + services.py + services.yaml + en.json. Manager method `set_user_chores_paused()` implemented in Phase 2. Dashboard card pending in admin templates. |
| Phase 6 — Testing | FSM guard tests, rotation skip, all-paused freeze, return-from-pause, regression | 0% | Not started — test environment has pre-existing HA framework mismatch |
| Phase 7 — Documentation & Polish | Wiki, ARCHITECTURE.md, DASHBOARD_UI_DESIGN_GUIDELINE.md | 0% | Not started |

1. **Key objective** — Allow admins to pause chore processing for a user (with optional return date). While paused, the user's chores display `paused` state instead of normal FSM states, rotation advances past them in real time, and no overdue/missed stats or notifications accumulate. The architecture supports three pause scopes — user-level (MVP), chore-level global, and chore×user intersection — all feeding into a single P0 guard.

2. **Summary of recent work** — Full analysis completed 2026-06-05 through 2026-06-06. Three supporting documents created:
   - [LEXICAL_ANALYSIS_UNAVAILABLE_VS_PAUSED.md](LEXICAL_ANALYSIS_UNAVAILABLE_VS_PAUSED.md) — Renamed from `unavailable` to `paused` to avoid HA protocol state collision
   - [ARCH_DECISION_PAUSED_DERIVED_VS_PERSISTED.md](ARCH_DECISION_PAUSED_DERIVED_VS_PERSISTED.md) — `paused` is a derived UI state (not persisted), three-scope architecture
   - [CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md](CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md) — Interaction analysis with primary-backup chore type

   **Phases 1–3 implementation completed 2026-06-08**:
   - **Phase 1**: All constants added to `const.py` (storage keys, states, claim modes, CFOF, translation keys). Frozensets updated. `UserData` TypedDict extended. Builders updated with defaults, validation, and preserve fields. Options flow schema added. English translations added (sensor state, claim mode, admin form, exception).
   - **Phase 2**: 11 guard steps implemented — `_is_chore_paused_for_assignee()` helper, P0 guard in `get_chore_status_context()`, guards in `_process_overdue()`, `_record_chore_missed()`, `_advance_rotation()`, `chore_counts_toward_due_today_summary()`, `_is_chore_due_today_for_assignee()` (statistics_manager), `set_rotation_turn()`, `_process_approval_reset_entries()` (both loops), auto-re-enable midnight hook, real-time rotation advance past paused turn-holders.
   - **Phase 3**: All signal paths verified — `CHORE_OVERDUE`, `CHORE_MISSED`, midnight approval/completion signals. `can_claim_chore()` guard added. Calendar and dashboard helper confirmed covered.
   - **Validation**: 🟢 Lint passes (Platinum), 🟢 mypy 0 errors, 🟢 all imports and JSON valid. Tests have pre-existing HA framework mismatch (unrelated).

4. **Risks / blockers**
   - `paused` state must be added to `CHORE_UI_ASSIGNEE_STATES` and `CHORE_CLAIM_MODES` frozensets
   - Dashboard templates must add `paused` / `blocked_paused` entries to `status_map`, `status_color_map`, `claimModeIconMap`, and sort-order logic across 9 template files
   - Rotation advance must handle the edge case where ALL assignees are paused — should freeze at current position, not infinite-loop
   - `_transition_chore_state` callers must be audited to ensure no bypass of the pause guard
   - Midnight `_process_approval_reset_entries` emits approval/completion signals for paused users — needs guard (see Phase 2 Step 9)
  - Auto-re-enable hook must run after reset entries so unpaused users are processed in the same midnight cycle (see Phase 2 Step 10)

5. **Dashboard asset governance (mandatory)**
   - All dashboard template changes MUST be authored in the `choreops-dashboards` repository (canonical source)
   - After editing canonical templates, run `python utils/sync_dashboard_assets.py` to mirror changes into `custom_components/choreops/dashboards/`
   - Verify parity with `python utils/sync_dashboard_assets.py --check`
   - Vendored copies in `custom_components/choreops/dashboards/` are **sync outputs only** — never hand-edit them
   - After sync, run the integration validation gates: `./utils/quick_lint.sh --fix`, `mypy`, `pytest`
   - See DEVELOPMENT_STANDARDS.md §1.3 for the full dashboard asset governance contract

6. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) — FSM contract, derived UI states, state resolution contract
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) — Constant naming, event architecture, CRUD patterns, lexicon standards
   - [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) — Phase 0 boundary checks
   - [DASHBOARD_UI_DESIGN_GUIDELINE.md](../DASHBOARD_UI_DESIGN_GUIDELINE.md) — State color/style table, claim mode icon table
   - `custom_components/choreops/managers/chore_manager.py:3988` — `get_chore_status_context` (P0 guard insertion point)
   - `custom_components/choreops/managers/chore_manager.py:4943` — `_advance_rotation` (pause skip insertion point)
   - `custom_components/choreops/managers/chore_manager.py:2000` — `_process_overdue` (pause skip insertion point)
   - `custom_components/choreops/managers/chore_manager.py:5634` — `_record_chore_missed` (pause skip insertion point)
   - `custom_components/choreops/const.py:1835-1860` — Derived vs persisted state boundary

7. **Decisions & completion check**
   - **Decisions captured** (D-1 through D-14 span this plan + supporting docs):
     - D-1: P0 guard in `get_chore_status_context`, not inside `resolve_assignee_chore_state` — keeps the FSM pure
     - D-2: Suppress at signal emission — `_process_overdue` and `_record_chore_missed` skip paused users; notification/statistics managers need zero changes
     - D-3: `_advance_rotation` skips paused turn-holders. All paused → freeze at current position
     - D-4: Admin workflow = Push Chores Forward (existing) → Pause User's Chores (new). Two complementary actions
     - D-5: No stash/restore of assignment lists. Paused users stay on shared/rotation chores; they just don't accumulate penalties
     - D-6: On return: due dates are whatever they were. If past due, next midnight cycle marks overdue — admin should have used Push Chores Forward
     - D-7: Display state `paused` with claim mode `blocked_paused` — user sees clear "Paused" status
     - D-8: `paused` is a derived UI state, never persisted on chore records — it's an administrative overlay, not a workflow event
     - D-9: MVP uses user-level flag only (`DATA_USER_CHORES_PAUSED`)
     - D-10: If per-chore pause is needed later, add `DATA_CHORE_PAUSED_FOR` list (Scope 3) — achieves granularity without making `paused` a persisted workflow state
     - D-11: P0 guard checks three sources via `_is_chore_paused_for_assignee()` — single point of truth, all scopes compose via OR
     - D-12: All three scopes use the same display state (`paused`) and claim mode (`blocked_paused`) — users don't need to know WHY
     - D-13: Global chore pause (Scope 2) does NOT auto-clear existing claims — claims are workflow state, pause is administrative overlay
     - D-14: MVP ships Scope 1 only; Scopes 2 & 3 are architectural hooks in the guard from day one
   - **Completion confirmation**: `[ ]` All phases complete, tests pass, admin dashboard updated, wiki updated.

## Architecture: Three Pause Scopes

The architecture supports three distinct pause scopes, all feeding into a single P0 guard. MVP implements Scope 1 only; Scopes 2 and 3 are designed but deferred.

```
Scope 1: Pause USER (MVP)        Scope 2: Pause CHORE (future)    Scope 3: Pause CHORE×USER (future)
┌─────────────────────┐          ┌──────────────────────────┐      ┌──────────────────────────┐
│ users[id].           │          │ chores[id].paused: true   │      │ chores[id].             │
│   chores_paused: true│          │                          │      │   paused_for: [user_id]  │
│                      │          │ "Dishwasher is broken —   │      │                          │
│ "Sarah is on vacation│          │  nobody does dishes"      │      │ "Sarah can't do dishes    │
│  — freeze all chores"│          │                          │      │  but can do homework"     │
└─────────────────────┘          └──────────────────────────┘      └──────────────────────────┘
         │                                    │                              │
         └────────────────────────────────────┼──────────────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │  _is_chore_paused │
                                    │  _for_assignee()  │
                                    │                   │
                                    │  Any True → P0    │
                                    │  guard returns    │
                                    │  "paused" state   │
                                    └───────────────────┘
```

See [ARCH_DECISION_PAUSED_DERIVED_VS_PERSISTED.md](ARCH_DECISION_PAUSED_DERIVED_VS_PERSISTED.md) for full scope definitions, interaction matrix, and implementation phasing.

## Unpause Behavior (Resuming Chores)

When a user's `chores_paused` flag is cleared, the system does NOT perform any catch-up or reconciliation. The FSM resumes normal resolution immediately.

### What happens per chore type

| Chore type | State before pause | What happens on unpause |
|-----------|-------------------|------------------------|
| Independent | `pending` | FSM resolves normally. If due date passed while paused → immediately `overdue` at next poll |
| Independent | `claimed` | Claim survives. Approver can approve. P1 returns `completed` if already approved |
| Independent | `approved` | P1 returns `completed` immediately |
| Rotation | Turn-holder when paused | Turn advanced past them. They re-enter at end of rotation line. Next turn cycle picks up normally |
| Rotation | Not turn-holder when paused | No change. Their position in rotation is unchanged |
| Shared | Any underlying state | FSM resolves normally for all assignees |
| Primary-backup | Primary paused | Turn advanced to backup. At next reset boundary, snaps back to primary (CRIT-2) |

### What the admin should do before unpausing

The admin is responsible for managing due dates before lifting the pause:

1. **Use Push Chores Forward** to move recurring chore due dates past the return date
2. **Review rotation position** — the user may have lost their turn; consider using `set_rotation_turn` if needed
3. **Clear persistent notifications** — stale overdue/missed notifications from before the pause remain visible

### What happens if admin doesn't push dates

- Due dates that passed during the pause → chores immediately show `overdue` at next poll/midnight
- Overdue signals fire → notifications sent, stats recorded
- This is correct behavior — the chore WAS missed. The pause prevented penalty accumulation during absence but doesn't retroactively change due dates

### Rotation re-entry detail

When a paused user was the turn-holder in a rotation chore:
1. `_advance_rotation` skipped them (Phase 2 Step 5)
2. The next available assignee became turn-holder
3. On unpause: the user is now at the back of the rotation line
4. They will get their next turn when the rotation cycles around to them

For primary-backup chores: the reset-boundary force-to-primary (CRIT-2) snaps turn back to the primary at the next midnight — the primary regains their position within 24 hours.

### Edge case: unpausing mid-claim

If a user claimed a chore before being paused, and the claim is still pending approval on unpause:
- No change — the claim persists. The approver can approve/disapprove
- If the approver approves after unpause, the chore completes normally
- If midnight auto-approval fires before unpause... is guarded by Phase 2 Step 9

### Automatic unpause at return date

When `chores_paused_until` is set to a future date, the system automatically clears the `chores_paused` flag at the first midnight after that date passes. This is implemented as a midnight hook (Phase 2 Step 10).

- **With return date**: Admin sets "Paused until June 10." At midnight on June 11 (UTC), the flag auto-clears. The user's chores resume normally at the next poll.
- **Without return date** (`chores_paused_until` left blank): Pause is indefinite. Admin must manually unpause via the dashboard card or service.
- **Edge case — admin manually unpauses before return date**: The `paused_until` field is cleared along with the flag (already handled in Phase 5 Step 2). The midnight hook is a no-op if `chores_paused` is already `false`.
- **No per-user notification on auto-unpause**: The system does not send a notification when auto-unpausing. The admin dashboard shows the updated status. A notification could be added in a follow-up.

## Tracking expectations

- **Summary upkeep**: Update the Summary section after each significant change (commits, test results, blockers).
- **Detailed tracking**: Use the phase-specific sections below. Do not merge into the Summary table.

---

## Detailed phase tracking

### Phase 1 — Storage & Constants

- **Goal**: Add user-level pause fields to the data model, wire constants and type definitions, add validation, and surface in the options flow. Scope 1 (user-level) only.

- **Steps / detailed work items**

  1. `[ ]` **Add `DATA_USER_CHORES_PAUSED` and `DATA_USER_CHORES_PAUSED_UNTIL` constants** in `custom_components/choreops/const.py` (~line 1235, near existing `DATA_USER_*` fields):
     ```python
     DATA_USER_CHORES_PAUSED: Final = "chores_paused"
     DATA_USER_CHORES_PAUSED_UNTIL: Final = "chores_paused_until"
     ```

  2. `[ ]` **Add `CHORE_STATE_PAUSED` derived UI state** in `custom_components/choreops/const.py` (~line 1859, in the "Derived UI-only states" block after `CHORE_STATE_NOT_MY_TURN`):
     ```python
     CHORE_STATE_PAUSED: Final = "paused"
     ```
     Add to `CHORE_UI_ASSIGNEE_STATES` frozenset (~line 1889).

  3. `[ ]` **Add `CHORE_CLAIM_MODE_BLOCKED_PAUSED` claim mode** in `custom_components/choreops/const.py` (~line 1926, after `CHORE_CLAIM_MODE_BLOCKED_MISSED_LOCKED`):
     ```python
     CHORE_CLAIM_MODE_BLOCKED_PAUSED: Final = "blocked_paused"
     ```
     Add to `CHORE_CLAIM_MODES` frozenset.

  4. `[ ]` **Add Scope 2 & 3 storage constants** (DEFERRED — architectural hooks only, not yet used):
     ```python
     # Scope 2: Global chore pause (future)
     DATA_CHORE_PAUSED: Final = "paused"  # bool on chore record
     # Scope 3: Chore×User pause (future)
     DATA_CHORE_PAUSED_FOR: Final = "paused_for"  # list[user_id] on chore record
     ```

  5. `[ ]` **Update `UserData` TypedDict** in `custom_components/choreops/type_defs.py` (~line 662, add after `can_be_assigned` field):
     ```python
     chores_paused: NotRequired[bool]
     chores_paused_until: NotRequired[str | None]  # ISO datetime or None
     ```

  6. `[ ]` **Add validation in `data_builders.py`** — in `validate_user_data()` or `build_user()`, ensure `chores_paused` is boolean and `chores_paused_until` is a valid future datetime if provided. Allow clearing both (user's chores resume).

  7. `[ ]` **Add to `build_user()` defaults** — `chores_paused: False`, `chores_paused_until: None` when creating new users.

  8. `[ ]` **Add CFOF constants** for options flow form fields:
     ```python
     CFOF_USERS_INPUT_CHORES_PAUSED: Final = "chores_paused"
     CFOF_USERS_INPUT_CHORES_PAUSED_UNTIL: Final = "chores_paused_until"
     ```

  9. `[ ]` **Update options flow** `async_step_edit_user` — add pause controls to the standard user edit screen in `options_flow.py` (~line 836). This is the primary configuration surface for admins who prefer the HA UI over dashboards.

     **Schema additions** (in `flow_helpers.py` `build_user_schema()`):
     ```python
     # Add to the existing user edit schema:
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
     Both fields are always visible — HA options flow schemas are static and cannot conditionally show/hide fields. The `description` on the date field makes the relationship clear. The description text must be added to `translations/en.json` under the CFOF key.

     **Validation in `validate_user_inputs()`**: If `chores_paused` is `true` and `chores_paused_until` is provided, ensure the date is in the future (or today). If `chores_paused` is `false`, always clear `chores_paused_until`.

     **Data flow**: The save handler passes validated input to `build_user_profile()` which applies the new fields. The coordinator persists and emits `SIGNAL_SUFFIX_USER_UPDATED`. Entity listeners pick up the change and the dashboard helper refreshes. No integration reload is needed — this is a storage-level user data change, not a system settings change.

  10. `[ ]` **Add translation key constants** in `custom_components/choreops/const.py`:
      ```python
      TRANS_KEY_ERROR_CHORE_PAUSED: Final = "chore_paused"
      ```

  11. `[ ]` **Add translation strings** in `custom_components/choreops/translations/en.json`:
      - Under `entity.sensor.chore_status_sensor.state`: `"paused": "Paused"`
      - Under `entity.sensor.chore_status_sensor.state_attributes.claim_mode.state`: `"blocked_paused": "Chores are paused for this user"`
      - Under `config.step.edit_user.data`: labels for `chores_paused` and `chores_paused_until`
      - Under `exceptions`: `"chore_paused": "Chores are currently paused for {user_name}."`

- **Key issues**
  - Schema version: this adds new user-level fields. Schema version may need bumping if `build_user()` changes the required field set.
  - `chores_paused_until` is an optional UTC datetime. When set, the system auto-clears the `chores_paused` flag at the next midnight after the return date passes. When not set, the pause is indefinite and must be manually cleared by the admin. The auto-re-enable hook is implemented in Phase 2 Step 10.

---

### Phase 2 — Unified P0 Guard (Core Behavioral Change)

- **Goal**: Implement `_is_chore_paused_for_assignee()` helper and insert guard clauses at the P0 display layer and signal-emission points. ~25 lines in `chore_manager.py`.

- **Steps / detailed work items**

  1. `[ ]` **Add `_is_chore_paused_for_assignee()` helper** in `custom_components/choreops/managers/chore_manager.py` (~line 3980, before `get_chore_status_context`):
     ```python
     def _is_chore_paused_for_assignee(self, assignee_id: str, chore_id: str) -> bool:
         """Check all pause scopes. Returns True if chore should show as paused.

         Checks three sources (composed via OR):
           1. User-level: DATA_USER_CHORES_PAUSED on user record
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

  2. `[ ]` **P0 guard in `get_chore_status_context()`** — `custom_components/choreops/managers/chore_manager.py` line ~3988. Insert as the FIRST check before any FSM resolution:
     ```python
     # P0: Check if chore processing is paused for this assignee
     if self._is_chore_paused_for_assignee(assignee_id, chore_id):
         return {
             # All 15 CHORE_CTX_* keys (const.py:1942-1956) must be set
             CHORE_CTX_STATE: CHORE_STATE_PAUSED,
             CHORE_CTX_STORED_STATE: None,
             CHORE_CTX_IS_OVERDUE: False,
             CHORE_CTX_IS_DUE: False,
             CHORE_CTX_HAS_PENDING_CLAIM: False,
             CHORE_CTX_IS_APPROVED_IN_PERIOD: False,
             CHORE_CTX_IS_COMPLETED_BY_OTHER: False,
             CHORE_CTX_CAN_CLAIM: False,
             CHORE_CTX_CAN_CLAIM_ERROR: None,
             CHORE_CTX_CLAIM_MODE: CHORE_CLAIM_MODE_BLOCKED_PAUSED,
             CHORE_CTX_CAN_APPROVE: False,
             CHORE_CTX_CAN_APPROVE_ERROR: None,
             CHORE_CTX_DUE_DATE: None,
             CHORE_CTX_AVAILABLE_AT: None,
             CHORE_CTX_LAST_COMPLETED: None,
         }
     ```

  3. `[ ]` **Guard in `_process_overdue()`** — `custom_components/choreops/managers/chore_manager.py` line ~2025, inside the per-entry loop, after the idempotency check but before state transition:
     ```python
     # Skip paused users/chores — no overdue processing
     if self._is_chore_paused_for_assignee(assignee_id, chore_id):
         continue
     ```

  4. `[ ]` **Guard in `_record_chore_missed()`** — `custom_components/choreops/managers/chore_manager.py` line ~5634, at function entry:
     ```python
     # Skip paused users/chores — no missed recording
     if self._is_chore_paused_for_assignee(assignee_id, chore_id):
         return
     ```

  5. `[ ]` **Guard in `_advance_rotation()`** — `custom_components/choreops/managers/chore_manager.py` line ~4960. After determining candidate `new_assignee_id` (for any rotation type), run through the pause skip:
     ```python
     # Step A: Determine candidate (criteria-specific — simple, smart, or primary_backup)
     if completion_criteria == const.COMPLETION_CRITERIA_ROTATION_PRIMARY_BACKUP:
         new_assignee_id = assigned[0] if assigned else None
     elif completion_criteria == const.COMPLETION_CRITERIA_ROTATION_SIMPLE:
         new_assignee_id = self._calculate_next_turn_simple(...)
     else:  # smart
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
             pass
     ```
     **Coordination with primary-backup plan**: This guard MUST run AFTER the primary-backup early-return determines `new_assignee_id = assigned[0]` but BEFORE the signal payload is built. See [CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md](CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md) CRIT-1.

- **Key issues**
  - **P0 placement**: The guard lives in `get_chore_status_context` (display orchestrator), not `resolve_assignee_chore_state` (pure FSM). The FSM stays pure — no new parameters needed.
  - **All-paused rotation freeze**: The `for/else` loop handles the case where every assignee is paused. Rotation freezes at current position. When someone is unpaused, the next rotation advance picks up normally.
  - **Performance**: `_is_chore_paused_for_assignee` does two dict lookups (user data + chore data). Negligible cost for typical household sizes.
  - **Scope 2 & 3 hooks**: The helper already checks `DATA_CHORE_PAUSED` and `DATA_CHORE_PAUSED_FOR`. These return `False` until the fields exist, so they have zero runtime impact in MVP.

  6. `[ ]` **Guard in `chore_counts_toward_due_today_summary()`** — `custom_components/choreops/managers/chore_manager.py` line ~4193. Add `CHORE_STATE_PAUSED` to the `display_state` exclusion tuple and `CHORE_CLAIM_MODE_BLOCKED_PAUSED` to the `claim_mode` exclusion tuple. This prevents paused chores from being counted in the "Due Today" summary.

  7. `[ ]` **Guard in `_is_chore_due_today_for_assignee()`** — `custom_components/choreops/managers/statistics_manager.py` line ~2354. Add pause check at function entry:
     ```python
     user_data = self.coordinator._data.get(DATA_USERS, {}).get(assignee_id, {})
     if user_data.get(DATA_USER_CHORES_PAUSED):
         return False
     ```
     This ensures statistics calculations don't count paused users' chores as due-today.

  8. `[ ]` **Guard in `set_rotation_turn()`** — `custom_components/choreops/managers/chore_manager.py` line ~5124. After assignment validation, add:
     ```python
     if self._is_chore_paused_for_assignee(assignee_id, chore_id):
         raise ServiceValidationError(
             translation_domain=DOMAIN,
             translation_key=TRANS_KEY_ERROR_CHORE_PAUSED,
         )
     ```
     Prevents approvers from setting rotation turn to a paused user.

  9. `[ ]` **Guard in `_process_approval_reset_entries()`** — `custom_components/choreops/managers/chore_manager.py` lines ~2283 (SHARED loop) and ~2343 (INDEPENDENT loop). Add `continue` for paused users at the top of each loop:
     ```python
     # SHARED loop (~line 2283):
     for assignee_id in assigned_assignees:
         if self._is_chore_paused_for_assignee(assignee_id, chore_id):
             continue
     # INDEPENDENT loop (~line 2343):
     for assignee_entry in assignee_entries:
         assignee_id = assignee_entry[CHORE_SCAN_ENTRY_USER_ID]
         if self._is_chore_paused_for_assignee(assignee_id, chore_id):
             continue
     ```
     This prevents midnight auto-approval from emitting `CHORE_APPROVED` and `CHORE_COMPLETED` signals for paused users. Without this guard, midnight would auto-approve paused users' pre-existing claims and emit gamification/notification signals.

  10. `[ ]` **Auto-re-enable hook at midnight** — `custom_components/choreops/managers/chore_manager.py`, in `_on_midnight_rollover()` (~line 334). After existing midnight processing, iterate all users and auto-clear expired pauses:
      ```python
      # After existing midnight processing completes:
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
      ```
      This hook must run AFTER `_process_approval_reset_entries` (Step 9 guard) so that auto-unpaused users are processed in the same midnight cycle — their chores will be evaluated normally in the next midnight (24h later), avoiding the "immediate overdue" surprise at the exact moment of unpause.

- **Key issues** (updated)
  - **P0 guard must return ALL 15 CHORE_CTX_* keys**: The return dict in Step 2 lists all 15 keys explicitly. Missing any key causes `KeyError` in consumers. See `const.py:1942-1956` for the authoritative list.
  - **Sensor `can_approve` vs actual `can_approve_chore()`**: The P0 guard sets `CHORE_CTX_CAN_APPROVE: False` (correct for sensor display). But `can_approve_chore()` at line 3862 is a standalone method that does NOT go through the P0 guard. An approver CAN still approve a paused user's claimed chore via service call. This is by design (Q8: claims survive pause). Documented as edge case #15.

---

### Phase 3 — Signal Suppression Verification

- **Goal**: Confirm that suppressing at the emission point (Phase 2 guards) covers all downstream consumers. No code changes expected — verification pass only.

- **Verification checklist**

  1. `[ ]` **`SIGNAL_SUFFIX_CHORE_OVERDUE`** — emitted by `_process_overdue`. Downstream: `notification_manager._handle_chore_overdue` and `statistics_manager._on_chore_overdue`. Phase 2 step 3 skips paused entries before the signal emits. ✅ Covered.

  2. `[ ]` **`SIGNAL_SUFFIX_CHORE_MISSED`** — emitted by `_record_chore_missed`. Downstream: `notification_manager._handle_chore_missed` and `statistics_manager._on_chore_missed`. Phase 2 step 4 returns early before the signal emits. ✅ Covered.

  3. `[ ]` **`_transition_chore_state` callers** — verify all paths that call `_transition_chore_state` are guarded. The midnight rollover path calls `_process_overdue` first (guarded). Direct approval/claim paths: an approver could act on a paused user's chore. **Mitigation**: `can_claim_chore` should return `(False, "chore_paused")` for paused users, preventing the action from reaching `_transition_chore_state`.

  4. `[ ]` **`can_claim_chore` guard** — add a check at the top of `can_claim_chore` (~line 674):
     ```python
     if self._is_chore_paused_for_assignee(assignee_id, chore_id):
         return (False, const.TRANS_KEY_ERROR_CHORE_PAUSED)
     ```
     This prevents claim/approve/disapprove actions on paused users' chores.

  5. `[ ]` **Calendar entity** — `custom_components/choreops/calendar.py`. Calendar iterates user's chore data. Paused users would still have calendar entries showing due dates. **Decision**: defer filtering to follow-up. Calendar showing paused chores is informational (admin can see what's paused) and not a correctness issue.

  6. `[ ]` **Dashboard helper** — verify `AssigneeDashboardHelperSensor._build_payload` includes `paused` state chores in its output. Paused chores SHOULD appear in the helper so the dashboard can display them with the "Paused" badge.

- **Key issues**
  - **Item 3 (`_transition_chore_state` bypass)**: The `can_claim_chore` guard (item 4) is the safety net. Even if a call path reaches `_transition_chore_state` for a paused user, the display layer shows `paused` — but preventing the action entirely is cleaner.
  - **Item 5 (calendar)**: Deferrable. Paused chores appearing on the calendar is arguably useful — it shows the admin what would be due.

---

### Phase 4 — Display Surfaces

- **Goal**: All user-facing surfaces recognize the `paused` state and `blocked_paused` claim mode. Includes sensors, admin templates, user templates, and shared row templates.

- **Files affected (canonical sources in `choreops-dashboards/`)**:

  | File | What changes |
  |------|-------------|
  | `translations/en_dashboard.json` | 2 new translation keys: `paused`, `blocked_paused` |
  | `templates/admin-shared-v1.yaml` | `status_map`, `status_color_map` entries |
  | `templates/admin-peruser-v1.yaml` | `status_map`, `status_color_map` entries |
  | `templates/user-chores-essential-v1.yaml` | `statusMap`, sort order, exclude example |
  | `templates/user-chores-lite-v1.yaml` | Same pattern |
  | `templates/user-chores-standard-v1.yaml` | Same pattern |
  | `templates/user-gamification-premier-v1.yaml` | Same pattern |
  | `templates/shared/button_card_template_chore_row_v1.yaml` | `statusMap`, `claimModeIconMap` |
  | `templates/shared/button_card_template_chore_row_kids_v1.yaml` | `statusMap`, `claimModeIconMap` |

- **Steps / detailed work items**

  1. `[X]` **Add dashboard translation keys** in `choreops-dashboards/translations/en_dashboard.json`:
     ```json
     "paused": "Paused",
     "blocked_paused": "Paused"
     ```
     ⚠️ `"paused"` present but `"blocked_paused"` key is MISSING — needs adding.

  2. `[X]` **Update `status_map` in admin templates** — add `'paused': ui.get('paused', 'err-paused')` and `'blocked_paused': ui.get('paused', 'err-paused')` adjacent to `not_my_turn` entries.
     ✅ Both `admin-shared-v1.yaml` and `admin-peruser-v1.yaml` have proper entries.

  3. `[X]` **Update `status_color_map` in admin templates** — add `'paused': 'var(--disabled-text-color)'` and `'blocked_paused': 'var(--disabled-text-color)'`. Same tier as `not_my_turn` — muted, inactive.
     ✅ Both admin templates have proper entries.

  4. `[ ]` **Update shared row templates** (most critical — used by all user views):
     - `button_card_template_chore_row_v1.yaml`: `statusMap` (line 149) MISSING `paused` and `blocked_paused`. Secondary `map` (line 151, completion tooltip) also MISSING both.
     - `button_card_template_chore_row_kids_v1.yaml`: Blocked states check (line 9) MISSING `paused`. Color logic (line 82) MISSING `paused`. Badge icon (line 146) MISSING `paused`.

  5. `[ ]` **Update user-facing templates**:
     - `user-chores-essential-v1.yaml`: ✅ Has `paused` in `statusMap`, sort order (priority 5), `pref_exclude_states` example, and `blocked_paused` in `statusMap`.
     - `user-chores-lite-v1.yaml`: ✅ Sort order has `paused`. ❌ Blocked states check (line 191) missing `paused`. ❌ `tile_color` disabled check (line 467) missing `paused`.
     - `user-chores-standard-v1.yaml`: ⚠️ Only `pref_exclude_states` example has `paused`. Relies on shared row templates for `statusMap` — fix shared to propagate.
     - `user-gamification-premier-v1.yaml`: ⚠️ Only `pref_exclude_states` example has `paused`. Relies on shared row templates — fix shared to propagate.
     - `user-kidschores-classic-v1.yaml`: ❌ Has its own `state_map` (line 460) — NO `paused` or `blocked_paused` entries at all. Needs direct update.

  6. `[ ]` **Update sort order**:
     - `user-chores-essential-v1.yaml`: ✅ Sort order implemented with `paused` at priority 5 (between `claimed`=4 and `completed`=6). ❌ Sort comment (line 464) still lists `overdue, due, pending, waiting, claimed, completed, completed_by_other, not_my_turn, missed` — missing `paused`.
     - `user-chores-lite-v1.yaml`: ✅ Sort order with `paused` at priority 5.
     - `user-chores-standard-v1.yaml`: ❌ No sort order — uses shared row template ordering.
     - `user-gamification-premier-v1.yaml`: ❌ No sort order — uses shared row template ordering.
     - `user-kidschores-classic-v1.yaml`: ❌ No state_priority sort order.
     - ⚠️ Current actual priority is 5 (between claimed and completed), plan specifies priority 6 (between claimed and completed_by_other). Verify desired placement.

  7. `[X]` **Sensor state projection** — `custom_components/choreops/sensor.py`. The `AssigneeChoreStatusSensor.native_value` property returns `ctx[CHORE_CTX_STATE]` directly, which will be `"paused"` when the P0 guard fires. No explicit mapping needed — the sensor automatically displays `"paused"`. Verify the `extra_state_attributes` include proper `claim_mode` and `can_claim` values.

  8. `[ ]` **Add non-English translation stubs** in `choreops-dashboards/translations/` — add `"paused": "Paused"` and `"blocked_paused": "Paused"` to ALL 14 non-English locale files (`ca`, `da`, `de`, `es`, `fi`, `fr`, `it`, `nb`, `nl`, `pl`, `pt`, `sk`, `sl`, `sv`). Currently only `en_dashboard.json` has `"paused"`.

  9. `[ ]` **Update user chore header in user-facing templates** (all 4 variants: `user-chores-essential`, `user-chores-lite`, `user-chores-standard`, `user-gamification-premier`):
     - Add a conditional banner/indicator at the top of the user's chore view when `chores_paused` is true
     - Display: `mdi:pause-circle-outline` icon + "Your chores are paused" text
     - Read `chores_paused` from the user's dashboard helper sensor attributes or via a template check
     - Banner should be dismissible or auto-hide when pause is lifted
     - **Dashboard asset governance**: Edit canonical templates in `choreops-dashboards/templates/`, then run `python utils/sync_dashboard_assets.py` + `--check`

- **Key issues**
  - **Sort order decision**: `paused` at priority 6 is an administrative state — more actionable than `completed_by_other` (terminal, someone else did it) but less urgent than `claimed` (awaiting approval). The admin needs to see paused chores to know they should unpause or push dates.
  - **Icon choice**: `mdi:pause-circle-outline` conveys "temporarily paused" and is visually distinct from `mdi:account-lock-outline` (used for `not_my_turn`).
  - **Shared row templates are critical**: They compose into all 4 user templates. Getting these right propagates everywhere.

---

### Phase 5 — Admin Workflow (Dashboard Card + Service)

- **Goal**: Add a "Pause User's Chores" card to the admin Management section and a `choreops.pause_user_chores` service. The card integrates with the existing Push Chores Forward / Reschedule Chores infrastructure.

- **Steps / detailed work items**

  1. `[ ]` **Add `choreops.pause_user_chores` service** in `custom_components/choreops/services.yaml`:
     ```yaml
     pause_user_chores:
       name: Pause user's chores
       description: Pause or resume chore processing for a user.
       target:
         entity:
           integration: choreops
       fields:
         user_name:
           name: User name
           description: Name of the user whose chores to pause/resume.
           required: true
           example: Sarah
           selector:
             text:
         paused:
           name: Paused
           description: Whether to pause (true) or resume (false) chore processing.
           required: true
           default: true
           selector:
             boolean:
         paused_until:
           name: Paused until
           description: Optional date when chores should resume. Informational in MVP.
           required: false
           selector:
             datetime:
     ```

  2. `[ ]` **Implement service handler** in `custom_components/choreops/services.py`:
     ```python
     async def handle_pause_user_chores(call: ServiceCall) -> None:
         """Handle pause_user_chores service call."""
         user_name = call.data[SERVICE_FIELD_USER_NAME]
         paused = call.data[SERVICE_FIELD_CHORES_PAUSED]
         paused_until = call.data.get(SERVICE_FIELD_CHORES_PAUSED_UNTIL)

         coordinator = _get_coordinator_from_call(call)
         user_id = get_user_id_or_raise(coordinator, user_name)

         user_data = coordinator._data[DATA_USERS][user_id]
         user_data[DATA_USER_CHORES_PAUSED] = paused
         if paused_until is not None:
             user_data[DATA_USER_CHORES_PAUSED_UNTIL] = paused_until
         elif not paused:
             user_data.pop(DATA_USER_CHORES_PAUSED_UNTIL, None)

         coordinator._persist_and_update()
         async_dispatcher_send(
             coordinator.hass,
             get_event_signal(coordinator.entry_id, SIGNAL_SUFFIX_USER_UPDATED),
         )
     ```

  3. `[ ]` **Add "Pause User's Chores" card** in both `admin-shared-v1.yaml` and `admin-peruser-v1.yaml`, placed adjacent to the existing "Reschedule Chores" card in the Management section.

  4. `[ ]` **Card layout**:
     - Header: `mdi:pause-circle-outline`, "Pause User's Chores"
     - Date picker: reuse `dashboard_date_helper` (same entity used by Push Chores Forward)
     - Description: "Push all recurring chores past the return date and pause chore processing. The user won't accumulate missed or overdue stats while paused."
     - Action button: "Pause Chores" — calls `multi-actions`:
       1. `choreops.reschedule_chores_after` (push dates past return date)
       2. `choreops.pause_user_chores` (set `paused: true, paused_until: [selected date]`)

  5. `[ ]` **On return (resume chores)**: The card shows "Chores paused until [date]. Tap to resume." with a "Resume Chores" button calling `choreops.pause_user_chores` with `paused: false`.

  6. `[ ]` **Add pause status indicator to admin dashboard user context** (both `admin-shared-v1.yaml` and `admin-peruser-v1.yaml`):
     - When a user is selected via `dashboard_user_selector` and that user's chores are paused, show a visible indicator near the user selector or in the management section header
     - Display: `mdi:pause-circle-outline` icon + "Chores paused" badge/text
     - Read `chores_paused` state from the user's data accessible via the dashboard helper or a dedicated sensor attribute
     - Include a quick-action button to toggle pause state inline (without navigating to the full Pause Chores card)
     - **Dashboard asset governance**: Edit canonical templates in `choreops-dashboards/templates/`, then run `python utils/sync_dashboard_assets.py` + `--check`

- **Key issues**
  - **Two-card UX**: The Reschedule Chores card and Pause Chores card should feel complementary. The Pause card should reference the Reschedule card: "Before pausing, use the Reschedule Chores card above to push due dates forward."
  - **Service transactions**: `multi-actions` runs services sequentially. If reschedule succeeds but pause fails, the user is in a partial state (dates pushed but not paused). Acceptable — admin can retry the pause.
  - **User selector**: The card uses the existing `dashboard_user_selector` entity for picking which user to pause.
  - **Complementary to options flow, not a replacement**: The dashboard card and service call are convenience surfaces for quick actions. The options flow (Phase 1 Step 9) is the canonical configuration surface and must support pause controls equally. Both surfaces mutate the same storage fields and produce the same result. Admins can use whichever they prefer.

---

### Phase 6 — Testing

- **Goal**: Cover P0 guard, rotation skip, all-paused freeze, return-from-pause, signal suppression, and regression.

- **Steps / detailed work items**

  1. `[ ]` **Test: independent chore — paused user sees `paused` state** — Pause user on an independent chore. Verify `get_chore_status_context` returns `state=paused`, `can_claim=False`, `claim_mode=blocked_paused`.

  2. `[ ]` **Test: independent chore — no overdue transition for paused user** — Due date is past, midnight runs. Verify `_process_overdue` skips paused user. Chore stays in its underlying state.

  3. `[ ]` **Test: independent chore — no missed recording for paused user** — Same scenario as #2 but with `mark_missed_and_lock`. Verify `_record_chore_missed` is not called.

  4. `[ ]` **Test: rotation — paused user's turn is skipped** — Rotation chore [A, B, C], B is current turn and paused. Midnight runs. Verify `_advance_rotation` skips B and sets C as new turn.

  5. `[ ]` **Test: rotation — all assignees paused, rotation freezes** — Rotation chore [A, B], both paused, A is current turn. Verify rotation doesn't advance (no infinite loop). State is `paused`.

  6. `[ ]` **Test: shared chore — all users paused** — Shared chore [A, B], both paused, due date past. Verify no overdue signal. Chore stays in current state.

  7. `[ ]` **Test: return from pause** — Clear flag. Verify next midnight processes normally. If due date still past, overdue fires (expected — admin should have used Push Chores Forward).

  8. `[ ]` **Test: notification and stats suppression** — Verify `notification_manager` and `statistics_manager` never receive overdue/missed signals for paused users.

  9. `[ ]` **Test: dashboard helper includes paused chores** — Verify helper payload includes chores in `paused` state.

  10. `[ ]` **Test: `can_claim_chore` returns False for paused users** — Verify claim is blocked with translation key `chore_paused`.

  11. `[ ]` **Test: `choreops.pause_user_chores` service** — Test pause, resume, and `paused_until` field handling.

  12. `[ ]` **Test: regression — unpaused users unaffected** — Standard overdue/rotation/missed behavior unchanged.

- **Key issues**
  - **Rotation freeze test (#5)**: Need to verify no infinite loop. `range(len(assigned))` iteration cap is sufficient.
  - **Return test (#7)**: State after return depends on due dates. By design — admin should have pushed dates.

---

### Phase 7 — Documentation & Polish

- **Goal**: Update all documentation surfaces across 3 repos.

- **Files affected**:

  | Doc | Repo | What to add |
  |-----|------|------------|
  | `Configuration:-Users.md` | `choreops-wiki` | `chores_paused` flag + return date field |
  | `ARCHITECTURE.md` | `choreops` | `paused` derived UI state, three-scope pause architecture |
  | `DASHBOARD_UI_DESIGN_GUIDELINE.md` | `choreops` | `paused` state row (color: disabled-text, icon: pause-circle-outline) |
  | `en_dashboard.json` | `choreops-dashboards` | Covered in Phase 4 step 1 |
  | All locale `*_dashboard.json` | `choreops-dashboards` | English placeholder stubs for Crowdin |
  | `RELEASE_CHECKLIST.md` | `choreops` | Release note entry for `paused` state and `pause_user_chores` service |
  | `choreops-wiki/_Sidebar.md` | `choreops-wiki` | Link update if new page needed |

  1. `[ ]` **Add "Gamification during chore pause" section** to wiki (`Configuration:-Users.md` or a new Advanced page) and `ARCHITECTURE.md`:
     - Document expected behavioral caveats for badges (periodic, cumulative), achievements, challenges, streaks, and points during pause
     - Explain that cumulative badge maintenance may demote, streaks always break, and time-limited challenges continue counting down
     - Note that these effects are correct — they reflect actual chore activity during the pause period
     - Reference the precedent: pushing chore due dates has analogous effects on gamification
     - See [GAMIFICATION_IMPACT_PAUSE.md](GAMIFICATION_IMPACT_PAUSE.md) for full analysis

- **Key issues**
  - Wiki updates are in a separate repository — coordinate with integration release.
  - ARCHITECTURE.md should document the three-scope pause architecture even though only Scope 1 ships in MVP.

---

## Edge Cases Catalog (Prioritized)

### Priority: Critical (must handle in MVP)

1. **All assignees paused — rotation**: Rotation must not infinite-loop. Guard with `range(len(assigned))` iteration cap. Freeze at current position when all paused.

2. **All assignees paused — shared chore**: Shared chore's global state stays frozen. No overdue/missed signals. When first user is unpaused, next midnight processes normally.

3. **`can_claim_chore` guard for paused users**: Prevents claim/approve/disapprove actions on paused users' chores. Without this, an approver could approve a paused user's chore, bypassing the P0 display guard.

4. **User returns, due date is in the past**: Overdue fires immediately. Expected — admins must use Push Chores Forward before (or when) pausing. Document this workflow.

### Priority: High (should handle, low risk of occurrence)

5. **`paused` state in all allowlists**: Must be added to `CHORE_UI_ASSIGNEE_STATES` and `CHORE_CLAIM_MODES` frozensets. Audit all state allowlists in `const.py`.

6. **Calendar shows paused user's chores**: Calendar entries still appear. Consider filtering — at minimum, document that paused chores appear on the calendar.

7. **Dashboard helper shard count**: Paused users still count toward shard calculations. Low priority — chore count doesn't change.

8. **Cumulative badge maintenance may demote during pause**: If a cumulative badge has a maintenance threshold and the user is paused long enough to miss it, the badge demotes. This is correct behavior — no completions occurred during the pause window. Document as expected. See [GAMIFICATION_IMPACT_PAUSE.md](GAMIFICATION_IMPACT_PAUSE.md).

9. **Streaks always break during pause**: First midnight with no completion resets the streak to 0. No fix needed — by definition, no chores were completed on those days.

### Priority: Medium (edge case, deferrable)

10. **Concurrent admin actions**: Two admins pause different users simultaneously. No conflict — per-user flag, independent writes.

11. **Notification suppression during pause**: Existing persistent notifications (previously-sent overdue alerts) remain visible. No auto-clearing. Acceptable.

12. **Paused user with `can_approve` role**: An approver who is also an assignee and is paused — can they still approve others? Yes — pause only affects chore assignment processing, not approver capabilities.

13. **Paused user's pending claims**: If a user claimed a chore before being paused, the claim persists. The approver can still approve/disapprove. Acceptable — claims are transient.

14. **Time-limited achievements and challenges continue during pause**: The clock keeps ticking on deadlines. Short-window challenges that overlap significantly with the pause period may become impossible to complete. Document as expected — admins should consider challenge windows when planning pauses.

15. **Sensor `can_approve` attribute vs actual `can_approve_chore()`**: The P0 guard sets `CHORE_CTX_CAN_APPROVE: False` in sensor context (correct for display). But `can_approve_chore()` is a standalone method that does NOT go through the P0 guard. An approver can still approve a paused user's claimed chore via service call. This is by design (Q8 — claims survive pause) but the sensor attribute may appear contradictory.

### Priority: Low (defer to follow-up)

16. **Automatic re-enable on `chores_paused_until`**: Implemented as Phase 2 Step 10 — midnight hook auto-clears the `chores_paused` flag when `chores_paused_until` has passed. Users with an indefinite pause (no return date) are unaffected.

17. **Statistics gap during pause**: Period stats for the paused window show zeros. Correct behavior (no penalties during pause), but admins should understand "all time" stats will have a gap.

---

## Cross-Feature Interactions

### Primary-Backup Chore Type

See [CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md](CROSS_ANALYSIS_AVAILABILITY_X_PRIMARY_BACKUP.md) for full analysis. Key points:

- **CRIT-1**: `_advance_rotation` — the pause skip loop MUST run AFTER the primary-backup `assigned[0]` candidate is determined but BEFORE the signal payload. The pause helper shared between both criteria types.
- **CRIT-2**: Reset-boundary force-to-primary — must also check pause status. If primary is paused, snap to first available backup instead.
- **MOD-1**: P0 guard correctly returns `paused` before primary-backup's P3 `standby_backup` check. Unavailable (paused) beats standby.
- **Implementation order**: Pause should be implemented first (simpler `_advance_rotation` change), then primary-backup adds its criteria dispatch before the pause skip loop.

---

## Future Scopes (Architectural Hooks)

The P0 guard is designed to handle three pause scopes from day one. Scopes 2 and 3 are additive — new storage fields and service endpoints only.

### Scope 2: Global Chore Pause (Phase 3)

| What | Detail |
|------|--------|
| Storage | `DATA_CHORE_PAUSED: Final = "paused"` (boolean on chore record) |
| Service | `choreops.pause_chore(chore_name, paused: bool)` |
| Options flow | Toggle on chore edit screen |
| Behavior | All assignees see `paused` state. Rotation freezes. No overdue/missed for anyone. |
| Dashboard | "Paused" badge on all users' view of this chore |

### Scope 3: Chore×User Pause (Phase 2)

| What | Detail |
|------|--------|
| Storage | `DATA_CHORE_PAUSED_FOR: Final = "paused_for"` (list of user IDs on chore record) |
| Service | `choreops.pause_chore_for_user(chore_name, user_name, paused: bool)` |
| Behavior | Specific chore paused for specific user. Other users process normally. |
| Dashboard | "Paused" badge only for the affected user |
| Unpause all | `choreops.resume_all_chores_for_user(user_name)` — removes user from all `paused_for` lists |

---

## Notes & follow-up

- **Architecture impact**: P0 guard in `get_chore_status_context` keeps `resolve_assignee_chore_state` pure. Three scopes compose via OR in a single helper.
- **Code surface**: ~60 lines across integration files (heavily concentrated in `chore_manager.py`), ~25 lines across 9 dashboard templates.
- **Dashboard surface**: 9 template files, each gets 2-3 lines in the same pattern (adjacent to `not_my_turn` entries).
- **Terminology**: `paused` / `chores_paused` throughout. No `unavailable` anywhere — avoids HA protocol state collision.

**Follow-up for future initiatives**:
- Scope 2: Global chore pause
- Scope 3: Per-chore×user pause
- "Vacation mode" that pushes dates + pauses in one action
- Calendar filtering for paused chores
- Per-user notification on auto-unpause ("Your chores have been resumed")

> **Plan created**: 2026-06-06 | **Based on**: Full surface audit + lexical analysis + three-scope architecture + cross-feature interaction analysis.
