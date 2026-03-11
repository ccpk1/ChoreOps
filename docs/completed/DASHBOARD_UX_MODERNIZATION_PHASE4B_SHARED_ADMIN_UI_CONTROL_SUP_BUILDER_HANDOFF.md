# Supporting archive: Phase 4B shared-admin ui_control blueprint

## Initiative snapshot

- **Name / Code**: Dashboard UX modernization Phase 4B shared-admin `ui_control` contract (`DASHBOARD_UX_MODERNIZATION_PHASE4B_SHARED_ADMIN_UI_CONTROL`)
- **Target release / milestone**: v0.5.x pre-release (schema 45 window)
- **Owner / driver(s)**: Builder implementation owner + ChoreOps maintainers (approval gates required)
- **Status**: Archived - completed

## Archive notice

Execution for this phase is complete and this file is retained as historical implementation evidence only.

Authoritative archive summary:

- `docs/completed/DASHBOARD_UX_MODERNIZATION_PHASE4B_SHARED_ADMIN_UI_CONTROL_COMPLETED.md`

The umbrella dashboard modernization program remains active in:

- `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`

## Summary & immediate steps

| Phase / Step                                | Description                                                                           | % complete | Quick notes                                              |
| ------------------------------------------- | ------------------------------------------------------------------------------------- | ---------: | -------------------------------------------------------- |
| Preflight - Workspace hygiene gate          | Finish dashboard sync/test/doc cleanup and commit before integration contract work    |         75 | Baseline prepared; rollback anchor SHA not recorded here |
| Phase 1 - Contract constants + data model   | Add canonical constants and shared-admin storage root under `data/meta`               |        100 | Implemented and targeted validation green                |
| Phase 2 - Service + manager ownership split | Route `manage_ui_control` writes to user-owned or shared-admin-owned targets          |        100 | Implemented and targeted validation green                |
| Phase 3 - Sensor/snippet/template contract  | Expose system helper and snippet variables; enforce `ui_root` split in admin template |        100 | Implemented and targeted validation green                |
| Phase 4 - Tests + release gates             | Add regression/contract coverage and run required command gates                       |        100 | Completed in four 25 percent terminal batches            |

1. **Key objective** - Implement one stable shared-admin state owner (`data/meta/shared_admin_ui_control`) without breaking per-user dashboard behavior.
2. **Summary of recent work** - Phase 3 added the shared-admin system helper sensor, expanded the shared admin snippet contract to provide both `ui_root.shared_admin` and `ui_root.selected_user`, split canonical and vendored admin-shared template ownership, synced dashboard assets, cleaned up dashboard manifest metadata, and completed Phase 4 release-gate validation.
3. **Next steps (short term)** - No further execution in this file. Any remaining admin template UX polish continues in the separate follow-up plan.
4. **Risks / blockers**
   - Cross-owner drift risk if any admin-shared card still reads selected-user `ui_control`.
   - Template/runtime drift risk if snippet contract changes without matching template test updates.
   - Migration risk if `meta` defaults or schema enforcement paths are bypassed.
5. **References**
   - `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Shared-admin persistent path: `data/meta/shared_admin_ui_control`.
     - Shared-admin helper identity: system helper sensor with purpose `purpose_system_dashboard_helper`.
     - Shared-admin language selection order: selected user language -> first associated admin fallback language -> integration default language.
     - Shared-admin template ownership split: top-level admin cards read `ui_root.shared_admin`; selected-user views read `ui_root.selected_user`.
     - Single-template strategy remains target end-state; this blueprint only stabilizes contract first.
   - **Completion confirmation**: `[x]` All phases and hard gates completed and archived.

## Tracking expectations

- **Summary upkeep**: Update percentages and gate status after each completed phase.
- **Detailed tracking**: Record exact file/method changes in each step with date and PR/commit evidence.
- **Validation execution policy**: Run lint and tests only in an actual terminal session so output is captured. For pytest, the only acceptable invocation pattern going forward is `python -m pytest ...`.
- **Mid-phase validation policy**: During active implementation inside a phase, run only targeted terminal pytest commands for the files and contracts touched by that step.
- **Completion-gate validation policy**: Run `python -m pytest tests/ -v --tb=line` only after the phase's code changes are believed complete and ready for gate review.

## Detailed phase tracking

### Preflight - Workspace hygiene gate

- **Goal**: Ensure Builder starts from a clean and reversible baseline after expected dashboard sync churn.
- **Steps / detailed work items**

1. [x] Complete dashboard sync-related test/doc cleanup currently in progress (dashboard-focused diffs only).
   - Scope includes dashboard templates/translations/preferences/tests/docs cleanup from the active sync cycle.
2. [x] Commit cleanup-only changes first as a standalone commit before any Phase 4B integration contract changes.
   - Commit intent: baseline normalization only (no new shared-admin contract behavior).
3. [x] Verify working tree is clean (or only intentionally unrelated tracked work) before starting Phase 1.
4. [ ] Record cleanup commit SHA in the main initiative plan to establish rollback anchor.

- **Key issues**
  - Do not mix cleanup commit and Phase 4B behavior changes in the same commit.
  - The cleanup commit is a hard prerequisite for safe revert/cherry-pick workflows.

### Phase 1 - Contract constants + data model

- **Goal**: Introduce canonical names and storage root for shared-admin UI state with zero runtime behavior change.
- **Steps / detailed work items**

1. [x] Add shared-admin data path constants in `custom_components/choreops/const.py` near existing `DATA_META*` and `ui_control` constants.
   - Add constants: `DATA_META_SHARED_ADMIN_UI_CONTROL`, `UI_CONTROL_TARGET_USER`, `UI_CONTROL_TARGET_SHARED_ADMIN`, and any needed `ATTR_UI_ROOT_*` names.
   - Keep string values stable and explicit (`"shared_admin_ui_control"`, `"user"`, `"shared_admin"`).
   - Anchor: `custom_components/choreops/const.py:353`, `custom_components/choreops/const.py:2748`, `custom_components/choreops/const.py:3233`.
2. [x] Extend translation keys/constants in `custom_components/choreops/const.py` and `custom_components/choreops/translations/en.json` for new service-target validation errors.
   - Add keys for invalid `ui_control_target` values and missing/invalid shared-admin target context.
   - Preserve current `ui_control_target_required` behavior for user scope.
   - Anchor: `custom_components/choreops/const.py:3140`, `custom_components/choreops/translations/en.json:4981`.
3. [x] Ensure default store structure initializes shared-admin bucket under `meta`.
   - Add `data[meta][shared_admin_ui_control] = {}` in `ChoreOpsStore.get_default_structure()`.
   - Confirm no top-level storage root additions.
   - Anchor: `custom_components/choreops/store.py` (default structure block near existing `meta` initialization).
4. [x] Add/adjust schema45 migration shim for existing installs that have `meta` but no shared-admin bucket.
   - Implement idempotent migration in `custom_components/choreops/migration_pre_v50.py` and register marker constant in `custom_components/choreops/const.py` migration identifiers section.
   - Do not increment schema version beyond 45 in this workstream.
   - Anchor: `custom_components/choreops/migration_pre_v50.py:74`, `custom_components/choreops/const.py:2877`, `custom_components/choreops/coordinator.py:343`.
5. [x] Add phase-level unit tests for schema/default behavior.
   - Validate new-store default includes empty shared-admin bucket.
   - Validate migration path backfills bucket without mutating unrelated `meta` fields.
   - Candidate files: `tests/test_entity_loading_extension.py`, add targeted schema test module if clearer.
6. [x] Validate Phase 1 with terminal-only targeted pytest commands before Gate A review.
   - Use `python -m pytest` only.
   - Prefer focused migration/storage tests while Phase 1 is still in progress.

**Phase 1 evidence**

- Code changes landed in `const.py`, `store.py`, `migration_pre_v50.py`, `translations/en.json`, `tests/test_schema45_user_migration.py`, and `tests/test_storage_manager.py`.
- `./utils/quick_lint.sh --fix` passed.
- `/workspaces/choreops/.venv/bin/python -m mypy custom_components/choreops/` passed.
- `python -m pytest tests/test_schema45_user_migration.py tests/test_storage_manager.py -v --tb=line` passed (`40 passed`).
- Additional targeted sanity run for prior SIGKILL artifacts passed: `python -m pytest tests/test_approval_reset_contract_parity.py tests/test_approval_reset_overdue_interaction.py tests/test_chore_engine.py -v --tb=line` (`124 passed`).
- Full-suite terminal command remains reserved for final completion gate per policy; an earlier attempt was killed by the environment and is not treated as gate evidence.

- **Key issues**
  - Must not accidentally create dual canonical roots for shared-admin state.
  - Migration must remain idempotent and marker-driven.

### Phase 2 - Service + manager ownership split

- **Goal**: Make `manage_ui_control` explicitly owner-aware while preserving current per-user behavior by default.
- **Steps / detailed work items**

1. [x] Extend service schema for `manage_ui_control` to accept `ui_control_target` with default user targeting.
   - Update `MANAGE_UI_CONTROL_SCHEMA` in `custom_components/choreops/services.py`.
   - Default target must remain `user` for backward compatibility.
   - Allowed values are validated in manager logic so translated runtime errors remain available.
   - Anchor: `custom_components/choreops/services.py` (`MANAGE_UI_CONTROL_SCHEMA` block near current action/key/value fields).
2. [x] Keep service handler routing through one manager API, but pass target explicitly.
   - Update `async_handle_manage_ui_control` in `custom_components/choreops/services.py`.
   - Extend `UserManager.async_manage_ui_control(call_data)` call contract to include target handling.
   - Anchor: `custom_components/choreops/services.py` (manage handler) and `custom_components/choreops/managers/user_manager.py:165`.
3. [x] Split target resolution in `UserManager`.
   - Keep `_resolve_ui_control_target_user()` for `user` target path.
   - Add shared-admin path methods: `_resolve_ui_control_target_shared_admin()`, `_get_shared_admin_ui_control_bucket()`, and target-aware set/clear wrappers.
   - Preserve existing key-path validation helper semantics.
   - Anchor: `custom_components/choreops/managers/user_manager.py:238`, `custom_components/choreops/managers/user_manager.py:287`.
4. [x] Add read API in `UIManager` for shared-admin `ui_control` payload.
   - Add `get_shared_admin_ui_control()` returning a deep copy of `data[meta][shared_admin_ui_control]`.
   - Keep `get_dashboard_ui_control(user_id)` unchanged for selected-user helper payload.
   - Anchor: `custom_components/choreops/managers/ui_manager.py:152`.
5. [x] Add strict logging and error translation placeholders for target-aware failures.
   - Use lazy logging only.
   - Ensure exceptions remain `HomeAssistantError` with translation keys.
   - Anchor: `custom_components/choreops/managers/user_manager.py:174`.
6. [x] Validate Phase 2 with terminal-only targeted pytest commands before Gate B review.
   - Use `python -m pytest` only.
   - Prefer service and manager test modules relevant to `manage_ui_control` target routing.

**Phase 2 evidence**

- Code changes landed in `services.py`, `managers/user_manager.py`, `managers/ui_manager.py`, `services.yaml`, `translations/en.json`, `tests/test_ui_control_contract_parity.py`, and `tests/test_ui_control_services.py`.
- `python -m pytest tests/test_ui_control_contract_parity.py -v --tb=line -o log_cli=false` passed (`2 passed`).
- `python -m pytest tests/test_ui_control_services.py -v --tb=line -o log_cli=false` passed (`9 passed`).
- `./utils/quick_lint.sh --fix` passed.
- `/workspaces/choreops/.venv/bin/python -m mypy custom_components/choreops/` passed.
- Backward compatibility for the default `user` target is covered by the existing per-user service tests in `tests/test_ui_control_services.py`.

- **Key issues**
  - No direct storage writes outside manager-owned methods.
  - Target routing must not permit ambiguous writes (for example, shared-admin target + user_id payload mismatch).

### Phase 3 - Sensor/snippet/template contract

- **Goal**: Publish shared-admin state to dashboard templates and enforce root ownership boundaries.
- **Steps / detailed work items**

1. [x] Add a system-level dashboard helper sensor entity in `custom_components/choreops/sensor.py`.
   - New class should follow existing system sensor patterns (see `SystemDashboardTranslationSensor`).
   - Required attributes:
     - `purpose: purpose_system_dashboard_helper`
     - `integration_entry_id`
     - `ui_control` (shared-admin bucket)
       - `user_dashboard_helpers` (pointer map only)
     - `language`
     - `dashboard_lookup_key` (stable helper lookup string for shared-admin context)
   - Anchor: `custom_components/choreops/sensor.py:3887`, `custom_components/choreops/sensor.py:3960`, `custom_components/choreops/sensor.py:4887`.
2. [x] Define shared-admin language resolution helper used by the new system sensor.
   - Order: selected user language -> first associated admin fallback -> default language.
   - Keep deterministic tie-break rules for multiple associated admins (for example sorted by name/id).
   - Anchor: `custom_components/choreops/sensor.py:4831` (existing language pattern), plus user-association access in coordinator user data.
3. [x] Extend snippet builder contract in `custom_components/choreops/helpers/dashboard_helpers.py`.
   - Update `_build_template_snippets()` so `template_snippets.admin_setup_shared` resolves both:
     - `admin_selector_eid` (existing purpose lookup)
     - `shared_admin_helper_eid` (new system helper lookup by purpose + `integration_entry_id`)
   - Expose template variables to construct:
     - `ui_root.shared_admin`
     - `ui_root.selected_user`
   - Anchor: `custom_components/choreops/helpers/dashboard_helpers.py:1389`, `custom_components/choreops/helpers/dashboard_helpers.py:1468`.
4. [x] Update `admin-shared-v1` template contract in dashboard assets to use explicit ownership split.
   - In `choreops-dashboards/templates/admin-shared-v1.yaml` and vendored `custom_components/choreops/dashboards/templates/admin-shared-v1.yaml`, enforce:
     - top-level admin cards read only `ui_root.shared_admin`
     - selected-user cards read only `ui_root.selected_user`
   - Remove current mixed-source fallback patterns in shared cards.
   - Anchor: admin shared template `ui_control_source`/collapse root blocks.
5. [x] Add or update template preferences documentation to match defaults and ownership rules.
   - Update `choreops-dashboards/preferences/admin-shared-v1.md`.
   - Ensure documented defaults match template `| default(...)` values exactly.
6. [x] Validate Phase 3 with terminal-only targeted pytest commands before Gate C review.
   - Use `python -m pytest` only.
   - Prefer focused sensor, dashboard context, template contract, and render smoke tests.

**Phase 3 evidence**

- Code changes landed in `custom_components/choreops/const.py`, `custom_components/choreops/sensor.py`, `custom_components/choreops/helpers/dashboard_helpers.py`, `custom_components/choreops/translations/en.json`, `custom_components/choreops/icons.json`, `choreops-dashboards/templates/admin-shared-v1.yaml`, `choreops-dashboards/preferences/admin-shared-v1.md`, `tests/test_dashboard_context_contract.py`, `tests/test_dashboard_template_contract.py`, `tests/test_dashboard_template_render_smoke.py`, and `tests/test_dashboard_provenance_contract.py`.
- `utils/sync_dashboard_assets.py` ran successfully and reported parity passed.
- `./utils/quick_lint.sh --fix` passed.
- `/workspaces/choreops/.venv/bin/python -m mypy custom_components/choreops/` passed.
- `python -m pytest tests/test_dashboard_context_contract.py tests/test_dashboard_template_contract.py tests/test_dashboard_template_render_smoke.py tests/test_dashboard_provenance_contract.py -v --tb=line` passed (`21 passed`).

- **Key issues**
  - Shared-admin snippet contract must remain metadata-driven; no hardcoded entity IDs.
  - Any unresolved helper lookup must degrade to existing markdown validation behavior, not silent failure.

### Phase 4 - Tests + release gates

- **Goal**: Prevent regression and drift before any additional admin UX modernization work.
- **Steps / detailed work items**

1. [x] Add or extend targeted tests for:
   - Validate `user` target path writes to `users[*].ui_preferences`.
   - Validate `shared_admin` target path writes to `meta.shared_admin_ui_control`.
   - Validate invalid/missing target cases raise translated errors.
   - Candidate files: new focused test module under `tests/test_*ui_control*`, plus service-layer contract tests.
2. [ ] Add/extend sensor tests for new system helper attributes and language derivation.
3. [x] Run dashboard asset sync and parity verification after template updates.
4. [x] Run required validation gates:
   - Update `tests/test_dashboard_context_contract.py` for `admin_setup_shared` payload expectations.
   - Update `tests/test_dashboard_template_contract.py` for required shared-admin snippet usage markers.
5. [ ] Add regression test to lock `admin-shared-v1` root ownership split.
   - Assert shared-card controls never read selected-user root and vice versa.
   - Candidate file: `tests/test_dashboard_template_render_smoke.py` or new dedicated admin shared contract test.
   - Full-suite coverage was executed in four 25 percent `python -m pytest` batches per owner instruction, with failures fixed before continuing.

- **Phase 4 evidence**

- `./utils/quick_lint.sh --fix` passed.
- Dashboard manifest regression fix landed in both canonical and vendored `dashboard_registry.json` files:
  - `admin-peruser-v1` now declares the `ha-card:button-card` runtime dependency.
  - classic admin template ids now follow the `-v1` contract.
- Fast regression confirmation passed: `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line` (`6 passed`).
- Full test suite executed in four 25 percent terminal batches:
  - Batch 1: `518 passed`
  - Batch 2: `366 passed`, `4 skipped`
  - Batch 3: `325 passed`, `2 deselected`
  - Batch 4: `456 passed`
- Aggregate release-gate coverage across the four batches: `1665 passed`, `4 skipped`, `2 deselected`.
- Dashboard asset sync parity remained green after the shared-admin snippet/template refactor.

5. [ ] Run mandatory quality gates and record evidence in main initiative plan.
   - `./utils/quick_lint.sh --fix`
   - `mypy custom_components/choreops/`
   - `python -m pytest tests/ -v --tb=line`
   - Run these commands in an actual terminal session only.
   - Do not use non-terminal test runners for phase sign-off.

- **Key issues**
  - Must update both canonical dashboard assets and vendored runtime assets using established sync workflow.
  - Do not proceed to `admin-shared-v2`/`admin-peruser-v2` until Phase 4 gates pass.

## Hard stop approval gates (mandatory)

0. **Gate 0 (preflight)**
   - Required evidence: dashboard sync/test/doc cleanup commit landed; rollback anchor SHA documented.
   - Stop condition: no Phase 4B integration implementation starts before this gate is approved.
1. **Gate A (after Phase 1)**
   - Required evidence: constants, store default, migration tests green.
   - Current state: ready for approval.
   - Stop condition: no service/manager/sensor/template behavior edits merged before approval.
2. **Gate B (after Phase 2)**
   - Required evidence: service schema + manager routing tests green, backward compatibility for default user target confirmed.
   - Current state: ready for approval.
   - Stop condition: no sensor/snippet/template edits merged before approval.
3. **Gate C (after Phase 3)**
   - Required evidence: system helper exists, snippet provides both roots, admin-shared template split complete in canonical and vendored assets.
   - Current state: approved and completed.
   - Stop condition: no final release readiness sign-off before Phase 4 tests.
4. **Gate D (after Phase 4)**
   - Required evidence: all mandatory commands pass, plan evidence updated, zero unresolved blockers.
   - Current state: complete.
   - Stop condition: Phase 4 admin modernization work stays blocked until this gate is approved.

## Validation matrix (pass/fail)

| Check                     | Pass criteria                                                                            | Fail trigger                                                      |
| ------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Schema/meta contract      | `meta.shared_admin_ui_control` always present after new install or migration             | Missing bucket, duplicate root, or schema > 45                    |
| Service ownership routing | `manage_ui_control` writes only to target-selected owner                                 | Mixed writes or ambiguous target resolution                       |
| Snippet lookup contract   | `admin_setup_shared` resolves selector + shared helper dynamically by metadata           | Hardcoded entity IDs or unresolved helper without validation card |
| Template root ownership   | Shared cards use `ui_root.shared_admin`; selected-user cards use `ui_root.selected_user` | Any mixed root access in same ownership domain                    |
| Docs/default parity       | Preferences docs match template defaults exactly                                         | Drift between docs and template defaults                          |

## Testing & validation

- Terminal execution policy: All lint and pytest validation must run in a real terminal session.
- Pytest invocation policy: The only acceptable pytest form is `python -m pytest ...`.
- Mid-phase practice: Run targeted pytest commands while a phase is still being implemented.
- Final gate practice: Run `python -m pytest tests/ -v --tb=line` only when the active phase or change set is believed complete.
- Current validation status: Phase 1-4 terminal validation is complete. The full suite was executed as four 25 percent `python -m pytest` batches to satisfy the approved batching rule for this phase.

## Notes & follow-up

- This blueprint intentionally isolates contract stabilization from larger admin v2 UX redesign.
- After Gate D approval, Phase 4 admin modernization may proceed with a stable shared-admin state foundation.
