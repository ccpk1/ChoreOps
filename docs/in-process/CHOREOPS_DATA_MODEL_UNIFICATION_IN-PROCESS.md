# Initiative Plan: ChoreOps data model unification (Option 3)

## Initiative snapshot

- **Name / Code**: ChoreOps Data Model Unification (`CHOREOPS-ARCH-UNIFY-003`)
- **Target release / milestone**: v0.5.0-beta5 (schema 45)
- **Owner / driver(s)**: Engineering + Strategy & Architecture Team
- **Status**: Architecture pivot in progress (Phase 1/2 refinement active)

## Summary & immediate steps

| Phase / Step                              | Description                                                                    | % complete | Quick notes                                                                                              |
| ----------------------------------------- | ------------------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------- |
| Phase 1 – Contract & migration foundation | Lock unified-user schema contract and capability-only authorization model      | 65%        | Pivot applied; checklist reset to strict contract                                                        |
| Phase 2 – Storage unification migration   | Replace `kids`/`parents` with canonical `users` using promote-and-merge method | 25%        | Migration path exists; must remove legacy dual-bucket use                                                |
| Phase 3 – Full Python refactor            | Rename internal model and logic (`kid_*` → `user_*`) across managers/platforms | 90%        | `manage_shadow_link` retired; parent linked-profile constant migration active with legacy key alias preserved |
| Phase 4 – Tests, hardening, and release   | Update tests/fixtures, validate migration paths, publish release notes         | 0%         | No release until migration-path tests are green                                                          |

1. **Key objective** – Complete a clean backend reset to one role-based `users` model and remove shadow-kid architecture debt in the same initiative.
2. **Summary of recent work**

- Option comparison completed; Option 3 selected as architecture target.
- Migration strategy retained: **kid-first / promote-and-merge**.
- Contract pivot approved: **Identity decoupled from capability** (`can_approve`, `can_manage`, `can_be_assigned`).
- Legacy model assumptions are now explicitly deprecated: no separate runtime parent dictionary, no shadow-link relationship model.
- Phase 3 batch progress: coordinator `users_data` bridge is active and manager reads in chore/reward/gamification/user-manager were migrated away from direct split-bucket raw access.
- Validation snapshot (batch): `./utils/quick_lint.sh --fix` passed and focused tests passed (`test_shadow_link_service`, `test_kc_helpers`, `test_kiosk_mode_buttons`, `test_schema45_user_migration`).
- Additional Phase 3 typing pass: `KidData` annotations were migrated to `UserData` in chore/reward/gamification managers with green chore/reward/gamification focused tests.
- Helper/platform migration delta: entity creation gating now routes through capability-aware participation helper (`can_be_assigned` with legacy fallback), validated against shadow and kiosk behavior suites.
- Platform call-site cleanup delta: `sensor`, `button`, `select`, `calendar`, and `datetime` now use capability-oriented approval-profile naming in entity-creation calls while retaining compatibility behavior.
- Validation snapshot (platform batch): `./utils/quick_lint.sh --fix` passed and focused tests passed (`test_shadow_kid_buttons`, `test_kiosk_mode_buttons`, `test_chore_services`).
- Next-pass gating reminder: add a final capability-first entity-creation matrix (`can_be_assigned`, workflow toggle, gamification toggle, extra toggle) and remove runtime dependency on `is_shadow_kid` semantics after compatibility window.
- Semantic cleanup delta: entity helper and platform call-sites now use `feature_gated_profile` naming bridge while preserving legacy compatibility paths; validation passed with focused helper/shadow/workflow suites.
- Service compatibility delta: `manage_shadow_link` now maps legacy link/unlink actions to `can_be_assigned` updates with deprecation warnings (no hard-fail path), and focused service tests were updated and validated.
- Options-flow delta: local shadow-centric variable/comment wording shifted to feature-gated terminology (behavior unchanged), and stale direct `coordinator._data[DATA_KIDS]` test access was updated to use `coordinator.kids_data` in unified-model validation tests.
- Flow validation delta: config-flow local shadow-profile naming was migrated to linked profile terminology (behavior unchanged), and focused config/options flow suites now pass against unified coordinator views.
- Planning delta: explicit deferred step added for consolidated kid/parent form UX after compatibility-window stabilization.
- Builder semantics delta: `data_builders` kid/parent validation language now uses assignment/feature-gated terminology in comments/docstrings/local variables without behavior changes; focused config/options/compatibility test suites remain green.
- Authorization delta: `auth_helpers` now exposes centralized `is_user_authorized_for_action` capability checks and service-level authorization paths route through action constants (`approval`/`management`) with compatibility wrappers retained.
- Authorization cleanup delta: interim helper wrappers were removed; `button`, `services`, and helper tests now use centralized action-based authorization checks directly.
- Terminology cleanup delta: `config_flow`/`options_flow`/`data_builders` comments and local naming now consistently use parent-linked profile wording (behavior unchanged); focused config/options suites remain green.
- Terminology sweep completion delta: residual flow-surface wording was normalized (`is_feature_gated_profile` → `is_linked_profile` and remaining feature-gated comment text removed); `flow_helpers` required no further changes.
- Service compatibility delta: `manage_shadow_link` handler internals now use capability-oriented profile naming and include explicit schema-version deprecation context in warnings; focused shadow-link/chore/reward service suites are green.
- Translation alignment delta: `translations/en.json` service text for `manage_shadow_link` now matches compatibility behavior (`can_be_assigned` toggle) instead of retired shadow-link rename/link semantics.
- Service retirement delta: `manage_shadow_link` registration/schema/constants/docs/tests were removed (`services.py`, `const.py`, `services.yaml`, `translations/en.json`, helper exports, retired test/scenario files) with focused service/options suites green.
- Stale-field cleanup delta: introduced canonical `DATA_PARENT_LINKED_PROFILE_ID` and migrated runtime references (`config_flow`, `options_flow`, `data_builders`, `migration_pre_v50`, `user_manager`) while keeping `DATA_PARENT_LINKED_SHADOW_KID_ID` as compatibility alias to the same storage key.

3. **Next steps (short term)**

- Finalize Phase 1 strict contract updates (`const.py`, `type_defs.py`, `auth_helpers.py`, `data_builders.py`).
- Complete Phase 2 canonical migration behavior with no dual-bucket runtime dependency.
- Rebase open work to remove shadow-link and parent-list assumptions.

4. **Risks / blockers**
   - High-touch refactor across managers, entities, helpers, and tests.
   - Potential migration regressions for legacy installations if role-flag merge is incomplete.
   - Release timeline risk if test fixture migration is under-scoped.

- Environment validation blockers observed:
  - `mypy custom_components/choreops/` parser failure in linked Home Assistant core syntax context.
  - `python -m pytest tests/ -v --tb=line` terminated with exit 137 near completion in current container.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)

- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CRITICAL_REVIEW.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CRITICAL_REVIEW.md)
- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_IMPLEMENTATION_BLUEPRINT.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_IMPLEMENTATION_BLUEPRINT.md)
- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_PHASE12_REMEDIATION.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_PHASE12_REMEDIATION.md)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Option 1 rejected.
     - Option 2 migration pattern adopted as implementation method.
     - Option 3 selected as final architecture outcome in this cycle.
     - Backend terminology standard approved: `users`, `user_id`, `user_data`.
   - **Completion confirmation**: `[ ]` All migration, refactor, compatibility, and release tasks complete before requesting owner approval.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Update phase percentages and blockers after each merged implementation PR.
- **Detailed tracking**: Keep low-level task notes in phase sections; keep summary high-level.

## Detailed phase tracking

### Phase 1 – Contract & migration foundation

- **Goal**: Freeze the data contract, schema/version path, and migration wiring before any broad refactor.
- **Steps / detailed work items**
  - [ ] Define and add unified-user constants only (remove split model constants)
    - File: [custom_components/choreops/const.py](../../custom_components/choreops/const.py)
    - Required: `DATA_USERS`, `DATA_USER_*`, capability flags.
    - Required removal target: `DATA_KIDS`, `DATA_PARENTS` as canonical model constants.
  - [x] Define next schema version and migration semantic note
    - File: [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L331-L355)
    - Add explicit schema bump and comment for kid/parent → users unification.
  - [x] Add migration hook entry point in integrity pipeline
    - File: [custom_components/choreops/managers/system_manager.py](../../custom_components/choreops/managers/system_manager.py#L190-L236)
    - Ensure migration executes before `DATA_READY` emission.
  - [x] Add architecture contract notes for role flags
    - File: [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Document `can_approve`, `can_manage`, and `can_be_assigned` as the canonical role model.
  - [ ] Define authorization matrix contract and explicit non-derivation rules
    - Files: [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Rule: `can_approve`/`can_manage` are explicit capabilities, not inferred from assignment relationships.
    - Acceptance criteria:
      - Documented precedence order: Home Assistant runtime admin override → stored capability flags → deny.
      - Assignment changes do not grant or revoke `can_approve` or `can_manage`.
      - At least one authorization test covers each precedence branch.
  - [ ] Consolidate type layer and builder contract to unified user model
    - Files: [custom_components/choreops/type_defs.py](../../custom_components/choreops/type_defs.py), [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
    - Required:
      - Merge `KidData` + `ParentData` into `UserData` TypedDict.
      - Add `build_user` with explicit capability inputs (`set_approve`, `set_manage`, `set_assigned`).
      - Remove dual-builder assumptions for kid/parent as canonical persistence model.
  - [ ] Define service/event compatibility window for legacy key names
    - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py), [custom_components/choreops/notification_action_handler.py](../../custom_components/choreops/notification_action_handler.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Rule: Support `kid_id` and `user_id` payload keys during transition window; emit deprecation logs for legacy keys.
    - Acceptance criteria:
      - Compatibility window duration and end-version are documented.
      - Incoming legacy payloads continue working during the window.
      - Release notes include removal timeline and migration guidance.
  - [x] Define parent-merge collision policy for `users` map
    - Files: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Rule: If standalone parent insert collides on `user_id`, generate new ID and persist remap metadata/log.
    - Acceptance criteria:
      - Collision path is deterministic and idempotent.
      - Collision count and remapped IDs are logged in migration summary.
      - Migration tests include at least one forced-collision fixture.
  - [ ] Define hard removal contract for shadow-link relationships
    - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py), [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Required: remove `linked_shadow_kid_id` model and shadow-link maintenance behavior from canonical flow.
- **Key issues**
  - Schema and constant names must be final before mass renaming begins.

### Phase 2 – Storage unification migration

- **Goal**: Perform startup migration from legacy split dictionaries to unified `users` without copying kid payloads.
- **Steps / detailed work items**
  - [ ] Implement kid-first rename container algorithm in migration module (canonical)
    - File: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
    - Algorithm:
      1. `data['users'] = data.pop('kids')`
      2. Enrich all users with defaults: `can_approve=False`, `can_manage=False`, `can_be_assigned=True`
      3. Merge `parents` into `users`:
         - linked shadow parent updates existing user record (`can_approve=True`, `can_manage=True`, auth updates)
         - standalone parent creates new user (`can_approve=True`, `can_manage=True`, `can_be_assigned=False`)
      4. Drop legacy container references from canonical runtime state (`kids`, `parents`).
  - [ ] Guarantee idempotency and re-run safety
    - File: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
    - Re-running migration should not duplicate users or corrupt role flags.
  - [ ] Keep startup backup protection before migration writes
    - File: [custom_components/choreops/**init**.py](../../custom_components/choreops/__init__.py#L122-L154)
    - Ensure recovery backup exists before persistence of transformed schema.
  - [ ] Update default store shape to canonical `users` only
    - File: [custom_components/choreops/store.py](../../custom_components/choreops/store.py#L45-L72)
    - New installs initialize with `users` only (no split buckets).
  - [ ] Add migration summary logs and counts for observability
    - Files: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py), [custom_components/choreops/managers/system_manager.py](../../custom_components/choreops/managers/system_manager.py)
    - Log counts: users migrated, linked-parent merges, standalone parent creations.
- **Key issues**
  - Parent-to-user merge needs deterministic precedence rules for auth and naming fields.
  - Open runtime paths still reading split buckets must be refactored in same wave.

### Phase 3 – Full Python refactor (`kid_*` → `user_*`)

- **Goal**: Align all internal symbols, TypedDicts, managers, and platform logic to the unified user model.
- **Steps / detailed work items**
  - [ ] Rename type layer to unified user model
    - File: [custom_components/choreops/type_defs.py](../../custom_components/choreops/type_defs.py)
    - `KidData` → `UserData`; update collection aliases and related type imports.
  - [x] Refactor coordinator accessors and field names
    - File: [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - Replace `kids_data` / `parents_data` pathways with unified user accessors and role-filter helpers where needed.
  - [x] Implement dual-read interim compatibility properties in coordinator
    - File: [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - Provide temporary `kids_data` and `parents_data` filtered views over `users_data` to enable manager-by-manager refactor PRs.
    - Acceptance criteria:
      - Existing managers operate unchanged against filtered views during transition.
      - New/refactored managers consume canonical `users_data` APIs.
      - Interim properties are marked temporary with removal target in plan notes.
  - [ ] Refactor managers to consume `user_id` and role flags
    - Files:
      - [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py)
      - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
      - [custom_components/choreops/managers/reward_manager.py](../../custom_components/choreops/managers/reward_manager.py)
      - [custom_components/choreops/managers/gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py)
      - [custom_components/choreops/managers/notification_manager.py](../../custom_components/choreops/managers/notification_manager.py)
    - Progress note: Accessor migration batches completed for `chore_manager`, `reward_manager`, `gamification_manager`, and `user_manager`; `notification_manager` has no direct split-bucket raw reads. Full role-flag semantic rename still remains.
  - [ ] Refactor helper and platform logic to capability flags (remove shadow branching)
    - Files:
      - [custom_components/choreops/helpers/entity_helpers.py](../../custom_components/choreops/helpers/entity_helpers.py)
      - [custom_components/choreops/helpers/device_helpers.py](../../custom_components/choreops/helpers/device_helpers.py)
      - [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py)
      - [custom_components/choreops/button.py](../../custom_components/choreops/button.py)
      - [custom_components/choreops/select.py](../../custom_components/choreops/select.py)
      - [custom_components/choreops/calendar.py](../../custom_components/choreops/calendar.py)
      - [custom_components/choreops/datetime.py](../../custom_components/choreops/datetime.py)
    - Progress note: `entity_helpers` now includes capability-aware assignment participation checks with migration-safe fallback; primary platform setup call sites have been migrated to capability-oriented naming.
  - [ ] Remove shadow-link service and stale shadow fields once migration is stable
    - File: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L527-L667)
    - Replace with role-based user administration behavior or remove endpoint with migration notice.
    - Progress note: Runtime service endpoint is retired and linked-profile constant migration is in place; final storage key/type rename cleanup remains.
  - [x] Convert shadow-link service to no-op compatibility behavior before removal
    - File: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L527-L667)
    - Transition behavior: legacy service toggles `can_be_assigned` on target user and emits deprecation warning.
    - Acceptance criteria:
      - Existing automations calling shadow-link service do not hard-fail during compatibility window.
      - Deprecation logs clearly point to capability-based replacement behavior.
  - [x] Rename flow inputs/outputs and builders to user-oriented naming
    - Files:
      - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
      - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
      - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
      - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
  - [x] Unify authorization helpers into capability-driven permission checks
    - Files:
      - [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py)
      - [custom_components/choreops/services.py](../../custom_components/choreops/services.py)
    - Replace fragmented checks with centralized capability-action checks.
    - Naming contract:
      - Avoid role-bucket names in final APIs (for example, avoid `authorized_for_kid`).
      - Prefer action/capability names (for example, approval authorization, management authorization, assignment participation checks).
    - Acceptance criteria:
      - All service-level authorization paths use shared helper.
      - Helper enforces precedence: HA admin override → capability checks → deny.
      - No final public helper name implies legacy split-role storage model.
  - [x] Remove interim authorization wrapper layer after refactor stabilization
    - Files:
      - [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py)
      - [tests/test_kc_helpers.py](../../tests/test_kc_helpers.py)
    - Acceptance criteria:
      - Wrapper functions kept only during staged migration.
      - Wrapper removal occurs before Phase 3 sign-off.
      - Tests assert action/capability-oriented helper usage, not wrapper usage.
- **Key issues**
  - This phase intentionally touches many files; execute in narrow, reviewable PR batches to limit regression scope.

### Phase 4 – Tests, hardening, and release

- **Goal**: Prove migration safety and behavioral parity for user workflows before release.
- **Steps / detailed work items**
  - [ ] Update test constants/helpers for user terminology
    - Files:
      - [tests/helpers/constants.py](../../tests/helpers/constants.py)
      - [tests/helpers/setup.py](../../tests/helpers/setup.py)
      - [tests/helpers/**init**.py](../../tests/helpers/__init__.py)
  - [ ] Rewrite migration-path tests for users schema
    - Files:
      - [tests/test_migration_hardening.py](../../tests/test_migration_hardening.py)
      - [tests/test_config_flow_use_existing.py](../../tests/test_config_flow_use_existing.py)
      - [tests/test_config_flow_direct_to_storage.py](../../tests/test_config_flow_direct_to_storage.py)
      - Add migration fixture wrapper that transforms legacy test payloads through real migration logic before assertions.
  - [ ] Rewrite shadow-focused tests to role-flag semantics
    - Files:
      - [tests/test_parent_shadow_kid.py](../../tests/test_parent_shadow_kid.py)
      - [tests/test_shadow_kid_buttons.py](../../tests/test_shadow_kid_buttons.py)
      - [tests/test_shadow_link_service.py](../../tests/test_shadow_link_service.py)
      - [tests/test_options_flow_shadow_kid_entity_creation.py](../../tests/test_options_flow_shadow_kid_entity_creation.py)
  - [ ] Validate diagnostics and entity behavior under unified user model
    - Files:
      - [tests/test_diagnostics.py](../../tests/test_diagnostics.py)
      - [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py)
      - [tests/test_badge_target_types.py](../../tests/test_badge_target_types.py)
  - [ ] Add authorization acceptance tests for capability and HA-admin precedence
    - Files:
      - [tests/test_chore_services.py](../../tests/test_chore_services.py)
      - [tests/test_reward_services.py](../../tests/test_reward_services.py)
      - [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py)
    - Required scenarios:
      1. HA admin override: can approve/manage even when no designated approver exists.
      2. Designated approver: non-admin with `can_approve=true` can approve but cannot manage unless `can_manage=true`.
      3. Non-approver denial: assigned/linked user without `can_approve` is denied approval actions.
  - [ ] Add final entity-gating matrix and assertions for capability-only behavior
    - Files:
      - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
      - [tests/test_shadow_kid_buttons.py](../../tests/test_shadow_kid_buttons.py)
      - [tests/test_options_flow_shadow_kid_entity_creation.py](../../tests/test_options_flow_shadow_kid_entity_creation.py)
    - Matrix dimensions:
      - Eligibility: `can_be_assigned`
      - Feature toggles: workflow enabled, gamification enabled, extra entities enabled
      - Requirement classes: `ALWAYS`, `WORKFLOW`, `GAMIFICATION`, `EXTRA`
  - [ ] Evaluate and implement consolidated user form UX (post-compatibility)
    - Files:
      - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
      - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
      - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
    - Scope:
      - Merge kid/parent setup UX into a unified user-oriented form only after compatibility window stabilization.
      - Keep capability toggles explicit (`can_be_assigned`, approval/manage capabilities, workflow/gamification toggles).
      - Preserve migration-safe defaults and avoid breaking existing options-flow edit paths.
  - [ ] Execute quality gates and release validation commands
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/ -v --tb=line`
  - [ ] Update release documentation and migration notes
    - Files:
      - [README.md](../../README.md)
      - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
      - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
- **Key issues**
  - No release candidate should be cut without successful legacy-upgrade migration-path evidence.

## Testing & validation

- **Planned suites**
  - Migration-focused:
    - `python -m pytest tests/test_migration_hardening.py tests/test_config_flow_use_existing.py -v --tb=line`
  - Workflow/entity role-flag parity:
    - `python -m pytest tests/test_workflow_notifications.py tests/test_badge_target_types.py tests/test_diagnostics.py -v --tb=line`
  - Full gate:
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/ -v --tb=line`
- **Outstanding tests**
  - Full-suite execution (`python -m pytest tests/ -v --tb=line`) reached 99% and was terminated by container with exit 137.
  - Standalone `mypy custom_components/choreops/` fails due parser mismatch against linked HA core syntax in this environment.
  - Focused changed-area validation passed:
    - `./utils/quick_lint.sh --fix`
    - `python -m pytest tests/test_kc_helpers.py -v --tb=line`
    - `python -m pytest tests/test_shadow_link_service.py -v --tb=line`

## Open PR impact assessment (pivot directive)

- **Scope impact**
  - Any open PR that preserves `kids`/`parents` as canonical runtime state is now out of contract.
  - Any open PR that extends shadow-link behavior (`linked_shadow_kid_id`) must be reworked.

- **Required rebase rules**
  1. Rebase onto unified `users` storage and `user_id` naming.
  2. Replace parent-list and shadow-link assumptions with capability-flag filtering.
  3. Use authorization checks keyed by required capability (`can_approve` or `can_manage`), not role bucket membership.

- **Review block criteria**
  - PR introduces or depends on new canonical uses of `DATA_KIDS`/`DATA_PARENTS`.
  - PR introduces new persistence or workflows tied to `linked_shadow_kid_id`.
  - PR authorization logic checks parent membership rather than capability flags.

## Mandatory remediation gate (before Phase 3)

- Phase 3 work is blocked until Phase 1/2 remediation TODOs are completed.
- Authoritative tracker: [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_PHASE12_REMEDIATION.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_PHASE12_REMEDIATION.md)
- Builder must execute the tracker in-order and report validation results before continuation.

## Notes & follow-up

- **Canonical capability model**
  - `can_approve=True`: can approve/disapprove chore and reward workflows.
  - `can_manage=True`: can perform integration management actions (configuration, item CRUD, broader workflow control).
  - `can_be_assigned=True`: can receive chores and participate in points/gamification.
  - A user can hold any combination of capabilities (`Hybrid Home` support).
- **Migration precedence notes (to implement)**
  - For linked shadow cases, user record from `kids` remains authoritative for nested progress/history structures.
  - Parent merge only enriches role/auth/admin fields and must not overwrite complex kid-owned historical subtrees.
  - On merge collision, preserve kid/user record as canonical and remap standalone parent-derived user to a newly generated UUID.
- **Role mapping table (locked contract for implementation)**

| Legacy shape                     | New capability state                                            | Notes                                       |
| -------------------------------- | --------------------------------------------------------------- | ------------------------------------------- |
| Regular kid record               | `can_approve=false`, `can_manage=false`, `can_be_assigned=true` | Default task participant                    |
| Shadow-linked parent + kid       | `can_approve=true`, `can_manage=true`, `can_be_assigned=true`   | Hybrid actor (approver + participant)       |
| Standalone parent record         | `can_approve=true`, `can_manage=true`, `can_be_assigned=false`  | Approver/manager without assignment         |
| Home Assistant global admin user | Runtime override (outside storage flags)                        | HA admin remains an external auth authority |

- **Capability semantics**
  - `can_approve`: approval/disapproval authority for chore/reward workflows.
  - `can_manage`: permission for integration management actions (configuration and lifecycle operations).
  - `can_be_assigned`: eligibility for chore assignment and points/gamification pathways.
  - Capabilities are explicit persisted fields; they are **not** derived from assignment graphs.
  - Identity labels (kid/parent/agent/lead) must never be inferred from a single capability flag.
  - `can_be_assigned=false` does not imply parent identity; capability combinations are valid by design.
  - Authorization helper naming in final architecture must describe capability/action intent, not legacy role buckets.
- **Authority rule (explicit)**
  - Home Assistant runtime admin authority is always an override for approval and management actions.
  - Even when no designated approver exists in storage, an HA admin can approve claims and perform management actions.
  - HA admins can update user capabilities (`can_approve`, `can_manage`) to delegate ongoing approver/manager responsibilities.
  - Assignment/linking relationships do not automatically grant approval authority; delegation occurs by capability update.
- **Execution rule**
  - Favor sequential PR batches by subsystem (types → coordinator → managers → platforms → tests) to keep reviews reliable.
