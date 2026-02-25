# Initiative Plan Template

## Initiative snapshot

- **Name / Code**: Chore sectioned edit preservation / CSEP-2026-001
- **Target release / milestone**: v0.5.x patch release
- **Owner / driver(s)**: ChoreOps maintainers (Options Flow + Chore domain)
- **Status**: Complete

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Contract audit | Lock field contracts across chore section schema, edit transform, and helper routing | 100% | Completed audit; drift and preserve/clear contracts documented |
| Phase 2 – Refactor implementation | Apply users/badges update-preserve pattern to chore edit path only | 100% | Existing-aware edit transform added; clear semantics preserved |
| Phase 3 – Regression safety net | Add round-trip tests for partial section submits + helper routes | 100% | Added and validated regression coverage for sectioned edit preservation contracts |
| Phase 4 – Service compatibility validation | Prove chore CRUD services remain behaviorally unchanged | 100% | Service schemas/mappings unchanged; focused service regressions passed |

1. **Key objective** – Eliminate chore edit regressions from sectioned payload omission while preserving intentional clear behavior and helper-step complexity.
2. **Summary of recent work**
   - Completed Phase 1 contract audit and documented choreography of main edit flow + per-assignee/daily-multi helper routes.
   - Completed Phase 2 implementation for existing-aware chore edit value resolution in helpers + options flow wiring.
   - Completed Phase 3 regression safety net with new tests for partial edit payload preservation, explicit due-date clear transform behavior, INDEPENDENT helper integrity, DAILY_MULTI helper integrity, and section tuple parity.
   - Completed Phase 4 service compatibility validation with focused chore service regressions and explicit contract boundary review.
   - Confirmed users/badges update paths resolve values with precedence `user_input > existing > default`.
   - Confirmed chore edit transform currently defaults missing keys, causing silent resets after section migration.
   - Confirmed chore service CRUD paths use DATA_* contracts and manager CRUD directly, with update-time validation merge.
3. **Next steps (short term)**
   - Finalize initiative completion check and owner sign-off.
   - Optionally capture one short supporting summary doc for preserve/clear contract for future maintainers.
   - Prepare commit message and review bundle.
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
  - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Contract audit ✅

- **Goal**: Build a complete, field-level preserve/clear contract for chore sectioned edit flows, including helper branches.
- **Steps / detailed work items**
  1. - [x] Produce a choreography map for edit path branching.
     - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L976-L1248), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1767-L2230)
     - Capture branch gates for INDEPENDENT vs non-INDEPENDENT and DAILY_MULTI routing.
     - Findings:
       - Main edit path persists first, then conditionally routes to per-assignee helper (`INDEPENDENT` + assignees) and/or daily-multi helper.
       - Helper state handoff uses `_chore_being_edited` and template fields (`_chore_template_*`) as routing contract.
  2. - [x] Build field matrix: schema section fields vs suggested-values vs transform-consumed keys.
     - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L599-L660), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1408-L1513), [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1170-L1279)
     - Flag omissions/drift (including daily-multi section contract alignment).
     - Findings:
       - Chore edit transform consumes many fields with `get(..., default)` behavior; missing keys are treated as reset-to-default.
       - Detected field-contract drift risk where some actively edited fields are not consistently represented across section tuple/suggested/transform contracts.
  3. - [x] Define preserve-vs-clear semantics per field family.
     - File: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1000-L1279)
     - Required families: booleans, lists, text offsets, due dates, notifications, per-assignee structures.
     - Findings:
       - Preserve rule for edit refactor: absent key = preserve existing; present key value (including `False`, `[]`, `""`, `None`) = explicit mutation/clear.
       - `clear_due_date` remains explicit command path and must continue to supersede implicit date preservation.
  4. - [x] Confirm parity reference behavior from users and badges.
     - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L515-L680), [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py#L999-L1148), [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py#L1820-L2160)
     - Record reusable implementation pattern.
     - Findings:
       - Users and badges already implement update-safe merge contract (`user_input > existing > default`) at builder level.
       - Chore options-flow transform is the outlier and should be aligned without touching service CRUD contracts.
- **Key issues**
  - Existing chore transform function was designed for flat payload assumptions; section partial payloads changed that assumption.
  - Pylint numeric score gate is not currently available in this environment (`.pylintrc` contains unsupported option for installed pylint), so lint validation uses `quick_lint` project gate.

### Phase 2 – Refactor implementation ✅

- **Goal**: Refactor chore options-flow edit transformation to preserve existing values when section fields are omitted, without breaking explicit clear paths.
- **Steps / detailed work items**
  1. - [x] Introduce existing-aware field resolver for chore transform path used by options-flow edit.
     - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1170-L1279), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1037-L1047)
     - Contract: `if key in user_input -> use submitted value; else -> preserve existing`.
     - Completed:
       - Added `existing_chore`-aware resolution in chore validation + transform paths.
       - Wired edit flow to pass current chore context into both validation and transform.
  2. - [x] Keep explicit clear mechanics intact.
     - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L1014-L1070), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1091-L1188)
     - `clear_due_date` and explicit empty values must still clear as intended.
     - Completed:
       - `clear_due_date` remains explicit override; absent due-date field now preserves existing where expected.
       - Notification booleans now preserve existing values when consolidated notifications field is omitted.
  3. - [x] Validate helper-route state handoff assumptions remain unchanged.
     - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1219-L1225), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L1767-L2034), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py#L2140-L2190)
     - Ensure `_chore_being_edited` and template fields remain authoritative for helper steps.
     - Completed:
       - Helper-route state variables and routing conditions were left unchanged; edits are limited to value resolution semantics before/at transform.
  4. - [x] Align section contract constants with actual edited fields.
     - File: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L608-L617)
     - Resolve any missing key in section field tuple that is used by edit form.
     - Completed:
       - Confirmed no section tuple mutation required in this phase; alignment risk deferred to Phase 3 parity test coverage.
  5. - [x] Limit change surface to options-flow + helper transform only.
     - Non-goal files: services, chore manager, data schema migration.
     - Completed:
       - Code changes confined to [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py) and [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py).
- **Key issues**
  - Over-correcting preserve logic can accidentally block intentional clear operations.

### Phase 3 – Regression safety net ✅

- **Goal**: Add tests that prove sectioned chore edit round-trip preserves stored values while still allowing explicit clears and helper-specific updates.
- **Steps / detailed work items**
   1. - [x] Add round-trip partial payload test for schedule booleans/offsets.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Scenario: omit schedule section key(s) on edit submit; verify stored values remain unchanged.
   2. - [x] Add explicit clear test for due-date behavior in edit.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Scenario: submit `clear_due_date=True`; verify cleared storage and subsequent prefill.
   3. - [x] Add INDEPENDENT + per-assignee helper integrity test.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Scenario: edit main chore with partial payload, then complete per-user details; verify per-assignee structures remain source-of-truth.
   4. - [x] Add DAILY_MULTI helper integrity test.
     - Files: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py), [tests/test_options_flow_daily_multi.py](../../tests/test_options_flow_daily_multi.py)
     - Scenario: daily-multi times absent then provided in helper; verify no unrelated field reset.
   5. - [x] Add contract parity test for section tuples ↔ transform field set.
     - File: [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
     - Fail fast when new chore form keys are added but not represented consistently.
   6. - [x] Planned validation commands for implementer:
     - `./utils/quick_lint.sh --fix`
     - `mypy custom_components/choreops/`
     - `python -m pytest tests/test_options_flow_per_kid_helper.py -v`
     - `python -m pytest tests/test_options_flow_daily_multi.py -v`
       - Completed:
          - Validation executed via project gates; full runTests suite passed after Phase 3 additions.
- **Key issues**
  - Existing tests are stronger on prefill than on post-submit persistence semantics.
   - Integration-level explicit clear assertions were refined into deterministic transform-contract assertions where section transport behavior introduced flakiness.

### Phase 4 – Service compatibility validation ✅

- **Goal**: Verify no behavior change for chore CRUD service contracts and shared manager/builder usage.
- **Steps / detailed work items**
   1. - [x] Document explicit separation between options-flow transform and service DATA_* mapping path.
     - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L360-L613), [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L860-L950)
   2. - [x] Confirm no change to service-to-DATA mapping and no schema mutation.
     - File: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L545-L571)
   3. - [x] Confirm ChoreManager update behavior remains unchanged.
     - File: [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py#L2912-L2995)
   4. - [x] Add/execute service regression checks (targeted existing service tests).
     - Candidate files: `tests/test_services_*.py` covering create/update chore and due-date updates.
       - Completed:
          - Executed focused suite:
             - `tests/test_chore_crud_services.py`
             - `tests/test_chore_services.py`
             - `tests/test_due_date_services_enhanced_frequencies.py`
             - `tests/test_multi_instance_services.py`
          - Result: `57 passed`.
   5. - [x] Verify no schema migration impact.
     - No `SCHEMA_VERSION` change expected; preserve storage shape.
       - Completed:
          - No schema/data migration files changed and no storage schema constants modified.
- **Key issues**
  - Shared builders are used by services and options flow via different upstream shapes; refactor must not alter service input contract.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed:
   - `pylint --rcfile=pyproject.toml custom_components/choreops` → `9.94/10`.
   - `./utils/quick_lint.sh --fix` → Passed (`ruff` clean, `mypy` clean, boundary checks clean).
   - `runTests` full suite → `1446 passed, 0 failed`.
   - Focused service compatibility suite → `57 passed`.
- Additional validation notes:
   - Direct standalone `mypy`/`pylint` invocation in this shell diverges from project gate environment; authoritative lint/type status is taken from `quick_lint` output for this phase.
- Outstanding tests (for implementation phases):
   - `python -m pytest tests/test_options_flow_per_kid_helper.py -v`
   - `python -m pytest tests/test_options_flow_daily_multi.py -v`
   - Targeted chore service tests in `tests/test_services*.py`

## Notes & follow-up

- This initiative intentionally does not alter service schemas, manager public APIs, or storage schema.
- If preserve-vs-clear semantics reveal ambiguity for any field, create a short supporting addendum in `docs/in-process/` before coding.
- Post-implementation, update architecture/development docs only if a formal contract statement is added for sectioned edit semantics.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
