# Initiative plan

## Initiative snapshot

- **Name / Code**: Chore display state hard-fork (`approved` → `completed`, helper key `state`) / `CHORE_STATUS_COMPLETED_ALIAS_SENSOR_ONLY`
- **Target release / milestone**: Next ChoreOps patch/minor release after validation
- **Owner / driver(s)**: ChoreOps maintainers (Integration + QA)
- **Status**: Not started

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Contract analysis and guardrails | Confirm state contract boundaries, signal consistency, and UI-layer coupling | 0% | Includes required dashboard-helper/test impact analysis before coding |
| Phase 2 – Sensor alias + translations | Implement display-only alias and translation coverage without backend FSM/storage changes | 0% | Includes shared chore global sensor rotation coverage |
| Phase 3 – Test remediation | Update sensor/state assertions and translation checks to new display contract | 0% | Keep tests aligned with sensor-only objective |
| Phase 4 – Validation and release readiness | Run quality gates, verify no signal/state contract drift, and finalize docs | 0% | Platinum-quality handoff evidence required |

1. **Key objective** – Introduce a display-only `completed` status and move dashboard helper chore key to `state` using the existing single state-calculation path, while preserving backend lifecycle/state machine behavior and event contracts.
2. **Summary of recent work** – Architectural and code-path research completed for: sensor state source-of-truth, context provider, signal usage (`chore_approved` vs `chore_completed`), translation paths, dashboard-helper dependencies, and affected tests.
3. **Next steps (short term)** – Execute Phase 1 analysis checklist and freeze implementation boundaries before any code edits.
4. **Risks / blockers**
   - Dashboard helper currently mirrors `CHORE_CTX_STATE` and may diverge from sensor alias unless intentionally handled.
   - Existing tests hard-assert `approved` in sensor state and helper status sets.
   - Event consumers depend on `SIGNAL_SUFFIX_CHORE_APPROVED` and `SIGNAL_SUFFIX_CHORE_COMPLETED` semantics; these must remain unchanged.
  - Existing lifecycle paths can emit signals after state transitions that no longer match naive UI expectations (must be contract-tested).
  - Overengineering risk: attempting millisecond-level strict lockstep can add unnecessary complexity.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `docs/QUALITY_REFERENCE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `custom_components/choreops/managers/chore_manager.py` (state context provider + approval/completion signal emission)
   - `custom_components/choreops/engines/chore_engine.py` (FSM/state resolution)
   - `custom_components/choreops/sensor.py` (assignee status sensor + dashboard helper sensor)
   - `custom_components/choreops/translations/en.json` (sensor state localization)
   - `custom_components/choreops/dashboards/translations/en_dashboard.json` (dashboard translation key set)
6. **Decisions & completion check**
   - **Decisions captured**:
     - This initiative is **display contract only** for chore status sensor output.
     - Backend chore lifecycle states, storage keys, transition engine logic, and manager workflow events remain unchanged.
     - Dashboard template rework is explicitly deferred; only analysis and test safety checks are in scope.
   - **Hard-fork rule**: no compatibility layers, no wrapper aliases, no dual helper fields (`status` + `state`).
   - Dashboard helper chore key is `state` only.
   - Reuse existing `get_chore_status_context()` state path; do not introduce duplicate state-calculation methods.
     - Signal contract must remain: approval emits `SIGNAL_SUFFIX_CHORE_APPROVED`; completion bookkeeping remains on `SIGNAL_SUFFIX_CHORE_COMPLETED`.
    - **Signal/UI lockstep invariant** applies to all chore lifecycle signals, not only `completed`.
    - For every chore lifecycle signal, define and test expected post-persist helper/sensor state contract.
    - **Timing tolerance policy**: transient in-transaction state changes are acceptable; required invariant is final post-settle alignment.
  - Shared chore global status sensor remains in scope and will include rotation completion types plus rotation-appropriate attributes.
   - **Completion confirmation**: `[ ]` All required follow-up items complete (analysis, implementation, tests, validation, docs) before owner sign-off.

> **Important:** Keep the Summary section current after each meaningful execution update (phase progress, blockers, scope adjustments).

## Scope boundaries (non-negotiable)

### Hard-fork constraints (non-negotiable)

1. No compatibility layer for dashboard helper chore state keys.
2. No mirrored `status` field retained for transition.
3. No adapter/wrapper methods that duplicate existing state calculation.
4. No signal payload/semantic changes.

### In scope

- Add a **display-only alias** so assignee chore status sensor can report `completed` in place of `approved` where appropriate.
- Rename dashboard helper chore key from `status` to `state` (hard fork, no compatibility fallback).
- Extend shared chore global status sensor creation/contract to include rotation modes.
- Ensure translation coverage for the new visible state in integration sensor translations.
- Update tests to reflect the aliased display contract while preserving backend-state assertions where needed.
- Perform focused analysis of dashboard helper state usage and associated tests to prevent silent UI drift.
- Define and enforce chore signal-to-visible-state lockstep contracts for claimed/approved/completed/overdue/missed/reset and due-window/reminder families.
- Define explicit post-settle alignment requirements (`await hass.async_block_till_done()`), not strict millisecond lockstep.

### Out of scope

- Any backend FSM transition changes in `ChoreEngine`.
- Any storage schema/state key migration (no schema bump).
- Any manager event/signal payload contract changes.
- Dashboard template behavior changes (templates are being reworked separately).
- Any compatibility support for deprecated helper key names.

## Detailed phase tracking

### Phase 1 – Contract analysis and guardrails

- **Goal**: Freeze exact implementation boundaries and prevent unintended coupling regressions before code changes.
- **Steps / detailed work items**
  1. [ ] Confirm sensor state source-of-truth and alias insertion point.
     - Files:
       - `custom_components/choreops/sensor.py` (~`AssigneeChoreStatusSensor.native_value`, around lines 805-812)
       - `custom_components/choreops/managers/chore_manager.py` (~`get_chore_status_context`, around lines 3483-3614)
   - Validate that aliasing occurs at display layer only, not persisted/context source layer.
   - Confirm existing single calculation path: `get_chore_status_context()` (via `CHORE_CTX_STATE`) remains authoritative.
   2. [ ] **Required extra analysis**: map dashboard helper use of chore states and associated tests.
     - Files:
       - `custom_components/choreops/sensor.py` (~`AssigneeDashboardHelperSensor._calculate_chore_attributes`, around lines 4060-4105)
       - `tests/test_dashboard_helper_size_reduction.py` (~valid status set check, around lines 448-452)
       - `custom_components/choreops/dashboards/templates/*.yaml` (analysis only; no edits)
   - Deliverable: explicit impact note for hard-fork rename (`status` → `state`) and test updates.
  3. [ ] Audit event-signal consistency and freeze no-change contract.
     - Files:
       - `custom_components/choreops/const.py` (~signal suffix definitions around lines 232-245)
       - `custom_components/choreops/managers/chore_manager.py` (~approval/completion emits around lines 1068-1175 and approved event helper around 2448-2488)
       - `custom_components/choreops/managers/economy_manager.py` (listens to `chore_approved`)
       - `custom_components/choreops/managers/notification_manager.py` (approval-notification flow)
        - Guardrail: no change to `chore_approved` vs `chore_completed` semantics or payloads.
       - Confirm single-path emit logic coverage:
          - `chore_approved` uses canonical helper path (`_emit_chore_approved_event`)
          - `chore_completed` emits remain behavior-equivalent across criteria branches
          - Add explicit regression assertions to prevent future divergence.
      4. [ ] Build lifecycle signal/UI lockstep matrix (all chore signal families).
        - Families:
         - `chore_claimed`, `chore_approved`, `chore_completed`, `chore_overdue`, `chore_missed`, `chore_status_reset`
         - `chore_due_window`, `chore_due_reminder` (advisory temporal signals)
        - For each: define authoritative source, persist boundary, expected helper/sensor state set, and allowed exceptions.
        - Explicitly mark contract scope as **post-settle** and document that transient in-flight transitions do not fail contract.
      5. [ ] Define exact alias behavior matrix by completion criteria (independent/shared/shared_first/rotation/shared_all partial states).
  4. [ ] Define exact alias behavior matrix by completion criteria (independent/shared/shared_first/rotation/shared_all partial states).
     - Files:
       - `custom_components/choreops/engines/chore_engine.py` (~`resolve_assignee_chore_state`, lines ~638-711)
       - `custom_components/choreops/managers/chore_manager.py` (~single-claimer `completed_by_other` override, lines ~3588-3600)
     - Guardrail: alias applies only where current display state is `approved`; do not alter `approved_in_part`, `completed_by_other`, etc.
  6. [ ] Capture phase decision log in this plan before implementation starts.
     - Include: helper-status strategy, test strategy split (sensor assertions vs manager/backend assertions), and translation key handling.
- **Key issues**
  - High risk of accidental backend-state mutation if alias is inserted in manager/engine layer.
  - Potential UI mismatch if sensor alias and helper status diverge without deliberate test coverage.

### Phase 2 – Sensor alias + translations

- **Goal**: Implement minimal, robust display alias and required localization support with strict boundary adherence.
- **Steps / detailed work items**
  1. [ ] Introduce display alias constant(s) for clarity and maintainability.
     - File: `custom_components/choreops/const.py` (near chore state constants around lines 1750-1768)
     - Pattern: use explicit display-only naming/comments aligned with existing “not persisted” state conventions.
  2. [ ] Implement sensor-only state alias mapping.
     - File: `custom_components/choreops/sensor.py` (`AssigneeChoreStatusSensor.native_value`)
     - Behavior: map context `approved` → sensor output `completed` based on Phase 1 contract.
  3. [ ] Implement dashboard helper key rename and state projection.
     - File: `custom_components/choreops/sensor.py` (`_calculate_chore_attributes`)
     - Replace helper key `status` with `state` (hard-fork, no alias field).
     - Helper `state` must be derived from the same projected value used by assignee chore sensor state.
   4. [ ] Add translation entries for sensor/helper state localization.
     - Files:
       - `custom_components/choreops/translations/en.json` (`entity.sensor.assignee_chore_status_sensor.state`)
      - Any required dashboard translation source files if helper-readable state labels require key updates.
     - Guardrail: no direct non-English hand edits (localization pipeline remains authoritative).
  5. [ ] Validate no manager/engine/event contract changes occurred.
     - Files for regression check:
       - `custom_components/choreops/managers/chore_manager.py`
       - `custom_components/choreops/engines/chore_engine.py`
       - `custom_components/choreops/managers/economy_manager.py`
       - `custom_components/choreops/managers/notification_manager.py`
  6. [ ] Expand shared chore global sensor criteria to include rotation modes.
     - Files:
       - `custom_components/choreops/engines/chore_engine.py` (`is_shared_chore` and/or new explicit global-scope helper)
       - `custom_components/choreops/sensor.py` (creation gate for `SystemChoreSharedStateSensor`)
     - Contract: include `rotation_simple` and `rotation_smart` in global/system-level chore state sensor coverage.
  7. [ ] Add rotation-appropriate attributes to shared chore global sensor.
     - File: `custom_components/choreops/sensor.py` (`SystemChoreSharedStateSensor.extra_state_attributes`)
     - Minimum planning contract:
       - rotation mode indicator
       - current turn assignee id/name
       - rotation override/open-cycle visibility attributes (if available in chore data)
     - Guardrail: additive attributes only; no backend logic rewrites.
- **Key issues**
  - Translation drift risk between integration sensor translations and dashboard UI translation dictionaries.
  - Helper/template reliance on literal `approved` can break filtering if helper behavior changes without coordinated tests.
  - Shared global sensor scope change requires test updates for creation expectations and attribute schema.

### Phase 3 – Test remediation

- **Goal**: Update and harden tests for display alias behavior while preserving backend lifecycle verification.
- **Steps / detailed work items**
  1. [ ] Update tests asserting assignee chore **sensor state** to expected alias contract.
     - Candidate files:
       - `tests/test_rotation_fsm_states.py` (e.g., sensor state assertions around lines 210-214)
       - `tests/test_chore_scheduling.py` (e.g., sensor state assertion around lines 2398-2401)
       - `tests/test_chore_services.py` (display-state helper expectations)
  2. [ ] Update dashboard helper tests for hard-fork key rename.
     - File: `tests/test_dashboard_helper_size_reduction.py` (helper item key and state set assertions)
     - Migrate assertions from `chore["status"]` to `chore["state"]`.
  3. [ ] Add/adjust translation validation tests for new state key coverage.
     - Candidate files:
       - `tests/test_translations_custom.py` (dashboard translation integrity; if impacted)
       - Existing integration translation tests/snapshots (if present) for `en.json` state map.
    4. [ ] Add targeted regression tests for single-path state and signal contracts.
     - Suggested pattern:
          - Assert manager context remains `approved` while sensor state and helper `state` show `completed`.
          - Assert `SIGNAL_SUFFIX_CHORE_APPROVED` and `SIGNAL_SUFFIX_CHORE_COMPLETED` behavior remains unchanged in workflow tests.
          - Assert no helper `status` key is emitted (hard-fork guarantee).
    5. [ ] Add lockstep contract tests for non-completed lifecycle signals.
      - `chore_claimed`: validate expected **post-settle** visible state contract (including auto-approve branch expectations).
      - `chore_approved`: contract must account for immediate-reset modes (`upon_completion`, late immediate clear) and validate **post-settle** state.
      - `chore_overdue` / `chore_missed` / `chore_status_reset`: emitted state must match persisted visible state after update (**post-settle**).
        - `chore_due_window` / `chore_due_reminder`: assert temporal-window contract and document advisory semantics explicitly.
    6. [ ] Keep test fixtures and constants aligned with modern helper imports and no direct const-module imports.
     - Follow `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` patterns.
      7. [ ] Add shared global sensor tests for rotation criteria.
        - Validate sensor is created for `rotation_simple` and `rotation_smart` chores.
        - Validate rotation-specific global attributes are present and coherent.
- **Key issues**
  - Over-updating tests can accidentally encode dashboard-template assumptions that are intentionally deferred.
  - Need clear split between display-level assertions and backend-level assertions to avoid future ambiguity.

### Phase 4 – Validation and release readiness

- **Goal**: Complete platinum-quality validation and produce clean handoff evidence.
- **Steps / detailed work items**
  1. [ ] Run local quality gates in required order.
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/choreops/`
     - `python -m pytest tests/ -v --tb=line`
  2. [ ] Run focused targeted suites for changed areas first (fast feedback).
     - `python -m pytest tests/test_rotation_fsm_states.py -v`
     - `python -m pytest tests/test_chore_scheduling.py -v`
     - `python -m pytest tests/test_dashboard_helper_size_reduction.py -v`
     - `python -m pytest tests/test_chore_services.py -v`
  3. [ ] Confirm translation build/readiness expectations for changed source files.
     - Ensure English source is correct and localization workflow expectations are documented.
  4. [ ] Validate no hidden scope expansion occurred.
     - Explicitly confirm dashboard templates were not modified.
     - Explicitly confirm manager/event contracts unchanged.
  5. [ ] Update Summary table percentages and closeout notes.
- **Key issues**
  - Full test suite runtime can be long; targeted test-first sequence is required for efficient failure isolation.

## Testing & validation

- **Planned command sequence**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/test_rotation_fsm_states.py -v`
  - `python -m pytest tests/test_chore_scheduling.py -v`
  - `python -m pytest tests/test_dashboard_helper_size_reduction.py -v`
  - `python -m pytest tests/test_chore_services.py -v`
  - `python -m pytest tests/ -v --tb=line`
- **Validation assertions to record**
  - Sensor displays `completed` per contract.
  - Helper `chores[*].state` matches chore status sensor state exactly at post-settle boundary.
   - Helper `chores[*].status` is absent.
  - Backend state machine/storage paths still operate on `approved` where expected.
  - `chore_approved` and `chore_completed` signal semantics remain unchanged.
  - Lifecycle signal/UI lockstep matrix passes for all chore signal families with documented exceptions only.
  - All lockstep assertions are evaluated at post-settle boundary (`await hass.async_block_till_done()`), not intra-transaction micro-steps.
   - Dashboard-helper behavior is explicitly documented and test-covered, even with template changes deferred.

## Notes & follow-up

- **Signal consistency note**: This initiative must not conflate approval and completion events. Existing dual-signal design (`chore_approved` and `chore_completed`) supports separate consumers (economy/notifications/gamification/reporting), and display aliasing must not modify that architecture.
- **Signal lockstep note**: The architecture must define expected UI-state alignment for every emitted chore signal so events and visible state remain predictably consistent under all reset/automation branches.
- **No-overengineering note**: The contract targets final consistency after workflow completion; it does not require strict synchronization during internal sub-step transitions that occur within a single workflow transaction.
- **Future handoff note**: When dashboard template rework begins, this initiative’s helper-state decision should be revisited and consolidated into the template state-map/filter contract to remove interim ambiguity.

> **Template usage notice:** This plan follows the project template structure and is stored in `docs/in-process/` for execution tracking.