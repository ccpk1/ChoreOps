# Initiative Plan: Role-based user flow redesign (options/config)

## Initiative snapshot

- **Name / Code**: Role-based User Flow Redesign (`CHOREOPS-UX-ROLEFLOW-001`)
- **Target release / milestone**: v0.5.0-beta5 follow-up hardening
- **Owner / driver(s)**: Integration maintainers + architecture owner
- **Status**: Phase 5 in progress (hard-fork runtime key and compatibility removal completed)

## Summary & immediate steps

| Phase / Step                              | Description                                                      | % complete | Quick notes                                                                                                                                               |
| ----------------------------------------- | ---------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Contract lock                   | Freeze role-based user UX/API contract and naming                | 100%       | Canonical user terms, inclusion rules, and compatibility policy are now documented and locked                                                             |
| Phase 2 – Entry-point rewrite             | Rewire options/config user entry points to canonical user model  | 100%       | Main route now uses `manage_user`, CRUD uses user step IDs, selection source uses canonical user adapter                                                  |
| Phase 3 – Form/translation unification    | Replace parent-labeled surfaces with role-based user language    | 100%       | User-management translation surfaces now consistently use user-role language and canonical step namespaces                                                |
| Phase 4 – Validation/data parity          | Align data builders, manager behavior, and user visibility rules | 100%       | Approval inference removed, user-facing helper/manager APIs aligned, and user-management list ordering is deterministic                                   |
| Phase 5 – Test matrix + release hardening | Migrate tests and verify all flow paths + regressions            | 94%        | Batch 1-3 green (`workflow_chores`, `workflow_gaps`, `badge_cumulative`, `workflow_notifications`, `shared_chore_features`, setup/shadow/migration suite) |

1. **Key objective** – Deliver a true role-based user management flow across config/options, removing parent-only routing and legacy UX leakage.
2. **Summary of recent work**

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
   - Approve this plan as the implementation contract.
   - Execute Phase 1 and 2 in one PR batch (contract + routing).
   - Hold Phase 3+ until routing parity tests are green.
4. **Risks / blockers**
   - Runtime remains dual-bucket (`DATA_USERS` + `DATA_PARENTS`) during migration window, creating selection/visibility drift.
   - High risk of partial rename (labels only) unless step IDs, selector values, and data-source adapters are changed together.
   - Test churn is significant because existing tests encode old step names and menu values.
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

6. **Decisions & completion check**
   - **Decisions captured**:
     - Options/config UX is user-role based; parent/kid wording is non-canonical for user management surfaces.
     - “Manage Users” must enumerate all managed user records intended by the role model, not only legacy parent bucket rows.
     - Step IDs, selector values, and translation namespaces must be coherent (no label-only rename).
   - **Completion confirmation**: `[ ]` All implementation, tests, and docs completed before owner approval.

## Detailed analysis (current-state findings)

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

### Phase 2 – Entry-point rewrite

- **Goal**: Rewire options flow and config flow to canonical user entry points.
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
  - [x] Align config flow onboarding steps from `parent_count`/`parents` to user-oriented step contract.
    - File: [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
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
  - [ ] Rewrite options flow CRUD/navigation tests to canonical user flow names and routes.
    - Files: [tests/test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py), [tests/test_options_flow_shadow_kid_entity_creation.py](../../tests/test_options_flow_shadow_kid_entity_creation.py)
  - [ ] Add contract tests for user selection completeness (no parent-bucket subset).
    - Files: [tests/test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py), [tests/helpers/setup.py](../../tests/helpers/setup.py)
  - [ ] Update config fresh-start tests for user-count/user-step progression.
    - File: [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py)
  - [ ] Validate translation coverage for new step IDs and selector labels.
    - File: [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
  - [ ] Execute gates:
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/test_options_flow_entity_crud.py tests/test_options_flow_shadow_kid_entity_creation.py tests/test_config_flow_fresh_start.py -v --tb=line`
- **Key issues**
  - Existing tests currently encode parent/kid step names and must be migrated atomically with runtime changes.

## Testing & validation

- **Required acceptance tests**
  - User can add/edit/delete role-based users from options without parent-only filtering.
  - User selection list includes all intended role records per contract.
  - Config flow user step surfaces role-based language and validation behavior.
  - Section-level and field-level errors render correctly for collapsed admin section.

## Notes & follow-up

- Implementation should be done in coherent batches (Phase 2 + 3 together minimum) to avoid another partial-state release.
- Any retained legacy constants/step IDs must be justified with explicit removal step in this document.
