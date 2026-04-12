# Phase 3B support plan - Sparse edit preservation remediation

## Initiative snapshot

- **Name / Code**: Sparse edit preservation remediation / `CHORE_DYNAMIC_ENTITY_LIFECYCLE_PHASE_3B`
- **Target release / milestone**: Same release train as issue 107; must complete before final rollout signoff
- **Owner / driver(s)**: TBD
- **Status**: Complete

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Step 1 – Confirm defect breadth | Expand ESV06 into a minimal but explicit sparse-edit regression set | 100% | Representative sparse-edit regressions were added and reproduced the defect class |
| Step 2 – Audit edit boundary | Trace where omitted optional fields become defaulted values | 100% | Direct transform/build paths preserved values; edit schema boundary was the defect surface |
| Step 3 – Remediate root cause | Fix preserve-on-omit semantics in one shared place | 100% | Added edit-mode schema behavior that stops backend default injection for optional preserve-on-omit fields |
| Step 4 – Re-validate rollout | Re-run sparse-edit and runtime-sync coverage together | 100% | Repo gate passed and the combined targeted suite passed with 100 tests |

1. **Key objective** – Close the options-flow sparse-edit defect surface before any more rollout work proceeds, using tests first and a root-cause fix rather than field-specific patches.
2. **Summary of recent work**
   - Confirmed `test_esv06_edit_partial_section_payload_preserves_schedule_fields` in `tests/test_options_flow_per_kid_helper.py` fails in isolation.
   - Confirmed the returned bad value is `0d 1h 0m`, which is the schema default for `chore_due_window_offset`, not the stored value `3h`.
   - Confirmed direct calls to `flow_helpers.transform_chore_cfof_to_data()` and `data_builders.build_chore()` preserve the same omitted fields correctly, narrowing suspicion to the options-flow edit boundary.
   - Confirmed `build_chore_schema()` assigns defaults for multiple optional schedule and advanced fields, creating a plausible preserve-on-omit risk when edit payloads are sparse.
3. **Next steps (short term)**
   - Phase complete. Await owner approval before resuming Phase 4 rollout work.
4. **Risks / blockers**
   - The defect may affect more than due-window fields, because multiple optional fields in the chore edit schema use defaults.
   - Notifications are especially risky because omission must preserve prior booleans while explicit submission must still deterministically rewrite them.
   - Any fix that alters form defaults globally could break add-flow ergonomics if create and edit semantics are not separated carefully.
5. **References**
   - [docs/completed/CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md](./CHORE_DYNAMIC_ENTITY_LIFECYCLE_COMPLETED.md)
   - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
   - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
   - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
   - [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/QUALITY_REFERENCE.md](../QUALITY_REFERENCE.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Treat ESV06 as a blocker for rollout, not as an optional cleanup item.
     - Use a test-first sequence before any code remediation.
     - Fix preserve-on-omit semantics at one shared edit-boundary layer rather than through per-field special cases.
     - Do not introduce wrappers, fallback shims, or hidden compatibility branches to hide sparse-edit defects.
   - **Completion confirmation**: `[x]` All sparse-edit reproduction tests, remediation, and re-validation completed before Phase 4 can resume.

## Detailed analysis

### Confirmed observations

- `tests/test_options_flow_per_kid_helper.py` around lines 1374-1449 creates a chore with non-default values for:
  - `chore_due_window_offset = 3h`
  - `chore_due_reminder_offset = 20m`
  - `notify_on_claim = True`
  - `notify_on_due_window = True`
- The same test reopens the edit form and submits only a partial section payload, intentionally omitting some schedule and advanced fields.
- The final assertion fails because stored `chore_due_window_offset` becomes `0d 1h 0m`, which matches `DEFAULT_DUE_WINDOW_OFFSET` instead of the stored `3h`.
- Running the test alone still fails, so the defect is not caused by prior test contamination.

### Narrowed defect surface

- `flow_helpers.transform_chore_cfof_to_data()` preserves omitted values correctly when `existing_chore` is passed.
- `data_builders.build_chore()` also preserves omitted values correctly in update mode when the transformed payload omits the field.
- That leaves the edit boundary as the most likely defect surface:
  - `build_chore_schema()` in `helpers/flow_helpers.py` defines defaults for optional edit fields.
  - `async_step_edit_chore()` in `options_flow.py` accepts sectioned user input and routes it into shared validation and transform logic.
  - If Home Assistant submits schema-defaulted optional values back in sparse edit submissions, omission semantics are lost before preservation logic runs.

### Risk map by field family

Potentially affected fields are those that are optional on edit and also have schema defaults or synthesized defaults:

- **Schedule section**
  - `chore_due_window_offset`
  - `due_date`
  - `applicable_days`
  - `custom_interval`
  - `custom_interval_unit`
- **Advanced configuration section**
  - `chore_due_reminder_offset`
  - consolidated `notifications`
  - any booleans or selectors whose omission should preserve existing values during edit
- **Lower risk / likely safe**
  - fields already marked `Required` where edit semantics expect full re-submission
  - fields with explicit clear controls that distinguish omission from deliberate clearing

### Planned coverage model

The Phase 3B test plan should be representative, not exhaustively one-test-per-field.

Coverage should deliberately sample distinct behavior patterns:

- **Optional text field with non-default stored value**
   - Example: `chore_due_window_offset`
   - Why: this is the confirmed ESV06 failure shape and the clearest schema-default injection signal.
- **Optional text field in a different section**
   - Example: `chore_due_reminder_offset`
   - Why: proves the defect is not limited to one section container.
- **Optional synthesized multi-select / fan-out field**
   - Example: consolidated `notifications`
   - Why: omission must preserve multiple stored booleans, while explicit submission must still rewrite them deterministically.
- **Optional list/collection field or selector-backed field**
   - Example candidate: `applicable_days`
   - Why: protects against collection replacement/defaulting regressions that differ from simple text offsets.
- **Explicit overwrite control**
   - Use one representative field with a changed submitted value.
   - Why: proves the fix preserves omitted values without breaking intentional updates.
- **Explicit clear control**
   - Use an existing field with a supported clear semantic, such as due date clearing.
   - Why: proves omission and deliberate clearing remain distinct after remediation.

This coverage model is the bar for Phase 3B. The goal is not to add a nearly identical test for every optional chore field. The goal is to prove the defect class is closed across the main input patterns that matter.

### Why this matters to issue 107

This defect is not part of the runtime entity-sync contract itself, but it was exposed during validation of that workstream and it affects the same chore options-flow edit surface. If omitted optional fields are silently reset during edit, users can lose stored schedule or notification behavior even though runtime sync itself works correctly. That is a release-quality defect and should block rollout signoff.

## Implementation approach

### Step 1 - Add tests before code changes

Add targeted regression coverage first. Do not start remediation until these tests exist and fail for the right reason.

1. In `tests/test_options_flow_per_kid_helper.py` near the ESV06 block:
   - Add one test that omits only schedule optional fields while keeping advanced fields explicit.
   - Add one test that omits only advanced optional fields while keeping schedule fields explicit.
   - Add one test that omits the consolidated notifications selector and verifies stored notification booleans are preserved.
   - Add one explicit-overwrite control test proving a user-provided new due-window value replaces the stored value.
   - Prefer extending a small number of high-signal scenarios over adding many nearly identical field-by-field tests.
2. In `tests/test_options_flow_entity_crud.py`:
   - Add a broader options-flow edit test that starts with stored non-default optional values, edits a chore with a sparse payload, and verifies the stored values remain intact.
   - Add at least one system-settings or non-chore control assertion proving this remediation stays chore-edit scoped.
   - Use this file for pattern-level coverage, not exhaustive duplication of helper-file assertions.
3. In `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` only after the fix is proven:
   - Add guidance that sparse edit tests must distinguish omission from explicit clear/update behavior.

### Step 2 - Audit the edit boundary

Inspect and document the exact behavior of these call sites:

1. `helpers/flow_helpers.py` around lines 919-1037:
   - Identify each optional field that receives a backend default during schema creation.
   - Classify whether that default is safe for create only, safe for edit, or unsafe for preserve-on-omit edit semantics.
2. `options_flow.py` around lines 1385-1394:
   - Verify what payload shape `async_step_edit_chore()` receives from Home Assistant after sparse section submission.
   - Determine whether omitted optional keys are absent or already materialized with default values.
3. `helpers/flow_helpers.py` around lines 1084-1565:
   - Confirm validation and transform logic should remain preservation-aware and not be polluted with UI display defaults.

### Step 3 - Fix at one shared layer

Preferred remediation order:

1. **Best option**: Separate create-form defaults from edit-form preserve semantics.
   - Keep defaults for create UX.
   - Avoid backend schema defaults for edit fields where omission must preserve stored values.
2. **Second option**: Normalize sparse edit payloads immediately before validation.
   - Strip schema-injected default values for fields that were not explicitly changed.
   - This must be centralized and deterministic, not handwritten per field in multiple callers.
3. **Avoid**:
   - per-field patch branches in transform logic
   - special-case wrappers in `update_chore()`
   - test-only accommodations that hide production behavior

### Step 4 - Prove the fix

Required validation sequence after remediation:

1. `./utils/quick_lint.sh --fix`
2. `python -m pytest tests/test_options_flow_per_kid_helper.py -v --tb=line`
3. `python -m pytest tests/test_options_flow_entity_crud.py -v --tb=line`
4. Re-run the previously green runtime-sync regression set:
   - `python -m pytest tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py::TestPerAssigneeHelperAdd::test_pkh02_helper_completion_does_not_mark_deferred_reload tests/test_options_flow_daily_multi.py::TestDailyMultiOptionsFlow::test_of_03_helper_completion_does_not_mark_deferred_reload -v --tb=line`

Phase 4 may only resume once the new sparse-edit tests pass and the earlier runtime-sync validation remains green.

## Completion notes

- The final remediation did not change `data_builders.build_chore()` or the service-layer builder contract.
- The final remediation did not change create-flow schema behavior in config flow or options-flow add forms.
- The fix was intentionally scoped to chore edit-form schema generation by enabling preserve-on-omit behavior only on the edit call sites in `options_flow.py`.
- Validation completed successfully:
   - `./utils/quick_lint.sh --fix` passed on 2026-04-12.
   - `python -m pytest tests/test_chore_runtime_entity_sync.py tests/test_chore_crud_services.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py tests/test_options_flow_daily_multi.py -v --tb=line` passed on 2026-04-12 (`100 passed`).

## Acceptance criteria

1. ESV06 passes without weakening its preserve-on-omit contract.
2. Additional sparse-edit tests prove the breadth of the defect is understood and closed across representative field patterns.
3. Explicit user edits still overwrite stored values.
4. Explicit clear semantics remain distinct from omission semantics.
5. No field-specific wrappers or compatibility shims are introduced.
6. Existing chore runtime-sync behavior remains green after the sparse-edit fix.

## Notes & follow-up

- This Phase 3B plan is intentionally test-first because the current evidence suggests a systemic edit-boundary defect rather than a one-off field bug.
- The test strategy is intentionally pattern-based. The objective is to cover the main classes of optional edit behavior with a compact, high-signal suite rather than an exhaustive per-field matrix.
- If the audit proves Home Assistant always materializes defaults for omitted optional fields in sectioned edit forms, ChoreOps should document a stable mitigation pattern for other domains too, but only after the chore fix is complete.
