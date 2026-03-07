# Initiative plan: Dashboard UI control state + per-user UI preference contract

## Initiative snapshot

- **Name / Code**: Dashboard UI control state + per-user UI preference contract (`DASHBOARD_UI_CONTROL_STATE`)
- **Target release / milestone**: Post-v0.5.0-beta.5 UX architecture track
- **Owner / driver(s)**: ChoreOps maintainers + dashboard UX contributors
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                                         | Description                                                                                                                | % complete | Quick notes                                                                                                                         |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------: | ----------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Contract + storage model                   | Lock naming, persistence scope, manager ownership, path delimiter, and schema impact for per-user UI control state         |        100 | Contract documented in architecture + constants; aligned to schema 45 durable storage contract                                      |
| Phase 2 – Backend plumbing                           | Add user-profile storage normalization, durable user-write ownership, translation contracts, and a single service contract |        100 | Single `manage_ui_control` service added; normalization, `UserManager` write ownership, and translation/docs contracts are in place |
| Phase 3 – Dashboard helper exposure + first consumer | Expose merged `ui_control` on the dashboard helper and wire the first Game Full consumer                                   |        100 | Helper now exposes resolved `ui_control`; first consumer is limited to Rewards header collapse in `user-game-full-v1`               |
| Phase 4 – Tests + documentation                      | Add contract, translations, service, storage, and dashboard-helper coverage plus docs                                      |          0 | Requires targeted service/helper tests plus schema, migration, and translation parity coverage                                      |

1. **Key objective** – Add a backend-owned `ui_control` channel to the assignee dashboard helper so Lovelace templates can respond to per-user UI state such as expand/collapse without relying on standalone Home Assistant helpers or row-only frontend wrappers, with `UserManager` owning durable `ui_preferences` writes and `UIManager` remaining helper-facing UI orchestration.
2. **Summary of recent work**
   - Planning research confirmed the dashboard helper already acts as the frontend pointer/aggregation surface in [docs/ARCHITECTURE.md] and in [custom_components/choreops/sensor.py].
   - Existing user-profile normalization patterns were reviewed in `data_builders.py` and `user_manager.py` to keep any new storage keys aligned with current `DATA_USER_*` conventions.
   - Existing service-field and dashboard-helper attribute naming patterns were reviewed in `const.py`, `services.py`, and current dashboard-helper tests.
     - Translation and platinum-quality patterns were reviewed across `translations/en.json`, `services.yaml`, dashboard translation assets, and existing contract-parity tests.
       - Phase 1 contract updates landed in `docs/ARCHITECTURE.md` and `custom_components/choreops/const.py`, including the durable `ui_preferences` target shape, delimiter constant, translation ownership split, and schema 45 alignment.
       - Phase 2 backend plumbing landed in `data_builders.py`, `user_manager.py`, `ui_manager.py`, `store.py`, `services.py`, `services.yaml`, and `translations/en.json`, including strict CRUD semantics for `create`/`update`/`remove` and blank-key clear-all support for `remove`.
3. **Next steps (short term)** - Phase 3 is complete. Next work is Phase 4 targeted tests and final documentation follow-through only after owner approval.
       - The first dashboard consumer remains limited to `gamification/rewards/header_collapse`.
       - Validation through the end of Phase 3 remained lint-only per approved execution deviation.
4. **Risks / blockers** - Persisted per-user UI overrides are part of the schema 45 contract and still require correct legacy normalization and migration coverage.
   - If `ui_control` is allowed to become an unbounded bag of arbitrary frontend state, the dashboard helper can drift from its current focused aggregation role.
   - Service validation must prevent malformed key paths or invalid action payloads from being stored, or the user profile bucket will become inconsistent.
   - The helper should expose **resolved** control values; exposing raw stored structure would leak persistence details into template authoring.
     - Platinum-quality drift can occur if new service docs, exception keys, helper attributes, or dashboard-visible labels are added without matching translation entries and parity tests.
     - Builder execution must stop for approval before any scope expansion, new consumer rollout, contract rename, additional service introduction, or storage-shape deviation beyond what is locked below.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `docs/DASHBOARD_TEMPLATE_GUIDE.md`
   - `custom_components/choreops/const.py`
   - `custom_components/choreops/data_builders.py`
   - `custom_components/choreops/managers/ui_manager.py`
   - `custom_components/choreops/managers/user_manager.py`
   - `custom_components/choreops/sensor.py`
   - `custom_components/choreops/services.py`
     - `custom_components/choreops/services.yaml`
     - `custom_components/choreops/translations/en.json`
     - `choreops-dashboards/translations/en_dashboard.json`
   - `tests/test_dashboard_helper_size_reduction.py`
     - `tests/test_pending_claim_action_contract_parity.py`
   - `tests/test_storage_manager.py`
   - `.github/agents/builder.agent.md`
   - `.github/agents/strategist.agent.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Prefer backend-owned UI state over standalone `input_boolean` helpers for this initiative so UI behavior can remain per-user and integration-scoped.
   - Use the dashboard helper as the UI-facing aggregation layer, consistent with the existing `core_sensors`, `dashboard_helpers`, and translation-pointer patterns.
     - `UserManager` should own durable `ui_preferences` writes and path-resolution behavior; `UIManager` should remain the helper-facing orchestration layer.
     - Persist UI-control overrides with the user profile; dashboard templates/cards will always provide defaults when no key exists, minimizing storage churn.
     - Treat the experimental 2x rewards expander as the first proving-ground consumer before broadening the feature to other dashboard sections.
   - Prefer a single scoped service contract over multiple narrow services; reuse existing integration-target and user-target fields where possible.
     - Use forward slash (`/`) as the standard nested key-path delimiter because it is the safest and most familiar structured-path format for YAML strings, service payloads, and frontend-authored config, while avoiding backslash escaping ambiguity.
     - Do not support a `read` action in the public service; dashboards should use the dashboard helper as the read source. - New user-facing strings for services, exceptions, helper attributes, and dashboard-visible controls must be captured through the integration and dashboard translation contracts, not hardcoded ad hoc.
   - **Completion confirmation**: `[ ]` All follow-up items completed (contract, storage decision, service design, helper exposure, tests, docs, migration notes) before requesting owner approval to mark initiative done.

> **Important:** Keep the Summary section current whenever persistence scope, constant names, schema impact, or first-consumer scope changes.

## Tracking expectations

- **Summary upkeep**: Update phase percentages and quick notes after any contract decision, schema decision, or implementation handoff.
- **Detailed tracking**: Keep concrete file anchors, naming decisions, and validation scope in the phase sections below. Do not collapse those details into the Summary table.

## Builder handoff package

### Approved builder scope

- The Builder may implement only the locked contract in this document.
- The Builder must execute one approved phase at a time and must not begin the next phase without user approval, consistent with `.github/agents/builder.agent.md`.
- The first consumer remains limited to the experimental 2x rewards expander in `user-game-full-v1`.

### Explicitly out of scope unless re-approved

- Adding more than one public service for UI control.
- Adding a public `read` service action.
- Introducing `dashboard_id` targeting.
- Supporting delimiters other than `/`.
- Expanding to multiple dashboard consumers in the same phase without explicit approval.
- Storing raw frontend-only transient state that has no approved user-value or dashboard-helper use case.

### Builder permission guardrails

The Builder must pause and request permission before doing any of the following:

1. Renaming locked constants, service fields, helper attributes, or action values.
2. Changing the persisted storage shape beyond the approved `DATA_USER_UI_PREFERENCES*` family.
3. Adding or removing signals beyond the minimum needed for helper refresh behavior.
4. Broadening the first consumer beyond `gamification/rewards/header_collapse`.
5. Introducing new visible dashboard UX copy not already accounted for in translation files.
6. Deviating from the phase order, skipping validation gates, or merging steps across phases.
7. Replacing the approved `UserManager` durable-write ownership or moving the flow into direct coordinator-owned logic.

### Required deviation request format

If the Builder believes a deviation is necessary, the Builder must stop and provide all of the following before making the change:

- **Planned deviation**: exact change from this plan
- **Why the current plan is insufficient**: concrete implementation blocker
- **Files impacted**: exact files expected to change
- **Contract impact**: constants, services, storage, translations, dashboards, tests
- **Risk assessment**: migration, backward compatibility, dashboard breakage, helper size, translation drift
- **Validation impact**: which additional lint, mypy, and test suites will be required
- **Rollback path**: how to revert safely if rejected
- **Approval requested from user**: explicit yes/no gate before proceeding

### Builder plan-update rules

- After each completed step, the Builder must update this document by checking the step and refreshing the Summary table percentage for the active phase.
- After each completed phase, the Builder must add a short dated note under the phase verification subsection summarizing what was confirmed.
- If blocked, the Builder must mark the step as blocked in this document instead of silently re-scoping work.

## Detailed phase tracking

### Phase 1 – Contract + storage model

- **Goal**: Lock where UI control state lives, how it is named, how nested key paths are addressed, and how persisted per-user overrides coexist with dashboard-defined defaults.
- **Steps / detailed work items** 1. [x] Document in `docs/ARCHITECTURE.md` near the storage-only model section (lines 125-224) that per-user UI overrides are durable user-profile data, not runtime-only derived state.
  **Files**: `docs/ARCHITECTURE.md`, this plan file. 2. [x] Define the user-profile key contract adjacent to current user-key naming guidance in `custom_components/choreops/const.py` (lines 961-1215) and align the proposal with existing singular/plural storage conventions.
  **Files**: `custom_components/choreops/const.py`, this plan file. 3. [x] Align `SCHEMA_VERSION_BETA5` in `custom_components/choreops/const.py` (lines 326-343) with the `ui_preferences` durable storage contract and capture the matching legacy migration-path requirement in storage docs.
  **Files**: `custom_components/choreops/const.py`, `docs/ARCHITECTURE.md`. 4. [x] Ratify the UI-helper exposure contract against the current dashboard-helper pointer pattern in `docs/ARCHITECTURE.md` (lines 752-770) so `ui_control` remains a resolved helper attribute, not a raw storage dump.
  **Files**: `docs/ARCHITECTURE.md`, this plan file. 5. [x] Capture the approved naming contract in this plan before any Builder handoff so constants, service schemas, and dashboard template usage all start from the same vocabulary.
  **Files**: this plan file. 6. [x] Lock forward slash (`/`) as the nested key-path delimiter used by cards and services (for example `gamification/rewards/header_collapse`) so both service mutation and helper resolution use the same path rules.
  **Files**: this plan file, `custom_components/choreops/const.py`. 7. [x] Define the translation ownership split up front: integration-owned service/error/helper strings in `custom_components/choreops/translations/en.json` and dashboard-visible card text in `choreops-dashboards/translations/en_dashboard.json` when new dashboard copy is introduced.
  **Files**: `custom_components/choreops/translations/en.json`, `choreops-dashboards/translations/en_dashboard.json`, this plan file.
- **Key issues** - Persisted state improves UX, but it now requires explicit schema, migration, and validation coverage. - Dynamic nested paths reduce schema friction, but still need path-syntax guardrails so service calls remain predictable. - Forward slash should be treated as the only supported delimiter to avoid ambiguous parsing rules. - Translation ownership can drift if service strings, exception messages, and dashboard text are updated in only one of the integration or dashboard translation layers.

#### Phase 1 builder blueprint

- Document and lock the storage contract before touching implementation files.
- Treat this phase as the architectural gate for all later work: no service, helper, or dashboard implementation should start until the schema, naming, delimiter, and translation ownership decisions are reflected in docs.
- Recommended Builder deliverables for this phase: - contract constants list finalized in plan notes - schema 45 storage contract alignment recorded - migration expectation recorded - translation ownership split confirmed

#### Phase 1 verification hold points

The Builder must confirm all of the following before requesting Phase 2 approval:

- [x] `DATA_USER_UI_PREFERENCES*` naming is still the approved storage family.
- [x] `/` remains the only supported path delimiter.
- [x] `remove` with blank key is still the approved clear-all contract.
- [x] `UserManager` owns durable `ui_preferences` writes while `UIManager` remains the helper-facing orchestration layer.
- [x] Translation ownership split is documented between integration and dashboard repositories.
- [x] Schema 45 alignment and legacy normalization requirement are explicitly captured.

#### Phase 1 completion note

- 2026-03-07: Phase 1 completed. Contract, naming, delimiter, translation ownership, and schema 45 alignment were documented in architecture and constants. Validation was run with `./utils/quick_lint.sh --fix` only, per user-approved deviation to defer pytest until the end of Phase 3.

### Phase 2 – Backend plumbing

- **Goal**: Add the backend structures and the single service surface needed to own UI control state consistently under canonical user-record ownership.
- **Steps / detailed work items**
  1. [x] Extend user-profile builders in `custom_components/choreops/data_builders.py` around `build_user_profile()` (line 999) and the assignment-profile builder block (lines 804-845) so the new `DATA_USER_UI_PREFERENCES*` bucket is normalized alongside current user data.
         **Files**: `custom_components/choreops/data_builders.py`.
  2. [x] Update `custom_components/choreops/managers/user_manager.py` around `_normalize_user_record()` (lines 103-151) so new UI-preference fields survive create/update flows consistently with the existing merged user/assignment profile model.
         **Files**: `custom_components/choreops/managers/user_manager.py`.
  3. [x] Add UI-control handling under canonical user-record ownership so durable `ui_preferences` writes live in `custom_components/choreops/managers/user_manager.py`, while `UIManager` remains responsible for helper-facing orchestration and refresh behavior.
         **Files**: `custom_components/choreops/managers/user_manager.py`, `custom_components/choreops/managers/ui_manager.py`, `custom_components/choreops/managers/base_manager.py`.
  4. [x] Define a single service name, field constants, and schema placement in `custom_components/choreops/const.py` (service field guidance at lines 2704-2748) and register the handler in `custom_components/choreops/services.py` alongside current `_with_service_target_fields()` patterns (lines 116-403) and service registration blocks (lines 904-2929).
         **Files**: `custom_components/choreops/const.py`, `custom_components/choreops/services.py`.
  5. [x] Add the translation constants and user-facing error contract needed by the new service in `custom_components/choreops/const.py`, then wire matching exception/service entries in `custom_components/choreops/translations/en.json` and service documentation in `custom_components/choreops/services.yaml`.
         **Files**: `custom_components/choreops/const.py`, `custom_components/choreops/translations/en.json`, `custom_components/choreops/services.yaml`.
  6. [x] Decide whether UI-control updates should emit a dedicated signal suffix for helper refreshes or reuse broader user-update pathways; document that decision with the existing signal catalog in `custom_components/choreops/const.py` (lines 153-300).
         **Files**: `custom_components/choreops/const.py`, `custom_components/choreops/managers/ui_manager.py`.
  7. [x] Add migration/default-structure handling near the storage initialization contract in `custom_components/choreops/store.py` (lines 53-76) so legacy installs tolerate missing persisted UI-preference data.
         **Files**: `custom_components/choreops/store.py`, `custom_components/choreops/const.py`.
- **Key issues**
  - Service validation should constrain actions, user targeting, and key-path syntax rather than accepting arbitrary nested writes.
  - Manager ownership must be explicit so no non-manager file writes directly to `_data`.
  - Service docs and translation catalogs must stay in sync; this integration already uses parity tests for similar option/selector contracts, so UI control should follow the same discipline.

#### Phase 2 builder blueprint

- `UserManager` should own the mutation workflow end-to-end because `ui_preferences` lives on the canonical user record, with service handlers delegating to manager methods rather than writing directly to `_data`.
- Recommended Builder method blueprint in `user_manager.py`: - `async_manage_ui_control(...)` as the single orchestration entry point for the service handler - `_resolve_ui_control_target_user(...)` to normalize `user_id` / `user_name` - `_validate_ui_control_key_path(...)` to enforce delimiter and blank-key rules - `_set_ui_control_value(...)` for `create` / `update` - `_clear_ui_control_value(...)` for keyed `remove` - `_clear_all_ui_control_values(...)` for blank-key `remove` - helper refresh continues through the approved persistence/update flow
- Recommended service flow blueprint: 1. Service schema validates integration target + user target + action/value fields. 2. Service handler resolves the config entry and delegates to `UserManager`. 3. `UserManager` validates path and action semantics. 4. `UserManager` performs the write through approved manager-owned persistence flow. 5. Helper refresh continues through the approved persistence/update pathway used by manager-owned writes. 6. User-facing errors map to translation-backed exceptions.
- Update behavior blueprint: - `create`: strict create; raises a translated error when the path already exists. - `update`: replace existing value at a valid path and raise a translated error when the path is missing. - `remove` with non-empty key: remove targeted leaf and prune empty parents if needed. - `remove` with empty key: clear the entire `ui_preferences` bucket for the targeted user.

#### Phase 2 verification hold points

The Builder must confirm all of the following before requesting Phase 3 approval:

- [x] Only one public service contract was added.
- [x] Service handler delegates to a manager-owned user-record write path; no direct storage writes were added in `services.py`.
- [x] `create`, `update`, and `remove` are the only public actions.
- [x] Blank-key `remove` clears all user UI preferences and is explicitly covered by tests or planned tests.
- [x] Translation-backed service docs and exception contracts were added together.
- [x] Any signal addition or reuse decision is documented in the plan.

#### Phase 2 completion note

- 2026-03-07: Phase 2 completed. `DATA_USER_UI_PREFERENCES` is now normalized in builders, user normalization, and store-load handling. A single `manage_ui_control` service delegates to a manager-owned canonical user write path with strict `create`, `update`, and `remove` semantics plus blank-key clear-all behavior. Helper refreshes reuse `coordinator._persist_and_update()` and do not add a dedicated UI-control signal in this phase. Validation was run with `./utils/quick_lint.sh --fix` only, per user-approved deviation to defer pytest until the end of Phase 3.

#### Phase 2 approved correction note

- 2026-03-07: Owner approved a contract correction after Phase 2 review. Durable `ui_preferences` writes were moved from `UIManager` to `UserManager` so canonical user-record ownership and reset behavior stay aligned with the manager write-boundary rules and the economy landlord pattern.

### Phase 3 – Dashboard helper exposure + first consumer

- **Goal**: Expose resolved UI-control values on the helper and prove the contract with one dashboard consumer.
- **Steps / detailed work items**
  1. [x] Add the new helper attribute constant near existing dashboard-helper attrs in `custom_components/choreops/const.py` (lines 2418-2580), matching current concise frontend-facing attribute naming.
         **Files**: `custom_components/choreops/const.py`.
  2. [x] Build a helper-side `ui_control` resolver near the current helper composition methods in `custom_components/choreops/sensor.py` (dashboard helper class lines 4074-4415) so the sensor merges runtime defaults with any stored overrides before returning attributes.
         **Files**: `custom_components/choreops/sensor.py`, `custom_components/choreops/managers/ui_manager.py`.
  3. [x] Insert the resolved `ui_control` payload into dashboard-helper `extra_state_attributes` next to `core_sensors`, `dashboard_helpers`, and other frontend data in `custom_components/choreops/sensor.py` (lines 4985-5008).
         **Files**: `custom_components/choreops/sensor.py`.
  4. [x] Add the new helper attribute name and any helper-purpose/attribute translation metadata to `custom_components/choreops/translations/en.json` so the dashboard helper remains fully translated at the entity-attribute layer.
         **Files**: `custom_components/choreops/translations/en.json`, `custom_components/choreops/sensor.py`.
  5. [x] Document the template-consumption contract in `docs/DASHBOARD_TEMPLATE_GUIDE.md` near the dashboard-helper authoring guidance so templates know to read `state_attr(dashboard_helper, 'ui_control')` rather than the underlying user profile structure.
         **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, this plan file.
  6. [x] Scope the first consumer to the experimental 2x rewards expander in `choreops-dashboards/templates/user-game-full-v1.yaml`, using one reviewed control path only, before broader rollout to other templates.
         **Files**: `choreops-dashboards/templates/user-game-full-v1.yaml`, `choreops-dashboards/preferences/user-game-full-v1.md`.
  7. [x] If the first consumer introduces any new visible dashboard copy (for example a collapse label, expanded/collapsed state text, or helper hint), add it to `choreops-dashboards/translations/en_dashboard.json` instead of hardcoding it in the template.
         **Files**: `choreops-dashboards/translations/en_dashboard.json`, `choreops-dashboards/templates/user-game-full-v1.yaml`.
  8. [x] Add public-facing service/docs examples only after the first consumer is proven so the project does not publish an unstable control contract prematurely.
         **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `utils/README.md`.
- **Key issues** - The helper should expose only resolved controls relevant to templates; raw stored nesting should stay backend-side.
  - The first rollout should validate one boolean expander use case before introducing multi-value layout controls.
  - New dashboard-visible text must flow through dashboard translations, while backend service/error/helper strings must flow through integration translations; mixing these layers is a trap.

#### Phase 3 builder blueprint

- The dashboard helper should expose a resolved `ui_control` object that templates can read directly without understanding storage internals.
- Recommended resolver blueprint: - source 1: dashboard/card defaults defined by the consuming template contract - source 2: persisted per-user overrides from `ui_preferences` - merge rule: stored override wins only when the key exists; otherwise dashboard default remains authoritative
- Recommended first-consumer blueprint for `user-game-full-v1`: - one reviewed local path constant/variable: `gamification/rewards/header_collapse` - one boolean control use case only - no generic multi-layout state bundle in the first pass
- Clear/read behavior blueprint for templates: - templates always read `state_attr(dashboard_helper, 'ui_control')` - templates never inspect `users[*].ui_preferences` - cleared preferences fall back naturally to dashboard defaults with no extra cleanup logic in the template

#### Phase 3 verification hold points

The Builder must confirm all of the following before requesting Phase 4 approval:

- [x] `ui_control` is exposed as a resolved helper attribute, not a raw persistence dump.
- [x] The first consumer uses only `gamification/rewards/header_collapse`.
- [x] Clearing a stored preference causes fallback to dashboard defaults.
- [x] No additional dashboard consumers were added without approval.
- [x] Any new visible dashboard copy was routed through `en_dashboard.json`.
- [x] Helper attribute translation metadata was added for `ui_control`.

#### Phase 3 completion note

- 2026-03-07: Phase 3 completed. The dashboard helper now exposes resolved `ui_control` state, dashboard authoring docs now point templates to `state_attr(dashboard_helper, 'ui_control')`, and the first consumer remains limited to the Rewards header collapse control in `user-game-full-v1`. Canonical dashboard assets were synced into the vendored runtime mirror. Validation was run with `./utils/quick_lint.sh --fix` only, per user-approved deviation to defer pytest until the end of Phase 3.

### Phase 4 – Tests + documentation

- **Goal**: Validate storage normalization, helper exposure, service updates, and dashboard consumption with project-standard test coverage.
- **Steps / detailed work items**
  1. [ ] Add storage/default-structure tests near `tests/test_storage_manager.py` (lines 20-80) to confirm legacy data without UI preferences still initializes cleanly and that persisted overrides, if approved, round-trip correctly.
         **Files**: `tests/test_storage_manager.py`.
  2. [ ] Add user-profile normalization tests near current user helper/profile tests such as `tests/test_user_profile_gating_helpers.py` so new fields do not break capability gating or user normalization behavior.
         **Files**: `tests/test_user_profile_gating_helpers.py`, or a new focused `tests/test_user_ui_control_profile.py` module.
  3. [ ] Add dashboard-helper attribute tests near `tests/test_dashboard_helper_size_reduction.py` (lines 1-196) to verify `ui_control` appears on the helper without regressing size-focused architecture goals.
         **Files**: `tests/test_dashboard_helper_size_reduction.py`.
  4. [ ] Add service schema and end-to-end tests using current service patterns from `tests/test_chore_crud_services.py` and `tests/test_reward_crud_services.py`, proving `service -> user storage/runtime update -> helper refresh` behavior.
         **Files**: `tests/test_chore_crud_services.py`, or a new focused `tests/test_ui_control_services.py` module.
  5. [ ] Add translation parity tests patterned after `tests/test_pending_claim_action_contract_parity.py` so service fields/options/docs in `services.yaml` and `translations/en.json` stay aligned for the new UI-control contract.
         **Files**: `tests/test_ui_control_contract_parity.py` or equivalent, `custom_components/choreops/services.yaml`, `custom_components/choreops/translations/en.json`.
  6. [ ] Add template/render contract coverage if the first consumer lands in `user-game-full-v1`, using the dashboard-context and render-smoke test patterns described in `tests/test_dashboard_context_contract.py` and dashboard template smoke suites.
         **Files**: `tests/test_dashboard_context_contract.py`, relevant `tests/test_dashboard_*` module(s).
  7. [ ] Add translation coverage tests for any new dashboard-visible copy and helper attribute metadata so both integration and dashboard translation catalogs stay complete.
         **Files**: `tests/test_translations_custom.py`, relevant `tests/test_dashboard_*` modules, `custom_components/choreops/translations/en.json`, `choreops-dashboards/translations/en_dashboard.json`.
  8. [ ] Update architecture and authoring docs, then capture the required validation commands in the completion notes before Builder execution closes the initiative.
         **Files**: `docs/ARCHITECTURE.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`, this plan file.
- **Key issues** - Tests must verify both dashboard-default behavior and persisted-override behavior.
  - Dashboard-helper size tests should remain green; `ui_control` must stay compact.
  - Translation parity tests should be treated as part of the feature contract, not a later polish task.

#### Phase 4 builder blueprint

- Treat validation as a contract phase, not cleanup.
- The Builder should close this phase only after service, storage, helper, dashboard, and translation contracts all have test evidence or explicit approved rationale for any deferred coverage.
- Documentation blueprint: - architecture docs explain persistence and migration impact - dashboard template guide explains read path and fallback behavior - service docs explain mutation behavior including blank-key clear-all semantics

#### Phase 4 verification hold points

The Builder must confirm all of the following before marking the initiative ready for owner review:

- [ ] Storage/migration coverage exists for legacy records and new persisted preferences.
- [ ] Service tests cover create, update, keyed remove, and clear-all remove.
- [ ] Helper tests cover default fallback and stored override behavior.
- [ ] Translation parity tests cover service docs and integration translation maps.
- [ ] Dashboard translation coverage exists for any newly introduced visible text.
- [ ] Required validation gates were run and results recorded in this plan.

## Testing & validation

- **Planned validation commands**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- **Approved execution deviation** - Through the end of Phase 3, run lint-only validation (`./utils/quick_lint.sh --fix`) during phase execution. - Full pytest validation remains required before closing Phase 4 unless re-approved otherwise.
- **Targeted suites expected during implementation**
  - `python -m pytest tests/test_storage_manager.py -v --tb=line`
  - `python -m pytest tests/test_dashboard_helper_size_reduction.py -v --tb=line`
  - `python -m pytest tests/test_chore_crud_services.py tests/test_reward_crud_services.py -v --tb=line`
    - `python -m pytest tests/test_ui_control_contract_parity.py -v --tb=line`
  - `python -m pytest tests/test_dashboard_context_contract.py tests/test_dashboard_template_render_smoke.py -v --tb=line`
- **Outstanding tests (not run in planning)** - No implementation tests were run as part of this planning task. - Migration-specific tests will be required because persistence is now a locked decision.

## Notes & follow-up

### Purpose overview

The purpose of this feature is to let the integration own small, user-scoped dashboard behavior decisions such as whether an experimental section is expanded, while keeping templates simple and avoiding a growing collection of standalone Home Assistant helper entities. The dashboard helper remains the single frontend consumption surface; services and storage remain backend responsibilities, with `UserManager` owning durable writes and `UIManager` remaining the helper-facing UI orchestration layer.

### Proposed naming contract for review

#### User-profile storage keys (persisted with the user)

Recommended persisted shape:

```text
users[user_id].ui_preferences[...] = value
```

Recommended fixed bucket names:

- `ui_preferences`

Locked dynamic path model:

- Keys are dynamic and card-defined.
- Each relevant card exposes a local variable for the UI-control storage path used by its tap-action service call.
- Example reviewed path: `gamification/rewards/header_collapse`
- `remove` with an empty key path should clear all stored UI preferences for the targeted user.
- Forward slash (`/`) is the only supported nested path delimiter.
- Backslash-delimited paths are not supported because they introduce escaping ambiguity in YAML, JSON, and service payload strings.

Locked dynamic values:

- `key_path`: structured nested path identifying the UI setting
- Example: `gamification/rewards/header_collapse`

Recommended constant names:

- `DATA_USER_UI_PREFERENCES = "ui_preferences"`
- `DATA_USER_UI_PREFERENCES*` family for any supporting path/meta constants that prove necessary during implementation

Optional reviewed-path constant for first consumer:

- `UI_CONTROL_PATH_GAMIFICATION_REWARDS_HEADER_COLLAPSE = "gamification/rewards/header_collapse"`

#### Dashboard helper key shown to templates

Recommended helper attribute name:

- `ui_control`

Recommended helper shape:

```text
state_attr(dashboard_helper, 'ui_control') -> resolved UI control object for the user
```

Recommended constant name:

- `ATTR_UI_CONTROL = "ui_control"`

This keeps helper usage aligned with current concise helper attrs such as `core_sensors`, `dashboard_helpers`, and `pending_approvals`.

#### Expected service and signal constant names

Recommended service constants:

- `SERVICE_MANAGE_UI_CONTROL`
- `SERVICE_FIELD_UI_CONTROL_ACTION`
- `SERVICE_FIELD_UI_CONTROL_KEY`
- `SERVICE_FIELD_UI_CONTROL_VALUE`

Targeting should reuse current patterns where possible:

- `SERVICE_FIELD_CONFIG_ENTRY_ID`
- `SERVICE_FIELD_CONFIG_ENTRY_TITLE`
- `SERVICE_FIELD_USER_NAME`
- `SERVICE_FIELD_USER_ID`

Locked action values:

- `create`
- `update`
- `remove`

Recommended event constant:

- `SIGNAL_SUFFIX_UI_CONTROL_UPDATED`

Recommended error/translation constant family if service validation is user-facing:

- `TRANS_KEY_ERROR_UI_CONTROL_INVALID_KEY`
- `TRANS_KEY_ERROR_UI_CONTROL_INVALID_VALUE`
- `TRANS_KEY_ERROR_UI_CONTROL_INVALID_ACTION`

### Locked implementation decisions

- Per-user UI-control data will be persisted with the user profile.
- Dashboard templates/cards will always provide defaults when no persisted key exists.
- Forward slash (`/`) is the standard and only supported nested key delimiter.
- Public service actions are `create`, `update`, and `remove` only.
- Dashboard helper output is the read source; a service-level `read` action is not part of the contract.
- New user-facing strings must use translation-backed integration or dashboard catalogs; no new hardcoded UX copy is acceptable for this feature.

### Builder execution guardrails

- The Builder must request approval before deviating from any locked implementation decision.
- The Builder must justify any requested deviation using the required deviation request format in the Builder handoff package section.
- The Builder must not silently rename methods, constants, service fields, helper attributes, or translation keys for convenience.
- The Builder must not implement extra consumers, extra actions, or extra persistence fields in the same pass without approval.
- The Builder must update this plan after each completed step and phase.

### Translation and platinum-quality traps to avoid

- Do not add a new service in `services.py` without matching documentation in `custom_components/choreops/services.yaml` and matching user-facing strings in `custom_components/choreops/translations/en.json`.
- Do not add new `TRANS_KEY_*` constants without corresponding `exceptions`, `services`, or other required entries in `custom_components/choreops/translations/en.json`.
- Do not add a new dashboard-helper attribute such as `ui_control` without adding its attribute name metadata to the dashboard-helper entity section of `custom_components/choreops/translations/en.json`.
- Do not place dashboard-visible copy for the first consumer directly in `user-game-full-v1.yaml`; any new visible label or helper text belongs in `choreops-dashboards/translations/en_dashboard.json`.
- Do not let service action values, selector options, `services.yaml`, and translation option maps drift apart; existing contract-parity tests show this is already a known maintenance risk in the project.
- Do not assume English-only coverage is sufficient at the design level; even if translation pipelines handle other languages later, the feature is not platinum-ready unless the English source catalogs are complete and structurally correct.

### Recommended first-scope rule

Only one reviewed control path should be implemented first:

- `gamification/rewards/header_collapse`

Do not broaden the contract to arbitrary dashboard layout state until the first consumer proves the model and size impact.

> **Template usage notice:** Do **not** modify `docs/PLAN_TEMPLATE.md`. This file is an initiative-specific copy saved under `docs/in-process/` per project planning rules.
