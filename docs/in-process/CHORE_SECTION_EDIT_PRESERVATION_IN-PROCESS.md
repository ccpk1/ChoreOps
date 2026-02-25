# Initiative Plan Template

## Initiative snapshot

- **Name / Code**: Chore sectioned edit preservation / CSEP-2026-001
- **Target release / milestone**: v0.5.x patch release
- **Owner / driver(s)**: ChoreOps maintainers (Options Flow + Chore domain)
- **Status**: Not started

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Contract audit | Lock field contracts across chore section schema, edit transform, and helper routing | 0% | Prevent silent resets on partial section payloads |
| Phase 2 – Refactor implementation | Apply users/badges update-preserve pattern to chore edit path only | 0% | Keep clear-field behavior explicit |
| Phase 3 – Regression safety net | Add round-trip tests for partial section submits + helper routes | 0% | Focus on daily-multi + per-assignee due dates |
| Phase 4 – Service compatibility validation | Prove chore CRUD services remain behaviorally unchanged | 0% | Shared builder/manager path must be unaffected |

1. **Key objective** – Eliminate chore edit regressions from sectioned payload omission while preserving intentional clear behavior and helper-step complexity.
2. **Summary of recent work**
   - Confirmed users/badges update paths resolve values with precedence `user_input > existing > default`.
   - Confirmed chore edit transform currently defaults missing keys, causing silent resets after section migration.
   - Confirmed chore service CRUD paths use DATA_* contracts and manager CRUD directly, with update-time validation merge.
3. **Next steps (short term)**
   - Document exact preserve-vs-clear rules per chore field group.
   - Refactor chore edit transform contract to be existing-aware in options flow path.
   - Add targeted tests for partial section payloads and helper branch integrity.
4. **Risks / blockers**
   - Daily-multi and INDEPENDENT per-assignee helper flows mutate chore-level and per-assignee fields in sequence; wrong precedence can break source-of-truth transitions.
   - Notification fields use consolidated selector and fan-out booleans; omission handling must not re-enable defaults unexpectedly.
   - Existing tests currently emphasize prefill, not full edit round-trip with partial payload omission.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L976)
   - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L631)
   - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1086)
   - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1170)
   - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1767)
   - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L2140)
   - [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L795)
   - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py#L2912)
   - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py#L1820)
   - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py#L999)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Chore edit path will adopt users/badges preserve semantics (`explicit key required to mutate`).
     - Scope is options-flow edit contract only; no service contract or data schema changes in this initiative.
     - Clear operations remain explicit and field-specific (`clear_due_date`, explicit false/empty/None payloads).
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Contract audit

- **Goal**: Build a complete, field-level preserve/clear contract for chore sectioned edit flows, including helper branches.
- **Steps / detailed work items**
  1. - [ ] Produce a choreography map for edit path branching.
     - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L976-L1248), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1767-L2230)
     - Capture branch gates for INDEPENDENT vs non-INDEPENDENT and DAILY_MULTI routing.
  2. - [ ] Build field matrix: schema section fields vs suggested-values vs transform-consumed keys.
     - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L599-L660), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1408-L1513), [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1170-L1279)
     - Flag omissions/drift (including daily-multi section contract alignment).
  3. - [ ] Define preserve-vs-clear semantics per field family.
     - File: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1000-L1279)
     - Required families: booleans, lists, text offsets, due dates, notifications, per-assignee structures.
  4. - [ ] Confirm parity reference behavior from users and badges.
     - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L515-L680), [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py#L999-L1148), [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py#L1820-L2160)
     - Record reusable implementation pattern.
- **Key issues**
  - Existing chore transform function was designed for flat payload assumptions; section partial payloads changed that assumption.

### Phase 2 – Refactor implementation

- **Goal**: Refactor chore options-flow edit transformation to preserve existing values when section fields are omitted, without breaking explicit clear paths.
- **Steps / detailed work items**
  1. - [ ] Introduce existing-aware field resolver for chore transform path used by options-flow edit.
     - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1170-L1279), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1037-L1047)
     - Contract: `if key in user_input -> use submitted value; else -> preserve existing`.
  2. - [ ] Keep explicit clear mechanics intact.
     - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1014-L1070), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1091-L1188)
     - `clear_due_date` and explicit empty values must still clear as intended.
  3. - [ ] Validate helper-route state handoff assumptions remain unchanged.
     - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1219-L1225), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1767-L2034), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L2140-L2190)
     - Ensure `_chore_being_edited` and template fields remain authoritative for helper steps.
  4. - [ ] Align section contract constants with actual edited fields.
     - File: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L608-L617)
     - Resolve any missing key in section field tuple that is used by edit form.
  5. - [ ] Limit change surface to options-flow + helper transform only.
     - Non-goal files: services, chore manager, data schema migration.
- **Key issues**
  - Over-correcting preserve logic can accidentally block intentional clear operations.

### Phase 3 – Regression safety net

- **Goal**: Add tests that prove sectioned chore edit round-trip preserves stored values while still allowing explicit clears and helper-specific updates.
- **Steps / detailed work items**
  1. - [ ] Add round-trip partial payload test for schedule booleans/offsets.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Scenario: omit schedule section key(s) on edit submit; verify stored values remain unchanged.
  2. - [ ] Add explicit clear test for due-date behavior in edit.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Scenario: submit `clear_due_date=True`; verify cleared storage and subsequent prefill.
  3. - [ ] Add INDEPENDENT + per-assignee helper integrity test.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Scenario: edit main chore with partial payload, then complete per-user details; verify per-assignee structures remain source-of-truth.
  4. - [ ] Add DAILY_MULTI helper integrity test.
     - Files: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py), [tests/test_options_flow_daily_multi.py](../../tests/test_options_flow_daily_multi.py)
     - Scenario: daily-multi times absent then provided in helper; verify no unrelated field reset.
  5. - [ ] Add contract parity test for section tuples ↔ transform field set.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Fail fast when new chore form keys are added but not represented consistently.
  6. - [ ] Planned validation commands for implementer:
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/choreops/`
     - `python -m pytest tests/test_options_flow_per_kid_helper.py -v`
     - `python -m pytest tests/test_options_flow_daily_multi.py -v`
- **Key issues**
  - Existing tests are stronger on prefill than on post-submit persistence semantics.

### Phase 4 – Service compatibility validation

- **Goal**: Verify no behavior change for chore CRUD service contracts and shared manager/builder usage.
- **Steps / detailed work items**
  1. - [ ] Document explicit separation between options-flow transform and service DATA_* mapping path.
     - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L360-L613), [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L860-L950)
  2. - [ ] Confirm no change to service-to-DATA mapping and no schema mutation.
     - File: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L545-L571)
  3. - [ ] Confirm ChoreManager update behavior remains unchanged.
     - File: [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py#L2912-L2995)
  4. - [ ] Add/execute service regression checks (targeted existing service tests).
     - Candidate files: `tests/test_services_*.py` covering create/update chore and due-date updates.
  5. - [ ] Verify no schema migration impact.
     - No `SCHEMA_VERSION` change expected; preserve storage shape.
- **Key issues**
  - Shared builders are used by services and options flow via different upstream shapes; refactor must not alter service input contract.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed: None in planning phase (strategy-only).
- Outstanding tests (to be run by implementer):
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/test_options_flow_per_kid_helper.py -v`
  - `python -m pytest tests/test_options_flow_daily_multi.py -v`
  - Targeted chore service tests in `tests/test_services*.py`
- Links to failing logs or CI runs if relevant:
  - Current suite state should be re-baselined before merging this initiative.

## Notes & follow-up

- This initiative intentionally does not alter service schemas, manager public APIs, or storage schema.
- If preserve-vs-clear semantics reveal ambiguity for any field, create a short supporting addendum in `docs/in-process/` before coding.
- Post-implementation, update architecture/development docs only if a formal contract statement is added for sectioned edit semantics.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
