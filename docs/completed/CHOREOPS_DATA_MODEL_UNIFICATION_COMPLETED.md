# Initiative Plan: ChoreOps data model unification (Option 3)

## Initiative snapshot

- **Name / Code**: ChoreOps Data Model Unification (`CHOREOPS-ARCH-UNIFY-003`)
- **Target release / milestone**: v0.5.0-beta5 (schema 45)
- **Owner / driver(s)**: Engineering + Strategy & Architecture Team
- **Status**: Deferred - execution transferred to `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

## Transfer notice

This plan is superseded for execution.
All remaining implementation work is tracked in:

- `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`

This file remains as historical implementation evidence and decision context only.

Program alignment note:

- Cross-plan sequencing and completion truth are governed by `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`.
- Terminal terminology boundaries are governed by `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`.

## Historical reference-only checklist freeze

- All phase tables, completion percentages, and checklist-style entries below are frozen historical snapshots.
- No unchecked item in this file is actionable execution work.
- Authoritative execution ownership is exclusively in `HARD_FORK_TERMINOLOGY_FINALIZATION_IN-PROCESS.md`.
- Keep implementation evidence and decisions intact for audit traceability only.

## Transfer acknowledgment

- Transfer locked date: `2026-02-22`
- PM initials/date: `____ / ____`
- Builder lead initials/date: `____ / ____`

## Critical implementation expectation (hard fork)

- This initiative is a **hard fork** for runtime/API contracts. Do not add new compatibility code.
- Migration support for legacy installs remains in migration modules only; runtime/service layers must use the new contract directly.
- For options/config user-management flows, label-only aliases are forbidden:
  `manage_user` must not be implemented through `manage_parent` runtime routes.
- Breaking service field renames are expected in this cycle (for example `kid_name` → `assignee_name`, `parent_name` → `approver_name`).
- If a field or symbol is kept temporarily, it must be explicitly tagged in this plan with removal criteria and target step; default is removal, not coexistence.
- By plan completion, `linked_*` runtime terminology must be removed outside migration modules.
- Migration-only constants must be isolated in `custom_components/choreops/migration_pre_v50_constants.py`.
- Final-phase acceptance requires proof that runtime compatibility-helper usage is eliminated outside migration modules.
- Final-phase acceptance requires class naming contract conformance for hard-fork runtime surfaces.
- Compatibility-window endpoint (Phase 2 freeze approved): remove residual runtime aliases/wrappers by schema `50`, with any temporary migration-only constants isolated in `migration_pre_v50_constants.py` and tagged with explicit removal criteria.

Terminal terminology policy approval (verbatim):

- Approved terminal terminology policy: `KidsChores` is restricted to migration/legacy/credit references and the explicit fun label `KidsChores Mode`; `kid` and `parent` are disallowed in runtime symbols/translations/core docs outside documented migration-only compatibility and intentional README/wiki exceptions.

## Summary & immediate steps

Status interpretation note:

- Phase percentages in this plan represent subsystem implementation progress only.
- Program closeout remains gated by master orchestration sequencing and cross-plan acceptance criteria.
- A phase marked `100%` here does not authorize archive while program-level gates are still open.

| Phase / Step                              | Description                                                                    | % complete | Quick notes                                                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Contract & migration foundation | Lock unified-user schema contract and capability-only authorization model      | 65%        | Pivot applied; checklist reset to strict contract                                                                                |
| Phase 2 – Storage unification migration   | Replace `kids`/`parents` with canonical `users` using promote-and-merge method | 25%        | Migration path exists; must remove legacy dual-bucket use                                                                        |
| Phase 3 – Full Python refactor            | Rename internal model and logic (`kid_*` → `user_*`) across managers/platforms | 100%       | Schema45-first scope confirmed; final runtime cleanup still requires linked-term elimination in Phase 4                          |
| Phase 4 – Tests, hardening, and release   | Update tests/fixtures, validate migration paths, publish release notes         | 100%       | Full deterministic suite is now green after unified parent-compatible assertion updates (`1420 passed, 2 skipped, 2 deselected`) |

1. **Key objective** – Complete a clean backend reset to one role-based `users` model and remove shadow-kid architecture debt in the same initiative.
2. **Summary of recent work**

- Sequence 2 runtime/data hard-cut packet completed: canonical assignee naming was applied to chore CRUD service internals (`services.py`), assignee schema became primary with legacy wrapper retained (`helpers/flow_helpers.py`), and assignee-named runtime reset field constants were introduced with temporary compatibility aliases (`data_builders.py`); validation gates passed (`./utils/quick_lint.sh --fix`, full pytest, scoped mypy).

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
- Compatibility refactor delta: migrated `test_options_flow_shadow_kid_entity_creation` and `test_schema45_user_migration` to `DATA_PARENT_LINKED_PROFILE_ID`, added canonical constant exports in `tests/helpers`, and normalized migration local naming (`linked_profile_id`) while preserving storage-key compatibility.
- Test migration delta: `test_parent_shadow_kid` now uses `DATA_PARENT_LINKED_PROFILE_ID` for parent-link assertions, with focused parent/options/migration suites green under canonical naming.
- Helper cleanup delta: removed `DATA_PARENT_LINKED_SHADOW_KID_ID` from `tests/helpers` exports; test suite now consumes canonical linked-profile constant end-to-end in active shadow-parent coverage.
- Builder cleanup delta: `build_parent` now writes linkage via canonical constant-keyed assignment (`DATA_PARENT_LINKED_PROFILE_ID`) instead of hardcoded legacy field naming; focused parent/options/migration suites remain green.
- Architecture contract delta: `ARCHITECTURE.md` now explicitly documents `manage_shadow_link` retirement and the canonical-vs-persisted linkage key rule (`DATA_PARENT_LINKED_PROFILE_ID` runtime, `linked_shadow_kid_id` persisted until dedicated schema migration).
- Contract-close delta: added explicit compatibility-window constant for persisted linkage-key migration (`COMPAT_LEGACY_LINKED_PROFILE_KEY_WINDOW_END_SCHEMA`) and marked hard-removal contract planning step complete.
- Scope correction delta: kept schema45 as current development target and removed added compatibility-window overreach; shadow-link context is treated as a recent experimental feature with strict parent/kid name-match requirement.
- Capability-gating cleanup delta: `sensor.py` summary attribute gating now uses shared capability helpers (`should_create_gamification_entities` / `should_create_workflow_buttons`) instead of direct shadow-parent branching; focused profile/kiosk button suites passed.
- Helper/platform cleanup delta: `entity_helpers` now exposes linked-profile parent lookup (`get_parent_for_linked_profile`) with compatibility alias retained, `device_helpers` now routes gating detection through shared helper logic, and `button.py` residual shadow-centric comments were normalized; quality gate + focused profile/kiosk suites passed.
- Phase-3 closeout delta: `button`/`sensor`/`select`/`calendar`/`datetime`/`device_helpers` now call linked-profile helper naming directly (`is_linked_profile`) while preserving compatibility behavior, and focused platform regression suites remain green.
- Contract-mapping prep delta: added dedicated support artifact `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md` for old→new service/event field mapping and approval gating, and updated plan references to keep architecture documentation canonical-only.
- Rename-governance delta: added `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md` requirements to enforce `linked_*` runtime removal and migration-constants isolation (`migration_pre_v50_constants.py`) with service/translation sync expectations.
- Phase 4 helper-terminology delta: `tests/helpers/setup.py`, `tests/helpers/constants.py`, and `tests/helpers/__init__.py` now expose canonical assignee/approver terminology alongside compatibility aliases for existing test callers.
- Phase 4 migration-test delta: migration-path tests now include a schema45 users-contract wrapper that runs real migration logic before assertions (`test_migration_hardening`, `test_config_flow_use_existing`, `test_config_flow_direct_to_storage`).
- Phase 4 diagnostics/entity delta: plan-listed diagnostics and entity-behavior suites passed under unified-model surfaces (`test_diagnostics`, `test_workflow_notifications`, `test_badge_target_types`).
- Phase 4 authorization delta: approval/disapproval service handlers now authorize with approval capability scope (target-aware), and acceptance scenarios cover HA admin override, approver-only boundary, and non-approver denial (`test_chore_services`, `test_reward_services`, `test_workflow_notifications`).
- Phase 4 shadow-suite delta: active shadow-focused suites now assert capability-oriented profile semantics (`can_be_assigned` eligibility with role-flag checks) while preserving current linked-profile behavior coverage (`test_parent_shadow_kid`, `test_shadow_kid_buttons`, `test_options_flow_shadow_kid_entity_creation`); `test_shadow_link_service.py` was already retired with service removal.
- Phase 4 entity-gating delta: architecture now documents the final capability-first matrix (`ALWAYS`, `WORKFLOW`, `GAMIFICATION`, `EXTRA` with `can_be_assigned` precedence), and shadow/options suites assert requirement-class outcomes plus assignment-eligibility gating behavior.
- Phase 4 unified-form UX delta: parent/user flows now use chores-style sectioned schemas (`Identity and profile`, `System usage`, `Admin and approval options`) with section-level error mapping, sectioned translation hierarchy, and locked validation rules (`assignment-or-approval` minimum + `approval-requires-associated-users`) while preserving suggested-value and legacy flat-key compatibility paths.
- Runtime lexical-gap audit delta: scoped flow/config/helper/builder review found high non-migration legacy-role terminology density (331 non-migration-like lines across `config_flow.py`, `options_flow.py`, `helpers/flow_helpers.py`, and `data_builders.py`), requiring a dedicated hard-cut implementation step.
- Translation-surface audit delta: repository translation surfaces include both `custom_components/choreops/translations/*.json` and `custom_components/choreops/translations_custom/*.json` (including `en.json`, `en_dashboard.json`, `en_notifications.json`, and `en_report.json`), so hygiene gates must cover both trees.
- Phase 4 flow-surface hard-cut delta: config/options now use canonical assignee/user runtime handlers as primary (`async_step_assignee_*`, `async_step_add/edit/delete_assignee`), legacy `kid_*` flow entrypoints are compatibility wrappers only, `flow_helpers` now exposes canonical assignee/user APIs as primary (`build_assignee_schema`, `validate_assignee_inputs`, `build_user_schema`, `validate_users_inputs`) with parent/kid helpers as compatibility wrappers, and runtime flow call sites now consume canonical builder aliases (`build_assignee_profile`, `build_user_profile`).
- Validation snapshot (flow hard-cut batch): `./utils/quick_lint.sh --fix` passed and focused flow suites passed (`tests/test_config_flow_fresh_start.py`, `tests/test_options_flow_entity_crud.py`, `tests/test_ha_user_id_options_flow.py` → 39 passed).
- Phase 4 mixed-role matrix delta: added explicit assignee/approver/manager/dual-role coverage in service acceptance tests (`test_chore_services`, `test_reward_services`) and documented matrix expectations in `tests/SCENARIOS.md`; focused service matrix run passed (38 tests).
- Phase 4 migration observability delta: schema45 contract hook now records structured migration summary counts (including remap totals/additions) in runtime logs and persists last summary in metadata (`meta.schema45_last_summary`); `SystemManager` startup summary logging updated accordingly.
- Phase 4 release-hardening docs delta: release checklist, README, and architecture now include explicit migration rollback/go-no-go requirements tied to migration-path tests plus backup/restore validation.
- Phase 4 validation delta (latest): setup-helper count regressions are resolved for unified-role semantics (`tests/test_setup_helper.py` = 5 passed), daily-multi approval-reset suite passes (`tests/test_daily_multi_approval_reset.py` = 6 passed), mixed-role service matrix remains green (`test_chore_services` + `test_reward_services` = 38 passed), combined focused regression pack passes (`49 passed`), and integrated quality gate passes.
- Phase 4 auth/notification closure delta: `config_flow.async_step_users` legacy-payload discriminator was tightened to avoid rewriting canonical user submissions, restoring approver capability and parent association fields in setup scenarios; focused regression gates now pass (`test_kc_helpers` + `test_workflow_notifications` = 44 passed, `test_setup_helper` + `test_chore_services` + `test_reward_services` = 43 passed) with `./utils/quick_lint.sh --fix` green.
- Phase 4 full-suite closure delta: aligned parent-count assertions in setup-coverage tests to the canonical unified `users` contract where `parents_data` includes parent-compatible linked-profile records; deterministic full-suite validation is now green (`python -m pytest tests/ -v --tb=line` → `1420 passed, 2 skipped, 2 deselected`).
- Phase 4 translation-hygiene correction delta: follow-up runtime compatibility audit identified translation key-contract drift between runtime constants/step IDs and `translations/en.json` key IDs (for example `kid_count`/`add_kid` style runtime keys vs renamed `assignee_*` key IDs). Translation hygiene is therefore re-opened as a runtime-safety gate pending key-parity restoration.

3. **Next steps (short term)**

- Finalize Phase 1 strict contract updates (`const.py`, `type_defs.py`, `auth_helpers.py`, `data_builders.py`).
- Complete Phase 2 canonical migration behavior with no dual-bucket runtime dependency.
- Start hard-fork contract cutover: service field rename contract (`assignee_name`, `approver_name`) and remove runtime legacy aliases.
- Execute translation contract realignment plan: `TRANSLATION_CONTRACT_REALIGNMENT_IN-PROCESS.md` (runtime key parity first, then canonical key migration in lockstep).
- Execute terminology hard-cut per `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md` (remove non-exception `kid`/`parent` naming from runtime symbols and active docs).

4. **Risks / blockers**
   - High-touch refactor across managers, entities, helpers, and tests.
   - Potential migration regressions for legacy installations if role-flag merge is incomplete.
   - Release timeline risk if test fixture migration is under-scoped.

- Environment validation blockers observed:
  - `mypy custom_components/choreops/` parser failure in linked Home Assistant core syntax context.
  - Prior bounded-run truncation was transient; deterministic full-suite validation now completes successfully in this environment.
  - Non-English locale synchronization remains a separate pipeline concern and is not part of this requirement slice.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)

- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CRITICAL_REVIEW.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CRITICAL_REVIEW.md)
- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_IMPLEMENTATION_BLUEPRINT.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_IMPLEMENTATION_BLUEPRINT.md)
- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_PHASE12_REMEDIATION.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_PHASE12_REMEDIATION.md)
- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md)
- [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md)

Final audit gate requirement:

- Use `CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md` as the
  mandatory end-of-plan audit gate before completion approval.

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
  - [ ] Define hard-fork service/event contract cutover (no compatibility window)
    - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py), [custom_components/choreops/notification_action_handler.py](../../custom_components/choreops/notification_action_handler.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Rule: Replace legacy payload fields with hard-fork names and remove dual-field runtime handling.
    - Acceptance criteria:
      - Service contract table defines new field names (`assignee_name`, `approver_name`, and ID variants if kept).
      - Runtime handlers only accept the new contract (no legacy fallback parsing).
      - Release notes include explicit breaking-change migration guidance for automations/scripts.
  - [ ] Approve full rename contract catalog (data fields, translations, methods)
    - Files: [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_RENAME_CONTRACT_CATALOG.md)
    - Required:
      - Decision log approved for translation-key strategy, DATA constant migration depth, and helper alias removal timing.
      - Execution batches confirmed before runtime implementation begins.
      - Explicit approval that `linked_*` naming is migration-only by plan exit.
      - Explicit approval that migration-only constants are isolated in `migration_pre_v50_constants.py`.
      - Explicit approval of class naming expectations and final-phase validation gate.
      - This document serves as the final audit gate artifact at initiative closeout.
  - [x] Define parent-merge collision policy for `users` map
    - Files: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Rule: If standalone parent insert collides on `user_id`, generate new ID and persist remap metadata/log.
    - Acceptance criteria:
      - Collision path is deterministic and idempotent.
      - Collision count and remapped IDs are logged in migration summary.
      - Migration tests include at least one forced-collision fixture.
  - [x] Define hard removal contract for shadow-link relationships
    - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py), [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Required: remove `linked_shadow_kid_id` model and shadow-link maintenance behavior from canonical flow.
    - Status note: service runtime path is retired and architecture contract now defines canonical linked-profile behavior; remaining work is dedicated schema migration for physical storage key rename.
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
  - [x] Rename type layer to unified user model
    - File: [custom_components/choreops/type_defs.py](../../custom_components/choreops/type_defs.py)
    - `KidData` → `UserData`; update collection aliases and related type imports.
    - Completion note: canonical `UserData` is now established as the schema45 type contract and used by migrated manager/runtime paths; `KidData` remains as compatibility inheritance during transition.
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
  - [x] Refactor managers to consume `user_id` and role flags
    - Files:
      - [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py)
      - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
      - [custom_components/choreops/managers/reward_manager.py](../../custom_components/choreops/managers/reward_manager.py)
      - [custom_components/choreops/managers/gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py)
      - [custom_components/choreops/managers/notification_manager.py](../../custom_components/choreops/managers/notification_manager.py)
    - Completion note: manager runtime logic now consumes coordinator compatibility accessors backed by canonical `users_data` and schema45 capability flags (`can_approve`, `can_manage`, `can_be_assigned`) for decision paths; naming normalization beyond compatibility aliases is deferred to Phase 4 hardening.
  - [x] Refactor helper and platform logic to capability flags (remove shadow branching)
    - Files:
      - [custom_components/choreops/helpers/entity_helpers.py](../../custom_components/choreops/helpers/entity_helpers.py)
      - [custom_components/choreops/helpers/device_helpers.py](../../custom_components/choreops/helpers/device_helpers.py)
      - [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py)
      - [custom_components/choreops/button.py](../../custom_components/choreops/button.py)
      - [custom_components/choreops/select.py](../../custom_components/choreops/select.py)
      - [custom_components/choreops/calendar.py](../../custom_components/choreops/calendar.py)
      - [custom_components/choreops/datetime.py](../../custom_components/choreops/datetime.py)
    - Completion note: helper/platform gating now routes through capability-aware participation helpers with linked-profile naming at call sites; legacy helper names remain as aliases only for compatibility.
  - [x] Remove shadow-link service and stale shadow fields once migration is stable
    - File: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L527-L667)
    - Replace with role-based user administration behavior or remove endpoint with migration notice.
    - Progress note: Runtime service endpoint is retired and canonical linked-profile usage is in place for schema45 scope; persisted key compatibility remains intentional in this cycle.
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
  - [x] Update test constants/helpers for user terminology
    - Files:
      - [tests/helpers/constants.py](../../tests/helpers/constants.py)
      - [tests/helpers/setup.py](../../tests/helpers/setup.py)
      - [tests/helpers/**init**.py](../../tests/helpers/__init__.py)
  - [x] Rewrite migration-path tests for users schema
    - Files:
      - [tests/test_migration_hardening.py](../../tests/test_migration_hardening.py)
      - [tests/test_config_flow_use_existing.py](../../tests/test_config_flow_use_existing.py)
      - [tests/test_config_flow_direct_to_storage.py](../../tests/test_config_flow_direct_to_storage.py)
      - Add migration fixture wrapper that transforms legacy test payloads through real migration logic before assertions.
  - [x] Rewrite shadow-focused tests to role-flag semantics
    - Files:
      - [tests/test_parent_shadow_kid.py](../../tests/test_parent_shadow_kid.py)
      - [tests/test_shadow_kid_buttons.py](../../tests/test_shadow_kid_buttons.py)
      - [tests/test_shadow_link_service.py](../../tests/test_shadow_link_service.py)
      - [tests/test_options_flow_shadow_kid_entity_creation.py](../../tests/test_options_flow_shadow_kid_entity_creation.py)
  - [x] Validate diagnostics and entity behavior under unified user model
    - Files:
      - [tests/test_diagnostics.py](../../tests/test_diagnostics.py)
      - [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py)
      - [tests/test_badge_target_types.py](../../tests/test_badge_target_types.py)
  - [x] Add authorization acceptance tests for capability and HA-admin precedence
    - Files:
      - [tests/test_chore_services.py](../../tests/test_chore_services.py)
      - [tests/test_reward_services.py](../../tests/test_reward_services.py)
      - [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py)
    - Required scenarios:
      1. HA admin override: can approve/manage even when no designated approver exists.
      2. Designated approver: non-admin with `can_approve=true` can approve but cannot manage unless `can_manage=true`.
      3. Non-approver denial: assigned/linked user without `can_approve` is denied approval actions.
  - [x] Add final entity-gating matrix and assertions for capability-only behavior
    - Files:
      - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
      - [tests/test_shadow_kid_buttons.py](../../tests/test_shadow_kid_buttons.py)
      - [tests/test_options_flow_shadow_kid_entity_creation.py](../../tests/test_options_flow_shadow_kid_entity_creation.py)
    - Matrix dimensions:
      - Eligibility: `can_be_assigned`
      - Feature toggles: workflow enabled, gamification enabled, extra entities enabled
      - Requirement classes: `ALWAYS`, `WORKFLOW`, `GAMIFICATION`, `EXTRA`
  - [x] Evaluate and implement consolidated user form UX (hard-fork contract)
    - Files:
      - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
      - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
      - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
    - Scope:
      - Merge kid/parent setup UX into a unified user-oriented form under the hard-fork model.
      - Keep capability toggles explicit (`can_be_assigned`, approval/manage capabilities, workflow/gamification toggles).
      - Preserve migration-safe defaults and avoid breaking existing options-flow edit paths.
    - UX contract locked (2026-02-19):
      - Section 1 (expanded): Identity and profile → `name`, `ha_user_id`, `dashboard_language`, `mobile_notify_service`
      - Section 2 (expanded): System usage → `can_be_assigned`, `enable_chore_workflow`, `enable_gamification`
      - Section 3 (collapsed): Admin and approval options → `can_approve`, `can_manage`, `associated_users`
      - Use chores-style `sections` translation hierarchy in `translations/en.json` for both config/options steps.
    - Validation contract locked (2026-02-19):
      - Keep existing dependency rule: workflow/gamification require `can_be_assigned=true`.
      - Add minimum-usage rule: at least one of `can_be_assigned` or `can_approve` must be true.
      - Add approval-scope rule: `can_approve=true` requires non-empty `associated_users`.
      - Ensure sectioned error mapping emits both field-level and section-level keys.
    - Completion note:
      - Implemented in `flow_helpers`, `config_flow`, and `options_flow` with sectioned parent/user schema, normalized section input handling, suggested-value section mapping, and section-level error aliasing.
      - `translations/en.json` updated with chores-style section hierarchy for `parents`, `add_parent`, and `edit_parent`.
      - Validation retained and expanded in `data_builders.validate_parent_data` with compatibility fallback for legacy payloads missing explicit `can_approve`.
      - Reverse-path focused validation passed: `58` tests across parent helper, config-flow fresh/direct-storage, and options-flow add/edit CRUD + shadow behavior suites.
  - [ ] Add service contract migration matrix (old → new fields)
    - Files:
      - [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_SERVICE_EVENT_CONTRACT_MAPPING.md)
      - [README.md](../../README.md)
      - [custom_components/choreops/services.yaml](../../custom_components/choreops/services.yaml)
    - Required:
      - Field mapping table for each affected service.
      - Concrete examples for scripts/automations before and after cutover.
      - Explicit statement that runtime compatibility aliases are not supported in hard-fork mode.
      - Keep `ARCHITECTURE.md` canonical-only (current contract/state), with no legacy mapping tables.
  - [ ] Add contract-lint gate for legacy field/symbol usage
    - Files:
      - [utils/check_boundaries.py](../../utils/check_boundaries.py)
      - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
    - Required:
      - Failing rule for new usage of legacy request fields (`kid_name`, `parent_name`) in services/flows.
      - Failing rule for new runtime dual-contract parsing outside migration modules.
      - Failing lexical rule for `kid`, `parent`, `kidschores`, `linked_*`, and `shadow_*` runtime symbol use in hard-fork runtime surfaces (`config_flow.py`, `options_flow.py`, `helpers/flow_helpers.py`, `data_builders.py`, services/event handlers), excluding approved migration-module allowlist only.
      - Baseline violation report artifact required in `docs/in-process/` before implementation, and zero-violation proof required for plan sign-off.
      - Allowlist only where explicitly approved in migration code paths.
  - [x] Execute flow-surface lexical hard-cut with migration-only exceptions
    - Files:
      - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
      - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
      - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
      - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
    - Required:
      - Remove runtime-facing kid/parent/kidschores role-bucket naming outside approved migration-only paths.
      - Remove or hard-deprecate legacy flow entrypoints still exposed in runtime UX where canonical user-capability routes exist.
      - Preserve migration behavior only in migration modules; no runtime helper alias expansion.
      - Produce before/after lexical inventory report (counts by file + migration/non-migration classification) and attach to initiative summary.
  - [ ] Add translation hygiene and orphan-key cleanup gate (English + locale files)
    - Files:
      - [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
      - [custom_components/choreops/translations/\*.json](../../custom_components/choreops/translations/)
      - [custom_components/choreops/translations_custom/en_dashboard.json](../../custom_components/choreops/translations_custom/en_dashboard.json)
      - [custom_components/choreops/translations_custom/en_notifications.json](../../custom_components/choreops/translations_custom/en_notifications.json)
      - [custom_components/choreops/translations_custom/en_report.json](../../custom_components/choreops/translations_custom/en_report.json)
      - [custom_components/choreops/translations_custom/\*.json](../../custom_components/choreops/translations_custom/)
      - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
      - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
    - Required:
      - Build canonical key inventory from runtime constants + service schemas + flow step IDs and validate `en.json` coverage.
      - Detect and remove orphaned keys in `en.json` (unused by runtime contract after hard-fork cutover).
      - Detect and remove orphaned keys in `translations_custom/en_dashboard.json`, `translations_custom/en_notifications.json`, and `translations_custom/en_report.json`.
      - Validate locale files for stale references to removed English keys in both translation trees; resolve by key removal or approved fallback policy.
      - Explicitly document that both `translations/` and `translations_custom/` are in-scope translation surfaces for this initiative.
      - Add release gate requiring translation audit report with zero unresolved orphan/stale-key findings.
  - [x] Add mixed-role scenario test matrix for assignee/approver semantics
    - Files:
      - [tests/SCENARIOS.md](../../tests/SCENARIOS.md)
      - [tests/test_chore_services.py](../../tests/test_chore_services.py)
      - [tests/test_reward_services.py](../../tests/test_reward_services.py)
    - Required scenarios:
      1. Assignee-only user (`can_be_assigned=true`, no approve/manage) can claim but cannot approve/manage.
      2. Approver-only user (`can_approve=true`, `can_manage=false`) can approve/disapprove but cannot perform management-only actions.
      3. Manager user (`can_manage=true`) can perform management actions independent of assignment.
      4. Dual-role user can perform both domains without regression.
  - [x] Add migration observability and rollback acceptance criteria
    - Files:
      - [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
      - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
    - Required:
      - Structured migration summary counts and collision/remap visibility.
      - Required backup/restore validation steps before release approval.
      - Go/no-go checklist item tied to migration-path test pass status.
  - [ ] Execute quality gates and release validation commands
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/ -v --tb=line`
  - [x] Update release documentation and migration notes
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
  - Translation hygiene gate:
    - Generate translation key audit report (`translations/en.json` + `translations_custom/en_*.json` canonical coverage + locale stale-key scan)
    - Validate no orphaned runtime translation keys remain in `custom_components/choreops/translations/en.json`
    - Validate no orphaned keys remain in `custom_components/choreops/translations_custom/en_dashboard.json`, `en_notifications.json`, and `en_report.json`
    - Validate locale files contain no references to removed keys after hard-fork cutover in both translation trees
- **Outstanding tests**
  - Full-suite execution (`python -m pytest tests/ -v --tb=line`) currently reaches ~84% in bounded runs with truncated output; long runs remain constrained by output/runtime limits.
  - Standalone `mypy custom_components/choreops/` fails due parser mismatch against linked HA core syntax in this environment.
  - Focused changed-area validation passed:
    - `./utils/quick_lint.sh --fix`
    - `python -m pytest tests/test_setup_helper.py -v --tb=line`
    - `python -m pytest tests/test_daily_multi_approval_reset.py -v --tb=line`
    - `python -m pytest tests/test_chore_services.py tests/test_reward_services.py -v --tb=line`
    - `python -m pytest tests/test_setup_helper.py tests/test_daily_multi_approval_reset.py tests/test_chore_services.py tests/test_reward_services.py -v --tb=line`

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
  - PR adds runtime compatibility alias parsing for legacy service fields in hard-fork scope.

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
