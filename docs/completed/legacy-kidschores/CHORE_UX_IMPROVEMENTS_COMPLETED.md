# Initiative Plan: Chore UX Improvements

## Initiative snapshot

- **Name / Code**: CHORE_UX_IMPROVEMENTS
- **Target release / milestone**: v0.5.0-beta4 follow-up
- **Owner / driver(s)**: KidsChores core team
- **Status**: Completed (owner sign-off recorded)

## Summary & immediate steps

| Phase / Step                            | Description                                                     | % complete | Quick notes                                                    |
| --------------------------------------- | --------------------------------------------------------------- | ---------- | -------------------------------------------------------------- |
| Phase 1 – Baseline & scope lock         | Capture current behavior and freeze UX scope                    | 100%       | Baseline, scope split, and no-change list documented           |
| Phase 2 – Form architecture             | Reorder/group chore fields without behavior change              | 100%       | Canonical ordering + native section UI implemented             |
| Phase 3 – Consolidation & compatibility | Simplify schedule inputs with explicit compatibility guardrails | 20%        | Step 1 complete, Step 2 deferred by owner; remaining items parked |
| Phase 4 – Validation & release prep     | Test matrix, docs parity, and rollout checklist                 | 100%       | Targeted + full gates passed; parity evidence recorded         |

1. **Key objective** – Make chore add/edit forms easier to use (clear grouping, reduced cognitive load, fewer confusing scheduling inputs) while keeping runtime chore behavior stable.
2. **Summary of recent work** – Phase 1 and Phase 2 completed; in Phase 3, Step 1 (claim-lock placement/default rule) is complete and Step 2 is deferred by owner.
3. **Next steps (short term)** – Initiative closed. Reopen parked Phase 3 consolidation items only by explicit owner direction.
4. **Risks / blockers** – `flow_helpers.py` schema drives both config and options paths; changes can unintentionally break DAILY_MULTI helper routing and per-kid helper flows.
5. **References** –

- [docs/PLAN_TEMPLATE.md](../PLAN_TEMPLATE.md)
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
- [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
- [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
- [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
- [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
- [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py)
- [custom_components/kidschores/config_flow.py](../../custom_components/kidschores/config_flow.py)
- [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
- [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py)
- [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
- [custom_components/kidschores/services.yaml](../../custom_components/kidschores/services.yaml)

6. **Decisions & completion check**

- **Decisions captured**:
  - This initiative is UX/form architecture only; no chore-state-engine behavior changes are included by default.
  - `build_chore_schema()` remains the single schema source for both config/options flows.
  - Claim-lock field stays in scope and remains positioned before auto-approve.
  - Any consolidation of custom schedule inputs requires backward compatibility for existing stored chore records.
  - **Critical constraint**: Existing flow validation/transformation/data-builder logic and patterns are treated as stable and must remain unchanged unless a change is strictly required to support field reordering and section presentation.
  - **Critical constraint**: No refactor/rewrite of `validate_chores_inputs()`, `transform_chore_cfof_to_data()`, or `data_builders` behavior in this initiative.
  - Phase 3 sequencing decision (2026-02-13): Step 1 completed, Step 2 deferred by owner, and Phase 4 is prioritized. Remaining Phase 3 items are parked until explicitly reactivated.
- **Completion confirmation**: `[x]` All phase checklists complete, validation gates passed, and owner sign-off recorded.

> **Important:** Keep Summary current after each builder phase completion.

## Tracking expectations

- **Summary upkeep**: Update phase percentages, blockers, and decisions after each completed phase.
- **Detailed tracking**: Keep implementation details and unresolved questions in phase sections below.

## Proposed UX section blueprint (for alignment/sign-off)

### Non-functional guardrail (critical)

- This initiative is a **layout-only UX pass**. Scope is limited to:
  - Moving existing fields to approved positions
  - Introducing/using sections (or linear section headings fallback)
- Out of scope unless explicitly approved in a follow-up plan:
  - Changing validation semantics
  - Changing transform semantics
  - Changing stored payload shape
  - Changing manager/data-builder behavior
- Implementation rule: preserve all existing defaults, conditional logic, and routing behavior; only touch logic where absolutely required to carry section structure in/out of the form layer.

### Grouping model decision

- **Primary model**: Three-zone layout with one root block and two sections:
  - **Root Form**: identity + assignment + core contract settings
  - **Schedule**: timing, access window, and dynamic custom interval controls
  - **Advanced Configurations**: lifecycle automation, alerts, visibility, metadata
- **Execution note**: If native section components (`data_entry_flow.section`) are not adopted in this phase, preserve this exact order in a linear schema and use translation headings.

### Exact field placement and order (all existing chore fields)

| Order | Section                | Field key                                  | Rationale for placement          |
| ----- | ---------------------- | ------------------------------------------ | -------------------------------- |
| 1     | Root Form              | `name`                                     | Identity: The contract title     |
| 2     | Root Form              | `chore_description`                        | Identity: Context/instructions   |
| 3     | Root Form              | `icon`                                     | Identity: Visual                 |
| 4     | Root Form              | `default_points`                           | Value: moved up (contract value) |
| 5     | Root Form              | `assigned_kids`                            | Assignment: who does it          |
| 6     | Root Form              | `completion_criteria`                      | Mechanics: solo vs. shared       |
| 7     | Schedule               | `recurring_frequency`                      | Timing: daily/weekly             |
| 8     | Schedule               | `due_date`                                 | Timing: deadline                 |
| 9     | Schedule               | `clear_due_date`                           | Timing: remove deadline          |
| 10    | Schedule               | `applicable_days`                          | Timing: restriction (M/W/F)      |
| 11    | Schedule               | `chore_due_window_offset`                  | Access: start time (window)      |
| 12    | Schedule               | `chore_claim_lock_until_window`            | Access: enforce start (lock)     |
| 13    | Schedule               | `custom_interval` / `custom_interval_unit` | Hidden/dynamic                   |
| 14    | Advanced Configuration | `approval_reset_type`                      | Cycle: when it resets            |
| 15    | Advanced Configuration | `approval_reset_pending_claim_action`      | Cycle: cleanup logic             |
| 16    | Advanced Configuration | `auto_approve`                             | Automation: happy path           |
| 17    | Advanced Configuration | `overdue_handling_type`                    | Automation: unhappy path         |
| 18    | Advanced Configuration | `chore_due_reminder_offset`                | Alerts: when to notify           |
| 19    | Advanced Configuration | `chore_notifications`                      | Alerts: what to notify           |
| 20    | Advanced Configuration | `show_on_calendar`                         | Visibility: dashboard            |
| 21    | Advanced Configuration | `chore_labels`                             | Meta: moved to bottom            |

### Related flow helper fields (not in main chore form)

- `daily_multi_times` is intentionally handled in dedicated helper steps (DAILY_MULTI flow) and **must not** be inserted into the main add/edit chore form in this initiative.
- Per-kid helper fields (`applicable_days_<kid>`, `date_<kid>`, apply-to-all flags) remain in the per-kid details step and are out of scope for this main form layout pass.

### Alignment checkpoints

- **Checkpoint A (required before build)**: ✅ Approved by owner (2026-02-13) — field-order matrix locked as implementation source of truth.
- **Checkpoint B (required before Phase 3)**: Owner confirms whether Root/Schedule/Advanced is implemented via native sections now or linear headings now + native sections later.

## Handoff readiness

- **Plan readiness**: ✅ Ready for builder execution
- **Builder start phase**: Phase 1 – Baseline & scope lock
- **Execution constraint**: Implement strictly to approved 21-field matrix and section model in this document
- **Gated decision pending**: Checkpoint B (section implementation mode) required before entering Phase 3
- **Reporting requirement**: Builder must update this plan with phase % complete and validation outcomes before requesting next-phase approval

## Detailed phase tracking

### Phase 1 – Baseline & scope lock

- **Goal**: Build exact baseline of current choreography form behavior and lock the UX scope before edits.
- **Steps / detailed work items**
  1. - [x] Baseline schema inventory from `build_chore_schema()` (current ordering, defaults, optional vs required).
  - File: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L507-L780)
  2. - [x] Baseline data transformation/validation contracts (`validate_chores_inputs`, `transform_chore_cfof_to_data`).
  - File: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L781-L1040)
  3. - [x] Confirm Config Flow touchpoints and restricted frequency behavior.
  - File: [custom_components/kidschores/config_flow.py](../../custom_components/kidschores/config_flow.py#L723-L839)
  4. - [x] Confirm Options Flow add/edit routing dependencies (INDEPENDENT, DAILY_MULTI, per-kid helper).
  - File: [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py#L797-L1140)
  5. - [x] Produce explicit scope list: reorder-only fields vs candidate consolidation fields.
  - Planned output section: this document (Phase 2 + Phase 3 step notes)
  6. - [x] Record a function-level no-change list for builder execution.
  - Must preserve behavior in: `validate_chores_inputs`, `transform_chore_cfof_to_data`, `data_builders.build_chore`, and options-flow routing helpers
- **Key issues**
  - DAILY_MULTI and per-kid helper behaviors are sensitive to field presence and post-submit routing logic.
  - Scope creep risk: avoid mixing this with chore engine/FSM changes.

#### Phase 1 completion notes (baseline + constraints)

- **Current schema field construction baseline** (`build_chore_schema`):
  - Initial dict build includes identity, labels, points, assignment, completion, workflow tuning, claim/approve toggles, recurrence, custom interval fields, applicable days, due date
  - Conditional add: `clear_due_date` only when existing due date is present
  - Post-dict append sequence: `chore_due_window_offset` → `chore_due_reminder_offset` → `chore_notifications` → `show_on_calendar`
- **Validation contract baseline** (`validate_chores_inputs`):
  - Resolves assigned kid names to IDs
  - Handles clear-due-date semantics and due-date parsing
  - Delegates core rule validation to `data_builders.validate_chore_data` (single source)
- **Transform contract baseline** (`transform_chore_cfof_to_data`):
  - Converts names→IDs, builds `per_kid_due_dates`, controls custom interval fields by frequency
  - Maps notification selections and preserves existing payload conventions
- **Config Flow baseline**:
  - Uses `build_chore_schema` + `validate_chores_inputs` + `transform_chore_cfof_to_data` + `data_builders.build_chore`
  - Enforces restricted frequency options via `CHORE_FREQUENCY_OPTIONS_CONFIG_FLOW` (excludes DAILY_MULTI)
- **Options Flow routing baseline**:
  - `INDEPENDENT + assigned_kids` routes to per-kid helper (with single-kid fast path)
  - `DAILY_MULTI` routes to `async_step_chores_daily_multi` where required
  - Edit flow mirrors add flow routing and preserves per-kid details behavior
- **Scope split (locked)**:
  - **Reorder-only in Phase 2**: field ordering/grouping/section presentation and related translation heading text
  - **Candidate consolidation in Phase 3**: only if compatibility matrix proves no behavior/payload drift
- **Function-level no-change list (locked)**:
  - `helpers.flow_helpers.validate_chores_inputs`
  - `helpers.flow_helpers.transform_chore_cfof_to_data`
  - `data_builders.build_chore`
  - Options-flow routing logic for INDEPENDENT/per-kid and DAILY_MULTI helper transitions

### Phase 2 – Form architecture

- **Goal**: Define and implement a simpler form information architecture without changing business behavior.
- **Steps / detailed work items**
  1. - [x] Freeze the "Proposed UX section blueprint" table as implementation source of truth.
  - Output: approved matrix in this plan file
  2. - [x] Create canonical section model for chore forms using approved Root/Schedule/Advanced grouping.
  - Target: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L507)
  3. - [x] Reorder schema fields to match canonical sequence in one place (`build_chore_schema`) and propagate to both flows.
  - Targets: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L507-L780), [custom_components/kidschores/config_flow.py](../../custom_components/kidschores/config_flow.py#L751-L839), [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py#L797-L1140)
  4. - [x] Preserve existing defaults and conditional appearance rules (e.g., clear due date checkbox, custom-only interval fields).
  - Target: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L540-L735)
  5. - [x] Enforce non-functional rule: no behavior edits in validation/transform/data-builder logic while applying section/order changes.
  - Validation targets: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L781-L1040), [custom_components/kidschores/data_builders.py](../../custom_components/kidschores/data_builders.py)
  6. - [x] Validate translation labels/help text order and terminology parity for config + options flow forms.
  - Target: [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json) (`config.step.chores`, `options.step.add_chore`, `options.step.edit_chore`)
  7. - [x] Decide and document whether to introduce `data_entry_flow.section` now or defer to a follow-up initiative.
  - Decision log: this document, Notes & follow-up
- **Key issues**
  - Introducing native sections may require nested payload handling; defer if it increases implementation risk beyond UX ordering goals.

#### Phase 2 completion notes (form architecture)

- `build_chore_schema()` reordered to approved 21-field sequence with Root/Schedule/Advanced grouping intent preserved in linear schema order.
- `clear_due_date` conditional placement preserved directly after `due_date` when applicable.
- Existing defaults, selectors, and conditional field visibility behavior preserved (no validation/transform/data-builder semantic changes).
- Translation parity validated for config/options chore field naming and terminology alignment.
- Decision: implement native `data_entry_flow.section` now with `Root Form` expanded and `Schedule` + `Advanced Configurations` collapsed.
- Compatibility handling added at flow layer to normalize sectioned payloads so existing validation/transform/data-builder logic remains behaviorally unchanged.
- Section translation mappings are now scoped under `sections.*.data` and `sections.*.data_description` for `config.step.chores`, `options.step.add_chore`, and `options.step.edit_chore` to match native section rendering.
- Section title wording refined from `Root Form` to `Definition` for professional UI terminology, while preserving approved existing field labels and descriptions.

### Phase 3 – Consolidation & compatibility

- **Goal**: Reduce scheduling-field friction while retaining data compatibility and migration safety.
- **Steps / detailed work items**
  1. - [x] Finalize rule for claim lock field (`CFOF_CHORES_INPUT_CLAIM_LOCK_UNTIL_WINDOW`) placement + defaults.
  - Constants: [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py#L643), [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py#L1444-L1445), [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py#L1745)
  2. - [ ] Define consolidation approach for custom frequency inputs (`custom_interval`, `custom_interval_unit`) and non-custom behavior. **Deferred by owner (2026-02-13).**
  - Targets: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L661-L706), [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py#L968-L990)
  3. - [ ] Draft compatibility matrix for old/new payloads (UI payload, transformed DATA payload, stored chore record, services payload).
  - Related docs/files: [custom_components/kidschores/services.yaml](../../custom_components/kidschores/services.yaml), [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
  4. - [ ] Determine schema-version impact: if storage shape changes, plan schema bump + migration method in store/coordinator path.
  - Architecture refs: [docs/ARCHITECTURE.md](../ARCHITECTURE.md), storage source: [custom_components/kidschores/store.py](../../custom_components/kidschores/store.py)
  5. - [ ] Lock “no engine behavior drift” guardrail and list explicit out-of-scope behavior changes.
  - Guardrail refs: [custom_components/kidschores/engines/chore_engine.py](../../custom_components/kidschores/engines/chore_engine.py)
- **Key issues**
  - If storage contract changes, schema migration planning becomes mandatory before builder implementation.

#### Phase 3 status note (owner decision)

- Step 1 completed.
- Step 2 deferred by owner.
- Steps 3–5 are currently parked because consolidation work is deferred.
- No additional Phase 3 implementation is planned unless owner explicitly reopens this phase.

### Phase 4 – Validation & release prep

- **Goal**: Provide a complete verification and release-readiness checklist for builder execution.
- **Steps / detailed work items**
  1. - [x] Add/update tests for schema and flow UX paths (add/edit chore, config + options).
  - Primary test files: [tests/test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py), [tests/test_options_flow_daily_multi.py](../../tests/test_options_flow_daily_multi.py), [tests/test_options_flow_per_kid_helper.py](../../tests/test_options_flow_per_kid_helper.py), [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py), [tests/test_config_flow_direct_to_storage.py](../../tests/test_config_flow_direct_to_storage.py)
  2. - [x] Update flow test helper mappings if schema inputs change.
  - File: [tests/helpers/flow_test_helpers.py](../../tests/helpers/flow_test_helpers.py#L173-L211)
  3. - [x] Validate translation and service metadata parity for every user-facing chore field.
  - Files: [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json), [custom_components/kidschores/services.yaml](../../custom_components/kidschores/services.yaml)
  4. - [x] Run required quality gates and capture results in phase report.
  - Commands: `./utils/quick_lint.sh --fix`, `mypy custom_components/kidschores/`, `python -m pytest tests/ -v --tb=line`
  5. - [x] Add behavior-parity verification note in phase report confirming no intentional logic changes to validation/transform/data-builder paths.
  - Evidence: targeted diff review for [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py), [custom_components/kidschores/data_builders.py](../../custom_components/kidschores/data_builders.py), and [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
  6. - [x] Update this plan summary percentages and completion checklist before requesting phase sign-off.
  - File: [docs/in-process/CHORE_UX_IMPROVEMENTS_IN-PROCESS.md](CHORE_UX_IMPROVEMENTS_IN-PROCESS.md)
- **Key issues**
  - Test coverage must include DAILY_MULTI and per-kid helper paths to avoid regressions from schema reorder/consolidation.

#### Phase 4 completion notes (validation + parity)

- Targeted UX regression matrix passed:
  - `python -m pytest tests/test_config_flow_direct_to_storage.py tests/test_config_flow_fresh_start.py tests/test_config_flow_use_existing.py tests/test_config_flow_error_scenarios.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py tests/test_options_flow_shadow_kid_entity_creation.py tests/test_options_flow_daily_multi.py -v --tb=line` → `77 passed`
- Quality gates passed:
  - `./utils/quick_lint.sh --fix` ✅
  - `mypy custom_components/kidschores/` ✅ (`Success: no issues found in 48 source files`)
  - `python -m pytest tests/ -v --tb=line` → `1307 passed, 2 skipped, 2 deselected`
- Flow helper mapping check:
  - No update required in `tests/helpers/flow_test_helpers.py`; flat payload helpers remain compatible because chore form input is normalized for both flat and sectioned payloads.
- Behavior parity verification:
  - No intentional logic changes were introduced to `validate_chores_inputs()`, `transform_chore_cfof_to_data()`, or `data_builders` semantics in this phase.

## Testing & validation

- **Tests executed**:
  - `./utils/quick_lint.sh --fix` ✅ Passed (ruff + mypy + boundary checks)
  - `mypy custom_components/kidschores/` ✅ Passed (0 errors)
  - `python -m pytest tests/test_config_flow_direct_to_storage.py tests/test_config_flow_fresh_start.py tests/test_config_flow_use_existing.py tests/test_config_flow_error_scenarios.py tests/test_options_flow_entity_crud.py tests/test_options_flow_per_kid_helper.py tests/test_options_flow_shadow_kid_entity_creation.py tests/test_options_flow_daily_multi.py -v --tb=line` ✅ Passed (77 passed)
  - `python -m pytest tests/ -v --tb=line` ✅ Passed (1307 passed, 2 skipped, 2 deselected)
- **Builder validation commands (required before phase closure)**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/ -v --tb=line`
- **Targeted test focus (minimum)**:
  - Config flow chore input + validation path
  - Options flow add/edit chore path
  - DAILY_MULTI helper route + validation
  - Per-kid helper route + apply-to-all behavior
  - Translation/service metadata parity for chore fields

## Notes & follow-up

- Confirmed lock-claim naming and storage path are already present and should be treated as stable API surface in this initiative.
- No schema migration is planned yet; migration work is conditionally required only if Phase 3 changes storage structure.
- Builder execution protocol:
  - Execute one phase at a time.
  - Provide phase completion report with validation outputs.
  - Update this plan before requesting approval to proceed to next phase.
