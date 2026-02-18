# Initiative Plan: ChoreOps data model unification (Option 3)

## Initiative snapshot

- **Name / Code**: ChoreOps Data Model Unification (`CHOREOPS-ARCH-UNIFY-003`)
- **Target release / milestone**: v0.5.x hard-fork execution window (Option 3 track)
- **Owner / driver(s)**: Engineering + Strategy & Architecture Team
- **Status**: Not started (approved direction: Option 3)

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Contract & migration foundation | Lock terminology, schema contract, and migration entry points | 0% | Mandatory before broad refactor |
| Phase 2 – Storage unification migration | Replace `kids`/`parents` with `users` using kid-first merge algorithm | 0% | Startup migration is idempotent and backup-safe |
| Phase 3 – Full Python refactor | Rename internal model and logic (`kid_*` → `user_*`) across managers/platforms | 0% | Includes shadow-link removal and role-flag logic |
| Phase 4 – Tests, hardening, and release | Update tests/fixtures, validate migration paths, publish release notes | 0% | No release until migration-path tests are green |

1. **Key objective** – Complete a clean backend reset to one role-based `users` model and remove shadow-kid architecture debt in the same initiative.
2. **Summary of recent work**
   - Option comparison completed; Option 3 selected as architecture target.
   - Migration strategy chosen: **kid-first container rename + parent merge**.
  - Terminology target confirmed: `users`, `user_id`, `user_data`, plus capability flags (`can_approve`, `can_manage`, `can_be_assigned`).
3. **Next steps (short term)**
   - Implement schema/version constants and migration hook scaffolding.
   - Implement startup migration algorithm with idempotency and backup guard.
   - Start type/model rename sweep (`KidData` → `UserData`) in managed file batches.
4. **Risks / blockers**
   - High-touch refactor across managers, entities, helpers, and tests.
   - Potential migration regressions for legacy installations if role-flag merge is incomplete.
   - Release timeline risk if test fixture migration is under-scoped.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
  - [docs/in-process/CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CRITICAL_REVIEW.md](CHOREOPS_DATA_MODEL_UNIFICATION_SUP_CRITICAL_REVIEW.md)
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
  - [ ] Define and add new storage/model constants for unified users
    - File: [custom_components/choreops/const.py](../../custom_components/choreops/const.py)
    - Add keys and fields for `DATA_USERS`, `DATA_USER_INTERNAL_ID`, `DATA_USER_CAN_APPROVE`, `DATA_USER_CAN_MANAGE`, `DATA_USER_CAN_BE_ASSIGNED`.
  - [ ] Define next schema version and migration semantic note
    - File: [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L331-L355)
    - Add explicit schema bump and comment for kid/parent → users unification.
  - [ ] Add migration hook entry point in integrity pipeline
    - File: [custom_components/choreops/managers/system_manager.py](../../custom_components/choreops/managers/system_manager.py#L190-L236)
    - Ensure migration executes before `DATA_READY` emission.
  - [ ] Add architecture contract notes for role flags
    - File: [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Document `can_approve`, `can_manage`, and `can_be_assigned` as the canonical role model.
    - [ ] Define authorization matrix contract and explicit non-derivation rules
      - Files: [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
      - Rule: `can_approve`/`can_manage` are explicit capabilities, not inferred from assignment relationships.
  - [ ] Define deprecation contract for shadow-link services and fields
    - Files: [custom_components/choreops/services.py](../../custom_components/choreops/services.py), [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Mark behavior transition (deprecated then removed in this initiative).
- **Key issues**
  - Schema and constant names must be final before mass renaming begins.

### Phase 2 – Storage unification migration

- **Goal**: Perform startup migration from legacy split dictionaries to unified `users` without copying kid payloads.
- **Steps / detailed work items**
  - [ ] Implement kid-first rename container algorithm in migration module
    - File: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
    - Algorithm:
      1. `data['users'] = data.pop('kids')`
      2. Enrich all users with defaults: `can_approve=False`, `can_manage=False`, `can_be_assigned=True`
      3. Merge `parents` into `users`:
         - linked shadow parent updates existing user record (`can_approve=True`, `can_manage=True`, auth updates)
         - standalone parent creates new user (`can_approve=True`, `can_manage=True`, `can_be_assigned=False`)
  - [ ] Guarantee idempotency and re-run safety
    - File: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
    - Re-running migration should not duplicate users or corrupt role flags.
  - [ ] Keep startup backup protection before migration writes
    - File: [custom_components/choreops/__init__.py](../../custom_components/choreops/__init__.py#L122-L154)
    - Ensure recovery backup exists before persistence of transformed schema.
  - [ ] Update default store shape to canonical `users`
    - File: [custom_components/choreops/store.py](../../custom_components/choreops/store.py#L45-L72)
    - New installs should initialize with `users` only (no `kids`/`parents` primary buckets).
  - [ ] Add migration summary logs and counts for observability
    - Files: [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py), [custom_components/choreops/managers/system_manager.py](../../custom_components/choreops/managers/system_manager.py)
    - Log counts: users migrated, linked-parent merges, standalone parent creations.
- **Key issues**
  - Parent-to-user merge needs deterministic precedence rules for auth and naming fields.

### Phase 3 – Full Python refactor (`kid_*` → `user_*`)

- **Goal**: Align all internal symbols, TypedDicts, managers, and platform logic to the unified user model.
- **Steps / detailed work items**
  - [ ] Rename type layer to unified user model
    - File: [custom_components/choreops/type_defs.py](../../custom_components/choreops/type_defs.py)
    - `KidData` → `UserData`; update collection aliases and related type imports.
  - [ ] Refactor coordinator accessors and field names
    - File: [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - Replace `kids_data` / `parents_data` pathways with unified user accessors and role-filter helpers where needed.
  - [ ] Refactor managers to consume `user_id` and role flags
    - Files:
      - [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py)
      - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
      - [custom_components/choreops/managers/reward_manager.py](../../custom_components/choreops/managers/reward_manager.py)
      - [custom_components/choreops/managers/gamification_manager.py](../../custom_components/choreops/managers/gamification_manager.py)
      - [custom_components/choreops/managers/notification_manager.py](../../custom_components/choreops/managers/notification_manager.py)
  - [ ] Refactor helper and platform logic to capability flags (remove shadow branching)
    - Files:
      - [custom_components/choreops/helpers/entity_helpers.py](../../custom_components/choreops/helpers/entity_helpers.py)
      - [custom_components/choreops/helpers/device_helpers.py](../../custom_components/choreops/helpers/device_helpers.py)
      - [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py)
      - [custom_components/choreops/button.py](../../custom_components/choreops/button.py)
      - [custom_components/choreops/select.py](../../custom_components/choreops/select.py)
      - [custom_components/choreops/calendar.py](../../custom_components/choreops/calendar.py)
      - [custom_components/choreops/datetime.py](../../custom_components/choreops/datetime.py)
  - [ ] Remove shadow-link service and stale shadow fields once migration is stable
    - File: [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L527-L667)
    - Replace with role-based user administration behavior or remove endpoint with migration notice.
  - [ ] Rename flow inputs/outputs and builders to user-oriented naming
    - Files:
      - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
      - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
      - [custom_components/choreops/data_builders.py](../../custom_components/choreops/data_builders.py)
      - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
- **Key issues**
  - This phase intentionally touches many files; execute in narrow, reviewable PR batches to limit regression scope.

### Phase 4 – Tests, hardening, and release

- **Goal**: Prove migration safety and behavioral parity for user workflows before release.
- **Steps / detailed work items**
  - [ ] Update test constants/helpers for user terminology
    - Files:
      - [tests/helpers/constants.py](../../tests/helpers/constants.py)
      - [tests/helpers/setup.py](../../tests/helpers/setup.py)
      - [tests/helpers/__init__.py](../../tests/helpers/__init__.py)
  - [ ] Rewrite migration-path tests for users schema
    - Files:
      - [tests/test_migration_hardening.py](../../tests/test_migration_hardening.py)
      - [tests/test_config_flow_use_existing.py](../../tests/test_config_flow_use_existing.py)
      - [tests/test_config_flow_direct_to_storage.py](../../tests/test_config_flow_direct_to_storage.py)
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
  - Not run in this planning update.

## Notes & follow-up

- **Canonical capability model**
  - `can_approve=True`: can approve/disapprove chore and reward workflows.
  - `can_manage=True`: can perform integration management actions (configuration, item CRUD, broader workflow control).
  - `can_be_assigned=True`: can receive chores and participate in points/gamification.
  - A user can hold any combination of capabilities (`Hybrid Home` support).
- **Migration precedence notes (to implement)**
  - For linked shadow cases, user record from `kids` remains authoritative for nested progress/history structures.
  - Parent merge only enriches role/auth/admin fields and must not overwrite complex kid-owned historical subtrees.
- **Role mapping table (locked contract for implementation)**

| Legacy shape | New capability state | Notes |
| --- | --- | --- |
| Regular kid record | `can_approve=false`, `can_manage=false`, `can_be_assigned=true` | Default task participant |
| Shadow-linked parent + kid | `can_approve=true`, `can_manage=true`, `can_be_assigned=true` | Hybrid actor (approver + participant) |
| Standalone parent record | `can_approve=true`, `can_manage=true`, `can_be_assigned=false` | Approver/manager without assignment |
| Home Assistant global admin user | Runtime override (outside storage flags) | HA admin remains an external auth authority |

- **Capability semantics**
  - `can_approve`: approval/disapproval authority for chore/reward workflows.
  - `can_manage`: permission for integration management actions (configuration and lifecycle operations).
  - `can_be_assigned`: eligibility for chore assignment and points/gamification pathways.
  - Capabilities are explicit persisted fields; they are **not** derived from assignment graphs.
- **Execution rule**
  - Favor sequential PR batches by subsystem (types → coordinator → managers → platforms → tests) to keep reviews reliable.
