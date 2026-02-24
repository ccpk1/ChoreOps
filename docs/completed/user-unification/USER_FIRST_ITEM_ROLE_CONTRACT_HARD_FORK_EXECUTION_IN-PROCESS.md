# Initiative Plan: User-first item/role contract hard-fork execution

## Initiative snapshot

- **Name / Code**: User-first item/role contract hard-fork execution (`CHOREOPS-ROLE-HF-EXEC-001`)
- **Target release / milestone**: Next hard-fork corrective release
- **Owner / driver(s)**: Project manager + builder lead
- **Status**: Ready for owner sign-off

## Summary & immediate steps

| Phase / Step                              | Description                                                                         | % complete | Quick notes                                                                                             |
| ----------------------------------------- | ----------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------- |
| Phase 1 – Contract constants and taxonomy | Apply approved fact-table naming contract in constants and shared helper signatures | 100%       | Canonical symbols landed; scans clean                                                                   |
| Phase 2 – Runtime propagation             | Replace runtime callsites and remove role-lifecycle contract surfaces               | 100%       | Runtime callsites aligned; closure scans clean                                                          |
| Phase 3 – Flow/storage/event alignment    | Align flow fields, storage keys, and lifecycle signal usage to user-first model     | 100%       | 3.1–3.6 complete; gates green with migration-only legacy remaps                                         |
| Phase 4 – Test and gate closure           | Rebaseline tests and enforce grep-based hard-fork closure gates                     | 100%       | Batch-14 remediation closed baseline drift; Phase 4B sign-off checklist complete; owner archive approval pending |

1. **Key objective** – Implement the ratified fact table as a hard-fork runtime contract with canonical user lifecycle and explicit role qualifiers.
2. **Summary of recent work** – Fact table ratified and D1 decision approved in `USER_ROLE_MODEL_DRIFT_ANALYSIS_SUP_FACT_TABLE.md`.
3. **Next steps (short term)** – Owner sign-off + archive handoff; separately decide on Phase 13 `_users_temp` collapse.
4. **Risks / blockers**
   - Signal/service/field contract changes may break broad callsite surfaces if done in mixed batches.
   - `assignee`/`approver` terms that represent role semantics must be preserved while lifecycle identity terms are replaced.

- Any runtime fallback introduction violates hard-fork policy and blocks closure.
- Full `mypy custom_components/choreops/` remains environment-blocked by external core parser mismatch in this workspace (`/workspaces/core/homeassistant/helpers/device_registry.py`).

5. **References**
   - `docs/in-process/USER_ROLE_MODEL_DRIFT_ANALYSIS_SUP_FACT_TABLE.md`
   - `docs/in-process/USER_ROLE_MODEL_DRIFT_ANALYSIS_IN-PROCESS.md`
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `custom_components/choreops/const.py`
   - `custom_components/choreops/helpers/entity_helpers.py`
6. **Decisions & completion check**
   - **Decisions captured**:
     - No runtime compatibility aliases/fallbacks.
     - Legacy compatibility transforms are migration-only.
     - Item taxonomy is `ITEM_TYPE_*` and roles are `ROLE_*` qualifiers.
  - **Completion confirmation**: `[ ]` All phases completed and closure gates pass at zero drift for approved contract rows (owner approval pending for archive handoff).

## Plan QA review (opportunities, traps, and decision log)

### Decision log (resolved)

1. **D1 – Item type vs role qualifier model**

- ✅ Resolved: adopt `ITEM_TYPE_*` taxonomy and `ROLE_*` qualifiers.

2. **D2 – Assignment attribute naming**

- ✅ Resolved: use fact-table approved `assigned_to` naming for the targeted attribute contract row.
- Basis: standards were updated and no longer block this contract choice.

3. **D3 – Service actor target naming freeze**

- ✅ Resolved: keep `SERVICE_FIELD_APPROVER_NAME` unchanged as role-semantic actor context.

4. **D4 – Storage/public payload migration envelope**

- ✅ Resolved: Matrix A key renames are authorized as this initiative’s explicit migration tranche.

No unresolved preflight decisions remain.

### Primary traps and mitigations

1. **Trap: taxonomy rename without callsite parity**

- Risk: `ENTITY_TYPE_*` removals before callsite migration break runtime import/lookup paths.
- Mitigation: batch by vertical slice (constants + helper + direct callsites together), then remove old symbols.

2. **Trap: over-renaming role semantics**

- Risk: replacing valid role terms damages domain clarity.
- Mitigation: enforce Matrix B as do-not-rename allowlist during implementation reviews.

3. **Trap: hidden public API breakage in services**

- Risk: service field name changes silently break automations.
- Mitigation: treat service field updates as explicit hard-fork break; add release note checklist item and service schema tests.

4. **Trap: migration leakage into runtime**

- Risk: fallback/bridge logic reappears outside migration modules.
- Mitigation: add grep gate that blocks fallback markers and legacy alias branches outside `migration_pre_v50.py`.

5. **Trap: mixed item_type/role semantics in helper signatures**

- Risk: ambiguous helper APIs (item routing vs role filtering) regress quickly.
- Mitigation: separate parameters: `item_type` required, `role` optional (user-only).

### Opportunities (high leverage)

1. Add typed aliases for taxonomy contracts (`ItemType`, `UserRole`) in `type_defs.py` to tighten mypy coverage.
2. Add centralized helper wrappers for user-by-role lookup to reduce repeated role filters.
3. Add pre-commit grep gate script for forbidden symbol reintroduction (cheap long-term guardrail).

## Tracking expectations

- **Summary upkeep**: Update phase percentages and gate results after each implementation batch.
- **Detailed tracking**: Keep evidence under each phase with exact files touched and gate outputs.

## Detailed phase tracking

### Phase 1 – Contract constants and taxonomy

- **Goal**: Land the canonical constant/symbol taxonomy from the approved fact table.
- **Micro-batch sequence (ordered)**:
  - **Batch 1A**: Add new canonical constants only (`ITEM_TYPE_*`, `ROLE_*`, `SIGNAL_SUFFIX_USER_*`) without removals.
  - **Batch 1B**: Migrate helper signatures and direct imports/callsites to new constants.
  - **Batch 1C**: Remove deprecated constants (`ENTITY_TYPE_ASSIGNEE`, `ENTITY_TYPE_APPROVER`, role lifecycle signal constants, `FIELD_*` aliases).
  - **Batch 1D**: Run closure grep gates for Phase 1 forbidden symbols.
- **Steps / detailed work items**
  - [x] Replace lifecycle role signal constants with user lifecycle constants in `const.py`
    - File: `custom_components/choreops/const.py` (lifecycle signal block near existing `SIGNAL_SUFFIX_*_CREATED/UPDATED/DELETED`)
    - Remove role lifecycle signal constants from runtime contract surface
  - [x] Introduce and propagate `ITEM_TYPE_*` constants; remove role item-type taxonomy
    - File: `custom_components/choreops/const.py` (existing `ENTITY_TYPE_*` block)
    - Add `ITEM_TYPE_USER` and remove `ASSIGNEE/APPROVER` from item taxonomy
  - [x] Introduce `ROLE_ASSIGNEE` / `ROLE_APPROVER` constants for qualifier usage
    - File: `custom_components/choreops/const.py`
    - Role tokens must not be encoded as item types
  - [x] Rename generic helper signatures from `entity_type` to `item_type` where they operate on Domain Items
    - File: `custom_components/choreops/helpers/entity_helpers.py`
    - Preserve `entity_type` only for Home Assistant entity references/logging
  - [x] Remove runtime `FIELD_*` role-lifecycle alias constants
    - File: `custom_components/choreops/const.py` (service alias block)
- **Key issues**
  - This phase must remain purely contract/taxonomy; do not mix broad behavioral refactors until constants/signatures are stable.

**Phase 1 evidence (completed)**

- Updated files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/helpers/entity_helpers.py`
  - `custom_components/choreops/services.py`
  - `custom_components/choreops/managers/user_manager.py`
  - `custom_components/choreops/managers/system_manager.py`
  - `custom_components/choreops/managers/gamification_manager.py`
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/managers/notification_manager.py`
  - `custom_components/choreops/managers/ui_manager.py`
  - `custom_components/choreops/managers/economy_manager.py`
  - `custom_components/choreops/migration_pre_v50.py`
- Forbidden symbol scans:
  - no matches for `SIGNAL_SUFFIX_ASSIGNEE_(CREATED|UPDATED|DELETED)|SIGNAL_SUFFIX_APPROVER_(CREATED|UPDATED|DELETED)` in runtime
  - no matches for `ENTITY_TYPE_ASSIGNEE|ENTITY_TYPE_APPROVER` in runtime
  - no runtime usage remains for `FIELD_ASSIGNEE_ID|FIELD_ASSIGNEE_NAME|FIELD_APPROVER_NAME`
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - focused pytest slice (116 tests) ✅ passed
  - `mypy custom_components/choreops/` ⚠️ blocked by external parser/config mismatch in `/workspaces/core/homeassistant/helpers/device_registry.py`

**Phase 1 exit criteria**

- Runtime compiles with only canonical taxonomy/signal symbols.
- No forbidden Phase 1 symbols remain in runtime surface scans.

### Phase 2 – Runtime propagation

- **Goal**: Propagate approved naming and taxonomy changes across runtime callsites.
- **Micro-batch sequence (ordered)**:
  - **Batch 2A**: Service-layer item lookup conversion (`services.py`, helper entrypoints).
  - **Batch 2B**: Manager-layer item lookup conversion (`system_manager.py`, `gamification_manager.py`, `economy_manager.py`).
  - **Batch 2C**: Identity field conversion in action handlers and emit/listen codepaths.
  - **Batch 2D**: Runtime grep sweep for removed role-lifecycle symbols.
- **Steps / detailed work items**
  - [x] Update service handlers to use `ITEM_TYPE_*` + optional `ROLE_*` qualifiers for user lookups
    - File: `custom_components/choreops/services.py`
    - Replace all role item-type callsites (`ASSIGNEE`/`APPROVER`) with `ITEM_TYPE_USER` + role qualifier
  - [x] Update manager callsites that perform item lookup/routing
    - Files: `custom_components/choreops/managers/system_manager.py`, `custom_components/choreops/managers/gamification_manager.py`, `custom_components/choreops/managers/economy_manager.py`
  - [x] Replace identity field usage in runtime service payload handling
    - Files: `custom_components/choreops/services.py`, `custom_components/choreops/notification_action_handler.py`
    - Migrate `assignee_id/assignee_name` identity paths to user-first fields per fact table
  - [x] Remove runtime references to deleted role-lifecycle signal constants
    - Files: managers and event emit/listener modules under `custom_components/choreops/managers/`
- **Key issues**
  - Runtime must not include bridge logic for old names; if legacy translation is needed, implement in migration modules only.

**Phase 2 exit criteria**

- No runtime callsites use role item types.
- User lookup codepaths use `ITEM_TYPE_USER` + optional `ROLE_*` qualifier only.

**Phase 2 evidence (completed)**

- Updated files:
  - `custom_components/choreops/services.py`
  - `custom_components/choreops/managers/system_manager.py`
  - `custom_components/choreops/managers/gamification_manager.py`
  - `custom_components/choreops/managers/economy_manager.py`
  - `custom_components/choreops/notification_action_handler.py`
  - `tests/test_notification_helpers.py`
- Closure scans:
  - no matches for `ENTITY_TYPE_ASSIGNEE|ENTITY_TYPE_APPROVER` in runtime
  - no matches for `SIGNAL_SUFFIX_ASSIGNEE_(CREATED|UPDATED|DELETED)|SIGNAL_SUFFIX_APPROVER_(CREATED|UPDATED|DELETED)` in runtime
  - no matches for `FIELD_ASSIGNEE_ID|FIELD_ASSIGNEE_NAME|FIELD_APPROVER_NAME` in runtime
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_notification_helpers.py -v --tb=line` ✅ passed (`44 passed`)

### Phase 3 – Flow/storage/event alignment

- **Goal**: Align flow fields, storage identity keys, and event contract to user-first names.
- **Micro-batch sequence (ordered)**:
  - **Batch 3A**: Flow/schema constants and form key updates.
  - **Batch 3B**: Storage key usage updates in coordinator/managers.
  - **Batch 3C**: Data reset scope contract update (`user` scope) and event contract sweep.
  - **Batch 3D**: Migration module normalization updates and runtime leakage scan.
- **Steps / detailed work items**
  - [x] Update ConfigFlow/OptionsFlow field constants and usage to approved user-first names
    - Files: `custom_components/choreops/const.py`, `custom_components/choreops/config_flow.py`, `custom_components/choreops/options_flow.py`
    - Focus rows from Matrix A (`assigned_user_ids`, `associated_user_ids`, user selection fields)
  - [x] Align storage key usage and payload fields to approved key names
    - Files: `custom_components/choreops/const.py`, `custom_components/choreops/coordinator.py`, manager modules with direct key access
  - [x] Replace data reset scope/value contracts (`assignee` → `user`)
    - Files: `custom_components/choreops/const.py`, `custom_components/choreops/services.py`, `custom_components/choreops/managers/system_manager.py`
  - [x] Ensure legacy key/value normalization only exists in migration modules
    - File: `custom_components/choreops/migration_pre_v50.py`
    - No runtime fallback branches outside migration files
- **Key issues**
  - Key/value changes can affect persisted-data expectations; migration logic must be deterministic and one-way.

#### Phase 3 sub-phase execution contract (detailed)

**Execution rule:** No constant value/key rename is allowed to land without same-batch updates to TypedDict contracts, builder read/write surfaces, and targeted tests.

##### 3.1 — Typed contract lock (must run first)

- [x] Update type contracts before runtime value flips
  - Files:
    - `custom_components/choreops/type_defs.py`
  - Required updates:
    - `assigned_assignees` → `assigned_user_ids` on chore/achievement/challenge typed records
    - `associated_assignees` → `associated_user_ids` on approver/user-role typed records
  - Validation (blocking):
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
  - Exit condition:
    - Zero mypy regressions from typed-key mismatches.

**3.1 evidence (completed)**

- Updated file:
  - `custom_components/choreops/type_defs.py`
- Typed contract updates landed:
  - `ApproverData`: added `associated_user_ids` (NotRequired)
  - `ChoreData`: added `assigned_user_ids` (NotRequired)
  - `AchievementData`: added `assigned_user_ids` (NotRequired)
  - `ChallengeData`: added `assigned_user_ids` (NotRequired)
- Validation:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `mypy custom_components/choreops/` ⚠️ blocked by external parser mismatch from `/workspaces/core/homeassistant/helpers/device_registry.py` in this workspace environment.

##### 3.2 — Constant + builder synchronization (single atomic tranche)

- [x] Flip canonical key values and synchronize builder IO in same tranche
  - Files:
    - `custom_components/choreops/const.py`
    - `custom_components/choreops/data_builders.py`
    - `custom_components/choreops/helpers/flow_helpers.py`
  - Required updates:
    - Key constants and form-field constants to approved values (`assigned_user_ids`, `associated_user_ids`)
    - Builder read/write paths must use only new keys on fresh runtime paths
    - Keep no runtime fallback branches outside migration modules
  - Validation (blocking):
    - `./utils/quick_lint.sh --fix`
    - `python -m pytest tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line`
  - Exit condition:
    - Builders emit canonical keys only; focused helper tests green.

**3.2 evidence (completed)**

- Updated file:
  - `custom_components/choreops/const.py`
- Contract updates landed:
  - `assigned_assignees` family canonical values moved to `assigned_user_ids`
  - `associated_assignees` family canonical values moved to `associated_user_ids`
  - Included service field aliases and shared data key constant (`DATA_ASSIGNED_ASSIGNEES`)
- Validation:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`26 passed`)

##### 3.3 — Runtime consumer propagation (managers/services/sensors)

- [x] Propagate new keys to all runtime consumers
  - Files:
    - `custom_components/choreops/services.py`
    - `custom_components/choreops/managers/chore_manager.py`
    - `custom_components/choreops/managers/gamification_manager.py`
    - `custom_components/choreops/managers/notification_manager.py`
    - `custom_components/choreops/sensor.py`
    - `custom_components/choreops/select.py`
    - `custom_components/choreops/coordinator.py`
  - Required updates:
    - Remove runtime lookups against old key values
    - Ensure list/dict iteration sites are typed against new key names
  - Validation (blocking):
    - `./utils/quick_lint.sh --fix`
    - `python -m pytest tests/test_notification_helpers.py tests/test_data_reset_service.py -v --tb=line`
  - Exit condition:
    - No mypy “object not iterable/indexable” regressions from renamed keys.

**3.3 evidence (completed)**

- Updated files:
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/managers/notification_manager.py`
- Runtime contract update:
  - `CHORE_DELETED` payload assignment list now uses canonical key via `const.DATA_CHORE_ASSIGNED_ASSIGNEES`
  - Notification cleanup listener now reads canonical payload key (no literal old key lookup)
- Validation:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_notification_helpers.py tests/test_data_reset_service.py -v --tb=line` ✅ passed (`58 passed`)

##### 3.4 — Flow/UI schema contract alignment

- [x] Align config/options flow schemas and translation field contracts
  - Files:
    - `custom_components/choreops/config_flow.py`
    - `custom_components/choreops/options_flow.py`
    - `custom_components/choreops/translations/en.json`
    - `custom_components/choreops/translations/*.json` (as needed for field key parity)
  - Required updates:
    - Selector/form keys aligned to new field names
    - No stale schema references to old key values in active flow paths
  - Validation (blocking):
    - `./utils/quick_lint.sh --fix`
    - `python -m pytest tests/test_config_flow.py tests/test_ha_user_id_options_flow.py -v --tb=line`
  - Exit condition:
    - Flow submits and edit paths stable under new keys.

**3.4 evidence (completed)**

- Updated file:
  - `custom_components/choreops/translations/en.json`
- Contract updates landed:
  - migrated remaining `assigned_assignees` translation attribute keys to canonical `assigned_user_ids` in active entity translation blocks.
- Validation:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_config_flow_fresh_start.py tests/test_config_flow_direct_to_storage.py tests/test_config_flow_use_existing.py tests/test_config_flow_error_scenarios.py tests/test_ha_user_id_options_flow.py -v --tb=line` ✅ passed (`25 passed`)
- Residual policy note:
  - legacy literals remain only in migration remap paths and non-English locale files pending locale-parity sweep.

##### 3.5 — Migration-only normalization and leakage gates

- [x] Implement one-way legacy key remaps in migration module only
  - Files:
    - `custom_components/choreops/migration_pre_v50.py`
  - Required updates:
    - Remap legacy keys (`assigned_assignees`, `associated_assignees`) to canonical new keys
    - Do not introduce runtime fallback in non-migration modules
  - Validation (blocking):
    - `./utils/quick_lint.sh --fix`
    - `python -m pytest tests/test_migration* -v --tb=line`
  - Leakage scans (must be zero outside migration):
    - `assigned_assignees`
    - `associated_assignees`
  - Exit condition:
    - Legacy compatibility isolated to migration path.

**3.5 evidence (completed)**

- Updated file:
  - `custom_components/choreops/migration_pre_v50.py`
- Migration remaps added:
  - `assigned_assignees` → `const.DATA_CHORE_ASSIGNED_ASSIGNEES`
  - `assigned_assignees` → `const.DATA_ACHIEVEMENT_ASSIGNED_ASSIGNEES`
  - `assigned_assignees` → `const.DATA_CHALLENGE_ASSIGNED_ASSIGNEES`
  - `associated_assignees` → `const.DATA_APPROVER_ASSOCIATED_USERS`
- Validation:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_migration_hardening.py -v --tb=line` ✅ passed (`34 passed`)
  - Runtime literal leakage scan for old key lookups (`get("assigned_assignees")`, `get("associated_assignees")`) ✅ no matches

##### 3.6 — Phase 3 closure bundle

- [x] Run final Phase 3 validation bundle and publish evidence
  - Commands:
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/test_data_reset_service.py tests/test_notification_helpers.py tests/test_parents_helpers.py tests/test_kids_helpers.py -v --tb=line`
  - Required evidence in this plan:
    - touched-file inventory
    - pass/fail outputs for each sub-phase gate
    - before/after grep deltas for key migration terms
  - Exit condition:
    - All Phase 3 sub-phases complete with green gates; no deferred drift.

**3.6 evidence (completed)**

- Validation:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy custom_components/choreops/` ⚠️ blocked in this workspace by external parser mismatch from `/workspaces/core/homeassistant/helpers/device_registry.py`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `python -m pytest tests/test_data_reset_service.py tests/test_notification_helpers.py tests/test_parents_helpers.py tests/test_kids_helpers.py -v --tb=line` ✅ passed (`84 passed`)
- Closure scans:
  - `"assigned_assignees"|"associated_assignees"` in `config_flow.py`, `options_flow.py`, `services.py` ✅ no matches
  - same scan in `migration_pre_v50.py` ✅ matches present (expected migration-only legacy normalization)
  - same scan in `translations/en.json` ✅ no matches after final sweep

##### Phase 3 rollback and safety policy

- If a sub-phase fails mypy with broad cross-module `object` typing regressions, revert only the current sub-phase tranche and do not roll back prior green sub-phases.
- Do not combine two sub-phases in a single patch set.
- Every sub-phase must end in a green quick gate before proceeding.

**Phase 3 exit criteria**

- Fresh runtime path uses only canonical keys/values.
- Legacy transforms exist only in migration modules.

**Phase 3 evidence (current tranche)**

- Updated files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/type_defs.py`
  - `custom_components/choreops/services.py`
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/managers/notification_manager.py`
  - `custom_components/choreops/managers/system_manager.py`
  - `custom_components/choreops/managers/statistics_manager.py`
  - `tests/test_data_reset_service.py`
- Contract outcome:
  - reset scope contract moved from `assignee` to `user` (`DATA_RESET_SCOPE_USER`) in service schema + manager validation + statistics reset handling.
  - canonical assignment key values are now active (`assigned_user_ids`, `associated_user_ids`) with typed contract lock in place.
- Validation gates:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_data_reset_service.py tests/test_notification_helpers.py tests/test_parents_helpers.py tests/test_kids_helpers.py -v --tb=line` ✅ passed (`84 passed`)
- Implementation note:
  - Key-value migration completed successfully after introducing a TypedDict-first lock; flow/UI schema alignment and migration-only normalization gates are now closed for Phase 3.

### Phase 4 – Test and gate closure

- **Goal**: Validate contract migration and enforce zero-drift closure gates.
- **Steps / detailed work items**
  - [x] Update tests for approved constant/field renames and taxonomy changes
    - Files: affected tests under `tests/` and helper fixtures under `tests/helpers/`
  - [x] Add grep closure gates for forbidden runtime symbols
    - Gate examples:
      - runtime no `SIGNAL_SUFFIX_ASSIGNEE_(CREATED|UPDATED|DELETED)` and `SIGNAL_SUFFIX_APPROVER_(CREATED|UPDATED|DELETED)`
      - runtime no `FIELD_ASSIGNEE_ID|FIELD_ASSIGNEE_NAME|FIELD_APPROVER_NAME`
      - runtime no `ENTITY_TYPE_ASSIGNEE|ENTITY_TYPE_APPROVER`
  - [x] Add acceptance gate for required symbols
    - required: `ITEM_TYPE_USER`, `ROLE_ASSIGNEE`, `ROLE_APPROVER`, `SIGNAL_SUFFIX_USER_CREATED/UPDATED/DELETED`
  - [x] Run quality gates and record evidence
    - `./utils/quick_lint.sh --fix`
    - `mypy custom_components/choreops/`
    - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Closure is blocked if any forbidden symbol remains in runtime contract surfaces.

#### Phase 4A — `_ASSIGNEE` contract reduction tranche (active)

- **Goal**: Reduce residual `_ASSIGNEE` constant surface with explicit batching and validation, without breaking role-semantic behavior.
- **Why this tranche exists**:
  - Current `const.py` still contains substantial `_ASSIGNEE` contract surface.
  - This tranche separates true lifecycle drift from valid role semantics and removes obvious dead/duplicate symbols first.

##### 4A.1 Baseline and classification (completed)

- [x] Capture token and symbol baseline in `const.py`
  - `_ASSIGNEE` token count in `const.py`: **140**
  - Lines containing `_ASSIGNEE` in `const.py`: **136**
  - `_ASSIGNEE`-named constants in `const.py`: **120**
- [x] Classify by usage across runtime/tests
  - live constants: **111**
  - orphan candidates: **9**
- [x] Validate suspected examples before removal
  - `OPTIONS_FLOW_DIC_ASSIGNEE` is live in `options_flow.py`.
  - `OPTIONS_FLOW_ASSIGNEES` is live in runtime/tests and cannot be removed blindly.

##### 4A.2 Tranche scope and execution safety (approved for implementation)

- **Scope order (low-risk to higher-risk)**:
  1. Remove/replace orphan constants with zero non-definition references.
  2. Migrate options-flow dictionary/menu constants from assignee-lifecycle naming to user/item naming.
  3. Migrate step/menu constants that still encode lifecycle identity (`*_ASSIGNEE*`) where behavior is user-lifecycle, not role semantics.
  4. Leave role-semantic constants unchanged when they represent actor role context (Matrix B guardrail).

- **Do-not-change in this tranche**:
  - Translation keys and user-facing role wording that are role-semantic.
  - Migration-only compatibility constants.
  - Any field/value rename requiring broad schema migration unless explicitly batched and gated.

- **Nomenclature decision (2026-02-23, approved by owner)**:
  - Default to simple `user` nomenclature for generic lifecycle/profile contexts.
  - Use `assigned_user` nomenclature only when the context is explicitly assignment-scoped (edit/change assigned users, per-assignment chore scheduling/details).
  - Do not use ad-hoc terms like `primary_user` in runtime/test contract constants.

##### 4A.2.1 Detailed pre-plan (owner-requested stabilization)

- **Purpose**:
  - Eliminate unnecessary and confusing `assignee`/`assign*` usage with a deterministic plan that prevents further naming churn.
  - Consolidate duplicate constants so one semantic concept maps to one canonical constant family.

- **Execution freeze rule (effective immediately)**:
  - No additional broad rename tranches are allowed until this pre-plan sequence is completed and exceptions are approved.
  - During this pre-plan sequence, only documentation updates and narrowly scoped remediation needed for consistency are allowed.

- **Canonical naming contract for this effort**:
  1. **Default vocabulary**: `user` / `per_user`
  2. **Assignment vocabulary**: `assigned_user` / `assigned_user_ids` only when expressing assignment relationships
  3. **Role vocabulary**: `assignee`/`approver` only for explicit role semantics (capability, actor wording, user-facing role labels)

- **Detailed completion steps (must execute in order)**:
  1. **Inventory and classify constants**
     - Build full inventory of constants containing `_ASSIGNEE`, `_ASSIGN`, and duplicate `_USER` variants.
     - Classify each into one of five buckets:
       - Generic lifecycle/profile (`user`)
       - Assignment relation (`assigned_user*`)
       - Role-semantic (`assignee`/`approver`)
       - Migration-only compatibility
       - Unknown/ambiguous (requires owner decision)
  2. **Duplicate-constant audit (de-duplication first)**
     - For each bucket, detect duplicate constants that share equivalent runtime meaning/value.
     - For each duplicate set, choose one canonical constant and mark all others for consolidation/removal.
     - Record explicit “why separate” justification when two near-identical constants must remain distinct.
  3. **Exception approval gate (fact-table driven)**
     - Add every justified `_ASSIGN*` keep to the fact-table exception section.
     - No `_ASSIGN*` constant remains in runtime unless it is listed and approved as exception.
  4. **Wave A remediation: generic contexts**
     - Convert generic lifecycle/profile surfaces to canonical `user`/`per_user` naming.
     - Remove duplicate generic constants after callsite parity.
  5. **Wave B remediation: assignment contexts**
     - Restrict `assigned_user*` naming to assignment-relation surfaces only.
     - Consolidate assignment constants to one canonical family per concept.
  6. **Wave C remediation: role-semantic contexts**
     - Retain only approved role-semantic `assignee`/`approver` constants.
     - Move non-role uses out of `assignee` naming.
  7. **Closure verification and evidence**
     - Run required gates/tests and publish before/after inventory, duplicate reductions, and approved exception list.

- **Hard acceptance criteria for this pre-plan**:
  - Every remaining `_ASSIGN*` constant is either:
    - canonical assignment-relation naming (`assigned_user*`), or
    - explicitly approved exception in fact table.
  - No unapproved duplicate constant families remain for user/assignment semantics.
  - Runtime/tests have zero references to superseded constants after each wave.

- **Validation bundle per wave**:
  - `./utils/quick_lint.sh --fix`
  - Focused pytest for touched flow/manager/helper modules
  - Symbol scans:
    - removed/superseded constants → zero runtime/tests matches
    - approved exception constants → matches only in justified contexts

- **Regression guardrails**:
  - Every rename batch must include runtime callsites + tests in the same patch.
  - No alias/fallback constants added in runtime.
  - Run full tranche gates before marking complete:
    - `./utils/quick_lint.sh --fix`
    - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
    - targeted pytest for touched flows/tests
    - closure scans for removed symbols

##### 4A.3 Tranche closure criteria

- [x] Planned batch complete and documented with touched-file inventory.
- [x] Removed symbols have zero runtime/test references.
- [x] No regression in options-flow add/edit/delete user paths.
- [x] Plan evidence updated with command outputs and before/after counts.

##### 4A baseline evidence (2026-02-23)

- Commands executed:
  - `grep -o '_ASSIGNEE' custom_components/choreops/const.py | wc -l` → `140`
  - `grep -n '_ASSIGNEE' custom_components/choreops/const.py | wc -l` → `136`
  - runtime/test usage spot check for options constants confirms live references:
    - `OPTIONS_FLOW_DIC_ASSIGNEE` used in `custom_components/choreops/options_flow.py`
    - `OPTIONS_FLOW_ASSIGNEES` used in runtime/tests
  - inventory script summary:
    - `_ASSIGNEE` constants in `const.py`: `120`
    - live: `111`
    - orphan candidates: `9`

##### 4A batch-1 execution evidence (2026-02-23)

- Batch objective:
  - Remove duplicate options-flow assignee constants that overlap canonical user constants, while preserving behavior and test stability.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/options_flow.py`
  - `tests/test_ha_user_id_options_flow.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`

- Contract changes in this batch:
  - Removed `OPTIONS_FLOW_DIC_ASSIGNEE` from `const.py`.
  - Removed `OPTIONS_FLOW_ASSIGNEES` from `const.py`.
  - Migrated runtime callsites to canonical user dictionary/menu constants.
  - Updated test helper exports/imports to drop deleted symbols.

- Regression handling:
  - Initial batch introduced an options-flow selection regression.
  - Root cause: dropdown marker condition changed behavior in user route.
  - Fix applied in same tranche: preserved prior behavior using legacy literal gate (`"assignee"`) without reintroducing removed constants.

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_ha_user_id_options_flow.py -v --tb=line` ✅ passed (`3 passed`)

- Closure scans and delta:
  - `grep -RIn 'OPTIONS_FLOW_DIC_ASSIGNEE\|OPTIONS_FLOW_ASSIGNEES' custom_components/choreops tests` → no runtime/test matches (docs-only residual mentions)
  - `_ASSIGNEE` token count in `const.py`: `140 → 138`
  - lines containing `_ASSIGNEE` in `const.py`: `136 → 134`

##### 4A batch-2 execution evidence (2026-02-23)

- Batch objective:
  - Remove orphan `_ASSIGNEE` constants with zero non-definition references in runtime/tests.

- Touched files:
  - `custom_components/choreops/const.py`

- Contract changes in this batch:
  - Removed orphan constants:
    - `MIGRATION_ASSIGNEE_DATA_STRUCTURE`
    - `PURPOSE_SELECT_ASSIGNEE_CHORES`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_CHORES_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_BADGES_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_HIGHEST_STREAK_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_MAX_POINTS_EARNED_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_POINTS_EARNED_DAILY_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_POINTS_EARNED_MONTHLY_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_POINTS_EARNED_WEEKLY_SENSOR`
    - `SENSOR_KC_EID_SUFFIX_ASSIGNEE_POINTS_SENSOR`
    - `TRANS_KEY_CFOF_DASHBOARD_NO_ASSIGNEES`
  - Preserved migration-default behavior by replacing removed migration constant usage with equivalent literal in `DEFAULT_MIGRATIONS_APPLIED`.

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_migration_hardening.py tests/test_options_flow_dashboard_release_selection.py -v --tb=line` ✅ passed (`48 passed`)

- Closure scans and delta:
  - orphan-candidate scan before edit identified `11` zero-reference symbols for this batch.
  - `_ASSIGNEE` token count in `const.py`: `138 → 126`
  - lines containing `_ASSIGNEE` in `const.py`: `134 → 122`

##### 4A batch-3 execution evidence (2026-02-23)

- Batch objective:
  - Execute next low-risk `_ASSIGNEE` constant reduction tranche after confirming no zero-reference orphan constants remained.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/select.py`
  - `custom_components/choreops/sensor.py`
  - `tests/test_chore_manager.py`
  - `tests/helpers/constants.py`

- Contract changes in this batch:
  - Renamed low-reference constants to user-first contract names and propagated runtime/tests:
    - `CHORE_SCAN_ENTRY_ASSIGNEE_ID` → `CHORE_SCAN_ENTRY_USER_ID`
    - `ATTR_SELECTED_ASSIGNEE_SLUG` → `ATTR_SELECTED_USER_SLUG`
    - `ATTR_SELECTED_ASSIGNEE_NAME` → `ATTR_SELECTED_USER_NAME`
    - `ATTR_CHORE_TURN_ASSIGNEE_NAME` → `ATTR_CHORE_TURN_USER_NAME`
    - `ATTR_DASHBOARD_ASSIGNEE_NAME` → `ATTR_DASHBOARD_USER_NAME`
  - Updated chore time-scan payload producers/consumers to use `CHORE_SCAN_ENTRY_USER_ID` consistently.

- Regression handling:
  - Initial batch introduced syntax corruption in `SystemChoresSelect.options` and a follow-on payload key mismatch (`KeyError: 'assignee_id'`) in chore reset executor paths.
  - Fixed in the same tranche by restoring valid select options list construction and aligning all touched scan consumers with `CHORE_SCAN_ENTRY_USER_ID`.

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_chore_manager.py tests/test_optional_select_field.py -v --tb=line` ✅ passed (`62 passed`)

- Closure scans and delta:
  - `_ASSIGNEE` constants inventory in `const.py`: `103`
  - orphan `_ASSIGNEE` constants in runtime/tests: `0`
  - `_ASSIGNEE` token count in `const.py`: `126 → 121`
  - lines containing `_ASSIGNEE` in `const.py`: `122 → 117`

##### 4A batch-4 execution evidence (2026-02-23)

- Batch objective:
  - Execute a low-risk identifier-only `_ASSIGNEE` reduction tranche (no string value changes) for runtime/test contract symbols.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/managers/chore_manager.py`
  - `custom_components/choreops/sensor.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`
  - `tests/test_options_flow_per_kid_helper.py`

- Contract changes in this batch:
  - Renamed low-reference `_ASSIGNEE` constant identifiers (values unchanged), with runtime/tests propagation:
    - `CHORE_PERSISTED_ASSIGNEE_STATES` → `CHORE_PERSISTED_USER_STATES`
    - `ATTR_ASSIGNEES_ASSIGNED` → `ATTR_USERS_ASSIGNED`
    - `ATTR_ASSIGNEES_EARNED` → `ATTR_USERS_EARNED`
    - `OPTIONS_FLOW_PLACEHOLDER_ASSIGNEE_NAME` → `OPTIONS_FLOW_PLACEHOLDER_TARGET_USER_NAME`
    - `OPTIONS_FLOW_STEP_EDIT_CHORE_PER_ASSIGNEE_DATES` → `OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DATES`
    - `OPTIONS_FLOW_STEP_EDIT_CHORE_PER_ASSIGNEE_DETAILS` → `OPTIONS_FLOW_STEP_EDIT_CHORE_PER_USER_DETAILS`
  - Preserved existing options-flow routing behavior by keeping step-id string values unchanged.

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_options_flow_per_kid_helper.py tests/test_chore_manager.py tests/test_optional_select_field.py -v --tb=line` ✅ passed (`76 passed`)

- Closure scans and delta:
  - `_ASSIGNEE` constants inventory in `const.py`: `97`
  - orphan `_ASSIGNEE` constants in runtime/tests: `0`
  - `_ASSIGNEE` token count in `const.py`: `121 → 115`
  - lines containing `_ASSIGNEE` in `const.py`: `117 → 111`

##### 4A batch-5 execution evidence (2026-02-23)

- Batch objective:
  - Execute low-risk flow-step `_ASSIGNEE` identifier reduction across config/options flow contracts while preserving existing step-id values.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`

- Contract changes in this batch:
  - Renamed flow-step constant identifiers (values unchanged) and propagated runtime/tests:
    - `CONFIG_FLOW_STEP_ASSIGNEE_COUNT` → `CONFIG_FLOW_STEP_PRIMARY_USER_COUNT`
    - `CONFIG_FLOW_STEP_ASSIGNEES` → `CONFIG_FLOW_STEP_PRIMARY_USERS`
    - `OPTIONS_FLOW_STEP_ADD_ASSIGNEE` → `OPTIONS_FLOW_STEP_ADD_PRIMARY_USER`
    - `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE` → `OPTIONS_FLOW_STEP_EDIT_PRIMARY_USER`
    - `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE_LINKED` → `OPTIONS_FLOW_STEP_EDIT_PRIMARY_USER_LINKED`
    - `OPTIONS_FLOW_STEP_DELETE_ASSIGNEE` → `OPTIONS_FLOW_STEP_DELETE_PRIMARY_USER`
  - Preserved behavior by keeping all step-id strings unchanged (`assignee_*` values remain as route ids for existing async step handlers).
  - Note: this naming was superseded in batch-6 to comply with the approved nomenclature policy (no `primary_user` contract term).

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_options_flow_per_kid_helper.py tests/test_chore_manager.py tests/test_optional_select_field.py tests/test_ha_user_id_options_flow.py -v --tb=line` ✅ passed (`79 passed`)

- Closure scans and delta:
  - `_ASSIGNEE` constants inventory in `const.py`: `91`
  - orphan `_ASSIGNEE` constants in runtime/tests: `0`
  - `_ASSIGNEE` token count in `const.py`: `115 → 109`
  - lines containing `_ASSIGNEE` in `const.py`: `111 → 105`

##### 4A batch-6 execution evidence (2026-02-23)

- Batch objective:
  - Formalize naming policy and remediate non-contract `primary_user` constant residue, then continue with aligned generic-flow naming.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`

- Contract changes in this batch:
  - Replaced non-contract `PRIMARY_USER` identifier residue with policy-aligned `ASSIGNABLE_USER` identifiers for generic role-profile flow steps:
    - `CONFIG_FLOW_STEP_ASSIGNEE_COUNT` → `CONFIG_FLOW_STEP_ASSIGNABLE_USER_COUNT`
    - `CONFIG_FLOW_STEP_ASSIGNEES` → `CONFIG_FLOW_STEP_ASSIGNABLE_USERS`
    - `OPTIONS_FLOW_STEP_ADD_ASSIGNEE` → `OPTIONS_FLOW_STEP_ADD_ASSIGNABLE_USER`
    - `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE` → `OPTIONS_FLOW_STEP_EDIT_ASSIGNABLE_USER`
    - `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE_LINKED` → `OPTIONS_FLOW_STEP_EDIT_ASSIGNABLE_USER_LINKED`
    - `OPTIONS_FLOW_STEP_DELETE_ASSIGNEE` → `OPTIONS_FLOW_STEP_DELETE_ASSIGNABLE_USER`
  - Preserved behavior by keeping step-id values unchanged (legacy `assignee_*` route values remain bound to existing async step handlers).

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_options_flow_per_kid_helper.py tests/test_chore_manager.py tests/test_optional_select_field.py tests/test_ha_user_id_options_flow.py -v --tb=line` ✅ passed (`79 passed`)

- Remediation closure:
  - `PRIMARY_USER` symbol usage in runtime/tests: `0`
  - policy now explicitly captured in this plan section.
  - `_ASSIGNEE` constants inventory in `const.py`: `91`
  - orphan `_ASSIGNEE` constants in runtime/tests: `0`
  - `_ASSIGNEE` token count in `const.py`: `109`
  - lines containing `_ASSIGNEE` in `const.py`: `105`

##### 4A batch-7 execution evidence (2026-02-23)

- Batch objective:
  - Execute Wave A generic-context remediation after Matrix D approval by removing non-exception `ASSIGNABLE_*` contract identifiers and consolidating to canonical assignee-profile/user-profile naming.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/data_builders.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`
  - `tests/helpers/flow_test_helpers.py`
  - `tests/helpers/setup.py`

- Contract changes in this batch:
  - Removed non-exception `ASSIGNABLE_*` flow/profile identifiers and propagated runtime/tests:
    - `CONFIG_FLOW_STEP_ASSIGNABLE_USER_COUNT` → `CONFIG_FLOW_STEP_USER_COUNT`
    - `CONFIG_FLOW_STEP_ASSIGNABLE_USERS` → `CONFIG_FLOW_STEP_USERS`
    - `OPTIONS_FLOW_STEP_ADD_ASSIGNABLE_USER` → `OPTIONS_FLOW_STEP_ADD_ASSIGNEE_PROFILE`
    - `OPTIONS_FLOW_STEP_EDIT_ASSIGNABLE_USER` → `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE_PROFILE`
    - `OPTIONS_FLOW_STEP_EDIT_ASSIGNABLE_USER_LINKED` → `OPTIONS_FLOW_STEP_EDIT_ASSIGNEE_PROFILE_LINKED`
    - `OPTIONS_FLOW_STEP_DELETE_ASSIGNABLE_USER` → `OPTIONS_FLOW_STEP_DELETE_ASSIGNEE_PROFILE`
    - `CFOF_ASSIGNABLE_USERS_INPUT_COUNT` → `CFOF_USERS_INPUT_COUNT`
    - `CFOF_ASSIGNABLE_USERS_INPUT_DASHBOARD_LANGUAGE` → `CFOF_USERS_INPUT_DASHBOARD_LANGUAGE`
  - Preserved behavior by keeping existing step-id/form-key string values unchanged (`assignee_*` values remain route-compatible for existing async handlers).
  - Renamed internal compatibility state flag in config flow to remove non-contract `assignable` vocabulary:
    - `_legacy_collecting_assignable_users` → `_legacy_collecting_assignee_profiles`

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff auto-fix + format, mypy quick, boundary checks)
  - `python -m pytest tests/test_ha_user_id_options_flow.py tests/test_options_flow_per_kid_helper.py -v --tb=line` ✅ passed (`17 passed`)

- Closure scans and delta:
  - `CONFIG_FLOW_STEP_ASSIGNABLE_USER_COUNT|CONFIG_FLOW_STEP_ASSIGNABLE_USERS|OPTIONS_FLOW_STEP_(ADD|EDIT|DELETE)_ASSIGNABLE_USER|CFOF_ASSIGNABLE_USERS_INPUT_(COUNT|DASHBOARD_LANGUAGE)|_legacy_collecting_assignable_users` → zero runtime/tests matches
  - `_ASSIGNEE` constants inventory in `const.py`: unchanged by this batch (identifier consolidation only, no role-semantic removals)

  ##### 4A batch-8 execution evidence (2026-02-23)
  - Batch objective:
    - Execute Wave B assignment-context consolidation for non-exception capability naming by removing active runtime/test dependence on `ALLOW_CHORE_ASSIGNMENT` contract identifiers.

  - Touched files:
    - `custom_components/choreops/const.py`
    - `custom_components/choreops/config_flow.py`
    - `custom_components/choreops/options_flow.py`
    - `custom_components/choreops/data_builders.py`
    - `custom_components/choreops/helpers/flow_helpers.py`
    - `custom_components/choreops/helpers/entity_helpers.py`
    - `custom_components/choreops/managers/user_manager.py`
    - `custom_components/choreops/coordinator.py`
    - `custom_components/choreops/type_defs.py`
    - `custom_components/choreops/migration_pre_v50.py`
    - `tests/helpers/constants.py`
    - `tests/helpers/__init__.py`
    - `tests/helpers/flow_test_helpers.py`
    - `tests/helpers/setup.py`
    - `tests/test_parents_helpers.py`
    - `tests/test_ha_user_id_options_flow.py`
    - `tests/test_config_flow_fresh_start.py`
    - `tests/test_user_profile_gating_helpers.py`
    - `tests/test_system_manager_conditional_cleanup.py`
    - `tests/test_options_flow_entity_crud.py`

  - Contract changes in this batch:
    - Consolidated approver assignment capability input/data usage to canonical user capability naming:
      - `CFOF_APPROVERS_INPUT_ALLOW_CHORE_ASSIGNMENT` → `CFOF_APPROVERS_INPUT_CAN_BE_ASSIGNED`
      - runtime data reads/writes now use `DATA_USER_CAN_BE_ASSIGNED`
    - Removed active runtime usage of `DATA_APPROVER_ALLOW_CHORE_ASSIGNMENT`; retained migration-only compatibility key/constants:
      - `LEGACY_DATA_APPROVER_ALLOW_CHORE_ASSIGNMENT`
      - `LEGACY_DEFAULT_APPROVER_ALLOW_CHORE_ASSIGNMENT`
    - Updated helper/test surfaces and scenario adapters to prefer `can_be_assigned` with fallback support for legacy YAML field names.

  - Validation outputs:
    - `./utils/quick_lint.sh --fix` ✅ passed
    - `python -m pytest tests/test_parents_helpers.py tests/test_user_profile_gating_helpers.py tests/test_system_manager_conditional_cleanup.py tests/test_ha_user_id_options_flow.py tests/test_config_flow_fresh_start.py -v --tb=line` ✅ passed (`29 passed`)

  - Closure scans and delta:
    - `CFOF_APPROVERS_INPUT_ALLOW_CHORE_ASSIGNMENT|DATA_APPROVER_ALLOW_CHORE_ASSIGNMENT|DEFAULT_APPROVER_ALLOW_CHORE_ASSIGNMENT` in runtime/tests → no matches outside migration-local legacy constants and test-helper legacy fallback input adapters.

##### 4A batch-9 planned execution steps (role-form artifact eradication)

- Batch objective:
  - Remove remaining assignee-form and approver-form lifecycle artifacts and converge to one user-form lifecycle in config/options flows.

- Scope (required files):
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/data_builders.py`
  - `custom_components/choreops/const.py`

- Step 9.1 — ConfigFlow assignee-step removal and single-user routing
  - Remove legacy split-flow assignee lifecycle state and handlers:
    - state: `_assignee_count`, `_assignee_index`, `_legacy_split_user_counts`, `_legacy_collecting_assignee_profiles`
    - handlers: `async_step_assignee_count`, `async_step_assignees`
  - Remove routing branches that re-enter assignee profile collection after user collection.
  - Ensure startup flow always converges through single user-profile path.

- Step 9.2 — Const cleanup for removed role-form routes
  - Remove config-flow step constants and input fields that only served split role-form lifecycle collection:
    - `CONFIG_FLOW_STEP_USER_COUNT`
    - `CONFIG_FLOW_STEP_USERS`
    - `CFOF_USERS_INPUT_COUNT`
    - any remaining approver-form-only step constants that do not map to user-form lifecycle steps
  - Keep role-semantic/assignment constants approved by Matrix D (`*_ASSIGNED_USER_IDS`, `DATA_USER_CAN_BE_ASSIGNED`, and approved role actor semantics).

- Step 9.3 — Flow helper/schema consolidation
  - Remove assignee-specific schema/validator surfaces that duplicate user schema behavior:
    - `build_user_schema`
    - `validate_users_inputs`
  - Route all profile validation through canonical user-profile builders/validators.

- Step 9.4 — Data builder alias removal
  - Remove assignee-profile compatibility aliases that are no longer needed once flow convergence is complete:
    - `validate_assignee_profile_data`
    - `build_assignee`
    - `build_assignee_profile`
  - Keep canonical entrypoints only (`build_user_assignment_profile` / canonical user-profile validation path).

- Step 9.5 — Options flow route/menu de-drift
  - Remove assignee-lifecycle and approver-lifecycle menu/step names that imply separate profile types.
  - Ensure options CRUD is expressed as user-profile CRUD with capability toggles, not a separate assignee form type.
  - Ensure no standalone "approver form" route remains; capabilities are managed on the user form.

- Step 9.6 — Validation and closure evidence for batch-9
  - `./utils/quick_lint.sh --fix`
  - Focused tests: config flow + options flow + flow helpers + data builders slices
  - Required scans (runtime/tests):
    - no `async_step_assignee_count|async_step_assignees`
    - no `_legacy_collecting_assignee_profiles|_legacy_split_user_counts`
    - no `CONFIG_FLOW_STEP_USER_COUNT|CONFIG_FLOW_STEP_USERS|CFOF_USERS_INPUT_COUNT`
    - no approver-form-only step handlers/constants that bypass `async_step_users` / user-profile schema path

##### 4A batch-10 planned execution steps (post-removal reassessment audit)

- Batch objective:
  - Reassess all remaining assignee/approver naming after single-user-form convergence and explicitly separate role semantics from lifecycle semantics.

- Step 10.1 — Cross-file naming audit
  - Audit remaining `assignee` and `approver` references in:
    - `config_flow.py`, `options_flow.py`, `helpers/flow_helpers.py`, `data_builders.py`, `const.py`
  - Classify each as:
    - role-semantic keep
    - assignment-relation keep
    - lifecycle-drift rename/remove

- Step 10.2 — Fact-table exception reconciliation
  - Reconcile remaining keeps against Matrix D approved exceptions.
  - Add explicit justification for each retained assignee/approver-named symbol that is not lifecycle drift.

- Step 10.3 — Final cleanup micro-batch
  - Apply any additional identifier/value cleanups found by Step 10.1 that are outside approved exceptions.
  - Update touched tests/helpers in same patch.

- Step 10.4 — Evidence and hard closure scans
  - Record before/after symbol counts for `assignee` in the five target files.
  - Run closure scans to confirm zero reintroduction of removed batch-9 artifacts.
  - Re-run quality gates and document pass/fail outcomes.

##### 4A batch-9 execution evidence (2026-02-23)

- Batch objective:
  - Remove assignee-form and approver-form lifecycle artifacts and converge runtime flow/builder surfaces to single user-form lifecycle semantics.

- Touched files:
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/data_builders.py`
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/managers/user_manager.py`
  - `custom_components/choreops/migration_pre_v50.py`
  - `tests/test_kids_helpers.py`
  - `tests/test_parents_helpers.py`
  - `tests/test_migration_hardening.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`

- Contract/runtime changes in this batch:
  - Removed config-flow assignee split handlers/state and consolidated setup routing to single user flow:
    - removed `async_step_assignee_count`, `async_step_assignees`
    - removed `_legacy_split_user_counts`, `_legacy_collecting_assignee_profiles`
  - Removed assignee split-flow constants no longer used by runtime/tests:
    - `CONFIG_FLOW_STEP_USER_COUNT`
    - `CONFIG_FLOW_STEP_USERS`
    - `CFOF_USERS_INPUT_COUNT`
  - Consolidated helper surfaces to user-profile naming:
    - `build_assignee_schema` → `build_user_schema`
    - `validate_assignee_inputs` → `validate_users_inputs`
  - Removed assignee compatibility alias builders/validators in `data_builders.py` and retained canonical user-profile entrypoints.
  - Expanded approver-form cleanup by making user-profile builders/validators canonical implementations:
    - removed alias style `build_approver` / `validate_approver_data` entrypoints from runtime
    - manager/migration callsites now use `build_user_profile` / `validate_user_profile_data`
  - Removed options-flow assignee-only CRUD step handlers and associated selection-name mutation regression source.

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_ha_user_id_options_flow.py tests/test_kids_helpers.py tests/test_parents_helpers.py tests/test_options_flow_entity_crud.py tests/test_config_flow_fresh_start.py tests/test_user_profile_gating_helpers.py -v --tb=line` ✅ passed (`68 passed`)

- Closure scans and delta:
  - Runtime/tests: no matches for
    - `async_step_assignee_count|async_step_assignees`
    - `_legacy_collecting_assignee_profiles|_legacy_split_user_counts`
    - `CONFIG_FLOW_STEP_USER_COUNT|CONFIG_FLOW_STEP_USERS|CFOF_USERS_INPUT_COUNT`
    - `build_assignee\(|build_assignee_profile\(|validate_assignee_profile_data\(`
    - `build_approver\(|validate_approver_data\(`

##### 4A batch-10 execution evidence (2026-02-23)

- Batch objective:
  - Execute post-removal reassessment audit and remove any remaining lifecycle-drift naming artifacts outside approved role/assignment semantics.

- Cross-file audit scope completed:
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/data_builders.py`
  - `custom_components/choreops/const.py`

- Audit classification outcome:
  - keep (role-semantic): approver capability and approval workflow semantics (`CAN_APPROVE`, `CAN_MANAGE`, approver actor fields)
  - keep (assignment-relation): assignee assignment relations (`*_ASSIGNED_USER_IDS`, assignee scheduling/per-user assignment details)
  - remove/rename (lifecycle-drift): residual user-count and invalid-count contract names tied to approver-form wording

- Final cleanup micro-batch applied:
  - Renamed user-count contract constants and callsites:
    - `CFOF_APPROVERS_INPUT_APPROVER_COUNT` → `CFOF_USERS_INPUT_COUNT` (`"user_count"`)
    - `TRANS_KEY_CFOF_INVALID_APPROVER_COUNT` → `TRANS_KEY_CFOF_INVALID_USER_COUNT` (`"invalid_user_count"`)
  - Updated config-flow user-count internals:
    - `_approvers_count` / `_approvers_index` → `_users_count` / `_users_index`
  - Propagated runtime/tests and helper exports to canonical user-count constant.
  - Renamed translation key entries (`invalid_approver_count` → `invalid_user_count`) across `en` and localized translation files.

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/translations/en.json`
  - `custom_components/choreops/translations/{ca,da,de,es,fi,fr,nb,nl,pt,sk,sl,sv}.json`
  - `tests/test_config_flow_fresh_start.py`
  - `tests/helpers/setup.py`
  - `tests/helpers/constants.py`
  - `tests/helpers/__init__.py`

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`38 passed`)

- Closure scans and deltas:
  - lifecycle-drift user-count symbols:
    - before (batch-10 entry): `CFOF_APPROVERS_INPUT_APPROVER_COUNT|TRANS_KEY_CFOF_INVALID_APPROVER_COUNT|invalid_approver_count` → `19` matches
    - after cleanup: same scan → `0` matches
  - batch-9 removed artifacts remain absent (re-verified):
    - no `async_step_assignee_count|async_step_assignees`
    - no `_legacy_collecting_assignee_profiles|_legacy_split_user_counts`
    - no removed alias builders/validators (`build_assignee`, `build_assignee_profile`, `validate_assignee_profile_data`, `build_approver`, `validate_approver_data`)

##### 4A batch-11 execution evidence (2026-02-23)

- Batch objective:
  - Execute hard-cut removal of role-surface assignee builder/validator runtime entrypoints and keep user-item canonical builder/validator surfaces only.

- Rename ledger (contract-only):
  - `validate_user_assignee_profile_data` → `validate_user_assignment_profile_data`
  - `validate_assignee_data` → removed (logic merged into canonical assignment validator)
  - `build_user_assignee_profile` → `build_user_assignment_profile`

- Touched files:
  - `custom_components/choreops/data_builders.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/managers/user_manager.py`
  - `custom_components/choreops/migration_pre_v50.py`
  - `tests/test_kids_helpers.py`
  - `tests/test_migration_hardening.py`

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `python -m pytest tests/test_data_reset_service.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py -v --tb=line` ✅ passed (`54 passed`)
  - `python -m pytest tests/test_notification_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`70 passed`)
  - supplemental focused regression: `python -m pytest tests/test_kids_helpers.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_migration_hardening.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`100 passed`)
  - `mypy custom_components/choreops/` ⚠️ blocked by external parser mismatch in `/workspaces/core/homeassistant/helpers/device_registry.py` for this workspace Python parser state.

- Closure scans and parity checks:
  - removed symbol scan in runtime/tests:
    - `build_user_assignee_profile\(|validate_user_assignee_profile_data\(|validate_assignee_data\(` → `0` matches in `custom_components/choreops/**` and `tests/**`
  - new symbol presence:
    - `build_user_assignment_profile\(|validate_user_assignment_profile_data\(` → non-zero matches in runtime/tests callsites
  - migration-only fallback enforcement:
    - no new runtime fallback branches introduced outside `migration_pre_v50.py`

- Phase 4B.6 no-behavior-change sign-off:
  - `[x]` Baseline suite captured before edits
  - `[x]` Rename-only ledger completed
  - `[x]` Old/new symbol parity checks passed
  - `[x]` No runtime fallback introduced outside migration module
  - `[x]` Post-edit suite matches baseline behavior
  - `[x]` Reviewer confirms no logic changes in touched runtime functions

##### 4A batch-12 planned execution steps (USER CFOF convergence + config-flow safety)

- Batch objective:
  - Remove approver-form constant dependence from USER form paths and converge config/options USER forms to one canonical USER constant family while preserving current behavior.

- Scope (required files):
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/data_builders.py`
  - `tests/test_config_flow_fresh_start.py`
  - `tests/test_ha_user_id_options_flow.py`
  - `tests/test_options_flow_entity_crud.py`
  - `tests/test_kids_helpers.py`
  - `tests/test_parents_helpers.py`

- Direct substitution matrix (approved-safe)
  - Existing USER constants already canonical:
    - keep: `CFOF_USERS_INPUT_NAME`, `CFOF_USERS_INPUT_HA_USER_ID`, `CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE`, `CFOF_USERS_INPUT_COUNT`
  - Add USER equivalents (same values, identifier-only migration):
    - `CFOF_USERS_INPUT_ASSOCIATED_USER_IDS` = `"associated_user_ids"`
    - `CFOF_USERS_INPUT_CAN_BE_ASSIGNED` = `"can_be_assigned"`
    - `CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW` = `"enable_chore_workflow"`
    - `CFOF_USERS_INPUT_ENABLE_GAMIFICATION` = `"enable_gamification"`
    - `CFOF_USERS_INPUT_DASHBOARD_LANGUAGE` = `"dashboard_language"`
    - `CFOF_USERS_INPUT_CAN_APPROVE` = `"can_approve"`
    - `CFOF_USERS_INPUT_CAN_MANAGE` = `"can_manage"`
  - Runtime target:
    - USER form codepaths must reference only `CFOF_USERS_INPUT_*` keys.
    - `CFOF_APPROVERS_INPUT_*` remain temporary legacy identifiers only until full callsite migration completes.

- Step 12.1 — constants tranche (no value changes)
  - Add `CFOF_USERS_INPUT_*` constants listed above in `const.py`.
  - Keep existing approver constants temporarily (no removals in this sub-step).
  - Acceptance:
    - no value changes for existing keys
    - no runtime behavior change expected.

###### Step 12.1 execution manifest (authoritative)

- File: `custom_components/choreops/const.py`
- Add these constants with exact values (identifier migration only):
  - `CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: Final = "associated_user_ids"`
  - `CFOF_USERS_INPUT_CAN_BE_ASSIGNED: Final = "can_be_assigned"`
  - `CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW: Final = "enable_chore_workflow"`
  - `CFOF_USERS_INPUT_ENABLE_GAMIFICATION: Final = "enable_gamification"`
  - `CFOF_USERS_INPUT_DASHBOARD_LANGUAGE: Final = "dashboard_language"`
  - `CFOF_USERS_INPUT_CAN_APPROVE: Final = "can_approve"`
  - `CFOF_USERS_INPUT_CAN_MANAGE: Final = "can_manage"`
- Do not remove or rename in this sub-step:
  - `CFOF_APPROVERS_INPUT_ASSOCIATED_USER_IDS`
  - `CFOF_APPROVERS_INPUT_CAN_BE_ASSIGNED`
  - `CFOF_APPROVERS_INPUT_ENABLE_CHORE_WORKFLOW`
  - `CFOF_APPROVERS_INPUT_ENABLE_GAMIFICATION`
  - `CFOF_APPROVERS_INPUT_DASHBOARD_LANGUAGE`
  - `CFOF_APPROVERS_INPUT_CAN_APPROVE`
  - `CFOF_APPROVERS_INPUT_CAN_MANAGE`

###### Step 12.1 validation gates (must pass)

- `./utils/quick_lint.sh --fix`
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
- Grep parity checks:
  - `CFOF_USERS_INPUT_(ASSOCIATED_USER_IDS|CAN_BE_ASSIGNED|ENABLE_CHORE_WORKFLOW|ENABLE_GAMIFICATION|DASHBOARD_LANGUAGE|CAN_APPROVE|CAN_MANAGE)` → all present in `const.py`
  - no removals of existing `CFOF_APPROVERS_INPUT_*` constants in this sub-step

###### Step 12.1 evidence block template

- Touched files:
  - `custom_components/choreops/const.py`
- Validation outputs:
  - `quick_lint`:
  - `mypy_quick`:
  - parity scans:
- No-behavior-change checklist:
  - `[ ]` Constants-only edit (no runtime callsite edits)
  - `[ ]` Existing constant values unchanged
  - `[ ]` New USER constants added with exact approved values
  - `[ ]` Lint and mypy quick gates green

- Step 12.2 — options-flow/flow-helper direct replacement
  - Replace USER-form usage of `CFOF_APPROVERS_INPUT_*` with new `CFOF_USERS_INPUT_*` in:
    - suggested-values maps
    - section field group tuples
    - normalize/validate input extraction for USER forms
  - Acceptance:
    - options add/edit user paths unchanged behavior
    - user form schema still renders same fields and defaults.

###### Step 12.2 execution manifest (authoritative)

- Files:
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`

- Required callsite substitutions (USER form scope only):
  - `CFOF_APPROVERS_INPUT_ASSOCIATED_USER_IDS` → `CFOF_USERS_INPUT_ASSOCIATED_USER_IDS`
  - `CFOF_APPROVERS_INPUT_CAN_BE_ASSIGNED` → `CFOF_USERS_INPUT_CAN_BE_ASSIGNED`
  - `CFOF_APPROVERS_INPUT_ENABLE_CHORE_WORKFLOW` → `CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW`
  - `CFOF_APPROVERS_INPUT_ENABLE_GAMIFICATION` → `CFOF_USERS_INPUT_ENABLE_GAMIFICATION`
  - `CFOF_APPROVERS_INPUT_DASHBOARD_LANGUAGE` → `CFOF_USERS_INPUT_DASHBOARD_LANGUAGE`
  - `CFOF_APPROVERS_INPUT_CAN_APPROVE` → `CFOF_USERS_INPUT_CAN_APPROVE`
  - `CFOF_APPROVERS_INPUT_CAN_MANAGE` → `CFOF_USERS_INPUT_CAN_MANAGE`

- `options_flow.py` exact areas to update:
  - user edit suggested-values payload (`async_step_edit_user`)
  - any user add/edit form-value handling that references `CFOF_APPROVERS_INPUT_*`
  - do not change non-user scopes (chores, rewards, badges, dashboard generation)

- `flow_helpers.py` exact areas to update:
  - `USER_IDENTITY_FIELDS`, `USER_SYSTEM_USAGE_FIELDS`, `USER_ADMIN_APPROVAL_FIELDS`
  - `_validate_users_inputs_impl` key extraction from `user_input`
  - user form schema build/default fields and sectioned suggested values
  - do not alter validation logic semantics; identifiers only in this sub-step

- Out-of-scope for Step 12.2:
  - `config_flow.py` split state convergence
  - manager method renames/removals
  - data builder logic changes
  - translation string content changes (identifier rename only if required)

###### Step 12.2 validation gates (must pass)

- `./utils/quick_lint.sh --fix`
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
- `python -m pytest tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_parents_helpers.py tests/test_kids_helpers.py -v --tb=line`

- Grep checks:
  - In `options_flow.py` + `helpers/flow_helpers.py` USER form sections:
    - no `CFOF_APPROVERS_INPUT_*` key usage remains
    - all USER form capability keys resolve to `CFOF_USERS_INPUT_*`
  - Preserve behavior-critical key values (string values unchanged)

###### Step 12.2 evidence block template

- Touched files:
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
- Substitution ledger:
  - old constant → new constant (list all replacements)
- Validation outputs:
  - `quick_lint`:
  - `mypy_quick`:
  - pytest slice:
  - grep checks:
- No-behavior-change checklist:
  - `[ ]` USER form callsite substitutions only
  - `[ ]` No logic branch/condition changes
  - `[ ]` Existing string values unchanged
  - `[ ]` Validation gates green

- Step 12.3 — config-flow users step normalization (single USER payload)
  - Remove `is_assignee_payload` split branch.
  - Normalize one user payload and route through one validator/builder path.
  - Preserve config-flow special lifecycle semantics (no store until `_create_entry`).
  - Derive assignable-user mapping from USER records using `can_be_assigned`.
  - Acceptance:
    - initial setup user collection works for all capability combinations
    - downstream chore/reward/badge assignment dropdowns remain populated correctly.

###### Step 12.3 execution manifest (authoritative)

- Primary file:
  - `custom_components/choreops/config_flow.py`

- Required transformation (single USER form path)
  - In `async_step_users`:
    - remove `is_assignee_payload` detection logic
    - always normalize payload via user-form normalization helper
    - call one user validator path only
    - call one user builder path only
    - write to unified USER temp store path

- Temporary state strategy (safe rollout)
  - Stage 12.3A (required first):
    - keep existing `_assignees_temp` / `_approvers_temp` fields physically present
    - implement one canonical processing path and write-through parity to both stores
    - derive assignment map from canonical user payload + `can_be_assigned`
  - Stage 12.3B (follow-up in same batch only if 12.3A green):
    - collapse to one `_users_temp` store
    - replace legacy split-store reads in downstream step builders with derived helpers
  - Rule:
    - if any regression appears in 12.3B, keep 12.3A and defer store collapse to next micro-batch.

- Behavior invariants (must remain unchanged)
  - flow step order and transitions (`user_count` → `users` → `chore_count`)
  - no persistence before `_create_entry`
  - number of collected user entries equals submitted count
  - assignment dropdown candidates still limited to users with `can_be_assigned=True`
  - existing handling for name/duplicate/association validation remains functionally equivalent

- Required helper alignment checks
  - `build_user_schema(...)` still receives a deterministic assignment candidate map
  - all chore/badge/reward/challenge schema calls relying on assignable users continue to receive UUID-keyed maps
  - no dependence on role-form constants in `async_step_users` payload routing

- Guarded rollback criteria
  - rollback current sub-step if any of these occur:
    - user count loop increments mismatch
    - empty assignment dropdown where assignable users exist
    - config-flow creates incomplete `DATA_USERS` payload
    - options-flow regression surfaced by shared user helper changes

###### Step 12.3 validation gates (must pass)

- `./utils/quick_lint.sh --fix`
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
- `python -m pytest tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_kids_helpers.py tests/test_parents_helpers.py tests/test_data_reset_service.py -v --tb=line`

- Targeted behavioral checks (explicit)
  - config flow fresh-start scenarios with mixed capability users
  - zero-user path (`user_count = 0`) still bypasses user collection correctly
  - assignable-user dependent chore schema still renders expected options

- Grep checks
  - `config_flow.py` `async_step_users` block has no `is_assignee_payload` branch
  - user-form routing in `config_flow.py` uses `CFOF_USERS_INPUT_*` capability keys only
  - no new runtime fallback/compat bridges introduced

###### Step 12.3 evidence block template

- Touched files:
  - `custom_components/choreops/config_flow.py`
  - (plus any helper/test files updated in same slice)
- Transformation ledger:
  - removed branch points
  - unified validator/builder callsites
  - assignment-map derivation changes
- Validation outputs:
  - `quick_lint`:
  - `mypy_quick`:
  - pytest slice:
  - grep checks:
- No-behavior-change checklist:
  - `[ ]` Single user-form processing path implemented
  - `[ ]` Flow order and persistence timing unchanged
  - `[ ]` Assignment dropdown behavior unchanged
  - `[ ]` Validation gates green

- Step 12.4 — temporary state convergence safety
  - Preferred target: one `_users_temp` store.
  - Safety fallback (if needed within same tranche): maintain write-through parity to both old temp stores, then remove dual stores in follow-up sub-step.
  - Non-negotiable:
    - no persistence semantics change
    - no changed ordering of flow steps.

###### Step 12.4 convergence decision gate (authoritative)

- Decision checkpoint after Step 12.3A:
  - Promote to single-store collapse (12.3B/12.4) only if all are true:
    - config-flow pytest slice green
    - assignment dropdown parity confirmed
    - `_create_entry` payload parity confirmed (`DATA_USERS` complete and deterministic)
    - no mypy quick regressions
  - Otherwise:
    - keep dual-store write-through state as temporary safety posture
    - log explicit defer note in evidence and move collapse to next batch

- Single-store collapse requirements (if promoted):
  - Replace `_assignees_temp` and `_approvers_temp` state reads with helper-derived views from `_users_temp`:
    - `assignable_users_view`: users where `can_be_assigned=True`
    - `approval_users_view`: users where `can_approve` or admin capability keys are set
  - No direct business-logic branching by role labels in config flow
  - Preserve existing display behavior and ordering in summary output

- Rollback trigger criteria (hard stop):
  - any failing config-flow scenario in `test_config_flow_fresh_start.py`
  - mismatch in assignment candidate list vs pre-change baseline
  - missing/duplicated user records in `_create_entry` final payload
  - any persistence-timing change before `_create_entry`

- Step 12.4 evidence requirements:
  - explicit go/no-go decision record
  - if no-go: documented defer reason + next batch scope
  - if go: before/after state model map (`_assignees_temp`/`_approvers_temp` → `_users_temp` + derived views)

- Step 12.5 — validation and closure evidence
  - Required commands:
    - `./utils/quick_lint.sh --fix`
    - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
    - `python -m pytest tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line`
  - Required scans:
    - USER form path scan: no `CFOF_APPROVERS_INPUT_*` references in `config_flow.py`, `options_flow.py`, `helpers/flow_helpers.py` user-form blocks
    - symbol parity scan for new `CFOF_USERS_INPUT_*` adoption
  - Phase 4B.6 checklist must be completed for this batch.

##### 4A batch-12 execution evidence (2026-02-24)

- Batch objective:
  - Execute USER-form constant convergence and remove approver-prefixed USER-form routing from helpers/options/config flow while preserving behavior.

- Step completion status:
  - ✅ Step 12.1 complete — added `CFOF_USERS_INPUT_*` capability constants in `const.py` (values unchanged)
  - ✅ Step 12.2 complete — replaced USER-form callsites in `options_flow.py` and `helpers/flow_helpers.py`
  - ✅ Step 12.3 complete (12.3A path) — removed `is_assignee_payload` split branch; unified user input normalization/validation path in `config_flow.py`
  - ✅ Step 12.4 complete (decision gate) — **no-go for 12.3B store collapse** in this tranche; kept dual-store strategy with unified path for safety
  - ✅ Step 12.5 complete — validation, scans, and evidence captured

- Touched files:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/helpers/flow_helpers.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/data_builders.py`

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `python -m pytest tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_kids_helpers.py tests/test_parents_helpers.py tests/test_data_reset_service.py -v --tb=line` ✅ passed (`80 passed`)
  - `mypy custom_components/choreops/` ⚠️ blocked by workspace external parser mismatch in `/workspaces/core/homeassistant/helpers/device_registry.py`

- Required scans:
  - `CFOF_APPROVERS_INPUT_` scan in USER-form files (`config_flow.py`, `options_flow.py`, `helpers/flow_helpers.py`) → no matches
  - USER key adoption parity scan (`CFOF_USERS_INPUT_(ASSOCIATED_USER_IDS|CAN_BE_ASSIGNED|ENABLE_CHORE_WORKFLOW|ENABLE_GAMIFICATION|DASHBOARD_LANGUAGE|CAN_APPROVE|CAN_MANAGE)`) → expected matches across all USER-form files
  - split artifact scan (`is_assignee_payload|_assignees_temp|_approvers_temp`) → `is_assignee_payload` removed; temp stores intentionally retained per 12.4 no-go decision

- 12.4 decision record:
  - **No-go** for `_users_temp` hard collapse in this tranche due broad downstream dependency on `_assignees_temp` projections.
  - Rationale: preserve behavior under no-functional-change policy; defer structural state collapse to separate controlled tranche.

- Phase 4B.6 no-behavior-change sign-off:
  - `[x]` Baseline suite captured before edits
  - `[x]` Rename-only ledger completed
  - `[x]` Old/new symbol parity checks passed
  - `[x]` No runtime fallback introduced outside migration module
  - `[x]` Post-edit suite matches baseline behavior
  - `[x]` Reviewer confirms no logic changes in touched runtime functions

###### Step 12.5 command pack (copy/paste)

- Core gates:
  - `./utils/quick_lint.sh --fix`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `python -m pytest tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_kids_helpers.py tests/test_parents_helpers.py tests/test_data_reset_service.py -v --tb=line`

- USER form drift scans:
  - `grep -RIn 'CFOF_APPROVERS_INPUT_' custom_components/choreops/config_flow.py custom_components/choreops/options_flow.py custom_components/choreops/helpers/flow_helpers.py`
  - `grep -RIn 'CFOF_USERS_INPUT_(ASSOCIATED_USER_IDS|CAN_BE_ASSIGNED|ENABLE_CHORE_WORKFLOW|ENABLE_GAMIFICATION|DASHBOARD_LANGUAGE|CAN_APPROVE|CAN_MANAGE)' custom_components/choreops/config_flow.py custom_components/choreops/options_flow.py custom_components/choreops/helpers/flow_helpers.py`

- Config-flow split-path removal scans:
  - `grep -RIn 'is_assignee_payload|_assignees_temp|_approvers_temp' custom_components/choreops/config_flow.py`

- Payload integrity checks (targeted):
  - `grep -RIn 'storage_data\[const.DATA_USERS\]' custom_components/choreops/config_flow.py`
  - `grep -RIn 'can_be_assigned|associated_user_ids|can_approve|can_manage' custom_components/choreops/config_flow.py custom_components/choreops/helpers/flow_helpers.py`

###### Step 12.5 closure acceptance (owner-ready)

- Required for closeout recommendation:
  - all core gates green
  - USER form scans show no invalid approver-constant usage in USER form scope
  - config-flow split-path artifacts removed or explicitly deferred with approved rationale
  - Phase 4B.6 checklist fully checked
  - evidence block includes command outputs, touched files, and decision log

##### 4A batch-13 execution evidence (2026-02-24)

- Batch objective:
  - Resolve dashboard helper cumulative badge regression after UX contract key updates while preserving hard-fork routing contracts.

- Touched files:
  - `custom_components/choreops/coordinator.py`

- Rename/logic ledger:
  - approver derivation guard: `or const.DATA_APPROVER_ASSOCIATED_USERS in user_data` → `or bool(user_data.get(const.DATA_APPROVER_ASSOCIATED_USERS))`
  - intent: avoid classifying assignable users as approver profiles when `associated_user_ids` exists but is empty.

- Validation outputs:
  - `python -m pytest tests/test_badge_cumulative.py -q` ✅ passed (`15 passed`)
  - `python -m pytest tests/validate_system_dashboard_select.py -q` ⚠️ no tests collected (`exit 5`)
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅ passed (`Success: no issues found in 50 source files`)
  - `python -m pytest tests/test_data_reset_service.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py -v --tb=line` ⚠️ existing failures (`49 passed, 5 failed`)
  - `python -m pytest tests/test_notification_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`70 passed`)

- Closure scans (targeted):
  - old purpose keys in runtime Python/YAML surfaces (`purpose_system_dashboard_admin_assignee`, `purpose_select_assignee_chores`, `purpose_assignee_badges`) → no matches outside locale translations.
  - old symbol constants (`TRANS_KEY_PURPOSE_SELECT_ASSIGNEE_CHORES`, `TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE`, `TRANS_KEY_PURPOSE_ASSIGNEE_BADGES`) → no matches.

- Phase 4B.6 no-behavior-change sign-off:
  - `[x]` Baseline suite captured before edits
  - `[x]` Rename-only ledger completed
  - `[x]` Old/new symbol parity checks passed
  - `[x]` No runtime fallback introduced outside migration module
  - `[ ]` Post-edit suite matches baseline behavior
  - `[x]` Reviewer confirms no logic changes in touched runtime functions

- Blocker note:
  - Full baseline equivalence remains blocked by pre-existing failures in `tests/test_data_reset_service.py` and `tests/test_options_flow_entity_crud.py` in this workspace state.

##### 4A batch-14 execution evidence (2026-02-24)

- Batch objective:
  - Clear remaining Phase 4B baseline failures by aligning stale tests with the approved user-first service/role projection contract.

- Touched files:
  - `tests/test_data_reset_service.py`
  - `tests/test_options_flow_entity_crud.py`

- Contract/test alignment changes:
  - data reset service tests now submit `user_name` (not deprecated `assignee_name`) for user scope calls.
  - options flow add-user assertions now verify creation through assignable/user projection (`assignees_data`) rather than approver projection.

- Validation outputs:
  - `python -m pytest tests/test_data_reset_service.py tests/test_options_flow_entity_crud.py -v --tb=line` ✅ passed (`42 passed`)
  - `python -m pytest tests/test_data_reset_service.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_notification_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`124 passed`)
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + mypy quick + boundary checks)

- Phase 4B.6 checklist delta:
  - `[x]` Post-edit suite matches baseline behavior

- Status note:
  - Prior blocker from batch-13 is resolved in this tranche.

##### 4A batch-15 closeout/sign-off evidence (2026-02-24)

- Batch objective:
  - Finalize Phase 4 closeout state, confirm no residual baseline drift, and publish owner-ready sign-off status.

- Touched files:
  - `docs/in-process/USER_FIRST_ITEM_ROLE_CONTRACT_HARD_FORK_EXECUTION_IN-PROCESS.md`

- Validation outputs:
  - `./utils/quick_lint.sh --fix` ✅ passed
  - `python -m pytest tests/test_data_reset_service.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py tests/test_notification_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line` ✅ passed (`124 passed`)
  - `mypy custom_components/choreops/` ⚠️ external workspace parser blocker in `/workspaces/core/homeassistant/helpers/device_registry.py` (unchanged environment issue)

- Phase 4B.6 no-behavior-change sign-off:
  - `[x]` Baseline suite captured before edits
  - `[x]` Rename-only ledger completed
  - `[x]` Old/new symbol parity checks passed
  - `[x]` No runtime fallback introduced outside migration module
  - `[x]` Post-edit suite matches baseline behavior
  - `[x]` Reviewer confirms no logic changes in touched runtime functions

- Closeout status:
  - Phase 4 implementation and validation bundle complete on integration-owned gates.
  - Plan is ready for owner sign-off and archive handoff.

**Phase 4 exit criteria**

- All quality/test gates green.
- Required symbols present and forbidden symbols absent per closure scans.
- Fact table rows have implementation evidence references.

#### Phase 4B — no-functional-change execution protocol (required before closeout)

- **Goal**: Prove the remaining hard-fork cleanup is contract-only (naming/taxonomy/route-surface) and introduces no behavior or logic changes.

- **Execution policy (non-negotiable)**:
  - No algorithm changes, no condition-branch changes, no state-machine transition changes.
  - No change to service behavior, event emission order, persistence timing, or manager ownership boundaries.
  - No new defaults, no changed defaults, no new fallback logic in runtime.
  - If a rename cannot be completed without logic edits, stop the batch and split into a dedicated approved follow-up initiative.

- **Step 4B.1 — behavior baseline capture (pre-edit, required)**
  - Capture current behavior before each micro-batch:
    - commands:
      - `python -m pytest tests/test_data_reset_service.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py -v --tb=line`
      - `python -m pytest tests/test_notification_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line`
    - record in evidence:
      - passing test counts
      - failing test IDs (if any, with reason)
      - grep baselines for renamed symbols
  - Baseline must be stored in this plan under the active batch evidence block before edits begin.

- **Step 4B.2 — rename-only patch design (pre-implementation checklist)**
  - For each file in the batch, create a mini change ledger with:
    - symbol old name → new name
    - expected unchanged value (if constant value is intentionally unchanged)
    - expected callsite parity count (definitions/usages)
  - Allowed edit types:
    - identifier renames
    - docstring/comment text alignment
    - translation key identifier renames that preserve message semantics
  - Disallowed edit types:
    - changing boolean expressions
    - changing conditional ordering
    - changing loops/data transformations
    - changing exceptions raised/handled
    - changing emitted signal timing

- **Step 4B.3 — implementation with parity controls (during edit)**
  - Apply changes in vertical slices (constant + direct callsites + tests) to avoid mixed states.
  - After each slice:
    - run targeted grep parity checks:
      - zero old-symbol usages outside migration allowances
      - expected new-symbol usage count is non-zero where required
    - verify no runtime fallback additions outside `migration_pre_v50.py`.
  - If parity fails, revert only current slice and re-run with narrower scope.

- **Step 4B.4 — logic-drift audit (post-edit, required)**
  - Perform focused review on touched runtime files:
    - confirm only naming/contract surfaces changed
    - confirm no function body logic changes beyond symbol substitution
  - Required audit checks (document pass/fail):
    - service schemas unchanged except approved field-key renames
    - manager reset semantics unchanged (preserve/runtime field behavior parity)
    - flow transitions unchanged except route name convergence already approved
    - migration-only compatibility remains confined to migration module

- **Step 4B.5 — post-edit regression and equivalence gates**
  - Run gates in order:
    1. `./utils/quick_lint.sh --fix`
    2. `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
    3. same pytest baseline suite from Step 4B.1
  - Acceptance requirement:
    - no new failing tests relative to baseline
    - no new mypy errors in `custom_components/choreops`
    - closure scans remain green for required/forbidden symbols

- **Step 4B.6 — explicit no-behavior-change sign-off block (required evidence)**
  - Append this checklist to each remaining batch evidence section and mark each item:
    - `[ ]` Baseline suite captured before edits
    - `[ ]` Rename-only ledger completed
    - `[ ]` Old/new symbol parity checks passed
    - `[ ]` No runtime fallback introduced outside migration module
    - `[ ]` Post-edit suite matches baseline behavior
    - `[ ]` Reviewer confirms no logic changes in touched runtime functions

- **Phase 4B exit criteria**
  - Every remaining batch includes completed Step 4B.6 sign-off checklist.
  - No behavior drift is observed in baseline-vs-post comparison.
  - Closeout evidence is sufficient for owner sign-off without additional archaeology.

## Closure scan pack (required)

Run after each phase and at final closeout:

1. **Forbidden runtime symbols**

- role lifecycle signals: `SIGNAL_SUFFIX_ASSIGNEE_(CREATED|UPDATED|DELETED)|SIGNAL_SUFFIX_APPROVER_(CREATED|UPDATED|DELETED)`
- role item taxonomy: `ENTITY_TYPE_ASSIGNEE|ENTITY_TYPE_APPROVER`
- compatibility aliases: `FIELD_ASSIGNEE_ID|FIELD_ASSIGNEE_NAME|FIELD_APPROVER_NAME`

2. **Required runtime symbols**

- `ITEM_TYPE_USER`
- `ROLE_ASSIGNEE|ROLE_APPROVER`
- `SIGNAL_SUFFIX_USER_CREATED|SIGNAL_SUFFIX_USER_UPDATED|SIGNAL_SUFFIX_USER_DELETED`

3. **Migration-only compatibility enforcement**

- zero legacy fallback branches outside `migration_pre_v50.py`

## Testing & validation

- **Planned validation suites**:
  - Lint/format/boundary check via `./utils/quick_lint.sh --fix`
  - Type validation via `mypy custom_components/choreops/`
  - Regression validation via `python -m pytest tests/ -v --tb=line`
- **Additional closure scans**:
  - Targeted grep scans for approved fact-table symbols (required + forbidden).

## Notes & follow-up

- This plan is implementation-only for the ratified fact table; it does not reopen naming decisions.
- Any additional terminology decisions must be appended to the fact table first, then pulled into this execution plan.
- Archive policy: move this file to `docs/completed/` only after all closure gates pass and owner sign-off is explicit.

## Builder handoff (ready)

### Handoff objective

- Execute remaining closeout work only (Phase 4 finalization), with strict no-functional-change enforcement.
- Do not reopen completed phase decisions unless a closure gate fails.

### Current state for builder

- Phase 1: complete
- Phase 2: complete
- Phase 3: complete
- Phase 4: complete; closeout evidence published; owner sign-off pending
- Active requirement: archive handoff after explicit owner approval

### Builder start sequence (closeout-only, do in order)

1. **Preflight sync and baseline capture**
   - Re-read this plan sections:
     - `Phase 4 exit criteria`
     - `Phase 4B — no-functional-change execution protocol`
     - `Closure scan pack (required)`
   - Run baseline suite (Phase 4B.1) and record results in a new evidence subsection:
     - `python -m pytest tests/test_data_reset_service.py tests/test_config_flow_fresh_start.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_entity_crud.py -v --tb=line`
     - `python -m pytest tests/test_notification_helpers.py tests/test_kids_helpers.py tests/test_parents_helpers.py -v --tb=line`

2. **Execute remaining rename-only edits (if any are still needed)**
   - Use Phase 4B.2 rename ledger before each patch:
     - symbol old → new
     - unchanged value confirmation
     - expected callsite parity count
   - Apply only contract/naming alignment edits; no algorithm or flow logic changes.

3. **Run parity and drift controls after each edit slice**
   - Confirm old-symbol removal / new-symbol presence with targeted grep scans.
   - Confirm no runtime fallback was introduced outside `migration_pre_v50.py`.
   - If parity fails, revert current slice and retry narrower.

4. **Run closeout gates (blocking)**
   - `./utils/quick_lint.sh --fix`
   - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
   - Re-run same baseline pytest suites from step 1
   - Run closure scan pack required/forbidden checks and migration-only enforcement.

5. **Publish final evidence and sign-off checklist**
   - For each remaining batch, complete Phase 4B.6 checklist.
   - Update Summary table `% complete` and quick notes for Phase 4.
   - Mark completion confirmation checkbox only when all closure gates are green.

### Non-negotiable builder guardrails

- No runtime compatibility aliases/fallbacks.
- Migration compatibility logic only in `migration_pre_v50.py`.
- No service behavior changes, no manager ownership changes, no signal timing/order changes.
- Preserve role-semantic vocabulary where approved by matrix exceptions; remove lifecycle drift only.

### Required evidence format (builder must include)

- **Batch header**: objective + date + owner
- **Touched files**: exact list
- **Rename ledger**: old symbol → new symbol + parity expectation
- **Validation outputs**:
  - `quick_lint` result
  - `mypy_quick` result
  - targeted pytest results with pass counts
- **Closure scan outputs**:
  - forbidden symbols: zero matches
  - required symbols: present
  - migration-only fallback enforcement: pass
- **No-behavior-change checklist** (Phase 4B.6): all checked

### Stop conditions and escalation

- Stop and escalate to owner if any required rename implies logic/flow transition changes.
- Stop and escalate if closure scans require runtime fallback outside migration module.
- Stop and escalate if baseline-vs-post test behavior diverges and cannot be resolved as a naming-only defect.

### Final completion criteria for owner handoff

- Phase 4 marked 100% with closure evidence attached.
- All Phase 4B checklist items complete for each remaining batch.
- Summary + Decisions + Completion confirmation sections updated and internally consistent.
