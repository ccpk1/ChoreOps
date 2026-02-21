# Initiative Plan: Role-based user flow redesign (options/config)

## Initiative snapshot

- **Name / Code**: Role-based User Flow Redesign (`CHOREOPS-UX-ROLEFLOW-001`)
- **Target release / milestone**: v0.5.0-beta5 follow-up hardening
- **Owner / driver(s)**: Integration maintainers + architecture owner
- **Status**: Phase 5 and Phase 6 complete (all planned phases complete; awaiting owner approval for archive)

Program alignment note:

- Archive decision is gated by cross-plan reconciliation in `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`.
- Terminal terminology boundaries are governed by `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`.

## Summary & immediate steps

| Phase / Step                              | Description                                                              | % complete | Quick notes                                                                                                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Contract lock                   | Freeze role-based user UX/API contract and naming                        | 100%       | Canonical user terms, inclusion rules, and compatibility policy are now documented and locked                                                  |
| Phase 2 – Options entry-point rewrite     | Rewire options-flow user entry points to canonical user model            | 100%       | Main route now uses `manage_user`, CRUD uses user step IDs, selection source uses canonical user adapter                                       |
| Phase 3 – Form/translation unification    | Replace parent-labeled surfaces with role-based user language            | 100%       | User-management translation surfaces now consistently use user-role language and canonical step namespaces                                     |
| Phase 4 – Validation/data parity          | Align data builders, manager behavior, and user visibility rules         | 100%       | Approval inference removed, user-facing helper/manager APIs aligned, and user-management list ordering is deterministic                        |
| Phase 5 – Test matrix + release hardening | Migrate tests and verify all flow paths + regressions                    | 100%       | Focused hardening gates green: `test_options_flow_entity_crud`, `test_config_flow_fresh_start`, `test_ha_user_id_options_flow`, lint, and mypy |
| Phase 6 – Config flow parity rollout      | Replace start-fresh legacy kid/parent count/forms with canonical user UX | 100%       | Start-fresh route now uses canonical `user_count/users`; focused config-flow + options-flow matrix gates are green                             |

1. **Key objective** – Deliver a true role-based user management flow across config/options, removing parent-only routing and legacy UX leakage.
2. **Summary of recent work**

- Sequence 3 flow-contract packet completed: canonical assignee flow helpers were reinforced (`build_assignee_schema` primary with legacy wrapper retained), config-flow assignee counters/indexes moved to canonical internal naming, options-flow wrapper indirection was reduced (`edit_kid_shadow` now delegates directly to canonical assignee handler), and helper naming shifted to canonical user wording (`_get_user_ha_user_ids` with legacy wrapper retained). Validation gates passed (`./utils/quick_lint.sh --fix`, full pytest, scoped mypy).

- Phase 4 parity completed: validation now enforces explicit `can_approve` behavior (no inferred approval from associated users).
- Hard-fork runtime storage usage completed: options/config/coordinator/manager paths no longer read/write `DATA_PARENTS`; migration now removes legacy `parents` key after conversion.
- Hard-fork runtime compatibility removal completed: legacy parent route constants/wrappers are removed from runtime flow contract; focused tests now use canonical user step/menu IDs.
- Phase 5A value-first triage completed: full-suite failures are classified by business value and contract relevance before any rewrite/removal actions.
- Phase 5 Batch 1 completed: canonical users-backed points seeding fixed the remaining `workflow_gaps` reward/bonus/penalty point-balance regressions (targeted suite now fully green).
- Phase 5 Batch 2 completed: notification and shared-chore suites are green after removing all remaining legacy `DATA_PARENTS` test coupling in workflow notifications.
- Phase 5 Batch 3 completed: setup/shadow/migration suites are green after aligning assignable-user semantics and hard-fork storage assertions to canonical `users` behavior.
- Contract-facing helper APIs now include user-named wrappers (`build_user_schema`, `normalize_user_form_input`, `validate_users_inputs`, `map_user_form_errors`) and are wired into config/options user flow paths.
- Contract-facing manager APIs now include user-named wrappers (`create_user`, `update_user`, `delete_user`) and options-flow user handlers route through them.
- User-management adapter now returns a deterministic, stable ordering (name then ID) for consistent selection behavior.
- Validation gates completed: `./utils/quick_lint.sh --fix`, focused flow regression suite (44 passed), and `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`.
- Phase 5 closeout delta: updated HA-user-link options-flow test assumptions to align with current user-capability validation contract and completed focused hardening gates with all-pass results.

- Phase 3 translation unification completed: config/options user-management copy now consistently uses user-role wording.
- Canonical step namespaces for user flow (`user_count`, `users`, `add_user`, `edit_user`, `delete_user`) are now represented in translations.
- Legacy parent-labeled translation entries used for compatibility wrappers were updated to user-role wording to prevent UX leakage.
- Options intro text now uses canonical user language.
- Phase 2 entry-point rewrite completed: options menu now routes through canonical `manage_user` and normalizes legacy parent tokens to user flow.
- User CRUD flow now uses canonical user step IDs (`add_user`, `edit_user`, `delete_user`) with explicit parent-step compatibility wrappers.
- User selection source now uses coordinator canonical user-management adapter (`users_for_management`) rather than raw parent bucket reads.
- Config onboarding now uses user step contract (`user_count`/`users`) with legacy wrapper methods retained for flow continuity.
- Duplicate-name user selection now prefers approver/admin records in user edit/delete routing to prevent incorrect kid-target edits.
- Phase 1 contract lock completed across constants, translations, coordinator contract surface, and architecture policy notes.
- Canonical terminology map now defines `manage_user` + `add_user`/`edit_user`/`delete_user` as the role-based flow contract.
- Inclusion rules for Manage Users are documented in architecture and coordinator via canonical `users_for_management` contract property.
- Compatibility policy now explicitly forbids label-only alias routing for options/config user-management surfaces.
- Menu label changed to “Manage Users”, but route remains `manage_parent` and still uses parent-scoped data.
- User sections were added to parent schema, but flow step IDs/titles/descriptions still refer to parent/kid entities.
- Existing selectors and CRUD routing still branch by `kid`/`parent` dictionaries and step handlers.

3. **Next steps (short term)**

- Complete translation contract realignment gate before archive approval: `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md`.
- Complete terminology hard-cut gate before archive approval: `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`.
- Owner review of completion evidence and approval to move this plan to completed.
- Optional broader regression run (`python -m pytest tests/ -v --tb=line`) if environment permits.
- If broader run is deferred, proceed with documented focused-gate evidence for release hardening sign-off.

4. **Risks / blockers**
  - Archive remains blocked until cross-plan terminology and translation gates are closed per master orchestration.
  - Residual historical references in this plan must remain clearly marked as resolved/non-authoritative context.
  - Final closeout still depends on program-level evidence consolidation (open-vs-done matrix).
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
   - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
   - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
   - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
   - [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py)
   - [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)

- [docs/in-process/OPTIONS_FLOW_ROLE_BASED_USERS_SUP_TEST_VALUE_TRIAGE.md](OPTIONS_FLOW_ROLE_BASED_USERS_SUP_TEST_VALUE_TRIAGE.md)
- [docs/in-process/OPTIONS_FLOW_ROLE_BASED_USERS_SUP_BUILDER_HANDOFF.md](OPTIONS_FLOW_ROLE_BASED_USERS_SUP_BUILDER_HANDOFF.md)

6. **Decisions & completion check**
   - **Decisions captured**:
  - Approved terminal terminology policy: `KidsChores` is restricted to migration/legacy/credit references and the explicit fun label `KidsChores Mode`; `kid` and `parent` are disallowed in runtime symbols/translations/core docs outside documented migration-only compatibility and intentional README/wiki exceptions.
     - Options/config UX is user-role based; parent/kid wording is non-canonical for user management surfaces.
     - “Manage Users” must enumerate all managed user records intended by the role model, not only legacy parent bucket rows.
     - Step IDs, selector values, and translation namespaces must be coherent (no label-only rename).
   - **Completion confirmation**: `[ ]` All implementation, tests, and docs completed before owner approval.

## Detailed analysis (historical baseline and resolved findings)

This section is retained as historical context for completed work and is not the authoritative blocker list. Current gating decisions are tracked in:

- `REBRAND_ROLEMODEL_MASTER_ORCHESTRATION_IN-PROCESS.md`
- `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`

Any conflict between this historical section and the summary/status sections should be resolved in favor of the program authority plans above.

### A) Entry-point and routing drift

- Main menu in options flow now hides `manage_kid`, but still routes through `manage_parent`:
  - `OPTIONS_FLOW_PARENTS = "manage_parent"` and `self._entity_type = "parent"`
  - File: [custom_components/choreops/const.py](../../custom_components/choreops/const.py)
  - File: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
- `async_step_manage_entity` + `async_step_select_entity` still execute parent-specific handlers (`add_parent`, `edit_parent`, `delete_parent`), preserving old domain naming.

### B) Data-source mismatch causing “subset of users” behavior

- `_get_entity_dict()` maps parent entity type to raw `DATA_PARENTS` bucket, not canonical user view:
  - File: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
- Coordinator exposes `users_data`, `kids_data`, and `parents_data` compatibility views, but options flow bypasses these by reading raw `coordinator.data[DATA_PARENTS]`.
  - File: [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
- Outcome: “Manage Users” can miss role-based user records that are not represented in legacy parent bucket.

### C) Form model is partially modernized, surface language is not

- Sectioned user schema exists in helper layer (`section_identity_profile`, `section_system_usage`, `section_admin_approval`).
  - File: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
- But options/config step IDs and many strings remain parent/kid named (`add_parent`, `edit_parent`, `Define Parent`, `Add Parent`).
  - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)

### D) Validation parity gap

- `build_parent` no longer infers `can_approve`, but `validate_parent_data()` still defaults `can_approve` from associated users when key missing.
  - File: [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
- This can create inconsistent UX/behavior across create vs edit paths and legacy payloads.

### E) Config flow still parent-count/parent-step driven

- Initial setup continues with `parent_count` and `parents` step identifiers.
  - File: [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
- This diverges from the hard-fork user-form contract in architecture docs.

## Detailed phase tracking

### Phase 1 – Contract lock

- **Goal**: Lock exact role-based flow contract before any code rewrite.
- **Steps / detailed work items**
  - [x] Publish canonical terminology map for flow surfaces.
    - Files: [custom_components/choreops/const.py](../../custom_components/choreops/const.py), [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
    - Define canonical `user` flow terms for menu value, entity type, and step IDs.
  - [x] Define user record inclusion rules for “Manage Users”.
    - Files: [docs/ARCHITECTURE.md](../ARCHITECTURE.md), [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - Explicitly list which records appear and why (assignee-only, approver-only, dual-role, linked profile behavior).
  - [x] Freeze compatibility policy for this rewrite.
    - File: [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md](CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md)
    - Confirm no label-only compatibility aliases in runtime options/config flow.
- **Key issues**
  - Must prevent new mixed vocabulary (`parent` implementation under `users` label).

### Phase 2 – Options entry-point rewrite

- **Goal**: Rewire options flow to canonical user entry points.
- **Steps / detailed work items**
  - [x] Replace options menu user route constants and selector values.
    - Files: [custom_components/choreops/const.py](../../custom_components/choreops/const.py), [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
    - Introduce `manage_user` route and user entity type token; remove dependency on `manage_parent` for main UX.
  - [x] Replace parent-specific CRUD step handlers with user-centric handlers.
    - File: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
    - New step IDs: `add_user`, `edit_user`, `delete_user` (with explicit migration mapping for internal flow continuity).
  - [x] Update selection dictionary source from raw parent bucket to canonical user view adapter.
    - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py), [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - Remove direct `_get_entity_dict()` dependency on `DATA_PARENTS` for user-management path.
- **Key issues**
  - This phase is high-impact; partial merge is not acceptable.

### Phase 3 – Form/translation unification

- **Goal**: Make user-facing copy and translation hierarchy fully role-based.
- **Steps / detailed work items**
  - [x] Add canonical options/config translation steps for user CRUD.
    - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
    - Introduce `add_user`, `edit_user`, `delete_user`, and user-count text where applicable.
  - [x] Remove parent/kid text from user-management forms and descriptions.
    - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
  - [x] Keep sectioned schema keys synchronized with translation namespaces.
    - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py), [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
  - [x] Update options intro copy to remove legacy “manage kids/parents” language.
    - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
- **Key issues**
  - Copy-only edits without step-ID alignment create hidden translation drift.

### Phase 4 – Validation/data parity

- **Goal**: Ensure behavior parity across config flow, options flow, and services.
- **Steps / detailed work items**
  - [x] Remove implicit approval inference path and enforce explicit capability validation consistently.
    - File: [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
    - `validate_parent_data()` must match `build_parent()` behavior.
  - [x] Rename/align helper APIs from parent terminology to user terminology where contract-facing.
    - Files: [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py), [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py)
  - [x] Add deterministic adapter for user-management display list.
    - Files: [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py), [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - Define sort/visibility rules and linked-profile marker behavior under unified user UX.
- **Key issues**
  - Role capability semantics must remain identical after naming/routing migration.

### Phase 5 – Test matrix + release hardening

- **Goal**: Validate all flow entry points and regression paths before release.
- **Steps / detailed work items**
  - [x] Rewrite options flow CRUD/navigation tests to canonical user flow names and routes.
    - Files: [tests/test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py), [tests/test_options_flow_shadow_kid_entity_creation.py](../../tests/test_options_flow_shadow_kid_entity_creation.py)
    - Status note: shadow-focused coverage is represented by active current suites (for example `tests/test_ha_user_id_options_flow.py`) in this branch.
  - [x] Add contract tests for user selection completeness (no parent-bucket subset).
    - Files: [tests/test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py), [tests/helpers/setup.py](../../tests/helpers/setup.py)
  - [x] Update config fresh-start tests for user-count/user-step progression.
    - File: [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py)
  - [x] Validate translation coverage for new step IDs and selector labels.
    - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
    - Status note: targeted translation coverage check for canonical role-flow keys passed.
  - [x] Execute gates:
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/test_options_flow_entity_crud.py tests/test_options_flow_shadow_kid_entity_creation.py tests/test_config_flow_fresh_start.py -v --tb=line`
    - Executed focused gate set in current branch:
      - `python -m pytest tests/test_options_flow_entity_crud.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py -v --tb=line` → 39 passed
      - `./utils/quick_lint.sh --fix` → passed (ruff + boundary + mypy gate inside script)
      - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` → 0 errors
- **Key issues**
  - Existing tests currently encode parent/kid step names and must be migrated atomically with runtime changes.

### Phase 6 – Config flow parity rollout (start-fresh path)

- **Goal**: Bring the start-fresh config flow to the same canonical user-role contract already applied in options flow.
- **Scope lock (explicit)**
  - In scope:
    - Start-fresh onboarding path currently exposing legacy kid/parent count steps and forms.
    - Canonical user step IDs, user-role forms, and translation alignment for config flow.
  - Out of scope:
    - Backup import/migration internals beyond required field/step mapping continuity.
    - Unrelated service/runtime refactors.
- **Steps / detailed work items**
  - [x] Define and freeze canonical start-fresh config step sequence
    - File: [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
    - Required:
      - Replace legacy branching through `kid_count` + `parent_count` with canonical user-oriented onboarding sequence.
      - Remove reliance on legacy parent/kid step IDs in the primary start-fresh route.
  - [x] Replace start-fresh legacy forms with canonical user-role form(s)
    - Files: [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py), [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
    - Required:
      - Use the same capability-first user form contract as options flow (`can_be_assigned`, `can_approve`, `can_manage`, workflow/gamification toggles).
      - Preserve sectioned UX parity and section-level error mapping.
  - [x] Align config-flow translation namespaces and labels to user-role contract
    - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
    - Required:
      - Remove legacy kid/parent wording from start-fresh step titles/descriptions.
      - Ensure canonical step IDs have complete translation coverage.
  - [x] Add explicit compatibility boundary for legacy wrappers in config flow
    - Files: [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py), [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md](CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md)
    - Required:
      - Document any temporary wrapper methods and their removal target.
      - Ensure wrapper use does not define the primary route contract.
  - [x] Add focused regression matrix for start-fresh role-based onboarding
    - Files: [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py), [tests/helpers/setup.py](../../tests/helpers/setup.py)
    - Required scenarios:
      1. User-role onboarding with assignable-only participant.
      2. User-role onboarding with approver-only participant.
      3. Mixed-role onboarding with both assignee and approver capabilities.
      4. Validation failures for capability constraints and section error routing.
  - [x] Execute dedicated Phase 6 gates before release hardening continuation
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/test_config_flow_fresh_start.py tests/test_config_flow_error_scenarios.py tests/test_options_flow_entity_crud.py -v --tb=line`
- **Acceptance criteria (must all pass)**
  - Start-fresh no longer presents legacy kid/parent count/forms as the primary onboarding contract.
  - Config flow and options flow present consistent canonical user-role terminology and step IDs.
  - Config-flow start-fresh tests assert user-role contract behavior and pass in focused suite.
  - No label-only compatibility route remains in the primary config-flow path.
- **Key issues**
  - Partial rollout risks mixed UX where options flow is canonical but start-fresh remains legacy.
  - Translation and step-ID drift can reintroduce silent regressions if not validated as one batch.

## Testing & validation

- **Required acceptance tests**
  - User can add/edit/delete role-based users from options without parent-only filtering.
  - User selection list includes all intended role records per contract.
  - Config flow user step surfaces role-based language and validation behavior.
  - Section-level and field-level errors render correctly for collapsed admin section.

## Notes & follow-up

- Implementation should be done in coherent batches (Phase 2 + 3 together minimum) to avoid another partial-state release.
- Any retained legacy constants/step IDs must be justified with explicit removal step in this document.
