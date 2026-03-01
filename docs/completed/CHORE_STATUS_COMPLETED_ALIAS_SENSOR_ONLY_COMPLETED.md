# Initiative plan

## Initiative snapshot

- **Name / Code**: Chore calculated state matrix update (`completed`) + aligned display surfaces / `CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY`
- **Target release / milestone**: Next ChoreOps patch/minor release
- **Owner / driver(s)**: ChoreOps maintainers (Integration + QA)
- **Status**: Complete (Phases 1-5 complete)

## Summary table

| Phase                                           | Description                                                       | %    | Quick notes                                                                            |
| ----------------------------------------------- | ----------------------------------------------------------------- | ---- | -------------------------------------------------------------------------------------- |
| Phase 1 – Matrix re-evaluation                  | Define exact `completed` semantics inside calculated state matrix | 100% | Matrix frozen with branch-aware rules                                                  |
| Phase 2 – State-calculation integration         | Implement `completed` in matrix method(s) with centralized logic  | 100% | Integrated in context path; UI force alias removed                                     |
| Phase 3 – Contract hardening + global authority | Enforce Option A and make global aggregation authority explicit   | 100% | Per-user/global contracts enforced; manager context + engine rotation override unified |
| Phase 4 – Verification hardening                | Expand targeted tests with deviation-control guardrails           | 100% | Contract tests added; per-user/global allowlists and mappings verified                 |
| Phase 5 – Documentation closeout + handoff      | Publish final technical matrices and run final quality gates      | 100% | In-process + architecture + wiki/translation closeout complete                         |

## Re-evaluation trigger (why this plan changed)

- The prior approach (`approved` always projected to `completed` at UI boundary) was rejected.
- Correct requirement: add `completed` **properly in the calculated state matrix**, then display that matrix output consistently in chore status sensor and dashboard helper.
- This must not be a one-off bridge; it must be integrated and branch-correct.

## Non-negotiable objective

Create a branch-aware calculated `completed` state that is accurate across completion criteria and role contexts, then use that calculated state in:

- `AssigneeChoreStatusSensor.native_value`
- `AssigneeDashboardHelperSensor` chore item state key (`state`)

## Decision update (2026-03-01) — Option A selected

Option A is now the active contract for this initiative:

- Per-user per-chore `state` shows only that assignee's lifecycle status or direct blocker.
- Aggregate/shared progress semantics must be represented by chore-level global state and related attributes.
- `approved_in_part` and `claimed_in_part` are global aggregation concepts, not per-user context states.

Decision consequences for this plan:

- Remove per-user `approved_in_part` from `get_chore_status_context(...)[state]` outputs.
- Keep per-user approved mapping criteria-aware for blockers/overlays, but finalize approved assignees as `completed`.
- Keep global persisted partial aggregate state token as `approved_in_part`, while global UI publication uses `completed_in_part`.
- Explicitly verify global shared chore sensor state and global state attributes remain consistent.

## Architecture decision update (workflow vs display responsibilities)

This initiative now locks the following architecture split:

- Engine (`ChoreEngine`) remains the workflow state authority (workflow checkpoints and FSM resolution inputs/outputs).
- Manager (`ChoreManager`) remains the assignee display/context authority (per-user context shaping and overlays).
- Global/chore-level aggregate state must have one explicit authoritative calculation path and one explicit publication path.

Implementation intent:

- Rework existing methods first (no parallel logic paths).
- Avoid adding new public APIs unless required to remove duplication safely.
- Any added helper must reduce duplication while preserving the single-source-of-truth contract.

## State model for final approval (single source of truth)

This section is the only authoritative state contract for this initiative.

### A) Per-user persisted state (storage)

Storage key: `assignee_chore_data[chore_id][DATA_USER_CHORE_DATA_STATE]`

- `pending`
- `claimed`
- `approved`
- `overdue`
- `missed`

### B) Per-user UI state (context + assignee sensor)

Source: `get_chore_status_context(...)[state]` and assignee chore sensor `native_value`

- `pending`
- `due`
- `waiting`
- `claimed`
- `overdue`
- `missed`
- `not_my_turn`
- `completed`
- `completed_by_other`

Must never emit:

- `approved`
- `approved_in_part`
- `claimed_in_part`
- `independent`
- `unknown`

### C) Global aggregate persisted state (storage)

Storage key: `chores_data[chore_id][DATA_CHORE_STATE]`

- `pending`
- `claimed`
- `claimed_in_part`
- `approved`
- `approved_in_part`
- `overdue`
- `missed`
- `independent`

Target rule: do not persist `unknown` in normal workflows.

### D) Global UI state (shared/global sensor publication)

Source: shared/global chore sensor `native_value`

- `pending`
- `due`
- `waiting`
- `claimed`
- `completed`
- `completed_in_part`
- `overdue`
- `missed`
- `independent`
- `claimed_in_part`

Must never emit:

- `completed_by_other`
- `not_my_turn`
- `approved_in_part`

Locked naming decision:

- Global persisted state remains `approved_in_part`.
- Global UI state token is `completed_in_part`.
- Translation label for `completed_in_part` is `Completed (in-part)`.

Master-list enforcement rule:

- This section is the authoritative allowlist/denylist for all state outputs in code, tests, and documentation.
- If any file, test, or doc conflicts with this list, this section wins and conflicting artifacts must be updated.

## Scope boundaries (non-negotiable)

### In scope

- Matrix/state calculation path:
  - `custom_components/choreops/engines/chore_engine.py` (`resolve_assignee_chore_state`)
  - `custom_components/choreops/managers/chore_manager.py` (`get_chore_status_context` final state shaping)
- Display surfaces:
  - `custom_components/choreops/sensor.py` (consume matrix output; no force alias)
- Constants/translations/tests for the new calculated state behavior

### Out of scope

- Signal redesign/audit (separate initiative)
- Storage schema or migration changes
- Dashboard template redesign
- Unrelated refactors

## Current baseline correction (required first)

- A prior attempt introduced unconditional UI projection (`approved` → `completed`) in `sensor.py`.
- This approach is rejected and must be removed/reworked before matrix integration.
- Treat this as architecture correction, not optional cleanup.

## Exact file/symbol anchors

- `custom_components/choreops/engines/chore_engine.py`
  - `resolve_assignee_chore_state(...)`
- `custom_components/choreops/managers/chore_manager.py`
  - `get_chore_status_context(...)`
- `custom_components/choreops/sensor.py`
  - `_project_chore_display_state(...)` (current rejected unconditional alias)
  - `AssigneeChoreStatusSensor.native_value`
  - `AssigneeDashboardHelperSensor._calculate_chore_attributes`
- `custom_components/choreops/const.py`
  - chore state literals and helper key constants
- `custom_components/choreops/translations/en.json`
  - `entity.sensor.assignee_chore_status_sensor.state`

## Phase 1 – Matrix re-evaluation

- **Goal**: Lock exact semantics for when state is `completed` vs `approved`.
- **Steps**
  - [x] Build explicit per-criteria decision table for assignee-visible calculated state:
    - `independent`
    - `shared`
    - `shared_first`
    - `rotation_simple`
    - `rotation_smart`
  - [x] Define actor vs non-actor outcomes where relevant (`completed_by_other`, `not_my_turn`, etc.).
  - [x] Define precedence order including `completed` relative to existing states.
  - [x] Define invariants for partial completion (`approved_in_part`) vs fully completed outcomes.
  - [x] Freeze acceptance matrix before coding.
- **Key issues**
  - “Approved always means completed” is invalid for some branches (must be criteria-aware).
- **Phase exit criteria**
  - [x] Decision table approved with no ambiguous branch semantics.
  - [x] Precedence ordering finalized and documented.
  - [x] Actor/non-actor outcomes explicitly defined for shared-first and rotation.

### Phase 1 required artifact (decision table) — frozen

The table below is approved for implementation:

| Criteria     | Assignee context                 | Preconditions                                           | Expected calculated state                           |
| ------------ | -------------------------------- | ------------------------------------------------------- | --------------------------------------------------- |
| independent  | actor approved in period         | approval recorded, no immediate reset branch            | completed                                           |
| shared       | actor approved, not all approved | actor approved in period; shared cycle incomplete       | completed (global state carries `approved_in_part`) |
| shared       | actor approved, all approved     | actor approved in period; shared cycle complete         | completed                                           |
| shared_first | actor (first claimer)            | actor has pending claim or approved in period           | claimed (pre-approval) or completed (post-approval) |
| shared_first | non-actor assignee               | another assignee is active (claimed/approved)           | completed_by_other                                  |
| rotation\_\* | turn-holder assignee             | approved in period for current turn; no immediate reset | completed                                           |
| rotation\_\* | non-turn assignee                | before steal window                                     | not_my_turn                                         |
| rotation\_\* | non-turn assignee                | overdue + allow_steal active                            | overdue                                             |

### Phase 1 precedence and invariants (frozen)

Precedence for assignee-visible calculated state (highest to lowest):

1. `completed_by_other`
2. `completed`
3. `claimed`
4. `not_my_turn`
5. `missed`
6. `overdue`
7. `waiting`
8. `due`
9. `pending`

Invariants:

- `completed` is never produced by unconditional display remapping.
- `approved_in_part` is a global aggregation semantic (not a per-user state output) under Option A.
- `completed_by_other` remains the non-actor blocking outcome for shared-first/rotation active-assignee branches.
- If an immediate-reset path clears approval-period context, post-settle state can be `pending` and does not violate matrix semantics.

### Phase 1 validation note

- Per directive, validation gates were not rerun in this phase.
- Latest confirmed gate status is accepted as baseline:
  - `./utils/quick_lint.sh --fix`: passed
  - mypy (via quick lint): zero errors
  - tests: previously confirmed successful

## Phase 2 – State-calculation integration

- **Goal**: Implement `completed` in the matrix path, not as surface-only remap.
- **Steps**
  - [x] Remove/rework unconditional UI projection helper in `sensor.py` (no force mapping).
  - [x] Implement completed-aware matrix logic in `resolve_assignee_chore_state` and/or manager final shaping path.
  - [x] Keep a single authoritative calculated state result in `get_chore_status_context()[state]`.
  - [x] Ensure branch rules are encoded once and reused by both sensor/helper consumers.
  - [x] Update constants if a dedicated `CHORE_STATE_COMPLETED` literal is introduced.
- **Exact methods to change**
  - `custom_components/choreops/engines/chore_engine.py`
    - `resolve_assignee_chore_state(...)`
  - `custom_components/choreops/managers/chore_manager.py`
    - `get_chore_status_context(...)`
  - `custom_components/choreops/sensor.py`
    - `AssigneeChoreStatusSensor.native_value`
    - `AssigneeDashboardHelperSensor._calculate_chore_attributes`
- **Key issues**
  - Avoid introducing duplicate calculator paths.
- **Phase exit criteria**
  - [x] No unconditional UI force alias remains.
  - [x] Context `state` is matrix-derived (no post-hoc force remap).
  - [x] Quick lint passes.

## Phase 3 – Contract hardening + global authority

- **Goal**: Finalize Option A per-user contract and remove global aggregation ambiguity.
- **Interpretation lock**:
  - Per-user context state is personal lifecycle/blocker only.
  - Global partial progress states are aggregate-only.
  - This is calculated-state rework, not display aliasing.
- **Steps**
  - [x] Rework `get_chore_status_context(...)` so per-user approved resolves to `completed` and never `approved_in_part`.
  - [x] Preserve per-user blocker overlays (`completed_by_other`, `not_my_turn`, `waiting`, `missed`) without introducing aggregate semantics into per-user state.
  - [x] Reconcile global aggregation authority by reworking existing paths so one path is clearly authoritative and the other path is delegation/adapter only.
  - [x] Ensure shared/global sensor state and `ATTR_GLOBAL_STATE` derive from the same aggregate contract without contradictory overlays, with explicit mapping `approved_in_part` (persisted) → `completed_in_part` (UI).
  - [x] Add explicit invariants in code-level docs/comments where authority boundaries are enforced.
  - [x] Update docstrings/comments for every changed/added method so descriptions exactly match final behavior and contracts.
- **Exact methods to change/verify**
  - `custom_components/choreops/managers/chore_manager.py`
    - `get_chore_status_context(...)`
    - `_update_global_state(...)`
  - `custom_components/choreops/engines/chore_engine.py`
    - `resolve_assignee_chore_state(...)` (verify unchanged workflow authority)
    - `compute_global_chore_state(...)` (authority/adapter reconciliation)
  - `custom_components/choreops/sensor.py`
    - assignee chore status sensor (`state`)
    - dashboard helper chore item state (`state`)
    - shared/global chore state sensor state and attributes
- **Key issues**
  - Current duplicated global-state logic can drift and must be de-ambiguated.
- **Phase exit criteria**
  - [x] Per-user context state cannot emit `approved_in_part` or `claimed_in_part`.
  - [x] Per-user context state output is restricted to the approved allowlist.
  - [x] Global aggregate state can emit `approved_in_part` / `claimed_in_part` where expected.
  - [x] Global UI state emits `completed_in_part` (never `approved_in_part`) for partial completion display.
  - [x] Global aggregate persisted state does not settle on `unknown` in normal/covered workflows.
  - [x] Authority boundary (engine workflow vs manager context shaping vs global aggregation path) is explicit and verified.
  - [x] All changed/added methods in touched files have accurate, non-stale docstrings/comments.
  - [x] Quick lint passes.

## Phase 4 – Verification hardening

- **Goal**: Enforce design-intent verification and prevent “test to green” drift.
- **Non-negotiable test change protocol**
  - [x] Test edits must be limited to assertions whose expected state labels changed by approved design decisions.
  - [x] Any additional assertion change requires explicit rationale in PR notes under “Deviation from plan”.
  - [x] No broad assertion weakening (`in (...)`, looser contains checks, or removed assertions) without explicit approval.
  - [x] Preserve existing behavior checks not covered by Option A/global-authority decisions.
  - [x] If failing tests suggest behavior outside approved matrices/scope, pause and request approval before scope expansion.
- **Current robust coverage to preserve**
  - [x] Keep existing shared-first `completed_by_other` precedence coverage intact.
  - [x] Keep existing rotation lock/waiting/missed coverage intact.
  - [x] Keep existing shared global persisted partial progression (`claimed_in_part`, `approved_in_part`) coverage intact.
- **Missing/insufficient coverage to add (required)**
  - [x] Add test: per-user context state never emits `approved_in_part` for `shared_all` after approval.
  - [x] Add allowlist test: per-user context/sensor states are always within the approved per-user allowlist and never in the forbidden set.
  - [x] Add test: per-user sensor state mirrors manager context state contract for the same assignee/chore.
  - [x] Add allowlist test: global UI state publication stays within the approved global UI allowlist and excludes blocker-only states.
  - [x] Add mapping test: persisted global `approved_in_part` is published as global UI `completed_in_part`.
  - [x] Add parity test: manager global aggregate state == shared global sensor state output for representative criteria/time windows.
  - [x] Add parity test: authoritative global aggregation function/path matches persisted `DATA_CHORE_STATE` outcomes across shared/shared_first/rotation sequences.
  - [x] Add regression test: persisted global state does not remain `unknown` under valid covered workflows.
  - [x] Add regression test: only expected state-label deltas occur in impacted scenarios (no hidden collateral state shifts).
  - [x] End-of-phase cleanup: remove `CHORE_STATE_UNKNOWN` from persisted global-state allowlist and normalize aggregate fallbacks to `pending`.
- **Targeted files to review/update (strictly scoped)**
  - [x] `tests/test_chore_state_matrix.py`
  - [x] `tests/test_workflow_chores.py`
  - [x] `tests/test_workflow_gaps.py`
  - [x] `tests/test_rotation_fsm_states.py`
  - [x] `tests/test_chore_scheduling.py`
  - [x] `tests/test_dashboard_helper_size_reduction.py`
  - `tests/helpers/workflows.py` (contracts/docs only if required)
- **Phase exit criteria**
  - [x] All new/updated assertions map directly to approved state-contract decisions.
  - [x] No non-scoped behavior assertions changed without documented approval.
  - [x] Quick lint passes.

### Phase 4 deviation note

- Monolithic final gate `python -m pytest tests/ -v --tb=line` was terminated by container memory limits (exit 137)
- Equivalent broad validation was completed with deterministic shards:
  - `python -m pytest tests/test_[a-g]*.py -v --tb=line` (pass)
  - `python -m pytest tests/test_[h-m]*.py -v --tb=line` (pass)
  - `python -m pytest tests/test_[n-z]*.py -v --tb=line` (pass after contract-aligned assertion/key updates)

## Phase 5 – Documentation closeout + handoff

- **Goal**: Publish clear technical state contracts and complete final validation.
- **Documentation deliverables (required final product)**
  - [x] Publish a clear per-user/per-chore state matrix (engine workflow result + manager UI/context overlays) with plain-language explanations.
  - [x] Publish a clear global state matrix (authoritative aggregate calculation + sensor publication/overlays) with plain-language explanations.
  - [x] Include an explicit persisted-vs-UI mapping table for global partial state: `approved_in_part` → `completed_in_part`.
  - [x] Add a short “how to reason about state” section describing workflow-checkpoint vs display-context vs global-aggregate layers.
  - [x] Document expected/intentional differences between stored per-user state and displayed per-user state.
  - [x] Audit all chore-related `en.json` translation files for missing and extra state keys against this master list.
  - [x] Verify technical comments/docstrings in touched implementation methods align with the published matrices.
- **Implementation/validation steps**
  - [x] Reconcile technical docs with as-built behavior and update references.
  - [x] Run focused chore test groups, then final full validation gates.
  - [x] Confirm no out-of-scope signal redesign or storage schema migration was introduced.
  - [x] Publish completion report with explicit expected-state-delta list.
- **Phase exit criteria**
  - [x] Final technical documentation includes both required matrices and explanatory notes.
  - [x] Method comment/docstring accuracy audit completed for all touched methods.
  - [x] All final validation gates pass.
  - [x] Handoff summary includes changed files, rationale, approved deviations (if any), and deferred-work confirmation.

### Phase 5 closeout notes

- Translation audit result (`custom_components/choreops/translations/en.json`):
  - Assignee UI state keys include: `pending`, `due`, `waiting`, `claimed`, `overdue`, `missed`, `not_my_turn`, `completed`, `completed_by_other`.
  - Shared/global state keys include: `pending`, `due`, `waiting`, `claimed`, `completed`, `completed_in_part`, `overdue`, `missed`, `claimed_in_part`, `independent`.
  - No `approved_in_part` UI publication key is present in shared/global state translations.
- Dashboard translation audit action: replaced `approved_in_part` with `completed_in_part` and added `waiting`, `not_my_turn`, and `missed` labels in both dashboard translation sources.
- `docs/completed/**` updates were intentionally skipped per execution constraint for this run.

## Quality and guardrails (Platinum)

- [x] Single authoritative state-calculation path
- [x] No UI-layer hardcoded force alias that bypasses matrix semantics
- [x] Per-user `state` contract remains personal/blocker-only (Option A)
- [x] Per-user `state` output remains inside the explicit allowlist; forbidden states are never emitted
- [x] Aggregate partial states (`approved_in_part`, `claimed_in_part`) remain global-only
- [x] Global UI partial state token is `completed_in_part` and translation label is `Completed (in-part)`
- [x] Global aggregation authority is explicit (no ambiguous duplicated logic)
- [x] Test updates are expectation-driven (state contract deltas), not convenience-driven
- [x] Method-level comments/docstrings are updated and accurate for all touched methods
- [x] No signal semantic changes in this initiative
- [x] Strict typing and docs maintained
- [x] No test dilution (no broad ambiguous assertions)
- [x] Branch-specific expectations remain explicit

## Builder trap prevention checklist (mandatory)

- [ ] Avoid dual-authority drift: no independent global-state logic in both manager and engine without explicit delegation ownership.
- [ ] Avoid display/workflow conflation: do not move display semantics into workflow checkpoints.
- [ ] Avoid stored/display conflation: do not treat persisted per-user state and displayed per-user state as interchangeable.
- [ ] Avoid scope creep: no signal redesign, schema migration, or dashboard redesign in this initiative.
- [ ] Avoid test dilution: no assertion weakening to force green tests.
- [ ] Cover rotation/open-cycle edges (override + allow_steal) in parity verification.

## Deviation and escalation protocol

- If unexpected behavior appears outside approved matrices, document the delta and pause implementation.
- Record proposed options and impacts in this plan before continuing.
- Resume only after explicit approval for the deviation is captured under Decisions.

## Key documentation scan/update list (closeout)

At initiative close, scan and update these key docs to match final behavior:

- [x] `docs/in-process/CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY_IN-PROCESS.md` (final as-built semantics + phase completion)
- [ ] `docs/completed/legacy-kidschores/CHORE_LOGIC_V050_SUP_STATE_MATRIX.md` (engine vs manager display scope clarification)
- [x] `docs/ARCHITECTURE.md` (state-contract language for per-user vs global aggregation)
- [ ] `docs/DEVELOPMENT_STANDARDS.md` (if state-contract conventions need codification)
- [x] Chore technical docs section: publish final per-user matrix and global matrix with clear examples and layer responsibilities
- [x] `choreops-wiki/Advanced:-Chores.md` (user-facing explanation of per-user vs global shared states)
- [x] `custom_components/choreops/translations/en.json` full chore-state key audit (missing + extra keys) and wording verification
- [x] `choreops-dashboards/translations/en_dashboard.json` full chore-state key audit (missing + extra keys) and wording verification

Execution constraint note:

- `docs/completed/**` was not modified in this run by request.

## Validation gates

- Intermediate phases: quick lint only (as directed)
- Final phase:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/test_dashboard_helper_size_reduction.py -v`
  - `python -m pytest tests/test_rotation_fsm_states.py -v`
  - `python -m pytest tests/test_chore_scheduling.py -v`
  - `python -m pytest tests/test_chore_services.py -v`
  - `python -m pytest tests/test_workflow_chores.py -v`
  - `python -m pytest tests/test_workflow_gaps.py -v`
  - `python -m pytest tests/ -v --tb=line`

## References

- `docs/DEVELOPMENT_STANDARDS.md`
- `docs/ARCHITECTURE.md`
- `docs/QUALITY_REFERENCE.md`
- `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
- `custom_components/choreops/engines/chore_engine.py`
- `custom_components/choreops/managers/chore_manager.py`
- `custom_components/choreops/sensor.py`
- `custom_components/choreops/const.py`
- `custom_components/choreops/translations/en.json`
- `choreops-dashboards/translations/en_dashboard.json`

## Decisions & completion check

- **Decisions captured**:
  - Unconditional `approved`→`completed` display mapping is rejected.
  - Option A selected: per-user `state` is personal lifecycle/blocker only.
  - `approved_in_part` and `claimed_in_part` are global-only aggregate states.
  - Global persisted partial state remains `approved_in_part`; global UI partial state is `completed_in_part` with translation `Completed (in-part)`.
  - Engine remains workflow authority; manager remains per-user context/display authority.
  - Global aggregate calculation/publication path must be explicit and non-ambiguous.
  - `completed` must be integrated in calculated state matrix logic.
  - Sensor/helper must display matrix output, not override it ad hoc.
  - Signal-contract work remains deferred.
- **Completion confirmation**: `[x]` All phase gates complete and matrix behavior validated.
- **Current closeout status**: Documentation, translation audits, and final validation gates complete.

## Builder handoff (ready)

Execution order (must follow):

1. Phase 3 contract hardening and global authority reconciliation
2. Phase 4 verification hardening with strict no-dilution protocol
3. Phase 5 documentation closeout, translation audits, and final validation gates

Builder acceptance checklist (must all be true before closeout):

- Per-user UI state set matches this master list exactly (no forbidden states emitted)
- Global persisted partial state remains `approved_in_part`
- Global UI partial state is `completed_in_part` with translation `Completed (in-part)`
- All chore-related `en.json` files pass missing/extra key audit against this master list
- No out-of-scope signal/schema/dashboard redesign changes introduced
- Final completion report lists all intentional state-label deltas and confirms none others occurred
