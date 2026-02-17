# Initiative Plan: CHORE_LOGIC Phase 5 — Waiting Claim Path Reinstatement

## Initiative snapshot

- **Name / Code**: CHORE_LOGIC Phase 5 — Waiting Claim Path Reinstatement
- **Target release / milestone**: v0.5.0-beta4 follow-up patch (no schema bump)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Phase 5 validation complete

## Summary & immediate steps

| Phase / Step                     | Description                                                  | % complete | Quick notes                                                                   |
| -------------------------------- | ------------------------------------------------------------ | ---------- | ----------------------------------------------------------------------------- |
| Phase 1 – Contract alignment     | Reconcile plan intent vs current code and docs               | 100%       | ✅ Completed; docs aligned to implementation gap                              |
| Phase 2 – Core logic restoration | Re-enable due-window waiting path using existing fields      | 100%       | ✅ Implemented in engine/manager/sensor; no new storage fields                |
| Phase 3 – Flow/service parity    | Keep create/update UX aligned with existing options/services | 100%       | ✅ Flow + services + metadata parity aligned                                  |
| Phase 4 – Tests & validation     | Add focused regression tests around waiting/can-claim        | 100%       | ✅ Targeted + full gates passing                                              |
| Phase 5 – State truth model      | Finalize persisted-vs-derived chore state contract and apply | 100%       | ✅ Matrix, write/read guardrails, contract tests, and final gates all passing |

1. **Key objective** – Reinstate Phase 5 “claim restriction before due window” behavior by using existing `due_window_offset` and current `can_claim` pipeline, returning `waiting` as a calculated lock state.
2. **Summary of recent work** – Phase 1 completed: doc contract mismatch corrected across architecture/standards/initiative references, including explicit note that `waiting` is currently not emitted due to removed P6 branch.
3. **Next steps (short term)** – Prepare completion handoff/archive once owner confirms phase closeout.
4. **Risks / blockers** – No active blockers.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/in-process/CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md)
   - [custom_components/kidschores/engines/chore_engine.py](../../custom_components/kidschores/engines/chore_engine.py)
   - [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py)
   - [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py)
   - [custom_components/kidschores/data_builders.py](../../custom_components/kidschores/data_builders.py)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep D-04 intent: claim restriction is derived from existing `due_window_offset` presence and due-window timing.
     - Do **not** add `claim_restriction_enabled` to storage constants/forms/services; existing `type_defs.py` optional key remains unused legacy typing and should not drive behavior.
     - Use existing pipeline only: `resolve_kid_chore_state()` → `can_claim_chore()` (engine) → `ChoreManager.can_claim_chore()` and `claim_chore()` guards.
     - Do **not** overload unrelated selectors (`approval_reset_type`, `completion_criteria`, `overdue_handling_type`) to encode claim restriction.

- **Completion confirmation**: `[x]` All follow-up items completed before requesting owner approval.

## Tracking expectations

- **Summary upkeep**: Update this plan table after each merged implementation/test pass.
- **Detailed tracking**: Keep architectural rationale in this plan; keep code/test details in PR notes.

## Detailed phase tracking

### Phase 1 – Contract alignment

- **Goal**: Remove ambiguity between blueprint intent and present implementation behavior.
- **Steps / detailed work items**
  1. - [x] Update decision notes in [docs/in-process/CHORE_LOGIC_V050_IN-PROCESS.md](CHORE_LOGIC_V050_IN-PROCESS.md#L229) to reflect actual implementation gap: `waiting` currently not emitted.
  - File: `docs/in-process/CHORE_LOGIC_V050_IN-PROCESS.md`
  - Hint: around current D-04 + Phase 5 sections (~L229, ~L608).
  2. - [x] Add short architecture note in [docs/ARCHITECTURE.md](../ARCHITECTURE.md) under chore FSM section clarifying `waiting` is derived (not persisted) and gated by due-window math.
  - File: `docs/ARCHITECTURE.md`
  - Hint: chore state resolution / manager-engine boundaries section.
  3. - [x] Add implementation guardrail note in [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md): avoid introducing dedicated claim-restriction field; use existing due-window field.
  - File: `docs/DEVELOPMENT_STANDARDS.md`
  - Hint: choreography/logic placement and no-duplication rules.
- **Key issues**
  - Existing plan docs imply feature complete while code path is disabled; this mismatch risks future regressions.
    - Validation blocker while closing phase: `tests/test_phase4_pipeline_guards.py::test_idempotency_overdue_already_overdue` fails in baseline with assertion "Expected idempotency debug log".

### Phase 2 – Core logic restoration

- **Goal**: Re-enable waiting lock in the engine and ensure all claim paths consume it.
- **Steps / detailed work items**
  1. - [x] Restore P6 waiting branch in [custom_components/kidschores/engines/chore_engine.py](../../custom_components/kidschores/engines/chore_engine.py#L680).
     - Replace removed placeholder with condition:
       - `due_window_start is not None`
       - `due_date is not None`
       - `now < due_window_start`
       - return `(CHORE_STATE_WAITING, "waiting")`
  2. - [x] Ensure `can_claim_chore()` lock handling maps lock reasons to valid translation keys/messages.
     - File: `custom_components/kidschores/engines/chore_engine.py`
     - If returning bare `"waiting"`, manager/service exception path must not degrade to generic `already_claimed`.
  3. - [x] Align manager error propagation in [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py#L615) for lock reasons `waiting|not_my_turn|missed`.
     - Add explicit branch or translation mapping instead of falling through default error.
  4. - [x] Verify read-path parity in [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py#L2948) and status-context path (~L3156) still uses same engine-derived state for both dashboard and claim validation.
  5. - [x] Populate chore status sensor `Lock_reason` attribute from resolved lock context so waiting/claim locks are visible without inferring from state alone.
  - Files: `custom_components/kidschores/managers/chore_manager.py` (status context builder) and corresponding chore status sensor entity platform.
  - Rule: expose lock reason token (`waiting`, `not_my_turn`, `missed`, etc.) when locked; set `None` when claim is currently allowed.
- **Key issues**
  - Lock reason strings are state tokens, while exception paths currently prefer translation keys; mismatch can produce wrong user-facing error text.

### Phase 3 – Flow/service parity (no new fields)

- **Goal**: Keep UX/API stable while ensuring claim restriction behavior is controllable via existing fields only.
- **Steps / detailed work items**
  1. - [x] Confirm [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L717) remains the sole UI path for due-window configuration (`chore_due_window_offset`).
  2. - [x] Confirm [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L895) transform path maps due-window offset consistently for create/edit.
  3. - [x] Confirm [custom_components/kidschores/services.py](../../custom_components/kidschores/services.py#L357) `UPDATE_CHORE_SCHEMA` keeps `due_window_offset` mutable and explicitly supports `chore_claim_lock_until_window` parity.
  4. - [x] Remove/update stale comments indicating immutable criteria in [custom_components/kidschores/services.py](../../custom_components/kidschores/services.py#L259), and align `services.yaml` + `translations/en.json` service descriptions.
- **Key issues**
  - API docs/comments drift was corrected in this phase.

### Phase 4 – Tests & validation

- **Goal**: Add focused test coverage proving waiting lock behavior and preventing silent removal in future refactors.
- **Steps / detailed work items**
  1. - [x] Add engine-level tests in [tests/test_chore_engine.py](../../tests/test_chore_engine.py) for P6 waiting:
     - pre-window returns `(waiting, lock_reason=waiting)`;
     - in-window returns `due` or `pending` depending on due timing.
  2. - [x] Add manager-level tests in [tests/test_chore_scheduling.py](../../tests/test_chore_scheduling.py#L2200) or a dedicated file to validate `can_claim_chore()` rejects before window and allows once window opens.
  3. - [x] Add sensor/status contract checks in [tests/test_ui_manager.py](../../tests/test_ui_manager.py) or existing dashboard-helper tests to verify `lock_reason=waiting` and `available_at` when waiting.
  4. - [x] Add chore status sensor attribute assertions verifying `Lock_reason` mirrors lock context across locked vs claimable states.
  - Target tests: existing chore status sensor tests (or add focused test file if missing coverage).
  5. - [x] Run quality gates:
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/kidschores/`
     - `python -m pytest tests/test_chore_engine.py tests/test_chore_scheduling.py -v --tb=line`
     - `python -m pytest tests/ -v --tb=line` (final confidence run)
- **Key issues**
  - Some legacy tests may encode previous “pending-before-window” semantics and need intentional updates.
  - Progress update (2026-02-13): Engine waiting suite now covers pre-window waiting lock, in-window due state, and lock-disabled pending fallback in `TestResolveKidChoreStateWaiting`.
  - Progress update (2026-02-13): Due-window manager/sensor suite expanded and passing in `tests/test_chore_scheduling.py`:
    - `TestDueWindowClaimLockBehavior.test_can_claim_blocks_before_window_then_allows_in_window`
    - `TestDueWindowClaimLockBehavior.test_manager_can_claim_transitions_from_waiting_to_allowed`
    - `TestDueWindowClaimLockBehavior.test_sensor_available_at_present_only_while_waiting`
    - `TestDueWindowClaimLockBehavior.test_lock_disabled_keeps_pending_without_waiting_attributes`
  - Validation update (2026-02-13): `python -m pytest tests/test_chore_engine.py tests/test_chore_scheduling.py -v --tb=line` passed (`164 passed`).
  - Validation update (2026-02-13): `./utils/quick_lint.sh --fix` now passes end-to-end.

### Phase 5 – State source-of-truth consolidation (final)

- **Goal**: Make chore state ownership explicit by classifying states as persisted workflow checkpoints vs derived/display states, then align implementation to that contract.
- **Steps / detailed work items**
  1. - [x] Add a source-of-truth matrix (state → persisted or derived/display) in this plan and mirror concise guidance in [docs/ARCHITECTURE.md](../ARCHITECTURE.md).
  - Include both kid-level state (`DATA_KID_CHORE_DATA_STATE`) and chore-level aggregate state (`DATA_CHORE_STATE`).
  - Mark which states are event/checkpoint states vs purely computed states.
  2. - [x] Refactor write/read paths to match the matrix (no storing of display-only states; runtime-only states resolved via engine/context).
  - Primary files: [custom_components/kidschores/managers/chore_manager.py](../../custom_components/kidschores/managers/chore_manager.py), [custom_components/kidschores/engines/chore_engine.py](../../custom_components/kidschores/engines/chore_engine.py), [custom_components/kidschores/sensor.py](../../custom_components/kidschores/sensor.py), [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py).
  3. - [x] Add/adjust tests to enforce the contract and prevent drift.
  - Ensure tests cover that derived states are not persisted while persisted checkpoint states remain stable.
  4. - [x] Run final quality gates after consolidation:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Must preserve behavioral parity for existing automations/dashboards while removing unnecessary state persistence.

#### Phase 5 source-of-truth matrix

| Storage key                 | State                                                                                                        | Persisted? | Classification      | Notes                                        |
| --------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------- | ------------------- | -------------------------------------------- |
| `DATA_KID_CHORE_DATA_STATE` | `pending`, `claimed`, `approved`, `overdue`, `missed`                                                        | ✅ Yes     | Workflow checkpoint | Kid-level source-of-truth states             |
| `DATA_KID_CHORE_DATA_STATE` | `due`, `waiting`, `not_my_turn`, `completed_by_other`                                                        | ❌ No      | Derived/display     | Runtime-only from engine/context             |
| `DATA_CHORE_STATE`          | `pending`, `claimed`, `approved`, `overdue`, `claimed_in_part`, `approved_in_part`, `independent`, `unknown` | ✅ Yes     | Aggregate snapshot  | Stored roll-up from per-kid persisted states |

#### Phase 5 implementation updates (2026-02-13)

- Added explicit state contract constants in `const.py`:
  - `CHORE_PERSISTED_KID_STATES`
  - `CHORE_DERIVED_KID_STATES`
  - `CHORE_PERSISTED_GLOBAL_STATES`
- Hardened manager write path in `chore_manager.py::_apply_effect()`:
  - Any non-persisted kid state is normalized to `pending` before storage write.
- Added contract tests:
  - `tests/test_chore_manager.py::TestStatePersistenceContract.test_apply_effect_normalizes_derived_state_to_pending`
  - `tests/test_chore_manager.py::TestStatePersistenceContract.test_apply_effect_persists_missed_checkpoint_state`
  - `tests/test_chore_scheduling.py::TestDueWindowClaimLockBehavior.test_can_claim_blocks_before_window_then_allows_in_window` now asserts storage state remains `pending` while display state is `waiting`.

#### Phase 5 validation notes

- ✅ Targeted suites pass:
  - `python -m pytest tests/test_chore_engine.py tests/test_chore_scheduling.py -v --tb=line` (`164 passed`)
- ✅ Full suite gate passes:
  - `runTests` / `python -m pytest tests/ -v --tb=line` → `1296 passed, 0 failed`
- ✅ Pipeline guard module passes:
  - `python -m pytest tests/test_phase4_pipeline_guards.py -v --tb=line` → `5 passed`
- ✅ Lint/type/architecture gate passes:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/` (`Success: no issues found in 48 source files`)

## Testing & validation

- **Planned tests**: Engine unit tests + manager scheduling behavior + sensor/dashboard helper lock attribute checks.
- **Outstanding tests**: Full suite run required after targeted tests pass.

## Notes & follow-up

- **Architecture recommendation (final)**: Re-implement Phase 5 using existing due-window signal (`due_window_offset`) and current can-claim path; do not overload other selectors and do not add storage fields.
- **Why this fits best**:
  - Preserves established manager/engine separation.
  - Avoids schema churn and migration complexity.
  - Keeps one source of truth for claimability (engine FSM + manager wrappers).
- **Future cleanup (optional, post-fix)**:
  - Remove `claim_restriction_enabled` from `ChoreData` `TypedDict` if confirmed permanently unused to reduce cognitive overhead (separate cleanup PR).
